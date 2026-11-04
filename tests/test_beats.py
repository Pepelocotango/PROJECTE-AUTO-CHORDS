"""Tests del motor de beats i de la sensibilitat."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals

from app import beats  # noqa: E402


class TestSensibilitat(unittest.TestCase):
    def test_tightness_baixa_quan_puja_la_sensibilitat(self):
        self.assertAlmostEqual(beats.tightness_de_sensibilitat(0), 100.0)
        self.assertAlmostEqual(beats.tightness_de_sensibilitat(50), 55.0)
        self.assertAlmostEqual(beats.tightness_de_sensibilitat(100), 10.0)

    def test_alpha_baixa_quan_puja_la_sensibilitat(self):
        self.assertAlmostEqual(beats.alpha_de_sensibilitat(0), 0.99)
        self.assertAlmostEqual(beats.alpha_de_sensibilitat(100), 0.10)

    def test_limits_de_sensibilitat(self):
        self.assertAlmostEqual(beats.tightness_de_sensibilitat(-20), 100.0)
        self.assertAlmostEqual(beats.tightness_de_sensibilitat(200), 10.0)

    def test_motor_desconegut(self):
        with self.assertRaises(ValueError):
            beats.detecta("x.wav", motor="inexistent")


class TestMotors(unittest.TestCase):
    def test_resultat_nostre(self):
        with patch.object(beats.tempo, "detecta_bpm", return_value=120.0), \
                patch.object(beats.tempo, "segueix_beats",
                             return_value=([0.0, 0.5, 1.0], 120.0)), \
                patch.object(beats.pipeline, "wav_info",
                             return_value={"durada": 2.0}), \
                patch.object(beats.tempo, "beats_a_trams",
                             return_value=([], 0.0)):
            res = beats.detecta("x.wav", motor="nostre", sensibilitat=50)
        self.assertEqual(res["motor"], "nostre")
        self.assertEqual(res["bpm"], 120.0)
        self.assertEqual(res["beats"], [0.0, 0.5, 1.0])
        self.assertEqual(res["downbeats"], [])

    def test_nomes_beats_sense_bpm_ni_downbeats(self):
        with patch.object(beats.tempo, "detecta_bpm", return_value=120.0), \
                patch.object(beats.tempo, "segueix_beats",
                             return_value=([0.0, 0.5, 1.0], 120.0)):
            res = beats.detecta("x.wav", motor="nostre", nomes_beats=True)
        self.assertIsNone(res["bpm"])
        self.assertEqual(res["beats"], [0.0, 0.5, 1.0])
        self.assertEqual(res["downbeats"], [])

    def test_qm_nomes_beats_usa_tempotracker(self):
        with patch.object(beats, "_qm_temps", return_value=[0.1, 0.6]) as qm:
            res = beats.detecta("x.wav", motor="qm", nomes_beats=True)
        self.assertIsNone(res["bpm"])
        self.assertEqual(res["beats"], [0.1, 0.6])
        self.assertEqual(res["downbeats"], [])
        self.assertEqual(qm.call_count, 1)
        transform = qm.call_args.args[0]
        self.assertIn("qm-tempotracker:beats", transform)
        params = qm.call_args.args[2]
        self.assertNotIn("bpb", params)

    def test_qm_passa_alpha_i_bpb(self):
        with patch.object(beats, "_qm_temps", side_effect=[[0.1, 0.6],
                                                           [0.1]]) as qm, \
                patch.object(beats.pipeline, "detecta_bpm_qm",
                             return_value=120.0):
            res = beats.detecta("x.wav", motor="qm", sensibilitat=100,
                                bpb=3)
        self.assertEqual(res["motor"], "qm")
        self.assertEqual(res["bpm"], 120.0)
        self.assertEqual(res["beats"], [0.1, 0.6])
        self.assertEqual(res["downbeats"], [0.1])
        params = qm.call_args_list[0].args[2]
        self.assertEqual(params["bpb"], "3")
        self.assertAlmostEqual(float(params["alpha"]), 0.10)


if __name__ == "__main__":
    unittest.main()


class TestSnapMarcadors(unittest.TestCase):
    def test_snap_dins_tolerancia_i_ambigus(self):
        from app import marcadors as M
        res = M.snap_a_objectius([1.0, 2.0, 5.0],
                                 [1.03, 2.2, 4.98, 5.0], tolerancia=0.12)
        self.assertEqual(res["marques"], [1.03, 2.0, 5.0])
        self.assertEqual(res["moviments"], [(1.0, 1.03)])
        self.assertEqual(len(res["ambigus"]), 1)
        self.assertEqual(res["sense_objectiu"], [2.0])

    def test_no_duplica_objectiu(self):
        from app import marcadors as M
        res = M.snap_a_objectius([1.0, 1.1], [1.0], tolerancia=0.12)
        self.assertEqual(len(res["marques"]), 2)
        self.assertEqual(res["moviments"], [])
        self.assertEqual(len(res["ambigus"]), 1)
