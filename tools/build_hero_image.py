#!/usr/bin/env python3
"""
Build the hero sky asset from the film scan.

The scan is almost monochrome (mean saturation 8.5 percent), but the hue
structure is real and regional: warm on the left and along the bottom, cool
blue through the lower centre, magenta into violet up the right edge. This
script amplifies that regional colour without inventing any.

Method: split to YCbCr. Luma is untouched, so every bit of cloud detail and
film grain survives. Chroma is split into a low frequency part (the region's
colour, from a heavy gaussian) and a high frequency part (chroma grain). Only
the low frequency part is multiplied. Keeping the chroma grain at unity is what
stops the amplified gradients from banding: the grain dithers them for free.

Usage:
    python tools/build_hero_image.py                 # ships k=5 to images/
    python tools/build_hero_image.py --all           # also writes k=3,4,6 previews
"""

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "tools" / "hero-sky-source.jpg"
OUT_DIR = ROOT / "images"

WIDTH = 1920          # long edge of the shipped asset
QUALITY = 82          # webp quality, chosen by eye on a 1:1 crop
BLUR_DIVISOR = 24     # gaussian radius = width / this
DEFAULT_K = 5         # chroma amplification actually shipped


def grade(src: Image.Image, k: float) -> Image.Image:
    """Amplify regional chroma by k, leaving luma and chroma grain alone."""
    luma, cb, cr = src.convert("YCbCr").split()
    radius = src.size[0] / BLUR_DIVISOR

    out = []
    for chan in (cb, cr):
        full = np.asarray(chan, dtype=np.float32)
        low = np.asarray(chan.filter(ImageFilter.GaussianBlur(radius=radius)), dtype=np.float32)
        grain = full - low
        out.append(np.clip(128 + (low - 128) * k + grain, 0, 255).astype(np.uint8))

    return Image.merge(
        "YCbCr", [luma, Image.fromarray(out[0]), Image.fromarray(out[1])]
    ).convert("RGB")


def saturation_stats(img: Image.Image) -> tuple[float, float]:
    a = np.asarray(img, dtype=np.float32)
    mx, mn = a.max(2), a.min(2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0) * 100
    return float(sat.mean()), float(np.percentile(sat, 95))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="also write k=3,4,6 as preview assets")
    args = ap.parse_args()

    src = Image.open(SOURCE).convert("RGB")
    src = src.resize((WIDTH, round(WIDTH * src.size[1] / src.size[0])), Image.LANCZOS)
    OUT_DIR.mkdir(exist_ok=True)

    targets = [(DEFAULT_K, OUT_DIR / "hero-sky.webp")]
    if args.all:
        targets += [(k, OUT_DIR / f"hero-sky-k{k}.webp") for k in (3, 4, 6)]

    for k, path in targets:
        img = grade(src, k)
        img.save(path, "WEBP", quality=QUALITY, method=6)
        mean, p95 = saturation_stats(img)
        print(f"{path.name:22s} k={k}  {path.stat().st_size:>7,} bytes  "
              f"saturation mean {mean:.1f}%  p95 {p95:.1f}%")


if __name__ == "__main__":
    main()
