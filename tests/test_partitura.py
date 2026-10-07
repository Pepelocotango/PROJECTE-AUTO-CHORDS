"""Tests de l'exportació de partitura (app/partitura.py).

No necessiten MuseScore: només proven el parsing, el mapeig xifrat-><harmony>,
la descomposició de durades i la construcció del MusicXML.
"""
import os
import tempfile
import unittest
from pathlib import Path

from app import partitura


class ParsingTests(unittest.TestCase):
    def test_parse_pos_qualsevol_compas(self):
        self.assertAlmostEqual(partitura.parse_pos("1.1.1", 4), 0.0)
        self.assertAlmostEqual(partitura.parse_pos("1.1.3", 4), 0.5)
        self.assertAlmostEqual(partitura.parse_pos("2.3.3", 4), 6.5)
        self.assertAlmostEqual(partitura.parse_pos("1.1.1", 3), 0.0)
        self.assertAlmostEqual(partitura.parse_pos("2.1.1", 3), 3.0)

    def test_llegeix_locators_ignora_capcalera(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "acords_locators.txt"
            p.write_text("posició (compàs.temps.setzena)   acord   durada(temps)\n"
                         "1.1.3          G        22\n"
                         "6.3.3          BbMaj7   1\n", encoding="utf-8")
            ev = partitura.llegeix_locators(str(p), 4)
            self.assertEqual(len(ev), 2)
            self.assertAlmostEqual(ev[0][0], 0.5)
            self.assertEqual(ev[0][1], "G")
            self.assertEqual(ev[0][2], 22.0)
            self.assertEqual(ev[1][1], "BbMaj7")

    def test_llegeix_seccions_deduplica(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "estructura_ABC.csv"
            p.write_text("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
                         "0,3,3,A,A,1.1.1,2.2.1\n"
                         "3,30,27,B,B,2.2.1,13.3.3\n", encoding="utf-8")
            secs = partitura.llegeix_seccions(str(p))
            self.assertEqual(secs, [(1, "A"), (2, "B")])


class HarmonyTests(unittest.TestCase):
    def test_majors_i_menors(self):
        self.assertIn("<kind>major</kind>", partitura.harmony_xml("C"))
        self.assertIn("<kind>minor</kind>", partitura.harmony_xml("Am"))
        self.assertIn("<kind>minor</kind>", partitura.harmony_xml("A-"))

    def test_septimes_i_alteracions(self):
        self.assertIn("major-seventh", partitura.harmony_xml("Cmaj7"))
        w = partitura.harmony_xml("BbMaj7")
        self.assertIn("<root-step>B</root-step>", w)
        self.assertIn("<root-alter>-1</root-alter>", w)
        self.assertIn("major-seventh", w)
        self.assertIn("diminished-seventh", partitura.harmony_xml("F#dim7"))

    def test_slash_chord(self):
        w = partitura.harmony_xml("G/D")
        self.assertIn("<kind>major</kind>", w)
        self.assertIn("<bass-step>D</bass-step>", w)

    def test_no_acord_i_qualitat_desconeguda(self):
        self.assertEqual(partitura.harmony_xml("N"), "")
        self.assertIn('text="Cxyz"', partitura.harmony_xml("Cxyz"))


class DuradesTests(unittest.TestCase):
    def test_decomposa(self):
        self.assertEqual(partitura._decomposa(16), [("whole", 0)])
        self.assertEqual(partitura._decomposa(12), [("half", 1)])
        self.assertEqual(partitura._decomposa(10), [("half", 0), ("eighth", 0)])
        self.assertEqual(partitura._decomposa(3), [("eighth", 1)])
        self.assertEqual(partitura._decomposa(0), [])

    def test_note_i_silenci(self):
        self.assertIn("<notehead>slash</notehead>", partitura._note_xml(8))
        self.assertIn("<rest/>", partitura._note_xml(4, rest=True))
        self.assertNotIn("<pitch>", partitura._note_xml(4, rest=True))


class MusicXmlTests(unittest.TestCase):
    def _events(self):
        # C (1 compàs) | Am (2 temps) + F (2 temps) | G
        return [(0.0, "C", 4.0), (4.0, "Am", 2.0), (6.0, "F", 2.0),
                (8.0, "G", 4.0)]

    def test_construeix_basic(self):
        xml = partitura.construeix_musicxml(
            self._events(), [(1, "A"), (3, "B")], bpb=4, bpm=120.0,
            titol="Prova", key_fifths=1)
        self.assertIn('<score-partwise version="4.0">', xml)
        self.assertIn("<work-title>Prova</work-title>", xml)
        self.assertIn("<fifths>1</fifths>", xml)
        self.assertIn("<per-minute>120</per-minute>", xml)
        self.assertIn("<rehearsal>A</rehearsal>", xml)
        self.assertIn("<rehearsal>B</rehearsal>", xml)
        self.assertIn("<print new-system=\"yes\"/>", xml)
        self.assertIn("<harmony><root><root-step>C</root-step>", xml)
        self.assertIn("minor</kind>", xml)
        # 3 compassos + compàs final de tancament
        self.assertEqual(xml.count("<measure number="), 4)
        # no hi ha d'haver durations incoherents: cada compàs suma 16 unitats
        self.assertIn("<bar-style>light-heavy</bar-style>", xml)

    def test_salt_de_sistema_i_beat_type(self):
        xml = partitura.construeix_musicxml(
            self._events(), [(1, "A")], bpb=4, bpm=100.0, titol="X",
            new_system_each=2, beat_type=8)
        self.assertIn("<beat-type>8</beat-type>", xml)
        self.assertIn('new-system="yes"', xml)


class ExportaTests(unittest.TestCase):
    def _escriu_font(self, td):
        d = Path(td) / "Tema_ACORDS"
        d.mkdir()
        (d / "acords_locators.txt").write_text(
            "posició (compàs.temps.setzena)   acord   durada(temps)\n"
            "1.1.1   C   4\n"
            "2.1.1   Am  4\n", encoding="utf-8")
        (d / "estructura_ABC.csv").write_text(
            "inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
            "0,5,5,A,A,1.1.1,2.2.1\n", encoding="utf-8")
        (d / "guia_acords.html").write_text(
            "<h3>103 BPM · 4 temps/compàs · gris = acord</h3>", encoding="utf-8")
        return d

    def test_exporta_sense_musescore(self):
        with tempfile.TemporaryDirectory() as td:
            d = self._escriu_font(td)
            res = partitura.exporta_partitura(
                str(d), log=lambda *_a: None,
                genera_pdf=False, genera_mscz=False)
            self.assertIn("musicxml", res)
            self.assertTrue(os.path.isfile(res["musicxml"]))
            self.assertTrue(res["musicxml"].endswith("Tema.musicxml"))
            self.assertIsNone(res["pdf"])
            text = open(res["musicxml"], encoding="utf-8").read()
            self.assertIn("<per-minute>103</per-minute>", text)  # de la guia
            self.assertIn("<harmony>", text)

    def test_sense_locators(self):
        with tempfile.TemporaryDirectory() as td:
            res = partitura.exporta_partitura(str(td), log=lambda *_a: None,
                                              genera_pdf=False, genera_mscz=False)
            self.assertEqual(res.get("error"), "sense_locators")


class EntornTests(unittest.TestCase):
    def test_musescore_bin_env_override(self):
        vell = os.environ.get("AUTO_CHORDS_MUSESCORE")
        try:
            os.environ["AUTO_CHORDS_MUSESCORE"] = "/tmp/fals_mscore"
            self.assertEqual(partitura.musescore_bin(), "/tmp/fals_mscore")
        finally:
            if vell is None:
                os.environ.pop("AUTO_CHORDS_MUSESCORE", None)
            else:
                os.environ["AUTO_CHORDS_MUSESCORE"] = vell

    def test_fifths_de_to(self):
        self.assertEqual(partitura.fifths_de_to("C"), 0)
        self.assertEqual(partitura.fifths_de_to("G"), 1)
        self.assertEqual(partitura.fifths_de_to("F"), -1)
        self.assertEqual(partitura.fifths_de_to("G major"), 1)
        self.assertEqual(partitura.fifths_de_to("E minor"), 1)
        self.assertEqual(partitura.fifths_de_to("Em"), 1)


if __name__ == "__main__":
    unittest.main()
