"""Lògica dels DIÀLEGS (`app/dialegs.py`) — sense obrir-los.

Els tests de la resta del projecte **sempre bypassen** els diàlegs (patch de
`QMessageBox`/`QInputDialog`, o cridant directament la lògica del visor), així
que les 600 línies de `app/dialegs.py` no tenien cap prova: ni el parsing del
compàs, ni `valors()`, ni l'add/delete de trams del mapa (auditoria
18-10-2026).

Ací es construeixen els diàlegs (sense `exec_()`, sense ensenyar-los) i es prova
la seua lògica, que és on viu el que pot fallar.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtWidgets import QApplication  # noqa: E402

from app import dialegs  # noqa: E402


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])


class TestDialegTramTempo(_Base):
    """`valors()` — el compàs s'escriu «num/den» o «num»."""

    def _dlg(self, compas="4/4", bpm=120.0):
        d = dialegs.DialegTramTempo(None, inici=4.0, bpm=bpm, num=4, den=4)
        d.ed_compas.setText(compas)
        return d

    def test_compas_amb_barra(self):
        self.assertEqual(self._dlg("3/8").valors(), (120.0, 3, 8))

    def test_compas_amb_espais(self):
        self.assertEqual(self._dlg(" 6 / 4 ").valors(), (120.0, 6, 4))

    def test_compas_nomes_numerador(self):
        """«5» vol dir 5/4 (el denominador es conserva a 4)."""
        self.assertEqual(self._dlg("5").valors(), (120.0, 5, 4))

    def test_compas_invalid_cau_a_4_4(self):
        self.assertEqual(self._dlg("abc").valors(), (120.0, 4, 4))
        self.assertEqual(self._dlg("3/x").valors(), (120.0, 4, 4))
        self.assertEqual(self._dlg("").valors(), (120.0, 4, 4))

    def test_compas_mai_zero(self):
        """El compàs sempre és positiu (regla #12 de les dades: valors vàlids)."""
        self.assertEqual(self._dlg("0/0").valors(), (120.0, 1, 1))

    def test_el_bpm_surt_del_camp(self):
        self.assertEqual(self._dlg(bpm=97.5).valors()[0], 97.5)


class TestDialegTempoMapa(_Base):
    """Parsing compàs→segons i add/delete de trams (el que fa el diàleg)."""

    TRAMS = [(0.0, 4.0, 120.0, 4, 4), (4.0, 8.0, 90.0, 4, 4)]

    def _dlg(self, trams=None, durada=8.0):
        return dialegs.DialegTempoMapa(
            None, trams=list(self.TRAMS if trams is None else trams),
            durada=durada)

    def test_compas_a_segons(self):
        """Amb 120 BPM i 4/4 el compàs fa 2 s: el 3 comença a 4,0 s."""
        d = self._dlg()
        self.assertAlmostEqual(d._temps_de_compas("3"), 4.0, places=6)

    def test_compas_i_temps_escala_amb_el_mapa(self):
        """«3.2» = compàs 3 + un temps MÉS, amb el tempo d'AQUELL tram.

        El compàs 3 cau al segon tram (90 BPM): el temps hi fa 0,667 s, no 0,5
        (els 120 BPM del primer). El diàleg ha de fer cas del MAPA, no del BPM
        de la barra.
        """
        from app import tempo_map as tm
        d = self._dlg()
        mapa = tm.TempoMap(tm.normalitza_trams(self.TRAMS, 8.0))
        self.assertAlmostEqual(d._temps_de_compas("3.2"),
                               mapa.t_de_pos(3, 2), places=6)
        self.assertAlmostEqual(d._temps_de_compas("3.2"), 4.0 + 2.0 / 3.0,
                               places=6)

    def test_compas_1_es_l_inici(self):
        self.assertAlmostEqual(self._dlg()._temps_de_compas("1"), 0.0, places=6)

    def test_afegeix_un_tram_al_mig_del_darrer(self):
        d = self._dlg()
        d._afegeix()
        trams = d.trams()
        self.assertEqual(len(trams), 3)
        self.assertAlmostEqual(float(trams[-1][0]), 6.0, places=6)  # (4+8)/2
        self.assertEqual(float(trams[-1][2]), 90.0)   # hereta el tempo del tros

    def test_elimina_no_toca_el_valor_inicial(self):
        d = self._dlg()
        d.taula.setCurrentCell(0, 0)
        d._elimina()
        self.assertEqual(len(d.trams()), 2, "la fila 0 és el valor inicial")

    def test_elimina_un_tram_del_mig(self):
        d = self._dlg(trams=[(0.0, 4.0, 120.0, 4, 4), (4.0, 6.0, 90.0, 3, 4),
                             (6.0, 8.0, 100.0, 4, 4)])
        d.taula.setCurrentCell(1, 0)
        d._elimina()
        trams = d.trams()
        self.assertEqual(len(trams), 2)
        self.assertAlmostEqual(float(trams[0][1]), 6.0, places=6)

    def test_trams_sempre_contigus_i_coberts(self):
        """El que entrega el diàleg és un mapa vàlid (regles #1/#2/#4)."""
        d = self._dlg()
        d._afegeix()
        trams = d.trams()
        self.assertEqual(float(trams[0][0]), 0.0)
        self.assertAlmostEqual(float(trams[-1][1]), 8.0, places=6)
        self.assertEqual([float(t[1]) for t in trams[:-1]],
                         [float(t[0]) for t in trams[1:]])


if __name__ == "__main__":
    unittest.main()
