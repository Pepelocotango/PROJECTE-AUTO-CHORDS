"""Smoke dels scripts d'ARREL: que es puguen executar.

L'auditoria (18-10-2026) va trobar dos scripts d'arrel que PETAVEN de bon
començament i que cap test mirava:

- `wav_a_wavs.py`: feia `import pipeline` amb `app/` al `sys.path` → petava amb
  «attempted relative import with no known parent package» (el mòdul viu dins el
  paquet `app` des del refactor).
- `acords_a_live.py` sense arguments: `IndexError`.

Aquests guards són barats (una execució amb `--help` o sense arguments) i
haurien atrapat tots dos.
"""
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene dels tests: l'import té efecte (esborra els temporals en plegar)

from app import plataforma  # noqa: E402

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _corre(script, *args, timeout=60):
    return subprocess.run([plataforma.python_actual(),
                           os.path.join(ARREL, script), *args],
                          capture_output=True, text=True, timeout=timeout,
                          cwd=ARREL)


class TestScriptsArrelSmoke(unittest.TestCase):

    def test_wav_a_wavs_arranca(self):
        """`--help` ha de funcionar: si l'import està trencat, peta (codi 1)."""
        p = _corre("wav_a_wavs.py", "--help")
        self.assertEqual(p.returncode, 0, f"wav_a_wavs.py --help peta:\n"
                                          f"{p.stderr[-400:]}")
        self.assertIn("wav", p.stdout.lower())
        p2 = _corre("wav_a_wavs.py")
        self.assertNotEqual(p2.returncode, 0)
        self.assertNotIn("Traceback", p2.stderr, "ha de dir l'ús, no petar")

    def test_baixa_verificat_valida_abans_de_baixar(self):
        """Ha de rebutjar el SHA mal format i l'HTTP ABANS de tocar la xarxa."""
        p = _corre("eines/baixa_verificat.py", "https://ex.invalid/x", "zzz",
                   "/tmp/f.bin")
        self.assertEqual(p.returncode, 2)
        self.assertIn("64 car", p.stderr)
        p2 = _corre("eines/baixa_verificat.py", "http://ex.invalid/x", "-",
                    "/tmp/f.bin")
        self.assertNotEqual(p2.returncode, 0)
        self.assertIn("HTTPS", p2.stdout + p2.stderr)
        self.assertNotIn("Traceback", p2.stderr)

    def test_notes_release_vol_una_versio(self):
        """`--fitxer` no ha de confondre el seu VALOR amb la versio (abans
        `notes_release.py --fitxer out.md` feia servir «out.md» com a versio)."""
        p = _corre("eines/notes_release.py", "--fitxer", "/tmp/x.md")
        self.assertEqual(p.returncode, 2)
        self.assertIn("Ús:", p.stderr)
        p2 = _corre("eines/notes_release.py", "")
        self.assertEqual(p2.returncode, 2)
        p3 = _corre("eines/notes_release.py", "v0.0.0")
        self.assertEqual(p3.returncode, 0, p3.stderr[-200:])

    def test_acords_a_live_diu_l_us(self):
        p = _corre("acords_a_live.py")
        self.assertEqual(p.returncode, 2)
        self.assertIn("Ús:", p.stderr)
        self.assertNotIn("Traceback", p.stderr)

    def test_explica_bpm_diu_l_us(self):
        p = _corre("eines/explica_bpm.py")
        self.assertNotEqual(p.returncode, 0)
        self.assertNotIn("Traceback", p.stderr,
                         "ha de dir què falta, no petar amb IndexError")

    def test_ordre_aleatori_llista(self):
        """L'eina d'ordre aleatori ha de poder llistar sense executar res."""
        p = _corre("eines/ordre_aleatori.py", "3", "--llista", timeout=180)
        self.assertEqual(p.returncode, 0, p.stderr[-300:])
        self.assertIn("seed=3", p.stdout)
        self.assertIn("tests en ordre aleatori", p.stdout)

    def test_dev_reload_arranca(self):
        p = _corre("dev_reload.py", "--help")
        self.assertEqual(p.returncode, 0, p.stderr[-300:])
        self.assertIn("usage", p.stdout.lower())


class TestScriptsShSintaxi(unittest.TestCase):
    """`bash -n` de TOTS els scripts de shell del projecte.

    Una errada de sintaxi en un `.sh` no peta enlloc fins que el CI (o
    l'operador) el llança — i aleshores el build sencer cau. És una comprovació
    de mil·lisegons que estalvia una tongada de CI (auditoria 18-10-2026; els
    12 scripts estaven bé).
    """

    def test_la_sintaxi_dels_scripts(self):
        import glob
        import shutil
        if not shutil.which("bash"):
            self.skipTest("sense bash (p. ex. un runner sense MSYS2)")
        scripts = sorted(glob.glob(os.path.join(ARREL, "*.sh"))
                         + glob.glob(os.path.join(ARREL, "eines", "*.sh")))
        self.assertGreaterEqual(len(scripts), 5, "no he trobat els scripts")
        for s in scripts:
            p = subprocess.run(["bash", "-n", s], capture_output=True,
                               text=True, timeout=60)
            self.assertEqual(p.returncode, 0,
                             f"sintaxi de {os.path.basename(s)}:\n{p.stderr}")


if __name__ == "__main__":
    unittest.main()
