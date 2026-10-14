"""Tests del pont MCP (`app/mcp_bridge.py` + `eines/mcp_auto_chords_server.py`).

⚠️ **Per què amb dobles i sense GUI**: el pont real necessita l'app viva i el
fil de Qt. Aquí provem la **lògica** (registre d'operacions, lectura de
l'estat, edició amb undo/validació i el protocol MCP) amb un `window`/`visor`
**falsos**, de manera que corre a Linux sense pantalla ni l'app oberta.

La prova real d'extrem a extrem (app oberta amb `AUTO_CHORDS_MCP.sh`) es fa a
mà; vegeu `docs/MCP_AUTO_CHORDS.md`.
"""
import importlib.util
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import mcp_bridge  # noqa: E402
from app import projecte  # noqa: E402

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
        self.acords = [(0.0, "N", "0.000000000"), (4.0, "C", "4.000000000"),
                       (8.0, "G", "8.000000000")]
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
        ordenats = sorted(items, key=lambda x: float(x[0]))
        prev = None
        for it in ordenats:
            t = float(it[0])
            if t < 0:
                raise ValueError(f"inici negatiu: {t}")
            if prev is not None and t <= prev + 1e-9:
                raise ValueError("inici duplicat/ invertit")
            prev = t
        if isinstance(items, list):
            self.acords = ordenats
        return ordenats

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
        nom = (str(nom).strip() if nom else self.acords[idx][1]) or self.acords[idx][1]
        nova = list(self.acords)
        nova[idx] = (t0, self.acords[idx][1], self.acords[idx][2])
        nova.insert(idx + 1, (t, nom, f"{t:.9f}"))
        self.acords = self._normalitza_acords(nova)
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
        nova = list(self.acords)
        del nova[j]
        self.acords = self._normalitza_acords(nova)
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
        self.assertEqual(vr.acords[1][1], "Cmaj")
        mcp_bridge._op_move_chord(_ctx(vr), {"index": 1, "t_s": 5.0})
        self.assertEqual(vr.acords[1][0], 5.0)

    def test_delete_chord(self):
        vr = _FakeVisor()
        mcp_bridge._op_delete_chord(_ctx(vr), {"index": 0})
        self.assertEqual(len(vr.acords), 2)

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
        mcp_bridge._op_delete_section(_ctx(vr), {"index": 0})
        self.assertEqual(len(vr.seccions), 2)

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
        self.assertEqual(vr.acords[2][1], "Am")

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



def tearDownModule():
    # Neteja ORDENADA dels objectes Qt del mòdul (evita destrucció pel GC en un
    # test posterior -> access violation intermitent). Vegeu tests/_qt_neteja.py.
    try:
        import _qt_neteja
    except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

if __name__ == "__main__":
    unittest.main()
