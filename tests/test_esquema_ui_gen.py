"""Les vistes de l'esquema de la UI (`docs/ESQUEMA_UI.html` i `.svg`) han d'estar
**generades** i **al dia** amb la font única `docs/ESQUEMA_UI.md`.

El generador és **`eines/genera_esquema_ui.py`** (stdlib). Si algú edita el `.md`
i no regenera, aquest test peta i diu la comanda exacta a córrer.
"""
import os
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ARREL, "eines", "genera_esquema_ui.py")
HTML = os.path.join(ARREL, "docs", "ESQUEMA_UI.html")
SVG = os.path.join(ARREL, "docs", "ESQUEMA_UI.svg")
MD = os.path.join(ARREL, "docs", "ESQUEMA_UI.md")


class TestEsquemaUiGenerat(unittest.TestCase):
    def test_vistes_generades_i_al_dia(self):
        """`--check` compara les vistes amb el que produiria el `.md`."""
        r = subprocess.run([sys.executable, GEN, "--check"],
                           cwd=ARREL, capture_output=True, text=True)
        self.assertEqual(
            r.returncode, 0,
            "Les vistes ESQUEMA_UI no estan al dia amb el .md:\n"
            f"{r.stdout}{r.stderr}\n"
            "→ Corre: python3 eines/genera_esquema_ui.py")

    def test_els_fitxers_existeixen(self):
        for p in (MD, GEN, HTML, SVG):
            self.assertTrue(os.path.isfile(p), f"falta {p}")

    def test_svg_es_xml_valid(self):
        ET.parse(SVG)          # aixeca si no és XML correcte

    def test_html_referencia_la_font(self):
        with open(HTML, encoding="utf-8") as f:
            s = f.read()
        self.assertIn("ESQUEMA_UI.md", s)     # porta el peu «generat des de…»
        self.assertIn("NO editar a mà", s)


if __name__ == "__main__":
    unittest.main()
