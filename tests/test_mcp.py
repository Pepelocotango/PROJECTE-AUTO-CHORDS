"""Suite de test — Mcp

> Suite CONSOLIDADA (Fase 4, 2026-10-19): fusiona 8 mòduls de test que abans
> vivien separats a `tests/`. Cada bloc conserva el seu codi original íntegre
> (només s'han renombrat els símbols de nivell superior que xocaven i s'han
> unificat els imports). Cobertura intacta: cap test eliminat.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene: esborra els temporals en plegar

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
import importlib.util
import json
import shutil
import socket
import tempfile
import threading
from unittest.mock import patch
from app import mcp_bridge
from app import pipeline
from app import projecte
import wave
import PyQt5.QtWidgets as QW
from app import main as app_main
import copy
from app import dialegs
import ast
import re
from eines import mcp_auto_chords_server as srv
from PyQt5.QtCore import Qt



def tearDownModule():
    _mcp_bridge_tearDownModule()
    _mcp_a4_tearDownModule()
    _mcp_a6_tearDownModule()
    _mcp_a7_tearDownModule()
    _avis_no_modal_tearDownModule()


# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_mcp_bridge.py
# ══════════════════════════════════════════════════════════════════════════
"""Tests del pont MCP (`app/mcp_bridge.py` + `eines/mcp_auto_chords_server.py`).

⚠️ **Per què amb dobles i sense GUI**: el pont real necessita l'app viva i el
fil de Qt. Aquí provem la **lògica** (registre d'operacions, lectura de
l'estat, edició amb undo/validació i el protocol MCP) amb un `window`/`visor`
**falsos**, de manera que corre a Linux sense pantalla ni l'app oberta.

La prova real d'extrem a extrem (app oberta amb `AUTO_CHORDS_MCP.sh`) es fa a
mà; vegeu `docs/MCP_AUTO_CHORDS.md`.
"""



ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── Dobles de l'app ──────────────────────────────────────────────────────────
class _FakeTimeline:
    def __init__(self):
        self._data = []
        self._multi = {("chord", 0)}
        self._pos = 12.5

    def set_data(self, acords, seccions):
        self._data = (list(acords), list(seccions))

    def selected_keys(self):
        return set(self._multi)

    def get_position(self):
        return self._pos

    def zoom_full(self):
        pass

    def zoom_selection(self):
        pass

    def zoom_in(self):
        pass

    def zoom_out(self):
        pass


class _FakeVisor:
    def __init__(self):
        self.wav_path = "/tmp/tema.wav"
        self.audio = {"durada": 120.0, "sr": 44100, "canals": 2}
        self.csv_acords = "/tmp/out/acords.csv"
        self.bpm, self.bpb, self.offset, self.tempo_fix = 120.0, 4, 0.0, True
        self.acords = [
            pipeline.Clip(0.0, 4.0, ("N", "0.000000000")),
            pipeline.Clip(4.0, 8.0, ("C", "4.000000000")),
            pipeline.Clip(8.0, 120.0, ("G", "8.000000000"))]
        self.seccions = [(0.0, 16.0, "A", "A"), (16.0, 40.0, "B", "B")]
        self.pos = 0.0
        self.sona = False
        self.loop_a = None
        self.loop_b = None
        self.loop_on = False
        self.mut = False
        self.metro_on = False
        self.timeline = _FakeTimeline()
        self._undo_stack = []
        self._redo_stack = []
        self._undo_pending = None
        self._base_estat = self._estat_edicio()
        self.desa_cops = 0
        self.abc_cops = 0

    # -- model ----------------------------------------------------------
    def _estat_edicio(self):
        import copy
        return (copy.deepcopy(list(self.acords)), copy.deepcopy(list(self.seccions)))

    def _undo_marca(self):
        if self._undo_pending is None:
            self._undo_pending = self._base_estat

    def _undo_commit(self):
        ara = self._estat_edicio()
        if self._undo_pending is not None and ara != self._undo_pending:
            self._undo_stack.append(self._undo_pending)
            self._redo_stack.clear()
        self._base_estat = ara
        self._undo_pending = None

    def _normalitza_acords(self, items=None):
        items = self.acords if items is None else items
        durada = float(self.audio["durada"])
        ordenats = sorted(items, key=lambda x: float(x[0]))
        prev = None
        for it in ordenats:
            t = float(it[0])
            if t < 0:
                raise ValueError(f"inici negatiu: {t}")
            if prev is not None and t <= prev + 1e-9:
                raise ValueError("inici duplicat/ invertit")
            prev = t
        out = []
        for i, a in enumerate(ordenats):
            fi = (float(ordenats[i + 1][0]) if i + 1 < len(ordenats)
                  else durada)
            p = a.payload if isinstance(a, pipeline.Clip) else tuple(a[1:])
            out.append(pipeline.Clip(float(a[0]), fi, tuple(p)))
        if isinstance(items, list):
            self.acords = out
        return out

    def _normalitza_seccions(self, items=None):
        items = self.seccions if items is None else items
        ordenats = sorted(items, key=lambda x: float(x[0]))
        if isinstance(items, list):
            self.seccions = ordenats
        return ordenats

    def _omple_llista_ac(self):
        pass

    def _actualitza_llista_abc(self):
        pass

    def _actualitza_editor(self):
        pass

    def _desa_i_regenera(self):
        self.desa_cops += 1

    def _regenera_abc_des_de_totes_les_seccions(self, msg):
        self.abc_cops += 1

    # -- transport ------------------------------------------------------
    def ves_a(self, t):
        self.pos = float(t)

    def play_stop(self):
        self.sona = not self.sona

    def stop_inici(self):
        self.sona = False
        self.pos = 0.0

    def marca_A(self):
        self.loop_a = self.pos

    def marca_B(self):
        self.loop_b = self.pos

    def set_loop(self, on):
        self.loop_on = bool(on)

    def set_mut(self, on):
        self.mut = bool(on)

    def undo(self):
        if self._undo_stack:
            self._redo_stack.append(self._estat_edicio())
            est = self._undo_stack.pop()
            self.acords, self.seccions = est

    def redo(self):
        if self._redo_stack:
            self._undo_stack.append(self._estat_edicio())
            est = self._redo_stack.pop()
            self.acords, self.seccions = est

    # -- partir / fusionar (paritat d'edició #11) ------------------------
    MIN = 1e-3

    def parteix_acord(self, idx, t, nom=None):
        if not (0 <= idx < len(self.acords)) or idx + 1 >= len(self.acords):
            return False
        t = float(t)
        t0 = float(self.acords[idx][0])
        fi = float(self.acords[idx + 1][0])
        if not (t0 + self.MIN <= t <= fi - self.MIN):
            return False
        self._undo_marca()
        vell = self.acords[idx].nom
        nom = (str(nom).strip() if nom else vell) or vell
        nou = pipeline.parteix_clips(list(self.acords), idx, t,
                                     nou_payload=(nom, f"{t:.9f}"),
                                     marge=self.MIN)
        self.acords = self._normalitza_acords(list(nou))
        self._undo_commit()
        self.timeline.set_data(self.acords, self.seccions)
        self._omple_llista_ac()
        return idx + 1

    def fusiona_acord(self, idx, amb="seguent"):
        if not (0 <= idx < len(self.acords)):
            return False
        j = idx + 1 if amb == "seguent" else idx - 1
        if not (0 <= j < len(self.acords)):
            return False
        self._undo_marca()
        nou = pipeline.fusiona_clips(list(self.acords), idx, amb,
                                     etiqueta="acord")
        self.acords = self._normalitza_acords(list(nou))
        self._undo_commit()
        self.timeline.set_data(self.acords, self.seccions)
        self._omple_llista_ac()
        self._desa_i_regenera()
        return True

    def parteix_seccio(self, idx, t, lletra=None, fam=None):
        if not (0 <= idx < len(self.seccions)):
            return False
        t = float(t)
        ini, fi, L, F = self.seccions[idx]
        ini, fi = float(ini), float(fi)
        if not (ini + self.MIN <= t <= fi - self.MIN):
            return False
        self._undo_marca()
        L2 = (str(lletra).strip() if lletra else L) or L
        F2 = (str(fam).strip() if fam else (F or L2)) or L2
        nova = list(self.seccions)
        nova[idx] = (ini, t, L, F)
        nova.insert(idx + 1, (t, fi, L2, F2))
        self.seccions = self._normalitza_seccions(nova)
        self._undo_commit()
        self.timeline.set_data(self.acords, self.seccions)
        self._actualitza_llista_abc()
        return idx + 1

    def fusiona_seccio(self, idx, amb="seguent"):
        if not (0 <= idx < len(self.seccions)):
            return False
        j = idx + 1 if amb == "seguent" else idx - 1
        if not (0 <= j < len(self.seccions)):
            return False
        self._undo_marca()
        nova = list(self.seccions)
        del nova[j]
        self.seccions = self._normalitza_seccions(nova)
        self._undo_commit()
        self.timeline.set_data(self.acords, self.seccions)
        self._actualitza_llista_abc()
        self._regenera_abc_des_de_totes_les_seccions(f"secció {idx} fusionada")
        return True

    def regularitza_des_de_cru(self, nivell="auto", modul_compassos=0):
        """Fake del mode fàcil: deixa un acord cada 2,0 s (120 BPM)."""
        dur = float(self.audio["durada"])
        pas = 2.0
        n = max(1, int(dur // pas))
        self._undo_marca()
        self.acords = self._normalitza_acords(
            [(i * pas, f"C{i % 4}", f"{i * pas:.9f}") for i in range(n)])
        self._undo_commit()
        self.desa_cops += 1
        return len(self.acords)


class _FakeEdit:
    """QLineEdit mínim (només el que fa servir el pont)."""

    def __init__(self, text=""):
        self._t = text

    def text(self):
        return self._t

    def setText(self, t):
        self._t = str(t)


class _FakeCheck:
    """QCheckBox mínim."""

    def __init__(self, on=False):
        self._on = on

    def isChecked(self):
        return self._on


class _FakeWindow:
    def __init__(self, visor=None):
        self.visor_ref = visor
        self.sortida = "/tmp/out"
        # Estat de projecte (per a les ops de projectes).
        self.projecte = None
        self.recents = []
        self.dirty = False
        self.titols = 0
        self.activats = []
        # Widgets mínims (per a `crea_projecte`).
        self.wav_edit = _FakeEdit("")
        self.bpb = _FakeEdit("4")
        self.tempo_fix = _FakeCheck(True)
        self.opcions = {}

    def _bpm_val(self):
        return 120.0

    def _bpb_val(self):
        return 4

    def _offset_val(self):
        return 0.0

    def _activa_projecte(self, p):
        self.projecte = p
        self.activats.append(p.carpeta)

    def _refresca_dades_projecte(self):
        pass

    def _actualitza_titol(self):
        self.titols += 1

    def _afegeix_recent(self, ruta):
        if ruta not in self.recents:
            self.recents.append(ruta)

    def windowTitle(self):
        return "Auto Chords — prova"


def _ctx(visor=None):
    return mcp_bridge._Context(_FakeWindow(visor))


# ── Registre ─────────────────────────────────────────────────────────────────
class TestRegistre(unittest.TestCase):
    def test_operacions_esperades(self):
        esperades = {
            "ping", "status", "list_chords", "list_sections", "selection",
            "add_chord", "rename_chord", "move_chord", "delete_chord",
            "add_section", "rename_section", "move_section", "delete_section",
            "undo", "redo", "seek", "play", "pause", "stop",
            "mark_loop_a", "mark_loop_b", "set_loop", "set_mut", "zoom",
            "undo_list", "open_wav", "analyze", "get_options", "export_wav",
            "export_partitura", "set_tempo",
            # A7: accions de l'app que faltaven al pont.
            "set_metro", "set_key_detect", "detect_downbeat", "mark_downbeat",
            "open_output_folder", "select_clip", "toggle_selection",
            "clear_selection", "select_at_cursor",
            # Projectes autocontinguts + paritat d'edició #11 (2026-10-15).
            "crea_projecte", "obre_projecte", "desa_projecte", "desa_com",
            "fes_backup", "recents", "parteix_acord", "fusiona_acord",
            "parteix_seccio", "fusiona_seccio",
            # Mode fàcil (graella) — 2026-10-15.
            "regularitza",
            # Paritat d'ACCIONS amb la GUI — 2026-10-17.
            "copia_seleccio", "retalla_seleccio", "enganxa_seleccio",
            "esborra_seleccio", "duplica_seleccio", "duplica_a",
            "renomena_seleccio",
            "selecciona_rang", "selecciona_loop", "nudge", "mou_bloc",
            "troba_i_reemplaca", "reverteix", "neteja_loop", "set_eina",
            "set_inclou_estructura", "set_inclou_partitura",
            # Mapa de tempo/compàs (trams) — 2026-10-18.
            "list_tempo", "afegeix_tall", "elimina_tall", "mou_tall",
            "detecta_tempo_mapa", "set_tram_tempo",
        }
        self.assertEqual(set(mcp_bridge.OPERACIONS), esperades)


# ── Lectura ──────────────────────────────────────────────────────────────────
class TestLectura(unittest.TestCase):
    def test_status_sense_visor(self):
        r = mcp_bridge._op_status(_ctx(None), {})
        self.assertIsNone(r["audio"])
        self.assertIn("missatge", r)

    def test_status_amb_visor(self):
        vr = _FakeVisor()
        r = mcp_bridge._op_status(_ctx(vr), {})
        self.assertEqual(r["audio"]["wav"], "tema.wav")
        self.assertEqual(r["model"]["mode"], "bpm_compas")
        self.assertEqual(r["model"]["n_chords"], 3)
        self.assertEqual(r["transport"]["pos_s"], 0.0)
        self.assertFalse(r["transport"]["sonant"])

    def test_list_chords(self):
        r = mcp_bridge._op_list_chords(_ctx(_FakeVisor()), {})
        self.assertEqual(len(r["chords"]), 3)
        self.assertEqual(r["chords"][1]["acord"], "C")
        self.assertEqual(r["chords"][1]["t_s"], 4.0)

    def test_list_sections(self):
        r = mcp_bridge._op_list_sections(_ctx(_FakeVisor()), {})
        self.assertEqual(r["sections"][0]["durada_s"], 16.0)
        self.assertEqual(r["sections"][1]["lletra"], "B")

    def test_selection(self):
        vr = _FakeVisor()
        vr.pos = 12.5
        r = mcp_bridge._op_selection(_ctx(vr), {})
        self.assertEqual(r["seleccio"], [["chord", 0]])
        self.assertEqual(r["pos_s"], 12.5)

    def test_lectura_sense_visor_es_error(self):
        from app.mcp_bridge import BridgeError
        with self.assertRaises(BridgeError):
            mcp_bridge._op_list_chords(_ctx(None), {})


# ── Edició ───────────────────────────────────────────────────────────────────
class TestEdicio(unittest.TestCase):
    def test_add_chord_i_desat(self):
        vr = _FakeVisor()
        r = mcp_bridge._op_add_chord(_ctx(vr), {"t_s": 6.0, "acord": "Am"})
        self.assertEqual(len(vr.acords), 4)
        self.assertEqual(r["model"]["n_chords"], 4)
        self.assertEqual(vr.desa_cops, 1)
        self.assertTrue(vr._undo_stack)          # hi ha un pas per desfer

    def test_add_chord_invalid_es_rebutja(self):
        from app.mcp_bridge import BridgeError
        vr = _FakeVisor()
        with self.assertRaises(BridgeError):
            # t coincideix amb l'acord de 4.0 s -> lògica temporal invàlida
            mcp_bridge._op_add_chord(_ctx(vr), {"t_s": 4.0, "acord": "X"})
        self.assertEqual(len(vr.acords), 3)      # estat intacte
        self.assertEqual(vr.desa_cops, 0)

    def test_rename_i_move_chord(self):
        vr = _FakeVisor()
        mcp_bridge._op_rename_chord(_ctx(vr), {"index": 1, "acord": "Cmaj"})
        # el MODEL es desa en notació canònica: `Cmaj` → `C` (tríada major)
        self.assertEqual(vr.acords[1][2][0], "C")
        mcp_bridge._op_move_chord(_ctx(vr), {"index": 1, "t_s": 5.0})
        self.assertEqual(vr.acords[1][0], 5.0)

    def test_delete_chord(self):
        vr = _FakeVisor()
        # S'esborra un acord REAL (el del mig). Esborrar l'índex 0 (la «N» de
        # capçalera) el núcli el torna a tapar amb la «N» (cobertura #4, §6.4),
        # o sigui que no en canvia el recompte.
        mcp_bridge._op_delete_chord(_ctx(vr), {"index": 1})
        self.assertEqual(len(vr.acords), 2)
        self.assertEqual([a[2][0] for a in vr.acords], ["N", "G"])

    def test_delete_chord_fora_rang(self):
        from app.mcp_bridge import BridgeError
        vr = _FakeVisor()
        with self.assertRaises(BridgeError):
            mcp_bridge._op_delete_chord(_ctx(vr), {"index": 99})

    def test_add_i_delete_section(self):
        vr = _FakeVisor()
        mcp_bridge._op_add_section(_ctx(vr), {"ini_s": 40.0, "fi_s": 60.0,
                                              "lletra": "C", "familia": "C"})
        self.assertEqual(len(vr.seccions), 3)
        # S'esborra una secció REAL (la del mig): el nucli §6.4 fa que
        # l'anterior s'estiri. (Esborrar la 0 deixaria un forat «-» davant.)
        mcp_bridge._op_delete_section(_ctx(vr), {"index": 1})
        self.assertEqual(len(vr.seccions), 2)
        self.assertEqual([s[2] for s in vr.seccions], ["A", "C"])

    def test_undo_redo(self):
        vr = _FakeVisor()
        mcp_bridge._op_add_chord(_ctx(vr), {"t_s": 6.0, "acord": "Am"})
        n = len(vr.acords)
        mcp_bridge._op_undo(_ctx(vr), {})
        self.assertEqual(len(vr.acords), n - 1)
        mcp_bridge._op_redo(_ctx(vr), {})
        self.assertEqual(len(vr.acords), n)


# ── Servidor MCP ─────────────────────────────────────────────────────────────
def _carrega_servidor():
    ruta = os.path.join(ROOT, "eines", "mcp_auto_chords_server.py")
    spec = importlib.util.spec_from_file_location("mcp_auto_chords_server", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestParitatEdicio(unittest.TestCase):
    """Partir / fusionar (regla d'or #11) a través del pont MCP."""

    def test_parteix_acord(self):
        vr = _FakeVisor()
        r = mcp_bridge._op_parteix_acord(_ctx(vr), {"index": 1, "t_s": 6.0})
        self.assertEqual(len(vr.acords), 4)
        self.assertEqual(r["model"]["n_chords"], 4)
        self.assertTrue(vr._undo_stack)          # hi ha un pas per desfer

    def test_parteix_acord_temps_fora_es_error(self):
        from app.mcp_bridge import BridgeError
        vr = _FakeVisor()
        with self.assertRaises(BridgeError):
            mcp_bridge._op_parteix_acord(_ctx(vr), {"index": 1, "t_s": 3.9})
        self.assertEqual(len(vr.acords), 3)      # estat intacte

    def test_parteix_acord_nom_nova_part(self):
        vr = _FakeVisor()
        mcp_bridge._op_parteix_acord(
            _ctx(vr), {"index": 1, "t_s": 6.0, "nom": "Am"})
        self.assertEqual(vr.acords[2][2][0], "Am")

    def test_parteix_acord_accepta_fraccions_de_segon(self):
        # Regressió (2026-10-15): `t_s` ha de ser FLOAT. Abans es passava
        # `enter=True` a `_num` i el temps es TRUNCAVA a enter (0.5 -> 0).
        vr = _FakeVisor()
        mcp_bridge._op_parteix_acord(_ctx(vr), {"index": 1, "t_s": 6.5})
        self.assertEqual(len(vr.acords), 4)
        self.assertEqual(float(vr.acords[2][0]), 6.5)

    def test_parteix_seccio_accepta_fraccions_de_segon(self):
        vr = _FakeVisor()
        mcp_bridge._op_parteix_seccio(_ctx(vr), {"index": 0, "t_s": 7.5})
        self.assertEqual(float(vr.seccions[1][0]), 7.5)

    def test_fusiona_acord(self):
        vr = _FakeVisor()
        r = mcp_bridge._op_fusiona_acord(_ctx(vr), {"index": 1})
        self.assertEqual(len(vr.acords), 2)
        self.assertEqual(r["model"]["n_chords"], 2)

    def test_fusiona_acord_amb_invalid(self):
        from app.mcp_bridge import BridgeError
        vr = _FakeVisor()
        with self.assertRaises(BridgeError):
            mcp_bridge._op_fusiona_acord(_ctx(vr), {"index": 1, "amb": "dalt"})

    def test_parteix_seccio(self):
        vr = _FakeVisor()
        r = mcp_bridge._op_parteix_seccio(_ctx(vr), {"index": 0, "t_s": 8.0})
        self.assertEqual(len(vr.seccions), 3)
        self.assertEqual(r["model"]["n_sections"], 3)
        self.assertGreaterEqual(vr.abc_cops, 1)

    def test_parteix_seccio_temps_fora_es_error(self):
        from app.mcp_bridge import BridgeError
        vr = _FakeVisor()
        with self.assertRaises(BridgeError):
            mcp_bridge._op_parteix_seccio(_ctx(vr), {"index": 0, "t_s": 0.0})
        self.assertEqual(len(vr.seccions), 2)

    def test_fusiona_seccio(self):
        vr = _FakeVisor()
        mcp_bridge._op_fusiona_seccio(_ctx(vr), {"index": 0})
        self.assertEqual(len(vr.seccions), 1)


class TestModeFacil(unittest.TestCase):
    """Mode fàcil (graella / ritme harmònic) a través del pont MCP."""

    def test_regularitza(self):
        vr = _FakeVisor()
        r = mcp_bridge._op_regularitza(_ctx(vr), {"nivell": "compas"})
        self.assertEqual(r["model"]["n_chords"], len(vr.acords))
        self.assertTrue(vr._undo_stack)          # hi ha un pas per desfer
        self.assertGreaterEqual(vr.desa_cops, 1)

    def test_regularitza_auto_per_defecte(self):
        vr = _FakeVisor()
        mcp_bridge._op_regularitza(_ctx(vr), {})
        self.assertGreaterEqual(len(vr.acords), 1)

    def test_regularitza_nivell_invalid(self):
        from app.mcp_bridge import BridgeError
        vr = _FakeVisor()
        with self.assertRaises(BridgeError):
            mcp_bridge._op_regularitza(_ctx(vr), {"nivell": "setmana"})

    def test_regularitza_modul_negatiu(self):
        from app.mcp_bridge import BridgeError
        vr = _FakeVisor()
        with self.assertRaises(BridgeError):
            mcp_bridge._op_regularitza(_ctx(vr), {"modul_compassos": -1})

    def test_regularitza_sense_resultat(self):
        from app.mcp_bridge import BridgeError
        vr = _FakeVisor()
        vr.regularitza_des_de_cru = lambda *a, **k: 0
        with self.assertRaises(BridgeError):
            mcp_bridge._op_regularitza(_ctx(vr), {})


class TestProjectes(unittest.TestCase):
    """Eines de projecte (`.acproj`) a través del pont MCP."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acproj_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.wav = os.path.join(self.tmp, "tema.wav")
        with open(self.wav, "wb") as f:
            f.write(b"RIFF....WAVEfmt ")   # WAV fals: només cal que existeixi
        self.p = projecte.Projecte.crea(
            os.path.join(self.tmp, "ElMeuProjecte"), self.wav, nom="ElMeuProjecte")

    def _win(self):
        w = _FakeWindow()
        w.projecte = self.p
        return w

    def test_crea_projecte(self):
        w = _FakeWindow()
        w.wav_edit.setText(self.wav)
        desti = os.path.join(self.tmp, "NOU")
        mcp_bridge._op_crea_projecte(mcp_bridge._Context(w), {"path": desti})
        self.assertIsNotNone(w.projecte)
        self.assertTrue(os.path.isfile(w.projecte.ruta_acproj))
        self.assertTrue(w.projecte.audio_present())

    def test_crea_projecte_sense_ruta(self):
        from app.mcp_bridge import BridgeError
        w = _FakeWindow()
        with self.assertRaises(BridgeError):
            mcp_bridge._op_crea_projecte(mcp_bridge._Context(w), {})

    def test_crea_projecte_sense_wav(self):
        from app.mcp_bridge import BridgeError
        w = _FakeWindow()
        with self.assertRaises(BridgeError):
            mcp_bridge._op_crea_projecte(
                mcp_bridge._Context(w), {"path": os.path.join(self.tmp, "X")})

    def test_obre_projecte(self):
        w = _FakeWindow()
        mcp_bridge._op_obre_projecte(
            mcp_bridge._Context(w), {"path": self.p.ruta_acproj})
        self.assertIsNotNone(w.projecte)
        self.assertEqual(w.projecte.nom, "ElMeuProjecte")
        self.assertTrue(w.activats)              # s'ha activat a la finestra

    def test_obre_projecte_inexistent(self):
        from app.mcp_bridge import BridgeError
        w = _FakeWindow()
        with self.assertRaises(BridgeError):
            mcp_bridge._op_obre_projecte(
                mcp_bridge._Context(w), {"path": os.path.join(self.tmp, "no.acproj")})

    def test_obre_projecte_sense_ruta(self):
        from app.mcp_bridge import BridgeError
        w = _FakeWindow()
        with self.assertRaises(BridgeError):
            mcp_bridge._op_obre_projecte(mcp_bridge._Context(w), {})

    def test_desa_projecte(self):
        w = self._win()
        mcp_bridge._op_desa_projecte(mcp_bridge._Context(w), {})
        self.assertFalse(w.dirty)
        self.assertIn(self.p.ruta_acproj, w.recents)

    def test_desa_projecte_sense_projecte(self):
        from app.mcp_bridge import BridgeError
        w = _FakeWindow()
        with self.assertRaises(BridgeError):
            mcp_bridge._op_desa_projecte(mcp_bridge._Context(w), {})

    def test_desa_com(self):
        w = self._win()
        desti = os.path.join(self.tmp, "COPIA")
        mcp_bridge._op_desa_com(mcp_bridge._Context(w), {"path": desti})
        self.assertEqual(os.path.abspath(w.projecte.carpeta), os.path.abspath(desti))
        self.assertTrue(os.path.isfile(w.projecte.ruta_acproj))

    def test_desa_com_sense_ruta(self):
        from app.mcp_bridge import BridgeError
        w = self._win()
        with self.assertRaises(BridgeError):
            mcp_bridge._op_desa_com(mcp_bridge._Context(w), {})

    def test_fes_backup(self):
        w = self._win()
        r = mcp_bridge._op_fes_backup(mcp_bridge._Context(w), {})
        self.assertTrue(r["ok"])
        self.assertTrue(os.path.isdir(r["backup"]))
        self.assertIn(r["backup"], r["backups"])

    def test_recents_filtra_inexistents(self):
        w = _FakeWindow()
        w.recents = [self.p.ruta_acproj,
                     os.path.join(self.tmp, "noexisteix.acproj")]
        r = mcp_bridge._op_recents(mcp_bridge._Context(w), {})
        self.assertEqual(r["recents"], [self.p.ruta_acproj])


class TestServidor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = _carrega_servidor()

    def test_tools_ben_formades(self):
        eines = self.srv._tools_mcp()
        noms = {e["name"] for e in eines}
        self.assertIn("ac_status", noms)
        self.assertIn("ac_add_chord", noms)
        for e in eines:
            self.assertEqual(e["inputSchema"]["type"], "object")
            self.assertTrue(e["description"])

    def test_mapa_eines_coincideix_amb_pont(self):
        ops = set(self.srv._OP_PER_TOOL.values())
        self.assertTrue(ops <= set(mcp_bridge.OPERACIONS))
        self.assertEqual(set(mcp_bridge.OPERACIONS) - ops, set())

    def test_initialize(self):
        r = self.srv.gestiona({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                               "params": {"protocolVersion": "2024-11-05"}})
        self.assertEqual(r["result"]["serverInfo"]["name"], "mcp_auto_chords")
        self.assertIn("tools", r["result"]["capabilities"])

    def test_tools_list(self):
        r = self.srv.gestiona({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertTrue(any(t["name"] == "ac_status" for t in r["result"]["tools"]))

    def test_tools_call_ok(self):
        self.srv.crida_pont = lambda op, args: {"op": op, "echo": args}
        r = self.srv.gestiona({
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "ac_status", "arguments": {}}})
        self.assertFalse(r["result"]["isError"])
        text = r["result"]["content"][0]["text"]
        self.assertIn("status", text)

    def test_tools_call_error(self):
        def _falla(op, args):
            raise RuntimeError("pont no actiu")
        self.srv.crida_pont = _falla
        r = self.srv.gestiona({
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {"name": "ac_ping", "arguments": {}}})
        self.assertTrue(r["result"]["isError"])
        self.assertIn("pont no actiu", r["result"]["content"][0]["text"])

    def test_metode_desconegut(self):
        r = self.srv.gestiona({"jsonrpc": "2.0", "id": 5, "method": "foo/bar"})
        self.assertEqual(r["error"]["code"], -32601)

    def test_notificacio_sense_resposta(self):
        self.assertIsNone(self.srv.gestiona(
            {"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_crida_sense_pont(self):
        antic = self.srv.ENDPOINT_PATH
        self.srv.ENDPOINT_PATH = "/tmp/no_existeix_mai_mcp_bridge.json"
        try:
            with self.assertRaises(self.srv.PontNoActiu):
                self.srv.crida_pont("status", {})
        finally:
            self.srv.ENDPOINT_PATH = antic


# ── Pont amb SOCKET real (Pas 3: testimoni, límits i connexió bona) ──────────
class TestPontSocket(unittest.TestCase):
    """Pont MCP amb un socket TCP de debò (`127.0.0.1`).

    ⚠️ Aquests tests creen una `QApplication` (offscreen) i un `PontMCP` real:
    la cua cap al fil de Qt es buida amb el `QTimer`, que aquí fem avançar amb
    `processEvents()`.
    """

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtWidgets import QApplication, QWidget
        cls.QApplication = QApplication
        cls.QWidget = QWidget
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._pat = patch.object(
            mcp_bridge, "ENDPOINT_PATH",
            os.path.join(self._tmp, "mcp_bridge.json"))
        self._pat.start()
        self.w = self.QWidget()
        self.pont = mcp_bridge.PontMCP(self.w)
        self.assertTrue(self.pont._actiu, "el pont no s'ha pogut obrir")
        self._obertes = []

    def tearDown(self):
        for s in self._obertes:
            try:
                s.close()
            except OSError:
                pass
        self.pont.tanca()
        self._pat.stop()
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _connecta(self):
        s = socket.create_connection(("127.0.0.1", self.pont._port), timeout=5)
        self._obertes.append(s)
        return s

    def _enviar(self, s, obj):
        s.sendall((json.dumps(obj) + "\n").encode("utf-8"))

    def _llegeix_linia(self, s, amb_qt=False):
        """Llegeix una línia del socket; amb `amb_qt`, fa avançar el fil de Qt."""
        caixa = {}

        def _fil():
            buf = b""
            try:
                s.settimeout(15)
                while b"\n" not in buf:
                    troç = s.recv(65536)
                    if not troç:
                        break
                    buf += troç
            except OSError as e:  # noqa: BLE001
                caixa["err"] = e
                return
            if buf:
                caixa["linia"] = buf.split(b"\n", 1)[0]

        t = threading.Thread(target=_fil)
        t.start()
        while t.is_alive():
            if amb_qt:
                self.app.processEvents()
            t.join(0.01)
        if "linia" not in caixa:
            self.fail(f"sense resposta del pont: {caixa.get('err')}")
        return json.loads(caixa["linia"])

    # --- els casos que demanava l'operador ----------------------------------
    def test_testimoni_invalid(self):
        s = self._connecta()
        self._enviar(s, {"token": "dolent", "op": "ping"})
        r = self._llegeix_linia(s)
        self.assertFalse(r["ok"])
        self.assertIn("testimoni", r["error"])

    def test_linia_sobredimensionada(self):
        # El valor REAL del límit es comprova a `test_constants`; aquí el patem
        # a un valor petit perquè el test sigui ràpid i determinista (sense
        # arriscar un RST mentre encara s'envia).
        with patch.object(mcp_bridge, "MAX_LINIA", 1024):
            s = self._connecta()
            s.sendall(b"x" * 2048)          # sense cap salt de línia
            r = self._llegeix_linia(s)
        self.assertFalse(r["ok"])
        self.assertIn("massa llarga", r["error"])

    def test_connexio_legitima(self):
        s = self._connecta()
        self._enviar(s, {"token": self.pont._token, "op": "ping", "params": {}})
        r = self._llegeix_linia(s, amb_qt=True)
        self.assertTrue(r["ok"], r)
        self.assertTrue(r["result"]["pong"])

    # --- límits -------------------------------------------------------------
    def test_limit_de_connexions(self):
        # Ocupa tots els llocs i comprova que la connexió de més es rebutja
        # (determinista: no depèn de córrer 9 sockets de debò).
        for _ in range(mcp_bridge.MAX_CONNEXIONS):
            self.assertTrue(self.pont._sem.acquire(blocking=False))
        try:
            s = self._connecta()
            r = self._llegeix_linia(s)
        finally:
            for _ in range(mcp_bridge.MAX_CONNEXIONS):
                self.pont._sem.release()
        self.assertFalse(r["ok"])
        self.assertIn("massa connexions", r["error"])

    def test_constants(self):
        self.assertEqual(mcp_bridge.MAX_LINIA, 1024 * 1024)     # 1 MiB
        self.assertEqual(mcp_bridge.MAX_CONNEXIONS, 8)

    @unittest.skipIf(sys.platform.startswith("win"), "permisos POSIX")
    def test_endpoint_0600(self):
        mode = os.stat(mcp_bridge.ENDPOINT_PATH).st_mode & 0o777
        self.assertEqual(mode, 0o600)

    def test_open_wav_no_restingeix_rutes(self):
        # Invariant 1: `ac_open_wav` NO ha de limitar la ruta. Amb un fitxer
        # inexistent ha de dir que no el troba (no pas que la ruta no valgui).
        from app.mcp_bridge import BridgeError
        with self.assertRaises(BridgeError) as cm:
            mcp_bridge._op_open_wav(
                _ctx(None), {"path": "/tmp/estrany amb espais & 'ü' #1.wav"})
        self.assertIn("No trobo", str(cm.exception))



def _mcp_bridge_tearDownModule():
    # Neteja ORDENADA dels objectes Qt del mòdul (evita destrucció pel GC en un
    # test posterior -> access violation intermitent). Vegeu tests/_qt_neteja.py.
    try:
        import _qt_neteja
    except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_mcp_a4.py
# ══════════════════════════════════════════════════════════════════════════
"""A4: exportar la PARTITURA des de l'MCP (i poder incloure-la amb els WAVs).

La partitura era una acció separada de la GUI (`Fitxer ▸ Exporta la partitura…`)
i l'MCP no la podia demanar. Ara hi ha `ac_export_partitura` (sense obrir cap
finestra ni carpeta) i `ac_export_wav` accepta `partitura` per incloure-la en
aquella exportació sense canviar la marca de l'app.
"""






def _finestra():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "t.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * 3)
    w = app_main.Finestra()
    w.wav_edit.setText(wav)
    w._carrega_visor(wav)
    return w


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QW.QApplication.instance() or QW.QApplication([])

    def ctx(self, w):
        return mcp_bridge._Context(w)


class TestExportPartitura(_Base):
    def test_sense_carpeta_de_sortida_es_rebutja(self):
        w = _finestra()
        w.sortida = ""
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_export_partitura(self.ctx(w), {})

    def test_sense_locators_es_rebutja_amb_missatge(self):
        w = _finestra()
        w.sortida = tempfile.mkdtemp()
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_export_partitura(self.ctx(w), {})

    def test_locators_vells_es_regeneren(self):
        """Bug: exportar NOMÉS la partitura reutilitzava els locators VELLS.

        La partitura es construeix a partir de `acords_locators.txt`, que és un
        DERIVAT del model. Si el CSV s'ha editat després de l'últim export de
        WAVs, els locators del disc són vells i la partitura sortia amb els
        acords antics.
        """
        w = _finestra()
        sortida = pipeline.carpeta_sortida(w.wav_edit.text().strip())
        w.sortida = sortida
        os.makedirs(sortida, exist_ok=True)
        csv_ac = os.path.join(sortida, "acords.csv")
        with open(csv_ac, "w", encoding="utf-8") as f:
            f.write("0.0,4.0,C\n")
        loc = os.path.join(sortida, "acords_locators.txt")
        with open(loc, "w", encoding="utf-8") as f:
            f.write("posició acord durada\n")
        os.utime(loc, (os.path.getmtime(csv_ac) - 60,) * 2)   # locators VELLS
        with patch.object(pipeline, "run_acords_py") as m:
            self.assertTrue(w._assegura_locators())
            m.assert_called_once()
        os.utime(loc, None)          # com si s'haguessin reescrit
        with patch.object(pipeline, "run_acords_py") as m2:
            self.assertTrue(w._assegura_locators())
            m2.assert_not_called()   # ja estan al dia → no es toca res

    def test_retorna_els_camins_generats(self):
        w = _finestra()
        w.sortida = tempfile.mkdtemp()
        fals = {"musicxml": "/x/a.musicxml", "pdf": "/x/a.pdf",
                "mscz": "/x/a.mscz"}
        with patch.object(w, "_exporta_partitura", return_value=fals):
            r = mcp_bridge._op_export_partitura(self.ctx(w), {})
        self.assertTrue(r.get("ok"))
        self.assertEqual(r.get("musicxml"), "/x/a.musicxml")
        self.assertEqual(r.get("pdf"), "/x/a.pdf")
        self.assertIn("MusicXML", r.get("missatge", ""))

    def test_no_obre_cap_finestra_ni_carpeta(self):
        w = _finestra()
        w.sortida = tempfile.mkdtemp()
        with patch.object(w, "_exporta_partitura",
                          return_value={"musicxml": "/x/a.musicxml"}), \
                patch.object(w, "obre_carpeta") as ob, \
                patch.object(QW.QMessageBox, "information") as inf:
            mcp_bridge._op_export_partitura(self.ctx(w), {})
        self.assertFalse(ob.called, "no ha d'obrir carpetes")
        self.assertFalse(inf.called, "no ha de mostrar diàlegs")


class TestExportWavAmbPartitura(_Base):
    def test_partitura_true_inclou_la_partitura_i_restaura_la_marca(self):
        w = _finestra()
        vist = {}
        with patch.object(w, "exporta", lambda: vist.update(
                durant=w.amb_part.isChecked())):
            mcp_bridge._op_export_wav(self.ctx(w), {"partitura": True})
        self.assertTrue(vist.get("durant"), "durant l'export havia d'estar ON")
        self.assertFalse(w.amb_part.isChecked(), "la marca s'ha de restaurar")

    def test_partitura_false_la_treu_nomes_durant_l_export(self):
        w = _finestra()
        w.amb_part.setChecked(True)
        vist = {}
        with patch.object(w, "exporta", lambda: vist.update(
                durant=w.amb_part.isChecked())):
            mcp_bridge._op_export_wav(self.ctx(w), {"partitura": False})
        self.assertFalse(vist.get("durant"))
        self.assertTrue(w.amb_part.isChecked(), "la marca s'ha de restaurar")

    def test_sense_el_parametre_no_toca_la_marca(self):
        w = _finestra()
        w.amb_part.setChecked(True)
        with patch.object(w, "exporta"):
            mcp_bridge._op_export_wav(self.ctx(w), {})
        self.assertTrue(w.amb_part.isChecked())



def _mcp_a4_tearDownModule():
    # Neteja ORDENADA dels objectes Qt del mòdul (evita destrucció pel GC en un
    # test posterior -> access violation intermitent). Vegeu tests/_qt_neteja.py.
    try:
        import _qt_neteja
    except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_mcp_a6.py
# ══════════════════════════════════════════════════════════════════════════
"""A6: `ac_analyze` ha de poder rebre les opcions (no només les desades).

Abans, l'MCP només podia llançar l'anàlisi amb les opcions JA desades (les del
darrer diàleg): no les podia llegir ni canviar. Ara:
- `ac_get_options` retorna les opcions actuals + els defectes;
- `ac_analyze` accepta `opcions` (per seccions/claus) per a aquesta anàlisi, i
  `desa: true` perquè també quedin guardades;
- una secció o clau desconeguda es **rebutja** (si no, s'ignoraria en silenci).
"""






def _mcp_a6___finestra():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "t.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * 3)
    w = app_main.Finestra()
    w.wav_edit.setText(wav)
    w._carrega_visor(wav)
    return w


class _mcp_a6___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QW.QApplication.instance() or QW.QApplication([])

    def ctx(self, w):
        return mcp_bridge._Context(w)


class TestGetOptions(_mcp_a6___Base):
    def test_retorna_actuals_i_defectes(self):
        w = _mcp_a6___finestra()
        r = mcp_bridge._op_get_options(self.ctx(w), {})
        self.assertIn("opcions", r)
        self.assertIn("defectes", r)
        for seccio in ("chords", "bpm", "structure", "clean"):
            self.assertIn(seccio, r["defectes"])
            self.assertIn(seccio, r["opcions"])


class TestAnalyzeAmbOpcions(_mcp_a6___Base):
    def test_aplica_les_opcions_noves(self):
        w = _mcp_a6___finestra()
        with patch.object(w, "executa") as ex:
            r = mcp_bridge._op_analyze(
                self.ctx(w), {"opcions": {"chords": {"s": 0.5}}})
        self.assertTrue(ex.called, "hauria d'haver llançat l'anàlisi")
        self.assertEqual(w.opcions["chords"]["s"], 0.5)
        self.assertEqual(r["opcions"]["chords"]["s"], 0.5)
        self.assertTrue(r["iniciat"])

    def test_no_toca_les_altres_claus(self):
        w = _mcp_a6___finestra()
        abans = copy.deepcopy(w.opcions)
        with patch.object(w, "executa"):
            mcp_bridge._op_analyze(
                self.ctx(w), {"opcions": {"clean": {"snap": False}}})
        self.assertFalse(w.opcions["clean"]["snap"])
        # la resta de la secció i les altres seccions, intactes
        self.assertEqual(w.opcions["clean"]["durada_min"],
                         abans["clean"]["durada_min"])
        self.assertEqual(w.opcions["chords"], abans["chords"])
        self.assertEqual(w.opcions["bpm"], abans["bpm"])

    def test_sense_opcions_no_canvia_res(self):
        w = _mcp_a6___finestra()
        abans = copy.deepcopy(w.opcions)
        with patch.object(w, "executa"):
            mcp_bridge._op_analyze(self.ctx(w), {})
        self.assertEqual(w.opcions, abans)

    def test_desa_les_opcions_si_es_demana(self):
        w = _mcp_a6___finestra()
        with patch.object(w, "executa"), \
                patch.object(dialegs, "desa_opcions") as d:
            mcp_bridge._op_analyze(
                self.ctx(w), {"opcions": {"structure": {"motor": "qm"}},
                              "desa": True})
        self.assertTrue(d.called, "amb desa:true s'han de guardar")

    def test_seccio_desconeguda_es_rebutja(self):
        w = _mcp_a6___finestra()
        abans = copy.deepcopy(w.opcions)
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_analyze(self.ctx(w),
                                   {"opcions": {"inventada": {"x": 1}}})
        self.assertEqual(w.opcions, abans)

    def test_clau_desconeguda_es_rebutja(self):
        w = _mcp_a6___finestra()
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_analyze(self.ctx(w),
                                   {"opcions": {"chords": {"no_existeix": 1}}})



def _mcp_a6_tearDownModule():
    # Neteja ORDENADA dels objectes Qt del mòdul (evita destrucció pel GC en un
    # test posterior -> access violation intermitent). Vegeu tests/_qt_neteja.py.
    try:
        import _qt_neteja
    except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_mcp_a7.py
# ══════════════════════════════════════════════════════════════════════════
"""A7: accions de l'app que faltaven al pont MCP.

L'MCP exposava 29 eines, però hi havia funcions de l'app sense cap eina:
metrònom, tonalitat automàtica, compàs 1 (detecció i marca manual), obrir la
carpeta de sortida i la **selecció** (inclosa la multi-selecció). Ara totes hi
són (`ac_set_metro`, `ac_set_key_detect`, `ac_detect_downbeat`,
`ac_mark_downbeat`, `ac_open_output_folder`, `ac_select_clip`,
`ac_toggle_selection`, `ac_clear_selection`, `ac_select_at_cursor`).
"""





DUR = 30.0
SECCIONS = "0.00,15.00,15.00,A,A,1,1\n15.00,30.00,15.00,B,B,1,1\n"


def _mcp_a7___finestra():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "t.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * int(44100 * DUR))
    ac = os.path.join(td, "AUTOCHORDS_t")
    os.makedirs(ac)
    with open(os.path.join(ac, "acords.csv"), "w", encoding="utf-8") as f:
        f.write("0.0,4.0,C\n4.0,10.0,Am\n10.0,10.0,G\n")
    with open(os.path.join(ac, "estructura_ABC.csv"), "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
                + SECCIONS)
    w = app_main.Finestra()
    w.wav_edit.setText(wav)
    w._carrega_visor(wav)
    return w


class _mcp_a7___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QW.QApplication.instance() or QW.QApplication([])

    def ctx(self, w):
        return mcp_bridge._Context(w)


class TestMetronom(_mcp_a7___Base):
    def test_activar_i_desactivar(self):
        w = _mcp_a7___finestra()
        v = w.visor_ref
        r = mcp_bridge._op_set_metro(self.ctx(w), {"on": True})
        self.assertTrue(v.metro_on)
        self.assertTrue(r.get("metronom"))
        self.assertTrue(w.a_metro.isChecked(), "l'acció de menú s'ha de sincronitzar")
        mcp_bridge._op_set_metro(self.ctx(w), {"on": False})
        self.assertFalse(v.metro_on)
        self.assertFalse(w.a_metro.isChecked())


class TestTonalitat(_mcp_a7___Base):
    def test_activar_la_deteccio_de_tonalitat(self):
        w = _mcp_a7___finestra()
        self.assertFalse(w.tonalitat_auto.isChecked())
        r = mcp_bridge._op_set_key_detect(self.ctx(w), {"on": True})
        self.assertTrue(w.tonalitat_auto.isChecked())
        self.assertTrue(r.get("tonalitat_automatica"))


class TestCompas1(_mcp_a7___Base):
    def test_marca_el_compas_1_al_cursor(self):
        w = _mcp_a7___finestra()
        w.visor_ref.ves_a(2.0)
        mcp_bridge._op_mark_downbeat(self.ctx(w), {})
        self.assertAlmostEqual(float(w.visor_ref.offset), 2.0, places=2)

    def test_detecta_automaticament(self):
        w = _mcp_a7___finestra()
        with patch.object(QW.QMessageBox, "information"), \
                patch.object(QW.QMessageBox, "warning"):
            mcp_bridge._op_detect_downbeat(self.ctx(w), {})
        # No ha de petar; l'estat es pot consultar sempre.
        self.assertIsNotNone(mcp_bridge._op_status(self.ctx(w), {}))


class TestCarpetaSortida(_mcp_a7___Base):
    def test_obre_la_carpeta(self):
        w = _mcp_a7___finestra()
        from PyQt5.QtGui import QDesktopServices
        with patch.object(QDesktopServices, "openUrl", return_value=True) as m:
            r = mcp_bridge._op_open_output_folder(self.ctx(w), {})
        self.assertTrue(m.called, "hauria d'obrir la carpeta")
        self.assertTrue(r.get("ok"))


class TestSeleccio(_mcp_a7___Base):
    def test_select_clip_substitueix(self):
        w = _mcp_a7___finestra()
        r = mcp_bridge._op_select_clip(self.ctx(w), {"kind": "section", "index": 1})
        self.assertIn(("section", 1), w.visor_ref.timeline.selected_keys())
        self.assertIsNotNone(r)

    def test_toggle_afegeix_a_la_multi_seleccio(self):
        w = _mcp_a7___finestra()
        c = self.ctx(w)
        mcp_bridge._op_select_clip(c, {"kind": "chord", "index": 0})
        mcp_bridge._op_toggle_selection(c, {"kind": "chord", "index": 2})
        self.assertEqual(w.visor_ref.timeline.selected_keys(),
                         {("chord", 0), ("chord", 2)})

    def test_clear_buida(self):
        w = _mcp_a7___finestra()
        c = self.ctx(w)
        mcp_bridge._op_select_clip(c, {"kind": "chord", "index": 1})
        mcp_bridge._op_clear_selection(c, {})
        self.assertEqual(w.visor_ref.timeline.selected_keys(), set())

    def test_select_at_cursor(self):
        w = _mcp_a7___finestra()
        w.visor_ref.ves_a(5.0)          # dins l'acord «Am» (4.0–10.0)
        mcp_bridge._op_select_at_cursor(self.ctx(w), {"kind": "chord"})
        self.assertIn(("chord", 1), w.visor_ref.timeline.selected_keys())

    def test_kind_invalid_es_rebutja(self):
        w = _mcp_a7___finestra()
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_select_clip(self.ctx(w), {"kind": "peix", "index": 0})



def _mcp_a7_tearDownModule():
    # Neteja ORDENADA dels objectes Qt del mòdul (evita destrucció pel GC en un
    # test posterior -> access violation intermitent). Vegeu tests/_qt_neteja.py.
    try:
        import _qt_neteja
    except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_mcp_paritat.py
# ══════════════════════════════════════════════════════════════════════════
"""Paritat d'ACCIONS MCP ↔ GUI: tot el que l'usuari pot fer, l'MCP també.

Aquí provem les eines noves del 17-10-2026 **amb la Finestra REAL** (i el seu
visor/timeline reals): porta-retalls (copiar/retallar/enganxar), esborrar/
duplicar/reanomenar la SELECCIÓ, selecció per rang i del loop, nudge, moure un
bloc d'acords, troba i reemplaça, revertir, netejar el loop, l'eina del
timeline i els commutadors d'incloure estructura/partitura.

Cap crida ha de poder obrir un diàleg modal (deixaria l'agent penjat): els
tests deixen el pont «actiu» (`mcp_actiu`) on toca i cap diàleg s'ha d'obrir.
"""




DURADA_S = 10
# C[0,2) Am[2,4) F[4,6) G[6,8) Em[8,10)
ACORDS = "0.0,2.0,C\n2.0,4.0,Am\n4.0,6.0,F\n6.0,8.0,G\n8.0,10.0,Em\n"
_mcp_paritat__SECCIONS = ("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
            "0.0,4.0,4.0,A,A,1.1,5.1\n"
            "4.0,8.0,4.0,B,B,5.1,9.1\n"
            "8.0,10.0,2.0,B,B,9.1,11.1\n")

_VIVES = []


def _mcp_paritat___ctx(w):
    return mcp_bridge._Context(w)


class _mcp_paritat___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = (app_main.QApplication.instance()
                    or app_main.QApplication([]))

    def _finestra(self, acords=ACORDS, seccions=_mcp_paritat__SECCIONS):
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "tema.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * DURADA_S)
        sortida = os.path.join(td, "AUTOCHORDS_tema")
        os.makedirs(sortida, exist_ok=True)
        with open(os.path.join(sortida, "acords.csv"), "w",
                  encoding="utf-8") as f:
            f.write(acords)
        with open(os.path.join(sortida, "estructura_ABC.csv"), "w",
                  encoding="utf-8") as f:
            f.write(seccions)
        w = app_main.Finestra()
        w.wav_edit.setText(wav)
        w._carrega_visor(wav)
        _VIVES.append(w)
        return w

    def tearDown(self):
        try:
            import _qt_neteja
        except ImportError:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import _qt_neteja
        ws, _VIVES[:] = _VIVES[:], []
        _qt_neteja.tanca_i_destrueix(*ws)

    # -- helpers -------------------------------------------------------------
    def _acords(self, w):
        return [(round(float(a[0]), 3), a[2][0]) for a in w.visor_ref.acords]

    def _selecciona(self, w, *keys):
        w.visor_ref.timeline.select_multi({(k, i) for (k, i) in keys})


class TestMapaTempo(_mcp_paritat___Base):
    """Eines MCP del MAPA de BPM/compàs (el mirall del que fa la GUI)."""

    def test_list_tempo(self):
        w = self._finestra()
        w.visor_ref.aplica_tempo_trams([(0.0, 4.0, 120.0, 4, 4),
                                        (4.0, DURADA_S, 90.0, 3, 4)])
        r = mcp_bridge._op_list_tempo(_mcp_paritat___ctx(w), {})
        self.assertEqual(len(r["trams"]), 2)
        self.assertEqual(r["trams"][1]["bpm"], 90.0)
        self.assertEqual(r["trams"][1]["bpb"], 3)
        w.close()

    def test_set_tram_tempo(self):
        w = self._finestra()
        w.visor_ref.aplica_tempo_trams([(0.0, 4.0, 120.0, 4, 4),
                                        (4.0, DURADA_S, 90.0, 3, 4)])
        mcp_bridge._op_set_tram_tempo(_mcp_paritat___ctx(w), {"index": 1, "bpm": 100.0,
                                                "bpb": 5, "beat_type": 8})
        t = w.visor_ref.tempo_trams[1]
        self.assertEqual((float(t[2]), int(t[3]), int(t[4])), (100.0, 5, 8))
        self.assertEqual(w.visor_ref.tempo_trams[0][2], 120.0)  # el 0 no es toca
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_set_tram_tempo(_mcp_paritat___ctx(w), {"index": 1, "bpm": 0})
        w.close()

    def test_afegeix_i_elimina_tall(self):
        w = self._finestra()
        w.visor_ref.aplica_tempo_trams([(0.0, DURADA_S, 120.0, 4, 4)])
        mcp_bridge._op_afegeix_tall(_mcp_paritat___ctx(w), {"t_s": 4.0})
        self.assertEqual(len(w.visor_ref.tempo_trams), 2)
        self.assertAlmostEqual(float(w.visor_ref.tempo_trams[1][0]), 4.0,
                               places=3)
        mcp_bridge._op_elimina_tall(_mcp_paritat___ctx(w), {"index": 1})
        self.assertEqual(len(w.visor_ref.tempo_trams), 1)
        w.close()

    def test_elimina_l_unic_tram_dona_error(self):
        w = self._finestra()
        w.visor_ref.aplica_tempo_trams([(0.0, DURADA_S, 120.0, 4, 4)])
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_elimina_tall(_mcp_paritat___ctx(w), {"index": 0})
        w.close()

    def test_detecta_tempo_mapa_no_obre_dialegs(self):
        """L'eina d'inferir el mapa existeix i, sense àudio, aixeca (no dialoga)."""
        w = self._finestra()
        self.assertIn("detecta_tempo_mapa", mcp_bridge.OPERACIONS)
        # Amb el WAV de la finestra, la detecció pot trigar: proven nomes que
        # l'operacio hi es i que els errors surten com a BridgeError.
        w.wav_edit.setText("")
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_detecta_tempo_mapa(_mcp_paritat___ctx(w), {})
        w.close()

    def test_mou_tall(self):
        w = self._finestra()
        w.visor_ref.aplica_tempo_trams([(0.0, 4.0, 120.0, 4, 4),
                                        (4.0, DURADA_S, 90.0, 3, 4)])
        mcp_bridge._op_mou_tall(_mcp_paritat___ctx(w), {"index": 1, "t_s": 6.0})
        self.assertAlmostEqual(float(w.visor_ref.tempo_trams[0][1]), 6.0,
                               places=3)
        w.close()


class TestPortaRetalls(_mcp_paritat___Base):
    def test_copiar_i_enganxar_sobreescriu(self):
        w = self._finestra()
        # Copiem [Am,F] (2 clips, 4 s) i enganxem a 8 s → sobreescriu el tram
        self._selecciona(w, ("chord", 1), ("chord", 2))
        mcp_bridge._op_copia_seleccio(_mcp_paritat___ctx(w), {})
        mcp_bridge._op_enganxa_seleccio(_mcp_paritat___ctx(w), {"t_s": 6.0})
        noms = [n for _t, n in self._acords(w)]
        self.assertGreaterEqual(noms.count("Am"), 1)
        w.close()

    def test_retallar_treu_la_seleccio(self):
        w = self._finestra()
        n0 = len(w.visor_ref.acords)
        self._selecciona(w, ("chord", 1), ("chord", 2))
        mcp_bridge._op_retalla_seleccio(_mcp_paritat___ctx(w), {})
        # El porta-retalls queda ple i el model ha perdut marques
        self.assertTrue(w.visor_ref.timeline.has_clipboard())
        self.assertLess(len(w.visor_ref.acords), n0)
        w.close()

    def test_enganxar_sense_porta_retalls_dona_error(self):
        w = self._finestra()
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_enganxa_seleccio(_mcp_paritat___ctx(w), {})
        w.close()

    def test_copiar_sense_seleccio_dona_error(self):
        w = self._finestra()
        w.visor_ref.timeline.clear_selection()
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_copia_seleccio(_mcp_paritat___ctx(w), {})
        w.close()


class TestSeleccioEdicio(_mcp_paritat___Base):
    def test_esborra_seleccio(self):
        w = self._finestra()
        n0 = len(w.visor_ref.acords)
        self._selecciona(w, ("chord", 1), ("chord", 2))
        mcp_bridge._op_esborra_seleccio(_mcp_paritat___ctx(w), {})
        self.assertLess(len(w.visor_ref.acords), n0)
        w.close()

    def test_duplica_seleccio(self):
        w = self._finestra()
        self._selecciona(w, ("chord", 1))
        mcp_bridge._op_duplica_seleccio(_mcp_paritat___ctx(w), {})
        # La còpia va DESPRÉS i sobreescriu (§2): el recompte pot no créixer.
        self.assertEqual([n for _t, n in self._acords(w)],
                         ["C", "Am", "Am", "G", "Em"])
        w.close()

    def test_renomena_seleccio(self):
        w = self._finestra()
        self._selecciona(w, ("chord", 1), ("chord", 2))
        mcp_bridge._op_renomena_seleccio(_mcp_paritat___ctx(w), {"nom": "CMaj7"})
        noms = [n for _t, n in self._acords(w)]
        self.assertEqual(noms.count("CMaj7"), 2)
        w.close()

    def test_renomena_seleccio_sense_nom_dona_error(self):
        w = self._finestra()
        self._selecciona(w, ("chord", 1), ("chord", 2))
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_renomena_seleccio(_mcp_paritat___ctx(w), {})
        w.close()

    def test_selecciona_rang(self):
        w = self._finestra()
        r = mcp_bridge._op_selecciona_rang(_mcp_paritat___ctx(w), {"t0": 1.0, "t1": 5.0,
                                                     "kind": "chord"})
        idxs = sorted(i for k, i in r["seleccio"] if k == "chord")
        self.assertEqual(idxs, [1, 2])       # Am (2 s) i F (4 s)
        w.close()

    def test_selecciona_loop(self):
        w = self._finestra()
        vr = w.visor_ref
        vr.ves_a(2.0)
        mcp_bridge._op_mark_loop_a(_mcp_paritat___ctx(w), {})
        vr.ves_a(6.0)
        mcp_bridge._op_mark_loop_b(_mcp_paritat___ctx(w), {})
        r = mcp_bridge._op_selecciona_loop(_mcp_paritat___ctx(w), {})
        self.assertTrue(r["seleccio"])
        w.close()

    def test_selecciona_loop_sense_loop_dona_error(self):
        w = self._finestra()
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_selecciona_loop(_mcp_paritat___ctx(w), {})
        w.close()


class TestEdicioFina(_mcp_paritat___Base):
    def test_nudge_mou_la_vora(self):
        w = self._finestra()
        vr = w.visor_ref
        vr.timeline.select_clip("chord", 1)          # Am @ 2.0
        t0 = float(vr.acords[1][0])
        mcp_bridge._op_nudge(_mcp_paritat___ctx(w), {"direccio": "dreta", "pas": 0.5})
        self.assertAlmostEqual(float(vr.acords[1][0]), t0 + 0.5, places=3)
        w.close()

    def test_nudge_sense_seleccio_dona_error(self):
        w = self._finestra()
        w.visor_ref.timeline.clear_selection()
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_nudge(_mcp_paritat___ctx(w), {"direccio": "dreta"})
        w.close()

    def test_mou_bloc_preserva_durada_i_sobreescriu(self):
        w = self._finestra()
        # bloc [Am,F] (2 clips, 4 s) +2 s → C@0 Am@4 F@6 Em@8 (G eliminat)
        self._selecciona(w, ("chord", 1), ("chord", 2))
        mcp_bridge._op_mou_bloc(_mcp_paritat___ctx(w), {"dt_s": 2.0})
        self.assertEqual(self._acords(w),
                         [(0.0, "C"), (4.0, "Am"), (6.0, "F"), (8.0, "Em")])
        w.close()

    def test_mou_bloc_endarrere(self):
        w = self._finestra()
        self._selecciona(w, ("chord", 2), ("chord", 3))   # bloc [F,G] −2 s
        mcp_bridge._op_mou_bloc(_mcp_paritat___ctx(w), {"dt_s": -2.0})
        self.assertEqual(self._acords(w),
                         [(0.0, "C"), (2.0, "F"), (4.0, "G"), (6.0, "Em")])
        w.close()

    def test_troba_i_reemplaca(self):
        w = self._finestra()
        r = mcp_bridge._op_troba_i_reemplaca(
            _mcp_paritat___ctx(w), {"camp": "acords", "troba": "Am", "reemplaca": "A-"})
        self.assertEqual(r["substituits"], 1)
        self.assertIn("A-", [n for _t, n in self._acords(w)])
        w.close()

    def test_troba_i_reemplaca_estructura(self):
        w = self._finestra()
        r = mcp_bridge._op_troba_i_reemplaca(
            _mcp_paritat___ctx(w), {"camp": "estructura", "troba": "B", "reemplaca": "Est"})
        self.assertGreaterEqual(r["substituits"], 1)
        w.close()


class TestVistaIOpcions(_mcp_paritat___Base):
    def test_neteja_loop(self):
        w = self._finestra()
        vr = w.visor_ref
        vr.ves_a(1.0)
        mcp_bridge._op_mark_loop_a(_mcp_paritat___ctx(w), {})
        vr.ves_a(5.0)
        mcp_bridge._op_mark_loop_b(_mcp_paritat___ctx(w), {})
        mcp_bridge._op_neteja_loop(_mcp_paritat___ctx(w), {})
        r = mcp_bridge._op_status(_mcp_paritat___ctx(w), {})
        self.assertIsNone(r["transport"]["loop"]["a"])
        self.assertIsNone(r["transport"]["loop"]["b"])
        self.assertFalse(r["transport"]["loop"]["on"])
        w.close()

    def test_set_eina(self):
        w = self._finestra()
        mcp_bridge._op_set_eina(_mcp_paritat___ctx(w), {"mode": "marc"})
        self.assertTrue(w.b_eina.isChecked())
        self.assertEqual(w.visor_ref.timeline._tool, "marc")
        mcp_bridge._op_set_eina(_mcp_paritat___ctx(w), {"mode": "intel·ligent"})
        self.assertFalse(w.b_eina.isChecked())
        w.close()

    def test_set_eina_ko(self):
        w = self._finestra()
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_set_eina(_mcp_paritat___ctx(w), {"mode": "potato"})
        w.close()

    def test_set_inclou_estructura_i_partitura(self):
        w = self._finestra()
        mcp_bridge._op_set_inclou_estructura(_mcp_paritat___ctx(w), {"on": False})
        self.assertFalse(w.amb_est.isChecked())
        mcp_bridge._op_set_inclou_estructura(_mcp_paritat___ctx(w), {"on": True})
        self.assertTrue(w.amb_est.isChecked())
        mcp_bridge._op_set_inclou_partitura(_mcp_paritat___ctx(w), {"on": True})
        self.assertTrue(w.amb_part.isChecked())
        mcp_bridge._op_set_inclou_partitura(_mcp_paritat___ctx(w), {"on": False})
        self.assertFalse(w.amb_part.isChecked())
        w.close()

    def test_reverteix_no_obre_cap_dialeg_amb_pont(self):
        """Amb el pont actiu, `reverteix` no ha de demanar confirmació modal."""
        w = self._finestra()
        w.mcp_actiu = True
        r = mcp_bridge._op_reverteix(_mcp_paritat___ctx(w), {})   # no projecte → avís, no penja
        self.assertIn("projecte", r["avis"].lower())
        w.close()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_mcp_schemas.py
# ══════════════════════════════════════════════════════════════════════════
"""Paritat entre l'ESQUEMA de cada eina MCP i el que el PONT llig de debò.

Si l'esquema oferix un paràmetre que la funció del pont no llig mai, l'agent el
passa i s'ignora **en silenci** (pitjor que un error: creu que ha fet una cosa i
no l'ha feta). I a l'inrevés, un paràmetre que el pont necessita i l'esquema no
declara fa que l'eina sempre peta.

Es comprova estàticament sobre el codi font del pont (auditoria 18-10-2026: les
74 eines estaven en paritat).
"""



ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Ajudes del pont que lliguen un paràmetre sense dir-ne el nom literal.
AJUDES = {"_kind_opt": {"kind", "tipus"}}


def _fonts_del_pont():
    ruta = os.path.join(ARREL, "app", "mcp_bridge.py")
    with open(ruta, encoding="utf-8") as f:
        src = f.read()
    return {n.name: ast.get_source_segment(src, n)
            for n in ast.parse(src).body if isinstance(n, ast.FunctionDef)}


def _llegeix(cos):
    """Noms de paràmetre que la funció llig de `params`."""
    noms = set()
    noms |= set(re.findall(r'params\.get\(\s*"([a-z_0-9]+)"', cos))
    noms |= set(re.findall(r'params\[\s*"([a-z_0-9]+)"\s*\]', cos))
    noms |= set(re.findall(r'"([a-z_0-9]+)"\s+in\s+params', cos))
    for m in re.finditer(r'_\w+\(\s*params\s*,\s*([^)]*)\)', cos):
        noms |= set(re.findall(r'"([a-z_0-9]+)"', m.group(1)))
    for ajuda, claus in AJUDES.items():
        if re.search(re.escape(ajuda) + r"\(\s*params", cos):
            noms |= claus
    return noms


class TestEsquemesMCP(unittest.TestCase):

    def test_cada_eina_te_la_seua_funcio_al_pont(self):
        funcs = _fonts_del_pont()
        for nom, op, _d, _p in srv._TOOLS:
            self.assertIn("_op_" + op, funcs,
                          f"{nom}: falta `_op_{op}` al pont")

    def test_l_esquema_i_el_pont_parlen_dels_mateixos_parametres(self):
        funcs = _fonts_del_pont()
        for nom, op, _d, props in srv._TOOLS:
            cos = funcs.get("_op_" + op)
            if cos is None:
                continue                       # ja ho diu el test anterior
            ignorats = set(props) - _llegeix(cos)
            self.assertEqual(ignorats, set(),
                             f"{nom}: l'esquema oferix {sorted(ignorats)} i el "
                             f"pont no els llig (s'ignorarien en silenci)")

    def test_totes_les_eines_tenen_descripcio_i_esquema_objecte(self):
        for nom, _op, desc, props in srv._TOOLS:
            self.assertTrue(desc and desc.strip(), f"{nom}: sense descripció")
            self.assertIsInstance(props, dict, f"{nom}: esquema no és dict")

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_endpoint_pont.py
# ══════════════════════════════════════════════════════════════════════════
"""L'endpoint del pont MCP no pot quedar-se sense fitxer mentre l'app és viva.

Troballa OC-6/378: `PROJECT_ROOT/temp/mcp_bridge.json` desapareixia amb l'app i
el socket **vius** → MCP inutilitzable.

**Causa arrel**: un altre procés (un **test** que cridava `activa_pont` sense
redirigir `ENDPOINT_PATH`) sobreescrivia l'endpoint amb el **seu** pid i, en
tancar-se, l'esborrava (el `_esborra_endpoint` només esborra el que és seu → el
seu era el que havia escrit). L'app viva quedava òrfena d'endpoint.

Proteccions:
1. `_escriu_endpoint` **no sobreescriu** l'endpoint d'un altre procés **viu**.
2. `_revisa_endpoint` (QTimer de 15 s) el **reescriu** si ha desaparegut.
"""






class _endpoint_pont___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QW.QApplication.instance() or QW.QApplication([])

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.path = os.path.join(self._tmp, "mcp_bridge.json")
        self._pat = patch.object(mcp_bridge, "ENDPOINT_PATH", self.path)
        self._pat.start()

    def tearDown(self):
        self._pat.stop()

    def _dades(self):
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)


class TestProteccioEscriptura(_endpoint_pont___Base):
    def test_no_sobreescriu_l_endpoint_d_un_altre_proces_viu(self):
        # Un procés VIU que no és nostre: el PARE (getppid). Abans s'usava el
        # pid 1, que a Linux/init sempre hi és però a Windows NO existeix (i
        # allà `os.kill` no és una sonda) → el test fallava només a Windows.
        alien = os.getppid()
        if alien <= 0 or alien == os.getpid():
            self.skipTest("sense un procés pare vàlid per fer d'aliè")
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"port": 9999, "token": "aliena", "pid": alien}, f)
        w = QW.QWidget()
        p = mcp_bridge.PontMCP(w)
        try:
            d = self._dades()
            self.assertEqual(d["pid"], alien, "ha sobreescrit un endpoint aliè viu!")
            self.assertEqual(d["token"], "aliena")
            self.assertEqual(p._endpoint_viu_d_algu_altre(), alien)
            # I en tancar-se NO se l'ha d'endur (no és seu).
            p.tanca()
            self.assertTrue(os.path.isfile(self.path),
                            "tanca() s'ha emportat un endpoint aliè")
        finally:
            p.tanca()

    def test_recicla_l_endpoint_d_un_proces_mort(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"port": 9999, "token": "vella", "pid": 999999}, f)
        w = QW.QWidget()
        p = mcp_bridge.PontMCP(w)
        try:
            if p._actiu:
                self.assertEqual(self._dades()["pid"], os.getpid(),
                                 "un endpoint de procés mort s'ha de reciclar")
        finally:
            p.tanca()


class TestVigilancia(_endpoint_pont___Base):
    def test_reescriu_l_endpoint_si_desapareix(self):
        w = QW.QWidget()
        p = mcp_bridge.PontMCP(w)
        self.assertTrue(p._actiu, "el pont no s'ha pogut obrir")
        self.assertTrue(os.path.isfile(self.path))
        os.unlink(self.path)                  # actor extern
        self.assertFalse(os.path.isfile(self.path))
        p._revisa_endpoint()                  # el que fa el QTimer
        self.assertTrue(os.path.isfile(self.path),
                        "no s'ha reescrit l'endpoint desaparegut")
        self.assertEqual(self._dades()["pid"], os.getpid())
        self.assertEqual(self._dades()["port"], p._port)
        p.tanca()

    def test_el_timer_de_vigilancia_es_actiu_i_es_para(self):
        w = QW.QWidget()
        p = mcp_bridge.PontMCP(w)
        self.assertTrue(p._timer_endpoint.isActive())
        p.tanca()
        self.assertFalse(p._timer_endpoint.isActive())

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_avis_no_modal.py
# ══════════════════════════════════════════════════════════════════════════
"""Els avisos de l'app NO poden encallar el pont MCP.

Bug (OC-6/367, nota a): l'export i l'analitza mostren un `QMessageBox` **modal**
que bloqueja el fil de Qt fins que algú el tanca. Si l'acció la dispara una
crida MCP (p. ex. `ac_export_wav`), el pont queda **encallat** i l'agent no rep
mai la resposta.

Fix: `main.Finestra._avis()` — amb el pont actiu (`w.mcp_actiu`, que posa
`mcp_bridge.activa_pont`) l'avís s'ensenya **no modal**, s'auto-tanca al cap de
10 s i el text queda a `ultim_avis` perquè el pont el retorni. Sense pont, el
comportament és el de sempre (modal).
"""





_avis_no_modal___VIVES = []     # finestres creades pel test: es tanquen al tearDown


def _avis_no_modal___finestra():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "t.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * 5)
    f = app_main.Finestra()
    f.wav_edit.setText(wav)
    f._carrega_visor(wav)
    _avis_no_modal___VIVES.append(f)
    return f


class _avis_no_modal___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QW.QApplication.instance() or QW.QApplication([])

    def setUp(self):
        # Cap test ensenya un QMessageBox de veritat (els que volen veure'l
        # el sobreescriuen amb el seu propi patch).
        p = patch.object(QW.QMessageBox, "show", lambda self: None)
        p.start()
        self.addCleanup(p.stop)

    def tearDown(self):
        # Destrucció ORDENADA (closeEvent) + flush FORÇAT (DeferredDelete + GC):
        # `deleteLater()` sol no n'hi ha prou sense event loop (Qt 5).
        try:
            import _qt_neteja
        except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
            import os as _os, sys as _sys
            _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
            import _qt_neteja
        ws = _avis_no_modal___VIVES[:]
        _avis_no_modal___VIVES.clear()
        _qt_neteja.tanca_i_destrueix(*ws)


class TestAvisSensePont(_avis_no_modal___Base):
    def test_sense_pont_es_modal_com_sempre(self):
        w = _avis_no_modal___finestra()
        with patch.object(QW.QMessageBox, "warning") as m:
            w.avisa("Títol", "missatge")
        self.assertTrue(m.called, "sense pont ha de ser modal (de sempre)")
        self.assertEqual(w.ultim_avis, "missatge")


class TestAvisAmbPont(_avis_no_modal___Base):
    def test_amb_pont_no_es_modal_i_queda_registrat(self):
        w = _avis_no_modal___finestra()
        w.mcp_actiu = True
        vist = {}
        with patch.object(QW.QMessageBox, "warning") as modal, \
                patch.object(QW.QMessageBox, "show",
                             lambda self: vist.update(box=self)):
            w.avisa("Títol", "missatge")
        self.assertFalse(modal.called, "amb el pont NO hi pot haver modal")
        self.assertEqual(w.ultim_avis, "missatge")
        self.assertIn("box", vist, "s'hauria d'haver ensenyat (no modal)")
        self.assertEqual(vist["box"].windowModality(), Qt.NonModal)

    def test_activa_pont_marca_mcp_actiu(self):
        """⚠️ Cal redirigir ENDPOINT_PATH: si no, la prova escriuria (i en
        tancar-se esborraria) l'endpoint REAL de l'app viva → MCP inutilitzable.
        Va passar de veritat (OC-6/378): aquest test n'era la causa."""
        w = _avis_no_modal___finestra()
        self.assertFalse(w.mcp_actiu)
        tmp = tempfile.mkdtemp()
        with patch.object(mcp_bridge, "ENDPOINT_PATH",
                          os.path.join(tmp, "mcp_bridge.json")):
            pont = mcp_bridge.activa_pont(w)
            self.assertTrue(w.mcp_actiu,
                            "activar el pont ha de desactivar els modals")
            if pont is not None:
                pont.tanca()


class TestExportMCPNoBloqueja(_avis_no_modal___Base):
    def test_l_export_amb_pont_torna_i_reporta_l_avis(self):
        """Si l'export vol avisar, la crida MCP TORNA (no s'encalla) i l'avís
        arriba a l'agent."""
        w = _avis_no_modal___finestra()
        w.mcp_actiu = True
        ctx = mcp_bridge._Context(w)
        # Roadmap §14.1: en obrir la WAV el model ja neix amb 1 acord + 1
        # secció, així que l'export SÍ que s'executa (el simulem). El que
        # guarda aquest test és que la crida MCP TORNA i no obre res.
        with patch.object(QW.QMessageBox, "warning") as modal, \
                patch.object(pipeline, "exporta_total", return_value={}), \
                patch.object(w, "obre_carpeta") as obre:
            r = mcp_bridge._op_export_wav(ctx, {})
        self.assertFalse(obre.called, "no ha d'obrir cap carpeta")
        self.assertFalse(modal.called, "no pot haver-hi modal amb el pont")
        self.assertTrue(r.get("ok"))
        self.assertIn("avis", r, "l'avís hauria d'arribar a l'agent")

    def test_el_status_mostra_el_darrer_avis(self):
        w = _avis_no_modal___finestra()
        w.mcp_actiu = True
        w.avisa("Títol", "avís de prova")
        r = mcp_bridge._op_status(mcp_bridge._Context(w), {})
        self.assertEqual(r.get("avis"), "avís de prova")

    def test_el_status_consumeix_lavis(self):
        """L'avís es retorna UN COP: si no, seria «persistent» (OC-6/415)."""
        w = _avis_no_modal___finestra()
        w.mcp_actiu = True
        w.avisa("Títol", "avís de prova")
        ctx = mcp_bridge._Context(w)
        self.assertEqual(mcp_bridge._op_status(ctx, {}).get("avis"),
                         "avís de prova")
        self.assertEqual(mcp_bridge._op_status(ctx, {}).get("avis", ""), "",
                         "un avís vell no es pot repetir a cada status")



def _avis_no_modal_tearDownModule():
    # Neteja ORDENADA dels objectes Qt del mòdul (evita destrucció pel GC en un
    # test posterior -> access violation intermitent). Vegeu tests/_qt_neteja.py.
    try:
        import _qt_neteja
    except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()


if __name__ == "__main__":   # pragma: no cover
    unittest.main()
