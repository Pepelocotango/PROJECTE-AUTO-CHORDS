"""Tests del regle/grid: numeració de compassos i posicions SENSE deriva.

Regressió del bug «7.1, 7.4, 8.4» (un inici de compàs etiquetat com «(N-1).4»
en lloc de «N.1») i de la deriva per acumulació `t += step` al regle i al grid.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import timeline_base as tb  # noqa: E402


class TestFmtPosIniciDeCompas(unittest.TestCase):
    def test_inici_de_compas_sempre_dot_1(self):
        for bpm in (60, 75, 90, 100, 118, 120, 125.4, 138, 150, 179.8):
            for bpb in (3, 4, 6):
                beat = 60.0 / bpm
                measure = beat * bpb
                for k in range(0, 250):
                    t = k * measure
                    lab = tb.fmt_pos(t, True, bpm, bpb, 0.0, measure)
                    self.assertTrue(
                        lab.endswith(".1"),
                        f"bpm={bpm} bpb={bpb} k={k} t={t!r} -> {lab!r}")

    def test_neteja_soroll_coma_flotant(self):
        # cas exacte del bug (125,4 BPM · posició del compàs 8 = 7*measure)
        beat = 60.0 / 125.4
        measure = beat * 4
        net = measure * 7
        self.assertEqual(tb.fmt_pos(net, True, 125.4, 4, 0.0, measure), "8.1")
        # amb el soroll típic d'acumulació, abans sortia «7.4»; ara «8.1»
        brut = net - 1e-12
        self.assertEqual(tb.fmt_pos(brut, True, 125.4, 4, 0.0, measure), "8.1")


class TestGridPositionsSenseDeriva(unittest.TestCase):
    STEP = 1.9138755980861244      # 1 compàs a 125,4 BPM · 4/4

    def test_posicions_coincideixen_amb_index(self):
        pos = list(tb.grid_positions(0.0, 90 * self.STEP, self.STEP, 0.0))
        self.assertGreater(len(pos), 80)
        for i, t in enumerate(pos):
            self.assertAlmostEqual(t, i * self.STEP, places=9)

    def test_cap_inici_de_compas_deriva(self):
        for t in tb.grid_positions(0.0, 200 * self.STEP, self.STEP, 0.0):
            lab = tb.fmt_pos(t, True, 125.4, 4, 0.0, self.STEP)
            self.assertTrue(lab.endswith(".1"), f"t={t!r} -> {lab!r}")

    def test_amb_offset(self):
        step, off = 0.5, 3.0
        pos = list(tb.grid_positions(off, off + 20 * step, step, off))
        for i, t in enumerate(pos):
            self.assertAlmostEqual(t, off + i * step, places=9)

    def test_step_invalid(self):
        self.assertEqual(list(tb.grid_positions(0.0, 10.0, 0.0)), [])


if __name__ == "__main__":
    unittest.main()
