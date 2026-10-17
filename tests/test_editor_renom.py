"""Test de regressió: reanomenar una secció (o un acord) des de la franja
EDITOR no ha de fallar pel fet que l'inici es mostri amb 2 decimals.

Bug original: `Visor._aplica_editor` re-escrivia l'inici amb el valor ARRODONIT
que mostra l'editor (2 decimals). Com que una secció acaba EXACTAMENT on comença
la següent, reaplicar 16,63 en lloc de 16,633663 feia que la 2a secció «solapés»
la 1a → l'app rebutjava el canvi («Les seccions no poden solapar-se…») i el nom
de qualsevol secció que no fos la primera no es podia canviar mai.

Arreglament: si l'inici NO s'ha tocat (el valor de l'editor és el mateix dins
l'error d'arrodoniment de 2 decimals), es conserva el valor INTERN de precisió
completa. Mateix criteri per als acords.
"""
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from app import visor  # noqa: E402


def _wav_silenci(segons=40):
    fd, ruta = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * segons)
    return ruta


FRONTERA = 16.633663          # 28 compassos a 101 BPM (precisió interna real)


class TestEditorRenom(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def _visor(self):
        v = visor.Visor(_wav_silenci(), None, None, 101.0, 4, True)
        v.seccions = [(0.0, FRONTERA, "INTRO+RIFF", "A"),
                      (FRONTERA, 31.20, "C", "C")]
        v.timeline.set_data(v.acords, v.seccions)
        return v

    def test_renom_segona_seccio_des_de_leditor(self):
        v = self._visor()
        # l'editor mostra l'inici amb 2 decimals (com fa _actualitza_editor)
        v._ed_kind, v._ed_idx = "section", 1
        v.ed_nom.setText("NOU NOM")
        v.ed_fam.setText("C")
        v.ed_ini.setText(f"{FRONTERA:.2f}")      # -> "16.63"
        v.ed_cb.setText("8.1")
        v._aplica_editor()
        self.assertEqual(v.seccions[1][2], "NOU NOM",
                         "no s'ha pogut reanomenar la 2a secció")
        self.assertAlmostEqual(v.seccions[1][0], FRONTERA, places=5,
                               msg="l'inici s'ha arrodonit (pèrdua de precisió)")
        self.assertEqual(len(v.seccions), 2, "ha canviat el nombre de seccions")
        self.assertEqual(v.seccions[0][2], "INTRO+RIFF",
                         "la 1a secció no s'havia de tocar")

    def test_renom_segona_seccio_amb_inici_mogut_de_veritat(self):
        """Si l'inici SÍ que es canvia, s'ha de fer cas del valor nou."""
        v = self._visor()
        v._ed_kind, v._ed_idx = "section", 1
        v.ed_nom.setText("C")
        v.ed_fam.setText("C")
        v.ed_ini.setText("17.50")                # mogut de debò
        v.ed_cb.setText("")
        v._aplica_editor()
        self.assertAlmostEqual(v.seccions[1][0], 17.50, places=5,
                               msg="no s'ha aplicat l'inici nou")

    def test_renom_acord_proper_al_vei(self):
        v = self._visor()
        # El model duu la «N» de capçalera a 0 (regla d'or #4: els clips
        # cobreixen TOTA la WAV); el parell 7.13/7.144567 és el que prova
        # l'arrodoniment de l'editor. Han de distar >= 10 ms (resolució del
        # CSV): abans eren 7.13/7.134567 (4,6 ms) i arrodonien a la MATEIXA
        # fila «7.13» → col·lisió que el bug #5 ara rebutja.
        v.acords = v._valida_canvis_acords([
            (0.0, "N", "0.000000000"),
            (7.13, "A", "7.130000000"),
            (7.144567, "E-7", "7.144567000")])
        v.timeline.set_data(v.acords, v.seccions)
        v._ed_kind, v._ed_idx = "chord", 2
        v.ed_nom.setText("E7")
        v.ed_ini.setText("7.14")                 # arrodonit del valor real
        v._aplica_editor()
        self.assertEqual(v.acords[2][2][0], "E7",
                         "no s'ha pogut reanomenar l'acord")
        self.assertAlmostEqual(float(v.acords[2][0]), 7.144567, places=5)



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
