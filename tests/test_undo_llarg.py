"""Validació — undo/redo en CADENES LLARGUES (consistència de les piles).

Després de N edicions, N desfers han de tornar EXACTAMENT a l'estat inicial, i
N refers al final; i una edició nova ha de netejar la pila de refer.
"""
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from app import visor as visor_mod  # noqa: E402

ACORDS = "0.0,2.0,C\n2.0,4.0,G\n4.0,20.0,Am\n"


def _snapshot(v):
    return [(round(float(a[0]), 6), a[1]) for a in v.acords]


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])

    def _visor(self):
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
        with open(ca, "w", encoding="utf-8") as f:
            f.write(ACORDS)
        v = visor_mod.Visor(wav, ca, None, 120.0, 4, False)
        v.td, v.sortida = td, out
        return v

    def _edita(self, v, t, nom):
        v._undo_marca()
        v.acords = v._normalitza_acords(v.acords + [(t, nom, f"{t:.9f}")])
        v._undo_commit()


class TestUndoLlarg(_Base):
    def test_40_edicions_40_desfers_40_refers(self):
        v = self._visor()
        ini = _snapshot(v)
        for k in range(40):
            self._edita(v, 6.0 + k * 0.2, "X")
        self.assertEqual(len(v.acords), len(ini) + 40)
        self.assertEqual(len(v._undo_stack), 40)
        for _ in range(40):
            v.undo()
        self.assertEqual(_snapshot(v), ini)
        self.assertEqual(len(v._undo_stack), 0)
        self.assertEqual(len(v._redo_stack), 40)
        for _ in range(40):
            v.redo()
        self.assertEqual(len(v.acords), len(ini) + 40)
        self.assertEqual(len(v._redo_stack), 0)
        v.close()

    def test_redo_es_neteja_amb_edicio_nova(self):
        v = self._visor()
        self._edita(v, 6.0, "X")
        v.undo()
        self.assertEqual(len(v._redo_stack), 1)
        self._edita(v, 8.0, "Y")          # edició nova → el refer es descarta
        self.assertEqual(len(v._redo_stack), 0)
        self.assertEqual(len(v._undo_stack), 1)
        v.close()

    def test_desfer_amb_pila_buida_no_peta(self):
        v = self._visor()
        ini = _snapshot(v)
        v.undo()
        v.redo()
        self.assertEqual(_snapshot(v), ini)
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
