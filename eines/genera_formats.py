#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera el bloc «Formats d'àudio acceptats» de `README.md`.

- **Font única:** `app/ffmpeg.EXTENSIONS` (les extensions que l'app accepta
  obrir). El recompte i la llista no es poden desfasar del codi.
- **Bloc generat:** entre els marcadors `<!-- GENERAT: formats ... -->` i
  `<!-- /GENERAT: formats -->` de `README.md`. No editar-lo a mà.
- **Agrupament:** `AIFF/AIF/AIFC` i `OGG/OGA` es mostren com un sol nom; la
  resta, en majúscules (`Opus` es conserva així).
- Si el codi afig una extensió sense agrupament, apareix automàticament.

Ús:
    python3 eines/genera_formats.py            # escriu el bloc
    python3 eines/genera_formats.py --check    # diu si està al dia
"""
from __future__ import annotations

import os
import sys

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ARREL, "README.md")
INICI = "<!-- GENERAT: formats — no editar a mà -->"
FI = "<!-- /GENERAT: formats -->"

GRUPS = {
    "aif": ("AIFF/AIF/AIFC", {"aif", "aiff", "aifc"}),
    "ogg": ("OGG/OGA", {"ogg", "oga"}),
}

NOMS_ESPECIALS = {"opus": "Opus"}

AMPLADA = 88


def _extensions() -> list:
    sys.path.insert(0, ARREL)
    try:
        from app import ffmpeg
        return list(ffmpeg.extensions())
    finally:
        sys.path.pop(0)


def _noms(exts) -> list:
    noms = []
    ja = set()
    for ext in exts:
        ext = str(ext).lower()
        if ext in ja:
            continue
        grup = GRUPS.get(ext)
        if grup:
            etiqueta, membres = grup
            noms.append(etiqueta)
            ja.update(membres)
        else:
            noms.append(NOMS_ESPECIALS.get(ext, ext.upper()))
            ja.add(ext)
    return noms


def _linies_formatades(noms) -> list:
    """Ajusta la llista a AMPLADA amb el separador « ·» al final de línia."""
    linies = []
    actual = ""
    for nom in noms:
        tros = f"`{nom}`"
        candidat = f"{actual} · {tros}" if actual else tros
        if actual and len(candidat) > AMPLADA:
            linies.append(actual + " ·")
            actual = tros
        else:
            actual = candidat
    if actual:
        linies.append(actual)
    return linies


def construeix() -> str:
    exts = _extensions()
    text = [
        INICI,
        f"L'app treballa amb **WAV PCM 16 bits** internament, però `Obre…` "
        f"accepta **{len(exts)} formats**",
        "i els converteix automàticament amb **ffmpeg** (vegeu "
        "`app/ffmpeg.py`):",
        "",
        *_linies_formatades(_noms(exts)),
        FI,
    ]
    return "\n".join(text)


def _bloc_actual(contingut: str):
    a = contingut.find(INICI)
    b = contingut.find(FI)
    if a < 0 or b < 0 or b < a:
        return None
    return contingut[a:b + len(FI)]


def main(argv) -> int:
    text = construeix()
    if len(argv) > 1 and argv[1] == "-":
        print(text)
        return 0
    if not os.path.isfile(DOC):
        print(f"falta: {os.path.relpath(DOC, ARREL)}")
        return 1
    with open(DOC, encoding="utf-8") as f:
        contingut = f.read()
    actual = _bloc_actual(contingut)
    if actual is None:
        print(f"falten els marcadors a {os.path.relpath(DOC, ARREL)}")
        return 1
    if len(argv) > 1 and argv[1] == "--check":
        if actual != text:
            print("desactualitzat: README.md (corre: python3 eines/genera_formats.py)")
            return 1
        print("OK: README.md (formats)")
        return 0
    nou = contingut.replace(actual, text)
    with open(DOC, "w", encoding="utf-8") as f:
        f.write(nou)
    print("escrit: README.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
