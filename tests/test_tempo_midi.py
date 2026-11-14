"""Exportació del mapa de tempo/compàs a MIDI (pista de conductor)."""
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app import mapa_tempo, pipeline, tempo_midi  # noqa: E402


class TestTempoMidi(unittest.TestCase):
    def test_genera_i_llegeix_tempo_timesig_markers(self):
        trams = [
            mapa_tempo.TramMapa(0.0, 4.0, 120.0, "normal", "4/4"),
            mapa_tempo.TramMapa(4.0, 8.0, 60.0, "normal", "6/8",
                                beat_unit="negra_punt"),
        ]
        ruta = os.path.join(tempfile.mkdtemp(), tempo_midi.NOM_MAPA_MIDI)
        tempo_midi.desa_mapa_midi(
            ruta, trams, offset=0.5,
            marques=[(1.0, "seccio"), 6.0])
        info = tempo_midi.llegeix_mapa_midi(ruta)
        self.assertEqual(info["format"], 1)
        self.assertEqual(info["n_tracks"], 1)
        self.assertEqual(info["ppq"], tempo_midi.PPQ)
        self.assertEqual(
            [(e["tick"], round(e["bpm"], 6)) for e in info["tempo"]],
            [(0, 120.0), (3840, 60.0), (5760, 60.0)])
        self.assertEqual(
            [(e["tick"], e["num"], e["den"]) for e in info["timesig"]],
            [(0, 4, 4), (3840, 6, 8)])
        self.assertEqual(
            [(e["cc"], e["bb"]) for e in info["timesig"]],
            [(24, 8), (36, 8)])
        textos = [e["text"] for e in info["markers"]]
        self.assertIn("Tram 1 · 4/4", textos)
        self.assertIn("Tram 2 · 6/8", textos)
        self.assertIn("Anacrusi: 0.500000 s", textos)
        self.assertIn("Secció", textos)
        self.assertIn("Marcador", textos)
        self.assertNotIn("Fi", textos)
        ticks = {e["text"]: e["tick"] for e in info["markers"]
                 if e["text"] in ("Secció", "Marcador")}
        self.assertEqual(ticks["Secció"], 960)
        self.assertEqual(ticks["Marcador"], 4800)
        self.assertEqual(info["tempo"][-1]["tick"], info["end_tick"])
        self.assertAlmostEqual(
            tempo_midi.tick_a_segons(info, 3840), 4.0, places=6)
        self.assertAlmostEqual(
            tempo_midi.tick_a_segons(info, 4800), 6.0, places=6)
        self.assertAlmostEqual(
            tempo_midi.tick_a_segons(info, info["end_tick"]), 8.0, places=6)

    def test_exporta_total_inclou_mapa_midi(self):
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "tema.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * 2)
        csv_ac = os.path.join(td, "acords.csv")
        pipeline.desa_acords_csv(csv_ac, [pipeline.Clip(0.0, 2.0, "C")], 2.0)
        trams = [mapa_tempo.TramMapa(0.0, 2.0, 120.0, "normal", "4/4")]
        res = pipeline.exporta_total(
            csv_ac=csv_ac, csv_seg=None, sortida=td, bpm=120.0, bpb=4,
            offset=0.0, sr=44100, log=lambda *_a: None, tempo_fix=True,
            amb_estructura=False, total_s=2.0,
            acords=[pipeline.Clip(0.0, 2.0, "C")], seccions=[],
            mapa_tempo=trams, marques=[0.5])
        ruta = res["mapa_tempo_midi"]
        self.assertTrue(os.path.isfile(ruta))
        self.assertEqual(os.path.dirname(ruta),
                         os.path.join(td, "mapa_tempo"))
        info = tempo_midi.llegeix_mapa_midi(ruta)
        self.assertIn("Marcador", [m["text"] for m in info["markers"]])
        self.assertAlmostEqual(
            tempo_midi.tick_a_segons(info, info["end_tick"]), 2.0, places=6)

    def test_mapa_buit_es_rebutja(self):
        ruta = os.path.join(tempfile.mkdtemp(), "buit.mid")
        with self.assertRaises(ValueError):
            tempo_midi.desa_mapa_midi(ruta, [])


if __name__ == "__main__":
    unittest.main()
