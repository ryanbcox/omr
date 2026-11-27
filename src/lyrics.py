"""Vocal melody + lyrics, aligned to the transcription.

Lyric syllables are read (with x positions) from the PDF text layer and attached to the
nearest melody onset in the same system. Melody = top note of RH voice 0 (the printed
piano part doubles the tune; 'soft' fill voices are excluded).

melody_events(verse) -> list of dicts: start/end (beats, absolute performance timeline),
    midi, syl (text), word (whole word), wpos (index of syllable within word), cont (melisma continuation)
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import pymupdf as fitz
from transcription import M, performance_order
from build import parse_voice, midi_num

PDF = os.path.join(os.path.dirname(__file__), '..', 'score', 'living_the_gospel_of_jesus_christ.pdf')
TOOLS = os.path.join(os.path.dirname(__file__), '..', 'tools')
sys.path.insert(0, TOOLS)

# measures per printed system (page, system index) in written order
SYSTEMS = {
    (0, 0): ['i0', 'i1', 'i2', 'i3', 'i4'],
    (0, 1): ['v0', 'a1', 'a2'],
    (0, 2): ['a3', 'a4'],
    (0, 3): ['a5', 'a6'],
    (1, 0): ['a7', 'a8'],
    (1, 1): ['a9', 'a10', 'a11'],
    (1, 2): ['a12', 'e1', 'e2'],
    (1, 3): ['e3', 'e4', 'f1'],
    (1, 4): ['f2', 'f3', 'f4'],
}
# lyric rows (page, baseline y) -> verses they apply to. 'next' = sung as pickup into next verse.
ROWS = {
    (0, 284): [1], (0, 296): [2], (0, 308): [3], (0, 320): [4],
    (0, 446): [1], (0, 458): [2], (0, 470): [3], (0, 482): [4],
    (0, 610): [1], (0, 622): [2], (0, 634): [3], (0, 646): [4],
    (1, 99): [1], (1, 111): [2], (1, 123): [3], (1, 135): [4], (1, 117): [1, 2, 3, 4],
    (1, 264): [1, 2, 3, 4],
    (1, 401): [1, 2, 3, 4],
    (1, 539): [2], (1, 552): [3, 4], (1, 564): [4],     # "2./3./4. Oh, the" pickups (+ 4th ending text)
    (1, 695): [4],
}
VOCAL_MEASURES = {'v0', 'e1', 'e2', 'e4', 'f1', 'f2', 'f3', 'f4'} | {'a%d' % i for i in range(1, 13)}


def _staff_tops(page):
    from pdf_vector_glyphs import load
    os.environ.setdefault('SCORE_PDF', PDF)
    D = load(page)
    return D


def _rh_onset_x(page):
    """RH staff onset x-centres per system, from the vector glyphs."""
    from pdf_vector_glyphs import load
    import pdf_vector_glyphs
    pdf_vector_glyphs.PDF = PDF
    D = load(page)
    st = D['staves']
    res = []
    for si in range(0, len(st), 2):
        s = st[si]
        xs = sorted({round(g['bb'][0], 1) for g in D['glyphs']
                     if g['n'] in ('blk', 'half', 'whole') and s[0] - 14 < g['y'] < s[4] + 14})
        # merge seconds/clusters within 3pt
        merged = []
        for x in xs:
            if merged and x - merged[-1] < 3.5:
                continue
            merged.append(x)
        res.append((s[0], [x + 4.4 for x in merged]))   # notehead centre
    return res


def _onsets_for_system(names):
    """distinct (measure, offset) onsets in RH across all voices, in time order."""
    out = []
    for n in names:
        offs = set()
        for v in M[n]['rh']:
            for off, d, ps, t, f in parse_voice(v)[0]:
                if ps:
                    offs.add(off)
        out += [(n, o) for o in sorted(offs)]
    return out


def syllables_by_measure():
    """-> {(measure, offset, verse): (text, joins_next)}"""
    doc = fitz.open(PDF)
    table = {}
    for page in (0, 1):
        systems = _rh_onset_x(page)
        keys = [k for k in SYSTEMS if k[0] == page]
        assert len(keys) == len(systems), (page, len(systems))
        onset_map = []
        for (pg, si), (ytop, xs) in zip(keys, systems):
            ons = _onsets_for_system(SYSTEMS[(pg, si)])
            assert len(ons) == len(xs), (pg, si, len(ons), len(xs), ons, xs)
            onset_map.append((ytop, list(zip(xs, ons))))
        rows = {}
        for b in doc[page].get_text('rawdict')['blocks']:
            for l in b.get('lines', []):
                for s in l['spans']:
                    if 'McKayNeue' not in s['font'] or s['size'] > 12:
                        continue
                    t = ''.join(c['c'] for c in s['chars']).strip()
                    y = round(s['origin'][1])
                    if t and (page, y) in ROWS:
                        rows.setdefault(y, []).append(((s['bbox'][0] + s['bbox'][2]) / 2, t))
        for y, toks in rows.items():
            verses = ROWS[(page, y)]
            # which system: the last RH staff top above the row
            sysmap = [om for (yt, om) in onset_map if yt < y][-1]
            toks.sort()
            for i, (x, t) in enumerate(toks):
                if t == '-' or re.fullmatch(r'\d\.|[\d, ]+\.', t):
                    continue
                joins = i + 1 < len(toks) and toks[i + 1][1] == '-'
                bx, (meas, off) = min(sysmap, key=lambda e: abs(e[0] - x))
                assert abs(bx - x) < 9, (page, y, t, x, bx)
                for v in verses:
                    if meas == 'f1' and v != 4:
                        continue
                    if meas == 'e4' and (page, y) == (1, 552) and v != 3:
                        continue
                    table[(meas, off, v)] = (t, joins)
    return table


def melody_events():
    """All sung notes for the whole performance, -> list per performance order."""
    syl = syllables_by_measure()
    order = performance_order()
    t = 0.0
    events = []
    for name, verse in order:
        mm = M[name]
        if name in VOCAL_MEASURES:
            evs, _ = parse_voice(mm['rh'][0])
            for off, d, ps, tie, ferm in evs:
                if not ps:
                    if events:
                        events[-1]['phrase_end'] = True
                    continue
                key_v = verse + 1 if name == 'e4' else (1 if name == 'v0' else verse)
                if name == 'e4' and off < 3:
                    continue                      # piano tag, not sung
                s = syl.get((name, off, key_v))
                ev = dict(start=t + off, end=t + off + d, midi=max(midi_num(p) for p in ps),
                          verse=key_v, measure=name, fermata=ferm)
                if s is None:
                    if events and not events[-1].get('rest') and not events[-1].get('phrase_end'):
                        ev['cont'] = True        # melisma / extender
                    else:
                        continue
                elif s[0] in ('—', '–'):
                    if events:
                        events[-1]['phrase_end'] = True
                    continue
                else:
                    ev['syl'], ev['joins'] = s
                events.append(ev)
        else:
            if events:
                events[-1]['phrase_end'] = True
        t += mm['beats']
    # group syllables into words
    word, words = [], []
    for ev in events:
        if ev.get('cont'):
            continue
        word.append(ev)
        if not ev['joins']:
            words.append(word); word = []
    for w in words:
        text = ''.join(clean(e['syl']) for e in w)
        for i, e in enumerate(w):
            e['word'] = text; e['wpos'] = i; e['wlen'] = len(w)
    return events


def clean(s):
    return re.sub(r'[^A-Za-z’\']', '', s).replace('’', "'")


if __name__ == '__main__':
    evs = melody_events()
    NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    line = []
    cur = None
    for e in evs:
        if e['verse'] != cur:
            if line: print(' '.join(line))
            cur = e['verse']; line = [f'\nVERSE {cur}:']
        p = NAMES[e['midi'] % 12] + str(e['midi'] // 12 - 1)
        line.append(('~' if e.get('cont') else e['syl']) + f'[{p}]' + ('/' if e.get('phrase_end') else ''))
    print(' '.join(line))
    print('\nwords:', sorted({e['word'] for e in evs if 'word' in e}))
