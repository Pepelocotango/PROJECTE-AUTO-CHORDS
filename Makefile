# Comandes del projecte AUTO CHORDS.
# La font de veritat és aquest fitxer; no dupliquis les comandes als .md.

PY := .venv/bin/python
OFFSCREEN := QT_QPA_PLATFORM=offscreen

.PHONY: help entorn app compile test lint smoke docs docs-check aleatori coverage check

help:
	@echo "make entorn      instal·la l'entorn local (sense sudo)"
	@echo "make app         arrenca l'app"
	@echo "make compile     compilació ràpida (no arrenca l'app)"
	@echo "make test        suite completa (offscreen)"
	@echo "make lint        pyflakes"
	@echo "make smoke       smoke de l'app"
	@echo "make docs        regenera les vistes i els documents generats"
	@echo "make docs-check  comprova que els documents generats estan al dia"
	@echo "make aleatori    suite en ordre aleatori"
	@echo "make coverage    suite amb informe de cobertura"
	@echo "make check       compile + lint + test + docs-check"

entorn:
	bash instal·la_local.sh

app:
	bash AUTO_CHORDS.sh

compile:
	$(PY) -m py_compile app/*.py wav_a_wavs.py

test:
	$(OFFSCREEN) $(PY) -m unittest discover -s tests

lint:
	$(PY) -m pyflakes app/*.py tests/*.py

smoke:
	AUTO_CHORDS_SMOKE=1 $(OFFSCREEN) $(PY) -m app.main

docs:
	$(PY) eines/genera_esquema_ui.py
	$(PY) eines/genera_inventari.py
	$(PY) eines/genera_moduls.py

docs-check:
	$(PY) eines/genera_esquema_ui.py --check
	$(PY) eines/genera_inventari.py --check
	$(PY) eines/genera_moduls.py --check

aleatori:
	$(PY) eines/ordre_aleatori.py 3

coverage:
	$(OFFSCREEN) $(PY) -m coverage run --source=app -m unittest discover -s tests
	$(PY) -m coverage report

check: compile lint test docs-check
