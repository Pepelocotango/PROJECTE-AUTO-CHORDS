# Registre de canvis — PROJECTE AUTO CHORDS

Format [Keep a Changelog](https://keepachangelog.com/ca/1.0.0/).
Versions amb tag git (`v0.1-punt-control` … `v0.1.8-checkpoint`).

## [No publicat]

### Pendent de polir (visor)
- Confusió visual entre clip **seleccionat** (vora groga) i **actiu**
  (fons més clar, segons el cursor).
- Usabilitat: multi-selecció, duplicar/eliminar clips, menú contextual,
  afegir clips amb click al buit (Fase D.1 del ROADMAP).

## [0.1.8] — 2026-10-06 (tag `v0.1.8-checkpoint`)

### Afegit
- **Ctrl+D duplica el clip seleccionat** (acord o secció), amb **undo** i
  respectant les invariants. On s'insereix: **just després de l'original,
  repartint la seva durada** (no es desplaça res):
  - **acord** → el duplicat va a mig camí entre l'original i el següent;
  - **secció** → l'original es parteix en dues meitats (ini–mig, mig–fi).
  Si no hi ha espai suficient, no fa res i ho diu al log. 2 tests nous.
- **Tecla Delete/Backspace** esborra el **clip seleccionat** (acord o
  secció) al visor. Passa pel sistema d'**undo** (`_undo_marca`/
  `_undo_commit`) i respecta la contigüitat (en treure una secció, el
  veí ocupa l'espai buit). Els items de QGraphicsView no reben tecles (no
  són focusables), per tant es gestiona al `TimelineView`. 2 tests nous.

### Verificat
- **Clic a un clip → cursor al seu inici** (acords i seccions): JA funcionava
  (es va arreglar en una versió anterior: el lambda del click capturava el
  valor vell d'`ini`/`t`). Afegit un **test de regressió**
  (`test_click_a_un_clip_mou_el_cursor`).

### Documentat
- **README**: «Estat actual» posat al dia (v0.1.8) i el bloc de configuració
  de `AUTO_CHORDS_TEMP` tret de dins de «Filosofia i lògica del flux»
  (trencava la secció «Semàntica del flux») → nova secció «Configuració».
- **DEVELOPING.md**: «Python 3.8+» → **3.10+** (coincideix amb
  `requires-python` del `pyproject.toml`).
- **requirements.txt**: treta la menció a `als2rpp.py` (ja no hi és).

### Netejat
- **Imports sense ús** trets (`pyflakes` no és al venv i instal·lar-lo seria
  una dependència nova → anàlisi amb l'AST de la stdlib): `visor.py`
  (`atexit`, `math`, `QObject`, `QThread`, `pyqtSignal`), `timeline.py`
  (`QObject`, `Tuple`), `main.py` (`QObject`, `QSpinBox`). Variables
  leftovers: `tsrc` i `idx`.
- **`AUTO_CHORDS.desktop`**: tenia un **byte NUL** al final (podia trencar
  alguns parsers) i una **ruta absoluta fixa** (`/home/peplx/...`). Ara usa
  `%k` (la ubicació del mateix `.desktop`) → **funciona des de qualsevol
  carpeta o usuari**. `launcher.sh` fa el seu propi `cd`.

### Canviat
- **Missatges d'error al log**: els handlers `except Exception` que només
  mostraven un `QMessageBox` (o que s'empassaven l'error en silenci) ara
  **també escriuen a `auto_chords.log`** amb el context. 14 punts a
  `app/visor.py` (12 de `QMessageBox` + la lectura de CSV malmès + el
  directori temporal). Els handlers benignes (procés ja mort, senyal ja
  desconnectat, fallback d'API Qt) es deixen silenciosos a propòsit.
  Comportament visible **sense canvis**.

### Arreglat
- **Els tests ja no es pengen en entorns sense pantalla (CI)**: els
  `QMessageBox` de `Visor.exporta()` i `Finestra.exporta()` són **modals** i
  bloquejaven per sempre (ningú no pot clicar «OK» sense pantalla). Als
  tests es neutralitzen. També `QT_QPA_PLATFORM=offscreen` a nivell de
  mòdul i `pipeline.run()` amb `timeout` (un subprocés encallat ja no
  penja). 2 tests nous (`PipelineRunTests`).

## [0.1.7] — 2026-10-05 (tag `v0.1.7-checkpoint`)

### Afegit
- **Plugin Vamp d'aubio** (`vamp-aubio-linux64-local/`): detecció de
  **tempo/BPM** i **pulsacions** (`vamp:vamp-aubio:aubiotempo:beats`),
  més onsets, pitch, notes, silencis i descriptors. Compilat localment
  **sense sudo** (`libaubio-dev` via `apt-get download`), flags
  `-msse -msse2` (sense AVX). Afegit a `VAMP_DIRS`.
  Guia de reproducció i precisió: `docs/AUBIO_TEMPO.md`.
- **Nou flux de temps** (`app/main.py`): en lloc del checkbox «tempo fix»,
  un **selector de 2 estats** — **BPM · compàs** / **Lliure (hh:mm:ss)**.
  En mode BPM hi ha un botó **🎯 Detecta** que crida `pipeline.detecta_bpm()`
  (aubio) i omple el camp (editable). En mode Lliure s'amaguen els camps
  de BPM.
- **Entrada de text manual**: fora les fletxes ▲▼ (`QDoubleSpinBox`/
  `QSpinBox` → `QLineEdit`). Accepta coma decimal (`101,5`).
- **`concatena.py`**: genera `CODI_concatenat.txt` (tot el codi font en un
  sol fitxer, amb índex; exclou `.venv/.git/.deps`, binaris, plugins i el
  C++ de tercers). L'artefacte generat queda a `.gitignore`.

### Canviat
- `pipeline.detecta_bpm(wav, log)`: BPM a partir de la **mediana** dels
  intervals entre pulsacions (aubio).

### Arreglat
- **Compàs de qualsevol mètrica**: `pos_compas` tenia `SB = 8` fix (només
  4/4) i contradeia `acords_a_live.py`. Ara usa `bpb` (`SB = bpb*2`) i
  funciona amb 3/4, 6/8, 5/4… El `bpb` es propaga a `desa_abc_csv`,
  `fer_abc` i tots els camins de crida.
- **Resolució temporal unificada dels CSV**: `acords.csv` guardava 9
  decimals i `estructura_ABC.csv` 2 (7 ordres de magnitud de diferència).
  Ara tots dos a **2 decimals = 10 ms** (constant `TEMPS_DEC`).
  Tests nous a `FormatCsvTests`.

### Netejat
- Fora el material innecessari per l'app actual (a la paperera; tot
  recuperable de git): **`tauri-ui/`** (experiment Tauri aparcat, 8,8 GB
  amb build + node_modules), `AUTO_CHORDS_TAURI.sh`,
  `nnls-chroma-osx-v1.1/` (plugin macOS), `als2rpp.py` (v1 obsoleta),
  `XXAUTO_CHORDS_dev.sh` (duplicat), `exemple_*`, `auto_chords.log`,
  `__pycache__/`.
- **Projecte: 9,3 GB → 508 MB (−95 %).**
- ⚠️ `codi_font_chordino/` es va restaurar: `instal·la_local.sh` el necessita.

## [0.1.6] — 2026-10-05 (tag `v0.1.6-checkpoint`)

### Afegit
- **Barra de menús** (`app/main.py`): Fitxer · Edita · Selecciona ·
  Visualitza · Analitza · Ajuda, amb les accions bàsiques cablejades
  (obre WAV, exporta, desfer/refer, zoom, loop A/B, ajuda).
- Captura d'**excepcions no gestionades** al log (`sys.excepthook`) i els
  logs del visor ara també van a `auto_chords.log`.

### Arreglat
- **CRÍTIC — el visor incrustat quedava sord**: `_carrega_visor` fa
  `_embedded = True` + `close()`, i el `closeEvent` **desconnectava tots
  els senyals del timeline** sense comprovar `_embedded`. Ara només
  desconnecta si el visor és una finestra autònoma. Això arreglava alhora
  l'undo/redo i la propagació de canvis.
- **Undo/Redo**: la captura de l'estat passava pel senyal de canvi i no
  arribava mai. Ara es fa **a l'inici del gest** (`editStarted` al mouse
  press dels clips) — model Audacity (`PushState` explícit). La base
  s'autoactualitza (`_undo_touch_base`); el reanomenament pel diàleg
  (`_edita_acord`/`_edita_seccio`) ara apila operació; i l'accés a la llista
  va protegit (un `.index()` sobre una tupla normalitzada podia **fer
  petar l'app**).
- **Imatges fantasma** en redimensionar: `prepareGeometryChange()` ha
  d'anar **abans** de canviar la geometria (8 llocs: setters de
  `ChordItem`/`SectionItem` i les capes). Afegit `FullViewportUpdate`.
- **Mètodes duplicats** `_elimina_acord_index` / `_elimina_seccio_index`
  eliminats (la 2a definició guanyava).

### Nota
- Undo/Redo treballa **només** sobre el model (les dades que van al CSV);
  mai regenera wavs.

## [0.1.5] — 2026-10-05 (tag `v0.1.5-checkpoint`)

### Afegit
- **Desfer/refer (undo/redo)** d'edició: moviment, redimensionat i canvi
  de nom, tant d'acords com d'estructures. Pila de **snapshots** del model
  (`acords`/`seccions`). Dreceres **Ctrl+Z** (desfer) i
  **Ctrl+Shift+Z** / **Ctrl+Y** (refer). Només en memòria de la sessió.
- `docs/ESQUEMA_UI.md` — document de referència de la UI (noms de zones,
  mides, interaccions).
- `docs/ESQUEMA_UI.html` — réplica visual fidel de la GUI (HTML+CSS).
- `docs/ESQUEMA_UI.svg` — versió vectorial de l'esquema.

### Canviat
- **Les wavs ja no es regeneren a cada edició.** `_desa_i_regenera()` i
  `_regenera_abc_des_de_totes_les_seccions()` ara escriuen **NOMÉS el CSV**.
  Les `wavs_acords/` i `wavs_estructura/` es generen **exclusivament** amb
  `exporta()` («Finalitza i publica»), quan tot està revisat i editat.
  Efecte: editar és **instantani** i l'undo/redo no toca mai les wavs.

### Nota de disseny
- Les wavs generades **no tenen cap paper** en la visualització ni l'edició:
  l'ona i la reproducció fan servir el **WAV original**; l'edició treballa
  sobre el **CSV**. Les wavs són el producte final d'exportació.

## [0.1.4] — 2026-10-05 (tag `v0.1.4-checkpoint`)

### Afegit
- **Follow del cursor**: durant la reproducció, si el cursor surt de la
  zona còmoda (0–85 % de la vista), la vista es desplaça per deixar-lo
  a ~15 % de l'esquerra (estil DAW). S'activa amb ▶ i s'atura amb ⏸.
- **Cursor hover** als clips d'acord i de secció: la «mà» sobre el cos,
  fletxes ↔ a les vores (paritat acords/estructura).

### Arreglat
- **Click sobre un clip desplaçat**: les connexions capturaven l'inici
  en crear el lambda (`lambda t0=float(ini)`) → després d'un resize, el
  click anava al **vell** inici. Ara es llegeix el valor **actual**
  de l'item (`it.ini` / `it.t`).
- **Cos de secció**: ara mou inici **i** fi (desplaça) com els acords;
  abans només movia l'inici (bug «només enrere»).
- **Propagació de contigüitat**: el fi d'un clip = inici del següent,
  recalculat sempre (2 bugs que col·lapsaven/separen clips).

## [0.1.3] — 2026-10-05 (tag `v0.1.3-wip`)

### Afegit / Canviat
- **Paritat acords/estructura**: les estructures passen a model «només
  inici» (el fi es deriva del veí); cos de secció desplaça inici+fi.
- **Snap més fi**: mai el compàs sencer — setzena (span ≤ 8 beats),
  corxera (≤ 32) o temps; mode lliure 0.02–1.0 s.
- Llindar de click 3 → 5 px; la guia de snap s'amaga al deixar anar.
- Regeneració només al release (no a cada frame).

## [0.1.2] — 2026-10-05 (tag `v0.1.2`)

### Afegit / Canviat
- **Coordenades unificades** al visor: clips, cursor, grid, regle, ona,
  guia i loop tots relatius a la vista (`_x_to_time` únic); escena =
  mida de la viewport. Abans clips/cursor eren absoluts i la resta
  relatius → es desalineaven amb zoom/scroll.
- **Pan** amb botó dret arrossegant; **roda = zoom** centrat al clip
  seleccionat (o al cursor).
- **Loop A/B** arrossegant sobre el regle (banda groga).
- Sincronització bidireccional llista ↔ timeline; Space = play/pausa.

## [0.1.1] — 2026-10-05 (tag `v0.1.1`)

### Afegit
- Visor DAW-like: **ona plena** (estil Audacity, envolupant min/max per
  tram visible) + **GridLayer** (compàs/beat/subdivisió) + regle a dalt.
- **2 carrils sobreposats** semitransparents (estructura + acords).

## [0.1] — 2026-10-01 (tag `v0.1-punt-control`)

### Afegit
- Script únic `wav_a_wavs.py` (mateix motor que l'app, sense duplicar lògica).
- Entorn aïllat Ubuntu sense sudo: `requirements.txt` (`PyQt5`,
  `pyqtgraph`, `numpy<2` obligat pel Q9400) + `instal·la_local.sh`
  (venv + `.deps/` amb headers via `apt-get download`, sense instal·lar).
- `chordextract` compila en local (`.deps/`); via `sonic-annotator` intacta.
- `fer_abc` per famílies (`N1/N4→N`), fusió d'adjacents i resum de
  repeticions (ex. `ABCBACDACA, A×4 B×2 C×3 D×1`).

### Arreglat
- `acords_a_live.py`: csv amb tot `N` donava `IndexError`; ara error
  llegible (`cap acord detectat...`, sortida 1).

## [No publicat — visor fase A/B.1]

### Afegit
- Visor fase A (`app/visor.py`): ona + acords + estructura + escolta amb
  transports (play/pausa/stop, ±10 s, volum/mute, loop A-B, zoom, temps),
  botó «Analitza» (Chordino+Segmentino en fil) i ressalt del que sona.
  Reproducció amb `paplay` extern (QtMultimedia aparcat: segfault).
- Visor fase B.1: doble-clic a un acord → desa `acords.csv` i regenera
  `wavs_acords/` (i locators/guia) sense tornar a Chordino.
- `CHANGELOG.md`, `ROADMAP.md`, `pyproject.toml`.
