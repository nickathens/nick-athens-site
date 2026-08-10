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
import urllib.parse
import urllib.request

import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

# The asset check below scores the served sky with the builder's own metric
# rather than a second copy of it, so the two cannot drift apart. sys.path[0] is
# this directory, and build_hero_image does nothing at import beyond defining.
import build_hero_image  # noqa: E402

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


def open_page(b, css_vars=None, w=1600, h=900):
    p = b.new_page(viewport={"width": w, "height": h})
    # Arrive as a returning visitor: the first note otherwise pops the synth
    # manual 800ms later, and every reading taken through its overlay is dark.
    p.add_init_script("localStorage.setItem('synthDiscovered', 'true');")
    # Record the shape of every oscillator at the moment it starts. This is the
    # only reading that can tell the nav's waveform select apart from a
    # hardcoded oscillator.type, so it is installed before any script runs.
    p.add_init_script(
        """
        window.__waves = [];
        const start = OscillatorNode.prototype.start;
        OscillatorNode.prototype.start = function (...a) {
            window.__waves.push(this.type);
            return start.apply(this, a);
        };
    """
    )
    p.goto(URL, wait_until="networkidle")
    p.wait_for_timeout(1400)
    p.evaluate("() => { for (let i = 1; i < 99999; i++) clearInterval(i); }")
    # The hero's look was chosen through temporary query knobs which have since
    # been removed from the shipped page. The variables they wrote are still the
    # real mechanism, so they are driven here directly.
    if css_vars:
        p.evaluate(
            """(vars) => {
            for (const [k, v] of Object.entries(vars)) {
                document.documentElement.style.setProperty(k, v);
            }
        }""",
            css_vars,
        )
        p.wait_for_timeout(700)
    return p


def press_cell(p, box, hold=450):
    """Press and release one cell, returning the waveforms that sounded."""
    p.evaluate("() => { window.__waves = []; }")
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    p.mouse.move(cx, cy)
    p.mouse.down()
    p.wait_for_timeout(hold)
    p.mouse.up()
    return p.evaluate("() => window.__waves")


def wave_state(p):
    return p.evaluate(
        """() => {
        const o = [...document.querySelectorAll('#waveSelect .wave-option')];
        return {
            order: o.map(x => x.dataset.wave),
            active: o.filter(x => x.classList.contains('is-active')).map(x => x.dataset.wave),
            checked: o.filter(x => x.getAttribute('aria-checked') === 'true').map(x => x.dataset.wave),
            // A top level `let` is a script scope binding, not a window
            // property, so it is read by bare name rather than off window.
            armed: typeof synthWaveform === 'undefined' ? null : synthWaveform,
        };
    }"""
    )


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

    # The two variables move what they name. Both tint readings pin the same
    # colour on the same cell, so the only difference between them is the value.
    p = open_page(b, {"--hero-off": "0.15"})
    box = settle(p, off=True)
    dark = shot(p, box)
    p.close()
    check("the resting dim is a live variable, not baked in", dark["luma"] < rest["luma"] * 0.6,
          f"{dark['luma']} vs default {rest['luma']}")

    p = open_page(b, {"--hero-tint": "0.2"})
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
    check("a weaker tint softens the colour", soft["sat"] < held["sat"] * 0.7,
          f"sat {soft['sat']} vs full {held['sat']}")
    check("tint at 0.2 still colours the cell", soft_shift > 5 and soft["sat"] > base["sat"],
          f"hue shift {round(soft_shift, 1)}, sat {base['sat']} -> {soft['sat']}")
    check("tint at 0.2 keeps the photo", soft["spread"] > 2.0, f"spread {soft['spread']}")

    # The waveform select arms a shape, and the shape reaches the oscillator.
    # Reading the button state alone would pass with a hardcoded oscillator
    # type, so every case is confirmed by what actually sounded.
    p = open_page(b)
    box = settle(p)
    start = wave_state(p)
    check("the four shapes are offered in order",
          start["order"] == ["sine", "triangle", "square", "sawtooth"], f"{start['order']}")
    check("saw is armed on arrival, and only saw",
          start["active"] == ["sawtooth"] and start["checked"] == ["sawtooth"]
          and start["armed"] == "sawtooth",
          f"active {start['active']}, aria {start['checked']}, armed {start['armed']}")
    # The armed button has to look armed. Reading the class alone would pass
    # with the .is-active rule deleted, leaving a selector with no selection.
    paint = p.evaluate(
        """() => {
        const o = [...document.querySelectorAll('#waveSelect .wave-option')];
        const on = o.find(x => x.classList.contains('is-active'));
        const off = o.find(x => !x.classList.contains('is-active'));
        const read = e => {
            const s = getComputedStyle(e);
            return [s.backgroundColor, s.color, s.opacity].join(' | ');
        };
        return { on: read(on), off: read(off) };
    }"""
    )
    check("the armed button is drawn differently from the rest", paint["on"] != paint["off"],
          f"armed {paint['on']}, others {paint['off']}")
    default_waves = press_cell(p, box)
    check("an untouched page still plays saw",
          bool(default_waves) and set(default_waves) == {"sawtooth"}, f"{default_waves}")
    p.wait_for_timeout(2600)

    for wave, label in (("sine", "Sin"), ("triangle", "Tri"), ("square", "Sqr"), ("sawtooth", "Saw")):
        p.click(f'#waveSelect .wave-option[data-wave="{wave}"]')
        s = wave_state(p)
        check(f"{label} lights up alone when picked",
              s["active"] == [wave] and s["checked"] == [wave] and s["armed"] == wave,
              f"active {s['active']}, aria {s['checked']}, armed {s['armed']}")
        sounded = press_cell(p, box)
        check(f"{label} is the shape that sounds",
              bool(sounded) and set(sounded) == {wave}, f"{sounded}")
        p.wait_for_timeout(2600)
    p.close()

    # The cluster sits top left beside Harmony and clears the mobile menu
    # button. 320 is in the list because that is the width where the untightened
    # bar ended exactly on the button, with a gap of 0.0.
    for w, h, label in ((1600, 900, "desktop"), (430, 932, "phone"), (320, 800, "narrow")):
        p = open_page(b, None, w, h)
        geo = p.evaluate(
            """() => {
            const r = e => e ? e.getBoundingClientRect() : null;
            const wave = r(document.getElementById('waveSelect'));
            const harm = r(document.querySelector('.harmony-toggle'));
            const bar = r(document.querySelector('.synth-controls'));
            // Hidden on desktop, where a zero sized rect would read as x = 0
            // and make the clearance check fail for the wrong reason.
            let burger = r(document.querySelector('.nav-toggle'));
            if (burger && burger.width === 0) burger = null;
            const visible = getComputedStyle(document.getElementById('waveSelect')).display !== 'none';
            return { wave, harm, bar, burger, visible,
                     vw: innerWidth, scrollW: document.documentElement.scrollWidth };
        }"""
        )
        w_box, h_box, bar, burger = geo["wave"], geo["harm"], geo["bar"], geo["burger"]
        check(f"{label}: all four buttons are on screen",
              geo["visible"] and w_box["width"] > 40, f"width {round(w_box['width'], 1)}")
        check(f"{label}: it sits immediately after Harmony",
              -1 <= w_box["x"] - h_box["right"] <= 14,
              f"harmony ends {round(h_box['right'], 1)}, select starts {round(w_box['x'], 1)}")
        check(f"{label}: the cluster is top left", bar["x"] < geo["vw"] / 2 and bar["y"] < 100,
              f"bar starts {round(bar['x'], 1)}, {round(bar['y'], 1)} down")
        # The menu button is what the fourth control can collide with, and a
        # touch target needs real clearance, not a rect that merely does not
        # overlap.
        check(f"{label}: it clears the menu button",
              burger is None or bar["right"] <= burger["x"] - 12,
              f"bar ends {round(bar['right'], 1)}"
              + (f", button at {round(burger['x'], 1)}" if burger else ", no button"))
        check(f"{label}: nothing pushes the page sideways", geo["scrollW"] <= geo["vw"],
              f"scroll width {geo['scrollW']} of {geo['vw']}")
        p.close()

    # Every cell carries a slice, the logo cell included, at both widths
    for w, h, label in ((1600, 900, "desktop"), (430, 932, "mobile")):
        p = open_page(b, None, w, h)
        r = p.evaluate(
            """() => {
            const c = [...document.querySelectorAll('.hero-grid .cell')];
            return { n: c.length,
                     photo: c.filter(x => (x.style.backgroundImage || '').includes('hero-sky')).length };
        }"""
        )
        check(f"{label}: every cell has a photo slice", r["n"] == r["photo"], f"{r['photo']}/{r['n']}")
        p.close()
    # The slice checks above pass whether the sky reads as cloud or as a smear,
    # which is how the first version shipped as a colour wash. These score the
    # asset the server actually hands out, through the portrait crop a phone
    # gets, which is the strict view: it keeps under a third of the frame.
    served = urllib.request.urlopen(  # noqa: S310  (fixed scheme, own server)
        urllib.parse.urljoin(URL, "images/hero-sky.webp"), timeout=30
    ).read()
    sky = Image.open(io.BytesIO(served)).convert("RGB")
    form = build_hero_image.cloud_form(sky)

    # The control is the flat sky that actually shipped, rebuilt out of these
    # same bytes by scaling the cloud band back down by the clarity that was
    # applied to it. Without a control the floor is a number nobody has shown a
    # failing image can fall under. A first attempt at this used a plain
    # gaussian and scored 10.86, over the floor, because a blur at grain scale
    # leaves the cloud band standing: it would have passed on a smeared sky.
    flat = build_hero_image.grade(sky, 1, 1 / build_hero_image.DEFAULT_CLARITY)
    flat_form = build_hero_image.cloud_form(flat)

    a = np.asarray(sky, dtype=np.float32)
    keep = round(sky.size[0] * (build_hero_image.PHONE_ASPECT / (sky.size[0] / sky.size[1])))
    x0 = round((sky.size[0] - keep) * build_hero_image.PHONE_FOCUS_X)
    window = a[:, x0:x0 + keep]
    mx, mn = window.max(2), window.min(2)
    sat = float((np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0) * 100).mean())

    check("the sky the server hands out reads as cloud, not as a wash",
          form > 9.0, f"cloud form {form:.2f}, the flat version scored 5.20")
    check("that reading can tell a flat sky apart", flat_form < 9.0,
          f"blurred control scored {flat_form:.2f}")
    check("the colour survived the clarity pass", sat > 24.0, f"saturation {sat:.1f}%")
    b.close()

print("\n" + ("ALL PASS" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}"))
sys.exit(1 if FAILS else 0)
