import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from app import tempo_map as tm
from app import limits


class TestTempoMapGuardrails(unittest.TestCase):
    """Guardrails del flux principal: mapa de tempo/compas."""

    def test_valida_tempo_rubato_0_0_valid(self):
        bpm, num, den = tm.valida_tempo(120.0, 0, 0)
        self.assertEqual((num, den), (0, 0))

    def test_valida_tempo_0_4_invalid(self):
        with self.assertRaises(ValueError):
            tm.valida_tempo(120.0, 0, 4)

    def test_valida_tempo_4_0_invalid(self):
        with self.assertRaises(ValueError):
            tm.valida_tempo(120.0, 4, 0)

    def test_tempo_map_buit_no_crasha(self):
        m = tm.TempoMap([])
        self.assertIsNotNone(m)
        self.assertEqual(m.tram(0.0).bpm, 120.0)

    def test_tempo_map_extrapola_fora(self):
        m = tm.TempoMap([(0.0, 10.0, 120.0, 4, 4)])
        t = m.tram(100.0)
        self.assertIsNotNone(t)
        self.assertEqual(t.bpm, 120.0)

    def test_clip_conte_beat_sencer_false_si_massa_curt(self):
        tram = (0.0, 0.3, 120.0, 4, 4)
        graella = [0.0, 0.5, 1.0]
        self.assertFalse(tm.clip_conte_beat_sencer(tram, graella))

    def test_clip_conte_beat_sencer_true_si_beat_complet(self):
        tram = (0.0, 1.0, 120.0, 4, 4)
        graella = [0.0, 0.5, 1.0]
        self.assertTrue(tm.clip_conte_beat_sencer(tram, graella))

    def test_valida_i_normalitza_compassos_rebutja_clip_sense_beat(self):
        trams = [(0.0, 5.0, 0.0, 4, 4), (5.0, 10.0, 120.0, 4, 4)]
        with self.assertRaises(ValueError):
            tm.valida_i_normalitza_compassos(trams, 10.0)

    def test_repara_fronteres_no_bpm_fora_banda(self):
        trams = [(0.0, 5.0, 120.0, 4, 4), (5.0, 10.0, 120.0, 4, 4)]
        out = tm.repara_fronteres(trams, 10.0)
        for t in out:
            self.assertTrue(limits.BPM_MIN <= t[2] <= limits.BPM_MAX)


if __name__ == "__main__":
    unittest.main()
