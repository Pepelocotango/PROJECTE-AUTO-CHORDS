# Índex de la documentació (`docs/`)

> **El codi és la font de veritat.** Aquesta carpeta només conté el contracte i
> els documents amb informació que no es pot derivar del codi. La resta de
> documentació (història, plans executats, guies operatives) viu al
> `CHANGELOG.md`, `ROADMAP_HISTORIA.md` i els docstrings dels mòduls.
>
> L'estat de la sessió és a **`../ROADMAP.md` §2**; l'abast del producte, a
> **`../AGENTS.md`**.

## Contracte i documents vius

| Doc | Què explica |
|---|---|
| **`REGLES_DE_LA_APP.md`** | 🔴 **Regles d'or (invariants)**: 1–12 i el §13 (temps, compàs i graella). Si el codi no les compleix, és un bug del codi. |
| `ESQUEMA_UI.md` (`.html` · `.svg`) | Esquema de la interfície. Les vistes `.html`/`.svg` es **generen** (`eines/genera_esquema_ui.py`) — no editar-les a mà. |
| `EDICIO_OPERACIONS.md` | Taula única d'operacions d'edició: GUI × paritat acords/estructura × estat. |
| `TIPUS_XIFRAT_ACORDS.md` | Catàleg de tipus d'acord, variants, graus i `<kind>` MusicXML. |
| `COMPONENTS_I_VERSIONS.md` | Inventari de components i versions. El **genera** `eines/genera_inventari.py` — no editar-lo a mà. |

## Recerca (`recerca/`)

Documents de referència i propostes que **no** descriuen l'estat actual del codi:

| Doc | Què explica |
|---|---|
| `recerca/guia_tecnica_downbeat_onsets_beats.md` | Teoria d'onsets, beats i downbeats; criteris per a la detecció. |
| `recerca/NOTACIO_XIFRAT.md` | Forma canònica del xifrat i les seues variants. |
| `recerca/GRAELLA_PPQ_TEMPS.md` | Proposta de PPQ/ticks i swing (no implementada). |
| `recerca/AUTODETECCIO_OPCIONS.md` | Mesuraments reals dels motors d'autodetecció. |

---

> 📌 **Convencions**: documentació en català; cada doc porta data/versió a dalt.
> Si un document descriu codi que ja no existeix, **s'esborra**: no es mantenen
> documents històrics dins `docs/`.
