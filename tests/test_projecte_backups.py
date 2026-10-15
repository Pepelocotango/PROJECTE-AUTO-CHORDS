"""Projectes — backups versionats + sessió/recuperació (fase 3).

- `Projecte.fes_backup()`: còpia dins `backup/<data-hora>/` (document + CSVs) i
  rotació perquè no creixin sense control.
- Sessió: marcador `sessio.json` (s'escriu amb un projecte obert i es neteja al
  tancament net); a l'arrencada, `_sessio_pendent()` retorna el projecte a
  oferir si l'app va caure.
"""
import json
import os
import sys
import tempfile
import unittest
import wave
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtWidgets import QFileDialog  # noqa: E402

from app import config  # noqa: E402
from app import main as app_main  # noqa: E402
from app import projecte  # noqa: E402

_VIVES = []


def _wav(dur=2.0):
    d = tempfile.mkdtemp()
    ruta = os.path.join(d, "tema.wav")
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * int(44100 * dur))
    return ruta


def _finestra():
    f = app_main.Finestra()
    _VIVES.append(f)
    return f


def _obre_wav(f, wav, nom="Projecte1"):
    acproj = os.path.join(os.path.dirname(wav), nom + ".acproj")
    with patch.object(QFileDialog, "getOpenFileName", return_value=(wav, "")), \
            patch.object(QFileDialog, "getSaveFileName",
                         return_value=(acproj, "")):
        f.tria_wav()
    return f.projecte


# ── Backups (model) ──────────────────────────────────────────────────────────
class TestBackups(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()

    def _projecte(self):
        wav = _wav()
        return projecte.Projecte.crea(os.path.join(self.td, "P"), wav, bpm=120.0)

    def test_fes_backup_crea_document_i_csvs(self):
        p = self._projecte()
        with open(p.ruta_csv_acords(), "w", encoding="utf-8") as f:
            f.write("0.0,C\n1.0,Am\n")
        dest = p.fes_backup()
        self.assertTrue(os.path.isfile(
            os.path.join(dest, os.path.basename(p.ruta_acproj))))
        self.assertTrue(os.path.isfile(os.path.join(dest, "acords.csv")))
        self.assertEqual(len(p.backups()), 1)

    def test_backup_captura_l_estat_viu(self):
        p = self._projecte()
        p.dades["tempo"]["bpm"] = 173.0
        dest = p.fes_backup()
        with open(os.path.join(dest, os.path.basename(p.ruta_acproj)),
                  encoding="utf-8") as f:
            b = json.load(f)
        self.assertEqual(b["tempo"]["bpm"], 173.0)

    def test_rota_backups(self):
        p = self._projecte()
        for _ in range(5):
            p.fes_backup(max_backups=3)
        self.assertEqual(len(p.backups()), 3)

    def test_rota_backups_zero_no_rota(self):
        p = self._projecte()
        for _ in range(3):
            p.fes_backup(max_backups=0)          # 0 = no esborrar res
        self.assertEqual(len(p.backups()), 3)

    def test_backups_sense_carpeta(self):
        p = self._projecte()
        self.assertEqual(p.backups(), [])        # encara no s'ha fet cap backup

    def test_molts_backups_dins_el_mateix_segon(self):
        """La rotació ha de quedar-se els MÉS NOUS, ni que comparteixin segon."""
        p = self._projecte()
        creats = [p.fes_backup(max_backups=10) for _ in range(15)]
        queden = p.backups()
        self.assertEqual(len(queden), 10)
        # noms ÚNICS (no es reutilitza cap nom esborrat)
        noms = [os.path.basename(b) for b in queden]
        self.assertEqual(len(set(noms)), len(noms))
        # els 10 més NOUS (els 10 darrers creats) són els que queden
        esperats = {os.path.abspath(c) for c in creats[-10:]}
        self.assertEqual({os.path.abspath(b) for b in queden}, esperats)


# ── Sessió + autosave (GUI) ──────────────────────────────────────────────────
class _BaseGUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = app_main.QApplication.instance() or app_main.QApplication([])

    def setUp(self):
        self.td = tempfile.mkdtemp()
        self._p = patch.object(config, "DADES_DIR", self.td)
        self._p.start()

    def tearDown(self):
        self._p.stop()
        try:
            import _qt_neteja
        except ImportError:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import _qt_neteja
        ws, _VIVES[:] = _VIVES[:], []
        for w in ws:
            w.dirty = False
        _qt_neteja.tanca_i_destrueix(*ws)


class TestSessio(_BaseGUI):
    def test_marca_i_sessio_pendent(self):
        f = _finestra()
        p = _obre_wav(f, _wav())
        self.assertTrue(os.path.isfile(f._sessio_path()),
                        "en obrir un projecte s'ha de marcar la sessió")
        self.assertEqual(f._sessio_pendent(), os.path.abspath(p.ruta_acproj))
        self.assertFalse(os.path.isfile(f._sessio_path()),
                         "el marcador s'ha de netejar en llegir-lo")

    def test_sessio_pendent_sense_marcador(self):
        f = _finestra()
        self.assertIsNone(f._sessio_pendent())

    def test_sessio_pendent_amb_acproj_inexistent(self):
        f = _finestra()
        with open(f._sessio_path(), "w", encoding="utf-8") as fh:
            json.dump({"acproj": os.path.join(self.td, "no-existeix.acproj")}, fh)
        self.assertIsNone(f._sessio_pendent())
        self.assertFalse(os.path.isfile(f._sessio_path()))

    def test_close_net_neteja_la_sessio(self):
        f = _finestra()
        _obre_wav(f, _wav())
        self.assertTrue(os.path.isfile(f._sessio_path()))
        f.dirty = False
        f.close()
        self.assertFalse(os.path.isfile(f._sessio_path()))


class TestAutosave(_BaseGUI):
    def test_autosave_nomes_amb_canvis(self):
        f = _finestra()
        p = _obre_wav(f, _wav())
        f._fes_autosave()                 # net -> no ha de fer res
        self.assertEqual(p.backups(), [])
        f._marca_dirty()
        f._fes_autosave()
        self.assertEqual(len(p.backups()), 1)

    def test_autosave_captura_el_tempo_dels_widgets(self):
        f = _finestra()
        p = _obre_wav(f, _wav())
        f.bpm.setText("155.0")
        f._marca_dirty()
        f._fes_autosave()
        dest = p.backups()[0]
        with open(os.path.join(dest, os.path.basename(p.ruta_acproj)),
                  encoding="utf-8") as fh:
            b = json.load(fh)
        self.assertEqual(b["tempo"]["bpm"], 155.0)


def tearDownModule():
    try:
        import _qt_neteja
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()


if __name__ == "__main__":
    unittest.main()
