"""El desat dels CSV d'edició (acords + estructura) és ATÒMIC.

Les edicions de l'usuari es desen a `acords.csv` i `estructura_ABC.csv` a cada
canvi. Abans el fitxer es truncava ABANS d'escriure: un error (o un crash/tall
de corrent) enmig el deixava buit o a mitges i es perdia la feina. Ara, o hi ha
la versió anterior sencera o la nova sencera, i no queden temporals.
"""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _temporals  # noqa: E402
_ = _temporals  # higiene dels tests: l'import té efecte (esborra en plegar)

from app import pipeline  # noqa: E402


class TestDesatAtomic(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, self.td, True)

    def _llegeix(self, nom):
        with open(os.path.join(self.td, nom), encoding="utf-8") as f:
            return f.read()

    def _residus(self):
        return [n for n in os.listdir(self.td) if n.endswith(".tmp")]

    def test_acords_escriu_i_no_deixa_temporals(self):
        ruta = os.path.join(self.td, "acords.csv")
        pipeline.desa_acords_csv(ruta, [(0.0, "N"), (2.0, "Am")])
        self.assertIn("2.00", self._llegeix("acords.csv"))
        self.assertEqual(self._residus(), [])

    def test_acords_error_enmig_conserva_la_versio_anterior(self):
        ruta = os.path.join(self.td, "acords.csv")
        pipeline.desa_acords_csv(ruta, [(0.0, "N"), (2.0, "Am")])
        abans = self._llegeix("acords.csv")
        with self.assertRaises(ValueError):
            pipeline.desa_acords_csv(ruta, [(0.0, "C"), ("no-és-un-temps", "G")])
        self.assertEqual(self._llegeix("acords.csv"), abans,
                         "un error enmig no pot deixar el CSV truncat")
        self.assertEqual(self._residus(), [])

    def test_abc_error_enmig_conserva_la_versio_anterior(self):
        ruta = os.path.join(self.td, "estructura_ABC.csv")
        bons = [(0.0, 4.0, "A", "A"), (4.0, 8.0, "B", "B")]
        pipeline.desa_abc_csv(ruta, bons, 120.0, lambda *_: None)
        abans = self._llegeix("estructura_ABC.csv")
        dolents = [(0.0, 4.0, "A", "A"), ("x", 8.0, "B", "B")]
        with self.assertRaises((ValueError, TypeError)):
            pipeline.desa_abc_csv(ruta, dolents, 120.0, lambda *_: None)
        self.assertEqual(self._llegeix("estructura_ABC.csv"), abans)
        self.assertEqual(self._residus(), [])

    def test_windows_destí_ocupat_es_reintenta(self):
        """Antivirus/Explorer poden tenir el destí obert un instant."""
        ruta = os.path.join(self.td, "acords.csv")
        real = os.replace
        crides = {"n": 0}

        def replace_flaquer(a, b):
            crides["n"] += 1
            if crides["n"] < 3:
                raise PermissionError("destí ocupat")
            return real(a, b)

        with patch.object(pipeline.os, "replace", replace_flaquer), \
                patch.object(pipeline.time, "sleep"):
            pipeline.desa_acords_csv(ruta, [(0.0, "N")])
        self.assertEqual(crides["n"], 3)
        self.assertTrue(os.path.isfile(ruta))
        self.assertEqual(self._residus(), [])

    def test_windows_destí_sempre_ocupat_dona_error_net(self):
        ruta = os.path.join(self.td, "acords.csv")
        with patch.object(pipeline.os, "replace",
                          side_effect=PermissionError("ocupat")), \
                patch.object(pipeline.time, "sleep"):
            with self.assertRaises(PermissionError):
                pipeline.desa_acords_csv(ruta, [(0.0, "N")])
        self.assertEqual(self._residus(), [])


if __name__ == "__main__":
    unittest.main()
