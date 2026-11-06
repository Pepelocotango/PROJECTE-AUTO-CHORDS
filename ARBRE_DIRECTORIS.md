# ARBRE DE DIRECTORIS — PROJECTE AUTO CHORDS

> **Per a agents:** aquest fitxer és el mapa de navegació del repositori. No és un
> `tree` exhaustiu: descriu **tot el que és rellevant** i resumeix les carpetes
> generades o binàries (`.venv/`, `.deps/`, `portable/`, `CORPUS/`, `node_modules/`)
> amb el recompte de fitxers, perquè no amaguen res important.
>
> **Font de veritat:** el codi. Els `.md` expliquen intenció; si divergeixen, mana
> el codi. L'abast del producte és a `AGENTS.md`; el contracte, a
> `docs/REGLES_DE_LA_APP.md`.
>
> **Omissió deliberada:** `.git/` (intern de Git) i el contingut profund de les
> carpetes generades/binàries, que se citen amb el recompte de fitxers.
>
> **Actualitzat:** 2026-11-06. Convencions: 🟢 versionat · 🟡 local/generat (no versionat).

## 1. Mapa ràpid: on mirar segons la tasca

| Tasca | Comença per |
|---|---|
| Entendre l'abast i les regles | `AGENTS.md` → `docs/REGLES_DE_LA_APP.md` |
| Estat actual / relleu de sessió | `ROADMAP.md` §2 · `CHANGELOG.md` |
| Entorn, build i CI | `DEVELOPING.md` · `eines/` · `.github/workflows/` |
| GUI i interacció | `app/main.py` · `app/visor.py` · `app/timeline*.py` · `app/*_ui.py` |
| Tempo, compàs, graella i metrònom | `app/tempo*.py` · `app/beats.py` · `app/graella.py` · `app/metronom.py` · `app/mapa_tempo.py` |
| Acords, estructura i export | `app/pipeline*.py` · `app/xifrat.py` · `app/partitura.py` · `app/projecte.py` |
| Reproducció i edició d'àudio | `app/audio_out.py` · `app/audio_edit.py` · `app/exporta_audio.py` |
| Tests i regressions | `tests/` |
| Documentació viva | `docs/` (5 docs de contracte + `docs/recerca/`) |

## 2. Arbre del projecte

```text
PROJECTE AUTO CHORDS/
├── 00PER FER/ 🟢                   # Plans, auditories i instruccions pendents (62 fitxers).
│   ├── DECISIONS_RUBATO.md         # Subplà de rubato i doble graella.
│   ├── PLA_FLUX_MARCADORS_BEATS.md # Pla del flux de marcadors i beats.
│   ├── PLA_SIMPLIFICACIO_TEMPO.md  # Pla per fases de simplificació del tempo.
│   ├── TORNAR A REVISAR AVANS AQUEST PLA.TXT
│   └── per fer_2026-11-05/         # Paquets de canvis per blocs.
│       ├── AUDITORIA_TECNICA_2026-11-05.md
│       ├── INSTRUCCIONS_APLICACIO_LINUX.md
│       ├── scratch_bloc3.py · scratch_bloc3b.py
│       └── BLOC1…BLOC7/            # Cada bloc: DIFFS/*.patch · MODIFICATS/ (còpies) · instruccions (B1–B6).
│
├── .github/ 🟢                     # GitHub Actions (tots d'execució manual).
│   └── workflows/
│       ├── build-all.yml           # Compila els 3 SO i comprova l'inventari.
│       ├── build-appimage.yml      # Linux: AppImage.
│       ├── build-macos.yml         # macOS 10.13+: .app i .dmg.
│       ├── build-windows.yml       # Windows x64: ZIP portable.
│       ├── qualitat.yml            # Fuzzer i proves sintètiques (no bloquejant).
│       └── release.yml             # Release idempotent amb els últims artefactes verds.
│
├── .opencode/ 🟡                  # Configuració local d'OpenCode (NO versionada; 18 fitxers + node_modules).
│   ├── agents/                     # audio-dsp.md · docs.md · explorer.md · pipeline.md · reviewer.md · tester.md
│   ├── command/                    # estat.md · qualitat.md · regles.md
│   ├── skills/                     # audio-tempo/ · flux-dades/ · regles-app/ · release-higiene/ · suite-tests/ (SKILL.md)
│   ├── README.md · package.json · package-lock.json · .gitignore
│   └── node_modules/ 🟡            # ~3.649 fitxers de dependències locals (no versionat).
│
├── app/ 🟢                         # Codi de l'aplicació (54 fitxers Python + PyQt5).
│   ├── __init__.py                 # Paquet de l'aplicació.
│   ├── main.py                     # Finestra principal (`Finestra`): menús, barres, flux i projectes.
│   ├── visor.py                    # Visor DAW: ona, llistes, edició, reproducció i loop.
│   ├── timeline.py                 # Orquestrador del timeline (QGraphicsView).
│   ├── timeline_base.py            # Base compartida: geometria i snap.
│   ├── timeline_items.py           # Clips editables.
│   ├── timeline_layers.py          # Regle, graella i forma d'ona.
│   ├── temps_ui.py                 # UI de temps: BPM, compàs i offset.
│   ├── barres.py                   # Transport, snap i metrònom (F3).
│   ├── menus.py                    # Menús, dreceres i ajuda (F3).
│   ├── edicio_ui.py                # Accions d'edició delegades al visor (F3).
│   ├── projecte_ui.py              # Projectes, desat, recents, autosave i sessió (F3).
│   ├── info_box.py                 # Caixa d'informació i rotatori de consells (F3).
│   ├── feines.py                   # Workers de fils (`Feina`, `FeinaExporta`, `FilTempoTrams`).
│   ├── drag_drop_ui.py             # Helpers de drag & drop de la finestra (F3).
│   ├── dialegs.py                  # Diàleg d'opcions d'autodetecció.
│   ├── dialeg_guia_rapida.py       # Guia ràpida d'anàlisi (només informació).
│   ├── dialeg_bpm_marcadors.py     # Tria del BPM deduït dels marcadors.
│   ├── panell_xifrat.py            # Panell «Tipus d'acord».
│   ├── acord_audio.py              # Audició sintetitzada d'un tipus d'acord.
│   ├── theme.py                    # Tema centralitzat (colors i estils Qt).
│   ├── icones.py                   # Icones SVG de Lucide recolorejades.
│   ├── config.py                   # Camins i directori d'estat escrivible.
│   ├── plataforma.py               # Abstracció per SO.
│   ├── limits.py                   # Límits compartits de tempo i compàs.
│   ├── bpm_unit.py                 # Unitats de visualització del BPM.
│   ├── graella.py                  # Graella musical, snap i quantització.
│   ├── tempo.py                    # Detecció de BPM i mapa de tempo (numpy pur).
│   ├── tempo_map.py                # Motor del mapa de tempo/compàs per trams.
│   ├── tempo_ajust.py              # Ajust d'un BPM a partir de marcadors.
│   ├── beats.py                    # Detecció de beats amb motors intercanviables.
│   ├── mapa_tempo.py               # Model de `mapa_tempo.csv`.
│   ├── marcadors.py                # Marcadors humans d'inici de compàs.
│   ├── rubato.py                   # Derivació mètrica dels clips de rubato.
│   ├── metronom.py                 # Generació de clics de metrònom.
│   ├── audio_out.py                # Motors de reproducció per SO.
│   ├── audio_edit.py               # Edició segura dels extrems del WAV.
│   ├── exporta_audio.py            # Exportació de l'àudio de treball.
│   ├── ffmpeg.py                   # Import d'altres formats via ffmpeg.
│   ├── drag_drop.py                # Lectura dels fitxers d'un drag & drop.
│   ├── postproc.py                 # Neteja i post-processat de deteccions.
│   ├── projecte.py                 # Projectes autocontinguts (`.acproj`, `audio/`, backups).
│   ├── pipeline.py                 # Façana del backend.
│   ├── pipeline_model.py           # Model pur de clips i invariants.
│   ├── pipeline_io.py              # Noms segurs, escriptura atòmica i CSV.
│   ├── pipeline_vamp.py            # Host Vamp, subprocess i detectors.
│   ├── pipeline_edicio.py          # Operacions d'edició i validació.
│   ├── pipeline_mapa.py            # `mapa_tempo.csv` i `marcadors.csv`.
│   ├── pipeline_derivats.py        # Segments, locators i guia HTML.
│   ├── pipeline_estructura.py      # `estructura_ABC.csv` i WAVs de secció.
│   ├── pipeline_export.py          # WAVs d'acords, manifest i `exporta_total`.
│   ├── partitura.py                # MusicXML/PDF/MSCZ.
│   ├── xifrat.py                   # Notació canònica del xifrat (font única).
│   ├── vamp_params.py              # Paràmetres `.n3` dels plugins Vamp.
│   └── __pycache__/ 🟡              # Bytecode Python (generat).
│
├── codi_font_chordino/ 🟢          # Codi font del plugin Chordino (NNLS-Chroma; 40 fitxers).
│   ├── README · CITATION · COPYING · .hgignore · .hgtags · .travis.yml
│   ├── Makefile.inc · Makefile.linux · Makefile.mingw · Makefile.osx
│   ├── Chordino.cpp · Chordino.h · chordextract.cpp · plugins.cpp
│   ├── NNLSChroma.cpp · NNLSChroma.h · NNLSBase.cpp · NNLSBase.h
│   ├── chromamethods.cpp · chromamethods.h · Tuning.cpp · Tuning.h
│   ├── viterbi.cpp · viterbi.h · nnls.c · nnls.f · nnls.h
│   ├── nnls-chroma.n3 · nnls-chroma.cat · chord.dictold
│   ├── chordino.png · sv-screenshot-nnls-chroma.png
│   ├── releasenotes-0.2.txt · releasenotes-0.2.1.txt · releasenotes-0.3.txt
│   ├── vamp-plugin.list · vamp-plugin.map
│   └── regression/                 # expected.csv · expected-v0.2.1.csv · regression.sh
│
├── CORPUS/ 🟡                     # Corpus local d'avaluació (NO versionat; 623 fitxers).
│   ├── ANALISI_CORPUS.md           # Referència, model final i diferències per tema.
│   ├── MIREX06_BEAT/               # audio/ · anotacions_originals/ · projectes autochords app/.
│   ├── GMD_LOOPS/                  # audio/ · midi/ · projectes autochords loops_gdm/.
│   ├── Alabama Shakes - Gimme All Your Love/
│   ├── click contrafase/
│   ├── Commodores - Easy/
│   ├── cop de sort/
│   ├── Daft Punk, Pharrell Williams, & Nile Rodgers - Get Lucky (Radio Edit - feat. Pharrell Williams and Nile Rodgers)/
│   ├── David Bowie - Space Oddity/
│   ├── De res - cop de sort_55bpm_C12_8/
│   ├── Foo Fighters - Times Like These/
│   ├── Jamiroquai - Dynamite/
│   ├── Jamiroquai - Feels Just Like It Should/
│   ├── Radiohead - High and Dry/
│   ├── Sitting On The Dock Of The Bay - Otis Redding -/
│   └── The Chemical Brothers - All Rights Reversed (feat. The Klaxons)/
│       # Cada tema conté AUTOCHORDS_<tema>/ amb el projecte autocontingut.
│
├── docs/ 🟢                        # Contracte i documentació viva (12 fitxers).
│   ├── README.md                   # Índex de la documentació.
│   ├── REGLES_DE_LA_APP.md         # Regles d'or (1–12) i §13 (temps, compàs i graella).
│   ├── ESQUEMA_UI.md               # Font de l'esquema visual de la UI.
│   ├── ESQUEMA_UI.html 🟡          # Generat des del `.md` (no editar).
│   ├── ESQUEMA_UI.svg 🟡           # Generat des del `.md` (no editar).
│   ├── EDICIO_OPERACIONS.md        # Taula única d'operacions d'edició.
│   ├── TIPUS_XIFRAT_ACORDS.md      # Catàleg de tipus, graus i `<kind>` MusicXML.
│   ├── COMPONENTS_I_VERSIONS.md 🟡 # Inventari generat (`eines/genera_inventari.py`).
│   └── recerca/                    # Documents de recerca (no descriuen l'estat viu).
│       ├── guia_tecnica_downbeat_onsets_beats.md
│       ├── NOTACIO_XIFRAT.md
│       ├── GRAELLA_PPQ_TEMPS.md
│       └── AUTODETECCIO_OPCIONS.md
│
├── eines/ 🟢                       # Build, empaquetat i cadena de subministrament (23 fitxers).
│   ├── AutoChords-win.spec         # PyInstaller (Windows).
│   ├── launcher_pyinstaller.py     # Punt d'entrada del paquet congelat.
│   ├── crea_icona.py               # Genera `.ico`/`.icns`.
│   ├── crea_portable.sh            # Crea l'entorn portable.
│   ├── empaqueta_portable.sh       # Empaqueta el portable.
│   ├── crea_appimage.sh            # Construeix l'AppImage.
│   ├── compila_vamp_host.sh        # Compila `vamp_host_local`.
│   ├── compila_vamp_plugins.sh     # Compila els plugins QM (sense AVX).
│   ├── libreries_natives.sh        # Copia llibreries natives.
│   ├── smoke_macos.sh · verifica_minos_macos.py · prova_windows.py
│   ├── vamp_host.cpp               # Host Vamp propi (C++).
│   ├── baixa_verificat.py · baixa_icones.sh · deps_fixades.env
│   ├── genera_inventari.py         # Genera `docs/COMPONENTS_I_VERSIONS.md`.
│   ├── genera_esquema_ui.py        # Genera `docs/ESQUEMA_UI.html` i `.svg`.
│   ├── notes_release.py            # Notes de release des del CHANGELOG.
│   ├── avalua_tempo.py · explica_bpm.py · exporta_partitura.py
│   └── ordre_aleatori.py           # Suite en ordre aleatori.
│
├── icona/ 🟢                       # Icones de l'aplicació (12 fitxers).
│   ├── auto-chords-logo.svg · auto-chords.png · captura.png
│   ├── auto-chords.ico · auto-chords.icns
│   ├── auto-chords-32.png · auto-chords-48.png · auto-chords-64.png
│   └── auto-chords-128.png · auto-chords-256.png · auto-chords-512.png · auto-chords-1024.png
│
├── icones/ 🟢                      # Icones SVG de la UI (Lucide, ISC; 23 fitxers).
│   ├── play.svg · pause.svg · square.svg · rewind.svg · fast-forward.svg
│   ├── repeat-2.svg · undo-2.svg · redo-2.svg
│   ├── metronome.svg · music.svg · piano.svg · volume-x.svg · x.svg
│   ├── compass.svg · target.svg · map-pin.svg · focus.svg · maximize.svg
│   ├── zoom-in.svg · zoom-out.svg
│   ├── arrow-left-to-line.svg · arrow-right-to-line.svg
│   └── LICENSE
│
├── nnls-chroma-linux64-local/ 🟢   # Plugin Chordino compilat (local).
│   ├── nnls-chroma.so · nnls-chroma.n3 · nnls-chroma.cat · chord.dict
│
├── qm-vamp-plugins-linux64-local/ 🟢 # Plugins Queen Mary compilats (local).
│   ├── qm-vamp-plugins.so · qm-vamp-plugins.n3 · qm-vamp-plugins.cat
│
├── tests/ 🟢                       # Suite unittest offscreen (19 fitxers).
│   ├── _temporals.py               # Neteja de temporals en plegar.
│   ├── _qt_neteja.py               # Neteja de widgets Qt (evita segfaults).
│   ├── test_pipeline.py            # Pipeline, xifrat, partitura, export i contractes.
│   ├── test_pipeline_contracte.py  # Contractes del backend modular.
│   ├── test_tempo_map.py           # Mapa de tempo/compàs i validesa.
│   ├── test_tempo_trams.py         # Tempo per trams i re-tempo local.
│   ├── test_tempo_ajust.py         # Ajust de BPM amb marcadors.
│   ├── test_mapa_tempo.py          # `mapa_tempo.csv` i marcadors.
│   ├── test_beats.py               # Beats i snap.
│   ├── test_rubato.py              # Model de rubato.
│   ├── test_ancoratges.py          # Marcadors en viu.
│   ├── test_edicio.py              # Edició de clips, undo/redo i paritat #11.
│   ├── test_despatx_edicio.py      # Matriu operacions × carrils.
│   ├── test_audio_edit.py          # Edició dels extrems del WAV.
│   ├── test_exporta_audio.py       # Exportació d'àudio.
│   ├── test_drag_drop.py           # Drag & drop.
│   ├── test_avalua_tempo.py        # Avaluador de tempo.
│   ├── test_gui.py                 # GUI, avisos, projectes i esquema UI.
│   ├── test_timeline_contracte.py  # Contractes del timeline.
│   └── __pycache__/ 🟡             # Bytecode (generat).
│
├── portable/ 🟡 (~5.157 fitxers)   # Entorn portable local (regenerable).
│   ├── bin/                        # appimagetool · ffmpeg.
│   ├── lib/                        # 9 llibreries natives (FLAC, mp3lame, mpg123, ogg, opus, sndfile, vamp-hostsdk, vorbisenc, vorbis).
│   └── python/                     # ~5.146 fitxers: bin/ · include/ · lib/ · share/.
├── temp/ 🟡                        # Temporals de l'app.
│   └── visor_player.log            # Log del reproductor.
├── .venv/ 🟡 (~5.760 fitxers)      # Entorn virtual de Python (no versionat).
│   ├── bin/ · include/ · lib/ · lib64/
│   └── pyvenv.cfg · .lock
├── .deps/ 🟡 (~15.795 fitxers)     # Dependències natives aïllades (no versionat).
│   ├── usr/                        # ~15.791 fitxers extrets (include/ · lib/ · share/).
│   ├── libaubio-dev_0.4.9-4.4build1_amd64.deb
│   ├── libboost1.83-dev_1.83.0-2.1ubuntu3.2_amd64.deb
│   ├── libsndfile1-dev_1.2.2-1ubuntu5.24.04.1_amd64.deb
│   └── vamp-plugin-sdk_2.10.0-4build1_amd64.deb
│
├── ARBRE_DIRECTORIS.md 🟡          # Aquest fitxer (mapa per a agents).
├── AGENTS.md 🟢                    # Guia del projecte i contracte d'abast.
├── README.md 🟢                    # Producte: visió, instal·lació i flux.
├── DEVELOPING.md 🟢                # Entorn, mapa del codi, build i CI.
├── ROADMAP.md 🟢                   # Full de ruta i estat actual (§2).
├── CHANGELOG.md 🟢                 # Historial de canvis.
├── SECURITY.md 🟢                  # Canal de report de vulnerabilitats.
├── LLICENCIES_TERCERS.md 🟢        # Llicències de tercers.
├── LICENSE 🟢                      # GPL-3.0-or-later.
├── pyproject.toml 🟢               # Metadades i pins del paquet.
├── requirements.txt 🟢             # Dependències de Python (pins).
├── requirements-build.txt 🟢       # Pins addicionals del build.
├── instal·la_local.sh 🟢           # Instal·lació local sense sudo.
├── AUTO_CHORDS.sh 🟢               # Llançador principal.
├── AUTO_CHORDS_dev.sh 🟢           # Llançador de desenvolupament.
├── dev_reload.py 🟢                # Recàrrega automàtica en dev.
├── concatena.py 🟢                 # Genera un sol fitxer amb el codi indispensable.
├── wav_a_wavs.py 🟢                # CLI: WAV → WAVs d'acords/seccions.
├── vamp_host_local 🟡              # Host Vamp compilat (binari local).
├── .gitignore 🟢                   # Què no es versiona.
├── opencode.json 🟡                # Configuració local d'OpenCode.
├── opcions_detecta.json 🟡         # Opcions d'autodetecció recordades.
├── recents.json 🟡                 # Projectes oberts recentment.
├── auto_chords.log 🟡              # Log de l'aplicació.
└── crash_nadiu.log 🟡              # Traces de crash natiu.
```

## 3. Què és generat i què no s'ha de tocar

| Ruta | Origen | Acció |
|---|---|---|
| `docs/ESQUEMA_UI.html` · `.svg` | `eines/genera_esquema_ui.py` des de `ESQUEMA_UI.md` | Regenerar, no editar a mà |
| `docs/COMPONENTS_I_VERSIONS.md` | `eines/genera_inventari.py` | Regenerar si canvien pins |
| `app/__pycache__/` · `tests/__pycache__/` | Python | Ignorar |
| `portable/` · `.venv/` · `.deps/` | Entorn local | No versionar ni incloure al codi |
| `CORPUS/` | Corpus local d'avaluació | No versionar |
| `.opencode/` · `opencode.json` | Config local d'agents | No versionar |
| `*.log` · `recents.json` · `opcions_detecta.json` · `crash_nadiu.log` | Estat local | No versionar |

## 4. Ordre de lectura recomanat per a un agent

1. `AGENTS.md` (abast, fora d'abast i decisions congelades).
2. `docs/REGLES_DE_LA_APP.md` (contracte; si el codi no el compleix, és un bug).
3. `app/projecte.py` i `app/pipeline_model.py` (model, cru i projecte).
4. `ROADMAP.md` §2 (estat i relleu de sessió).
5. El mòdul concret que toqui; després, els tests que el fixen.

## 5. Ordres ràpides

```bash
# Suite (ha d'estar verda)
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests

# Estil
.venv/bin/python -m pyflakes app/*.py tests/*.py

# Smoke de l'app
AUTO_CHORDS_SMOKE=1 QT_QPA_PLATFORM=offscreen .venv/bin/python -m app.main

# Regenerar artefactes de docs
.venv/bin/python eines/genera_esquema_ui.py
.venv/bin/python eines/genera_inventari.py

# Tests en ordre aleatori
.venv/bin/python eines/ordre_aleatori.py 3
```
