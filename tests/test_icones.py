"""Coherència de les ICONES (`app/icones.py` + `icones/*.svg`).

Una icona que no existeix **no peta**: `icones.ico()` torna una pixmap buida i
el botó queda sense dibuix, en silenci. Només es nota mirant la finestra. Aquest
guard comprova que totes les icones que el CODI demana hi són (auditoria
18-10-2026).
"""
import glob
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtWidgets import QApplication  # noqa: E402

from app import icones  # noqa: E402

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _usades():
    """Noms d'icona que apareixen LITERALMENT al codi de `app/`."""
    noms = set()
    for p in glob.glob(os.path.join(ARREL, "app", "*.py")):
        with open(p, encoding="utf-8") as f:
            src = f.read()
        noms |= set(re.findall(r'icones\.ico\("([a-z0-9_]+)"', src))
        noms |= set(re.findall(r'\bicona\s*=\s*"([a-z0-9_]+)"', src))
        noms |= set(re.findall(
            r'icones\.icona_boto\([^,]+,\s*"([a-z0-9_]+)"', src))
    return noms


class TestIcones(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_totes_les_icones_demanades_existeixen(self):
        usades = _usades()
        self.assertGreaterEqual(len(usades), 8, "no he trobat usos d'icones")
        for nom in sorted(usades):
            self.assertTrue(icones.disponible(nom),
                            f"falta l'icona {nom!r} ({nom}.svg)")

    def test_disponible_es_fiable(self):
        """`disponible()` mira el fitxer de debò, no una llista hardcoded."""
        self.assertTrue(icones.disponible("play"))
        self.assertFalse(icones.disponible("aixo_no_existeix"))

    def test_l_icona_de_l_app_existeix(self):
        """La icona de la finestra (barra de tasques) també ha d'haver-hi."""
        pm = icones.icona_app()
        self.assertFalse(pm.isNull(), "la icona de l'app ix buida")

    def test_les_icones_tenen_paleta_de_recoloreig(self):
        """`ico()` recoloreix l'SVG: un color invàlid no ha de fer-la buida."""
        pm = icones.ico("play", 18)
        self.assertFalse(pm.isNull())


if __name__ == "__main__":
    unittest.main()
