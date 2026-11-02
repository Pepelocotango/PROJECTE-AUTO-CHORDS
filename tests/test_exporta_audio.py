"""Tests de l'exportació de la còpia de treball (Fase 6)."""
import os
import subprocess
import sys
import tempfile
import unittest
import wave
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals

from app import exporta_audio  # noqa: E402
from app import ffmpeg  # noqa: E402


def _wav(ruta, segons=0.2, sr=44100):
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"\x00\x00" * int(sr * segons))


class TestEncoders(unittest.TestCase):
    def test_parseja_la_llista_d_encoders(self):
        sortida = (
            " Encoders:\n"
            " A....D aac                  AAC (Advanced Audio Coding)\n"
            " V..... libx264              libx264 H.264\n"
            " A....D libmp3lame           libmp3lame MP3\n")
        p = subprocess.CompletedProcess([], 0, sortida, "")
        with patch.object(ffmpeg.subprocess, "run", return_value=p):
            self.assertEqual(ffmpeg.encoders(), {"aac", "libmp3lame"})

    def test_comanda_exporta(self):
        cmd = ffmpeg.comanda_exporta(
            "entrada.wav", "sortida.mp3", "libmp3lame", ("-b:a", "192k"))
        self.assertIn("-vn", cmd)
        self.assertEqual(cmd[cmd.index("-c:a") + 1], "libmp3lame")
        self.assertEqual(cmd[-3:-1], ["-b:a", "192k"])
        self.assertTrue(cmd[-1].endswith("sortida.mp3"))


class TestPerfils(unittest.TestCase):
    def test_nomes_els_encoders_disponibles(self):
        perfils = exporta_audio.perfils_disponibles(
            {"pcm_s16le", "libmp3lame"})
        ext = {p["ext"] for p in perfils}
        self.assertIn("wav", ext)
        self.assertIn("mp3", ext)
        self.assertNotIn("flac", ext)
        wavs = [p for p in perfils if p["ext"] == "wav"]
        self.assertTrue(wavs)
        self.assertTrue(all(p["codec"] == "pcm_s16le" for p in wavs))

    def test_sense_encoders_no_ofereix_res(self):
        self.assertEqual(exporta_audio.perfils_disponibles(set()), [])

    def test_filtre_i_perfil(self):
        perfils = exporta_audio.perfils_disponibles({"pcm_s16le"})
        p = perfils[0]
        self.assertIn(p["etiqueta"], exporta_audio.filtre(p))
        self.assertIn("(*.wav)", exporta_audio.filtre(p))
        self.assertEqual(
            exporta_audio.perfil_de_filtre(exporta_audio.filtre(p), perfils),
            p)
        self.assertIsNone(exporta_audio.perfil_de_filtre("Res", perfils))


class TestExporta(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.origen = os.path.join(self.td, "tema.wav")
        _wav(self.origen)

    def _perfil(self, id_perfil="wav16_origen"):
        for p in exporta_audio.perfils_disponibles():
            if p["id"] == id_perfil:
                return p
        self.skipTest(f"el perfil {id_perfil} no és disponible")

    def test_rebutja_exportar_sobre_el_mateix_fitxer(self):
        p = self._perfil()
        with self.assertRaises(ValueError):
            exporta_audio.exporta(self.origen, self.origen, p)

    def test_rebutja_extensio_que_no_toca(self):
        p = self._perfil()
        desti = os.path.join(self.td, "sortida.mp3")
        with self.assertRaises(ValueError):
            exporta_audio.exporta(self.origen, desti, p)

    def test_rebutja_codec_absent(self):
        p = {"id": "x", "etiqueta": "Inventat", "ext": "wav",
             "codec": "pcm_s16le", "args": ()}
        with patch.object(ffmpeg, "encoders", return_value=set()):
            with self.assertRaises(ValueError):
                exporta_audio.exporta(
                    self.origen, os.path.join(self.td, "x.wav"), p)

    def test_error_no_deixa_temporal_ni_desti(self):
        p = {"id": "x", "etiqueta": "WAV", "ext": "wav",
             "codec": "pcm_s16le", "args": ()}
        desti = os.path.join(self.td, "fallida.wav")
        fallada = subprocess.CompletedProcess([], 1, "", "error de prova")
        with patch.object(ffmpeg, "encoders", return_value={"pcm_s16le"}), \
                patch.object(ffmpeg, "_executa", return_value=fallada):
            with self.assertRaises(RuntimeError):
                exporta_audio.exporta(self.origen, desti, p)
        self.assertFalse(os.path.exists(desti))
        self.assertEqual(
            [n for n in os.listdir(self.td)
             if n.startswith(".auto-chords-export-")], [])

    @unittest.skipUnless(ffmpeg.disponible(), "ffmpeg no disponible")
    def test_exporta_wav_de_veritat(self):
        p = self._perfil("wav16_441")
        desti = os.path.join(self.td, "sortida.wav")
        exporta_audio.exporta(self.origen, desti, p)
        with wave.open(desti, "rb") as w:
            self.assertEqual(w.getframerate(), 44100)
            self.assertGreater(w.getnframes(), 0)

    @unittest.skipUnless(ffmpeg.disponible(), "ffmpeg no disponible")
    def test_exporta_mp3_de_veritat(self):
        p = self._perfil("mp3_192")
        desti = os.path.join(self.td, "sortida.mp3")
        exporta_audio.exporta(self.origen, desti, p)
        self.assertGreater(os.path.getsize(desti), 500)


if __name__ == "__main__":      # pragma: no cover
    unittest.main()
