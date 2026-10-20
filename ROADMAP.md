# Full de ruta — PROJECTE AUTO CHORDS

> Eina per a **músics multi-DAW**: analitza una cançó (WAV), en deixa **editar
> visualment** els acords i l'estructura, i n'exporta el resultat com a **clips
> WAV** llestos per arrossegar a qualsevol DAW. Tot en català ·
> **GPL-3.0-or-later**.
>
> **v0.7.0** · Estat: **flux de producte estable i multi-SO** · Suite **tota verda**
> + pyflakes net (el **recompte viu, al CI**; no es fixa ací perquè rota).
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

No és àudio: és una **pista visual de noms i durades**. Deliberadament simple —
i per això funciona a tot arreu.

**Cas d'ús**: obrir WAV → analitzar (Chordino + qm) o **treballar a mà** →
editar visualment → exportar → arrossegar al DAW.

**Arquitectura oberta**: el **core** (pipeline + plugins Vamp) és **independent
de la GUI**; l'embolcall (avui **PyQt5**) es pot canviar. Restricció:
**Q9400 sense AVX** → verificar binari a binari abans de canviar de tecnologia.

---

## 2. Estat actual (2026-10-16 · v0.7.0)

> Detall de canvis: [`CHANGELOG.md`](CHANGELOG.md). Detall històric:
> [`ROADMAP_HISTORIA.md`](ROADMAP_HISTORIA.md).

- **Anàlisi** — Chordino (acords) + qm-segmenter (estructura), **opcions reals**
  del detector, BPM (amb `consens`), compàs 1 automàtic (`🧭`), import de
  formats via `ffmpeg`. **L'anàlisi és OPCIONAL**:
  es pot **treballar sense analitzar** (model inicial 1+1 clips editables).
- **Visor DAW-like** — ona, ruler BPM/segons, 2 carrils, **constraint
  propagation** en viu, nanses de resize, **rename inline**, **snap**
  configurable, zoom/pan, play/loop, **multi-selecció**, porta-retalls.
- **Edició** — desfer/refer, **partir/fusionar/duplicar/eliminar**, **renom en
  bloc**, **troba-i-reemplaça** (`Ctrl+H`), **nudge**, **graella configurable**,
  **eina del timeline** (intel·ligent / **marc**), **mode fàcil** (regularitza a
  la graella).
- **Xifrat** — **notació canònica** (font única `app/xifrat.py`), **panell de
  tipus d'acord** (80 tipus) amb **audició** (e-piano, **8 timbres**).
- **Projectes** — autocontinguts (`.acproj` + `audio/` + CSVs + `backup/`),
  autosave i recuperació de sessió.
- **Export** — paquet de WAVs per DAW + **partitura** (MusicXML sempre;
  PDF/MSCZ si hi ha MuseScore).
- **Multi-SO** — AppImage (Linux) · ZIP (Windows x64) · `.app`/DMG (macOS
  10.13+) — tot amb GitHub Actions. Sense signar (assumit).
- **Qualitat** — suite completa als 3 CI; pyflakes net.

---

## 3. Regles d'or i criteris

- **Les regles d'or** (invariants) són a
  **[`docs/REGLES_DE_LA_APP.md`](docs/REGLES_DE_LA_APP.md)** → **cap canvi no les
  pot trencar**. Si una idea hi xoca, es canvia **la funcionalitat**, no la regla.
- **#4 — cobertura total**: la suma dels clips (acords i estructura) = la
  **durada de la WAV**, en qualsevol mode; ho garanteix
  `pipeline.normalitza_cobertura()`.
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
- **En curs**: refinaments d'**edició a la graella** (convencions de DAW) i
  l'**eina del timeline** (intel·ligent / marc). Últim detall: `CHANGELOG` +
  `ROADMAP_HISTORIA.md` §15.

---

## 5. DESPRÉS (Next) — prioritzat (MoSCoW)

### Must (properes línies)
- **Backups: triar/restaurar des de l'app** — llista de còpies (`backup/`) amb
  data-hora → previsualitzar i restaurar (amb confirmació, mai destructiu);
  mostrar què conté cada còpia.
- **Aprofitar l'espai** quan s'amaga el dock «Log · Informació» → que el visor
  creixi i ocupi tota l'alçada.
- **Edició a la graella — pendents d'UX**: fonts de **snap commutables**
  (events/graella), **tolerància de snap** configurable, **`Ctrl+C` no hauria de
  moure el cursor**, mode **«sense graella»** (rubato) i **indicador visual del
  punt d'ancoratge**.
- **Higiene dels tests**: que la suite **esborri els seus `tempdir`** (avui
  deixa ~2,4 GB a `/tmp` per tongada).

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
- **Conversor universal d'àudio** (aprofitar l'`ffmpeg` intern): exportar en
  qualsevol format, lot, normalització **LUFS**, remostreig, mono/stereo, retall.
- **Edició de l'àudio carregat** (**sempre sobre una CÒPIA**): tallar, escurçar/
  expandir, **fades/crossfade**.
- **Guany per clip** (sense tocar la WAV mare) i **fades amb nanses**.
- **Snap a zero-crossings** (talls sense clic).
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

- **Refactor de `app/main.py`** (3.043 línies, `Finestra` = 138 mètodes) en
  mòduls dedicats → **mixins**, per fases. **No urgent** (decisió de l'operador,
  16-10). ✅ *Ben organitzat de moment*; l'històric del disseny és a l'arxiu.
  *(1a extracció proposada: la caixa d'informació.)*
- **Higiene dels tests**: els fixtures no esborren la seva carpeta temporal
  (acumulen a `/tmp`) → `addCleanup(shutil.rmtree, …)` o un helper comú.
- **`app/visor.py`** (3.097 línies) tindria un tractament semblant si mai calgués.

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
- **Detall complet** de tot això (i els brainstorms originals §10–§12, l'anàlisi
  multi-SO, la nota de graella/PPQ, la d'obertura tecnològica i les notes
  d'implementació): **[`ROADMAP_HISTORIA.md`](ROADMAP_HISTORIA.md)**.


apunt usuari: investigar madmom motor neuronal per detectar downbeats i bpm.