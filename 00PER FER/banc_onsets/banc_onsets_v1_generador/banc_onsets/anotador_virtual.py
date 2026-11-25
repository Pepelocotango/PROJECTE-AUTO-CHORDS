# -*- coding: utf-8 -*-
"""Anotador virtual · Fase 0.A.

Implementa el criteri numèric revisat de l'anotador humà:

    primer sample on |x| supera 3 × RMS d'una base fixa de 20 ms
    que acaba 10 ms abans del clic aproximat, i es manté ≥1 ms.

La cerca va de ``t_aprox − 10 ms`` a ``t_aprox + 80 ms``. Els esdeveniments
anteriors a ``t_aprox − 10 ms`` no es consideren l'atac objectiu.

El criteri del 5 % del pic local queda com a diagnòstic: no és el detector
principal.

Treballa sobre el senyal ja renderitzat (amb soroll i filtres), tal com el
veuria una persona, i NO coneix la referència analítica ni el detector.
"""
from __future__ import annotations

import numpy as np

PARAMS = {
    "finestra_base_s": 0.020,
    "base_fi_abans_s": 0.010,
    "base_regio_s": 0.100,
    "factor_rms": 3.0,
    "sostingut_s": 0.001,
    "consecutius": 3,
    "fraccio_pic_alt": 0.05,
    "cerca_abans_s": 0.010,
    "cerca_despres_s": 0.080,
}


def parametres():
    return dict(PARAMS)


def a_mono_abs(x):
    """Valor absolut d'un senyal 1-D o (n, canals): màxim entre canals."""
    x = np.abs(np.asarray(x, dtype=np.float64))
    return x if x.ndim == 1 else x.max(axis=1)


def _primers_amb_sostingut(a, lo, hi, llindar, k):
    """Primer índex amb ``k`` samples consecutius per damunt del llindar."""
    if hi - lo <= k:
        return None
    ok = np.ones(hi - lo - k + 1, dtype=bool)
    for j in range(k):
        ok &= a[lo + j:hi - k + 1 + j] > llindar
    if not ok.any():
        return None
    return lo + int(np.argmax(ok))


def anota(x, sr, t_aprox, criteri="rms", base="fix"):
    """Retorna el temps (s) de l'atac anotat, o None si no en troba cap.

    ``t_aprox`` és el punt aproximat on l'anotador «ha fet clic».

    ``base="fix"`` usa el criteri revisat. ``base="lliscant"`` es conserva com a
    diagnòstic del criteri antic (RMS immediatament anterior a cada sample).
    """
    a = a_mono_abs(x)
    p = PARAMS
    w = max(1, int(round(p["finestra_base_s"] * sr)))
    k_new = max(1, int(round(p["sostingut_s"] * sr)))
    k_old = max(1, int(p["consecutius"]))
    centre = int(round(float(t_aprox) * sr))
    lo = max(0, centre - int(round(p["cerca_abans_s"] * sr)))
    hi = min(a.size, centre + int(round(p["cerca_despres_s"] * sr)))
    if hi - lo <= k_new:
        return None

    if criteri == "pic":
        llindar = p["fraccio_pic_alt"] * float(a[lo:hi].max())
        i = _primers_amb_sostingut(a, lo, hi, llindar, k_new)
        return None if i is None else i / float(sr)
    if criteri != "rms":
        raise ValueError(f"criteri desconegut: {criteri!r}")

    quad = np.concatenate([[0.0], np.cumsum(a * a)])

    def rms(i0, i1):
        i0 = max(0, i0)
        n = max(1, i1 - i0)
        return np.sqrt(max(quad[i1] - quad[i0], 0.0) / n)

    if base == "fix":
        # Base fixa per regla: la finestra de 20 ms més silenciosa dins dels
        # 100 ms previs al clic. Així un esdeveniment anterior no eleva el
        # llindar si hi ha un tros net abans.
        pre_fi = max(0, centre - int(round(p["base_fi_abans_s"] * sr)))
        pre_ini = max(0, centre - int(round(p["base_regio_s"] * sr)))
        if pre_fi - pre_ini < w:
            pre_ini = max(0, pre_fi - w)
        if pre_fi - pre_ini < max(1, w // 2):
            pre_ini, pre_fi = 0, min(w, a.size)
        melhor = None
        for ini in range(pre_ini, max(pre_ini, pre_fi - w) + 1):
            fim = min(a.size, ini + w)
            if fim - ini < max(1, w // 2):
                continue
            r = rms(ini, fim)
            if melhor is None or r < melhor[0]:
                melhor = (r, ini, fim)
        r = melhor[0] if melhor is not None else rms(0, min(w, a.size))
        i = _primers_amb_sostingut(a, lo, hi, p["factor_rms"] * r, k_new)
        return None if i is None else i / float(sr)

    if base == "lliscant":
        # Criteri antic, només per comparar. Manté 3 samples.
        idx = np.arange(lo, hi - k_old + 1)
        ini = np.maximum(idx - w, 0)
        n = np.maximum(idx - ini, 1)
        r = np.sqrt(np.maximum(quad[idx] - quad[ini], 0.0) / n)
        i = _primers_amb_sostingut(a, lo, hi, p["factor_rms"] * r, k_old)
        return None if i is None else i / float(sr)

    raise ValueError(f"base desconeguda: {base!r}")
