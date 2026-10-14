"""Partitura SENSE MuseScore: ha de fer el fallback (només MusicXML) sense petar.

El PDF i el MSCZ depenen de MuseScore (l'app no l'inclou). Sense ell, l'export
ha de generar **igualment** el MusicXML, avisar que el PDF no s'ha fet i no
fallar mai (ni des de la GUI ni des de l'MCP).

Aquí es **mocka** `partitura.musescore_bin()` → None (com si no hi fos), en
comptes de dependre de si la màquina el té instal·lat.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from unittest.mock import patch  # noqa: E402

import PyQt5.QtWidgets as QW  # noqa: E402

from app import main as app_main  # noqa: E402
from app import mcp_bridge  # noqa: E402
from app import partitura  # noqa: E402


def _sortida_amb_locators():
    """Carpeta de sortida mínima vàlida per a la partitura (mode BPM · compàs)."""
    d = tempfile.mkdtemp()
    with open(os.path.join(d, "acords_locators.txt"), "w", encoding="utf-8") as f:
        f.write("1.1.1 Am 4\n2.1.1 C 4\n")
    with open(os.path.join(d, "estructura_ABC.csv"), "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
                "0.00,4.00,4.00,A,A,1.1,2.1\n")
    return d


class TestPartituraSenseMuseScore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QW.QApplication.instance() or QW.QApplication([])

    def test_fallback_a_nomes_musicxml(self):
        d = _sortida_amb_locators()
        logs = []
        with patch.object(partitura, "musescore_bin", return_value=None):
            res = partitura.exporta_partitura(d, log=logs.append, bpm=120.0,
                                              bpb=4)
        self.assertFalse(res.get("error"), f"no hauria de fallar: {res}")
        self.assertTrue(res.get("musicxml"), "hauria de generar el MusicXML")
        self.assertTrue(os.path.isfile(res["musicxml"]))
        self.assertIsNone(res.get("pdf"), "sense MuseScore no hi ha PDF")
        self.assertIsNone(res.get("mscz"), "sense MuseScore no hi ha MSCZ")
        self.assertTrue(any("MuseScore" in m for m in logs),
                        "hauria d'avisar que no hi ha MuseScore")

    def test_la_gui_ho_diu_clarament(self):
        w = app_main.Finestra()
        w.sortida = _sortida_amb_locators()
        # ⚠️ `main.py` fa `import partitura` (nom cru): el mòdul que ELL veu no
        # és `app.partitura` → cal patchejar el seu.
        with patch.object(app_main.partitura, "musescore_bin", return_value=None):
            res = w._exporta_partitura()
        self.assertTrue(res and res.get("musicxml"))
        msg = w._missatge_partitura(res)
        self.assertIn("MusicXML", msg)
        self.assertIn("MuseScore", msg, "ha de dir que el PDF depèn de MuseScore")
        w.close()

    def test_el_mcp_torna_ok_amb_nomes_musicxml(self):
        w = app_main.Finestra()
        w.sortida = _sortida_amb_locators()
        with patch.object(app_main.partitura, "musescore_bin", return_value=None):
            r = mcp_bridge._op_export_partitura(mcp_bridge._Context(w), {})
        self.assertTrue(r.get("ok"))
        self.assertTrue(r.get("musicxml"))
        self.assertIsNone(r.get("pdf"))
        self.assertIn("MusicXML", r.get("missatge", ""))
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
