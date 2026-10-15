"""Auditoria GUI ↔ documentació: `docs/ESQUEMA_UI.md` no ha de divergir de la
GUI real.

Extreu la GUI **de debò** (barres d'eines, menús, transport) i comprova que tot
hi sigui a la doc. Així, si algú afegeix/renombra un botó o una acció de menú i
no actualitza l'`ESQUEMA_UI`, el CI peta.

(Neix de bugs reals: la barra d'accions que Qt posava a la mateixa fila, i el
botó de «zoom a la selecció» que només era al transport del visor — que s'amaga
quan va incrustat.)
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import QApplication, QMenu, QPushButton, QToolBar  # noqa: E402

from app import main as app_main  # noqa: E402

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ARREL, "docs", "ESQUEMA_UI.md")


class EsquemaUiDocTests(unittest.TestCase):
    def setUp(self):
        # cal mantenir la referència a la QApplication (si no, el GC la mata)
        self._app = QApplication.instance() or QApplication([])
        self.w = app_main.Finestra()
        self.w.resize(1280, 900)
        self.w.show()                 # cal mostrar-la perquè Qt assigni geometries
        self._app.processEvents()
        with open(DOC, encoding="utf-8") as f:
            self.doc = f.read()

    def test_barres_documentades(self):
        """Cada barra d'eines ha de sortir pel seu nom a la doc."""
        for tb in self.w.findChildren(QToolBar):
            self.assertIn(tb.windowTitle(), self.doc,
                          f"la barra «{tb.windowTitle()}» no surt a la doc")

    def test_botons_obre_audio_i_mode_facil(self):
        """La barra ha de tenir «Obre àudio» i «Mode fàcil» (botó a l'app)."""
        texts = [b.text()
                 for b in self.w.barra_principal.findChildren(QPushButton)]
        self.assertIn("Obre àudio", texts)
        self.assertIn("Mode fàcil", texts)
        self.assertIsNotNone(getattr(self.w, "b_mode_facil", None))

    def test_accions_de_menu_documentades(self):
        """Cada acció real de menú ha d'aparèixer a la doc."""
        faltes = []
        for m in self.w.menuBar().findChildren(QMenu):
            for a in m.actions():
                t = a.text().replace("&", "").strip()
                if t and not a.isSeparator() and t not in self.doc:
                    faltes.append(t)
        self.assertEqual(faltes, [],
                         f"accions de menú NO documentades a l'ESQUEMA_UI: {faltes}")

    def test_menus_documentats(self):
        for m in self.w.menuBar().findChildren(QMenu):
            nom = m.title().replace("&", "").strip()
            if nom:
                self.assertIn(nom, self.doc,
                              f"el menú «{nom}» no surt a la doc")

    def test_transport_te_zoom_seleccio(self):
        """El transport de la finestra ha de tenir el botó de zoom a la selecció."""
        tips = [b.toolTip() for b in
                self.w.barra_transport.findChildren(QPushButton)]
        self.assertTrue(any("selecci" in t.lower() for t in tips),
                        "falta el botó de zoom a la selecció al transport")
        self.assertIn("Zoom a la selecció", self.doc)

    def test_barres_en_files_distintes(self):
        """Les 3 barres han d'ocupar files (y) diferents (cal `addToolBarBreak`)."""
        ys = {tb.windowTitle(): tb.geometry().y()
              for tb in self.w.findChildren(QToolBar)}
        self.assertEqual(len(set(ys.values())), len(ys),
                         f"hi ha barres a la mateixa fila: {ys}")



def tearDownModule():
    # Neteja ORDENADA dels objectes Qt del mòdul (evita destrucció pel GC en un
    # test posterior -> access violation intermitent). Vegeu tests/_qt_neteja.py.
    try:
        import _qt_neteja
    except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

if __name__ == "__main__":
    unittest.main()
