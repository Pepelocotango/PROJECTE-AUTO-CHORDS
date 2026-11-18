# Mapa de compassos `x/x`, BPM i metrònom

> **Estat:** recerca aplicada (2026-11-16). **Abast:** tots els compassos que
> accepta AUTO CHORDS (`1…12` / `2, 4, 8, 16`), amb la relació entre BPM intern,
> BPM percebut, pols, clics de metrònom i exportació. **No és un contracte:** el
> contracte és `docs/REGLES_DE_LA_APP.md` §13.

## 1. Conclusió

No hi ha «un BPM» únic. Cal separar quatre capes:

| Capa | Què és | Unitat |
|---|---|---|
| **BPM intern** | El rellotge que fa avançar l'àudio, el MIDI i les graelles | negres/minut (`qpm`) |
| **BPM percebut** | El número que veu el músic en cada clip | figura de `beat_unit` |
| **Pols** | Allò que el músic compta o marca amb el peu | figura musical |
| **Clic** | Allò que sona al metrònom | divisió del compàs |

La relació és:

```text
u_q = factor de la unitat en negres      # negra=1, negra_punt=1,5, corxera=0,5…
qpm = bpm_mostrat * u_q
bpm_mostrat = qpm / u_q
bar_q = num * (4 / den)                  # negres per compàs
bar_s = bar_q * 60 / qpm
click_s = (4 / den) * 60 / qpm           # clic al denominador
pulse_s = u_q * 60 / qpm                 # pols percebuda
```

`qpm` no és una alternativa al BPM percebut: és la conversió necessària per
situar els esdeveniments en segons. La font de la UI és el clip; el motor només
convertix.

## 2. Regla estàndard per `num/den`

La classificació no depén només del denominador:

| Numerador | Tipus estàndard | Pols |
|---|---|---|
| `1` | simple d'un temps (poc habitual) | la figura del denominador |
| `2` | simple duple | la figura del denominador |
| `3` | simple triple | la figura del denominador |
| `4` | simple quàdruple | la figura del denominador |
| `6` | compost duple | figura del denominador **amb punt** |
| `9` | compost triple | figura del denominador **amb punt** |
| `12` | compost quàdruple | figura del denominador **amb punt** |
| `5, 7, 8, 10, 11` | irregular/compost | **no hi ha una pols única**; depén de l'agrupació |

Conseqüències:

- `3/8` és **simple triple** en teoria: la pols estàndard és la corxera. No és
  un `6/8` ni un compost. **Decisió de l'app (2026-11-17):** per defecte es
  tracta com una sola pols de **negra amb punt** (1 pols per compàs); només una
  agrupació explícita que no siga de 3 el torna a corxera.
- `6/8` és **compost duple**: la divisió és la corxera, la pols és la negra amb
  punt (`3+3`).
- `6/4` és **compost duple**: la divisió és la negra, la pols és la **blanca
  amb punt**.
- `6/16` és **compost duple**: la divisió és la semicorxera, la pols és la
  **corxera amb punt**.
- `6/2` és compost duple en la teoria, amb pols de **rodona amb punt**; és poc
  habitual i no tots els programes el mostren així.
- `5/8`, `7/8`, `8/8`, `10/8`, `11/8`, `5/4`… no tenen una agrupació única
  universal. `5/8` pot ser `3+2` o `2+3`; `7/8` pot ser `2+2+3`, `3+2+2` o
  `2+3+2`; `8/8` sovint és un `4/4` escrit en vuitens. L'app usa per defecte
  `5`, `7` i `8` respectivament; les altres agrupacions són tries explícites.

## 3. Comportament actual d'AUTO CHORDS

- **BPM intern** sempre en negres/minut.
- **BPM mostrat** = `qpm / factor(beat_unit)`.
- **Metrònom per defecte**: clica el **denominador** (`num` clics per compàs) i
  accentua els inicis de `agrupacio_compas`. En `6/8` fa 6 corxeres amb accents
  a 1 i 4; en `9/8` 9 i accents a 1, 4 i 7; en `12/8` 12 i accents a 1, 4, 7 i
  10.
- **Tap tempo**: treballa amb la unitat percebuda del clip i convertix a `qpm`.
- **Graella**: les línies de compàs es calculen amb `num·4/den` negres; amb un
  mapa s'afig una línia de pols (`beat_unit`) a més de les subdivisions.
- **Exportació**: `mapa_tempo.csv` desa `qpm` + `compas` + `beat_unit`; MIDI
  exporta `Set Tempo` amb `qpm` i `Time Signature`; MusicXML exporta
  `<sound tempo>` amb `qpm` i `<metronome>` amb el BPM percebut i la figura.

### 3.1 Taula completa (exemple `qpm = 120`)

La columna **BPM app** és el valor que mostra avui l'app amb la unitat que
deriva; la columna **BPM estàndard** és el valor que correspon a la pols
estàndard. La columna **clic** indica els clics per compàs al denominador; els
accents actuals ixen de l'agrupació per defecte de l'app.

| Compàs | Classificació | Pols estàndard | Factor | BPM estàndard | Clics/compàs | Accents estàndard | Unitat actual de l'app | BPM app | Accents actuals | Durada compàs (s) | Observació |
|---|---|---:|---:|---:|---:|---|---|---:|---|---:|---|
| 1/2 | simple d'un temps (rar) | blanca | 2 | 60 | 1 | 1 | blanca | 60 | 1 | 1 |  |
| 2/2 | simple duple | blanca | 2 | 60 | 2 | 1 | blanca | 60 | 1 | 2 |  |
| 3/2 | simple triple | blanca | 2 | 60 | 3 | 1 | blanca | 60 | 1 | 3 |  |
| 4/2 | simple quàdruple | blanca | 2 | 60 | 4 | 1 | blanca | 60 | 1 | 4 |  |
| 5/2 | irregular/compost | grup variable | — | — | 5 | — | blanca | 60 | 1 | 5 | cal agrupació explícita; l'app usa 5 |
| 6/2 | compost duple | rodona amb punt | 6 | 20 | 6 | 1,4 | rodona punt | 20 | 1,4 | 6 |  |
| 7/2 | irregular/compost | grup variable | — | — | 7 | — | blanca | 60 | 1 | 7 | cal agrupació explícita; l'app usa 7 |
| 8/2 | irregular/compost | grup variable | — | — | 8 | — | blanca | 60 | 1 | 8 | cal agrupació explícita; l'app usa 8 |
| 9/2 | compost triple | rodona amb punt | 6 | 20 | 9 | 1,4,7 | rodona punt | 20 | 1,4,7 | 9 |  |
| 10/2 | irregular/compost | grup variable | — | — | 10 | — | blanca | 60 | 1 | 10 | cal agrupació explícita; l'app usa 10 |
| 11/2 | irregular/compost | grup variable | — | — | 11 | — | blanca | 60 | 1 | 11 | cal agrupació explícita; l'app usa 11 |
| 12/2 | compost quàdruple | rodona amb punt | 6 | 20 | 12 | 1,4,7,10 | rodona punt | 20 | 1,4,7,10 | 12 |  |
| 1/4 | simple d'un temps (rar) | negra | 1 | 120 | 1 | 1 | negra | 120 | 1 | 0.5 |  |
| 2/4 | simple duple | negra | 1 | 120 | 2 | 1 | negra | 120 | 1 | 1 |  |
| 3/4 | simple triple | negra | 1 | 120 | 3 | 1 | negra | 120 | 1 | 1.5 |  |
| 4/4 | simple quàdruple | negra | 1 | 120 | 4 | 1 | negra | 120 | 1 | 2 |  |
| 5/4 | irregular/compost | grup variable | — | — | 5 | — | negra | 120 | 1 | 2.5 | cal agrupació explícita; l'app usa 5 |
| 6/4 | compost duple | blanca amb punt | 3 | 40 | 6 | 1,4 | blanca punt | 40 | 1,4 | 3 |  |
| 7/4 | irregular/compost | grup variable | — | — | 7 | — | negra | 120 | 1 | 3.5 | cal agrupació explícita; l'app usa 7 |
| 8/4 | irregular/compost | grup variable | — | — | 8 | — | negra | 120 | 1 | 4 | cal agrupació explícita; l'app usa 8 |
| 9/4 | compost triple | blanca amb punt | 3 | 40 | 9 | 1,4,7 | blanca punt | 40 | 1,4,7 | 4.5 |  |
| 10/4 | irregular/compost | grup variable | — | — | 10 | — | negra | 120 | 1 | 5 | cal agrupació explícita; l'app usa 10 |
| 11/4 | irregular/compost | grup variable | — | — | 11 | — | negra | 120 | 1 | 5.5 | cal agrupació explícita; l'app usa 11 |
| 12/4 | compost quàdruple | blanca amb punt | 3 | 40 | 12 | 1,4,7,10 | blanca punt | 40 | 1,4,7,10 | 6 |  |
| 1/8 | simple d'un temps (rar) | corxera | 0.5 | 240 | 1 | 1 | corxera | 240 | 1 | 0.25 |  |
| 2/8 | simple duple | corxera | 0.5 | 240 | 2 | 1 | corxera | 240 | 1 | 0.5 |  |
| 3/8 | simple triple | corxera | 0.5 | 240 | 3 | 1 | negra punt | 80 | 1 | 0.75 | decisió de producte: 3/8 = 1 pols de negra amb punt |
| 4/8 | simple quàdruple | corxera | 0.5 | 240 | 4 | 1 | corxera | 240 | 1 | 1 |  |
| 5/8 | irregular/compost | grup variable | — | — | 5 | — | corxera | 240 | 1 | 1.25 | l'app usa 5 per defecte; es pot triar 3+2 o 2+3 |
| 6/8 | compost duple | negra amb punt | 1.5 | 80 | 6 | 1,4 | negra punt | 80 | 1,4 | 1.5 |  |
| 7/8 | irregular/compost | grup variable | — | — | 7 | — | corxera | 240 | 1 | 1.75 | l'app usa 7 per defecte; es pot triar 2+2+3, 3+2+2… |
| 8/8 | irregular/compost | grup variable | — | — | 8 | — | corxera | 240 | 1 | 2 | l'app usa 8 per defecte; es pot triar 3+3+2 o 4+4 |
| 9/8 | compost triple | negra amb punt | 1.5 | 80 | 9 | 1,4,7 | negra punt | 80 | 1,4,7 | 2.25 |  |
| 10/8 | irregular/compost | grup variable | — | — | 10 | — | corxera | 240 | 1 | 2.5 | cal agrupació explícita; l'app usa 10 |
| 11/8 | irregular/compost | grup variable | — | — | 11 | — | corxera | 240 | 1 | 2.75 | cal agrupació explícita; l'app usa 11 |
| 12/8 | compost quàdruple | negra amb punt | 1.5 | 80 | 12 | 1,4,7,10 | negra punt | 80 | 1,4,7,10 | 3 |  |
| 1/16 | simple d'un temps (rar) | semicorxera | 0.25 | 480 | 1 | 1 | semicorxera | 480 | 1 | 0.125 |  |
| 2/16 | simple duple | semicorxera | 0.25 | 480 | 2 | 1 | semicorxera | 480 | 1 | 0.25 |  |
| 3/16 | simple triple | semicorxera | 0.25 | 480 | 3 | 1 | semicorxera | 480 | 1 | 0.375 |  |
| 4/16 | simple quàdruple | semicorxera | 0.25 | 480 | 4 | 1 | semicorxera | 480 | 1 | 0.5 |  |
| 5/16 | irregular/compost | grup variable | — | — | 5 | — | semicorxera | 480 | 1 | 0.625 | cal agrupació explícita; l'app usa 5 |
| 6/16 | compost duple | corxera amb punt | 0.75 | 160 | 6 | 1,4 | corxera punt | 160 | 1,4 | 0.75 |  |
| 7/16 | irregular/compost | grup variable | — | — | 7 | — | semicorxera | 480 | 1 | 0.875 | cal agrupació explícita; l'app usa 7 |
| 8/16 | irregular/compost | grup variable | — | — | 8 | — | semicorxera | 480 | 1 | 1 | cal agrupació explícita; l'app usa 8 |
| 9/16 | compost triple | corxera amb punt | 0.75 | 160 | 9 | 1,4,7 | corxera punt | 160 | 1,4,7 | 1.125 |  |
| 10/16 | irregular/compost | grup variable | — | — | 10 | — | semicorxera | 480 | 1 | 1.25 | cal agrupació explícita; l'app usa 10 |
| 11/16 | irregular/compost | grup variable | — | — | 11 | — | semicorxera | 480 | 1 | 1.375 | cal agrupació explícita; l'app usa 11 |
| 12/16 | compost quàdruple | corxera amb punt | 0.75 | 160 | 12 | 1,4,7,10 | corxera punt | 160 | 1,4,7,10 | 1.5 |  |

### 3.2 Exemples que cal retindre

| Compàs | `beat_unit` | `qpm` | BPM mostrat | Clic del metrònom | Durada del compàs |
|---|---|---:|---:|---|---:|
| `4/4` | negra | 120 | 120 | 4 negres, accent a 1 | 2,00 s |
| `2/2` | blanca | 120 | 60 | 2 blanques, accent a 1 | 2,00 s |
| `6/8` | negra amb punt | 120 | 80 | 6 corxeres, accents a 1 i 4 | 1,50 s |
| `9/8` | negra amb punt | 120 | 80 | 9 corxeres, accents a 1, 4 i 7 | 2,25 s |
| `12/8` | negra amb punt | 120 | 80 | 12 corxeres, accents a 1, 4, 7 i 10 | 3,00 s |
| `6/4` | blanca amb punt | 120 | 40 | 6 negres, accents a 1 i 4 | 3,00 s |
| `6/16` | corxera amb punt | 120 | 160 | 6 semicorxeres, accents a 1 i 4 | 0,75 s |
| `5/8` | corxera (o grup) | 120 | 240 (o grup) | 5 corxeres; agrupació per defecte `5` | 1,25 s |
| `7/8` | corxera (o grup) | 120 | 240 (o grup) | 7 corxeres; agrupació per defecte `7` | 1,75 s |
| `5/16` | semicorxera (o grup) | 120 | 480 (o grup) | 5 semicorxeres; agrupació a decidir | 0,625 s |

## 4. Conseqüències per a AUTO CHORDS

1. **La pols no depén només del denominador.** En `6/4`, `6/16`, `6/2` i els
   seus múltiples `9` i `12`, la pols estàndard és una figura amb punt diferent
   de la del denominador.
2. **El model ja té les figures necessàries.** `bpm_unit.UNITATS` inclou
   `rodona_punt`, `blanca_punt`, `negra_punt` i `corxera_punt`, a més de les
   figures simples.
3. **`3/8` no és compost en teoria.** És simple triple i la pols estàndard és
   la corxera; l'app, però, el tracta per defecte com a **1 pols de negra amb
   punt** (2026-11-17) i no l'ha de confondre amb un `6/8`.
4. **Els irregulars no tenen una agrupació única.** `5/8`, `7/8`, `8/8`,
   `10/8`, `11/8`, `5/4`… necessiten una agrupació explícita o una decisió de
   producte; no s'ha de presentar una tria com a estàndard universal.
5. **El metrònom i la graella distingixen pols i subdivisió.** En `6/4`, la
   pols és la blanca amb punt, però el clic per defecte és la negra (6 clics).
   En `6/8`, la pols és la negra amb punt i el clic per defecte és la corxera
   (6 clics).
6. **Exportar no és triar entre intern i percebut.** MIDI necessita `qpm`;
   MusicXML necessita `qpm` a `<sound tempo>` i la figura percebuda a
   `<metronome>`. Si la unitat percebuda és incorrecta, la partitura i el MIDI
   poden ser coherents en temps però incorrectes en notació.

### 4.1 Estat de la implementació

- **Fet:** unitats amb punt `rodona_punt`, `blanca_punt`, `negra_punt` i
  `corxera_punt`; derivació de la pols per a `6`, `9` i `12` amb qualsevol
  denominador; `3/8` derivat a negra amb punt (1 pols); agrupació per defecte `3+3…` en tots
  els compassos compostos; `5/8` i `7/8` amb agrupació per defecte `5` i `7`;
  accents del metrònom i de la graella alineats.
- **Fet:** tests que recorren tots els `1…12` × `2, 4, 8, 16` i comproven
  unitat, factor, encaix i agrupació; a més dels casos `6/4`, `6/16`, `6/2`,
  `3/8`, `5/8`, `7/8` i `8/8`.
- **Pendent:** per als irregulars, decidir l'agrupació explícita a la UI; no
  assignar-la automàticament com si fóra universal.

## 5. Fonts

- Open Music Theory, *Meter*: simple/compound, duple/triple/quadruple i el
  significat del numerador i denominador.
  <https://open-musictheory.github.io/docs/fundamentals/meter>
- Open Music Theory, *Compound Meter and Time Signatures*: la pols dels
  compostos és la figura del denominador amb punt; exemples `6/4`, `6/8`,
  `6/16`.
  <https://viva.pressbooks.pub/openmusictheory/chapter/compound-meters-and-time-signatures>
- W3C MusicXML 4.1, `<metronome>`: `beat-unit`, `beat-unit-dot` i
  `per-minute`; possibilitat de relacions mètriques.
  <https://w3c-cg.github.io/musicxml/musicxml-reference/elements/metronome/>
- W3C MusicXML 4.1, `<sound>`: `tempo` expressat en **negres per minut**.
  <https://w3c-cg.github.io/musicxml/musicxml-reference/elements/sound/>
- MIDI Field Guide, *Standard MIDI Files*: `Set Tempo` en microsegons per
  negra; `Time Signature` amb `nn dd cc bb` i `cc` com a clics MIDI per clic
  de metrònom.
  <https://midi.community/docs/smf>
- Ableton Live 12 Reference Manual, *Metronome Settings*: `Auto` seguix el
  denominador; les divisions que no caben al compàs es desactiven.
  <https://cdn-resources.ableton.com/resources/pdfs/live-manual/12/2026-09-23/live12-manual-en.pdf>
- Apple Logic Pro, *Metronome project settings*: Bar, Group, Beat i Division
  són controls separats; `Group` és per a compassos compostos i compostos
  irregulars.
  <https://support.apple.com/guide/logicpro/metronome-project-settings-lgcpe1d6118e/mac>
- REAPER User Guide: el patró de clic i el compàs són configuracions
  separades; el metrònom seguix el mapa de tempo i compàs.
  <https://dlx.reaper.fm/userguide/ReaperUserGuide781c.pdf>

## 6. Relació amb la resta de recerca

- `COMPASSOS_COMPOSTOS_BPM_METRONOM.md` aprofundix en `6/8`, `9/8`, `12/8`,
  `5/8`, `7/8` i `8/8`, i en la relació amb DAWs.
- Aquest document és la **taula completa** dels compassos acceptats per
  l'app; no substitueix el contracte de `REGLES_DE_LA_APP.md` §13.
