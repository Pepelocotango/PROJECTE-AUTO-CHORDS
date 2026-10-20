# Tempo per trams — motor d'autodetecció de BPM variable

> Implementat el **2026-10-21** (motor: `app/tempo.py`; acció de menú:
> *Analitza ▸ Detecta el tempo per trams…*). Complement del guiat
> (`ANALISI_GUIAT.md`), que és la versió **manual/assistida** del mateix
> problema.

## 1. Què resol

Un tema pot **no tindre** un BPM únic: directes, ritardandos, canvis de
secció, intros lliures, finals que es queden… Amb un sol número, la graella
se'n va a la meitat de la cançó. La solució dels DAW professionals és **un
tram de tempo cada pocs compassos** (Pro Tools Beat Detective en crea un per
compàs; Cubase en diu *Tempo Detection*; REAPER ho fa a mà amb *Create
measure from time selection*).

Ací: **un BPM cada N compassos** (4 per defecte) amb les fronteres **sempre
en línia de compàs**, que és el contracte de la graella
(`REGLES_TEMPS_GRID.md` §4).

## 2. Canonada (3 passos)

| # | Pas | Funció |
|---|-----|--------|
| 1 | **BPM de referència** del tema sencer (amb alternatives) | `tempo.detecta_bpm_candidats` |
| 2 | **Temps (beats) seguits** per programació dinàmica (Ellis 2007) | `tempo.segueix_beats` |
| 3 | **Blocs de N compassos** → un tram per bloc, BPM derivat de la seua durada | `tempo.beats_a_trams` |

### 2.1 Per què DP i no autocorrelació sola

L'autocorrelació diu **quin** tempo hi ha, però no **on** cauen els temps.
El DP maximitza la suma de la corba d'onsets als beats amb una penalització
per desviar-se del període:

```
puntuació = Σ onsets(beat_i) − tightness · Σ log(lag_i / P)²
```

amb `P` = període inicial (de la referència) i `tightness = 30` (baix a
posto: permet **deriva**, que és el que volem en un tema amb tempo variable).

⚠️ Dues trampes verificades:

- **Cal normalitzar la corba** (mitjana 0, desviació 1) abans del DP. Si no,
  la magnitud de l'envolupant ofega la penalització i el tracker salta a la
  meitat o al doble (a Otis donava **304 beats a 154 BPM** en compte de 262
  a 103,4).
- **La finestra de cerca de lags** ha de ser ampla (`0,5·P … 2·P`) perquè el
  DP puga travessar un canvi de secció.

### 2.2 Per què el BPM ix de la durada del bloc

El validador de la graella exigeix que cada tram interior tinga un **nombre
enter de compassos** i que les fronteres caiguen en una línia de compàs. Per
tant el BPM **no** es pot prendre de la mitjana dels intervals: es **deriva**
de la durada del bloc,

```
bpm = (4 · num / den) · 60 · m / (fi − base)
```

on `m = round((fi − base) / durada_compàs_estimada)`. Així la frontera cau
exactament damunt d'una línia de compàs i el contracte es compleix **sempre**
(ho comprova `tempo_map.valida_i_normalitza_compassos` abans d'aplicar res).

### 2.3 Offset (compàs 1)

El primer beat seguit és el **compàs 1** (offset). El tram inicial queda
parcial de 0 a l'offset: és l'única excepció que permet el contracte (el
compte enrere). Si l'usuari ho desmarca, el rellotge arranca a 0 i la pickup
s'absorbix dins del primer compàs.

### 2.4 Cua

Els **blocs només es tanquen sencers** (`N` compassos). Les restes del final
no es mesuren a banda: s'allarguen al tram anterior **conservant el seu
BPM**. Mesurar-les donava invents com «69 BPM» en l'últim compàs d'Otis.

## 3. Alternatives i fiabilitat (com Logic)

`candidats_bpm` puntua cada BPM amb la puntuació «comb» (pics de
l'autocorrelació a 1×, 2×, 3× i 4× el període, pesats 1/m) multiplicada pel
**prior** (plateau 85–150, caiguda suau fora). Retorna els `n` millors amb
la **fiabilitat relativa** (1,0 = el guanyador) i descarta candidats a menys
del 2 % (serien el mateix tempo).

A més, `detecta_bpm_candidats` fa una segona passada amb **rang ample
(40–240)** i el **mateix prior**: els valors que queden fora del rang
configurat es tornen com a `alternatives`. És el que permet avisar:

> tema de 120 BPM mesurat amb un rang 50–100 → surt **59,9** (la meitat) i
> l'alternativa **120,0** amb fiabilitat 1,0.

## 4. Comparativa amb els DAW (recerca, 20-10-2026)

| DAW | Com ho fa | Què n'hem pres |
|-----|-----------|----------------|
| Ableton Live | *Auto-Warp*: marcador al primer temps de cada compàs; *Warp From Here* per seccions; *Set 1.1.1 Here* | la idea de seccions i el downbeat manual |
| Logic Pro | *Smart Tempo*: 5 candidats amb barra de fiabilitat + *Hint Mode* | les 3 alternatives amb % i la referència global |
| Pro Tools | *Beat Detective*: la selecció ha de començar/acabar en beats, l'usuari diu quants compassos | mesurar **per blocs** i derivar el BPM de la durada |
| Cubase | *Tempo Detection*: mínim **7 s**, ×2/÷2/×4-3/×3-4, *Offbeat Correction* | el mínim de 7 s i els ràtios de tresets |
| REAPER | no en té de natiu: *Create measure from time selection*; ReaBeat fa refinament d'onsets, *gap filling* i correcció d'octava | el DP + la fusió de veïns |
| librosa | `beat_track(tightness=100)`, `feature.tempo(prior=…)` | l'algorisme (Ellis 2007) i el prior |
| aubio | autocorrelació + prior de Rayleigh | el prior sobre el tempo |

**Descartat**: detectors per aprenentatge (madmom, BeatNet, beat-this). El
Q9400 **no té AVX** i `torch`/ONNX no hi són viables (SIGILL o lentitud
inacceptable). Tot el motor és **numpy pur**.

## 5. API

```python
from app import tempo
res = tempo.detecta_bpm_candidats(wav, log, bpm_min=60, bpm_max=180,
                                  preferit=(85, 150), n=3)
# {'bpm': 103.4, 'candidats': [(103.4, 1.0), (101.3, 0.97), …],
#  'alternatives': [(52.2, 0.61), …]}

beats, base = tempo.segueix_beats(wav, log, tightness=30.0)

trams, off = tempo.beats_a_trams(beats, durada, num=4, den=4,
                                 cada_compassos=4, tolerancia=0.02)

trams, off, base = tempo.mapa_tempo_automatic(wav, log, durada=durada)
```

I per la GUI (`app/pipeline.py`): `detecta_bpm_tram_detallat`,
`detecta_bpm_detallat`, `detecta_tempo_per_trams`.

## 6. Xifres reals (Otis «Dock of the Bay», 165,7 s)

| Mesura | Abans | Ara |
|--------|-------|-----|
| BPM del tema sencer | 103,5 (rang 60–180) / **99,75** amb el rang de l'usuari (50–100) | **103,4** + alternativa 103,4 fora de rang |
| Loop 1,98–11,25 s | 52,25 (meitat) | **104,6** |
| Finestra del guiat (13,7 s) | **55,25** | 8 s → **~103** |
| Mapa per trams | no existia | **8 trams** de 100,4 a 106,5 (validat) |

## 7. Límits coneguts

- L'**intro** d'Otis (xiulada sola, 13 s) queda fora de l'anàlisi: el
  detector descarta el silenci inicial (llindar del 15 % del màxim). El
  primer tram comprén eixa zona amb el BPM del primer bloc musical.
- Un canvi de tempo **dins** d'un bloc de 4 compassos es reparteix: el tram
  mesura la mitjana ponderada del bloc. Amb `cada_compassos=1` es veu el
  canvi, a canvi de molts més trams.
- Els **rits lliures** (rubato) no tenen tempo: el mapa els assigna el del
  bloc i la graella no els seguirà mai bé (és el mateix que fa qualsevol DAW).
