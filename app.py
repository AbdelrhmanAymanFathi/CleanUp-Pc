import ctypes
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLEANUP_SCRIPT = os.path.join(BASE_DIR, "cleanup.ps1")
SPEEDUP_SCRIPT = os.path.join(BASE_DIR, "speedup.ps1")

APP_TITLE = "CleanUp-Pc - Windows Optimizer"


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
    caption = ""
    build = ""
    try:
        import subprocess
        ps = (
            "powershell -NoProfile -Command "
            "'$o=Get-CimInstance Win32_OperatingSystem; "
            "$o.Caption + \"|\" + $o.Version + \"|\" + $o.BuildNumber + \"|\" + "
            "[string]::Format(\"{0}\",$o.ProductType)'"
        )
        out = subprocess.check_output(ps, shell=True, stderr=subprocess.STDOUT, text=True, timeout=15)
        parts = out.strip().split("|")
        if len(parts) >= 4:
            caption = parts[0].strip()
            build = parts[2].strip()
            product_type = parts[3].strip()
            is_server = product_type != "1"
        else:
            is_server = False
    except Exception:
        caption = ""
        build = ""
        is_server = False

    if not caption:
        try:
            import platform
            import sys as _sys
            ver = _sys.getwindowsversion()
            rel = platform.release()
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


class OptimizerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("760x560")
        self.minsize(700, 500)
        self.configure(bg="#0f172a")

        self.caption, self.build, self.edition, self.is_server = detect_windows_version()

        self._build_ui()
        self._log(f"Detected: {self.caption} (Build {self.build}) - {self.edition}")
        if self.is_server:
            self._log("Server mode: client-only tweaks will be skipped automatically.", level="warn")

    def _build_ui(self):
        style = ttk.Style(self)
        style.theme_use("clam")

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

        btn_frame = tk.Frame(self, bg="#0f172a")
        btn_frame.pack(fill="x", padx=18, pady=18)

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
        self.btn_cleanup.pack(side="left", padx=(0, 12), fill="x", expand=True)

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
        self.btn_speedup.pack(side="left", padx=(12, 0), fill="x", expand=True)

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

    def run_action(self, action):
        if not is_admin():
            elevate()
            return

        script = CLEANUP_SCRIPT if action == "cleanup" else SPEEDUP_SCRIPT
        label = "Cleanup" if action == "cleanup" else "Speed up"

        if not os.path.exists(script):
            messagebox.showerror("Missing script", f"Could not find {os.path.basename(script)}")
            return

        if not messagebox.askyesno(
            f"{label} OS",
            f"This will {label.lower()} your Windows OS.\n\n"
            "Make sure you have saved your work. A restart may be required after speed up.\n\nContinue?",
        ):
            return

        self._set_buttons("disabled")
        self.log.delete("1.0", "end")
        self._log(f"Starting {label}...", level="cmd")
        threading.Thread(target=self._run_script, args=(script, label), daemon=True).start()

    def _run_script(self, script, label):
        try:
            ps_cmd = (
                f'powershell -NoProfile -ExecutionPolicy Bypass -File "{script}"'
            )
            self._log(f"> {ps_cmd}", level="cmd")

            proc = __import__("subprocess").Popen(
                ps_cmd,
                shell=True,
                stdout=__import__("subprocess").PIPE,
                stderr=__import__("subprocess").STDOUT,
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
