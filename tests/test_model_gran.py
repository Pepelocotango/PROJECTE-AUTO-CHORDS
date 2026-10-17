"""Validació — la VISTA amb models GRANS (robustesa, no rendiment exacte).

Un model amb centenars de clips s'ha de carregar, dibuixar i permetre-hi operar
(seek, ressalta de reproducció, zoom i nudge) sense petar ni degradar-se.
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

DUR = 200.0


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])

    def _visor_gran(self, n_ac=200, n_sec=40, dur=DUR):
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "tema.wav")
        out = os.path.join(td, "AUTOCHORDS_tema")
        os.makedirs(out)
        with wave.open(wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(b"\x00\x00" * int(44100 * dur))
        patrons = ["C", "G", "Am", "F"]
        ca = os.path.join(out, "acords.csv")
        with open(ca, "w", encoding="utf-8") as f:
            for k in range(n_ac):
                f.write(f"{k:.2f},{k + 1:.2f},{patrons[k % 4]}\n")
        sa = os.path.join(out, "estructura_ABC.csv")
        with open(sa, "w", encoding="utf-8") as f:
            f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n")
            pas = dur / n_sec
            for k in range(n_sec):
                L = "ABCD"[k % 4]
                f.write(f"{k * pas:.2f},{(k + 1) * pas:.2f},{pas:.2f},{L},{L},1,1\n")
        v = visor_mod.Visor(wav, ca, sa, 120.0, 4, True)
        v.td, v.sortida = td, out
        return v


class TestModelGran(_Base):
    def test_carrega_i_les_llistes_quadren(self):
        v = self._visor_gran(200, 40)
        self.assertEqual(len(v.acords), 200)
        self.assertEqual(len(v.timeline._chord_items), 200)
        self.assertEqual(len(v.seccions), 40)
        self.assertEqual(len(v.timeline._section_items), 40)
        self.assertEqual(v.llista_ac.count(), 200)
        self.assertEqual(v.llista_ab.count(), 40)
        v.close()

    def test_operacions_amb_model_gran(self):
        v = self._visor_gran(200, 40)
        # seek + ressalta de reproducció (recorre el model)
        v.timeline.set_position(123.0, emit=False)
        v._ressalta(123.0)
        # zoom i scroll
        v.timeline.zoom_to(0.0, 50.0)
        v.timeline.zoom_to(150.0, 200.0)
        # nudge d'un clip del mig
        v.timeline.select_clip("chord", 100)
        t0 = float(v.acords[100][0])
        v.timeline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_Right, Qt.NoModifier))
        self.assertGreater(float(v.acords[100][0]), t0)
        # cobertura intacta
        self.assertAlmostEqual(float(v.acords[0][0]), 0.0, places=6)
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
