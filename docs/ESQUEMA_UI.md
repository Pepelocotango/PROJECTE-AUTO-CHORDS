# ESQUEMA VISUAL DE LA INTERFÍCIE — PROJECTE AUTO CHORDS

> Document de referència de la UI (PyQt5). Noms que fa servir el codi i
> noms «humans» de cada zona, mides reals i interaccions.
> **Actualitzat: 2026-10-06 · v0.2.2** (GUI reordenada: timeline al centre,
> barres d'eines, metrònom, count-in, caixa d'informació).

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
│ [Obre…] [Analitza] [Exporta]  Temps:[BPM·compàs][Lliure]  BPM:[101]        │  ← BARRA 1
│   🎯[Detecta]  Compàs:[4]  Offset:[0.0] ≈ [1.1]  ☑ Inclou estructura       │     (temps)
├────────────────────────────────────────────────────────────────────────────┤
│ [▶ Escolta] [⏹] [−10s] [+10s]  [A⟨] [⟩B] [🔁]  [🔍−] [🔍+] [Tot]  [🔇] [🥁] [▬▬●▬] │  ← BARRA 2
├────────────────────────────────────────────────────────────────────────────┤     (transport)
│                                                                              │
│                          E L   V I S O R                                    │  ← CENTRAL
│   (vegeu §1: regle · ona · carrils · llistes · lliscador)                   │
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
| — | `self.b_exec` | **Analitza** (F5) | `QPushButton` |
| — | `self.b_export` | **Exporta** (Ctrl+E) | `QPushButton` |
| — | `self.b_mode_bpm` · `self.b_mode_lliure` | selector **BPM · compàs / Lliure** | `QPushButton` (2 estats) |
| — | `self.bpm` · `self.bpb` · `self.offset` · `self.offset_cb` | **BPM**, **Compàs**, **Offset (s)**, **≈ C.B** | `QLineEdit` |
| — | `self.b_detecta` | **🎯 Detecta** | `QPushButton` |
| — | `self.amb_est` | **Inclou estructura** | `QCheckBox` |
| — | `self.tb_loop` · `self.tb_mut` | **🔁 loop** · **🔇 mute** (barra) | `QPushButton` (checkable) |
| — | `self.b_metro` · `self.vol_metro` | **🥁 metrònom** · volum del clic | `QPushButton` · `QSlider` |
| — | `self.barra` | **barra de progrés** | `QProgressBar` (a la status) |
| — | `self.log` · `self.info_box` | **log** · **caixa d'informació «live»** | `QTextEdit` ×2 |
| — | `self.log_dock` | dock **«Log · Informació»** (a baix) | `QDockWidget` |

### Barres d'eines (`QToolBar`, no movibles, a dalt)

| Barra | Contingut |
|-------|-----------|
| **Principal / temps** | `Obre…` · `Analitza` · `Exporta` · selector temps · BPM · 🎯 Detecta · Compàs · Offset (s) · ≈ C.B · Inclou estructura |
| **Transport** | `▶ Escolta` · `⏹` · `−10s` · `+10s` · `A⟨` · `⟩B` · `🔁` · `🔍−` · `🔍+` · `Tot` · `🔇` · `🥁` · volum del clic |

> ⚠️ Les **dreceres** viuen a la **finestra principal** (`QShortcut`/`QAction`),
> mai al visor incrustat (un `QShortcut` dins el visor no s'activa).
> **Espai** = play/stop · **Ctrl+Z / Ctrl+Y** = desfer/refer · **Del** = eliminar ·
> **Ctrl+D** = duplicar · **Ctrl+O** = obrir · **Ctrl+E** = exportar ·
> **Ctrl+1..9** = … (vegeu menús) · **F5** = Analitza.

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
│  ⑨  LLISTA ACORDS (llista_ac) │ ⑩ LLISTA SECCIONS (llista_ab)          │
│     «1.1 N», «8.1 E7»…        │   «A(N) 1.1–10.1»…                     │
│     clic=salta · doble=edita  │   clic=salta · doble=edita             │
│     dret=menú contextual      │   dret=menú contextual                 │
├────────────────────────────────────────────────────────────────────────┤
│  ⑫  LLISCADOR ──────●────────  │ 9.4 / 95.1 │ [⏹] │ [volum] │ stats    │
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
| ⑫ | `self.lliscador` · `self.temps` · `b_mut` · `volum` · `etiqueta` | **lliscador + estatus** | `QSlider`/`QLabel` |

> 🥁 **El transport principal** (`b_play`, `b_stop`, `b_menys`, `b_mes`, `b_A`,
> `b_B`, `b_loop`, `b_zm`, `b_zp`, `b_zt`, `b_mut`, `b_metro`, `vol_metro`)
> viu a la **barra 2 de la finestra** (PAS 5). Quan el visor va incrustat, la
> seva fila interna s'amaga; el visor **standalone** encara la té.

---

## 2. Interaccions (per zona)

| Zona on cliques | Acció |
|-----------------|-------|
| **Regle ①** | arrossegar → **crea loop A/B** · clic → salta |
| **Cos d'item ③④** | arrossegar → **mou** · `hover` = ✋ mà oberta |
| **Vora dreta ③④** | arrossegar → **mou el final** · `hover` = ↔ |
| **Vora esquerra ③④** | arrossegar → **mou l'inici** · `hover` = ↔ |
| **Clic (sense moure)** | **posa el cursor vermell** a l'inici del clip |
| **Doble-clic ③④ / llistes ⑨⑩** | **editar** (nom + inici) |
| **Zona buida ② + botó dret** | **pan** (desplaçar la vista) |
| **Botó dret SOBRE un clip** | **menú contextual**: Duplica · Elimina · Reanomena |
| **Roda ②** | **zoom** (centrat al clip seleccionat) |
| **Espai** | **play / pausa** |
| **Delete / Backspace** | **elimina** el clip seleccionat |
| **Ctrl+D** | **duplica** el clip seleccionat |
| **Ctrl+Z / Ctrl+Y** | **desfer / refer** |
| **Ratolí sobre un botó/camp** | la **caixa d'informació** (a baix a la dreta) mostra què fa |

---

## 3. Temps: BPM i offset

- **BPM** = la velocitat (un cop cada `60/BPM` segons).
- **Offset** = el segon on cau el **compàs 1** (la fase de la graella).
- **Dos camps sincronitzats**: `Offset` (segons) i `≈ C.B` (compàs.beat,
  **relatiu a la graella original amb offset = 0** → estable, llegible).
- **Analitza ▸ «Marca el compàs 1 aquí»** → posa l'offset on és el cursor.
- Abans de l'offset la graella és **negativa** (`-3.1 … -1.3`) = **count-in**
  (i el metrònom també el clica).
- **🎯 Detecta** només el **BPM** (autocorrelació d'onsets + comb, numpy;
  `app/tempo.py`); **no** toca l'offset.

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

**Colors** (`app/theme.py`, NO al codi del timeline):

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
| `METRO_ACTIU` `#ffd166` | botó/acció del metrònom activat |

> **Coordenades unificades**: TOTS els elements es posicionen amb
> `x = _x_offset + (t − _view_left) × _pps` → tot alineat amb zoom i pan.

---

## 6. Documents relacionats
- `docs/AUBIO_TEMPO.md` — plugin d'aubio (tempo/beats).
- `docs/REVISIO_METRONOM.diff` · `docs/REVISIO_REORG_METRONOM.diff` — diffs
  anotats per a revisió externa.
- `README.md` — «Estat actual» de l'app.
