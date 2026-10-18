"""Regressió: el botó 🔁 del transport s'ha de sincronitzar amb l'estat REAL del loop.

Bug (operador, 13-10-2026): en arrossegar el regle per crear un rang A-B, el
loop **s'activava** (el play ja feia loop) però el botó 🔁 de la barra quedava
**desactivat** → incoherent.
"""
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene dels tests: l'import té efecte (esborra els temporals en plegar)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtWidgets import QApplication  # noqa: E402

from app import main as app_main  # noqa: E402
from app import visor as visor_mod  # noqa: E402


def _wav(dur=2.0):
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "tema.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * int(44100 * dur))
    return wav


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])


class TestSenyalLoopDelVisor(_Base):
    def test_on_loop_changed_emet_senyal(self):
        v = visor_mod.Visor(_wav(), None, None, 120.0, 4, True)
        estats = []
        v.loopStateChanged.connect(estats.append)
        v._on_loop_changed(0.5, 1.5)
        self.assertEqual(estats, [True])
        self.assertTrue(v.loop_on)

    def test_set_loop_emet_l_estat_real(self):
        v = visor_mod.Visor(_wav(), None, None, 120.0, 4, True)
        estats = []
        v.loopStateChanged.connect(estats.append)
        v.set_loop(True)          # sense A/B vàlids → s'ha de revertir a OFF
        self.assertEqual(estats, [False])
        self.assertFalse(v.loop_on)


class TestBotoTransportSincronitzat(_Base):
    def test_crear_rang_activa_el_boto_i_netejar_el_desactiva(self):
        w = app_main.Finestra()
        w._carrega_visor(_wav())
        self.assertIsNotNone(w.visor_ref)
        self.assertFalse(w.tb_loop.isChecked())        # d'entrada, apagat
        # Arrossegar el regle acaba cridant exactament això:
        w.visor_ref._on_loop_changed(0.5, 1.5)
        self.assertTrue(w.tb_loop.isChecked(),
                        "el botó 🔁 hauria d'activar-se amb el rang nou")
        # I netejar el loop l'ha de tornar a apagar:
        w._neteja_loop()
        self.assertFalse(w.tb_loop.isChecked())

    def test_control_sense_connexio_el_boto_no_se_sincronitza(self):
        """Control (meta-verificació): sense la connexió del senyal el botó NO
        canvia → prova que el test de dalt cassa REALMENT aquest bug."""
        w = app_main.Finestra()
        w._carrega_visor(_wav())
        w.visor_ref.loopStateChanged.disconnect(w._on_loop_state)
        w.visor_ref._on_loop_changed(0.5, 1.5)
        self.assertTrue(w.visor_ref.loop_on)      # el loop SÍ que està actiu
        self.assertFalse(w.tb_loop.isChecked())   # ... pero el boto no ho sap



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
