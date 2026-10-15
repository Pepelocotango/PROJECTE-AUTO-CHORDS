"""Nudge amb teclat: `←`/`→` mouen la frontera del clip seleccionat un pas de
graella. `Shift` = més fi; `Alt` = estira/encongeix (mou la vora dreta).

Una sola operació de desfer; només es mou UNA frontera → ordre i contigüitat
(regles d'or #1/#2) queden intactes.
"""
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtCore import QEvent, Qt  # noqa: E402
from PyQt5.QtGui import QKeyEvent  # noqa: E402

from app import visor as visor_mod  # noqa: E402

ACORDS = "0.0,C\n2.0,Am\n4.5,F\n7.0,G\n10.0,C\n"
SECCIONS = ("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
            "0.0,5.0,5.0,A,A,1.1,5.1\n"
            "5.0,10.0,5.0,B,B,5.1,10.1\n"
            "10.0,20.0,10.0,C,C,10.1,20.1\n")


def _visor():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "tema.wav")
    out = os.path.join(td, "AUTOCHORDS_tema")
    os.makedirs(out)
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * 20)
    ca = os.path.join(out, "acords.csv")
    sa = os.path.join(out, "estructura_ABC.csv")
    with open(ca, "w", encoding="utf-8") as f:
        f.write(ACORDS)
    with open(sa, "w", encoding="utf-8") as f:
        f.write(SECCIONS)
    v = visor_mod.Visor(wav, ca, sa, bpm=120, bpb=4, tempo_fix=True)
    v.td, v.sortida = td, out
    return v


def _key(key, mods=Qt.NoModifier):
    return QKeyEvent(QEvent.KeyPress, key, mods)


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])


class TestNudge(_Base):
    def test_acord_una_frontera_a_la_dreta(self):
        v = _visor()
        v.timeline.select_clip("chord", 1)
        pas = v.timeline._pas_nudge()
        t0 = float(v.acords[1][0])
        v.timeline.keyPressEvent(_key(Qt.Key_Right))
        self.assertAlmostEqual(float(v.acords[1][0]) - t0, pas, places=6)
        # cobertura/ordre intactes
        self.assertAlmostEqual(float(v.acords[0][0]), 0.0, places=6)
        v.close()

    def test_acord_una_frontera_a_l_esquerra(self):
        v = _visor()
        v.timeline.select_clip("chord", 2)          # F @ 4.5
        pas = v.timeline._pas_nudge()
        t0 = float(v.acords[2][0])
        v.timeline.keyPressEvent(_key(Qt.Key_Left))
        self.assertAlmostEqual(t0 - float(v.acords[2][0]), pas, places=6)
        v.close()

    def test_es_desfa_duna_sola_operacio(self):
        v = _visor()
        v.timeline.select_clip("chord", 1)
        t0 = float(v.acords[1][0])
        v.timeline.keyPressEvent(_key(Qt.Key_Right))
        self.assertEqual(len(v._undo_stack), 1)
        v.undo()
        self.assertAlmostEqual(float(v.acords[1][0]), t0, places=6)
        v.close()

    def test_alt_estira_la_vora_dreta(self):
        v = _visor()
        v.timeline.select_clip("chord", 1)          # Am @ 2 ; fi = 4.5 (inici de F)
        pas = v.timeline._pas_nudge()
        v.timeline.keyPressEvent(_key(Qt.Key_Right, Qt.AltModifier))
        self.assertAlmostEqual(float(v.acords[2][0]) - 4.5, pas, places=6)
        v.close()

    def test_seccio_nudge_la_frontera(self):
        v = _visor()
        v.timeline.select_clip("section", 1)        # B 5-10
        pas = v.timeline._pas_nudge()
        v.timeline.keyPressEvent(_key(Qt.Key_Right))
        # la frontera A/B es mou: B comença a 5+pas
        self.assertAlmostEqual(float(v.seccions[1][0]) - 5.0, pas, places=6)
        self.assertAlmostEqual(float(v.seccions[0][0]), 0.0, places=6)
        v.close()

    def test_sense_seleccio_no_canvia_res(self):
        v = _visor()
        abans = [round(float(a[0]), 6) for a in v.acords]
        v.timeline.keyPressEvent(_key(Qt.Key_Right))
        self.assertEqual([round(float(a[0]), 6) for a in v.acords], abans)
        v.close()


def tearDownModule():
    try:
        import _qt_neteja
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()


if __name__ == "__main__":
    unittest.main()
