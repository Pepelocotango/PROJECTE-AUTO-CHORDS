"""Derivats de guia i exportació (F1): segments, locators i guia HTML.

Extret de `app/pipeline.py`. Treballa amb el model en segons i el mapa de
tempo; no depén de Qt ni del motor Vamp.
"""
import csv
import os

from .pipeline_mapa import _mapa_tempo_carpeta

def _segments_guia_daw(csv_path, bpm, bpb, offset=0.0, durada=0.0, mapa=None):
    """Calcula els segments quantitzats a **1/32** per als locators i la guia HTML.

    Retorna `(segs, end, step, slots_bar, mapa, pos_de_p)`, on cada segment és
    `(t_exacte, p, acord)` i `p` és l'índex de **fusa** des de l'origen.
    """
    bpm = float(bpm)
    bpb = int(bpb)
    offset = float(offset or 0.0)
    durada = float(durada or 0.0)
    step = 60.0 / bpm / 8.0                  # fusa (1/32)
    slots_bar = bpb * 8                      # fuses per compàs

    if mapa is None:
        mapa = _mapa_tempo_carpeta(os.path.dirname(os.path.abspath(csv_path)),
                                   offset=offset)
    elif hasattr(mapa, "es_constant") and mapa.es_constant():
        mapa = None

    with open(csv_path, encoding="utf-8") as f:
        rows = [(float(r[0]), r[2].strip())
                for r in csv.reader(f)
                if len(r) >= 3 and not r[0].startswith("inici")]

    def _q(t):
        if mapa is not None:
            return mapa.quarters(t)
        return (float(t) - offset) / (60.0 / bpm)

    def _t_de_p(p):
        if mapa is not None:
            return mapa.t_de_quarters(p / 8.0)
        return offset + p * step

    def _pos_de_p(p):
        if mapa is not None:
            return mapa.label(_t_de_p(p))
        return "%d.%d.%d" % (p // slots_bar + 1, (p % slots_bar) // 8 + 1,
                             1 + (p % 8))

    segs, last, end = [], -1, 0
    for t, c in rows:
        p = max(0, round(_q(t) * 8))
        if c == "N":
            end = p
            continue
        if p <= last:
            p = last + 1
        if segs and segs[-1][2] == c:
            continue
        # El TEMPS és l'exacte del model; `p` només serveix per a l'etiqueta.
        segs.append((t, p, c))
        last = p
    if not segs:
        raise RuntimeError(
            "No hi ha cap acord per exportar: el model només té «N». "
            "Posa'n almenys un (editant-lo al timeline) o prem «Analitza».")
    end = max(end, segs[-1][1] + slots_bar)
    if durada > 0:
        end = max(end, round(_q(durada) * 8))
    return segs, end, step, slots_bar, mapa, _pos_de_p


def segments_locators(csv_path, bpm, bpb, offset=0.0, durada=None,
                      mapa=None, _dades=None):
    """Guia DAW **en memòria**: `[(posició_1/32, acord, durada_en_beats), …]`.

    És un DERIVAT del model: **no es desa en cap fitxer** (decisió de
    l'operador, 2026-10-19: el sistema de fitxers intern, el més simple
    possible). El fan servir la guia HTML i la partitura; els WAVs d'acords
    usen `segments_export` (temps exactes) i el `manifest.csv`.
    """
    if _dades is None:
        _dades = _segments_guia_daw(csv_path, bpm, bpb, offset=offset,
                                    durada=durada, mapa=mapa)
    segs, end, _step, _slots_bar, _mapa, _pos_de_p = _dades
    out = []
    for i, (_t, p, c) in enumerate(segs):
        q = segs[i + 1][1] if i + 1 < len(segs) else end
        out.append((_pos_de_p(p), c, (q - p) / 8.0))
    return out


def events_partitura(csv_path, bpm, bpb, offset=0.0, durada=None, mapa=None,
                     _dades=None):
    """Acords per a la PARTITURA en memòria: `[(beat_inici, acord, beats), …]`.

    Mateixa font que la guia (`_segments_guia_daw`): el model quantitzat a
    **1/32**. Així la partitura no depèn de cap fitxer intermedi.
    """
    if _dades is None:
        _dades = _segments_guia_daw(csv_path, bpm, bpb, offset=offset,
                                    durada=durada, mapa=mapa)
    segs, end, _step, _slots_bar, _mapa, _pos_de_p = _dades
    out = []
    for i, (_t, p, c) in enumerate(segs):
        q = segs[i + 1][1] if i + 1 < len(segs) else end
        out.append((p / 8.0, c, (q - p) / 8.0))
    return out


def segments_exactes(csv_path, durada=0.0):
    """Segments EXACTES del model: `[(ini_s, fi_s, acord), …]`.

    A diferència de `segments_locators` (que quantitza a 1/32 per a la guia i
    els noms), ací els temps són els del model, sense arrodonir. És la font
    per a les durades dels WAV i per al `manifest.csv` de l'export.
    """
    durada = float(durada or 0.0)
    rows = []
    with open(csv_path, encoding="utf-8") as f:
        for r in csv.reader(f):
            if len(r) < 3 or r[0].startswith(("inici", "posici")):
                continue
            try:
                t = float(r[0])
            except ValueError:
                continue
            c = r[2].strip()
            if c == "N":
                continue
            if rows and rows[-1][1] == c:
                continue
            rows.append((t, c))
    if not rows:
        raise RuntimeError(
            "No hi ha cap acord per exportar: el model només té «N». "
            "Posa'n almenys un (editant-lo al timeline) o prem «Analitza».")
    out = []
    if rows[0][0] > 1e-9:
        out.append((0.0, rows[0][0], "N"))
    for i, (t, c) in enumerate(rows):
        if durada > 0 and t >= durada - 1e-9:
            continue
        fi = rows[i + 1][0] if i + 1 < len(rows) else (
            durada if durada > 0 else t + 1.0)
        if durada > 0:
            fi = min(fi, durada)
        if fi > t + 1e-9:
            out.append((t, fi, c))
    return out


def segments_export(csv_path, bpm, bpb, offset=0.0, durada=None, mapa=None):
    """`[(posicio_1/32, acord, ini_s, fi_s)]` per als WAVs i el manifest.

    El nom és la posició musical quantitzada a 1/32; els temps són els EXACTES
    del model. Si dos acords cauen a la mateixa fusa, el segon agafa la
    següent etiqueta per no xocar el nom (el manifest porta el temps exacte).
    """
    bpm = float(bpm)
    bpb = int(bpb)
    offset = float(offset or 0.0)
    durada = float(durada or 0.0)
    if mapa is None:
        mapa = _mapa_tempo_carpeta(os.path.dirname(os.path.abspath(csv_path)),
                                   offset=offset)
    elif hasattr(mapa, "es_constant") and mapa.es_constant():
        mapa = None
    step = 60.0 / bpm / 8.0                  # fusa (1/32)
    slots_bar = bpb * 8

    def _q(t):
        if mapa is not None:
            return mapa.quarters(t)
        return (float(t) - offset) / (60.0 / bpm)

    def _t_de_p(p):
        if mapa is not None:
            return mapa.t_de_quarters(p / 8.0)
        return offset + p * step

    def _pos(p):
        if mapa is not None:
            return mapa.label(_t_de_p(p))
        return "%d.%d.%d" % (p // slots_bar + 1, (p % slots_bar) // 8 + 1,
                             1 + (p % 8))

    exactes = segments_exactes(csv_path, durada)
    out, last = [], -1
    for ini, fi, c in exactes:
        p = max(0, round(_q(ini) * 8))
        if p <= last:
            p = last + 1
        out.append((_pos(p), c, ini, fi))
        last = p
    return out


def genera_guia_html(csv_path, bpm, bpb, offset=0.0, workdir=None, durada=None,
                     mapa=None, log=None, _dades=None):
    """Genera `guia_acords.html` en memòria i en retorna la ruta."""
    import html as _html
    workdir = workdir or os.path.dirname(os.path.abspath(csv_path))
    bpm = float(bpm)
    bpb = int(bpb)
    offset = float(offset or 0.0)
    durada_val = float(durada or 0.0)
    if _dades is None:
        _dades = _segments_guia_daw(csv_path, bpm, bpb, offset=offset,
                                    durada=durada_val, mapa=mapa)
    segs, end, step, slots_bar, mapa_resolt, _pos = _dades

    if mapa_resolt is not None:
        talls = [x[1] for x in mapa_resolt.compassos()]
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
        items = []
        for i, (t, _p, c) in enumerate(segs):
            t1 = segs[i + 1][0] if i + 1 < len(segs) else (
                durada_val if durada_val > 0 else t + 1e-9)
            if _bar_de(t) <= b <= _bar_de(max(t1 - 1e-9, t)):
                items.append(
                    '<span class="%s">%s</span>'
                    % ("" if _bar_de(t) >= b else "k", _html.escape(c)))
        cells.append('<div class="b"><i>%d</i>%s</div>' % (b + 1, " ".join(items)))

    guia_path = os.path.join(workdir, "guia_acords.html")
    with open(guia_path, "w", encoding="utf-8") as f:
        f.write(
            """<!doctype html><meta charset="utf-8"><title>Guia d'acords</title>
<style>body{font:20px system-ui;margin:20px;background:#fff;color:#111}
.g{display:grid;grid-template-columns:repeat(4,1fr);gap:0;border-top:1px solid #999;border-left:1px solid #999}
.b{position:relative;min-height:56px;padding:22px 8px 6px;border-right:1px solid #999;border-bottom:1px solid #999;font-weight:600}
.b i{position:absolute;top:3px;left:6px;font:12px system-ui;color:#888}.b span{margin-right:10px}.k{color:#aaa;font-weight:400}
@media(prefers-color-scheme:dark){body{background:#111;color:#eee}}</style>
<h3>%d BPM · %d temps/compàs · gris = acord que ve del compàs anterior</h3><div class="g">%s</div>"""
            % (bpm, bpb, "".join(cells))
        )
    if log:
        log(f"  {len(segs)} acords, {nbars} compassos")
    return guia_path


def pos_compas(t, bpm, bpb=4, lliure=False, offset=0.0, mapa=None):
    """Posició en format compàs.temps.fusa (qualsevol compàs).

    Graella = **1/32** (fusa). El tercer camp és la fusa dins del temps
    (1..8). `bpb` = temps per compàs, així funciona amb 3/4, 6/8, 5/4…
    """
    if lliure:
        return f"{float(t):07.3f}s"
    if mapa is not None and not mapa.es_constant():
        return mapa.label(t)           # mateixa forma (compàs.temps.fusa)
    step = 60.0 / bpm / 8              # fusa (1/32)
    SB = max(1, int(bpb)) * 8          # fuses per compàs
    # Sense clampar: abans de l'offset (compàs 1) les posicions son negatives
    # -> el silenci inicial queda com un compte enrere (compàs -1, -2...).
    p = round((float(t) - float(offset)) / step)
    return "%d.%d.%d" % (p // SB + 1, (p % SB) // 8 + 1, 1 + (p % 8))


def seq_abc(seccions):
    return "".join(s[2] for s in seccions)
