"""(2) Amb «Inclou estructura» OFF: el MODEL mai s'esborra.

`estructura_ABC.csv` és el MODEL del projecte i **no es toca mai** (la marca
decideix què s'EXPORTA, no què es conserva). Només s'ofereixen treure les restes
de l'export anterior (`wavs_estructura/`), i **sempre amb confirmació**.
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
from app import pipeline  # noqa: E402


def _finestra(amb_estructura):
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
    # restes d'un export ANTERIOR amb estructura
    with open(os.path.join(s, "estructura_ABC.csv"), "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n")
    os.makedirs(os.path.join(s, "wavs_estructura"), exist_ok=True)
    with open(os.path.join(s, "wavs_estructura", "vella.wav"), "wb") as f:
        f.write(b"RIFF")
    w = app_main.Finestra()
    w.wav_edit.setText(wav)
    w._carrega_visor(wav)
    w.mcp_actiu = True
    w.amb_est.setChecked(amb_estructura)
    w._sortida = s
    return w, s


class TestNetejaEstructura(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QW.QApplication.instance() or QW.QApplication([])

    def setUp(self):
        # Cap QMessageBox REAL: mostrar-lo amb el pont MCP actiu fa «access
        # violation» a Windows (crash natiu; CI run #14). Vegeu test_avis_no_modal.
        p = patch.object(QW.QMessageBox, "show", lambda self: None)
        p.start()
        self.addCleanup(p.stop)

    def test_amb_la_marca_off_es_netegen_els_wavs_pero_MAI_el_model(self):
        w, s = _finestra(amb_estructura=False)
        with patch.object(pipeline, "exporta_total", return_value={}), \
                patch.object(w, "obre_carpeta"), \
                patch.object(type(w), "_ho_confirma", return_value=True):
            w.exporta()
        self.assertTrue(os.path.isfile(os.path.join(s, "estructura_ABC.csv")),
                        "el MODEL de l'estructura NO s'ha d'esborrar mai")
        self.assertFalse(os.path.isdir(os.path.join(s, "wavs_estructura")),
                         "la carpeta de wavs d'estructura vella hi és")
        self.assertIn("tret l'export anterior", w.log.toPlainText())
        w.close()

    def test_amb_la_marca_off_sense_confirmacio_no_esborra_res(self):
        w, s = _finestra(amb_estructura=False)
        with patch.object(pipeline, "exporta_total", return_value={}), \
                patch.object(w, "obre_carpeta"), \
                patch.object(type(w), "_ho_confirma", return_value=False):
            w.exporta()
        self.assertTrue(os.path.isfile(os.path.join(s, "estructura_ABC.csv")))
        self.assertTrue(os.path.isdir(os.path.join(s, "wavs_estructura")))
        self.assertIn("es conserven els derivats", w.log.toPlainText())
        w.close()

    def test_amb_pont_mcp_actiu_no_esborra_mai_res(self):
        """Amb el pont MCP actiu no es mostra cap diàleg ni s'esborra res."""
        w, s = _finestra(amb_estructura=False)   # mcp_actiu=True dins _finestra
        with patch.object(pipeline, "exporta_total", return_value={}), \
                patch.object(w, "obre_carpeta"):
            w.exporta()
        self.assertTrue(os.path.isfile(os.path.join(s, "estructura_ABC.csv")))
        self.assertTrue(os.path.isdir(os.path.join(s, "wavs_estructura")))
        w.close()

    def test_amb_la_marca_on_es_respecten(self):
        w, s = _finestra(amb_estructura=True)
        with patch.object(pipeline, "exporta_total", return_value={}), \
                patch.object(w, "obre_carpeta"):
            w.exporta()
        self.assertTrue(os.path.isfile(os.path.join(s, "estructura_ABC.csv")))
        self.assertTrue(os.path.isdir(os.path.join(s, "wavs_estructura")))
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
