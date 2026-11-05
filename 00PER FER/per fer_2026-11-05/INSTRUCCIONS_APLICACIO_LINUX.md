# INSTRUCCIONS PER A L'APLICACIÓ AL PC LINUX (REPOSITORI REAL)

> **Data de generació:** 2026-11-05  
> **Contingut del paquet:**  
> - `AUDITORIA_TECNICA_2026-11-05.md` (Auditoria tècnica completa + Secció 10 de Revisió Independent).  
> - `INSTRUCCIONS_APLICACIO_LINUX.md` (Aquest full de ruta pas a pas).

---

## 1. On va aquest fitxer al PC Linux
Copia el fitxer d'auditoria al repositori original a la mateixa carpeta:
```bash
cp AUDITORIA_TECNICA_2026-11-05.md "<ruta-al-projecte>/00PER FER/AUDITORIA_TECNICA_2026-11-05.md"
```

---

## 2. Abans de tocar cap codi (Fase 0 de seguretat)
Al PC Linux (amb entorn complet, Git i Python):

1. **Comprovar l'estat net de Git:**
   ```bash
   git status
   ```
2. **Crear  tag de seguretat:**
   ```bash
   git tag abans-neteja-2026-11-05
   ```
3. **Comprovar que la suite de tests i l'estil estan en verd:**
   ```bash
   QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests
   .venv/bin/python -m pyflakes app/*.py tests/*.py
   ```
   *(Si algun test falla abans de començar, aturar-se i avisar l'operador).*

---

## 3. Ordre d'execució recomanat (segons la Revisió Independent §10.4)

### Bloc 1 — Higiene documental i correcció multiplataforma (Immediat)
1. **Corregir el bug A-04 a `app/vamp_params.py`:**
   - Fer que resolgui els fitxers `.n3` a través de `plataforma.dirs_plugins()`.
2. **Reconciliació documental:**
   - Actualitzar `AGENTS.md` (indicar 4 CSVs, 14 mòduls de test, denominadors 2/4/8).
   - Actualitzar `docs/REGLES_DE_LA_APP.md` (línia 9: «1–12 + §13» en lloc de «1–19»).
   - Actualitzar `DEVELOPING.md` (afegir els 19 mòduls que falten i reflectir el model de 4 CSVs).
   - Actualitzar `docs/ESQUEMA_UI.md` (línia 56: reflectir que obre `DialegGuiaRapida`, no `DialegAncoratges`).
   - Regenerar l'esquema UI:
     ```bash
     .venv/bin/python eines/genera_esquema_ui.py
     ```

### Bloc 2 — Retirada del guiat v2/v3 mort (Fase 1 de l'auditoria)
- Eliminar `app/dialeg_ancoratges.py` i `app/ancoratges.py` (a la paperera amb `gio trash`, mai `rm`).
- Netejar de `app/main.py`: `FilGuiaBpm`, `_analisi_ancoratges`, `_aplica_ancoratges`, `_analisi_guitat` i la cadena `_guia_*`.
- Netejar de `app/dialegs.py`: `DialegGuiaDownbeat` i `DialegGuiaBpm`.
- Renombrar el botó de la barra a **«Guia ràpida»** (manté `dialeg_guia_rapida.py`).
- Eliminar `tests/test_ancoratges.py` i els tests associats al guiat mort a `tests/test_gui.py`.
- Verificar suite i pyflakes en verd després d'aquest bloc.

### Bloc 3 — Codi orfe i modularització de `pipeline.py`
- Eliminar shims i funcions sense crides identificades a §3.10 (`pipeline.duplica_*`, `metronom._ha_de_sonar`, etc.).
- Renombrar `app/mapa_tempo.py` → `app/tempo_csv.py` per eliminar la confusió amb `tempo_map.py`.
- Modularitzar `app/pipeline.py` (2.257 línies) en `pipeline_vamp.py` i `pipeline_export.py` mantenint `pipeline.py` com a façana.

---

## 4. Normes de treball de l'operador
- **Tot en català** (comentaris, commits, documentació).
- **Paperera sempre** (`gio trash`, mai `rm`).
- **Un commit per bloc/fase**, amb suite verda i `pyflakes` net abans de commitejar.
- **Mai fer push** sense el vistiplau explícit de l'operador.
