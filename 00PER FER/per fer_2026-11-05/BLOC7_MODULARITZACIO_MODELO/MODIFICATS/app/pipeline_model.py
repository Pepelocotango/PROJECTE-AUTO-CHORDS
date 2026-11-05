#!/usr/bin/env python3
# pipeline_model.py - model, segments, edicio unificada
# Extret de pipeline.py (BLOC 7). Re-exportat per pipeline.py (fassana).
import csv
import os
from collections import namedtuple

from app import xifrat, tempo_csv

TEMPS_DEC = 6
RESOLUCIO_CSV = 10.0 ** -TEMPS_DEC
NOM_MAPA_TEMPO = tempo_csv.NOM_MAPA_TEMPO

__all__ = ['Clip', 'FORAT_ACORD', 'FORAT_SECCIO', 'MIN_GAP_TEMPS', 'SENSE_ACORD', 'SENSE_SECCIO', 'TOL_TEMPS', '_ClipBase', '_nom_item_acord', '_segments_guia_daw', '_tempo_csv_carpeta', 'NOM_MAPA_TEMPO', 'RESOLUCIO_CSV', 'TEMPS_DEC', 'acords_de_clips', 'bloc_sobre_acords', 'bloc_sobre_seccions', 'clips_d_acords', 'clips_de_seccions', 'contiguitat_seccions', 'duplica_bloc_clips', 'duplica_bloc_seccions', 'duplica_clips', 'elimina_clips', 'elimina_seccio', 'events_partitura', 'fusiona_acords', 'fusiona_clips', 'fusiona_seccions', 'model_inicial', 'mou_bloc_acords', 'mou_bloc_clips', 'mou_bloc_seccions', 'normalitza_clips', 'normalitza_cobertura', 'parteix_acord', 'parteix_clips', 'parteix_seccio', 'pos_compas', 'redimensiona_acord', 'redimensiona_clips', 'redimensiona_seccio', 'renomena_acords_model', 'renomena_seccions_model', 'saneja_nom_acord', 'seccions_de_clips', 'segments_exactes', 'segments_export', 'segments_lliures', 'segments_locators', 'seq_abc', 'style', 'substitueix_en_model', 'valida_canvis_acords', 'valida_canvis_seccions']

def saneja_nom_acord(nom):
    """Nom d'acord net per al MODEL i el CSV, en la **notació canònica** de l'app.

    Delega a `app.xifrat`: entén les variants que escrigui l'usuari (menor
    `m`/`mi`/`min`/`-`, major `M`/`Ma`/`maj`/`Δ`, `°`/`o`/`dim`, `+`, `ø`…) i
    deixa el xifrat en la forma canònica (`Am` → `A-`, `Cmaj7` → `CMaj7`,
    `Bø` → `B-7b5`). El baix amb `/` es conserva (`A7/G` → `A7/G`).

    La seguretat per als noms de FITXER la garanteix `safe_filename`, que
    l'export aplica pel seu compte. Retorna "" si el nom queda buit — qui cridi
    decideix què fer.
    """
    return xifrat.normalitza_xifrat(nom)

TOL_TEMPS = 1e-6

MIN_GAP_TEMPS = 0.001

_ClipBase = namedtuple("Clip", ("ini", "fi", "payload"))

class Clip(_ClipBase):
    """Estructura única de clip: interval `[ini, fi)` amb `payload`."""

    @property
    def nom(self):
        p = self.payload
        return p[0] if isinstance(p, tuple) else p

def clips_d_acords(acords, durada):
    """Converteix acords a `Clip` amb el `fi` derivat de la cadena de fronteres."""
    durada = float(durada or 0.0)
    acords = list(acords or ())
    out = []
    for i, a in enumerate(acords):
        if isinstance(a, Clip):
            out.append(a)
        else:
            fi = float(acords[i + 1][0]) if i + 1 < len(acords) else durada
            out.append(Clip(float(a[0]), fi, tuple(a[1:])))
    return out

def acords_de_clips(clips):
    """`Clip` → acords `(t, nom, tsrc)`: només la frontera d'inici."""
    return [(float(c.ini),) + tuple(c.payload) for c in clips]

def clips_de_seccions(seccions):
    """Seccions `(ini, fi, lletra, família)` → `Clip`."""
    return [s if isinstance(s, Clip) else Clip(float(s[0]), float(s[1]), tuple(s[2:]))
            for s in (seccions or ())]

def seccions_de_clips(clips):
    """`Clip` → seccions `(ini, fi, lletra, família)`."""
    return [(float(c.ini), float(c.fi)) + tuple(c.payload) for c in clips]

def normalitza_clips(clips, durada, forat, arrodoneix=False, deriva_fi=False,
                     log=None):
    """XARXA DE SEGURETAT única dels invariants #1, #2, #4 i #8 (model de clips).

    - **#1 ordre estricte**: clips ordenats per `ini` (`sort` estable).
    - **#2 contigüitat**: la frontera entre dos clips és una de sola → si dos
      clips es trepitgen, el primer s'acota a l'`ini` del segon (o s'elimina si
      queda sense espai); si hi ha un forat, es tapa amb un clip de payload `forat`.
    - **#4 cobertura**: si el primer no arrenca a 0 s'hi posa una capçalera
      `forat`, i el `fi` de l'últim s'acota a `durada`.
    - **#8 temps vàlids**: cap inici negatiu ni durada ≤ 0.

    Retorna una llista NOVA de `Clip`; no muta l'entrada.
    """
    durada = float(durada or 0.0)
    ordenats = sorted(
        (c if isinstance(c, Clip) else Clip(float(c[0]), float(c[1]), tuple(c[2]))
         for c in (clips or ())),
        key=lambda c: float(c.ini))
    net, fora, n_neg = [], 0, 0
    for c in ordenats:
        ini, fi = float(c.ini), float(c.fi)
        if deriva_fi:
            if ini < 0.0:
                ini = 0.0
                n_neg += 1
        else:
            if fi <= 0.0:
                n_neg += 1
                continue
            if ini < 0.0:
                ini = 0.0
                n_neg += 1
        if durada > 0:
            ref = round(ini, TEMPS_DEC) if arrodoneix else ini
            if ref >= durada - TOL_TEMPS:
                fora += 1
                continue
            fi = min(fi, durada)
        if arrodoneix and net and ini - net[-1].ini < MIN_GAP_TEMPS - TOL_TEMPS:
            if log:
                log(f"cobertura: clip a {ini:.6f} s eliminat (a menys de "
                    f"{MIN_GAP_TEMPS * 1000:.0f} ms del clip anterior, "
                    f"{net[-1].ini:.6f} s)")
            continue
        net.append(Clip(ini, fi, tuple(c.payload)))
    if n_neg and log:
        log(f"cobertura: {n_neg} clip(s) amb temps negatiu ajustats")
    if fora and log:
        log(f"cobertura: {fora} clip(s) fora de la WAV (>= {durada:.2f} s) eliminats")
    net.sort(key=lambda c: c.ini)
    if deriva_fi:
        net = [Clip(c.ini, net[i + 1].ini if i + 1 < len(net) else durada,
                    c.payload) for i, c in enumerate(net)]
    out = []
    for c in net:
        if not deriva_fi and c.fi <= c.ini + TOL_TEMPS:
            continue
        while out and c.ini < out[-1].fi - TOL_TEMPS:
            prev = out[-1]
            if c.ini <= prev.ini + TOL_TEMPS:
                out.pop()
                continue
            out[-1] = Clip(prev.ini, c.ini, prev.payload)
            break
        if out and c.ini > out[-1].fi + TOL_TEMPS:
            out.append(Clip(out[-1].fi, c.ini, tuple(forat)))
            if log:
                log(f"cobertura: forat {out[-2].fi:.2f}–{c.ini:.2f} s tapat "
                    f"amb «{forat[0]}»")
        out.append(c)
    if out and out[0].ini > 1e-9:
        out.insert(0, Clip(0.0, out[0].ini, tuple(forat)))
        if log:
            log(f"cobertura: capçalera «{forat[0]}» a 0 ({out[1].ini:.2f} s)")
    if out and durada > 0 and out[-1].fi < durada - 1e-9:
        ult = out[-1]
        out[-1] = Clip(ult.ini, durada, ult.payload)
    return out

def model_inicial(durada, log=None):
    """Model MÍNIM per treballar **sense anàlisi** (roadmap §14.1).

    Un sol clip d'acords (marca «N» = sense acord) i un de sol d'estructura
    que cobreixen **tota la cançó**: el punt de partida editable (a partir
    d'aquí, partir/afegir/moure/renombrar). Regla d'or **#4**: els clips han
    de cobrir `[0, durada]`.
    """
    dur = max(0.0, float(durada or 0.0))
    if log:
        log(f"model inicial (sense anàlisi): 1 acord «N» i 1 secció de 0 a "
            f"{dur:.2f}s")
    return ([Clip(0.0, dur, FORAT_ACORD)], [(0.0, dur, "A", "A")])

def normalitza_cobertura(acords, seccions, durada, log=None):
    """Garanteix l'**INVARIANT de COBERTURA** delegant al motor únic `normalitza_clips`."""
    durada = float(durada or 0.0)
    ac_out, sec_out = [], []
    if acords:
        son_clips = isinstance(acords[0], Clip)
        if son_clips:
            ac_out = normalitza_clips(acords, durada, FORAT_ACORD,
                                      arrodoneix=True, deriva_fi=True, log=log)
        else:
            extra = tuple("0.000000000" for _ in acords[0][2:])
            cl = normalitza_clips(
                clips_d_acords(acords, durada), durada,
                (SENSE_ACORD,) + extra, arrodoneix=True, deriva_fi=True,
                log=log)
            ac_out = acords_de_clips(cl)
    if seccions:
        son_clips_s = isinstance(seccions[0], Clip)
        cl_s = seccions if son_clips_s else clips_de_seccions(seccions)
        norm_s = normalitza_clips(cl_s, durada, FORAT_SECCIO, log=log)
        sec_out = norm_s if son_clips_s else seccions_de_clips(norm_s)
    return ac_out, sec_out

def _tempo_csv_carpeta(carpeta, offset=0.0):
    """Llig `mapa_tempo.csv` de `carpeta` (o `mapa_tempo/`) i retorna un
    `TempoMap` si té més d'un tram i no és constant, o `None`.
    """
    try:
        from app.tempo_map import TempoMap

        for d in (carpeta, os.path.join(carpeta, "tempo_csv")):
            trams_map = tempo_csv.llegeix_tempo_csv(
                os.path.join(d, NOM_MAPA_TEMPO))
            if len(trams_map) > 1:
                tm = TempoMap([tuple(t) for t in trams_map], offset=offset)
                if not tm.es_constant():
                    return tm
    except Exception:
        pass
    return None

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
        mapa = _tempo_csv_carpeta(os.path.dirname(os.path.abspath(csv_path)),
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
        mapa = _tempo_csv_carpeta(os.path.dirname(os.path.abspath(csv_path)),
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

def parteix_clips(clips, i, talla, nou_payload=None, marge=MIN_GAP_TEMPS,
                  etiqueta="clip"):
    """Parteix el clip `i` pel temps `talla` (implementació única, #11)."""
    if i < 0 or i >= len(clips):
        raise ValueError(f"índex de {etiqueta} inexistent")
    c = clips[i]
    talla = float(talla)
    if not (c.ini + marge < talla < c.fi - marge):
        raise ValueError(f"el tall ({talla:.2f}s) ha de caure dins "
                         f"{c.ini:.2f}–{c.fi:.2f}s")
    esq = Clip(c.ini, talla, c.payload)
    dreta = Clip(talla, c.fi, c.payload if nou_payload is None else nou_payload)
    return list(clips[:i]) + [esq, dreta] + list(clips[i + 1:])

def fusiona_clips(clips, i, amb="seguent", etiqueta="clip"):
    """Fusiona el clip `i` amb el veí: el de l'esquerra s'estén (un sol nucli)."""
    n = len(clips)
    if n == 0 or i < 0 or i >= n:
        raise ValueError(f"índex de {etiqueta} inexistent")
    if amb == "anterior":
        if i == 0:
            raise ValueError(f"no hi ha {etiqueta} anterior")
        i -= 1
    elif amb != "seguent":
        raise ValueError("amb ha de ser 'seguent' o 'anterior'")
    if i >= n - 1:
        raise ValueError(f"no hi ha {etiqueta} següent")
    a, b = clips[i], clips[i + 1]
    return list(clips[:i]) + [Clip(a.ini, b.fi, a.payload)] + list(clips[i + 2:])

def parteix_acord(acords, i, talla, nom=None, marge=MIN_GAP_TEMPS, durada=0.0):
    """Parteix l'acord `i` (wrapper del nucli unificat `parteix_clips`; #11)."""
    if i < 0 or i >= len(acords):
        raise ValueError("índex d'acord inexistent")
    nom = (saneja_nom_acord(nom) if nom else "") or acords[i][1]
    payload = (nom, f"{float(talla):.9f}")
    cl = parteix_clips(clips_d_acords(acords, durada), i, talla,
                       nou_payload=payload, marge=marge, etiqueta="acord")
    return [(float(c.ini),) + tuple(c.payload) for c in cl]

def fusiona_acords(acords, i, amb="seguent"):
    """Fusiona l'acord `i` amb el veí (wrapper de `fusiona_clips`; #11)."""
    cl = fusiona_clips(clips_d_acords(acords, 0.0), i, amb, etiqueta="acord")
    return [(float(c.ini),) + tuple(c.payload) for c in cl]

def mou_bloc_acords(acords, first, last, dt, durada, log=None):
    """DESTÍ del moviment d'un BLOC d'acords (PLA_EDICIO_LLIURE §6.3).

    Mou el bloc **consecutiu** `[first..last]` un delta `dt` (segons) **sense
    canviar-ne la durada** i resol el destí amb la regla «**mana l'últim
    editat**»: el material que queda **a sota** del bloc es **talla** (se'n
    conserva la part que no cau dins del bloc) o **s'elimina** (si no en queda
    cap tros). Mai es refusa l'operació per la regla d'or #4.

    El model són **MARQUES**: el clip `i` va de `t_i` a `t_{i+1}` (i l'últim,
    fins a `durada`). El bloc només **tapa** el seu nou tram `[a', b')`: el que
    cau a sota es talla o s'elimina, però **els clips que queden entre l'origen
    i el destí NO es toquen** (es queden quiets i la cobertura la manté el
    mateix model de marques). L'**origen** el tanca el veí: endavant,
    l'anterior s'estira fins a l'inici nou; endarrere, el posterior s'estira
    fins al final nou. Si el bloc queda a la vora, el tros que cap operació tapi
    es converteix en `N` a la normalització (``normalitza_cobertura``).

    Retorna una llista NOVA d'acords (no muta l'entrada). Si el bloc no
    existeix, la durada és nul·la o el delta és ~0, torna la llista original.
    """
    clips = mou_bloc_clips(clips_d_acords(acords, durada), first, last, dt,
                           durada, FORAT_ACORD, log)
    # `tsrc` (temps font): el d'un acord que NO s'ha mogut es conserva; el d'un
    # de mogut o nou passa a ser el seu temps.
    orig = {(round(float(a[0]), 6), a[1]): tuple(a) for a in (acords or ())}
    res = []
    for c in clips:
        t = float(c.ini)
        vell = orig.get((round(t, 6), c.payload[0]))
        if vell is not None:
            res.append((t,) + vell[1:])
        else:
            res.append((t, c.payload[0], f"{t:.9f}") + tuple(c.payload[2:]))
    return res

SENSE_SECCIO = "-"      # §6.1: forat explícit d'estructura («sense secció»)

SENSE_ACORD = "N"       # §6.1: forat explícit d'acords («sense acord»)

def redimensiona_acord(acords, idx, vora, t, durada, log=None):
    """ESTIRAR/ENCONGIR una vora d'un acord (mateixa lògica que MOURE, §6.3).

    El clip editat **mana** al seu tram nou: el que queda **a sota** es **talla**
    o **s'elimina**. **Encongir** deixa un buit que tanca el **veí** (a la dreta,
    el següent; a l'esquerra, l'anterior); si **no hi ha veí** (primer o últim
    clip), el buit queda perquè `normalitza_cobertura` hi posi **`N`**.

    `vora`: `"ini"` (esquerra) o `"fi"` (dreta). Retorna una llista NOVA.
    """
    return acords_de_clips(redimensiona_clips(
        clips_d_acords(acords, durada), idx, vora, t, durada, FORAT_ACORD, log))

FORAT_ACORD = (SENSE_ACORD, "0.000000000")

FORAT_SECCIO = (SENSE_SECCIO, SENSE_SECCIO)

def redimensiona_clips(clips, idx, vora, t, durada, forat, log=None):
    """ESTIRAR/ENCONGIR una VORA d'un clip (regla §6.3, la mateixa que MOURE).

    El clip editat **mana** al seu tram nou: el que queda **a sota** es **talla**
    o **s'elimina**. **Encongir** deixa un buit que tanca el **veí** (a la dreta
    el següent; a l'esquerra l'anterior); si **no hi ha veí** (primer o últim
    clip) el buit queda perquè `normalitza_clips` hi posi el `forat`.

    `vora`: `"ini"` (esquerra) o `"fi"` (dreta). Retorna una llista NOVA.
    """
    out = [Clip(c.ini, c.fi, c.payload) for c in clips or ()]
    durada = float(durada or 0.0)
    if not (0 <= idx < len(out)) or abs(float(t)) < 1e-12:
        return out
    t = max(0.0, min(durada, float(t)))
    esq = str(vora).strip().lower() in ("ini", "inici", "esquerra", "left")
    c = out[idx]
    if not esq:
        if (abs(t - c.fi) < TOL_TEMPS
                or (t < c.fi and t - c.ini < MIN_GAP_TEMPS - TOL_TEMPS)):
            return out                      # no canvia res (o queda massa curt)
        if t > c.fi:                        # ESTIRAR cap a la dreta
            nous = [Clip(c.ini, t, c.payload)]
            for i, x in enumerate(out):
                if i == idx:
                    continue
                if x.ini >= c.fi - TOL_TEMPS and x.fi <= t + TOL_TEMPS:
                    continue                # cobert del tot → s'elimina
                if x.ini < t - TOL_TEMPS and x.fi > t + TOL_TEMPS:
                    x = Clip(t, x.fi, x.payload)    # contenia t → es talla
                nous.append(x)
            nous.sort(key=lambda z: z.ini)
            return normalitza_clips(nous, durada, forat)
        if idx + 1 >= len(out):             # últim clip: el buit → `forat`
            return normalitza_clips(out + [Clip(t, c.fi, tuple(forat))],
                                    durada, forat)
        out[idx] = Clip(c.ini, t, c.payload)
        s = out[idx + 1]
        out[idx + 1] = Clip(t, s.fi, s.payload)     # el següent s'estira
        return normalitza_clips(out, durada, forat)
    if t < c.ini:                           # ESTIRAR cap a l'esquerra
        nous = [Clip(t, c.fi, c.payload)]
        for i, x in enumerate(out):
            if i == idx:
                continue
            if x.ini >= t - TOL_TEMPS and x.fi <= c.ini + TOL_TEMPS:
                continue                    # cobert del tot → s'elimina
            if x.ini < t - TOL_TEMPS and x.fi > t + TOL_TEMPS:
                x = Clip(x.ini, t, x.payload)   # contenia t → es talla
            nous.append(x)
        nous.sort(key=lambda z: z.ini)
        return normalitza_clips(nous, durada, forat)
    if c.fi - t < MIN_GAP_TEMPS - TOL_TEMPS:
        return out                          # no canvia res (queda massa curt)
    if idx > 0:                             # l'anterior s'estira endavant
        p = out[idx - 1]
        out[idx - 1] = Clip(p.ini, t, p.payload)
    out[idx] = Clip(t, c.fi, c.payload)
    return normalitza_clips(out, durada, forat)

def redimensiona_seccio(seccions, idx, vora, t, durada, log=None):
    """Vora d'una SECCIÓ: mateixa regla i mateix nucli que els acords (#11)."""
    return seccions_de_clips(redimensiona_clips(
        clips_de_seccions(seccions), idx, vora, t, durada, FORAT_SECCIO, log))

def mou_bloc_clips(clips, first, last, dt, durada, forat, log=None):
    """Moviment d'un BLOC de clips (§6.3; implementació única).

    El bloc **conserva la durada** i **tapa** `[a', b')`: el material de sota es
    **TALLA** (si només queda cobert en part → en sobreviu el tros de fora, amb
    el seu nom) o **S'ELIMINA** (si queda sobrepassat del tot). L'**origen** el
    tanca el veí; si no n'hi ha cap, hi va el `forat`. Retorna clips NOUS.
    """
    out = [Clip(c.ini, c.fi, c.payload) for c in clips or ()]
    n = len(out)
    durada = float(durada or 0.0)
    if not (0 <= first <= last < n) or abs(float(dt)) < 1e-9:
        return out
    a, b = out[first].ini, out[last].fi
    if b - a <= 1e-9:
        return out
    dt = max(-a, min(durada - b, float(dt)))     # el bloc no surt de la WAV
    if abs(dt) < 1e-9:
        return out
    a2, b2 = a + dt, b + dt
    bloc = [Clip(c.ini + dt, c.fi + dt, c.payload) for c in out[first:last + 1]]
    resta = []
    for c in out[:first] + out[last + 1:]:
        if c.fi <= a2 + TOL_TEMPS or c.ini >= b2 - TOL_TEMPS:
            resta.append(c)                      # fora del tram nou: intacte
            continue
        if c.ini < a2 - TOL_TEMPS:
            resta.append(Clip(c.ini, a2, c.payload))    # se'n talla la cua
        if c.fi > b2 + TOL_TEMPS:
            resta.append(Clip(b2, c.fi, c.payload))     # se'n talla el principi
    if dt > 0:                                   # l'anterior tanca l'origen
        fi_vei, tapades = min(a2, b), False
        for i, c in enumerate(resta):
            if c.ini < a - TOL_TEMPS and abs(c.fi - a) <= TOL_TEMPS:
                resta[i], tapades = Clip(c.ini, fi_vei, c.payload), True
        if not tapades:
            resta.append(Clip(0.0, fi_vei, tuple(forat)))
    else:                                        # el següent tanca l'origen
        ini_vei, tapades = max(b2, a), False
        for i, c in enumerate(resta):
            if abs(c.ini - b) <= TOL_TEMPS:
                resta[i], tapades = Clip(ini_vei, c.fi, c.payload), True
        if not tapades and b2 < durada - TOL_TEMPS:
            resta.append(Clip(ini_vei, durada, tuple(forat)))
    nou = bloc + resta
    nou.sort(key=lambda c: c.ini)                # sort estable: mana el bloc
    if log and len(nou) != n:
        log(f"moviment: bloc {first}-{last} → {a2:.2f}-{b2:.2f}s")
    return nou

def mou_bloc_seccions(seccions, first, last, dt, durada, log=None):
    """DESTÍ del moviment d'un BLOC de seccions (paritat d'edició #11, §6.3).

    Mateixa regla que :func:`mou_bloc_acords`: el bloc **conserva la seva
    durada**, **tapa** el seu tram nou (el que hi cau a sota es talla o
    s'elimina) i **no toca** les seccions que queden entre l'origen i el destí.
    L'**origen** el tanca el veí (endavant, l'anterior; endarrere, la següent) i,
    si no n'hi ha cap, el forat es converteix en una secció **«-»** (§6.1).

    Les seccions són explícites `(ini, fi, lletra, família)`; el resultat torna a
    ser **contigu** (sense forats) i ordenat. Retorna una llista NOVA.
    """
    return seccions_de_clips(mou_bloc_clips(
        clips_de_seccions(seccions), first, last, dt, durada, FORAT_SECCIO, log))

def parteix_seccio(seccions, i, talla, marge=MIN_GAP_TEMPS):
    """Parteix la secció `i` (mateix nucli que els acords, #11)."""
    return seccions_de_clips(parteix_clips(
        clips_de_seccions(seccions), i, talla, marge=marge, etiqueta="secció"))

def fusiona_seccions(seccions, i, amb="seguent"):
    """Fusiona la secció `i` amb el veí (mateix nucli que els acords, #11)."""
    return seccions_de_clips(fusiona_clips(
        clips_de_seccions(seccions), i, amb, etiqueta="secció"))

def elimina_clips(clips, idx, durada, forat):
    """Nucli únic d'ESBORRAR un clip (§6.4: l'anterior s'estira; sense veí, forat).

    El clip `idx` s'esborra i l'**anterior s'estira** per tapar el forat (mateixa
    lògica que l'origen d'un moviment, §6.3). Si NO hi ha anterior (el clip 0),
    el forat el tapa el **normalitzador** amb `forat` (`N`/`-`) sense moure cap
    altre clip (important: esborrar la «N» de capçalera no ha de desplaçar l'acord
    següent). Si el carril queda **buit**, hi va el clip canònic `forat` de 0 a
    `durada` (regla d'or #4). Retorna clips NOUS; no muta l'entrada.
    """
    out = [Clip(c.ini, c.fi, c.payload) for c in (clips or ())]
    if not (0 <= idx < len(out)):
        return out
    c = out.pop(idx)
    if idx > 0 and out:
        p = out[idx - 1]
        out[idx - 1] = Clip(p.ini, c.fi, p.payload)
    out = normalitza_clips(out, durada, forat)
    if not out:
        out = [Clip(0.0, float(durada or c.fi), tuple(forat))]
    return out

def elimina_seccio(seccions, idx, durada):
    """Esborra la secció `idx` (mateix nucli que els acords; #11)."""
    return seccions_de_clips(elimina_clips(
        clips_de_seccions(seccions), idx, durada, FORAT_SECCIO))

def duplica_clips(clips, idx, marge=MIN_GAP_TEMPS):
    """Nucli únic de DUPLICAR un clip: es **parteix pel mig** en dos d'iguals.

    El duplicat conserva el `payload` i, entre els dos, la durada total (com el
    `Ctrl+D` de l'app: la meitat per a cadascun). Si no hi ha prou marge (< 2×
    `marge`), no es fa res. Retorna clips NOUS; no muta l'entrada.
    """
    out = [Clip(c.ini, c.fi, c.payload) for c in (clips or ())]
    if not (0 <= idx < len(out)):
        return out
    c = out[idx]
    mig = (c.ini + c.fi) / 2.0
    if mig - c.ini < marge or c.fi - mig < marge:
        return out
    return (list(out[:idx]) + [Clip(c.ini, mig, c.payload),
                               Clip(mig, c.fi, c.payload)] + list(out[idx + 1:]))

def duplica_bloc_clips(clips, first, last, desti, durada, forat):
    """Nucli de DUPLICAR un BLOC a un DESTÍ (sobreescrivint, §6.3/#11).

    La còpia del bloc `[first..last]` (que conserva la durada i l'espaiat intern,
    com el `Grid Relative` del Cubase) es col·loca a `desti`; el material que hi
    cau **a sota** es **talla** o **s'elimina** (§6.3) i **l'original es queda
    intacte** (a diferència de MOURE). El destí s'acota a `[0, durada)`.

    Amb `desti = fi del bloc` és el `Ctrl+D` («el duplicat va després del clip i
    sobreescriu el tram que ocupa», PLA_EDICIO_LLIURE §2). Retorna clips NOUS.
    """
    out = [Clip(c.ini, c.fi, c.payload) for c in (clips or ())]
    n = len(out)
    durada = float(durada or 0.0)
    if not (0 <= first <= last < n):
        return out
    a, b = float(out[first].ini), float(out[last].fi)
    llarg = b - a
    if llarg <= 1e-9:
        return out
    desti = max(0.0, min(float(desti or 0.0), max(0.0, durada - llarg)))
    ini2, fi2 = desti, desti + llarg
    copies = [Clip(c.ini - a + ini2, c.fi - a + ini2, c.payload)
              for c in out[first:last + 1]]
    resta = []
    for x in out:
        if x.fi <= ini2 + TOL_TEMPS or x.ini >= fi2 - TOL_TEMPS:
            resta.append(x)                       # fora del destí: intacte
            continue
        if x.ini < ini2 - TOL_TEMPS:
            resta.append(Clip(x.ini, ini2, x.payload))      # se'n talla la cua
        if x.fi > fi2 + TOL_TEMPS:
            resta.append(Clip(fi2, x.fi, x.payload))        # se'n talla el cap
    nou = resta + copies
    nou.sort(key=lambda c: c.ini)                 # sort estable: mana la còpia
    return normalitza_clips(nou, durada, forat)

def duplica_bloc_seccions(seccions, first, last, desti, durada):
    """Duplica un bloc de seccions a `desti` (mateix nucli que els acords, #11)."""
    return seccions_de_clips(duplica_bloc_clips(
        clips_de_seccions(seccions), first, last, desti, durada, FORAT_SECCIO))

def _nom_item_acord(item):
    if isinstance(item, Clip):
        return item.nom
    if len(item) >= 3 and isinstance(item[1], (int, float)):
        p = item[2]
        return p[0] if isinstance(p, tuple) else p
    return item[1]

def valida_canvis_acords(items, durada=0.0):
    """Valida l'ordre estricte, límits i resolució CSV, i deriva el `fi` en `Clip`."""
    if not items:
        return []
    durada = float(durada or 0.0)
    ordenats = sorted(items, key=lambda x: float(x[0]))
    n = len(ordenats)
    out = []
    prev_t, prev_nom = None, None
    for i, item in enumerate(ordenats):
        t = float(item[0])
        nom = _nom_item_acord(item)
        if t < 0:
            raise ValueError(f"L'acord {nom} té un inici negatiu ({t:.2f}s)")
        if durada > 0 and t >= durada - TOL_TEMPS:
            raise ValueError(
                f"L'acord {nom} no cap dins de la WAV ({t:.2f}s; la WAV "
                f"fa {durada:.2f}s)")
        if prev_t is not None:
            if t <= prev_t + 1e-9:
                raise ValueError(
                    "Els acords no poden compartir ni invertir el seu inici. "
                    "L'ordre ha de ser estricte i sense solapaments."
                )
            if t - prev_t < MIN_GAP_TEMPS - 1e-9:
                raise ValueError(
                    f"Els acords {prev_nom} ({prev_t:.6f}s) i {nom} "
                    f"({t:.6f}s) estan a menys de "
                    f"{MIN_GAP_TEMPS * 1000:.0f} ms: dos canvis d'acord "
                    f"més junts no són útils i fan clips inútils."
                )
        prev_t, prev_nom = t, nom
        fi = float(ordenats[i + 1][0]) if i + 1 < n else durada
        if isinstance(item, Clip):
            payload = tuple(item.payload)
        elif len(item) >= 3 and isinstance(item[1], (int, float)):
            p = item[2]
            payload = tuple(p) if isinstance(p, tuple) else (p,)
        else:
            payload = tuple(item[1:])
        out.append(Clip(t, fi, payload))
    return out

def valida_canvis_seccions(items, durada=0.0):
    """Valida l'ordre estricte, durades positives i no solapament d'estructura."""
    if not items:
        return []
    durada = float(durada or 0.0)
    ordenats = sorted(items, key=lambda x: float(x[0]))
    prev_fi = -1e-9
    for item in ordenats:
        ini = float(item[0])
        fi = float(item[1])
        etq = item.payload[0] if isinstance(item, Clip) else item[2]
        if ini < 0 or fi < 0:
            raise ValueError(
                f"La secció {etq} té temps negatius ({ini:.2f}s–{fi:.2f}s)")
        if fi <= ini:
            raise ValueError(
                f"La secció {etq} té una durada no vàlida ({ini:.2f}s–{fi:.2f}s)")
        if durada > 0 and fi > durada + TOL_TEMPS:
            raise ValueError(
                f"La secció {etq} surt de la WAV ({fi:.2f}s; la WAV fa "
                f"{durada:.2f}s)")
        if ini < prev_fi - 1e-9:
            raise ValueError(
                "Les seccions no poden solapar-se ni invertir-se. "
                "L'ordre temporal ha de ser estricte."
            )
        prev_fi = fi
    return ordenats

def contiguitat_seccions(items, idx, min_s=MIN_GAP_TEMPS):
    """Manté l'INVARIANT de CONTIGÜITAT (#2) ajustant els veïns de la secció `idx`."""
    items = list(items)
    ini, fi, L, _F = items[idx]
    if fi - ini < min_s:
        raise ValueError(
            f"La secció {L} quedaria massa curta ({ini:.2f}s–{fi:.2f}s)")
    if idx - 1 >= 0:
        pi, _pf, pl, pfam = items[idx - 1]
        if ini - pi < min_s:
            raise ValueError(
                f"La secció {pl} quedaria massa curta: el nou inici "
                f"({ini:.2f}s) no deixa marge")
        items[idx - 1] = (pi, ini, pl, pfam)
    if idx + 1 < len(items):
        _ni, nf, nl, nfam = items[idx + 1]
        if nf - fi < min_s:
            raise ValueError(
                f"La secció {nl} quedaria massa curta: el nou fi "
                f"({fi:.2f}s) no deixa marge")
        items[idx + 1] = (fi, nf, nl, nfam)
    return items

def bloc_sobre_acords(acords, bloc, llargada, T, durada, rel=1e-6):
    """Sobreescriu un bloc copiat d'acords dins `[T, T+llargada]`."""
    Te = min(float(T) + float(llargada), float(durada))
    punts = []
    for (r, name) in bloc:
        t = float(T) + float(r)
        if t < durada - rel:
            punts.append(Clip(t, t, (str(name), f"{t:.9f}")))
    if not punts:
        return list(acords)
    marca = None
    for a in acords:
        if abs(float(a[0]) - Te) <= rel:
            marca = a
            break
    if marca is None and Te < durada - rel:
        after = None
        for a in acords:
            if float(a[0]) <= Te - rel:
                after = a
            else:
                break
        nom_m = (str(_nom_item_acord(after))
                 if after else str(_nom_item_acord(punts[-1])))
        marca = Clip(Te, Te, (nom_m, f"{Te:.9f}"))
    nou = [a for a in acords if float(a[0]) < float(T) - rel]
    nou += punts
    if marca is not None:
        if float(marca[0]) > float(punts[-1][0]) + RESOLUCIO_CSV - 1e-6:
            nou.append(marca)
    nou += [a for a in acords if float(a[0]) > Te + rel]
    return nou

def bloc_sobre_seccions(seccions, bloc, llargada, T, durada, rel=1e-6):
    """Sobreescriu un bloc copiat de seccions dins `[T, T+llargada]`."""
    T = float(T)
    durada = float(durada)
    Te = min(T + float(llargada), durada)
    nou = []
    for (ini, fi, ll, fam) in seccions:
        ini, fi = float(ini), float(fi)
        if fi <= T + rel or ini >= Te - rel:
            nou.append((ini, fi, ll, fam))
            continue
        if ini < T - rel:
            nou.append((ini, T, ll, fam))
        if fi > Te + rel:
            nou.append((Te, fi, ll, fam))
    for (ri, rf, ll, fam) in bloc:
        ini = T + float(ri)
        fi = min(T + float(rf), Te)
        if ini < durada - rel and fi - ini > rel:
            nou.append((ini, fi, str(ll), str(fam)))
    nou.sort(key=lambda s: float(s[0]))
    return [s for s in nou if float(s[1]) - float(s[0]) > rel]

def renomena_acords_model(acords, idxs, nom, durada=0.0):
    """Reanomena els acords `idxs` a `nom` i valida la cadena."""
    idxs = sorted({i for i in idxs if 0 <= i < len(acords)})
    nom = saneja_nom_acord(nom)
    if not idxs or not nom:
        return None, ""
    nova = list(acords)
    for i in idxs:
        _a = nova[i]
        nova[i] = Clip(float(_a[0]), float(_a[1]), (nom,) + tuple(_a[2][1:]))
    return valida_canvis_acords(nova, durada), nom

def renomena_seccions_model(seccions, idxs, lletra, durada=0.0):
    """Reanomena les seccions `idxs` a `lletra` i valida la cadena."""
    idxs = sorted({i for i in idxs if 0 <= i < len(seccions)})
    if not idxs:
        return None, ""
    lletra = (str(lletra) if lletra is not None else "").strip() \
        or seccions[idxs[0]][2]
    nova = list(seccions)
    for i in idxs:
        ini, fi, _l, _f = nova[i]
        nova[i] = (ini, fi, lletra, lletra)
    return valida_canvis_seccions(nova, durada), lletra

def substitueix_en_model(items, camp, troba, reemplaca, durada=0.0):
    """Substitueix aparicions exactes a `items` (`acords` o `estructura`).

    Retorna `(nova_llista, n_canvis, etiqueta_aplicada)`.
    """
    troba = str(troba or "").strip()
    reemplaca = str(reemplaca or "").strip()
    if not troba or not reemplaca:
        return list(items), 0, ""
    if camp == "estructura":
        lista, n = [], 0
        for (ini, fi, lletra, fam) in items:
            if str(lletra) == troba:
                n += 1
                fam = reemplaca if str(fam) == troba else fam
                lletra = reemplaca
            lista.append((ini, fi, lletra, fam))
        if not n:
            return list(items), 0, reemplaca
        return valida_canvis_seccions(lista, durada), n, reemplaca
    nou = saneja_nom_acord(reemplaca)
    if not nou:
        return list(items), 0, ""
    lista, n = [], 0
    for _a in items:
        t, fi, nom = float(_a[0]), float(_a[1]), _nom_item_acord(_a)
        if str(nom) == troba:
            n += 1
            nom = nou
        lista.append(Clip(t, fi, (nom, f"{t:.9f}")))
    if not n:
        return list(items), 0, nou
    return valida_canvis_acords(lista, durada), n, nou

def style(c):
    """Normalitza noms d’acords a un format estable i llegible.

    Exemples:
    - cmaj7 -> CMaj7
    - am -> A-
    - Em7 -> E-7
    - g/d -> G/D
    - Bbmaj7 -> B♭Maj7
    """
    import re

    if c is None:
        return ""

    s = str(c).strip()
    if not s:
        return ""
    if s.upper() == "N":
        return "N"

    def norm_alt(token):
        if token in {"#", "♯"}:
            return "#"
        if token in {"b", "♭"}:
            return "b"
        return token

    def norm_root(base):
        if not base:
            return ""
        m = re.match(r"^([A-Ga-g])([#b♯♭]?)", base)
        if not m:
            return base
        root, alt = m.groups()
        return f"{root.upper()}{norm_alt(alt)}"

    if "/" in s:
        base, bass = s.split("/", 1)
        return f"{style(base)}/{norm_root(bass)}"

    s = s.replace("♭", "b").replace("♯", "#")
    m = re.match(r"^([A-Ga-g])([#b]?)(.*)$", s)
    if not m:
        return s.strip()

    root, alt, quality = m.groups()
    root = root.upper()
    alt = norm_alt(alt)
    quality = quality.strip()

    if quality.lower().startswith("maj"):
        quality = "Maj" + quality[3:]
    elif quality.lower().startswith("m") and not quality.lower().startswith("maj"):
        quality = "-" + quality[1:]
    elif quality.lower().startswith("dim"):
        quality = "dim" + quality[3:]
    elif quality.lower().startswith("aug"):
        quality = "aug" + quality[3:]

    return f"{root}{alt}{quality}"

def segments_lliures(csv_path, total_s, log):
    # Mode Lliure: com la guia DAW però en segons, sense graella: N s'absorbeix,
    # repetits seguits es fusionen, capçalera N si cal.
    # El CSV del model és `inici,fi,acord` (S3): el fi es re-deriva.
    segs = []
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) < 3 or row[0].startswith("inici"):
                continue
            t, c = float(row[0]), row[2].strip()
            if c == "N" or (segs and segs[-1][1] == style(c)):
                continue
            segs.append([t, style(c)])
    if segs and segs[0][0] > 1e-9:
        segs.insert(0, [0.0, "N"])
        log(f"capçalera N: {segs[1][0]:.2f} s")
    out = []
    for i, (t, c) in enumerate(segs):
        fi = segs[i + 1][0] if i + 1 < len(segs) else total_s
        out.append((t, fi, c))
    return out

