"""Tests: AVÍS VISIBLE quan el motor d'àudio mor.

Cobreix l'arreglament de `docs/AUDITORIA_PRODUCCIO.md` 1.6/4.3 i el «Pendent» de
`docs/PLAY.md`: que un error del reproductor NO quedi només al log, sinó que
l'usuari en rebi un avís (senyal `infoMissatge` → caixa d'informació).
"""
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from app import visor  # noqa: E402


def _wav_silenci(segons=1):
    fd, ruta = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * segons)
    return ruta


class _FakeProcError:
    returncode = 1

    def poll(self):
        return 1

    def atura(self):
        pass


class TestAvisAudio(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def _visor(self):
        return visor.Visor(_wav_silenci(), None, None, 120.0, 4, True)

    def test_tiquet_avisa_si_el_motor_mor(self):
        v = self._visor()
        v.proc = _FakeProcError()
        v.sona = True
        v.t0_pos = 0.0
        v.t0_mono = 0.0
        missatges = []
        v.infoMissatge.connect(missatges.append)
        v._tiquet()
        self.assertTrue(any("motor d'àudio" in m for m in missatges),
                        f"no s'ha emès l'avís visible: {missatges}")
        self.assertFalse(v.sona, "l'error hauria d'haver aturat la reproducció")

    def test_avis_nomes_un_cop_per_reproduccio(self):
        v = self._visor()
        v.proc = _FakeProcError()
        v.sona = True
        v.t0_pos = 0.0
        v.t0_mono = 0.0
        n = []
        v.infoMissatge.connect(n.append)
        v._tiquet()                     # avisa i atura
        v.proc = _FakeProcError()       # "torna a sonar" sense passar per play
        v.sona = True
        v.t0_mono = 0.0
        v._tiquet()                     # NO ha de tornar a avisar
        self.assertEqual(len(n), 1)


if __name__ == "__main__":
    unittest.main()
