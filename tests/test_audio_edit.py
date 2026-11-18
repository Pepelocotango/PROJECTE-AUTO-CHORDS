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
from app import mapa_tempo, pipeline  # noqa: E402


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
            durada=8.0, operacio=operacio, delta=delta,
            pos=3.0, loop_a=1.0, loop_b=6.0, loop_on=True)

    def test_retalla_inici_desplaca_model_offset_i_loop(self):
        nou = self.transforma(edita.RETALLA_INICI, 2.0)
        self.assertEqual(nou["durada"], 6.0)
        self.assertEqual([a.ini for a in nou["acords"]], [0.0, 2.0])
        self.assertEqual(nou["seccions"], [(0.0, 2.0, "A", "A"),
                                           (2.0, 6.0, "B", "B")])
        self.assertEqual(nou["trams"], [(0.0, 2.0, 120.0, 4, 4),
                                        (2.0, 6.0, 90.0, 3, 4)])
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
        self.assertEqual((nou["marcadors"], nou["pos"]),
                         ([3.0, 7.0], 5.0))

    def test_retall_inici_mante_n_enter_i_ajusta_bpm(self):
        trams = [(0.0, 8.0, 120.0, 4, 4)]
        nou = edita.transforma_model(
            [pipeline.Clip(0.0, 8.0, ("C", "0"))],
            [(0.0, 8.0, "A", "A")], trams, [], 8.0,
            edita.RETALLA_INICI, 1.0)
        tram = nou["trams"][0]
        self.assertAlmostEqual(tram.fi, 7.0, places=6)
        self.assertAlmostEqual(float(tram.n), round(float(tram.n)),
                               places=9)
        self.assertAlmostEqual(float(tram.bpm), 4 * 4 * 60.0 / 7.0,
                               places=6)

    def test_retall_inici_elimina_primer_tram_i_conserva_unitat(self):
        from app import mapa_tempo
        trams = [
            mapa_tempo.TramMapa(
                0.0, 5.0, 120.0, "normal", "6/8", "", None, "negra_punt"),
            mapa_tempo.TramMapa(
                5.0, 15.0, 120.0, "normal", "4/4", "", None, "negra")]
        nou = edita.transforma_model(
            [pipeline.Clip(0.0, 15.0, ("C", "0"))],
            [(0.0, 15.0, "A", "A")], trams, [], 15.0,
            edita.RETALLA_INICI, 6.0)
        tram = nou["trams"][0]
        self.assertEqual(tram.beat_unit, "negra")
        self.assertAlmostEqual(float(tram.ini), 0.0, places=6)
        self.assertAlmostEqual(float(tram.fi), 9.0, places=6)

    def test_silenci_inici_mante_metadades_i_n_enter(self):
        from app import mapa_tempo
        trams = [mapa_tempo.TramMapa(
            0.0, 8.0, 120.0, "rubato", "4/4", "2+2", 4.0, "negra")]
        nou = edita.transforma_model(
            [pipeline.Clip(0.0, 8.0, ("C", "0"))],
            [(0.0, 8.0, "A", "A")], trams, [], 8.0,
            edita.SILENCI_INICI, 1.0)
        tram = nou["trams"][0]
        self.assertEqual(tram.tipus, "rubato")
        self.assertEqual(tram.agrupacio, "2+2")
        self.assertEqual(tram.beat_unit, "negra")
        self.assertAlmostEqual(float(tram.n), round(float(tram.n)),
                               places=9)

    def test_cap_edicio_deixa_n_fraccionari(self):
        from app import mapa_tempo
        trams_base = [
            mapa_tempo.TramMapa(0.0, 8.0, 120.0, "normal", "4/4"),
            mapa_tempo.TramMapa(8.0, 16.0, 90.0, "normal", "3/4")]
        for operacio in (edita.RETALLA_INICI, edita.RETALLA_FINAL,
                         edita.SILENCI_INICI, edita.SILENCI_FINAL):
            with self.subTest(operacio=operacio):
                nou = edita.transforma_model(
                    [pipeline.Clip(0.0, 16.0, ("C", "0"))],
                    [(0.0, 16.0, "A", "A")], list(trams_base), [], 16.0,
                    operacio, 1.0)
                for tram in nou["trams"]:
                    self.assertAlmostEqual(
                        float(tram.n), round(float(tram.n)), places=9)

    def test_silenci_final_estén_tots_els_carrils(self):
        nou = self.transforma(edita.SILENCI_FINAL, 2.0)
        self.assertEqual(nou["durada"], 10.0)
        self.assertEqual(nou["acords"][-1].payload, pipeline.FORAT_ACORD)
        self.assertEqual(nou["seccions"][-1], (4.0, 10.0, "B", "B"))
        self.assertEqual(nou["trams"][-1], (4.0, 10.0, 90.0, 3, 4))


class TestQuadraturaExtrems(unittest.TestCase):
    """Càlcul pur de N i plans d'inici/final (sense Qt)."""

    def setUp(self):
        self.bpm = 110.345
        self.durada = 10 * (4 * 60.0 / self.bpm)
        self.trams = [(0.0, self.durada, self.bpm, 4, 4)]

    def test_presets_inici_1_8s(self):
        esperat = {"ceil": 1, "floor": 0, "un": 1, "zero": 0}
        for mode, n in esperat.items():
            with self.subTest(mode=mode):
                self.assertEqual(edita.calcula_n_inici(
                    1.8, self.bpm, 4, 4, mode), n)
        self.assertEqual(edita.calcula_n_inici(
            1.8, self.bpm, 4, 4, "manual", 3), 3)

    def test_presets_inici_20s_aplaudiments(self):
        self.assertEqual(edita.calcula_n_inici(
            20.0, self.bpm, 4, 4, "ceil"), 10)
        self.assertEqual(edita.calcula_n_inici(
            20.0, self.bpm, 4, 4, "floor"), 9)
        self.assertEqual(edita.calcula_n_inici(
            20.0, self.bpm, 4, 4, "manual", 4), 4)

    def test_plan_inici_completa_o_retalla(self):
        p = edita.planifica_extrems(
            self.durada, 44100, self.trams, t_temps1=20.0, n_ini=10)
        self.assertEqual(p["n_ini"], 10)
        self.assertGreater(p["silenci_ini"], 0)
        self.assertEqual(p["retalla_ini"], 0)
        self.assertAlmostEqual(p["delta_ini"],
                               10 * (4 * 60.0 / self.bpm) - 20.0, 9)
        p = edita.planifica_extrems(
            self.durada, 44100, self.trams, t_temps1=20.0, n_ini=9)
        self.assertGreater(p["retalla_ini"], 0)
        self.assertEqual(p["silenci_ini"], 0)
        self.assertAlmostEqual(p["delta_ini"],
                               9 * (4 * 60.0 / self.bpm) - 20.0, 9)

    def test_inici_permet_bpm_i_compas_d_entrada_diferents(self):
        p = edita.planifica_extrems(
            self.durada, 44100, self.trams, t_temps1=2.0, n_ini=1,
            bpm_ini=120.0, num_ini=3, den_ini=4)
        self.assertAlmostEqual(p["target_ini"], 3 * 60.0 / 120.0, 9)
        tr = edita.transforma_model_extrems(
            [pipeline.Clip(0.0, self.durada, ("C", "0"))],
            [(0.0, self.durada, "A", "A")], self.trams, [],
            self.durada, p)
        self.assertEqual(tr["trams"][0].compassos, "3/4")
        self.assertAlmostEqual(float(tr["trams"][0].bpm), 120.0, 9)
        self.assertEqual(tr["trams"][0].n, 1)

    def test_unitat_de_pols_visible_es_propagada_al_model(self):
        trams = [mapa_tempo.TramMapa(
            0.0, 16.0, 120.0, "normal", "6/8", "", 8, "negra_punt")]
        p = edita.planifica_extrems(
            16.0, 1000, trams, t_temps1=2.0, n_ini=1,
            bpm_ini=90.0, num_ini=6, den_ini=8,
            beat_unit_ini="negra", aplica_inici=True,
            aplica_final=False)
        self.assertEqual(p["beat_unit_ini"], "negra")
        tr = edita.transforma_model_extrems(
            [pipeline.Clip(0.0, 16.0, ("C", "0"))],
            [(0.0, 16.0, "A", "A")], trams, [], 16.0, p)
        self.assertEqual(tr["trams"][0].beat_unit, "negra")
        self.assertAlmostEqual(tr["trams"][0].bpm, 90.0, 9)
        self.assertEqual(tr["trams"][0].n, 1)

    def test_unitat_de_pols_de_la_cua_es_propagada(self):
        trams = [mapa_tempo.TramMapa(
            0.0, 16.0, 120.0, "normal", "6/8", "", 8, "negra_punt")]
        p = edita.planifica_extrems(
            16.0, 1000, trams, aplica_inici=False, aplica_final=True,
            t_final=12.0, n_fi=1, bpm_fi=90.0, num_fi=6, den_fi=8,
            beat_unit_fi="negra")
        self.assertEqual(p["beat_unit_fi"], "negra")
        tr = edita.transforma_model_extrems(
            [pipeline.Clip(0.0, 16.0, ("C", "0"))],
            [(0.0, 16.0, "A", "A")], trams, [], 16.0, p)
        cua = tr["trams"][-1]
        self.assertEqual(cua.beat_unit, "negra")
        self.assertAlmostEqual(cua.bpm, 90.0, 9)

    def test_inici_zero_talla_fins_al_temps_1(self):
        p = edita.planifica_extrems(
            self.durada, 44100, self.trams, t_temps1=5.0, n_ini=0)
        self.assertEqual(p["n_ini"], 0)
        self.assertEqual(p["silenci_ini"], 0)
        self.assertGreater(p["retalla_ini"], 0)
        self.assertAlmostEqual(p["delta_ini"], -5.0, 9)

    def test_plan_final_afegeix_silenci_si_la_cua_no_quadra(self):
        trams = [(0.0, 20.0, self.bpm, 4, 4)]
        p = edita.planifica_extrems(
            20.0, 48000, trams, aplica_inici=False, aplica_final=True,
            n_fi=10)
        self.assertGreater(p["silenci_fi"], 0)
        self.assertEqual(p["retalla_fi"], 0)
        self.assertAlmostEqual(p["durada_nova"], 10 * 4 * 60.0 / self.bpm, 9)

    def test_durada_massa_curta_es_rebutja(self):
        with self.assertRaises(ValueError):
            edita.planifica_extrems(
                0.05, 44100, self.trams, t_temps1=0.04, n_ini=0)

    def test_plan_final_ceil_floor_i_proteccio(self):
        p = edita.planifica_extrems(
            self.durada, 44100, self.trams, aplica_inici=False,
            aplica_final=True, n_fi=10)
        self.assertEqual(p["n_fi"], 10)
        self.assertAlmostEqual(p["target_fi"], self.durada, 9)
        p = edita.planifica_extrems(
            self.durada, 44100, self.trams, aplica_inici=False,
            aplica_final=True, n_fi=9)
        self.assertAlmostEqual(p["delta_fi"],
                               9 * (4 * 60.0 / self.bpm) - self.durada, 9)
        with self.assertRaises(ValueError):
            edita.planifica_extrems(
                self.durada, 44100, self.trams, aplica_inici=False,
                aplica_final=True, n_fi=8, t_ultim_fort=19.0)

    def test_ceil_no_salta_de_compas_per_soroll_de_coma_flotant(self):
        bpm = 68.617874
        durada = 258.856471
        start = 3.529412
        D = 4 * 60.0 / bpm
        self.assertEqual(edita.calcula_n_fi(
            durada, start, bpm, 4, 4, "ceil"), 73)
        self.assertEqual(edita.calcula_n_inici(
            2 * D, bpm, 4, 4, "ceil"), 2)
        self.assertEqual(edita.calcula_n_inici(
            2 * D, bpm, 4, 4, "floor"), 2)

    def test_k_compassos_despres_del_fort(self):
        n = edita.n_fi_despres_fort(
            15.0, 0.0, self.bpm, 4, 4, 2)
        minim = edita.n_min_fi(15.0, 0.0, self.bpm, 4, 4)
        self.assertGreaterEqual(n, minim)
        self.assertEqual(edita.n_fi_despres_fort(
            15.0, 0.0, self.bpm, 4, 4, 1), minim)

    def test_precisio_a_mostra_44100_i_48000(self):
        for sr in (44100, 48000):
            with self.subTest(sr=sr):
                p = edita.planifica_extrems(
                    self.durada, sr, self.trams, t_temps1=1.8, n_ini=1)
                self.assertLessEqual(abs(
                    p["durada_nova"] - p["durada_nova_frames"] / sr),
                    1.0 / sr)

    def test_model_inici_crea_intro_i_despres_musica(self):
        acords = [pipeline.Clip(0.0, self.durada, ("C", "0"))]
        seccions = [(0.0, self.durada, "A", "A")]
        p = edita.planifica_extrems(
            self.durada, 44100, self.trams, t_temps1=1.8, n_ini=1)
        tr = edita.transforma_model_extrems(
            acords, seccions, self.trams, [2.0], self.durada, p)
        self.assertAlmostEqual(tr["durada"], p["durada_nova"], 9)
        self.assertEqual(tr["acords"][0].payload, pipeline.FORAT_ACORD)
        self.assertAlmostEqual(tr["acords"][0].fi, p["delta_ini"], 9)
        self.assertAlmostEqual(float(tr["trams"][0].fi),
                               p["target_ini"], 9)
        self.assertEqual(tr["trams"][0].n, 1)
        self.assertEqual(tr["marcadors"], [2.0 + p["delta_ini"]])
        for t in tr["trams"]:
            self.assertAlmostEqual(float(t.n), round(float(t.n)), 6)

    def test_model_final_retalla_i_protegeix(self):
        acords = [pipeline.Clip(0.0, self.durada, ("C", "0"))]
        seccions = [(0.0, self.durada, "A", "A")]
        p = edita.planifica_extrems(
            self.durada, 44100, self.trams, aplica_inici=False,
            aplica_final=True, n_fi=9, t_ultim_fort=15.0)
        tr = edita.transforma_model_extrems(
            acords, seccions, self.trams, [2.0], self.durada, p)
        self.assertAlmostEqual(tr["durada"], p["target_fi"], 9)
        self.assertAlmostEqual(float(tr["trams"][-1].fi), tr["durada"], 9)
        self.assertGreaterEqual(float(tr["trams"][-1].fi), 15.0)
        self.assertEqual(tr["trams"][-1].n, 9)
        self.assertAlmostEqual(float(tr["acords"][-1].fi), tr["durada"], 9)

    def test_model_final_talla_el_tram_i_deixa_la_cua_demanada(self):
        trams = [(0.0, 16.0, 120.0, 4, 4)]
        acords = [pipeline.Clip(0.0, 16.0, ("C", "0"))]
        seccions = [(0.0, 16.0, "A", "A")]
        p = edita.planifica_extrems(
            16.0, 1000, trams, aplica_inici=False, aplica_final=True,
            t_final=12.0, n_fi=1)
        self.assertEqual(p["n_cua"], 1)
        self.assertEqual(p["n_fi"], 7)
        tr = edita.transforma_model_extrems(
            acords, seccions, trams, [], 16.0, p)
        self.assertAlmostEqual(tr["durada"], 14.0, 9)
        self.assertEqual([(t.ini, t.fi, t.n) for t in tr["trams"]],
                         [(0.0, 12.0, 6.0), (12.0, 14.0, 1.0)])
        self.assertEqual(
            [(a.ini, a.fi) for a in tr["acords"]],
            [(0.0, 12.0), (12.0, 14.0)])
        self.assertIn("N", str(tr["acords"][-1].payload))
        self.assertEqual(
            [(s[0], s[1]) for s in tr["seccions"]],
            [(0.0, 12.0), (12.0, 14.0)])

    def test_model_final_ceil_conserva_bpm_i_tota_la_cua(self):
        trams = [(0.0, 20.0, self.bpm, 4, 4)]
        acords = [pipeline.Clip(0.0, 20.0, ("C", "0"))]
        seccions = [(0.0, 20.0, "A", "A")]
        p = edita.planifica_extrems(
            20.0, 44100, trams, aplica_inici=False,
            aplica_final=True, n_fi=10)
        tr = edita.transforma_model_extrems(
            acords, seccions, trams, [], 20.0, p)
        self.assertAlmostEqual(tr["durada"], p["durada_nova"], 9)
        self.assertAlmostEqual(float(tr["trams"][-1].bpm), self.bpm, 9)
        self.assertEqual(tr["trams"][-1].n, 10)
        self.assertAlmostEqual(float(tr["acords"][-1].fi), p["durada_nova"], 9)

    def test_model_combinat_es_una_sola_transformacio(self):
        acords = [pipeline.Clip(0.0, self.durada, ("C", "0"))]
        seccions = [(0.0, self.durada, "A", "A")]
        p = edita.planifica_extrems(
            self.durada, 44100, self.trams, t_temps1=1.8, n_ini=1,
            t_ultim_fort=15.0, n_fi=9, aplica_inici=True,
            aplica_final=True)
        tr = edita.transforma_model_extrems(
            acords, seccions, self.trams, [], self.durada, p)
        self.assertAlmostEqual(tr["durada"], p["durada_nova"], 9)
        self.assertAlmostEqual(float(tr["trams"][0].fi), p["target_ini"], 9)
        self.assertAlmostEqual(float(tr["trams"][-1].fi), tr["durada"], 9)
        self.assertEqual(tr["trams"][-1].n, 9)


    def test_model_final_recalcula_el_tram_normal_de_l_esquerra(self):
        trams = [(0.0, 16.0, 120.0, 4, 4)]
        acords = [pipeline.Clip(0.0, 16.0, ("C", "0"))]
        seccions = [(0.0, 16.0, "A", "A")]
        p = edita.planifica_extrems(
            16.0, 1000, trams, aplica_inici=False, aplica_final=True,
            t_final=11.0, n_fi=1)
        tr = edita.transforma_model_extrems(
            acords, seccions, trams, [], 16.0, p)
        esquerra, cua = tr["trams"]
        self.assertAlmostEqual(esquerra.fi, 11.0, 9)
        self.assertEqual(esquerra.n, 6.0)
        self.assertAlmostEqual(
            esquerra.bpm, 6 * 4 * 60.0 / 11.0, 9)
        self.assertEqual(cua.n, 1.0)

    def test_model_final_talla_dins_d_un_tram_anterior_i_esborra_la_resta(self):
        trams = [(0.0, 8.0, 120.0, 4, 4), (8.0, 16.0, 120.0, 4, 4)]
        acords = [pipeline.Clip(0.0, 8.0, ("C", "0")),
                  pipeline.Clip(8.0, 16.0, ("G", "0"))]
        seccions = [(0.0, 8.0, "A", "A"), (8.0, 16.0, "B", "B")]
        p = edita.planifica_extrems(
            16.0, 1000, trams, aplica_inici=False, aplica_final=True,
            t_final=10.0, n_fi=1)
        tr = edita.transforma_model_extrems(
            acords, seccions, trams, [], 16.0, p)
        self.assertEqual([(t.ini, t.fi, t.n) for t in tr["trams"]],
                         [(0.0, 8.0, 4.0), (8.0, 10.0, 1.0),
                          (10.0, 12.0, 1.0)])
        self.assertEqual([(a.ini, a.fi) for a in tr["acords"]],
                         [(0.0, 8.0), (8.0, 10.0), (10.0, 12.0)])
        self.assertIn("N", str(tr["acords"][-1].payload))

    def test_model_final_admet_bpm_i_compas_propis_de_la_cua(self):
        trams = [(0.0, 16.0, 120.0, 4, 4)]
        acords = [pipeline.Clip(0.0, 16.0, ("C", "0"))]
        seccions = [(0.0, 16.0, "A", "A")]
        p = edita.planifica_extrems(
            16.0, 1000, trams, aplica_inici=False, aplica_final=True,
            t_final=12.0, n_fi=1, bpm_fi=90.0, num_fi=3, den_fi=4)
        tr = edita.transforma_model_extrems(
            acords, seccions, trams, [], 16.0, p)
        self.assertAlmostEqual(tr["durada"], 14.0, 9)
        self.assertEqual(tr["trams"][0].n, 6)
        cua = tr["trams"][-1]
        self.assertAlmostEqual(cua.ini, 12.0, 9)
        self.assertAlmostEqual(cua.fi, 14.0, 9)
        self.assertEqual(cua.n, 1)
        self.assertAlmostEqual(cua.bpm, 90.0, 9)
        self.assertEqual(cua.compassos, "3/4")


class TestWavExtrems(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.origen = os.path.join(self.td, "o.wav")
        self.desti = os.path.join(self.td, "d.wav")

    def tearDown(self):
        shutil.rmtree(self.td, ignore_errors=True)

    def test_combinat_a_mostra_exacta(self):
        for sr in (44100, 48000):
            with self.subTest(sr=sr):
                _escriu_wav(self.origen, np.arange(sr, dtype="<i2"), sr=sr)
                durada = edita.escriu_wav_extrems(
                    self.origen, self.desti, silenci_ini=17,
                    retalla_fi=23)
                with wave.open(self.desti, "rb") as w:
                    self.assertEqual(w.getnframes(), sr + 17 - 23)
                self.assertAlmostEqual(durada, (sr - 6) / float(sr), 9)

    def test_retall_inici_i_silenci_final(self):
        _escriu_wav(self.origen, np.arange(1000, 11000, 1000), sr=1000)
        edita.escriu_wav_extrems(
            self.origen, self.desti, retalla_ini=2, silenci_fi=3)
        _sr, _c, valors = _llegeix_wav(self.desti)
        self.assertEqual(len(valors), 11)
        self.assertEqual(valors[-3:, 0].tolist(), [0, 0, 0])

    def test_invalid_no_toca_desti(self):
        _escriu_wav(self.origen, np.arange(1000, dtype="<i2"))
        with open(self.desti, "wb") as f:
            f.write(b"preserva")
        with self.assertRaises(ValueError):
            edita.escriu_wav_extrems(
                self.origen, self.desti, retalla_ini=1, silenci_ini=1)
        with open(self.desti, "rb") as f:
            self.assertEqual(f.read(), b"preserva")
