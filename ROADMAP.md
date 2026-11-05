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
Opus. L'abast és a [`docs/EDICIO_AUDIO.md`](docs/EDICIO_AUDIO.md).

**Arquitectura oberta**: el **core** (pipeline + plugins Vamp) és **independent
de la GUI**; l'embolcall (avui **PyQt5**) es pot canviar. Restricció:
**Q9400 sense AVX** → verificar binari a binari abans de canviar de tecnologia.

---

## 2. Estat actual i relleu de sessió (2026-11-05)

> **Norma per a agents:** qualsevol agent que treballi en el codi ha
> d'**actualitzar aquesta secció** en plegar (reescriure-la, **no**
> incrementalment: reflectir l'estat actual, no l'historial). L'historial viu al
> [`CHANGELOG.md`](CHANGELOG.md). La definició de **què fa l'app i què queda
> fora** és a [`AGENTS.md`](AGENTS.md#-abast-i-flux-de-lusuari--font-única).

Fases del pla `00PER FER/PLA_SIMPLIFICACIO_TEMPO.md` completades: **0, 1, 2, 3,
4, 5, 6** i **7** (coberta pel subplà de rubato). La **10** (motor de detecció)
queda **oberta**; la **12** (congelació, higiene i CI) està **en curs**.
Ajornades: **8** (MIDI), **9** (anàlisi guiada) i **11** (flux del 90 %).

> **Prioritat actual (2026-11-05): simplificar el producte.** L'abast vigent és
> a [`AGENTS.md` §Abast i flux](AGENTS.md#-abast-i-flux-de-lusuari--font-única):
> només el nucli (obrir → analitzar opcional → editar 3 pistes → exportar →
> desar). La **fase 10**, el **rubato avançat** i l'**export MIDI/DAW** queden
> **ajornats sense data**; no s'hi treballa fins que el nucli estiga estable i
> l'operador ho decidisca. Les funcions congelades són al mateix document.

Fet recentment (2026-11-02/05):
- **Drag & drop d'àudio** (2026-11-05): es pot arrossegar una cançó des de
  l'explorador (Windows/macOS/Linux) sobre qualsevol part de la finestra i
  s'obre amb el flux de `Obre àudio…` (conversió ffmpeg, projecte existent o
  ubicació nova). Llig `text/uri-list` (`QMimeData.urls()` +
  `QUrl.toLocalFile()`) amb fallback de text pla; accepta només fitxers
  locals existents de la llista d'`app.ffmpeg`, com a còpia, i fa la feina
  fora del `dropEvent`. Mòdul `app/drag_drop.py`; tests a
  `tests/test_drag_drop.py`. Suite: **1.610 tests**, 1 omés.
- **Base d'agents d'OpenCode** (2026-11-04): config a `opencode.json` (l'únic
  que es llig), `.opencode/` local via `.gitignore`, **6 subagents**
  (`explorer`, `tester`, `reviewer`, `docs`, `audio-dsp`, `pipeline`) amb
  `deepseek-v4.1-flash`, **5 skills** amb frontmatter i els commands
  `/qualitat`, `/estat` i `/regles`. Detall: `.opencode/README.md` (local, no versionat).
- **Contracte de beats sencers** (2026-11-04): els clips de BPM/compàs ja no
  exigeixen compassos enters; han de contindre almenys un beat sencer de la
  graella del Snap (QM o BPM/compàs), inclòs `1/4`. El `+` sempre usa el beat
  QM més pròxim; l’ajust prioritza conservar el BPM i canviar el compàs. El botó
  **«Ajusta BPM al compàs»** força compassos sencers de manera explícita. En
  fixar l’offset, el pre-roll es recalcula com un compàs sencer amb el compàs
  que deixa el BPM més pròxim al clip següent. Docs:
  `docs/REGLES_DE_LA_APP.md` §13.4–13.6 i `docs/ANALISI_BPM.md`.
- **Analitza BPM** (2026-11-04): acció separada de «Analitza» (que queda per
  a acords + estructura), motors **nostre**/QM, sensibilitat 0–100 i línies
  sobre l'ona. El motor per defecte és **Queen Mary**; el mode per defecte és
  **només beats** (sense BPM, compàs ni downbeats); l'altre mode afig
  BPM/downbeats. L'acció **Ajusta la graella
  als beats QM** snapeja els marcadors de compàs i recalcula el BPM; `+`
  continua creant compàs + secció; els dubtes del snap es revisen en un
  diàleg no modal, el metre d’un tram s’edita amb **Compàs del marcador…** i
  el Snap **Beats QM** encaixa cursor/clips/`+` a les línies de QM.
  Detall: `docs/ANALISI_BPM.md`.
- **Fase 12 (en curs)**: afinador i `Gt_ALL_Chords_app` congelats; tots els
  tests importen `_temporals`; `.github/workflows/qualitat.yml` executa fuzzer i
  proves sintètiques sense bloquejar.
- **Subplà de rubato — fases 1-5**: motor pur `app/rubato.py`, model
  unificat `app/mapa_tempo.py` (`mapa_tempo.csv`, `FORMAT = 3`, rebuig de
  projectes vells), visor/graella, accions de crear/convertir rubato i
  exportació amb avís aproximat. Suite completa: **1.610 tests**, 1 omés.
- **Anàlisi del projecte de prova** `AUTOCHORDS_01 POLICE_convertit`:
  model coherent i cobertura exacta; documentats els límits del pre-roll a la
  partitura, els noms d'acord crus de l'anàlisi i la precisió de l'offset.
- **Unitat de BPM**: selector global negra / negra amb punt / corxera /
  blanca; el metrònom té una unitat de clic independent (auto/negra/negra amb punt/corxera/blanca). El model continua en negres/min i la unitat es desa al `.acproj`.
  Suite: **1.610 tests**, 1 omés.
- **Metrònom per denominador**: el beat és `4/den` negres; `6/8`, `9/8` i
  `12/8` cliquen corxeres, `2/2` blanques; accents de compàs i grup, modes
  Auto/Compàs/Temps/Grup i selector al transport.
- **Regressió blindada (2026-11-04)**: només la frontera **0→1** és pre-roll.
  Les fronteres 2–3 i 3–4 no s'han de tornar a enviar a
  `mou_frontera_preroll`; tenen test propi.
- **Pendent explícit (2026-11-04)**: l'edició automàtica/directa de la WAV per
  completar el pre-roll o el primer compàs **no està implementada**; no s'ha
  d'afegir silenci automàticament ni trencar el flux manual de nanses.
- **Fase 6**: `Fitxer ▸ Exporta àudio…` amb diàleg natiu, perfils
  WAV/MP3/FLAC/AAC/OGG/Opus, detecció d'encoders en temps d'execució,
  escriptura atòmica i protecció de la còpia de treball.
- **P0**: suite verda, `pyflakes` net, vistes `ESQUEMA_UI` al dia i indicador
  del TAP coherent amb el comportament real.
- Downbeat (offset) absolut: no es mou en ajustar BPM.
- T (tap tempo): només amb clip de tempo seleccionat.
- Fases 4 i 5: compàs ≠ secció i ajust d'un sol BPM per mínims quadrats.

Corpus real de tempo encara pendent (l'avaluador sintètic funciona).
Commit de referència: `22affe2` (drag & drop: els fills no capturen l'àudio i docs al dia).

---

## 3. Regles d'or i criteris

- **Les regles d'or** (invariants) són a
  **[`docs/REGLES_DE_LA_APP.md`](docs/REGLES_DE_LA_APP.md)** → **cap canvi no les
  pot trencar**. Si una idea hi xoca, es canvia **la funcionalitat**, no la regla.
- **#4 — cobertura total**: la suma dels clips (acords i estructura) = la
  **durada de la WAV**, en qualsevol mode; ho garanteix
  `pipeline.normalitza_cobertura()`.
- **Retrocompatibilitat = NO és prioritat** (decisió 2026-11-02): els canvis
  de format poden rebutjar projectes vells amb un error clar; no es fan
  migracions ni es mantenen dos formats. Vegeu `AGENTS.md` i `DEVELOPING.md`.
- **Criteri de «producte preparat»**: *obrir WAV → analitzar sense terminal →
  veure/editar acords i estructura → corregir/afegir/eliminar → exportar per
  DAW, tot en una sola app.* → **✅ cobert** (validat per regressions).
- **«Fet»** = hi ha test (smoke + unittest), la **suite és verda** i el
  comportament respecta les regles d'or.

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
  [`docs/EDICIO_AUDIO.md`](docs/EDICIO_AUDIO.md).
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
> **Fora d'abast (congelat):** afinador de guitarra i `Gt_ALL_Chords_app`. No
> es planifiquen; vegeu `AGENTS.md` §Fora d'abast.

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

### Edició i graella
- **Ripple edit explícit** (commutador: en moure/inserir, la resta s'arrossega o no).
- **Historial d'undo/redo** amb **llista de passos** i salt directe.
- **Modes de graella** (`straight` · **tresets** · **puntets** · `swing` ·
  `custom`) al `grid_plan` + **display `compàs.temps.tick`**.
- **Tempo map / rampes** (BPM variable, compassos 4/4→3/4).
- **Selecció per rectangle** ja existeix («marc») → afinar-la.

### Navegació i vista
- **Mini-mapa (overview)** de tota la cançó per saltar i seleccionar.
- **Zoom vertical de l'ona** + **carrils amagables i alçada ajustable**.
- **Zoom a la selecció/loop** i **auto-scroll** fi.
- **Tema clar/fosc** (amb opció de seguir el sistema) i **paleta de colors**
  per acords/seccions; **ona amb gradient** per secció.

### Marques i rang
- **Marcadors amb nom** («solo», «pont»…) + **llista** per saltar-hi (`Tab`) i
  **export de cue-sheet**.
- **Selecció de rang temporal** (arrossegar el regle) per limitar-hi accions.

### So, edició d'àudio i anàlisi
- Els talls continuaran al fotograma triat (sense moure'ls a un zero-crossing);
  els fades automàtics de 4 ms protegeixen les vores.
- **A/B de dues anàlisis** (detectors/paràmetres) amb commutador.

> **Fora d'abast (congelat):** edició avançada d'àudio (fades ajustables,
> guany per clip, crossfade i snap a zero-crossings). Vegeu `AGENTS.md`
> §Fora d'abast.

### Export i partitura
- **Export MIDI** (acords/seccions com a notes o marcadors + **mapa de
  tempo/timesig**); el **PPQ/ticks** només caldria en aquest cas.
- **Generar un projecte de DAW** (`.rpp` de REAPER, `.als` de Live…) amb els
  clips **ja col·locats a la graella** (el «pont» definitiu per a multi-DAW).
- **Plantilles d'export per DAW** (Reaper/Live/Logic) amb noms i carpeta coneguts.
- **Export alternatiu**: **PDF de l'ona+acords**, **Markdown/HTML**,
  **Lyrics+Chords** i **plantilles de paquet** configurables.
- **CSV intel·ligible**, **ABC/LilyPond** i **imatges resumides** de partitura.

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

> **Fora d'abast (congelat):** i18n, multi-pestanya i batch/render queue. No es
> planifiquen; vegeu `AGENTS.md` §Fora d'abast.

### El que encara queda obert de l'edició
- **Snap a esdeveniments** — ja **fet**; queden **fonts de snap commutables** i
  **tolerància configurable** (vegeu §5, Must).
- **Cursor amb snap** — avui el cursor és lliure (per navegació fina); valorar
  una opció commutable.
- **Indicador de MODE** i **línia guia de snap** més visible durant el drag.

---

## 7. Deute tècnic

- **Refactor de `app/main.py`** (4.746 línies, `Finestra` = 202 mètodes) en
  mòduls dedicats → **mixins**, per fases. **No urgent** (decisió de l'operador,
  16-10). ✅ *Ben organitzat de moment*; l'històric del disseny és a l'arxiu.
  *(1a extracció proposada: la caixa d'informació.)*
- **`app/visor.py`** (5.602 línies, 211 mètodes) tindria un tractament semblant
  si mai calgués; `app/timeline.py` ja és a 2.189 línies.
- **Codi d'anàlisi guiada en stand-by**: v2 (`_analisi_guitat`) i v3
  (`_analisi_ancoratges` + `dialeg_ancoratges.py`, ~957 línies) es conserven
  sense entrada a la UI (decisió 21-10-2026). No és un bug; es revisarà si es
  reprén el flux (fase 9).
- ~~**Higiene dels tests**~~ → ✅ **FET** (2026-10-18/19): `tests/_temporals.py`
  esborra els temporals en plegar; la suite no deixa GB a `/tmp`.

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
