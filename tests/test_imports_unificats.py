"""Els mòduls de l'app han de ser UN SOL objecte (no dos per import cru).

`app/main.py` importava `ffmpeg`, `partitura`, `pipeline`, `postproc` i `theme`
pel **nom cru** mentre la resta del codi feia `from . import X`: això crea
**dos objectes de mòdul** per al mateix fitxer → l'estat a nivell de mòdul pot
divergir i el *monkey-patching* deixa de funcionar (va passar de veritat: un
test de la partitura patchejava `app.partitura` i `main` seguia fent servir
l'altre objecte).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class TestUnSolObjecteDeModul(unittest.TestCase):
    def test_main_veu_els_mateixos_moduls(self):
        from app import main as app_main
        from app import ffmpeg, partitura, pipeline, postproc, theme
        for nom, mod in (("ffmpeg", ffmpeg), ("partitura", partitura),
                         ("pipeline", pipeline), ("postproc", postproc),
                         ("theme", theme)):
            self.assertIs(
                getattr(app_main, nom), mod,
                f"`app.main.{nom}` i `app.{nom}` són objectes DIFERENTS "
                f"(import cru vs relatiu)")

    def test_el_visor_i_la_finestra_comparteixen_pipeline(self):
        from app import main as app_main
        from app import pipeline, visor
        self.assertIs(visor.pipeline, pipeline)
        self.assertIs(app_main.pipeline, pipeline)


if __name__ == "__main__":
    unittest.main()
