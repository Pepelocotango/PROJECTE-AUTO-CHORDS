# Pla per fases — tempo/compàs i edició bàsica d'àudio

Context: anàlisi del projecte AUTO CHORDS del 25-10-2026.
> Objectiu de producte: importar una cançó → extreure acords, estructura **i mapa de
> tempo/compàs** → revisar-ho, editar-ho i exportar-ho per a l'app, un DAW o una
> partitura. AUTO CHORDS també ha de permetre **edicions d'àudio bàsiques** sobre
> una sola còpia WAV de treball del projecte i exportar-ne el resultat. **Els tres
> carrils musicals continuen sent el producte**: la graella és el que fa útil
> l'exportació, i la qualitat del mapa (que quadri amb la cançó al DAW) és la
> **mètrica central** del projecte.
>

> ⛔ **ATURADA OBLIGATÒRIA (2026-11-02):** abans de continuar amb la **fase 7**
> (i, per tant, amb les fases 10 i 12), cal executar el **subplà de rubato**
> definit a [`DECISIONS_RUBATO.md`](DECISIONS_RUBATO.md). El model `0/0` i les
> tasques de la fase 7 queden **substituïts** per eixe subplà. No implementar
> la fase 7 amb el model antic.

## 0. Normes de treball (obligatòries)

1. **Un bloc = una fase.** En acabar una fase: suite verda + pyflakes net → **para** i informa. Cap push ni compilació sense l'OK de l'operador.
2. **Cap canvi a `docs/REGLES_DE_LA_APP.md` sense aprovació explícita de l'operador** (en particular, fases 1, 2, 6 i 7). Es proposa, no s'aplica. Tot canvi de regla queda al `CHANGELOG`.
3. **Restriccions de maquinari**: Q9400 sense AVX, `numpy<2`, cap `-mavx*` ni `-march=native`. Qualsevol dependència nova s'ha de provar en aquest maquinari abans d'adoptar-la.
4. **Cap substitució silenciosa**: tota correcció d'entrada dolenta avisa a l'usuari i deixa traça al registre.
5. **Una mutació = un sol desfer**, atòmica: o s'aplica sencera o no toca res.
6. Comentaris, missatges d'UI i documentació en **català**.
7. **Verifica abans d'assumir.** Les afirmacions marcades «(per verificar)» no s'han comprovat; confirma-les llegint el codi abans de dissenyar.

---

## Fase 0 — Línia base i corpus de prova

> **Estat: completada (2026-11-01, commit local pendent de publicar).**
> Avaluador, mètriques sintètiques, comprovacions de tipus i notes de
> verificació afegits. L'avaluador passa sis proves específiques i la suite
> completa passa amb 1.417 tests correctes i 1 omés; `pyflakes` i Pylance
> queden nets. No hi ha corpus real autoritzat; la línia base amb àudio queda
> pendent de rebre'l.

**Per què**: sense mesura no es pot saber si un canvi millora o empitjora l'anàlisi.

Tasques:
- Preparar l'avaluador i les proves sintètiques sense dependre d'àudio comercial. El format de «veritat de terreny» per cançó serà JSON: `bpm`, `compas_1_s` (primer downbeat), llista de canvis `(t, bpm, num, den)`, passatges rubato `(ini, fi)`, i opcionalment acords/seccions de referència.
- El corpus real (objectiu orientatiu: 15-20 cançons amb tempo fix, silencis, anacrusi, canvis de BPM o compàs i rubato) el proporciona l'operador i queda fora del repositori per defecte. Només s'hi incorpora, o s'usa al CI, amb permís clar. L'avaluador accepta una ruta local al corpus.
- `eines/avalua_tempo.py`: executa la detecció actual sobre el corpus i imprimeix, per cançó i en conjunt: error de BPM (%), error de downbeat (ms), % de downbeats dins ±70 ms, i temps d'execució.
  **Mètrica central (nova)**: *alineació de la graella a tota la cançó*. Compara els compassos reals amb els detectats i informa de quants encaixen dins ±70 ms, quants en sobren, quants en falten, l'error màxim i la **deriva** (diferència entre l'error del principi i del final). Així no es premia un mapa massa dens només perquè té sempre una línia a prop. També informa de la precisió del BPM, l'error del downbeat i el temps d'execució. Resultats en CSV + resum.
- Amb corpus sintètic, comprovar que l'avaluador funciona i que tracta correctament els casos buits («sense dades»). Quan hi haja un corpus real autoritzat, executar-lo i desar-ne els resultats com a **línia base**; no exigir ni inventar `BASE.csv` abans de disposar d'eixos àudios.
- Respondre (per verificar), i deixar-ho escrit a `docs/NOTES_VERIFICACIO.md`:
  a) Què fa `edita_tempo_objectiu` quan el crida el TAP: passa per `canvia_bpm_local` i mou la frontera amb el veí?
  b) Quin control de la UI obre `_analisi_ancoratges` (v3)?
  c) Quins tests actuals cobreixen cada regla 1–13?

**Acceptació**: l'avaluador funciona sense intervenció amb dades sintètiques i, si no rep cap corpus real, mostra «sense dades». Quan hi haja un corpus real autoritzat, genera els resultats i desa la línia base.

---

## Fase 1 — Constants i validació unificades

> **Estat: completada.** Constants compartides i validador connectats a les
> superfícies d'entrada, reparació avisada dels CSV i proves de regressió.
> Acceptació verificada amb 1.435 proves correctes i 1 omesa; `pyflakes` i
> `git diff --check` nets.
>
> **Continuació:** la fase següent és la 2 (fuzzer d'invariants i proposta de
> regles). No s'ha començat. Executar-la com un bloc separat i parar abans
> d'aplicar canvis al contracte fins a tindre l'aprovació requerida.

**Per què**: és el *Must* del roadmap; hi ha 6 rangs diferents de BPM/compàs repartits.

Tasques:
- Centralitzar els límits compartits a `app/limits.py`: BPM 30–350, numerador 1–12 i denominadors 2, 4 o 8. El límit del numerador i del BPM es conserva; limitar els denominadors és el canvi acordat respecte del contracte actual (§13.4). Afegir-hi altres límits només quan siguen realment compartits (per exemple, la separació mínima entre marcadors); no convertir qualsevol número repetit en una constant.
- Crear `tempo_map.valida_tempo(bpm, num, den)` → retorna valors normalitzats o aixeca `ValueError` amb missatge útil per a l'usuari. Accepta `0/0` com a rubato explícit. Rebutja NaN/Inf, BPM ≤ 0, compàs mal format i zero parcial.
- Fer que **totes** les superfícies hi passen: diàleg de tram, barra/transport, franja Editor, TAP, marcadors, v3 i CSV carregat. Una entrada incorrecta s'avisa i no es converteix silenciosament en 4/4.
- Substituir els límits duplicats identificats per les constants compartides. Afegir proves específiques que comproven que els validadors i les superfícies d'entrada respecten els mateixos límits; no una cerca textual general de números, que podria marcar valors sense relació.
- Actualitzar §13.4 de `docs/REGLES_DE_LA_APP.md` i el `CHANGELOG.md` per deixar constància que els únics denominadors admesos són 2, 4 i 8.
- Tests: BPM 0/negatiu/NaN/Inf/límits; compàs mal format, zero parcial i límits; primer/interior/últim tram; canviar només BPM, només compàs, tots dos; entrada i sortida de `0/0`; veïns mètrics o rubato; rebuig sense mutació parcial; GUI, desfer/refer, CSV desat, recàrrega i export.

**Acceptació**: cap superfície no accepta un valor que una altra rebutja; `0/0` continua sent una opció explícita per al rubato; els valors incorrectes es rebutgen amb avís i sense canvis parcials; les proves específiques són verdes.

---

## Fase 2 — Fuzzer d'invariants i proposta de regles

Tasques:
- Estendre el patró de `_vista_segueix_model___Base`: un fuzzer amb *seeds* que aplica seqüències d'operacions (afegir, eliminar, moure, redimensionar, partir, duplicar, quantitzar, desfer/refer) sobre **els tres carrils** i comprova **després de cada pas** que es mantenen les regles vigents pertinents: cobertura i contigüitat, segons intactes quan només canvia BPM/compàs, fronteres mètriques vàlides i cap mutació parcial davant d'un rebuig.
- Redactar **`docs/PROPOSTA_REGLES_v2.md`** (no tocar el contracte original) amb els invariants candidats, el test que cobreix cada un i quins en tenen i quins no:
  - I1 Partició contigua i completa de `[0, durada]` per carril.
  - I2 Els segons manen; la graella en deriva.
  - I3 Fronteres interiors en línia de compàs (excepcions: primer inici, últim final, trams lliures).
  - I4 Una sola font de veritat al backend, amb un únic punt de refresc.
  - I5 Atòmic, un desfer, sense reparacions silencioses.
  - I6 L'exportació surt del model editat; l'edició no escriu àudio.
- I7 **(candidat)** Les dades incertes no es presenten com a confirmades: el rubato continua com a `0/0` al projecte i a l'app; per als formats d'exportació que necessiten graella, es pot generar un BPM aproximat derivat de la durada i del tempo/compàs de referència, sempre identificat com a aproximació i sense canviar el model.
- Proposar, sense aplicar, si té sentit reorganitzar les regles en *requisits de plataforma* (7, 9, 10), *criteri de paritat* (11, 12) i *especificació del tempo* (§13). No canviar el contracte ni la seva numeració sense decisió explícita de l'operador.
- **Parar i esperar l'aprovació de l'operador** abans d'aplicar res a `REGLES_DE_LA_APP.md`.

**Acceptació**: el fuzzer corre amb ≥ 20 seeds i és verd (o els errors trobats queden documentats com a bugs); la proposta està escrita i no altera el contracte vigent.

---

## Fase 3 — TAP i destí de les accions

Tasques:
- **Un algorisme de TAP robust** (mediana i descart de tocs clarament anòmals) a la barra principal, reutilitzable si en el futur hi ha altres fluxos. Manté l'aplicació en directe i el tancament de sessió als 2 s actuals; tota la sessió continua sent un sol desfer. El rang del TAP segueix els límits compartits de BPM (30–350).
- El TAP manté la semàntica d'edició actual: aplica el BPM al tram objectiu en directe, incloent-hi l'ajust local de frontera que corresponga segons el contracte vigent. No es canvia a la semàntica de «Detecta» ni es fixa una frontera diferent com a part d'aquesta fase.
- **Destí visible sense canviar què fa cada acció**: «Detecta» mostra si analitzarà la selecció A–B, el tram seleccionat o el tema sencer (en aquest ordre de prioritat). El TAP mostra quin tram modificarà: el seleccionat o, si no n'hi ha cap, el primer tram del mapa. El text s'actualitza amb la selecció.
- Tests de GUI per als indicadors i per comprovar per separat que cada acció manté el seu destí i prioritat actuals.

**Acceptació**: el TAP calcula el BPM de manera robusta, l'aplica en directe al destí actual i la sessió es desfà d'una sola vegada; l'usuari sap sempre quin destí tocaran TAP i Detecta, sense haver canviat les prioritats actuals.

---

## Fase 4 — Marcador de compàs ≠ marcador de secció

**Per què**: avui cada `+` talla també l'estructura; marcar un compàs cada 4 genera desenes de seccions.

Tasques:
- Afegir **dos botons explícits**: «Marca compàs» crea una frontera només al mapa de tempo; «Marca secció» crea una frontera al mapa de tempo i a l'estructura.
- El model del marcador guanya un camp `tipus` (`"compas"` | `"seccio"`), que es desa a `marcadors.csv`.
- No invertir temps en compatibilitat amb marcadors de versions anteriors: el format nou no ha de migrar ni interpretar els fitxers antics; els projectes antics poden no conservar aquests marcadors.
- Quan es reprenga l'anàlisi guiada, haurà de llegir els tipus nous: cada interval és un tram i només els marcadors `seccio` generen seccions. No implementar aquest canvi dins de la fase actual mentre el flux guiat estiga aparcat.
- Pintar els dos tipus de manera diferent al timeline. Menú contextual per convertir-ne un en l'altre.
- Tests: afegir/convertir/eliminar de cada tipus; un sol desfer; lectura i desat del format nou; regla 13.6 (el marcador viatja amb la frontera) intacta.

**Acceptació**: marcar 30 compassos no crea cap secció; marcar 3 seccions crea 3 seccions i les fronteres corresponents al mapa de tempo.

**Decisió de compatibilitat**: no cal suportar ni migrar els marcadors dels projectes antics.

---

## Fase 5 — Ajust d'un sol BPM i fusió amb tolerància

**Per què**: el jitter humà fragmenta les cançons de tempo constant en trams amb BPMs gairebé iguals.

Tasques:
- Nou mòdul pur (dins `ancoratges.py` o `tempo_ajust.py`): donats els marcadors de compàs consecutius, ajustar **un sol BPM per mínims quadrats** (temps de la línia de compàs en funció de l'índex de compàs) i calcular el **residu** (ms màxim i RMS).
- Prioritzar un ajust sensible als canvis: si el residu supera el llindar, partir **recursivament** pel punt de màxim residu fins que cada tram complisca o no es puga partir més. Es permet un mínim d'**un compàs per tram**.
- Provar 40 ms i altres llindars amb el corpus abans de fixar el valor per defecte. Informar del nombre de trams i del motiu de cada divisió per poder detectar tant canvis reals com subdivisions causades per soroll dels marcadors.
- `fusiona_trams_iguals` guanya paràmetre de **tolerància** (BPM i fronteres) i només s'activa en aquest ajust, mai a l'edició manual.
- Missatge a l'usuari: «Tempo constant: 120,03 BPM (residu màx. 18 ms)» o «3 trams, motiu…».
- Tests amb dades sintètiques: tempo fix amb jitter → no crear subdivisions innecessàries; canvi de BPM brusc → detectar el canvi; rubato gradual → seguir-lo amb trams i avís; compassos que no encaixen → rebuig amb avís.

**Acceptació**: les proves mesuren tant si es detecten els canvis reals com si se n'inventen; el llindar triat segueix els canvis de tempo sense fragmentar innecessàriament les cançons constants.

---

## Fase 6 — Edició bàsica d'àudio i exportació amb FFmpeg

**Per què**: a més de preparar el mapa musical, l'app ha de permetre fer una
edició senzilla del fitxer d'àudio, inspirada en el flux d'Audacity: forma d'ona,
edició fàcil de desfer i exportació triant el destí. No pretén substituir un DAW
ni un editor complet.

Tasques:
- El format intern continua sent **WAV PCM 16 bits**. En obrir un àudio no
  compatible, convertir-lo directament a l'única còpia WAV de treball de
  `audio/` dins del projecte; no crear un `_convertit.wav` intermedi al costat
  de l'original. L'original extern es conserva intacte. (Això canvia el flux
  actual d'importació i s'ha de cobrir amb proves.)
- L'edició d'àudio sempre es fa dins d'un projecte; no es crea un mode separat
  d'editor de fitxers. L'anàlisi musical és opcional: es pot editar i exportar
  el WAV sense extraure acords ni estructura.
- Sobre la forma d'ona, oferir nanses senzilles per a **retallar l'inici i/o el
  final**. Allargar més enllà de l'àudio existent afegeix **silenci**; no canvia
  la velocitat ni el to. Aquesta fase no edita el mig de la cançó: tallar,
  enganxar, duplicar, fades i processament queden per a més endavant.
- Mentre s'arrossega una nansa, mostrar una previsualització; en deixar-la anar,
  aplicar-ho com una sola acció desferable amb `Ctrl+Z`, sense diàleg de
  confirmació per a cada gest. L'afegit automàtic de silenci per completar
  compassos sí que requereix confirmació.
- L'ajust de les nanses a les línies de compàs es pot activar o desactivar.
- Ajustar el punt final del tall al pas per zero més pròxim per reduir clics;
  no aplicar fades automàtiques. Verificar que l'ajust és molt pròxim al punt
  triat i funciona amb WAV mono i estèreo.
- Si es retalla l'inici, eliminar el contingut anterior al tall i desplaçar
  l'àudio restant i el seu model musical junts cap a zero. Si es retalla el
  final, ajustar el model al nou límit: eliminar el que queda fora i escurçar
  els clips que el travessen. Àudio i model es restauren junts amb un sol
  desfer.
- En afegir silenci al principi, desplaçar amb ell el so i el model musical; al
  final, estendre la cobertura fins al nou límit. El silenci afegit rep un tram
  d'acord `N` (sense acord), mentre la secció existent el continua cobrint.
- Per completar compassos als extrems, calcular i mostrar quant de silenci es
  proposa afegir i una previsió del resultat. L'usuari ha de confirmar abans
  d'aplicar l'afegit de silenci.
- Afegir «Exporta àudio…»: demanar **on** desar el fitxer, el nom i el format.
  Primera llista objectiu: **WAV, MP3, FLAC, AAC/M4A, OGG i Opus**. Verificar
  encoders disponibles en els FFmpeg dels tres paquets abans de prometre cada
  format. Exportar sempre el WAV sencer; usar qualitat predeterminada, sense
  controls tècnics de còdec/bitrate/mostreig. Els errors d'exportació han de ser
  visibles i el WAV de treball no s'ha de substituir. Exportar fragments i
  opcions avançades queda per a més endavant.
- Crear o obrir sempre un projecte per editar àudio; no hi haurà mode independent
  d'editor ràpid. L'anàlisi és opcional: es pot editar i exportar sense extraure
  acords ni estructura.
- Escriure cada canvi en un temporal, validar-lo i només llavors actualitzar la
  còpia WAV del projecte. Àudio i model s'han de mantindre alineats; una edició
  que canvie inici o durada ha de tractar conjuntament acords, estructura,
  marcadors, mapa de tempo i offset. Un sol desfer/refer restaura àudio i model;
  si falla qualsevol part, no s'aplica cap canvi.
- El rubato massa curt al mig continua avisant i rebutjant-se; aquesta fase no
  l'allarga editant el mig de l'àudio.
- Abans d'implementar, revisar la regla 6 i el §13 de
  `docs/REGLES_DE_LA_APP.md`: les regles vigents continuen manant. Si la nova
  edició d'àudio exigeix canviar-ne alguna, parar i demanar aprovació explícita;
  documentar qualsevol canvi aprovat al contracte i al `CHANGELOG`.
- Tests: importació WAV i conversió directa de formats; retallar i afegir
  silenci a cada extrem; confirmar/cancel·lar la proposta; coherència de durada
  i alineació amb el model; exportació a un destí nou en els formats validats;
  original i WAV de treball intactes durant l'exportació; desfer/refer conjunt;
  reducció de clics amb talls propers a pas per zero en mono i estèreo; errors
  sense mutació parcial; rebuig d'un tram lliure massa curt.

**Acceptació**: l'usuari pot obrir àudio, treballar sobre una única còpia WAV
interna, retallar o afegir silenci als extrems amb nanses i exportar una còpia
nova triant destí i format. L'original no canvia; l'àudio i el model continuen
alineats; desfer/refer ho restaura tot. Els formats disponibles són els que
s'hagen validat en els paquets distribuïts.

---

## Fase 7 — Rubato a l'app, mapa aproximat a l'exportació i anacrusi

> **SUBSTITUÏDA pel subplà de rubato** ([`DECISIONS_RUBATO.md`](DECISIONS_RUBATO.md)).
> Aquesta descripció queda com a històric; **no executar-la amb el model `0/0`**.

**Per què**: l'usuari ha de poder conservar i editar el rubato com a temps lliure dins l'app, però alguns formats de DAW o partitura necessiten una graella mètrica. L'exportació pot oferir una aproximació sense canviar el model original.

Tasques:
- **Conservar el rubato al projecte.** Els clips lliures continuen apareixent a l'app com a «TEMPS/LLIURE» i es desen com `0/0`, sense graella. No es canvien els seus segons ni es modifica el model quan s'exporta.
- **Preparar una representació mètrica per als formats d'exportació.** Per cada clip `0/0`, usar com a referència el compàs i el tempo del tram mètric anterior; si no n'hi ha, el següent; si tampoc n'hi ha, els del transport. Triar el nombre enter de compassos que done un BPM més pròxim a aquesta referència i calcular el BPM exacte que fa coincidir l'inici i la fi del clip. La durada real no canvia; el tempo calculat és una aproximació per a la graella d'exportació.
- Aplicar aquesta conversió a les parts actuals de l'exportació que necessiten una graella (còpia de `tempo.csv`/`compas.csv` dins `mapa_tempo/` i MusicXML), mantenint intactes els CSV del model del projecte amb `0/0`. Avisar visiblement i identificar la representació exportada com a **aproximada**; no presentar el BPM calculat com una detecció real. La sortida MIDI queda per a una fase futura.
- Aquesta proposta canvia el contracte vigent de la §13.7 i la representació exportada de la regla 12. Abans d'implementar-la, cal aprovar explícitament l'actualització de `REGLES_DE_LA_APP.md` i deixar-la al `CHANGELOG`.
- **Estats de treball, no resultats**: 0 = només segons · 1 = BPM global + downbeat + compàs · 2 = mapa per trams · 3 = trams amb rubato. Si es mostra un nivell, ha de descriure el que l'usuari ha revisat, no fingir que un valor per defecte està confirmat. Els noms de fitxer exportats **sempre** porten compàs (`1-1-1_C.wav`).
- **Anacrusi i compàs 1: requisit de primera.** Mostrar l'anacrusi com un compàs inicial incomplet; el primer compàs complet continua sent el compàs 1. Fer-ho coherent a la UI, els CSV i l'exportació MusicXML. La validació MIDI en DAWs es farà només quan es reprenga la fase futura. Tests per a: anacrusi d'1 temps, anacrusi de més d'un temps, silenci inicial llarg, silenci final i anacrusi amb canvi de compàs immediat.

**Decisions de l'operador**: presentació visible del caràcter aproximat de la graella exportada.

**Acceptació**: dins l'app, el clip conserva «TEMPS/LLIURE» i els segons originals; els CSV d'exportació i el MusicXML tenen compassos enters que cobreixen la mateixa durada i avisen que són aproximats. La prova inclou anacrusi i silencis.

---

## Fase 8 — Futura evolució: export MIDI (ajornada)

**Estat**: no és una fase activa d'aquest pla. L'operador ha decidit no dedicar-hi temps ara; es reprendrà quan l'export MIDI siga prioritari.

- Mentrestant, conservar el model d'exportació amb el mapa complet, les fronteres en segons, els compassos admesos i els noms de secció. No afegir ara escriptor MIDI, fitxer `.rpp`, menú ni proves d'importació a DAW.
- Notes per reprendre-ho més endavant, no compromisos d'implementació: MIDI estàndard amb **PPQ 480**, tempo i compàs del mapa, marcadors de secció (sense marcadors d'acords), i validació a **REAPER i Ableton Live**. La precisió s'haurà de mesurar aleshores.

**Acceptació actual**: no s'implementa MIDI en aquest pla. La preparació no ha de condicionar ni retardar les exportacions existents.

---

## Fase 9 — Aparcar l'anàlisi guiada fins que la base siga estable

**Estat**: no implementar ni unificar ara l'anàlisi guiada. Primer han de funcionar correctament les autodeteccions, l'edició manual i les exportacions existents.

Tasques:
- Traure de la interfície l'accés visible «Anàlisi guiat» mentre no hi haja un flux complet i fiable.
- Deixar aparcats, sense refactoritzar ni esborrar, el codi i les proves actuals de v2/v3. Revisar-los només quan la detecció i l'edició manual hagen superat les proves d'estabilitat.
- Ajornar també la fusió d'accions del menú *Analitza* i la reorganització de documents/regles; reprendre-les només si continuen sent útils després de validar el flux principal.

**Acceptació**: no es presenta a l'usuari un accés a una anàlisi guiada incompleta o només informativa; detecció i edició manuals continuen disponibles.

---

## Fase 10 — Millorar el motor de detecció (amb mesures)

Tasques:
- **Puntuació de downbeat amb acords**: aprofitar que els canvis d'acord de Chordino cauen sovint en temps forts. Donats candidats de downbeat i compàs del tracker, puntuar-los per la coincidència amb els canvis d'acord i triar o reordenar. Mesurar sobre el corpus; adoptar només si millora la línia base.
- **Avaluar motors alternatius** (madmom, Beat This! o similar) amb l'script de la Fase 0 (mètrica d'alineació de la graella), **un per un i en una branca**: comprovar llicència (models inclosos), compatibilitat amb `numpy<2`, funcionament sense AVX al Q9400, pes de l'AppImage/portable i temps d'execució. Informe amb taula comparativa; **no integrar res** sense l'OK de l'operador.
- Qualsevol motor nou és **opcional** i s'oculta darrere la mateixa interfície de detecció (`pipeline.detecta_beats`/`detecta_bpm`), perquè el tracker de Vamp continuï de reserva.

**Acceptació**: informe amb mètriques sobre el corpus (incloent-hi l'alineació de la graella a tota la cançó); cap regressió a la línia base per defecte.

> ⚠️ **Prioritat de qualitat**: si les mesures mostren que l'autodetecció actual no és prou fiable, cal prioritzar-ne l'avaluació i les millores provades abans de reprendre les fases ajornades 9 i 11.

---

## Fase 11 — Flux del 90 %: proposta, escolta, acceptació

**Estat**: ajornada fins que les autodeteccions, l'edició manual i les exportacions existents siguen fiables.

Quan es reprenga:
- L'app podrà **proposar** BPM, compàs i primer temps, però no els aplicarà ni activarà el metrònom sense que l'usuari ho accepte.
- Rebutjar o ajornar la proposta no bloqueja escoltar, editar acords/estructura ni exportar el model actual; no s'inventa un mapa «provisional» per a substituir dades desconegudes.
- Validar el flux de punta a punta amb àudio sintètic i després amb el corpus real autoritzat.

**Acceptació futura**: la proposta ajuda a començar més ràpid, però l'usuari manté el control i pot continuar treballant sense acceptar-la.

---

## Fase 12 — Congelació i higiene

- Congelar funcionalitats laterals (afinador, `Gt_ALL_Chords_app`, etc.) fins que les fases actives d'aquest pla siguen estables; deixar-ho escrit al ROADMAP. Les fases ajornades 8, 9 i 11 no bloquegen aquesta acceptació.
- Higiene dels tests: esborrar els `tempdir` (`addCleanup(shutil.rmtree, …)` o helper comú).
- Passar el fuzzer i les proves sintètiques al CI com a comprovació no bloquejant. Els àudios reals només s'hi usen si hi ha permís clar; el corpus local de l'operador no és requisit del CI.
- Actualitzar `CHANGELOG`, `README` i `ROADMAP` amb l'estat final.

---


## Resum d'ordre i dependències

| Fase | Depèn de | Necessita decisió de l'operador |
|---|---|---|
| 0 Base i corpus (amb alineació de graella) | — | corpus d'àudio |
| 1 Constants i validació | 0 | — |
| 2 Fuzzer i proposta de regles | 1 | Proposta separada; no canviar el contracte sense aprovació |
| 3 TAP i destí | 1 | — |
| 4 Compàs vs secció | 1, 2 | Dos botons; sense migració de marcadors antics |
| 5 Ajust d'un BPM | 4 | Ajustar llindar amb mesures; permetre un compàs per tram |
| 6 Edició bàsica d'àudio i exportació | 5 | Còpia WAV única; confirmar silenci proposat; validar formats |
| 7 Rubato exportat i anacrusi | 5, 6 | Actualitzar explícitament §13.4, §13.7 i regla 12 al contracte/CHANGELOG |
| 8 Evolució MIDI | Ajornada | Reobrir quan siga prioritari |
| 9 Anàlisi guiada aparcada | Fases de base estables | Reprendre més endavant |
| 10 Motor de detecció — **camí crític** | 0 | adoptar un motor nou |
| 11 Flux del 90 % | Ajornada fins que detecció i edició siguen estables | Acceptació explícita; no aplicar automàticament |
| 12 Congelació i higiene | Fases actives estables | No esperar les fases ajornades |

> **Nota d'ordre**: si les mesures de la Fase 0 mostren que el mapa automàtic no és prou bo, la Fase 10 es prioritza i pot avançar en paral·lel a les fases 3–5. Les fases 8, 9 i 11 queden ajornades i no bloquegen les altres.
