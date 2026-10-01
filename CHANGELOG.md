# Registre de canvis — PROJECTE AUTO CHORDS

Format [Keep a Changelog](https://keepachangelog.com/ca/1.0.0/).
Versions amb tag git (`v0.1-punt-control`, ...).

## [No publicat]

### Afegit
- Visor fase A (`app/visor.py`): ona + acords + estructura + escolta amb
  transports (play/pausa/stop, ±10 s, volum/mute, loop A-B, zoom, temps),
  botó «Analitza» (Chordino+Segmentino en fil) i ressalt del que sona.
  Reproducció amb `paplay` extern (QtMultimedia aparcat: segfault).
- Visor fase B.1: doble-clic a un acord → desa `acords.csv` i regenera
  `wavs_acords/` (i locators/guia) sense tornar a Chordino.
- `CHANGELOG.md`, `ROADMAP.md`, `pyproject.toml`.

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
