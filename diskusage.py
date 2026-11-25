"""Disk Usage analyzer window.

Scans a drive with os.scandir (no symlink/junction following, access-denied
skipped silently) and lists the largest top-level folders.  Drill down by
double-clicking, go back with the Back button.  Read-only: no delete actions.
All worker-thread output flows through a queue polled with after().
"""
import os
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import ttk
import queue

try:
    import winreg
except ImportError:  # not on Windows (e.g. linting on Linux)
    winreg = None

BG = "#0f172a"
PANEL = "#1e293b"
BORDER = "#334155"
FG = "#f8fafc"
MUTED = "#94a3b8"
LOG_BG = "#020617"

BAR_FULL = "█"
BAR_EMPTY = "░"
BAR_LEN = 10


def format_size(num_bytes):
    try:
        num_bytes = int(num_bytes)
    except (TypeError, ValueError):
        return "0 B"
    if num_bytes >= 1024 ** 4:
        return f"{num_bytes / 1024 ** 4:.2f} TB"
    if num_bytes >= 1024 ** 3:
        return f"{num_bytes / 1024 ** 3:.2f} GB"
    if num_bytes >= 1024 ** 2:
        return f"{num_bytes / 1024 ** 2:.2f} MB"
    if num_bytes >= 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes} B"


def size_bar(used, total):
    if total <= 0:
        return ""
    filled = int(BAR_LEN * used / total)
    filled = max(0, min(BAR_LEN, filled))
    return BAR_FULL * filled + BAR_EMPTY * (BAR_LEN - filled)


class DiskUsageWindow:
    def __init__(self, parent):
        self.parent = parent
        self.win = tk.Toplevel(parent)
        self.win.title("Disk Usage - What is using my space?")
        self.win.geometry("920x620")
        self.win.configure(bg=BG)
        self.win.transient(parent)

        self.q = queue.Queue()
        self.cancelled = False
        self.scanning = False
        self.path_cache = {}        # path -> list of item dicts
        self.history = []           # stack of paths
        self.current_items = {}     # name -> info for current view
        self.total_size = 0
        self.drives = []

        self._build_ui()
        self._style_tree()
        self.win.after(80, self._poll_queue)
        self._refresh_drives()
        if self.drives:
            self.drive_var.set(self.drives[0])
            self._scan(self.drives[0])

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #
    def _build_ui(self):
        top = tk.Frame(self.win, bg=BG)
        top.pack(fill="x", padx=14, pady=(12, 6))

        tk.Label(top, text="Drive:", font=("Segoe UI", 9), fg=MUTED, bg=BG).pack(side="left")
        self.drive_var = tk.StringVar()
        self.drive_combo = ttk.Combobox(
            top, textvariable=self.drive_var, state="readonly", width=18, font=("Segoe UI", 9)
        )
        self.drive_combo.pack(side="left", padx=(6, 12))
        self.drive_combo.bind("<<ComboboxSelected>>", lambda e: self._scan(self.drive_var.get()))

        self.btn_rescan = tk.Button(
            top, text="Rescan", command=self._rescan, bg=PANEL, fg=FG,
            activebackground="#334155", activeforeground=FG, relief="flat",
            font=("Segoe UI", 9), width=8,
        )
        self.btn_rescan.pack(side="left", padx=(0, 12))

        self.btn_cancel = tk.Button(
            top, text="Cancel", command=self._do_cancel, bg="#7f1d1d", fg=FG,
            activebackground="#991b1b", activeforeground=FG, relief="flat",
            font=("Segoe UI", 9), width=8, state="disabled",
        )
        self.btn_cancel.pack(side="left")

        self.space_label = tk.Label(
            top, text="", font=("Segoe UI", 9), fg=FG, bg=BG, anchor="e",
        )
        self.space_label.pack(side="right")

        self.breadcrumb = tk.Label(
            self.win, text="", font=("Segoe UI", 9, "bold"), fg="#818cf8",
            bg=BG, anchor="w",
        )
        self.breadcrumb.pack(fill="x", padx=14, pady=(0, 6))

        cols = ("name", "size", "pct", "bar")
        self.tree = ttk.Treeview(
            self.win, columns=cols, show="headings", selectmode="browse",
        )
        self.tree.heading("name", text="Name")
        self.tree.heading("size", text="Size")
        self.tree.heading("pct", text="% of parent")
        self.tree.heading("bar", text="Usage")
        self.tree.column("name", width=340, anchor="w")
        self.tree.column("size", width=100, anchor="e")
        self.tree.column("pct", width=80, anchor="e")
        self.tree.column("bar", width=130, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=14, pady=(0, 6))

        self.menu = tk.Menu(self.win, tearoff=0, bg=PANEL, fg=FG)
        self.menu.add_command(label="Open in Explorer", command=self._open_in_explorer)
        self.menu.add_command(label="Copy path", command=self._copy_path)
        self.tree.bind("<Button-3>", self._on_right_click)
        self.tree.bind("<Double-1>", self._on_double_click)

        btns = tk.Frame(self.win, bg=BG)
        btns.pack(pady=(0, 12))
        tk.Button(
            btns, text="Back", command=self._go_back, bg=PANEL, fg=FG,
            activebackground="#334155", activeforeground=FG, relief="flat",
            font=("Segoe UI", 9), width=10,
        ).pack(side="left", padx=4)
        tk.Button(
            btns, text="Close", command=self.win.destroy, bg=BORDER, fg=FG,
            activebackground="#475569", activeforeground=FG, relief="flat",
            font=("Segoe UI", 9), width=10,
        ).pack(side="left", padx=4)

        self.status = tk.Label(
            self.win, text="", font=("Segoe UI", 9), fg=MUTED, bg=BG, anchor="w",
        )
        self.status.pack(fill="x", padx=14, pady=(0, 4))

    def _style_tree(self):
        style = ttk.Style(self.win)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Disk.Treeview", background=LOG_BG, fieldbackground=LOG_BG,
            foreground=FG, rowheight=22, borderwidth=0,
        )
        style.configure(
            "Disk.Treeview.Heading", background=PANEL, foreground=FG, relief="flat",
        )
        self.tree.configure(style="Disk.Treeview")

    # ------------------------------------------------------------------ #
    # Drive discovery
    # ------------------------------------------------------------------ #
    def _refresh_drives(self):
        self.drives = []
        if winreg:
            try:
                ps = [
                    "powershell", "-NoProfile", "-Command",
                    "Get-Volume | Where-Object { $_.DriveType -eq 3 } | "
                    "Select-Object -ExpandProperty DriveLetter",
                ]
                out = subprocess.check_output(
                    ps, stderr=subprocess.STDOUT, text=True, timeout=10,
                )
                for line in out.splitlines():
                    line = line.strip()
                    if line and len(line) == 1:
                        self.drives.append(f"{line}:\\")
            except Exception:
                pass
        if not self.drives:
            self.drives = ["C:\\"]
        self.drive_combo["values"] = self.drives

    # ------------------------------------------------------------------ #
    # Scanning
    # ------------------------------------------------------------------ #
    def _scan(self, path):
        self.cancelled = False
        self.scanning = True
        self.history = [path]
        self.path_cache = {}
        self.current_items = {}
        self.total_size = 0
        self.tree.delete(*self.tree.get_children())
        self.breadcrumb.config(text=path)
        self.btn_cancel.config(state="normal")
        self.status.config(text="Scanning...")
        threading.Thread(target=self._scan_worker, args=(path,), daemon=True).start()

    def _rescan(self):
        self._scan(self.drive_var.get())

    def _do_cancel(self):
        self.cancelled = True
        self.status.config(text="Cancelling...")

    def _scan_worker(self, root_path):
        try:
            total, used, free = shutil.disk_usage(root_path)
            self.q.put(("space", total, used, free))
            items = self._scan_dir(root_path)
            if not self.cancelled:
                self.q.put(("done", root_path, items))
        except Exception as exc:  # noqa: BLE001
            self.q.put(("error", str(exc)))

    def _scan_dir(self, path):
        results = {}
        try:
            entries = list(os.scandir(path))
        except OSError:
            return results
        for entry in entries:
            if self.cancelled:
                break
            try:
                if entry.is_symlink() or entry.is_junction():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    size = self._dir_size(entry.path)
                    self.path_cache[entry.path] = size
                    self.total_size += size
                    results[entry.name] = {
                        "path": entry.path, "size": size, "is_dir": True,
                    }
                else:
                    try:
                        size = entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        size = 0
                    self.total_size += size
                    results[entry.name] = {
                        "path": entry.path, "size": size, "is_dir": False,
                    }
            except OSError:
                continue
        return results

    def _dir_size(self, path):
        total = 0
        try:
            for entry in os.scandir(path):
                if self.cancelled:
                    break
                try:
                    if entry.is_symlink() or entry.is_junction():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        total += self._dir_size(entry.path)
                    else:
                        try:
                            total += entry.stat(follow_symlinks=False).st_size
                        except OSError:
                            pass
                except OSError:
                    continue
        except OSError:
            pass
        return total

    # ------------------------------------------------------------------ #
    # Queue polling (main thread only)
    # ------------------------------------------------------------------ #
    def _poll_queue(self):
        try:
            while True:
                item = self.q.get_nowait()
                if item[0] == "space":
                    _, total, used, free = item
                    self.space_label.config(
                        text=(
                            f"Total: {format_size(total)}  "
                            f"Used: {format_size(used)}  "
                            f"Free: {format_size(free)}"
                        )
                    )
                elif item[0] == "done":
                    _, path, items = item
                    self.current_items = items
                    self.path_cache[path] = items
                    self._show_results(path, items)
                    self.scanning = False
                    self.btn_cancel.config(state="disabled")
                elif item[0] == "error":
                    self.status.config(text=f"Error: {item[1]}")
                    self.scanning = False
                    self.btn_cancel.config(state="disabled")
        except queue.Empty:
            pass
        self.win.after(80, self._poll_queue)

    def _show_results(self, path, items):
        if not items:
            self.status.config(text="No items found.")
            return
        sorted_items = sorted(items.values(), key=lambda x: x["size"], reverse=True)[:25]
        parent_total = sum(i["size"] for i in sorted_items) or self.total_size or 1
        for info in sorted_items:
            pct = (info["size"] / parent_total * 100) if parent_total > 0 else 0
            bar = size_bar(info["size"], parent_total)
            self.tree.insert(
                "", "end",
                values=(info["name"], format_size(info["size"]), f"{pct:.1f}%", bar),
            )
        self.status.config(text=f"{len(sorted_items)} items shown (top 25 by size)")

    # ------------------------------------------------------------------ #
    # Navigation
    # ------------------------------------------------------------------ #
    def _on_double_click(self, event):
        sel = self.tree.selection()
        if not sel or self.scanning:
            return
        item = self.tree.item(sel[0])
        name = item["values"][0]
        info = self.current_items.get(name)
        if not info or not info["is_dir"]:
            return
        path = info["path"]
        if path in self.path_cache:
            # Already scanned this path in this session — instant restore
            self.history.append(path)
            self._restore_view(path)
        else:
            self.history.append(path)
            self._scan(path)

    def _restore_view(self, path):
        items = self.path_cache.get(path, {})
        self.current_items = items
        self.tree.delete(*self.tree.get_children())
        self.breadcrumb.config(text=path)
        self.total_size = sum(i["size"] for i in items.values()) or 0
        sorted_items = sorted(items.values(), key=lambda x: x["size"], reverse=True)[:25]
        parent_total = self.total_size or 1
        for info in sorted_items:
            pct = (info["size"] / parent_total * 100) if parent_total > 0 else 0
            bar = size_bar(info["size"], parent_total)
            self.tree.insert(
                "", "end",
                values=(info["name"], format_size(info["size"]), f"{pct:.1f}%", bar),
            )
        self.status.config(text=f"{len(sorted_items)} items shown (cached)")

    def _go_back(self):
        if self.scanning or len(self.history) <= 1:
            return
        self.history.pop()
        path = self.history[-1]
        self._restore_view(path)

    # ------------------------------------------------------------------ #
    # Right-click menu (read-only)
    # ------------------------------------------------------------------ #
    def _on_right_click(self, event):
        row = self.tree.identify_row(event.y)
        if not row:
            return
        self.tree.selection_set(row)
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def _selected_path(self):
        sel = self.tree.selection()
        if not sel:
            return None
        item = self.tree.item(sel[0])
        name = item["values"][0]
        info = self.current_items.get(name)
        return info["path"] if info else None

    def _open_in_explorer(self):
        path = self._selected_path()
        if not path:
            return
        try:
            if os.path.isdir(path):
                subprocess.Popen(["explorer", path], creationflags=0x08000000)
            else:
                subprocess.Popen(["explorer", "/select,", path], creationflags=0x08000000)
        except Exception:  # noqa: BLE001
            pass

    def _copy_path(self):
        path = self._selected_path()
        if not path:
            return
        self.win.clipboard_clear()
        self.win.clipboard_append(path)
