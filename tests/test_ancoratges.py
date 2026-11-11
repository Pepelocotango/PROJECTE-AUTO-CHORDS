"""Suite de test — Marcadors humans i velocitat de reproducció.

Cobreix `app/marcadors.py` (afegir, eliminar, normalitzar i desar) i les
utilitats d'àudio de `app/ffmpeg.py` que fa servir el transport.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene: esborra els temporals en plegar

import unittest

import math
import struct
import tempfile
import wave

from app import ffmpeg
from app import marcadors as M
from app import pipeline
import shutil


class TestMarcadors(unittest.TestCase):
    """Marcadors humans: llista ordenada, alta/baixa i rebot de la tecla."""

    def test_afegeix_ordena_i_descarta_rebots(self):
        m = M.afegeix([], 2.0, 60.0)
        self.assertEqual(m, [2.0])
        m = M.afegeix(m, 1.0, 60.0)
        self.assertEqual(m, [1.0, 2.0])
        m2 = M.afegeix(m, 2.02, 60.0)          # rebot (< 50 ms)
        self.assertEqual(m2, m)
        self.assertEqual(M.afegeix(m, 0.0, 60.0), m)      # fora (inici)
        self.assertEqual(M.afegeix(m, 60.0, 60.0), m)     # fora (final)

    def test_elimina_i_consultes(self):
        m = [1.0, 4.0, 9.0]
        self.assertEqual(M.elimina(m, 1), [1.0, 9.0])
        self.assertEqual(M.elimina(m, 9), m)             # índex inexistent
        self.assertEqual(M.index_a(m, 4.05), 1)
        self.assertIsNone(M.index_a(m, 6.0))
        self.assertEqual(M.seguent(m, 2.0), 4.0)
        self.assertEqual(M.anterior(m, 5.0), 4.0)
        self.assertIsNone(M.seguent(m, 9.0))

    def test_normalitza_treu_duplicats(self):
        self.assertEqual(M.normalitza_marcadors([3, 1.0, 1.0000001, 2], 10),
                         [1.0, 2.0, 3.0])

    def test_desa_i_llegeix_al_projecte(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        ruta = pipeline.desa_marcadors(d, [1.5, 4.25])
        self.assertTrue(os.path.exists(ruta))
        self.assertEqual(pipeline.llegeix_marcadors(d, 60.0), [1.5, 4.25])
        self.assertEqual(pipeline.llegeix_marcadors(tempfile.mkdtemp(), 60.0), [])


def _wav_sine(ruta, segons=1.0, sr=44100):
    """WAV PCM 16 mono amb una sinusoide de 440 Hz."""
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        n = int(sr * segons)
        dades = b"".join(
            struct.pack("<h", int(12000 * math.sin(2 * math.pi * 440 * i / sr)))
            for i in range(n))
        w.writeframes(dades)
    return ruta


def _durada_wav(ruta):
    with wave.open(ruta, "rb") as w:
        return w.getnframes() / float(w.getframerate())


class TestVelocitat(unittest.TestCase):
    """F2 / R11: estirament amb el to mantingut i relació de temps."""

    def test_cadena_atempo(self):
        self.assertEqual(ffmpeg.cadena_atempo(0.5), "atempo=0.500000")
        self.assertEqual(ffmpeg.cadena_atempo(2.0), "atempo=2.000000")
        self.assertEqual(ffmpeg.cadena_atempo(4.0),
                         "atempo=2.0,atempo=2.000000")
        self.assertEqual(ffmpeg.cadena_atempo(1.0), "atempo=1.000000")
        with self.assertRaises(ValueError):
            ffmpeg.cadena_atempo(0)

    def test_prepara_escolta_1_5_escurca(self):
        if not ffmpeg.disponible():
            self.skipTest("ffmpeg no disponible")
        d = tempfile.mkdtemp()
        ruta = _wav_sine(os.path.join(d, "a.wav"), segons=3.0)
        dest = ffmpeg.prepara_escolta(ruta, 1.5, carpeta=d)
        self.assertAlmostEqual(_durada_wav(dest), 3.0 / 1.5, places=2)

    def test_prepara_escolta_mono_1x_no_renderitza(self):
        d = tempfile.mkdtemp()
        ruta = _wav_sine(os.path.join(d, "a.wav"))       # mono PCM16
        self.assertEqual(ffmpeg.prepara_escolta(ruta, 1.0), ruta)

    def test_prepara_escolta_estereo_sempre_mono(self):
        """El WAV de l'usuari sol ser ESTÈREO: el transport necessita mono."""
        if not ffmpeg.disponible():
            self.skipTest("ffmpeg no disponible")
        d = tempfile.mkdtemp()
        ruta = os.path.join(d, "estereo.wav")
        with wave.open(ruta, "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(8000)
            w.writeframes(b"\x00\x00\x00\x00" * 8000)   # 1 s
        dest = ffmpeg.prepara_escolta(ruta, 1.0, carpeta=d)
        self.assertNotEqual(dest, ruta)
        with wave.open(dest, "rb") as w:
            self.assertEqual(w.getnchannels(), 1)
            self.assertEqual(w.getsampwidth(), 2)
            self.assertAlmostEqual(w.getnframes() / 8000.0, 1.0, places=2)

    def test_ruta_velocitat_determinista(self):
        d = tempfile.mkdtemp()
        ruta = _wav_sine(os.path.join(d, "a.wav"))
        r1 = ffmpeg.ruta_velocitat(ruta, 0.5, d)
        r2 = ffmpeg.ruta_velocitat(ruta, 0.5, d)
        r3 = ffmpeg.ruta_velocitat(ruta, 2.0, d)
        self.assertEqual(r1, r2)
        self.assertNotEqual(r1, r3)
        self.assertTrue(os.path.basename(r1).startswith(ffmpeg.PREFIX_VELOCITAT))
        self.assertTrue(r1.endswith(".wav"))

if __name__ == "__main__":
    unittest.main()
