"""Prints per-staff, per-measure pitches/durations derived from the PDF vectors.
Usage: SCORE_PDF=path.pdf python3 tools/pdf_vector_omr.py"""
import sys; sys.path.insert(0,__file__.rsplit('/',1)[0])
from pdf_vector_glyphs import load
L='CDEFGAB'
def pname(step):  # step: diatonic index, C0=0
    letter=L[step%7]; octv=step//7
    acc='#' if letter in 'FC' else ''
    return f'{letter}{acc}{octv}'
def run(pi):
    D=load(pi); g=D['glyphs']; out=[]
    st=D['staves']
    for si,s in enumerate(st):
        clef='G' if si%2==0 else 'F'
        bottom=s[4]; base = 4*7+2 if clef=='G' else 2*7+4   # E4 / G2
        top=s[0]-14; bot=s[4]+14
        sysi=si//2
        # bars spanning this staff
        bars=sorted(set(round(b[0],1) for b in D['bars'] if b[1]<=s[2]<=b[2]))
        heads=[x for x in g if x['n'] in('blk','half','whole') and top<x['y']<bot]
        others=[x for x in g if top<x['y']<bot and x['n'] not in('blk','half','whole')]
        evs=[]
        for h in heads:
            y=h['y']; x0,_,x1,_=h['bb']
            step=base+round((bottom-y)/2.125)
            # stem
            stem=None
            for (sx,y0,y1) in D['stems']:
                if (abs(sx-x0)<1.0 or abs(sx-x1)<1.0) and y0-1.5<=y<=y1+1.5:
                    stem=(sx,y0,y1); break
            dur=None; info=''
            if h['n']=='whole': dur=4
            elif h['n']=='half': dur=2
            else: dur=1
            if stem and h['n']=='blk':
                sx,y0,y1=stem
                up = abs(y1-y)<abs(y0-y)   # notehead at bottom -> stem up
                tip = y0 if up else y1
                nb=0
                for (a,b,c,d) in D['polys']:
                    if a-0.6<=sx<=c+0.6 and (b-1.5<=tip<=d+1.5 or (up and b-1<=tip+4.5*nb<=d+1)):
                        nb+=1
                fl=[o for o in others if o['n'] in('flagU','flagD') and abs(o['x']-sx)<1.5]
                nb=max(nb,len(fl))
                if nb==1: dur=0.5
                elif nb==2: dur=0.25
                info=('U' if up else 'D')+f'{sx:.1f}'
            dots=[o for o in others if o['n']=='dot' and 2<o['x']-x1<9 and abs(o['y']-y)<2.2]
            if dots: dur*=1.5
            acc=[o for o in others if o['n'] in('#','nat','b') and 0<x0-o['x']<10 and abs(o['y']-y)<3]
            evs.append(dict(x=round(x0,1),p=pname(step),dur=dur,stem=info,acc=[a['n'] for a in acc]))
        rests=[dict(x=round(o['x'],1),n=o['n']) for o in others if o['n'].startswith('r')]
        ferm=[round(o['x'],1) for o in g if o['n'].startswith('ferm') and s[0]-25<o['y']<s[4]+25]
        out.append(dict(page=pi,staff=si,clef=clef,bars=bars,evs=sorted(evs,key=lambda e:(e['x'],e['p'])),rests=rests,ferm=ferm))
    return out
if __name__=='__main__':
    for pi in (0,1):
        for S in run(pi):
            print(f"=== p{S['page']+1} staff{S['staff']} {S['clef']} bars={S['bars']} rests={S['rests']} ferm={S['ferm']}")
            bars=S['bars']+[999]
            cur=None
            for e in S['evs']:
                m=sum(1 for b in bars if b<e['x'])
                if m!=cur: print(f' |m{m}:'); cur=m
                print(f"   x{e['x']:6} {e['p']:4} d{e['dur']} {e['stem']} {''.join(e['acc'])}")
