import unittest
import random

from app import tempo_ajust


class TestTempoAjust(unittest.TestCase):
    def test_tempo_fix_jitter_un_sol_tram(self):
        random.seed(1)
        ms = [i * 2.0 + random.uniform(-0.005, 0.005) for i in range(20)]
        info = tempo_ajust.ajusta_un_bpm(ms, 4, 4)
        self.assertAlmostEqual(info["bpm"], 120.0, places=1)
        self.assertLess(info["residu_max_ms"], 40.0)

    def test_canvi_brusc_parteix(self):
        ms = [i * 2.0 for i in range(10)] + [20.0 + i * (240.0 / 90.0) for i in range(1, 11)]
        trams, motius = tempo_ajust.ajusta_amb_particio(ms, 40.0, 4, 4)
        self.assertGreaterEqual(len(trams), 2)

    def test_residu_rms(self):
        ms = [i * 0.5 for i in range(10)]
        info = tempo_ajust.ajusta_un_bpm(ms, 4, 4)
        self.assertAlmostEqual(info["residu_max_ms"], 0.0, places=3)


if __name__ == "__main__":
    unittest.main()