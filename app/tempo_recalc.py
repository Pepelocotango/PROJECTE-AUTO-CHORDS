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
_MENYS_COMUNS = {(5, 4), (7, 8), (9, 8), (5, 8), (6, 4), (2, 2), (3, 8)}


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
        return 1.0
    return 1.5


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
                    bpm_min=None, bpm_max=None,
                    n_ventana=3,
                    w_bpm=1.0, w_compas=1.5, w_n=3.0, w_natural=0.1):
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
        "canvis": {
            "bpm": abs(bpm - bpm_ref) > 1e-9,
            "compas": (num, den) != (num_ref, den_ref),
            "n": (not n_fix) and n != n_previst,
        },
    }
