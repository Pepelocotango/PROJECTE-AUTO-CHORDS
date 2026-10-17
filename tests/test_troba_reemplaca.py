"""Troba i reemplaça: substitució GLOBAL d'un xifrat (acords) o d'una etiqueta
(estructura) a tot el tema. Exacte, una sola operació de desfer, i sense canviar
cap temps (regles d'or intactes).
"""
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from app import visor as visor_mod  # noqa: E402

ACORDS = "0.0,2.0,Cmaj7\n2.0,4.0,Am\n4.0,6.0,Cmaj7\n6.0,8.0,G\n"
SECCIONS = ("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
            "0.0,4.0,4.0,A,A,1.1,4.1\n"
            "4.0,8.0,4.0,D,D,4.1,8.1\n")


def _visor():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "tema.wav")
    out = os.path.join(td, "AUTOCHORDS_tema")
    os.makedirs(out)
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * 8)
    ca = os.path.join(out, "acords.csv")
    sa = os.path.join(out, "estructura_ABC.csv")
    with open(ca, "w", encoding="utf-8") as f:
        f.write(ACORDS)
    with open(sa, "w", encoding="utf-8") as f:
        f.write(SECCIONS)
    v = visor_mod.Visor(wav, ca, sa, bpm=120, bpb=4, tempo_fix=False)
    v.td, v.sortida = td, out
    return v


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])


class TestTrobaReemplaca(_Base):
    def test_acords_xifrat_global(self):
        v = _visor()
        n = v.troba_i_reemplaca("acords", "Cmaj7", "C9")
        self.assertEqual(n, 2)
        self.assertEqual([a[1] for a in v.acords], ["C9", "Am", "C9", "G"])
        self.assertEqual(len(v._undo_stack), 1)
        v.undo()
        self.assertEqual([a[1] for a in v.acords], ["Cmaj7", "Am", "Cmaj7", "G"])
        v.close()

    def test_exacte_no_toca_parcials(self):
        v = _visor()
        n = v.troba_i_reemplaca("acords", "A", "X")   # "Am" NO és "A"
        self.assertEqual(n, 0)
        self.assertEqual([a[1] for a in v.acords], ["Cmaj7", "Am", "Cmaj7", "G"])
        self.assertEqual(len(v._undo_stack), 0)
        v.close()

    def test_estructura_etiqueta_global(self):
        v = _visor()
        n = v.troba_i_reemplaca("estructura", "D", "estribillo")
        self.assertEqual(n, 1)
        self.assertEqual([s[2] for s in v.seccions], ["A", "estribillo"])
        self.assertEqual(v.seccions[1][3], "estribillo",
                         "la família que coincidia també es canvia")
        self.assertEqual(len(v._undo_stack), 1)
        v.undo()
        self.assertEqual([s[2] for s in v.seccions], ["A", "D"])
        v.close()

    def test_sense_canvis_no_fa_res(self):
        v = _visor()
        self.assertEqual(v.troba_i_reemplaca("acords", "Zzz", "Q"), 0)
        self.assertEqual(v.troba_i_reemplaca("estructura", "ZZ", "Y"), 0)
        self.assertEqual(len(v._undo_stack), 0)
        v.close()

    def test_camps_buits_no_fan_res(self):
        v = _visor()
        self.assertEqual(v.troba_i_reemplaca("acords", "", "C9"), 0)
        self.assertEqual(v.troba_i_reemplaca("acords", "Cmaj7", ""), 0)
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
