"""Diàleg conjunt de talls QM."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication  # noqa: E402

from app.dialeg_tall_qm import DialegTallQM  # noqa: E402
from app import mapa_tempo  # noqa: E402


def _opcions():
    clip = mapa_tempo.TramMapa(0.0, 1.0, 120.0, "normal", "4/4", "", 1,
                               "negra")
    return [
        {"etiqueta": "4/4 N=1 (120.000)", "clips": [clip]},
        {"etiqueta": "4/4 N=2 (120.000)", "clips": [clip]},
    ]


class TestDialegTallQM(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_sense_preseleccio_fins_triar_les_dos(self):
        d = DialegTallQM(None, _opcions(), _opcions())
        ok = d._botons.button(d._botons.Ok)
        self.assertFalse(ok.isEnabled())
        self.assertEqual(d._lista_esq.currentRow(), -1)
        self.assertEqual(d._lista_dreta.currentRow(), -1)
        d._lista_esq.setCurrentRow(0)
        self.assertFalse(ok.isEnabled())
        d._lista_dreta.setCurrentRow(1)
        self.assertTrue(ok.isEnabled())
        self.assertEqual(d.seleccions(), (0, 1))
        d.close()

    def test_costat_fix(self):
        d = DialegTallQM(None, _opcions(), _opcions()[:1])
        self.assertIsNone(d._lista_dreta)
        ok = d._botons.button(d._botons.Ok)
        self.assertFalse(ok.isEnabled())
        d._lista_esq.setCurrentRow(0)
        self.assertTrue(ok.isEnabled())
        self.assertEqual(d.seleccions(), (0, 0))
        d.close()


if __name__ == "__main__":
    unittest.main()
