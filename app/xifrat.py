#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Notació del xifrat d'acords — font ÚNICA (parseig + forma canònica).

L'app desa **sempre** els acords en una **forma canònica** (decisió de
l'operador, 2026-10-15 — «opció 3»): si l'usuari escriu una variant, l'app
l'enten i la deixa bé, i així el model, els noms de fitxer de l'export i la
partitura (MusicXML → MuseScore) parlen tots la mateixa llengua.

Gramàtica::

    xifrat  := ARREL ALTERACIÓ?  QUALITAT  ( "/" BAIX )?


Forma canònica de la qualitat:
    - **menor** ``-``   (escrivis ``m``/``mi``/``min``/``-``)
    - **major**: sense marca  (``M``/``Ma``/``maj``/``Δ``/``^``)
    - ``Maj7`` major 7 · ``-7`` menor 7 · ``-Maj7`` menor-maj7
    - ``dim`` / ``dim7`` · ``-7b5`` (semidisminuït, ``ø``) · ``aug``
    - ``sus4`` / ``sus2`` · ``6`` / ``-6`` · ``9``/``11``/``13``…

Exemples::

    "Am"        → "A-"          "Amin7" → "A-7"
    "Amaj7"     → "AMaj7"       "AM7"   → "AMaj7"
    "CΔ7"       → "CMaj7"       "F#o7"  → "F#dim7"
    "Bø"        → "B-7b5"       "C+"    → "Caug"
    "Am/G"      → "A-/G"        "C6/9"  → "C6/9"   (no és un baix!)
    "N"         → "N"

El mòdul NO depèn de res del projecte (es pot fer servir des de `pipeline` i
`partitura` sense cicles).
"""
from __future__ import annotations

import re

# --- parseig bàsic ---------------------------------------------------------
_RE_ARREL = re.compile(r"^([A-Ga-g])([#b♯♭]?)")
_RE_NOTA = re.compile(r"^[A-Ga-g][#b♯♭]?$")

# «Sense acord»: capçalera del CSV i equivalents.
CAPS_ACORD = {"", "N", "NC", "N.C.", "N.C", "N.C", "NO CHORD"}

# Accidental → ASCII (♯/♭ són unicode «guai» però l'app fa servir #/b).
_ALTERACIO = {"♯": "#", "♭": "b"}


def es_cap_acord(nom) -> bool:
    """Cert si el text és un «sense acord» (N, NC, N.C., buit…)."""
    return str(nom or "").strip().upper() in CAPS_ACORD


def parteix_baix(xifrat):
    """(base, baix): el darrer ``/`` compta NOMÉS si el que segueix és una NOTA.

    Així ``A7/G`` dona baix ``G``, però ``C6/9`` (que també porta barra) es
    queda sencer.
    """
    s = str(xifrat or "").strip()
    for i in range(len(s) - 1, -1, -1):
        if s[i] == "/":
            cua = s[i + 1:]
            if _RE_NOTA.match(cua):
                return s[:i], cua
    return s, ""


def parteix_arrel(base):
    """(arrel, qualitat) de la part sense baix; ``None`` si no comença per nota."""
    m = _RE_ARREL.match(str(base or "").strip())
    if not m:
        return None
    arrel = m.group(1).upper() + _ALTERACIO.get(m.group(2), m.group(2))
    return arrel, str(base).strip()[m.end():]


# --- forma canònica de la qualitat ----------------------------------------
# Prefixos «de paraula» (es comparen en minúscules) — el més llarg primer!
_PREFIXOS = (
    ("min", "-"), ("mi", "-"), ("maj", "Maj"), ("ma", "Maj"),
    ("dim", "dim"), ("aug", "aug"),
    ("sus4", "sus4"), ("sus2", "sus2"), ("sus", "sus4"),
)
# Símbols d'un sol caràcter (sensible a majúscules: m ≠ M).
_SIMBOLS = {
    "-": "-", "−": "-",           # guionet i «menys» unicode
    "m": "-", "M": "Maj",
    "Δ": "Maj", "∆": "Maj", "^": "Maj",
    "°": "dim", "o": "dim", "O": "dim",
    "+": "aug", "ø": "-7b5", "Ø": "-7b5",
}


def _ajunta(cap, cua) -> str:
    """Junta la marca de tríada amb la cua (evitant duplicar el «menor»)."""
    if cap == "-" and cua.startswith("-"):
        return cua                    # `-min7` → `-7`, no `--7`
    res = cap + cua
    return "" if res == "Maj" else res    # `Maj` tot sol = tríada major


def normalitza_qualitat(q) -> str:
    """Forma canònica de la qualitat d'un xifrat (o la cua tal qual si no es reconeix)."""
    q = str(q or "").strip()
    if not q:
        return ""
    c0 = q[0]
    if c0 in ("ø", "Ø"):              # semidisminuït: `ø`/`ø7` → `-7b5`
        cua = q[1:].strip()
        if cua.startswith("7"):       # `ø7` = `ø` (la 7a ja hi és dins)
            cua = cua[1:]
        return _ajunta("-7b5", normalitza_qualitat(cua))
    ql = q.lower()
    for pref, can in _PREFIXOS:
        if ql.startswith(pref):
            return _ajunta(can, normalitza_qualitat(q[len(pref):]))
    if c0 in _SIMBOLS:
        return _ajunta(_SIMBOLS[c0], normalitza_qualitat(q[1:]))
    return q


def normalitza_xifrat(nom) -> str:
    """Xifrat en la forma canònica de l'app.

    Només s'hi toca la NOTACIÓ (arrel en majúscula, qualitat canònica, baix amb
    ``/``). Si el text no sembla un acord, es retorna net però sense inventar-hi
    res (així no es trenquen anotacions rares).
    """
    s = " ".join(str(nom or "").split())
    if not s:
        return ""
    if es_cap_acord(s):
        return "N"                    # «sense acord» → la marca de l'app
    base, baix = parteix_baix(s)
    pa = parteix_arrel(base)
    if pa is None:
        return s                      # no comença per nota → es deixa tal qual
    arrel, qual = pa
    out = arrel + normalitza_qualitat(qual)
    if baix:
        pb = parteix_arrel(baix)
        if pb is not None:
            out += "/" + pb[0]
    return out
