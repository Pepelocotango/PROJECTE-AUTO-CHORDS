"""Test: la taula de mòduls de `DEVELOPING.md` ha d'estar al dia.

El generador és `eines/genera_moduls.py`. Si algú afegeix o renombra un mòdul
i no regenera la taula, aquest test peta.
"""
import os
import subprocess
import sys
import unittest

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402

_ = _temporals

EINA = os.path.join(ARREL, "eines", "genera_moduls.py")
DOC = os.path.join(ARREL, "DEVELOPING.md")


class TestModulsAlDia(unittest.TestCase):
    def test_taula_al_dia(self):
        r = subprocess.run([sys.executable, EINA, "--check"],
                           cwd=ARREL, capture_output=True, text=True)
        self.assertEqual(
            r.returncode, 0,
            f"{r.stdout}{r.stderr}\n"
            "→ Corre: python3 eines/genera_moduls.py")

    def test_document_existeix(self):
        self.assertTrue(os.path.isfile(DOC))


if __name__ == "__main__":
    unittest.main()
