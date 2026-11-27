"""Check a replacement vocal track against the score before remixing.

usage: python3 tools/check_vocals.py NEW_VOCAL.(wav|flac) [GUIDE.flac]
  GUIDE defaults to output/stems_flac/solo_1_dry.flac (the MBROLA guide it was converted from)

Reports:
  * timing: overall offset and worst per-phrase offset vs the guide (envelope cross-correlation)
    -> want |offset| < 20 ms everywhere; otherwise pad/trim the file (the timeline must start at MIDI t=0)
  * pitch: median |cents| error per sung note vs output/vocal_score.json (autocorrelation f0)
    -> want median < 30 cents, and no long runs of notes > 100 cents (octave/key mistakes)
Intelligibility is not checked here; run Whisper on the file and compare with the lyrics (see HANDOFF.md).
"""
import json, os, subprocess, sys
import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), '..')
SR = 16000


def load(p):
    raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', p, '-f', 's16le', '-ac', '1', '-ar', str(SR), '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def env(a, hop=160):
    n = len(a) // hop
    return np.sqrt((a[:n * hop].reshape(n, hop) ** 2).mean(1))


def xcorr_offset(a, b, max_lag):
    a = (a - a.mean()) / (a.std() + 1e-9); b = (b - b.mean()) / (b.std() + 1e-9)
    best, lag = -1e9, 0
    for L in range(-max_lag, max_lag + 1):
        x = a[max(0, L):len(a) + min(0, L)]; y = b[max(0, -L):len(b) - max(0, L)]
        n = min(len(x), len(y))
        c = float((x[:n] * y[:n]).mean()) if n else -1e9
        if c > best:
            best, lag = c, L
    return lag


def f0(seg):
    seg = seg - seg.mean()
    if np.abs(seg).max() < 0.01:
        return None
    c = np.correlate(seg, seg, 'full')[len(seg) - 1:]
    lo, hi = int(SR / 900), int(SR / 150)
    i = lo + int(np.argmax(c[lo:hi]))
    return SR / i


def main():
    new = load(sys.argv[1])
    guide = load(sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'output/stems_flac/solo_1_dry.flac'))
    score = json.load(open(os.path.join(ROOT, 'output/vocal_score.json')))
    En, Eg = env(new), env(guide)          # 10 ms frames
    lag = xcorr_offset(En, Eg, 50)
    print(f'overall offset: {lag * 10:+d} ms (positive = new vocal is late)')
    worst = 0
    for ph in score['phrases']:
        a, b = int(ph['start'] * 100), int(ph['end'] * 100) + 10
        if b > len(En) or b > len(Eg):
            continue
        l = xcorr_offset(En[a:b], Eg[a:b], 10)
        worst = max(worst, abs(l))
    print(f'worst per-phrase offset: {worst * 10} ms')
    errs = []
    for ph in score['phrases']:
        for n in ph['notes']:
            t0, t1 = n['start'], n['end']
            mid = t0 + 0.55 * (t1 - t0)
            seg = new[int(mid * SR): int(mid * SR) + 1024]
            f = f0(seg) if len(seg) == 1024 else None
            if f is None:
                continue
            c = 1200 * np.log2(f / (440 * 2 ** ((n['midi'] - 69) / 12)))
            errs.append(abs(c))
    errs = np.array(errs)
    print(f'pitch: {len(errs)} notes measured, median {np.median(errs):.0f} cents, '
          f'{(errs > 100).mean() * 100:.0f}% of notes > 100 cents off')


if __name__ == '__main__':
    main()
