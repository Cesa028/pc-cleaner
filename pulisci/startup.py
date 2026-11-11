"""Programmi all'avvio. Attiva/disattiva come fa Gestione attività (chiavi StartupApproved),
quindi è sempre reversibile e Windows mostra lo stesso stato."""
from __future__ import annotations

import os
import struct
import time
import winreg
from dataclasses import dataclass

from .utils import env, log

RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN32 = r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"
APPROVED = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved"

HIVES = {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE}


@dataclass
class StartupItem:
    name: str
    command: str
    source: str          # descrizione leggibile
    hive: str            # HKCU / HKLM dove sta lo stato
    approved_sub: str    # Run / Run32 / StartupFolder
    value_name: str      # nome del valore in StartupApproved
    enabled: bool
    needs_admin: bool


def _read_values(hive, key) -> list[tuple[str, object]]:
    out = []
    try:
        with winreg.OpenKey(hive, key) as k:
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
    try:
        with winreg.OpenKey(HIVES[hive_name], APPROVED + "\\" + sub) as k:
            data, _ = winreg.QueryValueEx(k, value)
            if isinstance(data, bytes) and data:
                return data[0] % 2 == 0   # 02/06 = attivo, 03/07 = disattivato
    except OSError:
        pass
    return True


def list_items() -> list[StartupItem]:
    items: list[StartupItem] = []
    for hive_name, key, sub, label in (("HKCU", RUN, "Run", "Registro (utente)"),
                                       ("HKLM", RUN, "Run", "Registro (tutti gli utenti)"),
                                       ("HKLM", RUN32, "Run32", "Registro (tutti gli utenti, 32 bit)")):
        for name, cmd in _read_values(HIVES[hive_name], key):
            if not name:
                continue
            items.append(StartupItem(name, str(cmd), label, hive_name, sub, name,
                                     _approved_state(hive_name, sub, name), hive_name == "HKLM"))
    folders = (("HKCU", os.path.join(env("APPDATA"), r"Microsoft\Windows\Start Menu\Programs\Startup"),
                "Cartella Esecuzione automatica (utente)"),
               ("HKLM", os.path.join(env("ProgramData"), r"Microsoft\Windows\Start Menu\Programs\StartUp"),
                "Cartella Esecuzione automatica (tutti)"))
    for hive_name, folder, label in folders:
        if not os.path.isdir(folder):
            continue
        for fn in os.listdir(folder):
            if fn.lower() == "desktop.ini":
                continue
            items.append(StartupItem(os.path.splitext(fn)[0], os.path.join(folder, fn), label, hive_name,
                                     "StartupFolder", fn, _approved_state(hive_name, "StartupFolder", fn),
                                     hive_name == "HKLM"))
    items.sort(key=lambda i: i.name.lower())
    return items


def set_enabled(item: StartupItem, enabled: bool) -> None:
    """Solleva PermissionError se servono i diritti di amministratore."""
    if enabled:
        data = b"\x02" + b"\x00" * 11
    else:
        ft = int((time.time() + 11644473600) * 10_000_000)  # FILETIME, come Gestione attività
        data = b"\x03\x00\x00\x00" + struct.pack("<Q", ft)
    with winreg.CreateKeyEx(HIVES[item.hive], APPROVED + "\\" + item.approved_sub, 0,
                            winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY) as k:
        winreg.SetValueEx(k, item.value_name, 0, winreg.REG_BINARY, data)
    item.enabled = enabled
    log(f"Avvio automatico: {item.name} -> {'attivato' if enabled else 'disattivato'}")
