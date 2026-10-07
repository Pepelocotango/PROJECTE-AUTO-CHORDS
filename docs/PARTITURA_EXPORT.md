# Exportació de partitura (xifrat)

> Mòdul `app/partitura.py` — converteix els resultats d'Auto Chords en una
> **partitura de xifrats** (MusicXML + PDF + `.mscz`).
> Alta: 2026-10-07 (OC-2). No substitueix res: és una sortida addicional.

## Què fa

Aprofita les dades que ja genera l'exportació normal:

    <sortida>/acords_locators.txt   (posició compàs.temps.setzena · acord · durada en temps)
    <sortida>/estructura_ABC.csv    (seccions amb posició en compàs)

i produeix:

    <sortida>/partitura/<tema>.musicxml   estàndard, editable a qualsevol MuseScore
    <sortida>/partitura/<tema>.pdf        render amb MuseScore (si hi és)
    <sortida>/partitura/<tema>.mscz       projecte natiu MuseScore (si hi és)

És un **lead sheet**: xifrats sobre notes *slash*, amb tempo, compàs, armadura
i **marques de secció** (cada secció comença línia).

## Com s'usa

- **CLI**:

      python3 eines/exporta_partitura.py "<carpeta>_ACORDS" \
          [--tema NOM] [--key auto|G|"E minor"] [--wav RUTA] \
          [--musescore RUTA] [--no-pdf] [--no-mscz] [--timeout SG] \
          [--compassos-per-linia N] [--beat-type N]

- **API**:

      from app import partitura
      partitura.exporta_partitura(sortida, log=print, bpm=103, bpb=4,
                                  offset=0.0, key_fifths=0)

- **App** (menú **Fitxer**):
  - **«Inclou la partitura (xifrat)»** (commutable, per defecte **NO**): en fer
    «Exporta», genera també el lead sheet.
  - **«Exporta la partitura…»**: genera només la partitura de la sortida actual.
  - **«Tonalitat automàtica (qm-keydetector)»** (per defecte **NO**): calcula
    l'armadura amb `detecta_fifths` (triga uns segons).
  - La GUI passa `new_system_each=4` (4 compassos per línia).

## Requisits i maquinari

- **MuseScore 4.6.x funciona**; **4.7+ NO** en CPU sense SSE4.2 — el Qt6 de
  MuseScore 4.7 exigeix **SSE4.2 + POPCNT** i el Q9400 no els té.
- El binari es detecta amb la variable **`AUTO_CHORDS_MUSESCORE`** o
  automàticament (`PATH` i AppImages de `~/Applications`, preferint 4.6.x).
- **Sense MuseScore**: s'escriu només el MusicXML i s'avisa — **no trenca**
  l'exportació normal.

## Límits

- Només té sentit en mode **BPM · compàs** (cal `acords_locators.txt`); en mode
  lliure no hi ha graella de compassos.
- És un full de **xifrat**: **no hi ha melodia** (el pipeline no extreu
  alçades), només acords i estructura. La melodia s'afegiria a mà al MuseScore.

## Notes tècniques

- Conversió `compàs.temps.setzena` -> beats: `(b-1)*bpb + (t-1) + (sub-1)/4`
  (el 3r camp és la subdivisió dins del temps: 1 = temps, 3 = «i» del temps).
- Mapeig de qualitats -> `<kind>` de MusicXML (`major`, `minor`, `dominant`,
  `major-seventh`, `diminished`…); les desconegudes -> `<kind text="...">other`.
- Acords amb baix (`G/D`, `A7/C#`) -> `<bass>`.
- `--key auto` usa el `qm-keydetector` del projecte (via `app.pipeline`).
- `new_system_each=N` (CLI `--compassos-per-linia`): salt de sistema cada N compassos
  (a més de l'inici de cada secció).
- `beat_type=N` (CLI `--beat-type`): denominador del compàs (per defecte 4; 8 per 6/8).
- Tests: `tests/test_partitura.py` (no necessiten MuseScore).

## Coordinació

- Fitxers **nous** d'OC-2: `app/partitura.py`, `eines/exporta_partitura.py`,
  `tests/test_partitura.py`, aquest document. **Cap fitxer existent tocat.**
- El ganxo a `app/main.py` (accions «Inclou la partitura», «Exporta la
  partitura…» i «Tonalitat automàtica») el va fer **OC-1** (propietari de
  `main.py`), a partir de la spec OC-2/182.
