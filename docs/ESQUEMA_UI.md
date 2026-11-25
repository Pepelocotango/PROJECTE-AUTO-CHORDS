# ESQUEMA VISUAL DE LA INTERFÍCIE — PROJECTE AUTO CHORDS

> Document de referència de la UI (PyQt5). Noms que fa servir el codi i
> noms «humans» de cada zona, mides reals i interaccions.
> **Actualitzat: 2026-10-18 · v0.7.0** (GUI reordenada:
> timeline al centre, barres d'eines, **pista de BPM/compàs**, franja Editor,
> metrònom, caixa d'informació, tap tempo, panell **Tipus d'acord**
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
│ [Guia ràpida][BPM·compàs][Lliure] TAP TAP→ 🔓BPM 🔓N 🔓x/x BPM:80.000      │  ← BARRA 1a
│   Compàs:6/8                                                               │     (treball)
├────────────────────────────────────────────────────────────────────────────┤
│ [Analitza]                                                                  │  ← BARRA 1b
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

> 📐 **Docks** (desacoplables i ocultables des de *Visualitza*): a l'**esquerra**, el panell **Tipus d'acord** (`dock_xifrat`, `app/panell_xifrat.py`: paleta d'arrel + baix + **92 tipus**, ▶ Escoltar i selector de timbre), **tancat per defecte**; a **baix**, el dock **Log · Informació** (`log_dock`). El transport i les accions són **barres d'eines** (no movibles), no docks.
>
> 🎨 **Icones REALS**: la UI fa servir icones **Lucide** (`icones/`, llicència ISC) — **no** emojis. El dibuix de dalt n'és una aproximació; el mapa real és: ▶/⏸ → `play`/`pause` · ⏹ → `square` · ⏪/⏩ → `rewind`/`fast-forward` · `A⟨`/`⟩B` → `arrow-left-to-line`/`arrow-right-to-line` · 🔁 → `repeat-2` · (neteja el loop) → `x` · 🔍−/🔍+ → `zoom-out`/`zoom-in` · ⛶ → `maximize` · ⊙ → `focus` · 🔇 → `volume-x` · 🥁 → `metronome` · 🎯 → `target` · (Desfer/Refer) → `undo-2`/`redo-2` · 🎵/🎼 (Editor) → `music`/`piano`.

### Noms (codi ↔ UI) — finestra principal

| Ref | Nom al **codi** | Nom a la **UI** | Tipus |
|-----|-----------------|-----------------|-------|
| ⓪ | `Finestra` | finestra principal | `QMainWindow` |
| — | `self.b_guia` | **Guia ràpida**: obri `DialegGuiaRapida`, que delega les accions al visor. Té **Proposa inici**, **Proposa final**, **Proposa BPM**, **Comprova estabilitat**, **Proposa mapa**, **Aplica BPM** i **Aplica mapa**. Les propostes calculen onsets, `e(t)`, gap, inliers i un mapa d’un sol BPM; no apliquen res. **Aplica BPM** aplica el BPM triat: al clip de tempo seleccionat sense moure fronteres o, si no n’hi ha, substituint el mapa amb confirmació. **Aplica mapa** aplica la proposta amb confirmació, conserva els clips de fora del rang i exigix que els marcadors coincidisquen amb una frontera; un sol desfer. Si no hi ha mapa, proposa un clip de tota la WAV. Els talls es fan amb `＋` / `Fin` / `0`; `M` afig marcadors independents. Sense WAV, desactivat | `QPushButton` |
| — | `self.b_lock_bpm` · `self.b_lock_n` · `self.b_lock_compas` | **Candaus del mapa de tempo** (icona oberta/tancada): bloquegen globalment els canvis de **BPM intern**, **N de compassos** i **x/x**. Són independents, comencen desactivats, no es guarden entre sessions i **no permeten més de dos actius**. Les anàlisis automàtiques poden executar-se; si l’usuari confirma una aplicació, els candaus es respecten. Les operacions que canviarien un camp bloquejat es rebutgen senceres | `QPushButton` (checkable) ×3 |
| — | `self.b_audio_ini` · `self.b_audio_fi` | **Ajusta inici WAV** · **Ajusta final WAV**: obrin `DialegQuadratura` ja enfocat a l'inici o al final. No apliquen res sense confirmar. Sense WAV, desactivats | `QPushButton` |
| — | `self.b_exec` | **Analitza** (F5) | `QPushButton` (`#principal`) |
| — | `self.b_analitza_beats` · `self.b_analitza_beats_clip` · `self.b_analitza_beats_loop` · `self.b_analitza_onsets_loop` | **Beats/BPM** (icona `target`): obri **Analitza beats, downbeats i BPM** (F7) · **Beats del clip**: analitza només el tram de tempo seleccionat amb QM · **Beats A–B**: analitza el loop amb el diàleg de F7 · **Onsets A–B**: detecta només onsets del loop (0,1–2 s), sense BPM, amb atac refinat a mostra, **marge de 30 ms a l'inici** i color **lila**; beats i onsets són capes independents i, si coincideixen, les línies semitransparents es mesclen | `QPushButton` ×4 |
| — | `self.b_desfer` · `self.b_refer` | **Desfer** · **Refer** (icones `undo-2` / `redo-2`) | `QPushButton` |
| — | (al transport; `self.b_zs` al visor) | **Zoom a la selecció** (icona `focus`, sense text) | `QPushButton` |
| — | `self.b_mode_bpm` · `self.b_mode_lliure` | selector **BPM · compàs / hh:mm:ss** (abans deia «Lliure») | `QPushButton` (checkable) |
| — | `self.bpm_intern_bar` · `self.bpm_bar` · `self.compas_bar` | **BPM intern** (negres/minut), **BPM del clip** (en la seua unitat de pols) i **Compàs** del clip, tots **només lectura**. La unitat de pols es deriva del compàs; l'opció avançada viu al diàleg del clip | `QLabel` ×3 |
| — | `self.bpm` · `self.bpb` | **BPM** i **Compàs** **interns del transport**: NO es munten a cap barra; l'edició visible és a la **franja Editor** del clip de tempo seleccionat (tram 0 inclòs) | `QLineEdit` (no visible) |
| — | `self.lb_desti_accions` | **destí visible**: `TAP: … · Edita a la franja: …`; indica si s’edita un tram o el transport (tram 0) | `QLabel` |
| — | `self.b_tap` | **TAP** (tecla **T**) | `QPushButton` |
| — | `self.amb_est` · `self.a_metro` · `self.a_eina_marc` | **Inclou estructura** · **Metrònom** · **Eina de marc** | `QAction` (checkable, menús) |
| — | `self.amb_part` | **Inclou la partitura (xifrat)** | `QAction` (checkable, menú Fitxer) |
| — | `self.b_eina` | **Eina: intel·ligent / Eina: marc** | `QPushButton` (checkable) |
| — | `self._params_temps` | contenidor dels **paràmetres de temps** (TAP · BPM intern · BPM del clip · Compàs); els BPM i el Compàs són **només lectura**; l'edició és a la franja Editor; **×2/÷2** viu al menú del clip de tempo | `QWidget` |
| — | `self.panell_xifrat` · `self.dock_xifrat` | **panell «Tipus d'acord»** (arrel · baix · 92 tipus · ▶ Escoltar · timbre) | `PanellXifrat` en un `QDockWidget` |
| — | `self.tb_loop` · `self.tb_neteja_loop` · `self.tb_mut` | **loop** (icona `repeat-2`) · **neteja el loop** (icona `x`) · **mute** (icona `volume-x`) | `QPushButton` |
| — | `self.tb_snap` · `self.cb_graella` | **Snap** (interruptor: encaixar a la graella) + **divisió del grid i del snap**: **Marcadors** · **Onsets** · **Beats QM** · Auto (zoom) · Negra (1/4) · Corxera (1/8) · Semicorxera (1/16) · Fusa (1/32) · **Treset de negra (2/3) · Treset de corxera (1/3) · Treset de semicorxera (1/6)** · **1 · 2 · 4 · 6 · 8 · 12 · 16 · 24 · 32 · 48 · 64 compassos**. El selector **força el grid** encara que el snap estigui apagat; «Auto» torna a manar pel zoom. **Marcadors** encaixa el cursor i les edicions al marcador humà més pròxim; **Onsets** fa el mateix amb els onsets detectats (si no n'hi ha, no inventa cap posició). **Beats QM** fa que el cursor, els clips i els talls (`+`/`Fin`/`0`) s'encaixen a les línies de beats de QM; `M` també respecta el Snap actiu. Si el tall `+` cau exactament en una línia de compàs i els dos costats queden amb `N` enter, s'aplica directament sense diàleg QM. Amb QM, si cau sobre un beat i l'esquerra queda a prop d'un `N` enter, també es resol directament; la cua final pot quedar fraccionària. Si l'esquerra té una única opció i la dreta és l'últim clip, el motor de talls aplica la cua fraccionària directament, conservant el BPM/compàs local. | `QPushButton` (checkable) · `QComboBox` |
| — | `self.b_metro` · `self.vol_metro` · `self.cb_metro` | **metrònom** (icona `metronome`) · volum del clic · **patró** (Auto · Compàs · Temps · Grup · Beats QM · BPM percebuts · BPM interns). El clic per defecte segueix el **denominador** del compàs (`6/8` → 6 corxeres); la subdivisió és un control a part. Els accents de grup ixen de l’**agrupació de cada tram**: `6/8 = 3+3`, `5/8 = 5`, `7/8 = 7`, `12/8 = 3+3+3+3`… **BPM percebuts** clica la pols percebuda de cada tram i **BPM interns** clica negres (el BPM intern); tots dos sense accents | `QPushButton` · `QSlider` · `QComboBox` |
| — | `self.b_play_tb` | **play / pause** transport (icones `play` / `pause`) | `QPushButton` |
| — | `self.cmb_vel_tb` · `visor.cmb_vel` | **velocitat de reproducció** (0,5 · 0,75 · 1 · 1,25 · 1,5 · 2 · 3×) amb el **to mantingut** (`ffmpeg atempo`); els dos selectors van sincronitzats per `velocitatCanviada` | `QComboBox` |
| — | `self.barra` · `self._progres_analisi` | **barra de progrés** | `QProgressBar` (a la status) · `QProgressDialog` modal mentre s’analitza |
| — | `self.log` · `self.info_box` | **log** · **caixa d'informació «live»** | `QTextEdit` ×2 |
| — | `self.log_dock` | dock **«Log · Informació»** (a baix) | `QDockWidget` |

### Barres d'eines (`QToolBar`, no movibles, a dalt)

| Barra | Contingut |
|-------|-----------|
| **Treball** (barra 1, fila 1) | **Guia ràpida** (amb **Proposa inici** / **Proposa final** / **Proposa mapa** / **Aplica mapa**) → **Ajusta inici WAV** · **Ajusta final WAV** → **selector temps** (**BPM·compàs** / **hh:mm:ss**) → **Analitza** → **Desfer** (icona `undo-2`) · **Refer** (icona `redo-2`). Obrir i exportar viuen al menú **Fitxer** |
| **Temps** (barra 1, fila 2) | **TAP** · **TAP→** (mòbil: mou el fi del clip) · **BPM intern** (negres/minut) · **BPM del clip** en la seua unitat de pols (p. ex. `80` en `6/8` amb `negra amb punt`) · **Compàs** del clip (p. ex. `6/8`), tot **només lectura**. L'edició del BPM i del Compàs és a la **franja Editor**; en canviar només el compàs, per defecte es conserva el **BPM visible** (Cas B); la unitat de pols es deriva del compàs i es pot canviar al diàleg del clip. **×2/÷2** viu al **menú contextual del clip de tempo** |
| **Transport** (fila 3) | **`play`/`pause`** (play/pausa) · `square` · `rewind` · `fast-forward` · `arrow-left-to-line` (A) · `arrow-right-to-line` (B) · `repeat-2` (loop) · **`x` (neteja el loop)** · `zoom-out` · `zoom-in` · `maximize` (Tot) · **`focus` (zoom a la selecció)** · `volume-x` (mute) · **selector de velocitat (0,5–3×, to mantingut)** · `metronome` · volum del clic · **[patró Auto/Compàs/Temps/Grup/Beats QM/BPM percebuts/BPM interns]** · **[Quantitza]** · **[BPM…]** · **[Snap]** (interruptor) · **[selector de divisió de graella]** · **[Eina: intel·ligent]** (commutador; passa a «Eina: marc» — també amb la tecla `E` i al menú Selecciona) |

### Menús

| Menú | Accions |
|------|---------|
| **Fitxer** | Obre àudio… (Ctrl+O) · Obre projecte… · Obre recent… · Desa (Ctrl+S) · Desa com… · Desa una còpia… · Reverteix · **Restaura una còpia de seguretat…** · **Desa i exporta-ho tot…** (Ctrl+Shift+E) · Exporta WAV's… (Ctrl+E) · Exporta àudio… · Exporta la partitura… · **Exporta mapa de tempo (MIDI)…** · Inclou la partitura (xifrat) · Obre la carpeta de sortida · Surt (Ctrl+Q) |
| **Edita** | Desfer (Ctrl+Z) · Refer (Ctrl+Y) · Refer (alternatiu) · Retalla (Ctrl+X) · Copia (Ctrl+C) · Enganxa (Ctrl+V) · Afegeix acord… · Afegeix secció… · Parteix l'acord al cursor… · Parteix la secció al cursor… · Afegeix tram de tempo/compàs… · Parteix el tram al cursor… · **Parteix el tempo al cursor** (Fin) · **Parteix l'estructura al cursor** (0) · **Parteix tempo i estructura al cursor** (+) · Elimina element (Del) · Duplica element (Ctrl+D) · Reanomena element (F2) · Troba i reemplaça… (Ctrl+H) · **Quadra els extrems de la WAV…** · Paràmetres… · Retard global de reproducció… |
| **Selecciona** | Selecciona l'acord del cursor · Selecciona la secció del cursor · Selecciona el tram de tempo/compàs del cursor · Loop a la selecció (L) · Marca inici de loop (A) (Ctrl+[) · Marca fi de loop (B) (Ctrl+]) · Neteja el loop · Activa/desactiva loop · Eina de marc (rubber-band) |
| **Visualitza** | Zoom + (Ctrl++) · Zoom − (Ctrl+−) · Zoom total (Ctrl+0) · Mostra el log · Mostra els tipus d'acord · Metrònom |
| **Analitza** | Analitza l'àudio (acords + estructura) (F5) · **Analitza només els acords… (F6)** · **Analitza acords al rang A–B…** · **Analitza beats, downbeats i BPM (F7)** · **Beats del clip** (QM només al tram de tempo seleccionat)· Quantitza el model… · **Quantitza BPM** (Sense decimals · 1 decimal · 2 decimals) · Marca el rang A–B com a rubato · Converteix el tram de tempo a rubato · Converteix el rubato a normal · Detecta el tempo per trams… · Detecta el mapa de tempo (per beats)… · Afegeix un marcador (M) · **Marca l'inici de l'anàlisi** · **Marca el final de l'anàlisi** · Esborra l'últim marcador · Inclou estructura |
| **Ajuda** | Dreceres de teclat · **Configura les dreceres…** · Obre la carpeta del registre · Quant a Auto Chords |

### Desa i exporta-ho tot… (Ctrl+Shift+E)

- **`Fitxer ▸ Desa i exporta-ho tot…`** desa primer el projecte (`.acproj` +
  `.bak`); si el desat falla, **no exporta res**. Després llança l'export en un
  **fil** i genera el paquet complet: `acords.csv` + `wavs_acords/`,
  `estructura_ABC.csv` + `wavs_estructura/`, `mapa_tempo/`
  (`mapa_tempo.csv` + `.mid`), guia, manifest i **partitura sempre**
  (MusicXML; PDF/MSCZ si hi ha MuseScore), encara que «Inclou la partitura»
  estiga desmarcada.
- **No exporta la WAV sencera**: per a una còpia en un altre format es fa
  servir **`Fitxer ▸ Exporta àudio…`**.
- Els derivats existents (`wavs_*`, `partitura/`, `mapa_tempo/`, CSVs) es
  **sobreescriuen**. En acabar s'obri la **carpeta del projecte**.

### Quadra els extrems de la WAV…

- **`Edita ▸ Quadra els extrems de la WAV…`** obri `DialegQuadratura`: ajusta
  l'inici (silenci d'estudi, anacrusi, introducció o aplaudiments) i/o el final
  (cua, *fade-out* o aplaudiments) a **N compassos sencers**. L'inici usa per
  defecte el BPM/compàs del primer tram (es pot canviar al diàleg); el final
  usa per defecte els de l'últim tram, però el BPM i el compàs de la cua també
  són editables.
- Cada extrem té un selector d'**unitat de pols** (`negra`, `negra amb punt`,
  `blanca`, `corxera`…): el camp **BPM** mostra el valor percebut en eixa
  unitat, no l'intern. Canviar la unitat conserva el tempo intern; editar el
  número recalcula l'intern i tota la resta del pla (N, durada objectiu i
  retall/silenci). La unitat triada es desa al tram d'introducció o de cua.
- Els botons **Ajusta inici WAV** i **Ajusta final WAV** de la barra **Treball**
  obrin el mateix diàleg amb només la part corresponent activada.
- Marca **«On comença la cançó (temps 1)»** i, al final, **«On s'acaba la música (inici de la cua)»**. Presets clars: **Conserva el so i afig silenci**, **Retalla el tros sobrant**, **Deixa 1 compàs d'introducció** i **Comença directament al temps 1**; al final, **Conserva tota la cua i afig silenci**, **Retalla la cua sobrant** i **Deixa K compassos de cua**. El final es tracta com una cua independent: es talla l'últim tram exactament al punt marcat; el tram normal de l'esquerra es recalcula (N/BPM) a compassos sencers, queda el tram final de cua i la WAV s'allarga o es retalla pel final. Els clips d'acords i seccions que hi haja després del tall es descarten; només queda un clip final buit (`N`) fins al nou final. S'afigen els marcadors **Inici** (al temps 1) i **Final** (a l'inici de la cua), visibles com a text al timeline. Els **beats/downbeats QM** es desplacen amb l'àudio i s'actualitzen a la còpia del projecte.
- La previsualització mostra segons i **mostres** afegides/retallades, la nova
  durada i els compassos/BPM resultants abans d'aplicar.
- L'original no es toca: s'edita només la còpia de treball. L'operació és **atòmica** (WAV + acords + seccions + mapa + marcadors + CSVs) i un sol `Ctrl+Z`/`Ctrl+Y`.

### Exporta àudio… (Fase 6)

- **`Fitxer ▸ Exporta àudio…`** obre el **diàleg natiu de desar** del sistema.
  Exporta la **còpia WAV de treball** (ja editada). Si el destí és eixa mateixa
  còpia, es rebutja amb un avís; per a qualsevol altre fitxer existent (també
  l'original importat), el diàleg natiu demana confirmació de sobreescriptura.
- **Perfils** (els que el `ffmpeg` del paquet sap escriure de debò):
  - **WAV** PCM 16 bits (mostreig original, 44,1 kHz o 48 kHz), 24 bits i
    32 bits float.
  - **MP3** 128, 192 i 320 kbps · **FLAC** 16 bits · **AAC/M4A** 256 kbps ·
    **OGG Vorbis** q6 · **Opus** 160 kbps.
  - La llista s'obté amb `ffmpeg -encoders`: si un còdec no hi és, el perfil
    no s'ofereix.
- El nom suggerit és `<projecte>_editat.<ext>` dins la carpeta del projecte.
  L'escriptura és **atòmica** (temporal + `os.replace`); l'error surt al log i
  en un avís, sense deixar fitxers a mitges.
- L'exportació va en un **fil** i l'estat es veu al log (inici, comandament i
  resultat).

### Exporta mapa de tempo (MIDI) i restauració de còpies

- **`Fitxer ▸ Exporta mapa de tempo (MIDI)…`** desa només el mapa de
  tempo/compàs com a **Standard MIDI File tipus 1** (pista de conductor):
  `Set Tempo`, `Time Signature`, markers de tram i marcadors de compàs/secció;
  `mapa_tempo/mapa_tempo.mid` automàticament.
- **`Fitxer ▸ Restaura una còpia de seguretat…`** llista les carpetes de
  `backup/` (les més noves primer). Abans de restaurar crea una còpia de
  l'estat actual; després recupera el document, els CSV/marcadors i `audio/`.
  **No toca els exports** (`wavs_*`, `partitura/`, MIDI).

### Configuració de dreceres

- **`Ajuda ▸ Configura les dreceres…`** obri una taula amb **totes les
  dreceres**: accions de menú, globals (play, TAP, eina), editor (`+`,
  Fin, `0`, `M`) i timeline (Esc, nudge). Té **cerca**, edició amb
  `QKeySequenceEdit`, **Esborra**, **Restaura la seleccionada**, **Restaura
  totes** i **Desa**.
- En desar es comproven els **conflictes** (una mateixa combinació per a dues
  accions) i, si n'hi ha, no es desa i s'indica quines xoquen.
- Les dreceres es guarden a `dreceres.json` dins `DADES_DIR` i es tornen a
  aplicar en obrir l'app. Un valor buit deixa l'acció sense drecera.
- Els camps de text no s'intercepten; Enter respecta botons, combos i
  diàlegs amb acció pròpia.

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
  continua funcionant igual.
- **`Ctrl+Shift` mantingut = eina «marc» temporal**: mentre les dues tecles
  estan premudes, el timeline passa a l'eina de selecció (marquee) i, en
  deixar anar qualsevol de les dues, torna a l'eina que hi havia (normalment
  «intel·ligent»). És el gest equivalent al *temporary tool switch* d'un DAW.
- El **rang de `Shift+clic`** és sempre del **carril del clip clicat**. Per
  agafar clips de les **dues pistes** de cop, el **marquee**: `Ctrl`+arrossega
  (temporal) o l'eina «marc» (permanent).
- La **selecció no entra a la pila de desfer** (com abans).
- **Tecla `E`**: commuta l'eina (**toggle**, no on/off). Per defecte sempre
  s'arrenca en «intel·ligent».
- **Duplicar**: `Ctrl+D` (element o grup seleccionat). **No hi ha** duplicat
  arrossegant: l'arrossegament del cos mou; per duplicar, `Ctrl+D` o
  copiar/enganxar.
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
> **Espai** = play/stop · **T** o **`.` del teclat numèric** = tap tempo · **Ctrl+Z / Ctrl+Y**
> = desfer/refer · **Del** = eliminar · **Ctrl+D** = duplicar · **F2** = reanomenar (clip o **grup del mateix tipus**) ·
> **←/→** = **nudge** un pas de graella (**Alt+←/→** = vora dreta) ·
> **Ctrl+O** = obrir WAV · **Ctrl+S** = desar · **Ctrl+E** = exportar ·
> **Ctrl+[ / Ctrl+]** = loop A/B ·
> **F5** = Analitza · **Ctrl++ / Ctrl+− / Ctrl+0** = zoom +/− / total ·
> **`+`** = parteix tempo i estructura · **Fin** = parteix només tempo ·
> **`0`** = parteix només estructura · **`M`** = marcador independent.
> `+`, `Fin`, `0` i `M` funcionen des de **qualsevol focus de la finestra**
> (llistes, editor, timeline…), tret dels **camps de text**; `Fin` respecta
> botons, combos i diàlegs que tenen la seua pròpia acció.
>
> **Multi-selecció (timeline)**: **Ctrl+clic** afegeix/treu un clip ·
> **Shift+clic** = rang **per temps, sempre del carril del clip clicat** (per agafar
> clips de **les dues pistes**, el **marquee**: `Ctrl`+arrossega o l'eina «marc») ·
> **Ctrl+Shift** = eina «marc» temporal mentre es mantenen les tecles ·
> **Del** = esborrar la selecció (grup) · **Ctrl+C/X/V** = copiar/retallar/enganxar
> la selecció **sobreescrivint** el tram (regla d'or #4: la cançó no pot créixer) ·
> **Ctrl+D** = duplicar el grup ·
> **arrossegar** un clip seleccionat = moure el grup. El regle mostra el
> **mode** (`120 BPM · 4/4` o `hh:mm:ss`).

### ✅ P1 (A1–A3) — **IMPLEMENTAT i COMMITEJAT** (v0.7.0)

> Al **codi** ja hi és (committejat; suite verda):
> - ✅ **A1 — Desfer/Refer del temps i del loop**: `undo`/`redo` ara també cobreix **BPM, compàs** i el **loop A-B** (nou estat de temps), no només acords/seccions.
> - ✅ **A2 — Partir una secció — FET**: acció **Edita ▸ Parteix la secció al cursor…** i entrada **«Parteix la secció…»** al menú contextual de la secció (s'activa només si el clic és en una secció i el cursor hi cau a dins). Parteix la secció que conté el cursor en dues: la meitat esquerra conserva lletra i família i la nova rep la lletra que es tria (per defecte, la mateixa). És la manera natural d'afegir secció en un model **saturat** (les seccions cobreixen tota la WAV, regla #4).
> - ✅ **Regla d'or #11 — paritat acords ↔ estructura**: els acords tenen ara les **mateixes eines** que les seccions — **Edita ▸ Parteix l'acord al cursor…**, **«Parteix l'acord…»** al menú contextual del clip i **menú de la llista d'acords** amb *Afegeix/Partir/Fusionar amb anterior/Fusionar amb següent/Elimina* (idèntic al de les seccions). El tall deixa l'esquerra amb el nom i el clip nou (dreta) amb el nom triat (per defecte, el mateix). Darrere: `pipeline.parteix_acord`/`fusiona_acords` i `visor.parteix_acord`/`fusiona_acord` (mirall dels de secció).
> - ✅ **A3 — Dreceres completes — FET**: el diàleg **Ajuda ▸ Dreceres de teclat** ara **dedueix totes les dreceres dels menús reals** (abans només en llistava 6).

---

## 1. Visor (`Visor`, `app/visor.py`) — widget central

```
┌────────────────────────────────────────────────────────────────────────┐
│  ①  REGLE DE TEMPS        (RulerLayer)      y 0–26    · 26 px          │
│      etiquetes compàs.beat (el compàs 1 és sempre a 0 s)                 │
│      ◄── arrossega AQUÍ el ratolí per crear un LOOP A/B ──►            │
├────────────────────────────────────────────────────────────────────────┤
│  ②  FORMA D'ONA           (WaveformLayer)   fons #0f1218               │
│      ↔ nanses d'inici i final d'àudio                                   │
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
│      acord/secció: [Nom▢] [Família▢] [Inici (s)▢] [≈ ▢] [Aplica]│
│      tempo: [BPM▢][[]][->][x2][/2] [Compàs▢][[]][->] [Agrupació▢][Aplica] [N▢][[]][->] [Rol] [Ini(c)▢] [Fi(c)▢] [Aplica tot] [Ajusta]│
├────────────────────────────────────────────────────────────────────────┤
│  ⑩ LLISTA ACORDS    │ ⑪ LLISTA SECCIONS  │ ⑭ LLISTA TEMPO             │
│  «1.1 N», «8.1 E7»… │ «A(N) 1.1–10.1»…   │ Inici·Fi·BPM·Compàs        │
│  clic=salta (i ressalta la fila) · doble=edita (Editor)                │
│  dret=menú contextual (el mateix del carril)                          │
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
| ①b | `TimeRulerLayer` / `self._time_ruler` | **graella fixa de temps absolut `hh:mm:ss`**, sota l'ona; no depén de BPM ni rubato; el zoom només canvia la resolució | `QGraphicsItem` |
| ② | `WaveformLayer` / `self._waveform` | **forma d'ona** | `QGraphicsPixmapItem` |
| — | `self._audio_handles` / `self._audio_preview` | **nanses i previsualització** de retall/afegit als extrems; snap compartit amb el timeline | `QGraphicsRectItem` |
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
| ⑫ | `ed_gran` · `ed_nom` · `ed_fam` · `ed_agr` · `ed_n` · `ed_rol_lbl` · `ed_ini` · `ed_cb` · `ed_aplica` · `ed_bpm_fix` · `ed_bpm_aplica` · `ed_bpm_x2` · `ed_bpm_div2` · `ed_compas_fix` · `ed_compas_aplica` · `ed_n_fix` · `ed_n_aplica` · `ed_agr_aplica` | **franja Editor** (acord/secció: nom/família/inici; **tempo: BPM + compàs + agrupació + N + rol derivat + Ini (c) + Fi (c)**). BPM, Compàs i N tenen **`[]`** (recalc fix) i **`->`** (recalc mòbil); BPM també té **`x2`/`/2`** amb recalc fix; Agrupació té un sol **Aplica**; els compassos irregulars mostren suggeriments d'agrupació | `QLabel`/`QLineEdit`/`QPushButton` |
| ⑭ | `self.llista_tempo` | **llista de clips de tempo/compàs** (`Inici (s)` · `Fi (s)` · `BPM` · `Compàs`; compàs del rubato, p. ex. `R 4/4`) | `QTableWidget` |
| ⑮ | `self.llista_marcadors` | **llista de marcadors independents** (`Temps (s)` · `Tipus`): tipus `marcador`, `compas`, `seccio`, `inici`, `final`, `inici_analisi` o `final_analisi`; doble-clic edita, menú contextual elimina; no està lligada al tempo ni a l'estructura. Les quatre llistes ⑩⑪⑭⑮ comparteixen **una sola fila** | `QTableWidget` |
| ⑬ | `self.lliscador` · `self.temps` · `b_mut` · `volum` · `etiqueta` | **lliscador + estatus** | `QSlider`/`QLabel` |

> 🥁 **El transport principal** (`b_play`, `b_stop`, `b_menys`, `b_mes`, `b_A`,
> `b_B`, `b_loop`, `b_zm`, `b_zp`, `b_zt`, `b_zs`, `b_mut`, `cmb_vel_tb`, `b_metro`,
> `vol_metro`)
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
| **Clic llista ⑩⑪⑭⑮** | salta + **ressalta la fila** (i selecciona el clip al carril) |
| **Doble-clic llista ⑭** | porta el clip de tempo a la franja Editor (BPM + compàs) |
| **Doble-clic llista ⑮** | edita el temps o el tipus del marcador |
| **Botó dret llista ⑮** / **Del** | elimina el marcador seleccionat |
| **Zona buida ② + botó dret** | **pan** (desplaçar la vista) |
| **Botó dret SOBRE un clip** | **selecciona** el clip i obri el **menú contextual** — **el mateix joc a les 3 pistes** (regla #11): **Afegeix acord/secció aquí** · Duplica · Elimina · Reanomena · Parteix l'acord/la secció… · Partir per la meitat · **Parteix a la selecció A–B** (només amb loop marcat) · Retalla · Copia · Enganxa |
| **Pista de tempo ③ — clic** | **selecciona** el tram de tempo/compàs i hi posa el cursor **exactament al seu inici** (paritat amb els clips ④⑤; sense snap, perquè les fronteres del mapa poden ser lliures) |
| **Pista de tempo ③ — doble-clic** | **diàleg del recalcul fix** (`_on_tempo_edit`). Dues zones: esquerra amb **Recalcul fix** —camps **N**, **Compàs** i **BPM**, casella **N mana (el BPM es recalcula)**, **desactivada per defecte**, i botó **Recalcula**— i dreta amb la **Informació del clip** (només lectura). El recalcul s'aplica immediatament amb un sol desfer; **Tanca** no aplica res més. El **recalcul mòbil** es fa des de la franja Editor; a la pista, el cos d'un tram interior mou el bloc sencer i les vores interiors continuen redimensionant una frontera. |
| **Pista de tempo ③ — cos** | arrossegar un tram **interior** → mou el **bloc sencer** (mateixa durada, BPM, compàs i N). Els veïns dret i esquerre es recalculen. El primer i l'últim tram no es mouen com a bloc perquè tenen l'inici/final de la WAV ancorats. Les **vores interiors** continuen redimensionant una frontera |
| **Pista de tempo ③ — botó dret** | **selecciona** el tram i obri **el mateix joc de menú que els clips** (regla #11): **Afegeix un canvi aquí** (el seu «afegir» propi) · Duplica (només si hi ha lloc després) · Elimina (només si hi ha més d'un tram) · Reanomena (BPM/compàs)… · Parteix aquest tros aquí · Partir per la meitat · **Parteix a la selecció A–B** (s'imanta a línia de compàs) · **Afegir 1 compàs (+1)** · **Restar 1 compàs (−1)** · **Doblar compassos (×2)** · **Dividir compassos (÷2)** (aquestes 4, només a ③: canvien els compassos amb els **segons immòbils** i el BPM s'adapta) · Retalla · Copia · Enganxa |
| **Nansa esquerra de l'àudio ②** | arrossegar cap a dins → retalla l'inici · cap a fora → afegeix silenci |
| **Nansa dreta de l'àudio ②** | arrossegar cap a dins → retalla el final · cap a fora → afegeix silenci |
| **Previsualització d'àudio** | mostra el tram afectat mentre s'arrossega; en deixar anar, aplica l'edició a la còpia del projecte i sincronitza el model (una acció de desfer) |
| **Roda ②** | **zoom** (centrat al clip seleccionat) |
| **Espai** | **play / pausa** |
| **T** / **`.` del teclat numèric** | **tap tempo** (mentre s'escriu en un camp, no) |
| **Ctrl+clic / Shift+clic** | **multi-selecció**: afegeix/treu del grup · **rang** (Shift = per temps, **sempre del carril**; per les 2 pistes, el **marquee**) |
| **Ctrl+Shift (mantingut)** | passa temporalment a l'eina **marc**; en deixar anar, torna a l'eina anterior |
| **Alt+clic** | **cap acció de l'app**. Alt només s'usa amb `Alt+←`/`Alt+→` (vora dreta); el sistema pot interceptar Alt+clic (moure la finestra / menú) |
| **Delete / Backspace** | **elimina** el clip o tota la **selecció** (grup) |
| **Ctrl+D** | **duplica** el clip o **tot el grup** seleccionat |
| **Ctrl+C / Ctrl+X / Ctrl+V** | **copiar / retallar / enganxar** la selecció — l'enganxat **sobreescriu** el tram (regla #4: la cançó no pot créixer); si no mous el cursor, enganxa just **després** del bloc i deixa el bloc enganxat **seleccionat** |
| **F2** | **reanomena** el clip seleccionat, o **tot el grup del tipus actiu** (N acords → un nom · M seccions → una lletra); amb selecció **mixta** es renombren només els del tipus del clip actiu (opció A), i el bloc queda **seleccionat** |
| **Editor ⑫ + «Aplica»** | amb **multi-selecció**, el camp **Nom** s'aplica a **tots els seleccionats del tipus actiu** (estil fulla de càlcul); l'inici NO s'aplica en bloc. En un clip de tempo, **`[]`** al costat de **BPM**, **Compàs** o **N** aplica eixa variable amb **recalc fix** (fronteres fixes) i adapta les altres:
- **BPM**: BPM exacte → N enter + compàs; si no hi ha combinació, rebutja.
- **Compàs**: compàs exacte → N enter més pròxim + BPM recalculat si cal.
- **N**: N exacte → compàs que conserve el BPM; si no n’hi ha, compàs actual + BPM recalculat.
Per exemple, `4/4 N=14` → `7/4` deixa `N=8` i conserva el BPM. **`->`** aplica-la amb **recalc mòbil** (mou la frontera compartida). L'Editor **no consulta QM**; els beats QM només s'apliquen als **Talls QM** (`+`, intro/normals) amb Snap Beats QM. **`x2`/`/2`** doblen o dividixen el BPM amb la mateixa lògica del BPM fix. **Agrupació** té un sol **Aplica** perquè no recalcula tempo. El botó **Aplica** general fa el recalc mòbil si només ha canviat un camp. A l’últim clip, els `->` queden desactivats perquè la fi de la WAV és fixa. Amb **Snap = Beats QM**, els beats són una restricció forta **només per als Talls QM** (`+`, intro/normals); l'Editor, les fronteres, els diàlegs i el TAP no consulten QM. L’últim clip pot quedar amb `N` fraccionari perquè el final de la WAV és fix |
| **Ctrl+Z / Ctrl+Y** | **desfer / refer** |
| **Ctrl+H** | **troba i reemplaça** xifrats (acords) o etiquetes (estructura) a **tot el tema**; una sola operació de desfer i **no canvia cap temps** |
| **← / →** | **nudge**: mou la **vora esquerra** (l'inici) del clip seleccionat **un pas de graella**; **Alt+←/→** mou la **vora dreta** (estirar/encongir). Una sola operació de desfer; sense selecció no fa res. |
| **Ratolí sobre un botó/camp** | la **caixa d'informació** (a baix a la dreta) mostra què fa; si el ratolí **no** és sobre res amb info, hi gira un **rotatori de consells i dreceres** (cada **8 s**; el 1r panell segueix l'**eina vigent**). **Clic a la caixa** → la **para** (30 s) i el clic **següent avança** de «pantalla»; un **missatge transitori** (desfer/refer…) hi surt amb **format propi** |
| **Esc** | **anul·la**, per ordre de prioritat: (1) el **rang** en curs (`Ctrl`+arrossegar o eina «marc») · (2) un **loop a mig marcar** (el descarta i el restaura) · (3) el **loop actiu** (el desactiva i **treu la caixa groga** del timeline) · (4) **buida la selecció**; si no hi ha res d'això, no fa res. Manté el que ja feia: **cancel·la el reanomenament inline** i **tanca diàlegs** (aquests tenen prioritat) |

> ⚠️ **«Afegeix … aquí»** (el menú de les 3 pistes i la llista): els clips cobreixen
> **tota** la WAV (regla #4), així que **afegir no és inserir** un tros nou, sinó
> **obrir un clip nou** en eixe instant — **acord** = una **marca** nova (l'anterior
> s'hi acaba); **secció** = **partir** la secció que conté l'instant (la meitat
> dreta rep la lletra/família). Un **únic camí** (`visor._afegeix_a_la_posicio()`)
> per a la llista i el timeline.

---

## 3. Temps: BPM i tap tempo

- **BPM** = la velocitat en **negres/minut**, com als DAW. La **unitat de pols**
  (`beat_unit`) és per tram i només canvia la presentació: en `6/8`, una negra
  amb punt a `80` s’escriu `120` negres/min internes i `80` en la unitat. La
  unitat es deriva del compàs i de l'agrupació; el diàleg del tram conserva
  l'opció avançada per canviar-la.
- **On s'edita**: la barra «Temps» mostra **el BPM del clip** en la seua
  unitat de pols i el **Compàs** del clip, tots dos de només lectura. L'edició
  del BPM i del Compàs es fa a la **franja Editor** del clip de tempo
  seleccionat. La unitat de pols es deriva automàticament del compàs, amb
  l'opció avançada al diàleg del clip. La resta de camps
  (Agrupació · N · Ini/Fi) també s'editen a la franja Editor. El
  transport intern del tram 0 se sincronitza des del model (`_sincronitza_temps_del_visor`),
  mai al revés.
- **TAP** (tecla **T**): sempre mana i no té restricció QM; conserva les fronteres i manté `N` enter, també a l’últim clip.
- **TAP→** (botó o `.` del teclat numèric): BPM exacte; mou el `fi` del clip seleccionat a la **línia de compàs més pròxima** amb el BPM nou i **recalcula N**. A l’últim clip la fi de la WAV no es mou i deixa `N` fraccionari. Comparteix la mateixa sessió robusta de taps. Patró estàndard dels DAWs — guarda els instants dels
  últims taps, **mediana dels intervals** → `60/∅`; **reset als 2 s** (LMMS);
  **descarta intervals fora de 30–350 BPM** i els clarament anòmals (±30 % de
  la mediana). La **unitat de pols del clip** indica el valor de cada tap:
  `BPM intern = taps/min × negres per beat`. El botó mostra **taps/min en la
  unitat del tram** (`TAP (n) 80`), no el quarter intern. **Només actua amb un
  tram de tempo seleccionat**. Propaga BPM al regle i al metrònom **sense
  reengegar l'àudio**. No hi ha cap Ref. recalc: el TAP només toca el clip
  seleccionat. El clip sempre queda amb `N` enter. Canviar la unitat amb un
  TAP obert tanca la sessió (1 undo) i el canvi és un altre undo. Durant la
  sessió de TAP **no s'emet l'avís modal** de mapa inconsistent.

### Rubato

- Es crea amb **`Analitza ▸ Marca el rang A–B com a rubato`**, **`Converteix
  el tram de tempo a rubato`** o les mateixes accions del menú contextual del
  carril ③.
- El clip de rubato té **inici i fi en segons invariables**, un **sol compàs**
  i la **unitat heretada del primer tram musical**; a l’Editor els camps són
  editables com en un tram normal (el rubato només és un flag de notació).
- La graella del rubato és la mateixa que la d’un tram normal. El rubato
  només canvia la notació; no genera cap fitxer d’aproximació.

## 4. Metrònom 🥁

- Només en mode **BPM · compàs** (gris a Lliure).
- Volum propi (60 % per defecte); el mute/volum de la cançó **no** l'afecta.
- El clic per defecte segueix el **denominador del tram**: `6/8` clica 6
  corxeres amb accents a 1 i 4. La **subdivisió** de grup és un control a
  part. Accent de
  compàs (temps 1) ≈ 1500 Hz; resta ≈ 1000 Hz.
- **Patrons**: `Auto` (per defecte) = pols del tram + accents de compàs i grup; `Compàs` =
  només el primer temps; `Temps` = Compàs + Temps, sense accents de grup;
  `Grup` = Compàs + inicis de grup; `BPM percebuts` = pols percebuda del tram
  i `BPM interns` = negres, tots dos sense accents. Els inicis de grup ixen de
  l’agrupació efectiva de **cada tram** (`3+3`, `2+2+3`, `3+2`…), no d’una
  unitat global.
- **`Beats QM`**: marca només els **beats detectats per QM**, un a un i
  **sense accents**. No passa per la graella del mapa: els instants poden no
  coincidir amb cap compàs/beat teòric i sonen exactament on els ha detectat
  QM. Si no hi ha beats detectats, no clica i ho indica al log.
- **`BPM percebuts`**: clica la **pols percebuda de cada tram**
  (`6/8` → negra amb punt, `4/4` → negra…), **sense accents**. Si no hi ha
  mapa, ix del compàs del transport.
- **`BPM interns`**: clica **negres** (el BPM intern en negres/minut),
  **sense accents**. No exigix que la negra òmpliga el compàs: a `3/8` un
  clic pot caure a cavall de compàs.
- No hi ha **unitat de clic global**: la unitat és la del tram i no depén de
  la selecció del visor. Si no n’hi ha (o no encaixa), s’usa el denominador
  (`4/den`) com a fallback; la subdivisió de grup ve de l’agrupació del tram.
  El TAP no força el mode de grup: són controls separats.
- El clic es **mescla al mateix buffer** que s'envia al reproductor (sense
  QTimer ni segon procés → no deriva).
- **Commutar-lo** (o canviar-ne el volum o el patró) **no** reinicia el
  reproductor: el fil d'alimentació llig `metro_on`/`metro_vol`/`metro_mode` a
  **cada tros**, com fa amb el volum i el mute de la cançó. (Reiniciar-hi
  tallava l'àudio uns mil·lisegons.)
- Sense clics per sobre de **400 BPM** (`metronom.BPM_MAX`).

---

### Graella fixa de temps

A sota de l'ona hi ha una segona graella independent, en **temps absolut**
(`hh:mm:ss`). Els seus tics són sempre segons des de l'inici del WAV; no es
mouen amb el BPM, els compassos ni els rubatos. Només el zoom canvia
la resolució visual (1, 2, 5, 10, 15, 30 s…), no les posicions temporals.

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
| **Base (apagat)** | gris `SURFACE #2a2c30` | **tots** |
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

En clicar **`Analitza`** (obre a **Acords**)
surt un `QDialog` amb 3 pestanyes + «Restaura per defecte»:

| Pestanya | «Què s'analitza» + paràmetres |
|----------|----------|
| **BPM** | **casella «Detecta el BPM»** (`_cb_bpm`) + rang de cerca (min/max), rang preferit i motor (consens/tempo) |
| **Acords** | **casella «Detecta els acords»** (`_cb_acords`) + els **6 paràmetres del Chordino** (construïts del descriptor `.n3`) + **neteja posterior** |
| **Estructura** | **casella «Detecta l'estructura»** (`_cb_estructura`) + durada mínima de secció + fusionar trossos iguals |

La pestanya **Acords** es genera **dinàmicament** des de `app/vamp_params.py`
(checkbox pels 0/1, combo quan el paràmetre té noms, spinbox pels numèrics).
Els títols són **en català** amb l'`id` del plugin a sota i una **ajuda**
(tooltip). Es passen al motor amb `--param nom=valor` (host propi,
`vamp_host_local`).

Les **3 caselles** són **independents** (`analisi.bpm` · `analisi.acords` ·
`analisi.estructura` a `opcions_detecta.json`, defecte: totes tres marcades).
Cada etapa que es desactiva **no s'executa i conserva el que ja hi ha**:
sense BPM es manté el tempo del transport, sense acords es manté el model
d'acords (i el seu CSV), sense estructura es conserven les seccions dels
marcadors (`2/3 estructura: OMESA (es conserva la que hi ha)` al log).

> **El BPM també es detecta amb «Analitza»**:
> l'etapa 1 del pipeline busca el tempo (`pipeline.detecta_bpm`) i, si en surt
> un, s'escriu al camp BPM i s'aplica al mapa de tempo (si el mapa té més
> d'un tram, s'avisa i no es toca). L'acció **F6** *Analitza només els acords*
> és drecera de «només acords» (BPM i estructura desactivats).

La casella **«Detecta l'estructura»** és el MATEIX estat que l'acció *Inclou
estructura* del menú (es sincronitzen).

**Neteja posterior** (`app/postproc.py`): treure el baix (`A/E`→`A`), reduir
(`Cmaj7`→`C`), fusionar iguals, durada mínima i **encaixar a la graella** amb
les mateixes graelles que «Quantitza» (per defecte **corxera = 1/2 temps**,
és a dir, 2 posicions per temps). Usa el `TempoMap` vigent en llançar
l'anàlisi.

**Anàlisi per rang A–B** (*Analitza ▸ Analitza acords al rang A–B…*): amb un
loop A–B marcat, extreu només eixe tram (amb 2 s de context abans i 1 s
després), hi passa Chordino, aplica la mateixa neteja/graella i **fusiona
només els acords del rang**; la resta del model, el BPM i l'estructura no es
toquen. El mínim és 0,5 s.

Les opcions es **recorden** a `opcions_detecta.json` (gitignored).

### 6.2 Motors d'autodetecció (Queen Mary)

S'han **compilat** els plugins **`qm-vamp-plugins`** de Queen Mary (els
d'Audacity/Mixxx), **sense AVX** (`eines/compila_vamp_plugins.sh`).

| Pestanya | Motor per defecte | Altre motor |
|----------|-------------------|-------------|
| **BPM** | `nostre` (`app/tempo.py`) | `qm`, **`consens`** |
| **Estructura** | **`qm`** (qm-segmenter) — únic motor | — |

La detecció de beats usa el
**primer downbeat del resultat d’Analitza beats, downbeats i BPM** si ja existeix; si no, cau a
`qm-onsetdetector` + `qm-barbeattracker` (al tema de 101 dona 9,49 s). Així
les línies de downbeats ixen de la mateixa detecció.

QM s’executa amb `bpb` = beats QM per compàs i `inputtempo` = BPM d’eixos
beats, calculats amb la **unitat de pols** del clip: `6/8` amb negra amb punt a
120 negres/minut → `bpb=2` i `inputtempo=80`. El BPM retornat es reconverteix
a negres/minut. Si la unitat no cap al rang 2–16 de QM, es fa fallback a la
unitat del denominador o a `qm-tempotracker` sense bars.

El diàleg **Analitza beats, downbeats i BPM** proposa la pols segons el compàs
(`6/8` → negra amb punt, `4/4` → negra…) i mostra el BPM percebut equivalent a
l’intern. L’usuari pot canviar-la a negra, negra amb punt, corxera… abans de
detectar; la tria s’envia a QM i afecta `bpb`/`inputtempo`.

### 6.3 Import de formats (`app/ffmpeg.py`)

`Obre àudio` accepta **wav, mp3, aif/aiff, flac, m4a, ogg, opus, wma…**. Si el
fitxer no és **WAV PCM 16 bits**, es converteix automàticament amb
`ffmpeg -vn -c:a pcm_s16le` directament en un temporal dins `audio/` del
projecte. No es crea cap WAV convertit al costat de l'original.

També es pot **arrossegar el fitxer des de l'explorador del sistema** i deixar-lo
anar sobre qualsevol part de la finestra: fa exactament el mateix flux. La
lectura del drag & drop és al mòdul `app/drag_drop.py` (URLs natives
`text/uri-list` amb *fallback* de text pla) i només accepta fitxers locals amb
una extensió d'àudio de la llista.

---

## 7. Documents relacionats
- `docs/ESQUEMA_UI.html` i `docs/ESQUEMA_UI.svg` — aquest mateix esquema en
  **HTML** i **vectorial**, **GENERATS** d'aquest `.md` amb
  **`python3 eines/genera_esquema_ui.py`** (**no editar-los a mà**; el test
  `tests/test_pipeline.py` › `TestEsquemaUiGenerat` ho blinda → si edites aquest
  `.md`, regenera'ls).
- `README.md` — vista de producte: què és i què fa l'app.
