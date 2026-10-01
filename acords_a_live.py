#!/usr/bin/env python3
# Ús: python3 acords_a_live.py acords_csv.csv 138 2   (BPM, temps per compàs)
import csv, re, sys, html
src, bpm, bpb = sys.argv[1], float(sys.argv[2]), int(sys.argv[3])
offset = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0   # segons on cau el compàs 1
step = 60.0 / bpm / 2            # graella = mig temps (corxera)
slots_bar = bpb * 2

def style(c):                     # Cmaj7->CMaj7, Am->A-, Em7->E-7
    c = re.sub(r'^([A-G][#b]?)maj', r'\1Maj', c)
    return re.sub(r'^([A-G][#b]?)m(?!aj|Aj)', r'\1-', c)

rows = [(float(t), c.strip()) for t, c in csv.reader(open(src))]
segs, last, end = [], -1, 0
for t, c in rows:
    p = max(0, round((t - offset) / step))
    if c == 'N':
        end = p; continue
    if p <= last: p = last + 1     # evita col·lisions després d'arrodonir
    if segs and segs[-1][1] == style(c): continue
    segs.append((p, style(c))); last = p
if not segs:
    sys.exit("cap acord detectat al csv (tot N): revisa la wav o l'extracció Chordino")
end = max(end, segs[-1][0] + slots_bar)

def pos(p):                        # posició estil Live: compàs.temps.setzena
    return "%d.%d.%d" % (p // slots_bar + 1, (p % slots_bar) // 2 + 1, 1 + 2 * (p % 2))

with open('acords_locators.txt', 'w') as f:
    f.write("posició (compàs.temps.setzena)   acord   durada(temps)\n")
    for i, (p, c) in enumerate(segs):
        q = segs[i + 1][0] if i + 1 < len(segs) else end
        f.write("%-14s %-8s %g\n" % (pos(p), c, (q - p) / 2))

nb = (end + slots_bar - 1) // slots_bar
cells = []
for b in range(nb):
    lo, hi = b * slots_bar, (b + 1) * slots_bar
    items = []
    for i, (p, c) in enumerate(segs):
        q = segs[i + 1][0] if i + 1 < len(segs) else end
        if p < hi and q > lo:
            items.append('<span class="%s">%s</span>' % ('' if p >= lo else 'k', html.escape(c)))
    cells.append('<div class="b"><i>%d</i>%s</div>' % (b + 1, ' '.join(items)))
open('guia_acords.html', 'w').write("""<!doctype html><meta charset="utf-8"><title>Guia d'acords</title>
<style>body{font:20px system-ui;margin:20px;background:#fff;color:#111}
.g{display:grid;grid-template-columns:repeat(4,1fr);gap:0;border-top:1px solid #999;border-left:1px solid #999}
.b{position:relative;min-height:56px;padding:22px 8px 6px;border-right:1px solid #999;border-bottom:1px solid #999;font-weight:600}
.b i{position:absolute;top:3px;left:6px;font:12px system-ui;color:#888}.b span{margin-right:10px}.k{color:#aaa;font-weight:400}
@media(prefers-color-scheme:dark){body{background:#111;color:#eee}}</style>
<h3>%d BPM · %d temps/compàs · gris = acord que ve del compàs anterior</h3><div class="g">%s</div>""" % (bpm, bpb, ''.join(cells)))
print(len(segs), "acords,", nb, "compassos")
