# INSTRUCCIONS D'APLICACIÓ — BLOC 1
**Data:** 2026-11-05  
**Objectiu:** Sincronització de documentació canònica i correcció del bug multiplataforma de resolució de plugins Vamp (`app/vamp_params.py`).  
**Risc:** Molt baix (sense impacte en lògica central d'àudio o timeline; només correccions documentals i camins multiplataforma).

---

## 1. Fitxers afectats

| Fitxer original al repo | Fitxer modificat al paquet | Descripció del canvi |
|---|---|---|
| `app/vamp_params.py` | `MODIFICATS/app/vamp_params.py` | Resolució dinàmica de camins `.n3` via `plataforma.dirs_plugins()` amb fallback multiplataforma. Evita fallada silenciosa a Windows/macOS. |
| `docs/REGLES_DE_LA_APP.md` | `MODIFICATS/docs/REGLES_DE_LA_APP.md` | Correcció a la capçalera (línia 9): «regles d'or (1–12)» en lloc de l'obsolet «(1–19)». |
| `docs/ESQUEMA_UI.md` | `MODIFICATS/docs/ESQUEMA_UI.md` | Correcció a la taula de controls (línia 56): `b_guia` obre `DialegGuiaRapida`, no l'inexistent `DialegAncoratges`. |
| `AGENTS.md` | `MODIFICATS/AGENTS.md` | Actualització a 4 CSVs (`marcadors.csv` inclòs), 14 suites/fitxers de test, denominadors permesos (2, 4, 8) i relleu de sessió 2026-11-05. |
| `DEVELOPING.md` | `MODIFICATS/DEVELOPING.md` | Neteja del model de dades obsolet (esborrat d'`analisi/` i `segments.csv`), i taula completa de mòduls actualitzada als 39 actius. |

---

## 2. Com aplicar els canvis a la màquina Linux

Pots triar una d'aquestes dues vies:

### Opció A: Còpia directa dels fitxers modificats
Des de l'arrel del repositori a Linux:
```bash
cp "00PER FER/PAQUET_USB_2026-11-05/BLOC1_DOCS_I_BUG_VAMP/MODIFICATS/app/vamp_params.py" app/vamp_params.py
cp "00PER FER/PAQUET_USB_2026-11-05/BLOC1_DOCS_I_BUG_VAMP/MODIFICATS/docs/REGLES_DE_LA_APP.md" docs/REGLES_DE_LA_APP.md
cp "00PER FER/PAQUET_USB_2026-11-05/BLOC1_DOCS_I_BUG_VAMP/MODIFICATS/docs/ESQUEMA_UI.md" docs/ESQUEMA_UI.md
cp "00PER FER/PAQUET_USB_2026-11-05/BLOC1_DOCS_I_BUG_VAMP/MODIFICATS/AGENTS.md" AGENTS.md
cp "00PER FER/PAQUET_USB_2026-11-05/BLOC1_DOCS_I_BUG_VAMP/MODIFICATS/DEVELOPING.md" DEVELOPING.md
```

### Opció B: Aplicació mitjançant el pegat unificat (`.patch`)
Des de l'arrel del repositori a Linux:
```bash
git apply "00PER FER/PAQUET_USB_2026-11-05/BLOC1_DOCS_I_BUG_VAMP/DIFFS/bloc1.patch"
```

---

## 3. Validació obligatòria a Linux

Un cop aplicats els fitxers, executa les comprovacions de qualitat:

```bash
# 1. Comprova que l'estil i la sintaxi siguin 100% nets:
.venv/bin/python -m pyflakes app/vamp_params.py AGENTS.md

# 2. Executa la suite de tests per confirmar que no hi ha cap regressió:
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tests/test_pipeline.py

# 3. Revisa les diferències amb git per verificar que només s'ha tocat el previst:
git diff
```

---

## 4. Proposta de commit (en català)

Si la suite està en verd i `git diff` és net:

```bash
git add app/vamp_params.py docs/REGLES_DE_LA_APP.md docs/ESQUEMA_UI.md AGENTS.md DEVELOPING.md
git commit -m "docs: sincronització de documentació i fix de resolució de plugins a vamp_params

- Resol dinàmicament els camins dels fitxers .n3 de paràmetres Vamp mitjançant plataforma.dirs_plugins() amb suport multiplataforma.
- Corregeix la numeració de regles d'or a REGLES_DE_LA_APP.md (1-12).
- Corregeix el diàleg referenciat pel botó b_guia a ESQUEMA_UI.md (DialegGuiaRapida).
- Actualitza AGENTS.md i DEVELOPING.md amb els 4 CSVs actius, 39 mòduls i 14 suites de test."
```
