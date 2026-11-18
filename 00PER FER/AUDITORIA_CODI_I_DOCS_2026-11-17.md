# Auditoria exhaustiva de codi i documentació — PROJECTE AUTO CHORDS

> **Data:** 2026-11-17 · **Versió auditada:** `v0.9.3`
> **Abast:** Lectura completa de tots els `.md` del repositori (`README.md`, `AGENTS.md`, `DEVELOPING.md`, `ROADMAP.md`, `ROADMAP_HISTORIA.md`, `CHANGELOG.md`, `ARBRE_DIRECTORIS.md`, `SECURITY.md`, `LLICENCIES_TERCERS.md`, `docs/*.md` i `docs/recerca/*.md`) i auditoria en només lectura de `app/`, `eines/` i `tests/` contra el contracte invariant (`docs/REGLES_DE_LA_APP.md` regles 1–12 i §13).
> **Estat:** Cap fitxer de codi modificat (només auditoria).

---

## Índex

1. [Resum executiu](#1-resum-executiu)
2. [Bugs crítics i greus (P0 / P1) — Pèrdua de dades, violació d'invariants i trencament d'Undo](#2-bugs-crítics-i-greus-p0--p1--pèrdua-de-dades-violació-dinvariants-i-trencament-dundo)
3. [Bugs funcionals i matemàtics (P2) — Tempo, compàs, metrònom, graella i export](#3-bugs-funcionals-i-matemàtics-p2--tempo-compàs-metrònom-graella-i-export)
4. [Bugs d'interfície, dreceres i estat intern (P2 / P3)](#4-bugs-dinterfície-dreceres-i-estat-intern-p2--p3)
5. [Incoherències entre documentació (`.md`) i codi](#5-incoherències-entre-documentació-md-i-codi)
6. [Ordre d'actuació recomanat](#6-ordre-dactuació-recomanat)

---

## 1. Resum executiu

L'arquitectura general del projecte (model unificat de clips `Clip(ini, fi, payload)`, separació `pipeline_*` / `visor_*` / `timeline_*`, motor `TempoMap` i persistència atòmica) és sòlida i té una cobertura de tests molt alta. Tanmateix, les iteracions ràpides recents (introducció de `TramMapa` amb `tipus`/`agrupacio`/`n`/`beat_unit`, eliminació de `offset`/`pre-roll`/`Ref. recalc`, nous compassos amb denominador `16` i `2`, i botons `Aplica` individuals a la franja Editor) han deixat **punts on camins antics basats en 5-tuples conviuen amb `TramMapa`**, així com **forats al sistema d'undo/redo** i **assumpcions de denominador 4** en algorismes de metrònom, detecció i conversió de posicions.

Les troballes principals s'agrupen en 4 blocs:
- **Pèrdua silenciosa de metadades del mapa de tempo (`rubato`, `agrupacio`, `n`, `beat_unit`)** en passar per funcions de `tempo_map` (5-tuples) sense `reenganxa_metadades`, en el diàleg `DialegTempoMapa`, i en editar els extrems d'àudio (`audio_edit.py`).
- **Trencament de la pila de Desfer/Refer (`Ctrl+Z`)**: els 4 botons `Aplica` individuals de la franja Editor (`BPM`, `Compàs`, `Agrupació`, `N`) muten el model i avancen la base sense crear pas d'undo; i 6 camins d'edició deixen `_undo_pending` obert quan fallen amb `ValueError`.
- **Errors matemàtics en compassos `x/16`, `x/8` i `x/2`**: el metrònom en mapa variable o amb agrupació explícita salta a passos de `0.5` negres i perd la meitat dels clics en `x/16`; `beats_a_trams` duplica el BPM en `2/2`; i les conversions `C.B ↔ segons` ignoren el denominador.
- **Divergències als 4 punts de validació (Regles 1–12 i §13)**: l'anàlisi desa acords crus no canònics al CSV, l'exportació d'`estructura_ABC.csv` no passa el `mapa_viu` ni `den`, i l'edició d'àudio (§13.9) pot deixar trams amb `N` fraccionari.

---

## 2. Bugs crítics i greus (P0 / P1) — Pèrdua de dades, violació d'invariants i trencament d'Undo

### 2.1. Els 4 botons «Aplica» per variable de la franja Editor no tenen Desfer (`Ctrl+Z`)
- **Ubicació:** `app/visor_editor.py:176-230` (`_aplica_editor_var`), connectats a `app/visor.py:278-279` (`ed_bpm_aplica`), `294-295` (`ed_compas_aplica`), `312-313` (`ed_agr_aplica`) i `332-333` (`ed_n_aplica`).
- **Problema:** `_aplica_editor_var` crida directament `self.edita_tempo_objectiu(...)`, `self.edita_compas_objectiu(...)`, `self.aplica_tempo_trams(...)` o `self.edita_n_compassos(...)` **sense envoltar l'operació amb `self._undo_marca()` i `self._undo_commit()`**.
- **Impacte:** Com que `aplica_tempo_trams` executa `self._undo_touch_base()` (`app/visor_tempo.py:610`) quan `_undo_pending` és `None`, el canvi sobreescriu `_undo_base` directament i **no es pot desfer amb `Ctrl+Z`**. Incompleix la **Regla #11** (`docs/REGLES_DE_LA_APP.md:84-86`, `:97-98`).

### 2.2. Marques d'undo penjades (`_undo_pending`) quan una edició falla
- **Ubicació:**
  - `app/visor.py:3568` → `3575-3577` (`parteix_acord`)
  - `app/visor.py:3922` → `3930-3932` (`parteix_seccio`)
  - `app/visor.py:3980` → `3984-3986` (`fusiona_acord`)
  - `app/visor.py:4005` → `4009-4011` (`fusiona_seccio`)
  - `app/visor_editor.py:457` → `463-466` (`_aplica_editor`, branca acord)
  - `app/visor_editor.py:488` → `495-497` (`_aplica_editor`, branca secció)
- **Problema:** Es crida `self._undo_marca()` abans d'un bloc `try ... except ValueError: return`, sense `finally: self._undo_commit()`. Si la validació llança `ValueError`, la funció retorna deixant `self._undo_pending` ple.
- **Impacte:** Mentre `_undo_pending` no és `None`, `_undo_touch_base()` (`app/visor.py:993-994`) queda desactivat i la propera operació d'undo apila un estat antic o desfà operacions intermèdies que no li corresponen. (Compareu amb `_aplica_editor_tempo` a `app/visor_editor.py:330-396`, que sí que usa `try ... finally: self._undo_commit()`).

### 2.3. `DialegTempoMapa` destrueix `rubato`, `agrupacio`, `n` i desalinea `beat_unit`
- **Ubicació:** `app/dialeg_tempo_mapa.py:28-40`, `197-208` i `210-221`.
- **Problema:**
  1. `trams()` (`:218-220`) reconstrueix tots els trams com `mapa_tempo.TramMapa(float(t[0]), float(t[1]), float(t[2]), "normal", f"{int(t[3])}/{int(t[4])}", "", None, unit)`: **converteix silenciosament tots els trams `rubato` en `normal`**, esborra qualsevol `agrupacio` explícita i posa `n=None`. Viola **§13.7** (`docs/REGLES_DE_LA_APP.md:257-258`).
  2. `_elimina()` (`:197-208`) elimina una fila de `self._trams`, però **no elimina l'element corresponent de `self._unitats`**, desplaçant les unitats `beat_unit` de totes les files posteriors.
  3. A més, `app/main.py:1063` (`_tempo_mapa_ui`) aplica el resultat amb `vr.aplica_tempo_validat(dlg.trams())` sense `_undo_marca()`/`_undo_commit()`, de manera que editar el mapa des del diàleg tampoc no es pot desfer amb `Ctrl+Z`.

### 2.4. Pèrdua de metadades en el «Recalcul fix» del diàleg de tram i en reparacions
- **Ubicació:**
  - `app/visor_tempo.py:855-858` i `:870` (`_recalcula_tram_dialeg`, branca `mode == "fix"`)
  - `app/visor.py:2776-2788` i `:2856` (`repara_fronteres` / `_aplica_mapa_reparat`)
- **Problema:** `tempo_map.canvia_compassos_tram` i `tempo_map.repara_fronteres` retornen **5-tuples** `(ini, fi, bpm, num, den)`. En passar-les directament a `self.aplica_tempo_trams(nous)` **sense cridar `mapa_tempo.reenganxa_metadades(trams, nous)`**, tots els clips del mapa perden `tipus="rubato"`, `agrupacio`, `n` i `beat_unit`.
- **Contrast:** A `app/visor_tempo.py:1057-1063` (`canvia_compassos_tram` del visor) sí que es fa `nous = mapa_tempo.reenganxa_metadades(trams, nous)` just abans d'`aplica_tempo_trams`.

### 2.5. Edició d'àudio (§13.9): deixa `N` fraccionari, perd metadades de `TramMapa` i desalinea `beat_unit`
- **Ubicació:** `app/audio_edit.py:164-269` (`transforma_model`).
- **Problema:**
  1. **Violació de §13.4 i §13.9 (`docs/REGLES_DE_LA_APP.md:271-272`):** En retallar o afegir silenci als extrems (`RETALLA_INICI`, `RETALLA_FINAL`, `SILENCI_INICI`, `SILENCI_FINAL`), la duració del primer o últim tram de tempo canvia per `delta` segons sense arrodonir `N` ni recalcular el BPM per mantenir `N` enter. Es retorna `TramMapa(..., n=None)` i es desa al CSV amb `N` fraccionari implícit.
  2. **Pèrdua de `tipus` i `agrupacio` (`:266-268`):** Reconstrueix tots els `TramMapa` amb `"normal"` i `""`, esborrant el flag `rubato` i l'agrupació de tots els trams del projecte.
  3. **Desalineació de `beat_unit` en `RETALLA_INICI` (`:164-170`, `:186-194`, `:263-265`):** Si el retall d'inici elimina el tram 0 sencer (perquè `delta >= trams[0].fi`), `nou_trams[0]` passa a ser l'antic tram 1 (o posterior), però el bucle final li assigna `units[0]` (la unitat de l'antic tram 0 eliminat).

### 2.6. Round-trip trencat entre `a_tupla_completa` i `des_de_tupla`
- **Ubicació:** `app/mapa_tempo.py:189-223` i `app/tempo_map.py:284-300`.
- **Problema:**
  - `a_tupla_completa(tram)` (`app/mapa_tempo.py:213-217`) retorna una tupla de **8 elements**: `(ini, fi, bpm, tipus, compassos, agrupacio, n, beat_unit)`, on l'índex 3 és `tipus` (`"normal"`/`"rubato"`) i l'índex 4 és `compassos` (`"4/4"`).
  - Si aquesta tupla es passa a `des_de_tupla(tram)` (`app/mapa_tempo.py:208-210`), fa `ini, fi, bpm, num, den = tram[:5]` i executa `int(num)` sobre `"normal"` → **`ValueError: invalid literal for int() with base 10: 'normal'`**.
  - Igualment, en tupla de 7 elements, `tempo_map._expandeix_segments` (`app/tempo_map.py:296-298`) interpreta el 7è element com a `beat_unit`, mentre que `mapa_tempo.des_de_tupla` (`:203-207`) l'interpreta com a `n` tret que sigui un string dins `bpm_unit.UNITATS`.

### 2.7. `Projecte.crea` sobreescriu `mapa_tempo.csv` existent en migració *in situ*
- **Ubicació:** `app/projecte.py:306-312` i `:604-621`.
- **Problema:** Dins `Projecte.crea()`, `acords.csv` i `estructura_ABC.csv` només s'inicialitzen si `not os.path.isfile(...)`, però a la línia `311-312` es crida `pipeline.desa_tempo_map(carpeta, [(0.0, durada, bpm, bpb, den)])` **incondicionalment**, fins i tot quan `permet_existent=True` (`importa_autochords` o obertura *in situ*), destruint qualsevol `mapa_tempo.csv` previ de la carpeta.

---

## 3. Bugs funcionals i matemàtics (P2) — Tempo, compàs, metrònom, graella i export

### 3.1. Metrònom: els compassos `x/16` perden la meitat dels clics en mapa variable o amb agrupació explícita
- **Ubicació:** `app/metronom.py:249-273`.
- **Problema:** Quan `mapa` no és constant **o** té agrupacions explícites (`mapa.te_agrupacions_explicites()`), la branca `click_unit == "auto"` avança `q` a passos de **`0.5` negres (corxera)** (`q += 0.5`, línia 273) i comprova `s == 1`. En qualsevol compàs amb denominador `16` (`4/16`, `6/16`, `7/16`, `12/16`…), cada temps del denominador val **`0.25` negres (semicorxera)**. Com que `q` salta de `0.5` en `0.5`, només visita els temps imparells (`b = 1, 3, 5...`) i **es menja la meitat dels clics del compàs**.
- ** agreujant:** `edita_compas_objectiu` (`app/visor_tempo.py:396-398`) i `_aplica_editor_tempo` (`app/visor_editor.py:298-300`) desglossen i escriuen una agrupació explícita cada cop que es canvia el compàs a la GUI; per tant, fins i tot un projecte amb un sol tram entra en aquesta branca (`mapa.te_agrupacions_explicites() == True`).

### 3.2. «Recalcul mòbil» al diàleg del tram aplica el BPM antic del camp i ignora el BPM recalculat
- **Ubicació:** `app/visor_tempo.py:860-863` (`_recalcula_tram_dialeg`).
- **Problema:** Després de cridar `tempo_recalc.recalculca_tram(...)` i obtenir `res["bpm"]`, `res["num"]`, `res["den"]`, `res["n"]` (i mostrar `res["bpm"]` a l'usuari a la línia 852), la branca `mode != "fix"` crida:
  ```python
  nous = mapa_tempo.recalcula_tram_c(
      trams, idx, self._durada_wav(),
      n=int(res["n"]), bpm=float(bpm_camp),
      num=int(res["num"]), den=int(res["den"]), camp="n")
  ```
  Dins `recalcula_tram_c` (`app/mapa_tempo.py:297-305`), per a un tram interior utilitza `bpm` (`bpm_camp`, no `res["bpm"]`) per calcular `dur_nou` i deixa `bpm_final = bpm_camp`. És a dir, **no aplica el BPM que el motor de recalcul ha calculat**.

### 3.3. Franja Editor: canviar el compàs amb `Enter` / «Aplica» no actualitza `beat_unit` ni aplica el Cas B
- **Ubicació:** `app/visor_editor.py:251`, `293-301` i `373-376` (`_aplica_editor_tempo`).
- **Problema:**
  1. Quan l'usuari canvia el compàs a la franja Editor (p. ex. de `4/4` a `6/8`) i prem el botó general `Aplica` (o `Enter`), `bpm = self.bpm_entrada(self.ed_nom.text())` (`:251`) llegeix el BPM amb la **unitat antiga** (`negra`) i a la línia `376` crea el `TramMapa` nou conservant `tr.beat_unit` (`negra`), en lloc de derivar `negra_punt`.
  2. Això contradiu **§13.4** (`docs/REGLES_DE_LA_APP.md:160-164`: *«Canviar la signatura actualitza la unitat si esta era la derivada. En canviar només el compàs, per defecte es conserva el BPM visible (pulsació, Cas B)»*) i divergeix del botó petit `ed_compas_aplica` (`:203`, que crida `edita_compas_objectiu` i sí que aplica el Cas B i deriva la unitat).

### 3.4. `beats_a_trams` assumeix que cada beat detectat és una negra i duplica el BPM en `2/2`
- **Ubicació:** `app/tempo.py:396-438`.
- **Problema:** `pas = max(1, int(cada_compassos)) * int(num)` avança `num` beats per compàs, però `bq = float(num) * 4.0 / float(den)` mesura el compàs en negres. En `2/2` (`num=2, den=2, bq=4`), per a `cada_compassos=1` agafa `pas=2` beats; si els beats són negres (`ibi = 0.5 s` a 120 BPM), `fi - base = 1.0 s`, `m = max(1, round(1.0 / (4 * 0.5))) = max(1, 0) = 1`, i calcula `bpm = 4 * 60 * 1 / 1.0 = 240 BPM` (**el doble del real**).

### 3.5. Conversions `C.B ↔ segons` ignoren el denominador i truncen a 60 s a `temps_ui.py`
- **Ubicació:** `app/temps_ui.py:58-83` (`_cb_a_secs`, `_secs_a_cb`) i `app/visor.py:3385-3421`.
- **Problema:**
  1. A `app/temps_ui.py:68-71`, `_cb_a_secs` fa `beat_len = 60.0 / bpm` (sempre negra, ignorant `den`) i a la línia 71 fa `return max(0.0, min(60.0, n * beat_len))` — **qualsevol posició més enllà del segon 60 queda truncada a `60.0 s`**.
  2. A `app/visor.py:3389-3398` i `3413-3421`, el fallback quan `tempo_map` és `None` també calcula `beat_len = 60.0 / bpm` i `SB = bpb * 8` sense aplicar `4.0 / den`, de manera que en `6/8` o `2/2` els compassos duren el doble o la meitat.

### 3.6. Graella `pulse` i metrònom amb unitat explícita s'ancoren a `q=0` global i no a l'inici del compàs
- **Ubicació:** `app/tempo_map.py:487-507` (`grid_lines`, `kind == "pulse"`) i `app/metronom.py:274-294`.
- **Problema:** Quan hi ha un canvi de compàs que no cau en un múltiple global de `pas_q` des de `q=0` (p. ex. un compàs de `5/8` seguit d'un `6/8`), `k = int(math.ceil(q_ini / pas_q))` alinea les línies de `pulse` respecte de `q=0` i no respecte de l'inici del compàs del tram (`b0_q`). Les línies de pols queden desfasades respecte de les línies de `bar` i del metrònom.

### 3.7. Exportació: `estructura_ABC.csv` no rep el `mapa_viu` ni `den` a `exporta_total`
- **Ubicació:** `app/pipeline_export.py:269-278`.
- **Problema:** Dins `exporta_total()`, quan s'exporta l'estructura es crida:
  - `desa_abc_csv(abc, seccions, bpm, log, lliure=not tempo_fix, bpb=bpb)` (`:269-270`) **sense passar `mapa=mapa_viu` ni `den=den`**.
  - `fer_abc(csv_seg, abc, bpm, log, lliure=not tempo_fix, bpb=bpb, durada=total_s)` (`:277-278`) **sense `den` ni `mapa`**.
- **Impacte:** Mentre que el visor (`app/visor.py:1125-1128`) i la guia HTML (`app/pipeline_export.py:233-240`) sí que calculen els compassos amb `mapa` i `den`, l'acció d'exportar (`Ctrl+E`) sobreescriu `estructura_ABC.csv` calculant `compas_ini` i `compas_fi` com si tota la cançó fos a BPM constant i amb denominador `4`. Viola els **4 punts de validació** i la **Regla #12**.

### 3.8. Anàlisi d'acords desa xifrats crus (no canònics) a `acords.csv`
- **Ubicació:** `app/feines.py:190-206`, `:295-316`, `app/postproc.py:279` i `app/pipeline_io.py:198-211`.
- **Problema:** Els acords que surten de Chordino (`Fm`, `C#maj7`, `Ebm`…) passen per `postproc.processa_acords_csv` i `desa_acords_csv` sense passar per `pipeline.saneja_nom_acord` (`xifrat.normalitza_xifrat`).
- **Impacte:** Després d'analitzar, `acords.csv` i els WAVs exportats tenen noms no canònics (`Fm`), mentre que `partitura.py:144` sí que els normalitza (`F-`), creant divergència entre CSV/WAVs i MusicXML fins que l'usuari edita manualment cada acord. (Reconegut com a pendent a `docs/recerca/NOTACIO_XIFRAT.md:78-83`).

### 3.9. Validació incompleta de BPM i `N` enter en carregar CSV extern i en recalc automàtic
- **Ubicació:**
  - `app/mapa_tempo.py:85-112` (`TramMapa.__post_init__`) i `:452-457` (`normalitza_trams_map`): `TramMapa` no valida que `bpm` estigui dins `30–350`, i `normalitza_trams_map` crida `ajusta_compassos_sencers(..., estricte=False)` que, si el BPM necessari per fer `N` enter surt de `30–350`, **conserva el `N` fraccionari** i el desa a `TramMapa.n` (contra **§13.4**: *«No existix l'estat amb N fraccionari»*).
  - `app/tempo_map.py:1826-1838` (`_recalcula_costats`): si el millor candidat de `recalculca_tram` no encaixa amb la `beat_unit` actual del tram, no filtra els candidats per triar-ne un que sí que encaixi, sinó que descarta directament el recalcul i deixa el tram vell (contra **§13.6**: *«En recalc automàtic es filtren els candidats per la unitat actual i, si no n'hi ha cap, es conserva el valor anterior amb avís»*).
  - `app/tempo_map.py:1740-1744` i `:1801-1804` (`mou_frontera_retempo`): si es crida amb `ref_base=None` (valor per defecte), el veí dret pren com a referència el seu propi BPM/compàs en lloc del clip a l'esquerra del seleccionat (**§13.5**).

### 3.10. Truncament de BPM decimal a `genera_guia_html`
- **Ubicació:** `app/pipeline_derivats.py:272` i `app/partitura.py:117`.
- **Problema:** `genera_guia_html` formata el BPM amb `%d BPM` (truncant qualsevol decimal, p. ex. `82.5` → `82`), i `partitura.llegeix_bpm_bpb_de_guia` llegeix aquest enter com a fallback.

---

## 4. Bugs d'interfície, dreceres i estat intern (P2 / P3)

### 4.1. La drecera `Ctrl+Alt+V` (enganxar sense snap) és inabastable
- **Ubicació:** `app/menus.py:95-96`, `282`, `app/info_box.py:156` i `app/visor.py:2925`.
- **Problema:** La documentació (`docs/ESQUEMA_UI.md:214`), el diàleg de dreceres (`menus.py:282`) i la caixa d'informació (`info_box.py:156`) anuncien `Ctrl+Alt+V` per enganxar sense snap. Però a `menus.py:95-96` només es registra l'acció `Ctrl+V`; quan l'usuari prem `Ctrl+Alt+V`, Qt no activa el `QAction` de `Ctrl+V` perquè sobra el modificador `Alt`. Per tant, la comprovació `QApplication.keyboardModifiers() & Qt.AltModifier` a `app/visor.py:2925` no s'executa mai des del teclat.

### 4.2. Contaminació del BPM/compàs del transport (`self.bpm` / `self.bpb`) pel clip seleccionat
- **Ubicació:** `app/main.py:652-666` (`_sincronitza_temps_del_visor`) vs `app/analisi_ui.py:134, 206, 329`, `app/export_ui.py:69, 317, 331` i `app/visor_ui.py:73`.
- **Problema:** `_sincronitza_temps_del_visor` escriu als camps interns `self.bpm` i `self.bpb` de la finestra els valors de `vr.tempo_objectiu_vals()` (que són els del **tram seleccionat**, p. ex. tram 2, no necessàriament el tram 0). Quan s'executa `Analitza`, `Exporta` o es recarrega el visor (`_carrega_visor`), aquests mòduls llegeixen `self._bpm_val()` assumint que és el transport (tram 0). (Nota: `app/projecte_ui.py:120-129` ja té un pegat explícit per esquivar-ho en desar el `.acproj`, però la resta de consumidors no).

### 4.3. Fuita de widgets a `self._stack` en recarregar el visor
- **Ubicació:** `app/visor_ui.py:148-153` (`_carrega_visor`).
- **Problema:** Cada vegada que s'obre un projecte, es reverteix o acaba una anàlisi, `_carrega_visor` crea un `Visor` nou i fa `self._stack.addWidget(visor_widget)` sense fer `removeWidget` ni `deleteLater()` del widget del visor anterior, acumulant pàgines ocultes en memòria amb els seus `TimelineView` i arrays PCM.

### 4.4. Restes de `0/0` i «En segons (rubato)» que xoquen amb §13.7
- **Ubicació:**
  - `app/dialeg_tram_tempo.py:56-62`, `196-198` i `983-986`: El diàleg del tram encara crea el checkbox `self._lliure = QCheckBox("En segons (rubato)")` (tot i estar ocult), amb text d'ajuda obsolet.
  - `app/temps_ui.py:13` i `22-28`: `_parse_compas` i `tempo_map.valida_tempo` (`app/tempo_map.py:44-48, 71-74`) encara accepten `0/0`, cosa que fa que si arriba a `TramMapa` (`app/mapa_tempo.py:58-64`) peti amb `ValueError` no controlat en alguns fluxos.

### 4.5. `info_box.py`: dreceres hardcodejades i temps de rotació inconsistent
- **Ubicació:** `app/info_box.py:14-17`, `125-202` i `230`.
- **Problema:**
  1. Les dreceres que mostra el rotatori de la caixa d'informació estan escrites a mà (`Espai`, `T`, `E`, `Ctrl+D`…) i no consulten `self._valor_drecera(...)` (`app/dreceres_ui.py:49-52`), de manera que si l'usuari canvia les dreceres a *Ajuda ▸ Configura les dreceres…*, la caixa d'informació mostra les antigues (**Regla #5**).
  2. `_INFO_ROTACIO_S` val `8.0` segons (`:17`), però el peu HTML de la mateixa caixa (`:230`) i `docs/ESQUEMA_UI.md:348` diuen `14 s`.

---

## 5. Incoherències entre documentació (`.md`) i codi

Tot i que `AGENTS.md` estableix que el codi mana sobre els `.md` (tret de `docs/REGLES_DE_LA_APP.md`), s'han detectat les següents contradiccions als documents actuals:

1. **Agrupació per defecte de `5/8` i `7/8` a `TAULA_COMPASSOS_X_X.md`:**
   - A `docs/recerca/TAULA_COMPASSOS_X_X.md:62` i `:146-147` diu que l'app usa per defecte `5` i `7`, però a la taula gran del mateix document (`:119` i `:121`) diu: *«l'app usa 3+2»* (per a `5/8`) i *«l'app usa 2+2+3»* (per a `7/8`), amb accents `1,4` i `1,3,5`. Al codi (`app/tempo_map.py:194-206`), l'agrupació per defecte és `(5,)` i `(7,)` amb accent només a `1`.
2. **Rubato i `AVIS_APROXIMACIO.txt` / MusicXML (`README.md`, `ESQUEMA_UI.md` vs `REGLES_DE_LA_APP.md`):**
   - `README.md:107` i `docs/ESQUEMA_UI.md:392-397` diuen que en marcar un rang com a rubato *«l'app deriva BPM i compassos, conserva els segons i identifica la graella exportada com a aproximada»*.
   - En canvi, `docs/REGLES_DE_LA_APP.md:254-258` (§13.7) i el codi actual estableixen que el rubato és **només un flag de notació** i que convertir a rubato **no deriva BPM ni parteix el clip**. A més, `app/partitura.py` ja no escriu «graella aproximada» (només `"Rubato"`), mentre que `app/pipeline_export.py:299-311` encara genera el fitxer anomenat `AVIS_APROXIMACIO.txt` tot i que el seu text intern diu el contrari (*«El rubato només canvia la notació/exportació; el tempo i els compassos són els mateixos que els d'un tram normal»*).
3. **Metrònom a `docs/ESQUEMA_UI.md:71` vs `:404` i `REGLES_DE_LA_APP.md:156`:**
   - A `docs/ESQUEMA_UI.md:71` (taula de la finestra principal, fila `self.b_metro`) diu: *«El clic per defecte segueix la unitat de pols del tram (no el denominador si el tram diu una altra cosa)»* i posa `7/8 = 2+2+3, 5/8 = 3+2`.
   - A `docs/ESQUEMA_UI.md:404` i `docs/REGLES_DE_LA_APP.md:156-158` diu el que realment fa el codi: per defecte el metrònom clica el **denominador** (`click_unit="auto"`) i `5/8` / `7/8` tenen agrupació per defecte `5` i `7`.
4. **Diagrama ASCII i panell de xifrat a `docs/ESQUEMA_UI.md`:**
   - El diagrama ASCII (`docs/ESQUEMA_UI.md:24-27`) encara dibuixa `[Anàlisi guiat]` i `BARRA 1b [Analitza]`, quan la barra s'ha reordenat i el botó es diu `Guia ràpida`.
   - A `docs/ESQUEMA_UI.md:68` diu *«62 tipus»* al panell «Tipus d'acord», mentre que a la línia `44` i al codi (`xifrat.TAULA_TIPUS`) en són **92**.
   - A `docs/ESQUEMA_UI.md:291` i `294` diu que a la llista de tempo ⑭ els rubatos mostren «segons» a la columna Compàs; al codi actual (`app/visor_llistes.py`) mostren el seu compàs (`R 4/4`).
5. **Docstring de `Visor.quantitza_bpm` (`app/visor.py:2250-2253`) i `README.md:96`:**
   - Afirmen que *«els rubatos no es quantitzen»*, però `mapa_tempo.quantitza_bpm` (`app/mapa_tempo.py:475-478`) sí que quantitza els rubatos igual que els trams normals (coherent amb §13.7).
6. **Referències a fitxers `.md` eliminats dins `CHANGELOG.md` i `ROADMAP.md`:**
   - `ROADMAP.md:349-355` i `395` enllacen a `00PER FER/PLA_SIMPLIFICACIO_TEMPO.md` i `00PER FER/DECISIONS_RUBATO.md`, que ja no existeixen a `00PER FER/`.

---

## 6. Ordre d'actuació recomanat

Quan l'operador autoritzi tocar codi, l'ordre més segur (seguint el cicle **test de regressió en vermell → fix mínim → verificació als 4 punts**) és:

1. **Integritat de `TramMapa` i metadades (2.3, 2.4, 2.6):**
   - Corregir `des_de_tupla` per acceptar tuples de 8 camps (`a_tupla_completa`).
   - Fer que `DialegTempoMapa` preservi `tipus`, `agrupacio`, `n` i sincronitzi `_unitats` en eliminar files.
   - Afegir `reenganxa_metadades` al camí `mode == "fix"` de `_recalcula_tram_dialeg` i a `repara_fronteres`.
2. **Sistema de Desfer/Refer (2.1, 2.2):**
   - Embolcallar `_aplica_editor_var` amb `_undo_marca()` i `try ... finally: _undo_commit()`.
   - Posar `try ... finally: self._undo_commit()` als 6 mètodes d'edició d'acords/seccions que poden retornar abans d'hora.
3. **Edició d'àudio §13.9 i migració de projecte (2.5, 2.7):**
   - A `audio_edit.transforma_model`, conservar `tipus`/`agrupacio`/`beat_unit` del tram d'origen i passar el mapa resultant per l'ajust de compassos sencers (§13.4 / §13.9).
   - A `Projecte.crea`, no sobreescriure `mapa_tempo.csv` si ja existeix quan `permet_existent=True`.
4. **Càlculs musicals i exportació (3.1–3.8):**
   - A `metronom.py:254-273`, usar `pas_q = 0.25` (o `0.125`) en lloc de `0.5` perquè els compassos `x/16` facin tots els clics.
   - A `_recalcula_tram_dialeg` (`mode == "mobil"`), passar `bpm=float(res["bpm"])`.
   - A `_aplica_editor_tempo`, derivar `beat_unit` i aplicar el Cas B quan canvia el compàs.
   - A `pipeline_export.exporta_total`, passar `mapa=mapa_viu, den=den` a `desa_abc_csv` i `fer_abc`.
   - Normalitzar els noms d'acord amb `saneja_nom_acord` en desar des de l'anàlisi/`postproc`.
5. **UI, dreceres i documentació (4.1–4.5, 5):**
   - Registrar la drecera `Ctrl+Alt+V` (o ajustar l'acció d'enganxar sense snap), netejar widgets vells de `self._stack` en recarregar el visor, i alinear els `.md` amb `make docs`.
