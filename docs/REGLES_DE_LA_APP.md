# ⚠️ REGLES DE LA APP — invariants

> **Contracte, no descripció.** Si el codi incompleix una regla, és un **bug del
> codi**. Si una funcionalitat xoca amb una regla, es canvia la funcionalitat.
> Cap canvi d'estes regles sense **consentiment explícit de l'operador**, i queda
> documentat al `CHANGELOG.md`.
>
> Cada regla (1–12 i §13) té **validació al codi** i **test** a `tests/`; el
> mapa regla → codi → test és a `DEVELOPING.md` §«Implementació del contracte de
> temps».
>
> 📖 Nota no normativa: vista de producte a [`../README.md`](../README.md) i
> abast canònic a [`../AGENTS.md`](../AGENTS.md) §«Abast i flux».

## S'ha de complir SEMPRE — a estos 4 punts

1. **Edició en viu** — cada mutació de la GUI deixa el model vàlid.
2. **Visor** — el que es veu reflectix el model.
3. **CSV desat** — `acords.csv` / `estructura_ABC.csv` es desen ja normalitzats.
4. **Exportació** — el paquet exportat ix del model editat i normalitzat.

No n'hi ha prou d'aplicar les regles «en carregar i en exportar»: s'apliquen
**després de cada edició**.

## Regles 1–12

### 1. Ordre estricte dels clips
Acords, seccions i trams de BPM/compàs estan **ordenats per inici**, sense
solapaments ni inversions. L'estat invàlid no el pot produir l'app; si entra de
fora (CSV a mà, projecte vell, desfer), es **repara i s'avisa** (mai en silenci).

### 2. Contigüitat
Cada clip comença exactament on acaba l'anterior (`prev.fi == curr.ini`) a les
**tres** famílies, amb el model unificat `Clip(ini, fi, payload)`. Al mapa de
tempo el `fi` **no s'emmagatzema**: és l'`ini` del següent (l'últim, la WAV), de
manera que forats i encavalcaments no es poden representar.

### 3. Durades derivades
La durada **no s'emmagatzema**: es deriva de la frontera següent (o de la durada
de la WAV per a l'últim). La **cadena de fronteres** és la font de veritat.

### 4. Cobertura total
La suma dels clips d'acords, de seccions i de trams de BPM/compàs és la **durada
de la WAV** en qualsevol mode i amb o sense snap: el primer clip arrenca a **0**
(capçalera «N» si cal) i l'últim arriba a la durada. La regla **mana sobre el
snap**, que només quantitza límits **interiors**.

En eliminar un clip, el buit l'absorbeix el clip de la **dreta**: el posterior
passa a començar on començava el clip eliminat. Si s'elimina l'últim clip, no
hi ha dreta i l'anterior s'estira fins al final. Si el carril queda buit, hi va
el forat canònic (`N` o `-`). Al mapa de tempo no es pot eliminar l'únic clip.

### 5. Una sola font de veritat
El model viu al **backend**, no al visor. El visor en guarda una **còpia** que
**mai no mana**; tota mutació passa primer pel backend. Les còpies derivades
(mapa, transport, llista, graella) es reconstrueixen en un **sol punt**. La UI
mai fabrica ni muta trams a mà: només crea un tram inicial si el mapa és buit.

### 6. WAVs musicals només en exportar
L'edició no toca mai els WAVs silenciosos d'acords i seccions; només s'escriuen
en exportar. La còpia WAV de treball es pot editar segons §13.9; això no autoritza
a modificar els WAVs musicals generats.

### 7. Instància única
No poden córrer dues instàncies. El bloqueig és un lock **del sistema operatiu**,
**no** un fitxer de PID. El nom inclou l'usuari.

### 8. Temps vàlids
Els **segons** no poden ser negatius ni les durades **≤ 0**. La **numeració de
compàs** comença sempre a **1** en el segon 0; no existeix cap compte enrere.
Els validadors de la UI ho rebutgen; les xarxes de seguretat (CSV a mà) ho
reparen.

### 9. Portabilitat i maquinari objectiu
Ha de córrer a **Linux** (AppImage x86_64), **Windows** (portable x64) i
**macOS** (`.app` per a 10.13+ Intel), amb el maquinari mínim **sense AVX**: cap
dependència ni binari pot requerir AVX ni superar `minos 10.13`.

### 10. Estat en un directori escriptible
Log, opcions i temporals van sempre a un directori **escriptible**, mai dins un
paquet de només lectura (AppImage, portable a `Program Files`, `.app` en
quarantena).

### 11. Paritat d'edició i tracte visual
Acords, estructura i trams de BPM/compàs són iguals davant l'edició i la
visualització, i pel **mateix camí d'usuari**:

- **Operacions comunes**: afegir · eliminar · partir (cursor o meitat) · moure ·
  redimensionar · desfer/refer. Reanomenar i duplicar/fusionar també a acords i
  seccions. Als trams, «afegir» i «partir» són el mateix gest (obrir un tall) i
  «eliminar» fusiona els veïns.
- **Gest idèntic**: nanses, cursors de hover, ressaltat de selecció, ordre z,
  doble-clic/menú contextual i mateixa transparència.
- **Propi de cada tipus** (no s'iguala): payload, camps de l'Editor, edició
  inline i «Reanomena en bloc» (només acord/secció), color/carril.
- **Diferències legítimes del carril de BPM/compàs**: alçada mitjana, sense
  edició inline ni «Reanomena en bloc»; sí franja Editor i llista pròpia.
- **Semàntica**: partir un acord = dos trossos amb el mateix nom (el nou és
  editable); fusionar = harmonia de l'esquerre. Partir un tram = dos trams amb
  el mateix BPM i compàs.

Les operacions **mixtes** (esborrar/copiar una selecció acord+secció+tram) són
una sola operació i un sol `Ctrl+Z`.

### 12. Paritat a l'exportació
El paquet exportat tracta els **tres** tipus igual: acords (`acords.csv` +
`wavs_acords/`) · estructura (`estructura_ABC.csv` + `wavs_estructura/`) · mapa
de tempo/compàs (**`mapa_tempo/`** amb `mapa_tempo.csv`). La graella
exportada coincidix amb el model; els CSV del projecte mantenen `0,0`.

## 13. Temps, compàs i graella

**Resum**: *els segons manen per a l'àudio; els clips de tempo/compàs són el
model (el tram 0 inclòs) i el transport només n'és una vista; el recalcul usa
el **veí esquerre** com a referència i busca compassos sencers; les
fronteres interiors són lliures (snap opcional) i només cal una durada mínima
d'un compàs 1/16 a 350 BPM (≈43 ms); els clips de tempo/compàs tenen un
nombre enter de compassos (`N`), **excepte l'últim**, que pot quedar fraccionari
quan el final de la WAV és fix (qualsevol edició del mapa); **Ajusta final WAV**
és l'única excepció que força `N` enter a l'últim clip; el primer inici (0) i
l'últim final (durada de la WAV) són fixes.*

### 13.1 Els segons són la font de veritat de l'àudio
Acords i seccions es guarden en **segons**: canviar BPM o compàs **no els mou**.
Només es recalcula la posició musical (etiquetes i columnes de compàs). Alinear
a la graella és **Quantitza**, explícit.

### 13.2 Els trams de tempo/compàs manen sobre la graella
Els clips de tempo/compàs manen **sempre**, inclòs el **tram 0**: el mapa definix
BPM i compàs a cada instant i graella, regle, snap, metrònom, numeració i
exports **en deriven**. El **transport** (BPM/compàs del tram 0) és només una
**vista** que se sincronitza des del clip 0; no és una segona font de veritat.
L'edició visible de BPM/compàs es fa a la **franja Editor** del clip de tempo
seleccionat.

### 13.3 Cobertura, ordre i contigüitat del mapa
Els trams cobreixen **tota la WAV**, de 0 a la durada, contigus i ordenats
(`Σ trams = durada`), sense forats, solapaments ni durades nul·les o negatives.
El mapa buit no existix: se'n crea un de sol amb el transport. Si ja hi ha
trams, el transport **no els sobreescriu** (el tram 0 és un clip més). Si **no
se sap la durada** (`durada == 0`), la cobertura no s'imposa i es conserva el
`fi` de l'últim tram.

### 13.4 Model permissiu: valors vàlids i durada mínima
L'edició general de la GUI **no bloqueja** un clip perquè no coincidisca amb
compassos sencers. El model és permissiu:

- **Valors**: BPM **30–350**, numerador **1–12** (inclòs `1/4`), denominador
  **2, 4, 8 o 16**. Un rubato no va en segons ni en `0/0`. El rang de BPM es
  valida sempre en **negres/minut** (espai intern), no en el número mostrat.
- **Unitat de pols per tram**: cada clip té `beat_unit` (`rodona_punt`,
  `blanca_punt`, `blanca`, `negra_punt`, `negra`, `corxera_punt`, `corxera`,
  `semicorxera`). El BPM canònic continua
  sent **negres/minut**; la unitat només canvia la presentació i la conversió
  dels beats detectats/TAP, no el so. Si falta, es deriva de la taula de
  pols percebuda (decisió 2026-11-18):

  - **`x/8`**: `3/8`, `6/8`, `9/8` i `12/8` → **negra amb punt**; la resta
    de `x/8` → **corxera**.
  - **`x/4`**: sempre **negra**.
  - **`x/2`**: sempre **blanca**.
  - **`x/16`**: sempre **semicorxera**.

  L'agrupació explícita **no canvia** esta unitat per defecte; només una
  unitat explícita del tram mana sobre ella. En canviar el compàs `x/x`,
  l'agrupació passa al valor per defecte del compàs nou i la unitat resultant
  seguix esta regla:

  - si la unitat vella era la **derivada**, passa a la derivada del compàs nou;
  - si era **explícita i compatible**, es conserva;
  - si era **explícita i incompatible**, no s'aplica res: es proposa la
    unitat derivada i l'usuari decideix.

  El **BPM intern no canvia mai** en un canvi de compàs: només es recalcula el
  **BPM visible** amb la unitat resultant. El **metrònom per defecte clica el
  denominador** i accentua els inicis de grup: `6/8` → 6 corxeres amb accents
  a 1 i 4, `9/8` → 9, `12/8` → 12. Una unitat explícita
  (`corxera`, `semicorxera`…) mana mentre siga compatible; el denominador
  només és el fallback si la unitat no encaixa en el compàs.
- **Persistència**: `mapa_tempo.csv` porta `beat_unit` al final i es llig per
  noms; columna absent o valor desconegut = **rebuig**, valor buit =
  derivar+avisar. `.acproj` **FORMAT 5** només desa el model actual; els
  projectes de format anterior es rebutgen sense tocar-los.
- **Durada mínima**: cap clip pot ser més curt que un compàs **`1/16`** a 350
  BPM (≈ **43 ms**).
- **N enter sempre, excepte l'últim**: tots els clips de tempo/compàs
  (primer, interiors, penúltim i rubato inclòs) han de contindre un **nombre
  enter de compassos** (`N ≥ 1`). L'**últim clip** pot quedar amb `N`
  fraccionari perquè el final de la WAV és fix: **qualsevol edició del mapa**
  ho pot deixar així (talls, unions, TAP, BPM, N, compàs, enganxat, etc.).
  L'única excepció és **Ajusta final WAV**, que tanca deliberadament l'últim
  clip amb `N` enter perquè quadra el final de la WAV a compassos sencers. Si
  una edició deixa `N` fraccionari en un clip que **no és l'últim**,
  s'**arrodoneix `N`** i es **recalcula el BPM**; si el BPM resultant ix de
  30–350 o el clip queda per davall del mínim, l'operació es **rebutja amb
  avís**.
- **Extrems fixes**: l'**inici del primer clip** és sempre **0** i el **final
  de l'últim** és sempre la **durada de la WAV**; no s'editen. La resta de
  fronteres són interiors i lliures.
- **BPM derivat**: el BPM es deriva de `N`, el compàs i la duració. En el
  recalc fix de l'Editor, el camp triat mana (`BPM`, `Compàs` o `N`) i els
  altres dos s'adapten segons la prioritat indicada; si no hi ha cap combinació
  vàlida, es **rebutja amb avís** sense moure fronteres ni deixar N fraccionari
  (excepte l'últim clip).
- **Fronteres interiors lliures**: poden caure on vulga l'usuari; el **snap és
  opcional** i no s'exigeix cap línia de beat. Els beats detectats **no
  intervenen en l'Editor de tempo**; només s'usen als **Talls QM** (`+`,
  intro/normals) quan **Snap Beats QM** està actiu.
- Entrada invàlida: es rebutja amb avís i sense mutació parcial. CSV extern
  invàlid: es repara i s'informa (incloent-hi l'ajust de `N`/BPM).

### 13.5 Ajust de BPM i compàs: recalcul guiat pel veí esquerre
La referència és sempre el **clip immediatament a l'esquerra** del clip
seleccionat (`clip seleccionat − 1`); si el seleccionat és el primer o l'únic,
s'usa el propi clip. El **veí de la dreta** que es recalcula en editar el clip
seleccionat també s'ancora a eixa referència (el clip anterior al seleccionat),
no al clip seleccionat. No hi ha cap BPM/compàs global.
En moure una frontera, els **segons** són fixos i el recalcul busca la
combinació de **compassos sencers** que més s'acosta a eixa referència: pot
canviar el **BPM**, el **compàs** o el **nombre de compassos** (`N`). El compàs
local mana en `n_previst`, en la regla del múltiple i en `bloca_compas`.

**Talls QM (només `+`/intro/normals, no l'Editor)**: amb **Snap Beats QM**,
el nombre de **negres** (ja amb la unitat del beat aplicada) és una
**restricció forta**: 7 negres han de ser `7/4` (o una combinació equivalent),
no 2 compassos de `4/4` amb 8 negres. Si no s'usen o no n'hi ha, s'intenta
inferir el nombre de negres a partir de la referència; si cau a prop d'un
enter, s'aplica la mateixa restricció; si no, es recorre al càlcul per durada.
Si no hi ha cap combinació, es conserva el valor anterior; si el resultat
incomplix el mínim de durada (o
qualsevol altra regla permissiva), el gest es rebutja amb **avís** (mai un
canvi silenciós).

### 13.6 Fronteres a mà i marcadors
La frontera la col·loca el músic; el snap és **opcional** i és el snap normal del
timeline. No hi ha obligació que les fronteres caiguen en una línia de beat.
Amb el snap apagat, inici i fi es mouen lliurement dins la WAV; el que no pot
passar és que un clip quede per davall del **mínim d'un compàs 1/16 a 350 BPM**
(§13.4), que `N` no siga enter (excepte l'últim clip) o que un extrem isca de
la WAV.

El snap pot ser a la **graella musical**, als **marcadors humans** o als
**onsets detectats**. Marcadors i onsets són capes independents; si la capa
triada és buida, el snap no inventa cap posició i deixa el temps lliure.

**Terminologia obligatòria:** **«recalc fix»** i **«recalc mòbil»**. Són les
dos úniques famílies de recalcul manual; qualsevol agent ha d'usar estos noms
tal qual.

1. **recalc fix** (durada fixa): les fronteres **no es mouen**. Es fixa el
   BPM/compàs (o el nombre de compassos) i es deriva l'altre; si no hi ha
   combinació vàlida, es rebutja amb avís.
2. **recalc mòbil** (una frontera compartida): es mou **exactament una**
   frontera i es recalculen els **dos clips adjacents**. Editar el `fi` del clip
   seleccionat i editar l'`ini` del clip de la dreta són la **mateixa**
   operació. No es mouen l'altre extrem del clip seleccionat ni cap frontera no
   adjacent.

**Moure un bloc sencer** és una operació estructural, no un recalc: es mouen
les **dues fronteres** del clip seleccionat, que conserva BPM, compàs, `N`,
unitat i durada. Els **dos veïns** s'han de recalcular; si qualsevol dels dos
no pot quedar amb `N` enter i una unitat compatible, es **rebutja el moviment
sencer** amb avís i no es deixa cap canvi parcial. Excepció: l'**últim clip**
pot quedar amb `N` fraccionari, com a la resta d'edicions.

**En un recalc manual mòbil no es mouen dues fronteres.** Les operacions
estructurals (partir, fusionar, eliminar, duplicar o moure un bloc) i la
reparació/càrrega poden reajustar diverses fronteres per restaurar `N` enter;
**no són ni «recalc fix» ni «recalc mòbil»** i no es presenten com a tals.

- **Unitat incompatible**: si un canvi de compàs (manual o per recalc) deixa
  la unitat del clip fora de `encaixa_en_compas`, **no s'aplica res**; es
  proposa la unitat derivada i l'usuari decideix. En recalc automàtic es
  filtren els candidats per la unitat actual i, si no n'hi ha cap, es conserva
  el valor anterior amb avís. L'avís d'alineació amb l'agrupació és
  **no bloquejant**.

**Els marcadors són anotacions independents**: no viatgen amb les fronteres
de tempo ni amb les seccions, i no s'esborren quan una frontera desapareix.
Cap operació de tempo —ni automàtica ni explícita— els consulta ni en deriva
BPM, compassos o intervals. Per a ajustar el tempo només manen els inicis i
finals dels clips.

### 13.7 Clips de rubato (`tipus=rubato`)
El rubato és **només un flag de notació**: un tram rubato és idèntic a un tram
normal pel que fa a camps, graella, validació, edició i exportació de dades.

- Al CSV del mapa de tempo: `tipus=rubato` i un **sol compàs** (`4/4`, `6/8`…).
  No s'admeten `0/0` ni seqüències (`4/4*3+3/4`).
- BPM, N, compàs, agrupació, inici i fi són els mateixos camps que un tram
  normal i es poden editar directament.
- La marca “Rubato” només afecta la partitura/exportació de notació.
- Convertir a rubato o a normal només canvia `tipus`; no deriva BPM ni parteix
  el clip.
- Els rubatos **hereten la unitat del primer tram musical**; `beat_unit` és
  un camp més i no canvia el flag `tipus`.
- Un projecte amb rubatos antics de seqüència es rebutja amb error clar.

### 13.8 Detecció i marcadors
La **detecció** conserva els seus criteris musicals i la validació estricta.
Els **marcadors** són anotacions visuals independents del model, segons §13.6.

### 13.9 Edició de l'àudio del projecte
- Afecta només la **còpia WAV de treball**; l'original importat es conserva. Els
  WAVs silenciosos no es modifiquen (regla #6).
- Després de cada operació, acords, seccions i mapa continuen ordenats, contigus
  i cobrint `[0, durada]`. Els trams de tempo/compàs resultants mantenen `N`
  enter a tots els clips; l'últim pot quedar fraccionari (§13.4).
- **Ajusta final WAV** és l'única operació que força `N` enter a l'últim clip:
  quadra el final de la WAV a compassos sencers. La resta d'edicions d'àudio
  poden deixar la cua amb `N` fraccionari.
- L'edició d'àudio és una acció explícita diferent d'un canvi de tempo: §13.1
  continua vigent per al tempo, però retallar/inserir transforma els temps perquè
  les marques seguisquen el mateix so. Les restriccions de §13.6 no autoritzen ni
  prohibeixen esta operació.
- L'àudio i el model són **atòmics** i formen un **sol desfer/refer**. Un error
  no pot deixar àudio i model en estats diferents.

### 13.10 Candaus de protecció del mapa de tempo

La GUI pot protegir tres camps del mapa amb **tres candaus independents**:
**BPM intern**, **N de compassos** i **compàs `x/x`**.

- Són **globals**: afecten tots els clips de tempo/compàs del mapa.
- Es poden activar com a màxim **dos alhora**; el tercer queda deshabilitat.
- Comencen **desactivats** i **no es guarden** entre sessions ni al projecte.
- **Undo/redo** no queden bloquejats: els candaus protegeixen edicions noves,
  no la història.
- Tota edició que produïsca un mapa nou comprova el resultat:
  - si un camp bloquejat canvia, es **rebutja l'operació sencera** amb avís;
  - si el resultat conserva els camps bloquejats, l'operació s'accepta;
  - mai hi ha canvi parcial ni canvi silenciós.
- Els veïns recalculats també compten: si l'operació canvia el camp bloquejat
  d'un veí, es rebutja.
- L'**anàlisi automàtica** no queda bloquejada: pot executar-se i, si aplica
  el resultat automàticament, els candaus no l'aturen. Si l'usuari ha de
  confirmar l'aplicació, eixa aplicació sí que respecta els candaus.
