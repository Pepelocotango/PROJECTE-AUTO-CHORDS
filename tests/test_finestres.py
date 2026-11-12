"""Geometria persistent de finestres (estat local, no del projecte)."""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene: esborra els temporals en plegar

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QDialog  # noqa: E402

from app import finestres  # noqa: E402


class TestFinestres(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self._fitxer = os.path.join(self._td.name, "finestres.json")
        self._p_fitxer = patch.object(finestres, "FITXER", self._fitxer)
        self._p_activa = patch.object(finestres, "persistencia_activa",
                                      lambda: True)
        self._p_fitxer.start()
        self._p_activa.start()

    def tearDown(self):
        self._p_fitxer.stop()
        self._p_activa.stop()
        self._td.cleanup()

    def test_desa_i_restaura_la_geometria(self):
        w = QDialog()
        w.setObjectName("Prova")
        w.setGeometry(120, 90, 360, 240)
        finestres.desa(w)
        self.assertTrue(os.path.isfile(self._fitxer))

        w2 = QDialog()
        w2.setObjectName("Prova")
        self.assertTrue(finestres.restaura(w2, centra_si_falta=False))
        self.assertEqual(w2.size(), w.size())
        self.assertAlmostEqual(w2.x(), w.x(), delta=2)
        self.assertAlmostEqual(w2.y(), w.y(), delta=2)
        w2.close()

    def test_sense_geometria_es_centra(self):
        w = QDialog()
        w.setObjectName("Nou")
        with patch.object(finestres, "_centra") as centra:
            self.assertFalse(finestres.restaura(w))
        centra.assert_called_once_with(w)

    def test_offscreen_no_escriu(self):
        with patch.object(finestres, "persistencia_activa", lambda: False):
            w = QDialog()
            finestres.desa(w, "NoEscriure")
            self.assertFalse(os.path.exists(self._fitxer))
