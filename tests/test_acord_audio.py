"""Àudio per escoltar un tipus d'acord (`app/acord_audio.py`).

Piano elèctric sintetitzat amb numpy (FM estil Rhodes): **sense dependències
noves** i amb el **mateix motor d'àudio** de l'app. Aquí **no es fa sonar res**:
es verifica la matemàtica (notes → MIDI) i el senyal (mida, extrems, sense
saturar, sense NaN).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene dels tests: l'import té efecte (esborra els temporals en plegar)

import numpy as np  # noqa: E402
from app import acord_audio as A  # noqa: E402


class TestNotes(unittest.TestCase):
    def test_acords_coneguts(self):
        for arrel, graus, esperat in [
                ("C", "1,3,5,7", [48, 52, 55, 59]),          # Cmaj7: C3 E3 G3 B3
                ("F#", "1,b3,b5,b7", [54, 57, 60, 64]),      # F#m7b5
                ("Ab", "1,3,5,6,9", [56, 60, 63, 65, 70]),   # Ab6/9
                ("C", "1,5", [48, 55]),                      # C5 (power)
                ("C", "", [48])]:                            # sense graus → arrel
            self.assertEqual(A.notes_del_tipus(arrel, graus), esperat,
                             f"{arrel} {graus}")

    def test_sense_arrel_valida(self):
        self.assertEqual(A.notes_del_tipus("", "1,3,5"), [])
        self.assertEqual(A.notes_del_tipus("H", "1,3,5"), [])

    def test_graus_no_numerics_s_ignoren(self):
        """`7alt` porta «+alt» → s'ignora i queden 1,3,b7."""
        self.assertEqual(A.notes_del_tipus("C", "1,3,b7,+alt"), [48, 52, 58])

    def test_no_surt_del_rang(self):
        for arrel in ("C", "B", "Gb"):
            notes = A.notes_del_tipus(arrel, "1,3,5,7,9,11,13")
            self.assertTrue(all(A.MIDI_MIN <= m <= A.MIDI_MAX for m in notes),
                            arrel)

    def test_notes_amb_baix(self):
        """Acords amb `/`: el baix sona una octava sota l'arrel."""
        # A + 1,3,5,b7 (A7) amb baix G → G2 (43) + l'acord de A3 (57)
        notes = A.notes_amb_baix("A", "1,3,5,b7", "G")
        self.assertEqual(notes[0], 43, "el baix ha d'anar a baix de tot")
        self.assertIn(57, notes)
        # sense baix → igual que el tipus sol
        self.assertEqual(A.notes_amb_baix("A", "1,3,5,b7", ""),
                         A.notes_del_tipus("A", "1,3,5,b7"))
        # baix invàlid → s'ignora
        self.assertEqual(A.notes_amb_baix("A", "1,3,5,b7", "H"),
                         A.notes_del_tipus("A", "1,3,5,b7"))

    def test_baix_enharmonic(self):
        # Db2 i C#2 són la mateixa nota (MIDI 37)
        self.assertEqual(A.notes_amb_baix("Ab", "1,3,5,6,9", "Db")[0], 37)
        self.assertEqual(A.notes_amb_baix("F#", "1,b3,b5,b7", "C#")[0], 37)

    def test_duplicats_fora(self):
        # `1,1,3` → dues vegades la tònica = una sola nota
        self.assertEqual(A.notes_del_tipus("C", "1,1,3"), [48, 52])


class TestSenyal(unittest.TestCase):
    def _x(self, pcm):
        return np.frombuffer(pcm, "<i2").astype(float)

    def test_pcm_acord(self):
        sr = 22050
        x = self._x(A.pcm_acord([48, 52, 55, 59], sr, 0.5))
        self.assertEqual(len(x), int(0.5 * sr))
        self.assertFalse(np.isnan(x).any())
        self.assertLessEqual(abs(x).max(), 32767)
        self.assertLess(abs(x[0]), 100, "ha de començar a 0 (sense clic)")
        self.assertGreater(abs(x).max(), 10000, "no pot ser silenci")

    def test_no_satura_amb_moltes_notes(self):
        """El pic ha de quedar a 0,85 sense arribar mai al fons d'escala."""
        for n in (1, 4, 8, 12):
            notes = [48 + i for i in range(n)]
            x = self._x(A.pcm_acord(notes, 22050, 0.4))
            self.assertLessEqual(abs(x).max(), 32767, n)
            self.assertAlmostEqual(abs(x).max(), 0.85 * 32767, delta=250,
                                   msg=f"{n} notes saturades")

    def test_arpegi_i_escolta(self):
        bloc = A.pcm_acord([48, 52, 55], 22050, 0.5)
        arp = A.pcm_arpegi([48, 52, 55], 22050, 0.5, 0.2)
        self.assertGreater(len(arp), len(bloc), "l'arpegi dura més (en sèrie)")
        esc = A.pcm_escolta([48, 52, 55], 22050)
        self.assertGreater(len(esc), len(arp), "escolta = arpegi + pausa + bloc")

    def test_buits(self):
        self.assertEqual(A.pcm_acord([]), b"")
        self.assertEqual(A.pcm_arpegi([]), b"")
        self.assertEqual(A.pcm_escolta([]), b"")
        self.assertEqual(A.notes_del_tipus("C", ""), [48])


if __name__ == "__main__":
    unittest.main()
