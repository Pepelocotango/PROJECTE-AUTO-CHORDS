"""Configuració persistent de dreceres de teclat."""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["AUTO_CHORDS_TEST"] = "1"

from PyQt5.QtCore import QEvent, Qt  # noqa: E402
from PyQt5.QtGui import QKeyEvent  # noqa: E402
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from app import config, dreceres  # noqa: E402
from app.dialeg_dreceres import DialegDreceres  # noqa: E402
from app.main import Finestra  # noqa: E402


class TestDreceres(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.td = tempfile.mkdtemp()
        self._p = patch.object(config, "DADES_DIR", self.td)
        self._p.start()
        self._vives = []

    def tearDown(self):
        self._p.stop()
        import _qt_neteja
        ws, self._vives[:] = self._vives[:], []
        for w in ws:
            w.dirty = False
        _qt_neteja.tanca_i_destrueix(*ws)

    def _finestra(self):
        f = Finestra()
        self._vives.append(f)
        return f

    def test_persistencia_i_aplicacio(self):
        f = self._finestra()
        accio = f._dreceres_cataleg["edita.copia"]["objecte"]
        self.assertEqual(accio.shortcut().toString(), "Ctrl+C")
        f._bindings["edita.copia"] = "Ctrl+Shift+C"
        f._aplica_dreceres()
        self.assertEqual(accio.shortcut().toString(), "Ctrl+Shift+C")
        self.assertEqual(f._mapa_timeline()["edita.copia"], "Ctrl+Shift+C")
        dreceres.desa(f._bindings)

        f2 = self._finestra()
        accio2 = f2._dreceres_cataleg["edita.copia"]["objecte"]
        self.assertEqual(accio2.shortcut().toString(), "Ctrl+Shift+C")

    def test_dialeg_detecta_conflictes_i_desa(self):
        f = self._finestra()
        d = DialegDreceres(f, f._cataleg_llista())
        d._editors["edita.copia"][1].setKeySequence("Ctrl+Shift+X")
        d._editors["edita.retalla"][1].setKeySequence("Ctrl+Shift+X")
        with patch.object(QMessageBox, "warning") as warn:
            d.accept()
        self.assertTrue(warn.called)
        self.assertNotEqual(d.result(), QDialog.Accepted)

        d._editors["edita.retalla"][1].setKeySequence("Ctrl+Shift+Y")
        d.accept()
        self.assertEqual(d.result(), QDialog.Accepted)
        self.assertEqual(d.bindings["edita.copia"], "Ctrl+Shift+X")
        self.assertEqual(d.bindings["edita.retalla"], "Ctrl+Shift+Y")

    def test_restaura_totes(self):
        f = self._finestra()
        d = DialegDreceres(f, f._cataleg_llista())
        d._editors["talla.plus"][1].setKeySequence("Ctrl+Alt+P")
        d._restaura_totes()
        self.assertEqual(
            d._editors["talla.plus"][1].keySequence().toString(), "+")

    def test_punt_del_numeric_es_tap_i_el_de_la_fila_no(self):
        punt = QKeyEvent(QEvent.KeyPress, Qt.Key_Period, Qt.KeypadModifier, ".")
        self.assertTrue(dreceres.coincideix("Num+.", punt))
        coma = QKeyEvent(QEvent.KeyPress, Qt.Key_Comma, Qt.KeypadModifier, ",")
        self.assertTrue(dreceres.coincideix("Num+.", coma))
        self.assertFalse(dreceres.coincideix(
            "Num+.", QKeyEvent(QEvent.KeyPress, Qt.Key_Period,
                               Qt.NoModifier, ".")))
        self.assertFalse(dreceres.coincideix(
            "Num+.", QKeyEvent(QEvent.KeyPress, Qt.Key_Period,
                               Qt.KeypadModifier | Qt.ControlModifier, ".")))

    def test_cataleg_te_el_tap_del_numeric(self):
        f = self._finestra()
        e = f._dreceres_cataleg["global.tap_numpad"]
        self.assertEqual(e["defecte"], "Num+.")
        self.assertIn("tap tempo", e["etiqueta"].lower())
        self.assertTrue(dreceres.coincideix(
            "Num+.", QKeyEvent(QEvent.KeyPress, Qt.Key_Period,
                               Qt.KeypadModifier, ".")))

    def test_equivalencies_plus_return_i_delete(self):
        plus = QKeyEvent(QEvent.KeyPress, Qt.Key_Equal, Qt.ShiftModifier)
        self.assertTrue(dreceres.coincideix("+", plus))
        plus_shift = QKeyEvent(
            QEvent.KeyPress, Qt.Key_Plus, Qt.ShiftModifier, "+")
        self.assertTrue(dreceres.coincideix("+", plus_shift))
        plus_keypad = QKeyEvent(
            QEvent.KeyPress, Qt.Key_Plus, Qt.KeypadModifier, "+")
        self.assertTrue(dreceres.coincideix("+", plus_keypad))
        self.assertFalse(dreceres.coincideix(
            "+", QKeyEvent(QEvent.KeyPress, Qt.Key_Equal,
                           Qt.NoModifier, "=")))
        self.assertFalse(dreceres.coincideix(
            "+", QKeyEvent(QEvent.KeyPress, Qt.Key_Plus,
                           Qt.ControlModifier, "+")))
        self.assertFalse(dreceres.coincideix(
            "+", QKeyEvent(QEvent.KeyPress, Qt.Key_Plus,
                           Qt.AltModifier, "+")))
        enter = QKeyEvent(QEvent.KeyPress, Qt.Key_Enter, Qt.NoModifier)
        self.assertTrue(dreceres.coincideix("Return", enter))
        ret = QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier)
        self.assertTrue(dreceres.coincideix("Enter", ret))
        back = QKeyEvent(QEvent.KeyPress, Qt.Key_Backspace, Qt.NoModifier)
        self.assertTrue(dreceres.coincideix("Del", back))
        self.assertFalse(dreceres.coincideix("", plus))


if __name__ == "__main__":
    unittest.main()
