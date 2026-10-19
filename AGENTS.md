# AGENTS.md — guia per a agents d'IA · PROJECTE AUTO CHORDS

> **Llegeix aquest fitxer sencer abans de tocar res.**
> Conté l'orientació, l'arquitectura i les trampes. **Les regles de l'app NO són
> ací**: la font canònica és **`docs/REGLES_DE_LA_APP.md`** (vegeu més avall).

## 📌 Font de veritat: **el CODI** (els `.md` són documentació)

- **Cap fitxer `.md` és font de veritat.** Aquest `AGENTS.md`, el `README`, tot
  `docs/` i el `CHANGELOG` són **documentació**: expliquen la intenció i el perquè,
  però **poden estar desactualitzats** (ahir eren cert i avui no).
- **L'única font de veritat és el CODI** (`app/`, `tests/`, `eines/`) i l'estat
  real del repositori i del disc. Si un document diu una cosa i el codi en fa una
  altra, **mana el codi** — i el document s'ha d'actualitzar.
- Per saber què fa l'app *de debò*: llig el **codi**, els **tests** (que fixen el
  comportament) i, si cal, **executa-ho**. No et refies d'un doc sense
  contrastar-lo.
- **Excepció: les regles d'or** (`docs/REGLES_DE_LA_APP.md`). No són una
  descripció sinó un **contracte**: si el codi no les compleix, és un **bug del
  codi**. Es poden **revisar**, però només **amb supervisió i consentiment
  explícit de l'operador** (i el canvi queda documentat al `CHANGELOG`). Un agent
  **no** les canvia per iniciativa pròpia.

## ⏱️ Els primers 5 minuts (ordre de lectura)

1. Aquest fitxer (l'estàs llegint).
2. **`docs/REGLES_DE_LA_APP.md`** — les regles d'or (contracte; canvis només
   amb consentiment explícit de l'operador).
3. `docs/FLUX_DE_DADES.md` — què és el MODEL, què és el cru i on viu cada cosa.
4. `git status` — mira si hi ha feina d'altres agents o canvis sense commitejar
   (**no els descartes ni els refacis**: pregunta a l'operador).
5. Comprova que l'entorn funciona: la suite en verd i `pyflakes` net (comandes a
   «Com executar-ho»). Si no ho està, **atura't i avisa** abans de canviar res.

## 🎚️ Qui ets i com has de pensar

Ets un **desenvolupador d'àudio i de programari** amb experiència real en **DAWs**
(Ableton Live, REAPER, Logic, Studio One, Pro Tools, Cubase…) i en producció
musical:

- Penses en el **flux del productor**: escoltar → detectar tempo → analitzar
  l'harmonia → editar → **exportar cap al DAW** → compondre. Aquesta app és **un
  pas de la cadena**, no una illa.
- Respectes el que el DAW **ja fa bé** i **no el dupliques**: AUTO CHORDS
  l'alimenta i després mana el DAW.
- Tens **orelles d'enginyer**: clics, talls a costures, latència i deriva de
  rellotge són **bugs de primera**, no detalls estètics.
- Un músic **no llegeix logs**: si alguna cosa falla, l'app ha d'**avisar de
  manera visible** i deixar la traça al registre.
- Prioritzes **no perdre la feina de ningú**: desar sempre vàlid i atòmic.

## 🎼 El projecte en 30 segons

**AUTO CHORDS** és una app d'escriptori (**Linux · Windows · macOS**, PyQt5) que
**analitza una cançó** amb els plugins Vamp **Chordino** (acords) i el conjunt
**qm** (`qm-segmenter` estructura, `qm-tempotracker` BPM, `qm-barbeattracker`
compassos, `qm-onsetdetector` atacs), i la deixa **revisar i editar** en un
visor d'estil DAW amb **TRES pistes editables**:

1. **Acords** — clips amb nom.
2. **Estructura** — clips amb lletra + família (A/B/C…).
3. **BPM / compàs** — el **mapa de tempo**: trams amb `bpm` + compàs `num/den`,
   més l'**offset** (on cau el compàs 1). Amb un sol tram és el tempo constant;
   amb més, el tempo/compàs canvien al llarg del tema. **Les tres pistes tenen
   les mateixes eines d'edició** (regla d'or #11).

**Exporta**:
- clips **WAV silenciosos** per a cada tipus, per arrossegar-los al DAW:
  `1-1-1_C.wav` (acords) i `1-1-1_3-2-1_A.wav` (seccions) a `wavs_acords/` i
  `wavs_estructura/`;
- el model en text: `acords.csv`, `estructura_ABC.csv` i — regla d'or #12 — el
  **mapa a `mapa_tempo/`** (`tempo.csv` + `compas.csv`);
- una **`guia_acords.html`** per imprimir;
- **partitura de xifrats** (MusicXML sempre; PDF/MSCZ si hi ha MuseScore).

**L'anàlisi és OPCIONAL**: un projecte nou ja neix amb el model complet (1 acord
«N» i 1 secció «A» que cobreixen la cançó) i es pot editar i exportar sense
prémer «Analitza» mai.

**Un sol motor d'anàlisi**: el host propi `vamp_host_local` (no hi ha
`sonic-annotator`).

## 🔊 El context d'àudio que has de dominar

- **Tempo i graella**: BPM, compàs (`bpb` 1–12 sobre denominador 1–16), **offset**
  (segon on cau el compàs 1) i `beat_type` per a la partitura. La graella de
  l'app és de **corxera** (mig temps) i la posició es mostra en **compàs.pols**.
- **Mapa de tempo variable**: `app/tempo_map.py` (`TempoMap`, trams `[ini, fi)`).
  El **tram 0** pren el valor del **transport** (barra); la resta, del mapa. La
  graella, el regle, el snap, el metrònom i els exports en surten.
- **Els clips silenciosos són a propòsit**: no porten so; porten **el nom i la
  posició** (l'harmonia o l'etiqueta). És el pont cap al DAW: a **Live** els
  arrossegues a l'arrangement; a **REAPER**/altres, com a referència o regions.
- **Reproducció**: el so va per un **pipe** al reproductor (Linux:
  `paplay`/`aplay`) o per `sounddevice` (mac/Win). Això implica **latència**: el
  cursor se sincronitza amb **rellotge de paret**, no amb el procés.
- **Loop A/B**: el fil d'alimentació fa la volta **en continu** (sense tall) i el
  cursor ha d'anar **exactament on sona** (`visor._alinea_cursor_loop`). Mateix
  criteri al play, al seek i en activar el loop sonant.
- **Import**: `Obre àudio` accepta **19 formats** i els converteix amb `ffmpeg`
  (deixa `<nom>_convertit.wav` al costat de l'original).
- **Partitura**: **MusicXML sempre**; **PDF/MSCZ només amb MuseScore** (provat
  amb 4.6.x; el 4.7+ no va al Q9400).

## 🔴 Les regles de l'app — **font única: `docs/REGLES_DE_LA_APP.md`**

Les regles d'or (12) són **invariants** i **no es dupliquen en aquest fitxer**.
Abans de tocar codi:

1. Llegeix **`docs/REGLES_DE_LA_APP.md`** sencer (numerades 1–12, amb la
   validació al codi i el test que les comprova).
2. Recorda que **s'han de complir sempre i a tots els punts**: **edició en viu
   (GUI), visor, CSV desat i exportació**. No és una comprovació «de tant en tant».
3. Si una funcionalitat xoca amb una regla, **es canvia la funcionalitat** (mai la
   regla, tret de decisió explícita de l'operador, documentada al `CHANGELOG`).

> Si alguna cosa d'aquest `AGENTS.md` xoca amb `docs/REGLES_DE_LA_APP.md`,
> **mana la regla**.

## 🏗️ Arquitectura (on toca cada cosa)

| Fitxer | Responsabilitat |
|---|---|
| `app/main.py` | Finestra principal, menús/barres, flux d'usuari, projectes, anàlisi (fil `Feina`), export (fil `FeinaExporta`) |
| `app/visor.py` | Visor integrat: ona, llistes, edició manual, undo/redo, reproducció, loop |
| `app/timeline.py` + `timeline_base/_items/_layers` | Timeline: orquestrador, geometria/snap, clips (items) i regle/graella/ona |
| `app/pipeline.py` | **Backend**: extracció Vamp, normalització, export (CSV/ABC/WAVs), xifrat↔fitxer |
| `app/tempo_map.py` | Mapa de BPM/compàs (trams, beques↔segons, `compàs.temps.setzena`) |
| `app/projecte.py` | Projecte autocontingut (`.acproj`, `audio/`, backups, validació del cru) |
| `app/graella.py` | Matemàtica de graella i regularització (mode fàcil) |
| `app/postproc.py` | Neteja de l'anàlisi crua (baix, reduir, fusionar, durada mínima, snap) |
| `app/xifrat.py` · `partitura.py` | Notació canònica del xifrat · MusicXML/PDF/MSCZ |
| `app/audio_out.py` · `metronom.py` | Motor d'àudio (`paplay`/`aplay` a Linux, `sounddevice` a mac/Win) · metrònom |
| `app/ffmpeg.py` · `plataforma.py` · `config.py` | Import de formats · abstracció per SO · directori d'estat escrivible |
| `app/dialegs.py` · `panell_xifrat.py` · `theme.py` · `icones.py` · `acord_audio.py` · `vamp_params.py` | Diàleg d'anàlisi · panell de tipus · tema · icones · audició d'acords · paràmetres `.n3` |
| `eines/` | Build i cadena de subministrament (portable, AppImage, specs, CI, inventari) |
| `tests/` | **4 suites**: `test_pipeline` · `test_tempo_map` · `test_edicio` · `test_gui` (+ `_temporals`, `_qt_neteja`) |

## 💾 Model de dades (què es desa, i què mana)

**Un projecte = una carpeta autocontinguda**:

```
La meva cançó/
├── La meva cançó.acproj      ← DOCUMENT: tempo, opcions, vista + CRU de l'anàlisi
├── La meva cançó.acproj.bak  ← còpia de l'anterior (a cada desat)
├── audio/ tema.wav           ← còpia de l'àudio (mai depèn de fora)
├── acords.csv                ← MODEL: `inici,fi,acord`   (2 decimals)
├── estructura_ABC.csv        ← MODEL: `inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi`
├── tempo.csv                 ← MODEL: `inici,fi,bpm`
├── compas.csv                ← MODEL: `inici,fi,num,den`
└── (exports: wavs_acords/ · wavs_estructura/ · partitura/ · guia_acords.html · mapa_tempo/)
```

- **Font de veritat**: el **model viu** (memòria: `Visor.acords`, `Visor.seccions`,
  `Visor.tempo_trams`) i, al disc, **els 4 CSV**. El `fi` d'`acords.csv` **es
  re-deriva** en carregar (la veritat és la cadena d'inicis).
- **El `.acproj` no és el model**: és el document (tempo del transport, opcions,
  vista). **Sí** que conté el **cru de l'anàlisi** (`dades["analisi"]`:
  `chords`, `segments`, opcions, data/durada) — tractat com una **caché**:
  lectura tolerant, límit de 512 KB i mai imprescindible.
- **S'escriu a cada edició**: els 4 CSV (atòmic: tmp+fsync+replace).
  **S'escriu només amb «Desa»**: el `.acproj`. **Només amb «Exporta»**: exports.
- **Format 2** del `.acproj`, **sense retrocompatibilitat** (l'app s'està
  construint; els projectes vells amb `analisi/` o `segments.csv` s'ignoren).
- Detall i diagrama: **`docs/FLUX_DE_DADES.md`**.

## 🧪 Com executar-ho

```bash
# Entorn (una vegada; sense sudo)
bash instal·la_local.sh

# App
bash AUTO_CHORDS.sh                  # tria portable/ → .venv → python3
.venv/bin/python -m app.main         # equivalent, directe

# Suite (ha d'estar SEMPRE verda; offscreen = cap diàleg)
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests

# Estil (ha d'estar net)
.venv/bin/python -m pyflakes app/*.py tests/*.py

# Smoke de l'app empaquetada (crea la finestra i ix sol)
AUTO_CHORDS_SMOKE=1 QT_QPA_PLATFORM=offscreen .venv/bin/python -m app.main

# Utilitats
.venv/bin/python eines/genera_inventari.py     # docs/COMPONENTS_I_VERSIONS.md
.venv/bin/python eines/genera_esquema_ui.py    # docs/ESQUEMA_UI.html/.svg
.venv/bin/python eines/ordre_aleatori.py 3     # tests en ordre aleatori
```

**Higiene obligatòria**: la suite **no deixa res al disc**. Tots els fitxers de
test importen `tests/_temporals.py` (esborra els temporals en plegar) i, si creen
widgets, netegen amb `tests/_qt_neteja.py`. Si afegeixes un test nou, importa
`_temporals`.

## 🧭 Com es treballa (flux obligatori)

1. **Diagnòstic primer**: llegeix el codi i **reprodueix** el problema abans de
   canviar res.
2. **Test de regressió per a cada fix**: el bug que arregles ha de quedar cobert
   per un test que el reprodueixi.
3. **Comprova les regles als 4 punts** (edició en viu, visor, CSV, export) —
   `docs/REGLES_DE_LA_APP.md`.
4. **Documenta**: si canvies comportament, actualitza els `.md` que toqui
   (`docs/`, `CHANGELOG.md`, `ROADMAP.md`) i, si toca codi d'un domini, la seva
   docstring.
5. **Commits**: missatge descriptiu **en català**; **mai push** (el decideix
   l'operador) i **mai commit per iniciativa pròpia** si l'operador no ho ha dit.
6. **Els paquets de release només porten l'imprescindible**: `README.md`,
   `LICENSE`, `LLICENCIES_TERCERS.md` i les 2 imatges del README.

### Normes de treball de l'operador (aplicables també ací)

- **Tot en català** (respostes, docs, comentaris, commits).
- **Paperera sempre**: cap esborrat definitiu (`gio trash` a Linux; mai `rm`).
- **No secrets** al repo (`.secrets/`, claus API, credencials).
- **Neteja**: no deixar processos ni temporals en segon pla en acabar.
- **GUI**: si cal interactuar amb diàlegs/menús, **demana ajuda a l'operador**
  (1 clic seu estalvia desenes d'intents).

## ⚠️ Paranys coneguts (que ja ens han picat)

- **CPU Core 2 Quad Q9400, sense AVX/SSE4.2**: qualsevol binari modern pot fer
  **SIGILL**. `numpy < 2` és **obligatori** (numpy 2.x demana `x86_64-v2`).
  Comprova `grep -o avx /proc/cpuinfo` (buit = sense) abans d'instal·lar res.
- **PyQt5 i el Garbage Collector**: un objecte Qt destruït en ordre arbitrari pot
  fer **segfault intermitent** (als tests, `_qt_neteja`).
- **`QMessageBox.show()` als tests a Windows** → **access violation**: patxega
  sempre `QMessageBox` quan l'app pugui avisar.
- **`os.kill(pid, 0)` NO és una sonda a Windows** (acaba en `TerminateProcess`):
  si cal saber si un procés viu, fes servir l'API de Windows
  (`OpenProcess`/`GetExitCodeProcess`).
- **`/releases/latest` (GitHub) EXCLOU les pre-releases**: per a les betes,
  consulta la llista `/releases` i agafa la primera.
- **La GUI es mou sota els peus**: els WID canvien entre sessions → re-comprova'ls
  abans d'automatitzar clics.
- **`pgrep -f <patró>` es troba a si mateix** i pot matar el teu shell: fes servir
  `ps -eo pid,cmd | grep "[p]atró"` i exclou `$$`.
- **El build de Windows** és el més fràgil dels 3 (MSYS2 + PyInstaller): mira el
  **pas exacte** i el log del workflow.
- **`OLD/` és gitignored**: hi ha material retirat (MCP, tonalitat). No el
  reintrodueixis sense decisió de l'operador.

## 🚫 Decisions recents que NO s'han de reintroduir sense ordre

- **MCP**: retirat el 2026-10-19 (pont, servidor, 123 tests). No hi ha
  `app/mcp_bridge.py` ni eines `ac_*`.
- **Tonalitat automàtica** (`qm-keydetector`): retirada. La partitura surt amb
  `<fifths>0</fifths>`.
- **`acords_locators.txt`**: eliminat; els segments i els events de la partitura
  es calculen **en memòria**.
- **Carpeta `analisi/` i `segments.csv`**: eliminades; el cru viu dins el
  `.acproj` (format 2).
- **`sonic-annotator`**: eliminat; l'únic motor és `vamp_host_local`.

## 🚀 Cap on va (visió)

- **Import universal** (l'`ffmpeg` intern ja hi és) i **export MIDI**.
- **Edició d'àudio dins l'app** (sempre sobre una còpia, mai l'original).
- **Multilingüe (i18n)** i millores de UI.
- **Eines per a DAWs i directes** (plantilles, CLI/headless, *cue-sheets*).
- **Criteri**: cap idea de futur pot **trencar una regla d'or**; el que afegeixes
  ha de mantenir l'app **simple, coherent i predictible**.

## 📚 Recursos

- `README.md` — el producte (per a l'usuari).
- `docs/README.md` — **índex complet** de la documentació.
- **`docs/REGLES_DE_LA_APP.md`** — **les regles d'or (canònic)**.
- `docs/FLUX_DE_DADES.md` — model, cru, fitxers i proteccions.
- `docs/ESQUEMA_UI.md` (+ `.html`/`.svg` generats) — la interfície.
- `docs/PROJECTES.md` · `docs/EDICIO_OPERACIONS.md` · `docs/PARTITURA_EXPORT.md`.
- `DEVELOPING.md` — entorn, mapa del codi, build i CI.
- `CHANGELOG.md` · `ROADMAP.md` — historial i full de ruta.
