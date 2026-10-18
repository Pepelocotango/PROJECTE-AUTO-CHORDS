"""La taula única d'operacions d'edició (`docs/EDICIO_OPERACIONS.md`) no pot
quedar-se enrere: ha de llistar **totes** les eines `ac_*` del pont i cap
d'inventada.

És el document que creua GUI ↔ MCP ↔ paritat #11 (§2 del pla d'edició lliure).
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene dels tests: l'import té efecte (esborra els temporals en plegar)

from app import mcp_bridge  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, "docs", "EDICIO_OPERACIONS.md")


class TestDocEdicioOperacions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DOC, encoding="utf-8") as f:
            cls.text = f.read()
        cls.citades = set(re.findall(r"`(ac_[a-z_]+)`", cls.text))

    def _vives(self):
        return {"ac_" + op for op in mcp_bridge.OPERACIONS}

    def test_totes_les_eines_hi_surten(self):
        falten = sorted(self._vives() - self.citades)
        self.assertEqual(falten, [], f"eines sense documentar: {falten}")

    def test_cap_eina_inventada(self):
        fantasma = sorted(self.citades - self._vives())
        self.assertEqual(fantasma, [],
                         f"eines citades que no existeixen: {fantasma}")

    def test_la_taula_diu_gui_mcp_i_paritat(self):
        """Cada fila ha de dir com es fa per GUI, per MCP i si val per a les dues
        pistes (paritat #11)."""
        for capçalera in ("| GUI", "| MCP |", "| Acords |", "| Estr. |"):
            self.assertIn(capçalera, self.text)


if __name__ == "__main__":   # pragma: no cover
    unittest.main()
