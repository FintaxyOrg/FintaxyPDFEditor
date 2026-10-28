"""Turn a photo/scan of a handwritten signature into a transparent PNG (ink only).

Works like Adobe's "Fill & Sign" capture: the paper (white, grey, shadowed) becomes
transparent, the ink keeps its real colour, and the image is cropped tight.

Usage:
  python signature_transparent.py INPUT [OUTPUT] [--color original|blue|black]
                                  [--strength 1.0] [--min-speck 25] [--preview PREVIEW.png]

  --strength  >1 keeps more faint strokes, <1 removes more paper noise (default 1.0)
  --min-speck drop isolated dots smaller than this many pixels (dust, paper grain)
  --preview   also write a check image: the signature on white and on a dark grid
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image, ImageFilter, ImageOps


def load_rgb(path):
    im = ImageOps.exif_transpose(Image.open(path))
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        white = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(white, im)
    return im.convert("RGB")


def estimate_background(rgb, ink_px):
    """Paper colour per pixel: a max filter wipes out thin dark ink, a blur smooths shadows."""
    size = max(3, int(ink_px) | 1)  # odd
    small_scale = 1
    w, h = rgb.size
    # paper colour is smooth, so a small copy is enough; MaxFilter costs size^2 per pixel
    # and at 1400 px a 1500 px signature took ~6 s, at 500 px it is well under a second
    if max(w, h) > 500:
        small_scale = max(w, h) / 500
        work = rgb.resize((int(w / small_scale), int(h / small_scale)), Image.BILINEAR)
        size = max(3, int(size / small_scale) | 1)
    else:
        work = rgb
    bg = work.filter(ImageFilter.MaxFilter(size)).filter(ImageFilter.MaxFilter(size))
    bg = bg.filter(ImageFilter.GaussianBlur(size))
    if small_scale != 1:
        bg = bg.resize((w, h), Image.BILINEAR)
    return bg


def _label(mask):
    """8-connected component labelling, pure Python (no scipy/opencv needed)."""
    h, w = mask.shape
    lab = np.zeros((h, w), np.int32)
    sizes, border = [0], [False]
    n = 0
    ys, xs = np.nonzero(mask)
    for sy, sx in zip(ys.tolist(), xs.tolist()):
        if lab[sy, sx]:
            continue
        n += 1
        lab[sy, sx] = n
        stack = [(sy, sx)]
        size, touch = 0, False
        while stack:
            y, x = stack.pop()
            size += 1
            if y == 0 or x == 0 or y == h - 1 or x == w - 1:
                touch = True
            for ny in (y - 1, y, y + 1):
                if ny < 0 or ny >= h:
                    continue
                for nx in (x - 1, x, x + 1):
                    if 0 <= nx < w and mask[ny, nx] and not lab[ny, nx]:
                        lab[ny, nx] = n
                        stack.append((ny, nx))
        sizes.append(size)
        border.append(touch)
    return lab, np.array(sizes), np.array(border)


def remove_specks(alpha, min_px):
    """Drop dust specks and marks that touch the photo edge (sheet edges, shadows, table)."""
    h, w = alpha.shape
    f = max(1, int(np.ceil(max(h, w) / 700)))
    hh, ww = int(np.ceil(h / f)), int(np.ceil(w / f))
    pad = np.zeros((hh * f, ww * f), bool)
    pad[:h, :w] = alpha > 0.15
    small = pad.reshape(hh, f, ww, f).any(axis=(1, 3))
    # bridge 1-px gaps so one pen stroke stays one component
    grown = small.copy()
    grown[1:, :] |= small[:-1, :]; grown[:-1, :] |= small[1:, :]
    grown[:, 1:] |= small[:, :-1]; grown[:, :-1] |= small[:, 1:]
    lab, sizes, border = _label(grown)
    if len(sizes) <= 1:
        return alpha
    total = sizes[1:].sum()
    # absolute floor, plus a floor relative to the whole signature (an i-dot is
    # still ~0.5% of the ink, paper grain is far smaller)
    min_small = max(2, min_px / (f * f), 0.003 * total)
    keep = sizes >= min_small
    # edge-touching blobs are paper edges/shadows, unless they are most of the ink
    keep &= ~(border & (sizes < 0.4 * total))
    keep[0] = False
    # small pieces survive only near the main strokes (i-dots, accents); far-away
    # crumbs are dirt on the paper and would blow up the crop
    big = keep & (sizes >= 0.02 * total)
    if big.any():
        by, bx = np.nonzero(big[lab])
        y0, y1, x0, x1 = by.min(), by.max(), bx.min(), bx.max()
        my, mx = (y1 - y0) * 0.15 + 3, (x1 - x0) * 0.15 + 3
        for i in np.nonzero(keep & ~big)[0]:
            cy, cx = np.nonzero(lab == i)
            if cy.min() < y0 - my or cy.max() > y1 + my or cx.min() < x0 - mx or cx.max() > x1 + mx:
                keep[i] = False
    km = keep[lab]
    full = np.repeat(np.repeat(km, f, axis=0), f, axis=1)[:h, :w]
    return alpha * full


def process(src, dst, color="original", strength=1.0, min_speck=25):
    rgb = load_rgb(src)
    w, h = rgb.size
    ink_px = max(w, h) / 40  # wider than any pen stroke at typical resolutions
    bg = estimate_background(rgb, ink_px)

    a = np.asarray(rgb, dtype=np.float32) / 255.0
    b = np.asarray(bg, dtype=np.float32) / 255.0
    b = np.maximum(b, a)  # paper is never darker than the pixel itself

    # darkness of the pixel relative to the local paper, per channel -> take the strongest
    dark = 1.0 - (a + 1e-4) / (b + 1e-4)
    d = dark.max(axis=2)

    # adaptive thresholds from the noise level of the paper
    noise = np.percentile(d, 60)
    lo = noise + 0.06 / strength
    hi = lo + 0.28
    alpha = np.clip((d - lo) / (hi - lo), 0, 1)
    alpha = remove_specks(alpha, min_speck)

    if not (alpha > 0.05).any():
        raise SystemExit("No ink found in the image. Try --strength 2.")

    # un-composite: recover the ink colour that, laid on the paper, gave this pixel
    al = alpha[..., None]
    safe = np.maximum(al, 0.05)
    ink = np.clip((a - (1 - al) * b) / safe, 0, 1)
    if color == "blue":
        target = np.array([0.10, 0.18, 0.55], np.float32)
        ink = np.broadcast_to(target, ink.shape)
    elif color == "black":
        ink = np.zeros_like(ink)
    else:
        # deepen washed-out photo ink a little so it reads like real pen on screen
        ink = np.clip(ink * 0.85, 0, 1)

    out = np.dstack([ink, alpha]) * 255
    img = Image.fromarray(out.astype(np.uint8), "RGBA")

    ys, xs = np.where(alpha > 0.05)
    pad = int(max(w, h) * 0.015) + 2
    box = (max(xs.min() - pad, 0), max(ys.min() - pad, 0),
           min(xs.max() + pad + 1, w), min(ys.max() + pad + 1, h))
    img = img.crop(box)
    img.save(dst, optimize=True)
    return img


def preview(img, path):
    w, h = img.size
    canvas = Image.new("RGB", (w * 2 + 30, h + 20), (255, 255, 255))
    canvas.paste(img, (10, 10), img)
    grid = Image.new("RGB", (w, h), (60, 60, 60))
    px = grid.load()
    for y in range(h):
        for x in range(w):
            if ((x // 16) + (y // 16)) % 2:
                px[x, y] = (90, 90, 90)
    grid.paste(img, (0, 0), img)
    canvas.paste(grid, (w + 20, 10))
    canvas.save(path)


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output", nargs="?")
    ap.add_argument("--color", default="original", choices=["original", "blue", "black"])
    ap.add_argument("--strength", type=float, default=1.0)
    ap.add_argument("--min-speck", type=int, default=25)
    ap.add_argument("--preview")
    args = ap.parse_args()
    dst = args.output or os.path.splitext(args.input)[0] + "_transparent.png"
    img = process(args.input, dst, args.color, args.strength, args.min_speck)
    if args.preview:
        preview(img, args.preview)
    print(f"OK {dst} {img.size[0]}x{img.size[1]}")


if __name__ == "__main__":
    sys.exit(main())
