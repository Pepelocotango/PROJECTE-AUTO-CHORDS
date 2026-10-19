# Índex de la documentació (`docs/`)

> Guia de navegació dels documents d'AUTO CHORDS. **Actualitzat: 2026-10-18.**
> L'estat *actual* del projecte és a **`../README.md`** i **`../ROADMAP.md`**;
> aquí hi ha el **detall temàtic**. Els documents d'**`archive/`** (marcats
> **[HISTÒRIC]**, **[ANÀLISI]** o **[COMPLETAT]**) es conserven com a referència,
> però ja **no** descriuen el projecte actual.

## Com començar

| Doc | Què explica |
|---|---|
| **`../README.md`** | Visió general, instal·lació i «estat actual». |
| **`../DEVELOPING.md`** | Entorn de desenvolupament i mapa del codi. |
| **`REGLES_DE_LA_APP.md`** | 🔴 **Les regles d'or (invariants)** — llegir **abans** de tocar codi. |
| **`ESQUEMA_UI.md`** (`.html` · `.svg`) | Esquema visual de la interfície: zones, icones reals i colors. |

## Funcionament de l'app

| Doc | Què explica |
|---|---|
| `REGLES_DE_LA_APP.md` | Regles d'or: ordre estricte, contigüitat, cobertura total… |
| `ESQUEMA_UI.md` · `ESQUEMA_UI.html` · `ESQUEMA_UI.svg` | Esquema de la GUI. El `.html` i el `.svg` es **generen** (`eines/genera_esquema_ui.py`) des del `.md` — **no editar-los a mà**. L'**art manual** original es conserva a `ESQUEMA_UI_manual.svg` · `ESQUEMA_UI_manual.html`. |
| `PROJECTES.md` | **Projectes autocontinguts** («com un DAW»): `.acproj`, `audio/` copiat, «Desa com», backups. |
| `FLUX_DE_DADES.md` | **Flux de dades**: capa **CRUA** (`analisi/`, immutable) vs **MODEL** editable. |
| `NOTACIO_XIFRAT.md` | **Notació del xifrat**: la forma canònica (`Am`→`A-`) i on s'aplica. |
| `TIPUS_XIFRAT_ACORDS.md` | **Tipus de xifrat**: variants de sintaxi, graus i `<kind>` MusicXML (MuseScore). |
| `AUDIO.md` | **Àudio**: reproducció (play) i motors per SO (Linux/macOS/Windows). |
| `GRAELLA_PPQ_TEMPS.md` | Graella, PPQ i formats de temps: **estat actual del codi** (§1) i **proposta pendent** de la capa de *ticks*/PPQ 960 (§8). |
| `PARTITURA_EXPORT.md` | Exportació de partitura (xifrat: MusicXML/PDF/MSCZ). |
| `EDICIO_OPERACIONS.md` | **Taula única** de totes les formes d'edició: operació × **GUI** × paritat acords/estructura (**#11**) × estat (FET/pendent). El test `TestDocEdicioOperacions` la manté al dia. |

## Plans i refactors **en curs**

| Doc | Què explica |
|---|---|

> Els refactors **acabats** viuen a `archive/` (p. ex. `REFACTOR_INICI_FI.md`):
> es conserven com a contracte i rastre, però ja no descriuen estat viu.

## Autodetecció (motors i opcions)

| Doc | Què explica |
|---|---|
| `AUTODETECCIO_OPCIONS.md` **[HISTÒRIC]** | Exploració de motors d'autodetecció i **mesuraments reals** del 07-10-2026 (superada per `QM_VAMP.md` i `ESQUEMA_UI.md` §6). |
| `QM_VAMP.md` | Plugins QM Vamp (Queen Mary) compilats localment. |

## Portabilitat i compilació (3 SO)

| Doc | Què explica |
|---|---|
| `ESTAT_MULTI_SO.md` | 🎯 **Foto actual** del desplegament a Linux/Windows/macOS. |
| `PORTABILITAT_WINDOWS.md` | Com es construeix el paquet portable de Windows. |
| `PROVES_FUNCIONALS_3SO.md` | Com validar els 3 paquets en un sistema real. |

## CI/CD, versions i seguretat

| Doc | Què explica |
|---|---|
| `CI_WORKFLOWS.md` | Els workflows de GitHub Actions i el flux de Release. |
| `COMPONENTS_I_VERSIONS.md` | Inventari de components i versions (per vigilar CVE). El **genera** `eines/genera_inventari.py` des de `requirements.txt` i `eines/deps_fixades.env` — **no editar-lo a mà** (el CI comprova que estiga al dia). |
| `SEGURETAT.md` · `../SECURITY.md` | Enduriment de seguretat i canal de report. |

## Auditoria

| Doc | Què explica |
|---|---|
| `archive/INFORME_INCOHERENCIES_2026-10-16.md` | **Auditoria de coherència** (docs + codi), del 16-10-2026: **tots els punts resolts**; arxivada (vegeu `archive/AUDITORIA_REGLES.md`, Ronda 13). |

## Arxiu — superats o de referència (`archive/`)

| Doc | Què explica |
|---|---|
| `archive/REFACTOR_INICI_FI.md` **[COMPLETAT]** | 🏗️ Refactor de base **inici+fi** (model únic de clips amb `ini`+`fi` per a acords i estructura): contracte i pla per fases. **Acabat** el 17-10-2026 (`refactor-fi-fet`). |
| `archive/AUDITORIA_PRODUCCIO.md` **[HISTÒRIC]** | Auditoria de producció (OC-5+OC-6, 10-2026): estat i bugs trobats/arreglats. |
| `archive/REFERENCIA_PILES_PROGRAMES_REFERENCIA.md` **[REFERÈNCIA]** | Piles tecnològiques/gràfiques d'altres programes (REAPER, Audacity…). |
| `archive/PANELL_TIPUS_ACORD_mockup.svg` · `.png` **[DISSENY]** | Maqueta **aprovada** del panell de tipus d'acord (ja implementat). |
| `archive/AUDITORIA_REGLES.md` **[ARXIVAT]** | 🔍 Registre de l'auditoria de les regles d'or (rondes 1–54), **tancada**: mapa regla→validació→test, trobades i cua. |
| `archive/PLA_TEMPO_COMPAS.md` **[FET]** | 🎚️ Pla del mapa de tempo i compàs variables (motor `app/tempo_map.py`). |
| `archive/PLA_EDICIO_LLIURE.md` **[FET]** | ✂️ Pla de l'edició lliure (§2, §6): la regla #4 com a contracte **posterior** a cada operació. |
| `archive/AUBIO_TEMPO.md` **[HISTÒRIC]** | Plugin d'aubio (tempo/beats), **retirat** — substituït per `app/tempo.py`. |
| `archive/PORTABILITAT.md` **[ANÀLISI]** | Anàlisi original de què calia per ser autocontingut (ja fet). |
| `archive/PLA_PORTABILITAT.md` **[COMPLETAT]** | Pla per fases (2026-10-07) — ja executat. |
| `archive/PLANIFICACIO_MACOS.md` **[FET]** | Pla per a macOS High Sierra 10.13+ — ja executat. |

---

> 📌 **Convencions**: documentació **en català**; les regles d'or
> (`REGLES_DE_LA_APP.md`) són **invariants**; cada doc porta a dalt la
> data/versió. En moure/renombrar un doc, actualitzeu els enllaços i aquest índex.
