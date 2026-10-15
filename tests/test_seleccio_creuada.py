"""Selecció creuada (Shift+clic per TEMPS a les dues pistes) + renom en bloc
estil fulla de càlcul (opció A: amb selecció mixta, només el tipus actiu).

- `extend_selection`: el rang abraça acords I seccions (l'inici dels quals cau
  dins del rang), per poder copiar/enganxar/esborrar «2 estructures + N acords».
- `_renomena_acords`/`_renomena_seccions`: renom de molts elements de cop, i
  el camp Nom + «Aplica» de l'editor també ho fa amb una multi-selecció.
Regla d'or #11: mateix tracte acords↔estructura.
"""
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtCore import QPoint  # noqa: E402
from PyQt5.QtWidgets import QListWidget, QMenu  # noqa: E402

from app import visor as visor_mod  # noqa: E402

# acords: 0 C · 2 Am · 4.5 F · 7 G · 10 C   |   seccions: A 0-5 · B 5-10 · C 10-20
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
    v = visor_mod.Visor(wav, ca, sa, bpm=120, bpb=4, tempo_fix=False)
    v.td, v.sortida = td, out
    return v


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])


class TestSeleccioCreuada(_Base):
    def test_shift_de_chord_a_chord_abraça_seccions(self):
        v = _visor()
        try:
            tl = v.timeline
            tl.select_clip("chord", 0)
            tl.extend_selection("chord", 3)      # rang [0.0, 7.0]
            self.assertEqual(tl.selected_keys(), {
                ("chord", 0), ("chord", 1), ("chord", 2), ("chord", 3),
                ("section", 0), ("section", 1)})   # A(0) i B(5) hi cauen
        finally:
            v.close()

    def test_shift_de_section_a_section_abraça_acords(self):
        v = _visor()
        try:
            tl = v.timeline
            tl.select_clip("section", 1)
            tl.extend_selection("section", 2)    # rang [5.0, 10.0]
            self.assertEqual(tl.selected_keys(), {
                ("section", 1), ("section", 2),
                ("chord", 3), ("chord", 4)})       # 7.0 i 10.0 hi cauen
        finally:
            v.close()

    def test_copia_enganxa_bloc_mixt(self):
        """Copiar «secció + acords» i enganxar-ho: canvien LES DUES pistes."""
        v = _visor()
        try:
            tl = v.timeline
            tl.select_multi({("chord", 2), ("chord", 3), ("section", 1)})
            tl.copy_selection()
            tl.set_position(10.0, emit=False, snap=False)   # cursor mogut
            b = [s[2] for s in v.seccions].count("B")
            tl.paste_at_cursor()
            # acords: el bloc F(4.5), G(7.0) s'enganxa a 10.0 → 10 F, 12.5 G
            self.assertEqual(v.acords[4][1], "F")
            self.assertEqual(v.acords[5][1], "G")
            # estructura: la secció B s'ha sobreescrit al tram nou
            self.assertEqual([s[2] for s in v.seccions].count("B"), b + 1)
        finally:
            v.close()


class TestRenomMultiple(_Base):
    def test_editor_aplica_renombra_tot_el_bloc(self):
        """Seleccionar acords 0,2,4 i «Aplica» → tots a G (com una fulla)."""
        v = _visor()
        try:
            v.timeline.select_multi({("chord", 0), ("chord", 2), ("chord", 4)})
            v._ed_kind, v._ed_idx = "chord", 0
            v.ed_nom.setText("G")
            v._aplica_editor()
            self.assertEqual([a[1] for a in v.acords],
                             ["G", "Am", "G", "G", "G"])
            self.assertEqual(len(v._undo_stack), 1)      # una sola operació
            v.undo()
            self.assertEqual([a[1] for a in v.acords],
                             ["C", "Am", "F", "G", "C"])
        finally:
            v.close()

    def test_editor_aplica_mixt_renombra_el_tipus_actiu(self):
        v = _visor()
        try:
            v.timeline.select_multi({("chord", 0), ("chord", 1),
                                     ("section", 0), ("section", 1)})
            v._ed_kind, v._ed_idx = "chord", 0          # actiu = acords
            v.ed_nom.setText("Dm")
            v._aplica_editor()
            self.assertEqual([a[1] for a in v.acords[:3]], ["Dm", "Dm", "F"])
            self.assertEqual([s[2] for s in v.seccions], ["A", "B", "C"])
        finally:
            v.close()

    def test_renomena_seccions_en_bloc_conserva_lletra_i_familia(self):
        v = _visor()
        try:
            self.assertTrue(v._renomena_seccions([0, 2], "Z"))
            self.assertEqual([s[2] for s in v.seccions], ["Z", "B", "Z"])
            self.assertEqual([s[3] for s in v.seccions], ["Z", "B", "Z"])
        finally:
            v.close()

    def test_menu_de_llista_te_reanomena(self):
        """El menú contextual de les llistes ha d'oferir «Reanomena» (regla #11)."""
        for nom_menu, esperat in (("_menu_acord", "acord"),
                                  ("_menu_seccio", "secció")):
            v = _visor()
            capt = {}
            orig_exec = QMenu.exec_
            orig_idx = QListWidget.indexAt

            class _Fila:
                def row(self):
                    return 0
            QMenu.exec_ = lambda self, pos, *a: capt.update(
                texts=[t.text() for t in self.actions() if not t.isSeparator()])
            QListWidget.indexAt = lambda self, pos: _Fila()
            try:
                getattr(v, nom_menu)(QPoint(1, 1))
            finally:
                QMenu.exec_ = orig_exec
                QListWidget.indexAt = orig_idx
            self.assertTrue(any("Reanomena" in t for t in capt["texts"]),
                            f"{nom_menu}: {capt['texts']}")
            self.assertTrue(any(esperat in t.lower() for t in capt["texts"]))
            v.close()


if __name__ == "__main__":
    unittest.main()
