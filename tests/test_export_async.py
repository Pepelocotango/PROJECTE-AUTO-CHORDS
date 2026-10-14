"""A5: export ASÍNCRON (l'export pot trigar i no ha de bloquejar res).

Fet al fil de la UI, l'export congelava la finestra i —si venia d'una crida
MCP— deixava el pont sense resposta fins al final (síncrona opaca). Ara
`exporta_async()` el fa en un fil (`FeinaExporta`), amb el progrés a la barra i
a `ac_status` (`exportant`), i `ac_export_wav` accepta `async: true`.
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
    # Amb el pont actiu els avisos són NO modals: així el test no es queda
    # esperant un clic (i és el cas realista: l'export sol venir de l'MCP).
    w.mcp_actiu = True
    return w


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QW.QApplication.instance() or QW.QApplication([])

    def ctx(self, w):
        return mcp_bridge._Context(w)

    def _espera(self, w, ms=8000):
        w.feina_export.wait(ms)
        for _ in range(20):                  # deixa arribar el senyal `feta`
            self._app.processEvents()


class TestExportAsync(_Base):
    def test_arrenca_i_acaba(self):
        w = _finestra()
        with patch.object(pipeline, "exporta_total", return_value={}), \
                patch.object(w, "obre_carpeta"):
            self.assertTrue(w.exporta_async())
            self.assertTrue(w.exportant, "mentre corre ha de constar com a tal")
            self._espera(w)
        self.assertFalse(w.exportant, "en acabar ha de quedar a False")
        self.assertIn("Exportació feta", w.log.toPlainText())
        w.close()

    def test_no_arrenca_dues_vegades(self):
        w = _finestra()
        import time as _t
        with patch.object(pipeline, "exporta_total",
                          side_effect=lambda **k: _t.sleep(0.3)), \
                patch.object(w, "obre_carpeta"):
            self.assertTrue(w.exporta_async())
            self.assertFalse(w.exporta_async(), "no pot arrencar-ne dos")
            self._espera(w)
        w.close()

    def test_error_al_fil_avisa(self):
        w = _finestra()
        with patch.object(pipeline, "exporta_total",
                          side_effect=RuntimeError("boom")), \
                patch.object(w, "obre_carpeta"):
            self.assertTrue(w.exporta_async())
            self._espera(w)
        self.assertFalse(w.exportant)
        self.assertIn("boom", w.log.toPlainText())
        w.close()


class TestExportAsyncMCP(_Base):
    def test_ac_export_wav_async_torna_de_seguida(self):
        w = _finestra()
        import time as _t
        with patch.object(pipeline, "exporta_total",
                          side_effect=lambda **k: _t.sleep(0.3)), \
                patch.object(w, "obre_carpeta"):
            r = mcp_bridge._op_export_wav(self.ctx(w), {"async": True})
            self.assertTrue(r.get("iniciat"))
            st = mcp_bridge._op_status(self.ctx(w), {})
            self.assertTrue(st.get("exportant"), "l'estat ha de dir que exporta")
            self._espera(w)
        st2 = mcp_bridge._op_status(self.ctx(w), {})
        self.assertFalse(st2.get("exportant"))
        w.close()

    def test_async_sense_wav_es_rebutja(self):
        w = _finestra()
        w.wav_edit.setText("")
        w.sortida = ""
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_export_wav(self.ctx(w), {"async": True})
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
