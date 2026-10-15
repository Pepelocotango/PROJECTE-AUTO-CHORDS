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
        self.assertEqual(xifrat.parteix_baix("C6/9"), ("C6/9", ""))
        self.assertEqual(xifrat.parteix_baix("A7/G"), ("A7", "G"))
        self.assertEqual(xifrat.normalitza_xifrat("C6/9"), "C6add9")

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


# Els tipus de la taula de referència de l'operador («acords i tensions»,
# 3 nivells) amb el `kind` de MusicXML i els GRAUS que han de generar.
TIPUS_REFERENCIA = [
    # Beginners
    ("C", "major", []), ("Cm", "minor", []), ("Cdim", "diminished", []),
    ("C7", "dominant", []), ("Cm7", "minor-seventh", []),
    ("Cm7b5", "half-diminished", []), ("Cmaj7", "major-seventh", []),
    # Intermediates
    ("Cmajb5", "major", [(5, -1, "alter")]),
    ("C5", "power", []), ("Csus2", "suspended-second", []),
    ("Csus4", "suspended-fourth", []), ("C+", "augmented", []),
    ("C6", "major-sixth", []), ("Cadd9", "major", [(9, 0, "add")]),
    ("Cm6", "minor-sixth", []), ("Cmadd9", "minor", [(9, 0, "add")]),
    ("Cdim7", "diminished-seventh", []),
    ("C7sus4", "suspended-fourth", [(7, -1, "add")]),
    ("C7b5", "dominant", [(5, -1, "alter")]),
    ("C7#5", "augmented-seventh", []), ("Cm(maj7)", "major-minor", []),
    ("C6add9", "major-sixth", [(9, 0, "add")]),
    ("Cm6add9", "minor-sixth", [(9, 0, "add")]),
    ("C7b9", "dominant", [(9, -1, "alter")]),
    ("C7#9", "dominant", [(9, 1, "alter")]),
    ("Cm7b9", "minor-seventh", [(9, -1, "alter")]),
    ("C9", "dominant-ninth", []),
    ("C9b5", "dominant-ninth", [(5, -1, "alter")]),
    ("C9#5", "dominant-ninth", [(5, 1, "alter")]),
    ("Cm9", "minor-ninth", []), ("Cmaj9", "major-ninth", []),
    ("C11", "dominant-11th", []), ("Cm11", "minor-11th", []),
    ("Cmaj11", "major-11th", []), ("C13", "dominant-13th", []),
    ("Cm13", "minor-13th", []), ("Cmaj13", "major-13th", []),
    # Advanced
    ("Cmaj7b5", "major-seventh", [(5, -1, "alter")]),
    ("Cmaj7#5", "major-seventh", [(5, 1, "alter")]),
    ("C7b5b9", "dominant", [(5, -1, "alter"), (9, -1, "alter")]),
    ("C7#5b9", "augmented-seventh", [(9, -1, "alter")]),
    ("C7#5#9", "augmented-seventh", [(9, 1, "alter")]),
    ("C7add11", "dominant", [(11, 0, "add")]),
    ("C7#11", "dominant", [(11, 1, "alter")]),
    ("Cm7b5b9", "half-diminished", [(9, -1, "alter")]),
    ("Cm7add11", "minor-seventh", [(11, 0, "add")]),
    ("Cmaj7#11", "major-seventh", [(11, 1, "alter")]),
    ("Cm9b5", "minor-ninth", [(5, -1, "alter")]),
    ("Cm(maj9)", "major-minor", [(9, 0, "add")]),
    ("Cmaj9#5", "major-ninth", [(5, 1, "alter")]),
    ("C9#11", "dominant-ninth", [(11, 1, "alter")]),
    ("Cmaj9#11", "major-ninth", [(11, 1, "alter")]),
    ("C11b9", "dominant-11th", [(9, -1, "alter")]),
    ("C13b5b9", "dominant-13th", [(5, -1, "alter"), (9, -1, "alter")]),
    ("C13b9", "dominant-13th", [(9, -1, "alter")]),
    ("C13#9", "dominant-13th", [(9, 1, "alter")]),
    ("C13#11", "dominant-13th", [(11, 1, "alter")]),
]


class TestGraus(unittest.TestCase):
    def test_graus_treure(self):
        """`noN` = treure un grau → MusicXML `subtract` (`no3`, `no5`, `no7`…)."""
        for xif, kind, gr in [
                ("Cno5", "major", [(5, 0, "subtract")]),
                ("Cno3", "major", [(3, 0, "subtract")]),
                ("Cno7", "major", [(7, 0, "subtract")]),
                ("Cmaj7no5", "major-seventh", [(5, 0, "subtract")]),
                ("Cm7no3no5", "minor-seventh",
                 [(3, 0, "subtract"), (5, 0, "subtract")]),
                ("C7no9", "dominant", [(9, 0, "subtract")]),
                ("C13no5", "dominant-13th", [(5, 0, "subtract")]),
                ("Cm6no5", "minor-sixth", [(5, 0, "subtract")])]:
            pa = xifrat.parteix_arrel(xifrat.normalitza_xifrat(xif))
            self.assertIsNotNone(pa, xif)
            k, g = xifrat.kind_i_graus(pa[1])
            self.assertEqual(k, kind, f"{xif}: kind")
            self.assertEqual(list(g), [tuple(x) for x in gr], f"{xif}: graus")

    def test_alteracions_dobles(self):
        """Dobles alteracions (MuseScore: `##`, `bb` i `x` = doble sostingut)."""
        for brut, net in [("C##", "C##"), ("Cbb", "Cbb"), ("Cx", "C##"),
                          ("Cx5", "C##5"), ("F##m7", "F##-7"),
                          ("C##/Dbb", "C##/Dbb"), ("Gbbmaj7", "GbbMaj7"),
                          ("Cxyz", "Cxyz")]:     # `x` + lletra ≠ accidental
            self.assertEqual(xifrat.normalitza_xifrat(brut), net, brut)

    def test_resta_qualitat(self):
        """El tros no convertible (p. ex. `alt`) es conserva per al `text`."""
        self.assertEqual(xifrat.resta_qualitat("7alt"), "alt")
        self.assertEqual(xifrat.resta_qualitat("7#11"), "")   # → `<degree>`
        self.assertEqual(xifrat.resta_qualitat("Maj7"), "")
        self.assertEqual(xifrat.resta_qualitat("xyz"), "xyz")

    def test_paraules_i_parentesis(self):
        """`major`/`minor` senceres i els graus entre parèntesis.

        Regressió (graella «Create The Music»): `Cmajor` feia `CMajdimr` i
        `C7(9,13)` feia `C7913` (els graus s'engrunaven i es perdien).
        """
        for brut, net in [("Cmajor", "C"), ("CMajor", "C"),
                          ("Cminor", "C-"), ("CMinor", "C-"),
                          ("C7(9,13)", "C7add9add13"),
                          ("Cmaj7(9)", "CMaj7add9"),
                          ("Cmaj7(13)", "CMaj7add13"),
                          ("Cmaj7(#11)", "CMaj7#11"),
                          ("C7(#9,b5)", "C7#9b5"),
                          ("C7sus2", "C7sus2"), ("C9sus4", "C9sus4"),
                          ("C13sus4", "C13sus4")]:
            self.assertEqual(xifrat.normalitza_xifrat(brut), net, brut)

    def test_els_graus_dels_parentesis_no_sengrunen(self):
        k, g = xifrat.kind_i_graus("7add9add13")
        self.assertEqual(k, "dominant")
        self.assertEqual(list(g), [(9, 0, "add"), (13, 0, "add")])

    def test_alteracions_no_son_acords(self):
        """Text que no és un xifrat NO s'ha de reconèixer (ni amb `no5`)."""
        for t in ("Cxyz", "solo", "veus", "X"):
            pa = xifrat.parteix_arrel(xifrat.normalitza_xifrat(t))
            k, _g = xifrat.kind_i_graus(pa[1]) if pa else (None, ())
            self.assertIsNone(k, f"{t!r} no s'hauria de reconèixer")


class TestTipusDeReferencia(unittest.TestCase):
    def test_kind_i_graus(self):
        for xif, kind, gr in TIPUS_REFERENCIA:
            q = xifrat.normalitza_xifrat(xif)[1:]      # treu l'arrel («C»)
            k, g = xifrat.kind_i_graus(q)
            self.assertEqual(k, kind, f"{xif}: kind={k!r} (esperat {kind!r})")
            self.assertEqual(list(g), [tuple(x) for x in gr], f"{xif}: graus")

    def test_tots_els_tipus_tenen_arrel_i_qualitat(self):
        for xif, _k, _g in TIPUS_REFERENCIA:
            pa = xifrat.parteix_arrel(xifrat.normalitza_xifrat(xif))
            self.assertIsNotNone(pa, xif)
            self.assertEqual(pa[0], "C", xif)


if __name__ == "__main__":
    unittest.main()
