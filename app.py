import ctypes
import os
import sys
import subprocess
import threading
import queue
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext

# DPI awareness at startup
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# Resolve base directory (supports PyInstaller _MEIPASS)
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CLEANUP_SCRIPT = os.path.join(BASE_DIR, "cleanup.ps1")
SPEEDUP_SCRIPT = os.path.join(BASE_DIR, "speedup.ps1")
RESTORE_SCRIPT = os.path.join(BASE_DIR, "restore-defaults.ps1")

APP_TITLE = "CleanUp-Pc - Windows Optimizer"


def detect_windows_version():
    """Detect Windows using sys.getwindowsversion() and registry ProductName."""
    build = 0
    product_type = 1
    caption = "Windows"
    try:
        ver = sys.getwindowsversion()
        build = getattr(ver, "build", 0)
        product_type = getattr(ver, "product_type", 1)
    except Exception:
        pass
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
        caption, _ = winreg.QueryValueEx(key, "ProductName")
        winreg.CloseKey(key)
    except Exception:
        pass
    is_server = product_type != 1
    edition = "Server" if is_server else "Desktop"
    if build >= 22000 and "11" not in caption:
        caption = "Windows 11"
    elif build < 22000 and "11" in caption:
        caption = "Windows 10"
    return caption, str(build), edition, is_server


class OptimizerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("920x800")
        self.configure(bg="#0f172a")

        self.caption, self.build, self.edition, self.is_server = detect_windows_version()

        self.log_queue = queue.Queue()
        self.current_proc = None
        self.is_running = False
        self.cancel_requested = False
        self.vars = {}
        self.startup_items = []

        self._build_ui()
        self._log(f"Detected: {self.caption}  (Build {self.build})  -  {self.edition}", "cmd")
        if self.is_server:
            self._log("Server detected: client-only tweaks are skipped automatically.", "warn")
        self._poll_queue()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- UI construction ----------
    def _build_ui(self):
        pad = 14
        header = tk.Frame(self, bg="#0f172a")
        header.pack(fill="x", padx=pad, pady=(14, 6))
        tk.Label(header, text=APP_TITLE, font=("Segoe UI", 15, "bold"),
                 fg="#f8fafc", bg="#0f172a").pack(anchor="w")
        self.version_label = tk.Label(header, text=f"{self.caption}  |  Build {self.build}  |  {self.edition}",
                                      font=("Segoe UI", 10), fg="#94a3b8", bg="#0f172a")
        self.version_label.pack(anchor="w", pady=(2, 0))

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=False, padx=pad, pady=(10, 6))

        clean_tab = tk.Frame(nb, bg="#0f172a")
        nb.add(clean_tab, text="Cleanup Options")
        self._build_cleanup_tab(clean_tab)

        speed_tab = tk.Frame(nb, bg="#0f172a")
        nb.add(speed_tab, text="Speed Up Options")
        self._build_speedup_tab(speed_tab)

        start_tab = tk.Frame(nb, bg="#0f172a")
        nb.add(start_tab, text="Startup Programs")
        self._build_startup_tab(start_tab)

        btn_frame = tk.Frame(self, bg="#0f172a")
        btn_frame.pack(fill="x", padx=pad, pady=(8, 4))

        self.btn_cleanup = tk.Button(btn_frame, text="Cleanup My OS",
                                     font=("Segoe UI", 11, "bold"), bg="#1e293b", fg="#f8fafc",
                                     activebackground="#334155", activeforeground="#ffffff",
                                     relief="flat", cursor="hand2", command=self._do_cleanup,
                                     width=18, height=2)
        self.btn_cleanup.pack(side="left", padx=(0, 6), fill="x", expand=True)

        self.btn_speedup = tk.Button(btn_frame, text="Speed Up My OS",
                                     font=("Segoe UI", 11, "bold"), bg="#1e293b", fg="#f8fafc",
                                     activebackground="#334155", activeforeground="#ffffff",
                                     relief="flat", cursor="hand2", command=self._do_speedup,
                                     width=18, height=2)
        self.btn_speedup.pack(side="left", padx=(6, 0), fill="x", expand=True)

        btn_frame2 = tk.Frame(self, bg="#0f172a")
        btn_frame2.pack(fill="x", padx=pad, pady=(4, 4))

        self.btn_auto = tk.Button(btn_frame2, text="Auto Optimize (Recommended)",
                                  font=("Segoe UI", 11, "bold"), bg="#0f766e", fg="#f8fafc",
                                  activebackground="#115e59", activeforeground="#ffffff",
                                  relief="flat", cursor="hand2", command=self._do_auto,
                                  width=26, height=2)
        self.btn_auto.pack(side="left", padx=(0, 6), fill="x", expand=True)

        self.btn_undo = tk.Button(btn_frame2, text="Undo Speed Up",
                                  font=("Segoe UI", 11, "bold"), bg="#334155", fg="#f8fafc",
                                  activebackground="#475569", activeforeground="#ffffff",
                                  relief="flat", cursor="hand2", command=self._do_undo,
                                  width=16, height=2)
        self.btn_undo.pack(side="left", padx=(6, 0), fill="x", expand=True)

        btn_frame3 = tk.Frame(self, bg="#0f172a")
        btn_frame3.pack(fill="x", padx=pad, pady=(4, 8))

        self.var_dryrun = tk.BooleanVar(value=False)
        self.chk_dryrun = tk.Checkbutton(btn_frame3, text="Scan only / dry run",
                                         variable=self.var_dryrun, bg="#0f172a", fg="#94a3b8",
                                         selectcolor="#1e293b", activebackground="#0f172a",
                                         activeforeground="#f8fafc", font=("Segoe UI", 9))
        self.chk_dryrun.pack(side="left")

        self.btn_cancel = tk.Button(btn_frame3, text="Cancel",
                                    font=("Segoe UI", 10), bg="#475569", fg="#f8fafc",
                                    activebackground="#64748b", activeforeground="#ffffff",
                                    relief="flat", command=self._do_cancel, state="disabled",
                                    width=10)
        self.btn_cancel.pack(side="right", padx=(6, 0))

        self.btn_save = tk.Button(btn_frame3, text="Save log to file",
                                  font=("Segoe UI", 10), bg="#334155", fg="#f8fafc",
                                  activebackground="#475569", activeforeground="#ffffff",
                                  relief="flat", command=self._do_save_log, width=16)
        self.btn_save.pack(side="right")

        self.progress = ttk.Progressbar(self, mode="indeterminate")
        self.progress.pack(fill="x", padx=pad, pady=(0, 6))

        log_frame = tk.Frame(self, bg="#0f172a")
        log_frame.pack(fill="both", expand=True, padx=pad, pady=(0, 12))
        tk.Label(log_frame, text="Output / Log:", font=("Segoe UI", 9, "bold"),
                 fg="#cbd5e1", bg="#0f172a").pack(anchor="w")
        self.log = scrolledtext.ScrolledText(log_frame, font=("Consolas", 10),
                                             bg="#020617", fg="#e2e8f0",
                                             insertbackground="#f8fafc", relief="flat",
                                             padx=8, pady=8)
        self.log.pack(fill="both", expand=True)

    def _chk(self, parent, text, key, default=False):
        var = tk.BooleanVar(value=default)
        self.vars[key] = var
        chk = tk.Checkbutton(parent, text=text, variable=var, bg="#0f172a", fg="#cbd5e1",
                             selectcolor="#1e293b", activebackground="#0f172a",
                             activeforeground="#f8fafc", font=("Segoe UI", 9))
        chk.pack(anchor="w", pady=1)
        return chk

    def _build_cleanup_tab(self, parent):
        container = tk.Frame(parent, bg="#0f172a")
        container.pack(fill="both", expand=True, padx=8, pady=8)
        left = tk.Frame(container, bg="#0f172a")
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        right = tk.Frame(container, bg="#0f172a")
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))

        tk.Label(left, text="Standard cleanup (ON by default):", font=("Segoe UI", 9, "bold"),
                 fg="#f8fafc", bg="#0f172a").pack(anchor="w", pady=(0, 4))
        self._chk(left, "User Temp", "clean_temp", True)
        self._chk(left, "Windows Temp", "clean_windows_temp", True)
        self._chk(left, "Windows Update cache", "clean_update_cache", True)
        self._chk(left, "Delivery Optimization", "clean_delivery_opt", True)
        self._chk(left, "DNS cache", "clean_dns", True)
        self._chk(left, "Icon cache", "clean_icon_cache", True)
        self._chk(left, "Thumbnail cache", "clean_thumbnail_cache", True)
        self._chk(left, "Crash logs (WER)", "clean_crash_logs", True)
        self._chk(left, "Recycle Bin", "clean_recycle_bin", True)

        tk.Label(right, text="Optional cleanup (OFF by default):", font=("Segoe UI", 9, "bold"),
                 fg="#f8fafc", bg="#0f172a").pack(anchor="w", pady=(0, 4))
        self._chk(right, "Prefetch", "clean_prefetch", False)
        self._chk(right, "Disable hibernation", "disable_hibernate", False)
        self._chk(right, "Compact OS (compact.exe)", "compact_os", False)
        self._chk(right, "Chrome cache", "clean_chrome", False)
        self._chk(right, "Edge cache", "clean_edge", False)
        self._chk(right, "Firefox cache", "clean_firefox", False)
        self._chk(right, "Windows.old", "clean_windows_old", False)
        self._chk(right, ".chk files", "clean_chk", False)
        self._chk(right, "Old Event Logs", "clean_event_logs", False)

    def _build_speedup_tab(self, parent):
        container = tk.Frame(parent, bg="#0f172a")
        container.pack(fill="both", expand=True, padx=8, pady=8)
        tk.Label(container, text="Speed up options:", font=("Segoe UI", 9, "bold"),
                 fg="#f8fafc", bg="#0f172a").pack(anchor="w", pady=(0, 4))
        self._chk(container, "Keep Windows Search indexing", "keep_search", True)
        self._chk(container, "Keep SysMain / Superfetch", "keep_sysmain", True)
        self._chk(container, "Disable Xbox services", "disable_xbox", False)
        self._chk(container, "Disable telemetry", "disable_telemetry", True)
        tk.Label(container, text="Note: Explorer restart and hibernation are disabled "
                                 "in GUI mode (run separately if needed).",
                 font=("Segoe UI", 8), fg="#64748b", bg="#0f172a").pack(anchor="w", pady=(8, 0))

    def _build_startup_tab(self, parent):
        top = tk.Frame(parent, bg="#0f172a")
        top.pack(fill="x", padx=8, pady=(6, 4))
        tk.Label(top, text="Startup programs:", font=("Segoe UI", 9, "bold"),
                 fg="#f8fafc", bg="#0f172a").pack(side="left")
        self.btn_refresh_startup = tk.Button(top, text="Refresh",
                                             font=("Segoe UI", 9), bg="#1e293b", fg="#f8fafc",
                                             activebackground="#334155", relief="flat",
                                             command=self._refresh_startup)
        self.btn_refresh_startup.pack(side="right")
        self.btn_disable_startup = tk.Button(top, text="Disable Selected",
                                             font=("Segoe UI", 9), bg="#334155", fg="#f8fafc",
                                             activebackground="#475569", relief="flat",
                                             command=self._disable_selected_startup, state="disabled")
        self.btn_disable_startup.pack(side="right", padx=(0, 6))

        list_frame = tk.Frame(parent, bg="#0f172a")
        list_frame.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        canvas = tk.Canvas(list_frame, bg="#020617", highlightthickness=0, height=180)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        self.startup_inner = tk.Frame(canvas, bg="#020617")
        self.startup_inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.startup_inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.startup_items = []
        self._refresh_startup()

    # ---------- Thread-safe logging ----------
    def _poll_queue(self):
        try:
            while True:
                item = self.log_queue.get_nowait()
                self._write_log(item["text"], item.get("level", "info"))
        except queue.Empty:
            pass
        self.after(80, self._poll_queue)

    def _log(self, text, level="info"):
        self.log_queue.put({"text": text, "level": level})

    def _write_log(self, text, level="info"):
        colors = {"info": "#e2e8f0", "ok": "#4ade80", "warn": "#fbbf24",
                  "error": "#f87171", "cmd": "#818cf8", "dryrun": "#fbbf24"}
        start = self.log.index("end-1c")
        self.log.insert("end", text + "\n")
        end = self.log.index("end-1c")
        self.log.tag_add(level, start, end)
        self.log.tag_config(level, foreground=colors.get(level, "#e2e8f0"))
        self.log.see("end")

    # ---------- Button states ----------
    def _set_buttons(self, running):
        self.is_running = running
        state = "disabled" if running else "normal"
        self.btn_cleanup.config(state=state)
        self.btn_speedup.config(state=state)
        self.btn_auto.config(state=state)
        self.btn_undo.config(state=state)
        self.btn_refresh_startup.config(state=state)
        self.btn_disable_startup.config(state=state)
        self.chk_dryrun.config(state=state)
        self.btn_cancel.config(state="normal" if running else "disabled")
        if running:
            self.progress.start(10)
        else:
            self.progress.stop()
            self.cancel_requested = False

    # ---------- Startup programs ----------
    def _refresh_startup(self):
        for w in self.startup_inner.winfo_children():
            w.destroy()
        self.startup_items = []
        try:
            ps = ["powershell", "-NoProfile", "-Command",
                  "Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run', "
                  "'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run' -ErrorAction SilentlyContinue | "
                  "ForEach-Object { $_.PsObject.Properties | ForEach-Object { \"$($_.Name)|$($_.Value)|Reg\" } }; "
                  "Get-ChildItem \"$env:AppData\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\" -ErrorAction SilentlyContinue | "
                  "ForEach-Object { \"$($_.BaseName)|$($_.FullName)|StartupFolder\" }; "
                  "Get-ChildItem \"$env:ProgramData\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\" -ErrorAction SilentlyContinue | "
                  "ForEach-Object { \"$($_.BaseName)|$($_.FullName)|StartupFolder\" }"]
            out = subprocess.check_output(ps, stderr=subprocess.STDOUT, text=True, timeout=15,
                                          creationflags=subprocess.CREATE_NO_WINDOW)
            for line in out.splitlines():
                line = line.strip()
                if not line or "|" not in line:
                    continue
                parts = line.split("|", 2)
                if len(parts) < 3:
                    continue
                name, path, location = parts
                var = tk.BooleanVar(value=False)
                row = tk.Frame(self.startup_inner, bg="#020617")
                row.pack(fill="x", pady=1)
                chk = tk.Checkbutton(row, variable=var, bg="#020617", selectcolor="#1e293b",
                                     activebackground="#020617")
                chk.pack(side="left")
                tk.Label(row, text=f"{name}  [{location}]", fg="#e2e8f0", bg="#020617",
                         font=("Segoe UI", 9), anchor="w").pack(side="left", padx=(6, 0), fill="x", expand=True)
                tk.Label(row, text=path, fg="#64748b", bg="#020617",
                         font=("Segoe UI", 8), anchor="w").pack(side="left", padx=(6, 0))
                self.startup_items.append((var, name, path, location))
            if self.startup_items:
                self.btn_disable_startup.config(state="normal")
        except Exception as exc:
            self._log(f"Could not enumerate startup programs: {exc}", "error")

    def _disable_selected_startup(self):
        selected = [(n, p, l) for v, n, p, l in self.startup_items if v.get()]
        if not selected:
            messagebox.showinfo("No selection", "Select startup programs to disable first.")
            return
        # Build PowerShell to remove registry Run values and delete startup folder shortcuts
        cmds = []
        for name, path, location in selected:
            if location == "Reg":
                # Try HKCU then HKLM
                cmds.append(f"Remove-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run' -Name '{name}' -ErrorAction SilentlyContinue")
                cmds.append(f"Remove-ItemProperty 'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run' -Name '{name}' -ErrorAction SilentlyContinue")
            else:
                cmds.append(f"Remove-Item '{path}' -Recurse -Force -ErrorAction SilentlyContinue")
        ps_cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "; ".join(cmds)]
        try:
            subprocess.run(ps_cmd, check=False, creationflags=subprocess.CREATE_NO_WINDOW,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._log(f"Disabled {len(selected)} startup program(s).", "ok")
            self._refresh_startup()
        except Exception as exc:
            self._log(f"Failed to disable startup programs: {exc}", "error")

    # ---------- Parameter building ----------
    def _build_cleanup_params(self):
        v = self.vars
        params = ["-NoPause"]
        if self.var_dryrun.get():
            params.append("-DryRun")
        bool_params = {
            "clean_temp": "CleanTemp",
            "clean_windows_temp": "CleanWindowsTemp",
            "clean_prefetch": "CleanPrefetch",
            "clean_update_cache": "CleanUpdateCache",
            "clean_delivery_opt": "CleanDeliveryOpt",
            "clean_dns": "CleanDns",
            "clean_icon_cache": "CleanIconCache",
            "clean_thumbnail_cache": "CleanThumbnailCache",
            "clean_crash_logs": "CleanCrashLogs",
            "clean_recycle_bin": "CleanRecycleBin",
            "disable_hibernate": "DisableHibernate",
            "compact_os": "CompactOS",
            "clean_chrome": "CleanChromeCache",
            "clean_edge": "CleanEdgeCache",
            "clean_firefox": "CleanFirefoxCache",
            "clean_windows_old": "CleanWindowsOld",
            "clean_chk": "CleanChkFiles",
            "clean_event_logs": "CleanEventLogs",
        }
        for key, ps_name in bool_params.items():
            val = "$true" if v.get(key, tk.BooleanVar(value=False)).get() else "$false"
            params.append(f"-{ps_name}:{val}")
        return params

    def _build_speedup_params(self):
        v = self.vars
        params = ["-NoPause"]
        if self.var_dryrun.get():
            params.append("-DryRun")
        bool_params = {
            "keep_search": "KeepSearchIndexing",
            "keep_sysmain": "KeepSysMain",
            "disable_xbox": "DisableXboxServices",
            "disable_telemetry": "DisableTelemetry",
        }
        for key, ps_name in bool_params.items():
            val = "$true" if v.get(key, tk.BooleanVar(value=False)).get() else "$false"
            params.append(f"-{ps_name}:{val}")
        return params

    # ---------- Actions ----------
    def _do_cleanup(self):
        self._run_action("cleanup")

    def _do_speedup(self):
        self._run_action("speedup")

    def _do_auto(self):
        self._run_action("auto")

    def _do_undo(self):
        self._run_action("undo")

    def _run_action(self, action):
        if self.is_running:
            return
        if action == "undo":
            if not messagebox.askyesno("Undo Speed Up",
                                       "Revert Speed Up changes (services, tasks, registry, power plan)?\n\nContinue?"):
                return
            script = RESTORE_SCRIPT
            params = []
            label = "Undo Speed Up"
        elif action == "cleanup":
            script = CLEANUP_SCRIPT
            params = self._build_cleanup_params()
            label = "Cleanup"
        elif action == "speedup":
            script = SPEEDUP_SCRIPT
            params = self._build_speedup_params()
            label = "Speed up"
        elif action == "auto":
            if self.is_server:
                script = CLEANUP_SCRIPT
                params = self._build_cleanup_params()
                label = "Auto Optimize (Cleanup only - Server)"
                self._start_script(script, params, label)
                return
            else:
                self._run_sequence([
                    ("cleanup", CLEANUP_SCRIPT, self._build_cleanup_params(), "Cleanup"),
                    ("speedup", SPEEDUP_SCRIPT, self._build_speedup_params(), "Speed up"),
                ])
                return
        else:
            return
        self._start_script(script, params, label)

    def _run_sequence(self, steps):
        if not steps:
            self._set_buttons(False)
            return
        step = steps[0]
        rest = steps[1:]
        name, script, params, label = step
        if not messagebox.askyesno(f"Auto Optimize - {label}",
                                   f"Step {len(steps) - len(rest)} of {len(steps)}: {label}\n\nContinue?"):
            self._log("Auto Optimize cancelled by user.", "warn")
            self._set_buttons(False)
            return
        self._start_script(script, params, label, chained=rest)

    def _start_script(self, script, params, label, chained=None):
        if not os.path.exists(script):
            messagebox.showerror("Missing script", f"Not found: {script}")
            self._set_buttons(False)
            return
        self._set_buttons(True)
        self.log.delete("1.0", "end")
        self.cancel_requested = False
        dry = self.var_dryrun.get()
        self._log(f"> powershell -NoProfile -ExecutionPolicy Bypass -File {os.path.basename(script)} {' '.join(params)}", "cmd")
        t = threading.Thread(target=self._worker, args=(script, params, label, chained, dry), daemon=True)
        t.start()

    def _worker(self, script, params, label, chained, dry):
        try:
            cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                   "-File", script] + params
            if dry:
                cmd.insert(3, "-DryRun")  # -NoPause already in params; add -DryRun if not present
                if "-DryRun" not in cmd:
                    cmd.append("-DryRun")
            proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    encoding="utf-8", errors="replace",
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            self.current_proc = proc
            for line in iter(proc.stdout.readline, ""):
                if self.cancel_requested:
                    break
                if not line:
                    break
                line = line.rstrip("\n")
                if not line:
                    continue
                level = "info"
                if "Freed" in line and "GB" in line:
                    level = "ok"
                elif "Finished Successfully" in line or "completed successfully" in line.lower():
                    level = "ok"
                elif "skip" in line.lower() or "Detected:" in line or "DRYRUN" in line:
                    level = "warn"
                elif "Error" in line or "error" in line or "Failed" in line or "failed" in line:
                    level = "error"
                self._log(line, level=level)
            proc.wait()
            if self.cancel_requested:
                self._log(f"{label} cancelled.", "warn")
            elif proc.returncode == 0:
                self._log(f"{label} completed successfully.", "ok")
            else:
                self._log(f"{label} finished with exit code {proc.returncode}.", "error")
        except Exception as exc:
            self._log(f"Error during {label}: {exc}", "error")
        finally:
            self.current_proc = None
            self.after(0, lambda: self._worker_finished(chained))

    def _worker_finished(self, chained):
        if chained:
            self._run_sequence(chained)
        else:
            self._set_buttons(False)
            self._log("Operation finished.", "ok")

    def _do_cancel(self):
        self.cancel_requested = True
        if self.current_proc:
            try:
                pid = self.current_proc.pid
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            except Exception:
                pass
        self._log("Cancel requested...", "warn")

    def _do_save_log(self):
        content = self.log.get("1.0", "end").strip()
        if not content:
            messagebox.showinfo("Empty log", "Nothing to save.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt",
                                            filetypes=[("Text files", "*.txt")],
                                            title="Save log to file")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                self._log(f"Log saved to {path}", "ok")
            except Exception as exc:
                self._log(f"Failed to save log: {exc}", "error")

    def _on_close(self):
        if self.is_running:
            if not messagebox.askyesno("Confirm close",
                                       "An operation is still running. Close anyway?\n"
                                       "The background process will be cancelled."):
                return
            self._do_cancel()
        self.destroy()


def main():
    app = OptimizerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
