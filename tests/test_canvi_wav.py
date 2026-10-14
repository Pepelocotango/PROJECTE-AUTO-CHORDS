"""Canviar de WAV ha de reiniciar el tempo (troballa OC-6/415).

El BPM és del TEMA: si obres un WAV nou i el camp es queda amb el valor del
tema anterior, el nou surt analitzat amb el tempo vell (i la graella de
compassos, malament). `tria_wav()` ara el torna al valor per defecte (120.0) i
ho registra; l'usuari el pot detectar o posar a mà.
"""
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from unittest.mock import patch  # noqa: E402

import PyQt5.QtWidgets as QW  # noqa: E402
from PyQt5.QtWidgets import QFileDialog  # noqa: E402

from app import main as app_main  # noqa: E402

_VIVES = []


def _wav(segons=1):
    fd, ruta = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * segons)
    return ruta


def _finestra():
    f = app_main.Finestra()
    _VIVES.append(f)
    return f


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QW.QApplication.instance() or QW.QApplication([])

    def tearDown(self):
        try:
            import _qt_neteja
        except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
            import os as _os
            _sys = sys
            _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
            import _qt_neteja
        ws, _VIVES[:] = _VIVES[:], []
        _qt_neteja.tanca_i_destrueix(*ws)


class TestCanviWavReiniciaTempo(_Base):
    def _obre(self, f, ruta):
        with patch.object(QFileDialog, "getOpenFileName",
                          return_value=(ruta, "")):
            f.tria_wav()

    def test_bpm_reiniciat_en_carregar_un_wav_nou(self):
        f = _finestra()
        f.bpm.setText("140.0")
        self._obre(f, _wav())
        self.assertEqual(f.bpm.text(), "120.0",
                         "el WAV nou no ha d'heretar el BPM de l'anterior")
        self.assertIsNotNone(f.visor_ref, "s'hauria d'haver carregat el visor")

    def test_bpm_per_defecte_no_canvia(self):
        f = _finestra()
        self.assertEqual(f.bpm.text(), "120.0")
        self._obre(f, _wav())
        self.assertEqual(f.bpm.text(), "120.0")


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
