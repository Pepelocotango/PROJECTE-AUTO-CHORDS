"""Tests del motor pur de recalcul del mapa de temps (F0)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene: esborra els temporals en plegar

import unittest  # noqa: E402

from app import tempo_recalc as tr  # noqa: E402


class TestRecalculcaTram(unittest.TestCase):
    def test_n_negres_del_clip_factor_i_frontera(self):
        beats = [1.0, 2.0, 3.0, 4.0]
        # El beat de la frontera (3.0) només compta al clip de la dreta.
        self.assertEqual(tr.n_negres_del_clip(beats, 1.0, 3.0, 1.0), 2.0)
        self.assertEqual(tr.n_negres_del_clip(beats, 3.0, 5.0, 1.0), 2.0)
        self.assertEqual(tr.n_negres_del_clip(beats, 1.0, 3.0, 1.5), 3.0)
        self.assertIsNone(tr.n_negres_del_clip(beats, 5.0, 6.0, 1.0))
        self.assertIsNone(tr.n_negres_del_clip([], 0.0, 1.0, 1.0))

    def _cas(self, durada, bpm=120.0, num=4, den=4, n_ref=None):
        return tr.recalculca_tram(durada, bpm, num, den, n_ref=n_ref)

    def test_tram_4_compassos(self):
        r = self._cas(7.8)
        self.assertEqual((r["n"], r["num"], r["den"]), (4, 4, 4))
        self.assertAlmostEqual(r["bpm"], 4 * 4 * 60.0 / 7.8, places=6)

    def test_onze_beats_trien_11_4(self):
        r = self._cas(5.5)
        self.assertEqual((r["n"], r["num"], r["den"]), (1, 11, 4))
        self.assertAlmostEqual(r["bpm"], 120.0, places=6)
        self.assertTrue(r["beats_inferits"])

    def test_un_segon_prefereix_canviar_compas(self):
        r = self._cas(1.0)
        self.assertEqual((r["n"], r["num"], r["den"]), (1, 2, 4))
        self.assertAlmostEqual(r["bpm"], 120.0, places=6)

    def test_set_beats_inferits_trien_7_4(self):
        r = self._cas(3.5)
        self.assertEqual((r["n"], r["num"], r["den"]), (1, 7, 4))
        self.assertAlmostEqual(r["bpm"], 120.0, places=6)
        self.assertTrue(r["beats_inferits"])

    def test_dos_segons_es_un_compas(self):
        r = self._cas(2.0)
        self.assertEqual((r["n"], r["num"], r["den"]), (1, 4, 4))
        self.assertAlmostEqual(r["bpm"], 120.0, places=6)

    def test_n_fixat_mana(self):
        r = self._cas(2.0, n_ref=4)
        self.assertEqual((r["n"], r["num"], r["den"]), (4, 2, 4))
        self.assertAlmostEqual(r["bpm"], 240.0, places=6)
        self.assertFalse(r["canvis"]["n"])

    def test_minim_de_la_app(self):
        r = self._cas(30.0 / 350.0)
        self.assertEqual((r["n"], r["num"], r["den"]), (1, 1, 8))
        self.assertAlmostEqual(r["bpm"], 350.0, places=5)

    def test_per_sota_del_minim_no_hi_ha_solucio(self):
        self.assertIsNone(self._cas(0.08))

    def test_set_beats_forcen_7_4(self):
        r = tr.recalculca_tram(2.912646, 144.569633, 4, 4, n_beats=7)
        self.assertEqual((r["n"], r["num"], r["den"]), (1, 7, 4))
        self.assertTrue(r["beats_usats"])
        self.assertAlmostEqual(r["bpm"], 7 * 60.0 / 2.912646, places=4)

    def test_fallback_k_mes_menys_u(self):
        casos = ((13, 4, 4, 12), (17, 4, 4, 16), (19, 4, 4, 20),
                 (23, 4, 4, 24), (17, 3, 4, 18))
        for k, num, den, k_usat in casos:
            with self.subTest(k=k, ref=(num, den)):
                r = tr.recalculca_tram(k * 0.5, 120.0, num, den, n_beats=k)
                self.assertEqual((r["num"], r["den"]), (num, den))
                self.assertEqual(r["beats"], k_usat)
                self.assertEqual(r["beats_detectats"], k)
                self.assertTrue(r["beats_ajustats"])
                self.assertTrue(r["beats_usats"])

    def test_fallback_k_no_accepta_2_8_degenerat(self):
        r = tr.recalculca_tram(6.5, 120.0, 4, 4, n_beats=13)
        self.assertNotEqual((r["num"], r["den"]), (2, 8))
        self.assertEqual((r["num"], r["den"], r["n"]), (4, 4, 3))

    def test_fallback_k_respecta_n_fix(self):
        r = tr.recalculca_tram(6.0, 120.0, 4, 4, n_ref=4, n_beats=12)
        self.assertFalse(r["beats_ajustats"])
        self.assertEqual((r["n"], r["num"], r["den"], r["beats"]),
                         (4, 3, 4, 12))
        r = tr.recalculca_tram(6.0, 120.0, 4, 4, n_ref=3, n_beats=12)
        self.assertFalse(r["beats_ajustats"])
        self.assertEqual((r["n"], r["num"], r["den"], r["beats"]),
                         (3, 4, 4, 12))

    def test_avisos_de_bpm_i_octava(self):
        r = tr.recalculca_tram(6.0, 120.0, 4, 4, n_beats=8)
        self.assertAlmostEqual(r["desviacio_bpm"], -1.0 / 3.0, places=6)
        self.assertFalse(r["sospita_octava"])
        self.assertIn("BPM desviat", tr.avis_de_resultat(r))
        r = tr.recalculca_tram(2.0, 120.0, 4, 4, n_beats=8)
        self.assertTrue(r["sospita_octava"])
        self.assertIn("sospita d'octava", tr.avis_de_resultat(r))
        r = tr.recalculca_tram(8.0 / 3.0, 120.0, 4, 4, n_beats=8)
        self.assertFalse(r["sospita_octava"])
        self.assertIn("BPM desviat", tr.avis_de_resultat(r))

    def test_9_8_amb_tres_beats_de_negra_amb_punt(self):
        r = tr.recalculca_tram(2.25, 120.0, 9, 8, n_beats=4.5)
        self.assertEqual((r["n"], r["num"], r["den"]), (1, 9, 8))
        self.assertAlmostEqual(r["bpm"], 120.0, places=6)
        self.assertEqual(r["beats"], 4.5)
        self.assertEqual(r["beats_detectats"], 4.5)

    def test_5_8_amb_cinc_corxeres(self):
        r = tr.recalculca_tram(1.25, 120.0, 5, 8, n_beats=2.5)
        self.assertEqual((r["n"], r["num"], r["den"]), (1, 5, 8))
        self.assertAlmostEqual(r["bpm"], 120.0, places=6)
        self.assertEqual(r["beats"], 2.5)

    def test_fallback_avança_un_beat_detectat(self):
        # Amb pas 1,5 (negra amb punt), 19 no prova 18/20 sinó 17,5/20,5.
        r = tr.recalculca_tram(6.5, 120.0, 4, 4, n_beats=19,
                              pas_beat=1.5)
        self.assertEqual(r["beats"], 17.5)
        self.assertTrue(r["beats_ajustats"])
        r = tr.recalculca_tram(6.5, 120.0, 4, 4, n_beats=19,
                              pas_beat=1.0)
        self.assertEqual(r["beats"], 20.0)
        self.assertTrue(r["beats_ajustats"])

    def test_zero_beats_no_bloqueja_la_inferència(self):
        r = tr.recalculca_tram(3.5, 120.0, 4, 4, n_beats=0)
        self.assertEqual((r["n"], r["num"], r["den"]), (1, 7, 4))
        self.assertAlmostEqual(r["bpm"], 120.0, places=6)

    def test_avis_de_beats_inferits(self):
        r = tr.recalculca_tram(6.5, 120.0, 4, 4)
        text = tr.avis_de_resultat(r)
        self.assertIn("sense beats detectats", text)
        self.assertNotIn("beats ajustats", text)

    def test_avisos_i_beats_en_el_cami_per_durada(self):
        r = tr.recalculca_tram(2.8, 120.0, 4, 4)
        self.assertFalse(r["beats_usats"])
        self.assertFalse(r["beats_ajustats"])
        self.assertIsNone(r["beats_detectats"])
        self.assertIn("desviacio_bpm", r)
        self.assertIn("sospita_octava", r)

    def test_regla_del_multiple_4_4(self):
        for k, n in ((20, 5), (24, 6), (28, 7), (40, 10)):
            with self.subTest(k=k):
                r = tr.recalculca_tram(k * 0.5, 120.0, 4, 4, n_beats=k)
                self.assertEqual((r["n"], r["num"], r["den"]), (n, 4, 4))

    def test_regla_del_multiple_3_4(self):
        for k, n in ((12, 4), (36, 12)):
            with self.subTest(k=k):
                r = tr.recalculca_tram(k * 0.5, 120.0, 3, 4, n_beats=k)
                self.assertEqual((r["n"], r["num"], r["den"]), (n, 3, 4))

    def test_regla_del_multiple_6_8(self):
        for k, n in ((6, 2), (12, 4)):
            with self.subTest(k=k):
                r = tr.recalculca_tram(k * 0.5, 120.0, 6, 8, n_beats=k)
                self.assertEqual((r["n"], r["num"], r["den"]), (n, 6, 8))

    def test_regla_del_multiple_respecta_n_fix(self):
        r = tr.recalculca_tram(6.0, 120.0, 4, 4, n_ref=4, n_beats=12)
        self.assertEqual((r["n"], r["num"], r["den"]), (4, 3, 4))
        r = tr.recalculca_tram(6.0, 120.0, 4, 4, n_ref=3, n_beats=12)
        self.assertEqual((r["n"], r["num"], r["den"]), (3, 4, 4))

    def test_regla_del_multiple_exempta_n_max(self):
        r = tr.recalculca_tram(240.0, 120.0, 4, 4, n_beats=480)
        self.assertEqual((r["n"], r["num"], r["den"]), (120, 4, 4))

    def test_14_beats_amb_base_4_4_son_dos_7_4(self):
        r = tr.recalculca_tram(5.813688, 144.569633, 4, 4, n_beats=14)
        self.assertEqual((r["n"], r["num"], r["den"]), (2, 7, 4))
        self.assertAlmostEqual(r["bpm"], 14 * 60.0 / 5.813688, places=4)

    def test_beats_corregixen_compas_base_7_4(self):
        r = tr.recalculca_tram(3.365208, 144.569633, 7, 4, n_beats=8)
        self.assertEqual((r["n"], r["num"], r["den"]), (2, 4, 4))
        self.assertAlmostEqual(r["bpm"], 8 * 60.0 / 3.365208, places=4)

    def test_22_beats_amb_base_4_4_son_onze_quarts(self):
        r = tr.recalculca_tram(9.120, 144.569633, 4, 4, n_beats=22)
        self.assertEqual((r["n"], r["num"], r["den"]), (2, 11, 4))

    def test_vuit_beats_son_dos_compassos_de_4_4(self):
        r = tr.recalculca_tram(3.365208, 144.569633, 4, 4, n_beats=8)
        self.assertEqual((r["n"], r["num"], r["den"]), (2, 4, 4))
        self.assertAlmostEqual(r["bpm"], 2 * 4 * 60.0 / 3.365208, places=4)

    def test_set_beats_en_el_segon_clip(self):
        r = tr.recalculca_tram(2.901042, 144.569633, 4, 4, n_beats=7)
        self.assertEqual((r["n"], r["num"], r["den"]), (1, 7, 4))
        self.assertAlmostEqual(r["bpm"], 7 * 60.0 / 2.901042, places=4)

    def test_referencia_invalida(self):
        with self.assertRaises(ValueError):
            tr.recalculca_tram(2.0, 20.0, 4, 4)
        with self.assertRaises(ValueError):
            tr.recalculca_tram(2.0, 120.0, 0, 4)
        with self.assertRaises(ValueError):
            tr.recalculca_tram(0.0, 120.0, 4, 4)

    def test_n_fixat_amb_compas_que_si_cap(self):
        r = self._cas(1.0, n_ref=2)
        self.assertEqual((r["n"], r["num"], r["den"]), (2, 2, 4))
        self.assertAlmostEqual(r["bpm"], 240.0, places=6)
