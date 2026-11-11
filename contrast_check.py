"""Verifica il contrasto WCAG delle coppie testo/sfondo dell'interfaccia (eseguire: python contrast_check.py)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pulisci import ui  # noqa: E402


def lum(h):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def ratio(a, b):
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


W = ui.ON_ACCENT
# (descrizione, primo piano, sfondo, minimo)
PAIRS = [
    ("Pulsante primario", W, ui.ACCENT, 4.5), ("Pulsante primario (hover)", W, ui.ACCENT_HOVER, 4.5),
    ("Pulsante pericolo", W, ui.DANGER, 4.5), ("Pulsante pericolo (hover)", W, ui.DANGER_HOVER, 4.5),
    ("Segmentato selezionato", W, ui.ACCENT, 4.5), ("Riga selezionata tabella", W, ui.ACCENT, 4.5),
    ("Segno di spunta checkbox", W, ui.ACCENT, 4.5),
    ("Testo su sfondo", ui.TEXT, ui.BG, 4.5), ("Testo su scheda", ui.TEXT, ui.SURFACE, 4.5),
    ("Testo su secondario", ui.TEXT, ui.SURFACE_ALT, 4.5), ("Testo su hover", ui.TEXT, ui.HOVER, 4.5),
    ("Secondario su scheda", ui.MUTED, ui.SURFACE, 4.5), ("Secondario su sfondo", ui.MUTED, ui.BG, 4.5),
    ("Secondario su campi", ui.MUTED, ui.SURFACE_ALT, 4.5), ("Secondario su hover", ui.MUTED, ui.HOVER, 4.5),
    ("Voce attiva barra laterale", ui.NAV_SEL_TEXT, ui.NAV_SEL, 4.5),
    ("Avviso su scheda", ui.WARN, ui.SURFACE, 4.5), ("Avviso su sfondo", ui.WARN, ui.BG, 4.5),
    ("OK su sfondo (modalita' admin)", ui.OK, ui.BG, 4.5), ("OK su scheda", ui.OK, ui.SURFACE, 4.5),
    ("Bordo checkbox (grafico)", ui.MUTED, ui.SURFACE, 3.0),
    ("Anello focus su scheda (grafico)", ui.FOCUS, ui.SURFACE, 3.0), ("Anello focus su sfondo", ui.FOCUS, ui.BG, 3.0),
    ("Anello focus su campi", ui.FOCUS, ui.SURFACE_ALT, 3.0), ("Anello focus su selezione", ui.FOCUS, ui.NAV_SEL, 3.0),
    ("Barra disco OK", ui.BAR_OK, ui.HOVER, 3.0), ("Barra disco avviso", ui.BAR_WARN, ui.HOVER, 3.0),
    ("Barra disco pericolo", ui.BAR_DANGER, ui.HOVER, 3.0),
]
bad = 0
for name, fg, bg, mn in PAIRS:
    for i, theme in enumerate(("chiaro", "scuro")):
        f = fg if isinstance(fg, str) else fg[i]
        b = bg if isinstance(bg, str) else bg[i]
        r = ratio(f, b)
        ok = r >= mn
        bad += not ok
        print(f"{'OK  ' if ok else 'FAIL'} {r:5.2f}:1 (min {mn}) {theme:6} {name}: {f} su {b}")
print("\nRISULTATO:", "tutte le coppie rispettano il minimo" if not bad else f"{bad} coppie sotto il minimo")
sys.exit(1 if bad else 0)
