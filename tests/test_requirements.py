"""Guard de dependències: MAI `numpy >= 2` ni `PyQt6`.

El Q9400 no té AVX/SSE4.2: `numpy` 2.x demana `x86_64-v2` (SIGILL) i PyQt6
trencaria el desplegament a High Sierra 10.13. Aquest test ho vigila a
`requirements.txt`, `pyproject.toml` i els workflows de CI: si algú ho
introdueix sense voler, el CI peta.
"""
import glob
import os
import re
import unittest
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene dels tests: l'import té efecte (esborra en plegar)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FITXERS = ([os.path.join(ROOT, "requirements.txt"),
            os.path.join(ROOT, "pyproject.toml")]
           + sorted(glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml"))))

# Especificadors que admetrien la 2.x de numpy.
_NUMPY_2 = (r"numpy\s*>=\s*2", r"numpy\s*==\s*2", r"numpy\s*>\s*2",
            r"numpy\s*~=\s*2", r"numpy\s*!=\s*1")
# Requisit REAL de numpy: `numpy` seguit d'un operador (no una menció en prosa).
_RE_NUMPY = re.compile(r"numpy\s*((?:==|>=|<=|>|<|~=|!=)\s*[^\"'\s]+)")


class GuardAvxTests(unittest.TestCase):
    """Regla d'or #9: cap binari del paquet pot requerir **AVX**.

    El Q9400 no en té: un binari compilat amb AVX peta amb SIGILL (ja va passar
    amb la CLI d'opencode). La garantia ve del build, així que aquest test
    vigila que els scripts de compilació dels natius **no** hi introdueixin
    flags amb AVX ni `-march=native` (que compilaria pel maquinari de qui
    construeix, no pel de destí).
    """

    SCRIPTS = ("eines/compila_vamp_host.sh", "eines/compila_vamp_plugins.sh",
               "eines/compila_vamp_plugins.sh")
    PROHIBIT = (r"-mavx", r"-mavx2", r"-mavx512", r"-march\s*=\s*native",
                r"-march\s*=\s*haswell", r"-mtune\s*=\s*native")

    def test_cap_flag_amb_avx(self):
        for rel in self.SCRIPTS:
            f = os.path.join(ROOT, rel)
            if not os.path.isfile(f):
                continue
            with open(f, encoding="utf-8") as fh:
                linies = [ln for ln in fh.read().splitlines()
                          if not ln.lstrip().startswith("#")]   # sense comentaris
            text = "\n".join(linies)
            for pat in self.PROHIBIT:
                self.assertIsNone(
                    re.search(pat, text),
                    f"{rel}: hi ha un flag amb AVX ({pat}) — el Q9400 no en té")

    def test_els_builds_demanen_sse2(self):
        for rel in ("eines/compila_vamp_host.sh",
                    "eines/compila_vamp_plugins.sh"):
            f = os.path.join(ROOT, rel)
            if not os.path.isfile(f):
                continue
            with open(f, encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn("-msse2", text,
                          f"{rel}: cal fixar el maquinari mínim amb -msse2")


class DependènciesGuardTests(unittest.TestCase):
    @staticmethod
    def _sense_comentaris(t):
        """Treu els comentaris (`#...`): un comentari no és una dependència."""
        return "\n".join(ln.split("#", 1)[0] for ln in t.splitlines())

    def _llegeix(self):
        d = {}
        for f in FITXERS:
            if os.path.isfile(f):
                with open(f, encoding="utf-8") as fh:
                    d[f] = self._sense_comentaris(fh.read())
        return d

    def test_cap_pyqt6(self):
        for f, t in self._llegeix().items():
            self.assertNotIn("PyQt6", t, f"PyQt6 introduït a {f}")

    def test_cap_especificador_de_numpy_2(self):
        for f, t in self._llegeix().items():
            for patro in _NUMPY_2:
                self.assertIsNone(re.search(patro, t),
                                  f"{f}: numpy podria resoldre's a 2.x ({patro})")

    def test_si_es_demana_numpy_ha_d_excloure_la_2(self):
        # Només mirem REQUISITS reals (`numpy` + operador), no mencions en prosa
        # (noms de passos, comentaris...).
        for f, t in self._llegeix().items():
            for m in _RE_NUMPY.finditer(t):
                spec = m.group(1).replace(" ", "")
                ok = ("<2" in spec) or spec.startswith("==1.")
                self.assertTrue(ok, f"{f}: numpy '{m.group(1)}' podria ser 2.x")

    def test_requirements_pin_exacte(self):
        # A requirements.txt totes les dependències van amb `==` (pins exactes).
        with open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8") as fh:
            linies = [ln.strip() for ln in fh
                      if ln.strip() and not ln.strip().startswith("#")]
        self.assertTrue(linies, "requirements.txt buit?")
        for ln in linies:
            nom = ln.split(";")[0].strip()      # sense el marcador de plataforma
            self.assertIn("==", nom, f"sense pin exacte: {ln!r}")
        m = re.search(r"^numpy==([\d.]+)", "\n".join(linies), re.M)
        self.assertIsNotNone(m, "requirements.txt ha de fixar numpy amb ==")
        self.assertTrue(m.group(1).startswith("1."),
                        f"numpy ha de ser 1.x, no {m.group(1)}")


if __name__ == "__main__":
    unittest.main()
