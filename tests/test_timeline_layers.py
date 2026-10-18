"""Proves de les CAPES del timeline (`app/timeline_layers.py`).

La suite exercitava les capes sobretot pel **paint** («no peta») i a través del
`TimelineView`. Però `TempoLayer._zona()` és el **cor del gest** de la pista de
BPM/compàs: decideix si l'arrossegament mou una **vora** o el **punt de canvi**
(i, amb ell, què passa amb els veïns). No tenia cap prova pròpia (auditoria
18-10-2026).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene dels tests: l'import té efecte (esborra els temporals en plegar)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtCore import Qt  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from app import tempo_map as tm  # noqa: E402
from app import timeline_layers as L  # noqa: E402

TRAMS = [(0.0, 5.0, 120.0, 4, 4), (5.0, 10.0, 90.0, 3, 4),
         (10.0, 20.0, 100.0, 4, 4)]


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])


class TestTempoLayerZones(_Base):
    """`_zona(x)` -> (índex, zona) amb zona ∈ {ini, fi, cos, None}."""

    def _capa(self, actiu=True):
        capa = L.TempoLayer(20, 60.0, 0.0, 0.0, 20.0)
        capa.set_mapa(tm.TempoMap(TRAMS), actiu)
        return capa

    def test_vores_i_cos_de_cada_bloc(self):
        capa = self._capa()
        # tram 0 [0,5) -> x 0..300 ; tram 1 [5,10) -> 300..600 ; 2 [10,20) -> 600..1200
        # (a la frontera 300 és COMPARTIDA: el tram 0 respon «fi» i el tram 1
        #  «ini»; tots dos són el mateix punt de canvi i el visor els tracta
        #  igual. La comprovació d'«ini» es fa al tram 2, on el tram anterior no
        #  pot respondre «fi» — si no, el test no distingiria les dues vores.)
        self.assertIn(capa._zona(301.0), [(0, "fi"), (1, "ini")])
        self.assertEqual(capa._zona(603.0), (2, "ini"))
        self.assertEqual(capa._zona(450.0), (1, "cos"))
        self.assertEqual(capa._zona(700.0), (2, "cos"))

    def test_els_extrems_no_tenen_vora_draggable(self):
        """El PRIMER tram no té vora esquerra i l'ÚLTIM no en té de dreta: el
        mapa sempre comença a 0 i acaba a la durada."""
        capa = self._capa()
        self.assertEqual(capa._zona(1.0), (0, "cos"))
        self.assertEqual(capa._zona(1199.0), (2, "cos"))

    def test_fora_del_mapa(self):
        capa = self._capa()
        self.assertEqual(capa._zona(-500.0), (-1, None))

    def test_sense_mapa_ni_activa_no_hi_ha_zones(self):
        capa = self._capa(actiu=False)
        self.assertEqual(capa._zona(450.0), (-1, None))
        buida = L.TempoLayer(20, 60.0, 0.0, 0.0, 20.0)   # sense mapa
        self.assertEqual(buida._zona(450.0), (-1, None))

    def test_cursor_de_zona_com_les_altres_pistes(self):
        """Paritat #11: ↔ a les vores, mà OBLERTA al cos, fletxa al buit.

        Es prova la funció pura (PyQt5 no deixa fabricar un event de *hover*),
        i que el *hover* la fa servir amb la zona que toca.
        """
        capa = self._capa()
        self.assertEqual(capa._cursor_de_zona("ini"), Qt.SizeHorCursor)
        self.assertEqual(capa._cursor_de_zona("fi"), Qt.SizeHorCursor)
        self.assertEqual(capa._cursor_de_zona("cos"), Qt.OpenHandCursor)
        self.assertEqual(capa._cursor_de_zona(None), Qt.ArrowCursor)
        # i la zona que calcula per a una x concreta
        self.assertEqual(capa._zona(450.0)[1], "cos")


class TestTempoLayerSeleccio(_Base):

    def test_select_deselecciona(self):
        capa = L.TempoLayer(20, 60.0, 0.0, 0.0, 20.0)
        capa.set_mapa(tm.TempoMap(TRAMS), True)
        self.assertEqual(capa._sel, -1)
        capa.select(1)
        self.assertEqual(capa._sel, 1)
        capa.deselecciona()
        self.assertEqual(capa._sel, -1)


if __name__ == "__main__":
    unittest.main()
