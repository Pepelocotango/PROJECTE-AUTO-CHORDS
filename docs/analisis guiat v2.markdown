# Especificació Tècnica: Anàlisi Guiat v2 (Flux Musical Interactiu)

> **Destinatari:** Agent de desenvolupament (OC / Claude / Assistent de codi).  
> **Àmbit:** Projecte AUTO CHORDS (v0.8.x).  
> **Objectiu:** Transformar l'«Anàlisi guiat» actual en una estació d'audició interactiva, fluida i orientada al músic per construir mapes de tempo variables fiables sense fricció cognitiva.  
> **Restricció fonamental:** Complir estrictament les 12 Regles d'Or (`docs/REGLES_DE_LA_APP.md`), el contracte de compassos enters (`docs/REGLES_TEMPS_GRID.md`) i les limitacions de maquinari (sense AVX, `numpy < 2`, PyQt5, multi-SO).

---

## 1. Visió de Producte i Filosofia

En cançons amb tempo humà (directes, rubato, fluctuacions, canvis de compàs o secció), la detecció global d'una sola xifra falla o simplifica en excés. D'altra banda, dibuixar el mapa a mà compàs a compàs és lent i tediós.

L'**Anàlisi Guiat v2** implementa un model **híbrid (algorisme + decisió auditiva del músic)**:
1. La màquina analitza finestres locals en segon pla i calcula propostes de BPM i compàs.
2. L'usuari no calcula mil·lisegons ni mira números: **sent el tram en bucle amb el metrònom i valida o corregeix a l'instant**.
3. El pas d'un tram al següent és continu: l'àudio salta de bucle sense talls bruscos ni reinicis feixucs.

---

## 2. Fitxers implicats

| Fitxer | Rol en aquesta especificació |
|---|---|
| `app/dialegs.py` | Ampliació de `DialegGuiaBpm`: controls d'audició, loop, metrònom, mètrica, pastilles de candidats i ajust de mida del tram. |
| `app/main.py` | Orquestrador del flux (`Finestra._analisi_guitat`, `_guia_*`, gestió d'estat de reproducció i transició suau de finestres). |
| `app/tempo_map.py` | Nucli pur: càlcul de finestres amb canvi de mètrica (`num/den`), ajust de compassos enters per tram i validació. |
| `app/visor.py` | Controls de transport, reproducció en bucle continu (`_fixa_loop`, `_alinea_cursor_loop`) i volum del metrònom. |
| `docs/ANALISI_GUIAT.md` | Actualització de la documentació viva del projecte amb el flux definitiu. |
| `tests/test_gui.py` | Tests del cicle de vida del diàleg, tecles ràpides i orquestració del guiat. |
| `tests/test_tempo_map.py` | Tests de les funcions pures de càlcul de trams amb compassos enters. |

---

## 3. Especificació Funcional Pas a Pas

### Pas 0: Entrada en mode guiat (Mode Enfocament)
* **Trigger:** Clic al botó `b_guia` («Anàlisi guiat») a la barra *Treball*.
* **Comportament de la UI:**
  1. Si hi ha reproducció en curs, s'atura netament (`_atura_si_sona`).
  2. Es desactiva el snap del timeline (`set_snap(on=False)`).
  3. Es commuta a mode temps real / lliure (`_canvia_mode_temps(False)`).
  4. Es neteja qualsevol loop o selecció prèvia.
  5. S'obre el diàleg modeless `DialegGuiaDownbeat`.
* **Missatge per a l'usuari:**
  * *«1 · Situa el cursor al primer cop fort del tema (on comença el compte musical). Pots fer Play (Espai) per escoltar-lo.*  
    *2 · Prem Enter per confirmar el Compàs 1.»*

---

### Pas 1: Fixació del Compàs 1 (Downbeat Inicial)
* **Trigger:** L'usuari prem `Enter` o clica «Fet (Enter)» a `DialegGuiaDownbeat`.
* **Acció en un sol pas de desfer (Undo):**
  1. `t0 = vr.pos` (posició exacta del cursor).
  2. S'aplica l'offset a `t0`.
  3. Es realitza el tall del carril de tempo a `t0` via `tempo_map.parteix_trams_a`. El tram previ `[0, t0)` queda com a zona de compte enrere / pre-música a 120 BPM per defecte.
  4. Es restaura automàticament el mode musical **BPM · compàs** i el snap a negra (`1/4`).
  5. Es tanca `DialegGuiaDownbeat` i s'inicia immediatament la primera finestra de detecció.

---

### Pas 2: Bucle interactiu per trams (L'Estació d'Audició Interactiva)

Per a cada finestra $k$ des del punt de frontera $t_k$:

#### 2.1 Mida i acotament del tram proposat
* **Durada base:** Per defecte **4 compassos enters** de la mètrica vigent segons el BPM anterior (o finestra inicial de 8 s si és el primer tram).
* **Si hi ha selecció / Loop A–B actiu de l'usuari:** La mesura del BPM es fa exclusivament sobre l'interval del loop (`[A, B]`).
* **Llançament en fil desacoblat:** `FilGuiaBpm` analitza el tram sense congelar la interfície gràfica.

#### 2.2 Comportament auditiu immediat en obrir la finestra
* En aparèixer `DialegGuiaBpm` (o en rebre el BPM proposat):
  * Es fixa el loop del visor exactament a l'interval del tram `[t_k, t_{k+1}]`.
  * S'activa automàticament la reproducció en bucle amb el **metrònom mesclat al BPM proposat**.
  * L'usuari sent a l'instant si el clic encaixa amb la cançó.
  * Si l'usuari prem `Espai`, la reproducció s'atura o es reprèn sense tancar el diàleg.

#### 2.3 Controls del diàleg `DialegGuiaBpm`
El diàleg ha d'incorporar els següents elements operatius:

1. **Camp principal de BPM:**
   * Editable directament per teclat.
   * Modificar el valor actualitza immediatament el tempo del metrònom en temps real mentre sona el bucle.
2. **Botons de ràtio de tempo (Correcció d'octava i pols):**
   * **`÷2`** (mitja velocitat) i **`×2`** (doble velocitat).
   * **`×3/4`** i **`×4/3`** (correcció per a figures ternàries / tresets).
   * En clicar-los, el BPM canvia a l'acte i el metrònom s'adapta immediatament.
3. **Botó TAP integrat:**
   * Botó accessible (i drecera de teclat `T` activa quan el diàleg té focus).
   * Permet marcar 3 o 4 cops per calcular el BPM si la detecció ha fallat o el tema és acústic sense bateria.
4. **Selector de mètrica (Compàs):**
   * Desplegable amb `4/4`, `3/4`, `2/4`, `6/8`, `12/8` (i opció d'escriure `num/den`).
   * Canviar el compàs recalcula automàticament la durada del tram per complir el contracte de compassos enters.
5. **Selector de longitud del tram:**
   * Botons o selector ràpid: `[ -1 compàs ]` | **`N compassos`** | `[ +1 compàs ]`.
   * Permet allargar o escurçar la proposta perquè el tall coincideixi amb el final de la frase musical abans de confirmar.
6. **Pastilles de candidats alternatius (estil Logic Pro):**
   * Mostrar les 3 millors opcions del detector amb el percentatge de fiabilitat (ex: `101.30 (95%)`, `105.00 (88%)`).
   * Un sol clic sobre una pastilla carrega el BPM al camp i actualitza el metrònom.
7. **Botó de confirmació:**
   * Botó per defecte «Accepta (Enter)».

#### 2.4 Avanç de tram sense fricció (`Enter`)
* En prémer `Enter`:
  1. S'aplica el tram confirmat via `tempo_map.trams_finestra_guia` (en una sola operació de desfer per a aquest tram).
  2. Si el tram arriba al final de la WAV (o resta menys d'un compàs), el bucle finalitza (vegeu Pas 3).
  3. Si queden trams pendents:
     * El loop i el cursor salten suaument a l'inici del següent tram $t_{k+1}$.
     * S'inicia la detecció de la següent finestra.
     * La música no s'atura; continua sonant el nou tram en bucle.

---

### Pas 3: Tancament Orgànic i Transició a l'Harmonia

1. **Últim tram (Cua del tema):**
   * L'últim tram absorbeix la diferència fins al final exacte de la WAV (excepció permesa pel contracte `REGLES_TEMPS_GRID.md` §5).
2. **Consolidació del model:**
   * S'executa `tempo_map.fusiona_trams_iguals()` per unir trams consecutius amb el mateix BPM i mètrica.
   * S'atura la reproducció i es desactiva el metrònom.
   * Es restableix el mode `BPM · compàs` i el snap a negra.
3. **Transició directa a l'anàlisi d'acords:**
   * Es mostra un avís breu i elegant:  
     *«Mapa de tempo consolidat (X trams). Es llança l'anàlisi d'acords i estructura sobre el mapa.»*
   * S'obre directament el diàleg `Finestra.executa()` (amb la pestanya d'Acords seleccionada) per procedir amb Chordino i qm-segmenter.

---

## 4. Invariants i Regles Tècniques Obligatòries

1. **Compassos enters interiors:**
   Cap tram interior generat pel guiat pot tenir compassos fraccionaris. La funció de càlcul ha d'utilitzar sempre `durada_compas(bpm, num, den)` i arrodonir a múltiples enters.
2. **Seguretat de fils en PyQt5:**
   `FilGuiaBpm` **mai** ha d'invocar mètodes de widgets directament (com `append()` o `setText()`). Tota comunicació ha d'anar exclusivament mitjançant senyals Qt connectats a slots del fil principal (`feta`, `missatge`).
3. **Desfer atòmic (Undo/Redo):**
   Cada tram confirmat constitueix exactament un pas a `_undo_stack`. Si l'usuari s'equivoca, pot tancar el guiat i prémer `Ctrl+Z` per tirar enrere tram a tram.
4. **Gestió del so i eliminació de clics:**
   En canviar de loop o tram, s'han d'aprofitar les rutines existents de micro-fade (`FADE_LOOP_S = 0.004`) de `visor.py` per evitar espetecs sonors.

---

## 5. Pla de Treball per a l'Agent (Passos d'Execució)

### Bloc 1: Backend pur de tempo (`app/tempo_map.py`)
- [ ] Adaptar `trams_finestra_guia` perquè accepti paràmetres explícits de mètrica (`num`, `den`) i nombre de compassos desitjats (`n_compassos`), derivant la frontera exacta en segons.
- [ ] Afegir tests unitaris a `tests/test_tempo_map.py` verificant que el càlcul amb mètriques variades (3/4, 6/8, 4/4) genera sempre trams interiors que superen `valida_i_normalitza_compassos`.

### Bloc 2: Diàleg d'audició interactiva (`app/dialegs.py`)
- [ ] Ampliar `DialegGuiaBpm` amb:
  - Botó de reproducció/pausa intern o connexió transparent amb la barra espaiadora.
  - Botó TAP amb càlcul en viu.
  - Selector de mètrica (`num/den`) sincronitzat.
  - Botons per incrementar/reduir compassos del tram (`+/- 1 compàs`).
  - Botons de ràtio (`×2`, `÷2`, `×4/3`, `×3/4`).
  - Pastilles clicables amb els candidats alternatius.

### Bloc 3: Orquestració i reproducció contínua (`app/main.py`)
- [ ] Connectar l'obertura de cada finestra del guiat amb l'activació del loop del tram i el metrònom actiu.
- [ ] Implementar el salt continu d'un tram al següent en prémer `Enter`.
- [ ] Afegir el tancament amb transició directa cap a `Finestra.executa()`.

### Bloc 4: Suite de proves i regressió
- [ ] Crear tests a `tests/test_gui.py` que simulin el cicle complet: arrencada -> fixació compàs 1 -> acceptació de 2 trams -> tancament amb mapa vàlid.
- [ ] Executar la suite sencera (`python -m unittest discover -s tests`) verificant que cap test existent es trenca.
