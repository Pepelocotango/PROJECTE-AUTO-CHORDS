# Anàlisi guiat v3 (ancoratges) — EN STAND BY

> **21-10-2026:** el flux v3 queda **en stand by** (codi conservat, sense
> entrada d'UI). La feina diària es fa amb **marcadors en viu**
> (`docs/MARCADORS.md`): `+` mentre sona → inici de clip de BPM/compàs i
> d'estructura, i després el marcador és independent. El motiu: el
> diàleg era modal i no deixava moure el cursor del visor.

---

# Anàlisi guiat v3 — ancoratges humans

> **Estat: ESPECIFICACIÓ PER REVISAR — no implementat.**
> Data: 2026-10-20 · Autor: OC · Substitueix el flux de §4 de
> [`ANALISI_GUIAT.md`](ANALISI_GUIAT.md) (v2: downbeat → finestres → confirmació
> per tram). Decisió de l'operador: **substituir**, no conviure.
> Este document és la font de veritat del flux nou: si el codi i el document
> discrepen, mana el document (i s'arregla el codi o s'actualitza el document,
> però mai en silenci).

## 0. Resum en cinc línies

1. L'usuari **declara** els punts on passa alguna cosa (fletxa avall) mentre
   escolta la cançó; cada punt és **inici de compàs i inici de secció** alhora.
2. Els punts es diuen **ancoratges** i són **intocables**: la graella hi passa
   exactament per damunt, amb desviació zero.
3. Entre dos ancoratges, la detecció automàtica només decidix **un nombre enter
   de compassos**; el BPM **es deriva** de Δt i d'eixe nombre (no s'estima).
4. Tot es pot **desfer i esborrar pas a pas** dins del diàleg, i l'interval on
   algo no quadra es marca **sospitós** abans d'aplicar res.
5. S'aplica a **temps** i **estructura** alhora, amb **un sol desfer** a la
   finestra gran.

## 1. El problema (per què v3)

La v2 va millorar molt el tempo global (Otis «Dock of the Bay»: 103,4 al tema
sencer, 104,6 al loop) però l'operador continua veient errors **locals** i de
**downbeat**: 51,70 en compte de 103,40, el compàs 1 desplaçat, compassos que no
cauen a lloc. La conclusió tècnica:

- El **downbeat no és una propietat acústica**: és mètrica (harmonia, baix,
  patrons de caixa, frases). El DSP clàssic (onsets + programació dinàmica +
  autocorrelació) detecta *pulsacions*, no *compassos*. Per això hi ha errors
  que no s'arreglen afinant el detector.
- L'alternativa neuronal (madmom, BeatNet, All-in-One, beat_this) no és viable
  ací com a dependència (els models moderns demanen AVX → SIGILL al Q9400) i,
  fins i tot corrent, seria una caixa negra.
- **La informació que falta la té l'operador.** El flux v3 la recull en 2 minuts
  d'escolta i la convertix en restriccions exactes.

La inversió és esta: el motor ja no decidix **on** és el compàs; només decidix
**quants n'hi caben** entre dos punts que l'usuari ha afirmat.

## 2. Decisions tancades (operador)

| # | Decisió | Valor |
|---|---------|-------|
| D1 | Conviure o substituir | **Substituir** el flux v2 com a entrada principal |
| D2 | Què significa un ancoratge | **Inici de compàs + inici de secció** (una tecla, dos resultats) |
| D3 | Correcció d'ancoratges | Es poden **esborrar de la llista** (no només l'últim), i desfer |
| D4 | Compàs / metre | **Es pot canviar al diàleg** (4/4, 3/4, 2/4, 5/4, 6/8, 7/8, 9/8, 12/8 i num/den lliures); s'aplica **a l'ancoratge següent** i es pot editar després |
| D5 | Velocitat de reproducció | ½ · ⅔ (÷1,5) · 1 · **1,5** · 2 · 4 — **sempre amb el to mantingut** |
| D6 | Latència de la targeta | **Selector de delay en ms** al diàleg, recordat |
| D7 | Errors de la passada | Es corregeixen **després, a mà** (no cal encertar-ho tot al vol) |
| D8 | Recompte de compassos | **No** es calcula a mà: el decidix la detecció **dins** de l'interval (només un enter) |
| D9 | Paper del diàleg per tram de v2 | Es queda com a **eina de reparació** d'un interval sospitós |
| D10 | Llindars de desviació | **Es decideixen al mateix diàleg** (no al codi) i es recorden |
| D11 | Zones inicial i final | **S'extrapola** el BPM de l'interval adjacent (no queden sense tempo) |

## 3. Vocabulari

- **Ancoratge**: instant `t` (temps real de la cançó) on l'usuari afirma que hi
  ha inici de compàs i de secció. Porta el metre vigent `(num, den)`.

- **Interval**: el tros de cançó entre **dos ancoratges consecutius**, o entre un
  ancoratge i un extrem de l'àudio. És la unitat de treball de tot el flux: no
  és encara res del model, és una mesura sobre els ancoratges.

  ```
  |---- pre ----|------ interval 1 ------|-- interval 2 --|--- post ---|
  0            a1                       a2               ak          final
  ```

  - **pre** = `[0, a1)` (només existeix si `a1 > 0`)
  - **interval i** = `[a_i, a_{i+1})`
  - **post** = `[a_k, final]` (només si `a_k < final`)

  Cada interval es convertix en **exactament un tram del mapa** (un sol BPM i un
  sol metre) i en **`n` clips de compàs** dins del tram. Per tant:

  > ancoratges → intervals → (un tram del mapa per interval) → (n clips de compàs
  > per interval) → (una secció d'estructura per interval)

  La diferència entre «interval» i «tram» és important: **interval** és el que
  decidixes tu (on passes alguna cosa); **tram** és el que eixirà al model
  (BPM + metre), i n'ix un per interval.

- **Encaix**: procés pel qual, per a un interval, es decidix `n` (compassos
  enters) i es deriva el BPM.
- **Sospitós**: interval on el BPM derivat no casa amb el detectat (o no n'hi ha
  cap de bo) → es marca per revisar, sense bloquejar.
- **Zona pre** i **zona post**: els dos intervals dels extrems (vegeu el dibuix).

## 4. Regles (normatives)

> Cada regla ha de tindre la seua verificació automàtica (tests) o la seua
> comprovació manual explícita al pla. Si no se'n pot verificar cap de les dues,
> no s'aprova.

**R1 · Ancoratge = compàs + secció.** Cada ancoratge crea una frontera a la
pista de **temps** i a la d'**estructura**. No hi ha mode «només secció».
*Verificació:* el mapa resultant té una línia de compàs a `t` i la pista
d'estructura té un tall a `t`.

**R2 · La graella passa exactament pels ancoratges.** Desviació **0** (tolerància
de coma flotant, 1e-6 s). L'encaix no suavitza, no promitja i no mou mai un
ancoratge. *Verificació:* test que compara cada `t_k` amb la línia de compàs
més pròxima.

**R3 · Dins d'un interval el metre és constant.** El que val és el metre de
**l'ancoratge d'inici** de l'interval. Un canvi de metre només pot ocórrer en un
ancoratge. *Verificació:* cap tram del mapa creua un canvi de metre si no és a
una frontera d'ancoratge.

**R4 · El BPM es deriva, no s'estima.** Per a un interval de durada `Δt` amb
`n` compassos de `num/den`:

```
durada_compas = num · (4/den) · 60 / bpm
Δt            = n · durada_compas
⇒  bpm = n · num · (4/den) · 60 / Δt
```

`bpm` és el valor **exacte** que fa quadrar la frontera. *Verificació:* test
`n · durada_compas(bpm, num, den) ≈ Δt` a 1e-9.

**R5 · `n` és un enter ≥ 1 i es tria, no es calcula.** Es busca en `1…N_MAX`
(per defecte **64**, configurable al diàleg) i només es consideren els valors
que deixen el BPM dins del rang configurat (`min`/`max` d'Opcions). S'escull el
que minimitza `|bpm(n) − b0| / b0`, amb `b0` = BPM detectat a l'interval; si hi
ha empat tècnic (diferència < 0,2 %), guanya el més pròxim al BPM de l'interval
anterior (continuïtat). *Verificació:* tests amb dades sintètiques on `n` és
inequívoc.

**R6 · Referències de `b0`, per ordre:** (1) detectat dins de l'interval;
(2) BPM de l'interval anterior; (3) referència global del tema
(`detecta_bpm_candidats` sobre tot l'àudio); (4) el `bpm` preferit d'Opcions.
Si no n'hi ha cap → l'interval queda **sense referència** i demana `n` a mà.
*Verificació:* test amb detecció forçada a `None`.

**R6-ter · Rang de BPM pels dos marcs (D13).** `bpm ≈ n_compassos ·
num · (4/den) · 60 / (t₂ − t₁)` amb `n_compassos` editable (1 per defecte). El
rang acceptat és `bpm ± 10 %` (`marge`, desat a les opcions) i **substituïx** el
rang absolut 60–180: els `n` que donarien el doble o la meitat queden fora. La
referència de la cadena (`b0`) passa a ser eixe BPM aproximat.

**R6-bis · El primer interval MANA (no es rebutja per la referència global).**
Si l'`b0` ve de la referència global (o del preferit) i no d'una detecció ni de
l'interval anterior, una desviació gran **no bloqueja**: l'interval passa a
`nota` amb el motiu («s'allunya un 16,3 % del de la barra (120); s'accepta com
a referència del tema»). El 120 de la barra sol ser el valor per defecte, no una
mesura. El bloqueig (`no_encaixa`) queda per als intervals que **sí** tenen
cadena i per als que no admeten cap `n` dins del rang.

**R7 · Llindars de desviació, configurables al diàleg.**
`desv = |bpm_deriv − b0| / b0`, amb tres valors que l'operador pot moure
**dins del mateix diàleg** (no al codi) i que es recorden:

| desv | Estat | Què fa |
|------|-------|--------|
| ≤ *llindar nota* (def. **1 %**) | **ok** | aplica sense dir res |
| *nota* … *sospitós* (def. **3 %**) | **nota** | aplica i ho anota al log (pot ser rubato) |
| *sospitós* … *no encaixa* (def. **10 %**) | **sospitós** | aplica i el marca a la llista de revisió |
| > *no encaixa* | **no encaixa** | **no tria `n` automàticament**: demana `n` a l'operador abans d'aplicar |

Els valors han de ser creixents (`nota < sospitós < no encaixa`); si no, el camp
es marca en roig i no es pot generar. Es desen a `opcions_detecta.json` →
`guiat.*`. *Verificació:* tests de cada banda amb els valors per defecte i amb
valors alternatius.

**R8 · Correcció d'octava per interval.** Cada interval sospitós es pot corregir
amb **×2 / ÷2** (i opcionalment ×3/÷3), que duplica o parteix `n` **sense tocar
mai els ancoratges**. És la resposta directa a l'error de meitat/doble tempo.
*Verificació:* test que ×2 duplica el nombre de clips de compàs i manté R2.

**R9 · Zones pre i post: extrapolació.** Si el primer ancoratge és > 0, la
graella **s'extrapola cap enrere** amb el BPM de l'interval 1 (mateix metre) fins
a 0. Si l'últim ancoratge és < final de l'àudio, s'**extrapola cap avant** amb el
BPM de l'últim interval. Si l'usuari punxa a 0 s i al final, no hi ha
extrapolació. La pre i la post **no es marquen sospitoses per desviació** (tenen
una sola frontera): només s'informa del BPM extrapolat.
*Verificació:* tests amb ancoratges a 5 s i a 170 s sobre un àudio de 180 s.

**R10 · Delay (latència) global.** `t_real = t_premsa − delay_ms/1000`,
acotat a `≥ 0`. Canviar el delay **recalcula tots** els ancoratges i l'encaix
sense demanar res més. Es desa a `opcions_detecta.json` → `guiat.delay_ms`.
*Verificació:* test que un delay de 100 ms desplaça tots els ancoratges −0,1 s.

**R11 · Velocitat amb to mantingut.** La reproducció a ½ · ⅔ (÷1,5) · 1 · 1,5 ·
2 · 4 es fa amb
una còpia estirada (`ffmpeg atempo`, caché temporal) i ``t_real = t_estirat ×
factor`` (factor = velocitat: a ½, 1 s de música ocupa 2 s de fitxer). Mai
`paplay --rate` (canviaria el to). Els ancoratges es guarden **sempre en temps
real**. *Verificació:* test de conversió; comprovació manual
que a ½ el to és el mateix.

**R12 · Anti-rebot de teclat.** Es descarta l'auto-repetició (`isAutoRepeat`) i
s'ignoren dos ancoratges a menys de **0,15 s** (en temps real) — es queda el
primer. *Verificació:* test de doble esdeveniment seguit.

**R13 · Desfer = pila d'operacions.** La pila guarda operacions
(`afegir`, `esborrar`, `metre`, `×2`, `÷2`), no estats: es pot desfer en ordre,
també l'esborrament d'un ancoratge del mig. En desfer un `afegir`, el cursor
torna **2 s abans** d'eixe punt i queda **en pausa**. *Verificació:* test de
seqüència afegir/afegir/esborrar/desfer/desfer.

**R14 · El metre triat s'aplica a l'ancoratge següent.** Canviar el combo
mentre sona no altera res del passat; la pròxima fletxa avall naix amb eixe
metre. Després, clicant un ancoratge, se li pot canviar el metre (operació de
pila). *Verificació:* test de canvi enmig de la passada.

**R15 · Res s'aplica al model sense validar.** Abans de tocar res:
`tempo_map.valida_i_normalitza_compassos(...)` i la validació de seccions
(`_valida_canvis_seccions`) han de passar. Si no, s'avisa i **no es toca el
model**. *Verificació:* test amb un mapa que incomplix el contracte.

**R16 · Un sol desfer a la finestra gran.** L'aplicació completa (mapa de tempo
+ clips de compàs derivats + seccions) és **una unitat** de desfer
(`_undo_marca` → aplicar → `_undo_commit`). *Verificació:* test que un `undo`
deixa el model exactament com abans.

**R17 · Ordre i contigüitat (regles #1 i #2 de l'app).** Les fronteres ixen
ordenades, sense solapaments i cobrint tota l'àudio (regla #4), per construcció;
es verifica igualment abans d'aplicar. *Verificació:* els validadors existents
de `pipeline`/`tempo_map`.

**R18 · Les durades són derivades (regla #3).** Cap durada s'escriu a mà: els
clips de compàs es generen des de la graella del mapa, no a l'inrevés.

**R19 · Privacitat i neteja.** Les còpies estirades viuen a `/tmp`
(`auto_chords_vel_*.wav`) i s'esborren en tancar el diàleg. Cap dada de la cançó
ix del disc local (no hi ha núvol en este flux).

**R20 · El diàleg no toca el fil d'àudio del visor.** Fa servir el seu propi
reproductor (com el de v2); en tancar, deixa el visor com estava (loop,
metrònom i cursor restaurats).

**R21 · Integració visual: el cursor del visor avança amb el só.** Encara que
l'àudio el porte el diàleg (R20), la posició de l'audició s'ha de veure a la
finestra principal: cada *tick* (i cada salt) es crida
`main._mou_cursor_guia(t)` → `Visor.ves_a(t)` + `ensure_cursor_visible()`, de
manera que **la línia del cursor, la regla de temps, la barra lliscant i la
vista** segueixen la música. L'audició **arrenca on hi ha el cursor** del visor
(no a 0). És el mínim per punxar a cegues sense mirar el diàleg.

## 5. Flux d'usuari

1. Menú *Analitza ▸ Anàlisi guiat* (o el botó de la barra).
2. S'obri el diàleg, que explica què fer (text de §6). **Primer de tot**:
   **① «Marca el compàs 1»** (posa el cursor del visor a l'inici del tema i
   prem; fixa l'offset i crea el primer ancoratge) i **② «Marca el compàs 2»**
   (o un compàs posterior; el camp «Compassos entre» diu quants n'hi ha). Amb
   els dos punts el motor ja sap el **BPM aproximat del tema** i fixa el
   **rang acceptat** (±10 %): si el tema va a ~104, cap solució a 208 o a 52
   no entra. Sense els dos marcs, «Genera» està bloquejat.
3. L'àudio comença a sonar **des d'on és el cursor del visor** i a la velocitat
   triada (per defecte ×1); mentrestant **el cursor del visor avança** amb el
   só (R21).
4. L'operador prem **+** cada cop que comença un compàs nou / canvia
   l'estructura. Pot canviar la **velocitat** i el **metre** sense parar.
5. Si s'equivoca: **↶ Desfés** (o Ctrl+Z); el cursor torna 2 s abans del punt
   desfet i queda en pausa; o clica l'ancoratge a la llista i l'esborra.
6. En acabar (o quan en tinga prou), **Genera i aplica**.
7. El diàleg encaixa tots els intervals i mostra el **resultat** (BPM,
   compassos, desviació) amb els **sospitosos** marcats; pots aplicar ja o
   corregir (`×2`/`÷2`, esborrar, tornar a punxar).
8. En aplicar: es tanca el diàleg, el model queda amb la graella nova i **un sol
   desfer**. Un avís no modal diu quants trams i quants sospitosos queden.

## 6. La finestra

```
┌─ Anàlisi guiat — ancoratges ──────────────────────────────────────────┐
│ Escolta la cançó i prem + cada vegada que comença un compàs nou o     │
│ canvia l'estructura. Cada + és inici de compàs I d'una secció nova.   │
│                                                                       │
│ [① Marca el compàs 1] [② Marca el compàs 2] entre [1] · BPM≈104 · 93,9–114,8 │
│  00:42.35 / 03:18.90      [▮▮ Pausa (Espai)]   Vel: [½][⅔][1][1,5][2][4] │
│  Compàs: [4/4 ▾]   Delay: [35] ms   Ancoratges: 12     [↶ Desfés]     │
│  Encaix: nota > [1] %  sospitós > [3] %  no encaixa > [10] %  N≤[64]  │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  #   temps      Δt     compàs  n   BPM     desv            accions │  │
│  │ 12   00:42.350  8.120  3/4     2   104.3   ok        [→][×][×2][÷2]│  │
│  │ 11   00:34.230 16.400  4/4     4   103.9   0,4 %     [→][×][×2][÷2]│  │
│  │ 10   00:17.830 17.830  4/4     8   104.1   1,8 %     [→][×][×2][÷2]│  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  [ Genera i aplica ]                                  [ Cancel·la ]   │
└───────────────────────────────────────────────────────────────────────┘
```

- `[→]` porta el cursor a eixe ancoratge (i pausa); `[×]` l'esborra.
- `[×2]`/`[÷2]` (nomes a les files amb interval) forcen el nombre de compassos
  eixe interval (`n_manual`) i recalculen.
- La llista es mostra del més recent al més antic, amb Δt respecte del previ.
- Després d'encaixar, cada fila afig **BPM**, **desviació** i, si cal,
  `[×2] [÷2]`.
- Els quatre camps de la línia **Encaix** són els de R7 i R5 (editables, es
  recorden; si `nota ≥ sospitós` o `sospitós ≥ no encaixa`, es posen en roig i
  no es pot generar).

**Tecles:** `+` afig ancoratge — val **el de dalt del teclat** (Maj+`=`) i **el del teclat numèric**, i funciona encara que el focus siga a un camp (és un atall de finestra, no un `keyPressEvent`); **les fletxes no fan res** (donaven problemes) · `Espai` play/pausa · `Ctrl+Z` desfés ·
`1…6` velocitats · `Esc` cancel·la (avisa si hi ha ancoratges).

## 7. Model de dades i opcions

```python
# ancoratge (en memòria, dins del diàleg)
{"t": 42.350, "num": 4, "den": 4}      # t = temps real de la cançó (segons)
```

Opcions persistides (`opcions_detecta.json`, secció `guiat`) — s'afig a les que
ja hi ha (les de v2 es conserven per al diàleg de reparació):

```json
"guiat": {
  "delay_ms": 35,
  "velocitat": 1.0,
  "compas": "4/4",
  "n_max": 64,
  "desv_nota": 0.01,
  "desv_sospitos": 0.03,
  "desv_no_encaixa": 0.10,
  "compassos": 8,          // llegat v2 (diàleg per tram)
  "confirma": true         // llegat v2
}
```

## 8. Algorisme d'encaix

```
entrada: ancoratges ordenats a1…ak (t, num, den), durada_audio, opcions
eixida:  trams [(t_ini, t_fi, bpm, num, den)] + informes per interval

1. Si k == 0: error controlat («punxa almenys un ancoratge»).
2. Per a cada interval (pre, 1…k-1, post):
     Δt = fi − ini
     metre = metre de l'ancoratge d'inici (per a la pre: el de a1)
     b0 = referència segons R6
     si b0 és None → estat = "sense_referencia"; n = None
     si no:
       per a n en 1…N_MAX:
         bpm_n = n · num · (4/den) · 60 / Δt
         si bpm_n dins [bpm_min, bpm_max]: candidats.append((desv, n, bpm_n))
       si no hi ha candidats → estat = "no_encaixa"; n = None
       si no → tria el mínim segons R5 → estat segons R7
3. Construeix els trams contigus amb les fronteres exactes dels ancoratges
   (pre i post inclosos, amb extrapolació per R9).
4. Valida amb tempo_map.valida_i_normalitza_compassos(...).
5. Retorna també: per a cada interval, {n, bpm, desv, estat}.
```

Notes d'implementació:

- Tot en `tempo_map` (o un mòdul nou `app/ancoratges.py` si `tempo_map` es fa
  gros), **sense PyQt**, per poder-ho testar pur.
- El càlcul de `b0` per interval pot fer-se en un fil (com `FilGuiaBpm`) quan
  l'interval és llarg; el diàleg no es bloqueja.
- La pre i la post no es marquen sospitoses per desviació (R9).

## 9. Casos límit

| Cas | Què fa |
|-----|--------|
| Cap ancoratge | No deixa generar; text explicatiu |
| Un sol ancoratge | Graella a partir d'ell amb el BPM global detectat; avisa que no hi ha segona frontera |
| Dos ancoratges a < 1 compàs | Error clar en eixe interval («no hi cap un compàs»); proposa esborrar-ne un |
| `Δt ≤ 0` | Impossibles per R12; si passa, error |
| Interval sense cap `n` vàlid al rang | `no_encaixa`; demana `n` a mà (selector amb el BPM resultant) |
| `n` ambigu (meitat/doble) | Es tria pel prior (R5/R6) i, si queda dubte, es marca sospitós; `×2`/`÷2` ho corregeix en un clic |
| Canvi de metre a l'ancoratge | Permès (R3/R14); la frontera és compartida i les línies de compàs canvien de durada allí |
| Ancoratge erroni (no era inici de compàs) | L'encaix dona desviació gran o cap `n`; es marca; s'esborra i es torna a punxar |
| Àudio sense pulsació (parlat, silenci) | `b0 = None` a tots els intervals → demana `n` o cancel·la |
| Tema molt llarg (30 min) | La llista virtualitza; l'encaix és O(k · N_MAX), trivial |

## 10. Aplicació al model

Ordre exacte (tot dins d'una sola unitat de desfer):

1. `_undo_marca()`.
2. **Tempo/mapa**: `visor.aplica_tempo_validat(trams, msg="Anàlisi guiat")`
   (ja fa la validació del contracte de compassos; si retorna `False`, s'avorta
   i es desfà la marca).
3. **Seccions**: crear un clip d'estructura per interval, amb nom provisional
   (`Secció 1…`) i el mateix ordre; validar amb `_valida_canvis_seccions`.
   Si falla, s'avorta l'aplicació sencera (no es deixa el mapa sense seccions).
4. `_undo_commit()` + refresc (`_sincronitza_temps_del_visor`, timeline).
5. Avís no modal: «N trams · M seccions · K sospitosos».

Paritat: l'operació viu a **una sola funció** de `main.py` (no duplicada per
carril) i es registra com una acció més si acaba apareixent al menú.

## 11. Compliment de les 12 regles de l'app

| Regla | Com es complix |
|-------|----------------|
| #1 ordre sense solapaments | Fronteres generades en ordre des dels ancoratges |
| #2 contigüitat | Trams contigus per construcció; s'eliminen micro-gaps |
| #3 durades derivades | Els clips de compàs es generen des de la graella del mapa |
| #4 cobertura total | Pre i post cobreixen 0…final de l'àudio |
| #5 backends font de veritat | `tempo_map` + `pipeline` decideixen; el diàleg només recull |
| #6 conversió d'unitats | Tot en segons; el compàs/temps ve del mapa |
| #7 desfer | Una unitat a la finestra gran; pila d'operacions al diàleg |
| #8 desar | Es desa com qualsevol canvi (mapa + seccions) |
| #9 validació | R15: res s'aplica sense validar |
| #10 logging | Cada encaix i cada avís al log de l'app |
| #11 paritat entre carrils | Una sola funció d'aplicació, sense branques per carril |
| #12 exportació | El mapa nou i les seccions entren a l'export com sempre |

## 12. Pla per fases

Cada fase acaba amb la suite verda i pyflakes net. No es passa a la següent
sense revisió de l'operador si la fase canvia comportament visible.

- **F1 · Motor d'encaix** · ✅ **FET** (`app/ancoratges.py`): `encaixa_ancoratges`
  i companyia, R4–R9, R15. Tests purs (`tests/test_ancoratges.py`, 52).
  *Acceptació:* donats ancoratges sintètics (4/4, 3/4, 5/4, 6/8, canvi de metre,
  pre/post, sense referència), l'encaix dona el `n` esperat, la desviació
  correcta i les fronteres exactes.
- **F2 · Velocitat amb to mantingut** · ✅ **FET** (`app/ffmpeg.py`):
  `prepara_escolta`/`estira_a_wav` + caché, ½ · ⅔ · 1 · 1,5 · 2 · 4 (R11, R19).
  *Acceptació:* factor ½ → `t_real = 2·t`; el fitxer temporal s'esborra en
  tancar; comprovació d'oïda que el to no canvia.
- **F3 · El diàleg** · ✅ **FET** (`app/dialeg_ancoratges.py`): transport amb
  velocitat (to mantingut, `t_real = t_estirat × factor`), `+` amb delay i metre,
  llista amb salt/esborrar/canvi de compàs, desfer amb pila (R13), llindars
  editables (R7), tecles (`+`, `Espai`, `Ctrl+Z`, `1…6`), temporals a la
  paperera en tancar (R19). Tests: `TestDialegAncoratges` (11).
- **F4 · Generar i aplicar** · ✅ **FET**: `Visor.aplica_ancoratges` valida
  (tempo + estructura) i aplica **offset + mapa + seccions en un sol desfer**;
  `main._aplica_ancoratges` crea l'estructura amb
  `ancoratges.seccions_de_ancoratges` (**un clip per interval + «Intro»**),
  desa l'offset al `.acproj` (sense això, en reobrir el projecte la graella
  tornava a compàs 1 = 0) i registra el resum.
  - **(a) Detecció per interval** · ✅ `main._detector_interval` +
    `DialegAncoratges._detecta_dolents`: només es detecta als intervals que la
    cadena no ha pogut encaixar, i el resultat només s'accepta si **millora**.
  - **(b) Seccions automàtiques** · ✅ `ancoratges.seccions_de_ancoratges`.
  - **(c) `×2`/`÷2`** · ✅ botons per fila (`n_manual`, R8); els ancoratges no
    es toquen. El salt al `DialegGuiaBpm` de v2 queda cobert pel menú
    *Analitza* (la v2 sencera hi és com a eina de reparació).
  - **(d) Resum** · ✅ al diàleg («N trams i seccions · M sospitosos») i al log
    (`guiat v3: …`). La finestra continua sent **modal** (D12).
- **F5 · Docs i polit** · ✅ `ANALISI_GUIAT.md` (v2 = llegat), `CHANGELOG`,
  `ESQUEMA_UI` + vistes, i **`docs/PLA_GUIAT_V3.md`** amb l'estat.

### D12 · La finestra és modal (decisió)
Fer-la no modal exigix que el transport del diàleg seguisca el cursor del visor
quan l'usuari clica la forma d'ona (o que el diàleg mane el cursor i bloquege
el clic). Mentre no es resolga eixa sincronia, es queda **modal**: el cursor i
la regla de temps sí que avancen (R21) i l'audició arranca on és el cursor.

## 13. Tests previstos

**Purs (F1/F2)**: 4/4 n conegut · 3/4 · 5/4 · 6/8 · canvi de metre a
l'ancoratge · desviació ok/nota/sospitós/no encaixa (amb llindars per defecte i
amb uns altres) · llindars incoherents rebutjats · sense referència · rang de
BPM que descarta `n` · dos ancoratges massa junts · pre i post · `×2`/`÷2` ·
conversió de velocitats i delay.

**GUI (F3)**: `+` afig · auto-repetició ignorada · dos ancoratges < 0,15 s ·
desfer afegir (cursor −2 s) · desfer esborrar · canvi de metre al següent ·
delay retroactiu · llindar canviat i recordat · espai play/pausa · cancel·lar
amb ancoratges avisa · neteja del temporal en tancar.

**Integració (F4)**: aplicar i validar · un sol desfer · sospitosos llistats ·
`×2` canvia el nombre de clips · obrir el diàleg per tram des d'un sospitós ·
«sense ancoratges» no aplica.

## 14. Què NO fa (fora d'abast)

- No detecta downbeats automàticament (això és el que estem substituint).
- No edita a nivell de temps dins del diàleg (això és per al visor, després).
- No fa canvis de metre a mig compàs.
- No fa rampes de tempo (accelerando) dins d'un interval.
- No toca l'exportació ni el format del projecte.
- No fa servir núvol ni cap servei extern.

## 15. Riscos i mitigacions

| Risc | Mitigació |
|------|-----------|
| Octava equivocada (103,4 vs 206,8) | Prior + rang de BPM + marca sospitós + `×2/÷2` en un clic |
| L'operador punxa a contratemps | Desviació gran → no encaixa → esborrar i repetir; el delay ajuda |
| Massa ancoratges (passada nerviosa) | Llista + esborrar; no passen dos en < 0,15 s |
| El diàleg es tanca i es perd la feina | Confirmació si hi ha ancoratges; els ancoratges no es desen al projecte (es tornen a fer en 2 min) |
| Latència diferent per eixida | Selector de delay; es pot recalcular sense repetir |
| `ffmpeg` lent en temes llargs | Caché per velocitat; es renderitza només el que es demana |

## 16. Punts oberts (per a la revisió de l'operador)

> Resolts el 21-10: **bloqueig** → el primer interval (o un sense cadena) mai
> no bloqueja per la referència global (R6-bis); el bloqueig queda per a
> incoherències dins la cadena o per a intervals que no admeten cap `n`.
> **Editar el mapa després** → eliminar/fusionar/duplicar imanten la frontera a
> la línia de compàs (`tempo_map.repara_fronteres`) en lloc de rebutjar
> (l'operació es quedava bloquejada per 1 ms).

Resolts: llindars configurables al diàleg (D10) · definició d'**interval** (§3) ·
pre i post s'extrapolen (D11).

1. **`N_MAX`** per defecte 64 (configurable): et va bé? Amb 64 cobreixes uns
   2–3 minuts de música entre marques a tempo normal.
2. **Interval «no encaixa»**: prefereixes que el diàleg **no et deixe generar**
   fins a arreglar-lo (el meu criteri), o que aplique la resta i el deixe
   marcat i pendent?
3. Vols un **clic de metrònom opcional** durant la passada (apagat per
   defecte) o millor res que et distraga?
4. Els **noms de secció** provisionals (`Secció 1…`) o prefereixes que quedin
   buits per a omplir-los després?
5. Després d'aplicar, el diàleg **es tanca** (el que propose) o es queda obert
   per seguir polint?
