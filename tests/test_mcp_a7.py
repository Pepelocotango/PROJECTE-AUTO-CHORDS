"""A7: accions de l'app que faltaven al pont MCP.

L'MCP exposava 29 eines, però hi havia funcions de l'app sense cap eina:
metrònom, tonalitat automàtica, compàs 1 (detecció i marca manual), obrir la
carpeta de sortida i la **selecció** (inclosa la multi-selecció). Ara totes hi
són (`ac_set_metro`, `ac_set_key_detect`, `ac_detect_downbeat`,
`ac_mark_downbeat`, `ac_open_output_folder`, `ac_select_clip`,
`ac_toggle_selection`, `ac_clear_selection`, `ac_select_at_cursor`).
"""
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from unittest.mock import patch  # noqa: E402

import PyQt5.QtWidgets as QW  # noqa: E402

from app import main as app_main  # noqa: E402
from app import mcp_bridge  # noqa: E402

DUR = 30.0
SECCIONS = "0.00,15.00,15.00,A,A,1,1\n15.00,30.00,15.00,B,B,1,1\n"


def _finestra():
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
        f.write("0.0,C\n4.0,Am\n10.0,G\n")
    with open(os.path.join(ac, "estructura_ABC.csv"), "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
                + SECCIONS)
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


class TestMetronom(_Base):
    def test_activar_i_desactivar(self):
        w = _finestra()
        v = w.visor_ref
        r = mcp_bridge._op_set_metro(self.ctx(w), {"on": True})
        self.assertTrue(v.metro_on)
        self.assertTrue(r.get("metronom"))
        self.assertTrue(w.a_metro.isChecked(), "l'acció de menú s'ha de sincronitzar")
        mcp_bridge._op_set_metro(self.ctx(w), {"on": False})
        self.assertFalse(v.metro_on)
        self.assertFalse(w.a_metro.isChecked())


class TestTonalitat(_Base):
    def test_activar_la_deteccio_de_tonalitat(self):
        w = _finestra()
        self.assertFalse(w.tonalitat_auto.isChecked())
        r = mcp_bridge._op_set_key_detect(self.ctx(w), {"on": True})
        self.assertTrue(w.tonalitat_auto.isChecked())
        self.assertTrue(r.get("tonalitat_automatica"))


class TestCompas1(_Base):
    def test_marca_el_compas_1_al_cursor(self):
        w = _finestra()
        w.visor_ref.ves_a(2.0)
        mcp_bridge._op_mark_downbeat(self.ctx(w), {})
        self.assertAlmostEqual(float(w.visor_ref.offset), 2.0, places=2)

    def test_detecta_automaticament(self):
        w = _finestra()
        with patch.object(QW.QMessageBox, "information"), \
                patch.object(QW.QMessageBox, "warning"):
            mcp_bridge._op_detect_downbeat(self.ctx(w), {})
        # No ha de petar; l'estat es pot consultar sempre.
        self.assertIsNotNone(mcp_bridge._op_status(self.ctx(w), {}))


class TestCarpetaSortida(_Base):
    def test_obre_la_carpeta(self):
        w = _finestra()
        from PyQt5.QtGui import QDesktopServices
        with patch.object(QDesktopServices, "openUrl", return_value=True) as m:
            r = mcp_bridge._op_open_output_folder(self.ctx(w), {})
        self.assertTrue(m.called, "hauria d'obrir la carpeta")
        self.assertTrue(r.get("ok"))


class TestSeleccio(_Base):
    def test_select_clip_substitueix(self):
        w = _finestra()
        r = mcp_bridge._op_select_clip(self.ctx(w), {"kind": "section", "index": 1})
        self.assertIn(("section", 1), w.visor_ref.timeline.selected_keys())
        self.assertIsNotNone(r)

    def test_toggle_afegeix_a_la_multi_seleccio(self):
        w = _finestra()
        c = self.ctx(w)
        mcp_bridge._op_select_clip(c, {"kind": "chord", "index": 0})
        mcp_bridge._op_toggle_selection(c, {"kind": "chord", "index": 2})
        self.assertEqual(w.visor_ref.timeline.selected_keys(),
                         {("chord", 0), ("chord", 2)})

    def test_clear_buida(self):
        w = _finestra()
        c = self.ctx(w)
        mcp_bridge._op_select_clip(c, {"kind": "chord", "index": 1})
        mcp_bridge._op_clear_selection(c, {})
        self.assertEqual(w.visor_ref.timeline.selected_keys(), set())

    def test_select_at_cursor(self):
        w = _finestra()
        w.visor_ref.ves_a(5.0)          # dins l'acord «Am» (4.0–10.0)
        mcp_bridge._op_select_at_cursor(self.ctx(w), {"kind": "chord"})
        self.assertIn(("chord", 1), w.visor_ref.timeline.selected_keys())

    def test_kind_invalid_es_rebutja(self):
        w = _finestra()
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_select_clip(self.ctx(w), {"kind": "peix", "index": 0})



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
