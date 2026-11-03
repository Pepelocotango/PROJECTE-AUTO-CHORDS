"""Proves sintètiques per a l'avaluador de tempo."""
import os
import sys
import tempfile
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals

import unittest  # noqa: E402
from unittest.mock import patch  # noqa: E402

from eines import avalua_tempo  # noqa: E402


class TestAvaluacioTempo(unittest.TestCase):
    def test_prova_sintetica_sense_plugins(self):
        self.assertTrue(avalua_tempo.prova_sintetica())

    def test_detecta_compassos_sobrants_absents_i_deriva(self):
        resultat = avalua_tempo.avalua_graella(
            [0.0, 2.0, 4.0, 6.0],
            [0.02, 2.04, 4.2, 8.0],
            tolerancia=0.07)
        self.assertEqual(resultat["dins_tolerancia_pct"], 50.0)
        self.assertEqual(resultat["sobrants"], 2)
        self.assertEqual(resultat["absents"], 2)
        self.assertAlmostEqual(resultat["error_maxim_s"], 1.8)
        self.assertAlmostEqual(resultat["deriva_s"], 0.02)

    def test_cas_buit_no_fabrica_un_percentatge(self):
        resultat = avalua_tempo.avalua_graella([], [])
        self.assertIsNone(resultat["dins_tolerancia_pct"])
        self.assertEqual(resultat["sobrants"], 0)
        self.assertEqual(resultat["absents"], 0)

    def test_beat_f_i_error_d_alineacio(self):
        resultat = avalua_tempo.avalua_events(
            [0.0, 1.0, 2.0], [0.01, 1.02, 2.30], tolerancia=0.070)
        self.assertEqual(resultat["esperats"], 3)
        self.assertEqual(resultat["detectats"], 3)
        self.assertEqual(resultat["emparellats"], 2)
        self.assertAlmostEqual(resultat["precisio"], 2.0 / 3.0)
        self.assertAlmostEqual(resultat["recall"], 2.0 / 3.0)
        self.assertAlmostEqual(resultat["f"], 2.0 / 3.0)
        self.assertAlmostEqual(resultat["error_mitja_s"], 0.015)
        self.assertAlmostEqual(resultat["error_maxim_s"], 0.02)

    def test_beat_f_castiga_sobrants_i_absents(self):
        resultat = avalua_tempo.avalua_events(
            [0.0, 1.0, 2.0], [0.1, 1.1, 2.1], tolerancia=0.070)
        self.assertEqual(resultat["emparellats"], 0)
        self.assertEqual(resultat["f"], 0.0)
        self.assertIsNone(resultat["error_mitja_s"])
        buit = avalua_tempo.avalua_events([], [])
        self.assertIsNone(buit["f"])

    def test_anotacio_de_tempo_variable_i_rubato(self):
        bars = avalua_tempo.compassos_referencia({
            "bpm": 120,
            "num": 4,
            "den": 4,
            "compas_1_s": 0.0,
            "canvis": [[4.0, 100, 4, 4]],
            "rubatos": [[10.0, 12.0]],
        }, 20.0)
        self.assertEqual(bars[0], 0.0)
        self.assertTrue(all(b < 10.0 or b >= 12.0 for b in bars))
        self.assertEqual(bars, sorted(bars))

    def test_rebutja_canvis_duplicats_i_temps_invalid(self):
        with self.assertRaises(ValueError):
            avalua_tempo.compassos_referencia({
                "bpm": 120,
                "canvis": [[0.0, 100, 4, 4], [0.0, 90, 4, 4]],
            }, 10.0)
        with self.assertRaises(ValueError):
            avalua_tempo.avalua_graella([float("nan")], [])

    def test_avaluacio_i_csv_amb_wav_sintetic(self):
        with tempfile.TemporaryDirectory() as carpeta:
            wav_path = os.path.join(carpeta, "sintetic.wav")
            anotacio = os.path.join(carpeta, "sintetic.tempo.json")
            sortida = os.path.join(carpeta, "resultats.csv")
            with wave.open(wav_path, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(100)
                w.writeframes(bytes(4000))
            with open(anotacio, "w", encoding="utf-8") as f:
                f.write(
                    '{"audio":"sintetic.wav","bpm":120,"num":4,"den":4,'
                    '"compas_1_s":0.0}')
            with patch.object(avalua_tempo.pipeline, "detecta_bpm",
                              return_value=120.0):
                with patch.object(avalua_tempo.pipeline, "detecta_compas1",
                                  return_value=0.0):
                    with patch.object(
                            avalua_tempo.pipeline,
                            "detecta_tempo_per_trams",
                            return_value=(
                                [(0.0, 20.0, 120.0, 4, 4),], 0.0, 120.0)):
                        fila = avalua_tempo.avalua_canço(anotacio)
            self.assertEqual(fila["dins_70ms_pct"], 100.0)
            self.assertIsNone(fila["beat_f"])
            self.assertIsNone(fila["downbeat_f"])
            avalua_tempo.escriu_csv(sortida, [fila])
            with open(sortida, encoding="utf-8") as f:
                csv_text = f.read()
            self.assertIn("dins_70ms_pct", csv_text)
            self.assertIn("beat_f", csv_text)
            self.assertIn("sintetic.wav", csv_text)

    def test_beat_i_downbeat_amb_anotacio_completa(self):
        with tempfile.TemporaryDirectory() as carpeta:
            wav_path = os.path.join(carpeta, "sintetic.wav")
            anotacio = os.path.join(carpeta, "sintetic.tempo.json")
            with wave.open(wav_path, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(100)
                w.writeframes(bytes(4000))
            with open(anotacio, "w", encoding="utf-8") as f:
                f.write(
                    '{"audio":"sintetic.wav","bpm":120,"num":4,"den":4,'
                    '"compas_1_s":0.0,"beats":[0,1,2,3,4],'
                    '"downbeats":[0,2,4,6,8],"onsets":[0.0,0.5]}')
            with patch.object(avalua_tempo.pipeline, "detecta_bpm",
                              return_value=120.0):
                with patch.object(avalua_tempo.pipeline, "detecta_compas1",
                                  return_value=0.0):
                    with patch.object(
                            avalua_tempo.pipeline,
                            "detecta_beats",
                            return_value=[0.0, 1.0, 2.0, 3.0, 4.0]):
                        with patch.object(
                                avalua_tempo.pipeline,
                                "detecta_tempo_per_trams",
                                return_value=(
                                    [(0.0, 8.0, 120.0, 4, 4),],
                                    0.0, 120.0)):
                            fila = avalua_tempo.avalua_canço(anotacio)
            self.assertEqual(fila["beat_f"], 1.0)
            self.assertEqual(fila["beat_error_mitja_ms"], 0.0)
            self.assertEqual(fila["downbeat_f"], 1.0)
            self.assertEqual(fila["downbeat_error_mitja_ms"], 0.0)

    def test_temps_de_beat_fora_de_l_audio(self):
        with tempfile.TemporaryDirectory() as carpeta:
            wav_path = os.path.join(carpeta, "sintetic.wav")
            anotacio = os.path.join(carpeta, "sintetic.tempo.json")
            with wave.open(wav_path, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(100)
                w.writeframes(bytes(4000))
            with open(anotacio, "w", encoding="utf-8") as f:
                f.write(
                    '{"audio":"sintetic.wav","bpm":120,"num":4,"den":4,'
                    '"compas_1_s":0.0,"beats":[999]}')
            with self.assertRaises(ValueError):
                avalua_tempo.avalua_canço(anotacio)


if __name__ == "__main__":
    unittest.main()
