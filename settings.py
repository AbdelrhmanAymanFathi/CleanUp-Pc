"""Saved settings for CleanUp-Pc.

Stored atomically in %APPDATA%\\CleanUp-Pc\\settings.json.
Never crashes the app on I/O errors; falls back to defaults.
"""
import json
import os
import tempfile

APP_NAME = "CleanUp-Pc"
SETTINGS_VERSION = 1

DEFAULTS = {
    "version": SETTINGS_VERSION,
    "profile": "balanced",
    # cleanup checkboxes
    "o_browser": True,
    "o_dism": True,
    "o_prefetch": False,
    "o_hibernate": False,
    "o_compact": False,
    "o_explorer": False,
    "o_winold": False,
    "o_events": False,
    # speed up checkboxes
    "o_telemetry": True,
    "o_restore_point": True,
    "o_sysmain": False,
    "o_search": False,
    "o_xbox": False,
    # window geometry
    "width": 940,
    "height": 800,
    # last folder used by "Save log"
    "last_log_folder": "",
}

# Profile definitions. "maximum" o_sysmain is overridden at runtime based on SSD.
PROFILES = {
    "safe": {
        "label": "Safe",
        "desc": "Browser cache only. Minimal changes, safest choice.",
        "values": {
            "o_browser": True,
            "o_dism": False,
            "o_prefetch": False,
            "o_hibernate": False,
            "o_compact": False,
            "o_explorer": False,
            "o_winold": False,
            "o_events": False,
            "o_telemetry": True,
            "o_restore_point": True,
            "o_sysmain": False,
            "o_search": False,
            "o_xbox": False,
        },
    },
    "balanced": {
        "label": "Balanced",
        "desc": "Browser cache + DISM + telemetry off + restore point. Recommended default.",
        "values": {
            "o_browser": True,
            "o_dism": True,
            "o_prefetch": False,
            "o_hibernate": False,
            "o_compact": False,
            "o_explorer": False,
            "o_winold": False,
            "o_events": False,
            "o_telemetry": False,
            "o_restore_point": True,
            "o_sysmain": False,
            "o_search": False,
            "o_xbox": False,
        },
    },
    "maximum": {
        "label": "Maximum performance",
        "desc": "Balanced + Windows.old + Explorer restart + Xbox off + SysMain off (SSD only).",
        "values": {
            "o_browser": True,
            "o_dism": True,
            "o_prefetch": False,
            "o_hibernate": False,
            "o_compact": False,
            "o_explorer": True,
            "o_winold": True,
            "o_events": False,
            "o_telemetry": False,
            "o_restore_point": True,
            "o_sysmain": False,
            "o_search": False,
            "o_xbox": True,
        },
    },
    "custom": {
        "label": "Custom",
        "desc": "You changed checkboxes manually — settings are fully under your control.",
        "values": {},
    },
}


def _settings_path():
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    base = os.path.join(appdata, APP_NAME)
    try:
        os.makedirs(base, exist_ok=True)
    except OSError:
        pass
    return os.path.join(base, "settings.json")


class Settings:
    def __init__(self):
        self.data = dict(DEFAULTS)
        self._load()

    def _load(self):
        path = _settings_path()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                self.data = dict(DEFAULTS)
                return
            for key in DEFAULTS:
                if key in data:
                    self.data[key] = data[key]
        except (OSError, ValueError, json.JSONDecodeError):
            self.data = dict(DEFAULTS)

    def save(self):
        path = _settings_path()
        if not path:
            return
        try:
            dirn = os.path.dirname(path)
            fd, tmp = tempfile.mkstemp(dir=dirn, prefix=".settings-", suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
            os.replace(tmp, path)
        except OSError:
            pass

    def get(self, key, default=None):
        return self.data.get(key, DEFAULTS.get(key, default))

    def set(self, key, value):
        self.data[key] = value

    def apply_to_app(self, app):
        profile = self.get("profile", "balanced")
        app._apply_profile(profile, from_settings=True)
        for key, var in app._checkbox_vars().items():
            if key in self.data:
                var.set(bool(self.data[key]))
        try:
            app.geometry(f"{int(self.get('width', 940))}x{int(self.get('height', 800))}")
        except Exception:
            pass
        app.last_log_folder = self.get("last_log_folder", "")

    def capture_from_app(self, app):
        self.data["profile"] = app.profile_var.get()
        for key, var in app._checkbox_vars().items():
            self.data[key] = bool(var.get())
        try:
            app.update_idletasks()
            geom = app.geometry()
            size_part = geom.split("+")[0]
            w, h = size_part.split("x")
            self.data["width"] = int(w)
            self.data["height"] = int(h)
        except Exception:
            pass
        self.data["last_log_folder"] = getattr(app, "last_log_folder", "")
