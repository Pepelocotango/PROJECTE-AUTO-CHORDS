# Desenvolupament — PROJECTE AUTO CHORDS

Tot en català. Llicència: GPLv3 (vegeu `LICENSE`).

## Requisits

- Python 3.8+ (stdlib; sense pip per al pipeline).
- Per a l'app: PyQt5 del sistema (`python3-pyqt5`, Qt5).
  ⚠️ Qt6 **no** corre en CPU sense SSE4.2 (com el Q9400): no s'hi pot
  usar PySide6/PyQt6.
- `sonic-annotator` + plugin Chordino (`nnls-chroma-linux64-local/`)
  per al pas `wav → csv`.

## Entorn aïllat (Ubuntu, sense sudo)

```bash
bash instal·la_local.sh   # crea .venv/ + pip PyQt5 + .deps/ (headers via apt download, sense instal·lar)
.venv/bin/python app/main.py
.venv/bin/python wav_a_wavs.py tema.wav 138 4 [offset]
```

* Python: stdlib + PyQt5 en `.venv/` (rodes, sense apt).
* C++ (`chordextract`): headers a `.deps/usr/include` (descarregats, no instal·lats); binari de prova a `/tmp/opencode/chordextract`, sense substituir l'annotator.
* `.deps/` i `.venv/` no es commitegen.

## Matriu ferro → eina (Q9400 + Ubuntu 24, verificada 01-10-2026)

Ferro: Q9400 **sense AVX** (`grep avx` buit), SSE4.1. So del sistema:
**PipeWire 1.0.5 + pipewire-pulse**. Qualsevol canvi d'eina ha de passar
aquest filtre o mor al SIGILL / violació de segment.

| Eina | Veredicte | Motiu (verificat) |
|---|---|---|
| `wave` stdlib | ✅ fem servir | Zero dependències; millor que `soundfile` |
| `numpy` 1.26 (`numpy<2`) | ✅ fixat | El 2.x demana x86_64-v2 (SSE4.2) → `RuntimeError` al Q9400 |
| PyQt5 + pyqtgraph | ✅ fem servir | Rodes amb Qt5; Qt6-GUI/PySide6 demana SSE4.2 |
| `paplay --raw` (libpulse → PipeWire) | ✅ fem servir | Camí natiu Ubuntu 24 amb mescla; `aplay` (ALSA directe) només de reserva, `ffplay` últim recurs |
| `QAudioOutput` QtMultimedia | ❌ aparcat | Les rodes SÍ porten plugins (`libqtaudio_alsa.so`); el segfault era format/QBuffer, però `paplay` té stderr visible i zero acoblament Qt — no es reobre sense motiu |
| `sounddevice` (PortAudio) | ❌ innecessari | `libportaudio.so.2` hi és, però afegiria dependència pip+sistema sense guanyar res |
| Chordino/Segmentino + `sonic-annotator` (compilats aquí) | ✅ fem servir | L'únic anàlisi Vamp que corre; `chordextract` compila a `.deps/` sense sudo |
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
7. `Finalitza i publica` genera el paquet final per a DAW

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

## Convencions

- Comentaris i docs en català.
- Sense secrets ni credencials al repo (ni claus API ni tokens).
- Els binaris compilats aquí (`sonic-annotator`, `.so`) SÍ es commitegen
  (són l'eina); les sortides (`*_obsolets/`, `midis_acords/`) no.
