# Full de ruta — PROJECTE AUTO CHORDS

> Eina per a **músics multi-DAW**: analitza una cançó (WAV), en deixa **editar
> visualment** els acords i l'estructura, i n'exporta el resultat com a **clips
> WAV** llestos per arrossegar a qualsevol DAW. També es vol que permeta
> **edicions d'àudio bàsiques** sobre una còpia del projecte. Tot en català ·
> **GPL-3.0-or-later**.
>
> **v0.8.0** · Estat: **flux de producte estable i multi-SO** · Suite **verda**
> (1.563 tests locals, 1 omés) + `pyflakes` net. El recompte viu és al CI.
>
> 📌 Aquest fitxer és el full **viu**. L'històric (Fases A–E, anàlisi multi-SO,
> graella/PPQ, obertura tecnològica, brainstorms originals, notes…) és a
> **[`ROADMAP_HISTORIA.md`](ROADMAP_HISTORIA.md)**.

---

## 1. Visió i objectiu

**El problema**: passar els acords d'una cançó a un DAW sol demanar MIDI,
plugins o transcriure a mà.

**La solució** (raó de ser del projecte): **un fitxer WAV per acord/secció**,
**silenciós**, on:
- **Nom = acord** (`Am.wav`) → al DAW el clip es llegeix com l'acord.
- **Durada = durada de l'acord** → arrossegats, dibuixen la progressió sencera.
- **Zero plugins**: qualsevol DAW arrossega una carpeta d'àudio.
- **Doble pista**: `wavs_acords/` + `wavs_estructura/`, sincronitzables.

Els clips exportats no són àudio musical: són una **pista visual de noms i
durades**, deliberadament simple i per això compatible amb qualsevol DAW.
L'edició bàsica del fitxer d'àudio carregat és una funció complementària
parcialment implementada, amb un abast molt més limitat que un editor general.

**Cas d'ús oficial**: vegeu el **flux de l'usuari** a
[`AGENTS.md` §Abast i flux](AGENTS.md#-abast-i-flux-de-lusuari--font-única)
(obrir WAV → analitzar o treballar a mà → editar visualment → exportar →
arrossegar al DAW).

**Línia de producte complementària (implementada)**: la importació
ja desa una única còpia WAV de treball dins del projecte i els backups també la
inclouen; l'original es conserva. Les nanses permeten retallar o allargar amb
silenci els extrems i desfer/refer l'edició junt amb el model musical.
`Fitxer ▸ Exporta àudio…` desa el resultat en WAV, MP3, FLAC, AAC/M4A, OGG o
Opus. L'abast és a [`docs/REGLES_DE_LA_APP.md` §13.9](docs/REGLES_DE_LA_APP.md).

**Arquitectura oberta**: el **core** (pipeline + plugins Vamp) és **independent
de la GUI**; l'embolcall (avui **PyQt5**) es pot canviar. Restricció:
**Q9400 sense AVX** → verificar binari a binari abans de canviar de tecnologia.

---

## 2. Estat actual i relleu de sessió (2026-11-06)

> **Norma per a agents:** qualsevol agent que treballi en el codi ha
> d'**actualitzar aquesta secció** en plegar (reescriure-la, **no**
> incrementalment: reflectir l'estat actual, no l'historial). L'historial viu al
> [`CHANGELOG.md`](CHANGELOG.md). La definició de **què fa l'app i què queda
> fora** és a [`AGENTS.md`](AGENTS.md#-abast-i-flux-de-lusuari--font-única).

**Fases** del pla `00PER FER/PLA_SIMPLIFICACIO_TEMPO.md`: **0–7 fetes**. La **10**
(motor de detecció amb corpus real) està **oberta i bloquejada pel corpus
manual**; la **12** (congelació, higiene i CI) està **en curs**. **8** (MIDI),
**9** (anàlisi guiada) i **11** (flux del 90 %) queden **ajornades**.

> **Prioritat:** simplificar el producte. L'abast vigent és a
> [`AGENTS.md` §Abast i flux](AGENTS.md#-abast-i-flux-de-lusuari--font-única):
> només el nucli (obrir → analitzar opcional → editar 3 pistes → exportar →
> desar). La **fase 10**, el **rubato avançat** i l'**export MIDI/DAW** queden
> **ajornats sense data**.

**Fet (2026-11-06):**
- **Refactor complet**: `pipeline.py` queda en **89 línies** (façana) +
  `pipeline_*`; `main.py` **1.511** + `*_ui`/`feines`/`opcions`; `visor.py`
  **4.447** + `visor_*`; `timeline.py` **2.135** + `timeline_geometry`;
  `dialegs.py` **25** + `dialeg_*`. Tests de contracte a
  `test_pipeline_contracte` i `test_timeline_contracte`.
- **Guiat v2/v3 retirat**: codi d'ancoratges eliminat; el flux viu són els
  **marcadors en viu** (`+`) i la **Guia ràpida**.
- **Docs al mínim**: `AGENTS`/`DEVELOPING` escurçats; `Makefile`, generadors de
  la taula de mòduls i `make docs-check`.
- **Suite**: **1.490 tests OK** (1 skip), `pyflakes` net i smoke OK.

**Fet recentment (2026-11-07):** simplificació del mapa de temps (fases F0–F5
del [`PLA_MAPA_TEMPS`](docs/recerca/PLA_MAPA_TEMPS.md)): el **tram 0 és un clip**
(el transport és només una vista), **model permissiu** amb mínim de **86 ms**,
**recalcul guiat** per una **referència base manual** de la barra 2 (BPM +
compàs `x/x`, desada a `tempo.ref`) i **marcadors com a `N` fix**. Els beats
detectats poden corregir el compàs/X-X i `N` de la base (14 → `7/4` N=2; 8 →
`4/4` N=2). Suite **1517 OK** (1 skip), `pyflakes` net.

**Pendent:**
- **Fase 10**: motor de detecció amb corpus real (bloquejat pel corpus manual).
- **Fase 12**: congelació, higiene i CI; inclou el **CI automàtic en push/PR**
  (proposat, encara no activat).
- **Rubato avançat** i **MIDI/export de projecte DAW**: ajornats sense data.
- **`ARBRE_DIRECTORIS.md`**: encara snapshot manual; pendent generador + test.
- Corpus real de tempo pendent (l'avaluador sintètic funciona).

Commit de referència: `31d23df` (refactor modular).

---

## 3. Regles d'or i criteris

- **Les regles d'or** (invariants) són a
  **[`docs/REGLES_DE_LA_APP.md`](docs/REGLES_DE_LA_APP.md)** → **cap canvi no les
  pot trencar**. Si una idea hi xoca, es canvia **la funcionalitat**, no la regla.
- **Criteri de «producte preparat»**: *obrir WAV → analitzar sense terminal →
  veure/editar acords i estructura → corregir/afegir/eliminar → exportar per
  DAW, tot en una sola app.* → **✅ cobert** (validat per regressions).
- **«Fet»** = hi ha test (smoke + unittest), la **suite és verda** i el
  comportament respecta les regles d'or.
- **Prioritat**: estabilitat → UX/visualització → configuració/automatització →
  export/desplegament.

---

## 4. ARA (Now)

- **Cicle de treball** (acordat): **OC-8 = codi** (blocs amb tests verds →
  **para**) · **OC-5 = tests + documentació + commits locals**.
  **Cap push ni compilacions** sense l'OK de l'operador.
- **Fet (2026-11-02)**: P0 de la revisió — **suite verda** (1.452 tests,
  1 omés), vistes `ESQUEMA_UI` al dia i indicador del TAP coherent (només
  actua amb un tram de tempo seleccionat).
- **Fet (2026-11-02)**: **fase 6** — `Fitxer ▸ Exporta àudio…` amb diàleg
  natiu, perfils WAV/MP3/FLAC/AAC/OGG/Opus i detecció d'encoders en temps
  d'execució; escriptura atòmica i protecció de la còpia de treball.
- **Fet (2026-11-01)**: fases **0–5** del
  [`PLA_SIMPLIFICACIO_TEMPO`](00PER%20FER/PLA_SIMPLIFICACIO_TEMPO.md) —
  línia base i avaluador, validació unificada, fuzzer i proposta de regles,
  TAP robust, compàs vs secció i ajust d'un BPM per mínims quadrats.
- **Fet (2026-11-02)**: **subplà de rubato complet (fases 1–5)** —
  [`00PER FER/DECISIONS_RUBATO.md`](00PER%20FER/DECISIONS_RUBATO.md).
  Inclou la fase 7 del pla de simplificació.
- **Fet (2026-11-03)**: anàlisi del projecte de prova
  `AUTOCHORDS_01 POLICE_convertit`; model coherent i límits del pre-roll,
  notació crua i offset documentats al subplà de rubato.
- **Següent (2026-11-05)**: **consolidar el nucli** i simplificar (abast a
  [`AGENTS.md`](AGENTS.md#-abast-i-flux-de-lusuari--font-única)). La **fase 10**
  (motor de detecció) i el **rubato avançat** queden **ajornats sense data**.
- **EN CURS (2026-11-03) — fase 12: congelació i higiene**:
  - **congelades** les funcions laterals **afinador de guitarra** i
    **`Gt_ALL_Chords_app`**; no s'eliminen, només no es desenvolupen fins que
    l'operador ho decidisca;
  - higiene de tests: `tests/_temporals.py` és obligatori a tots els mòduls de
    test; la suite no deixa temporals;
  - nou workflow manual **`qualitat.yml`** amb fuzzer i proves sintètiques
    **no bloquejants**; no usa cap corpus real;
  - pendent: tancament final i actualització d'estat quan la fase 10 es
    considere estable.

---

## 5. DESPRÉS (Next) — prioritzat (MoSCoW)

### Must (properes línies)
- **FET (fase 1) — validació unificada de BPM/compàs**: límits compartits a
  `app/limits.py` (BPM 30–350, numerador 1–12, denominador 2/4/8), `0/0`
  explícit per al rubato, errors visibles i reparació avisada dels CSV.
  Els casos d'auditoria del 25-10-2026 queden coberts per proves; qualsevol
  regressió nova torna a aquesta llista.
- **FET — edició bàsica d'àudio**: còpia de treball interna,
  retall/afegit als extrems, previsualització, snap compartit, fades de 4 ms,
  sincronització amb el model i desfer/refer conjunt. L'original no se
  sobreescriu.
- **FET (fase 6) — Exportar àudio editat amb FFmpeg**: `Fitxer ▸ Exporta
  àudio…` obri el diàleg natiu de desar; perfils WAV (16/24/32 bits, 44,1/48
  kHz), MP3 128/192/320, FLAC, AAC/M4A, OGG i Opus. Només s'ofereixen els
  còdecs que el `ffmpeg` del paquet pot escriure (`-encoders`). Escriptura
  atòmica, log visible i protecció de la còpia de treball. Vegeu
  [`docs/REGLES_DE_LA_APP.md` §13.9](docs/REGLES_DE_LA_APP.md).
- **AJORNAT (sense data) — Rubato i doble graella avançada**: el que ja hi ha
  implementat es conserva; no s'amplia fins que l'operador ho decidisca. Vegeu
  [`00PER FER/DECISIONS_RUBATO.md`](00PER%20FER/DECISIONS_RUBATO.md).
- **AJORNAT (sense data) — Millorar el motor de detecció (fase 10)**: puntuar
  downbeats amb els canvis d'acord i avaluar motors alternatius. Cap motor nou
  sense l'OK de l'operador. No es treballa ara.
- **PENDENT — Backups: triar/restaurar des de l'app** — llista de còpies
  (`backup/`) amb data-hora → previsualitzar i restaurar (amb confirmació,
  mai destructiu); mostrar què conté cada còpia.
- **PENDENT — Aprofitar l'espai** quan s'amaga el dock «Log · Informació» →
  que el visor creixi i ocupi tota l'alçada.
- **PENDENT — Edició a la graella, UX**: fonts de **snap commutables**
  (events/graella), **tolerància de snap** configurable, **`Ctrl+C` no hauria
  de moure el cursor**, mode **«sense graella»** (rubato) i **indicador visual
  del punt d'ancoratge**.

> ✅ **Fet (2026-10-18/19) — higiene dels tests**: `tests/_temporals.py`
> intercepta i esborra els `tempdir` en plegar. La suite ja no acumula GB a
> `/tmp`. Es manté com a norma per a qualsevol test nou.

### Should
- **AJORNAT (sense data) — Exportació del mapa de tempo a DAWs** (2026-11-04):
  - **WAV**: pot portar `cue`/`LIST adtl` (marcadors) i, com a molt, un BPM
    únic (`ACID`); **no hi ha un mapa de tempo complex estàndard** ni un
    comportament comú entre DAWs. El `bext`/`iXML` no és un tempo map portable.
  - **MIDI**: exportar `mapa_tempo.mid` (tipus 1, pista de conductor) amb
    `Set Tempo`, `Time Signature` i markers. És el format més portable
    (Cubase/Logic/Pro Tools/Reaper/Studio One…), amb el rubato aproximat per
    events de tempo densos. L’offset/anacrusi necessita marker o projecte DAW.
  - **Reaper**: generar un `.rpp` amb l’àudio, `TEMPO`, `TIMESIG`, markers i
    offset; és el camí exacte per a Reaper, però no intercanviable.
  - **Cues al WAV** per a compàs/secció, com a complement per als DAWs que
    importen marcadors.
  - **Clic de referència WAV** generat amb el mapa, com a alternativa
    universal que qualsevol DAW pot importar i alinear.
  - **BPM per clip**: afegir-lo al `manifest.csv`/`ACID`/`iXML` pot ser útil
    com a metadada, però **no converteix cada clip en un canvi de tempo del
    DAW**. Els clips (sobretot si són silenciosos) no defineixen el tempo
    global; el mapa ha d’anar en un MIDI, un `.rpp` o un altre sidecar.
  - Ordre recomanat: **MIDI + cues + clic** per a multi-DAW; **`.rpp`** per a
    Reaper; el BPM per clip queda com a metadada opcional, no com a substitut
    del mapa.
- **Confiança dels acords** (`loglikelihood` del Chordino) → **ressaltar a la UI**
  els acords dubtosos per revisar-los.
- **Tonalitat** → si mai cal, mostrar-la i, si escau, **paleta d'acords**
  (suggerir diatònics).

### Could
- **`Ctrl+Shift`+arrossegar també per a les seccions** (paritat d'edició #11 amb els acords).
- **Afegeix clips des del timeline** (ara només des del menú de la llista).
- **Overflow de barres d'eines** a < 1300 px (avui es tallen).
- **Beats/bars del qm** per **auto-ajustar la graella** (ara només el 1r downbeat)
  i conservar les **etiquetes de repetició** del qm-segmenter.
- **Configuració persistent** d'usuari (ara només `opcions_detecta.json`).
- **Notes de l'acord** (`chordnotes` del Chordino) a l'Editor.

---

## 6. MÉS ENDAVANT (Later) — idees en un sol lloc, per temes

> Cap **no és planificada**; es valoraran. Cap no pot trencar les regles d'or.
> Fora d'abast vigent: `AGENTS.md` §«FORA d'abast».

### Edició i graella
- **Ripple edit explícit** (commutador: en moure/inserir, la resta s'arrossega o no).
- **Historial d'undo/redo** amb **llista de passos** i salt directe.
- **Modes de graella** (`straight` · **tresets** · **puntets** · `swing` ·
  `custom`) al `grid_plan` + **display `compàs.temps.tick`**.
- **Tempo map / rampes** (BPM variable, compassos 4/4→3/4).
- **Representació de compàs amb 3 xifres** (`1.1.3`…) i decidir si és només
  visual o també al CSV/export.
- **Selecció per rectangle** ja existeix («marc») → afinar-la.

### Navegació i vista
- **Mini-mapa (overview)** de tota la cançó per saltar i seleccionar.
- **Zoom vertical de l'ona** + **carrils amagables i alçada ajustable**.
- **Zoom a la selecció/loop** i **auto-scroll** fi.
- **Tema clar/fosc** (amb opció de seguir el sistema) i **paleta de colors**
  per acords/seccions; **ona amb gradient** per secció.
- **Línia de temps dual segons/BPM**, sincronitzada amb el cursor i la selecció.

### Marques i rang
- **Marcadors amb nom** («solo», «pont»…) + **llista** per saltar-hi (`Tab`) i
  **export de cue-sheet**.
- **Selecció de rang temporal** (arrossegar el regle) per limitar-hi accions.

### So, edició d'àudio i anàlisi
- Els talls continuaran al fotograma triat (sense moure'ls a un zero-crossing);
  els fades automàtics de 4 ms protegeixen les vores.
- **A/B de dues anàlisis** (detectors/paràmetres) amb commutador.
- **Panell avançat de paràmetres del processament** (Chordino/QM) amb mode
  bàsic/avançat.

### Export i partitura
- **Export MIDI** (acords/seccions com a notes o marcadors + **mapa de
  tempo/timesig**); el **PPQ/ticks** només caldria en aquest cas.
- **Generar un projecte de DAW** (`.rpp` de REAPER, `.als` de Live…) amb els
  clips **ja col·locats a la graella** (el «pont» definitiu per a multi-DAW).
- **Plantilles d'export per DAW** (Reaper/Live/Logic) amb noms i carpeta coneguts.
- **Export alternatiu**: **PDF de l'ona+acords**, **Markdown/HTML**,
  **Lyrics+Chords** i **plantilles de paquet** configurables.
- **CSV intel·ligible**, **ABC/LilyPond** i **imatges resumides** de partitura.
- **Convenció semàntica de noms i ordre** dels clips exportats.

### Projectes i flux
- **Pantalla d'inici** (Recents: WAV + projectes · «Nou» · «Obre…»).
- **Arrossega-i-deixa-anar** un `.acproj` damunt la finestra per obrir-lo (els
  àudios ja s'hi poden arrossegar des del 2026-11-05).
- **Explorador multimèdia integrat** (arbre + audició ràpida).
- **Copiar/enganxar entre projectes** (buffer persistent).
- **«Repeteix l'última acció»** (`Ctrl+R`) i **plantilles de projecte**.
- **Presets d'export** i **CLI/headless** (`auto-chords analitza tema.wav`).
- **Suport de vídeo** (treure'n l'àudio) via `ffmpeg`.

### Musical (ajuda a l'usuari)
- **Tonalitat → paleta d'acords** (escala + diatònics verd/vermell + selector).
- **Opacitat segons la confiança** de la detecció.
- **Notes/anotacions per clip** («revisar», «dubtós»).
- **Entrada d'acords** per teclat a pantalla / MIDI (a més del panell).

### Configuració i UX
- **Editor de dreceres** (reassignar + perfils) i **modificadors de ratolí**.
- **Workspaces (screensets)**, panells flotants/acoblables i pantalla completa.
- **Preferències completes** (motor d'àudio, autosave, graella per defecte, tema).
- **Barra de transport configurable** i **peu d'estat** (motor, sr, CPU, autosave).
- **Paleta de comandes** (`Ctrl+K`) i **rellotge gran** (big clock).
- **Accessibilitat** (navegació completa per teclat + lectors de pantalla).

### El que encara queda obert de l'edició
- **Snap a esdeveniments** — ja **fet**; queden **fonts de snap commutables** i
  **tolerància configurable** (vegeu §5, Must).
- **Cursor amb snap** — avui el cursor és lliure (per navegació fina); valorar
  una opció commutable.
- **Indicador de MODE** i **línia guia de snap** més visible durant el drag.

---

## 7. Deute tècnic

- ~~**Refactor de `app/main.py`**~~ → ✅ **FET** (2026-11-06): 4.858 → **1.511
  línies**; extret a `*_ui`, `feines`, `opcions`, `info_box` i `drag_drop_ui`.
- ~~**`app/visor.py`**~~ → ✅ **FET** (2026-11-06): 5.602 → **4.447 línies**;
  extret a `visor_*`.
- ~~**`app/timeline.py`**~~ → ✅ **FET** (2026-11-06): extret
  `timeline_geometry.py`.
- ~~**Codi d'anàlisi guiada en stand-by**~~ → ✅ **RETIRAT** (2026-11-06):
  s'han eliminat la cadena `_guia_*`/`_analisi_guitat`/`_analisi_ancoratges`,
  `FilGuiaBpm`, els diàlegs `DialegGuiaDownbeat`/`DialegGuiaBpm` i els mòduls
  `app/ancoratges.py`/`app/dialeg_ancoratges.py`. Els marcadors en viu (`+`)
  cobreixen el flux. Detall al `CHANGELOG.md`.
- ~~**Higiene dels tests**~~ → ✅ **FET** (2026-10-18/19): `tests/_temporals.py`
  esborra els temporals en plegar; la suite no deixa GB a `/tmp`.
- **`ARBRE_DIRECTORIS.md`**: encara és un snapshot manual; pendent generador +
  test perquè no es desfasï.

---

## 8. Fites i història

- **Fases A–E ✅** — A: visor navegable · B: edició/correcció · C: flux producte ·
  D: interacció DAW-like (D.1/D.2 ✅, D.3 nice-to-have) · E: autodetecció
  avançada (Queen Mary).
- **Multi-SO ✅** — fulla de ruta Windows/macOS (v0.5.1–v0.6.0) → **els 3 builds
  verds** i **release v0.7.0 (BETA)** amb els 3 paquets.
- **Xifrat canònic + panell de tipus + audició · eina del timeline
  (intel·ligent/marc, tecla `E`) · `Ctrl+Shift`+arrossegar = duplicar · treballar
  sense analitzar** — 15–16/10/2026.
- **Anàlisi per etapes + velocitat de reproducció** — 21/10/2026: les 3
  etapes de l'anàlisi (BPM · acords · estructura) són **caselles
  independents** al diàleg d'autodetecció i «Analitza» **també detecta el
  BPM** (i l'aplica al mapa); el transport guanya **selector de velocitat
  0,5–3×** amb el **to mantingut** (`ffmpeg atempo`), amb cursor, loop i
  metrònom alineats (`factor` a `metronom.mescla_metronom`).
- **Pla de simplificació del tempo — fases 0–6 ✅ (2026-11-01/02)**: avaluador
  sintètic (`eines/avalua_tempo.py`), validació unificada, fuzzer d'invariants
  i proposta de regles fusionada, TAP robust amb destí visible, marcadors de
  compàs vs secció, ajust d'un sol BPM per mínims quadrats amb partició
  recursiva i **exportació d'àudio amb FFmpeg**. Detall: `CHANGELOG.md`.
- **Detall complet** de tot això (i els brainstorms originals §10–§12, l'anàlisi
  multi-SO, la nota de graella/PPQ, la d'obertura tecnològica i les notes
  d'implementació): **[`ROADMAP_HISTORIA.md`](ROADMAP_HISTORIA.md)**.


apunt usuari: investigar madmom motor neuronal per detectar downbeats i bpm.
exportar partitures amb silenci al pentagrama, que sonin només els acords xifrats
play a diferents velocitats — ✅ FET (21-10: selector 0,5–3× al transport amb
  `ffmpeg atempo`, to mantingut; cursor, loop i metrònom alineats)
acabar separació analitza tot/només estructura/només acords/ etc.. — ✅ FET
  (21-10: 3 caselles independents al diàleg d'autodetecció —BPM · acords ·
  estructura— i «Analitza» ja detecta també el BPM)
actualitzar documentació V8.x — ✅ FET (2026-11-02)
millorar welcome mode fàcil ( text millor explicat de flux de treball)
millorar info box
