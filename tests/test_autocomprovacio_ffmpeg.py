"""A9: l'autocomprovació d'arrencada ha d'incloure ffmpeg.

L'app s'autocomprova `ACORDS_PY` i els `VAMP_DIRS`, però **no** comprovava
`ffmpeg`: és imprescindible per obrir qualsevol format que no sigui WAV PCM
16 bits (mp3/flac/m4a/ogg…). Sense ell, l'obertura fallava tard i amb un error
críptic. Ara s'avisa a l'arrencada i, si no hi és, el diàleg d'obertura només
ofereix WAV (oferir la resta seria enganyós).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from unittest.mock import patch  # noqa: E402

import PyQt5.QtWidgets as QW  # noqa: E402

from app import main as app_main  # noqa: E402


class TestAutocomprovacioFfmpeg(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QW.QApplication.instance() or QW.QApplication([])

    def test_avisa_si_falta_ffmpeg(self):
        with patch.object(app_main.ffmpeg, "disponible", return_value=False):
            w = app_main.Finestra()
        self.assertIn("ffmpeg", w.log.toPlainText(),
                      "hauria d'avisar que falta ffmpeg")
        w.close()

    def test_no_avisa_si_hi_es(self):
        with patch.object(app_main.ffmpeg, "disponible", return_value=True):
            w = app_main.Finestra()
        self.assertNotIn("no trobo ffmpeg", w.log.toPlainText())
        w.close()

    def test_l_app_arrenca_igual_sense_ffmpeg(self):
        """No ha de petar: només s'avisa (l'app funciona amb WAV)."""
        with patch.object(app_main.ffmpeg, "disponible", return_value=False):
            w = app_main.Finestra()
        self.assertIsNotNone(w.menuBar())
        w.close()

    def test_filtre_amb_ffmpeg_ofereix_tots_els_formats(self):
        with patch.object(app_main.ffmpeg, "disponible", return_value=True):
            w = app_main.Finestra()
            f = w._filtre_audio()
        self.assertIn("mp3", f)
        w.close()

    def test_filtre_sense_ffmpeg_nomes_wav(self):
        with patch.object(app_main.ffmpeg, "disponible", return_value=False):
            w = app_main.Finestra()
            f = w._filtre_audio()
        self.assertIn("WAV", f)
        self.assertNotIn("mp3", f, "sense ffmpeg no pot oferir mp3")
        w.close()


if __name__ == "__main__":
    unittest.main()
