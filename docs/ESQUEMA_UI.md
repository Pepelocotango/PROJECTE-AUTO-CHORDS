# ESQUEMA VISUAL DE LA INTERFÍCIE — PROJECTE AUTO CHORDS

> Document de referència de la UI (PyQt5). Noms que fa servir el codi i
> noms «humans» de cada zona, mides reals i interaccions.
> Actualitzat: 2026-10-05.

L'app té **dues finestres en una**:
1. **`Finestra`** (`app/main.py`) — la finestra principal (shell d'anàlisi).
2. **`Visor`** (`app/visor.py`) — el visor DAW-like, **incrustat** dins la
   principal com a `QDockWidget` a la dreta (es pot moure/flotar).

---

## 0. Finestra principal (`Finestra`, `app/main.py`)

Títol: «Auto Chords — wav → acords + estructura» · 1500×900.

```
┌────────────────────────────────────────────────────────────────────────────────┐
│  Ⓜ  FINESTRA PRINCIPAL  (Finestra / QMainWindow)                               │
│     «Auto Chords — wav → acords + estructura»                    [◀ Dock ▸]    │
│                                                                                │
│  ┌──────────────────────────────────────────────┐  ┌───────────────────────┐  │
│  │  Ⓜ1  GRUP «1 · Tria la wav»  (QGroupBox)      │  │  Ⓥ  DOCK «Visor»      │  │
│  │      [ /camí/al/tema.wav            ] [Tria...]│  │  (QDockWidget)        │  │
│  │                                               │  │  ┌─────────────────┐  │  │
│  │  Ⓜ2  informació de la wav  (wav_info)        │  │  │   EL VISOR      │  │  │
│  │      «tema.wav · 20,0 s · 44100 Hz…»          │  │  │   (bloc ①–⑬)    │  │  │
│  │                                               │  │  │                 │  │  │
│  │  Ⓜ3  flux  (flux_label)                       │  │  │  … vegeu §1 …   │  │  │
│  │      «Tria WAV → Processa → Revisa i edita    │  │  │                 │  │  │
│  │       → Finalitza i publica»                  │  │  │                 │  │  │
│  │                                               │  │  └─────────────────┘  │  │
│  │  ┌─ Ⓜ4  GRUP «2 · Paràmetres» (QGroupBox) ─┐  │  │                       │  │
│  │  │   BPM:                 [ 120,0 ▲▼]      │  │  │  (si no hi ha WAV:    │  │
│  │  │   Temps per compàs:    [ 4 ▲▼]          │  │  │   placeholder amb     │  │
│  │  │   Offset compàs 1 (s): [ 0,0 ▲▼]        │  │  │   «Sense WAV           │  │
│  │  │   ☐ El tema té tempo fix (BPM definit)  │  │  │    carregada…»)       │  │
│  │  │   ☑ Inclou estructura (Segmentino→ABC)  │  │  │                       │  │
│  │  └─────────────────────────────────────────┘  │  └───────────────────────┘  │
│  │                                               │                             │
│  │  ┌─ Ⓜ5  GRUP «3 · Analitza i exporta» ─────┐  │                             │
│  │  │   [ Processa ]  [ Finalitza i publica ] │  │                             │
│  │  │   ▓▓▓▓▓▓▓▓▓▓░░░░░░░░░  (barra progrés)  │  │                             │
│  │  │   ┌───────────────────────────────────┐ │  │                             │
│  │  │   │ log (QTextEdit)                   │ │  │                             │
│  │  │   └───────────────────────────────────┘ │  │                             │
│  │  └─────────────────────────────────────────┘  │                             │
│  └──────────────────────────────────────────────┘                             │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Noms (codi ↔ UI) — finestra principal

| Ref | Nom al **codi** | Nom a la **UI** | Tipus |
|-----|-----------------|-----------------|-------|
| Ⓜ | `Finestra` | finestra principal | `QMainWindow` |
| Ⓜ1 | `g1`, `wav_edit`, `b_tria` | **1 · Tria la wav** | `QGroupBox`/`QLineEdit`/`QPushButton` |
| Ⓜ2 | `self.wav_info` | info de la WAV | `QLabel` |
| Ⓜ3 | `self.flux_label` | rètol de flux | `QLabel` |
| Ⓜ4 | `g2`, `bpm`, `bpb`, `offset`, `tempo_fix`, `amb_est` | **2 · Paràmetres** | `QGroupBox` + spinboxes/checkboxes |
| Ⓜ5 | `g3`, `b_exec`, `b_export`, `barra`, `log` | **3 · Analitza i exporta** | `QGroupBox` + botons/progrés/log |
| Ⓥ | `visor_dock`, `visor_widget` | **Dock «Visor»** | `QDockWidget` |
| Ⓜ6 | `self._sc_play` | drecera **Espai** = play/pausa | `QShortcut` |

> ⚠️ El **Dock «Visor»** viu a la dreta (`Qt.RightDockWidgetArea`), és
> mòbil i flotable. Sense WAV carregada mostra un **placeholder**.

---

## 1. Visor (`Visor`, `app/visor.py`)

```
┌────────────────────────────────────────────────────────────────────────┐
│  ⓪  VISOR  (QMainWindow / dock)                                         │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  ①  REGLE DE TEMPS        (RulerLayer)      y 0–26    · 26 px    │  │
│  │      marques de BPM a sobre                              ▼        │  │
│  │      ◄── arrossega AQUÍ el ratolí per crear un LOOP A/B ──►       │  │
│  ├──────────────────────────────────────────────────────────────────┤  │
│  │  ②  FORMA D'ONA           (WaveformLayer)   fons #0f1218         │  │
│  │                                                                  │  │
│  │        ③  CARRIL ESTRUCTURA  (SectionItem)   y  32,8–86,8 · 54 px│  │
│  │           ┌──────┐┌──────┐┌──────────┐                           │  │
│  │           │  A   ││  B   ││    C     │     (semitransparent)     │  │
│  │           └──────┘└──────┘└──────────┘                           │  │
│  │                                                                  │  │
│  │        ④  CARRIL ACORDS      (ChordItem)     y 104,2–158,2 · 54 px│ │
│  │           ┌────┐┌─────┐┌──────┐┌────┐                             │  │
│  │           │ C  ││ Am  ││  F   ││ G  │       (semitransparent)     │  │
│  │           └────┘└─────┘└──────┘└────┘                             │  │
│  │                                                                  │  │
│  │  ⑤  GRID (GridLayer)      línies de compàs/beat/subdivisió        │  │
│  │  ⑥  CURSOR VERMELL        playhead (línia vertical)               │  │
│  │  ⑦  BANDA LOOP A/B        rectangle groc                          │  │
│  │  ⑧  GUIA DE SNAP          línia que apareix en arrossegar          │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  ┌───────────────────────────────┬──────────────────────────────────┐  │
│  │ ⑨  LLISTA ACORDS  (llista_ac) │ ⑩  LLISTA SECCIONS  (llista_ab)  │  │
│  │    clic = salta · dret = menú │    clic = salta · dret = menú    │  │
│  │    doble-clic = editar        │    doble-clic = editar           │  │
│  └───────────────────────────────┴──────────────────────────────────┘  │
│                                                                        │
│  ⑪  TRANSPORT   [▶ Escolta][⏹][−10s][+10s][A⟨][⟩B][🔁][🔍−][🔍+][Tot]  │
│                                                                        │
│  ⑫  LLISCADOR ─────────●──────────  │ 00:12 / 00:20 │ [🔇] [vol] [stats]│
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ ⑬  REGISTRE  (QTextEdit monospace) — log i missatges             │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

### Noms (codi ↔ UI) — visor

| Ref | Nom al **codi** | Nom a la **UI** | Tipus |
|-----|-----------------|-----------------|-------|
| ⓪ | `Visor` | finestra del visor | `QMainWindow` |
| ① | `RulerLayer` / `self._ruler` | **regle de temps** (BPM/segons) | `QGraphicsItem` |
| ② | `WaveformLayer` / `self._waveform` | **forma d'ona** | `QGraphicsItem` |
| ③ | `SectionItem` / `self._section_items` | **carril estructura** | `QGraphicsItem` |
| ④ | `ChordItem` / `self._chord_items` | **carril acords** | `QGraphicsItem` |
| ⑤ | `GridLayer` / `self._grid` | **graella** (compàs/beat/subdiv.) | `QGraphicsItem` |
| ⑥ | `self._cursor` | **cursor vermell** (playhead) | `QGraphicsItem` |
| ⑦ | `self._loop_item` | **banda de loop** A/B | `QGraphicsRectItem` |
| ⑧ | `self._snap_guide` | **guia de snap** | `QGraphicsLineItem` |
| — | `TimelineView` | tot el bloc ①–⑧ | `QGraphicsView` |
| ⑨ | `self.llista_ac` | **llista d'acords** | `QListWidget` |
| ⑩ | `self.llista_ab` | **llista de seccions (ABC)** | `QListWidget` |
| ⑪ | `b_play`, `b_stop`, `b_menys`, `b_mes`, `b_A`, `b_B`, `b_loop`, `b_zm`, `b_zp`, `b_zt` | **transports** | `QPushButton` ×10 |
| ⑫ | `self.lliscador`, `self.temps`, `b_mut`, `volum`, `etiqueta` | **barra d'estat/temps** | `QSlider`/`QLabel` |
| ⑬ | `self.registre` | **registre** (log) | `QTextEdit` |

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
| **Roda ②** | **zoom** (centrat al clip seleccionat) |
| **Botó dret llistes ⑨⑩** | menú contextual (afegir/eliminar) |
| **Espai** | **play / pausa** |
| **Ctrl+Z** | **desfer** |
| **Ctrl+Shift+Z** / **Ctrl+Y** | **refer** |

---

## 3. Mides i constants (`app/timeline.py`)

| Constant | Valor | Significat |
|----------|-------|-----------|
| `RULER_H` | 26 px | alçada del regle de temps |
| `WAVEFORM_H` | 170 px | alçada de la pista d'ona |
| `LANE_H_FRAC` | 0.32 | alçada dels carrils = 54 px |
| `LANE_SEC_TOP_FRAC` | 0.04 | dalt del carril estructura → y 32,8 |
| `LANE_ACC_TOP_FRAC` | 0.46 | dalt del carril acords → y 104,2 |
| `TOTAL_H` | 196 px | regle + ona |
| `WAVEFORM_BG` | `#0f1218` | fons de l'ona |
| `LANE_BG_A` | `#1a1d23` | fons carril (A) |
| `LANE_BG_B` | `#15181d` | fons carril (B) |
| `WAVEFORM_COLOR` | `#8ab4f8` | color de l'ona |

> **Coordenades unificades**: TOTS els elements (clips, cursor, grid,
> regle, ona, guia, loop) es posicionen amb
> `x = _x_offset + (t - _view_left) * _pps` → tot queda alineat amb
> zoom i pan. L'escena és de la mida de la viewport.
