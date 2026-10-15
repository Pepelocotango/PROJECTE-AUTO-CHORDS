"""Notació del xifrat (`app/xifrat.py`): parseig del baix i forma canònica.

Decisió de l'operador (2026-10-15, «opció 3»): el MODEL desa **sempre** els
acords en una forma canònica; si l'usuari n'escriu una variant, l'app l'enten i
la deixa bé → el model, els noms de fitxer de l'export i la partitura
(MusicXML → MuseScore) parlen tots la mateixa llengua.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import xifrat  # noqa: E402

CANONICS = [
    # tríades
    ("C", "C"), ("Cmaj", "C"), ("CM", "C"), ("CΔ", "C"), ("c", "C"),
    ("Am", "A-"), ("A-", "A-"), ("Amin", "A-"), ("Ami", "A-"), ("amin", "A-"),
    ("Cdim", "Cdim"), ("C°", "Cdim"), ("Co", "Cdim"), ("Caug", "Caug"),
    ("C+", "Caug"), ("Csus4", "Csus4"), ("Csus", "Csus4"), ("Csus2", "Csus2"),
    # séptimes
    ("C7", "C7"), ("Cmaj7", "CMaj7"), ("CM7", "CMaj7"), ("CΔ7", "CMaj7"),
    ("CMa7", "CMaj7"), ("Cm7", "C-7"), ("Cmin7", "C-7"), ("C-7", "C-7"),
    ("CmM7", "C-Maj7"), ("CmMaj7", "C-Maj7"), ("C-maj7", "C-Maj7"),
    ("Cdim7", "Cdim7"), ("Co7", "Cdim7"), ("Cm7b5", "C-7b5"), ("Cø", "C-7b5"),
    ("Cø7", "C-7b5"), ("Caug7", "Caug7"),
    # sisenes / extensions / afegits
    ("C6", "C6"), ("Cm6", "C-6"), ("C-6", "C-6"), ("Cadd9", "Cadd9"),
    ("C9", "C9"), ("Cm9", "C-9"), ("Cmaj9", "CMaj9"), ("CM9", "CMaj9"),
    ("C7#9", "C7#9"), ("C11", "C11"), ("C13", "C13"), ("C7sus4", "C7sus4"),
    # alteracions de l'arrel (+ baix)
    ("Bb", "Bb"), ("A#", "A#"), ("F#dim7", "F#dim7"), ("BbMaj7", "BbMaj7"),
    ("A7/G", "A7/G"), ("Am/G", "A-/G"), ("G/D", "G/D"), ("C/E", "C/E"),
    ("A-7/G", "A-7/G"), ("A-6/F#", "A-6/F#"), ("Amaj7/G#", "AMaj7/G#"),
    ("C/Bb", "C/Bb"), ("a7/g", "A7/G"),
    # «sense acord» i espais
    ("N", "N"), ("NC", "N"), ("N.C.", "N"), ("", ""), ("  C  ", "C"),
]


class TestFormaCanonica(unittest.TestCase):
    def test_taula(self):
        for brut, net in CANONICS:
            self.assertEqual(xifrat.normalitza_xifrat(brut), net,
                             f"{brut!r} hauria de donar {net!r}")

    def test_el_baix_no_es_confon_amb_6_9(self):
        """`C6/9` porta barra però NO és un acord amb baix."""
        self.assertEqual(xifrat.normalitza_xifrat("C6/9"), "C6/9")
        self.assertEqual(xifrat.parteix_baix("C6/9"), ("C6/9", ""))
        self.assertEqual(xifrat.parteix_baix("A7/G"), ("A7", "G"))

    def test_es_cap_acord(self):
        for t in ("N", "n", "NC", "N.C.", "", "  "):
            self.assertTrue(xifrat.es_cap_acord(t), t)
        for t in ("C", "Am", "N7"):
            self.assertFalse(xifrat.es_cap_acord(t), t)

    def test_text_no_dacord_no_es_trenca(self):
        for t in ("solo", "veus", "H7", "X"):
            self.assertEqual(xifrat.normalitza_xifrat(t), t,
                             f"no s'hauria de tocar {t!r}")

    def test_arrel_i_qualitat(self):
        self.assertEqual(xifrat.parteix_arrel("BbMaj7"), ("Bb", "Maj7"))
        self.assertEqual(xifrat.parteix_arrel("A-7"), ("A", "-7"))
        self.assertIsNone(xifrat.parteix_arrel("solo"))


if __name__ == "__main__":
    unittest.main()
