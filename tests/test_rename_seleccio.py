"""Renombrar/editar: mantenir la selecció i refrescar la llista a l'instant,
i RENOM EN BLOC de la selecció del TIPUS ACTIU (amb selecció mixta es
renombren només els del tipus del clip actiu, opció A).

Com un DAW: editar no ha de perdre la selecció ni deixar la llista vella (regla
d'or #11: mateix tracte acords↔estructura). La selecció mixta serveix per a
operacions de BLOC (eliminar/copiar/enganxar/duplicar/moure) i per renombrar el
tipus actiu.
"""
import os
import sys
import tempfile
import unittest
import wave
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene dels tests: l'import té efecte (esborra els temporals en plegar)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtWidgets import QInputDialog  # noqa: E402

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


class TestEditorManteSeleccio(_Base):
    def _aplica(self, v, kind, idx, nom, ini_txt):
        v._ed_kind, v._ed_idx = kind, idx
        v.ed_nom.setText(nom)
        v.ed_ini.setText(ini_txt)
        v.ed_cb.setText("")
        v._aplica_editor()

    def test_acord_queda_seleccionat_i_llista_al_dia(self):
        v = _visor()
        v.ves_a(7.0)
        v.timeline.select_clip("chord", 3)
        self._aplica(v, "chord", 3, "Gmaj7", "7.00")
        self.assertEqual(v.acords[3][2][0], "GMaj7")
        self.assertEqual(v.timeline.selected_keys(), {("chord", 3)},
                         "el clip editat ha de quedar seleccionat")
        self.assertEqual(v.llista_ac.currentRow(), 3)
        self.assertIn("GMaj7", v.llista_ac.currentItem().text(),
                      "la llista s'ha d'actualitzar a l'instant")
        self.assertAlmostEqual(v.pos, 7.0, places=6,
                               msg="editar no ha de moure el cursor")
        v.close()

    def test_seccio_queda_seleccionada_i_llista_al_dia(self):
        v = _visor()
        v.ves_a(12.0)
        v.timeline.select_clip("section", 2)
        v.ed_fam.setText("X")
        self._aplica(v, "section", 2, "Z", "12.00")
        self.assertEqual(v.seccions[2][2], "Z")
        self.assertEqual(v.timeline.selected_keys(), {("section", 2)})
        self.assertEqual(v.llista_ab.currentRow(), 2)
        self.assertIn("Z", v.llista_ab.currentItem().text())
        self.assertAlmostEqual(v.pos, 12.0, places=6)
        v.close()


class TestRenomEnBloc(_Base):
    def test_acords_en_bloc(self):
        v = _visor()
        v.timeline.select_clip("chord", 0)
        v.timeline.extend_selection("chord", 2)     # {0,1,2}
        with patch.object(QInputDialog, "getText",
                          return_value=("Am", True)):
            self.assertTrue(v.renomena_seleccio())
        self.assertEqual([a[2][0] for a in v.acords[:3]], ["A-", "A-", "A-"])
        self.assertEqual(v.timeline.selected_keys(),
                         {("chord", 0), ("chord", 1), ("chord", 2)})
        self.assertEqual(len(v._undo_stack), 1)     # una sola operació
        v.undo()
        self.assertEqual([a[2][0] for a in v.acords[:3]], ["C", "Am", "F"])
        v.close()

    def test_seccions_en_bloc(self):
        v = _visor()
        v.timeline.select_clip("section", 1)
        v.timeline.extend_selection("section", 2)   # {1,2}
        with patch.object(QInputDialog, "getText",
                          return_value=("R", True)):
            self.assertTrue(v.renomena_seleccio())
        self.assertEqual([s[2] for s in v.seccions[1:]], ["R", "R"])
        self.assertEqual(v.timeline.selected_keys(),
                         {("section", 1), ("section", 2)})
        v.close()

    def test_seleccio_mixta_renombra_el_tipus_actiu(self):
        """Opció A: amb selecció mixta es renombren NOMÉS els del tipus actiu."""
        v = _visor()
        v.timeline.select_clip("chord", 0)
        v.timeline.toggle_selection("section", 0)   # mixta; actiu = section 0
        with patch.object(QInputDialog, "getText", return_value=("R", True)):
            self.assertTrue(v.renomena_seleccio())
        self.assertEqual(v.seccions[0][2], "R")     # la secció sí
        self.assertEqual([a[2][0] for a in v.acords],
                         ["C", "Am", "F", "G", "C"])  # els acords, intactes
        self.assertEqual(len(v._undo_stack), 1)
        v.close()


class TestRenomInlineManteSeleccio(_Base):
    def test_inline_mante_seleccio_i_llista(self):
        v = _visor()
        v.ves_a(7.0)
        v.timeline.select_clip("chord", 3)
        # flux faithful: el timeline ja té el nom nou quan arriba el senyal
        v.timeline._acords[3] = (7.0, "G7", "7.0")
        v.timeline.chordRenamed.emit(3, "G7")
        self.assertEqual(v.acords[3][2][0], "G7")
        self.assertEqual(v.timeline.selected_keys(), {("chord", 3)})
        self.assertIn("G7", v.llista_ac.currentItem().text())
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
