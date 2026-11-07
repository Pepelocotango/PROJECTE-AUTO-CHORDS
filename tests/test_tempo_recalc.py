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
