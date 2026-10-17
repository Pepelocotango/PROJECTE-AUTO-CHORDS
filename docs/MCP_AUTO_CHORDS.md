# MCP d'AUTO CHORDS — controlar l'app viva des d'opencode

> Afegit 2026-10-13. Permet que un agent (opencode) **llegeixi i accioni
> l'estat viu** de l'app mentre tu la veus, per depurar i provar conjuntament.
> És **additiu**: si no l'actives, l'app funciona exactament com sempre.

## Què és i per què

L'app AUTO CHORDS és una app d'escriptori (PyQt5). Aquest connector fa el mateix
que `nelson` (LibreOffice viu) o `reaper` (REAPER viu): obre un canal perquè
l'agent llegeixi/editi el **model real** (acords, seccions, transport) en comptes
d'intentar-ho per píxels. Tots dos mireu la **mateixa finestra**.

## Arquitectura

```
opencode ──stdio (JSON-RPC/MCP)──► eines/mcp_auto_chords_server.py   (stdlib pur)
                                          │  JSON per línia · TCP 127.0.0.1
                                          ▼
                                   app/mcp_bridge.py  (DINS l'app viva)
                                          │  cua + QTimer  → fil de Qt
                                          ▼
                                   Finestra / Visor / TimelineView
```

- **Servidor MCP** (`eines/mcp_auto_chords_server.py`): `stdlib` pur → immune a
  AVX/SIGILL (Q9400). Tradueix eines MCP ↔ operacions del pont.
- **Pont** (`app/mcp_bridge.py`): servidor TCP localhost dins l'app. Cap accés a
  widgets fora del fil de Qt: tot passa per una cua que buida un `QTimer` del fil
  principal (patró del pont de REAPER).
- **Acord (endpoint)**: `temp/mcp_bridge.json` (`{port, token, pid, ...}`),
  gitignorat. El servidor el llegeix per saber on connectar-se. Esborrat en
  sortir net; si l'app peta, queda obsolet i el servidor avisa que cal
  re-arrencar l'app.
- **Seguretat**: només `127.0.0.1`, amb **testimoni** aleatori per sessió.

## Com s'activa

1. **Arrenca l'app amb el pont** (en comptes de `AUTO_CHORDS.sh`):
   ```bash
   ./AUTO_CHORDS_MCP.sh
   ```
   El llançador enganxa el pont **sense tocar `app/main.py`** (embolcalla la
   classe `Finestra` en una subclasse).
   > ⚠️ Només una instància de l'app alhora (bloqueig d'instància única de l'app).

2. **Activa el MCP a opencode**: a `~/.config/opencode/opencode.jsonc`, posa
   `"enabled": true` a l'entrada `mcp_auto_chords` i **reinicia** opencode (no hi
   ha recàrrega en calent).

3. Fet: l'agent ja veu les eines `ac_*`. En acabar, torna a `"enabled": false` i
   reinicia (estalvia context).

## Eines exposades (67)

| Lectura | Acció (model) | Transport / vista | Finestra |
|---|---|---|---|
| `ac_ping` | `ac_add_chord` (t_s, acord) | `ac_seek` (t_s) | `ac_open_wav` (path) |
| `ac_status` | `ac_rename_chord` (index, acord) | `ac_play` / `ac_pause` / `ac_stop` | `ac_analyze` |
| `ac_list_chords` | `ac_move_chord` (index, t_s) | `ac_mark_loop_a` / `ac_mark_loop_b` | `ac_export_wav` (partitura?) · `ac_export_partitura` |
| `ac_list_sections` | `ac_delete_chord` (index) | `ac_set_loop` (on) | `ac_set_tempo` (bpm, bpb, offset_s) · `ac_get_options` |
| `ac_selection` | `ac_add_section` (ini_s, fi_s, lletra, familia) | `ac_set_mut` (on) | `ac_set_metro` (on) |
| `ac_undo_list` | `ac_rename_section` / `ac_move_section` / `ac_delete_section` | `ac_zoom` (mode) | `ac_set_key_detect` (on) |
| | `ac_undo` / `ac_redo` | `ac_select_clip` (kind, index) · `ac_toggle_selection` (kind, index) · `ac_clear_selection` · `ac_select_at_cursor` (kind) | `ac_detect_downbeat` · `ac_mark_downbeat` · `ac_open_output_folder` |

> **67 eines** en total. Les de l'última fila (metrònom, tonalitat automàtica,
> compàs 1, carpeta de sortida i selecció/multi-selecció) es van afegir per
> **A7**, perquè eren funcions de l'app sense cap eina equivalent.

### Paritat d'ACCIONS amb la GUI (2026-10-17) — 16 eines noves

> **Criteri**: tot el que l'usuari pot **fer** des de la GUI, l'agent també ho
> ha de poder fer per eines. Cap eina obre diàlegs (tot arriba per paràmetre o
> per l'estat vigent). Les 16 eines noves fan servir les **mateixes
> transaccions d'undo/desat** que la GUI.

| Eina | Què fa |
|---|---|
| `ac_copia_seleccio` | Copia la selecció al porta-retalls INTERN (Ctrl+C). |
| `ac_retalla_seleccio` | Retalla: copia i esborra la selecció (Ctrl+X). |
| `ac_enganxa_seleccio` (`t_s`?) | Enganxa al cursor (Ctrl+V), **sobreescrivint** el tram; `t_s` mou el cursor abans. |
| `ac_esborra_seleccio` (`kind`?) | Esborra els clips seleccionats (tecla Del), d'un tipus o tots. |
| `ac_duplica_seleccio` (`kind`?) | Duplica els clips seleccionats (Ctrl+D). |
| `ac_renomena_seleccio` (`nom`, `kind`?) | Reanomena **en bloc** la selecció del tipus (F2 amb multi). |
| `ac_selecciona_rang` (`t0`, `t1`, `kind`?) | Selecció per **rang de temps** (Shift+clic; sense `kind`, les dues pistes). |
| `ac_selecciona_loop` | Selecciona tot el que hi ha dins el **loop A/B** (cursor al final). |
| `ac_nudge` (`direccio`, `estira`?, `pas`?) | Nudge d'una frontera del clip seleccionat (←/→; `estira` = Alt+←/→). |
| `ac_mou_bloc` (`dt_s`, `first`?, `last`?) | Mou un **bloc** d'acords preservant-ne la durada (l'arrossegament; DESTÍ §6.3). |
| `ac_troba_i_reemplaca` (`camp`, `troba`, `reemplaca`) | **Troba i reemplaça** xifrats o etiquetes a tot el tema (Ctrl+H). |
| `ac_reverteix` | Torna el projecte a l'**últim desat** (sense confirmació modal). |
| `ac_neteja_loop` | Desactiva i esborra el **loop A/B**. |
| `ac_set_eina` (`mode`) | Tria l'**eina** del timeline: `intel·ligent` \| `marc`. |
| `ac_set_inclou_estructura` (`on`) | Commuta «**Inclou estructura**» (anàlisi/export). |
| `ac_set_inclou_partitura` (`on`) | Commuta «**Inclou la partitura**» (export de WAVs). |

> **Exclusions (a propòsit)**: `Surt`, mostrar/amagar els docks de vista
> (`log`, tipus d'acord) i «Paràmetres…» — no són accions de contingut per a un
> agent, i «Obre recent…» ja és composable (`ac_recents` + `ac_obre_projecte`).

### Projectes autocontinguts i paritat d'edició #11 (2026-10-15)

| Eina | Què fa |
|---|---|
| `ac_crea_projecte` (`path`, `wav`?) | Crea un `.acproj` a `path` a partir d'un WAV (el paràmetre o el WAV obert). |
| `ac_obre_projecte` (`path`) | Obre un projecte `.acproj` (o la seva carpeta). |
| `ac_desa_projecte` | Desa el projecte obert al seu lloc (document + CSVs). |
| `ac_desa_com` (`path`) | Desa una **còpia** del projecte a una carpeta nova. |
| `ac_fes_backup` | Còpia versionada a `backup/<data-hora>/` (rotació de 10). |
| `ac_recents` | Llista els projectes recents que encara existeixen. |
| `ac_parteix_acord` (`index`, `t_s`, `nom`?) | Parteix l'acord `index` pel temps `t_s` (regla #11). |
| `ac_fusiona_acord` (`index`, `amb`?) | Fusiona l'acord amb el veí (`seguent`\|`anterior`). |
| `ac_parteix_seccio` (`index`, `t_s`, `lletra`?, `familia`?) | Parteix la secció `index` pel temps `t_s`. |
| `ac_fusiona_seccio` (`index`, `amb`?) | Fusiona la secció amb el veí (`seguent`\|`anterior`). |
| `ac_regularitza` (`nivell`?, `modul_compassos`?) | **Mode fàcil**: re-regularitza els acords de l'**anàlisi crua** a la graella (ritme harmònic `auto`\|`compas`\|`mig`\|`temps`); `modul_compassos` encaixa també els talls de secció a blocs. |

> ⚠️ Les eines de **projecte** **no obren cap diàleg**: la ruta és un paràmetre i,
> si falta o no existeix, l'eina retorna un **error clar** (mai encalla l'agent).
> L'**últim acord** no es pot partir (la seva durada arriba al final de la WAV):
> cal afegir-ne un abans, com a la GUI.

- Les **edicions** passen per la **mateixa transacció d'undo** que la GUI
  (`_undo_marca`/`_undo_commit`) i **desen el CSV** + regeneren l'ABC: pots
  desfer amb `Ctrl+Z` el que fa l'agent.
- Si una edició trenca la **lògica temporal** (inici duplicat/invertit, etc.),
  es **rebutja sencera** amb un error clar; l'estat no canvia.

> ✅ **Reanomenament sanejat** (IMPLEMENTAT): els noms d'acord es **sanegen** de manera canònica — `pipeline.saneja_nom_acord()` (el mateix que fa l'export) — a **tots** els camins, **MCP inclòs** (`ac_rename_chord`). Així el nom del **model** i el del **CSV** sempre coincideixen i no hi entren caràcters invàlids. Noms habituals intactes (`C#m7`, `N`; `Am/G` → `Am_G`).

## Verificació manual (sense opencode)

```bash
# 1) Amb l'app oberta per AUTO_CHORDS_MCP.sh:
.venv/bin/python eines/mcp_auto_chords_server.py --tools            # llista les eines
.venv/bin/python eines/mcp_auto_chords_server.py --call ac_status
.venv/bin/python eines/mcp_auto_chords_server.py --call ac_list_chords
.venv/bin/python eines/mcp_auto_chords_server.py --call ac_add_chord --args '{"t_s":1.0,"acord":"Cmaj7"}'
```

Tests automàtics (logica del pont + protocol, amb dobles i sense GUI):
```bash
.venv/bin/python -m unittest discover -s tests -p "test_mcp_bridge.py"
```

**Prova completa EN VIU** (protocol MCP real; requereix l'app oberta amb `AUTO_CHORDS_MCP.sh`):
```bash
# WAV de prova (qualsevol WAV) i carpeta temporal del projecte:
AC_PROVA_WAV=/tmp/ac_prova.wav AC_PROVA_PROJ=/tmp/ac_prova_proj \
  .venv/bin/python eines/prova_mcp_completa.py
```
Cobreix **57 comprovacions**: handshake, estat, transport, model (acords i
seccions), selecció, opcions, paritat #11 (partir/fusionar), mode fàcil i
projectes. Usa l'`AUTO_CHORDS_MCP_ENDPOINT` de l'app oberta.

## Trampes i regles (no repetir)

1. **Qt no és thread-safe**: mai tocar widgets/model des del fil del socket.
   Tota operació passa pel `QTimer` del fil principal (el pont ja ho fa així).
2. **Diàlegs modals**: cap crida MCP obre diàlegs modals (l'app els fa **no
   modals** amb el pont actiu i el text viatja a la resposta: `avis`).
   `ac_export_wav` té **`async: true`** per no bloquejar (progrés a `ac_status`).
   ⚠️ **LIMITACIÓ ACCEPTADA** (decisió de l'operador, 14-10-2026): el **confirm
   de re-anàlisi** («Continua i descarta / Cancel·la») és **modal** i **retorna
   una decisió**; fer-lo no-modal voldria un flux asíncron (no es fa). **No
   afecta cap crida MCP** (el pont hi passa `pregunta=False`): només passaria si
   un **humà** deixa el diàleg obert **i** algú crida l'MCP → el pont espera fins
   que es tanqui (acotat pel **timeout de 120 s**). Si mai molesta, afegir-hi un
   timeout que el tanqui com a *Cancel·la* és una opció.
3. **Instància única**: no pots tenir l'app oberta "normal" i la "amb pont"
   alhora; cal tancar-ne una.
4. **Endpoint obsolet**: si l'app peta, `temp/mcp_bridge.json` queda vell; el
   servidor ho detecta i avisa. Re-arrenca l'app amb `AUTO_CHORDS_MCP.sh`.
5. **No interfereix amb el codi**: el pont crida els mètodes existents del visor;
   no modifica cap fitxer de l'app per funcionar. Si algun mètode intern canvia
   de nom, caldrà ajustar `app/mcp_bridge.py`.

## Fitxers afegits (tots nous)

- `app/mcp_bridge.py` — pont dins l'app.
- `eines/mcp_auto_chords_server.py` — servidor MCP (stdio).
- `eines/mcp_auto_chords_launcher.py` — llançador que enganxa el pont.
- `AUTO_CHORDS_MCP.sh` — llançador d'escriptori amb pont.
- `tests/test_mcp_bridge.py` — tests.
- `docs/MCP_AUTO_CHORDS.md` — aquest document.

---

## ✅ P2 (A4–A9) — **IMPLEMENTAT i verificat** (14-10-2026)

> ✅ Ja és al codi; **51 eines**. Verificat amb **gates funcionals MCP** (OC-7/405-406).

- **A4 — Partitura des de l'MCP**: eina nova **`ac_export_partitura`** (MusicXML + PDF + MSCZ si hi ha MuseScore) i **`ac_export_wav`** amb el paràmetre **`partitura`** (força si s'hi inclou, sense canviar la marca de l'app). ✅
- **A5 — `ac_export_wav` asíncrona**: paràmetre **`async: true`** → torna de seguida; el progrés es consulta a **`ac_status`** (`exportant` / `exporta_iniciat`). ✅
- **A6 — `ac_analyze` amb opcions**: eina nova **`ac_get_options`** (opcions actuals i defectes: `chords`/`bpm`/`structure`/`clean`). ✅
- **A7 — Més eines**: **`ac_set_key_detect`** (tonalitat), **`ac_set_metro`** (metrònom), **`ac_detect_downbeat` / `ac_mark_downbeat`** (compàs 1), **`ac_open_output_folder`**, i **multi-selecció** (`ac_select_clip`, `ac_toggle_selection`, `ac_clear_selection`, `ac_select_at_cursor`). ✅
- **A8 — MCP OFF + instància única**: el MCP és **OFF per defecte** i l'app és d'**instància única** → **tanqueu l'altra instància** o arrenqueu directament amb **`./AUTO_CHORDS_MCP.sh`**. ✅
- **A9 — Autocomprovació amb `ffmpeg`**: l'autocomprovació d'arrencada ara **avisa si no troba `ffmpeg`** (només podrà obrir WAV PCM). ✅

---

## ✅ Funcions noves cobertes (2026-10-15)

> ✅ **FET**: les funcions que abans eren **només GUI** ja tenen eines `ac_*`
> (vegeu «Projectes autocontinguts i paritat d'edició #11», més amunt). **51 eines**.

- **Projectes autocontinguts** (vegeu `docs/PROJECTES.md`): `ac_crea_projecte`,
  `ac_obre_projecte`, `ac_desa_projecte`, `ac_desa_com`, `ac_fes_backup` i
  `ac_recents`. *(La **recuperació de sessió** continua sent automàtica a l'arrencada
  de l'app — no cal eina.)*
- **Paritat d'edició #11** (`docs/REGLES_DE_LA_APP.md` §11): `ac_parteix_acord`,
  `ac_fusiona_acord`, `ac_parteix_seccio` i `ac_fusiona_seccio` — la GUI i l'MCP
  ofereixen **el mateix joc** d'operacions.

> ✅ Verificat: **51 eines** a `--tools`, coherència pont↔servidor al test
> `test_mapa_eines_coincideix_amb_pont`, i **prova en viu pel protocol MCP real**
> (initialize + tools/list + 25 crides amb un WAV i un projecte de prova).

---

## ✅ Paritat d'ACCIONS amb la GUI (2026-10-17) — **67 eines**

> ✅ Verificat: **67 eines** a `--tools` i coherència pont↔servidor
> (`test_mapa_eines_coincideix_amb_pont`). Les 16 eines noves es proven **amb
> la Finestra REAL** (i el seu visor/timeline) a `tests/test_mcp_paritat.py`
> (22 tests): porta-retalls, esborrar/duplicar/reanomenar la selecció, rang,
> loop, nudge, mou_bloc, troba i reemplaça, revertir (sense modal), eina i
> commutadors d'estructura/partitura. **Cap eina obre diàlegs.**

