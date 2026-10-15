"""Graella configurable: interruptor de snap + divisió (1/4 · 1/8 · 1/16 …).

Amb el snap configurable, el nudge fi és possible (divisió fina) i es pot
desactivar el snap del tot. Només mou fronteres → regles d'or intactes.
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
            "0.0,10.0,10.0,A,A,1.1,5.1\n"
            "10.0,20.0,10.0,B,B,5.1,10.1\n")


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


class TestSnap(_Base):
    def test_snap_per_defecte_encaixa(self):
        v = _visor()
        v.timeline.set_snap(on=True, divisio="corxera")   # 0,25 s a 120 BPM
        self.assertAlmostEqual(v.timeline._snap(2.13), 2.25, places=6)
        v.close()

    def test_snap_off_no_encaixa(self):
        v = _visor()
        v.timeline.set_snap(on=False)
        self.assertAlmostEqual(v.timeline._snap(2.13), 2.13, places=6)
        v.close()

    def test_divisio_configura_el_pas(self):
        v = _visor()
        v.timeline.set_snap(on=True, divisio="semicorxera")   # 0,125 s
        self.assertAlmostEqual(v.timeline._pas_nudge(), 0.125, places=6)
        v.close()

    def test_nudge_fi_amb_divisio(self):
        v = _visor()
        v.timeline.set_snap(on=True, divisio="semicorxera")
        v.timeline.select_clip("chord", 1)                # Am @ 2.0
        v.timeline.keyPressEvent(_key(Qt.Key_Right))
        self.assertAlmostEqual(float(v.acords[1][0]), 2.125, places=6)
        v.close()

    def test_nudge_amb_snap_off(self):
        v = _visor()
        v.timeline.set_snap(on=False)
        pas = v.timeline._pas_nudge()
        v.timeline.select_clip("chord", 1)
        v.timeline.keyPressEvent(_key(Qt.Key_Right))
        self.assertAlmostEqual(float(v.acords[1][0]), 2.0 + pas, places=6)
        v.close()

    def test_divisio_en_compassos(self):
        v = _visor()                                   # 120 BPM, 4/4 → compàs 2 s
        for divisio, esperat in (("compas1", 2.0), ("compas4", 8.0),
                                 ("compas8", 16.0), ("compas16", 32.0)):
            v.timeline.set_snap(on=True, divisio=divisio)
            self.assertAlmostEqual(v.timeline._pas_nudge(), esperat, places=6,
                                   msg=divisio)
        v.close()

    def test_cursor_segueix_snap(self):
        """Amb snap actiu, el cursor s'encaixa a la graella (en clicar/moure'l)."""
        v = _visor()
        v.timeline.set_snap(on=True, divisio="compas1")   # 2 s
        v.timeline.set_position(3.3)                      # → cel·la més propera
        self.assertAlmostEqual(v.timeline.get_position(), 4.0, places=6)
        # snap=False (reproducció/looop) → posició exacta
        v.timeline.set_position(3.3, snap=False)
        self.assertAlmostEqual(v.timeline.get_position(), 3.3, places=6)
        v.close()

    def test_cursor_snap_off_no_encaixa(self):
        v = _visor()
        v.timeline.set_snap(on=False)
        v.timeline.set_position(3.3)
        self.assertAlmostEqual(v.timeline.get_position(), 3.3, places=6)
        v.close()

    def test_ves_a_es_una_cerca_exacta(self):
        """Les cerques programàtiques (barra/llistes/MCP) NO s'encaixen."""
        v = _visor()
        v.timeline.set_snap(on=True, divisio="compas1")
        v.ves_a(3.3)
        self.assertAlmostEqual(v.pos, 3.3, places=6)
        v.close()

    def test_visor_reenvia_set_snap(self):
        v = _visor()
        v.set_snap(on=False, divisio="negra")
        self.assertFalse(v.timeline._snap_on)
        self.assertEqual(v.timeline._snap_div_nom, "negra")
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
