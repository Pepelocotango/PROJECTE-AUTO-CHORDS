# Portabilitat: fer l'app autocontinguda

> **2026-10-07.** Anàlisi (no implementació) de què caldria perquè AUTO CHORDS
> sigui **autocontingut i portable** (copiar la carpeta i que funcioni, sense
> instal·lar res). Mides i `ldd` reals del projecte.
>
> ⚠️ Les seccions **1–5** són l'**anàlisi inicial** (històrica, es conserva per
> entendre el raonament). L'estat **actual** és la **secció 0**; el flux de
> treball és la **secció 6**.

---

## 0. Estat actual (2026-10-07 · v0.5.0): **AUTOPORTABLE** ✅

**Què va DINS el paquet/AppImage** (res a instal·lar al host):

| Peça | Contingut |
|------|-----------|
| `portable/python/` | CPython 3.12 portable + PyQt5 + numpy<2 (build **genèric**, sense AVX) |
| `portable/bin/ffmpeg` | build **estàtic** (importar mp3/aif/flac/m4a/ogg) |
| `portable/lib/` | **llibreries natives** de l'host Vamp i dels plugins |
| `nnls-chroma-linux64-local/` · `qm-vamp-plugins-linux64-local/` | plugins Vamp (Chordino, Queen Mary) |
| `vamp_host_local` | host Vamp propi (substitueix `sonic-annotator`, que queda de reserva) |

**Llibreries natives empaquetades** — 9 fitxers, ~3,1 MB. Les copia
`eines/libreries_natives.sh` **del mateix sistema que compila** (al CI,
`ubuntu-22.04`): no es baixa res i la glibc mínima queda lligada al build.

| Llibreria | Llicència | Per a |
|---|---|---|
| `libvamp-hostsdk.so.3` | MIT / BSD-3 | carregar i executar els plugins Vamp |
| `libsndfile.so.1` | LGPL-2.1+ | llegir els WAV |
| `libFLAC` · `libogg` · `libvorbis` · `libvorbisenc` · `libopus` | BSD-3 | còdecs de libsndfile |
| `libmpg123` · `libmp3lame` | LGPL-2.1 / LGPL-2.0 | mp3 |

**Què queda AL SO host** (el mínim absolut):

| Requisit | Detall |
|----------|--------|
| **`glibc` ≥ 2.35** | Ubuntu 22.04+ · Debian 12+ · Fedora 36+… (el CI compila a `ubuntu-22.04`, i això fixa el terra de l'AppImage) |
| **`libstdc++` / `libgcc_s`** | universals; **no** s'empaqueten (vegeu nota) |
| **Entorn d'escriptori** (X11 o Wayland) | per la GUI |
| **PipeWire o PulseAudio + `paplay` o `aplay`** | només per **escoltar**; opcional (sense això l'app fa la resta i avisa) |
| **Suport FUSE del nucli** | per executar l'AppImage (estàndard). Alternativa: `--appimage-extract-and-run` |

> ⚠️ **Per què no s'hi inclouen `libstdc++`/`libgcc`**: el Python portable i Qt
> els demanen del sistema, i empaquetar-los podria **ombrejar** una versió més
> nova i trencar Qt. Són presents a qualsevol distro amb glibc ≥ 2.35.

**Repositori (codi i AppImage publicada):**
**https://github.com/Pepelocotango/PROJECTE-AUTO-CHORDS**

**Verificació feta** (2026-10-07): dins un *namespace* de muntatge amb les **9
llibreries del sistema amagades** (`/dev/null` a sobre) i només `portable/lib`
disponible, `vamp_host_local` extreu acords (Chordino, 82 línies) i estructura
(`qm-segmenter`); l'app arrenca i passen **173/173 tests**.

---

## 1. Anàlisi inicial (històrica): què era autocontingut i què no

Projecte: **515 MB**.

| Peça | Mida | Autocontingut? | Bloqueig |
|------|------|----------------|----------|
| Codi Python (`app/`, `eines/`) | petit | ✅ | — |
| **Plugins Vamp** (`*-local/*.so`) | ~2 MB | ✅ **només libc/libstdc++** | — |
| `sonic-annotator` | 2,3 MB | ❌ | **~70 llibreries**: Qt6Core/Xml/Network, ICU, glib, gnutls, curl, krb5, sndfile… |
| `.venv` (PyQt5 202 MB + numpy 78 MB + pyqtgraph) | 300 MB | ⚠️ | **no portable**: `pyvenv.cfg` apunta a `/usr/bin/python3.12` + rutes absolutes |
| `.deps` (headers .deb per compilar) | 198 MB | ❌ (només build) | boost-dev 188 MB (no és runtime!) |
| **`ffmpeg`/`ffprobe`** | sistema | ❌ | `/usr/bin/ffmpeg` |
| **`paplay`** (play) | sistema | ❌ | PipeWire/PulseAudio |
| Python 3.12 del sistema | — | ❌ | `/usr/bin/python3.12` |

**Conclusió**: la part «d'anàlisi» (els plugins) i el codi **ja** són portables;
els bloquejos són (a) el **host Vamp** (`sonic-annotator`+Qt6), (b) el
**Python/PyQt5**, (c) l'**àudio**, (d) l'**import ffmpeg**.

## 2. Opcions per bloc

### A) Host Vamp — el bloqueig més gran ⭐
`sonic-annotator` arrossega **Qt6 + ICU + glib + gnutls + curl…** (mireu el
`ldd`): centenars de MB i lligams al sistema.

| Opció | Mida | Esforç | Nota |
|-------|------|--------|------|
| **Host propi** amb `libvamp-hostsdk` (C++ o el mòdul `vamp` de Python) | ~petit | **mitjà** | ⭐ depèn només de libc/libstdc++ + libsndfile; **ja compilem C++** |
| Empaquetar `sonic-annotator` + totes les seves libs | ~150-250 MB | baix | funciona però gros i fràgil entre distros |
| `vamp` (pip) | petit | baix | envolcalla `libvamp-hostsdk`; a provar al Q9400 |

### B) Python + PyQt5
| Opció | Mida | Esforç |
|-------|------|--------|
| **CPython portable** (`python-build-standalone`) + les rodes a dins | ~120 MB (PyQt5+numpy) | **baix** ⭐ |
| `PyInstaller` (one-folder) | ~150 MB | mitjà |
| **AppImage** (ho empaqueta tot) | ~150-200 MB | mitjà |

### C) Àudio (el més difícil d'«autocontingut»)
`paplay` depèn de **PipeWire/PulseAudio** del sistema. Opcions:
- **Assumir PipeWire/Pulse** (estàndard a qualsevol escriptori Linux actual): 0 esforç. ✅
- Empaquetar `libpulse` + el daemon: no té sentit.
- PortAudio empaquetat + ALSA directa: pitjor qualitat de mescla.

### D) Import de formats (`ffmpeg`)
- **`ffmpeg` estàtic** (builds estàtics oficials/community) dins el paquet: ~70 MB. ✅

### E) Altres SO (Windows/macOS)
- La **GUI (PyQt5) és portable**; el codi Python també.
- Però: **els plugins Vamp s'han de recompilar per a cada SO** (o empaquetar els
  binaris ja publicats: `nnls-chroma`, `segmentino`, `qm-vamp-plugins` en tenen
  per a Win/Mac) i l'àudio/ffmpeg canvien.
- **Esforç: alt.** No bloqueja el Linux portable.

## 3. Proposta de camí (per fases)

> ✅ **Fase 5 FETA (2026-10-07)**: `eines/empaqueta_portable.sh` munta la
> carpeta portable (excloent `.deps/`, `.venv/`, `.git/`, `temp/`…).
> **Verificat**: copiat a `/tmp` i executat des d'allà — **els 166 tests
> passen**, l'app carrega i el **pipeline complet funciona** (acords 54,
> estructura, compàs 1 = 9,49 s, BPM) i també **l'import d'mp3** amb el
> ffmpeg del paquet. Mida final: **~526 MB**.

> ✅ **Fase 3 FETA (2026-10-07)**: `ffmpeg` estàtic a `portable/bin/ffmpeg`
> (només ffmpeg: `ffprobe` no s'usava). `app/ffmpeg.py` el prefereix.
> **Nota de mida**: el portable real és **~528 MB** (Python 452 + ffmpeg 80),
> molt més que l'estimació inicial de ~160 MB — el CPython portable (225 MB),
> PyQt5/Qt5 (166 MB) i el ffmpeg (80 MB) pesen molt.

> ✅ **Fase 2 FETA (2026-10-07)**: **CPython portable** a `portable/python/`
> (`python-build-standalone` 3.12.15, build **genèric x86_64**, sense AVX) amb
> PyQt5 + numpy<2. `AUTO_CHORDS.sh` el prefereix. **Els 166 tests passen amb
> aquest Python.** `portable/` és al `.gitignore` (es regenera).

> ✅ **Fase 1 FETA**: host Vamp propi (`vamp_host_local`).

> ✅ **Fase 1 FETA (2026-10-07)**: host Vamp propi (`vamp_host_local`, 48 KB,
> 13 llibreries en comptes de 73) → `docs/QM_VAMP.md`. Ja no cal
> `sonic-annotator` (queda de reserva).

| Fase | Què | Mida resultant | Esforç |
|------|-----|----------------|--------|
| **1** | **Host Vamp propi** (treure `sonic-annotator`) | −(Qd6/ICU/glib) | mitjà |
| **2** | **CPython portable** + rodes dins la carpeta (+ `AUTO_CHORDS.sh` que hi apunti) | paquet ~160 MB | baix |
| **3** | `ffmpeg` estàtic embegut (opcional) | +70 MB | baix |
| **4** | Assumir PipeWire/Pulse per al play (documentar-ho) | 0 | — |
| **5** | *(opcional)* empaquetar com a **AppImage** | 1 fitxer | mitjà |

**Objectiu assolible**: una carpeta d'**~160 MB** que es copia a qualsevol
**Linux x86_64 modern** (amb PipeWire/Pulse) i funciona amb **doble clic**,
sense instal·lar Python ni res. → `./AUTO_CHORDS.sh` (que ja existeix i apunta
a `.venv/bin/python`, caldria fer-lo apuntar al Python portable).

## 4. Riscos / coses a verificar
- ⚠️ **Q9400 sense AVX**: el CPython portable i les rodes han de ser **SSE**.
  `numpy<2` ✅. Cal verificar els wheels de PyQt5.
- ⚠️ **`sonic-annotator` va amb Qt6**: per què? (probablement el lector de
  fitxers). Un host propi ho evitaria.
- ⚠️ El `.venv` actual **no és reubicable**; caldria un Python portable nou.
- ⚠️ `.deps` (198 MB) **no cal** per executar (només per compilar) → fora del paquet.
- ⚠️ Els `.so` dels plugins són **ELF Linux** → no serveixen a Windows/Mac.

## 5. Què es pot fer JA (sense risc)
- Excloure `.deps/` del paquet portable (198 MB estalviats).
- `AUTO_CHORDS.sh` que detecti el Python portable si hi és.
- Documentar el requisit de PipeWire/Pulse + ffmpeg.


---

## 6. Flux de treball i cicle de vida (IMPORTANT)

### Regla d'or
> **El paquet `AUTO_CHORDS_PORTABLE/` NO es toca mai.** És un **artefacte de
> build**: tot el codi viu al **projecte** (`PROJECTE AUTO CHORDS/`), i el
> paquet es **regenera** quan cal. Editar-hi res seria feina perduda (la
> propera regeneració ho esborraria).

### Cicle normal (canviar codi)
```bash
cd "PROJECTE AUTO CHORDS"
# 1) editar el codi, tests, commit
git add -A && git commit -m "..."
# 2) regenerar el paquet (germà del projecte)
./eines/empaqueta_portable.sh          # -> ../AUTO_CHORDS_PORTABLE/
```

### Dependències del paquet (només cal regenerar-les si falten o s'actualitzen)
| Eina | Què crea | Quan cal |
|------|----------|----------|
| `eines/crea_portable.sh` | `portable/` (CPython + ffmpeg + **llibreries natives**) | 1 cop; o si es vol actualitzar el Python/ffmpeg |
| `eines/libreries_natives.sh` | `portable/lib/` (Vamp + sndfile + còdecs) | la crida sol `crea_portable.sh`; es pot repetir sense risc |
| `eines/compila_vamp_host.sh` | `vamp_host_local` | 1 cop; o si canvia `eines/vamp_host.cpp` |
| `eines/empaqueta_portable.sh` | `../AUTO_CHORDS_PORTABLE/` | **cada vegada** que es vol el paquet al dia |

`empaqueta_portable.sh` **comprova** que existeixin `portable/python` i
`vamp_host_local`, i **refusa** un destí dins del projecte (bucle de còpia).

### Què va al paquet i què no
| Inclòs | Exclòs |
|--------|--------|
| `app/`, `eines/`, `docs/`, `*.md`, `*.py` de l'arrel | `.deps/` (només build) |
| `nnls-chroma-linux64-local/`, `qm-vamp-plugins-linux64-local/` | `.venv/` (dev/tests) |
| `vamp_host_local`, `sonic-annotator` (reserva) | `.git/`, `tauri-ui/`, `temp/` |
| **`portable/`** (Python + ffmpeg + **`lib/` amb les llibreries natives**) | `__pycache__/`, logs, `opcions_detecta.json` |
| `AUTO_CHORDS.sh` (llançador), `LLEGEIX-ME.txt` (generat) | el propi paquet (germà) |
