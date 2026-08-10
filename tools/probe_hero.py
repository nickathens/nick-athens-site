#!/usr/bin/env python3
"""Drive the real hero grid in a browser and measure what a cell actually shows.

Three states per run, each measured on the rendered pixels of one cell:
  idle   a normal lit cell
  off    a cell carrying the .off class
  held   a cell with the pointer down on it

For each, mean RGB, per-pixel spread (does the photo survive?) and saturation
(is it a colour?). A flat cell has spread 0, which is what "totally black" and
"totally coloured" both look like from here.
"""
import argparse
import colorsys
import io
import json
import statistics
import sys

from PIL import Image
from playwright.sync_api import sync_playwright

VIEWPORT = {"width": 1600, "height": 900}


def stats(img, box):
    crop = img.crop(box).convert("RGB")
    px = list(crop.getdata())
    r = [p[0] for p in px]
    g = [p[1] for p in px]
    b = [p[2] for p in px]
    lum = [0.2126 * p[0] + 0.7152 * p[1] + 0.0722 * p[2] for p in px]
    mr, mg, mb = statistics.mean(r), statistics.mean(g), statistics.mean(b)
    h, s, v = colorsys.rgb_to_hsv(mr / 255, mg / 255, mb / 255)
    return {
        "rgb": [round(mr, 1), round(mg, 1), round(mb, 1)],
        "luma": round(statistics.mean(lum), 1),
        "spread": round(statistics.pstdev(lum), 2),
        "sat": round(s, 3),
        "hue": round(h * 360, 1),
    }


def run(url, out_prefix):
    result = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--force-color-profile=srgb"])
        page = browser.new_page(viewport=VIEWPORT, device_scale_factor=1)
        # The first note pops the Grid Synth manual 800ms later, and it dims the
        # whole hero behind an overlay: a held cell measured through it reads as
        # near black. Arriving as a returning visitor keeps it away entirely,
        # which is deterministic where dismissing it was not.
        page.add_init_script("localStorage.setItem('synthDiscovered', 'true');")
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(1200)

        # Freeze the churn so a cell cannot change state under the measurement
        page.evaluate("() => { for (let i = 1; i < 99999; i++) clearInterval(i); }")
        page.wait_for_timeout(1200)

        # One press target, measured in all three states, so idle and held are
        # the same pixels and the spread numbers are directly comparable.
        # It must be the topmost element at its own centre or the press lands
        # on the nav bar and the whole measurement is of the wrong thing.
        picked = page.evaluate(
            """() => {
            const cells = [...document.querySelectorAll('.hero-grid .cell:not(.logo-cell)')];
            const lit = cells.filter(c => !c.classList.contains('off'));
            const off = cells.filter(c => c.classList.contains('off'));
            const idx = c => cells.indexOf(c);
            const rect = c => { const r = c.getBoundingClientRect();
                return [Math.ceil(r.x)+2, Math.ceil(r.y)+2, Math.floor(r.right)-2, Math.floor(r.bottom)-2]; };
            const topmost = c => { const r = c.getBoundingClientRect();
                const t = document.elementFromPoint(r.x + r.width/2, r.y + r.height/2);
                return t === c || c.contains(t); };
            // Prefer the most textured lit cell so "does the photo survive" is
            // asked where there is something to survive.
            const mid = lit.filter(topmost);
            const press = mid[Math.floor(mid.length / 2)] || mid[0] || null;
            const offCell = off.filter(topmost)[0] || off[0] || null;
            const logo = document.querySelector('.hero-grid .logo-cell');
            return {
                lit: lit.length, offCount: off.length, total: cells.length,
                offIdx: offCell ? idx(offCell) : -1,
                offBox: offCell ? rect(offCell) : null,
                pressIdx: press ? idx(press) : -1,
                pressBox: press ? rect(press) : null,
                logoBox: logo ? rect(logo) : null,
                pressCentre: press ? (() => { const r = press.getBoundingClientRect();
                    return [r.x + r.width/2, r.y + r.height/2]; })() : null,
            };
        }"""
        )
        result["grid"] = {k: picked[k] for k in ("total", "lit", "offCount")}
        result["lit_ratio"] = round(picked["lit"] / picked["total"], 3)
        result["cell_index"] = {"press": picked["pressIdx"], "off": picked["offIdx"]}

        shot = Image.open(io.BytesIO(page.screenshot()))
        shot.save(f"{out_prefix}_idle.png")
        if picked["pressBox"]:
            result["idle"] = stats(shot, picked["pressBox"])
        if picked["offBox"]:
            result["off"] = stats(shot, picked["offBox"])
        if picked["logoBox"]:
            result["logo_cell"] = stats(shot, picked["logoBox"])
            shot.crop(picked["logoBox"]).save(f"{out_prefix}_logo.png")

        # Press and hold
        if picked["pressCentre"]:
            x, y = picked["pressCentre"]
            page.mouse.move(x, y)
            page.mouse.down()
            page.wait_for_timeout(400)
            held = Image.open(io.BytesIO(page.screenshot()))
            held.save(f"{out_prefix}_held.png")
            result["held"] = stats(held, picked["pressBox"])
            shot.crop(picked["pressBox"]).save(f"{out_prefix}_cell_idle.png")
            held.crop(picked["pressBox"]).save(f"{out_prefix}_cell_held.png")
            page.mouse.up()
            page.wait_for_timeout(3200)
            assert not page.locator("#synthManual").is_visible(), "manual dimmed the reading"
            rel = Image.open(io.BytesIO(page.screenshot()))
            rel.save(f"{out_prefix}_released.png")
            result["released"] = stats(rel, picked["pressBox"])
        browser.close()
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--out", default="/tmp/hero")
    a = ap.parse_args()
    print(json.dumps(run(a.url, a.out), indent=2))
    sys.exit(0)
