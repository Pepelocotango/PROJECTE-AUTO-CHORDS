# Full de ruta — PROJECTE AUTO CHORDS

> Eina per a **músics multi-DAW**: analitza una cançó (WAV), en deixa **editar
> visualment** els acords i l'estructura, i n'exporta el resultat com a **clips
> WAV** llestos per arrossegar a qualsevol DAW. També es vol que permeta
> **edicions d'àudio bàsiques** sobre una còpia del projecte. Tot en català ·
> **GPL-3.0-or-later**.
>
> **v0.8.0** · Estat: **flux de producte estable i multi-SO** · Suite **verda**
> (1.533 tests locals, 1 omés) + `pyflakes` net. El recompte viu és al CI.
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

**Cas d'ús**: obrir WAV → analitzar (Chordino + qm) o **treballar a mà** →
editar visualment → exportar → arrossegar al DAW.

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

## 2. Estat actual (2026-11-02 · v0.8.0)

> Detall de canvis: [`CHANGELOG.md`](CHANGELOG.md). Detall històric:
> [`ROADMAP_HISTORIA.md`](ROADMAP_HISTORIA.md).

- **Anàlisi** — Chordino (acords) + qm-segmenter (estructura), **opcions reals**
  del detector, BPM (amb `consens`), compàs 1 automàtic (`🧭`), import de
  formats via `ffmpeg`. **L'anàlisi és OPCIONAL**:
  es pot **treballar sense analitzar** (model inicial 1+1 clips editables).
- **Mapa de tempo/compàs** — trams editables amb **compassos enters**,
  re-tempo local, `0/0` per al rubato, **marcadors de compàs vs secció**,
  ajust d'un sol BPM per **mínims quadrats** i **validació unificada**
  (BPM 30–350, numerador 1–12, denominador 2/4/8).
- **Visor DAW-like** — ona, ruler BPM/segons, 3 carrils, **constraint
  propagation** en viu, nanses de resize, **rename inline**, **snap**
  configurable, zoom/pan, play/loop, **multi-selecció**, porta-retalls.
- **Edició** — desfer/refer, **partir/fusionar/duplicar/eliminar**, **renom en
  bloc**, **troba-i-reemplaça** (`Ctrl+H`), **nudge**, **graella configurable**,
  **eina del timeline** (intel·ligent / **marc**), **modes de temps** i
  **Quantitza**.
- **Xifrat** — **notació canònica** (font única `app/xifrat.py`), **panell de
  tipus d'acord** (80 tipus) amb **audició** (e-piano, **8 timbres**).
- **Projectes** — autocontinguts (`.acproj` + `audio/` + CSVs + `backup/`),
  autosave i recuperació de sessió.
- **Àudio** — importació convertida a l'única còpia WAV del projecte;
  **retall/afegit de silenci als extrems** amb previsualització, snap, fades
  de 4 ms i desfer/refer conjunt amb el model; **exportació** de la còpia
  editada (WAV 16/24/32, MP3, FLAC, AAC/M4A, OGG, Opus) amb FFmpeg.
- **Export** — paquet de WAVs per DAW + **partitura** (MusicXML sempre;
  PDF/MSCZ si hi ha MuseScore) + `mapa_tempo/` + guia HTML.
- **Multi-SO** — AppImage (Linux) · ZIP (Windows x64) · `.app`/DMG (macOS
  10.13+) — tot amb GitHub Actions. Sense signar (assumit).
- **Qualitat** — suite completa als 3 CI; pyflakes net; **1.452 tests** locals.
- **Pla de tempo** — fases **0–6 fetes**; pendents **7, 10 i 12**;
  ajornades **8, 9 i 11** (vegeu §5).

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
- **Següent**: **fase 10** (motor de detecció amb corpus real; **en curs**,
  pendent del corpus manual de tempo/compàs a `CORPUS/`) i **fase 12**
  (fuzzer al CI, congelació i docs).

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
- **SUBPLÀ PRIORITARI — Rubato i doble graella**: substitueix la fase 7.
  Model B (BPM/compàs derivats, `mapa_tempo.csv`, dues graelles, exportació
  marcada, anacrusi). S'ha d'executar **abans** de les fases 10 i 12. Vegeu
  [`00PER FER/DECISIONS_RUBATO.md`](00PER%20FER/DECISIONS_RUBATO.md).
- **EN CURS (fase 10, 2026-11-03) — Millorar el motor de detecció**: puntuar
  downbeats amb els canvis d'acord i avaluar motors alternatius (madmom,
  Beat This!…) amb l'avaluador de la fase 0. Cap motor nou sense l'OK de
  l'operador. **Bloquejat per corpus real**: sense dades no es pot acceptar
  cap motor.
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
- **Afinador (tuner) de guitarra** — entrada d'àudio → detecció de to →
  nota + cents (natural/tempered). Reutilitzant `app/audio_out.py`.
- **Incorporar `Gt_ALL_Chords_app`** — diapasó, identificador d'acords, filtres,
  centre d'estudi, cercle de quintes, diccionari flamenc… **per fases** i
  **reimplementant** (⚠️ llicència **Polyform Noncommercial** vs **GPL-3.0**).
 
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
- **Conversió avançada d'àudio** (aprofitar l'`ffmpeg` intern): més formats,
  processament en lot, normalització **LUFS**, remostreig i mono/stereo.
- **Edició avançada** més enllà dels extrems: tallar/enganxar al mig,
  **fades ajustables/crossfade** i processament de clips.
- **Guany per clip** (sense tocar la WAV mare) i **fades amb nanses**.
- Els talls continuaran al fotograma triat (sense moure'ls a un zero-crossing);
  els fades automàtics de 4 ms protegeixen les vores.
- **Loudness (LUFS) + espectrograma** i **anàlisi en lot** (informe de carpetes).
- **A/B de dues anàlisis** (detectors/paràmetres) amb commutador.

### Export i partitura
- **Export MIDI** (acords/seccions com a notes o marcadors + **mapa de
  tempo/timesig**); el **PPQ/ticks** només caldria en aquest cas.
- **Generar un projecte de DAW** (`.rpp` de REAPER, `.als` de Live…) amb els
  clips **ja col·locats a la graella** (el «pont» definitiu per a multi-DAW).
- **Plantilles d'export per DAW** (Reaper/Live/Logic) amb noms i carpeta coneguts.
- **Export alternatiu**: **PDF de l'ona+acords**, **Markdown/HTML**,
  **Lyrics+Chords** i **plantilles de paquet** configurables.
- **CSV intel·ligible**, **ABC/LilyPond** i **imatges resumides** de partitura.
- **Cua de render (batch)**: exportar diversos projectes/rangs d'un cop.

### Projectes i flux
- **Pantalla d'inici** (Recents: WAV + projectes · «Nou» · «Obre…»).
- **Arrossega-i-deixa-anar** un WAV/`.acproj` damunt la finestra per obrir-lo.
- **Explorador multimèdia integrat** (arbre + audició ràpida).
- **Documents amb pestanyes** (diverses cançons alhora).
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
- **Multi-idioma (i18n)** de la UI (`gettext`/`QTranslator`) i **docs en anglès**.

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
