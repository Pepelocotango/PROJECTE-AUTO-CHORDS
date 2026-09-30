# Desenvolupament — PROJECTE AUTO CHORDS

Tot en català. Llicència: GPLv3 (vegeu `LICENSE`).

## Requisits

- Python 3.8+ (stdlib; sense pip per al pipeline).
- Per a l'app: PyQt5 del sistema (`python3-pyqt5`, Qt5).
  ⚠️ Qt6 **no** corre en CPU sense SSE4.2 (com el Q9400): no s'hi pot
  usar PySide6/PyQt6.
- `sonic-annotator` + plugin Chordino (`nnls-chroma-linux64-local/`)
  per al pas `wav → csv`.

## Arrencar l'app

```bash
bash AUTO_CHORDS.sh
# o bé:
python3 app/main.py
```

## Pipeline manual

```bash
VAMP_PATH=nnls-chroma-linux64-local ./sonic-annotator \
  -d vamp:nnls-chroma:chordino:simplechord -w csv tema.wav
python3 acords_a_live.py acords.csv 138 4 [offset_segons]
```

## Verificar canvis

```bash
python3 -m py_compile acords_a_live.py app/main.py app/pipeline.py
```

## VM Debian (execució, no compilació)

A la VM només calen llibreries d'execució:

```bash
bash instal·la_vm_debian.sh   # demana 1 pkexec, dins la VM
```

Nota: aquest repo viu al `/home` de l'host; la VM/Mac no hi accedeix
directament. Per usar-lo allà, copia la carpeta o deixa-la a l'exFAT.

## Convencions

- Comentaris i docs en català.
- Sense secrets ni credencials al repo (ni claus API ni tokens).
- Els binaris compilats aquí (`sonic-annotator`, `.so`) SÍ es commitegen
  (són l'eina); les sortides (`*_obsolets/`, `midis_acords/`) no.
