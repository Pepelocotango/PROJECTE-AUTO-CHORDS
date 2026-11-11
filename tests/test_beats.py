"""Tests del motor de beats i de la sensibilitat."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals

from app import beats, limits  # noqa: E402


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


class TestQMExtraccioUnica(unittest.TestCase):
    def test_qm_temps_normalitza_i_deduplica(self):
        from app import pipeline_vamp

        def _fake(transform, out, wav, log, params=None):
            with open(out, "w", encoding="utf-8") as f:
                f.write("0.600000,0\n0.100000,0\n0.600000,0\n")

        with patch.object(pipeline_vamp, "executa_transform",
                          side_effect=_fake):
            self.assertEqual(beats._qm_temps("t", "x.wav"), [0.1, 0.6])


class TestMotors(unittest.TestCase):
    def test_bpm_de_beats_fora_de_banda_retorna_none(self):
        self.assertIsNone(beats._bpm_de_beats([0.0, 10.0, 20.0, 30.0]))

    def test_bpm_de_beats_dins_de_banda(self):
        bpm = beats._bpm_de_beats([0.0, 0.5, 1.0, 1.5, 2.0])
        self.assertAlmostEqual(bpm, 120.0)
        self.assertTrue(limits.BPM_MIN <= bpm <= limits.BPM_MAX)

    def test_bpm_de_beats_menys_de_dos(self):
        self.assertIsNone(beats._bpm_de_beats([1.0]))

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

    def test_motor_per_defecte_es_qm(self):
        with patch.object(beats, "_qm_temps", return_value=[0.1, 0.6]) as qm:
            res = beats.detecta("x.wav", nomes_beats=True)
        self.assertEqual(res["motor"], "qm")
        self.assertIn("qm-tempotracker:beats", qm.call_args.args[0])

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
