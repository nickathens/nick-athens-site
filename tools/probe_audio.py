#!/usr/bin/env python3
"""Measure the shipped synth's real output, wet and dry, through a live tap.

The page's own ctx.destination is replaced with a gain node that everything
lands on, so this reads the graph the site actually builds rather than a copy
of it. A second analyser hangs off the shipped convolver, which gives the wet
level on its own.

  python tools/probe_audio.py            envelope at the shipped send
  python tools/probe_audio.py --send 0   the same note with the plate silent
  python tools/probe_audio.py --wav out.webm --send 0.4   record it to a file

Usage: python tools/probe_audio.py [--url U] [--send X] [--wav PATH] [--hold MS]
"""
import argparse
import base64
import statistics
import sys

from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument("--url", default="http://127.0.0.1:8777/index.html")
ap.add_argument("--send", type=float, default=None, help="override PLATE_SEND")
ap.add_argument("--wav", default=None, help="record the tap to this .webm")
ap.add_argument("--hold", type=int, default=700)
ap.add_argument("--wave", default=None)
ap.add_argument("--quiet", action="store_true")
ap.add_argument("--phrase", type=int, default=0, help="press N cells in a row instead of one")
A = ap.parse_args()

TAP = """
window.__env = [];
const RealAC = window.AudioContext || window.webkitAudioContext;
const destDesc = Object.getOwnPropertyDescriptor(
    window.BaseAudioContext.prototype, 'destination');
function Patched() {
    const ctx = new RealAC();
    const tap = ctx.createGain();
    const an = ctx.createAnalyser();
    an.fftSize = 2048;
    tap.connect(an);
    an.connect(destDesc.get.call(ctx));
    Object.defineProperty(ctx, 'destination', { get: () => tap, configurable: true });
    window.__an = an;
    window.__tap = tap;
    window.__ctx = ctx;
    window.__realDest = destDesc.get.call(ctx);
    return ctx;
}
window.AudioContext = Patched;
window.webkitAudioContext = Patched;

// A second analyser on the shipped convolver: an extra connection changes no
// audio, and it is the only way to read the wet on its own.
// plateReverb is a top level `let`, which is a script scope binding and not a
// window property, so it is reached by bare name. Reading it off window returns
// undefined and would report the bus as missing while it is plainly there.
window.__tapWet = () => {
    if (typeof plateReverb === 'undefined' || !plateReverb) return false;
    const wet = window.__ctx.createAnalyser();
    wet.fftSize = 2048;
    plateReverb.convolver.connect(wet);
    window.__anWet = wet;
    return true;
};

window.__record = () => {
    const buf = new Float32Array(window.__an.fftSize);
    const wetBuf = new Float32Array(window.__an.fftSize);
    const rms = (an, b) => {
        if (!an) return null;
        an.getFloatTimeDomainData(b);
        let s = 0;
        for (let i = 0; i < b.length; i++) s += b[i] * b[i];
        return Math.sqrt(s / b.length);
    };
    window.__t0 = performance.now();
    setInterval(() => {
        window.__env.push([
            Math.round(performance.now() - window.__t0),
            rms(window.__an, buf),
            rms(window.__anWet, wetBuf),
        ]);
    }, 40);
};

window.__startRec = () => {
    const dest = window.__ctx.createMediaStreamDestination();
    window.__tap.connect(dest);
    window.__chunks = [];
    const rec = new MediaRecorder(dest.stream, { mimeType: 'audio/webm' });
    rec.ondataavailable = e => window.__chunks.push(e.data);
    rec.start();
    window.__rec = rec;
};
window.__stopRec = () => new Promise(resolve => {
    window.__rec.onstop = async () => {
        const blob = new Blob(window.__chunks, { type: 'audio/webm' });
        const bytes = new Uint8Array(await blob.arrayBuffer());
        let s = '';
        for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
        resolve(btoa(s));
    };
    window.__rec.stop();
});
"""

with sync_playwright() as pw:
    b = pw.chromium.launch()
    p = b.new_page(viewport={"width": 1600, "height": 900})
    p.add_init_script("localStorage.setItem('synthDiscovered', 'true');")
    p.add_init_script(TAP)
    p.goto(A.url, wait_until="networkidle")
    p.wait_for_timeout(1200)
    p.evaluate("() => { for (let i = 1; i < 99999; i++) clearInterval(i); }")

    if A.wave:
        p.click(f'#waveSelect .wave-option[data-wave="{A.wave}"]')

    box = p.evaluate(
        """() => {
        const c = [...document.querySelectorAll('.hero-grid .cell:not(.logo-cell)')];
        const r = c[40].getBoundingClientRect();
        return [r.x + r.width / 2, r.y + r.height / 2];
    }"""
    )
    # The page builds its context lazily on the first gesture, so neither the
    # tap nor the reverb bus exists until something has been pressed.
    p.mouse.click(box[0], box[1])
    p.wait_for_timeout(3600)

    built = p.evaluate("() => typeof plateReverb !== 'undefined' && !!plateReverb")
    wet_tapped = p.evaluate("() => window.__tapWet()")
    if A.send is not None:
        p.evaluate("(v) => { plateReverb.send.gain.value = v; }", A.send)
    send = p.evaluate("() => plateReverb ? plateReverb.send.gain.value : null")

    p.evaluate("() => window.__record()")
    if A.wav:
        p.evaluate("() => window.__startRec()")
        p.wait_for_timeout(400)
    if A.phrase:
        # A run of presses with gaps between them: a plate is heard in the gaps,
        # not under a single sustained tone, so a one note probe understates it.
        cells = p.evaluate(
            """(n) => {
            const c = [...document.querySelectorAll('.hero-grid .cell:not(.logo-cell)')];
            const picks = [40, 22, 57, 31, 66, 13, 49, 70];
            return picks.slice(0, n).map(i => {
                const r = c[i].getBoundingClientRect();
                return [r.x + r.width / 2, r.y + r.height / 2];
            });
        }""",
            A.phrase,
        )
        for cx, cy in cells:
            p.mouse.move(cx, cy)
            p.mouse.down()
            p.wait_for_timeout(A.hold)
            p.mouse.up()
            p.wait_for_timeout(650)
        p.wait_for_timeout(5000)
    else:
        p.mouse.move(box[0], box[1])
        p.mouse.down()
        p.wait_for_timeout(A.hold)
        p.mouse.up()
        p.wait_for_timeout(5000)
    env = p.evaluate("() => window.__env")
    if A.wav:
        data = p.evaluate("() => window.__stopRec()")
        with open(A.wav, "wb") as fh:
            fh.write(base64.b64decode(data))
    p.close()
    b.close()

release_at = A.hold
print(f"reverb bus built: {built}   wet analyser: {wet_tapped}   send: {send}")
print(f"samples: {len(env)}")

tot = [(t, v) for t, v, _ in env if v is not None]
wet = [(t, w) for t, _, w in env if w is not None]
peak = max((v for _, v in tot), default=0)
wet_peak = max((w for _, w in wet), default=0)


def during(rows, a, bnd):
    vals = [v for t, v in rows if a <= t <= bnd]
    return statistics.mean(vals) if vals else 0.0


held_tot = during(tot, 150, release_at - 50)
held_wet = during(wet, 150, release_at - 50)
print(f"peak total {peak:.5f}   peak wet {wet_peak:.5f}")
# The held window only means anything for a single press. In phrase mode it
# lands wherever the run happens to be and the ratio it prints is noise.
if held_tot and not A.phrase:
    print(f"while held: total {held_tot:.5f}, wet {held_wet:.5f} "
          f"= {held_wet / held_tot * 100:.1f}% of what is heard")

# The dry path is hard disconnected 2.55s after release, so anything still
# sounding past that point can only be the plate.
cutoff = release_at + 2550
after = [(t, v) for t, v in tot if t > cutoff + 60]
alive = [t for t, v in after if v > 1e-5]
print(f"after the dry graph is torn down at {cutoff}ms: "
      f"{'rings to ' + str(max(alive)) + 'ms' if alive else 'silent'}")

if not A.quiet:
    for t, v, w in env[::4]:
        bar = "#" * int((v or 0) * 400)
        wbar = "+" * int((w or 0) * 400)
        mark = "  <- release" if abs(t - release_at) < 25 else ""
        print(f"{t:6d} ms  {v:.5f} {(w if w is not None else 0):.5f}  {bar}{wbar}{mark}")
sys.exit(0)
