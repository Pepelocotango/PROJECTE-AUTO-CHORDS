"""`ac_export_wav` ha de dir `ok: false` quan l'export FALLA (OC-6/386).

Abans retornava `ok: true` SEMPRE, també quan l'export petava (p. ex. amb 0
acords): l'agent creia que s'havia exportat. Ara, si l'export falla, `ok` és
fals i s'hi afegeix el motiu (`error`), a més de l'avís de l'app.
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
from app import pipeline  # noqa: E402


def _finestra():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "t.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * 3)
    s = pipeline.carpeta_sortida(wav)
    os.makedirs(s, exist_ok=True)
    with open(os.path.join(s, "acords.csv"), "w", encoding="utf-8") as f:
        f.write("0.0,C\n2.0,Am\n")
    w = app_main.Finestra()
    w.wav_edit.setText(wav)
    w._carrega_visor(wav)
    w.mcp_actiu = True          # avisos no-modals (no ha de bloquejar el test)
    return w


class TestOkFalsEnFallar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QW.QApplication.instance() or QW.QApplication([])

    def setUp(self):
        # Cap QMessageBox REAL: mostrar-lo amb el pont MCP actiu fa «access
        # violation» a Windows (crash natiu; CI run #14). Vegeu test_avis_no_modal.
        p = patch.object(QW.QMessageBox, "show", lambda self: None)
        p.start()
        self.addCleanup(p.stop)

    def test_export_que_falla_retorna_ok_false(self):
        w = _finestra()
        with patch.object(pipeline, "exporta_total",
                          side_effect=RuntimeError("no hi ha acords")), \
                patch.object(w, "obre_carpeta"):
            r = mcp_bridge._op_export_wav(mcp_bridge._Context(w), {})
        self.assertFalse(r.get("ok"), f"hauria de ser ok:false → {r}")
        self.assertIn("no hi ha acords", r.get("error", ""))
        w.close()

    def test_export_bo_retorna_ok_true(self):
        w = _finestra()
        with patch.object(pipeline, "exporta_total", return_value={}), \
                patch.object(w, "obre_carpeta"):
            r = mcp_bridge._op_export_wav(mcp_bridge._Context(w), {})
        self.assertTrue(r.get("ok"), f"hauria de ser ok:true → {r}")
        self.assertNotIn("error", r)
        w.close()

    def test_async_que_falla_tambe_ho_diu(self):
        w = _finestra()
        with patch.object(pipeline, "exporta_total",
                          side_effect=RuntimeError("boom")), \
                patch.object(w, "obre_carpeta"):
            mcp_bridge._op_export_wav(mcp_bridge._Context(w), {"async": True})
            w.feina_export.wait(8000)
            for _ in range(20):
                self._app.processEvents()
        self.assertEqual(w.exporta_error, "boom")
        w.close()



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
