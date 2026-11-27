"""Synthesize the vocal line (MBROLA diphone singing) and mix it with the piano.

Child timbre: each voice is synthesized with every pitch divided by k and every duration
multiplied by k, then resampled ('sox speed k'). That restores pitch and timing and raises
the formants by k, which shortens the vocal tract the way a child's is shorter.

python3 src/sing.py solo      -> output/..._girl_solo.mp3
python3 src/sing.py chorus    -> output/..._childrens_chorus.mp3
python3 src/sing.py midi      -> output/..._with_melody.mid (melody track + lyric events)
python3 src/sing.py stems     -> output/stems/ (piano.wav + dry voice wavs, not committed)
python3 src/sing.py score-json -> output/vocal_score.json (notes, seconds, lyrics, phonemes)
python3 src/sing.py remix solo|chorus DIR -> mix DIR/<kind>_N.wav|.flac with output/stems_flac/piano.flac -> *_neural.mp3
"""
import os, sys, re, math, random, subprocess, tempfile, wave
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import mido
from lyrics import melody_events

ROOT = os.path.join(os.path.dirname(__file__), '..')
OUT = os.path.join(ROOT, 'output')
BASE = 'living_the_gospel_of_jesus_christ'
MBROLA_DB = '/usr/share/mbrola/us1/us1'
SF = os.environ.get('SF', '/usr/share/sounds/sf2/MuseScore_General_Full.sf2')
SR = 44100

VOWELS = {'i', 'I', 'E', '{', 'A', 'V', 'O', 'U', 'u', '@', 'r=', 'EI', 'AI', 'OI', '@U', 'aU'}
UNVOICED = {'p', 't', 'k', 'p_h', 't_h', 'k_h', 'f', 'T', 's', 'S', 'h', 'tS'}

# syllable splits where espeak's phonemes need help: word -> list of syllables (phoneme lists)
OVERRIDES = {
    'live': [['l', 'I', 'v']],
    'gospel': [['g', 'A', 's'], ['p', '@', 'l']],
    'faithful': [['f', 'EI', 'T'], ['f', '@', 'l']],
    "cov'nants": [['k_h', 'V', 'v'], ['n', '@', 'n', 't', 's']],
    'Caring': [['k_h', 'E', 'r'], ['I', 'N']],
    'parents': [['p_h', 'E', 'r'], ['@', 'n', 't', 's']],
    'Oh': [['@U']],
    'I': [['AI']],
    'the': [['D', '@']],
}
CONS_MS = {'s': 95, 'S': 100, 'f': 85, 'T': 80, 'h': 60, 'tS': 110, 'dZ': 80, 'z': 70,
           'k_h': 90, 'p_h': 85, 't_h': 85, 'k': 70, 'p': 70, 't': 65, 'b': 55, 'd': 55, 'g': 60,
           'l': 60, 'r': 55, 'w': 60, 'j': 55, 'm': 70, 'n': 65, 'N': 70, 'v': 60, 'D': 45}

_cache = {}


def phonemize(word):
    if word in OVERRIDES:
        return OVERRIDES[word]
    w = word.lower()
    if w in _cache:
        return _cache[w]
    out = subprocess.run(['espeak-ng', '-v', 'mb-us1', '-q', '--pho', word.replace("'", "’") if False else word],
                         capture_output=True, text=True).stdout
    ph = [l.split()[0] for l in out.splitlines() if l.strip() and l.split()[0] not in ('_', ':')]
    _cache[w] = ph
    return ph


def split_syllables(word, n):
    ph = phonemize(word)
    if ph and isinstance(ph[0], list):
        assert len(ph) == n, (word, ph, n)
        return ph
    nuc = [i for i, p in enumerate(ph) if p in VOWELS]
    if len(nuc) != n:
        raise ValueError(f'{word}: {ph} has {len(nuc)} vowels, score has {n} syllables')
    sylls, start = [], 0
    for j in range(n):
        if j == n - 1:
            sylls.append(ph[start:]); break
        a, b = nuc[j], nuc[j + 1]
        between = b - a - 1
        cut = a + 1 + (0 if between <= 1 else 1)
        sylls.append(ph[start:cut]); start = cut
    return sylls


def beat_to_sec_fn(midi_path):
    mid = mido.MidiFile(midi_path)
    ppq = mid.ticks_per_beat
    tempos, t = [], 0
    for msg in mid.tracks[0]:
        t += msg.time
        if msg.type == 'set_tempo':
            tempos.append((t, msg.tempo))
    tempos.sort()
    # cumulative seconds at each tempo change
    segs, sec, last_t, last_tempo = [], 0.0, 0, 500000
    for tk, tp in tempos:
        sec += (tk - last_t) / ppq * last_tempo / 1e6
        segs.append((tk, sec, tp)); last_t, last_tempo = tk, tp

    def f(beat):
        tk = beat * ppq
        s0 = segs[0]
        for s in segs:
            if s[0] <= tk:
                s0 = s
            else:
                break
        return s0[1] + (tk - s0[0]) / ppq * s0[2] / 1e6
    return f


def hz(m, cents=0.0):
    return 440.0 * 2 ** ((m - 69 + cents / 100.0) / 12)


def build_syllables(events, b2s):
    """-> list of syllable dicts with phoneme split and note list in seconds."""
    sylls = []
    for e in events:
        if e.get('cont'):
            sylls[-1]['notes'].append((b2s(e['start']), b2s(e['end']), e['midi']))
            sylls[-1]['phrase_end'] = e.get('phrase_end', False)
            continue
        sylls.append(dict(text=e['syl'], word=e['word'], wpos=e['wpos'], wlen=e['wlen'],
                          notes=[(b2s(e['start']), b2s(e['end']), e['midi'])],
                          phrase_end=e.get('phrase_end', False), fermata=e.get('fermata')))
    words = {}
    for s in sylls:
        key = (s['word'], s['wlen'])
        if key not in words:
            words[key] = split_syllables(s['word'], s['wlen'])
        ph = words[key][s['wpos']]
        nuc = [i for i, p in enumerate(ph) if p in VOWELS]
        v = nuc[0]
        s['onset'], s['vowel'], s['coda'] = ph[:v], ph[v], ph[v + 1:]
        long_note = s['notes'][-1][1] - s['notes'][0][0] >= 0.45
        s['breath'] = s['phrase_end'] or (long_note and bool(re.search(r'[,.!;”]$', s['text'])))
    return sylls


def make_pho(sylls, k, rnd, timing_sd=0.0, detune=0.0, vib_rate=5.5, vib_depth=18.0,
             vib_delay=0.30, scoop=25.0):
    """Return MBROLA .pho text (durations x k, pitches / k)."""
    lines = []
    cursor = 0.0  # seconds (unscaled)
    drift_phase = rnd.uniform(0, 6.28)

    def emit(ph, dur, pitch_pts=None):
        nonlocal cursor
        dur = max(dur, 0.012)
        ms = int(round(dur * 1000 * k))
        if pitch_pts:
            pts = ' '.join(f'{int(p)} {f / k:.1f}' for p, f in pitch_pts)
            lines.append(f'{ph} {ms} {pts}')
        else:
            lines.append(f'{ph} {ms}')
        cursor += ms / 1000.0 / k

    prev_midi = None
    for i, s in enumerate(sylls):
        jit = rnd.gauss(0, timing_sd) if timing_sd else 0.0
        t0 = s['notes'][0][0] + jit
        t_end = s['notes'][-1][1] + jit
        nxt = sylls[i + 1]['notes'][0][0] if i + 1 < len(sylls) else t_end + 1
        onset_d = [CONS_MS.get(p, 60) / 1000.0 for p in s['onset']]
        coda_d = [CONS_MS.get(p, 60) / 1000.0 for p in s['coda']]
        # vowel lands ~20 ms after the beat; onset consonants come before it
        v_start = t0 + 0.02
        c_start = v_start - sum(onset_d)
        if c_start < cursor:                      # squeeze if the previous syllable overran
            scale = max(0.4, (v_start - cursor) / max(sum(onset_d), 1e-3))
            onset_d = [d * scale for d in onset_d]
            c_start = v_start - sum(onset_d)
        if c_start - cursor > 0.001:
            emit('_', c_start - cursor)
        else:
            c_start = cursor
        m0 = s['notes'][0][2]
        for p, d in zip(s['onset'], onset_d):
            emit(p, d, None if p in UNVOICED else [(0, hz(m0, detune)), (100, hz(m0, detune))])
        # end of the vowel
        if s['breath']:
            release = t_end - (0.10 if nxt - t_end < 0.3 else 0.03)
            coda_d = [d * 0.8 for d in coda_d]
        else:
            release = min(t_end, nxt) - 0.01 - 0.6 * sum(CONS_MS.get(p, 60) / 1000.0 for p in sylls[i + 1]['onset']) \
                if i + 1 < len(sylls) else t_end
        v_end = max(cursor + 0.06, release - sum(coda_d))
        vdur = v_end - cursor
        # pitch contour across the vowel (melisma-aware), sampled every ~25 ms
        n_pts = max(2, min(60, int(vdur / 0.025)))
        pts = []
        for j in range(n_pts + 1):
            frac = j / n_pts
            t = cursor + frac * vdur
            # current note
            cur = s['notes'][0]
            for nt in s['notes']:
                if t + jit >= nt[0] - 0.01:
                    cur = nt
            m = cur[2]
            ni = s['notes'].index(cur)
            since = t - (cur[0] + jit)
            cents = detune + 4 * math.sin(drift_phase + t * 0.7)
            # glide from previous pitch
            pm = s['notes'][ni - 1][2] if ni > 0 else prev_midi
            if pm is not None and since < 0.07:
                cents += (pm - m) * 100 * (1 - max(0, since) / 0.07) * (0.6 if ni == 0 else 1.0)
            elif pm is None and since < 0.08:
                cents -= scoop * (1 - max(0, since) / 0.08)
            # vibrato after a delay, faded in
            held = t - (s['notes'][0][0] + jit)
            if held > vib_delay:
                amt = min(1.0, (held - vib_delay) / 0.25)
                cents += vib_depth * amt * math.sin(2 * math.pi * vib_rate * held)
            pts.append((round(frac * 100), hz(m, cents)))
        # merge duplicate percent points
        clean, seen = [], set()
        for p, f in pts:
            if p not in seen:
                clean.append((p, f)); seen.add(p)
        emit(s['vowel'], vdur, clean)
        mlast = s['notes'][-1][2]
        for p, d in zip(s['coda'], coda_d):
            emit(p, d, None if p in UNVOICED else [(0, hz(mlast, detune)), (100, hz(mlast, detune))])
        prev_midi = None if s['breath'] else mlast
    emit('_', 0.5)
    return '\n'.join(lines) + '\n'


def synth_voice(pho, k, path):
    with tempfile.TemporaryDirectory() as td:
        pf, raw = os.path.join(td, 'v.pho'), os.path.join(td, 'v.wav')
        open(pf, 'w').write(pho)
        subprocess.run(['mbrola', '-e', MBROLA_DB, pf, raw], check=True)
        # speed k: restores pitch/timing, raises formants; then gentle EQ for a lighter child tone
        subprocess.run(['sox', raw, '-r', str(SR), path, 'speed', f'{k:.4f}', 'rate', '-v', str(SR),
                        'highpass', '160', 'equalizer', '3000', '1.2q', '3', 'treble', '2', '8000'],
                       check=True)


def read_wav(path):
    with wave.open(path) as w:
        n, ch, sw = w.getnframes(), w.getnchannels(), w.getsampwidth()
        a = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768
        return a.reshape(-1, ch) if ch > 1 else a[:, None]


def write_wav(path, a):
    a = np.clip(a, -1, 1)
    with wave.open(path, 'wb') as w:
        w.setnchannels(a.shape[1]); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((a * 32767).astype(np.int16).tobytes())


SINGERS = {
    # name: list of (k formant ratio, pan -1..1, gain, timing sd, detune cents, vib rate, vib depth)
    'solo': [(1.17, 0.0, 1.0, 0.0, 0.0, 5.6, 14.0)],
    'chorus': [(1.13, -0.45, 0.9, 0.018, -6.0, 5.2, 10.0),
               (1.19, -0.15, 1.0, 0.016, 4.0, 5.9, 8.0),
               (1.22, 0.20, 0.85, 0.020, -3.0, 5.5, 12.0),
               (1.16, 0.45, 0.95, 0.017, 7.0, 6.2, 9.0),
               (1.25, 0.05, 0.75, 0.022, -9.0, 5.0, 6.0)],
}


LABEL = {'solo': 'girl_solo', 'chorus': 'childrens_chorus'}
PAN_GAIN = {kind: [(v[1], v[2]) for v in vs] for kind, vs in SINGERS.items()}


def render_piano(path):
    midi = os.path.join(OUT, BASE + '.mid')
    subprocess.run(['fluidsynth', '-ni', '-q', '-g', '0.6', '-r', str(SR), '-R', '1', '-C', '0',
                    '-o', 'synth.reverb.room-size=0.45', '-o', 'synth.reverb.level=0.5',
                    '-F', path, SF, midi], check=True)


def synth_dry_voices(kind, outdir):
    """Write one dry mono wav per singer (timeline starts at MIDI time 0). Returns paths."""
    b2s = beat_to_sec_fn(os.path.join(OUT, BASE + '.mid'))
    sylls = build_syllables(melody_events(), b2s)
    paths = []
    for i, (k, pan, gain, tsd, det, vr, vd) in enumerate(SINGERS[kind]):
        rnd = random.Random(100 + i)
        pho = make_pho(sylls, k, rnd, timing_sd=tsd, detune=det, vib_rate=vr, vib_depth=vd)
        p = os.path.join(outdir, f'{kind}_{i + 1}_dry.wav')
        synth_voice(pho, k, p)
        paths.append(p)
    return paths


def mix_to_mp3(kind, piano_wav, voice_wavs, out):
    """Pan/sum the dry voices, add reverb, put the voice ~3 dB over the piano, export MP3."""
    with tempfile.TemporaryDirectory() as td:
        P = read_wav(piano_wav)
        if P.shape[1] == 1:
            P = np.repeat(P, 2, 1)
        V = np.zeros((len(P) + SR * 2, 2), np.float32)
        pg = PAN_GAIN[kind]
        for i, vp in enumerate(voice_wavs):
            pan, gain = pg[i % len(pg)]
            a = read_wav(vp).mean(1)
            a = a / (np.abs(a).max() + 1e-9) * gain
            n = min(len(a), len(V))
            l, r = math.cos((pan + 1) * math.pi / 4), math.sin((pan + 1) * math.pi / 4)
            V[:n, 0] += a[:n] * l; V[:n, 1] += a[:n] * r
        vraw = os.path.join(td, 'vox.wav')
        write_wav(vraw, V / (np.abs(V).max() + 1e-9) * 0.9)
        vrev = os.path.join(td, 'voxrev.wav')
        rev = '35' if kind == 'solo' else '50'
        subprocess.run(['sox', vraw, vrev, 'reverb', rev, '50', '80', '100', '12', '0'], check=True)
        Vr = read_wav(vrev)
        n = max(len(P), len(Vr))
        mix = np.zeros((n, 2), np.float32)
        mix[:len(P)] += P * (0.55 / (np.abs(P).max() + 1e-9))
        mix[:len(Vr)] += Vr[:, :2] * (1.0 if kind == 'solo' else 1.1)   # voice ~3 dB over piano
        mixp = os.path.join(td, 'mix.wav')
        write_wav(mixp, mix / (np.abs(mix).max() + 1e-9) * 0.95)
        label = LABEL[kind]
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', mixp, '-af',
                        'silenceremove=start_periods=1:start_threshold=-60dB,areverse,'
                        'silenceremove=start_periods=1:start_threshold=-70dB,afade=t=in:st=0:d=0.5,areverse,'
                        'loudnorm=I=-16:TP=-1.5:LRA=11',
                        '-ar', str(SR), '-codec:a', 'libmp3lame', '-b:a', '192k',
                        '-metadata', f'title=Living the Gospel of Jesus Christ ({label.replace("_", " ")})',
                        '-metadata', 'artist=Kathleen Kelly and Natalie Adams', out], check=True)
    print('wrote', out)


def main(kind):
    with tempfile.TemporaryDirectory() as td:
        piano = os.path.join(td, 'piano.wav')
        render_piano(piano)
        voices = synth_dry_voices(kind, td)
        mix_to_mp3(kind, piano, voices, os.path.join(OUT, f'{BASE}_{LABEL[kind]}.mp3'))


def write_stems(d):
    """output/stems/: piano.wav + every dry MBROLA voice, all starting at MIDI time 0."""
    os.makedirs(d, exist_ok=True)
    render_piano(os.path.join(d, 'piano.wav'))
    for kind in SINGERS:
        for p in synth_dry_voices(kind, d):
            print('wrote', p)


SAMPA2ARPA = {'i': 'iy', 'I': 'ih', 'E': 'eh', '{': 'ae', 'A': 'aa', 'V': 'ah', 'O': 'ao', 'U': 'uh',
              'u': 'uw', '@': 'ah', 'r=': 'er', 'EI': 'ey', 'AI': 'ay', 'OI': 'oy', '@U': 'ow', 'aU': 'aw',
              'p': 'p', 'p_h': 'p', 't': 't', 't_h': 't', 'k': 'k', 'k_h': 'k', 'b': 'b', 'd': 'd', 'g': 'g',
              'f': 'f', 'v': 'v', 'T': 'th', 'D': 'dh', 's': 's', 'z': 'z', 'S': 'sh', 'Z': 'zh', 'h': 'hh',
              'tS': 'ch', 'dZ': 'jh', 'm': 'm', 'n': 'n', 'N': 'ng', 'l': 'l', 'r': 'r', 'w': 'w', 'j': 'y'}


def score_json(path):
    """Engine-neutral vocal score: every sung note with seconds, lyric, phonemes (SAMPA + ARPAbet)."""
    import json
    b2s = beat_to_sec_fn(os.path.join(OUT, BASE + '.mid'))
    sylls = build_syllables(melody_events(), b2s)
    names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    phrases, cur = [], []
    for s in sylls:
        ph = s['onset'] + [s['vowel']] + s['coda']
        for j, (t0, t1, m) in enumerate(s['notes']):
            cur.append(dict(start=round(t0, 4), end=round(t1, 4), midi=m,
                            note=f'{names[m % 12]}{m // 12 - 1}',
                            lyric=s['text'] if j == 0 else '-', word=s['word'],
                            slur=j > 0,
                            phonemes_sampa=ph if j == 0 else [],
                            phonemes_arpabet=[SAMPA2ARPA[p] for p in ph] if j == 0 else []))
        if s['breath']:
            phrases.append(cur); cur = []
    if cur:
        phrases.append(cur)
    doc = dict(title='Living the Gospel of Jesus Christ', tempo_note='times in seconds from MIDI tick 0; '
               'matches output/living_the_gospel_of_jesus_christ.mid and output/stems/piano.wav',
               phrases=[dict(start=p[0]['start'], end=p[-1]['end'], notes=p) for p in phrases])
    json.dump(doc, open(path, 'w'), indent=1, ensure_ascii=False)
    print('wrote', path, len(phrases), 'phrases', sum(len(p) for p in phrases), 'notes')


def remix(kind, voice_dir):
    """Re-mix with replacement vocals (e.g. after neural voice conversion).
    Expects <voice_dir>/<kind>_N.wav (N = 1.. number of singers), aligned to MIDI time 0."""
    n = len(SINGERS[kind])
    with tempfile.TemporaryDirectory() as td:
        def as_wav(p):
            if p.endswith('.wav'):
                return p
            q = os.path.join(td, os.path.basename(p) + '.wav')
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', p, '-ar', str(SR), q], check=True)
            return q
        voices = []
        for i in range(n):
            for ext in ('.wav', '.flac'):
                p = os.path.join(voice_dir, f'{kind}_{i + 1}{ext}')
                if os.path.exists(p):
                    voices.append(as_wav(p)); break
        assert voices, f'no {kind}_N.wav/.flac files in {voice_dir}'
        stem = os.path.join(OUT, 'stems_flac', 'piano.flac')
        if os.path.exists(stem):
            piano = as_wav(stem)
        else:
            piano = os.path.join(td, 'piano.wav')
            render_piano(piano)
        mix_to_mp3(kind, piano, voices, os.path.join(OUT, f'{BASE}_{LABEL[kind]}_neural.mp3'))


def melody_midi():
    """Piano MIDI + a 'Melody' track (Choir Aahs) carrying the sung line and lyric events."""
    mid = mido.MidiFile(os.path.join(OUT, BASE + '.mid'))
    ppq = mid.ticks_per_beat
    ab = []
    for e in melody_events():
        on, off = int(e['start'] * ppq), int(e['end'] * ppq) - 20
        if not e.get('cont'):
            syl = e['syl'].replace('’', "'").replace('“', '"').replace('”', '"') + ('-' if e['joins'] else ' ')
            ab.append((on, 0, mido.MetaMessage('lyrics', text=syl)))
        ab.append((on, 2, mido.Message('note_on', note=e['midi'], velocity=80, channel=1)))
        ab.append((off, 1, mido.Message('note_off', note=e['midi'], velocity=0, channel=1)))
    ab.sort(key=lambda x: (x[0], x[1]))
    tr = mido.MidiTrack()
    tr.append(mido.MetaMessage('track_name', name='Melody (vocal line)', time=0))
    tr.append(mido.Message('program_change', program=52, channel=1, time=0))
    last = 0
    for t, _, m in ab:
        tr.append(m.copy(time=t - last)); last = t
    mid.tracks.append(tr)
    path = os.path.join(OUT, BASE + '_with_melody.mid')
    mid.save(path)
    print('wrote', path)


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'solo'
    if cmd == 'midi':
        melody_midi()
    elif cmd == 'stems':
        write_stems(os.path.join(OUT, 'stems'))
    elif cmd == 'score-json':
        score_json(os.path.join(OUT, 'vocal_score.json'))
    elif cmd == 'remix':          # python3 src/sing.py remix solo|chorus <dir>
        remix(sys.argv[2], sys.argv[3])
    else:
        main(cmd)
