import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from app import beats
from app import limits


class TestBeatsGuardrails(unittest.TestCase):
    """Guardrails del flux principal: deteccio de beats."""

    def test_bpm_de_beats_retorna_none_si_fora_banda(self):
        # beats espaiats 10s -> BPM ~6, fora de banda
        beats = [0.0, 10.0, 20.0, 30.0]
        self.assertIsNone(beats._bpm_de_beats(beats) if False else None)
        # crida directa a la funcio privada
        self.assertIsNone(__import__("app.beats", fromlist=["_bpm_de_beats"])._bpm_de_beats(beats))

    def test_bpm_de_beats_retorna_bpm_valid(self):
        beats = [0.0, 0.5, 1.0, 1.5, 2.0]
        bpm = beats._bpm_de_beats(beats) if False else None
        bpm = __import__("app.beats", fromlist=["_bpm_de_beats"])._bpm_de_beats(beats)
        self.assertIsNotNone(bpm)
        self.assertTrue(limits.BPM_MIN <= bpm <= limits.BPM_MAX)

    def test_bpm_de_beats_none_si_menys_de_2(self):
        self.assertIsNone(__import__("app.beats", fromlist=["_bpm_de_beats"])._bpm_de_beats([1.0]))

    def test_detecta_motor_desconegut(self):
        with self.assertRaises(ValueError):
            beats.detecta("x.wav", motor="foo")


if __name__ == "__main__":
    unittest.main()
