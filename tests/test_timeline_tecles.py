"""Tecles del timeline (`TimelineView.keyPressEvent`).

Les dreceres del timeline són el que fa l'app «de DAW», però es proven totes
**indirectament** (el nudge pel seu efecte, el porta-retalls pel resultat) i les
que només emeten un senyal (`Space` → play, `Esc`) no les mirava ningú: si un
refactor se les menjava, la suite quedava verda i el teclat deixava de funcionar
(auditoria 18-10-2026).
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
from PyQt5.QtCore import QEvent, Qt  # noqa: E402
from PyQt5.QtGui import QKeyEvent  # noqa: E402

from app import visor as visor_mod  # noqa: E402

ACORDS = "0.0,4.0,C\n4.0,10.0,G\n"


def _visor():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "t.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * 10)
    out = os.path.join(td, "AUTOCHORDS_t")
    os.makedirs(out)
    ca = os.path.join(out, "acords.csv")
    with open(ca, "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,acord\n" + ACORDS)
    v = visor_mod.Visor(wav, ca, None, bpm=120, bpb=4, tempo_fix=True)
    v.td, v.sortida = td, out
    return v


def _tecla(key, mods=Qt.NoModifier):
    return QKeyEvent(QEvent.KeyPress, key, mods)


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])


class TestTeclesTimeline(_Base):

    def test_space_emet_play(self):
        v = _visor()
        self.addCleanup(v.close)
        # El visor connecta `playRequested` al reproductor REAL: el desconnectem
        # perquè aquest test provinga NOMÉS el senyal (res d'àudio als tests).
        try:
            v.timeline.playRequested.disconnect(v.play_stop)
        except (TypeError, RuntimeError):
            pass
        hits = []
        v.timeline.playRequested.connect(lambda: hits.append(1))
        v.timeline.keyPressEvent(_tecla(Qt.Key_Space))
        self.assertEqual(len(hits), 1, "Space ha d'emetre playRequested")

    def test_escape_emet_escape_pressed(self):
        v = _visor()
        self.addCleanup(v.close)
        hits = []
        v.timeline.escapePressed.connect(lambda: hits.append(1))
        v.timeline.keyPressEvent(_tecla(Qt.Key_Escape))
        self.assertEqual(len(hits), 1, "Esc ha d'emetre escapePressed")

    def test_del_sense_seleccio_no_peta(self):
        v = _visor()
        self.addCleanup(v.close)
        v.timeline.clear_selection()
        v.timeline.keyPressEvent(_tecla(Qt.Key_Delete))   # sense selecció
        self.assertEqual([c.payload[0] for c in v.acords], ["C", "G"])

    def test_les_fletxes_sense_seleccio_no_mouen_res(self):
        v = _visor()
        self.addCleanup(v.close)
        v.timeline.clear_selection()
        abans = [float(c.ini) for c in v.acords]
        v.timeline.keyPressEvent(_tecla(Qt.Key_Left))
        v.timeline.keyPressEvent(_tecla(Qt.Key_Right))
        self.assertEqual([float(c.ini) for c in v.acords], abans)

    def test_les_tecles_amb_ctrl_no_es_menja_el_sistema(self):
        """Sense selecció, Ctrl+C/X/V no han de petar ni tocar el model."""
        v = _visor()
        self.addCleanup(v.close)
        v.timeline.clear_selection()
        abans = [(float(c.ini), c.payload[0]) for c in v.acords]
        for k in (Qt.Key_C, Qt.Key_X, Qt.Key_V):
            v.timeline.keyPressEvent(_tecla(k, Qt.ControlModifier))
        self.assertEqual([(float(c.ini), c.payload[0]) for c in v.acords],
                         abans)


if __name__ == "__main__":
    unittest.main()
