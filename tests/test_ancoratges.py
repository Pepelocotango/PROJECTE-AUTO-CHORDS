"""Suite de test — Ancoratges humans (Anàlisi guiat v3, nucli)

Cobreix R1–R9 de `docs/ANALISI_GUIAT_v3.md`: encaix, derivació del BPM,
llindars, octava, cap/cua i la verificació que la graella passa pels
ancoratges.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene: esborra els temporals en plegar

import unittest

import math
import struct
import tempfile
import wave

from app import ancoratges as A
from app import ffmpeg
from app import marcadors as M
from app import pipeline
from app import tempo_map as TM
import shutil


def anc(*pares):
    return [{"t": t, "num": n, "den": d} for t, n, d in pares]


class TestEncaixBasic(unittest.TestCase):
    def test_4_4_quatre_compassos(self):
        r = A.encaixa_ancoratges(anc((0, 4, 4), (8, 4, 4)), 8.0, [120.0])
        self.assertTrue(r["ok"], r["error"])
        self.assertEqual(r["trams"], [(0.0, 8.0, 120.0, 4, 4)])
        self.assertEqual(r["intervals"][0]["n"], 4)
        self.assertAlmostEqual(r["intervals"][0]["bpm"], 120.0)
        self.assertEqual(r["intervals"][0]["estat"], A.ESTAT_OK)
        self.assertAlmostEqual(r["intervals"][0]["desv"], 0.0)

    def test_3_4(self):
        r = A.encaixa_ancoratges(anc((0, 3, 4), (9, 3, 4)), 9.0, [120.0])
        self.assertTrue(r["ok"], r["error"])
        self.assertEqual(r["intervals"][0]["n"], 6)
        self.assertAlmostEqual(r["intervals"][0]["bpm"], 120.0)

    def test_5_4(self):
        r = A.encaixa_ancoratges(anc((0, 5, 4), (30, 5, 4)), 30.0, [100.0])
        self.assertTrue(r["ok"], r["error"])
        self.assertEqual(r["intervals"][0]["n"], 10)
        self.assertAlmostEqual(r["intervals"][0]["bpm"], 100.0)

    def test_6_8(self):
        r = A.encaixa_ancoratges(anc((0, 6, 8), (12, 6, 8)), 12.0, [120.0])
        self.assertTrue(r["ok"], r["error"])
        self.assertEqual(r["intervals"][0]["n"], 8)
        self.assertAlmostEqual(r["intervals"][0]["bpm"], 120.0)

    def test_canvi_de_metre_a_l_ancoratge(self):
        # El metre de l'ancoratge 3 (3/4) mana a l'interval que comença allí.
        punts = anc((0, 4, 4), (8, 4, 4), (14, 3, 4), (20, 3, 4))
        r = A.encaixa_ancoratges(punts, 20.0, [120.0, 120.0, 120.0])
        self.assertTrue(r["ok"], r["error"])
        self.assertEqual(len(r["trams"]), 3)
        self.assertEqual(r["trams"][1][3:], (4, 4))
        self.assertEqual(r["trams"][2][3:], (3, 4))
        self.assertTrue(A.verifica_ancoratges(r["trams"], punts, r["offset"]))


class TestMarcadors(unittest.TestCase):
    """Marcadors humans: llista ordenada, alta/baixa i rebot de la tecla."""

    def test_afegeix_ordena_i_descarta_rebots(self):
        m = M.afegeix([], 2.0, 60.0)
        self.assertEqual(m, [2.0])
        m = M.afegeix(m, 1.0, 60.0)
        self.assertEqual(m, [1.0, 2.0])
        m2 = M.afegeix(m, 2.02, 60.0)          # rebot (< 50 ms)
        self.assertEqual(m2, m)
        self.assertEqual(M.afegeix(m, 0.0, 60.0), m)      # fora (inici)
        self.assertEqual(M.afegeix(m, 60.0, 60.0), m)     # fora (final)

    def test_elimina_i_consultes(self):
        m = [1.0, 4.0, 9.0]
        self.assertEqual(M.elimina(m, 1), [1.0, 9.0])
        self.assertEqual(M.elimina(m, 9), m)             # índex inexistent
        self.assertEqual(M.index_a(m, 4.05), 1)
        self.assertIsNone(M.index_a(m, 6.0))
        self.assertEqual(M.seguent(m, 2.0), 4.0)
        self.assertEqual(M.anterior(m, 5.0), 4.0)
        self.assertIsNone(M.seguent(m, 9.0))

    def test_normalitza_treu_duplicats(self):
        self.assertEqual(M.normalitza_marcadors([3, 1.0, 1.0000001, 2], 10),
                         [1.0, 2.0, 3.0])

    def test_candidats_bpm_de_marcadors_sintetics(self):
        """Marcadors a 4/8/16 compassos d'un tema a 96 BPM (compàs 2,5 s)."""
        ms, t = [], 8.1
        for k in (4, 4, 8, 4, 16, 4):
            ms.append(round(t, 3))
            t += k * 2.5
        cands = M.candidats_bpm(ms, 4, 4, 60, 180, preferit=94.0)
        self.assertTrue(cands)
        # amb dades perfectes l'ambigüitat doble/meitat és real: 96 ha d'estar
        # entre els candidats, amb els compassos correctes
        dinou = next(c for c in cands if abs(c["bpm"] - 96.0) < 0.2)
        self.assertEqual(dinou["compassos"], [4, 4, 8, 4, 16])
        self.assertLess(dinou["residu"], 1e-6)
        # i amb el BPM de la barra a prop de 96, eixe va primer
        cands = M.candidats_bpm(ms, 4, 4, 60, 180, preferit=96.0)
        self.assertAlmostEqual(cands[0]["bpm"], 96.0, delta=0.2)

    def test_candidats_bpm_amb_soroll_huma(self):
        """Marcacions reals: ±30 ms i intervals d'1, 2, 3, 4 i 8 compassos."""
        import random
        random.seed(7)
        bar = 2.75                       # ~87,3 BPM 4/4
        ms, t = [], 3.289
        for k in (1, 1, 1, 1, 1, 1, 1, 2, 1, 3, 3, 1, 2, 2, 1, 1, 2, 2, 2, 2,
                  2, 4, 4, 8, 4, 4, 4, 4, 4, 3, 1, 4, 4, 4, 4, 2):
            ms.append(round(t + random.uniform(-0.03, 0.03), 3))
            t += k * bar
        c = M.candidats_bpm(ms, 4, 4, 50, 200, preferit=120.0, tol=0.12)[0]
        self.assertAlmostEqual(c["bpm"], 240 / bar, delta=3.0)
        self.assertLessEqual(max(c["compassos"]), 9)

    def test_desa_i_llegeix_al_projecte(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        ruta = pipeline.desa_marcadors(d, [1.5, 4.25])
        self.assertTrue(os.path.exists(ruta))
        self.assertEqual(pipeline.llegeix_marcadors(d, 60.0), [1.5, 4.25])
        self.assertEqual(pipeline.llegeix_marcadors(tempfile.mkdtemp(), 60.0), [])


class TestReparaFronteres(unittest.TestCase):
    """Bug 21-10: després del guiat, eliminar/fusionar un tram de tempo fallava
    per mil·lèsimes fora de la línia de compàs («no es podien editar»)."""

    MAPA = [(0.0, 30.379, 100.4184, 4, 4), (30.379, 35.157, 100.4604, 4, 4),
            (35.157, 39.595, 108.1568, 4, 4), (39.595, 60.0, 108.1568, 4, 4)]
    OFF = 27.989

    def test_eliminar_el_segon_tram(self):
        out = TM.elimina_tall(self.MAPA, 1)
        with self.assertRaises(ValueError):        # sense reparar, peta
            TM.valida_i_normalitza_compassos(out, 60.0, self.OFF)
        fi = TM.repara_fronteres(out, 60.0, self.OFF)
        self.assertEqual(len(fi), 3)
        # la frontera s'ha imantat a la línia de compàs (2 ms)
        self.assertAlmostEqual(fi[0][1], 35.159, places=3)
        self.assertAlmostEqual(fi[0][1] - self.OFF, 3 * 2.3900, places=2)
        # i el mapa resultant és vàlid (no llança)
        TM.valida_i_normalitza_compassos(fi, 60.0, self.OFF)

    def test_eliminar_el_tercer_tram_absorbeix_mig_compas(self):
        out = TM.elimina_tall(self.MAPA, 2)
        fi = TM.repara_fronteres(out, 60.0, self.OFF)
        self.assertEqual(len(fi), 3)
        bars = (fi[1][1] - fi[1][0]) / TM.durada_compas(fi[1][2], 4, 4)
        self.assertAlmostEqual(bars, round(bars), places=5)   # enters
        self.assertEqual(round(bars), 4)

    def test_eliminar_el_primer_tram(self):
        fi = TM.repara_fronteres(TM.elimina_tall(self.MAPA, 0), 60.0, self.OFF)
        self.assertEqual(len(fi), 3)
        self.assertAlmostEqual(fi[0][1], 35.156, places=3)   # imantat
        TM.valida_i_normalitza_compassos(fi, 60.0, self.OFF)

    MAPA_MICRO = [(0.0, 0.273090, 120.0, 4, 4),
                  (0.273090, 0.273773, 120.0, 4, 4),
                  (0.273773, 286.186817, 115.0, 4, 4),
                  (286.186817, 297.453333, 125.125938, 4, 4)]

    def test_elimina_amb_micro_tram_i_offset_de_milisegons(self):
        # Cas real (Jamiroquai, 23:40): un `+` a 0,7 ms d'una frontera va
        # deixar un tram de 0,000683 s i cap «Elimina tempo» no passava.
        for idx in range(4):
            fi = TM.repara_fronteres(TM.elimina_tall(self.MAPA_MICRO, idx),
                                     297.453333, 0.273)
            TM.valida_i_normalitza_compassos(fi, 297.453333, 0.273)
            self.assertAlmostEqual(fi[0][0], 0.0)
            self.assertAlmostEqual(fi[-1][1], 297.453333, places=6)
            self.assertTrue(all(float(b[1]) - float(b[0]) > 0 for b in fi))

    def test_neteja_trams_curts(self):
        t = TM.neteja_trams_curts([(0.0, 0.5, 120.0, 4, 4),
                                   (0.5, 0.5007, 120.0, 4, 4),
                                   (0.5007, 2.0, 90.0, 4, 4)])
        self.assertEqual(len(t), 2)
        self.assertAlmostEqual(t[0][1], 0.5007, places=6)

    def test_premusica_amb_offset_de_milisegons_valida(self):
        # L'offset es desa amb 3 decimals (0,273) i la frontera pot caure a
        # 0,273090: la tolerància és en TEMPS, no en compassos (abans 1e-5
        # compassos = 20 µs ho rebutjava i bloquejava la reparació).
        trams = [(0.0, 0.273090, 120.0, 4, 4),
                 (0.273090, 10.0, 120.0, 4, 4)]
        out = TM.valida_i_normalitza_compassos(trams, 10.0, 0.273)
        self.assertAlmostEqual(out[0][1], 0.273090, places=6)

    def test_un_mapa_ja_valid_no_es_toca(self):
        fi = TM.valida_i_normalitza_compassos(self.MAPA, 60.0, self.OFF)
        self.assertEqual(TM.repara_fronteres(fi, 60.0, self.OFF),
                         [tuple(t) for t in fi])


class TestCasRealOtis(unittest.TestCase):
    """Regressió 21-10 (log real): tema a ~100 BPM amb la barra a 120.

    El 1r interval no es pot rebutjar per allunyar-se del BPM de la barra:
    eixe BPM (el 120 per defecte) és una referència, no una mesura. Abans,
    4 ancoratges ben punxats donaven «Hi ha intervals sense encaixar».
    """

    ANC = [{"t": 27.989, "num": 4, "den": 4}, {"t": 30.379, "num": 4, "den": 4},
           {"t": 35.157, "num": 4, "den": 4}, {"t": 39.595, "num": 4, "den": 4}]

    def test_encaixa_amb_la_barra_a_120(self):
        r = A.encaixa_ancoratges(self.ANC, 165.7, None, 120.0)
        self.assertTrue(r["ok"], r["error"])
        self.assertEqual(len(r["trams"]), 4)
        self.assertAlmostEqual(r["offset"], 27.989, places=6)
        pri = r["intervals"][0]
        self.assertEqual(pri["estat"], A.ESTAT_NOTA)   # avís, no bloqueig
        self.assertAlmostEqual(pri["bpm"], 100.42, places=2)
        self.assertIn("barra", pri["nota"])
        # la cadena sí que mana als intervals següents
        self.assertAlmostEqual(r["intervals"][1]["bpm"], 100.46, places=2)
        self.assertEqual(r["intervals"][1]["estat"], A.ESTAT_OK)

    def test_un_interval_posterior_es_inexacte_encara_bloqueja(self):
        anc = [{"t": 0.0, "num": 4, "den": 4}, {"t": 2.0, "num": 4, "den": 4},
               {"t": 2.6, "num": 4, "den": 4}]        # 2n interval: 0,6 s
        r = A.encaixa_ancoratges(anc, 10.0, None, 120.0)
        self.assertFalse(r["ok"])
        self.assertIn(1, r["no_encaixen"])


class TestLlindars(unittest.TestCase):
    def _un_interval(self, dt, det):
        return A.encaixa_ancoratges(
            anc((0, 4, 4), (dt, 4, 4)), dt, [det])

    def test_ok(self):
        r = self._un_interval(8.0, 120.0)
        self.assertEqual(r["intervals"][0]["estat"], A.ESTAT_OK)
        self.assertTrue(r["ok"])

    def test_nota(self):
        dt = 4 * 240.0 / 121.8          # 121,8 BPM → 1,5 % del detectat
        r = self._un_interval(dt, 120.0)
        self.assertEqual(r["intervals"][0]["estat"], A.ESTAT_NOTA)
        self.assertAlmostEqual(r["intervals"][0]["desv"], 0.015, places=3)
        self.assertTrue(r["ok"])

    def test_sospitos(self):
        dt = 4 * 240.0 / 126.0          # 126 BPM → 5 %
        r = self._un_interval(dt, 120.0)
        self.assertEqual(r["intervals"][0]["estat"], A.ESTAT_SOSPITOS)
        self.assertTrue(r["ok"])
        self.assertEqual(r["sospitosos"], [0])

    def test_no_encaixa(self):
        # 4,8 s: n=2 → 100 (−23 %) i n=3 → 150 (+15 %); cap dins del 10 %
        r = self._un_interval(4.8, 130.0)
        self.assertFalse(r["ok"])
        self.assertIsNone(r["trams"])
        self.assertEqual(r["intervals"][0]["estat"], A.ESTAT_NO_ENCAIXA)
        self.assertEqual(r["no_encaixen"], [0])
        self.assertIn("s'allunya", r["intervals"][0]["nota"])

    def test_llindars_alternatius(self):
        dt = 4 * 240.0 / 126.0          # 5 %
        r = A.encaixa_ancoratges(anc((0, 4, 4), (dt, 4, 4)), dt, [120.0],
                                 desv_nota=0.01, desv_sospitos=0.06,
                                 desv_no_encaixa=0.20)
        self.assertEqual(r["intervals"][0]["estat"], A.ESTAT_NOTA)
        r2 = A.encaixa_ancoratges(anc((0, 4, 4), (dt, 4, 4)), dt, [120.0],
                                  desv_nota=0.01, desv_sospitos=0.04,
                                  desv_no_encaixa=0.20)
        self.assertEqual(r2["intervals"][0]["estat"], A.ESTAT_SOSPITOS)

    def test_llindars_incoherents(self):
        with self.assertRaises(ValueError):
            A.encaixa_ancoratges(anc((0, 4, 4), (8, 4, 4)), 8.0, [120.0],
                                 desv_nota=0.05, desv_sospitos=0.03)


class TestReferencies(unittest.TestCase):
    def test_sense_referencia(self):
        r = A.encaixa_ancoratges(anc((0, 4, 4), (8, 4, 4)), 8.0, [None])
        self.assertFalse(r["ok"])
        self.assertEqual(r["intervals"][0]["estat"], A.ESTAT_SENSE_REFERENCIA)

    def test_usa_el_global(self):
        r = A.encaixa_ancoratges(anc((0, 4, 4), (8, 4, 4)), 8.0, [None],
                                 bpm_ref=120.0)
        self.assertTrue(r["ok"], r["error"])
        self.assertEqual(r["intervals"][0]["font_b0"], "global")
        self.assertAlmostEqual(r["intervals"][0]["bpm"], 120.0)

    def test_usa_l_anterior(self):
        r = A.encaixa_ancoratges(
            anc((0, 4, 4), (8, 4, 4), (16, 4, 4)), 16.0, [120.0, None])
        self.assertTrue(r["ok"], r["error"])
        self.assertEqual(r["intervals"][1]["font_b0"], "anterior")
        self.assertAlmostEqual(r["intervals"][1]["bpm"], 120.0)

    def test_usa_el_preferit(self):
        r = A.encaixa_ancoratges(anc((0, 4, 4), (8, 4, 4)), 8.0, [None],
                                 bpm_preferit=120.0)
        self.assertTrue(r["ok"], r["error"])
        self.assertEqual(r["intervals"][0]["font_b0"], "preferit")

    def test_rang_descarta_tots_els_n(self):
        r = A.encaixa_ancoratges(anc((0, 4, 4), (8, 4, 4)), 8.0, [105.0],
                                 bpm_min=100.0, bpm_max=110.0)
        self.assertFalse(r["ok"])
        self.assertEqual(r["intervals"][0]["estat"], A.ESTAT_NO_ENCAIXA)
        self.assertIn("rang", r["intervals"][0]["nota"])

    def test_interval_massa_curt(self):
        r = A.encaixa_ancoratges(anc((0, 4, 4), (0.3, 4, 4)), 10.0, [120.0],
                                 bpm_max=180.0)
        self.assertFalse(r["ok"])
        self.assertEqual(r["intervals"][0]["estat"], A.ESTAT_MASSA_CURT)


class TestCapICua(unittest.TestCase):
    def test_cap_absorbit_per_l_offset(self):
        # El primer ancoratge a 5 s és el compàs 1 (offset); el cap no és tram.
        r = A.encaixa_ancoratges(anc((5, 4, 4), (13, 4, 4)), 20.0, [120.0])
        self.assertTrue(r["ok"], r["error"])
        self.assertAlmostEqual(r["offset"], 5.0)
        self.assertAlmostEqual(r["cap"], 5.0)
        self.assertAlmostEqual(r["cua"], 7.0)
        self.assertEqual(len(r["trams"]), 2)
        self.assertAlmostEqual(r["trams"][0][0], 0.0)
        self.assertAlmostEqual(r["trams"][1][0], 13.0)
        self.assertTrue(A.verifica_ancoratges(
            r["trams"], anc((5, 4, 4), (13, 4, 4)), r["offset"]))

    def test_ancoratge_al_zero_sense_cap(self):
        r = A.encaixa_ancoratges(anc((0, 4, 4), (8, 4, 4)), 12.0, [120.0])
        self.assertAlmostEqual(r["cap"], 0.0)
        self.assertAlmostEqual(r["offset"], 0.0)
        self.assertAlmostEqual(r["cua"], 4.0)

    def test_ancoratge_al_final_sense_cua(self):
        r = A.encaixa_ancoratges(anc((0, 4, 4), (12, 4, 4)), 12.0, [120.0])
        self.assertAlmostEqual(r["cua"], 0.0)
        self.assertEqual(len(r["trams"]), 1)

    def test_un_sol_ancoratge_amb_referencia(self):
        r = A.encaixa_ancoratges(anc((5, 4, 4)), 20.0, None, bpm_ref=120.0)
        self.assertTrue(r["ok"], r["error"])
        self.assertEqual(len(r["trams"]), 1)
        self.assertAlmostEqual(r["trams"][0][2], 120.0)
        self.assertTrue(A.verifica_ancoratges(
            r["trams"], anc((5, 4, 4)), r["offset"]))

    def test_un_sol_ancoratge_sense_referencia(self):
        r = A.encaixa_ancoratges(anc((5, 4, 4)), 20.0, None)
        self.assertFalse(r["ok"])
        self.assertIn("referència", r["error"])


class TestOctavaIManual(unittest.TestCase):
    def test_dobla_n_canvia_el_recompte(self):
        r = A.encaixa_ancoratges(anc((0, 4, 4), (8, 4, 4)), 8.0, [120.0])
        n_abans = len(A.linies_de_compas(r["trams"], r["offset"]))
        r2 = A.encaixa_ancoratges(anc((0, 4, 4), (8, 4, 4)), 8.0, [120.0],
                                  n_manual={0: 8})
        n_despres = len(A.linies_de_compas(r2["trams"], r2["offset"]))
        self.assertTrue(r2["ok"], r2["error"])
        self.assertEqual(r2["intervals"][0]["n"], 8)
        self.assertAlmostEqual(r2["intervals"][0]["bpm"], 240.0)
        self.assertEqual(n_despres, n_abans + 4)
        self.assertTrue(A.verifica_ancoratges(
            r2["trams"], anc((0, 4, 4), (8, 4, 4)), r2["offset"]))

    def test_n_manual_desbloqueja_no_encaixa(self):
        r = A.encaixa_ancoratges(anc((0, 4, 4), (4.8, 4, 4)), 4.8, [130.0],
                                 n_manual={0: 2})
        self.assertTrue(r["ok"], r["error"])
        self.assertEqual(r["intervals"][0]["estat"], A.ESTAT_MANUAL)
        self.assertAlmostEqual(r["intervals"][0]["bpm"], 100.0)

    def test_n_manual_invalid(self):
        with self.assertRaises(ValueError):
            A.encaixa_ancoratges(anc((0, 4, 4), (8, 4, 4)), 8.0, [120.0],
                                 n_manual={0: 0})


class TestValidacions(unittest.TestCase):
    def test_sense_ancoratges(self):
        with self.assertRaises(ValueError):
            A.encaixa_ancoratges([], 10.0, [])

    def test_desordenats_es_ordenen(self):
        r = A.encaixa_ancoratges(anc((8, 4, 4), (0, 4, 4)), 8.0, [120.0])
        self.assertTrue(r["ok"], r["error"])
        self.assertAlmostEqual(r["offset"], 0.0)

    def test_dos_massa_junts(self):
        with self.assertRaises(ValueError):
            A.encaixa_ancoratges(anc((0, 4, 4), (0.1, 4, 4)), 10.0, [120.0])

    def test_fora_de_l_audio(self):
        with self.assertRaises(ValueError):
            A.encaixa_ancoratges(anc((0, 4, 4), (11, 4, 4)), 10.0, [120.0])

    def test_deteccions_de_mida_equivocada(self):
        with self.assertRaises(ValueError):
            A.encaixa_ancoratges(anc((0, 4, 4), (8, 4, 4)), 8.0, [120.0, 130.0])

    def test_durada_invalida(self):
        with self.assertRaises(ValueError):
            A.encaixa_ancoratges(anc((0, 4, 4), (8, 4, 4)), 0.0, [120.0])

    def test_metre_invalid(self):
        with self.assertRaises(ValueError):
            A.encaixa_ancoratges(anc((0, 0, 4), (8, 4, 4)), 8.0, [120.0])

    def test_compas_invalid_a_la_entrada(self):
        with self.assertRaises(ValueError):
            A.encaixa_ancoratges([(0, 4, 0), (8, 4, 4)], 8.0, [120.0])


class TestVerificacio(unittest.TestCase):
    def test_bona(self):
        r = A.encaixa_ancoratges(
            anc((0, 4, 4), (8, 4, 4), (20, 4, 4)), 26.0, [120.0, 120.0])
        self.assertTrue(A.verifica_ancoratges(
            r["trams"], anc((0, 4, 4), (8, 4, 4), (20, 4, 4)), r["offset"]))

    def test_dolenta(self):
        # Anchor a 4 s amb una graella que no hi passa (el compàs fa 1,778 s)
        trams = [(0.0, 8.0, 135.0, 4, 4), (8.0, 20.0, 120.0, 4, 4)]
        self.assertFalse(A.verifica_ancoratges(
            trams, anc((0, 4, 4), (4, 4, 4), (20, 4, 4)), 0.0))

    def test_bpm_de_n_es_l_invers_de_durada_compas(self):
        from app import tempo_map
        bpm = A.bpm_de_n(5, 6, 8, 7.345)
        self.assertAlmostEqual(
            5 * tempo_map.durada_compas(bpm, 6, 8), 7.345, places=9)


def _wav_sine(ruta, segons=1.0, sr=44100):
    """WAV PCM 16 mono amb una sinusoide de 440 Hz."""
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        n = int(sr * segons)
        dades = b"".join(
            struct.pack("<h", int(12000 * math.sin(2 * math.pi * 440 * i / sr)))
            for i in range(n))
        w.writeframes(dades)
    return ruta


def _durada_wav(ruta):
    with wave.open(ruta, "rb") as w:
        return w.getnframes() / float(w.getframerate())


class TestVelocitat(unittest.TestCase):
    """F2 / R11: estirament amb el to mantingut i relació de temps."""

    def test_cadena_atempo(self):
        self.assertEqual(ffmpeg.cadena_atempo(0.5), "atempo=0.500000")
        self.assertEqual(ffmpeg.cadena_atempo(2.0), "atempo=2.000000")
        self.assertEqual(ffmpeg.cadena_atempo(4.0),
                         "atempo=2.0,atempo=2.000000")
        self.assertEqual(ffmpeg.cadena_atempo(1.0), "atempo=1.000000")
        with self.assertRaises(ValueError):
            ffmpeg.cadena_atempo(0)

    def test_factor_1_torna_el_mateix(self):
        d = tempfile.mkdtemp()
        ruta = _wav_sine(os.path.join(d, "a.wav"))
        self.assertEqual(ffmpeg.estira_a_wav(ruta, 1.0), ruta)

    def test_velocitats_inclou_1_5_i_dividit(self):
        self.assertIn(1.5, ffmpeg.VELOCITATS)
        self.assertIn(1.0 / 1.5, ffmpeg.VELOCITATS)      # ⅔ = ÷1,5
        self.assertEqual(ffmpeg.cadena_atempo(1.5), "atempo=1.500000")
        self.assertEqual(ffmpeg.cadena_atempo(1.0 / 1.5), "atempo=0.666667")
        # cada velocitat té la seua caché (no es trepitgen)
        d = tempfile.mkdtemp()
        ruta = _wav_sine(os.path.join(d, "a.wav"))
        rutes = {f: ffmpeg.ruta_velocitat(ruta, f, d) for f in ffmpeg.VELOCITATS}
        self.assertEqual(len(set(rutes.values())), len(ffmpeg.VELOCITATS))

    def test_prepara_escolta_1_5_escurca(self):
        if not ffmpeg.disponible():
            self.skipTest("ffmpeg no disponible")
        d = tempfile.mkdtemp()
        ruta = _wav_sine(os.path.join(d, "a.wav"), segons=3.0)
        dest = ffmpeg.prepara_escolta(ruta, 1.5, carpeta=d)
        self.assertAlmostEqual(_durada_wav(dest), 3.0 / 1.5, places=2)

    def test_prepara_escolta_mono_1x_no_renderitza(self):
        d = tempfile.mkdtemp()
        ruta = _wav_sine(os.path.join(d, "a.wav"))       # mono PCM16
        self.assertEqual(ffmpeg.prepara_escolta(ruta, 1.0), ruta)

    def test_prepara_escolta_estereo_sempre_mono(self):
        """El WAV de l'usuari sol ser ESTÈREO: el transport necessita mono."""
        if not ffmpeg.disponible():
            self.skipTest("ffmpeg no disponible")
        d = tempfile.mkdtemp()
        ruta = os.path.join(d, "estereo.wav")
        with wave.open(ruta, "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(8000)
            w.writeframes(b"\x00\x00\x00\x00" * 8000)   # 1 s
        dest = ffmpeg.prepara_escolta(ruta, 1.0, carpeta=d)
        self.assertNotEqual(dest, ruta)
        with wave.open(dest, "rb") as w:
            self.assertEqual(w.getnchannels(), 1)
            self.assertEqual(w.getsampwidth(), 2)
            self.assertAlmostEqual(w.getnframes() / 8000.0, 1.0, places=2)

    def test_ruta_velocitat_determinista(self):
        d = tempfile.mkdtemp()
        ruta = _wav_sine(os.path.join(d, "a.wav"))
        r1 = ffmpeg.ruta_velocitat(ruta, 0.5, d)
        r2 = ffmpeg.ruta_velocitat(ruta, 0.5, d)
        r3 = ffmpeg.ruta_velocitat(ruta, 2.0, d)
        self.assertEqual(r1, r2)
        self.assertNotEqual(r1, r3)
        self.assertTrue(os.path.basename(r1).startswith(ffmpeg.PREFIX_VELOCITAT))
        self.assertTrue(r1.endswith(".wav"))

    def test_mig_tempo_duplica_la_durada(self):
        if not ffmpeg.disponible():
            self.skipTest("ffmpeg no disponible")
        d = tempfile.mkdtemp()
        ruta = _wav_sine(os.path.join(d, "a.wav"), 1.0)
        dest = ffmpeg.estira_a_wav(ruta, 0.5, carpeta=d)
        self.assertTrue(os.path.exists(dest))
        self.assertAlmostEqual(_durada_wav(dest), 2.0, delta=0.05)
        # t_real = t_estirat / factor  (R11)
        self.assertAlmostEqual(1.0 / 0.5, 2.0)

    def test_doble_tempo_plega_la_durada(self):
        if not ffmpeg.disponible():
            self.skipTest("ffmpeg no disponible")
        d = tempfile.mkdtemp()
        ruta = _wav_sine(os.path.join(d, "a.wav"), 2.0)
        dest = ffmpeg.estira_a_wav(ruta, 2.0, carpeta=d)
        self.assertAlmostEqual(_durada_wav(dest), 1.0, delta=0.05)

    def test_4x_i_caché(self):
        if not ffmpeg.disponible():
            self.skipTest("ffmpeg no disponible")
        d = tempfile.mkdtemp()
        ruta = _wav_sine(os.path.join(d, "a.wav"), 2.0)
        dest = ffmpeg.estira_a_wav(ruta, 4.0, carpeta=d)
        self.assertAlmostEqual(_durada_wav(dest), 0.5, delta=0.05)
        mida = os.path.getsize(dest)
        dest2 = ffmpeg.estira_a_wav(ruta, 4.0, carpeta=d)
        self.assertEqual(dest, dest2)
        self.assertEqual(os.path.getsize(dest2), mida)  # no s'ha re-renderitzat


if __name__ == "__main__":
    unittest.main()
