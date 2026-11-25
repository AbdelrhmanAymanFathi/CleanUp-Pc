"""Fail if the installer version and version.txt disagree."""
import pathlib
import re
import sys

root = pathlib.Path(__file__).resolve().parent.parent
iss = (root / "installer" / "CleanUp-Pc.iss").read_text(encoding="utf-8")
ver = (root / "version.txt").read_text(encoding="utf-8")

m_iss = re.search(r'#define\s+MyAppVersion\s+"([^"]+)"', iss)
m_ver = re.search(r"u'FileVersion',\s*u'([^']+)'", ver)
if not m_iss or not m_ver:
    print("ERROR: could not read the version from CleanUp-Pc.iss or version.txt")
    sys.exit(1)


def norm(v):
    parts = v.split(".")
    return tuple(int(p) for p in (parts + ["0"] * 4)[:4])


if norm(m_iss.group(1)) != norm(m_ver.group(1)):
    print(f"ERROR: version mismatch - installer {m_iss.group(1)} vs version.txt {m_ver.group(1)}")
    print("Update MyAppVersion in installer\\CleanUp-Pc.iss and FileVersion/ProductVersion/filevers/prodvers in version.txt.")
    sys.exit(1)

print(f"Version OK: {m_iss.group(1)}")
