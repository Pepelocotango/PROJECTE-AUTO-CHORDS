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

    def test_tram_3_compassos(self):
        r = self._cas(5.5)
        self.assertEqual((r["n"], r["num"], r["den"]), (3, 4, 4))
        self.assertAlmostEqual(r["bpm"], 3 * 4 * 60.0 / 5.5, places=6)

    def test_un_segon_prefereix_canviar_compas(self):
        r = self._cas(1.0)
        self.assertEqual((r["n"], r["num"], r["den"]), (1, 2, 4))
        self.assertAlmostEqual(r["bpm"], 120.0, places=6)

    def test_tres_segons_i_mig(self):
        r = self._cas(3.5)
        self.assertEqual((r["n"], r["num"], r["den"]), (2, 4, 4))
        self.assertAlmostEqual(r["bpm"], 2 * 4 * 60.0 / 3.5, places=6)

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
