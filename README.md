# PROJECTE AUTO CHORDS

> **AUTO CHORDS** analitza un àudio i n'extreu els **acords** i l'**estructura**
> (motor Chordino + Queen Mary). Els pots **revisar i editar** en un visor
> estil DAW i **exportar** els clips **WAV** per al Live/Reaper, més la
> **partitura** (MusicXML/PDF). App d'escriptori **multi-SO** (Linux · Windows · macOS).

> **Repositori:** https://github.com/Pepelocotango/PROJECTE-AUTO-CHORDS
> (les versions publicades, com l'**AppImage**, són a *Releases*).

> **Novetats v0.5.1 (BETA):** **multi-SO** — a més de l'**AppImage de Linux**,
> el CI construeix i empaqueta **Windows x64** i **macOS 10.13+** (host i
> plugins compilats al runner; `qm-vamp-plugins` des de font). **AppImage
> autocontinguda** (un sol fitxer executable) i **GitHub Actions** (builds
> manuals + Release en tag). **Icones professionals** (Lucide). **Compàs 1
> automàtic** (`🧭`, Queen Mary) i **motors d'autodetecció triables** (BPM:
> nostre/qm/**consens**; estructura: **qm-segmenter**). `qm-vamp-plugins`
> (sense AVX) i **coherència del play**. De v0.3.0: tap tempo
> (`TAP`/`T`), botó **📍**, **×2/÷2**, diàleg d'opcions, **import ffmpeg** i
> franja **Editor**.

## Estat actual (2026-10-08 · v0.5.1 BETA)

L’app està **reorganitzada amb el timeline com a centre de la finestra**
(estil Audacity/DAW): l’anàlisi és una **acció** sobre el que es veu, no un
pas d’assistent.

- En obrir un àudio (**Fitxer ▸ Obre…**, `Ctrl+O`) es mostren l’ona i el
  timeline **de seguida**, amb les pistes Acords/Estructura buides.
- **Barra de menús**: Fitxer · Edita · Selecciona · Visualitza · Analitza · Ajuda.
- **Barra de temps** fina: mode **BPM · compàs** / **Lliure (hh:mm:ss)**,
  BPM, botons **×2/÷2**, **🎯 Detecta** (motor triable), **TAP**, compàs,
  Offset amb **📍** (cursor) i **🧭** (automàtic) i «Inclou estructura».
- **Barra de transport** pròpia: play/stop, −10s/+10s, loop A/B, zoom i mute
  (`Espai` = play/stop).
- **Metrònom** 🥁 (només en mode BPM · compàs), amb **volum propi** (60 %).
- **Analitza** (`F5`): progrés a la **barra d’estat**; el **log** és un tauler
  plegable a baix (**Visualitza ▸ Mostra el log**).
- **Exporta…** (`Ctrl+E`) a Fitxer; desactivat fins que hi ha resultat.
- **Edició al timeline**: desfer/refer (`Ctrl+Z`/`Ctrl+Y`), `Delete`, `Ctrl+D`
  (duplica) i **menú contextual** (botó dret). Mai toca els WAVs generats.
- **Multi-selecció i porta-retalls**: `Ctrl+clic` (afegir/treure) i `Shift+clic`
  (rang); `Ctrl+C`/`Ctrl+X`/`Ctrl+V` (copiar/retallar/enganxar al cursor) i
  `Ctrl+D` per duplicar **tot el grup**; arrossegar un clip seleccionat mou el
  grup sencer. El regle mostra el **mode** (`120 BPM · 4/4` o `Lliure`).
- **Inspector** (**Visualitza ▸ Mostra l’inspector**): llistes d’acords i
  estructura (clic per saltar, doble-clic per editar, menú contextual).
- Compassos de **qualsevol mètrica** (3/4, 6/8, 5/4…), no només 4/4.

La funcionalitat principal està validada: **224 tests · OK (1 skip)** (`python -m unittest tests.test_pipeline_export tests.test_partitura`).

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
4. Fes `Exporta`

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

- La carpeta temporal per defecte és `temp/` a l’arrel del projecte.
- Es pot sobreescriure amb la variable d’entorn **`AUTO_CHORDS_TEMP`**
  (camí absolut o relatiu), útil per a fluxos de treball personalitzats:

```bash
export AUTO_CHORDS_TEMP=/home/user/tmp_auto_chords
python -m app.visor tema.wav
```

## Llançament

Des de la carpeta del projecte:

```bash
python -m app.main
```

O directament amb:

```bash
./AUTO_CHORDS.sh
```

També hi ha llançador de desktop:

```bash
./AUTO_CHORDS.desktop
```

## Estructura clau

- `app/main.py` — finestra principal i flux d’usuari
- `app/visor.py` — visor integrat, llistes, navegació, edició manual
- `app/timeline.py` — regle, graella, carrils i clips (QGraphicsView)
- `app/pipeline.py` — extracció, exportació, normalització
- `app/tempo.py` — detecció de BPM (numpy, sense AVX)
- `app/metronom.py` — clic del metrònom mesclat al buffer
- `app/vamp_params.py` — paràmetres dels plugins Vamp (descriptors `.n3`)
- `app/dialegs.py` — diàleg d’opcions d’autodetecció
- `app/postproc.py` — neteja posterior dels acords
- `app/ffmpeg.py` — import d’altres formats (conversió a WAV)
- `app/theme.py` — tema centralitzat
- `eines/vamp_host.cpp` — **host Vamp propi** (`vamp_host_local`), sense Qt6
- `eines/` — `crea_portable.sh`, `compila_vamp_host.sh`, `empaqueta_portable.sh`
- `portable/` — Python + ffmpeg portables (entrada de build, gitignorat)
- `AUTO_CHORDS.sh` — llançador (prefereix el Python portable)

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
> **Windows (x64)** i **macOS (High Sierra 10.13+)**. **Els 3 builds surten
> VERDS**; estat i artefactes: **`docs/ESTAT_MULTI_SO.md`**.
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

Les versions publicades (AppImage) són a
**https://github.com/Pepelocotango/PROJECTE-AUTO-CHORDS** → *Releases*.

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
Tres workflows a `.github/workflows/`:

| Workflow | Quan s'activa | Què fa |
|----------|---------------|--------|
| **`build-appimage.yml`** | **només manual** (GitHub ▸ Actions ▸ Run workflow) | Construeix l'AppImage de **Linux** i la deixa com a **artefacte** descarregable |
| **`build-windows.yml`** | **només manual** | Construeix el paquet portable de **Windows x64** (MSYS2 + PyInstaller `--onedir`) i el deixa com a **artefacte** (ZIP) |
| **`build-macos.yml`** | **només manual** | Construeix el **`.app` de macOS 10.13+** (Intel; PyInstaller) i el deixa com a **artefacte** (ZIP) |
| **`release.yml`** | en **pujar un tag `v*`** | Construeix l'AppImage i crea un **Release (esborrany)** amb títol `AUTO CHORDS v<versió>`, el cos **en català** (de `CHANGELOG.md` via `eines/notes_release.py`) i l'AppImage adjunta |

```bash
git tag v0.5.1 -m "..." && git push origin v0.5.1   # -> Release esborrany
```
> El Release es crea com a **esborrany**: el revises a GitHub ▸ Releases i el
> publiques tu. Cap workflow fa `git push` al repositori.

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
| **RAM / disc** | ~1 GB RAM lliure · ~170 MB a disc (l'AppImage és un sol fitxer) |
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

GPLv3 — vegeu `LICENSE`.
Copyright (c) 2026 Pëp <pepelocotango@gmail.com>.


## Formats d'àudio acceptats

L'app treballa amb **WAV PCM 16 bits**, però `Obre…` accepta també
**mp3, aif/aiff, flac, m4a, ogg, opus, wma…** i els converteix
automàticament amb **ffmpeg** (vegeu `app/ffmpeg.py`).
