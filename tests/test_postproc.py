"""Casos límit de `app/postproc.py` (post-processat de l'anàlisi crua).

El post-processador NO és el límit del model: l'ordre, els negatius i la
cobertura es garanteixen DESPRÉS, a `pipeline.normalitza_cobertura()` (regles
d'or #1, #4 i #8). Ací es fixa què fa amb l'entrada rara perquè quede clar on
acaba la seua responsabilitat i que no peta (auditoria 18-10-2026).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import postproc  # noqa: E402


class TestProcessaAcords(unittest.TestCase):

    def test_buit_i_un_de_sol(self):
        self.assertEqual(postproc.processa_acords([], durada_min=0.0), [])
        self.assertEqual(postproc.processa_acords([(0.0, "C")], durada_min=0.0),
                         [(0.0, "C")])

    def test_duplicats_mateix_instant_es_fonen(self):
        self.assertEqual(
            postproc.processa_acords([(0.0, "C"), (2.0, "C")], durada_min=0.0),
            [(0.0, "C")])

    def test_un_sol_acord_no_el_treu_encara_que_siga_curt(self):
        """Amb `durada_min` gran, un acord sol no desapareix (no hi ha veí)."""
        self.assertEqual(postproc.processa_acords([(0.0, "C")], durada_min=3.0),
                         [(0.0, "C")])

    def test_no_ordena_ni_sana_negatius(self):
        """Documenta el CONTRACTE: això és post-processat, no el límit del
        model. L'ordre i els temps vàlids els garanteix `normalitza_cobertura`
        (regles #1 i #8), que és qui alimenta el model."""
        desordenat = [(4.0, "G"), (0.0, "C"), (2.0, "Am")]
        self.assertEqual(postproc.processa_acords(desordenat, durada_min=0.0),
                         desordenat)
        negatiu = [(-2.0, "C"), (2.0, "G")]
        self.assertEqual(postproc.processa_acords(negatiu, durada_min=0.0),
                         negatiu)


class TestSnapAcords(unittest.TestCase):

    def test_buit(self):
        self.assertEqual(postproc.snap_acords([], 120.0), [])

    def test_encaixa_al_mig_temps(self):
        """A 120 BPM la divisió és 0,5 s: 0,37 s va a 0,5."""
        self.assertEqual(postproc.snap_acords([(0.37, "C")], 120.0),
                         [(0.5, "C")])

    def test_bpm_zero_no_canvia_res(self):
        self.assertEqual(postproc.snap_acords([(0.37, "C")], 0.0),
                         [(0.37, "C")])

    def test_negatiu_va_a_zero(self):
        self.assertEqual(postproc.snap_acords([(-0.4, "C")], 120.0),
                         [(0.0, "C")])


if __name__ == "__main__":
    unittest.main()
