"""Tests de l'avís de re-anàlisi.

En tornar a prémer «Analitza» amb resultats ja presents, l'app ha d'avisar que
sobreviurà el resultat actual (i les edicions manuals) i que no es pot desfer.
Aquí comprovem la DECISIÓ de quan cal avisar (`_hi_ha_resultats` /
`_confirma_reanalisi`); el diàleg en si és de la GUI.
"""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import Finestra  # noqa: E402


def _win(visor):
    return types.SimpleNamespace(visor_ref=visor)


def _visor(acords=(), seccions=()):
    return types.SimpleNamespace(acords=list(acords), seccions=list(seccions))


class TestHiHaResultats(unittest.TestCase):
    def test_sense_visor(self):
        self.assertFalse(Finestra._hi_ha_resultats(_win(None)))

    def test_visor_buit(self):
        # primera anàlisi d'un WAV nou: no hi ha res a perdre
        self.assertFalse(Finestra._hi_ha_resultats(_win(_visor())))

    def test_amb_acords(self):
        self.assertTrue(Finestra._hi_ha_resultats(
            _win(_visor(acords=[(0.0, "N", "0.000000000")]))))

    def test_amb_seccions(self):
        self.assertTrue(Finestra._hi_ha_resultats(
            _win(_visor(seccions=[(0.0, 4.0, "A", "A")]))))

    def test_visor_sense_atributs(self):
        # no ha de petar si el visor no té els atributs
        self.assertFalse(Finestra._hi_ha_resultats(
            _win(types.SimpleNamespace())))


class TestConfirmaReanalisi(unittest.TestCase):
    def setUp(self):
        if not os.environ.get("DISPLAY") and not os.environ.get("QT_QPA_PLATFORM"):
            os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PyQt5.QtWidgets import QApplication
        self._qapp = QApplication.instance() or QApplication([])

    def test_sense_resultats_continua_sense_dialeg(self):
        # sense resultats, ha de retornar True SENSE mostrar cap avís
        w = Finestra()
        w.visor_ref = None
        self.assertTrue(w._confirma_reanalisi())



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
