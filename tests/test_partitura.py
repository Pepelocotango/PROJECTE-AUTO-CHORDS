"""Tests de l'exportació de partitura (app/partitura.py).

No necessiten MuseScore: només proven el parsing, el mapeig xifrat-><harmony>,
la descomposició de durades i la construcció del MusicXML.
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def test_xifrat_jazz_amb_baix(self):
        """Els xifrats de jazz (menor amb `-`, maj7, 6a) amb baix `/nota`.

        Regressió: `A-maj7/G#` sortia com a `<root>A</root>` + un `<kind
        text="A-maj7-G#">` → MuseScore duplicava el nom («AA-maj7-G#»).
        """
        w = partitura.harmony_xml("A-7/G")
        self.assertIn("<kind>minor-seventh</kind>", w)
        self.assertIn("<bass-step>G</bass-step>", w)
        w = partitura.harmony_xml("A-6/F#")
        self.assertIn("<kind>minor-sixth</kind>", w)
        self.assertIn("<bass-step>F</bass-step>", w)
        self.assertIn("<bass-alter>1</bass-alter>", w)
        w = partitura.harmony_xml("A-maj7/G#")
        self.assertIn("<kind>major-minor</kind>", w)
        self.assertIn("<bass-step>G</bass-step>", w)
        w = partitura.harmony_xml("A7/G")
        self.assertIn("<kind>dominant</kind>", w)
        self.assertIn("<bass-step>G</bass-step>", w)

    def test_la_barra_de_6_9_no_es_un_baix(self):
        """`C6/9` porta barra però NO és un acord amb baix."""
        w = partitura.harmony_xml("C6/9")
        self.assertNotIn("<bass>", w)
        self.assertIn("<kind>major-sixth</kind>", w)   # 6a amb la 9a afegida
        self.assertIn("<degree-value>9</degree-value>", w)

    def test_acord_complexe_amb_tensions_i_baix(self):
        """`Ab69(#11,#13)/Db`: root + kind + els 3 `<degree>` + baix."""
        w = partitura.harmony_xml("Ab69(#11,#13)/Db")
        self.assertIn("<root-step>A</root-step>", w)
        self.assertIn("<root-alter>-1</root-alter>", w)
        self.assertIn("<kind>major-sixth</kind>", w)      # 6a
        for v in ("9", "11", "13"):                        # 9 afegida + #11 + #13
            self.assertIn(f"<degree-value>{v}</degree-value>", w)
        self.assertIn("<degree-alter>1</degree-alter>", w)  # sostinguts
        self.assertIn("<bass-step>D</bass-step>", w)
        self.assertIn("<bass-alter>-1</bass-alter>", w)

    def test_alteracions_dobles_al_root_i_al_baix(self):
        """`##`/`bb` → `<root-alter>±2</root-alter>` (i el baix igual)."""
        w = partitura.harmony_xml("C##m7")
        self.assertIn("<root-alter>2</root-alter>", w)
        self.assertIn("<kind>minor-seventh</kind>", w)
        w = partitura.harmony_xml("Gbbmaj7")
        self.assertIn("<root-alter>-2</root-alter>", w)
        w = partitura.harmony_xml("C##/Dbb")
        self.assertIn("<root-alter>2</root-alter>", w)
        self.assertIn("<bass-alter>-2</bass-alter>", w)

    def test_qualitat_no_estandard_conserva_el_text(self):
        """`C7alt`: el `kind` base + el símbol sencer al `text` (no es perd)."""
        w = partitura.harmony_xml("C7alt")
        self.assertIn("<kind text=\"7alt\">dominant</kind>", w)

    def test_no_grau(self):
        """`noN` (sense la 5a, etc.) → `<degree-type>subtract</degree-type>`."""
        w = partitura.harmony_xml("Cmaj7no5")
        self.assertIn("<kind>major-seventh</kind>", w)
        self.assertIn("<degree-value>5</degree-value>", w)
        self.assertIn("<degree-type>subtract</degree-type>", w)

    def test_altered_amb_degrees(self):
        w = partitura.harmony_xml("C7b9#11")
        self.assertIn("<kind>dominant</kind>", w)
        self.assertIn("<degree-value>9</degree-value>", w)
        self.assertIn("<degree-alter>-1</degree-alter>", w)
        self.assertIn("<degree-value>11</degree-value>", w)
        self.assertIn("<degree-type>alter</degree-type>", w)

    def test_no_acord_i_qualitat_desconeguda(self):
        self.assertEqual(partitura.harmony_xml("N"), "")
        self.assertEqual(partitura.harmony_xml("N.C."), "")
        # Qualitat desconeguda: el `text` porta NOMÉS el sufix (el root ja
        # s'escriu a part) → MuseScore no duplica el nom.
        self.assertIn('text="xyz"', partitura.harmony_xml("Cxyz"))
        self.assertNotIn('text="Cxyz"', partitura.harmony_xml("Cxyz"))


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
        d = Path(td) / "AUTOCHORDS_Tema"
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


class TestMuseScore(unittest.TestCase):
    """Descobriment del binari de MuseScore (ha de funcionar a tots els SO)."""

    def test_env_te_prioritat(self):
        with mock.patch.dict(os.environ, {"AUTO_CHORDS_MUSESCORE": "/tmp/msc"}):
            self.assertEqual(partitura.musescore_bin(), "/tmp/msc")

    def test_no_peta_si_no_hi_es(self):
        env = {k: v for k, v in os.environ.items()
               if k != "AUTO_CHORDS_MUSESCORE"}
        with mock.patch.dict(os.environ, env, clear=True):
            partitura.musescore_bin()      # None o binari real: no ha de petar

    def test_troba_binari_per_glob(self):
        env = {k: v for k, v in os.environ.items()
               if k != "AUTO_CHORDS_MUSESCORE"}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch("app.partitura.shutil.which", return_value=None), \
                mock.patch("app.partitura.glob.glob",
                           side_effect=lambda p, **k: ["/X"] if "MuseScore" in p else []):
            self.assertEqual(partitura.musescore_bin(), "/X")


class BaseDeSortidaTests(unittest.TestCase):
    """Títol per defecte derivat del nom de la carpeta (prefix AUTOCHORDS_)."""

    def test_prefix_coincideix_amb_pipeline(self):
        # El mòdul partitura no importa el projecte: el prefix s'hi repeteix i
        # aquest test evita que els dos valors divergeixin.
        from app import pipeline
        self.assertEqual(partitura._PREFIX_SORTIDA, pipeline.PREFIX_SORTIDA)

    def test_treu_el_prefix(self):
        self.assertEqual(partitura._base_de_sortida("/musica/AUTOCHORDS_Tema"),
                         "Tema")

    def test_sense_prefix_es_queda_igual(self):
        self.assertEqual(partitura._base_de_sortida("/musica/Altres"), "Altres")


if __name__ == "__main__":
    unittest.main()


class TestMusicXmlMapa(unittest.TestCase):
    """Fase 5: el MusicXML reflecteix els canvis de TEMPO del mapa."""

    def test_canvis_de_tempo(self):
        from app.tempo_map import TempoMap
        mapa = TempoMap([(0.0, 4.0, 120.0, 4, 4), (4.0, 8.0, 60.0, 4, 4)])
        events = [(0.0, "C", 4.0), (4.0, "G", 4.0)]
        xml = partitura.construeix_musicxml(events, [], bpb=4, bpm=120.0,
                                            mapa=mapa)
        self.assertIn('<sound tempo="120"', xml)
        self.assertIn('<sound tempo="60"', xml)      # canvi al compàs 3
        self.assertIn('<measure number="3">', xml)

    def test_constant_no_afegeix_res(self):
        from app.tempo_map import TempoMap
        const = TempoMap.constant(120, 4, 4, durada=8.0)
        events = [(0.0, "C", 4.0), (4.0, "G", 4.0)]
        a = partitura.construeix_musicxml(events, [], bpb=4, bpm=120.0)
        b = partitura.construeix_musicxml(events, [], bpb=4, bpm=120.0,
                                          mapa=const)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
