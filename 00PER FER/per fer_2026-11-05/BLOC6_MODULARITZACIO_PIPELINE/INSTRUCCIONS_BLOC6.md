# INSTRUCCIONS BLOC 6 - MODULARITZACIO DE pipeline.py (FASE 4, part 1)
Data: 2026-11-05
Objectiu: Extreure el motor Vamp (subprocess, transforms, deteccio) a pipeline_vamp.py.
Risc: Baix (extraccio de backend pur, sense Qt).

## 1. Resum
Extreu ~30 funcions i constants del motor Vamp de pipeline.py a un nou modul pipeline_vamp.py.
pipeline.py esdevé fassana que re-exporta els simbols necessaris.

## 2. Fitxers afectats
- app/pipeline_vamp.py (nou)
- app/pipeline.py (modificat: importa de pipeline_vamp, elimina funcions mogudes)

## 3. Aplicacio (copia directa)
cp MODIFICATS/app/pipeline_vamp.py app/pipeline_vamp.py
cp MODIFICATS/app/pipeline.py app/pipeline.py

## 4. Patch
git apply DIFFS/bloc6.patch

## 5. Validacio
.venv/bin/python -m pyflakes app/*.py tests/*.py
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests
