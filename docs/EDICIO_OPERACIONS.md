# EDICIO_OPERACIONS — totes les formes d'edició (GUI)

> **Font viva creuada.** Aquest document és l'**única taula** que llista *totes*
> les operacions d'edició i, per a cadascuna, com es fan **per GUI**,
> si valen per a **acords** i **estructura** (paritat d'edició **#11**) i el seu
> **estat**.
>
> Fonts que creua: `docs/ESQUEMA_UI.md` (gestos i dreceres) ·
> `docs/REGLES_DE_LA_APP.md` (regles d'or).
>
> **No pot quedar desfasat**: el test `TestDocEdicioOperacions` comprova que la
> taula continua dient com es fa cada operació **per GUI** i per a quines pistes
> val (paritat #11).
>
> Aquest inventari cobreix les operacions del **model musical** (acords,
> estructura i tempo/compàs). El **detall operatiu** de tempo/compàs i de
> l'edició de la còpia WAV del projecte —nanses als extrems, fades i
> desfer/refer conjunt— és a **§9 d'este mateix document**; les regles i
> invariants són a [`REGLES_DE_LA_APP.md` §13](REGLES_DE_LA_APP.md).

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
> **Tempo objectiu (2026-10-19 · TAP 2026-11-01)**: si hi ha un tram de tempo
> seleccionat, els camps BPM/compàs de la barra editen eixe tram; si no, el
> **clip 0**. El transport és només una vista/editor del clip. El **tap tempo**
> només actua amb un tram de tempo
> seleccionat: sense selecció no fa res. Mentre sona, el tap crea el **loop**
> d'eixe tram.
> Els canvis de BPM no mouen els clips en segons: només recalculen les
> posicions musicals (etiquetes i columnes de compàs de l'ABC); per alinear
> clips a la graella es fa servir **Quantitza**. Si un canvi deixa clips sense
compassos sencers, apareix un diàleg per **conservar o descartar** l'operació.
> Un canvi de **tempo** a mig
> compàs no reinicia la numeració: el compàs continua i només canvia la seua
> durada; els canvis de **compàs** (signatura) sí que obrin un compàs nou.
>
> **Model actual (2026-11-11)**: les fronteres interiors dels clips de
> tempo/compàs són **lliures**; el snap és opcional i no s'exigeix cap línia de
> beat. Cal BPM/compàs vàlids, una durada mínima d'un compàs **`1/16` a 350 BPM
> (≈43 ms)** i **`N` enter a tots els clips** (primer i últim inclosos, sense
> exempció de pre-roll ni de rubato). El primer inici és 0 i l'últim final és la
> durada de la WAV. El **detall del recalcul guiat, la referència i els avisos**
> és a **§9.1–§9.2**.
> Els canvis explícits de BPM/compàs respecten el valor escrit; si el resultat
> no és vàlid, es rebutja amb avís. Si un **canvi de compàs** deixa un `N` no
> enter, es rebutja i s'obri un diàleg per reparar-lo (ajustar el BPM a `N`
> enter o canviar a la signatura canònica). «Encaixar a
> graella» de l'anàlisi fa servir el mateix nucli i graelles que «Quantitza»;
> per defecte, **corxera** (1/2 temps, 2 acords per temps). El selector
> **Beat/TAP** de la barra 2 indica la unitat del detector **i el valor de
> cada tap** (negra per defecte; negra amb punt per a 6/8). El TAP multiplica
> `taps/min × negres per beat` abans d'escriure el BPM intern. La franja
> Editor del clip de tempo té **Agrupació** (`3+3`, `2+2+3`…; buit =
> automàtica). Al diàleg del clip
> hi ha **N compassos** (mode A): N i compàs manen, el BPM es recalcula i les
> fronteres no es mouen. La validació d'este canvi és **local** al clip editat;
> un altre clip fora de graella no bloqueja l'edició. Els canvis explícits de
> compassos
> (`+1`/`−1`/`×2`/`÷2`) es mantenen com a reinterpretació mètrica
> del clip. Contracte complet: `docs/REGLES_DE_LA_APP.md` §13.4–13.6 i
> `docs/recerca/PLA_MAPA_TEMPS.md`.
>
> **Clic a un tram de tempo (2026-10-20, paritat #11)**: el clic **selecciona**
> el tram i posa el cursor **exactament al seu inici** (sense snap: les
> fronteres del mapa poden ser lliures, p. ex. el tall de «compàs 1 al
> cursor»). Igual que els clips d'acords/seccions ④⑤; arrossegar una vora
> **no** mou el cursor.
>
> **Sincronització (2026-10-20)**: quan el model es reconstrueix (quantitzar,
> desfer, etc.), l'editor integrat es buida/refresca. Després de quantitzar es
> recupera el clip editat (si encara existeix) amb el **temps nou**; no es pot
> aplicar el temps vell. En carregar, els trams de tempo adjacents amb el
> mateix BPM/compàs es fusionen.

## 1. Regles que manen

> Les regles d'or (#1–#4, #11 i §6.3) són a `docs/REGLES_DE_LA_APP.md`. Ací
> només recollim les implicacions operatives que no hi són.

- **«Afegir» en un model saturat**: com que els clips cobreixen **tota** la WAV
  (#4), afegir **no** és inserir un tros nou, sinó **obrir un clip nou** en eixe
  instant: **acord** = una **marca** nova (l'anterior s'hi acaba); **secció** =
  **partir** la secció que conté l'instant (la meitat dreta rep la
  lletra/família). Un **únic camí** (`visor._afegeix_a_la_posicio()`) per a la
  llista, el menú contextual del timeline i el menú principal.
- **Carril buit** (estat excepcional): l'alta crea el clip i tapa els forats amb
  **`N`/`-`** perquè torne a cobrir `0..durada`; en carregar, el visor també
  completa qualsevol pista buida (regla #4).

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
| 10 | **Moure un clip / BLOC** | arrossegar el **cos** | ✓ | ✓ | ✓ | **FET** (§6.3). A ③ el cos mou la frontera amb **re-tempo local** (els compassos dels dos costats es conserven, el BPM en deriva i les fronteres següents **no** es mouen); la guia del drag segueix el punter |
| 11 | **Moure una marca** (fi = inici del següent) | — | ✓ | ✓ | ✓ | **FET** (camí de la vora) |
| 12 | **Nudge** (moure una frontera) | `←` / `→` · `Alt+←`/`→` (vora dreta) | ✓ | ✓ | ✓ | **FET** (`←`/`→` mou la frontera del tram; `Alt` la de la dreta) |
| 13 | **Redimensionar (vores lliures)** | arrossegar la **vora** del clip · a ③ escrivint **`Ini (c)`** / **`Fi (c)`** a la franja Editor o amb el ratolí/carril | ✓ | ✓ | ✓ | **FET**: nucli únic (`redimensiona_clips` + `redimensiona_acord`/`redimensiona_seccio`) i el gest del visor hi enganxat · vores **LLIURES** (§6.6): estirar talla/elimina el veí. A ③ (`mou_frontera_retempo`, §13.6) l'extrem contrari **no** es mou i es re-tempo el clip i el veí; l'`ini` del 1r i la `fi` de l'últim es **rebutgen amb avís** (són els extrems de la WAV) |
| 13b | **Parteix a la selecció A–B** | menú contextual dels **3** carrils ▸ *Parteix a la selecció A–B (A–Bs)* | ✓ | ✓ | ✓ | **FET** (20-10-2026): és el «parteix aquí» fet **als dos llocs alhora** — cada frontera del loop (**A** i **B**) que caiga **dins** del clip seleccionat hi deixa un tall nou, així que el clip queda en **2 o 3 trossos amb el mateix nom** i el tros que va d'A a B queda **seleccionat**. Tot en **una sola operació d'undo**. Si A i B cauen fora del clip, no es parteix res i s'avisa. A ③ el tall s'imanta a la **línia de compàs** (dues fronteres al mateix compàs = **un sol tall**) i es rebutja si deixaria un tram interior sense un compàs sencer |
| 14 | **Duplicar** | `Ctrl+D` · *Duplica* del menú contextual de les 3 pistes | ✓ | ✓ | ✓ | **FET**: nucli únic `duplica_bloc_clips` (§2: la còpia va DESPRÉS i sobreescriu el tram, §6.3). Cal que la còpia **sencera** hi capça després; si no, no es fa res i s'avisa (la cançó no pot créixer) |
| 15 | **Duplicar arrossegant** | — | — | — | — | **RETIRAT** (2026-10-19). Es duplica amb `Ctrl+D` (#14) o copiar/enganxar (#16); `Ctrl+Shift` queda per a l'eina de selecció temporal |
| 15b | **Crear rubato sobre un rang** | *Analitza ▸ Marca el rang A–B com a rubato* · menú contextual ③ | — | — | ✓ | **FET** (3.2): parteix el mapa, ajusta els veïns i parteix el mapa i marca el flag; un sol desfer |
| 15c | **Convertir un tram a rubato** | menú contextual ③ · *Analitza ▸ Converteix el tram de tempo a rubato* | — | — | ✓ | **FET** (3.2) |
| 15d | **Convertir un rubato a normal** | menú contextual ③ · *Analitza ▸ Converteix el rubato a normal* | — | — | ✓ | **FET** (3.2): només canvia el flag a normal |
| 16 | **Copiar / Retallar / Enganxar** | `Ctrl+C` / `Ctrl+X` / `Ctrl+V` (`Ctrl+Alt+V` = sense snap) | ✓ | ✓ | ✓ | **FET** (sobreescriu el tram; als trams obre les fronteres i hi canvia el BPM/compàs) |
| 17 | **Copiar/retallar el LOOP** | doble clic al regle · menú contextual de la banda | ✓ | ✓ | ✓ | **FET** (composable; la selecció del LOOP ja inclou els trams) |
| 18 | **Quantitza** (inicis de clips) | *Analitza ▸ Quantitza el model…* · botó **Quantitza** | ✓ | ✓ | — | **FET** (abast: tot · selecció · només acords · només estructura) |
| 18b | **Quantitza BPM** | *Analitza ▸ Quantitza BPM* · botó **BPM…** | — | — | ✓ | **FET**: tria **Sense decimals**, **1 decimal** o **2 decimals**; conserva compassos, reencaixa fronteres i arredonix els empats amb `ROUND_HALF_UP`; els rubatos es quantitzen com qualsevol tram. **El pre-roll 0 → offset es conserva intacte** |

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
| 35 | **Llistar el model** | llistes del visor: acords ⑩, seccions ⑪, **clips de tempo/compàs ⑭** (`Inici (s)`·`Fi (s)`·`BPM`·`Compàs`; el flag rubato) i **marcadors ⑮** (`Temps (s)`·`Tipus`). Clic = salta, doble-clic = editar/franja Editor, botó dret = menú del carril | **FET** |
| 35b | **Talls i marcadors independents** | `Enter` = només tempo · `0` = només estructura · `+` = tempo + estructura · `M` = només marcador; llista ⑮ per editar/eliminar | **FET**: els marcadors són anotacions independents del tempo i de l'estructura |
| 35c | **Configurar dreceres** | *Ajuda ▸ Configura les dreceres…* | **FET**: taula amb totes les dreceres, cerca, edició, restauració i control de conflictes; es desa a `dreceres.json` |

L'historial de desfer/refer conserva les **10 últimes accions totals**. En
superar el límit, la més antiga es descarta i l'app ho comunica.

## 6. Tempo, anàlisi i opcions

| # | Operació | GUI | Estat |
|---|---|---|---|
| 36 | **Tempo · compàs · offset** | camps de la barra · *Analitza ▸ Mapa de tempo i compàs…* · *Analitza ▸ Detecta el mapa de tempo (per beats)…* | **FET**: amb un tram de tempo seleccionat, els camps editen **eixe tram** (2B); si no, el **clip 0**. L'offset és global. Canviar el BPM/compàs (barra, diàleg del tram o TAP) respecta el valor escrit (validació permissiva); en moure una frontera, el recalcul guiat pot ajustar BPM/compàs/N; si no hi ha solució, s'avisa i es rebutja el gest |
| 36b | **Tap tempo** | `T` · botó **TAP** | **FET**: només al tram de tempo **seleccionat** (sense selecció no fa res); **una sola operació d'undo per sessió**; mentre sona, crea el **loop** d'eixe tram i alinea el cursor |
| 37 | **Analitzar** (acords + estructura) | `F5` · *Analitza* | **FET** |
| 37b | **Analitzar acords al rang A–B** | *Analitza ▸ Analitza acords al rang A–B…* | **FET**: només substitueix els acords dins el loop A–B; conserva la resta del model, el BPM i l'estructura; una sola operació de desfer |
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
| 46 | **Còpia versionada (backup)** | automàtic (autosave) + **Fitxer ▸ Restaura una còpia de seguretat…** | **FET** |
| 47 | **Exportar WAVs** | `Ctrl+E` | **FET** — el paquet hi porta les **tres parts** (regla #12): `acords.csv`+`wavs_acords/`, `estructura_ABC.csv`+`wavs_estructura/` i **`mapa_tempo/mapa_tempo.csv` + `mapa_tempo/mapa_tempo.mid`** (+ `AVIS_APROXIMACIO.txt` si hi ha trams rubato). També es pot exportar només el MIDI des de **Fitxer ▸ Exporta mapa de tempo (MIDI)…** |
| 48 | **Exportar la partitura** | *Fitxer ▸ Exporta la partitura…* | **FET** |
| 49 | **Obrir la carpeta de sortida** | *Fitxer ▸ Obre la carpeta de sortida* | **FET** |
| 50 | **Exportar l'àudio editat** | *Fitxer ▸ Exporta àudio…* | **FET** (Fase 6): diàleg natiu de desar; perfils WAV 16/24/32 bits, MP3 128/192/320, FLAC, AAC/M4A, OGG i Opus; només els còdecs que el `ffmpeg` del paquet pot escriure; escriptura atòmica i protecció de la còpia de treball |

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

## 9. Detall operatiu de tempo/compàs i edició d'àudio

> Les regles i invariants són a `docs/REGLES_DE_LA_APP.md` §13. Ací només hi ha
> el detall operatiu de la GUI i de les accions.

### 9.1 Offset i referència

- L'**offset** conserva el valor intern (p. ex. `1.207438`); la GUI en mostra
  **3 decimals**.
- La referència del recalcul és la **manual i global** de «Ref. recalc» (barra
  2: `BPM ref` + `compàs ref`), no la dels clips veïns. El motor pot ajustar
  BPM, compàs o `N` enters per acostar-s'hi.
- **Compàs 1 aquí**: en fixar l'offset, el pre-roll es recalcula amb un nombre
  enter de compassos (`N ≥ 1`) i el BPM es deriva per encaixar-hi; el clip de
  música següent també conserva `N` enter i recalcula el seu BPM. L'offset es
  desa immediatament al `.acproj`.
- El **pre-roll** és només la frontera `0→1`; les fronteres `2–3`, `3–4`… són
  interiors normals.

### 9.2 Recalcul guiat i botons Aplica/Ajusta

- **Aplica** = **recalc mòbil**: el clip seleccionat rep exactament el BPM,
  compàs i `N` del formulari, i la seua `fi` passa a ser l'`ini` del veí dret.
  El veí es recalcula a partir de **Ref. recalc**: conserva la signatura `x/x`
  si pot i busca l'`N` enter que deixa el BPM més a prop possible; només si no
  hi ha cap `N` vàlid amb eixa signatura canvia `x/x`. Si no hi ha cap
  combinació vàlida, es rebutja **tota** l'operació. En l'últim/únic clip
  Aplica està deshabilitat (la fi de la WAV és fixa).
- **Ajusta** obre el mateix diàleg que el doble clic sobre el tram (BPM,
  compàs i `N`); el resultat s'aplica pel mateix camí del diàleg. No s'aplica
  automàticament.
- El diàleg té **2 columnes**: a l'esquerra, l'edició/recalcul dividida en
  **3 blocs** —**Recalcul fix** (N/compàs/BPM + botó **Recalcula**),
  **Recalcul mòbil** (N/compàs/BPM + botó **Recalcula**) i **Opcions**—;
  a la dreta, un panell compacte de **només lectura** amb la informació
  completa del clip (rol, inici/fi, durada, compàs, agrupació, `N` real i
  enter, BPM intern, offset, Ref. recalc, unitats, snap i beats QM, veïns i
  validació), sense scroll. Este panell no participa en l'acceptació ni mou
  cap frontera.
- Les **Opcions** són comunes als dos recalcs: **Beats QM**, **Ref. recalc**,
  **Segons del tram**, **Unitat del beat**, **Canviar compàs**, **N fix** i
  **En segons (rubato)**. Indiquen què ha de tindre en compte el càlcul. Les
  caselles tenen un **indicador visible** (quadre buit/ple) sobre fons fosc i
  la secció **Ajuda** explica què fa cada opció **activada i desactivada**.
- La **Ref. recalc** es pot canviar des del mateix diàleg amb **BPM ref**,
  **Compàs ref** i **Aplica ref.**; el canvi va al visor i a la barra 2, i no
  recalcula cap clip per si sol.
- El selector **Beat/TAP** (negra, negra amb punt, corxera o blanca) canvia la
  unitat del beat detectat i del TAP al visor, i queda sincronitzat amb la
  barra 2.
- **Recalcula (fix)**: manté `ini` i `fi` i deriva el BPM amb l'`N`/compàs
  resultants de les opcions.
- **Recalcula (mòbil)**: mou la frontera compartida (`fi` del clip seleccionat
  = `ini` del veí dret) amb l'`N`/compàs resultants i el BPM del camp; el veí
  es recalcula.
- Els dos jocs de camps (fix i mòbil) estan **sincronitzats**; el mode el tria
  el botó, no el bloc on s'escriu.
- Sota la informació del clip hi ha una fila **Ajuda** que mostra el tooltip
  del camp, botó o casella sota el ratolí (la mateixa informació que la infobox
  de la finestra).
- **Ajusta** (al costat d'OK i Cancel) aplica els canvis d'edició/recalcul
  sense tancar el diàleg i refresca el panell d'informació amb l'estat real
  del model. OK després d'un Ajusta només tanca si no hi ha canvis nous.
- **Arrossegar una frontera** continua usant el recalcul guiat amb segons com a
  entrada; no és una edició directa de camps. El punter fixa Δt; s'ajusten les
  fronteres i el recalcul decideix BPM/compàs/`N` enters dels dos costats amb
  la referència base.
- **Regla del múltiple**: si la signatura base encaixa exacta amb els beats
  (`K/bq_ref` enter), mana ella; 20/24/28 beats amb base 4/4 → 4/4 N=5/6/7;
  12/36 amb base 3/4 → 3/4 N=4/12; 6/12 amb base 6/8 → 6/8 N=2/4. Amb `n_fix`
  només val si `N` coincidix amb el fixat; la signatura base n'està exempta de
  `n_max` (clips llargs).
- **K no factoritzable**: s'exclouen els compassos degenerats (`2/8`, `1/8`,
  `1/4` amb `N>1`) i es prova **un beat detectat** amunt/avall (`K ± beat_factor`;
  1,5 negres amb negra amb punt, 0,5 amb corxera, i 1,0 si els beats són
  inferits). Es prefereix el que encaixa amb la signatura base i, si no, el de
  BPM més pròxim. El resultat indica `beats_ajustats`, `beats_detectats` i
  `beats_inferits`; amb beats inferits l'avís diu «sense beats detectats», no
  «beats ajustats».
- **Beats**: amb **Snap Beats QM**, si n'hi ha dins del clip, el nombre de
  negres és una restricció forta per al BPM. Sense beats (o sense usar-los),
  s'inferix `D × BPM_ref / 60` i, si cau a prop d'un enter (±0,2), s'aplica la
  mateixa restricció. En talls sense
  snap, un beat dins de **50 ms** (`TOL_TALL`) de la frontera es classifica de
  manera estable i s'avisa del recompte ambigu.
- **Avisos de BPM**: cada recalcul pot adjuntar una desviació de BPM >12 % i una
  sospita d'octava (ratio ≈2 o ≈0,5, marge 8 %). Són avisos, no canvien la
  decisió.
- **Fusionar o eliminar una frontera** recalcula el clip afectat amb la
  referència base i els beats. Si no pot quedar en compassos sencers, avisa i
  el deixa com està; no hereta el `N` fraccionari del clip que desapareix.
- Un tram **rubato** es mou i es re-tempa com qualsevol tram normal; només
  canvia el flag de notació.

### 9.3 Fronteres a mà (`Inici (s)` / `Fi (s)`)

`Inici (s)` i `Fi (s)` són editables. Com que la frontera és única, moure'n un
mou **eixa** frontera; l'extrem contrari no es mou i s'aplica el **recalcul
guiat** del clip i, si cal, del veí:

| Gest | Resultat |
|---|---|
| `ini` del **1r** clip | **rebutjat + avís** (inici de la WAV) |
| `fi` de l'**últim** clip | **rebutjat + avís** (fi de la WAV) |
| `ini` de qualsevol altre | mou la frontera `(i-1, i)`; el `fi` no es mou; recalcul guiat |
| `fi` de qualsevol altre | mou la frontera `(i, i+1)`; l'`ini` no es mou; recalcul guiat |
| costat rubato | es mou com un tram normal; el flag `tipus` no canvia |

Si l'instant no és possible, s'aplica el més a prop i **s'avisa**.

- **`+`**: parteix **tempo i estructura** al cursor, sense crear cap marcador.
  **Enter**: parteix només el tempo. **`0`**: parteix només l'estructura.
  Amb Snap actiu s'encaixa a la graella; amb Snap desactivat es respecta el
  cursor. Si el tall necessita ajust, s'aplica el recalcul guiat
  (`REGLES_DE_LA_APP.md` §13.5).
- **`M`**: crea només un **marcador independent**; no talla tempo ni
  estructura i no està lligat a cap frontera.
- **Graella robusta**: un canvi de compàs a menys de **20 ms** d'una línia de
  compàs s'imanta a la línia; no es creen dos compassos quasi iguals ni salta
  la numeració. Les etiquetes i el metrònom toleren els offsets d'integració
  de fraccions de fusa (resolució 1/32), de manera que una edició manual de
  mil·lisegons no atura el metrònom.

### 9.4 Detecció amb tram seleccionat

- Amb un **tram seleccionat**, **Detecta** analitza només eixe tram i el
  downbeat és el seu inici. En un tram amb els extrems fixos, **Δt és fix**: el
  BPM detectat només compta compassos (`N = round(Δt · BPM_ref / (bq · 60))`,
  mínim 1) i s'aplica el **BPM derivat exacte** (`N · bq · 60 / Δt`), que clava
  les barres entre els dos punts. La fi del tram i els següents no es mouen; si
  el BPM derivat cau fora de 30–350 o no hi cap cap compàs sencer, **s'avisa**.
  S'aplica en una sola operació de desfer.
- Per a tempo variable, **Analitza ▸ Detecta el tempo per trams…** fa el mapa
  sencer (un BPM cada N compassos, amb els criteris musicals del detector) i el
  valida de manera estricta.

### 9.5 Edició de l'àudio del projecte

- **Retallar l'inici `t`**: s'elimina l'àudio anterior; elements, marcadors,
  fronteres i offset es desplacen `−t`; el contingut anterior desapareix.
- **Retallar el final a `D`**: s'eliminen els elements posteriors, s'escurcen
  els intervals que travessen `D` i la durada nova és `D`.
- **Afegir silenci al inici `t`**: so i referències es desplacen `+t`; offset
  `+t`; es crea un acord `N` per al silenci i la secció existent el cobrix.
- **Afegir silenci al final**: la cobertura s'estén fins a la nova durada amb
  acord `N`; secció i últim tram cobrixen l'extensió.
- Previsualització en arrossegar, aplicació en deixar anar; àudio i model
  **atòmics** i un sol desfer/refer. Tall al fotograma més pròxim, sense moure a
  un pas per zero. Cada vora àudio/silenci rep un **fade de 4 ms**. El crossfade
  entre clips queda fora de l'abast inicial (només hi ha un WAV).
- L'historial conjunt conserva les **10 últimes accions** (musicals i d'àudio) i
  comunica quan descarta la més antiga.
- S'escriu primer en un temporal i es valida abans de substituir la còpia. Un
  error no pot deixar àudio i model en estats diferents.
- Les còpies de seguretat versionades inclouen el WAV de treball i els marcadors.

### 9.6 Unitat de pols, Ref., classificació i export (S1–S3)

- **Model**: cada tram té `beat_unit` (`negra`, `negra_punt`, `corxera`,
  `semicorxera`, `blanca`). El BPM canònic continua sent negres/minut i el TAP
  es deriva. `mapa_tempo.csv` porta `beat_unit` al final i es llig per noms;
  columna absent o valor desconegut = rebuig; valor buit = derivar+avisar.
  `.acproj` FORMAT 4 desa `tempo.ref.beat_unit`; el format 3 es rebutja sense
  tocar-lo.
- **Presentació**: el BPM del clip i el TAP es mostren en la unitat del tram;
  la Ref. en la seua unitat; el transport/barra sense clip en el tram 0 o
  `negra`. El selector **Beat/TAP** de la barra és una drecera del tram
  seleccionat; `cb_ref_beat` és el de la Ref. Al **diàleg**, el canvi d'unitat
  del clip és **inline** (radios «Mantén el tempo (canvia el número)» /
  «Mantén el número (canvia el tempo)», preview de les dues xifres) i no
  s'aplica fins **Ajusta/OK**; la Ref. té el seu selector i un modal amb les
  mateixes opcions. TAP = Mantén el número; BPM manual = Mantén el tempo.
  **Escolta la proposta** reprodueix el clip en bucle amb el metrònom al BPM,
  compàs i unitat proposats, sense aplicar res; guarda i restaura loop,
  metrònom i reproducció en aturar o en Ajusta/OK/Cancel.
- **TAP/Ref. (L1)**: si el compàs de la Ref. difereix del clip, el TAP aplica
  el clip però **no toca la Ref.**: mostra «TAP aplicat; Ref. no actualitzada
  (compàs diferent)». Si coincideix, actualitza BPM+unitat de la Ref. Canviar
  la unitat amb un TAP obert tanca la sessió (1 undo) i el canvi és un altre
  undo; `Aplica ref.` i el canvi d'unitat tenen undo real.
- **Rang**: es valida el BPM **intern** 30–350; missatges amb les dues xifres
  (`20 ♩. = 30 intern` vàlid; `240 ♩. = 360 intern` rebutjat).
- **L3/L4**: un canvi de compàs o recalc que deixa la unitat fora de
  `encaixa_en_compas` no s'aplica (atòmic); es proposa la unitat derivada. El
  recalc automàtic filtra candidats per la unitat actual i, si no n'hi ha,
  conserva+avisa. L4 avisa si la unitat no alinea amb l'agrupació, sense
  bloquejar.
- **Classificador (S3)**: `recalculca_tram(..., meter_prior=None)` separa BPM
  global + compàs local per costat; el compàs global de la Ref. només
  desempata. `classifica_recalc`/`recalculca_tram_amb_candidats` donen
  **ALT/MITJÀ/BAIX** i alternatives. ALT només en acció explícita; MITJÀ amb
  alternatives o canvi estructural; BAIX només per condició dura (cap
  candidat, rang, octava, conflicte real unitat/compàs, frontera ambigua o
  beats no resolubles). Cost alt amb candidat factible = MITJÀ. La sospita
  1,5×/2/3 és MITJÀ i no s'auto-aplica; es pot **silenciar per tram/sessió**
  amb la casella del diàleg (el resum continua dient que l'avís està
  silenciat). L'Assistència és per context (info box + fila Ajuda del diàleg)
  i les alternatives es poden carregar amb doble-clic.
- **DAW (REAPER)**: flux provat (2026-11-14) amb `mapa_tempo.mid`: importa
  **primer** el MIDI, accepta el diàleg **«Importar mapa de tempo al
  proyecto»** (+ marcadors) i després importa la WAV en una segona pista.
  Resultat: 17 markers de tempo/compàs, WAV **256,534059 s** i MIDI
  **256,534098 s**. Si la WAV s'importa primer, el *timebase* per defecte
  (**Beats**) pot ajustar-ne la longitud/velocitat; l'alternativa és posar el
  projecte o l'item en **Time**.
- **Talls QM (+/Enter/Afegeix/meitat/A–B)**: amb Snap QM es compten els
  beats de cada meitat (el beat del tall pertany a la dreta) i es convertixen a
  negres (`Bq`). El motor proposa BPM, compàs i `N` exactes: base pura, base +
  un compàs extrany o secció sencera; si cal, també `base + /4`. Màxim 2 clips
  per costat, `1/4` filtrat si hi ha alternativa i mínim 2 opcions `/4` al
  diàleg. Les fronteres internes cauen als temps reals dels beats QM. Si hi ha
  2+ opcions, un diàleg conjunt (màxim 6 per costat, sense preselecció) les
  mostra amb la diferència de BPM respecte de la Ref.; cancel·lar no toca res.
  El play es pausa en obrir el diàleg i es reprén en aplicar; cancel·lar el
  deixa en pausa. Si es cancel·la o falla el tempo, no es parteix
  l'estructura (`+` és atòmic).
- **Export (S2)**: `manifest.csv` té 10 columnes (les 7 històriques +
  `bpm_quarter`, `beat_unit`, `bpm_mostra` al final; estat a l'inici del
  segment; `mapa_tempo.csv` canònic). La guia HTML mostra les dues xifres. La
  partitura usa la unitat de cada mesura, emet `<metronome>` en canvi de
  compàs o d'unitat encara que no canvie el BPM, `<sound tempo>` només en
  canvi de BPM, i `semicorxera` → `16th`. El fallback constant usa
  `bar_quarters(num,den)` i `beat_type`.

### 9.7 Dreceres configurables (2026-11-14)

- **Catàleg únic**: les accions de menú amb drecera, les globals (`Space`,
  `T`, `E`), les de l'editor (`+`, Enter, `0`, `M`) i les del timeline (Esc,
  nudge) es poden editar des de **Ajuda ▸ Configura les dreceres…**.
- **Aplicació immediata**: en desar, s'actualitzen els `QAction`, els
  `QShortcut` i el mapa que consulta el timeline; els canvis de `Copia`,
  `Retalla`, `Enganxa`, `Duplica`, `Elimina` i `Space` valen també al
  timeline perquè comparteixen identificador.
- **Persistència**: `dreceres.json` dins `DADES_DIR`; es carrega a
  l'arrencada. Un valor buit desactiva la drecera. Si el fitxer no existeix o
  és invàlid, s'usen els valors per defecte.
- **Conflictes**: no es desa cap combinació repetida; el diàleg mostra les
  dues accions en xoc. Les equivalències Return/Enter, Del/Retrocés i
  `+`/Maj+`=` es mantenen.
- **Context**: els camps de text no s'intercepten; Enter respecta botons,
  combos i diàlegs que tenen acció pròpia.
