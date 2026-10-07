# QM Vamp Plugins (Queen Mary) — compilats localment

> **2026-10-07.** Compilats i integrats a l'app. Vegeu també
> `docs/AUTODETECCIO_OPCIONS.md` i `docs/AUBIO_TEMPO.md`.

## Què és

Els **`qm-vamp-plugins`** de la **Queen Mary University of London** (C4DM) són
un joc de plugins **Vamp** de codi obert (**GPL**) que fan servir
**Audacity, Mixxx i Sonic Visualiser**. Inclouen:

| Plugin | Què fa |
|--------|--------|
| `qm-tempotracker` | **Beat tracker + tempo** (`tempo`, `beats`, `detection_fn`) |
| `qm-barbeattracker` | **Beats + BARS (downbeats)** — els compassos! |
| `qm-onsetdetector` | Onsets |
| `qm-keydetector` | **Tonalitat** (key) |
| `qm-segmenter` | **Estructura** (com el Segmentino) |
| `qm-chromagram`, `qm-constantq`, `qm-simple…` | Croma, CQT, MFCC… |

## Per què compilats a mà

**No són als repositoris d'Ubuntu** (`qm-vamp-plugins` no existeix a l'apt ni
al `.deb` del Sonic Visualiser). El lloc de descàrrega original
(`code.soundsoftware.ac.uk`) estava inaccessible, però el **codi font és a
GitHub** ([`c4dm/qm-vamp-plugins`](https://github.com/c4dm/qm-vamp-plugins))
amb les dependències al mateix GitHub (`c4dm/qm-dsp` + `c4dm/vamp-plugin-sdk`).

⚠️ **Q9400 sense AVX**: el Makefile fa servir **`-msse -msse2 -mfpmath=sse`**
(verificat: cap flag AVX) → **funciona al Q9400**.

## Com es va compilar (reproduïble)

```bash
cd /tmp/opencode && mkdir -p qmsrc && cd qmsrc
curl -sL -o src.tar.gz \
  https://github.com/c4dm/qm-vamp-plugins/archive/refs/heads/master.tar.gz
tar xzf src.tar.gz && cd qm-vamp-plugins-master
mkdir -p lib
git clone --depth 1 https://github.com/c4dm/qm-dsp lib/qm-dsp
git clone --depth 1 https://github.com/c4dm/vamp-plugin-sdk lib/vamp-plugin-sdk
make -C lib/qm-dsp -f build/linux/Makefile.linux64          # -> libqm-dsp.a
make -f build/linux/Makefile.linux64                        # -> qm-vamp-plugins.so
# copiar .so + .cat + .n3 a l'app:
cp qm-vamp-plugins.{so,cat,n3} "<PROJECTE>/qm-vamp-plugins-linux64-local/"
```

El directori `qm-vamp-plugins-linux64-local/` ja és a `pipeline.VAMP_DIRS`,
així que `sonic-annotator --list` els veu.

## Comparativa real (11 temes, 2026-10-07)

| Tema | `tempo.py` (actual) | `qm-tempotracker:tempo` | Real |
|------|--------------------:|------------------------:|-----:|
| 01 pep 101 | **101,0** ✅ | 103,4 | 101 |
| 02 pep 138 | **138,0** ✅ | 139,7 ✅ | 138 |
| 03 pep 70 | **70,0** ✅ | ❌ 141,6 | 70 |
| 04 pep 118 | **117,8** ✅ | 120,2 ✅ | 117,8 |
| 05 pep 107 | **107,0** ✅ | 110,0 ✅ | 107 |
| Otis Redding | **103,5** ✅ | 105,5 ✅ | ~103,5 |
| Chemical Brothers | **132,0** ✅ | 136,0 ✅ | 132 |
| Jamiroquai Feels | **87,0** ✅ | ❌ 172,3 | 87 |

👉 **Conclusió**: pel **tempo**, el `tempo.py` afinat fa **5/5** en el material
propi i el `qm-tempotracker` **4/5**. Es manté el `tempo.py` com a motor
principal; el qm queda com a **motor alternatiu** (i per a beats/bars/key).

## El valor real: BEATS i BARS

`qm-barbeattracker` dona els **downbeats**. Al tema de 101 (amb 9,5 s de
silenci) els compassos són:
```
0.01 · 2.36 · 4.74 · 7.13 · 9.49 · 11.88 ...   (interval ~2.38 s = 4 temps a 101)
                            ↑ 9.49 s = el COMPÀS 1 real!
```
→ **Es podria posar el compàs 1 sol** (l'acció que ara es fa a mà amb el
botó 📍). I els `beats` donen la graella real de pulsacions.

## Pendents / idees
- Motor de BPM triable al diàleg (nostre / qm / aubio) + mode **consens**.
- **Auto-compàs 1** amb `qm-barbeattracker:bars`.
- **Tonalitat** amb `qm-keydetector` (mostrar-la).
- Provar `qm-segmenter` per a l'estructura (alternativa al Segmentino).
