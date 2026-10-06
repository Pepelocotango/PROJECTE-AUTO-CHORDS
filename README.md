# PROJECTE AUTO CHORDS

> Aplicació desktop per analitzar una WAV, navegar-ne acords i estructura, corregir-la i exportar clips preparats per a DAW.

## Estat actual (2026-10-06 · v0.1.8)

La base del producte funciona com a aplicació única i coherent:

- la app principal carrega una WAV i processa sense terminal
- el visor està integrat en la mateixa finestra principal
- es generen acords, estructura i carpetes de sortida compartides
- el flux és clar: `Processa` i `Finalitza i publica`
- **barra de menús** (Fitxer · Edita · Selecciona · Visualitza · Analitza · Ajuda)
- **desfer/refer** d’edició (Ctrl+Z / Ctrl+Y), mai toca els WAVs generats
- **temps** en dos modes: **BPM · compàs** o **Lliure (hh:mm:ss)**, amb
  **detecció automàtica del BPM** (plugin Vamp d’aubio)
- els compassos de qualsevol mètrica (3/4, 6/8, 5/4…), no només 4/4
- la llista d’acords i la d’estructura són editables
- es pot llançar directament des de la carpeta del projecte amb doble clic

La funcionalitat principal està validada: **45/45 tests OK** (`python -m unittest tests.test_pipeline_export`).

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

## Filosofia i lògica del flux

La idea central del projecte no és tenir “múltiples eines ocultes”, sinó una sola aplicació amb un flux clar i un model de dades coherent:


### Semàntica del flux

- els intervals tenen inici i fi; el fi no s’edita de manera independent perquè es deriva del següent inici o de la durada total
- “N” és un valor de chord vàlid, no una excepció especial
- el sistema accepta acords i seccions ordenats de manera estricta: no solapaments, no inversions de temps, no duplicats de start
- la normalització ordena els elements abans de salvar-los i la validació rebutja canvis lògicament invàlids

### Per què aquest model

Perquè permet que el producte sigui coherent i predictible:

- l’usuari sempre editant la mateixa font de dades
- el visor reflecteix el que realment es guardarà
- els exports són reproduïbles i no depenen d’una “modalitat temporal” distinta
- el codi no es descontrola amb dades inconsistents ni amb dos models de temps barrejats

Aquest és el criteri que ha acabat definint la base de l’app: una app única, un flux únic i una representació temporal única en el backend.

## Configuració

- La carpeta temporal per defecte és `temp/` a l’arrel del projecte.
- Es pot sobreescriure amb la variable d’entorn **`AUTO_CHORDS_TEMP`**
  (camí absolut o relatiu), útil per a fluxos de treball personalitzats:

```bash
export AUTO_CHORDS_TEMP=/home/user/tmp_auto_chords
python3 app/visor.py tema.wav
```

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

## Agraïments i reconeixement a projectes de tercers

Aquest projecte depèn de treballs previs i eines desenvolupades per altres persones i equips. Volem reconèixer-ho explícitament i agrair-ho sincerament:

- Python i la comunitat Python
- PyQt5 / Qt5 i PyQtGraph per la base de l’interfície i la visualització gràfica
- NumPy pel processament numèric i la manipulació de dades d’àudio
- Chordino i el sistema Vamp / Sonic Annotator per la detecció automàtica d’acords i estructures
- Segmentino i la cadena de processament d’estructura/locators
- les llibreries d’àudio del sistema i els drivers del entorn Linux que permeten la reproducció i la manipulació d’ona
- les biblioteques i recursos de la comunitat open source que han servit de referência per a la normalització, l’edició i la integració de la app

Sense aquest ecosistema, aquest projecte no seria possible. Els agraïments i el reconeixement formal són part de la forma de treball i del respecte que es mereixen les eines i els desenvolupadors que ens han donat base i inspiració.

## Llicència

GPLv3 — vegeu `LICENSE`.
Copyright (c) 2026 Pëp <pepelocotango@gmail.com>.
