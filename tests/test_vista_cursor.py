"""Selecció a les llistes → el cursor vermell ja hi va; ara la VISTA s'ha de
desplaçar (pan) perquè el cursor quedi visible, MANTENINT el ZOOM actual.

`TimelineView.ensure_cursor_visible()` fa el pan només si el cursor surt de la
zona còmoda (no canvia el zoom). El visor el crida en seleccionar una fila de
les llistes (acords o seccions).
"""
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
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


def _span(tl):
    return tl._view_right - tl._view_left


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])


class TestVistaCursor(_Base):
    def test_ensure_cursor_visible_desplaca_mantenint_zoom(self):
        v = _visor()
        try:
            tl = v.timeline
            tl.zoom_to(0.0, 3.0)                 # vista estreta a l'inici
            abans = _span(tl)
            tl.set_position(10.0, emit=False, snap=False)
            tl.ensure_cursor_visible()
            self.assertLessEqual(tl._view_left, 10.0)
            self.assertGreaterEqual(tl._view_right, 10.0)
            self.assertAlmostEqual(_span(tl), abans, places=6)   # zoom intacte
        finally:
            v.close()

    def test_ensure_cursor_visible_no_desplaca_si_ja_es_veu(self):
        v = _visor()
        try:
            tl = v.timeline
            tl.zoom_full()                        # vista sencera
            l0, r0 = tl._view_left, tl._view_right
            tl.set_position(10.0, emit=False, snap=False)
            tl.ensure_cursor_visible()
            self.assertAlmostEqual(tl._view_left, l0, places=9)
            self.assertAlmostEqual(tl._view_right, r0, places=9)
        finally:
            v.close()

    def test_llista_desplaca_la_vista_al_cursor(self):
        """Seleccionar una fila llunyana ha de portar el visor al clip."""
        for llista, salt, idx in (("llista_ac", "_salt_acord", 4),
                                  ("llista_ab", "_salt_seccio", 1)):
            v = _visor()
            try:
                tl = v.timeline
                tl.zoom_to(0.0, 3.0)
                abans = _span(tl)
                self.assertGreaterEqual(tl._view_right, 3.0)
                item = getattr(v, llista).item(idx)
                getattr(v, salt)(item)            # clic a la llista
                cur = tl.get_position()
                self.assertGreater(cur, 3.0)      # el cursor ha saltat fora
                self.assertLessEqual(tl._view_left, cur)
                self.assertGreaterEqual(tl._view_right, cur)
                self.assertAlmostEqual(_span(tl), abans, places=6)
            finally:
                v.close()


if __name__ == "__main__":
    unittest.main()
