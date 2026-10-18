"""L'endpoint del pont MCP no pot quedar-se sense fitxer mentre l'app és viva.

Troballa OC-6/378: `PROJECT_ROOT/temp/mcp_bridge.json` desapareixia amb l'app i
el socket **vius** → MCP inutilitzable.

**Causa arrel**: un altre procés (un **test** que cridava `activa_pont` sense
redirigir `ENDPOINT_PATH`) sobreescrivia l'endpoint amb el **seu** pid i, en
tancar-se, l'esborrava (el `_esborra_endpoint` només esborra el que és seu → el
seu era el que havia escrit). L'app viva quedava òrfena d'endpoint.

Proteccions:
1. `_escriu_endpoint` **no sobreescriu** l'endpoint d'un altre procés **viu**.
2. `_revisa_endpoint` (QTimer de 15 s) el **reescriu** si ha desaparegut.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene dels tests: l'import té efecte (esborra els temporals en plegar)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from unittest.mock import patch  # noqa: E402

import PyQt5.QtWidgets as QW  # noqa: E402

from app import mcp_bridge  # noqa: E402


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QW.QApplication.instance() or QW.QApplication([])

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.path = os.path.join(self._tmp, "mcp_bridge.json")
        self._pat = patch.object(mcp_bridge, "ENDPOINT_PATH", self.path)
        self._pat.start()

    def tearDown(self):
        self._pat.stop()

    def _dades(self):
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)


class TestProteccioEscriptura(_Base):
    def test_no_sobreescriu_l_endpoint_d_un_altre_proces_viu(self):
        # Un procés VIU que no és nostre: el PARE (getppid). Abans s'usava el
        # pid 1, que a Linux/init sempre hi és però a Windows NO existeix (i
        # allà `os.kill` no és una sonda) → el test fallava només a Windows.
        alien = os.getppid()
        if alien <= 0 or alien == os.getpid():
            self.skipTest("sense un procés pare vàlid per fer d'aliè")
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"port": 9999, "token": "aliena", "pid": alien}, f)
        w = QW.QWidget()
        p = mcp_bridge.PontMCP(w)
        try:
            d = self._dades()
            self.assertEqual(d["pid"], alien, "ha sobreescrit un endpoint aliè viu!")
            self.assertEqual(d["token"], "aliena")
            self.assertEqual(p._endpoint_viu_d_algu_altre(), alien)
            # I en tancar-se NO se l'ha d'endur (no és seu).
            p.tanca()
            self.assertTrue(os.path.isfile(self.path),
                            "tanca() s'ha emportat un endpoint aliè")
        finally:
            p.tanca()

    def test_recicla_l_endpoint_d_un_proces_mort(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"port": 9999, "token": "vella", "pid": 999999}, f)
        w = QW.QWidget()
        p = mcp_bridge.PontMCP(w)
        try:
            if p._actiu:
                self.assertEqual(self._dades()["pid"], os.getpid(),
                                 "un endpoint de procés mort s'ha de reciclar")
        finally:
            p.tanca()


class TestVigilancia(_Base):
    def test_reescriu_l_endpoint_si_desapareix(self):
        w = QW.QWidget()
        p = mcp_bridge.PontMCP(w)
        self.assertTrue(p._actiu, "el pont no s'ha pogut obrir")
        self.assertTrue(os.path.isfile(self.path))
        os.unlink(self.path)                  # actor extern
        self.assertFalse(os.path.isfile(self.path))
        p._revisa_endpoint()                  # el que fa el QTimer
        self.assertTrue(os.path.isfile(self.path),
                        "no s'ha reescrit l'endpoint desaparegut")
        self.assertEqual(self._dades()["pid"], os.getpid())
        self.assertEqual(self._dades()["port"], p._port)
        p.tanca()

    def test_el_timer_de_vigilancia_es_actiu_i_es_para(self):
        w = QW.QWidget()
        p = mcp_bridge.PontMCP(w)
        self.assertTrue(p._timer_endpoint.isActive())
        p.tanca()
        self.assertFalse(p._timer_endpoint.isActive())


if __name__ == "__main__":
    unittest.main()
