"""Model unificat de clips (inici+fi) — refactor S1 (docs/REFACTOR_INICI_FI.md).

Criteri d'èxit de S1: **cap canvi de comportament**. Les funcions noves han de
reproduir EXACTAMENT el que fa avui `pipeline.normalitza_cobertura` (que no es
toca) sobre el corpus dels dos tipus (acords i estructura).
"""
import unittest
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene dels tests: l'import té efecte (esborra en plegar)

from app import pipeline

SENSE_A = (pipeline.SENSE_ACORD, "0.000000000")
SENSE_S = (pipeline.SENSE_SECCIO, pipeline.SENSE_SECCIO)
D = 10.0


class TestAdaptadors(unittest.TestCase):
    """`clip` ↔ model actual, anada i tornada."""

    def test_acords_a_clips_deriva_el_fi(self):
        ac = [(0.0, "C", "0.000000000"), (2.0, "Am", "2.000000000")]
        c = pipeline.clips_d_acords(ac, D)
        self.assertEqual([(x.ini, x.fi) for x in c], [(0.0, 2.0), (2.0, D)])
        self.assertEqual(c[0].payload, ("C", "0.000000000"))

    def test_acords_anada_i_tornada(self):
        ac = [(0.0, "C", "0"), (2.0, "Am", "0")]
        self.assertEqual(pipeline.acords_de_clips(
            pipeline.clips_d_acords(ac, D)), ac)

    def test_seccions_anada_i_tornada(self):
        s = [(0.0, 4.0, "A", "A"), (4.0, 10.0, "B", "B")]
        self.assertEqual(pipeline.seccions_de_clips(
            pipeline.clips_de_seccions(s)), s)

    def test_clip_es_comporta_com_a_tupla(self):
        c = pipeline.Clip(0.0, 2.0, ("C", "0"))
        self.assertEqual(tuple(c), (0.0, 2.0, ("C", "0")))
        ini, fi, payload = c
        self.assertEqual((ini, fi), (0.0, 2.0))
        self.assertEqual(payload, ("C", "0"))


class TestEquivalencia(unittest.TestCase):
    """`normalitza_clips` ha de donar el MATEIX que `normalitza_cobertura`."""

    CASOS_ACORDS = [
        [(0.0, "C", "0.000000000")],
        [(0.0, "C", "0"), (2.0, "Am", "0"), (4.0, "F", "0")],
        [(2.0, "C", "0")],                                       # capçalera N
        [(0.0, "C", "0"), (10.0, "Am", "0")],                     # fora de la WAV
        [(0.0, "C", "0"), (2.0, "Am", "0"), (2.004, "F", "0")],   # xoc al CSV
        [(0.0, "C", "0"), (9.999, "Am", "0")],
        [(2.0, "C", "0"), (2.004, "F", "0"), (5.0, "G", "0")],
    ]
    CASOS_SECCIONS = [
        [(0.0, 10.0, "A", "A")],
        [(2.0, 4.0, "A", "A")],                                  # capçalera
        [(2.0, 4.0, "A", "A"), (5.0, 7.0, "B", "B")],             # forat intern
        [(0.0, 12.0, "A", "A")],                                 # fi > durada
        [(0.0, 2.0, "A", "A"), (12.0, 14.0, "B", "B")],           # fora
        [(0.0, 3.0, "A", "A"), (7.0, 10.0, "-", "-")],
    ]

    def test_acords_equivalent(self):
        for ac in self.CASOS_ACORDS:
            amb, _ = pipeline.normalitza_cobertura([tuple(x) for x in ac], [], D)
            nou = pipeline.acords_de_clips(pipeline.normalitza_clips(
                pipeline.clips_d_acords(ac, D), D, forat=SENSE_A,
                arrodoneix=True, deriva_fi=True))
            self.assertEqual(nou, amb, f"acords {ac}")

    def test_seccions_equivalent(self):
        for s in self.CASOS_SECCIONS:
            _, amb = pipeline.normalitza_cobertura([], [tuple(x) for x in s], D)
            nou = pipeline.seccions_de_clips(pipeline.normalitza_clips(
                pipeline.clips_de_seccions(s), D, forat=SENSE_S))
            self.assertEqual(nou, amb, f"seccions {s}")

    def test_cobertura_exacta(self):
        for s in self.CASOS_SECCIONS:
            cl = pipeline.normalitza_clips(pipeline.clips_de_seccions(s), D,
                                           forat=SENSE_S)
            self.assertAlmostEqual(cl[0].ini, 0.0)
            self.assertAlmostEqual(cl[-1].fi, D)
            for a, b in zip(cl, cl[1:]):
                self.assertAlmostEqual(a.fi, b.ini)

    def test_cadena_sense_forats_ni_solapaments(self):
        for ac in self.CASOS_ACORDS:
            cl = pipeline.normalitza_clips(pipeline.clips_d_acords(ac, D), D,
                                           forat=SENSE_A, arrodoneix=True,
                                           deriva_fi=True)
            for a, b in zip(cl, cl[1:]):
                self.assertAlmostEqual(a.fi, b.ini)

    def test_treure_zona_determinista(self):
        """Dos clips que es trepitgen: mana l'inici del segon (regla única)."""
        s = [(0.0, 6.0, "A", "A"), (4.0, 10.0, "B", "B")]
        cl = pipeline.normalitza_clips(pipeline.clips_de_seccions(s), D,
                                       forat=SENSE_S)
        self.assertEqual([(x.ini, x.fi) for x in cl],
                         [(0.0, 4.0), (4.0, 10.0)])

    def test_no_muta_l_entrada(self):
        s = [(2.0, 4.0, "A", "A")]
        copia = list(s)
        pipeline.normalitza_clips(pipeline.clips_de_seccions(s), D, forat=SENSE_S)
        self.assertEqual(s, copia)

    def test_forat_porta_el_payload_de_forat(self):
        s = [(2.0, 4.0, "A", "A"), (6.0, 8.0, "B", "B")]
        cl = pipeline.normalitza_clips(pipeline.clips_de_seccions(s), D,
                                       forat=SENSE_S)
        self.assertEqual([x.payload for x in cl],
                         [SENSE_S, ("A", "A"), SENSE_S, ("B", "B")])


if __name__ == "__main__":   # pragma: no cover
    unittest.main()
