import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from app import pipeline


class TestPipelineGuardrails(unittest.TestCase):
    """Guardrails del flux principal: pipeline.wav_info."""

    def test_wav_info_fitxer_inexistent(self):
        with self.assertRaises(ValueError):
            pipeline.wav_info("no_existeix.wav")

    def test_wav_info_no_wav(self):
        fd, p = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        with open(p, "w") as f:
            f.write("no es wav")
        try:
            with self.assertRaises(ValueError):
                pipeline.wav_info(p)
        finally:
            os.remove(p)


if __name__ == "__main__":
    unittest.main()
