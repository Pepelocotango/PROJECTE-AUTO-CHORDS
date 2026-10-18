"""El visor avisa (no bloquejant) si el fitxer és MOLT llarg.

El visor carrega el PCM sencer a memòria (`raw` + la còpia `mono`) ≈ 3× la mida
del fitxer (prova real: 1 h ≈ 2 GB de pic). A partir de `visor.LLARG_MIN_S`
s'ha de registrar un avís al panell del log — sense bloquejar.
"""
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene dels tests: l'import té efecte (esborra els temporals en plegar)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from app import visor  # noqa: E402


def _wav(segons=2):
    fd, ruta = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * segons)
    return ruta


class TestFitxerLlarg(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def test_avisa_si_supera_el_llindar(self):
        orig = visor.LLARG_MIN_S
        visor.LLARG_MIN_S = 1          # 2 s de WAV > 1 s -> ha d'avisar
        try:
            v = visor.Visor(_wav(2), None, None, 120.0, 4, True)
        finally:
            visor.LLARG_MIN_S = orig
        # `registre` és el QTextEdit del panell del log (l'avís ha de ser-hi).
        txt = v.registre.toPlainText() if hasattr(v, "registre") else ""
        self.assertIn("MOLT LLARG", txt, f"no s'ha avisat: {txt!r}")
        v.close()

    def test_no_avisa_si_es_curt(self):
        v = visor.Visor(_wav(2), None, None, 120.0, 4, True)   # llindar real (45 min)
        txt = v.registre.toPlainText() if hasattr(v, "registre") else ""
        self.assertNotIn("MOLT LLARG", txt, "no hauria d'avisar per un fitxer curt")
        v.close()


def tearDownModule():
    try:
        import _qt_neteja
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()


if __name__ == "__main__":
    unittest.main()
