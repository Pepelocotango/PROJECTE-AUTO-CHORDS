#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Marcadors humans de la cançó (inici de compàs, en viu).

Un **marcador** és només un instant marcat per l'operador mentre escolta
(tecla `+` o botó «Afegeix marker»). Quan es crea, **talla** el carril de
BPM/compàs i el d'estructura en eixe punt (comença un clip nou a cada un); a
partir d'ací el marcador és **independent**: si després mous o esborres eixos
clips, el marcador es queda on el vas posar.

Este mòdul és **pur** (sense Qt ni fitxers): llista de temps ordenada, amb
alta, baixa i consulta. La persistència i el model viu són a `pipeline` i
`Visor`.
"""

import math

#: Dos marcadors més a prop que això són el mateix colp (rebot de la tecla).
SEPARACIO_MIN = 0.05


def normalitza_marcadors(marques, durada):
    """Llista ordenada, sense duplicats i dins de `(0, durada)`."""
    durada = float(durada or 0.0)
    out = []
    for m in marques or ():
        try:
            t = float(m)
        except (TypeError, ValueError):
            continue
        if 0.0 < t < durada:
            out.append(round(t, 6))
    out.sort()
    net = []
    for t in out:
        if not net or t - net[-1] >= SEPARACIO_MIN:
            net.append(t)
    return net


def afegeix(marques, t, durada, separacio_min=SEPARACIO_MIN):
    """Torna la llista amb `t` afegit (o la MATEIXA si no és vàlid o és rebot)."""
    durada = float(durada or 0.0)
    t = float(t)
    if not (0.0 < t < durada):
        return list(marques or ())
    actuals = normalitza_marcadors(marques, durada)
    if any(abs(t - m) < float(separacio_min) for m in actuals):
        return actuals
    return normalitza_marcadors(actuals + [t], durada)


def elimina(marques, idx):
    """Torna la llista sense el marcador `idx` (o la mateixa si no hi és)."""
    actuals = list(marques or ())
    if not (0 <= int(idx) < len(actuals)):
        return actuals
    return actuals[:int(idx)] + actuals[int(idx) + 1:]


def index_a(marques, t, tol=0.15):
    """Índex del marcador més pròxim a `t` (dins de `tol`), o `None`."""
    millor, dist = None, float(tol)
    for i, m in enumerate(marques or ()):
        d = abs(float(m) - float(t))
        if d <= dist:
            millor, dist = i, d
    return millor


def seguent(marques, t):
    """Primer marcador després de `t` (o `None`)."""
    for m in marques or ():
        if float(m) > float(t) + 1e-9:
            return float(m)
    return None


def anterior(marques, t):
    """Últim marcador abans de `t` (o `None`)."""
    out = None
    for m in marques or ():
        if float(m) < float(t) - 1e-9:
            out = float(m)
    return out


def candidats_bpm(marques, num=4, den=4, bpm_min=60.0, bpm_max=180.0,
                  preferit=None, max_candidats=6, tol=0.06):
    """BPMs que fan que TOTS els intervals entre marcadors siguen compassos.

    Un marcador és un **inici de compàs**, així que la distància entre dos
    marcadors ha de ser un nombre enter de compassos. Ací es busquen tots els
    BPM que ho complixen (residu ≈ 0) i es tornen ordenats: primer els que
    quadren millor, i entre eixos el més a prop del BPM `preferit` (el de la
    barra, si n'hi ha).

    L'ambigüitat del doble/meitat és real (10 s poden ser 4 compassos a 96 o 6
    a 144): per això es torna una LLISTA i decidix l'operador.

    Retorna ``[{"bpm", "residu", "bar", "intervals": [(dt, k, bpm_i)],
    "compassos": [k, …]}, …]``.
    """
    ms = normalitza_marcadors(marques, 1e12)
    if len(ms) < 2:
        raise ValueError("Calen almenys dos marcadors per a traure el BPM")
    gaps = [b - a for a, b in zip(ms, ms[1:])]
    num, den = int(num), int(den)
    if num < 1 or den < 1:
        raise ValueError("El compàs no és vàlid")
    preferit = float(preferit) if preferit else 110.0

    def _residu(bpm):
        """Error mitjà, en SEGONS, de cada tall respecte de la línia més pròxima.

        En segons (no en fracció de compàs): si es mesura en fracció, els BPM
        alts ixen sempre millor només perquè el compàs és més curt i el mateix
        error absolut és una fracció menor.
        """
        bar = num * (4.0 / float(den)) * 60.0 / float(bpm)
        if bar <= 0:
            return 9.9
        total = 0.0
        for g in gaps:
            k = max(1, int(round(g / bar)))
            total += abs(g - k * bar)
        return total / len(gaps)

    def _premi(bpm):
        # Preferència suau pel rang musical habitual (desfà el doble/meitat).
        if bpm < 70.0:
            return 0.5 * (70.0 - bpm) / 70.0
        if bpm > 160.0:
            return 0.5 * (bpm - 160.0) / 160.0
        return 0.0

    tots, b = [], float(bpm_min)
    while b <= float(bpm_max) + 1e-9:
        bar = num * (4.0 / den) * 60.0 / b
        ks = [max(1, int(round(g / bar))) for g in gaps]
        tots.append((_residu(b) + _premi(b), _residu(b), b, bar, ks))
        b += 0.05
    # El cost s'arredonix a 1 ms perquè els empats exactes (residu 0) no els
    # decidisca el soroll de coma flotant: a igualtat, mana el més a prop del
    # BPM de la barra.
    tots.sort(key=lambda t: (round(t[0], 3),
                             abs(math.log(t[2] / float(preferit))), t[2]))
    out = []
    for _cost, r, bpm, bar, ks in tots:
        if r > max(float(tol), 0.25):
            continue
        if any(abs(math.log(bpm / c["bpm"])) < 0.08 for c in out):
            continue          # massa a prop d'un candidat ja triat
        out.append({
            "bpm": round(bpm, 3), "residu": r, "bar": bar,
            "compassos": ks,
            "intervals": [(round(g, 6), k,
                           k * num * (4.0 / den) * 60.0 / g)
                          for g, k in zip(gaps, ks)],
        })
        if len(out) >= int(max_candidats):
            break
    if not out:      # cap BPM raonable: el de cost mínim (informatiu)
        _cost, r, bpm, bar, ks = tots[0]
        out = [{"bpm": round(bpm, 3), "residu": r, "bar": bar,
                "compassos": ks,
                "intervals": [(round(g, 6), k,
                               k * num * (4.0 / den) * 60.0 / g)
                              for g, k in zip(gaps, ks)]}]
    return out[:int(max_candidats)]
