"""Vector OMR helper: pulls SMuFL glyphs (noteheads, dots, flags, rests...) and
staff/stem/beam geometry out of a Finale-engraved PDF with PyMuPDF."""
import pymupdf as fitz, sys, json
from collections import defaultdict
import os
PDF=os.environ.get('SCORE_PDF','score/living_the_gospel_of_jesus_christ.pdf')
NAMES={0xe0a4:'blk',0xe0a3:'half',0xe0a2:'whole',0xe1e7:'dot',0xe240:'flagU',0xe241:'flagD',0xe262:'#',0xe261:'nat',0xe260:'b',
0xe4c0:'fermA',0xe4c1:'fermB',0xe4e5:'rQ',0xe4e6:'r8',0xe4e4:'rH',0xe4e3:'rW',0xe050:'G',0xe062:'F',0xe084:'4',0xe044:'?'}
def load(pi):
    d=fitz.open(PDF); p=d[pi]
    glyphs=[]
    for b in p.get_text('rawdict')['blocks']:
        for l in b.get('lines',[]):
            for s in l['spans']:
                if not s['font'].startswith('FinaleMaestro'): continue
                for ch in s['chars']:
                    o=ord(ch['c']); 
                    if o==0x20: continue
                    glyphs.append(dict(n=NAMES.get(o,hex(o)),x=ch['origin'][0],y=ch['origin'][1],bb=ch['bbox']))
    hl=[];vl=[];stems=[];polys=[];curves=[]
    for dr in p.get_drawings():
        its=dr['items']
        if dr.get('fill') is not None or any(i[0]=='c' for i in its):
            pts=[]
            for i in its: pts+= [q for q in i[1:] if hasattr(q,'x')]
            r=dr['rect']
            if any(i[0]=='c' for i in its): curves.append((r.x0,r.y0,r.x1,r.y1))
            else: polys.append((r.x0,r.y0,r.x1,r.y1))
            continue
        for i in its:
            if i[0]!='l': continue
            a,b=i[1],i[2]
            if abs(a.y-b.y)<0.2: hl.append((min(a.x,b.x),max(a.x,b.x),a.y))
            elif abs(a.x-b.x)<0.2:
                w=dr.get('width') or 0
                (vl if w>0.5 else stems).append((a.x,min(a.y,b.y),max(a.y,b.y)))
    staff=[h for h in hl if h[1]-h[0]>200]
    ys=sorted(set(round(h[2],1) for h in staff))
    staves=[]
    for y in ys:
        seq=[y+k*4.25 for k in range(5)]
        if all(any(abs(z-q)<0.3 for z in ys) for q in seq) and not any(abs(y-st[0])<1 for st in staves) and not any(st[0]<y<st[-1]+1 for st in staves):
            staves.append(seq)
    return dict(glyphs=glyphs,staves=staves,bars=vl,stems=stems,polys=polys,curves=curves,ledgers=[h for h in hl if h[1]-h[0]<15])
if __name__=='__main__':
    for pi in (0,1):
        D=load(pi)
        print('page',pi,'staves',[(s[0],s[-1]) for s in D['staves']])
