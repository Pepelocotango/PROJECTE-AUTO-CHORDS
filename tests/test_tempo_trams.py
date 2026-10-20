"""Motor de tempo per trams (app/tempo.py): candidats, beats i mapa.

Cobreix el que fa possible l'acció «Detecta el tempo per trams»:
  - alternatives amb fiabilitat (com Logic) i avís de rang estret,
  - beat tracking per DP sobre clics sintètics,
  - mapa de BPM cada N compassos que **compleix el contracte** de la graella
    (`tempo_map.valida_i_normalitza_compassos`) i que segueix canvis de tempo,
  - pistes de tempo dels metadades (chunk ACID / nom del fitxer).
"""
import os
import struct
import sys
import tempfile
import unittest
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals     # higiene: esborra els temporals en plegar

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app import tempo, tempo_map  # noqa: E402

SR = 22050


def wav_clics(td, bpm, dur=20.0, silenci_ini=2.0, nom="clics.wav",
              canvi=None):
    """WAV de clics periòdics; `canvi=(t, bpm2)` canvia el tempo a mitges."""
    n = int(SR * dur)
    a = np.zeros(n, dtype=np.int16)
    llarg = int(SR * 0.02)
    base = np.exp(-8.0 * np.arange(llarg) / llarg).astype(np.float32)

    def _clic(t):
        i = int(t * SR)
        if i + llarg >= n:
            return
        to = np.sin(2 * np.pi * 1000 * np.arange(llarg) / SR) * base * 12000
        a[i:i + llarg] = np.clip(a[i:i + llarg] + to.astype(np.int16),
                                 -32768, 32767)

    t = silenci_ini
    while t < dur - 0.05:
        _clic(t)
        ara = bpm if (canvi is None or t < canvi[0]) else canvi[1]
        t += 60.0 / ara
    ruta = os.path.join(td, nom)
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(a.tobytes())
    return ruta


class CandidatsTests(unittest.TestCase):
    """Alternatives amb fiabilitat + detecció de tempo fora del rang."""

    def test_candidats_normalitzats(self):
        with tempfile.TemporaryDirectory() as td:
            ruta = wav_clics(td, 100.0, 24.0)
            cands = tempo.candidats_bpm(
                tempo._envolupant_onsets(ruta)[0], 60, 180, None, n=4)
            self.assertTrue(cands)
            self.assertLess(abs(cands[0][0] - 100.0), 2.0, cands)
            self.assertAlmostEqual(cands[0][1], 1.0, places=6)
            for _bpm, conf in cands:
                self.assertLessEqual(conf, 1.0 + 1e-9)
            # cap candidat pot ser el mateix tempo que un altre (< 2 %)
            for i, (b1, _c) in enumerate(cands):
                for b2, _c2 in cands[i + 1:]:
                    self.assertGreater(abs(b1 - b2) / b2, 0.02)

    def test_alternatives_avisen_del_rang_estret(self):
        """Un tema de 120 mesurat amb un rang 50–100 ha d'avisar del 120."""
        with tempfile.TemporaryDirectory() as td:
            ruta = wav_clics(td, 120.0, 20.0)
            res = tempo.detecta_bpm_candidats(
                ruta, None, bpm_min=50, bpm_max=100, preferit=None)
            # dins del rang guanya la meitat (60)…
            self.assertLess(abs(res["bpm"] - 60.0), 2.0, res)
            # …i el 120 apareix com a alternativa fora del rang
            alts = [b for b, _c in res["alternatives"]]
            self.assertTrue(any(abs(b - 120.0) < 2.0 for b in alts), alts)

    def test_silenci_retorna_diccionari_buit(self):
        with tempfile.TemporaryDirectory() as td:
            ruta = os.path.join(td, "silenci.wav")
            with wave.open(ruta, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(SR)
                w.writeframes(b"\x00\x00" * SR)
            res = tempo.detecta_bpm_candidats(ruta, None)
            self.assertIsNone(res["bpm"])
            self.assertEqual(res["candidats"], [])


class SegueixBeatsTests(unittest.TestCase):
    """Beat tracking per DP: nombre, separació i offset."""

    def test_beats_en_clics(self):
        with tempfile.TemporaryDirectory() as td:
            ruta = wav_clics(td, 120.0, 20.0, silenci_ini=2.0)
            beats, base = tempo.segueix_beats(ruta, None)
            self.assertLess(abs(base - 120.0), 2.0, base)
            self.assertGreaterEqual(len(beats), 30)
            self.assertLessEqual(len(beats), 40)
            self.assertLess(abs(beats[0] - 2.0), 0.1, beats[:3])
            d = np.diff(beats)
            self.assertLess(d.min(), 0.55)
            self.assertGreater(d.max(), 0.45)
            self.assertAlmostEqual(float(np.median(d)), 0.5, delta=0.02)

    def test_envolupant_retorna_offset(self):
        with tempfile.TemporaryDirectory() as td:
            ruta = wav_clics(td, 100.0, 10.0, silenci_ini=3.0)
            env, _sr, t0 = tempo._envolupant_onsets(ruta, retorna_offset=True)
            self.assertGreater(env.size, 0)
            self.assertLess(abs(t0 - 3.0), 0.15, t0)

    def test_silenci_no_dona_beats(self):
        with tempfile.TemporaryDirectory() as td:
            ruta = os.path.join(td, "silenci.wav")
            with wave.open(ruta, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(SR)
                w.writeframes(b"\x00\x00" * SR)
            beats, base = tempo.segueix_beats(ruta, None)
            self.assertEqual(beats, [])
            self.assertIsNone(base)


class BeatsATramsTests(unittest.TestCase):
    """El mapa ha de complir el contracte de compassos enters SIEMPRE."""

    def _beats(self, bpm, dur, ini=0.0):
        return [round(ini + i * 60.0 / bpm, 6)
                for i in range(int((dur - ini) * bpm / 60.0) + 1)]

    def test_mapa_de_tempo_constant(self):
        beats = self._beats(120.0, 32.0, ini=1.0)
        trams, off = tempo.beats_a_trams(beats, 32.0)
        self.assertAlmostEqual(off, 1.0, places=6)
        self.assertTrue(trams)
        for t in trams:
            self.assertLess(abs(t[2] - 120.0), 2.0, t)
        # el contracte de la graella s'ha de complir
        val = tempo_map.valida_i_normalitza_compassos(trams, 32.0, offset=off)
        self.assertEqual(len(val), len(trams))

    def test_mapa_segueix_un_canvi_de_tempo(self):
        """100 BPM mitja cançó i 130 la resta → dos trams distints."""
        beats = self._beats(100.0, 20.0, ini=0.0)
        ultim = beats[-1]
        beats += [round(ultim + i * 60.0 / 130.0, 6)
                  for i in range(1, int(20.0 * 130.0 / 60.0) + 1)]
        trams, off = tempo.beats_a_trams(beats, 40.0, cada_compassos=4,
                                        tolerancia=0.02)
        self.assertGreaterEqual(len(trams), 2)
        self.assertLess(abs(trams[0][2] - 100.0), 3.0, trams)
        self.assertLess(abs(trams[1][2] - 130.0), 4.0, trams)
        tempo_map.valida_i_normalitza_compassos(trams, 40.0, offset=off)

    def test_offset_zero_no_mou_el_compas1(self):
        beats = self._beats(110.0, 24.0, ini=0.7)
        trams, off = tempo.beats_a_trams(beats, 24.0, offset=0.0)
        self.assertEqual(off, 0.0)
        self.assertEqual(trams[0][0], 0.0)
        tempo_map.valida_i_normalitza_compassos(trams, 24.0, offset=0.0)

    def test_massa_pocs_beats(self):
        trams, off = tempo.beats_a_trams([0.0, 0.5, 1.0], 10.0)
        self.assertEqual(trams, [])
        self.assertEqual(off, 0.0)

    def test_fusio_de_veins(self):
        """Amb jitter, sense tolerància ixen molts trams; amb 10 % se'n funden."""
        # clics amb ±10 ms de jitter (com un directe): cada bloc mesura un BPM
        # lleugerament diferent i, sense tolerància, no es fusionen
        beats = [round(1.0 + i * 0.5 + (0.01 if i % 2 else -0.01), 6)
                 for i in range(70)]
        molts, _o = tempo.beats_a_trams(beats, 36.0, tolerancia=0.0)
        pocs, _o = tempo.beats_a_trams(beats, 36.0, tolerancia=0.10)
        self.assertGreater(len(molts), 1, molts)
        self.assertLess(len(pocs), len(molts))
        self.assertEqual(len(pocs), 1, pocs)


class MapaAutomaticTests(unittest.TestCase):
    """De la WAV al mapa validat (motor complet)."""

    def test_mapa_sintetic(self):
        with tempfile.TemporaryDirectory() as td:
            ruta = wav_clics(td, 110.0, 30.0, silenci_ini=1.0)
            trams, off, base = tempo.mapa_tempo_automatic(
                ruta, None, durada=30.0, cada_compassos=4)
            self.assertTrue(trams)
            self.assertLess(abs(base - 110.0), 3.0, base)
            self.assertLess(abs(off - 1.0), 0.2, off)
            self.assertLess(abs(trams[0][2] - 110.0), 3.0, trams)
            tempo_map.valida_i_normalitza_compassos(trams, 30.0, offset=off)

    def test_mapa_en_dos_tempos(self):
        with tempfile.TemporaryDirectory() as td:
            ruta = wav_clics(td, 100.0, 40.0, silenci_ini=0.5,
                             canvi=(20.0, 132.0))
            trams, off, _base = tempo.mapa_tempo_automatic(
                ruta, None, durada=40.0, cada_compassos=4)
            self.assertGreaterEqual(len(trams), 2)
            self.assertLess(abs(trams[0][2] - 100.0), 4.0, trams)
            self.assertLess(abs(trams[1][2] - 132.0), 6.0, trams)
            tempo_map.valida_i_normalitza_compassos(trams, 40.0, offset=off)


class PistesTempoTests(unittest.TestCase):
    """BPM declarat al nom del fitxer o al chunk ACID."""

    def test_nom_del_fitxer(self):
        self.assertEqual(tempo.llegeix_pistes_tempo("/x/01 tema 103bpm.wav"),
                         [(103.0, "nom")])
        self.assertEqual(tempo.llegeix_pistes_tempo("/x/101 BPM pep.wav"),
                         [(101.0, "nom")])
        self.assertEqual(tempo.llegeix_pistes_tempo("/x/96,5bpm.wav"),
                         [(96.5, "nom")])
        self.assertEqual(tempo.llegeix_pistes_tempo("/x/tema.wav"), [])

    def test_chunk_acid(self):
        with tempfile.TemporaryDirectory() as td:
            ruta = os.path.join(td, "acid.wav")
            dades = b"\x00\x00" * SR
            acid = struct.pack("<i", 1) + b"\x00" * 12 + struct.pack("<f", 118.0) \
                + b"\x00" * 4
            with wave.open(ruta, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(SR)
                w.writeframes(dades)
            # afig el chunk ACID dins el RIFF (abans de tancar el fitxer)
            with open(ruta, "rb") as f:
                raw = f.read()
            cos = raw[12:] + b"acid" + struct.pack("<I", len(acid)) + acid
            with open(ruta, "wb") as f:
                f.write(b"RIFF" + struct.pack("<I", len(cos)) + b"WAVE" + cos)
            pistes = tempo.llegeix_pistes_tempo(ruta)
            self.assertIn((118.0, "acid"), pistes, pistes)


if __name__ == "__main__":
    unittest.main()
