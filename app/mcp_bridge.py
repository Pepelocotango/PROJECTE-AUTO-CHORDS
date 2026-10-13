#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pont MCP d'AUTO CHORDS — permet controlar l'app **viva** des d'un client MCP.

Arquitectura (mateix patró que `reaper`/`nelson` al sistema de l'operador):

    opencode ──stdio──► eines/mcp_auto_chords_server.py
                              │  (JSON per línia, TCP 127.0.0.1)
                              ▼
                       app/mcp_bridge.py  (DINS l'app viva)
                              │  (salt al fil de Qt: cua + QTimer)
                              ▼
                       Finestra / Visor / TimelineView  (estat viu)

**Quan s'activa**: NOMÉS quan l'app s'arrenca amb el llançador MCP
(`AUTO_CHORDS_MCP.sh` o `eines/mcp_auto_chords_launcher.py`). Arrencada
normalment (`AUTO_CHORDS.sh`), l'app funciona exactament igual i aquest pont
**no existeix** (no s'importa ni s'obre cap port).

⚠️ **Qt no és thread-safe**: cap operació toca widgets ni el model des del fil
del socket. Totes passen pel **fil principal** mitjançant una cua + `QTimer`
(vegeu `PontMCP._buida_cua`), que és el patró del pont de REAPER.

Cap sortida per stdout (reservat al protocol MCP); tot el diagnòstic va al
logger de l'app (`auto_chords`) i a stderr.
"""
from __future__ import annotations

import copy
import json
import logging
import os
import queue
import secrets
import socket
import threading
import time

from PyQt5.QtCore import QObject, QTimer

from . import __version__ as APP_VERSION
from . import pipeline

logger = logging.getLogger("auto_chords")

# ── Configuració del pont ────────────────────────────────────────────────────
PONT_VERSION = "1"

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(APP_DIR)
# Fitxer d'acord (port + testimoni) que el servidor MCP llegeix per connectar-se.
# És dins `temp/` (gitignorat) i configurable per coherència amb l'app.
ENDPOINT_PATH = (os.environ.get("AUTO_CHORDS_MCP_ENDPOINT")
                 or os.path.join(PROJECT_ROOT, "temp", "mcp_bridge.json"))
# Port fix opcional; per defecte s'agafa un port lliure a l'atzar (127.0.0.1).
PORT_DEMANAT = int(os.environ.get("AUTO_CHORDS_MCP_PORT") or 0)
TIMEOUT_ESPERA = float(os.environ.get("AUTO_CHORDS_MCP_TIMEOUT") or 120.0)


class BridgeError(Exception):
    """Error controlat que s'envia al client MCP com a text (mai traça)."""


# ── Accés a l'estat viu ──────────────────────────────────────────────────────
class _Context:
    """Envolta la finestra principal i dona accés còmode al visor viu."""

    def __init__(self, window):
        self.window = window

    @property
    def visor(self):
        return getattr(self.window, "visor_ref", None)


def _requereix_visor(ctx):
    vr = ctx.visor
    if vr is None:
        raise BridgeError("No hi ha cap àudio obert al visor (obre'n un primer).")
    return vr


def _num(params, *claus, default=None, enter=False):
    for c in claus:
        if c in params and params[c] is not None and params[c] != "":
            try:
                return int(params[c]) if enter else float(params[c])
            except (TypeError, ValueError):
                raise BridgeError(f"El paràmetre «{c}» ha de ser numèric: {params[c]!r}")
    if default is not None:
        return default
    raise BridgeError(f"Falta el paràmetre «{claus[0]}».")


def _bool(params, clau, default=False):
    v = params.get(clau, default)
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "si", "sí", "yes", "on")
    return bool(v)


# ── Operacions de LECTURA ────────────────────────────────────────────────────
def _op_ping(ctx, params):
    return {"pong": True, "pont": PONT_VERSION, "app": APP_VERSION}


def _op_status(ctx, params):
    w = ctx.window
    vr = ctx.visor
    estat = {
        "pont": PONT_VERSION,
        "app": {"versio": APP_VERSION, "titol": w.windowTitle()},
        "audio": None,
        "missatge": "",
    }
    if vr is None:
        estat["missatge"] = "cap àudio obert (obre'n un per començar)"
        return estat
    a = getattr(vr, "audio", {}) or {}
    estat["audio"] = {
        "wav": os.path.basename(vr.wav_path) if getattr(vr, "wav_path", None) else None,
        "wav_path": getattr(vr, "wav_path", None),
        "durada_s": round(float(a.get("durada", 0.0)), 3),
        "sr": a.get("sr"),
        "canals": a.get("canals"),
        "csv_acords": getattr(vr, "csv_acords", None),
    }
    estat["model"] = {
        "mode": "bpm_compas" if getattr(vr, "tempo_fix", True) else "lliure",
        "bpm": float(getattr(vr, "bpm", 0.0)),
        "bpb": int(getattr(vr, "bpb", 4)),
        "offset_s": round(float(getattr(vr, "offset", 0.0)), 3),
        "n_chords": len(getattr(vr, "acords", [])),
        "n_sections": len(getattr(vr, "seccions", [])),
        "sortida": getattr(w, "sortida", "") or "",
    }
    estat["transport"] = {
        "sonant": bool(getattr(vr, "sona", False)),
        "pos_s": round(float(getattr(vr, "pos", 0.0)), 3),
        "loop": {"a": getattr(vr, "loop_a", None),
                 "b": getattr(vr, "loop_b", None),
                 "on": bool(getattr(vr, "loop_on", False))},
        "mut": bool(getattr(vr, "mut", False)),
        "metronom": bool(getattr(vr, "metro_on", False)),
    }
    return estat


def _op_list_chords(ctx, params):
    vr = _requereix_visor(ctx)
    return {"chords": [
        {"index": i, "t_s": round(float(t), 4), "acord": str(c)}
        for i, (t, c, *_r) in enumerate(vr.acords)
    ]}


def _op_list_sections(ctx, params):
    vr = _requereix_visor(ctx)
    return {"sections": [
        {"index": i, "ini_s": round(float(ini), 4), "fi_s": round(float(fi), 4),
         "durada_s": round(float(fi) - float(ini), 4),
         "lletra": str(L), "familia": str(fam)}
        for i, (ini, fi, L, fam) in enumerate(vr.seccions)
    ]}


def _op_selection(ctx, params):
    vr = _requereix_visor(ctx)
    keys = []
    tl = getattr(vr, "timeline", None)
    if tl is not None:
        try:
            keys = [[str(k), int(i)] for (k, i) in tl.selected_keys()]
        except Exception:  # noqa: BLE001 — format desconegut: no trenquem la lectura
            keys = []
    return {"seleccio": keys, "pos_s": round(float(getattr(vr, "pos", 0.0)), 3)}


def _jsonable(items):
    """Converteix tuples del model a llistes (per serialitzar)."""
    return [list(x) for x in items]


# ── Edició del model (amb undo + desat, com fa la GUI) ───────────────────────
def _refresca(vr, desa=True):
    """Sincronitza timeline, llistes i franja editor des del model del visor."""
    try:
        vr.timeline.set_data(vr.acords, vr.seccions)
    except Exception as e:  # noqa: BLE001
        logger.warning("mcp_bridge: no s'ha pogut refrescar el timeline: %s", e)
    for nom in ("_omple_llista_ac", "_actualitza_llista_abc", "_actualitza_editor"):
        try:
            getattr(vr, nom)()
        except Exception as e:  # noqa: BLE001
            logger.warning("mcp_bridge: %s ha fallat: %s", nom, e)
    if desa:
        try:
            vr._desa_i_regenera()
        except Exception as e:  # noqa: BLE001
            logger.warning("mcp_bridge: no s'ha pogut desar el CSV: %s", e)
        try:
            vr._regenera_abc_des_de_totes_les_seccions("MCP")
        except Exception as e:  # noqa: BLE001
            logger.warning("mcp_bridge: no s'ha pogut regenerar l'ABC: %s", e)


def _aplica(ctx, mut):
    """Aplica una mutació del model dins una transacció d'undo i desa.

    Si la mutació trenca la lògica temporal (v. `_valida_canvis_*`), es
    descarta sencera i es retorna un error clar (l'estat no canvia).
    """
    vr = _requereix_visor(ctx)
    abans = vr._estat_edicio()
    vr._undo_marca()
    try:
        mut(vr)
        vr._normalitza_acords()
        vr._normalitza_seccions()
    except ValueError as e:
        vr.acords, vr.seccions = copy.deepcopy(abans)
        _refresca(vr, desa=False)
        raise BridgeError(f"Canvi rebutjat (lògica temporal): {e}") from e
    _refresca(vr, desa=True)
    vr._undo_commit()
    return _op_status(ctx, {})


def _op_add_chord(ctx, params):
    t = _num(params, "t_s", "t")
    nom = str(params.get("acord") or params.get("nom") or "N").strip()
    if not nom:
        raise BridgeError("El nom de l'acord no pot ser buit.")

    def mut(vr):
        vr.acords = list(vr.acords) + [(float(t), nom, f"{float(t):.9f}")]

    return _aplica(ctx, mut)


def _op_rename_chord(ctx, params):
    idx = _num(params, "index", enter=True)
    nom = str(params.get("acord") or params.get("nom") or "").strip()
    if not nom:
        raise BridgeError("Cal un nom d'acord.")

    def mut(vr):
        if idx < 0 or idx >= len(vr.acords):
            raise BridgeError(f"Índex d'acord fora de rang: {idx}")
        nova = list(vr.acords)
        nova[idx] = (nova[idx][0], nom, nova[idx][2])
        vr.acords = nova

    return _aplica(ctx, mut)


def _op_move_chord(ctx, params):
    idx = _num(params, "index", enter=True)
    t = _num(params, "t_s", "t")

    def mut(vr):
        if idx < 0 or idx >= len(vr.acords):
            raise BridgeError(f"Índex d'acord fora de rang: {idx}")
        nova = list(vr.acords)
        nova[idx] = (float(t), nova[idx][1], f"{float(t):.9f}")
        vr.acords = nova

    return _aplica(ctx, mut)


def _op_delete_chord(ctx, params):
    idx = _num(params, "index", enter=True)

    def mut(vr):
        if idx < 0 or idx >= len(vr.acords):
            raise BridgeError(f"Índex d'acord fora de rang: {idx}")
        del vr.acords[idx]

    return _aplica(ctx, mut)


def _op_add_section(ctx, params):
    ini = _num(params, "ini_s", "ini")
    fi = _num(params, "fi_s", "fi")
    lletra = (str(params.get("lletra")).strip()
              if params.get("lletra") is not None else None)
    fam = (str(params.get("familia")).strip()
           if params.get("familia") is not None else None)

    def mut(vr):
        L = lletra or (fam or "A")
        F = fam or L
        vr.seccions = list(vr.seccions) + [(float(ini), float(fi), L, F)]

    return _aplica(ctx, mut)


def _op_rename_section(ctx, params):
    idx = _num(params, "index", enter=True)
    lletra = params.get("lletra")
    fam = params.get("familia")

    def mut(vr):
        if idx < 0 or idx >= len(vr.seccions):
            raise BridgeError(f"Índex de secció fora de rang: {idx}")
        ini, fi, L, F = vr.seccions[idx]
        nova = list(vr.seccions)
        nova[idx] = (ini, fi,
                     str(lletra).strip() if lletra is not None else L,
                     str(fam).strip() if fam is not None else F)
        vr.seccions = nova

    return _aplica(ctx, mut)


def _op_move_section(ctx, params):
    idx = _num(params, "index", enter=True)
    ini = _num(params, "ini_s", "ini")
    fi = _num(params, "fi_s", "fi")

    def mut(vr):
        if idx < 0 or idx >= len(vr.seccions):
            raise BridgeError(f"Índex de secció fora de rang: {idx}")
        _i, _f, L, F = vr.seccions[idx]
        nova = list(vr.seccions)
        nova[idx] = (float(ini), float(fi), L, F)
        vr.seccions = nova

    return _aplica(ctx, mut)


def _op_delete_section(ctx, params):
    idx = _num(params, "index", enter=True)

    def mut(vr):
        if idx < 0 or idx >= len(vr.seccions):
            raise BridgeError(f"Índex de secció fora de rang: {idx}")
        del vr.seccions[idx]

    return _aplica(ctx, mut)


# ── Transport i vista (no muten el model) ────────────────────────────────────
def _op_undo(ctx, params):
    vr = _requereix_visor(ctx)
    vr.undo()
    return _op_status(ctx, {})


def _op_redo(ctx, params):
    vr = _requereix_visor(ctx)
    vr.redo()
    return _op_status(ctx, {})


def _op_seek(ctx, params):
    vr = _requereix_visor(ctx)
    vr.ves_a(_num(params, "t_s", "t"))
    return {"pos_s": round(float(getattr(vr, "pos", 0.0)), 3)}


def _op_play(ctx, params):
    vr = _requereix_visor(ctx)
    if not getattr(vr, "sona", False):
        vr.play_stop()
    return {"sonant": bool(getattr(vr, "sona", False))}


def _op_pause(ctx, params):
    vr = _requereix_visor(ctx)
    if getattr(vr, "sona", False):
        vr.play_stop()
    return {"sonant": bool(getattr(vr, "sona", False))}


def _op_stop(ctx, params):
    vr = _requereix_visor(ctx)
    if getattr(vr, "sona", False):
        vr.play_stop()
    vr.stop_inici()
    return {"sonant": bool(getattr(vr, "sona", False)),
            "pos_s": round(float(getattr(vr, "pos", 0.0)), 3)}


def _op_mark_loop_a(ctx, params):
    vr = _requereix_visor(ctx)
    vr.marca_A()
    return {"a": getattr(vr, "loop_a", None), "b": getattr(vr, "loop_b", None)}


def _op_mark_loop_b(ctx, params):
    vr = _requereix_visor(ctx)
    vr.marca_B()
    return {"a": getattr(vr, "loop_a", None), "b": getattr(vr, "loop_b", None)}


def _op_set_loop(ctx, params):
    vr = _requereix_visor(ctx)
    vr.set_loop(_bool(params, "on", True))
    return {"loop_on": bool(getattr(vr, "loop_on", False))}


def _op_set_mut(ctx, params):
    vr = _requereix_visor(ctx)
    vr.set_mut(_bool(params, "on", True))
    return {"mut": bool(getattr(vr, "mut", False))}


def _op_zoom(ctx, params):
    vr = _requereix_visor(ctx)
    mode = str(params.get("mode") or "tot").strip().lower()
    tl = vr.timeline
    if mode in ("seleccio", "selecció", "sel"):
        tl.zoom_selection()
    elif mode in ("in", "+"):
        tl.zoom_in()
    elif mode in ("out", "-"):
        tl.zoom_out()
    else:
        tl.zoom_full()
    return {"mode": mode}


def _op_undo_list(ctx, params):
    """Retorna la pila visible d'undo/redo (noms), útil per verificar proves."""
    vr = _requereix_visor(ctx)
    return {"undo": len(getattr(vr, "_undo_stack", [])),
            "redo": len(getattr(vr, "_redo_stack", []))}


# ── Operacions de finestra (anàlisi / export / obertura) ─────────────────────
def _op_open_wav(ctx, params):
    w = ctx.window
    ruta = params.get("path") or params.get("ruta") or params.get("wav")
    if not ruta or not os.path.isfile(str(ruta)):
        raise BridgeError(f"No trobo el fitxer: {ruta!r}")
    ruta = os.path.abspath(str(ruta))
    w.wav_original = ""
    treball = w._assegura_wav(ruta)
    if treball != ruta:
        w.wav_original = ruta
    w.wav_edit.setText(treball)
    info = pipeline.wav_info(treball)
    w.sortida = w._detecta_sortida_wav(treball)
    try:
        w._actualitza_info_wav(treball, info)
    except Exception:  # noqa: BLE001
        pass
    w._carrega_visor(treball)
    return _op_status(ctx, {})


def _op_analyze(ctx, params):
    """Llança l'anàlisi amb les opcions ja desades (sense diàleg)."""
    w = ctx.window
    if not (w.wav_edit.text().strip() and os.path.isfile(w.wav_edit.text().strip())):
        raise BridgeError("Cal un àudio obert abans d'analitzar.")
    w.executa(pregunta=False)      # asíncron: arrenca la feina en un QThread
    return {"iniciat": True,
            "missatge": "anàlisi en marxa; consulta ac_status per seguir-ne l'estat"}


def _op_export_wav(ctx, params):
    """Exporta el paquet de WAV's (síncron). Pot trigar segons el tema."""
    w = ctx.window
    w.exporta()
    return {"ok": True, "sortida": getattr(w, "sortida", "") or ""}


def _op_set_tempo(ctx, params):
    w = ctx.window
    if "bpm" in params and params["bpm"] is not None:
        w.bpm.setText(str(params["bpm"]))
    if "bpb" in params and params["bpb"] is not None:
        w.bpb.setText(str(params["bpb"]))
    if ("offset_s" in params) and params["offset_s"] is not None:
        w.offset.setText(str(params["offset_s"]))
    w._aplica_parametres_temps()
    return _op_status(ctx, {})


# Registre d'operacions (nom → funció). L'MCP les exposa via `eines/..._server.py`.
OPERACIONS = {
    "ping": _op_ping,
    "status": _op_status,
    "list_chords": _op_list_chords,
    "list_sections": _op_list_sections,
    "selection": _op_selection,
    "add_chord": _op_add_chord,
    "rename_chord": _op_rename_chord,
    "move_chord": _op_move_chord,
    "delete_chord": _op_delete_chord,
    "add_section": _op_add_section,
    "rename_section": _op_rename_section,
    "move_section": _op_move_section,
    "delete_section": _op_delete_section,
    "undo": _op_undo,
    "redo": _op_redo,
    "seek": _op_seek,
    "play": _op_play,
    "pause": _op_pause,
    "stop": _op_stop,
    "mark_loop_a": _op_mark_loop_a,
    "mark_loop_b": _op_mark_loop_b,
    "set_loop": _op_set_loop,
    "set_mut": _op_set_mut,
    "zoom": _op_zoom,
    "undo_list": _op_undo_list,
    "open_wav": _op_open_wav,
    "analyze": _op_analyze,
    "export_wav": _op_export_wav,
    "set_tempo": _op_set_tempo,
}


# ── Cua de peticions cap al fil principal ────────────────────────────────────
class _Peticio:
    __slots__ = ("op", "params", "resultat", "error", "esdeveniment")

    def __init__(self, op, params):
        self.op = op
        self.params = params
        self.resultat = None
        self.error = None
        self.esdeveniment = threading.Event()


class PontMCP(QObject):
    """Servidor TCP local que executa operacions al fil de Qt."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.ctx = _Context(window)
        self._cua = queue.Queue()
        self._token = secrets.token_hex(16)
        self._srv = None
        self._fil = None
        self._actiu = False

        # Timer al fil principal: buida la cua i executa les operacions.
        self._timer = QTimer(self)
        self._timer.setInterval(15)
        self._timer.timeout.connect(self._buida_cua)

        try:
            self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._srv.bind(("127.0.0.1", PORT_DEMANAT))
            self._srv.listen(8)
            self._port = self._srv.getsockname()[1]
        except OSError as e:
            logger.error("mcp_bridge: no s'ha pogut obrir el port local: %s", e)
            if self._srv is not None:
                self._srv.close()
            self._srv = None
            return

        self._actiu = True
        self._escriu_endpoint()
        self._fil = threading.Thread(target=self._accepta, name="mcp-bridge",
                                     daemon=True)
        self._fil.start()
        self._timer.start()
        logger.info("mcp_bridge: pont actiu a 127.0.0.1:%s (port+testimoni a %s)",
                    self._port, ENDPOINT_PATH)
        print(f"[mcp_bridge] pont MCP actiu a 127.0.0.1:{self._port}", flush=True)

    # -- endpoint ----------------------------------------------------------
    def _escriu_endpoint(self):
        dades = {
            "port": self._port,
            "token": self._token,
            "pid": os.getpid(),
            "versio": PONT_VERSION,
            "app": APP_VERSION,
            "inici": time.time(),
        }
        try:
            os.makedirs(os.path.dirname(ENDPOINT_PATH), exist_ok=True)
            tmp = ENDPOINT_PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(dades, f)
            os.replace(tmp, ENDPOINT_PATH)
        except OSError as e:
            logger.error("mcp_bridge: no s'ha pogut escriure l'endpoint: %s", e)

    def _esborra_endpoint(self):
        try:
            with open(ENDPOINT_PATH, encoding="utf-8") as f:
                dades = json.load(f)
            if dades.get("pid") == os.getpid():
                os.unlink(ENDPOINT_PATH)
        except (OSError, ValueError):
            pass

    def tanca(self):
        if not self._actiu:
            return
        self._actiu = False
        try:
            self._timer.stop()
        except Exception:  # noqa: BLE001
            pass
        if self._srv is not None:
            try:
                self._srv.close()
            except OSError:
                pass
        self._esborra_endpoint()
        logger.info("mcp_bridge: pont aturat")

    # -- servidor de sockets (fil de fons) ---------------------------------
    def _accepta(self):
        while self._actiu and self._srv is not None:
            try:
                conn, _ = self._srv.accept()
            except OSError:
                break
            threading.Thread(target=self._atent, args=(conn,), daemon=True).start()

    def _atent(self, conn):
        try:
            conn.settimeout(TIMEOUT_ESPERA + 10)
            buffer = b""
            while self._actiu:
                try:
                    troç = conn.recv(65536)
                except socket.timeout:
                    break
                if not troç:
                    break
                buffer += troç
                while b"\n" in buffer:
                    linia, buffer = buffer.split(b"\n", 1)
                    if not linia.strip():
                        continue
                    resposta = self._processa_linia(linia)
                    conn.sendall((json.dumps(resposta, ensure_ascii=False) + "\n")
                                 .encode("utf-8"))
        except OSError as e:
            logger.debug("mcp_bridge: connexió tancada: %s", e)
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def _processa_linia(self, linia):
        try:
            msg = json.loads(linia.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            return {"ok": False, "error": f"json invàlid: {e}"}
        if not isinstance(msg, dict):
            return {"ok": False, "error": "esperava un objecte JSON"}
        if not secrets.compare_digest(str(msg.get("token", "")), self._token):
            return {"ok": False, "error": "testimoni invàlid"}
        op = msg.get("op")
        if op not in OPERACIONS:
            return {"ok": False, "error": f"operació desconeguda: {op!r}"}
        pet = _Peticio(op, msg.get("params") or {})
        self._cua.put(pet)
        if not pet.esdeveniment.wait(TIMEOUT_ESPERA):
            return {"ok": False, "error": "temps d'espera esgotat al fil de Qt "
                                          "(pot haver-hi un diàleg obert)"}
        if pet.error is not None:
            return {"ok": False, "error": pet.error}
        return {"ok": True, "result": pet.resultat}

    # -- executor (fil de Qt) ---------------------------------------------
    def _buida_cua(self):
        for _ in range(100):
            try:
                pet = self._cua.get_nowait()
            except queue.Empty:
                return
            try:
                pet.resultat = OPERACIONS[pet.op](self.ctx, pet.params)
            except BridgeError as e:
                pet.error = str(e)
            except Exception as e:  # noqa: BLE001
                logger.exception("mcp_bridge: error executant %s", pet.op)
                pet.error = f"{type(e).__name__}: {e}"
            finally:
                pet.esdeveniment.set()


def activa_pont(window):
    """ACTIVA el pont MCP sobre una Finestra ja creada.

    Retorna el `PontMCP` (o None si no s'ha pogut obrir el port). Guarda la
    referència a `window._mcp_pont` perquè visqui mentre visqui la finestra.
    """
    pont = PontMCP(window)
    window._mcp_pont = pont
    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(pont.tanca)
    except Exception:  # noqa: BLE001
        pass
    return pont if pont._actiu else None
