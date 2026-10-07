# ESQUEMA VISUAL DE LA INTERFÍCIE — PROJECTE AUTO CHORDS

> Document de referència de la UI (PyQt5). Noms que fa servir el codi i
> noms «humans» de cada zona, mides reals i interaccions.
> **Actualitzat: 2026-10-07 · v0.4.0** (GUI reordenada:
> timeline al centre, barres d'eines, franja Editor, metrònom, count-in,
> caixa d'informació, tap tempo i paleta de botons unificada).

L'app és **una sola finestra** (`Finestra`, `app/main.py`) amb el **visor**
(`Visor`, `app/visor.py`) **com a widget central**. Ja no hi ha formulari
tipus assistent ni `QDockWidget` del visor.

---

## 0. Finestra principal (`Finestra`, `app/main.py`)

Títol: «**<fitxer.wav> — Auto Chords**» · mida per defecte 1500×900.

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Fitxer   Edita   Selecciona   Visualitza   Analitza   Ajuda               │  ← menú
├────────────────────────────────────────────────────────────────────────────┤
│ [Obre…] Temps:[BPM·compàs][Lliure] BPM:[101][×2][÷2] 🎯[Detecta][TAP] Compàs:[4] │  ← BARRA 1
│   Offset:[0.0] [📍] ≈[1.1] ☑ Inclou estructura   [Analitza]   [Exporta]     │     (treball)
├────────────────────────────────────────────────────────────────────────────┤
│ [▶/⏸] [⏹] [−10s] [+10s]  [A⟨] [⟩B] [🔁]  [🔍−] [🔍+] [Tot]  [🔇] [🥁] [▬▬●] │  ← BARRA 2
├────────────────────────────────────────────────────────────────────────────┤     (transport)
│                                                                              │
│                          E L   V I S O R                                    │  ← CENTRAL
│   (vegeu §1: regle · ona · carrils · franja EDITOR · llistes · lliscador)   │
│                                                                              │
├────────────────────────────────────────────────────────────────────────────┤
│ ┌─ Log · Informació ───────────────────────────────────────────────────────┐ │  ← DOCK (baix)
│ │  [log de l'anàlisi          (3/4)]        │  [info del widget   (1/4)]  │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────────────────┤
│ 223.4 s · 2 canals · 44100 Hz                              [▓▓▓▓░░] progrés  │  ← BARRA D'ESTAT
└────────────────────────────────────────────────────────────────────────────┘
```

### Noms (codi ↔ UI) — finestra principal

| Ref | Nom al **codi** | Nom a la **UI** | Tipus |
|-----|-----------------|-----------------|-------|
| ⓪ | `Finestra` | finestra principal | `QMainWindow` |
| — | `self.offset` · `self.offset_cb` | **dos camps d'offset** (segons · compàs.beat) | `QLineEdit` |
| — | `self.b_obre` | **Obre…** | `QPushButton` |
| — | `self.b_exec` | **Analitza** (F5) | `QPushButton` (`#principal`) |
| — | `self.b_export` | **Exporta** (Ctrl+E) | `QPushButton` |
| — | `self.b_mode_bpm` · `self.b_mode_lliure` | selector **BPM · compàs / Lliure** | `QPushButton` (checkable) |
| — | `self.bpm` · `self.bpb` · `self.offset` · `self.offset_cb` | **BPM**, **Compàs**, **Offset (s)**, **≈ C.B** | `QLineEdit` |
| — | `self.b_detecta` | **🎯 Detecta** (obre el diàleg de BPM) | `QPushButton` |
| — | `self.b_bpm_x2` · `self.b_bpm_div2` | **×2 / ÷2** del BPM | `QPushButton` |
| — | `self.b_compas_auto` | **🧭** detecta el compàs 1 automàticament | `QPushButton` |
| — | `self.b_tap` | **TAP** (tecla **T**) | `QPushButton` |
| — | `self.b_offset_cursor` | **📍** → compàs 1 al cursor | `QPushButton` |
| — | `self.amb_est` | **Inclou estructura** | `QCheckBox` |
| — | `self.tb_loop` · `self.tb_mut` | **🔁 loop** · **🔇 mute** (barra) | `QPushButton` (checkable) |
| — | `self.b_metro` · `self.vol_metro` | **🥁 metrònom** · volum del clic | `QPushButton` · `QSlider` |
| — | `self.b_play_tb` | **▶ / ⏸** transport (icona commutable) | `QPushButton` |
| — | `self.barra` | **barra de progrés** | `QProgressBar` (a la status) |
| — | `self.log` · `self.info_box` | **log** · **caixa d'informació «live»** | `QTextEdit` ×2 |
| — | `self.log_dock` | dock **«Log · Informació»** (a baix) | `QDockWidget` |

### Barres d'eines (`QToolBar`, no movibles, a dalt)

| Barra | Contingut |
|-------|-----------|
| **Treball** (ordre del flux) | `Obre…` → **selector temps** (BPM·compàs/Lliure) → BPM · **×2/÷2** · 🎯 Detecta · **TAP** · Compàs · Offset (s) · **📍** · **🧭** · ≈ C.B → **Inclou estructura** → **Analitza** → **Exporta** |
| **Transport** | **▶/⏸** (play/pausa) · `⏹` · `−10s` · `+10s` · `A⟨` · `⟩B` · `🔁` · `🔍−` · `🔍+` · `Tot` · `🔇` · `🥁` · volum del clic |

### Menús

| Menú | Accions |
|------|---------|
| **Fitxer** | Obre… (Ctrl+O) · Exporta (Ctrl+E) · Sortir |
| **Edita** | Desfer (Ctrl+Z) · Refer (Ctrl+Y / Ctrl+Shift+Z) · **Afegeix acord/secció** · **Elimina** (Del) · **Duplica** (Ctrl+D) · **Reanomena** (F2) |
| **Selecciona** | Acord del cursor · Secció del cursor · **Loop A/B** (Ctrl+[ / Ctrl+]) · Neteja loop |
| **Visualitza** | Zoom (🔍−/🔍+) · Tot · Metrònom (🥁) |
| **Analitza** | Detecta BPM (🎯) · Analitza · **Marca el compàs 1 aquí** (📍) |
| **Ajuda** | Dreceres · Quant a |

> ⚠️ Les **dreceres** viuen a la **finestra principal** (`QShortcut`/`QAction`),
> mai al visor incrustat (un `QShortcut` dins el visor no s'activa).
> **Espai** = play/stop · **T** = tap tempo · **Ctrl+Z / Ctrl+Y / Ctrl+Shift+Z**
> = desfer/refer · **Del** = eliminar · **Ctrl+D** = duplicar · **F2** = reanomenar ·
> **Ctrl+O** = obrir · **Ctrl+E** = exportar · **Ctrl+[ / Ctrl+]** = loop A/B ·
> **Ctrl+1..9** = menús · **F5** = Analitza.

---

## 1. Visor (`Visor`, `app/visor.py`) — widget central

```
┌────────────────────────────────────────────────────────────────────────┐
│  ①  REGLE DE TEMPS        (RulerLayer)      y 0–26    · 26 px          │
│      etiquetes compàs.beat (o gt; amb offset, abans del compàs 1 són   │
│      NEGATIVES = compte enrere / count-in)                             │
│      ◄── arrossega AQUÍ el ratolí per crear un LOOP A/B ──►            │
├────────────────────────────────────────────────────────────────────────┤
│  ②  FORMA D'ONA           (WaveformLayer)   fons #0f1218               │
│                                                                        │
│        ③  CARRIL ESTRUCTURA  (SectionItem)   y 32,8–86,8 · 54 px       │
│           ┌──────┐┌──────┐┌──────────┐   (semitransparent)             │
│           │ A·N  ││  B   ││   C·A    │                                 │
│           └──────┘└──────┘└──────────┘                                 │
│        ④  CARRIL ACORDS      (ChordItem)     y 104,2–158,2 · 54 px     │
│           ┌────┐┌─────┐┌──────┐┌────┐                                   │
│           │ N  ││ E7  ││  Em7 ││ F  │    (semitransparent)             │
│           └────┘└─────┘└──────┘└────┘                                   │
│                                                                        │
│  ⑤  GRID (GridLayer)      línies de compàs/beat/subdivisió             │
│  ⑥  CURSOR VERMELL        playhead (línia vertical)                    │
│  ⑦  BANDA LOOP A/B        rectangle groc                               │
│  ⑧  GUIA DE SNAP          línia que apareix en arrossegar               │
├────────────────────────────────────────────────────────────────────────┤
│  ⑪  FRANJA EDITOR (ed_*)  edició directa del clip seleccionat:         │
│      [🎵/🎼] [Nom▢] [Família▢] [Inici (s)▢] [≈ ▢] [Aplica]              │
│      (sense finestres emergents; Enter = aplica)                       │
├────────────────────────────────────────────────────────────────────────┤
│  ⑨  LLISTA ACORDS (llista_ac) │ ⑩ LLISTA SECCIONS (llista_ab)          │
│     «1.1 N», «8.1 E7»…        │   «A(N) 1.1–10.1»…                     │
│     clic=salta (i ressalta)   │   clic=salta (i ressalta)              │
│     doble=edita (Editor)      │   doble=edita (Editor)                 │
│     dret=menú contextual      │   dret=menú contextual                 │
├────────────────────────────────────────────────────────────────────────┤
│  ⑫  LLISCADOR ──────●────────  │ 9.4 / 95.1 │ [🔇] │ [volum] │ stats    │
│      (posició + estatus del transport; el transport principal és a la  │
│       barra de la finestra)                                            │
└────────────────────────────────────────────────────────────────────────┘
```

### Noms (codi ↔ UI) — visor

| Ref | Nom al **codi** | Nom a la **UI** | Tipus |
|-----|-----------------|-----------------|-------|
| ① | `RulerLayer` / `self._ruler` | **regle de temps** | `QGraphicsItem` |
| ② | `WaveformLayer` / `self._waveform` | **forma d'ona** | `QGraphicsPixmapItem` |
| ③ | `SectionItem` / `self._section_items` | **carril estructura** | `QGraphicsObject` |
| ④ | `ChordItem` / `self._chord_items` | **carril acords** | `QGraphicsObject` |
| ⑤ | `GridLayer` / `self._grid` | **graella** | `QGraphicsItem` |
| ⑥ | `self._cursor` | **cursor vermell** (playhead) | `QGraphicsItem` |
| ⑦ | `self._loop_item` | **banda de loop** A/B | `QGraphicsRectItem` |
| ⑧ | `self._snap_guide` | **guia de snap** | `QGraphicsLineItem` |
| — | `TimelineView` | tot el bloc ①–⑧ | `QGraphicsView` |
| ⑨ | `self.llista_ac` | **llista d'acords** | `QListWidget` |
| ⑩ | `self.llista_ab` | **llista de seccions (ABC)** | `QListWidget` |
| ⑪ | `ed_icona` · `ed_gran` · `ed_nom` · `ed_fam` · `ed_ini` · `ed_cb` · `ed_aplica` | **franja Editor** | `QLabel`/`QLineEdit`/`QPushButton` |
| ⑫ | `self.lliscador` · `self.temps` · `b_mut` · `volum` · `etiqueta` | **lliscador + estatus** | `QSlider`/`QLabel` |

> 🥁 **El transport principal** (`b_play`, `b_stop`, `b_menys`, `b_mes`, `b_A`,
> `b_B`, `b_loop`, `b_zm`, `b_zp`, `b_zt`, `b_mut`, `b_metro`, `vol_metro`)
> viu a la **barra 2 de la finestra**. Quan el visor va incrustat, la seva fila
> interna s'amaga; el visor **standalone** encara la té.
> El visor emet **`playStateChanged(bool)`** perquè la barra de fora actualitzi
> la icona **▶ / ⏸**.

---

## 2. Interaccions (per zona)

| Zona on cliques | Acció |
|-----------------|-------|
| **Regle ①** | arrossegar → **crea loop A/B** · clic → salta |
| **Cos d'item ③④** | arrossegar → **mou** · `hover` = ✋ mà oberta |
| **Vora dreta ③④** | arrossegar → **mou el final** · `hover` = ↔ |
| **Vora esquerra ③④** | arrossegar → **mou l'inici** · `hover` = ↔ |
| **Clic (sense moure)** | **posa el cursor vermell** a l'inici del clip |
| **Doble-clic ③④ / llistes ⑨⑩** | **selecciona i enfoca l'Editor ⑪** |
| **Clic llista ⑨⑩** | salta + **ressalta la fila** (i selecciona el clip al carril) |
| **Zona buida ② + botó dret** | **pan** (desplaçar la vista) |
| **Botó dret SOBRE un clip** | **menú contextual**: Duplica · Elimina · Reanomena |
| **Roda ②** | **zoom** (centrat al clip seleccionat) |
| **Espai** | **play / pausa** |
| **T** | **tap tempo** |
| **Delete / Backspace** | **elimina** el clip seleccionat |
| **Ctrl+D** | **duplica** el clip seleccionat |
| **F2** | **reanomena** el clip seleccionat |
| **Ctrl+Z / Ctrl+Y** | **desfer / refer** |
| **Ratolí sobre un botó/camp** | la **caixa d'informació** (a baix a la dreta) mostra què fa |

---

## 3. Temps: BPM, offset i tap tempo

- **BPM** = la velocitat (un cop cada `60/BPM` segons).
- **Offset** = el segon on cau el **compàs 1** (la fase de la graella).
- **Dos camps sincronitzats**: `Offset` (segons) i `≈ C.B` (compàs.beat,
  **relatiu a la graella original amb offset = 0** → estable, llegible).
- **📍 botó** (i **Analitza ▸ «Marca el compàs 1 aquí»**) → llegeix el **cursor
  vermell** i hi posa l'offset.
- Abans de l'offset la graella és **negativa** (`-3.1 … -1.3`) = **count-in**
  (i el metrònom també el clica).
- **🎯 Detecta** només el **BPM** (autocorrelació d'onsets + comb, numpy;
  `app/tempo.py`); **no** toca l'offset.
- **TAP** (tecla **T**): patró estàndard dels DAWs — guarda els instants dels
  últims taps, **mitjana dels intervals** → `60/∅`; **reset als 2 s** (LMMS);
  **descarta intervals fora de 30–300 BPM** (Max/Dobrian). Propaga BPM al regle
  i al metrònom **sense reengegar l'àudio**. El botó mostra `TAP (n) BPM`.

## 4. Metrònom 🥁

- Només en mode **BPM · compàs** (gris a Lliure).
- Volum propi (60 % per defecte); el mute/volum de la cançó **no** l'afecta.
- El clic es **mescla al mateix buffer** que s'envia al reproductor (sense
  QTimer ni segon procés → no deriva). Accent (temps 1) ≈ 1500 Hz; resta ≈ 1000.
- Sense clics per sobre de **400 BPM** (`metronom.BPM_MAX`).

---

## 5. Mides i constants (`app/timeline.py`)

| Constant | Valor | Significat |
|----------|-------|-----------|
| `RULER_H` | 26 px | alçada del regle |
| `WAVEFORM_H` | 170 px | alçada de la pista d'ona |
| `LANE_H_FRAC` | 0.32 | alçada dels carrils = 54 px |
| `LANE_SEC_TOP_FRAC` | 0.04 | dalt carril estructura → y 32,8 |
| `LANE_ACC_TOP_FRAC` | 0.46 | dalt carril acords → y 104,2 |
| `TOTAL_H` | 196 px | regle + ona |

**Colors del timeline** (`app/theme.py`, NO al codi del timeline):

| Clau | Ús |
|------|-----|
| `TL_BG` `#0f1218` | fons de l'ona |
| `TL_LANE_BG_A/B` `#1a1d23`/`#15181d` | fons carrils |
| `TL_WAVEFORM` `#8ab4f8` | ona |
| `CLIP_FILL` `#2e3844` | clip normal |
| `CLIP_ACTIVE_FILL` `#1f5c3d` | **actiu** (el que sona) |
| `CLIP_SELECTED_BORDER` `#38bdf8` | **seleccionat** (vora cian, 3 px) |
| `TL_CURSOR` `#ff6b6b` | cursor vermell |
| `TL_GUIDE` `#ffd166` | guia de snap / loop |

### 5.1 Paleta dels botons (estat ences/apagat)

| Estat | Color | Botons |
|-------|-------|--------|
| **Base (apagat)** | gris «Obre…» `SURFACE #2a2c30` | **tots** |
| **Encès** | **blau** `ACTIU #2563eb` (+ vora `#1e40af`) | `🔁 loop`, modes `BPM·compàs`/`Lliure` |
| **Encès (especial)** | **groc** `ACTIU_GROC #ffd166` | `🔇 mute`, `🥁 metrònom` |
| **Acció principal** | blanc `#ffffff` | `Analitza` (`#principal`) |
| **Deshabilitat** | gris apagat `DISABLED #2f3238` | (🥁 en mode Lliure) |

> Regla clau: `QPushButton:checked` → blau; `#metro:checked, #mute:checked` → groc.
> La icona de transport és **▶** aturat / **⏸** sonant (sense text).

> **Coordenades unificades**: TOTS els elements es posicionen amb
> `x = _x_offset + (t − _view_left) × _pps` → tot alineat amb zoom i pan.

---

## 7. Opcions d'autodetecció (diàleg) i import

### 7.1 Diàleg d'opcions (`app/dialegs.py`)

En clicar **`🎯 Detecta`** (obre a **BPM**) o **`Analitza`** (obre a **Acords**)
surt un `QDialog` amb 3 pestanyes + «Restaura per defecte»:

| Pestanya | Controls |
|----------|----------|
| **BPM** | rang de cerca (min/max) i rang preferit |
| **Acords** | els **6 paràmetres del Chordino** (construïts del descriptor `.n3`) + **neteja posterior** |
| **Estructura** | durada mínima de secció + fusionar trossos iguals |

La pestanya **Acords** es genera **dinàmicament** des de `app/vamp_params.py`
(checkbox pels 0/1, combo quan el paràmetre té noms, spinbox pels numèrics).
Els títols són **en català** amb l'`id` del plugin a sota i una **ajuda**
(tooltip). Es passen al motor amb un transform `.ttl` (`pipeline.escriu_ttl`
+ `sonic-annotator -t`).

**Neteja posterior** (`app/postproc.py`): treure el baix (`A/E`→`A`), reduir
(`Cmaj7`→`C`), fusionar iguals, durada mínima i encaixar a la graella.

Les opcions es **recorden** a `opcions_detecta.json` (gitignored).

### 7.2 Motors d'autodetecció (Queen Mary)

`docs/QM_VAMP.md`: s'han **compilat** els plugins **`qm-vamp-plugins`** de Queen
Mary (els d'Audacity/Mixxx), **sense AVX**.

| Pestanya | Motor per defecte | Altre motor |
|----------|-------------------|-------------|
| **BPM** | `nostre` (`app/tempo.py`) | `qm`, `aubio`, **`consens`** |
| **Estructura** | **`qm`** (qm-segmenter) | `segmentino` |

El **`🧭`** (i Analitza ▸ «Detecta el compàs 1 automàticament») usa
`qm-onsetdetector` + `qm-barbeattracker` per posar l'offset sol (al tema de
101 dona 9,49 s).

### 7.3 Import de formats (`app/ffmpeg.py`)

`Obre…` accepta **wav, mp3, aif/aiff, flac, m4a, ogg, opus, wma…**. Si el
fitxer no és **WAV PCM 16 bits**, es converteix automàticament amb
`ffmpeg -vn -c:a pcm_s16le` i el WAV de treball queda al costat de l'original
com **`<nom>_convertit.wav`** (es reutilitza si ja és més nou).

---

## 6. Documents relacionats
- `docs/AUBIO_TEMPO.md` — plugin d'aubio (tempo/beats).
- `docs/AUTODETECCIO_OPCIONS.md` — motors d'autodetecció, opcions i post-processat.
- `docs/REVISIO_METRONOM.diff` · `docs/REVISIO_REORG_METRONOM.diff` — diffs
  anotats per a revisió externa.
- `README.md` — «Estat actual» de l'app.
