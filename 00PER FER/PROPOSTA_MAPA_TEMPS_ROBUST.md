# Proposta de mapa de temps robust

**Data:** 2026-11-22  
**Estat:** document de treball, no implementat  
**Àmbit:** inici dels clips principals, BPM, compàs, `N` i deriva al final del tema  
**Corpus analitzat:** `CORPUS/XXPROVES I ANALISIS/proves autochords` (només lectura)

> Objectiu: que AUTO CHORDS puga generar o assistir un mapa de temps que aguante
> el metrònom i la graella de punta a punta. Un inici amb 20 ms d'error és
> acceptable i corregible; un BPM que deriva al final del tema no ho és.
>
> **Abast d'esta assistència:** la app **no ha d'endevinar** el compàs
> (`x/x`) ni el BPM percebut. Ha de:
>
> 1. proposar **onsets d'inici**;
> 2. dir si, en conjunt, el tema té una **periodicitat/BPM constant** o no;
> 3. oferir **diverses propostes** (inici, BPM/pols, mapa d'un sol BPM o per
>    trams) perquè l'usuari trie.
>
> L'usuari continua decidint el compàs, la pols percebuda i les fronteres.
>
> **Decisió d'abast:** no continuar analitzant DAWs. L'exportació es dissenya
> per al pitjor cas, però no és l'eix de la recerca. REAPER/Ardour només seran
> una validació local; Ableton/Cubase/Logic queden **no verificats** i fora de
> l'abast immediat.

---

## 1. Resum executiu

La conclusió principal és que **el problema no és només detectar l'inici**:
és mantindre la fase de la graella durant tota la cançó.

- **Inici:** un error de fins a **20 ms** es pot acceptar; l'usuari el pot
  ajustar i no desqualifica el mapa.
- **BPM:** un error petit es multiplica pel temps. Per exemple, 0,05 BPM
  d'error en una cançó de 4 minuts pot acabar en **més de 100 ms** de deriva.
  Ací sí que cal precisió.
- **Onsets:** són la millor eina per a l'inici, però **només en una finestra
  guiada**; els onsets globals fallen en intros fluixos o amb pickups.
- **QM:** pot ajudar a la fase/beats, però no és fiable per a downbeats ni
  compàs; no és prou exacte com a veritat única.
- **Motor intern:** és el millor per al BPM global inicial, però no per a
  l'inici dels clips en estos exemples.
- **Solució robusta:** ancoratge d'inici ajudat per l'usuari + onsets +
  **ajust de tempo constant per regressió sobre un tram llarg** + validació
  de `e(t)` amb punts no usats, inclòs el residu final. QM i el motor intern
  passen a ser inicialitzadors i
  controls, no la font final.

---

## 2. Què ens diu el corpus

Els mapes del corpus són coherents: `N` és conseqüència de **BPM + compàs +
fronteres**, no un valor que es detecte aïlladament. Els primers tres són 4/4;
els dos nous aporten 6/8 i un cas amb BPM i compàs variables.

| Cançó | Clips de tempo | Estructura de tempo/compàs |
|---|---:|---|
| Stayin' Alive | 2 | `0–0.3715` 1/4 161.5 N1 · `0.3715–283.144` 4/4 103.55 N122.0046 |
| Times Like These | 7 | 4/4 145.43 N1 · 4/4 144.69 N4 · **7/4** N2 · 4/4 N68 · **7/4** N8 · 4/4 N34 · **67.5 BPM** 4/4 N7.0777 |
| Every Breath You Take | 3 | `0–0.1778` 1/16 84.379 N1 · `0.1778–0.6891` 1/4 117.35 N1 · `0.6891–253.933` 4/4 117.35 N123.8259 |

### 2.1. Inicis dels clips principals

| Cançó | Inici real | QM beat més pròxim | Motor intern (`offset`) | Onset global | Onset guiat (finestra centrada) |
|---|---:|---:|---:|---:|---:|
| Stayin' Alive | 0.371517 | 0.383 (+11.5 ms) | 0.680 (+309 ms) | 0.380 (+8.5 ms) | 0.371517 (0) |
| Every Breath | 0.689061 | 0.673 (−15.7 ms) | 0.190 (−499 ms) | 0.170 (−519 ms) | 0.689061 (0) |
| Times Like These | 1.650283 | 1.659 (+8.7 ms) | 7.930 (+6.28 s) | 7.050 (+5.40 s) | 1.650283 (0) |

> **Avís de validació:** els “0 ms” de la columna guiada **no són una prova de
> precisió**. La finestra d'onsets estava centrada en l'etiqueta del corpus i,
> per tant, el clic era la resposta. Cal repetir amb clics simulats a ±50,
> ±150 i ±300 ms, i amb clics que caiguen al beat anterior. Mentre no es faça,
> no es pot afirmar que l'onset guiat encerta.

Lectura:

- **Onsets en finestra guiada:** pendent de validació independent; el resultat
  actual té fuita d'etiqueta.
- **QM beats:** 8–16 ms d'error; bo com a pista de fase, no com a frontera
  final ni com a compàs fiable.
- **Motor intern:** inutilitzable per a l'inici en estos intros; el seu valor
  està en el BPM global.
- **Onsets globals:** no; en Foo es perd fins a 7 s i en Police confon el
  pickup inicial.

### 2.2. El problema real: la deriva del BPM

Amb el BPM detectat actualment:

| Cançó | BPM real | BPM detectat | Deriva al final |
|---|---:|---:|---:|
| Stayin' Alive | 103.55 | 103.50 | **136 ms** |
| Every Breath | 117.35 | 117.30 | **108 ms** |
| Times Like These | 144.69 | 144.70 | **−14 ms** |

Per mantindre **20 ms** al final d'una cançó de 4 minuts, l'error de BPM ha
de ser de l'ordre de **0,008–0,012 BPM** (aproximadament 0,01 BPM). Els
detectors actuals treballen amb errors de 0,01–0,05 BPM: el marge és molt
estret i, en els casos pitjors, la graella pot incomplir la tolerància abans
del final.

**Prioritat:** primer BPM/fase; després inici; després compàs i fronteres.

### 2.3. Nous casos 6/8

S'han afegit dos mapes més difícils:

| Cas | Durada | Compàs | BPM | Clips | Resultat |
|---|---:|---|---:|---:|---|
| De res — cop de sort | 296.727 s | 6/8 3+3 | 82.5 negra/min | 1 | **BPM estable**; N136 |
| Alabama Shakes — Gimme All Your Love | 246.001 s | 6/8 → 4/4 → 6/8 | variable | 46 | **BPM no estable** i canvis de compàs |

#### De res

- `mapa_tempo.csv`: `0–296.727`, 6/8 `3+3`, **82.5 BPM de negra**,
  `beat_unit=negra_punt`, N136.000003.
- La referència del nom del projecte és **55 BPM de negra amb punt**:
  `55 × 1.5 = 82.5` negres/min.
- El motor intern detecta **55** (pols de negra amb punt) i
  `pipeline.detecta_bpm(..., beat_unit="negra_punt")` el converteix a
  **82.5**, que és el valor del mapa.
- `mapa_tempo_automatic` amb **6/8 i negra amb punt** dona **un sol tram
  82.500**, exacte. Amb 4/4 dona 55 i és incorrecte.
- Conclusió: és un cas **ESTABLE**, però demostra que el compàs i la unitat
  de pols no són opcionals.

#### Alabama Shakes

- 46 clips: **25 en 6/8** i **21 en 4/4**, amb retorn a 6/8 al final.
- 6/8: BPM de negra entre **47.95 i 55.79**; N total 43.53.
- 4/4: BPM entre **42.87 i 102.99**; N total 36.
- Canvis de compàs: 0–140.407 en 6/8, 140.407–233.309 en 4/4,
  233.309–246.001 en 6/8.
- El BPM canvia dins de cada secció; no és un sol tempo amb canvis de compàs.
- `mapa_tempo_automatic` en 6/8 genera 16 trams (~100–110 BPM) i en 4/4
  genera 8 trams (~68–72 BPM); cap reprodueix el mapa real.
- QM en 6/8 dona **172.35 BPM** i no dona downbeats útils.
- Conclusió: és el primer cas **NO ESTABLE** del corpus. Cal mapa manual o
  assistit per trams.

#### Implicació per al model

El `bpm` del CSV és **BPM de negra**; `beat_unit` indica la pols percebuda.
En 6/8, un mapa pot estar a 82.5 negres/min i percebre's a 55 negres amb punt.
La GUI ha de mostrar les dos coses sense confondre-les, i els detectors han de
rebre el compàs i la unitat de pols de manera explícita.

### 2.4. Prototip de regressió (mesura preliminar)

Provant un ajust robust sobre els onsets/beats actuals del tram estable:

| Cançó | Error de BPM | Deriva final | ≤20 ms? |
|---|---:|---:|---:|
| Stayin' Alive | +0,016 BPM | **+44 ms** | **No** |
| Times Like These | +0,008 BPM | **+11 ms** | Sí |
| Every Breath | +0,007 BPM | **+15 ms** | Sí |

És una mesura **preliminar i no validada**: usa onsets/beats amb la resolució
actual de 10 ms, i el prototip va partir de `segueix_beats`, un tracker que
regularitza cap a tempo constant. El residu és in-sample. Millora el detector
global, però no és una prova independent. Caldrà refinar els onsets a nivell de
mostra, usar punts no usats en l'ajust i repetir l'avaluació.

---

## 3. Decisions de producte

### 3.1. Toleràncies

- **Inici del clip principal:** objectiu ≤20 ms; ideal ≤10 ms. Un error de
  20 ms no invalida el mapa i es pot ajustar a mà.
- **Validació principal:** una corba d'error de fase `e(t)` suavitzada contra
  punts **no usats** en l'ajust; no una suma de toleràncies separades.
- **BPM:** objectiu `e_max`/`e_final` ≤20 ms; si no s'assoleix, no aplicar
  automàticament. La deriva i l'inici no s'han de sumar sense declarar-ho.
- **Estabilitat musical i deriva:** mana **`e_max`/`e_final` ≤20 ms**. No hi ha
  un llindar fix de 0,01 BPM: 0,01 BPM pot superar 20 ms en temes llargs o
  lents. Per a un tram de durada `D`, l'error de BPM admissible és aproximadament
  `20 ms × BPM / D`.
- **Fronteres interiors:** preferiblement fixades per l'usuari damunt d'un
  onset; tolerància operativa ≤20 ms, amb snap i previsualització.
- **Canvis de compàs:** no s'inferixen automàticament; l'usuari els confirma.
- **Tram final:** si hi ha half-time o canvi de tempo, es tracta com un tram
  propi, amb el seu BPM i la seua frontera.

### 3.2. Què és automàtic i què és assistit

| Tasca | Automàtic | Assistit per l'usuari |
|---|---|---|
| BPM global inicial | Sí, com a candidat | Confirmar o triar alternativa |
| Inici del cos principal | Proposta d'onset | Clic aproximat + confirmació |
| Final del cos principal | Proposta d'onset/beat | Clic aproximat + confirmació |
| Graella de beats | Sí, com a línia de referència | Validar amb metrònom |
| Compàs 4/4, 7/4… | No | Sí |
| Pickup/silenci inicial | Proposta | Triar tipus, compàs i `N` |
| Fronteres interiors | Snap a beat/onset | Marcar o ajustar |
| Tram final half-time | Detecció local opcional | Confirmar frontera i BPM |
| `N` | Càlcul exacte | Revisar si canvia el compàs |
| Mapa sencer sense revisió | **No** | Sempre previsualitzar |

### 3.3. Classificador d'estabilitat del BPM

Detectar un BPM no és el mateix que decidir si el tema té un **BPM estable**.
La app ha de fer explícita esta diferència i no ha de crear un mapa d'un sol
BPM només perquè el detector haja retornat un número.

**Entrada:** des de l'inici fins al final que marca l'usuari. Els dos ancoratges
són assistits per la app: l'usuari fa un clic aproximat i la app proposa
onsets/beats per confirmar. El final delimita el tram estable; la cua posterior,
si n'hi ha, queda com a provisional i pot tindre `N` fraccionari.

La classificació és sobre **periodicitat d'onsets/beats**, no sobre el compàs.
Un tema pot ser `ESTABLE` amb canvis de 4/4 a 7/4 o de 6/8 a 4/4; el que es
mesura és si una periodicitat explica el tram, no si el compàs és sempre el
mateix.

**La decisió ha de ser de tres estats, no binària:**

| Estat | Significat | Flux |
|---|---|---|
| **ESTABLE** | Un sol BPM explica el tram i `e(t)` és acceptable | Mapa automàtic assistit + confirmació |
| **ESTABLE AMB RESERVA** | El BPM pareix constant, però el fit o el residu no arriba a la tolerància | Assistit: refinar, validar i decidir |
| **NO ESTABLE** | Hi ha canvis de tempo, rubato o deriva no explicable per un sol BPM | Mapa manual o per trams |

No s'ha de confondre **BPM estable** amb **compàs estable**:

- Foo Fighters té BPM estable (144.69) i **canvis de compàs** 4/4 ↔ 7/4.
- Un tema pot tindre BPM estable i compàs variable.
- Un tema pot tindre compàs constant i BPM inestable.

#### Mètriques proposades

1. **BPM global candidat** i alternatives.
2. **Finestres locals** de 20–30 s o 8–16 beats; no pressuposar un compàs que
   encara no s'ha confirmat.
3. **Dispersió local** del BPM, normalitzada per octava.
4. **Tendència temporal** del BPM local: pendent i significança.
5. **Canvis sobtats** de període entre finestres consecutives.
6. **Residus del fit global** `t_i ≈ t0 + n_i · P`:
   - residu màxim sobre una corba suavitzada;
   - `e(t)` (màxim i final);
   - percentatge d'onsets/beats inlier;
   - cobertura del tram.
   - **Punts de validació no usats** en l'ajust; no usar només residu in-sample.
7. **Independència del tracker:** l'estabilitat s'avalua sobre ODF/onsets crus,
   no sobre els beats de `segueix_beats`, que ja regularitza cap a tempo constant.
8. **Confiança** segons energia, densitat d'onsets i estabilitat.
9. **Canvis de compàs** detectats o confirmats per l'usuari.

#### Criteris inicials

Els llindars s'han de calibrar amb el corpus i amb temes inestables; no han de
ser números inventats i definitius.

- `ESTABLE`:
  - el BPM global té suport suficient;
  - no hi ha canvis locals sostinguts;
  - `e_max` i `e_final` són **≤20 ms**;
  - no cal un llindar fix de 0,01 BPM: el criteri és la deriva final;
  - la majoria d'onsets/beats queden dins la graella;
  - el tram té prou durada per a decidir.
- `ESTABLE AMB RESERVA`:
  - el BPM local pareix constant;
  - però `e_max`/`e_final` superen 20 ms, o hi ha pocs inliers, o la confiança
    és baixa;
  - no s'aplica automàticament: es proposa refinar o fer mapa assistit.
- `NO ESTABLE`:
  - hi ha canvis de BPM sostinguts;
  - hi ha rubato o accelerando/ritardando;
  - el millor BPM global no explica el tram ni tan sols amb tolerància àmplia;
  - el detector no té prou suport.

#### Regla important

**Un BPM estable musicalment pot tindre un fit encara no prou precís.** En eixe
cas, la app no ha de dir “no estable”: ha de dir **“BPM estable amb reserva”** i
passar al flux assistit. Això evita confondre un problema de mesura amb un
canvi real de tempo.

#### Exemple d'UX

Tram estable analitzat:

```text
Tram: 14.091–206.502 s
BPM: 144.69 (estable)
Compàs: 4/4 → 7/4 → 4/4
Deriva estimada al final: 11 ms ✔
Decisió: mapa assistit de compàs
```

Tram no estable:

```text
Tram: 0.000–180.000 s
BPM: no estable
Canvis detectats: 2 (74.5 BPM, 120.2 BPM)
Decisió: mapa manual o per trams
```

#### Propostes que ha d'oferir la app

La app no ha de tornar un únic resultat; ha de tornar una llista curta i
ordenada perquè l'usuari trie:

| Tipus | Exemple de proposta |
|---|---|
| Inici | `0.3715` · `0.3831` · `0.5200` (amb energia i distància) |
| BPM/pols | `55.0` · `82.5` · `110.0` (factors 1×, 1,5×, 2×) |
| Estabilitat | `ESTABLE` · `ESTABLE AMB RESERVA` · `NO ESTABLE` |
| Mapa | un sol BPM · per trams · manual |
| Fronteres | candidats d'onset/downbeat, no una sola frontera opaca |

Cada proposta ha de mostrar:

- valor;
- confiança o residu;
- relació amb les altres (1×, 2×, 1,5×…);
- si és només una hipòtesi o si ha passat la validació.

La llista de BPM no és una llista de “BPM percebuts”: són **candidats de
periodicitat** perquè l'usuari trie la pols que vulga usar al mapa.

#### Fallback si no és estable

- No crear un mapa d'un sol BPM.
- Oferir **mapa manual** i **mapa assistit per trams**.
- Proposar fronteres i BPM locals amb confiança, però no aplicar-los sense
  confirmació.
- Permetre rubricar/ajustar cada tram.
- Validar cada tram amb el seu propi residu.

### 3.4. La Guia ràpida com a orquestrador

**Decisió:** tot el flux assistit s'ha d'iniciar des del botó **Guia ràpida**.
No s'ha de repartir en cinc botons o en un menú nou.

#### Estat actual

- `app/main.py`: el botó `b_guia` ja existix i ja està connectat a
  `_obre_guia_rapida`.
- `_obre_guia_rapida()` només obri `DialegGuiaRapida`.
- `app/dialeg_guia_rapida.py` és una guia **només informativa** de cinc
  pantalles; no toca el model.
- Ja existixen les peces de detecció, mapa, validació i previsualització. El
  que falta és un **coordinador** que les encadene.

#### Flux dins de la Guia ràpida

1. **Obri l'àudio** o comprova que ja n'hi ha un.
2. L'usuari marca **l'inici i el final** del tram principal amb ajuda de la
   app: clic aproximat i confirmació d'onset/beat. La cua posterior al final
   queda com a provisional. Opcionalment pot usar A–B per a una prova local.
3. La guia executa una única anàlisi i mostra propostes:
   - onsets candidats d'inici;
   - BPM/periodicitats candidates amb factors;
   - estat d'estabilitat;
   - fronteres candidates;
   - proposta de mapa d'un sol BPM o per trams.
4. L'usuari tria:
   - onset inicial;
   - candidat de BPM/pols;
   - si accepta el mapa d'un BPM o vol mapa per trams;
   - compàs, `beat_unit`, pickup i fronteres.
5. La guia mostra una **previsualització** amb metrònom/graella.
6. Només després de confirmar, s'aplica el mapa.

Si l'usuari cancel·la en qualsevol pas, **no es toca el model**.

#### Reutilització d'eines existents

| Necessitat | Eina existent | Ús |
|---|---|---|
| Onsets inicials | `tempo.detecta_onsets`; `analisi_ui._analitza_onsets_loop` | Finestra guiada i candidats |
| BPM candidats | `tempo.detecta_bpm_candidats`; `pipeline.detecta_bpm` | Propostes i conversió per `beat_unit` |
| Beats/QM | `beats.detecta`; `pipeline.detecta_bpm_tram` | Fase, controls i propostes |
| Estabilitat | ODF/onsets crus + regressió/validació | `segueix_beats` només com a inicialitzador |
| Mapa d'un BPM | `tempo.mapa_tempo_automatic`; `tempo.beats_a_trams` | Proposta inicial |
| Mapa per trams | `pipeline.detecta_tempo_per_trams` | Proposta de trams |
| `N` i validació | `tempo_map`, `mapa_tempo`, `tempo_recalc` | Càlcul i comprovació |
| Aplicar mapa | `visor_tempo.aplica_tempo_trams` | Només amb confirmació |
| Previsualització | `visor_transport.set_metro_forcat` | Metrònom sobre la graella proposada |
| Fil de treball | `app/feines.py` + `_obre_progres` | Anàlisi sense bloquejar la GUI |
| Diàleg | `DialegGuiaRapida` (`QStackedWidget`) | Convertir-lo en assistent |
| Rang A–B | `visor._loop_vals()` | Opcional: inici/final per a una prova |

#### Estratègia de mínim codi

1. **No duplicar detectors**: la detecció, el mapa, `N`, la validació i
   l'aplicació ja existixen. Sí que caldrà una capa d'orquestració nova.
2. Convertir `DialegGuiaRapida` en un **assistent amb accions**, conservant
   les pantalles d'ajuda actuals com a context.
3. Afegir un **coordinador** menut que cride les funcions existents en ordre:
   onsets → candidats BPM → estabilitat → propostes → previsualització →
   aplicació.
4. Reutilitzar `Feina` i el progrés existent per a l'anàlisi.
5. No duplicar la lògica de `_analitza_bpm`, `_analitza_bpm_loop` ni
   `_analitza_onsets_loop`: si cal, extraure una funció comuna o cridar les
   funcions de `tempo`/`beats` directament.
6. Mantindre un sol punt d'entrada: **Guia ràpida**. Els botons tècnics
   actuals poden quedar com a dreceres, però no han de ser obligatoris.
7. Fer el flux **fail closed**: si no hi ha prou confiança, no aplicar res i
   deixar el mapa manual.

#### Criteri d'acceptació del flux

- Es pot completar des del botó **Guia ràpida** amb un sol fil conductor.
- L'usuari pot cancel·lar sense canvis.
- La app proposa, com a mínim: un onset, diversos BPM/pols, un estat
  d'estabilitat i un mapa (o diversos trams).
- Res s'aplica sense confirmació.
- No s'ha duplicat cap detector ni s'ha creat un motor paral·lel.

---

### 3.5. Repartiment de variables i opcions

La regla general: **la app proposa; l'usuari decideix**. Les propostes
automàtiques no s'apliquen fins que l'usuari les confirma.

#### A. Variables que decideix l'usuari

Són decisions musicals o de producte que la app **no ha d'endevinar**:

- **Compàs** (`x/x`) de cada tram: 4/4, 6/8, 7/4, 1/4…
- **Canvis de compàs** i la seua seqüència.
- **Agrupació** del compàs: `3+3`, `4+4`, buit…
- **Pols percebuda / `beat_unit`**: negra, negra amb punt, corxera,
  semicorxera…
- **Inici i final del tram principal** amb els marcadors `inici_analisi` i
  `final_analisi`; els dos amb assistència d'onsets/beats. Després del final
  pot quedar una cua provisional.
- **Tipus de clip inicial**: silenci, pickup, anacrusi o cap.
- **Compàs i `N` del clip inicial**, si no és el mateix que el principal.
- **Nivell de pols/família de BPM** (1×, 1,5×, 2×…). El **valor fi** el
  proposa la regressió i l'usuari l'accepta o el sobreescriu.
- **Tipus de mapa**: un sol BPM, per trams o manual.
- **Rubato**: marcar un tram com a rubato o no.
- **Canvi final** de tempo o half-time.
- **Aplicar, desar o descartar** el mapa.
- **Tolerància i criteri de qualitat** que vol usar l'usuari.
- **Motor preferit** (intern, QM o onsets), si en vol triar un.
- **Sensibilitat** del detector, si la vol ajustar.
- **Nombre de propostes** que vol vore.

#### B. Variables usuari assistides per la app

L'usuari dona una referència o pren la decisió, però la app proposa, refina o
valida:

- **Onset inicial**: l'usuari fa un clic aproximat; la app proposa 1–3
  onsets i l'usuari confirma.
- **Fase/offset inicial**: la app l'ajusta al primer beat/onset confirmat.
- **BPM**: la app proposa diversos candidats; l'usuari tria, ajusta o
  descarta.
- **Pols**: la app mostra candidats relacionats (1×, 1,5×, 2×…); l'usuari
  decideix quina és la pols del mapa.
- **Estabilitat**: la app proposa `ESTABLE`, `ESTABLE AMB RESERVA` o
  `NO ESTABLE`; l'usuari pot acceptar o corregir.
- **Fronteres interiors**: la app proposa onsets/beats; l'usuari confirma
  o mou.
- **Canvis de tempo**: la app detecta candidats; l'usuari decideix on són i
  com s'etiqueten.
- **Canvis de compàs**: la app pot assenyalar un canvi de període o una
  frontera; l'usuari assigna el `x/x`.
- **`N`**: la app el calcula a partir de frontera + BPM + compàs; l'usuari
  el revisa.
- **Clip inicial**: la app proposa una opció per defecte; l'usuari tria el
  tipus i el compàs.
- **Deriva final**: la app calcula el residu; l'usuari decideix si accepta,
  refina o fa mapa per trams.
- **Mapa resultant**: la app el previsualitza; l'usuari aplica o descarta.

#### C. Variables/opcions proposades automàticament per la app

La app pot calcular i presentar estes propostes sense que l'usuari les
decidisca prèviament:

- **Llista d'onsets candidats** a l'inici, amb energia i distància.
- **Llista de BPM/periodicitats candidates**, amb confiança i factors.
- **Classificació d'estabilitat** del tram: `ESTABLE`,
  `ESTABLE AMB RESERVA` o `NO ESTABLE`.
- **Fronteres candidates** per a canvis de període o de secció.
- **Qualitat del fit**: `e_max`, `e_final`, inliers i cobertura.
- **`N` calculat** per a una combinació de frontera, BPM i compàs.
- **Proposta de mapa d'un sol BPM** amb fase ancorada.
- **Proposta de mapa per trams** amb BPM locals i confiança.
- **Proposta de clip inicial** (silenci/pickup) amb una opció per defecte.
- **Avisos de risc**: pocs beats, deriva excessiva, pols ambigua, canvi
  sobtat.

La app **no proposa automàticament**:

- el compàs `x/x` d'un tram;
- la pols percebuda com a veritat;
- el valor fi del BPM (el calcula i el proposa; l'usuari decideix).
- les fronteres finals;
- l'aplicació del mapa.

#### Nota sobre el corpus

El corpus actual té **cinc temes**:

- Stayin' Alive: 4/4, **BPM estable** 103.55.
- Every Breath: 4/4, **BPM estable** 117.35.
- Times Like These: 4/4 amb canvis a 7/4, **BPM estable** 144.69 i final a
  67.5.
- De res — cop de sort: 6/8, **BPM estable** 82.5 (55 negres amb punt).
- Alabama Shakes — Gimme All Your Love: 6/8 → 4/4 → 6/8, **BPM no estable**
  i canvis de compàs; és el primer cas **NO ESTABLE**.

Per calibrar millor el classificador caldran més casos inestables (rubato,
accelerando, directes), sense modificar estos corpus.

### 3.6. Ancoratge d'inici i final; cua provisional

**Decisió:** l'usuari marca **l'inici i el final del tram d'anàlisi** amb dos
marcadors independents. La app assistix els dos amb la mateixa metodologia:
clic aproximat, candidats d'onset/beat i confirmació.

`final_analisi` **no és la fi del mapa**: només delimita què s'analitza. El mapa
pot continuar fins al final de la WAV amb una cua provisional.

Conseqüències:

- Cap dels dos marcadors no talla clips de tempo.
- El mapa pot continuar fins al final de la WAV; la cua posterior al
  `final_analisi` queda com a **provisional**.
- `final_analisi` no tanca ni retalla l'últim clip del mapa.
- L'últim clip pot tindre `N` fraccionari mentre no es resol la cua.
- Els clips interiors, inclòs el penúltim, continuen subjectes a `N` enter i a
  la validació del compàs.
- Moure l'inici o el final no obliga a desfer el mapa.
- Si no hi ha `final_analisi`, no es fa la classificació automàtica de cos
  estable: es treballa en mode manual o amb una cua provisional.

Implicació per a l'anàlisi d'estabilitat:

- El classificador treballa exactament dins `[inici_analisi, final_analisi]`.
- La cua posterior no contamina la decisió del cos principal.
- L'usuari pot ajustar el final si un outro o un canvi de tempo entra dins del
  tram.

Implicació per al model:

- Ja existixen rutes que accepten l'últim clip fraccionari
  (`permet_ultim_fraccionari=True` a `mapa_tempo`/`tempo_map`/`visor_tempo`).
- Cal revisar els camins que hui forcen `N` enter a tots els clips perquè
  respecten la cua provisional.
- No fa falta un motor de detecció nou; sí una capa d'anàlisi i validació nova.
- El clip inicial `0 → inici` continua sent una decisió separada de l'usuari.

### 3.7. Marcadors d'anàlisi independents

**Proposta:** dos marcadors especials, `inici_analisi` i `final_analisi`, que
no són clips de tempo ni fronteres del mapa. Només delimiten el tram que la
Guia ràpida analitza. `final_analisi` **no és la fi del mapa**.

És una bona solució perquè separa dos conceptes que no s'han de confondre:

- **mapa**: clips, BPM, compàs, `N`, fronteres i cua final;
- **rang d'anàlisi**: interval on la app busca onsets, estabilitat i
  propostes.

#### Per què és millor que marcar el final amb un tall de tempo

- No obliga a resoldre el final del tema per començar a treballar.
- No crea ni parteix clips.
- No imposa `N` enter a l'últim clip.
- Els marcadors es poden moure sense desfer el mapa.
- No alteren la validació de `N` dels clips interiors.
- L'últim clip pot quedar com a cua provisional fins al final.
- Es poden fer diverses anàlisis canviant només els marcadors, sense tocar el
  model.

#### Regles

- **Inici**: obligatori per a l'anàlisi assistida.
- **Final**: també marcat per l'usuari, amb assistència d'onsets/beats. Sense
  final no es fa la classificació de cos estable; es pot treballar en mode
  manual o amb una cua provisional.
- Han de ser únics: com a màxim un `inici_analisi` i un `final_analisi`.
- `final_analisi` ha de ser posterior a `inici_analisi`.
- No participen en el recalcul de tempo ni en l'exportació del mapa.
- No substitueixen el loop A–B: el loop és reproducció; estos marcadors són
  anàlisi.
- Es poden amagar/mostrar al timeline.
- No s'han de confondre amb els marcadors `inici`/`final` que usa el retall
  d'extrems de la WAV.

#### Reutilització de les eines existents

| Necessitat | Eina existent | Canvi mínim |
|---|---|---|
| Marcadors independents | `app/marcadors.py`, `visor.marcadors`, `marcador_tipus` | Afegir els dos tipus i les etiquetes |
| Persistència | `pipeline.desa_marcadors`, `llegeix_marcadors_tipus`, `marcadors.csv` | Cap canvi d'estructura |
| Pintar-los | `timeline_layers.MarkerLayer` | Text/color propi |
| Moure'ls | `visor_marcadors._mou_marcador` | Cap canvi |
| Esborrar-los | `visor_marcadors.elimina_marcador` | Cap canvi |
| Rang per a anàlisi | funció menuda `_rang_analisi()` sobre els marcadors | Retorna `(inici, final)` o `(inici, durada)` |
| Guia ràpida | `DialegGuiaRapida`, `_obre_guia_rapida` | Passar el rang a les anàlisis |
| Anàlisi | `tempo.detecta_onsets`, `detecta_bpm_candidats`, `segueix_beats` | Usar el rang, no canviar el motor |

No cal tocar `mapa_tempo.csv` ni afegir cap taula nova. Els marcadors ja són
anotacions independents i ja es desen al projecte.

#### Criteri d'acceptació

- Es pot treballar amb `inici_analisi` i `final_analisi`, tots dos assistits.
- Canviar els marcadors no parteix cap clip.
- L'últim clip pot tindre `N` fraccionari.
- Els clips interiors, inclòs el penúltim, continuen validant-se amb `N` enter.
- La Guia ràpida usa exactament el rang dels marcadors.

### 3.8. Convenció d'atac, gap i referència

#### Convenció única

Hi ha un `t_onset` intern canònic per a l'app, calculat amb el mateix detector i
el mateix refinament per a:

- l'ancoratge que confirma l'usuari;
- l'ajust de fase i període;
- la comparació de resultats.

La **referència independent de la Fase 0 no usa eixe detector**. És una anotació
humana sobre l'ona, amb un criteri d'atac declarat. La diferència entre detector
i anotador s'ha de mesurar per timbre:

```
biaix_atac = t_detector − t_anotador
```

No és una convenció compartida: és un desplaçament conegut que s'ha de
quantificar abans de comparar res. No depén només del timbre:

- llindar del detector: 10 % del pic local;
- llindar de l'anotador: 3 × RMS de la finestra de 20 ms més silenciosa dins
  dels 100 ms previs al clic, amb un sostingut mínim d'1 ms;
- en atacs ràpids poden coincidir; en atacs lents difereixen 2–5 ms;
- en gravacions sorolloses o mescles denses el llindar de l'anotador puja i el
  biaix canvia.

Per això cal registrar, amb cada anotació:

- relació pic/soroll (`SNR`);
- temps de pujada de l'atac;
- filtre aplicat (el detector actual treballa a banda completa).

La versió filtrada serà la norma en mescles denses; el filtre ha de quedar
declarat per a l'anotador i per al detector.

Definició operativa de `t_onset` de l'app:

1. Pic de l'ODF (resolució 10 ms).
2. Envolupant de pic causal amb finestra de 12 ms.
3. Dins de `[pic, pic + 80 ms]`, es pren el màxim de l'envolupant.
4. Terra: percentil 10 de l'envolupant des de **50 ms abans del pic de l'ODF**
   fins al pic de l'envolupant.
   Llindar = `max(10 % del pic local, 3 × terra)`, limitat a `50 %` del pic.
5. Es retrocedix des del pic fins al primer sample per davall del llindar o
   fins a la vall d'un so anterior. La vall es considera separada si torna a
   pujar més d'un **25 %** per damunt del mínim.
6. Es retorna el sample resultant amb 6 decimals.

Al manifest han de constar totes les constants: `50 ms` (finestra del terra),
`12 ms` (envolupant), `80 ms` (cerca endavant), `10 %` (llindar), `50 %`
(topall), `25 %` (vall) i la versió de l'algorisme.

La referència humana no usa este càlcul; mesura un **biaix d'atac** que depén
del timbre, del soroll i del filtre.

**El 10 % és una convenció operativa del detector, no una definició universal
d'inici musical.** En bombos i caixes pot coincidir amb l'inici físic; en atacs
lents o exponencials pot quedar 20–30 ms després. Per a pads i cordes lentes,
l'ancoratge de l'usuari ha de poder manar sobre eixa convenció.

La Guia ràpida ha de mostrar, per a l'inici:

- `t_10`: creuament del 10 %;
- `t_físic`: inici de l'atac;
- diferència en ms;
- efecte sobre la graella: si es tria `t_físic`, el compàs 1 i tota la graella
  es desplacen eixa diferència; si es tria `t_10`, la graella queda ancorada al
  criteri del detector.

L'usuari tria i veu el desplaçament abans d'aplicar.

Sobre eixe `t_onset` es poden aplicar desplaçaments explícits i documentats:

- `t_cut = t_onset − pre_roll` per a un tall d'àudio;
- `t_click = t_onset + latency_comp` per al metrònom.

No són convencions diferents; són transformacions declarades.

#### Política del gap

Definicions:

- `t_onset`: onset que confirma l'usuari.
- `P`: període ajustat sobre molts onsets.
- `t0`: fase global de la graella.
- `t_grid`: línia de graella més pròxima a `t_onset`.
- `gap = t_onset − t_grid`.

El llindar no és un valor fix de 20 ms. Es compara amb:

- la dispersió robusta (MAD) dels residus;
- la fracció del període `P`;
- el nombre d'onsets i la confiança de l'ajust.

Tres règims:

| Règim | Interpretació | Acció |
|---|---|---|
| Petit, dins del soroll | microtiming del cop | compàs 1 a la graella |
| Mitjà, significatiu però molt menor que `P` | biaix d'instrument o convenció d'atac | mostrar gap i deixar triar |
| Gran, ordre de `P/4` o més | pols o fase equivocats | reajustar amb fase restringida o canviar de candidat |

El gap només és interpretable si l'onset de l'usuari i els de l'ajust tenen la
mateixa convenció d'atac. Si no, el gap constant només mesura una diferència de
detector.

#### Dues graelles de referència

Si l'ajust es fa sobre l'esdeveniment confirmat, el gap és pròxim a zero per
construcció. La magnitud informativa passa a ser:

- **graella de la referència**;
- **graella de tots els onsets**;
- diferència entre les dues.

La primera és la del mapa; la segona és diagnòstic. L'usuari tria la referència
en construir el mapa; el metrònom sempre sona eixa graella.

#### Recurrències i plantilla

No cal periodicitat a nivell de pols. Un acord que sona cada dos compassos pot
ser referència si té prou recurrències regulars per ajustar `P`.

Per a la versió mínima es pot usar correlació creuada d'una plantilla:

- l'usuari selecciona un fragment/gest;
- es busca on es repetix sobre una banda filtrada o l'envolupant;
- es proposen candidats;
- l'usuari confirma.

No cal classificador d'instruments. Si hi ha poques recurrències o poca
confiança, es proposa el pols mitjà.

#### Una sola graella

- El mapa té una sola graella: la de la referència triada en construir-lo.
- El metrònom sona eixa graella.
- Les altres referències són diagnòstic superposat (“la caixa va +9 ms”).
- Canviar la referència és una acció explícita que recalcula el mapa, no un
  selector del metrònom.
- Això **no elimina** les opcions actuals del metrònom: patró de compàs,
  denominador, agrupació, volum, BPM percebut/intern i beats QM continuen
  existint com a capes o clics complementaris sobre la mateixa graella.

#### Corba d'error

La validació principal és `e(t)`, l'error de fase suavitzat contra punts no
usats en l'ajust. Es descompon en:

- terme constant: gap;
- pendent: error de BPM;
- estructura: canvi de tempo o rubato.

Es reporten `e_max`, `e_final` i el perfil, no una suma opaca de toleràncies.

### 3.9. Exportació: decisions bàsiques

**No es continua analitzant DAWs en esta fase.** L'exportació es dissenya per al
pitjor cas, però la recerca principal és el mapa de temps.

**Consumidor principal:** el mapa editable i l'exportació a DAW. El metrònom és
validació; l'harmonia és una capa secundària. La referència per defecte ha de
ser un transitori recurrent (bombo, caixa o cop de baix), no el promig de la
banda, perquè és el que justifica la tolerància estricta de 10–20 ms.

Principis:

- **Font de veritat:** la WAV i el mapa intern.
- **MIDI:** còpia portable, no font de veritat.
- **Precisió:** es garantix a l'app i es verifica per anada i tornada.
- **DAW:** només es mesura una vegada per eina; no es dissenya al voltant d'un
  DAW concret.
- **Abast de validació:** només REAPER 7.80 i Ardour 8.4 estan verificats com a
  prova local. Ableton, Cubase i Logic són **no verificats** i representen el
  pitjor cas; no es poden usar per afirmar una validació universal.

Capes d'exportació:

1. **MIDI** amb `Set Tempo`, `Time Signature` i markers per tram.
2. **Pista de clic en àudio** renderitzada a mostra a partir del mapa intern.
3. **Round-trip dins l'app**: llegir el MIDI generat, reconstruir la línia de
   temps i comparar-la amb el mapa intern.

Avisos d'importació:

- La WAV ha d'anar en **temps absolut**: sense *warp* a Ableton, sense mode
  musical a Cubase, sense flex a Logic ni base de temps en beats a REAPER.
- La pista de clic en àudio és **sempre obligatòria**; un DAW pot ignorar el
  mapa o importar només el primer canvi de tempo.
- El clic exportat s'alinea al `t_grid` de la graella, amb el seu transitori
  propi; **no** s'ha d'aplicar `latency_comp` de reproducció.
- El manifest ha de dur el mapa intern amb precisió completa (`BPM_DEC=6`), la
  convenció d'atac, els offsets aplicats i la versió del generador; així es pot
  recalcular l'avís sense obrir l'app.
- Els markers han de ser ASCII i dur el `beat_unit` quan siga compost.
- `PPQ 480` és suficient per a la tolerància de 20 ms.
- `BPM_DEC=6` al CSV; la GUI/exportació no ha d'arredonir a 2 decimals.

Protocol de mesura:

- El MIDI de calibratge ha de dur **una nota per beat**, a més del mapa.
- La WAV de calibratge ha de dur clics a posicions exactes del mapa intern.
- Es fa un *bounce* i s'analitza en Python la diferència clic WAV / nota MIDI.
- Interessa el **pendent i la forma**, no el valor absolut: un desplaçament
  constant pot ser latència; una deriva és error de tempo.
- El lector de bounces ha de suportar **24 bits i `float32`**, no només PCM16.
- El round-trip ha de comprovar explícitament que **no hi ha cap pas per un
  format de 2 decimals** entremig; no n'hi ha prou amb suposar-ho.

Proves:

- **REAPER 7.80** i **Ardour 8.4** són la validació local.
- Altres DAWs (Ableton, Cubase, Logic) queden **no verificats** i fora de
  l'abast immediat.
- L'alternança d'arrodoniment cada ~30 s queda com a **mode de precisió
  opcional**, només si una prova de camp demostra que cal.

#### Garantia de l'app i incertesa del DAW

L'app pot garantir:

- que la WAV exportada i la pista de clic es generen a partir del **mapa
  intern**;
- que el clic està renderitzat a nivell de mostra;
- que el round-trip del MIDI es comprova dins l'app.

L'app **no pot garantir**:

- que el mapa intern siga musicalment correcte;
- que un DAW conserve tots els events de tempo;
- que un DAW no arredonisca el BPM en importar.

Per tant, “garantia” vol dir **fidelitat d'exportació**, no veritat musical ni
compatibilitat universal.

#### Perfils per capacitat, no per DAW

No s'ha de fer “versió per a Ableton” ni “versió per a Cubase”. S'ha de fer una
escala de suport:

1. **MIDI complet + clic**: el DAW respecta els events de tempo.
2. **MIDI amb trams curts o arrodoniment alternat + clic**: el DAW arrodoneix
   el BPM; el clic continua sent la referència.
3. **Marcadors + clic**: el DAW ignora o importa malament el mapa de tempo.

El clic en àudio és el mínim comú: si tot el demés falla, l'usuari pot alinear
la WAV i els clips contra el clic.

#### Pèrdua calculada per cançó

No n'hi ha prou amb un avís genèric. Per a cada cançó, l'app pot calcular
l'escenari de pèrdua:

```
deriva ≈ durada × (error_d'arrodoniment / BPM)
```

Exemples amb 103,55 BPM i 283 s:

| Precisió del DAW | Error màxim de BPM | Deriva aproximada |
|---|---:|---:|
| 3 decimals | 0,0005 | ~1,4 ms |
| 2 decimals | 0,005 | ~14 ms |
| 1 decimal | 0,05 | ~140 ms |

S'ha de calcular:

- per tram, si el DAW respecta els events;
- per la cançó sencera, si només conserva el primer tempo;
- i amb l'escenari pitjor, no amb el promig.

Si el DAW només conserva el primer tempo, no és un error d'arrodoniment: és un
desfasament acumulat pels canvis de tempo ignorats. En eixe cas cal sumar les
diferències per tram o recalcular les posicions, no aplicar la fórmula
d'arrodoniment.

Només cal avisar quan supera el pressupost acordat.

#### Joc de prova per a l'usuari

Un joc de prova pot ser:

- una WAV amb clics a posicions exactes;
- un MIDI amb notes a cada beat;
- el mapa de tempo;
- una guia curta per importar-ho en ordre.

Si el DAW arredonix, el clic i la nota MIDI es veuran separats a l'inici i,
sobretot, al final. L'usuari pot triar el perfil sense analitzar res.

No el faria imprescindible a la primera versió; sí que exportaria sempre el
clic i l'avís calculat.

#### Taula de compatibilitat

La taula és útil com a **document viu**, no com a promesa:

- REAPER i Ardour: primeres files, verificació local.
- Ableton, Cubase, Logic: **no verificats** fins que algú execute la prova.
- Verificar REAPER/Ardour valida el **generador**, no l'ecosistema.

La taula no s'ha de convertir en una llista de “suport oficial” sense proves.

#### Primera versió

La primera versió hauria de fer:

- exportar **sempre** MIDI + clic en àudio + manifest;
- calcular l'avís de pèrdua per cançó;
- deixar els perfils de capacitat i el joc de prova per a una segona fase;
- no afirmar compatibilitat amb DAWs no verificats.

---

## 4. Proposta principal: ancoratge + regressió de tempo constant

### 4.1. Flux

1. **L'usuari marca referències aproximades** de l'inici i del final del cos
   principal (clic, A–B curta o posició del cursor).
2. **Finestres d'onsets**: la app analitza només ±0,35–0,50 s al voltant de
   cada referència, no tota la cançó.
3. **Candidats d'inici i final**: tria els onsets/beats més pròxims, o ensenya
   1–3 candidats amb energia i distància. L'usuari confirma els dos.
4. **BPM inicial**: el motor intern proposa el tempo global; QM pot aportar
   una segona opinió.
5. **Tram estable**: s'analitza des de l'inici confirmat fins al final
   confirmat. La cua posterior al final queda com a provisional i no contamina
   la decisió d'estabilitat.
6. **Regressió**: s'ajusten `P` i la fase `t0` sobre molts onsets, no sobre un
   sol clic: `t_i ≈ t0 + i · P`, amb `P = 60 / BPM`.
7. **Validació**: es calcula `e(t)` sobre punts no usats; es miren `e_max`,
   `e_final` i el perfil. Si supera el llindar, no s'aplica sense revisió.
8. **Mapa**: es calcula el gap entre `t_onset` i la graella; si és petit,
   s'ancora el compàs 1 a `t_grid`; si és gran, es mostra i decideix l'usuari.
   Es crea el clip inicial `0 → compàs 1` segons la seua decisió.
9. **Canvis de compàs i cua final**: l'usuari marca les fronteres interiors;
   la app recalcula `N` i valida cada tram. L'últim clip pot quedar amb `N`
   fraccionari com a cua provisional.

### 4.2. Per què regressió i no un detector més?

Un detector de beats dona temps individuals amb jitter. Una regressió sobre
**molts** onsets reparteix eixe jitter i estima el període amb molta més
precisió. És la manera natural d'obtindre un BPM que no derive al final.

Opcions d'implementació:

- mínims quadrats robustos;
- RANSAC;
- Theil–Sen;
- mediana de diferències entre onsets allunyats;
- ajust per fases successives, descartant outliers.

No cal decidir-ho ara; el prototip ha de comparar-les amb el corpus.

### 4.3. Per què no usar QM com a veritat

- En Foo Fighters, QM dona **120.245 BPM** en una cançó de 144.69.
- El seu downbeat pot caure en 1.253 o 2.913 tot i que l'inici musical és
  1.650.
- En Bee/Police, QM dona BPM un 1–2 % alt.
- QM continua sent útil per a:
  - inicialitzar la cerca;
  - contrastar la fase;
  - detectar compassos en passatges on funciona;
  - avisar quan el resultat no és coherent.

### 4.4. Per què no usar el motor intern per a l'inici

- Bee: `offset` 0.680 (error +309 ms).
- Police: `offset` 0.190 (error −499 ms).
- Foo: `offset` 7.930 (error +6.28 s).

El motor intern és bo per al **BPM global**, no per a la frontera d'inici en
intros amb silenci, pickup o poca energia.

### 4.5. Horitzó de coherència

És el mètode proposat per detectar la cua i decidir on acaba el tram estable:

1. Es comença amb l'ajust des de l'inici confirmat.
2. Els onsets no usats són **intercalats** (validació creuada), no només els
   posteriors al prefix; així l'error d'estimar `P` no es confon amb un canvi
   real.
3. Es fa créixer el tram i es mesura `e(t)` sobre eixos onsets no usats.
4. No n'hi ha prou amb un sol beat atípic: cal una **desviació sostinguda de
   4–8 beats seguits**.
5. Eixe punt es proposa com a `final_analisi`, però és una **cota superior**,
   no necessàriament la frontera exacta: després d'un canvi de tempo l'ajust
   pot adaptar-se a les dades posteriors abans de superar el pressupost.
6. Un test local de canvi de mitjana del residu, o l'usuari, pot refinar la
   frontera.

No cal inferir el compàs. L'horitzó és una propietat del tempo; el compàs només
s'usa després per calcular `N` i validar les fronteres.

És especialment útil per al final de Foo Fighters: la coherència del tempo
principal hauria de caure prop de 206.5 s, on comença el half-time.

### 4.6. Dos ancoratges

Alternativa directa a la regressió sobre tots els onsets:

1. L'usuari confirma dos onsets/downbeats allunyats, **del mateix tipus
   d'esdeveniment** (bombo amb bombo, no bombo amb caixa).
2. L'app estima el nombre enter de beats `n` a partir del BPM aproximat:
   `P = Δt / n`.
3. Un beat de més o de menys sobre ~480 mou `P` un 0,2 % i el residu ho
   detecta; per això els onsets intermedis són la validació.
4. Si el residu és acceptable, el BPM queda determinat amb molta precisió.

No cal que l'app endevine el compàs ni la pols. L'usuari tria els dos punts i
el compàs; l'app calcula i valida. És una bona segona proposta per a la Guia
ràpida, sobretot quan hi ha pocs onsets fiables o el tram és curt.

Els dos ancoratges no eliminen la política del gap: el primer ancoratge encara
s'ha de comparar amb la graella ajustada.

---

## 5. Onsets: com usar-los sense trencar la precisió

### 5.1. Finestra guiada

Els onsets globals no són fiables per a l'inici. La proposta és:

- l'usuari dona una referència aproximada;
- la detecció es limita a una finestra curta;
- es mostra el candidat i el context;
- l'usuari pot sentir i ajustar.

La prova feta amb una finestra de ±0,35 s centrada en les etiquetes del corpus
dona coincidència exacta, però **no val com a validació**: la finestra contenia
la resposta. Cal repetir amb clics simulats i desplaçats.

### 5.2. Refinament d'atac

Hi ha dos instants diferents:

- **pic de l'ODF** (resolució de 10 ms);
- **inici de l'atac** a resolució de mostra.

Els mapes del corpus **són compatibles** amb el pic de l'ODF sense refinament,
però no proven que siga la convenció correcta: podrien haver-se creat amb la
mateixa eina. Amb `refina=True`, l'inici es mou 0,5–8 ms; en Police arriba a
−7,9 ms. Per tant:

- la convenció d'atac ha de ser única i declarada;
- per a un tall visual: ensenyar tots dos i deixar triar;
- mai canviar la frontera sense que l'usuari veja l'efecte.

### 5.3. Regla pràctica

1. Clic aproximat.
2. Onsets dins la finestra.
3. Triar el més pròxim o el primer amb energia suficient.
4. Confirmar.
5. No rebutjar el candidat pel fet de caure lluny del clic: el clic és
   aproximat. Mostrar el gap i les alternatives si és significatiu.

---

## 6. Clip inicial, pickup i silenci

Els primers clips del corpus no són tots iguals:

- **Stayin' Alive:** 0.3715 s a 1/4 i 161.5 BPM.
- **Every Breath:** 0.1778 s a 1/16 i 84.379 BPM, més 0.5113 s a 1/4 i
  117.35 BPM.
- **Times Like These:** 1.6503 s a 4/4 i 145.43 BPM.

No hi ha una regla automàtica única. La proposta:

- la app crea el clip `0 → compàs 1` **només després** que l'usuari confirme
  l'inici;
- l'usuari tria **silenci, pickup o anacrusi**;
- l'usuari tria el compàs i, si cal, el nombre de compassos;
- la app proposa una opció per defecte, però no l'aplica sense confirmar;
- el clip principal comença exactament al compàs 1 confirmat.

---

## 7. Compàs, fronteres i `N`

### 7.1. Compàs

No inferir automàticament la seqüència de compassos en esta fase. El motor
actual treballa amb un `num/den` fix; els 7/4 de Foo Fighters són un cas clar
de canvi que l'usuari ha de confirmar.

Proposta:

- l'usuari marca els trams de compàs;
- la app mostra les línies de compàs i el metrònom;
- el canvi de compàs no canvia el BPM;
- el `N` es recalcula a partir de la frontera i del compàs.

### 7.2. `N`

`N` no s'ha de detectar com un valor independent:

```
N = durada · BPM / (bar_quarters · 60)
bar_quarters = num · 4 / den
```

Per exemple, en 4/4 `bar_quarters = 4`; en 7/4, `bar_quarters = 7`; en 1/4,
`bar_quarters = 1`.

`N` només és enter si frontera, BPM i compàs són consistents. Si les fronteres
cauen a la graella ajustada, és enter per construcció dins d'un tram constant.
Si no, cal decidir què cedeix: BPM, frontera o rebuig; no es canvien dos valors
en silenci. En canvis de tempo o compàs, dos ajustos consecutius han de
compartir el punt de frontera. Només l'últim clip pot quedar fraccionari, i el
model ho ha de validar.

### 7.3. Tram final

A Foo Fighters, el tram `206.502 → 231.667` és **67.5 BPM** (half-time). No és
una deriva del BPM principal: és un canvi real de tempo. La proposta:

- l'usuari marca la frontera;
- la app proposa un BPM local;
- el tram es valida per separat;
- el BPM global no s'ha d'aplicar al tram final.

---

## 8. Validació i errors

### 8.1. Mètriques

Per a cada cançó:

- `e(t)` contra punts **no usats** en l'ajust;
- `e_max`, `e_final` i perfil (constant, pendent, estructura);
- error d'inici del clip principal;
- error de BPM;
- error de fronteres;
- error de `N`;
- nombre de compassos coberts;
- resultat del metrònom en els primers i últims compassos;
- incertesa de la referència, declarada a part.

### 8.2. Criteri d'acceptació

- Inici: ≤20 ms (ideal ≤10 ms).
- Fronteres interiors: ≤20 ms, amb snap.
- BPM: mana `e_max`/`e_final` ≤20 ms; si no, no aplicar automàticament.
- No es fixa un llindar universal de 0,01 BPM: en temes llargs pot incomplir
  els 20 ms. Si el fit és estable però `e_final` supera 20 ms, queda en
  reserva o no estable.
- Si es conserven “inici 20 ms” i “deriva 20 ms”, el pitjor absolut pot ser
  40 ms: cal declarar-ho.
- La incertesa de la referència no es pot ignorar; si és comparable a la
  tolerància, la validació no és concloent.
- Canvis de compàs: sempre confirmats.
- Cap aplicació destructiva sense previsualització.

### 8.3. Fail closed

Si el detector no pot garantir el criteri:

- no inventar una frontera;
- no arredonir el BPM perquè quadre;
- ensenyar el candidat i el residu;
- demanar confirmació o ajust manual.

---

## 9. UX proposada

**Punt d'entrada únic:** el botó **Guia ràpida**.

1. **Obre l'àudio** si encara no n'hi ha.
2. **Prem Guia ràpida.**
3. **Marca aproximadament l'inici i el final del tram principal.** La app
   proposa onsets/beats per als dos; opcionalment pots usar el loop A–B per a
   una prova.
4. La guia proposa onsets, BPM/pols, estabilitat i un mapa.
5. Confirma **compàs 1**, compàs, pickup i candidat de BPM.
6. La guia ajusta el BPM amb regressió sobre el tram estable.
7. **Previsualitza** la graella sencera i `e(t)` (màxim i final).
8. **Escolta el metrònom a inici, meitat i final del tram estable proposat**
   amb el BPM ja ajustat; no al final de la WAV si la cua és provisional.
9. L'usuari marca canvis de compàs i ajusta el final o la cua si cal.
10. La guia calcula `N` i valida.
11. Només aleshores s'aplica el mapa.

La interfície ha de mostrar sempre:

- inici triat;
- BPM i confiança;
- `e(t)` (màxim i final);
- nombre de beats utilitzats;
- si s'ha descartat algun onset;
- quines parts són automàtiques i quines confirmades.

---

## 10. Pla d'implementació recomanat

### Fase 0 — Laboratori d'avaluació

- Fixar la **convenció d'atac única** (`t_onset`, refinament i offsets).
- Llegir el corpus sense modificar-lo.
- Convertir els mapes a referència interna.
- Anotar **8–10 downbeats per cançó a nivell de mostra**, independents del
  detector, o declarar la incertesa de la referència.
- Simular clics a **±50, ±150 i ±300 ms**, i clics que caiguen al beat anterior.
- Mesurar el **jitter del metrònom/playback** abans de fer servir l'audició com
  a criteri de validació.
- Calcular error d'inici, BPM, deriva, gap i fronteres amb punts no usats.
- Guardar resultats fora del corpus.

#### Protocol d'anotació independent

**Eines:** Audacity o Sonic Visualiser (instal·lades); **no** usar AUTO CHORDS
ni el seu ODF per a la referència.

1. Treballar sobre la WAV original, sense normalitzar, sense warp i sense
   resamplejar. El corpus no es modifica.
2. Triar **8–10 downbeats forts** repartits per la cançó. Les línies del mapa
   només serveixen per navegar; cal amagar-les o desactivar el snap en el moment
   de marcar. No s'han de veure mentre s'ajusta el temps, per evitar biaix
   d'ancoratge.
3. Zoom a nivell de mostra. Marcar el **primer sample de l'atac**, no el pic.
   Criteri numèric revisat: base de 20 ms = la finestra més silenciosa dins
   dels 100 ms previs al clic; llindar **3 × RMS de la base**; cal que `|x|`
   el supere durant
   **≥1 ms** (44 samples a 44,1 kHz, 48 a 48 kHz). La cerca va de
   `t_aprox − 10 ms` a `t_aprox + 80 ms`; un esdeveniment anterior no és
   l'atac objectiu. El `5 % del pic local` queda només com a diagnòstic.
   Per a bombo/baix, es pot usar una versió filtrada, però el filtre i el
   llindar han de quedar documentats.
4. Anotar cada downbeat amb `sample_index` i `t_seconds` calculat amb el sample
   rate original. Evitar arrodoniments a centèsimes.
5. Repetir l'anotació en una segona passada, o amb un segon anotador, i
   comparar. Usar la mediana i calcular la dispersió (MAD). Si anota la mateixa
   persona que va construir els mapes, ha de fer-ho **sense veure el mapa ni
   l'app**; idealment, un segon anotador independent.
6. Si la dispersió és comparable a la tolerància que volem mesurar, la
   referència no és prou forta: resoldre els punts dubtosos o declarar la
   incertesa.
7. Guardar fora del corpus:

```json
{
  "cançó": "...",
  "wav": "...",
  "sample_rate": 44100,
  "anotador": "...",
  "eina": "Audacity x.y",
  "criteri_atac": "3x RMS base 20ms; sostingut >=1ms",
  "filtre": "cap (banda completa)",
  "snr_db": null,
  "rise_ms": null,
  "passada": 1,
  "downbeats": [{"sample": 123456, "t_s": 2.799455782}]
}
```

La referència ha de ser **independent de l'app** i ha de permetre calcular
l'error sense circularitat.

#### Banc sintètic d'atacs (Fase 0.A)

El generador ha de respondre **dos preguntes separades**:

1. **El detector implementa la seua pròpia definició?**
   - Referència analítica: inici físic, creuament del 10 %, creuament del 50 %
     i pic.
   - L'error es mesura contra el **10 %**.
   - Criteri: `<1 ms` en el cas net. Si falla, és un defecte de codi.
2. **La definició coincideix amb el criteri humà?**
   - La diferència respecte de l'inici físic és el `biaix_atac`.
   - En senyals sintètics es pot calcular com a funció de `rise_ms`, SNR i
     filtre.
   - Serveix per predir el biaix humà i detectar anotacions desviades.

Anotador virtual:

- implementar el criteri humà: **3 × RMS de la finestra de 20 ms més
  silenciosa dels 100 ms previs**, sostingut **≥1 ms**, finestra
  `t_aprox − 10 ms` a `t_aprox + 80 ms`;
- aplicar-lo als mateixos atacs sintètics;
- comparar `detector − anotador virtual`; quan arriben humans, comparar
  `humà − virtual`, no només `humà − detector`.

Casos mínims, a més del clic net:

- fons de soroll, baix sostingut, pad i esdeveniment anterior que decau;
- atacs lineals, exponencials i de cosinus;
- filtres: banda completa, passabaix i passaalt;
- fase aleatòria dins del bloc de 10 ms;
- 44,1 i 48 kHz;
- 24 bits i `float32` (el lector actual només entén 16 bits: ha de fallar de
  manera sorollosa, no silenciosa);
- estèreo amb canals en oposició de fase.

Cada cas s'ha de desar amb una llavor i un JSON de paràmetres perquè siga
reproduïble.

#### Peça sintètica (Fase 0.B)

Després de validar l'atac, el mateix generador pot crear una peça amb mapa
conegut:

- tempo constant;
- deriva petita;
- ritardando;
- microtiming de σ ms;
- beats que falten;
- 4/4 → 7/4;
- tram final a mig temps.

Servix per provar regressió, `e(t)`, horitzó i política del gap amb veritat
exacta. No substitueix la música real.

#### Especificació congelada del banc (Fase 0.C)

No es crea un `.md` nou: esta secció és la congelació dins del document.

**Congelació:** l'operador fixa data, commit i hash del JSON de paràmetres del
banc abans de la primera execució.

- Els **criteris i paràmetres del banc** queden congelats en una versió (`v1`).
- Una correcció del banc (per exemple, una referència mal calculada) crea una
  **versió nova** (`v1.1`) amb hash nou i obliga a tornar a executar les dos
  línies base.
- No es pot modificar el banc després de vore resultats de validació per fer-los
  passar; si cal, es documenta el canvi i es repeteix la validació.
- Les **constants del detector** es poden canviar durant el desenvolupament,
  però no després de començar la validació; si canvien, cal un conjunt nou de
  llavors de validació.

El banc l'executa **l'operador**; el generador es pot construir abans, sense
executar-lo contra cap detector fins que la versió estiga congelada.

**Dos punts d'entrada:**

| Funció | Contracte |
|---|---|
| `detecta_onsets(inici, fi)` | Llig context 30–50 ms abans d'`inici`, però retorna només temps refinats dins `[inici, fi)`; cap onset fora del rang |
| `onsets_ab(wav, A, B, marge=0.03)` | Funció pura sense Qt; aplica el contracte A–B de la taula |

La UI només crida `onsets_ab`; el banc pot provar les dos funcions per separat.

**Contracte A–B:**

| Posició d'A respecte del **10 % de l'atac objectiu** | Resultat |
|---|---|
| Abans o al 10 % | Trobat, a <1 ms del 10 % |
| Fins a 30 ms dins | Trobat, encara que la línia caiga fora de `[A,B)` |
| Més de 30 ms dins | No es retorna **l'atac objectiu** |

El marge es mesura sobre el temps refinat (10 %), no sobre l'inici físic.
No és una prohibició global: si dins `[A,B)` hi ha un altre atac legítim, s'ha
de retornar. El límit de 30 ms només aplica a l'atac objecte de la prova de
frontera.

`_fusiona_beats_rang`:

- dins `[A,B)`, substitueix com ara;
- dins del marge, un onset nou només substitueix un beat antic a **±15 ms**
  (mateix esdeveniment); la resta es conserva;
- no s'esborren beats llunyans pel simple fet de caure dins del marge.

El marge és paràmetre d'anàlisi, no d'exportació: es guarda amb la configuració
del detector i del banc, no al manifest d'exportació.

**Referències:**

- calculades sobre el senyal net sobremostrejat ×16, amb càlcul independent del
  detector;
- inici físic, creuament del 10 %, creuament del 50 % i pic;
- l'acceptació es mesura contra el **10 %**; el biaix respecte de l'inici físic
  és informatiu;
- el 10 % és una convenció del detector, no una veritat musical universal:
  en atacs lents la diferència pot superar 20 ms i s'ha de reportar.

**Conjunts i repeticions:**

- desenvolupament: llavors 1–999;
- validació: llavors 10000+;
- **calibratge de música real** per a la prominència mínima: passatges suaus
  anotats, en cançons o talls diferents del conjunt de validació;
- ≥30 repeticions per condició;
- N, mediana, p95, màxim, biaix amb signe, % fallback i % esdeveniment
  equivocat (|error| >20 ms).

L'atac s'ha de generar a una **posició fraccionària de mostra**, no sempre en
una mostra entera. La fase dins del bloc de 10 ms també ha de ser fraccionària.

**Grups de casos:**

| Grup | Casos |
|---|---|
| A | Bombo net, caixa, acord, baix suau |
| B | Soroll blanc/rosa a 60/40/30/20/12 dB |
| C | Baix sostingut, pad, esdeveniment anterior |
| D | Banda completa, passabaix, passaalt, passabanda |
| E | A a −80/−20/0/+15/+25/+40 ms |
| F | PCM16/24/float32, 44,1/48 kHz, mono/estèreo/fase oposada |
| G | DC, clipping, fade-in |
| N | **Controls negatius:** soroll, to sostingut, decaïment, silenci → **0 onsets** |

**Criteris inicials proposats (a congelar):**

- A net: p95 ≤1 ms; màxim ≤2 ms; 0 % fallback.
- A4 baix suau: p95 ≤2 ms per a pujades de 30/60 ms. La pujada de **120 ms**
  queda com a **informatiu/límit conegut**: la referència del 10 % es calcula
  amb una finestra de 80 ms i el pic queda tallat per la finestra. No s'ha de
  presentar com a precisió del detector.
- B ≥30 dB: p95 ≤2 ms; 20 dB: p95 ≤4 ms i fallback ≤5 %; 12 dB informatiu.
- C: p95 ≤3 ms; 0 % retorna l'esdeveniment anterior.
- D: p95 ≤2 ms contra la referència de la banda.
- E: taula A–B.
- F1a — detector directe: PCM24/float32 han de donar **error explícit**, no
  lectura de brossa.
- F1b — camí de conversió de l'app: precisió de la conversió a PCM16, prova
  separada de F1a.
- F3 — estèreo en oposició: defecte reproduït i corregit, no limitació
  acceptada.
- N: **0 onsets** en tots els controls negatius.
- Calibratge de la prominència amb música real:
  - mínim **30 atacs suaus anotats** en passatges reals;
  - **retenció ≥95 %** dels atacs anotats (emparellament a ±20 ms);
  - **0 onsets** al grup N;
  - si no existix cap llindar que complisca les dos condicions, no se'n tria
    cap: es declara el bloc com a no resolt.
  - La retenció del 95 % és una decisió de producte; si es vol un marge més
    exigent, s'ha de canviar **abans** de calibrar.

Com ajudar en el calibratge sense treball tècnic:

1. Triar **5–10 talls reals** de 10–20 s amb atacs suaus (raspats, plats,
   guitarres, pads, veus).
2. Autoritzar-ne la lectura sense modificar-los.
3. Marcar o confirmar **uns 30 atacs** amb Audacity o Sonic Visualiser.
4. No usar eixos talls per a validació: el calibratge i la validació han de
   ser conjunts diferents.

Amb això es pot fixar la prominència mínima; no cal que l'operador toque codi.

**Ordre d'execució:**

1. Congelar decisions i llindars.
2. Construir el banc.
3. Executar sobre el codi **actual** (marge dins del detector) amb
   `refina=False` i `refina=True`, i desar les dos línies base.
4. Separar `detecta_onsets` i `onsets_ab`; corregir rebuig de format, downmix
   sense cancel·lació i prominència mínima.
5. Tornar a executar desenvolupament.
6. Executar validació sense retocar res amb els resultats a la vista.

### Fase 1 — Ancoratge d'inici i final guiat

- Finestra d'onsets al voltant dels dos clics.
- Candidats i confirmació per a inici i final.
- Política del gap i elecció entre graella ajustada i ancoratge.
- Creació del clip inicial `0 → compàs 1`.
- Integrar-ho dins del botó **Guia ràpida**.

### Fase 2 — BPM constant per regressió i classificador d'estabilitat

- Detectar onsets/ODF crus del tram estable; no usar `segueix_beats` com a
  font d'estabilitat.
- Provar mínims quadrats, RANSAC i Theil–Sen.
- Estimar `t0` i `P` conjuntament.
- Validar `e(t)` amb punts no usats; reportar `e_max` i `e_final`.
- Implementar el classificador `ESTABLE` / `ESTABLE AMB RESERVA` /
  `NO ESTABLE` amb les mètriques de la secció 3.3.
- Calibrar els llindars amb el corpus i amb casos inestables.
- Retornar **propostes**, no una decisió única.

### Fase 3 — Compàs i fronteres

- Marcatge de canvis de compàs.
- Snap i recalcul de `N`.
- Validació per trams.

### Fase 4 — Final i casos especials

- Half-time final.
- Pickups llargs.
- Intros amb silenci o poca energia.
- Rúbrica d'avisos i fallback manual.

### Fase 5 — Integració GUI

- Convertir `DialegGuiaRapida` en l'assistent únic.
- Previsualització de metrònom.
- Residus visibles.
- Undo/redo.
- Desar el mapa només després de validar.
- Reutilitzar `_obre_guia_rapida`, `Feina` i els diàlegs existents.

---

## 11. Riscos i decisions pendents

- **Onsets en música amb molta percussió:** poden sobrar candidats; caldrà
  triar el més pròxim i descartar syncopacions.
- **Onsets en música lenta o legato:** poden faltar; caldrà un llindar
  adaptatiu.
- **Intros fluixos:** l'onset global falla; la finestra guiada és obligatòria.
- **Compàs:** no hi ha detector de seqüència de compassos; no inventar-lo.
- **Tram final:** no confondre half-time amb deriva del BPM.
- **Regressió:** si el tram té rubato, no aplicar-hi un BPM constant; caldrà
  detectar-ho o demanar a l'usuari.
- **Precisió:** 20 ms al final continua exigent; el prototip ha de mesurar-ho
  amb el corpus abans de prometre-ho.
- **No tocar el corpus:** les proves són de només lectura.

---

## 12. Fitxers i eines existents a tindre en compte

- `app/tempo.py` — onsets, BPM intern, `beats_a_trams`,
  `mapa_tempo_automatic`.
- `app/beats.py` — QM i motor intern, beats/downbeats.
- `app/pipeline_vamp.py` — QM, `detecta_compas1`.
- `app/analisi_ui.py` — F7, Beats A–B, Onsets A–B, aplicació de BPM.
- `app/visor_tempo.py` — edició del mapa i recalcul.
- `app/tempo_recalc.py` — `N`, BPM, compàs i recalcul.
- `app/mapa_tempo.py` — model i validació de `mapa_tempo.csv`.
- `eines/avalua_tempo.py` — avaluació existent; punt de partida per a les
  mètriques.
- `tests/test_avalua_tempo.py` — contracte de l'avaluador.

---

## 13. Conclusió

La proposta robusta no és triar un detector i confiar-hi. És separar el
problema:

1. **Onset guiat** per a l'inici i el final, amb tolerància de 20 ms.
2. **Regressió de tempo constant** per al BPM, per evitar deriva al final.
3. **Classificador d'estabilitat** `ESTABLE` / `ESTABLE AMB RESERVA` /
   `NO ESTABLE`, per decidir si el mapa pot ser d'un sol BPM.
4. **QM i motor intern** com a inicialitzadors i controls.
5. **Usuari** per al compàs, pickup, fronteres i tram final.
6. **Validació de `e(t)`** abans d'aplicar el mapa.

Així la app pot aspirar a un mapa que quadre amb el metrònom i la graella de
punta a punta, sense acceptar una deriva silenciosa que el músic acabarà
detectant.
