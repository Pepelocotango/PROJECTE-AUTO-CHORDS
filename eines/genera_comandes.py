#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera el bloc «Comandes essencials» de `DEVELOPING.md` des del `Makefile`.

- **Font única:** les línies `@echo "make ..."` de l'objectiu `help` del
  `Makefile`. Si s'afig, renombra o esborra una comanda, el bloc s'actualitza
  amb `make docs` i `make docs-check` ho detecta.
- **Bloc generat:** entre els marcadors `<!-- GENERAT: comandes ... -->` i
  `<!-- /GENERAT: comandes -->` de `DEVELOPING.md`. No editar-lo a mà.

Ús:
    python3 eines/genera_comandes.py            # escriu el bloc
    python3 eines/genera_comandes.py --check    # diu si està al dia
"""
from __future__ import annotations

import os
import re
import sys

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAKEFILE = os.path.join(ARREL, "Makefile")
DOC = os.path.join(ARREL, "DEVELOPING.md")
INICI = "<!-- GENERAT: comandes — no editar a mà -->"
FI = "<!-- /GENERAT: comandes -->"

_RE_ECHO = re.compile(r'^\t@echo "make (\S+)\s+(.+)"\s*$')


def _comandes() -> list:
    with open(MAKEFILE, encoding="utf-8") as f:
        linies = f.read().splitlines()
    comandes = []
    dins = False
    for linia in linies:
        if linia.rstrip() == "help:":
            dins = True
            continue
        if dins and linia and not linia.startswith("\t"):
            break
        if dins:
            m = _RE_ECHO.match(linia)
            if m:
                comandes.append((m.group(1), m.group(2).strip()))
    return comandes


def construeix() -> str:
    comandes = _comandes()
    amplada = max(len(f"make {nom}") for nom, _ in comandes)
    cos = [f"make {nom}".ljust(amplada) + f"  # {desc}"
           for nom, desc in comandes]
    return "\n".join([INICI, "```bash", *cos, "```", FI])


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
            print("desactualitzat: DEVELOPING.md (corre: "
                  "python3 eines/genera_comandes.py)")
            return 1
        print("OK: DEVELOPING.md (comandes)")
        return 0
    nou = contingut.replace(actual, text)
    with open(DOC, "w", encoding="utf-8") as f:
        f.write(nou)
    print("escrit: DEVELOPING.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
