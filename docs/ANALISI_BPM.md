# Analitza BPM — detecció de beats i downbeats

> **Estat:** implementació inicial 2026-11-04 (fase 10).
> **Abast:** detecció de BPM, beats i downbeats com a **capa de diagnòstic**
> sobre l'ona. No reanalitza acords ni estructura i no canvia el model de
> tempo/compàs sense una acció explícita.

## Separació d'accions

- **Analitza l'àudio**: només **acords + estructura**. El BPM ja no forma
  part d'este flux; la pestanya BPM no s'oferix en este diàleg.
- **Analitza BPM…** (`F7`): obri un diàleg propi amb motor i sensibilitat.
  Té dos modes:
  - **Només beats** (per defecte): retorna únicament la seqüència de polsos;
    **no** infereix BPM, compàs ni downbeats, ni agrupa en compassos.
  - **BPM + beats + downbeats**: afig el BPM i els downbeats que el motor
    puga proporcionar.

La separació evita que una reanàlisi d'acords destruïsca una corba de tempo
feta a mà, i que una prova de BPM òmpliga el model d'acords.

## Mode «només beats»

És el mode que respon a la guia tècnica: separar **onset → beat → downbeat** i
no inventar la fase mètrica si no es demana.

- **Nostre**: igualment calcula un període intern per poder seguir el pols,
  però **no l’exposa** ni l’aplica al transport; no deriva `beats_a_trams` ni
  compassos.
- **QM**: usa `qm-tempotracker:beats`, no `qm-barbeattracker:bars`; no rep
  `bpb` i no retorna bars.
- La sortida és només `beats`; `bpm=None` i `downbeats=[]`.
- Les línies resultants són només de beats.

El fet que el tracker use un període intern no vol dir que estiga endevinant
el compàs: el període és una condició del beat tracking, però no es presenta
com a BPM ni com a graella.

## Motors

| Motor | Origen | Sensibilitat |
|---|---|---|
| **Nostre** | `app/tempo.py`: envolupant d'onsets + DP d'Ellis | `tightness`: 100 (estable) → 10 (flexible) |
| **Queen Mary** | `qm-barbeattracker` via `vamp_host_local` | `alpha`: 0.99 (estable) → 0.10 (flexible) |

El valor de sensibilitat és una **comoditat d'usuari** 0–100, no una mesura
comparable entre motors. Cada motor té la seua escala interna:

```text
0   = estable / estricte
50  = equilibrada
100 = sensible / flexible
```

Els paràmetres QM es passen al plugin amb la mateixa interfície de
`vamp_host_local`; no hi ha un motor nou ni una dependència nova.

## Què es guarda

- Les llistes de beats i downbeats es guarden dins el `.acproj` com a
  `analisi_beats` (caché de diagnòstic, no model).
- Les línies es poden buidar o tornar a detectar sense tocar cap CSV.
- Si el projecte té `analisi_beats`, es tornen a pintar en obrir-lo.
- El BPM detectat només s'aplica al transport si l'usuari ho demana i el
  mapa és d'un sol tram; en mapes amb rubato o trams múltiples no es
  reescriu res automàticament.

## Ajusta la graella als beats QM

Després del play, l’acció **Ajusta la graella als beats QM…** fa:

1. agafa els beats/downbeats de l’última anàlisi;
2. busca el bar (si n’hi ha) o el beat més pròxim a cada marcador de compàs;
3. només mou els marcadors que cauen dins de la tolerància (per defecte
   120 ms);
4. els marcadors sense objectiu queden intactes i es marquen com a dubtosos;
5. mou la secció que encara coincidia amb el marcador; si ja s’havia editat a
   mà, no la toca;
6. recalcula el BPM amb els marcadors resultants;
7. aplica el mapa amb **un sol desfer**.

No obri cap diàleg mentre sona: la comprovació i la tolerància es demanen
després d’aturar la reproducció.

`+` continua creant **inici de compàs + inici de secció**. La secció es pot
editar després sense que desaparega l’ancoratge de compàs.

El selector **Snap → Beats QM** fa que el cursor i els clips s'encaixen a les
línies de beats de QM; amb el Snap actiu, el `+` també s'hi encaixa abans de
crear el marcador. Si no hi ha cap beat a prop (120 ms), el `+` conserva el
temps del cursor.

Els talls que no han trobat cap beat dins de la tolerància es mostren en un
**diàleg no modal** de revisió; doble clic porta el cursor al tall i el botó
**Snap al candidat** aplica eixe tall individualment. No bloquegen la
reproducció ni l’edició.

Per canviar el metre d’un tram, col·loca el cursor prop d’un marcador i usa
**Compàs del marcador…**. El canvi es fa sobre el clip de tempo que comença en
eixe marcador; el model admet metres diferents per tram.

## Línies sobre l'ona

- **Beats**: línies fines.
- **Downbeats**: línies més gruixudes i grogues.
- Són una capa de diagnòstic; no són clips ni modifiquen el snap.
- La graella de compàs existent continua sent la referència d'edició.

## Límits coneguts

- QM pot retornar el BPM en la unitat del seu beat intern (per exemple, negra
  amb punt en 12/8); no s'ha de confondre amb el BPM en negres del model.
- El motor QM no sempre retorna downbeats utilitzables; si no en retorna, es
  mostren només els beats.
- El motor «nostre» deriva els downbeats de la graella de beats i el metre
  actual; no és un detector de fase mètrica independent.
- La sensibilitat no és comparable entre motors: un 70 de QM i un 70 de
  «nostre» poden produir resultats molt diferents.
- L'acció encara no substituïx el flux d'ancoratges manuals; les línies són
  una eina de diagnòstic i de correcció, no la veritat final.

## Relació amb els ancoratges

La detecció proposa. L'usuari ha de poder confirmar o corregir els inicis de
compàs amb ancoratges (vegeu `ANALISI_GUIAT_v3.md` i `MARCADORS.md`). El BPM
final ha de ser derivat dels ancoratges, no imposat pel detector.

## Prova

- Tests del motor i de la sensibilitat: `tests/test_beats.py`.
- Per comparar motors, usar el corpus i les mètriques de beat/downbeat de
  `eines/avalua_tempo.py`.
