# -*- coding: utf-8 -*-
"""Genera icon.ico (multi-tamano) para GLPI Notificator.
Requiere Pillow solo para generarlo:  pip install pillow
Uso:  python make_icon.py
"""
from PIL import Image, ImageDraw

S = 1024
BG = (255, 77, 0, 255)      # naranja electrico #ff4d00
INK = (13, 13, 13, 255)     # tinta #0d0d0d
RED = (224, 27, 36, 255)    # rojo #e01b24
WHITE = (255, 255, 255, 255)

img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

d.rectangle([0, 0, S - 1, S - 1], fill=BG)
m = int(S * 0.055)
for i in range(m):
    d.rectangle([i, i, S - 1 - i, S - 1 - i], outline=INK)

cx = S / 2
kr = S * 0.048
d.ellipse([cx - kr, S * 0.19 - kr, cx + kr, S * 0.19 + kr], fill=INK)
d.ellipse([S * 0.30, S * 0.255, S * 0.70, S * 0.70], fill=INK)
d.polygon([(S * 0.30, S * 0.50), (S * 0.245, S * 0.76),
           (S * 0.755, S * 0.76), (S * 0.70, S * 0.50)], fill=INK)
d.rectangle([S * 0.205, S * 0.75, S * 0.795, S * 0.805], fill=INK)
cr = S * 0.052
d.ellipse([cx - cr, S * 0.83 - cr, cx + cr, S * 0.83 + cr], fill=INK)

bx, by, br = S * 0.755, S * 0.245, S * 0.165
d.ellipse([bx - br, by - br, bx + br, by + br], fill=RED,
          outline=BG, width=int(S * 0.022))
bar_w = S * 0.05
d.rectangle([bx - bar_w / 2, by - S * 0.095, bx + bar_w / 2, by + S * 0.02], fill=WHITE)
d.ellipse([bx - bar_w / 2, by + S * 0.05, bx + bar_w / 2, by + S * 0.05 + bar_w], fill=WHITE)

tamanos = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)]
img.save("icon.ico", sizes=tamanos)
img.resize((256, 256), Image.LANCZOS).save("icon.png")
print("Generado: icon.ico", tamanos, "y icon.png")
