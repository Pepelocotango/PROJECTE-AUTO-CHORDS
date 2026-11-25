#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Marcadors humans de la cançó (inici de compàs, en viu).

Un **marcador** és només un instant marcat per l'operador mentre escolta
(tecla `M` o botó «Afegeix marcador»). No talla cap carril ni forma part del
mapa de tempo.

Els marcadors són **anotacions independents**: no viatgen amb les fronteres
de tempo ni amb les seccions, i no s'esborren quan una frontera desapareix.
No participen en cap recalcul de tempo: només són referències visuals.

Este mòdul és **pur** (sense Qt ni fitxers): llista de temps ordenada, amb
alta, baixa i consulta. La persistència i el model viu són a `pipeline` i
`Visor`.
"""

#: Dos marcadors més a prop que això són el mateix colp (rebot de la tecla).
SEPARACIO_MIN = 0.05

#: Tipus admesos al projecte i al CSV de marcadors.
TIPUS_VALIDS = (
    "marcador", "compas", "seccio", "inici", "final",
    "inici_analisi", "final_analisi",
)
TIPUS_ANALISI = ("inici_analisi", "final_analisi")


def normalitza_marcadors(marques, durada):
    """Llista ordenada, sense duplicats i dins de `[0, durada]`."""
    durada = float(durada or 0.0)
    out = []
    for m in marques or ():
        try:
            t = float(m)
        except (TypeError, ValueError):
            continue
        if 0.0 <= t <= durada:
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
    if not (0.0 <= t <= durada):
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


def rang_analisi(marques, tipus, durada=0.0):
    """Retorna `(inici_analisi, final_analisi)` o `None`.

    Els marcadors d'anàlisi són anotacions independents; esta funció només
    en calcula el rang. Si falten, estan duplicats o no són coherents, retorna
    `None` i el cridador ha de demanar a l'usuari que els defense.
    """
    if not isinstance(tipus, dict):
        return None
    inici = []
    final = []
    for t, tp in tipus.items():
        if tp not in TIPUS_ANALISI:
            continue
        try:
            v = float(t)
        except (TypeError, ValueError):
            continue
        if tp == "inici_analisi":
            inici.append(v)
        else:
            final.append(v)
    if len(inici) != 1 or len(final) != 1:
        return None
    a, b = float(inici[0]), float(final[0])
    if b <= a:
        return None
    if a < 0.0:
        return None
    if durada:
        b = min(b, float(durada))
    return (a, b)


def es_tipus_valid(tipus):
    """Cert si el tipus de marcador és dels que entén el projecte."""
    return str(tipus or "").strip() in TIPUS_VALIDS
