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


def _op_status(ctx, params):
    w = ctx.window
    vr = ctx.visor
    estat = {
        "pont": PONT_VERSION,
        "app": {"versio": APP_VERSION, "titol": w.windowTitle()},
        "audio": None,
        "missatge": "",
        # Darrer avís que l'app ha hagut de donar amb el pont actiu (llavors NO
        # és modal, perquè no encalli el pont): així l'agent el pot veure.
        "avis": getattr(w, "ultim_avis", ""),
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
    # Mateix sanejat que l'alta i l'export (separadors, reservats de Windows…):
    # si no, el nom del CSV i el del WAV exportat podien divergir.
    nom = pipeline.saneja_nom_acord(nom)
    if not nom:
        raise BridgeError("El nom de l'acord no és vàlid.")

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
    except Exception as e:  # noqa: BLE001
        logger.warning("mcp_bridge: no s'ha pogut actualitzar la info del WAV: %s", e)
    w._carrega_visor(treball)
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
    """Exporta el paquet de WAV's (síncron). Pot trigar segons el tema.

    ⚠️ L'export pot voler avisar l'usuari: amb el pont actiu aquests avisos són
    NO modals (un modal encallaria el pont) i el text es retorna aquí.
    """
    w = ctx.window
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
    r = {"ok": True, "sortida": getattr(w, "sortida", "") or ""}
    if getattr(w, "ultim_avis", ""):
        r["avis"] = w.ultim_avis
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
    """Selecciona el clip que CONTÉ el cursor (`kind`: chord|section)."""
    _requereix_visor(ctx)          # cal un visor carregat (a qui seleccionar)
    kind = str(params.get("kind") or params.get("tipus") or "chord").lower()
    if kind == "section":
        ctx.window._sel_seccio_cursor()
    elif kind == "chord":
        ctx.window._sel_acord_cursor()
    else:
        raise BridgeError("kind ha de ser 'chord' o 'section'.")
    return _op_selection(ctx, {})


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
        try:
            os.kill(pid, 0)          # senyal 0: només comprova que existeixi
        except ProcessLookupError:
            return None              # mort: el podem reciclar
        except PermissionError:
            pass                     # viu (d'un altre usuari)
        except OSError:
            return None
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
