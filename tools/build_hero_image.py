#!/usr/bin/env python3
"""
Build the hero sky asset from the film scan.

The scan is almost monochrome (mean saturation 8.5 percent), but the hue
structure is real and regional: warm on the left and along the bottom, cool
blue through the lower centre, magenta into violet up the right edge. This
script amplifies that regional colour without inventing any.

Method: split to YCbCr. Chroma is split into a low frequency part (the region's
colour, from a heavy gaussian) and a high frequency part (chroma grain). Only
the low frequency part is multiplied. Keeping the chroma grain at unity is what
stops the amplified gradients from banding: the grain dithers them for free.

Luma was untouched in the first version and that was the mistake. The scan's
cloud edges carry a standard deviation of about 5 levels out of 255, so once the
regional chroma is multiplied five times the colour simply drowns the form and
the sky reads as a wash rather than as clouds. Measured on the shipped asset
through the portrait crop a phone actually gets: cloud-form 5.2, saturation 27.

So luma is split into three bands rather than lifted whole. The base (heavy
gaussian, cloud sized) carries the exposure and stays put. The band between
grain and base is the cloud structure and is the only thing multiplied. Grain
sits above it and stays at unity, so clarity sharpens the sky without turning
the film stock crunchy. Same crop after: cloud-form 13.2, saturation 27.5, so
the colour Nick picked is untouched and only the form comes back.

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

# Two densities. The 1x is what a ratio-1 desktop needs to paint the grid at
# 1:1; the 2x is the source scan at its own resolution, which is what a ratio-2
# laptop and a ratio-3 phone need. Widths and qualities were measured against how
# much of the scan's film grain survives the encoder, because the grain is not
# decoration here: the grade multiplies the regional chroma five times and the
# grain is the only thing dithering those gradients. At the 1920/q82 this asset
# originally shipped at, 59 percent of it was gone by the time the browser had
# it, and a 2x upscale on a phone smeared what was left. Grain retained against
# the pre-encode file: 1920/q88 66 percent, 3072/q78 73 percent, 3072/q82 80
# percent for 251KB more, which is not worth it.
WIDTH = 1920          # long edge of the 1x asset
WIDTH_2X = 3072       # long edge of the 2x asset, the scan's own width
QUALITY = 88          # webp quality for 1x
QUALITY_2X = 78       # webp quality for 2x
BLUR_DIVISOR = 24     # chroma gaussian radius = width / this
FORM_DIVISOR = 48     # luma base radius, the scale a cloud mass occupies
GRAIN_DIVISOR = 400   # luma grain radius, everything finer than a cloud edge
DEFAULT_K = 5         # chroma amplification actually shipped
DEFAULT_CLARITY = 3   # cloud-band amplification actually shipped

# The portrait view this asset is judged in. A phone keeps under a third of a
# 3:2 frame, so it is the strict case and the one the wash showed up in.
# PHONE_FOCUS_X must track HERO_PHOTO.focusX in js/main.js.
PHONE_ASPECT = 393 / 852
PHONE_FOCUS_X = 0.78


def grade(src: Image.Image, k: float, clarity: float = DEFAULT_CLARITY) -> Image.Image:
    """Amplify regional chroma by k and cloud-band luma by clarity.

    Both leave their own grain at unity: chroma grain because it dithers the
    amplified colour gradients, luma grain because multiplying it is what makes
    a clarity pass look like sharpening instead of like weather.
    """
    luma, cb, cr = src.convert("YCbCr").split()
    radius = src.size[0] / BLUR_DIVISOR

    out = []
    for chan in (cb, cr):
        full = np.asarray(chan, dtype=np.float32)
        low = np.asarray(chan.filter(ImageFilter.GaussianBlur(radius=radius)), dtype=np.float32)
        grain = full - low
        out.append(np.clip(128 + (low - 128) * k + grain, 0, 255).astype(np.uint8))

    full = np.asarray(luma, dtype=np.float32)
    fine = np.asarray(
        luma.filter(ImageFilter.GaussianBlur(radius=src.size[0] / GRAIN_DIVISOR)), dtype=np.float32
    )
    base = np.asarray(
        luma.filter(ImageFilter.GaussianBlur(radius=src.size[0] / FORM_DIVISOR)), dtype=np.float32
    )
    lit = np.clip(base + (fine - base) * clarity + (full - fine), 0, 255).astype(np.uint8)

    return Image.merge(
        "YCbCr", [Image.fromarray(lit), Image.fromarray(out[0]), Image.fromarray(out[1])]
    ).convert("RGB")


def saturation_stats(img: Image.Image) -> tuple[float, float]:
    a = np.asarray(img, dtype=np.float32)
    mx, mn = a.max(2), a.min(2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0) * 100
    return float(sat.mean()), float(np.percentile(sat, 95))


def grain(img: Image.Image, radius: float = 1.0) -> float:
    """Standard deviation of everything finer than a pixel or two: the film grain.

    Reported per asset because it is the number that decides the encode. The
    grade leans on the grain to dither the amplified chroma, so an encoder that
    smooths it away takes the dithering with it and the sky separates into
    patches. This is measured on the asset's own pixels, so comparing two widths
    is only meaningful against each one's own pre-encode value.
    """
    grey = img.convert("L")
    a = np.asarray(grey, dtype=np.float32)
    b = np.asarray(grey.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32)
    return float((a - b).std())


def cloud_form(img: Image.Image) -> float:
    """Standard deviation of the cloud-sized luma band. How much sky reads as cloud.

    Measured through the crop a portrait phone actually gets, since that is the
    view where the wash was visible and the desktop one was not.
    """
    a = np.asarray(img, dtype=np.float32)
    luma = Image.fromarray(
        (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]).astype(np.uint8)
    )
    w, h = img.size
    fine = np.asarray(luma.filter(ImageFilter.GaussianBlur(radius=w / GRAIN_DIVISOR)), np.float32)
    base = np.asarray(luma.filter(ImageFilter.GaussianBlur(radius=w / FORM_DIVISOR)), np.float32)
    keep = round(w * (PHONE_ASPECT / (w / h)))
    x0 = round((w - keep) * PHONE_FOCUS_X)
    return float((fine - base)[:, x0:x0 + keep].std())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="also write k=3,4,6 as preview assets")
    ap.add_argument("--clarity", type=float, default=DEFAULT_CLARITY,
                    help="cloud-band amplification (1 is the flat original)")
    args = ap.parse_args()

    raw = Image.open(SOURCE).convert("RGB")
    OUT_DIR.mkdir(exist_ok=True)

    targets = [
        (DEFAULT_K, WIDTH, QUALITY, OUT_DIR / "hero-sky.webp"),
        (DEFAULT_K, WIDTH_2X, QUALITY_2X, OUT_DIR / "hero-sky@2x.webp"),
    ]
    if args.all:
        targets += [(k, WIDTH, QUALITY, OUT_DIR / f"hero-sky-k{k}.webp") for k in (3, 4, 6)]

    for k, width, quality, path in targets:
        src = raw.resize((width, round(width * raw.size[1] / raw.size[0])), Image.LANCZOS)
        img = grade(src, k, args.clarity)
        img.save(path, "WEBP", quality=quality, method=6)
        # Read the grain back off the encoded file, not off `img`. The whole
        # point of the number is what the encoder left behind, so measuring the
        # in-memory image would report the one value that cannot be wrong.
        written = Image.open(path).convert("RGB")
        mean, p95 = saturation_stats(written)
        print(f"{path.name:22s} {width}px q{quality} k={k} clarity={args.clarity}  "
              f"{path.stat().st_size:>9,} bytes  "
              f"saturation mean {mean:.1f}%  p95 {p95:.1f}%  "
              f"cloud form {cloud_form(written):.2f}  "
              f"grain {grain(written):.2f} of {grain(img):.2f}")


if __name__ == "__main__":
    main()
