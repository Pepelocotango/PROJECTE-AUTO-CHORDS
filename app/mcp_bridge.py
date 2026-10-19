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
from . import dialegs
from . import pipeline
from . import tempo_map
from . import plataforma
from . import projecte

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
# Límit de longitud d'una línia del protocol (es comprova ABANS de processar-
# la): evita que un client maliciós o espellifat faci créixer el buffer sense
# límit. Si se supera, es respon error i es tanca la connexió.
MAX_LINIA = 1024 * 1024          # 1 MiB
# Connexions simultànies màximes (cada connexió és un fil): les de més enllà
# es rebutgen netament.
MAX_CONNEXIONS = 8


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


def _pren_avis(w):
    """Retorna el darrer avís de l'app **una vegada** i el neteja.

    Sense això, `ultim_avis` només s'escrivia i mai no s'esborrava: un agent que
    consultés `ac_status` més tard veuria un avís VELL com si fos nou (troballa
    OC-6/415: «avís persistent»). L'agent ha de llegir-lo just després de
    l'acció que l'ha produït.
    """
    txt = getattr(w, "ultim_avis", "")
    try:
        w.ultim_avis = ""
    except (AttributeError, RuntimeError):
        pass
    return txt


def _op_status(ctx, params):
    w = ctx.window
    vr = ctx.visor
    estat = {
        "pont": PONT_VERSION,
        "app": {"versio": APP_VERSION, "titol": w.windowTitle()},
        "audio": None,
        "missatge": "",
        # Darrer avís que l'app ha hagut de donar amb el pont actiu (llavors NO
        # és modal, perquè no encalli el pont): així l'agent el pot veure. Es
        # retorna UN COP i es neteja (si no, seria «persistent»; OC-6/415).
        "avis": _pren_avis(w),
        # A5: export en curs (asíncron) → l'agent sap que s'està fent feina.
        "exportant": bool(getattr(w, "exportant", False)),
        "exporta_iniciat": float(getattr(w, "exporta_iniciat", 0.0) or 0.0),
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
        {"index": i, "t_s": round(float(a[0]), 4),
         "acord": str(a.nom if isinstance(a, pipeline.Clip) else a[2][0] if isinstance(a[1], (int, float)) else a[1])}
        for i, a in enumerate(vr.acords)
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
    # Mateix sanejat que l'alta i l'export (separadors, reservats de Windows…):
    # si no, el nom del CSV i el del WAV exportat podien divergir.
    nom = pipeline.saneja_nom_acord(nom)
    if not nom:
        raise BridgeError("El nom de l'acord no és vàlid.")

    def mut(vr):
        if idx < 0 or idx >= len(vr.acords):
            raise BridgeError(f"Índex d'acord fora de rang: {idx}")
        nova = list(vr.acords)
        nova[idx] = _acord_amb_nom(nova[idx], nom)
        vr.acords = nova

    return _aplica(ctx, mut)


def _op_move_chord(ctx, params):
    idx = _num(params, "index", enter=True)
    t = _num(params, "t_s", "t")

    def mut(vr):
        if idx < 0 or idx >= len(vr.acords):
            raise BridgeError(f"Índex d'acord fora de rang: {idx}")
        nova = list(vr.acords)
        nova[idx] = _acord_amb_ini(nova[idx], t)
        vr.acords = nova

    return _aplica(ctx, mut)


def _acord_amb_ini(a, t):
    """`a` amb l'inici `t` (clips o marques; pont S4)."""
    if isinstance(a, pipeline.Clip):
        return pipeline.Clip(float(t), float(a[1]), a[2])
    return (float(t),) + tuple(a[1:])


def _acord_amb_nom(a, nom):
    """`a` amb el nom `nom` (clips o marques; pont S4)."""
    if isinstance(a, pipeline.Clip):
        return pipeline.Clip(a[0], a[1], (nom,) + tuple(a[2][1:]))
    return (a[0], nom) + tuple(a[2:])


def _durada_de(vr):
    """Durada de la WAV del visor (0.0 si no se sap)."""
    return float((getattr(vr, "audio", None) or {}).get("durada", 0.0) or 0.0)


def _op_delete_chord(ctx, params):
    idx = _num(params, "index", enter=True)

    def mut(vr):
        if idx < 0 or idx >= len(vr.acords):
            raise BridgeError(f"Índex d'acord fora de rang: {idx}")
        # Nucli únic (§6.4/#11): mateixa semàntica que la GUI del visor.
        vr.acords = pipeline.elimina_clips(
            vr.acords, idx, _durada_de(vr), pipeline.FORAT_ACORD)

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
        # `mou_seccio` manté l'INVARIANT de CONTIGÜITAT (#2): el veí anterior
        # estén el seu fi fins al nou inici i el següent mou el seu inici al
        # nou fi. Abans s'escrivia la secció tal qual → forat intern acceptat.
        if not vr.mou_seccio(idx, ini, fi):
            raise BridgeError(f"Índex de secció fora de rang: {idx}")

    return _aplica(ctx, mut)


def _op_delete_section(ctx, params):
    idx = _num(params, "index", enter=True)

    def mut(vr):
        if idx < 0 or idx >= len(vr.seccions):
            raise BridgeError(f"Índex de secció fora de rang: {idx}")
        # Nucli únic (§6.4/#11): mateixa semàntica que la GUI del visor.
        vr.seccions = pipeline.elimina_seccio(vr.seccions, idx, _durada_de(vr))

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
    # Un WAV obert per MCP NO crea projecte (encara): no heretis el projecte
    # vell → l'estat (títol/desat) ha de quedar coherent amb el WAV obert.
    w.projecte = None
    w.dirty = False
    try:
        w._actualitza_info_wav(treball, info)
    except Exception as e:  # noqa: BLE001
        logger.warning("mcp_bridge: no s'ha pogut actualitzar la info del WAV: %s", e)
    w._carrega_visor(treball)
    w._actualitza_titol()
    return _op_status(ctx, {})


def _valida_opcions(noves):
    """Valida les opcions d'anàlisi que arriben per l'MCP (A6).

    Rebutja seccions o claus que no existeixin: si no, una errada d'escriptura
    s'ignoraria en silenci i l'agent creuria que ha canviat alguna cosa.
    """
    if not isinstance(noves, dict):
        raise BridgeError("`opcions` ha de ser un diccionari "
                          "(seccions: chords, bpm, structure, clean).")
    for seccio, valors in noves.items():
        if seccio not in dialegs.DEFECTES:
            raise BridgeError(
                f"Secció d'opcions desconeguda: {seccio!r} "
                f"(vàlides: {', '.join(sorted(dialegs.DEFECTES))}).")
        if not isinstance(valors, dict):
            raise BridgeError(f"`opcions[{seccio}]` ha de ser un diccionari.")
        desconegudes = [k for k in valors if k not in dialegs.DEFECTES[seccio]]
        if desconegudes:
            raise BridgeError(
                f"Claus desconegudes a `opcions[{seccio}]`: "
                f"{', '.join(sorted(desconegudes))} (vàlides: "
                f"{', '.join(sorted(dialegs.DEFECTES[seccio]))}).")
    return True


def _fusiona_opcions(base, noves):
    """Fusiona opcions per SECCIONS: només canvia el que s'hi passa."""
    res = copy.deepcopy(base) if isinstance(base, dict) else {}
    for seccio, valors in (noves or {}).items():
        if isinstance(valors, dict) and isinstance(res.get(seccio), dict):
            res[seccio] = {**res[seccio], **valors}
        else:
            res[seccio] = copy.deepcopy(valors)
    return res


def _op_get_options(ctx, params):
    """Retorna les opcions d'anàlisi ACTUALS i els valors per defecte (A6)."""
    w = ctx.window
    return {"opcions": copy.deepcopy(getattr(w, "opcions", {})),
            "defectes": copy.deepcopy(dialegs.DEFECTES)}


def _op_analyze(ctx, params):
    """Llança l'anàlisi amb les opcions JA desades (sense diàleg).

    `opcions` (opcional): diccionari per canviar-ne seccions o claus concretes
    per a AQUESTA anàlisi (p. ex. `{"chords": {"s": 0.5}}`); amb `desa: true`
    també queden guardades com les opcions de l'app (com si l'usuari hagués
    acceptat el diàleg). Sense `opcions`, es comporta com abans.
    """
    w = ctx.window
    if not (w.wav_edit.text().strip() and os.path.isfile(w.wav_edit.text().strip())):
        raise BridgeError("Cal un àudio obert abans d'analitzar.")
    noves = params.get("opcions")
    if noves is not None:
        _valida_opcions(noves)
        w.opcions = _fusiona_opcions(getattr(w, "opcions", {}), noves)
        if params.get("desa"):
            try:
                dialegs.desa_opcions(w.opcions)
            except Exception as e:  # noqa: BLE001
                logger.warning("mcp_bridge: no s'han pogut desar les opcions: %s", e)
    w.executa(pregunta=False)      # asíncron: arrenca la feina en un QThread
    return {"iniciat": True,
            "opcions": copy.deepcopy(getattr(w, "opcions", {})),
            "missatge": "anàlisi en marxa; consulta ac_status per seguir-ne l'estat"}


def _op_export_wav(ctx, params):
    """Exporta el paquet de WAV's. Pot trigar segons el tema.

    `async: true` (A5) → arrenca l'export en un FIL i retorna de seguida; el
    progrés es consulta a `ac_status` (`exportant`). Per defecte és síncrona.

    ⚠️ L'export pot voler avisar l'usuari: amb el pont actiu aquests avisos són
    NO modals (un modal encallaria el pont) i el text es retorna aquí.
    """
    w = ctx.window
    if params.get("async"):
        if not w.exporta_async():
            raise BridgeError("No s'ha pogut arrencar l'exportació "
                              "(cal una WAV i els CSVs: fes 'Analitza' primer).")
        return {"ok": True, "iniciat": True,
                "sortida": getattr(w, "sortida", "") or "",
                "missatge": "exportació en marxa; consulta ac_status "
                            "(camp «exportant») per seguir-la"}
    w.ultim_avis = ""                 # per retornar NOMÉS l'avís d'aquest export
    # `partitura` (opcional): força que s'hi inclogui (o no) en AQUESTA
    # exportació, sense canviar la marca de l'app (es restaura sempre).
    marca = None
    if params.get("partitura") is not None:
        marca = w.amb_part.isChecked()
        w.amb_part.setChecked(bool(params["partitura"]))
    try:
        w.exporta()
    finally:
        if marca is not None:
            w.amb_part.setChecked(marca)
    # Si l'export ha fallat, `ok` ha de ser FALSE (abans deia `true` sempre,
    # també quan fallava: l'agent creia que s'havia exportat).
    err = getattr(w, "exporta_error", "")
    r = {"ok": not err, "sortida": getattr(w, "sortida", "") or ""}
    if err:
        r["error"] = err
    if getattr(w, "ultim_avis", ""):
        r["avis"] = _pren_avis(w)
    return r


def _op_export_partitura(ctx, params):
    """Genera la PARTITURA (MusicXML sempre; PDF/MSCZ si hi ha MuseScore).

    Treballa sobre la carpeta de sortida actual i **no obre cap finestra ni
    carpeta**: retorna els camins generats. Cal haver exportat abans (hi ha
    d'haver `acords_locators.txt`).
    """
    w = ctx.window
    if not getattr(w, "sortida", ""):
        raise BridgeError("Cal exportar primer: no hi ha carpeta de resultats.")
    res = w._exporta_partitura()
    if not res or res.get("error"):
        detall = ((res or {}).get("error")
                  or "cal haver exportat abans, en mode BPM · compàs")
        raise BridgeError(f"No s'ha pogut generar la partitura: {detall}")
    return {"ok": True,
            "musicxml": res.get("musicxml"),
            "pdf": res.get("pdf"),
            "mscz": res.get("mscz"),
            "missatge": w._missatge_partitura(res)}


# ── A7: accions de l'app que faltaven al pont ────────────────────────────────
def _op_set_metro(ctx, params):
    """Activa/desactiva el metrònom (sincronitza botó, acció de menú i visor)."""
    on = bool(params.get("on"))
    ctx.window._toggle_metro(on)
    return {"metronom": bool(getattr(ctx.visor, "metro_on", False))}


def _op_set_key_detect(ctx, params):
    """Activa/desactiva la detecció de tonalitat (qm-keydetector) de la partitura."""
    on = bool(params.get("on"))
    ctx.window.tonalitat_auto.setChecked(on)
    return {"tonalitat_automatica": on}


def _op_detect_downbeat(ctx, params):
    """Detecta automàticament el compàs 1 (downbeat) de la cançó."""
    ctx.window._detecta_compas1()
    return _op_status(ctx, {})


def _op_mark_downbeat(ctx, params):
    """Marca el compàs 1 al cursor."""
    ctx.window._marca_compas_1()
    return _op_status(ctx, {})


def _op_open_output_folder(ctx, params):
    """Obre la carpeta de sortida amb el gestor de fitxers del sistema."""
    ctx.window.obre_carpeta()
    return {"ok": True, "sortida": getattr(ctx.window, "sortida", "") or ""}


def _op_select_clip(ctx, params):
    """Selecciona un clip (`kind`: chord|section, `index`); substitueix la selecció."""
    vr = _requereix_visor(ctx)
    kind = str(params.get("kind") or params.get("tipus") or "chord").lower()
    if kind not in ("chord", "section"):
        raise BridgeError("kind ha de ser 'chord' o 'section'.")
    idx = int(_num(params, "index", enter=True))
    vr.timeline.select_clip(kind, idx)
    return _op_selection(ctx, {})


def _op_toggle_selection(ctx, params):
    """Afegeix/treu un clip de la selecció múltiple (com Ctrl+clic)."""
    vr = _requereix_visor(ctx)
    kind = str(params.get("kind") or params.get("tipus") or "chord").lower()
    if kind not in ("chord", "section"):
        raise BridgeError("kind ha de ser 'chord' o 'section'.")
    idx = int(_num(params, "index", enter=True))
    vr.timeline.toggle_selection(kind, idx)
    return _op_selection(ctx, {})


def _op_clear_selection(ctx, params):
    """Buida la selecció de clips."""
    vr = _requereix_visor(ctx)
    vr.timeline.clear_selection()
    return _op_selection(ctx, {})


def _op_select_at_cursor(ctx, params):
    """Selecciona el clip que CONTÉ el cursor (`kind`: chord|section|tempo)."""
    _requereix_visor(ctx)          # cal un visor carregat (a qui seleccionar)
    kind = str(params.get("kind") or params.get("tipus") or "chord").lower()
    if kind == "section":
        ctx.window._sel_seccio_cursor()
    elif kind == "chord":
        ctx.window._sel_acord_cursor()
    elif kind in ("tempo", "bpm", "compas"):
        ctx.window._sel_tram_cursor()
    else:
        raise BridgeError("kind ha de ser 'chord', 'section' o 'tempo'.")
    return _op_selection(ctx, {})


def _aplica_tempo(ctx, mut):
    """Mutació del MAPA de BPM/compàs, dins una transacció de desfer i desada.

    El mapa ha de quedar sempre vàlid (`normalitza_trams`: contigu i cobrint
    `[0, durada]`); si la mutació el deixa buit o el trenca, es descarta tota i
    es retorna un error clar sense tocar res.
    """
    vr = _requereix_visor(ctx)
    abans = copy.deepcopy(list(vr.tempo_trams or []))
    vr._undo_marca()
    try:
        mut(vr)
        nous = tempo_map.normalitza_trams(list(vr.tempo_trams or []),
                                          vr._durada_wav())
        if not nous:
            raise BridgeError("El mapa de tempo/compàs no pot quedar buit.")
        vr.aplica_tempo_trams(nous)
    except BridgeError:
        vr.tempo_trams = abans
        vr._refresca_tempo_map()
        raise
    except ValueError as e:
        vr.tempo_trams = abans
        vr._refresca_tempo_map()
        raise BridgeError(f"Canvi rebutjat (mapa de tempo/compàs): {e}") from e
    vr._undo_commit()
    return _op_status(ctx, {})


def _op_detecta_tempo_mapa(ctx, params):
    """Infereix el mapa de BPM/compàs a partir dels temps (beats) de l'àudio.

    Pot trigar (fa córrer la detecció de beats sobre el WAV). No obre diàlegs.
    """
    _requereix_visor(ctx)
    try:
        n = ctx.window.detecta_tempo_mapa(avis=False)
    except Exception as e:  # noqa: BLE001
        raise BridgeError(f"No s'ha pogut detectar el mapa de tempo: {e}") from e
    return {"trams_inferits": int(n or 0), "estat": _op_status(ctx, {})}


def _op_set_tram_tempo(ctx, params):
    """Fixa el **BPM i/o el compàs** del tram `index` del mapa (mateix efecte
    que el diàleg «Reanomena (BPM/compàs)…» de la GUI).

    Els paràmetres que no s'indiquen conserven el valor del tram. Si el tram és
    el 0, el valor nou passa també al transport (`bpm`/`bpb`), que és el que
    mana com a valor inicial (igual que fa la GUI).
    """
    idx = _num(params, "index", "idx", enter=True)

    def mut(vr):
        trams = list(vr.tempo_trams or [])
        if not 0 <= idx < len(trams):
            raise BridgeError(f"Índex de tram fora de rang: {idx}")
        t = trams[idx]
        bpm = params.get("bpm")
        num = params.get("bpb", params.get("num"))
        den = params.get("beat_type", params.get("den"))
        bpm = float(t[2]) if bpm is None else float(bpm)
        num = int(t[3]) if num is None else int(num)
        den = int(t[4]) if den is None else int(den)
        if bpm <= 0:
            raise BridgeError("El BPM ha de ser més gran que 0.")
        if num <= 0 or den <= 0:
            raise BridgeError("El compàs ha de ser positiu (p. ex. 4/4).")
        nou = list(trams)
        nou[idx] = (float(t[0]), float(t[1]), bpm, num, den)
        vr.tempo_trams = nou

    return _aplica_tempo(ctx, mut)


def _op_list_tempo(ctx, params):
    """Llista els TRAMS del mapa de tempo/compàs (índex, inici, fi, BPM, compàs)."""
    vr = _requereix_visor(ctx)
    return {
        "mode": "bpm_compas" if getattr(vr, "tempo_fix", True) else "lliure",
        "trams": [
            {"index": i, "ini_s": round(float(t[0]), 4),
             "fi_s": round(float(t[1]), 4), "bpm": round(float(t[2]), 4),
             "bpb": int(t[3]), "beat_type": int(t[4])}
            for i, t in enumerate(vr.tempo_trams or [])
        ],
    }


def _op_afegeix_tall(ctx, params):
    """Obre una frontera nova al mapa (un canvi de BPM/compàs) al temps `t_s`."""
    t = _num(params, "t_s", "t")

    def mut(vr):
        vr.tempo_trams = tempo_map.afegeix_tall(
            list(vr.tempo_trams or []), float(t))

    return _aplica_tempo(ctx, mut)


def _op_elimina_tall(ctx, params):
    """Elimina el tram `index` del mapa (el veí n'ocupa l'espai)."""
    idx = _num(params, "index", "idx", enter=True)

    def mut(vr):
        trams = list(vr.tempo_trams or [])
        if len(trams) <= 1:
            raise BridgeError(
                "El mapa de tempo/compàs ha de tenir com a mínim 1 tram.")
        if not 0 <= idx < len(trams):
            raise BridgeError(f"Índex de tram fora de rang: {idx}")
        vr.tempo_trams = tempo_map.elimina_tall(trams, idx)

    return _aplica_tempo(ctx, mut)


def _op_mou_tall(ctx, params):
    """Mou la frontera del tram `index` a `t_s` (`vora`: ini|fi, per defecte ini)."""
    idx = _num(params, "index", "idx", enter=True)
    t = _num(params, "t_s", "t")
    vora = str(params.get("vora") or params.get("costa") or "ini").lower()

    def mut(vr):
        trams = list(vr.tempo_trams or [])
        if not 0 <= idx < len(trams):
            raise BridgeError(f"Índex de tram fora de rang: {idx}")
        vr._on_tempo_mogut(idx, "fi" if vora.startswith("f") else "ini",
                           float(t))

    return _aplica_tempo(ctx, mut)


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


# ── Projectes autocontinguts (`.acproj`) ─────────────────────────────────────
def _projecte_actual(w):
    """Retorna el projecte obert o un error clar (mai un diàleg)."""
    p = getattr(w, "projecte", None)
    if p is None:
        raise BridgeError(
            "No hi ha cap projecte obert: obre'n un (`obre_projecte`) o desa'n "
            "un primer des de la GUI.")
    return p


def _op_obre_projecte(ctx, params):
    """Obre un projecte `.acproj` (o la seva carpeta) per ruta."""
    w = ctx.window
    ruta = params.get("path") or params.get("ruta") or params.get("acproj")
    if not ruta:
        raise BridgeError("Cal indicar la ruta del projecte (paràmetre «path»).")
    ruta = os.path.abspath(str(ruta))
    if not os.path.exists(ruta):
        raise BridgeError(f"No trobo el projecte: {ruta!r}")
    try:
        p = projecte.Projecte.obre(ruta)
    except projecte.ProjecteError as e:
        raise BridgeError(f"No s'ha pogut obrir el projecte: {e}") from e
    if not p.audio_present():
        raise BridgeError(f"Falta l'àudio del projecte: {p.ruta_audio()}")
    w._activa_projecte(p)
    return _op_status(ctx, {})


def _op_crea_projecte(ctx, params):
    """Crea un projecte AUTOCONTINGUT a partir d'un WAV (el paràmetre o l'obert).

    És l'equivalent MCP de «Crea el projecte» de la GUI (`_obri_des_de_wav`):
    copia l'àudio a `audio/`, migra els CSVs d'una `AUTOCHORDS_<nom>/` vella si
    n'hi ha, i escriu el `.acproj`.
    """
    w = ctx.window
    desti = params.get("path") or params.get("carpeta") or params.get("desti")
    if not desti:
        raise BridgeError(
            "Cal indicar la carpeta on crear el projecte (paràmetre «path»).")
    desti = os.path.abspath(str(desti))
    wav = params.get("wav") or params.get("audio")
    if not wav:
        ed = getattr(w, "wav_edit", None)
        wav = ed.text().strip() if (ed is not None and hasattr(ed, "text")) else ""
    if not wav or not os.path.isfile(str(wav)):
        raise BridgeError(
            f"No trobo l'àudio per al projecte: {wav!r} (obre'n un amb "
            "`open_wav` o passa «wav»).")
    wav = os.path.abspath(str(wav))

    def _val(nom, defecte):
        f = getattr(w, nom, None)
        try:
            return f() if callable(f) else defecte
        except Exception:  # noqa: BLE001
            return defecte

    fix = False
    tf = getattr(w, "tempo_fix", None)
    if tf is not None and hasattr(tf, "isChecked"):
        fix = bool(tf.isChecked())
    compas = ""
    bp = getattr(w, "bpb", None)
    if bp is not None and hasattr(bp, "text"):
        compas = bp.text().strip()
    # Migració: si hi ha una AUTOCHORDS_<nom>/ vella al costat del WAV.
    antic = projecte.carpeta_autochords(wav)
    ca = os.path.join(antic, projecte.NOM_CSV_ACORDS) if antic else None
    sa = os.path.join(antic, projecte.NOM_CSV_ESTRUCTURA) if antic else None
    in_situ = bool(antic) and desti == os.path.abspath(antic)
    try:
        p = projecte.Projecte.crea(
            desti, wav, nom=os.path.basename(desti),
            bpm=_val("_bpm_val", 120.0), bpb=_val("_bpb_val", 4),
            offset=_val("_offset_val", 0.0), fix=fix,
            opcions=getattr(w, "opcions", None), compas=compas,
            csv_acords=ca if ca and os.path.isfile(ca) else None,
            csv_estructura=sa if sa and os.path.isfile(sa) else None,
            permet_existent=in_situ)
    except (projecte.ProjecteError, OSError) as e:
        raise BridgeError(f"No s'ha pogut crear el projecte: {e}") from e
    w._activa_projecte(p)
    return _op_status(ctx, {})


def _op_desa_projecte(ctx, params):
    """Desa el projecte obert al seu lloc."""
    w = ctx.window
    p = _projecte_actual(w)
    w._refresca_dades_projecte()
    try:
        p.desa()
    except OSError as e:
        raise BridgeError(f"No s'ha pogut desar el projecte: {e}") from e
    w.dirty = False
    w._actualitza_titol()
    w._afegeix_recent(p.ruta_acproj)
    return _op_status(ctx, {})


def _op_desa_com(ctx, params):
    """Desa una CÒPIA del projecte a una carpeta nova (ruta obligatòria)."""
    w = ctx.window
    p = _projecte_actual(w)
    desti = params.get("path") or params.get("carpeta") or params.get("desti")
    if not desti:
        raise BridgeError("Cal indicar la carpeta de destí (paràmetre «path»).")
    desti = os.path.abspath(str(desti))
    if desti == os.path.abspath(p.carpeta):
        return _op_desa_projecte(ctx, {})   # mateix lloc → «Desa» normal
    w._refresca_dades_projecte()
    try:
        p.desa()
        nou = p.duplica(desti)
    except (projecte.ProjecteError, OSError) as e:
        raise BridgeError(f"No s'ha pogut desar com: {e}") from e
    w.projecte = nou
    w.sortida = nou.carpeta
    w.dirty = False
    w._actualitza_titol()
    w._afegeix_recent(nou.ruta_acproj)
    return _op_status(ctx, {})


def _op_fes_backup(ctx, params):
    """Fa una còpia versionada del projecte (`backup/<data-hora>/`)."""
    w = ctx.window
    p = _projecte_actual(w)
    w._refresca_dades_projecte()
    try:
        dest = p.fes_backup()
    except (projecte.ProjecteError, OSError) as e:
        raise BridgeError(f"No s'ha pogut fer la còpia: {e}") from e
    try:
        copies = [str(b) for b in p.backups()]
    except Exception:  # noqa: BLE001
        copies = []
    return {"ok": True, "backup": (str(dest) if dest else None),
            "canviat": dest is not None, "backups": copies}


def _op_recents(ctx, params):
    """Llista els projectes recents que encara existeixen."""
    w = ctx.window
    recents = [r for r in (getattr(w, "recents", None) or [])
               if os.path.isfile(r)]
    return {"recents": recents}


# ── Paritat d'edició #11: partir / fusionar (acords i seccions) ──────────────
def _op_parteix_acord(ctx, params):
    """Parteix l'acord `index` pel temps `t_s` (nom opcional per a la part nova)."""
    vr = _requereix_visor(ctx)
    idx = _num(params, "index", enter=True)
    t = _num(params, "t_s", "t")          # float: admet fraccions de segon
    nom = params.get("nom") or params.get("acord")
    nou = vr.parteix_acord(idx, float(t), nom)
    if nou is False:
        raise BridgeError(
            f"No s'ha pogut partir l'acord {idx} a {t}s (l'índex ha d'existir, "
            "no ser l'últim i el temps ha de caure a dins).")
    try:
        vr._desa_i_regenera()
    except Exception as e:  # noqa: BLE001
        raise BridgeError(f"Acord partit, però no s'ha pogut desar: {e}") from e
    return _op_status(ctx, {})


def _op_fusiona_acord(ctx, params):
    """Fusiona l'acord `index` amb el veí (`amb`: seguent | anterior)."""
    vr = _requereix_visor(ctx)
    idx = _num(params, "index", enter=True)
    amb = params.get("amb") or "seguent"
    if amb not in ("seguent", "anterior"):
        raise BridgeError("«amb» ha de ser 'seguent' o 'anterior'.")
    if not vr.fusiona_acord(idx, amb=amb):
        raise BridgeError(f"No s'ha pogut fusionar l'acord {idx} amb el {amb}.")
    return _op_status(ctx, {})


def _op_parteix_seccio(ctx, params):
    """Parteix la secció `index` pel temps `t_s` (lletra/família opcionals)."""
    vr = _requereix_visor(ctx)
    idx = _num(params, "index", enter=True)
    t = _num(params, "t_s", "t")          # float: admet fraccions de segon
    lletra = params.get("lletra") or params.get("nom")
    fam = params.get("familia") or params.get("fam")
    nou = vr.parteix_seccio(idx, float(t), lletra, fam)
    if nou is False:
        raise BridgeError(
            f"No s'ha pogut partir la secció {idx} a {t}s (l'índex ha d'existir, "
            "no ser l'última i el temps ha de caure a dins).")
    try:
        vr._regenera_abc_des_de_totes_les_seccions(
            f"secció {idx} partida a {float(t):.2f}s")
    except Exception as e:  # noqa: BLE001
        raise BridgeError(f"Secció partida, però no s'ha pogut regenerar: {e}") from e
    return _op_status(ctx, {})


def _op_fusiona_seccio(ctx, params):
    """Fusiona la secció `index` amb el veí (`amb`: seguent | anterior)."""
    vr = _requereix_visor(ctx)
    idx = _num(params, "index", enter=True)
    amb = params.get("amb") or "seguent"
    if amb not in ("seguent", "anterior"):
        raise BridgeError("«amb» ha de ser 'seguent' o 'anterior'.")
    if not vr.fusiona_seccio(idx, amb=amb):
        raise BridgeError(f"No s'ha pogut fusionar la secció {idx} amb el {amb}.")
    return _op_status(ctx, {})


def _op_regularitza(ctx, params):
    """Mode fàcil: re-regularitza els acords de l'anàlisi CRUA a la graella."""
    vr = _requereix_visor(ctx)
    nivell = params.get("nivell") or params.get("ritme") or "auto"
    if nivell not in ("auto", "compas", "mig", "temps"):
        raise BridgeError(
            "«nivell» ha de ser 'auto', 'compas', 'mig' o 'temps'.")
    modul = int(_num(params, "modul_compassos", "modul", default=0, enter=True))
    if modul < 0:
        raise BridgeError("«modul_compassos» no pot ser negatiu.")
    try:
        n = vr.regularitza_des_de_cru(nivell, modul_compassos=modul)
    except Exception as e:  # noqa: BLE001
        raise BridgeError(f"No s'ha pogut regularitzar: {e}") from e
    if not n:
        raise BridgeError(
            "No hi ha res a regularitzar (cal un tema amb acords; si vols la "
            "capa crua, una anàlisi prèvia del tema).")
    return _op_status(ctx, {})


# ── Paritat d'ACCIONS amb la GUI (2026-10-17) ────────────────────────────────
# Totes les accions d'EDICIÓ/de vista que l'usuari té a la GUI i que encara no
# tenien eina `ac_*`. Cap obre diàlegs: reben els paràmetres (noms, temps) o fan
# servir l'estat vigent (selecció, cursor, porta-retalls intern). Les edicions
# passen per les MATEIXES transaccions d'undo/desat que la GUI.
def _kind_opt(params):
    """`kind` opcional del paràmetre → 'chord' | 'section' | None."""
    k = str(params.get("kind") or params.get("tipus") or "").strip().lower()
    if k in ("chord", "acord", "acords"):
        return "chord"
    if k in ("section", "seccio", "secció", "seccions", "estructura"):
        return "section"
    if k:
        raise BridgeError("«kind» ha de ser 'chord' o 'section'.")
    return None


def _sel_teclat(vr, kind=None):
    """Clips del timeline actualment seleccionats (filtrats per `kind`)."""
    keys = set(vr.timeline.selected_keys())
    if kind:
        keys = {k for k in keys if k[0] == kind}
    return keys


def _op_copia_seleccio(ctx, params):
    """Copia la selecció al porta-retalls INTERN (Ctrl+C)."""
    vr = _requereix_visor(ctx)
    keys = _sel_teclat(vr)
    if not keys:
        raise BridgeError("No hi ha cap clip seleccionat per copiar.")
    vr.timeline.copy_selection()
    return {"ok": True, "copiats": len(keys),
            "porta_retalls": bool(vr.timeline.has_clipboard())}


def _op_retalla_seleccio(ctx, params):
    """Retalla la selecció (Ctrl+X): la copia al porta-retalls i l'esborra."""
    vr = _requereix_visor(ctx)
    keys = _sel_teclat(vr)
    if not keys:
        raise BridgeError("No hi ha cap clip seleccionat per retallar.")
    vr.timeline.cut_selection()
    return _op_status(ctx, {})


def _op_enganxa_seleccio(ctx, params):
    """Enganxa el porta-retalls intern al cursor (Ctrl+V).

    `t_s` (opcional) mou el cursor abans d'enganxar; sense paràmetre, enganxa
    on hi ha el cursor. L'enganxat **sobreescriu** el tram (regla d'or #4).
    """
    vr = _requereix_visor(ctx)
    if not vr.timeline.has_clipboard():
        raise BridgeError(
            "El porta-retalls intern és buit (cal copiar o retallar abans).")
    if params.get("t_s") is not None:
        vr.timeline.set_position(float(_num(params, "t_s", "t")))
    vr.timeline.paste_at_cursor()
    return _op_status(ctx, {})


def _op_esborra_seleccio(ctx, params):
    """Elimina els clips seleccionats al timeline (tecla Del)."""
    vr = _requereix_visor(ctx)
    keys = _sel_teclat(vr, _kind_opt(params))
    if not keys:
        raise BridgeError("No hi ha cap clip seleccionat per esborrar.")
    vr._elimina_seleccio(sorted(keys))
    return _op_status(ctx, {})


def _op_duplica_seleccio(ctx, params):
    """Duplica els clips seleccionats (Ctrl+D)."""
    vr = _requereix_visor(ctx)
    keys = _sel_teclat(vr, _kind_opt(params))
    if not keys:
        raise BridgeError("No hi ha cap clip seleccionat per duplicar.")
    vr._duplica_seleccio(sorted(keys))
    return _op_status(ctx, {})


def _op_renomena_seleccio(ctx, params):
    """Reanomena de cop tots els clips seleccionats del mateix tipus (F2 en bloc).

    «kind» és opcional si la selecció és d'un sol tipus; «nom» és obligatori.
    """
    vr = _requereix_visor(ctx)
    nom = str(params.get("nom") or params.get("acord")
              or params.get("lletra") or "").strip()
    if not nom:
        raise BridgeError("Cal el nom nou («nom»).")
    kind = _kind_opt(params)
    if kind is None:
        tipus = {k for k, _i in vr.timeline.selected_keys() if k}
        if len(tipus) != 1:
            raise BridgeError(
                "Amb selecció mixta cal dir «kind» (chord|section).")
        kind = tipus.pop()
    idxs = sorted(i for _k, i in _sel_teclat(vr, kind))
    if not idxs:
        raise BridgeError(f"No hi ha cap clip de tipus «{kind}» seleccionat.")
    ok = (vr._renomena_acords(idxs, nom) if kind == "chord"
          else vr._renomena_seccions(idxs, nom))
    if not ok:
        raise BridgeError(f"No s'han pogut reanomenar els «{kind}» seleccionats.")
    return _op_status(ctx, {})


def _op_selecciona_rang(ctx, params):
    """Selecciona els clips l'inici dels quals cau dins `[t0, t1]` (rang de Shift+clic).

    Sense «kind» s'agafen les dues pistes (com el marquee); amb «kind», només
    la demanada.
    """
    vr = _requereix_visor(ctx)
    t0 = _num(params, "t0", "ini", "des")
    t1 = _num(params, "t1", "fi", "fins")
    kind = _kind_opt(params)
    keys = vr.timeline.keys_dins_rang(float(t0), float(t1), inclou_fi=True)
    if kind:
        keys = {k for k in keys if k[0] == kind}
    vr.timeline.select_multi(keys)
    return _op_selection(ctx, {})


def _op_selecciona_loop(ctx, params):
    """Selecciona tot el que hi ha dins el loop A/B (deixa el cursor al final)."""
    vr = _requereix_visor(ctx)
    n = vr.selecciona_bloc_del_loop()
    if not n:
        raise BridgeError("No hi ha cap loop A/B amb clips a dins.")
    return _op_selection(ctx, {})


def _op_duplica_a(ctx, params):
    """Duplica el bloc seleccionat a un DESTÍ (`t_s`), sobreescrivint-lo (§6.3).

    És l'equivalent MCP del gest **`Ctrl+Shift`+arrossegar**: l'original es
    queda i la **còpia va al destí**, que es talla/elimina segons §6.3. `kind`
    (chord|section) limita la duplicació a una pista.
    """
    t = _num(params, "t_s", "t")
    kind = str(params.get("kind") or "").strip().lower()

    def mut(vr):
        durada = _durada_de(vr)
        kinds = ([kind] if kind in ("chord", "section")
                 else ["chord", "section"])
        tocat = False
        for k in kinds:
            magatzem = "acords" if k == "chord" else "seccions"
            base = list(getattr(vr, magatzem))
            idxs = sorted(i for kk, i in vr.timeline.selected_keys()
                          if kk == k)
            if not idxs:
                continue
            first, last = idxs[0], idxs[-1]
            if not (0 <= first <= last < len(base)):
                continue
            if k == "chord":
                nou = pipeline.duplica_bloc_clips(
                    base, first, last, float(t), durada,
                    pipeline.FORAT_ACORD)
            else:
                nou = pipeline.duplica_bloc_seccions(
                    base, first, last, float(t), durada)
            if nou != base:
                setattr(vr, magatzem, nou)
                tocat = True
        if not tocat:
            raise BridgeError("No hi ha res a duplicar (cal una selecció i "
                              "espai al destí).")

    return _aplica(ctx, mut)


def _op_nudge(ctx, params):
    """Nudge d'una frontera del clip seleccionat (←/→; `estira` = Alt+←/→)."""
    vr = _requereix_visor(ctx)
    kind, idx = vr.timeline._sel
    if not kind or idx < 0:
        raise BridgeError("Cal tenir un clip seleccionat per fer nudge.")
    d = params.get("direccio", params.get("dir", "dreta"))
    if isinstance(d, str):
        d = -1 if d.strip().lower() in (
            "esquerra", "prev", "anterior", "-1", "-") else 1
    direccio = -1 if float(d) < 0 else 1
    estira = _bool(params, "estira", False)
    pas = params.get("pas")
    pas = (float(pas) if pas not in (None, "") else vr.timeline._pas_nudge())
    if pas <= 0:
        raise BridgeError("«pas» ha de ser positiu (segons).")
    vr.timeline._nudge(direccio, estira, pas)
    return _op_status(ctx, {})


def _op_mou_bloc(ctx, params):
    """Mou un BLOC preservant-ne la durada (DESTÍ del moviment, §6.3).

    Val per a **acords** i **seccions** (paritat d'edició #11). El bloc és
    `[first..last]` o, si no es donen, la **selecció contigua** del tipus.
    `dt_s` és el desplaçament (pot ser negatiu); al destí, el que queda a sota
    es talla o s'elimina («mana l'últim editat») i l'origen el tanca el veí
    (els forats d'estructura → «-», §6.1).
    """
    vr = _requereix_visor(ctx)
    kind = _kind_opt(params) or "chord"
    magatzem = "acords" if kind == "chord" else "seccions"
    dt = _num(params, "dt_s", "dt", "delta")
    if params.get("first") is not None and params.get("last") is not None:
        first = int(_num(params, "first", enter=True))
        last = int(_num(params, "last", enter=True))
    else:
        idxs = sorted(i for k, i in vr.timeline.selected_keys() if k == kind)
        if not idxs:
            raise BridgeError("Cal «first»/«last» o bé una selecció contigua.")
        first, last = idxs[0], idxs[-1]
        if idxs != list(range(first, last + 1)):
            raise BridgeError("La selecció ha de ser un bloc CONTIGU.")

    def mut(vr2):
        base = list(getattr(vr2, magatzem))
        if not (0 <= first <= last < len(base)):
            raise BridgeError(f"Bloc fora de rang: {first}-{last}.")
        durada = float((getattr(vr2, "audio", {}) or {}).get("durada", 0.0) or 0.0)
        if kind == "chord":
            setattr(vr2, magatzem, pipeline.mou_bloc_clips(
                base, first, last, float(dt), durada, pipeline.FORAT_ACORD))
        else:
            setattr(vr2, magatzem, pipeline.mou_bloc_seccions(
                base, first, last, float(dt), durada))

    return _aplica(ctx, mut)


def _op_troba_i_reemplaca(ctx, params):
    """Troba i reemplaça xifrats (acords) o etiquetes (estructura) a tot el tema."""
    vr = _requereix_visor(ctx)
    camp = str(params.get("camp") or params.get("on") or "acords").strip().lower()
    if camp in ("estructura", "section", "seccio", "secció", "seccions"):
        camp = "estructura"
    else:
        camp = "acords"
    troba = str(params.get("troba") or params.get("cerca") or "").strip()
    reemplaca = str(params.get("reemplaca") or params.get("nous") or "").strip()
    if not troba or not reemplaca:
        raise BridgeError("Calen «troba» i «reemplaca» (no buits).")
    n = vr.troba_i_reemplaca(camp, troba, reemplaca)
    return {"ok": bool(n), "substituits": int(n or 0), "camp": camp,
            **_op_status(ctx, {})}


def _op_reverteix(ctx, params):
    """Torna el projecte a l'últim estat desat (Reverteix, sense cap diàleg)."""
    ctx.window._reverteix()
    return _op_status(ctx, {})


def _op_neteja_loop(ctx, params):
    """Desactiva i esborra el loop A/B («Neteja el loop»)."""
    ctx.window._neteja_loop()
    return _op_status(ctx, {})


def _op_set_eina(ctx, params):
    """Tria l'eina del timeline: `intel·ligent` (per defecte) o `marc`."""
    mode = str(params.get("mode") or params.get("eina") or "").strip().lower()
    if mode in ("marc", "seleccio", "selecció", "rubber", "rubber-band",
                "marquee"):
        marc = True
    elif mode in ("intel·ligent", "inteligent", "smart", "fletxa", "link"):
        marc = False
    else:
        raise BridgeError("«mode» ha de ser 'intel·ligent' o 'marc'.")
    btn = getattr(ctx.window, "b_eina", None)
    if btn is None:
        raise BridgeError("La finestra no té el commutador d'eina del timeline.")
    # El botó és la font de veritat: `setChecked` dispara `_canvia_eina` (toggled).
    btn.setChecked(marc)
    return {"eina": "marc" if bool(btn.isChecked()) else "intel·ligent"}


def _op_set_inclou_estructura(ctx, params):
    """Marca/desmarca «Inclou estructura» (afecta l'anàlisi i l'export)."""
    on = _bool(params, "on", True)
    ctx.window.amb_est.setChecked(on)
    return {"inclou_estructura": bool(ctx.window.amb_est.isChecked())}


def _op_set_inclou_partitura(ctx, params):
    """Marca/desmarca «Inclou la partitura» (afecta l'export de WAVs)."""
    on = _bool(params, "on", True)
    ctx.window.amb_part.setChecked(on)
    return {"inclou_partitura": bool(ctx.window.amb_part.isChecked())}


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
    # A7: accions de l'app que faltaven al pont.
    "set_metro": _op_set_metro,
    "set_key_detect": _op_set_key_detect,
    "detect_downbeat": _op_detect_downbeat,
    "mark_downbeat": _op_mark_downbeat,
    "open_output_folder": _op_open_output_folder,
    "select_clip": _op_select_clip,
    "toggle_selection": _op_toggle_selection,
    "clear_selection": _op_clear_selection,
    "select_at_cursor": _op_select_at_cursor,
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
    "get_options": _op_get_options,
    "export_wav": _op_export_wav,
    "export_partitura": _op_export_partitura,
    "set_tempo": _op_set_tempo,
    # Mapa de tempo/compàs (trams): mirall de l'edició de la GUI.
    "list_tempo": _op_list_tempo,
    "detecta_tempo_mapa": _op_detecta_tempo_mapa,
    "afegeix_tall": _op_afegeix_tall,
    "elimina_tall": _op_elimina_tall,
    "mou_tall": _op_mou_tall,
    "set_tram_tempo": _op_set_tram_tempo,
    # Projectes autocontinguts + paritat d'edició #11 (2026-10-15).
    "crea_projecte": _op_crea_projecte,
    "obre_projecte": _op_obre_projecte,
    "desa_projecte": _op_desa_projecte,
    "desa_com": _op_desa_com,
    "fes_backup": _op_fes_backup,
    "recents": _op_recents,
    "parteix_acord": _op_parteix_acord,
    "fusiona_acord": _op_fusiona_acord,
    "parteix_seccio": _op_parteix_seccio,
    "fusiona_seccio": _op_fusiona_seccio,
    "regularitza": _op_regularitza,
    # Paritat d'ACCIONS amb la GUI (2026-10-17): el que l'usuari pot fer, l'MCP
    # també (porta-retalls, duplicar/esborrar/reanomenar la selecció, rang i
    # loop, nudge, moure un bloc, troba i reemplaça, revertir, eina i opcions).
    "copia_seleccio": _op_copia_seleccio,
    "retalla_seleccio": _op_retalla_seleccio,
    "enganxa_seleccio": _op_enganxa_seleccio,
    "esborra_seleccio": _op_esborra_seleccio,
    "duplica_seleccio": _op_duplica_seleccio,
    "duplica_a": _op_duplica_a,
    "renomena_seleccio": _op_renomena_seleccio,
    "selecciona_rang": _op_selecciona_rang,
    "selecciona_loop": _op_selecciona_loop,
    "nudge": _op_nudge,
    "mou_bloc": _op_mou_bloc,
    "troba_i_reemplaca": _op_troba_i_reemplaca,
    "reverteix": _op_reverteix,
    "neteja_loop": _op_neteja_loop,
    "set_eina": _op_set_eina,
    "set_inclou_estructura": _op_set_inclou_estructura,
    "set_inclou_partitura": _op_set_inclou_partitura,
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
        # Nombre de connexions simultànies permeses (una = un fil).
        self._sem = threading.Semaphore(MAX_CONNEXIONS)

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
        # Vigilància de l'endpoint: si un actor extern (una eina de neteja, un
        # `git clean`, un altre procés…) l'esborra mentre l'app és viva, el
        # servidor MCP no s'hi podria connectar → el reescrivim de seguida.
        self._timer_endpoint = QTimer(self.window)
        self._timer_endpoint.timeout.connect(self._revisa_endpoint)
        self._timer_endpoint.start(15000)
        logger.info("mcp_bridge: pont actiu a 127.0.0.1:%s (port+testimoni a %s)",
                    self._port, ENDPOINT_PATH)
        print(f"[mcp_bridge] pont MCP actiu a 127.0.0.1:{self._port}", flush=True)

    # -- endpoint ----------------------------------------------------------
    def _endpoint_viu_d_algu_altre(self):
        """Pid de l'endpoint SI existeix i el seu procés és VIU i no som nosaltres.

        És la protecció clau: un segon procés (una prova, una eina, una app
        fantasma) no pot deixar l'app viva SENSE endpoint.
        """
        try:
            with open(ENDPOINT_PATH, encoding="utf-8") as f:
                dades = json.load(f)
        except (OSError, ValueError):
            return None
        pid = dades.get("pid")
        if not isinstance(pid, int) or pid == os.getpid():
            return None
        # `plataforma.proces_viu` en comptes d'`os.kill(pid, 0)`: a Windows el
        # kill no és una sonda (acaba en `TerminateProcess`: podria MATAR el
        # procés aliè i, si no hi és, llança OSError → «mort» fals).
        if not plataforma.proces_viu(pid):
            return None              # mort: el podem reciclar
        return pid

    def _revisa_endpoint(self):
        """Reescriu l'endpoint si ha desaparegut mentre l'app és viva.

        Un actor extern (una eina de neteja, un `git clean`, un altre procés…)
        el pot esborrar: aleshores el servidor MCP ja no s'hi pot connectar i
        l'app queda «sense pont» tot i tenir el socket viu. Aquí ho detectem i
        el tornem a escriure de seguida.
        """
        if not self._actiu:
            return
        if self._endpoint_viu_d_algu_altre() is not None:
            return
        try:
            with open(ENDPOINT_PATH, encoding="utf-8") as f:
                dades = json.load(f)
            if (dades.get("pid") == os.getpid()
                    and dades.get("port") == self._port):
                return               # hi és i és nostre: tot bé
        except (OSError, ValueError):
            pass
        logger.warning("mcp_bridge: l'endpoint %s havia desaparegut → el "
                       "reescric", ENDPOINT_PATH)
        self._escriu_endpoint()

    def _escriu_endpoint(self):
        # MAI sobreescriure l'endpoint d'un altre procés VIU (vegeu
        # `_endpoint_viu_d_algu_altre`): si el pid és mort, sí que el reciclem.
        viu = self._endpoint_viu_d_algu_altre()
        if viu is not None:
            logger.error(
                "mcp_bridge: NO sobreescric %s — pertany a un altre procés VIU "
                "(pid %s). Si és una app fantasma, tanca-la; aquest pont quedarà "
                "sense endpoint.", ENDPOINT_PATH, viu)
            return False
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
            # 0600: el fitxer porta el TESTIMONI; només el propietari l'ha de
            # poder llegir. `os.open` amb mode + `os.replace` (atòmic): el mode
            # del temporal es conserva en substituir el definitiu.
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
            flags |= getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(tmp, flags, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
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
        for nom in ("_timer", "_timer_endpoint"):
            t = getattr(self, nom, None)
            try:
                if t is not None:
                    t.stop()
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
            # Límit de connexions simultànies: si ja n'hi ha prou, es rebutja
            # la nova netament (sense crear-hi fil).
            if not self._sem.acquire(blocking=False):
                self._respon_error(conn, "massa connexions simultànies")
                try:
                    conn.close()
                except OSError:
                    pass
                continue
            threading.Thread(target=self._atent, args=(conn,), daemon=True).start()

    @staticmethod
    def _respon_error(conn, missatge):
        """Envia un error pel socket (best-effort; mai llança)."""
        try:
            conn.sendall((json.dumps({"ok": False, "error": missatge},
                                     ensure_ascii=False) + "\n").encode("utf-8"))
        except OSError:
            pass

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
                    # Límit ABANS de processar la línia.
                    if len(linia) > MAX_LINIA:
                        self._respon_error(conn, "línia massa llarga")
                        return
                    if not linia.strip():
                        continue
                    resposta = self._processa_linia(linia)
                    conn.sendall((json.dumps(resposta, ensure_ascii=False) + "\n")
                                 .encode("utf-8"))
                # Sense cap salt de línia i el que hi ha ja passa del màxim:
                # no pot ser una línia vàlida → error i fora.
                if len(buffer) > MAX_LINIA:
                    self._respon_error(conn, "línia massa llarga")
                    return
        except OSError as e:
            logger.debug("mcp_bridge: connexió tancada: %s", e)
        finally:
            try:
                conn.close()
            except OSError:
                pass
            self._sem.release()

    def _processa_linia(self, linia):
        try:
            msg = json.loads(linia.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            return {"ok": False, "error": f"json invàlid: {e}"}
        if not isinstance(msg, dict):
            return {"ok": False, "error": "esperava un objecte JSON"}
        # El TESTIMONI es valida ABANS de qualsevol altra feina (abans de mirar
        # l'operació i abans de posar res a la cua), amb comparació en temps
        # constant.
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
    # Amb el pont actiu, CAP avís de l'app pot ser MODAL: deixaria el pont
    # encallat fins que algú el tanqués (l'agent no rebria mai la resposta).
    # Vegeu `main.Finestra._avis`.
    window.mcp_actiu = True
    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(pont.tanca)
    except Exception:  # noqa: BLE001
        pass
    return pont if pont._actiu else None
