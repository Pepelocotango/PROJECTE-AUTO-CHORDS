"""Tancar l'app MENTRE sona → neteja ordenada (`closeEvent`), sense petar.

Cas real (Claude, checklist pre-publicació punt 2): l'usuari tanca la finestra
mentre el visor està reproduint. Sense `closeEvent`, Qt destrueixia la Finestra
amb el **fil d'alimentació viu** escrivint PCM al reproductor → destrucció en
ordre arbitrari = risc d'`access violation` (el crash intermitent que va costar
de trobar als tests).

Aquí es reprodueix el **pitjor cas** de manera determinista: s'injecta un motor
d'àudio FALS (mateixa interfície que `audio_out.crea_motor`: `stdin`/`poll`/
`returncode`/`pid`/`atura`) el `write` del qual **es bloqueja** fins que algú
l'atura — és a dir, el fil queda viu «sonant» fins que el `closeEvent` hi actua.
Així el test no depèn de maquinari d'àudio ni d'orelles.

Cobreix el `closeEvent` (que fins ara no tenia cap test): espera l'export, atura
el rellotge i el reproductor del visor, tanca el pont MCP i la caixa d'avís no
modal. El **motor natiu real** (PortAudio a mac/win, canvi d'auriculars en calent)
segueix sent prova manual.
"""
import os
import sys
import tempfile
import threading
import time
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene dels tests: l'import té efecte (esborra els temporals en plegar)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from unittest.mock import patch  # noqa: E402

import PyQt5.QtWidgets as QW  # noqa: E402

from app import audio_out  # noqa: E402
from app import main as app_main  # noqa: E402
from app import visor as app_visor  # noqa: E402

_VIVES = []     # finestres creades pel test: es tanquen al tearDown


def _finestra(segons=20):
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "t.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * segons)
    f = app_main.Finestra()
    f.wav_edit.setText(wav)
    f._carrega_visor(wav)
    _VIVES.append(f)
    return f


def _fil_alimenta(v):
    """El fil d'alimentació de `v` encara viu (o `None`)."""
    for t in threading.enumerate():
        obj = getattr(t, "_target", None)
        if obj is None:
            continue
        if getattr(obj, "__self__", None) is v and \
                getattr(getattr(obj, "__func__", None), "__name__", "") == "_alimenta":
            return t
    return None


class _FakeMotor:
    """Motor d'àudio fals, amb la interfície d'`audio_out.crea_motor`."""

    def __init__(self):
        self.pid = 4242
        self.aturat = False
        self.escrit = 0
        self._allibera = threading.Event()
        self.stdin = self          # `proc.stdin.write(tros)` → write()

    def write(self, b):
        self.escrit += len(b)
        # Com un pipe PLE: el fil queda encallat aquí fins que `atura()` el
        # desbloqueja → és el que fa que «estigui sonant» de debò en tancar.
        self._allibera.wait(5.0)
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
        self._allibera.set()       # desbloqueja el fil d'alimentació


class _FakePont:
    def __init__(self):
        self.tancat = False

    def tanca(self):
        self.tancat = True


class _FakeFeina:
    def __init__(self):
        self.esperat = None

    def isRunning(self):
        return True

    def wait(self, ms):
        self.esperat = ms
        return True


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QW.QApplication.instance() or QW.QApplication([])

    def setUp(self):
        # Cap test no ha d'ensenyar un QMessageBox de veritat.
        p = patch.object(QW.QMessageBox, "show", lambda self: None)
        p.start()
        self.addCleanup(p.stop)

    def tearDown(self):
        try:
            import _qt_neteja
        except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
            import os as _os
            import sys as _sys
            _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
            import _qt_neteja
        ws = _VIVES[:]
        _VIVES.clear()
        _qt_neteja.tanca_i_destrueix(*ws)


class TestTancarSonant(_Base):
    def test_tancar_mentre_sona_atura_el_motor_i_no_peta(self):
        f = _finestra()
        v = f.visor_ref
        v.player, v.player_args = "paplay", []   # crea_motor queda substituït
        f.feina_export = _FakeFeina()
        f._mcp_pont = _FakePont()
        f.mcp_actiu = True
        f.avisa("T", "avís viu")                 # caixa no modal oberta
        tmp = tempfile.mkdtemp()
        motor = _FakeMotor()

        with patch.object(audio_out, "crea_motor", lambda *a, **k: motor), \
                patch.object(app_visor, "OPENCODE_DIR", tmp):
            v.play_stop()                        # ARRENCA la reproducció
            self.assertTrue(v.sona, "hauria d'estar sonant")
            self.assertIs(v.proc, motor)
            fil = _fil_alimenta(v)
            self.assertIsNotNone(fil, "el fil d'alimentació hauria d'estar viu")
            f.close()                            # <<< EL CAS: tancar SONANT

        # El closeEvent ho ha netejat tot, en ordre:
        self.assertTrue(f.feina_export.esperat == 10000,
                        "s'hauria d'haver esperat l'export (10000 ms)")
        self.assertTrue(motor.aturat, "el motor d'àudio s'hauria d'haver aturat")
        self.assertIsNone(v.proc, "el visor no pot quedar amb el proc viu")
        self.assertFalse(v.rellotge.isActive(), "el rellotge s'hauria d'haver aturat")
        self.assertTrue(f._mcp_pont.tancat, "el pont MCP s'hauria d'haver tancat")
        self.assertIsNone(getattr(f, "_avis_box", None),
                          "la caixa d'avís no modal hauria d'estar tancada")
        # El fil d'alimentació ACABA (no queda res viu escrivint PCM).
        for _ in range(80):
            if not fil.is_alive():
                break
            time.sleep(0.05)
        self.assertFalse(fil.is_alive(),
                         "el fil d'alimentació no pot quedar viu")
        self.assertEqual(motor.escrit, 65536,
                         "només hi cap un tros (32768 mostres) abans d'aturar-lo")

    def test_tancar_sense_sonar_tambe_es_net(self):
        """Camí normal: tancar amb el visor aturat no ha de petar ni fer res."""
        f = _finestra()
        v = f.visor_ref
        f.close()
        self.assertIsNone(v.proc)
        self.assertFalse(v.rellotge.isActive())


def tearDownModule():
    # Neteja ORDENADA dels objectes Qt del mòdul (evita destrucció pel GC en un
    # test posterior -> access violation intermitent). Vegeu tests/_qt_neteja.py.
    try:
        import _qt_neteja
    except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
        import os
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()


if __name__ == "__main__":
    unittest.main()
