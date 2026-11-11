"""Impostazioni dell'utente: file JSON nella cartella dati dell'app (scrittura atomica, errori ignorati)."""
from __future__ import annotations

import json
import os

from .utils import data_dir

THEMES = ("Chiaro", "Scuro", "Sistema")
DEFAULTS = {
    "theme": "Sistema",        # Chiaro / Scuro / Sistema
    "window": None,            # {"w", "h", "x", "y", "zoomed"}
    "sidebar_collapsed": False,
    "page": "home",
    "space_target": "",        # ultimo disco o cartella scelto in Analisi spazio
}


class Settings:
    def __init__(self, path: str | None = None):
        self.path = path or os.path.join(data_dir(), "impostazioni.json")
        self.data = dict(DEFAULTS)
        try:
            with open(self.path, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                for k in DEFAULTS:
                    if k in loaded:
                        self.data[k] = loaded[k]
        except (OSError, ValueError):
            pass
        if self.data["theme"] not in THEMES:
            self.data["theme"] = DEFAULTS["theme"]

    def get(self, key: str):
        return self.data.get(key, DEFAULTS.get(key))

    def set(self, key: str, value, save: bool = True) -> None:
        if self.data.get(key) == value:
            return
        self.data[key] = value
        if save:
            self.save()

    def save(self) -> None:
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)   # atomico: il file non resta mai a meta'
        except OSError:
            pass
