# Pla per fases — simplificar i professionalitzar el flux de BPM/compàs

Context: anàlisi del projecte AUTO CHORDS del 25-10-2026.
> Objectiu de producte: carregar una cançó → extreure acords, estructura **i mapa de
> tempo/compàs** → veure'ls i exportar-los perquè un músic els pugui fer servir dins la propia app, 
> en un DAW i en una partitura. **Els tres són el producte**: un acord sense compàs no és
> interpretable per a un músic. La graella és el que fa útil l'exportació, i la qualitat del
> mapa (que quadri amb la cançó al DAW) és la **mètrica central** del projecte.
>

## 0. Normes de treball (obligatòries)

1. **Un bloc = una fase.** En acabar una fase: suite verda + pyflakes net → **para** i informa. Cap push ni compilació sense l'OK de l'operador.
2. **Cap canvi a `docs/REGLES_DE_LA_APP.md` sense aprovació explícita de l'operador** (fases 2, 6 i 8). Es proposa, no s'aplica. Tot canvi de regla queda al `CHANGELOG`.
3. **Restriccions de maquinari**: Q9400 sense AVX, `numpy<2`, cap `-mavx*` ni `-march=native`. Qualsevol dependència nova (fase 8) s'ha de provar en aquest maquinari abans d'adoptar-la.
4. **Cap substitució silenciosa**: tota correcció d'entrada dolenta avisa a l'usuari i deixa traça al registre.
5. **Una mutació = un sol desfer**, atòmica: o s'aplica sencera o no toca res.
6. Comentaris, missatges d'UI i documentació en **català**.
7. **Verifica abans d'assumir.** Les afirmacions marcades «(per verificar)» no s'han comprovat; confirma-les llegint el codi abans de dissenyar.

---

## Fase 0 — Línia base i corpus de prova

**Per què**: sense mesura no es pot saber si un canvi millora o empitjora l'anàlisi.

Tasques:
- Crear `tests/corpus/` (fora del paquet) amb un format de «veritat de terreny» per cançó, en JSON: `bpm`, `compas_1_s` (primer downbeat), llista de canvis `(t, bpm, num, den)`, passatges rubato `(ini, fi)`, i opcionalment acords/seccions de referència. El corpus d'àudio el proporciona l'operador (objectiu: 15-20 cançons: tempo fix, silenci inicial/final, anacrusi, canvi de BPM, canvi de compàs, rubato). L'agent només prepara l'estructura i l'script.
- `eines/avalua_tempo.py`: executa la detecció actual sobre el corpus i imprimeix, per cançó i en conjunt: error de BPM (%), error de downbeat (ms), % de downbeats dins ±70 ms, i temps d'execució.
  **Mètrica central (nova)**: *alineació de la graella a tota la cançó* — per a cada línia de compàs de la veritat de terreny, distància a la línia més propera del mapa detectat; informa el % dins ±70 ms i l'error màxim, i també la **deriva** (error al principi vs al final). Una cançó amb el primer downbeat bé però amb deriva no és un bon resultat. Sortida en CSV + resum.
- Executar-lo i desar els resultats com a **línia base** (`tests/corpus/BASE.csv`).
- Respondre (per verificar), i deixar-ho escrit a `docs/NOTES_VERIFICACIO.md`:
  a) Què fa `edita_tempo_objectiu` quan el crida el TAP: passa per `canvia_bpm_local` i mou la frontera amb el veí?
  b) Quin control de la UI obre `_analisi_ancoratges` (v3)?
  c) Quins tests actuals cobreixen cada regla 1–13?

**Acceptació**: l'script corre sense l'operador amb un corpus buit (mostra «sense dades») i amb un de real; la línia base està desada.

---

## Fase 1 — Constants i validació unificades

**Per què**: és el *Must* del roadmap; hi ha 6 rangs diferents de BPM/compàs repartits.

Tasques:
- Crear `app/limits.py` amb **totes** les constants: `BPM_MIN/MAX` (30–350), compàs (num 1–12, den 1–16), separació mínima de marcadors, banda del re-tempo, etc. Cap altre mòdul no en repeteix el número.
- Crear `tempo_map.valida_tempo(bpm, num, den)` → retorna valors normalitzats o aixeca `ValueError` amb missatge d'usuari. Accepta `0/0` com a rubato explícit. Rebutja NaN/Inf, BPM ≤ 0, compàs mal format, zero parcial.
- Fer que **totes** les superfícies hi passin: diàleg de tram, barra/transport, franja Editor, TAP, marcadors, v3, CSV carregat. Eliminar el fallback silenciós a 4/4.
- Substituir els literals trobats (60–180, 1000, 0,2–2,0 s…) per constants. Un test d'arquitectura (`grep` automatitzat) falla si apareix un literal de límit fora de `limits.py`.
- Tests: BPM 0/negatiu/NaN/Inf/límits; compàs mal format, zero parcial i límits; primer/interior/últim tram; canviar només BPM, només compàs, tots dos; entrada i sortida de `0/0`; veïns mètrics o rubato; rebuig sense mutació parcial; GUI, desfer/refer, CSV desat, recàrrega i export.

**Acceptació**: cap superfície no accepta un valor que una altra rebutja; el test d'arquitectura és verd.

---

## Fase 2 — Fuzzer d'invariants i proposta de regles

Tasques:
- Estendre el patró de `_vista_segueix_model___Base`: un fuzzer amb *seeds* que aplica seqüències aleatòries d'operacions (afegir, eliminar, moure, redimensionar, partir, duplicar, quantitzar, desfer/refer) sobre **els tres carrils** i comprova **després de cada pas**: partició contigua i cobertura (I1), segons intactes quan només canvia BPM/compàs (I2), fronteres interiors en línia de compàs (I3), cap mutació parcial davant d'un rebuig (I5).
- Redactar **`docs/PROPOSTA_REGLES_v2.md`** (no tocar l'original) amb els 7 invariants següents, el test que cobreix cada un i quins en tenen i quins no:
  - I1 Partició contigua i completa de `[0, durada]` per carril.
  - I2 Els segons manen; la graella en deriva.
  - I3 Fronteres interiors en línia de compàs (excepcions: primer inici, últim final, trams lliures).
  - I4 Una sola font de veritat al backend, amb un únic punt de refresc.
  - I5 Atòmic, un desfer, sense reparacions silencioses.
  - I6 L'exportació surt del model editat; l'edició no escriu àudio.
  - I7 **(nova, reformulada)** *El mapa sempre existeix i sempre s'exporta.* Mentre l'usuari el corregeix, la resta de l'app (veure, escoltar, editar acords) no es bloqueja; però cap exportació no surt sense mapa. Si el mapa no és fiable, l'export **avisa clarament** i utilitza un tempo constant per defecte marcat com a **provisional** (vegeu Fase 6). El «nivell 0 · només segons» és un estat de treball, mai un resultat.
- Proposar quines regles passen a: *requisits de plataforma* (7, 9, 10), *criteri de paritat* (11, 12) i *especificació del tempo* (13.5–13.8).
- **Parar i esperar l'aprovació de l'operador** abans d'aplicar res a `REGLES_DE_LA_APP.md`.

**Acceptació**: el fuzzer corre amb ≥ 20 seeds i és verd (o els fallos trobats estan documentats com a bugs); la proposta està escrita.

---

## Fase 3 — TAP i destí de les accions

Tasques:
- **Un sol algorisme de TAP** (mediana + descart d'*outliers* + reinici a 2,5 s) compartit pel transport i el diàleg v3. Que el rang vingui de `limits.py`.
- **El TAP mesura i no mou fronteres.** Mostra el BPM proposat i l'usuari el confirma (Enter o botó) abans d'aplicar-lo. Si s'aplica a un tram interior, fa servir la semàntica de «Detecta» del §13.8 (fronteres fixes, BPM derivat), no la de `canvia_bpm_local`. Si (a) de la Fase 0 demostra que ja era així, només cal unificar l'algorisme.
- **Destí visible**: el botó «Detecta» i el TAP mostren el destí a l'etiqueta o al tooltip: «Detecta · tram 3» / «· selecció A–B» / «· tema sencer». S'actualitza amb la selecció.
- Tests de GUI per a l'etiqueta i per a cada prioritat (loop > tram > tema).

**Acceptació**: TAP i Detecta tenen la mateixa semàntica sobre el mateix tram; l'usuari sap sempre què tocarà.

---

## Fase 4 — Marcador de compàs ≠ marcador de secció

**Per què**: avui cada `+` talla també l'estructura; marcar un compàs cada 4 genera desenes de seccions.

Tasques:
- `+` → marcador de **compàs** (talla només el carril de tempo, manté l'offset/compassos enters).
- `Maj+ +` (o la tecla que decideixi l'operador) → marcador de **secció** (talla tempo i estructura).
- El model del marcador guanya un camp `tipus` (`"compas"` | `"seccio"`); `marcadors.csv` i projectes vells carreguen amb `"seccio"` per compatibilitat (o la que decideixi l'operador, documentat).
- A la v3, el flux canvia: cada interval és un tram; les seccions només surten dels marcadors de tipus `seccio` (modifica `seccions_de_ancoratges` i la decisió D3, amb la nota corresponent al `CHANGELOG`).
- Pintar els dos tipus de manera diferent al timeline. Menú contextual per convertir-ne un en l'altre.
- Tests: afegir/convertir/eliminar de cada tipus; un sol desfer; compatibilitat amb projectes vells; regla 13.6 (el marcador viatja amb la frontera) intacta.

**Acceptació**: marcar 30 compassos no crea cap secció; marcar 3 seccions en crea 3.

---

## Fase 5 — Ajust d'un sol BPM i fusió amb tolerància

**Per què**: el jitter humà fragmenta les cançons de tempo constant en trams amb BPMs gairebé iguals.

Tasques:
- Nou mòdul pur (dins `ancoratges.py` o `tempo_ajust.py`): donats els marcadors de compàs consecutius, ajustar **un sol BPM per mínims quadrats** (temps de la línia de compàs en funció de l'índex de compàs) i calcular el **residu** (ms màxim i RMS).
- Si el residu màxim ≤ llindar (per defecte 40 ms, configurable a `limits.py`), el resultat és **un tram únic**; si no, partir **recursivament** en el punt de màxim residu fins que cada tram compleixi o no es pugui partir més (mínim N compassos per tram).
- `fusiona_trams_iguals` guanya paràmetre de **tolerància** (BPM i fronteres) i només s'activa en aquest ajust, mai a l'edició manual.
- Missatge a l'usuari: «Tempo constant: 120,03 BPM (residu màx. 18 ms)» o «3 trams, motiu…».
- Tests amb dades sintètiques: tempo fix amb jitter ±40 ms → 1 tram; canvi de BPM brusc → 2 trams; rubato gradual → es parteix i avisa; compassos que no encaixen → rebuig amb avís.

**Acceptació**: sobre el corpus, les cançons de tempo constant donen 1 tram; les de tempo variable no es fan malbé.

---

## Fase 6 — Mapa sempre present, rubato com a mapa dens i anacrusi (invariant I7)

**Per què**: un acord sense compàs no és interpretable per a un músic. Cap DAW té un mode «sense compassos»; el rubato s'hi representa amb molts canvis de tempo. El mapa ha de ser sempre exportable.

Tasques (només després d'aprovar I7 reformulat a la Fase 2):
- **Mapa sempre present.** Eliminar tota possibilitat d'exportar sense mapa. Si l'usuari no n'ha construït cap, s'usa el del transport (tram únic, tempo constant) i es marca com a **provisional**: indicador visible a la barra d'estat («Mapa provisional: no verificat»), camp `provisional` al `.acproj`, i avís a l'export (diàleg + línia a un `LLEGEIX.txt` dins `mapa_tempo/`). Es treu en el moment que l'usuari accepta o edita el mapa.
- **Nivells com a *estat de treball*, no com a resultat**: 0 = només segons (transitori) · 1 = BPM global + downbeat + compàs · 2 = mapa per trams · 3 = trams amb rubato. Indicador del nivell a la barra d'estat. Els noms de fitxer exportats **sempre** porten compàs (`1-1-1_C.wav`).
- **Rubato com a mapa dens.** El `0/0` passa a ser un estat de «pendent» a la UI. Oferir l'acció **«Converteix el passatge en mapa dens»**: un tram per compàs (o per cop, a elecció de l'usuari) a partir dels marcadors de compàs o dels beats detectats (n = 1 per interval, la mateixa aritmètica que `ancoratges.py`). Les exportacions (CSV, MIDI, MusicXML) **tradueixen els trams `0/0` restants** a un mapa dens si hi ha marcadors i, si no n'hi ha, a un tempo de notació amb avís. ⚠️ Això toca la §13.7 (clips en segons): requereix l'aprovació explícita de l'operador i una nota al `CHANGELOG`.
- **Anacrusi i compàs 1: requisit de primera.** Convenció de compàs 0 / compassos negatius abans del compàs 1, coherent amb la UI, la numeració, el CSV, l'exportació MusicXML (compàs parcial inicial) i l'exportació MIDI (Fase 7). Tests per a: anacrusi d'1 temps, anacrusi de més d'un temps, silenci inicial llarg, silenci final, i anacrusi amb canvi de compàs immediat.
- Eliminar tota dependència implícita «sense mapa no s'exporta» o «sense mapa tot es fa en segons».

**Decisions de l'operador**: nom i lloc de l'indicador de «provisional»; compàs 0 o negatius per a l'anacrusi; si el mapa dens del rubato és per compàs o per cop.

**Acceptació**: no hi ha cap camí que exporti sense mapa; una cançó amb silenci inicial, anacrusi i un passatge rubato exporta compassos numerats coherents a CSV i MusicXML; el mapa provisional sempre es veu i s'avisa.

---

## Fase 7 — Pont amb el DAW: export MIDI de tempo/compàs (i després `.rpp`)

**Per què**: el valor real per al músic és que, en importar l'export al DAW, **la graella del DAW coincideix amb la cançó** i els clips d'acord i d'estructura cauen als compassos correctes. Al roadmap això estava a «Més endavant»; passa a ser camí crític.

Tasques:
- **7.1 · Export MIDI estàndard** (SMF, PPQ 480 o el que decideixi l'operador) amb: pista de **tempo** (un *set tempo* per cada tram del mapa, a la posició en ticks derivada dels segons), **compàs** (*time signature* a cada canvi), i opcionalment **marcadors** (*marker/cue*) per a acords i seccions amb el seu nom. Escriptor SMF **propi en Python pur** (sense dependències noves; format senzill). Comprovar que el BPM del model és «per negra» (així ho indica `bpm_de_n`: `n·num·(4/den)·60/Δt`) i que el *set tempo* es calcula coherentment per a compassos amb den ≠ 4 (6/8, 12/8…).
- **Anacrusi i silenci inicial**: estratègia d'import a validar en un DAW real (per exemple, un primer compàs curt amb el seu *time signature* propi, o un desplaçament documentat). **No assumir**: deixar un fitxer de prova i demanar a l'operador que l'importi a REAPER i a l'altre DAW que faci servir.
- **Integració a l'export**: `exporta_total` desa `mapa_tempo/mapa_tempo.mid` (regla 12, paritat d'exportació); entrada de menú «Exporta ▸ Mapa de tempo (MIDI)…» per fer-ho sol.
- **Test d'anada i tornada**: llegir el `.mid` generat amb un lector mínim i comprovar que les línies de compàs reconstruïdes coincideixen amb `ancoratges.linies_de_compas` dins de ±1 ms, per a tempo fix, canvi de BPM, canvi de compàs i rubato dens.
- **7.2 · Projecte REAPER (`.rpp`)** — després de validar el MIDI i només amb l'OK de l'operador: format de text. Genera un projecte amb l'enveloupe de tempo, els *time signature*, i els clips WAV d'acords i d'estructura **ja col·locats** a les seves posicions. Mateix test d'anada i tornada. Altres DAWs (`.als`, Logic…) queden fora d'aquest pla.
- **7.3 · Plantilles per DAW**: només si 7.1 i 7.2 funcionen; fora de l'abast d'aquest pla.

**Decisions de l'operador**: PPQ, quins DAWs vol validar, si els marcadors de MIDI porten acords, seccions o tots dos, i si es fa 7.2.

**Acceptació**: importat a REAPER (i al segon DAW triat), el regle de compassos del `.mid` coincideix amb la cançó, i els clips WAV exportats cauen als compassos amb el nom corresponent. El test d'anada i tornada és verd.

---

## Fase 8 — Unificar marcadors i v3; netejar menús i regles

Tasques:
- **Un sol model humà**: els marcadors de compàs (Fase 4) són l'única font d'ancoratges. La v3 passa a ser la **pantalla de revisió/generació** que els llegeix i hi mostra els estats (ok/nota/sospitós/no encaixa), no un camí paral·lel. Eliminar el codi duplicat.
- Retirar la **v2** (`_analisi_guitat`, `DialegGuiaDownbeat`, `DialegGuiaBpm`, `FilGuiaBpm` i els seus tests) i el comportament enganyós del botó «Anàlisi guiat». El botó obre directament el flux unificat; la guia informativa passa a «Ajuda».
- Reduir el menú *Analitza*: fusionar «BPM a partir dels marcadors» i «Ajusta BPMs per trams» en una sola acció («Ajusta el mapa als marcadors»), amb la Fase 5 per sota. Treure «Detecta el mapa de tempo (per beats)» o fusionar-lo amb «per trams» si fan el mateix (per verificar).
- Aplicar a `REGLES_DE_LA_APP.md` la nova versió **només si l'operador ho ha aprovat**, i moure 13.5–13.8 a `docs/ESPECIFICACIO_TEMPO.md` i la paritat a `docs/PARITAT.md`. Actualitzar tots els enllaços entre documents i el recompte de versions (README diu v0.8.0, ROADMAP v0.7.0).

**Acceptació**: un sol camí per construir el mapa humà; cap codi mort; documentació coherent.

---

## Fase 9 — Millorar el motor de detecció (amb mesures)

Tasques:
- **Puntuació de downbeat amb acords**: aprofitar que els canvis d'acord de Chordino cauen sovint en temps forts. Donats candidats de downbeat i compàs del tracker, puntuar-los per la coincidència amb els canvis d'acord i triar o reordenar. Mesurar sobre el corpus; adoptar només si millora la línia base.
- **Avaluar motors alternatius** (madmom, Beat This! o similar) amb l'script de la Fase 0 (mètrica d'alineació de la graella), **un per un i en una branca**: comprovar llicència (models inclosos), compatibilitat amb `numpy<2`, funcionament sense AVX al Q9400, pes de l'AppImage/portable i temps d'execució. Informe amb taula comparativa; **no integrar res** sense l'OK de l'operador.
- Qualsevol motor nou és **opcional** i s'oculta darrere la mateixa interfície de detecció (`pipeline.detecta_beats`/`detecta_bpm`), perquè el tracker de Vamp continuï de reserva.

**Acceptació**: informe amb mètriques sobre el corpus (incloent-hi l'alineació de la graella a tota la cançó); cap regressió a la línia base per defecte.

> ⚠️ **Camí crític**: sense un mapa que quadri amb la cançó, el pont amb el DAW (Fase 7) no serveix. Si l'informe mostra que el motor actual no arriba a un nivell acceptable, aquesta fase passa al davant de la 8 i la 10.

---

## Fase 10 — Flux del 90 %: proposta, escolta, acceptació

Tasques:
- En obrir una cançó, l'app **proposa** BPM global, downbeat i compàs (nivell 1) i **activa el metrònom** sobre l'àudio. Barra clara: «Accepta» / «Ajusta». No hi ha opció «sense graella»: si l'usuari no accepta, el mapa queda **provisional** (Fase 6).
- «Ajusta» obre el flux de marcadors (només cal marcar on es desvia el metrònom); amb 2 marcadors llunyans s'ajusta el BPM global (Fase 5).
- **Confiança al timeline**: pintar els trams segons la desviació/estat que ja calcula `ancoratges.py` (ok / nota / sospitós), amb llegenda.
- Text de benvinguda del «mode fàcil» (apuntat al roadmap) reescrit per a aquest flux.
- Test de GUI de punta a punta amb una WAV sintètica: obrir → proposta → accepta → analitza → exporta, i un segon cas amb un marcador de correcció. El final del flux inclou l'acció **«Exporta al DAW»** (paquet de WAVs + `mapa_tempo.mid`, Fase 7).

**Acceptació**: el cas habitual (tempo fix) es resol sense obrir cap diàleg avançat.

---

## Fase 11 — Congelació i higiene

- Congelar funcionalitats laterals (afinador, `Gt_ALL_Chords_app`, etc.) fins que les fases 1–10 siguin estables; deixar-ho escrit al ROADMAP.
- Higiene dels tests: esborrar els `tempdir` (`addCleanup(shutil.rmtree, …)` o helper comú).
- Passar el fuzzer i l'avaluació del corpus al CI com a comprovació no bloquejant (informa de regressions).
- Actualitzar `CHANGELOG`, `README` i `ROADMAP` amb l'estat final.

---


## Resum d'ordre i dependències

| Fase | Depèn de | Necessita decisió de l'operador |
|---|---|---|
| 0 Base i corpus (amb alineació de graella) | — | corpus d'àudio |
| 1 Constants i validació | 0 | — |
| 2 Fuzzer i regles | 1 | **aprovar regles (I7 reformulat)** |
| 3 TAP i destí | 1 | — |
| 4 Compàs vs secció | 1, 2 | tecla i compatibilitat de projectes vells |
| 5 Ajust d'un BPM | 4 | llindar de residu |
| 6 Mapa sempre present, rubato dens, anacrusi | 2 (I7), 5 | **indicador «provisional» · anacrusi · modificar §13.7** |
| 7 Pont amb el DAW (MIDI, `.rpp`) | 5, 6 | PPQ · DAWs a validar · fer `.rpp` |
| 8 Unificació i neteja | 4, 5, 6 | **aplicar regles v2** |
| 9 Motor de detecció — **camí crític** | 0 | adoptar un motor nou |
| 10 Flux del 90 % | 5, 6, 7, 9 | — |
| 11 Congelació | tot | — |

> **Nota d'ordre**: les fases 1–5 no canvien. Si les mesures de la Fase 0 mostren que el mapa automàtic no és prou bo, la Fase 9 s'avança (pot córrer en paral·lel a les 3–5). La Fase 7.1 pot començar tan bon punt la 6 deixi de produir mapes amb `0/0` sense traduir.
