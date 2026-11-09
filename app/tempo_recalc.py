"""Motor pur de recalcul del mapa de temps (F0).

Donada la durada d'un tram i una referència de BPM/compàs (la que ha posat
el músic amb el tap tempo i el compàs), busca la combinació de BPM, compàs i
nombre de compassos que més s'hi acosta i que fa que el tram tinga compassos
sencers.

No depén de Qt ni del model de clips: és una funció pura i testable.
"""
from __future__ import annotations

import math

from . import limits

# Penalitzacions de signatures poc habituals.
_COMUNS = {(4, 4), (3, 4), (2, 4), (6, 8), (12, 8)}
_MENYS_COMUNS = {(5, 4), (7, 4), (11, 4), (7, 8), (9, 8), (5, 8),
                 (6, 4), (2, 2), (3, 8)}

# Avisos (no canvien la decisió): desviació de BPM i sospita d'octava.
LLINDAR_DESVIACIO_BPM = 0.12
MARGE_SOSPITA_OCTAVA = 0.08

# Tolerància exacta per a fronteres calculades (tests i snap).
TOL_BEATS = 1e-6
# Tolerància OPERATIVA dels talls manuals sense snap: un beat dins d'esta
# franja es considera de frontera. Evita que moure la vora 1 ms canvie K i,
# amb ell, la signatura o el BPM.
TOL_TALL = 0.05


def n_negres_del_clip(beats, ini, fi, beat_factor=1.0, tol=TOL_TALL):
    """Negres (float) dels beats detectats dins `[ini, fi)`, o `None`.

    `beats` són els temps del detector (tactus); `beat_factor` els convertix a
    negres (negra=1, negra amb punt=1.5, corxera=0.5). Si no hi ha cap beat
    dins el clip retorna `None` (no `0`), perquè el recalcul puga inferir el
    nombre de negres des de la durada i la referència.

    `tol` és la tolerància operativa (50 ms per defecte): un beat dins d'eixa
    franja al voltant d'una frontera es classifica de manera estable. Els tests
    de frontera exacta poden passar `tol=TOL_BEATS`.
    """
    ini = float(ini)
    fi = float(fi)
    if fi <= ini:
        return None
    factor = float(beat_factor or 1.0)
    if factor <= 0:
        return None
    tol = float(tol)
    n = sum(1 for b in (beats or ())
            if ini - tol <= float(b) < fi - tol)
    if not n:
        return None
    return float(n) * factor


def beats_a_la_frontera(beats, ini, fi, tol=TOL_TALL):
    """Beats que queden dins la franja ambigua d'algun extrem del clip.

    No inclou els que cauen exactament damunt la frontera: eixos tenen una
    classificació clara (clip de la dreta). Serveix per a avisar que un tall
    sense snap està massa prop d'un beat i que el recompte depén de la
    tolerància.
    """
    ini = float(ini)
    fi = float(fi)
    tol = float(tol)
    if tol <= 0 or fi <= ini:
        return []
    return sorted({float(b) for b in (beats or ())
                   if 0.0 < abs(float(b) - ini) <= tol
                   or 0.0 < abs(float(b) - fi) <= tol})


def _bar_quarters(num, den):
    return float(num) * (4.0 / float(den))


def _distancia_compas(num, den, num_ref, den_ref):
    if (num, den) == (num_ref, den_ref):
        return 0.0
    if den == den_ref:
        diferencia = abs(int(num) - int(num_ref))
        if diferencia == 1:
            return 0.25
        if diferencia == 2:
            return 0.5
        return 1.5
    if num == num_ref:
        return 1.5
    return 2.0


def _penalitzacio_compas(num, den):
    if (num, den) in _COMUNS:
        return 0.0
    if (num, den) in _MENYS_COMUNS:
        return 0.2
    return 0.5


def _valida_referencia(bpm_ref, num_ref, den_ref):
    bpm_ref = float(bpm_ref)
    if not (limits.BPM_MIN <= bpm_ref <= limits.BPM_MAX):
        raise ValueError(
            f"BPM de referència fora de {limits.BPM_MIN:g}–"
            f"{limits.BPM_MAX:g}")
    if int(num_ref) < limits.NUM_MIN or int(num_ref) > limits.NUM_MAX:
        raise ValueError("Numerador de referència fora de rang")
    if int(den_ref) not in limits.DENOMINADORS_ADMESOS:
        raise ValueError("Denominador de referència no admissible")
    return bpm_ref, int(num_ref), int(den_ref)


def recalculca_tram(durada, bpm_ref, num_ref, den_ref, n_ref=None, *,
                    n_beats=None, bpm_min=None, bpm_max=None,
                    n_ventana=3,
                    w_bpm=1.0, w_compas=1.5, w_n=3.0, w_natural=0.1,
                    w_den=1.5, n_max=16, ajusta_beats=True,
                    pas_beat=1.0):
    """Busca la millor combinació (BPM, compàs, N) per a un tram.

    `n_ref` fixat = el nombre de compassos és una restricció (marcadors).
    Si no es passa, es calcula a partir de la referència i la durada.

    Retorna un diccionari o `None` si no hi ha cap combinació dins dels límits.
    """
    durada = float(durada)
    if durada <= 0:
        raise ValueError("La durada del tram ha de ser positiva")
    if n_beats is not None:
        n_beats = float(n_beats)
        if n_beats <= 0:
            n_beats = None
    pas_beat = float(pas_beat or 1.0)
    if pas_beat <= 0:
        pas_beat = 1.0
    bpm_ref, num_ref, den_ref = _valida_referencia(
        bpm_ref, num_ref, den_ref)
    bpm_min = limits.BPM_MIN if bpm_min is None else float(bpm_min)
    bpm_max = limits.BPM_MAX if bpm_max is None else float(bpm_max)

    def _amb_avisos(res):
        ratio = float(res["bpm"]) / float(bpm_ref)
        res["desviacio_bpm"] = ratio - 1.0
        res["sospita_octava"] = (
            abs(ratio - 2.0) <= 2.0 * MARGE_SOSPITA_OCTAVA
            or abs(ratio - 0.5) <= 0.5 * MARGE_SOSPITA_OCTAVA)
        return res

    bar_ref = _bar_quarters(num_ref, den_ref) * 60.0 / bpm_ref
    n_previst = max(1, int(round(durada / bar_ref)))
    n_fix = n_ref is not None
    beats_inferits = False

    # Sense beats detectats, si la referència BPM dona un nombre de negres
    # pràcticament enter, l'usem com a pista (7,02 → 7). No ho fem si el
    # nombre de compassos ve fixat pels marcadors.
    if n_beats is None and not n_fix:
        beats_ref = durada * bpm_ref / 60.0
        n_round = int(round(beats_ref))
        if n_round >= 1 and abs(beats_ref - n_round) <= 0.2:
            n_beats = float(n_round)
            beats_inferits = True

    # Si tenim els beats detectats, el nombre de negres del clip és una
    # restricció forta: 7 beats han de ser 7/4 (o una combinació equivalent),
    # no 2 compassos de 4/4. Quan hi ha beats, poden corregir el compàs i `N`
    # respecte de la referència base: es prefereix una signatura natural amb
    # el mínim de compassos (14 beats → 7/4 N=2, no 2/4 N=7; 8 beats → 4/4
    # N=2, no 8/4 N=1). La referència base decidix només els empats.
    if n_beats is not None:
        # Regla del múltiple: si la signatura de la referència encaixa exacta
        # amb el nombre de negres del clip, mana ella. Així 20/24/28 beats amb
        # base 4/4 són 4/4 N=5/6/7 (no 5/4/6/4/7/4); 12/36 amb base 3/4 són
        # 3/4 N=4/12; 6/12 amb base 6/8 són 6/8 N=2/4. La signatura de la
        # referència està exempta de `n_max` (clips llargs), però no de la
        # banda de BPM. Amb `n_fix`, només val si `N` coincidix amb el fixat.
        bq_ref = _bar_quarters(num_ref, den_ref)
        if bq_ref > 1.0 + 1e-9:
            n_ref_mult = int(round(float(n_beats) / bq_ref))
            if (n_ref_mult >= 1
                    and abs(n_ref_mult * bq_ref - float(n_beats)) <= 0.25
                    and (not n_fix or n_ref_mult == int(n_ref))):
                bpm_ref_mult = 60.0 * n_ref_mult * bq_ref / durada
                if bpm_min - 1e-9 <= bpm_ref_mult <= bpm_max + 1e-9:
                    return _amb_avisos({
                        "bpm": float(bpm_ref_mult),
                        "num": int(num_ref),
                        "den": int(den_ref),
                        "n": int(n_ref_mult),
                        "cost": 0.0,
                        "n_ref": int(n_previst),
                        "bpm_ref": float(bpm_ref),
                        "compas_ref": (int(num_ref), int(den_ref)),
                        "beats": float(n_beats),
                        "beats_detectats": float(n_beats),
                        "beats_ajustats": False,
                        "beats_usats": True,
                        "beats_inferits": beats_inferits,
                        "canvis": {
                            "bpm": abs(bpm_ref_mult - bpm_ref) > 1e-9,
                            "compas": False,
                            "n": (not n_fix) and n_ref_mult != n_previst,
                        },
                    })
        beats_candidats = []
        for den in limits.DENOMINADORS_ADMESOS:
            for num in range(limits.NUM_MIN, limits.NUM_MAX + 1):
                bq = _bar_quarters(num, den)
                n_exact = float(n_beats) / bq
                n = int(round(n_exact))
                if n < 1 or n > int(n_max):
                    continue
                if abs(n * bq - float(n_beats)) > 0.25:
                    continue
                # Evita solucions degenerades: un compàs de 1/4, 1/8 o 2/8
                # repetit moltes vegades (p. ex. 2/8 N=13 per a K=13).
                if bq <= 1.0 + 1e-9 and int(n) > 1:
                    continue
                if n_fix and n != int(n_ref):
                    continue
                bpm = 60.0 * n * bq / durada
                if not (bpm_min - 1e-9 <= bpm <= bpm_max + 1e-9):
                    continue
                cost = (w_bpm * abs(math.log2(bpm / bpm_ref))
                        + w_compas * _distancia_compas(
                            num, den, num_ref, den_ref)
                        + w_n * abs(n - n_previst) / max(1, n_previst)
                        + w_natural * _penalitzacio_compas(num, den)
                        + w_den * (den != den_ref))
                beats_candidats.append((
                    cost, abs(math.log2(bpm / bpm_ref)),
                    _distancia_compas(num, den, num_ref, den_ref),
                    bpm, num, den, n))
        if beats_candidats:
            # Prioritat 1: signatures COMUNES amb el MATEIX denominador que
            # la base i pocs compassos (8 beats → 4/4 N=2; 9 → 3/4 N=3; 6 →
            # 3/4 N=2, no 12/8 N=1). Prioritat 2: qualsevol signatura natural
            # amb el mateix denominador (14 → 7/4 N=2, no 2/4 N=7). Prioritat
            # 3: qualsevol natural. Si no, cost.
            def _natural(c):
                return (c[4], c[5]) in _COMUNS or (c[4], c[5]) in _MENYS_COMUNS
            comuns_den = [
                c for c in beats_candidats
                if c[6] <= 4 and c[5] == den_ref and (c[4], c[5]) in _COMUNS
            ]
            naturals_den = [
                c for c in beats_candidats if c[5] == den_ref and _natural(c)
            ]
            naturals = [c for c in beats_candidats if _natural(c)]
            if comuns_den:
                tria = comuns_den
            elif naturals_den:
                tria = naturals_den
            elif naturals:
                tria = naturals
            else:
                tria = beats_candidats
            # Menys compassos primer; el cost decidix empats (p. ex. 4/4 vs
            # 2/2 per a 8 beats, o 3/4 vs 6/8 per a 9).
            cost, _db, _dc, bpm, num, den, n = min(
                tria, key=lambda c: (c[6], c[0], c[1], c[2]))
            return _amb_avisos({
                "bpm": float(bpm),
                "num": int(num),
                "den": int(den),
                "n": int(n),
                "cost": float(cost),
                "n_ref": int(n_previst),
                "bpm_ref": float(bpm_ref),
                "compas_ref": (int(num_ref), int(den_ref)),
                "beats": float(n_beats),
                "beats_detectats": float(n_beats),
                "beats_ajustats": False,
                "beats_usats": True,
                "beats_inferits": beats_inferits,
                "canvis": {
                    "bpm": abs(bpm - bpm_ref) > 1e-9,
                    "compas": (num, den) != (num_ref, den_ref),
                    "n": (not n_fix) and n != n_previst,
                },
            })
        # Fallback d'un beat detectat: si K no es pot factoritzar en cap
        # compàs, provem un tacte amunt/avall. `pas_beat` val 1,5 negres amb
        # negra amb punt i 0,5 amb corxera; si els beats són inferits, el pas
        # és una negra (no hi ha cap tacte detectat). Prioritat al K' que
        # encaixa amb la signatura de la referència; si no, al BPM més pròxim.
        # No s'aplica amb n_fix.
        if (ajusta_beats and not n_fix
                and n_beats is not None and float(n_beats) > 0):
            pas = 1.0 if beats_inferits else pas_beat
            candidats = []
            for k2 in (n_beats - pas, n_beats + pas):
                if k2 < 1:
                    continue
                r2 = recalculca_tram(
                    durada, bpm_ref, num_ref, den_ref, n_ref=None,
                    n_beats=k2, bpm_min=bpm_min, bpm_max=bpm_max,
                    ajusta_beats=False, pas_beat=pas)
                if r2 is not None and r2.get("beats_usats"):
                    candidats.append((k2, r2))
            if candidats:
                def _mult_ref(k2):
                    if bq_ref <= 1.0 + 1e-9:
                        return False
                    n2 = int(round(float(k2) / bq_ref))
                    return (n2 >= 1
                            and abs(n2 * bq_ref - float(k2)) <= 0.25)
                refs = [c for c in candidats if _mult_ref(c[0])]
                pool = refs or candidats
                k2, r = min(
                    pool,
                    key=lambda c: abs(math.log(c[1]["bpm"] / bpm_ref)))
                r["beats"] = float(k2)
                r["beats_detectats"] = float(n_beats)
                r["beats_ajustats"] = True
                r["beats_inferits"] = beats_inferits
                return _amb_avisos(r)
    if n_fix:
        n_valors = [int(n_ref)]
        n_cost_ref = int(n_ref)
    else:
        n_valors = range(max(1, n_previst - int(n_ventana)),
                         n_previst + int(n_ventana) + 1)
        n_cost_ref = n_previst

    millor = None
    for n in n_valors:
        for den in limits.DENOMINADORS_ADMESOS:
            for num in range(limits.NUM_MIN, limits.NUM_MAX + 1):
                bpm = 60.0 * n * num * (4.0 / den) / durada
                if not (bpm_min - 1e-9 <= bpm <= bpm_max + 1e-9):
                    continue
                cost = (w_bpm * abs(math.log2(bpm / bpm_ref))
                        + w_compas * _distancia_compas(
                            num, den, num_ref, den_ref)
                        + w_n * abs(n - n_cost_ref) / max(1, n_cost_ref)
                        + w_natural * _penalitzacio_compas(num, den))
                candidat = (cost, abs(n - n_cost_ref),
                            abs(math.log2(bpm / bpm_ref)),
                            _distancia_compas(num, den, num_ref, den_ref),
                            bpm, num, den, n)
                if millor is None or candidat < millor:
                    millor = candidat
    if millor is None:
        return None
    cost, _dn, _db, _dc, bpm, num, den, n = millor
    return _amb_avisos({
        "bpm": float(bpm),
        "num": int(num),
        "den": int(den),
        "n": int(n),
        "cost": float(cost),
        "n_ref": int(n_previst),
        "bpm_ref": float(bpm_ref),
        "compas_ref": (int(num_ref), int(den_ref)),
        "beats": None if n_beats is None else float(n_beats),
        "beats_detectats": None if n_beats is None else float(n_beats),
        "beats_ajustats": False,
        "beats_usats": False,
        "beats_inferits": False,
        "canvis": {
            "bpm": abs(bpm - bpm_ref) > 1e-9,
            "compas": (num, den) != (num_ref, den_ref),
            "n": (not n_fix) and n != n_previst,
        },
    })


def avis_de_resultat(resultat):
    """Text combinat d'avisos d'un resultat de `recalculca_tram`.

    No decidix res: només descriu beats ajustats, desviació de BPM i sospita
    d'octava. Retorna "" si no hi ha cap avís.
    """
    if not resultat:
        return ""
    parts = []

    def _fmt(v):
        return "—" if v is None else f"{float(v):g}"

    if resultat.get("beats_ajustats"):
        if resultat.get("beats_inferits"):
            parts.append(
                "sense beats detectats; durada incompatible amb compassos "
                f"sencers ({_fmt(resultat.get('beats_detectats'))}→"
                f"{_fmt(resultat.get('beats'))} negres)")
        else:
            parts.append(
                f"beats ajustats {_fmt(resultat.get('beats_detectats'))}→"
                f"{_fmt(resultat.get('beats'))}")
    desviacio = float(resultat.get("desviacio_bpm") or 0.0)
    if abs(desviacio) > LLINDAR_DESVIACIO_BPM:
        parts.append(f"BPM desviat {desviacio * 100.0:+.1f}%")
    if resultat.get("sospita_octava"):
        parts.append("sospita d'octava")
    return "; ".join(parts)
