# INSTRUCCIONS BLOC 5 - RENOMBRAT mapa_tempo.py -> tempo_csv.py
Data: 2026-11-05
Objectiu: Eliminar la col-lisio de noms tempo_map.py (motor) vs mapa_tempo.py (CSV).
Risc: Baix (renombra mecanic + actualitzacio d'imports).

## 1. Resum
Renombra app/mapa_tempo.py a app/tempo_csv.py i actualitza tots els imports i referencies.
El nom del fitxer CSV (mapa_tempo.csv) NO canvia (compatibilitat amb projectes existents).

## 2. Fitxers afectats
- app/mapa_tempo.py -> esborrar (renombrat a app/tempo_csv.py)
- app/tempo_csv.py (nou, copia de mapa_tempo.py amb imports actualitzats)
- app/main.py, app/pipeline.py, app/projecte.py, app/tempo.py, app/visor.py
- tests/test_despatx_edicio.py, tests/test_edicio.py, tests/test_gui.py
- tests/test_mapa_tempo.py, tests/test_pipeline.py, tests/test_tempo_map.py, tests/test_tempo_trams.py

## 3. Aplicacio (copia directa)
cp MODIFICATS/app/tempo_csv.py app/tempo_csv.py
cp MODIFICATS/app/main.py app/main.py
cp MODIFICATS/app/pipeline.py app/pipeline.py
cp MODIFICATS/app/projecte.py app/projecte.py
cp MODIFICATS/app/tempo.py app/tempo.py
cp MODIFICATS/app/visor.py app/visor.py
cp MODIFICATS/tests/*.py tests/
git rm app/mapa_tempo.py

## 4. Patch
git apply DIFFS/bloc5.patch

## 5. Validacio
.venv/bin/python -m pyflakes app/*.py tests/*.py
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests
