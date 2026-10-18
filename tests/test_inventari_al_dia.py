"""La llista de components (`docs/COMPONENTS_I_VERSIONS.md`) ha d'estar AL DIA.

El CI ja ho comprova (`build-all`: genera l'inventari i fa `git diff
--exit-code`), però això vol dir descobrir el desfasament **al CI**, després
d'haver pujat. Aquest test ho atrapa en local.

Es fa servir la funció **PURA** `construeix()` de l'eina (no escriu cap fitxer):
el document és d'OC-12 i un test no l'ha de tocar (auditoria 18-10-2026).
"""
import importlib.util
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene dels tests: l'import té efecte (esborra els temporals en plegar)

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ARREL, "docs", "COMPONENTS_I_VERSIONS.md")
EINA = os.path.join(ARREL, "eines", "genera_inventari.py")


def _eina():
    spec = importlib.util.spec_from_file_location("genera_inventari", EINA)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestInventariAlDia(unittest.TestCase):

    def test_el_document_coincideix_amb_el_que_es_generaria(self):
        if not os.path.isfile(DOC):
            self.skipTest("no hi ha el document d'inventari")
        with open(DOC, encoding="utf-8") as f:
            actual = f.read()
        generat = _eina().construeix()
        self.assertEqual(
            generat, actual,
            "docs/COMPONENTS_I_VERSIONS.md està desfasat respecte de "
            "requirements.txt / eines/deps_fixades.env: torna a generar-lo "
            "(python3 eines/genera_inventari.py)")

    def test_l_eina_no_te_efectes_en_construir(self):
        """`construeix()` no ha d'escriure res (el test no toca cap doc)."""
        abans = None
        if os.path.isfile(DOC):
            with open(DOC, encoding="utf-8") as f:
                abans = f.read()
        _eina().construeix()
        if abans is not None:
            with open(DOC, encoding="utf-8") as f:
                self.assertEqual(f.read(), abans, "no pot haver-lo tocat")


if __name__ == "__main__":
    unittest.main()
