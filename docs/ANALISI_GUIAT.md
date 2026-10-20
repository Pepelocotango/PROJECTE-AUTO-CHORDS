# Anàlisi guiat — l'assistent de BPM no constant

> **Estat: IMPLEMENTAT (v1, 2026-10-20).** Botó a la barra *Treball*
> (`b_guia`, entre **Obre àudio** i el selector de temps; sense WAV és
> desactivat). Implementació: `main._analisi_guitat` + els mètodes
> `_guia_*` de la Finestra · diàlegs `DialegGuiaDownbeat`/`DialegGuiaBpm`
> a `dialegs.py` · fil de detecció `FilGuiaBpm` · nucli pur a
> `tempo_map.parteix_trams_a` i `tempo_map.trams_finestra_guia`. Tests:
> `TestGuia` (tempo_map) + `TestDialegGuia`/`TestGuiaFlux` (gui).
>
> **Diferred de la v1** (vegeu §4 i §6): el botó *Escolta el tram*, el
> mode automàtic i el «per cops» exacte (`detecta_cops`).
>
> **Necessitat que cobreix**: cançons amb **BPM no constant** (rubato,
> canvis de tempo, temes gravats en viu), on la detecció global del
> rècord falla o un mapa manual trigaria massa. L'assistent guia l'usuari
> pas a pas per construir un **mapa de tempo variable fiable**, i ho
> lliura al diàleg d'**Analitza** normal.
>
> Idea de l'operador (2026-10-20, sessió del botó): «anàlisi *guiat*,
> amb passos interactius i l'usuari al mig». S'anomena **Anàlisi guiat**
> per decisió de l'operador (botó, 20-10-2026).

## 1. El fluxe, pas per pas (versió de l'operador)

| # | Qui | Pas | Punt de codi |
|---|---|---|---|
| 1 | app | El botó **Anàlisi guiat** posa el projecte en **mode temps real** (`hh:mm:ss`) i **desactiva el snap**, perquè puguis buscar el downbeat sense cap grid. | `_canvia_mode_temps(False)` · commutador de snap del transport |
| 2 | **usuari** | Diàleg guiat: *«Posa el cursor a l'inici del primer temps fort de la cançó (downbeat) i prem Enter»* — amb el so a mà (scrub, micro-loop) per trobar-lo bé. | diàleg nou de l'assistent |
| 3 | app | En **Enter**: **offset = cursor** (compàs 1 allà) **i a més talla el carril de tempo/compàs en eixe punt**. El primer clip queda a 120 BPM · 4/4 (per defecte) — **no ens importa**: és la zona pre-música. | 📍 `_marca_compas_1` (offset); el **tall lliure** és `tempo_map.parteix_trams_a` + `aplica_tempo_trams` (backend permissiu: el camí GUI normal rebutjaria el primer tram parcial; el guiat hi va directe, com tota eina del projecte) |
| 4 | app | Torna el mode **BPM · compàs** i fixa el **snap a negra (1/4)** — **immediatament** després del tall (el bucle treballa amb el mapa, no amb el cursor lliure). | `_guia_restaurar_ui()` |
| 5 | app+**usuari** | **Bucle de finestres de 16 temps** (vegeu §2): des del downbeat, analitza la finestra, mostra el BPM i l'**usuari confirma** (Enter · ×2 · ÷2); acceptat → tall de la frontera i següent tram. Les fronteres cauen en **línia de compàs** (opció A del contracte). | fil `FilGuiaBpm` (per finestra) + diàleg `DialegGuiaBpm` + el nucli pur `tempo_map.trams_finestra_guia` |
| 6 | app | … **fins al final de la WAV** (l'últim tram absorbeix la resta, com manda el contracte). | — |
| 7 | app | **Fusió** dels trams adjacents amb el mateix BPM/compàs. | `tempo_map.fusiona_trams_iguals()` — ja existeix |
| 8 | **usuari**+app | **Diàleg Analitza** (el de sempre, tab acords) amb el mapa de tempo ja en marxa: acords + estructura sobre el tema. | `Finestra.executa()` → `dialegs.DialegOpcions` |

**Fi del procés.** Tot el que genera l'assistent és el MODEL del mapa de
tempo (`tempo.csv` + `compas.csv`); **no toca mai el cru** de l'anàlisi.

**Detalls de la v1 implementada:**
- Els diàlegs són **modeless** (pas 1 i pas 2): l'usuari pot moure el
  cursor i escoltar mentre són oberts. Al pas 1, **Enter = Fet**.
- Al pas 2, mentre detecta el camp de BPM és **disabled** i l'acceptació
  és ignorada; quan arriba el resultat (`feta` del fil) s'omple i fica el
  focus. Si la detecció falla, el camp s'habilita per edició manual.
- Cada finestra aplicada és **un pas d'undo** (`_undo_marca/commit` al
  voltant d'`aplica_tempo_trams`); cancel·lar a mitja feina deixa el mapa
  tal com va quedar i es desfà amb Ctrl+Z.
- Cancel·lat el guiat (o acabar-lo), es restaura **mode BPM·compàs +
  snap a negra** sempre.
- ⚠️ **El fil mai toca la GUI directament** (bug real del 20-10, ja
  arreglat): el log del fil va per `missatge(str)` (senyal queued,
  mateix patró que `Feina`) i la Finestra el conect a `registra`.
  Cridar `QTextEdit.append` des del fil = UB → segfault natiu al bucle
  principal.

## 2. La finestra de 16 temps (com viatja)

Cada finestra del bucle **autodetecta els 16 temps següents** des d'on va
quedar la frontera — no assumim mai el BPM «original»:

- **La longitud de la finestra, en segons, surt del BPM del tram anterior**:
  16 temps al BPM anterior = 16 · 60 / BPM_anterior s. És la manera de
  dir «detecta'm els 16 temps següents» sense saber encara el BPM nou: el
  tracker treballa dins d'eixe marge i el BPM que retorna és el seu.
- **Primer tram** (no hi ha BPM previ): finestra d'estimació prou llarga
  per a 16 temps de la cançó més lenta plausible (16 temps a ~70 BPM =
  ≈ 14 s): el BPM que trobi és el de referència del tram següent.
- **No és trampa**: la mida de la finestra només decideix **fins a on es
  talla** el bucle; el BPM n'és sempre la **autodetecció** del tram.
- Si el compàs vigent no és 4/4, el tall es fa en **compassos sencers**
  (16 temps en 4/4 = 4 compàsos; en 3/4, 4 compàsos = 12 temps…): el
  contracte dels **compassos enters interiors** (`REGLES_TEMPS_GRID` §4)
  exigeix fronteres en línia de compàs. Per defecte: **4 compàsos del
  compàs vigent**.

## 3. «Marcar un punt X i que el detector només detecti els N primers cops forts» — què tenim i què fa falta

- **Ja tenim `pipeline.detecta_bpm_tram(wav, inici, fi)`**: analitza
  **només la finestra en segons** que li pases; el **downbeat és l'inici**
  del tram i no busca cap altre. Aquest és el motor del bucle (§2).
- **Ja tenim `pipeline.detecta_beats(wav)`**: temps dels *beats*
  (`qm-barbeattracker`), però **global** (des de 0) — no serveix per
  contar «els 16 primers cops des de X» quan el BPM no és constant.
- **No tenim** literalment «els N primers cops forts des de X», però amb
  `detecta_bpm_tram` + la finestra en segons calculada com al §2 queda
  cobert (finestra sempre prou gran per contindre ≥ 16 cops del BPM real).
- **Extensió possible** (futura, no per a la v1 del guiat): un
  `detecta_cops(wav, inici, n_cops)` — el host amb el tracker i un
  comptador de beats dins la finestra — que faria la finestra exacta
  «per cops» en lloc de per segons. **No és bloquejant** per a la v1.

## 4. Com és la UI de l'assistent (esbós → v1)

- **Pantalla de passos** (diàleg no modal o overlay sobre el visor) amb
  passos numerats i instruccions al costat de les eines que fa falta
  tocar (cursor, loop, transport). → **v1**: `DialegGuiaDownbeat` (pas 1,
  instruccions + Fet/Cancel) i `DialegGuiaBpm` (pas 2, BPM de cada
  finestra), els dos modeless.
- El bucle (pas 5): **Enter = accepta el BPM** · **×2 / ÷2** per arreglar
  errors d'octava (els mateixos botons del transport) · *Escolta el tram*
  (loop del tram sonat) per comprovar-lo a l'oïda. → **v1**: Enter · ×2 ·
  ÷2 ✅; l'usuari pot escoltar amb el transport normal (espai) mentre el
  diàleg és obert; el botó *Escolta el tram* queda **diferit**.
- **Mode automàtic opcional** (només dins el bucle): acceptar el BPM de
  cada finestra sense confirmar — el guiat és per fiabilitat, no de
  cap mena d'obligació. → **diferit** (pregunta §6.1).
- **Cada finestra acceptada = una sola operació de desfer** (igual que
  el comportament actual de les edicions del mapa; al final del tema
  tens un pas d'undo per tram). → **v1**: ✅.
- Progrés del bucle: *tram n* + «resten X s» perquè l'usuari sàpiga el
  que queda. → **v1**: ✅ (títol del diàleg «tram n» + capçalera amb
  inici amb etiqueta de compàs, fi i durada de la finestra en segons).

### 4.1 Detecció limitada a la selecció (loop A–B)

Si hi ha **loop A–B** marcat al visor (`loop_a`/`loop_b`, tant si sona com
si no), cada finestra **mesura el BPM només del tros del loop que cau dins
la finestra** (intersecció; si l'interval resultant és < 1,5 s, cau a la
finestra sencera). El **tram aplicat** continua sent de `m` compassos des de
`t_k`: el loop només acota **on** es mesura. El diàleg del tram ho indica
(«detecció només de la selecció A–B: a–b s»).

El botó **🎯 Detecta** de la barra fa el mateix fora del guiat: amb loop
marcat, el BPM surt només de `[A, B]`.

### 4.2 El botó 📍 fora del guiat

**Compàs 1 al cursor** (`b_offset_cursor` / *Analitza ▸ Marca el compàs 1
aquí*) fa el paquet complet en **un sol desfer**: offset al cursor, **tall**
del carril de tempo (clip de tempo nou si no hi havia frontera) i **inici
del clip** en eixa posició, mostrat en segons i en compàs.beat de la graella
original. El clip nou queda seleccionat (els camps BPM/compàs l'editen).
El tall és lliure: amb trams interiors, cal comprovar que les fronteres
caiguen en línia de compàs.

## 5. Què NO fa (per no demanar-li de més)

- **No toca la detecció global** que ja té el transport: el guiat és una
  via per a BPM no constant, i el rècord global queda com és.
- **No toca el cru** ni els acords/estructura: només construeix el mapa
  de tempo del MODEL (els 2 CSV), com qualsevol altra edició del carril ③.
- **No fa res sense l'usuari**: el downbeat i la confirmació de cada
  tram (en mode guiat) són decisions humanes.

## 6. Preguntes pendents de decisió (operador)

> Estat 2026-10-20 (v1 implementada): (1) confirmació **sempre**, el
> mode automàtic queda **diferit**; (2) fusió exacta, sense canvis; (3)
> **VERIFICAT** — el mapa del guiat passa el contracte de compassos
> enters amb l'offset del pas 1 (tests `TestGuia`, també en 3/4 i amb
> l'últim tram absorbit); (4) el compàs del tram confirmat és el vigent
> i es pot editar a mà després amb les eines normals.

1. **Confirmació per cada tram vs automàtic** (§4) — i si el mode
   automàtic només es fiarà de trams amb estimacions coherents.
   *(v1: confirmació sempre; automàtic diferit.)*
2. **Tolerància de la fusió del pas 7**: ara `fusiona_trams_iguals`
   només uneix trams amb el mateix BPM/compàs **exactes** — si el bucle
   detecta 119,8 i 120,2, quedaran separats. Opcions a valorar:
   arrodonir el BPM de l'assistent (enters o mitjos BPM), o tolerància
   de fusió només dins del guiat.
3. **El tram 0** (0 → downbeat) és zona «pre-música» a 120 BPM per
   defecte: verificar-lo contra el §5 del contracte (el primer tram pot
   començar a mig compàs, però la frontera amb el segon és *frontera
   interior* — d'aquí que el tall del pas 3 vagi via backend permissiu
   i no pel camí GUI).
4. **Canvis de compàs a mig tema** (p. ex. 3/4 dins d'una 4/4): el
   bucle per defecte continua amb el compàs vigent; l'usuari l'edita
   després amb les eines normals (el mapa és editable).

---

> Vegeu també: [`REGLES_TEMPS_GRID.md`](REGLES_TEMPS_GRID.md) (contracte
> dels trams: opció A, compassos enters, detecció per tram) ·
> [`EDICIO_OPERACIONS.md`](EDICIO_OPERACIONS.md) §6 (#36/36b tempo i tap) ·
> [`QM_VAMP.md`](QM_VAMP.md) (motors) · [`FLUX_DE_DADES.md`](FLUX_DE_DADES.md)
> (el MODEL vs cru).
