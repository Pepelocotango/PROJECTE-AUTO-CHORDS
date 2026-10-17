"""Loop A/B: doble-clic DINS la banda del loop (a dalt) → selecciona TOT el
que hi ha a dins (acords I seccions) i deixa el cursor al final del loop, a
punt per copiar (Ctrl+C) i enganxar (Ctrl+V).

També hi ha el menú de botó dret dins del loop (copiar/retallar/enganxar).
"""
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PyQt5.QtGui import QMouseEvent  # noqa: E402
from PyQt5.QtWidgets import QMenu  # noqa: E402

from app import visor as visor_mod  # noqa: E402

ACORDS = "0.0,2.0,C\n2.0,4.5,Am\n4.5,7.0,F\n7.0,10.0,G\n10.0,20.0,C\n"
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
    v = visor_mod.Visor(wav, ca, sa, bpm=120, bpb=4, tempo_fix=False)
    v.td, v.sortida = td, out
    return v


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])

    def _x_de_temps(self, tl, t):
        return int(tl._x_offset + (float(t) - tl._view_left) * tl._pps)

    def _dobleclic(self, tl, t, y=2):
        ev = QMouseEvent(QEvent.MouseButtonDblClick,
                         QPointF(self._x_de_temps(tl, t), y),
                         Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        tl.mouseDoubleClickEvent(ev)
        return ev


class TestLoopDobleClic(_Base):
    def test_dobleclic_selecciona_tot_dins_el_loop(self):
        v = _visor()
        try:
            tl = v.timeline
            tl.resize(900, 300)
            v.loop_a, v.loop_b = 1.0, 9.0        # dins: A(0) NO · acords 2,4.5,7
            v._pinta_loop()
            self._dobleclic(tl, 5.0)             # a dalt, dins del loop
            self.assertEqual(tl.selected_keys(), {
                ("chord", 1), ("chord", 2), ("chord", 3), ("section", 1)})
            self.assertAlmostEqual(v.pos, 9.0, places=6)   # cursor al final
        finally:
            v.close()

    def test_dobleclic_fora_del_loop_no_selecciona(self):
        v = _visor()
        try:
            tl = v.timeline
            tl.resize(900, 300)
            v.loop_a, v.loop_b = 1.0, 4.0
            v._pinta_loop()
            tl.clear_selection()
            self._dobleclic(tl, 12.0)            # fora del loop
            self.assertEqual(tl.selected_keys(), set())
        finally:
            v.close()

    def test_dobleclic_sense_loop_no_fa_res(self):
        v = _visor()
        try:
            tl = v.timeline
            tl.resize(900, 300)
            v.loop_a = v.loop_b = None
            v._pinta_loop()
            tl.clear_selection()
            self._dobleclic(tl, 5.0)
            self.assertEqual(tl.selected_keys(), set())
        finally:
            v.close()

    def test_no_agafa_els_clips_de_la_frontera(self):
        """Un clip que comença EXACTAMENT a loop_b ja és FORA (semi-obert)."""
        v = _visor()
        try:
            v.loop_a, v.loop_b = 1.0, 10.0   # hi ha acord @10.0 i secció C @10.0
            self.assertEqual(v.selecciona_bloc_del_loop(), 4)
            keys = v.timeline.selected_keys()
            self.assertNotIn(("chord", 4), keys)      # acord @10.0 → fora
            self.assertNotIn(("section", 2), keys)    # secció C @10.0 → fora
            self.assertIn(("chord", 3), keys)         # acord @7.0 → dins
            self.assertIn(("section", 1), keys)       # secció B @5.0 → dins
        finally:
            v.close()

    def test_selecciona_bloc_del_loop_retorna_el_recompte(self):
        v = _visor()
        try:
            v.loop_a, v.loop_b = 1.0, 9.0
            self.assertEqual(v.selecciona_bloc_del_loop(), 4)
            self.assertEqual(v.loop_a, 1.0)      # el loop no es toca
        finally:
            v.close()


class TestLoopMenu(_Base):
    def test_menu_loop_te_les_accions(self):
        v = _visor()
        try:
            v.loop_a, v.loop_b = 1.0, 9.0
            v._pinta_loop()
            capt = {}
            orig = QMenu.exec_
            QMenu.exec_ = lambda self, pos, *a: capt.update(
                texts=[t.text() for t in self.actions() if not t.isSeparator()])
            try:
                v._on_loop_context_menu(None)
            finally:
                QMenu.exec_ = orig
            self.assertTrue(any("Copia" in t for t in capt["texts"]),
                            capt["texts"])
            self.assertTrue(any("Enganxa" in t for t in capt["texts"]),
                            capt["texts"])
        finally:
            v.close()

    def test_menu_copia_selecciona_i_deixa_cursor_al_final(self):
        v = _visor()
        try:
            v.loop_a, v.loop_b = 1.0, 9.0
            v._pinta_loop()
            textos = {}
            orig = QMenu.exec_

            def fake(self, pos, *a):
                textos["copia"] = next(
                    act for act in self.actions() if "Copia" in act.text())
                return textos["copia"]
            QMenu.exec_ = fake
            try:
                v._on_loop_context_menu(None)
            finally:
                QMenu.exec_ = orig
            self.assertTrue(v.timeline.has_clipboard())
            self.assertAlmostEqual(v.pos, 9.0, places=6)
        finally:
            v.close()


if __name__ == "__main__":
    unittest.main()
