"""Iconița aplicației PDF Sign: foaie albă cu o semnătură albastră, pe pătrat albastru rotunjit.

  python make_icon.py   -> app/pdf-sign.ico (pentru PDF Sign.exe) și editor/icon.png (fereastra editorului)
"""
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
S = 1024  # desenăm mare și micșorăm, ca marginile să iasă netede


def draw() -> Image.Image:
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((40, 40, S - 40, S - 40), radius=210, fill=(47, 107, 255, 255))
    # foaia, cu colțul îndoit
    x0, y0, x1, y1, f = 250, 170, 774, 854, 150
    d.polygon([(x0, y0), (x1 - f, y0), (x1, y0 + f), (x1, y1), (x0, y1)], fill=(255, 255, 255, 255))
    d.polygon([(x1 - f, y0), (x1 - f, y0 + f), (x1, y0 + f)], fill=(200, 214, 255, 255))
    # rânduri de text
    for k, w in enumerate((330, 400, 260)):
        y = 330 + k * 85
        d.rounded_rectangle((x0 + 70, y, x0 + 70 + w, y + 30), radius=15, fill=(214, 222, 240, 255))
    # semnătura
    pts = [(330, 720), (370, 640), (405, 600), (420, 640), (410, 720), (450, 650), (490, 610), (505, 660),
           (520, 715), (560, 650), (600, 630), (630, 690), (690, 660)]
    d.line(pts, fill=(31, 63, 191, 255), width=34, joint="curve")
    d.line((320, 770, 700, 770), fill=(31, 63, 191, 255), width=18)
    return im


def main():
    big = draw()
    big.resize((256, 256), Image.LANCZOS).save(HERE / "pdf-sign.ico", sizes=[(16, 16), (20, 20), (24, 24), (32, 32),
                                                                          (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)])
    big.resize((192, 192), Image.LANCZOS).save(HERE.parent / "editor" / "icon.png", optimize=True)


if __name__ == "__main__":
    main()
