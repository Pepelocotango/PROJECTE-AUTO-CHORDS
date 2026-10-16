# Informe d'incoherències — PROJECTE AUTO CHORDS

> **Data:** 2026-10-16 · **Autor:** agent `OC` (opencode) · **Tipus:** auditoria de **només lectura**
>
> **Abast:** coherència interna del **codi** i de la **documentació**, i contradiccions
> entre tots dos. **No s'ha modificat cap fitxer existent**; aquest informe és un fitxer **nou**.
>
> **Estat del repo en fer l'auditoria:** branca `main`, HEAD `102d18e`
> («Ctrl+Shift+arrossegar una SECCIO…»), **net** (sense canvis pendents),
> `origin/main` endarrerit **28 commits** (tot local, cap push).
>
> **Línia base verificada:** `python -m unittest discover -s tests`
> → **871 tests** (1 skip), OK · `pyflakes` net (segons ROADMAP) ·
> eines MCP = **51** (`_TOOLS`) · `xifrat.TAULA_TIPUS` = **80** · `main.py` = 3.043 línies ·
> `visor.py` = 3.097 línies · `Finestra` = 138 mètodes · versió `0.7.0`.

---

## Resum

| # | Tipus | Severitat | On |
|---|-------|:---------:|----|
| 1 | Enllaços a docs **arxivats/fosos** (6 refs vives) | 🟠 | AGENTS, LLICENCIES_TERCERS, QM_VAMP, REGLES, CI_WORKFLOWS, ESTAT_MULTI_SO, ESQUEMA_UI, ROADMAP_HISTORIA, requirements-build.txt, empaqueta_portable.sh |
| 2 | **Recompte de tests** contradictori (633 / 857 vs 871 reals) | 🔴 | AGENTS.md, ROADMAP.md |
| 3 | Panell de tipus: **62 vs 80** | 🔴 | ROADMAP.md, TIPUS_XIFRAT_ACORDS.md, CHANGELOG.md |
| 4 | **Tag `v0.7.1`** sense versió/bump equivalent | 🟠 | git + CHANGELOG.md |
| 5 | Línies de `main.py`/`visor.py` desfasades | 🟡 | ROADMAP.md, ROADMAP_HISTORIA.md |
| 6 | **Què inclouen els paquets** (contradicció) | 🔴 | CI_WORKFLOWS.md vs DEVELOPING/AGENTS + workflows |
| 7 | **Projectes per MCP**: «pendent» vs «FET» | 🔴 | PROJECTES.md vs MCP_AUTO_CHORDS.md + codi |
| 8 | **▶ Escoltar**: «desactivat» vs «actiu» dins mateix CHANGELOG | 🟠 | CHANGELOG.md |
| 9 | `Am/G` → `Am-G` (erroneu; canònic = `Am_G`) | 🟠 | MCP_AUTO_CHORDS.md, SEGURETAT.md |
| 10 | «**Obre WAV…**» vs «**Obre àudio…**» | 🟡 | PROVES_FUNCIONALS_3SO.md, PROJECTES.md |
| 11 | «plugin **aubio**» encara com a font de BPM actual | 🟡 | GRAELLA_PPQ_TEMPS.md |
| 12 | Paràmetres Chordino: descrit via `sonic-annotator -t` (avui `--param`) | 🟡 | AUTODETECCIO_OPCIONS.md |
| 13 | Comentari de test sobre regles d'or erroni | 🟡 | tests/test_regles_or.py |
| 14 | Capçalera `ESQUEMA_UI.md` amb data antiga | 🟡 | docs/ESQUEMA_UI.md |
| 15 | Errata «Obertura tecnolítica» | 🟡 | ROADMAP_HISTORIA.md |

---

## 1. Referències a documentació moguda/arxivada (enllaços trencats)

Durant l'agost-octubre de 2026 diversos docs s'han **fusionat o arxivat** a `docs/archive/`,
però les referències des d'altres fitxers **no s'han actualitzat**. Són enllaços que
**no resolen** (fitxer inexistent a la ruta citada).

### 1.1 `docs/PORTABILITAT.md` → ara a `docs/archive/PORTABILITAT.md`

| Fitxer:línia | Text |
|---|---|
| `AGENTS.md:158` | `` `docs/PORTABILITAT.md` · `docs/CI_WORKFLOWS.md` — els 3 paquets i el CI. `` |
| `LLICENCIES_TERCERS.md:50` | `` …`eines/libreries_natives.sh` i `docs/PORTABILITAT.md`… `` |
| `docs/QM_VAMP.md:107` | `` …Detall: `docs/PORTABILITAT.md` §0. `` |
| `docs/CI_WORKFLOWS.md:152` | `` Detall per SO: …`docs/PORTABILITAT.md`,… `` |
| `docs/ESTAT_MULTI_SO.md:6` | `` …`docs/PORTABILITAT.md` (Linux), `docs/PORTABILITAT_WINDOWS.md`,… `` |
| `eines/empaqueta_portable.sh:109` | `Mes informacio: docs/PORTABILITAT.md dins aquesta carpeta.` |

> ✏️ **Correcció proposada:** canviar la ruta a `docs/archive/PORTABILITAT.md` (o, als
> llocs on es vol el doc **viu**, apuntar a `docs/ESTAT_MULTI_SO.md`, que és
> l'equivalent actiu). `ESTAT_MULTI_SO.md:7` ja fa servir bé el prefix `docs/archive/`
> per a `PLANIFICACIO_MACOS.md` — **dins el mateix document** d'una línia per l'altra.

### 1.2 `docs/PLANIFICACIO_MACOS.md` → ara a `docs/archive/PLANIFICACIO_MACOS.md`

| Fitxer:línia | Text |
|---|---|
| `docs/REGLES_DE_LA_APP.md:69` | `→ PLANIFICACIO_MACOS.md · verificat al CI (eines/verifica_minos_macos.py).` |
| `docs/CI_WORKFLOWS.md:153` | `` `docs/PORTABILITAT_WINDOWS.md`, `docs/PLANIFICACIO_MACOS.md`. `` |

### 1.3 `docs/AUBIO_TEMPO.md` → ara a `docs/archive/AUBIO_TEMPO.md`

| Fitxer:línia | Text |
|---|---|
| `docs/QM_VAMP.md:4` | `` …`docs/AUTODETECCIO_OPCIONS.md` i `docs/AUBIO_TEMPO.md`. `` |
| `docs/ESQUEMA_UI.md:378` | `` - `docs/AUBIO_TEMPO.md` — **[històric]** plugin d'aubio…, retirat. `` |

> ⚠️ `DEVELOPING.md:251` **sí** que ho fa bé: `archive/AUBIO_TEMPO.md (històric)`.

### 1.4 `docs/MOTOR_AUDIO_SO.md` (fusionat dins `docs/AUDIO.md`)

| Fitxer:línia | Text |
|---|---|
| `ROADMAP_HISTORIA.md:116` | `` i `docs/MOTOR_AUDIO_SO.md`. `` |

*(`docs/AUDIO.md:3` també diu «fusió de `PLAY.md` + `MOTOR_AUDIO_SO.md`»: és una **nota
històrica** acceptable, però els fitxers ja no existeixen.)*

### 1.5 `docs/AUDITORIA_PRODUCCIO.md` → ara a `docs/archive/AUDITORIA_PRODUCCIO.md`

| Fitxer:línia | Text |
|---|---|
| `requirements-build.txt:12` | `# Vegeu docs/AUDITORIA_PRODUCCIO.md (A.2/D.1).` |

> Els workflows **sí** que escriuen bé `docs/archive/AUDITORIA_PRODUCCIO.md`
> (p. ex. `build-windows.yml:112`, `build-macos.yml:90`).

> ℹ️ **No comptabilitzades com a error** les mencions dins `CHANGELOG.md`
> (728, 940, 1485…) ni `docs/archive/*`: són **registre històric** i
> `ROADMAP_HISTORIA.md:745` diu explícitament que es conserven.

---

## 2. Xifres i versions desfasades

### 2.1 Recompte de tests 🔴

La suite real, avui: **871 tests** (1 skip). Els docs en donen **dues xifres diferents
i totes dues velles**:

| Fitxer:línia | Diu | Real |
|---|---|---|
| `AGENTS.md:106` | «**633** tests actuals» | **871** |
| `ROADMAP.md:8` | «Suite: **857** tests OK (1 skip)» | **871** |

> ✏️ **Correcció:** fixar la xifra des d'una **font única** (idealment, que el doc la
> llegeixi del CI o que s'actualitzi al mateix commit que els tests). `DEVELOPING.md`
> (que és el doc de qui desenvolupa) no en dona cap xifra — bon patró a imitar.

### 2.2 Panell «Tipus d'acord»: 62 vs 80 🔴

| Fitxer:línia | Diu |
|---|---|
| `ROADMAP.md:58` | «panell de tipus d'acord (**62 tipus**)» |
| `docs/TIPUS_XIFRAT_ACORDS.md:21` | «La llista surt de `xifrat.TAULA_TIPUS` (**62 files**, de menys a més complex…)» |
| `CHANGELOG.md:87` | «una **llista de 62 tipus**» |

**Realitat al codi:** `len(xifrat.TAULA_TIPUS)` = **80**, i el panell en carrega **tots**
(`app/panell_xifrat.py:152-154`: `for etiqueta, qual, alts, graus in xifrat.TAULA_TIPUS`).
A més, `len(xifrat.TIPUS)` = **61** (una altra xifra), i la taula del mateix
`TIPUS_XIFRAT_ACORDS.md` té **85 files** (7+37+31+10).

> ✏️ **Correcció:** dir **80** (o derivar-ho del codi). `test_doc_xifrat.py` **no**
> detecta aquest desfasament perquè només comprova `xifrat.TIPUS ⊆ doc`, no la
> mida de `TAULA_TIPUS`.

### 2.3 Tag `v0.7.1` sense versió equivalent 🟠

- El repo té el tag **`v0.7.1`** (`git show -s v0.7.1` → `75134d5`), però
  `pyproject.toml:7` i `app/__init__.py` diuen **`0.7.0`** i el `CHANGELOG.md`
  **no té cap secció `[0.7.1]`** (l'última és `[0.7.0] — 2026-10-14`, línia 333).
- A més, els altres checkpoints porten sufix: `v0.6.2-checkpoint`,
  `v0.5.0-checkpoint`… → `v0.7.1` **no segueix la convenció** i sembla una
  release sense bump.
- `CHANGELOG.md:4` diu: «Versions amb tag git (`v0.1-punt-control` …
  `v0.5.1_CHECKPOINT_3_so_ARTIFACTS`)» → **desfasat** (els tags arriben a `v0.7.1`).

> ✏️ **Correcció:** o bé **esborrar el tag `v0.7.1`** (si era un checkpoint), o bé
> reanomenar-lo `v0.7.1-checkpoint`, o bé fer-ne una release real (bump + `CHANGELOG`).
> I actualitzar `CHANGELOG.md:4`.

### 2.4 Línies de `main.py` / `visor.py` 🟡

| Fitxer:línia | Diu | Real |
|---|---|---|
| `ROADMAP.md:216` · `ROADMAP_HISTORIA.md:1141` | `main.py` **2.942** línies | **3.043** |
| `ROADMAP.md:222` · `ROADMAP_HISTORIA.md:1177` | `visor.py` **3.029** línies | **3.097** |

> ✅ El recompte de mètodes de `Finestra` (**138**) **sí** que és correcte.
> ✏️ **Correcció:** actualitzar les 4 xifres (o treure el recompte de línies, que
> envellix sol).

---

## 3. Contradiccions entre documents

### 3.1 Què inclouen els paquets de release 🔴

**`docs/CI_WORKFLOWS.md:43-44`** diu:
> «Docs inclosos: `README.md`, `CHANGELOG.md`, `ROADMAP.md`, `LICENSE`,
> `LLICENCIES_TERCERS.md` i `docs/`.»

Però **dos altres docs** diuen exactament el contrari, i **els workflows reals ho
confirmen**:

| Font | Diu |
|---|---|
| `DEVELOPING.md:114-116` | «Els paquets de release només porten l'imprescindible: `README.md` + `LICENSE` + `LLICENCIES_TERCERS.md` + les 2 imatges del README. **No** s'hi posen `docs/`, `CHANGELOG` ni `ROADMAP`.» |
| `DEVELOPING.md:320` | «…Els paquets només porten `README.md` + `LICENSE` + `LLICENCIES_TERCERS.md`.» |
| `AGENTS.md:114-116` (regla de treball #6) | mateix text |
| `build-appimage.yml:179-186` | comentari «Al paquet NOMÉS hi va l'imprescindible… El CHANGELOG/ROADMAP i tot `docs/` són documentació» + `cp LICENSE LLICENCIES_TERCERS.md README.md` |
| `build-windows.yml:155-160` · `build-macos.yml:354-358` | idèntics |

> ✏️ **Correcció:** **`CI_WORKFLOWS.md:43-44` és l'incorrecte.** Ha de dir
> `README.md`, `LICENSE`, `LLICENCIES_TERCERS.md` i les 2 imatges.

### 3.2 Els projectes per MCP: «pendent» vs «FET» 🔴

**`docs/PROJECTES.md:87-89`** («Pendents») diu:
> «**(MCP) exposar els projectes al pont**: obrir/desar/desar com/backup/recents →
> **encara NO hi és** (ara només GUI). Detall: `docs/MCP_AUTO_CHORDS.md`
> §«Pendent — funcions noves NO cobertes per l'MCP».»

Però **`docs/MCP_AUTO_CHORDS.md`** té la secció «**Funcions noves cobertes
(2026-10-15)**» (línies 170-181) que diu que **ja hi són** (`ac_crea_projecte`,
`ac_obre_projecte`, `ac_desa_projecte`, `ac_desa_com`, `ac_fes_backup`, `ac_recents`),
i el **codi** les implementa (`app/mcp_bridge.py` + `eines/mcp_auto_chords_server.py`,
51 eines). A més, **la secció que cita `PROJECTES.md` no existeix** (el títol va canviar).

> ✏️ **Correcció:** marcar els projectes com a **coberts per l'MCP** a
> `PROJECTES.md` (treure'ls de «Pendents») i corregir la referència a la secció.

### 3.3 `CHANGELOG.md` es contradiu dins `[Unreleased]` 🟠

Dues entrades del **mateix bloc** diuen coses oposades sobre el botó **▶ Escoltar**:

- `CHANGELOG.md:85-93` («Afegit», panell de tipus): «El botó **▶ Escoltar** va
  **desactivat** (plaçaholder de la futura funció **MIDI**…)».
- `CHANGELOG.md:65-72` («Afegit», audició): «**▶ Escoltar al panell…**: el botó
  **ja és actiu** — sent l'acord … amb un **e-piano FM estil Rhodes**».

> ✏️ **Correcció:** a l'entrada del panell, indicar que el toc d'escolta es va
> **completar després** (o retirar l'afirmació «desactivat»). Nota: la funcionalitat
> implementada **no és MIDI** sinó **síntesi numpy**; el títol «MIDI» també hi és a
> `ROADMAP_HISTORIA.md:980` («MIDI per escoltar els acords»), cosa que confon.

### 3.4 `Am/G` → `Am-G` vs `Am_G` 🟠

La canonització real transforma `/` en **`_`** (mai `-`), perquè `-` vol dir «menor»:

- **Codi** `app/pipeline.py:69` (docstring de `safe_filename`): «`Am/G`→`Am_G`».
- **Canònic als docs:** `docs/NOTACIO_XIFRAT.md:65` (`A7/G` → `A7_G.wav`),
  `docs/TIPUS_XIFRAT_ACORDS.md:35`, `CHANGELOG.md:231-234`.

Però **dos docs** ho tenen malament:

| Fitxer:línia | Diu (incorrecte) |
|---|---|
| `docs/MCP_AUTO_CHORDS.md:97` | «(`C#m7`, `N`; `Am/G` → `Am-G`)» |
| `docs/SEGURETAT.md:60` | «(`C`, `C#m7`, `N`, `Am/G`→`Am-G`…)» |

> ✏️ **Correcció:** canviar-ho a `Am/G` → `Am_G` als dos llocs.

### 3.5 «Obre WAV…» vs «Obre àudio…» 🟡

L'app va renombrar l'acció (CHANGELOG: «**«Obre…» → «Obre àudio»**»); el codi diu
`"Obre àudio"` (`app/main.py:341` i `:736`) i `ESQUEMA_UI.md:51,86` també. Però:

| Fitxer:línia | Diu (vell) |
|---|---|
| `docs/PROVES_FUNCIONALS_3SO.md:57` | «**Obre un WAV** (`Fitxer ▸ **Obre WAV…**`, `Ctrl+O`)» |
| `docs/PROJECTES.md:42` | «**Obre WAV…** | `Ctrl+O`» |

> *(El `docs/ESQUEMA_UI.md:129` també diu «`Ctrl+O` = obrir WAV», però és la drecera
> i el sentit és correcte; es pot deixar o dir «obrir àudio».)*

---

## 4. Documentació vs codi (envelliment)

### 4.1 «plugin aubio» com a font de BPM actual 🟡

`docs/GRAELLA_PPQ_TEMPS.md:31` («On som **ara**»): «BPM: `app/tempo.py` (numpy) /
`qm-tempotracker` / **plugin aubio**.»

Però l'aubio està **retirat** des de la v0.5:
`docs/QM_VAMP.md:88-95`, `DEVELOPING.md:16-17`, `docs/AUTODETECCIO_OPCIONS.md:22`
(«vamp-aubio (**retirat**)»).

> ✏️ **Correcció:** treure «plugin aubio» de la llista de motors actuals.

### 4.2 Com es passen els paràmetres del Chordino 🟡

`docs/AUTODETECCIO_OPCIONS.md:119-122` (§4bis, «implementat») diu:
> «`extract_chords(..., params=)` el fa servir amb **`sonic-annotator -t <ttl>`**.»

Però amb el **host propi** (que és el camí normal), els paràmetres es passen amb
**`--param clau=valor`** (`app/pipeline.py:259-260`); el camí `sonic-annotator -t`
només s'usa **com a reserva** si falta el host (`pipeline.py:263-271`).

> ✏️ **Correcció:** explicar que el mecanisme principal és el **host propi** amb
> `--param`, i que `sonic-annotator -t <ttl>` és el **fallback**.
> *(La resta del §4bis —la trampa del `-s`— segueix vigent i és correcta.)*

---

## 5. Menors

- **`tests/test_regles_or.py:3-9`** — El docstring diu que el doc marca com «amb test»
  les regles «**2, 4, 8, 9 i 11**» i que aquí es blinden «les que no: 1, 3, 5, 6, 7,
  **8** i 10» → la **8 surt a les dues llistes**. El que diu `docs/REGLES_DE_LA_APP.md:129-131`
  és que `test_regles_or` cobreix **(1, 3, 5, 6, 7, 8, 10)** i que la 8 no la té cap
  altre. El docstring hauria de dir «2, 4, 9 i 11».
- **`docs/ESQUEMA_UI.md:5`** — «Actualitzat: **2026-10-14** · v0.7.0», però el
  contingut es va regenerar el **2026-10-16** (bloc de l'`Esc`; vegeu els commits
  `da15c04`/`f54bae1`). Actualitzar la data.
- **`ROADMAP_HISTORIA.md:59`** — Títol «Obertura **tecnolítica**» (errata; hauria de
  ser «tecnològica»).
- **`AGENTS.md` està gitignorat** (`.gitignore:105`) i **no trackejat** — decisió
  conscient (és fitxer «local d'agent»), però porta informació que els agents llegeixen
  (les 11 regles resumides + el recompte de tests desfasat de §2.1). Convé, com a mínim,
  mantenir-lo al dia encara que no es versioni.

---

## Metodologia (reproduïble)

1. **Fase 0 — línia base:** executar la suite (`QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests`),
   comptar eines MCP (`_TOOLS`), mida de fitxers (`wc -l`), `git status`/`log`/`tag`.
2. **Fase 1-2 — docs:** lectura sencera de tots els `.md` d'arrel i de `docs/`, amb
   comprovació creuada d'enllaços (script propi que resol rutes relatives i per basename).
3. **Fase 3 — doc ↔ codi:** verificar al codi les afirmacions dels docs
   (`TAULA_TIPUS`, `safe_filename`, `_cmd_transform`, etiquetes de menú, etc.).
4. **Fase 4 — coherència interna:** funcions de les regles d'or al codi, fonts de veritat.
5. **Fase 5-6 — build/CI i tests:** workflows, `requirements*.txt`, `deps_fixades.env`,
   llançadors, `.desktop`, i coherència dels recomptes de tests de les regles.

---

## Notes

- **No s'ha modificat cap fitxer existent** del projecte. Aquest informe és l'únic fitxer creat.
- Les troballes estan **prioritzades**: els 🔴 afecten afirmacions que poden portar a
  error un agent o un usuari (què porten els paquets, si l'MCP té tal funció, quants
  tests hi ha, quants tipus d'acord); els 🟠 són enllaços trencats i xifres visibles;
  els 🟡 són d'envelliment/etiquetes.
- Les referències dins `CHANGELOG.md` i `docs/archive/` a fitxers moguts **no** es
  compten com a error (són història; `ROADMAP_HISTORIA.md:745` ho documenta).
