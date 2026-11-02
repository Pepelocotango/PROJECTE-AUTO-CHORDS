# Projectes d'AUTO CHORDS — carpeta autocontinguda («com un DAW»)

> ✅ **FET** (2026-10-14, OC-8; refinat després). Codi: **`app/projecte.py`** + la
> **GUI** a `app/main.py`. Tests: `tests/test_gui.py` (`TestCrea`,
> `TestAutocontencio`, `TestObreDesa`, `TestDuplica`, `TestMigracioAutochords`,
> `TestBackups`) i la paritat de projecte a `tests/test_edicio.py` ›
> `_regla11_paritat___Base`.
> Regla de producte: **«com un DAW»** — un projecte ho conté tot i **no depèn de res
> de fora**.

> ⚠️ **Política de formats (2026-11-02):** la **retrocompatibilitat no és
> prioritat**. Un canvi de format pot **rebutjar** projectes vells amb un error
> clar; no es fan migracions automàtiques ni es mantenen dos formats en
> paral·lel. Els fitxers de l'usuari no es toquen mai: es rebutgen i s'explica
> el motiu.

## Què és

Un **projecte** és una **carpeta que ho conté tot** (com el projecte d'un DAW):

```
La meva cançó/                 ← la carpeta del projecte (portable)
├── La meva cançó.acproj       ← el document (JSON, amb «versió de format»)
├── audio/ tema.wav            ← CÒPIA WAV de treball (mai depèn de fora)
├── acords.csv                 ← el model (font de veritat)
├── estructura_ABC.csv         ← el model (font de veritat)
├── tempo.csv · compas.csv     ← el model (mapa de BPM/compàs)
├── marcadors.csv              ← marcadors humans del mapa
│   (el CRU de l'anàlisi viu DINS el .acproj — no hi ha carpeta analisi/)
├── wavs_acords/ …             ← exports (els crea `pipeline.exporta_total`)
└── backup/ <data-hora>/ …     ← còpies versionades (autosave / rotació)
```

L'àudio de treball es guarda a `audio/`: així la carpeta es pot **renombrar o moure**
sencera —o es pot **esborrar l'original**— i el projecte s'obre **exactament igual**.
**Cap ruta absoluta cap a fora** del projecte. Aquesta és l'única còpia editable
per a les operacions actuals als extrems. Si l'entrada no és un WAV PCM 16 bits compatible,
es converteix directament en un temporal dins `audio/`, sense un WAV intermedi
al costat de l'original; vegeu
[`EDICIO_AUDIO.md`](EDICIO_AUDIO.md).

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
| **Obre recent…** | — | **Recents** (fins a 8) — `recents.json` al **directori d'estat** (`app/config.py`: la carpeta del projecte si és escrivible, si no `~/.local/state/auto-chords/`). |
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
  + els **fitxers del MODEL** + `marcadors.csv` + la **cru de l'anàlisi** (que viatja dins el
  `.acproj`) + el WAV de treball (`audio/`). **NO** copia els exports
  (`wavs_*`, `partitura/`), que es deriven i són grossos. No duplica si el
  contingut no ha canviat des de l'última còpia. El WAV es compara amb mida i
  data de modificació per evitar llegir-lo complet a cada autosave; les còpies
  es preparen en temporal i només es publiquen quan estan completes.
- La inclusió del WAV i els marcadors està implementada; les edicions actuals
  sincronitzen l'àudio i el model i es poden desfer/refer junts. Encara falta
  implementar el flux de restauració conjunta des d'un backup (§13.9 de
  `REGLES_DE_LA_APP.md`).
- **Rotació**: es guarden les **10** còpies més noves (`MAX_BACKUPS`).
- **Sessió / crash**: `sessio.json` (al **directori d'estat**, com el log) s'escriu amb un
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

## Estat

- ~~Migracions de `format` < actual~~ → ✅ **FET**: `_migra` accepta qualsevol
  `format` anterior (el 0 = projectes sense el camp), migra camp a camp quan
  calgui i **rebutja** els projectes d'un format MÉS NOU amb un error clar;
  proveït a `tests/test_gui.py` (`format` 0 i 99).

## Edició bàsica d'àudio

- El WAV de `audio/` és l'única còpia editable dins del projecte; l'original
  importat es conserva intacte i el resultat exportat va a un fitxer nou.
  La conversió, l'edició dels extrems i l'exportació amb FFmpeg ja estan
  implementades; la restauració de backups des de la GUI continua pendent.
  Detall: [`EDICIO_AUDIO.md`](EDICIO_AUDIO.md).

### Idees (no són pendents)

- UI per **recuperar una còpia** concreta de `backup/` des de la GUI (avui les
  còpies ja es fan totes i es poden recuperar a mà des del gestor de fitxers).

> ⚠️ Cap canvi d'aquest feature no pot trencar les **regles d'or**
> (`docs/REGLES_DE_LA_APP.md`).
