"""Validació — exportació: límits (0 wavs), fusió d'iguals, capçalera «N» i
retall al final. Mode Lliure (`tempo_fix=False`) per no dependre d'scripts.

NOTA (a revisar amb l'operador): l'export aplica `style()` al nom del fitxer, de
manera que el nom del WAV pot DIFERIR del nom al CSV (`Am` → `A-.wav`). El test
`test_nom_wav_usa_style` ho DOCUMENTA (no és una afirmació que sigui el desitjat).
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene dels tests: l'import té efecte (esborra els temporals en plegar)

from app import pipeline  # noqa: E402


def _export(acords, total_s):
    td = tempfile.mkdtemp()
    ca = os.path.join(td, "acords.csv")
    out = os.path.join(td, "out")
    r = pipeline.exporta_total(
        csv_ac=ca, csv_seg=None, sortida=out, bpm=120.0, bpb=4, offset=0.0,
        sr=44100, log=lambda *_: None, tempo_fix=False, amb_estructura=False,
        total_s=total_s, acords=acords, seccions=None)
    dest = os.path.join(out, "wavs_acords")
    wavs = sorted(os.listdir(dest)) if os.path.isdir(dest) else []
    return ca, wavs, r


class TestExportLimits(unittest.TestCase):
    def test_tot_N_zero_wavs(self):
        _ca, wavs, r = _export([(0.0, "N", "0")], 5.0)
        self.assertEqual(wavs, [])
        self.assertEqual(r["n_acords_wavs"], 0)

    def test_csv_buit_zero_wavs(self):
        _ca, wavs, r = _export([], 5.0)
        self.assertEqual(wavs, [])
        self.assertEqual(r["n_acords_wavs"], 0)

    def test_fusiona_acords_iguals_seguits(self):
        _ca, wavs, r = _export([(0.0, "C", "0"), (2.0, "C", "2"), (4.0, "G", "4")],
                               8.0)
        self.assertEqual(len(wavs), 2)               # C 0-4 · G 4-8
        self.assertTrue(any("_C.wav" in w for w in wavs))
        self.assertTrue(any("_G.wav" in w for w in wavs))

    def test_capcalera_N_produeix_wav(self):
        _ca, wavs, r = _export([(0.5, "C", "0.5")], 3.0)
        self.assertEqual(len(wavs), 2)               # N 0-0.5 · C 0.5-3
        self.assertTrue(any("_N.wav" in w for w in wavs))

    def test_retalla_al_final(self):
        _ca, wavs, r = _export([(0.0, "C", "0")], 3.0)
        self.assertEqual(len(wavs), 1)
        self.assertIn("0000.00s_0003.00s", wavs[0])  # fi = durada de la WAV

    def test_nom_wav_usa_style(self):
        """DOCUMENTA: l'export estilitza el nom → pot diferir del CSV."""
        ca, wavs, r = _export([(0.0, "Am", "0"), (2.0, "Cmaj7", "2")], 4.0)
        self.assertTrue(any("A-.wav" in w for w in wavs),
                        f"l'export estilitza (Am→A-): {wavs}")
        with open(ca, encoding="utf-8") as f:
            self.assertIn("Am", f.read())


if __name__ == "__main__":
    unittest.main()
