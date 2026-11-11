"""Programmi all'avvio. Attiva/disattiva come fa Gestione attività (chiavi StartupApproved),
quindi è sempre reversibile e Windows mostra lo stesso stato.

Nota sui 32 bit: su Windows a 64 bit un programma a 32 bit vede una copia "ridotta" del registro
(WOW64). Qui ogni chiave viene aperta chiedendo esplicitamente la vista giusta (64 bit per le chiavi
di Windows e di StartupApproved, 32 bit per i programmi a 32 bit), così la versione a 32 bit
e quella a 64 bit mostrano esattamente le stesse cose di Gestione attività."""
from __future__ import annotations

import json
import os
import struct
import subprocess
import time
import winreg
from dataclasses import dataclass

from .utils import env, log

RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
APPROVED = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved"

HIVES = {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE}
VIEW64 = winreg.KEY_WOW64_64KEY
VIEW32 = winreg.KEY_WOW64_32KEY


@dataclass
class StartupItem:
    name: str
    command: str         # comando (o percorso del collegamento per le cartelle Esecuzione automatica)
    source: str          # descrizione leggibile
    hive: str            # HKCU / HKLM dove sta lo stato
    approved_sub: str    # Run / Run32 / StartupFolder
    value_name: str      # nome del valore in StartupApproved
    enabled: bool
    needs_admin: bool
    target: str = ""     # per i collegamenti: file di destinazione reale (.exe)
    args: str = ""       # per i collegamenti: argomenti del collegamento


def _read_values(hive, key, view) -> list[tuple[str, object]]:
    out = []
    try:
        with winreg.OpenKey(hive, key, 0, winreg.KEY_READ | view) as k:
            i = 0
            while True:
                try:
                    out.append(winreg.EnumValue(k, i)[:2])
                except OSError:
                    break
                i += 1
    except OSError:
        pass
    return out


def _approved_state(hive_name: str, sub: str, value: str) -> bool:
    # StartupApproved va sempre letto nella vista a 64 bit, come fa Gestione attività
    try:
        with winreg.OpenKey(HIVES[hive_name], APPROVED + "\\" + sub, 0, winreg.KEY_READ | VIEW64) as k:
            data, _ = winreg.QueryValueEx(k, value)
            if isinstance(data, bytes) and data:
                return data[0] % 2 == 0   # 02/06 = attivo, 03/07 = disattivato
    except OSError:
        pass
    return True


# --------------------------------------------------------------------------- #
# Collegamenti (.lnk): destinazione reale
# --------------------------------------------------------------------------- #
_LNK_CACHE: dict[tuple[str, float], tuple[str, str]] = {}

_PS_SCRIPT = (
    "$ErrorActionPreference='SilentlyContinue';"
    "$paths=[Console]::In.ReadToEnd()|ConvertFrom-Json;"
    "$sh=New-Object -ComObject WScript.Shell;$out=@{};"
    "foreach($p in $paths){$l=$sh.CreateShortcut($p);$out[$p]=@($l.TargetPath,$l.Arguments)};"
    "$out|ConvertTo-Json -Compress"
)


def _powershell() -> str:
    # da un processo a 32 bit "sysnative" raggiunge il PowerShell a 64 bit
    sysnative = os.path.join(env("SystemRoot"), "Sysnative", "WindowsPowerShell", "v1.0", "powershell.exe")
    return sysnative if os.path.isfile(sysnative) else "powershell"


def resolve_shortcuts(paths: list[str]) -> dict[str, tuple[str, str]]:
    """{percorso .lnk: (file di destinazione, argomenti)}; assente se non risolvibile."""
    todo = []
    result: dict[str, tuple[str, str]] = {}
    for p in paths:
        try:
            key = (p, os.path.getmtime(p))
        except OSError:
            continue
        if key in _LNK_CACHE:
            result[p] = _LNK_CACHE[key]
        else:
            todo.append(p)
    if todo:
        try:
            r = subprocess.run([_powershell(), "-NoProfile", "-NonInteractive", "-Command", _PS_SCRIPT],
                               input=json.dumps(todo), capture_output=True, text=True, encoding="utf-8",
                               creationflags=subprocess.CREATE_NO_WINDOW, timeout=20)
            data = json.loads(r.stdout) if r.stdout.strip() else {}
            for p in todo:
                tgt, args = (data.get(p) or ["", ""])[:2]
                if tgt:
                    val = (os.path.expandvars(str(tgt)), str(args or ""))
                    result[p] = val
                    _LNK_CACHE[(p, os.path.getmtime(p))] = val
        except Exception as e:  # noqa: BLE001 - se non si riesce si mostra il collegamento stesso
            log(f"Collegamenti: destinazione non risolta ({e!r})")
    return result


def list_items() -> list[StartupItem]:
    items: list[StartupItem] = []
    for hive_name, view, sub, label in (("HKCU", VIEW64, "Run", "Registro (utente)"),
                                        ("HKLM", VIEW64, "Run", "Registro (tutti gli utenti)"),
                                        ("HKLM", VIEW32, "Run32", "Registro (tutti gli utenti, 32 bit)")):
        for name, cmd in _read_values(HIVES[hive_name], RUN, view):
            if not name:
                continue
            items.append(StartupItem(name, str(cmd), label, hive_name, sub, name,
                                     _approved_state(hive_name, sub, name), hive_name == "HKLM"))
    folders = (("HKCU", os.path.join(env("APPDATA"), r"Microsoft\Windows\Start Menu\Programs\Startup"),
                "Cartella Esecuzione automatica (utente)"),
               ("HKLM", os.path.join(env("ProgramData"), r"Microsoft\Windows\Start Menu\Programs\StartUp"),
                "Cartella Esecuzione automatica (tutti)"))
    links = []
    for hive_name, folder, label in folders:
        if not os.path.isdir(folder):
            continue
        for fn in os.listdir(folder):
            if fn.lower() == "desktop.ini":
                continue
            full = os.path.join(folder, fn)
            if fn.lower().endswith(".lnk"):
                links.append(full)
            items.append(StartupItem(os.path.splitext(fn)[0], full, label, hive_name,
                                     "StartupFolder", fn, _approved_state(hive_name, "StartupFolder", fn),
                                     hive_name == "HKLM"))
    resolved = resolve_shortcuts(links)
    for it in items:
        if it.command in resolved:
            it.target, it.args = resolved[it.command]
    items.sort(key=lambda i: i.name.lower())
    return items


def display_command(item: StartupItem) -> str:
    """Testo da mostrare nella colonna Comando: per i collegamenti il file che parte davvero."""
    if item.target:
        return f'"{item.target}" {item.args}'.strip()
    return item.command


def reveal_path(item: StartupItem) -> str:
    """File da mostrare in Esplora file ('Apri percorso file'): per un collegamento, la sua destinazione."""
    if item.approved_sub == "StartupFolder":
        if item.target and os.path.exists(item.target):
            return item.target
        return item.command
    cmd = item.command.strip()
    exe = cmd[1:cmd.find('"', 1)] if cmd.startswith('"') else cmd.split(" ")[0]
    return os.path.expandvars(exe)


def set_enabled(item: StartupItem, enabled: bool) -> None:
    """Solleva PermissionError se servono i diritti di amministratore."""
    if enabled:
        data = b"\x02" + b"\x00" * 11
    else:
        ft = int((time.time() + 11644473600) * 10_000_000)  # FILETIME, come Gestione attività
        data = b"\x03\x00\x00\x00" + struct.pack("<Q", ft)
    with winreg.CreateKeyEx(HIVES[item.hive], APPROVED + "\\" + item.approved_sub, 0,
                            winreg.KEY_SET_VALUE | VIEW64) as k:
        winreg.SetValueEx(k, item.value_name, 0, winreg.REG_BINARY, data)
    item.enabled = enabled
    log(f"Avvio automatico: {item.name} -> {'attivato' if enabled else 'disattivato'}")
