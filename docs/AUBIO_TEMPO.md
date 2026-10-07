> ⚠️ **OBSOLET per al BPM (2026-10-07)**: el detector d'aubio s'ha
> substituït per `app/tempo.py` (numpy, molt més encertat) i, com a
> alternativa, pel `qm-tempotracker` (vegeu `docs/QM_VAMP.md`). Aquest
> document es conserva com a històric del plugin d'aubio.

# Plugin Vamp d'aubio (tempo i beats) — com es va compilar

> Afegit 2026-10-05. Proporciona **detecció de BPM** i **pulsacions**
> des d'una WAV, integrat a l'arquitectura Vamp existent
> (`VAMP_DIRS` + `sonic-annotator`), **sense sudo**.

## Què aporta

El plugin `vamp-aubio.so` (biblioteca `aubio/vamp-aubio-plugins`) afegeix,
entre d'altres:

| Transform | Què dóna |
|---|---|
| `vamp:vamp-aubio:aubiotempo:tempo` | Tempo (per fotograma) |
| `vamp:vamp-aubio:aubiotempo:beats` | **Posicions de les pulsacions** (s) |
| `vamp:vamp-aubio:aubioonset:onsets` | Onsets |
| `vamp:vamp-aubio:aubiopitch:frequency` | To fonamental |
| `vamp:vamp-aubio:aubionotes:notes` | Notes MIDI-like |
| `vamp:vamp-aubio:aubiosilence:*` | Regions silencioses |
| `vamp:vamp-aubio:aubiomfcc:mfcc` · `aubiomelenergy:mfcc` · `aubiospecdesc:specdesc` | Descriptors espectrals |

## Ús

```bash
cd "PROJECTE AUTO CHORDS"
VP="nnls-chroma-linux64-local:segmentino-linux64-local:vamp-aubio-linux64-local"

# Beats (recomanat per calcular el BPM)
VAMP_PATH="$VP" ./sonic-annotator \
  -d vamp:vamp-aubio:aubiotempo:beats -w csv --csv-stdout tema.wav
```

**BPM recomanat**: derivar-lo de les pulsacions (no del `tempo` per
fotograma, que oscil·la):
```
BPM = 60 / mediana(intervals entre beats consecutius)
```

## Precisió observada

| Fitxer | BPM esperat | BPM calculat (beats) |
|---|---|---|
| `04 PEP LOGIC 118BMP.wav` | 118 | **~119–120** ✅ |
| `01 101bpm pep live RE-ESTRUCTURA.wav` | 101 | desviat (gravació **en directe**; el beat tracker hi pateix) |

> 🎯 Funciona bé en material amb pols estable (estudi/programat). En
> directe/improvisat pot desviar-se. Per a més precisió es pot valorar
> `qm-tempotracker` (QM Vamp Plugins), que és el referent, a canvi de més
> feina d'instal·lació.

## Dependències

| Component | Origen | Nota |
|---|---|---|
| `libaubio5` (runtime) | Paquet del sistema (`apt`) | `libaubio.so.5` |
| `libfftw3f` | Paquet del sistema | dependència d'aubio |
| `vamp-plugin-sdk` | Paquet del sistema (o `.deps/`) | headers + lib |
| gcc/g++/make | Sistema | compilació |
| `libaubio-dev` | `apt-get download` → `.deps/` (sense sudo) | **només els headers** |

## Reproducció (passos exactes)

```bash
# 1. Headers d'aubio SENSE sudo (patró del projecte)
mkdir -p /tmp/aubio-build && cd /tmp/aubio-build
apt-get download libaubio-dev          # baixa el .deb (no instal·la!)
dpkg-deb -x libaubio-dev_*.deb extract # extreu a extract/

# 2. Codi font del plugin
git clone --depth 1 https://github.com/aubio/vamp-aubio-plugins.git
cd vamp-aubio-plugins

# 3. Compilar (flags del Makefile.linux: -msse -msse2, MAI AVX)
EXTRACT=/tmp/aubio-build/extract
CXXFLAGS="-Wall -O2 -msse -msse2 -mfpmath=sse -fPIC -I/usr/include -I$EXTRACT/usr/include"
for f in libmain.cpp plugins/*.cpp; do g++ $CXXFLAGS -c "$f" -o "${f%.cpp}.o"; done

# 4. Enllaçar contra el libaubio.so.5 REAL (no el symlink del dev, que
#    ve trencat perquè el .deb -dev no porta la llibreria)
g++ -shared -o vamp-aubio.so libmain.o plugins/*.o \
    -L/usr/lib/x86_64-linux-gnu -lvamp-sdk -l:libaubio.so.5 \
    -Wl,-Bsymbolic -Wl,--version-script=vamp-plugin.map

# 5. Instal·lar al projecte
cp vamp-aubio.so vamp-aubio.cat vamp-aubio.n3 \
   "PROJECTE AUTO CHORDS/vamp-aubio-linux64-local/"
```

> ⚠️ **Trampa crítica**: si s'enllaça amb `-laubio` i el `libaubio.so` trobat
> és el **symlink del paquet -dev** (que apunta a `libaubio.so.5.4.8`, que
> només té el paquet runtime), el linker cau a **l'estàtic** `libaubio.a` i el
> plugin queda amb símbols d'FFTW **sense resoldre** en carregar-se:
> `undefined symbol: fftwf_malloc`. Cal enllaçar amb `-l:libaubio.so.5`.

## Compatibilitat maquinari

Flags `-msse -msse2` → **cap AVX** (compatible amb el Q9400). ✅

## Verificació

```bash
VAMP_PATH="nnls-chroma-linux64-local:segmentino-linux64-local:vamp-aubio-linux64-local" \
  ./sonic-annotator --list | grep aubiotempo
# → vamp:vamp-aubio:aubiotempo:beats
# → vamp:vamp-aubio:aubiotempo:tempo
```

## Pendent (proper pas)

- **Integrar a la GUI**: en carregar una WAV, cridar el transform `beats`,
  calcular el BPM i **omplir automàticament** el camp «BPM» (i,
  opcionalment, l'«Offset compàs 1» amb la primera pulsació).
- Valorar `qm-bartracker` (compassos) si cal afinar l'offset.
