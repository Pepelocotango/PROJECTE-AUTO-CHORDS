"""Motor de talls de tempo/compàs amb Snap de Beats QM.

Funcions pures (sense Qt) per al pla ``00PER FER/PLA_MOTOR_TALLS_QM.md``.
El visor s'encarrega del diàleg, l'undo i la reproducció.

La unitat interna és sempre la **negra**. `Bq` és la duració musical del costat
en negres; pot ser fraccionari (7/8 amb corxera: 3,5).
"""
from __future__ import annotations

import math

from . import bpm_unit, limits, mapa_tempo

TOL = 1e-7
NUM_MAX = 12
MAX_CLIPS_COSTAT = 2
MAX_OPCIONS = 6
MIN_OPCIONS_4 = 2


def _bar_quarters(num, den):
    return float(num) * 4.0 / float(den)


def _camps(tr):
    """Retorna `(bpm, num, den, beat_unit)` d'un TramMapa o d'una tupla."""
    bpm = float(getattr(tr, "bpm", tr[2]))
    num = int(getattr(tr, "num", tr[3]))
    den = int(getattr(tr, "den", tr[4]))
    unit = getattr(tr, "beat_unit", None)
    if not unit:
        unit = bpm_unit.unitat_per_defecte(num, den)
    return bpm, num, den, unit


def _enter(x):
    n = int(round(float(x)))
    return n if abs(float(x) - n) <= TOL else None


def _num_de_quarters(q, den):
    """Numerador enter d'un compàs `num/den` que fa `q` negres."""
    num = _enter(float(q) * float(den) / 4.0)
    if num is None or num < 1 or num > NUM_MAX:
        return None
    return num


def _compta_beats(beats, ini, fi, tol=TOL):
    """Compta beats en `[ini, fi)`. El beat de la frontera va a la dreta."""
    ini = float(ini)
    fi = float(fi)
    return sum(1 for b in beats or ()
               if ini - tol <= float(b) < fi - tol)


def _knots_temps(ini, fi, bq, beats, factor):
    """Knots `(negres, temps)` amb els beats QM reals, si n'hi ha."""
    ini, fi, bq = float(ini), float(fi), float(bq)
    beats = [float(b) for b in (beats or ())
             if ini - TOL <= float(b) < fi - TOL]
    if not beats:
        return [(0.0, ini), (bq, fi)]
    # Si el primer beat no cau a l'inici, compta'l al primer pols.
    dep = 0.0 if abs(beats[0] - ini) <= TOL else float(factor)
    knots = [(0.0, ini)]
    for i, b in enumerate(beats):
        q = dep + i * float(factor)
        if q <= TOL or q >= bq - TOL:
            continue
        t = float(b)
        if t <= ini + TOL or t >= fi - TOL:
            continue
        knots.append((q, t))
    knots.append((bq, fi))
    # Elimina q duplicats i assegura monotonia.
    out = []
    for q, t in sorted(knots, key=lambda x: x[0]):
        if out and abs(q - out[-1][0]) <= TOL:
            continue
        if out and t < out[-1][1] - TOL:
            continue
        out.append((q, t))
    if out[0][0] > TOL:
        out.insert(0, (0.0, ini))
    if out[-1][0] < bq - TOL:
        out.append((bq, fi))
    return out


def _temps_de_q(q, knots, ini, fi):
    q = max(0.0, min(float(q), knots[-1][0]))
    for (q0, t0), (q1, t1) in zip(knots, knots[1:]):
        if q <= q1 + TOL:
            if q1 <= q0 + TOL:
                return t1
            return t0 + (t1 - t0) * (q - q0) / (q1 - q0)
    return float(fi)


def _clips_de_costats(ini, fi, bq, parts, beats=None, factor=1.0):
    """Construeix clips a partir de `[(quarters, num, den), …]`.

    Les fronteres cauen als temps reals dels beats QM si se'n passen; si no,
    es reparteixen proporcionalment a les negres de cada part.
    """
    dt = float(fi) - float(ini)
    if dt <= TOL or bq <= TOL:
        return None
    knots = _knots_temps(ini, fi, bq, beats, factor)
    clips = []
    q_acum = 0.0
    t_acum = float(ini)
    for part in parts:
        q, num, den = float(part[0]), int(part[1]), int(part[2])
        n = float(part[3]) if len(part) > 3 else 1.0
        if q <= TOL:
            continue
        q_fi = q_acum + q
        fi_clip = (float(fi) if abs(q_fi - bq) <= TOL
                   else _temps_de_q(q_fi, knots, ini, fi))
        dur = fi_clip - t_acum
        bpm = 60.0 * q / dur if dur > 0 else 0.0
        if not (limits.BPM_MIN - TOL <= bpm <= limits.BPM_MAX + TOL):
            return None
        if dur < limits.TEMPS_MIN_CLIP - TOL:
            return None
        clips.append(mapa_tempo.TramMapa(
            t_acum, fi_clip, bpm, "normal", f"{int(num)}/{int(den)}",
            "", n, bpm_unit.unitat_per_defecte(int(num), int(den))))
        q_acum = q_fi
        t_acum = fi_clip
    if abs(q_acum - float(bq)) > 1e-4 or abs(t_acum - float(fi)) > 1e-4:
        return None
    return clips


def _opcio(ini, fi, bq, parts, base_bars=0, cross=False, beats=None,
           factor=1.0):
    # `n` de cada part = compassos sencers que ocupa.
    parts_amb_n = []
    for q, num, den in parts:
        n = _enter(float(q) / _bar_quarters(num, den))
        if n is None or n < 1:
            return None
        parts_amb_n.append((q, num, den, n))
    clips = _clips_de_costats(ini, fi, bq, parts_amb_n,
                               beats=beats, factor=factor)
    if not clips:
        return None
    # Base+extrany: una excepció. Secció sencera: N compassos extranys.
    if base_bars > 0:
        extranys = max(0, len(parts_amb_n) - 1)
    else:
        extranys = sum(n for _q, _num, _den, n in parts_amb_n)
    etiqueta = " + ".join(
        f"{int(c.num)}/{int(c.den)} N={int(c.n)} ({float(c.bpm):.3f})"
        for c in clips)
    return {
        "clips": clips,
        "etiqueta": etiqueta,
        "n_extranys": extranys,
        "n_base": base_bars,
        "n_clips": len(clips),
        "es_4": any(int(c.den) == 4 for c in clips),
        "cross": bool(cross),
    }


def _afegeix(out, opcio):
    if opcio is None:
        return
    clau = tuple((round(float(c.ini), 6), round(float(c.fi), 6),
                 round(float(c.bpm), 6), int(c.num), int(c.den), int(c.n))
                 for c in opcio["clips"])
    if clau not in {o["_clau"] for o in out}:
        opcio["_clau"] = clau
        out.append(opcio)


def _pures(bq, bases):
    out = []
    for num, den in bases:
        n = _enter(float(bq) / _bar_quarters(num, den))
        if n is None or n < 1:
            continue
        # La pura no necessita BPM de candidat: es calcula al clip.
        out.append((num, den, n))
    return out


def _opcions_costat(ini, fi, bq, bases, beats=None, factor=1.0):
    """Candidats per a un costat, sense aplicar el filtre de 1/4."""
    ini, fi, bq = float(ini), float(fi), float(bq)
    out = []
    pures = _pures(bq, bases)
    if pures:
        # Si hi ha pura, no es proposen alternatives exòtiques.
        for num, den, n in pures:
            _afegeix(out, _opcio(
                ini, fi, bq, [(bq, num, den)], base_bars=n,
                beats=beats, factor=factor))
        return out

    for base_num, base_den in bases:
        base_bar = _bar_quarters(base_num, base_den)
        max_n = int(math.floor(bq / base_bar + TOL))
        # Base + exactament un compàs extrany (final i principi).
        for n_base in range(max_n, 0, -1):
            odd_q = bq - n_base * base_bar
            if odd_q <= TOL:
                continue
            num = _num_de_quarters(odd_q, base_den)
            if num is None:
                continue
            parts = [(n_base * base_bar, base_num, base_den),
                     (odd_q, num, base_den)]
            _afegeix(out, _opcio(ini, fi, bq, parts, base_bars=n_base,
                                 beats=beats, factor=factor))
            parts_rev = [(odd_q, num, base_den),
                         (n_base * base_bar, base_num, base_den)]
            _afegeix(out, _opcio(ini, fi, bq, parts_rev, base_bars=n_base,
                                 beats=beats, factor=factor))
        # Secció sencera en un compàs extrany.
        for num in range(1, NUM_MAX + 1):
            bar = _bar_quarters(num, base_den)
            n = _enter(bq / bar)
            if n is not None and n >= 1:
                _afegeix(out, _opcio(
                    ini, fi, bq, [(bq, num, base_den)], base_bars=0,
                    beats=beats, factor=factor))
        # Canvi a denominador 4: només base + un compàs /4, mai /4 sol.
        if int(base_den) != 4:
            for n_base in range(max_n, 0, -1):
                odd_q = bq - n_base * base_bar
                num = _enter(odd_q)
                if num is None or num < 1 or num > NUM_MAX:
                    continue
                parts = [(n_base * base_bar, base_num, base_den),
                         (odd_q, num, 4)]
                _afegeix(out, _opcio(
                    ini, fi, bq, parts, base_bars=n_base, cross=True,
                    beats=beats, factor=factor))
                parts_rev = [(odd_q, num, 4),
                             (n_base * base_bar, base_num, base_den)]
                _afegeix(out, _opcio(
                    ini, fi, bq, parts_rev, base_bars=n_base, cross=True,
                    beats=beats, factor=factor))

    # Filtra 1/4 si hi ha cap alternativa sense numerador 1.
    te_alternativa = any(
        not any(int(c.num) == 1 for c in o["clips"]) for o in out)
    if te_alternativa:
        out = [o for o in out
               if not any(int(c.num) == 1 for c in o["clips"])]
    return _ordena(out)


def _ordena(out):
    return sorted(out, key=lambda o: (
        int(o["n_extranys"]), -int(o["n_base"]), int(o["n_clips"]),
        1 if o["cross"] else 0, o["etiqueta"]))


def _opcio_sense_beats(ini, fi, ref_base):
    """Fallback: Ref. pura amb N arrodonit i BPM derivat."""
    bpm_ref, num, den = ref_base
    bar = _bar_quarters(num, den)
    dt = float(fi) - float(ini)
    if dt <= TOL or bar <= TOL:
        return []
    n = max(1, int(round(dt / (bar * 60.0 / float(bpm_ref)))))
    bpm = 60.0 * n * bar / dt
    if not (limits.BPM_MIN - TOL <= bpm <= limits.BPM_MAX + TOL):
        return []
    clip = mapa_tempo.TramMapa(
        float(ini), float(fi), bpm, "normal", f"{int(num)}/{int(den)}",
        "", float(n), bpm_unit.unitat_per_defecte(num, den))
    return [{"clips": [clip], "etiqueta": f"{num}/{den} N={n} ({bpm:.3f})",
             "n_extranys": 0, "n_base": n, "n_clips": 1,
             "es_4": int(den) == 4, "cross": False}]


def opcions_tall(trams, t, durada, offset, beats, ref_base, beat_factor):
    """Retorna `[opcions_esquerra, opcions_dreta]` o `None`.

    `beats` són els beats QM detectats. `beat_factor` convertix cada beat a
    negres. Les opcions de cada costat ja estan filtrades i ordenades.
    """
    t = float(t)
    for i, tr in enumerate(trams or ()):
        ini = float(getattr(tr, "ini", tr[0]))
        fi = float(getattr(tr, "fi", tr[1]))
        if not (ini + TOL < t < fi - TOL):
            continue
        _bpm, local_num, local_den, _unit = _camps(tr)
        ref_bpm, ref_num, ref_den = ref_base
        bases = []
        for m in ((local_num, local_den), (int(ref_num), int(ref_den))):
            if m[0] > 0 and m[1] > 0 and m not in bases:
                bases.append(m)
        sides = []
        for a, b in ((ini, t), (t, fi)):
            n = _compta_beats(beats, a, b)
            if n <= 0:
                opcions = _opcio_sense_beats(a, b, ref_base)
            else:
                bq = float(n) * float(beat_factor)
                beats_costat = [x for x in beats
                                if a - TOL <= float(x) < b - TOL]
                opcions = _opcions_costat(
                    a, b, bq, bases, beats=beats_costat,
                    factor=beat_factor)
            if not opcions:
                return None
            sides.append(opcions)
        return sides
    return None


def selecciona_opcions(opcions, max_opcions=MAX_OPCIONS,
                       min_4=MIN_OPCIONS_4):
    """Retalla a `max_opcions` garantint `min_4` opcions amb denominador 4."""
    out = list(opcions)[:int(max_opcions)]
    if min_4 <= 0 or sum(1 for o in out if o.get("es_4")) >= min_4:
        return out
    resto = [o for o in opcions if o.get("es_4") and o not in out]
    for o in resto:
        if not out:
            break
        # Substituïx la pitjor opció que no siga /4.
        idx = next((j for j in range(len(out) - 1, -1, -1)
                    if not out[j].get("es_4")), None)
        if idx is None:
            break
        out[idx] = o
        if sum(1 for x in out if x.get("es_4")) >= min_4:
            break
    return _ordena(out)
