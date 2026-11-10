"""Tests de la capa de dades `mapa_tempo.csv` (subplà de rubato, fase 2)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals

from app import mapa_tempo as M  # noqa: E402
from app import rubato  # noqa: E402
from app import tempo_map as tm  # noqa: E402


class TestTramMapa(unittest.TestCase):
    def test_compatible_amb_cinc_tuples(self):
        tm = M.TramMapa(1.0, 2.0, 120.0, "normal", "3/4")
        self.assertEqual(tuple(tm), (1.0, 2.0, 120.0, 3, 4))
        self.assertEqual(tm[2], 120.0)
        self.assertEqual(len(tm), 5)
        ini, fi, bpm, num, den = tm
        self.assertEqual((ini, fi, bpm, num, den), (1.0, 2.0, 120.0, 3, 4))
        self.assertEqual(tm.payload, (120.0, 3, 4))

    def test_rubato_te_el_primer_compas_a_num_den(self):
        tm = M.TramMapa(0.0, 15.0, 60.0, "rubato", "4/4*3+3/4")
        self.assertEqual(tm.num, 4)
        self.assertEqual(tm.den, 4)
        self.assertTrue(tm.lliure)
        self.assertEqual(tm.segments, ((4, 4, 3), (3, 4, 1)))

    def test_normal_no_admet_sequencia(self):
        with self.assertRaises(rubato.RubatoError):
            M.TramMapa(0.0, 4.0, 120.0, "normal", "4/4+3/4")

    def test_rubato_admet_denominadors_diferents(self):
        tm = M.TramMapa(0.0, 4.0, 120.0, "rubato", "4/4+6/8")
        self.assertEqual(tm.compassos, "4/4+6/8")
        self.assertEqual(tm.segments, ((4, 4, 1), (6, 8, 1)))

    def test_normal_no_admet_repeticions(self):
        with self.assertRaises(rubato.RubatoError):
            M.TramMapa(0.0, 8.0, 120.0, "normal", "4/4*2")

    def test_tipus_invalid(self):
        with self.assertRaises(rubato.RubatoError):
            M.TramMapa(0.0, 4.0, 120.0, "lliure", "4/4")

    def test_agrupacio_invalida(self):
        with self.assertRaises(ValueError):
            M.TramMapa(0.0, 4.0, 120.0, "normal", "7/8", "3+3")

    def test_des_de_tupla(self):
        tm = M.des_de_tupla((0.0, 4.0, 120.0, 3, 8))
        self.assertEqual(tm.tipus, "normal")
        self.assertEqual(tm.compassos, "3/8")


class TestNormalitzacio(unittest.TestCase):
    def test_normal_sense_rubato_delega_en_el_model_antic(self):
        trams = [(0.0, 2.0, 120.0, 4, 4), (2.0, 4.0, 120.0, 4, 4)]
        out, avisos = M.normalitza_trams_map(trams, 4.0, fusiona=True)
        self.assertEqual(out, [(0.0, 4.0, 120.0, 4, 4)])
        self.assertEqual(avisos, [])

    def test_rubato_es_preserva(self):
        rub = M.TramMapa(0.0, 7.0, 60.0, "rubato", "4/4+6/8")
        out, _avisos = M.normalitza_trams_map([rub], 7.0)
        self.assertEqual(out, [rub])

    def test_rubato_amb_durada_canviada_recalcula_bpm(self):
        rub = M.TramMapa(0.0, 7.0, 60.0, "rubato", "4/4+6/8")
        out, _avisos = M.normalitza_trams_map([rub], 14.0)
        self.assertEqual(out[0].compassos, "4/4+6/8")
        self.assertAlmostEqual(out[0].bpm, 30.0, places=6)

    def test_dos_rubatos_adjacents_es_fusionen(self):
        a = M.TramMapa(0.0, 4.0, 60.0, "rubato", "4/4")
        b = M.TramMapa(4.0, 7.0, 60.0, "rubato", "3/4")
        out, _avisos = M.normalitza_trams_map([a, b], 7.0, fusiona=True)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].compassos, "4/4+3/4")
        self.assertAlmostEqual(out[0].bpm, 60.0, places=6)

    def test_agrupacio_es_preserva_en_normalitzar(self):
        trams = [M.TramMapa(0.0, 4.0, 120.0, "normal", "7/8", "3+2+2")]
        out, _avisos = M.normalitza_trams_map(trams, 4.0, fusiona=True)
        self.assertEqual(out[0].agrupacio, "3+2+2")

    def test_agrupacio_no_impedix_fusionar_iguals(self):
        trams = [M.TramMapa(0.0, 2.0, 120.0, "normal", "6/8", "3+3"),
                 M.TramMapa(2.0, 4.0, 120.0, "normal", "6/8", "3+3")]
        out, _avisos = M.normalitza_trams_map(trams, 4.0, fusiona=True)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].agrupacio, "3+3")

    def test_agrupacions_diferents_no_es_fusionen(self):
        trams = [M.TramMapa(0.0, 2.0, 120.0, "normal", "7/8", "2+2+3"),
                 M.TramMapa(2.0, 4.0, 120.0, "normal", "7/8", "3+2+2")]
        out, _avisos = M.normalitza_trams_map(trams, 4.0, fusiona=True)
        self.assertEqual(len(out), 2)
        self.assertEqual([t.agrupacio for t in out], ["2+2+3", "3+2+2"])


class TestFitxer(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.ruta = os.path.join(self.td, M.NOM_MAPA_TEMPO)

    def test_roundtrip_normal(self):
        trams = [M.TramMapa(0.0, 4.0, 120.0, "normal", "4/4"),
                 M.TramMapa(4.0, 8.0, 90.0, "normal", "3/4")]
        M.desa_mapa_tempo(self.ruta, trams)
        self.assertEqual(M.llegeix_mapa_tempo(self.ruta), trams)

    def test_roundtrip_rubato(self):
        trams = [M.TramMapa(0.0, 15.0, 60.0, "rubato", "4/4*3+3/4"),
                 M.TramMapa(15.0, 20.0, 120.0, "normal", "4/4")]
        M.desa_mapa_tempo(self.ruta, trams)
        self.assertEqual(M.llegeix_mapa_tempo(self.ruta), trams)

    def test_roundtrip_agrupacio(self):
        trams = [M.TramMapa(0.0, 4.0, 120.0, "normal", "7/8", "3+2+2")]
        M.desa_mapa_tempo(self.ruta, trams)
        self.assertEqual(M.llegeix_mapa_tempo(self.ruta), trams)

    def test_llegeix_tuples_antigues(self):
        M.desa_mapa_tempo(self.ruta, [(0.0, 4.0, 120.0, 4, 4)])
        llegits = M.llegeix_mapa_tempo(self.ruta)
        self.assertEqual(len(llegits), 1)
        self.assertEqual(llegits[0].tipus, "normal")
        self.assertEqual(llegits[0].compassos, "4/4")

    def test_la_capcalera_es_ignora(self):
        with open(self.ruta, "w", encoding="utf-8", newline="") as f:
            f.write("inici,fi,bpm,tipus,compassos\n")
            f.write("0.000000,4.000000,120.000000,normal,4/4\n")
        self.assertEqual(len(M.llegeix_mapa_tempo(self.ruta)), 1)

    def test_files_dolentes_es_descarten(self):
        with open(self.ruta, "w", encoding="utf-8", newline="") as f:
            f.write("0,4,120,normal,4/4\n")
            f.write("4,8,120,normal,4/4+3/4\n")     # normal amb seqüència
            f.write("8,12,120,estrany,4/4\n")       # tipus invàlid
            f.write("12,16,120,normal\n")           # falten columnes
            f.write("16,20,120,normal,4/4\n")
        logs = []
        out = M.llegeix_mapa_tempo(self.ruta, log=logs.append)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0].ini, 0.0)
        self.assertEqual(out[1].ini, 16.0)
        self.assertEqual(len(logs), 3)

    def test_fitxer_absent(self):
        self.assertEqual(M.llegeix_mapa_tempo(self.ruta), [])

    def test_te_format_antic(self):
        self.assertFalse(M.te_format_antic(self.td))
        open(os.path.join(self.td, "tempo.csv"), "w").close()
        self.assertTrue(M.te_format_antic(self.td))

    def test_a_tuples(self):
        trams = [M.TramMapa(0.0, 4.0, 120.0, "normal", "4/4"),
                 M.TramMapa(4.0, 8.0, 120.0, "rubato", "4/4*2")]
        self.assertEqual(M.a_tuples(trams),
                         [(0.0, 4.0, 120.0, 4, 4),
                          (4.0, 8.0, 120.0, 4, 4)])


if __name__ == "__main__":      # pragma: no cover
    unittest.main()


class TestDiagnosticCompassos(unittest.TestCase):
    def test_detecta_n_fraccionari_i_ignora_preroll(self):
        trams = [
            M.TramMapa(0.0, 2.0, 120.0, "normal", "4/4"),
            M.TramMapa(2.0, 14.5, 120.0, "normal", "4/4"),
        ]
        issues = tm.problemes_compassos_sencers(
            trams, 14.5, offset=2.0)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["idx"], 1)
        self.assertAlmostEqual(issues[0]["n"], 6.25, places=6)


class TestQuantitzaBpm(unittest.TestCase):
    def test_quantitza_tres_normals_a_un_decimal(self):
        bq = 4.0
        bpms = (145.023, 143.984, 144.348)
        trams = []
        ini = 0.0
        for bpm in bpms:
            fi = ini + 4 * bq * 60.0 / bpm
            trams.append(M.TramMapa(ini, fi, bpm, "normal", "4/4"))
            ini = fi
        durada = ini
        out = M.quantitza_bpm(trams, durada, decimals=1)
        self.assertEqual([round(t.bpm, 1) for t in out],
                         [145.0, 144.0, 144.3])
        self.assertAlmostEqual(out[-1].fi, durada, places=9)
        for t in out[:-1]:
            self.assertAlmostEqual(
                (t.fi - t.ini) * t.bpm / (4 * 60.0), 4.0, places=6)

    def test_quantitza_preserva_el_preroll(self):
        pre = M.TramMapa(0.0, 2.0, 108.738, "normal", "3/4")
        music = M.TramMapa(2.0, 2.0 + 4 * 3 * 60.0 / 105.918,
                           105.918, "normal", "3/4")
        out = M.quantitza_bpm([pre, music], 30.0, decimals=2, offset=2.0)
        self.assertEqual(tuple(out[0]), tuple(pre))
        self.assertAlmostEqual(out[1].ini, 2.0, places=9)
        self.assertEqual(out[1].bpm, 105.92)

    def test_quantitza_preroll_inconsistent_avisa(self):
        pre = M.TramMapa(0.0, 1.655325, 108.74, "normal", "3/4")
        music = M.TramMapa(1.655325, 8.0, 105.92, "normal", "3/4")
        with self.assertRaises(ValueError):
            M.quantitza_bpm([pre, music], 30.0, decimals=2, offset=2.20714)

    def test_quantitza_arrodoneix_mig_cap_amunt(self):
        def trams(bpms):
            ini = 0.0
            out = []
            for bpm in bpms:
                fi = ini + 4 * 4 * 60.0 / bpm
                out.append(M.TramMapa(ini, fi, bpm, "normal", "4/4"))
                ini = fi
            return out, ini

        ts, d = trams((145.5, 144.5))
        out = M.quantitza_bpm(ts, d, decimals=0)
        self.assertEqual([t.bpm for t in out], [146.0, 145.0])

        ts, d = trams((145.25, 144.25))
        out = M.quantitza_bpm(ts, d, decimals=1)
        self.assertEqual([t.bpm for t in out], [145.3, 144.3])

    def test_quantitza_zero_i_dos_decimals(self):
        bq = 4.0
        trams = []
        ini = 0.0
        for bpm in (145.023, 143.984, 144.348):
            fi = ini + 4 * bq * 60.0 / bpm
            trams.append(M.TramMapa(ini, fi, bpm, "normal", "4/4"))
            ini = fi
        out0 = M.quantitza_bpm(trams, ini, decimals=0)
        self.assertEqual([t.bpm for t in out0], [145.0, 144.0, 144.0])
        out2 = M.quantitza_bpm(trams, ini, decimals=2)
        self.assertEqual([round(t.bpm, 2) for t in out2],
                         [145.02, 143.98, 144.35])

    def test_rubato_no_es_quantitza_pero_es_desplaça(self):
        bq = 4.0
        d1 = 4 * bq * 60.0 / 145.023
        dur_rub = 2.5
        d2 = 4 * bq * 60.0 / 143.984
        trams = [
            M.TramMapa(0.0, d1, 145.023, "normal", "4/4"),
            M.TramMapa(d1, d1 + dur_rub, 100.0, "rubato", "4/4*2"),
            M.TramMapa(d1 + dur_rub, d1 + dur_rub + d2, 143.984,
                       "normal", "4/4"),
        ]
        out = M.quantitza_bpm(trams, trams[-1].fi, decimals=1)
        self.assertEqual(out[0].bpm, 145.0)
        self.assertEqual(out[1].tipus, "rubato")
        self.assertAlmostEqual(out[1].fi - out[1].ini, dur_rub, places=9)
        self.assertAlmostEqual(out[1].ini, out[0].fi, places=9)
        self.assertEqual(out[2].bpm, 144.0)
