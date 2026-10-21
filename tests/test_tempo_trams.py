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


class RetempoTests(unittest.TestCase):
    """Re-tempo pel ratolí (docs/FLUX DE TEMPO VARIABLE.md).

    Llei de fons: el **ratolí** fixa Δt, el nombre de compassos N de cada tram
    es conserva i el **BPM** es recalcula. Contrari del flux vell (snap a la
    línia de compàs), on qui manava era el validador i el punter es descartava.
    """

    DU = 32.0

    def _trams(self, bpm_a=120.0, bpm_b=120.0):
        b = tempo_map.durada_compas(bpm_a, 4, 4)
        tall = b * 8                      # 8 compassos de 120 BPM = 16 s
        return [(0.0, tall, bpm_a, 4, 4), (tall, self.DU, bpm_b, 4, 4)]

    def test_retempo_mou_la_frontera_i_recalcula_els_dos_bpm(self):
        out = tempo_map.mou_frontera_retempo(self._trams(), 1, 18.0, self.DU)
        self.assertAlmostEqual(out[0][1], 18.0, places=6)
        self.assertAlmostEqual(out[1][0], 18.0, places=6)
        # N es conserva a TOTS dos costats: 8 compassos cada un (§6.1 del doc).
        self.assertAlmostEqual(
            (18.0 - 0.0) / tempo_map.durada_compas(out[0][2], 4, 4), 8.0,
            places=4)
        self.assertAlmostEqual(
            (self.DU - 18.0) / tempo_map.durada_compas(out[1][2], 4, 4), 8.0,
            places=4)
        # Cobertura exacta: de 0 a la fi de la WAV, sense forats.
        self.assertAlmostEqual(out[0][0], 0.0, places=9)
        self.assertAlmostEqual(out[1][1], self.DU, places=9)
        self.assertAlmostEqual(out[0][1], out[1][0], places=9)
        # Xifres del document: 106,67 i 137,14 BPM.
        self.assertAlmostEqual(out[0][2], 106.6667, places=3)
        self.assertAlmostEqual(out[1][2], 137.1429, places=3)

    def test_la_frontera_cau_sempre_en_linia_de_compas(self):
        # El validador de compassos enters ha d'acceptar qualsevol drag.
        trams = self._trams()
        # Vàlids: N=8 a cada costat amb Δt dins la banda 30–350 BPM.
        for t in (9.123, 15.999, 16.001, 24.4):
            out = tempo_map.mou_frontera_retempo(trams, 1, t, self.DU)
            self.assertEqual(len(out), 2)
            self.assertAlmostEqual(out[0][1], t, places=6)

    def test_no_mou_cap_altre_tram(self):
        trams = [(0.0, 10.0, 120.0, 4, 4), (10.0, 20.0, 120.0, 4, 4),
                 (20.0, self.DU, 90.0, 4, 4)]
        out = tempo_map.mou_frontera_retempo(trams, 1, 12.0, self.DU)
        self.assertEqual(out[2], trams[2])      # el veí del fons, intacte
        self.assertAlmostEqual(out[0][1], 12.0, places=6)

    def test_limits_de_seguretat(self):
        trams = self._trams()
        # Massa a prop de l'inici del tram esquerre.
        with self.assertRaises(ValueError):
            tempo_map.mou_frontera_retempo(
                trams, 1, tempo_map.FRONTERA_MIN_S / 2.0, self.DU)
        # Massa a prop del final del tram dret.
        with self.assertRaises(ValueError):
            tempo_map.mou_frontera_retempo(
                trams, 1, self.DU - tempo_map.FRONTERA_MIN_S / 2.0, self.DU)
        # La primera frontera (inici de la WAV) no es pot moure.
        with self.assertRaises(ValueError):
            tempo_map.mou_frontera_retempo(trams, 0, 1.0, self.DU)
        # Frontera inexistent.
        with self.assertRaises(ValueError):
            tempo_map.mou_frontera_retempo(trams, 2, 1.0, self.DU)

    def test_bpm_fora_de_rang_es_rebutja(self):
        # 8 compassos en 0,6 s → 3200 BPM: absurd, s'ha d'avisar.
        trams = [(0.0, 10.0, 120.0, 4, 4), (10.0, self.DU, 120.0, 4, 4)]
        with self.assertRaises(ValueError) as cm:
            tempo_map.mou_frontera_retempo(trams, 1, 0.6, self.DU)
        self.assertIn("BPM", str(cm.exception))

    def test_primer_tram_amb_premusica_conserva_l_offset(self):
        # L'offset (3 s de pre-música) no es toca: els compassos compten des d'ell.
        trams = [(0.0, 19.0, 120.0, 4, 4), (19.0, self.DU, 120.0, 4, 4)]
        out = tempo_map.mou_frontera_retempo(trams, 1, 21.0, self.DU,
                                            offset=3.0)
        # La pre-música (0 → 3 s) no es toca mai: només canvia la frontera.
        self.assertAlmostEqual(out[0][0], 0.0, places=6)
        self.assertAlmostEqual(out[0][1], 21.0, places=6)
        # 18 s de música des de l'offset amb N=8 → 106,67 BPM (N es conserva).
        self.assertAlmostEqual(out[0][2], 106.6667, places=3)

    def test_primer_tram_pot_acabar_al_compas_1(self):
        # Pre-roll pur: la fi del primer clip pot caure EXACTAMENT al compàs 1
        # (abans s'exigia offset + 0,5 s i era impossible tornar-hi).
        trams = [(0.0, 6.778, 50.0, 4, 4),
                 (6.778, 165.733854, 120.858, 4, 4)]
        out = tempo_map.mou_frontera_retempo(trams, 1, 1.978, 165.733854,
                                            offset=1.978)
        self.assertAlmostEqual(out[0][0], 0.0, places=6)
        self.assertAlmostEqual(out[0][1], 1.978, places=6)
        self.assertAlmostEqual(out[0][2], 50.0, places=6)   # BPM intacte
        self.assertAlmostEqual(out[1][0], 1.978, places=6)
        self.assertAlmostEqual(out[1][1], 165.733854, places=6)
        # La dreta conserva els seus 80 compassos (163,76 s) → 117,25 BPM.
        self.assertAlmostEqual(out[1][2], 117.25, places=1)

    def test_frontera_no_passa_abans_del_compas_1(self):
        trams = [(0.0, 6.778, 50.0, 4, 4),
                 (6.778, 165.733854, 120.858, 4, 4)]
        with self.assertRaises(ValueError) as cm:
            tempo_map.mou_frontera_retempo(trams, 1, 1.5, 165.733854,
                                          offset=1.978)
        self.assertIn("compàs 1", str(cm.exception))

    def test_compassos_mes_menys_i_doblar(self):
        un = [(0.0, 8.0, 120.0, 4, 4)]
        self.assertAlmostEqual(
            tempo_map.canvia_compassos_tram(un, 0, 1, 8.0)[0][2], 150.0,
            places=4)                      # +1 → 5 compassos en 8 s
        self.assertAlmostEqual(
            tempo_map.canvia_compassos_tram(un, 0, -1, 8.0)[0][2], 90.0,
            places=4)                      # −1 → 3 compassos en 8 s
        self.assertAlmostEqual(
            tempo_map.canvia_compassos_tram(un, 0, 0, 8.0, factor=2)[0][2],
            240.0, places=4)               # ×2 → 8 compassos en 8 s
        self.assertAlmostEqual(
            tempo_map.canvia_compassos_tram(un, 0, 0, 8.0, factor=0.5)[0][2],
            60.0, places=4)                # ÷2 → 2 compassos en 8 s

    def test_compassos_no_mouen_res_mes(self):
        # Tram central de 12 s amb 3/4 a 60 BPM = 4 compassos (12 s / 3 s).
        trams = [(0.0, 8.0, 120.0, 4, 4), (8.0, 20.0, 60.0, 3, 4),
                 (20.0, self.DU, 90.0, 4, 4)]
        out = tempo_map.canvia_compassos_tram(trams, 1, 2, self.DU)
        self.assertEqual(out[0], trams[0])          # el veí d'abans, intacte
        self.assertEqual(out[2], trams[2])          # el de darrere, intacte
        self.assertAlmostEqual(out[1][0], 8.0, places=6)   # ini immòbil
        self.assertAlmostEqual(out[1][1], 20.0, places=6)  # fi immòbil
        # 12 s amb 3/4: 4 compassos a 60 BPM → 6 compassos a 90 BPM.
        self.assertAlmostEqual(out[1][2], 90.0, places=4)

    def test_compassos_no_baixen_d_un(self):
        with self.assertRaises(ValueError):
            # 4 compassos − 4 = 0 compassos.
            tempo_map.canvia_compassos_tram([(0.0, 8.0, 120.0, 4, 4)], 0, -4,
                                            8.0)
        with self.assertRaises(ValueError):
            tempo_map.canvia_compassos_tram([(0.0, 8.0, 120.0, 4, 4)], 0, 0,
                                            8.0, factor=0)

    def test_compassos_fora_de_rang(self):
        # 10 compassos a 340 BPM + 1 → 374 BPM: fora de la banda raonable.
        b = tempo_map.durada_compas(340.0, 4, 4)
        with self.assertRaises(ValueError) as cm:
            tempo_map.canvia_compassos_tram([(0.0, b * 10, 340.0, 4, 4)], 0,
                                            1, b * 10)
        self.assertIn("BPM", str(cm.exception))

    def test_canviar_bpm_local_ajusta_el_vei_sense_moure_res_mes(self):
        # Diàleg/transport (contracte §7): el tram conserva N; el veí interior
        # conserva els compassos i el seu final, i recalcula el BPM. La resta
        # del mapa no es mou.
        trams = [(0.0, 8.0, 120.0, 4, 4), (8.0, 20.0, 60.0, 3, 4),
                 (20.0, 32.0, 60.0, 3, 4), (32.0, 44.0, 120.0, 4, 4)]
        out = tempo_map.canvia_bpm_local(trams, 1, 90.0, 44.0)
        self.assertEqual(out[0], trams[0])            # el d'abans, intacte
        self.assertEqual(out[3], trams[3])            # el del fons, intacte
        self.assertAlmostEqual(out[1][2], 90.0, places=6)
        self.assertAlmostEqual(out[1][1], 16.0, places=6)   # 4 compassos a 90
        self.assertAlmostEqual(out[2][1], trams[2][1], places=9)  # fi immòbil
        # 4 compassos de 3/4 en 16 s → 45 BPM (el BPM és la conseqüència).
        self.assertAlmostEqual(out[2][2], 45.0, places=6)
        self.assertAlmostEqual(
            (out[2][1] - out[2][0]) / tempo_map.durada_compas(out[2][2], 3, 4),
            4.0, places=6)

    def test_canviar_bpm_local_el_vei_ultim_absorbeix(self):
        # L'últim tram no pot moure la seua fi (WAV): conserva el BPM i
        # absorbeix el desplaçament en el nombre de compassos (§5).
        trams = [(0.0, 8.0, 90.0, 4, 4), (8.0, 10.0, 120.0, 3, 4)]
        out = tempo_map.canvia_bpm_local(trams, 0, 110.0, 10.0)
        self.assertAlmostEqual(out[0][1], 6.54545, places=4)
        self.assertAlmostEqual(out[1][0], out[0][1], places=9)
        self.assertAlmostEqual(out[1][1], 10.0, places=9)   # la WAV mana
        self.assertAlmostEqual(out[1][2], 120.0, places=6)  # el tempo es manté

    def test_canviar_bpm_local_respecta_la_premusica(self):
        trams = [(0.0, 19.0, 120.0, 4, 4), (19.0, 35.0, 120.0, 4, 4)]
        out = tempo_map.canvia_bpm_local(trams, 0, 100.0, 35.0, offset=3.0)
        self.assertAlmostEqual(out[0][0], 0.0, places=9)    # pre-música intacta
        self.assertAlmostEqual(out[0][1], 22.2, places=6)   # 3 + 8 compassos
        self.assertAlmostEqual(out[0][2], 100.0, places=6)
        self.assertAlmostEqual(out[1][1], 35.0, places=9)   # la fi no es mou
        self.assertAlmostEqual(out[1][2], 120.0, places=6)  # l'últim absorbeix

    def test_canviar_bpm_local_rebutja_si_no_hi_cap(self):
        # El tram creixeria més enllà del veí.
        trams = [(0.0, 8.0, 120.0, 4, 4), (8.0, 16.0, 120.0, 4, 4)]
        with self.assertRaises(ValueError):
            tempo_map.canvia_bpm_local(trams, 0, 30.0, 16.0)
        # ...i si el BPM d'un veí INTERIOR se n'aniria fora de la banda.
        trams = [(0.0, 8.0, 120.0, 4, 4), (8.0, 40.0, 90.0, 4, 4),
                 (40.0, 50.0, 120.0, 4, 4)]
        with self.assertRaises(ValueError) as cm:
            tempo_map.canvia_bpm_local(trams, 0, 30.0, 50.0)
        self.assertIn("BPM", str(cm.exception))

    def test_canviar_bpm_local_canvia_el_compas_conservant_n(self):
        # 5 compassos de 4/4 a 120 (10 s) → 5 compassos de 3/4 a 100 (9 s).
        trams = [(0.0, 10.0, 120.0, 4, 4), (10.0, 30.0, 90.0, 3, 4),
                 (30.0, 42.0, 120.0, 4, 4)]
        out = tempo_map.canvia_bpm_local(trams, 0, 100.0, 42.0, num=3, den=4)
        self.assertAlmostEqual(out[0][1], 9.0, places=6)
        self.assertEqual(out[0][3:], (3, 4))
        self.assertAlmostEqual(
            out[0][1] / tempo_map.durada_compas(100.0, 3, 4), 5.0, places=6)
        self.assertAlmostEqual(out[1][1], 30.0, places=9)
        # El veí [9,30] = 21 s conserva 10 compassos → 85,714 BPM.
        self.assertAlmostEqual(out[1][2], 10 * 3 * 60 / 21.0, places=6)
        self.assertEqual(out[2], trams[2])            # el del fons, intacte

    def test_canviar_bpm_local_ultim_tram(self):
        out = tempo_map.canvia_bpm_local([(0.0, 12.0, 60.0, 3, 4)], 0,
                                         90.0, 12.0)
        self.assertEqual(out, [(0.0, 12.0, 90.0, 3, 4)])

    def test_canviar_bpm_local_primer_parcial_redimensiona(self):
        # Pre-roll que acaba fora de graella (marcador a 1,99 s): no es
        # bloqueja, el tram canvia de mida i el veí últim absorbeix.
        trams = [(0.0, 1.99, 120.0, 4, 4), (1.99, 60.0, 120.0, 4, 4)]
        out = tempo_map.canvia_bpm_local(trams, 0, 100.0, 60.0)
        self.assertAlmostEqual(out[0][1], 2.4, places=6)   # 1 compàs a 100
        self.assertAlmostEqual(out[0][2], 100.0, places=6)
        self.assertAlmostEqual(out[1][0], 2.4, places=9)
        self.assertAlmostEqual(out[1][1], 60.0, places=9)  # la WAV mana
        self.assertAlmostEqual(out[1][2], 120.0, places=6)  # conserva el BPM

    def test_canviar_bpm_local_premusica_pura_no_es_mou(self):
        # Tot el primer tram és pre-música: només canvia el BPM.
        trams = [(0.0, 1.99, 120.0, 4, 4), (1.99, 60.0, 120.0, 4, 4)]
        out = tempo_map.canvia_bpm_local(trams, 0, 100.0, 60.0, offset=1.99)
        self.assertEqual(out[0], (0.0, 1.99, 100.0, 4, 4))
        self.assertEqual(out[1], trams[1])

    def test_canviar_bpm_local_diu_el_llindar_que_hi_cap(self):
        # Cas real (Otis): el clip central no pot créixer més enllà de la WAV.
        # El missatge ha de dir el BPM més baix que encara hi cap.
        trams = [(0.0, 1.911874, 124.625161, 4, 4),
                 (1.911874, 1.925775, 124.625161, 4, 4),
                 (1.925775, 157.232073, 120.536, 4, 4),
                 (157.232073, 165.733854, 112.911987, 4, 4)]
        with self.assertRaises(ValueError) as cm:
            tempo_map.canvia_bpm_local(trams, 2, 100.0, 165.733854)
        self.assertIn("massa curt", str(cm.exception))
        self.assertIn("114.6", str(cm.exception))

    def test_canviar_bpm_local_no_el_bloqueja_una_frontera_fora_de_graella(self):
        # Canviar el BPM de l'últim tram amb la frontera a 1,99 s (fora de
        # graella) ha de funcionar: mateixa validació permissiva que el drag.
        trams = [(0.0, 1.99, 120.0, 4, 4), (1.99, 60.0, 120.0, 4, 4)]
        out = tempo_map.canvia_bpm_local(trams, 1, 100.0, 60.0)
        self.assertAlmostEqual(out[0][0], 0.0, places=9)
        self.assertAlmostEqual(out[1][0], 1.99, places=9)
        self.assertAlmostEqual(out[1][1], 60.0, places=9)
        self.assertAlmostEqual(out[1][2], 100.0, places=6)


class MarcadorsTempoTests(unittest.TestCase):
    """`+` i «Detecta» per tram: cap gest es bloqueja per compassos fraccionaris.

    Regressió del flux de tempo variable: un marcador ha de nàixer damunt d'una
    línia de compàs (tram esquerre amb N enter) i «Detecta» no pot moure les
    fronteres (els marcadors delimitadors manen).
    """

    def test_parteix_el_tram_amb_compassos_enters(self):
        # 15 s des de 0 amb referència 120 BPM → N=8 compassos de 4/4 → 128 BPM.
        out = tempo_map.parteix_tram_marcador(
            [(0.0, 30.0, 120.0, 4, 4)], 15.0, 30.0)
        self.assertEqual(len(out), 2)
        self.assertAlmostEqual(out[0][1], 15.0, places=6)
        self.assertAlmostEqual(out[0][2], 128.0, places=4)
        self.assertAlmostEqual(
            15.0 / tempo_map.durada_compas(out[0][2], 4, 4), 8.0, places=4)
        # La resta fins al pròxim inici (15→30) també queda amb 8 compassos
        # enters: el BPM s'ajusta (aquí coincideix: 128) i el compàs no canvia.
        self.assertAlmostEqual(out[1][2], 128.0, places=6)
        self.assertEqual((out[1][3], out[1][4]), (4, 4))
        self.assertAlmostEqual(
            15.0 / tempo_map.durada_compas(out[1][2], 4, 4), 8.0, places=4)
        # Cobertura contigua i exacta.
        self.assertAlmostEqual(out[0][1], out[1][0], places=9)
        self.assertAlmostEqual(out[1][1], 30.0, places=9)

    def test_parteix_respecta_l_offset(self):
        # Pre-música de 2 s: els compassos del primer tram compten des de 2 s.
        out = tempo_map.parteix_tram_marcador(
            [(0.0, 30.0, 120.0, 4, 4)], 10.0, 30.0, offset=2.0,
            bpm_ref=120.0)
        # 8 s de música → N=4 compassos de 4/4 → 120 BPM.
        self.assertAlmostEqual(out[0][2], 120.0, places=4)
        self.assertAlmostEqual(
            (10.0 - 2.0) / tempo_map.durada_compas(out[0][2], 4, 4), 4.0,
            places=4)

    def test_marcador_massa_a_prop_no_bloqueja(self):
        # `+` a 0,4 s (el cas del play): 1 compàs donaria 600 BPM, fora de
        # rang. El gest s'accepta conservant el BPM vigent i queda pendent
        # d'ajust; abans llançava ValueError i el marcador no es creava.
        out = tempo_map.parteix_tram_marcador(
            [(0.0, 60.0, 120.0, 4, 4)], 0.4, 60.0, bpm_ref=120.0)
        self.assertEqual(len(out), 2)
        self.assertAlmostEqual(out[0][1], 0.4, places=6)
        self.assertAlmostEqual(out[0][2], 120.0, places=6)

    def test_retempo_detectat_no_mou_les_fronteres(self):
        trams = [(0.0, 16.0, 120.0, 4, 4), (16.0, 32.0, 120.0, 4, 4)]
        out = tempo_map.retempo_tram_detectat(trams, 0, 130.0, 32.0)
        # Δt=16 s fixes: N=round(16·130/240)=9 → 135 BPM exactes.
        self.assertAlmostEqual(out[0][2], 135.0, places=6)
        self.assertAlmostEqual(out[0][0], 0.0, places=9)
        self.assertAlmostEqual(out[0][1], 16.0, places=9)
        self.assertAlmostEqual(out[1][0], 16.0, places=9)
        self.assertAlmostEqual(out[1][1], 32.0, places=9)
        self.assertAlmostEqual(out[1][2], 120.0, places=9)
        validat = tempo_map.valida_i_normalitza_compassos(out, 32.0)
        self.assertEqual(len(validat), 2)
        self.assertAlmostEqual(float(validat[0][2]), 135.0, places=6)

    def test_retempo_detectat_valida_index_i_bpm(self):
        trams = [(0.0, 16.0, 120.0, 4, 4), (16.0, 32.0, 120.0, 4, 4)]
        with self.assertRaises(ValueError):
            tempo_map.retempo_tram_detectat(trams, 9, 130.0, 32.0)
        with self.assertRaises(ValueError):
            tempo_map.retempo_tram_detectat(trams, 0, 0.0, 32.0)

    def test_ajusta_un_tram_per_interval_de_marcador(self):
        out = tempo_map.ajusta_trams_a_marcadors(
            [(0.0, 30.0, 120.0, 4, 4)], [2.0, 10.5, 20.0], 30.0)
        self.assertEqual(len(out), 4)
        self.assertEqual([round(float(t[0]), 6) for t in out],
                         [0.0, 2.0, 10.5, 20.0])
        self.assertAlmostEqual(out[-1][1], 30.0, places=9)
        # 8,5 s amb N=4 → 112,94 BPM; 9,5 s amb N=5 → 126,32 BPM.
        self.assertAlmostEqual(out[1][2], 112.9412, places=3)
        self.assertAlmostEqual(out[2][2], 126.3158, places=3)
        # Cap i cua hereten el BPM de l'interval adjacent.
        self.assertAlmostEqual(out[0][2], out[1][2], places=9)
        self.assertAlmostEqual(out[3][2], out[2][2], places=9)

    def test_ajusta_amb_menys_de_dos_marcadors_falla(self):
        with self.assertRaises(ValueError):
            tempo_map.ajusta_trams_a_marcadors(
                [(0.0, 30.0, 120.0, 4, 4)], [5.0], 30.0)

    def test_una_frontera_heretada_no_bloqueja_el_re_tempo(self):
        # Tram 0 amb 10,3 s (5,15 compassos a 120): desviació vella. Moure la
        # frontera 2 (trams 1 i 2) no ha de quedar bloquejat pel tram 0.
        trams = [(0.0, 10.3, 120.0, 4, 4), (10.3, 20.0, 120.0, 4, 4),
                 (20.0, 32.0, 120.0, 4, 4)]
        out = tempo_map.mou_frontera_retempo(trams, 2, 21.0, 32.0)
        self.assertEqual(len(out), 3)
        self.assertAlmostEqual(out[1][1], 21.0, places=6)
        self.assertAlmostEqual(out[2][0], 21.0, places=6)
        # Els trams tocats sí que queden amb compassos enters.
        self.assertAlmostEqual(
            (21.0 - 10.3) / tempo_map.durada_compas(out[1][2], 4, 4), 5.0,
            places=3)
        self.assertAlmostEqual(
            (32.0 - 21.0) / tempo_map.durada_compas(out[2][2], 4, 4), 6.0,
            places=3)


if __name__ == "__main__":
    unittest.main()
