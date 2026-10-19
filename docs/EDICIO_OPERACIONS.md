# EDICIO_OPERACIONS — totes les formes d'edició (GUI)

> **Font viva creuada.** Aquest document és l'**única taula** que llista *totes*
> les operacions d'edició i, per a cadascuna, com es fan **per GUI**,
> si valen per a **acords** i **estructura** (paritat d'edició **#11**) i el seu
> **estat**.
>
> Fonts que creua: `docs/PLA_EDICIO_LLIURE.md` (§2, §6) · `docs/ESQUEMA_UI.md`
> (gestos i dreceres) ·
> `docs/REGLES_DE_LA_APP.md` (regles d'or).
>
> **No pot quedar desfasat**: el test `TestDocEdicioOperacions` comprova que la
> taula continua dient com es fa cada operació **per GUI** i per a quines pistes
> val (paritat #11).

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

## 2. Edició de clips (acords · estructura · BPM/compàs)

| # | Operació | GUI (gest / drecera) | Acords | Estr. | **BPM/comp.** | Estat |
|---|---|---|---|---|---|---|
| 1 | **Afegir** un clip | menú *Edita ▸ Afegeix acord/secció…* · menú contextual · *Afegeix…* a la llista | ✓ | ✓ | ✓ | **FET**: model **saturat** → acord = **marca** nova; secció = **partir** (un sol camí sota `_afegeix_a_la_posicio`; vegeu §1) |
| 2 | **Partir** (dividir) | menú contextual ▸ *Parteix l'acord/secció…* (pel cursor) · **«Partir per la meitat»** (dues meitats iguals) als menús de la llista, del clip i de la **pista de BPM/compàs** (③) | ✓ | ✓ | ✓ | **FET**: «per la meitat» = `parteix_per_la_meitat` (centre exacte); a la pista ③ el menú diu *Parteix aquest tros aquí* |
| 3 | **Fusionar** | menú contextual ▸ *Fusionar amb anterior/seguent* | ✓ | ✓ | ✓ | **FET**: als trams de BPM/compàs es fa amb **«Elimina»** (el veïnatge s'uneix) |
| 4 | **Eliminar** un clip | `Del` · menú contextual ▸ *Elimina* · llista | ✓ | ✓ | ✓ | **FET**: nucli únic `elimina_clips` (§6.4) |
| 5 | **Eliminar la SELECCIÓ** | `Del` amb multi-selecció | ✓ | ✓ | ✓ | **FET** |
| 6 | **Eliminar-ho TOT** → `N`/`-` a 0 | `Del` de tot | ✓ | ✓ | — | **FET** |
| 7 | **Reanomenar** | `F2` · doble clic (inline) · llista · *Reanomena (BPM/compàs)…* (diàleg del tram) | ✓ | ✓ | ✓ | **FET** |
| 8 | **Reanomenar en bloc** | `F2` amb multi-selecció | ✓ | ✓ | — | **FET** |
| 9 | **Trobar i reemplaçar** | `Ctrl+H` | ✓ | ✓ | — | **FET** |
| 10 | **Moure un clip / BLOC** | arrossegar el **cos** (guard `Ctrl+Shift` = duplicar) | ✓ | ✓ | ✓ | **FET** (§6.3) |
| 11 | **Moure una marca** (fi = inici del següent) | — | ✓ | ✓ | ✓ | **FET** (camí de la vora) |
| 12 | **Nudge** (moure una frontera) | `←` / `→` · `Alt+←`/`→` (vora dreta) | ✓ | ✓ | ✓ | **FET** (`←`/`→` mou la frontera del tram; `Alt` la de la dreta) |
| 13 | **Redimensionar (vores lliures)** | arrossegar la **vora** del clip | ✓ | ✓ | ✓ | **FET**: nucli únic (`redimensiona_clips` + `redimensiona_acord`/`redimensiona_seccio`) i el gest del visor hi enganxat · vores **LLIURES** (§6.6): estirar talla/elimina el veí |
| 14 | **Duplicar** | `Ctrl+D` · *Duplica* del menú contextual de les 3 pistes (a la ③ només si hi ha lloc després del tram) | ✓ | ✓ | ✓ | **FET**: nucli únic `duplica_bloc_clips` (§2: la còpia va DESPRÉS i sobreescriu el tram, §6.3) |
| 15 | **Duplicar arrossegant** | `Ctrl+Shift`+arrossegar (a l'origen hi torna una còpia) | ✓ | ✓ | — | **FET**. Als trams de BPM/compàs **no hi ha aquest gest**: l'arrossegar del cos hi mou el punt de canvi; es duplica amb `Ctrl+D` (#14) o copiar/enganxar (#16) |
| 16 | **Copiar / Retallar / Enganxar** | `Ctrl+C` / `Ctrl+X` / `Ctrl+V` (`Ctrl+Shift+V` = sense snap) | ✓ | ✓ | ✓ | **FET** (sobreescriu el tram; als trams obre les fronteres i hi canvia el BPM/compàs) |
| 17 | **Copiar/retallar el LOOP** | doble clic al regle · menú contextual de la banda | ✓ | ✓ | ✓ | **FET** (composable; la selecció del LOOP ja inclou els trams) |
| 18 | **Mode fàcil** (re-regularitzar) | *Analitza ▸ Mode fàcil…* | ✓ | — | — | **FET** |

## 3. Selecció i vista

| # | Operació | GUI | Acords | Estr. | **BPM/comp.** | Estat |
|---|---|---|---|---|---|---|
| 19 | **Seleccionar un clip** | clic ·  | ✓ | ✓ | ✓ | **FET** |
| 20 | **Multi-selecció (toggle)** | `Ctrl`+clic | ✓ | ✓ | ✓ | **FET**: també a la pista de BPM/compàs (`Ctrl`+clic) |
| 21 | **Rang** | `Shift`+clic · `Ctrl`+arrossegar (marquee) | ✓ | ✓ | ✓ | **FET** (trams inclosos; la **selecció del loop** encara és només acords+estructura) |
| 22 | **Seleccionar el del cursor** | clic + cursor | ✓ | ✓ | ✓ | **FET** (`kind: tempo` al i al menú) |
| 23 | **Seleccionar el LOOP** | doble clic a la banda | ✓ | ✓ | ✓ | **FET** (la selecció del LOOP inclou els trams) |
| 24 | **Buida la selecció** | `Esc` | ✓ | ✓ | ✓ | **FET** |
| 25 | **Consultar la selecció / cursor** | — | ✓ | ✓ | ✓ | **FET** |
| 26 | **Eina del timeline** (intel·ligent/marc) | tecla `E` · menú *Selecciona* · botó | ✓ | ✓ | ✓ | **FET** |
| 27 | **Zoom** | `Ctrl++` / `Ctrl+−` / `Ctrl+0` |`seleccio`\|`in`\|`out`) | ✓ | ✓ | ✓ | **FET** |

## 4. Transport

| # | Operació | GUI | Estat |
|---|---|---|---|
| 28 | **Play / Pausa / Stop** | `Espai` · barra | **FET** |
| 29 | **Cursor (seek)** | clic al regle | **FET** |
| 30 | **Loop A/B** (marcar, activar, netejar) | `Ctrl+[` / `Ctrl+]` · menú | **FET** |
| 31 | **Mute** | barra | **FET** |
| 32 | **Metrònom** | *Visualitza ▸ Metrònom* | **FET** |

## 5. Desfer i estat

| # | Operació | GUI | Estat |
|---|---|---|---|
| 33 | **Desfer / Refer** | `Ctrl+Z` · `Ctrl+Y` · `Ctrl+Shift+Z` | **FET** |
| 34 | **Estat complet de l'app** | — | **FET** |
| 35 | **Llistar el model** | llistes del visor | **FET** |

## 6. Tempo, anàlisi i opcions

| # | Operació | GUI | Estat |
|---|---|---|---|
| 36 | **Tempo · compàs · offset** | camps de la barra · *Analitza ▸ Mapa de tempo i compàs…* · *Analitza ▸ Detecta el mapa de tempo (per beats)…* | **FET** |
| 37 | **Analitzar** (acords + estructura) | `F5` · *Analitza* | **FET** |
| 38 | **Opcions d'anàlisi** | *Paràmetres…* · *Inclou estructura* | **FET** |
| 39 | **Compàs 1** (detectar / marcar) | *Analitza ▸* | **FET** |
| 40 | **Tonalitat automàtica** | *Fitxer ▸ Tonalitat automàtica* | **FET** |
| 41 | **Inclou la partitura** (marca d'export) | *Fitxer ▸ Inclou la partitura* | **FET** |

## 7. Fitxers, projecte i export

| # | Operació | GUI | Estat |
|---|---|---|---|
| 42 | **Obrir àudio** | `Ctrl+O` | **FET** |
| 43 | **Projecte**: crear/obrir/desar/desar com/còpia | *Fitxer ▸* | **FET** |
| 44 | **Recents** | *Fitxer ▸ Obre recent…* | **FET** |
| 45 | **Revertir** | *Fitxer ▸ Reverteix* | **FET** (sense confirm modal amb el pont) |
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
- **#15 Duplicar arrossegant**: aquest gest, a la pista, ja el té pres el cos
  del tram (**mou el punt de canvi**); duplicar es fa amb `Ctrl+D` o el
  porta-retalls.
- **#18 Mode fàcil**: re-regularitza el **ritme harmònic** dels acords (i les
  seccions); no toca el mapa de tempo.

1. **Redimensionat amb vores lliures** (#13) — nucli únic FET (S2a: `redimensiona_clips`); falta el gest del visor i.
2. **Duplicar**: alinear el destí amb **§6.3** (#14) i exposar el gest de **duplicar
   arrossegant** a l'(#15).
3. **Seccions**: resta de la Fase 5 del pla (vores lliures).

> ✅ **Fet el 17-10-2026**: el **moviment de bloc** (§6.3, #10) amb el destí; la
> **paritat d'estructura** (`mou_bloc_seccions`, gest del visor i  amb
> `kind`); el símbol **`-`** a **tota** l'estructura (també a `normalitza_cobertura`);
> i la neteja del codi mort (`_move_section_group`).
