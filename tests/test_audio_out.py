"""Tests del motor d'àudio (`app/audio_out.py`, `app/plataforma.py`).

El motor **natiu** (sounddevice) només s'activa a macOS/Windows; a Linux
(l'entorn del CI i de l'ordinador de treball) es prova l'abstracció i el motor
de procés (`MotorProc`, paplay/aplay).
"""
import os
import sys
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import audio_out, plataforma  # noqa: E402


class TestSeleccioMotor(unittest.TestCase):
    def test_usa_audio_natiu_segons_so(self):
        """Natiu a mac/win; procés extern a Linux."""
        fmt = plataforma.ES_WINDOWS or plataforma.ES_MAC
        self.assertEqual(plataforma.usa_audio_natiu(), bool(fmt))

    def test_candidats_reproductor(self):
        if plataforma.ES_WINDOWS or plataforma.ES_MAC:
            self.assertEqual(plataforma.candidats_reproductor(), ())
        else:
            self.assertEqual(plataforma.candidats_reproductor(),
                             ("paplay", "aplay"))

    def test_missatge_sense_audio_es_segons_so(self):
        m = plataforma.missatge_sense_audio()
        self.assertIn("funciona igual", m)
        if plataforma.ES_WINDOWS or plataforma.ES_MAC:
            self.assertNotIn("PipeWire", m)
        else:
            self.assertIn("PipeWire", m)


class TestMotorProc(unittest.TestCase):
    """El motor de procés (Linux) ha de tenir la interfície del subprocess."""

    def test_cicle_de_vida(self):
        with open(os.devnull, "wb") as ferr:
            motor = audio_out.crea_motor("cat", [], 44100, ferr)
            self.assertIsInstance(motor, audio_out.MotorProc)
            for metode in ("poll", "atura"):
                self.assertTrue(callable(getattr(motor, metode)))
            motor.stdin.write(b"\x00\x00" * 64)   # PCM mono 16 bits
            self.assertIsNone(motor.poll())        # encara viu
            motor.stdin.close()
            motor.atura()
        self.assertIsNotNone(motor.poll())         # ja ha acabat

    def test_motorstream_no_s_usa_a_linux(self):
        # A Linux mai no es tria el motor natiu; la classe hi és igualment.
        self.assertTrue(callable(getattr(audio_out, "MotorStream", None)))


class _FakeStream:
    """Stream fals per provar el teardown sense PortAudio."""

    def __init__(self):
        self.stops = 0
        self.closes = 0

    def stop(self):
        self.stops += 1

    def close(self):
        self.closes += 1


class TestMotorStreamTeardown(unittest.TestCase):
    """El teardown natiu ha de ser IDEMPOTENT (causa del crash a macOS:
    `Pa_CloseStream` cridat 2 cops → EXC_BAD_ACCESS)."""

    def _motor(self):
        m = audio_out.MotorStream.__new__(audio_out.MotorStream)
        m._lock = threading.Lock()
        m._tancat = False
        m._fi = False
        m._err = False
        m._rc = None
        m.sr = 44100
        m._device = None
        m.stream = _FakeStream()
        return m

    def test_tanca_idempotent(self):
        m = self._motor()
        st = m.stream
        m.close()          # drena (stop + close)
        m.atura()          # 2n tancament -> NO ha de tocar el stream
        m.close()          # 3r -> tampoc
        self.assertEqual(st.stops, 1)
        self.assertEqual(st.closes, 1)
        self.assertIsNone(m.stream)
        self.assertTrue(m._fi)
        self.assertEqual(m.poll(), 0)

    def test_atura_no_drena(self):
        m = self._motor()
        st = m.stream
        m.atura()
        self.assertEqual(st.stops, 0)   # atura talla, no drena
        self.assertEqual(st.closes, 1)
        self.assertEqual(m.poll(), 0)


if __name__ == "__main__":
    unittest.main()
