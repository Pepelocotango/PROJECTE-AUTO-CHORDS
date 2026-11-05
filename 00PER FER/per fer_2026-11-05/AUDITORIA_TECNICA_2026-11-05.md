# AUDITORIA TÈCNICA — PROJECTE AUTO CHORDS

> **Data:** 2026-11-05
> **Abast:** repositori complet (`app/`, `tests/`, `eines/`, `docs/`, CI, build i
> dades versionades).
> **Mètode:** anàlisi **estàtica** (lectura, recompte, graf d'imports i
> referències creuades). **No s'ha executat l'app ni la suite**: l'equip
> d'aquesta sessió no té Python instal·lat. **No s'ha modificat cap fitxer de
> codi.** Aquest document és l'únic artefacte.
> **Per a:** l'agent de codi que executarà el pla de la §6.

> ⚠️ **Avís de seguretat previ a qualsevol esborrat.** Esta còpia és un **ZIP
> sense `.git`** (`Test-Path .git` = `False`). No hi ha historial: qualsevol
> esborrat és **definitiu**. Abans de la fase 1 cal treballar sobre el
> repositori real de l'operador (amb historial) o inicialitzar-ne un i fer un
> commit/tag de referència. A més, la norma del projecte és **paperera sempre,
> mai `rm`**.

---

## 0. Resum executiu

**Veredicte:** el producte és coherent i el codi és seriós (suite gran, regles
d'or escrites, escriptura atòmica, documentació abundant). El desordre **no és
caòtic**: és l'acumulació d'un **canvi de rumb** (anàlisi guiada v2/v3 →
marcadors en viu + beats QM) que va deixar una **capa sencera de codi mort** i
una **documentació que descriu dues realitats alhora**.

La feina gran **no és reescriure**: és **traure el que ja no és**, **reconciliar
els documents** i **trencar tres god objects** sense tocar les regles d'or.

### Xifres clau (snapshot 2026-11-05)

| Mètrica | Valor |
|---|---|
| Codi de l'app | **26.844 línies** en **39 mòduls** `.py` |
| Tests | **21.226 línies**, **14 mòduls** `test_*.py`, **1.592 mètodes** `test_` |
| Documentació | **53** fitxers `.md`, **13.093 línies**, **919 KB** |
| Repositori | **240 fitxers**, **5,79 MB** (sense `.git`) |
| Ràtio test:codi | **0,79** línies de test per línia d'app |
| Ràtio docs:codi | **0,49** línies de doc per línia d'app |
| Cobertura exigida al CI | **65 %** (`--fail-under=65`) |
| Workflows | **6**, tots d'execució **manual** |
| Enllaços interns trencats a `docs/` | **0** |
| Marques `TODO`/`FIXME` al codi | **0** |

### Top 5 problemes

1. **Subsistema «Anàlisi guiat» v2/v3 mort** (≈2.460 línies, 9,2 % de
   l'app) però encara importat, documentat com a viu a `docs/ESQUEMA_UI.md` i
   cobert per tests. El botó de la barra ja **no** fa eixe flux: obri una guia
   informativa de 5 pantalles.
2. **God objects**: `visor.py` 5.905 línies / 227 mètodes; `main.py` 5.130 /
   225; `pipeline.py` 1.954 / 89 funcions; `Finestra.__init__` 432 línies;
   `Visor.__init__` 427; `Visor.executa_edicio` 186.
3. **Documentació contradictòria**: conviuen **v0.7.0, v0.8.0 i v9.0.0**; les
   regles són «1–12» en uns llocs i «1–19» en un altre; `DEVELOPING.md` descriu
   un model de dades que ja no existeix; `ROADMAP.md` diu que el guiat «no té
   entrada a la UI» (fals); el `CHANGELOG` té `[Unreleased]` **davall** de
   9.0.0.
4. **Compatibilitats que la norma prohibeix** (decisió 2026-11-02): migració
   d'`AUTOCHORDS_<nom>/`, `_convertit.wav`, tuples de 5 elements, signatures
   antigues, `clip_te_temps_sencer`.
5. **Higiene i procés**: binaris Linux commitejats (~1,2 MB), codi font de
   Chordino amb metadades de Mercurial, **cap CI en push/PR** i cobertura
   mínima del 65 %.

### Les decisions (vegeu §7)

- **D1 — Guiat v2/v3: DECIDIDA (2026-11-05).** S'elimina i es documenta; es
  reconstruirà quan el nucli funcione correctament. La funcionalitat real
  d'avui són els marcadors en viu.
- **D2 — Binaris Linux:** context i protocol per a l'agent a §7.1. Recomanació:
  híbrid (quedar-se'ls, però amb checksum i verificació al CI).
- **D3 — Refactor de `main.py`/`visor.py`:** explicat a §7.2. Recomanació:
  ajornar; com a màxim, extraure `pipeline.py` si es vol un guany ràpid.

---

## 1. Què és el projecte avui (i què ja no és)

### 1.1 Producte real (flux viu)

1. **Obrir àudio** → es crea un **projecte autocontingut** (`.acproj` + `audio/`
   + `backup/`); l'àudio es converteix amb `ffmpeg` **dins** `audio/`.
2. **Analitzar** (opcional): acords (Chordino) + estructura (QM segmenter) +
   BPM/compàs (QM/beat tracker) amb el host propi `vamp_host_local`.
3. **Revisar/editar** en un visor d'estil DAW amb **3 pistes** (acords,
   estructura, mapa de tempo/compàs) + **marcadors en viu** (`+`).
4. **Exportar**: 3 CSV model + WAVs silenciosos per acord/secció + `mapa_tempo/`
   + `guia_acords.html` + partitura MusicXML/PDF/MSCZ.
5. **Editar l'àudio** (retallar/afegir silenci als extrems) i **exportar àudio**
   (WAV/MP3/FLAC/AAC/OGG/Opus).

### 1.2 Arquitectura de facto (capes)

```
GUI            main.py (Finestra) ── visor.py (Visor) ── timeline*.py
                 │                      │
diàlegs          dialegs.py · dialeg_bpm_marcadors.py · dialeg_guia_rapida.py
                 │
domini           tempo_map.py (motor) · mapa_tempo.py (serialització)
                 rubato.py · marcadors.py · tempo_ajust.py · graella.py
                 beats.py · tempo.py (DSP) · bpm_unit.py · limits.py
                 │
backend          pipeline.py (Vamp + model + export) · postproc.py · xifrat.py
                 partitura.py · projecte.py · audio_edit.py · exporta_audio.py
                 │
plataforma       audio_out.py · ffmpeg.py · plataforma.py · config.py
```

**Problemes estructurals de la capa de domini:**

- **`tempo_map.py` (1.709 l.) vs `mapa_tempo.py` (277 l.)**: noms quasi
  idèntics i responsabilitats diferents (motor vs serialitzador CSV). És la
  principal font de confusió per a un agent nou.
- **`tempo.py` vs `beats.py`**: `tempo.py` fa DSP (autocorrelació + beat
  tracking); `beats.py` orquestra motors (nostre/QM). Noms poc clars.
- **`ancoratges.py`** no és domini viu: és part del guiat v3 mort.
- **`pipeline.py`** concentra **5 responsabilitats**: subprocess Vamp, model,
  CSV, WAVs, HTML i segments de partitura. 89 funcions top-level.

### 1.3 Model de dades real: **4 CSV**, no 3

AGENTS.md diu «els 3 CSV». El codi i `docs/FLUX_DE_DADES.md` en tenen **4**:

| Fitxer | Contingut | S'escriu |
|---|---|---|
| `acords.csv` | `inici,fi,acord` | a cada edició |
| `estructura_ABC.csv` | `inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi` | a cada edició |
| `mapa_tempo.csv` | `inici,fi,bpm,tipus,compassos` | a cada edició |
| **`marcadors.csv`** | `t_s,tipus` (`compas` \| `seccio`) | a cada edició |

`marcadors.csv` està documentat a `FLUX_DE_DADES.md`, `PROJECTES.md`,
`MARCADORS.md` i `REGLES_DE_LA_APP.md` §13.9, però **no** a la fitxa de model
d'`AGENTS.md`. A més, la seua E/S viu a `pipeline.py`
(`desa_marcadors`/`llegeix_marcadors*`) i no a `marcadors.py`, que només té la
lògica.

### 1.4 Evolució: eines i funcions que han quedat enrere

| Època | Eina/flux | Estat real avui |
|---|---|---|
| Pre-GUI | `wav_a_wavs.py` (CLI) | Viu com a script, però **fora del flux**; el flux és la GUI |
| Oct. 2026 | Anàlisi guiada **v1** (`AUBIO_TEMPO`, `PLA_GUIAT_V2`) | Mort; docs a `archive/` |
| Oct. 2026 | Anàlisi guiada **v2** (`_analisi_guitat`, `FilGuiaBpm`, `DialegGuia*`) | **Mort** (sense crides) |
| Oct. 2026 | Anàlisi guiada **v3** (`ancoratges`, `dialeg_ancoratges`) | **Mort** (sense crides) |
| Oct. 2026 | Botó «Anàlisi guiat» | Viu, però **obri una guia informativa** (`dialeg_guia_rapida.py`) |
| Oct. 2026 | `sonic-annotator` | Retirat; únic motor `vamp_host_local` |
| Oct. 2026 | MCP (`app/mcp_bridge.py`, eines `ac_*`) | Retirat |
| Oct. 2026 | Tonalitat automàtica (`qm-keydetector`) | Retirada |
| Oct. 2026 | `concatena.py` (context per a LLM) | Viu, però **obsolet** amb agents moderns |
| Nov. 2026 | Marcadors en viu (`+`) + beats QM | **Flux real** |

---

## 2. Mètriques de codi

### 2.1 Mòduls de l'app (línies)

| Mòdul | Línies | Mòdul | Línies |
|---|---:|---|---:|
| `visor.py` | 5.905 | `plataforma.py` | 312 |
| `main.py` | 5.130 | `ffmpeg.py` | 312 |
| `timeline.py` | 2.059 | `mapa_tempo.py` | 277 |
| `pipeline.py` | 1.954 | `audio_edit.py` | 247 |
| `tempo_map.py` | 1.709 | `acord_audio.py` | 245 |
| `dialegs.py` | 1.491 | `metronom.py` | 241 |
| `dialeg_ancoratges.py` | 883 | `theme.py` | 230 |
| `timeline_layers.py` | 830 | `marcadors.py` | 209 |
| `projecte.py` | 504 | `audio_out.py` | 197 |
| `timeline_items.py` | 503 | `panell_xifrat.py` | 171 |
| `tempo.py` | 463 | `beats.py` | 157 |
| `partitura.py` | 431 | `graella.py` | 140 |
| `xifrat.py` | 397 | `exporta_audio.py` | 125 |
| `timeline_base.py` | 376 | `dialeg_guia_rapida.py` | 118 |
| `rubato.py` | 347 | `tempo_ajust.py` | 108 |
| `ancoratges.py` | 340 | `postproc.py` | 102 |
| | | `icones.py` 81 · `vamp_params.py` 74 · `bpm_unit.py` 58 · `dialeg_bpm_marcadors.py` 57 · `config.py` 46 · `__init__.py` 9 · `limits.py` 6 |

**Concentració:** els 6 fitxers més grans sumen **18.248 línies (68 % de
l'app)**. Els 10 més grans, **20.968 (78 %)**.

### 2.2 Funcions i classes grans

| Fitxer:línia | Element | Línies |
|---|---|---:|
| `main.py:585` | `Finestra.__init__` | 432 |
| `visor.py:168` | `Visor.__init__` | 427 |
| `visor.py:2795` | `Visor.executa_edicio` | 186 |
| `timeline.py:194` | `TimelineView.__init__` | 174 |
| `dialegs.py:964` | `DialegGuiaBpm.__init__` | 174 |
| `dialeg_ancoratges.py:189` | `_construix` | 173 |
| `main.py:4324` | `Finestra.boto` | 169 |
| `ancoratges.py:192` | `encaixa_ancoratges` | 164 |
| `timeline.py:1713` | `mousePressEvent` | 146 |
| `main.py:1095` | `_crea_menus` | 144 |
| `main.py:3563` | `_carrega_visor` | 128 |
| `audio_edit.py:142` | `transforma_model` | 127 |
| `theme.py:71` | `app_stylesheet` | 124 |
| `timeline_layers.py:359` | `paint` | 117 |
| `projecte.py:205` | `crea` | 114 |
| `visor.py:5954` | `_alimenta` | 113 |
| `xifrat.py:133` | `normalitza_qualitat` | 113 |
| `visor.py:4616` | `quantitza` | 109 |

### 2.3 Tests

| Mòdul | Mètodes `test_` | Línies |
|---|---:|---:|
| `test_pipeline.py` | 487 | 6.102 |
| `test_gui.py` | 393 | 6.311 |
| `test_edicio.py` | 251 | 4.137 |
| `test_tempo_map.py` | 188 | 1.627 |
| `test_ancoratges.py` | 62 | 477 |
| `test_despatx_edicio.py` | 60 | 961 |
| `test_tempo_trams.py` | 55 | 591 |
| `test_rubato.py` | 32 | 199 |
| `test_mapa_tempo.py` | 21 | 152 |
| `test_exporta_audio.py` | 11 | 114 |
| `test_avalua_tempo.py` | 10 | 152 |
| `test_beats.py` | 10 | 88 |
| `test_audio_edit.py` | 9 | 133 |
| `test_tempo_ajust.py` | 3 | 25 |
| **Total** | **1.592** | **21.226** |

> El recompte és de **mètodes definits**, no d'una execució verificada. AGENTS
> afirma «1.592 tests, 1 omès»; ací no s'ha pogut confirmar el verd.

### 2.4 Documentació

- **53 `.md`** (919 KB, 13.093 línies).
- `CHANGELOG.md`: **197 KB**, **25 blocs** de versió (23 versions + `[Unreleased]`
  + `[No publicat]`; moltes «checkpoint» d'un dia).
- `ROADMAP_HISTORIA.md`: 66 KB; `docs/archive/AUDITORIA_REGLES.md`: 65 KB.
- `docs/`: 34 fitxers, dels quals **6** són del guiat (2 actius + 1 `.markdown`
  + 2 plans + 1 a `archive/`).
- Els enllaços interns **no** estan trencats (0 trobats), però **sí** ho estan
  les afirmacions (vegeu §3.6).

---

## 3. Troballes

> Severitat: **A** = alt (afecta comprensió o seguretat de dades), **M** =
> mitjà (deute que creix), **B** = baix (higiene).
> Cada troballa porta evidència (fitxer:línia) perquè l'agent la puga
> verificar abans de tocar res.

### 3.1 A-01 · El subsistema «Anàlisi guiat» v2/v3 és codi mort (ALT)

**Evidència (cadena de dependències):**

- `main.py:211` `class FilGuiaBpm` → només s'usa a `main.py:2140`, dins
  `_analisi_guitat`.
- `main.py:1955` `_analisi_guitat` → **cap crida** (només apareix a la
  docstring de `FilGuiaBpm`, línia 214, i a la definició).
- `main.py:1664` `_analisi_ancoratges` → **cap crida**; és l'únic usuari de
  `dialeg_ancoratges.DialegAncoratges` (`main.py:1685`).
- `main.py:1928` `_aplica_ancoratges` → només l'usa `_analisi_ancoratges`
  (1664) i `_analisi_guitat` (1955), tots dos morts.
- `main.py:2013–2437` tots els `_guia_*` (tanca diàlegs, pas 1, audita,
  segmenta, cancel·la, neteja…) → només es criden entre ells i des dels dos
  fluxos morts.
- `main.py:5383` `closeEvent` crida `_guia_cancel` si `self._guia`; com que
  `_guia` només s'ompli a `_analisi_guitat`, és codi vestigial.
- `dialegs.py:868` `DialegGuiaDownbeat` i `dialegs.py:940` `DialegGuiaBpm`
  (533 línies) → només s'usen als fluxos morts (`main.py:2003`, `2127`) i als
  tests (`test_gui.py:4965`, `5049`, `5704`, `5789`).
- `app/dialeg_ancoratges.py` (883 l.) → només l'importa `main.py:42` per a
  `_analisi_ancoratges` (mort).
- `app/ancoratges.py` (340 l.) → només l'importa `main.py:41` per a
  `_aplica_ancoratges` (mort) i `dialeg_ancoratges.py`.
- `tests/test_ancoratges.py` (477 l., 62 tests) → cobreix codi mort.

**Quantificació:**

| Bloc | Línies |
|---|---:|
| `dialeg_ancoratges.py` | 883 |
| `ancoratges.py` | 340 |
| `main.py` (FilGuiaBpm + `_analisi_*` + `_aplica_*` + `_guia_*`) | ≈ 704 |
| `dialegs.py` (`DialegGuiaDownbeat` + `DialegGuiaBpm`) | 533 |
| **Total** | **≈ 2.460** (9,2 % de l'app) |
| + tests | 477 |
| + docs | ≈ 65 KB |

**Impacte:** un agent nou llegeix `main.py` i `dialegs.py` i creu que hi ha
**quatre fluxos d'anàlisi** (F5, F6, F7, guiat v2, guiat v3) quan n'hi ha
**tres** (Analitza, Analitza BPM, marcadors). És el principal focus de
confusió del projecte.

**Recomanació:** eliminar (D1). El codi queda a l'historial; la funcionalitat
real ja està coberta pels marcadors (`docs/MARCADORS.md` diu literalment que
substitueix el guiat v2/v3).

### 3.2 A-02 · `ESQUEMA_UI.md` descriu el guiat v3 com a viu (ALT)

`docs/ESQUEMA_UI.md:56` diu que `self.b_guia` obri **`DialegAncoratges`** i
descriu tot el flux v3 (transport 1×–4×, delay, metre per ancoratge, «en
aplicar crea el mapa de tempo I les seccions»).

La realitat del codi:

- `main.py:645`: `self.b_guia.clicked.connect(self._obre_guia_rapida)`.
- `main.py:1907`: `_obre_guia_rapida` obri `dialeg_guia_rapida.DialegGuiaRapida`
  (5 pantalles **informatives**, sense tocar el model).
- `tests/test_gui.py:2279–2281` **fixa** este comportament: el test comprova
  que es crida `DialegGuiaRapida`, no `DialegAncoratges`.

`docs/ANALISI_GUIAT_v3.md:3` diu «codi conservat, **sense entrada d'UI**»,
mentre `ESQUEMA_UI.md:56` diu que el botó l'obri. **Les dues docs es
contradiuen entre si i amb el codi.**

El test d'ESQUEMA_UI (`test_gui.py:2283`) només comprova que les **accions de
menú** (`QAction`) apareguen al document; **no** valida la descripció dels
botons de barra. Per això la deriva passa desapercebuda.

### 3.3 A-03 · God objects i baixa cohesió (ALT)

- `main.py`: 5.130 línies, **225 mètodes** a `Finestra`, `__init__` de 432
  línies, `_crea_menus` 144, `boto` 169.
- `visor.py`: 5.905 línies, **227 mètodes**, `__init__` 427, `executa_edicio`
  186.
- `pipeline.py`: 1.954 línies, **88 funcions + 1 classe top-level** que van des de
  `run()` (subprocess) fins a `genera_guia_html()` i `segments_exactes()`.
- `dialegs.py`: 1.491 línies, **10 classes** de diàlegs independents (opcions,
  cerca, quantitza, mapa, tram, guia downbeat, guia BPM, tempo per trams,
  analitza BPM, revisió snap).

**Impacte:** qualsevol canvi de GUI obliga a navegar fitxers de 5.000 línies;
els conflictes de merge i les regressions són cars. El propi `ROADMAP.md:312`
ja ho reconeix («Refactor de `app/main.py` … No urgent»).

### 3.4 M-01 · `DEVELOPING.md` descriu un model que ja no existeix (MITJÀ-ALT)

`DEVELOPING.md:136–158` afirma:

- «els CSVs d'acords i estructura són la font de veritat» → **n'hi ha 4**.
- «el temps es guarda en segons al backend» → el mapa de tempo **barreja
  segons i BPM** (`mapa_tempo.csv`).
- «el mode compàs/BPM és només una vista derivada» → **fals**: és model
  persistent i exportable (regla #12).
- «no es barregen segons i BPM en la mateixa base de dades» → **contradiu
  directament** `mapa_tempo.csv` (`inici,fi,bpm,tipus,compassos`) i §13.
- «`Processa` extreu acords…» → l'acció actual és **Analitza**.
- «el visor regenerat els clips» → frase trencada i comportament antic.

A més, el mapa de mòduls (`DEVELOPING.md:268–291`) llista **20 mòduls** i
n'omet **19** dels 39 reals: `tempo_map`, `mapa_tempo`, `rubato`, `marcadors`,
`tempo_ajust`, `beats`, `bpm_unit`, `limits`, `audio_edit`, `exporta_audio`,
`projecte` (només al mapa ràpid), `graella`, `xifrat`, `panell_xifrat`,
`acord_audio`, `ancoratges`, `dialeg_ancoratges`, `dialeg_guia_rapida`,
`dialeg_bpm_marcadors`. També diu que `tempo.py` fa «prior de plateau» (concepte
antic) i esmenta `chordextract`/`temp/chordextract` i «annotator» (retirats).

### 3.5 M-02 · Versions incoherents (MITJÀ)

| Document | Versió que declara |
|---|---|
| `pyproject.toml:7` | `9.0.0` |
| `app/__init__.py:11` | `9.0.0` |
| `README.md:22` | `v9.0.0` |
| `ROADMAP.md:9` i `:51` | **`v0.8.0`** |
| `docs/ESTAT_MULTI_SO.md:3` | **`v0.7.0`** |
| `docs/CI_WORKFLOWS.md:3` | **`v0.8.0`** |
| `docs/PROVES_FUNCIONALS_3SO.md` | **`v0.7.0`** |

El `CHANGELOG` salta de **0.8.0** a **9.0.0** sense 1.x–8.x. No és un error
funcional, però confon qualsevol agent que busque «l'estat actual».

### 3.6 M-03 · El `CHANGELOG` té `[Unreleased]` davall de 9.0.0 (MITJÀ)

`CHANGELOG.md:6` obri `[9.0.0] — 2026-11-04`; `CHANGELOG.md:631` obri
`## [Unreleased]` amb entrades datades **2026-10-22**, és a dir, **més antigues**
que la versió que tenen a dalt. L'ordre cronològic està invertit i les entrades
d'octubre queden penjades en un bloc «no publicat» que en realitat sí que ho
està.

### 3.7 M-04 · Compatibilitats que la norma prohibeix (MITJÀ)

La decisió 2026-11-02 diu: «no es fan migracions automàtiques ni es mantenen dos
formats en paral·lel». Al codi hi ha:

| On | Què |
|---|---|
| `main.py:4167`, `main.py:4264` | lectura/migració de la carpeta vella **`AUTOCHORDS_<nom>/`** |
| `main.py:3750` + `4674` | `_assegura_wav()` crea **`<nom>_convertit.wav`** al costat de l'original |
| `ffmpeg.py:32` + `:242` | `SUFIX = "_convertit"` (el flux de projecte ja no l'usa) |
| `mapa_tempo.py:41`, `:92` | «compatible amb el model antic de 5 tuples» |
| `tempo_map.py:88` | `Tram` amb «interfície compatible amb `Clip(ini, fi, payload)`» |
| `tempo_map.py:850` | `clip_te_temps_sencer()` → **cap crida** |
| `pipeline.py:2101` | `llegeix_marcadors()` «manté la signatura antiga … per compatibilitat» |
| `pipeline.py:2068` | `NOM_MAPA_TEMPO = mapa_tempo.NOM_MAPA_TEMPO` (re-export) |

**Nota:** `mapa_tempo.NOM_CSV_TEMPO_ANTIC`/`NOM_CSV_COMPAS_ANTIC`
(`mapa_tempo.py:26–27`) **sí** que tenen un ús legítim: detectar el projecte
vell i **rebutjar-lo amb error clar** (`mapa_tempo.py:327`,
`pipeline.py:2176`). Això és l'excepció de seguretat, no una migració.

### 3.8 M-05 · `_convertit.wav` encara es pot crear (MITJÀ)

El flux documentat (`Obre àudio` → projecte) converteix **dins** `audio/` amb
`projecte.py:256` (`converteix_a_wav(..., dest=temporal)`).

Però `main.py:4674` (`executa()` / F5) fa:

```python
if not ffmpeg.es_wav_pcm16(wav):
    wav = self._assegura_wav(wav)      # sense `dest`
```

i `ffmpeg.py:241–242` genera `os.path.splitext(ruta)[0] + "_convertit.wav"`.
Si l'usuari escriu un MP3 a la casella de ruta i prem F5, **es crea un fitxer
al costat de l'original**, en contra del que diuen `AGENTS.md` i `README.md`
(«no deixa `<nom>_convertit.wav` al costat de l'original»).

### 3.9 M-06 · Model de 4 CSV vs «3 CSV» a AGENTS (MITJÀ)

Vegeu §1.3. `AGENTS.md` diu «els 3 CSV» i «S'escriu a cada edició: els 3 CSV».
`FLUX_DE_DADES.md:26` ja inclou `marcadors.csv`. Cal alinear AGENTS (o
documentar per què els marcadors no compten com a «model»).

### 3.10 M-07 · Codi mort puntual (MITJÀ)

Funcions definides que **no tenen cap referència** ni a l'app ni als tests
(verificat per recompte textual; els duunders i les sobrecàrregues de Qt
s'han exclòs):

| Fitxer:línia | Funció |
|---|---|
| `pipeline.py:1326` | `duplica_acord()` |
| `pipeline.py:1342` | `duplica_seccio()` |
| `plataforma.py:256` | `proces_viu()` |
| `tempo_map.py:850` | `clip_te_temps_sencer()` |
| `metronom.py:101` | `_ha_de_sonar()` |
| `metronom.py:112` | `_es_accent()` |
| `metronom.py:120` | `beats_a_temps()` |
| `main.py:3091` | `_idx_acord_del_cursor()` |
| `main.py:3108` | `_idx_seccio_del_cursor()` |
| `main.py:3125` | `_idx_tram_del_cursor()` |
| `ffmpeg.py:334` | `estira_a_wav()` (només tests) |
| `dialeg_ancoratges.py:69` | `durada_real()` (dins el mòdul mort) |

`metronom._ha_de_sonar` i `_es_accent` són especialment reveladors: la lògica
es va **inline** dins `mescla_metronom` (`_decideix`, al voltant de la línia
150) i els ajudants van quedar enrere.

### 3.11 M-08 · Duplicacions i derives de contracte (MITJÀ)

| Duplicació | Evidència | Risc |
|---|---|---|
| Parsing d'acords | `postproc.treu_baix` (`:27`) vs `xifrat.parteix_baix` (`:58`); `postproc.redueix` (`:32`) vs `xifrat.normalitza_qualitat`/`resta_qualitat` | dues interpretacions del mateix xifrat |
| `_lliure()` | `tempo_map.py:900` i `visor.py:986` | dues definicions del mateix predicat |
| `VELOCITATS` | `visor.py:2297` `(0.5, 0.75, 1, 1.25, 1.5, 2, 3)` vs `ffmpeg.py:262` `(0.5, 1/1.5, 1, 1.5, 2, 4)` | dos conjunts de velocitats amb el mateix nom |
| Rangs de BPM | `limits.py:3–4` `30–350` vs `tempo.py` `60–180` vs literals `60.0/180.0` a `ancoratges.py:193`, `dialeg_ancoratges.py:151`, `visor`, `marcadors` | dos rangs per a dos usos, però repetits en 5 llocs |
| Noms de mapa | `tempo_map.py` (motor) vs `mapa_tempo.py` (CSV) | confusió permanent |
| Escriptura CSV | `pipeline.escriu_atomic` (bona) vs closures `_escriu` a `mapa_tempo`, `pipeline` | acceptable, però repetició |

### 3.12 M-09 · CI només manual i cobertura mínima 65 % (MITJÀ)

- Els **6 workflows** són `workflow_dispatch` (ho confirma
  `docs/CI_WORKFLOWS.md:3–5`). **No hi ha CI en `push` ni en `pull_request`.**
- Els builds (`build-appimage.yml:120`, `build-macos.yml:235`,
  `build-windows.yml:198`) sí que executen la suite i `coverage report
  --fail-under=65`.
- `qualitat.yml` executa fuzzer i proves sintètiques **sense bloquejar**
  (`AGENTS.md` ho descriu com a «no bloquejant»).

**Impacte:** un canvi pot arribar a `main` sense que ningú execute els 1.592
tests fins que algú llance un build manual (potser hores després). Per a un
projecte amb regles d'or és un risc alt de regressió silenciosa.

### 3.13 M-10 · Binaris i codi de tercers al repositori (MITJÀ — decisió D2)

| Fitxer | Mida | Naturalesa |
|---|---:|---|
| `qm-vamp-plugins-linux64-local/qm-vamp-plugins.so` | 846,9 KB | binari Linux |
| `nnls-chroma-linux64-local/nnls-chroma.so` | 330 KB | binari Linux |
| `vamp_host_local` | 47 KB | **ELF x86-64** (magic `7F 45 4C 46`) |
| `codi_font_chordino/` | ~350 KB | codi font de Chordino amb `.hgignore`, `.hgtags`, `.travis.yml`, `sv-screenshot-nnls-chroma.png` (178 KB) |

`DEVELOPING.md:301–302` diu que **és una decisió conscient** («els binaris
natius de Linux SÍ es commitejen, són l'eina»). Per tant **no és un bug**, però
sí un risc: infla el repo, només cobreix Linux i el binari ELF pot quedar
desactualitzat respecte del codi font. Cal revisar-ho amb l'operador (D2), no
esborrar-ho per iniciativa pròpia.

### 3.14 B-01 · Referències a fitxers que no existeixen (BAIX)

| On | Referència | Realitat |
|---|---|---|
| `requirements.txt:2` | `acords_a_live.py` | no existeix |
| `requirements.txt:9` | `tests/test_requirements.py` | no existeix (els pins es comproven, si de cas, en altres tests) |
| `app/__init__.py:8` | `tests/test_pipeline_export.py::test_versio_app_coincideix_amb_pyproject` | el fitxer real és `tests/test_pipeline.py` |
| `AGENTS.md:182`, `:186` | regles «1–12» | `docs/REGLES_DE_LA_APP.md:9` diu «1–19» |
| `AGENTS.md:154` | «denominador 1–16» | `limits.py:7` `DENOMINADORS_ADMESOS = (2, 4, 8)` |
| `AGENTS.md` (taula) | «tests: 4 suites» | 14 mòduls `test_*.py` |
| `AGENTS.md` | `opencode.json`, `.opencode/README.md` | **no existeixen** al repo (són locals i gitignorats) |
| `DEVELOPING.md:34` | `chordextract`, `temp/chordextract`, «annotator» | eines retirades |

### 3.15 B-02 · `docs/REGLES_DE_LA_APP.md` té la capçalera mal comptada (BAIX)

La línia 9 diu «Les regles numerades **1–19**», però el document només té
**12 regles numerades** (`## 1` … `## 12`) i el **§13** amb subseccions
`13.1–13.9`. No hi ha regles 13–19 com a tals. AGENTS i `docs/README.md` diuen
«1–12 + §13», que és el correcte. Cal corregir la capçalera, no les regles.

### 3.16 B-03 · `concatena.py` es contradiu (BAIX)

`concatena.py:7–18` diu a la vegada:

- línia 12: «INCLOU … i `tests/`»;
- línia 14: «EXCLOU … `tests/`».

A més, tracta `docs/ANALISI_GUIAT.md` com a «Tier A» quan és un document
**substituït** (la seua pròpia capçalera ho diu). L'eina va néixer per a un
context d'LLM que ja no és el flux de treball.

### 3.17 B-04 · `ROADMAP.md` té notes crues al final (BAIX)

`ROADMAP.md:353–362` són apunts personals sense format («apunt usuari:
investigar madmom…», «exportar partitures amb silenci…»). El document és el
«full viu», però aquesta cua no és ni full ni història: hauria d'anar a
`ROADMAP_HISTORIA.md` o a una llista de desitjos.

### 3.18 B-05 · `main.py` encara migra carpetes antigues (BAIX-MITJÀ)

`main.py:4167` documenta la «convenció de l'app» `AUTOCHORDS_<nom>/` i
`main.py:4264` fa la migració. És exactament el tipus de compatibilitat que la
norma 2026-11-02 diu que **no** s'ha de mantindre. Si es conserva per UX (obrir
un WAV sol i trobar el projecte al costat), cal **documentar-ho com a
excepció**, no deixar-ho com a herència silent.

### 3.19 B-06 · `marcadors.csv` viu a `pipeline.py` (BAIX)

`marcadors.py` conté la lògica dels marcadors, però la persistència
(`desa_marcadors`, `llegeix_marcadors`, `llegeix_marcadors_tipus`) viu a
`pipeline.py:2075–2140`. Això obliga `visor.py` a importar `pipeline` per a
una cosa que no és pipeline. Cohesió millorable.

### 3.20 B-07 · `estira_a_wav` només l'usen els tests (BAIX)

`ffmpeg.estira_a_wav` (`:334`) és una envolupant de `_render` que només
apareix a `tests/test_ancoratges.py`. El codi de producció usa
`prepara_escolta` (`:316`). Si s'elimina el guiat, `estira_a_wav` i
`ffmpeg.VELOCITATS` queden sense ús de producció.

### 3.21 B-08 · Tests que fixen codi mort (BAIX)

`tests/test_ancoratges.py` (62 tests) i part de `tests/test_gui.py`
(`DialegGuiaBpm`, `DialegGuiaDownbeat`, `_analisi_guitat`) fixen un
comportament que **no és accessible des de la GUI**. Si s'elimina el guiat,
cal eliminar/reescriure estos tests; si es conserva, cal **re-connectar-lo** o
marcar-lo explícitament com a «no suportat».

### 3.22 A-04 · `vamp_params.py` hardcodeja les rutes Linux dels `.n3` (ALT)

`app/vamp_params.py:18–23` definix:

```python
PLUGINS = {
    "chords": ("nnls-chroma-linux64-local/nnls-chroma.n3", "chordino"),
    "structure": ("qm-vamp-plugins-linux64-local/qm-vamp-plugins.n3",
                  "qm-segmenter"),
}
```

Són rutes **Linux**. En canvi, `app/plataforma.py:40–49` ja té el mapa correcte
per SO (`nnls-chroma-win64-local`, `nnls-chroma-macos-local`, etc.) i
`pipeline.VAMP_DIRS` en surt. Però `vamp_params` no el fa servir.

**Conseqüència:** en un paquet de Windows o macOS, la carpeta
`nnls-chroma-linux64-local/` **no hi és** (els workflows empaqueten només la
carpeta del SO). `params_de("chords")` (`vamp_params.py:81–87`) no troba el
`.n3`, retorna `[]`, i el diàleg d'anàlisi (`dialegs.py:313` i `:413`) es queda
**sense els controls de Chordino**. No peta, però és una regressió funcional
silenciosa.

**Arreglament:** resoldre el `.n3` a partir de `plataforma.dirs_plugins()` (o
`pipeline.VAMP_DIRS`), buscant el fitxer dins la carpeta del SO; si no hi és,
retornar `[]` amb un avís al log. Test: mock de `plataforma.SO`/`PROJ_DIR` que
comprove que es troba el `.n3` de cada plataforma.

**Relació:** és el mateix problema de fons que D2 (binaris per plataforma) i
D3 (rutes duplicades en compte de centralitzades). Es pot arreglar en la fase 3
o en la fase 6.

---

## 4. Inventari de codi obsolet/mort (detall per a l'agent)

### 4.1 Cadena «guiat» (ordre d'eliminació segur)

```
main.py
├── import ancoratges as ancoratges_mod          (41)
├── import dialeg_ancoratges                     (42)
├── class FilGuiaBpm                             (211–330)
├── self._guia = {}                              (593)
├── self._guia_fil = None                        (594)
├── self.b_guia (botó)                           (636–645, 834)
├── _analisi_ancoratges                          (1664–1722)
├── _aplica_ancoratges                           (1928–1954)
├── _analisi_guitat                              (1955–2012)
├── _guia_tanca_dlg2 … _guia_netega              (2013–2437)
└── closeEvent → _guia_cancel                    (5383)
        │
        ├── dialeg_ancoratges.py (883)  ← només _analisi_ancoratges
        ├── ancoratges.py (340)         ← només _aplica_ancoratges + dialeg
        └── dialegs.py
            ├── DialegGuiaDownbeat      (868–939)
            └── DialegGuiaBpm           (940–1400)
```

**Fora de la cadena (no eliminar):**

- `dialeg_guia_rapida.py` (118) → **viu**: és el que obri el botó.
- `ffmpeg.prepara_escolta` → **viu**: el visor l'usa per a la velocitat de
  reproducció.
- `audio_out.py` → **viu**: reproducció.
- `marcadors.py` → **viu**: flux real.

### 4.2 Funcions sense cap crida (esborrar o justificar)

Vegeu la taula §3.10. Ordre recomanat: primer les que no toquen Qt
(`pipeline.duplica_*`, `plataforma.proces_viu`, `tempo_map.clip_te_temps_sencer`,
`metronom.*`), després les de `main.py` (`_idx_*`), i finalment
`ffmpeg.estira_a_wav` quan el guiat ja no hi siga.

### 4.3 Compatibilitats (eliminar o documentar com a excepció)

Vegeu §3.7. **No** eliminar la detecció de `tempo.csv`/`compas.csv`: és
l'excepció de seguretat que **rebutja** projectes vells sense tocar-los.

### 4.4 Eines i fitxers llegat

| Fitxer | Estat | Acció recomanada |
|---|---|---|
| `wav_a_wavs.py` | CLI pre-GUI; registrat a `pyproject.toml` | conservar si l'operador vol CLI; si no, retirar |
| `concatena.py` | context per a LLM; contradicció interna | retirar o arreglar (D4) |
| `AUTO_CHORDS_dev.sh` + `dev_reload.py` | dev | conservar |
| `codi_font_chordino/` | font de Chordino amb metadades Hg | netejar metadades o moure a build (D2) |
| `vamp_host_local` + `*-local/*.so` | binaris Linux | decisió D2 |
| `docs/analisis guiat v2.markdown` | document antic amb espai al nom | arxivar |
| `00PER FER/TORNAR A REVISAR AVANS AQUEST PLA.TXT` | 1 línia («V3? CADA 4 COMPASOS??») | buidar o arxivar |

---

## 5. Mapa de veritat documental

### 5.1 Canònics (no tocar sense ordre)

| Document | Per a què |
|---|---|
| `docs/REGLES_DE_LA_APP.md` | Contracte (regles 1–12 + §13) |
| `docs/FLUX_DE_DADES.md` | Model, cru i proteccions |
| `README.md` | Producte visible |
| `AGENTS.md` | Orientació d'agents (cal actualitzar-lo, no reescriure'l) |
| `CHANGELOG.md` | Historial (cal reordenar `[Unreleased]`) |

### 5.2 Actius però desactualitzats (cal corregir)

| Document | Problema |
|---|---|
| `DEVELOPING.md` | model de dades obsolet; mapa de mòduls incomplet; eines retirades |
| `ROADMAP.md` | v0.8.0; 1.452/1.563 tests; fases 0–6; diu que el guiat no té UI |
| `docs/ESQUEMA_UI.md` | descriu el guiat v3 com a viu |
| `docs/ESTAT_MULTI_SO.md` | v0.7.0 |
| `docs/CI_WORKFLOWS.md` | v0.8.0; no diu que no hi ha CI en push/PR |
| `docs/README.md` | índex amb documents que haurien d'anar a `archive/` |
| `AGENTS.md` | «3 CSV»; «4 suites»; denominadors 1–16; `opencode.json` absent |

### 5.3 Històrics que haurien d'anar a `docs/archive/`

- `docs/ANALISI_GUIAT.md` (substituït el 2026-10-20)
- `docs/ANALISI_GUIAT_v3.md` (stand by)
- `docs/analisis guiat v2.markdown`
- `docs/PLA_GUIAT_V2.md`
- `docs/PLA_GUIAT_V3.md`
- `docs/AUTODETECCIO_OPCIONS.md` (marcat HISTÒRIC al mateix fitxer)
- `docs/GRAELLA_PPQ_TEMPS.md` (si ja no descriu el model actual)
- `docs/guia_tecnica_downbeat_onsets_beats.md` (si és teòria, no contracte)

### 5.4 Soroll/duplicats

- `docs/ESQUEMA_UI_manual.html` / `.svg` (26 KB) vs `ESQUEMA_UI.html` / `.svg`
  (generats): cal aclarir quin és la font i quin és el manual.
- `docs/archive/PANELL_TIPUS_ACORD_mockup.png` (221 KB): imatge de disseny,
  no document tècnic.
- `CHANGELOG.md` amb 24 versions «checkpoint»: històric valuós, però poc
  navegable. No cal reescriure'l; sí mantenir-lo ordenat.

---

## 6. Pla d'acció per a l'agent de codi

> **Regla d'or del pla:** cada fase acaba amb **suite verda + `pyflakes` net**.
> Si la suite no està verda a la fase 0, **aturar-se i avisar** (norma
> d'AGENTS). No barrejar fases en un mateix commit.

### Fase 0 — Baseline i seguretat (obligatòria, 0,5 dia)

**Objectiu:** poder desfer qualsevol cosa.

1. Confirmar que es treballa sobre el **repositori real amb `.git`**. Si no,
   `git init`, `git add -A`, commit `baseline abans de la neteja` i
   `git tag abans-neteja-2026-11-05`.
2. Executar l'entorn i desar els logs:
   ```bash
   bash instal·la_local.sh
   QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests 2>&1 | tee baseline-tests.log
   .venv/bin/python -m pyflakes app/*.py tests/*.py 2>&1 | tee baseline-pyflakes.log
   .venv/bin/python -m coverage run --source=app -m unittest discover -s tests
   .venv/bin/python -m coverage report
   ```
3. Anotar: nombre de tests, omesos, fallades, cobertura, versió de Python i
   PyQt5.
4. Comprovar que `eines/genera_esquema_ui.py` i `eines/genera_inventari.py`
   deixen el repo net (`git status`).

**Criteri d'acceptació:** tag creat; suite verda; logs desats; `git status`
net després dels generadors.
**Si falla:** aturar i reportar a l'operador. **No** començar la fase 1.

### Fase 1 — Retirada del guiat v2/v3 (1–2 dies) · **D1 decidida: eliminar**

**Objectiu:** eliminar ~2.460 línies de codi mort i deixar una sola realitat.

> **D1 decidida el 2026-11-05:** s'elimina i es documenta. La funcionalitat es
> **reconstruirà de nou quan el nucli funcione correctament**; no es conserva
> codi mort «per si de cas». Deixar constància d'esta decisió al `CHANGELOG` i,
> si cal, a `ROADMAP.md`.
>
> **Per a l'agent:** en esta fase només es **retira i es documenta**. **No** has
> de reconstruir el flux guiat ara, ni deixar ginys a mitges, ni mantindre'l
> darrere d'un *flag*. La reconstrucció és una tasca **futura**, condicionada al
> fet que el nucli (anàlisi + edició + export) funcione i tinga la suite verda.

**Tasques (D1 = eliminar):**

1. Esborrar `app/dialeg_ancoratges.py` i `app/ancoratges.py` (a la paperera,
   mai `rm`).
2. A `app/main.py`, eliminar:
   - imports `ancoratges as ancoratges_mod` (41) i `dialeg_ancoratges` (42);
   - `class FilGuiaBpm` (211–330);
   - estat `self._guia` / `self._guia_fil` (593–594);
   - `_analisi_ancoratges` (1664–1722);
   - `_aplica_ancoratges` (1928–1954);
   - `_analisi_guitat` (1955–2012);
   - tots els `_guia_*` (2013–2437);
   - el bloc de `closeEvent` que crida `_guia_cancel` (5380–5390).
3. A `app/dialegs.py`, eliminar `DialegGuiaDownbeat` (868–939) i
   `DialegGuiaBpm` (940–1400).
4. **Decidir el botó** (recomanació: conservar-lo):
   - **Opció A (recomanada):** renombrar `b_guia` a **«Guia ràpida»**, mantenir
     `dialeg_guia_rapida.py` i el seu test. Canviar el tooltip perquè no diga
     «v3».
   - **Opció B:** eliminar el botó, `dialeg_guia_rapida.py` i el test
     `test_boto_analisi_guitat_muntat`.
5. Eliminar `tests/test_ancoratges.py` i els tests de `DialegGuia*` a
   `test_gui.py` (buscar `DialegGuia`, `_analisi_guitat`, `ancoratges`).
6. Moure a `docs/archive/` els 5 documents del guiat (§5.3) i actualitzar
   `docs/README.md`.
7. Actualitzar `docs/ESQUEMA_UI.md` (fila de `b_guia`) i **regenerar**
   `.html`/`.svg`:
   ```bash
   .venv/bin/python eines/genera_esquema_ui.py
   ```
8. Actualitzar `ROADMAP.md` §7 (traure el deute del guiat) i §8; `AGENTS.md`
   (estat actual); `CHANGELOG.md` (entrada nova, no reescriure història).
9. A `app/ffmpeg.py`: eliminar `VELOCITATS` (262) i `estira_a_wav` (334) si ja
   no els usa ningú. **No** eliminar `prepara_escolta`.

**Criteri d'acceptació:**

```bash
grep -RIn "ancoratges\|DialegGuia\|_analisi_guitat\|_analisi_ancoratges\|_guia_" app tests
# només ha de trobar: dialeg_guia_rapida, _obre_guia_rapida i el test del botó
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests
.venv/bin/python -m pyflakes app/*.py tests/*.py
git status   # net després de generar ESQUEMA_UI
```

**Risc:** mitjà. Es toca `main.py`, el fitxer més gran. Fer **un sol commit**
(petit i reversible) i recolzar-se en el tag de la fase 0.

### Fase 2 — Codi mort i compatibilitats (0,5–1 dia)

**Objectiu:** llevar les restes que no aporten comportament.

1. Esborrar les funcions de §3.10 (excepte les del guiat, ja fetes a la fase 1).
2. Eliminar la migració `AUTOCHORDS_<nom>/` (`main.py:4167`, `4264`) **o**
   documentar-la com a excepció d'UX a `docs/PROJECTES.md`.
3. Eliminar el camí `_assegura_wav` que crea `_convertit.wav`:
   - si el fitxer no és WAV, obrir el flux de projecte (conversió dins
     `audio/`), o
   - rebutjar amb un missatge clar («Obri l'àudio amb *Obre àudio* perquè es
     convertisca dins del projecte»).
4. Eliminar els shims de §3.7 que no siguen l'excepció de seguretat:
   `mapa_tempo` 5 tuples, `tempo_map` `Clip`, `pipeline` signatures antigues.
5. Actualitzar els tests que cobrien estos shims.

**Criteri d'acceptació:** suite verda; `grep` dels noms eliminats buit;
`_convertit.wav` ja no es crea en cap camí (test nou que ho provinga).

### Fase 3 — Unificació de constants i models (1 dia)

1. **Rangs de BPM:** afegir a `app/limits.py`:
   ```python
   BPM_MIN, BPM_MAX = 30.0, 350.0          # edició
   BPM_DETECT_MIN, BPM_DETECT_MAX = 60.0, 180.0  # detecció
   ```
   Substituir els literals `60.0/180.0` de `beats.py`, `visor.py`,
   `marcadors.py` (i dels mòduls del guiat si encara hi són).
2. **Velocitats:** si els dos conjunts són a propòsit, renombrar
   `VELOCITATS_REPRODUCCIO` (visor) i `VELOCITATS_ANALISI` (ffmpeg); si no,
   unificar.
3. **Noms de mapa:** renombrar `app/mapa_tempo.py` → `app/tempo_csv.py` (o
   `model_tempo.py`) perquè no es confonga amb `tempo_map.py`. Actualitzar tots
   els imports i docs. **No fusionar** els dos mòduls en esta fase.
4. **Parsing d'acords:** fer que `postproc.treu_baix`/`redueix` deleguen en
   `xifrat.parteix_baix`/`normalitza_qualitat`, o documentar per què no.
5. **`marcadors.csv`:** moure `desa_marcadors`/`llegeix_marcadors*` de
   `pipeline.py` a `marcadors.py` (o `projecte.py`) i actualitzar `visor.py`.

**Criteri d'acceptació:** cap literal `60`, `180`, `30`, `350` fora de
`limits.py`; suite verda; docs de constants actualitzats.

### Fase 4 — God objects (2–4 dies, per fases) · requereix **D3**

> **No** fer-ho tot de cop. **Una extracció per commit**, suite verda entre
> cada una. L'objectiu no és «fer-ho bonic», és reduir el cost de canvi.

1. `main.py`:
   - extreure `Finestra.__init__` (432 l.) en `_crea_estat`, `_crea_barres`,
     `_crea_transport`, `_crea_menus`, `_connecta_senyals`;
   - extreure el flux de projectes a `app/finestra_projectes.py` (mixín);
   - extreure el flux d'anàlisi a `app/finestra_analisi.py`;
   - extreure l'export a `app/finestra_export.py`.
2. `visor.py`:
   - extreure `Visor.__init__` (427 l.);
   - extreure `executa_edicio` (186 l.) a `app/visor_edicio.py`.
3. `pipeline.py`:
   - `app/pipeline_vamp.py` (subprocess i parseig de Vamp);
   - `app/pipeline_export.py` (CSV/WAV/HTML/manifest);
   - `app/pipeline_model.py` (normalització/cobertura/segments);
   - mantenir `pipeline.py` com a **façana** per no trencar imports.
4. `timeline.py`: ja està modularitzat; només extreure `mousePressEvent` (146
   l.) si cal.

**Criteri d'acceptació:** cap funció > 100 línies; `Finestra` i `Visor` <
3.000 línies; suite verda; **cap canvi de comportament** (els tests existents
són el contracte).

### Fase 5 — Reconciliació documental (1 dia)

1. `AGENTS.md`:
   - «3 CSV» → «4 CSV» (+ `marcadors.csv`);
   - «4 suites» → «14 mòduls de test»;
   - «denominador 1–16» → «2, 4 i 8» (o el que diga `limits.py`);
   - `opencode.json`/`.opencode` → «locals, no versionats»;
   - estat actual: fases 0–7 fetes (7 via rubato), 10/12 en curs, 8/9/11
     ajornades;
   - enllaç a este informe.
2. `docs/REGLES_DE_LA_APP.md:9`: «1–19» → «1–12 + §13».
3. `DEVELOPING.md`:
   - reescriure §«Lògica de producte» amb el model de 4 CSV, segons+BPM i
     marcadors;
   - completar el mapa de mòduls (afegir els 19 que falten);
   - traure `chordextract`/`temp/chordextract`/«annotator» i `Processa`.
4. `ROADMAP.md`:
   - v9.0.0; 1.592 tests; fases 0–7 fetes, 10/12 en curs, 8/9/11 ajornades;
   - §7 sense el deute del guiat;
   - moure les notes de §353–362 a `ROADMAP_HISTORIA.md`.
5. `CHANGELOG.md`: moure `[Unreleased]` (631) a dalt o dins de 9.0.0. **No**
   reescriure l'historial.
6. `docs/ESTAT_MULTI_SO.md` i `docs/CI_WORKFLOWS.md`: v9.0.0; afegir «no hi ha
   CI en push/PR».
7. `docs/README.md`: índex actualitzat; guiat a `archive/`.
8. `requirements.txt`: traure `acords_a_live.py` i `tests/test_requirements.py`
   (o crear el test).
9. `app/__init__.py`: `tests/test_pipeline.py::test_versio_app_coincideix_amb_pyproject`.
10. `concatena.py`: retirar o arreglar la contradicció includes/excludes.

**Criteri d'acceptació:** cap document de `docs/` contradiu el codi en els 6
punts crítics (versió, tests, model, guiat, denominadors, regles); enllaços
interns 0 trencats.

### Fase 6 — Higiene de repositori/build (0,5 dia) · requereix **D2**

1. Si D2 = moure binaris:
   - traure `vamp_host_local`, `*-linux64-local/*.so` del repo;
   - assegurar que els workflows els compilen/descarreguen (ja ho fan:
     `build-appimage.yml:97`, `build-macos.yml:204`, `build-windows.yml:90`);
   - afegir al `.gitignore` i documentar-ho a `DEVELOPING.md`.
2. `codi_font_chordino/`: traure `.hgignore`, `.hgtags`, `.travis.yml`,
   `sv-screenshot-nnls-chroma.png`, `chord.dictold`, `releasenotes-*`; o
   convertir-ho en descàrrega amb checksum.
3. Si es retiren `concatena.py`/`wav_a_wavs.py`, actualitzar `pyproject.toml` i
   `DEVELOPING.md`.

**Criteri d'acceptació:** repo < 4 MB (si D2 = moure); build dels 3 SO verd;
cap binari a `git status`.

### Fase 7 — CI i qualitat (0,5–1 dia)

1. Afegir `.github/workflows/qualitat-pr.yml` per a `push`/`pull_request` a
   `main`:
   - `pyflakes app/*.py tests/*.py`;
   - suite offscreen;
   - comprovar que `genera_esquema_ui.py` i `genera_inventari.py` no deixen
     diferències.
2. Pujar `--fail-under` de **65** a **70** (i després a 75 si és estable).
3. Fer que `qualitat.yml` siga **bloquejant** per a pyflakes/tests.
4. Documentar-ho a `docs/CI_WORKFLOWS.md`.

**Criteri d'acceptació:** un PR amb un test trencat falla; un PR amb
`ESQUEMA_UI` desactualitzat falla.

### Ordre i dependències

```
Fase 0 (obligatòria)
   │
   ├─ D1 ─→ Fase 1 ─→ Fase 2 ─→ Fase 3 ─→ Fase 5 ─→ Fase 6 (D2) ─→ Fase 7
   │                        │
   │                        └─→ Fase 4 (D3, en paral·lel)
   │
   └─ Si la suite no és verda: ATURAR.
```

**Estimació:** 6–10 dies d'un agent amb accés a l'entorn i a l'operador per a
les decisions.

---

## 7. Decisions de l'operador (D1 decidida; D2–D6 pendents)

| ID | Decisió | Opcions | Recomanació |
|---|---|---|---|
| **D1** | Guiat v2/v3 | **DECIDIDA (2026-11-05): eliminar i documentar**; es reconstruirà quan el nucli funcione | ✅ (a) — el codi queda a l'historial; els marcadors ja fan la feina |
| **D2** | Binaris Linux i `codi_font_chordino` | (a) quedar-se; (b) moure a artefactes de build; (c) híbrid amb checksum + verificació | **(c)** — vegeu §7.1 |
| **D3** | Refactor de `main.py`/`visor.py` | (a) ara; (b) després de la fase 10; (c) només `pipeline.py` | **(b)** — ajornar; vegeu §7.2 |
| **D4** | `concatena.py` i `wav_a_wavs.py` | (a) conservar; (b) retirar | **(b)** per a `concatena.py`; `wav_a_wavs.py` només si l'operador vol CLI |
| **D5** | Renombrar `mapa_tempo.py` | (a) sí; (b) no | **(a)** — evita confusió permanent amb `tempo_map.py` |
| **D6** | Botó «Anàlisi guiat» | (a) renombrar a «Guia ràpida»; (b) eliminar | **(a)** — la guia és útil i ja és el comportament real |

### 7.1 D2 · Binaris natius: context i instruccions per a l'agent

> **Per a l'agent:** esta secció és context i protocol, no una ordre
> d'execució. **No** esborres ni mous cap binari fins que l'operador trie D2.

**Què ha d'entendre l'agent abans de tocar res**

L'app no analitza l'àudio en Python. Delega en dos motors C++ de Vamp:
**Chordino** (acords) i el conjunt **QM** (estructura, BPM, compassos). Per
executar-los calen:

| Peça | Fitxer | Què és |
|---|---|---|
| Host | `vamp_host_local` (Linux) / `vamp_host_local.exe` (Windows) | executable que carrega els plugins i els passa l'àudio |
| Plugin d'acords | `nnls-chroma-linux64-local/nnls-chroma.so` | biblioteca compartida |
| Plugin QM | `qm-vamp-plugins-linux64-local/qm-vamp-plugins.so` | biblioteca compartida |
| Font | `codi_font_chordino/`, `eines/vamp_host.cpp` | codi C++ d'origen |
| Build | `eines/compila_vamp_host.sh`, `eines/compila_vamp_plugins.sh` | scripts de compilació |

Al repo **només** hi ha els binaris de **Linux**. Els de Windows/macOS es
compilen al CI (`build-windows.yml`, `build-macos.yml`) i s'empaqueten dins el
paquet; no es commitejen.

**Per què estan commitejats (i per què no és un bug)**

`DEVELOPING.md:301–302` ho documenta com a decisió conscient: l'objectiu és que
un `git clone` en Linux puga executar l'app sense compilador de C++, perquè
l'equip objectiu (Q9400, sense AVX) té un build fràgil i sovint offline.

**Risc real (el que l'agent ha de vigilar)**

1. **Binari desactualitzat:** si es canvia `eines/vamp_host.cpp` o
   `codi_font_chordino/`, el binari commitejat no es regenera sol. Un clon local
   pot executar codi vell.
2. **No auditable:** un diff binari no es pot revisar.
3. **Només Linux:** el repo és multiplataforma, però el binari commitejat no ho és.

**Decisió pendent (D2). No implementar sense ordre de l'operador.**

| Opció | Descripció | Quan triar-la |
|---|---|---|
| **A** | Deixar-ho com està | Si es prioritza zero fricció i no es toca el codi C++ |
| **B** | Traure els binaris del repo i construir-los/descarregar-los al build | Si es prioritza un repo net i reproduïble |
| **C** | Híbrid: deixar-los + `SHA256SUMS` + README + smoke test al CI | **Recomanada** |

**Si l'operador tria C, l'agent ha de fer exactament això:**

1. Crear `bin/README.md` (o `local/README.md`) que diga: què és cada binari, de
   quin commit/font ix, com es regenera i quina plataforma cobreix.
2. Generar `bin/SHA256SUMS` (o a l'arrel) amb els hashes dels binaris
   commitejats.
3. Afegir un job de CI (no bloquejant al principi) que:
   - execute `eines/compila_vamp_host.sh` i `eines/compila_vamp_plugins.sh` en
     Linux;
   - compare el hash del binari acabat de compilar amb el commitejat;
   - si no coincideix, avise (no trenque el build fins que l'operador ho decidisca).
4. Actualitzar `DEVELOPING.md` amb el procediment de regeneració.
5. **No** esborrar cap binari ni `codi_font_chordino/` en esta fase.

**Criteri d'acceptació (C):**

```bash
sha256sum -c bin/SHA256SUMS
# i el job de CI ha de passar en verd (o avisar, si és no bloquejant)
```

**Prohibicions per a l'agent:**

- No esborrar binaris «per netejar» sense D2 explícita.
- No canviar els noms de les carpetes `*-linux64-local`, `*-win64-local`,
  `*-macos-local`: `plataforma.py` i els workflows en depenen.
- No tocar `codi_font_chordino/` (és font de tercers; si cal, es documenta).

**Connexió amb A-04:** `vamp_params.py` hardcodeja les rutes Linux dels `.n3`.
Si es toca D2, aprofitar per a centralitzar-ho amb `plataforma.dirs_plugins()`.
Vegeu §3.22.

### 7.2 D3 · Refactor de `main.py`/`visor.py`: context i instruccions per a l'agent

> **Veredicte: no és bloquejant. No refactoritzar sense ordre expressa.**

L'app funciona i té 1.592 tests. Els *god objects* són un **cost de
manteniment**, no un defecte funcional. L'agent **no** ha d'aprofitar qualsevol
tasca per a refactoritzar fitxers sencers.

**Mètriques actuals (snapshot 2026-11-05):**

| Fitxer | Línies | Mètodes/funcions | Paper |
|---|---:|---:|---|
| `app/main.py` | 5.130 | 225 | finestra, flux, projectes, anàlisi |
| `app/visor.py` | 5.905 | 227 | visor, edició, undo/redo, reproducció |
| `app/pipeline.py` | 1.954 | 88 funcions + 1 classe | backend d'anàlisi/export |

**Ordre d'extracció permés (de menys a més risc):**

1. **`pipeline.py` → 3 mòduls** (backend pur, sense Qt). És el més segur perquè
   no depén de la GUI i té tests. És l'únic refactor aprovat per a un guany ràpid.
2. **`Finestra.__init__` → blocs `_crea_*`** (menús, barra, estat, connexions).
   Canvi mecànic, sense alterar comportament.
3. **`Visor.__init__` → blocs** (ona, llistes, transport, snap).
4. **`executa_edicio`: NO tocar.** És el cor de l'edició; el risc de regressió
   no compensa sense una raó funcional i tests que el fixen.

**Criteri objectiu (per a l'agent):**

Refactoritzar un fitxer **només** si es compleixen les dos:

- (a) supera les **3.000 línies**; **i**
- (b) s'ha de fer un **canvi funcional** en eixe fitxer.

Refactoritzar una funció **només** si supera les **150 línies** i s'ha de
modificar. En qualsevol altre cas: **no tocar**.

**Regles de seguretat:**

- Un refactor = un commit **sense canvi de comportament**. Si cal canviar
  comportament, va en un altre commit.
- La suite ha d'estar verda **abans i després** de cada extracció.
- No barrejar refactor amb arreglar bugs ni amb canvis de UI.
- Si una extracció fa créixer el diff per damunt del que es pot revisar, aturar
  i dividir.

**Criteri d'acceptació:**

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests
.venv/bin/python -m pyflakes app/*.py tests/*.py
# i el diff no ha de canviar comportament observable
```

**Conclusió per a l'agent:** D3 = **ajornar**. Només `pipeline.py` si l'operador
ho demana. `main.py`/`visor.py` es toquen quan la fase 10 estiga tancada i el
producte ho requerisca.

---

## 8. Com verificar-ho tot (comandes de referència)

```bash
# Entorn
bash instal·la_local.sh

# Suite (ha d'estar SEMPRE verda)
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests

# Estil
.venv/bin/python -m pyflakes app/*.py tests/*.py

# Cobertura
.venv/bin/python -m coverage run --source=app -m unittest discover -s tests
.venv/bin/python -m coverage report

# Generadors (han de deixar el repo net)
.venv/bin/python eines/genera_esquema_ui.py
.venv/bin/python eines/genera_inventari.py
git status --short

# Smoke de l'app
AUTO_CHORDS_SMOKE=1 QT_QPA_PLATFORM=offscreen .venv/bin/python -m app.main
```

**Definició de «fet» per a qualsevol fase:**

1. Suite verda (1.592 tests o el recompte actualitzat).
2. `pyflakes` net.
3. `git status` net després dels generadors.
4. Cap referència nova a codi eliminat.
5. Documentació actualitzada en el mateix commit.
6. Un sol commit per fase, missatge en català, **sense push**.

---

## 9. El que està bé i **no** s'ha de tocar

Per evitar que l'agent «refactoritze de més»:

- **Les regles d'or** (`docs/REGLES_DE_LA_APP.md`) i els seus tests. No es
  canvien sense consentiment explícit de l'operador.
- **L'escriptura atòmica** (tmp + fsync + replace) de `pipeline.escriu_atomic`
  i dels CSV.
- **La política de no-retrocompatibilitat** (decisió 2026-11-02), amb
  l'excepció de seguretat: un projecte vell es **rebutja sense tocar-lo**.
- **La higiene dels tests** (`tests/_temporals.py`, `tests/_qt_neteja.py`).
- **La modularització del timeline** (`timeline_base/_items/_layers`): ja està
  ben feta; no cal tocar-la.
- **Els pins de dependències** (`numpy==1.26.4`, PyQt5 per plataforma):
  són deliberats per al Q9400 sense AVX/SSE4.2 i per a macOS 10.13.
- **La documentació en català** i els comentaris explicatius.
- **Els 3 fluxos reals** d'anàlisi (Analitza, Analitza BPM, marcadors).

---

## Annex A — Evidències (comandes executades)

Totes les xifres d'este informe ixen d'estes comprovacions (PowerShell, sobre
la còpia local):

```powershell
# Recompte de línies per mòdul
Get-ChildItem app -Filter *.py | ForEach-Object {
  $n = (Get-Content $_.FullName | Measure-Object -Line).Lines
  "{0,6} {1}" -f $n, $_.Name
} | Sort-Object -Descending

# Recompte de tests
(Select-String -Path tests/test_*.py -Pattern '^\s*def test_').Count
# → 1592

# Mides
(Get-ChildItem . -Recurse -File | Where-Object { $_.FullName -notmatch '\\\.git\\' } |
  Measure-Object Length -Sum).Sum / 1MB
# → 5,79 MB

# Magic del binari
[System.IO.File]::ReadAllBytes("vamp_host_local")[0..3]
# → 7F 45 4C 46  (ELF)

# Graf d'imports i funcions sense crides
# (script ad hoc de recompte textual; resultats a §3.10)
```

**Limitacions:**

- No s'ha executat la suite (no hi ha Python a l'equip d'esta sessió). El
  recompte de 1.592 és de **mètodes definits**, no de tests verds.
- El recompte de «codi mort» és **textual** (cap referència al codi ni als
  tests). En este projecte no hi ha `getattr`/reflexió sobre estos noms, però
  l'agent ha de **confirmar-ho amb `pyflakes` i la suite** abans d'esborrar.
- Les línies citades són del **snapshot 2026-11-05**; si el codi canvia,
  cal re-localitzar-les pel nom de la funció/classe.

---

## Annex B — Mapa ràpid de responsabilitats (per a l'agent)

| Vols tocar… | Ves a… |
|---|---|
| Finestra, menús, barres, flux d'usuari | `app/main.py` (`Finestra`) |
| Visor, ona, llistes, undo/redo, reproducció | `app/visor.py` (`Visor`) |
| Timeline, snap, graella visual | `app/timeline*.py` |
| Mapa de tempo/compàs (motor) | `app/tempo_map.py` |
| Serialització del mapa (`mapa_tempo.csv`) | `app/mapa_tempo.py` |
| Rubato | `app/rubato.py` |
| Marcadors | `app/marcadors.py` + E/S a `app/pipeline.py` |
| Detecció de BPM (DSP) | `app/tempo.py` |
| Orquestració de motors de beats | `app/beats.py` |
| Unitat de BPM | `app/bpm_unit.py` |
| Límits | `app/limits.py` |
| Acords: anàlisi crua i neteja | `app/pipeline.py` + `app/postproc.py` |
| Xifrat canònic | `app/xifrat.py` |
| Partitura | `app/partitura.py` |
| Projecte `.acproj` | `app/projecte.py` |
| Edició d'àudio | `app/audio_edit.py` |
| Export d'àudio | `app/exporta_audio.py` |
| Àudio (reproducció) | `app/audio_out.py` |
| Metrònom | `app/metronom.py` |
| FFmpeg (import/velocitat) | `app/ffmpeg.py` |
| Plataforma | `app/plataforma.py` |
| Config/estat | `app/config.py` |
| Diàlegs | `app/dialegs.py` + `dialeg_*.py` |
| Tema/icones | `app/theme.py` + `app/icones.py` |

---

## Annex C — Glossari de fitxers llegat

| Nom | Què era | Estat |
|---|---|---|
| `ancoratges.py` | Model d'ancoratges humans (guiat v3) | **mort** |
| `dialeg_ancoratges.py` | Diàleg del guiat v3 | **mort** |
| `dialeg_guia_rapida.py` | Guia informativa de 5 passos | **viu** |
| `DialegGuiaDownbeat` / `DialegGuiaBpm` | Diàlegs del guiat v2 | **morts** |
| `FilGuiaBpm` | Fil de detecció del guiat v2 | **mort** |
| `_analisi_guitat` | Entrada del guiat v2 | **mort** |
| `_analisi_ancoratges` | Entrada del guiat v3 | **mort** |
| `wav_a_wavs.py` | CLI pre-GUI | llegat |
| `concatena.py` | Concatenador per a LLM | llegat |
| `AUTOCHORDS_<nom>/` | Convenció de carpeta antiga | compatibilitat |
| `<nom>_convertit.wav` | Conversió al costat de l'original | compatibilitat |
| `tempo.csv` / `compas.csv` | Model de tempo antic | **rebutjat** amb error clar |
| `clip_te_temps_sencer()` | Ajudant del contracte antic | **mort** |
| `estira_a_wav()` | Envolupant de `_render` | només tests |

---

## 10. Revisió independent (Segona opinió tècnica — 2026-11-05)

> **Auditor independent:** Antigravity (Advanced Agentic Coding)  
> **Objectiu:** Avaluació crítica, contrast empíric, verificació de dades i identificació de punts cecs de l'informe d'auditoria tècnica precedent.  
> **Principi d'intervenció:** Segona opinió professional amb perspectiva d'enginyeria d'àudio, arquitectura de sistemes i prevenció de regressions en DAWs.

### 10.1 Verificació empírica de dades i mètriques (Fact-Checking)

S'ha contrastat el contingut de l'auditoria directament contra el codi font i la documentació del repositori.

1. **Subestimació del volum real de codi (desviació del snapshot):**
   - L'auditoria reportava `main.py` amb 5.130 línies; **el recompte real al disc és de 5.502 línies** (+372 línies).
   - L'auditoria reportava `visor.py` amb 5.905 línies; **el recompte real al disc és de 6.311 línies** (+406 línies).
   - L'auditoria reportava `pipeline.py` amb 1.954 línies; **el recompte real al disc és de 2.257 línies** (+303 línies).
   - **Motiu de la diferència:** El snapshot de l'auditor no va comptabilitzar completament les darreres incorporacions del 2026-11-04 (beats QM, contracte de beats per Snap, 'Ajusta BPM al compàs', selecció centrada de scroll a les llistes i gestió de l'offset sense pèrdua de precisió).
   - **Conclusió:** El problema dels *god objects* és **encara més sever** del que exposava l'auditoria: només `visor.py` i `main.py` sumen **11.813 línies** (en lloc de 11.035).

2. **Error de diagnòstic de l'auditor sobre l'entorn Python:**
   - L'auditoria afirmava a la capçalera i a l'Annex A que «l'equip d'aquesta sessió no té Python instal·lat». **Això és un fals negatiu de l'auditor.**
   - S'ha verificat empíricament l'existència d'un entorn Python complet i operatiu a la màquina:
     - Intèrpret pare: `C:\Users\CABINA_NEAPOLIS\Desktop\CARPETA IA\entorn\Python311\python.exe` (Python 3.11.9).
     - Entorn virtual del projecte: `.venv\` (`.venv\Scripts\python.exe`).
     - Dependències essencials instal·lades a `.venv`: **`PyQt5`**, **`numpy`** i **`sounddevice`**.
   - **Implicació:** L'aplicació es pot arrencar a Windows directament amb `.\.venv\Scripts\python.exe -m app.main`.

3. **Validació del codi mort del guiat v2/v3 (A-01):**
   - **Confirmació total:** Verificat línia per línia a `app/main.py`. La classe `FilGuiaBpm` (l. 211), els mètodes `_analisi_ancoratges` (l. 1664), `_aplica_ancoratges` (l. 1928), `_analisi_guitat` (l. 1955) i tots els auxiliars `_guia_*` (l. 2013–2437) estan completament desconnectats de la GUI.
   - El botó `b_guia` (l. 636) es connecta exclusivament a `self._obre_guia_rapida` (l. 645), que obre `DialegGuiaRapida` (només informatiu).
   - Els diàlegs `DialegGuiaDownbeat`, `DialegGuiaBpm` i `DialegAncoratges` són efectivament codi mort de producció.

3. **Validació de la deriva documental (A-02, M-01, B-01, B-02):**
   - **Confirmació total:**
     - `docs/ESQUEMA_UI.md:56` afirma que el botó obre `DialegAncoratges` (fals en codi).
     - `docs/REGLES_DE_LA_APP.md:9` diu «1–19» a la capçalera (quan només hi ha 12 regles + §13).
     - `DEVELOPING.md:136` manté la teoria superada de «2 CSVs» i «no es barregen segons i BPM».
     - `app/limits.py:7` fixa `DENOMINADORS_ADMESOS = (2, 4, 8)`, mentre `AGENTS.md:154` diu «denominador 1–16».

4. **Validació del bug latent multiplataforma a `vamp_params.py` (A-04):**
   - **Confirmació total i greu:** `app/vamp_params.py:18–23` té rutes absolutament codificades per a Linux (`nnls-chroma-linux64-local/...` i `qm-vamp-plugins-linux64-local/...`). A Windows i macOS no troba mai els descriptors `.n3`, degradant la funcionalitat d'inspecció de paràmetres de Chordino sense llençar cap excepció visible.

5. **Validació de les funcions orfes (M-07):**
   - `pipeline.duplica_acord` i `pipeline.duplica_seccio`: verificat que `visor.py` duplica mitjançant `pipeline.duplica_bloc_clips` i `pipeline.duplica_bloc_seccions`.
   - `metronom._ha_de_sonar`, `metronom._es_accent`, `metronom.beats_a_temps`: verificat que `mescla_metronom` reimplementa la decisió de clic a la closure interna `_decideix` (l. 184).

---

### 10.2 Avaluació crítica de les decisions proposades (D1 a D6)

| ID | Proposta de l'auditoria | Avaluació de la revisió independent | Veredicte revisat |
|---|---|---|---|
| **D1** | Eliminar guiat v2/v3 (~2.460 línies) | **Molt d'acord.** Mantenir codi mort genera entropia cognitiva. **Matís important:** cal comprovar que la lectura del `.acproj` (projecte antic o desat) no falli si troba la clau `ancoratges` a `opcions` (garantir desat/càrrega tolerant de diccionari). | ✅ **Executar a la Fase 1.** |
| **D2** | Binaris Linux: Opció C (híbrid amb checksums + CI) | **Discrepància parcial.** La solució C proposada (regenerar i comparar al CI) és feixuga per a un entorn de màquina vella (Q9400). **Recomanació independent:** Mantenir els binaris de Linux necessaris per a l'execució directa, però **purgar immediatament** la carpeta `codi_font_chordino/` (substituir per l'enllaç al commit upstream i instruccions de compilació a `eines/`) i retirar la captura PNG de 178 KB. | ⚠️ **Simplificar D2 (opció pràctica).** |
| **D3** | God objects: Ajornar refactor de `main.py` i `visor.py` | **Discrepància estratègica.** Ajornar-ho tot és còmode però perillós: continuen creixent (ja superen les 5.500 i 6.300 línies). **Recomanació independent:** Aplicar una **política de congelació estricta**: cap mètode nou a `Finestra` ni a `Visor`. Modularitzar de seguida el backend `pipeline.py` (2.257 línies, sense dependències Qt) en `pipeline_vamp.py` i `pipeline_export.py`. | ⚠️ **D3 híbrid: congelar GUI + extreure `pipeline.py`.** |
| **D4** | Retirar `concatena.py` i `wav_a_wavs.py` | **Molt d'acord** pel que fa a `concatena.py` (antiquat amb eines com Antigravity/OpenCode). Per a `wav_a_wavs.py`: comprovar `pyproject.toml` (`[project.scripts]`); si es retira, cal eliminar el punt d'entrada. | ✅ **Retirar `concatena.py`; consultar `wav_a_wavs.py`.** |
| **D5** | Renombrar `mapa_tempo.py` | **Molt d'acord.** La col·lisió de noms `tempo_map.py` (motor) vs `mapa_tempo.py` (CSV) és la confusió més freqüent dels agents. El nom recomanat és `tempo_csv.py`. | ✅ **Aprovat.** |
| **D6** | Renombrar botó «Anàlisi guiat» a «Guia ràpida» | **Molt d'acord.** Reflecteix exactament la UI actual (`DialegGuiaRapida`). | ✅ **Aprovat.** |

---

### 10.3 Punts cecs no detectats (o infravalorats) per l'auditoria original

Durant aquesta revisió independent s'han detectat aspectes que l'auditoria original va ometre o no va calibrar prou:

1. **Impacte del canvi del 2026-11-04 (Contracte de beats sencers per Snap QM):**
   - El canvi que permet clips de BPM/compàs que no completin un compàs enter si contenen almenys un beat de graella QM va introduir dependències d'acoblament molt fortes entre `tempo_map.py`, `beats.py` i `timeline_base.py`.
   - L'auditoria tracta aquest canvi com a fet, però no adverteix que les eines d'edició (nudge, retall, estirament) necessiten una revisió específica per verificar que cap gest manual produeixi fragments orfes sub-beat sense avís.

2. **Risc de falsos positius per slots de Qt per reflexió:**
   - En netejar mètodes aparentment orfes a `Finestra` o `Visor`, cal tenir present que PyQt5 pot connectar automàticament slots que segueixin el patró `on_<objectName>_<signal>` o tractar mètodes d'esdeveniments (`closeEvent`, `paintEvent`, `dragEnterEvent`). L'auditoria textual no filtrava explícitament aquesta casuística.

3. **Fragilitat del desenvolupament en entorns híbrids (sense Python/Git local):**
   - L'auditoria assumeix a la Fase 0 que tothom pot executar `.venv/bin/python` o `git tag`.
   - En entorns com el d'aquesta màquina de suport (on no hi ha Python instal·lat ni `.git`), **aquest document `.md` és el paquet d'entrega física**.
   - Per tant, el pla d'acció ha de diferenciar explícitament:
     - **Fase de disseny i contracte (offline/estàtic):** es pot realitzar sense entorn d'execució.
     - **Fase d'execució i commit:** s'ha de dur a terme exclusivament a la màquina de l'operador que disposa de Python, el venv amb dependències d'àudio i el repositori Git principal.

4. **Incoherència de l'indicador TAP:**
   - A la barra de transport conviuen la tecla `T` (TAP) i els botons de divisió/multiplicació de BPM. L'auditoria no esmenta si el comportament del TAP respon a clips seleccionats o al tempo global de transport en projectes multitempo. Cal assegurar que la documentació del TAP a `ESQUEMA_UI.md` sigui unívoca.

---

### 10.4 Pla d'acció optimitzat (prioritats recomanades)

Per optimitzar el temps d'enginyeria i evitar regressions, es recomana reordenar lleugerament les fases:

1. **Bloc 1 — Seguretat i higiene documental (Ràpid i d'alt impacte):**
   - Reconciliació documental (4 CSVs a `AGENTS.md` i `DEVELOPING.md`, versions a 9.0.0, regles 1-12+§13 a `REGLES_DE_LA_APP.md`, límits de compàs a `limits.py`). Això deixa el mapa net per a qualsevol desenvolupador.
   - Resolució del bug A-04 (`app/vamp_params.py` per a Windows/macOS mitjançant `plataforma.dirs_plugins()`).

2. **Bloc 2 — Codi Mort (sense impacte funcional en l'app viva):**
   - Retirada definitiva del guiat v2/v3 i els seus diàlegs orfes (Fase 1 de l'auditoria).
   - Neteja de les funcions orfes sense crides de §3.10 i shims de compatibilitat (Fase 2 de l'auditoria).

3. **Bloc 3 — Modularització de backend i Constants:**
   - Unificació de constants a `limits.py` i canvi de nom `mapa_tempo.py` → `tempo_csv.py` (Fase 3).
   - Modularització de `pipeline.py` (2.257 línies) en `pipeline_vamp.py` i `pipeline_export.py` (deixant `main.py`/`visor.py` congelats de noves addicions).

4. **Bloc 4 — CI i Repositori:**
   - Execució de les Fases 6 i 7 a la màquina principal amb entorn de proves complet.

---

**Fi de la revisió independent.** Aquesta anàlisi complementa i valida el diagnòstic estructural de l'auditoria del 2026-11-05, aportant refinaments operatius per a la seva execució segura.
