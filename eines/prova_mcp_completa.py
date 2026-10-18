#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prova EN VIU del pont MCP d'AUTO CHORDS — passada completa pel protocol real.

Cobreix tots els grups d'eines `ac_*` (transport, model, selecció, opcions,
projectes, partir/fusionar/regularitzar) amb un WAV de prova, **llegint l'estat
real** abans de cada operació (les eines de transport/selecció retornen
diccionaris focalitzats, no l'estat sencer).

Ús (amb l'app oberta amb `AUTO_CHORDS_MCP.sh`):
    .venv/bin/python prova_mcp_completa.py
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENDPOINT = os.environ.get("AUTO_CHORDS_MCP_ENDPOINT", "/tmp/opencode/acmcp.json")
WAV = os.environ.get("AC_PROVA_WAV", "/tmp/ac_prova.wav")
PROJ = os.environ.get("AC_PROVA_PROJ", "/tmp/ac_prova_proj")

env = dict(os.environ)
env["AUTO_CHORDS_MCP_ENDPOINT"] = ENDPOINT
p = subprocess.Popen(
    [os.path.join(ROOT, ".venv/bin/python"),
     os.path.join(ROOT, "eines/mcp_auto_chords_server.py")],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    text=True, env=env, cwd=ROOT)

_id = [0]
OK, KO = 0, 0
fallades = []


def rpc(method, params=None):
    _id[0] += 1
    p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": _id[0], "method": method,
                              "params": params or {}}) + "\n")
    p.stdin.flush()
    return json.loads(p.stdout.readline())


def call(name, **args):
    r = rpc("tools/call", {"name": name, "arguments": args})
    res = r.get("result", {})
    txt = (res.get("content") or [{}])[0].get("text", "")
    err = res.get("isError", False)
    try:
        data = json.loads(txt)
    except ValueError:
        data = txt
    return err, data


def prova(etiqueta, cond, detall=""):
    global OK, KO
    if cond:
        OK += 1
        print(f"  OK  {etiqueta}")
    else:
        KO += 1
        fallades.append(etiqueta)
        print(f"  KO  {etiqueta}  {str(detall)[:130]}")


def err_esperat(etiqueta, nom, **args):
    err, d = call(nom, **args)
    prova(etiqueta, bool(err), d)


def _llista(nom, clau):
    """Llista d'un `ac_list_*`; si la crida falla, buida (i no peta).

    Abans feia `d.get(...)` directament, però quan la crida torna un ERROR el
    resultat és un text i l'eina petava amb `AttributeError: 'str' object has no
    attribute 'get'` (auditoria 18-10-2026).
    """
    _err, d = call(nom)
    return d.get(clau, []) if isinstance(d, dict) else []


def chords():
    return _llista("ac_list_chords", "chords")


def seccions():
    return _llista("ac_list_sections", "sections")


print("== 0. Handshake ==")
prova("initialize", "result" in rpc("initialize", {"protocolVersion": "2024-11-05"}))
tl = rpc("tools/list")
noms = {t["name"] for t in tl["result"]["tools"]}
# El recompte ha de ser el que EXPOSA el servidor: abans hi havia un `== 51`
# hardcoded d'una sessió antiga i l'eina donava un fals KO amb 74 eines
# (auditoria 18-10-2026).
try:
    from mcp_auto_chords_server import _TOOLS as _EINES_SERVIDOR
    _n_servidor = len(_EINES_SERVIDOR)
except Exception:  # noqa: BLE001
    _n_servidor = None
prova(f"tools/list ({len(noms)} eines"
      + (" = servidor)" if _n_servidor == len(noms) else ")"),
      _n_servidor is None or len(noms) == _n_servidor,
      f"el servidor n'exposa {_n_servidor}")
prova("esquema + descripció a totes", all(
    e["inputSchema"]["type"] == "object" and e["description"]
    for e in tl["result"]["tools"]))

print("== 1. Lectura ==")
err, d = call("ac_ping")
prova("ac_ping", not err and d.get("pont"))
err, d = call("ac_status")
prova("ac_status", not err and "missatge" in d)

print("== 2. Obrir WAV i preparar el model ==")
err, d = call("ac_open_wav", path=WAV)
prova("ac_open_wav", not err and d.get("audio"))
if not seccions():
    err, _ = call("ac_add_section", ini_s=0.0, fi_s=4.0, lletra="A")
    prova("ac_add_section (model buit)", not err)
if len(chords()) < 2:
    err, _ = call("ac_add_chord", t_s=2.0, acord="C")
    prova("ac_add_chord (model buit)", not err)
prova("model amb acords i seccions", len(chords()) >= 2 and len(seccions()) >= 1,
      (len(chords()), len(seccions())))

print("== 3. Transport (dicts focalitzats) ==")
err, d = call("ac_seek", t_s=1.5)
prova("ac_seek", not err and abs(d.get("pos_s", -1) - 1.5) < 0.01, d)
err, d = call("ac_play")
prova("ac_play", not err and d.get("sonant"), d)
err, d = call("ac_pause")
prova("ac_pause", not err and not d.get("sonant"), d)
call("ac_seek", t_s=1.0)
call("ac_mark_loop_a")
call("ac_seek", t_s=3.0)
err, d = call("ac_mark_loop_b")
prova("ac_mark_loop_a/b", not err and d.get("a") == 1.0 and d.get("b") == 3.0, d)
err, d = call("ac_set_loop", on=True)
prova("ac_set_loop(on)", not err and d.get("loop_on"), d)
err, d = call("ac_set_loop", on=False)
prova("ac_set_loop(off)", not err and not d.get("loop_on"), d)
err, d = call("ac_set_mut", on=True)
prova("ac_set_mut(on)", not err and d.get("mut"), d)
err, d = call("ac_set_mut", on=False)
err, d = call("ac_stop")
prova("ac_stop", not err)
err, d = call("ac_zoom", mode="tot")
prova("ac_zoom", not err)
err, d = call("ac_set_metro", on=True)
prova("ac_set_metro", not err)
call("ac_set_metro", on=False)
err, d = call("ac_set_key_detect", on=True)
prova("ac_set_key_detect", not err)
call("ac_set_key_detect", on=False)

print("== 4. Temps / opcions ==")
err, d = call("ac_set_tempo", bpm=100, bpb=4, offset_s=0.0)
prova("ac_set_tempo", not err and abs(d["model"]["bpm"] - 100) < 0.01, d)
call("ac_set_tempo", bpm=120, bpb=4, offset_s=0.0)
err, d = call("ac_get_options")
prova("ac_get_options", not err and isinstance(d, dict))
err, d = call("ac_detect_downbeat")
prova("ac_detect_downbeat", not err)
err, d = call("ac_mark_downbeat")
prova("ac_mark_downbeat", not err)

print("== 5. Model: acords ==")
cs = chords()
t_lliure = round((cs[0]["t_s"] + cs[1]["t_s"]) / 2, 2) if len(cs) >= 2 else 1.0
n_abans = len(cs)
err, d = call("ac_add_chord", t_s=t_lliure, acord="Am")
prova("ac_add_chord", not err and d["model"]["n_chords"] == n_abans + 1, d)
cs = chords()
idx = len(cs) - 1
# L'app desa el xifrat CANONIC (`Am7` -> `A-7`, vegeu `docs/NOTACIO_XIFRAT.md`):
# l'expectativa ha de ser la canonica, no el text d'entrada.
err, d = call("ac_rename_chord", index=idx, acord="Am7")
prova("ac_rename_chord", not err and chords()[idx]["acord"] == "A-7", d)
err, d = call("ac_move_chord", index=idx, t_s=float(cs[idx]["t_s"]))
prova("ac_move_chord", not err, d)
err, d = call("ac_undo")
prova("ac_undo", not err)
err, d = call("ac_redo")
prova("ac_redo", not err)
err, d = call("ac_undo_list")
prova("ac_undo_list", not err)
err, d = call("ac_delete_chord", index=idx)
prova("ac_delete_chord", not err)
err_esperat("ac_delete_chord fora de rang -> error", "ac_delete_chord", index=999)
err_esperat("ac_add_chord temps negatiu -> error", "ac_add_chord", t_s=-1, acord="X")

print("== 6. Model: seccions ==")
ss = seccions()
idx = len(ss) - 1
err, d = call("ac_rename_section", index=idx, lletra="Z")
prova("ac_rename_section", not err, d)
err, d = call("ac_move_section", index=idx, ini_s=float(ss[idx]["ini_s"]),
              fi_s=float(ss[idx]["fi_s"]))
prova("ac_move_section", not err, d)
err, d = call("ac_delete_section", index=idx)
prova("ac_delete_section", not err, d)

print("== 7. Selecció (clau «seleccio») ==")
err, d = call("ac_select_clip", kind="chord", index=0)
prova("ac_select_clip", not err and ["chord", 0] in d.get("seleccio", []), d)
err, d = call("ac_toggle_selection", kind="section", index=0)
prova("ac_toggle_selection", not err and ["section", 0] in d.get("seleccio", []), d)
err, d = call("ac_selection", )
prova("ac_selection", not err and len(d.get("seleccio", [])) >= 1, d)
err, d = call("ac_clear_selection")
prova("ac_clear_selection", not err and not d.get("seleccio"), d)
err, d = call("ac_select_at_cursor", kind="chord")
prova("ac_select_at_cursor", not err)

print("== 8. Paritat #11 (partir / fusionar) ==")
# Assegura un estat mínim: almenys 2 acords amb un tall partible i 1 secció.
if not seccions():
    call("ac_add_section", ini_s=0.0, fi_s=4.0, lletra="A")


def _te_tall_partible():
    cs = chords()
    return any(float(cs[i + 1]["t_s"]) - float(cs[i]["t_s"]) > 0.5
               for i in range(len(cs) - 1))


if not _te_tall_partible():
    for t in (2.0, 1.0, 3.0, 0.5):
        if not call("ac_add_chord", t_s=t, acord="C")[0] and _te_tall_partible():
            break
cs = chords()
idx, tall = None, None
for i in range(len(cs) - 1):
    a, b = float(cs[i]["t_s"]), float(cs[i + 1]["t_s"])
    if b - a > 0.5:
        idx, tall = i, round((a + b) / 2, 2)
        break
n0 = len(cs)
if idx is not None:
    err, d = call("ac_parteix_acord", index=idx, t_s=tall, nom="Cm")
    prova("ac_parteix_acord", not err and d["model"]["n_chords"] == n0 + 1,
          f"idx={idx} tall={tall} n0={n0} → {d.get('model') if not err else d}")
    err, d = call("ac_fusiona_acord", index=idx)
    prova("ac_fusiona_acord", not err and d["model"]["n_chords"] == n0, d)
else:
    prova("ac_parteix_acord (sense acord partible)", False, f"model: {cs}")
err_esperat("ac_fusiona_acord amb invalid -> error", "ac_fusiona_acord",
            index=0, amb="dalt")
ss = seccions()
m0 = len(ss)
if ss:
    tall = round((float(ss[0]["ini_s"]) + float(ss[0]["fi_s"])) / 2, 2)
    err, d = call("ac_parteix_seccio", index=0, t_s=tall, lletra="A2")
    prova("ac_parteix_seccio", not err and d["model"]["n_sections"] == m0 + 1, d)
    err, d = call("ac_fusiona_seccio", index=0)
    prova("ac_fusiona_seccio", not err and d["model"]["n_sections"] == m0, d)
else:
    prova("ac_parteix_seccio (sense secció)", False, "cap secció al model")

print("== 9. Mode fàcil (graella) ==")
err, d = call("ac_regularitza", nivell="compas")
prova("ac_regularitza", not err, d)
err_esperat("ac_regularitza nivell invalid -> error", "ac_regularitza",
            nivell="setmana")
err_esperat("ac_regularitza modul negatiu -> error", "ac_regularitza",
            modul_compassos=-1)

print("== 10. Projectes ==")
err, d = call("ac_crea_projecte", path=PROJ)
prova("ac_crea_projecte", not err, d)
acproj = next((os.path.join(PROJ, f)
               for f in (os.listdir(PROJ) if os.path.isdir(PROJ) else [])
               if f.endswith(".acproj")), None)
prova(".acproj creat", acproj is not None)
err, d = call("ac_desa_projecte")
prova("ac_desa_projecte", not err, d)
err, d = call("ac_fes_backup")
prova("ac_fes_backup", not err and d.get("ok") and os.path.isdir(d.get("backup", "")), d)
err, d = call("ac_recents")
prova("ac_recents", not err and len(d.get("recents", [])) >= 1, d)
if acproj:
    err, d = call("ac_obre_projecte", path=acproj)
    prova("ac_obre_projecte", not err, d)
err_esperat("ac_obre_projecte inexistent -> error", "ac_obre_projecte",
            path="/tmp/opencode/no.acproj")
err_esperat("ac_desa_com sense ruta -> error", "ac_desa_com")

print(f"\n== RESULTAT: {OK} OK · {KO} KO ==")
if fallades:
    print("Fallades: " + ", ".join(fallades))
p.stdin.close()
p.wait(timeout=10)
sys.exit(0 if KO == 0 else 1)
