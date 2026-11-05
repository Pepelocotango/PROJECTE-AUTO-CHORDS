# Desenvolupament — PROJECTE AUTO CHORDS

Tot en català. Llicència: GPL-3.0-or-later (vegeu `LICENSE`).

> 🔴 **ABANS DE TOCAR CODI**: les **regles d'or (invariants)** de l'app són totes
> a **`docs/REGLES_DE_LA_APP.md`**. Cap canvi no les pot trencar.

## Requisits

- Python 3.10+ (stdlib; sense pip per al pipeline). Coincideix amb `requires-python` del `pyproject.toml`.
- Per a l'app: PyQt5 del sistema (`python3-pyqt5`, Qt5) o entorn virtual `.venv/`.
  ⚠️ Qt6 **no** corre en CPU sense SSE4.2 (com el Q9400): no s'hi pot
  usar PySide6/PyQt6.
- **plugins Vamp** a les carpetes `*-local/`: **`nnls-chroma`** (Chordino,
  acords) i **`qm-vamp-plugins`** (Queen Mary: tempo/beats/bars/segmenter/key
  — `docs/QM_VAMP.md`). El **Segmentino** i l'**aubio** s'han retirat
  (v0.5): l'estructura la fa el `qm-segmenter` i el BPM el `tempo.py`/`qm`.
- **`ffmpeg`** — opcional, només per importar formats que no siguin WAV
  (`app/ffmpeg.py`); s'embega a `portable/bin/ffmpeg` (fase 3).
- **Àudio**: a Linux cal **PipeWire** o **PulseAudio** per ESCOLTAR (reproductor
  `paplay`, o `aplay` d'ALSA de reserva). A macOS i Windows l'app reprodueix
  directament dins el procés mitjançant el motor natiu d'àudio (`app/audio_out.py`
  sobre PortAudio / `sounddevice` — CoreAudio a macOS i WASAPI a Windows).

## Entorn aïllat (Ubuntu, sense sudo)

```bash
bash instal·la_local.sh   # crea .venv/ + pip PyQt5 + numpy<2 + sounddevice
.venv/bin/python app/main.py
.venv/bin/python wav_a_wavs.py tema.wav 138 4 [offset]
```

* Python: stdlib + PyQt5 en `.venv/` (rodes, sense apt).
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
| Chordino + QM (`qm-segmenter`…) via **host propi** | ✅ fem servir | Únic motor: `vamp_host_local` (`docs/QM_VAMP.md`) |
| **`qm-vamp-plugins`** (Queen Mary) | ✅ fem servir | Compilats del codi font amb `-msse -msse2` (**sense AVX**); `docs/QM_VAMP.md` |
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

## Verificar canvis

```bash
# compilació ràpida (no arrenca l'app)
.venv/bin/python -m py_compile wav_a_wavs.py app/main.py app/pipeline.py app/visor.py

# la suite sencera (ha d'estar sempre verda; offscreen = cap diàleg)
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests

# estil
.venv/bin/python -m pyflakes app/*.py tests/*.py
```

**Higiene dels temporals**: la suite **no ha de deixar res** al disc. Tots els
fitxers de test importen **`tests/_temporals.py`**, que intercepta
`tempfile.mkdtemp` / `mkstemp` / `NamedTemporaryFile`, anota el que es crea i ho
esborra en plegar el procés (`atexit`). Abans una tongada deixava ~1.000 carpetes
i ~1,3 GB, i se n'hi van acumular **57 GB** (disc al 97%). **Si afegeixes un test
nou, importa'l també** (dues línies al costat del `sys.path.insert`).

## Trampes conegudes (provar canvis)

- **Si hi ha una app viva, porta el codi vell en memòria**: cal **reiniciar-la**
  perquè els canvis del disc hi entren.
- **Missatges en català dins comandes `bash`** amb accents o *backticks*: fes
  servir **heredocs** (`python3 - <<'PY' … PY`), no `-c "..."` (els *backticks*
  es substitueixen i mutilen el text).

## Retrocompatibilitat — no és prioritat (2026-11-02)

- **Cap canvi de codi no ha de mantindre** formats, fitxers, camps o
  comportaments antics si això complica el model o alenteix una millora.
- Els canvis de format poden **rebutjar** projectes vells amb un **error clar**;
  no es fan migracions, lectors tolerants ni carpetes de compatibilitat.
- **No es mantenen dos formats en paral·lel.** Si un canvi necessita un format
  nou, el vell deixa d'existir.
- **No es pregunta per retrocompatibilitat** en una modificació de codi: la
  resposta per defecte és **no** i el canvi es documenta al `CHANGELOG.md`.
- **Excepció de seguretat**: no es destrueix mai un fitxer de l'usuari. Un
  projecte no suportat es rebutja **sense tocar-lo** i s'explica el motiu.

## VM Debian (fora d'abast)

La VM Debian **ja no es fa servir per a l'app** (era massa limitada): l'antic
`instal·la_vm_debian.sh` **s'ha retirat**. Aquest repo viu al `/home` de l'host;
per usar-lo en un altre sistema, fes servir els **paquets del CI**
(AppImage de Linux o ZIP de Windows/macOS) o copia la carpeta / deixa-la a l'exFAT.

## Lògica de producte i flux de treball

La base del projecte és senzilla i molt important: un sol flux de treball
coherent on analitzador, editor i exportador comparteixen exactament el mateix model.

### Model de dades

- **Font de veritat**: el model viu en memòria i els **4 fitxers CSV** del projecte (`acords.csv`, `estructura_ABC.csv`, `mapa_tempo.csv` i `marcadors.csv`).
- Cada registre d'acords i estructura és un interval temporal contigu en segons `[ini, fi)`.
- El mapa de tempo (`mapa_tempo.csv`) és model persistent i exportable (regla #12): desa els trams amb `bpm`, metre `num/den` i tipus (`normal` o `rubato`), amb inici i fi contigus.
- El temps en segons és la referència física de l'àudio, mentre que la posició mètrica (`compàs.temps.subdivisió`) i la graella deriven del mapa de tempo (`app/tempo_map.py`).
- Els acords, les seccions i els trams de tempo sempre s'ordenen cronològicament abans de ser persistits de manera atòmica (`pipeline.escriu_atomic`).

### Flux implementat

1. La WAV o fitxer d'àudio s'obre a l'app principal (`Obre àudio`) i es crea el projecte autocontingut (`.acproj`).
2. L'anàlisi és opcional: `Analitza` (F5) extreu acords (Chordino) i estructura (QM); `Analitza BPM` (F7) detecta beats o tempo.
3. El visor carrega l'ona, els 3 carrils (acords, estructura, tempo/compàs) i els marcadors.
4. L'usuari pot editar manualment qualsevol dels 3 carrils amb les mateixes eines (paritat, regla #11), afegir marcadors en viu (`+`) i ajustar el mapa de tempo.
5. Cada canvi es valida: no solapaments, contigüitat estricta, cobertura total de la WAV (`[0, durada]`) i beats sencers.
6. `Exporta WAV's` (Ctrl+E) i `Exporta partitura` generen el paquet final per a DAW (clips silenciosos, CSVs, guia HTML i MusicXML/PDF).

### Regles de consistència

- La continuïtat és estricta: `prev.fi == curr.ini` en els tres carrils.
- Els extrems cobreixen exactament `[0, durada]` de la WAV de treball.
- El fi del segment es deriva del següent inici, perquè és la forma més robusta de representar intervals continus.
- Els valors no coneguts no són dades corruptes: `N` és un acord canònic vàlid per al silenci o harmonia indefinida.

## Mòduls de l'app (`app/`)

| Mòdul | Responsabilitat |
|-------|-----------------|
| `main.py` | Finestra principal, menús, barres, orquestració de flux i projectes (`Finestra`) |
| `visor.py` | Visor integrat (timeline + llistes + Editor + transport + undo/redo), `Visor` |
| `timeline.py` | Orquestrador del timeline i re-exportacions públiques |
| `timeline_base.py` | Vista base i escena de QGraphicsView (`TimelineView`, `TimelineScene`, constants de carril) |
| `timeline_items.py` | Clips gràfics d'acords i seccions (`ChordItem`, `SectionItem`) |
| `timeline_layers.py` | Capes visuals del regle, graella, ona i pista de tempo (`RulerLayer`, `GridLayer`, `WaveformLayer`, `TempoLayer`) |
| `pipeline.py` | Backend d'anàlisi Vamp, model, normalització, exportació de CSVs, WAVs silenciosos i HTML |
| `tempo_map.py` | Motor matemàtic del mapa de tempo (trams contigus, conversió temps↔musical, beats, subdivisió) |
| `mapa_tempo.py` | Serialització i persistència del mapa de tempo (`mapa_tempo.csv`, format 3) |
| `rubato.py` | Motor de derivació de trams rubato (`tipus=rubato`, aproximació mètrica) |
| `marcadors.py` | Lògica dels marcadors en viu (`+`), normalització i correspondència amb fronteres |
| `beats.py` | Orquestració dels motors de detecció de beats (nostre / Queen Mary) |
| `tempo.py` | Detecció de BPM per DSP (autocorrelació d'onsets + filtres comb en numpy, sense AVX) |
| `tempo_ajust.py` | Ajust de mapa de BPM per mínims quadrats i partició recursiva |
| `bpm_unit.py` | Conversió i visualització d'unitats de BPM (negra, negra amb punt, corxera, blanca) |
| `limits.py` | Constants compartides de límits (BPM 30–350, numeradors 1–12, denominadors 2, 4, 8) |
| `projecte.py` | Gestió de projectes autocontinguts (`.acproj`, carpeta `audio/`, còpies de seguretat) |
| `audio_edit.py` | Motor d'edició d'àudio dels extrems (retall i afegit de silenci atòmic amb el model) |
| `exporta_audio.py` | Exportació d'àudio multiformat (WAV/MP3/FLAC/AAC/OGG/Opus) via FFmpeg |
| `audio_out.py` | Motor d'àudio natiu de reproducció (`paplay`/`aplay` a Linux, `sounddevice` a Windows/macOS) |
| `metronom.py` | Clic del metrònom mesclat en temps real al buffer d'àudio (patrons i accents) |
| `graella.py` | Matemàtica de graella i regularització de temps |
| `postproc.py` | Neteja i postprocessament de l'anàlisi crua (baix, simplificació, durada mínima) |
| `xifrat.py` | Notació canònica de xifrats d'acord, parseig d'arrel i baix |
| `partitura.py` | Exportació de partitura en MusicXML (i PDF/MSCZ si MuseScore està instal·lat) |
| `panell_xifrat.py` | Panell gràfic dockable de selecció de 62 tipus d'acord i audició (`PanellXifrat`) |
| `acord_audio.py` | Síntesi d'àudio per a l'audició prèvia d'acords (timbres de piano/òrgan/guitarra) |
| `dialegs.py` | Diàlegs d'anàlisi, cerca i reemplaçament, quantització i ajust de trams |
| `dialeg_bpm_marcadors.py` | Diàleg per analitzar i aplicar BPM a partir de marcadors |
| `dialeg_guia_rapida.py` | Guia informativa de 5 pantalles sobre el flux DAW i els marcadors (`DialegGuiaRapida`) |
| `vamp_params.py` | Lectura i resolució dinàmica de descriptors `.n3` de plugins Vamp |
| `ffmpeg.py` | Importació de 19 formats d'àudio i canvi de velocitat amb to mantingut |
| `plataforma.py` | Abstracció del sistema operatiu (Linux, Windows, macOS), rutes i binaris |
| `config.py` | Configuració centralitzada i directori d'estat escriptible |
| `theme.py` | Tema gràfic centralitzat (colors, estils DAW i QSS) |
| `icones.py` | Gestió d'icones vectorials Lucide recolorides |

Docs de detall a `docs/`: `ESQUEMA_UI.md` (GUI), `AUTODETECCIO_OPCIONS.md`
(motors i opcions), `QM_VAMP.md` (Queen Mary), `AUDIO.md` (reproducció),
`PARTITURA_EXPORT.md` (partitura/MuseScore), `archive/AUBIO_TEMPO.md` (històric),
`SEGURETAT.md` (**què s'ha endurit i com es manté**).

## Convencions

- Comentaris i docs en català.
- Sense secrets ni credencials al repo (ni claus API ni tokens).
- Els binaris natius de Linux (`*-local/*.so`, `vamp_host_local`) SÍ es
  commitegen (són l'eina); les sortides (`*_obsolets/`, `midis_acords/`) no.
- **`OLD/`** (gitignorat) és l'**arxiu local** del que no és necessari però es
  vol conservar (p. ex. versions retirades). **No es puja al repo.**

## Paquet portable (autocontingut)

```bash
eines/empaqueta_portable.sh      # -> ../AUTO_CHORDS_PORTABLE/
cd ../AUTO_CHORDS_PORTABLE && ./AUTO_CHORDS.sh
```
El paquet **no s'edita mai** (és un artefacte de build): el codi viu al repo i es regenera. Detall: `docs/ESTAT_MULTI_SO.md` (i `docs/archive/PORTABILITAT.md`).

## AppImage

L'AppImage es construeix al CI (`.github/workflows/build-appimage.yml`) o amb:

```bash
eines/crea_appimage.sh
```
