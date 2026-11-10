"""Test: l'arbre de `ARBRE_DIRECTORIS.md` ha d'estar al dia.

El generador és `eines/genera_arbre.py`. Si algú afegeix, esborra o renombra
un fitxer o carpeta i no regenera l'arbre (`make docs`), aquest test peta.
"""
import os
import subprocess
import sys
import unittest

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402

_ = _temporals

EINA = os.path.join(ARREL, "eines", "genera_arbre.py")
DOC = os.path.join(ARREL, "ARBRE_DIRECTORIS.md")


class TestArbreAlDia(unittest.TestCase):
    def test_arbre_al_dia(self):
        r = subprocess.run([sys.executable, EINA, "--check"],
                           cwd=ARREL, capture_output=True, text=True)
        self.assertEqual(
            r.returncode, 0,
            f"{r.stdout}{r.stderr}\n"
            "→ Corre: make docs (o python3 eines/genera_arbre.py)")

    def test_document_existeix(self):
        self.assertTrue(os.path.isfile(DOC))


if __name__ == "__main__":
    unittest.main()
