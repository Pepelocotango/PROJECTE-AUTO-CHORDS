# Desenvolupament — PROJECTE AUTO CHORDS

Tot en català. Llicència: GPLv3 (vegeu `LICENSE`).

## Requisits

- Python 3.10+ (stdlib; sense pip per al pipeline). Coincideix amb `requires-python` del `pyproject.toml`.
- Per a l'app: PyQt5 del sistema (`python3-pyqt5`, Qt5).
  ⚠️ Qt6 **no** corre en CPU sense SSE4.2 (com el Q9400): no s'hi pot
  usar PySide6/PyQt6.
- **plugins Vamp** a les carpetes `*-local/`: **`nnls-chroma`** (Chordino,
  acords) i **`qm-vamp-plugins`** (Queen Mary: tempo/beats/bars/segmenter/key
  — `docs/QM_VAMP.md`). El **Segmentino** i l'**aubio** s'han retirat
  (v0.5): l'estructura la fa el `qm-segmenter` i el BPM el `tempo.py`/`qm`.
- **`ffmpeg`** — opcional, només per importar formats que no siguin WAV
  (`app/ffmpeg.py`); s'embega a `portable/bin/ffmpeg` (fase 3).
- **Àudio**: cal **PipeWire** o **PulseAudio** per ESCOLTAR (reproductor
  `paplay`, o `aplay`/`ffplay` de reserva). Sense cap d'ells, l'app
  **funciona igual** (analitzar, editar, exportar); només avisa que no es pot
  escoltar (`Visor._tria_player`).

## Entorn aïllat (Ubuntu, sense sudo)

```bash
bash instal·la_local.sh   # crea .venv/ + pip PyQt5 + .deps/ (headers via apt download, sense instal·lar)
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
| `paplay --raw` (libpulse → PipeWire) | ✅ fem servir | Camí natiu Ubuntu 24 amb mescla; `aplay` (ALSA directe) només de reserva, `ffplay` últim recurs |
| `QAudioOutput` QtMultimedia | ❌ aparcat | Les rodes SÍ porten plugins (`libqtaudio_alsa.so`); el segfault era format/QBuffer, però `paplay` té stderr visible i zero acoblament Qt — no es reobre sense motiu |
| `sounddevice` (PortAudio) | ❌ innecessari | `libportaudio.so.2` hi és, però afegiria dependència pip+sistema sense guanyar res |
| Chordino + QM (`qm-segmenter`…) via **host propi** | ✅ fem servir | Vegeu `docs/QM_VAMP.md`; el `sonic-annotator` queda com a reserva |
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
VAMP_PATH=nnls-chroma-linux64-local ./sonic-annotator \
  -d vamp:nnls-chroma:chordino:simplechord -w csv tema.wav
python3 acords_a_live.py acords.csv 138 4 [offset_segons]
```

## Verificar canvis

```bash
.venv/bin/python -m py_compile acords_a_live.py wav_a_wavs.py app/main.py app/pipeline.py app/visor.py
```

## VM Debian (execució, no compilació)

A la VM només calen llibreries d'execució:

```bash
bash instal·la_vm_debian.sh   # demana 1 pkexec, dins la VM
```

Nota: aquest repo viu al `/home` de l'host; la VM/Mac no hi accedeix
directament. Per usar-lo allà, copia la carpeta o deixa-la a l'exFAT.

## Lògica de producte i flux de treball

La base del projecte és senzilla i molt important: no hauríem de tenir un “analitzador” separat, un “editor” separat i un “exportador” separat que no comparteixen model.

### Model de dades

- els CSVs d’acords i estructura són la font de veritat
- cada registre és un interval temporal
- el temps es guarda en segons al backend
- el mode compàs/BPM és només una vista derivada, per a navegació humana i presentació del projecte
- els acords i les seccions sempre s’ordenen cronològicament abans de ser persistits

### Flux implementat

1. la WAV s’obre a l’app principal
2. `Processa` extreu acords i, si escau, estructura
3. el visor carrega la ona, els acords i les seccions generades
4. l’usuari pot corregir acords, afegir o esborrar seccions, i normalitzar l’ordre
5. cada canvi es valida: no solapaments, no ordre invers, no duplicats lògics
6. el visor regenerat els clips i les sortides associades
7. `Exporta` genera el paquet final per a DAW

### Regles de consistència

- no es barregen segons i BPM en la mateixa base de dades
- no es deixen intervals inconsistents en el CSV
- no es permeten edicions que comportin solapaments o anàlisis contradictòries
- el fi del segment es deriva del següent inici, perquè és la forma més robusta de representar intervals continus
- els valors no coneguts no se’ls tracta com a “males dades”; en aquest producte, `N` és un acord vàlid i ha de poder circular sense ser reinterpretat com a error

### Filosofia de disseny

L’arquitectura està pensada perquè el producte sigui un flux de treball coherent i no una col·lecció de scripts amb criteris diferents. Per això:

- una sola app front-end
- un únic model intern de temps
- un únic runtime de regeneració
- una única acció d’export final
- una validació d’edició que protegeix el dataset i evita “malformacions” que després trenquen la producció

El resultat és un sistema fàcil d’entendre, reproduïble i segur d’editar.

## Àrees de futur: investigar, valorar i prioritzar

Aquesta llista recull els temes que no són bloquejos del flux actual, però que tenen molt potencial i cal valorar amb criteri de producte i de manteniment.

### 1) Representació de compassos amb 3 xifres

- estudiar si el sistema ha de mostrar `1.1.3`, `1.1.50` o variants similars en la UI
- decidir si aquest format és només visual o si forma part del llegible de sortida i del CSV d’entrada
- definir un esquema de metadades per a compàs, beat i subdivisió sense confondre el model de temps intern
- protegir la compatibilitat amb el model actual en segons

### 2) Control avançat del processament automàtic

- investigar la configuració real de `Chordino` i els plugins QM
- valorar un panell d’algoritmes amb sensibilitat, llindars i paràmetres d’autogeneració
- discutir si el model ideal és “l’usuari no toca res” o “l’usuari expert ajusta llindars”
- definir un mode per defecte estable i un mode avançat opcional

### 3) Millora del tema visual i colors

- simplificar la paleta global i fer-la coherent a tots els components
- valorar una escala de grisos amb contrast millor i accents selectius
- decidir si el color s’usa exclusivament com a suport visual o si cada estat ha de tenir un significat semàntic clar

### 4) Gràfica amb línia temps segons/BPM

- afegir una línia de temps visual que mostri tant segons com compàs/BPM segons el mode actiu
- revisar si cal mostrar diferents escales o si una sola vista és suficient
- decidir si el cursor de temps s’ha de sincronitzar amb la posició de reproducció i amb la selecció de segments

### 5) Auditoria de seguretat

- revisar tots els punts d’entrada de fitxers i subprocessos
- validar que no hi hagi execucions no controlades ni paths vulnerables
- definir una política de logs i de gestió d’errors per a entorns reals
- verificar que els exportats no pateixen injecció de ruta, noms o contingut

### 6) Nomenclatura de fitxers i ordres d’export

- decidir una convenció semàntica que permeti ordenar de forma fàcil els clips finals
- procurar que el nom principal contengui la informació més important al principi
- revisar si els noms de acords i de seccions han d’indicar secció, ordre o temps inicial

### 7) Altres formats de partitura / sortida musical

- estudiar MusicXML, ABC, LilyPond o exportació de partitura en altres formats
- valorar si aquests formats són producte core o eines de postproducció
- decidir quins exportables tenen valor real per a usuaris de música i producció

### 8) Desplegament real de l’app

- definir un canal de distribució fiable per a usuaris finals
- preparar packaging, instal·ladors o bundles per a un sistema real
- pensar en versions, canvis, rollback i validació d’instal·lació

### 9) Desplegament a altres SO

- comprovar compatibilitats de Qt, Python i plugins en Linux, Windows i macOS
- separar la part “núcleo del producte” de la part “platform-specific glue”
- definir els punts de risc a cada OS: audio, subprocessos, paths, permisos, drivers, llicències

### 10) Criteri per prioritzar el futur

La regla sana és aquesta: no s’ha d’afegir complexitat fins que la base funcional no estigui molt estable. Per tant, el futur s’ha de prioritzar amb aquesta lògica:

- primer estabilitat i claredat del flux
- després UX i visualització
- després configuració avançada i automatització
- després exportacions més riques i desplegament generalitzat

Aquesta llista és una guia de futur, no una promesa de feina immediata.

## Agraïments i reconeixement a eines de tercers

Aquest projecte és un assemblatge de feina pròpia i de tecnologia de tercers. És important deixar-ho escrit explícitament:

- agraïments al projecte Python i a la seva comunitat
- agraïments a PyQt5, Qt5 i PyQtGraph per la base d’UI i gràfics
- agraïments a NumPy per la manipulació eficient de dades d’àudio i de temps
- agraïments a Chordino, Sonic Annotator i Vamp per la detecció automàtica d’acords
- agraïments als plugins Vamp de Queen Mary per la generació d’estructura
- agraïments a les llibreries i components del sistema operatiu que fan possible la reproducció i la conversió d’àudio
- agraïments a totes les persones i equips que han publicat biblioteques, plug-ins, tutorials i solucions que ens han ajudat a construir aquesta app

La nostra feina és construir i integrar, però no és “des de zero” en el sentit absolut: hi ha moltes bases creades per altres projectes i persones. Reconèixer-ho és una bona pràctica, un signe de respecte i un acte de transparència técnica.

## Mòduls de l'app (`app/`)

| Mòdul | Responsabilitat |
|-------|-----------------|
| `main.py` | finestra principal, menús, barres, diàleg de flux, `Finestra` |
| `visor.py` | visor (timeline + llistes + Editor + transport), `Visor` |
| `timeline.py` | regle, graella, carrils i clips (`QGraphicsView`) |
| `pipeline.py` | extracció (Chordino, QM), export, normalització, TTL |
| `tempo.py` | detecció de BPM (numpy pur, prior de plateau) — `docs/` |
| `vamp_params.py` | paràmetres dels plugins Vamp (descriptors `.n3`) |
| `dialegs.py` | diàleg d'opcions d'autodetecció |
| `postproc.py` | neteja posterior dels acords |
| `ffmpeg.py` | import d'altres formats (conversió a WAV) |
| `metronom.py` | clic del metrònom mesclat al buffer |
| `theme.py` | tema centralitzat (colors) |
| `icones.py` | icones SVG de **Lucide** (ISC) recolorejades (`icones/`, `eines/baixa_icones.sh`) |

Docs de detall a `docs/`: `ESQUEMA_UI.md` (GUI), `AUTODETECCIO_OPCIONS.md`
(motors i opcions), `QM_VAMP.md` (Queen Mary), `PLAY.md` (reproducció),
`AUBIO_TEMPO.md` (històric).

## Convencions

- Comentaris i docs en català.
- Sense secrets ni credencials al repo (ni claus API ni tokens).
- Els binaris compilats aquí (`sonic-annotator`, `.so`) SÍ es commitegen
  (són l'eina); les sortides (`*_obsolets/`, `midis_acords/`) no.
