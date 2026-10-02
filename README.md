# PROJECTE AUTO CHORDS

> Aplicació desktop per analitzar una WAV, navegar-ne acords i estructura, corregir-la i exportar clips preparats per a DAW.

## Estat actual (2026-10-02)

La base del producte ja funciona com a aplicació única i coherent:

- la app principal carrega una WAV i processa sense terminal
- el visor està integrat en la mateixa finestra principal
- es generen acords, estructura i carpetes de sortida compartides
- el flux és clar: `Processa` i `Finalitza i publica`
- la llista d’acords i la llista d’estructura són editables i regeneren els WAVs
- es pot llançar directament des de la carpeta del projecte amb doble clic

La funcionalitat principal ja està validada i els tests de regressió passaven al darrer control del pipeline i l’UI.

## Què fa l’app

- analitza una WAV amb Chordino + Segmentino
- genera CSVs d’acords i estructura ABC
- mostra ona, cursor, temps i navegació per la cançó
- permet corregir acords i editar seccions
- regenera els clips produïts en funció dels canvis manuals
- exporta el paquet final per a DAW en una sola acció final

## Flux actual d’ús

1. Obre la WAV
2. Fes `Processa`
3. Revisa i edita acords / seccions al visor
4. Fes `Finalitza i publica`

## Llançament

Des de la carpeta del projecte:

```bash
python -m app.main
```

O directament amb:

```bash
./AUTO_CHORDS.sh
```

També hi ha llançador de desktop:

```bash
./AUTO_CHORDS.desktop
```

## Estructura clau

- `app/main.py` — finestra principal i flux d’usuari
- `app/visor.py` — visor integrat, llistes, navegació, edició manual
- `app/pipeline.py` — exportació, regeneració, normalització d’acords
- `app/theme.py` — tema centralitzat gris
- `AUTO_CHORDS.sh` — llançador directe

## Requisits

- Python 3.10+
- PyQt5
- pyqtgraph
- numpy < 2
- dependències locals de Chordino / Segmentino / Vamp al sistema

## Llicència

GPLv3 — vegeu `LICENSE`.
Copyright (c) 2026 Pëp <pepelocotango@gmail.com>.
