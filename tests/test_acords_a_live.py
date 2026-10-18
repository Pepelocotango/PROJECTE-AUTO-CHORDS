"""Smoke de la guia DAW (`acords_a_live.py`) i dels locators.

L'app crida aquest script de veritat (`pipeline.run_acords_py`) però la suite
**sempre el mockejava** (`patch.object(pipeline, "run_acords_py")`): no hi havia
cap prova que s'executara, que generara els dos fitxers ni que respectara el
**mapa de tempo/compàs** (auditoria 18-10-2026). Aquest fitxer executa l'script
de debò.
"""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import pipeline  # noqa: E402
from app import plataforma  # noqa: E402

ACORDS = "inici_s,fi_s,acord\n0.0,4.0,C\n4.0,8.0,Am\n8.0,12.0,F\n12.0,16.0,G\n"


def _carpeta(tempo=None, compas=None):
    td = tempfile.mkdtemp()
    with open(os.path.join(td, "acords.csv"), "w", encoding="utf-8") as f:
        f.write(ACORDS)
    if tempo:
        with open(os.path.join(td, "tempo.csv"), "w", encoding="utf-8") as f:
            f.write(tempo)
        with open(os.path.join(td, "compas.csv"), "w", encoding="utf-8") as f:
            f.write(compas)
    return td


class TestGuiaDaw(unittest.TestCase):

    def _corre(self, td, durada=16.0):
        return pipeline.run_acords_py(
            os.path.join(td, "acords.csv"), 120.0, 4, 0.0, td,
            lambda *a: None, durada=durada)

    def test_genera_locators_i_guia(self):
        td = _carpeta()
        loc, guia = self._corre(td)
        self.assertTrue(os.path.isfile(loc), "ha de generar acords_locators.txt")
        self.assertTrue(os.path.isfile(guia), "ha de generar guia_acords.html")
        with open(loc, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("C", text)
        self.assertIn("G", text)
        with open(guia, encoding="utf-8") as f:
            html = f.read()
        self.assertIn("120 BPM", html)
        self.assertIn("<div class=\"g\">", html)

    def test_amb_mapa_de_tempo_variable(self):
        """Amb `tempo.csv`/`compas.csv` de més d'un tram, la guia es calcula
        amb el mapa (posicions compàs.temps.setzena) i no peta."""
        td = _carpeta(tempo="ini_s,fi_s,bpm\n0.0,8.0,120\n8.0,16.0,90\n",
                      compas="ini_s,fi_s,beats,beat_type\n0.0,8.0,4,4\n"
                             "8.0,16.0,3,4\n")
        loc, guia = self._corre(td)
        self.assertTrue(os.path.isfile(loc))
        self.assertTrue(os.path.isfile(guia))
        with open(guia, encoding="utf-8") as f:
            self.assertIn("G", f.read())

    def test_sense_arguments_dona_usuari_i_no_traça(self):
        """Sense arguments ha de dir l'ús, no petar amb IndexError."""
        script = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "acords_a_live.py")
        p = subprocess.run([plataforma.python_actual(), script],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 2)
        self.assertIn("Ús:", p.stderr)
        self.assertNotIn("Traceback", p.stderr)


if __name__ == "__main__":
    unittest.main()
