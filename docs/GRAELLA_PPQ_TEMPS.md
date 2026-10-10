# Graella, PPQ i formats de temps

> **Nota tècnica** (per a l'agent del projecte). Objectiu: fixar com AUTO
> CHORDS mesura, mostra i quantitza el **temps**, i quines opcions cal
> oferir de **graella** i de **resolució (PPQ)**. Document autocontingut.

## 0. Els 3 eixos (no barrejar-los mai)

| Eix | Què és | Magnitud |
|---|---|---|
| **PPQ (resolució)** | unitat atòmica interna (ticks per negra) | enter petit (480–3840) |
| **Graella** | sobre quines posicions s'imanta i es dibuixa | subdivisió del temps |
| **Tempo + compàs** | conversió temps musical ↔ absolut (s/mostres) | variable |

**Regla d'or:** les posicions es guarden sempre en **ticks enters**; el grid i
el BPM són "vistes" calculades a sobre.

## 1. On som ara (estat actual del codi)

- Posicions en **segons** (`float`); es converteix a `compàs.beat` (C.B) amb
  `beat = 60/bpm` i el compàs cada `bpb` temps.
- Grid **unificat** (`grid_plan` a `app/timeline_base.py`): grid, regle i snap
  surten del **mateix pla** → sempre quadren; nivells adaptatius al zoom
  (`MIN_LINE_PX`).
- Snap a beat/compàs, amb subdivisions triables.
- Metrònom amb la mateixa graella (`app/metronom.py`, `beat = 60/bpm`).
- **Offset** = segon on cau el compàs 1; abans, la graella és **negativa**
  (count-in).
- Export a Live: `acords_a_live.py` fa servir `step = 60.0 / bpm / 2`
  (corxera); `app/pipeline.py` idem.
- BPM: `app/tempo.py` (numpy) / `qm-tempotracker` / plugin aubio.

👉 **Implicació:** avui les subdivisions viuen en **segons**. Afegir una capa
de **ticks (PPQ)** fa el sistema exacte (sense arrodoniment acumulat), habilita
**tresets i puntets** amb enters i fa fiable l'**export MIDI**.

## 2. PPQ — la resolució

- **Definició:** ticks per **negra** (quarter note). Una posició = un `int64`.
- **Requisit dur:** el PPQ ha de ser **divisible** per totes les subdivisions
  objectiu. Tresets → **factor 3**; quintets → **5**; setets → **7**.
- **PROHIBIT:** potència de 2 (256, 512, 1024…) → **mai** tindràs tresets
  exactes (256 ÷ 3 no és enter).

Nombres "alts i compostos" (recomanats):

| PPQ | Factorització | Cobreix fins a |
|---|---|---|
| 96 | 2⁵·3 | 1/32 + tresets |
| 240 | 2⁴·3·5 | 1/32 + tresets + quintets |
| 480 | 2⁵·3·5 | 1/64 + tresets + quintets |
| **960** | 2⁶·3·5 | 1/64 + tresets + quintets + 1/128 |
| 1920 | 2⁷·3·5 | tot l'anterior, més fi |
| 3840 | 2⁸·3·5 | estàndard "professional" |
| 3360 | 2⁵·3·5·7 | afegeix **setets** (÷7) |

**Recomanat: `PPQ = 960`** per defecte, configurable per projecte.

## 3. Graella — la subdivisió

Modes a suportar: `straight` · `triplet` · `dotted` · `swing` · `custom (p:q)`.

**Pas de grid en ticks** (on `N` = denominador de la nota; 1/8 → N = 8):

```
Straight 1/N : step = PPQ · 4 / N
Triplet  1/N : step = PPQ · 8 / (3N)      (= straight × 2/3)
Dotted   1/N : step = PPQ · 6 / N         (= straight × 3/2)
```

Valors @ PPQ 960:

| Grid | Ticks | Grid | Ticks |
|---|---|---|---|
| 1/4 | 960 | 1/8T | 320 |
| 1/8 | 480 | 1/16T | 160 |
| 1/16 | 240 | 1/32T | 80 |
| 1/32 | 120 | 1/64T | 40 |

- **Swing:** desplaça cada 2a subdivisió → `offset = swing% · step`.
- **Snap:** `snap = round(tick / step) · step` (força parcial 0–100% opcional).
- **Graella unificada:** mantenir el patró actual (`grid_plan` = font única per
  a grid, regle i snap) i ampliar-lo amb els modes triplet/dotted/swing.

> **Clau:** el grid **no fa coincidir** els accents de ÷4 i ÷3 (són coprimers,
> és impossible). Només decideix **on s'imanta**. El PPQ només garanteix que
> tot cau en **ticks enters**.

## 4. Formats de temps

| Domini | Format | Depèn del BPM? |
|---|---|---|
| **Musical** | `compàs.temps.tick` | Sí |
| **Absolut** | segons · mostres | No |

- `compàs.temps.tick`: compàs i temps **1-indexats**, tick **0-indexat**.
- Llargada del compàs: `compàs_ticks = PPQ · 4 · num / den` (6/8 → `PPQ·3`).
- El nostre `C.B` actual és `compàs.temps` (sense tick); afegir el 3r camp el
  fa complet.

## 5. Fórmules de conversió

```
tick  → beat      : beat = tick / PPQ
beat  → segons    : s    = beat · 60 / BPM          (constant)
segons → mostres  : n    = s · samplerate
tick  → segons    : s    = tick / PPQ · 60 / BPM
segons → tick     : tick = round( s · BPM / 60 · PPQ )
```

- **Tempo constant:** conversió lineal (regla de tres).
- **Tempo map / rampes** (BPM variable): beat→segons requereix **integrar**
  `60/BPM` tram a tram; segons→beat, la **inversa**.
- Considerar: pickup / count-in / compassos negatius (ja suportats).

## 6. Export (on el PPQ es torna crític)

- **MIDI (SMF):** el header porta `division` = **ticks per quarter**. Si els
  tresets han d'existir al fitxer, ha de ser múltiple de 3 → **960**
  (`mido`: `ticks_per_beat=960`; el seu valor per defecte és 480).
- **.als (Live):** les posicions viuen en **beats** (XML). El `step` de corxera
  actual és correcte, però calcular-lo des de segons perd exactitud en tresets.
- **Audio (WAV):** sense graella → segons/mostres directes.

## 7. Trampes conegudes (per no repetir errors)

1. **PPQ potència de 2** → tresets impossible. ✗
2. **`float` per a posicions** → arrodoniment acumulat. Usa enters.
3. **Confondre grid amb PPQ**: el grid és vista; el PPQ és emmagatzematge.
4. **Assumir BPM constant**: amb tempo map, la conversió no és regla de tres.
5. **Noms de figures**: 3 per temps = *treset de corxea*; un *treset de
   semicorxea* en dona **6**. No confondre.
6. **Set/quintets**: si els vols, el PPQ ha d'incloure factor 5 (o 7) →
   480 / 960 / 3360…
7. **Canvi de compàs**: la llargada del compàs varia (no assumir 4/4 fix).
8. **Overflow**: `int64` per a posicions llargues amb PPQ alt.

## 8. Recomanació concreta

```
PPQ = 960 (configurable)
Posicions: int64 ticks   (o conviure amb els segons actuals)
Grid = capa calculada: step = f(mode, N, PPQ)   → dins del grid_plan unificat
Tempo: segments (constant + ramp) → integració per a beat ↔ segons
Display: compàs.temps.tick (1-indexat) + unitat de transport commutable
Export MIDI: ticks_per_beat = 960
```

**Pla mínim:**
1. Afegir la capa de **ticks** (PPQ 960) mantenint els segons actuals.
2. Posar el **mode de graella** (straight/triplet/dotted/swing) al `grid_plan`.
3. Snap, regle i grid ja surten del `grid_plan` → només cal ampliar-lo.
4. Export MIDI amb `ticks_per_beat=960` (i validar tresets).
5. Conservar l'offset de compàs 1 i els compassos negatius (count-in).
