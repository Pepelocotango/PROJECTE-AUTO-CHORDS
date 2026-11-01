"""Regressions de les edicions bàsiques d'àudio."""
import os
import shutil
import sys
import tempfile
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals

import unittest  # noqa: E402
import numpy as np  # noqa: E402
from app import audio_edit as edita  # noqa: E402
from app import pipeline  # noqa: E402


def _escriu_wav(ruta, valors, sr=1000):
    valors = np.asarray(valors, dtype="<i2")
    canals = valors.shape[1] if valors.ndim == 2 else 1
    with wave.open(ruta, "wb") as w:
        w.setnchannels(canals)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(valors.tobytes())


def _llegeix_wav(ruta):
    with wave.open(ruta, "rb") as w:
        return (w.getframerate(), w.getnchannels(),
                np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
                .reshape(-1, w.getnchannels()))


class TestEdicioWav(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.origen = os.path.join(self.td, "origen.wav")
        self.desti = os.path.join(self.td, "editada.wav")
        _escriu_wav(self.origen, np.arange(1000, 11000, 1000))

    def tearDown(self):
        shutil.rmtree(self.td, ignore_errors=True)

    def test_retalla_inici_i_fade_entrada(self):
        durada = edita.escriu_wav_editada(
            self.origen, self.desti, edita.RETALLA_INICI, 3)
        sr, canals, valors = _llegeix_wav(self.desti)
        self.assertEqual((sr, canals), (1000, 1))
        self.assertAlmostEqual(durada, 0.007)
        np.testing.assert_array_equal(
            valors[:, 0], [0, 1667, 4000, 7000, 8000, 9000, 10000])
        self.assertEqual(_llegeix_wav(self.origen)[2][0, 0], 1000)

    def test_retalla_final_i_fade_eixida(self):
        durada = edita.escriu_wav_editada(
            self.origen, self.desti, edita.RETALLA_FINAL, 7)
        _sr, _canals, valors = _llegeix_wav(self.desti)
        self.assertAlmostEqual(durada, 0.007)
        np.testing.assert_array_equal(
            valors[:, 0], [1000, 2000, 3000, 4000, 3333, 2000, 0])

    def test_silenci_inicial_i_final(self):
        edita.escriu_wav_editada(
            self.origen, self.desti, edita.SILENCI_INICI, 3)
        _sr, _canals, inici = _llegeix_wav(self.desti)
        np.testing.assert_array_equal(
            inici[:, 0], [0, 0, 0, 0, 667, 2000, 4000, 5000, 6000,
                          7000, 8000, 9000, 10000])
        edita.escriu_wav_editada(
            self.origen, self.desti, edita.SILENCI_FINAL, 3)
        _sr, _canals, final = _llegeix_wav(self.desti)
        np.testing.assert_array_equal(
            final[:, 0], [1000, 2000, 3000, 4000, 5000, 6000, 7000,
                          5333, 3000, 0, 0, 0, 0])

    def test_fades_estereo_conserven_la_fase(self):
        valors = np.column_stack((
            np.arange(1000, 11000, 1000),
            -np.arange(1000, 11000, 1000)))
        _escriu_wav(self.origen, valors)
        edita.escriu_wav_editada(
            self.origen, self.desti, edita.SILENCI_INICI, 2)
        _sr, canals, sortida = _llegeix_wav(self.desti)
        self.assertEqual(canals, 2)
        np.testing.assert_array_equal(sortida[:, 0], -sortida[:, 1])

    def test_entrada_invalida_no_trepitja_la_destinacio(self):
        with open(self.desti, "wb") as f:
            f.write(b"preserva")
        with self.assertRaises(ValueError):
            edita.escriu_wav_editada(
                self.origen, self.desti, edita.RETALLA_INICI, 10)
        with open(self.desti, "rb") as f:
            self.assertEqual(f.read(), b"preserva")


class TestTransformaModelAudio(unittest.TestCase):
    def setUp(self):
        self.acords = [
            pipeline.Clip(0.0, 4.0, ("C", "0")),
            pipeline.Clip(4.0, 8.0, ("G", "4")),
        ]
        self.seccions = [(0.0, 4.0, "A", "A"), (4.0, 8.0, "B", "B")]
        self.trams = [(0.0, 4.0, 120.0, 4, 4),
                      (4.0, 8.0, 90.0, 3, 4)]

    def transforma(self, operacio, delta):
        return edita.transforma_model(
            self.acords, self.seccions, self.trams, [1.0, 5.0],
            offset=2.0, durada=8.0, operacio=operacio, delta=delta,
            pos=3.0, loop_a=1.0, loop_b=6.0, loop_on=True)

    def test_retalla_inici_desplaca_model_offset_i_loop(self):
        nou = self.transforma(edita.RETALLA_INICI, 2.0)
        self.assertEqual(nou["durada"], 6.0)
        self.assertEqual([a.ini for a in nou["acords"]], [0.0, 2.0])
        self.assertEqual(nou["seccions"], [(0.0, 2.0, "A", "A"),
                                           (2.0, 6.0, "B", "B")])
        self.assertEqual(nou["trams"], [(0.0, 2.0, 120.0, 4, 4),
                                        (2.0, 6.0, 90.0, 3, 4)])
        self.assertEqual(nou["offset"], 0.0)
        self.assertEqual(nou["marcadors"], [3.0])
        self.assertEqual((nou["pos"], nou["loop_a"], nou["loop_b"]),
                         (1.0, 0.0, 4.0))

    def test_retalla_final_ajusta_les_cobertures(self):
        nou = self.transforma(edita.RETALLA_FINAL, 6.0)
        self.assertEqual(nou["durada"], 6.0)
        self.assertEqual([a.fi for a in nou["acords"]], [4.0, 6.0])
        self.assertEqual(nou["seccions"][-1], (4.0, 6.0, "B", "B"))
        self.assertEqual(nou["trams"][-1], (4.0, 6.0, 90.0, 3, 4))
        self.assertEqual((nou["loop_a"], nou["loop_b"]), (1.0, 6.0))

    def test_silenci_inicial_crea_n_i_mante_la_seccio(self):
        nou = self.transforma(edita.SILENCI_INICI, 2.0)
        self.assertEqual(nou["durada"], 10.0)
        self.assertEqual([a.ini for a in nou["acords"]], [0.0, 2.0, 6.0])
        self.assertEqual(nou["acords"][0].payload, pipeline.FORAT_ACORD)
        self.assertEqual(nou["seccions"], [(0.0, 6.0, "A", "A"),
                                           (6.0, 10.0, "B", "B")])
        self.assertEqual(nou["trams"], [(0.0, 6.0, 120.0, 4, 4),
                                        (6.0, 10.0, 90.0, 3, 4)])
        self.assertEqual((nou["offset"], nou["marcadors"], nou["pos"]),
                         (4.0, [3.0, 7.0], 5.0))

    def test_silenci_final_estén_tots_els_carrils(self):
        nou = self.transforma(edita.SILENCI_FINAL, 2.0)
        self.assertEqual(nou["durada"], 10.0)
        self.assertEqual(nou["acords"][-1].payload, pipeline.FORAT_ACORD)
        self.assertEqual(nou["seccions"][-1], (4.0, 10.0, "B", "B"))
        self.assertEqual(nou["trams"][-1], (4.0, 10.0, 90.0, 3, 4))
        self.assertEqual(nou["offset"], 2.0)
