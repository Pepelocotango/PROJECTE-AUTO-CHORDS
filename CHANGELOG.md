# Registre de canvis — PROJECTE AUTO CHORDS

Format [Keep a Changelog](https://keepachangelog.com/ca/1.0.0/).
Versions amb tag git (`v0.1-punt-control` … `v0.3.0-checkpoint`).

## [No publicat]

### Afegit
- **`eines/explica_bpm.py`**: genera un gràfic (PNG) que explica com es
  detecta el BPM (envolupant → autocorrelació → puntuació comb → prior), amb
  el cas real. Útil per documentar i per depurar casos difícils.

### Arreglat
- **BPM: ambigüitat d'octava/subdivisió** (cas real: *Sitting On The Dock Of
  The Bay*, Otis Redding). El biaix pla antic («+15 % a 90–180») **no** la
  resolia: amb corxera forta guanyava **179,8** en comptes del temps real
  **103,5** (que només quedava a un 2 %). Nou **prior de plateau**
  (`tempo._prior`): val **1,0 dins 80–160 BPM** i cau suaument (gaussiana en
  log₂, σ=0,7 octaves) fora. Verificat que **no trenca** cap tema conegut:
  101 · 138 · **70** · 117,8 · 107 · i l'Otis passa a **103,5** ✅. El
  «rang preferit» del diàleg ara és aquest plateau (80–160). **3 tests nous**
  (`TempoOctavaTests`), amb un clic-track sintètic que reprodueix el cas.

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
