# Desenvolupament — PROJECTE AUTO CHORDS

Tot en català. Llicència: GPL-3.0-or-later (vegeu `LICENSE`).

> 🔴 **ABANS DE TOCAR CODI**: les **regles d'or (invariants)** de l'app són totes
> a **`docs/REGLES_DE_LA_APP.md`**. Cap canvi no les pot trencar; només es canvien
> amb **OK explícit de l'operador** i queda constància al `CHANGELOG`.
>
> ⚠️ Document orientatiu: **vegeu `AGENTS.md`**.

## Requisits

- Python 3.10+ (stdlib; sense pip per al pipeline). Coincideix amb `requires-python` del `pyproject.toml`.
- Per a l'app: PyQt5 del sistema (`python3-pyqt5`, Qt5).
  ⚠️ Qt6 **no** corre en CPU sense SSE4.2 (com el Q9400): no s'hi pot
  usar PySide6/PyQt6.
- **plugins Vamp** a les carpetes `*-local/`: **`nnls-chroma`** (Chordino,
  acords) i **`qm-vamp-plugins`** (Queen Mary: tempo/beats/bars/segmenter/key
  — `app/pipeline.py`). El **Segmentino** i l'**aubio** s'han retirat
  (v0.5): l'estructura la fa el `qm-segmenter` i el BPM el `tempo.py`/`qm`.
- **`ffmpeg`** — opcional, només per importar formats que no siguin WAV
  (`app/ffmpeg.py`); s'embega a `portable/bin/ffmpeg` (fase 3).
- **Àudio**: a Linux cal **PipeWire** o **PulseAudio** per ESCOLTAR (reproductor
  `paplay`, o `aplay` d'ALSA de reserva). A macOS i Windows l'app reprodueix
  directament dins el procés mitjançant el motor natiu d'àudio (`app/audio_out.py`
  sobre PortAudio / `sounddevice` — CoreAudio a macOS i WASAPI a Windows).

## Entorn aïllat (Ubuntu, sense sudo)

```bash
bash instal·la_local.sh   # crea .venv/ + runtime + eines de qualitat (pyflakes/coverage)
.venv/bin/python app/main.py
.venv/bin/python wav_a_wavs.py tema.wav 138 4 [offset]
```

* Python: stdlib + PyQt5 en `.venv/` (rodes, sense apt).
* C++ (`chordextract`): headers a `.deps/usr/include` (descarregats, no instal·lats); binari de prova a `temp/chordextract`, sense substituir l'annotator.
* `.deps/` i `.venv/` no es commitegen.

## Matriu ferro → eina (Q9400 + Ubuntu 24, verificada 01-10-2026)

Ferro: Q9400 **sense AVX** (`grep avx` buit), SSE4.1. So del sistema:
**PipeWire 1.0.5 + pipewire-pulse**. Qualsevol canvi d'eina ha de passar
aquest filtre o mor al SIGILL / violació de segment.

| Eina | Veredicte | Motiu (verificat) |
|---|---|---|
| `wave` stdlib | ✅ fem servir | Zero dependències; millor que `soundfile` |
| `numpy` 1.26 (`numpy<2`) | ✅ fixat | El 2.x demana x86_64-v2 (SSE4.2) → `RuntimeError` al Q9400 |
| PyQt5 + QtSvg | ✅ fem servir | Rodes amb Qt5; Qt6-GUI/PySide6 demana SSE4.2 |
| `paplay --raw` (libpulse → PipeWire) | ✅ fem servir | Camí natiu Ubuntu 24 amb mescla; `aplay` (ALSA directe) només de reserva |
| `QAudioOutput` QtMultimedia | ❌ aparcat | Les rodes SÍ porten plugins (`libqtaudio_alsa.so`); el segfault era format/QBuffer, però `paplay` té stderr visible i zero acoblament Qt — no es reobre sense motiu |
| `sounddevice` (PortAudio) | ✅ fem servir a macOS/Win | Motor natiu d'àudio (`app/audio_out.py`) per a CoreAudio (macOS) i WASAPI/MME (Windows). A Linux es manté `paplay`. |
| Chordino + QM (`qm-segmenter`…) via **host propi** | ✅ fem servir | Únic motor: `vamp_host_local` (`app/pipeline.py`) |
| **`qm-vamp-plugins`** (Queen Mary) | ✅ fem servir | Compilats del codi font amb `-msse -msse2` (**sense AVX**); `eines/compila_vamp_plugins.sh` |
| **`ffmpeg`/`ffprobe`** del sistema | ✅ fem servir | Import d'altres formats → WAV PCM16; no cal per WAV |
| `librosa` / `madmom` / `essentia` (pip) | ❌ no provat | El `tempo.py` propi + el `qm-tempotracker` ja cobreixen el BPM (5/5 i 4/5 amb 11 temes reals) |
| `librosa` / `Essentia` | ❌ descartats | `llvmlite`/AVX (SIGILL) i AGPL3 respectivament |
| `music21` (BSD, pur Python) | 🔶 futur | Per a normalitzar noms d'acords (substitueix el `style()` casolà) |

## Arrencar l'app (sistema)

```bash
bash AUTO_CHORDS.sh
# o bé:
python3 app/main.py
```

## Pipeline manual

```bash
# Extracció directa amb el host propi (el mateix que fa l'app):
VAMP_PATH=nnls-chroma-linux64-local ./vamp_host_local \
  --plugin nnls-chroma:chordino:simplechord --csv out.csv tema.wav

# Segments (posició · acord · durada en temps) i guia, en memòria:
python3 -c "from app import pipeline as p; \
print(p.segments_locators('acords.csv', 138, 4, 0.0, durada=180.0))"
```

> La guia DAW (segments + `guia_acords.html`) es genera **en memòria** dins
> `app/pipeline.py` (`segments_locators` / `genera_guia_html`): no hi ha cap
> fitxer intermedi (`acords_locators.txt`) ni cap subprocés de Python.

## Comandes essencials

> La font de veritat és el **`Makefile`**. Ací només el resum; `make help` en
> llista totes.

<!-- GENERAT: comandes — no editar a mà -->
```bash
make entorn        # instal·la l'entorn local (sense sudo)
make app           # arrenca l'app
make compile       # compilació ràpida (no arrenca l'app)
make test          # suite completa (offscreen)
make lint          # pyflakes
make smoke         # smoke de l'app
make docs          # regenera les vistes i els documents generats
make docs-check    # comprova que els documents generats estan al dia
make aleatori      # suite en ordre aleatori
make coverage      # suite amb informe de cobertura
make check         # compile + lint + suite sencera + docs-check (lent)
make commit-check  # compile + lint + docs-check (ràpid, per commit)
make commit        # afegeix-ho tot, regenera docs, commit-check i commit (MSG=\"...\")
```
<!-- /GENERAT: comandes -->

**Mapa de funcionalitats (ODF).** `make docs` també regenera
`docs/FUNCIONALITATS_AUTO_CHORDS.ods` a partir de
`eines/funcionalitats_dades.json` (una fila per línia, editable). No editis
l'ODS a mà: canvia el JSON i torna a executar `make docs`; `make docs-check`
falla si l'ODS no hi coincideix. Cal `odfpy` (ja és a
`requirements-dev.txt`). El ZIP es reescriu amb dates fixes perquè el guardat
siga determinista i no genere diffs binaris innecessaris.

**Higiene dels temporals**: la suite **no ha de deixar res** al disc. Tots els
fitxers de test importen **`tests/_temporals.py`**, que intercepta
`tempfile.mkdtemp` / `mkstemp` / `NamedTemporaryFile`, anota el que es crea i ho
esborra en plegar el procés (`atexit`). Abans una tongada deixava ~1.000 carpetes
i ~1,3 GB, i se n'hi van acumular **57 GB** (disc al 97%). **Si afegeixes un test
nou, importa'l també** (dues línies al costat del `sys.path.insert`).

## Paranys i trampes conegudes

- **Si hi ha una app viva, porta el codi vell en memòria**: cal **reiniciar-la**
  perquè els canvis del disc hi entren.
- **Missatges en català dins comandes `bash`** amb accents o *backticks*: fes
  servir **heredocs** (`python3 - <<'PY' … PY`), no `-c "..."` (els *backticks*
  es substitueixen i mutilen el text).
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
- **`OLD/` és gitignored**: material retirat que no es puja al repo.

## Retrocompatibilitat

Vegeu **`AGENTS.md`** (decisió vigent, no invariant).

## Lògica de producte i flux de treball

> L'**abast i el flux d'usuari vigent** és a
> [`AGENTS.md` §Abast i flux](AGENTS.md#-abast-i-flux-de-lusuari--font-única).
> Aquesta secció descriu només el **flux intern del backend**; no redefineix el
> producte.

La base del projecte és senzilla i molt important: no hauríem de tenir un “analitzador” separat, un “editor” separat i un “exportador” separat que no comparteixen model.

### Model i regles

> El model (CSVs, intervals i segons) i les regles de consistència viuen als
> docstrings de **`app/projecte.py`** i **`app/pipeline_model.py`**, i al
> contracte **`docs/REGLES_DE_LA_APP.md`**. No es dupliquen ací.

### Implementació del contracte de temps

> El contracte (què és invariant) és a `docs/REGLES_DE_LA_APP.md` §13. Ací hi ha
> el mapa regla → codi → test i les notes d'implementació.

| Regla / secció | Codi | Test |
|---|---|---|
| #1 ordre estricte | `visor._valida_canvis_*`, `tempo_map.neteja_trams`, `afegeix_tall` | `test_edicio.py::TestRegla1OrdreEstricte`, `test_tempo_map.py::TestEdicioMapa` |
| #2 contigüitat | `timeline.py`, `pipeline.filtra_seccions`, `tempo_map.neteja_trams` | `test_edicio.py` (contigüitat), `test_tempo_map.py::TestEdicioMapa` |
| #3 durades derivades | model de clips (`pipeline_model.py`, `mapa_tempo.py`) | `test_edicio.py::TestRegla3DuradesDerivades` |
| #4 cobertura total | `pipeline.normalitza_cobertura()` | `test_edicio.py::TestCoberturaViu` |
| #5 font de veritat | `visor.py` (refresc únic del mapa) | `test_edicio.py::TestRegla5FontDeVeritat` |
| #6 WAVs musicals | `pipeline_export.py` (`exporta_total`) | `test_edicio.py::TestRegla6WavsNomesViaExporta`, `test_pipeline_contracte.py` |
| #7 instància única | `plataforma.bloqueja_instancia_unica` | `test_edicio.py::TestRegla7InstanciaUnica` |
| #8 temps vàlids | `visor._valida_canvis_*`, `pipeline.normalitza_cobertura`, `tempo_map.normalitza_trams` | `test_edicio.py::TestRegla8TempsValids` |
| #9 portabilitat | `eines/verifica_minos_macos.py`; builds sense AVX | `test_pipeline.py::GuardAvxTests` |
| #10 estat escriptible | `app/config.py` (`DADES_DIR`) | `test_edicio.py::TestRegla10EstatEscriptible` |
| #11 paritat d'edició | `visor.executa_edicio` i nuclis d'edició | `test_despatx_edicio.py`, `test_edicio.py::TestBackendParitat` |
| #12 paritat d'exportació | `pipeline.exporta_total(..., mapa_tempo=)` | `test_pipeline.py::TestRegla12ParitatExport` |
| §13.1 segons | `visor._regenera_posicions_musicals`, `tempo_map` | `test_despatx_edicio.py::TestPosicionsMusicals` |
| §13.2 clips manen | `tempo_map.TempoMap`, `visor._refresca_tempo_map` | `test_tempo_map.py::TestCanviDeTempo`, `test_tempo_map.py::TestCanviDeCompas` |
| §13.3 cobertura del mapa | `tempo_map.neteja_trams`, `TempoMap.__init__`, `visor._refresca_tempo_map` | `test_tempo_map.py::TestEdicioMapa`, `test_tempo_map.py::TestCompassosEnters` |
| §13.4 valors, mínim i `N` | `tempo_map.valida_tempo`, `valida_i_normalitza_permissiu`, `limits.TEMPS_MIN_CLIP`, `neteja_trams` | `test_tempo_map.py::TestValidaTempo`, `test_tempo_map.py::TestCompassosEnters` |
| §13.5 recalcul guiat | `mapa_tempo.recalcula_tram_c`, `tempo_recalc.recalculca_tram`, `tempo_map.mou_frontera_retempo`, `ajusta_bpm_a_compassos` | `test_tempo_recalc.py`, `test_tempo_trams.py`, `test_despatx_edicio.py::TestCompassosTempo` |
| §13.6 fronteres i marcadors | `tempo_map.mou_frontera_retempo`, `visor._on_tempo_mogut`, `visor._aplica_editor_tempo`, `marcadors` | `test_tempo_trams.py`, `test_edicio.py` (undo/marcadors) |
| §13.7 rubato | `mapa_tempo.py`, `tempo_map`, `visor_tempo`, `partitura` | `test_tempo_map.py::TestRubatoComANormal`, `test_edicio.py::TestRubatoAccions` |
| §13.8 detecció | `tempo_map.retempo_tram_detectat`, `tempo_recalc.recalculca_tram`, `tempo.py`, `pipeline.desa_tempo_map` | `test_tempo_trams.py` (retempo detectat), `test_tempo_map.py` |
| §13.9 edició d'àudio | `audio_edit.py`, `exporta_audio.py`, `projecte.py` | `test_audio_edit.py`, `test_exporta_audio.py`, `test_edicio.py::TestUndoTemps` |

La **validació estricta** (`valida_i_normalitza_compassos`,
`_millora_signatures_clips`, `ajusta_bpm_a_compassos`, `retempo_tram_detectat`)
es reserva per als **detectors** i les **accions explícites**; **no és el camí
general d'edició**.

Notes d'implementació:

- En **carregar** un projecte es fusionen els trams adjacents amb el mateix BPM
  i compàs; una partició manual de dos trams iguals es respecta mentre s'edita.
- Totes les edicions de la GUI que re-temporitzen passen pel **re-tempo local**;
  si el resultat no complix el contracte, no es toca res i s'avisa.
- Quan el model es reconstrueix (quantitzar, desfer…), la selecció es notifica
  buida i l'editor es buida o refresca: mai el temps vell d'un clip mogut.

### Flux implementat

1. la WAV s’obre a l’app principal
2. `Processa` extreu acords i, si escau, estructura
3. el visor carrega la ona, els acords i les seccions generades
4. l’usuari pot corregir acords, afegir o esborrar seccions, i normalitzar l’ordre
5. cada canvi es valida: no solapaments, no ordre invers, no duplicats lògics
6. el visor regenerat els clips i les sortides associades
7. `Exporta WAV's` genera el paquet final per a DAW

### Filosofia de disseny

L’arquitectura està pensada perquè el producte sigui un flux de treball coherent i no una col·lecció de scripts amb criteris diferents. Per això:

- una sola app front-end
- un únic model intern de temps
- un únic runtime de regeneració
- una única acció d’export final
- una validació d’edició que protegeix el dataset i evita “malformacions” que després trenquen la producció

El resultat és un sistema fàcil d’entendre, reproduïble i segur d’editar.

## Àrees de futur

> La llista viva és a **`ROADMAP.md` §5–§6**. No es duplica ací.

## Agraïments

Vegeu **`LLICENCIES_TERCERS.md`**.

## Mòduls de l'app (`app/`)

<!-- GENERAT: moduls — no editar a mà -->
| Mòdul | Responsabilitat |
|-------|-----------------|
| `acord_audio.py` | Àudio per ESCOLTAR un tipus d'acord — piano elèctric sintetitzat (numpy pur). |
| `analisi_ui.py` | Accions d'anàlisi de la finestra (F3). |
| `audio_edit.py` | Edició destructiva i segura dels extrems d'una WAV PCM 16 bits. |
| `audio_out.py` | Sortida d'àudio: motors de reproducció (un per SO, mateixa interfície). |
| `barres.py` | Barra de transport, snap i metrònom (F3). |
| `beats.py` | Detecció de beats amb motors intercanviables i sensibilitat ajustable. |
| `bpm_unit.py` | bpm_unit.py — unitat de visualització del BPM (negra, negra amb punt…). |
| `camp_text.py` | Camps de text de l'app amb l'inici sempre visible. |
| `config.py` | Camins de l'app i tria d'un directori d'estat ESCRIPTIBLE. |
| `dialeg_analitza_bpm.py` | Diàleg d'anàlisi de BPM/beats. |
| `dialeg_canvi_unitat.py` | Canvi explícit d'unitat de pols (clip o Ref. recalc). |
| `dialeg_dreceres.py` | Diàleg per veure i canviar totes les dreceres de teclat. |
| `dialeg_guia_rapida.py` | Guia ràpida d'«Anàlisi guiat» — **només informació**, pas a pas. |
| `dialeg_opcions.py` | Diàleg d'opcions d'autodetecció (BPM/acords/estructura). |
| `dialeg_quantitza.py` | Diàleg de quantització a la graella. |
| `dialeg_tempo_mapa.py` | Diàleg del mapa de tempo per trams. |
| `dialeg_tempo_per_trams.py` | Diàleg de detecció de tempo per trams. |
| `dialeg_tram_tempo.py` | Diàleg per editar un tram de tempo/compàs. |
| `dialeg_troba.py` | Diàleg de trobar i reemplaçar xifrats o etiquetes. |
| `dialegs.py` | Façana dels diàlegs d'AUTO CHORDS. |
| `drag_drop.py` | Fitxers d'àudio que es poden arrossegar des del gestor de fitxers. |
| `drag_drop_ui.py` | Helpers de drag & drop de la finestra (F3). |
| `dreceres.py` | Dreceres de teclat: valors per defecte, càrrega i desat. |
| `dreceres_ui.py` | Configuració de dreceres de la finestra (menú, globals i timeline). |
| `edicio_ui.py` | Accions d'edició de la finestra (F3). |
| `export_ui.py` | Exportació de la finestra (F3). |
| `exporta_audio.py` | Exportació de l'àudio de treball a altres formats (Fase 6). |
| `feines.py` | Workers de fils de la finestra (F3). |
| `ffmpeg.py` | Import d'altres formats d'àudio via ffmpeg. |
| `finestres.py` | Geometria persistent de la finestra principal i dels diàlegs. |
| `graella.py` | Graella musical — divisions, snap i quantització (stdlib pur). |
| `icones.py` | Icones de la UI: SVG de Lucide (llicència ISC, https://lucide.dev). |
| `info_box.py` | Caixa d'informació i rotatori de consells de la finestra (F3). |
| `limits.py` | Límits compartits per a l'edició del tempo i el compàs. |
| `main.py` | finestra principal, menús, barres, flux d'usuari i projectes |
| `mapa_tempo.py` | Model unificat del mapa de tempo/compàs (`mapa_tempo.csv`). |
| `marcadors.py` | Marcadors humans de la cançó (inici de compàs, en viu). |
| `marcadors_ui.py` | Marcadors en viu de la finestra (F3). |
| `menus.py` | Menús, dreceres i ajuda de la finestra (F3). |
| `metronom.py` | metronom.py — generador de clics de metrònom (numpy pur, sense Qt). |
| `opcions.py` | Opcions persistents i valors per defecte dels diàlegs. |
| `panell_xifrat.py` | Panell «Tipus d'acord» — construeix un xifrat clicant (dock de l'esquerra). |
| `partitura.py` | Exportació de partitura (xifrat) des dels resultats d'Auto Chords. |
| `pipeline.py` | façana del backend (re-exporta els símbols públics) |
| `pipeline_derivats.py` | Derivats de guia i exportació (F1): segments, locators i guia HTML. |
| `pipeline_edicio.py` | Operacions d'edició i validació del model de clips (F1). |
| `pipeline_estructura.py` | Estructura ABC i WAVs de seccions (F1). |
| `pipeline_export.py` | Exportació de WAVs silenciosos i paquet complet (F1). |
| `pipeline_io.py` | Fitxers, noms segurs i escriptura atòmica d'AUTO CHORDS (F1). |
| `pipeline_mapa.py` | Mapa de tempo i marcadors del projecte (F1). |
| `pipeline_model.py` | Model pur de clips d'AUTO CHORDS (refactor F1 de `pipeline.py`). |
| `pipeline_vamp.py` | Motor Vamp d'AUTO CHORDS (F1): host, subprocess i detectors. |
| `plataforma.py` | Abstracció de plataforma: tot el que canvia entre Linux, Windows i macOS. |
| `postproc.py` | Post-processat de les deteccions (opcions del diàleg d'autodetecció). |
| `projecte.py` | Projectes d'AUTO CHORDS — carpeta **autocontinguda**, com un DAW. |
| `projecte_ui.py` | Gestió de projectes de la finestra (F3). |
| `tap_ui.py` | Tap tempo de la finestra (F3). |
| `tempo.py` | tempo.py — detecció de BPM i mapa de tempo (numpy pur, sense Qt). |
| `tempo_map.py` | Mapa de TEMPO i COMPÀS variables — el «motor» (stdlib pur). |
| `tempo_midi.py` | Exportació del mapa de tempo/compàs a MIDI (Standard MIDI File tipus 1). |
| `tempo_recalc.py` | Motor pur de recalcul del mapa de temps (F0). |
| `temps_ui.py` | UI de temps de la finestra (F3): BPM, compàs i offset. |
| `theme.py` | tema centralitzat (colors i estils Qt) |
| `timeline.py` | timeline.py — Editor visual de la pista tipus DAW (QGraphicsView). |
| `timeline_base.py` | timeline_base.py — Base compartida de l'editor de timeline (DAW). |
| `timeline_geometry.py` | Geometria pura del timeline (F2). |
| `timeline_items.py` | timeline_items.py — Elements editables de l'editor de timeline (DAW). |
| `timeline_layers.py` | timeline_layers.py — Capes de fons de l'editor de timeline (DAW). |
| `vamp_params.py` | Llegeix els paràmetres ajustables dels plugins Vamp (descriptors .n3). |
| `visor.py` | visor DAW: ona, llistes, edició, reproducció i loop |
| `visor_editor.py` | Franja Editor del visor (F4). |
| `visor_io.py` | Lectura de WAV i CSV del visor (F4). |
| `visor_llistes.py` | Poblament i handlers de les llistes del visor (F4). |
| `visor_marcadors.py` | Marcadors humans del visor (F4). |
| `visor_tempo.py` | Tempo i rubato del visor (F4). |
| `visor_transport.py` | Transport, loop, zoom, velocitat i metrònom del visor (F4). |
| `visor_ui.py` | Càrrega del visor i estat d'exportació (F3). |
| `xifrat.py` | Notació del xifrat d'acords — font ÚNICA (parseig + forma canònica). |
<!-- /GENERAT: moduls -->

Docs de detall a `docs/`: `ESQUEMA_UI.md` (GUI), `EDICIO_OPERACIONS.md`
(edició), `TIPUS_XIFRAT_ACORDS.md` (xifrat) i `recerca/` (onsets/beats, PPQ,
mesuraments de motors).

## Convencions

- Comentaris i docs en català.
- Sense secrets ni credencials al repo (ni claus API ni tokens).
- Els binaris natius de Linux (`*-local/*.so`, `vamp_host_local`) SÍ es
  commitegen (són l'eina); les sortides (`*_obsolets/`, `midis_acords/`) no.
- **`OLD/`** (gitignorat) és l'**arxiu local** del que no és necessari però es
  vol conservar (p. ex. versions retirades). **No es puja al repo.**

## Estructura del codi

Vegeu **`ARBRE_DIRECTORIS.md`** (arbre complet) i la taula de mòduls d'ademunt.

## Configuració

- L'estat (**temp**, log, opcions) va a un **directori d'estat escriptible**: `~/.local/state/auto-chords/` (amb `temp/` a dins). **Mai** dins el paquet.
- El directori temporal es pot sobreescriure amb la variable `AUTO_CHORDS_TEMP`:

```bash
export AUTO_CHORDS_TEMP=/home/user/tmp_auto_chords
python -m app.visor tema.wav
```

## Paquet portable (autocontingut)

```bash
eines/empaqueta_portable.sh      # -> ../AUTO_CHORDS_PORTABLE/
cd ../AUTO_CHORDS_PORTABLE && ./AUTO_CHORDS.sh
```
El paquet **no s'edita mai** (és un artefacte de build): el codi viu al repo i es regenera. Detall: `.github/workflows/`.

## AppImage

L'AppImage embolcalla el paquet portable + un `AppRun` + el `.desktop` + la icona i el comprimeix (squashfs): dels ~530 MB surt un fitxer d'**~160 MB** que s'executa a qualsevol **Linux x86_64** sense instal·lar res.

```bash
eines/crea_appimage.sh           # -> ../AUTO_CHORDS-x86_64.AppImage
```
Requereix haver fet abans `eines/crea_portable.sh` i `eines/compila_vamp_host.sh`; l'`appimagetool` es baixa sol.

> El runtime incrustat és el modern **estàtic** (`type2-runtime`, amb libfuse+squashfuse+musl a dins): **no cal `libfuse2`** al sistema (només el suport FUSE del kernel). Si el nucli tingués FUSE desactivat: `./AutoChords-*.AppImage --appimage-extract-and-run`.

## GitHub Actions (CI)

Sis workflows a `.github/workflows/` (tots d'**execució manual**):

| Workflow | Què fa |
|----------|--------|
| **`build-all.yml`** | **Agregador**: executa els 3 builds (Linux + Windows + macOS) en paral·lel |
| **`build-appimage.yml`** | Construeix l'AppImage de **Linux** i l'empaqueta en un `.tar.gz` |
| **`build-windows.yml`** | Construeix el paquet portable de **Windows x64** (MSYS2 + PyInstaller `--onedir`) → `.zip` |
| **`build-macos.yml`** | Construeix l'`.app` de **macOS 10.13+** (Intel) → `.dmg` |
| **`release.yml`** | Agafa els **últims artefactes verds** dels 3 SO i crea/actualitza el **Release** (idempotent) amb les notes en català i el `SHA256SUMS.txt` |
| **`qualitat.yml`** | Fuzzer d'invariants i proves sintètiques, **no bloquejant**; no usa cap corpus real |

> Cap workflow fa `git push` ni s'activa sol. Els paquets només porten `README.md` + `LICENSE` + `LLICENCIES_TERCERS.md`. Detall: `.github/workflows/`.
> ⚠️ Els runners de Linux són `ubuntu-22.04` (allà s'hi compila `vamp_host_local`; la glibc marca l'abast mínim de l'AppImage). Detall: `.github/workflows/`.
