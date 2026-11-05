# INSTRUCCIONS BLOC 4 - BLINDATGE DEL FLUX PRINCIPAL
Data: 2026-11-05
Objectiu: Blindar el flux principal (carregar -> analitzar -> tallar -> mapa) amb guardrails i validacions.
Risc: Baix (canvis de validacio + tests nous).

## 1. Resum
Canvis de codi:
- app/beats.py: _bpm_de_beats valida el BPM resultant contra limits.BPM_MIN/MAX (retorna None si fora de banda).
- app/pipeline.py: wav_info captura fitxer inexistent i WAV invalid (ValueError clar).
Tests nous:
- tests/test_tempo_map_guardrails.py (9 tests)
- tests/test_beats_guardrails.py (4 tests)
- tests/test_pipeline_guardrails.py (2 tests)

## 2. Aplicacio (copia directa)
cp MODIFICATS/app/tempo_map.py app/tempo_map.py
cp MODIFICATS/app/beats.py app/beats.py
cp MODIFICATS/app/pipeline.py app/pipeline.py
cp MODIFICATS/tests/test_tempo_map_guardrails.py tests/
cp MODIFICATS/tests/test_beats_guardrails.py tests/
cp MODIFICATS/tests/test_pipeline_guardrails.py tests/

## 3. Patch
git apply DIFFS/bloc4.patch

## 4. Validacio
.venv/bin/python -m pyflakes app/*.py tests/*.py
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests
