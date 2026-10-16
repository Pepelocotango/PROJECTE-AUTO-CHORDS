# Índex de la documentació (`docs/`)

> Guia de navegació dels documents d'AUTO CHORDS. **Actualitzat: 2026-10-15.**
> L'estat *actual* del projecte és a **`../README.md`** i **`../ROADMAP.md`**;
> aquí hi ha el **detall temàtic**. Els documents marcats **[HISTÒRIC]** o
> **[COMPLETAT]** es conserven com a referència, però ja **no** descriuen el
> projecte actual (s'indica on és la informació vigent).

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
| `ESQUEMA_UI.md` · `ESQUEMA_UI.html` · `ESQUEMA_UI.svg` | Esquema de la GUI (3 formats). |
| `PROJECTES.md` 🚧 | **Projectes autocontinguts** («com un DAW»): `.acproj`, `audio/` copiat, «Desa com»… (en desenvolupament). |
| `FLUX_DE_DADES.md` | **Flux de dades**: capa **CRUA** (`analisi/`, immutable) vs **MODEL** editable; què toca cada operació. |
| `NOTACIO_XIFRAT.md` | **Notació del xifrat**: la forma canònica (`Am`→`A-`), variants que entén i on s'aplica. |
| `PLAY.md` | Com sona l'àudio a l'app i per què està fet així. |
| `MOTOR_AUDIO_SO.md` | Motors d'àudio per SO (Linux/macOS/Windows). |
| `GRAELLA_PPQ_TEMPS.md` | Graella, PPQ i formats de temps (nota tècnica). |
| `TIPUS_XIFRAT_ACORDS.md` | **Tipus de xifrat d'acords**: variants de sintaxi, graus i `<kind>` MusicXML (MuseScore). |
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
| `CI_WORKFLOWS.md` | Els 5 workflows de GitHub Actions i el flux de Release. |
| `COMPONENTS_I_VERSIONS.md` | Inventari de components i versions (per vigilar CVE). |
| `SEGURETAT.md` · `../SECURITY.md` | Enduriment de seguretat i canal de report. |

## Qualitat i auditoria

| Doc | Què explica |
|---|---|
| `AUDITORIA_PRODUCCIO.md` | Auditoria de producció (OC-5+OC-6), estat i bugs trobats/arreglats. |

## Referència

| Doc | Què explica |
|---|---|
| `REFERENCIA_PILES_PROGRAMES_REFERENCIA.md` | Piles tecnològiques/gràfiques d'altres programes (REAPER, Audacity…). |

## Arxiu — documents superats (es conserven a `archive/` com a referència)

| Doc | Què explica |
|---|---|
| `archive/AUBIO_TEMPO.md` **[HISTÒRIC]** | Plugin d'aubio (tempo/beats), **retirat** — substituït per `app/tempo.py`. |
| `archive/PORTABILITAT.md` **[ANÀLISI]** | Anàlisi original de què calia per ser autocontingut (ja fet). |
| `archive/PLA_PORTABILITAT.md` **[COMPLETAT]** | Pla per fases (2026-10-07) — ja executat. |
| `archive/PLANIFICACIO_MACOS.md` **[FET]** | Pla per a macOS High Sierra 10.13+ — ja executat. |

---

> 📌 **Convencions**: documentació **en català**; les regles d'or (`REGLES_DE_LA_APP.md`)
> són **invariants**; cada doc porta a dalt la data/versió. En moure/renombrar un doc,
> actualitzeu els enllaços i aquest índex.
