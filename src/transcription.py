"""Piano part of "Living the Gospel of Jesus Christ" (Kelly & Adams), transcribed
measure by measure. Pitches come from the PDF's vector glyphs (tools/pdf_vector_omr.py);
rhythms, voices, ties and fermatas were checked visually against 300-dpi renders.

Voice string syntax:  "<pitches>/<beats>"  tokens separated by spaces.
  pitches: dot-joined note names (F#3.A3.D4) or 'r' for a rest
  suffix '~' on the token = tie into the next measure, '^' = fermata
Each measure: dict(rh=[voice,...], lh=[voice,...], beats=N, label=...)
Optional 'soft' = list of RH voice indexes that are fills (played a bit softer).
"""

M = {}

def m(name, beats, rh, lh, **kw):
    M[name] = dict(name=name, beats=beats, rh=rh, lh=lh, **kw)

# ---------------- Introduction (page 1, system 1) ----------------
m('i0', 1, ['A3/.5 A3/.5'], ['r/1'])
m('i1', 4, ['F#3.A3.D4/1 D4/.5 E4/.5 B3.D4.F#4/1 F#4/.5 E4/.5'],
            ['D2/.5 A2/.5 F#3/1 B2/.5 F#3/.5 B3/1'])
m('i2', 4, ['B3.D4/1 B3/.5 D4/.5 G3.B3/1 F#3.A3/1'],
            ['G2/.5 D3/.5 G3/.5 D3/.5 G2/.5 D3/.5 F#2/1'])
m('i3', 4, M['i1']['rh'], M['i1']['lh'])
# split bar: 3 beats here + the 1-beat "Oh, the" pickup (v0)
m('i4', 3, ['G3.B3.E4/1.5 D4/.5 F#3.A3.D4/1^'],
            ['G2/.5 D3/.5 G3/1 D2.D3/1^~'])
m('v0', 1, ['A3/.5 A3/.5'], ['D2.D3/1'])

# ---------------- Verse (repeat body) ----------------
m('a1', 4, ['F#3.A3.D4/1 D4/.5 E4/.5 B3.D4.F#4/1 F#4/.5 E4/.5'],
            ['D2/.5 A2/.5 F#3/1 B2/.5 F#3/.5 B3/1'])                       # joy that I feel
m('a2', 4, ['B3.D4/1 B3/.5 D4/.5 G3.B3/1 F#3.A3/1'],
            ['G2/.5 D3/.5 G3/.5 D3/.5 G2/.5 D3/.5 F#2/1'])                # fol-low the Sav-ior
m('a3', 4, ['F#3.A3.D4/1 D4/.5 D4/.5 B3.D4/1 D4.F#4/.5 A4/.5'],
            ['D2/.5 A2/.5 D3/.5 C#3/.5 B2/.5 F#3/.5 B3/1'])               # Liv-ing the gos-pel of
m('a4', 4, ['D4.G4.B4/1.5 A4/.5 C#4.E4.A4/1 F#4/.5 A4/.5'],
            ['G2/.5 D3/.5 G3/1 A2.E3/2'])                                 # Je-sus Christ. I will
m('a5', 4, ['G4.B4/1 B4/.5 A4/.5 D4.F#4/1 F#4/.5 A4/.5'],
            ['G3/.5 D4/1.5 D3/.5 A3/1.5'])                                # Car-ing with love as I'm
m('a6', 4, ['B3.G4/.5 F#4/.5 E4/.5 D4/.5 G3.B3/1 F#3.A3/1'],
            ['G2/.5 D3/.5 G3/1 G2.D3/1 F#2.D3/1'])                        # serv-ing my neigh-bor
m('a7', 4, ['F#3.A3.D4/1 D4/.5 E4/.5 B3.D4.F#4/1 F#4/.5 E4/.5'],
            ['D2/.5 A2/.5 D3/.5 C#3/.5 B2/.5 F#3/.5 B3/1'])               # Liv-ing the gos-pel of
m('a8', 4, ['G3.B3.E4/1.5 D4/.5 F#3.A3.D4/1 F#4/.5 A4/.5'],
            ['G2/.5 D3/.5 G3/1 D2.D3/2'])                                 # Je-sus Christ. I can
m('a9', 4, ['D4.G4.B4/2 r/1 B4/.5 A4/.5', 'r/1 G5/.5 A5/.5 D5.G5.B5/1 r/1'],
            ['G2/.5 D3/.5 G3/1 B3/2'], soft=[1])                          # live, I can
m('a10', 4, ['A3.D4.F#4/2 r/1 F#4/.5 A4/.5', 'r/1 B5/.5 A5/.5 D5.F#5/1 r/1'],
            ['D2/.5 A2/.5 F#3/1 A3/2'], soft=[1])                         # care, I'll in-
m('a11', 4, M['a9']['rh'], M['a9']['lh'], soft=[1])                      # vite and u-
m('a12', 4, ['A3.D4.F#4/1 G4/.5 F#4/.5 A3.C#4.E4/2'],
            ['D2/1 A2/1 A2.E3/2'])                                        # nite,

# ---------------- 1st, 2nd, 3rd ending ----------------
m('e1', 4, ['F#3.D4/1 A3.D4/.5 E4/.5 D4.F#4/1 D4.F#4/.5 E4/.5'],
            ['D2/.5 A2/.5 F#3/1 B2/.5 F#3/.5 B3/1'])                       # Liv-ing the gos-pel of
m('e2', 4, ['G3.B3.E4/1.5 D4/.5 F#3.D4/2'],
            ['G2/.5 D3/.5 G3/1 D2.D3/2'])                                 # Je-sus Christ.
m('e3', 4, ['F#4.D5/1 A4.D5/.5 E5/.5 B4.D5.F#5/1 D5.F#5/.5 E5/.5'],
            ['D3/.5 A3/.5 D4/1 B2/.5 F#3/.5 B3/1'])                       # piano tag
m('e4', 4, ['G4.B4.E5/1.5 D5/.5 F#4.A4.D5/1^ A3/.5 A3/.5'],
            ['G3/.5 B3/.5 E4/.5 A3/.5 D3.A3/2^'])                         # tag + "Oh, the" pickup

# ---------------- 4th ending ----------------
m('f1', 4, ['F#3.D4/1 D4/.5 E4/.5 B3.D4.F#4/1 D4.F#4/.5 E4/.5'],
            ['D2/.5 A2/.5 F#3/1 B2/.5 F#3/.5 B3/1'])
m('f2', 4, ['G3.B3.E4/1.5 D4/.5 F#3.B3.D4/2'],
            ['G2/.5 D3/.5 G3/1 B2/2'])
m('f3', 4, ['G3.B3.D4/1 B3.D4/.5 E4/.5 B3.D4.F#4/1 F#4/.5 E4/.5'],
            ['G2/.5 D3/.5 G3/1 B2/.5 F#3/.5 B3/1'])
m('f4', 4, ['E4/1.5 D4/.5 D4/2^', 'G3.B3/1 A3.C#4/1 F#3/2^'],
            ['G2/.5 D3/.5 A2/.5 G3/.5 D2.D3/2^'])                        # rit. ... final chord

INTRO = ['i0', 'i1', 'i2', 'i3', 'i4', 'v0']
BODY = ['a%d' % i for i in range(1, 13)]
END123 = ['e1', 'e2', 'e3', 'e4']
END4 = ['f1', 'f2', 'f3', 'f4']
WRITTEN = INTRO + BODY + END123 + END4
VERSES = 4

def performance_order():
    """Unrolled: intro, then 4 verses (endings 1-3 / 4)."""
    seq = [(n, 0) for n in INTRO]
    for v in range(1, VERSES + 1):
        seq += [(n, v) for n in BODY]
        seq += [(n, v) for n in (END123 if v < VERSES else END4)]
    return seq
