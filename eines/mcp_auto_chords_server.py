#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Servidor MCP d'AUTO CHORDS (stdio, stdlib pur).

Connecta opencode amb l'app AUTO CHORDS **viva** a través del pont
`app/mcp_bridge.py` (que només s'obre amb el llançador `AUTO_CHORDS_MCP.sh`).

    opencode ──stdio(JSON-RPC/newline)──► aquest servidor
        ──TCP 127.0.0.1(endpoint)──► app/mcp_bridge.py dins l'app

⚠️ **Stdlib pur** (zero deps) → immune al problema d'AVX/SIGILL del Q9400
(mateix criteri que el servidor MCP de REAPER).

Config a `~/.config/opencode/opencode.jsonc` (clau local `mcp`):
    "mcp_auto_chords": {
      "type": "local",
      "command": ["python3", "<projecte>/eines/mcp_auto_chords_server.py"],
      "enabled": false
    }

Ús manual (per verificar):
    python3 eines/mcp_auto_chords_server.py --tools        # llista eines
    python3 eines/mcp_auto_chords_server.py --call ac_status
"""
from __future__ import annotations

import json
import os
import socket
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENDPOINT_PATH = (os.environ.get("AUTO_CHORDS_MCP_ENDPOINT")
                 or os.path.join(ROOT, "temp", "mcp_bridge.json"))

SERVER_NAME = "mcp_auto_chords"
SERVER_VERSION = "0.1.0"
PROTOCOL_DEFAULT = "2024-11-05"

# ── Catàleg d'eines MCP ──────────────────────────────────────────────────────
# Cada eina té un nom `ac_*` i l'operació equivalent al pont (sense el prefix).
# Els esquemes són JSON Schema (subset que opencode/LLM entenen bé).
_TOOLS = [
    ("ac_ping", "ping",
     "Comprova que el pont MCP d'Auto Chords és viu (l'app ha d'estar oberta "
     "amb AUTO_CHORDS_MCP.sh).", {}),
    ("ac_status", "status",
     "Estat complet de l'app viva: àudio obert, mode (BPM/lliure), BPM, compàs, "
     "offset, nombre d'acords/seccions, transport (sonant, posició, loop, mute, "
     "metrònom) i carpeta de sortida.", {}),
    ("ac_list_chords", "list_chords",
     "Llista els acords del model viu (índex, temps en segons, nom).", {}),
    ("ac_list_sections", "list_sections",
     "Llista les seccions/estructura del model viu (índex, inici, fi, lletra, "
     "família).", {}),
    ("ac_selection", "selection",
     "Clips seleccionats al timeline i posició del cursor.", {}),
    ("ac_undo_list", "undo_list",
     "Mida de les piles de desfer/refer (útil per verificar edicions).", {}),
    ("ac_add_chord", "add_chord",
     "Afegeix un acord a un temps donat (segons).",
     {"t_s": {"type": "number", "description": "instant en segons"},
      "acord": {"type": "string", "description": "nom de l'acord (p. ex. Cmaj7, N)"}}),
    ("ac_rename_chord", "rename_chord",
     "Reanomena un acord per índex.",
     {"index": {"type": "integer"}, "acord": {"type": "string"}}),
    ("ac_move_chord", "move_chord",
     "Mou l'inici d'un acord (per índex) a un temps nou en segons.",
     {"index": {"type": "integer"}, "t_s": {"type": "number"}}),
    ("ac_delete_chord", "delete_chord",
     "Elimina un acord per índex.", {"index": {"type": "integer"}}),
    ("ac_add_section", "add_section",
     "Afegeix una secció/estructura (inici i fi en segons).",
     {"ini_s": {"type": "number"}, "fi_s": {"type": "number"},
      "lletra": {"type": "string"}, "familia": {"type": "string"}}),
    ("ac_rename_section", "rename_section",
     "Reanomena una secció per índex (lletra i/o família).",
     {"index": {"type": "integer"}, "lletra": {"type": "string"},
      "familia": {"type": "string"}}),
    ("ac_move_section", "move_section",
     "Mou/redimensiona una secció (inici i fi en segons).",
     {"index": {"type": "integer"}, "ini_s": {"type": "number"},
      "fi_s": {"type": "number"}}),
    ("ac_delete_section", "delete_section",
     "Elimina una secció per índex.", {"index": {"type": "integer"}}),
    ("ac_undo", "undo", "Desfer el darrer canvi del model (acords/seccions).", {}),
    ("ac_redo", "redo", "Refer el darrer canvi desfet.", {}),
    ("ac_seek", "seek", "Mou el cursor de reproducció a un temps (segons).",
     {"t_s": {"type": "number"}}),
    ("ac_play", "play", "Reprodueix des de la posició actual.", {}),
    ("ac_pause", "pause", "Pausa la reproducció.", {}),
    ("ac_stop", "stop", "Atura i torna a l'inici.", {}),
    ("ac_mark_loop_a", "mark_loop_a", "Marca l'inici del loop (A) al cursor.", {}),
    ("ac_mark_loop_b", "mark_loop_b", "Marca el fi del loop (B) al cursor.", {}),
    ("ac_set_loop", "set_loop", "Activa/desactiva el loop A-B.",
     {"on": {"type": "boolean"}}),
    ("ac_set_mut", "set_mut", "Activa/desactiva el mute de la cançó.",
     {"on": {"type": "boolean"}}),
    ("ac_zoom", "zoom",
     "Canvia el zoom del timeline (mode: tot | seleccio | in | out).",
     {"mode": {"type": "string"}}),
    ("ac_open_wav", "open_wav",
     "Obre un fitxer d'àudio pel camí absolut (converteix a WAV si cal).",
     {"path": {"type": "string"}}),
    ("ac_analyze", "analyze",
     "Llança l'anàlisi (acords+estructura) amb les opcions ja desades, sense "
     "diàleg. És asíncrona: consulta ac_status per seguir-la.", {}),
    ("ac_export_wav", "export_wav",
     "Exporta el paquet de WAV's per al DAW (síncrona; pot trigar).", {}),
    ("ac_set_tempo", "set_tempo",
     "Fixa BPM, compàs (bpb) i/o offset (segons) i ho aplica al visor.",
     {"bpm": {"type": "number"}, "bpb": {"type": "integer"},
      "offset_s": {"type": "number"}}),
    # A7: accions de l'app que faltaven al pont.
    ("ac_set_metro", "set_metro",
     "Activa/desactiva el metrònom (només té sentit en mode BPM · compàs).",
     {"on": {"type": "boolean"}}),
    ("ac_set_key_detect", "set_key_detect",
     "Activa/desactiva la detecció de tonalitat (qm-keydetector) per a la "
     "partitura: amb ella, l'armadura es posa sola.",
     {"on": {"type": "boolean"}}),
    ("ac_detect_downbeat", "detect_downbeat",
     "Detecta automàticament el compàs 1 (downbeat) de la cançó.", {}),
    ("ac_mark_downbeat", "mark_downbeat",
     "Marca el compàs 1 al cursor.", {}),
    ("ac_open_output_folder", "open_output_folder",
     "Obre la carpeta de sortida amb el gestor de fitxers del sistema.", {}),
    ("ac_select_clip", "select_clip",
     "Selecciona un clip (kind: chord|section, index); substitueix la selecció.",
     {"kind": {"type": "string"}, "index": {"type": "integer"}}),
    ("ac_toggle_selection", "toggle_selection",
     "Afegeix/treu un clip de la selecció múltiple (com Ctrl+clic).",
     {"kind": {"type": "string"}, "index": {"type": "integer"}}),
    ("ac_clear_selection", "clear_selection", "Buida la selecció de clips.", {}),
    ("ac_select_at_cursor", "select_at_cursor",
     "Selecciona el clip que conté el cursor (kind: chord|section).",
     {"kind": {"type": "string"}}),
]

_OP_PER_TOOL = {nom: op for (nom, op, _d, _s) in _TOOLS}


def _esquema(propietats):
    return {"type": "object", "properties": propietats,
            "additionalProperties": False}


def _tools_mcp():
    return [{"name": nom, "description": desc,
             "inputSchema": _esquema(props)}
            for (nom, _op, desc, props) in _TOOLS]


def _log(msg):
    print(f"[mcp_auto_chords] {msg}", file=sys.stderr, flush=True)


# ── Client del pont ──────────────────────────────────────────────────────────
class PontNoActiu(RuntimeError):
    pass


def _info_endpoint():
    try:
        with open(ENDPOINT_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def crida_pont(op, params=None, timeout=120.0):
    """Envia una operació al pont dins l'app i en retorna el resultat."""
    info = _info_endpoint()
    if not info or "port" not in info:
        raise PontNoActiu(
            "El pont MCP no és actiu. Arrenca l'app amb AUTO_CHORDS_MCP.sh "
            f"(no trobo {ENDPOINT_PATH}).")
    try:
        s = socket.create_connection(("127.0.0.1", int(info["port"])), timeout=timeout)
    except OSError as e:
        raise PontNoActiu(
            f"No em puc connectar al pont ({info.get('port')}): {e}. "
            "Arrenca l'app amb AUTO_CHORDS_MCP.sh.") from e
    try:
        req = json.dumps({"token": info.get("token"), "op": op,
                          "params": params or {}}, ensure_ascii=False) + "\n"
        s.sendall(req.encode("utf-8"))
        buffer = b""
        while b"\n" not in buffer:
            troç = s.recv(65536)
            if not troç:
                break
            buffer += troç
        if not buffer:
            raise RuntimeError("El pont ha tancat la connexió sense resposta.")
        resp = json.loads(buffer.split(b"\n", 1)[0].decode("utf-8"))
        if not resp.get("ok"):
            raise RuntimeError(resp.get("error") or "error desconegut del pont")
        return resp.get("result")
    finally:
        s.close()


# ── Protocol MCP (JSON-RPC 2.0 sobre stdio) ──────────────────────────────────
def _resposta(missatge_id, result=None, error=None):
    m = {"jsonrpc": "2.0", "id": missatge_id}
    if error is not None:
        m["error"] = error
    else:
        m["result"] = result
    return m


def gestiona(msg):
    """Retorna el dict de resposta, o None si és una notificació (sense id)."""
    if not isinstance(msg, dict):
        return _resposta(None, error={"code": -32600, "message": "missatge invàlid"})
    metode = msg.get("method")
    mid = msg.get("id")
    connexions = {"initialize", "tools/list", "tools/call", "ping",
                  "resources/list", "prompts/list"}

    if metode in ("notifications/initialized",) or (mid is None and metode not in connexions):
        return None
    if mid is None and metode is None:
        return None

    if metode == "initialize":
        params = msg.get("params") or {}
        versio = params.get("protocolVersion") or PROTOCOL_DEFAULT
        return _resposta(mid, {
            "protocolVersion": versio,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })
    if metode == "ping":
        return _resposta(mid, {})
    if metode == "resources/list":
        return _resposta(mid, {"resources": []})
    if metode == "prompts/list":
        return _resposta(mid, {"prompts": []})
    if metode == "tools/list":
        return _resposta(mid, {"tools": _tools_mcp()})
    if metode == "tools/call":
        params = msg.get("params") or {}
        nom = params.get("name")
        args = params.get("arguments") or {}
        if nom not in _OP_PER_TOOL:
            return _resposta(mid, error={"code": -32602,
                                         "message": f"eina desconeguda: {nom}"})
        try:
            resultat = crida_pont(_OP_PER_TOOL[nom], args)
            text = json.dumps(resultat, ensure_ascii=False, indent=2)
            return _resposta(mid, {"content": [{"type": "text", "text": text}],
                                   "isError": False})
        except Exception as e:  # noqa: BLE001 — l'error va al client, no tomba res
            return _resposta(mid, {"content": [{"type": "text", "text": str(e)}],
                                   "isError": True})
    return _resposta(mid, error={"code": -32601,
                                 "message": f"mètode no implementat: {metode}"})


def serveix():
    _log(f"servidor MCP en marxa (pont a {ENDPOINT_PATH})")
    entrada = sys.stdin.buffer
    while True:
        linia = entrada.readline()
        if not linia:
            break
        linia = linia.strip()
        if not linia:
            continue
        try:
            msg = json.loads(linia.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            _log(f"json invàlid: {e}")
            continue
        resposta = gestiona(msg)
        if resposta is None:
            continue
        sys.stdout.write(json.dumps(resposta, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def _main_cli(argv):
    if "--tools" in argv:
        print(json.dumps({"tools": _tools_mcp()}, ensure_ascii=False, indent=2))
        return 0
    if "--call" in argv:
        i = argv.index("--call")
        eina = argv[i + 1] if i + 1 < len(argv) else ""
        if eina not in _OP_PER_TOOL:
            _log(f"eina desconeguda: {eina!r}")
            return 2
        args = {}
        if "--args" in argv:
            try:
                args = json.loads(argv[argv.index("--args") + 1])
            except (ValueError, IndexError) as e:
                _log(f"args invàlids: {e}")
                return 2
        try:
            print(json.dumps(crida_pont(_OP_PER_TOOL[eina], args),
                             ensure_ascii=False, indent=2))
            return 0
        except Exception as e:  # noqa: BLE001
            _log(f"ERROR: {e}")
            return 1
    serveix()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main_cli(sys.argv[1:]))
