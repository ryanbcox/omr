"""Build MusicXML (written + performance order) and an expressive piano MIDI.

python3 src/build.py            -> output/*.musicxml, output/*.mid
"""
import os, random, sys
sys.path.insert(0, os.path.dirname(__file__))
import mido
from transcription import M, WRITTEN, performance_order, VERSES

OUT = os.path.join(os.path.dirname(__file__), '..', 'output')
BASE = 'living_the_gospel_of_jesus_christ'
TEMPO = 96
PPQ = 480
NAMES = 'C D E F G A B'.split()
SEMI = dict(C=0, D=2, E=4, F=5, G=7, A=9, B=11)


def midi_num(p):
    letter, rest = p[0], p[1:]
    acc = 0
    while rest and rest[0] in '#b':
        acc += 1 if rest[0] == '#' else -1
        rest = rest[1:]
    return 12 * (int(rest) + 1) + SEMI[letter] + acc


def parse_voice(s):
    """-> list of (offset, dur, [pitches], tie, fermata)"""
    out, t = [], 0.0
    for tok in s.split():
        tie = tok.endswith('~') or '~' in tok
        ferm = '^' in tok
        tok = tok.replace('~', '').replace('^', '')
        ps, d = tok.split('/')
        d = float(d)
        out.append((t, d, [] if ps == 'r' else ps.split('.'), tie, ferm))
        t += d
    return out, t


def check():
    ok = True
    for name in WRITTEN:
        mm = M[name]
        for hand in ('rh', 'lh'):
            for v in mm[hand]:
                _, tot = parse_voice(v)
                if abs(tot - mm['beats']) > 1e-6:
                    print(f'!! {name} {hand} voice sums to {tot}, expected {mm["beats"]}')
                    ok = False
    print('duration check:', 'OK' if ok else 'FAILED')
    return ok


# ---------------------------------------------------------------- MusicXML
def to_music21(order, title):
    from music21 import stream, note, chord, meter, key, clef, tempo, expressions, metadata, tie as m21tie, layout
    sc = stream.Score()
    sc.metadata = metadata.Metadata(title=title, composer='Kathleen Kelly and Natalie Adams')
    parts = {}
    open_ties = set()
    for hand, cl in (('rh', clef.TrebleClef()), ('lh', clef.BassClef())):
        p = stream.PartStaff(id=hand)
        num = 0
        for i, (name, verse) in enumerate(order):
            mm = M[name]
            meas = stream.Measure(number=num)
            num += 1
            if i == 0:
                meas.append(cl)
                meas.append(key.Key('D'))
                meas.append(meter.TimeSignature('1/4'))
                if hand == 'rh':
                    meas.insert(0, tempo.MetronomeMark('With conviction', TEMPO))
            if i == 1:
                meas.insert(0, meter.TimeSignature('4/4'))
            for vi, vs in enumerate(mm[hand]):
                evs, _ = parse_voice(vs)
                v = stream.Voice(id=str(vi + 1))
                for off, d, ps, tie, ferm in evs:
                    if not ps:
                        n = note.Rest(quarterLength=d)
                        if len(mm[hand]) > 1:
                            n.style.hideObjectOnPrint = True
                    elif len(ps) == 1:
                        n = note.Note(ps[0], quarterLength=d)
                    else:
                        n = chord.Chord(ps, quarterLength=d)
                    tkey = (hand, tuple(ps))
                    if ps and tkey in open_ties:
                        n.tie = m21tie.Tie('stop')
                        open_ties.discard(tkey)
                    if tie and ps:
                        n.tie = m21tie.Tie('start')
                        open_ties.add(tkey)
                    if ferm:
                        n.expressions.append(expressions.Fermata())
                    v.insert(off, n)
                if len(mm[hand]) == 1:
                    for el in v.notesAndRests:
                        meas.insert(el.offset, el)
                else:
                    meas.insert(0, v)
            p.append(meas)
        parts[hand] = p
    sc.insert(0, parts['rh'])
    sc.insert(0, parts['lh'])
    sc.insert(0, layout.StaffGroup([parts['rh'], parts['lh']], name='Piano', symbol='brace'))
    # fix time signatures for split bars / pickups
    for hand in parts:
        ms = list(parts[hand].getElementsByClass('Measure'))
        for i, (name, _) in enumerate(order):
            want = M[name]['beats']
            prev = M[order[i - 1][0]]['beats'] if i else None
            if i and want != prev:
                for ts in ms[i].getElementsByClass('TimeSignature'):
                    ms[i].remove(ts)
                ms[i].insert(0, meter.TimeSignature(f'{int(want)}/4'))
    return sc


# ---------------------------------------------------------------- MIDI performance
def build_midi(path, seed=7):
    rnd = random.Random(seed)
    order = performance_order()
    # timeline in beats
    starts, t = [], 0.0
    for name, v in order:
        starts.append(t)
        t += M[name]['beats']
    total_beats = t

    # ---- tempo map: list of (beat, bpm)
    tmap = [(0.0, TEMPO)]

    def tempo_at(beat, bpm):
        tmap.append((beat, bpm))

    for (name, v), s in zip(order, starts):
        if name == 'i4':                       # end of intro: gentle broadening + fermata
            tempo_at(s, 92); tempo_at(s + 1.5, 86); tempo_at(s + 2, TEMPO / 2.6)
        if name == 'v0':
            tempo_at(s, 90)
        if name == 'a1':
            tempo_at(s, TEMPO)
        if name == 'e4':                       # tag fermata, breath, pickup into next verse
            tempo_at(s, 94); tempo_at(s + 1.5, 88); tempo_at(s + 2, TEMPO / 2.4); tempo_at(s + 3, 90)
        if name == 'f3':
            tempo_at(s, 94); tempo_at(s + 2, 91)
        if name == 'f4':                        # rit.
            tempo_at(s, 86); tempo_at(s + 0.5, 82); tempo_at(s + 1, 78); tempo_at(s + 1.5, 74)
            tempo_at(s + 2, TEMPO / 3.2)           # final fermata
    tmap.sort()

    def tick(beat):
        return int(round(beat * PPQ))

    # ---- notes
    rh_events, lh_events = [], []   # (tick, type, note/cc, value)
    pending_ties = {}
    for idx, ((name, verse), s) in enumerate(zip(order, starts)):
        mm = M[name]
        # dynamics shaping
        base = 64
        if name.startswith('i') or name == 'v0':
            base = 62
        if name in ('a9', 'a10', 'a11', 'a12'):
            base += 5                     # "I can live, I can care..." lift
        if name in ('e3', 'e4'):
            base += 2
        if verse == VERSES and name in ('a9', 'a10', 'a11', 'a12', 'f1', 'f2', 'f3'):
            base += 4
        if name == 'f4':
            base -= 2
        for hand, evlist in (('rh', rh_events), ('lh', lh_events)):
            for vi, vs in enumerate(mm[hand]):
                evs, _ = parse_voice(vs)
                soft = vi in mm.get('soft', [])
                for off, d, ps, tie, ferm in evs:
                    if not ps:
                        continue
                    on_beat = s + off
                    top = max(midi_num(p) for p in ps)
                    low = min(midi_num(p) for p in ps)
                    for p in ps:
                        n = midi_num(p)
                        key = (hand, n)
                        if key in pending_ties:     # continuation of a tie: extend previous note
                            prev = pending_ties.pop(key)
                            prev[1] = on_beat + d
                            if tie:
                                pending_ties[key] = prev
                            continue
                        vel = base
                        if hand == 'rh':
                            if n == top and not soft:
                                vel += 9               # melody voicing
                            else:
                                vel -= 8
                            if soft:
                                vel -= 6
                        else:
                            vel -= 4
                            if n == low and abs(off - round(off)) < 1e-6 and int(round(off)) in (0, 2):
                                vel += 5           # bass on strong beats
                        # metric accent
                        if abs(off) < 1e-6:
                            vel += 3
                        elif abs(off - round(off)) > 1e-6:
                            vel -= 3
                        vel = max(30, min(110, vel + rnd.randint(-3, 3)))
                        rec = [on_beat, on_beat + d, n, vel]
                        evlist.append(rec)
                        if tie:
                            pending_ties[key] = rec

    # ---- pedal: change at each half bar (harmony rhythm), none on pickups
    pedal = []
    for (name, v), s in zip(order, starts):
        b = M[name]['beats']
        if b < 2:
            continue
        segs = [(0, 2), (2, b)] if b == 4 else [(0, 2), (2, 3)]
        if name == 'e4':
            segs = [(0, 2), (2, 3)]              # clear before the pickup
        for a, z in segs:
            pedal.append((s + a, s + z + (1.5 if name == 'f4' and a == 2 else 0)))

    # ---- write: musical ticks + tempo map as set_tempo meta events
    def jitter():
        return rnd.uniform(-0.012, 0.012)  # beats

    mid = mido.MidiFile(ticks_per_beat=PPQ, type=1)
    meta = mido.MidiTrack(); mid.tracks.append(meta)
    meta.append(mido.MetaMessage('track_name', name='Living the Gospel of Jesus Christ', time=0))
    meta.append(mido.MetaMessage('copyright', text='Words and music by Kathleen Kelly and Natalie Adams. (c) 2026 IRI', time=0))
    meta.append(mido.MetaMessage('key_signature', key='D', time=0))
    abs_meta = [(0, mido.MetaMessage('time_signature', numerator=1, denominator=4))]
    abs_meta.append((tick(1), mido.MetaMessage('time_signature', numerator=4, denominator=4)))
    for b, bpm in tmap:
        abs_meta.append((tick(b), mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(bpm))))
    # markers
    for (name, v), s in zip(order, starts):
        if name == 'i0':
            abs_meta.append((tick(s), mido.MetaMessage('marker', text='Introduction')))
        if name == 'v0':
            abs_meta.append((tick(s), mido.MetaMessage('marker', text='Verse 1')))
        if name == 'e4':
            abs_meta.append((tick(s + 3), mido.MetaMessage('marker', text=f'Verse {v + 1}')))
    abs_meta.sort(key=lambda x: x[0])
    _write_abs(meta, abs_meta)

    for nm, evs, extra in (('Piano RH', rh_events, []), ('Piano LH', lh_events, pedal)):
        tr = mido.MidiTrack(); mid.tracks.append(tr)
        tr.append(mido.MetaMessage('track_name', name=nm, time=0))
        tr.append(mido.Message('program_change', program=0, channel=0, time=0))
        ab = []
        if nm == 'Piano LH':
            ab.append((0, mido.Message('control_change', control=7, value=110, channel=0)))
            ab.append((0, mido.Message('control_change', control=91, value=30, channel=0)))
        for on, off, n, vel in evs:
            j = jitter()
            t_on = max(0, tick(on + j))
            t_off = tick(off - 0.04)      # slight legato gap; pedal sustains
            if off >= total_beats - 1e-6:
                t_off = tick(off + 0.5)   # let the final chord ring a little longer
            if t_off <= t_on:
                t_off = t_on + 30
            ab.append((t_on, mido.Message('note_on', note=n, velocity=vel, channel=0)))
            ab.append((t_off, mido.Message('note_off', note=n, velocity=0, channel=0)))
        for a, z in extra:
            ab.append((tick(a) + 40, mido.Message('control_change', control=64, value=127, channel=0)))
            ab.append((tick(z) - 10, mido.Message('control_change', control=64, value=0, channel=0)))
        # final pedal hold through the end
        ab.append((tick(total_beats + 2.5), mido.MetaMessage('marker', text='end')))
        ab.sort(key=lambda x: (x[0], 0 if x[1].type == 'note_off' or (x[1].type == 'control_change' and x[1].value == 0) else 1))
        _write_abs(tr, ab)
    mid.save(path)
    return mid, order, starts, total_beats


def _write_abs(track, ab):
    last = 0
    for t, msg in ab:
        track.append(msg.copy(time=t - last))
        last = t
    track.append(mido.MetaMessage('end_of_track', time=0))


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    if not check():
        sys.exit(1)
    from transcription import WRITTEN
    written = [(n, 0) for n in WRITTEN]
    to_music21(written, 'Living the Gospel of Jesus Christ (piano, written order)').write(
        'musicxml', os.path.join(OUT, BASE + '_written.musicxml'))
    to_music21(performance_order(), 'Living the Gospel of Jesus Christ (piano, as performed)').write(
        'musicxml', os.path.join(OUT, BASE + '_performed.musicxml'))
    mid, order, starts, tb = build_midi(os.path.join(OUT, BASE + '.mid'))
    print('measures performed:', len(order), 'beats:', tb, 'length: %.1fs' % mid.length)
    print(' '.join(n for n, _ in order))
