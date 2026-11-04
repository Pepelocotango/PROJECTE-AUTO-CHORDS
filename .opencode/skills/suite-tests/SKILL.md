# Suite de tests (procediment)

Font: `AGENTS.md` § "Com executar-ho" i `DEVELOPING.md`.

## Comandes

```bash
# Suite completa (ha d'estar sempre verda; offscreen = cap diàleg)
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests

# Estil (ha d'estar net)
.venv/bin/python -m pyflakes app/*.py tests/*.py

# Tests en ordre aleatori
.venv/bin/python eines/ordre_aleatori.py 3

# Smoke de l'app empaquetada
AUTO_CHORDS_SMOKE=1 QT_QPA_PLATFORM=offscreen .venv/bin/python -m app.main
```

## Higiene obligatòria

- Tots els tests importen `tests/_temporals.py` (esborra temporals en plegar).
- Si creen widgets, netegen amb `tests/_qt_neteja.py`.
- La suite **no deixa res al disc**. Si afegeixes un test nou, importa `_temporals`.
- No deixis processos ni temporals en segon pla.

## Patxos obligatoris als tests

- `QMessageBox.show()` als tests a Windows → access violation: patxa sempre `QMessageBox` quan l'app pugui avisar.
- PyQt5 + GC: objectes Qt destruïts en ordre arbitrari poden fer segfault intermitent (`_qt_neteja`).

## Convencions

- Test de regressió per a cada fix: el bug que arregles ha de quedar cobert per un test que el reprodueixi.
- No modifiquis tests existents per fer passar un bug.
- Si un test falla, reporta test + error + causa probable; no "arreglis" el test.

## Comptes actuals

- ~1.589 tests, 1 omés.
- Si afegeixes tests, el comptador canvia; actualitza `AGENTS.md` "Estat actual" si cal.
