#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ajust d'un sol BPM a partir de marcadors de compàs (Fase 5).

Mínims quadrats: donats marcadors consecutius (inici de compàs), s'ajusta una
línia `t = a + k * d` (temps vs índex de compàs) i es deriva el BPM. Si el
residu supera el llindar, es parteix recursivament pel punt de màxim residu.
"""

from __future__ import annotations

import math


def _ajusta_lineal(marcadors):
    """Retorna (a, d, residu_max_s, residu_rms_s) per mínims quadrats.

    marcadors: llista de temps (segons) dels inicis de compàs consecutius.
    """
    ms = sorted(float(x) for x in (marcadors or ()))
    n = len(ms)
    if n < 2:
        raise ValueError("Calen almenys dos marcadors")
    ks = list(range(n))
    sum_k = sum(ks)
    sum_t = sum(ms)
    sum_kt = sum(k * t for k, t in zip(ks, ms))
    sum_k2 = sum(k * k for k in ks)
    denom = n * sum_k2 - sum_k * sum_k
    if abs(denom) < 1e-12:
        raise ValueError("Marcadors degenerats")
    d = (n * sum_kt - sum_k * sum_t) / denom
    a = (sum_t - d * sum_k) / n
    errors = [abs(t - (a + k * d)) for k, t in zip(ks, ms)]
    residu_max = max(errors) if errors else 0.0
    residu_rms = math.sqrt(sum(e * e for e in errors) / len(errors)) if errors else 0.0
    return a, d, residu_max, residu_rms


def ajusta_un_bpm(marcadors, num=4, den=4):
    """Ajusta un sol BPM per mínims quadrats.

    Retorna dict: bpm, a (offset), d (durada compàs), residu_max_ms,
    residu_rms_ms, n (nombre de marcadors).
    """
    a, d, rmax, rrms = _ajusta_lineal(marcadors)
    if d <= 0:
        raise ValueError("Durada de compàs no vàlida")
    # durada compàs = num*4/den * 60 / bpm  =>  bpm = num*4/den * 60 / d
    bq = num * 4.0 / float(den)
    bpm = bq * 60.0 / d
    return {
        "bpm": bpm,
        "offset": a,
        "durada_compas": d,
        "residu_max_ms": rmax * 1000.0,
        "residu_rms_ms": rrms * 1000.0,
        "n": len(marcadors or ()),
    }


def ajusta_amb_particio(marcadors, llindar_ms=40.0, num=4, den=4):
    """Ajusta BPM amb partició recursiva si el residu supera el llindar.

    Retorna (trams, motius) on trams és llista de (ini, fi, bpm, num, den)
    i motius és llista de strings amb el motiu de cada divisió.
    """
    ms = sorted(float(x) for x in (marcadors or ()))
    if len(ms) < 2:
        raise ValueError("Calen almenys dos marcadors")
    # Els trams es construeixen sobre els marcadors. El primer tram comença al
    # primer marcador; afegim un marcador inicial a 0 si cal.
    # Per simplicitat, els trams cobreixen [ms[0], ms[-1]].
    motius = []

    def _parteix(sub_ms):
        # sub_ms: llista de marcadors del subinterval
        if len(sub_ms) < 2:
            return []
        try:
            info = ajusta_un_bpm(sub_ms, num, den)
        except ValueError:
            return []
        if info["residu_max_ms"] <= llindar_ms or len(sub_ms) < 3:
            # un sol tram
            return [(sub_ms[0], sub_ms[-1], info["bpm"], num, den)]
        # partir pel punt que minimitza el residu màxim dels dos costats
        millor_k = None
        millor_residu = float("inf")
        for k in range(1, len(sub_ms) - 1):
            try:
                i1 = ajusta_un_bpm(sub_ms[:k + 1], num, den)
                i2 = ajusta_un_bpm(sub_ms[k:], num, den)
            except ValueError:
                continue
            residu = max(i1["residu_max_ms"], i2["residu_max_ms"])
            if residu < millor_residu:
                millor_residu = residu
                millor_k = k
        if millor_k is None:
            return [(sub_ms[0], sub_ms[-1], info["bpm"], num, den)]
        kmax = millor_k
        motius.append(
            f"Divisió a {sub_ms[kmax]:.3f}s (residu màx. "
            f"{info['residu_max_ms']:.0f} ms > {llindar_ms:.0f} ms)")
        esq = _parteix(sub_ms[:kmax + 1])
        dret = _parteix(sub_ms[kmax:])
        # Evitar perdre trams quan un costat té un sol tram.
        out = list(esq)
        for t in dret:
            if not out or abs(float(t[0]) - float(out[-1][0])) > 1e-9:
                out.append(t)
        return out

    trams = _parteix(ms)
    # Normalitzar contigüitat
    out = []
    for i, (ini, fi, bpm, n, d) in enumerate(trams):
        if out:
            ini = out[-1][1]
        out.append((float(ini), float(fi), float(bpm), int(n), int(d)))
    return out, motius