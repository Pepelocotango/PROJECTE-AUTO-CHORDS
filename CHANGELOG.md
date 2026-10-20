# Registre de canvis — PROJECTE AUTO CHORDS

Format [Keep a Changelog](https://keepachangelog.com/ca/1.0.0/).
Versions amb tag git (`v0.1-punt-control` … `v0.8.0`).

## [Unreleased]

### Afegit (2026-10-21) — tempo per trams i alternatives de BPM
- **«Detecta el tempo per trams…»** (*Analitza*): mapa de BPM **cada N
  compassos** (4 per defecte) pensat per a **cançons amb tempo variable**.
  Motor nou a `app/tempo.py`: `segueix_beats` (beat tracking per
  **programació dinàmica**, Ellis 2007) + `beats_a_trams` (el BPM de cada
  tram es **deriva** de la seua durada → la frontera cau sempre en una línia
  de compàs i el mapa passa `valida_i_normalitza_compassos`). Amb opcions de
  cada quants compassos, tolerància de fusió i offset automàtic. Tot en un
  **fil** (`FilTempoTrams`) i aplicat amb **un sol desfer**.
- **Alternatives de BPM amb fiabilitat** (`tempo.candidats_bpm`): el diàleg
  del guiat mostra les **3 millors** opcions amb el % de confiança (com
  Logic), la **referència del tema sencer** i un avís quan el BPM detectat
  cau **fora del rang configurat** (cas real: tema de 120 amb rang 50–100 →
  surt 59,9 i s'avisa del 120). Botons de ràtio **×4/3** i **×3/4** (tresets).
- **Guiat més fiable**: la 1a finestra passa de **13,7 s a 8 s** (la llarga
  donava 55,25 en un tema de 103,5), **mínim 7 s** si no hi ha loop, el
  **loop sencer** mana si interseca la finestra, i es **captura en arrancar**
  perquè un desfer no el perda. El prior s'estreny a **±10 %** al voltant de
  la referència global.
- **Opcions → BPM**: botó **«Valors recomanats (60–180 · 85–150)»** i avís
  en viu si el rang és estret (era la causa que la detecció donara la meitat
  del tempo: 99,75 en compte de 103,5).
- **Pistes de tempo** (`tempo.llegeix_pistes_tempo`): chunk **ACID** de la
  WAV i `103bpm` al nom del fitxer (només com a pista, mai com a veritat).
- **Resultat mesurat** (Otis «Dock of the Bay»): sencer **103,4** (abans
  99,75 amb el rang de l'usuari), loop **104,6** (abans 52,25), mapa de **8
  trams** de 100,4 a 106,5 validat. Motor **numpy pur** (el Q9400 no té AVX:
  res de torch/madmom).
- **21 tests nous** (`tests/test_tempo_trams.py` + GUI) i doc
  `docs/TEMPO_PER_TRAMS.md` amb la comparativa de DAW (Ableton, Logic, Pro
  Tools, Cubase, REAPER).

### Afegit (2026-10-20, 4a tongada)
- **«Parteix a la selecció A–B» als TRES carrils** (menú contextual, botó
  dret): és el «parteix aquí» fet **als dos llocs alhora** — cada frontera
  del loop (**A** i **B**) que caiga **dins** del clip seleccionat hi deixa
  un tall nou, de manera que el clip queda en **2 o 3 trossos amb el mateix
  nom** i el tros que va d'A a B queda **seleccionat**. Tot en **una sola
  operació de desfer** i amb els nuclis canònics (`pipeline.parteix_clips`,
  `tempo_map.parteix_a_compas`). Si A i B cauen fora del clip, no es parteix
  res i s'avisa per la franja Editor. A ③ el tall s'imanta a la **línia de
  compàs** i, si A i B cauen al mateix compàs, queda **un sol tall**.
  L'etiqueta mostra el rang (`Parteix a la selecció A–B (2.10–4.10s)`).
  **10 tests** (`TestParteixALoop`) + les llistes blanques de paritat
  actualitzades a 13 accions.

### Afegit (2026-10-20, 3a tongada)
- **Clic a un tram de tempo → cursor al seu inici** (paritat amb els clips
  d'acords/seccions, regla d'or #11): el `TempoLayer` emet
  `tramCursorRequested(inici)` en soltar un clic **sense arrossegada** i el
  timeline hi posa el cursor **sense snap** (les fronteres del mapa poden ser
  lliures: tall del guiat o de «compàs 1 al cursor»). El botó dret i
  l'arrossegada de vores **no** mouen el cursor. **5 tests**
  (`TestTempoLayerCursorAlClic`).
- Docs: `ESQUEMA_UI` i `EDICIO_OPERACIONS` ho documentaven **sense** estar
  implementat — ara codi i docs coincideixen.

### Afegit (2026-10-20, 2a tongada)
- **BPM només de la selecció A–B**: amb el loop marcat (encara que no
  soni), el botó **Detecta** mesura el BPM **només** d'eixe interval
  (`tempo.detecta_bpm(inici=, fi=)`); mana sobre el tram de tempo
  seleccionat. Rang < 1 s s'ignora. El **guiat** també l'aprofita: cada
  finestra mesura només la intersecció del loop amb la finestra (si és
  ≥ 1,5 s) i el diàleg ho indica.
- **Compàs 1 al cursor = offset + tall + inici del clip de tempo** (📍 i
  *Analitza ▸ Marca el compàs 1 aquí*): un sol pas de desfer fa les tres
  coses; el clip de tempo nou (si no hi havia frontera) arrenca al cursor,
  queda seleccionat i la posició es mostra en **segons** i en
  **compàs.beat** de la graella original. El guiat pas 1 reutilitza el
  mateix camí (abans eren dos desfers).
- **8 tests nous** (`TestSeleccioBpmICompas1`): loop com a font del BPM,
  sense loop, loop massa curt, offset+tall+clip amb un sol desfer, cursor
  damunt d'una frontera, cursor al final, i la finestra del guiat amb i
  sense loop.

### Corregit
- **Segfault de l'Anàlisi guiat en detectar (2026-10-20)**: el fil
  `FilGuiaBpm` cridava `Finestra.registra` **directament des del fil de
  treball** (que fa `QTextEdit.append`) — UB de Qt, avís
  `Cannot queue arguments of type 'QTextCursor'` al log i **segfault
  natiu** al bucle principal just després d'entregar el resultat (vist
  realment a la prova amb *Sitting on the Dock of the Bay*). Solució:
  mateix patró que `Feina` — el fil **emet el log per `missatge(str)`**
  (queued) i la Finestra el conect a `registra`; mai cap crida a la GUI
  des del fil. Test de regressió amb fil real + esdeveniments reals
  (`TestGuiaFilReal`).

### Afegit
- **Anàlisi guiat — implementada (2026-10-20)**: la v1 completa de l'assistent
  per a cançons amb **BPM no constant**. Pas 1: mode lliure + sense snap,
  l'usuari posa el cursor al downbeat i prem Enter → **offset + tall lliure**
  del carril de tempo (`tempo_map.parteix_trams_a`); immediatament torna el
  mode BPM·compàs amb snap a negra. Pas 2: **bucle de finestres de 16 temps** —
  cada finestra es detecta en un fil separat (`FilGuiaBpm`), el diàleg
  `DialegGuiaBpm` (modeless) deixa confirmar el BPM (**Enter · ×2 · ÷2**,
  editable a mà si la detecció falla), i cada tram confirmat s'aplica amb UN
  pas de desfer construint trams de **compassos enters**
  (`tempo_map.trams_finestra_guia`); l'últim tram absorbeix fins a la fi de la
  WAV. Al final: fusió dels trams iguals i obertura del diàleg **Analitza**.
  Cancel·lable en qualsevol moment (els trams aplicats es desfan amb Ctrl+Z).
- **Botó «Anàlisi guiat» (2026-10-20)**: a la barra *Treball*, entre
  **Obre àudio** i el selector de temps; desactivat sense WAV i durant una
  anàlisi. Obre l'assistent amb passos interactius (usuari al mig).
- **`docs/ANALISI_GUIAT.md` (2026-10-20)**: disseny de l'assistent
  (fluxe en 8 passos, finestra de 16 temps que viatja amb el BPM anterior,
  què ja existeix al codi i què falta, UI i preguntes obertes).

### Tests
- **18 tests nous**: `TestGuia` (nucli pur: tall lliure, finestres en 4/4 i
  3/4, absorció de l'últim tram, simulació completa validant el contracte),
  `TestDialegGuia` (estats detectant/detecció/×2/÷2/vàlids) i `TestGuiaFlux`
  (flux complet a la Finestra amb el fil anul·lat, pas 1, fusió final,
  cancel·lació, no-WAV). Suite: **1087 OK**.

## [0.8.0] — 2026-10-20 (BETA)

### Afegit
- **Regles de temps/compàs/graella (2026-10-20)**: nou contracte a
  `docs/REGLES_TEMPS_GRID.md`. Els trams **interiors** de tempo/compàs tenen
  un **nombre enter de compassos** i les fronteres cauen en línies de compàs;
  el primer inici i l'últim final de la WAV són les úniques excepcions.
- **Detecció de BPM per tram (2026-10-20)**: amb un tram de tempo seleccionat,
  el botó **Detecta** analitza **només eixe tram** i aplica el BPM directament
  (una sola operació de desfer). El downbeat és l'inici del tram. Sense
  selecció, es manté la detecció global.
- **Tap tempo amb clip objectiu (2026-10-19)**: amb diversos trams de
  BPM/compàs, el tap (tecla `T` o botó **TAP**) afecta el **tram de tempo
  seleccionat**; si no n'hi ha cap, el primer (transport). Els camps BPM i
  compàs de la barra segueixen eixa selecció i l'edició manual també hi va.
  Una sessió de taps (fins a 2 s sense tocar, canvi de tram o aturada) és
  **una sola operació de desfer**.
- **Loop a la selecció (2026-10-19)**: `L`, menú *Selecciona* i menú
  contextual dels **tres** carrils. Un clip → les seues fronteres; diversos o
  selecció mixta → unió (mínim inici → màxim fi); una sola operació d'undo.
  Si està sonant, alinea el cursor a l'inici.
- **Loop automàtic amb el tap (2026-10-19)**: si el tap es fa **mentre sona**,
  es crea i s'activa el loop A/B del clip de tempo objectiu (o del primer) i
  el cursor s'hi alinea. El loop es manté en aturar.

### Canviat
- **Canviar BPM/compàs d'un tram (opció A, 2026-10-20)**: el tram conserva el
  seu nombre enter de compassos; la seua fi es mou a la nova línia de compàs i
  les fronteres següents s'arrosseguen (l'últim absorbeix a la fi de la WAV).
  Si el resultat no compleix els compassos enters, el canvi es rebutja i
  s'avisa.
- **Fronteres de tempo a mà (2026-10-20)**: crear, moure, partir o fer nudge
  d'una frontera de tempo/compàs s'imanta a la línia de compàs més pròxima. Si
  deixaria un tram interior sense cap compàs sencer, es rebutja.
- **Posicions musicals en canviar el BPM (2026-10-19)**: els segons continuen
  sent la font de veritat (els acords i les seccions **no es mouen**), però les
  etiquetes de compàs i les columnes `compas_ini`/`compas_fi` de
  `estructura_ABC.csv` es recalculen amb la graella nova. Per alinear clips a
  la graella es fa servir **Quantitza**.
- **Icones de Windows (2026-10-19)**: `auto-chords.ico` passa a tenir 9 mides
  (16, 20, 24, 32, 40, 48, 64, 128 i 256): **16–128 en BMP/DIB 32-bit** i
  **256 en PNG**, segons la recomanació de Microsoft. S'hi afegeixen 20 i 40 px
  perquè Windows 10/11 els fa servir a 125 % i 150 % de DPI.
  `icones.icona_app()` prefereix l'ICO a Windows perquè Qt triï la mida exacta
  a la finestra/taskbar (amb fallback als PNG). Guards:
  `TestIcones.test_ico_windows_te_bmp_a_les_mides_petites_i_png_a_256` i
  `TestIcones.test_icona_app_a_windows_prefereix_l_ico_multimida`.
- **Despatx únic d'edició (2026-10-19)**: el menú contextual, les llistes, el
  menú principal, el teclat del timeline i el menú del loop ja no decideixen
  per carril: tots envien la intenció a **`Visor.executa_edicio()`**. La
  selecció també té un punt únic (`TimelineView.selecciona` amb
  `set`/`toggle`/`extend`) i `Visor.seleccio_activa()` inclou els **tres**
  carrils. Efectes visibles: `Ctrl+clic` i `Shift+clic` funcionen al carril de
  BPM/compàs, i `Del`, `F2` i `Ctrl+D` hi arriben (abans el QAction de la
  finestra es menjava la tecla i `main._clip_seleccionat()` només mirava
  acords/seccions). «Reanomena» amb diversos trams de tempo ja no renombra les
  seccions per error d'índex; el renom en bloc queda desactivat a ③. Contracte:
  `tests/test_despatx_edicio.py`.
- **Afegir secció** des del menú principal passa pel mateix camí que el menú
  contextual: demana **lletra i família** i, si el model no és saturat, crea el
  tros de 2 s pel mateix punt únic (abans `main.py` tenia una còpia pròpia).

### Corregit
- **Editor després de quantitzar (2026-10-20)**: en reconstruir el model es
  notifica la pèrdua de selecció i l'editor es buida/refresca; després de
  quantitzar es recupera el clip editat (si encara existeix) perquè mostre el
  **temps nou**, no el vell. Abans es podia prémer «Aplica» i tornar a escriure
  el temps anterior.
- **Trams de tempo duplicats (2026-10-20)**: en carregar es fusionen els trams
  adjacents amb el mateix BPM i compàs; no són cap canvi musical i omplien la
  pista de blocs repetits. Una partició manual de dos trams iguals es respecta
  mentre s'edita.
- **Graella i compassos amb tempo variable (2026-10-20)**: un canvi de
  **tempo** a mig compàs ja no reinicia el compàs (només els canvis de
  **compàs**/signatura obrin un compàs nou). El grid conserva el tipus de
  nivell (compàs/temps/subdivisió) i les llistes, l'editor i les columnes
  `compas_ini`/`compas_fi` de l'ABC calculen la posició amb el mapa, no amb el
  BPM del primer tram. Això arregla els acords/seccions que quedaven amb un
  compàs incorrecte després d'un canvi de BPM.
- **Partir des del menú contextual (2026-10-19)**: el tall es fa al **punt del
  clic** (amb **snap** si està actiu), no al cursor. Si el punt del clic no
  deixa marge suficient, es fa servir el cursor (també amb snap). El menú
  principal continua tallant al cursor perquè el text ho diu explícitament.
- **Duplicar sense lloc (2026-10-19)**: `Ctrl+D` / «Duplica» només actua si la
  còpia **sencera** cap després del clip o del bloc seleccionat. Si no hi cap,
  no es toca res i s'avisa a la barra d'informació (la cançó no pot créixer).
  Abans el destí s'acotava i la còpia podia caure damunt de l'original o del
  veí; a l'últim clip podia no fer res sense explicar-ho.
- **Icona de macOS al DMG/Finder (2026-10-19)**: l'`.icns` portava el 16 i el
  32 px com a PNG dins `icp4`/`icp5`/`icp6`. macOS els dibuixa **corruptes** a
  1× al Finder (finestra del DMG, còpia a Aplicacions), tot i que el Dock i
  l'app instal·lada es veien bé. Ara `ic04`/`ic05` es generen en **ARGB+RLE**,
  com `iconutil`, i s'han tret els blocs PNG petits. El staging del DMG fa
  servir `ditto` (no `cp -R`) per copiar el bundle 1:1. Guard:
  `TestIcones.test_icns_macos_usa_argb_a_16_i_32_px`.
- **Cobertura total als tres carrils (2026-10-19)**: si un projecte arriba amb
  una pista buida (sense acords o sense estructura), el visor la completa amb
  «N» / «-» de 0 a durada, com el model inicial. Tota **alta** torna a
  normalitzar la cobertura: afegir una secció en una estructura buida ja no
  deixa un illot de 2 s (queda «-» al davant i la secció fins al final), i
  afegir un acord tampoc no deixa forats. Els tres carrils queden sempre
  coberts després de l'edició.
- **Gestos i undo (2026-10-19)**: un clic o un micro-arrossegament (< 5 px)
  sobre un clip ja no deixa la marca d'undo oberta ni deixa el preview
  desplaçat respecte del model. El llindar de gest s'aplica abans d'emetre cap
  canvi; en deixar anar sense moviment s'emet `dragCancelled` i es tanca
  l'operació sense apilar res.
- **Drag del carril de BPM/compàs (2026-10-19)**: les fronteres fan el mateix
  **snap** que els clips (graella BPM/offset/mapa variable) i la guia visual ja
  ensenya el punt imantat. A més, el release del layer es processa **abans** de
  `editFinished`: abans el canvi de tempo s'aplicava després de tancar
  l'operació i quedava **fora de l'undo**. Un simple clic al tram tampoc no
  desa ni regenera res.
- **Drag de seccions (2026-10-19)**: ja no reescriu `estructura_ABC.csv` a cada
  `mouseMove`; desa al release com els acords (`_on_edit_finished`), i s'ha
  tret el segon desat d'ABC que es feia tot seguit.
- **Editor i selecció (2026-10-19)**: seleccionar un tram de BPM/compàs buida
  la franja editor (no queda un acord antic actiu). En enganxar, els trams
  enganxats queden seleccionats; el zoom a la selecció i el ressaltat visual
  inclouen tots els trams seleccionats.

### Afegit
- **Proteccions del `.acproj` (2026-10-19)**: el cru viatja dins el document i es
  tracta com una *cache*: (1) **lectura tolerant** (`saneja_analisi`: si el cru
  és invàlid es descarta i el projecte s'obre igual); (2) **límit de 512 KB**
  (`MAX_ANALISI_BYTES`): si el cru és més gran no es desa (s'avisa al log; el
  model als CSV ja hi és); (3) **`<nom>.acproj.bak`** abans de cada desat (com el
  `.rpp-bak` de REAPER).

### Canviat
- **Opcions de snap ampliades (2026-10-19)**: a més de les divisions binàries,
  el selector de graella inclou **treset de negra (2/3)**, **treset de corxera
  (1/3)** i **treset de semicorxera (1/6)**, i blocs de **2, 6, 12, 24, 32, 48
  i 64 compassos** (a més d'1, 4, 8 i 16). El snap manual també es respecta amb
  un **mapa de tempo variable** (abans queia al snap automàtic). El selector
  **força el grid visual** encara que el snap estigui apagat; amb «Auto» mana
  el zoom. Les línies de treset porten etiquetes al temps (no es poden
  representar amb la graella binària de 1/32).

### Canviat
- **Dreceres de ratolí i teclat (2026-10-19)**: `Ctrl+Shift` mantingut passa
  temporalment a l'eina **marc** (en deixar anar, torna a l'eina anterior) i
  s'elimina el gest `Ctrl+Shift`+arrossegar per duplicar (queda `Ctrl+D`).
  També s'eliminen les dreceres `Ctrl+Shift` de *Obre projecte*, *Desa com*,
  *Refer alternatiu*, *Afegeix acord* i *Afegeix secció* per evitar
  ambigüitats; l'enganxat sense snap passa a **`Ctrl+Alt+V`**. `Alt+clic` no
  fa cap acció pròpia (Alt+←/→ mou la vora dreta).

### Canviat
- **El «Mode fàcil» passa a ser «Quantitza» (2026-10-19)**: s'elimina tota la
  lògica de re-derivació del cru, la inferència compàs/mig/temps, els presets
  d'estil i el canvi automàtic de compàs. El botó i l'acció de menú es
  reciclen: **Quantitza** mou només els **inicis** dels clips del model
  (acords i/o estructura) a la graella. Abast: **tot · selecció · tot però
  només acords · tot però només estructura**. Graelles: acords de **1/8 a 1
  compàs**; estructura d'**1 a 64 compassos**. No toca BPM, compàs, offset ni
  el cru; una sola operació de desfer/refer. Selecció mixta = una sola
  operació (cada tipus amb la seua graella).

### Canviat
- **Resolució temporal unificada (2026-10-19)**: els quatre CSV del MODEL
  (`acords.csv`, `estructura_ABC.csv`, `tempo.csv`, `compas.csv`) es desen amb
  **6 decimals (1 µs)**, no 2 (10 ms). El BPM també es desa amb 6 decimals (no
  amb `:g`). La UI mostra **hh:mm:ss.mmm** i els camps d'edició accepten
  mil·lisegons. La separació mínima entre inicis passa de **10 ms a 1 ms**; els
  marges de partir, moure, redimensionar i duplicar també. MusicXML passa de
  `divisions=4` a **480**. Els fitxers editables ja no tenen resolucions
  diferents entre si.
- **Posicions musicals a 1/32 (2026-10-19)**: `pos_compas`, `TempoMap.pos`, el
  regle, el camp `C.B.S` i els noms d'export passen de **corxera (1/8)** a
  **fusa (1/32)**; el tercer camp de `compàs.temps.fusa` és **1..8**. Afecta el
  regle, la guia, `estructura_ABC.csv` i els noms d'export (que continuen sent
  `1-1-1_C.wav`). MusicXML pot escriure la **32nd** (`divisions` 480 → 60
  unitats) i el snap d'anàlisi admet fins a 8 subdivisions per temps.
- **Export amb temps exactes (2026-10-19)**: les durades dels WAV surten dels
  **segons exactes** del model (no de la graella 1/32) i l'exportació escriu
  **`manifest.csv`** amb `tipus, fitxer, inici_s, fi_s, durada_s, contingut,
  posicio` a 6 decimals. Els noms musicals es mantenen. En mode Lliure, els noms
  dels WAV passen a mil·lisegons (`0000.000s_...`).

### Arreglat
- **Graella a zoom extrem (2026-10-19)**: el pla únic de grid inclou
  **múltiples de compàs** (2, 4, 8 i 16) perquè el min zoom no siga una taca;
  si cap divisió hi cap, cau a la **més gruixuda** (abans queia a la més fina,
  `0,02 s`, i omplia el grid de milers de línies). Les etiquetes del regle no
  ixen per les vores, tenen una separació mínima de 8 px i, al min zoom, la
  línia de l'etiqueta es pinta més forta. Al max zoom, el primer compàs ja no
  es veu tallat.

### Tret
- **Els intermedis de l'anàlisi ja no són fitxers (2026-10-19)**: la carpeta
  `analisi/` (`chords_raw.csv`, `segments_raw.csv`, `meta.json`) i
  `segments.csv` desapareixen. El **cru** (sortida del motor abans de netejar)
  viu ara **dins el `.acproj`** (`dades["analisi"]`: data, durada, BPM/compàs/
  offset, opcions i els acords/talls crus). Format del document **2**; **sense
  migració** (l'app encara s'està construint).
  - L'«Analitza» escriu **directament** els 4 CSV del MODEL; el cru es queda en
    memòria i es desa al document en acabar.
  - El «Mode fàcil» llegeix el cru **del projecte** (no d'un CSV).
  - `fer_abc()` accepta els talls **en memòria**; les còpies de seguretat ja no
    han de copiar `analisi/` (viatja dins el `.acproj`).
  - Resultat: la carpeta del tema queda amb **6 fitxers** (`.acproj` + `audio/` +
    4 CSV) i els exports.

### Tret
- **MCP retirat (2026-10-19)**: fora el pont dins l'app (`app/mcp_bridge.py`), el
  servidor (`eines/mcp_auto_chords_server.py`), el llançador
  (`eines/mcp_auto_chords_launcher.py`, `AUTO_CHORDS_MCP.sh`), la prova
  (`eines/prova_mcp_completa.py`), la documentació (`docs/MCP_AUTO_CHORDS.md`) i
  la seva suite (123 tests). Decisió de l'operador: ens feia perdre temps; es
  reprendrà, si cal, quan el codi estigui estable. Còpia íntegra a `OLD/`
  (gitignored) + historial de git. La GUI és ara l'única via d'edició (cap avís
  s'ha de protegir de cap pont).
- **Tonalitat automàtica retirada (2026-10-19)**: fora l'acció «Tonalitat
  automàtica (qm-keydetector)», `partitura.detecta_fifths`/`fifths_de_to`, el
  paràmetre `key_fifths`, i el `qm-keydetector` de `pipeline.QM`/`STEPS`. La
  partitura surt sempre amb armadura de **do major**.
- **Format intern més simple**: fora el fitxer intermedi `acords_locators.txt`;
  els segments (posició · acord · durada en temps) i els events de la partitura
  es calculen **en memòria** des del model (`pipeline.segments_locators` /
  `events_partitura`). Fora el paràmetre `key_fifths` i `docs/MCP_AUTO_CHORDS.md`
  també de l'índex de docs.
- **Projecte complet des del naixement** i **diàleg d'àudio amb projecte ja
  associat** (carregar / sobreescriure amb paperera): vegeu l'entrada anterior.

### Canviat
- **«Obre àudio» amb projecte ja associat (2026-10-19)**: si l'àudio triat ja té
  projecte (la carpeta `AUTOCHORDS_<nom>/` del costat o un projecte dels
  **recents** amb el mateix àudio), l'app **pregunta**: **Carrega el projecte**
  (per defecte; mana el projecte: el seu `audio/`, CSVs i tempo) · **Sobreescriu**
  (la carpeta vella va a la **paperera** del sistema i es recrea de zero, sense
  restes de derivats ni d'`analisi/`) · **Cancel·la**. Abans donava un error
  («ja hi ha un projecte a …»).
- **Projecte complet des del naixement**: `Projecte.crea()` escriu també el
  **model inicial** (`acords.csv` 0→durada amb «N», `estructura_ABC.csv` 0→durada
  amb «A», i `tempo.csv`/`compas.csv`), no només `.acproj` + `audio/`. Així es
  pot treballar i **exportar WAVs i partitura sense analitzar mai**.
- **Exportar sense cap acord**: el missatge ja no és tècnic («tot N… Chordino»)
  sinó «No hi ha cap acord per exportar: el model només té «N»…».
- **Consolidació d'arquitectura i neteja de codi (4 fases, 2026-10-19)**: sense
  funcionalitats noves; **1.138 tests (1 skip)** i `pyflakes` net abans i
  després.
  - **Fase 1 — fora els subprocessos**: `acords_a_live.py` absorbit a
    `app/pipeline.py` (`genera_locators` / `genera_guia_html`), de manera que
    l'export ja no invoca cap intèrpret extern. `eines/launcher_pyinstaller.py`
    perd la intercepció amb `runpy` i els empaquetats (Win/macOS/portable) ja no
    inclouen l'script.
  - **Fase 2 — `Clip` com a única veritat**: `Tram` exposa `payload`; fora
    `clips_de_model`, `nom_d_acord` i `_acords_a_clips`; `normalitza_clips`
    absorbeix les regles #1/#2/#4/#8 i `normalitza_cobertura` hi delega;
    `desa_acords_csv` només accepta clips.
  - **Fase 3 — GUI prima**: la validació i les transformacions de blocs surten
    de `app/visor.py` cap a `app/pipeline.py` / `app/tempo_map.py`
    (`valida_canvis_*`, `contiguitat_seccions`, `bloc_sobre_*`,
    `renomena_*_model`, `substitueix_en_model`); el visor delega i refresca amb
    `_sincronitza_vista()`.
  - **Fase 4 — suite consolidada**: 95 fitxers de test → **5 suites**
    (`test_pipeline`, `test_tempo_map`, `test_edicio`, `test_mcp`, `test_gui`)
    amb la mateixa cobertura (cap test eliminat).
- **Refactor «inici+fi» del model de dades (S1–S5; tags `refactor-inici-fi` →
  `refactor-s1-s3-fets` → `refactor-s4-fet` → `refactor-s5-fet`)**: acords i
  estructura passen a compartir **un sol model de clips** `Clip(ini, fi, payload)`
  (abans: acords com a *marques* i estructura com a *intervals*), cosa que fa la
  paritat **#11** (*mateixes eines i comportament*) **estructural** en comptes de
  vigilada amb tests.
  - **S2** — una sola implementació per acció: `redimensiona_clips`,
    `mou_bloc_clips`, `parteix_clips`, `fusiona_clips`, `elimina_clips` (§6.4:
    l'anterior s'estira; sense veí, forat), `duplica_clips` i
    `graella.regularitza_clips` (+ wrappers dels dos tipus); el gest de vores del
    visor i el nudge hi passen; `filtra_seccions` reabsorbit (equivalència
    verificada sobre 20.000 casos).
  - **S3** — el CSV del model passa a **`inici,fi,acord`** (escriptors + tots els
    lectors alhora; sense retrocompatibilitat). Els crus d'anàlisi
    (`chords_raw.csv`/Chordino) queden en 2 columnes.
  - **S4** — el model **en memòria** del visor (i del timeline) també són clips;
    fora el despatx per tipus (`Visor._aplica_carril`).
  - **S5** — exports i derivats (WAVs, ABC, partitura/MusicXML, guia DAW, eines
    MCP) amb el nou model. Suite verda: 942 → **944 tests**.
- **Edició: duplicar i vores lliures (§2/§6.3/§6.6)**
  - **Duplicar** (`Ctrl+D` i `ac_duplica_seleccio`): la còpia va **després** del
    clip i **sobreescriu** el tram que ocupa (§2) — abans es partia pel mig. Nucli
    nou `duplica_bloc_clips` (+ `duplica_bloc_seccions`).
  - **Duplicar arrossegant per MCP**: eina nova **`ac_duplica_a`** (`t_s`), el gest
    `Ctrl+Shift`+arrossegar (l'original es queda; la còpia va al destí).
  - **Vores LLIURES** (§6.6): el gest de vores ja no s'atura al veí; estirar
    **talla/elimina** el material de sota (§6.3) i, on cap veí no tanca el buit,
    hi va el `N`/`-`.
  - Neteja: fora els «ponts» de l'MCP pel visor de proves amb **marques** (ja és de
    clips).

### Documentació
- **Auditoria de coherència (16-10-2026, `docs/INFORME_INCOHERENCIES_2026-10-16.md`)**:
  corregides **12 referències** a documents arxivats (ara `docs/archive/…`), xifres
  desfasades (**871 tests**, **80 tipus** d'acord, línies de `main.py`/`visor.py`),
  i contradiccions (`CI_WORKFLOWS` vs el contingut real dels paquets, `PROJECTES`
  vs l'MCP de projectes, botó **▶ Escoltar**, `Am/G`→`Am_G`, «Obre àudio», aubio
  retirat, paràmetres del Chordino via host propi `--param`). Vistes `ESQUEMA_UI`
  regenerades. *(Detall: l'informe; commits `bcd253d` + correccions següents.)*

### Afegit
- **MCP: paritat d'ACCIONS amb la GUI — 16 eines noves (51 → 67)**
  (`app/mcp_bridge.py` + `eines/mcp_auto_chords_server.py`). L'MCP ja pot fer
  tot el que fa l'usuari: **porta-retalls** (`ac_copia_seleccio`,
  `ac_retalla_seleccio`, `ac_enganxa_seleccio` amb `t_s` opcional),
  **selecció/edició en bloc** (`ac_esborra_seleccio`, `ac_duplica_seleccio`,
  `ac_renomena_seleccio`, `ac_selecciona_rang`, `ac_selecciona_loop`),
  **edició fina** (`ac_nudge`, `ac_mou_bloc` — el DESTÍ del moviment §6.3,
  `ac_troba_i_reemplaca`) i **estat/vista/opcions** (`ac_reverteix` sense
  confirmació modal, `ac_neteja_loop`, `ac_set_eina`,
  `ac_set_inclou_estructura`, `ac_set_inclou_partitura`). Cap eina obre
  diàlegs; totes passen per les mateixes transaccions d'undo/desat que la GUI.
  Exclusions a propòsit: Sortir, docks de vista i «Paràmetres…». Tests:
  `tests/test_mcp_paritat.py` (22) + registre ampliat a `test_mcp_bridge`.
- **`Esc` polivalent** (com als DAWs, per **ordre de prioritat**): anul·la (1) el
  **rang** en curs (`Ctrl`+arrossegar o l'eina «marc»), (2) un **loop a mig
  marcar** (el descarta i el **restaura** tal com era), (3) el **loop actiu** (el
  desactiva i **treu la caixa groga** del timeline) i (4) la **selecció**; si no
  hi ha res d'això, **no fa res**. Manté el que ja feia (cancel·la el
  **reanomenament inline** i **tanca diàlegs** — que tenen **prioritat**). El
  **timeline** emet `escapePressed` i el **visor** el resol (`_on_escape_pressed`)
  → cap estat duplicat. L'`Esc` surt ara també a les **combinacions de l'ajuda** i
  a la **caixa d'informació**. Tests: `test_eina_marc` (+5). Commits: `9533b9c`,
  `c08ebb8`.
- **Generador de les vistes de l'esquema de la UI** (`eines/genera_esquema_ui.py`):
  amb **una font única** (`docs/ESQUEMA_UI.md`) ara s'**auto-generen**
  `docs/ESQUEMA_UI.html` i `docs/ESQUEMA_UI.svg` → **mai més desfasades**.
  Ús: `python3 eines/genera_esquema_ui.py` (o `--check`, que només comprova).
  Un **test** (`tests/test_esquema_ui_gen.py`) peta si algú deixa les vistes
  velles → **sempre al dia**. *(L'SVG generat és un esquema **regenerable**; l'**art
  manual** original es conserva a **`docs/ESQUEMA_UI_manual.svg`/`.html`** — no s'ha
  perdut gens.)*
- **`Ctrl+Shift`+arrossegar un clip = duplicar-lo** (l'**única** manera): el clip
  viatja i **a l'origen hi torna una marca amb el mateix nom** → mous una còpia.
  Una sola operació de desfer; com que el model són marques, la **cobertura (#4)**
  es manté sola. Sense modificador, el gest segueix movent el clip. *(L'`Alt`+arrossegar
  es va **retirar**: dues maneres de fer el mateix només generen dubtes, i a Linux
  l'`Alt` no hi funciona. L'`Alt` només queda per a `Alt+←/→`, que és el nudge de
  la vora dreta — una altra cosa.)*
- **Tecla `E` = commuta l'eina del timeline** (intel·ligent ⇄ **marc**): és un
  *toggle* (comparteix estat amb el botó de la barra i l'acció del menú) i
  **sempre s'arrenca en «intel·ligent»**.
- **Totes les combinacions de ratolí/teclat, a la caixa d'informació i a l'ajuda**:
  reescrit el grup «Ratolí i tecles del visor» de `_dreceres()` (font **única** →
  alimenta el rotatori de la caixa **i** el diàleg *Ajuda ▸ Dreceres*): clic ·
  `Ctrl`+clic · `Shift`+clic (rang, **sempre del carril del clip**) · cos del clip ·
  **`Ctrl+Shift`+arrossegar = duplicar** · vores · **marquee** (`Ctrl`+arrossegar) ·
  **`E`** · fons · doble-clic loop · regle · botó dret · roda · Espai · `T` ·
  `Ctrl+C`/`X`/`V` · `Ctrl+Shift+V` · `←`/`→` · `Ctrl+Z`/`Y` · `F2` · `Del`.
  Test: `tests/test_eina_marc.py` (12 → 16).
- **Eina del timeline** (commutador a la barra **i** al menú *Selecciona*):
  - **«intel·ligent»** (per defecte): la d'ara — cos del clip = **moure**, vora =
    **redimensionar**, regla = **loop**, `Shift+clic` = **rang** (del carril del
    clip), `Ctrl+clic` = afegir/treure.
  - **«marc»** (rubber-band): arrossegar **no mou cap clip**; dibuixa un
    **rectangle** (que desapareix en deixar anar) → queda seleccionat tot el que
    **hi sona a dins**, i **només de les pistes que cobreixi** (marc damunt dels
    acords = només acords). `Ctrl`+arrossegar també fa un marquee temporal.
- *(Retirada la «**selecció creuada**»: el `Shift+clic` és **sempre** del carril del
  clip clicat; per agafar clips de **les dues pistes**, el **marquee**. Dues maneres
  de fer el mateix s'han eliminat.)*
- **8 timbres de piano al «▶» del panell «Tipus d'acord»**: el botó d'escolta és
  ara **només la icona ▶** i al costat hi ha un **desplegable de timbre** amb **8
  presets de família piano** (referència **General MIDI 1-8**): *Piano de cua ·
  Piano brillant · Piano elèctric de cua · Honky-tonk · **E-piano Rhodes** (defecte)
  · E-piano FM (DX7) · Wurlitzer · Piano de joguina*. Síntesi `numpy` (additiva
  inharmònica per als pianos + FM amb les regles clàssiques per als e-pianos). Al
  **Q9400** la síntesi (sobretot els pianos acústics, ~24 ones/nota) va en un
  **fil** amb `float32` → **la UI no es congela** (el so arriba ~0,2 s als e-pianos
  i ~1 s als acústics).
- **▶ Escoltar al panell «Tipus d'acord» (audició amb piano elèctric)**: el botó
  ja és **actiu** — sent l'acord triat (arrel + tipus) amb un **e-piano FM estil
  Rhodes** sintetitzat (`app/acord_audio.py`, **NOU**: `numpy` pur, **cap
  dependència nova**). Cada pulsació toca **primer els graus per separat (arpegi)
  i després tots alhora**, amb un **motor efímer** (no toca la reproducció de la
  cançó) i tot dins `try/except` (si l'àudio falla, avís clar; mai un crash). Els
  intervals surten de la mateixa `xifrat.TAULA_TIPUS`. Tests: `tests/test_acord_audio.py`
  + `test_panell_xifrat`.
- **Treballar SENSE analitzar (roadmap §14.1)**: en carregar un àudio, si el model
  és buit es crea el **punt de partida editable** (`pipeline.model_inicial()`):
  **1 clip d'acords** (`N`, «sense acord») + **1 clip d'estructura** (`A`) que
  cobreixen **tota la cançó**, i es **desen els CSV** (perquè l'export es pugui fer
  de seguida). Conseqüència: l'**anàlisi (Chordino/qm) passa a ser OPCIONAL**, mai
  un requisit previ; sense anàlisi **no es crea** la capa crua (`analisi/`).
  Test: `tests/test_sense_analisi.py` (8).
- **Xifrat — parèntesis i més tipus**: `7(9,13)` → `7add9add13`, `7(b9)` → `7b9`
  (abans els graus s'«engrunaven»); s'accepten les paraules senceres
  `major`/`minor`; i s'afegeixen tipus (`7sus2`, `9sus4`, `13sus4`, `add2`,
  `-add2`, `-add4`, `-(b6)`, `7#9b5`, `7#9#5`, `7(9,13)`, `7b13`, `7#9b13`,
  `maj7#5#11`, `maj7(9/11/13)`, `-9+7`…).
- **Panell «Tipus d'acord»** (dock desacoplable a l'esquerra; *Visualitza ▸
  Mostra els tipus d'acord*): construeix un xifrat **clicant** — **Arrel** i
  **Baix** (text lliure) + una **llista de 80 tipus** (de menys a més complex;
  cada fila duu els **alternatius** i els **graus**). **Clicar un tipus només
  omple** la casella «Nom» de l'editor (no aplica res: ho fa l'usuari amb
  «Aplica»). Font única: `xifrat.TAULA_TIPUS` + `xifrat.composa()`. El botó
  **▶ Escoltar** va sortir **desactivat** en aquest punt; es va **activar** al
  bloc següent (audició amb **e-piano**; vegeu l'entrada de dalt). Test: `tests/test_panell_xifrat.py`. Doc:
  `docs/TIPUS_XIFRAT_ACORDS.md` + mockup aprovat (`PANELL_TIPUS_ACORD_mockup.*`).
- **Xifrat canònic ampliat a (gairebé) tots els tipus d'acord** (`app/xifrat.py`):
  **taula de tipus → `<kind>` MusicXML + graus** (`TIPUS`) i **extensions/alteracions
  via `<degree>`** (`#5`, `b9`, `#9`, `#11`, `13`, `add9`, `no5`, `#5b9`…).
  Entén i canonitza: **dobles alteracions** (`C##`/`Cbb`/`Cx` → `±2`), `6/9` → `6add9`,
  `m(maj7)` → `-Maj7`, `#11`/`add9` sense arrel base → **tríada major**, i conserva el
  que no és estàndard (`7alt`). `partitura.harmony_xml` ara **escriu els `<degree>`** →
  MuseScore ho **mostra i ho reprodueix** bé. **2 bugs reals arreglats**: les **dobles
  alteracions** donaven `±1`, i **`C7alt` perdia l'`alt`**. Tests: `test_xifrat` i
  `test_partitura`.
- **Notació canònica del xifrat (`app/xifrat.py`, font ÚNICA)**: l'app desa
  **sempre** els acords en una **forma canònica** (decisió de l'operador,
  «opció 3», 2026-10-15). Entén el que escrigui l'usuari i ho deixa bé: menor
  `-` (`Am`/`Amin`/`ami` → `A-`), major sense marca (`Cmaj`/`CM`/`CΔ` → `C`),
  `Maj7`/`-7`/`-Maj7`, `dim`/`dim7`/`aug`, `-7b5` (`Bø` → `B-7b5`),
  `sus2`/`sus4`, `6`/`-6`, `9`/`11`/`13`, i baix amb `/` (`Am/G` → `A-/G`;
  `C6/9` **no** és un baix). `pipeline.saneja_nom_acord` hi **delega** → tots
  els camins d'entrada (editor, renombrar, renom en bloc, alta, **MCP**,
  troba-i-reemplaça) queden en canònic. Doc: `docs/NOTACIO_XIFRAT.md`.
  Test: `tests/test_xifrat.py` (5).
- **Caixa d'informació amb rotatori de dreceres i consells**: quan el ratolí
  **no** és sobre cap botó, camp o zona amb informació, la caixa (a baix a la
  dreta) ja no queda morta — hi gira un **panell de consells + les dreceres REALS**
  (llegides dels menús, agrupades com al diàleg d'ajuda), canviant cada ~8 s. Si
  el ratolí és sobre la mateixa caixa, **no rota** (no canvia mentre es llegeix).
  Test: `tests/test_info_box_consells.py`.
- **Selecció per rang (`Shift+clic`) a les DUES pistes, per TEMPS**: el rang ja no
  compta índexs d'un sol carril — s'inclouen **tots els acords i totes les seccions**
  l'inici dels quals cau dins el rang. Així es pot agafar «2 estructures + 20 acords»
  de cop per copiar/retallar/enganxar/esborrar/renombrar en bloc. Test:
  `tests/test_seleccio_creuada.py`.
- **Banda del loop — doble-clic i botó dret**: **doble-clic** dins la banda del loop
  selecciona **tot el que hi ha a dins** (acords I seccions) i deixa el **cursor al
  final** del loop (a punt per enganxar-hi just després); **botó dret** obre un menú
  amb *Copia/Retalla tot el que hi ha dins el loop* i *Enganxa al cursor*. Test:
  `tests/test_loop_copia.py`.
- **Botó «Mode fàcil» a la barra principal** (al costat de BPM/compàs): obre el mateix
  diàleg que *Analitza ▸ Mode fàcil…* en un clic.
- **Renom en bloc amb selecció MIXTA (tipus actiu, opció A)**: amb acords + seccions
  seleccionats, `F2`/«Aplica» renombra **només els del tipus del clip actiu** (abans no
  feia res). Els menús de les llistes mostren **«Reanomena N acords/seccions…»** i el
  botó **«Aplica»** de l'editor aplica el camp **Nom** a **tots els seleccionats del
  tipus actiu** (estil fulla de càlcul); l'inici NO s'aplica en bloc. Tests:
  `test_rename_seleccio.py`.
- **La vista segueix el cursor (mantenint el zoom)**: en seleccionar una fila de les
  **llistes** (acords o estructura), el timeline fa **pan** perquè el cursor quedi
  visible — només si surt de la zona còmoda i **sense canviar el zoom**.
- **Cursor amb snap (com un DAW)**: amb el snap actiu, el **cursor segueix la
  graella** en clicar-lo/moure'l al timeline; els **moviments programàtics** (barra
  lliscant, llistes, reproducció, alineació del loop i **MCP**) mantenen la posició
  **exacta**.
- **Backups més complets i lleugers**: `fes_backup()` ara guarda el **document**
  (`.acproj` amb l'**estat viu**) + els **fitxers importants** (CSVs d'acords/
  estructura/segments i locators) + la carpeta **`analisi/`** (l'anàlisi crua);
  **NO** copia l'àudio ni els exports (derivats i grossos) i **no duplica** si el
  contingut no ha canviat des de l'última còpia. L'autosave ho registra al log.
- **Menú «Retalla / Copia / Enganxa»** (`Ctrl+X` / `Ctrl+C` / `Ctrl+V`) a **Edita** (i
  al **menú contextual del clip**): les mateixes operacions que la barra/teclat, ara
  també **descobertes al menú**. En copiar, el **cursor va al final del bloc** perquè
  «Enganxa» hi pegui just a continuació.
- **Tancament intel·ligent**: en tancar, l'app detecta els **canvis** (els ajustos
  del projecte **i** les edicions de la cançó) i **només** avisa si n'hi ha, oferint
  **Desa / Descarta / Cancel·la**; **mai tanca** si el desat falla. Test:
  `tests/test_tancament.py` (7).
- **Graella en compassos**: el desplegable de snap (barra Transport) afegeix
  **1 compàs · 4 · 8 · 16 compassos** (a més d'Auto (zoom) i les subdivisions Negra/
  Corxera/Semicorxera/Fusa/Treset); depèn del **compàs** (a 120 BPM 4/4, 1 compàs =
  2 s; en 3/4, 1,5 s). El **snap i el nudge** segueixen la divisió triada.
- **Graella configurable + interruptor de snap** (barra d'eines): un botó **Snap**
  (activat/desactivat) i un selector de **divisió** (Auto (zoom) · Negra 1/4 ·
  Corxera 1/8 · Semicorxera 1/16 · Fusa 1/32 · Treset 1/12) que fixa on encaixen
  els clips **i el pas del nudge** (`←`/`→`). En mode **Lliure** el snap va lligat
  al zoom. Test: `tests/test_snap.py` (6).
- **Nudge amb teclat** (`←`/`→`): mou la **vora esquerra** (l'inici) del clip seleccionat
  **un pas de graella** (la mateixa divisió que el snap); **`Alt+←/→`** mou la **vora
  dreta** (estirar/encongir). Per a les **seccions**, mou la **frontera** amb la veïna.
  Una sola operació de desfer; sense selecció no fa res; les regles d'or es mantenen
  (només es mou una frontera → ordre i contigüitat intactes). Test: `tests/test_nudge.py` (6).
- **Graella musical («mode fàcil») + capa d'anàlisi crua** (`app/graella.py`, **NOU**):
  - **`analisi/` (capa crua, evidència)**: l'anàlisi de Chordino i de l'estructura es desa
    **sense netejar** (`chords_raw.csv`, `segments_raw.csv`, `meta.json`) i **no es toca
    mai** (ni l'edició, ni el mode fàcil, ni els canvis de BPM/compàs/mode) → es pot
    **reintrepretar**.
  - **Mode fàcil** (`Analitza ▸ Mode fàcil: re-regularitza a la graella…`): encaixa els
    canvis d'acord a la **graella** (ritme harmònic: `auto`/`compàs`/`mig`/`temps`) i, si
    cal, els talls de **secció** a **blocs** (mòdul de compassos). Una sola operació de
    desfer; la **cobertura (#4)** es manté. També s'aplica en **analitzar**.
  - **Presets d'estil** (14: Pop/Blues/Bulería/Swing…) al diàleg de mode fàcil.
  - **Inferència automàtica** del nivell de ritme harmònic i del cicle de blocs.
  - Eina MCP **`ac_regularitza`** (mode fàcil) → **51 eines** (vegeu `docs/MCP_AUTO_CHORDS.md`).
- **Fix — els CSV/export van al PROJECTE**: `visor._carpeta_acords()` ara usa la carpeta de
  sortida del projecte (abans la derivava del WAV, que viu a `<projecte>/audio/`).
  Test: `tests/test_projectes_gui.py`.
- **Troba i reemplaça global** (`c806b3f`): `Edita ▸ Troba i reemplaça…` (**`Ctrl+H`**)
  substitueix **totes** les aparicions exactes d'un **xifrat** (acords) o d'una **etiqueta**
  (estructura) a tot el tema, en **una sola operació de desfer** i **sense canviar cap temps**
  (regles d'or intactes). Diàleg amb camp, «troba» i «reemplaça per»; si no en troba cap, no fa
  res. Test: `tests/test_troba_reemplaca.py` (5).
- **Renom en bloc + selecció persistent** (`b7a6cb5`): `F2` sobre una selecció del
  **mateix tipus** reanomena **tots** els clips de cop (N acords → un nom · M seccions →
  una lletra); una selecció **mixta** no es renombra. Després d'editar/reanomenar, el clip
  queda **seleccionat** (timeline + llista + franja Editor) i les llistes es refresquen a
  l'instant (regla d'or #11). Test: `tests/test_rename_seleccio.py` (6).
- **Projectes autocontinguts («com un DAW»)** (`app/projecte.py` + GUI): en obrir un
  WAV, l'app pot crear una **carpeta que ho conté tot** — el document **`.acproj`**
  (JSON), una **còpia de l'àudio** a `audio/`, els CSVs a l'arrel i `backup/`. GUI:
  **Obre projecte** (`Ctrl+Shift+O`), **Obre recent**, **Desa** (`Ctrl+S`),
  **Desa com** (`Ctrl+Shift+S`), **Desa una còpia**, **Reverteix**; títol amb `*` si hi
  ha canvis. **Autosave** a `backup/` cada 60 s (rotació de 10) i **marcador de sessió**
  amb **recuperació** a l'arrencada si l'app va caure. Migració d'`AUTOCHORDS_<nom>/`
  velles. Detall: `docs/PROJECTES.md`.
- **Regla d'or #11 — paritat d'edició acords ↔ estructura** (els clips d'acord
  tenen ara **exactament les mateixes eines** que els de secció). Backend nou
  **`pipeline.parteix_acord()`** i **`pipeline.fusiona_acords()`** (mirall de
  `parteix_seccio()`/`fusiona_seccions()`); al visor **`parteix_acord()`**,
  **`fusiona_acord()`** i **`fusiona_seccio()`** (amb desfer/refer). Nous punts
  d'usuari: **Edita ▸ Parteix l'acord al cursor…**, entrada **«Parteix l'acord…»**
  al menú contextual del clip (la de secció ja hi era) i el **menú de la llista
  d'acords** alineat amb el de seccions (*Afegeix · Partir · Fusionar amb
  anterior · Fusionar amb següent · Elimina*). El tall deixa l'esquerra amb el nom
  i el clip nou (dreta) amb el nom triat (per defecte, el mateix). Regla
  documentada a `docs/REGLES_DE_LA_APP.md` (§11) i blindada amb el test
  **`tests/test_regla11_paritat.py`**. `AGENTS.md` passa a 11 regles.

### Canviat
- **Moviment de bloc: CORREGIT + paritat d'estructura (regla d'or #11)**. El bloc
  només **tapa el seu tram nou** `[a',b')`: abans s'esborraven TOTS els clips que
  quedaven entre l'origen i el destí (es perdien clips que no hi tocaven). Ara el
  que hi ha entremig es queda quiet i la cobertura la manté el model de marques.
  I l'**estructura** es comporta **exactament igual** que els acords:
  `pipeline.mou_bloc_seccions` (nov), arrossegar el **cos** d'una secció al visor
  (`_on_section_body_drag` + `_tanca_bloc`) i `ac_mou_bloc` amb **`kind`**
  (`chord`|`section`). Tests: els 2 casos de salt llarg (acords i estructura) i el
  cas de la secció A al compàs 29.1.
- **El símbol dels forats d'estructura és ara `-` a TOT ARREU** (§6.1): també a
  `normalitza_cobertura` (capçalera i forats interns), que encara hi posava `N`
  (el símbol dels acords). Amb això no conviuen dos símbols per al mateix concepte
  i el que genera un moviment i el que genera la normalització són idèntics.
  Tests: `test_seccions_capcalera_sense_seccio`,
  `test_moure_el_primer_obre_capcalera_sense_seccio` i 2 més actualitzats.
- **Neteja de codi mort**: fora `TimelineView._move_section_group` (el moviment de
  blocs de seccions ja el fa `_on_section_body_drag` + `_tanca_bloc`, §6.3).
- **Moviment d'un BLOC d'acords: destí amb tall/eliminació** (`PLA_EDICIO_LLIURE` §6.3):
  en arrossegar el **cos** d'un clip (sol o dins d'una multi-selecció contigua) el
  bloc es mou **preservant la seva durada** i, al **destí**, el que queda **a sota**
  es **talla** (se'n conserva el tros de fora) o **s'elimina** (si no en queda cap
  tros) — «**mana l'últim editat**». L'**origen** el tanca el veí: endavant, el clip
  anterior s'estira fins a l'inici nou; endarrere, el posterior fins al final nou. El
  gest ja **no va limitat** pels veïns. Nova funció pura `pipeline.mou_bloc_acords`
  (el gest la resol **al release**, perquè pot eliminar marques i cal re-renderitzar);
  el model de MARQUES fa que l'origen es tapi tot sol. Tests: `tests/test_moviment_desti.py`
  (16) + `test_mou_grup_*` actualitzats.
- **Caixa d'informació millorada (llegir-la al teu ritme)**: el **rotatori** ara
  gira cada **14 s** (abans 8, massa ràpid), el **1r panell s'adapta a l'eina
  vigent** del timeline («marc» vs «intel·ligent») i hi ha **més consells**
  (copiar/enganxar sobreescriu, `Ctrl+Shift+V`, nudge…). Un **clic a la caixa**
  la **PARA** (`_INFO_PAUSA_S` = 30 s) i el clic **següent avança** de «pantalla»;
  si no cliques, es torna a moure sol. El **missatge transitori** (desfer/refer…)
  té **format propi** (banner) per no confondre's amb el rotatori.
  Test: `tests/test_info_box_consells.py` (8).
- **S'ha acabat la divergència de noms CSV ↔ fitxer exportat**: com que el
  MODEL ja ve en notació **canònica** (`app/xifrat.py`), `acords_a_live.py`
  **deixa de reescriure** els noms (tret l'antic `style()`) i viatgen
  **verbatim** → el nom del WAV exportat i el del CSV **coincideixen**
  (`A-`, `A7_G.wav`).
- **`/` (acord amb baix) als noms de FITXER → `_`, mai `-`**: `safe_filename`
  (pipeline i partitura) passa `/` i els separadors de path a `_`, perquè al
  xifrat el `-` vol dir «menor» (`A7/G` → `A7_G.wav`; abans hauria xocat amb
  `A7-G`).
- **«Obre…» → «Obre àudio»**: el botó de la barra i l'acció de menú (*Fitxer ▸
  Obre àudio…*, `Ctrl+O`) ara diuen el que fan de debò — obren
  **wav/mp3/aiff/flac/m4a/ogg/opus/wma**, no només WAV.
- **Copiar/enganxar amb model SOBREESCRIURE** (regla d'or #4): `Ctrl+C`/`Ctrl+X`/`Ctrl+V`
  ja **no insereixen** clips (la cançó no pot créixer) — l'enganxat **substitueix** el tram
  de la mateixa durada que el bloc copiat. L'àncora és el **cursor**; si no l'has mogut,
  enganxa just **després** del bloc copiat. Retalla si sobrepassa el final, actua només
  sobre els carrils presents (acords / estructura / tots dos) i deixa **seleccionat** el
  bloc enganxat (una sola operació de desfer). Test: `tests/test_copiar_enganxar.py` (7).
- **`SectionItem` amb el mateix tracte que `ChordItem`**: ara emet `dragStarted`
  i fixa el cursor de gest (redimensionar/moure) igual que els acords.
- **«Partir» uniforme**: el «Partir secció aquí» del menú de la llista parteix
  ara pel **cursor** (com la resta de punts de partir), en lloc de demanar el
  temps per número — mateix tracte que els acords.

### Corregit
- **El clic a la caixa d'informació no responia**: un `QTextEdit` és una
  `QAbstractScrollArea` → rep els clics al seu **viewport**, no al widget; el
  filtre d'esdeveniments només era al widget. Ara es filtra **també el viewport**
  → el **clic per pausar/avançar** el rotatori funciona. *(Bug de la «caixa
  d'informació» de la tongada.)*
- **L'ajuda no inventa tecles**: deia **`Ctrl+Shift+clic`** per al «rang a les 2
  pistes», i **aquesta combinació NO existia al codi** (la «selecció creuada» era
  una **opció del menú** — que després **s'ha retirat del tot**, vegeu «Afegit»).
  Ara l'ajuda ho diu bé, tant a la **caixa d'informació** com al **diàleg d'Ajuda**
  (font única `_dreceres()`).
- **Copiar/enganxar ja no falla «en silenci» (bug real de l'operador)**: quan el
  bloc acabat **exactament** en una marca del model i el *snap* el movia ~2 ms, la
  validació (≥ 10 ms) **rebutjava l'enganxat SENCER** i només ho deia al log →
  a pantalla «no passava res». Ara, amb les convencions dels DAWs professionals
  (Cubase/Reaper/Pro Tools/Logic/Final Cut):
  (1) l'**àncora fa snap primer als EVENTS** (marques = vores de clip; el seu
  instant **exacte**) i la **graella musical** només si no hi ha cap marca a prop;
  (2) el bloc viatja **RÍGID** (no s'arrodoneix cada element — evita deformar
  l'espaiat intern; `Grid Relative` del Cubase);
  (3) un rebuig (o un «res a canviar») surt **a pantalla** (`avis_editor`), no
  només al log; i (4) **`Ctrl+Shift+V` se salta el snap** (`hold N` del Final Cut).
  Nous: `Timeline.snap_a_marca()` / `marques_temps()` i `SNAP_MARCA_PX = 10`
  (tolerància **en píxels** → depèn del zoom, com el «snap distance» del Reaper).
  Doc: `ROADMAP` **§15** (convencions de DAW). Test: `tests/test_copiar_enganxar.py`
  (+4; **verificat que fallen amb el codi anterior**).
- **Export amb el pont MCP actiu**: ja **no obre el gestor de fitxers** a
  l'escriptori (l'agent que ha demanat l'export no necessita finestres; abans,
  5 exports amb l'MCP = 5 finestres obertes).
- **Xifrat — `Cmajor`/`Cminor` (paraules senceres)**: abans es tallaven malament
  (`Cmajor` → …`Majdimr`); ara s'entenen com a major/menor.
- **Partitura amb acords VELLS**: `_exporta_partitura` ara **regenera**
  `acords_locators.txt` si és més vell que `acords.csv` (els locators són un
  **derivat** del model; si s'editava el model després de l'últim export de
  WAVs, la partitura llegia locators antics). Nou `_assegura_locators()`.
- **Partitura (MusicXML) — MuseScore no duplica l'arrel**: el `<kind text="…">`
  de fallback porta **només el sufix** de la qualitat (el root ja s'escriu a
  part) → s'ha acabat el «AA-maj7».
- **«Exporta WAV's»/«Exporta partitura» s'activen en OBRIR un projecte**: abans
  només s'activaven al final d'una **anàlisi** → obrir un projecte (amb els CSV
  ja fets) les deixava apagades i no feien res. Nou `_habilita_export()`.
- **El visor desa els CSV a la carpeta del PROJECTE des del primer moment**:
  `Visor.__init__` accepta `sortida` i `main` l'hi passa → no es crea cap còpia
  estranya `AUTOCHORDS_…/` dins `audio/`.
- **Exportar «sense estructura» ja NO esborra el MODEL**: `_neteja_estructura_vella`
  ja **no toca `estructura_ABC.csv`** (el model del projecte) — la marca «Inclou
  estructura» decideix què s'**exporta**, no què es **conserva**. Només s'ofereix
  treure els **derivats de l'export anterior** (`wavs_estructura/`) i **sempre amb
  confirmació** (nou `_ho_confirma`, amb «Cancel·la» per defecte); amb el **pont MCP
  actiu** no s'esborra mai res ni es mostra cap diàleg modal. Test:
  `tests/test_export_neteja_estructura.py` (3).
- **Loop — la frontera B ja no s'endú el clip següent**: el loop fa servir un
  interval **semi-obert `[A, B)`** (`keys_dins_rang(..., inclou_fi=False)`); abans un
  clip que comença **exactament** a `loop_b` hi entrava de més. El `Shift+clic` es
  manté **inclusiu** (el clip on cliques sí que hi ha d'entrar). Test:
  `tests/test_loop_copia.py`.
- **Reconstruir el timeline ja no perd el ZOOM**: en reconstruir els items (desfer,
  editar, reanomenar, enganxar…), ara s'hi aplica la **vista actual** (`view_left`)
  — abans es pintaven com si no hi hagués zoom i el clip **«saltava» fora de vista**.
  Tests: `tests/test_zoom_rebuild.py` (2).
- **Backups — noms únics i ordre correcte**: el segell dels backups ara porta
  **microsegons** (`YYYYMMDD-HHMMSS-ffffff`). Abans, quan se'n feien molts dins el
  mateix segon, el sufix `-2/-3…` trencava l'ordre **lexicogràfic** a partir de
  `-10` → la rotació podia quedar-se les còpies equivocades. Test:
  `test_projecte_backups` (molts backups dins el mateix segon).
- **Projectes — no sobreescriure un projecte existent**: `Projecte.crea()` ara
  **peta** si la carpeta de destí ja té un `.acproj` (abans el podia sobreescriure
  i perdre el document —tempo/vista—, sobretot en la migració *in situ*). Tests
  de casos límit a `test_projecte` i `test_projecte_backups` (inclòs
  `max_backups=0` = no rotar). I **`tests/test_graella_bpm.py`** (NOU): la
  regularització a **BPM extrems**, els guards de BPM 0 i el mode fàcil a BPM
  baix/alt amb offset (comprovant la cobertura #4).
- **Nudge — marca d'undo penjada**: quan el nudge no pot fer res (l'últim acord
  cap a la dreta, la 1a secció cap a l'esquerra, índex fora de rang…), ara **no
  s'emet `editStarted`** → no queda una marca d'undo de més. Tests de casos límit
  afegits (`test_nudge` +3, `test_copiar_enganxar` +1, `test_graella` +casos límit).
- **Regla d'or #1 blindada al backend**: `pipeline.normalitza_cobertura` ara
  **reordena** els acords i les seccions per temps d'inici (abans l'ordre només el
  garantia el visor → un CSV editat a mà podia exportar-se desordenat).
- **MCP — `ac_parteix_acord`/`ac_parteix_seccio`**: `t_s` es llegia com a **enter**
  i **truncava** el temps (`0.5 → 0`); ara és float. Trobat pel harness en viu
  (`eines/prova_mcp_completa.py`).

## [0.7.0] — 2026-10-14 (BETA)

### Seguretat
- **Import d'àudio (ffmpeg/ffprobe) endurit**: les comandes d'`info()` i
  `converteix_a_wav()` porten ara **`-nostdin`** i **`-protocol_whitelist
  file,pipe`** abans de l'entrada, perquè un fitxer disfressat (playlist
  HLS/concat, subtítol…) no pugui fer que ffmpeg llegeixi altres fitxers ni faci
  peticions de xarxa. Les rutes es passen sempre **absolutes** (i amb `./` si
  comencessin amb `-`), sense filtrar-ne cap caràcter. Si un ffmpeg molt vell no
  entén `-protocol_whitelist`, es reintenta sense l'opció i es registra al log
  (mai es trenca l'obertura d'àudio).
- **Bloqueig d'instància única per usuari i segur**: el fitxer de bloqueig ja
  no viu a un `/tmp` compartit amb un nom global (on un usuari podia bloquejar
  un altre) sinó a **`XDG_RUNTIME_DIR`** (o el directori d'estat de
  `config.py`), amb l'**uid/nom d'usuari al nom**. S'obre amb
  `os.open(O_RDWR|O_CREAT|O_NOFOLLOW, 0o600)` → **no segueix enllaços
  simbòlics** i només el propietari hi accedeix. En sortir **només s'allibera
  el bloqueig**, no s'esborra el fitxer (evita una carrera entre instàncies).
  Windows manté `msvcrt.locking`.
- **Pont MCP endurit**: el fitxer d'acord `temp/mcp_bridge.json` (que porta el
  **testimoni**) es crea amb **permisos `0600`** (`os.open` amb mode +
  `os.replace`). El socket té **límit de longitud de línia (1 MiB)** — es
  respon error i es tanca la connexió **abans de processar-la** — i **límit de
  connexions simultànies (8)**; el **testimoni es valida abans de qualsevol
  altra feina**. `ac_open_wav` segueix acceptant **qualsevol ruta** (invariant 1).
- **Noms de fitxer segurs a Windows (`pipeline.safe_filename`)**: a més dels
  separadors de camí i els caràcters de control, ara substitueix els
  **caràcters reservats a Windows** (`: * ? " < > |`), treu el **punt o espai
  final** i evita els **noms reservats** (`CON`, `PRN`, `AUX`, `NUL`,
  `COM0-9`, `LPT0-9`). Si dos noms queden iguals després de netejar/truncar es
  **desambigüen amb un sufix** (`_2`, `_3`…) — els noms únics **no canvien
  mai**. Els noms d'acord habituals (`C`, `C#m7`, `N`, `Am/G`→`Am_G`…) queden
  **idèntics** (hi ha un test «daurat»).
- **Directoris temporals de l'app: es netegen sempre**: els `ac_ttl_`/`ac_qm_`/
  `ac_key_` que crea l'anàlisi (transform `.ttl`, valors del qm, tonalitat) ja
  no s'acumulen a `/tmp`: s'esborren en un `finally` (també si peta) amb
  `pipeline.esborra_tmp()`, que **només** esborra directoris amb aquests
  prefixos propis.
- **Baixada verificada de dependències**: eina nova
  **`eines/baixa_verificat.py`** (només biblioteca estàndard, Python ≥ 3.8 del
  sistema): baixa per **HTTPS**, amb reintents i timeout, i **comprova el
  SHA256**; si no quadra → error, codi de sortida ≠ 0 i **no deixa cap fitxer a
  mitges**. Fitxer nou **`eines/deps_fixades.env`** amb URL + versió + SHA256 de
  tot el que es baixa (CPython portable, ffmpeg de Linux/macOS/Windows,
  appimagetool, icones Lucide) i el **commit** dels repositoris que es
  compilen.
- **Scripts de build amb baixades VERIFICADES**: `crea_portable.sh`,
  `crea_appimage.sh`, `baixa_icones.sh` i `compila_vamp_plugins.sh` ja no baixen
  res directament — fan servir **`eines/baixa_verificat.py`** amb les variables
  de **`eines/deps_fixades.env`**. Cap URL «mòbil» (`continuous`, `getrelease`,
  `master`, `-release-`) i tot `curl` amb `-f` i `--proto '=https'`. Els
  repositoris que es compilen es fixen per **commit** i es verifiquen amb
  `git rev-parse` (`clona_commit`).
- **GitHub Actions endurit** (un commit per workflow): totes les accions es
  fixen per **SHA de commit**, amb la versió en comentari
  (`checkout@fbc6f399… # v5`, `setup-python@ece7cb06… # v6`,
  `upload-artifact@b7c566a7… # v6`, `msys2/setup-msys2@ec48f7c5… # v2`);
  **`permissions: contents: read`** a tots els workflows i **`contents: write`
  només al job que crea el Release**; **`persist-credentials: false`** a tots
  els `checkout`. El ffmpeg de **macOS** (evermeet) i el de **Windows** (gyan)
  passen a URL amb **versió explícita + SHA256** verificat amb
  `baixa_verificat.py`, i els repositoris que es compilen (libsndfile,
  vamp-plugin-sdk) es fixen per **commit**.
- **Dependències Python fixades i vigilades**: `requirements.txt` passa a pins
  **exactes** — `PyQt5==5.15.11` (i `==5.15.10` a macOS 10.13, amb marcador de
  plataforma), `PyQt5-Qt5==5.15.19`, `PyQt5_sip==12.19.0`, `numpy==1.26.4`,
  `sounddevice==0.5.6`, `cffi==2.0.0`. Nou test **`tests/test_requirements.py`**
  que **peta** si algú introdueix `numpy>=2` o `PyQt6` (ho mira a
  `requirements.txt`, `pyproject.toml` i els workflows). `--require-hashes`
  queda **pendent** (calen els hashos de totes les rodes de les 3 plataformes);
  les instruccions són dins del mateix `requirements.txt`.
- **Memòria cau de les baixades (no baixar dues vegades)**: `baixa_verificat.py`
  desa cada fitxer verificat a **`.baixades/<sha256>`** (gitignorada) i el
  reutilitza; al CI, **`actions/cache`** conserva aquesta carpeta entre
  execucions (clau: SO + hash de `deps_fixades.env`). `--sense-cache` ho
  desactiva. Els fitxers **no** es guarden al repositori (GitHub rebutja
  > 100 MB; el ffmpeg de Windows en fa 114) — vegeu `docs/SEGURETAT.md`.
- **`SHA256SUMS.txt` als Releases**: en publicar una versió, el workflow
  `release.yml` genera la «petjada» (SHA256) de **tots** els paquets i l'adjunta
  al Release → qui baixa un paquet pot comprovar que és exactament el publicat
  (`sha256sum -c SHA256SUMS.txt`).

### Canviat
- **Les carpetes que genera l'app porten ara un PREFIX**: `AUTOCHORDS_<nom>`
  (abans `<nom>_ACORDS`). P. ex. `Tema.wav` → **`AUTOCHORDS_Tema/`**. Així totes
  les carpetes de l'app queden juntes i al davant quan s'ordena el directori de
  la cançó. El nom surt d'una **font única** (`pipeline.carpeta_sortida`), que
  fan servir l'anàlisi, el visor i `wav_a_wavs.py`; el títol per defecte de la
  partitura surt del prefix. **Sense retrocompatibilitat** amb carpetes
  `_ACORDS` existents (decisió de l'operador): les velles no es detectaran.

- **Export de WAVs asíncron**: `ac_export_wav` amb `async:true` torna de seguida i el
  progrés es consulta a `ac_status` (`exportant`/`exporta_iniciat`).
- **«Dreceres de teclat» i «Quant a»** són **no-modals** amb el pont MCP actiu.
- **Manteniment — A MÀ: Dependabot RETIRAT** (decisió de l'operador). Els pins són
  **deliberats** (Q9400 sense AVX, macOS 10.13, roda Windows) i Dependabot obria PRs
  perjudicials; les actualitzacions es fan a mà amb validació al CI.

### Afegit
- **`docs/REGLES_DE_LA_APP.md`**: totes les **regles d'or (invariants)** de l'app
  en un sol lloc, **numerades** (1–10) amb la seva validació al codi i tests.
  Enllaçat des del `ROADMAP` i el `DEVELOPING`.
- **`docs/SEGURETAT.md`**: resum per a mantenidors de tot l'**enduriment de
  seguretat** (app + cadena de subministrament) i de **com es manté**
  (actualitzar una versió amb `baixa_verificat.py`, què no s'ha de fer).
  Enllaçat des del `DEVELOPING.md`.
- **`SECURITY.md`** (arrel): com informar d'un problema de seguretat (contacte
  del `README`), què es considera un problema i la política d'actualitzar les
  llibreries natives a cada versió.
- **`eines/genera_inventari.py`** (només lectura) → **`docs/COMPONENTS_I_VERSIONS.md`**:
  què porta l'app a dins i **quina versió** de cada component (Python, PyQt5,
  numpy, sounddevice, ffmpeg + les seves llibreries internes i de tercers,
  appimagetool, plugins Vamp i els seus commits), per poder vigilar avisos de
  seguretat. Es regenera amb `python3 eines/genera_inventari.py`.

- **Edició — desfer/refer complet**: `undo`/`redo` ara també cobreix **BPM, compàs,
  offset i loop A-B** (abans només acords i seccions).
- **Edita ▸ «Parteix la secció al cursor…»**: **partir** una secció en dues — l'única
  manera d'afegir-ne en un model **saturat** per la cobertura (regla #4). També al
  menú contextual de la secció.
- **Diàleg de dreceres COMPLET**: **Ajuda ▸ Dreceres de teclat** ara **dedueix totes**
  les dreceres dels menús reals (abans només en llistava 6).
- **Pont MCP — de 29 a 40 eines**: `ac_export_partitura` (+ paràmetre `partitura` a
  `ac_export_wav`), `ac_get_options`, `ac_set_key_detect` (tonalitat), `ac_set_metro`
  (metrònom), `ac_detect_downbeat`/`ac_mark_downbeat` (compàs 1),
  `ac_open_output_folder` i **multi-selecció** (`ac_select_clip`,
  `ac_toggle_selection`, `ac_clear_selection`, `ac_select_at_cursor`);
  **export asíncron** (`async:true` amb progrés a `ac_status`) i **autocomprovació
  amb `ffmpeg`**.
- **Robustesa**: **desat atòmic** dels CSV (`pipeline.escriu_atomic`: temporal +
  `fsync` + `os.replace` → mai queda un CSV truncat); **`faulthandler`** (traca dels
  crashes nadius → `crash_nadiu.log`, amb detecció del crash anterior);
  **avís de fitxer llarg** (>45 min, no bloquejant); **Ajuda ▸ Obre la carpeta del
  registre**.

### Corregit
- **Invariant de COBERTURA dels clips** (regla d'or): la **suma dels clips
  d'acords = la durada de la WAV** i la **suma dels clips d'estructura = la
  durada** — el 1r clip arrenca a **0** (s'hi afegeix una **capçalera «N»** si el
  detectat comença més enllà) i l'últim arriba a la **durada**. Abans, el 1r
  acord podia quedar desplaçat (p. ex. 0.17 s amb el snap) i l'última secció no
  arribava al final de la WAV. Ho garanteix `pipeline.normalitza_cobertura()`,
  aplicat en **carregar el visor** i en l'**export** (CSV/ABC + wavs), per als 2
  modes i amb o sense snap. També l'**export dels acords**: l'últim clip arriba a
  la durada (`acords_a_live.py` rep la durada).

- **Reanomenament de seccions d'estructura**: no es podia canviar el nom de cap
  secció que no fos la primera — l'editor reaplicava l'inici arrodonit a 2 decimals i
  la 2a «solapava» la 1a. Si l'inici no s'ha tocat, es conserva la **precisió interna**.
- **L'exportació perdia les edicions de seccions**: ara surt del **MODEL**
  (`exporta_total(acords=, seccions=)`), no del `segments.csv` cru.
- **Cobertura (regla d'or #4) en edició en viu**: s'aplica **després de cada mutació**
  (GUI **i** MCP) i es desen els CSV **normalitzats**.
- **Forat intern en moure una secció** i **topall superior de temps** (rebutjat amb
  error clar; reparat en carregar).
- **Xocs d'inici dins la resolució del CSV**: distància mínima + detecció; l'export mai
  escriu clips de durada 0. **Reanomenament sanejat** canònic
  (`pipeline.saneja_nom_acord`) als 4 camins.
- **Cursor vermell desalineat amb el LOOP A/B**: en fer **play** i en **activar el
  loop sonant** (cursor i timeline sincronitzats amb el so).
- **El BPM s'heretava en canviar de WAV**: `tria_wav()` ara torna el camp de BPM al
  valor per defecte (120.0) i ho registra; abans el tema nou sortia analitzat amb el
  tempo del tema anterior.
- **Avís «persistent» pel pont MCP**: `ac_status` i l'export retornen el darrer avís
  **UN SOL COP** i el netegen (`mcp_bridge._pren_avis`); abans un agent podia veure
  un avís vell com si fos nou.
## [0.6.2] — 2026-10-13 (BETA)

### Afegit
- **Botons nous a la barra principal**: **«Exporta WAV's»** (abans «Exporta»),
  **«Exporta partitura»** (genera el MusicXML i, si hi ha MuseScore, el PDF/MSCZ)
  i **«Zoom selecció»** (ajusta la vista del timeline a tota la selecció).
- **UI: queda clar que el PDF de la partitura depèn de MuseScore**: `statusTip`
  al menú i als botons, i el missatge de resultat diu què s'ha generat i, si no
  hi ha PDF, que cal **MuseScore** instal·lat.

### Corregit
- **AVÍS confús en arrencar l'app congelada** (`AVÍS: no trobo …/OLD/
  sonic-annotator`): l'autocomprovació d'inici buscava la **reserva llegat**
  `OLD/sonic-annotator`, que **no s'empaqueta mai** (l'app fa servir
  `vamp_host_local`). Ja no s'avisa d'aquell fitxer (es manté com a *fallback*
  intern a `pipeline.py`).

### Canviat
- **Barra d'eines en 2 files**: la fila **Treball** (Obre…, opcions de temps) i
  una fila nova **Accions** amb **Analitza · Exporta WAV's · Exporta partitura**.
- **Zoom a la selecció**: ara és un **botó d'icona** (`focus`, sense text) al
  visor, just al costat de **Zoom tot** (`maximize`).

## [0.6.1] — 2026-10-11 (BETA)

### Corregit
- **macOS: l'app petava en aturar/canviar** (`EXC_BAD_ACCESS` a
  `AudioToolbox`/`Pa_CloseStream`). El motor natiu podia tancar el **mateix
  stream** de PortAudio **dues vegades o des de dos fils alhora** (el fil
  d'alimentació en acabar crida `stdin.close()` i el d'UI crida `atura()` en
  aturar/seek) → disposar un component CoreAudio ja disposat. `MotorStream` ara
  té el teardown **idempotent i serialitzat** (flag `_tancat` + `threading.Lock`)
  i escriu en **trossos curts** perquè `atura` respongui de pressa.
- **MuseScore no es trobava a macOS ni a Windows** (`musescore_bin`): només
  mirava el `PATH` i AppImages de Linux, i usava `os.popen("command -v …")` (que
  a Windows **no existeix**) → el PDF/MSCZ no es generaven mai fora de Linux. Ara
  fa servir `shutil.which` + rutes de **macOS** (`/Applications/MuseScore*.app`)
  i **Windows** (`Program Files\MuseScore *`).

### Canviat
- **Tests per caçar bugs ABANS de compilar**: nova bateria
  `tests/test_audio_out.py` que cobreix els camins que **només s'executen a
  macOS/Windows** fent servir un **`sounddevice` FALS** + simulant el SO —
  obertura amb **fallback de host API**, escriptura per trossos, **teardown
  idempotent**, **concurrència** `close`/`atura` (el bug del crash) i la capa
  `plataforma`. I els **3 CI** ara corren **TOTA** la suite
  (`python -m unittest discover -s tests`), no només 2 mòduls.

## [0.6.0] — 2026-10-10 (BETA)

### Corregit
- **macOS: l'`.app` no arrencava** (`ModuleNotFoundError: No module named
  'PyQt5'`). El build de macOS no passava `--paths` a PyInstaller; com que el
  launcher fa `from app.main import …` **dins d'una funció** i l'entry és a
  `eines/`, PyInstaller **no resolia `app.main`** ni veia els seus imports, i
  **no empaquetava PyQt5** (ni el directori `platforms` de Qt). Ara s'hi afegeix
  **`--paths . --paths app`** i els **`--hidden-import`** (igual que el `.spec` de
  Windows, que ja ho tenia). Verificat: amb `--paths` PyInstaller recull
  `PyQt5/Qt5/plugins/platforms`.

### Afegit
- **Àudio a macOS i Windows: motor natiu** (`app/audio_out.py` + `sounddevice`).
  L'app reprodueix **dins el procés** amb **PortAudio**: **CoreAudio** a macOS i
  **WASAPI** a Windows (amb fallback DirectSound → MME → WDM-KS; ASIO només si
  l'usuari el té). Abans es buscava un reproductor extern (`ffplay`) que **mai
  no s'empaquetava** → a macOS sortia un missatge d'error **de Linux** i no
  sonava. **Linux no es toca** (segueix amb `paplay`/`aplay`). El missatge
  d'error ara és **segons el SO** (`plataforma.missatge_sense_audio()`).
- **Empaquetat de macOS: `.dmg` a més del `.zip`** (`build-macos.yml`): el
  workflow ara genera un **DMG** (`hdiutil`, HFS+ comprimit) amb l'`.app` + un
  enllaç a `/Applications`, el **munta i en verifica el contingut**, i el puja
  com a artefacte (i al Release). Ja no cal fabricar l'instal·lador a mà.
- **Smoke test de l'`.app` al CI** (`build-macos.yml` pas 6c): després de
  construir, el CI **executa l'app empaquetada** en mode headless
  (`QT_QPA_PLATFORM=offscreen`, `AUTO_CHORDS_SMOKE=1`) i comprova que **arrenca
  de debò** (dyld, plugins de Qt, dades) i que la finestra principal es crea.
- **Verificació exhaustiva del `minos` del bundle** (`build-macos.yml` pas 6b +
  eina nova `eines/verifica_minos_macos.py`): comprova el `minos` de **TOTS**
  els Mach-O de l'`.app` (Python, frameworks de Qt, `*.so` de numpy/sip,
  l'executable, els natius, ffmpeg…) — **només la fatia x86_64** — i **falla**
  si algun supera **10.13**. Funciona sense `otool` (parser propi).

### Canviat
- **Release `release.yml`**: ara **publica directament** (abans deixava un
  esborrany per aprovar a mà), **aprofita l'agregador `build-all`** (els builds
  *reusable* no queden registrats com a execucions pròpies) i **crea el tag**
  `v<versió>`. Idempotent: si el Release ja existeix, l'actualitza i el publica.
- `app/main.py`: nou mode **`AUTO_CHORDS_SMOKE=1`** (per al CI) que confirma al
  log la creació de la finestra principal i surt sol (codi 0).
- **Release**: els fitxers adjunts porten ara **versió + número de build** de
  l'execució verda d'origen — `AutoChords_<tag>_build<NN>_<so>.<ext>`
  (p. ex. `AutoChords_v0.5.2_build14_macos.dmg`) — igual que els artefactes
  (abans es renombraven a `<tag>-<so>` i es perdia el número de build).

## [0.5.2] — 2026-10-09 (BETA)

### Afegit
- **Fase D.2 — edició DAW-like al timeline**:
  - **Multi-selecció**: **Ctrl+clic** afegeix/treu un clip de la selecció;
    **Shift+clic** selecciona el rang entre l'àncora i el clip clicat (dins del
    mateix carril). Clic al fons = neteja la selecció.
  - **Eliminació de grup**: `Delete` esborra tota la selecció en **una sola
    operació d'undo**.
  - **Porta-retalls intern**: **`Ctrl+C`** (copiar), **`Ctrl+X`** (retallar) i
    **`Ctrl+V`** (enganxar al cursor). Els acords es guarden **relatius al clip
    més antic**, així l'enganxat preserva l'espaiat intern; l'operació **valida
    abans d'aplicar** (si xoca, no toca res) i és un **únic undo**.
  - **`Ctrl+D` de grup**: duplica tots els clips seleccionats d'una vegada.
  - **Moure el grup**: arrossegar un clip seleccionat mou **tota la selecció**.
  - **Indicador de MODE** al regle: badge fix a la dreta amb `120 BPM · 4/4`
    (mode tempo) o `Lliure` (mode sense BPM). `RulerLayer.mode_label()`.
  - **Loop A/B amb SNAP**: la selecció de loop al regle (arrossegar) i els
    botons A/B (`Ctrl+[`/`Ctrl+]`) ara **arrodoneixen a la graella**, com els
    clips. El cursor/playhead continua sent **lliure**.
- **GUI — «Quant a»**: el diàleg **Quant a Auto Chords** ara mostra la
  **versió** de l'app (`app.__version__`), sincronitzada amb `pyproject.toml`
  per un test.
- **Refactor intern**: `timeline.py` **partit** en 4 mòduls (`timeline.py` 1774 →
  **898** línies + `timeline_items.py` + `timeline_layers.py` + `timeline_base.py`),
  preparant la Fase D.2. Els símbols públics es re-exporten via `__all__`.
- **CI — workflow agregador** `build-all.yml`: executa els 3 builds (Linux +
  Windows + macOS) **en paral·lel** amb un sol clic. Els 3 workflows de build
  són ara *reusable* (`workflow_call`), sense perdre el disparador manual.
- **CI — Release (drecera manual) amb els 3 SO**: `release.yml` ara és
  **manual** i **no compila**: agafa els **últims artefactes verds** de
  Linux/Windows/macOS de GitHub Actions i crea l'esborrany amb **els 3 paquets**
  adjunts (abans només l'AppImage de Linux, i s'activava amb el tag).
- **Grid, regle i snap UNIFICATS i adaptatius al zoom** (estil DAW): una sola
  font (`grid_plan`) amb **llindars en píxels** (`MIN_LINE_PX`/`MIN_LABEL_PX`)
  decideix les línies del grid, les del regle i el **snap** (que ara **segueix
  el grid**). El regle mostra **`m:ss`** en mode lliure (abans `X.Xs`) i
  `compàs.temps` en mode tempo, amb el format i la densitat segons el zoom.
- **Regle — etiquetes més denses**: el nivell de les etiquetes ara és el **més
  fi que hi cap** (abans era el més gruixut visible) → surten **cada 2-4 línies
  de graella** segons el zoom (abans 4-60), sense solapar-se.

### Arreglat
- **Línies del grid pintades de negre**: `grid_levels()` retornava els *strings*
  literals `"theme.TL_GRID_*"` i els consumidors feien `QColor(string)` → color
  **invàlid**. Ara retorna els colors **reals** de `theme`.
- **Zoom de la roda centrat al cursor vermell**: quan no hi ha selecció, el
  zoom ja se centra al **playhead** (cursor vermell) en lloc del punter del
  ratolí. El comportament amb clips seleccionats es manté coherent.
- **Compàs manual `x/x`**: el camp de compàs accepta `4`, `4/4`, `3/4`, `6/8`,
  etc., i el denominador es propaga al regle i a la graella sense trencar la
  lògica de snap/offset.
- **Labels d’inici de compàs destacades**: `1.1`, `2.1`, `3.1`... apareixen
  ressaltats en negreta i amb color de mesura per emular millor l’estil DAW.

### Proves
- **231 tests** · OK (1 skip) — +21 respecte de la v0.5.1 (multi-selecció,
  `Ctrl+C/V/X`, `Ctrl+D` i **moure** el grup, indicador de mode, **loop A/B amb
  snap** i colors del grid).
- **CI multi-SO re-verificat** amb tot el codi de D.2: **Linux AppImage #8**,
  **Windows #14** i **macOS #8** (amb pas de tests) — tots **VERDS**.

## [0.5.1] — 2026-10-08 (BETA)

### Afegit
- **Multi-SO (Linux + Windows + macOS): els 3 builds del CI VERDS** —
  abstracció de plataforma (`app/plataforma.py`), host i plugins **multi-SO**
  (`eines/compila_vamp_{host,plugins}.sh`, dispatch per SO), entry de
  PyInstaller compartida (`eines/launcher_pyinstaller.py`) i **3 workflows de
  CI** (`build-appimage.yml`, `build-windows.yml`, `build-macos.yml`). El host
  i els plugins es compilen **al runner** de cada SO; **`qm-vamp-plugins` es
  compila des de font** a Windows i macOS (els binaris oficials no carregaven
  o no es podien baixar). Artefactes: **Linux AppImage**, **Windows ZIP x64** i
  **macOS ZIP (10.13)**. Estat complet: **`docs/ESTAT_MULTI_SO.md`**.
- **Autoportabilitat real**: l'AppImage ara **empaqueta les llibreries natives**
  que necessita l'host Vamp — `libvamp-hostsdk`, `libsndfile` i els còdecs
  (`libFLAC`, `libogg`, `libvorbis`, `libvorbisenc`, `libopus`, `libmpg123`,
  `libmp3lame`) — a **`portable/lib/`**, i el llançador les prioritza via
  `LD_LIBRARY_PATH`. Nou **`eines/libreries_natives.sh`**, que les resol del
  mateix sistema que compila → **0 descàrregues extra** i glibc coherent.
  Al SO host només hi queden **`glibc` + `libstdc++/libgcc`** (universals).
  **Verificat** amb les 9 llibreries del sistema amagades dins un *namespace*
  de muntatge: acords + estructura OK.

### Canviat
- **Llançadors unificats**: `AUTO_CHORDS.desktop` ara executa **`AUTO_CHORDS.sh`**
  (que tria l'intèrpret: `portable/` → `.venv` → `python3`); retirat `launcher.sh`.
- **Arxiu local `OLD/`** (gitignorat): s'hi mou el que **no és necessari** però
  es vol conservar — `sonic-annotator` (reserva; `pipeline.SONIC` hi apunta) i
  l'estat local `opcions_detecta.json`. `concatena.py` i `empaqueta_portable.sh`
  l'exclouen.
- **Texts obsolets** trets («Segmentino» → `qm-segmenter`) a `app/main.py`,
  `app/dialegs.py`, `app/pipeline.py` i `wav_a_wavs.py`; `dev_reload.py` amb
  import lazy de `watchdog`; retirat `instal·la_vm_debian.sh` (la VM ja no cal).

### Arreglat
- **CI macOS**: `build-macos.yml` ara **corre la suite de tests**
  (`tests.test_pipeline_export` + `tests.test_partitura`, amb anotació `::error::`);
  era l'únic dels 3 workflows que no validava els tests.
- **Deute tècnic (Pas 3 — excepcions)**: revisats els `except Exception` de
  **tot el projecte** (`app/visor.py` ×24, `app/main.py` ×12, i
  `app/partitura.py`, `app/plataforma.py`, `app/pipeline.py`, `app/tempo.py`,
  `dev_reload.py`, `wav_a_wavs.py`) **sense canvi de comportament**;
  documentada la política a cada classe; anotats els fallbacks silenciosos de
  codi calent (timer de hover, fil d'àudio); la lectura de WAV fallida (fallback
  esperat) ara va al **log de fitxer** a nivell debug.
- **Deute tècnic (Pas 2 — imports/variables)**: `pyflakes` net a `app/` i `eines/`;
  trets els imports/variables morts (`os`, `postproc`, `atexit`, `signal`,
  `QCloseEvent`, `QFormLayout`, `QGroupBox`, `QCursor`, `QPainterPath`, `QFont`,
  `QPixmap`, `wave`) i f-strings sense placeholders; `QCloseEvent` ja no s'exporta
  des d'`app.visor` (el test l'importa directament de `PyQt5.QtGui`).
- **CI (`.github/workflows/`)**: el job d'AppImage fallava amb
  `E: Unable to locate package libvamp-hostsdk-dev` — aquest paquet **no
  existeix** a Ubuntu; el correcte és **`vamp-plugin-sdk`**. Corregit a
  `build-appimage.yml` **i** a `release.yml` (aquest s'activa amb els tags i
  hauria fallat igual).
- **CI**: `actions/checkout@v4` → **`@v5`** i `actions/upload-artifact@v4` →
  **`@v6`**, que són les que corren en **Node 24** (la v4 donava l'avís de
  deprecació de Node 20).
- `.gitignore`: s'ignoren `LOGS GITHUB ACTIONS/` i `logs_*/`.

### Documentació
- **Deute tècnic (Pas 4 — concatenat)**: `concatena.py` inclou **`tests/`**
  (47 fitxers · ~594 KB) perquè la revisió externa vegi el comportament esperat.
- **Deute tècnic (Pas 1 — docs)**: comandament del visor corregit a
  **`python -m app.visor`** (el `python app/visor.py` directe fallava amb
  imports relatius); recompte de tests actualitzat a **210 · OK (1 skip)**;
  `ROADMAP` **Fase D → D.1 marcada com a feta**; neteja d'espais al README.
- **Revisió 1 a 1 de tota la documentació a l'estat v0.5.1 (BETA)**: README,
  ROADMAP, CHANGELOG, DEVELOPING, `docs/ESQUEMA_UI.{md,html,svg}`,
  `docs/ESTAT_MULTI_SO`, `docs/PORTABILITAT*`, `docs/PLANIFICACIO_MACOS`,
  `docs/QM_VAMP`… (Windows/macOS verds; trets aubio/segmentino; `v0.5.0`→`v0.5.1`).
- `README.md`: **URL del repositori**, com descarregar l'AppImage i taula de
  requisits mínims actualitzada (llibreries natives incloses); recompte de
  tests corregit (173).
- `docs/PORTABILITAT.md`: nova **secció 0 «Estat actual: autoportable»** amb la
  llista exacta de llibreries empaquetades i el mínim del SO; l'anàlisi inicial
  queda marcada com a històrica.
- `LLICENCIES_TERCERS.md`: afegides les llicències de les **7 llibreries noves**
  (BSD-3 dels còdecs Xiph; LGPL-2.1/2.0 de mpg123 i mp3lame) + nota de
  relinkatge.

## [0.5.0] — 2026-10-07

### Arreglat
- **Revisió 1 a 1 de tota la documentació**: tretes/actualitzades les restes
  de l'etapa anterior (Segmentino, aubio, pyqtgraph, «Processa»/«Finalitza i
  publica», `v0.4.0`). Actualitzats: `ROADMAP` (estat v0.5.0 + novetats),
  `DEVELOPING` (matriu + mòduls + menús), `docs/ESQUEMA_UI.md` (v0.5.0,
  amplada mínima 1240, diagrama de 2 files amb **icones**, `amb_est`=QAction),
  `docs/ESQUEMA_UI.html`/`.svg` (v0.5.0, ◎ Detecta, fora «Inclou estructura»
  i l'aubio), `AUTODETECCIO_OPCIONS` (exemple amb el **host propi**, ja no els
  directors retirats), `PLAY`, `REFERENCIA_PILES`. Les mencions a CHANGELOG i
  `AUBIO_TEMPO` es conserven (història).

### Afegit
- **Secció «Autoria» al README** (i cua de les notes del Release): autor
  **Pëp** + **reconeixement explícit als agents d'IA** que hi han treballat
  (opencode amb models com **DeepSeek**, Gemini, Devin, Chatbox, Spark), amb
  una nota legal (la titularitat és de l'autor humà).

### Afegit (anterior)
- **CI a prova d'errors + logs de debug**:
  - **Diagnòstic** al inici de cada workflow (OS, glibc, g++, Python, disc, RAM).
  - Si **alguna cosa falla**: un pas **`if: failure()`** imprimeix pistes (disc,
    fitxers, logs) i un altre **puja els logs** com a artefacte `debug-logs-<N>`.
  - Nota al capdamunt dels workflows sobre el mode **`ACTIONS_STEP_DEBUG`**.
  - **Robustesa dels scripts**: `curl` del CPython i de l'ffmpeg ara amb **`-f`**
    (fallen si hi ha error HTTP, abans un 404 passava com a èxit); el
    `empaqueta_portable.sh` ja **no s'empassa** els errors de còpia.

### Arreglat
- **CI robust**: els 3 tests de `EscriuTtlTests` depenien de `sonic-annotator`
  (que vol Qt6/ICU/glib). Ara es fan **SKIP** (`skipUnless`) si no es pot
  executar, i els workflows **intenten** instal·lar-ne les llibreries
  (`libqt6core6 libqt6xml6 libqt6network6 libglib2.0-0`, best-effort). Així la
  ci no falla mai per aquest motiu. (El pipeline real usa l'host propi;
  el sonic-annotator és només la reserva.)
- **El nostre AppImage NO necessita `libfuse2`**: el runtime incrustat és el
  **modern estàtic** (`type2-runtime`, enllaçat amb musl + libfuse +
  squashfuse a dins; verificat amb `ldd`: «no és un executable dinàmic»).
  Només cal el suport **FUSE del nucli** (estàndard). L'avís clàssic
  d'instal·lar `libfuse2` és per a AppImages amb el runtime **antic**.
  Docs corregits (README, `eines/notes_release.py`); i afegides al
  `LLICENCIES_TERCERS.md` les llicències del runtime (libfuse LGPL-2.1,
  squashfuse BSD-2, musl MIT).

### Afegit
- **Release automàtic de GitHub** en crear un tag `v*`
  (`.github/workflows/release.yml`): construeix l'AppImage i crea un
  **Release esborrany** amb títol `AUTO CHORDS v<versió>` i el cos **en
  català** (generat de la secció del CHANGELOG amb `eines/notes_release.py`),
  amb l'AppImage adjunta. El publiques tu. (El build manual
  `build-appimage.yml` segueix igual: només `workflow_dispatch`.)

### Canviat
- **`.gitignore` blindat** (sense esborrar res del disc): afegides regles
  preventives per a `temp/`, `.pytest_cache/`, `.ruff_cache/`,
  `.mypy_cache/`, `.venv*/`, `*.orig`, `*.rej` i `*.AppImage.zsync`.
  Cobertura verificada: **0 fitxers al disc que no estiguin ni seguits ni
  ignorats** (el git puja 4,9 MB; el `portable/`, `.venv/` i `.deps/`
  es queden al PC).

### Afegit
- **Preparat per compilar un AppImage (i a GitHub Actions)**:
  - **Icona d'aplicació** (no en teníem): `eines/crea_icona.py` la dibuixa amb
    Qt (quadrat fosc + forma d'ona de Lucide en blau, coherent amb el tema) a
    `icona/` en 8 mides.
  - **`eines/crea_appimage.sh`**: munta l'AppDir (AppRun + `.desktop` +
    `auto-chords.png` + el paquet portable) i construeix l'AppImage amb
    `appimagetool`. **Provat: funciona** (l'app arrenca des de l'AppImage i el
    codi és idèntic al del projecte) i fa **160 MB** (squashfs, comprimit
    dels 532).
  - **`.github/workflows/build-appimage.yml`** (manual, com al GEP): deps →
    icones → **compila l'host Vamp** → portable → verificació → tests →
    AppImage → `upload-artifact`. `runs-on: ubuntu-22.04` (marca la glibc
    mínima: aquí es compila `vamp_host_local`; la resta de binaris són antics:
    Python 2.17, PyQt5 2.17, numpy 2.14, ffmpeg estàtic).

### Canviat

### Afegit
- **Desfer/refer surten a la caixa d'informació**: en fer `Ctrl+Z`/`Ctrl+Y` es
  mostra **què** s'ha desfet/refer, descrit automàticament comparant els dos
  estats (p. ex. «⟲ DESFER: moure l'acord «Am» (5.00s → 4.00s)»,
  «reanomenar l'acord…», «afegir/eliminar un acord/secció»). Nou
  `Visor._descriu_canvi()` + senyal `infoMissatge`; el missatge es veu **4 s**
  i no el trepitja el ratolí. **4 tests nous** (`UndoInfoTests`).

### Arreglat
- **Senyal `playStateChanged` no connectat en carregar el visor**: la icona
  ▶/⏸ **no s'actualitzava** en donar a play (la connexió havia anat a parar
  per error a `_tap_tempo`). Ara `_carrega_visor` connecta `playStateChanged`
  **i** `infoMissatge` (i `_tap_tempo` queda net).✨

### Afegit
- **La caixa d'informació explica el «ratolí intel·ligent» del visor**: abans
  només mostrava el tooltip del *giny* (i el timeline és un sol giny), així
  que sobre el visor no deia res. Ara `TimelineView.info_zona()` retorna
  l'acció segons on és el ratolí: **regle** (loop/saltar), **ona** (cursor/
  pan/zoom), **cos d'un clip** (moure/editar/menú), **vores** (moure inici/
  final) — amb el nom de l'acord o secció. La info box ho mostra en passar-hi
  el ratolí. **3 tests nous** (`InfoBoxTests`, 169 en total).

### Canviat
- **ICONES PROFESSIONALS (Lucide, ISC) en comptes d'emoji**: l'app ja no
  sembla de joguina. Nou `app/icones.py` (carrega els SVG de `icones/`,
  els **recoloreix** via QtSvg) i `eines/baixa_icones.sh` (21 icones, 88 KB).
  Substituïts: 🎯→`target`, 📍→`map-pin`, 🧭→`compass`, 🥁→`metronome`,
  🔁→`repeat-2`, 🔇→`volume-x`, 🔍±→`zoom-in/out`, ▶→`play`, ⏸→`pause`,
  ⏹→`square`, −10s/+10s→`rewind`/`fast-forward`, A⟨/⟩B→`arrow-*-to-line`,
  Tot→`maximize`, 🎵/🎼→`music`/`piano`. `×2`/`÷2` eixamplats perquè no es
  talli el text. Amplada mínima 1240. **166 tests.**

### Arreglat
- **El paquet portable ja no porta cap `.gitignore`** (era una còpia per
  accident: `rsync` no l'excloïa i, a més, `--exclude` *protegeix* els
  fitxers ja existents al destí i no els esborrava). `empaqueta_portable.sh`
  ara exclou `.gitignore`/`.git*` i, per si queden d'una build anterior, els
  treu explícitament. El paquet **no és un repo** i no necessita res de git.

### Canviat
- **Barres d'eines: 2 files amb `Analitza`/`Exporta` a la fila 1** (com a
  l'origen): **fila 1** = `Obre…` + temps/BPM/offset + **Analitza** +
  **Exporta** (1197 px); **fila 2** = **transport** (play/loop/zoom/mute/
  metrònom, 703 px). Amplada mínima de finestra **1210** perquè res no es
  talli (`Inclou estructura` és a `Analitza ▸ Inclou estructura`).

### Canviat
- **`Inclou estructura` surt de la barra d'eines** (era un `QCheckBox`) i passa
  a ser una **acció commutable al menú Analitza** (per defecte marcada). La
  **funció és la mateixa**; només canvia d'ubicació. La barra «Accions» queda
  amb `Analitza` + `Exporta` i comparteix fila amb el transport
  (**2 files**: opcions / accions+transport).

### Canviat
- **Barres d'eines: 3 files → 2**. La barra «Accions» (`Inclou estructura` +
  `Analitza` + `Exporta`) i la de **Transport** ara **comparteixen fila**
  (314 + 703 = 1029 px, caben junts). Així: fila 1 = opcions, fila 2 =
  accions + transport, i **tot visible a ≥1040 px**.

### Arreglat
- **Barres d'eines en finestres estretes** (<1400 px): la barra 1 demanava
  **1462 px** i, com que `QToolBar` **no crea cap botó d'extensió** aquí, els
  botons de la dreta (**Analitza/Exporta**) quedaven **inaccessibles**.
  Solució: **barra «Accions» pròpia** (fila nova) per a `Inclou estructura` +
  `Analitza` + `Exporta` (sempre visibles), barra 1 compactada (sense
  «Temps:», «Lliure» en comptes de «Lliure (hh:mm:ss)») → **1021 px**, i
  **amplada mínima de finestra 1040**. Verificat: a 1040-1400 px tot hi cap.
- **La suite de tests ja no deixa tempdirs a `/tmp`**: intercepta
  `tempfile.mkdtemp` i els esborra tots a `tearDownModule` (abans s'acumulaven
  centenars per execució).

Tongada de **portabilitat** (5 fases) + retirada de Segmentino/aubio +
`Analitza`/`Exporta` ben separats. **166 tests.**

### Arreglat
- **`Analitza` ja NO genera les carpetes de wavs** (es feien DUES vegades:
  també a l'`Exporta`). Restaura el disseny acordat: les `wavs_acords/` i
  `wavs_estructura/` són **l'últim pas**, i es generen **només amb
  `Exporta`** (`pipeline.exporta_total`, que també fa els locators i la
  guia). `Analitza` (la classe `Feina`) ara només crea **`acords.csv`**,
  **`segments.csv`** i **`estructura_ABC.csv`**. Verificat: després
  d'analitzar només hi ha els 3 CSVs; després d'exportar hi ha els locators,
  la guia i les dues carpetes de wavs. **166 tests.**

### Afegit
- **Fase 5 de portabilitat — empaquetat**: `eines/empaqueta_portable.sh`
  munta `AUTO_CHORDS_PORTABLE/` (codi + plugins + host + Python portable +
  ffmpeg; exclou `.deps/`, `.venv/`, `.git/`, `temp/`, brossa).
  **Verificat en brut**: copiat a `/tmp` i executat des d'allà → els 166
  tests passen, l'app carrega, el pipeline complet funciona (acords,
  estructura, compàs 1 = 9,49 s, BPM) i l'import d'mp3 amb el ffmpeg del
  paquet. **Mida final ~526 MB.**

### Canviat

### Canviat
- **Fase 4 de portabilitat — àudio/requisits**: si no hi ha cap reproductor
  (`paplay`/`aplay`/`ffplay`), l'app **avisa clarament** (cal PipeWire o
  PulseAudio per escoltar) i **la resta funciona igual**; abans petava en
  engegar el play. Documentat a `DEVELOPING.md`.

### Afegit
- **Fase 3 de portabilitat — `ffmpeg` estàtic embegut**: `portable/bin/ffmpeg`
  (build estàtic de johnvansickle, 80 MB, corre al Q9400). `app/ffmpeg.py`
  **prefereix el local** i cau al del sistema. Només s'embega `ffmpeg`:
  **`ffprobe` no s'usa enlloc** (`ffmpeg.info()` no té cap crida) → estalvi de
  80 MB. Verificat: conversió d'mp3 → WAV PCM16 amb el ffmpeg portable.
  `eines/crea_portable.sh` actualitzat.

### Afegit
- **Fase 2 de portabilitat — CPython portable**: `python-build-standalone`
  3.12.15 (build **genèric x86_64**, sense AVX; el `_v2` demanaria SSE4.2)
  a `portable/python/` amb PyQt5 + numpy<2. `AUTO_CHORDS.sh` **prefereix el
  Python portable** (i cau al `.venv` o al sistema). Verificat: **els 166
  tests passen amb el Python portable** i l'app carrega. `portable/` és al
  `.gitignore` (es regenera). Trets `pyqtgraph` (no s'usava) i `pip`.

### Afegit
- **Fase 1 de portabilitat — host Vamp propi** (`eines/vamp_host.cpp` →
  `vamp_host_local`, 48 KB): substitueix `sonic-annotator` (que arrossegava
  ~70 llibreries: Qt6/ICU/glib/gnutls). Només depèn de libc/libstdc++ +
  libvamp-hostsdk + libsndfile. Compilat amb `-msse -msse2` (sense AVX).
  `eines/compila_vamp_host.sh`. Resultats idèntics al sonic-annotator per al
  Chordino/qm-tempotracker/qm-onsetdetector. `pipeline.usa_host()` +
  `executa_transform` (el sonic-annotator queda de reserva). Vegeu
  `docs/QM_VAMP.md` i `docs/PORTABILITAT.md`.

### Canviat
- **Retirats el Segmentino i l'aubio**: l'**estructura** la fa només el
  **`qm-segmenter`** (l'única cosa que hi havia al diàleg) i el **BPM** el
  fan el `tempo.py` / `qm-tempotracker` / **consens**. Motius: el Segmentino
  fallava amb el nostre host Vamp i l'aubio donava BPM erronis (139,7 pel
  101). El projecte passa a dependre de **2 conjunts de plugins**:
  `nnls-chroma` (Chordino) i `qm-vamp-plugins`. Combo de motor d'estructura
  tret del diàleg; opcions `aubio`/`segmentino` eliminades. **166 tests.**

## [0.4.0] — 2026-10-07

Segona tongada del dia: **coherència del play** (cache de mono, volum/mute en
viu, latència, no tallar la cua), **BPM** (prior de plateau per l'ambigüitat
d'octava + motors triables), **plugins Queen Mary compilats** (qm-tempotracker,
qm-barbeattracker, qm-segmenter, qm-keydetector), **compàs 1 automàtic** i
**qm-segmenter com a motor d'estructura per defecte**. 165 tests.

### Canviat
- **L'estructura ara la fa el `qm-segmenter` per defecte** (abans Segmentino).
  Es va triar perquè **detecta les repeticions** (`A … A … A`) de manera
  explícita; dona una estructura més fina (~13 trossos al tema de 101 vs 7
  del Segmentino). Es pot ajustar amb la **durada mínima** (amb 15 s dona 7)
  o tornar al Segmentino des del diàleg. `extract_segments` i el diàleg
  passen a tenir `qm` com a defecte; el combo el llista primer.

### Afegit
- **Motor de BPM triable i motor d'estructura** (parts 2 i 4/3 amb el
  Queen Mary), al diàleg d'opcions:
  - **BPM**: `nostre` (tempo.py, per defecte) · `qm` (qm-tempotracker) ·
    `aubio` (l'antic) · **`consens`** (nostre + qm; si coincideixen — mateix
    tempo o doble/meitat dins d'un 4 % — ho diu com a confiança alta; si no,
    guanya el nostre i avisa).
    `pipeline.detecta_bpm(..., motor=)` i `detecta_bpm_qm()`.
  - **Estructura**: `segmentino` (per defecte) o `qm` (**qm-segmenter**, que
    a més troba les repeticions A…A). Mateix format de sortida, així que
    `fer_abc` funciona igual. `extract_segments(..., motor=)`.
  Res de la barra 1 s'ha tret. **3 tests nous**.

### Afegit (anterior)
- **Compàs 1 automàtic** (part 1/3 de les millores amb el Queen Mary): botó
  **`🧭`** a la barra de temps (al costat del 📍) + acció **Analitza ▸
  «Detecta el compàs 1 automàticament»**. Usa `qm-onsetdetector` (l'inici
  real de la música) + `qm-barbeattracker` (downbeats) per posar l'offset
  sol. **Verificat**: el tema de 101 (9,5 s de silenci) → **9,49 s** exacte.
  El botó 📍 manual es manté. `pipeline.detecta_compas1()`. **3 tests nous**
  (`Compas1Tests`).

### Afegit (anterior)
- **`qm-vamp-plugins` (Queen Mary) compilats i integrats** (`qm-vamp-plugins-linux64-local/`):
  els plugins Vamp que fan servir **Audacity, Mixxx i Sonic Visualiser**
  (`qm-tempotracker`, `qm-barbeattracker`, `qm-keydetector`, `qm-segmenter`…).
  No són als repos d'Ubuntu, així que s'han **compilat del codi font** (GitHub
  `c4dm/qm-vamp-plugins` + `qm-dsp` + `vamp-plugin-sdk`) amb
  **`-msse -msse2`** (⚠️ **sense AVX**, verificat pel Q9400). Afegits a
  `pipeline.VAMP_DIRS`. Comparativa amb 11 temes reals a `docs/QM_VAMP.md`:
  pel **tempo** el `tempo.py` propi fa **5/5** i el qm **4/5** → es manté el
  nostre de principal; el qm queda com a motor alternatiu + **beats/bars**
  (els downbeats permetrien posar el **compàs 1 sol**).

### Afegit (anterior)
- **`eines/explica_bpm.py`**: genera un gràfic (PNG) que explica com es
  detecta el BPM (envolupant → autocorrelació → puntuació comb → prior), amb
  el cas real. Útil per documentar i per depurar casos difícils.

### Arreglat
- **BPM: ambigüitat d'octava/subdivisió** (casos reals). El biaix pla antic
  («+15 % a 90–180») **no** la resolia: amb corxera/8ens forts guanyava el
  doble/subdivisió (Otis Redding → 179,8 en comptes de **103,5**; Chemical
  Brothers → 66 en comptes de **132**). Nou **prior de plateau**
  (`tempo._prior`): pes **1,0 dins 85–150 BPM** i caiguda gaussiana en log₂
  (**σ=0,5**) fora. Paràmetres triats amb **11 temes reals**; verificat:
  101 · 138 · **70** · 117,8 · 107 · **103,5** (Otis) · **132** (Chemical) ·
  **87** (Jamiroquai) — tots correctes. El «rang preferit» del diàleg és
  aquest plateau. **4 tests nous** (`TempoOctavaTests`) amb clic-tracks
  sintètics que reprodueixen els casos.

### Arreglat (anterior)
- **Coherència del play (2/2)**:
  - **Latència baixa** del reproductor (`paplay --latency-msec=100`): el so
    arrenca abans i el **cursor quadra millor amb el que se sent**.
  - **No es talla la cua**: al final ja no s'atura pel rellotge de paret
    (`t >= durada`); s'espera l'**EOF del reproductor** (que va per darrere
    per la latència). Només es para si el rellotge se'n va >15 s (encallat).
  - **Avisa si el reproductor mor per error** (abans s'aturava en silenci).
  - **Volum/mute EN VIU**: el guany l'aplica el **fil d'alimentació** tros a
    tros (llegint `self.vol`/`self.mut`), així **canviar-los no reinicia** el
    reproductor ni fa cap punxada. `_mono_bytes()` ara és el mono pur (cacat
    un sol cop per fitxer). **5 tests nous**.
- **Coherència del play (1/2)**:
  - **`_mono_bytes()` cachejat**: convertir l'estereo a mono + copiar trigava
    **~450 ms** en temes llargs i es cridava a cada play/seek/reinici
    (congelava la GUI). Ara es guarda i només es recalcula si canvien
    mute/volum → de **468 ms a 0,03 ms**.
  - **S'atura el reproductor** abans d'operacions pesades: **aplicar els
    plugins** (`Analitza`, 🎯 `Detecta`) i **recarregar/redibuixar el visor**
    (`_carrega_visor`). Nou helper `_atura_si_sona(motiu)`. **4 tests nous**
    (`PlayCoherenciaTests`).

## [0.3.0] — 2026-10-07

Sessió gran: tap tempo, botó 📍, franja Editor, menús, paleta de botons,
**diàleg d'opcions d'autodetecció** (BPM/acords/estructura amb els paràmetres
reals dels plugins Vamp + post-processat), **import d'altres formats amb
ffmpeg** i botons **×2/÷2** del BPM. 148 tests.

### Afegit
- **Botons `×2` / `÷2` del BPM** a la barra de temps (al costat del camp):
  doblen o fan la meitat del BPM d'un clic, útil quan la detecció agafa el
  doble o la meitat. Rangs ampliats a **30–400** (abans 40–240) perquè hi
  càpiguen els dobles de temes ràpids; es propaga al regle + metrònom.
  **4 tests nous** (`BpmDoblaTests`).

### Afegit
- **Import d'altres formats d'àudio via ffmpeg** (`app/ffmpeg.py`): `Obre…`
  ara accepta **wav, mp3, aif/aiff, flac, m4a, ogg, opus, wma…** i, si el
  fitxer no és **WAV PCM 16 bits**, el **converteix automàticament** amb
  `ffmpeg -vn -c:a pcm_s16le` (manté mostreig i canals). El WAV de treball es
  deixa al costat de l'original com **`<nom>_convertit.wav`** i es reutilitza
  si ja és més nou. El títol indica «convertit de <original>». Sense
  dependències noves (ffmpeg ja és al sistema). **6 tests nous**
  (`FfmpegTests`), amb conversió real d'mp3/aiff/flac.

### Arreglat
- Les etiquetes del diàleg mostren el nom català + l'`id` petit
  (abans el `<small>` sortia literal).

### Afegit
- **Neteja posterior dels acords** (post-processat, `app/postproc.py`), amb
  controls nous a la pestanya **Acords** del dialeg:
  - **Treure el baix** (`A/E` → `A`), **Reduir a l'acord bàsic**
    (`Cmaj7` → `C`, `Em6` → `Em`, `Edim7` → `Edim`), **Fusionar iguals**,
    **Durada mínima** (treu acords massa curts) i **Encaixar a la graella**
    (snap al beat/compàs, amb les subdivisions triables).
  Funcions pures i testeables; s'apliquen al CSV després del Chordino.
  **7 tests nous** (`PostprocTests`).

### Canviat
- **Opcions del Chordino traduïdes al català** al diàleg d'autodetecció, amb
  una **ajuda** per a cada paràmetre (tooltip) i els valors traduïts
  («afinació global/local»). Completesa **verificada**: el Chordino té
  exactament aquests **6** paràmetres (cap més) i el Segmentino **cap**; els
  paràmetres d'aubio només són dels seus plugins (que no fem servir per BPM).

### Afegit
- **Diàleg d'opcions d'autodetecció** (fases 3+4 de `AUTODETECCIO_OPCIONS.md`):
  en clicar **`🎯 Detecta`** (obre a la pestanya **BPM**) o **`Analitza`**
  (obre a **Acords**) surt un diàleg amb 3 pestanyes:
  - **BPM**: rang de cerca (min/max) i rang preferit.
  - **Acords**: els **6 paràmetres del Chordino**, construïts
    **dinàmicament** des del descriptor `.n3` (checkbox pels 0/1, combo pels
    que tenen noms, spinbox pels numèrics).
  - **Estructura**: durada mínima de secció + fusionar trossos iguals
    (`pipeline.filtra_seccions`, post-processat del Segmentino).
  Botó **«Restaura per defecte»**; les opcions es **recorden**
  (`opcions_detecta.json`, gitignored). Nous `app/dialegs.py`,
  `pipeline.filtra_seccions`, `fer_abc(durada_min=, fusiona_iguals=)` i
  `detecta_bpm(bpm_min=, bpm_max=, preferit=)`. **10 tests nous**.

### Afegit (anterior)
- **Base d'opcions de l'autodetecció** (fases 1+2 de `docs/AUTODETECCIO_OPCIONS.md`):
  - `app/vamp_params.py`: llegeix els **paràmetres ajustables** dels plugins
    Vamp des dels seus descriptors **`.n3`** (id, títol, rang, pas, defecte i
    noms de valor). Chordino: 6 paràmetres; Segmentino: cap.
  - `app/pipeline.py`: `extract_chords(..., params=)` i `extract_segments(..., params=)`
    i `escriu_ttl()` → **reconstrueix el transform `.ttl`** amb tots els
    paràmetres i el passa amb **`sonic-annotator -t`** (en comptes de `-d`).
    ⚠️ Clau: `sonic-annotator -s` **no llista tots els paràmetres** (no hi surt
    `useHMM`), per això el TTL es reconstrueix i no es pedaça.
  - Verificat amb execució real: `useHMM=0, rollon=3` → **57 acords** vs
    **54** del defecte. **8 tests nous** (`VampParamsTests`, `EscriuTtlTests`).

### Canviat
- **Botó de reproducció**: `▶ Escolta` → **botó d'icona** que canvia sol
  (**`▶`** aturat / **`⏸`** sonant), com als DAWs, sense text. El visor emet
  `playStateChanged(bool)` i la barra de transport s'hi sincronitza.
- **Botons commutables amb estat visible**: la base de **tots** els botons
  passa a l'estil **«Obre…» (gris)**; els botons amb estat (**🔁 loop**, els
  de **mode**) s'encenen en **BLAU**, i el **🔇 mute** i el **🥁 metrònom**
  en **GROC** (`#ffd166`). L'estil de la finestra principal **no tenia cap
  regla `:checked`**, per això mai no es veien actius. `Analitza` es manté
  destacat en blanc (`#principal`).
  **5 tests nous** (`BotoOnOffTests`), inclòs un que comprova el color real
  del píxel entre apagat i encès.

### Arreglat
- **Selecció de les llistes**: clicar una fila d'acords o de seccions ara la
  deixa **ressaltada** (abans el carril sí que quedava seleccionat però la
  llista no). Causa: `ves_a()` → `_actualitza_temps()` repoblava les llistes
  amb `clear()` i en perdia la selecció. Ara `_omple_llista_ac` i
  `_actualitza_llista_abc` **preserven la fila actual** en repoblar, així que
  la selecció també sobreviu als canvis de BPM/offset/compàs. **3 tests nous**
  (`LlistaSeleccioTests`).

### Afegit
- **Botó `📍` a l'Offset**: llegeix la posició del **cursor vermell** i hi posa
  el **compàs 1** (offset) a l'instant, actualitzant els dos camps
  (segons i ≈ C.B) i la graella. És la versió *botó* de
  `Analitza ▸ Marca el compàs 1 aquí`. **1 test nou**
  (`OffsetBotoCursorTests`).

### Afegit (anterior)
- **TAP TEMPO** (botó `TAP` a la barra de temps + tecla **`T`**): per fixar
  el BPM marcant el pols mentre sona la cançó. Segueix el **patró estàndard
  dels DAWs** (investigat): guarda els instants dels últims taps, **mitjana
  dels intervals** → `60/∅`; **reset als 2 s** sense tocar (LMMS); i
  **descarta intervals fora de 30-300 BPM** (Max/Dobrian) per ignorar
  dobles-taps i gaps llargs. Propaga el BPM al **regle i al metrònom**
  **sense reengegar l'àudio** en curs. El botó mostra `TAP (n) BPM`.
  **5 tests nous** (`TapTempoTests`).

### Arreglat
- **Seleccionar des de les LLISTES no actualitzava la franja Editor**:
  `TimelineView.select_clip()` no emetia `clipSelected` (només ho feia
  `_seek_to`, el clic al propi clip). Ara `select_clip()` **sí que l'emet**
  (i `_seek_to` no el duplica) → **tots els camins** (llista, carril, menú)
  actualitzen l'Editor i les llistes. **1 test nou** (regressió).

### Afegit
- **Franja «EDITOR»** entre els carrils i les llistes (app/visor.py): mostra
  **en gran** l'element seleccionat (🎵 acord / 🎼 secció) i s'edita
  **directament allà**, **sense cap finestra emergent**. Camps: **Nom**
  (i **Família** per a secció), **Inici (s)** i **≈ C.B** (compàs.beat,
  sincronitzats) + botó **Aplica** (o Enter). S'actualitza en canviar la
  selecció (timeline o llistes) i reutilitza la normalització, l'undo i els
  invariants. **Els dobles-clics ja NO obren diàleg**: carril i llista
  **seleccionen i enfoquen l'Editor**. **7 tests nous**
  (`EditorFranjaTests`). Fix: `import QLineEdit` al visor.

### Afegit (anterior)
- **Menús `Edita` i `Selecciona` completats** (reusant la lògica existent):
  - **Edita**: Afegeix acord… · Afegeix secció… · Elimina element (`Del`) ·
    Duplica element (`Ctrl+D`) · Reanomena element (`F2`), a més de
    Desfer/Refer i Paràmetres.
  - **Selecciona**: Selecciona l'acord/secció del cursor · Marca loop A/B
    (`Ctrl+[` / `Ctrl+]`) · Neteja el loop · Activa/desactiva loop.
  - `timeline.set_loop(None, None)` ara **neteja** el loop (abans petava).
  - **5 tests nous** (`MenuEdicioTests`).
- **Verificat el doble-clic** d'edició als 4 llocs: **carrils** (acord i
  estructura) obren l'editor inline ✅; a les **llistes** el senyal
  `itemDoubleClicked` hi és connectat (`_edita_acord`/`_edita_seccio`) però
  no s'ha pogut comprovar en entorn headless (limitació de QTest sense
  ratolí). Les accions del menú cobreixen el cas.

### Canviat
- **Barra 1 reordenada segons el FLUX de treball**: ara és
  `Obre…` → opcions de temps (selector BPM·compàs/Lliure, BPM, 🎯 Detecta,
  Compàs, Offset, ≈ C.B, Inclou estructura) → `Analitza` → `Exporta`.
  Abans `Analitza` i `Exporta` eren en una barra a part que quedava ABANS
  de la de temps i trencava l'ordre natural. Tot en **una sola barra**.
  Docs (`ESQUEMA_UI.md/.html/.svg`) actualitzats.

### Documentat
- **`docs/ESQUEMA_UI.md` · `.html` · `.svg` actualitzats a la vista actual
  (v0.2.2)**: finestra única amb el **visor al centre**, **dues barres
  d'eines** (temps + transport), **dos camps d'offset** sincronitzats
  (segons · compàs.beat), **metrònom**, **count-in**, llistes sota l'ona i
  el dock **«Log · Informació»** (log 3/4 + ajuda «live» 1/4). Taules de
  noms, interaccions, mides i colors al dia.

### Afegit
- **Offset amb DOS camps sincronitzats**: `Offset` (segons) i `≈ C.B`
  (compàs.beat). El camp compàs.beat és **relatiu a la graella original
  (offset = 0)** -> el número que hi escrius és el que llegiries al regle
  amb offset 0. Exemple: a 101 BPM 4/4, `5.1` = 9,50 s. Escriure en un camp
  actualitza l'altre i la graella. En mode Lliure s'amaga amb la resta de
  paràmetres. **3 tests nous** (`OffsetDosCampsTests`).

### Arreglat
- **Les llistes d'acords/estructura no seguien l'offset**: mostraven
  l'etiqueta de compas calculada amb offset 0 (p. ex. `5.1 Am` per un acord
  a 9,5 s), mentre el regle ja el tenia en compte. Dues causes: `_fmt_compas`
  no hi aplicava l'offset, i `_actualitza_temps` no repoblava les llistes en
  canviar la graella. Ara les dues coses van be (i amb compassos negatius
  abans del compas 1). **1 test nou** (`OffsetLlistesTests`). Tambe s'ha
  tornat a importar `math` a `app/visor.py` (calia per `math.floor`).

## [0.2.2] — 2026-10-06 (tag `v0.2.2-checkpoint`)

### Afegit
- **Compte enrere (count-in) al silenci inicial**: abans de l'offset (el
  compàs 1) la graella ara és **negativa** en comptes de quedar-se clavada a
  `1.1`. Així, si el compàs 1 cau a 9,5 s, el silenci es llegeix
  `-3.1 … -2.2 … -1.3` (com un compte enrere). Passa a `fmt_pos` (regle) i
  `pos_compas` (export). I el **clic del metrònom també sona al count-in**
  (des de t=0 de la cançó, no només des de l'offset). **3 tests nous** (+1
  adaptat).

### Canviat
- **Detecció de BPM reescrita (`app/tempo.py`, numpy pur)**: l'antic mètode
  (beat tracker d'**aubio** + mediana dels intervals) fallava amb temes reals:
  amb prou feines encertava `01 101bpm pep live RE-ESTRUCTURA.wav` (9,5 s de
  silenci inicial; aubio hi veia **139,7** BPM quan és **101**). El nou mètode
  calcula l'**envolupant d'onsets** (flux espectral, 10 ms), en treu el
  silenci inicial, en fa l'**autocorrelació** i puntua cada BPM candidat amb
  una **«comb»** (suma als múltiples 1-4, lleu biaix a 90-180 BPM).
  **Validat**: `101 → 101,0` i `118 → 117,8`. `pipeline.detecta_bpm` ara
  delega a `tempo.detecta_bpm`; l'antic queda com a `detecta_bpm_aubio`.
  **3 tests nous** (`TempoTests`, amb WAV sintètica i silenci inicial).

## [0.2.1] — 2026-10-06 (tag `v0.2.1-checkpoint`)

### Canviat
- **Llistes i log tornen a l'espai buit sota l'ona**: al PAS 6 les llistes
  havien passat a un dock lateral i havien deixat el visor buit. Ara tornen
  **al visor, sota l'ona** (acords | estructura) i el **log de l'anàlisi** és
  **visible per defecte** a baix. Retirat el dock «Inspector» i la seva acció
  del menú. Es mantenen clic-per-saltar, doble-clic-per-editar i menú
  contextual de les llistes.

### Afegit
- **Offset real (compàs 1)**: el camp «Offset (s)» ara s'aplica **a tot
  arreu** amb la MATEIXA graella: el **regle/graella** del timeline
  (`fmt_pos`, `grid_levels`, `snap_time` i el pintat de `GridLayer`/
  `RulerLayer`), el **clic del metrònom** i l'**export** (`pos_compas` +
  `desa_abc_csv`/`fer_abc`, coherent amb `acords_a_live.py` que ja
  l'usava). Abans només l'usava l'export.
- **Analitza ▸ «Marca el compàs 1 aquí»**: posa l'offset a la **posició del
  cursor** i ho propaga (regle + clic + export). És el que fa que el
  metrònom quadri amb cançons reals.
- **Límit de BPM al metrònom**: sense clics per sobre de **400 BPM**
  (`metronom.BPM_MAX`) → evita bucles de milions de voltes amb un BPM
  exagerat.
- **5 tests nous** (`OffsetTests`): fmt_pos, snap_time, pos_compas,
  metrònom amb offset i límit de BPM.

### Arreglat
- **Els botons 🔇 (mute) i 🔁 (loop) de la barra de transport no feien res**:
  `commuta_mut()` i `commuta_loop()` llegien l'estat dels botons **propis del
  visor** (`b_mut`/`b_loop`), que la barra no toca -> el botó es marcava però
  el visor veia el seu desmarcat. Ara hi ha `set_mut(on)`/`set_loop(on)`
  (setters explícits) i els botons de la barra els criden amb el seu estat,
  sincronitzant els botons interns. `commuta_*` passen a ser un toggle.
  **3 tests nous** (`TransportBarTests`) que proven la barra.

## [0.2.0] — 2026-10-06 (tag `v0.2.0-checkpoint`)

### Afegit
- **Metrònom (PAS 3: interfície i estat gris)**:
  - Botó marcable **🥁** i un **QSlider 0-100** (per defecte **60**) a la barra
    de transport, al costat del mute, amb tooltips. Acció marcable
    **Visualitza ▸ Metrònom**, sincronitzada amb el botó.
  - **Només disponible en mode BPM · compàs**: en mode **Lliure** es
    desmarca i es desactiven (gris) botó, acció i slider, amb tooltip
    «Només disponible en mode BPM · compàs». En tornar a BPM es reactiven.
  - Si el mode passa a Lliure mentre sona amb el clic activat, **reengega
    sense clic** des de la posició (a `_actualitza_temps`).
  - El color de l'estat activat viu a `app/theme.py` (`METRO_ACTIU`), no al
    codi del visor.
  - 2 tests nous a la finestra.

### Canviat
- **Metrònom (PAS 2: integració a la reproducció)** — `app/visor.py`:
  - Estat `metro_on = False` i `metro_vol = 0.6`.
  - A `_engega_des_de()`, **després** d'aplicar volum/mute de la cançó, els
    clics es **mesclen al mateix buffer** que s'envia al reproductor (només
    des del punt de reproducció endavant → funciona des de qualsevol posició
    i amb el loop A/B). **El mute/volum de la cançó no afecta el clic.**
  - `commuta_metro()` i `_canvia_vol_metro(v)`, amb el **mateix patró** que
    `commuta_mut`/`_canvia_volum`: si sona, atura i reengega des de la
    posició actual. Volum amb clamp 0-1.
  - 5 tests nous (`MetroVisorTests`). Encara **sense widgets**.

### Canviat
- **Metrònom (PAS 1: generador)** — `app/metronom.py`, numpy pur sense Qt:
  - `genera_clic(sr, accent)`: clic de 25 ms (sinusoide, envolupant
    exponencial). Accent → 1500 Hz (temps 1 de cada compàs); normal → 1000 Hz.
  - `mescla_metronom(...)`: mescla els clics a la rodanxa int16 mono,
    **només** els que cauen dins (funciona des de qualsevol posició i amb
    loop A/B). Suma en **float32** i fa **clip a int16**. BPM ≤ 0 / no finit
    → no fa res; `bpb < 1` → es tracta com 1; `volum=0` → retorna l'àudio.
  - **Graella**: la MATEIXA que el regle (`beat = 60/bpm`, compàs cada `bpb`).
    El visor **no aplica cap offset** a la visualització → no se n'ha afegit
    (queda com a paràmetre opcional `offset=0.0`).
  - 6 tests nous (`MetronomTests`): posicions a 120 BPM 4/4, començar a mig
    compàs, BPM invàlid, clip, volum 0, `bpb<1`.

### Canviat
- **Reorganització de la GUI — PAS 6: llistes al tauler «Inspector».**
  - Les llistes d'acords i estructura viuen en un **tauler lateral dret
    plegable** (`QDockWidget` «Inspector»), **amagat per defecte**;
    s'obre amb **Visualitza ▸ Mostra l'inspector**. Mantenen clic-per-salta,
    doble-clic-per-editar i menú contextual.
  - El visor les exposa en un contenidor (`self.inspector`) que la finestra
    re-parenta al dock; si el visor s'executa sol, queden al lloc de sempre.
  - **Edició des del timeline**: amb el panell amagat, desfer/refer, Delete,
    Ctrl+D (duplica), menú contextual i renombrat inline **ja funcionen**
    (passos P2-T2/T3/T5). Únic pendent: *afegir* un clip nou només és al
    menú contextual de la llista (es pot afegir al timeline més endavant).
  - El **log propi del visor** s'amaga quan va incrustat (ja hi ha el tauler
    «Log» de la finestra).

### Canviat (anteriors)
- **Reorganització de la GUI — PAS 5: barra de transport única.**
  - Els botons de transport (play/stop, −10s/+10s, loop A/B, zoom 🔍−/🔍+/Tot
    i mute) viuen ara en una **QToolBar pròpia** de la finestra (2a fila),
    **fora del visor**.
  - **Reutilització**: els botons criden els **mètodes existents del visor**
    (`play_stop`, `stop_inici`, `ves_a`, `marca_A/B`, `commuta_loop`,
    `zoom`, `zoom_tot`, `commuta_mut`) — no s'ha reescrit cap lògica.
  - Quan el visor va **incrustat**, la seva fila de transport **s'amaga**
    (el visor segueix funcionant sol si s'executa standalone).
  - **Tooltips amb la drecera** (Espai = play/stop). Es mantenen les
    dreceres existents.
  - Nota: el botó 🔇 del visor (a la fila del lliscador) es manté; el de la
    barra de transport és el mateix estat.

### Canviat (anteriors)
- **Reorganització de la GUI — PAS 4: exportar a Fitxer.**
  - «Finalitza i publica» passa a **Fitxer ▸ Exporta… (Ctrl+E)** i un botó
    **«Exporta»** a la barra d'eines. Mateixa lògica de `exporta()`; **no
    canvia què exporta ni els noms de carpetes/fitxers**.
  - **Desactivat** fins que hi ha un resultat d'anàlisi (`b_export` només
    s'activa a `acabada(True, …)`).

### Canviat (anteriors)
- **Reorganització de la GUI — PAS 3: «Analitza» com a acció + log plegable.**
  - **Fora el QGroupBox «3 · Analitza i exporta»**.
  - El botó «Processa» passa a **«Analitza»** a la barra d'eines (i a
    **Analitza ▸ Analitza**, `F5`). Crida el mateix `executa()`.
  - El **progrés** va a un `QProgressBar` permanent a la **barra d'estat**.
  - El **log** passa a un **QDockWidget inferior plegable**, **tancat per
    defecte**, que s'obre sol si hi ha error. **Visualitza ▸ Mostra el log**.
  - **Estats dinàmics**: «Analitza» desactivat sense WAV i mentre hi ha una
    feina en curs (centralitzat a `_carrega_visor`).
  - 3 tests nous + 2 adaptats (els noms dels botons canvien a propòsit).

### Canviat (anteriors)
- **Reorganització de la GUI — PAS 2: el timeline és la finestra.**
  - **Fora el `QDockWidget`**: el visor passa a ser el **widget central**
    (via `QStackedWidget`: pàgina 0 = placeholder, pàgina 1 = visor).
  - **Obrir una WAV mostra l'ona i el timeline immediatament**, ABANS
    d'analitzar, amb les pistes Acords i Estructura **buides**. No cal
    reescriure el visor: el seu constructor ja acceptava `acords=None` /
    `abc=None` (pistes buides) i, si la carpeta té CSV, els carrega sols.
  - **Fora el QGroupBox «1 · Tria la wav»**: obrir WAV passa per
    **Fitxer ▸ Obre WAV… (Ctrl+O)** i un botó **«Obre…»** a la barra
    d'eines. El **nom del fitxer va al títol** de la finestra i la info
    (durada, canals, Hz) a la **barra d'estat**.
  - Sense WAV es manté el **placeholder** al centre.
  - Fora l'etiqueta «Flux: …» (ja no és un assistent) i l'acció
    «Mostra el visor» del menú Visualitza.
  - **Test adaptat** (`test_obre_wav_mostra_timeline_buit_abans_d_analitzar`):
    abans s'esperava placeholder sense CSV; ara s'espera visor amb pistes
    buides. Comportament canviat a propòsit pel pas 2.

### Canviat (anteriors)
- **Reorganització de la GUI (estil Audacity/DAW) — PAS 1**: el QGroupBox
  «2 · Temps i paràmetres» passa a ser una **barra d'eines fina d'una sola
  línia** (`QToolBar`, no movable) sota el menú: selector
  **BPM · compàs / Lliure**, camps de text **BPM**, **Compàs**, **Offset (s)**,
  botó **🎯 Detecta** i la casella **Inclou estructura**. Mateixos widgets i
  mateixa lògica (entrada de text amb coma decimal; els paràmetres
  s'amaguen en bloc en mode Lliure). La resta de la finestra no canvia.

### Pendent de polir (visor)
- Confusió visual entre clip **seleccionat** (vora groga) i **actiu**
  (fons més clar, segons el cursor).
- Usabilitat: multi-selecció, duplicar/eliminar clips, menú contextual,
  afegir clips amb click al buit (Fase D.1 del ROADMAP).

## [0.1.8] — 2026-10-06 (tag `v0.1.8-checkpoint`)

### Afegit
- **Menú contextual** (botó dret) sobre un clip del timeline amb
  **Duplica**, **Elimina** i **Reanomena**, reutilitzant les accions dels
  punts anteriors i el rename inline existent. Les tres accions surten
  **desactivades** si no hi ha cap clip seleccionat. El botó dret al buit
  segueix fent **pan** (no s'ha perdut).

### Canviat
- **Seleccionat vs actiu, clarament diferents**: abans el `SELECTION_COLOR`
  era el mateix groc que la guia de snap i el fons «actiu» era quasi blanc
  (es confonien). Ara:
  - **ACTIU** (el clip que sona) → **fons verd suau** (`#1f5c3d`) + vora verda;
  - **SELECCIONAT** (el clip clicat) → **vora cian brillant i gruixuda**
    (`#38bdf8`, 3 px).
  Són estats **independents** (un clip pot ser tots dos alhora).
- **Tots els colors del visor centralitzats a `app/theme.py`** (abans hi
  havia ~18 hex escampats per `app/timeline.py`). Aquest ja no en conté cap.

### Afegit
- **Ctrl+D duplica el clip seleccionat** (acord o secció), amb **undo** i
  respectant les invariants. On s'insereix: **just després de l'original,
  repartint la seva durada** (no es desplaça res):
  - **acord** → el duplicat va a mig camí entre l'original i el següent;
  - **secció** → l'original es parteix en dues meitats (ini–mig, mig–fi).
  Si no hi ha espai suficient, no fa res i ho diu al log. 2 tests nous.
- **Tecla Delete/Backspace** esborra el **clip seleccionat** (acord o
  secció) al visor. Passa pel sistema d'**undo** (`_undo_marca`/
  `_undo_commit`) i respecta la contigüitat (en treure una secció, el
  veí ocupa l'espai buit). Els items de QGraphicsView no reben tecles (no
  són focusables), per tant es gestiona al `TimelineView`. 2 tests nous.

### Verificat
- **Clic a un clip → cursor al seu inici** (acords i seccions): JA funcionava
  (es va arreglar en una versió anterior: el lambda del click capturava el
  valor vell d'`ini`/`t`). Afegit un **test de regressió**
  (`test_click_a_un_clip_mou_el_cursor`).

### Documentat
- **README**: «Estat actual» posat al dia (v0.1.8) i el bloc de configuració
  de `AUTO_CHORDS_TEMP` tret de dins de «Filosofia i lògica del flux»
  (trencava la secció «Semàntica del flux») → nova secció «Configuració».
- **DEVELOPING.md**: «Python 3.8+» → **3.10+** (coincideix amb
  `requires-python` del `pyproject.toml`).
- **requirements.txt**: treta la menció a `als2rpp.py` (ja no hi és).

### Netejat
- **Imports sense ús** trets (`pyflakes` no és al venv i instal·lar-lo seria
  una dependència nova → anàlisi amb l'AST de la stdlib): `visor.py`
  (`atexit`, `math`, `QObject`, `QThread`, `pyqtSignal`), `timeline.py`
  (`QObject`, `Tuple`), `main.py` (`QObject`, `QSpinBox`). Variables
  leftovers: `tsrc` i `idx`.
- **`AUTO_CHORDS.desktop`**: tenia un **byte NUL** al final (podia trencar
  alguns parsers) i una **ruta absoluta fixa** (`/home/peplx/...`). Ara usa
  `%k` (la ubicació del mateix `.desktop`) → **funciona des de qualsevol
  carpeta o usuari**. `launcher.sh` fa el seu propi `cd`.

### Canviat
- **Missatges d'error al log**: els handlers `except Exception` que només
  mostraven un `QMessageBox` (o que s'empassaven l'error en silenci) ara
  **també escriuen a `auto_chords.log`** amb el context. 14 punts a
  `app/visor.py` (12 de `QMessageBox` + la lectura de CSV malmès + el
  directori temporal). Els handlers benignes (procés ja mort, senyal ja
  desconnectat, fallback d'API Qt) es deixen silenciosos a propòsit.
  Comportament visible **sense canvis**.

### Arreglat
- **Els tests ja no es pengen en entorns sense pantalla (CI)**: els
  `QMessageBox` de `Visor.exporta()` i `Finestra.exporta()` són **modals** i
  bloquejaven per sempre (ningú no pot clicar «OK» sense pantalla). Als
  tests es neutralitzen. També `QT_QPA_PLATFORM=offscreen` a nivell de
  mòdul i `pipeline.run()` amb `timeout` (un subprocés encallat ja no
  penja). 2 tests nous (`PipelineRunTests`).

## [0.1.7] — 2026-10-05 (tag `v0.1.7-checkpoint`)

### Afegit
- **Plugin Vamp d'aubio** (`vamp-aubio-linux64-local/`): detecció de
  **tempo/BPM** i **pulsacions** (`vamp:vamp-aubio:aubiotempo:beats`),
  més onsets, pitch, notes, silencis i descriptors. Compilat localment
  **sense sudo** (`libaubio-dev` via `apt-get download`), flags
  `-msse -msse2` (sense AVX). Afegit a `VAMP_DIRS`.
  Guia de reproducció i precisió: `docs/AUBIO_TEMPO.md`.
- **Nou flux de temps** (`app/main.py`): en lloc del checkbox «tempo fix»,
  un **selector de 2 estats** — **BPM · compàs** / **Lliure (hh:mm:ss)**.
  En mode BPM hi ha un botó **🎯 Detecta** que crida `pipeline.detecta_bpm()`
  (aubio) i omple el camp (editable). En mode Lliure s'amaguen els camps
  de BPM.
- **Entrada de text manual**: fora les fletxes ▲▼ (`QDoubleSpinBox`/
  `QSpinBox` → `QLineEdit`). Accepta coma decimal (`101,5`).
- **`concatena.py`**: genera `CODI_concatenat.txt` (tot el codi font en un
  sol fitxer, amb índex; exclou `.venv/.git/.deps`, binaris, plugins i el
  C++ de tercers). L'artefacte generat queda a `.gitignore`.

### Canviat
- `pipeline.detecta_bpm(wav, log)`: BPM a partir de la **mediana** dels
  intervals entre pulsacions (aubio).

### Arreglat
- **Compàs de qualsevol mètrica**: `pos_compas` tenia `SB = 8` fix (només
  4/4) i contradeia `acords_a_live.py`. Ara usa `bpb` (`SB = bpb*2`) i
  funciona amb 3/4, 6/8, 5/4… El `bpb` es propaga a `desa_abc_csv`,
  `fer_abc` i tots els camins de crida.
- **Resolució temporal unificada dels CSV**: `acords.csv` guardava 9
  decimals i `estructura_ABC.csv` 2 (7 ordres de magnitud de diferència).
  Ara tots dos a **2 decimals = 10 ms** (constant `TEMPS_DEC`).
  Tests nous a `FormatCsvTests`.

### Netejat
- Fora el material innecessari per l'app actual (a la paperera; tot
  recuperable de git): **`tauri-ui/`** (experiment Tauri aparcat, 8,8 GB
  amb build + node_modules), `AUTO_CHORDS_TAURI.sh`,
  `nnls-chroma-osx-v1.1/` (plugin macOS), `als2rpp.py` (v1 obsoleta),
  `XXAUTO_CHORDS_dev.sh` (duplicat), `exemple_*`, `auto_chords.log`,
  `__pycache__/`.
- **Projecte: 9,3 GB → 508 MB (−95 %).**
- ⚠️ `codi_font_chordino/` es va restaurar: `instal·la_local.sh` el necessita.

## [0.1.6] — 2026-10-05 (tag `v0.1.6-checkpoint`)

### Afegit
- **Barra de menús** (`app/main.py`): Fitxer · Edita · Selecciona ·
  Visualitza · Analitza · Ajuda, amb les accions bàsiques cablejades
  (obre WAV, exporta, desfer/refer, zoom, loop A/B, ajuda).
- Captura d'**excepcions no gestionades** al log (`sys.excepthook`) i els
  logs del visor ara també van a `auto_chords.log`.

### Arreglat
- **CRÍTIC — el visor incrustat quedava sord**: `_carrega_visor` fa
  `_embedded = True` + `close()`, i el `closeEvent` **desconnectava tots
  els senyals del timeline** sense comprovar `_embedded`. Ara només
  desconnecta si el visor és una finestra autònoma. Això arreglava alhora
  l'undo/redo i la propagació de canvis.
- **Undo/Redo**: la captura de l'estat passava pel senyal de canvi i no
  arribava mai. Ara es fa **a l'inici del gest** (`editStarted` al mouse
  press dels clips) — model Audacity (`PushState` explícit). La base
  s'autoactualitza (`_undo_touch_base`); el reanomenament pel diàleg
  (`_edita_acord`/`_edita_seccio`) ara apila operació; i l'accés a la llista
  va protegit (un `.index()` sobre una tupla normalitzada podia **fer
  petar l'app**).
- **Imatges fantasma** en redimensionar: `prepareGeometryChange()` ha
  d'anar **abans** de canviar la geometria (8 llocs: setters de
  `ChordItem`/`SectionItem` i les capes). Afegit `FullViewportUpdate`.
- **Mètodes duplicats** `_elimina_acord_index` / `_elimina_seccio_index`
  eliminats (la 2a definició guanyava).

### Nota
- Undo/Redo treballa **només** sobre el model (les dades que van al CSV);
  mai regenera wavs.

## [0.1.5] — 2026-10-05 (tag `v0.1.5-checkpoint`)

### Afegit
- **Desfer/refer (undo/redo)** d'edició: moviment, redimensionat i canvi
  de nom, tant d'acords com d'estructures. Pila de **snapshots** del model
  (`acords`/`seccions`). Dreceres **Ctrl+Z** (desfer) i
  **Ctrl+Shift+Z** / **Ctrl+Y** (refer). Només en memòria de la sessió.
- `docs/ESQUEMA_UI.md` — document de referència de la UI (noms de zones,
  mides, interaccions).
- `docs/ESQUEMA_UI.html` — réplica visual fidel de la GUI (HTML+CSS).
- `docs/ESQUEMA_UI.svg` — versió vectorial de l'esquema.

### Canviat
- **Les wavs ja no es regeneren a cada edició.** `_desa_i_regenera()` i
  `_regenera_abc_des_de_totes_les_seccions()` ara escriuen **NOMÉS el CSV**.
  Les `wavs_acords/` i `wavs_estructura/` es generen **exclusivament** amb
  `exporta()` («Finalitza i publica»), quan tot està revisat i editat.
  Efecte: editar és **instantani** i l'undo/redo no toca mai les wavs.

### Nota de disseny
- Les wavs generades **no tenen cap paper** en la visualització ni l'edició:
  l'ona i la reproducció fan servir el **WAV original**; l'edició treballa
  sobre el **CSV**. Les wavs són el producte final d'exportació.

## [0.1.4] — 2026-10-05 (tag `v0.1.4-checkpoint`)

### Afegit
- **Follow del cursor**: durant la reproducció, si el cursor surt de la
  zona còmoda (0–85 % de la vista), la vista es desplaça per deixar-lo
  a ~15 % de l'esquerra (estil DAW). S'activa amb ▶ i s'atura amb ⏸.
- **Cursor hover** als clips d'acord i de secció: la «mà» sobre el cos,
  fletxes ↔ a les vores (paritat acords/estructura).

### Arreglat
- **Click sobre un clip desplaçat**: les connexions capturaven l'inici
  en crear el lambda (`lambda t0=float(ini)`) → després d'un resize, el
  click anava al **vell** inici. Ara es llegeix el valor **actual**
  de l'item (`it.ini` / `it.t`).
- **Cos de secció**: ara mou inici **i** fi (desplaça) com els acords;
  abans només movia l'inici (bug «només enrere»).
- **Propagació de contigüitat**: el fi d'un clip = inici del següent,
  recalculat sempre (2 bugs que col·lapsaven/separen clips).

## [0.1.3] — 2026-10-05 (tag `v0.1.3-wip`)

### Afegit / Canviat
- **Paritat acords/estructura**: les estructures passen a model «només
  inici» (el fi es deriva del veí); cos de secció desplaça inici+fi.
- **Snap més fi**: mai el compàs sencer — setzena (span ≤ 8 beats),
  corxera (≤ 32) o temps; mode lliure 0.02–1.0 s.
- Llindar de click 3 → 5 px; la guia de snap s'amaga al deixar anar.
- Regeneració només al release (no a cada frame).

## [0.1.2] — 2026-10-05 (tag `v0.1.2`)

### Afegit / Canviat
- **Coordenades unificades** al visor: clips, cursor, grid, regle, ona,
  guia i loop tots relatius a la vista (`_x_to_time` únic); escena =
  mida de la viewport. Abans clips/cursor eren absoluts i la resta
  relatius → es desalineaven amb zoom/scroll.
- **Pan** amb botó dret arrossegant; **roda = zoom** centrat al clip
  seleccionat (o al cursor).
- **Loop A/B** arrossegant sobre el regle (banda groga).
- Sincronització bidireccional llista ↔ timeline; Space = play/pausa.

## [0.1.1] — 2026-10-05 (tag `v0.1.1`)

### Afegit
- Visor DAW-like: **ona plena** (estil Audacity, envolupant min/max per
  tram visible) + **GridLayer** (compàs/beat/subdivisió) + regle a dalt.
- **2 carrils sobreposats** semitransparents (estructura + acords).

## [0.1] — 2026-10-01 (tag `v0.1-punt-control`)

### Afegit
- Script únic `wav_a_wavs.py` (mateix motor que l'app, sense duplicar lògica).
- Entorn aïllat Ubuntu sense sudo: `requirements.txt` (`PyQt5`,
  `pyqtgraph`, `numpy<2` obligat pel Q9400) + `instal·la_local.sh`
  (venv + `.deps/` amb headers via `apt-get download`, sense instal·lar).
- `chordextract` compila en local (`.deps/`); via `sonic-annotator` intacta.
- `fer_abc` per famílies (`N1/N4→N`), fusió d'adjacents i resum de
  repeticions (ex. `ABCBACDACA, A×4 B×2 C×3 D×1`).

### Arreglat
- `acords_a_live.py`: csv amb tot `N` donava `IndexError`; ara error
  llegible (`cap acord detectat...`, sortida 1).

## [No publicat — visor fase A/B.1]

### Afegit
- Visor fase A (`app/visor.py`): ona + acords + estructura + escolta amb
  transports (play/pausa/stop, ±10 s, volum/mute, loop A-B, zoom, temps),
  botó «Analitza» (Chordino+Segmentino en fil) i ressalt del que sona.
  Reproducció amb `paplay` extern (QtMultimedia aparcat: segfault).
- Visor fase B.1: doble-clic a un acord → desa `acords.csv` i regenera
  `wavs_acords/` (i locators/guia) sense tornar a Chordino.
- `CHANGELOG.md`, `ROADMAP.md`, `pyproject.toml`.
