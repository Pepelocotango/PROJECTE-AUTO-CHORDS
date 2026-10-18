#!/usr/bin/env python3
# Ús: python3 acords_a_live.py acords_csv.csv 138 2   (BPM, temps per compàs)
import csv, sys, html, os
src, bpm, bpb = sys.argv[1], float(sys.argv[2]), int(sys.argv[3])
offset = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0   # segons on cau el compàs 1
durada = float(sys.argv[5]) if len(sys.argv) > 5 else 0.0   # durada de la WAV (cobertura)
step = 60.0 / bpm / 2            # graella = mig temps (corxera)
slots_bar = bpb * 2

# --- mapa de TEMPO i COMPÀS: la guia en fa cas si és variable ---------------
# Si a la carpeta del CSV hi ha `tempo.csv`/`compas.csv` amb mes d'un tros, la
# posició «compàs.temps.setzena» es calcula amb el mapa; si no, amb el BPM fix.
mapa = None
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from app.tempo_map import TempoMap

    def _llegeix(nom, ncol):
        r = os.path.join(os.path.dirname(os.path.abspath(src)), nom)
        out = []
        if os.path.isfile(r):
            with open(r, encoding="utf-8") as f:
                for fila in csv.reader(f):
                    if len(fila) >= ncol and not fila[0].startswith("inici"):
                        try:
                            out.append([float(x) for x in fila[:ncol]])
                        except ValueError:
                            pass
        return out

    _tempo = _llegeix("tempo.csv", 3)
    _compas = _llegeix("compas.csv", 4)
    if len(_tempo) > 1 and len(_tempo) == len(_compas):
        _trams = [(t[0], t[1], t[2], int(c[2]), int(c[3]))
                  for t, c in zip(_tempo, _compas)]
        if not TempoMap(_trams, offset=offset).es_constant():
            mapa = TempoMap(_trams, offset=offset)
except Exception:
    mapa = None

# NOTA: el nom de l'acord es desa TAL QUAL (el model ja ve en notació canònica
# — vegeu `app/xifrat.py`). Abans hi havia un `style()` que reescrivia
# `Am`→`A-`/`Cmaj7`→`CMaj7` aquí; ara la normalització és al MODEL, no a
# l'export, i així el CSV i els fitxers exportats coincideixen.
rows = [(float(r[0]), r[2].strip())
        for r in csv.reader(open(src, encoding="utf-8"))
        if len(r) >= 3 and not r[0].startswith("inici")]


def _q(t):
    """Negres (quarters) des de l'origen fins a `t` (mapa) o (t-offset)/beat."""
    if mapa is not None:
        return mapa.quarters(t)
    return (float(t) - offset) / (60.0 / bpm)


def _t_de_p(p):
    """Instant de la corxera `p` (per etiquetar quan hi ha xoc d'arrodoniment)."""
    if mapa is not None:
        return mapa.t_de_quarters(p / 2.0)
    return offset + p * step


def _pos(t):
    """Etiqueta «compàs.temps.setzena» a l'instant `t`."""
    if mapa is not None:
        return mapa.label(t)
    p = max(0, round((float(t) - offset) / step))
    return "%d.%d.%d" % (p // slots_bar + 1, (p % slots_bar) // 2 + 1,
                         1 + 2 * (p % 2))


segs, last, end = [], -1, 0
for t, c in rows:
    p = max(0, round(_q(t) * 2))
    if c == 'N':
        end = p; continue
    if p <= last: p = last + 1     # evita col·lisions després d'arrodonir
    if segs and segs[-1][2] == c: continue
    segs.append((_t_de_p(p), p, c)); last = p
if not segs:
    sys.exit("cap acord detectat al csv (tot N): revisa la wav o l'extracció Chordino")
end = max(end, segs[-1][1] + slots_bar)
if durada > 0:
    # INVARIANT de COBERTURA: l'últim acord arriba a la durada de la WAV.
    end = max(end, round(_q(durada) * 2))


with open('acords_locators.txt', 'w', encoding="utf-8") as f:
    f.write("posició (compàs.temps.setzena)   acord   durada(temps)\n")
    for i, (t, p, c) in enumerate(segs):
        q = segs[i + 1][1] if i + 1 < len(segs) else end
        f.write("%-14s %-8s %g\n" % (_pos(t), c, (q - p) / 2))

# Guia HTML: amb mapa constant, cel·les de `slots_bar`; amb mapa variable, una
# cel·la per COMPÀS del mapa (les durades en temps poden variar).
if mapa is not None:
    talls = [x[1] for x in mapa.compassos()]
    nbars = len(talls)
else:
    nbars = (end + slots_bar - 1) // slots_bar
    talls = [offset + b * slots_bar * step for b in range(nbars)]


def _bar_de(t):
    k = 0
    for i, tb in enumerate(talls):
        if t >= tb - 1e-9:
            k = i
        else:
            break
    return k


cells = []
for b in range(nbars):
    lo = talls[b]
    hi = talls[b + 1] if b + 1 < len(talls) else (durada if durada > 0 else lo)
    items = []
    for i, (t, p, c) in enumerate(segs):
        t1 = segs[i + 1][0] if i + 1 < len(segs) else (
            durada if durada > 0 else t + 1e-9)
        if _bar_de(t) <= b <= _bar_de(max(t1 - 1e-9, t)):
            items.append('<span class="%s">%s</span>'
                         % ('' if _bar_de(t) >= b else 'k', html.escape(c)))
    cells.append('<div class="b"><i>%d</i>%s</div>' % (b + 1, ' '.join(items)))
open('guia_acords.html', 'w', encoding="utf-8").write("""<!doctype html><meta charset="utf-8"><title>Guia d'acords</title>
<style>body{font:20px system-ui;margin:20px;background:#fff;color:#111}
.g{display:grid;grid-template-columns:repeat(4,1fr);gap:0;border-top:1px solid #999;border-left:1px solid #999}
.b{position:relative;min-height:56px;padding:22px 8px 6px;border-right:1px solid #999;border-bottom:1px solid #999;font-weight:600}
.b i{position:absolute;top:3px;left:6px;font:12px system-ui;color:#888}.b span{margin-right:10px}.k{color:#aaa;font-weight:400}
@media(prefers-color-scheme:dark){body{background:#111;color:#eee}}</style>
<h3>%d BPM · %d temps/compàs · gris = acord que ve del compàs anterior</h3><div class="g">%s</div>""" % (bpm, bpb, ''.join(cells)))
print(len(segs), "acords,", nbars, "compassos")
