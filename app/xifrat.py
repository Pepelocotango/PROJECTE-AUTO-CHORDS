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


# Taula de PRESENTACIÓ del panell «Tipus d'acord» (i del doc): ORDENADA de
# menys a més complex (bàsic → intermedi → avançat → extres). Cada entrada:
#   (etiqueta de la llista, qualitat canònica, noms alternatius, graus)
# Els GRAUS són els de la referència de l'operador («acords i tensions»),
# sense els parèntesis dels opcionals i separats per comes.
TAULA_TIPUS = (
    # ── Bàsic ─────────────────────────────────────────────────────────────
    ("maj", "", "M·Maj·Δ", "1,3,5"),
    ("m", "-", "mi·min·-", "1,b3,5"),
    ("dim", "dim", "o·°", "1,b3,b5"),
    ("7", "7", "", "1,3,5,b7"),
    ("m7", "-7", "mi7·min7·-7", "1,b3,5,b7"),
    ("m7b5", "-7b5", "ø·ø7·-7b5", "1,b3,b5,b7"),
    ("maj7", "Maj7", "M7·Ma7·Δ7", "1,3,5,7"),
    # ── Intermedi ─────────────────────────────────────────────────────────
    ("majb5", "Majb5", "", "1,3,b5"),
    ("5", "5", "", "1,5"),
    ("sus2", "sus2", "", "1,2,5"),
    ("sus4", "sus4", "sus", "1,4,5"),
    ("+", "aug", "aug", "1,3,#5"),
    ("6", "6", "", "1,3,5,6"),
    ("add9", "add9", "", "1,3,5,9"),
    ("m6", "-6", "mi6·min6·-6", "1,b3,5,6"),
    ("madd9", "-add9", "m(add9)", "1,b3,5,9"),
    ("dim7", "dim7", "o7·°7", "1,b3,b5,bb7"),
    ("7sus4", "7sus4", "7sus", "1,4,5,b7"),
    ("7b5", "7b5", "", "1,3,b5,b7"),
    ("7#5", "7#5", "+7·aug7", "1,3,#5,b7"),
    ("m(maj7)", "-Maj7", "mMaj7·mM7·mΔ7", "1,b3,5,7"),
    ("6/9", "6add9", "69", "1,3,5,6,9"),
    ("m6/9", "-6add9", "m69", "1,b3,5,6,9"),
    ("7b9", "7b9", "", "1,3,5,b7,b9"),
    ("7#9", "7#9", "", "1,3,5,b7,#9"),
    ("m7b9", "-7b9", "", "1,b3,5,b7,b9"),
    ("9", "9", "", "1,3,5,b7,9"),
    ("9b5", "9b5", "", "1,3,b5,b7,9"),
    ("9#5", "9#5", "", "1,3,#5,b7,9"),
    ("m9", "-9", "mi9·min9·-9", "1,b3,5,b7,9"),
    ("maj9", "Maj9", "M9·Ma9·Δ9", "1,3,5,7,9"),
    ("11", "11", "", "1,3,5,b7,9,11"),
    ("m11", "-11", "min11", "1,b3,5,b7,9,11"),
    ("maj11", "Maj11", "", "1,3,5,7,9,11"),
    ("13", "13", "", "1,3,5,b7,9,13"),
    ("m13", "-13", "", "1,b3,5,b7,9,13"),
    ("maj13", "Maj13", "M13", "1,3,5,7,9,13"),
    # ── Avançat ───────────────────────────────────────────────────────────
    ("maj7b5", "Maj7b5", "", "1,3,b5,7"),
    ("maj7#5", "Maj7#5", "", "1,3,#5,7"),
    ("7b5b9", "7b5b9", "", "1,3,b5,b7,b9"),
    ("7#5b9", "7#5b9", "", "1,3,#5,b7,b9"),
    ("7#5#9", "7#5#9", "", "1,3,#5,b7,#9"),
    ("7add11", "7add11", "", "1,3,5,b7,11"),
    ("7#11", "7#11", "", "1,3,5,b7,#11"),
    ("m7b5b9", "-7b5b9", "", "1,b3,b5,b7,b9"),
    ("m7add11", "-7add11", "", "1,b3,5,b7,11"),
    ("maj7#11", "Maj7#11", "", "1,3,5,7,#11"),
    ("m9b5", "-9b5", "", "1,b3,b5,b7,9"),
    ("m(maj9)", "-Maj9", "mMaj9·mM9", "1,b3,5,7,9"),
    ("maj9#5", "Maj9#5", "", "1,3,#5,7,9"),
    ("9#11", "9#11", "", "1,3,5,b7,9,#11"),
    ("maj9#11", "Maj9#11", "", "1,3,5,7,9,#11"),
    ("11b9", "11b9", "", "1,3,5,b7,b9,11"),
    ("13b5b9", "13b5b9", "", "1,3,b5,b7,b9,13"),
    ("13b9", "13b9", "", "1,3,5,b7,b9,13"),
    ("13#9", "13#9", "", "1,3,5,b7,#9,13"),
    ("13#11", "13#11", "", "1,3,5,b7,9,#11,13"),
    # ── Extres (fora de la referència «acords i tensions») ────────────────
    ("no3", "no3", "", "1,5"),
    ("no5", "no5", "", "1,3"),
    ("add6", "add6", "", "1,3,5,6"),
    ("add11", "add11", "", "1,3,5,11"),
    ("7alt", "7alt", "alt", "1,3,b7,+alt"),
)


def composa(arrel, qualitat, baix="") -> str:
    """Xifrat canònic a partir d'arrel + qualitat + baix (panell «Tipus d'acord»).

    Qualsevol dels tres pot anar buit: sense arrel queda **només la qualitat**
    (l'usuari hi afegeix l'arrel després) i sense baix, un acord normal.
    """
    a = " ".join(str(arrel or "").split())
    b = " ".join(str(baix or "").split())
    text = (a + str(qualitat or "")) if a else str(qualitat or "")
    if b:
        text += "/" + b
    return normalitza_xifrat(text)


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
        # Pot ser NOMÉS una qualitat (`Maj7`, `m7b5`…): el panell de tipus ho
        # permet i l'usuari hi afegeix l'arrel després. Si no canvia res, es
        # retorna tal qual (l'app no inventa).
        q2 = normalitza_qualitat(base)
        if q2 and q2 != base.strip():
            if baix:
                pb2 = parteix_arrel(baix)
                if pb2 is not None:
                    q2 += "/" + pb2[0]
            return q2
        return s
    arrel, qual = pa
    out = arrel + normalitza_qualitat(qual)
    if baix:
        pb = parteix_arrel(baix)
        if pb is not None:
            out += "/" + pb[0]
    return out
