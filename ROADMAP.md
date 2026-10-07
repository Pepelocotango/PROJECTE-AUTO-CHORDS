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
2. 🪄 L’app la processa amb **Chordino** (acords) i **Segmentino**
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

El **core del projecte** (detecció amb Chordino+Segmentino, validació
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
- 🐧 **Linux prioritari** (AppImage idealment); multi-OS és nice-to-have.

## Estat actual (2026-10-07 · v0.3.0)

El projecte ja ha passat de prototip funcional a flux de producte útil:

- app principal única i estable
- **visor DAW-like (QGraphicsView)** amb ona, ruler BPM/segons i 2 carrils (acords + estructura)
- **constraint propagation live** — moure l’inici d’un element ajusta automàticament el final de l’anterior i l’inici del següent
- **nanses de resize** als extrems dels acords i les seccions + cos central per moure’l sencer
- **rename inline** (doble-clic → edició al lloc, Enter desa, Esc cancel·la)
- **snap intel·ligent** a compàs/beat/corxera (tempo_fix) o a 0.1/0.5/1/5 s (mode lliure) segons el zoom
- **zoom** amb Ctrl+Roda (centrat al cursor) i **pan** amb Roda sola
- procés d’anàlisi amb una sola acció clara (`Processa`)
- revisió i edició d’acords i seccions des del visor
- export final separat i explícit (`Finalitza i publica`)
- llançament directe des de la carpeta del projecte
- bloqueig de doble instància per evitar sobreposició d’aplicacions
- **auditoria de seguretat/estabilitat aplicada**: clamp de temps, tipus d’excepció específics, `_proc_lock`, `safe_filename`, parser CSV robust, validació WAV (sr/ch > 0)

La base funcional i el nou visor estan validats. El que queda són millores de polish, estabilització i les funcionalitats pràctiques descrites a l’apartat següent.

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

## Fase D — Interacció DAW-like ⏳ *(properà)*

Aquesta fase és **el “kit de la qüestió”** del projecte: fer que el visor
interactiu sigui tan usable i natural com un DAW modern treballant amb
clips d’àudio. La detecció i l’export ja funcionen; ara toca que **editar
sigui un plaer** i no una fricció.

**Regla d’or** (ja implementada): cada clip d’acord o d’estructura
**sempre acaba o comença el següent** — és a dir, el final d’un element
és l’inici del veí (propagació de constraint en temps real).

### D.1 — Crítiques (sense elles el visor no és usable)

> ✅ **FET (2026-10-06)**: clic a un clip mou el cursor · `Delete` elimina
> l'element seleccionat (amb undo) · `Ctrl+D` duplica (repartint la durada,
> amb undo) · distinció visual **seleccionat** (vora cian gruixuda) vs
> **actiu** (fons verd) amb els colors a `app/theme.py` · **menú contextual**
> (botó dret) sobre un clip amb Duplica/Elimina/Reanomena. També s'ha afegit
> un **metrònom** (🥁, només mode BPM · compàs, volum propi) i la **GUI
> reorganitzada** amb el timeline al centre.

- **Click a un clip → mou cursor de play allà** (l’acció més bàsica d’un
  DAW que actualment **no funciona**).
- **Selecció persistent visual** — l’element seleccionat canvia de color
  clarament (vora groga o color de fons diferent).
- **Duplicar acord/estructura** — `Ctrl+D` o menú contextual; el duplicat
  s’insereix immediatament al costat i propaga el constraint.
- **Eliminar amb tecla `Delete`** (a més del menú contextual existent).
- **Línia guia de snap més visible** durant el drag — color groc discontínu
  que marqui on caurà el temps resultant.
- **Feedback visual quan s’arrossega** — el cursor canvia segons la zona
  (ja implementat parcialment) + highlight dels veins afectats.

### D.2 — Importants (per semblar un DAW de veritat)

- **Multi-selecció** amb `Ctrl+click` (afegir) i `Shift+click` (rang), i
  poder moure/duplicar/eliminar el grup.
- **Dreceres de teclat estàndard**: `Ctrl+C/V/X` (copy/cut/paste),
  `Ctrl+D` (duplicar), `Ctrl+Z/Y` (desfer/refer), `Delete` (eliminar),
  `Space` (play/pause), `Enter` (editar).
- **Undo/Redo** amb stack d’accions (cobreix qualsevol modificació manual).
- **Scroll drag amb mouse** per desplaçar-se horitzontalment quan el
  cursor agafa la forma de “mà” (com Reaper).
- **Indicador visual del mode actiu** (BPM/compàs vs segons) al ruler.

### D.3 — Nice-to-have (quan la D.1 i D.2 estiguin consolidades)

- **Drag-and-drop extern** d’un WAV per afegir manualment un acord nou.
- **Tooltips** sobre botons i accions (a més dels que ja existeixen).
- **Selecció amb drag-rectangle** (“lasso”) per seleccionar varis elements
  d’un cop.
- **Accel·leradors personalitzables** per l’usuari avançat.

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

## Prioritat de millores restants

### Alta
- **barra de menús**: completar les accions pendents i els estats
  dinàmics (vegeu §10-F)
- confirmacions d’export més guiades i logs de resultat més rics
- ajust final del layout i etiquetatge per a usuaris no tècnics
- packaging més net i docs d’ús final

### Mitjana
- ~~historial d’edicions / desfer~~ ✅ **(fet v0.1.5: undo/redo + menú Edita)**
- opcions de preset de tempo i export
- validacions visuals addicionals de l’ABC

### Baixa
- suport d’altres formats de sortida
- configuració persistents d’usuari

## Àrees de futur: investigar, valorar i discutir

Aquestes són idees i oportunitats que queden pendents de revisió i que convé gestionar com a feina de producte i d’arquitectura, no com a correccions urgents del flux principal.

### 1) Compassos amb 3 xifres i formats de temps avançats

- investigar com es representarà correctament la estructura en compàs amb notació de 3 xifres, per exemple `1.1.3` o `1.1.50`
- definir si el format és estrictament de visualització o si també entra dins el CSV de referència
- valorar si la codificació del compàs ha de tenir un esquema explícit separant `compàs`, `beat` i `subdivisió`
- decidir si l’editor ha de mostrar sempre “segons” o “compàs” o si ha d’haver un mode dual amb canvi contextual
- garantir que aquesta representació no trenqui el model que ja usa temps en segons com a font de veritat

### 2) Control del processament automàtic i paràmetres d’algoritme

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

- valorar exportar no només WAVs i carpetes de clips, sinó també altres sortides útils
- possibilitats a estudiar:
  - MusicXML
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
| Fitxer | Obre WAV… `Ctrl+O` · Finalitza i publica · Obre la carpeta de sortida · Surt `Ctrl+Q` |
| Edita | **Desfer `Ctrl+Z`** · **Refer `Ctrl+Y`** · Refer alt. `Ctrl+Shift+Z` · Paràmetres… |
| Selecciona | Marca inici de loop (A) · Marca fi de loop (B) · Activa/desactiva loop |
| Visualitza | Zoom + `Ctrl++` · Zoom − `Ctrl+-` · Zoom total `Ctrl+0` · Mostra el visor |
| Analitza | Processa el WAV `F5` |
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
  llindars de Chordino/Segmentino (vegeu §2).
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
