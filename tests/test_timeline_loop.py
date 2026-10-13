"""Tests de la manipulació del loop A/B (lògica pura `loop_after_drag`).

Ara el loop es pot moure/canviar inici/fi des del regle; aquesta és la part de
càlcul (límits dins la cançó, A<B, i 'move' que manté la durada).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.timeline_base import LOOP_GRAB_PX, loop_after_drag  # noqa: E402


class TestLoopAfterDrag(unittest.TestCase):
    A, B, DUR = 4.0, 10.0, 100.0

    def test_move_mante_durada_i_desplaca(self):
        # t0=5 (grab), t=8 → delta +3
        a, b = loop_after_drag("move", 8.0, 5.0, self.A, self.B, self.DUR)
        self.assertAlmostEqual(a, 7.0)
        self.assertAlmostEqual(b, 13.0)
        self.assertAlmostEqual(b - a, self.B - self.A)

    def test_move_limitat_a_l_inici(self):
        a, b = loop_after_drag("move", -50.0, 5.0, self.A, self.B, self.DUR)
        self.assertAlmostEqual(a, 0.0)
        self.assertAlmostEqual(b, self.B - self.A)

    def test_move_limitat_al_final(self):
        a, b = loop_after_drag("move", 999.0, 5.0, self.A, self.B, self.DUR)
        self.assertAlmostEqual(b, self.DUR)
        self.assertAlmostEqual(a, self.DUR - (self.B - self.A))

    def test_resize_a(self):
        a, b = loop_after_drag("a", 2.0, 0.0, self.A, self.B, self.DUR)
        self.assertAlmostEqual(a, 2.0)
        self.assertAlmostEqual(b, self.B)         # B no canvia

    def test_resize_a_no_passa_de_b(self):
        a, b = loop_after_drag("a", 50.0, 0.0, self.A, self.B, self.DUR)
        self.assertLess(a, b)
        self.assertAlmostEqual(b, self.B)
        self.assertAlmostEqual(b - a, 0.05, places=6)

    def test_resize_a_no_negatiu(self):
        a, _b = loop_after_drag("a", -5.0, 0.0, self.A, self.B, self.DUR)
        self.assertAlmostEqual(a, 0.0)

    def test_resize_b(self):
        a, b = loop_after_drag("b", 20.0, 0.0, self.A, self.B, self.DUR)
        self.assertAlmostEqual(a, self.A)         # A no canvia
        self.assertAlmostEqual(b, 20.0)

    def test_resize_b_no_passa_de_durada(self):
        _a, b = loop_after_drag("b", 999.0, 0.0, self.A, self.B, self.DUR)
        self.assertAlmostEqual(b, self.DUR)

    def test_resize_b_no_travessa_a(self):
        a, b = loop_after_drag("b", 0.0, 0.0, self.A, self.B, self.DUR)
        self.assertGreater(b, a)
        self.assertAlmostEqual(b - a, 0.05, places=6)

    def test_mode_desconegut_no_canvia(self):
        self.assertEqual(loop_after_drag("", 1.0, 0.0, self.A, self.B, self.DUR),
                         (self.A, self.B))

    def test_tolerancia_positiva(self):
        self.assertGreater(LOOP_GRAB_PX, 0)


class TestInteraccioRegle(unittest.TestCase):
    """Arrossegar de debò al regle (vores i cos) modifica el loop A/B."""

    def setUp(self):
        if not os.environ.get("DISPLAY") and not os.environ.get("QT_QPA_PLATFORM"):
            os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PyQt5.QtWidgets import QApplication
        self._qapp = QApplication.instance() or QApplication([])
        import numpy as np
        from app.timeline import TimelineView
        audio = {"durada": 60.0, "sr": 44100, "canals": 2,
                 "mono": np.zeros(2000, dtype=np.int16)}
        self.tl = TimelineView(audio, [], [], 120.0, 4, True)
        self.tl.resize(800, 400)
        self.tl.set_loop(10.0, 20.0)

    def _pt(self, t, y=10.0):
        from PyQt5.QtCore import QPointF
        return QPointF(self.tl.mapFromScene(QPointF(self.tl._loop_px(t), y)))

    def _ev(self, tipus, t, boto=None, botons=None):
        from PyQt5.QtGui import QMouseEvent
        from PyQt5.QtCore import Qt
        boto = Qt.LeftButton if boto is None else boto
        botons = Qt.LeftButton if botons is None else botons
        return QMouseEvent(tipus, self._pt(t), boto, botons, Qt.NoModifier)

    def test_hit_test(self):
        tl = self.tl
        self.assertEqual(tl._loop_mode_at(tl._loop_px(10.0)), "a")
        self.assertEqual(tl._loop_mode_at(tl._loop_px(20.0)), "b")
        self.assertEqual(tl._loop_mode_at(tl._loop_px(15.0)), "move")
        self.assertIsNone(tl._loop_mode_at(tl._loop_px(40.0)))

    def test_arrossegar_el_cos_mou_el_loop(self):
        from PyQt5.QtCore import QEvent, Qt
        tl = self.tl
        a0, b0 = tl._loop_a, tl._loop_b
        tl.mousePressEvent(self._ev(QEvent.MouseButtonPress, 15.0))
        tl.mouseMoveEvent(self._ev(QEvent.MouseMove, 19.0, Qt.NoButton,
                                   Qt.LeftButton))
        tl.mouseReleaseEvent(self._ev(QEvent.MouseButtonRelease, 19.0,
                                      Qt.LeftButton, Qt.NoButton))
        self.assertGreater(tl._loop_a, a0)                       # s'ha mogut
        self.assertAlmostEqual(tl._loop_b - tl._loop_a, b0 - a0, places=6)

    def test_arrossegar_la_vora_b_redimensiona(self):
        from PyQt5.QtCore import QEvent, Qt
        tl = self.tl
        a0 = tl._loop_a
        tl.mousePressEvent(self._ev(QEvent.MouseButtonPress, 20.0))
        tl.mouseMoveEvent(self._ev(QEvent.MouseMove, 23.0, Qt.NoButton,
                                   Qt.LeftButton))
        tl.mouseReleaseEvent(self._ev(QEvent.MouseButtonRelease, 23.0,
                                      Qt.LeftButton, Qt.NoButton))
        self.assertAlmostEqual(tl._loop_a, a0, places=6)         # A no canvia
        self.assertGreater(tl._loop_b, 20.0)                     # B s'ha mogut


if __name__ == "__main__":
    unittest.main()
