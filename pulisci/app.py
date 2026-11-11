"""Interfaccia grafica di PC Cleaner: barra laterale e una pagina per funzione (create al primo utilizzo)."""
from __future__ import annotations

import ctypes
import datetime as dt
import os
import queue
import re
import threading
import tkinter as tk
import traceback
from tkinter import filedialog, messagebox

import customtkinter as ctk
from send2trash import send2trash

from . import analyzer, cleaner, duplicates, startup, ui
from .dialogs import AboutDialog
from .filters import Filters, sort_entries
from .settings import THEMES, Settings
from .ui import (ACCENT, ACCENT_HOVER, BAR_DANGER, BAR_OK, BAR_WARN, BG, BORDER, FONT, HOVER, MUTED, NAV_SEL,
                 NAV_SEL_TEXT, OK, SURFACE, SURFACE_ALT, TEXT, WARN, Card, EmptyState, FilterBar, FlowBar, Tooltip,
                 button, icon, label, logo, make_tree, option_menu, page_header, pct_text, segmented)
from .utils import (APP_NAME, APP_VERSION, data_dir, empty_recycle_bin, env, explain_error, fmt_size, is_admin,
                    list_drives, log, open_cleanmgr_admin, open_in_explorer, protected_path, recycle_bin_info,
                    relaunch_as_admin, running_processes, system_prefers_light)

NAV = (("home", "Panoramica", "home"), ("clean", "Pulizia", "clean"), ("space", "Analisi spazio", "analyze"),
       ("dups", "Duplicati", "copy"), ("startup", "Avvio automatico", "power"))


class App(ctk.CTk):
    def __init__(self, settings: Settings | None = None):
        super().__init__()
        self.settings = settings or Settings()
        self.title(f"{APP_NAME} {APP_VERSION}" + ("  —  Amministratore" if is_admin() else ""))
        self.minsize(720, 560)
        self._normal_geo: dict | None = None
        self._restore_geometry()
        self._about = None
        self._narrow = False
        self._collapse_pref = bool(self.settings.get("sidebar_collapsed"))
        self._collapsed = False
        self.bind("<Configure>", self._on_resize)
        self.configure(fg_color=BG)
        try:
            self.iconbitmap(ui.resource("icon.ico"))
        except Exception:
            pass
        ui.set_scale(self.winfo_fpixels("1i") / 96.0)
        ui.set_font_scale(ctk.ScalingTracker.get_widget_scaling(self))
        ui.install_wheel(self)

        self._ui_q: queue.Queue = queue.Queue()
        self.after(60, self._drain_ui)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew", padx=28, pady=24)
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)
        self._page_cls = {"home": HomePage, "clean": CleanPage, "space": SpacePage, "dups": DupPage,
                          "startup": StartupPage}
        self._pages: dict[str, Page] = {}
        self._current: str | None = None
        ui.style_trees(self)
        self._apply_collapsed()
        page = self.settings.get("page")
        self.show(page if page in self._page_cls else "home")
        self._bind_keys()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(2500, self._poll_system_theme)

    # ---------------------------------------------------------------- thread → interfaccia
    def ui(self, fn, *args):
        """Esegue fn nel thread dell'interfaccia (chiamabile da qualsiasi thread)."""
        self._ui_q.put((fn, args))

    def _drain_ui(self):
        try:
            while True:
                fn, args = self._ui_q.get_nowait()
                try:
                    fn(*args)
                except Exception:
                    traceback.print_exc()
        except queue.Empty:
            pass
        self.after(60, self._drain_ui)

    def set_text(self, widget, text: str):
        self.ui(lambda: widget.configure(text=text))

    def run_bg(self, work, done=None, error=None):
        def worker():
            try:
                res = work()
            except Exception as ex:
                log("ERRORE: " + traceback.format_exc())
                self.ui(error or (lambda e: self.error_box("Non è stato possibile completare l'operazione.", e)), ex)
                return
            if done:
                self.ui(done, res)
        threading.Thread(target=worker, daemon=True).start()

    def error_box(self, what: str, ex: BaseException) -> None:
        """Errore comprensibile per l'utente; il dettaglio tecnico va nel registro attività."""
        log(f"ERRORE ({what}): {ex!r}")
        messagebox.showerror(APP_NAME, f"{what}\n\n{explain_error(ex)}\n\n"
                                       "I dettagli tecnici sono nel registro attività (pulsante in basso a sinistra).")

    # ---------------------------------------------------------------- finestra
    def _geo_dict(self) -> dict | None:
        nums = [int(n) for n in re.findall(r"-?\d+", self.geometry())]
        return dict(zip(("w", "h", "x", "y"), nums)) if len(nums) == 4 else None

    def _restore_geometry(self) -> None:
        """Ripristina dimensione e posizione salvate, tenendo la finestra dentro lo schermo."""
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        g = self.settings.get("window")
        try:
            w, h, x, y = (int(g[k]) for k in ("w", "h", "x", "y"))
        except (TypeError, KeyError, ValueError):
            # prima apertura: 85% dello schermo, al massimo 1280x840
            self._center(min(1280, int(sw * 0.85)), min(840, int(sh * 0.85)))
            return
        try:
            gm = ctypes.windll.user32.GetSystemMetrics   # area di tutti i monitor
            vx, vy, vw, vh = gm(76), gm(77), gm(78), gm(79)
        except Exception:
            vx, vy, vw, vh = 0, 0, sw, sh
        if vw <= 0 or vh <= 0:
            vx, vy, vw, vh = 0, 0, sw, sh
        k = ctk.ScalingTracker.get_window_scaling(self)
        w, h = max(720, min(w, int((vw - 40) / k))), max(560, min(h, int((vh - 80) / k)))
        x = min(max(x, vx - int(w * k) + 120), vx + vw - 120)   # almeno 120 px della barra del titolo visibili
        y = min(max(y, vy), vy + vh - 80)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self._normal_geo = {"w": w, "h": h, "x": x, "y": y}
        if g.get("zoomed"):
            self.after(60, lambda: self.state("zoomed"))

    def _save_window(self) -> None:
        try:
            zoomed = self.state() == "zoomed"
            geo = self._normal_geo if zoomed else self._geo_dict()
            if geo:
                self.settings.set("window", dict(geo, zoomed=zoomed), save=False)
            self.settings.save()
        except tk.TclError:
            pass

    def _on_close(self) -> None:
        self._save_window()
        self.destroy()

    # ---------------------------------------------------------------- tastiera
    def _bind_keys(self) -> None:
        for i, (key, _, _) in enumerate(NAV, start=1):
            self.bind_all(f"<Control-Key-{i}>", lambda e, k=key: self._shortcut(lambda: self.show(k)))
        self.bind_all("<F5>", lambda e: self._shortcut(lambda: self._pages[self._current].refresh()))
        self.bind_all("<Escape>", lambda e: self._shortcut(lambda: self._pages[self._current].cancel()))
        self.bind_all("<F1>", lambda e: self._shortcut(self.show_about))
        self.bind_all("<Control-b>", lambda e: self._shortcut(self._toggle_collapse, typing_ok=False))

    def _shortcut(self, fn, typing_ok: bool = True):
        """Esegue una scorciatoia solo se la finestra principale e' attiva (non una finestra di dialogo)."""
        try:
            w = self.focus_get()
        except (KeyError, tk.TclError):
            w = None
        if w is not None and w.winfo_toplevel() is not self:
            return None
        if not typing_ok and w is not None and w.winfo_class() in ("Entry", "Text"):
            return None
        fn()
        return "break"

    def show_about(self) -> None:
        if self._about is not None and self._about.winfo_exists():
            self._about.lift()
            return
        self._about = AboutDialog(self)

    def _center(self, w: int, h: int) -> None:
        """Apre la finestra al centro dello schermo (senza uscire dallo schermo)."""
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(w, sw - 80), min(h, sh - 120)
        x, y = (sw - w) // 2, max(0, (sh - h) // 2 - 20)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _on_resize(self, event):
        if event.widget is not self:
            return
        if self.state() == "normal":
            self._normal_geo = self._geo_dict() or self._normal_geo
        self._narrow = event.width < 1000
        self._apply_collapsed()

    def _apply_collapsed(self, force: bool = False) -> None:
        want = self._collapse_pref or self._narrow
        if want != self._collapsed or force:
            self._collapsed = want
            self._set_collapsed(want)

    def _toggle_collapse(self) -> None:
        self._collapse_pref = not self._collapse_pref
        self.settings.set("sidebar_collapsed", self._collapse_pref)
        self._nav_text["collapse"] = "  Espandi barra" if self._collapse_pref else "  Comprimi barra"
        self._apply_collapsed(force=True)

    def _set_collapsed(self, collapsed: bool) -> None:
        """Barra laterale ridotta alle sole icone quando la finestra è stretta."""
        self.sidebar.configure(width=68 if collapsed else 220)
        for name in (self._brand_name, self._brand_ver):
            name.grid_remove() if collapsed else name.grid()
        self.brand.grid_configure(padx=(16 if collapsed else 20), pady=(22, 26))
        for key, b in {**self.nav, **self._foot}.items():
            b.configure(text="" if collapsed else self._nav_text[key], width=40 if collapsed else 192,
                        compound="top" if collapsed else "left", anchor="center" if collapsed else "w")
        for box in (self.admin_box, self.bottom_box):
            box.grid_remove() if collapsed else box.grid()

    # ---------------------------------------------------------------- barra laterale
    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=SURFACE, border_width=0)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_propagate(False)
        sb.grid_columnconfigure(0, weight=1)
        sb.grid_rowconfigure(6, weight=1)

        brand = ctk.CTkFrame(sb, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="w", padx=20, pady=(22, 26))
        ctk.CTkLabel(brand, text="", image=logo(36)).grid(row=0, column=0, rowspan=2, padx=(0, 12))
        self.sidebar = sb
        self._brand_name = ctk.CTkLabel(brand, text=APP_NAME, font=(FONT, 16, "bold"), text_color=TEXT)
        self._brand_name.grid(row=0, column=1, sticky="sw")
        self._brand_ver = ctk.CTkLabel(brand, text=f"Versione {APP_VERSION}", font=(FONT, 11), text_color=MUTED)
        self._brand_ver.grid(row=1, column=1, sticky="nw")
        self.brand = brand

        self.nav: dict[str, ctk.CTkButton] = {}
        self._nav_text: dict[str, str] = {}
        for i, (key, text, ic) in enumerate(NAV):
            b = ctk.CTkButton(sb, text=f"  {text}", image=icon(ic, size=18), compound="left", anchor="w", height=38,
                              corner_radius=10, font=(FONT, 13), fg_color="transparent", text_color=TEXT,
                              hover_color=HOVER, command=lambda k=key: self.show(k), width=192)
            b.grid(row=1 + i, column=0, sticky="ew", padx=14, pady=3)
            self.nav[key] = b
            self._nav_text[key] = f"  {text}"
            Tooltip(b, f"{text} (Ctrl+{i + 1})")

        admin = ctk.CTkFrame(sb, fg_color=BG, corner_radius=12)
        self.admin_box = admin
        admin.grid(row=7, column=0, sticky="ew", padx=14, pady=(8, 10))
        if is_admin():
            ctk.CTkLabel(admin, text="  Modalità amministratore", image=icon("shield", on_accent=False, size=18),
                         compound="left", font=(FONT, 12, "bold"), text_color=OK).pack(
                anchor="w", padx=14, pady=12)
        else:
            notice = label(admin, "Alcune pulizie di sistema richiedono i diritti di amministratore.", size=11,
                           muted=True, justify="left")
            notice.pack(anchor="w", padx=14, pady=(12, 8))
            admin_btn = button(admin, "Riavvia da admin", "shield", "secondary", self._elevate, width=170, height=32)
            admin_btn.pack(padx=12, pady=(0, 12))

            def fit_admin(e):
                """Testo e pulsante prendono la larghezza reale del riquadro, a qualsiasi scala di Windows."""
                k = ctk.ScalingTracker.get_widget_scaling(admin)   # CustomTkinter scala anche i margini
                # CustomTkinter moltiplica wraplength e width per la scala: i valori vanno in unità logiche
                notice.configure(wraplength=max(80, int((e.width - 2 * 14 * k - 6) / k)))
                admin_btn.configure(width=max(120, int((e.width - 2 * 12 * k - 4) / k)))
            tk.Frame.bind(admin, "<Configure>", fit_admin)

        bottom = ctk.CTkFrame(sb, fg_color="transparent")
        self.bottom_box = bottom
        bottom.grid(row=8, column=0, sticky="ew", padx=14, pady=(0, 10))
        self.theme = segmented(bottom, list(THEMES), self._set_theme, height=30, size=12)
        self.theme.set(self.settings.get("theme"))
        self.theme.pack(fill="x")
        for name, b in self.theme._buttons_dict.items():
            Tooltip(b, {"Sistema": "Segue il tema di Windows"}.get(name, f"Tema {name.lower()}"))
        button(bottom, "Apri registro attività", "file", "ghost", lambda: open_in_explorer(data_dir()),
               height=32).pack(fill="x", pady=(8, 0))

        self._foot: dict[str, ctk.CTkButton] = {}
        collapsed = self._collapse_pref
        for i, (key, text, ic, cmd, tip) in enumerate((
                ("about", "Informazioni", "info", self.show_about, "Informazioni (F1)"),
                ("collapse", "Espandi barra" if collapsed else "Comprimi barra", "menu", self._toggle_collapse,
                 lambda: ("Espandi" if self._collapse_pref else "Comprimi") + " la barra laterale (Ctrl+B)"))):
            b = ctk.CTkButton(sb, text=f"  {text}", image=icon(ic, size=18), compound="left", anchor="w", height=38,
                              corner_radius=10, font=(FONT, 13), fg_color="transparent", text_color=TEXT,
                              hover_color=HOVER, command=cmd, width=192)
            b.grid(row=9 + i, column=0, sticky="ew", padx=14, pady=(0, 3 if i == 0 else 14))
            self._foot[key] = b
            self._nav_text[key] = f"  {text}"
            Tooltip(b, tip)

    def _set_theme(self, value):
        self.settings.set("theme", value)
        self._apply_theme(force=True)

    def _apply_theme(self, force: bool = False):
        """Applica la preferenza (Chiaro / Scuro / Sistema); con «Sistema» segue il tema di Windows."""
        pref = self.settings.get("theme")
        mode = resolve_mode(pref)
        if force or ctk.get_appearance_mode().lower() != mode:
            ctk.set_appearance_mode(mode)
            ui.style_trees(self)

    def _poll_system_theme(self):
        if self.settings.get("theme") == "Sistema":
            self._apply_theme()
        self.after(2500, self._poll_system_theme)

    def _elevate(self):
        self._save_window()
        if relaunch_as_admin():
            self.destroy()

    def show(self, key: str) -> Page:
        if self._current and self._current != key:
            self._pages[self._current].grid_remove()
        if key not in self._pages:
            self._pages[key] = self._page_cls[key](self.content, self)
        page = self._pages[key]
        page.grid(row=0, column=0, sticky="nsew")
        for k, b in self.nav.items():
            selected = k == key
            b.configure(fg_color=NAV_SEL if selected else "transparent",
                        text_color=NAV_SEL_TEXT if selected else TEXT)
        self._current = key
        self.settings.set("page", key)
        page.on_show()
        ui.a11y_pass(self)
        return page


class Page(ctk.CTkFrame):
    """Base di tutte le pagine."""

    def __init__(self, master, app: App):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._width = -1
        tk.Frame.bind(self, "<Configure>", self._on_configure)   # bind() di CTk agirebbe sul canvas interno

    def _on_configure(self, event):
        if event.widget is self and event.width != self._width and event.width > 1:
            self._width = event.width
            for child in self.winfo_children():   # sottotitoli delle intestazioni: vanno a capo
                sub = getattr(child, "_sub", None)
                if sub is not None:
                    sub.configure(wraplength=max(200, event.width - 60))
            self.layout(event.width)

    def layout(self, width: int) -> None:
        """Adatta la pagina alla larghezza disponibile (ogni pagina lo ridefinisce se serve)."""

    def on_show(self):
        pass

    def refresh(self) -> None:
        """F5: rifà l'azione principale della pagina (analizza o aggiorna)."""

    def cancel(self) -> None:
        """Esc: annulla l'operazione in corso, se c'è."""


def _card_title(parent, text: str, ic: str) -> None:
    ctk.CTkLabel(parent, text=f"  {text}", image=icon(ic, size=20), compound="left", font=(FONT, 16, "bold"),
                 text_color=TEXT).pack(anchor="w", padx=20, pady=(18, 6))


# =====================================================================================
class HomePage(Page):
    def __init__(self, master, app: App):
        super().__init__(master, app)
        for c in range(3):
            self.grid_columnconfigure(c, weight=1)
        page_header(self, "Panoramica", "Stato del PC e le azioni più utili.").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 18))

        self.drives = Card(self)
        self.drives.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 14))

        self._tiles: list = []
        self._tile_labels: list = []
        quick = self._quick = Card(self)
        quick.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=(0, 14))
        _card_title(quick, "Pulizia rapida", "clean")
        label(quick, "Trova file temporanei, cache di browser e programmi. Prima vedi cosa verrà eliminato, "
                     "poi decidi tu.", muted=True, wraplength=400, justify="left").pack(anchor="w", padx=20)
        row = FlowBar(quick)
        button(row, "Analizza ora", "search", "primary", self._quick_clean, height=42, width=200).pack(side="left")
        button(row, "Pulizia disco di Windows", "settings", "secondary", self._disk_cleanup, height=42,
               width=270).pack(side="left", padx=10)
        row.pack(fill="x", padx=20, pady=20)

        rb = self._rb = Card(self)
        rb.grid(row=2, column=2, sticky="nsew")
        _card_title(rb, "Cestino", "trash")
        self.rb_lbl = label(rb, "…", muted=True, wraplength=260, justify="left")
        self.rb_lbl.pack(anchor="w", padx=20)
        self.rb_btn = button(rb, "Svuota cestino", "trash", "danger", self._empty_rb, height=42, width=200)
        self.rb_btn.pack(anchor="w", padx=20, pady=20)

        tiles = (("space", "Analisi spazio", "Trova le cartelle e i file che occupano più spazio.", "analyze"),
                 ("dups", "Duplicati", "Trova file identici e libera spazio senza perdere nulla.", "copy"),
                 ("startup", "Avvio automatico", "Scegli quali programmi partono con Windows.", "power"))
        for i, (key, title, desc, ic) in enumerate(tiles):
            t = Card(self)
            self._tiles.append(t)
            t.grid(row=3, column=i, sticky="nsew", padx=(0 if i == 0 else 14, 0), pady=(14, 0))
            _card_title(t, title, ic)
            self._tile_labels.append(label(t, desc, muted=True, justify="left"))
            self._tile_labels[-1].pack(anchor="w", padx=20)
            button(t, "Apri", None, "secondary", lambda k=key: self.app.show(k), height=36, width=120).pack(
                anchor="w", padx=20, pady=16)

    def layout(self, width: int) -> None:
        narrow = width < 860
        if narrow:  # finestra stretta: tutto in una colonna
            self._quick.grid_configure(row=2, column=0, columnspan=3, padx=0)
            self._rb.grid_configure(row=3, column=0, columnspan=3, padx=0, pady=(14, 0))
            for i, t in enumerate(self._tiles):
                t.grid_configure(row=4 + i, column=0, columnspan=3, padx=0, pady=(14, 0))
        else:
            self._quick.grid_configure(row=2, column=0, columnspan=2, padx=(0, 14), pady=0)
            self._rb.grid_configure(row=2, column=2, columnspan=1, padx=0, pady=0)
            for i, t in enumerate(self._tiles):
                t.grid_configure(row=3, column=i, columnspan=1, padx=(0 if i == 0 else 14, 0), pady=(14, 0))
        for lbl in self._tile_labels:
            lbl.configure(wraplength=max(180, (width if narrow else width // 3) - 90))

    def on_show(self):
        for w in self.drives.winfo_children():
            w.destroy()
        label(self.drives, "Dischi", size=16, bold=True).grid(row=0, column=0, columnspan=3, sticky="w",
                                                              padx=20, pady=(16, 8))
        self.drives.grid_columnconfigure(1, weight=1)
        drives = list_drives()
        for i, d in enumerate(drives, start=1):
            last = i == len(drives)
            frac = d["used"] / d["total"] if d["total"] else 0
            color = BAR_DANGER if frac > 0.9 else BAR_WARN if frac > 0.75 else BAR_OK
            pady = (6, 20 if last else 6)   # l'ultima riga ha più spazio sotto: non resta a ridosso del bordo
            label(self.drives, f"{d['root'][:2]}  {d['label']}", bold=True).grid(
                row=i, column=0, sticky="w", padx=(20, 12), pady=pady)
            pb = ctk.CTkProgressBar(self.drives, height=10, corner_radius=5, progress_color=color, fg_color=HOVER)
            pb.set(frac)
            pb.grid(row=i, column=1, sticky="ew", padx=8, pady=pady)
            label(self.drives, f"{fmt_size(d['free'])} liberi di {fmt_size(d['total'])}", muted=True).grid(
                row=i, column=2, sticky="e", padx=(8, 20), pady=pady)
        if not drives:
            label(self.drives, "Nessun disco trovato.", muted=True).grid(row=1, column=0, columnspan=3, sticky="w",
                                                                         padx=20, pady=(0, 20))
        size, n = recycle_bin_info()
        self.rb_lbl.configure(text=f"{n} elementi · {fmt_size(size)}" if n else "Il cestino è vuoto.")
        self.rb_btn.configure(state="normal" if n else "disabled")

    def refresh(self):
        self.on_show()

    def _quick_clean(self):
        self.app.show("clean").scan()

    def _disk_cleanup(self):
        open_cleanmgr_admin()

    def _empty_rb(self):
        size, n = recycle_bin_info()
        if not messagebox.askyesno(APP_NAME, f"Svuotare definitivamente il cestino?\n{n} elementi, {fmt_size(size)}."):
            return
        self.rb_btn.configure(state="disabled", text="Svuotamento…")

        def done(_):
            self.rb_btn.configure(text="Svuota cestino")
            self.on_show()
        self.app.run_bg(empty_recycle_bin, done)


# =====================================================================================
class CleanPage(Page):
    def __init__(self, master, app: App):
        super().__init__(master, app)
        self.cats = cleaner.build_categories()
        self.results: dict[str, cleaner.ScanResult] = {}
        self.vars: dict[str, ctk.BooleanVar] = {}
        self.size_lbls: dict[str, ctk.CTkLabel] = {}
        self.note_lbls: dict[str, ctk.CTkLabel] = {}
        self._groups: list = []
        self._card_labels: list = []
        self.busy = False
        self.cancel_flag = False
        self.admin = is_admin()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        page_header(self, "Pulizia", "Analizza, scegli cosa eliminare e pulisci. Prima vedi quanto spazio "
                                     "puoi recuperare.").grid(row=0, column=0, sticky="w", pady=(0, 16))

        bar = Card(self)
        bar.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        inner = FlowBar(bar)
        inner.pack(fill="x", padx=16, pady=14)
        self.scan_btn = button(inner, "Analizza", "search", "primary", self.scan, width=140)
        self.scan_btn.pack(side="left")
        Tooltip(self.scan_btn, "Analizza il PC (F5)")
        self.clean_btn = button(inner, "Pulisci selezionati", "clean", "danger", self.clean, width=200,
                                state="disabled")
        self.clean_btn.pack(side="left", padx=10)
        Tooltip(self.clean_btn, lambda: "" if str(self.clean_btn.cget("state")) == "normal" else
                ("Operazione in corso" if self.busy else "Prima premi «Analizza» e scegli cosa pulire"))
        self.cancel_btn = button(inner, "Annulla", "stop", "secondary", self._cancel, width=110)
        Tooltip(self.cancel_btn, "Annulla (Esc)")
        self.preset = segmented(inner, ["Consigliati", "Tutti", "Nessuno"], self._preset, height=34)
        self.preset.set("Consigliati")
        self.preset.pack(side="right")
        self.total = label(inner, "", size=18, bold=True)
        self.total.pack(side="right", padx=18)

        self.list = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list.grid(row=2, column=0, sticky="nsew")
        self.list.grid_columnconfigure(0, weight=1)
        self._build_cards()

        foot = FlowBar(self)
        foot.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        self.status = label(foot, "Premi «Analizza» per vedere quanto spazio puoi recuperare.", muted=True)
        self.status.pack(side="left")
        self.progress = ctk.CTkProgressBar(self, height=6, mode="determinate")   # il totale e' noto: progresso reale

    def refresh(self):
        self.scan()

    def cancel(self):
        if self.busy:
            self._cancel()

    def _build_cards(self):
        groups: dict[str, list[cleaner.Category]] = {}
        for c in self.cats:
            groups.setdefault(c.group, []).append(c)
        row = 0
        for gname, items in groups.items():
            label(self.list, gname.upper(), size=11, bold=True, muted=True).grid(
                row=row, column=0, sticky="w", padx=6, pady=(16 if row else 0, 6))
            row += 1
            sub = ctk.CTkFrame(self.list, fg_color="transparent")
            sub.grid(row=row, column=0, sticky="ew")
            cards = [self._card(sub, c) for c in items]
            self._groups.append((sub, cards))
            row += 1
        self._cols = 0
        self._reflow(2)

    def _track(self, w):
        """Ricorda le etichette che devono andare a capo in base alla larghezza."""
        self._card_labels.append(w)
        return w

    def layout(self, width: int) -> None:
        cols = 1 if width < 900 else 2
        self._reflow(cols)
        wrap = max(180, width // cols - 110)
        for w in self._card_labels:
            w.configure(wraplength=wrap)

    def _reflow(self, cols: int):
        """Dispone le schede su una o due colonne, secondo la larghezza della finestra."""
        if cols == self._cols:
            return
        self._cols = cols
        for sub, cards in self._groups:
            for c in range(2):
                sub.grid_columnconfigure(c, weight=1 if c < cols else 0, uniform="cards" if cols == 2 else "")
            for i, card in enumerate(cards):
                card.grid_configure(row=i // cols, column=i % cols)

    def _card(self, parent, c: cleaner.Category):
        locked = c.admin and not self.admin
        v = ctk.BooleanVar(value=c.default and not locked)
        self.vars[c.id] = v
        card = Card(parent)
        card.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(14, 0))
        ctk.CTkCheckBox(top, text=c.name, variable=v, font=(FONT, 14, "bold"), text_color=TEXT,
                        fg_color=ACCENT, hover_color=ACCENT_HOVER, border_color=MUTED, checkmark_color="#ffffff",
                        command=self._update_total, state="disabled" if locked else "normal").pack(side="left")
        self.size_lbls[c.id] = label(top, "—", size=14, bold=True, muted=True)
        self.size_lbls[c.id].pack(side="right")
        desc = c.desc + ("  ·  richiede amministratore" if locked else "")
        self._track(label(card, desc, size=12, muted=True, justify="left")).pack(anchor="w", padx=(46, 16),
                                                                                    pady=(4, 0))
        self.note_lbls[c.id] = self._track(label(card, "", size=12, text_color=WARN, justify="left"))
        self.note_lbls[c.id].pack(anchor="w", padx=(46, 16), pady=(2, 12))
        return card

    def _preset(self, value: str):
        for c in self.cats:
            locked = c.admin and not self.admin
            wanted = {"Consigliati": c.default, "Tutti": True, "Nessuno": False}[value]
            self.vars[c.id].set(bool(wanted) and not locked)
        self._update_total()

    def _selected(self):
        return [c for c in self.cats if self.vars[c.id].get()]

    def _update_total(self):
        if not self.results:
            self.total.configure(text="")
            return
        tot = sum(self.results[c.id].size for c in self._selected() if c.id in self.results)
        self.total.configure(text=f"Da liberare: {fmt_size(tot)}")
        self.clean_btn.configure(state="normal" if tot and not self.busy else "disabled")

    def _set_busy(self, busy: bool):
        self.busy = busy
        self.scan_btn.configure(state="disabled" if busy else "normal")
        if busy:
            self.clean_btn.configure(state="disabled")
            self.cancel_btn.pack(side="left", padx=10)
            self.progress.configure(mode="determinate")
            self.progress.set(0)
            self.progress.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        else:
            ui.hide(self.cancel_btn)
            self.progress.stop()
            self.progress.grid_forget()
            self._update_total()

    def _cancel(self):
        self.cancel_flag = True
        self.status.configure(text="Annullamento in corso…")

    # ------------------------------------------------------------ scansione
    def scan(self):
        if self.busy:
            return
        self.cancel_flag = False
        self._set_busy(True)
        cats = list(self.cats)
        for c in cats:
            self.size_lbls[c.id].configure(text="…", text_color=MUTED)
            self.note_lbls[c.id].configure(text="")

        def work():
            procs = running_processes()
            out = {}
            for i, c in enumerate(cats):
                if self.cancel_flag:
                    break
                self.app.set_text(self.status, f"Analizzo: {c.name} ({i + 1} di {len(cats)})…")
                self.app.ui(self.progress.set, i / len(cats))
                if c.admin and not self.admin:
                    out[c.id] = None
                    continue
                res = cleaner.scan_category(c, lambda: self.cancel_flag)
                if any(p in procs for p in c.procs) and res.size:
                    res.note = f"Chiudi {c.name} per pulire tutto"
                out[c.id] = res
                self.app.ui(self._show_result, c.id, res)
            return out

        def done(out):
            self.results = {k: v for k, v in out.items() if v is not None}
            for c in self.cats:
                if out.get(c.id) is None:
                    self.size_lbls[c.id].configure(text="—")
            tot = sum(r.size for r in self.results.values())
            self.status.configure(text=("Analisi annullata." if self.cancel_flag else
                                        f"Analisi completata: trovati {fmt_size(tot)} in totale."))
            self._set_busy(False)

        self.app.set_text(self.status, "Analisi in corso…")
        self.app.run_bg(work, done, lambda e: (self._set_busy(False), self.app.error_box(
            "Non è stato possibile analizzare il PC.", e)))

    def _show_result(self, cid: str, res: cleaner.ScanResult):
        self.size_lbls[cid].configure(text=fmt_size(res.size) if res.size else "0",
                                      text_color=TEXT if res.size else MUTED)
        if res.note:
            self.note_lbls[cid].configure(text=res.note)

    # ------------------------------------------------------------ pulizia
    def clean(self):
        sel = [self.results[c.id] for c in self._selected() if c.id in self.results and self.results[c.id].size]
        if not sel:
            return
        tot = sum(r.size for r in sel)
        n = sum(r.count for r in sel)
        names = "\n".join(f"  • {r.cat.name}: {fmt_size(r.size)}" for r in sel)
        if not messagebox.askyesno(APP_NAME, f"Eliminare definitivamente {n} file ({fmt_size(tot)})?\n\n{names}\n\n"
                                             "I file in uso verranno saltati."):
            return
        self.cancel_flag = False
        self._set_busy(True)

        def work():
            freed = deleted = skipped = 0
            for i, r in enumerate(sel):
                if self.cancel_flag:
                    break
                self.app.set_text(self.status, f"Pulisco: {r.cat.name} ({i + 1} di {len(sel)})…")
                self.app.ui(self.progress.set, i / len(sel))
                f, d, s = cleaner.clean_result(r, cancel=lambda: self.cancel_flag)
                freed += f
                deleted += d
                skipped += s
            return freed, deleted, skipped

        def done(res):
            freed, deleted, skipped = res
            self._set_busy(False)
            msg = f"Liberati {fmt_size(freed)} ({deleted} file eliminati)."
            if skipped:
                msg += f"\n{skipped} file erano in uso e sono stati lasciati."
            messagebox.showinfo(APP_NAME, msg)
            self.scan()

        self.app.run_bg(work, done, lambda e: (self._set_busy(False), self.app.error_box(
            "La pulizia non è andata a buon fine.", e)))


# =====================================================================================
class SpacePage(Page):
    def __init__(self, master, app: App):
        super().__init__(master, app)
        self.result: analyzer.AnalysisResult | None = None
        self.current: analyzer.DirNode | None = None
        self.entries: list[dict] = []
        self.cancel_flag = False
        self.busy = False
        self._targets: dict[str, str] = {}
        self._filters_open = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)
        page_header(self, "Analisi spazio", "Scopri quali cartelle e file occupano più spazio. Usa i filtri per "
                                            "trovare file per nome, estensione, data o dimensione.").grid(
            row=0, column=0, sticky="w", pady=(0, 16))

        bar = Card(self)
        bar.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        inner = FlowBar(bar)
        inner.pack(fill="x", padx=16, pady=12)
        self.target = option_menu(inner, ["…"], self._target_changed, width=300)
        self.target.pack(side="left")
        self.go_btn = button(inner, "Analizza", "search", "primary", self.start, width=130)
        self.go_btn.pack(side="left", padx=10)
        Tooltip(self.go_btn, "Analizza il disco o la cartella scelti (F5)")
        self.cancel_btn = button(inner, "Annulla", "stop", "secondary", self._cancel, width=110)
        Tooltip(self.cancel_btn, "Annulla (Esc)")
        self.filter_btn = button(inner, "Filtri", "filter", "secondary", self._toggle_filters, width=150)
        self.filter_btn.pack(side="right")
        self.view = segmented(inner, ["Cartelle", "File più grandi"], self._view_changed, height=36)
        self.view.set("Cartelle")
        self.view.pack(side="right", padx=10)

        self.filter_bar = FilterBar(self, on_change=self._render)  # mostrata con il pulsante «Filtri»

        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        self.up_btn = button(nav, "Su", "up", "ghost", self._up, width=90, height=32, state="disabled")
        self.up_btn.pack(side="left")
        self.path_lbl = label(nav, "", bold=True)
        self.path_lbl.pack(side="left", padx=10, fill="x", expand=True)
        self.info_lbl = label(nav, "", size=12, muted=True)
        self.info_lbl.pack(side="right")

        holder = Card(self)
        holder.grid(row=4, column=0, sticky="nsew")
        holder.grid_columnconfigure(0, weight=1)
        holder.grid_rowconfigure(0, weight=1)
        self.dir_tree = make_tree(holder, [("name", "Nome", 380, "w"), ("type", "Tipo", 120, "w"),
                                           ("size", "Dimensione", 110, "e"), ("pct", "Quota", 100, "e"),
                                           ("date", "Modificato", 120, "w")])
        self.big_tree = make_tree(holder, [("name", "Nome", 300, "w"), ("type", "Tipo", 100, "w"),
                                           ("size", "Dimensione", 110, "e"), ("folder", "Cartella", 330, "w"),
                                           ("date", "Modificato", 120, "w")])
        self.dir_tree.frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.empty = EmptyState(holder, "analyze")
        self.dir_tree.bind("<Double-1>", self._open_item)
        self.dir_tree.bind("<Return>", self._open_item)
        self.dir_tree.bind("<BackSpace>", lambda e: self._up())
        self.big_tree.bind("<Double-1>", lambda e: self._reveal())
        for t in (self.dir_tree, self.big_tree):
            t.bind("<Button-3>", self._context)
            t.bind("<Delete>", lambda e: self._trash())

        foot = FlowBar(self)
        foot.grid(row=5, column=0, sticky="ew", pady=(12, 0))
        self.status = label(foot, "Scegli un disco o una cartella e premi «Analizza».", muted=True)
        self.status.pack(side="left", fill="x", expand=True)
        button(foot, "Sposta nel cestino", "trash", "danger", self._trash, width=190).pack(side="right")
        button(foot, "Apri in Esplora file", "open", "secondary", self._reveal, width=190).pack(side="right", padx=10)
        self.progress = ctk.CTkProgressBar(self, height=6, mode="indeterminate")   # totale ignoto: barra indeterminata
        self._update_empty()

        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="Apri in Esplora file", command=self._reveal)
        self.menu.add_command(label="Copia percorso", command=self._copy_path)
        self.menu.add_separator()
        self.menu.add_command(label="Sposta nel cestino", command=self._trash)

    # ------------------------------------------------------------ destinazione e filtri
    def on_show(self):
        self._targets = {}
        for d in list_drives():
            self._targets[f"{d['root'][:2]}  {d['label']}  ({fmt_size(d['free'])} liberi)"] = d["root"]
        home = env("USERPROFILE")
        if home:
            self._targets[f"Cartella utente  ({os.path.basename(home)})"] = home
        saved = self.app.settings.get("space_target") or ""
        saved_key = next((k for k, v in self._targets.items()
                          if v and saved and os.path.normcase(v) == os.path.normcase(saved)), None)
        if saved and saved_key is None and os.path.isdir(saved):   # cartella scelta in una sessione precedente
            saved_key = os.path.normpath(saved)
            self._targets = {saved_key: saved, **self._targets}
        self._targets["Scegli cartella…"] = ""
        cur = self.target.get()
        self.target.configure(values=list(self._targets))
        if cur not in self._targets:
            self.target.set(saved_key or next(iter(self._targets)))

    def refresh(self):
        self.start()

    def cancel(self):
        if self.busy:
            self._cancel()

    def _update_empty(self):
        """Messaggio al posto della tabella quando non c'e' nulla da mostrare."""
        if self.busy:
            self.empty.show("Analisi in corso…", "Sto leggendo file e cartelle: può richiedere qualche minuto. "
                            "Puoi annullare in qualsiasi momento con Esc.")
        elif not self.result:
            self.empty.show("Nessuna analisi ancora", "Scegli un disco o una cartella in alto e premi «Analizza» (F5) "
                            "per scoprire cosa occupa più spazio.", "Analizza", self.start, action_icon="search")
        elif not self._active_tree().get_children():
            if self.filter_bar.filters().active:
                self.empty.show("Nessun elemento corrisponde ai filtri", "Prova a cambiare i filtri oppure azzerali "
                                "per vedere di nuovo tutto.", "Azzera filtri", self.filter_bar.reset,
                                action_icon="cancel")
            else:
                self.empty.show("Niente da mostrare qui", "Questa cartella è vuota o non è accessibile.", ic="info")
        else:
            self.empty.hide()

    def _target_changed(self, value):
        if self._targets.get(value):
            self.app.settings.set("space_target", self._targets[value])
        if self._targets.get(value) == "":
            path = filedialog.askdirectory(title="Scegli la cartella da analizzare")
            if path:
                label_ = os.path.normpath(path)
                self._targets = {label_: label_, **self._targets}
                self.target.configure(values=list(self._targets))
                self.target.set(label_)
                self.app.settings.set("space_target", label_)
            else:
                self.target.set(next(iter(self._targets)))

    def _toggle_filters(self):
        self._filters_open = not self._filters_open
        if self._filters_open:
            self.filter_bar.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        else:
            self.filter_bar.grid_remove()
        self._update_filter_btn()

    def _update_filter_btn(self):
        active = self.filter_bar.filters().active
        self.filter_btn.configure(text="Filtri (attivi)" if active else "Filtri",
                                  fg_color=NAV_SEL if self._filters_open else SURFACE_ALT,
                                  text_color=NAV_SEL_TEXT if self._filters_open else TEXT)

    # ------------------------------------------------------------ analisi
    def _cancel(self):
        self.cancel_flag = True

    def start(self):
        if self.busy:
            return
        root = self._targets.get(self.target.get())
        if not root:
            return
        self.busy = True
        self.cancel_flag = False
        self.app.settings.set("space_target", root)
        self.go_btn.configure(state="disabled")
        self.cancel_btn.pack(side="left", padx=10)
        for t in (self.dir_tree, self.big_tree):
            t.delete(*t.get_children())
        self.progress.grid(row=6, column=0, sticky="ew", pady=(8, 0))
        self.progress.start()
        self._update_empty()

        def prog(path, n):
            shown = path if len(path) < 70 else "…" + path[-68:]
            self.app.set_text(self.status, f"{n:,} file letti…  {shown}".replace(",", "."))

        def finish():
            self.busy = False
            self.go_btn.configure(state="normal")
            ui.hide(self.cancel_btn)
            self.progress.stop()
            self.progress.grid_forget()
            self._update_empty()

        def done(res):
            finish()
            if res is None:
                self.status.configure(text="Analisi annullata.")
                return
            self.result = res
            extra = f" · {res.denied_dirs} cartelle non accessibili" if res.denied_dirs else ""
            hint = "  (avvia come amministratore per vederle)" if res.denied_dirs and not is_admin() else ""
            self.status.configure(text=fmt_size(res.root.size) + f" in {res.total_files:,} file".replace(",", ".")
                                  + extra + hint)
            self._open_node(res.root)

        def err(e):
            finish()
            self.status.configure(text="Analisi non riuscita.")
            self.app.error_box("Non è stato possibile analizzare questo percorso.", e)

        self.app.run_bg(lambda: analyzer.analyze(root, prog, lambda: self.cancel_flag), done, err)

    # ------------------------------------------------------------ visualizzazione
    def _view_changed(self, value):
        if value == "Cartelle":
            self.big_tree.frame.grid_remove()
            self.dir_tree.frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        else:
            self.dir_tree.frame.grid_remove()
            self.big_tree.frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self._render()
        self._update_empty()

    def _open_node(self, node: analyzer.DirNode):
        self.current = node
        self.entries = analyzer.list_dir_entries(node)
        root_key = os.path.normcase(self.result.root.path) if self.result else ""
        self.up_btn.configure(state="normal" if os.path.normcase(node.path) != root_key else "disabled")
        self._render()

    def _render(self):
        """Ridisegna la vista attuale applicando filtri e ordinamento (senza rileggere il disco)."""
        if not self.result:
            self._update_empty()
            return
        self._update_filter_btn()
        if self.view.get() == "Cartelle":
            self._render_dir()
        else:
            self._render_big()
        self._update_empty()

    def _render_dir(self):
        flt = self.filter_bar.filters()
        total = (self.current.size if self.current else 0) or 1
        if self.current:
            self.path_lbl.configure(text=f"{self.current.path}   ·   {fmt_size(self.current.size)}")
        t = self.dir_tree
        t.delete(*t.get_children())
        shown = [e for e in self.entries if flt.match(e["name"], e["dir"], e["size"], e["mtime"])]
        for e in sort_entries(shown, self.filter_bar.sort_key()):
            kind = "Cartella" if e["dir"] else (os.path.splitext(e["name"])[1][1:].upper() or "File")
            name = e["name"] + ("  (accesso negato)" if e["denied"] else "")
            t.insert("", "end", iid=e["path"],
                     values=(name, kind, fmt_size(e["size"]), pct_text(e["size"] / total),
                             dt.datetime.fromtimestamp(e["mtime"]).strftime("%d/%m/%Y")),
                     tags=("muted",) if e["denied"] else ())
        self.info_lbl.configure(text=f"{len(shown)} di {len(self.entries)} elementi")

    def _render_big(self):
        flt = self.filter_bar.filters()
        key = self.filter_bar.sort_key()
        self.path_lbl.configure(text=f"I file più grandi in {self.result.root.path}")
        t = self.big_tree
        t.delete(*t.get_children())
        rows = [(s, p, m) for s, p, m in self.result.biggest if flt.match(os.path.basename(p), False, s, m)]
        if key == "name":
            rows.sort(key=lambda r: os.path.basename(r[1]).lower())
        elif key == "date":
            rows.sort(key=lambda r: r[2], reverse=True)
        else:
            rows.sort(key=lambda r: r[0], reverse=True)
        for size, path, mtime in rows:
            kind = os.path.splitext(path)[1][1:].upper() or "File"
            t.insert("", "end", iid=path, values=(os.path.basename(path), kind, fmt_size(size), os.path.dirname(path),
                                                  dt.datetime.fromtimestamp(mtime).strftime("%d/%m/%Y")))
        self.info_lbl.configure(text=f"{len(rows)} di {len(self.result.biggest)} file")

    def _open_item(self, _=None):
        sel = self.dir_tree.focus()
        if not sel or not self.result:
            return
        node = self.result.index.get(os.path.normcase(sel))
        if node:
            self._open_node(node)
        else:
            open_in_explorer(sel)

    def _up(self):
        if not self.current or not self.result:
            return
        parent = self.result.index.get(os.path.normcase(os.path.dirname(self.current.path)))
        if parent and os.path.normcase(self.current.path) != os.path.normcase(self.result.root.path):
            child = self.current.path
            self._open_node(parent)
            if self.dir_tree.exists(child):
                self.dir_tree.selection_set(child)
                self.dir_tree.focus(child)
                self.dir_tree.see(child)

    # ------------------------------------------------------------ azioni
    def _active_tree(self):
        return self.dir_tree if self.view.get() == "Cartelle" else self.big_tree

    def _context(self, event):
        t = event.widget
        row = t.identify_row(event.y)
        if row:
            if row not in t.selection():
                t.selection_set(row)
            t.focus(row)
            self.menu.tk_popup(event.x_root, event.y_root)

    def _reveal(self):
        sel = self._active_tree().selection()
        if sel:
            open_in_explorer(sel[0])
        elif self.current:
            open_in_explorer(self.current.path)

    def _copy_path(self):
        sel = self._active_tree().selection()
        if sel:
            self.clipboard_clear()
            self.clipboard_append("\n".join(sel))

    def _size_of(self, path: str) -> tuple[int, bool]:
        node = self.result.index.get(os.path.normcase(path)) if self.result else None
        if node:
            return node.size, True
        try:
            return os.path.getsize(path), False
        except OSError:
            return 0, False

    def _trash(self):
        paths = list(self._active_tree().selection())
        if not paths or not self.result:
            return
        blocked = [p for p in paths if protected_path(p)]
        if blocked:
            messagebox.showwarning(APP_NAME, "Questi percorsi sono protetti e non possono essere eliminati:\n\n"
                                   + "\n".join(blocked))
            return
        info = [(p, *self._size_of(p)) for p in paths]
        tot = sum(i[1] for i in info)
        lst = "\n".join(f"  • {os.path.basename(p)}  ({fmt_size(s)})" for p, s, _ in info[:12])
        if len(info) > 12:
            lst += f"\n  … e altri {len(info) - 12}"
        if not messagebox.askyesno(APP_NAME, f"Spostare nel cestino {len(info)} elementi ({fmt_size(tot)})?\n\n{lst}\n\n"
                                             "Potrai recuperarli dal Cestino di Windows."):
            return

        def work():
            ok, failed = [], []
            for p, s, is_dir in info:
                try:
                    send2trash(p)
                    ok.append((p, s, is_dir))
                    log(f"Spostato nel cestino: {p} ({s} byte)")
                except Exception as ex:
                    log(f"Errore cestino {p}: {ex!r}")
                    failed.append(f"{os.path.basename(p)}: {explain_error(ex)}")
            return ok, failed

        def done(res):
            ok, failed = res
            for p, s, is_dir in ok:
                analyzer.remove_from_tree(self.result, p, s, is_dir)
            if self.current:
                self._open_node(self.current)
            else:
                self._render()
            if failed:
                messagebox.showwarning(APP_NAME, "Alcuni elementi non sono stati spostati (in uso o protetti):\n\n"
                                       + "\n".join(failed[:10]))
            self.status.configure(text=f"Spostati nel cestino {len(ok)} elementi "
                                       f"({fmt_size(sum(s for _, s, _ in ok))}).")

        self.status.configure(text="Sposto nel cestino…")
        self.app.run_bg(work, done)


# =====================================================================================
class DupPage(Page):
    MAX_GROUPS = 500   # oltre questo numero la tabella diventa lenta da usare

    def __init__(self, master, app: App):
        super().__init__(master, app)
        self.all_groups: list[duplicates.DupGroup] = []   # risultato della ricerca, senza filtri
        self.groups: list[duplicates.DupGroup] = []       # gruppi visibili con i filtri attuali
        self.checked: set[str] = set()
        self.cancel_flag = False
        self.busy = False
        self.searched = False   # almeno una ricerca completata
        self._filters_open = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)
        page_header(self, "Duplicati", "Trova file con contenuto identico, anche con nomi diversi. "
                                       "In ogni gruppo resta sempre almeno una copia.").grid(
            row=0, column=0, sticky="w", pady=(0, 14))

        top = Card(self)
        top.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        top_in = ctk.CTkFrame(top, fg_color="transparent")
        top_in.pack(fill="x", padx=16, pady=10)
        top_in.grid_columnconfigure(0, weight=1)
        label(top_in, "Cartelle da controllare (una per riga)", size=12, muted=True).grid(row=0, column=0, sticky="w")
        # casella Tk nativa: si ridimensiona in tempo reale senza scatti (la CTkTextbox ridisegnava tutto)
        self._box_wrap = tk.Frame(top_in, height=56, bd=0, highlightthickness=1)
        self._box_wrap.grid(row=1, column=0, sticky="ew", pady=(4, 0), padx=(0, 12))
        self._box_wrap.grid_propagate(False)
        self._box_wrap.grid_rowconfigure(0, weight=1)
        self._box_wrap.grid_columnconfigure(0, weight=1)
        self.folders_box = tk.Text(self._box_wrap, bd=0, highlightthickness=0, relief="flat", wrap="none",
                                   font=ui.pt(12), padx=10, pady=6)
        self.folders_box.grid(row=0, column=0, sticky="nsew")
        box_sb = ctk.CTkScrollbar(self._box_wrap, command=self.folders_box.yview)
        self.folders_box.configure(yscrollcommand=box_sb.set)
        box_sb.grid(row=0, column=1, sticky="ns")
        ui.register_text(self.folders_box, self._box_wrap)
        # bordo trascinabile: allunga o accorcia la lista delle cartelle senza cambiare la finestra
        grip = ctk.CTkFrame(top_in, height=8, fg_color=BORDER, corner_radius=4)
        grip.grid(row=2, column=0, sticky="ew", padx=(0, 12), pady=(3, 0))
        grip.bind("<ButtonPress-1>", self._grip_start)
        grip.bind("<B1-Motion>", self._grip_move)
        side = ctk.CTkFrame(top_in, fg_color="transparent")
        side.grid(row=1, column=1, sticky="n")
        button(side, "Aggiungi cartella", "add", "secondary", self._add_folder, width=170, height=32).pack(pady=(0, 6))
        button(side, "Ripristina", "refresh", "ghost", self._default_folders, width=170, height=32).pack()
        self._default_folders()

        bar = FlowBar(self)
        bar.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        self.go_btn = button(bar, "Cerca duplicati", "search", "primary", self.start, width=170)
        self.go_btn.pack(side="left")
        Tooltip(self.go_btn, "Cerca i file duplicati nelle cartelle scelte (F5)")
        self.filter_btn = button(bar, "Filtri", "filter", "secondary", self._toggle_filters, width=130)
        self.filter_btn.pack(side="left", padx=10)
        self.cancel_btn = button(bar, "Annulla", "stop", "secondary", self._cancel, width=110)
        Tooltip(self.cancel_btn, "Annulla (Esc)")
        for text, cmd in (("Deseleziona tutto", self._clear), ("Tieni il più recente", lambda: self._auto(True)),
                          ("Tieni il più vecchio", lambda: self._auto(False))):
            button(bar, text, None, "secondary", cmd, width=170).pack(side="right", padx=(8, 0))

        # i filtri lavorano sui risultati già trovati: non serve rifare la ricerca
        self.filter_bar = FilterBar(self, on_change=self._apply_filter, show_sort=False, default_min_size="Da 1 MB")

        holder = Card(self)
        holder.grid(row=4, column=0, sticky="nsew")
        self.tree = make_tree(holder, [("name", "File", 340, "w"), ("size", "Dimensione", 110, "e"),
                                       ("folder", "Cartella", 400, "w"), ("date", "Modificato", 140, "w")],
                              show_tree=True)
        self.tree.frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.empty = EmptyState(holder, "copy")
        self.tree.bind("<Button-1>", self._click)
        self.tree.bind("<space>", self._toggle_focus)
        self.tree.bind("<Double-1>", lambda e: self._reveal())

        foot = FlowBar(self)
        foot.grid(row=5, column=0, sticky="ew", pady=(12, 0))
        self.status = label(foot, "Clicca la casella a sinistra di un file per selezionarlo.", muted=True)
        self.status.pack(side="left", fill="x", expand=True)
        self.trash_btn = button(foot, "Sposta selezionati nel cestino", "trash", "danger", self._trash, width=270,
                                state="disabled")
        self.trash_btn.pack(side="right")
        Tooltip(self.trash_btn, lambda: "" if str(self.trash_btn.cget("state")) == "normal" else
                "Prima seleziona i file da spostare nel cestino")
        button(foot, "Apri posizione", "open", "secondary", self._reveal, width=160).pack(side="right", padx=10)
        self.progress = ctk.CTkProgressBar(self, height=6, mode="indeterminate")   # totale ignoto: barra indeterminata
        self._update_empty()

    def refresh(self):
        self.start()

    def cancel(self):
        if self.busy:
            self._cancel()

    def _update_empty(self):
        """Messaggio al posto della tabella quando non c'e' nulla da mostrare."""
        if self.busy:
            self.empty.show("Ricerca in corso…", "Sto confrontando i file delle cartelle scelte: può richiedere "
                            "qualche minuto. Puoi annullare con Esc.")
        elif not self.searched:
            self.empty.show("Nessuna ricerca ancora", "Scegli le cartelle qui sopra e premi «Cerca duplicati» (F5): "
                            "trovo i file identici anche con nomi diversi.", "Cerca duplicati", self.start,
                            action_icon="search")
        elif not self.all_groups:
            self.empty.show("Nessun duplicato trovato", "Nelle cartelle scelte non ci sono file identici. Se vuoi, "
                            "abbassa la dimensione minima nei filtri e cerca di nuovo.", ic="check")
        elif not self.groups:
            self.empty.show("Nessun gruppo corrisponde ai filtri", "Prova a cambiare i filtri oppure azzerali.",
                            "Azzera filtri", self.filter_bar.reset, action_icon="cancel")
        else:
            self.empty.hide()

    def _grip_start(self, event):
        self._grip_y = event.y_root
        self._grip_h = int(self._box_wrap.cget("height"))

    def _grip_move(self, event):
        # un solo aggiornamento per fotogramma del monitor, anche se il mouse invia più eventi
        self._grip_target = max(40, min(260, self._grip_h + (event.y_root - self._grip_y)))
        if not getattr(self, "_grip_pending", False):
            self._grip_pending = True
            self.after(ui.FRAME_MS, self._grip_apply)

    def _grip_apply(self):
        self._grip_pending = False
        self._box_wrap.configure(height=self._grip_target)

    def _toggle_filters(self):
        self._filters_open = not self._filters_open
        if self._filters_open:
            self.filter_bar.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        else:
            self.filter_bar.grid_remove()
        self._update_filter_btn()

    def _update_filter_btn(self):
        active = self.filter_bar.filters().active
        self.filter_btn.configure(text="Filtri (attivi)" if active else "Filtri",
                                  fg_color=NAV_SEL if self._filters_open else SURFACE_ALT,
                                  text_color=NAV_SEL_TEXT if self._filters_open else TEXT)

    def _default_folders(self):
        home = env("USERPROFILE")
        cands = [os.path.join(home, n) for n in ("Desktop", "Documents", "Downloads", "Pictures", "Music", "Videos")]
        one = env("OneDrive")
        if one:
            cands += [os.path.join(one, n) for n in ("Desktop", "Documents", "Pictures", "Documenti", "Immagini")]
        self.folders_box.delete("1.0", "end")
        self.folders_box.insert("1.0", "\n".join(p for p in cands if os.path.isdir(p)))

    def _add_folder(self):
        p = filedialog.askdirectory(title="Aggiungi una cartella")
        if p:
            cur = self.folders_box.get("1.0", "end").strip()
            self.folders_box.delete("1.0", "end")
            self.folders_box.insert("1.0", (cur + "\n" if cur else "") + os.path.normpath(p))

    def _roots(self) -> list[str]:
        roots = [line.strip().strip('"') for line in self.folders_box.get("1.0", "end").splitlines()]
        return [r for r in roots if r and os.path.isdir(r)]

    def _cancel(self):
        self.cancel_flag = True

    def start(self):
        roots = self._roots()
        if self.busy:
            return
        if not roots:
            messagebox.showinfo(APP_NAME, "Aggiungi almeno una cartella esistente.")
            return
        # la ricerca usa solo la dimensione minima: nome, estensione e data si applicano dopo, senza rifarla
        min_size = self.filter_bar.filters().min_size
        self.busy = True
        self.cancel_flag = False
        self.go_btn.configure(state="disabled")
        self.cancel_btn.pack(side="left", padx=10)
        self.tree.delete(*self.tree.get_children())
        self.checked.clear()
        self.progress.grid(row=6, column=0, sticky="ew", pady=(8, 0))
        self.progress.start()
        self._update_empty()

        def done(groups):
            self.busy = False
            self.go_btn.configure(state="normal")
            ui.hide(self.cancel_btn)
            self.progress.stop()
            self.progress.grid_forget()
            if groups is None:
                self.status.configure(text="Ricerca annullata.")
                self._update_empty()
                return
            self.searched = True
            self.all_groups = groups
            self._apply_filter()

        def err(e):
            done(None)
            self.status.configure(text="Ricerca non riuscita.")
            self.app.error_box("Non è stato possibile cercare i duplicati.", e)

        self.app.run_bg(lambda: duplicates.find_duplicates(
            roots, Filters(min_size=min_size), lambda m: self.app.set_text(self.status, m), lambda: self.cancel_flag),
            done, err)

    def _apply_filter(self):
        """Ricalcola i gruppi visibili dai risultati già trovati (nessuna nuova ricerca)."""
        flt = self.filter_bar.filters()
        self._update_filter_btn()
        visible = []
        for g in self.all_groups:
            files = [(p, m) for p, m in g.files if flt.match(os.path.basename(p), False, g.size, m)]
            if len(files) > 1:
                visible.append(duplicates.DupGroup(g.size, files))
        self.groups = visible
        self.checked &= {p for g in visible for p, _ in g.files}
        self._fill()

    def _fill(self):
        t = self.tree
        t.delete(*t.get_children())
        shown = self.groups[:self.MAX_GROUPS]
        for gi, g in enumerate(shown):
            gid = f"g{gi}"
            t.insert("", "end", iid=gid, image=ui.table_image("off"), open=True, tags=("group",),
                     values=(f"{len(g.files)} copie identiche", fmt_size(g.size),
                             f"{fmt_size(g.wasted)} recuperabili", ""))
            for path, mtime in sorted(g.files, key=lambda f: f[1]):
                t.insert(gid, "end", iid=path, image=ui.table_image("on" if path in self.checked else "off"),
                         values=(os.path.basename(path), fmt_size(g.size), os.path.dirname(path),
                                 dt.datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M")))
            self._refresh_group(gid)
        wasted = sum(g.wasted for g in self.groups)
        more = f" (mostrati i primi {len(shown)})" if len(self.groups) > len(shown) else ""
        if not self.all_groups:
            text = "Nessun duplicato trovato."
        elif not self.groups:
            text = "Nessun gruppo corrisponde ai filtri."
        else:
            text = f"{len(self.groups)} gruppi di duplicati{more}: {fmt_size(wasted)} recuperabili."
        self.status.configure(text=text)
        self._update_status()
        self._update_empty()

    def _group_of(self, path):
        parent = self.tree.parent(path)
        return self.groups[int(parent[1:])] if parent else None

    def _set_check(self, path: str, on: bool):
        if on:
            self.checked.add(path)
        else:
            self.checked.discard(path)
        self.tree.item(path, image=ui.table_image("on" if on else "off"))
        parent = self.tree.parent(path)
        if parent:
            self._refresh_group(parent)

    def _refresh_group(self, gid: str):
        kids = self.tree.get_children(gid)
        n = sum(1 for k in kids if k in self.checked)
        self.tree.item(gid, image=ui.table_image("on" if kids and n == len(kids) else ("part" if n else "off")))

    def _toggle_row(self, row: str):
        if self.tree.parent(row):
            self._set_check(row, row not in self.checked)
        else:  # riga di gruppo: seleziona o deseleziona tutte le copie
            kids = self.tree.get_children(row)
            on = not all(k in self.checked for k in kids)
            for k in kids:
                self._set_check(k, on)
        self._update_status()

    def _click(self, event):
        row = self.tree.identify_row(event.y)
        if not row or self.tree.identify_column(event.x) != "#0":
            return
        if "indicator" in str(self.tree.identify_element(event.x, event.y)):
            return  # freccia espandi/comprimi
        self._toggle_row(row)
        return "break"

    def _toggle_focus(self, _):
        row = self.tree.focus()
        if row:
            self._toggle_row(row)
        return "break"

    def _auto(self, newest: bool):
        for g in self.groups[:self.MAX_GROUPS]:
            files = sorted(g.files, key=lambda f: f[1], reverse=newest)
            for i, (p, _) in enumerate(files):
                self._set_check(p, i > 0)
        self._update_status()

    def _clear(self):
        for p in list(self.checked):
            self._set_check(p, False)
        self._update_status()

    def _update_status(self):
        if not self.checked:
            self.trash_btn.configure(state="disabled")
            return
        tot = sum(self._group_of(p).size for p in self.checked if self.tree.exists(p) and self._group_of(p))
        self.status.configure(text=f"Selezionati {len(self.checked)} file · {fmt_size(tot)}")
        self.trash_btn.configure(state="normal")

    def _reveal(self):
        row = self.tree.focus()
        if row and self.tree.parent(row):
            open_in_explorer(row)

    def _trash(self):
        # sicurezza: in ogni gruppo visibile deve restare almeno una copia
        sel, kept_all = [], []
        for g in self.groups[:self.MAX_GROUPS]:
            paths = [p for p, _ in g.files]
            chosen = [p for p in paths if p in self.checked]
            if chosen and len(chosen) == len(paths):
                kept_all.append(os.path.basename(paths[0]))
                chosen = chosen[1:]
            sel += [(p, g.size) for p in chosen]
        if kept_all:
            messagebox.showinfo(APP_NAME, "Per sicurezza non elimino tutte le copie di un file: una copia resterà per:\n\n"
                                + "\n".join(kept_all[:10]))
        if not sel:
            return
        tot = sum(s for _, s in sel)
        if not messagebox.askyesno(APP_NAME, f"Spostare nel cestino {len(sel)} file duplicati ({fmt_size(tot)})?"):
            return

        def work():
            ok, failed = [], []
            for p, _ in sel:
                try:
                    send2trash(p)
                    ok.append(p)
                    log(f"Duplicato nel cestino: {p}")
                except Exception as ex:
                    log(f"Errore cestino {p}: {ex!r}")
                    failed.append(f"{os.path.basename(p)}: {explain_error(ex)}")
            return ok, failed

        def done(res):
            ok, failed = res
            gone = set(ok)
            for g in self.all_groups:
                g.files = [f for f in g.files if f[0] not in gone]
            self.all_groups = [g for g in self.all_groups if len(g.files) > 1]
            self.checked -= gone
            self._apply_filter()
            msg = f"Spostati nel cestino {len(ok)} file."
            if failed:
                msg += "\n\nNon spostati:\n" + "\n".join(failed[:10])
            messagebox.showinfo(APP_NAME, msg)

        self.app.run_bg(work, done)


# =====================================================================================
class StartupPage(Page):
    def __init__(self, master, app: App):
        super().__init__(master, app)
        self.items: dict[str, startup.StartupItem] = {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        page_header(self, "Avvio automatico", "Programmi che partono con Windows. Disattivarli velocizza l'avvio; "
                                              "puoi sempre riattivarli.").grid(row=0, column=0, sticky="w",
                                                                               pady=(0, 16))
        bar = Card(self)
        bar.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        inner = FlowBar(bar)
        inner.pack(fill="x", padx=16, pady=12)
        button(inner, "Disattiva", "power", "danger", lambda: self._set(False), width=140).pack(side="left")
        button(inner, "Attiva", "check", "primary", lambda: self._set(True), width=140).pack(side="left", padx=10)
        button(inner, "Apri posizione", "open", "secondary", self._reveal, width=160).pack(side="left")
        refresh_btn = button(inner, "Aggiorna", "refresh", "ghost", self.on_show, width=130)
        refresh_btn.pack(side="right")
        Tooltip(refresh_btn, "Rilegge l'elenco dei programmi (F5)")

        holder = Card(self)
        holder.grid(row=2, column=0, sticky="nsew")
        self.tree = make_tree(holder, [("name", "Nome", 200, "w"), ("state", "Stato", 120, "w"),
                                       ("source", "Origine", 230, "w"), ("cmd", "Comando", 370, "w")],
                              show_tree=True)   # la colonna iniziale mostra un pallino verde/grigio
        self.tree.column("#0", width=int(44 * ui.SCALE), stretch=False, anchor="center")
        self.tree.frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.empty = EmptyState(holder, "power")
        self.tree.tag_configure("off", foreground="#667085")
        self.status = label(self, "", muted=True)
        self.status.grid(row=3, column=0, sticky="w", pady=(10, 0))

    def on_show(self):
        t = self.tree
        t.delete(*t.get_children())
        self.items.clear()
        for i, it in enumerate(startup.list_items()):
            iid = f"i{i}"
            self.items[iid] = it
            t.insert("", "end", iid=iid, tags=() if it.enabled else ("off",),
                     image=ui.table_image("dot_on" if it.enabled else "dot_off"),
                     values=(it.name, "Attivo" if it.enabled else "Disattivato", it.source, it.command))
        if self.items:
            self.empty.hide()
        else:
            self.empty.show("Nessun programma in avvio automatico", "Non ho trovato programmi che partono con "
                            "Windows, oppure Windows non ha permesso di leggerli. Premi «Aggiorna» per riprovare.",
                            "Aggiorna", self.on_show, action_icon="refresh")
        on = sum(1 for i in self.items.values() if i.enabled)
        self.status.configure(text=f"{len(self.items)} programmi, {on} attivi."
                              + ("" if is_admin() else "  Quelli «tutti gli utenti» richiedono l'amministratore."))

    def refresh(self):
        self.on_show()

    def _set(self, enabled: bool):
        sel = self.tree.selection()
        if not sel:
            return
        denied = []
        for iid in sel:
            it = self.items[iid]
            try:
                startup.set_enabled(it, enabled)
            except PermissionError:
                denied.append(it.name)
            except OSError as ex:
                log(f"Errore avvio automatico {it.name}: {ex!r}")
                denied.append(f"{it.name} ({explain_error(ex)})")
        self.on_show()
        if denied:
            messagebox.showwarning(APP_NAME, "Servono i diritti di amministratore per:\n\n" + "\n".join(denied))

    def _reveal(self):
        sel = self.tree.selection()
        if not sel:
            return
        it = self.items[sel[0]]
        if it.approved_sub == "StartupFolder":
            open_in_explorer(it.command)
            return
        cmd = it.command.strip()
        exe = cmd[1:cmd.find('"', 1)] if cmd.startswith('"') else cmd.split(" ")[0]
        exe = os.path.expandvars(exe)
        if os.path.exists(exe):
            open_in_explorer(exe)
        else:
            messagebox.showinfo(APP_NAME, f"File non trovato:\n{exe}\n\nPotrebbe essere un avvio rimasto da un "
                                          "programma disinstallato: puoi disattivarlo.")


def resolve_mode(pref: str) -> str:
    """Preferenza del tema (Chiaro / Scuro / Sistema) -> modalità di CustomTkinter."""
    if pref == "Chiaro" or (pref == "Sistema" and system_prefers_light()):
        return "light"
    return "dark"


def main():
    settings = Settings()
    ctk.set_appearance_mode(resolve_mode(settings.get("theme")))
    ctk.set_default_color_theme("green")
    App(settings).mainloop()
