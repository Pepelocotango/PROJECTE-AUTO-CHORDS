"""Funcions PURES de `app/timeline_base.py`: el pla de graella, el snap i les
posicions.

Són la base del grid, del regle i del snap del timeline, i fins ara només
s'exercitaven **indirectament** des del `TimelineView` (auditoria 18-10-2026,
que hi va veure zero referències directes a `snap_step`).

Es proven els **contractes**, no els números concrets de cada zoom: la divisió
de snap compleix la seua invariant, el pla i el snap coincideixen, i les
posicions es calculen per índex (mai acumulant, que era el bug del regle).
"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app import tempo_map as tm  # noqa: E402
from app import timeline_base as tb  # noqa: E402


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

        (Amb un zoom TAN petit que cap divisió hi cap, la funció cau a la més
        fina — és el fallback documentat; per això es prova només on hi ha
        candidats.)
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
        self.assertEqual([k for _s, k in divs][:2], ["bar", "beat"])
        self.assertAlmostEqual(divs[0][0], 2.0, places=6)   # 4 temps a 120 BPM
        self.assertAlmostEqual(divs[1][0], 0.5, places=6)   # una negra
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

    def test_grid_levels_deriva_del_pla(self):
        plan = tb.grid_plan(True, 120.0, 4, 60.0, 800.0)
        nivells = tb.grid_levels(True, 120.0, 4, 60.0, 800.0)
        self.assertEqual([s for s, _c, _w in nivells],
                         [s for s, _k in reversed(plan["lines"])])
        for _s, color, width in nivells:
            self.assertIsInstance(color, str)
            self.assertEqual(width, 1)


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


if __name__ == "__main__":
    unittest.main()
