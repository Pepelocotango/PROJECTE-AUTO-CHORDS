# Full de ruta — PROJECTE AUTO CHORDS

> Eina per a **músics multi-DAW**: analitza una cançó (WAV), en deixa **editar
> visualment** els acords i l'estructura, i n'exporta el resultat com a **clips
> WAV** llestos per arrossegar a qualsevol DAW. També es vol que permeta
> **edicions d'àudio bàsiques** sobre una còpia del projecte. Tot en català ·
> **GPL-3.0-or-later**.
>
> **v0.8.0** · Estat: **flux de producte estable i multi-SO** · Suite **verda**
> (1.563 tests locals, 1 omés) + `pyflakes` net. El recompte viu és al CI.
>
> 📌 Aquest fitxer és el full **viu**. L'històric (Fases A–E, anàlisi multi-SO,
> graella/PPQ, obertura tecnològica, brainstorms originals, notes…) és a
> **[`ROADMAP_HISTORIA.md`](ROADMAP_HISTORIA.md)**.

---

## 1. Visió i objectiu

**El problema**: passar els acords d'una cançó a un DAW sol demanar MIDI,
plugins o transcriure a mà.

**La solució** (raó de ser del projecte): **un fitxer WAV per acord/secció**,
**silenciós**, on:
- **Nom = acord** (`Am.wav`) → al DAW el clip es llegeix com l'acord.
- **Durada = durada de l'acord** → arrossegats, dibuixen la progressió sencera.
- **Zero plugins**: qualsevol DAW arrossega una carpeta d'àudio.
- **Doble pista**: `wavs_acords/` + `wavs_estructura/`, sincronitzables.

Els clips exportats no són àudio musical: són una **pista visual de noms i
durades**, deliberadament simple i per això compatible amb qualsevol DAW.
L'edició bàsica del fitxer d'àudio carregat és una funció complementària
parcialment implementada, amb un abast molt més limitat que un editor general.

**Cas d'ús oficial**: vegeu el **flux de l'usuari** a
[`AGENTS.md` §Abast i flux](AGENTS.md#-abast-i-flux-de-lusuari--font-única)
(obrir WAV → analitzar o treballar a mà → editar visualment → exportar →
arrossegar al DAW).

**Línia de producte complementària (implementada)**: la importació
ja desa una única còpia WAV de treball dins del projecte i els backups també la
inclouen; l'original es conserva. Les nanses permeten retallar o allargar amb
silenci els extrems i desfer/refer l'edició junt amb el model musical.
`Fitxer ▸ Exporta àudio…` desa el resultat en WAV, MP3, FLAC, AAC/M4A, OGG o
Opus. L'abast és a [`docs/REGLES_DE_LA_APP.md` §13.9](docs/REGLES_DE_LA_APP.md).

**Arquitectura oberta**: el **core** (pipeline + plugins Vamp) és **independent
de la GUI**; l'embolcall (avui **PyQt5**) es pot canviar. Restricció:
**Q9400 sense AVX** → verificar binari a binari abans de canviar de tecnologia.

---

## 2. Estat actual i relleu de sessió (2026-11-10)

> **Norma per a agents:** qualsevol agent que treballi en el codi ha
> d'**actualitzar aquesta secció** en plegar (reescriure-la, **no**
> incrementalment: reflectir l'estat actual, no l'historial). L'historial viu al
> [`CHANGELOG.md`](CHANGELOG.md). La definició de **què fa l'app i què queda
> fora** és a [`AGENTS.md`](AGENTS.md#-abast-i-flux-de-lusuari--font-única).

**Fases** del pla `00PER FER/PLA_SIMPLIFICACIO_TEMPO.md`: **0–7 fetes**. La **10**
(motor de detecció amb corpus real) està **oberta i bloquejada pel corpus
manual**; la **12** (congelació, higiene i CI) està **en curs**. La **8**
(export MIDI del mapa de tempo) queda **pendent (TODO)**; **9** (anàlisi
guiada) i **11** (flux del 90 %) queden **ajornades**.

> **Prioritat:** simplificar el producte. L'abast vigent és a
> [`AGENTS.md` §Abast i flux](AGENTS.md#-abast-i-flux-de-lusuari--font-única):
> només el nucli (obrir → analitzar opcional → editar 3 pistes → exportar →
> desar). La **fase 10** i el **rubato avançat** queden **ajornats sense data**.
> L'**export MIDI del mapa de tempo** (`mapa_tempo.mid`) queda **pendent
> (TODO)**, no prioritari, però amb l'abast i els criteris d'acceptació fixats
> davall.

**Fet (2026-11-06):**
- **Refactor complet**: `pipeline.py` queda en **89 línies** (façana) +
  `pipeline_*`; `main.py` **1.511** + `*_ui`/`feines`/`opcions`; `visor.py`
  **4.447** + `visor_*`; `timeline.py` **2.135** + `timeline_geometry`;
  `dialegs.py` **25** + `dialeg_*`. Tests de contracte a
  `test_pipeline_contracte` i `test_timeline_contracte`.
- **Guiat v2/v3 retirat**: codi d'ancoratges eliminat; el flux viu són els
  **marcadors en viu** (`+`) i la **Guia ràpida**.
- **Docs al mínim**: `AGENTS`/`DEVELOPING` escurçats; `Makefile`, generadors de
  la taula de mòduls i `make docs-check`.
- **Suite**: **1.490 tests OK** (1 skip), `pyflakes` net i smoke OK.

**Fet recentment (2026-11-09/10):** model de temps alineat amb els DAW i
simplificació del rubato.
- **BPM sempre en negres/minut**; fora el selector d’unitat del BPM.
- **Rubato = només flag de notació**: mateixos camps i regles que un tram
  normal; fora `0/0` i seqüències. `app/rubato.py` i els seus tests eliminats.
- **`N` per tram** a `mapa_tempo.csv`; rols derivats (`unic`, `primer`,
  `ultim`, `interior`, `preroll`).
- **Motor C/B/A**: en interiors, `N`/BPM/`x/x` exactes → `fi` derivada i veí
  amb BPM recalculat; en l’últim/únic, BPM/`x/x` exactes i `N` derivat (pot ser
  fraccionari). El TAP en viu conserva fronteres.
- **Franja Editor**: BPM, compàs, agrupació, `N`, rol derivat, **Ini (c)** i
  **Fi (c)** editables en compàs.beat, «Ajusta BPM al compàs». Fora el tipus i
  els extrems en segons (es veuen a la llista/carril). Eliminada la icona.
- **Camps de text**: `CampText` mostra l’inici si la dada no hi cap (abans
  s’amagaven els enters i es veien només els decimals).
- **`Analitza beats, downbeats i BPM`** (`F7`) amb botó **Beats/BPM** a la
  barra de treball.
- **QM/downbeats unificats**: `pipeline_vamp.qm_temps()` és l’única extracció
  QM; el mapa de tempo reutilitza els beats i el compàs 1 el primer downbeat.
- El **TAP en viu no obri l’avís de mapa inconsistent**.
- Es conserven la simplificació F0–F5 del
  [`PLA_MAPA_TEMPS`](docs/recerca/PLA_MAPA_TEMPS.md), el model permissiu de
  86 ms, els marcadors `N` fix i l’encaix amb «Quantitza».
- Suite **1562 OK** (1 skip), `pyflakes` i `docs-check` nets.

**Pendent:**
- **Fase 10**: motor de detecció amb corpus real (bloquejat pel corpus manual).
- **Fase 12**: congelació, higiene i CI; inclou el **CI automàtic en push/PR**
  (proposat, encara no activat).
- **Rubato avançat** i **export de projecte DAW**: ajornats sense data.
- **Export MIDI del mapa de tempo**: `mapa_tempo.mid` tipus 1 amb `Set Tempo`,
  `Time Signature`, marcadors i offset/anacrusi; rubato aproximat per events.
  Detall i criteris d'acceptació a «Exportació del mapa de tempo a DAWs».
- **`ARBRE_DIRECTORIS.md`**: encara snapshot manual; pendent generador + test.
- Corpus real de tempo pendent (l'avaluador sintètic funciona).
- **Pendents del motor C/B/A**: connectar `+1`/`−1`/`×2`/`÷2` i «Ajusta BPM
  al compàs» al mateix motor; decidir si «Quantitza BPM» continua sent una
  operació separada.
- **Motor d'àudio natiu amb rellotge de reproducció** (futur; detall davall).

### Futures iteracions — motor d'àudio natiu (2026-11-08)

> **Per què:** a Linux la reproducció va amb `paplay`/`aplay` extern. Estos
> programes **no exposen** quantes mostres ha reproduït el dispositiu ni la
> latència real. Per això el cursor, les llistes, el temps i el ressaltat van
> amb un rellotge de paret + un **retard global manual** (16 ms d'actualització).
> És suficient per a editar, però no és la sincronia de mostra d'un DAW.

- **Objectiu:** un motor d'àudio natiu (ALSA/JACK/PipeWire o PortAudio) que
  reporte la **posició real reproduïda**, la **latència del dispositiu** i
  l'estat del buffer.
- **Què permetria:** cursor i llistes lligats al rellotge d'àudio; compensació
  automàtica de latència; loop i seek sense deriva; un únic camí Linux/mac/win.
- **Requisits:** OK explícit per a dependències noves, fallback si el motor
  falla, proves d'estabilitat i de latència, i mantindre `paplay`/`aplay` com a
  alternativa.
- **Referència conceptual:** REAPER lliga el cursor al rellotge del motor
  d'àudio, no a un cronòmetre de paret; usa buffers/períodes baixos i compensa
  la latència del dispositiu.

### Recalcul de tempo — estat (2026-11-08)

> **Estat:** implementació pràcticament tancada (2026-11-08). Fets: regla del
> múltiple, candidats degenerats, fallback d'un **beat detectat**, avisos de
> BPM/octava, recalcul automàtic en fusionar/eliminar clips, diàleg de
> reparació, unitat del beat 6/8/9/8, helper únic de recompte i tolerància
> operativa de 50 ms per als talls sense snap. Pendent: cost gaussià, pickup
> inicial i validació completa amb una cançó real 6/8 o 9/8. Partix del commit
> `12654a4` (referència base manual «Ref. recalc»); una fase per commit i
> suite verda abans de la següent.

**Problema detectat:** amb beats, la referència base només desempata i mana
«menys compassos primer». Això produïx resultats no canònics: ref 4/4 amb
K=20/24/28 → 5/4/6/4/7/4 N=4 (haurien de ser 4/4 N=5/6/7); ref 3/4 amb
K=12/36 → 4/4 N=3 / 6/4 N=6; ref 6/8 amb K=6/12 → 12/8 N=1/2; K=13 →
2/8 N=13; K=17/19/23 → cau al camí per durada i ignora els beats; una
desviació de BPM gran (p. ex. 8 beats en 6 s amb ref 120 → 80 BPM) no avisa.

**Fases proposades (TODO):**

1. **Regla del múltiple — FET (2026-11-08).** Si la signatura de la referència encaixa amb K
   (`bq_ref > 1`, `K/bq_ref` enter dins la tolerància, `N ≥ 1`, BPM dins de
   rang), triar-la directament. Amb `n_fix`, només si `N` coincidix amb
   `n_ref`; si no, camí actual. La signatura de la referència queda **exempta**
   de `n_max` (p. ex. K=480, ref 4/4 → 4/4 N=120); la resta de candidats
   mantenen `n_max`. No tocar `_COMUNS`/`_MENYS_COMUNS` (11/4 es queda com
   està). Tests: els casos de dalt, `n_fix`, `n_max`, i que continuen igual
   14→7/4 N=2, 8→4/4 N=2, 22→11/4 N=2, 6→3/4 N=2, 9→3/4 N=3, 12→4/4 N=3.
2. **Candidats degenerats — FET (2026-11-08).** Excloure `bq ≤ 1` amb `N > 1`
   (2/8, 1/8, 1/4 amb N>1); mantindre `1/4 N=1` i `1/8 N=1`.
3. **Fallback d'un beat detectat — FET (2026-11-08).** Només amb beats, sense
   `n_fix` i sense cap candidat: provar `K−pas` i `K+pas`, on `pas` és el
   factor de la unitat (1,5 amb negra amb punt, 0,5 amb corxera) i **1,0** si
   els beats són inferits. Prioritzar el `K'` que encaixa amb la referència;
   si no, el de menor `|ln(bpm'/bpm_ref)|`. Si tampoc, camí per durada
   **marcat**. Claus sempre presents: `beats` = K usat, `beats_detectats` = K
   original, `beats_ajustats` = bool, `beats_inferits` = bool.
4. **Avisos, no decisions — FET (2026-11-08).** Afegir a tots els retorns
   `desviacio_bpm` (`bpm/bpm_ref − 1`) i `sospita_octava` (ratio ≈2 o ≈0,5,
   marge 8 %); constants: llindar de desviació 0,12 i marge d'octava 0,08. A
   `_recalcula_costats` i a `aplica_bpm_marcadors`, un avís combinat per clip
   (beats ajustats + desviació + octava), sense avisar pre-roll/rubato; les
   GUI el mostren amb `avis_editor` (no només al log). Quan no hi ha beats
   detectats i el nombre de negres és inferit, l'avís diu «sense beats
   detectats» en compte de «beats ajustats». Propagada la llista opcional
   `avisos` per `parteix_tram_marcador` i `mou_frontera_retempo`.
5. **Recompte robust en talls sense snap — FET (2026-11-08).** Tolerància
   operativa única `TOL_TALL = 50 ms` per classificar els beats de frontera i
   avís quan un beat cau dins la franja (o quan el recompte exacte canvia en
   moure la vora). Els camins de `_recalcula_costats`, `aplica_bpm_marcadors` i
   la reparació comparteixen el helper.
6. **Ajornat (no implementar encara):**
   - Cost gaussià al camí sense beats (σ≈0,04, recalibrar `w_compas`/`w_n`/
     `w_natural` i matriu de casos); només esborrany a `docs/recerca/`, amb OK
     explícit.
   - Àncora de BPM local per veïns, partició en subclips (11=4+4+3), cicle
     d'alternatives canòniques amb una tecla (6/4 ↔ 3/4×2), recompte en viu al
     clip (7 negres → 7/4).

**6/8 — unitat del beat.** `app/bpm_unit.py` continua sent només de
presentació, però la barra 2 té un selector **Beat detectat** (negra per
defecte) que convertix `K` a negres al recalcul: negra amb punt ×1,5,
corxera ×0,5. Els compassos estàndard no canvien si el selector queda en
**negra**. Amb `cop de sort` (55 negres amb punt = 82,5 negres/min), els trams
de 17,45–52,36 s (32 beats amb punt) i 52,36–56,73 s (4) passen a **6/8 N=16**
i **6/8 N=2** a 82,5 BPM.

El helper `n_negres_del_clip` aplica el factor una sola vegada i no
arredoneix a negres senceres: 3 beats amb punt són **4,5 negres** (9/8 N=1) i
5 corxeres són **2,5 negres** (5/8 N=1). Queda pendent el **pickup inicial**
(el primer beat cau a 1,08 s), decidir si el metrònom ha de seguir
automàticament la unitat i **validar el detector amb una cançó real** 6/8 o
9/8: el `CORPUS` actual no en té cap d'etiquetat (els loops GMD són 4/4; els
MIREX no porten compàs). La prova sintètica amb QM no va distingir
negra/negra amb punt/corxera.

**Validació inicial amb cançó real (2026-11-08):** QM sobre `De res - cop de
sort_55bpm_C12_8` retorna 273 beats, intervals de ~1,091 s (54,98 polsos/min)
i el primer a 1,0797 s: confirma que el detector marca negres amb punt en eixe
6/8. Queda provar el flux complet de mapa/reparació amb eixa cançó.

**Fet el 2026-11-08 — fusió/eliminació de clips:** `elimina_tall` i
`fusiona_trams` ara **recalculen el clip afectat** amb la referència base i
els beats abans de validar. Cas real: `149.218–165.800` té K=40; el merge
deixava 4/4 a 144.127 → **9,958 compassos**; ara dona **4/4 N=10 a 144.732**
sense moure la frontera. Si no pot quedar sencer, avisa. Un canvi manual de
compàs que deixa N no enter (10/4→4/4 amb 150 beats → 37,5) ara es **rebutja**
i obri un diàleg per ajustar el BPM a N enter o canviar a la signatura
canònica.

**Dubtes oberts a decidir abans de codi:** una base per cançó vs per secció;
11/4 com a natural (ara és `_MENYS_COMUNS`); `n_max` per als candidats que no
són la signatura base; si els canvis **només de BPM** també han de passar pel
diàleg de reparació (ara només es valida el compàs).

**No implementat en este punt:** cost gaussià, pickup inicial i validació
completa amb una cançó real 6/8/9/8.
La resta de fases, la unitat del beat i el diàleg de reparació sí que estan
implementats (2026-11-08).

Commit de referència: `68dcde1` (checkpoint v9.2).

---

## 3. Regles d'or i criteris

- **Les regles d'or** (invariants) són a
  **[`docs/REGLES_DE_LA_APP.md`](docs/REGLES_DE_LA_APP.md)** → **cap canvi no les
  pot trencar**. Si una idea hi xoca, es canvia **la funcionalitat**, no la regla.
- **Criteri de «producte preparat»**: *obrir WAV → analitzar sense terminal →
  veure/editar acords i estructura → corregir/afegir/eliminar → exportar per
  DAW, tot en una sola app.* → **✅ cobert** (validat per regressions).
- **«Fet»** = hi ha test (smoke + unittest), la **suite és verda** i el
  comportament respecta les regles d'or.
- **Prioritat**: estabilitat → UX/visualització → configuració/automatització →
  export/desplegament.

---

## 4. ARA (Now)

- **Cicle de treball** (acordat): **OC-8 = codi** (blocs amb tests verds →
  **para**) · **OC-5 = tests + documentació + commits locals**.
  **Cap push ni compilacions** sense l'OK de l'operador.
- **Fet (2026-11-02)**: P0 de la revisió — **suite verda** (1.452 tests,
  1 omés), vistes `ESQUEMA_UI` al dia i indicador del TAP coherent (només
  actua amb un tram de tempo seleccionat).
- **Fet (2026-11-02)**: **fase 6** — `Fitxer ▸ Exporta àudio…` amb diàleg
  natiu, perfils WAV/MP3/FLAC/AAC/OGG/Opus i detecció d'encoders en temps
  d'execució; escriptura atòmica i protecció de la còpia de treball.
- **Fet (2026-11-01)**: fases **0–5** del
  [`PLA_SIMPLIFICACIO_TEMPO`](00PER%20FER/PLA_SIMPLIFICACIO_TEMPO.md) —
  línia base i avaluador, validació unificada, fuzzer i proposta de regles,
  TAP robust, compàs vs secció i ajust d'un BPM per mínims quadrats.
- **Fet (2026-11-02)**: **subplà de rubato complet (fases 1–5)** —
  [`00PER FER/DECISIONS_RUBATO.md`](00PER%20FER/DECISIONS_RUBATO.md).
  Inclou la fase 7 del pla de simplificació.
- **Fet (2026-11-03)**: anàlisi del projecte de prova
  `AUTOCHORDS_01 POLICE_convertit`; model coherent i límits del pre-roll,
  notació crua i offset documentats al subplà de rubato.
- **Següent (2026-11-05)**: **consolidar el nucli** i simplificar (abast a
  [`AGENTS.md`](AGENTS.md#-abast-i-flux-de-lusuari--font-única)). La **fase 10**
  (motor de detecció) i el **rubato avançat** queden **ajornats sense data**.
- **EN CURS (2026-11-03) — fase 12: congelació i higiene**:
  - **congelades** les funcions laterals **afinador de guitarra** i
    **`Gt_ALL_Chords_app`**; no s'eliminen, només no es desenvolupen fins que
    l'operador ho decidisca;
  - higiene de tests: `tests/_temporals.py` és obligatori a tots els mòduls de
    test; la suite no deixa temporals;
  - nou workflow manual **`qualitat.yml`** amb fuzzer i proves sintètiques
    **no bloquejants**; no usa cap corpus real;
  - pendent: tancament final i actualització d'estat quan la fase 10 es
    considere estable.

---

## 5. DESPRÉS (Next) — prioritzat (MoSCoW)

### Must (properes línies)
- **FET (fase 1) — validació unificada de BPM/compàs**: límits compartits a
  `app/limits.py` (BPM 30–350, numerador 1–12, denominador 2/4/8), `0/0`
  explícit per al rubato, errors visibles i reparació avisada dels CSV.
  Els casos d'auditoria del 25-10-2026 queden coberts per proves; qualsevol
  regressió nova torna a aquesta llista.
- **FET — edició bàsica d'àudio**: còpia de treball interna,
  retall/afegit als extrems, previsualització, snap compartit, fades de 4 ms,
  sincronització amb el model i desfer/refer conjunt. L'original no se
  sobreescriu.
- **FET (fase 6) — Exportar àudio editat amb FFmpeg**: `Fitxer ▸ Exporta
  àudio…` obri el diàleg natiu de desar; perfils WAV (16/24/32 bits, 44,1/48
  kHz), MP3 128/192/320, FLAC, AAC/M4A, OGG i Opus. Només s'ofereixen els
  còdecs que el `ffmpeg` del paquet pot escriure (`-encoders`). Escriptura
  atòmica, log visible i protecció de la còpia de treball. Vegeu
  [`docs/REGLES_DE_LA_APP.md` §13.9](docs/REGLES_DE_LA_APP.md).
- **AJORNAT (sense data) — Rubato i doble graella avançada**: el que ja hi ha
  implementat es conserva; no s'amplia fins que l'operador ho decidisca. Vegeu
  [`00PER FER/DECISIONS_RUBATO.md`](00PER%20FER/DECISIONS_RUBATO.md).
- **AJORNAT (sense data) — Millorar el motor de detecció (fase 10)**: puntuar
  downbeats amb els canvis d'acord i avaluar motors alternatius. Cap motor nou
  sense l'OK de l'operador. No es treballa ara.
- **PENDENT — Backups: triar/restaurar des de l'app** — llista de còpies
  (`backup/`) amb data-hora → previsualitzar i restaurar (amb confirmació,
  mai destructiu); mostrar què conté cada còpia.
- **PENDENT — Aprofitar l'espai** quan s'amaga el dock «Log · Informació» →
  que el visor creixi i ocupi tota l'alçada.
- **PENDENT — Edició a la graella, UX**: fonts de **snap commutables**
  (events/graella), **tolerància de snap** configurable, **`Ctrl+C` no hauria
  de moure el cursor**, mode **«sense graella»** (rubato) i **indicador visual
  del punt d'ancoratge**.

> ✅ **Fet (2026-10-18/19) — higiene dels tests**: `tests/_temporals.py`
> intercepta i esborra els `tempdir` en plegar. La suite ja no acumula GB a
> `/tmp`. Es manté com a norma per a qualsevol test nou.

### Should

#### Pendent (TODO) — Exportació del mapa de tempo a MIDI/DAWs (2026-11-04)

> **Abast mínim:** generar `mapa_tempo.mid` (tipus 1, pista de conductor) amb
> els canvis de tempo (`Set Tempo`), els canvis de compàs (`Time Signature`),
> els marcadors de compàs/secció i l'offset/anacrusi. Cada tram del
> `mapa_tempo.csv` ha de tindre el seu event MIDI; el rubato s'aproxima amb
> events densos i s'ha d'avisar que és aproximat. **Criteri d'acceptació:** el
> MIDI es pot importar en un DAW i el tempo/timesig/marcadors quadren amb el
> mapa; test de generació i de lectura del fitxer. L'export de `.rpp`/DAW i
> els cues WAV són complements, no substituts del MIDI.

- **PENDENT (TODO) — Exportació del mapa de tempo a DAWs**:
  - **WAV**: pot portar `cue`/`LIST adtl` (marcadors) i, com a molt, un BPM
    únic (`ACID`); **no hi ha un mapa de tempo complex estàndard** ni un
    comportament comú entre DAWs. El `bext`/`iXML` no és un tempo map portable.
  - **MIDI** (abast mínim): exportar `mapa_tempo.mid` (tipus 1, pista de
    conductor) amb `Set Tempo`, `Time Signature` i markers. És el format més portable
    (Cubase/Logic/Pro Tools/Reaper/Studio One…), amb el rubato aproximat per
    events de tempo densos. L’offset/anacrusi necessita marker o projecte DAW.
  - **Reaper**: generar un `.rpp` amb l’àudio, `TEMPO`, `TIMESIG`, markers i
    offset; és el camí exacte per a Reaper, però no intercanviable.
  - **Cues al WAV** per a compàs/secció, com a complement per als DAWs que
    importen marcadors.
  - **Clic de referència WAV** generat amb el mapa, com a alternativa
    universal que qualsevol DAW pot importar i alinear.
  - **BPM per clip**: afegir-lo al `manifest.csv`/`ACID`/`iXML` pot ser útil
    com a metadada, però **no converteix cada clip en un canvi de tempo del
    DAW**. Els clips (sobretot si són silenciosos) no defineixen el tempo
    global; el mapa ha d’anar en un MIDI, un `.rpp` o un altre sidecar.
  - Ordre recomanat: **MIDI + cues + clic** per a multi-DAW; **`.rpp`** per a
    Reaper; el BPM per clip queda com a metadada opcional, no com a substitut
    del mapa.
- **Confiança dels acords** (`loglikelihood` del Chordino) → **ressaltar a la UI**
  els acords dubtosos per revisar-los.
- **Tonalitat** → si mai cal, mostrar-la i, si escau, **paleta d'acords**
  (suggerir diatònics).

### Could
- **`Ctrl+Shift`+arrossegar també per a les seccions** (paritat d'edició #11 amb els acords).
- **Afegeix clips des del timeline** (ara només des del menú de la llista).
- **Overflow de barres d'eines** a < 1300 px (avui es tallen).
- **Beats/bars del qm** per **auto-ajustar la graella** (ara només el 1r downbeat)
  i conservar les **etiquetes de repetició** del qm-segmenter.
- **Configuració persistent** d'usuari (ara només `opcions_detecta.json`).
- **Notes de l'acord** (`chordnotes` del Chordino) a l'Editor.

---

## 6. MÉS ENDAVANT (Later) — idees en un sol lloc, per temes

> Cap **no és planificada**; es valoraran. Cap no pot trencar les regles d'or.
> Fora d'abast vigent: `AGENTS.md` §«FORA d'abast».

### Edició i graella
- **Ripple edit explícit** (commutador: en moure/inserir, la resta s'arrossega o no).
- **Historial d'undo/redo** amb **llista de passos** i salt directe.
- **Modes de graella** (`straight` · **tresets** · **puntets** · `swing` ·
  `custom`) al `grid_plan` + **display `compàs.temps.tick`**.
- **Tempo map / rampes** (BPM variable, compassos 4/4→3/4).
- **Representació de compàs amb 3 xifres** (`1.1.3`…) i decidir si és només
  visual o també al CSV/export.
- **Selecció per rectangle** ja existeix («marc») → afinar-la.

### Navegació i vista
- **Mini-mapa (overview)** de tota la cançó per saltar i seleccionar.
- **Zoom vertical de l'ona** + **carrils amagables i alçada ajustable**.
- **Zoom a la selecció/loop** i **auto-scroll** fi.
- **Tema clar/fosc** (amb opció de seguir el sistema) i **paleta de colors**
  per acords/seccions; **ona amb gradient** per secció.
- **Línia de temps dual segons/BPM**, sincronitzada amb el cursor i la selecció.

### Marques i rang
- **Marcadors amb nom** («solo», «pont»…) + **llista** per saltar-hi (`Tab`) i
  **export de cue-sheet**.
- **Selecció de rang temporal** (arrossegar el regle) per limitar-hi accions.

### So, edició d'àudio i anàlisi
- Els talls continuaran al fotograma triat (sense moure'ls a un zero-crossing);
  els fades automàtics de 4 ms protegeixen les vores.
- **A/B de dues anàlisis** (detectors/paràmetres) amb commutador.
- **Panell avançat de paràmetres del processament** (Chordino/QM) amb mode
  bàsic/avançat.

### Export i partitura
- **Export MIDI** (acords/seccions com a notes o marcadors + **mapa de
  tempo/timesig**); el **PPQ/ticks** només caldria en aquest cas.
- **Generar un projecte de DAW** (`.rpp` de REAPER, `.als` de Live…) amb els
  clips **ja col·locats a la graella** (el «pont» definitiu per a multi-DAW).
- **Plantilles d'export per DAW** (Reaper/Live/Logic) amb noms i carpeta coneguts.
- **Export alternatiu**: **PDF de l'ona+acords**, **Markdown/HTML**,
  **Lyrics+Chords** i **plantilles de paquet** configurables.
- **CSV intel·ligible**, **ABC/LilyPond** i **imatges resumides** de partitura.
- **Convenció semàntica de noms i ordre** dels clips exportats.

### Projectes i flux
- **Pantalla d'inici** (Recents: WAV + projectes · «Nou» · «Obre…»).
- **Arrossega-i-deixa-anar** un `.acproj` damunt la finestra per obrir-lo (els
  àudios ja s'hi poden arrossegar des del 2026-11-05).
- **Explorador multimèdia integrat** (arbre + audició ràpida).
- **Copiar/enganxar entre projectes** (buffer persistent).
- **«Repeteix l'última acció»** (`Ctrl+R`) i **plantilles de projecte**.
- **Presets d'export** i **CLI/headless** (`auto-chords analitza tema.wav`).
- **Suport de vídeo** (treure'n l'àudio) via `ffmpeg`.

### Musical (ajuda a l'usuari)
- **Tonalitat → paleta d'acords** (escala + diatònics verd/vermell + selector).
- **Opacitat segons la confiança** de la detecció.
- **Notes/anotacions per clip** («revisar», «dubtós»).
- **Entrada d'acords** per teclat a pantalla / MIDI (a més del panell).

### Configuració i UX
- **Editor de dreceres** (reassignar + perfils) i **modificadors de ratolí**.
- **Workspaces (screensets)**, panells flotants/acoblables i pantalla completa.
- **Preferències completes** (motor d'àudio, autosave, graella per defecte, tema).
- **Barra de transport configurable** i **peu d'estat** (motor, sr, CPU, autosave).
- **Paleta de comandes** (`Ctrl+K`) i **rellotge gran** (big clock).
- **Accessibilitat** (navegació completa per teclat + lectors de pantalla).

### El que encara queda obert de l'edició
- **Snap a esdeveniments** — ja **fet**; queden **fonts de snap commutables** i
  **tolerància configurable** (vegeu §5, Must).
- **Cursor amb snap** — avui el cursor és lliure (per navegació fina); valorar
  una opció commutable.
- **Indicador de MODE** i **línia guia de snap** més visible durant el drag.

---

## 7. Deute tècnic

- ~~**Refactor de `app/main.py`**~~ → ✅ **FET** (2026-11-06): 4.858 → **1.511
  línies**; extret a `*_ui`, `feines`, `opcions`, `info_box` i `drag_drop_ui`.
- ~~**`app/visor.py`**~~ → ✅ **FET** (2026-11-06): 5.602 → **4.447 línies**;
  extret a `visor_*`.
- ~~**`app/timeline.py`**~~ → ✅ **FET** (2026-11-06): extret
  `timeline_geometry.py`.
- ~~**Codi d'anàlisi guiada en stand-by**~~ → ✅ **RETIRAT** (2026-11-06):
  s'han eliminat la cadena `_guia_*`/`_analisi_guitat`/`_analisi_ancoratges`,
  `FilGuiaBpm`, els diàlegs `DialegGuiaDownbeat`/`DialegGuiaBpm` i els mòduls
  `app/ancoratges.py`/`app/dialeg_ancoratges.py`. Els marcadors en viu (`+`)
  cobreixen el flux. Detall al `CHANGELOG.md`.
- ~~**Higiene dels tests**~~ → ✅ **FET** (2026-10-18/19): `tests/_temporals.py`
  esborra els temporals en plegar; la suite no deixa GB a `/tmp`.
- **`ARBRE_DIRECTORIS.md`**: encara és un snapshot manual; pendent generador +
  test perquè no es desfasï.

---

## 8. Fites i història

- **Fases A–E ✅** — A: visor navegable · B: edició/correcció · C: flux producte ·
  D: interacció DAW-like (D.1/D.2 ✅, D.3 nice-to-have) · E: autodetecció
  avançada (Queen Mary).
- **Multi-SO ✅** — fulla de ruta Windows/macOS (v0.5.1–v0.6.0) → **els 3 builds
  verds** i **release v0.7.0 (BETA)** amb els 3 paquets.
- **Xifrat canònic + panell de tipus + audició · eina del timeline
  (intel·ligent/marc, tecla `E`) · `Ctrl+Shift`+arrossegar = duplicar · treballar
  sense analitzar** — 15–16/10/2026.
- **Anàlisi per etapes + velocitat de reproducció** — 21/10/2026: les 3
  etapes de l'anàlisi (BPM · acords · estructura) són **caselles
  independents** al diàleg d'autodetecció i «Analitza» **també detecta el
  BPM** (i l'aplica al mapa); el transport guanya **selector de velocitat
  0,5–3×** amb el **to mantingut** (`ffmpeg atempo`), amb cursor, loop i
  metrònom alineats (`factor` a `metronom.mescla_metronom`).
- **Pla de simplificació del tempo — fases 0–6 ✅ (2026-11-01/02)**: avaluador
  sintètic (`eines/avalua_tempo.py`), validació unificada, fuzzer d'invariants
  i proposta de regles fusionada, TAP robust amb destí visible, marcadors de
  compàs vs secció, ajust d'un sol BPM per mínims quadrats amb partició
  recursiva i **exportació d'àudio amb FFmpeg**. Detall: `CHANGELOG.md`.
- **Detall complet** de tot això (i els brainstorms originals §10–§12, l'anàlisi
  multi-SO, la nota de graella/PPQ, la d'obertura tecnològica i les notes
  d'implementació): **[`ROADMAP_HISTORIA.md`](ROADMAP_HISTORIA.md)**.


apunt usuari: investigar madmom motor neuronal per detectar downbeats i bpm.
exportar partitures amb silenci al pentagrama, que sonin només els acords xifrats
play a diferents velocitats — ✅ FET (21-10: selector 0,5–3× al transport amb
  `ffmpeg atempo`, to mantingut; cursor, loop i metrònom alineats)
acabar separació analitza tot/només estructura/només acords/ etc.. — ✅ FET
  (21-10: 3 caselles independents al diàleg d'autodetecció —BPM · acords ·
  estructura— i «Analitza» ja detecta també el BPM)
actualitzar documentació V8.x — ✅ FET (2026-11-02)
millorar welcome mode fàcil ( text millor explicat de flux de treball)
millorar info box
