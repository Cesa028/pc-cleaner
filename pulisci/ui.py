"""Elementi grafici condivisi: colori, icone, pulsanti, tabelle e barra dei filtri."""
from __future__ import annotations

import ctypes
import os
import struct
import sys
import tkinter as tk
from tkinter import ttk

import customtkinter as ctk
from PIL import Image

from .filters import MODIFIED, SIZES, SORTS, KINDS, Filters, parse_exts

FONT = "Segoe UI"

# colori: (tema chiaro, tema scuro)
ACCENT = ("#138a55", "#24a867")
ACCENT_HOVER = ("#0f7046", "#2bb673")
DANGER = ("#d92d20", "#f04438")
DANGER_HOVER = ("#b42318", "#d92d20")
WARN = ("#b54708", "#fdb022")
OK = ("#138a55", "#4ade80")
BG = ("#f2f4f7", "#14161a")
SURFACE = ("#ffffff", "#1c1f25")
SURFACE_ALT = ("#f2f4f7", "#262a32")
HOVER = ("#e4e7ec", "#303540")
BORDER = ("#e4e7ec", "#2b303a")
TEXT = ("#101828", "#eef1f6")
MUTED = ("#667085", "#98a2b3")
NAV_SEL = ("#dcf5e8", "#1d3a2c")
NAV_SEL_TEXT = ("#0b6b40", "#7ee2a8")

_TREES: list[ttk.Treeview] = []   # per aggiornare i colori al cambio di tema
_FONT_SCALE = {"v": 1.0}          # scala di CustomTkinter (DPI × scala widget), impostata dall'app


def set_font_scale(value: float) -> None:
    _FONT_SCALE["v"] = value


def pt(size: int, bold: bool = False) -> tuple:
    """Font per i widget Tk nativi (tabelle, lista) con la stessa dimensione dei testi CustomTkinter.
    CustomTkinter usa pixel (valori negativi); Tk con valori positivi usa punti, che risultano più grandi."""
    px = -round(size * _FONT_SCALE["v"])
    return (FONT, px, "bold") if bold else (FONT, px)
SCALE = 1.0                       # fattore DPI, impostato dall'app all'avvio (solo per le tabelle ttk)


def set_scale(value: float) -> None:
    global SCALE
    SCALE = value


def resource(*parts: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "assets", *parts)


# ---------------------------------------------------------------- icone
_icon_cache: dict = {}


def icon(name: str, on_accent: bool = False, size: int = 18):
    """Icona per pulsanti ed etichette (si adatta al tema). None se il file manca."""
    key = (name, on_accent, size)
    if key not in _icon_cache:
        try:
            if on_accent:
                img = Image.open(resource("icons", f"{name}_w.png"))
                _icon_cache[key] = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
            else:
                _icon_cache[key] = ctk.CTkImage(light_image=Image.open(resource("icons", f"{name}_l.png")),
                                                dark_image=Image.open(resource("icons", f"{name}_d.png")),
                                                size=(size, size))
        except OSError:
            _icon_cache[key] = None
    return _icon_cache[key]


def logo(size: int = 40):
    img = Image.open(resource("icon.png"))
    return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))


# ---------------------------------------------------------------- pulsanti
_BUTTON_STYLES = {
    "primary": dict(fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color="#ffffff", on_accent=True),
    "danger": dict(fg_color=DANGER, hover_color=DANGER_HOVER, text_color="#ffffff", on_accent=True),
    "secondary": dict(fg_color=SURFACE_ALT, hover_color=HOVER, text_color=TEXT, border_width=1, border_color=BORDER),
    "ghost": dict(fg_color="transparent", hover_color=HOVER, text_color=TEXT),
}


def button(master, text: str = "", ic: str | None = None, kind: str = "secondary", command=None,
           width: int | None = None, height: int = 36, **kw) -> ctk.CTkButton:
    style = dict(_BUTTON_STYLES[kind])
    on_accent = style.pop("on_accent", False)
    image = icon(ic, on_accent) if ic else None
    if image is not None and text:
        text = f"  {text}"   # spazio tra icona e testo
    opts = dict(style, command=command, height=height, corner_radius=10, font=(FONT, 13, "bold" if kind == "primary" else "normal"))
    if image is not None:
        opts["image"] = image
        opts["compound"] = "left"
    if width:
        opts["width"] = width
    elif not text:
        opts["width"] = height
    opts.update(kw)
    return ctk.CTkButton(master, text=text, **opts)


def option_menu(master, values, command=None, width: int | None = None, height: int = 36) -> ctk.CTkOptionMenu:
    opts = dict(values=list(values), command=command, height=height, corner_radius=10, font=(FONT, 13),
                fg_color=SURFACE_ALT, button_color=HOVER, button_hover_color=BORDER, text_color=TEXT,
                dropdown_fg_color=SURFACE, dropdown_hover_color=HOVER, dropdown_text_color=TEXT)
    if width:
        opts["width"] = width
    return ctk.CTkOptionMenu(master, **opts)


def segmented(master, values, command=None, height: int = 36) -> ctk.CTkSegmentedButton:
    return ctk.CTkSegmentedButton(master, values=list(values), command=command, height=height, corner_radius=10,
                                  font=(FONT, 13), fg_color=SURFACE_ALT, selected_color=ACCENT,
                                  selected_hover_color=ACCENT_HOVER, unselected_color=SURFACE_ALT,
                                  unselected_hover_color=HOVER, text_color=TEXT)


def entry(master, placeholder: str = "", height: int = 34) -> ctk.CTkEntry:
    return ctk.CTkEntry(master, height=height, corner_radius=8, fg_color=SURFACE_ALT, border_color=BORDER,
                        text_color=TEXT, placeholder_text=placeholder, placeholder_text_color=MUTED)


class FlowBar(ctk.CTkFrame):
    """Barra di pulsanti che va a capo quando la finestra è stretta.

    I figli si creano con questa barra come contenitore: vengono disposti da sinistra a destra e,
    se non ci stanno, scendono sulla riga successiva. Controlla da sola ogni 200 ms se cambiano
    larghezza finestra o figli visibili, quindi non serve chiamare niente quando si mostra o nasconde un pulsante.
    """

    def __init__(self, master, gap: int = 10, vgap: int = 8, **kw):
        kw.setdefault("fg_color", "transparent")
        super().__init__(master, **kw)
        self._gap, self._vgap, self._sig = gap, vgap, None
        tk.Frame.bind(self, "<Configure>", lambda e: self._check())   # bind() di CTk agirebbe sul canvas interno
        self.after(200, self._tick)

    def _tick(self):
        try:
            self._check()
            self.after(200, self._tick)
        except tk.TclError:   # finestra chiusa: il controllo si ferma
            pass

    def _check(self):
        width = self.winfo_width() - 6   # margine di sicurezza contro il bordo destro
        if width <= 6:
            return
        kids = [c for c in self.winfo_children()
                if not isinstance(c, tk.Canvas) and c.winfo_manager() in ("pack", "place")]
        sig = (width, tuple((id(c), c.winfo_reqwidth(), c.winfo_reqheight()) for c in kids))
        if sig == self._sig:
            return
        self._sig = sig
        x = y = rowh = 0
        for c in kids:
            w, h = c.winfo_reqwidth(), c.winfo_reqheight()
            if x and x + w > width:
                x, y, rowh = 0, y + rowh + self._vgap, 0
            c.place(x=x, y=y)
            x += w + self._gap
            rowh = max(rowh, h)
        self.configure(height=max(y + rowh, 1))


# ---------------------------------------------------------------- contenitori e testi
class Card(ctk.CTkFrame):
    """Riquadro con bordo sottile, usato come contenitore di ogni sezione."""

    def __init__(self, master, **kw):
        kw.setdefault("fg_color", SURFACE)
        kw.setdefault("corner_radius", 14)
        kw.setdefault("border_width", 1)
        kw.setdefault("border_color", BORDER)
        super().__init__(master, **kw)


def page_header(master, title: str, subtitle: str) -> ctk.CTkFrame:
    f = ctk.CTkFrame(master, fg_color="transparent")
    ctk.CTkLabel(f, text=title, font=(FONT, 26, "bold"), text_color=TEXT).pack(anchor="w")
    f._sub = ctk.CTkLabel(f, text=subtitle, font=(FONT, 13), text_color=MUTED, justify="left", wraplength=900)
    f._sub.pack(anchor="w", pady=(2, 0))
    return f


def label(master, text: str, size: int = 13, bold: bool = False, muted: bool = False, **kw) -> ctk.CTkLabel:
    kw.setdefault("font", (FONT, size, "bold") if bold else (FONT, size))
    kw.setdefault("text_color", MUTED if muted else TEXT)
    kw.setdefault("anchor", "w")
    return ctk.CTkLabel(master, text=text, **kw)


def bar_text(frac: float, width: int = 10) -> str:
    frac = max(0.0, min(1.0, frac))
    full = int(round(frac * width))
    return "▰" * full + "▱" * (width - full) + f"  {frac * 100:.1f}%".replace(".", ",")


# ---------------------------------------------------------------- rotellina del mouse
WHEEL_ROWS = 6     # righe per tacca nelle tabelle
WHEEL_LINES = 6    # righe di testo per tacca nelle caselle di testo
WHEEL_PX = 90      # pixel per tacca nelle schede scorrevoli (Pulizia)


def _scroll_target(w):
    """Risale dal widget sotto il mouse fino al primo elemento scorrevole: (funzione di scorrimento, passo)."""
    while w is not None:
        if isinstance(w, ctk.CTkScrollbar):
            return None, 0            # la barra gestisce già da sola la propria rotellina
        if isinstance(w, ttk.Treeview):
            return w, WHEEL_ROWS
        if isinstance(w, ctk.CTkTextbox):
            return w._textbox, WHEEL_LINES
        if isinstance(w, tk.Text):
            return w, WHEEL_LINES
        canvas = getattr(w, "_parent_canvas", None)   # CTkScrollableFrame
        if canvas is not None:
            return canvas, WHEEL_PX
        w = getattr(w, "master", None)
    return None, 0


FRAME_MS = 16   # durata di un fotogramma: 1000 / frequenza del monitor (impostata da install_wheel)


def monitor_hz() -> int:
    """Frequenza di aggiornamento del monitor principale (60 se non rilevabile)."""
    try:
        buf = ctypes.create_string_buffer(220)       # DEVMODEW
        struct.pack_into("<H", buf, 68, 220)         # dmSize
        if ctypes.windll.user32.EnumDisplaySettingsW(None, -1, buf):   # -1 = impostazioni attuali
            hz = struct.unpack_from("<I", buf, 184)[0]   # dmDisplayFrequency
            if 30 <= hz <= 480:
                return hz
    except Exception:
        pass
    return 60


_scroll_left: dict = {}   # canvas -> pixel ancora da scorrere (scorrimento animato)


def _smooth_scroll(canvas, px: int) -> None:
    running = canvas in _scroll_left
    _scroll_left[canvas] = _scroll_left.get(canvas, 0) + px
    if not running:
        _scroll_step(canvas)


def _scroll_step(canvas) -> None:
    left = _scroll_left.get(canvas, 0)
    move = int(left * 0.3) or (1 if left > 0 else -1 if left < 0 else 0)   # ease-out: 30% del residuo
    try:
        if move:
            canvas.yview("scroll", move, "units")
        left -= move
    except tk.TclError:
        _scroll_left.pop(canvas, None)
        return
    if left:
        _scroll_left[canvas] = left
        canvas.after(FRAME_MS, _scroll_step, canvas)
    else:
        _scroll_left.pop(canvas, None)


def _on_wheel(event):
    try:
        w = event.widget.winfo_containing(event.x_root, event.y_root) or event.widget
    except Exception:
        w = event.widget
    target, step = _scroll_target(w)
    if target is not None:
        notches = -round(event.delta / 120) or (-1 if event.delta > 0 else 1)
        if isinstance(target, tk.Canvas):
            _smooth_scroll(target, notches * step)    # schede: scorrimento animato alla frequenza del monitor
        else:
            target.yview("scroll", notches * step, "units")
    return "break"   # niente scorrimento doppio dai gestori predefiniti


def _patch_progressbar() -> None:
    """Barre di avanzamento animate a una frequenza pari a quella del monitor (CustomTkinter: 50 fps fissi)."""
    def loop(self):
        if self._loop_running:
            k = FRAME_MS / 20   # l'originale avanza di un passo ogni 20 ms
            if self._mode == "determinate":
                self._determinate_value += self._determinate_speed / 50 * k
                if self._determinate_value > 1:
                    self._determinate_value -= 1
            else:
                self._indeterminate_value += self._indeterminate_speed * k
            self._draw()
            self._loop_after_id = self.after(FRAME_MS, self._internal_loop)
    ctk.CTkProgressBar._internal_loop = loop


def install_wheel(root) -> None:
    """Rotellina più efficiente su tutte le finestre scorrevoli dell'app."""
    # CustomTkinter scorre di pochi pixel e in più punti: lo sostituiamo con il nostro gestore
    global FRAME_MS
    try:   # Windows aggiorna i timer ogni ~15,6 ms: chiediamo 1 ms, altrimenti Tk non supera ~64 fps
        ctypes.windll.winmm.timeBeginPeriod(1)
    except Exception:
        pass
    FRAME_MS = max(2, round(1000 / monitor_hz()))
    _patch_progressbar()
    ctk.CTkScrollableFrame._mouse_wheel_all = lambda self, event: None
    root.bind_all("<MouseWheel>", _on_wheel)
    root.bind_class("Treeview", "<MouseWheel>", _on_wheel)
    root.bind_class("Text", "<MouseWheel>", _on_wheel)


# ---------------------------------------------------------------- tabelle
_TEXTS: list = []   # (testo, contenitore) da ricolorare al cambio di tema


def register_text(text, box) -> None:
    _TEXTS.append((text, box))
    _color_texts()


def _color_texts() -> None:
    dark = ctk.get_appearance_mode() == "Dark"
    bg, fg = ("#262a32", "#eef1f6") if dark else ("#f2f4f7", "#101828")
    border = "#2b303a" if dark else "#e4e7ec"
    for text, box in _TEXTS:
        try:
            text.configure(bg=bg, fg=fg, insertbackground=fg, selectbackground=ACCENT[1 if dark else 0])
            box.configure(bg=bg, highlightbackground=border, highlightcolor=border)
        except tk.TclError:
            pass


def style_trees(root) -> None:
    """Colori delle tabelle ttk, coerenti con il tema attivo."""
    dark = ctk.get_appearance_mode() == "Dark"
    bg, fg = ("#1c1f25", "#eef1f6") if dark else ("#ffffff", "#101828")
    head = "#262a32" if dark else "#f2f4f7"
    sel = ACCENT[1] if dark else ACCENT[0]
    muted = "#98a2b3" if dark else "#667085"
    _color_texts()
    st = ttk.Style(root)
    st.theme_use("clam")
    st.configure("Treeview", background=bg, fieldbackground=bg, foreground=fg, borderwidth=0,
                 rowheight=int(30 * SCALE), font=pt(10))
    st.map("Treeview", background=[("selected", sel)], foreground=[("selected", "#ffffff")])
    st.configure("Treeview.Heading", background=head, foreground=fg, relief="flat", font=pt(10, True),
                 padding=(8, 6))
    st.map("Treeview.Heading", background=[("active", head)])
    st.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    st.configure("Vertical.TScrollbar", background=head, troughcolor=bg, borderwidth=0, arrowcolor=fg)
    alive = []
    for t in _TREES:
        try:
            if not t.winfo_exists():
                continue
            t.tag_configure("muted", foreground=muted)
            t.tag_configure("off", foreground=muted)
            alive.append(t)
        except tk.TclError:   # finestra già chiusa
            continue
    _TREES[:] = alive


def make_tree(master, columns: list[tuple[str, str, int, str]], show_tree: bool = False) -> ttk.Treeview:
    """columns: (id, titolo, larghezza, allineamento 'w'/'e'). Ritorna il Treeview; il frame è in tree.frame."""
    frame = ctk.CTkFrame(master, fg_color="transparent")
    tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show="tree headings" if show_tree else "headings",
                        selectmode="extended")
    for cid, title, width, anchor in columns:
        tree.heading(cid, text=title, anchor=anchor)
        tree.column(cid, width=int(width * SCALE), minwidth=int(60 * SCALE), anchor=anchor, stretch=True)
    if show_tree:
        tree.column("#0", width=int(64 * SCALE), stretch=False, anchor="e")
    sb = ctk.CTkScrollbar(frame, command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    tree.frame = frame  # type: ignore[attr-defined]
    tree.tag_configure("muted", foreground="#667085")
    tree.tag_configure("group", font=pt(10, True))
    _TREES.append(tree)
    return tree


# ---------------------------------------------------------------- barra dei filtri
class FilterBar(Card):
    """Campi per filtrare file e cartelle. Chiama on_change ad ogni modifica."""

    def __init__(self, master, on_change, show_sort: bool = True, default_min_size: str = "Qualsiasi"):
        super().__init__(master)
        self._on_change = on_change
        self._pending = None
        self._default_min = default_min_size
        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="x", padx=16, pady=14)
        for c in range(4):
            grid.grid_columnconfigure(c, weight=1, uniform="f")

        def field(row, col, title, make):
            """Crea un campo con il suo titolo sopra e lo ritorna."""
            box = ctk.CTkFrame(grid, fg_color="transparent")
            box.grid(row=row, column=col, sticky="ew", padx=(0, 12), pady=(0, 10))
            label(box, title, size=11, muted=True).pack(anchor="w", pady=(0, 3))
            widget = make(box)
            widget.pack(fill="x")
            return widget

        def menu(values):
            return lambda p: option_menu(p, values, self._changed)

        self.name = field(0, 0, "Nome contiene", lambda p: entry(p, "es. foto, *.pdf, bozza*"))
        self.exts = field(0, 1, "Estensione (separa con virgole)", lambda p: entry(p, "es. jpg, png, mp4"))
        self.kind = field(0, 2, "Tipo", menu(KINDS))
        self.modified = field(0, 3, "Modificato", menu(MODIFIED))
        self.min_size = field(1, 0, "Dimensione minima", menu(SIZES))
        if show_sort:
            self.sort = field(1, 1, "Ordina per", menu(SORTS))
        else:
            self.sort = option_menu(self, SORTS)  # non mostrato: usa l'ordine di default
        self.reset_btn = button(grid, "Azzera filtri", "cancel", "secondary", self.reset, height=34)
        self.reset_btn.grid(row=1, column=3 if show_sort else 1, sticky="sw", padx=(0, 12), pady=(0, 10))

        self.name.bind("<KeyRelease>", lambda e: self._debounce())
        self.exts.bind("<KeyRelease>", lambda e: self._debounce())
        self.reset(notify=False)

    def _debounce(self):
        if self._pending:
            self.after_cancel(self._pending)
        self._pending = self.after(250, self._changed)

    def _changed(self, *_):
        self._pending = None
        self._on_change()

    def filters(self) -> Filters:
        newer, older = MODIFIED[self.modified.get()]
        return Filters(text=self.name.get().strip(), exts=parse_exts(self.exts.get()),
                       kind=KINDS[self.kind.get()], newer_days=newer, older_days=older,
                       min_size=SIZES[self.min_size.get()])

    def sort_key(self) -> str:
        return SORTS[self.sort.get()]

    def reset(self, notify: bool = True):
        self.name.delete(0, "end")
        self.exts.delete(0, "end")
        self.kind.set(next(iter(KINDS)))
        self.modified.set(next(iter(MODIFIED)))
        self.min_size.set(self._default_min)
        self.sort.set(next(iter(SORTS)))
        if notify:
            self._changed()
