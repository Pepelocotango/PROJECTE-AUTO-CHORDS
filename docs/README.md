# Índex de la documentació (`docs/`)

> Guia de navegació dels documents d'AUTO CHORDS. **Actualitzat: 2026-10-16.**
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
| `GRAELLA_PPQ_TEMPS.md` | Graella, PPQ i formats de temps (nota tècnica). |
| `PARTITURA_EXPORT.md` | Exportació de partitura (xifrat: MusicXML/PDF/MSCZ). |
| `MCP_AUTO_CHORDS.md` | Pont MCP perquè un agent controli l'app viva. |

## Autodetecció (motors i opcions)

| Doc | Què explica |
|---|---|
| `AUTODETECCIO_OPCIONS.md` | Motors d'autodetecció (BPM/acords/estructura) i opcions. |
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
| `COMPONENTS_I_VERSIONS.md` | Inventari de components i versions (per vigilar CVE). |
| `SEGURETAT.md` · `../SECURITY.md` | Enduriment de seguretat i canal de report. |

## Auditoria

| Doc | Què explica |
|---|---|
| `INFORME_INCOHERENCIES_2026-10-16.md` | **Auditoria de coherència** (docs + codi): incoherències, bugs i seguretat detectats. |

## Arxiu — superats o de referència (`archive/`)

| Doc | Què explica |
|---|---|
| `archive/AUDITORIA_PRODUCCIO.md` **[HISTÒRIC]** | Auditoria de producció (OC-5+OC-6, 10-2026): estat i bugs trobats/arreglats. |
| `archive/REFERENCIA_PILES_PROGRAMES_REFERENCIA.md` **[REFERÈNCIA]** | Piles tecnològiques/gràfiques d'altres programes (REAPER, Audacity…). |
| `archive/PANELL_TIPUS_ACORD_mockup.svg` · `.png` **[DISSENY]** | Maqueta **aprovada** del panell de tipus d'acord (ja implementat). |
| `archive/AUBIO_TEMPO.md` **[HISTÒRIC]** | Plugin d'aubio (tempo/beats), **retirat** — substituït per `app/tempo.py`. |
| `archive/PORTABILITAT.md` **[ANÀLISI]** | Anàlisi original de què calia per ser autocontingut (ja fet). |
| `archive/PLA_PORTABILITAT.md` **[COMPLETAT]** | Pla per fases (2026-10-07) — ja executat. |
| `archive/PLANIFICACIO_MACOS.md` **[FET]** | Pla per a macOS High Sierra 10.13+ — ja executat. |

---

> 📌 **Convencions**: documentació **en català**; les regles d'or
> (`REGLES_DE_LA_APP.md`) són **invariants**; cada doc porta a dalt la
> data/versió. En moure/renombrar un doc, actualitzeu els enllaços i aquest índex.
