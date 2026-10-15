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
# L'alteració pot ser DOBLE (MuseScore: `##`, `bb`, `x` = doble sostingut) i
# també acceptem els símbols unicode ♯/♭. La `x` només compta si NO la segueix
# una lletra (si no, `Cxyz` seria «C doble sostingut» + «yz»).
_RE_ARREL = re.compile(r"^([A-Ga-g])(##|bb|x(?![A-Za-z])|X(?![A-Za-z])|#|b|♯|♭)?")
_RE_NOTA = re.compile(
    r"^[A-Ga-g](##|bb|x(?![A-Za-z])|X(?![A-Za-z])|#|b|♯|♭)?$")

# «Sense acord»: capçalera del CSV i equivalents.
CAPS_ACORD = {"", "N", "NC", "N.C.", "N.C", "N.C", "NO CHORD"}

# Alteració escrita -> forma canònica (`x` = doble sostingut → `##`).
_ALTERACIO = {"♯": "#", "♭": "b", "x": "##", "X": "##"}


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
    grafia = m.group(2) or ""
    arrel = m.group(1).upper() + _ALTERACIO.get(grafia, grafia)
    return arrel, str(base).strip()[m.end():]


# --- forma canònica de la qualitat ----------------------------------------
# Prefixos «de paraula» (es comparen en minúscules) — el més llarg primer!
_PREFIXOS = (
    ("min", "-"), ("mi", "-"), ("maj", "Maj"),
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


# Parentesis: `m(maj7)` és un QUALITATIU (→ `-Maj7`), però `7(#11)` són
# ALTERACIONS. Primer convertim el cas qualitatiu i després traiem els
# parèntesis/comes de la resta (`(#11,#13)` → `#11#13`).
_RE_PAREN_QUAL = re.compile(r"\((maj|Maj|MAJ|M)(\d*)\)")
_SINONIM = {"69": "6add9", "6/9": "6add9"}


def normalitza_qualitat(q) -> str:
    """Forma canònica de la qualitat d'un xifrat (o la cua tal qual si no es reconeix)."""
    q = str(q or "").strip()
    if not q:
        return ""
    # `m(maj7)`/`min(maj9)` → `mmaj7`/`minmaj9` (continuen pel camí normal)
    q = _RE_PAREN_QUAL.sub(lambda m: m.group(1) + m.group(2), q)
    # `7(#11)` / `69(#11,#13)` → `7#11` / `6add9#11#13`
    q = q.replace("(", "").replace(")", "").replace(",", "").replace(" ", "")
    # `69`/`6/9` → `6add9` (també amb alteracions al darrere: `69#11` → `6add9#11`)
    for sin, can in _SINONIM.items():
        if q.startswith(sin):
            q = can + q[len(sin):]
            break
    c0 = q[0]
    if c0 in ("ø", "Ø"):              # semidisminuït: `ø`/`ø7` → `-7b5`
        cua = q[1:].strip()
        if cua.startswith("7"):       # `ø7` = `ø` (la 7a ja hi és dins)
            cua = cua[1:]
        return _ajunta("-7b5", normalitza_qualitat(cua))
    ql = q.lower()
    # `ma` = major NOMÉS si el segueix un número (`ma7`, `ma9`, `Ma7`); en
    # canvi `madd9` (= menor + `add9`) no hi entra.
    if ql.startswith("ma") and (len(q) == 2 or q[2:3].isdigit()):
        return _ajunta("Maj", normalitza_qualitat(q[2:]))
    for pref, can in _PREFIXOS:
        if ql.startswith(pref):
            return _ajunta(can, normalitza_qualitat(q[len(pref):]))
    if c0 in _SIMBOLS:
        return _ajunta(_SIMBOLS[c0], normalitza_qualitat(q[1:]))
    return q


# --- tipus d'acord -> (kind MusicXML, [graus extra]) ------------------------
# Els GRAUS són (valor, alteració, tipus) respecte del `kind` base; deriven de
# la taula de referència de l'operador («acords i tensions»): els graus que la
# taula marca com a OPCIONALS (entre parèntesis) no s'escriuen.
TIPUS = {
    # tríades
    "": ("major", ()),
    "-": ("minor", ()),
    "dim": ("diminished", ()),
    "aug": ("augmented", ()),
    "5": ("power", ()),
    "sus2": ("suspended-second", ()),
    "sus4": ("suspended-fourth", ()),
    "Majb5": ("major", ((5, -1, "alter"),)),
    # séptimes
    "7": ("dominant", ()),
    "-7": ("minor-seventh", ()),
    "-7b5": ("half-diminished", ()),
    "Maj7": ("major-seventh", ()),
    "dim7": ("diminished-seventh", ()),
    "7sus4": ("suspended-fourth", ((7, -1, "add"),)),
    "7b5": ("dominant", ((5, -1, "alter"),)),
    "7#5": ("augmented-seventh", ()),
    "aug7": ("augmented-seventh", ()),
    "-Maj7": ("major-minor", ()),
    "Maj7b5": ("major-seventh", ((5, -1, "alter"),)),
    "Maj7#5": ("major-seventh", ((5, 1, "alter"),)),
    # sisenes i afegits
    "6": ("major-sixth", ()),
    "-6": ("minor-sixth", ()),
    "add9": ("major", ((9, 0, "add"),)),
    "-add9": ("minor", ((9, 0, "add"),)),
    "6add9": ("major-sixth", ((9, 0, "add"),)),
    "-6add9": ("minor-sixth", ((9, 0, "add"),)),
    # novenes
    "9": ("dominant-ninth", ()),
    "-9": ("minor-ninth", ()),
    "Maj9": ("major-ninth", ()),
    "7b9": ("dominant", ((9, -1, "alter"),)),
    "7#9": ("dominant", ((9, 1, "alter"),)),
    "-7b9": ("minor-seventh", ((9, -1, "alter"),)),
    "9b5": ("dominant-ninth", ((5, -1, "alter"),)),
    "9#5": ("dominant-ninth", ((5, 1, "alter"),)),
    "9#11": ("dominant-ninth", ((11, 1, "alter"),)),
    "Maj9#5": ("major-ninth", ((5, 1, "alter"),)),
    "Maj9#11": ("major-ninth", ((11, 1, "alter"),)),
    "-9b5": ("minor-ninth", ((5, -1, "alter"),)),
    "-Maj9": ("major-minor", ((9, 0, "add"),)),
    # onzenes
    "11": ("dominant-11th", ()),
    "-11": ("minor-11th", ()),
    "Maj11": ("major-11th", ()),
    "7#11": ("dominant", ((11, 1, "alter"),)),
    "7add11": ("dominant", ((11, 0, "add"),)),
    "Maj7#11": ("major-seventh", ((11, 1, "alter"),)),
    "-7add11": ("minor-seventh", ((11, 0, "add"),)),
    "11b9": ("dominant-11th", ((9, -1, "alter"),)),
    # tretzenes
    "13": ("dominant-13th", ()),
    "-13": ("minor-13th", ()),
    "Maj13": ("major-13th", ()),
    "13b9": ("dominant-13th", ((9, -1, "alter"),)),
    "13#9": ("dominant-13th", ((9, 1, "alter"),)),
    "13#11": ("dominant-13th", ((11, 1, "alter"),)),
    "13b5b9": ("dominant-13th", ((5, -1, "alter"), (9, -1, "alter"))),
    # alterats combinats
    "7b5b9": ("dominant", ((5, -1, "alter"), (9, -1, "alter"))),
    "7#5b9": ("augmented-seventh", ((9, -1, "alter"),)),
    "7#5#9": ("augmented-seventh", ((9, 1, "alter"),)),
    "-7b5b9": ("half-diminished", ((9, -1, "alter"),)),
}

_RE_GRAU = re.compile(r"(add|no|#|b)?(\d+)")
_VALORS = tuple(range(1, 14))       # graus possibles (1–13)


def graus(text) -> tuple:
    """[(valor, alter, tipus)] de les alteracions/afegits (p. ex. `#9b13`, `no5`).

    Un número SOLT (el `7` de `C7`) no compta: ja el cobreix el `kind` base.
    """
    res = []
    for m in _RE_GRAU.finditer(str(text or "")):
        pre = m.group(1) or ""
        num = int(m.group(2))
        if num not in _VALORS or not pre:
            continue
        if pre == "add":
            res.append((num, 0, "add"))
        elif pre == "no":
            res.append((num, 0, "subtract"))
        else:                          # `#` o `b`
            res.append((num, 1 if pre == "#" else -1, "alter"))
    return tuple(res)


def _nomes_alteracions(q) -> bool:
    """Cert si TOT el text són alteracions amb prefix (`no5`, `add9#11`…)."""
    return (bool(q) and _RE_GRAU.sub("", q) == ""
            and any(m.group(1) for m in _RE_GRAU.finditer(q)))


def kind_i_graus(qual):
    """(kind MusicXML, [graus]) de la qualitat canònica; `(None, [])` si no es reconeix.

    Primer prova la qualitat SENCERA i, si no, el prefix més llarg reconegut +
    les alteracions de la resta (`7#11` → `7` + `#11`; `-7add9` → `-7` + `add9`).
    Si tota la qualitat són alteracions, la base és la **tríada major**
    (`no5`, `#11`, `add9`…).
    """
    q = str(qual or "")
    if q in TIPUS:
        return TIPUS[q]
    for n in range(len(q), 0, -1):
        pref = q[:n]
        if pref in TIPUS:
            kind, gr = TIPUS[pref]
            return kind, tuple(gr) + graus(q[n:])
    if _nomes_alteracions(q):
        return "major", graus(q)
    return None, ()


def resta_qualitat(qual) -> str:
    """El tros de la qualitat que NO s'ha pogut convertir en `kind`/graus.

    Serveix per posar-lo al `text` del `<kind>` i no perdre informació:
    `7alt` → `alt` (cal conservar-lo); `7#11` → `` (ja són `<degree>`).
    """
    q = str(qual or "")
    if q in TIPUS:
        return ""
    for n in range(len(q), 0, -1):
        pref = q[:n]
        if pref in TIPUS:
            cua = q[n:]
            return "" if (not cua or graus(cua)) else cua
    return "" if _nomes_alteracions(q) else q


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
