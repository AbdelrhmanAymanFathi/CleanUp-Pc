import ctypes
import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

APP_TITLE = "CleanUp-Pc - Windows Optimizer"

# Generic fallback scripts
CLEANUP_SCRIPT = os.path.join(BASE_DIR, "cleanup.ps1")
SPEEDUP_SCRIPT = os.path.join(BASE_DIR, "speedup.ps1")


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def elevate():
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{os.path.abspath(__file__)}"', None, 1
        )
        sys.exit(0)


def detect_windows_version():
    """Detect Windows caption, build, edition (Desktop/Server) and is_server flag."""
    caption = ""
    build = ""
    is_server = False

    try:
        ps = (
            "powershell -NoProfile -Command "
            "'$o=Get-CimInstance Win32_OperatingSystem; "
            "$o.Caption + \"|\" + $o.Version + \"|\" + $o.BuildNumber + \"|\" + "
            "[string]::Format(\"{0}\",$o.ProductType)'"
        )
        out = subprocess.check_output(
            ps, shell=True, stderr=subprocess.STDOUT, text=True, timeout=15
        )
        parts = out.strip().split("|")
        if len(parts) >= 4:
            caption = parts[0].strip()
            build = parts[2].strip()
            product_type = parts[3].strip()
            is_server = product_type != "1"
    except Exception:
        pass

    if not caption:
        try:
            ver = sys.getwindowsversion()
            build = str(ver.build)
            if int(build) >= 22000:
                caption = "Windows 11"
            else:
                caption = "Windows 10"
            is_server = False
        except Exception:
            caption = "Windows"
            build = ""
            is_server = False

    edition = "Server" if is_server else "Desktop"
    return caption, build, edition, is_server


def pick_script(base_name):
    """Pick a version-specific script if it exists, else fall back to generic.

    Precedence:
      1. <base>-<caption-slug>-<edition>.ps1   (e.g. cleanup-windows-11-desktop.ps1)
      2. <base>-<edition>.ps1                  (e.g. cleanup-server.ps1)
      3. <base>-<caption-slug>.ps1             (e.g. cleanup-windows-11.ps1)
      4. <base>.ps1                            (generic fallback)
    """
    name_slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in caption_var.get("caption", "windows")).strip("-")
    edition_slug = "server" if caption_var.get("is_server") else "desktop"

    candidates = [
        os.path.join(BASE_DIR, f"{base_name}-{name_slug}-{edition_slug}.ps1"),
        os.path.join(BASE_DIR, f"{base_name}-{edition_slug}.ps1"),
        os.path.join(BASE_DIR, f"{base_name}-{name_slug}.ps1"),
        os.path.join(BASE_DIR, f"{base_name}.ps1"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return os.path.join(BASE_DIR, f"{base_name}.ps1")


caption_var = {"caption": "windows", "is_server": False}


class OptimizerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("820x620")
        self.minsize(760, 560)
        self.configure(bg="#0f172a")

        self.caption, self.build, self.edition, self.is_server = detect_windows_version()
        caption_var["caption"] = self.caption
        caption_var["is_server"] = self.is_server

        self.cleanup_script = pick_script("cleanup")
        self.speedup_script = pick_script("speedup")

        self._build_ui()
        self._log(f"Detected: {self.caption}  (Build {self.build})  -  {self.edition}", level="cmd")
        self._show_recommendation()
        if self.is_server:
            self._log("Server detected: client-only tweaks are skipped automatically.", level="warn")
        self._log(f"Using cleanup script: {os.path.basename(self.cleanup_script)}", level="cmd")
        self._log(f"Using speedup script: {os.path.basename(self.speedup_script)}", level="cmd")

    def _build_ui(self):
        header = tk.Frame(self, bg="#0f172a")
        header.pack(fill="x", padx=18, pady=(16, 8))

        tk.Label(
            header,
            text=APP_TITLE,
            font=("Segoe UI", 16, "bold"),
            fg="#f8fafc",
            bg="#0f172a",
        ).pack(anchor="w")

        self.version_label = tk.Label(
            header,
            text=f"{self.caption}  |  Build {self.build}  |  {self.edition}",
            font=("Segoe UI", 10),
            fg="#94a3b8",
            bg="#0f172a",
        )
        self.version_label.pack(anchor="w", pady=(2, 0))

        # Recommendation banner
        self.rec_frame = tk.Frame(self, bg="#1e293b", highlightbackground="#334155", highlightthickness=1)
        self.rec_frame.pack(fill="x", padx=18, pady=(10, 8))

        self.rec_icon = tk.Label(
            self.rec_frame, text="", font=("Segoe UI", 12), fg="#fbbf24", bg="#1e293b"
        )
        self.rec_icon.pack(side="left", padx=(12, 8), pady=10)

        self.rec_text = tk.Label(
            self.rec_frame,
            text="",
            font=("Segoe UI", 10, "bold"),
            fg="#f8fafc",
            bg="#1e293b",
            justify="left",
        )
        self.rec_text.pack(side="left", padx=(0, 12), pady=10, fill="x", expand=True)

        # Main action buttons
        btn_frame = tk.Frame(self, bg="#0f172a")
        btn_frame.pack(fill="x", padx=18, pady=10)

        self.btn_cleanup = tk.Button(
            btn_frame,
            text="Cleanup My OS",
            font=("Segoe UI", 12, "bold"),
            bg="#1e293b",
            fg="#f8fafc",
            activebackground="#334155",
            activeforeground="#ffffff",
            relief="flat",
            cursor="hand2",
            command=lambda: self.run_action("cleanup"),
            width=20,
            height=2,
        )
        self.btn_cleanup.pack(side="left", padx=(0, 10), fill="x", expand=True)

        self.btn_speedup = tk.Button(
            btn_frame,
            text="Speed Up My OS",
            font=("Segoe UI", 12, "bold"),
            bg="#1e293b",
            fg="#f8fafc",
            activebackground="#334155",
            activeforeground="#ffffff",
            relief="flat",
            cursor="hand2",
            command=lambda: self.run_action("speedup"),
            width=20,
            height=2,
        )
        self.btn_speedup.pack(side="left", padx=(10, 0), fill="x", expand=True)

        # Auto optimize button
        auto_frame = tk.Frame(self, bg="#0f172a")
        auto_frame.pack(fill="x", padx=18, pady=(0, 10))

        self.btn_auto = tk.Button(
            auto_frame,
            text="Auto Optimize (Recommended)",
            font=("Segoe UI", 11, "bold"),
            bg="#0f766e",
            fg="#f8fafc",
            activebackground="#115e59",
            activeforeground="#ffffff",
            relief="flat",
            cursor="hand2",
            command=self.run_auto,
            width=30,
            height=2,
        )
        self.btn_auto.pack()

        info = tk.Frame(self, bg="#0f172a")
        info.pack(fill="x", padx=18, pady=(0, 8))

        tk.Label(
            info,
            text="Both actions require Administrator rights and will elevate automatically.",
            font=("Segoe UI", 9),
            fg="#64748b",
            bg="#0f172a",
        ).pack(anchor="w")

        out_frame = tk.Frame(self, bg="#0f172a")
        out_frame.pack(fill="both", expand=True, padx=18, pady=(0, 16))

        tk.Label(
            out_frame,
            text="Output / Log:",
            font=("Segoe UI", 9, "bold"),
            fg="#cbd5e1",
            bg="#0f172a",
        ).pack(anchor="w")

        self.log = scrolledtext.ScrolledText(
            out_frame,
            font=("Consolas", 10),
            bg="#020617",
            fg="#e2e8f0",
            insertbackground="#f8fafc",
            relief="flat",
            padx=8,
            pady=8,
        )
        self.log.pack(fill="both", expand=True)

        btn_close = tk.Button(
            self,
            text="Close",
            font=("Segoe UI", 10),
            bg="#334155",
            fg="#f8fafc",
            activebackground="#475569",
            activeforeground="#ffffff",
            relief="flat",
            command=self.destroy,
            width=12,
        )
        btn_close.pack(pady=(0, 12))

    def _show_recommendation(self):
        if self.is_server:
            self.rec_icon.config(text="\u26a0")
            self.rec_text.config(
                text="Server detected \u2014 Recommended: Cleanup My OS.\n"
                     "Speed Up runs in server-safe mode (client tweaks skipped)."
            )
            self.btn_auto.config(text="Auto Optimize (Cleanup only)")
        elif "11" in self.caption:
            self.rec_icon.config(text="\u2705")
            self.rec_text.config(
                text="Windows 11 detected \u2014 Recommended: Auto Optimize (Cleanup + Speed Up)."
            )
            self.btn_auto.config(text="Auto Optimize (Cleanup + Speed Up)")
        elif "10" in self.caption:
            self.rec_icon.config(text="\u2705")
            self.rec_text.config(
                text="Windows 10 detected \u2014 Recommended: Auto Optimize (Cleanup + Speed Up)."
            )
            self.btn_auto.config(text="Auto Optimize (Cleanup + Speed Up)")
        else:
            self.rec_icon.config(text="\u2139")
            self.rec_text.config(
                text=f"{self.caption} detected \u2014 choose an action below."
            )
            self.btn_auto.config(text="Auto Optimize")

    def _log(self, text, level="info"):
        colors = {
            "info": "#e2e8f0",
            "ok": "#4ade80",
            "warn": "#fbbf24",
            "error": "#f87171",
            "cmd": "#818cf8",
        }
        self.log.insert("end", text + "\n")
        last = f"end-{len(text)+1}c"
        self.log.tag_add(level, last, "end")
        self.log.tag_config(level, foreground=colors.get(level, "#e2e8f0"))
        self.log.see("end")
        self.update_idletasks()

    def _set_buttons(self, state):
        self.btn_cleanup.config(state=state)
        self.btn_speedup.config(state=state)
        self.btn_auto.config(state=state)

    def _confirm(self, title, message):
        return messagebox.askyesno(title, message)

    def run_action(self, action):
        if not is_admin():
            elevate()
            return

        script = self.cleanup_script if action == "cleanup" else self.speedup_script
        label = "Cleanup" if action == "cleanup" else "Speed up"

        if not os.path.exists(script):
            messagebox.showerror("Missing script", f"Could not find {os.path.basename(script)}")
            return

        if not self._confirm(
            f"{label} OS",
            f"This will {label.lower()} your Windows OS ({self.caption} {self.edition}).\n\n"
            "Make sure you have saved your work. A restart may be required after speed up.\n\nContinue?",
        ):
            return

        self._set_buttons("disabled")
        self.log.delete("1.0", "end")
        self._log(f"Starting {label} on {self.caption} {self.edition}...", level="cmd")
        self._log(f"Script: {os.path.basename(script)}", level="cmd")
        threading.Thread(
            target=self._run_script, args=(script, label), daemon=True
        ).start()

    def run_auto(self):
        if not is_admin():
            elevate()
            return

        if self.is_server:
            # Server: cleanup only
            self._run_sequence([("cleanup", self.cleanup_script, "Cleanup")])
        else:
            # Desktop: cleanup then speedup
            self._run_sequence(
                [
                    ("cleanup", self.cleanup_script, "Cleanup"),
                    ("speedup", self.speedup_script, "Speed up"),
                ]
            )

    def _run_sequence(self, steps):
        if not steps:
            self._set_buttons("normal")
            return

        action, script, label = steps[0]
        rest = steps[1:]

        if not os.path.exists(script):
            self._log(f"Missing script: {os.path.basename(script)}", level="error")
            if rest:
                self._run_sequence(rest)
            else:
                self._set_buttons("normal")
            return

        if not self._confirm(
            f"Auto Optimize - {label}",
            f"Step {len(steps) - len(rest)} of {len(steps)}: {label} on {self.caption} {self.edition}.\n\n"
            "Make sure you have saved your work. Continue?",
        ):
            self._log("Auto Optimize cancelled by user.", level="warn")
            self._set_buttons("normal")
            return

        self._set_buttons("disabled")
        self.log.delete("1.0", "end")
        self._log(f"Auto Optimize: {label} ({os.path.basename(script)})", level="cmd")
        threading.Thread(
            target=self._run_script_chained, args=(script, label, rest), daemon=True
        ).start()

    def _run_script_chained(self, script, label, rest):
        try:
            ps_cmd = f'powershell -NoProfile -ExecutionPolicy Bypass -File "{script}"'
            self._log(f"> {ps_cmd}", level="cmd")

            proc = subprocess.Popen(
                ps_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            for line in iter(proc.stdout.readline, ""):
                if not line:
                    break
                line = line.rstrip("\n")
                if not line:
                    continue
                level = "info"
                if "Finished Successfully" in line:
                    level = "ok"
                elif "skip" in line.lower() or "Detected:" in line:
                    level = "warn"
                elif "Error" in line or "error" in line or "Failed" in line:
                    level = "error"
                self._log(line, level=level)

            proc.wait()
            if proc.returncode == 0:
                self._log(f"{label} completed successfully.", level="ok")
            else:
                self._log(f"{label} finished with exit code {proc.returncode}.", level="error")

        except Exception as exc:
            self._log(f"Error during {label}: {exc}", level="error")
        finally:
            if rest:
                self._run_sequence(rest)
            else:
                self._set_buttons("normal")
                self._log("Auto Optimize finished.", level="ok")

    def _run_script(self, script, label):
        try:
            ps_cmd = f'powershell -NoProfile -ExecutionPolicy Bypass -File "{script}"'
            self._log(f"> {ps_cmd}", level="cmd")

            proc = subprocess.Popen(
                ps_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            for line in iter(proc.stdout.readline, ""):
                if not line:
                    break
                line = line.rstrip("\n")
                if not line:
                    continue
                level = "info"
                if "Finished Successfully" in line:
                    level = "ok"
                elif "skip" in line.lower() or "Detected:" in line:
                    level = "warn"
                elif "Error" in line or "error" in line or "Failed" in line:
                    level = "error"
                self._log(line, level=level)

            proc.wait()
            if proc.returncode == 0:
                self._log(f"{label} completed successfully.", level="ok")
            else:
                self._log(f"{label} finished with exit code {proc.returncode}.", level="error")
        except Exception as exc:
            self._log(f"Error: {exc}", level="error")
        finally:
            self._set_buttons("normal")


def main():
    if not is_admin():
        elevate()
        return

    app = OptimizerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
