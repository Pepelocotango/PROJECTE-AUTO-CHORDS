# Decisions de disseny — rubato i doble graella

> **SUBPLÀ PRIORITARI (2026-11-02).** S'ha d'executar **abans de continuar**
> amb el `PLA_SIMPLIFICACIO_TEMPO.md` (fases 7, 10 i 12). No començar cap altra
> fase del pla de simplificació fins que aquest subplà estiga complet i
> verificat.

> **Estat:** en discussió (2026-11-02). **No implementat.**
> Document viu per no perdre cap decisió durant la conversa. Cada decisió
> s'afig ací quan l'operador la confirma. Les preguntes obertes queden al final.

## Objectiu

Representar passatges de **temps lliure (rubato)** sense falsejar el model:
els segons són invariables; la graella mètrica és una interpretació derivada
per llegir, numerar compassos i exportar.

## Decisions preses

| # | Decisió | Data |
|---|---------|------|
| 1 | **Dues graelles simultànies**: a dalt, BPM/compàs; a baix, temps (segons) sempre visible. La de temps només canvia si s'edita la WAV de treball (retallar, afegir silenci…). | 2026-11-02 |
| 2 | El **rubato és una secció declarada per l'usuari** (inici, fi, o al mig). Té inici i fi en **segons invariables**. | 2026-11-02 |
| 3 | L'app assigna al rubato un **BPM i un compàs derivats** a partir del clip mètric de referència, perquè la numeració i l'exportació quadren. | 2026-11-02 |
| 4 | **Cas B (rubato al mig)**: la referència automàtica és el clip mètric **anterior**. | 2026-11-02 |
| 5 | **Compassos llegibles**: es prefereixen compassos estàndard amb un parcial si cal (`3×4/4 + 1×3/4`) abans que un compàs únic estrany (`15/4`). | 2026-11-02 |
| 6 | **Metrònom**: no s'apaga sol; continua si està activat. Dins del rubato clica al **BPM derivat** (decisió 12). | 2026-11-02 |
| 7 | Al carril de BPM/Compàs hi ha d'haver **dos tipus de clips diferenciats**: normals i rubato/lliures. Tots dos han de mostrar BPM i un compàs `x/x` amb numerador enter. | 2026-11-02 |
| 8 | El rubato pot ser **inicial, final o al mig** de la cançó. | 2026-11-02 |
| 9 | **Model B**: el model guarda el **BPM i el compàs derivats** del rubato, amb un camp `tipus` (`normal`/`rubato`). Els valors derivats es recalculen quan canvia el veí o la durada. **Sense retrocompatibilitat** amb el `0/0` antic. | 2026-11-02 |
| 10 | **Seqüència de compassos dins del clip rubato**: un sol BPM i una seqüència de compassos (p. ex. `4/4×3 + 3/4`), no un sol compàs forçat ni subtrams separats. Els clips normals continuen tenint un sol compàs. | 2026-11-02 |
| 11 | **Abast inicial = D**: només **blocs lliures** (sense corba interna). Un rubato té un sol BPM derivat i una seqüència de compassos. Els ritardandos/accelerandos amb subtrams o rampa queden per a una fase posterior; el model ha de deixar-hi lloc. | 2026-11-02 |
| 12 | **Metrònom dins del rubato = A**: clica al **BPM derivat** del rubato. Com que eixe BPM fa que el rubato acabe a la frontera, l'últim clic coincidix amb el clip mètric següent. És una guia, no la veritat de la interpretació. | 2026-11-02 |
| 13 | **Projectes vells amb `0/0` = A**: es **rebutgen** amb un error clar («projecte anterior al model de rubato; no suportat»). No hi ha migració ni lectura tolerant d'eixe estat. | 2026-11-02 |
| 14 | **Format unificat = C**: `tempo.csv` + `compas.csv` es fusionen en un sol **`mapa_tempo.csv`** amb `inici,fi,bpm,tipus,compassos`. L'exportació `mapa_tempo/` passa a un sol fitxer. Caldrà actualitzar la regla 12 i el `CHANGELOG` en implementar-ho. | 2026-11-02 |
| 15 | **Projectes actuals amb `tempo.csv` + `compas.csv` = A**: es **rebutgen** també, sense conversió. La retrocompatibilitat no és prioritat (política global, vegeu `AGENTS.md`). | 2026-11-02 |
| 16 | **Rubato no representable = A**: si no hi ha cap solució dins de BPM 30–350 i compassos estàndard, es **rebutja** la conversió a rubato amb un avís clar. No s'inventen BPM ni compassos fora del contracte. | 2026-11-02 |
| 17 | **Rubato inicial = A**: el rubato ocupa **compassos negatius** (pre-roll) i el primer clip mètric és `1.1`. L'offset és l'inici del primer clip mètric; si es mou el fi del rubato, es mou el compàs 1. | 2026-11-02 |
| 18 | **Flux d'usuari = D**: es pot crear un rubato **sobre un rang** (*Marca com a rubato*) i **convertir un clip existent** (*Converteix a rubato*). Totes dues portes passen pel mateix despatx d'edició. | 2026-11-02 |
| 19 | **Sintaxi de dades = ASCII**: `4/4*3+3/4` (sense espais; `*` repeticions, `+` seqüència; `4/4` = un compàs). La **UI** el presenta com `4/4 × 3 + 3/4` i pot afegir una forma humana («3 compassos de 4/4 + 1 de 3/4»). Dades i presentació són coses distintes. | 2026-11-02 |
| 20 | **Algorisme de compassos = A**: referència = compàs del clip mètric anterior; si no dividix els pulsos, llista tancada d'estàndards (`2/4`, `3/4`, `4/4`, `5/4`, `6/4`, `7/4`, `3/8`, `6/8`, `9/8`, `12/8`). Es prefereix **fidelitat al compàs de referència** (decisió 27); en cas d'empat, menys compassos/segments; parcial final permès; si no hi ha solució, es rebutja (decisió 16). | 2026-11-02 |
| 21 | **Fronteres del rubato = A**: les vores són compartides amb el veí, com la resta del mapa. Moure una vora mou la frontera, el veí amb compàs conserva els compassos i re-tempa, i el rubato recalcula BPM/seqüència. Un sol desfer. | 2026-11-02 |
| 22 | **Presentació a la UI = A**: el rubato sempre és visible a la graella mètrica amb la seqüència derivada (compassos negatius si és inicial), color/patró distint, etiqueta `RUBATO · BPM · compassos` i indicador «derivat». La graella de temps continua sempre visible. | 2026-11-02 |
| 23 | **Etiquetatge de l'exportació = A**: `tipus=rubato` al `mapa_tempo.csv`, `mapa_tempo/AVIS_APROXIMACIO.txt` amb la llista de trams i la referència, i text visible «Rubato — graella aproximada» al MusicXML. | 2026-11-02 |
| 24 | **Convertir rubato → normal = A**: si el rubato té una seqüència de diversos compassos, es **parteix en clips normals, un per segment** (`4/4*3+3/4` → `4/4*3` + `3/4`), amb el mateix BPM derivat. La graella no canvia. | 2026-11-02 |
| 25 | **Rubatos adjacents = A**: es **fusionen** en un sol rubato (un BPM i una seqüència). La frontera comuna desapareix; un sol desfer. | 2026-11-02 |
| 26 | **Denominadors = A**: no es barregen dins d'un rubato. La seqüència usa la mateixa família que el compàs de referència: `x/4` → `2/4`, `3/4`, `4/4`, `5/4`, `6/4`, `7/4`; `x/8` → `3/8`, `6/8`, `9/8`, `12/8`. El BPM continua sent inequívoc. | 2026-11-02 |
| 27 | **Prioritat de l'algorisme = A**: repetir el compàs de referència tant com es puga; el reste, amb un compàs estàndard del mateix denominador o un parcial. Màxim **4 segments**; si no hi ha solució, provar altres estàndards; si tampoc, rebutjar. | 2026-11-02 |
| 28 | **Nombre de pulsos = A**: `N = round(D*R/60)`, mínim 1; `BPM = N*60/D`. Si cau fora de 30–350, es proven els enters veïns dins de la banda i es tria el BPM més pròxim a `R`; si no n'hi ha cap, es rebutja. | 2026-11-02 |
| 29 | **Format del projecte = A**: `FORMAT = 3`. Qualsevol `.acproj` anterior es **rebutja** amb un error clar. És conseqüència directa de la política de no retrocompatibilitat; **no es torna a preguntar**. | 2026-11-02 |

## Model B — regles de ferro

- Els **segons són la veritat**; el BPM/compàs del rubato és una **vista
  materialitzada** (una caché) que sempre s'ha de poder recalcular.
- Un sol punt central recalcula tots els rubatos: en carregar el projecte i
  després de qualsevol mutació que canvie segons, veïns o durada.
- El BPM/compàs derivat és **de només lectura** per a l'usuari. No s'edita com
  si fóra un tempo detectat.
- Si el valor guardat no coincidix amb el recalculat, es repara amb avís i
  traça al registre (mai en silenci).
- Una mutació continua sent **un sol desfer**: el recalcul no genera passos
  extra.
- **Sense retrocompatibilitat**: els projectes vells amb `0/0` **i** els que
  tenen `tempo.csv` + `compas.csv` es **rebutgen** amb un error clar; no es
  migren ni es lligen. Política global: `AGENTS.md`.
- El model ha de distingir sempre `tipus=normal` de `tipus=rubato`; un rubato
  no es pot confondre amb un tempo detectat.
- Un clip rubato té **un sol BPM** i una **seqüència de compassos** que cobreix
  exactament la seua durada. Els compassos de la seqüència són estàndard i el
  darrer pot ser parcial (`4/4×3 + 3/4`). Els clips normals mantenen un sol
  compàs.
- La seqüència és part de la **vista derivada**: si canvia la durada o el veí,
  es torna a calcular sencera.
- **Primera fase**: el rubato és un bloc lliure amb un sol BPM. No es modela
  cap corba interna (ritardando/accelerando) ni subtrams. El model ha de
  permetre afegir-ho més endavant sense trencar el format ni les regles.
- **Model unificat**: `mapa_tempo.csv` amb `inici,fi,bpm,tipus,compassos`.
  Desapareixen `tempo.csv` i `compas.csv` com a fitxers del model. L'exportació
  `mapa_tempo/` tindrà eixe únic fitxer; la regla 12 s'ha d'actualitzar amb
  aprovació explícita.
- **Dades vs presentació**: al fitxer, `compassos` és ASCII i compacte
  (`4/4*3+3/4`); a la UI es mostra amb `×` i espais (`4/4 × 3 + 3/4`) i, si
  cal, amb la forma humana. El parser només accepta la forma canònica ASCII.
- **Tria de la seqüència**: referència = compàs mètric anterior; després,
  fidelitat al compàs de referència; en cas d'empat, menys compassos/segments;
  parcial final permès; si no hi ha solució, es rebutja.
- **Fórmula (proposta)**: `N_ideal = D * R / 60` en pulsos del denominador de
  referència; `N = round(N_ideal)`, mínim 1; `BPM = N * 60 / D`. Si el BPM cau
  fora de 30–350, es proven els enters veïns dins de la banda i es tria el BPM
  més pròxim a `R`; si no n'hi ha cap, es rebutja. La seqüència ha de sumar
  exactament `N` pulsos.

## Regles d'or — s'apliquen a tothom

El rubato **no és una excepció** a les regles d'or ni al §13. Els clips de
rubato compleixen igualment:

- ordre, contigüitat i **cobertura total** (regles 1, 2 i 4);
- **temps vàlids** (regla 8);
- **paritat d'edició i exportació** (regles 11 i 12);
- **BPM 30–350** i compassos dins del contracte;
- **un sol desfer** per mutació;
- els segons són la veritat; la graella en deriva.

## Model final (resum per a implementació)

- **`.acproj` FORMAT = 3**. Qualsevol versió anterior es rebutja amb error clar.
- **Model**: `mapa_tempo.csv` amb `inici,fi,bpm,tipus,compassos`.
  - `tipus`: `normal` o `rubato`.
  - `compassos`: ASCII `4/4` o `4/4*3+3/4`; la UI mostra `4/4 × 3 + 3/4`.
- **Clips normals**: un sol compàs; BPM i compàs editables.
- **Clips rubato**: un sol BPM + una seqüència de compassos; els valors són
  **derivats**, de només lectura i es recalculen en un sol punt.
- **Referència**: clip mètric anterior; si no n'hi ha, el següent; si tampoc,
  el transport.
- **Família de denominador**: la del compàs de referència; no es barregen
  denominadors dins d'un rubato.
- **Seqüència**: compàs de referència sempre que es puga; resta amb estàndard
  o parcial; màxim **4 segments**; si no hi ha solució, es rebutja.
- **Pulsos**: `N = round(D*R/60)`, mínim 1; `BPM = N*60/D`; si cau fora de
  30–350, es proven veïns dins de la banda; si no, es rebutja.
- **Fronteres compartides**: moure una vora mou la frontera; el veí amb compàs
  conserva els compassos i re-tempa; un sol desfer.
- **Adjacents**: es fusionen. **Convertir a normal**: es parteix per segment.
- **UI**: dues graelles (mètrica i temps); rubato visible amb estil «derivat»;
  pre-roll negatiu si és inicial.
- **Export**: `mapa_tempo/mapa_tempo.csv` + `AVIS_APROXIMACIO.txt`; text
  «Rubato — graella aproximada» al MusicXML; la regla 12 s'actualitza.
- **Regles d'or i §13**: s'apliquen a tothom, rubato inclòs.

### Límit de compassos (resolt tècnicament)

No hi ha un límit pràctic de compassos: la seqüència s'escriu en run-length
(`4/4*75`) i no ocupa espai. El límit és de **4 segments** de compàs. Per
seguretat interna, cap rubato no pot superar els **999 compassos**; si els
supera, es rebutja amb avís.

## Pla d'implementació proposat

1. **Motor pur de derivació** (`app/rubato.py` o similar): referència, `N`,
   BPM, cerca de seqüència, validació i rebuig. Funcions pures i tests amb els
   casos A/B/C, rubatos curts/llargs, fora de banda, denominadors i segments.
2. **Model i format**: lector/escriptor de `mapa_tempo.csv`, `FORMAT = 3`,
   rebuig de projectes vells, integració a `projecte`/`pipeline`/`tempo_map`,
   tests.
3. **Visor i timeline**: dues graelles, tipus rubato, crear/convertir,
   fronteres, etiquetes derivades, undo, tests de GUI.
4. **Exportació**: `mapa_tempo/` unificat, `AVIS_APROXIMACIO.txt`, text al
   MusicXML, actualització de la regla 12, tests.
5. **Docs i CI**: regles, docs, `CHANGELOG`, suite i `pyflakes` verds.

## Pregunta actual

**Voleu que comence pel punt 1, el motor pur de derivació, sense tocar encara
la UI ni el format del projecte?**
