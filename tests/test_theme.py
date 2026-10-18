"""Coherència del tema (`app/theme.py`).

El tema és la font dels colors de la UI i de la distinció visual per carril
(regla d'or #11: cada família —acords, estructura i BPM/compàs— ha de ser
reconeixible pel seu color/carril). Un color mal escrit (#f3f4f6 amb 5 dígits,
una coma, un `None`…) no peta enlloc: simplement es pinta mal o cau a un valor
per defecte, i ningú no se n'adona. Aquest guard ho atura (auditoria
18-10-2026).
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene dels tests: l'import té efecte (esborra els temporals en plegar)

from app import theme  # noqa: E402

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def _colors():
    return {k: v for k, v in vars(theme).items()
            if k.isupper() and isinstance(v, str) and v.startswith("#")}


class TestTema(unittest.TestCase):

    def test_tots_els_colors_son_hex_de_6_digits(self):
        colors = _colors()
        self.assertGreater(len(colors), 30, "el tema hauria de tindre colors")
        for nom, val in colors.items():
            self.assertRegex(val, _HEX, f"{nom} = {val!r}")

    def test_les_paletes_son_valides_i_sense_repetits(self):
        paletes = {k: v for k, v in vars(theme).items()
                   if k.isupper() and isinstance(v, (tuple, list))
                   and v and all(isinstance(x, str) and x.startswith("#")
                                 for x in v)}
        self.assertTrue(paletes, "hi hauria d'haver alguna paleta")
        for nom, pal in paletes.items():
            for c in pal:
                self.assertRegex(c, _HEX, f"{nom}: {c!r}")
            self.assertEqual(len(set(pal)), len(pal),
                             f"{nom}: colors repetits dins la paleta")

    def test_el_llegat_de_seccio_te_varios_nivells(self):
        """`SECTION_FILLS` distingeix les lletres de secció (A, B, C…)."""
        self.assertGreaterEqual(len(theme.SECTION_FILLS), 3)

    def test_els_colors_dels_tres_carrils_son_distints(self):
        """Cada família ha de tindre un color propi (regla #11)."""
        self.assertNotEqual(theme.TL_LANE_BG_A, theme.TL_LANE_BG_B)
        # Les paletes de secció no poden coincidir amb el fons del carril.
        self.assertNotIn(theme.TL_LANE_BG_A, theme.SECTION_FILLS)


if __name__ == "__main__":
    unittest.main()
