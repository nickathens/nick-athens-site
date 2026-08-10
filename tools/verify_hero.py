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


# Everything the page sends to its own destination is routed through a gain node
# first, so the reverb checks read the graph the site actually builds rather
# than a rebuilt copy of it. The splitter is what makes the width reading
# possible: an AnalyserNode downmixes to mono on its own, and mono is exactly
# where a decorrelated plate tail hides.
AUDIO_TAP = """
window.__audio = {};
window.__edges = [];
const rawConnect = AudioNode.prototype.connect;
AudioNode.prototype.connect = function (destination, ...rest) {
    window.__edges.push([this, destination]);
    return rawConnect.call(this, destination, ...rest);
};
const RealAC = window.AudioContext || window.webkitAudioContext;
const destDesc = Object.getOwnPropertyDescriptor(
    window.BaseAudioContext.prototype, 'destination');
function Patched() {
    const ctx = new RealAC();
    const tap = ctx.createGain();
    const split = ctx.createChannelSplitter(2);
    const anL = ctx.createAnalyser();
    const anR = ctx.createAnalyser();
    anL.fftSize = 2048;
    anR.fftSize = 2048;
    rawConnect.call(tap, split);
    rawConnect.call(split, anL, 0);
    rawConnect.call(split, anR, 1);
    rawConnect.call(tap, destDesc.get.call(ctx));
    Object.defineProperty(ctx, 'destination', { get: () => tap, configurable: true });
    Object.assign(window.__audio, { ctx, tap, anL, anR });
    return ctx;
}
window.AudioContext = Patched;
window.webkitAudioContext = Patched;

// plateReverb is a top level `let`, a script scope binding rather than a window
// property, so it is reached by bare name. Read off window it is undefined,
// which would report a bus that is plainly there as missing.
window.__plate = () => (typeof plateReverb === 'undefined' ? null : plateReverb);

window.__wiring = () => {
    const p = window.__plate();
    if (!p) return null;
    const edge = (a, c) => window.__edges.some(e => e[0] === a && e[1] === c);
    return {
        sendToHighpass: edge(p.send, p.highpass),
        highpassToConvolver: edge(p.highpass, p.convolver),
        convolverToOutput: edge(p.convolver, window.__audio.tap),
        // A note's gain lands on both the output and the send, which is what
        // makes this a send off the voice rather than a second signal path.
        voicesIntoSend: window.__edges.filter(e => e[1] === p.send).length,
        voicesIntoOutput: window.__edges.filter(
            e => e[1] === window.__audio.tap && e[0] !== p.convolver).length,
    };
};

window.__response = () => {
    const p = window.__plate();
    if (!p || !p.convolver.buffer) return null;
    const b = p.convolver.buffer;
    const left = b.getChannelData(0);
    const right = b.getChannelData(1);
    const rms = (a, s, e) => {
        let x = 0;
        for (let i = s; i < e; i++) x += a[i] * a[i];
        return Math.sqrt(x / (e - s));
    };
    let dot = 0, ll = 0, rr = 0;
    for (let i = 0; i < b.length; i++) {
        dot += left[i] * right[i];
        ll += left[i] * left[i];
        rr += right[i] * right[i];
    }
    const ms = n => Math.floor(b.sampleRate * n / 1000);
    return {
        channels: b.numberOfChannels,
        seconds: b.duration,
        firstMs: rms(left, 0, Math.floor(b.sampleRate / 1000)),
        // The pre-delay window and the window just after it. A plate with the
        // pre-delay removed reads the same in every other field in here.
        preGap: rms(left, 0, ms(20)),
        afterGap: rms(left, ms(30), ms(60)),
        early: rms(left, 0, Math.floor(b.length * 0.05)),
        late: rms(left, Math.floor(b.length * 0.9), b.length),
        correlation: dot / Math.sqrt(ll * rr),
        normalize: p.convolver.normalize,
    };
};

// An extra analyser on the shipped convolver. An extra connection changes no
// audio, and it is the only way to read the wet on its own, which is the direct
// statement of how much of what is heard is plate.
window.__tapWet = () => {
    const p = window.__plate();
    if (!p) return false;
    const wet = window.__audio.ctx.createAnalyser();
    wet.fftSize = 2048;
    rawConnect.call(p.convolver, wet);
    window.__audio.anWet = wet;
    return true;
};

window.__wetLevel = () => {
    const an = window.__audio.anWet;
    if (!an) return null;
    const buf = new Float32Array(an.fftSize);
    an.getFloatTimeDomainData(buf);
    let s = 0;
    for (let i = 0; i < buf.length; i++) s += buf[i] * buf[i];
    return Math.sqrt(s / buf.length);
};

// Mid and side of what is actually leaving the page, read live.
window.__level = () => {
    const { anL, anR } = window.__audio;
    const L = new Float32Array(anL.fftSize);
    const R = new Float32Array(anR.fftSize);
    anL.getFloatTimeDomainData(L);
    anR.getFloatTimeDomainData(R);
    let m = 0, s = 0;
    for (let i = 0; i < L.length; i++) {
        const mid = (L[i] + R[i]) / 2;
        const side = (L[i] - R[i]) / 2;
        m += mid * mid;
        s += side * side;
    }
    return { mid: Math.sqrt(m / L.length), side: Math.sqrt(s / L.length) };
};
"""


def open_page(b, css_vars=None, w=1600, h=900, tap=False):
    p = b.new_page(viewport={"width": w, "height": h})
    if tap:
        p.add_init_script(AUDIO_TAP)
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
    check("square is armed on arrival, and only square",
          start["active"] == ["square"] and start["checked"] == ["square"]
          and start["armed"] == "square",
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
    check("an untouched page plays square",
          bool(default_waves) and set(default_waves) == {"square"}, f"{default_waves}")
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

    # The plate. Every reading here is of the graph the page built for itself,
    # and the decisive one is stereo width: the oscillators are mono, so the dry
    # signal has no side content at all and any that appears can only be the
    # plate. A level reading alone would not do, because a wet at -15dB moves
    # the total by a fraction of a decibel.
    p = open_page(b, tap=True)
    box = settle(p)
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2

    def hold_and_read(ms=700):
        """Press, let the plate fill, read mid, side and wet, then release.

        Five readings taken across the hold rather than one. The synth draws its
        pitch at random over four octaves, and the plate's response at one pitch
        is a different draw from its response at another, so a single window
        makes the reading a lottery rather than a measurement.
        """
        p.mouse.move(cx, cy)
        p.mouse.down()
        p.wait_for_timeout(ms)
        rows = []
        for _ in range(5):
            row = p.evaluate("() => window.__level()")
            row["wet"] = p.evaluate("() => window.__wetLevel()")
            rows.append(row)
            p.wait_for_timeout(90)
        p.mouse.up()
        p.wait_for_timeout(3200)
        return {k: statistics.median([r[k] for r in rows]) for k in ("mid", "side", "wet")}

    # The context, and with it the bus, is built on the first gesture
    p.mouse.click(cx, cy)
    p.wait_for_timeout(3400)
    ir = p.evaluate("() => window.__response()")
    wiring = p.evaluate("() => window.__wiring()")
    check("the wet can be read on its own", p.evaluate("() => window.__tapWet()"))

    check("the plate bus is built with the audio context", ir is not None and wiring is not None)
    if ir and wiring:
        check("the response is stereo", ir["channels"] == 2, f"{ir['channels']} channels")
        # Merely clearing 2.55s is not enough, which is why this bar moved. The
        # dry is torn down 2.55s after the release and the plate has to still
        # have level in the window after that or there is nothing to hear: at
        # 2.8s it was 52dB under the note's own peak there, which is the version
        # Nick could not hear. The level itself is checked further down; this
        # pins the one parameter that makes it reachable.
        check("the response runs well past the note's teardown",
              ir["seconds"] > 4.5, f"{round(ir['seconds'], 2)}s against a 2.55s teardown")
        # A plate has no discrete early reflections, but it does need a pre-delay
        # or it arrives with the note and is heard as tone colour rather than as
        # space. This pair pins both halves: the gap is quiet, and what follows
        # it is at full density rather than a slow build.
        check("nothing sounds during the pre-delay",
              ir["preGap"] < ir["early"] * 0.15,
              f"first 20ms {ir['preGap']:.6f} against early {ir['early']:.5f}")
        check("the response is dense the moment the pre-delay ends",
              ir["afterGap"] > ir["early"] * 0.5,
              f"30-60ms {ir['afterGap']:.5f} against early {ir['early']:.5f}")
        check("the response decays to a tail", ir["late"] < ir["early"] * 0.05,
              f"late {ir['late']:.6f} against early {ir['early']:.5f}")
        check("the two sides of the plate are decorrelated",
              abs(ir["correlation"]) < 0.15, f"correlation {ir['correlation']:.4f}")
        # Measured on this graph: the convolver's own normalize took a 0.22 send
        # down to 2.8% of what is heard, so the send meant nothing predictable.
        # It is off, and the response carries its own scaling.
        check("the response is scaled by hand, not by the convolver",
              ir["normalize"] is False, f"normalize {ir['normalize']}")
        check("the send reaches the plate through the highpass",
              wiring["sendToHighpass"] and wiring["highpassToConvolver"],
              f"send->hp {wiring['sendToHighpass']}, hp->conv {wiring['highpassToConvolver']}")
        check("the plate reaches the output", wiring["convolverToOutput"])
        check("a voice lands on both the output and the send",
              wiring["voicesIntoSend"] >= 1
              and wiring["voicesIntoOutput"] >= wiring["voicesIntoSend"],
              f"{wiring['voicesIntoSend']} into the send, "
              f"{wiring['voicesIntoOutput']} into the output")

    # The release behaviour, which is the whole reason the first plate could not
    # be heard. Every check above this point passed on that version too: the bus
    # was built, wired, stereo and present in the output, and none of that says
    # anything about whether a tail is ever exposed.
    # The reading that separates a plate you can hear from one you cannot, and
    # the one place to take it. The dry graph is hard disconnected 2.55s after
    # the release, so anything sounding after that instant is the plate alone and
    # nothing else: that window is where a reverb is actually heard. Everything
    # above this point passed on the version Nick could not hear at all.
    #
    # It has to be an absolute level, not a decay rate. A slope check was written
    # first and it is worthless here: with the plate slower than the dry, the wet
    # ends up decaying at the plate's own rate whether it is still being fed or
    # not, so the slope is the same either way. The mutation that reverted the
    # feed walked straight through it.
    TRACK = """(ms) => new Promise(res => {
        const rows = [];
        const t0 = performance.now();
        const id = setInterval(() => {
            rows.push([performance.now() - t0, window.__level().mid, window.__wetLevel()]);
            if (performance.now() - t0 > ms) { clearInterval(id); res(rows); }
        }, 50);
    })"""

    def tail():
        """Press, release, and read the plate in the window after the dry is gone.

        Returned as a share of the note's own peak, so the synth's random pitch
        and the volume setting cannot move it.
        """
        p.mouse.move(cx, cy)
        p.mouse.down()
        p.wait_for_timeout(300)
        peak = max(p.evaluate("() => window.__level().mid") for _ in range(5))
        p.wait_for_timeout(500)
        p.mouse.up()
        rows = p.evaluate(TRACK, 3200)
        p.wait_for_timeout(6000)
        late = [r for r in rows if 2750 <= r[0] <= 3150]
        mid = statistics.median([r[1] for r in late])
        wet = statistics.median([r[2] for r in late])
        return wet / max(peak, 1e-9) * 100, wet / max(mid, 1e-9)

    reads = sorted(tail() for _ in range(3))
    tail_share, only_plate = reads[1]
    check("what is left after the dry is torn down is the plate and nothing else",
          only_plate > 0.9, f"wet is {only_plate:.2f} of the total there")
    # 0.35 sits between two measured populations rather than being picked: the
    # 2.8s send-0.30 plate that shipped as inaudible reads 0.116 to 0.174 here,
    # and this one reads 0.634 to 1.134. Three presses, median, because a plate
    # answers each pitch differently.
    check("the plate is still audibly ringing there",
          tail_share > 0.35,
          f"{tail_share:.3f}% of the note's peak (of "
          f"{[round(r[0], 3) for r in reads]}); the version that could not be "
          f"heard read 0.145%")

    wet_on = hold_and_read()
    shipped_send = p.evaluate("() => plateReverb.send.gain.value")
    p.evaluate("() => { plateReverb.send.gain.value = 0; }")
    wet_off = hold_and_read()
    width_on = wet_on["side"] / max(wet_on["mid"], 1e-9)
    width_off = wet_off["side"] / max(wet_off["mid"], 1e-9)

    check("with the plate silenced the synth is dead mono", width_off < 0.01,
          f"width {width_off:.4f}")
    check("the plate is audible as width on a held note", width_on > 0.06,
          f"width {width_on:.4f} against {width_off:.4f} silenced")
    # Read off the convolver rather than off the total. The total is the wrong
    # place to look: a decorrelated plate at -15dB moves the mid channel by
    # under one percent, so a band drawn there is either unsatisfiable or
    # meaningless.
    #
    # The band here is wide on purpose. The synth draws its pitch at random over
    # four octaves and the plate answers each pitch differently, so this reading
    # came out at 8.4, 11.4, 16.9 and 27.4 percent over four runs with nothing
    # changed. A tight band would fail on a draw rather than on a defect. What
    # pins the magnitude deterministically is the send check below; this pair
    # proves the plate is genuinely in the output and has not swallowed it.
    share = wet_on["wet"] / max(wet_on["mid"], 1e-9)
    check("the plate is present in what is heard", share > 0.03, f"{share * 100:.1f}%")
    check("the plate has not taken the sound over", share < 0.50, f"{share * 100:.1f}%")
    check("silencing the plate leaves nothing wet", wet_off["wet"] < wet_on["wet"] * 0.02,
          f"{wet_off['wet']:.6f} against {wet_on['wet']:.5f}")
    check("the send is set low", 0.1 <= shipped_send <= 0.5, f"send {shipped_send}")

    # The wet comes off the voice, so the volume slider has to take it with it.
    # A plate fed from anywhere else would keep ringing through a muted synth.
    p.evaluate("(v) => { plateReverb.send.gain.value = v; }", shipped_send)
    p.evaluate(
        """() => {
        const s = document.getElementById('synthVolumeSlider');
        s.value = 0;
        s.dispatchEvent(new Event('input', { bubbles: true }));
    }"""
    )
    muted = hold_and_read(500)
    check("pulling the volume down takes the plate with it",
          muted["side"] < wet_on["side"] * 0.1,
          f"side {muted['side']:.6f} against {wet_on['side']:.6f} at full volume")
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

    def asset_width(name):
        """Pixel width of an asset as the server hands it out."""
        req = urllib.request.Request(
            urllib.parse.urljoin(URL, f"images/{name}"),
            headers={"User-Agent": "nick-athens-site verify_hero"},
        )
        return Image.open(io.BytesIO(urllib.request.urlopen(req, timeout=30).read())).size[0]  # noqa: S310,E501

    # Which density each device actually downloads, and how far it then has to
    # stretch it. The grid cover-fits the photo across the viewport, so the
    # pixels asked for are the viewport times the device ratio: reading the CSS
    # width alone says 1278px on a phone and hides a 2x upscale completely.
    for w, h, dpr, want, label in (
        (393, 852, 3, "hero-sky@2x.webp", "phone at ratio 3"),
        (1512, 982, 2, "hero-sky@2x.webp", "laptop at ratio 2"),
        (1920, 1080, 1, "hero-sky.webp", "desktop at ratio 1"),
    ):
        seen = []
        p = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=dpr)
        p.on("response", lambda r, s=seen: s.append(r.url.rsplit("/", 1)[-1])
             if "hero-sky" in r.url else None)
        p.add_init_script("localStorage.setItem('synthDiscovered', 'true');")
        p.goto(URL, wait_until="networkidle")
        p.wait_for_timeout(1600)
        css_w = float(p.evaluate(
            """() => getComputedStyle(
                document.querySelector('.hero-grid .cell')).backgroundSize.split('px')[0]"""
        ))
        p.close()
        fetched = sorted(set(seen))
        check(f"{label} gets the right density", fetched == [want], f"fetched {fetched}")
        # Both densities being fetched would be a silent doubling of the page
        # weight that the density check above would not notice.
        check(f"{label} downloads one file, not both", len(fetched) == 1, f"{fetched}")
        # The width comes out of the bytes the server actually sent, not out of
        # the name that was expected. Deriving it from `want` made this check
        # measure a real 2.0x stretch as 1.25x when a mutation pointed the 2x
        # entry at the 1x file: internally valid, against the wrong reference.
        served_w = asset_width(fetched[0]) if len(fetched) == 1 else 0
        scale = css_w * dpr / served_w if served_w else float("inf")
        check(f"{label} stretches it less than 1.4x", scale < 1.4,
              f"{round(css_w * dpr)} device px from {served_w}, {scale:.2f}x")

    # image-set decides the density, and a browser that cannot parse it must be
    # left with the plain url() rather than with no photo at all. Driven by
    # rejecting the image-set value at the CSSOM, which is exactly what such a
    # browser does, rather than by reading the source for the fallback line.
    p = b.new_page(viewport={"width": 1600, "height": 900})
    p.add_init_script("localStorage.setItem('synthDiscovered', 'true');")
    # Two earlier versions of this blocker failed silently and the check passed
    # anyway, which is worth recording. Patching CSSStyleDeclaration.prototype
    # does nothing, because Blink hangs the CSS properties off each instance: it
    # threw in the init script, the grid never built, and the check read 0 of 0
    # cells as a pass. Reading the instance's own descriptor and guarding on it
    # then skipped the patch entirely and reported the unpatched page. Going
    # through setProperty works because that one really is on the prototype, and
    # the control below is what proves the blocker blocks.
    p.add_init_script(
        """
        const create = document.createElement.bind(document);
        document.createElement = function (tag, ...rest) {
            const el = create(tag, ...rest);
            Object.defineProperty(el.style, 'backgroundImage', {
                configurable: true,
                get: () => el.style.getPropertyValue('background-image'),
                set: v => {
                    if (String(v).includes('image-set')) return;
                    el.style.setProperty('background-image', v);
                },
            });
            return el;
        };
    """
    )
    p.goto(URL, wait_until="networkidle")
    p.wait_for_timeout(1600)
    fb = p.evaluate(
        """() => {
        const c = [...document.querySelectorAll('.hero-grid .cell')];
        return { n: c.length,
                 photo: c.filter(x => (x.style.backgroundImage || '').includes('hero-sky')).length,
                 set: c.filter(x => (x.style.backgroundImage || '').includes('image-set')).length };
    }"""
    )
    p.close()
    check("a browser without image-set still gets the photo",
          fb["n"] > 50 and fb["n"] == fb["photo"] and fb["set"] == 0,
          f"{fb['photo']}/{fb['n']} with a photo, {fb['set']} using image-set")
    # Without this the check above passes on a blocker that blocked nothing.
    p = open_page(b)
    control = p.evaluate(
        """() => [...document.querySelectorAll('.hero-grid .cell')]
                 .filter(x => (x.style.backgroundImage || '').includes('image-set')).length"""
    )
    p.close()
    check("that blocker really does block image-set", control > 50,
          f"{control} cells use image-set unblocked, {fb['set']} blocked")

    # The slice checks above pass whether the sky reads as cloud or as a smear,
    # which is how the first version shipped as a colour wash. These score the
    # asset the server actually hands out, through the portrait crop a phone
    # gets, which is the strict view: it keeps under a third of the frame.
    # Cloudflare sits in front of the live domain and answers the default
    # urllib agent with 403, so the run against production died before it
    # reached these checks rather than reporting anything about the sky.
    asset = urllib.request.Request(
        urllib.parse.urljoin(URL, "images/hero-sky.webp"),
        headers={"User-Agent": "nick-athens-site verify_hero"},
    )
    served = urllib.request.urlopen(asset, timeout=30).read()  # noqa: S310
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

    # The grain is not decoration. The grade multiplies the regional chroma five
    # times and leans on the grain to dither those gradients, so an encoder that
    # smooths it away takes the dithering with it and the sky separates into
    # patches. The cloud-form check above passes on a grainless file: it reads a
    # band far coarser than a grain of film. This reads the grain itself, off the
    # asset a phone is actually handed.
    asset2x = urllib.request.Request(
        urllib.parse.urljoin(URL, "images/hero-sky@2x.webp"),
        headers={"User-Agent": "nick-athens-site verify_hero"},
    )
    big = Image.open(io.BytesIO(urllib.request.urlopen(asset2x, timeout=30).read()))  # noqa: S310
    big = big.convert("RGB")
    grain2x = build_hero_image.grain(big)
    check("the 2x asset is the scan's own width", big.size[0] >= 3072, f"{big.size[0]}px")
    # 1.01 is what the 1920/q82 asset that shipped as mush measured. The floor
    # sits above it so this cannot be satisfied by the file it replaced.
    check("the phone's asset kept its film grain", grain2x > 2.5,
          f"grain {grain2x:.2f}, the smoothed asset it replaces scored 1.01")
    b.close()

print("\n" + ("ALL PASS" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}"))
sys.exit(1 if FAILS else 0)
