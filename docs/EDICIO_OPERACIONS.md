# EDICIO_OPERACIONS — totes les formes d'edició (GUI ↔ MCP)

> **Font viva creuada.** Aquest document és l'**única taula** que llista *totes*
> les operacions d'edició i, per a cadascuna, com es fan **per GUI** i **per MCP**,
> si valen per a **acords** i **estructura** (paritat d'edició **#11**) i el seu
> **estat**.
>
> Fonts que creua: `docs/PLA_EDICIO_LLIURE.md` (§2, §6) · `docs/ESQUEMA_UI.md`
> (gestos i dreceres) · `docs/MCP_AUTO_CHORDS.md` (67 eines `ac_*`) ·
> `docs/REGLES_DE_LA_APP.md` (regles d'or).
>
> **No pot quedar desfasat**: `tests/test_edicio_operacions_doc.py` comprova que
> **totes** les eines `ac_*` del servidor surten aquí i que **cap** `ac_*` citada
> és inventada.

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

## 2. Edició de clips (acords · estructura · BPM/compàs)

| # | Operació | GUI (gest / drecera) | MCP | Acords | Estr. | **BPM/comp.** | Estat |
|---|---|---|---|---|---|---|---|
| 1 | **Afegir** un clip | menú *Edita ▸ Afegeix acord/secció…* · menú contextual · *Afegeix…* a la llista | `ac_add_chord`, `ac_add_section` | ✓ | ✓ | ✓ | **FET** |
| 2 | **Partir** (dividir) | menú contextual ▸ *Parteix l'acord/secció…* (pel cursor) · **«Partir per la meitat»** (dues meitats iguals) als menús de la llista i del clip | `ac_parteix_acord`, `ac_parteix_seccio` | ✓ | ✓ | ✓ | **FET**: «per la meitat» = `parteix_per_la_meitat` (centre exacte; l'MCP ho fa passant el `t` del mig) |
| 3 | **Fusionar** | menú contextual ▸ *Fusionar amb anterior/seguent* | `ac_fusiona_acord`, `ac_fusiona_seccio` | ✓ | ✓ | ✓ | **FET**: als trams de BPM/compàs es fa amb **«Elimina»** (el veïnatge s'uneix) |
| 4 | **Eliminar** un clip | `Del` · menú contextual ▸ *Elimina* · llista | `ac_delete_chord`, `ac_delete_section`, `ac_elimina_tall` | ✓ | ✓ | ✓ | **FET**: nucli únic `elimina_clips` (§6.4) — mateix camí a la GUI i a l'MCP |
| 5 | **Eliminar la SELECCIÓ** | `Del` amb multi-selecció | `ac_esborra_seleccio` | ✓ | ✓ | ✓ | **FET** |
| 6 | **Eliminar-ho TOT** → `N`/`-` a 0 | `Del` de tot | `ac_esborra_seleccio` | ✓ | ✓ | — | **FET** |
| 7 | **Reanomenar** | `F2` · doble clic (inline) · llista · *Reanomena (BPM/compàs)…* (diàleg del tram) | `ac_rename_chord`, `ac_rename_section`, `ac_set_tram_tempo` (BPM + compàs del tram) | ✓ | ✓ | ✓ | **FET** |
| 8 | **Reanomenar en bloc** | `F2` amb multi-selecció | `ac_renomena_seleccio` | ✓ | ✓ | — | **FET** |
| 9 | **Trobar i reemplaçar** | `Ctrl+H` | `ac_troba_i_reemplaca` | ✓ | ✓ | — | **FET** |
| 10 | **Moure un clip / BLOC** | arrossegar el **cos** (guard `Ctrl+Shift` = duplicar) | `ac_mou_bloc` (`kind`) | ✓ | ✓ | ✓ | **FET** (§6.3) |
| 11 | **Moure una marca** (fi = inici del següent) | — | `ac_move_chord`, `ac_move_section`, `ac_mou_tall` | ✓ | ✓ | ✓ | **FET** (camí de la vora · MCP `ac_mou_tall`) |
| 12 | **Nudge** (moure una frontera) | `←` / `→` · `Alt+←`/`→` (vora dreta) | `ac_nudge` (`direccio`, `estira`, `pas`) | ✓ | ✓ | ✓ | **FET** (`←`/`→` mou la frontera del tram; `Alt` la de la dreta) |
| 13 | **Redimensionar (vores lliures)** | arrossegar la **vora** del clip | `ac_nudge(estira)` | ✓ | ✓ | ✓ | **FET**: nucli únic (`redimensiona_clips` + `redimensiona_acord`/`redimensiona_seccio`) i el gest del visor hi enganxat · vores **LLIURES** (§6.6): estirar talla/elimina el veí |
| 14 | **Duplicar** | `Ctrl+D` | `ac_duplica_seleccio` | ✓ | ✓ | ✓ | **FET**: nucli únic `duplica_bloc_clips` (§2: la còpia va DESPRÉS i sobreescriu el tram, §6.3) |
| 15 | **Duplicar arrossegant** | `Ctrl+Shift`+arrossegar (a l'origen hi torna una còpia) | `ac_duplica_a` | ✓ | ✓ | — | **FET** (GUI + MCP). Als trams de BPM/compàs **no hi ha aquest gest**: l'arrossegar del cos hi mou el punt de canvi; es duplica amb `Ctrl+D` (#14) o copiar/enganxar (#16) |
| 16 | **Copiar / Retallar / Enganxar** | `Ctrl+C` / `Ctrl+X` / `Ctrl+V` (`Ctrl+Shift+V` = sense snap) | `ac_copia_seleccio`, `ac_retalla_seleccio`, `ac_enganxa_seleccio` | ✓ | ✓ | ✓ | **FET** (sobreescriu el tram; als trams obre les fronteres i hi canvia el BPM/compàs) |
| 17 | **Copiar/retallar el LOOP** | doble clic al regle · menú contextual de la banda | `ac_selecciona_loop` + les de copiar/retallar | ✓ | ✓ | ✓ | **FET** (composable; la selecció del LOOP ja inclou els trams) |
| 18 | **Mode fàcil** (re-regularitzar) | *Analitza ▸ Mode fàcil…* | `ac_regularitza` | ✓ | — | — | **FET** |

## 3. Selecció i vista

| # | Operació | GUI | MCP | Acords | Estr. | **BPM/comp.** | Estat |
|---|---|---|---|---|---|---|---|
| 19 | **Seleccionar un clip** | clic · `ac_select_clip` | `ac_select_clip` | ✓ | ✓ | ✓ | **FET** |
| 20 | **Multi-selecció (toggle)** | `Ctrl`+clic | `ac_toggle_selection` | ✓ | ✓ | ✓ | **FET**: també a la pista de BPM/compàs (`Ctrl`+clic) i per MCP |
| 21 | **Rang** | `Shift`+clic · `Ctrl`+arrossegar (marquee) | `ac_selecciona_rang` | ✓ | ✓ | ✓ | **FET** (trams inclosos; la **selecció del loop** encara és només acords+estructura) |
| 22 | **Seleccionar el del cursor** | clic + cursor | `ac_select_at_cursor` | ✓ | ✓ | ✓ | **FET** (`kind: tempo` al MCP i al menú) |
| 23 | **Seleccionar el LOOP** | doble clic a la banda | `ac_selecciona_loop` | ✓ | ✓ | ✓ | **FET** (la selecció del LOOP inclou els trams) |
| 24 | **Buida la selecció** | `Esc` | `ac_clear_selection` | ✓ | ✓ | ✓ | **FET** |
| 25 | **Consultar la selecció / cursor** | — | `ac_selection` | ✓ | ✓ | ✓ | **FET** |
| 26 | **Eina del timeline** (intel·ligent/marc) | tecla `E` · menú *Selecciona* · botó | `ac_set_eina` | ✓ | ✓ | ✓ | **FET** |
| 27 | **Zoom** | `Ctrl++` / `Ctrl+−` / `Ctrl+0` | `ac_zoom` (`tot`\|`seleccio`\|`in`\|`out`) | ✓ | ✓ | ✓ | **FET** |

## 4. Transport

| # | Operació | GUI | MCP | Estat |
|---|---|---|---|---|
| 28 | **Play / Pausa / Stop** | `Espai` · barra | `ac_play`, `ac_pause`, `ac_stop` | **FET** |
| 29 | **Cursor (seek)** | clic al regle | `ac_seek` | **FET** |
| 30 | **Loop A/B** (marcar, activar, netejar) | `Ctrl+[` / `Ctrl+]` · menú | `ac_mark_loop_a`, `ac_mark_loop_b`, `ac_set_loop`, `ac_neteja_loop` | **FET** |
| 31 | **Mute** | barra | `ac_set_mut` | **FET** |
| 32 | **Metrònom** | *Visualitza ▸ Metrònom* | `ac_set_metro` | **FET** |

## 5. Desfer i estat

| # | Operació | GUI | MCP | Estat |
|---|---|---|---|---|
| 33 | **Desfer / Refer** | `Ctrl+Z` · `Ctrl+Y` · `Ctrl+Shift+Z` | `ac_undo`, `ac_redo`, `ac_undo_list` | **FET** |
| 34 | **Estat complet de l'app** | — | `ac_status`, `ac_ping` | **FET** |
| 35 | **Llistar el model** | llistes del visor | `ac_list_chords`, `ac_list_sections`, `ac_list_tempo` | **FET** |

## 6. Tempo, anàlisi i opcions

| # | Operació | GUI | MCP | Estat |
|---|---|---|---|---|
| 36 | **Tempo · compàs · offset** | camps de la barra · *Analitza ▸ Mapa de tempo i compàs…* · *Analitza ▸ Detecta el mapa de tempo (per beats)…* | `ac_set_tempo` (global) · `ac_afegeix_tall`, `ac_elimina_tall`, `ac_mou_tall`, `ac_list_tempo` (mapa) · `ac_detecta_tempo_mapa` (inferir) | **FET** |
| 37 | **Analitzar** (acords + estructura) | `F5` · *Analitza* | `ac_analyze` | **FET** |
| 38 | **Opcions d'anàlisi** | *Paràmetres…* · *Inclou estructura* | `ac_get_options`, `ac_set_inclou_estructura` | **FET** |
| 39 | **Compàs 1** (detectar / marcar) | *Analitza ▸* | `ac_detect_downbeat`, `ac_mark_downbeat` | **FET** |
| 40 | **Tonalitat automàtica** | *Fitxer ▸ Tonalitat automàtica* | `ac_set_key_detect` | **FET** |
| 41 | **Inclou la partitura** (marca d'export) | *Fitxer ▸ Inclou la partitura* | `ac_set_inclou_partitura` | **FET** |

## 7. Fitxers, projecte i export

| # | Operació | GUI | MCP | Estat |
|---|---|---|---|---|
| 42 | **Obrir àudio** | `Ctrl+O` | `ac_open_wav` | **FET** |
| 43 | **Projecte**: crear/obrir/desar/desar com/còpia | *Fitxer ▸* | `ac_crea_projecte`, `ac_obre_projecte`, `ac_desa_projecte`, `ac_desa_com` | **FET** |
| 44 | **Recents** | *Fitxer ▸ Obre recent…* | `ac_recents` | **FET** |
| 45 | **Revertir** | *Fitxer ▸ Reverteix* | `ac_reverteix` | **FET** (sense confirm modal amb el pont) |
| 46 | **Còpia versionada (backup)** | automàtic (autosave) | `ac_fes_backup` | **FET** |
| 47 | **Exportar WAVs** | `Ctrl+E` | `ac_export_wav` (`partitura`, `async`) | **FET** — el paquet hi porta les **tres parts** (regla #12): `acords.csv`+`wavs_acords/`, `estructura_ABC.csv`+`wavs_estructura/` i **`mapa_tempo/`** (tempo+compàs) |
| 48 | **Exportar la partitura** | *Fitxer ▸ Exporta la partitura…* | `ac_export_partitura` | **FET** |
| 49 | **Obrir la carpeta de sortida** | *Fitxer ▸ Obre la carpeta de sortida* | `ac_open_output_folder` | **FET** |

## 8. Estat i exclusions (resum)

> ✅ **Cap pendent obert** (18-10-2026). Els tres ítems que hi havia aquí
> (vores lliures #13, duplicar #14/#15 i la «Fase 5» de les seccions) estaven
> **fets** i s'han verificat un per un abans de treure'ls: el gest del visor i
> l'MCP de redimensionar, el duplicat amb el destí de §6.3 i les vores lliures
> de les seccions (les dues bandes, també l'última).

### Pista de BPM/compàs (trams del mapa de tempo) — ✅ COMPLERTA

La pista comparteix amb acords i estructura **tot** el joc d'edició:
**afegir/partir** (obrir un *tall*), **partir per la meitat**, **eliminar**
(amb els veïns unint-se), **moure** (el cos mou el punt de canvi; les vores, les
fronteres), **redimensionar**, **nudge** (`←`/`→` i `Alt`), **desfer/refer**,
**selecció** (`Esc`, `ac_selection`, `Ctrl`+clic, `Shift`+clic, **marquee** i
**LOOP**), **porta-retalls** (`Ctrl+C/X/V`), **duplicar** (`Ctrl+D`) i
**MCP** (`ac_list_tempo`, `ac_afegeix_tall`, `ac_elimina_tall`, `ac_mou_tall`,
`ac_select_at_cursor` amb `kind: tempo`; `ac_set_tempo` és el BPM/compàs
**global** de la barra).

Les files amb `—` a la columna **BPM/comp.** són **exclusions deliberades**, no
pendents:

- **#6 Eliminar-ho TOT**: el mapa **no pot quedar buit** (ha de cobrir sempre
  `0..durada`); l'equivalent és deixar-hi un sol tram.
- **#8 Reanomenar en bloc**: el contingut d'un tram és numèric (BPM + compàs) i
  s'edita amb el diàleg/MCP; no hi ha noms inline.
- **#9 Trobar i reemplaçar**: idem — no hi ha text on buscar (es fa tram a tram
  o amb les eines del mapa).
- **#15 Duplicar arrossegant**: aquest gest, a la pista, ja el té pres el cos
  del tram (**mou el punt de canvi**); duplicar es fa amb `Ctrl+D` o el
  porta-retalls.
- **#18 Mode fàcil**: re-regularitza el **ritme harmònic** dels acords (i les
  seccions); no toca el mapa de tempo.

1. **Redimensionat amb vores lliures** (#13) — nucli únic FET (S2a: `redimensiona_clips`); falta el gest del visor i l'MCP.
2. **Duplicar**: alinear el destí amb **§6.3** (#14) i exposar el gest de **duplicar
   arrossegant** a l'MCP (#15).
3. **Seccions**: resta de la Fase 5 del pla (vores lliures).

> ✅ **Fet el 17-10-2026**: el **moviment de bloc** (§6.3, #10) amb el destí; la
> **paritat d'estructura** (`mou_bloc_seccions`, gest del visor i `ac_mou_bloc` amb
> `kind`); el símbol **`-`** a **tota** l'estructura (també a `normalitza_cobertura`);
> i la neteja del codi mort (`_move_section_group`).
