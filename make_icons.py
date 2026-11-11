"""Genera le icone dell'interfaccia in assets/icons/ (eseguito in fase di build).

Le icone sono glifi del font di sistema «Segoe MDL2 Assets» (Windows 10/11), salvati come PNG:
  <nome>_l.png  colore scuro  (tema chiaro)
  <nome>_d.png  colore chiaro (tema scuro)
  <nome>_w.png  bianco        (pulsanti colorati)
"""
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "assets", "icons")
FONTS = [os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", n) for n in ("segmdl2.ttf", "SegoeIcons.ttf")]

GLYPHS = {
    "home": 0xE80F, "clean": 0xE75C, "analyze": 0xE9D9, "copy": 0xE8C8, "power": 0xE7E8,
    "search": 0xE721, "filter": 0xE71C, "trash": 0xE74D, "shield": 0xE83D, "refresh": 0xE72C,
    "check": 0xE73E, "cancel": 0xE711, "up": 0xE74A, "settings": 0xE713, "down": 0xE70D,
    "sun": 0xE706, "moon": 0xE708, "stop": 0xE71A, "open": 0xE8A7, "file": 0xE8A5,
    "info": 0xE946, "warn": 0xE7BA, "lock": 0xE72E, "add": 0xE710,
}
COLORS = {"l": (27, 31, 38, 255), "d": (238, 241, 246, 255), "w": (255, 255, 255, 255)}
SIZE = 64  # px: l'app la ridimensiona


def main() -> None:
    font_path = next((p for p in FONTS if os.path.exists(p)), None)
    if not font_path:
        raise SystemExit("Font Segoe MDL2 Assets non trovato: impossibile generare le icone.")
    font = ImageFont.truetype(font_path, 54)
    os.makedirs(OUT, exist_ok=True)
    for name, cp in GLYPHS.items():
        for tag, color in COLORS.items():
            img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
            ImageDraw.Draw(img).text((SIZE / 2, SIZE / 2), chr(cp), font=font, fill=color, anchor="mm")
            img.save(os.path.join(OUT, f"{name}_{tag}.png"))
    print(f"ok: {len(GLYPHS) * len(COLORS)} icone in {OUT}")


if __name__ == "__main__":
    main()
