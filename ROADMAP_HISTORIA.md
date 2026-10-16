# Història del full de ruta — AUTO CHORDS

> **Arxivat el 2026-10-16.** Aquest fitxer és la **instantània** del `ROADMAP.md`
> anterior (l'acumulat del maig–octubre de 2026) que es va **reorganitzar** per
> deixar el `ROADMAP.md` viu i curt. **Es conserva tot**: Fases A–E, anàlisi
> multi-SO, graella/PPQ, obertura tecnològica, notes d'implementació i els
> brainstorms originals. Per a la llista **viva** d'idees i prioritats, vegeu
> [`ROADMAP.md`](ROADMAP.md).

---


> Eina per a **músics multi-DAW** que analitza una cançó (WAV), en deixa
> **editar visualment** els acords i l'estructura com si fos una pista, i
> n'exporta el resultat com a **clips d'àudio llestos per arrossegar a
> qualsevol DAW** (Live, Reaper, Logic, Bitwig, Studio One, Pro Tools,
> Cubase…). Tot en català. Llicència: GPL-3.0-or-later (GPLv3 o posterior).

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

## Obertura tecnològica

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

## Estat actual (2026-10-14 · v0.7.0)

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
- export final separat i explícit (`Exporta WAV's`, Ctrl+E)
- llançament directe des de la carpeta del projecte
- bloqueig de doble instància per evitar sobreposició d’aplicacions
- **auditoria de seguretat/estabilitat aplicada**: clamp de temps, tipus d’excepció específics, `_proc_lock`, `safe_filename`, parser CSV robust, validació WAV (sr/ch > 0)

**Novetats v0.3.0–v0.7.0 (2026-10-14):**

- **Estabilitat (v0.6.1)**: arreglat un **crash de macOS** (doble tancament
  del motor d'àudio) + **MuseScore** trobat també a **macOS/Windows**; i els 3
  CI ara corren **tota** la suite.
- **Embalatge i àudio (v0.6.0)**: **DMG de macOS** (a més del ZIP) i **motor
  d'àudio natiu** a macOS/Windows (`sounddevice`/PortAudio → **CoreAudio** i
  **WASAPI**; **Linux intacte**). CI de macOS amb **smoke test** de l'`.app` i
  **verificació exhaustiva del `minos`** (≤ 10.13). Detall: `CHANGELOG` [0.6.0]
  i `docs/AUDIO.md`.
- **Fase D.2 — edició DAW-like (v0.5.2)**: **multi-selecció** (`Ctrl`/`Shift`+clic),
  **porta-retalls intern** (`Ctrl+C/V/X`), **duplicar** i **moure** el grup,
  **indicador de MODE** al regle i **loop A/B amb snap**; `timeline.py` partit
  en 4 mòduls. Detall: `CHANGELOG` [0.5.2].
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
- **tota la suite** (OK, 1 skip) — suite completa executant-se als 3 CI.

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

> ⚠️ **Nota (14-10-2026):** secció del **08-10**, **superada** per la feina posterior:
> el **tag `v0.5.2-deute`** ja no cal (hi ha la **v0.7.0** amb els **3 paquets**), la
> **Fase D.2** (multi-selecció + copiar/enganxar) és **FETA** i el **`timeline.py`**
> ja s'ha **partit** (1.777 → **1.293** línies). Els **pendents vius** són a
> `docs/ESTAT_MULTI_SO.md` §«Pendent real» i `docs/MCP_AUTO_CHORDS.md` §«Pendent».

- **Proves manuals** (operador): `./AUTO_CHORDS.sh` (obrir WAV → Analitza →
  editar acord → Exporta WAV's); `python -m app.visor <wav>` (standalone); **metrònom**
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

### Coherència del snap — loop A/B (FET) i cursor *(per decidir)*

> 🔍 **Revisió de codi (2026-10-09, OC-3)** — `app/timeline.py`. Dins el visor
> hi conviuen **dos comportaments**: els **clips** (acords/estructures) SÍ que
> fan snap a la graella, i el **cursor/playhead** és **lliure**.

- ✅ **Loop A/B amb snap (FET 2026-10-09).** La selecció al regle
  (`_loop_x_to_time()`, usat per `mousePressEvent`/`mouseMoveEvent`) i els
  botons A/B (`marca_A`/`marca_B`, `app/visor.py`) ara arrodoneixen amb
  `TimelineView.snap()` (la mateixa graella que els clips, respectant
  l'**offset**).
- **Cursor sense snap.** `set_position()` no arrodoneix mai: totes les vies
  (clic al fons, lliscador, `±10 s`, editar l'etiqueta de posició) hi posen
  temps continu. Única excepció: clicar un clip situa el cursor al seu inici
  (snap *al clip*, no a la graella).
- **A decidir.** Si el **cursor** ha de fer snap també (coherent amb els clips)
  o quedar-se **lliure** per a navegació fina — o una opció **commutable**.

### Graella, PPQ i formats de temps — possibles millores *(per valorar)*

> 🧭 **Nota tècnica (2026-10-10)** — detall a `docs/GRAELLA_PPQ_TEMPS.md`. Fixa
> com l'app mesura, mostra i quantitza el temps i quines opcions de **graella** i
> **resolució (PPQ)** es podrien oferir.
> **Decisió actual: NO adoptar el PPQ ara** (l'app és d'àudio; les posicions són
> **segons** i no hi ha MIDI).

**Els 3 eixos (no barrejar-los mai):**

| Eix | Què és | Magnitud |
|---|---|---|
| **PPQ (resolució)** | unitat atòmica interna (ticks per negra) | enter (480–3840) |
| **Graella** | sobre quines posicions s'imanta i es dibuixa | subdivisió del temps |
| **Tempo + compàs** | conversió musical ↔ absolut (s/mostres) | variable |

**Per què el PPQ no encaixa ara:** AUTO CHORDS és una app d'**àudio** — els acords
i les seccions són **trossos de temps de l'àudio** (segons/mostres, de l'anàlisi),
i el grid (bpm/offset) és una **vista**. El PPQ és útil sobretot per a **(a)**
subdivisions exactes (tresets/puntets) i **(b)** **export MIDI** (que aquí encara
no existeix). Guardar les durades en ticks voldria dir **quantitzar** temps
d'àudio → pèrdua de precisió.

**Millores que SÍ que valen la pena (ordre suggerit):**

1. **Modes de graella** al `grid_plan` (que ja és font única de grid/regle/snap):
   `straight` · **`triplet`** · **`dotted`** · `swing` · `custom (p:q)`.
   - Pas en segons: `straight = beat·4/N`, `triplet = straight·2/3`,
     `dotted = straight·3/2`; `swing` desplaça la 2a subdivisió.
   - Selector de mode a la UI. *(No cal PPQ: els tresets/puntets funcionen bé en
     segons perquè el snap es calcula per operació, sense acumular.)*
2. **Display complet** `compàs.temps.tick` (ara tenim `compàs.temps`, sense el 3r
   camp).
3. **Si algun dia es fa export MIDI** (SMF): convertir **segons→ticks** en aquell
   moment amb `ticks_per_beat = 960` (múltiple de 3 i 5 → cobreix tresets i
   quintets). No cal canviar el model d'emmagatzematge.
4. **Tempo map / rampes** (BPM variable): si mai es vol, `beat↔segons` requereix
   **integrar** `60/BPM` tram a tram (no regla de tres).

**Trampes a evitar** (de la nota): PPQ **potència de 2** (tresets impossibles) ·
`float` per a posicions si mai es guarden musicals · confondre **grid** (vista)
amb **PPQ** (emmagatzematge) · assumir BPM constant amb tempo map · noms de
figures (treset de corxera ≠ treset de semicorxera) · setets/quintets exigeixen
factor 5/7 al PPQ · canvi de compàs (la llargada varia) · `int64` per a PPQ alt.

> 📌 **Estat: no implementat** — anotat com a possibles millores. La graella
> actual (`grid_plan`, adaptativa al zoom, amb offset i compassos negatius) es
> manté.

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
  | `app/visor.py` (`_tria_player`) | `paplay`/`aplay` (només Linux) | mapa per SO (Mac/Win: **motor natiu** `sounddevice`) |
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

- ✅ **FET (15-10, `c806b3f`)** — 🔍 **Cerca i reemplaça** d'acords **i** d'etiquetes
  d'estructura (`Edita ▸ Troba i reemplaça…`, **`Ctrl+H`**): substitueix **totes** les
  aparicions exactes a tot el tema, en **una sola operació de desfer** i **sense tocar
  cap temps**. *(La idea original demanava «preview»; s'ha resolt amb el recompte final.)*
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
  Reanomena · Duplica · Copia/enganxa · ✅ Cerca i reemplaça
  (fet, vegeu §10-A).
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

> 🔴 **Les regles d'or (invariants) de l'app són totes a
> `docs/REGLES_DE_LA_APP.md`** — llegiu-les abans de tocar codi. Cap canvi no
> les pot trencar.

- **Cap canvi trenca la invarianta** actual (`prev.fi == curr.t` per a
  acords; ordre estricte sense solapaments per a tothom).
- **Invariant de COBERTURA** (regla d'or): la **suma dels clips d'acords = la
  durada de la WAV** i la **suma dels clips d'estructura = la durada**, en
  qualsevol mode (**Lliure** o **BPM · compàs**) i amb o sense **snap** → el 1r
  clip a **0** (capçalera «N» si cal) i l'últim a la **durada**. Ho garanteix
  `pipeline.normalitza_cobertura()`, que s'ha d'aplicar **SEMPRE** (edició en viu,
  visor, CSV i exportació; **no només** en carregar el visor i en exportar — vegeu
  `docs/REGLES_DE_LA_APP.md` §«S'ha de complir SEMPRE» i l'evidència OC-6/332-334).
  La regla **mana sobre el snap**, que només quantitza els límits interiors.
- **Regla d'or #11 — paritat d'edició (acords ↔ estructura)**: **implementada a
  l'app** (GUI + backend) el **2026-10-14**: `pipeline.parteix_acord` i
  `pipeline.fusiona_acords`, `visor.parteix_acord`/`fusiona_acord`/`fusiona_seccio`,
  els menús de llista i el menú contextual del clip **simètrics**, i `SectionItem`
  amb el mateix tracte (`dragStarted` + cursor) que `ChordItem`. Test:
  `tests/test_regla11_paritat.py`. La part **MCP** (exposar *partir*/*fusionar*)
  queda **aparcada** — vegeu **§11-g**.
- **Totes les noves funcionalitats han de mantenir el principi d’una sola
  font de veritat**: el backend (`app.pipeline`) continua sent l’única
  font de dades; la UI (`app.visor` + `app.timeline`) en reflecteix l’estat.
- **Tests nous** per cada feature abans de fer merge.
- **Reutilitzar els hooks** del visor (`chordTimeMoved`, `sectionMoved`,
  `_on_chord_*`, `_on_section_*`) en lloc d’afegir-ne de nous quan sigui
  possible.

## 11) Idees de futur — brainstorm (2026-10-14)

> **Funcionalitats futures** (a part de les ja existents). Encara **no** planificades:
> es valoraran i prioritzaran més endavant. *(Idees de l'operador + derivades.)*

### a) Conversor universal d'àudio (aprofitant l'`ffmpeg` intern)
- **Exportar en qualsevol format**: MP3, FLAC, OGG/Opus, M4A/AAC i WAV a qualsevol
  mostreig/profunditat (16/24/32-bit) — l'`ffmpeg` ja viatja **dins** l'app.
- **Conversió en lot** (una carpeta sencera), **normalització de volum** (LUFS),
  **remostreig** (44.1↔48↔96 kHz) i mono/stereo.
- **Retall a l'export** (només un tros: per punts o per secció/acord).
- Casos d'ús: treure un MP3 d'una demo, passar una WAV de 96k a 44.1, tallar una cua,
  preparar un MP3 per escoltar.

### b) Edició de l'àudio carregat (tallar / escurçar / expandir + còpia)
- **Tallar** (trim) l'àudio original: treure silenci inicial/final, marcar in/out.
- **Escurçar/expandir**: allargar un tros (loop dins d'un acord), ajustar durades.
- **Sempre sobre una CÒPIA**: **mai** modificar l'original → es desa `<nom>_editat.wav`.
- **Fade in/out** i **crossfade** entre seccions.
- Integrat amb el model (regles d'or: cobertura/contigüitat) i amb l'export.

### c) Millores de botons / UI
- Estats visuals més clars (actiu/desactivat/inhabilitat) i tooltips/`aria` revisats.
- **Barra de transport configurable** (quins botons es veuen).
- Agrupacions i **dreceres** noves; revisió d'icones.
- Botons d'**export amb opcions** (format, retall…) → petit diàleg.

### d) Multilingüe
- **i18n** de la UI (català per defecte; anglès…): `gettext`/`QTranslator`.
- Traduir menús, diàlegs i missatges (els **noms de fitxer** i les dreceres es mantenen).
- Opció de tenir **docs en anglès** (com a mínim el `README`).

### e) Export MIDI
- **MIDI** amb els acords/seccions: com a **notes** o com a **marcadors**
  (meta-events `marker`/`text`), per importar a qualsevol DAW.
- **Mapa de tempo/timesig** al MIDI (la graella que ja tenim).
- Opcions: només canvis d'acord, o notes mantingudes; xifrat vs notes.

### f) Altres (brainstorm lliure)
- **Plantilles d'export** per DAW (Reaper/Live/Logic) amb nom i estructura coneguts.
- **CLI/headless**: `auto-chords analitza tema.wav` per automatitzar cues.
- **Marcadors/seccions** i export de **cue-sheets**.
- **Suport de vídeo** (treure'n l'àudio) via `ffmpeg`.

### g) MCP — paritat d'edició de clips (*partir* / *fusionar*) — ✅ FET
- ✅ **FET (2026-10-15)**: el pont exposa **`ac_parteix_acord` · `ac_fusiona_acord` ·
  `ac_parteix_seccio` · `ac_fusiona_seccio`** (noms finals, en català com la resta
  del pont) → GUI i MCP ofereixen **el mateix joc** (regla d'or **#11**).
- **De passada**, s'han cobert les funcions de **projectes** que també eren només
  GUI: `ac_crea_projecte` · `ac_obre_projecte` · `ac_desa_projecte` · `ac_desa_com` ·
  `ac_fes_backup` · `ac_recents`.
- **Comptador**: **40 → 50 eines**; `docs/MCP_AUTO_CHORDS.md`, `README.md` i
  `AGENTS.md` actualitzats. Tests: `tests/test_mcp_bridge.py` (+20) i **prova en
  viu** pel protocol MCP real. Darrere: `app/mcp_bridge.py` (`_op_*` + `OPERACIONS`)
  i `eines/mcp_auto_chords_server.py` (`_TOOLS`).

> 🧭 **Criteri**: cap d'aquestes pot trencar les **regles d'or**
> (`docs/REGLES_DE_LA_APP.md`); si en xoca alguna, es canvia **la funcionalitat**, no la regla.

## 12) Idees «DAW professional» — brainstorm ampliat (2026-10-14, OC-5)

> Idees **noves** (no cobertes per §10/§11) per acostar AUTO CHORDS a l'experiència
> d'un **DAW professional** (Reaper/Live/Logic). Cap és planificada; cap no pot
> trencar les **regles d'or** (§«Notes sobre la implementació»).

### A) Edició fina — el «feel» de DAW
- **Nudge amb teclat** — `←`/`→` mouen el clip seleccionat **un pas de graella**
  (`Shift` = més fi; `Alt+←/→` = estirar/encongir un pas). És el gest més habitual
  d'un DAW per ajustar sense ratolí.
- **Graella configurable** — triar la **divisió** (1/4 · 1/8 · 1/16 · tresets) i un
  **interruptor de snap** ràpid al regle; avui el snap és sempre a la subdivisió.
- **Ripple edit explícit** — commutador visible: en moure/inserir, la resta
  **s'arrossega** (manté la cobertura, regla #4) o **no**; fer palès què fa el model.
- **Historial d'undo/redo** — a més de Desfer/Refer, una **llista de passos**
  («Mou acord Am → 12,4 s», «Parteix secció B»), amb salt directe al pas.

### B) Navegació i vista
- **Auto-scroll (playhead follow)** — durant el play, el timeline **segueix el
  cursor** amb scroll suau; i **zoom a la selecció/loop**.
- **Mini-mapa (overview)** — franja fina amb **tota la cançó** de cop, per saltar
  i seleccionar trams ràpid (com l'overview de Reaper).
- **Zoom vertical de l'ona** — alçada/amplitud independent del zoom horitzontal
  (per veure atacs i silencis).
- **Carrils amagables i alçada ajustable** — mostrar/amagar i deformar l'alçada de
  cada carril (avui fixa).

### C) Marques i rang
- **Marcadors amb nom** — punts marcats («solo», «pont»…) + **llista** per saltar-hi
  (`Tab` = següent) i export **cue-sheet** *(extensió de §11-f)*.
- **Selecció de rang temporal** — arrossegar el regle fixa un **rang**; les accions
  (exporta, copia, elimina) s'hi poden **limitar** (com el *time selection*).

### D) So i anàlisi
- **Tempo map** — més d'un canvi de **BPM** (cançons que acceleren/retarden) i
  **compassos variables** (4/4 → 3/4), amb la graella redibuixada.
- **Loudness (LUFS) + espectrograma** — mesurar i veure el so carregat abans d'exportar.
- **Analitzar en lot** — una carpeta sencera de WAVs → **informe** (BPM, tonalitat,
  acords) sense obrir-les una a una.

### E) Musical (ajuda a l'usuari)
- **Tonalitat → paleta d'acords** — mostrar l'escala i **suggerir acords** diatònics
  (verd/vermell) + **selector** (arrel/qualitat/baix) en lloc d'escriure text.
- **Confiança de la detecció** — pintar l'acord amb **opacitat segons la confiança**
  del detector (saber què revisar primer).
- **Notes/anotacions per clip** — camp lliure per clip («revisar», «dubtós»).

### F) UX de producte
- **Arrossega-i-deixa-anar** un WAV/`.acproj` **damunt la finestra** per obrir-lo.
- **Pantalla d'inici** — en arrencar sense arguments: **Recents** (WAV + projectes),
  «Nou», «Obre…» (com un DAW).
- **Accessibilitat** — navegació completa amb teclat + etiquetes per a lectors de pantalla.

### G) Àudio de clips — edició no destructiva
- **Guany per clip** — `+ Gain` a cada clip (sense tocar la WAV mare) → s'aplica a l'export.
- **Fades amb nanses** — triangles a les cantonades del clip per fade in/out, i
  **crossfade** arrossegant un clip sobre el veí *(extensió de §11-b)*.
- **Snap a zero-crossings** — els talls cauen a un creuament de zero (evita el «clic» al tall/export).

### H) Configuració «pro» (com un DAW madur)
- **Editor de dreceres** — reassignar qualsevol tecla i **desar perfils**.
- **Modificadors de ratolí** — què fa `Arrossega` / `Alt+Arrossega` / `Shift+Arrossega`
  (moure · copiar · esborrar el clip), personalitzable.
- **Workspaces (screensets)** — desar/recuperar disposicions de panells (edició, anàlisi)
  i **panells flotants/acoblables** + pantalla completa.
- **Preferències completes** — motor d'àudio, autosave, graella per defecte, tema.

### I) Flux de treball
- **Copiar/enganxar entre projectes** — buffer persistent entre sessions.
- **«Repeteix l'última acció»** (`Ctrl+R`, com Reaper) — repetir el darrer moviment/partit.
- **Plantilles de projecte** — crear un `.acproj` amb graella i valors prefixats.
- **Presets d'export** — «per a Live», «per a Logic»… amb noms i carpeta coneguts *(vegeu §11-f)*.

### J) Vista pro
- **Gestor central de marques/regions** — una taula amb totes les marques i regions per
  editar, saltar-hi i exportar *(extensió de la idea C)*.
- **Peu d'estat** — motor d'àudio, taxa de mostreig, format, CPU i autosave sempre visibles.
- **Tema clar/fosc** — amb opció de seguir el tema del sistema.

### K) Navegació ràpida «de DAW»
- **Paleta de comandes** (`Ctrl+K`) — escriure el nom d'una acció i executar-la
  (descobriment total + velocitat de teclat, sense recordar dreceres).
- **Rellotge gran (big clock)** — el temps actual en **gran** (compàs.beat o min:seg),
  útil en gravar o assajar; clic per canviar de format.
- **Snap a esdeveniments** — a més de la graella, encaixar als **extrems dels clips**
  veïns i al **cursor** (com els «snap targets» dels DAW).

### L) Explorador multimèdia integrat
- **Navegador de fitxers** dins l'app (arbre de carpetes + audició ràpida) per trobar el
  WAV o el `.acproj` sense sortir; arrossegar-lo a la finestra per obrir-lo *(lliga amb F)*.

### M) Cua de render (batch)
- **Cua de treballs**: afegir diversos projectes o rangs i exportar-los **tots** d'un cop
  (noms i formats prefixats) — com el *Render Queue* d'un DAW.

### N) Entrada d'acords (ajuda musical)
- **Teclat a pantalla / MIDI** — tocar l'acord i que s'escrigui el xifrat, o triar
  **arrel/qualitat/baix** amb botons, en lloc d'escriure'l a mà.

### O) Generar un projecte de DAW (el «pont» definitiu)
- **Exportar una sessió** (`.rpp` de REAPER, `.als` de Live, `logicx`…) amb els clips
  **ja col·locats a la graella** (tempo, posicions, noms): obrir-la i ja estar llest —
  estalvia l'arrossegament manual. És el que més valora un usuari multi-DAW.
  *(Lliga amb §11-f «plantilles d'export per DAW» i l'skill `live9-to-reaper`.)*

### P) Documents amb pestanyes
- **Diverses cançons obertes alhora** (pestanyes), amb desfer/estat independents, per
  comparar dues versions del mateix tema.

### Q) Navegador de còpies (autosave/backups)
- **Veure i restaurar** les còpies de `backup/` des de la GUI (amb data i resum) i
  comparar-les amb l'actual — la recuperació d'un DAW, però visible.

### R) A/B de dues anàlisis
- **Comparar** dues anàlisis del mateix tema (detectors o paràmetres diferents) amb un
  commutador, i decidir quina es queda.

> 🧭 Prioritat suggerida: **A** (edició fina) i **B** (navegació) donen el màxim
> «seny de DAW» per cost baix; **D** (tempo map) i **E** (paleta d'acords) són les
> de més valor musical i més cost.

## 13) Decisions pendents i validació a reprendre (2026-10-15)

> Estat de la tongada de **validació** (prioritat 1 de l'operador): **feta i tancada**
> el 15-10 — **738 tests OK** (1 skip), **prova MCP en viu 57/57**, i **6 fixes reals**.
> Aquí queden les coses que **NO** s'han tancat perquè depenen de l'operador o de
> reprendre la feina.

### ⚠️ Decisió de producte pendent (operador)
- 🔎 **Divergència de noms a l'export**: l'export aplica **`style()`** al nom del
  fitxer → el nom del **WAV pot diferir** del nom al **CSV** (`Am` → `A-.wav`).
  Està **documentat** com a NOTA a `tests/test_export_limits.py` (test
  `test_nom_wav_usa_style`) i a `CHANGELOG.md`. **Pendent**: decidir si és el
  comportament **desitjat** o si cal **alinear** el nom del WAV amb el del CSV.

### 🔁 Validació a reprendre (només si l'operador ho demana)
- **MCP**: casos d'error de les eines noves (`parteix`/`fusiona` acord i secció,
  `regularitza`, i les de projectes).
- **Model**: mode **Lliure** vs **BPM** amb temps **negatius** i `offset`.
- **Anàlisi**: amb un **WAV molt curt** o un **CSV buit**.
- **Mode fàcil**: amb **seccions** (blocs) en casos rars.

### 🚚 Publicació (en espera, per ordre de l'operador)
- **`push`**: tot és **local** (projecte + context).
- **Compilacions / CI**: `build-all` en espera.

## 14) Funcionalitats futures proposades (2026-10-15, operador)

> Idees que l'operador vol tenir presents com a **properes línies de treball**.
> Cap no ha de trencar les **regles d'or** (cobertura, ordre, contigüitat…).

### 14.1 Treballar SENSE analitzar (edició total pel usuari) ✅ FET (2026-10-15)
> **Implementat.** En carregar un àudio, si el model és buit es crea el punt de
> partida editable (`pipeline.model_inicial()`): **1 clip d'acords** (`N`) +
> **1 clip d'estructura** (`A`) que cobreixen tota la cançó, i es desen els CSV.
> L'**anàlisi passa a ser opcional** (no es crea `analisi/` si no analitzes).
> Test: `tests/test_sense_analisi.py` (8). Detall: `MEMORIA.md` 15-10.
- **Objectiu**: poder fer servir l'app **sense dependre de l'anàlisi** — el usuari
  vol poder **crear i editar-ho tot a mà** (acords i estructura).
- **Primer pas**: en **carregar un àudio**, crear automàticament **un sol clip
  d'acords** i **un sol clip d'estructura** que cobreixin tota la cançó, com a punt
  de partida editable; a partir d'aquí, partir / afegir / moure / renombrar.
- **Conseqüència**: l'**anàlisi** (Chordino/qm) passa a ser **opcional**
  («Analitza» quan ho vulguis), **no un requisit previ**.
- **A vigilar**: regla d'or **#4** (cobertura total) — el clip únic ha de cobrir la
  durada de l'àudio; i que **sense anàlisi** no calgui la capa crua (`analisi/`).

### 14.2 MIDI per escoltar els acords (panell de tipus d'acord) ✅ FET (2026-10-15)
> **Implementat** com a **audició interna**: `app/acord_audio.py` (NOU, numpy pur)
> sintetitza un **e-piano FM estil Rhodes** i el botó **▶ Escoltar** del panell
> toca **arpegi + bloc** amb un **motor efímer**. No és sortida **MIDI estàndard**
> (si mai es vol alimentar un DAW, es pot afegir). Test: `tests/test_acord_audio.py`.
- **Objectiu**: **sentir** l'acord mentre es tria/edita al **panell de tipus
  d'acord** (el que s'ha dissenyat a `docs/PANELL_TIPUS_ACORD_mockup.*`).
- **Què cal**: reproduir l'acord (MIDI o to intern) en **clicar una fila** o en
  canviar la selecció; opcionalment, **audició de la inversió/baix** (`A-/G`).
- **A vigilar**: el motor d'àudio d'aquest PC (sense AVX), baixa latència i que
  **no interfereixi** amb la reproducció de la cançó.
- **Com ho faríem (investigat 15-10, OC-8)** — **cap dependència nova**:
  - Les apps «pro» (MsyChords, InstaChord, Chordbot, Chordjam…) fan totes el mateix:
    **xifrat → graus → notes MIDI → sintetitzador intern** (i sovint també un
    **arpegi/strum**).
  - **Ja ho tenim**: `app/audio_out.py` (motor **unificat** a 3 SO: Linux
    `paplay`/`aplay`, mac/win `sounddevice`/PortAudio) i **`numpy`** (com fa
    `app/metronom.py`, sinusoide + envolupant «sense pops»).
  - **Pla**: mòdul pur **`app/acord_audio.py`** — `notes_del_tipus(arrel, graus)`
    (intervals **derivats de la mateixa `xifrat.TAULA_TIPUS`** → font única) +
    `genera_acord`/`genera_arpegi` (to lleuger + envolupant). El botó **▶ Escoltar**
    del panell sonaria **arpegi (per separat) + bloc (alhora)** amb un **motor
    efímer** (no interfereix amb la cançó). Tot dins `try/except` → si l'àudio
    falla, **avís clar**, mai un crash.

### 14.3 Revisar Copiar/Enganxa (per què de vegades no «fa el que s'espera»)
- **Objectiu**: auditar copiar / retallar / enganxar (clips **i** loop) i
  **explicitar** el comportament esperat: regla d'or **#4** — l'enganxat
  **sobreescriu** el tram i la cançó **no creix**; l'àncora és el **cursor**; i què
  passa **si no mous el cursor** (s'enganxa just després del bloc).
- **Què cal**: reproduir amb **tests** els casos que «no funcionen com s'espera»,
  trobar la causa (índexs, arrodoniments, **selecció mixta**, cobertura) i/o
  **aclarir la UX** (missatge a la caixa d'informació amb **què farà** l'enganxat).

### 14.4 Backups — revisar com funcionen i poder-ne seleccionar des de l'app
- **Objectiu**: revisar el funcionament dels **backups** (quan es fan, què guarden,
  rotació) i afegir una manera de **triar/restaurar una còpia des de la mateixa app**
  (llista de còpies amb **data-hora** → previsualitzar i restaurar).
- **Què cal**: UI de selecció + restauració (amb **confirmació** i seguretat — una
  operació clara, mai destructiva), i mostrar **què conté** cada còpia (document
  `.acproj` + CSV + `analisi/`).
- **Relacionat**: `docs/PROJECTES.md` (autosave, rotació de 10) i
  `Projecte.fes_backup`.

### 14.5 Aprofitar l'espai quan s'amaga el «Log · Informació»
- **Observació**: en **amagar** el dock **«Log · Informació»** (a baix), la
  finestra **no reaprofita** l'espai → queda una **franja buida**.
- **Objectiu**: que l'espai alliberat vagi a les **llistes d'acords i
  estructura** (i al timeline), de manera que el visor **creixi** i s'aprofiti
  tota l'alçada disponible.
- **Què cal**: fer que el visor (amb les seves llistes) sigui el **widget
  central expansible** quan el dock està ocult; comprovar-ho amb el dock
  **visible / ocult** (i en tornar-lo a mostrar, que tot recuperi la mida).
- **A vigilar**: que el redimensionament no descol·loqui el transport ni la
  barra; cap canvi al model (només presentació).

### 14.6 Afinador (tuner) de guitarra
- **Objectiu**: un **afinador** dins l'app, aprofitant la **entrada d'àudio** (p. ex.
  la Scarlett): captar el so de la corda → **detecció de to** → mostrar la **nota**
  i la **desviació en cents**, amb una referència visual (agulla/LED).
- **Què cal**: capturar l'entrada, calcular el to fonamental (pitch), comparar amb
  l'afinació (estàndard **EADGBE** i, opcionalment, alternatives); suport
  **natural / tempered** (a la carpeta `documentacio_per_treball/` de
  `Gt_ALL_Chords_app` hi ha l'`afinacion natural-temperat.jpg`).
- **A vigilar**: **CPU/latència** (Q9400 sense AVX) i que **no xoqui** amb la
  reproducció; reutilitzar el motor d'`app/audio_out.py`.

### 14.7 Incorporar i millorar `Gt_ALL_Chords_app` («Creador d'Acords de Guitarra»)
- **Què és**: app d'escriptori **Electron + HTML/JS vanilla**
  (`~/0PROJECTES_GitHub/Gt_ALL_Chords_app`): **diapasó interactiu**, **identificador
  d'acords** (a partir de les posicions), **filtres de digitacions**, **centre
  d'estudi**, **cercle de quintes**, **diccionari flamenc**, **escala cromàtica**,
  **presets** i **funció tonal**. És **estable** (v1.0.0) però **dormit** des del
  24-06.
- **Objectiu**: **incorporar** aquestes funcionalitats a AUTO CHORDS (o
  integrar-hi l'app) i **millorar-les** amb el que ja tenim: **xifrat canònic**,
  **panell de tipus d'acord**, graella `xifrat.TAULA_TIPUS`, projectes, MCP i
  export/partitura.
- **Sinergies clares**: el **diapasó** ↔ triar/visualitzar la **digitació** dels
  acords del tema; el **diccionari/filtres** ↔ el **panell de tipus**; el **cercle
  de quintes** ↔ tonalitat/armadura de la partitura; el **centre d'estudi** ↔
  pràctica amb el tema carregat.
- ⚠️ **Llicència (CRÍTIC)**: `Gt_ALL_Chords_app` és **Polyform Noncommercial
  1.0.0** i AUTO CHORDS és **GPL-3.0** → **no es pot copiar codi directament**;
  cal **reimplementar** les idees (o consensuar-ho amb el propietari), i respectar
  la **no-comercialitat**.
- **A vigilar**: abast **gran** → fer-ho per **fases** (diapasó → identificador →
  filtres → estudi…), i sense trencar les **regles d'or**.

## 15) Edició a la graella — convencions dels DAWs professionals (2026-10-16)

> **Origen**: bug real de l'operador («faig Ctrl+C i Ctrl+V i no funciona»). El
> bloc 13.25→18.00 acaba EXACTAMENT a la marca següent (l'A de 18.500 s); el
> snap de la graella musical movia l'àncora a 18.502, l'A sobrevivia a 1,9 ms de
> la nova i la validació (≥ 10 ms) rebuixava l'enganxat **sencer** — i només ho
> deia al log, o sigui que a pantalla «no passava res».
>
> **Investigació** (Cubase 15, Reaper, Pro Tools, Logic, Final Cut, Premiere,
> Resolve): les convencions són clares i el disseny de l'app s'hi ha alineat.

### 15.0 FET (2026-10-16)
- **(3) L'àncora fa snap primer als EVENTS**: si el cursor cau a prop d'una
  **marca del model** (vora de clip) s'usa el SEU instant **exacte**; la graella
  musical només si no hi ha cap marca a prop. Tolerància **en píxels**
  (`SNAP_MARCA_PX = 10.0`, com el «snap distance» del Reaper) → depèn del zoom.
  Nous: `Timeline.snap_a_marca()` i `Timeline.marques_temps()`.
- **(4) El bloc viatja RÍGID**: les posicions relatives copiades no s'arrodoneixen
  (equivalent al `Grid Relative` del Cubase / «snap relative to grid» del Reaper
  per als ítems que ja porten offset): arrodonir cada element deformava
  l'espaiat intern del bloc.
- **(6) Mai en silenci**: un rebuig d'enganxat (o un «res a canviar») surt **a
  pantalla** via `avis_editor` (caixa d'informació), no només al log; i
  **`Ctrl+Shift+V` se salta el snap** (patró «hold N» del Final Cut / Shift de
  l'Avid MediaCentral).
- **Tests**: `tests/test_copiar_enganxar.py::TestAncoraDeMarca` i
  `TestEnganxatALaVoraDelBloc` (regressió amb la geometria exacta del cas real;
  **verificat que fallen amb el codi anterior**). Suite: **842 tests OK**.

### 15.0b FET (2026-10-16) — eina del timeline + marquee (petició de l'operador)
- **Commutador d'eina** (botó a la barra `[Eina: intel·ligent]` + acció al menú
  Selecciona): **«intel·ligent»** (per defecte; la fletxa contextual d'abans:
  mou/redimensiona clips, regla = loop, Shift+clic = rang) o **«marc»**.
- **Eina «marc»** (marquee/rubber-band, com els DAWs): arrossegar **no mou cap
  clip**; es dibuixa un rectangle que **desapareix en deixar anar**
  (`TimelineView.drawForeground`) i queden seleccionats els clips que **HI
  SONEN** a dins — solapament, no només inicis (`TimelineView.keys_dins_marc`)
  — i **només de les pistes que el rectangle cobreix**: un marc damunt dels
  acords agafa només acords. Un arrossegament minúscul es tracta com un clic i
  la selecció **no** entra a la pila de desfer.
- **Selecció creuada DESACTIVADA per defecte** (menú Selecciona): el rang de
  `Shift+clic` es queda al **carril del clip clicat**; activada, torna a abraçar
  les dues pistes com abans (`extend_selection` + `set_seleccio_creuada`).
- **Tests**: `tests/test_eina_marc.py` (**12**) · suite **854 tests OK** · i
  `docs/ESQUEMA_UI.md` actualitzat (el test d'auditoria GUI↔doc ho exigeix).

### 15.1 Pendents d'UX (investigats, NO implementats)
- **(1) Fonts de snap commutables**: dues caselles independents, com el Reaper
  («snap a events/marques» i «snap a la graella», per separat) i el `Snap Type`
  múltiple del Cubase (`Grid` · `Grid Relative` · `Events` · `Cursor` ·
  combinacions).
- **(2) Tolerància de snap configurable** (avui fixa a 10 px) i valorar adaptar
  la **resolució de la graella al zoom** (`Adapt to Zoom` del Cubase).
- **(5) `Ctrl+C` no hauria de moure el cursor**: cap DAW ho fa. Substituir el
  «mou el cursor al final del bloc copiat» per un comandament **a part**
  («duplica just darrere») i deixar el `Ctrl+V` lligat al cursor tal com estigui.
- **(7) Mode «sense graella»**: snap **només a les marques** per a cançons
  rubato (equivalent al regle en *Seconds* del Cubase, on la graella passa a
  1/10/100 ms). Útil quan el BPM detectat no quadra amb tota la peça.
- **(8) Indicador visual del punt d'ancoratge**: la línia vertical que apareix
  al Premiere en moure/enganxar («a vertical line will appear to indicate the
  adjusted alignment»), per veure a què s'ha enganxat.
- **(9) Opcional**: eines MCP `ac_copia` / `ac_retalla` / `ac_enganxa` perquè un
  agent pugui fer aquestes operacions (avui el pont només té les de selecció).
- **(10) Higiene dels tests (16-10-2026)**: els fixtures (`_visor()` →
  `tempfile.mkdtemp()`) **no esborren mai** la seva carpeta temporal: en una
  tongada de feina la suite deixa **~2,4 GB** a `/tmp`. Solució: que cada test
  registri `addCleanup(shutil.rmtree, v.td, ignore_errors=True)` (o un helper
  comú `_qt_neteja`), i així la suite es neteja sola sense `rm` manual.

## 16) Refactorització de `main.py` en mòduls dedicats (FUTUR — 2026-10-16)

> **Estat**: `app/main.py` té **2.942 línies** i la classe `Finestra` acumula
> **138 mètodes** («god object»). **Avui està prou organitzat i funciona** (suite
> verda) → **NO és urgent**; queda **anotat per a una futura versió**, amb calma
> i **per fases**. Decisió de l'operador (16-10): deixar-ho com està de moment.

### 16.1 Què es faria
Partir les responsabilitats de `Finestra` en **mòduls petits i dedicats** (com la
resta del projecte: `xifrat`, `partitura`, `projecte`, `acord_audio`…):

| Grup | Mètodes / estat | Mòdul proposat |
|---|---|---|
| **Info box** (rotatori, clic, `eventFilter`) | `_missatge_info`, `_actualitza_info_widget`, `_posa_info`, `_info_panells`, `_panell_eina`, `_info_defecte_html`, `_clic_info_box` | `app/info_box.py` |
| **Log** | `self.log`, `registra` | `app/log_panel.py` |
| **Avisos** (no-modals amb pont MCP actiu) | `avisa*`, `_avis`, `_tanca_avis_box` | `app/avisos.py` |
| **Dreceres** | `_dreceres`, `_text_dreceres`, `_mostra_dreceres` | `app/dreceres.py` |
| **Projectes** (obrir/desar/backups/sessió/recents) | ~25 mètodes | `app/projecte_ui.py` |
| **Export** | `exporta*`, `_prepara_export`, `_ho_confirma`, `_exporta_partitura`, `_assegura_locators` | `app/export_ui.py` |
| **Anàlisi** | `Feina`, `FeinaExporta`, `executa`, `acabada` | `app/feina.py` |
| **Temps/BPM** | `_bpm_val`, `_parse_compas`, `_canvia_tempo`, tap tempo | `app/temps_ui.py` |
| **Barres d'eines/transport · menús** | construcció de la GUI | `app/barres.py`, `app/menus.py` |

### 16.2 Com (l'estratègia amb menys risc)
- **Mixins** (`InfoBoxMixin`, `AvisosMixin`, `DreceresMixin`, `ProjecteMixin`…)
  i la classe final `Finestra(InfoBoxMixin, AvisosMixin, …)`: **des de fora es
  veu exactament igual** → els **25 fitxers de test** que instancien `Finestra`
  i criden `w._…` **NO canvien**.
- **Un grup per commit**: bloc → **suite verda** → pyflakes → commit local.
  `main.py` baixaria de ~2.942 a ~**1.500/1.700** línies.

### 16.3 Cost i riscos
- **Temps**: ~1-3 h per grup; **tot, 2-4 dies** fets per blocs (no cal de cop).
- **Risc**: **baix-mig** si es fa fasejat; **alt** si es fa «de cop».
- **Fricció**: l'**estat compartit** a `self` (amb mixins no es toca) i que molts
  tests usen l'**API interna** de `Finestra` (es mantindria).
- **Regla del projecte**: **un sol escriptor per fitxer** → fer-ho amb **OC-8
  aturat** o clarament coordinats.
- **`visor.py`** (3.029 línies) tindria un tractament semblant si mai calgués.

> **1a extracció recomanada (prova de concepte)**: la **caixa d'informació**
> (autocontinguda i ja fresca).

## Criteri de producte actualitzat

La projecta es considera funcionalment preparada per a l’ús del flux principal quan:

- un usuari pot obrir una WAV
- analitzar-la sense terminal
- veure i navegar acords i estructura
- corregir, eliminar o afegir acords i seccions
- exportar el paquet final per a DAW
- i fer-ho tot des d’una sola app, amb un flux clar i repetible.

Aquest criteri ja està cobert en la seva base funcional i validat per regressions del pipeline i la UI.
