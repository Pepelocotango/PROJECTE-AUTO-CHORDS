# Higiene de release (checklist)

Font: `AGENTS.md` § "Com es treballa" i `DEVELOPING.md`.

## Abans de commitejar

1. **Suite verda**: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests`
2. **pyflakes net**: `.venv/bin/python -m pyflakes app/*.py tests/*.py`
3. **Docs actualitzades** si ha canviat comportament:
   - `CHANGELOG.md` (amb data)
   - `AGENTS.md` "Estat actual" (reescriure, no incremental)
   - docs/ afectats (`REGLES_DE_LA_APP.md` només amb aprovació explícita de l'operador)
4. **Tests de regressió** per cada fix.
5. **Sense secrets** (`.secrets/`, claus API, credencials).
6. **Sense esborrats definitius**: paperera sempre (`gio trash`, mai `rm`).
7. **Tot en català**: comentaris, docs, commits.
8. **Sense processos ni temporals** en segon pla en acabar.

## Decisions que NO es reintrodueixen sense ordre

- MCP (retirat 2026-10-19).
- Tonalitat automàtica (`qm-keydetector`).
- `acords_locators.txt`.
- Carpeta `analisi/` i `segments.csv`.
- `sonic-annotator` (únic motor: `vamp_host_local`).

## Retrocompatibilitat

No és prioritat. Canvis de format rebutgen projectes vells amb error clar. No migració, no lector tolerant, no dos formats en paral·lel. No es destrueix mai un fitxer de l'usuari.

## Paranys coneguts

- CPU Q9400 sense AVX/SSE4.2: numpy < 2 obligatori.
- PyQt5 + GC: segfault intermitent (neteja amb `_qt_neteja`).
- `QMessageBox.show()` als tests a Windows → access violation (patxa sempre).
- `os.kill(pid, 0)` NO és sonda a Windows.
- `pgrep -f` es troba a si mateix.
- Build de Windows és el més fràgil.

## Paquets de release

Només porten: `README.md`, `LICENSE`, `LLICENCIES_TERCERS.md` i les 2 imatges del README.
