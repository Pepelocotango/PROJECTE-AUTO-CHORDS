# Registre de canvis — PROJECTE AUTO CHORDS

Format [Keep a Changelog](https://keepachangelog.com/ca/1.0.0/).
Versions amb tag git (`v0.1-punt-control`, ..., `v0.1.4-checkpoint`).

## [No publicat]

### Pendent de polir (visor)
- Confusió visual entre clip **seleccionat** (vora groga) i **actiu**
  (fons més clar, segons el cursor).
- Usabilitat: undo/redo, multi-selecció, duplicar/eliminar clips,
  menú contextual, afegir clips amb click al buit.

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
