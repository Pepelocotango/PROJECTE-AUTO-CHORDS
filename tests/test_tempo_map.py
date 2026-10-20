"""Suite de test — Tempo Map

> Suite CONSOLIDADA (Fase 4, 2026-10-19): fusiona 8 mòduls de test que abans
> vivien separats a `tests/`. Cada bloc conserva el seu codi original íntegre
> (només s'han renombrat els símbols de nivell superior que xocaven i s'han
> unificat els imports). Cobertura intacta: cap test eliminat.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene: esborra els temporals en plegar

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
import unittest.mock  # noqa: F401  (alguns tests fan servir unittest.mock)
from app import pipeline
from app.tempo_map import TempoMap
import numpy as np
from app import metronom
from app import tempo_map as tm
import tempfile
import wave
from app import graella
from app import visor as visor_mod
from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtGui import QKeyEvent
from app import config
from app import main as app_main
import math
from app import timeline_base as tb



def tearDownModule():
    _quantitza_tearDownModule()
    _snap_tearDownModule()


# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_tempo_map.py
# ══════════════════════════════════════════════════════════════════════════
# -*- coding: utf-8 -*-
"""Tests del motor `TempoMap` (mapa de tempo i compàs variables) — fase 1.

Comprova: equivalència amb el cas constant (l'app actual), integració
temps↔negres amb canvis de tempo, canvis de compàs (amb el compàs correcte
`num·4/den` negres), numeració des de l'offset, snap i combinació de mapes.
"""




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
        self.assertEqual(tm.pos(0.25), (1, 1, 5))
        self.assertEqual(tm.pos(2.0), (2, 1, 1))
        self.assertEqual(tm.label(4.0), "3.1.1")

    def test_pos_1_32_i_vora_de_compas(self):
        tm = TempoMap.constant(101, 4, 4, durada=20.0)
        self.assertEqual(tm.pos(0.125 * (60.0 / 101.0) * 2),
                         (1, 1, 3))
        # 9,5 s a 101 BPM és pràcticament 16 negres (compàs 5): la vista a
        # 1/32 ha de coincidir amb `pos_compas`, no quedar-se al compàs 4.
        from app import pipeline
        self.assertEqual(tm.label(9.5), pipeline.pos_compas(9.5, 101, 4))

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

    def test_tempo_a_mig_compas_no_reinicia_el_compas(self):
        """Un canvi de TEMPO a mig compàs no és una frontera de compàs."""
        tm = TempoMap([(0.0, 3.0, 120, 4, 4), (3.0, 8.0, 60, 4, 4)])
        starts = [round(t, 6) for _q, t, _n, _d in tm.compassos()]
        self.assertEqual(starts, [0.0, 2.0, 5.0])
        self.assertEqual(tm.label(0.0), "1.1.1")
        self.assertEqual(tm.label(2.0), "2.1.1")
        self.assertEqual(tm.label(3.0), "2.3.1")
        self.assertEqual(tm.label(5.0), "3.1.1")
        self.assertEqual([round(t, 6) for t in tm.grid_lines(0.0, 8.0,
                                                             kind="bar")],
                         [0.0, 2.0, 5.0])

    def test_t_de_pos_amb_canvi_de_tempo(self):
        tm = TempoMap([(0.0, 3.0, 120, 4, 4), (3.0, 8.0, 60, 4, 4)])
        self.assertAlmostEqual(tm.t_de_pos(2, 1), 2.0, places=6)
        self.assertAlmostEqual(tm.t_de_pos(2, 3), 3.0, places=6)
        self.assertAlmostEqual(tm.t_de_pos(3, 1), 5.0, places=6)
        self.assertAlmostEqual(tm.t_de_pos(3, 2), 6.0, places=6)


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

    def test_canvi_de_compas_a_mig_compas(self):
        """Un canvi de compàs a mig compàs sí que obri un compàs nou."""
        tm = TempoMap([(0.0, 3.0, 120, 4, 4), (3.0, 8.0, 120, 3, 4)])
        starts = [round(t, 6) for _q, t, _n, _d in tm.compassos()]
        self.assertEqual(starts, [0.0, 2.0, 3.0, 4.5, 6.0, 7.5])
        self.assertEqual(tm.label(2.0), "2.1.1")
        self.assertEqual(tm.label(3.0), "3.1.1")
        self.assertEqual(tm.label(4.5), "4.1.1")

    def test_6_8(self):
        # 6/8 → compàs de 3 negres (1,5 s a 120) i temps de 0,5 negres
        tm = TempoMap.constant(120, 6, 8, durada=10.0)
        self.assertEqual(tm.label(0.0), "1.1.1")
        self.assertEqual(tm.label(1.5), "2.1.1")
        self.assertAlmostEqual(tm.snap(0.3, ("beat", 1.0)), 0.25)


class TestCompassosEnters(unittest.TestCase):
    """Contracte de `docs/REGLES_TEMPS_GRID.md` (trams interiors enters)."""

    BASE = [(0.0, 10.0, 120.0, 4, 4), (10.0, 30.0, 90.0, 3, 4)]

    def test_mapa_valid(self):
        self.assertEqual(tm.valida_i_normalitza_compassos(self.BASE, 30.0),
                         self.BASE)

    def test_fusiona_trams_iguals(self):
        trams = [(0.0, 5.0, 120.0, 4, 4), (5.0, 10.0, 120.0, 4, 4),
                 (10.0, 20.0, 90.0, 4, 4)]
        self.assertEqual(tm.fusiona_trams_iguals(trams, 20.0),
                         [(0.0, 10.0, 120.0, 4, 4),
                          (10.0, 20.0, 90.0, 4, 4)])

    def test_frontera_a_mig_compas_es_rebutja(self):
        with self.assertRaises(ValueError):
            tm.valida_i_normalitza_compassos(
                [(0.0, 4.0, 90.0, 4, 4), (4.0, 10.0, 120.0, 3, 4)], 10.0)

    def test_primer_parcial_amb_offset(self):
        # El primer tram comença en un compte enrere parcial; la resta són
        # compassos sencers des de l'offset.
        trams = [(0.0, 3.0, 120.0, 4, 4), (3.0, 9.0, 120.0, 4, 4)]
        self.assertEqual(tm.valida_i_normalitza_compassos(
            trams, 9.0, offset=1.0), trams)

    def test_canviar_bpm_conserva_compassos_i_arrossega(self):
        nous = tm.canvia_bpm_compassos(self.BASE, 0, 100.0, 30.0)
        self.assertEqual(nous, [(0.0, 12.0, 100.0, 4, 4),
                                (12.0, 30.0, 90.0, 3, 4)])

    def test_ultim_tram_absorbeix(self):
        nous = tm.canvia_bpm_compassos(self.BASE, 1, 100.0, 30.0)
        self.assertEqual(nous, [(0.0, 10.0, 120.0, 4, 4),
                                (10.0, 30.0, 100.0, 3, 4)])

    def test_snap_frontera_a_compas(self):
        tall, nous = tm.snap_frontera_compas(self.BASE, 0, 11.5, 30.0)
        self.assertAlmostEqual(tall, 12.0, places=6)
        self.assertEqual(nous, [(0.0, 12.0, 120.0, 4, 4),
                                (12.0, 30.0, 90.0, 3, 4)])

    def test_parteix_a_compas(self):
        tall, nous = tm.parteix_a_compas(self.BASE, 0, 5.0, 30.0)
        self.assertIn(round(tall, 6), (4.0, 6.0))
        self.assertEqual(len(nous), 3)
        self.assertTrue(all(
            abs((t[1] - t[0]) / tm.durada_compas(t[2], t[3], t[4])
                - round((t[1] - t[0]) / tm.durada_compas(t[2], t[3], t[4])))
            < 1e-5 for t in nous[1:-1]))

    def test_no_es_parteix_un_unic_compas(self):
        trams = [(0.0, 2.0, 120.0, 4, 4), (2.0, 6.0, 120.0, 4, 4)]
        with self.assertRaises(ValueError):
            tm.parteix_a_compas(trams, 0, 1.0, 6.0)


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

    def test_csv_editat_a_ma_entra_normalitzat(self):
        """Els CSVs del mapa poden estar editats a mà: el que ix de la CARREGA
        és el model, i ha de complir les regles 1, 2, 4 i 8.

        Auditoria 18-10-2026: `llegeix_tempo_map` retornava els trams tal qual,
        així que un forat (tram que no arrenca a 0), un inici negatiu o un bpm
        o compàs impossibles entraven a l'app.
        """
        import tempfile
        td = tempfile.mkdtemp()
        with open(os.path.join(td, "tempo.csv"), "w", encoding="utf-8") as f:
            f.write("ini_s,fi_s,bpm\n4.0,10.0,90\n-2.0,20.0,0\n")
        with open(os.path.join(td, "compas.csv"), "w", encoding="utf-8") as f:
            f.write("ini_s,fi_s,beats,beat_type\n4.0,10.0,3,4\n-2.0,20.0,0,0\n")
        trams = pipeline.llegeix_tempo_map(td, 120.0, 4, 4, 30.0)
        self.assertEqual(trams[0][0], 0.0)                    # comença a 0
        self.assertEqual(trams, [(0.0, 4.0, 120.0, 4, 4),      # valors valids
                                 (4.0, 30.0, 90.0, 3, 4)])     # i acaba a la WAV

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
        self.assertEqual(linia, "0.000000,2.500000,105.315000")


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

    def test_elimina_tall_el_primer_ancora_a_zero(self):
        """El mapa sempre comenca a 0: esborrar el 1r tros no hi deixa forat.

        Abans el nou primer quedava amb l'inici vell i `normalitza_trams` hi
        afegia un tros duplicat -> mai es podia arribar a un sol tram.
        """
        from app import tempo_map as tmm
        trams = [(0.0, 6.0, 120.0, 4, 4), (6.0, 20.0, 90.0, 3, 4),
                 (20.0, 30.0, 140.0, 4, 4)]
        mig = tmm.normalitza_trams(tmm.elimina_tall(trams, 1), 30.0)
        self.assertEqual([(t[0], t[1], t[2]) for t in mig],
                         [(0.0, 20.0, 120.0), (20.0, 30.0, 140.0)])
        # esborrar el 1r: el que era el 2n passa a ser el 1r i s'ancora a 0
        # (amb el SEU tempo, no amb el del tros esborrat)
        un = tmm.normalitza_trams(tmm.elimina_tall(trams, 0), 30.0)
        self.assertEqual([(t[0], t[1], t[2]) for t in un],
                         [(0.0, 20.0, 90.0), (20.0, 30.0, 140.0)])
        # ... i tambe es pot deixar el mapa amb un sol tros des de dos
        dos = tmm.normalitza_trams([(0.0, 6.0, 120.0, 4, 4),
                                    (6.0, 30.0, 90.0, 3, 4)], 30.0)
        self.assertEqual(len(tmm.normalitza_trams(tmm.elimina_tall(dos, 0),
                                                   30.0)), 1)

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


class TestGuia(unittest.TestCase):
    """Anàlisi guiat: el tall lliure del carril i les finestres de 16 temps.

    Disseny: `docs/ANALISI_GUIAT.md`. Cada resultat ha de passar el contracte
    de compassos enters (`valida_i_normalitza_compassos`) amb l'offset del
    compàs 1, que és com el consumirà l'app.
    """

    DURADA = 30.0

    def test_parteix_al_mig_mateixos_valors(self):
        p = tm.parteix_trams_a([(0.0, 10.0, 120.0, 4, 4)], 2.5, 10.0)
        self.assertEqual([(s[0], s[1], s[2], s[3], s[4]) for s in p],
                         [(0.0, 2.5, 120.0, 4, 4), (2.5, 10.0, 120.0, 4, 4)])

    def test_parteix_damunt_frontera_no_duplica(self):
        p = tm.parteix_trams_a([(0.0, 5.0, 120.0, 4, 4), (5.0, 10.0, 90.0, 4, 4)],
                               5.0, 10.0)
        self.assertEqual([(s[0], s[1], s[2]) for s in p],
                         [(0.0, 5.0, 120.0), (5.0, 10.0, 90.0)])

    def test_parteix_fora_rang_no_canvia_res(self):
        base = [(0.0, 10.0, 120.0, 4, 4)]
        for t in (0.0, -1.0, 10.0, 12.0):
            self.assertEqual(tm.parteix_trams_a(base, t, 10.0), base)

    def test_finestra_44(self):
        p = tm.parteix_trams_a([(0.0, self.DURADA, 120.0, 4, 4)], 2.5,
                               self.DURADA)
        nous, t_seg, m = tm.trams_finestra_guia(p, 2.5, 100.0, 4, 4,
                                                self.DURADA)
        # bar(100, 4/4) = 2.4s; 16 temps = 9.6s → m = 4 compàsos exactes
        self.assertEqual(m, 4)
        self.assertAlmostEqual(t_seg, 12.1, places=6)
        self.assertEqual([(s[0], s[1], s[2], s[3], s[4]) for s in nous],
                         [(0.0, 2.5, 120.0, 4, 4),
                          (2.5, 12.1, 100.0, 4, 4),
                          (12.1, 30.0, 100.0, 4, 4)])
        v = tm.valida_i_normalitza_compassos(nous, self.DURADA, offset=2.5)
        self.assertEqual(len(v), 3)

    def test_finestra_34_m_five(self):
        """Camí ANTIC (`beats=16`, compatibilitat): en 3/4 eixen 5 compassos.

        L'app ja no l'usa (passa `n_compassos`), però es conserva perquè el
        paràmetre `beats` seguisca funcionant per a qui cride la funció.
        """
        p = tm.parteix_trams_a([(0.0, self.DURADA, 120.0, 4, 4)], 1.0,
                               self.DURADA)
        _, t_seg, m = tm.trams_finestra_guia(p, 1.0, 120.0, 3, 4,
                                             self.DURADA)
        # bar(120, 3/4) = 1.5s; 16 temps = 8.0s → m = round(5.333) = 5
        self.assertEqual(m, 5)
        self.assertAlmostEqual(t_seg, 1.0 + 5 * 1.5, places=6)
        _, t_seg, m = tm.trams_finestra_guia(p, 1.0, 120.0, 3, 4,
                                             self.DURADA)
        nous2, _, _ = tm.trams_finestra_guia(p, 1.0, 120.0, 3, 4,
                                             self.DURADA)
        v = tm.valida_i_normalitza_compassos(nous2, self.DURADA, offset=1.0)
        self.assertTrue(len(v) >= 3)

    def test_finestra_n_compassos_34(self):
        """`n_compassos` mana: 4 compassos de 3/4 (no els 5 del mode `beats`)."""
        p = tm.parteix_trams_a([(0.0, self.DURADA, 120.0, 4, 4)], 1.0,
                               self.DURADA)
        _, t_seg, m = tm.trams_finestra_guia(p, 1.0, 120.0, 3, 4,
                                             self.DURADA, n_compassos=4)
        self.assertEqual(m, 4)
        self.assertAlmostEqual(t_seg, 1.0 + 4 * 1.5, places=6)   # 1,5 s/compàs
        nous, _, _ = tm.trams_finestra_guia(p, 1.0, 120.0, 3, 4,
                                           self.DURADA, n_compassos=4)
        v = tm.valida_i_normalitza_compassos(nous, self.DURADA, offset=1.0)
        self.assertAlmostEqual(v[1][1], 7.0, places=6)

    def test_finestra_n_compassos_68(self):
        p = tm.parteix_trams_a([(0.0, self.DURADA, 100.0, 4, 4)], 2.0,
                               self.DURADA)
        # 6/8 a 100 BPM: el «compàs» són 3 negres = 1,8 s
        self.assertAlmostEqual(tm.durada_compas(100.0, 6, 8), 1.8, places=6)
        _, t_seg, m = tm.trams_finestra_guia(p, 2.0, 100.0, 6, 8,
                                             self.DURADA, n_compassos=2)
        self.assertEqual(m, 2)
        self.assertAlmostEqual(t_seg, 2.0 + 2 * 1.8, places=6)

    def test_finestra_n_compassos_limits(self):
        p = tm.parteix_trams_a([(0.0, self.DURADA, 120.0, 4, 4)], 1.0,
                               self.DURADA)
        for m_in, m_out in ((1, 1), (8, 8), (0, 1), (-3, 1), (2, 2)):
            _, _, m = tm.trams_finestra_guia(p, 1.0, 120.0, 4, 4, self.DURADA,
                                             n_compassos=m_in)
            self.assertEqual(m, m_out)

    def test_finestra_ultima_absorbeix(self):
        """Si la finestra sobrepassa la fi de la WAV, un sol tram etern."""
        p = tm.parteix_trams_a([(0.0, self.DURADA, 120.0, 4, 4)], 2.5,
                               self.DURADA)
        trams = p
        for t in (2.5, 12.1, 21.7):
            r = tm.trams_finestra_guia(trams, t, 100.0, 4, 4, self.DURADA)
            trams, t_seg, m = r
        self.assertAlmostEqual(t_seg, 21.7 + 9.6, places=6)  # 31.3 > 30
        # però la durada es retalla: l'últim tram acaba a durada
        self.assertAlmostEqual(trams[-1][1], self.DURADA, places=6)
        v = tm.valida_i_normalitza_compassos(trams, self.DURADA, offset=2.5)
        self.assertAlmostEqual(v[-1][1], self.DURADA, places=6)

    def test_finestra_invalida_retorna_none(self):
        p = tm.parteix_trams_a([(0.0, self.DURADA, 120.0, 4, 4)], 2.5,
                               self.DURADA)
        self.assertIsNone(tm.trams_finestra_guia(p, self.DURADA, 100.0, 4, 4,
                                                 self.DURADA))
        self.assertIsNone(tm.trams_finestra_guia(p, 2.5, 0.0, 4, 4,
                                                 self.DURADA))

    def test_bucle_complet_valida(self):
        """Simulació de 4 finestres com les faria l'app: sempre vàlid."""
        trams = tm.parteix_trams_a([(0.0, self.DURADA, 120.0, 4, 4)], 2.5,
                                   self.DURADA)
        off = 2.5
        confirmats = 0
        for bpm in (94.0, 58.0, 122.0, 94.0):
            r = tm.trams_finestra_guia(trams, float(trams[-1][0]), bpm,
                                       4, 4, self.DURADA)
            self.assertIsNotNone(r)
            trams, t_seg, m = r
            self.assertGreaterEqual(m, 1)
            v = tm.valida_i_normalitza_compassos(trams, self.DURADA,
                                                 offset=off)
            self.assertAlmostEqual(v[-1][1], self.DURADA, places=6)
            confirmats += 1
            if t_seg >= self.DURADA - 1e-6:
                break                   # última finestra: l'app s'atura aquí
        # al final: fusiona els iguals (cap adjacent d'iguals en aquest cas)
        fm = tm.fusiona_trams_iguals(trams, self.DURADA)
        v = tm.valida_i_normalitza_compassos(fm, self.DURADA, offset=off)
        self.assertEqual(len(v), 1 + confirmats)   # pre-música + confirmats


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

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_metronom.py
# ══════════════════════════════════════════════════════════════════════════
"""Metrònom: clics i accents, amb BPM fix i amb **mapa de tempo/compàs**.

Regla d'or #5: el mapa és la font del tempo. El metrònom ha de seguir-lo; abans
anava sempre amb el BPM fix de la barra i, a partir del primer canvi de tempo, es
desalineava (auditoria 18-10-2026).
"""




SR = 44100


def _silenci(segons):
    return b"\x00\x00" * int(SR * segons)


def _clics(mono, llindar=1500):
    """Instants (s) on arrenca cada clic (les regions no nul·les)."""
    arr = np.abs(np.frombuffer(mono, dtype=np.int16))
    idx = np.flatnonzero(arr > llindar)
    if idx.size == 0:
        return []
    talls = np.flatnonzero(np.diff(idx) > SR // 50)   # 20 ms de separació
    inicis = np.concatenate(([idx[0]], idx[talls + 1]))
    return [round(i / SR, 2) for i in inicis]


class TestMetronom(unittest.TestCase):

    def test_sense_volum_no_toca_res(self):
        s = _silenci(2)
        self.assertEqual(metronom.mescla_metronom(s, SR, 0.0, 120.0, 4, 0.0), s)

    def test_bpm_fix_clics_cada_temps(self):
        """A 120 BPM el temps fa 0,5 s: clics a 0, 0,5, 1,0, 1,5…"""
        out = metronom.mescla_metronom(_silenci(2), SR, 0.0, 120.0, 4)
        self.assertEqual(_clics(out), [0.0, 0.5, 1.0, 1.5])

    def test_accent_al_primer_temps_del_compas(self):
        """El clic del temps 1 sona més fort que els altres (4/4 → cada 4)."""
        out = metronom.mescla_metronom(_silenci(2), SR, 0.0, 120.0, 4)
        arr = np.abs(np.frombuffer(out, dtype=np.int16))
        fort = arr[int(0.0 * SR):int(0.1 * SR)].max()
        fluix = arr[int(0.5 * SR):int(0.6 * SR)].max()
        self.assertGreater(fort, fluix)

    def test_amb_mapa_segueix_el_canvi_de_tempo(self):
        """Mapa 120 BPM (0–2 s) i 60 BPM (2–6 s): a partir de 2 s els clics van
        cada 1 s, no cada 0,5 (que és el que faria el BPM fix)."""
        mapa = tm.TempoMap([(0.0, 2.0, 120.0, 4, 4),
                            (2.0, 6.0, 60.0, 4, 4)])
        out = metronom.mescla_metronom(_silenci(6), SR, 0.0, 120.0, 4,
                                       mapa=mapa)
        clics = _clics(out)
        self.assertEqual(clics, [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0])

    def test_amb_mapa_constant_es_el_cami_de_sempre(self):
        mapa = tm.TempoMap([(0.0, 2.0, 120.0, 4, 4)])
        a = metronom.mescla_metronom(_silenci(2), SR, 0.0, 120.0, 4)
        b = metronom.mescla_metronom(_silenci(2), SR, 0.0, 120.0, 4,
                                     mapa=mapa)
        self.assertEqual(a, b)

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_graella.py
# ══════════════════════════════════════════════════════════════════════════
"""Quantització: divisions, nuclis de fronteres i visor."""




class TestDivisionsQuantitza(unittest.TestCase):
    def test_divisio_segons_compassos(self):
        # 120 BPM, 4/4 → compàs = 2 s
        for n, segons in ((1, 2.0), (2, 4.0), (4, 8.0), (6, 12.0),
                          (8, 16.0), (12, 24.0), (16, 32.0), (24, 48.0),
                          (32, 64.0), (48, 96.0), (64, 128.0)):
            self.assertAlmostEqual(
                graella.divisio_segons(f"compas{n}", 120, True, 4), segons)
        # depèn del compàs: 3/4 → compàs 1,5 s
        self.assertAlmostEqual(graella.divisio_segons("compas1", 120, True, 3), 1.5)
        # 6/8 → 3 negres (1,5 s), no 6 negres
        self.assertAlmostEqual(
            graella.divisio_segons("compas1", 120, True, 6, 8), 1.5)

    def test_divisio_segons_tresets(self):
        # 120 BPM → negra = 0,5 s
        self.assertAlmostEqual(
            graella.divisio_segons("treset_negra", 120, True), 0.5 * 2 / 3)
        self.assertAlmostEqual(
            graella.divisio_segons("treset_corxera", 120, True), 0.5 / 3)
        self.assertAlmostEqual(
            graella.divisio_segons("treset_semicorxera", 120, True), 0.5 / 6)

    def test_divisio_segons_lliure(self):
        self.assertEqual(graella.divisio_segons("corxera", 120, False), 0.0)
        self.assertAlmostEqual(graella.divisio_segons("corxera", 120, True), 0.25)

    def test_graelles_logiques(self):
        self.assertEqual([c for _e, c in graella.GRID_ACORDS],
                         ["corxera", "treset_corxera", "negra",
                          "treset_negra", "blanca", "compas1"])
        self.assertEqual([c for _e, c in graella.GRID_ESTRUCTURA],
                         [f"compas{n}" for n in
                          (1, 2, 4, 6, 8, 12, 16, 24, 32, 48, 64)])


class TestQuantitzaNucli(unittest.TestCase):
    def test_tot_quantitza_inicis(self):
        clips = [(0.0, 1.0, ("C",)), (1.0, 2.0, ("G",)),
                 (2.0, 3.0, ("Am",))]
        out = graella.quantitza_boundaries(
            clips, [0.0, 1.0, 2.0], {0, 1, 2}, 3.0)
        self.assertEqual([round(c[0], 3) for c in out], [0.0, 1.0, 2.0])
        self.assertEqual([c[2] for c in out], [("C",), ("G",), ("Am",)])

    def test_seleccio_nomes_mou_els_seleccionats(self):
        clips = [(0.0, 1.0, ("C",)), (1.0, 2.0, ("G",)),
                 (2.0, 3.0, ("Am",))]
        out = graella.quantitza_boundaries(
            clips, [0.0, 1.3, 2.0], {1}, 3.0)
        self.assertEqual([round(c[0], 3) for c in out], [0.0, 1.3, 2.0])

    def test_capcalera_n_no_menja_el_primer_acord(self):
        clips = [(0.0, 0.1, ("N",)), (0.1, 2.0, ("C",)),
                 (2.0, 4.0, ("G",))]
        out = graella.quantitza_boundaries(
            clips, [0.0, 0.0, 2.0], {0, 1, 2}, 4.0)
        self.assertEqual(out[0], (0.0, 2.0, ("C",)))
        self.assertEqual([c[2][0] for c in out], ["C", "G"])

    def test_no_inverteix_lordre_entre_fixos(self):
        clips = [(0.0, 1.0, ("C",)), (1.0, 2.0, ("G",)),
                 (2.0, 3.0, ("Am",))]
        # El seleccionat vol anar a 3, però el fix el limita abans de 2.0.
        out = graella.quantitza_boundaries(
            clips, [0.0, 5.0, 2.0], {1}, 3.0)
        self.assertLess(out[1][0], 2.0)
        self.assertGreaterEqual(
            out[1][0] - out[0][0], graella.MIN_GAP_QUANTITZA - 1e-9)

    def test_el_fixe_despres_del_seleccionat_sobreviu(self):
        clips = [(0.0, 1.0, ("C",)), (1.0, 2.0, ("G",)),
                 (2.0, 3.0, ("Am",))]
        out = graella.quantitza_boundaries(
            clips, [0.0, 1.999, 2.0], {1}, 3.0)
        self.assertEqual([round(c[0], 3) for c in out],
                         [0.0, 1.999, 2.0])
        self.assertEqual([c[2][0] for c in out], ["C", "G", "Am"])

    def test_colisio_entre_seleccionats_queda_el_mes_llarg(self):
        clips = [(0.0, 0.2, ("C",)), (0.2, 2.0, ("X",))]
        out = graella.quantitza_boundaries(
            clips, [0.0, 0.0], {0, 1}, 2.0)
        self.assertEqual(out, [(0.0, 2.0, ("X",))])


def _quantitza___visor():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "tema.wav")
    out = os.path.join(td, "AUTOCHORDS_tema")
    os.makedirs(out)
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * 8)
    ca = os.path.join(out, "acords.csv")
    sa = os.path.join(out, "estructura_ABC.csv")
    with open(ca, "w", encoding="utf-8") as f:
        f.write("0.00,0.10,N\n0.10,2.00,C\n2.10,4.00,G\n"
                "4.20,6.00,Am\n6.10,8.00,F\n")
    with open(sa, "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
                "0.0,2.9,2.9,A,A,1.1,2.2\n"
                "2.9,8.0,5.1,B,B,2.2,5.1\n")
    v = visor_mod.Visor(wav, ca, sa, bpm=120, bpb=4, tempo_fix=True)
    v.td, v.sortida = td, out
    return v


class TestQuantitzaVisor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = visor_mod.QApplication.instance() or visor_mod.QApplication([])

    def test_tot_acords_i_estructura(self):
        v = _quantitza___visor()
        n = v.quantitza("tot", "compas1", "compas1")
        self.assertGreater(n, 0)
        self.assertEqual([round(float(a[0]), 2) for a in v.acords],
                         [0.0, 2.0, 4.0, 6.0])
        self.assertEqual([a[2][0] for a in v.acords], ["C", "G", "Am", "F"])
        self.assertEqual([round(float(s[0]), 2) for s in v.seccions],
                         [0.0, 2.0])
        self.assertEqual([s[2] for s in v.seccions], ["A", "B"])
        self.assertEqual(len(v._undo_stack), 1)
        v.close()

    def test_no_toca_bpm_compas_offset_ni_cru(self):
        v = _quantitza___visor()
        abans = (v.bpm, v.bpb, getattr(v, "beat_type", 4), v.offset,
                 list(v.tempo_trams or ()))
        v.quantitza("tot", "compas1", "compas1")
        self.assertEqual(abans, (v.bpm, v.bpb, getattr(v, "beat_type", 4),
                                 v.offset, list(v.tempo_trams or ())))
        self.assertFalse(hasattr(v, "raw_acords"))
        v.close()

    def test_seleccio_mixta_una_sola_operacio(self):
        v = _quantitza___visor()
        v.timeline.select_multi({("chord", 2), ("section", 1)})
        n = v.quantitza("seleccio", "compas1", "compas1")
        self.assertGreater(n, 0)
        self.assertEqual(len(v._undo_stack), 1)
        despres = ([a[2][0] for a in v.acords],
                   [s[2] for s in v.seccions])
        v.undo()
        self.assertEqual([a[2][0] for a in v.acords],
                         ["N", "C", "G", "Am", "F"])
        v.redo()
        self.assertEqual(([a[2][0] for a in v.acords],
                          [s[2] for s in v.seccions]), despres)
        v.close()

    def test_nomes_acords_no_toca_estructura(self):
        v = _quantitza___visor()
        abans = list(v.seccions)
        v.quantitza("acords", "compas1", "compas1")
        self.assertEqual(v.seccions, abans)
        v.close()

    def test_nomes_estructura_no_toca_acords(self):
        v = _quantitza___visor()
        acords = [a[2][0] for a in v.acords]
        v.quantitza("estructura", "compas1", "compas1")
        self.assertEqual([a[2][0] for a in v.acords], acords)
        v.close()

    def test_en_mode_lliure_no_quantitza(self):
        v = _quantitza___visor()
        v.tempo_fix = False
        self.assertEqual(v.quantitza("tot", "compas1", "compas1"), 0)
        v.close()

    def test_sense_canvis_no_crea_undo(self):
        v = _quantitza___visor()
        v.quantitza("tot", "compas1", "compas1")
        abans = len(v._undo_stack)
        self.assertEqual(v.quantitza("tot", "compas1", "compas1"), 0)
        self.assertEqual(len(v._undo_stack), abans)
        v.close()


def _quantitza_tearDownModule():
    try:
        import _qt_neteja
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ORIGEN: test_snap.py
# ══════════════════════════════════════════════════════════════════════════
"""Graella configurable: interruptor de snap + divisió (1/4 · 1/8 · 1/16 · 1/32…).

Amb el snap configurable, el nudge fi és possible (divisió fina) i es pot
desactivar el snap del tot. Només mou fronteres → regles d'or intactes.
"""




ACORDS = "0.0,2.0,C\n2.0,4.5,Am\n4.5,7.0,F\n7.0,10.0,G\n10.0,20.0,C\n"
SECCIONS = ("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
            "0.0,10.0,10.0,A,A,1.1,5.1\n"
            "10.0,20.0,10.0,B,B,5.1,10.1\n")


def _snap___visor():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "tema.wav")
    out = os.path.join(td, "AUTOCHORDS_tema")
    os.makedirs(out)
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * 20)
    ca = os.path.join(out, "acords.csv")
    sa = os.path.join(out, "estructura_ABC.csv")
    with open(ca, "w", encoding="utf-8") as f:
        f.write(ACORDS)
    with open(sa, "w", encoding="utf-8") as f:
        f.write(SECCIONS)
    v = visor_mod.Visor(wav, ca, sa, bpm=120, bpb=4, tempo_fix=True)
    v.td, v.sortida = td, out
    return v


def _key(key, mods=Qt.NoModifier):
    return QKeyEvent(QEvent.KeyPress, key, mods)


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])


class TestSnap(_Base):
    def test_snap_per_defecte_encaixa(self):
        v = _snap___visor()
        v.timeline.set_snap(on=True, divisio="corxera")   # 0,25 s a 120 BPM
        self.assertAlmostEqual(v.timeline._snap(2.13), 2.25, places=6)
        v.close()

    def test_snap_off_no_encaixa(self):
        v = _snap___visor()
        v.timeline.set_snap(on=False)
        self.assertAlmostEqual(v.timeline._snap(2.13), 2.13, places=6)
        v.close()

    def test_divisio_configura_el_pas(self):
        v = _snap___visor()
        v.timeline.set_snap(on=True, divisio="semicorxera")   # 0,125 s
        self.assertAlmostEqual(v.timeline._pas_nudge(), 0.125, places=6)
        v.close()

    def test_nudge_fi_amb_divisio(self):
        v = _snap___visor()
        v.timeline.set_snap(on=True, divisio="semicorxera")
        v.timeline.select_clip("chord", 1)                # Am @ 2.0
        v.timeline.keyPressEvent(_key(Qt.Key_Right))
        self.assertAlmostEqual(float(v.acords[1][0]), 2.125, places=6)
        v.close()

    def test_nudge_amb_snap_off(self):
        v = _snap___visor()
        v.timeline.set_snap(on=False)
        pas = v.timeline._pas_nudge()
        v.timeline.select_clip("chord", 1)
        v.timeline.keyPressEvent(_key(Qt.Key_Right))
        self.assertAlmostEqual(float(v.acords[1][0]), 2.0 + pas, places=6)
        v.close()

    def test_divisio_en_compassos(self):
        v = _snap___visor()                                   # 120 BPM, 4/4 → compàs 2 s
        for divisio, esperat in (("compas1", 2.0), ("compas2", 4.0),
                                 ("compas4", 8.0), ("compas6", 12.0),
                                 ("compas8", 16.0), ("compas12", 24.0),
                                 ("compas16", 32.0), ("compas24", 48.0),
                                 ("compas32", 64.0), ("compas48", 96.0),
                                 ("compas64", 128.0)):
            v.timeline.set_snap(on=True, divisio=divisio)
            self.assertAlmostEqual(v.timeline._pas_nudge(), esperat, places=6,
                                   msg=divisio)
        v.close()

    def test_snap_amb_tresets(self):
        v = _snap___visor()                                   # 120 BPM
        v.timeline.set_snap(on=True, divisio="treset_corxera")
        self.assertAlmostEqual(v.timeline._snap(2.13), 13 * (0.5 / 3),
                               places=6)
        v.timeline.set_snap(on=True, divisio="treset_negra")
        self.assertAlmostEqual(v.timeline._snap(2.13), 6 * (0.5 * 2 / 3),
                               places=6)
        v.close()

    def test_el_grid_segueix_el_snap(self):
        v = _snap___visor()
        v.timeline.set_snap(on=True, divisio="treset_corxera")
        self.assertEqual(v.timeline._grid._divisio, "treset_corxera")
        self.assertEqual(v.timeline._ruler._divisio, "treset_corxera")
        v.timeline.set_snap(on=True, divisio="compas12")
        self.assertEqual(v.timeline._grid._divisio, "compas12")
        # El snap OFF no ha de desactivar el grid forçat.
        v.timeline.set_snap(on=False, divisio="compas12")
        self.assertFalse(v.timeline._snap_on)
        self.assertEqual(v.timeline._grid._divisio, "compas12")
        # I Auto torna a manar pel zoom.
        v.timeline.set_snap(on=False, divisio="")
        self.assertEqual(v.timeline._grid._divisio, "")
        v.close()

    def test_snap_manual_amb_mapa_variable(self):
        v = _snap___visor()
        mapa = TempoMap([(0.0, 10.0, 120, 4, 4), (10.0, 20.0, 60, 4, 4)])
        v.timeline.set_tempo_mode(True, 120, 4, mapa=mapa)
        v.timeline.set_snap(on=True, divisio="treset_corxera")
        self.assertAlmostEqual(v.timeline._snap(2.13), 13 * (0.5 / 3),
                               places=6)
        v.timeline.set_snap(on=True, divisio="compas2")
        self.assertAlmostEqual(v.timeline._snap(2.13), 4.0, places=6)
        v.close()

    def test_cursor_segueix_snap(self):
        """Amb snap actiu, el cursor s'encaixa a la graella (en clicar/moure'l)."""
        v = _snap___visor()
        v.timeline.set_snap(on=True, divisio="compas1")   # 2 s
        v.timeline.set_position(3.3)                      # → cel·la més propera
        self.assertAlmostEqual(v.timeline.get_position(), 4.0, places=6)
        # snap=False (reproducció/looop) → posició exacta
        v.timeline.set_position(3.3, snap=False)
        self.assertAlmostEqual(v.timeline.get_position(), 3.3, places=6)
        v.close()

    def test_cursor_snap_off_no_encaixa(self):
        v = _snap___visor()
        v.timeline.set_snap(on=False)
        v.timeline.set_position(3.3)
        self.assertAlmostEqual(v.timeline.get_position(), 3.3, places=6)
        v.close()

    def test_ves_a_es_una_cerca_exacta(self):
        """Les cerques programàtiques (barra/llistes/MCP) NO s'encaixen."""
        v = _snap___visor()
        v.timeline.set_snap(on=True, divisio="compas1")
        v.ves_a(3.3)
        self.assertAlmostEqual(v.pos, 3.3, places=6)
        v.close()

    def test_visor_reenvia_set_snap(self):
        v = _snap___visor()
        v.set_snap(on=False, divisio="negra")
        self.assertFalse(v.timeline._snap_on)
        self.assertEqual(v.timeline._snap_div_nom, "negra")
        v.close()


def _snap_tearDownModule():
    try:
        import _qt_neteja
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_canvi_mode_temps.py
# ══════════════════════════════════════════════════════════════════════════
"""Canvi de mode de temps (BPM·compàs ↔ hh:mm:ss) — la pista de BPM/compàs
ha de **sobreviure** al viatge d'anada i tornada.

Què es protegeix (bug real, reportat per l'operador el 19-10-2026):
    «he obert àudio, he fet canvis al carril compàs, he canviat a hh:mm:ss i
     tornat a BPM i ara ja no hi ha carril temps/compàs»

Causa arrel: `Finestra._canvia_tempo()` (que s'executa en commutar el mode)
tornava a cridar `timeline.set_tempo_mode(...)` —una crida anterior al **mapa
de tempo variable**— **sense el paràmetre `mapa=`**. El timeline hi quedava amb
`_mapa = None`, i això apagava la pista de BPM/compàs (`TempoLayer._visible()`)
i tornava la graella i el regle a la graella constant. Les dades
(`tempo_trams` / `tempo_map`) no es perdien mai: només la pintura.

`_actualitza_temps()` (que ja fa la crida correcta, amb `mapa=self.tempo_map`)
és l'única que hi ha de quedar.
"""




# Mapa VARIABLE (2 trams): és el cas on el carril és més visible —i on el bug
# feia més mal—, però el mateix passa amb un mapa d'un sol tram, perquè el que
# es perd és la REFERÈNCIA al mapa, no el nombre de trams.
TRAMS = [(0.0, 10.0, 120.0, 4, 4), (10.0, 20.0, 90.0, 3, 4)]

_VIVES = []


def _wav(dur=20.0):
    d = tempfile.mkdtemp()
    ruta = os.path.join(d, "tema.wav")
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * int(44100 * dur))
    return ruta


class _canvi_mode_temps___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = app_main.QApplication.instance() or app_main.QApplication([])

    def setUp(self):
        # Aïlla el que l'app escriu a les dades (recents, projectes…).
        self.td = tempfile.mkdtemp()
        patcher = unittest.mock.patch.object(config, "DADES_DIR", self.td)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        import _qt_neteja
        ws, _VIVES[:] = _VIVES[:], []
        for w in ws:
            w.dirty = False          # res de prompt de tancament als tests
        _qt_neteja.tanca_i_destrueix(*ws)

    def _muntar(self, trams=TRAMS):
        """Finestra + visor amb àudio obert i, si escau, mapa de tempo variable."""
        f = app_main.Finestra()
        _VIVES.append(f)
        wav = _wav()
        f.sortida = tempfile.mkdtemp()
        f._carrega_visor(wav)
        v = f.visor_ref
        self.assertIsNotNone(v, "el visor no s'ha carregat")
        if trams is not None:
            v.aplica_tempo_trams(list(trams))
        return f, v


class TestCanviModeTemps(_canvi_mode_temps___Base):
    """El gest de l'operador: BPM · compàs → hh:mm:ss → BPM · compàs."""

    def test_la_pista_de_bpm_torna_en_tornar_a_bpm(self):
        f, v = self._muntar()
        tl = v.timeline
        self.assertTrue(tl._tempo_lane._visible(),
                        "d'entrada la pista de BPM/compàs ha de ser visible")

        f._canvia_mode_temps(False)                  # → hh:mm:ss
        self.assertFalse(tl._tempo_lane._visible(),
                         "en mode Lliure la pista de BPM/compàs s'ha d'amagar")

        f._canvia_mode_temps(True)                   # → BPM · compàs
        self.assertTrue(tl._tempo_lane._visible(),
                        "el carril de temps/compàs ha de TORNAR en mode BPM")

    def test_el_timeline_recupera_la_referencia_al_mapa(self):
        """Sense `_mapa`, el regle i la graella perden el tempo variable."""
        f, v = self._muntar()
        tl = v.timeline
        f._canvia_mode_temps(False)
        f._canvia_mode_temps(True)
        self.assertIsNotNone(tl._mapa, "el timeline s'ha quedat sense mapa")
        self.assertIsNotNone(tl._tempo_lane._mapa, "la pista s'ha quedat sense mapa")
        self.assertFalse(tl._mapa.es_constant(),
                         "el mapa ha de continuar sent VARIABLE (2 trams)")

    def test_les_dades_del_mapa_no_es_perden(self):
        """El bug era de pintura: `tempo_trams`/`tempo_map` no s'han de tocar."""
        f, v = self._muntar()
        f._canvia_mode_temps(False)
        f._canvia_mode_temps(True)
        self.assertEqual(len(v.tempo_trams), 2)
        self.assertEqual(v.tempo_trams[1][2], 90.0)
        self.assertIsNotNone(v.tempo_map)
        self.assertFalse(v.tempo_map.es_constant())

    def test_tambe_amb_un_sol_tram(self):
        """La pista es mostra igualment (s'hi pot fer botó dret per afegir canvis)."""
        f, v = self._muntar(trams=[(0.0, 20.0, 120.0, 4, 4)])
        tl = v.timeline
        f._canvia_mode_temps(False)
        f._canvia_mode_temps(True)
        self.assertTrue(tl._tempo_lane._visible())
        self.assertIsNotNone(tl._mapa)

    def test_el_mode_arriba_al_timeline(self):
        f, v = self._muntar()
        tl = v.timeline
        f._canvia_mode_temps(False)
        self.assertFalse(tl._tempo_fix)
        self.assertFalse(v.tempo_fix)
        f._canvia_mode_temps(True)
        self.assertTrue(tl._tempo_fix)
        self.assertTrue(v.tempo_fix)

    def test_la_commutacio_actualitza_l_offset(self):
        """`_actualitza_temps()` llig `visor.offset`: el camp de la GUI hi ha
        d'arribar (abans ho feia la crida redundant que s'ha tret)."""
        f, v = self._muntar()
        f.offset.setText("2.5")
        f._canvia_mode_temps(False)
        f._canvia_mode_temps(True)
        self.assertAlmostEqual(v.offset, 2.5, places=6)

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_timeline_base.py
# ══════════════════════════════════════════════════════════════════════════
"""Funcions PURES de `app/timeline_base.py`: el pla de graella, el snap i les
posicions.

Són la base del grid, del regle i del snap del timeline, i fins ara només
s'exercitaven **indirectament** des del `TimelineView` (auditoria 18-10-2026,
que hi va veure zero referències directes a `snap_step`).

Es proven els **contractes**, no els números concrets de cada zoom: la divisió
de snap compleix la seua invariant, el pla i el snap coincideixen, i les
posicions es calculen per índex (mai acumulant, que era el bug del regle).
"""





class TestSnapStep(unittest.TestCase):

    def test_la_divisio_de_snap_compleix_la_seua_invariant(self):
        """La triada és la més fina que hi cap: step*pps >= MIN_LINE_PX."""
        for pps in (2.0, 5.0, 20.0, 60.0, 200.0, 800.0):
            s = tb.snap_step(True, 120.0, 4, pps)
            self.assertGreater(s, 0.0)
            fit = [d for (d, _k) in tb._divisions(True, 120.0, 4)
                   if d * pps >= tb.MIN_LINE_PX]
            if fit:
                self.assertEqual(s, fit[-1],
                                 f"pps={pps}: no és la més fina que hi cap")

    def test_mes_zoom_mai_dona_una_divisio_mes_gruixuda(self):
        """Amb més zoom (més pps) la divisió es va afiant o es queda igual.

        Si cap divisió hi cap (zoom extremadament allunyat), la funció cau a la
        **més gruixuda**; abans queia a la més fina i omplia el grid de línies.
        """
        pps_valors = [10.0, 50.0, 400.0]
        pas = [tb.snap_step(True, 120.0, 4, p) for p in pps_valors]
        self.assertEqual(pas, sorted(pas, reverse=True))

    def test_amb_mapa_variable_les_durades_son_les_del_mapa(self):
        """Amb mapa, les divisions són les del tram de l'OFFSET del mapa.

        El mapa comença amb 4/4 a 120 BPM (compàs = 2 s) i a 4 s passa a 3/4 a
        60 BPM (compàs = 3 s). Les divisions «representatives» es prenen del
        tram on cau l'origen, que és el del començament.
        """
        mapa = tm.TempoMap([(0.0, 4.0, 120.0, 4, 4), (4.0, 12.0, 60.0, 3, 4)])
        divs = tb._divisions(True, 120.0, 4, mapa)
        bar = next(s for s, k in divs if k == "bar")
        beat = next(s for s, k in divs if k == "beat")
        self.assertAlmostEqual(bar, 2.0, places=6)   # 4 temps a 120 BPM
        self.assertAlmostEqual(beat, 0.5, places=6)  # una negra
        self.assertTrue(any(isinstance(k, tuple) and k[0] == "bar"
                            for _s, k in divs), "falten múltiples de compàs")
        # ... i el pla les fa servir (no els valors del BPM de la barra)
        plan = tb.grid_plan(True, 90.0, 3, 60.0, 800.0, mapa=mapa)
        self.assertGreater(plan["snap"], 0.0)

    def test_en_mode_lliure_les_divisions_no_depen_del_bpm(self):
        a = tb._divisions(False, 90.0, 4)
        b = tb._divisions(False, 150.0, 4)
        self.assertEqual(a, b)


class TestGridPlan(unittest.TestCase):

    def test_el_pla_i_el_snap_coincideixen(self):
        """`grid_plan` és la font única: el seu snap ha de ser el de `snap_step`."""
        for pps in (3.0, 12.0, 40.0, 150.0, 600.0):
            plan = tb.grid_plan(True, 120.0, 4, pps, 800.0)
            self.assertEqual(plan["snap"], tb.snap_step(True, 120.0, 4, pps))

    def test_les_linies_van_de_gruixut_a_fi_i_inclouen_el_snap(self):
        plan = tb.grid_plan(True, 120.0, 4, 60.0, 800.0)
        steps = [s for s, _k in plan["lines"]]
        self.assertEqual(steps, sorted(steps, reverse=True))
        self.assertAlmostEqual(steps[-1], plan["snap"], places=9)
        for s in steps:
            self.assertGreaterEqual(s * 60.0, tb.MIN_LINE_PX)

    def test_l_etiqueta_es_la_mes_fina_que_hi_cap(self):
        """Si alguna divisió cap a l'amplada d'etiqueta, la triada l'hi cap;
        si no n'hi cap, cau al nivell gran (no pot inventar-se'n una)."""
        pps = 200.0
        plan = tb.grid_plan(True, 120.0, 4, pps, 800.0, min_label_px=120.0)
        cands = [s for (s, _k) in tb._divisions(True, 120.0, 4)
                 if s * pps >= 120.0]
        if cands:
            self.assertAlmostEqual(plan["label"], cands[-1], places=9)
        else:
            self.assertGreater(plan["label"], 0.0)

    def test_divisio_manual_treset(self):
        plan = tb.grid_plan(True, 120.0, 4, 60.0, 1000.0,
                            divisio=("beat", 1.0 / 3.0))
        self.assertAlmostEqual(plan["snap"], 1.0 / 6.0)
        self.assertEqual(plan["lines"][-1][1], "sub")
        self.assertAlmostEqual(plan["label"], 0.5)   # etiqueta al temps
        self.assertIn((0.5, "beat"), plan["lines"])

    def test_divisio_manual_bloc_de_compassos(self):
        plan = tb.grid_plan(True, 120.0, 4, 20.0, 1000.0,
                            divisio=("bars", 12))
        self.assertAlmostEqual(plan["snap"], 24.0)
        self.assertEqual(plan["lines"], [(24.0, "bar"), (2.0, "bar")])
        self.assertAlmostEqual(plan["label"], 24.0)

    def test_divisio_manual_molt_fina_es_forca(self):
        plan = tb.grid_plan(True, 120.0, 4, 60.0, 1000.0,
                            divisio=("beat", 1.0 / 6.0))
        self.assertAlmostEqual(plan["snap"], 1.0 / 12.0)
        self.assertAlmostEqual(plan["lines"][-1][0], 1.0 / 12.0)

    def test_divisio_manual_fora_de_vista_es_forca(self):
        plan = tb.grid_plan(True, 120.0, 4, 60.0, 1000.0,
                            divisio=("bars", 64))
        self.assertAlmostEqual(plan["snap"], 128.0)
        self.assertEqual(plan["label"], 128.0)

    def test_grid_positions_amb_treset_i_mapa(self):
        mapa = TempoMap([(0.0, 10.0, 120, 4, 4), (10.0, 20.0, 121, 4, 4)])
        pos = list(tb.grid_positions(0.0, 0.5, 0.5, mapa=mapa,
                                     kind=("sub", 1.0 / 3.0)))
        self.assertEqual(len(pos), 4)
        for obtingut, esperat in zip(pos, (0.0, 1 / 6, 2 / 6, 0.5)):
            self.assertAlmostEqual(obtingut, esperat, places=6)

    def test_min_zoom_no_omple_el_grid_de_linies(self):
        """A poc zoom, la divisió més fina que hi cap (no 0,02 s a l'atzar)."""
        plan = tb.grid_plan(True, 120.0, 4, 0.5, 1000.0)
        self.assertGreaterEqual(plan["snap"] * 0.5, tb.MIN_LINE_PX - 1e-9)
        self.assertLessEqual(len(plan["lines"]), 3)

    def test_zoom_extremadament_allunyat_cau_a_la_mes_gruixuda(self):
        plan = tb.grid_plan(True, 120.0, 4, 0.01, 1000.0)
        self.assertEqual(plan["snap"], 32.0)       # 16 compassos a 120 BPM
        self.assertEqual(plan["lines"], [(32.0, "bar")])
        self.assertEqual(tb.snap_step(True, 120.0, 4, 0.01), 32.0)

    def test_max_zoom_arriba_a_1_32(self):
        plan = tb.grid_plan(True, 120.0, 4, 5000.0, 1000.0)
        self.assertAlmostEqual(plan["snap"], 0.0625)   # fusa
        self.assertAlmostEqual(plan["label"], 0.0625)

    def test_multiples_de_compas_amb_mapa(self):
        mapa = tm.TempoMap([(0.0, 20.0, 120.0, 4, 4)])
        pos = list(tb.grid_positions(0.0, 20.0, 8.0, mapa=mapa,
                                     kind=("bar", 4)))
        self.assertEqual(pos, [0.0, 8.0, 16.0])

    def test_grid_plan_manual_bar_multiple_te_label_kind(self):
        """El nivell de compàs múltiple no s'ha de perdre al pintar el grid."""
        # Mapa VARIABLE (4/4 → 8/8) però amb el mateix compàs de 4 negres.
        mapa = tm.TempoMap([(0.0, 10.0, 120.0, 4, 4),
                            (10.0, 20.0, 120.0, 8, 8)])
        plan = tb.grid_plan(True, 120.0, 4, 10.0, 1000.0, mapa=mapa,
                            divisio=("bars", 2))
        self.assertEqual(plan["label_kind"], ("bar", 2))
        self.assertIn((4.0, ("bar", 2)), plan["lines"])
        pos = list(tb.grid_positions(0.0, 20.0, 4.0, mapa=mapa,
                                     kind=("bar", 2)))
        self.assertEqual(pos, [0.0, 4.0, 8.0, 12.0, 16.0, 20.0])

    def test_grid_levels_deriva_del_pla(self):
        plan = tb.grid_plan(True, 120.0, 4, 60.0, 800.0)
        nivells = tb.grid_levels(True, 120.0, 4, 60.0, 800.0)
        self.assertEqual([s for s, _c, _w in nivells],
                         [s for s, _k in reversed(plan["lines"])])
        for _s, color, width in nivells:
            self.assertIsInstance(color, str)
            self.assertEqual(width, 1)

    def test_min_zoom_te_una_linia_mestra_mes_gruixuda(self):
        plan = tb.grid_plan(True, 120.0, 4, 1.96, 1200.0)
        nivells = tb.grid_levels(True, 120.0, 4, 1.96, 1200.0)
        self.assertIn((plan["label"], 2),
                      [(s, w) for s, _c, w in nivells])


class TestGridPositions(unittest.TestCase):

    def test_les_posicions_son_offset_mes_k_per_pas(self):
        """`grid_positions` és un GENERADOR (el timeline el consumeix)."""
        pos = list(tb.grid_positions(0.0, 10.0, 1.0, offset=0.0))
        self.assertEqual(pos, [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0,
                               8.0, 9.0, 10.0])

    def test_no_acumula_error_de_coma_flotant(self):
        """El cor del contracte: `t = offset + k*step` per ÍNDEX.

        Amb acumulació (`t += step`), al regle els inicis de compàs acabaven
        sortint com «(N-1).4» en lloc de «N.1». Ací es comprova que cada posició
        és EXACTAMENT la fórmula, fins i tot amb un pas que no és representable
        (1/3) i en una vista llunyana.
        """
        pas = 1.0 / 3.0
        pos = list(tb.grid_positions(100.0, 110.0, pas))
        base = math.floor(100.0 / pas)
        self.assertEqual(pos[:3], [base * pas, (base + 1) * pas,
                                   (base + 2) * pas])

    def test_dins_de_la_vista_i_ordre(self):
        pos = list(tb.grid_positions(2.0, 8.0, 1.0))
        self.assertEqual(pos, [2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
        self.assertEqual(pos, sorted(pos))

    def test_vista_d_un_sol_punt(self):
        """Els extrems són INCLUSIUS: una vista d'amplada zero dona el punt."""
        self.assertEqual(list(tb.grid_positions(10.0, 10.0, 1.0)), [10.0])

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_timeline_regle.py
# ══════════════════════════════════════════════════════════════════════════
"""Tests del regle/grid: numeració de compassos i posicions SENSE deriva.

Regressió del bug «7.1, 7.4, 8.4» (un inici de compàs etiquetat com «(N-1).4»
en lloc de «N.1») i de la deriva per acumulació `t += step` al regle i al grid.
"""




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


class TestAvaluaConfirmacio(unittest.TestCase):
    """Guiat v2: el veredicte «fiable / dubtós» de la doble comprovació."""

    def test_tot_coincidix_es_fiable(self):
        r = tm.avalua_confirmacio(103.4, prev=103.0, banda=103.5,
                                  llarga=103.3)
        self.assertEqual(r["estat"], "fiable")
        self.assertTrue(r["coincideix"])
        self.assertAlmostEqual(r["bpm"], 103.4, places=6)
        self.assertIn("fiable", r["detall"])

    def test_meitat_de_tempo_es_dubtos(self):
        """El cas real: la detecció lliure cau a la meitat (51,7)."""
        r = tm.avalua_confirmacio(51.7, prev=103.0, banda=103.4,
                                  llarga=103.5)
        self.assertEqual(r["estat"], "dubtos")
        self.assertFalse(r["coincideix"])
        self.assertIn("dubtós", r["detall"])
        self.assertIn("✗", r["detall"])

    def test_sense_reforc_no_es_pot_confirmar(self):
        r = tm.avalua_confirmacio(103.4)
        self.assertEqual(r["estat"], "sense")
        self.assertFalse(r["coincideix"])
        self.assertAlmostEqual(r["bpm"], 103.4, places=6)

    def test_reforc_salva_una_deteccio_lliure_fallida(self):
        """Si la lliure falla però el reforç té número, s'usa eixe número."""
        r = tm.avalua_confirmacio(None, prev=103.0, banda=103.4)
        self.assertAlmostEqual(r["bpm"], 103.4, places=6)
        self.assertEqual(r["estat"], "fiable")

    def test_res_utilitzable(self):
        r = tm.avalua_confirmacio(None, prev=None, banda=None, llarga=None)
        self.assertEqual(r["estat"], "sense")
        self.assertIsNone(r["bpm"])

    def test_tolerancia_del_tram_anterior_es_percentual(self):
        # 103 → ±3 % = ±3,09 BPM: 106 casa, 107 no
        self.assertTrue(tm.avalua_confirmacio(106.0, prev=103.0)["coincideix"])
        self.assertFalse(tm.avalua_confirmacio(107.0, prev=103.0)["coincideix"])


if __name__ == "__main__":   # pragma: no cover
    unittest.main()
