"""Finestre secondarie: Informazioni e visualizzatore di testo (licenza, componenti di terze parti)."""
from __future__ import annotations

import os
import sys
import webbrowser

import customtkinter as ctk

from . import ui
from .ui import FONT, SURFACE, SURFACE_ALT, TEXT, button, label, logo
from .utils import APP_NAME, APP_SITE, APP_VERSION, data_dir, open_in_explorer

SHORTCUTS = (("Ctrl+1 … Ctrl+5", "Vai alla pagina"), ("F5", "Analizza / Aggiorna"), ("Esc", "Annulla l'operazione"),
             ("Ctrl+B", "Comprimi la barra laterale"), ("F1", "Informazioni"), ("Tab", "Passa al controllo successivo"))


def find_doc(*parts: str) -> str | None:
    """Cerca un file di documentazione: accanto all'exe (app installata), nel pacchetto PyInstaller o nel progetto."""
    roots = []
    if getattr(sys, "frozen", False):
        roots.append(os.path.dirname(sys.executable))
        roots.append(getattr(sys, "_MEIPASS", ""))
    roots.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for r in roots:
        if r:
            p = os.path.join(r, *parts)
            if os.path.isfile(p):
                return p
    return None


class _Dialog(ctk.CTkToplevel):
    def __init__(self, app, title: str, w: int, h: int, resizable: bool = False):
        super().__init__(app)
        self.app = app
        self.title(title)
        self.configure(fg_color=ui.BG)
        self.transient(app)
        self.resizable(resizable, resizable)   # una sola volta: due chiamate ravvicinate lasciano la finestra nascosta
        k = ctk.ScalingTracker.get_widget_scaling(self)
        x = app.winfo_rootx() + max(0, (app.winfo_width() - int(w * k)) // 2)
        y = app.winfo_rooty() + max(0, (app.winfo_height() - int(h * k)) // 3)
        self.geometry(f"{w}x{h}+{x}+{y}")
        # CustomTkinter reimposta l'icona dopo ~200 ms: la rimettiamo dopo
        self.after(250, self._icon)
        self.bind("<Escape>", lambda e: self.close())
        self.protocol("WM_DELETE_WINDOW", self.close)

    def _icon(self):
        try:
            self.iconbitmap(ui.resource("icon.ico"))
        except Exception:
            pass

    def make_modal(self):
        ui.a11y_pass(self)
        self.after(120, self._grab)

    def _grab(self):
        try:
            self.lift()
            self.focus_force()
            self.grab_set()
        except Exception:
            pass

    def close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()


class TextViewer(_Dialog):
    def __init__(self, app, title: str, path: str | None):
        super().__init__(app, title, 760, 560, resizable=True)
        self.minsize(520, 380)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        box = ctk.CTkTextbox(self, font=("Consolas", 12), fg_color=SURFACE, text_color=TEXT, corner_radius=10,
                             border_width=1, border_color=ui.BORDER, wrap="word")
        box.grid(row=0, column=0, sticky="nsew", padx=18, pady=(18, 10))
        text = None
        if path:
            try:
                with open(path, encoding="utf-8-sig") as f:
                    text = f.read()
            except OSError:
                text = None
        box.insert("1.0", text or "Impossibile trovare questo documento.\n\nSe hai installato PC Cleaner, "
                                  "reinstallalo oppure leggi i file nella cartella del programma.")
        box.configure(state="disabled")
        b = button(self, "Chiudi", None, "primary", self.close, width=120)
        b.grid(row=1, column=0, sticky="e", padx=18, pady=(0, 18))
        self.make_modal()


class AboutDialog(_Dialog):
    def __init__(self, app):
        super().__init__(app, f"Informazioni su {APP_NAME}", 560, 720)
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=28, pady=(24, 18))
        ctk.CTkLabel(f, text="", image=logo(72)).pack()
        ctk.CTkLabel(f, text=APP_NAME, font=(FONT, 24, "bold"), text_color=TEXT).pack(pady=(10, 0))
        label(f, f"Versione {APP_VERSION}", muted=True, anchor="center").pack()
        label(f, "© 2026 Cesa028 — Licenza MIT", anchor="center").pack(pady=(6, 10))
        label(f, "Libera spazio su Windows: elimina file temporanei e cache, mostra cosa occupa più spazio, "
                 "trova i file duplicati e gestisce i programmi in avvio automatico. "
                 "Prima di eliminare qualcosa vedi sempre cosa verrà tolto.",
              muted=True, wraplength=470, justify="center", anchor="center").pack()

        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(pady=(18, 4))
        button(row, "Licenza", "file", "secondary", self._license, width=210, height=34).grid(row=0, column=0, padx=5, pady=4)
        button(row, "Componenti di terze parti", "copy", "secondary", self._third, width=210, height=34).grid(
            row=0, column=1, padx=5, pady=4)
        button(row, "Sito del progetto", "open", "secondary", lambda: webbrowser.open(APP_SITE), width=210,
               height=34).grid(row=1, column=0, padx=5, pady=4)
        button(row, "Cartella dei dati", "open", "secondary", lambda: open_in_explorer(data_dir()), width=210,
               height=34).grid(row=1, column=1, padx=5, pady=4)

        sc = ctk.CTkFrame(f, fg_color=SURFACE_ALT, corner_radius=12)
        sc.pack(fill="x", pady=(14, 0))
        label(sc, "Scorciatoie da tastiera", size=12, bold=True).grid(row=0, column=0, columnspan=2, sticky="w",
                                                                       padx=16, pady=(10, 4))
        for i, (k, d) in enumerate(SHORTCUTS, start=1):
            label(sc, k, size=12, bold=True).grid(row=i, column=0, sticky="w", padx=(16, 14), pady=1)
            label(sc, d, size=12, muted=True).grid(row=i, column=1, sticky="w", pady=1)
        ctk.CTkFrame(sc, height=8, fg_color="transparent").grid(row=99, column=0)

        button(f, "Chiudi", None, "primary", self.close, width=130).pack(pady=(16, 0))
        self.make_modal()

    def _license(self):
        TextViewer(self.app, "Licenza", find_doc("LICENSE.txt"))

    def _third(self):
        TextViewer(self.app, "Componenti di terze parti", find_doc("licenses", "THIRD-PARTY-NOTICES.txt"))
