"""Auditoria: `docs/TIPUS_XIFRAT_ACORDS.md` no ha de divergir de `app/xifrat.py`.

Si s'afegeix un tipus d'acord al codi (`xifrat.TIPUS`) i no es documenta, el CI
peta — igual que fa `tests/test_esquema_ui_doc.py` amb l'ESQUEMA_UI.
"""
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import xifrat  # noqa: E402

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ARREL, "docs", "TIPUS_XIFRAT_ACORDS.md")


class TestDocXifrat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with io.open(DOC, encoding="utf-8") as f:
            cls.doc = f.read()

    def test_tots_els_tipus_del_codi_son_al_doc(self):
        faltes = []
        for qual in xifrat.TIPUS:
            canon = "C" + qual          # els exemples del doc fan servir l'arrel C
            if f"`{canon}`" not in self.doc:
                faltes.append(canon)
        self.assertEqual(faltes, [],
                         f"tipus al codi i NO documentats al doc: {faltes}")

    def test_el_doc_tambe_llista_els_extres(self):
        """Els extres (no del PDF) hi han de ser: `5`, `noN`, `alt`, baixes…"""
        for tros in ("`C5`", "`Cno5`", "`C7alt`", "`C/E`", "`C##`", "`N`",
                     "`C69`"):
            self.assertIn(tros, self.doc, f"falta {tros} al doc")

    def test_diu_que_els_policords_no_hi_son(self):
        """Els policords NO estan suportats i el doc ho ha de dir."""
        self.assertIn("Policords", self.doc)
        self.assertIn("drop2", self.doc)


if __name__ == "__main__":
    unittest.main()
