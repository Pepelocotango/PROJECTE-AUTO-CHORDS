"""Tests del motor pur de derivació de rubato (subplà de rubato, fase 1)."""
import unittest

from app import rubato


class TestDerivacio(unittest.TestCase):
    def test_cas_a_15s_a_60bpm(self):
        d = rubato.deriva(15.0, 60.0, 4, 4)
        self.assertAlmostEqual(d.bpm, 60.0, places=6)
        self.assertEqual(d.pulsos, 15)
        self.assertEqual(d.compassos, "4/4*3+3/4")
        self.assertEqual(d.segments, ((4, 4, 3), (3, 4, 1)))

    def test_resta_2(self):
        d = rubato.deriva(14.0, 60.0, 4, 4)
        self.assertEqual(d.compassos, "4/4*3+2/4")
        self.assertAlmostEqual(d.bpm, 60.0, places=6)

    def test_resta_5(self):
        d = rubato.deriva(13.0, 60.0, 4, 4)
        self.assertEqual(d.compassos, "4/4*2+5/4")
        self.assertAlmostEqual(d.bpm, 60.0, places=6)

    def test_multiple_exacte(self):
        d = rubato.deriva(16.0, 60.0, 4, 4)
        self.assertEqual(d.compassos, "4/4*4")
        self.assertEqual(d.pulsos, 16)

    def test_referencia_3_4(self):
        d = rubato.deriva(15.0, 60.0, 3, 4)
        self.assertEqual(d.compassos, "3/4*5")

    def test_referencia_6_8(self):
        d = rubato.deriva(15.0, 60.0, 6, 8)
        self.assertEqual(d.compassos, "6/8*5")
        self.assertEqual(d.den, 8)
        self.assertAlmostEqual(d.quarters, 15.0)

    def test_referencia_2_2(self):
        d = rubato.deriva(7.0, 60.0, 2, 2)
        self.assertEqual(d.compassos, "2/2+3/4")
        self.assertAlmostEqual(d.quarters, 7.0)

    def test_referencia_9_4(self):
        d = rubato.deriva(17.0, 60.0, 9, 4)
        self.assertEqual(d.compassos, "9/4+4/2")
        self.assertEqual(d.segments, ((9, 4, 1), (4, 2, 1)))
        self.assertAlmostEqual(d.quarters, 17.0)

    def test_cas_b_25_pulsos(self):
        d = rubato.deriva(15.0, 100.0, 4, 4)
        self.assertEqual(d.pulsos, 25)
        self.assertAlmostEqual(d.bpm, 100.0, places=6)
        self.assertEqual(d.compassos, "4/4*5+5/4")

    def test_cas_c_15s_a_100bpm(self):
        d = rubato.deriva(15.0, 100.0, 4, 4)
        self.assertEqual(d.pulsos, 25)
        self.assertEqual(d.bpm, 100.0)


class TestBandes(unittest.TestCase):
    def test_massa_curt_per_a_la_banda(self):
        with self.assertRaises(rubato.RubatoError):
            rubato.deriva(0.1, 60.0, 4, 4)

    def test_un_sol_puls_no_es_representable(self):
        with self.assertRaises(rubato.RubatoError):
            rubato.deriva(1.0, 60.0, 4, 4)

    def test_ajusta_el_nombre_de_pulsos_a_la_banda(self):
        d = rubato.deriva(1.0, 350.0, 4, 4)
        self.assertEqual(d.pulsos, 5)
        self.assertAlmostEqual(d.bpm, 300.0, places=6)
        self.assertEqual(d.compassos, "5/4")

    def test_bpm_350_exacte_no_baixa_de_puls(self):
        durada = 3 * 60.0 / 350.0
        d = rubato.deriva(durada, 350.0, 3, 4)
        self.assertEqual(d.pulsos, 3)
        self.assertAlmostEqual(d.bpm, 350.0, places=6)
        self.assertLessEqual(d.bpm, 350.0)
        self.assertEqual(d.compassos, "3/4")

    def test_bpm_sempre_dins_de_la_banda(self):
        ok = 0
        for durada in (2.0, 3.7, 8.0, 15.0, 31.0):
            for bpm in (30.0, 60.0, 120.0, 350.0):
                try:
                    d = rubato.deriva(durada, bpm, 4, 4)
                except rubato.RubatoError:
                    continue          # pot no haver-hi cap compàs estàndard
                ok += 1
                self.assertGreaterEqual(d.bpm, 30.0)
                self.assertLessEqual(d.bpm, 350.0)
                self.assertAlmostEqual(
                    d.pulsos * 60.0 / durada, d.bpm, places=9)
        self.assertGreater(ok, 0, "cap cas vàlid: la prova no cobreix res")

    def test_maxim_quatre_segments(self):
        for n in range(2, 301):
            d = rubato.deriva(float(n), 60.0, 4, 4)
            self.assertLessEqual(len(d.segments), 4, n)
            self.assertAlmostEqual(
                sum(num * 4.0 / den * count
                    for num, den, count in d.segments), d.pulsos)
            self.assertLessEqual(
                sum(count for _, _, count in d.segments), rubato.MAX_BARS)

    def test_propietats_en_families(self):
        for bpm, num, den in ((60.0, 4, 4), (60.0, 3, 4), (60.0, 5, 4),
                              (60.0, 6, 8), (60.0, 9, 4), (60.0, 2, 2)):
            for n in range(2, 301):
                try:
                    d = rubato.deriva(float(n), bpm, num, den)
                except rubato.RubatoError:
                    continue
                self.assertAlmostEqual(
                    sum(m * 4.0 / dd * c for m, dd, c in d.segments),
                    d.pulsos, msg=(num, den, n))
                self.assertLessEqual(len(d.segments), 4)
                self.assertLessEqual(
                    sum(c for _, _, c in d.segments), rubato.MAX_BARS)
                self.assertEqual(rubato.text_a_compassos(d.compassos),
                                 d.segments)
                self.assertEqual(
                    rubato.compassos_a_text(d.segments), d.compassos)

    def test_litimit_de_999_compassos_no_dona_falsos_negatius(self):
        for durada, num, den in ((6992.0, 4, 4), (8965.0, 9, 4),
                                 (4021.0, 4, 4)):
            d = rubato.deriva(durada, 60.0, num, den)
            self.assertLessEqual(
                sum(c for _, _, c in d.segments), rubato.MAX_BARS,
                d.compassos)
            self.assertAlmostEqual(
                sum(m * 4.0 / dd * c for m, dd, c in d.segments),
                d.pulsos, msg=d.compassos)

    def test_prioritat_de_la_referencia_en_rubatos_llargs(self):
        d = rubato.deriva(4021.0, 60.0, 4, 4)
        self.assertEqual(
            sum(c for m, _dd, c in d.segments if (m, _dd) == (4, 4)), 992)
        self.assertLessEqual(
            sum(c for _, _, c in d.segments), rubato.MAX_BARS)

    def test_casos_impossibles_llargs_no_penjen(self):
        for durada, num, den in ((11985.0, 6, 8), (11987.0, 12, 4),
                                 (11987.0, 1, 8)):
            with self.assertRaises(rubato.RubatoError):
                rubato.deriva(durada, 60.0, num, den)


class TestSintaxi(unittest.TestCase):
    def test_parseja_la_forma_canonica(self):
        self.assertEqual(rubato.text_a_compassos("4/4*3+3/4"),
                         ((4, 4, 3), (3, 4, 1)))
        self.assertEqual(rubato.text_a_compassos("4/4"), ((4, 4, 1),))
        self.assertEqual(rubato.text_a_compassos("4/4+6/8"),
                         ((4, 4, 1), (6, 8, 1)))

    def test_presenta_per_a_la_ui(self):
        self.assertEqual(rubato.presenta_compassos("4/4*3+3/4"),
                         "4/4 × 3 + 3/4")
        self.assertEqual(rubato.presenta_compassos("4/4+6/8"),
                         "4/4 + 6/8")

    def test_rebutja_variants_no_canoniques(self):
        for text in ("4/4 × 3+3/4", "4/4 * 3", " 4/4", "4/4*0",
                     "0/4", "13/4", "4/16",
                     "4/4*1", "4/4+4/4", "4/4*3+4/4",
                     "04/4", "4/04", "4/4*01",
                     "4/4+4/4+4/4+4/4+4/4",
                     "4/4*999+3/4*999"):
            with self.assertRaises(rubato.RubatoError, msg=text):
                rubato.text_a_compassos(text)

    def test_compassos_a_text(self):
        self.assertEqual(rubato.compassos_a_text([(4, 4, 3), (3, 4, 1)]),
                         "4/4*3+3/4")
        self.assertEqual(rubato.compassos_a_text([(4, 4, 1)]), "4/4")
        self.assertEqual(rubato.compassos_a_text([(4, 4, 1), (4, 4, 2)]),
                         "4/4*3")
        self.assertEqual(rubato.compassos_a_text([(4, 4, 1), (6, 8, 1)]),
                         "4/4+6/8")

    def test_compassos_a_text_valida(self):
        for segments in ([(4, 4, 1000)], [(4, 16, 1)], [(13, 4, 1)],
                         [(4, 4, 999), (3, 4, 999)]):
            with self.assertRaises(rubato.RubatoError):
                rubato.compassos_a_text(segments)


class TestReferencia(unittest.TestCase):
    def test_anterior_mana(self):
        self.assertEqual(
            rubato.tria_referencia([(90.0, 3, 4)], [(120.0, 4, 4)],
                                   (100.0, 4, 4)),
            (90.0, 3, 4))

    def test_si_no_hi_ha_anterior_usa_el_seguent(self):
        self.assertEqual(
            rubato.tria_referencia([], [(120.0, 4, 4)], (100.0, 4, 4)),
            (120.0, 4, 4))

    def test_si_no_hi_ha_cap_usa_el_transport(self):
        self.assertEqual(
            rubato.tria_referencia([], [], (100.0, 4, 4)),
            (100.0, 4, 4))

    def test_ignora_referencies_invalides(self):
        self.assertEqual(
            rubato.tria_referencia([None, (0.0, 4, 4)], [], (100.0, 4, 4)),
            (100.0, 4, 4))

    def test_accepta_una_sola_tupla(self):
        self.assertEqual(
            rubato.tria_referencia((90.0, 3, 4), [], (100.0, 4, 4)),
            (90.0, 3, 4))

    def test_rebutja_compassos_no_enters(self):
        self.assertEqual(
            rubato.tria_referencia([(90.0, 4.9, 4)], [], (100.0, 4, 4)),
            (100.0, 4, 4))

    def test_sense_cap_referencia(self):
        with self.assertRaises(rubato.RubatoError):
            rubato.tria_referencia([], [], None)


if __name__ == "__main__":      # pragma: no cover
    unittest.main()
