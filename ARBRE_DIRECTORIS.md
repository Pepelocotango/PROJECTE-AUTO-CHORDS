# ARBRE DE DIRECTORIS — PROJECTE AUTO CHORDS

> **Per a agents:** llegeix només aquesta primera part. L'arbre complet és al
> final, plegat, per quan necessitis localitzar un fitxer concret.
>
> **Abast i font de veritat:** vegeu `AGENTS.md`. L'arbre final es **genera**
> (`make docs`); si en dubtes, verifica-ho al disc (`git status`, `find`).

## On començar

> Ordre de lectura: vegeu `AGENTS.md` §«Primers 5 minuts».

## Mapa per tasca

| Tasca | Comença per |
|---|---|
| Abast i regles | `AGENTS.md` → `docs/REGLES_DE_LA_APP.md` |
| Estat actual | `ROADMAP.md` §2 · `CHANGELOG.md` |
| GUI | `app/main.py` · `app/visor.py` · `app/timeline*.py` · `app/*_ui.py` |
| Tempo/compàs/graella | `app/tempo*.py` · `app/beats.py` · `app/graella.py` · `app/metronom.py` |
| Acords/estructura/export | `app/pipeline*.py` · `app/xifrat.py` · `app/partitura.py` · `app/projecte.py` |
| Àudio | `app/audio_out.py` · `app/audio_edit.py` · `app/exporta_audio.py` |
| Tests | `tests/` |
| Entorn i build | `DEVELOPING.md` · `eines/` · `.github/workflows/` |
| Docs vives | `docs/` (contracte + mapa de funcionalitats + `docs/recerca/`) |

## Convencions

- 🟢 versionat · 🟡 local/generat (no versionat).
- **L'arbre de davall es genera** amb `eines/genera_arbre.py` (`make docs`); no editar-lo a mà. Les descripcions dins l'arbre surten del diccionari del generador i dels docstrings; per corregir-les, edita el generador.
- **No editar a mà:** `docs/ESQUEMA_UI.html`/`.svg` (`eines/genera_esquema_ui.py`), `docs/COMPONENTS_I_VERSIONS.md` (`eines/genera_inventari.py`), la taula de mòduls de `DEVELOPING.md` (`eines/genera_moduls.py`) ni `docs/FUNCIONALITATS_AUTO_CHORDS.ods` (`eines/genera_funcionalitats.py`).
- **No versionar ni tocar:** `.venv/`, `.deps/`, `portable/`, `temp/`, `CORPUS/`, `.opencode/`, `*.log`, `recents.json`, `opcions_detecta.json`.
- `.git/` s'omet; les carpetes grans o locals es resumeixen amb recurs direkte i recompte de fitxers.

> **Comandes:** vegeu `DEVELOPING.md` §«Comandes essencials».

<details>
<summary><b>Arbre complet del projecte</b> (desplega)</summary>

<!-- GENERAT: arbre — no editar a mà -->
```text
PROJECTE AUTO CHORDS/
├── .deps/                         🟡  # Dependències natives aïllades (no versionat) (15.800 fitxers)
│   ├── libaubio-dev_0.4.9-4.4build1_amd64.deb 🟡
│   ├── libboost1.83-dev_1.83.0-2.1ubuntu3.2_amd64.deb 🟡
│   ├── libsndfile1-dev_1.2.2-1ubuntu5.24.04.1_amd64.deb 🟡
│   ├── vamp-plugin-sdk_2.10.0-4build1_amd64.deb 🟡
│   └── usr/                               🟡  # (15.796 fitxers)
├── .github/                       🟢  # GitHub Actions (6 fitxers)
│   └── workflows/ 🟢  # Workflows de GitHub Actions
│       ├── build-all.yml      🟢  # Compila els 3 SO i comprova l'inventari
│       ├── build-appimage.yml 🟢  # Linux: AppImage
│       ├── build-macos.yml    🟢  # macOS 10.13+: .app i .dmg
│       ├── build-windows.yml  🟢  # Windows x64: ZIP portable
│       ├── qualitat.yml       🟢  # Fuzzer i proves sintètiques (no bloquejant)
│       └── release.yml        🟢  # Release idempotent amb els últims artefactes verds
├── .opencode/                     🟡  # Configuració local d'OpenCode (no versionada) (18 fitxers)
│   ├── .gitignore        🟡
│   ├── package-lock.json 🟡
│   ├── package.json      🟡
│   ├── README.md         🟡
│   ├── agents/           🟡  # Agents d'OpenCode (6 fitxers)
│   ├── command/          🟡  # Comandes locals d'OpenCode (3 fitxers)
│   └── skills/           🟡  # Skills locals d'OpenCode (5 fitxers)
├── .venv/                         🟡  # Entorn virtual de Python (no versionat) (4.512 fitxers)
│   ├── .lock      🟡
│   ├── pyvenv.cfg 🟡
│   ├── bin/       🟡  # (30 fitxers)
│   ├── include/   🟡  # (0 fitxers)
│   ├── lib/       🟡  # (4.469 fitxers)
│   ├── lib64/     🟡  # (4.469 fitxers)
│   └── share/     🟡  # (11 fitxers)
├── 00PER FER/                     🟢  # Plans, auditories i instruccions pendents (58 fitxers)
│   ├── DECISIONS_RUBATO.md                🟢  # Subplà de rubato i doble graella
│   ├── PLA_FLUX_MARCADORS_BEATS.md        🟢  # Pla del flux de marcadors i beats
│   ├── PLA_SIMPLIFICACIO_TEMPO.md         🟢  # Pla per fases de simplificació del tempo
│   ├── TORNAR A REVISAR AVANS AQUEST PLA.TXT 🟢
│   └── per fer_2026-11-05/                🟢  # (54 fitxers)
├── app/                           🟢  # Codi de l'aplicació (PyQt5) (76 fitxers)
│   ├── __init__.py               🟢  # Auto Chords — paquet de l'aplicació.
│   ├── acord_audio.py            🟢  # Àudio per ESCOLTAR un tipus d'acord — piano elèctric sintetitzat (numpy pur).
│   ├── analisi_ui.py             🟢  # Accions d'anàlisi de la finestra (F3).
│   ├── audio_edit.py             🟢  # Edició destructiva i segura dels extrems d'una WAV PCM 16 bits.
│   ├── audio_out.py              🟢  # Sortida d'àudio: motors de reproducció (un per SO, mateixa interfície).
│   ├── barres.py                 🟢  # Barra de transport, snap i metrònom (F3).
│   ├── beats.py                  🟢  # Detecció de beats amb motors intercanviables i sensibilitat ajustable.
│   ├── bpm_unit.py               🟢  # bpm_unit.py — unitat de visualització del BPM (negra, negra amb punt…).
│   ├── camp_text.py              🟢  # Camps de text de l'app amb l'inici sempre visible.
│   ├── config.py                 🟢  # Camins de l'app i tria d'un directori d'estat ESCRIPTIBLE.
│   ├── dialeg_analitza_bpm.py    🟢  # Diàleg d'anàlisi de BPM/beats.
│   ├── dialeg_bpm_marcadors.py   🟢  # Triar el BPM deduït dels marcadors (llista de candidats).
│   ├── dialeg_guia_rapida.py     🟢  # Guia ràpida d'«Anàlisi guiat» — **només informació**, pas a pas.
│   ├── dialeg_opcions.py         🟢  # Diàleg d'opcions d'autodetecció (BPM/acords/estructura).
│   ├── dialeg_quantitza.py       🟢  # Diàleg de quantització a la graella.
│   ├── dialeg_revisio_snap.py    🟢  # Diàleg de revisió dels dubtes del snap.
│   ├── dialeg_tempo_mapa.py      🟢  # Diàleg del mapa de tempo per trams.
│   ├── dialeg_tempo_per_trams.py 🟢  # Diàleg de detecció de tempo per trams.
│   ├── dialeg_tram_tempo.py      🟢  # Diàleg per editar un tram de tempo/compàs.
│   ├── dialeg_troba.py           🟢  # Diàleg de trobar i reemplaçar xifrats o etiquetes.
│   ├── dialegs.py                🟢  # Façana dels diàlegs d'AUTO CHORDS.
│   ├── drag_drop.py              🟢  # Fitxers d'àudio que es poden arrossegar des del gestor de fitxers.
│   ├── drag_drop_ui.py           🟢  # Helpers de drag & drop de la finestra (F3).
│   ├── edicio_ui.py              🟢  # Accions d'edició de la finestra (F3).
│   ├── export_ui.py              🟢  # Exportació de la finestra (F3).
│   ├── exporta_audio.py          🟢  # Exportació de l'àudio de treball a altres formats (Fase 6).
│   ├── feines.py                 🟢  # Workers de fils de la finestra (F3).
│   ├── ffmpeg.py                 🟢  # Import d'altres formats d'àudio via ffmpeg.
│   ├── graella.py                🟢  # Graella musical — divisions, snap i quantització (stdlib pur).
│   ├── icones.py                 🟢  # Icones de la UI: SVG de Lucide (llicència ISC, https://lucide.dev).
│   ├── info_box.py               🟢  # Caixa d'informació i rotatori de consells de la finestra (F3).
│   ├── limits.py                 🟢  # Límits compartits per a l'edició del tempo i el compàs.
│   ├── main.py                   🟢  # finestra principal, menús, barres, flux d'usuari i projectes
│   ├── mapa_tempo.py             🟢  # Model unificat del mapa de tempo/compàs (`mapa_tempo.csv`).
│   ├── marcadors.py              🟢  # Marcadors humans de la cançó (inici de compàs, en viu).
│   ├── marcadors_ui.py           🟢  # Marcadors en viu de la finestra (F3).
│   ├── menus.py                  🟢  # Menús, dreceres i ajuda de la finestra (F3).
│   ├── metronom.py               🟢  # metronom.py — generador de clics de metrònom (numpy pur, sense Qt).
│   ├── opcions.py                🟢  # Opcions persistents i valors per defecte dels diàlegs.
│   ├── panell_xifrat.py          🟢  # Panell «Tipus d'acord» — construeix un xifrat clicant (dock de l'esquerra).
│   ├── partitura.py              🟢  # Exportació de partitura (xifrat) des dels resultats d'Auto Chords.
│   ├── pipeline.py               🟢  # façana del backend (re-exporta els símbols públics)
│   ├── pipeline_derivats.py      🟢  # Derivats de guia i exportació (F1): segments, locators i guia HTML.
│   ├── pipeline_edicio.py        🟢  # Operacions d'edició i validació del model de clips (F1).
│   ├── pipeline_estructura.py    🟢  # Estructura ABC i WAVs de seccions (F1).
│   ├── pipeline_export.py        🟢  # Exportació de WAVs silenciosos i paquet complet (F1).
│   ├── pipeline_io.py            🟢  # Fitxers, noms segurs i escriptura atòmica d'AUTO CHORDS (F1).
│   ├── pipeline_mapa.py          🟢  # Mapa de tempo i marcadors del projecte (F1).
│   ├── pipeline_model.py         🟢  # Model pur de clips d'AUTO CHORDS (refactor F1 de `pipeline.py`).
│   ├── pipeline_vamp.py          🟢  # Motor Vamp d'AUTO CHORDS (F1): host, subprocess i detectors.
│   ├── plataforma.py             🟢  # Abstracció de plataforma: tot el que canvia entre Linux, Windows i macOS.
│   ├── postproc.py               🟢  # Post-processat de les deteccions (opcions del diàleg d'autodetecció).
│   ├── projecte.py               🟢  # Projectes d'AUTO CHORDS — carpeta **autocontinguda**, com un DAW.
│   ├── projecte_ui.py            🟢  # Gestió de projectes de la finestra (F3).
│   ├── tap_ui.py                 🟢  # Tap tempo de la finestra (F3).
│   ├── tempo.py                  🟢  # tempo.py — detecció de BPM i mapa de tempo (numpy pur, sense Qt).
│   ├── tempo_ajust.py            🟢  # Ajust d'un sol BPM a partir de marcadors de compàs (Fase 5).
│   ├── tempo_map.py              🟢  # Mapa de TEMPO i COMPÀS variables — el «motor» (stdlib pur).
│   ├── tempo_recalc.py           🟢  # Motor pur de recalcul del mapa de temps (F0).
│   ├── temps_ui.py               🟢  # UI de temps de la finestra (F3): BPM, compàs i offset.
│   ├── theme.py                  🟢  # tema centralitzat (colors i estils Qt)
│   ├── timeline.py               🟢  # timeline.py — Editor visual de la pista tipus DAW (QGraphicsView).
│   ├── timeline_base.py          🟢  # timeline_base.py — Base compartida de l'editor de timeline (DAW).
│   ├── timeline_geometry.py      🟢  # Geometria pura del timeline (F2).
│   ├── timeline_items.py         🟢  # timeline_items.py — Elements editables de l'editor de timeline (DAW).
│   ├── timeline_layers.py        🟢  # timeline_layers.py — Capes de fons de l'editor de timeline (DAW).
│   ├── vamp_params.py            🟢  # Llegeix els paràmetres ajustables dels plugins Vamp (descriptors .n3).
│   ├── visor.py                  🟢  # visor DAW: ona, llistes, edició, reproducció i loop
│   ├── visor_editor.py           🟢  # Franja Editor del visor (F4).
│   ├── visor_io.py               🟢  # Lectura de WAV i CSV del visor (F4).
│   ├── visor_llistes.py          🟢  # Poblament i handlers de les llistes del visor (F4).
│   ├── visor_marcadors.py        🟢  # Marcadors humans del visor (F4).
│   ├── visor_tempo.py            🟢  # Tempo i rubato del visor (F4).
│   ├── visor_transport.py        🟢  # Transport, loop, zoom, velocitat i metrònom del visor (F4).
│   ├── visor_ui.py               🟢  # Càrrega del visor i estat d'exportació (F3).
│   └── xifrat.py                 🟢  # Notació del xifrat d'acords — font ÚNICA (parseig + forma canònica).
├── codi_font_chordino/            🟢  # Codi font del plugin Chordino (NNLS-Chroma) (40 fitxers)
│   ├── .hgignore                     🟢
│   ├── .hgtags                       🟢
│   ├── .travis.yml                   🟢
│   ├── chord.dictold                 🟢
│   ├── chordextract.cpp              🟢
│   ├── Chordino.cpp                  🟢
│   ├── Chordino.h                    🟢
│   ├── chordino.png                  🟢
│   ├── chromamethods.cpp             🟢
│   ├── chromamethods.h               🟢
│   ├── CITATION                      🟢
│   ├── COPYING                       🟢
│   ├── Makefile.inc                  🟢
│   ├── Makefile.linux                🟢
│   ├── Makefile.mingw                🟢
│   ├── Makefile.osx                  🟢
│   ├── nnls-chroma.cat               🟢
│   ├── nnls-chroma.n3                🟢
│   ├── nnls.c                        🟢
│   ├── nnls.f                        🟢
│   ├── nnls.h                        🟢
│   ├── NNLSBase.cpp                  🟢
│   ├── NNLSBase.h                    🟢
│   ├── NNLSChroma.cpp                🟢
│   ├── NNLSChroma.h                  🟢
│   ├── plugins.cpp                   🟢
│   ├── README                        🟢
│   ├── releasenotes-0.2.1.txt        🟢
│   ├── releasenotes-0.2.txt          🟢
│   ├── releasenotes-0.3.txt          🟢
│   ├── sv-screenshot-nnls-chroma.png 🟢
│   ├── Tuning.cpp                    🟢
│   ├── Tuning.h                      🟢
│   ├── vamp-plugin.list              🟢
│   ├── vamp-plugin.map               🟢
│   ├── viterbi.cpp                   🟢
│   ├── viterbi.h                     🟢
│   └── regression/                   🟢  # Tests de regressió del plugin
│       ├── expected-v0.2.1.csv 🟢
│       ├── expected.csv        🟢
│       └── regression.sh       🟢
├── CORPUS/                        🟡  # Corpus local d'avaluació (no versionat) (819 fitxers)
│   ├── ANALISI_CORPUS.md                  🟡
│   ├── Alabama Shakes - Gimme All Your Love/ 🟡  # (78 fitxers)
│   ├── click contrafase/                  🟡  # (38 fitxers)
│   ├── Commodores - Easy/                 🟡  # (78 fitxers)
│   ├── Daft Punk, Pharrell Williams, & Nile Rodgers - Get Lucky (Radio Edit - feat. Pharrell Williams and Nile Rodgers)/ 🟡  # (1 fitxer)
│   ├── David Bowie - Space Oddity/        🟡  # (1 fitxer)
│   ├── De res - cop de sort_55bpm_C12_8/  🟡  # (134 fitxers)
│   ├── Foo Fighters - Times Like These/   🟡  # (78 fitxers)
│   ├── GMD_LOOPS/                         🟡  # (134 fitxers)
│   ├── Jamiroquai - Dynamite/             🟡  # (1 fitxer)
│   ├── Jamiroquai - Feels Just Like It Should/ 🟡  # (1 fitxer)
│   ├── MIREX06_BEAT/                      🟡  # (87 fitxers)
│   ├── Radiohead - High and Dry/          🟡  # (67 fitxers)
│   ├── Sitting On The Dock Of The Bay - Otis Redding -/ 🟡  # (42 fitxers)
│   └── The Chemical Brothers - All Rights Reversed (feat. The Klaxons)/ 🟡  # (78 fitxers)
├── docs/                          🟢  # Contracte i documentació viva (14 fitxers)
│   ├── COMPONENTS_I_VERSIONS.md       🟢  # Inventari generat (`eines/genera_inventari.py`)
│   ├── EDICIO_OPERACIONS.md           🟢  # Taula única d'operacions d'edició
│   ├── ESQUEMA_UI.html                🟢  # Generat des del `.md` (no editar)
│   ├── ESQUEMA_UI.md                  🟢  # Font de l'esquema visual de la UI
│   ├── ESQUEMA_UI.svg                 🟢  # Generat des del `.md` (no editar)
│   ├── FUNCIONALITATS_AUTO_CHORDS.ods 🟢  # Mapa complet de funcionalitats (generat; ODF)
│   ├── README.md                      🟢  # Índex de la documentació
│   ├── REGLES_DE_LA_APP.md            🟢  # Regles d'or (1–12) i §13 (temps, compàs i graella)
│   ├── TIPUS_XIFRAT_ACORDS.md         🟢  # Catàleg de tipus, graus i `<kind>` MusicXML
│   └── recerca/                       🟢  # Documents de recerca (no descriuen l'estat viu)
│       ├── AUTODETECCIO_OPCIONS.md            🟢
│       ├── GRAELLA_PPQ_TEMPS.md               🟢
│       ├── guia_tecnica_downbeat_onsets_beats.md 🟢
│       ├── NOTACIO_XIFRAT.md                  🟢
│       └── PLA_MAPA_TEMPS.md                  🟢
├── eines/                         🟢  # Build, empaquetat i cadena de subministrament (30 fitxers)
│   ├── AutoChords-win.spec       🟢  # PyInstaller (Windows)
│   ├── avalua_tempo.py           🟢  # Avaluador sintètic del mapa de tempo
│   ├── baixa_icones.sh           🟢  # Baixa les icones de Lucide
│   ├── baixa_verificat.py        🟢  # Baixades verificades per SHA256 (caché `.baixades/`)
│   ├── compila_vamp_host.sh      🟢  # Compila `vamp_host_local`
│   ├── compila_vamp_plugins.sh   🟢  # Compila els plugins QM (sense AVX)
│   ├── crea_appimage.sh          🟢  # Construeix l'AppImage
│   ├── crea_icona.py             🟢  # Genera `.ico`/`.icns`
│   ├── crea_portable.sh          🟢  # Crea l'entorn portable
│   ├── deps_fixades.env          🟢  # Pins de la cadena de subministrament
│   ├── empaqueta_portable.sh     🟢  # Empaqueta el portable
│   ├── explica_bpm.py            🟢
│   ├── exporta_partitura.py      🟢
│   ├── funcionalitats_dades.json 🟢  # Font de dades del mapa de funcionalitats
│   ├── genera_arbre.py           🟢  # Genera l'arbre d'aquest fitxer
│   ├── genera_comandes.py        🟢
│   ├── genera_esquema_ui.py      🟢  # Genera `docs/ESQUEMA_UI.html` i `.svg`
│   ├── genera_formats.py         🟢
│   ├── genera_funcionalitats.py  🟢  # Genera `docs/FUNCIONALITATS_AUTO_CHORDS.ods`
│   ├── genera_index_docs.py      🟢
│   ├── genera_inventari.py       🟢  # Genera `docs/COMPONENTS_I_VERSIONS.md`
│   ├── genera_moduls.py          🟢  # Genera la taula de mòduls de `DEVELOPING.md`
│   ├── launcher_pyinstaller.py   🟢  # Punt d'entrada del paquet congelat
│   ├── libreries_natives.sh      🟢  # Copia biblioteques natives
│   ├── notes_release.py          🟢  # Notes de release des del CHANGELOG
│   ├── ordre_aleatori.py         🟢  # Suite en ordre aleatori
│   ├── prova_windows.py          🟢
│   ├── smoke_macos.sh            🟢
│   ├── vamp_host.cpp             🟢  # Host Vamp propi (C++)
│   └── verifica_minos_macos.py   🟢
├── icona/                         🟢  # Icones de l'aplicació (12 fitxers)
│   ├── auto-chords-1024.png 🟢
│   ├── auto-chords-128.png  🟢
│   ├── auto-chords-256.png  🟢
│   ├── auto-chords-32.png   🟢
│   ├── auto-chords-48.png   🟢
│   ├── auto-chords-512.png  🟢
│   ├── auto-chords-64.png   🟢
│   ├── auto-chords-logo.svg 🟢
│   ├── auto-chords.icns     🟢
│   ├── auto-chords.ico      🟢
│   ├── auto-chords.png      🟢
│   └── captura.png          🟢
├── icones/                        🟢  # Icones SVG de la UI (Lucide, ISC) (21 fitxers)
│   ├── arrow-left-to-line.svg  🟢
│   ├── arrow-right-to-line.svg 🟢
│   ├── compass.svg             🟢
│   ├── fast-forward.svg        🟢
│   ├── focus.svg               🟢
│   ├── LICENSE                 🟢  # Llicència ISC de Lucide
│   ├── map-pin.svg             🟢
│   ├── maximize.svg            🟢
│   ├── metronome.svg           🟢
│   ├── pause.svg               🟢
│   ├── play.svg                🟢
│   ├── redo-2.svg              🟢
│   ├── repeat-2.svg            🟢
│   ├── rewind.svg              🟢
│   ├── square.svg              🟢
│   ├── target.svg              🟢
│   ├── undo-2.svg              🟢
│   ├── volume-x.svg            🟢
│   ├── x.svg                   🟢
│   ├── zoom-in.svg             🟢
│   └── zoom-out.svg            🟢
├── nnls-chroma-linux64-local/     🟢  # Plugin Chordino compilat (local) (4 fitxers)
│   ├── chord.dict      🟢
│   ├── nnls-chroma.cat 🟢
│   ├── nnls-chroma.n3  🟢
│   └── nnls-chroma.so  🟢
├── portable/                      🟡  # Entorn portable local (regenerable) (5.951 fitxers)
│   ├── bin/    🟡  # (2 fitxers)
│   ├── lib/    🟡  # (9 fitxers)
│   └── python/ 🟡  # (5.940 fitxers)
├── qm-vamp-plugins-linux64-local/ 🟢  # Plugins Queen Mary compilats (local) (3 fitxers)
│   ├── qm-vamp-plugins.cat 🟢
│   ├── qm-vamp-plugins.n3  🟢
│   └── qm-vamp-plugins.so  🟢
├── temp/                          🟡  # Temporals de l'app (no versionat) (1 fitxer)
│   └── visor_player.log 🟡  # Log del reproductor
├── tests/                         🟢  # Suite unittest offscreen (23 fitxers)
│   ├── _qt_neteja.py              🟢  # Neteja ORDENADA dels objectes Qt entre tests.
│   ├── _temporals.py              🟢  # Higiene dels tests: cap temporal no s'ha de quedar pel disc.
│   ├── test_ancoratges.py         🟢  # Suite de test — Marcadors humans i velocitat de reproducció.
│   ├── test_arbre_al_dia.py       🟢  # Test: l'arbre de `ARBRE_DIRECTORIS.md` ha d'estar al dia.
│   ├── test_audio_edit.py         🟢  # Regressions de les edicions bàsiques d'àudio.
│   ├── test_avalua_tempo.py       🟢  # Proves sintètiques per a l'avaluador de tempo.
│   ├── test_beats.py              🟢  # Tests del motor de beats i de la sensibilitat.
│   ├── test_camp_text.py          🟢  # Tests — Camps de text que mostren l'inici del contingut.
│   ├── test_despatx_edicio.py     🟢  # Despatx ÚNIC d'edició (regla d'or #11) — contracte de superfícies.
│   ├── test_docs_al_dia.py        🟢  # Test: la documentació generada ha d'estar al dia.
│   ├── test_drag_drop.py          🟢  # Drag & drop d'àudio des del gestor de fitxers (Linux, Windows i macOS).
│   ├── test_edicio.py             🟢  # Suite de test — Edicio
│   ├── test_exporta_audio.py      🟢  # Tests de l'exportació de la còpia de treball (Fase 6).
│   ├── test_gui.py                🟢  # Suite de test — Gui
│   ├── test_mapa_tempo.py         🟢  # Tests de la capa de dades `mapa_tempo.csv` (subplà de rubato, fase 2).
│   ├── test_moduls_al_dia.py      🟢  # Test: la taula de mòduls de `DEVELOPING.md` ha d'estar al dia.
│   ├── test_pipeline.py           🟢  # Suite de test — Pipeline
│   ├── test_pipeline_contracte.py 🟢  # Contracte de superfície de `app.pipeline` (refactor F0).
│   ├── test_tempo_ajust.py        🟢  # —
│   ├── test_tempo_map.py          🟢  # Suite de test — Tempo Map
│   ├── test_tempo_recalc.py       🟢  # Tests del motor pur de recalcul del mapa de temps (F0).
│   ├── test_tempo_trams.py        🟢  # Motor de tempo per trams (app/tempo.py): candidats, beats i mapa.
│   └── test_timeline_contracte.py 🟢  # Contracte de superfície de `app.timeline` (refactor F0).
├── .gitignore                     🟢  # Què no es versiona
├── AGENTS.md                      🟢  # Guia del projecte i contracte d'abast
├── ARBRE_DIRECTORIS.md            🟢  # Mapa de carpetes i fitxers (generat, no editar a mà)
├── AUTO_CHORDS.sh                 🟢  # Llançador principal
├── AUTO_CHORDS_dev.sh             🟢  # Llançador de desenvolupament
├── CHANGELOG.md                   🟢  # Historial de canvis
├── concatena.py                   🟢  # Genera un sol fitxer amb el codi indispensable
├── dev_reload.py                  🟢  # Recàrrega automàtica en dev
├── DEVELOPING.md                  🟢  # Entorn, mapa del codi, build i CI
├── instal·la_local.sh             🟢  # Instal·lació local sense sudo
├── LICENSE                        🟢  # GPL-3.0-or-later
├── LLICENCIES_TERCERS.md          🟢  # Llicències de tercers
├── Makefile                       🟢  # Comandes del projecte (test, lint, docs…)
├── pyproject.toml                 🟢  # Metadades i pins del paquet
├── README.md                      🟢  # Producte: visió, instal·lació i flux
├── requirements-build.txt         🟢  # Pins addicionals del build
├── requirements-dev.txt           🟢  # Eines de qualitat: pyflakes i coverage
├── requirements.txt               🟢  # Dependències de Python (pins)
├── ROADMAP.md                     🟢  # Full de ruta i estat actual (§2)
├── ROADMAP_HISTORIA.md            🟢  # Historial del full de ruta (fases A–E i notes)
├── SECURITY.md                    🟢  # Canal de report de vulnerabilitats
├── vamp_host_local                🟢  # Host Vamp compilat (binari)
└── wav_a_wavs.py                  🟢  # CLI: WAV → WAVs d'acord/secció
```
<!-- /GENERAT: arbre -->

### Què és generat i què no s'ha de tocar

| Ruta | Origen | Acció |
|---|---|---|
| L'arbre d'aquest document | `eines/genera_arbre.py` | Regenerar si canvia el contingut (`make docs`) |
| `docs/ESQUEMA_UI.html` · `.svg` | `eines/genera_esquema_ui.py` des de `ESQUEMA_UI.md` | Regenerar, no editar a mà |
| `docs/COMPONENTS_I_VERSIONS.md` | `eines/genera_inventari.py` | Regenerar si canvien pins |
| `DEVELOPING.md` (taula de mòduls) | `eines/genera_moduls.py` des de `app/*.py` | Regenerar si canvia `app/` |
| `app/__pycache__/` · `tests/__pycache__/` | Python | Ignorar |
| `portable/` · `.venv/` · `.deps/` | Entorn local | No versionar ni incloure al codi |
| `CORPUS/` | Corpus local d'avaluació | No versionar |
| `.opencode/` · `opencode.json` | Config local d'agents | No versionar |
| `*.log` · `recents.json` · `opcions_detecta.json` · `crash_nadiu.log` | Estat local | No versionar |

</details>
