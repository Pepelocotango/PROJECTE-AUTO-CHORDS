# Compassos compostos, BPM i metrònom

> **Estat:** recerca aplicada (2026-11-16). **Abast:** com separar el BPM que es
> mostra, el rellotge intern, el pols percebut i el clic del metrònom en
> compassos compostos (`6/8`, `9/8`, `12/8`) i en compassos irregulars
> (`5/8`, `7/8`, `8/8`). **No és un contracte:** el contracte és
> `docs/REGLES_DE_LA_APP.md` §13.

## 1. Conclusió curta

Els sistemes professionals no guarden «un BPM» a seques. Separen quatre coses:

1. **Rellotge canònic:** negres/minut (`qpm`) o microsegons per negra. És el que
   fa sonar l'àudio i el que exporten MIDI i MusicXML.
2. **Unitat del BPM mostrat:** negra (`♩`), negra amb punt (`♩.`), corxera
   (`♪`), etc. És una **vista**; no canvia el so si no canvia `qpm`.
3. **Pols percebut:** on va el peu del músic. En `6/8` normalment és la negra
   amb punt (`3+3`); en `9/8`, `3+3+3`; en `12/8`, `3+3+3+3`.
4. **Clic:** el metrònom pot clicar el compàs, els inicis de grup, cada unitat
   del denominador o una subdivisió. És independent de la unitat del BPM.

**Regla pràctica:** guardar `qpm` i els segons com a autoritat; derivar el BPM
mostrat de la unitat; guardar el compàs i l'agrupació per separat. Així `6/8`
no és un cas especial: és `meter=6/8`, `grouping=[3,3]`, `pulse_unit=♩.`.

## 2. Fórmules

Si la unitat de tempo és una figura de denominador `den` amb `dots` punts:

```text
u_q = (4 / den) * (2 - 2^(-dots))     # negres per unitat
qpm = bpm_mostrat * u_q               # BPM intern
bpm_mostrat = qpm / u_q
durada_compas = num * (4 / den) * (60 / qpm)
durada_pols   = u_q * (60 / qpm)
```

Exemples:

| Compàs | BPM mostrat | Unitat | `qpm` intern | Durada compàs |
|---|---:|---|---:|---:|
| `6/8` | 80 | `♩.` | 120 | 1,50 s |
| `6/8` | 120 | `♩` | 120 | 1,50 s |
| `6/8` | 240 | `♪` | 120 | 1,50 s |
| `9/8` | 60 | `♩.` | 90 | 3,00 s |
| `12/8` | 80 | `♩.` | 120 | 3,00 s |

`♩.=80`, `♩=120` i `♪=240` poden描述 el mateix rellotge, però no volen dir el
mateix per al metrònom, el tap tempo ni la notació. Per això la unitat és
obligatòria a la UI i a l'export.

## 3. Què fan les apps professionals

### 3.1 DAWs

| App | BPM mostrat | Unitat canònica | `♩.` al transport? | Clic per defecte en `6/8` | Agrupació |
|---|---|---|---|---|---|
| **Logic Pro** | `♩` | negres/minut | No | 6 corxeres; `Group` dona 2 polsos | `Beat Grouping` `3+3` / `2+2+2` |
| **Ableton Live** | `♩` | negres/minut | No | 6 corxeres (`Auto` = denominador) | Sense accent de grup explícit |
| **Cubase / Nuendo** | `♩` | negres/minut | No | denominador; Click Pattern Editor | Patrons d'accent per beat |
| **Pro Tools** | `♩` o `♩.` | Tempo Resolution | **Sí** | valor del meter event (pot ser `♩.` → 2) | accent al primer beat |
| **REAPER** | `♩` + `BPM basis` | negra o negra amb punt (7.31+) | **Sí** | patró `A/B/T/.` per compàs | patró per unitat |
| **MuseScore** | `♩` | negres/minut (playback) | Text sí; playback no | 2 clics en `6/8` (`num/3`) | T1/T2; subdivisions si `qpm<60` |
| **Dorico** | depén del compàs/tempo mark | depén | **Sí** | fort `♩.` + febles corxeres | «subdivide beats in compound» |
| **Sibelius / Finale** | unitat del tempo mark | conversió interna | **Sí** | segons tempo mark | tempo mark + playback |

### 3.2 Observacions clau

- **Logic**: el transport sempre és en negres, encara que el denominador siga 8;
  el compàs no afecta el playback, només la graella. El metrònom té
  `Bar / Group / Beat / Division`; per a `6/8` es recomana `Group` activat i
  `Beat` desactivat.
- **Ableton**: `Auto` clica el denominador; el BPM no canvia de definició. Un
  canvi de compàs a mig compàs pot crear una *fragmentary bar*.
- **Cubase/Nuendo**: el signature event va a inici de compàs; el click pattern
  permet accents per beat.
- **Pro Tools**: la *Tempo Resolution* i el valor de clic del meter event són
  decisions separades; en `6/8` es pot triar negra amb punt.
- **REAPER 7.31+**: introdueix `BPM basis` (negra, negra amb punt…) i
  auto-switch en compassos compostos; abans calia multiplicar a mà.
- **MuseScore**: el playback sempre en negres; en compostos compta
  `numerador/3` clics i, si el tempo resultant baixa de 60 `qpm`, afegeix dos
  clics per pols.
- **Dorico**: el transport deriva la unitat del compàs/tempo mark; el clic fort
  de pols i la subdivisió són configurables.
- **Sibelius/Finale**: el tempo mark pot ser qualsevol figura; el playback
  converteix internament.

### 3.3 MusicXML i MIDI

- **MusicXML**: `<sound tempo="...">` és **negres/minut**; `<metronome>` amb
  `<beat-unit>` i `<beat-unit-dot>` és la visualització. Les dues coses poden
  coexistir i no sempre coincideixen.
- **MIDI**: `FF 51` guarda microsegons per negra; `FF 58 cc` guarda els
  *clocks per metronome click* (24 = negra, 36 = negra amb punt). No hi ha un
  «BPM» textual.

## 4. Compassos compostos vs simples

`6/8` i `3/4` tenen sis corxeres per compàs, però no són el mateix:

| | `6/8` | `3/4` |
|---|---|---|
| Agrupació | `3+3` | `2+2+2` |
| Pols percebut | 2 negres amb punt | 3 negres |
| Accents | 1 i 4 | 1, 2 i 3 |
| Metrònom defecte | 2 clics | 3 clics |

Per això el model ha de guardar **`meter` + `grouping` + `pulse_unit`**, no
només `num/den`.

## 5. Anacrusi, count-in i canvis a mig compàs

> **Fora de l'abast actual (2026-11-16):** AUTO CHORDS no té pre-roll, offset
> ni count-in; el compàs 1 cau sempre a **0 s**. Esta secció es conserva com a
> recerca per a una possible pickup futura.

- **Anacrusi/pickup:** és una barra incompleta amb `actual` i `nominal`. La
  numeració comença al primer compàs complet. El count-in ha d'omplir
  `nominal - actual` beats, no una barra sencera cegament.
- **Canvi de compàs a mig compàs:** hi ha apps que ho prohibeixen (Cubase,
  MuseScore) i apps que creen una **barra fragmentària** (Ableton, Pro Tools,
  Dorico). AUTO CHORDS, que treballa en segons, ha de representar-ho com una
  barra fragmentària o rebutjar-ho amb avís; no ha de «reflowar» l'àudio en
  silenci.
- **Count-in:** es calcula cap enrere des del downbeat objectiu; els accents
  han de seguir el compàs objectiu, no el compàs anterior.

## 6. Decisions per a AUTO CHORDS

### 6.1 Model

Mínim recomanat per tram:

```text
ini, fi, qpm, num, den, agrupacio, beat_unit
```

- `ini`/`fi`: segons, autoritat de l'àudio.
- `qpm`: negres/minut, sempre intern.
- `num`/`den`: compàs.
- `agrupacio`: `3+3`, `2+2+3`…; buit = automàtica.
- `beat_unit`: unitat de pols mostrada (negra, negra amb punt…).

No cal guardar un «BPM mostrat» separat: es deriva de `qpm` i `beat_unit`.

### 6.2 BPM

- **Intern sempre `qpm`**; la UI mostra la unitat del tram.
- Mostrar sempre la figura: `♩.=80`, no `80` sol.
- En `6/8`, `9/8`, `12/8` amb grups de 3, la unitat per defecte és `♩.`.
- **Cas A — conservar el tempo intern:** canviar només el compàs manté `qpm`;
  el BPM visible canvia amb la unitat. És el mode explícit «conservar el tempo
  intern» del diàleg.
- **Cas B — conservar la pulsació (per defecte):** en canviar el compàs es
  conserva el **BPM visible** en la unitat de pulsació; `qpm` es recalcula.
  Exemple: `4/4` a 90 negres/min → `6/8` amb `♩.=90`, intern 135 negres/min.
- Si es vol conservar la durada del compàs, és una acció explícita.
- Tap tempo: la unitat del tap és la del tram; convertir a `qpm` i mostrar les
  dues xifres.
- Recalc mòbil: la referència del clip seleccionat i la del seu veí dret és el
  **clip anterior al seleccionat**; el clip editat no és la referència del veí.

### 6.3 Metrònom

- **Decisió AUTO CHORDS (2026-11-16):** per defecte, clicar el **denominador**
  amb accents d’agrupació: `6/8` → 6 corxeres amb accents a 1 i 4; `9/8` → 9;
  `12/8` → 12. La pols de negra amb punt es pot oferir com a mode alternatiu.
- Oferir un mode explícit de **subdivisió** per clicar corxeres o
  semicorxeres; no ha de ser el defecte.
- Accents: compàs, inici de grup, temps i subdivisió; el grup surt de
  `agrupacio`.
- Si l'usuari tria una unitat explícita (`corxera`), el clic la respecta.

### 6.4 Export

- MusicXML: `<sound tempo>` amb `qpm` i `<metronome>` amb la unitat mostrada.
- MIDI: `FF 51` amb `60_000_000 / qpm`; `FF 58 cc` amb `24 * u_q` (36 per
  negra amb punt).
- `mapa_tempo.csv`: mantenir `bpm` (qpm), `compassos`, `agrupacio`, `beat_unit`
  i, si es vol, un camp explícit de `tempo_unit`/`pulse_unit` en el futur.

## 7. Proves de regressió mínimes

1. `6/8` amb `♩.=80` → `qpm=120`; `♪=240` → `qpm=120`.
2. `9/8` amb `♩.=60` → `qpm=90`; `12/8` amb `♩.=80` → `qpm=120`.
3. `6/8 [3,3]` i `3/4 [2,2,2]` no es col·lapsen en el mateix objecte.
4. Metrònom `6/8` → 6 corxeres amb accents a 1 i 4; `9/8` → 9; `12/8` → 12;
   `4/4` → 4; `2/2` → 2.
5. Una unitat explícita (`corxera`) en `6/8` → 6 clics.
6. Canvi de compàs no canvia `qpm` per defecte.
7. Export MusicXML/MIDI conserva `qpm`, `meter`, `agrupacio` i unitat.
8. Count-in amb pickup omple `nominal - actual` beats (només si algun dia
   s'implementa el pickup; avui no hi ha count-in).

## 8. Fonts

- Apple, *Logic Pro 9 User Guide — Setting Project Properties*:
  <https://help.apple.com/logicpro/mac/9.1.6/en/logicpro/usermanual/chapter_7_section_8.html>
- Apple, *Logic Pro — Metronome project settings*:
  <https://support.apple.com/guide/logicpro/metronome-project-settings-lgcpe1d6118e/mac>
- Apple, *Logic Pro — Recording project settings*:
  <https://support.apple.com/guide/logicpro/recording-project-settings-lgcpbc10f1ea/mac>
- Ableton, *Live 12 Reference Manual — Live Concepts*:
  <https://www.ableton.com/en/manual/live-concepts/>
- Steinberg, *Cubase/Nuendo — Click Pattern Editor*:
  <https://archive.steinberg.help/nuendo/v8/en/cubase_nuendo/topics/playback/metronome_click_pattern_editor_r.html>
- Avid, *Pro Tools — Inserting Meter Events*:
  <https://apps.avid.com/proToolsFirstHelp/version12.0/enu/Pro%20Tools%20First%20Help/Arr1.conductors.31.58.html>
- Avid, *Pro Tools — Selecting Tempo Resolution*:
  <https://apps.avid.com/protoolsfirsthelp/version12.3/enu/Pro%20Tools%20First%20Help/Arr1.conductors.31.34.html>
- Cockos, *REAPER 7.31 changelog / BPM basis*:
  <https://reaper.blog/2025/03/735-update/>
- MuseScore, *Tempo markings*:
  <https://handbook.musescore.org/text/tempo-markings.md>
- MuseScore, *Playback controls*:
  <https://musescore.org/en/handbook/4/playback-controls>
- Steinberg, *Dorico — Types of time signatures*:
  <https://www.steinberg.help/r/dorico-pro/6.2/en/dorico/topics/notation_reference/notation_reference_time_signatures/notation_reference_time_signatures_types_r.html>
- Steinberg, *Dorico — Inputting pick-up bars*:
  <https://www.steinberg.help/r/dorico-elements/6.2/en/dorico/topics/write_mode/write_mode_notations_input/write_mode_time_signatures_pick_up_bars_inputting_popover_t.html>
- Avid, *Sibelius Reference 2025*:
  <https://resources.avid.com/SupportFiles/Sibelius/2025.2/Sibelius_Reference.pdf>
- Finale, *User Manual — Tempo*:
  <http://usermanuals.finalemusic.com/FinaleWin/Content/Finale/Tempo.htm>
- MusicXML, *The `<metronome>` element*:
  <https://musicxml.formats.music/musicxml-reference/elements/metronome/>
- MusicXML, *Complex Type: sound*:
  <https://usermanuals.musicxml.com/MusicXML/Content/CT-MusicXML-sound.htm>
- MIDI, *Tempo*:
  <http://midi.teragonaudio.com/tech/midifile/tempo.htm>
- MIDI Field Guide, *Standard MIDI Files*:
  <https://midi.community/docs/smf/>
