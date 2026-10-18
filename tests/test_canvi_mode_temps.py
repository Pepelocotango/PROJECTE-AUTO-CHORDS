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
import os
import sys
import tempfile
import unittest
import unittest.mock
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene dels tests: l'import té efecte (esborra els temporals en plegar)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app import config  # noqa: E402
from app import main as app_main  # noqa: E402

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


class _Base(unittest.TestCase):
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


class TestCanviModeTemps(_Base):
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


if __name__ == "__main__":
    unittest.main()
