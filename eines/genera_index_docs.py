#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera l'índex de `docs/README.md` a partir del disc i dels JSON.

- **Bloc generat:** entre els marcadors `<!-- GENERAT: index_docs ... -->` i
  `<!-- /GENERAT: index_docs -->` de `docs/README.md`. No editar-lo a mà.
- **Què automatitza:** la taula del contracte i la de `docs/recerca/`.
  Els recomptes del mapa de funcionalitats (`N fitxes`, `M fulls`) surten de
  `eines/funcionalitats_dades.json`, i qualsevol `.md` nou de `docs/` o de
  `docs/recerca/` que no tinga descripció al diccionari apareix igualment
  (amb «—»), de manera que l'índex no pot oblidar un document.
- **Descripcions:** diccionari `DESCRIPCIONS` i ordre de `ORDRE`; per a la
  resta, ordre alfabètic.

Ús:
    python3 eines/genera_index_docs.py            # escriu el bloc
    python3 eines/genera_index_docs.py --check    # diu si està al dia
"""
from __future__ import annotations

import json
import os
import sys

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ARREL, "docs")
DOC = os.path.join(DOCS, "README.md")
DADES = os.path.join(ARREL, "eines", "funcionalitats_dades.json")
INICI = "<!-- GENERAT: index_docs — no editar a mà -->"
FI = "<!-- /GENERAT: index_docs -->"

ORDRE = [
    "REGLES_DE_LA_APP.md",
    "ESQUEMA_UI.md",
    "EDICIO_OPERACIONS.md",
    "TIPUS_XIFRAT_ACORDS.md",
    "COMPONENTS_I_VERSIONS.md",
    "FUNCIONALITATS_AUTO_CHORDS.ods",
]

DESCRIPCIONS = {
    "REGLES_DE_LA_APP.md": "🔴 **Regles d'or (invariants)**: 1–12 i el §13 "
                           "(temps, compàs i graella). Si el codi no les "
                           "compleix, és un bug del codi.",
    "ESQUEMA_UI.md": "Esquema de la interfície. Les vistes `.html`/`.svg` es "
                     "**generen** (`eines/genera_esquema_ui.py`) — no "
                     "editar-les a mà.",
    "EDICIO_OPERACIONS.md": "Taula única d'operacions d'edició: GUI × paritat "
                            "acords/estructura × estat.",
    "TIPUS_XIFRAT_ACORDS.md": "Catàleg de tipus d'acord, variants, graus i "
                              "`<kind>` MusicXML.",
    "COMPONENTS_I_VERSIONS.md": "Inventari de components i versions. El "
                                "**genera** `eines/genera_inventari.py` — no "
                                "editar-lo a mà.",
    "FUNCIONALITATS_AUTO_CHORDS.ods": "Mapa complet d'ús: totes les accions "
                                      "d'usuari, què fan, des d'on s'executen "
                                      "(menú, botó, drecera, contextual, "
                                      "ratolí, diàleg o automàtic), "
                                      "disponibilitat i límits.",
}

ORDRE_RECERCA = [
    "guia_tecnica_downbeat_onsets_beats.md",
    "NOTACIO_XIFRAT.md",
    "GRAELLA_PPQ_TEMPS.md",
    "AUTODETECCIO_OPCIONS.md",
    "PLA_MAPA_TEMPS.md",
]

DESCRIPCIONS_RECERCA = {
    "guia_tecnica_downbeat_onsets_beats.md":
        "Teoria d'onsets, beats i downbeats; criteris per a la detecció.",
    "NOTACIO_XIFRAT.md": "Forma canònica del xifrat i les seues variants.",
    "GRAELLA_PPQ_TEMPS.md": "Proposta de PPQ/ticks i swing (no implementada).",
    "AUTODETECCIO_OPCIONS.md": "Mesuraments reals dels motors d'autodetecció.",
    "PLA_MAPA_TEMPS.md": "Pla de simplificació del mapa de temps: referència "
                         "manual, recalcul guiat i model permissiu.",
}

# Noms de la columna «Doc» que no són el nom del fitxer.
NOMS = {
    "REGLES_DE_LA_APP.md": "**`REGLES_DE_LA_APP.md`**",
    "ESQUEMA_UI.md": "`ESQUEMA_UI.md` (`.html` · `.svg`)",
    "FUNCIONALITATS_AUTO_CHORDS.ods":
        "**`FUNCIONALITATS_AUTO_CHORDS.ods`**",
}


def _xifres():
    with open(DADES, encoding="utf-8") as f:
        dades = json.load(f)
    fitxes = len(dades.get("funcionalitats", []))
    fulls = len(dades) + 2  # + les taules derivades «Resum» i «Mapa mental»
    return fitxes, fulls


def _desc_funcionalitats() -> str:
    fitxes, fulls = _xifres()
    return (DESCRIPCIONS["FUNCIONALITATS_AUTO_CHORDS.ods"] +
            f" {fulls} fulls: resum, llegenda, mapa mental, {fitxes} fitxes, "
            "menús, botons, dreceres, diàlegs i flux de treball. El "
            "**genera** `eines/genera_funcionalitats.py` des de "
            "`eines/funcionalitats_dades.json` — no editar l'ODS a mà.")


def _filera(nom, desc) -> str:
    etiqueta = NOMS.get(nom, f"`{nom}`")
    return f"| {etiqueta} | {desc} |"


def _taula(carpeta, ordre, descripcions) -> list:
    presents = sorted(n for n in os.listdir(carpeta) if n.endswith(".md"))
    ordre_ok = [n for n in ordre if n in presents]
    resta = sorted(set(presents) - set(ordre_ok), key=str.casefold)
    linies = ["| Doc | Què explica |", "|---|---|"]
    for nom in ordre_ok + resta:
        linies.append(f"| `recerca/{nom}` | {descripcions.get(nom, '—')} |")
    return linies


def construeix() -> str:
    linies = [
        INICI,
        "## Contracte i documents vius",
        "",
        "| Doc | Què explica |",
        "|---|---|",
    ]
    presents = {n for n in os.listdir(DOCS) if os.path.isfile(
        os.path.join(DOCS, n))}
    resta = sorted((n for n in presents
                    if n.endswith(".md") and n != "README.md"
                    and n not in DESCRIPCIONS),
                   key=str.casefold)
    for nom in ORDRE:
        if nom not in presents:
            continue
        desc = (_desc_funcionalitats() if nom.endswith(".ods")
                else DESCRIPCIONS[nom])
        linies.append(_filera(nom, desc))
    for nom in resta:
        linies.append(_filera(nom, DESCRIPCIONS.get(nom, "—")))

    linies += [
        "",
        "## Recerca (`recerca/`)",
        "",
        "Documents de referència i propostes que **no** descriuen l'estat "
        "actual del codi:",
        "",
    ]
    linies += _taula(os.path.join(DOCS, "recerca"), ORDRE_RECERCA,
                     DESCRIPCIONS_RECERCA)
    linies.append(FI)
    return "\n".join(linies)


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
            print("desactualitzat: docs/README.md (corre: "
                  "python3 eines/genera_index_docs.py)")
            return 1
        print("OK: docs/README.md")
        return 0
    nou = contingut.replace(actual, text)
    with open(DOC, "w", encoding="utf-8") as f:
        f.write(nou)
    print("escrit: docs/README.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
