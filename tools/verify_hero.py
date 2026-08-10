#!/usr/bin/env python3
"""Positive tests for the hero grid, driven through a real browser.

Every check asserts that something which is supposed to change did change, so a
pass cannot come from the feature being absent. Two rules learned the hard way
and kept here on purpose:

  - the synth picks its colour at random from a five colour palette, so any
    reading that compares two presses must pin the colour first, or it is
    comparing palette entries rather than the thing under test
  - a cell released at the centre of the screen has zero drag, which is exactly
    the value a leftover drag state would also hold, so the release is done from
    a dragged position

Usage: python tools/verify_hero.py [url]
"""
import colorsys
import io
import statistics
import sys

from PIL import Image
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8777/index.html"
PROBE_CELL = 40
PINNED = "#00bbf9"
# All ten of cellColors in js/main.js, as the browser reports an inline
# background-color. It is ten, not the five on the array's second line.
PALETTE_RGB = {
    "rgb(230, 57, 70)", "rgb(244, 162, 97)", "rgb(233, 196, 106)",
    "rgb(42, 157, 143)", "rgb(38, 70, 83)",
    "rgb(155, 93, 229)", "rgb(241, 91, 181)", "rgb(0, 187, 249)",
    "rgb(0, 245, 212)", "rgb(254, 228, 64)",
}
FAILS = []


def brightness_of(p, idx=PROBE_CELL):
    """The brightness multiplier the cell is actually rendering with."""
    f = p.evaluate(
        """(idx) => {
        const c = [...document.querySelectorAll('.hero-grid .cell:not(.logo-cell)')];
        return getComputedStyle(c[idx]).filter;
    }""",
        idx,
    )
    m = [s for s in f.split() if s.startswith("brightness(")]
    return float(m[0][len("brightness(") : -1]) if m else None


def st(img, box):
    px = list(img.crop(box).convert("RGB").getdata())
    m = [statistics.mean([p[i] for p in px]) for i in range(3)]
    h, s, _ = colorsys.rgb_to_hsv(*[x / 255 for x in m])
    lum = [0.2126 * p[0] + 0.7152 * p[1] + 0.0722 * p[2] for p in px]
    return dict(
        luma=round(statistics.mean(lum), 2),
        spread=round(statistics.pstdev(lum), 2),
        sat=round(s, 3),
        hue=round(h * 360, 1),
    )


def hue_gap(a, b):
    return abs(((a - b + 180) % 360) - 180)


def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("   " + detail if detail else ""))
    if not cond:
        FAILS.append(name)


def open_page(b, query="", w=1600, h=900):
    p = b.new_page(viewport={"width": w, "height": h})
    # Arrive as a returning visitor: the first note otherwise pops the synth
    # manual 800ms later, and every reading taken through its overlay is dark.
    p.add_init_script("localStorage.setItem('synthDiscovered', 'true');")
    p.goto(URL + query, wait_until="networkidle")
    p.wait_for_timeout(1400)
    p.evaluate("() => { for (let i = 1; i < 99999; i++) clearInterval(i); }")
    return p


def settle(p, idx=PROBE_CELL, off=False):
    """Put one cell in a known state and wait out the 0.5s opacity transition."""
    box = p.evaluate(
        """([idx, off]) => {
        const c = [...document.querySelectorAll('.hero-grid .cell:not(.logo-cell)')];
        c.forEach(x => x.classList.remove('off'));
        if (off) c[idx].classList.add('off');
        const r = c[idx].getBoundingClientRect();
        return [Math.ceil(r.x)+3, Math.ceil(r.y)+3, Math.floor(r.right)-3, Math.floor(r.bottom)-3];
    }""",
        [idx, off],
    )
    p.wait_for_timeout(1100)
    return box


def pin_colour(p, idx=PROBE_CELL, colour=PINNED):
    p.evaluate(
        """([idx, colour]) => {
        const c = [...document.querySelectorAll('.hero-grid .cell:not(.logo-cell)')];
        c[idx].querySelector('.tint').style.backgroundColor = colour;
    }""",
        [idx, colour],
    )


def shot(p, box):
    return st(Image.open(io.BytesIO(p.screenshot())), box)


with sync_playwright() as pw:
    b = pw.chromium.launch(args=["--force-color-profile=srgb"])

    # A resting cell shows the photo, dimmed, with its colour intact
    p = open_page(b)
    box = settle(p, off=False)
    lit = shot(p, box)
    settle(p, off=True)
    rest = shot(p, box)
    check("resting cell is not black", rest["luma"] > 20, f"luma {rest['luma']}")
    check("resting cell still carries photo texture", rest["spread"] > 1.0, f"spread {rest['spread']}")
    check("resting cell is dimmer than lit", rest["luma"] < lit["luma"] * 0.85, f"{rest['luma']} vs {lit['luma']}")
    check("resting cell keeps its hue", hue_gap(rest["hue"], lit["hue"]) < 12, f"{rest['hue']} vs {lit['hue']}")
    check("resting cell keeps its colour", rest["sat"] >= lit["sat"], f"{rest['sat']} vs {lit['sat']}")
    p.close()

    # A held cell is a hue of the photo, the drag still reads, and the release
    # puts back exactly what was there
    p = open_page(b)
    box = settle(p)
    idle = shot(p, box)
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    p.mouse.move(cx, cy)
    p.mouse.down()
    p.wait_for_timeout(450)
    # Read the press before pinning: the pin is what makes the two tint readings
    # comparable, and it would also cover for the synth never setting a colour.
    # Every entry in the palette is heavily saturated, so this threshold holds
    # whichever of the five was drawn.
    natural = shot(p, box)
    worn = p.evaluate(
        """(idx) => {
        const c = [...document.querySelectorAll('.hero-grid .cell:not(.logo-cell)')];
        return c[idx].querySelector('.tint').style.backgroundColor;
    }""",
        PROBE_CELL,
    )
    check("press puts a palette colour on the tint", worn in PALETTE_RGB, f"got {worn!r}")
    # Measured for all ten palette entries on this cell: the weakest is #264653
    # at 0.341 and the strongest 0.995, against an idle 0.18. The threshold sits
    # under the weakest of the ten rather than at a number that happened to hold
    # for whichever was drawn on the day.
    check("press colours the pixels", natural["sat"] > 0.28,
          f"sat {idle['sat']} -> {natural['sat']} with {worn}")
    pin_colour(p)
    p.wait_for_timeout(250)
    held = shot(p, box)
    full_shift = hue_gap(held["hue"], idle["hue"])
    check("held cell still carries photo texture", held["spread"] > idle["spread"] * 0.6,
          f"spread {held['spread']} vs idle {idle['spread']}")
    check("held cell is not flat", held["spread"] > 2.0, f"spread {held['spread']}")
    check("held cell takes the colour", full_shift > 25, f"hue {idle['hue']} -> {held['hue']}")
    held_brightness = brightness_of(p)
    p.mouse.move(cx + 500, cy)
    p.wait_for_timeout(300)
    right, right_b = shot(p, box), brightness_of(p)
    p.mouse.move(cx - 500, cy)
    p.wait_for_timeout(300)
    left, left_b = shot(p, box), brightness_of(p)
    check("drag right brightens the pixels", right["luma"] > left["luma"] + 1,
          f"{right['luma']} vs {left['luma']}")
    # The pixel check above is satisfied by the blend's own clipping even when
    # the lift is dead, so the mechanism is asserted separately: the cell's
    # rendered brightness must actually track the drag.
    check("the drag drives the cell's brightness",
          right_b is not None and left_b is not None
          and right_b > held_brightness > left_b,
          f"left {left_b}, centre {held_brightness}, right {right_b}")
    # Released from a dragged position, not from the centre, where a leftover
    # drag state would happen to equal the resting default and hide itself.
    p.mouse.move(cx + 500, cy)
    p.wait_for_timeout(250)
    p.mouse.up()
    p.wait_for_timeout(2600)
    rel = shot(p, box)
    check("release returns the untouched photo", rel == idle, f"{rel} vs {idle}")
    p.close()

    # A resting cell that is played goes back to resting, not to lit. It is the
    # only path through the wasOff branch, and the probe cell above is lit.
    p = open_page(b)
    box = settle(p, off=False)
    was_lit = shot(p, box)
    settle(p, off=True)
    was_rest = shot(p, box)
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    p.mouse.move(cx, cy)
    p.mouse.down()
    p.wait_for_timeout(400)
    p.mouse.up()
    p.wait_for_timeout(2600)
    back = shot(p, box)
    check("a resting cell returns to resting after a press",
          abs(back["luma"] - was_rest["luma"]) < 1.5 and back["luma"] < was_lit["luma"] * 0.85,
          f"{back['luma']}, resting {was_rest['luma']}, lit {was_lit['luma']}")
    p.close()

    # A dragged release must not leave its brightness behind for the next press.
    p = open_page(b)
    box = settle(p)
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2

    def press_read(drag_to=None):
        p.mouse.move(cx, cy)
        p.mouse.down()
        p.wait_for_timeout(400)
        pin_colour(p)
        p.wait_for_timeout(250)
        first = shot(p, box)
        if drag_to is not None:
            p.mouse.move(drag_to, cy)
            p.wait_for_timeout(300)
            p.mouse.up()
        else:
            p.mouse.up()
        p.wait_for_timeout(2600)
        return first

    clean = press_read()
    press_read(cx + 500)          # drag hard right, release there
    after = press_read()          # next press, no drag
    check("a dragged release leaves nothing behind",
          abs(after["luma"] - clean["luma"]) < 1.5, f"{after['luma']} vs first press {clean['luma']}")
    p.close()

    # The knobs move what they name. Both tint readings pin the same colour on
    # the same cell, so the only difference between them is the knob.
    p = open_page(b, "?off=0.15")
    box = settle(p, off=True)
    dark = shot(p, box)
    p.close()
    check("?off knob darkens the resting cell", dark["luma"] < rest["luma"] * 0.6,
          f"{dark['luma']} vs default {rest['luma']}")

    p = open_page(b, "?tint=0.2")
    box = settle(p)
    base = shot(p, box)
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    p.mouse.move(cx, cy)
    p.mouse.down()
    p.wait_for_timeout(450)
    pin_colour(p)
    p.wait_for_timeout(250)
    soft = shot(p, box)
    p.mouse.up()
    p.close()
    # Saturation, not hue, is the direct measure of how far the colour took the
    # cell. Hue swings hard even at a weak tint because the photo's own hue is
    # unstable where it is nearly grey, which makes it a poor proxy.
    soft_shift = hue_gap(soft["hue"], base["hue"])
    check("?tint knob softens the colour", soft["sat"] < held["sat"] * 0.7,
          f"sat {soft['sat']} vs full {held['sat']}")
    check("?tint at 0.2 still colours the cell", soft_shift > 5 and soft["sat"] > base["sat"],
          f"hue shift {round(soft_shift, 1)}, sat {base['sat']} -> {soft['sat']}")
    check("?tint at 0.2 keeps the photo", soft["spread"] > 2.0, f"spread {soft['spread']}")

    # Every cell carries a slice, the logo cell included, at both widths
    for w, h, label in ((1600, 900, "desktop"), (430, 932, "mobile")):
        p = open_page(b, "", w, h)
        r = p.evaluate(
            """() => {
            const c = [...document.querySelectorAll('.hero-grid .cell')];
            return { n: c.length,
                     photo: c.filter(x => (x.style.backgroundImage || '').includes('hero-sky')).length };
        }"""
        )
        check(f"{label}: every cell has a photo slice", r["n"] == r["photo"], f"{r['photo']}/{r['n']}")
        p.close()
    b.close()

print("\n" + ("ALL PASS" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}"))
sys.exit(1 if FAILS else 0)
