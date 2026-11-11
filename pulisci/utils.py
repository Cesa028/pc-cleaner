"""Funzioni di supporto: formattazione, privilegi, percorsi, log."""
from __future__ import annotations

import ctypes
import datetime as _dt
import os
import shutil
import string
import subprocess
import sys
from ctypes import wintypes

APP_NAME = "PC Cleaner"
APP_VERSION = "1.1.2"


def fmt_size(n: float) -> str:
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}".replace(".", ",")
        n /= 1024
    return f"{n:.1f} TB"


def env(name: str) -> str:
    return os.environ.get(name, "")


def expand(path: str) -> str:
    return os.path.normpath(os.path.expandvars(path))


# ---------------------------------------------------------------- privilegi
def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin() -> bool:
    """Riavvia l'app con UAC. Ritorna True se il nuovo processo è partito."""
    if getattr(sys, "frozen", False):
        exe, params = sys.executable, " ".join(f'"{a}"' for a in sys.argv[1:])
    else:
        exe = sys.executable
        params = " ".join(f'"{a}"' for a in [os.path.abspath(sys.argv[0]), *sys.argv[1:]])
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
    return rc > 32


# ---------------------------------------------------------------- dischi
DRIVE_FIXED = 3
DRIVE_REMOVABLE = 2


def list_drives() -> list[dict]:
    drives = []
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    for i, letter in enumerate(string.ascii_uppercase):
        if not mask & (1 << i):
            continue
        root = f"{letter}:\\"
        dtype = ctypes.windll.kernel32.GetDriveTypeW(root)
        if dtype not in (DRIVE_FIXED, DRIVE_REMOVABLE):
            continue
        try:
            u = shutil.disk_usage(root)
        except OSError:
            continue
        label = ctypes.create_unicode_buffer(261)
        ctypes.windll.kernel32.GetVolumeInformationW(root, label, 261, None, None, None, None, 0)
        drives.append({
            "root": root, "label": label.value or ("Disco locale" if dtype == DRIVE_FIXED else "Rimovibile"),
            "total": u.total, "used": u.used, "free": u.free,
        })
    return drives


# ---------------------------------------------------------------- cestino
class _SHQUERYRBINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("i64Size", ctypes.c_longlong), ("i64NumItems", ctypes.c_longlong)]


def recycle_bin_info() -> tuple[int, int]:
    info = _SHQUERYRBINFO()
    info.cbSize = ctypes.sizeof(info)
    if ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info)) != 0:
        return 0, 0
    return int(info.i64Size), int(info.i64NumItems)


def empty_recycle_bin() -> bool:
    # SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
    rc = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x7)
    return rc in (0, -2147418113)  # S_OK oppure E_UNEXPECTED (cestino già vuoto)


def open_cleanmgr_admin() -> None:
    """Apre Pulizia disco di Windows con i diritti di amministratore (chiede l'UAC se serve)."""
    if is_admin():
        subprocess.Popen(["cleanmgr.exe"])
    else:
        ctypes.windll.shell32.ShellExecuteW(None, "runas", "cleanmgr.exe", None, None, 1)


# ---------------------------------------------------------------- processi
def running_processes() -> set[str]:
    try:
        out = subprocess.run(
            ["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=15,
        ).stdout
    except Exception:
        return set()
    names = set()
    for line in out.splitlines():
        if line.startswith('"'):
            names.add(line.split('","')[0].strip('"').lower())
    return names


# ---------------------------------------------------------------- shell
def open_in_explorer(path: str) -> None:
    if os.path.isdir(path):
        os.startfile(path)
    else:
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])


def protected_path(path: str) -> bool:
    """Percorsi che l'app non deve mai mandare nel cestino."""
    p = os.path.normcase(os.path.normpath(os.path.abspath(path))).rstrip("\\")
    if len(p) <= 3:  # radice di un disco
        return True
    sysroots = [env("SystemRoot"), env("ProgramFiles"), env("ProgramFiles(x86)"), env("ProgramData"),
                env("USERPROFILE"), os.path.dirname(env("USERPROFILE"))]
    for r in sysroots:
        if not r:
            continue
        r = os.path.normcase(os.path.normpath(r)).rstrip("\\")
        if p == r:
            return True
    win = os.path.normcase(env("SystemRoot") or r"C:\Windows")
    if p.startswith(win + "\\"):
        return True
    return False


# ---------------------------------------------------------------- log
def data_dir() -> str:
    d = os.path.join(env("LOCALAPPDATA") or os.path.expanduser("~"), APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def log(msg: str) -> None:
    try:
        with open(os.path.join(data_dir(), "registro.txt"), "a", encoding="utf-8") as f:
            f.write(f"[{_dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}\n")
    except OSError:
        pass
