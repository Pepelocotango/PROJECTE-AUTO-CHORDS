"""A6: `ac_analyze` ha de poder rebre les opcions (no només les desades).

Abans, l'MCP només podia llançar l'anàlisi amb les opcions JA desades (les del
darrer diàleg): no les podia llegir ni canviar. Ara:
- `ac_get_options` retorna les opcions actuals + els defectes;
- `ac_analyze` accepta `opcions` (per seccions/claus) per a aquesta anàlisi, i
  `desa: true` perquè també quedin guardades;
- una secció o clau desconeguda es **rebutja** (si no, s'ignoraria en silenci).
"""
import copy
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from unittest.mock import patch  # noqa: E402

import PyQt5.QtWidgets as QW  # noqa: E402

from app import dialegs  # noqa: E402
from app import main as app_main  # noqa: E402
from app import mcp_bridge  # noqa: E402


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


class TestGetOptions(_Base):
    def test_retorna_actuals_i_defectes(self):
        w = _finestra()
        r = mcp_bridge._op_get_options(self.ctx(w), {})
        self.assertIn("opcions", r)
        self.assertIn("defectes", r)
        for seccio in ("chords", "bpm", "structure", "clean"):
            self.assertIn(seccio, r["defectes"])
            self.assertIn(seccio, r["opcions"])


class TestAnalyzeAmbOpcions(_Base):
    def test_aplica_les_opcions_noves(self):
        w = _finestra()
        with patch.object(w, "executa") as ex:
            r = mcp_bridge._op_analyze(
                self.ctx(w), {"opcions": {"chords": {"s": 0.5}}})
        self.assertTrue(ex.called, "hauria d'haver llançat l'anàlisi")
        self.assertEqual(w.opcions["chords"]["s"], 0.5)
        self.assertEqual(r["opcions"]["chords"]["s"], 0.5)
        self.assertTrue(r["iniciat"])

    def test_no_toca_les_altres_claus(self):
        w = _finestra()
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
        w = _finestra()
        abans = copy.deepcopy(w.opcions)
        with patch.object(w, "executa"):
            mcp_bridge._op_analyze(self.ctx(w), {})
        self.assertEqual(w.opcions, abans)

    def test_desa_les_opcions_si_es_demana(self):
        w = _finestra()
        with patch.object(w, "executa"), \
                patch.object(dialegs, "desa_opcions") as d:
            mcp_bridge._op_analyze(
                self.ctx(w), {"opcions": {"structure": {"motor": "qm"}},
                              "desa": True})
        self.assertTrue(d.called, "amb desa:true s'han de guardar")

    def test_seccio_desconeguda_es_rebutja(self):
        w = _finestra()
        abans = copy.deepcopy(w.opcions)
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_analyze(self.ctx(w),
                                   {"opcions": {"inventada": {"x": 1}}})
        self.assertEqual(w.opcions, abans)

    def test_clau_desconeguda_es_rebutja(self):
        w = _finestra()
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_analyze(self.ctx(w),
                                   {"opcions": {"chords": {"no_existeix": 1}}})



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
