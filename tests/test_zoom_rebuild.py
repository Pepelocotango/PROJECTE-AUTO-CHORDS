"""Regressió: reconstruir els items del timeline NO ha de perdre el ZOOM.

`set_data` (undo, editar/renombrar des de l'editor, enganxar, edicions MCP…)
reconstrueix tots els items. Si els items nous no reben la VISTA ACTUAL
(`_view_left`), es pinten com si la vista comencés a 0 → amb zoom, el clip
«salta» fora de vista i sembla que es perd el focus. Aquest test fixa
l'invariant: tot item reconstruït ha de portar la `_view_left` del timeline.
"""
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from app import visor as visor_mod  # noqa: E402

ACORDS = "0.0,2.0,C\n2.0,4.5,Am\n4.5,7.0,F\n7.0,10.0,G\n10.0,20.0,C\n"
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


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])


class TestZoomRebuild(_Base):
    def _zoom(self, v, kind, idx):
        v.resize(1200, 700)
        v.timeline.select_clip(kind, idx)
        v.timeline.zoom_selection()
        self.assertNotAlmostEqual(v.timeline._view_left, 0.0,
                                  msg="cal que hi hagi zoom per provar-ho")

    def test_set_data_mante_la_vista_als_items(self):
        """Tots els items reconstruïts han de portar la `_view_left` del timeline."""
        for kind in ("chord", "section"):
            v = _visor()
            try:
                self._zoom(v, kind, 1)
                vl = v.timeline._view_left
                v.timeline.set_data(v.acords, v.seccions)   # reconstrucció
                items = (v.timeline._chord_items if kind == "chord"
                         else v.timeline._section_items)
                self.assertTrue(items)
                for it in items:
                    self.assertAlmostEqual(it._view_left, vl, places=9,
                                           msg=f"{kind}: item sense la vista")
            finally:
                v.close()

    def test_renombrar_no_mou_el_clip(self):
        """El símptoma real: en reanomenar (Aplica) el clip NO ha de saltar."""
        for kind in ("chord", "section"):
            v = _visor()
            try:
                self._zoom(v, kind, 1)
                arr = (v.timeline._chord_by_idx if kind == "chord"
                       else v.timeline._section_by_idx)
                abans = arr[1].boundingRect()
                v._ed_kind, v._ed_idx = kind, 1
                v.ed_nom.setText("Am7" if kind == "chord" else "A2")
                v._aplica_editor()
                arr2 = (v.timeline._chord_by_idx if kind == "chord"
                        else v.timeline._section_by_idx)
                despres = arr2[1].boundingRect()
                self.assertAlmostEqual(despres.x(), abans.x(), places=6,
                                       msg=f"{kind}: el clip s'ha mogut de lloc")
            finally:
                v.close()

    def test_zoom_in_out_mante_la_vista_als_items(self):
        """Zoom amb els botons +/− també ha de propagar la vista a tots els items."""
        v = _visor()
        try:
            v.timeline.set_position(5.0)     # centra el zoom lluny de t=0
            v.timeline.zoom_in()
            v.timeline.zoom_in()
            vl = v.timeline._view_left
            self.assertNotAlmostEqual(vl, 0.0)
            for it in v.timeline._chord_items + v.timeline._section_items:
                self.assertAlmostEqual(it._view_left, vl, places=9)
        finally:
            v.close()


if __name__ == "__main__":
    unittest.main()
