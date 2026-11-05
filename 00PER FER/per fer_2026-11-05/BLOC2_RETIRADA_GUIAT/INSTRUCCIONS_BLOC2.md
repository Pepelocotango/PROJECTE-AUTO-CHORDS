# INSTRUCCIONS D'APLICACIÓ — BLOC 2
**Data:** 2026-11-05  
**Objectiu:** Retirada definitiva del subsistema obsolet d'anàlisi guiada v2/v3 (codi mort identificat com a `A-01` a l'auditoria tècnica).  
**Estalvi:** ~5.380 línies eliminades (més de 1.600 línies de codi de producció orfe, 1.300 línies de mètodes morts a `main.py` i `dialegs.py`, i ~2.400 línies de tests obsolets).  
**Risc:** Baix (s'elimina codi que ja no tenia cap crida ni punt d'entrada des de la GUI, i es manté intacta la guia explicativa `DialegGuiaRapida` i els marcadors actius).

---

## 1. Resum del canvi

L'antic flux d'anàlisi guiat per trams (v2) i per ancoratges (v3) va quedar completament superat per:
1. Els **marcadors de compàs i secció en viu (`+`)** sobre la forma d'ona.
2. L'acció de detecció de BPM per trams (`DialegTempoPerTrams` / Ellis DP).
3. La substitució del botó `b_guia` cap a la nova **«Guia ràpida»** explicativa (`DialegGuiaRapida`), que no toca el model.

Els fitxers `ancoratges.py` i `dialeg_ancoratges.py` havien quedat com a codi orfe, i a `app/main.py` i `app/dialegs.py` hi romanien centenars de línies de fils de detecció secundaris (`FilGuiaBpm`) i diàlegs antics (`DialegGuiaDownbeat`, `DialegGuiaBpm`) que ningú podia obrir.

---

## 2. Fitxers modificats al paquet

| Fitxer original al repo | Fitxer modificat al paquet | Canvis realitzats |
|---|---|---|
| `app/main.py` | `MODIFICATS/app/main.py` | Eliminat fil `FilGuiaBpm`, imports d'`ancoratges`, mètodes `_analisi_ancoratges`, `_aplica_ancoratges`, `_mou_cursor_guia`, i el bucle sencer `_guia_*` (-754 línies). Consolidat `b_guia` com a «Guia ràpida». |
| `app/dialegs.py` | `MODIFICATS/app/dialegs.py` | Eliminats `DialegGuiaDownbeat` i `DialegGuiaBpm`, i imports no usats `time` i `pyqtSignal` (-535 línies). |
| `tests/test_gui.py` | `MODIFICATS/tests/test_gui.py` | Eliminades les classes de prova de diàlegs i fils eliminats (-2.051 línies). Actualitzat el test del botó `b_guia` a «Guia ràpida». |

---

## 3. Fitxers a esborrar o arxivar (a la màquina Linux)

Executa a l'arrel del repositori Linux per retirar els fitxers que han deixat d'existir:

```bash
# 1. Codi de producció i tests orfes:
git rm app/ancoratges.py
git rm app/dialeg_ancoratges.py
git rm tests/test_ancoratges.py

# 2. Documents de disseny i propostes obsoletes (arxivar a docs/archive/):
mkdir -p docs/archive
git mv docs/ANALISI_GUIAT.md docs/archive/
git mv docs/ANALISI_GUIAT_v2.md docs/archive/
git mv docs/ANALISI_GUIAT_v3.md docs/archive/
git mv docs/ANALISI_GUIAT_PROPOSTA.md docs/archive/
git mv docs/ANALISI_GUIAT_DISCUSSIO.md docs/archive/
git mv docs/PLA_GUIAT_V2.md docs/archive/
git mv docs/PLA_GUIAT_V3.md docs/archive/
```

---

## 4. Com aplicar els fitxers modificats a Linux

### Opció A: Còpia directa dels fitxers modificats
Des de l'arrel del repositori a Linux:
```bash
cp "00PER FER/PAQUET_USB_2026-11-05/BLOC2_RETIRADA_GUIAT/MODIFICATS/app/dialegs.py" app/dialegs.py
cp "00PER FER/PAQUET_USB_2026-11-05/BLOC2_RETIRADA_GUIAT/MODIFICATS/app/main.py" app/main.py
cp "00PER FER/PAQUET_USB_2026-11-05/BLOC2_RETIRADA_GUIAT/MODIFICATS/tests/test_gui.py" tests/test_gui.py
```

### Opció B: Aplicació mitjançant el pegat unificat (`.patch`)
Des de l'arrel del repositori a Linux:
```bash
git apply "00PER FER/PAQUET_USB_2026-11-05/BLOC2_RETIRADA_GUIAT/DIFFS/bloc2.patch"
```

---

## 5. Validació obligatòria a Linux

Un cop aplicats els fitxers i retirats els fitxers orfes:

```bash
# 1. Comprova que l'estil i la sintaxi siguin 100% nets (sense imports orfes ni alertes):
.venv/bin/python -m pyflakes app/*.py tests/*.py

# 2. Executa la suite de tests completa:
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests

# 3. Comprova que no quedi cap referència trencada:
git grep "ancoratges"
git grep "FilGuiaBpm"
git grep "DialegGuiaDownbeat"
```

---

## 6. Proposta de commit (en català)

```bash
git add app/main.py app/dialegs.py tests/test_gui.py app/ancoratges.py app/dialeg_ancoratges.py tests/test_ancoratges.py docs/
git commit -m "refactor: retirada del subsistema d'anàlisi guiat v2/v3 i neteja de codi mort

- Elimina completament el subsistema orfe d'anàlisi guiat per ancoratges (app/ancoratges.py, app/dialeg_ancoratges.py).
- Retira de app/main.py el fil FilGuiaBpm, _analisi_ancoratges i el bucle complet _guia_*.
- Retira de app/dialegs.py els diàlegs obsolets DialegGuiaDownbeat i DialegGuiaBpm.
- Consilida el botó de barra b_guia exclusivament com a 'Guia ràpida' (DialegGuiaRapida).
- Neteja les suites de test a test_gui.py i retira test_ancoratges.py (~5.380 línies totals eliminades)."
```
