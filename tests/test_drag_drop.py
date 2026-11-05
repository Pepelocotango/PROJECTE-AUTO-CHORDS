"""Drag & drop d'àudio des del gestor de fitxers (Linux, Windows i macOS).

Cobreix:
- la lectura del `QMimeData` (URLs natives + fallback de text pla);
- que només s'accepten fitxers locals amb extensió d'àudio;
- que un drop sobre la finestra obri l'àudio (delegat fora de l'esdeveniment);
- que un drop sobre un fill que accepta text (QLineEdit) NO hi enganxa la
  ruta i obri l'àudio igualment.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["AUTO_CHORDS_TEST"] = "1"

import tempfile  # noqa: E402
import unittest  # noqa: E402
from unittest.mock import patch  # noqa: E402

from PyQt5.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl  # noqa: E402
from PyQt5.QtGui import QDragEnterEvent, QDropEvent  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from app import drag_drop  # noqa: E402
from app import main as app_main  # noqa: E402


def tearDownModule():
    import _qt_neteja
    _qt_neteja.processa_esborrats()


_APP = None


def _app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def _mime(*rutes):
    md = QMimeData()
    md.setUrls([QUrl.fromLocalFile(r) for r in rutes])
    return md


class TestRutes(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.wav = os.path.join(self.td, "canco.wav")
        self.mp3 = os.path.join(self.td, "altre.MP3")
        self.txt = os.path.join(self.td, "notes.txt")
        self.carpeta = os.path.join(self.td, "carpeta.wav")
        for ruta in (self.wav, self.mp3, self.txt):
            with open(ruta, "wb") as f:
                f.write(b"x")
        os.mkdir(self.carpeta)

    def test_urls_natives_i_filtre_d_audio(self):
        rutes = drag_drop.rutes_audio(
            _mime(self.wav, self.txt, self.carpeta, self.mp3, self.wav))
        self.assertEqual(rutes, [self.wav, self.mp3])

    def test_fallback_de_text_pla(self):
        md = QMimeData()
        md.setText(f"{self.wav}\n{self.txt}\n")
        self.assertEqual(drag_drop.rutes_audio(md), [self.wav])

    def test_text_amb_file_uri(self):
        md = QMimeData()
        md.setText(QUrl.fromLocalFile(self.mp3).toString())
        self.assertEqual(drag_drop.rutes_audio(md), [self.mp3])

    def test_sense_audio(self):
        md = _mime(self.txt, self.carpeta)
        self.assertEqual(drag_drop.rutes_audio(md), [])
        self.assertFalse(drag_drop.te_audio(md))

    def test_mime_buit(self):
        self.assertEqual(drag_drop.rutes(None), [])
        self.assertFalse(drag_drop.te_audio(None))


class TestDropGui(unittest.TestCase):
    def setUp(self):
        _app()
        self.td = tempfile.mkdtemp()
        self.wav = os.path.join(self.td, "canco.wav")
        with open(self.wav, "wb") as f:
            f.write(b"x")
        self.txt = os.path.join(self.td, "notes.txt")
        with open(self.txt, "wb") as f:
            f.write(b"x")
        self.w = app_main.Finestra()

    def tearDown(self):
        import _qt_neteja
        _qt_neteja.tanca_i_destrueix(self.w)

    def test_finestra_accepta_drops_i_els_fills_no(self):
        self.assertTrue(self.w.acceptDrops())
        # Si un camp de text acceptara drops, s'hi enganxaria la ruta.
        self.assertFalse(self.w.bpm.acceptDrops())
        self.assertFalse(self.w.log.acceptDrops())

    def test_enter_accepta_i_avisa(self):
        md = _mime(self.wav)          # viu mentre viu l'esdeveniment
        ev = QDragEnterEvent(QPoint(5, 5), Qt.CopyAction, md,
                             Qt.LeftButton, Qt.NoModifier)
        self.w.dragEnterEvent(ev)
        self.assertTrue(ev.isAccepted())
        self.assertIn("àudio", self.w.statusBar().currentMessage())

    def test_enter_ignora_no_audio(self):
        md = _mime(self.txt)
        ev = QDragEnterEvent(QPoint(5, 5), Qt.CopyAction, md,
                             Qt.LeftButton, Qt.NoModifier)
        self.w.dragEnterEvent(ev)
        self.assertFalse(ev.isAccepted())

    def test_drop_obre_l_audio_fora_de_l_esdeveniment(self):
        md = _mime(self.wav)
        ev = QDropEvent(QPointF(5, 5), Qt.CopyAction, md,
                        Qt.LeftButton, Qt.NoModifier)
        with patch.object(self.w, "_obri_des_de_wav") as obri:
            self.w.dropEvent(ev)
            self.assertTrue(ev.isAccepted())
            obri.assert_not_called()          # no obre dins del dropEvent
            QApplication.processEvents()
            obri.assert_called_once_with(self.wav)

    def test_drop_sobre_camp_de_text_no_hi_enganxa_la_ruta(self):
        self.w.bpm.setText("120.000")
        md = _mime(self.wav)
        ev = QDropEvent(QPointF(5, 5), Qt.CopyAction, md,
                        Qt.LeftButton, Qt.NoModifier)
        with patch.object(self.w, "_obri_des_de_wav") as obri:
            gestionat = self.w.eventFilter(self.w.bpm, ev)
            self.assertTrue(gestionat)
            self.assertTrue(ev.isAccepted())
            self.assertEqual(self.w.bpm.text(), "120.000")
            QApplication.processEvents()
            obri.assert_called_once_with(self.wav)

    def test_drop_no_audio_sobre_camp_de_text_no_es_gestiona(self):
        self.w.bpm.setText("120.000")
        md = _mime(self.txt)
        ev = QDropEvent(QPointF(5, 5), Qt.CopyAction, md,
                        Qt.LeftButton, Qt.NoModifier)
        with patch.object(self.w, "_obri_des_de_wav") as obri:
            self.assertFalse(self.w.eventFilter(self.w.bpm, ev))
            QApplication.processEvents()
            obri.assert_not_called()


if __name__ == "__main__":
    unittest.main()
