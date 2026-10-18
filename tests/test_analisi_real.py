"""ANÀLISI REAL (motor Vamp) de cap a cap — el nucli de l'app.

La resta de la suite **sempre mockeja** `pipeline.extract_chords` /
`pipeline.executa_transform`: per velocitat i per no dependre dels plugins. El
resultat era que el **nucli de l'app** (treure els acords d'una WAV) no
s'executava mai de veritat als tests (auditoria 18-10-2026: forat trobat amb el
mateix patró que el de la guia DAW de la Ronda 20).

Aquest fitxer corre el **host Vamp de debò** sobre un WAV sintètic (tres triades)
i comprova que el pipeline dels transforms funciona: arrenca, desa el CSV amb el
format esperat i hi ha **almenys un acord de veritat** (no tot «N»).

Si el host o els plugins no hi són (p. ex. un CI abans de compilar-los), els
tests se **salten** netament en comptes de fallar.
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


def _wav_triades(ruta, sr=44100):
    import wave

    import numpy as np
    def acord(fs, dur=2.6):
        n = int(sr * dur)
        t = np.arange(n) / sr
        return (sum(np.sin(2 * np.pi * f * t) for f in fs) * 6000 / len(fs)
                ).astype(np.int16)
    x = np.concatenate([acord([261.6, 329.6, 392.0]),    # C
                        acord([349.2, 440.0, 523.3]),    # F
                        acord([392.0, 493.9, 587.3])])   # G
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(x.tobytes())


@unittest.skipUnless(pipeline.usa_host(),
                     "cal el host Vamp propi (vamp_host_local) compilat")
class TestAnalisiReal(unittest.TestCase):

    def test_el_motor_treu_acords_de_veritat(self):
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "triades.wav")
        _wav_triades(wav)
        out = os.path.join(td, "acords.csv")
        pipeline.executa_transform(pipeline.TRANSFORMS["chords"], out, wav,
                                   lambda *a: None)
        self.assertTrue(os.path.isfile(out), "ha de generar el CSV")
        with open(out, encoding="utf-8") as f:
            files = [ln.strip() for ln in f if ln.strip()]
        self.assertTrue(files, "el CSV no pot ser buit")
        camps = [ln.split(",") for ln in files]
        temps = []
        for c in camps:
            self.assertEqual(len(c), 2, f"format inesperat: {c!r}")
            temps.append(float(c[0]))
        self.assertEqual(temps, sorted(temps), "els temps han d'anar en ordre")
        noms = [c[1].strip().strip('"') for c in camps]
        self.assertTrue([n for n in noms if n and n != "N"],
                        f"cap acord detectat de veritat: {noms}")

    def test_el_ttl_temporal_no_queda_enrere(self):
        """Els `.ttl` temporals de la crida s'esborren en acabar."""
        import glob
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "triades.wav")
        _wav_triades(wav)
        abans = set(glob.glob(os.path.join(tempfile.gettempdir(), "ac_ttl_*")))
        pipeline.executa_transform(
            pipeline.TRANSFORMS["chords"], os.path.join(td, "o.csv"), wav,
            lambda *a: None, params={"smoothing": 0.5})
        despres = set(glob.glob(os.path.join(tempfile.gettempdir(), "ac_ttl_*")))
        self.assertEqual(despres - abans, set(),
                         "no ha de deixar directoris ac_ttl_ orfes")


if __name__ == "__main__":
    unittest.main()
