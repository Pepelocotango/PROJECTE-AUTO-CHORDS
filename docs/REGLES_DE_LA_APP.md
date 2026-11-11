# ⚠️ REGLES DE LA APP — invariants

> **Contracte, no descripció.** Si el codi incompleix una regla, és un **bug del
> codi**. Si una funcionalitat xoca amb una regla, es canvia la funcionalitat.
> Cap canvi d'estes regles sense **consentiment explícit de l'operador**, i queda
> documentat al `CHANGELOG.md`.
>
> Cada regla (1–12 i §13) té **validació al codi** i **test** a `tests/`.

## S'ha de complir SEMPRE — a estos 4 punts

1. **Edició en viu** — cada mutació de la GUI deixa el model vàlid.
2. **Visor** — el que es veu reflectix el model (punt únic:
   `Visor._sincronitza_vista()`, cobert pel fuzzer de `tests/test_gui.py`).
3. **CSV desat** — `acords.csv` / `estructura_ABC.csv` es desen ja normalitzats.
4. **Exportació** — el paquet exportat ix del model editat i normalitzat.

No n'hi ha prou d'aplicar les regles «en carregar i en exportar»: s'apliquen
**després de cada edició**.

## Regles 1–12

### 1. Ordre estricte dels clips
Acords, seccions i trams de BPM/compàs estan **ordenats per inici**, sense
solapaments ni inversions. L'estat invàlid no el pot produir l'app; si entra de
fora (CSV a mà, projecte vell, desfer), es **repara i s'avisa** (mai en silenci).
→ `visor._valida_canvis_*` · `tempo_map.neteja_trams` · `afegeix_tall`.

### 2. Contigüitat
Cada clip comença exactament on acaba l'anterior (`prev.fi == curr.ini`) a les
**tres** famílies, amb el model unificat `Clip(ini, fi, payload)`. Al mapa de
tempo el `fi` **no s'emmagatzema**: és l'`ini` del següent (l'últim, la WAV), de
manera que forats i encavalcaments no es poden representar. `TempoMap` ho
re-deriva en construir-se i `visor._refresca_tempo_map` ho desa amb avís si cal.
→ `timeline.py` · `pipeline.filtra_seccions` · `tempo_map.neteja_trams`.

### 3. Durades derivades
La durada **no s'emmagatzema**: es deriva de la frontera següent (o de la durada
de la WAV per a l'últim). La **cadena de fronteres** és la font de veritat.

### 4. Cobertura total
La suma dels clips d'acords, de seccions i de trams de BPM/compàs és la **durada
de la WAV** en qualsevol mode i amb o sense snap: el primer clip arrenca a **0**
(capçalera «N» si cal) i l'últim arriba a la durada. La regla **mana sobre el
snap**, que només quantitza límits **interiors**. → `pipeline.normalitza_cobertura()`.

### 5. Una sola font de veritat
El model viu al **backend**: `app.pipeline` (acords i estructura) i el mapa de
tempo/compàs (`visor.tempo_trams` + `mapa_tempo.csv`, amb `app.mapa_tempo` com a
model). `app.tempo_map.TempoMap` és el **motor derivat** que calcula graella,
posicions i conversions; no és la font. El visor en guarda una **còpia** que
**mai no mana**; tota mutació passa primer pel backend. Les còpies derivades
(mapa, transport, llista, graella) es reconstrueixen en un **sol punt**:
`visor._refresca_tempo_map`. La UI mai fabrica ni muta trams a mà: només crea un
tram inicial si el mapa és buit.

### 6. WAVs musicals només via `pipeline.exporta_total()`
L'edició no toca mai els WAVs silenciosos d'acords i seccions; només s'escriuen
en exportar. La còpia WAV de treball es pot editar segons §13.9; això no autoritza
a modificar els WAVs musicals generats.

### 7. Instància única
No poden córrer dues instàncies. El bloqueig és un lock **del sistema operatiu**
(`fcntl.flock` a Linux/macOS, `msvcrt.locking` a Windows), **no** un fitxer de
PID. El nom inclou l'usuari. → `plataforma.bloqueja_instancia_unica`.

### 8. Temps vàlids
Els **segons** no poden ser negatius ni les durades **≤ 0**. La **numeració de
compàs** sí que pot ser `≤ 0` quan hi ha **pre-roll** (compte enrere abans del
compàs 1); no és un temps negatiu. Els validadors de la UI ho rebutgen; les
xarxes de seguretat (CSV a mà, projectes vells) ho reparen.
→ `visor._valida_canvis_*` · `pipeline.normalitza_cobertura` ·
`tempo_map.normalitza_trams`.

### 9. Portabilitat i maquinari objectiu
Ha de córrer a **Linux** (AppImage x86_64), **Windows** (portable x64) i
**macOS** (`.app` per a 10.13+ Intel), amb el maquinari mínim **sense AVX**: cap
dependència ni binari pot requerir AVX ni superar `minos 10.13`.
→ `eines/verifica_minos_macos.py` · `GuardAvxTests` (cap `-mavx*`/`-march=native`,
i cal `-msse2`).

### 10. Estat en un directori escriptible
Log, opcions i temporals van sempre a un directori **escriptible**, mai dins un
paquet de només lectura (AppImage, portable a `Program Files`, `.app` en
quarantena). → `app/config.py` tria `DADES_DIR` amb prova d'escriptura real.

### 11. Paritat d'edició i tracte visual
Acords, estructure i trams de BPM/compàs són iguals davant l'edició i la
visualització, i pel **mateix camí d'usuari**:

- **Operacions comunes**: afegir · eliminar · partir (cursor o meitat) · moure ·
  redimensionar · desfer/refer. Reanomenar i duplicar/fusionar també a acords i
  seccions. Als trams, «afegir» i «partir» són el mateix gest (obrir un tall) i
  «eliminar» fusiona els veïns.
- **Gest idèntic**: nanses, cursors de hover, `dragStarted`, ressaltat de
  selecció, ordre z, doble-clic/menú contextual i mateixa transparència.
- **Propi de cada tipus** (no s'iguala): payload, camps de l'Editor, edició
  inline i «Reanomena en bloc» (només acord/secció), color/carril.
- **Diferències legítimes del carril de BPM/compàs**: alçada mitja
  (`LANE_TEMPO_H`), sense edició inline ni «Reanomena en bloc»; sí franja
  Editor i llista pròpia (⑭).
- **Semàntica**: partir un acord = dos trossos amb el mateix nom (el nou és
  editable); fusionar = harmonia de l'esquerre. Partir un tram = dos trams amb
  el mateix BPM i compàs.

Les operacions **mixtes** (esborrar/copiar una selecció acord+secció+tram) són
una sola operació i un sol `Ctrl+Z`.

### 12. Paritat a l'exportació
El paquet exportat tracta els **tres** tipus igual: acords (`acords.csv` +
`wavs_acords/`) · estructura (`estructura_ABC.csv` + `wavs_estructura/`) · mapa
de tempo/compàs (**`mapa_tempo/`** amb `mapa_tempo.csv`).
→ `pipeline.exporta_total(..., mapa_tempo=)` rep el mapa del model viu; si no
se li passa, el paquet queda com era. La graella mètrica exportada pot ser
**aproximada** i s'identifica com a tal; els CSV del projecte mantenen `0,0`.

## 13. Temps, compàs i graella

**Resum**: *els segons manen per a l'àudio; els clips de tempo/compàs són el
model (el tram 0 inclòs) i el transport només n'és una vista; la referència la
posa el músic (BPM/compàs) i el recalcul guiat busca compassos sencers; les
fronteres interiors són lliures (snap opcional) i només cal una durada mínima
d'un compàs 1/16 a 350 BPM (≈43 ms); **tots** els clips de tempo/compàs tenen
un nombre enter de compassos (`N`), i el primer inici (0) i l'últim final
(durada de la WAV) són fixes.*

### 13.1 Els segons són la font de veritat de l'àudio
Acords i seccions es guarden en **segons**: canviar BPM o compàs **no els mou**.
Només es recalcula la posició musical (etiquetes de compàs i columnes
`compas_ini`/`compas_fi`). Alinear a la graella és **Quantitza**, explícit.
L'offset conserva el valor intern (p. ex. `1.207438`) tot i que la GUI en mostre
3 decimals. → `visor._regenera_posicions_musicals` · `tempo_map`.

### 13.2 Els trams de tempo/compàs manen sobre la graella
Els clips de tempo/compàs manen **sempre**, inclòs el **tram 0**: el mapa definix
BPM i compàs a cada instant i graella, regle, snap, metrònom, numeració i
exports **en deriven**. El **transport** (BPM/compàs del tram 0) és només una
**vista** que se sincronitza des del clip 0; no és una segona font de veritat.
L'edició visible de BPM/compàs es fa a la **franja Editor** del clip de tempo
seleccionat. `app/tempo_map.py` és l'**únic motor** del temps; el visor només
n'aplica el resultat. → `tempo_map.TempoMap` · `visor._refresca_tempo_map`.

### 13.3 Cobertura, ordre i contigüitat del mapa
Els trams cobreixen **tota la WAV**, de 0 a la durada, contigus i ordenats
(`Σ trams = durada`), sense forats, solapaments ni durades nul·les o negatives.
El mapa buit no existix: se'n crea un de sol amb el transport. Si ja hi ha
trams, el transport **no els sobreescriu** (el tram 0 és un clip més). Si **no
se sap la durada** (`durada == 0`), la cobertura no s'imposa i es conserva el
`fi` de l'últim tram. → `tempo_map.neteja_trams` · `TempoMap.__init__` ·
`visor._refresca_tempo_map`.

### 13.4 Model permissiu: valors vàlids i durada mínima
L'edició general de la GUI **no bloqueja** un clip perquè no coincidisca amb
compassos sencers. El model és permissiu:

- **Valors**: BPM **30–350**, numerador **1–12** (inclòs `1/4`), denominador
  **2, 4, 8 o 16** (`app/limits.py`). Un rubato no va en segons ni en `0/0`.
- **Durada mínima**: cap clip pot ser més curt que
  `limits.TEMPS_MIN_CLIP` = un compàs **`1/16`** a 350 BPM (≈ **43 ms**).
- **N enter sempre**: tots els clips de tempo/compàs (primer, interiors,
  últim i únic, rubato inclòs) han de contindre un **nombre enter de
  compassos** (`N ≥ 1`). No existix l'estat amb `N` fraccionari: si una
  edició o una càrrega el produïx, s'**arrodoneix `N`** i es **recalcula el
  BPM** perquè la duració quede exacta; si el BPM resultant ix de 30–350 o el
  clip queda per davall del mínim, l'operació es **rebutja amb avís**.
- **Extrems fixes**: l'**inici del primer clip** és sempre **0** i el **final
  de l'últim** és sempre la **durada de la WAV**; no s'editen. La resta de
  fronteres són interiors i lliures.
- **BPM derivat**: el BPM es deriva de `N`, el compàs i la duració. Si
  l'usuari escriu un BPM que no dona `N` enter amb la duració actual, es
  **rebutja amb avís** (no es deixa `N` fraccionari ni es mou la frontera).
- **Offset i pre-roll**: l'offset és la fase de la graella (on cau el compàs
  1) i el pre-roll és el tram de temps abans d'eixe compàs. Cap dels dos
  **no eximeix** el primer clip de tindre `N` enter: el seu `N` es compta
  sobre la **duració completa** del clip (`fi − ini`), no sobre el tros
  posterior a l'offset.
- **Fronteres interiors lliures**: poden caure on vulga l'usuari; el **snap és
  opcional** i no s'exigeix cap línia de beat. **Només amb Snap Beats QM** els
  beats detectats intervenen en els talls i recalcs; amb Snap Auto o qualsevol
  altra graella mana el BPM/compàs i els QM no canvien el resultat. Quan un tall sense snap cau a
  prop d'un beat, el recompte usa una **tolerància operativa de 50 ms** i
  avisa si el beat és ambigu o si el recompte exacte canvia; no s'imposa cap
  desplaçament de la frontera.
- Entrada invàlida: es rebutja amb avís i sense mutació parcial. CSV extern
  invàlid: es repara i s'informa (incloent-hi l'ajust de `N`/BPM).

La validació **estricta** (`valida_i_normalitza_compassos`,
`_millora_signatures_clips`, `ajusta_bpm_a_compassos`, `retempo_tram_detectat`)
es conserva per als **detectors** i les **accions explícites**, però **no és el
camí general d'edició**.

→ `tempo_map.valida_tempo` · `valida_i_normalitza_permissiu` ·
`limits.TEMPS_MIN_CLIP` · `neteja_trams`.

### 13.5 Ajust de BPM i compàs: recalcul guiat per la referència
La referència la posa el músic: el BPM i el compàs que cada costat tenia abans
del gest. En moure una frontera, el punter fixa els **segons** i
`tempo_recalc.recalculca_tram()` busca la combinació de **compassos sencers**
que més s'acosta a eixa referència: pot canviar el **BPM**, el **compàs** o el
**nombre de compassos** (`N`). Si hi ha **beats detectats** dins del clip, el
nombre de **negres** (`K`, ja amb la unitat del beat aplicada) és una
**restricció forta**: 7 negres han de ser `7/4` (o una combinació equivalent),
no 2 compassos de `4/4` amb 8 negres. El recompte el fa
`tempo_recalc.n_negres_del_clip()` amb una tolerància única de frontera; si no
hi ha cap beat dins el clip retorna `None` (no `0`). Per als talls manuals
sense snap, la tolerància operativa és **50 ms** (`TOL_TALL`): un beat dins
d'eixa franja es classifica de manera estable i s'avisa (activa snap si vols
una frontera inequívoca). El BPM s'ajusta per
encaixar eixa xifra. Si **no hi ha beats detectats**, s'intenta inferir el
nombre de negres a partir de la referència (`D × BPM_ref / 60`); si cau a prop
d'un enter (±0,2), s'aplica la mateixa restricció; si no, es recorre al càlcul
per durada. Si no hi ha cap combinació, es conserva el valor
anterior; si el resultat incompleix el mínim de durada (o qualsevol altra regla
permissiva), el gest es rebutja amb **avís** (mai un canvi silenciós).

- **Regla del múltiple**: si la signatura base encaixa exacta amb els beats
  (`K/bq_ref` enter), mana ella; 20/24/28 beats amb base 4/4 → 4/4 N=5/6/7;
  12/36 amb base 3/4 → 3/4 N=4/12; 6/12 amb base 6/8 → 6/8 N=2/4. Amb `n_fix`
  només val si `N` coincidix amb el fixat; la signatura base n'està exempta de
  `n_max` (clips llargs).
- **K no factoritzable**: s'exclouen els compassos degenerats (`2/8`, `1/8`,
  `1/4` amb `N>1`) i es prova **un beat detectat** amunt/avall
  (`K ± beat_factor`; 1,5 negres amb negra amb punt, 0,5 amb corxera, i 1,0
  si els beats són inferits). Es prefereix el que encaixa amb la signatura
  base i, si no, el de BPM més pròxim. El resultat indica `beats_ajustats`,
  `beats_detectats` i `beats_inferits`; amb beats inferits l'avís diu «sense
  beats detectats», no «beats ajustats».
- **Avisos de BPM**: cada recalcul pot adjuntar una desviació de BPM >12 % i
  una sospita d'octava (ratio ≈2 o ≈0,5, marge 8 %). Són avisos, no canvien la
  decisió.
- **Edició directa de `N`**: `N` és exacte i **enter**. Es recalcula el BPM
  perquè `N` compassos hi caben. En interiors també es deriva `fi`
  (`base + N · bq · 60 / BPM`); la frontera del veí de la dreta passa a eixa
  `fi`, i el veí conserva el seu `N` enter i **recalcula el BPM**.
- **Edició directa de BPM o `x/x`**: les fronteres **no es mouen**. El valor
  ha de donar un `N` enter amb la duració actual (`N = Δt · BPM / (bq · 60)`);
  si no, es **rebutja amb avís**. El BPM és una vista derivada, no una segona
  font de veritat.
- **Últim i únic**: el final de la WAV no es mou i `N` ha de ser enter. Si una
  edició de frontera o una càrrega deixa `N` fraccionari, s'arrodoneix `N` i
  es recalcula el BPM amb el final fix. Si el BPM resultant ix de 30–350 o el
  clip queda massa curt, l'operació es rebutja amb avís.
- **«Ajusta BPM al compàs»** continua sent una **acció explícita**: conserva
  fronteres, compàs i `N` enter, i recalcula el BPM. No s'aplica
  automàticament.
- **Arrossegar una frontera** continua usant el recalcul guiat amb segons com a
  entrada; no és una edició directa de camps.
- **Arrossegar**: el punter fixa Δt; s'ajusten les fronteres i el recalcul
  guiat decideix BPM/compàs/N enters dels dos costats amb la **referència
  base**.
- Un tram **rubato** es mou i es re-tempa com qualsevol tram normal; només canvia
  el flag de notació.

→ `mapa_tempo.recalcula_tram_c` · `tempo_recalc.recalculca_tram` ·
`tempo_map.mou_frontera_retempo` · `ajusta_bpm_a_compassos`.

### 13.6 Fronteres a mà i marcadors
La frontera la col·loca el músic; el snap és **opcional** i és el snap normal del
timeline. No hi ha obligació que les fronteres caiguen en una línia de beat.
Amb el snap apagat, inici i fi es mouen lliurement dins la WAV; el que no pot
passar és que un clip quede per davall del **mínim d'un compàs 1/16 a 350 BPM**
(§13.4), que `N` no siga enter o que un extrem isca de la WAV. El **pre-roll**
(només la frontera `0→1`) **no** exempta de `N` enter: el primer clip també ha
de tindre un nombre enter de compassos.

`Inici (s)` i `Fi (s)` són editables. Com que la frontera és única, moure'n un
mou **eixa** frontera; l'extrem contrari no es mou i s'aplica el **recalcul
guiat** del clip i, si cal, del veí:

| Gest | Resultat |
|---|---|
| `ini` del **1r** clip | **rebutjat + avís** (inici de la WAV) |
| `fi` de l'**últim** clip | **rebutjat + avís** (fi de la WAV) |
| `ini` de qualsevol altre | mou la frontera `(i-1, i)`; el `fi` no es mou; recalcul guiat |
| `fi` de qualsevol altre | mou la frontera `(i, i+1)`; l'`ini` no es mou; recalcul guiat |
| costat rubato | es mou com un tram normal; el flag `tipus` no canvia |

Si l'instant no és possible, s'aplica el més a prop i **s'avisa**.

- **`+`**: parteix **tempo i estructura** al cursor, sense crear cap marcador.
  **Enter**: parteix només el tempo. **`0`**: parteix només l'estructura.
  Amb Snap actiu s'encaixa a la graella; amb Snap desactivat es respecta el
  cursor. Si el tall necessita ajust, s'aplica el recalcul guiat (§13.5).
- **`M`**: crea només un **marcador independent**; no talla tempo ni
  estructura i no està lligat a cap frontera.
- **Només la frontera 0→1 és pre-roll.** Les fronteres 2–3, 3–4… són interiors
  normals (`mou_frontera_retempo`).
- En fixar l'offset amb **Compàs 1 aquí**, el pre-roll es recalcula amb un
  **nombre enter de compassos** (`N ≥ 1`) i el BPM es deriva per encaixar-hi;
  el clip de música següent també conserva `N` enter i recalcula el seu BPM.
  L'offset es desa immediatament al `.acproj`.
- **Els marcadors són anotacions independents**: no viatgen amb les fronteres
  de tempo ni amb les seccions, i no s'esborren quan una frontera desapareix.
  Per a ajustar el tempo només manen els inicis i finals dels clips.
- **Graella robusta**: un canvi de compàs a menys de **20 ms** d'una línia de
  compàs s'imanta a la línia; no es creen dos compassos quasi iguals ni salta
  la numeració. Les etiquetes i el metrònom toleren els offsets d'integració
  de fraccions de fusa (resolució 1/32), de manera que una edició manual de
  mil·lisegons no atura el metrònom.
- **Fusionar o eliminar una frontera** recalcula el clip afectat amb la
  referència base i els beats. Si no pot quedar en compassos sencers, avisa i
  el deixa com està; no hereta el N fraccionari del clip que desapareix.

→ `tempo_map.mou_frontera_retempo` · `visor._on_tempo_mogut` ·
`visor._aplica_editor_tempo` · `marcadors`.

### 13.7 Clips de rubato (`tipus=rubato`)
El rubato és **només un flag de notació**: un tram rubato és idèntic a un tram
normal pel que fa a camps, graella, validació, edició i exportació de dades.

- Al `mapa_tempo.csv`: `tipus=rubato` i un **sol compàs** (`4/4`, `6/8`…).
  No s'admeten `0/0` ni seqüències (`4/4*3+3/4`).
- BPM, N, compàs, agrupació, inici i fi són els mateixos camps que un tram
  normal i es poden editar directament.
- La marca “Rubato” només afecta la partitura/exportació de notació.
- Convertir a rubato o a normal només canvia `tipus`; no deriva BPM ni parteix
  el clip.
- Un projecte amb rubatos antics de seqüència es rebutja amb error clar.

→ `app/mapa_tempo.py` · `tempo_map` · `visor_tempo` · `partitura`.

### 13.8 Detecció i marcadors
La **detecció** conserva els seus criteris musicals i la validació estricta.
Amb un **tram seleccionat**, *Detecta* analitza només eixe tram i el downbeat és
el seu inici. En un tram delimitat per marcadors, **Δt és fix**: el BPM detectat
només compta compassos (`N = round(Δt · BPM_ref / (bq · 60))`, mínim 1) i
s'aplica el **BPM derivat exacte** (`N · bq · 60 / Δt`), que clava les barres
entre els dos punts. La fi del tram i els següents no es mouen; si el BPM derivat
cau fora de 30–350 o no hi cap cap compàs sencer, **s'avisa**. S'aplica en una
sola operació de desfer.

Els **marcadors** són anotacions independents del model. Les accions
explícites *BPM dels marcadors* i *Ajusta BPMs a partir dels marcadors* poden
usar-los com a referència manual, però cap operació automàtica de tempo els
consulta. *BPM dels marcadors* usa el
**nombre de compassos de cada interval** com a `N` **fix**; el recalcul usa la
**referència base de la barra 2** per al BPM/compàs (no la del clip). Si hi ha
**beats detectats** dins l'interval, el seu nombre de **negres** **mana**
sobre el `N` estimat i pot corregir el compàs: 7 negres són `7/4`, no 2×`4/4`;
14 negres `7/4` N=2 i 8 negres `4/4` N=2. En estes accions explícites, els
intervals dels marcadors i els beats manen sobre
l'estructura de compassos i el tempo s'hi adapta.

Per a tempo variable, *Analitza ▸ Detecta el tempo per trams…* fa el mapa sencer
(un BPM cada N compassos, amb els criteris musicals del detector) i el valida de
manera estricta. L'export porta les tres parts (acords, estructura i mapa).

→ `tempo_map.retempo_tram_detectat` · `tempo_map.ajusta_trams_a_marcadors` ·
`tempo_recalc.recalculca_tram` · `visor_marcadors.aplica_bpm_marcadors` ·
`app/tempo.py` · `pipeline.desa_tempo_map`.

### 13.9 Edició de l'àudio del projecte
> **Estat**: implementat quant a importació, backups, retall/afegit als extrems,
> sincronització del model, desfer/refer i exportació d'àudio amb FFmpeg. Queden
> pendents la restauració des de la GUI i les proves visuals. **No implementat**
> (2026-11-04): afegir silenci automàticament per completar el pre-roll o el
> primer compàs; no s'ha de tocar el flux manual de nanses mentre no es decidisca.

- Afecta només la **còpia WAV de treball**; l'original importat es conserva. Els
  WAVs silenciosos no es modifiquen (regla #6).
- **Retallar l'inici `t`**: s'elimina l'àudio anterior; elements, marcadors,
  fronteres i offset es desplacen `−t`; el contingut anterior desapareix.
- **Retallar el final a `D`**: s'eliminen els elements posteriors, s'escurcen els
  intervals que travessen `D` i la durada nova és `D`.
- **Afegir silenci al inici `t`**: so i referències es desplacen `+t`; offset
  `+t`; es crea un acord `N` per al silenci i la secció existent el cobrix.
- **Afegir silenci al final**: la cobertura s'estén fins a la nova durada amb
  acord `N`; secció i últim tram cobrixen l'extensió.
- Després de cada operació, acords, seccions i mapa continuen ordenats, contigus
  i cobrint `[0, durada]`. Els trams de tempo/compàs resultants mantenen `N`
  enter a tots els clips, primer i últim inclosos (§13.4).
- L'edició d'àudio és una acció explícita diferent d'un canvi de tempo: §13.1
  continua vigent per al tempo, però retallar/inserir transforma els temps perquè
  les marques seguisquen el mateix so. Les restriccions de §13.6 no autoritzen ni
  prohibixen esta operació.
- Previsualització en arrossegar, aplicació en deixar anar; àudio i model
  **atòmics** i un sol desfer/refer. Tall al fotograma més pròxim, sense moure a
  un pas per zero. Cada vora àudio/silenci rep un **fade de 4 ms**. El crossfade
  entre clips queda fora de l'abast inicial (només hi ha un WAV).
- L'historial conjunt conserva les **10 últimes accions** (musicals i d'àudio) i
  comunica quan descarta la més antiga.
- S'escriu primer en un temporal i es valida abans de substituir la còpia. Un
  error no pot deixar àudio i model en estats diferents.
- Les còpies de seguretat versionades inclouen el WAV de treball i els marcadors.

→ Proves: `tests/test_exporta_audio.py` i les d'edició/undo/backups.

## Notes d'implementació

- En **carregar** un projecte es fusionen els trams adjacents amb el mateix BPM i
  compàs; una partició manual de dos trams iguals es respecta mentre s'edita.
- Totes les edicions de la GUI que re-temporitzen passen pel **re-tempo local**;
  si el resultat no complix el contracte, no es toca res i s'avisa.
- Quan el model es reconstrueix (quantitzar, desfer…), la selecció es notifica
  buida i l'editor es buida o refresca: mai el temps vell d'un clip mogut.
