"""`activa_faulthandler`: la traça d'un crash nadiu queda a disc.

Sense això, un SIGSEGV de Qt/PortAudio no deixava res (ni `excepthook` ni log)
i un informe de beta era només «s'ha tancat sol».
"""
import faulthandler
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene dels tests: l'import té efecte (esborra els temporals en plegar)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from app import main as app_main  # noqa: E402


class _Logger:
    def __init__(self):
        self.avisos = []

    def warning(self, fmt, *args):
        self.avisos.append(fmt % args if args else fmt)


class TestActivaFaulthandler(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.log = os.path.join(self.td, "auto-chords.log")
        # el faulthandler és global del procés: ho deixem com estava
        self._estava = faulthandler.is_enabled()
        self.addCleanup(self._restaura)

    def _restaura(self):
        if app_main._FH_FITXER is not None:
            try:
                app_main._FH_FITXER.close()
            except OSError:
                pass
            app_main._FH_FITXER = None
        faulthandler.disable()
        if self._estava:
            faulthandler.enable()
        __import__("shutil").rmtree(self.td, True)

    def test_activa_i_crea_el_fitxer_al_costat_del_log(self):
        ruta = app_main.activa_faulthandler(self.log)
        self.assertEqual(ruta, os.path.join(self.td, "crash_nadiu.log"))
        self.assertTrue(os.path.isfile(ruta))
        self.assertTrue(faulthandler.is_enabled())
        self.assertEqual(os.path.getsize(ruta), 0, "en sortida normal, buit")

    def test_escriu_la_traça_al_fitxer(self):
        ruta = app_main.activa_faulthandler(self.log)
        faulthandler.dump_traceback(file=app_main._FH_FITXER)
        app_main._FH_FITXER.flush()
        with open(ruta, encoding="utf-8") as f:
            self.assertIn("most recent call first", f.read())

    def test_traça_anterior_es_conserva_i_s_avisa(self):
        ruta = os.path.join(self.td, "crash_nadiu.log")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write("Windows fatal exception: access violation\n")
        lg = _Logger()
        app_main.activa_faulthandler(self.log, lg)
        with open(ruta + ".anterior", encoding="utf-8") as f:
            self.assertIn("access violation", f.read())
        self.assertEqual(os.path.getsize(ruta), 0)
        self.assertTrue(any("crash nadiu" in a for a in lg.avisos))

    def test_sense_crash_previ_no_avisa(self):
        lg = _Logger()
        app_main.activa_faulthandler(self.log, lg)
        self.assertEqual(lg.avisos, [])
        self.assertFalse(os.path.exists(
            os.path.join(self.td, "crash_nadiu.log.anterior")))

    def test_dues_activacions_no_deixen_fitxers_oberts(self):
        app_main.activa_faulthandler(self.log)
        primer = app_main._FH_FITXER
        app_main.activa_faulthandler(self.log)
        self.assertTrue(primer.closed)
        self.assertFalse(app_main._FH_FITXER.closed)

    def test_directori_no_escriptible_no_peta(self):
        ruta = app_main.activa_faulthandler(
            os.path.join(self.td, "no", "existeix", "x.log"))
        self.assertIsNone(ruta)


if __name__ == "__main__":
    unittest.main()
