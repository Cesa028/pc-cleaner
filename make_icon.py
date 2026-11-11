"""Genera assets/icon.ico (eseguito solo in fase di build)."""
import os

from PIL import Image, ImageDraw, ImageFont

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
top, bot = (46, 204, 113), (17, 122, 101)
grad = Image.new("RGBA", (S, S))
gd = ImageDraw.Draw(grad)
for y in range(S):
    k = y / (S - 1)
    gd.line([(0, y), (S, y)], fill=tuple(int(top[i] * (1 - k) + bot[i] * k) for i in range(3)) + (255,))
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([8, 8, S - 8, S - 8], radius=56, fill=255)
img.paste(grad, (0, 0), mask)
try:
    font = ImageFont.truetype(os.path.join(os.environ["WINDIR"], "Fonts", "seguiemj.ttf"), 150)
    d.text((S / 2, S / 2 + 6), "🧹", font=font, anchor="mm", embedded_color=True)
except OSError:
    d.text((S / 2, S / 2), "P", fill="white", anchor="mm",
           font=ImageFont.truetype("segoeuib.ttf", 170))
os.makedirs("assets", exist_ok=True)
img.save("assets/icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
img.save("assets/icon.png")
print("ok")
