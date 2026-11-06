#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera la taula de mòduls de `DEVELOPING.md` a partir dels docstrings.

- **Font única:** els docstrings dels `app/*.py` **versionats** (`git ls-files`).
- **Bloc generat:** entre els marcadors `<!-- GENERAT: moduls ... -->` i
  `<!-- /GENERAT: moduls -->` de `DEVELOPING.md`. No editar-lo a mà.
- **Descripcions:** primera línia del docstring; si no n'hi ha, un diccionari
  de reserva per als mòduls que no en tenen.

Ús:
    python3 eines/genera_moduls.py            # escriu la taula
    python3 eines/genera_moduls.py --check    # diu si està al dia
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ARREL, "app")
DOC = os.path.join(ARREL, "DEVELOPING.md")
INICI = "<!-- GENERAT: moduls — no editar a mà -->"
FI = "<!-- /GENERAT: moduls -->"

IGNORATS = {"__init__.py"}
RESERVA = {
    "main.py": "finestra principal, menús, barres, flux d'usuari i projectes",
    "pipeline.py": "façana del backend (re-exporta els símbols públics)",
    "visor.py": "visor DAW: ona, llistes, edició, reproducció i loop",
    "theme.py": "tema centralitzat (colors i estils Qt)",
}


def _primera_línia(text: str) -> str:
    for línia in (text or "").splitlines():
        línia = línia.strip()
        if línia:
            return línia
    return ""


def _descripcio(cami: str) -> str:
    nom = os.path.basename(cami)
    try:
        with open(cami, encoding="utf-8") as f:
            arbre = ast.parse(f.read(), filename=cami)
        text = ast.get_docstring(arbre) or ""
    except (OSError, SyntaxError):
        text = ""
    desc = _primera_línia(text) or RESERVA.get(nom, "—")
    return desc.replace("|", "\\|")


def _noms_versionats():
    try:
        out = subprocess.run(
            ["git", "ls-files", "--", "app"],
            cwd=ARREL, capture_output=True, text=True, check=True).stdout
        noms = [os.path.basename(p) for p in out.splitlines()
                if p.endswith(".py")]
    except (OSError, subprocess.SubprocessError):
        noms = [n for n in os.listdir(APP) if n.endswith(".py")]
    return sorted(set(noms))


def construeix() -> str:
    files = []
    for nom in _noms_versionats():
        if nom in IGNORATS:
            continue
        cami = os.path.join(APP, nom)
        files.append((nom, _descripcio(cami)))
    out = [INICI, "| Mòdul | Responsabilitat |", "|-------|-----------------|"]
    out += [f"| `{nom}` | {desc} |" for nom, desc in files]
    out.append(FI)
    return "\n".join(out)


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
            print("desactualitzat: DEVELOPING.md (corre: python3 eines/genera_moduls.py)")
            return 1
        print("OK: DEVELOPING.md")
        return 0
    nou = contingut.replace(actual, text)
    with open(DOC, "w", encoding="utf-8") as f:
        f.write(nou)
    print("escrit: DEVELOPING.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
