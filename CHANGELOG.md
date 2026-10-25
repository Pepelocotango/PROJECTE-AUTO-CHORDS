# Registre de canvis — PROJECTE AUTO CHORDS

Format [Keep a Changelog](https://keepachangelog.com/ca/1.0.0/).
Versions amb tag git (`v0.1-punt-control` … `v0.8.0`).

## [Unreleased]

### Corregit (2026-10-25) — ×2/÷2 als clips de BPM/compàs mantenen la duració en segons
- **`app/tempo_map.py`**: afegit paràmetre opcional `preserva_fi_idx` a
  `neteja_trams()`, `normalitza_trams()` i `valida_i_normalitza_compassos()` per
  poder preservar el `fi` original d'un tram específic quan es fa una edició
  mètrica (×2/÷2). Abans, normalitza_trams() re-derivava tots els fi des dels
  ini següents, fent que el fi original del clip editat es perdés i el clip
  s'estirés o encogia incorrectament.
- **`canvia_compassos_tram()`**: ara passa `preserva_fi_idx=i` a
  `valida_i_normalitza_compassos()` quan s'aplica una edició mètrica.
- **Exemple**: clip 0-8s a 120 BPM (4 compassos)
  - ×2 → 0-8s a 240 BPM (8 compassos, mateixa duració)
  - ÷2 → 0-8s a 60 BPM (2 compassos, mateixa duració)
- **Test**: `test_tempo_trams` › `test_compassos_mes_menys_i_doblar` ara verifica
  que `out[0][1]` (el fi) es manté en 8.0s per a totes les operacions (+1, -1,
  ×2, ÷2).
- **Docs**: `docs/EDICIO_OPERACIONS.md` actualitzat per especificar que ×2/÷2
  mantenen els segons immòbils i només recalculen el BPM.
- Suite **1.386 OK** (1 skip), pyflakes net.

### Documentació (2026-10-23, 11p) — les regles de temps/compàs, al canònic
- **`docs/REGLES_DE_LA_APP.md`** incorpora el **§13 «Temps, compàs i graella»**
  (13.1–13.8 + notes d'aplicació): els segons com a font de veritat, el mapa com
  a amo de la graella, cobertura/contigüitat, compassos enters i valors, re-tempo
  local (**sense *ripple***), fronteres i marcadors, **clips en segons (`0/0`)** i
  detecció/export del mapa. Passa a ser l'**únic document normatiu**.
- **Fusionats i arxivats** a `docs/archive/`: `REGLES_TEMPS_GRID.md` (contracte
  vell) i `FLUX DE TEMPO VARIABLE.md` (especificació del re-tempo; el seu §5, amb
  el «mínim de 0,5 s», ja estava superat). Les **referències repuntades** a
  `§13.x` a tot el codi, els tests, `AGENTS.md`, `ROADMAP`, `docs/` i
  `concatena.py` (19 ocurrències).
- **Tres contradiccions eliminades** (el codi ja no les feia): «el BPM
  arrossega les fronteres següents» (§13 antic), «el marcador és independent»
  (`MARCADORS.md`, `ESQUEMA_UI.md`, `ANALISI_GUIAT_v3.md` → ara §13.6) i «el tram
  de tempo només s'edita amb diàleg emergent» (§11 → també franja Editor i
  llista ⑭).
- Suite **1.368 OK** (1 skip), pyflakes net.

### Corregit (2026-10-23, 11v) — regla #5: la UI no fabrica trams
- **`visor._desa_csvs_base`** muntava a mà el tram únic a partir del transport
  (`self.bpm`/`self.bpb`) i **no** refrescava `self.tempo_map`: es podia desar
  un `tempo.csv` a 140 BPM mentre la graella encara anava a 120 (dues fonts de
  veritat). Ara la sincronització la fa el **punt únic**
  (`_refresca_tempo_map`), que rederiva model **i** mapa alhora.
- **Test**: `test_edicio` › `TestLlistaTempo.test_desar_no_deixa_el_mapa_derivat_endarrerit`
  (comprova model, mapa derivat **i** el `tempo.csv` del disc).
- Docs: regla #5 (punt únic + «la UI no munta trams»). Suite **1.385 OK**.

### Corregit (2026-10-23, 11u) — regla #4: sense durada, el mapa no es destrossa
- **`tempo_map.neteja_trams`** amb `durada == 0` (WAV absent o encara no
  carregat) posava el `fi` de l'últim tram a **0**: el tram quedava **invertit**
  (10 → 0) i el mapa es desava així (un projecte amb l'àudio il·legible perdia
  el mapa). Ara, si la durada no es coneix, la cobertura **no s'imposa** i es
  conserva el `fi` propi. Amb durada > 0 tot igual (l'últim acaba a la WAV).
- **Test**: `test_tempo_map` › `test_sense_durada_el_mapa_no_es_destrossa`.
- Docs: §13.3. Suite **1.384 OK** (1 skip).

### Canviat (2026-10-23, 11t) — regla #3: banda de BPM al re-tempo (decisió)
- **Arrossegar una frontera** ja no pot deixar un tram **amb compàs** fora de
  **30–350 BPM**: com que N es conserva, un clip d'1 ms demanava **1.200.000
  BPM** (i el veí, 80). Ara el gest **es rebutja** i l'avís diu **entre quins
  segons** sí que hi cap. Continua **sense** mínim de 0,5 s.
- **Els clips rubato (`0/0`) no tenen cap regla**: es mouen lliurement (sense
  mínim ni banda). Però **el seu veí amb compàs sí**: abans la branca «algun
  costat va en segons» deixava eixe costat amb el BPM vell i, per tant, amb un
  **nombre de compassos fraccionari** (fora de graella). Ara conserva N, en
  deriva el BPM i respecta la banda.
- **`_bar_quarters(0, 0)`** ja no peta (`ZeroDivisionError`): un tram en segons
  val 4 de notació.
- **Tests**: 2 reescrits (codificaven la decisió del 22-10 «drag sense banda»:
  `test_arrossegar_dins_de_la_banda_es_lliure`,
  `test_no_es_pot_deixar_un_tram_fora_de_la_banda`) + 3 de nous (veí mètric d'un
  rubato re-tempa, veí mètric respecta la banda, dos rubatos són lliures) i 2
  actualitzats (vora d'un mètric i test del visor).
- Docs: §13.5 (banda), §13.6 («arrossegar és lliure» + taula), §13.7 (vores del
  rubato). Suite **1.383 OK** (1 skip).

### Corregit (2026-10-23, 11s) — regla #2: la contigüitat del mapa, estructural
- **`TempoMap.__init__`** re-deriva el `fi` de cada tram a partir de l'`ini` del
  següent (l'últim conserva el seu): una llista amb **forats o encavalcaments**
  (CSV editat a mà, client antic) ja **no pot** produir una graella trencada.
  És el mateix criteri que `neteja_trams` al model, però a la capa derivada, de
  manera que quede garantit encara que un camí nou s'oblide de normalitzar.
- **`visor._refresca_tempo_map`**: comentari del punt únic de reparació
  reescrit (havia quedat tallat en fusionar les regles #1 i #2).
- **Tests**: +2 (`TempoMap` amb forat i amb encavalcament → contigu; i la
  bateria al visor —afegir tall, desfer, refer, moure la frontera, eliminar,
  desfer— amb la invariant comprovada després de **cada** gest).
- Docs: `REGLES_DE_LA_APP.md` #2 i §13.3. Suite **1.379 OK** (1 skip).

### Documentació (2026-10-23, 11r) — les referències de tests, al dia
- El canònic citava **fitxers de test que no existeixen** (eren noms de *classes*
  de la ronda de fusió de suites): `test_regles_or.py`, `test_regla12_export.py`,
  `test_requirements.py`, `test_vista_segueix_model.py`, `test_regla11_paritat.py`,
  `test_seccions_contigues`, `test_cobertura_viu`. Ara apunten al **fitxer real ›
  classe real** (`test_edicio.py` › `TestRegla1OrdreEstricte`…,
  `_regla11_paritat___Base`, `TestCoberturaViu`; `test_pipeline.py` ›
  `GuardAvxTests`, `TestRegla12ParitatExport`, `CoberturaTests`; `test_gui.py` ›
  `_vista_segueix_model___Base`).
- Mateixa correcció a `PROJECTES.md`, `PARTITURA_EXPORT.md`, `SEGURETAT.md`,
  `ESQUEMA_UI.md` i `PORTABILITAT_WINDOWS.md` (aquest, a més, ja no proposa
  `unittest tests.test_pipeline_export …`: mana `discover -s tests`, com el CI).
- Suite **1.377 OK** (1 skip), pyflakes net.

### Afegit (2026-10-23, 11q) — regla #1: l'estat invàlid no pot existir
- **`tempo_map.neteja_trams(trams, durada)`** → `(trams, avisos)`: el punt únic
  de reparació del mapa (inici negatiu → 0; inici repetit, descartat; inici fora
  del tema, descartat; fi abans de l'inici, recalculat). `normalitza_trams`
  queda com a embolcall sense avisos.
- **`visor._refresca_tempo_map`** mostra els avisos (caixa d'informació + log,
  **sense repetir-los** a cada refresc): reparar mai no és silenciós.
- **Inici duplicat impossible per construcció**: `tempo_map.afegeix_tall` no
  crea el tall si ja hi ha una frontera en eixe instant.
- **`Inici (s)` i `Fi (s)` a la franja Editor** (només en mode tempo, camp nou
  `ed_fi`): mouen **la frontera** (§13.6) amb re-tempo local del clip i del veí;
  l'**inici del 1r** clip i la **fi de l'últim** es **rebutgen amb avís**; si
  l'instant demanat no és possible, s'aplica el més a prop i s'avisa; amb un
  costat en segons (`0/0`) no es recalcula cap BPM. Si el BPM/compàs del
  formulari no s'ha tocat, no es reimposa (desfaria el moviment).
- **Docs**: `REGLES_DE_LA_APP.md` #1 (repara i avisa) i §13.6 (taula
  d'inicis/fis), `ESQUEMA_UI.md` ⑫, `EDICIO_OPERACIONS.md` #13.
- **Tests**: +8 (avisos de `neteja_trams`, `afegeix_tall` sense duplicat,
  moviment d'inici/fi amb recalcul del veí, rebuig dels extrems, rubato intacte,
  camp Fi visible només en tempo). Suite **1.377 OK** (1 skip), pyflakes net.

### Afegit (2026-10-22, 11o) — llista de clips de **tempo/compàs** editable
- **Tercera llista** a l'Inspector, al costat d'acords i seccions:
  `QTableWidget` amb **Inici (s) · Fi (s) · BPM · Compàs** (a un clip rubato, la
  columna Compàs diu «segons»). Una fila per tram del mapa.
- **Mateix tracte que les altres dues** (regla d'or #11): clic → selecciona el
  clip al timeline i hi porta el cursor; **doble-clic → franja Editor**; botó
  dret → el **mateix** menú contextual del carril (`_menu_de_llista`).
- **Franja Editor amb mode tempo**: les etiquetes passen a **BPM:** i
  **Compàs:** (el camp de compàs accepta `4/4`, `0/0` o «segons»); «Aplica»
  crida `edita_tempo_objectiu` (re-tempo local + desfer). *(11q: Inici i Fi ja
  s'hi poden escriure.)*
- **`_on_clip_selected`**: seleccionar un clip de tempo ja **no buida** la
  franja (abans ho feia perquè no hi havia editor de tempo).
- **Tests**: +6 (`TestLlistaTempo`: files/columnes, clic, doble-clic, aplicar
  BPM/compàs, `0/0`, compàs invàlid amb avís) i actualitzat el de
  `test_despatx_edicio` a la conducta nova → **1.368 OK** (1 skip), pyflakes net.

### Afegit (2026-10-22, 11n) — clips **en segons** (rubato) al carril de tempo
- **Regla nova de l'operador**: qualsevol clip de tempo/compàs pot existir **en
  segons** (compàs `0/0`), al mig del tema. Dura el que diu l'àudio; no té
  graella, ni compassos enters, ni obligació de caure en una línia.
- **`tempo_map.py`**: `Tram.lliure` / `num_ef` / `den_ef` / `bpm_ef` (0/0 →
  100 BPM 4/4 per a l'aritmètica). `normalitza_trams` i `TempoMap` conserven el
  0/0; `grid_lines` no dibuixa res dins del clip (sí la línia que l'obri);
  `label`/`fmt_pos` mostren temps; `snap` no encaixa res; el validador de
  compassos enters ignora les fronteres i els intervals que toquen un clip
  lliure. `canvia_bpm_local` accepta entrar i eixir del mode segons;
  `mou_frontera_retempo` mou la frontera sense tocar cap BPM quan un costat va
  en segons; `canvia_compassos_tram` i el pre-roll el rebutgen amb avís.
- **`dialegs.py`**: casella «En segons (sense compàs: rubato)» al diàleg del
  clip (apaga el camp del compàs).
- **`timeline_layers.py`**: el clip en segons es pinta amb color propi i
  l'etiqueta «segons · N s».
- **`visor.py`**: el transport (BPM/compàs/beat_type) només pren valors d'un
  primer clip **amb** compàs (0/0 no deixa `bpb=0`).
- **Partitura**: els clips en segons s'exporten com a compassos a 100 BPM
  (últim compàs parcial si cal).
- **Tests**: +14 (model, CSV, diàlegs, barra) → **1.362 OK** (1 skip), pyflakes net.
- **Barra de temps** (`main.py`): casella **«En segons»** al costat del compàs
  (aplica `0/0` al clip objectiu). Escriure **0 BPM** ja no es converteix en 30
  en silenci: avisa i indica la casella.
- **Corregit el bloquejador real** (`visor._refresca_tempo_map`): el mapa es
  reconstruïa des del transport i **forçava el tram 0 a 4/4 al BPM de la
  barra**; amb un sol tram, a més, el substituïa sencer. Per això un clip en
  segons «no es quedava». Ara un 0/0 es respecta (transport inclòs).
- **`DialegTempoMapa`** («Mapa de tempo i compàs»): la columna «Compàs» també
  accepta `0/0` (= clip en segons) i una fila amb BPM 0 ja no desapareix en
  silenci.
- Docs: `REGLES_TEMPS_GRID.md` §4, §5 i §10 reescrita.

## [Unreleased]

### Canviat (2026-10-22, 11m) — regla: edició lliure dels talls de tempo
- **Regla nova de l'operador**: tots els clips de tempo/compàs admeten moure
  l'inici o el fi **lliurement** (amb el snap apagat); l'extrem contrari no es
  mou i es **recalcula el BPM de dins**. Excepcions: l'inici del primer clip i
  el final de l'últim (marquen la WAV) — ara amb avís explícit.
- `mou_frontera_retempo()` i `mou_frontera_preroll()` ja **no apliquen la banda
  30–350**: eixa banda queda només per a l'edició manual del BPM. Només es
  rebutja una durada zero (`_bpm_de_n`).
- Tests: 2 reescrits (el drag de 0,6 s i el de 0,25 s ara s'accepten) →
  **1.347 OK** (1 skip), pyflakes net.

### Corregit (2026-10-22, 11l) — arrossegar el compàs 1 i fora la guarda de 0,5 s
- **`tempo_map.mou_frontera_retempo()`**: fora el mínim arbitrari
  `FRONTERA_MIN_S` (0,5 s) als dos costats. Impedia moure una frontera que ja
  hi era més a prop (compàs 1 a 0,036 s) i, amb el guard, cap posició era
  vàlida. El que bloqueja ara és la banda de BPM (30–350) i un tram de durada
  zero.
- **Pre-roll**: si el primer tram no té cap compàs (§5), arrossegar-ne la fi
  **mou el compàs 1** (`mou_frontera_preroll` + `es_frontera_preroll`): el
  pre-roll continua de 0 compassos, el tram de música conserva els seus i se'n
  recalcula el BPM. Abans es forçava `N=1` i eixien 606 BPM → rebutjat.
- `Visor._on_tempo_mogut()` encamina eixe cas al compàs 1 (un sol desfer).
- **Tests**: +4 → **1.347 OK** (1 skip), pyflakes net.

### Canviat (2026-10-21, 11k) — la roda del ratolí fa zoom al punter
- **`Timeline.wheelEvent()`**: el zoom seguix el **punt del ratolí** (el temps
  davall el cursor es queda a la mateixa columna), com en qualsevol DAW. Abans
  centrava la vista al clip seleccionat o al **playhead** («sempre seguix el
  cursor vermell»). `Shift`+roda continua fent *pan* horitzontal.
- Els botons **+/−** no canvien: zoomen al centre del clip seleccionat i, si no
  n'hi ha, al playhead.
- **Tests**: +1 → **1.343 OK** (1 skip), pyflakes net.

### Corregit (2026-10-21, 11j) — eliminar trams amb micro-trams i tornar a 4/4
- **`tempo_map.repara_fronteres()`** neteja abans de validar els trams de menys
  de **50 ms** (`neteja_trams_curts`): un `+` a 0,7 ms d'una frontera deixava un
  micro-tram i **cap** «Elimina tempo» passava («La frontera 0.273773s no cau
  en una línia de compàs», 28 intents).
- **Últim recurs `refit_trams()`**: si imantar la frontera faria curt un dels
  costats, es conserven les fronteres i es **recalcula el BPM** de cada tram
  amb `N` enter.
- **Tolerància del pre-roll en TEMPS** (1e-4 s) en lloc de 1e-5 compassos
  (20 µs a 120 BPM): l'offset es desa amb 3 decimals (`0,273`) i la frontera
  0,273090 bloquejava qualsevol reparació.
- **`canvia_bpm_local()`**: canviar **només el compàs** conserva la **durada**
  i recompta `N` (abans conservava `N` i el tram es feia 4× més llarg): un clip
  de mig tema en `1/4` (551 compassos) ja es pot tornar a `4/4` (138 compassos,
  BPM 114,19 → 114,40).
- **Tests**: +4 → **1.342 OK** (1 skip), pyflakes net.

### Corregit (2026-10-21, 11i) — la fi del primer clip pot tornar al compàs 1
- **`tempo_map.mou_frontera_retempo()`**: amb pre-música, la frontera es
  limitava a `offset + 0,5 s`, així que era **impossible** tornar la fi del
  primer clip al compàs 1 (l'intro d'«Otis», offset 1,978 s, no podia baixar de
  2,478 s). Ara el límit és el **compàs 1** (`offset`): la frontera no pot
  passar-hi abans, però sí caure-hi exactament → **pre-roll pur** (0 compassos,
  excepció §5): el primer tram conserva el BPM i només canvia la fi, i el tram
  de la dreta conserva N i recalcula el BPM.
- L'avís és específic («La frontera no pot quedar abans del compàs 1») en lloc
  de l'enganyós «a menys de 0,5 s de l'inici del tram».
- **Tests**: +2 (fi exacta al compàs 1 i rebuig abans del compàs 1) → **1.338 OK**
  (1 skip), pyflakes net.

### Canviat (2026-10-21, 11h) — l'avís de «no hi cap» diu el BPM límit
- **`tempo_map.canvia_bpm_local()`** ja no es limita a «el tram següent quedaria
  massa curt»: calcula i mostra el **BPM més baix que encara hi cap** (baixar el
  BPM allarga el tram i el veí té el final fix). Exemple real (Otis): el clip
  central de 78 compassos no pot baixar de **114,6 BPM** perquè l'últim clip
  (8,5 s) es quedaria a 0,5 s. El comportament seguix refusant el canvi.
- **Tests**: +1 (missatge amb el llindar) → **1.336 OK** (1 skip), pyflakes net.

### Corregit (2026-10-21, 11g) — BPM manual amb el primer i l'últim tram
- **`tempo_map.canvia_bpm_local()`** validava amb el contracte estricte de
  compassos enters: qualsevol **frontera vella fora de graella** (p. ex. un
  marcador a 1,99 s amb compàs de 2 s) bloquejava el canvi de BPM de **qualsevol**
  tram, i el **primer tram** d'un pre-roll podia no tindre cap compàs sencer
  («El tram ha de tindre almenys un compàs»). Ara:
  - usa `_mapa_valida_sense_moure` (la mateixa validació **permissiva** que el
    drag): una frontera heretada no impedix editar el tram;
  - el primer tram que acaba a **mig compàs** conserva eixa fracció i canvia de
    mida; si tot ell és pre-música, només canvia el BPM.
- Reproduït amb el projecte real d'«Otis Redding» (2 trams, frontera a
  1,990315 s): els intents de BPM manual a l'11g donaven «almenys un compàs» i
  «la frontera no cau en una línia de compàs».
- **Tests**: +4 (3 de `tempo_map` i 1 de GUI amb eixe mapa) → **1.335 OK**
  (1 skip), pyflakes net.

### Corregit (2026-10-21, 11f) — el clip d'estructura seguix el marcador
- **`Visor._mou_seccio_amb_marcador()`**: en arrossegar una frontera de
  BPM/compàs, el marcador que hi havia viatja amb ella (ja passava) i ara
  també ho fa el **clip d'estructura** que el `+` va crear en eixe punt: la
  secció de l'esquerra estira la fi i la de la dreta mou l'inici, dins del
  **mateix desfer** i respectant `MIN_SECCIO_S`. El vincle es resol per
  **coincidència de temps** (±5 ms), sense cap identificador nou al projecte:
  si la secció s'edita a mà i deixa de coincidir amb el marcador, deixa de
  seguir-lo.
- Si la secció no hi cap (quedaria buida o fora del seu final), **no es toca**:
  el marcador es mou i el registre n'informa (mai una secció nul·la).
- **Esborrar/fusionar el tram** que s'emporta el marcador **no** fusiona les
  seccions: l'estructura és model d'usuari i es queda com està.
- **Tests**: +3 a `test_gui.TestAncoratgesFinestra` (el gest complet frontera →
  marcador → clip de secció, el seguiment amb etiquetes intactes i el rebuig
  sense espai) → **1.331 OK** (1 skip), pyflakes net.

### Canviat (2026-10-21, 11e) — diàleg, barra i TAP fan **re-tempo local** (deute tancat)
- **`tempo_map.canvia_bpm_local()`** (pur): canvia el BPM/compàs d'un tram
  conservant-li els compassos (`Δt = N · bq · 60 / BPM`) i fent que el **veí
  interior** conserve els seus compassos i el seu final recalculant el BPM.
  **Cap altra frontera es mou** (sense *ripple*). Respecta la pre-música del
  primer tram i, si el veí és **l'últim**, este conserva BPM i fi i absorbeix
  el desplaçament en compassos (excepció §5). Rebutja si no hi cap o si un BPM
  interior ix de `BPM_EDIT_MIN/MAX`.
- **`Visor.edita_tempo_objectiu()`** hi delega: cobrix el **diàleg del tram**
  (`_on_tempo_edit`), els **camps de la barra/transport** i el **TAP**
  (`desa=False`). S'ha acabat el «deute declarat» de l'11c: ja **no queda cap
  camí d'usuari que arrossegue** les fronteres següents.
- **Retirat `tempo_map.canvia_bpm_compassos()`** (l'opció A amb
  `_ripple_des_de`). `snap_frontera_compas`/`_ripple_des_de` es conserven
  només per a `repara_fronteres` (mapes heretats) i l'anàlisi guiat, que creen
  el mapa des de zero.
- **Documentació**: §7 i §13 de `REGLES_TEMPS_GRID.md` ja no parlen de deute
  (diuen què fa `canvia_bpm_local`); `docs/EDICIO_OPERACIONS.md` (paràgraf de
  compassos enters i fila 36) alineats. Les **12 regles d'or** i la regla de
  compassos enters queden intactes.
- **Tests**: +7 → **1.328 OK** (1 skip), pyflakes net. 6 de nous a
  `test_tempo_trams` (veí interior amb BPM recalculat i la resta quieta, veí
  últim que absorbeix, pre-música, rebuig per espai i per BPM, canvi de compàs
  conservant N, últim tram) + 1 a `test_gui` (barra/diàleg = re-tempo local).
  Reescrits els 2 de `test_tempo_map` que fixaven l'opció A amb *ripple*.

### Afegit/Corregit (2026-10-21, 11d) — marcadors i «Detecta» sense bloquejos
- **`+` (marcador) ja no es pot perdre** per una validació de compassos. El
  tram que es tanca naix amb un **nombre enter de compassos** i el BPM derivat
  (`tempo_map.parteix_tram_marcador`); la resta fins al pròxim inici, que **no
  es mou**, ajusta el seu BPM al nombre enter més pròxim. Si el marcador cau
  massa a prop de l'inici per a cap compàs dins de 30–350 BPM (el cas real del
  `+` a 0,4 s durant el play), es conserva el BPM vigent i el tram queda
  pendent d'ajust: **el gest no es bloqueja**.
- **«Detecta» sobre un tram ja no fa *ripple***: `tempo_map.retempo_tram_detectat`
  fixa Δt (les fronteres i els veïns no es mouen), el BPM detectat només tria
  `N` i s'aplica el BPM exacte (`main._detecta_bpm` → `Visor.retempo_tram_detectat`).
- **Acció nova** «Ajusta BPMs a partir dels marcadors per trams»
  (`Visor.ajusta_bpms_marcadors` → `tempo_map.ajusta_trams_a_marcadors`): un
  tram per interval entre marcadors, compassos enters, offset = primer
  marcador, **un sol desfer**.
- **Cap frontera heretada bloqueja ni es mou sola**: `_mapa_valida_sense_moure`
  valida i, si un altre tram arrossega una desviació vella, retorna el mapa
  normalitzat (permissiu). S'elimina el pas per `repara_fronteres` en els
  gestos en viu (marcador, re-tempo, «Detecta», ajust per lot) i a
  `Visor._normalitza_mapa_viu`.
- **Nansa de la frontera de BPM/compàs visible i agarrable**: zona de 8 px a
  cada costat (`TEMPO_GRAB_PX`), nansa dibuixada al `paint` i guia vertical a
  tot el timeline mentre s'arrossega.
- **El diàleg de guiat passa a ser la finestra activa** en obrir-se
  (`showEvent`): els atalls `+`/`−` no es perdien si el visor conservava
  l'activació.
- **Tests**: `tests/test_tempo_trams.py` (marcador amb N enter, offset,
  0,4 s sense bloqueig, «Detecta» sense moure fronteres, ajust per intervals,
  frontera heretada), `tests/test_despatx_edicio.py` (5 proves de visor, un sol
  desfer) i `tests/test_gui.py` (zona de 8 px). Actualitzat el test de
  «Detecta» de `test_pipeline.py` al contracte nou (90 BPM en 2 s de 3/4).

### Canviat (2026-10-21, 11c) — **contracte de temps/graella** alineat amb el re-tempo
- **Canvi de regla amb vistiplau explícit de l'operador** (com exigeix el
  preàmbul de `docs/REGLES_TEMPS_GRID.md`): el document encara descrivia el
  model antic —snap a la graella vella i *ripple*— mentre el codi ja aplicava el
  re-tempo des de l'11b. Es reescriuen **§7, §8 i §9**:
  - **§7 «Canviar el BPM o el compàs d'un tram»**: el re-tempo és **local**.
    El tram conserva els compassos, la seua durada en surt
    (`Δt = N · bq · 60 / BPM`), el **veí recalcula el BPM conservant els
    seus compassos** i **els trams posteriors no es desplacen**. L'últim
    tram segueix acotat per la fi de la WAV; es rebutja si un interior baixa
    d'un compàs, si falta espai (`FRONTERA_MIN_S`) o si el BPM surt de
    `BPM_EDIT_MIN/MAX`.
  - **§8 «Moure o crear fronteres a mà»**: la frontera la col·loca el músic
    (snap normal opcional) i **és la graella que s'ajusta**, recalculant els
    BPMs dels dos costats; la línia de compàs es complix per construcció, no
    per imantació. Els marcadors lligats a la frontera viatgen amb ella.
  - **§9 «Detecció de BPM dins d'un tram»**: en un tram delimitat per marcadors
    **Δt és fix**; el BPM detectat només tria **N**
    (`N = round(Δt · BPM_ref / (bq · 60))`) i s'aplica el BPM derivat exacte.
    **La fi del tram no es mou.**
- **Coherència total del document**: també s'actualitzen el **resum (§12)**,
  que encara deia «arrossega les fronteres», i **§13**, que deia que totes les
  edicions «imanten a la línia de compàs»; ara distingix el re-tempo local, el
  deute declarat del diàleg/transport i l'anàlisi guiat, i afegix
  `tests/test_tempo_trams.py` a la llista de tests del contracte.
- **Deute declarat al document** (no és una excepció del contracte): el
  **diàleg del tram** (`Visor._on_tempo_edit`) i el **transport**
  (`Visor.edita_tempo_objectiu` → `tempo_map.canvia_bpm_compassos`) encara
  apliquen el model vell (fi moguda + `_ripple_des_de`, l'últim absorbeix).
  Queda escrit a §7 i §13 com a únic camí que arrossega, pendent de migrar a
  `mou_frontera_retempo`/`retempo_tram_detectat`. Així el document no menteix
  ni deixa zona grisa: diu què és contracte i què és bug pendent.
- **Intactes**: les **12 regles d'or** (`docs/REGLES_DE_LA_APP.md`) i la **regla
  de compassos enters** (§4). **Cap canvi de codi ni de tests**: només
  documentació (`docs/REGLES_TEMPS_GRID.md` + les referències creuades de
  `docs/README.md` i `docs/EDICIO_OPERACIONS.md` + este `CHANGELOG`).

### Canviat (2026-10-21, 11b) — **re-tempo**: el ratolí mana sobre el temps
- **Arrossegar una frontera de BPM/compàs ja no s'imanta a la línia de compàs
  ni arrossega els trams següents**: la jerarquia del mapa s'inverteix
  (`docs/FLUX DE TEMPO VARIABLE.md` §2) — el punter fixa **Δt**, els
  **compassos N** dels dos costats es conserven i el **BPM** es recalcula
  (`BPM = N · bq · 60 / Δt`). Sempre en línia de compàs per construcció, així
  que `valida_i_normalitza_compassos` no pot bloquejar el gest (era el
  *bloqueig circular* de la §1). Amb l'exemple del document: dos trams de 8
  compassos a 120 BPM (32 s) amb la frontera central a 16 s → arrossegada a
  18 s deixa `106,67` i `137,14` BPM, 8 compassos a cada costat i 32 s de
  cobertura exacta. **Cap altre tram no es mou.**
- **`tempo_map.mou_frontera_retempo()`** (pur): límits de seguretat
  `FRONTERA_MIN_S` (0,5 s) a cada veí, banda `BPM_EDIT_MIN/MAX`
  (30–350 BPM, s'avisa en comptes d'aplicar un absurd), **pre-música** del
  primer tram respectada (compta des de l'`offset`) i últim tram fins a la fi
  de la WAV. `snap_frontera_compas`/`_ripple_des_de` es conserven per al diàleg
  i l'anàlisi guiat.
- **La guia del drag segueix el punter** (§4.B): `_snap_tempo_guia` ja no busca
  la línia de compàs del tram anterior; aplica el **snap normal del timeline**
  (que l'operador pot apagar per a anar-hi lliurement damunt del pic de l'ona).
  El que es veu durant el gest és el que s'aplica en deixar anar.
- **Correcció mètrica discreta** (§4.C): al menú contextual del tram de tempo,
  4 accions noves — **Afegir 1 compàs (+1)**, **Restar 1 compàs (−1)**,
  **Doblar compassos (×2)**, **Dividir compassos (÷2)** — que canvien **N**
  amb els **segons immòbils** (`tempo_map.canvia_compassos_tram`, p. ex. 8 s
  amb 4 compassos a 120 → `+1` = 5 compassos a 150). Passen pel despatx únic
  (`executa_edicio("compassos")`, claus `compas_*`), un sol desfer i cap veí
  tocat. Són **exclusives del carril ③**; la paritat de menús (regla #11)
  passa a declarar-les com a extres.
- **Els marcadors humans viatgen amb la seua frontera** (decisió de
  l'operador, §4.C): si el marcador coincidia amb la frontera moguda, es mou
  amb ella; si la frontera **desapareix** (eliminar el tram o fusionar), el
  marcador **s'esborra**. Tot dins del **mateix** desfer. Abans el docstring de
  `app/marcadors.py` deia el contrari («el marcador és independent»), que és el
  *desacoblament* de la §1.
- **Tests**: `+17` → **1.307 OK** (1 skip), pyflakes net. 11 de nous a
  `test_tempo_trams` (retempo bidireccional amb les xifres del document,
  cobertura exacta, no-bloqueig del validador, no-moure els veïns, límits i
  BPM absurd, pre-música, +1/−1/×2/÷2 i els seus extrems) + 6 a
  `test_despatx_edicio` (les 4 accions pel despatx, claus del menú, desfer,
  selecció, altres carrils, guia del drag) i 1 de fusió amb marcador.
  Actualitzats els 9 que fixaven el comportament vell (snap + ripple).

### Afegit (2026-10-21, 11a) — anàlisi **per etapes** + **velocitat de reproducció**
- **Les 3 etapes es poden activar/desactivar per separat** al diàleg
  *Opcions d'autodetecció*: una casella **«Què s'analitza»** a cada pestanya —
  **BPM** (`_cb_bpm`) · **Acords** (`_cb_acords`) · **Estructura**
  (`_cb_estructura`) — desades a `analisi.bpm` / `analisi.acords` /
  `analisi.estructura` (defecte: totes tres). Substitueix la casella única
  «Només els acords» del 10a.
- **«Analitza» ara també detecta el BPM**: etapa 1 del pipeline
  (`Feina._detecta_bpm` → `pipeline.detecta_bpm`), amb la numeració dels passos
  dinàmica (`1/3`, `2/3`, `3/3`). El tempo detectat s'escriu al camp BPM i
  s'aplica al mapa (`_aplica_bpm_detectat`), **sense tocar-lo si té més d'un
  tram** (s'avisa al log). Abans el BPM només sortia de `🎯 Detecta`.
- Cada etapa desactivada **no s'executa i conserva el que hi ha**: sense BPM es
  manté el tempo del transport; sense acords, el model i el seu CSV; sense
  estructura, les seccions dels marcadors. Log:
  `1/3 BPM: OMÈS (es conserva el del transport)` · `2/3 acords: OMESOS`
  · `3/3 estructura: OMESA`.
- **Selector de velocitat de reproducció 0,5–3× amb el to mantingut**
  (`ffmpeg atempo`, com el VLC; mai `--rate`): desplegable al **transport de la
  finestra** (`cmb_vel_tb`) i al del **visor** (`cmb_vel`), sincronitzats pel
  senyal `velocitatCanviada`. El PCM estirat es renderitza **una vegada per
  factor** (`ffmpeg.prepara_escolta`, caché per mtime+mida+factor) i es queda a
  `_vel_cache` (màxim 2 factors simultanis a memòria); els WAV temporals van a
  la **paperera** en tancar el visor.
- **Cursor, loop i metrònom es mantenen alineats a qualsevol velocitat**: el
  fil d'alimentació llig el buffer a `pos × factor` (posicions sempre en
  **mostres de cançó**), el rellotge del cursor multiplica pel factor
  (`_tiquet`) i `metronom.mescla_metronom` guanya el paràmetre `factor`
  (al final, per no trencar les crides posicionals) que col·loca els clics a
  `t/factor`. Canviar de velocitat **no mou el cursor**: es reprèn exactament
  al mateix punt de la cançó.
- **Tests**: `+17` des de l'última tongada — 7 de **velocitat** (sincronia dels
  dos selectors, el de la barra → el visor, 1×, rellotge × factor, sense
  `ffmpeg`, paperera), 3 de **recorregut complet del fil d'àudio** a 1× / ½ /
  2× (el buffer estirat es llig amb l'índex `pos/factor`; sense això es
  quedava a mig camí), 3 del **`factor`** del metrònom a `test_tempo_map`, 3
  del **diàleg/`Feina`** (les 3 caselles, «Analitza» detecta el BPM, etapa
  d'acords OFF conserva el CSV) i 1 de la tongada 10a que encara no s'havia
  comptat. Suite **1.290 OK** (1 skip), pyflakes net. Comprovat a més **en
  viu** amb ffmpeg real: 128 BPM detectats (127,75) i el fil d'àudio recorre
  la cançó sencera a 1× / 1,5× / 2× / ½×.

### Afegit (2026-10-21, 4a) — Anàlisi guiat **v3**: ancoratges (F1–F3)
- **Nucli d'encaix** `app/ancoratges.py` (pur, sense Qt): donats els ancoratges
  humans (`t`, `num`, `den`) deriva el BPM de cada interval (`n` compassos
  enters dins d'un rang) i retorna el mapa que passa **exactament** pels punts
  (+ «cap» absorbit per l'`offset` i «cua» allargada amb l'últim BPM). Estats
  `ok/nota/sospitos/no_encaixa/sense_referencia/massa_curt/manual` i llindars
  editables (1 % / 3 % / 10 % per defecte). 42 tests.
- **Velocitat amb to mantingut** (`ffmpeg.estira_a_wav`, `VELOCITATS`,
  `cadena_atempo`, caché per mtime+mida+factor a PCM mono): a ½ el fitxer dura
  el doble i ``t_real = t_estirat × factor``. `atempo` encadenat per a factors
  extrems. Mai `--rate` (canviaria el to).
- **Finestra `DialegAncoratges`** (`app/dialeg_ancoratges.py`): **+** = ancoratge
  (inici de compàs **i** de secció) amb metre i delay aplicats; transport amb
  ▶/⏸ i **½ · ⅔ (÷1,5) · 1 · 1,5 · 2 · 4** (tecles 1…6); llista inversa amb `→`
  (salt) i `×` (esborrar); `↶ Desfés`
  amb pila (afegir → cursor 2 s enrere i pausa); llindars i `N ≤` a la pròpia
  finestra amb validació creixent; tecles `+` (**el de dalt i el del teclat
  numèric**; atall de finestra → funciona amb qualsevol focus), `Espai`,
  `Ctrl+Z`, `1…6` — les **fletxes no fan res** (donaven problemes);
  els temporals van a la paperera en tancar.
- **Aplicació en un sol desfer**: `main._aplica_ancoratges` valida amb
  `tempo_map.valida_i_normalitza_compassos` (si no quadra, no toca res) i
  aplica **offset + trams** junts. El botó «Anàlisi guiat» obri la v3; la v2
  queda al menú **Analitza** com a eina de reparació.
- **Integració amb el visor (R21)**: mentre sona el diàleg, el **cursor del
  visor avança en directe** (línia, regla de temps, barra lliscant i
  desplaçament de la vista) i l'audició **arrenca on hi ha el cursor**. Abans el
  diàleg era un món aïllat: s'hi punxava a cegues.
- **Spec**: `docs/ANALISI_GUIAT_v3.md` (R1–R20, mockup, pla F1–F5) i capçalera
  de llegat a `docs/ANALISI_GUIAT.md`.

### Afegit (2026-10-21, 10a) — analitzar **només els acords** (sense estructura)
- **Casella «Només els acords (no detectar l'estructura)»** dalt de la pestanya
  *Acords* d'*Opcions d'autodetecció*: només passa Chordino i **conserva les
  seccions** que ja tens (les dels marcadors); no passa el qm-segmenter ni
  reescriu l'ABC. Es recorda a `opcions_detecta.json` → `analisi.estructura`.
- **Acció nova** *Analitza ▸ Analitza només els acords…* (**F6**), que força
  eixa opció. La casella i l'acció *Inclou estructura* són **un sol estat**
  (es sincronitzen; abans el toggle del menú no es desava).
- Al log: `2/3 estructura: OMESA (es conserva la que hi ha)`.

### Afegit (2026-10-21, 9a) — **BPM a partir dels marcadors** (clips editables)
- `marcadors.candidats_bpm()`: busca els BPM que fan que **tots** els intervals
  entre marcadors siguen compassos sencers (error en **segons**, amb preferència
  suau pel rang 70–160 per a desfer el doble/meitat) i torna una llista.
- *Analitza ▸ BPM a partir dels marcadors…* (`DialegBpmMarcadors`): tries el
  candidat (es mostra quants compassos té cada tram) i s'escriu el mapa amb
  `k` compassos exactes per interval → **les fronteres cauen en línia de compàs
  i els clips de tempo/compàs tornen a ser editables**. Un sol desfer. L'offset
  passa a ser el primer marcador.
- **Diagnosi del «no puc editar»**: els marcadors creaven fronteres que no eren
  línies de compàs (el BPM de la barra encara no era el bo), i el contracte de
  compassos enters les rebutjava. Amb el BPM deduït, el mapa és consistent.

### Afegit (2026-10-21, 8a) — **MARCADORS en viu** (+ marker) i guiat en stand by
- **Marcadors humans** (`app/marcadors.py` + `Visor.afegeix_marcador`):
  la tecla **`+`** (de dalt o del teclat numèric) o el botó **＋ Marker** marquen
  un **inici de compàs** en el punt del cursor, **també mentre sona**. Un sol
  desfer ho desfà. Es pinten com a **ratlles grogues discontínues** damunt del
  visor (`MarcadorsLayer`).
- En crear-se, un marcador **talla dos carrils**: comença un clip de
  **BPM/compàs** i un d'**estructura** en eixe instant. Després el marcador és
  **independent** dels clips (si els mous o els esborres, es queda on era).
- Es guarden a `marcadors.csv` del projecte; *Analitza ▸ Esborra l'últim
  marcador* i `Ctrl+Z`.
- **`+` no roba la tecla** si estas escrivint en un camp (nom d'acord, BPM…):
  va per un filtre d'esdeveniments, no per un `QShortcut`.
- **«Anàlisi guiat» passa a guia** (`app/dialeg_guia_rapida.py`): 5 pantalles
  d'informació (obrir àudio → escoltar i marcar → què fa un marcador → ajustar
  BPM/compàs → acords i exportar). **No toca el model**.
- **Guiat v2 (per trams) i v3 (ancoratges): EN STAND BY** — el codi queda, però
  no tenen entrada d'UI (el diàleg v3 era modal i impedia moure el cursor del
  visor; eixa era la queixa). Docs: `docs/MARCADORS.md`.

### Afegit (2026-10-21, 7a) — dos marcs (offset + rang de BPM) i voreres que es mouen
- **①② marcs obligatoris** al diàleg: *Marca el compàs 1* (offset + primer
  ancoratge) i *Marca el compàs 2* (o un de posterior, amb «compassos entre»).
  D'allí ix el **BPM aproximat** i el **rang ±10 %** que descarta el doble o la
  meitat; sense els dos marcs, «Genera» està desactivat i el diàleg diu per què.
  El marge i els compassos entre marcs es desen a les opcions.
- **Arrossegar les voreres de tempo**: ara mana el **sentit del gest** (dreta →
  següent línia de compàs; esquerra → anterior). Abans, mig compàs de moviment
  s'imantava a la mateixa línia i pareixia que el clip no es podia moure.

### Afegit (2026-10-21, 6a) — v3 completa: seccions, ×2/÷2 i detecció puntual
- **Seccions automàtiques**: `ancoratges.seccions_de_ancoratges` crea **un clip
  d'estructura per interval** (A, B, C…) i una secció **«Intro»** per al cap.
  `Visor.aplica_ancoratges` aplica **offset + mapa + seccions en un sol
  desfer** (també regenera l'ABC i desa l'offset al `.acproj`; abans, en
  reobrir el projecte la graella tornava a compàs 1 = 0).
- **×2 / ÷2 per interval** al diàleg: força el nombre de compassos (`n_manual`)
  i recalcula; els ancoratges no es toquen.
- **Detecció de BPM per interval, només on fa falta**: si algun interval no
  encaixa, el diàleg demana la detecció **només d'eixos** i l'accepta només si
  l'encaix **millora** (cost acotat).
- **Cursor del visor en directe** mentre sona el diàleg (R21) i l'audició
  arranca **on és el cursor**.

### Arreglat (2026-10-21, 6a) — editar els trams de tempo després del guiat
- **«No puc editar clips de temps/compàs»** (reportat per l'operador): després
  d'aplicar ancoratges, **eliminar/fusionar/duplicar** un tram fallava amb
  «La frontera 30.378667s no cau en una línia de compàs» — la frontera quedava
  a mil·lèsimes de la graella. Nou `tempo_map.repara_fronteres`: imanta la
  frontera més desviada a la línia de compàs i arrossega les següents
  (`snap_frontera_compas`) abans de rebutjar. També s'aplica al `duplica`.

### Arreglat (2026-10-21, 5a) — el «+» del teclat numèric i l'encaix amb BPM global
- **«+» del teclat numèric**: a més del de dalt (Maj+`=`), ara és un **atall de
  finestra** (`QShortcut`) → funciona amb `Qt.Key_Plus` ± `KeypadModifier` i
  **encara que el focus siga a un camp** (un `QLineEdit` s'empassava la tecla).
- **`encaix NO` en un tema a ~100 BPM** (cas real del log): el primer interval
  es rebutjava per allunyar-se del **BPM de la barra (120 = valor per defecte)**.
  Ara la referència global només **informa** (`nota`); el primer interval
  estableix el tempo i la cadena mana a partir del segon. El missatge d'error
  diu **quin** interval falla (temps) i **per què**.

### Pendent (v3)
- Detecció de BPM **per interval** (ara mana `bpm_ref`), **seccions
  automàtiques**, `×2/÷2` + salt al diàleg per tram des de la llista de
  sospitosos i avís no modal amb el resum.

### Afegit (2026-10-21, 3a) — mida del tram, doble comprovació i BPM anterior
- **Mida del tram configurable**: **4 · 8 · 16 · 32 compassos** (abans era una
  constant 4 al codi). Es tria al **pas 1** (val per a tot el guiat i es
  **recorda** a `opcions_detecta.json` → `guiat.compassos`) i es pot canviar a
  cada tram des del combo «Tram:» del diàleg; la tria passa a les finestres
  següents. Deriva la **finestra de mesura** (`m · durada_compas`), el tall i
  el bucle d'audició → trams llargs = mesura més estable; curts = més punts
  per a un rubato.
- **Doble comprovació de la detecció** (`guiat.confirma`, marcada per defecte):
  dues mesures extra del mateix tram — (a) la finestra **acotada al ±8 % del
  BPM del tram anterior** i (b) la detecció sobre el **doble de tros**.
  `tempo_map.avalua_confirmacio` les creua i el diàleg diu **✓ fiable** o
  **⚠ dubtós** amb els tres números i una ✗ al que discrepa; si la detecció
  lliure falla, s'usa el número del reforç. És la resposta als errors de
  meitat/doble tempo (51,70 en compte de 103,40).
- **BPM dels trams anteriors**: pastilles amb els **dos últims** BPM
  confirmats («tram 3 · 103.40») que omplin el camp d'un clic; l'últim entra
  com a prior de la comprovació acotada.
- **Tecla `0` = TAP** al diàleg del guiat (a més de `T`).
- **Fix**: desar des d'*Opcions* ja **no esborra** les seccions que eixe diàleg
  no edita (es perdia `guiat`); `opcions()` les conserva.
- **Fix**: el combo de mida es podia quedar «enganxat» a 32 en llevar-li
  l'element temporal (`removeItem` de l'actual emetia `currentIndexChanged`
  amb el valor del veí).

### Afegit (2026-10-21, 2a) — el guiat com a estació d'audició
- **El tram sona amb metrònom** en rebre el BPM (detecció o TAP): bucle
  `[t_k, t_k + m·compàs]` + **metrònom forçat** (`Visor.set_metro_forcat`)
  que **ignora el mapa** i segueix el BPM proposat. Canviar el BPM al camp
  mou el clic **a l'instant** (el fil de farciment el relliga cada ~0,7 s:
  sense reiniciar l'àudio ni micro-talls).
- **Mètrica i llargada al diàleg del tram**: desplegable **4/4 · 3/4 · 2/4 ·
  6/8 · 12/8** (+ la vigent) i **−/+ de compassos (1…32)**. Abans la finestra
  comptava **16 temps** i en 3/4 eixien **5 compassos** (`round(16/3)`) en
  compte de 4 — **bug arreglat** amb `trams_finestra_guia(n_compassos=…)`
  (el paràmetre `beats` es conserva per compatibilitat).
- **TAP dins el diàleg** (tecla **T** o botó): 2–6 cops, mediana dels
  intervals i reinici si passes > 2,5 s. **Espai** = play/pausa del tram.
  Les tecles no s'activen mentre s'escriu al camp del BPM.
- **El loop de l'usuari no es contamina**: la mesura usa sempre la
  instantània feta en arrencar (`_guia["loop"]`) i el loop del visor passa
  a ser l'interval d'audició; en aplicar/acabar/cancel·lar es **restaura**
  el loop de l'usuari (`_guia["loop_usuari"]`) i el metrònom.
- **Avís final no modal** (caixa d'informació del visor) en consolidar el
  mapa, en compte d'un diàleg que interromp.
- **Bug cosmètic arreglat**: el desplegable de mètrica afegia un «4/4»
  duplicat (`findData` amb una tupla no casa mai a PyQt5 → es compara per
  text).

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
