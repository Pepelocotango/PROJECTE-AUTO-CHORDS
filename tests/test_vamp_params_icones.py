#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests dels mòduls que no en tenien cap: `app/vamp_params.py` i `app/icones.py`.

- `vamp_params`: parseja els descriptors `.n3` dels plugins Vamp (paràmetres
  quantitzats i numèrics, ordre del descriptor, valors per defecte).
- `icones`: disponibilitat dels SVG i els colors de la UI (l'app no ha de petar
  mai per una icona que falti).
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene dels tests: l'import té efecte (esborra els temporals en plegar)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtWidgets import QApplication  # noqa: E402
from app import icones, vamp_params  # noqa: E402

N3_PROVA = """
plugbase:test_param_alpha a vamp:QuantizedParameter ;
    vamp:identifier "alpha" ;
    dc:title "Alpha" ;
    value_names ("one", "two", "three") ;
    min_value 1 ; max_value 3 ; quantize_step 1 ; default_value 2 .

plugbase:test_param_beta a vamp:Parameter ;
    vamp:identifier "beta" ;
    dc:title "Beta" ;
    min_value 0.0 ; max_value 10.0 ; default_value 5.0 .

plugbase:test a vamp:Plugin ;
    vamp:parameter plugbase:test_param_alpha ;
    vamp:parameter plugbase:test_param_beta .
"""


class TestVampParams(unittest.TestCase):
    """Els descriptors `.n3` dels plugins Vamp es converteixen bé."""

    def _n3(self, text=N3_PROVA):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "test.n3")
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        self.addCleanup(lambda: os.remove(p))
        return p

    def test_parseja_quantitzat_i_numeric(self):
        ps = vamp_params.llegeix_params(self._n3(), "test")
        self.assertEqual(len(ps), 2, "dos paràmetres al descriptor")
        alpha = next(p for p in ps if p["id"] == "alpha")
        beta = next(p for p in ps if p["id"] == "beta")
        self.assertEqual(alpha["tipus"], "quantitzat")
        self.assertEqual(alpha["titol"], "Alpha")
        self.assertEqual(alpha["valors"], ["one", "two", "three"])
        self.assertEqual(alpha["minim"], 1.0)
        self.assertEqual(alpha["maxim"], 3.0)
        self.assertEqual(alpha["defecte"], 2.0)
        self.assertEqual(beta["tipus"], "numeric")
        self.assertEqual(beta["valors"], [])
        self.assertEqual(beta["maxim"], 10.0)
        self.assertEqual(beta["pas"], 0.0, "un numèric no té pas de quantització")

    def test_ordre_del_descriptor(self):
        ps = vamp_params.llegeix_params(self._n3(), "test")
        self.assertEqual([p["id"] for p in ps], ["alpha", "beta"],
                         "s'ha de respectar l'ordre declarat al plugin")

    def test_plugin_sense_parametres(self):
        ps = vamp_params.llegeix_params(
            self._n3("plugbase:test a vamp:Plugin .\n"), "test")
        self.assertEqual(ps, [])

    def test_params_de_clau_desconeguda(self):
        with self.assertRaises(KeyError):
            vamp_params.params_de("no_existeix")

    def test_params_de_i_valors_per_defecte_dels_reals(self):
        # Amb els plugins reals del repo (si hi són) o llista buida; mai peta.
        for clau in ("chords", "structure"):
            ps = vamp_params.params_de(clau)
            self.assertIsInstance(ps, list)
            vd = vamp_params.valors_per_defecte(clau)
            self.assertIsInstance(vd, dict)
            self.assertEqual(set(vd), {p["id"] for p in ps})


class TestIcones(unittest.TestCase):
    """Icones SVG + colors de la UI."""

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_disponible_amb_una_icona_real(self):
        svgs = [f[:-4] for f in os.listdir(icones._DIR) if f.endswith(".svg")]
        self.assertTrue(svgs, "hi ha d'haver icones al repo")
        for nom in svgs[:5]:
            self.assertTrue(icones.disponible(nom), nom)

    def test_disponible_inexistent(self):
        self.assertFalse(icones.disponible("no_existeix_zzz"))

    def test_ico_sense_svg_retorna_buida_sense_petar(self):
        # L'app no ha de petar mai per una icona que falti.
        ico = icones.ico("no_existeix_zzz")
        self.assertTrue(ico.isNull(), "ha de tornar un QIcon buit")

    def test_ico_real_no_es_buida(self):
        svgs = [f[:-4] for f in os.listdir(icones._DIR) if f.endswith(".svg")]
        self.assertFalse(icones.ico(svgs[0]).isNull())

    def test_colors_son_hex_valids(self):
        for c in (icones.TEXT, icones.MUTED, icones.ACTIU, icones.BLAU,
                  icones.GROC, icones.VERMELL):
            self.assertRegex(c, r"^#[0-9a-fA-F]{6}$", f"color invàlid: {c!r}")


if __name__ == "__main__":
    unittest.main()
