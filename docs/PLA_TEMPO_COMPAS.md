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
   ✅ **4b FET**: **3 pistes** al timeline (BPM/compàs · estructura · acords);
   la de BPM/compàs amb **mitja alçada**, només visible en mode **BPM·compàs**
   i amb mapa variable. És **EDITABLE**: clic a un bloc → diàleg `BPM`/`compàs`
   (`DialegTramTempo`); arrossegar una **vora** → mou on canvia; **botó dret** →
   afegir/editar/eliminar (`afegeix_tall`/`elimina_tall`). Tot alimenta el
   mateix mapa (una sola font).
5. ✅ **FET — Exports/derivats**: `pipeline.pos_compas` (etiquetes de l'ABC i
   del CSV d'estructura) i la guia DAW (`acords_a_live.py`, que llegeix el
   mapa) són mapa-conscients; el **MusicXML** emet els canvis de **tempo**
   (`<sound tempo>`) al compàs on cauen, i els canvis de **compàs** amb
   `<attributes><time>` a cada compassos amb signatura nova
   (`mapa.compassos_beats()`); verificat 18-10-2026: 4/4 → 3/4 surten tots dos.
   La **inferència** automàtica del mapa des dels `beat` detectats tambe hi es
   (`tempo_map.infereix_trams_beat`, accio «Detecta el mapa de tempo (per
   beats)…» del menu Analitza i l'eina MCP `ac_detecta_tempo_mapa`).

## Decisions preses (no són pendents)
- **Rampes de tempo lineals**: NO s'implementen. El mapa és de **trams
  discrets** (un BPM per tram) i el motor n'és coherent a tots els punts; les
  rampes queden com a **idea futura**, sense res a mig fer.
- **Denominador del compàs**: el `beat_type` es mostra i s'exporta (`<beat-type>`
  del MusicXML) i el mapa calcula cada compàs amb `num·4/den`; la
  **graella/quantització del timeline és de negres** (la unitat del MusicXML i
  la que fan servir els DAW per defecte) — simplificació **deliberada**.
- **Offset dins d'un tros**: no se suporta. El motor **ancora l'origen al
  compàs 1** (`mapa.offset`) i tots els trams hereten aquesta numeració.
- **Mode fàcil amb un mapa**: regularitza el ritme harmònic amb el **BPM/compàs
  de la barra** (amb mapa, el del PRIMER tram) — una sola graella per a tot el
  tema. És una **limitació coneguda**: en temes amb canvis de tempo forts, si
  cal precisió, treballa en mode constant (un sol tram). *(Idea futura:
  regularitzar amb la graella LOCAL de cada tram; avui el nucli
  `graella.regularitza_clips` treballa amb un pas fix.)*

## Estat
- **Fases 1-5 i 4b FETES** (motor, persistència, graella/regle/snap,
  diàleg d'edició + marcadors, exports/derivats amb compàs al MusicXML i
  inferència automàtica, i **pista al timeline**).
- ✅ **FET (18-10-2026)** — la pista del timeline queda **completa**: a més de
  les vores i el cos editables (§6.3), hi ha **nudge** `←`/`→`+`Alt`,
  **desfer/refer** del mapa, **selecció** (rang, marquee, LOOP, `Ctrl`+clic),
  **porta-retalls** (`Ctrl+C/X/V`), **duplicar** (`Ctrl+D`) i **eines MCP**
  (`ac_list_tempo`, `ac_afegeix_tall`, `ac_elimina_tall`, `ac_mou_tall`).
- L'app es comporta igual que abans (BPM·compàs constant = un sol tros → la
  via uniforme de sempre); el mapa variable ja funciona a l'engine i a la UI.
