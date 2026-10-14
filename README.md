# PROJECTE AUTO CHORDS

> **AUTO CHORDS** analitza un àudio i n'extreu els **acords** i l'**estructura**
> (motor Chordino + Queen Mary). Els pots **revisar i editar** en un visor
> estil DAW i **exportar** els clips **WAV** per al Live/Reaper, més la
> **partitura** (MusicXML/PDF). App d'escriptori **multi-SO** (Linux · Windows · macOS).

> **Repositori:** https://github.com/Pepelocotango/PROJECTE-AUTO-CHORDS
> (les versions publicades —Linux `.tar.gz` amb l'**AppImage**, Windows `.zip`, macOS `.dmg`— són a *Releases*).

> **Novetats v0.6.2 (BETA):** **botons nous** a la barra («Exporta WAV's»,
> «Exporta partitura», «Zoom selecció») i la partitura deixa clar que el PDF
> necessita **MuseScore** instal·lat. **v0.6.1:** **estabilitat d'àudio a macOS** (teardown idempotent
> i serialitzat a `audio_out.py` que evita crashes `EXC_BAD_ACCESS`),
> **suport de MuseScore a macOS i Windows** per a exportació de partitures en PDF/MSCZ,
> i **suite completa de tests** executant-se als 3 workflows del CI.
> **v0.6.0:** **motor d'àudio natiu multi-SO** (`sounddevice`/PortAudio sobre CoreAudio
> a macOS i WASAPI a Windows), **generació de DMG a macOS**, **smoke test** de l'`.app`
> i **verificació exhaustiva de `minos`** (≤ 10.13). **v0.5.2:** **edició DAW-like completa**
> (multi-selecció, copiar/retallar/enganxar, duplicar i moure grup) i refactorització del timeline.

## Estat actual (2026-10-13 · v0.6.2 BETA)

L’app està **reorganitzada amb el timeline com a centre de la finestra**
(estil Audacity/DAW): l’anàlisi és una **acció** sobre el que es veu, no un
pas d’assistent.

- En obrir un àudio (**Fitxer ▸ Obre…**, `Ctrl+O`) es mostren l’ona i el
  timeline **de seguida**, amb les pistes Acords/Estructura buides.
- **Barra de menús**: Fitxer · Edita · Selecciona · Visualitza · Analitza · Ajuda.
- **Barra de temps** fina: mode **BPM · compàs** / **Lliure (hh:mm:ss)**,
  BPM, botons **×2/÷2**, **🎯 Detecta** (motor triable), **TAP**, compàs
  en format **`x/x`** (`4`, `4/4`, `6/8`, etc.) i Offset amb **📍** (cursor) i
  **🧭** (automàtic). (**«Inclou estructura»** és una acció del menú **Analitza**.)
- **Barra de transport** pròpia: play/stop, −10s/+10s, loop A/B, **neteja del loop**
  (icona `x`), zoom i mute (`Espai` = play/stop). La roda del ratolí fa **zoom centrat
  al cursor vermell** quan no hi ha cap clip seleccionat, i segueix sent coherent amb
  el clip seleccionat quan n’hi ha un.
- **Barra d'Accions** (sota la de temps): **Analitza**, **Exporta WAV's**, **Exporta
  partitura**, **Desfer**/**Refer** (icones `undo-2`/`redo-2`) i **Obre la carpeta de sortida**.
- **Metrònom** 🥁 (només en mode BPM · compàs), amb **volum propi** (60 %).
- **Analitza** (`F5`): progrés a la **barra d’estat**; el **log** és un tauler
  plegable a baix (**Visualitza ▸ Mostra el log**).
- **Exporta WAV's…** (`Ctrl+E`) a Fitxer; desactivat fins que hi ha resultat.
- **Edició al timeline**: desfer/refer (`Ctrl+Z`/`Ctrl+Y`), `Delete`, `Ctrl+D`
  (duplica) i **menú contextual** (botó dret). Mai toca els WAVs generats.
- **Multi-selecció i porta-retalls**: `Ctrl+clic` (afegir/treure) i `Shift+clic`
  (rang); `Ctrl+C`/`Ctrl+X`/`Ctrl+V` (copiar/retallar/enganxar al cursor) i
  `Ctrl+D` per duplicar **tot el grup**; arrossegar un clip seleccionat mou el
  grup sencer. El regle mostra el **mode** (`120 BPM · 4/4` o `Lliure`).
- **Llistes** d’acords (⑨) i estructura (⑩) **a sota de l’ona**: clic per saltar,
  doble-clic per editar, botó dret = menú contextual. (El panell **Log · Informació**,
  a baix, s’amaga/mostra amb **Visualitza ▸ Mostra el log**.)
- Compassos de **qualsevol mètrica** (3/4, 6/8, 5/4…), no només 4/4.

La funcionalitat principal està validada: **tota la suite · OK (1 skip)** (`python -m unittest discover -s tests`).

## ✅ Implementat (pendent de commit) + ⏳ En preparació

> **P1 (A1–A3) — ja és al CODI** (sense commitejar; es validarà i commitarà aviat):
> - **A1** — **desfer/refer** també per a **BPM, compàs, offset i loop A-B**.
> - **A2** — **Edita ▸ «Parteix la secció al cursor…»**: partir una secció (manera natural d'afegir-ne en un model saturat per la cobertura).
> - **A3** — el diàleg **Ajuda ▸ Dreceres de teclat** ara llista **totes** les dreceres reals.
>
> **P2 (A4–A9) — EN IMPLEMENTACIÓ** (encara NO disponible). Detall: `docs/MCP_AUTO_CHORDS.md`:
> A4 partitura des de l'MCP/amb els WAVs · A5 progrés d'export · A6 `ac_analyze` amb opcions ·
> A7 més eines · A8 convivència OFF/instància única · A9 autocomprovació amb `ffmpeg`.

## Què fa l’app

- analitza un àudio amb **Chordino** (acords) + **qm-segmenter** (estructura)
- genera CSVs d’acords i estructura ABC
- mostra ona, cursor, temps i navegació per la cançó
- permet corregir acords i editar seccions
- regenera els clips produïts en funció dels canvis manuals
- exporta el paquet final per a DAW en una sola acció final

## Flux actual d’ús

1. Obre l'àudio (`Obre…`) — si no és WAV, es converteix sol amb ffmpeg
2. Ajusta el BPM (🎯 Detecta o TAP) i fes `Analitza` (obre el diàleg d'opcions)
3. Revisa i edita acords / seccions al visor (franja Editor)
4. Fes `Exporta WAV's`

## Filosofia i lògica del flux

La idea central del projecte no és tenir “múltiples eines ocultes”, sinó una sola aplicació amb un flux clar i un model de dades coherent:

### Semàntica del flux

- els intervals tenen inici i fi; el fi no s’edita de manera independent perquè es deriva del següent inici o de la durada total
- “N” és un valor de chord vàlid, no una excepció especial
- el sistema accepta acords i seccions ordenats de manera estricta: no solapaments, no inversions de temps, no duplicats de start
- la normalització ordena els elements abans de salvar-los i la validació rebutja canvis lògicament invàlids

### Per què aquest model

Perquè permet que el producte sigui coherent i predictible:

- l’usuari sempre editant la mateixa font de dades
- el visor reflecteix el que realment es guardarà
- els exports són reproduïbles i no depenen d’una “modalitat temporal” distinta
- el codi no es descontrola amb dades inconsistents ni amb dos models de temps barrejats

Aquest és el criteri que ha acabat definint la base de l’app: una app única, un flux únic i una representació temporal única en el backend.

## Configuració

- L'estat (**temp**, log, opcions) va a un **directori d'estat escriptible**:
  `~/.local/state/auto-chords/` (hi ha `temp/` a dins). Mai dins el paquet (regla d'or #10).
- El directori temporal es pot sobreescriure amb la variable d'entorn
  **`AUTO_CHORDS_TEMP`** (camí absolut o relatiu), útil per a fluxos personalitzats:

```bash
export AUTO_CHORDS_TEMP=/home/user/tmp_auto_chords
python -m app.visor tema.wav
```

## Llançament

Des de la carpeta del projecte:

```bash
python -m app.main
```

Si **no tens PyQt5 al sistema**, crea abans un entorn aïllat **sense `sudo`**
(mateix flux que a `DEVELOPING.md`):

```bash
bash instal·la_local.sh        # crea .venv/ + PyQt5 + .deps/ (headers)
.venv/bin/python app/main.py
```

O directament amb:

```bash
./AUTO_CHORDS.sh
```

També hi ha un **llançador d'escriptori** (`AUTO_CHORDS.desktop`): fes-hi **doble-clic**,
o instal·la'l al menú d'aplicacions amb `bash instal·la_local.sh`. (Un `.desktop` **no**
s'executa com un programa des del terminal (`./AUTO_CHORDS.desktop` no funciona).)

## Estructura clau

- `app/main.py` — finestra principal i flux d’usuari
- `app/visor.py` — visor integrat, llistes, navegació, edició manual
- `app/timeline.py` — orquestrador del timeline i re-exportacions
- `app/timeline_base.py` — vista base i escena de QGraphicsView
- `app/timeline_items.py` — clips d'acords i seccions (items gràfics)
- `app/timeline_layers.py` — capes de regle, graella i forma d'ona
- `app/pipeline.py` — extracció, exportació, normalització
- `app/audio_out.py` — motor d'àudio natiu (PortAudio / sounddevice / CoreAudio / WASAPI)
- `app/plataforma.py` — abstracció multi-SO (Linux / Windows / macOS)
- `app/config.py` — configuració centralitzada de la aplicació
- `app/tempo.py` — detecció de BPM (numpy, sense AVX)
- `app/metronom.py` — clic del metrònom mesclat al buffer
- `app/vamp_params.py` — paràmetres dels plugins Vamp (descriptors `.n3`)
- `app/dialegs.py` — diàleg d’opcions d’autodetecció
- `app/postproc.py` — neteja posterior dels acords
- `app/partitura.py` — export de partitura (MusicXML / PDF / MSCZ)
- `app/ffmpeg.py` — import d’altres formats (conversió a WAV)
- `app/theme.py` — tema centralitzat
- `eines/vamp_host.cpp` — **host Vamp propi** (`vamp_host_local`), sense Qt6
- `eines/` — build i cadena de subministrament: `crea_portable.sh`,
  `compila_vamp_host.sh`, `compila_vamp_plugins.sh`, `empaqueta_portable.sh`,
  `crea_appimage.sh`, `libreries_natives.sh`; **descàrregues verificades**
  (`baixa_verificat.py` + `deps_fixades.env`); packaging (`AutoChords-win.spec`,
  `launcher_pyinstaller.py`, `crea_icona.py`); release (`notes_release.py`) i
  inventari (`genera_inventari.py`)
- `portable/` — Python + ffmpeg portables (entrada de build, gitignorat)
- `AUTO_CHORDS.sh` — llançador (prefereix el Python portable)

## Documentació

Índex complet de documents: **`docs/README.md`** — esquema de la GUI, **regles d'or**,
portabilitat (Linux/Windows/macOS), CI/CD, seguretat, autodetecció, auditoria…
Destaquen: **`docs/REGLES_DE_LA_APP.md`** (invariants), **`docs/ESQUEMA_UI.md`** i
**`docs/CI_WORKFLOWS.md`**.

## Paquet portable (autocontingut)

```bash
eines/empaqueta_portable.sh      # -> ../AUTO_CHORDS_PORTABLE/
cd ../AUTO_CHORDS_PORTABLE && ./AUTO_CHORDS.sh
```
El paquet **no s'edita mai** (és un artefacte de build): el codi viu aquí i es
regenera. Detall: `docs/PORTABILITAT.md`.

## AppImage (un sol fitxer executable)

L'AppImage embolcalla el paquet portable + un `AppRun` + el `.desktop` + la
icona, i el comprimeix (squashfs): dels ~530 MB surt un fitxer d'**~160 MB**
que s'executa a qualsevol **Linux x86_64** sense instal·lar res.

> **Multi-SO**: a més d'aquesta AppImage de Linux, el CI construeix i empaqueta
> **Windows (x64)** i **macOS (High Sierra 10.13+)**. Els 3 builds **han estat verds**;
> l'**últim `build-all` verd és el #4** (`98aa58e`) i després hi ha hagut fixos de CI
> **pendents de revalidar**. Estat i artefactes: **`docs/ESTAT_MULTI_SO.md`**.
>
> El runtime incrustat és el modern **estàtic** (`type2-runtime`, enllaçat amb
> musl i libfuse a dins), així que **no cal instal·lar `libfuse2`**.

**És autoportable**: a dins hi van el Python, Qt, ffmpeg, els plugins Vamp
**i les seves llibreries natives** (`libvamp-hostsdk`, `libsndfile` i els
còdecs: FLAC, Vorbis, Opus, Ogg, mpg123, LAME). Al sistema host **només** calen
`glibc` + `libstdc++/libgcc` (que té qualsevol Linux modern), un entorn
d'escriptori i —per **escoltar**— PipeWire o PulseAudio. Detall exacte:
`docs/PORTABILITAT.md`.

### Descarregar

Les versions publicades són a
**https://github.com/Pepelocotango/PROJECTE-AUTO-CHORDS** → *Releases*:
**Linux** `.tar.gz` (AppImage + docs) · **Windows** `.zip` · **macOS** `.dmg`.

### Construir-lo localment
```bash
eines/crea_appimage.sh          # -> ../AUTO_CHORDS-x86_64.AppImage
```
Requereix haver fet abans: `eines/crea_portable.sh` (Python + ffmpeg + les
llibreries natives del host Vamp) i `eines/compila_vamp_host.sh` (l'host Vamp).
L'`appimagetool` es baixa sol.

### Executar-lo
```bash
chmod +x AUTO_CHORDS-x86_64.AppImage
./AUTO_CHORDS-x86_64.AppImage
```
O **doble clic**. ⚠️ Per **escoltar** cal **PipeWire** o **PulseAudio** (sense
ells l'app funciona igual, només avisa).

> ✅ **No cal `libfuse2`**: el runtime incrustat és **estàtic** (porta
> libfuse + squashfuse + musl a dins) i només depèn del **suport FUSE del
> kernel**, que tot Linux ja té. (L'avís clàssic d'instal·lar `libfuse2` és
> per a AppImages construïdes amb el runtime **antic**.) Només si el nucli
> tingués FUSE desactivat caldria `./AutoChords-*.AppImage --appimage-extract-and-run`.

### GitHub Actions
Cinc workflows a `.github/workflows/` (tots d'execució **manual**):

| Workflow | Quan s'activa | Què fa |
|----------|---------------|--------|
| **`build-all.yml`** | **només manual** | **Agregador**: executa els 3 builds (Linux + Windows + macOS) **en paral·lel**; cada un deixa el seu artefacte |
| **`build-appimage.yml`** | **només manual** (GitHub ▸ Actions ▸ Run workflow) | Construeix l'AppImage de **Linux** i l'empaqueta en un **`.tar.gz`** (AppImage + docs) com a **artefacte** descarregable |
| **`build-windows.yml`** | **només manual** | Construeix el paquet portable de **Windows x64** (MSYS2 + PyInstaller `--onedir`) i el deixa com a **artefacte** (ZIP) |
| **`build-macos.yml`** | **només manual** | Construeix el **`.app` de macOS 10.13+** (Intel; PyInstaller) i el deixa com a **artefacte** (DMG) |
| **`release.yml`** | **només manual** | **Drecera**: agafa els **últims artefactes verds** de Linux/Windows/macOS **directament de GitHub Actions** i crea un **Release PUBLICAT** (no esborrany) amb títol `AUTO CHORDS v<versió>`, el cos **en català** (`eines/notes_release.py`) i els **3 paquets** adjunts |

> **Tot manual**: cap workflow s'activa sol (ni amb tags). Per fer un **Release**:
> llança **`release.yml`** a mà — agafa els últims artefactes verds dels 3 SO i crea
> el **Release PUBLICAT** (`gh release create`, sense `--draft`) a GitHub ▸ Releases.
> Cap workflow fa `git push` al repositori.
>
> **Com funciona cada workflow (detall): `docs/CI_WORKFLOWS.md`.**

> ⚠️ Els runners són `ubuntu-22.04` (no 24.04): allà s'hi **compila
> `vamp_host_local`**, i la seva glibc marca l'abast mínim de l'AppImage.
> Detall: `docs/PORTABILITAT.md`.

## Requisits

### ✅ Mínims per FER-LA FUNCIONAR (usuari final, amb l'AppImage)

| Requisit | Detall |
|----------|--------|
| **Sistema** | **Linux x86_64** amb **glibc ≥ 2.35** → Ubuntu 22.04+, Debian 12+, Fedora 36+… |
| **Llibreries natives** | **Cap instal·lació** ✅ — `libvamp-hostsdk`, `libsndfile` i els còdecs (FLAC, Vorbis, Opus, Ogg, mpg123, LAME) van **dins** l'AppImage (`portable/lib/`). Al SO només calen `glibc` + `libstdc++/libgcc` |
| **CPU** | Qualsevol x86_64 amb **SSE2** · provada en un **Core 2 Quad Q9400** *sense AVX* ✅ |
| **RAM / disc** | ~1 GB RAM lliure per a temes curts · ~170 MB a disc (l'AppImage és un sol fitxer). ⚠️ **Fitxers llargs**: el visor carrega **tot el PCM a memòria** (≈ **3× la mida del fitxer**; una hora ≈ **2 GB**); a partir de **45 min** l'app ho avisa pel panell del log. |
| **Per ESCOLTAR** | **PipeWire** o **PulseAudio** (qualsevol escriptori Linux actual). **Opcional**: sense això l'app fa tota la resta (analitzar, editar, exportar), només avisa que no pot sonar |
| **Per executar l'AppImage** | **Res especial** ✅ — el runtime va **estàtic** (porta libfuse+squashfuse a dins; només cal el suport **FUSE del kernel**, que és estàndard). Si mai fallés: `./AutoChords-*.AppImage --appimage-extract-and-run` |

> ✨ **No cal instal·lar res més**: ni Python, ni Qt, ni ffmpeg, ni els plugins
> — tot va **dins** l'AppImage.

### 🛠️ Per executar-la des del codi (desenvolupament)

- **Python 3.10+** + **PyQt5** + **numpy < 2** (el **QtSvg** ve amb PyQt5)
  → o, més fàcil, el **Python portable** que ja ho porta tot (`portable/`)
- **Plugins Vamp** dins el projecte: **Chordino** (`nnls-chroma`) i
  **qm-vamp-plugins** (Queen Mary) — **sense instal·lar res al sistema**
- **Host Vamp propi** (`vamp_host_local`) — substitueix `sonic-annotator`
- **`ffmpeg`** (opcional, només per importar formats que no siguin WAV):
  s'embega a `portable/bin/ffmpeg`
- `numpy < 2` és **obligatori** (numpy 2.x demana x86_64-v2 → falla en CPUs
  antigues com el Q9400)

### 🏗️ Per construir (AppImage / paquet portable)

- **`g++`** + **`vamp-plugin-sdk`** + **`libsndfile1-dev`** (per compilar l'host;
  `vamp-plugin-sdk` porta els headers de Vamp — `libvamp-hostsdk-dev` **no
  existeix** com a paquet)
- Les **llibreries natives** que fa servir l'host (Vamp, sndfile i els còdecs)
  **no es baixen**: `eines/libreries_natives.sh` les **copia del sistema que
  compila** cap a `portable/lib/` (així la glibc mínima queda lligada al build)
- **`curl`** + **connexió a Internet** (es baixen el Python portable, l'ffmpeg i les icones Lucide)
- **`appimagetool`** (es baixa sol; duu el runtime **estàtic** a dins → **no** cal `libfuse2`)
- Els **workflows de GitHub Actions** ho fan tot sols a **`ubuntu-22.04`**
  (aquesta versió fixa la **glibc mínima** de l'AppImage, perquè allà s'hi
  compila l'host). Detall: `docs/PORTABILITAT.md`

## Autoria

**Autor:** **Pëp** — [pepelocotango@gmail.com](mailto:pepelocotango@gmail.com)

Aquest projecte s'ha desenvolupat **en col·laboració amb agents i assistents
d'intel·ligència artificial**, que hi han dedicat moltes hores de feina. Volem
reconèixer-ho explícitament:

- 🤖 **[opencode](https://opencode.ai)** (agent `OC`) — el gruix del
  desenvolupament d'aquesta darrera etapa: l'**AppImage autocontinguda**, els
  **workflows de GitHub Actions** (build + release), els **plugins Vamp de
  Queen Mary**, l'**host Vamp propi**, les **icones professionals**, la
  **coherència del play**, el diàleg d'opcions i bona part de la resta.
  Amb models com **DeepSeek** (que va fer una feinada enorme 💙), **Claude**,
  **Gemini**, entre d'altres.
- 🧠 **[Claude](https://claude.ai)** (Anthropic) — també hi ha ajudat
- ✨ **[Gemini](https://gemini.google.com)** i
  **[Google AI Studio](https://aistudio.google.com)** (agent `GM`)
- 🧭 **Devin** (agent `DV`)
- 💬 **[Chatbox](https://chatboxai.app)** (agent `CB`)
- 🛠️ **[VS Code](https://code.visualstudio.com)** amb
  **[GitHub Copilot](https://github.com/features/copilot)** (agent `VS`)
- 🌊 **[Windsurf](https://windsurf.com)** amb el model **SWE** (agent `WS`)
- ⚡ **Spark** (`SPARK`, primeres versions de l'app)

> **Nota legal**: els sistemes d'IA no són titulars de drets d'autor (UE/EUA);
> la **titularitat i la responsabilitat del projecte són de l'autor humà**. El
> reconeixement de dalt és, per tant, un **agraïment honest**, no una
> atribució jurídica.

## Agraïments i reconeixement a projectes de tercers

Aquest projecte depèn de treballs previs i eines desenvolupades per altres
persones i equips. Volem reconèixer-ho explícitament i agrair-ho sincerament.
**El detall complet de llicències és a [`LLICENCIES_TERCERS.md`](LLICENCIES_TERCERS.md).**

| Component | Llicència | Autoria |
|-----------|-----------|---------|
| **[Python](https://www.python.org)** | PSF-2.0 | Python Software Foundation |
| **[PyQt5](https://riverbankcomputing.com/software/pyqt)** / **[Qt5](https://www.qt.io)** | GPL-3.0 / LGPL-3.0 | Riverbank / The Qt Company |
| **[NumPy](https://numpy.org)** | BSD-3-Clause | NumPy Developers |
| **[Chordino / NNLS-Chroma](https://code.soundsoftware.ac.uk/projects/nnls-chroma)** | GPL-2.0+ | Matthias Mauch (C4DM, Queen Mary) |
| **[QM Vamp Plugins](https://github.com/c4dm/qm-vamp-plugins)** | GPL-2.0+ | Centre for Digital Music (Queen Mary) |
| **[Vamp Plugin SDK](https://github.com/c4dm/vamp-plugin-sdk)** | MIT / BSD-3 | C4DM |
| **[Sonic Annotator](https://github.com/sonic-visualiser/sonic-annotator)** | GPL-2.0+ | Chris Cannam / QMUL |
| **[FFmpeg](https://ffmpeg.org)** | GPL-3.0 | FFmpeg team |
| **[Lucide](https://lucide.dev)** (icones) | **ISC** (+ MIT de **[Feather](https://feathericons.com)**, © Cole Bemis) | Lucide contributors |
| **[libsndfile](https://libsndfile.github.io/libsndfile)** | LGPL-2.1+ | Erik de Castro Lopo |
| **[libvamp-hostsdk](https://github.com/c4dm/vamp-plugin-sdk)** | MIT / BSD-3 | C4DM |
| **[libFLAC](https://xiph.org/flac)** · **[libogg](https://xiph.org/ogg)** · **[libvorbis](https://xiph.org/vorbis)** · **[libopus](https://opus-codec.org)** | BSD-3-Clause | Xiph.Org |
| **[mpg123](https://www.mpg123.de)** · **[LAME](https://lame.sourceforge.io)** | LGPL-2.1 / LGPL-2.0 | mpg123 / LAME project |
| **[AppImageKit](https://github.com/AppImage/AppImageKit)** | MIT | AppImage comunitat |

> Les icones de la UI són de **Lucide** (**ISC**); algunes deriven de
> **Feather** (**MIT**, © 2013-present Cole Bemis). El text complet de totes
> dues llicències és a [`icones/LICENSE`](icones/LICENSE).

Sense aquest ecosistema, aquest projecte no seria possible. Els agraïments i el reconeixement formal són part de la forma de treball i del respecte que es mereixen les eines i els desenvolupadors que ens han donat base i inspiració.

## Llicència

GPL-3.0-or-later (GPLv3 o posterior) — vegeu `LICENSE`.
Copyright (c) 2026 Pëp <pepelocotango@gmail.com>.


## Formats d'àudio acceptats

L'app treballa amb **WAV PCM 16 bits**, però `Obre…` accepta també
**mp3, aif/aiff, flac, m4a, ogg, opus, wma…** i els converteix
automàticament amb **ffmpeg** (vegeu `app/ffmpeg.py`).

---
**Visita el portal de projectes:** [https://pepelocotango.github.io](https://pepelocotango.github.io)
---
