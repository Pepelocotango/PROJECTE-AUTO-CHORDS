# -*- coding: utf-8 -*-
"""Tests del motor `TempoMap` (mapa de tempo i compàs variables) — fase 1.

Comprova: equivalència amb el cas constant (l'app actual), integració
temps↔negres amb canvis de tempo, canvis de compàs (amb el compàs correcte
`num·4/den` negres), numeració des de l'offset, snap i combinació de mapes.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import pipeline  # noqa: E402
from app.tempo_map import TempoMap  # noqa: E402


class TestConstant(unittest.TestCase):
    """El cas BPM·compàs constant ha de coincidir amb l'app actual."""

    def test_quarters_i_inversa(self):
        tm = TempoMap.constant(120, 4, 4, durada=16.0)
        self.assertAlmostEqual(tm.quarters(2.0), 4.0)      # 0,5 s/negra
        self.assertAlmostEqual(tm.quarters(0.5), 1.0)
        self.assertAlmostEqual(tm.t_de_quarters(4.0), 2.0)
        self.assertAlmostEqual(tm.t_de_quarters(1.0), 0.5)

    def test_equivalencia_amb_pos_compas_a_la_graella(self):
        """Als instants de graella (on `pos_compas` no arrodoneix res) la
        etiqueta del mapa coincideix amb la funció clàssica."""
        tm = TempoMap.constant(120, 4, 4, durada=20.0)
        for k in range(0, 40):                     # cada corxera (0,25 s)
            t = 0.25 * k
            self.assertEqual(tm.label(t),
                             pipeline.pos_compas(t, 120, 4, False, 0.0),
                             f"t={t}")

    def test_pos_basica(self):
        tm = TempoMap.constant(120, 4, 4, durada=8.0)
        self.assertEqual(tm.pos(0.0), (1, 1, 1))
        self.assertEqual(tm.pos(0.5), (1, 2, 1))
        self.assertEqual(tm.pos(0.25), (1, 1, 3))
        self.assertEqual(tm.pos(2.0), (2, 1, 1))
        self.assertEqual(tm.label(4.0), "3.1.1")

    def test_snap(self):
        tm = TempoMap.constant(120, 4, 4, durada=10.0)
        self.assertAlmostEqual(tm.snap(0.6, ("beat", 1.0)), 0.5)
        self.assertAlmostEqual(tm.snap(2.1, ("bars", 1)), 2.0)
        self.assertAlmostEqual(tm.snap(0.6, ("beat", 0.5)), 0.5)

    def test_offset(self):
        tm = TempoMap.constant(120, 4, 4, durada=10.0, offset=1.0)
        self.assertEqual(tm.pos(1.0), (1, 1, 1))
        c, _b, _s = tm.pos(0.5)                     # compte enrere: compàs ≤ 0
        self.assertLessEqual(c, 0)


class TestCanviDeTempo(unittest.TestCase):
    def setUp(self):
        # 120 BPM [0,4) i 60 BPM [4,8)
        self.tm = TempoMap([(0.0, 4.0, 120, 4, 4), (4.0, 8.0, 60, 4, 4)])

    def test_integracio(self):
        self.assertAlmostEqual(self.tm.quarters(4.0), 8.0)    # 8 negres
        self.assertAlmostEqual(self.tm.quarters(8.0), 12.0)   # +4 negres (1 s/negra)
        self.assertAlmostEqual(self.tm.t_de_quarters(10.0), 6.0)

    def test_round_trip(self):
        for t in (0.0, 0.3, 1.7, 4.0, 5.5, 7.9):
            self.assertAlmostEqual(self.tm.t_de_quarters(self.tm.quarters(t)),
                                   t, places=6)

    def test_bpm_i_compassos(self):
        self.assertEqual(self.tm.bpm(1.0), 120)
        self.assertEqual(self.tm.bpm(6.0), 60)
        # compàs de 4 negres: a 120 → 2 s; a 60 → 4 s
        self.assertEqual(self.tm.label(0.0), "1.1.1")
        self.assertEqual(self.tm.label(2.0), "2.1.1")
        self.assertEqual(self.tm.label(4.0), "3.1.1")
        self.assertEqual(self.tm.label(8.0), "4.1.1")


class TestCanviDeCompas(unittest.TestCase):
    def setUp(self):
        # 4/4 [0,4) i 3/4 [4,8), tot a 120 BPM
        self.tm = TempoMap([(0.0, 4.0, 120, 4, 4), (4.0, 8.0, 120, 3, 4)])

    def test_bar_lengths(self):
        self.assertEqual(self.tm.label(0.0), "1.1.1")
        self.assertEqual(self.tm.label(2.0), "2.1.1")   # 4/4 = 2 s
        self.assertEqual(self.tm.label(4.0), "3.1.1")   # canvi de compàs
        self.assertEqual(self.tm.label(5.5), "4.1.1")   # 3/4 = 1,5 s

    def test_temps_dins_del_compas(self):
        self.assertEqual(self.tm.pos(5.0), (3, 3, 1))   # 2 negres dins del 3/4
        self.assertEqual(self.tm.signatura(6.0), (3, 4))
        self.assertEqual(self.tm.signatura(1.0), (4, 4))

    def test_6_8(self):
        # 6/8 → compàs de 3 negres (1,5 s a 120) i temps de 0,5 negres
        tm = TempoMap.constant(120, 6, 8, durada=10.0)
        self.assertEqual(tm.label(0.0), "1.1.1")
        self.assertEqual(tm.label(1.5), "2.1.1")
        self.assertAlmostEqual(tm.snap(0.3, ("beat", 1.0)), 0.25)


class TestCombinacio(unittest.TestCase):
    def test_des_de_maps(self):
        tempo = [(0.0, 4.0, 120), (4.0, 8.0, 60)]
        compas = [(0.0, 4.0, 4, 4), (4.0, 8.0, 3, 4)]
        tm = TempoMap.des_de_maps(tempo, compas)
        self.assertEqual(len(tm.trams), 2)
        self.assertEqual((tm.trams[0].bpm, tm.trams[0].num, tm.trams[0].den),
                         (120.0, 4, 4))
        self.assertEqual((tm.trams[1].bpm, tm.trams[1].num, tm.trams[1].den),
                         (60.0, 3, 4))
        self.assertEqual(tm.label(4.0), "3.1.1")

    def test_buit(self):
        tm = TempoMap([])
        self.assertEqual(tm.bpm(1.0), 120)
        self.assertEqual(tm.signatura(1.0), (4, 4))
        self.assertEqual(tm.pos(0.0), (1, 1, 1))

    def test_tram_unic_estes(self):
        # un sol tros que arrenca a 2 s → s'estén cap a 0 amb el seu valor
        tm = TempoMap([(2.0, 10.0, 90, 3, 4)])
        self.assertEqual(tm.trams[0].ini, 0.0)
        self.assertEqual(tm.bpm(0.0), 90)
        self.assertEqual(tm.signatura(1.0), (3, 4))


class TestSnapIConversions(unittest.TestCase):
    def test_snap_a_compassos(self):
        tm = TempoMap([(0.0, 4.0, 120, 4, 4), (4.0, 8.0, 120, 3, 4)])
        self.assertAlmostEqual(tm.snap(3.9, ("bars", 1)), 4.0)
        self.assertAlmostEqual(tm.snap(4.8, ("bars", 1)), 5.5)

    def test_t_de_pos(self):
        tm = TempoMap.constant(120, 4, 4, durada=20.0)
        self.assertAlmostEqual(tm.t_de_pos(2, 1), 2.0)
        self.assertAlmostEqual(tm.t_de_pos(3, 2), 4.5)


class TestPersistencia(unittest.TestCase):
    """Fase 2: `tempo.csv` (`inici,fi,bpm`) i `compas.csv` (`inici,fi,num,den`)."""

    def test_round_trip(self):
        import tempfile
        td = tempfile.mkdtemp()
        trams = [(0.0, 4.0, 120.0, 4, 4), (4.0, 8.0, 90.0, 3, 4)]
        pipeline.desa_tempo_map(td, trams)
        self.assertTrue(os.path.isfile(os.path.join(td, "tempo.csv")))
        self.assertTrue(os.path.isfile(os.path.join(td, "compas.csv")))
        self.assertEqual(pipeline.llegeix_tempo_map(td, 120, 4, 4, 8.0), trams)

    def test_sense_fitxers_es_constant(self):
        import tempfile
        td = tempfile.mkdtemp()                    # carpeta buida
        self.assertEqual(pipeline.llegeix_tempo_map(td, 100.0, 3, 4, 20.0),
                         [(0.0, 20.0, 100.0, 3, 4)])

    def test_tempo_csv_format(self):
        import tempfile
        td = tempfile.mkdtemp()
        ruta = os.path.join(td, "tempo.csv")
        pipeline.desa_tempo_csv(ruta, [(0.0, 2.5, 105.315, 4, 4)])
        with open(ruta, encoding="utf-8") as f:
            linia = f.read().strip()
        self.assertEqual(linia, "0.00,2.50,105.315")


class TestGraellaAmbMapa(unittest.TestCase):
    """Fase 3: la graella/regle/snap amb un mapa **variable**.

    4/4 a 120 BPM [0,4) i 3/4 a 60 BPM [4,8): els compassos fan 2 s i 3 s.
    """

    def setUp(self):
        from app import timeline_base as tb
        self.tb = tb
        self.mapa = TempoMap([(0.0, 4.0, 120.0, 4, 4), (4.0, 8.0, 60.0, 3, 4)])

    def test_grid_lines_bar(self):
        self.assertEqual(
            [round(t, 3) for t in self.mapa.grid_lines(0.0, 8.0, "bar")],
            [0.0, 2.0, 4.0, 7.0])

    def test_grid_lines_beat(self):
        self.assertEqual(
            [round(t, 3) for t in self.mapa.grid_lines(0.0, 5.0, "beat")],
            [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0])

    def test_fmt_pos_mapa(self):
        f = self.tb.fmt_pos
        self.assertEqual(f(0.0, True, 120, 4, 0.0, mapa=self.mapa), "1.1")
        self.assertEqual(f(2.0, True, 120, 4, 0.0, mapa=self.mapa), "2.1")
        self.assertEqual(f(4.0, True, 120, 4, 0.0, mapa=self.mapa), "3.1")

    def test_snap_mapa(self):
        st = self.tb.snap_time
        self.assertAlmostEqual(st(1.7, True, 120, 4, 60.0, 0.0,
                                  mapa=self.mapa), 1.75)
        self.assertAlmostEqual(st(4.1, True, 120, 4, 60.0, 0.0,
                                  mapa=self.mapa), 4.0)

    def test_constant_identic(self):
        """Amb un mapa constant, la via del mapa és IDÈNTICA a la uniforme."""
        const = TempoMap.constant(120, 4, 4, durada=10.0)
        for t in (0.0, 0.25, 1.7, 3.9, 7.05):
            self.assertEqual(
                self.tb.fmt_pos(t, True, 120, 4, 0.0, mapa=const),
                self.tb.fmt_pos(t, True, 120, 4, 0.0))

    def test_plan_constant_identic(self):
        const = TempoMap.constant(120, 4, 4, durada=10.0)
        self.assertEqual(
            self.tb.grid_plan(True, 120, 4, 60.0, 800.0, mapa=const),
            self.tb.grid_plan(True, 120, 4, 60.0, 800.0))


class TestEdicioMapa(unittest.TestCase):
    """Utilitats pures d'edició del mapa (les del diàleg)."""

    def test_normalitza_contigu(self):
        from app import tempo_map as tmm
        trams = tmm.normalitza_trams(
            [(2.0, 2.0, 90.0, 3, 4), (0.0, 0.0, 120.0, 4, 4)], 10.0)
        self.assertEqual(trams, [(0.0, 2.0, 120.0, 4, 4),
                                 (2.0, 10.0, 90.0, 3, 4)])

    def test_normalitza_capcalera(self):
        from app import tempo_map as tmm
        trams = tmm.normalitza_trams([(3.0, 3.0, 90.0, 3, 4)], 10.0)
        self.assertEqual(trams[0], (0.0, 3.0, 90.0, 3, 4))   # arrenca a 0

    def test_afegeix_i_elimina(self):
        from app import tempo_map as tmm
        base = [(0.0, 10.0, 120.0, 4, 4)]
        nou = tmm.normalitza_trams(tmm.afegeix_tall(base, 4.0), 10.0)
        self.assertEqual(len(nou), 2)
        self.assertEqual(nou[1][0], 4.0)
        self.assertEqual(nou[1][2], 120.0)          # hereta el tempo del tros
        self.assertEqual(
            tmm.normalitza_trams(tmm.elimina_tall(nou, 1), 10.0),
            [(0.0, 10.0, 120.0, 4, 4)])

    def test_dialog_trams_round_trip(self):
        from app import tempo_map as tmm
        trams = [(0.0, 4.0, 120.0, 4, 4), (4.0, 8.0, 90.0, 3, 4)]
        tm = TempoMap(tmm.normalitza_trams(trams, 8.0))
        self.assertEqual(tm.label(0.0), "1.1.1")
        self.assertEqual(tm.signatura(5.0), (3, 4))


class TestExportsMapa(unittest.TestCase):
    """Fase 5: `pos_compas` (etiqueta d'export) mapa-conscient."""

    def test_pos_compas_mapa(self):
        mapa = TempoMap([(0.0, 4.0, 120.0, 4, 4), (4.0, 8.0, 60.0, 3, 4)])
        self.assertEqual(pipeline.pos_compas(0.0, 120, 4, False, 0.0, mapa),
                         "1.1.1")
        self.assertEqual(pipeline.pos_compas(4.0, 120, 4, False, 0.0, mapa),
                         "3.1.1")
        self.assertEqual(pipeline.pos_compas(6.0, 120, 4, False, 0.0, mapa),
                         "3.3.1")

    def test_pos_compas_constant_identic(self):
        const = TempoMap.constant(120, 4, 4, durada=10.0)
        for t in (0.0, 0.5, 2.0):
            self.assertEqual(
                pipeline.pos_compas(t, 120, 4, False, 0.0, const),
                pipeline.pos_compas(t, 120, 4, False, 0.0))


class TestInferencia(unittest.TestCase):
    """Fase 5c: `infereix_trams_beat` (mapa a partir dels temps detectats)."""

    def test_tempo_constant(self):
        from app import tempo_map as tmm
        beats = [i * 0.5 for i in range(40)]          # 120 BPM
        trams = tmm.infereix_trams_beat(beats, 20.0, 4, 4)
        self.assertEqual(len(trams), 1)
        self.assertAlmostEqual(trams[0][2], 120.0, places=1)

    def test_canvi_de_tempo(self):
        from app import tempo_map as tmm
        a = [i * 0.5 for i in range(21)]              # 120 BPM (0..10 s)
        b = [10.0 + i * 1.0 for i in range(1, 11)]    # 60 BPM (10..20 s)
        trams = tmm.infereix_trams_beat(a + b, 20.0, 4, 4)
        self.assertEqual(len(trams), 2)
        self.assertAlmostEqual(trams[0][2], 120.0, places=1)
        self.assertAlmostEqual(trams[1][2], 60.0, places=1)
        self.assertLessEqual(trams[1][0], 11.0)       # la frontera ~10 s
        self.assertGreaterEqual(trams[1][0], 8.0)

    def test_poques_dades(self):
        from app import tempo_map as tmm
        self.assertEqual(len(tmm.infereix_trams_beat([0.0, 0.5], 10.0)), 1)
        self.assertEqual(len(tmm.infereix_trams_beat([], 10.0)), 1)


if __name__ == "__main__":
    unittest.main()
