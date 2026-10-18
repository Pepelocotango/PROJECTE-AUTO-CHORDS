# ESQUEMA VISUAL DE LA INTERFÍCIE — PROJECTE AUTO CHORDS

> Document de referència de la UI (PyQt5). Noms que fa servir el codi i
> noms «humans» de cada zona, mides reals i interaccions.
> **Actualitzat: 2026-10-18 · v0.7.0** (GUI reordenada:
> timeline al centre, barres d'eines, **pista de BPM/compàs**, franja Editor,
> metrònom, count-in, caixa d'informació, tap tempo, panell **Tipus d'acord**
> i paleta de botons unificada).

L'app és **una sola finestra** (`Finestra`, `app/main.py`) amb el **visor**
(`Visor`, `app/visor.py`) **com a widget central**. Ja no hi ha formulari
tipus assistent ni `QDockWidget` del visor.

---

## 0. Finestra principal (`Finestra`, `app/main.py`)

Títol: «**Auto Chords**» — o «**<nom del projecte> — Auto Chords**» quan hi ha un projecte obert; s'hi afig ` *` si hi ha canvis sense desar (`_actualitza_titol`) · mida per defecte 1500×900, **amplada mínima 1240 px** (perquè les barres no es tallin mai).

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Fitxer   Edita   Selecciona   Visualitza   Analitza   Ajuda               │  ← menú
├────────────────────────────────────────────────────────────────────────────┤
│ [Obre àudio] [BPM·compàs][Lliure] BPM:[101][×2][÷2] ◎Detecta TAP Compàs:[4]     │  ← BARRA 1a
│   Offset:[0.0] 📍 🧭 ≈[1.1]                                                 │     (treball)
├────────────────────────────────────────────────────────────────────────────┤
│ [Analitza] [Exporta WAV's] [Exporta partitura]                              │  ← BARRA 1b
├────────────────────────────────────────────────────────────────────────────┤     (accions)
│ ▶/⏸ □ ⏪ ⏩ ↤ ↦ ↻  🔍− 🔍+ ⛶ ⊙  🔇 🥁 ▬▬●▬                                  │  ← BARRA 2
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

> 📐 **Docks** (desacoplables i ocultables des de *Visualitza*): a l'**esquerra**, el panell **Tipus d'acord** (`dock_xifrat`, `app/panell_xifrat.py`: paleta d'arrel + baix + **62 tipus**, ▶ Escoltar i selector de timbre); a **baix**, el dock **Log · Informació** (`log_dock`). El transport i les accions són **barres d'eines** (no movibles), no docks.
>
> 🎨 **Icones REALS**: la UI fa servir icones **Lucide** (`icones/`, llicència ISC) — **no** emojis. El dibuix de dalt n'és una aproximació; el mapa real és: ▶/⏸ → `play`/`pause` · ⏹ → `square` · ⏪/⏩ → `rewind`/`fast-forward` · `A⟨`/`⟩B` → `arrow-left-to-line`/`arrow-right-to-line` · 🔁 → `repeat-2` · (neteja el loop) → `x` · 🔍−/🔍+ → `zoom-out`/`zoom-in` · ⛶ → `maximize` · ⊙ → `focus` · 🔇 → `volume-x` · 🥁 → `metronome` · 🎯 → `target` · 📍 → `map-pin` · 🧭 → `compass` · (Desfer/Refer) → `undo-2`/`redo-2` · 🎵/🎼 (Editor) → `music`/`piano`.

### Noms (codi ↔ UI) — finestra principal

| Ref | Nom al **codi** | Nom a la **UI** | Tipus |
|-----|-----------------|-----------------|-------|
| ⓪ | `Finestra` | finestra principal | `QMainWindow` |
| — | `self.offset` · `self.offset_cb` | **dos camps d'offset** (segons · compàs.beat) | `QLineEdit` |
| — | `b_obre` (local) | **Obre àudio** | `QPushButton` |
| — | `self.b_exec` | **Analitza** (F5) | `QPushButton` (`#principal`) |
| — | `self.b_export` | **Exporta WAV's** (Ctrl+E) | `QPushButton` |
| — | `self.b_export_part` | **Exporta partitura** (MusicXML; PDF/MSCZ si hi ha MuseScore) | `QPushButton` |
| — | `self.b_desfer` · `self.b_refer` | **Desfer** · **Refer** (icones `undo-2` / `redo-2`) | `QPushButton` |
| — | `self.b_obre_carpeta` | **Obre la carpeta de sortida** | `QPushButton` |
| — | (al transport; `self.b_zs` al visor) | **Zoom a la selecció** (icona `focus`, sense text) | `QPushButton` |
| — | `self.b_mode_bpm` · `self.b_mode_lliure` | selector **BPM · compàs / hh:mm:ss** (abans deia «Lliure») | `QPushButton` (checkable) |
| — | `self.bpm` · `self.bpb` · `self.offset` · `self.offset_cb` | **BPM**, **Compàs**, **Offset (s)**, **≈ C.B** | `QLineEdit` |
| — | `self.b_detecta` | **Detecta** (icona `target`) → obre el diàleg de BPM | `QPushButton` |
| — | `self.b_bpm_x2` · `self.b_bpm_div2` | **×2 / ÷2** del BPM | `QPushButton` |
| — | `self.b_compas_auto` | **Detecta el compàs 1** (icona `compass`) | `QPushButton` |
| — | `self.b_tap` | **TAP** (tecla **T**) | `QPushButton` |
| — | `self.b_offset_cursor` | **Marca el compàs 1 aquí** (icona `map-pin`) → al cursor | `QPushButton` |
| — | `self.amb_est` · `self.a_metro` · `self.a_eina_marc` | **Inclou estructura** · **Metrònom** · **Eina de marc** | `QAction` (checkable, menús) |
| — | `self.amb_part` · `self.tonalitat_auto` | **Inclou la partitura (xifrat)** · **Tonalitat automàtica** | `QAction` (checkable, menú Fitxer) |
| — | `self.b_mode_facil` · `self.b_eina` | **Mode fàcil** · **Eina: intel·ligent / Eina: marc** | `QPushButton` (el 2n, checkable) |
| — | `self._params_temps` | contenidor dels **paràmetres de temps** (BPM · ×2/÷2 · Detecta · TAP · Compàs · Offset · ≈ C.B) | `QWidget` |
| — | `self.panell_xifrat` · `self.dock_xifrat` | **panell «Tipus d'acord»** (arrel · baix · 62 tipus · ▶ Escoltar · timbre) | `PanellXifrat` en un `QDockWidget` |
| — | `self.tb_loop` · `self.tb_neteja_loop` · `self.tb_mut` | **loop** (icona `repeat-2`) · **neteja el loop** (icona `x`) · **mute** (icona `volume-x`) | `QPushButton` |
| — | `self.tb_snap` · `self.cb_graella` | **Snap** (interruptor: encaixar a la graella) + **divisió**: Auto (zoom) · Negra (1/4) · Corxera (1/8) · Semicorxera (1/16) · Fusa (1/32) · Treset (1/12) · **1 compàs · 4 · 8 · 16 compassos** | `QPushButton` (checkable) · `QComboBox` |
| — | `self.b_metro` · `self.vol_metro` | **metrònom** (icona `metronome`) · volum del clic | `QPushButton` · `QSlider` |
| — | `self.b_play_tb` | **play / pause** transport (icones `play` / `pause`) | `QPushButton` |
| — | `self.barra` | **barra de progrés** | `QProgressBar` (a la status) |
| — | `self.log` · `self.info_box` | **log** · **caixa d'informació «live»** | `QTextEdit` ×2 |
| — | `self.log_dock` | dock **«Log · Informació»** (a baix) | `QDockWidget` |

### Barres d'eines (`QToolBar`, no movibles, a dalt)

| Barra | Contingut |
|-------|-----------|
| **Treball** (barra 1, fila 1) | `Obre àudio` → **selector temps** (**BPM·compàs** / **hh:mm:ss**) → BPM · **×2/÷2** · ◎ Detecta · **TAP** · Compàs · Offset (s) · **📍** · **🧭** · ≈ C.B · **[Mode fàcil]** (`Inclou estructura` és una acció del **menú Analitza**) |
| **Accions** (barra 1, fila 2) | **Analitza** → **Exporta WAV's** → **Exporta partitura** → **Obre la carpeta de sortida** → **Desfer** (icona `undo-2`) · **Refer** (icona `redo-2`) |
| **Transport** | **`play`/`pause`** (play/pausa) · `square` · `rewind` · `fast-forward` · `arrow-left-to-line` (A) · `arrow-right-to-line` (B) · `repeat-2` (loop) · **`x` (neteja el loop)** · `zoom-out` · `zoom-in` · `maximize` (Tot) · **`focus` (zoom a la selecció)** · `volume-x` (mute) · `metronome` · volum del clic · **[Snap]** (interruptor) · **[selector de divisió de graella]** · **[Eina: intel·ligent]** (commutador; passa a «Eina: marc» — també amb la tecla `E` i al menú Selecciona) |

### Menús

| Menú | Accions |
|------|---------|
| **Fitxer** | Obre àudio… (Ctrl+O) · Obre projecte… (Ctrl+Shift+O) · Obre recent… · Desa (Ctrl+S) · Desa com… (Ctrl+Shift+S) · Desa una còpia… · Reverteix · Exporta WAV's… (Ctrl+E) · Exporta la partitura… · Inclou la partitura (xifrat) · Tonalitat automàtica (qm-keydetector) · Obre la carpeta de sortida · Surt (Ctrl+Q) |
| **Edita** | Desfer (Ctrl+Z) · Refer (Ctrl+Y) · Refer (alternatiu) (Ctrl+Shift+Z) · Retalla (Ctrl+X) · Copia (Ctrl+C) · Enganxa (Ctrl+V) · Afegeix acord… (Ctrl+Shift+A) · Afegeix secció… (Ctrl+Shift+S) · Parteix l'acord al cursor… · Parteix la secció al cursor… · Elimina element (Del) · Duplica element (Ctrl+D) · Reanomena element (F2) · Troba i reemplaça… (Ctrl+H) · Paràmetres… |
| **Selecciona** | Selecciona l'acord del cursor · Selecciona la secció del cursor · Selecciona el tram de tempo/compàs del cursor · Marca inici de loop (A) (Ctrl+[) · Marca fi de loop (B) (Ctrl+]) · Neteja el loop · Activa/desactiva loop · Eina de marc (rubber-band) |
| **Visualitza** | Zoom + (Ctrl++) · Zoom − (Ctrl+−) · Zoom total (Ctrl+0) · Mostra el log · Mostra els tipus d'acord · Metrònom |
| **Analitza** | Analitza l'àudio (F5) · Detecta el compàs 1 automàticament · Marca el compàs 1 aquí · Mode fàcil: re-regularitza a la graella… · Mapa de tempo i compàs… · Detecta el mapa de tempo (per beats)… · Inclou estructura |
| **Ajuda** | Dreceres de teclat · Obre la carpeta del registre · Quant a Auto Chords |

### Eina del timeline i abast del rang

- **Eina «intel·ligent»** (per defecte): la fletxa s'adapta al que hi ha sota —
  el cos d'un clip el mou, la vora el redimensiona, el regle fa el loop.
- **Eina «marc»**: arrossegar **no mou cap clip**; es dibuixa un **rectangle**
  (rubber-band) que **desapareix en deixar anar**, i queden seleccionats tots
  els clips que **HI SONEN** a dins — només de les pistes que el rectangle
  cobreixi, de manera que un marc només damunt dels acords agafa només acords.
  (Convenció dels DAWs: `Snap Type` del Cubase, marquee de Logic/Reaper.)
- **`Ctrl`+arrossegar = marquee TEMPORAL**: fa la funció de l'eina «marc» sense
  canviar d'eina; en deixar anar, tot torna a **intel·ligent** (és la convenció
  de l'Studio One: *«[Ctrl] in arrangement temporarily switches Tools»*). Si el
  gest és un clic sense arrossegar, es resol com a **`Ctrl`+clic = toggle**, que
  continua funcionant igual. `Ctrl+Shift`+arrossegar té prioritat (és duplicar).
- El **rang de `Shift+clic`** és sempre del **carril del clip clicat**. Per
  agafar clips de les **dues pistes** de cop, el **marquee**: `Ctrl`+arrossega
  (temporal) o l'eina «marc» (permanent).
- La **selecció no entra a la pila de desfer** (com abans).
- **Tecla `E`**: commuta l'eina (**toggle**, no on/off). Per defecte sempre
  s'arrenca en «intel·ligent».
- **`Ctrl+Shift`+arrossegar el cos d'un clip d'acord = duplicar-lo**: el clip
  viatja i a l'**origen hi torna una còpia** amb el mateix nom (l'original es
  queda a lloc). És l'**única** drecera de duplicar: `Alt`+arrossegar **no** s'hi
  fa servir perquè a Linux el gestor de finestres se l'emporta per moure la
  finestra (MATE: `<Alt>`; GNOME: `<Super>`) i `Ctrl+Shift` és lliure als 3
  sistemes. El **mateix gest val per a les seccions** (l'original es queda i
  la còpia va al destí).
- **Arrossegar el COS d'un clip = moure el BLOC** (`PLA_EDICIO_LLIURE` §6.3): el
  clip (o el bloc **contigu** seleccionat) es mou **preservant la seva durada** i,
  al **destí**, el que queda **a sota** es **talla** (se'n conserva el tros de
  fora) o **s'elimina** (si no en queda cap tros) — «**mana l'últim editat**».
  L'**origen** el tanca el veí: **endavant**, l'anterior s'estira fins a l'inici
  nou; **endarrere**, el posterior fins al final nou. El gest **ja no va limitat**
  pels veïns. Les **VORES del clip són LLIURES** (§6.6): si l'encaixament deixa
  un forat, el tanca el clip veí i, sense veí, hi apareix `N`/`-`.
- La caixa d'informació (**`_info_panells`** → `_dreceres()`) llista **totes**
  les combinacions de tecles i de ratolí (també les del diàleg *Ajuda ▸
  Dreceres de teclat*: una sola font).

> ⚠️ Les **dreceres** viuen a la **finestra principal** (`QShortcut`/`QAction`),
> mai al visor incrustat (un `QShortcut` dins el visor no s'activa).
> **Espai** = play/stop · **T** = tap tempo · **Ctrl+Z / Ctrl+Y / Ctrl+Shift+Z**
> = desfer/refer · **Del** = eliminar · **Ctrl+D** = duplicar · **F2** = reanomenar (clip o **grup del mateix tipus**) ·
> **←/→** = **nudge** un pas de graella (**Alt+←/→** = vora dreta) ·
> **Ctrl+O** = obrir WAV · **Ctrl+Shift+O** = obrir projecte · **Ctrl+S** = desar ·
> **Ctrl+Shift+S** = desar com · **Ctrl+E** = exportar · **Ctrl+[ / Ctrl+]** = loop A/B ·
> **F5** = Analitza · **Ctrl++ / Ctrl+− / Ctrl+0** = zoom +/− / total.
>
> **Multi-selecció (timeline)**: **Ctrl+clic** afegeix/treu un clip ·
> **Shift+clic** = rang **per temps, sempre del carril del clip clicat** (per agafar
> clips de **les dues pistes**, el **marquee**: `Ctrl`+arrossega o l'eina «marc») · **Del** = esborrar la selecció (grup) · **Ctrl+C/X/V**
> = copiar/retallar/enganxar la selecció **sobreescrivint** el tram (regla d'or #4: la
> cançó no pot créixer) · **Ctrl+D** = duplicar el grup ·
> **arrossegar** un clip seleccionat = moure el grup. El regle mostra el
> **mode** (`120 BPM · 4/4` o `hh:mm:ss`).

### ✅ P1 (A1–A3) — **IMPLEMENTAT i COMMITEJAT** (v0.7.0)

> Al **codi** ja hi és (committejat; suite verda):
> - ✅ **A1 — Desfer/Refer del temps i del loop**: `undo`/`redo` ara també cobreix **BPM, compàs, offset** i el **loop A-B** (nou estat de temps), no només acords/seccions.
> - ✅ **A2 — Partir una secció — FET**: acció **Edita ▸ Parteix la secció al cursor…** i entrada **«Parteix la secció…»** al menú contextual de la secció (s'activa només si el clic és en una secció i el cursor hi cau a dins). Parteix la secció que conté el cursor en dues: la meitat esquerra conserva lletra i família i la nova rep la lletra que es tria (per defecte, la mateixa). És la manera natural d'afegir secció en un model **saturat** (les seccions cobreixen tota la WAV, regla #4).
> - ✅ **Regla d'or #11 — paritat acords ↔ estructura**: els acords tenen ara les **mateixes eines** que les seccions — **Edita ▸ Parteix l'acord al cursor…**, **«Parteix l'acord…»** al menú contextual del clip i **menú de la llista d'acords** amb *Afegeix/Partir/Fusionar amb anterior/Fusionar amb següent/Elimina* (idèntic al de les seccions). El tall deixa l'esquerra amb el nom i el clip nou (dreta) amb el nom triat (per defecte, el mateix). Darrere: `pipeline.parteix_acord`/`fusiona_acords` i `visor.parteix_acord`/`fusiona_acord` (mirall dels de secció).
> - ✅ **A3 — Dreceres completes — FET**: el diàleg **Ajuda ▸ Dreceres de teclat** ara **dedueix totes les dreceres dels menús reals** (abans només en llistava 6).

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
│  ③  PISTA BPM/COMPÀS      (TempoLayer)      y 29–54   · 25 px          │
│         ┌────────────┐┌───────────┐   trams «120 · 4/4»… (només en     │
│         │ 120 · 4/4  ││  98 · 4/4 │   mode BPM · compàs; a Lliure,     │
│         └────────────┘└───────────┘   buida). clic sel. · doble edit.  │
│        ④  CARRIL ESTRUCTURA  (SectionItem)   y 60–111  · 51 px         │
│           ┌──────┐┌──────┐┌──────────┐   (semitransparent)             │
│           │ A·N  ││  B   ││   C·A    │                                 │
│           └──────┘└──────┘└──────────┘                                 │
│        ⑤  CARRIL ACORDS      (ChordItem)     y 117–168 · 51 px         │
│           ┌────┐┌─────┐┌──────┐┌────┐                                   │
│           │ N  ││ E7  ││  Em7 ││ F  │    (semitransparent)             │
│           └────┘└─────┘└──────┘└────┘                                   │
│                                                                        │
│  ⑥  GRID (GridLayer)      línies de compàs/beat/subdivisió             │
│  ⑦  CURSOR VERMELL        playhead (línia vertical)                    │
│  ⑧  BANDA LOOP A/B        rectangle taronja                            │
│  ⑨  GUIA DE SNAP          línia que apareix en arrossegar               │
├────────────────────────────────────────────────────────────────────────┤
│  ⑫  FRANJA EDITOR (ed_*)  edició directa del clip seleccionat:         │
│      [🎵/🎼] [Nom▢] [Família▢] [Inici (s)▢] [≈ ▢] [Aplica]              │
│      (sense finestres emergents; Enter = aplica)                       │
├────────────────────────────────────────────────────────────────────────┤
│  ⑩  LLISTA ACORDS (llista_ac) │ ⑪ LLISTA SECCIONS (llista_ab)          │
│     «1.1 N», «8.1 E7»…        │   «A(N) 1.1–10.1»…                     │
│     clic=salta (i ressalta)   │   clic=salta (i ressalta)              │
│     doble=edita (Editor)      │   doble=edita (Editor)                 │
│     dret=menú contextual      │   dret=menú contextual                 │
├────────────────────────────────────────────────────────────────────────┤
│  ⑬  LLISCADOR ──────●────────  │ 9.4 / 95.1 │ [🔇] │ [volum] │ stats    │
│      (posició + estatus del transport; el transport principal és a la  │
│       barra de la finestra)                                            │
└────────────────────────────────────────────────────────────────────────┘
```

> 🔗 **Clips ENCADENATS** (regles **2** i **4** de `docs/REGLES_DE_LA_APP.md`): els clips d'**estructura** i d'**acords** van **en cadena** — cada clip comença **exactament** on acaba l'anterior (sense forats ni encavalcaments), el **primer** arrenca a **0** i l'**últim** arriba a la **durada** de la WAV. La suma dels clips cobreix **tota** la durada (en qualsevol mode i amb o sense snap). Al dibuix, els clips es mostren **en contacte**, formant una cadena contínua.

### Noms (codi ↔ UI) — visor

| Ref | Nom al **codi** | Nom a la **UI** | Tipus |
|-----|-----------------|-----------------|-------|
| ① | `RulerLayer` / `self._ruler` | **regle de temps** | `QGraphicsItem` |
| ② | `WaveformLayer` / `self._waveform` | **forma d'ona** | `QGraphicsPixmapItem` |
| ③ | `TempoLayer` / `self._tempo_lane` | **pista de BPM/compàs** (trams de tempo; només en mode BPM · compàs) | `QGraphicsObject` |
| ④ | `SectionItem` / `self._section_items` | **carril estructura** | `QGraphicsObject` |
| ⑤ | `ChordItem` / `self._chord_items` | **carril acords** | `QGraphicsObject` |
| ⑥ | `GridLayer` / `self._grid` | **graella** | `QGraphicsItem` |
| ⑦ | `self._cursor` | **cursor vermell** (playhead) | `QGraphicsItem` |
| ⑧ | `self._loop_item` | **banda de loop** A/B (arrossegable: vores mouen A/B, cos mou el loop sencer) | `QGraphicsRectItem` |
| ⑨ | `self._snap_guide` | **guia de snap** | `QGraphicsLineItem` |
| — | `TimelineView` | tot el bloc ①–⑨ | `QGraphicsView` |
| ⑩ | `self.llista_ac` | **llista d'acords** | `QListWidget` |
| ⑪ | `self.llista_ab` | **llista de seccions (ABC)** | `QListWidget` |
| ⑫ | `ed_icona` · `ed_gran` · `ed_nom` · `ed_fam` · `ed_ini` · `ed_cb` · `ed_aplica` | **franja Editor** | `QLabel`/`QLineEdit`/`QPushButton` |
| ⑬ | `self.lliscador` · `self.temps` · `b_mut` · `volum` · `etiqueta` | **lliscador + estatus** | `QSlider`/`QLabel` |

> 🥁 **El transport principal** (`b_play`, `b_stop`, `b_menys`, `b_mes`, `b_A`,
> `b_B`, `b_loop`, `b_zm`, `b_zp`, `b_zt`, `b_zs`, `b_mut`, `b_metro`, `vol_metro`)
> viu a la **barra de Transport** de la finestra (3a fila). Quan el visor va incrustat, la seva fila
> interna s'amaga; el visor **standalone** encara la té.
> El visor emet **`playStateChanged(bool)`** perquè la barra de fora actualitzi
> la icona **▶ / ⏸**.

---

## 2. Interaccions (per zona)

| Zona on cliques | Acció |
|-----------------|-------|
| **Regle ① (zona buida)** | arrossegar → **crea un loop A/B** nou (amb **snap** a la graella) · clic → salta |
| **Banda loop ⑧ — vora esquerra** | arrossegar → **mou A** (inici) · cursor ↔ · tolerància ±6 px (`LOOP_GRAB_PX`) |
| **Banda loop ⑧ — vora dreta** | arrossegar → **mou B** (fi) · cursor ↔ |
| **Banda loop ⑧ — cos** | arrossegar → **mou el loop sencer** (manté la durada) · cursor ✥ |
| **Banda loop ⑧ — doble-clic** | **selecciona TOT el que hi ha dins** (acords I seccions) i posa el cursor al **final del loop** → a punt per copiar (Ctrl+C) i enganxar |
| **Banda loop ⑧ — botó dret** | **menú**: Copia/Retalla tot el que hi ha dins el loop · Enganxa al cursor |
| **Cos d'item ④⑤** | arrossegar → **mou** · `hover` = ✋ mà oberta |
| **Vora dreta ④⑤** | arrossegar → **mou el final** · `hover` = ↔ |
| **Vora esquerra ④⑤** | arrossegar → **mou l'inici** · `hover` = ↔ |
| **Clic (sense moure)** | **posa el cursor vermell** a l'inici del clip |
| **Doble-clic ④⑤ / llistes ⑩⑪** | **selecciona i enfoca l'Editor ⑫** |
| **Clic llista ⑩⑪** | salta + **ressalta la fila** (i selecciona el clip al carril) |
| **Zona buida ② + botó dret** | **pan** (desplaçar la vista) |
| **Botó dret SOBRE un clip** | **selecciona** el clip i obri el **menú contextual** — **el mateix joc a les 3 pistes** (regla #11): **Afegeix acord/secció aquí** · Duplica · Elimina · Reanomena · Parteix l'acord/la secció… · Partir per la meitat · Retalla · Copia · Enganxa |
| **Pista de tempo ③ — clic** | **selecciona** el tram de tempo/compàs i hi porta el cursor |
| **Pista de tempo ③ — doble-clic** | **diàleg** per editar-ne el valor (`_on_tempo_edit`) |
| **Pista de tempo ③ — vores** | arrossegar → **mou on canvia** el tempo (`_on_tempo_mogut`; ±5 px i cursor ↔ com als clips — regla #11) |
| **Pista de tempo ③ — botó dret** | **selecciona** el tram i obri **el mateix joc de menú que els clips** (regla #11): **Afegeix un canvi aquí** (el seu «afegir» propi) · Duplica (només si hi ha lloc després) · Elimina (només si hi ha més d'un tram) · Reanomena (BPM/compàs)… · Parteix aquest tros aquí · Partir per la meitat · Retalla · Copia · Enganxa |
| **Roda ②** | **zoom** (centrat al clip seleccionat) |
| **Espai** | **play / pausa** |
| **T** | **tap tempo** |
| **Ctrl+clic / Shift+clic** | **multi-selecció**: afegeix/treu del grup · **rang** (Shift = per temps, **sempre del carril**; per les 2 pistes, el **marquee**) |
| **Delete / Backspace** | **elimina** el clip o tota la **selecció** (grup) |
| **Ctrl+D** | **duplica** el clip o **tot el grup** seleccionat |
| **Ctrl+C / Ctrl+X / Ctrl+V** | **copiar / retallar / enganxar** la selecció — l'enganxat **sobreescriu** el tram (regla #4: la cançó no pot créixer); si no mous el cursor, enganxa just **després** del bloc i deixa el bloc enganxat **seleccionat** |
| **F2** | **reanomena** el clip seleccionat, o **tot el grup del tipus actiu** (N acords → un nom · M seccions → una lletra); amb selecció **mixta** es renombren només els del tipus del clip actiu (opció A), i el bloc queda **seleccionat** |
| **Editor ⑫ + «Aplica»** | amb **multi-selecció**, el camp **Nom** s'aplica a **tots els seleccionats del tipus actiu** (estil fulla de càlcul); l'inici NO s'aplica en bloc |
| **Ctrl+Z / Ctrl+Y** | **desfer / refer** |
| **Ctrl+H** | **troba i reemplaça** xifrats (acords) o etiquetes (estructura) a **tot el tema**; una sola operació de desfer i **no canvia cap temps** |
| **← / →** | **nudge**: mou la **vora esquerra** (l'inici) del clip seleccionat **un pas de graella**; **Alt+←/→** mou la **vora dreta** (estirar/encongir). Una sola operació de desfer; sense selecció no fa res. |
| **Ratolí sobre un botó/camp** | la **caixa d'informació** (a baix a la dreta) mostra què fa; si el ratolí **no** és sobre res amb info, hi gira un **rotatori de consells i dreceres** (cada **14 s**; el 1r panell segueix l'**eina vigent**). **Clic a la caixa** → la **para** (30 s) i el clic **següent avança** de «pantalla»; un **missatge transitori** (desfer/refer…) hi surt amb **format propi** |
| **Esc** | **anul·la**, per ordre de prioritat: (1) el **rang** en curs (`Ctrl`+arrossegar o eina «marc») · (2) un **loop a mig marcar** (el descarta i el restaura) · (3) el **loop actiu** (el desactiva i **treu la caixa groga** del timeline) · (4) **buida la selecció**; si no hi ha res d'això, no fa res. Manté el que ja feia: **cancel·la el reanomenament inline** i **tanca diàlegs** (aquests tenen prioritat) |

> ⚠️ **«Afegeix … aquí»** (el menú de les 3 pistes i la llista): els clips cobreixen
> **tota** la WAV (regla #4), així que **afegir no és inserir** un tros nou, sinó
> **obrir un clip nou** en eixe instant — **acord** = una **marca** nova (l'anterior
> s'hi acaba); **secció** = **partir** la secció que conté l'instant (la meitat
> dreta rep la lletra/família). Un **únic camí** (`visor._afegeix_a_la_posicio()`)
> per a la llista i el timeline. Detall: `docs/EDICIO_OPERACIONS.md` §1.

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
- **Commutar-lo** (o canviar-ne el volum) **no** reinicia el reproductor: el fil
  d'alimentació llig `metro_on`/`metro_vol` a **cada tros**, com fa amb el volum i
  el mute de la cançó. (Reiniciar-hi tallava l'àudio uns mil·lisegons.)
- Sense clics per sobre de **400 BPM** (`metronom.BPM_MAX`).

---

## 5. Mides i constants (`app/timeline_base.py`)

| Constant | Valor | Significat |
|----------|-------|-----------|
| `RULER_H` | 26 px | alçada del regle |
| `WAVEFORM_H` | 170 px | alçada de la pista d'ona |
| `LANE_H_FRAC` | 0.30 | alçada dels carrils d'estructura i acords = **51 px** (`LANE_H`) |
| `LANE_TEMPO_H` | 25 px | alçada de la pista de BPM/compàs (`LANE_H // 2`) |
| `LANE_TEMPO_TOP` | 29 | dalt de la pista de tempo (regla + 2 % de l'ona) |
| `LANE_SEC_TOP` | 60 | dalt del carril estructura (tempo + 4 % de l'ona) |
| `LANE_ACC_TOP` | 117 | dalt del carril acords (estructura + 4 % de l'ona) |
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
| `TL_GUIDE` `#ffb26b` | guia de snap / loop (taronja suau) |

### 5.1 Paleta dels botons (estat ences/apagat)

| Estat | Color | Botons |
|-------|-------|--------|
| **Base (apagat)** | gris «Obre àudio» `SURFACE #2a2c30` | **tots** |
| **Encès** | **blau** `ACTIU #2563eb` (+ vora `#1e40af`) | `🔁 loop`, modes `BPM·compàs`/`Lliure` |
| **Encès (especial)** | **taronja suau** `ACTIU_GROC #ffb26b` (vora `#b36a2a`) | `mute` (icona `volume-x`), `metrònom` (icona `metronome`) |
| **Acció principal** | blanc `#ffffff` | `Analitza` (`#principal`) |
| **Deshabilitat** | gris apagat `DISABLED #1e2024` | (🥁 en mode Lliure) |

> Regla clau: `QPushButton:checked` → blau; `#metro:checked, #mute:checked` → taronja suau.
> La icona de transport és **`play`** aturat / **`pause`** sonant (sense text).

> **Coordenades unificades**: TOTS els elements es posicionen amb
> `x = _x_offset + (t − _view_left) × _pps` → tot alineat amb zoom i pan.

---

## 6. Opcions d'autodetecció (diàleg) i import

### 6.1 Diàleg d'opcions (`app/dialegs.py`)

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

### 6.2 Motors d'autodetecció (Queen Mary)

`docs/QM_VAMP.md`: s'han **compilat** els plugins **`qm-vamp-plugins`** de Queen
Mary (els d'Audacity/Mixxx), **sense AVX**.

| Pestanya | Motor per defecte | Altre motor |
|----------|-------------------|-------------|
| **BPM** | `nostre` (`app/tempo.py`) | `qm`, **`consens`** |
| **Estructura** | **`qm`** (qm-segmenter) — únic motor | — |

El **`🧭`** (i Analitza ▸ «Detecta el compàs 1 automàticament») usa
`qm-onsetdetector` + `qm-barbeattracker` per posar l'offset sol (al tema de
101 dona 9,49 s).

### 6.3 Import de formats (`app/ffmpeg.py`)

`Obre àudio` accepta **wav, mp3, aif/aiff, flac, m4a, ogg, opus, wma…**. Si el
fitxer no és **WAV PCM 16 bits**, es converteix automàticament amb
`ffmpeg -vn -c:a pcm_s16le` i el WAV de treball queda al costat de l'original
com **`<nom>_convertit.wav`** (es reutilitza si ja és més nou).

---

## 7. Documents relacionats
- `docs/ESQUEMA_UI.html` i `docs/ESQUEMA_UI.svg` — aquest mateix esquema en
  **HTML** i **vectorial**, **GENERATS** d'aquest `.md` amb
  **`python3 eines/genera_esquema_ui.py`** (**no editar-los a mà**; el test
  `tests/test_esquema_ui_gen.py` ho blinda → si edites aquest `.md`, regenera'ls).
  L'**art manual** original es conserva a `ESQUEMA_UI_manual.svg`/`.html`.
- `docs/archive/AUBIO_TEMPO.md` — **[històric]** plugin d'aubio (tempo/beats), retirat.
- `docs/AUTODETECCIO_OPCIONS.md` — motors d'autodetecció, opcions i post-processat.
- `README.md` — «Estat actual» de l'app.
