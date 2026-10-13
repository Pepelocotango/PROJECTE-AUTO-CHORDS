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

## Eines exposades (29)

| Lectura | Acció (model) | Transport / vista | Finestra |
|---|---|---|---|
| `ac_ping` | `ac_add_chord` (t_s, acord) | `ac_seek` (t_s) | `ac_open_wav` (path) |
| `ac_status` | `ac_rename_chord` (index, acord) | `ac_play` / `ac_pause` / `ac_stop` | `ac_analyze` |
| `ac_list_chords` | `ac_move_chord` (index, t_s) | `ac_mark_loop_a` / `ac_mark_loop_b` | `ac_export_wav` |
| `ac_list_sections` | `ac_delete_chord` (index) | `ac_set_loop` (on) | `ac_set_tempo` (bpm, bpb, offset_s) |
| `ac_selection` | `ac_add_section` (ini_s, fi_s, lletra, familia) | `ac_set_mut` (on) | |
| `ac_undo_list` | `ac_rename_section` / `ac_move_section` / `ac_delete_section` | `ac_zoom` (mode) | |
| | `ac_undo` / `ac_redo` | | |

- Les **edicions** passen per la **mateixa transacció d'undo** que la GUI
  (`_undo_marca`/`_undo_commit`) i **desen el CSV** + regeneren l'ABC: pots
  desfer amb `Ctrl+Z` el que fa l'agent.
- Si una edició trenca la **lògica temporal** (inici duplicat/invertit, etc.),
  es **rebutja sencera** amb un error clar; l'estat no canvia.

> ✅ **Reanomenament sanejat** (implementat, pendent de commit): els noms d'acord es **sanegen** de manera canònica — `pipeline.saneja_nom_acord()` (el mateix que fa l'export) — a **tots** els camins, **MCP inclòs** (`ac_rename_chord`). Així el nom del **model** i el del **CSV** sempre coincideixen i no hi entren caràcters invàlids. Noms habituals intactes (`C#m7`, `N`; `Am/G` → `Am-G`).

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

## Trampes i regles (no repetir)

1. **Qt no és thread-safe**: mai tocar widgets/model des del fil del socket.
   Tota operació passa pel `QTimer` del fil principal (el pont ja ho fa així).
2. **Diàlegs modals**: `ac_analyze` va **sense diàleg** (`pregunta=False`).
   `ac_export_wav` és síncrona; si surt un `QMessageBox` (error), el pont espera
   que es tanqui (i el client rep temps d'espera). No és habitual en un flux bo.
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

## ⏳ Pendent — P2 (A4–A9): **EN IMPLEMENTACIÓ**

> ⚠️ **Encara NO són al codi.** P2 està **aprovat i en curs per OC-4**; aquesta
> documentació queda **preparada** i es finalitzarà (noms d'eines/paràmetres exactes)
> quan es commiti — es verificarà amb **OC-4** abans de donar-la per bona.

- **A4 — Partitura des de l'MCP i amb els WAVs**: que l'**export** (i l'MCP) incloguin també la **partitura** (MusicXML/PDF/MSCZ), no només l'acció de menú.
- **A5 — `ac_export_wav` amb progrés**: avui l'export és **síncrona** i no informa del progrés; es preveu **retornar progrés/estat** per no semblar “penjada”.
- **A6 — `ac_analyze` amb opcions**: avui només fa servir les opcions **ja desades**; es preveu poder-hi **passar opcions** (BPM/acords/estructura).
- **A7 — Més camps/eines MCP**: exposar al pont el que el menú ja té i l'MCP no: **tonalitat**, **metrònom**, **marca el compàs 1**, **carpeta de sortida** i **multi-selecció**.
- **A8 — MCP OFF + instància única**: el MCP és **OFF per defecte** i l'app és d'**instància única** → **no conviu** amb una altra app oberta. Cal documentar **com conviure-hi**: tancar l'altra instància o arrencar directament amb `./AUTO_CHORDS_MCP.sh`.
- **A9 — Autocomprovació amb `ffmpeg`**: l'autocomprovació d'arrencada comprova els Vamp i `ACORDS_PY`; **afegir-hi `ffmpeg`** (opcional, només per importar formats no-WAV).

> 📌 Quan OC-4 ho commiteji: moure aquests punts a les seccions corresponents
> (§«Eines exposades» per A4–A7, §«Com s'activa» per A8) i treure aquesta secció.
