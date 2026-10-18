"""Paritat entre l'ESQUEMA de cada eina MCP i el que el PONT llig de debò.

Si l'esquema oferix un paràmetre que la funció del pont no llig mai, l'agent el
passa i s'ignora **en silenci** (pitjor que un error: creu que ha fet una cosa i
no l'ha feta). I a l'inrevés, un paràmetre que el pont necessita i l'esquema no
declara fa que l'eina sempre peta.

Es comprova estàticament sobre el codi font del pont (auditoria 18-10-2026: les
74 eines estaven en paritat).
"""
import ast
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene dels tests: l'import té efecte (esborra els temporals en plegar)

from eines import mcp_auto_chords_server as srv  # noqa: E402

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Ajudes del pont que lliguen un paràmetre sense dir-ne el nom literal.
AJUDES = {"_kind_opt": {"kind", "tipus"}}


def _fonts_del_pont():
    ruta = os.path.join(ARREL, "app", "mcp_bridge.py")
    with open(ruta, encoding="utf-8") as f:
        src = f.read()
    return {n.name: ast.get_source_segment(src, n)
            for n in ast.parse(src).body if isinstance(n, ast.FunctionDef)}


def _llegeix(cos):
    """Noms de paràmetre que la funció llig de `params`."""
    noms = set()
    noms |= set(re.findall(r'params\.get\(\s*"([a-z_0-9]+)"', cos))
    noms |= set(re.findall(r'params\[\s*"([a-z_0-9]+)"\s*\]', cos))
    noms |= set(re.findall(r'"([a-z_0-9]+)"\s+in\s+params', cos))
    for m in re.finditer(r'_\w+\(\s*params\s*,\s*([^)]*)\)', cos):
        noms |= set(re.findall(r'"([a-z_0-9]+)"', m.group(1)))
    for ajuda, claus in AJUDES.items():
        if re.search(re.escape(ajuda) + r"\(\s*params", cos):
            noms |= claus
    return noms


class TestEsquemesMCP(unittest.TestCase):

    def test_cada_eina_te_la_seua_funcio_al_pont(self):
        funcs = _fonts_del_pont()
        for nom, op, _d, _p in srv._TOOLS:
            self.assertIn("_op_" + op, funcs,
                          f"{nom}: falta `_op_{op}` al pont")

    def test_l_esquema_i_el_pont_parlen_dels_mateixos_parametres(self):
        funcs = _fonts_del_pont()
        for nom, op, _d, props in srv._TOOLS:
            cos = funcs.get("_op_" + op)
            if cos is None:
                continue                       # ja ho diu el test anterior
            ignorats = set(props) - _llegeix(cos)
            self.assertEqual(ignorats, set(),
                             f"{nom}: l'esquema oferix {sorted(ignorats)} i el "
                             f"pont no els llig (s'ignorarien en silenci)")

    def test_totes_les_eines_tenen_descripcio_i_esquema_objecte(self):
        for nom, _op, desc, props in srv._TOOLS:
            self.assertTrue(desc and desc.strip(), f"{nom}: sense descripció")
            self.assertIsInstance(props, dict, f"{nom}: esquema no és dict")


if __name__ == "__main__":
    unittest.main()
