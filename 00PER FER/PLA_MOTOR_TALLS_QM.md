# Pla — motor de talls amb Snap QM

**Data:** 2026-11-14  
**Estat:** implementat (2026-11-14); pendents a §18  
**Abast:** talls de tempo/compàs amb Snap QM (`+`, Enter, Afegeix/Parteix aquí, Partir per la meitat i Parteix A–B).

> Document de treball local. No és font de veritat del producte; el contracte
> continua sent `docs/REGLES_DE_LA_APP.md`.

---

## 1. Objectiu

Quan el Snap està en **Beats QM**, el tall no ha de limitar-se a partir el clip
i forçar `N` enter canviant el BPM. Ha de:

1. comptar els beats de cada meitat;
2. convertir-los a negres;
3. respectar la referència de compàs (Ref. recalc i compàs local);
4. proposar la interpretació més musical en BPM, `x/x` i `N`;
5. preguntar a l'usuari quan hi ha més d'una interpretació aplicable;
6. aplicar els clips resultants de manera atòmica.

Fora de Snap QM, el comportament actual es manté.

---

## 2. Estat previ rellevant

- `+` i Enter ja comparteixen `_talla()` → `_parteix_tempo_nou()`.
- `+` afig el tall d'estructura; Enter només tempo.
- El primer pas actual (`parteix_tram_marcador(..., recalculca=False)`)
  normalitza `N` canviant el BPM abans d'arribar al motor de beats.
- El recalcul guiat amb beats només s'executa com a fallback.
- `_parteix_tempo_nou` no passa `ref_base`, `avisos`, `unitats` ni
  `classificacions`.
- El `+` del teclat numèric ja està corregit (canvi local, sense commit).

---

## 3. Font de beats

### 3.1 Amb QM

- Si hi ha beats QM disponibles, **manen els QM**.
- Es compten dins de cada meitat.
- El beat exactament al punt de tall **pertany a la dreta**.
- No s'usen downbeats.

### 3.2 Sense QM

- Es compten els polsos de **metrònom del tram actual** del mapa.
- Si el costat travessa trams amb unitats distintes, es compta per trams i se
  sumen les conversions.

### 3.3 Conversió a negres

Cada pols es convertix a negres segons `beat_unit`:

| Unitat | Negres per pols |
|---|---:|
| negra | 1 |
| negra amb punt | 1,5 |
| corxera | 0,5 |
| semicorxera | 0,25 |
| blanca | 2 |

Variable de treball:

```text
Bq = suma de polsos × factor d'unitat
```

`Bq` pot ser fraccionari (per exemple, 7/8 amb corxera: 7 × 0,5 = 3,5 negres).
Els càlculs de compassos han de treballar amb eixe valor exacte, no amb enters
forçats.

### 3.4 Tempo intern, unitat i canvi de compàs

- El **BPM intern** de l'app i del MIDI és sempre en **negres/minut**.
- `beat_unit` és la unitat de presentació/comptatge de cada tram:
  - `6/8` → `negra_punt` per defecte;
  - `4/4` → `negra`;
  - la unitat es pot canviar manualment per tram.
- Exemple d'equivalència:
  - `6/8` a **80 negres amb punt/min** = **120 negres/min** internes.
  - `4/4` a **120 negres/min** = **120 negres/min** internes.
  - És el mateix pols de negra: el MIDI pot portar 120 en els dos trams i
    només canviar la Time Signature.
- El motor **no infereix modulació mètrica** ni decideix si el canvi és
  `♩ = ♩`, `♩. = ♩` o una altra relació.
- Si un candidat canvia de compàs i la relació de tempo no està definida,
  el tall **no s'aplica automàticament**: l'usuari l'ha de definir manualment
  fora del motor (editor de tempo o diàleg previ). El motor pot mostrar un
  avís i reprendre després.
- MIDI:
  - `Set Tempo` sempre en negres/minut;
  - `Time Signature` per tram;
  - `beat_unit` no és un camp estàndard; com a molt s'exporta al `cc` del
    Time Signature (24 negra, 36 negra amb punt, 12 corxera…);
  - molts DAWs ignoren el `cc` i mostren el tempo segons la seua configuració
    (120 negres o 80 negres amb punt). El compàs sí que el respecten.

---

## 4. Referència i bases

Sempre hi ha una Ref. recalc:

- `BPM_ref`
- `compàs_ref = num_ref/den_ref`

Cada costat té dos bases possibles:

1. el **compàs local** del clip original;
2. el **compàs de la Ref.**

Si coincidixen, n'hi ha una de sola. **No hi ha prioritat entre Ref. i local.**
Les dos famílies de candidats es barregen en una sola llista ordenada.

---

## 5. Generació de candidats

Per a cada costat, amb `Bq` negres:

### 5.1 Base pura

Si `Bq` és múltiple de la durada en negres del compàs base:

```text
N = Bq / (num_base × 4 / den_base)
```

- Una sola base pura exacta → **s'aplica directament**.
- Dues bases pures exactes i diferents → **diàleg entre les dos**.
- Si hi ha pura, **no** es proposen alternatives exòtiques.

### 5.2 Base + un compàs extrany

Un clip amb `N` compassos de la base i un segon clip amb **un sol compàs
extrany**:

```text
Bq = N × bar_quarters(base) + bar_quarters(extrany)
```

Condicions:

- `N >= 0`;
- l'extrany és exactament un compàs, no una repetició;
- `1 <= num_extrany <= 12`;
- denominador preferent: el mateix que la base;
- **a més**, s'afigen sempre les opcions amb **denominador 4** que encaixen,
  encara que ja hi haja candidats amb el mateix denominador. Només es permet
  canviar a denominador 4, no a 2, 16 ni altres;
- les opcions de denominador 4 han de ser `base + 1 compàs /4`; no es permet
  `/4 + /8` sense cap clip de la base;
- l'extrany va al final per defecte;
- també s'ha de generar la variant amb l'extrany al principi.
- `4/8` i `2/4` són duracions equivalents, però es mantenen com a **opcions
  separades** (igual que `10/8` i `5/4`). No es dedupliquen per duració.

### 5.3 Secció sencera extranya

Un sol clip amb `N` compassos d'un compàs extrany:

```text
Bq = N × bar_quarters(extrany)
```

- `N >= 1`;
- `1 <= num_extrany <= 12`;
- denominador preferent: el mateix que la base;
- el canvi a denominador 4 es fa només per la via `base + 1 compàs /4`
  (secció 5.2), no com a secció sencera;
- altres denominadors no s'afegeixen.

### 5.4 Límits

- Màxim **2 clips per costat**.
- Màxim **4 clips en total**.
- **No** es permeten dos compassos extranys diferents dins del mateix costat.
- **No** s'ajusten beats (fora K±1).
- **No** es contempla un residu arbitrari: tot clip és un compàs sencer o un
  grup de compassos sencers.

---

## 6. Filtres d'aplicabilitat

Un candidat només és aplicable si:

- la suma de compassos dona exactament `Bq`;
- `N` és enter i `N >= 1`;
- `num` és enter, `1 <= num <= 12`;
- `den` és 2, 4, 8 o 16;
- el BPM resultant de cada clip és dins 30–350;
- cada clip respecta la durada mínima vigent;
- no se superen 2 clips per costat;
- no hi ha dos compassos extranys diferents;
- les opcions amb denominador 4 s'afigen sempre que encaixen, encara que hi
  haja opcions del mateix denominador;
- al diàleg es reserven com a mínim **2 opcions amb denominador 4** per costat
  si n'hi ha;
- `4/8` i `2/4`, i `10/8` i `5/4`, es mostren com a opcions separades;
- `1/4` (i compassos molt diminuts) es filtra si hi ha una alternativa.
  - S'accepta `1/4` només si el costat sencer fa menys d'un compàs de la base
    o si no hi ha cap altra opció.

Els candidats duplicats exactes (mateixos clips, BPM, compàs i `N`)
s'eliminen. Les equivalències de duració amb **notació diferent** (`4/8` vs
`2/4`, `10/8` vs `5/4`) **no** es dedupliquen: es mostren com a opcions
separades.

---

## 7. BPM i fronteres internes

### 7.1 Amb beats

- Les fronteres internes cauen als **temps reals dels beats/polsos**.
- El beat del tall i el beat de cada frontera interna pertanyen al clip de la
  dreta.
- Cada clip deriva el seu BPM:

```text
BPM_clip = 60 × Bq_clip / durada_clip
```

- Els dos clips poden tindre BPM lleugerament diferent si els beats QM són
  irregulars.
- El BPM resultant no es força a la Ref.

### 7.2 Sense cap beat

Fallback:

```text
N = max(1, round(durada / durada_compàs_ref))
BPM = 60 × N × bar_quarters(compàs_ref) / durada
```

- Un sol clip de la Ref.
- Si el BPM resultant ix de 30–350, es rebutja i s'avisa.
- No es fa cap descomposició per durada en este cas.

---

## 8. Ordre de les opcions

Ordenació lexicogràfica:

1. menys compassos extranys (0 > 1 > N);
2. més compassos de la base;
3. menys clips;
4. compàs extrany més proper a la base;
5. evitar compassos massa curts;
6. a igualtat, es prefereix un denominador 4 comú (`2/4`, `3/4`, `4/4`,
   `5/4`…) abans que un `/8` equivalent, però les dos notacions es mostren.

Si hi ha empat, es manté l'orde estable de generació.

---

## 9. Diàleg

### 9.1 Quan s'obri

- Si un costat té **2 o més** candidats aplicables.
- Si un costat només té **1**, s'aplica directament i s'informa al log.
- Si un costat té base pura única, s'aplica directament.
- Si les dos bases donen pures diferents, es pregunta entre les dos.
- Si no hi ha cap candidat exacte en un costat, **no es fa res** i s'avisa.

### 9.2 Format

- **Un sol diàleg conjunt** per als dos costats.
- Dues columnes: esquerra i dreta.
- Màxim **6 opcions per costat**.
- Es reserven com a mínim **2 opcions amb denominador 4** per costat si
  n'hi ha.
- `4/8` i `2/4`, i `10/8` i `5/4`, es mostren com a opcions separades.
- Si un costat només té una opció, es mostra com a resum fix (BPM, compàs, N)
  i no cal triar-lo.
- Cap opció preseleccionada.
- El botó **Aplica** està desactivat fins que cada costat ambigu tinga una
  opció triada.
- Cada opció mostra, per a cada clip:
  - BPM;
  - compàs `x/x`;
  - `N`;
  - orde dels clips (base/extrany o extrany/base).
- Es mostra sempre la diferència exacta entre el BPM resultant i el BPM de la
  Ref., sense bloquejar.

### 9.3 Reproducció

- En obrir el diàleg, si la reproducció estava activa, es **pausa** i es
  recorda la posició i que estava sonant.
- En **cancel·lar**, tancar o fallar l'aplicació, es queda **en pausa**.
- En **aplicar correctament**, la reproducció **continua des de la pausa**
  (reprén la posició on s'havia pausat), sempre que estiguera sonant abans
  d'obrir el diàleg.
- Si ja estava en pausa abans d'obrir el diàleg, continua en pausa.
- Si no hi ha diàleg (aplicació directa d'una sola opció), no es toca l'estat
  de reproducció.

### 9.4 Atomicitat

- Si es cancel·la el diàleg, no es toca res.
- Si un costat no té candidat, no s'aplica l'altre.
- En aplicar, tots els clips dels dos costats i, si és `+`, el tall
  d'estructura, formen **una sola operació de desfer/refer**.
- Es desa el model una sola vegada en acabar.

---

## 10. Metadades dels clips resultants

- `tipus`: sempre `normal`.
  - Si el clip original era rubato, el tall el tracta com a normal i els clips
    resultants perden el flag.
- `beat_unit`: es deriva del compàs resultant. L'usuari el pot canviar
  manualment per tram; el motor no infereix cap modulació mètrica.
- `agrupació`: es deriva del compàs resultant.
- `N`: el del candidat.
- No s'hereten metadades antigues que no encaixen amb el compàs nou.

---

## 11. Exemples de referència

Amb `Bq` en negres i Ref. 4/4:

| Beats | Candidats principals |
|---:|---|
| 13 | `4/4 N=2` + `5/4 N=1`; `1/4 N=13` filtrat |
| 15 | `4/4 N=3` + `3/4 N=1`; `5/4 N=3`; `3/4 N=5` |
| 17 | `4/4 N=3` + `5/4 N=1`; `4/4 N=2` + `9/4 N=1`; `4/4 N=4` + `1/4 N=1` filtrat |
| 19 | `4/4 N=4` + `3/4 N=1`; `4/4 N=3` + `7/4 N=1`; `4/4 N=2` + `11/4 N=1` |
| 21 | `4/4 N=4` + `5/4 N=1`; `7/4 N=3`; `3/4 N=7` |
| 25 | `4/4 N=5` + `5/4 N=1`; `5/4 N=5`; `1/4 N=25` filtrat |

Exemple detallat de 17:

```text
4/4 N=3  → 12 beats
5/4 N=1  →  5 beats
total    → 17 beats
```

### Exemple 7/8 amb denominador 4

Ref. i local `7/8` (bar = 3,5 negres), `beat_unit=corxera`. Costat esquerre
`Bq=5,5`, costat dret `Bq=8,5`.

Esquerra:

- `7/8 N=1` + `2/4 N=1` (3,5 + 2)
- `2/4 N=1` + `7/8 N=1`
- `7/8 N=1` + `4/8 N=1` (equivalent a 2/4, però es mostra separat)
- `4/8 N=1` + `7/8 N=1`
- `11/8 N=1`

Dreta:

- `7/8 N=2` + `3/8 N=1` (7 + 1,5)
- `3/8 N=1` + `7/8 N=2`
- `7/8 N=1` + `5/4 N=1` (3,5 + 5)
- `5/4 N=1` + `7/8 N=1`
- `7/8 N=1` + `10/8 N=1` (equivalent a 5/4, però es mostra separat)
- `10/8 N=1` + `7/8 N=1`

El mínim de 2 opcions `/4` per costat es complix. No es genera `4/4 + 3/8`
perquè no inclou cap clip de la base `7/8`.

---

## 12. Integració als gestos

Tots estos camins han de passar pel mateix motor quan Snap = QM:

- `+` (`talla_tempo_i_estructura`);
- Enter (`talla_tempo`);
- `_afegeix_tall()` («Afegeix/Parteix aquí»);
- `_parteix_tram_per_la_meitat()`;
- `_parteix_tram_a_loop()` («Parteix A–B»).

`+` i Enter han de produir exactament el mateix resultat de tempo; `+` afig
només el tall d'estructura. Si el tempo falla o es cancel·la, no es parteix
l'estructura.

Si un candidat canvia de compàs i la relació de tempo (`♩ = ♩`, `♩. = ♩`…)
no està definida per l'usuari, el motor no l'inventa: avisa i deixa la decisió
a l'editor de tempo o al diàleg previ. El tall es reprén quan la relació
existeix.

---

## 13. Fitxers previsiblement afectats

- `app/visor_marcadors.py`: `_parteix_tempo_nou()`, `_talla()`.
- `app/tempo_map.py`: operacions de tall i validació; possible funció pura nova
  per al motor QM.
- `app/tempo_recalc.py`: reutilitzar el motor de candidats o adaptar-lo.
- `app/visor_tempo.py`: `ref_tempo_base()`, `_beats_per_validacio()`,
  `beat_factor()`.
- `app/marcadors_ui.py`: `_t_from_cursor_ui()`, `_snap_marcador_qm()`.
- `app/visor.py`: `_afegeix_tall()`, `_parteix_tram_a_loop()`,
  `_parteix_tram_per_la_meitat()`.
- Nou diàleg a `app/dialegs.py` o fitxer propi de diàleg.
- `tests/test_gui.py`, `tests/test_edicio.py`, `tests/test_tempo_trams.py`,
  `tests/test_tempo_map.py`.
- `CHANGELOG.md` i, si cal, `docs/EDICIO_OPERACIONS.md`.

---

## 14. Tests de regressió

### Motor

- Comptatge de beats QM: intervals, frontera dreta, factor d'unitat.
- Comptatge de polsos de metrònom sense QM.
- Conversió `Bq` amb 4/4, 6/8 i 7/8.
- Base pura única → aplicació directa.
- Dues bases pures diferents → diàleg.
- Base + extrany: final i principi.
- Opcions amb denominador 4 sempre que encaixen, encara que hi haja mateix
  denominador.
- Mínim 2 opcions `/4` per costat si n'hi ha.
- `4/8` i `2/4`, i `10/8` i `5/4`, es mantenen com a opcions separades.
- No es permet `/4 + /8` sense cap clip de la base.
- Secció sencera extranya.
- Filtre de `1/4` quan hi ha alternativa.
- Màxim 2 clips per costat.
- Prohibició de dos extranys diferents.
- Cap candidat → no es toca res.
- Rubato tractat com a normal.
- `beat_unit` i agrupació derivades.
- `6/8` a 80 negres amb punt/min equival a 120 negres/min internes.
- `4/4` a 120 negres/min i `6/8` a 80 negres amb punt comparteixen pols de
  negra; el MIDI pot mantindre 120 i canviar només la Time Signature.
- Canvi de compàs sense relació de tempo definida → no s'aplica
  automàticament; es demana manualment.
- Sense beats → Ref. pura amb `N` arrodonit i BPM derivat.
- BPM fora de 30–350 → candidat descartat.

### GUI

- `+` i Enter donen el mateix mapa de tempo.
- `+` també parteix estructura; Enter no.
- Cancel·lar el diàleg no deixa canvis ni undo apilat.
- Costat fix + costat ambigu.
- Cap preselecció; Aplica desactivat fins triar.
- Pausa en obrir el diàleg.
- Si s'aplica, reprén des de la pausa; si es cancel·la, queda en pausa.
- Diferència de BPM mostrada.
- Tots els gestos QM usen el mateix motor.
- Undo únic per al tall complet.

### Regressions existents

- Revisar `test_enter_recalcula_si_queden_compassos_fraccionaris`: actualment
  usa `_compassos_del_tram` (amb offset) en lloc de `compassos_del_clip`.
- Revisar tests que assumixen que el primer pas normalitza canviant BPM.

---

## 15. Fases d'implementació

### Fase 1 — motor pur i tests

- Comptatge de beats/polsos i conversió a `Bq`.
- Generació de candidats (pura, base+extrany, secció sencera).
- Opcions creuades amb denominador 4 (base + 1 compàs `/4`, dos ordres).
- Filtres, ordenació i límits (mínim 2 `/4` si n'hi ha).
- Fallback sense beats.
- Tests unitaris sense Qt.

### Fase 2 — diàleg conjunt

- Dues columnes, màxim 6 per costat.
- Costat fix si només té una opció.
- Sense preselecció; Aplica desactivat fins triar.
- Diferència de BPM.
- Pausa de reproducció en obrir; aplicar reprén des de la pausa; cancel·lar
  deixa en pausa.

### Fase 3 — integració

- Substituir el camí QM de `_parteix_tempo_nou`.
- Mantindre el camí actual per a Snap no QM.
- Integrar `+`, Enter, Afegeix, meitat i A–B.
- Atomicitat i undo únic.

### Fase 4 — documentació i verificació

- `CHANGELOG.md` i `docs/EDICIO_OPERACIONS.md`.
- `make docs-check`.
- Tests dirigits.
- Suite completa amb OK de l'operador.

---

## 16. Criteris de fet

- [ ] Snap QM usa els beats QM; sense QM, els polsos del mapa.
- [ ] El beat del tall compta a la dreta.
- [ ] `Bq` pot ser fraccionari i els càlculs no perden exactitud.
- [ ] Base pura s'aplica directament.
- [ ] Dues pures diferents pregunten.
- [ ] Sense pura es generen base+extrany i secció sencera.
- [ ] Màxim 2 clips per costat i 4 en total.
- [ ] Opcions `/4` sempre que encaixen; mínim 2 per costat si n'hi ha.
- [ ] `4/8`/`2/4` i `10/8`/`5/4` es mostren com a opcions separades.
- [ ] `1/4` filtrat si hi ha alternativa.
- [ ] Sense K±1 ni residu arbitrari.
- [ ] BPM per clip a partir dels temps reals.
- [ ] Sense beats: Ref. pura, N arrodonit, BPM derivat.
- [ ] Diàleg conjunt, màxim 6 per costat, sense preselecció.
- [ ] Cancel·lar no aplica res; undo únic.
- [ ] Pausa en obrir; aplicar reprén des de la pausa; cancel·lar deixa en pausa.
- [ ] Rubato tractat com a normal; unitat/agrupació derivades.
- [ ] `6/8` a 80 negres amb punt = 120 negres/min internes.
- [ ] Canvi de compàs sense relació de tempo definida → manual, no automàtic.
- [ ] MIDI exporta `Set Tempo` en negres/minut i `Time Signature` per tram;
  `beat_unit` no s'inventa.
- [ ] `+` i Enter comparteixen el resultat de tempo.
- [ ] Tests dirigits i suite completa verdes.
- [ ] `CHANGELOG` i documentació actualitzats.

---

## 17. Decisions descartades

- No K±1.
- No residu arbitrari.
- No dos compassos extranys diferents per costat.
- No `/4 + /8` sense cap clip de la base.
- No deduplicar `4/8` amb `2/4` ni `10/8` amb `5/4`; es mostren separats.
- No prioritat automàtica Ref. vs local.
- No downbeats.
- No `13/4` amb `NUM_MAX=12`.
- No forçar el BPM de la Ref. si els beats donen un altre BPM.
- No inferir modulació mètrica (`♩ = ♩`, `♩. = ♩`…) automàticament; és manual.
- No exportar `beat_unit` com si fóra un camp MIDI estàndard.
- No aplicar res si no hi ha cap candidat exacte.

---

## 18. Estat d'implementació (2026-11-14)

**Implementat:**

- `app/tall_qm.py`: comptatge QM, `Bq`, base pura, base + extrany, secció
  sencera extranya, canvi a `/4`, filtres, límit de 2 clips per costat,
  mínim 2 opcions `/4` i ordenació.
- `app/dialeg_tall_qm.py`: diàleg conjunt, dues columnes, costat fix, sense
  preselecció i diferència de BPM respecte de la Ref.
- `app/visor_marcadors.py`: integració amb Beats QM, pausa/reprén del play i
  atomicitat.
- `app/visor.py`: `+`, Enter, Afegeix/Parteix aquí, Partir per la meitat i
  Partir A–B.
- Fronteres internes amb interpolació sobre els temps reals dels beats QM.
- Tests: `tests/test_tall_qm.py`, `tests/test_dialeg_tall_qm.py` i proves GUI
  de motor, cancel·lació atòmica i represa del play.

**Pendent:**

- Fallback de graella quan no hi ha QM (actualment el motor QM només
  s'activa amb beats QM; fora de Snap QM es manté el camí anterior).
- Proves d'àudio real de pausa/reprén (els tests actuals simulen play_stop).
- Suite completa i revisió final.
