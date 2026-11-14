"""Motor pur de talls amb Snap QM."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402,F401
_ = _temporals

from app import tall_qm  # noqa: E402


class TestTallQM(unittest.TestCase):
    def _texts(self, opts):
        return [o["etiqueta"] for o in opts]

    def test_pura_4_4(self):
        opts = tall_qm._opcions_costat(0.0, 2.0, 4.0, [(4, 4)])
        self.assertEqual(self._texts(opts), ["4/4 N=1 (120.000)"])

    def test_17_beats_base_mes_extrany(self):
        opts = tall_qm._opcions_costat(0.0, 8.5, 17.0, [(4, 4)])
        textos = self._texts(opts)
        self.assertIn("4/4 N=3 (120.000) + 5/4 N=1 (120.000)", textos)
        self.assertNotIn("4/4 N=4 (120.000) + 1/4 N=1 (120.000)", textos)

    def test_15_beats_te_extrany_i_seccio_sencera(self):
        opts = tall_qm._opcions_costat(0.0, 7.5, 15.0, [(4, 4)])
        textos = self._texts(opts)
        self.assertIn("4/4 N=3 (120.000) + 3/4 N=1 (120.000)", textos)
        self.assertIn("5/4 N=3 (120.000)", textos)

    def test_7_8_opcions_4_i_8_separades(self):
        opts = tall_qm._opcions_costat(0.0, 2.75, 5.5, [(7, 8)])
        textos = self._texts(opts)
        self.assertIn("4/8 N=1 (120.000) + 7/8 N=1 (120.000)", textos)
        self.assertIn("2/4 N=1 (120.000) + 7/8 N=1 (120.000)", textos)

    def test_7_8_minim_dos_opcions_4(self):
        opts = tall_qm._opcions_costat(0.0, 4.25, 8.5, [(7, 8)])
        sel = tall_qm.selecciona_opcions(opts)
        self.assertLessEqual(len(sel), 6)
        self.assertGreaterEqual(sum(1 for o in sel if o["es_4"]), 2)

    def test_1_4_es_filtra_si_hi_ha_alternativa(self):
        opts = tall_qm._opcions_costat(0.0, 8.5, 17.0, [(4, 4)])
        self.assertFalse(any(
            any(int(c.num) == 1 for c in o["clips"]) for o in opts))

    def test_sense_beats_fallback_ref(self):
        opts = tall_qm._opcio_sense_beats(0.0, 2.0, (120.0, 4, 4))
        self.assertEqual(len(opts), 1)
        self.assertEqual(int(opts[0]["clips"][0].n), 1)
        self.assertAlmostEqual(float(opts[0]["clips"][0].bpm), 120.0)

    def test_opcions_tall_separa_esquerra_i_dreta(self):
        from app import mapa_tempo
        trams = [mapa_tempo.TramMapa(
            0.0, 8.0, 120.0, "normal", "4/4", "", None, "negra")]
        beats = [i * 0.5 for i in range(16)]
        sides = tall_qm.opcions_tall(
            trams, 2.0, 8.0, 0.0, beats, (120.0, 4, 4), 1.0)
        self.assertIsNotNone(sides)
        self.assertEqual(len(sides), 2)
        self.assertEqual(sides[0][0]["clips"][0].num, 4)
        self.assertEqual(sides[1][0]["clips"][0].n, 3)


if __name__ == "__main__":
    unittest.main()
