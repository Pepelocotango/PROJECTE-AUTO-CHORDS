# Pla — mapa de TEMPO i COMPÀS variables (com als DAWs)

> **Objectiu**: poder canviar el **BPM** i el **compàs** al llarg del tema (com la
> *tempo track* / *signature track* d'un DAW). Decisió de l'operador, 2026-10-17.

## Per què aquí és més fàcil que en un DAW
L'app **no estira ni deforma l'àudio** (la WAV és fixa) → un canvi de tempo/compàs
és **només el mapa** (graella, numeració de compassos i snap). Fora tota la part
DSP (*warp*/*time-stretch*). El **mode Lliure** ja existeix: el mapa només actua
en mode «BPM·compàs».

## Model (inspirat en Reaper/Cubase/Ableton)
- **Dos conceptes**: **tempo** (negres per minut) i **compàs** (`num/den`), com a
  **llistes d'esdeveniments** que valen fins al següent.
- **Unitat musical de referència**: la **negra** (quarter note), com a tots els
  DAWs. Un compàs `num/den` fa `num·4/den` negres; el seu temps, `4/den` negres.
  (4/4→4, 3/4→3, 6/8→3, 12/8→6.)
- **Trossos**: dins de cada tros el tempo i el compàs són constants (les rampes
  lineals són una extensió futura).
- **Font única**: com la resta del projecte, la geometria és una cadena de clips;
  el tempo/compàs seran **dues pistes més** (`Clip(ini, fi, bpm)` i
  `Clip(ini, fi, (num, den))`), i reutilitzaran els nuclis (#11).
- **Offset**: l'instant del **compàs 1** (origen de la numeració); abans seu, el
  compte enrere és ≤ 0 (com a l'app actual).

## Fases (suite verda a cada una)
1. ✅ **FET — Motor `app/tempo_map.py`**: `TempoMap` pur amb `quarters(t)` /
   `t_de_quarters(q)` (integració), `pos(t)` / `label(t)` (compàs·temps·sub),
   `bpm(t)` / `signatura(t)`, `snap(t, divisió)` i `des_de_maps(tempo, compàs)`.
   Tests: `tests/test_tempo_map.py` (16; inclou l'**equivalència** amb
   `pipeline.pos_compas` al cas constant i el compàs correcte 6/8).
2. ✅ **FET — Persistència**: `tempo.csv` (`inici,fi,bpm`) i `compas.csv`
   (`inici,fi,num,den`) a la carpeta del projecte i a les còpies de seguretat
   (`.acproj` ja porta `tempo: {bpm,bpb,offset}`). Lectors/escriptors alhora
   (`pipeline.desa_tempo_map`/`llegeix_tempo_map`); el visor carrega el mapa
   (o un **sol tros** amb el BPM·compàs actual → zero canvi visible) i el desa
   a cada edició.
3. ✅ **FET — Graella i regle**: `timeline_base` (`fmt_pos`, `snap_time`,
   `grid_plan`, `grid_positions`, `grid_levels`, `_divisions`) i les capes
   (regle i grid) accepten un `mapa` opcional; `TempoMap` guanya
   `es_constant`, `durations` i `grid_lines`. **Via constant intacta**
   (`es_constant()` → codi d'abans, tros per tros) → cap regressió; amb mapa
   variable, la graella/regle i el snap són **musicals**.
   (`pipeline.pos_compas` encara és constant; es farà a la fase 5.)
4. ✅ **FET — UI (primera versió)**: `DialegTempoMapa` (taula de trossos:
   «Des de (s)», BPM, compàs; afegir/treure) obert des d'*Analitza ▸ Mapa de
   tempo i compàs…*; `Visor.aplica_tempo_trams` normalitza (contigu, cobreix
   la WAV), actualitza el transport amb el **valor inicial** i desa. Al
   **regle** es dibuixen **marcadors** de canvi (BPM · compàs).
   ⏳ **Pendent (4b)**: pista pròpia al timeline amb vores §6.3 editables.
5. ✅ **FET — Exports/derivats**: `pipeline.pos_compas` (etiquetes de l'ABC i
   del CSV d'estructura) i la guia DAW (`acords_a_live.py`, que llegeix el
   mapa) són mapa-conscients; el **MusicXML** emet els canvis de **tempo**
   (`<sound tempo>`) al compàs on cauen. ⏳ **Pendent**: els canvis de
   **compàs** al MusicXML (cal refer la generació de compassos) i la
   **inferència** automàtica del mapa des de `beat`/`bar`/`onsets`.

## Decisions obertes
- **Rampes de tempo** lineals (sí/no i a quines fases).
- **Denominador** al compàs: l'app avui el mostra (`beat_type`) però la graella
  és de negres; el mapa ja el tracta correctament.
- **Offset** dins d'un tros (el motor ja l'ancora al compàs 1).
- Què fa el **mode fàcil** quan hi ha mapa (regularitza amb el tempo local).

## Estat
- **Fases 1-5 FETES** (motor, persistència, graella/regle/snap, diàleg
  d'edició + marcadors, i exports/derivats).
- **Pendent**: 4b (pista pròpia al timeline), compàs al MusicXML i inferència automàtica del mapa.
- L'app es comporta igual que abans (BPM·compàs constant = un sol tros → la
  via uniforme de sempre); el mapa variable ja funciona a l'engine i a la UI.
