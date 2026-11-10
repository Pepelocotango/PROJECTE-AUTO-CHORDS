"""Test: la documentació generada ha d'estar al dia.

- `README.md` (formats d'àudio) — `eines/genera_formats.py`
- `DEVELOPING.md` (comandes) — `eines/genera_comandes.py`
- `docs/README.md` (índex) — `eines/genera_index_docs.py`

Si algú canvia el codi o el `Makefile` i no regenera (`make docs`), peta.
"""
import io
import os
import subprocess
import sys
import unittest

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402

_ = _temporals

sys.path.insert(0, ARREL)


class TestDocsGeneratsAlDia(unittest.TestCase):
    def _check(self, eina: str):
        r = subprocess.run(
            [sys.executable, os.path.join(ARREL, "eines", eina), "--check"],
            cwd=ARREL, capture_output=True, text=True)
        self.assertEqual(
            r.returncode, 0,
            f"{r.stdout}{r.stderr}\n→ Corre: make docs")

    def test_formats_al_dia(self):
        self._check("genera_formats.py")

    def test_comandes_al_dia(self):
        self._check("genera_comandes.py")

    def test_index_docs_al_dia(self):
        self._check("genera_index_docs.py")


class TestFormatsCoherents(unittest.TestCase):
    """El recompte de formats del codi ha de coincidir amb els docs."""

    def test_recompte_a_agents_readme_i_json(self):
        from app import ffmpeg
        n = len(ffmpeg.extensions())
        for rel in ("AGENTS.md", "README.md", "eines/funcionalitats_dades.json"):
            with io.open(os.path.join(ARREL, rel), encoding="utf-8") as f:
                self.assertIn(f"{n} formats", f.read(),
                              f"{rel} no diu «{n} formats»")


if __name__ == "__main__":
    unittest.main()
