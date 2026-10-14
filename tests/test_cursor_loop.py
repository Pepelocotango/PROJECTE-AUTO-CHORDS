"""El cursor vermell ha d'anar ON sona el so quan hi ha un loop A/B.

Bug (operador, 14-10): amb el loop A/B actiu, `play` amb el cursor FORA del
bucle fa sonar el so des de `loop_a` (el feeder hi salta tot sol: `_alimenta`
fa `if pos < a or pos >= b: pos = a`), però el **cursor vermell es quedava on
era** → la visualització anava desalineada del so fins que la posició visual
atrapava `loop_b` (i encara llavors queia a mig bucle). També passava fent un
**seek** fora del bucle mentre sona (`ves_a` → `_engega_des_de`).

Fix: `visor._engega_des_de()` aplica el MATEIX salt que el feeder (si hi ha
loop i el punt demanat és fora de `[loop_a, loop_b)`, arrenca a `loop_a`) i
sincronitza el cursor (posició + timeline + lliscador + etiquetes) a l'instant.

Els tests no depenen de maquinari d'àudio: s'injecta un motor FALS (mateixa
interfície que `audio_out.crea_motor`) el `write()` del qual es bloqueja, així
el fil d'alimentació no acaba sol durant el test.
"""
import os
import sys
import tempfile
import threading
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from unittest.mock import patch  # noqa: E402

import PyQt5.QtWidgets as QW  # noqa: E402

from app import audio_out  # noqa: E402
from app import visor as app_visor  # noqa: E402

_VISORS = []


def _wav(segons=20):
    fd, ruta = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * segons)
    return ruta


def _visor():
    v = app_visor.Visor(_wav(), None, None, 120.0, 4, True)
    v.player, v.player_args = "paplay", []   # crea_motor queda substituït
    _VISORS.append(v)
    return v


class _FakeMotor:
    """Motor d'àudio fals, amb la interfície d'`audio_out.crea_motor`."""

    def __init__(self):
        self.pid = 4242
        self.aturat = False
        self._allibera = threading.Event()
        self.stdin = self

    def write(self, b):
        self._allibera.wait(5.0)     # com un pipe ple: el fil queda encallat
        return len(b)

    def close(self):
        pass

    def flush(self):
        pass

    def poll(self):
        return 0 if self.aturat else None

    @property
    def returncode(self):
        return 0 if self.aturat else None

    def atura(self):
        self.aturat = True
        self._allibera.set()


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QW.QApplication.instance() or QW.QApplication([])

    def setUp(self):
        p = patch.object(QW.QMessageBox, "information", lambda *a, **k: None)
        p.start()
        self.addCleanup(p.stop)

    def _arrenca(self, v):
        """Fa `play` (mateix motor fals que `_engega_des_de` farà servir)."""
        motor = _FakeMotor()
        self._motor = motor
        with patch.object(audio_out, "crea_motor", lambda *a, **k: motor), \
                patch.object(app_visor, "OPENCODE_DIR", tempfile.mkdtemp()):
            v.play_stop()
        return motor

    def tearDown(self):
        for v in _VISORS:
            try:
                v.rellotge.stop()
                v._atura_proc()
            except (RuntimeError, AttributeError):
                pass
        try:
            import _qt_neteja
        except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
            import os as _os
            _sys = sys
            _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
            import _qt_neteja
        ws, _VISORS[:] = _VISORS[:], []
        _qt_neteja.tanca_i_destrueix(*ws)


class TestCursorAmbLoop(_Base):
    def test_play_fora_del_loop_arrenca_a_loop_a(self):
        """EL BUG: cursor a 5 s, loop [2, 3] → el só va a 2 s; el cursor també."""
        v = _visor()
        v.loop_a, v.loop_b = 2.0, 3.0
        v.set_loop(True)
        v.ves_a(5.0)                       # cursor FORA del bucle
        self._arrenca(v)
        self.assertAlmostEqual(v.t0_pos, 2.0, places=6,
                               msg="el cursor ha d'anar on sona el só (loop_a)")
        self.assertAlmostEqual(v.pos, 2.0, places=6)
        self.assertAlmostEqual(float(v.timeline.get_position()), 2.0, places=6)

    def test_play_dins_del_loop_respecta_el_cursor(self):
        """Dins el bucle el só arrenca on és el cursor: no s'ha de moure."""
        v = _visor()
        v.loop_a, v.loop_b = 2.0, 3.0
        v.set_loop(True)
        v.ves_a(2.50)
        self._arrenca(v)
        self.assertAlmostEqual(v.t0_pos, 2.50, places=6)
        self.assertAlmostEqual(float(v.timeline.get_position()), 2.50, places=6)

    def test_play_sense_loop_respecta_el_cursor(self):
        v = _visor()
        v.ves_a(5.0)
        self._arrenca(v)
        self.assertAlmostEqual(v.t0_pos, 5.0, places=6)

    def test_loop_invalid_no_hi_ha_salt(self):
        """Un bucle degenerat (B <= A) no compta com a loop actiu."""
        v = _visor()
        v.loop_a, v.loop_b = 3.0, 3.0
        v.set_loop(True)
        self.assertFalse(v.loop_on, "un bucle B<=A no pot quedar actiu")
        v.ves_a(5.0)
        self._arrenca(v)
        self.assertAlmostEqual(v.t0_pos, 5.0, places=6)

    def test_seek_fora_del_loop_mentre_sona(self):
        """Sonant amb loop, un seek fora del bucle també ha d'alinear-se."""
        v = _visor()
        self._arrenca(v)                   # sona des del principi, sense loop
        v.loop_a, v.loop_b = 2.0, 3.0
        v.set_loop(True)                   # s'activa el bucle mentres sona
        v.ves_a(5.0)                       # seek FORA del bucle
        self.assertAlmostEqual(v.t0_pos, 2.0, places=6,
                               msg="el seek fora del bucle ha de saltar a loop_a")
        self.assertAlmostEqual(float(v.timeline.get_position()), 2.0, places=6)


class TestLoopActivatSonant(_Base):
    def test_activar_loop_sonant_alinea_cursor_i_so(self):
        """BUG (operador): donar `play` SENSE loop i ACTIVAR el loop mentre sona.

        El feeder llegeix `loop_on` en VIU i, si la posició de generació queda
        fora del bucle, hi salta (`pos = a`) → el só va a `loop_a`. Però
        `set_loop()` no tocava el cursor → el cursor seguia on era.
        """
        v = _visor()
        self._arrenca(v)                      # play sense loop (des del principi)
        self.assertTrue(v.sona)
        v.loop_a, v.loop_b = 2.0, 3.0
        v.set_loop(True)                      # ← el cas de l'operador
        self.assertAlmostEqual(v.t0_pos, 2.0, places=6,
                               msg="el cursor ha d'anar on el só (loop_a)")
        self.assertAlmostEqual(v.pos, 2.0, places=6)
        self.assertAlmostEqual(float(v.timeline.get_position()), 2.0, places=6)

    def test_activar_loop_amb_cursor_dins_no_mou(self):
        """Si el cursor ja és dins el bucle, el só arrenca allà: no es mou res."""
        v = _visor()
        self._arrenca(v)
        v.ves_a(2.5)                          # cursor dins el futur bucle
        v.loop_a, v.loop_b = 2.0, 3.0
        v.set_loop(True)
        self.assertAlmostEqual(v.t0_pos, 2.5, places=6)

    def test_activar_loop_parat_no_mou_el_cursor(self):
        """Amb el transport aturat, activar el loop no ha de moure el cursor."""
        v = _visor()
        v.ves_a(5.0)
        v.loop_a, v.loop_b = 2.0, 3.0
        v.set_loop(True)
        self.assertAlmostEqual(v.pos, 5.0, places=6)


def tearDownModule():
    try:
        import _qt_neteja
    except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()


if __name__ == "__main__":
    unittest.main()
