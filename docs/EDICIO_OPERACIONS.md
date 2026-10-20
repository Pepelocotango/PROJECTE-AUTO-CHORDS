# EDICIO_OPERACIONS — totes les formes d'edició (GUI)

> **Font viva creuada.** Aquest document és l'**única taula** que llista *totes*
> les operacions d'edició i, per a cadascuna, com es fan **per GUI**,
> si valen per a **acords** i **estructura** (paritat d'edició **#11**) i el seu
> **estat**.
>
> Fonts que creua: `docs/archive/PLA_EDICIO_LLIURE.md` (§2, §6) · `docs/ESQUEMA_UI.md`
> (gestos i dreceres) ·
> `docs/REGLES_DE_LA_APP.md` (regles d'or).
>
> **No pot quedar desfasat**: el test `TestDocEdicioOperacions` comprova que la
> taula continua dient com es fa cada operació **per GUI** i per a quines pistes
> val (paritat #11).

> **Despatx únic (2026-10-19)**: totes les superfícies (menú contextual,
> llistes, menú principal, teclat del timeline i menú del loop) envien la
> intenció a **`Visor.executa_edicio(operacio, kind, idx, **kw)`**. Cap
> superfície decideix per si mateixa com s'edita un carril; el despatx resol la
> selecció (`Visor.seleccio_activa()`, que inclou `chord`, `section` i `tempo`)
> i tria el nucli canònic. La selecció també té un punt únic
> (`TimelineView.selecciona(kind, idx, mode)` amb `set`/`toggle`/`extend`).
> El contracte el blinda `tests/test_despatx_edicio.py` (operacions × carrils ×
> superfícies). Les mutacions de **gest** (arrossegar/redimensionar) continuen
> resolent-se al timeline perquè necessiten l'estat del ratolí; les seues
> funcions de backend són les mateixes per als tres carrils.
>
> **Gestos (2026-10-19)**: el drag del carril ③ fa el mateix **snap** que els
> clips i s'aplica **abans** de `editFinished` (perquè el canvi entre a
> l'undo). Els tres carrils desen **al release** (no a cada `mouseMove`). Un
> clic o un micro-moviment (< 5 px) no canvia el model: s'emet
> `dragCancelled` i es tanca la marca d'undo sense apilar res.
>
> **Tempo objectiu (2026-10-19)**: si hi ha un tram de tempo seleccionat, els
> camps BPM/compàs de la barra i el **tap tempo** editen eixe tram; si no, el
> transport (tram 0). Mentre sona, el tap crea el **loop** del tram objectiu.
> Els canvis de BPM no mouen els clips en segons: només recalculen les
> posicions musicals (etiquetes i columnes de compàs de l'ABC); per alinear
> clips a la graella es fa servir **Quantitza**. Un canvi de **tempo** a mig
> compàs no reinicia la numeració: el compàs continua i només canvia la seua
> durada; els canvis de **compàs** (signatura) sí que obrin un compàs nou.
>
> **Compassos enters (2026-10-20)**: les fronteres entre trams **interiors** de
> tempo/compàs cauen en **línies de compàs**, i cada tram interior té un
> **nombre enter de compassos**. El primer inici i l'últim final de la WAV són
> les excepcions. Canviar el BPM/compàs d'un tram conserva els seus compassos,
> mou la seua fi i **arrossega** les fronteres següents (l'últim absorbeix);
> si no es pot, es rebutja. Crear/moure/partir una frontera s'imanta a la línia
> de compàs més pròxima. Contracte complet: `docs/REGLES_TEMPS_GRID.md`.
>
> **Clic a un tram de tempo (2026-10-20, paritat #11)**: el clic **selecciona**
> el tram i posa el cursor **exactament al seu inici** (sense snap: les
> fronteres del mapa poden ser lliures, p. ex. el tall de «compàs 1 al
> cursor»). Igual que els clips d'acords/seccions ④⑤; arrossegar una vora
> **no** mou el cursor.
>
> **Detecció per tram (2026-10-20)**: amb un tram de tempo seleccionat, el
> botó **Detecta** analitza només l'àudio d'eixe tram i aplica el BPM
> directament (una sola operació de desfer); el seu inici és el downbeat.
> Sense tram seleccionat, es manté la detecció global.
>
> **Sincronització (2026-10-20)**: quan el model es reconstrueix (quantitzar,
> desfer, etc.), l'editor integrat es buida/refresca. Després de quantitzar es
> recupera el clip editat (si encara existeix) amb el **temps nou**; no es pot
> aplicar el temps vell. En carregar, els trams de tempo adjacents amb el
> mateix BPM/compàs es fusionen.

## 1. Regles que manen

- **#1–#4** ordre, contigüitat, durades derivades i **cobertura total** (0 → durada;
  el forat explícit és **`N`** als acords i **`-`** a l'estructura, §6.1).
- **#11 paritat d'edició**: **acords**, **estructura** i **trams de BPM/compàs**
  tenen **les mateixes eines i el mateix tracte**; només canvia el contingut
  semàntic (i el tram de BPM/compàs no té inline ni «reanomena en bloc»: s'edita
  amb el diàleg, comú a tots els trams).
- **§6.3 (edició lliure)**: en moure un bloc, **mana l'últim editat**; es **preserva la
  durada** del bloc; al **destí** el que queda a sota es **talla o s'elimina**; el que
  hi ha **entremig no es toca**. Cap operació es refusa per la #4.
- **«Afegir» en un model saturat**: com que els clips cobreixen **tota** la WAV
  (#4), afegir **no** és inserir un tros nou, sinó **obrir un clip nou** en eixe
  instant: **acord** = una **marca** nova (l'anterior s'hi acaba); **secció** =
  **partir** la secció que conté l'instant (la meitat dreta rep la
  lletra/família). Un **únic camí** (`visor._afegeix_a_la_posicio()`) per a la
  llista, el menú contextual del timeline i el menú principal.
  🐞 **Arreglat el 19-10-2026**: la versió anterior creava una **secció de 2 s**
  que la validació **rebutjava sempre** per solapament → «Afegeix secció aquí»
  petava **sempre** dins la cançó, als **tres** llocs.
  Si el carril ve **buit** (estat excepcional), l'alta crea el clip i tapa els
  forats amb **`N`/`-`** perquè torne a cobrir `0..durada`; en carregar, el
  visor també completa qualsevol pista buida (regla #4).

## 2. Edició de clips (acords · estructura · BPM/compàs)

| # | Operació | GUI (gest / drecera) | Acords | Estr. | **BPM/comp.** | Estat |
|---|---|---|---|---|---|---|
| 1 | **Afegir** un clip | menú *Edita ▸ Afegeix acord/secció…* · menú contextual · *Afegeix…* a la llista | ✓ | ✓ | ✓ | **FET**: model **saturat** → acord = **marca** nova; secció = **partir** (un sol camí sota `_afegeix_a_la_posicio`; vegeu §1) |
| 2 | **Partir** (dividir) | menú contextual ▸ *Parteix l'acord/secció…* (**al punt del clic, amb snap**; si no deixa marge, al cursor) · **«Partir per la meitat»** (dues meitats iguals) als menús de la llista, del clip i de la **pista de BPM/compàs** (③) | ✓ | ✓ | ✓ | **FET**: «per la meitat» = `parteix_per_la_meitat` (centre exacte); a la pista ③ el menú diu *Parteix aquest tros aquí*. Els talls de tempo s'imanten a la **línia de compàs** i es rebutgen si deixarien un tram interior sense un compàs sencer |
| 3 | **Fusionar** | menú contextual ▸ *Fusionar amb anterior/seguent* | ✓ | ✓ | ✓ | **FET**: als trams de BPM/compàs es fa amb **«Elimina»** (el veïnatge s'uneix) |
| 4 | **Eliminar** un clip | `Del` · menú contextual ▸ *Elimina* · llista | ✓ | ✓ | ✓ | **FET**: nucli únic `elimina_clips` (§6.4) |
| 5 | **Eliminar la SELECCIÓ** | `Del` amb multi-selecció | ✓ | ✓ | ✓ | **FET** |
| 6 | **Eliminar-ho TOT** → `N`/`-` a 0 | `Del` de tot | ✓ | ✓ | — | **FET** |
| 7 | **Reanomenar** | `F2` · doble clic (inline) · llista · *Reanomena (BPM/compàs)…* (diàleg del tram) | ✓ | ✓ | ✓ | **FET** |
| 8 | **Reanomenar en bloc** | `F2` amb multi-selecció | ✓ | ✓ | — | **FET** |
| 9 | **Trobar i reemplaçar** | `Ctrl+H` | ✓ | ✓ | — | **FET** |
| 10 | **Moure un clip / BLOC** | arrossegar el **cos** | ✓ | ✓ | ✓ | **FET** (§6.3). A ③ el cos mou la frontera i s'imanta a la **línia de compàs**; les fronteres següents s'arrosseguen |
| 11 | **Moure una marca** (fi = inici del següent) | — | ✓ | ✓ | ✓ | **FET** (camí de la vora) |
| 12 | **Nudge** (moure una frontera) | `←` / `→` · `Alt+←`/`→` (vora dreta) | ✓ | ✓ | ✓ | **FET** (`←`/`→` mou la frontera del tram; `Alt` la de la dreta) |
| 13 | **Redimensionar (vores lliures)** | arrossegar la **vora** del clip | ✓ | ✓ | ✓ | **FET**: nucli únic (`redimensiona_clips` + `redimensiona_acord`/`redimensiona_seccio`) i el gest del visor hi enganxat · vores **LLIURES** (§6.6): estirar talla/elimina el veí |
| 13b | **Retallar a la selecció A–B** | menú contextual dels **3** carrils ▸ *Retalla a la selecció A–B (A–Bs)* | ✓ | ✓ | ✓ | **FET** (20-10-2026): el clip passa a ocupar **exactament `[A, B]`** — es mou la frontera d'inici a **A** i la de fi a **B**; els veïns s'ajusten sols (cadena de fronteres) i tot va en **una sola operació d'undo**. Vores clavades per la regla #4: al **primer** clip l'inici no es mou (0) i a l'**últim** el final no es mou (durada). Surt **desactivat** sense loop; si el clip no toca l'A–B, o el backend ho rebutja (a ③ tota frontera interior ha de caure en **línia de compàs**), no toca res i avisa |
| 14 | **Duplicar** | `Ctrl+D` · *Duplica* del menú contextual de les 3 pistes | ✓ | ✓ | ✓ | **FET**: nucli únic `duplica_bloc_clips` (§2: la còpia va DESPRÉS i sobreescriu el tram, §6.3). Cal que la còpia **sencera** hi capça després; si no, no es fa res i s'avisa (la cançó no pot créixer) |
| 15 | **Duplicar arrossegant** | — | — | — | — | **RETIRAT** (2026-10-19). Es duplica amb `Ctrl+D` (#14) o copiar/enganxar (#16); `Ctrl+Shift` queda per a l'eina de selecció temporal |
| 16 | **Copiar / Retallar / Enganxar** | `Ctrl+C` / `Ctrl+X` / `Ctrl+V` (`Ctrl+Alt+V` = sense snap) | ✓ | ✓ | ✓ | **FET** (sobreescriu el tram; als trams obre les fronteres i hi canvia el BPM/compàs) |
| 17 | **Copiar/retallar el LOOP** | doble clic al regle · menú contextual de la banda | ✓ | ✓ | ✓ | **FET** (composable; la selecció del LOOP ja inclou els trams) |
| 18 | **Quantitza** (inicis de clips) | *Analitza ▸ Quantitza el model…* · botó **Quantitza** | ✓ | ✓ | — | **FET** (abast: tot · selecció · només acords · només estructura) |

## 3. Selecció i vista

| # | Operació | GUI | Acords | Estr. | **BPM/comp.** | Estat |
|---|---|---|---|---|---|---|
| 19 | **Seleccionar un clip** | clic | ✓ | ✓ | ✓ | **FET** |
| 20 | **Multi-selecció (toggle)** | `Ctrl`+clic | ✓ | ✓ | ✓ | **FET**: també a la pista de BPM/compàs (`Ctrl`+clic) |
| 21 | **Rang** | `Shift`+clic · `Ctrl`+arrossegar (marquee) | ✓ | ✓ | ✓ | **FET** (trams inclosos; la **selecció del LOOP** també inclou els trams) |
| 22 | **Seleccionar el del cursor** | clic + cursor | ✓ | ✓ | ✓ | **FET** (`kind: tempo` al i al menú) |
| 23 | **Seleccionar el LOOP** | doble clic a la banda | ✓ | ✓ | ✓ | **FET** (la selecció del LOOP inclou els trams) |
| 24 | **Buida la selecció** | `Esc` | ✓ | ✓ | ✓ | **FET** |
| 25 | **Consultar la selecció / cursor** | — | ✓ | ✓ | ✓ | **FET** |
| 26 | **Eina del timeline** (intel·ligent/marc) | tecla `E` · menú *Selecciona* · botó | ✓ | ✓ | ✓ | **FET** |
| 27 | **Zoom** | `Ctrl++` · `Ctrl+−` · `Ctrl+0` (Zoom total) | ✓ | ✓ | ✓ | **FET** |

## 4. Transport

| # | Operació | GUI | Estat |
|---|---|---|---|
| 28 | **Play / Pausa / Stop** | `Espai` · barra | **FET** |
| 29 | **Cursor (seek)** | clic al regle | **FET** |
| 30 | **Loop A/B** (marcar, activar, netejar) | `Ctrl+[` / `Ctrl+]` · menú | **FET** |
| 30b | **Loop a la selecció** | `L` · *Selecciona ▸ Loop a la selecció* · menú contextual dels **3** carrils | **FET**: unió de la selecció (mínim inici → màxim fi), una sola operació d'undo; si sona, alinea el cursor a l'inici |
| 31 | **Mute** | barra | **FET** |
| 32 | **Metrònom** | *Visualitza ▸ Metrònom* | **FET** |

## 5. Desfer i estat

| # | Operació | GUI | Estat |
|---|---|---|---|
| 33 | **Desfer / Refer** | `Ctrl+Z` · `Ctrl+Y` | **FET** |
| 34 | **Estat complet de l'app** | — | **FET** |
| 35 | **Llistar el model** | llistes del visor | **FET** |

## 6. Tempo, anàlisi i opcions

| # | Operació | GUI | Estat |
|---|---|---|---|
| 36 | **Tempo · compàs · offset** | camps de la barra · *Analitza ▸ Mapa de tempo i compàs…* · *Analitza ▸ Detecta el mapa de tempo (per beats)…* | **FET**: amb un tram de tempo seleccionat, els camps editen **eixe tram** (2B); si no, el transport. L'offset és global. Canviar BPM/compàs conserva els compassos enters i arrossega les fronteres (opció A); si no es pot, es rebutja |
| 36b | **Tap tempo** | `T` · botó **TAP** | **FET**: al tram de tempo seleccionat (o al primer); **una sola operació d'undo per sessió**; mentre sona, crea el **loop** del tram objectiu i alinea el cursor. Amb un tram seleccionat, el botó **Detecta** analitza només eixe tram i aplica el BPM directament |
| 37 | **Analitzar** (acords + estructura) | `F5` · *Analitza* | **FET** |
| 38 | **Opcions d'anàlisi** | *Paràmetres…* · *Inclou estructura* | **FET** |
| 39 | **Compàs 1** (detectar / marcar) | *Analitza ▸* | **FET** |
| 40 | **Tonalitat automàtica** | — | **RETIRAT** (2026-10-19, decisió de l'operador): la partitura surt sempre amb `<fifths>0</fifths>` · `docs/REGLES_DE_LA_APP.md` |
| 41 | **Inclou la partitura** (marca d'export) | *Fitxer ▸ Inclou la partitura* | **FET** |

## 7. Fitxers, projecte i export

| # | Operació | GUI | Estat |
|---|---|---|---|
| 42 | **Obrir àudio** | `Ctrl+O` | **FET** |
| 43 | **Projecte**: crear/obrir/desar/desar com/còpia | *Fitxer ▸* | **FET** |
| 44 | **Recents** | *Fitxer ▸ Obre recent…* | **FET** |
| 45 | **Revertir** | *Fitxer ▸ Reverteix* | **FET** (amb confirmació modal) |
| 46 | **Còpia versionada (backup)** | automàtic (autosave) | **FET** |
| 47 | **Exportar WAVs** | `Ctrl+E` | **FET** — el paquet hi porta les **tres parts** (regla #12): `acords.csv`+`wavs_acords/`, `estructura_ABC.csv`+`wavs_estructura/` i **`mapa_tempo/`** (tempo+compàs) |
| 48 | **Exportar la partitura** | *Fitxer ▸ Exporta la partitura…* | **FET** |
| 49 | **Obrir la carpeta de sortida** | *Fitxer ▸ Obre la carpeta de sortida* | **FET** |

## 8. Estat i exclusions (resum)

> ✅ **Cap pendent obert** (18-10-2026). Els tres ítems que hi havia aquí
> (vores lliures #13, duplicar #14/#15 i la «Fase 5» de les seccions) estaven
> **fets** i s'han verificat un per un abans de treure'ls: el gest del visor i
> l'de redimensionar, el duplicat amb el destí de §6.3 i les vores lliures
> de les seccions (les dues bandes, també l'última).

### Pista de BPM/compàs (trams del mapa de tempo) — ✅ COMPLERTA

La pista comparteix amb acords i estructura **tot** el joc d'edició:
**afegir/partir** (obrir un *tall*), **partir per la meitat**, **eliminar**
(amb els veïns unint-se), **moure** (el cos mou el punt de canvi; les vores, les
fronteres), **redimensionar**, **nudge** (`←`/`→` i `Alt`), **desfer/refer**,
**selecció** (`Esc`, `Ctrl`+clic, `Shift`+clic, **marquee** i
**LOOP**), **porta-retalls** (`Ctrl+C/X/V`) i **duplicar** (`Ctrl+D`).

Les files amb `—` a la columna **BPM/comp.** són **exclusions deliberades**, no
pendents:

- **#6 Eliminar-ho TOT**: el mapa **no pot quedar buit** (ha de cobrir sempre
  `0..durada`); l'equivalent és deixar-hi un sol tram.
- **#8 Reanomenar en bloc**: el contingut d'un tram és numèric (BPM + compàs) i
  s'edita amb el diàleg; no hi ha noms inline.
- **#9 Trobar i reemplaçar**: idem — no hi ha text on buscar (es fa tram a tram
  o amb les eines del mapa).
- **#15 Duplicar arrossegant**: retirat; `Ctrl+Shift` és l'eina de selecció
  temporal i duplicar es fa amb `Ctrl+D` o el porta-retalls.
- **#18 Quantitza**: mou els **inicis** dels clips d'acords i/o estructura a
  la graella. No toca BPM, compàs, offset ni el cru; una sola operació de
  desfer. Graelles: acords de corxera a 1 compàs; estructura d'1 a 64 compassos.

> ✅ **Fet el 17-10-2026**: el **moviment de bloc** (§6.3, #10) amb el destí; la
> **paritat d'estructura** (`mou_bloc_seccions`, gest del visor i  amb
> `kind`); el símbol **`-`** a **tota** l'estructura (també a `normalitza_cobertura`);
> i la neteja del codi mort (`_move_section_group`).
