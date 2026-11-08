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
                    w_den=1.5, n_max=16):
    """Busca la millor combinació (BPM, compàs, N) per a un tram.

    `n_ref` fixat = el nombre de compassos és una restricció (marcadors).
    Si no es passa, es calcula a partir de la referència i la durada.

    Retorna un diccionari o `None` si no hi ha cap combinació dins dels límits.
    """
    durada = float(durada)
    if durada <= 0:
        raise ValueError("La durada del tram ha de ser positiva")
    bpm_ref, num_ref, den_ref = _valida_referencia(
        bpm_ref, num_ref, den_ref)
    bpm_min = limits.BPM_MIN if bpm_min is None else float(bpm_min)
    bpm_max = limits.BPM_MAX if bpm_max is None else float(bpm_max)

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
            n_beats = n_round
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
                    return {
                        "bpm": float(bpm_ref_mult),
                        "num": int(num_ref),
                        "den": int(den_ref),
                        "n": int(n_ref_mult),
                        "cost": 0.0,
                        "n_ref": int(n_previst),
                        "bpm_ref": float(bpm_ref),
                        "compas_ref": (int(num_ref), int(den_ref)),
                        "beats": int(n_beats),
                        "beats_usats": True,
                        "beats_inferits": beats_inferits,
                        "canvis": {
                            "bpm": abs(bpm_ref_mult - bpm_ref) > 1e-9,
                            "compas": False,
                            "n": (not n_fix) and n_ref_mult != n_previst,
                        },
                    }
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
                # Evita solucions absurdes del tipus 29 compassos d'1/4 quan
                # el nombre de beats no cap en un compàs natural.
                if int(num) == 1 and int(n) > 1:
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
            return {
                "bpm": float(bpm),
                "num": int(num),
                "den": int(den),
                "n": int(n),
                "cost": float(cost),
                "n_ref": int(n_previst),
                "bpm_ref": float(bpm_ref),
                "compas_ref": (int(num_ref), int(den_ref)),
                "beats": int(n_beats),
                "beats_usats": True,
                "beats_inferits": beats_inferits,
                "canvis": {
                    "bpm": abs(bpm - bpm_ref) > 1e-9,
                    "compas": (num, den) != (num_ref, den_ref),
                    "n": (not n_fix) and n != n_previst,
                },
            }
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
    return {
        "bpm": float(bpm),
        "num": int(num),
        "den": int(den),
        "n": int(n),
        "cost": float(cost),
        "n_ref": int(n_previst),
        "bpm_ref": float(bpm_ref),
        "compas_ref": (int(num_ref), int(den_ref)),
        "beats": None if n_beats is None else int(n_beats),
        "beats_usats": False,
        "beats_inferits": False,
        "canvis": {
            "bpm": abs(bpm - bpm_ref) > 1e-9,
            "compas": (num, den) != (num_ref, den_ref),
            "n": (not n_fix) and n != n_previst,
        },
    }
