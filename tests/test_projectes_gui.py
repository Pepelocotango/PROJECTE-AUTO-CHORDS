"""Projectes — cicle de vida a la GUI (fase 2): obrir WAV → projecte
autocontingut, desar / desar com / desar una còpia / reverteix, recents,
«brut» i títol.
"""
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
    d = tempfile.mkdtemp()          # dir únic per a cada WAV (evita xocs)
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
    """Simula «Obre WAV» triant WAV + ubicació del projecte."""
    acproj = os.path.join(os.path.dirname(wav), nom + ".acproj")
    with patch.object(QFileDialog, "getOpenFileName", return_value=(wav, "")), \
            patch.object(QFileDialog, "getSaveFileName",
                         return_value=(acproj, "")):
        f.tria_wav()
    return f.projecte


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = app_main.QApplication.instance() or app_main.QApplication([])

    def setUp(self):
        # Aïlla els recents (no escriure al DADES_DIR real).
        self.td = tempfile.mkdtemp()
        self._patches = [patch.object(config, "DADES_DIR", self.td)]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        try:
            import _qt_neteja
        except ImportError:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import _qt_neteja
        ws, _VIVES[:] = _VIVES[:], []
        for w in ws:
            w.dirty = False          # no volem el prompt de tancament als tests
        _qt_neteja.tanca_i_destrueix(*ws)


class TestObreWavCreaProjecte(_Base):
    def test_projecte_autocontingut(self):
        f = _finestra()
        wav = _wav()
        p = _obre_wav(f, wav)
        self.assertIsNotNone(p, "s'hauria d'haver creat un projecte")
        # carpeta = <dir del wav>/Projecte1
        self.assertEqual(p.carpeta, os.path.join(os.path.dirname(wav), "Projecte1"))
        self.assertTrue(os.path.isfile(p.ruta_audio()), "àudio copiat a dins")
        self.assertEqual(f.sortida, p.carpeta)
        self.assertEqual(f.visor_ref._carpeta_acords(), p.carpeta,
                         "el visor ha de desar els CSV al PROJECTE, no dins audio/")
        self.assertIsNotNone(f.visor_ref, "s'hauria d'haver carregat el visor")
        self.assertIn("Projecte1", f.windowTitle())
        self.assertFalse(f.dirty)

    def test_esborra_original_i_el_projecte_obre(self):
        f = _finestra()
        wav = _wav()
        p = _obre_wav(f, wav)
        os.remove(wav)                        # l'original ja no hi és
        f2 = _finestra()
        f2._obre_ruta_projecte(p.ruta_acproj)
        self.assertIsNotNone(f2.projecte)
        self.assertTrue(f2.projecte.audio_present())


    def test_compas_complet_preservat(self):
        """El compàs «6/8» (amb denominador) ha de sobreviure desar/reobrir."""
        f = _finestra()
        wav = _wav()
        f.bpb.setText("6/8")
        acproj = os.path.join(os.path.dirname(wav), "C.acproj")
        with patch.object(QFileDialog, "getOpenFileName",
                          return_value=(wav, "")), \
                patch.object(QFileDialog, "getSaveFileName",
                             return_value=(acproj, "")):
            f.tria_wav()
        self.assertEqual(f.bpb.text(), "6/8")
        p = f.projecte
        f._marca_dirty()
        f._desa_projecte()
        f2 = _finestra()
        f2._obre_ruta_projecte(p.ruta_acproj)
        self.assertEqual(f2.bpb.text(), "6/8")


class TestDesa(_Base):
    def test_desa_escriu_el_document(self):
        f = _finestra()
        p = _obre_wav(f, _wav())
        f.bpm.setText("133.0")
        f._marca_dirty()
        self.assertTrue(f.dirty)
        f._desa_projecte()
        self.assertFalse(f.dirty)
        p2 = projecte.Projecte.obre(p.ruta_acproj)
        self.assertEqual(p2.dades["tempo"]["bpm"], 133.0)

    def test_desa_una_copia_no_canvia_el_projecte(self):
        f = _finestra()
        p = _obre_wav(f, _wav())
        desti = os.path.join(self.td, "COPIA.acproj")
        with patch.object(QFileDialog, "getSaveFileName",
                          return_value=(desti, "")):
            f._desa_copia()
        self.assertEqual(f.projecte.carpeta, p.carpeta,
                         "una còpia no ha de canviar el projecte actiu")
        self.assertTrue(os.path.isfile(
            os.path.join(self.td, "COPIA", "COPIA.acproj")))

    def test_desa_com_canvia_el_projecte(self):
        f = _finestra()
        p = _obre_wav(f, _wav())
        desti = os.path.join(self.td, "NOU_NOM.acproj")
        with patch.object(QFileDialog, "getSaveFileName",
                          return_value=(desti, "")):
            f._desa_projecte_com()
        self.assertEqual(f.projecte.carpeta, os.path.join(self.td, "NOU_NOM"))
        self.assertNotEqual(f.projecte.carpeta, p.carpeta)
        self.assertTrue(os.path.isfile(f.projecte.ruta_audio()),
                        "la còpia també ha de ser autocontinguda")

    def test_desa_com_al_mateix_lloc_es_desa_normal(self):
        f = _finestra()
        p = _obre_wav(f, _wav())
        f.bpm.setText("111.0")
        f._marca_dirty()
        with patch.object(QFileDialog, "getSaveFileName",
                          return_value=(os.path.join(
                              os.path.dirname(p.carpeta),
                              p.nom + projecte.EXT), "")):
            f._desa_projecte_com()
        self.assertEqual(f.projecte.carpeta, p.carpeta)
        self.assertEqual(projecte.Projecte.obre(p.ruta_acproj)
                         .dades["tempo"]["bpm"], 111.0)
        self.assertFalse(f.dirty)

    def test_reverteix(self):
        f = _finestra()
        _obre_wav(f, _wav())
        f.bpm.setText("99.0")
        f._desa_projecte()
        f.bpm.setText("150.0")
        f._marca_dirty()
        with patch.object(f, "_confirma_descartar", return_value=True):
            f._reverteix()
        self.assertEqual(f.bpm.text(), "99.0")
        self.assertFalse(f.dirty)


class TestDirtyITitol(_Base):
    def test_titol_amb_estrella(self):
        f = _finestra()
        _obre_wav(f, _wav())
        self.assertNotIn("*", f.windowTitle())
        f._marca_dirty()
        self.assertTrue(f.windowTitle().endswith("*"))

    def test_pot_descartar(self):
        f = _finestra()
        f.dirty = False
        self.assertTrue(f._pot_descartar())
        f.dirty = True
        with patch.object(f, "_confirma_descartar", return_value=False):
            self.assertFalse(f._pot_descartar())

    def test_close_amb_canvis_ignora(self):
        f = _finestra()
        f.dirty = True

        class _Ev:
            def __init__(self):
                self._ignorat = False
            def ignore(self):
                self._ignorat = True
            def accept(self):
                pass
        ev = _Ev()
        with patch.object(f, "_pot_descartar", return_value=False):
            f.closeEvent(ev)
        self.assertTrue(ev._ignorat, "amb canvis sense desar no s'ha de tancar")


class TestRecents(_Base):
    def test_recents_guarda_i_llista(self):
        f = _finestra()
        p = _obre_wav(f, _wav())
        self.assertIn(os.path.abspath(p.ruta_acproj), f.recents)
        self.assertTrue(os.path.isfile(f._recents_path()),
                        "els recents s'han de persistir")


class TestObrirProjecteHabilitaExport(_Base):
    def test_obrir_projecte_amb_model_activa_les_exportacions(self):
        """Obrir un projecte amb model ha de deixar disponibles les exportacions.

        Bug: «Exporta WAV's»/«Exporta partitura» només s'activaven al final
        d'una ANÀLISI → obrir un projecte els deixava apagats i no es podia
        exportar sense tornar a analitzar (cosa que descarta les edicions).
        """
        wav = _wav()
        p = projecte.Projecte.crea(os.path.join(os.path.dirname(wav), "P"),
                                   wav, bpm=120.0)
        with open(p.ruta_csv_acords(), "w", encoding="utf-8") as fh:
            fh.write("0.0,2.0,C\n2.0,4.0,G\n")
        f = _finestra()
        f.avisa = lambda *a, **k: None
        self.assertFalse(f.b_export.isEnabled(), "abans d'obrir, apagat")
        f._activa_projecte(projecte.Projecte.obre(p.ruta_acproj))
        self.assertTrue(f.b_export.isEnabled(),
                        "amb projecte obert l'export ha d'estar activa")
        self.assertTrue(f.b_export_part.isEnabled())

    def test_obrir_projecte_no_deixa_copia_dins_audio(self):
        """El visor desa a la carpeta del PROJECTE, mai dins `<projecte>/audio/`.

        Bug: el constructor del visor no sabia la carpeta de sortida i, quan la
        normalització (regla d'or #4) canviava el model, desava una còpia a la
        carpeta derivada del WAV (`audio/AUTOCHORDS_…/`).
        """
        wav = _wav()
        p = projecte.Projecte.crea(os.path.join(os.path.dirname(wav), "P"),
                                   wav, bpm=120.0)
        with open(p.ruta_csv_acords(), "w", encoding="utf-8") as fh:
            fh.write("1.0,5.0,C\n")          # 1r acord NO a 0 → força normalització
        f = _finestra()
        f.avisa = lambda *a, **k: None
        f._activa_projecte(projecte.Projecte.obre(p.ruta_acproj))
        audio = os.path.join(p.carpeta, "audio")
        self.assertEqual(sorted(os.listdir(audio)),
                         [os.path.basename(p.ruta_audio())],
                         "audio/ només ha de contenir l'àudio")
        with open(p.ruta_csv_acords(), encoding="utf-8") as fh:
            self.assertIn("N", fh.read(), "el CSV del projecte s'ha normalitzat")


def tearDownModule():
    try:
        import _qt_neteja
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()


if __name__ == "__main__":
    unittest.main()
