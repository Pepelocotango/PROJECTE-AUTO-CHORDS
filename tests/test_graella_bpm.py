"""Validació: mode fàcil / graella amb BPM extrems i modes rars.

Rangs de l'app: BPM 30–400 (`_bpm_val`), compàs bpb 1–12, offset 0–60. Comprova
que la «matemàtica» de la graella i el mode fàcil no es trenquen als extrems i
que, sobretot, la COBERTURA (regla #4) es manté.
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
from app import graella  # noqa: E402
from app import pipeline  # noqa: E402
from app import visor as visor_mod  # noqa: E402


class TestGraellaBpmExtrems(unittest.TestCase):
    def test_nivell_segons_rangs(self):
        self.assertAlmostEqual(graella.nivell_segons("compas", 30, 4), 8.0)
        self.assertAlmostEqual(graella.nivell_segons("compas", 400, 4), 0.6)
        self.assertAlmostEqual(graella.nivell_segons("compas", 120, 1), 0.5)
        self.assertAlmostEqual(graella.nivell_segons("compas", 120, 12), 6.0)
        self.assertAlmostEqual(graella.nivell_segons("mig", 120, 12), 3.0)

    def test_regularitza_bpm_extrem(self):
        # bpm 30 → compàs 8 s: 20 s → cel·les a 0, 8, 16
        cru = [(0.1, "C"), (8.1, "G"), (16.2, "Am")]
        res = graella.regularitza_acords(cru, 30, 4, 0.0, "compas", 20.0)
        self.assertEqual([round(t, 3) for t, _n in res], [0.0, 8.0, 16.0])

    def test_guards_bpm_zero(self):
        self.assertEqual(graella.nivell_segons("compas", 0, 4), 0.0)
        self.assertEqual(graella.divisio_segons("corxera", 0, True), 0.0)
        self.assertAlmostEqual(graella.snap_a_nivell(2.1, "compas", 0, 4), 2.1)
        cru = [(0.0, "C"), (2.0, "G")]
        # sense BPM no es pot encaixar → es retorna el cru tal qual
        self.assertEqual(
            graella.regularitza_acords(cru, 0, 4, 0.0, "compas", 8.0), cru)
        self.assertEqual(graella.infereix_nivell(cru, 0, 4, 0.0, 8.0), "temps")

    def test_infereix_nivell_bpm_extrem(self):
        # canvis cada 8 s amb bpm 30 (compàs 8 s) → "compas"
        cru = [(0.0, "C"), (8.0, "G"), (16.0, "Am")]
        self.assertEqual(graella.infereix_nivell(cru, 30, 4, 0.0, 24.0),
                         "compas")


def _model_csv(cru):
    """Cru `t,acord` -> format del MODEL `inici,fi,acord` (S3)."""
    files = [ln for ln in cru.strip().splitlines() if ln.strip()]
    ts = [float(ln.split(",")[0]) for ln in files]
    out = []
    for i, ln in enumerate(files):
        t, nom = ln.split(",", 1)
        fi = ts[i + 1] if i + 1 < len(ts) else ts[-1] + 1.0
        out.append(f"{t},{fi},{nom}")
    return "\n".join(out) + "\n"


def _visor(bpm, bpb, tempo_fix, acords, durada):
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "tema.wav")
    out = os.path.join(td, "AUTOCHORDS_tema")
    os.makedirs(out)
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * int(44100 * durada))
    ca = os.path.join(out, "acords.csv")
    with open(ca, "w", encoding="utf-8") as f:
        f.write(_model_csv(acords))
    v = visor_mod.Visor(wav, ca, None, bpm=bpm, bpb=bpb, tempo_fix=tempo_fix)
    v.td, v.sortida = td, out
    # capa crua
    ana = pipeline.carpeta_analisi(out)
    os.makedirs(ana, exist_ok=True)
    with open(os.path.join(ana, pipeline.NOM_CRU_ACORDS), "w",
              encoding="utf-8") as f:
        f.write(acords)
    return v


class TestModeFacilBpmExtrem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = visor_mod.QApplication.instance() or visor_mod.QApplication([])

    def _check_cobertura(self, v):
        self.assertAlmostEqual(float(v.acords[0][0]), 0.0, places=6)
        if v.seccions:
            self.assertAlmostEqual(float(v.seccions[0][0]), 0.0, places=6)
            self.assertAlmostEqual(float(v.seccions[-1][1]),
                                   float(v.audio["durada"]), places=2)

    def test_mode_facil_bpm_baix(self):
        cru = "0.1,C\n8.1,G\n16.2,Am\n"
        v = _visor(30, 4, True, cru, 24.0)
        n = v.regularitza_des_de_cru("compas", modul_compassos=4)
        self.assertGreater(n, 0)
        self._check_cobertura(v)
        v.close()

    def test_mode_facil_bpm_alt(self):
        cru = "0.1,C\n0.7,G\n1.3,Am\n1.9,F\n"
        v = _visor(400, 4, True, cru, 5.0)
        n = v.regularitza_des_de_cru("compas", modul_compassos=4)
        self.assertGreater(n, 0)
        self._check_cobertura(v)
        v.close()

    def test_mode_facil_amb_offset(self):
        cru = "0.6,C\n1.1,G\n1.6,Am\n"
        v = _visor(120, 4, True, cru, 6.0)
        v.offset = 0.15                      # el compàs 1 cau a 0,15 s
        n = v.regularitza_des_de_cru("temps")
        self.assertGreater(n, 0)
        self._check_cobertura(v)
        v.close()


def tearDownModule():
    try:
        import _qt_neteja
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()


if __name__ == "__main__":
    unittest.main()
