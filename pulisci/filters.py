"""Filtri per file e cartelle: nome, estensione, tipo, data di modifica, dimensione minima."""
from __future__ import annotations

import fnmatch
import os
import re
import time
from dataclasses import dataclass

MB = 1024 ** 2
GB = 1024 ** 3

KINDS = {"Tutti": "all", "Solo file": "files", "Solo cartelle": "dirs"}
# etichetta -> (modificato entro N giorni, modificato prima di N giorni)
MODIFIED = {
    "Qualsiasi": (None, None),
    "Ultimi 7 giorni": (7, None),
    "Ultimo mese": (30, None),
    "Ultimo anno": (365, None),
    "Più vecchi di 1 anno": (None, 365),
    "Più vecchi di 3 anni": (None, 3 * 365),
}
SIZES = {"Qualsiasi": 0, "Da 1 MB": MB, "Da 10 MB": 10 * MB, "Da 100 MB": 100 * MB, "Da 1 GB": GB}
SORTS = {"Dimensione (più grandi)": "size", "Nome (A-Z)": "name", "Data (più recenti)": "date"}


@dataclass
class Filters:
    text: str = ""                       # parte del nome; con * o ? diventa un jolly (es. *.pdf)
    exts: frozenset = frozenset()        # estensioni senza punto, in minuscolo
    kind: str = "all"                    # all | files | dirs
    newer_days: float | None = None      # modificato negli ultimi N giorni
    older_days: float | None = None      # modificato più di N giorni fa
    min_size: int = 0

    def match(self, name: str, is_dir: bool, size: int, mtime: float) -> bool:
        if (self.kind == "files" and is_dir) or (self.kind == "dirs" and not is_dir):
            return False
        if size < self.min_size:
            return False
        if self.text:
            low, pattern = name.lower(), self.text.lower()
            if not fnmatch.fnmatchcase(low, pattern if ("*" in pattern or "?" in pattern) else f"*{pattern}*"):
                return False
        if self.exts:
            if is_dir or os.path.splitext(name)[1][1:].lower() not in self.exts:
                return False
        if self.newer_days is not None or self.older_days is not None:
            now = time.time()
            if self.newer_days is not None and mtime < now - self.newer_days * 86400:
                return False
            if self.older_days is not None and mtime > now - self.older_days * 86400:
                return False
        return True

    @property
    def active(self) -> bool:
        return bool(self.text or self.exts or self.kind != "all" or self.newer_days is not None
                    or self.older_days is not None or self.min_size)


def parse_exts(raw: str) -> frozenset:
    """'jpg, .PNG mp4' -> {'jpg', 'png', 'mp4'}"""
    parts = (p.strip().lstrip(".").lower() for p in re.split(r"[,;\s]+", raw or ""))
    return frozenset(p for p in parts if p)


def sort_entries(entries: list[dict], key: str) -> list[dict]:
    """Ordina elementi con chiavi name/size/mtime/dir. Con «nome» le cartelle stanno in cima."""
    if key == "name":
        return sorted(entries, key=lambda e: (not e["dir"], e["name"].lower()))
    if key == "date":
        return sorted(entries, key=lambda e: e["mtime"], reverse=True)
    return sorted(entries, key=lambda e: e["size"], reverse=True)
