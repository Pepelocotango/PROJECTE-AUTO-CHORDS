"""El fil d'anàlisi (`main.Feina`) — propagació d'errors i èxit.

`Feina` és el fil que llança «Executa»: fa l'anàlisi i avisa per senyals
(`progres`, `missatge`, `feta`). Cap test el tocava (auditoria 18-10-2026), i és
justament el punt on un error del pipeline ha d'arribar a la UI **sense penjar
la barra de progrés** ni deixar l'app mig engegada.

Es crida `run()` directament (al fil principal): determinista, sense curses.
"""
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene dels tests: l'import té efecte (esborra els temporals en plegar)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app import main as app_main  # noqa: E402
from app import pipeline  # noqa: E402


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = (app_main.QApplication.instance()
                    or app_main.QApplication([]))


def _wav(ruta, segons=3):
    import numpy as np
    sr = 44100
    n = int(sr * segons)
    t = np.arange(n) / sr
    x = (np.sin(2 * np.pi * 261.6 * t) * 6000).astype(np.int16)
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(x.tobytes())


class TestFilAnalisi(_Base):

    def test_error_de_l_analisi_arriba_a_feta_false(self):
        td = tempfile.mkdtemp()
        f = app_main.Feina(os.path.join(td, "no_existeix.wav"), td,
                           120.0, 4, 0.0, False)
        log, feta, prog = [], [], []
        f.missatge.connect(log.append)
        f.feta.connect(lambda ok, err: feta.append((ok, err)))
        f.progres.connect(prog.append)
        f.run()                       # al fil principal: determinista
        self.assertTrue(any("1/3" in m for m in log),
                        "l'analisi ha d'anar dient per on va (text)")

        self.assertEqual(len(feta), 1, "ha d'avisar UNA vegada")
        self.assertFalse(feta[0][0], "l'analisi ha fallat")
        self.assertTrue(feta[0][1], "ha de dir QUE ha fallat")
        self.assertTrue(any("ERROR" in m for m in log),
                        "l'error ha de quedar al log")
        # `Feina` no emet progrés numeric (a diferencia de `FeinaExporta`): el
        # que fa servir es el TEXT del registre («1/3…», «3/3…»).
        self.assertEqual(prog, [], "l'analisi no mou la barra per senyals")

    @unittest.skipUnless(pipeline.usa_host(),
                         "cal el host Vamp propi (vamp_host_local) compilat")
    def test_analisi_real_acaba_ok_i_deixa_els_csvs(self):
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "t.wav")
        _wav(wav)
        sortida = os.path.join(td, "AUTOCHORDS_t")
        f = app_main.Feina(wav, sortida, 120.0, 4, 0.0, False)
        feta, prog = [], []
        f.feta.connect(lambda ok, err: feta.append((ok, err)))
        f.progres.connect(prog.append)
        f.run()

        self.assertEqual(len(feta), 1)
        self.assertTrue(feta[0][0], f"hauria d'acabar be: {feta[0][1]}")
        self.assertEqual(prog[-1], 100, "la barra ha d'arribar al 100")
        self.assertTrue(os.path.isfile(os.path.join(sortida, "acords.csv")),
                        "l'analisi ha de deixar acords.csv")
        # La CAPA CRUA es desa apart (evidència de l'anàlisi, no es toca mai).
        ana = pipeline.carpeta_analisi(sortida)
        self.assertTrue(os.path.isdir(ana), "ha de crear la carpeta d'analisi")


if __name__ == "__main__":
    unittest.main()
