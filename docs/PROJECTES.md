# Projectes d'AUTO CHORDS — carpeta autocontinguda («com un DAW»)

> ✅ **FET** (2026-10-14, OC-8; refinat després). Codi: **`app/projecte.py`** + la
> **GUI** a `app/main.py`. Tests: `tests/test_projecte.py`,
> `test_projectes_gui.py`, `test_projecte_backups.py`, `test_regla11_paritat.py`.
> Regla de producte: **«com un DAW»** — un projecte ho conté tot i **no depèn de res
> de fora**.

## Què és

Un **projecte** és una **carpeta que ho conté tot** (com el projecte d'un DAW):

```
La meva cançó/                 ← la carpeta del projecte (portable)
├── La meva cançó.acproj       ← el document (JSON, amb «versió de format»)
├── audio/ tema.wav            ← CÒPIA de l'àudio (mai depèn de fora)
├── acords.csv                 ← el model (font de veritat)
├── estructura_ABC.csv         ← el model (font de veritat)
├── analisi/                   ← ANÀLISI CRUA (evidència, MAI es toca):
│   ├── chords_raw.csv         ←    sortida de Chordino, sense netejar
│   ├── segments_raw.csv       ←    sortida del segmentador d'estructura
│   └── meta.json              ←    WAV, durada, BPM/compàs/offset i opcions
├── wavs_acords/ …             ← exports (els crea `pipeline.exporta_total`)
└── backup/ <data-hora>/ …     ← còpies versionades (autosave / rotació)
```

L'àudio es **copia sempre** a `audio/`: així la carpeta es pot **renombrar o moure**
sencera —o es pot **esborrar l'original**— i el projecte s'obre **exactament igual**.
**Cap ruta absoluta cap a fora** del projecte.

## El document `.acproj` (JSON)

- `format` (versió de format; `_migra` **rebutja** una versió més nova) · `app` · `nom`
  · `creat` / `desat` · `audio` (ruta **relativa** dins el projecte).
- `tempo` (`bpm` / `bpb` / `offset` / `fix`) · `opcions` (autodetecció) · `vista`.
- Es desa **atòmicament** (`pipeline.escriu_atomic`: mai queda a mitges).

## GUI (fase 2) — cicle de vida (menú **Fitxer**)

| Acció | Drecera | Què fa |
|---|---|---|
| **Obre àudio…** | `Ctrl+O` | Obre un àudio (com sempre). |
| **Obre projecte…** | `Ctrl+Shift+O` | Obre una carpeta de projecte (`.acproj`). |
| **Obre recent…** | — | **Recents** (fins a 8) — `recents.json` a `~/.local/state/auto-chords/`. |
| **Desa** | `Ctrl+S` | Desa el `.acproj` (atòmic). |
| **Desa com…** | `Ctrl+Shift+S` | **`Projecte.duplica()`**: copia la carpeta sencera i renombra el `.acproj`. |
| **Desa una còpia…** | — | Duplica sense canviar el projecte obert. |
| **Reverteix** | — | Torna a l'últim desat (descarta els canvis). |

- El **títol** mostra el projecte i un **`*`** si hi ha canvis sense desar («brut»).
- En obrir un projecte es carrega **àudio + tempo + visor + títol** (`_activa_projecte`).

## Backups i recuperació (fase 3)

- **Autosave**: un `QTimer` cada **60 s** (`AUTOSAVE_MS`) fa una **còpia versionada**
  a **`backup/<data-hora>/`** — **només si hi ha canvis NOUS**.
- **Què copia** `Projecte.fes_backup()`: el **document** (`.acproj` amb l'**estat viu**)
  + els **fitxers importants** (CSVs d'acords/estructura/segments i locators) + la
  carpeta **`analisi/`** (l'anàlisi crua). **NO** copia l'àudio (`audio/`) ni els
  exports (`wavs_*`, `partitura/`), que es **deriven** i són grossos. **No duplica**
  si el contingut no ha canviat des de l'última còpia.
- **Rotació**: es guarden les **10** còpies més noves (`MAX_BACKUPS`).
- **Sessió / crash**: `sessio.json` (a `~/.local/state/auto-chords/`) s'escriu amb un
  projecte obert i es **neteja al tancament net**; si l'app va **caure**, a l'arrencada
  **s'ofereix** el projecte pendent (`_sessio_pendent`).

## API (resum)

| Funció | Què fa |
|---|---|
| `Projecte.crea(carpeta, wav, …)` | Crea la carpeta, **copia l'àudio** i desa el `.acproj`. |
| `Projecte.obre(ruta)` | Obre per `.acproj`, carpeta o WAV (migra el format). |
| `Projecte.desa()` | Desa el `.acproj` **atòmicament**. |
| `Projecte.duplica(destí)` | **Desa com / còpia**: copia el projecte sencer i renombra el `.acproj`. |
| `Projecte.fes_backup()` | Còpia versionada a `backup/<data-hora>/` + rotació. |
| `troba_acproj(ruta)` / `es_projecte(ruta)` | Troba/comprova un projecte (`.acproj`, carpeta o WAV). |
| `importa_autochords(wav, …)` | **Migra** una `AUTOCHORDS_<nom>/` antiga a un projecte autocontingut. |

## Per què

- **Portabilitat total**: l'app deixa de dependre de la ubicació de l'àudio original.
- **Còpia/duplicat segurs** («Desa com») i **recuperació** davant d'un crash.
- Base per a un futur **format de projecte estable**.

## Pendents

- **(MCP) exposar els projectes al pont** ✅ **FET (2026-10-15)**: `ac_crea_projecte`,
  `ac_obre_projecte`, `ac_desa_projecte`, `ac_desa_com`, `ac_fes_backup`, `ac_recents`.
  Detall: `docs/MCP_AUTO_CHORDS.md` §«Funcions noves cobertes».
- Migracions de `format` < actual (`_migra`, camp a camp).
- (opcional) UI per **recuperar una còpia** concreta de `backup/` des de la GUI.

> ⚠️ Cap canvi d'aquest feature no pot trencar les **regles d'or**
> (`docs/REGLES_DE_LA_APP.md`).
