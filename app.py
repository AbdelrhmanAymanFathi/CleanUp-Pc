import ctypes
import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from collections import namedtuple
from tkinter import filedialog, messagebox, scrolledtext, ttk

try:
    import winreg
except ImportError:  # not on Windows (e.g. when linting)
    winreg = None

from settings import Settings
from diskusage import DiskUsageWindow

APP_TITLE = "CleanUp-Pc - Windows Optimizer"
FROZEN = getattr(sys, "frozen", False)
BASE_DIR = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))

CLEANUP_SCRIPT = os.path.join(BASE_DIR, "cleanup.ps1")
SPEEDUP_SCRIPT = os.path.join(BASE_DIR, "speedup.ps1")
RESTORE_SCRIPT = os.path.join(BASE_DIR, "restore-defaults.ps1")

CREATE_NO_WINDOW = 0x08000000

# Colors
BG = "#0f172a"
PANEL = "#1e293b"
BORDER = "#334155"
FG = "#f8fafc"
MUTED = "#94a3b8"
LOG_BG = "#020617"

PROGRESS_RE = re.compile(r"^##PROGRESS:(\d+)\|(.*)$")
DISM_BAR_RE = re.compile(r"^\[[= ]*[\d.]+%[= ]*\]$")
ERR_RE = re.compile(r"\b(error|failed|exception)\b", re.I)
WARN_RE = re.compile(r"\b(skip(ped)?|warning|could not|detected|laptop)\b", re.I)

OSInfo = namedtuple("OSInfo", "caption build version kind is_server")


# --------------------------------------------------------------------------- #
# System helpers
# --------------------------------------------------------------------------- #
def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin():
    """Only used when running from source (python app.py). The .exe is built with
    uac_admin=True, so Windows elevates it before it starts."""
    params = f'"{os.path.abspath(__file__)}"'
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)


def enable_dpi_awareness():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _read_reg(root, path, name, default=""):
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return default


def detect_windows():
    """Detect the Windows caption, build and Desktop/Server edition without PowerShell."""
    caption, build, version, installation = "Windows", "", "", ""

    if winreg:
        cv = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
        caption = _read_reg(winreg.HKEY_LOCAL_MACHINE, cv, "ProductName", caption)
        build = str(_read_reg(winreg.HKEY_LOCAL_MACHINE, cv, "CurrentBuildNumber", ""))
        ubr = _read_reg(winreg.HKEY_LOCAL_MACHINE, cv, "UBR", None)
        version = str(
            _read_reg(winreg.HKEY_LOCAL_MACHINE, cv, "DisplayVersion", "")
            or _read_reg(winreg.HKEY_LOCAL_MACHINE, cv, "ReleaseId", "")
        )
        installation = str(_read_reg(winreg.HKEY_LOCAL_MACHINE, cv, "InstallationType", ""))
        if build and ubr is not None:
            build = f"{build}.{ubr}"

    is_server = installation.lower().startswith("server") if installation else False
    try:
        v = sys.getwindowsversion()
        if not build:
            build = str(v.build)
        if not installation:
            is_server = v.product_type != 1
    except Exception:
        pass

    try:
        build_num = int(build.split(".")[0])
    except ValueError:
        build_num = 0

    # ProductName still says "Windows 10" on Windows 11.
    if not is_server and build_num >= 22000:
        caption = caption.replace("Windows 10", "Windows 11")

    if is_server:
        kind = "server"
    elif build_num >= 22000:
        kind = "11"
    elif build_num >= 10240:
        kind = "10"
    else:
        kind = "other"

    return OSInfo(caption, build, version, kind, is_server)


# --------------------------------------------------------------------------- #
# Startup programs (Run keys + StartupApproved)
# --------------------------------------------------------------------------- #
def _startup_locations():
    cv = r"Software\Microsoft\Windows\CurrentVersion"
    appr = cv + r"\Explorer\StartupApproved"
    return [
        ("Current user", winreg.HKEY_CURRENT_USER, cv + r"\Run", 0, appr + r"\Run"),
        ("All users", winreg.HKEY_LOCAL_MACHINE, cv + r"\Run", winreg.KEY_WOW64_64KEY, appr + r"\Run"),
        ("All users (32-bit)", winreg.HKEY_LOCAL_MACHINE, cv + r"\Run", winreg.KEY_WOW64_32KEY, appr + r"\Run32"),
    ]


def _startup_disabled(root, approved_path, name):
    try:
        with winreg.OpenKey(root, approved_path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            data = winreg.QueryValueEx(key, name)[0]
            return bool(data) and data[0] % 2 == 1
    except OSError:
        return False


def list_startup_items():
    items = []
    if not winreg:
        return items
    for label, root, path, wow, approved in _startup_locations():
        try:
            key = winreg.OpenKey(root, path, 0, winreg.KEY_READ | wow)
        except OSError:
            continue
        with key:
            i = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                except OSError:
                    break
                i += 1
                items.append(
                    {
                        "where": label,
                        "root": root,
                        "approved": approved,
                        "name": name,
                        "command": str(value),
                        "disabled": _startup_disabled(root, approved, name),
                    }
                )
    return items


def set_startup_disabled(item, disabled):
    with winreg.CreateKeyEx(
        item["root"], item["approved"], 0, winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY
    ) as key:
        data = bytes([3 if disabled else 2]) + b"\x00" * 11
        winreg.SetValueEx(key, item["name"], 0, winreg.REG_BINARY, data)


# --------------------------------------------------------------------------- #
# GUI
# --------------------------------------------------------------------------- #
class OptimizerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("940x800")
        self.minsize(860, 700)
        self.configure(bg=BG)

        self.os = detect_windows()
        self.settings = Settings()
        self.last_log_folder = self.settings.get("last_log_folder", "")

        self.q = queue.Queue()
        self.proc = None
        self.jobs = []
        self.job_index = 0
        self.job_total = 0
        self.running = False
        self.cancelled = False
        self._applying_profile = False
        self.is_ssd = None  # detected asynchronously

        self._init_vars()
        self._init_style()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Apply saved settings (profile + checkboxes + geometry)
        self.settings.apply_to_app(self)

        self._log(f"Detected: {self.os.caption}  (Build {self.os.build})  -  {self._edition()}", "cmd")
        self._show_recommendation()
        if self.os.is_server:
            self._log("Server detected: client-only tweaks are skipped automatically.", "warn")

        # Detect SSD asynchronously (used by Maximum performance profile).
        self._detect_ssd()

        self.after(80, self._poll_queue)

    # ---- setup ------------------------------------------------------------ #
    def _edition(self):
        return "Server" if self.os.is_server else "Desktop"

    def _init_vars(self):
        v = tk.BooleanVar
        self.profile_var = tk.StringVar(value="balanced")
        # Cleanup options
        self.o_browser = v(value=True)
        self.o_dism = v(value=True)
        self.o_prefetch = v(value=False)
        self.o_hibernate = v(value=False)
        self.o_compact = v(value=False)
        self.o_explorer = v(value=False)
        self.o_winold = v(value=False)
        self.o_events = v(value=False)
        # Speed Up options
        self.o_telemetry = v(value=True)
        self.o_restore_point = v(value=True)
        self.o_sysmain = v(value=False)
        self.o_search = v(value=False)
        self.o_xbox = v(value=False)

        self.progress_var = tk.DoubleVar(value=0)
        self.status_var = tk.StringVar(value="Ready")

        # Trace every checkbox so a manual change flips the profile to Custom.
        for var in [
            self.o_browser, self.o_dism, self.o_prefetch, self.o_hibernate,
            self.o_compact, self.o_explorer, self.o_winold, self.o_events,
            self.o_telemetry, self.o_restore_point, self.o_sysmain,
            self.o_search, self.o_xbox,
        ]:
            var.trace_add("write", self._on_checkbox_change)

    def _checkbox_vars(self):
        return {
            "o_browser": self.o_browser,
            "o_dism": self.o_dism,
            "o_prefetch": self.o_prefetch,
            "o_hibernate": self.o_hibernate,
            "o_compact": self.o_compact,
            "o_explorer": self.o_explorer,
            "o_winold": self.o_winold,
            "o_events": self.o_events,
            "o_telemetry": self.o_telemetry,
            "o_restore_point": self.o_restore_point,
            "o_sysmain": self.o_sysmain,
            "o_search": self.o_search,
            "o_xbox": self.o_xbox,
        }

    def _on_checkbox_change(self, *args):
        if self._applying_profile:
            return
        self.profile_var.set("custom")
        self._update_profile_desc()

    def _apply_profile(self, profile, from_settings=False):
        """Apply a named profile's checkbox values."""
        self._applying_profile = True
        try:
            from settings import PROFILES
            prof = PROFILES.get(profile, PROFILES["balanced"])
            values = dict(prof["values"])

            # Maximum performance: SysMain disable only on SSD.
            if profile == "maximum":
                if self.is_ssd is True:
                    values["o_sysmain"] = True
                elif self.is_ssd is False:
                    values["o_sysmain"] = False
                else:
                    values["o_sysmain"] = False  # unknown -> treat as HDD

            # Server: client-only tweaks are skipped.
            if self.os.is_server:
                values["o_explorer"] = False
                values["o_sysmain"] = False
                values["o_search"] = False
                values["o_xbox"] = False

            for key, var in self._checkbox_vars().items():
                if key in values:
                    var.set(values[key])
            self.profile_var.set(profile)
        finally:
            self._applying_profile = False
        self._update_profile_desc()

    def _update_profile_desc(self):
        from settings import PROFILES
        profile = self.profile_var.get()
        prof = PROFILES.get(profile)
        if prof:
            self.profile_desc.config(text=prof["desc"])
        else:
            self.profile_desc.config(text="Custom settings — you control every checkbox.")

    def _detect_ssd(self):
        """Detect if the system drive is an SSD (background thread, once at startup)."""

        def _worker():
            try:
                ps = [
                    "powershell", "-NoProfile", "-Command",
                    "Get-PhysicalDisk | Where-Object { $_.DeviceID -eq "
                    "(Get-Partition -DriveLetter 'C').DiskNumber } | "
                    "Select-Object -ExpandProperty MediaType",
                ]
                out = subprocess.check_output(
                    ps, stderr=subprocess.STDOUT, text=True, timeout=10,
                )
                media = out.strip().lower()
                self.is_ssd = "ssd" in media
            except Exception:
                self.is_ssd = None
            # Re-apply Maximum performance profile now that we know SSD status.
            if self.profile_var.get() == "maximum":
                self.after(0, lambda: self._apply_profile("maximum"))

        threading.Thread(target=_worker, daemon=True).start()

    def _init_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Dark.Horizontal.TProgressbar",
            troughcolor=PANEL,
            background="#14b8a6",
            bordercolor=BORDER,
            lightcolor="#14b8a6",
            darkcolor="#14b8a6",
        )
        style.configure(
            "Dark.Treeview",
            background=LOG_BG,
            fieldbackground=LOG_BG,
            foreground=FG,
            rowheight=24,
            borderwidth=0,
        )
        style.configure("Dark.Treeview.Heading", background=PANEL, foreground=FG, relief="flat")
        style.map("Dark.Treeview", background=[("selected", "#0f766e")])

    def _button(self, parent, text, command, bg=PANEL, active="#334155", font=("Segoe UI", 10, "bold"), **kw):
        return tk.Button(
            parent,
            text=text,
            command=command,
            font=font,
            bg=bg,
            fg=FG,
            activebackground=active,
            activeforeground="#ffffff",
            disabledforeground="#64748b",
            relief="flat",
            cursor="hand2",
            **kw,
        )

    def _check(self, parent, text, var, state="normal"):
        cb = tk.Checkbutton(
            parent,
            text=text,
            variable=var,
            state=state,
            anchor="w",
            justify="left",
            font=("Segoe UI", 9),
            bg=PANEL,
            fg=FG,
            selectcolor=BG,
            activebackground=PANEL,
            activeforeground=FG,
            disabledforeground="#64748b",
            highlightthickness=0,
        )
        cb.pack(fill="x", anchor="w", pady=1)
        return cb

    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=18, pady=(14, 4))
        tk.Label(header, text=APP_TITLE, font=("Segoe UI", 16, "bold"), fg=FG, bg=BG).pack(anchor="w")
        ver = f"  |  {self.os.version}" if self.os.version else ""
        self.version_label = tk.Label(
            header,
            text=f"{self.os.caption}  |  Build {self.os.build}{ver}  |  {self._edition()}",
            font=("Segoe UI", 10),
            fg=MUTED,
            bg=BG,
        )
        self.version_label.pack(anchor="w", pady=(2, 0))

        # Recommendation banner
        self.rec_frame = tk.Frame(self, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        self.rec_frame.pack(fill="x", padx=18, pady=(8, 6))
        self.rec_icon = tk.Label(self.rec_frame, text="", font=("Segoe UI", 12), fg="#fbbf24", bg=PANEL)
        self.rec_icon.pack(side="left", padx=(12, 8), pady=8)
        self.rec_text = tk.Label(
            self.rec_frame, text="", font=("Segoe UI", 10, "bold"), fg=FG, bg=PANEL,
            justify="left", anchor="w",
        )
        self.rec_text.pack(side="left", padx=(0, 12), pady=8, fill="x", expand=True)

        # ---- Options panel: profile selector + checkboxes ----
        opts = tk.Frame(self, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        opts.pack(fill="x", padx=18, pady=(0, 6))

        # Profile selector row
        prof_row = tk.Frame(opts, bg=PANEL)
        prof_row.pack(fill="x", padx=12, pady=(8, 2))
        tk.Label(prof_row, text="Profile:", font=("Segoe UI", 9, "bold"), fg=MUTED, bg=PANEL).pack(side="left")
        self.profile_combo = ttk.Combobox(
            prof_row, textvariable=self.profile_var, state="readonly", width=20, font=("Segoe UI", 9),
        )
        self.profile_combo["values"] = [
            PROFILES["safe"]["label"],
            PROFILES["balanced"]["label"],
            PROFILES["maximum"]["label"],
            PROFILES["custom"]["label"],
        ]
        self.profile_combo.pack(side="left", padx=(6, 0))
        self.profile_combo.bind("<<ComboboxSelected>>", self._on_profile_selected)

        self.profile_desc = tk.Label(
            prof_row, text="", font=("Segoe UI", 8), fg=MUTED, bg=PANEL, anchor="w",
        )
        self.profile_desc.pack(side="left", padx=(12, 0), fill="x", expand=True)

        self.btn_reset = tk.Button(
            prof_row, text="Reset to defaults", command=self.reset_defaults, bg=BORDER, fg=FG,
            activebackground="#475569", activeforeground=FG, relief="flat",
            font=("Segoe UI", 8), width=14,
        )
        self.btn_reset.pack(side="right")

        left = tk.Frame(opts, bg=PANEL)
        left.pack(side="left", fill="both", expand=True, padx=12, pady=8)
        right = tk.Frame(opts, bg=PANEL)
        right.pack(side="left", fill="both", expand=True, padx=12, pady=8)

        tk.Label(left, text="Cleanup options", font=("Segoe UI", 9, "bold"), fg=MUTED, bg=PANEL).pack(anchor="w")
        self._check(left, "Browser caches (Chrome / Edge / Brave / Firefox)", self.o_browser)
        self._check(left, "Component store cleanup (DISM, slow)", self.o_dism)
        self._check(left, "Windows.old (previous Windows install)", self.o_winold)
        self._check(left, "Prefetch (apps start slower once afterwards)", self.o_prefetch)
        self._check(left, "Turn off Hibernate / Fast Startup", self.o_hibernate)
        self._check(left, "Restart Explorer + rebuild icon cache", self.o_explorer)
        self._check(left, "Clear all Windows event logs", self.o_events)
        self._check(left, "Compact OS (slow, can hurt HDDs)", self.o_compact)

        tk.Label(right, text="Speed Up options", font=("Segoe UI", 9, "bold"), fg=MUTED, bg=PANEL).pack(anchor="w")
        self._check(right, "Create a restore point first", self.o_restore_point,
                    "disabled" if self.os.is_server else "normal")
        self._check(right, "Disable telemetry services and tasks", self.o_telemetry)
        self._check(right, "Disable SysMain (Superfetch)", self.o_sysmain)
        self._check(right, "Disable Windows Search (Start search may break)", self.o_search)
        self._check(right, "Disable Xbox services (breaks Xbox / Game Pass)", self.o_xbox,
                    "disabled" if self.os.is_server else "normal")
        tk.Label(
            right,
            text="Speed Up is reversible: use 'Undo Speed Up'.",
            font=("Segoe UI", 8),
            fg=MUTED,
            bg=PANEL,
        ).pack(anchor="w", pady=(6, 0))

        # Main buttons
        row1 = tk.Frame(self, bg=BG)
        row1.pack(fill="x", padx=18, pady=(4, 4))
        self.btn_cleanup = self._button(
            row1, "Cleanup My OS", self.run_cleanup, font=("Segoe UI", 12, "bold"), height=2
        )
        self.btn_cleanup.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.btn_speedup = self._button(
            row1, "Speed Up My OS", self.run_speedup, font=("Segoe UI", 12, "bold"), height=2
        )
        self.btn_speedup.pack(side="left", fill="x", expand=True, padx=(6, 0))

        self.btn_auto = self._button(
            self, "Auto Optimize (Recommended)", self.run_auto, bg="#0f766e", active="#115e59",
            font=("Segoe UI", 11, "bold"), height=2,
        )
        self.btn_auto.pack(fill="x", padx=18, pady=(0, 4))

        row2 = tk.Frame(self, bg=BG)
        row2.pack(fill="x", padx=18, pady=(0, 6))
        self.btn_scan = self._button(row2, "Scan only (dry run)", self.run_scan)
        self.btn_scan.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.btn_undo = self._button(row2, "Undo Speed Up", self.run_undo)
        self.btn_undo.pack(side="left", fill="x", expand=True, padx=4)
        self.btn_startup = self._button(row2, "Startup Manager", self.open_startup_manager)
        self.btn_startup.pack(side="left", fill="x", expand=True, padx=(4, 0))
        self.btn_disk = self._button(row2, "Disk Usage", self.open_disk_usage)
        self.btn_disk.pack(side="left", fill="x", expand=True, padx=(4, 0))

        self.action_buttons = [
            self.btn_cleanup, self.btn_speedup, self.btn_auto,
            self.btn_scan, self.btn_undo, self.btn_startup, self.btn_disk,
        ]

        # Progress
        prog = tk.Frame(self, bg=BG)
        prog.pack(fill="x", padx=18, pady=(0, 6))
        self.progress = ttk.Progressbar(
            prog, variable=self.progress_var, maximum=100, style="Dark.Horizontal.TProgressbar"
        )
        self.progress.pack(side="left", fill="x", expand=True)
        self.btn_cancel = self._button(prog, "Cancel", self.cancel, bg="#7f1d1d", active="#991b1b", width=10)
        self.btn_cancel.config(state="disabled")
        self.btn_cancel.pack(side="left", padx=(8, 0))
        tk.Label(self, textvariable=self.status_var, font=("Segoe UI", 9), fg=MUTED, bg=BG, anchor="w").pack(
            fill="x", padx=18
        )

        # Log
        out = tk.Frame(self, bg=BG)
        out.pack(fill="both", expand=True, padx=18, pady=(6, 6))
        tk.Label(out, text="Output / Log:", font=("Segoe UI", 9, "bold"), fg="#cbd5e1", bg=BG).pack(anchor="w")
        self.log = scrolledtext.ScrolledText(
            out, font=("Consolas", 10), bg=LOG_BG, fg="#e2e8f0", insertbackground=FG,
            relief="flat", padx=8, pady=8, height=8,
        )
        self.log.pack(fill="both", expand=True)
        for level, color in {
            "info": "#e2e8f0", "ok": "#4ade80", "warn": "#fbbf24", "error": "#f87171", "cmd": "#818cf8",
        }.items():
            self.log.tag_config(level, foreground=color)

        bottom = tk.Frame(self, bg=BG)
        bottom.pack(pady=(0, 10))
        self._button(bottom, "Save log...", self.save_log, bg=BORDER, font=("Segoe UI", 10), width=12).pack(
            side="left", padx=4
        )
        self._button(bottom, "Close", self._on_close, bg=BORDER, font=("Segoe UI", 10), width=12).pack(
            side="left", padx=4
        )

        self._update_profile_desc()

    # ---- profile selection ------------------------------------------------ #
    def _on_profile_selected(self, event=None):
        label = self.profile_var.get()
        from settings import PROFILES
        for key, prof in PROFILES.items():
            if prof["label"] == label:
                self._apply_profile(key)
                break

    # ---- logging ---------------------------------------------------------- #
    def _log(self, text, level="info"):
        self.log.insert("end", text + "\n", level)
        self.log.see("end")

    def _classify(self, line):
        if "Finished Successfully" in line:
            return "ok"
        if ERR_RE.search(line):
            return "error"
        if WARN_RE.search(line):
            return "warn"
        if line.startswith("==>"):
            return "cmd"
        return "info"

    def save_log(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile="CleanUp-Pc-log.txt",
            initialdir=self.last_log_folder or None,
            filetypes=[("Text", "*.txt")],
        )
        if path:
            try:
                self.last_log_folder = os.path.dirname(path)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.log.get("1.0", "end"))
            except OSError as exc:
                messagebox.showerror("Save log", str(exc))

    # ---- option -> script arguments -------------------------------------- #
    def _cleanup_args(self, dry=False):
        args = ["-DryRun"] if dry else []
        for var, flag in (
            (self.o_prefetch, "-CleanPrefetch"),
            (self.o_hibernate, "-DisableHibernate"),
            (self.o_compact, "-CompactOS"),
            (self.o_explorer, "-RestartExplorer"),
            (self.o_browser, "-BrowserCache"),
            (self.o_winold, "-WindowsOld"),
            (self.o_events, "-EventLogs"),
            (self.o_dism, "-RunDism"),
        ):
            if var.get():
                args.append(flag)
        return args

    def _speedup_args(self):
        args = []
        if not self.o_telemetry.get():
            args.append("-KeepTelemetry")
        if self.o_sysmain.get():
            args.append("-DisableSysMain")
        if self.o_search.get():
            args.append("-DisableSearch")
        if self.o_xbox.get() and not self.os.is_server:
            args.append("-DisableXbox")
        if not self.o_restore_point.get() or self.os.is_server:
            args.append("-NoRestorePoint")
        return args

    # ---- actions ---------------------------------------------------------- #
    def _can_start(self):
        if self.running:
            return False
        if FROZEN or sys.platform != "win32":
            return True
        if not is_admin():
            messagebox.showerror("Administrator required", "Please run this app as Administrator.")
            return False
        return True

    def run_cleanup(self):
        if not self._can_start():
            return
        if not messagebox.askyesno(
            "Cleanup My OS",
            f"This will clean {self.os.caption} ({self._edition()}).\n\n"
            "Tip: run 'Scan only' first to see how much space can be freed.\n"
            "Save your work first.\n\nContinue?",
        ):
            return
        self._start_jobs([("Cleanup", CLEANUP_SCRIPT, self._cleanup_args())])

    def run_scan(self):
        if not self._can_start():
            return
        self._start_jobs([("Scan", CLEANUP_SCRIPT, self._cleanup_args(dry=True))])

    def run_speedup(self):
        if not self._can_start():
            return
        if not messagebox.askyesno(
            "Speed Up My OS",
            f"This will tune {self.os.caption} ({self._edition()}) for performance.\n\n"
            "Changes are recorded so you can undo them with 'Undo Speed Up'.\n"
            "A restart is recommended afterwards.\n\nContinue?",
        ):
            return
        self._start_jobs([("Speed up", SPEEDUP_SCRIPT, self._speedup_args())])

    def run_auto(self):
        if not self._can_start():
            return
        jobs = [("Cleanup", CLEANUP_SCRIPT, self._cleanup_args())]
        steps = "Cleanup"
        if not self.os.is_server:
            jobs.append(("Speed up", SPEEDUP_SCRIPT, self._speedup_args()))
            steps = "Cleanup, then Speed Up"
        if not messagebox.askyesno(
            "Auto Optimize",
            f"Auto Optimize will run: {steps}\non {self.os.caption} ({self._edition()}).\n\n"
            "Save your work first.\n\nContinue?",
        ):
            return
        self._start_jobs(jobs)

    def run_undo(self):
        if not self._can_start():
            return
        if not messagebox.askyesno(
            "Undo Speed Up", "Restore the settings, services and tasks changed by Speed Up?"
        ):
            return
        self._start_jobs([("Undo Speed Up", RESTORE_SCRIPT, [])])

    def reset_defaults(self):
        if self.running:
            return
        if not messagebox.askyesno("Reset to defaults", "Reset all checkboxes to the Balanced profile defaults?"):
            return
        self._apply_profile("balanced")
        self.settings.capture_from_app(self)
        self.settings.save()
        self._log("Settings reset to Balanced defaults.", "ok")

    def open_disk_usage(self):
        DiskUsageWindow(self)

    # ---- job runner ------------------------------------------------------- #
    def _set_running(self, running):
        self.running = running
        for b in self.action_buttons:
            b.config(state="disabled" if running else "normal")
        self.btn_cancel.config(state="normal" if running else "disabled")

    def _start_jobs(self, jobs):
        self.jobs = list(jobs)
        self.job_total = len(jobs)
        self.job_index = 0
        self.cancelled = False
        self.log.delete("1.0", "end")
        self.progress_var.set(0)
        self.status_var.set("Starting...")
        self._set_running(True)
        self._next_job()

    def _next_job(self):
        if self.cancelled or not self.jobs:
            self._finish()
            return

        label, script, args = self.jobs.pop(0)
        self.job_index += 1
        if not os.path.exists(script):
            self._log(f"Missing script: {os.path.basename(script)}", "error")
            self._next_job()
            return

        cmd = [
            "powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-File", script, "-NoPause", *args,
        ]
        self._log(f"> {label}: {os.path.basename(script)} {' '.join(args)}".rstrip(), "cmd")
        try:
            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                encoding="utf-8",
                errors="replace",
                creationflags=CREATE_NO_WINDOW,
            )
        except Exception as exc:
            self._log(f"Error starting {label}: {exc}", "error")
            self._next_job()
            return

        threading.Thread(target=self._reader, args=(self.proc, label), daemon=True).start()

    def _reader(self, proc, label):
        try:
            for line in proc.stdout:
                self.q.put(("line", line.rstrip("\r\n")))
        finally:
            proc.wait()
            self.q.put(("done", label, proc.returncode))

    def _poll_queue(self):
        try:
            while True:
                item = self.q.get_nowait()
                if item[0] == "line":
                    self._handle_line(item[1])
                else:
                    self._on_done(item[1], item[2])
        except queue.Empty:
            pass
        self.after(80, self._poll_queue)

    def _handle_line(self, line):
        m = PROGRESS_RE.match(line)
        if m:
            pct = int(m.group(1))
            overall = ((self.job_index - 1) + pct / 100.0) / max(self.job_total, 1) * 100
            self.progress_var.set(overall)
            self.status_var.set(f"{m.group(2)}  ({self.job_index}/{self.job_total})")
            return
        if not line.strip() or DISM_BAR_RE.match(line.strip()):
            return
        self._log(line, self._classify(line))

    def _on_done(self, label, rc):
        self.proc = None
        if self.cancelled:
            self._log(f"{label} cancelled.", "warn")
        elif rc == 0:
            self._log(f"{label} completed successfully.", "ok")
        else:
            self._log(f"{label} finished with exit code {rc}.", "error")
        self._next_job()

    def _finish(self):
        self.proc = None
        self._set_running(False)
        # Persist settings after each job completes.
        self.settings.capture_from_app(self)
        self.settings.save()
        if self.cancelled:
            self.status_var.set("Cancelled")
        else:
            self.progress_var.set(100)
            self.status_var.set("Finished")
            self._log("All done.", "ok")

    def cancel(self):
        if not self.running:
            return
        self.cancelled = True
        self.jobs.clear()
        self._log("Cancelling...", "warn")
        self._kill_proc()

    def _kill_proc(self):
        if self.proc and self.proc.poll() is None:
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(self.proc.pid), "/T", "/F"],
                    creationflags=CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass

    def _on_close(self):
        if self.running:
            if not messagebox.askyesno("Close", "An operation is still running. Cancel it and close?"):
                return
            self.cancelled = True
            self.jobs.clear()
            self._kill_proc()
        self.settings.capture_from_app(self)
        self.settings.save()
        self.destroy()

    # ---- startup manager -------------------------------------------------- #
    def open_startup_manager(self):
        if not winreg:
            messagebox.showinfo("Startup Manager", "Startup Manager is only available on Windows.")
            return

        win = tk.Toplevel(self)
        win.title("Startup Manager")
        win.geometry("820x440")
        win.configure(bg=BG)
        win.transient(self)

        tk.Label(
            win,
            text="Programs that start with Windows (Run keys). Disabled items stay installed and can be re-enabled.",
            font=("Segoe UI", 9), fg=MUTED, bg=BG, anchor="w",
        ).pack(fill="x", padx=14, pady=(12, 6))

        cols = ("name", "status", "where", "command")
        tree = ttk.Treeview(win, columns=cols, show="headings", style="Dark.Treeview", selectmode="browse")
        for col, text, width in (
            ("name", "Name", 170), ("status", "Status", 80), ("where", "Scope", 120), ("command", "Command", 420)
        ):
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        tree.pack(fill="both", expand=True, padx=14)

        items = []

        def refresh():
            items.clear()
            items.extend(list_startup_items())
            tree.delete(*tree.get_children())
            for idx, it in enumerate(items):
                tree.insert(
                    "", "end", iid=str(idx),
                    values=(it["name"], "Disabled" if it["disabled"] else "Enabled", it["where"], it["command"]),
                )

        def toggle():
            sel = tree.selection()
            if not sel:
                return
            item = items[int(sel[0])]
            try:
                set_startup_disabled(item, not item["disabled"])
            except OSError as exc:
                messagebox.showerror("Startup Manager", str(exc), parent=win)
                return
            refresh()

        btns = tk.Frame(win, bg=BG)
        btns.pack(pady=10)
        self._button(btns, "Enable / Disable selected", toggle, width=24).pack(side="left", padx=4)
        self._button(btns, "Refresh", refresh, bg=BORDER, width=10).pack(side="left", padx=4)
        self._button(btns, "Close", win.destroy, bg=BORDER, width=10).pack(side="left", padx=4)
        refresh()


def main():
    if sys.platform == "win32":
        enable_dpi_awareness()
        if not FROZEN and not is_admin():
            relaunch_as_admin()
            return
    app = OptimizerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
