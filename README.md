# PROJECTE AUTO CHORDS

> Aplicació desktop per analitzar un àudio, navegar-ne acords i estructura,
> corregir-la i exportar clips preparats per a DAW.

> **Novetats v0.4.0:** **compàs 1 automàtic** (`🧭`, amb el Queen Mary),
> **motors d'autodetecció triables** (BPM: nostre/qm/aubio/**consens**;
> estructura: **qm-segmenter** per defecte), **plugins `qm-vamp-plugins`
> compilats** (sense AVX), i **coherència del play** (volum/mute en viu, sense
> congelar la GUI). De v0.3.0: tap tempo (`TAP`/`T`), botó **📍**, **×2/÷2**,
> diàleg d'opcions, **import ffmpeg** i franja **Editor**.

## Estat actual (2026-10-07 · v0.4.0)

L’app està **reorganitzada amb el timeline com a centre de la finestra**
(estil Audacity/DAW): l’anàlisi és una **acció** sobre el que es veu, no un
pas d’assistent.

- En obrir una WAV (**Fitxer ▸ Obre WAV…**, `Ctrl+O`) es mostren l’ona i el
  timeline **de seguida**, amb les pistes Acords/Estructura buides.
- **Barra de menús**: Fitxer · Edita · Selecciona · Visualitza · Analitza · Ajuda.
- **Barra de temps** fina: mode **BPM · compàs** / **Lliure (hh:mm:ss)**,
  BPM, compàs, offset, botó **🎯 Detecta** (aubio) i «Inclou estructura».
- **Barra de transport** pròpia: play/stop, −10s/+10s, loop A/B, zoom i mute
  (`Espai` = play/stop).
- **Metrònom** 🥁 (només en mode BPM · compàs), amb **volum propi** (60 %).
- **Analitza** (`F5`): progrés a la **barra d’estat**; el **log** és un tauler
  plegable a baix (**Visualitza ▸ Mostra el log**).
- **Exporta…** (`Ctrl+E`) a Fitxer; desactivat fins que hi ha resultat.
- **Edició al timeline**: desfer/refer (`Ctrl+Z`/`Ctrl+Y`), `Delete`, `Ctrl+D`
  (duplica) i **menú contextual** (botó dret). Mai toca els WAVs generats.
- **Inspector** (**Visualitza ▸ Mostra l’inspector**): llistes d’acords i
  estructura (clic per saltar, doble-clic per editar, menú contextual).
- Compassos de **qualsevol mètrica** (3/4, 6/8, 5/4…), no només 4/4.

La funcionalitat principal està validada: **69/69 tests OK** (`python -m unittest tests.test_pipeline_export`).

## Què fa l’app

- analitza una WAV amb Chordino + Segmentino
- genera CSVs d’acords i estructura ABC
- mostra ona, cursor, temps i navegació per la cançó
- permet corregir acords i editar seccions
- regenera els clips produïts en funció dels canvis manuals
- exporta el paquet final per a DAW en una sola acció final

## Flux actual d’ús

1. Obre l'àudio (`Obre…`) — si no és WAV, es converteix sol amb ffmpeg
2. Ajusta el BPM (🎯 Detecta o TAP) i fes `Analitza` (obre el diàleg d'opcions)
3. Revisa i edita acords / seccions al visor (franja Editor)
4. Fes `Exporta`

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
- `app/timeline.py` — regle, graella, carrils i clips (QGraphicsView)
- `app/pipeline.py` — extracció, exportació, normalització
- `app/tempo.py` — detecció de BPM (numpy, sense AVX)
- `app/metronom.py` — clic del metrònom mesclat al buffer
- `app/vamp_params.py` — paràmetres dels plugins Vamp (descriptors `.n3`)
- `app/dialegs.py` — diàleg d’opcions d’autodetecció
- `app/postproc.py` — neteja posterior dels acords
- `app/ffmpeg.py` — import d’altres formats (conversió a WAV)
- `app/vamp_params.py` — paràmetres dels plugins Vamp (descriptors `.n3`)
- `app/theme.py` — tema centralitzat
- `AUTO_CHORDS.sh` — llançador directe

## Requisits

- Python 3.10+
- PyQt5
- pyqtgraph
- numpy < 2
- dependències locals de **Chordino** (`nnls-chroma`) i **qm-vamp-plugins**
  (Queen Mary), totes dins el projecte — **sense instal·lar res al sistema**
- **ffmpeg/ffprobe** (opcional, per importar formats que no siguin WAV)

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


## Formats d'àudio acceptats

L'app treballa amb **WAV PCM 16 bits**, però `Obre…` accepta també
**mp3, aif/aiff, flac, m4a, ogg, opus, wma…** i els converteix
automàticament amb **ffmpeg** (vegeu `app/ffmpeg.py`).
