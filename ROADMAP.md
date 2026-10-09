# Full de ruta — PROJECTE AUTO CHORDS

> Eina per a **músics multi-DAW** que analitza una cançó (WAV), en deixa
> **editar visualment** els acords i l'estructura com si fos una pista, i
> n'exporta el resultat com a **clips d'àudio llestos per arrossegar a
> qualsevol DAW** (Live, Reaper, Logic, Bitwig, Studio One, Pro Tools,
> Cubase…). Tot en català. Llicència: GPLv3.

## Filosofia — Per què clips WAV silenciosos?

La solució de **un fitxer WAV per acord/estructura** és enginyosa i
universal, i és la **raó de ser** d'aquest projecte:

- 🎯 **Nom = acord**: `1-1-1_Am.wav` → el clip es llegeix com “Am” al DAW.
- 📏 **Durada = durada de l’acord**: cada WAV té exactament la longitud de
  l’acord o secció que representa → de manera que un cop arrossegats al
  DAW, els clips es col·loquen un darrera l’altre i dibuixen la
  **progressió completa de la cançó**.
- 🔌 **Zero plugins especials**: qualsevol DAW sap arrossegar una carpeta
  d’àudio → funciona arreu sense coneixements de MIDI, VSTs, scripts o
  fluxos nous.
- ✂️ **Editable al DAW**: un cop els clips són allà, pots moure’ls,
  tallar-los, duplicar-los, dividir-los, afegir-ne de nous, etc.
- 🎼 **Doble pista al DAW**: `wavs_acords/` (un clip per acord) +
  `wavs_estructura/` (un clip per secció) → pots posar-les com a dues
  pistes sincronitzades (una d’acords, una d’estructura).

> **Conclusió**: el que exportem **NO** és audio. És una **pista visual
> de noms i durades** que qualsevol DAW pot consumir amb el seu propi
> sistema de clips. La solució és deliberadament simple — i per això
> funciona.

## Cas d’ús principal

1. 🎵 L’usuari tria una cançó (WAV).
2. 🪄 L’app la processa amb **Chordino** (acords) i **qm-segmenter**
   (estructura) → resultat semiautomàtic.
3. ✏️ L’usuari **edita visualment** els acords i l’estructura amb un
   visor DAW-like (drag, resize, snap, rename).
4. 📦 L’app exporta dues carpetes: `wavs_acords/` + `wavs_estructura/`
   amb noms ordenables i durades correctes.
5. 🎚️ L’usuari **arrossega les carpetes al seu DAW** → obté una pista
   visual d’acords i una d’estructura, sincronitzades, editables.

**Multi-DAW**: la solució és inherentment portable perquè **no depèn**
de cap DAW concret. Live, Reaper, Logic, Bitwig, Studio One, Pro Tools,
Cubase, GarageBand — tots consumeixen WAVs amb nom.

## Obertura tecnolítica

El **core del projecte** (detecció amb Chordino + qm-segmenter, validació
temporal, export WAVs amb noms intel·ligents) és estable i **independent
de la interfície**. 

L’**embolcall** (la GUI / el visor) pot canviar-se sense tocar el core.
Això ens permet estar oberts a:

- **PyQt5/QGraphicsView** (estat actual) — natiu, madur, però específic de
  Qt.
- **Electron + wavesurfer.js** — multiplataforma web (Chromium embebut).
- **Tauri + wavesurfer.js** — més lleuger que Electron (WebView natiu).
- **HTML/web (PWA)** — només si no calgui la integració amb el sistema.
- **Altres** — qualsevol que ens doni la millor experiència d’usuari.

> La tria tecnolítica **és intercanviable** mentre es preservi:
> - El **core** (pipeline.py i la integració amb `sonic-annotator`).
> - La **invariant de dades** (ordre estrictes, no solapaments, durades
>    derivades).
> - La **UX esperada** (visor DAW-like, edició semiautomàtica, drag/resize,
>    snap, propagació de constraint).

**Restriccions conegudes**:
- 🖥️ **Q9400 (CPU sense AVX2)**: alguns binaris moderns (numpy 2.x,
  Electron recent, Qt6) **no funcionaran**. Cal verificar la compatibilitat
  ABANS d’escollir una tecnologia.
- 🔒 **Sense secrets** al repo (`.secrets/` ignorat per `.gitignore`).
- 🐧 **Linux** prioritari (AppImage) i, com a producte, **multi-SO**: Windows x64 + macOS 10.13+.

## Estat actual (2026-10-08 · v0.5.1)

El projecte ja ha passat de prototip funcional a flux de producte útil:

- app principal única i estable
- **visor DAW-like (QGraphicsView)** amb ona, ruler BPM/segons i 2 carrils (acords + estructura)
- **constraint propagation live** — moure l’inici d’un element ajusta automàticament el final de l’anterior i l’inici del següent
- **nanses de resize** als extrems dels acords i les seccions + cos central per moure’l sencer
- **rename inline** (doble-clic → edició al lloc, Enter desa, Esc cancel·la)
- **snap intel·ligent** a compàs/beat/corxera (tempo_fix) o a 0.1/0.5/1/5 s (mode lliure) segons el zoom
- **zoom** amb Ctrl+Roda (centrat al cursor) i **pan** amb Roda sola
- procés d’anàlisi amb una sola acció clara (`Analitza`, F5)
- revisió i edició d’acords i seccions des del visor
- export final separat i explícit (`Exporta`, Ctrl+E)
- llançament directe des de la carpeta del projecte
- bloqueig de doble instància per evitar sobreposició d’aplicacions
- **auditoria de seguretat/estabilitat aplicada**: clamp de temps, tipus d’excepció específics, `_proc_lock`, `safe_filename`, parser CSV robust, validació WAV (sr/ch > 0)

**Novetats v0.3.0–v0.5.1 (2026-10-08):**

- **Multi-SO (v0.5.1)**: **Windows x64** i **macOS 10.13+** (Intel) via GitHub
  Actions — host i plugins **compilats al runner** de cada SO; **els 3 builds
  verds**. Detall: `docs/ESTAT_MULTI_SO.md`.
- **Autocontingut i portable**: **AppImage** (~160 MB, runtime estàtic → sense
  `libfuse2`), **host Vamp propi**, **CPython portable** (sense AVX) i ffmpeg
  estàtic. **GitHub Actions**: build manual + Release automàtic en tag.
- **Icones professionals (Lucide)** en comptes d'emoji + **icona d'app**.
- **Info box**: ratolí intel·ligent del visor + desfer/refer.

- **Autodetecció amb opcions**: diàleg (BPM / Acords / Estructura) amb els
  **paràmetres reals del Chordino** (llegits dels descriptors `.n3`) i
  **neteja posterior** dels acords (treure baix, reduir, fusionar, durada
  mínima, snap a la graella).
- **Motors triables**: BPM = `nostre` (tempo.py) · `qm` · **`consens`**;
  Estructura = **`qm-segmenter`** (únic; el Segmentino i l'aubio es van retirar).
- **Plugins Queen Mary compilats** (`qm-tempotracker`, `qm-barbeattracker`,
  `qm-segmenter`, `qm-keydetector`) sense AVX → `docs/QM_VAMP.md`.
- **Compàs 1 automàtic** (`🧭`): `qm-onsetdetector` + `qm-barbeattracker`.
- **Import d'altres formats** (mp3, aif, flac, m4a…) via **ffmpeg**.
- **GUI**: tap tempo (`TAP`/`T`), botó `📍`, `×2`/`÷2` del BPM, franja
  **Editor**, menús Edita/Selecciona, paleta de botons coherent, icona
  play/pause.
- **Coherència del play**: mono cacat, **volum/mute en viu**, latència baixa,
  sense tallar la cua, avís si el reproductor mor.
- **210 tests** (OK, 1 skip) — abans 82.

La base funcional i el nou visor estan validats. El que queda són millores de polish, estabilització i les funcionalitats pràctiques descrites a l’apartat següent.

### Deute tècnic tancat (2026-10-08)

- **Docs al dia**: el visor standalone es documenta com **`python -m app.visor`**
  (el `python app/visor.py` directe fallava per imports relatius); recompte de
  tests actualitzat; `ROADMAP` Fase D → D.1 ✅.
- **`pyflakes` net** a `app/` i `eines/` (imports/variables morts trets).
- **Excepcions** de `app/visor.py` i `app/main.py` revisades (cap canvi de
  comportament; política documentada; fallbacks calents anotats).
- **`concatena.py`** inclou `tests/` (47 fitxers · ~594 KB).

### Pendents (2026-10-08)

- **Proves manuals** (operador): `./AUTO_CHORDS.sh` (obrir WAV → Analitza →
  editar acord → Exporta); `python -m app.visor <wav>` (standalone); **metrònom**
  amb offset posat amb 📍 o 🧭.
- **Tag de retorn** `v0.5.2-deute` (⚠️ `release.yml` s’activa amb tags `v*`;
  alternativa: tag sense `v`).
- **Re-provar els builds** de Windows i macOS a GitHub Actions.
- **Fase D.2** (multi-selecció, copiar/enganxar): **partir `timeline.py`** abans
  de tocar-lo (≈1.777 línies).

## Fase A — Visor navegable ✅

- ona, cursor i navegació per temps
- play/stop, loop A-B, zoom i temps en compàs/segons segons el mode
- estructura i acords visibles a la mateixa interfície
- llista d’acords i llista d’estructura operatives
- validació del dock/visor integrat

## Fase B — Edició i correcció ✅

1. **Corregir acord** ✅
   - doble-clic a un acord per editar-ne la nota
   - regenera els `wavs_acords/` sense re-analitzar

2. **Partir / fusionar / eliminar secció** ✅
   - menú contextual sobre la llista ABC
   - regen de `estructura_ABC.csv` i `wavs_estructura/`

3. **Afegir / eliminar acords i seccions** ✅
   - possibilitat d’editar el dataset manualment des del visor
   - regeneració immediata del resultat exportable

4. **Noms `music21`** ✅
   - normalització d’arrel, qualitat i baix/inversió
   - criteri: `G/D`, `Cmaj7`, `Am` estables

## Fase C — Flux producte ✅

- app única des de la qual s’analitza i es revisa el resultat
- export final clar i separat del processament
- llançador directe (`AUTO_CHORDS.sh` / `AUTO_CHORDS.desktop`)
- sorteix sense dependre de terminal ni de múltiples finestres

## Fase D — Interacció DAW-like ✅ *(D.1 FET 2026-10-06; D.2 FET 2026-10-09; D.3 en curs)*

Aquesta fase és **el “kit de la qüestió”** del projecte: fer que el visor
interactiu sigui tan usable i natural com un DAW modern treballant amb
clips d’àudio. La detecció i l’export ja funcionen; ara toca que **editar
sigui un plaer** i no una fricció.

**Regla d’or** (ja implementada): cada clip d’acord o d’estructura
**sempre acaba o comença el següent** — és a dir, el final d’un element
és l’inici del veí (propagació de constraint en temps real).

### D.1 — Crítiques ✅ *(FET 2026-10-06)*

> ✅ **FET (2026-10-06)**: clic a un clip mou el cursor · `Delete` elimina
> l'element seleccionat (amb undo) · `Ctrl+D` duplica (repartint la durada,
> amb undo) · distinció visual **seleccionat** (vora cian gruixuda) vs
> **actiu** (fons verd) amb els colors a `app/theme.py` · **menú contextual**
> (botó dret) sobre un clip amb Duplica/Elimina/Reanomena. També s'ha afegit
> un **metrònom** (🥁, només mode BPM · compàs, volum propi) i la **GUI
> reorganitzada** amb el timeline al centre.

- ✅ **Click a un clip → mou cursor de play allà**.
- ✅ **Selecció persistent visual** — seleccionat vs actiu amb colors propis (`app/theme.py`).
- ✅ **Duplicar acord/estructura** — `Ctrl+D` o menú contextual (propaga el constraint).
- ✅ **Eliminar amb tecla `Delete`** (a més del menú contextual existent).
- **Línia guia de snap més visible** durant el drag (pendent de polir).
- **Feedback visual quan s’arrossega** — el cursor canvia segons la zona
  (parcialment fet) + highlight dels veïns afectats.

### D.2 — Importants ✅ *(FET 2026-10-09)*

> ✅ **FET (2026-10-09)**: **multi-selecció** (`Ctrl+clic` afegir/treure,
> `Shift+clic` rang) · **eliminar el grup** (un sol undo) · **porta-retalls intern**
> (`Ctrl+C`/`Ctrl+X`/`Ctrl+V`, valida abans d'aplicar) · **`Ctrl+D` de grup** ·
> **moure el grup** (arrossegar un clip seleccionat) · **indicador de MODE** al
> regle (`120 BPM · 4/4` / `Lliure`). Detall: `CHANGELOG` [0.5.2] i
> `docs/ESQUEMA_UI.*`. L'**Undo/Redo** ja hi era (v0.1.5).

- ✅ **Multi-selecció** amb `Ctrl+click` (afegir) i `Shift+click` (rang), i
  poder moure/duplicar/eliminar el grup.
- ✅ **Dreceres de teclat estàndard**: `Ctrl+C/V/X` (copy/cut/paste),
  `Ctrl+D` (duplicar), `Ctrl+Z/Y` (desfer/refer), `Delete` (eliminar),
  `Space` (play/pause), `Enter` (editar).
- ✅ **Undo/Redo** amb stack d’accions (cobreix qualsevol modificació manual).
- ⏳ **Scroll drag amb mouse** per desplaçar-se horitzontalment quan el
  cursor agafa la forma de “mà” (com Reaper) — el **pan amb botó dret** ja hi
  és; falta el mode “mà” (resta menor).
- ✅ **Indicador visual del mode actiu** (BPM/compàs vs segons) al ruler.

### D.3 — Nice-to-have (quan la D.1 i D.2 estiguin consolidades)

- **Drag-and-drop extern** d’un WAV per afegir manualment un acord nou.
- **Tooltips** sobre botons i accions (a més dels que ja existeixen).
- **Selecció amb drag-rectangle** (“lasso”) per seleccionar varis elements
  d’un cop.
- **Accel·leradors personalitzables** per l’usuari avançat.

### Coherència del snap — loop A/B i cursor *(pendent · per decidir)*

> 🔍 **Revisió de codi (2026-10-09, OC-3)** — `app/timeline.py`. Dins el visor
> hi conviuen **dos comportaments**: els **clips** (acords/estructures) SÍ que
> fan snap a la graella, però el **loop A/B** i el **cursor/playhead** són
> **lliures**.

- **Loop A/B sense snap.** La selecció al regle (`mousePressEvent` /
  `mouseMoveEvent`, ~línies 1036-1043 / 1088-1094 de `timeline.py`) i els
  botons A/B (`marca_A` / `marca_B`, `app/visor.py`) fan servir el temps
  continu de `_x_to_time()` → **no criden mai `snap_time`**.
- **Cursor sense snap.** `set_position()` (~297-305) no arrodoneix mai: totes
  les vies (clic al fons, lliscador, `±10 s`, editar l’etiqueta de posició) hi
  posen temps continu. Única excepció: clicar un clip situa el cursor al seu
  inici (snap *al clip*, no a la graella).
- **A decidir.** Si ha de ser **snap a graella** (coherent amb els clips i amb
  l’exportació, respectant l’**offset**) o bé **lliure** per a navegació fina
  — o una opció **commutable** per a tots dos.

### Notes d’implementació

- Tot canvi de la Fase D **ha de preservar**:
  - La **invariant de dades** (ordre estrictes, no solapaments, durades
    derivades).
  - El **principi d’una sola font de veritat** (`app.pipeline` continua
    sent el backend; el visor en reflecteix l’estat).
  - La **regla d’or** del final = inici del següent (constraint live).
- Si la base tecnolítica canvia (veure §“Obertura tecnolítica”), les
  funcionalitats de la Fase D s’han de **reimplementar** sobre la nova
  plataforma — però els **principis romanen**.
- Cada feature nova porta **tests** (al manco un test d’smoke i un
  unittest quan sigui possible).

## Fase E — Autodetecció avançada (Queen Mary) ✅ *(v0.4.0)*

- **Plugins compilats** (`qm-vamp-plugins-linux64-local/`): `qm-tempotracker`,
  `qm-barbeattracker`, `qm-segmenter`, `qm-keydetector` (els d'Audacity /
  Mixxx / Sonic Visualiser). Compilats de codi font amb `-msse -msse2`
  (⚠️ **sense AVX**). Detall i comparativa: `docs/QM_VAMP.md`.
- **Compàs 1 automàtic** (`🧭` + `Analitza ▸ Detecta el compàs 1`).
- **Motors triables** al diàleg (BPM + estructura).
- **BPM**: prior de plateau (85–150, σ0,5) que resol l'ambigüitat d'octava
  (casos reals: Otis 179,8→103,5 · Chemical 66→132 · Jamiroquai 174→87).
- Eines: `eines/explica_bpm.py` (gràfic).

**Pendent d'aquesta fase:**
- **`qm-keydetector`** → detectar i mostrar la **tonalitat** del tema.
- **Beats/bars a la graella**: usar els beats del qm per afinar/auto-ajustar
  la graella (ara només s'usa el primer downbeat).
- Afinar el **qm-segmenter** (conservar les seves etiquetes de repetició A…A
  directament, en lloc de re-letrar).

## Prioritat de millores restants

### Alta
- **confiança dels acords** (`loglikelihood` del Chordino) → ressaltar a la
  UI els acords dubtosos perquè l’usuari els revisi (ja tenim l’eina; vegeu
  `docs/AUTODETECCIO_OPCIONS.md` §2)
- **tonalitat** (`qm-keydetector`) → mostrar-la (Fase E)
- **overflow de les barres d’eines** a <1300 px (ara les barres es tallen)
- **afegir clips des del timeline** (ara només es poden crear des del menú
  de la llista)
- packaging més net i docs d’ús final

### Mitjana
- ~~historial d’edicions / desfer~~ ✅ **(fet v0.1.5: undo/redo + menú Edita)**
- ~~diàleg d’opcions de l’autodetecció~~ ✅ **(fet v0.3.0–v0.4.0)**
- ~~import d’altres formats d’àudio~~ ✅ **(fet v0.3.0: ffmpeg)**
- **conservar les etiquetes de repetició del qm-segmenter** (Fase E)
- els **beats** del qm per auto-ajustar la graella (Fase E)
- validacions visuals addicionals de l’ABC
- **la suite de tests no esborra els seus `tempdir`** (s’acumulen a `/tmp`)

### Baixa
- suport d’altres formats de sortida
- configuració persistents d’usuari (ara només `opcions_detecta.json`)
- mostrar les **notes de l’acord** (`chordnotes` del Chordino) a l’Editor

## Àrees de futur: investigar, valorar i discutir

Aquestes són idees i oportunitats que queden pendents de revisió i que convé gestionar com a feina de producte i d’arquitectura, no com a correccions urgents del flux principal.

### 1) Compassos amb 3 xifres i formats de temps avançats

- investigar com es representarà correctament la estructura en compàs amb notació de 3 xifres, per exemple `1.1.3` o `1.1.50`
- definir si el format és estrictament de visualització o si també entra dins el CSV de referència
- valorar si la codificació del compàs ha de tenir un esquema explícit separant `compàs`, `beat` i `subdivisió`
- decidir si l’editor ha de mostrar sempre “segons” o “compàs” o si ha d’haver un mode dual amb canvi contextual
- garantir que aquesta representació no trenqui el model que ja usa temps en segons com a font de veritat

### 2) Control del processament automàtic i paràmetres d’algoritme

> ✅ **IMPLEMENTAT (v0.3.0–v0.4.0)**: diàleg d’opcions amb els **6 paràmetres
> reals del Chordino** (llegits dels `.n3`), **neteja posterior** dels acords,
> **motors triables** (BPM i estructura) i opcions de BPM/estructura. Vegeu
> `docs/AUTODETECCIO_OPCIONS.md` i `docs/QM_VAMP.md`.

- revisar si `Chordino`, `Segmentino` i els scripts de suport exposen opcions reals de sensibilitat, llindars, auto-generació o ajust d’algoritme
- valorar la introducció d’una finestra de configuració avançada per a:
  - sensibilitat de detecció
  - llindar de confiança d’acords
  - detecció d’estructura i divisió de seccions
  - auto-generació de dades de referència
- decidir si el procés automàtic es manté “simple” per defecte i s’obre un mode expert quan calgui
- documentar clarament què és paramètric i què és resultat “fix”, per evitar la confusió entre dades analitzades i dades editades

### 3) Tema de colors i estètica visual

- millorar el tema global per a una paleta més coherent i menys agressiva
- comprovar si cal un tema “fosc” però amb menys intensitat i més contrast estable
- definir si la UI ha de tenir:
  - colors per categoria (acords, seccions, focus, cursor)
  - paleta mínima i legible
  - contrast calibrat per a treball llarg
- decidir si la gamma de colors forma part de l’arquitectura de tema centralitzat o si s’ha de mantenir en un sistema de variables CSS

### 4) Gràfica i visualització de temps

- millorar la representació visual perquè sigui clar veure la línea temporal en segons i en BPM/compàs
- valorar si la gràfica de l’ona ha de mostrar overlays amb indicadors de compàs, seccions i transicions
- decidir si la visualització ha de tenir un mode “temps real” i un mode “compàs” en paralelo
- revisar si hi ha necessitat d’afegir una etiqueta, una regla o un cursor de forma més clara a la UI

### 5) Auditoria de seguretat i robustesa

- revisar els punts d’entrada de fitxers, paths i execucions externes per fer un control més estricte
- auditar:
  - càrrega de WAVs i CSVs
  - execució de subprocessos
  - paths d’exportació
  - manejo de fitxers temporals
  - logs i processos no autoritzats
- valorar si cal una política de validació de ruta i noms, i si cal evitar l’execució de binaris fora de directoris controlats
- preparar una política d’errors i de registre per a producció, sense exposar informació sensible o innecessària

### 6) Nomenclatura de fitxers i convenis d’export

- revisar com es nomenen els WAVs finals i com s’ordenen a la carpeta de sortida
- buscar una regla clara per a:
  - acords
  - parts o seccions
  - clips derivats d’intervals
- que els noms siguin “ordenables” i “legibles” i que el prefixedel text estigui el més a prop possible de l’inici del nom
- definir si el nom és una etiqueta semàntica, temporal, de secció o de versió, i no barrejar totes les idees en un mateix string

### 7) Altres exportacions i formats de partitura

> ✅ **FET (2026-10-07)** — **export de partitura (xifrat)**: `app/partitura.py`
> converteix `acords_locators.txt` + `estructura_ABC.csv` a **MusicXML** i, si
> hi ha **MuseScore** (4.6.x; ⚠️ 4.7+ demana SSE4.2+POPCNT i **no** va al
> Q9400), també **PDF + MSCZ**. Ganxo a la GUI: **Fitxer ▸ Exporta la
> partitura…** i l'acció commutable **«Inclou la partitura (xifrat)»**; també
> CLI (`eines/exporta_partitura.py`). Només en mode **BPM · compàs** i només
> **xifrat** (sense melodia). Detall: `docs/PARTITURA_EXPORT.md`.
> **Encara pendent**: ABC / LilyPond i imatges resumides.

- valorar exportar no només WAVs i carpetes de clips, sinó també altres sortides útils
- possibilitats a estudiar:
  - ~~MusicXML~~ ✅ fet (vegeu la nota)
  - ABC / partitures basades en text
  - LilyPond
  - CSV intel·ligible per DAW i editors externs
  - imatges de partitura o exportació resumida
- decidir quin és el valor real per a l’usuari i si això entra dins el producte core o és un mode de postprocessament
- prioritzar les exportacions amb més rendiment i menys fragmentació de flux

### 8) Desplegament de l’app real

- definir si la app es distribueix com a:
  - binari local per desktop
  - paquet Python
  - app empaquetada per a Linux
  - app per a Windows/macOS
- decidir si cal un procés de build reproducible amb versions i checksums
- preparar un canal de distribució per a usuaris finals, no només per a desenvolupament local

### 9) Desplegament a altres SO

> **Anàlisi de viabilitat (2026-10-07).** Conclusió: **viable** fer executables per a
> **Windows (x64)** i **macOS High Sierra 10.13** com a mínim, **tot a GitHub Actions**
> (cap build local Win/Mac). **No es signaran** les apps → s'assumeixen les limitacions
> de Gatekeeper (macOS) i SmartScreen (Windows). El build de **Linux no es toca**.

> **PROGRÉS (2026-10-08):** **els 3 builds del CI són VERDS** — Linux ✅
> (AppImage verificada) · **Windows ✅** (ZIP portable x64) · **macOS ✅**
> (`.app` per a 10.13). Detall, artefactes i pendents: `docs/ESTAT_MULTI_SO.md`.

#### 9.1 — Què s'ha de portar

L'app = capa Python (**PyQt5 + numpy<2**) + **3 peces natives per SO**:

| Peça | Linux (actual) | Windows | macOS 10.13 |
|------|----------------|---------|-------------|
| **Host Vamp** (`vamp_host_local`) | C++ `-msse -msse2` lligat a `libvamp-hostsdk` + `libsndfile` | recompilar (MSYS2 mingw-w64 / vcpkg) | recompilar amb `MACOSX_DEPLOYMENT_TARGET=10.13` |
| **Plugins Vamp** (`nnls-chroma`, `qm-vamp-plugins`) | `.so` | `.dll` | `.dylib` |
| **ffmpeg** | estàtic a `portable/bin/` | build estàtic `.exe` | build estàtic (evermeet, requereix 10.13) |
| **Python / PyQt5** | CPython portable + rodes | rodes `win_amd64` | rodes `macosx_10_13` |

La part d'anàlisi (pipeline, CSV, ABC, wavs) és **stdlib pur** → ja és portable.

#### 9.2 — Windows (dificultat baixa-mitjana)

- **Python/PyQt5/numpy:** rodes `win_amd64` estàndard ✅.
- **Host Vamp:** `mingw-w64-vamp-plugin-sdk` + `mingw-w64-libsndfile` (MSYS2) →
  `vamp_host_local.exe` estàtic. Alternativa: vcpkg (`vamp-sdk`).
- **Plugins:** `qm-vamp-plugins` té **binari oficial win64** ✅. ⚠️ El
  **Chordino/NNLS-Chroma oficial de Windows és 32-bit** → cal **compilar-lo win64**
  (upstream + mingw-w64) o bé un build comunitari.
- **ffmpeg:** build estàtic (gyan.dev / BtbN).
- **Empaquetat:** **PyInstaller `--onedir`** → ZIP portable; `.bat`/`.exe`
  substitueix `AUTO_CHORDS.sh`.
- **CI:** `windows-2022`.

#### 9.3 — macOS High Sierra 10.13 (dificultat mitjana)

- ⚠️ **Clau 1 — PyQt5:** el wheel Intel de **`PyQt5 5.15.11` és
  `macosx_11_0_x86_64`** → **no instal·lable ni executable a 10.13**. Cal
  **fixar `PyQt5==5.15.10`** (wheel `macosx_10_13_x86_64`). `PyQt5-Qt5 5.15.19`
  (`10_13`), `numpy 1.26.4` (`10_9`) i `PyQt5-sip` (`10_9_universal2`) ja van bé.
  Python 3.12 suporta 10.13.
- ⚠️ **Clau 2 — Runner i target:** `macos-13` **retirat** (04/12/2025); l'últim
  Intel és **`macos-15-intel`** (fins a tardor 2027). Cal build **thin x86_64**
  amb **`MACOSX_DEPLOYMENT_TARGET=10.13`** i tots els binaris natius (host +
  `libvamp-hostsdk` + `libsndfile`) compilats amb aquest mínim — **mai bottles de
  Homebrew** (pujarien el mínim). Verificable amb
  `otool -l | grep LC_VERSION_MIN_MACOSX`.
- **PyInstaller** ja apunta a 10.13 per defecte al bootloader ✅.
- **Plugins:** `qm-vamp-plugins` macOS oficial **10.7+** ✅; Chordino macOS binari
  **64-bit Intel** ✅ (verificar `otool`).
- **ffmpeg:** builds estàtics **evermeet.cx x86_64 requereixen 10.13** → encaixa ✅.
- **Empaquetat:** PyInstaller `.app` + ZIP (`ditto`). Sense signar → quarantine;
  l'usuari passa amb **clic-dret → Obrir** o `xattr -dr com.apple.quarantine`.

#### 9.4 — Canvis de codi necessaris (portabilitat)

| Fitxer | Problema | Solució |
|--------|----------|---------|
| `app/main.py` | `import fcntl` + `flock` (no existeix a Windows) | import condicional + `msvcrt`/fitxer lock |
| `app/pipeline.py` (`_vamp_env`) | `VAMP_PATH = ":".join(...)` | `os.pathsep` |
| `app/pipeline.py` (`VAMP_DIRS`, `HOST`) | rutes `*-linux64-local` i sense `.exe` | mapa per SO |
| `app/pipeline.py` (`run_acords_py`) | `["python3", …]` (trenca PyInstaller i Windows) | `sys.executable` o crida en procés |
  | `app/visor.py` (`_tria_player`) | `paplay`/`aplay` (només Linux) | mapa per SO (Mac `afplay`, Win `ffplay`) |
| `app/visor.py` (`os.killpg`, `SIGKILL`, `start_new_session`) | no existeixen a Windows | `CREATE_NEW_PROCESS_GROUP` + `terminate()` |
| `app/ffmpeg.py` | noms sense `.exe`, `os.access(X_OK)` | `sys.platform` + `.exe` |
| `app/config.py` | `TEMP_DIR` dins el projecte | carpeta d'usuari a macOS |
| `AUTO_CHORDS.sh` | bash + `LD_LIBRARY_PATH` | `.bat`/`.exe` |

#### 9.5 — Pla de CI (GitHub Actions)

- **Job Linux:** l'actual (no tocar).
- **Job Windows** (`windows-2022`): Python x64 → `PyQt5`+`numpy<2` → host amb
  MSYS2 → qm win64 + Chordino win64 → ffmpeg → `pyinstaller --onedir` → ZIP.
- **Job macOS** (`macos-15-intel`): `MACOSX_DEPLOYMENT_TARGET=10.13` →
  **`PyQt5==5.15.10`** → host + SDK/sndfile de font amb mínim 10.13 → qm macOS +
  Chordino macOS → ffmpeg evermeet → `pyinstaller --windowed` → `.app`+ZIP →
  verificació `otool`.
- Els workflows actuals es poden estendre amb aquests dos jobs o bé crear-ne un de
  release multi-plataforma (draft, sense signar).

#### 9.6 — Riscos

- **EOL del runner Intel** (`macos-15-intel`, tardor 2027): després caldria
  self-hosted o cross-compilar des d'arm64.
- No fer servir **Homebrew** per a components de 10.13 (bottles massa nous).
- **Chordino win64** no oficial → compilar-lo; verificar les dependències de
  runtime dels `.dll`/`.dylib`.
- Apps no signades: assumit.
- Accents/espais a les rutes (Windows).

#### 9.7 — Esforç estimat

| Bloc | Esforç |
|------|--------|
| Portabilitat del codi Python (§9.4) | ~1-2 dies |
| Job + paquet Windows | ~1 dia |
| Job + paquet macOS 10.13 | ~2-3 dies |
| Proves reals a Windows i al Mac 10.13.6 | manual (operador) |

**~1 setmana d'agent.** Ordre recomanat: **Windows primer**, després **macOS**.

#### Decisions encara pendents (llistat original)

- revisar compatibilitat de dependències per a Linux, Windows i macOS
- detectar quines parts del stack són dependents de platforma i quines són universals
- determinar els punts crítics:
  - PyQt5 / Qt5
  - execució de `sonic-annotator` i plugins
  - subprocessos i reproductors d’àudio
  - paths i permisos de fitxers
- decidir una estratègia modular per a build multi-platform i per a mantenir un nucli de producte estable

## 10) Funcionalitats pràctiques pendents (propers commits)

Idees d'usabilitat i productivitat anotades durant la sessió de proves del
2026-10-04. Són **idees exploratòries** que poden acabar implementant-se o
descartant-se — cap està planificada per data.

> ℹ️ Les idees considerades **prioritàries** per la propera fase estan
> consolidades a la **Fase D — Interacció DAW-like** (més amunt). Aquest
> apartat §10 recull idees **complementàries** o **descartades per ara**.

### A) Productivitat *(idees no cobertes per Fase D)*

- 🔍 **Cerca i reemplaça d’acords** (ex. canviar tots els `C` per `Cm`
  arreu, amb preview abans d’aplicar).
- 📋 **Còpia / enganxa** d’acords o seccions individuals (amb un buffer
  intern, no cal OS clipboard).
- 🕐 **Recent files** (llista dels últims 5–10 WAVs processats).

### B) Visualització ampliada

- 🎨 **Color personalitzable** per acords/seccions (paleta configurable,
  no només blau/grisa) — potser una paleta semàntica per graus musicals.
- 🌈 **Forma d’ona amb gradient** de color segons la secció activa
  (A→verd, B→taronja, C→blau…).
- 🏷️ **Etiquetes d’acord sobreposades** a sobre de l’ona quan el cursor
  s’hi acosta (tooltip persistent).
- 🔎 **Zoom independent del waveform** vs els acords (per exemple, poder
  fer zoom al waveform sense que els acords es comprimeixin, o al revés).
- 🎯 **Cursor lluminós** quan el ratolí passa per sobre d’un acord al
  waveform.

### C) Reproducció

- 🔁 **Loop region visual millorat**: rectangle que es pot redimensionar
  arrossegant les vores (similar als handles del DAW).
- 🎚️ **Velocitat de reproducció variable** (50%, 75%, 100%, 125%) — útil
  per practicar o revisar cançons lentes.
- 🔉 **Volum / equalitzador per secció** (mixatge bàsic: cada secció pot
  tenir un nivell d’àudio diferent a l’export).
- ⏱️ **Indicador visual de beat actual** (punt gros sobre el ruler quan el
  cursor passa per un beat).

### D) Export *(idees explorades i **descartades per ara**)*

La solució **clips WAV** ja cobreix el cas d’ús principal
(drag-and-drop al DAW). Els següents exports alternatius es van
explorar però **no es prioritzaran** mentre la solució actual funcioni:

- 📄 **Export a PDF** amb gràfic de l’ona + acords + estructura (per
  imprimir fulls de paper per assajar).
- 📝 **Export a Markdown / HTML** (per incrustar en una web o un document).
- 🎵 **Export a MIDI dels acords** (un track MIDI amb els acords, durada
  i nom — integrable a qualsevol DAW).
- 🎤 **Export a format Lyrics+Chords** (per karaoke o fulls de cantant).
- 📦 **Plantilles d’export** configurables (quins formats inclou el paquet
  final per defecte).

> 💡 Si en el futur canviem la base tecnolítica i trobem una manera
> trivial d’afegir aquests exports, es poden recuperar d’aquesta llista.

### E) Altres

- 🌐 **Multi-idioma** de la interfície (català, espanyol, anglès —
  sistema de traduccions amb `.po` o similar).
- 🔌 **API / CLI** per integrar l’anàlisi amb altres eines (un
  `auto-chords-cli` que faci el pipeline sense GUI).
- 📱 **Versió mòbil / web** (només lectura o edició bàsica via web — útil
  per revisar cançons des del mòbil).
- 🧪 **Mode “preview ràpid”** que reprodueix un tros d’acord específic
  sense haver de navegar a la posició.

### F) Barra de menús pròpia *(en construcció — 2026-10-05)*

**Context.** La idea és que l’app tingui una **barra de menús estàndard** a
dalt (com qualsevol aplicació), perquè totes les funcions siguin
**descobertes** en comptes de viure amagades en botons. També resol el bug
de les dreceres: un `QShortcut` dins el **visor incrustat** no s’activa, així
que les dreceres han de viure com a `QAction` de la **finestra principal**.

**✅ Fet (bàsic) — 2026-10-05** *(pendent de commit)*

| Menú | Accions operatives |
|---|---|
| Fitxer | Obre… `Ctrl+O` · Exporta `Ctrl+E` · Obre la carpeta de sortida · Surt `Ctrl+Q` |
| Edita | **Desfer `Ctrl+Z`** · **Refer `Ctrl+Y`** · Refer alt. `Ctrl+Shift+Z` · Paràmetres… |
| Selecciona | Marca inici de loop (A) · Marca fi de loop (B) · Activa/desactiva loop |
| Visualitza | Zoom + `Ctrl++` · Zoom − `Ctrl+-` · Zoom total `Ctrl+0` · Mostra el visor |
| Analitza | Analitza `F5` · Detecta el compàs 1 · Inclou estructura |
| Ajuda | Dreceres de teclat · Quant a Auto Chords |

> 🔧 **Fix inclòs**: undo/redo passa de `QShortcut` al visor → `QAction` de
> la finestra principal (evita l’ambigüitat de dreceres i funciona
> incrustat).

**⏳ PER FER** — accions encara pendents d’implementar (anrem a poc a poc):

- **Fitxer**: Desar `Ctrl+S` · Desar com… · Recent files · Nou projecte.
- **Edita**: Afegeix acord… · Afegeix secció… · Elimina element seleccionat ·
  Reanomena · Duplica · Copia/enganxa · 🔍 Cerca i reemplaça d’acords
  (vegeu §10-A).
- **Selecciona**: Selecciona tot `Ctrl+A` · Tots els acords · Totes les
  seccions · Inverteix selecció · Neteja loop.
- **Visualitza**: toggles ☑ **Mostra regle** · ☑ **Mostra graella** ·
  ☑ **Mostra ona** (mostrar/amagar capes del timeline) · 🎨 presets de
  colors (vegeu §3 i §10-B).
- **Analitza**: Regenera wavs (exporta només les wavs) · sensibilitat i
  llindars de Chordino/QM (vegeu §2).
- **Ajuda**: obrir l’esquema de la UI (`docs/ESQUEMA_UI.html`) des del menú.
- **Barra d’eines (toolbar)** opcional, per duplicar les accions freqüents.
- **Estats dinàmics**: les accions haurien de **desactivar-se** quan no
  escauen (p. ex. Desfer/Refer si la pila és buida; Exporta sense WAV;
  Zoom sense visor).
- **Integritat**: qualsevol acció nova ha de respectar les invariantes
  (§Notes d’implementació): una sola font de veritat al backend i, si
  toca les wavs, fer-ho **només** via `exporta()`.

### Notes sobre la implementació

- **Cap canvi trenca la invarianta** actual (`prev.fi == curr.t` per a
  acords; ordre estricte sense solapaments per a tothom).
- **Totes les noves funcionalitats han de mantenir el principi d’una sola
  font de veritat**: el backend (`app.pipeline`) continua sent l’única
  font de dades; la UI (`app.visor` + `app.timeline`) en reflecteix l’estat.
- **Tests nous** per cada feature abans de fer merge.
- **Reutilitzar els hooks** del visor (`chordTimeMoved`, `sectionMoved`,
  `_on_chord_*`, `_on_section_*`) en lloc d’afegir-ne de nous quan sigui
  possible.

## Criteri de producte actualitzat

La projecta es considera funcionalment preparada per a l’ús del flux principal quan:

- un usuari pot obrir una WAV
- analitzar-la sense terminal
- veure i navegar acords i estructura
- corregir, eliminar o afegir acords i seccions
- exportar el paquet final per a DAW
- i fer-ho tot des d’una sola app, amb un flux clar i repetible.

Aquest criteri ja està cobert en la seva base funcional i validat per regressions del pipeline i la UI.
