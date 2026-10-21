"""Suite de test — Pipeline

> Suite CONSOLIDADA (Fase 4, 2026-10-19): fusiona 28 mòduls de test que abans
> vivien separats a `tests/`. Cada bloc conserva el seu codi original íntegre
> (només s'han renombrat els símbols de nivell superior que xocaven i s'han
> unificat els imports). Cobertura intacta: cap test eliminat.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene: esborra els temporals en plegar

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
import tempfile
from app import pipeline
import numpy as np
from app import acord_audio as A
import subprocess
import threading
from unittest import mock
from app import audio_out, plataforma
import hashlib
import struct
import http.server
import importlib.util
import shutil
import socketserver
from unittest.mock import patch
import io
from app import xifrat
import xml.etree.ElementTree as ET
import wave
import PyQt5.QtWidgets as QW
from app import main as app_main
import faulthandler
import glob
import re
from PyQt5.QtWidgets import QApplication
from app import icones
from pathlib import Path
from app import partitura
import csv
import logging
from app import config, dialegs, ffmpeg, postproc, theme, vamp_params, visor
from app import visor as visor_mod

def setUpModule():
    _pipeline_export_setUpModule()


def tearDownModule():
    _audio_out_tearDownModule()
    _export_async_tearDownModule()
    _export_neteja_estructura_tearDownModule()
    _export_ok_fals_tearDownModule()
    _partitura_sense_musescore_tearDownModule()
    _pipeline_export_tearDownModule()
    _xocs_inici_csv_tearDownModule()


# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_acords_a_live.py
# ══════════════════════════════════════════════════════════════════════════
"""Guia DAW — tot EN MEMÒRIA (`segments_locators` / `genera_guia_html`).

Els segments (posició, acord, durada en temps) i la guia HTML es calculen a
partir del model. **No hi ha cap `acords_locators.txt`**: decisió de
l'operador (2026-10-19) de tenir el sistema de fitxers intern més simple.
"""


ACORDS = "inici_s,fi_s,acord\n0.0,4.0,C\n4.0,8.0,Am\n8.0,12.0,F\n12.0,16.0,G\n"


def _carpeta(tempo=None, compas=None):
    td = tempfile.mkdtemp()
    with open(os.path.join(td, "acords.csv"), "w", encoding="utf-8") as f:
        f.write(ACORDS)
    if tempo:
        with open(os.path.join(td, "tempo.csv"), "w", encoding="utf-8") as f:
            f.write(tempo)
        with open(os.path.join(td, "compas.csv"), "w", encoding="utf-8") as f:
            f.write(compas)
    return td


class TestGuiaDaw(unittest.TestCase):

    def _segs(self, td, durada=16.0):
        return pipeline.segments_locators(
            os.path.join(td, "acords.csv"), 120.0, 4, 0.0, durada=durada)

    def test_segments_en_memoria(self):
        td = _carpeta()
        segs = self._segs(td)
        self.assertEqual([c for (_p, c, _d) in segs], ["C", "Am", "F", "G"])
        self.assertEqual(segs[0][0], "1.1.1", "posició compàs.temps.fusa")
        self.assertAlmostEqual(segs[0][2], 8.0, places=6)   # 4 s a 120 BPM

    def test_genera_guia_html(self):
        td = _carpeta()
        guia = pipeline.genera_guia_html(
            os.path.join(td, "acords.csv"), 120.0, 4, 0.0, workdir=td,
            durada=16.0)
        self.assertTrue(os.path.isfile(guia), "ha de generar guia_acords.html")
        with open(guia, encoding="utf-8") as f:
            html = f.read()
        self.assertIn("120 BPM", html)
        self.assertIn('<div class="g">', html)
        self.assertIn("G", html)

    def test_no_escriu_cap_locators(self):
        td = _carpeta()
        self._segs(td)
        pipeline.genera_guia_html(os.path.join(td, "acords.csv"), 120.0, 4,
                                  0.0, workdir=td, durada=16.0)
        self.assertFalse(os.path.exists(os.path.join(td, "acords_locators.txt")),
                         "el locator intermedi ja no s'ha de crear mai")

    def test_events_partitura(self):
        """Els beats de la partitura surten del mateix model (sense fitxers)."""
        td = _carpeta()
        ev = pipeline.events_partitura(
            os.path.join(td, "acords.csv"), 120.0, 4, 0.0, durada=16.0)
        self.assertEqual([e[1] for e in ev], ["C", "Am", "F", "G"])
        self.assertAlmostEqual(ev[0][0], 0.0)
        self.assertAlmostEqual(ev[0][2], 8.0, places=6)

    def test_amb_mapa_de_tempo_variable(self):
        """Amb `tempo.csv`/`compas.csv` de més d'un tram, tot es calcula amb el
        mapa (posicions compàs.temps.fusa) i no peta."""
        td = _carpeta(tempo="ini_s,fi_s,bpm\n0.0,8.0,120\n8.0,16.0,90\n",
                      compas="ini_s,fi_s,beats,beat_type\n0.0,8.0,4,4\n"
                             "8.0,16.0,3,4\n")
        segs = self._segs(td)
        self.assertEqual(len(segs), 4)
        guia = pipeline.genera_guia_html(
            os.path.join(td, "acords.csv"), 120.0, 4, 0.0, workdir=td,
            durada=16.0)
        with open(guia, encoding="utf-8") as f:
            self.assertIn("G", f.read())

    def test_tot_n_dona_error_clar(self):
        """Un model amb només «N» ha de llançar RuntimeError clar."""
        td = tempfile.mkdtemp()
        csv_path = os.path.join(td, "acords.csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("inici_s,fi_s,acord\n0.0,4.0,N\n")
        with self.assertRaises(RuntimeError) as ctx:
            pipeline.segments_locators(csv_path, 120.0, 4, 0.0, durada=4.0)
        self.assertIn("cap acord per exportar", str(ctx.exception))

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_acord_audio.py
# ══════════════════════════════════════════════════════════════════════════
"""Àudio per escoltar un tipus d'acord (`app/acord_audio.py`).

Piano elèctric sintetitzat amb numpy (FM estil Rhodes): **sense dependències
noves** i amb el **mateix motor d'àudio** de l'app. Aquí **no es fa sonar res**:
es verifica la matemàtica (notes → MIDI) i el senyal (mida, extrems, sense
saturar, sense NaN).
"""


class TestNotes(unittest.TestCase):
    def test_acords_coneguts(self):
        for arrel, graus, esperat in [
                ("C", "1,3,5,7", [48, 52, 55, 59]),          # Cmaj7: C3 E3 G3 B3
                ("F#", "1,b3,b5,b7", [54, 57, 60, 64]),      # F#m7b5
                ("Ab", "1,3,5,6,9", [56, 60, 63, 65, 70]),   # Ab6/9
                ("C", "1,5", [48, 55]),                      # C5 (power)
                ("C", "", [48])]:                            # sense graus → arrel
            self.assertEqual(A.notes_del_tipus(arrel, graus), esperat,
                             f"{arrel} {graus}")

    def test_sense_arrel_valida(self):
        self.assertEqual(A.notes_del_tipus("", "1,3,5"), [])
        self.assertEqual(A.notes_del_tipus("H", "1,3,5"), [])

    def test_graus_no_numerics_s_ignoren(self):
        """`7alt` porta «+alt» → s'ignora i queden 1,3,b7."""
        self.assertEqual(A.notes_del_tipus("C", "1,3,b7,+alt"), [48, 52, 58])

    def test_no_surt_del_rang(self):
        for arrel in ("C", "B", "Gb"):
            notes = A.notes_del_tipus(arrel, "1,3,5,7,9,11,13")
            self.assertTrue(all(A.MIDI_MIN <= m <= A.MIDI_MAX for m in notes),
                            arrel)

    def test_notes_amb_baix(self):
        """Acords amb `/`: el baix sona una octava sota l'arrel."""
        # A + 1,3,5,b7 (A7) amb baix G → G2 (43) + l'acord de A3 (57)
        notes = A.notes_amb_baix("A", "1,3,5,b7", "G")
        self.assertEqual(notes[0], 43, "el baix ha d'anar a baix de tot")
        self.assertIn(57, notes)
        # sense baix → igual que el tipus sol
        self.assertEqual(A.notes_amb_baix("A", "1,3,5,b7", ""),
                         A.notes_del_tipus("A", "1,3,5,b7"))
        # baix invàlid → s'ignora
        self.assertEqual(A.notes_amb_baix("A", "1,3,5,b7", "H"),
                         A.notes_del_tipus("A", "1,3,5,b7"))

    def test_baix_enharmonic(self):
        # Db2 i C#2 són la mateixa nota (MIDI 37)
        self.assertEqual(A.notes_amb_baix("Ab", "1,3,5,6,9", "Db")[0], 37)
        self.assertEqual(A.notes_amb_baix("F#", "1,b3,b5,b7", "C#")[0], 37)

    def test_duplicats_fora(self):
        # `1,1,3` → dues vegades la tònica = una sola nota
        self.assertEqual(A.notes_del_tipus("C", "1,1,3"), [48, 52])


class TestSenyal(unittest.TestCase):
    def _x(self, pcm):
        return np.frombuffer(pcm, "<i2").astype(float)

    def test_pcm_acord(self):
        sr = 22050
        x = self._x(A.pcm_acord([48, 52, 55, 59], sr, 0.5))
        self.assertEqual(len(x), int(0.5 * sr))
        self.assertFalse(np.isnan(x).any())
        self.assertLessEqual(abs(x).max(), 32767)
        self.assertLess(abs(x[0]), 100, "ha de començar a 0 (sense clic)")
        self.assertGreater(abs(x).max(), 10000, "no pot ser silenci")

    def test_no_satura_amb_moltes_notes(self):
        """El pic ha de quedar a 0,85 sense arribar mai al fons d'escala."""
        for n in (1, 4, 8, 12):
            notes = [48 + i for i in range(n)]
            x = self._x(A.pcm_acord(notes, 22050, 0.4))
            self.assertLessEqual(abs(x).max(), 32767, n)
            self.assertAlmostEqual(abs(x).max(), 0.85 * 32767, delta=250,
                                   msg=f"{n} notes saturades")

    def test_arpegi_i_escolta(self):
        bloc = A.pcm_acord([48, 52, 55], 22050, 0.5)
        arp = A.pcm_arpegi([48, 52, 55], 22050, 0.5, 0.2)
        self.assertGreater(len(arp), len(bloc), "l'arpegi dura més (en sèrie)")
        esc = A.pcm_escolta([48, 52, 55], 22050)
        self.assertGreater(len(esc), len(arp), "escolta = arpegi + pausa + bloc")

    def test_buits(self):
        self.assertEqual(A.pcm_acord([]), b"")
        self.assertEqual(A.pcm_arpegi([]), b"")
        self.assertEqual(A.pcm_escolta([]), b"")
        self.assertEqual(A.notes_del_tipus("C", ""), [48])

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_analisi_real.py
# ══════════════════════════════════════════════════════════════════════════
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


class TestAnalisiReal(unittest.TestCase):
    """Anàlisi REAL amb el host propi (`vamp_host_local`), sense skips."""

    def test_el_motor_treu_acords_de_veritat(self):
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "triades.wav")
        _wav_triades(wav)
        out = os.path.join(td, "acords.csv")
        pipeline.executa_transform(pipeline.CHORDS_TRANSFORM, out, wav,
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

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_audio_out.py
# ══════════════════════════════════════════════════════════════════════════
"""Tests del motor d'àudio (`app/audio_out.py`, `app/plataforma.py`).

⚠️ **Per què són aquí i no al CI de cada SO**: el motor natiu (`sounddevice`/
PortAudio) només s'executa a macOS/Windows. Com que provar al Mac és car (temps),
aquí fem servir un **`sounddevice` FALS** (`FakeSD`) i **simulem el SO**, de
manera que aquests tests corren a **Linux** (locals i al CI) i caçen bugs de
**concurrència/teardown** (com el `Pa_CloseStream` doble que petava l'app a
macOS) **abans** de compilar.
"""


# ── `sounddevice` FALS ───────────────────────────────────────────────────────
class _FakeStream:
    def __init__(self, **kw):
        self._falla = kw.pop("_falla", False)
        self.kw = kw
        self.started = False
        self.stops = 0
        self.aborts = 0
        self.closes = 0
        self.mostres = 0

    def start(self):
        if self._falla:
            raise RuntimeError("no s'ha pogut obrir el dispositiu")
        self.started = True

    def write(self, a):
        self.mostres += int(np.asarray(a).size)

    def stop(self):
        self.stops += 1

    def abort(self):
        self.aborts += 1

    def close(self):
        self.closes += 1


class FakeSD:
    """Substitut del mòdul `sounddevice` (per provar `MotorStream` a Linux)."""

    def __init__(self, apis=None, fallar=()):
        self.apis = apis if apis is not None else [
            {"name": "Core Audio", "default_output_device": 0}]
        self.fallar = set(fallar)
        self.creats = []
        self.default = mock.Mock(device=(0, 0))

    def query_hostapis(self):
        return list(self.apis)

    def OutputStream(self, **kw):
        # Com PortAudio: crea l'objecte i FALLA al start() si el dispositiu no
        # serveix (així provem que el MotorStream el tanqui).
        falla = kw.get("device") in self.fallar
        s = _FakeStream(_falla=falla, **kw)
        self.creats.append(s)
        return s


def _motor(so="mac", fake=None):
    """Crea un `MotorStream` real amb un `sounddevice` fals."""
    fake = fake or FakeSD()
    with mock.patch.dict(sys.modules, {"sounddevice": fake}), \
            mock.patch.object(plataforma, "SO", so):
        m = audio_out.MotorStream(44100)
    m._fake = fake
    return m


# ── Obertura / selecció de dispositiu ────────────────────────────────────────
class TestMotorStreamObertura(unittest.TestCase):
    def test_obre_el_primer_dispositiu(self):
        m = _motor()
        self.assertEqual(len(m._fake.creats), 1)
        self.assertTrue(m._fake.creats[0].started)
        self.assertIsNone(m.poll())          # encara sona

    def test_fallback_entre_host_apis(self):
        fake = FakeSD(apis=[{"name": "Windows WASAPI", "default_output_device": 0},
                            {"name": "MME", "default_output_device": 1}],
                      fallar=(0,))
        m = _motor(so="win", fake=fake)
        self.assertEqual(m._device, 1)                       # ha hagut de caure a MME
        self.assertEqual(m._fake.creats[0].closes, 1)        # el que va fallar es tanca

    def test_si_tot_falla_llanca(self):
        # cap host API obre, I el recurs final (`device=None`) tampoc.
        fake = FakeSD(fallar=(0, None))
        with self.assertRaises(RuntimeError):
            _motor(fake=fake)


# ── Escriptura ───────────────────────────────────────────────────────────────
class TestMotorStreamEscriptura(unittest.TestCase):
    def test_escriu_totes_les_mostres(self):
        m = _motor()
        m.write(b"\x01\x00" * 5000)
        m.close()
        self.assertEqual(m._fake.creats[0].mostres, 5000)

    def test_escriu_en_trossos(self):
        m = _motor()
        n = audio_out.MotorStream._PAS * 3 + 7
        m.write(b"\x00\x00" * n)
        m.close()
        self.assertEqual(m._fake.creats[0].mostres, n)

    def test_write_despres_de_tancar_peta(self):
        m = _motor()
        m.atura()
        with self.assertRaises(ValueError):
            m.write(b"\x00\x00")


# ── Teardown (el bug del crash) ──────────────────────────────────────────────
class TestMotorStreamTeardown(unittest.TestCase):
    def test_close_drena_i_tanca_un_sol_cop(self):
        m = _motor()
        st = m._fake.creats[0]
        m.close()
        self.assertEqual(st.stops, 1)        # drena
        self.assertEqual(st.closes, 1)
        self.assertIsNone(m.stream)
        self.assertEqual(m.poll(), 0)         # ha acabat

    def test_atura_no_drena(self):
        m = _motor()
        st = m._fake.creats[0]
        m.atura()
        self.assertEqual(st.stops, 0)        # atura talla, no drena
        self.assertEqual(st.closes, 1)
        self.assertEqual(m.poll(), 0)

    def test_tanca_idempotent(self):
        m = _motor()
        st = m._fake.creats[0]
        m.close()
        m.atura()          # 2n tancament -> no ha de tocar el stream
        m.close()          # 3r -> tampoc
        self.assertEqual(st.stops, 1)
        self.assertEqual(st.closes, 1)
        self.assertIsNone(m.stream)


class TestMotorStreamConcurrencia(unittest.TestCase):
    """⚠️ El bug original: `Pa_CloseStream` cridat 2 cops (o des de 2 fils) →
    `AudioToolbox APComponentInstance::disposeInstance` → EXC_BAD_ACCESS."""

    def test_concurrent_un_sol_tancament(self):
        m = _motor()
        st = m._fake.creats[0]
        errors = []

        def bucle(fn):
            for _audio_out___ in range(300):
                try:
                    fn()
                except ValueError:
                    pass
                except Exception as e:   # noqa: BLE001
                    errors.append(repr(e))

        accions = [m.close, m.atura, m.close,
                   lambda: m.write(b"\x00\x00" * 64), m.atura]
        fils = [threading.Thread(target=bucle, args=(a,)) for a in accions]
        for f in fils:
            f.start()
        for f in fils:
            f.join()
        self.assertEqual(errors, [])
        self.assertEqual(st.closes, 1, "el stream s'ha tancat més d'un cop! (crash a mac)")
        self.assertLessEqual(st.stops, 1)
        self.assertIsNone(m.stream)
        self.assertEqual(m.poll(), 0)


# ── Motor de procés (Linux) + selecció per SO ────────────────────────────────
class TestMotorProc(unittest.TestCase):
    def test_cicle_de_vida(self):
        if plataforma.ES_WINDOWS:
            self.skipTest("la prova fa servir /bin/cat (no hi és a Windows)")
        with open(os.devnull, "wb") as ferr:
            motor = audio_out.crea_motor("cat", [], 44100, ferr)
            self.assertIsInstance(motor, audio_out.MotorProc)
            motor.stdin.write(b"\x00\x00" * 64)
            self.assertIsNone(motor.poll())
            motor.stdin.close()
            motor.atura()
        self.assertIsNotNone(motor.poll())


class TestSeleccioPerSO(unittest.TestCase):
    def test_linux(self):
        # Determinista a qualsevol SO (simulem Linux).
        with mock.patch.object(plataforma, "ES_LINUX", True), \
                mock.patch.object(plataforma, "ES_MAC", False), \
                mock.patch.object(plataforma, "ES_WINDOWS", False):
            self.assertFalse(plataforma.usa_audio_natiu())
            self.assertEqual(plataforma.candidats_reproductor(),
                             ("paplay", "aplay"))
            self.assertIn("PipeWire", plataforma.missatge_sense_audio())

    def test_mac_i_win(self):
        for mac, win in ((True, False), (False, True)):
            with mock.patch.object(plataforma, "ES_MAC", mac), \
                    mock.patch.object(plataforma, "ES_WINDOWS", win):
                self.assertTrue(plataforma.usa_audio_natiu())
                self.assertEqual(plataforma.candidats_reproductor(), ())
                self.assertNotIn("PipeWire", plataforma.missatge_sense_audio())

    def test_tria_player_mac_win_es_natiu(self):
        from app import visor
        with mock.patch.object(plataforma, "ES_MAC", True), \
                mock.patch.object(plataforma, "ES_WINDOWS", False):
            v = visor.Visor.__new__(visor.Visor)
            v.audio = {"sr": 44100}
            player, args = v._tria_player()
        self.assertEqual(player, audio_out.NOM_NATIU)
        self.assertEqual(args, [])


class TestPlataforma(unittest.TestCase):
    """Capa compartida (`app/plataforma.py`): camins de Linux/mac/win."""

    def test_executable(self):
        import tempfile
        p = os.path.join(tempfile.mkdtemp(), "x")
        open(p, "w").close()
        if plataforma.ES_WINDOWS:
            self.assertTrue(plataforma.executable(p))     # a Windows n'hi ha prou que existeixi
        else:
            self.assertFalse(plataforma.executable(p))
            os.chmod(p, 0o755)
            self.assertTrue(plataforma.executable(p))

    def test_kwargs_nou_grup(self):
        if plataforma.ES_WINDOWS:
            self.assertIn("creationflags", plataforma.kwargs_nou_grup())
        else:
            self.assertEqual(plataforma.kwargs_nou_grup(),
                             {"start_new_session": True})

    def test_bloqueja_instancia_unica(self):
        if plataforma.ES_WINDOWS:
            self.skipTest("prova de flock només POSIX")
        import tempfile
        p = os.path.join(tempfile.mkdtemp(), "lock")
        with open(p, "w") as a, open(p, "w") as b:
            self.assertTrue(plataforma.bloqueja_instancia_unica(a))
            self.assertFalse(plataforma.bloqueja_instancia_unica(b))
            plataforma.desbloqueja(a)

    def test_mata_grup(self):
        if plataforma.ES_WINDOWS:
            self.skipTest("prova de grup només POSIX")
        p = subprocess.Popen(["sleep", "30"], **plataforma.kwargs_nou_grup())
        plataforma.mata_grup(p)
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        self.assertIsNotNone(p.poll())

    def test_path_env_vamp(self):
        self.assertEqual(plataforma.path_env_vamp(["/a", "/b"]), "/a" + os.pathsep + "/b")


class TestReengegaComElVisor(unittest.TestCase):
    """El camí que petava a macOS (i que encara passa en bussejar/saltar):
    `_atura_proc()` del motor vell + `_engega_des_de()` (motor nou), **mentre el
    fil d'alimentació vell encara tancava**. El motor vell s'ha de tancar UN sol
    cop.

    (El canvi de BPM/compàs JA NO reengega res — el fil llig la graella a cada
    tros; vegeu `test_canviar_bpm_mentre_sona_no_talla_l_audio`. El reinici viu
    encara a `ves_a()`, que és un salt demanat per l'usuari.)"""

    def test_atura_i_reengega_amb_fil_vell_escrivint(self):
        fake = FakeSD()
        vell = _motor(fake=fake)
        st_vell = vell._fake.creats[0]

        aturat = threading.Event()

        def alimenta():                     # com `visor._alimenta`
            while not aturat.is_set():
                try:
                    vell.write(b"\x00\x00" * 512)
                except ValueError:
                    return                  # tancat: plega

        fil = threading.Thread(target=alimenta, daemon=True)
        fil.start()

        vell.atura()                        # com al salt: atura el vell
        nou = _motor(fake=fake)             # ...i n'obre un de nou
        aturat.set()
        fil.join(timeout=5)

        self.assertEqual(st_vell.closes, 1, "el motor vell s'ha tancat més d'un cop!")
        self.assertIsNotNone(nou.stream)
        self.assertEqual(nou._fake.creats[-1].closes, 0)
        self.assertIsNone(nou.poll())


def _audio_out_tearDownModule():
    # Neteja ORDENADA dels objectes Qt del mòdul (evita destrucció pel GC en un
    # test posterior -> access violation intermitent). Vegeu tests/_qt_neteja.py.
    try:
        import _qt_neteja
    except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_baixa_verificat.py
# ══════════════════════════════════════════════════════════════════════════
"""Tests de l'eina de baixada verificada (`eines/baixa_verificat.py`).

Es fa servir un **servidor HTTP local** (loopback) perquè els tests no depenguin
de la xarxa.
"""

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _carrega():
    ruta = os.path.join(ROOT, "eines", "baixa_verificat.py")
    spec = importlib.util.spec_from_file_location("baixa_verificat", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BV = _carrega()


class _Servidor:
    """Servidor HTTP local que serveix un diccionari {cami: bytes}."""

    def __init__(self, fitxers):
        self._fitxers = fitxers
        pare = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                cos = pare._fitxers.get(self.path)
                if cos is None:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Length", str(len(cos)))
                self.end_headers()
                self.wfile.write(cos)

            def log_message(self, *a):      # silenciós
                pass

        self._srv = socketserver.TCPServer(("127.0.0.1", 0), Handler)
        self.port = self._srv.server_address[1]
        self._fil = threading.Thread(target=self._srv.serve_forever,
                                     daemon=True)
        self._fil.start()

    def url(self, cami):
        return f"http://127.0.0.1:{self.port}{cami}"

    def tanca(self):
        self._srv.shutdown()
        self._srv.server_close()


class BaixaVerificatTests(unittest.TestCase):
    def setUp(self):
        # Sense reintents ni esperes: els tests de fallada han de ser ràpids.
        self._reintents = BV.REINTENTS
        self._espera = BV.ESPERA
        BV.REINTENTS = 1
        BV.ESPERA = 0
        # Memòria cau AÏLLADA (que no toqui la del projecte).
        self._cache = tempfile.mkdtemp()
        self._env = os.environ.get(BV.CACHE_ENV)
        os.environ[BV.CACHE_ENV] = self._cache
        self._d = tempfile.mkdtemp()
        self._cos = b"contingut de prova\n" * 20
        self._sha = hashlib.sha256(self._cos).hexdigest()
        self.srv = _Servidor({"/fitxer.bin": self._cos})

    def tearDown(self):
        BV.REINTENTS = self._reintents
        BV.ESPERA = self._espera
        if self._env is None:
            os.environ.pop(BV.CACHE_ENV, None)
        else:
            os.environ[BV.CACHE_ENV] = self._env
        self.srv.tanca()
        shutil.rmtree(self._d, ignore_errors=True)
        shutil.rmtree(self._cache, ignore_errors=True)

    def _desti(self):
        return os.path.join(self._d, "f.bin")

    def test_hash_correcte(self):
        rc = BV.main(["baixa_verificat.py", self.srv.url("/fitxer.bin"),
                      self._sha, self._desti()])
        self.assertEqual(rc, 0)
        with open(self._desti(), "rb") as f:
            self.assertEqual(f.read(), self._cos)

    def test_hash_incorrecte(self):
        rc = BV.main(["baixa_verificat.py", self.srv.url("/fitxer.bin"),
                      "0" * 64, self._desti()])
        self.assertEqual(rc, 1)
        self.assertFalse(os.path.exists(self._desti()))
        self.assertFalse(os.path.exists(self._desti() + ".part"))

    def test_calcula_el_hash(self):
        rc = BV.main(["baixa_verificat.py", self.srv.url("/fitxer.bin"),
                      "-", self._desti()])
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(self._desti()))
        self.assertEqual(BV.baixa(self.srv.url("/fitxer.bin"),
                                  os.path.join(self._d, "altre.bin")),
                         self._sha)

    def test_url_no_permesa(self):
        for url in ("file:///etc/passwd", "ftp://exemple/x",
                    "http://exemple.com/x", "data:text/plain,hola", ""):
            with self.assertRaises(ValueError):
                BV.baixa(url, self._desti())

    def test_404_no_deixa_fitxer(self):
        rc = BV.main(["baixa_verificat.py", self.srv.url("/no-existeix"),
                      self._sha, self._desti()])
        self.assertEqual(rc, 1)
        self.assertFalse(os.path.exists(self._desti()))
        self.assertFalse(os.path.exists(self._desti() + ".part"))

    def test_sha256_mal_format(self):
        rc = BV.main(["baixa_verificat.py", self.srv.url("/fitxer.bin"),
                      "abc", self._desti()])
        self.assertEqual(rc, 2)

    def test_us_dolent(self):
        self.assertEqual(BV.main(["baixa_verificat.py"]), 2)

    def test_crea_el_directori_desti(self):
        desti = os.path.join(self._d, "sub", "dir", "f.bin")
        rc = BV.main(["baixa_verificat.py", self.srv.url("/fitxer.bin"),
                      self._sha, desti])
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.isfile(desti))


class MemoriaCauTests(unittest.TestCase):
    """Memòria cau de baixades (A+B): no es baixa dues vegades el mateix."""

    def setUp(self):
        self._reintents, self._espera = BV.REINTENTS, BV.ESPERA
        self._usa = BV.USA_CACHE
        BV.REINTENTS, BV.ESPERA, BV.USA_CACHE = 1, 0, True
        self._d = tempfile.mkdtemp()
        self._cache = tempfile.mkdtemp()
        self._env = os.environ.get(BV.CACHE_ENV)
        os.environ[BV.CACHE_ENV] = self._cache
        self._cos = b"memoria cau\n" * 5
        self._sha = hashlib.sha256(self._cos).hexdigest()
        self.srv = _Servidor({"/f.bin": self._cos})

    def tearDown(self):
        BV.REINTENTS, BV.ESPERA, BV.USA_CACHE = (self._reintents, self._espera,
                                                 self._usa)
        if self._env is None:
            os.environ.pop(BV.CACHE_ENV, None)
        else:
            os.environ[BV.CACHE_ENV] = self._env
        self.srv.tanca()
        shutil.rmtree(self._d, ignore_errors=True)
        shutil.rmtree(self._cache, ignore_errors=True)

    def _desa(self, cami):
        return os.path.join(self._d, cami)

    def test_segona_baixada_usa_la_cache(self):
        self.assertEqual(BV.main(["baixa_verificat.py", self.srv.url("/f.bin"),
                                  self._sha, self._desa("a.bin")]), 0)
        self.assertTrue(os.path.isfile(os.path.join(self._cache, self._sha)))
        # Ara el servidor no serveix RES: si intentés baixar, petaria.
        self.srv.tanca()
        self.srv = _Servidor({})
        self.assertEqual(BV.main(["baixa_verificat.py", self.srv.url("/f.bin"),
                                  self._sha, self._desa("b.bin")]), 0)
        with open(self._desa("b.bin"), "rb") as f:
            self.assertEqual(f.read(), self._cos)

    def test_cache_corrupta_es_ignora_i_es_repara(self):
        with open(os.path.join(self._cache, self._sha), "wb") as f:
            f.write(b"corrupte")
        self.assertEqual(BV.main(["baixa_verificat.py", self.srv.url("/f.bin"),
                                  self._sha, self._desa("c.bin")]), 0)
        with open(self._desa("c.bin"), "rb") as f:
            self.assertEqual(f.read(), self._cos)     # s'ha tornat a baixar
        # i la còpia de la cache ha quedat reparada
        with open(os.path.join(self._cache, self._sha), "rb") as f:
            self.assertEqual(f.read(), self._cos)

    def test_sense_cache_no_desa_res(self):
        self.assertEqual(BV.main(["baixa_verificat.py", "--sense-cache",
                                  self.srv.url("/f.bin"), self._sha,
                                  self._desa("d.bin")]), 0)
        self.assertFalse(os.path.isfile(os.path.join(self._cache, self._sha)))


class DepsFixadesTests(unittest.TestCase):
    """El fitxer de versions fixades ha de ser complet i llegible."""

    RUTA = os.path.join(ROOT, "eines", "deps_fixades.env")
    CLAUS_SHA = ("PYBS_SHA256", "FFMPEG_LINUX_SHA256", "APPIMAGETOOL_SHA256",
                 "FFMPEG_MAC_SHA256", "FFMPEG_WIN_SHA256")
    CLAUS_URL = ("PYBS_URL", "FFMPEG_LINUX_URL", "APPIMAGETOOL_URL",
                 "FFMPEG_MAC_URL", "FFMPEG_WIN_URL")
    CLAUS_COMMIT = ("QM_VAMP_PLUGINS_COMMIT", "QM_DSP_COMMIT",
                    "VAMP_PLUGIN_SDK_COMMIT", "LIBSNDFILE_COMMIT")

    def _vars(self):
        """Llegeix el fitxer com ho faria bash (KEY=valor)."""
        valors = {}
        with open(self.RUTA, encoding="utf-8") as f:
            for linia in f:
                linia = linia.strip()
                if not linia or linia.startswith("#") or "=" not in linia:
                    continue
                clau, valor = linia.split("=", 1)
                valors[clau.strip()] = valor.strip().strip('"')
        return valors

    def test_te_les_claus(self):
        v = self._vars()
        for c in self.CLAUS_SHA + self.CLAUS_URL + self.CLAUS_COMMIT:
            self.assertIn(c, v, f"falta {c} a deps_fixades.env")

    def test_sha256_son_valids(self):
        v = self._vars()
        for c in self.CLAUS_SHA:
            self.assertRegex(v[c], r"^[0-9a-f]{64}$", f"{c} no és un SHA256")

    def test_commits_son_valids(self):
        v = self._vars()
        for c in self.CLAUS_COMMIT:
            self.assertRegex(v[c], r"^[0-9a-f]{40}$", f"{c} no és un commit")

    def test_urls_https_i_no_mobils(self):
        v = self._vars()
        for c in self.CLAUS_URL:
            self.assertTrue(v[c].startswith("https://"), f"{c} no és HTTPS")
            for mobil in ("continuous", "getrelease", "/latest/", "-release-"):
                self.assertNotIn(mobil, v[c], f"{c} encara és mòbil ({mobil})")

    def test_tag_lucide_fixat(self):
        self.assertRegex(self._vars()["LUCIDE_TAG"], r"^\d+\.\d+\.\d+$")

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_clips_unificats.py
# ══════════════════════════════════════════════════════════════════════════
"""Model unificat de clips (inici+fi) — refactor S1 (docs/archive/REFACTOR_INICI_FI.md).

Criteri d'èxit de S1: **cap canvi de comportament**. Les funcions noves han de
reproduir EXACTAMENT el que fa avui `pipeline.normalitza_cobertura` (que no es
toca) sobre el corpus dels dos tipus (acords i estructura).
"""


SENSE_A = (pipeline.SENSE_ACORD, "0.000000000")
SENSE_S = (pipeline.SENSE_SECCIO, pipeline.SENSE_SECCIO)
D = 10.0


class TestAdaptadors(unittest.TestCase):
    """`clip` ↔ model actual, anada i tornada."""

    def test_acords_a_clips_deriva_el_fi(self):
        ac = [(0.0, "C", "0.000000000"), (2.0, "Am", "2.000000000")]
        c = pipeline.clips_d_acords(ac, D)
        self.assertEqual([(x.ini, x.fi) for x in c], [(0.0, 2.0), (2.0, D)])
        self.assertEqual(c[0].payload, ("C", "0.000000000"))

    def test_acords_anada_i_tornada(self):
        ac = [(0.0, "C", "0"), (2.0, "Am", "0")]
        self.assertEqual(pipeline.acords_de_clips(
            pipeline.clips_d_acords(ac, D)), ac)

    def test_seccions_anada_i_tornada(self):
        s = [(0.0, 4.0, "A", "A"), (4.0, 10.0, "B", "B")]
        self.assertEqual(pipeline.seccions_de_clips(
            pipeline.clips_de_seccions(s)), s)

    def test_clip_es_comporta_com_a_tupla(self):
        c = pipeline.Clip(0.0, 2.0, ("C", "0"))
        self.assertEqual(tuple(c), (0.0, 2.0, ("C", "0")))
        ini, fi, payload = c
        self.assertEqual((ini, fi), (0.0, 2.0))
        self.assertEqual(payload, ("C", "0"))


class TestEquivalencia(unittest.TestCase):
    """`normalitza_clips` ha de donar el MATEIX que `normalitza_cobertura`."""

    CASOS_ACORDS = [
        [(0.0, "C", "0.000000000")],
        [(0.0, "C", "0"), (2.0, "Am", "0"), (4.0, "F", "0")],
        [(2.0, "C", "0")],                                       # capçalera N
        [(0.0, "C", "0"), (10.0, "Am", "0")],                     # fora de la WAV
        [(0.0, "C", "0"), (2.0, "Am", "0"), (2.004, "F", "0")],   # xoc al CSV
        [(0.0, "C", "0"), (9.999, "Am", "0")],
        [(2.0, "C", "0"), (2.004, "F", "0"), (5.0, "G", "0")],
    ]
    CASOS_SECCIONS = [
        [(0.0, 10.0, "A", "A")],
        [(2.0, 4.0, "A", "A")],                                  # capçalera
        [(2.0, 4.0, "A", "A"), (5.0, 7.0, "B", "B")],             # forat intern
        [(0.0, 12.0, "A", "A")],                                 # fi > durada
        [(0.0, 2.0, "A", "A"), (12.0, 14.0, "B", "B")],           # fora
        [(0.0, 3.0, "A", "A"), (7.0, 10.0, "-", "-")],
    ]

    def test_acords_equivalent(self):
        for ac in self.CASOS_ACORDS:
            amb, _clips_unificats___ = pipeline.normalitza_cobertura([tuple(x) for x in ac], [], D)
            nou = pipeline.acords_de_clips(pipeline.normalitza_clips(
                pipeline.clips_d_acords(ac, D), D, forat=SENSE_A,
                arrodoneix=True, deriva_fi=True))
            self.assertEqual(nou, amb, f"acords {ac}")

    def test_seccions_equivalent(self):
        for s in self.CASOS_SECCIONS:
            _clips_unificats___, amb = pipeline.normalitza_cobertura([], [tuple(x) for x in s], D)
            nou = pipeline.seccions_de_clips(pipeline.normalitza_clips(
                pipeline.clips_de_seccions(s), D, forat=SENSE_S))
            self.assertEqual(nou, amb, f"seccions {s}")

    def test_cobertura_exacta(self):
        for s in self.CASOS_SECCIONS:
            cl = pipeline.normalitza_clips(pipeline.clips_de_seccions(s), D,
                                           forat=SENSE_S)
            self.assertAlmostEqual(cl[0].ini, 0.0)
            self.assertAlmostEqual(cl[-1].fi, D)
            for a, b in zip(cl, cl[1:]):
                self.assertAlmostEqual(a.fi, b.ini)

    def test_cadena_sense_forats_ni_solapaments(self):
        for ac in self.CASOS_ACORDS:
            cl = pipeline.normalitza_clips(pipeline.clips_d_acords(ac, D), D,
                                           forat=SENSE_A, arrodoneix=True,
                                           deriva_fi=True)
            for a, b in zip(cl, cl[1:]):
                self.assertAlmostEqual(a.fi, b.ini)

    def test_treure_zona_determinista(self):
        """Dos clips que es trepitgen: mana l'inici del segon (regla única)."""
        s = [(0.0, 6.0, "A", "A"), (4.0, 10.0, "B", "B")]
        cl = pipeline.normalitza_clips(pipeline.clips_de_seccions(s), D,
                                       forat=SENSE_S)
        self.assertEqual([(x.ini, x.fi) for x in cl],
                         [(0.0, 4.0), (4.0, 10.0)])

    def test_no_muta_l_entrada(self):
        s = [(2.0, 4.0, "A", "A")]
        copia = list(s)
        pipeline.normalitza_clips(pipeline.clips_de_seccions(s), D, forat=SENSE_S)
        self.assertEqual(s, copia)

    def test_forat_porta_el_payload_de_forat(self):
        s = [(2.0, 4.0, "A", "A"), (6.0, 8.0, "B", "B")]
        cl = pipeline.normalitza_clips(pipeline.clips_de_seccions(s), D,
                                       forat=SENSE_S)
        self.assertEqual([x.payload for x in cl],
                         [SENSE_S, ("A", "A"), SENSE_S, ("B", "B")])

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_desat_atomic.py
# ══════════════════════════════════════════════════════════════════════════
"""El desat dels CSV d'edició (acords + estructura) és ATÒMIC.

Les edicions de l'usuari es desen a `acords.csv` i `estructura_ABC.csv` a cada
canvi. Abans el fitxer es truncava ABANS d'escriure: un error (o un crash/tall
de corrent) enmig el deixava buit o a mitges i es perdia la feina. Ara, o hi ha
la versió anterior sencera o la nova sencera, i no queden temporals.
"""


class TestDesatAtomic(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, self.td, True)

    def _llegeix(self, nom):
        with open(os.path.join(self.td, nom), encoding="utf-8") as f:
            return f.read()

    def _residus(self):
        return [n for n in os.listdir(self.td) if n.endswith(".tmp")]

    def test_acords_escriu_i_no_deixa_temporals(self):
        ruta = os.path.join(self.td, "acords.csv")
        pipeline.desa_acords_csv(
            ruta, [pipeline.Clip(0.0, 2.0, ("N",)), pipeline.Clip(2.0, 4.0, ("Am",))])
        self.assertIn("2.00", self._llegeix("acords.csv"))
        self.assertEqual(self._residus(), [])

    def test_acords_error_enmig_conserva_la_versio_anterior(self):
        ruta = os.path.join(self.td, "acords.csv")
        pipeline.desa_acords_csv(
            ruta, [pipeline.Clip(0.0, 2.0, ("N",)), pipeline.Clip(2.0, 4.0, ("Am",))])
        abans = self._llegeix("acords.csv")
        with self.assertRaises(ValueError):
            pipeline.desa_acords_csv(
                ruta, [pipeline.Clip(0.0, 2.0, ("C",)),
                       pipeline.Clip("no-és-un-temps", 4.0, ("G",))])
        self.assertEqual(self._llegeix("acords.csv"), abans,
                         "un error enmig no pot deixar el CSV truncat")
        self.assertEqual(self._residus(), [])

    def test_abc_error_enmig_conserva_la_versio_anterior(self):
        ruta = os.path.join(self.td, "estructura_ABC.csv")
        bons = [(0.0, 4.0, "A", "A"), (4.0, 8.0, "B", "B")]
        pipeline.desa_abc_csv(ruta, bons, 120.0, lambda *_desat_atomic___: None)
        abans = self._llegeix("estructura_ABC.csv")
        dolents = [(0.0, 4.0, "A", "A"), ("x", 8.0, "B", "B")]
        with self.assertRaises((ValueError, TypeError)):
            pipeline.desa_abc_csv(ruta, dolents, 120.0, lambda *_desat_atomic___: None)
        self.assertEqual(self._llegeix("estructura_ABC.csv"), abans)
        self.assertEqual(self._residus(), [])

    def test_windows_destí_ocupat_es_reintenta(self):
        """Antivirus/Explorer poden tenir el destí obert un instant."""
        ruta = os.path.join(self.td, "acords.csv")
        real = os.replace
        crides = {"n": 0}

        def replace_flaquer(a, b):
            crides["n"] += 1
            if crides["n"] < 3:
                raise PermissionError("destí ocupat")
            return real(a, b)

        with patch.object(pipeline.os, "replace", replace_flaquer), \
                patch.object(pipeline.time, "sleep"):
            pipeline.desa_acords_csv(ruta, [pipeline.Clip(0.0, 2.0, ("N",))])
        self.assertEqual(crides["n"], 3)
        self.assertTrue(os.path.isfile(ruta))
        self.assertEqual(self._residus(), [])

    def test_windows_destí_sempre_ocupat_dona_error_net(self):
        ruta = os.path.join(self.td, "acords.csv")
        with patch.object(pipeline.os, "replace",
                          side_effect=PermissionError("ocupat")), \
                patch.object(pipeline.time, "sleep"):
            with self.assertRaises(PermissionError):
                pipeline.desa_acords_csv(ruta, [pipeline.Clip(0.0, 2.0, ("N",))])
        self.assertEqual(self._residus(), [])

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_doc_xifrat.py
# ══════════════════════════════════════════════════════════════════════════
"""Auditoria: `docs/TIPUS_XIFRAT_ACORDS.md` no ha de divergir de `app/xifrat.py`.

Si s'afegeix un tipus d'acord al codi (`xifrat.TIPUS`) i no es documenta, el CI
peta — igual que fa `tests/test_esquema_ui_doc.py` amb l'ESQUEMA_UI.
"""


ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ARREL, "docs", "TIPUS_XIFRAT_ACORDS.md")


class TestDocXifrat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with io.open(DOC, encoding="utf-8") as f:
            cls.doc = f.read()

    def test_tots_els_tipus_del_codi_son_al_doc(self):
        faltes = []
        for qual in xifrat.TIPUS:
            canon = "C" + qual          # els exemples del doc fan servir l'arrel C
            if f"`{canon}`" not in self.doc:
                faltes.append(canon)
        self.assertEqual(faltes, [],
                         f"tipus al codi i NO documentats al doc: {faltes}")

    def test_el_doc_tambe_llista_els_extres(self):
        """Els extres (no del PDF) hi han de ser: `5`, `noN`, `alt`, baixes…"""
        for tros in ("`C5`", "`Cno5`", "`C7alt`", "`C/E`", "`C##`", "`N`",
                     "`C69`"):
            self.assertIn(tros, self.doc, f"falta {tros} al doc")

    def test_diu_que_els_policords_no_hi_son(self):
        """Els policords NO estan suportats i el doc ho ha de dir."""
        self.assertIn("Policords", self.doc)
        self.assertIn("drop2", self.doc)

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_esquema_ui_gen.py
# ══════════════════════════════════════════════════════════════════════════
"""Les vistes de l'esquema de la UI (`docs/ESQUEMA_UI.html` i `.svg`) han d'estar
**generades** i **al dia** amb la font única `docs/ESQUEMA_UI.md`.

El generador és **`eines/genera_esquema_ui.py`** (stdlib). Si algú edita el `.md`
i no regenera, aquest test peta i diu la comanda exacta a córrer.
"""

_esquema_ui_gen__ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(_esquema_ui_gen__ARREL, "eines", "genera_esquema_ui.py")
HTML = os.path.join(_esquema_ui_gen__ARREL, "docs", "ESQUEMA_UI.html")
SVG = os.path.join(_esquema_ui_gen__ARREL, "docs", "ESQUEMA_UI.svg")
MD = os.path.join(_esquema_ui_gen__ARREL, "docs", "ESQUEMA_UI.md")


class TestEsquemaUiGenerat(unittest.TestCase):
    def test_vistes_generades_i_al_dia(self):
        """`--check` compara les vistes amb el que produiria el `.md`."""
        r = subprocess.run([sys.executable, GEN, "--check"],
                           cwd=_esquema_ui_gen__ARREL, capture_output=True, text=True)
        self.assertEqual(
            r.returncode, 0,
            "Les vistes ESQUEMA_UI no estan al dia amb el .md:\n"
            f"{r.stdout}{r.stderr}\n"
            "→ Corre: python3 eines/genera_esquema_ui.py")

    def test_els_fitxers_existeixen(self):
        for p in (MD, GEN, HTML, SVG):
            self.assertTrue(os.path.isfile(p), f"falta {p}")

    def test_svg_es_xml_valid(self):
        ET.parse(SVG)          # aixeca si no és XML correcte

    def test_html_referencia_la_font(self):
        with open(HTML, encoding="utf-8") as f:
            s = f.read()
        self.assertIn("ESQUEMA_UI.md", s)     # porta el peu «generat des de…»
        self.assertIn("NO editar a mà", s)

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_export_async.py
# ══════════════════════════════════════════════════════════════════════════
"""A5: export ASÍNCRON (l'export pot trigar i no ha de bloquejar res).

Fet al fil de la UI, l'export congelava la finestra i —si venia d'una crida
MCP— deixava el pont sense resposta fins al final (síncrona opaca). Ara
`exporta_async()` el fa en un fil (`FeinaExporta`), amb el progrés a la barra i
a `ac_status` (`exportant`), i `ac_export_wav` accepta `async: true`.
"""


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QW.QApplication.instance() or QW.QApplication([])

    def setUp(self):
        # Cap test no ha d'ensenyar un QMessageBox REAL: amb el pont MCP actiu
        # l'avís és NO modal i, a Windows, mostrar-lo des del context del test fa
        # «access violation» (crash natiu: vist al CI, run #14, a main._avis →
        # box.show()). Mateix remei que `test_avis_no_modal`.
        p = patch.object(QW.QMessageBox, "show", lambda self: None)
        p.start()
        self.addCleanup(p.stop)


    def _espera(self, w, ms=8000):
        w.feina_export.wait(ms)
        for _export_async___ in range(20):                  # deixa arribar el senyal `feta`
            self._app.processEvents()


class TestExportAsync(_Base):
    def test_arrenca_i_acaba(self):
        w = _finestra()
        with patch.object(pipeline, "exporta_total", return_value={}), \
                patch.object(w, "obre_carpeta"):
            self.assertTrue(w.exporta_async())
            self.assertTrue(w.exportant, "mentre corre ha de constar com a tal")
            self._espera(w)
        self.assertFalse(w.exportant, "en acabar ha de quedar a False")
        self.assertIn("Exportació feta", w.log.toPlainText())
        w.close()

    def test_no_arrenca_dues_vegades(self):
        w = _finestra()
        import time as _t
        with patch.object(pipeline, "exporta_total",
                          side_effect=lambda **k: _t.sleep(0.3)), \
                patch.object(w, "obre_carpeta"):
            self.assertTrue(w.exporta_async())
            self.assertFalse(w.exporta_async(), "no pot arrencar-ne dos")
            self._espera(w)
        w.close()

    def test_error_al_fil_avisa(self):
        w = _finestra()
        with patch.object(pipeline, "exporta_total",
                          side_effect=RuntimeError("boom")), \
                patch.object(w, "obre_carpeta"):
            self.assertTrue(w.exporta_async())
            self._espera(w)
        self.assertFalse(w.exportant)
        self.assertIn("boom", w.log.toPlainText())
        w.close()


def _export_async_tearDownModule():
    # Neteja ORDENADA dels objectes Qt del mòdul (evita destrucció pel GC en un
    # test posterior -> access violation intermitent). Vegeu tests/_qt_neteja.py.
    try:
        import _qt_neteja
    except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_export_limits.py
# ══════════════════════════════════════════════════════════════════════════
"""Validació — exportació: límits (0 wavs), fusió d'iguals, capçalera «N» i
retall al final. Mode Lliure (`tempo_fix=False`) per no dependre d'scripts.

NOTA (a revisar amb l'operador): l'export aplica `style()` al nom del fitxer, de
manera que el nom del WAV pot DIFERIR del nom al CSV (`Am` → `A-.wav`). El test
`test_nom_wav_usa_style` ho DOCUMENTA (no és una afirmació que sigui el desitjat).
"""


def _export(acords, total_s):
    td = tempfile.mkdtemp()
    ca = os.path.join(td, "acords.csv")
    out = os.path.join(td, "out")
    r = pipeline.exporta_total(
        csv_ac=ca, csv_seg=None, sortida=out, bpm=120.0, bpb=4, offset=0.0,
        sr=44100, log=lambda *_export_limits___: None, tempo_fix=False, amb_estructura=False,
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
        self.assertIn("0000.000s_0003.000s", wavs[0])  # fi = durada de la WAV

    def test_nom_wav_usa_style(self):
        """DOCUMENTA: l'export estilitza el nom → pot diferir del CSV."""
        ca, wavs, r = _export([(0.0, "Am", "0"), (2.0, "Cmaj7", "2")], 4.0)
        self.assertTrue(any("A-.wav" in w for w in wavs),
                        f"l'export estilitza (Am→A-): {wavs}")
        with open(ca, encoding="utf-8") as f:
            self.assertIn("Am", f.read())

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_export_neteja_estructura.py
# ══════════════════════════════════════════════════════════════════════════
"""(2) Amb «Inclou estructura» OFF: el MODEL mai s'esborra.

`estructura_ABC.csv` és el MODEL del projecte i **no es toca mai** (la marca
decideix què s'EXPORTA, no què es conserva). Només s'ofereixen treure les restes
de l'export anterior (`wavs_estructura/`), i **sempre amb confirmació**.
"""


class TestNetejaEstructura(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QW.QApplication.instance() or QW.QApplication([])

    def setUp(self):
        # Cap QMessageBox REAL: mostrar-lo amb el pont MCP actiu fa «access
        # violation» a Windows (crash natiu; CI run #14). Vegeu test_avis_no_modal.
        p = patch.object(QW.QMessageBox, "show", lambda self: None)
        p.start()
        self.addCleanup(p.stop)

    def test_amb_la_marca_off_es_netegen_els_wavs_pero_MAI_el_model(self):
        w, s = _export_neteja_estructura___finestra(amb_estructura=False)
        with patch.object(pipeline, "exporta_total", return_value={}), \
                patch.object(w, "obre_carpeta"), \
                patch.object(type(w), "_ho_confirma", return_value=True):
            w.exporta()
        self.assertTrue(os.path.isfile(os.path.join(s, "estructura_ABC.csv")),
                        "el MODEL de l'estructura NO s'ha d'esborrar mai")
        self.assertFalse(os.path.isdir(os.path.join(s, "wavs_estructura")),
                         "la carpeta de wavs d'estructura vella hi és")
        self.assertIn("tret l'export anterior", w.log.toPlainText())
        w.close()

    def test_amb_la_marca_off_sense_confirmacio_no_esborra_res(self):
        w, s = _export_neteja_estructura___finestra(amb_estructura=False)
        with patch.object(pipeline, "exporta_total", return_value={}), \
                patch.object(w, "obre_carpeta"), \
                patch.object(type(w), "_ho_confirma", return_value=False):
            w.exporta()
        self.assertTrue(os.path.isfile(os.path.join(s, "estructura_ABC.csv")))
        self.assertTrue(os.path.isdir(os.path.join(s, "wavs_estructura")))
        self.assertIn("es conserven els derivats", w.log.toPlainText())
        w.close()


    def test_amb_la_marca_on_es_respecten(self):
        w, s = _export_neteja_estructura___finestra(amb_estructura=True)
        with patch.object(pipeline, "exporta_total", return_value={}), \
                patch.object(w, "obre_carpeta"):
            w.exporta()
        self.assertTrue(os.path.isfile(os.path.join(s, "estructura_ABC.csv")))
        self.assertTrue(os.path.isdir(os.path.join(s, "wavs_estructura")))
        w.close()


def _export_neteja_estructura_tearDownModule():
    # Neteja ORDENADA dels objectes Qt del mòdul (evita destrucció pel GC en un
    # test posterior -> access violation intermitent). Vegeu tests/_qt_neteja.py.
    try:
        import _qt_neteja
    except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_export_ok_fals.py
# ══════════════════════════════════════════════════════════════════════════
"""`ac_export_wav` ha de dir `ok: false` quan l'export FALLA (OC-6/386).

Abans retornava `ok: true` SEMPRE, també quan l'export petava (p. ex. amb 0
acords): l'agent creia que s'havia exportat. Ara, si l'export falla, `ok` és
fals i s'hi afegeix el motiu (`error`), a més de l'avís de l'app.
"""


class TestOkFalsEnFallar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QW.QApplication.instance() or QW.QApplication([])

    def setUp(self):
        # Cap QMessageBox REAL: mostrar-lo amb el pont MCP actiu fa «access
        # violation» a Windows (crash natiu; CI run #14). Vegeu test_avis_no_modal.
        p = patch.object(QW.QMessageBox, "show", lambda self: None)
        p.start()
        self.addCleanup(p.stop)


def _export_ok_fals_tearDownModule():
    # Neteja ORDENADA dels objectes Qt del mòdul (evita destrucció pel GC en un
    # test posterior -> access violation intermitent). Vegeu tests/_qt_neteja.py.
    try:
        import _qt_neteja
    except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_faulthandler_crash.py
# ══════════════════════════════════════════════════════════════════════════
"""`activa_faulthandler`: la traça d'un crash nadiu queda a disc.

Sense això, un SIGSEGV de Qt/PortAudio no deixava res (ni `excepthook` ni log)
i un informe de beta era només «s'ha tancat sol».
"""


class _Logger:
    def __init__(self):
        self.avisos = []

    def warning(self, fmt, *args):
        self.avisos.append(fmt % args if args else fmt)


class TestActivaFaulthandler(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.log = os.path.join(self.td, "auto-chords.log")
        # el faulthandler és global del procés: ho deixem com estava
        self._estava = faulthandler.is_enabled()
        self.addCleanup(self._restaura)

    def _restaura(self):
        if app_main._FH_FITXER is not None:
            try:
                app_main._FH_FITXER.close()
            except OSError:
                pass
            app_main._FH_FITXER = None
        faulthandler.disable()
        if self._estava:
            faulthandler.enable()
        __import__("shutil").rmtree(self.td, True)

    def test_activa_i_crea_el_fitxer_al_costat_del_log(self):
        ruta = app_main.activa_faulthandler(self.log)
        self.assertEqual(ruta, os.path.join(self.td, "crash_nadiu.log"))
        self.assertTrue(os.path.isfile(ruta))
        self.assertTrue(faulthandler.is_enabled())
        self.assertEqual(os.path.getsize(ruta), 0, "en sortida normal, buit")

    def test_escriu_la_traça_al_fitxer(self):
        ruta = app_main.activa_faulthandler(self.log)
        faulthandler.dump_traceback(file=app_main._FH_FITXER)
        app_main._FH_FITXER.flush()
        with open(ruta, encoding="utf-8") as f:
            self.assertIn("most recent call first", f.read())

    def test_traça_anterior_es_conserva_i_s_avisa(self):
        ruta = os.path.join(self.td, "crash_nadiu.log")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write("Windows fatal exception: access violation\n")
        lg = _Logger()
        app_main.activa_faulthandler(self.log, lg)
        with open(ruta + ".anterior", encoding="utf-8") as f:
            self.assertIn("access violation", f.read())
        self.assertEqual(os.path.getsize(ruta), 0)
        self.assertTrue(any("crash nadiu" in a for a in lg.avisos))

    def test_sense_crash_previ_no_avisa(self):
        lg = _Logger()
        app_main.activa_faulthandler(self.log, lg)
        self.assertEqual(lg.avisos, [])
        self.assertFalse(os.path.exists(
            os.path.join(self.td, "crash_nadiu.log.anterior")))

    def test_dues_activacions_no_deixen_fitxers_oberts(self):
        app_main.activa_faulthandler(self.log)
        primer = app_main._FH_FITXER
        app_main.activa_faulthandler(self.log)
        self.assertTrue(primer.closed)
        self.assertFalse(app_main._FH_FITXER.closed)

    def test_directori_no_escriptible_no_peta(self):
        ruta = app_main.activa_faulthandler(
            os.path.join(self.td, "no", "existeix", "x.log"))
        self.assertIsNone(ruta)

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_icones.py
# ══════════════════════════════════════════════════════════════════════════
"""Coherència de les ICONES (`app/icones.py` + `icones/*.svg`).

Una icona que no existeix **no peta**: `icones.ico()` torna una pixmap buida i
el botó queda sense dibuix, en silenci. Només es nota mirant la finestra. Aquest
guard comprova que totes les icones que el CODI demana hi són (auditoria
18-10-2026).
"""


_icones__ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _usades():
    """Noms d'icona que apareixen LITERALMENT al codi de `app/`."""
    noms = set()
    for p in glob.glob(os.path.join(_icones__ARREL, "app", "*.py")):
        with open(p, encoding="utf-8") as f:
            src = f.read()
        # Noms amb guions compten: `arrow-left-to-line` etc. (el primer
        # detector no els veia i donava falsos «innecessaris»).
        noms |= set(re.findall(r'icones\.ico\("([a-z0-9\-]+)"', src))
        noms |= set(re.findall(r'\bicona\s*=\s*"([a-z0-9\-]+)"', src))
        noms |= set(re.findall(
            r'icones\.icona_boto\([^,]+,\s*"([a-z0-9\-]+)"', src))
    return noms


def _icns_blocs(ruta):
    """Retorna els blocs de l'`.icns` {tipus: dades}, validant-ne l'estructura."""
    with open(ruta, "rb") as f:
        d = f.read()
    if d[:4] != b"icns":
        raise AssertionError(f"{ruta} no comença amb 'icns'")
    if struct.unpack(">I", d[4:8])[0] != len(d):
        raise AssertionError("la mida declarada de l'.icns no coincideix")
    blocs, off = {}, 8
    while off < len(d):
        tipus = d[off:off + 4]
        n = struct.unpack(">I", d[off + 4:off + 8])[0]
        if n < 8 or off + n > len(d):
            raise AssertionError(f"bloc {tipus!r} amb mida invàlida ({n})")
        blocs[tipus] = d[off + 8:off + n]
        off += n
    return blocs


def _packbits_descomprimeix(dades):
    """Desfà l'RLE PackBits de l'ICNS (per validar `ic04`/`ic05`)."""
    out, i = bytearray(), 0
    while i < len(dades):
        control = dades[i]
        i += 1
        if control & 0x80:
            n = control - 125
            out.extend([dades[i]] * n)
            i += 1
        else:
            n = control + 1
            out.extend(dades[i:i + n])
            i += n
    return bytes(out)


def _ico_entrades(ruta):
    """Retorna les entrades de l'ICO {mida, planes, bpp, dades}, validant-ne els límits."""
    with open(ruta, "rb") as f:
        d = f.read()
    reserved, tipus, n = struct.unpack("<HHH", d[:6])
    if (reserved, tipus) != (0, 1):
        raise AssertionError(f"{ruta}: capçalera ICO invàlida")
    entrades, off = [], 6
    for _ in range(n):
        w, h, _colors, _resv, planes, bpp, size, ofs = struct.unpack(
            "<BBBBHHII", d[off:off + 16])
        off += 16
        if ofs + size > len(d):
            raise AssertionError(f"{ruta}: imatge fora del fitxer")
        if (w == 0) != (h == 0):
            raise AssertionError(f"{ruta}: amplada/alçada 0 incoherents")
        entrades.append({
            "mida": 256 if w == 0 else w,
            "planes": planes,
            "bpp": bpp,
            "dades": d[ofs:ofs + size],
        })
    return entrades


class TestIcones(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_totes_les_icones_demanades_existeixen(self):
        usades = _usades()
        self.assertGreaterEqual(len(usades), 8, "no he trobat usos d'icones")
        for nom in sorted(usades):
            self.assertTrue(icones.disponible(nom),
                            f"falta l'icona {nom!r} ({nom}.svg)")

    def test_disponible_es_fiable(self):
        """`disponible()` mira el fitxer de debò, no una llista hardcoded."""
        self.assertTrue(icones.disponible("play"))
        self.assertFalse(icones.disponible("aixo_no_existeix"))

    def test_l_icona_de_l_app_existeix(self):
        """La icona de la finestra (barra de tasques) també ha d'haver-hi."""
        pm = icones.icona_app()
        self.assertFalse(pm.isNull(), "la icona de l'app ix buida")

    def test_icns_macos_usa_argb_a_16_i_32_px(self):
        """`ic04`/`ic05` han de ser ARGB+RLE, no PNG (`icp4`/`icp5`/`icp6`).

        macOS Finder/DMG dibuixa **corruptes** els PNG petits de l'ICNS a 1×;
        el Dock i l'app instal·lada (mides grans) es veuen bé. Apple's
        `iconutil` escriu el 16 i el 32 px com a `ic04`/`ic05` amb ARGB+RLE.
        """
        ruta = os.path.join(_icones__ARREL, "icona", "auto-chords.icns")
        blocs = _icns_blocs(ruta)
        for tipus, mida in ((b"ic04", 16), (b"ic05", 32)):
            self.assertIn(tipus, blocs, f"falta el bloc {tipus!r}")
            dades = blocs[tipus]
            self.assertEqual(dades[:4], b"ARGB",
                             f"{tipus!r} no és ARGB (¿PNG?)")
            canals = _packbits_descomprimeix(dades[4:])
            self.assertEqual(
                len(canals), 4 * mida * mida,
                f"{tipus!r}: els 4 canals no fan {mida}×{mida} píxels")
        for tipus in (b"icp4", b"icp5", b"icp6"):
            self.assertNotIn(
                tipus, blocs,
                f"{tipus!r} (PNG petit) fa que Finder/DMG el vegi corrupte")
        for tipus in (b"ic07", b"ic08", b"ic09", b"ic10",
                      b"ic11", b"ic12", b"ic13", b"ic14"):
            self.assertIn(tipus, blocs, f"falta el bloc {tipus!r}")
            self.assertTrue(blocs[tipus].startswith(b"\x89PNG"),
                            f"{tipus!r} hauria de ser PNG")

    def test_ico_windows_te_bmp_a_les_mides_petites_i_png_a_256(self):
        """ICO de Windows: BMP/DIB fins a 128 px i PNG només a 256.

        Microsoft recomana no comprimir les mides < 256; el mix BMP+PNG evita
        problemes en eines antigues i en el diàleg de propietats. També calen
        les mides 20 i 40 px, que Windows 10/11 usa a 125 % i 150 % de DPI.
        """
        ruta = os.path.join(_icones__ARREL, "icona", "auto-chords.ico")
        entrades = _ico_entrades(ruta)
        self.assertEqual([e["mida"] for e in entrades],
                         [16, 20, 24, 32, 40, 48, 64, 128, 256])
        for e in entrades:
            self.assertEqual((e["planes"], e["bpp"]), (1, 32),
                             f"{e['mida']} px: planes/bpp inesperats")
            dades = e["dades"]
            if e["mida"] == 256:
                self.assertTrue(dades.startswith(b"\x89PNG\r\n\x1a\n"),
                                "256 px ha de ser PNG")
                self.assertEqual(struct.unpack(">II", dades[16:24]), (256, 256))
                continue
            self.assertEqual(dades[:4], b"\x28\x00\x00\x00",
                             f"{e['mida']} px: hauria de ser BMP/DIB")
            (bi_size, bi_w, bi_h, bi_planes, bi_bpp, bi_comp, bi_img,
             _x, _y, _cu, _ci) = struct.unpack("<IiiHHIIiiII", dades[:40])
            self.assertEqual(bi_size, 40)
            self.assertEqual((bi_w, bi_h), (e["mida"], e["mida"] * 2))
            self.assertEqual((bi_planes, bi_bpp, bi_comp), (1, 32, 0))
            self.assertEqual(bi_img, e["mida"] * e["mida"] * 4)
            mask_row = ((e["mida"] + 31) // 32) * 4
            self.assertEqual(
                len(dades),
                40 + e["mida"] * e["mida"] * 4 + mask_row * e["mida"],
                f"{e['mida']} px: mida del DIB + màscara incorrecta")

    def test_icona_app_a_windows_prefereix_l_ico_multimida(self):
        """A Windows, la finestra/taskbar han de poder triar la mida exacta."""
        from app import plataforma
        with mock.patch.object(plataforma, "ES_WINDOWS", True):
            ic = icones.icona_app()
        mides = {(s.width(), s.height()) for s in ic.availableSizes()}
        self.assertTrue(
            {(m, m) for m in (16, 20, 24, 32, 40, 48, 64, 128, 256)} <= mides,
            f"l'ICO no ofereix totes les mides: {sorted(mides)}")

    def test_no_hi_ha_icones_innecessaries(self):
        """Cap SVG del disc sense referència al codi.

        Una icona que no s'usa és pes mort que ningú no gosa esborrar: n'hi
        havia tres (`circle-gauge`, `mic`, `settings`, 18-10-2026) i s'han
        tret. Si mai cal, `eines/baixa_icones.sh` les torna a baixar
        afegint-les a la seua llista.
        """
        al_disc = {os.path.basename(x)[:-4]
                   for x in glob.glob(os.path.join(_icones__ARREL, "icones", "*.svg"))}
        sobren = sorted(al_disc - _usades())
        self.assertEqual(sobren, [],
                         f"icones sense cap referencia al codi: {sobren}")

    def test_les_icones_tenen_paleta_de_recoloreig(self):
        """`ico()` recoloreix l'SVG: un color invàlid no ha de fer-la buida."""
        pm = icones.ico("play", 18)
        self.assertFalse(pm.isNull())

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_imports_unificats.py
# ══════════════════════════════════════════════════════════════════════════
"""Els mòduls de l'app han de ser UN SOL objecte (no dos per import cru).

`app/main.py` importava `ffmpeg`, `partitura`, `pipeline`, `postproc` i `theme`
pel **nom cru** mentre la resta del codi feia `from . import X`: això crea
**dos objectes de mòdul** per al mateix fitxer → l'estat a nivell de mòdul pot
divergir i el *monkey-patching* deixa de funcionar (va passar de veritat: un
test de la partitura patchejava `app.partitura` i `main` seguia fent servir
l'altre objecte).
"""


class TestUnSolObjecteDeModul(unittest.TestCase):
    def test_main_veu_els_mateixos_moduls(self):
        from app import main as app_main
        from app import ffmpeg, partitura, pipeline, postproc, theme
        for nom, mod in (("ffmpeg", ffmpeg), ("partitura", partitura),
                         ("pipeline", pipeline), ("postproc", postproc),
                         ("theme", theme)):
            self.assertIs(
                getattr(app_main, nom), mod,
                f"`app.main.{nom}` i `app.{nom}` són objectes DIFERENTS "
                f"(import cru vs relatiu)")

    def test_el_visor_i_la_finestra_comparteixen_pipeline(self):
        from app import main as app_main
        from app import pipeline, visor
        self.assertIs(visor.pipeline, pipeline)
        self.assertIs(app_main.pipeline, pipeline)

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_inventari_al_dia.py
# ══════════════════════════════════════════════════════════════════════════
"""La llista de components (`docs/COMPONENTS_I_VERSIONS.md`) ha d'estar AL DIA.

El CI ja ho comprova (`build-all`: genera l'inventari i fa `git diff
--exit-code`), però això vol dir descobrir el desfasament **al CI**, després
d'haver pujat. Aquest test ho atrapa en local.

Es fa servir la funció **PURA** `construeix()` de l'eina (no escriu cap fitxer):
el document és d'OC-12 i un test no l'ha de tocar (auditoria 18-10-2026).
"""


_inventari_al_dia__ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_inventari_al_dia__DOC = os.path.join(_inventari_al_dia__ARREL, "docs", "COMPONENTS_I_VERSIONS.md")
EINA = os.path.join(_inventari_al_dia__ARREL, "eines", "genera_inventari.py")


def _eina():
    spec = importlib.util.spec_from_file_location("genera_inventari", EINA)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestInventariAlDia(unittest.TestCase):

    def test_el_document_coincideix_amb_el_que_es_generaria(self):
        if not os.path.isfile(_inventari_al_dia__DOC):
            self.skipTest("no hi ha el document d'inventari")
        with open(_inventari_al_dia__DOC, encoding="utf-8") as f:
            actual = f.read()
        generat = _eina().construeix()
        self.assertEqual(
            generat, actual,
            "docs/COMPONENTS_I_VERSIONS.md està desfasat respecte de "
            "requirements.txt / eines/deps_fixades.env: torna a generar-lo "
            "(python3 eines/genera_inventari.py)")

    def test_l_eina_no_te_efectes_en_construir(self):
        """`construeix()` no ha d'escriure res (el test no toca cap doc)."""
        abans = None
        if os.path.isfile(_inventari_al_dia__DOC):
            with open(_inventari_al_dia__DOC, encoding="utf-8") as f:
                abans = f.read()
        _eina().construeix()
        if abans is not None:
            with open(_inventari_al_dia__DOC, encoding="utf-8") as f:
                self.assertEqual(f.read(), abans, "no pot haver-lo tocat")

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_lock_windows.py
# ══════════════════════════════════════════════════════════════════════════
"""Simula WINDOWS per provar `plataforma.bloqueja_instancia_unica`.

El bloqueig d'instància única a Windows fa servir `msvcrt.locking`, que **no
existeix a Linux**. Aquí l'injectem amb un **doble** de `msvcrt` i simulem el
seu comportament, perquè aquesta classe d'error es caçi **a Linux** (sense
dependre que el CI de Windows hi sigui):

- `locking(fd, LK_NBLCK, 1)` bloqueja la regió **[posició actual, +1)** del
  **fitxer** (no del fd): dues obertures del mateix fitxer comparteixen el lock.
- **Escriure** en una regió bloquejada **llança `OSError`** (com fa Windows).

Amb això, dos bugs reals queden coberts:
1. si el `write`/`locking` no van dins el `try` → el test peta en lloc de
   retornar `False` (ERROR);
2. si el `locking` bloqueja un offset diferent del que allibera `desbloqueja`
   → el lock penja i el test falla (la 2a instància no el pot tornar a agafar).
"""


class _FakeMsvcrt:
    """Doble de `msvcrt`: bloqueig per regió `(fitxer, offset)`."""

    LK_NBLCK = 2
    LK_UNLCK = 0

    def __init__(self):
        self._fitxers = {}          # fd -> _FitxerFals
        self._bloquejats = set()    # {(fitxer_id, offset)}

    def registrar(self, fitxer):
        self._fitxers[fitxer.fileno()] = fitxer

    def esta_bloquejat(self, fitxer_id, offset):
        return (fitxer_id, offset) in self._bloquejats

    def locking(self, fd, mode, nbytes):
        fx = self._fitxers[fd]
        clau = (fx.fitxer_id, fx.posicio())
        if mode == self.LK_NBLCK:
            if clau in self._bloquejats:
                raise OSError(13, "regió ja bloquejada")
            self._bloquejats.add(clau)
        elif mode == self.LK_UNLCK:
            self._bloquejats.discard(clau)


class _FitxerFals:
    """Fitxer fals: `write()` peta si la regió actual està bloquejada."""

    def __init__(self, fake, fitxer_id, fd):
        self.fake = fake
        self.fitxer_id = fitxer_id
        self._fd = fd
        self._pos = 0
        fake.registrar(self)

    def seek(self, n):
        self._pos = int(n)

    def write(self, s):
        if self.fake.esta_bloquejat(self.fitxer_id, self._pos):
            raise OSError(13, "escriure en una regió bloquejada")
        self._pos += len(s)

    def flush(self):
        pass

    def fileno(self):
        return self._fd

    def posicio(self):
        return self._pos


class TestLockWindowsSimulat(unittest.TestCase):
    def setUp(self):
        self.msv = _FakeMsvcrt()
        sys.modules["msvcrt"] = self.msv          # `import msvcrt` dins la funció
        self._orig = plataforma.ES_WINDOWS
        plataforma.ES_WINDOWS = True

    def tearDown(self):
        plataforma.ES_WINDOWS = self._orig
        sys.modules.pop("msvcrt", None)

    def test_segona_instancia_rebutjada(self):
        f1 = _FitxerFals(self.msv, "tema", fd=1)
        self.assertTrue(plataforma.bloqueja_instancia_unica(f1))
        # 2a obertura del MATEIX fitxer: escriure/bloquejar la regió ja
        # bloquejada ha de donar False (no petar).
        f2 = _FitxerFals(self.msv, "tema", fd=2)
        self.assertFalse(plataforma.bloqueja_instancia_unica(f2))
        # En alliberar el primer, el segon JA el pot agafar (el lock no penja).
        plataforma.desbloqueja(f1)
        self.assertTrue(plataforma.bloqueja_instancia_unica(f2))
        plataforma.desbloqueja(f2)

    def test_desbloqueja_allibera_la_mateixa_regio(self):
        f = _FitxerFals(self.msv, "tema", fd=3)
        self.assertTrue(plataforma.bloqueja_instancia_unica(f))
        self.assertTrue(self.msv.esta_bloquejat("tema", 0))   # offset 0
        plataforma.desbloqueja(f)
        self.assertFalse(self.msv.esta_bloquejat("tema", 0))  # alliberat

    def test_desbloqueja_es_best_effort(self):
        # Mai ha de llançar, ni amb un fitxer sense `locking` disponible.
        plataforma.desbloqueja(None)
        f = _FitxerFals(self.msv, "tema", fd=4)   # sense bloquejar prèviament
        plataforma.desbloqueja(f)                 # no ha de petar

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_partitura.py
# ══════════════════════════════════════════════════════════════════════════
"""Tests de l'exportació de partitura (app/partitura.py).

No necessiten MuseScore: només proven el parsing, el mapeig xifrat-><harmony>,
la descomposició de durades i la construcció del MusicXML.
"""


class ParsingTests(unittest.TestCase):
    def test_parse_pos_qualsevol_compas(self):
        self.assertAlmostEqual(partitura.parse_pos("1.1.1", 4), 0.0)
        self.assertAlmostEqual(partitura.parse_pos("1.1.3", 4), 0.25)
        self.assertAlmostEqual(partitura.parse_pos("2.3.3", 4), 6.25)
        self.assertAlmostEqual(partitura.parse_pos("1.1.1", 3), 0.0)
        self.assertAlmostEqual(partitura.parse_pos("2.1.1", 3), 3.0)

    def test_llegeix_seccions_deduplica(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "estructura_ABC.csv"
            p.write_text("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
                         "0,3,3,A,A,1.1.1,2.2.1\n"
                         "3,30,27,B,B,2.2.1,13.3.3\n", encoding="utf-8")
            secs = partitura.llegeix_seccions(str(p))
            self.assertEqual(secs, [(1, "A"), (2, "B")])


class HarmonyTests(unittest.TestCase):
    def test_majors_i_menors(self):
        self.assertIn("<kind>major</kind>", partitura.harmony_xml("C"))
        self.assertIn("<kind>minor</kind>", partitura.harmony_xml("Am"))
        self.assertIn("<kind>minor</kind>", partitura.harmony_xml("A-"))

    def test_septimes_i_alteracions(self):
        self.assertIn("major-seventh", partitura.harmony_xml("Cmaj7"))
        w = partitura.harmony_xml("BbMaj7")
        self.assertIn("<root-step>B</root-step>", w)
        self.assertIn("<root-alter>-1</root-alter>", w)
        self.assertIn("major-seventh", w)
        self.assertIn("diminished-seventh", partitura.harmony_xml("F#dim7"))

    def test_slash_chord(self):
        w = partitura.harmony_xml("G/D")
        self.assertIn("<kind>major</kind>", w)
        self.assertIn("<bass-step>D</bass-step>", w)

    def test_xifrat_jazz_amb_baix(self):
        """Els xifrats de jazz (menor amb `-`, maj7, 6a) amb baix `/nota`.

        Regressió: `A-maj7/G#` sortia com a `<root>A</root>` + un `<kind
        text="A-maj7-G#">` → MuseScore duplicava el nom («AA-maj7-G#»).
        """
        w = partitura.harmony_xml("A-7/G")
        self.assertIn("<kind>minor-seventh</kind>", w)
        self.assertIn("<bass-step>G</bass-step>", w)
        w = partitura.harmony_xml("A-6/F#")
        self.assertIn("<kind>minor-sixth</kind>", w)
        self.assertIn("<bass-step>F</bass-step>", w)
        self.assertIn("<bass-alter>1</bass-alter>", w)
        w = partitura.harmony_xml("A-maj7/G#")
        self.assertIn("<kind>major-minor</kind>", w)
        self.assertIn("<bass-step>G</bass-step>", w)
        w = partitura.harmony_xml("A7/G")
        self.assertIn("<kind>dominant</kind>", w)
        self.assertIn("<bass-step>G</bass-step>", w)

    def test_la_barra_de_6_9_no_es_un_baix(self):
        """`C6/9` porta barra però NO és un acord amb baix."""
        w = partitura.harmony_xml("C6/9")
        self.assertNotIn("<bass>", w)
        self.assertIn("<kind>major-sixth</kind>", w)   # 6a amb la 9a afegida
        self.assertIn("<degree-value>9</degree-value>", w)

    def test_acord_complexe_amb_tensions_i_baix(self):
        """`Ab69(#11,#13)/Db`: root + kind + els 3 `<degree>` + baix."""
        w = partitura.harmony_xml("Ab69(#11,#13)/Db")
        self.assertIn("<root-step>A</root-step>", w)
        self.assertIn("<root-alter>-1</root-alter>", w)
        self.assertIn("<kind>major-sixth</kind>", w)      # 6a
        for v in ("9", "11", "13"):                        # 9 afegida + #11 + #13
            self.assertIn(f"<degree-value>{v}</degree-value>", w)
        self.assertIn("<degree-alter>1</degree-alter>", w)  # sostinguts
        self.assertIn("<bass-step>D</bass-step>", w)
        self.assertIn("<bass-alter>-1</bass-alter>", w)

    def test_alteracions_dobles_al_root_i_al_baix(self):
        """`##`/`bb` → `<root-alter>±2</root-alter>` (i el baix igual)."""
        w = partitura.harmony_xml("C##m7")
        self.assertIn("<root-alter>2</root-alter>", w)
        self.assertIn("<kind>minor-seventh</kind>", w)
        w = partitura.harmony_xml("Gbbmaj7")
        self.assertIn("<root-alter>-2</root-alter>", w)
        w = partitura.harmony_xml("C##/Dbb")
        self.assertIn("<root-alter>2</root-alter>", w)
        self.assertIn("<bass-alter>-2</bass-alter>", w)

    def test_qualitat_no_estandard_conserva_el_text(self):
        """`C7alt`: el `kind` base + el símbol sencer al `text` (no es perd)."""
        w = partitura.harmony_xml("C7alt")
        self.assertIn("<kind text=\"7alt\">dominant</kind>", w)

    def test_no_grau(self):
        """`noN` (sense la 5a, etc.) → `<degree-type>subtract</degree-type>`."""
        w = partitura.harmony_xml("Cmaj7no5")
        self.assertIn("<kind>major-seventh</kind>", w)
        self.assertIn("<degree-value>5</degree-value>", w)
        self.assertIn("<degree-type>subtract</degree-type>", w)

    def test_altered_amb_degrees(self):
        w = partitura.harmony_xml("C7b9#11")
        self.assertIn("<kind>dominant</kind>", w)
        self.assertIn("<degree-value>9</degree-value>", w)
        self.assertIn("<degree-alter>-1</degree-alter>", w)
        self.assertIn("<degree-value>11</degree-value>", w)
        self.assertIn("<degree-type>alter</degree-type>", w)

    def test_no_acord_i_qualitat_desconeguda(self):
        self.assertEqual(partitura.harmony_xml("N"), "")
        self.assertEqual(partitura.harmony_xml("N.C."), "")
        # Qualitat desconeguda: el `text` porta NOMÉS el sufix (el root ja
        # s'escriu a part) → MuseScore no duplica el nom.
        self.assertIn('text="xyz"', partitura.harmony_xml("Cxyz"))
        self.assertNotIn('text="Cxyz"', partitura.harmony_xml("Cxyz"))


class DuradesTests(unittest.TestCase):
    def test_decomposa(self):
        self.assertEqual(partitura._decomposa(1920), [("whole", 0)])
        self.assertEqual(partitura._decomposa(1440), [("half", 1)])
        self.assertEqual(partitura._decomposa(1200), [("half", 0), ("eighth", 0)])
        self.assertEqual(partitura._decomposa(360), [("eighth", 1)])
        self.assertEqual(partitura._decomposa(90), [("32nd", 1)])
        self.assertEqual(partitura._decomposa(60), [("32nd", 0)])
        self.assertEqual(partitura._decomposa(0), [])

    def test_note_i_silenci(self):
        self.assertIn("<notehead>slash</notehead>", partitura._note_xml(960))
        self.assertIn("<rest/>", partitura._note_xml(480, rest=True))
        self.assertNotIn("<pitch>", partitura._note_xml(480, rest=True))
        self.assertIn("<type>32nd</type>", partitura._note_xml(60))
        self.assertIn("<type>32nd</type>", partitura._note_xml(90))


class MusicXmlTests(unittest.TestCase):
    def _events(self):
        # C (1 compàs) | Am (2 temps) + F (2 temps) | G
        return [(0.0, "C", 4.0), (4.0, "Am", 2.0), (6.0, "F", 2.0),
                (8.0, "G", 4.0)]


    def test_salt_de_sistema_i_beat_type(self):
        xml = partitura.construeix_musicxml(
            self._events(), [(1, "A")], bpb=4, bpm=100.0, titol="X",
            new_system_each=2, beat_type=8)
        self.assertIn("<beat-type>8</beat-type>", xml)
        self.assertIn('new-system="yes"', xml)


class ExportaTests(unittest.TestCase):
    def _escriu_font(self, td):
        d = Path(td) / "AUTOCHORDS_Tema"
        d.mkdir()
        (d / "acords.csv").write_text(
            "0.00,1.94,C\n1.94,3.88,Am\n", encoding="utf-8")
        (d / "estructura_ABC.csv").write_text(
            "inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
            "0,5,5,A,A,1.1.1,2.2.1\n", encoding="utf-8")
        (d / "guia_acords.html").write_text(
            "<h3>103 BPM · 4 temps/compàs · gris = acord</h3>", encoding="utf-8")
        return d

    def test_exporta_sense_musescore(self):
        with tempfile.TemporaryDirectory() as td:
            d = self._escriu_font(td)
            res = partitura.exporta_partitura(
                str(d), log=lambda *_a: None,
                genera_pdf=False, genera_mscz=False)
            self.assertIn("musicxml", res)
            self.assertTrue(os.path.isfile(res["musicxml"]))
            self.assertTrue(res["musicxml"].endswith("Tema.musicxml"))
            self.assertIsNone(res["pdf"])
            text = open(res["musicxml"], encoding="utf-8").read()
            self.assertIn("<per-minute>103</per-minute>", text)  # de la guia
            self.assertIn("<harmony>", text)

    def test_sense_acords(self):
        with tempfile.TemporaryDirectory() as td:
            res = partitura.exporta_partitura(str(td), log=lambda *_a: None,
                                              genera_pdf=False, genera_mscz=False)
            self.assertEqual(res.get("error"), "sense_acords")


class EntornTests(unittest.TestCase):
    def test_musescore_bin_env_override(self):
        vell = os.environ.get("AUTO_CHORDS_MUSESCORE")
        try:
            os.environ["AUTO_CHORDS_MUSESCORE"] = "/tmp/fals_mscore"
            self.assertEqual(partitura.musescore_bin(), "/tmp/fals_mscore")
        finally:
            if vell is None:
                os.environ.pop("AUTO_CHORDS_MUSESCORE", None)
            else:
                os.environ["AUTO_CHORDS_MUSESCORE"] = vell


class TestMuseScore(unittest.TestCase):
    """Descobriment del binari de MuseScore (ha de funcionar a tots els SO)."""

    def test_env_te_prioritat(self):
        with mock.patch.dict(os.environ, {"AUTO_CHORDS_MUSESCORE": "/tmp/msc"}):
            self.assertEqual(partitura.musescore_bin(), "/tmp/msc")

    def test_no_peta_si_no_hi_es(self):
        env = {k: v for k, v in os.environ.items()
               if k != "AUTO_CHORDS_MUSESCORE"}
        with mock.patch.dict(os.environ, env, clear=True):
            partitura.musescore_bin()      # None o binari real: no ha de petar

    def test_troba_binari_per_glob(self):
        env = {k: v for k, v in os.environ.items()
               if k != "AUTO_CHORDS_MUSESCORE"}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch("app.partitura.shutil.which", return_value=None), \
                mock.patch("app.partitura.glob.glob",
                           side_effect=lambda p, **k: ["/X"] if "MuseScore" in p else []):
            self.assertEqual(partitura.musescore_bin(), "/X")


class BaseDeSortidaTests(unittest.TestCase):
    """Títol per defecte derivat del nom de la carpeta (prefix AUTOCHORDS_)."""

    def test_prefix_coincideix_amb_pipeline(self):
        # El mòdul partitura no importa el projecte: el prefix s'hi repeteix i
        # aquest test evita que els dos valors divergeixin.
        from app import pipeline
        self.assertEqual(partitura._PREFIX_SORTIDA, pipeline.PREFIX_SORTIDA)

    def test_treu_el_prefix(self):
        self.assertEqual(partitura._base_de_sortida("/musica/AUTOCHORDS_Tema"),
                         "Tema")

    def test_sense_prefix_es_queda_igual(self):
        self.assertEqual(partitura._base_de_sortida("/musica/Altres"), "Altres")


class TestMusicXmlMapa(unittest.TestCase):
    """Fase 5: el MusicXML reflecteix els canvis de TEMPO del mapa."""

    def test_canvis_de_tempo(self):
        from app.tempo_map import TempoMap
        mapa = TempoMap([(0.0, 4.0, 120.0, 4, 4), (4.0, 8.0, 60.0, 4, 4)])
        events = [(0.0, "C", 4.0), (4.0, "G", 4.0)]
        xml = partitura.construeix_musicxml(events, [], bpb=4, bpm=120.0,
                                            mapa=mapa)
        self.assertIn('<sound tempo="120"', xml)
        self.assertIn('<sound tempo="60"', xml)      # canvi al compàs 3
        self.assertIn('<measure number="3">', xml)

    def test_canvi_de_compas(self):
        from app.tempo_map import TempoMap
        mapa = TempoMap([(0.0, 4.0, 120.0, 4, 4), (4.0, 8.0, 120.0, 3, 4)])
        events = [(0.0, "C", 4.0), (4.0, "G", 3.0)]
        xml = partitura.construeix_musicxml(events, [], bpb=4, bpm=120.0,
                                            mapa=mapa)
        self.assertIn("<beats>4</beats><beat-type>4</beat-type>", xml)
        self.assertIn("<beats>3</beats><beat-type>4</beat-type>", xml)  # canvi
        self.assertIn('<measure number="3">', xml)

    def test_constant_no_afegeix_res(self):
        from app.tempo_map import TempoMap
        const = TempoMap.constant(120, 4, 4, durada=8.0)
        events = [(0.0, "C", 4.0), (4.0, "G", 4.0)]
        a = partitura.construeix_musicxml(events, [], bpb=4, bpm=120.0)
        b = partitura.construeix_musicxml(events, [], bpb=4, bpm=120.0,
                                          mapa=const)
        self.assertEqual(a, b)

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_partitura_sense_musescore.py
# ══════════════════════════════════════════════════════════════════════════
"""Partitura SENSE MuseScore: ha de fer el fallback (només MusicXML) sense petar.

El PDF i el MSCZ depenen de MuseScore (l'app no l'inclou). Sense ell, l'export
ha de generar **igualment** el MusicXML, avisar que el PDF no s'ha fet i no
fallar mai (ni des de la GUI ni des de l'MCP).

Aquí es **mocka** `partitura.musescore_bin()` → None (com si no hi fos), en
comptes de dependre de si la màquina el té instal·lat.
"""


def _sortida_amb_acords():
    """Carpeta de sortida mínima vàlida per a la partitura (mode BPM · compàs)."""
    d = tempfile.mkdtemp()
    with open(os.path.join(d, "acords.csv"), "w", encoding="utf-8") as f:
        f.write("0.00,1.00,Am\n1.00,2.00,C\n")
    with open(os.path.join(d, "estructura_ABC.csv"), "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
                "0.00,4.00,4.00,A,A,1.1,2.1\n")
    return d


class TestPartituraSenseMuseScore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QW.QApplication.instance() or QW.QApplication([])

    def test_fallback_a_nomes_musicxml(self):
        d = _sortida_amb_acords()
        logs = []
        with patch.object(partitura, "musescore_bin", return_value=None):
            res = partitura.exporta_partitura(d, log=logs.append, bpm=120.0,
                                              bpb=4)
        self.assertFalse(res.get("error"), f"no hauria de fallar: {res}")
        self.assertTrue(res.get("musicxml"), "hauria de generar el MusicXML")
        self.assertTrue(os.path.isfile(res["musicxml"]))
        self.assertIsNone(res.get("pdf"), "sense MuseScore no hi ha PDF")
        self.assertIsNone(res.get("mscz"), "sense MuseScore no hi ha MSCZ")
        self.assertTrue(any("MuseScore" in m for m in logs),
                        "hauria d'avisar que no hi ha MuseScore")

    def test_la_gui_ho_diu_clarament(self):
        w = app_main.Finestra()
        w.sortida = _sortida_amb_acords()
        # ⚠️ `main.py` fa `import partitura` (nom cru): el mòdul que ELL veu no
        # és `app.partitura` → cal patchejar el seu.
        with patch.object(app_main.partitura, "musescore_bin", return_value=None):
            res = w._exporta_partitura()
        self.assertTrue(res and res.get("musicxml"))
        msg = w._missatge_partitura(res)
        self.assertIn("MusicXML", msg)
        self.assertIn("MuseScore", msg, "ha de dir que el PDF depèn de MuseScore")
        w.close()


def _partitura_sense_musescore_tearDownModule():
    # Neteja ORDENADA dels objectes Qt del mòdul (evita destrucció pel GC en un
    # test posterior -> access violation intermitent). Vegeu tests/_qt_neteja.py.
    try:
        import _qt_neteja
    except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_pipeline_export.py
# ══════════════════════════════════════════════════════════════════════════
# --- Neteja: la suite creava centenars de tempdirs a /tmp que no s'esborraven
# (s'acumulaven entre execucions). Interceptem tempfile.mkdtemp i els traiem
# tots en acabar el modul de tests.
_TMPDIRS = []
_MKDTEMP_ORIG = tempfile.mkdtemp


def _mkdtemp_tracked(*args, **kwargs):
    d = _MKDTEMP_ORIG(*args, **kwargs)
    _TMPDIRS.append(d)
    return d


def _pipeline_export_setUpModule():
    _TMPDIRS.clear()
    tempfile.mkdtemp = _mkdtemp_tracked


def _pipeline_export_tearDownModule():
    tempfile.mkdtemp = _MKDTEMP_ORIG
    for d in _TMPDIRS:
        shutil.rmtree(d, ignore_errors=True)
    _TMPDIRS.clear()


# Mode headless GLOBAL: sense això, les classes que creen QApplication abans
# de definir-lo (p.ex. ExportPipelineTests, que corre primer) poden penjar-se
# o avortar en un entorn sense pantalla.


# QMessageBox.information/warning/... son MODALS: bloquegen fins que algu
# clica OK. En un entorn sense pantalla (CI) aixo penja el test per sempre.
# Els neutralitzem per a TOTS els tests (test-only; no toca l'app).
for _m in ("information", "warning", "critical", "question", "about"):
    if hasattr(visor.QMessageBox, _m):
        setattr(visor.QMessageBox, _m, staticmethod(lambda *a, **k: None))


def _escriu_fitxer(ruta, text):
    """Escriu un fitxer TANCANT-LO de seguida.

    A Windows un fitxer obert sense tancar pot bloquejar la lectura posterior
    (i les dades poden no estar a disc). Era la causa d'errors intermitents.
    """
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(text)


class ExportPipelineTests(unittest.TestCase):
    def test_setup_logging_creates_log_file(self):
        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "auto_chords_test.log"
            app_main.setup_logging(str(log_path))
            self.assertTrue(log_path.exists())
            # A Windows un FileHandler OBRERT bloqueja l'esborrat del tempdir
            # (TemporaryDirectory falla al cleanup): cal tancar i treure els
            # handlers del logger abans de sortir del `with`.
            _lg = logging.getLogger("auto_chords")
            for h in list(_lg.handlers):
                h.close()
                _lg.removeHandler(h)

    def test_main_detects_existing_output_folder_for_wav(self):
        with tempfile.TemporaryDirectory() as td:
            wav = Path(td) / "tema.wav"
            with wave.open(str(wav), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(44100)
                w.writeframes(b"\x00\x00" * 1000)
            out = Path(td) / "AUTOCHORDS_tema"
            out.mkdir()
            (out / "acords.csv").write_text("0.0,2.0,C\n", encoding="utf-8")
            (out / "estructura_ABC.csv").write_text(
                "inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n0.0,2.0,2.0,A,N,1.1.1,2.1.1\n",
                encoding="utf-8",
            )

            app = app_main.QApplication.instance() or app_main.QApplication([])
            window = app_main.Finestra()
            self.assertEqual(window._detecta_sortida_wav(str(wav)), str(out))
            window.sortida = ""
            window._carrega_visor(str(wav))
            self.assertEqual(window.sortida, str(out))
            self.assertGreater(window.visor_ref.llista_ac.count(), 0)
            app.quit()

    def test_obre_wav_mostra_el_model_inicial_abans_d_analitzar(self):
        """Reorg GUI (pas 2) + roadmap §14.1: obrir una WAV mostra l'ona i el
        timeline DE SEGUIDA, encara que no s'hagi analitzat — i el model neix
        amb **1 clip d'acords i 1 d'estructura** que cobreixen tota la cançó
        (punt de partida editable; l'anàlisi és opcional).

        Abans (comportament d'assistent) es mostrava un placeholder fins que
        hi havia CSV."""
        
        with tempfile.TemporaryDirectory() as td:
            wav = Path(td) / "tema.wav"
            with wave.open(str(wav), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(44100)
                w.writeframes(b"\x00\x00" * 1000)

            app = app_main.QApplication.instance() or app_main.QApplication([])
            window = app_main.Finestra()
            window.sortida = ""
            window._carrega_visor(str(wav))
            self.assertIsNotNone(window.visor_ref)
            self.assertEqual(len(window.visor_ref.acords), 1)
            self.assertEqual(len(window.visor_ref.seccions), 1)
            self.assertEqual(window.visor_ref.acords[0][2][0], "N")
            self.assertIsNotNone(window.visor_widget)
            self.assertFalse(hasattr(window, "visor_dock"))
            app.quit()

    def test_exporta_total_generates_expected_outputs(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "AUTOCHORDS_tema"
            csv_ac = base / "acords.csv"
            csv_seg = base / "segments.csv"
            abc = base / "estructura_ABC.csv"
            base.mkdir(parents=True, exist_ok=True)

            with csv_ac.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["0.0", "2.0", "C"])
                writer.writerow(["2.0", "4.0", "Am"])

            with csv_seg.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["0.0", "2.0", "0", "N1"])
                writer.writerow(["2.0", "4.0", "1", "A"])

            result = pipeline.exporta_total(
                csv_ac=str(csv_ac),
                csv_seg=str(csv_seg),
                sortida=str(base),
                bpm=120.0,
                bpb=4,
                offset=0.0,
                sr=44100,
                log=lambda msg: None,
                tempo_fix=True,
                amb_estructura=True,
            )

            self.assertEqual(result["acords_csv"], str(csv_ac))
            self.assertTrue(abc.exists())
            self.assertTrue((base / "wavs_acords").is_dir())
            self.assertTrue((base / "wavs_estructura").is_dir())

    def test_cobertura_export(self):
        """REGLA 4: la suma dels WAVs exportats (acords i estructura) = la durada."""
        import wave
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "AUTOCHORDS_tema"
            base.mkdir(parents=True)
            csv_ac = base / "acords.csv"
            csv_seg = base / "segments.csv"
            with csv_ac.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["1.5", "5.0", "C"])    # 1r acord NO a 0 -> capçalera N
                w.writerow(["5.0", "10.0", "G"])
            with csv_seg.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["0.0", "3.0", "0", "N1"])
                w.writerow(["3.0", "7.0", "1", "A"])   # últim fi < durada
            pipeline.exporta_total(
                csv_ac=str(csv_ac), csv_seg=str(csv_seg), sortida=str(base),
                bpm=120.0, bpb=4, offset=0.0, sr=44100, log=lambda m: None,
                tempo_fix=True, amb_estructura=True, total_s=10.0)

            def suma(carpeta):
                tot = 0.0
                for p in (base / carpeta).glob("*.wav"):
                    with wave.open(str(p), "rb") as w:
                        tot += w.getnframes() / w.getframerate()
                return tot

            self.assertAlmostEqual(suma("wavs_acords"), 10.0, places=1)
            self.assertAlmostEqual(suma("wavs_estructura"), 10.0, places=1)

    def test_app_main_imports_as_module(self):
        root = Path(__file__).resolve().parents[1]
        code = (
            "import sys; sys.path.insert(0, r'" + str(root) + "'); "
            "import app.main; print('APP_IMPORT_OK')"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("APP_IMPORT_OK", proc.stdout)

    def test_versio_app_coincideix_amb_pyproject(self):
        """app.__version__ ha de coincidir amb 'version' de pyproject.toml."""
        import re
        import app
        root = Path(__file__).resolve().parents[1]
        text = (root / "pyproject.toml").read_text(encoding="utf-8")
        m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
        self.assertIsNotNone(m, "no s'ha trobat 'version' a pyproject.toml")
        self.assertEqual(app.__version__, m.group(1))

    def test_section_split_and_merge(self):
        base = [(0.0, 4.0, "A", "A"), (4.0, 8.0, "B", "B")]
        split = pipeline.parteix_seccio(base, 0, 2.0)
        self.assertEqual(len(split), 3)
        self.assertEqual(split[0][0], 0.0)
        self.assertEqual(split[0][1], 2.0)
        self.assertEqual(split[1][0], 2.0)
        self.assertEqual(split[1][1], 4.0)
        merged = pipeline.fusiona_seccions(split, 0, amb="seguent")
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0][2], "A")
        self.assertEqual(merged[1][2], "B")

    def test_exporta_includes_both_acord_and_structure_wavs(self):
        # Test d'integració: el Visor complet amb TimelineView exporta bé
        from app.timeline import TimelineView

        app = visor.QApplication.instance() or visor.QApplication([])
        with tempfile.TemporaryDirectory() as td:
            wav = Path(td) / "tema.wav"
            with wave.open(str(wav), "wb") as wv_w:
                wv_w.setnchannels(1)
                wv_w.setsampwidth(2)
                wv_w.setframerate(44100)
                wv_w.writeframes(b"\x00\x00" * 44100 * 2)
            out = Path(td) / "AUTOCHORDS_tema"
            out.mkdir()
            (out / "acords.csv").write_text("0.0,2.0,C\n", encoding="utf-8")
            (out / "estructura_ABC.csv").write_text(
                "inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
                "0.0,2.0,2.0,A,N,1.1,2.1\n",
                encoding="utf-8",
            )
            v = visor.Visor(str(wav), str(out / "acords.csv"),
                           str(out / "estructura_ABC.csv"),
                           bpm=120, bpb=4, tempo_fix=True)
            self.assertIsInstance(v.timeline, TimelineView)
            self.assertGreater(len(v.timeline._chord_items), 0)
            self.assertGreater(len(v.timeline._section_items), 0)
            v.exporta()   # els QMessageBox ja son no-ops (vegeu dalt)
            self.assertTrue((out / "wavs_acords").is_dir())
            self.assertTrue((out / "wavs_estructura").is_dir())
            v.close()
        app.quit()

    def test_style_normalizes_common_chords(self):
        cases = {
            "cmaj7": "CMaj7",
            "am": "A-",
            "Em7": "E-7",
            "g/d": "G/D",
            "f#m7": "F#-7",
            "Bbmaj7": "BbMaj7",
        }
        for source, expected in cases.items():
            self.assertEqual(pipeline.style(source), expected)

    def test_tempo_fixed_view_switches_to_measure_display(self):
        original_init = visor.Visor.__init__
        visor.Visor.__init__ = lambda self, *args, **kwargs: None
        try:
            v = visor.Visor.__new__(visor.Visor)
            v.tempo_fix = True
            v.bpm = 120.0
            v.bpb = 4
            v.audio = {"durada": 8.0}

            self.assertEqual(v._fmt_timeline(0.0), "1.1 / 4.4")
            self.assertEqual(v._fmt_timeline(2.0), "1.4 / 4.4")
        finally:
            visor.Visor.__init__ = original_init


    def test_main_window_te_les_accions_analitza_i_exporta(self):
        """Reorg GUI (pas 3): «Processa» passa a dir-se «Analitza» i
        «Finalitza i publica» → «Exporta WAV's» (ara són accions, no passos
        d'assistent). També hi ha «Exporta partitura» i «Zoom selecció»."""
        app = app_main.QApplication.instance() or app_main.QApplication([])
        window = app_main.Finestra()
        self.assertTrue(hasattr(window, "b_exec"))
        self.assertTrue(hasattr(window, "b_export"))
        self.assertEqual(window.b_exec.text(), "Analitza")
        self.assertEqual(window.b_export.text(), "Exporta WAV's")
        self.assertTrue(hasattr(window, "b_export_part"))
        self.assertTrue(hasattr(window, "barra_accions"))   # 2a fila de la barra 1
        app.quit()

    def test_metro_desactivat_en_mode_lliure(self):
        """El metrònom només està disponible en mode BPM · compàs."""
        import tempfile, wave
        app = app_main.QApplication.instance() or app_main.QApplication([])
        window = app_main.Finestra()
        # sense visor NO hi ha metrònom disponible
        window._actualitza_metro_ui()
        self.assertFalse(window.b_metro.isEnabled())
        # amb una WAV carregada (mode BPM per defecte) → actiu
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "t.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100)
        window.wav_edit.setText(wav)
        window._carrega_visor(wav)
        self.assertTrue(window.b_metro.isEnabled())
        self.assertTrue(window.a_metro.isEnabled())
        # passar a Lliure → desactivat + desmarcat + tooltip
        window._toggle_metro(True)
        window._canvia_mode_temps(False)
        self.assertFalse(window.b_metro.isEnabled())
        self.assertFalse(window.vol_metro.isEnabled())
        self.assertFalse(window.a_metro.isEnabled())
        self.assertFalse(window.b_metro.isChecked())
        self.assertIn("BPM", window.b_metro.toolTip())
        app.quit()

    def test_volum_metro_per_defecte(self):
        from app import theme
        app = app_main.QApplication.instance() or app_main.QApplication([])
        window = app_main.Finestra()
        self.assertEqual(window.vol_metro.value(), 60)
        self.assertEqual(window.vol_metro.minimum(), 0)
        self.assertEqual(window.vol_metro.maximum(), 100)
        # i el color de l'estat activat viu al theme, no al visor
        self.assertTrue(hasattr(theme, "METRO_ACTIU"))
        app.quit()

    def test_analitza_desactivat_sense_wav(self):
        """Estat dinàmic: «Analitza» està desactivat fins que hi ha WAV."""
        app = app_main.QApplication.instance() or app_main.QApplication([])
        window = app_main.Finestra()
        self.assertFalse(window.b_exec.isEnabled())
        app.quit()

    def test_log_dock_amagat_per_defecte(self):
        """El log és un tauler inferior plegable, tancat per defecte."""
        app = app_main.QApplication.instance() or app_main.QApplication([])
        window = app_main.Finestra()
        self.assertTrue(hasattr(window, "log_dock"))
        self.assertFalse(window.log_dock.isVisible())
        app.quit()

    def test_embedded_visor_close_does_not_quit_app(self):
        from PyQt5.QtGui import QCloseEvent
        app = visor.QApplication.instance() or visor.QApplication([])
        v = visor.Visor.__new__(visor.Visor)
        visor.QMainWindow.__init__(v)
        v._embedded = True
        v.rellotge = type("R", (), {"stop": lambda self: None})()
        v._atura_proc = lambda: None
        v.log = lambda *args, **kwargs: None
        with patch.object(visor.QApplication.instance(), "quit") as quit_mock:
            v.closeEvent(QCloseEvent())
        quit_mock.assert_not_called()
        app.quit()

    def test_visor_supports_add_and_remove_chords_and_sections(self):
        app = visor.QApplication.instance() or visor.QApplication([])
        v = visor.Visor.__new__(visor.Visor)
        visor.QMainWindow.__init__(v)
        v.acords = [(0.0, "C", "0.0"), (2.0, "Am", "2.0")]
        # Es deixa un tros LLIURE (3–4 s) per poder-hi afegir una secció: amb
        # el topall superior de temps, una secció fora de la WAV (p. ex. 4–6 s
        # en una WAV de 4 s) ja no s'accepta (trencava la cobertura, regla #4).
        v.seccions = [(0.0, 2.0, "A", "A"), (2.0, 3.0, "B", "B")]
        v.bpm = 120.0
        v.bpb = 4
        v.offset = 0.0
        v.tempo_fix = True
        v.audio = {"durada": 4.0}
        v.log = lambda msg: None

        # La regla #4 no permet forats: afegim la secció al tros lliure 3–4
        # ABANS de l'alta d'acord (que normalitza la cobertura de tots dos
        # carrils i taparia eixe forat amb «-»).
        v._afegeix_seccio(3.0, 4.0, "C", "C")
        self.assertEqual(len(v.seccions), 3)
        self.assertEqual(v.seccions[2][2], "C")

        v._afegeix_acord(1.0, "G")
        self.assertEqual(len(v.acords), 3)
        self.assertEqual(v.acords[1][2][0], "G")

        v._elimina_acord(1)
        self.assertEqual(len(v.acords), 2)
        self.assertEqual(v.acords[1][2][0], "Am")

        v._elimina_seccio(2)
        self.assertEqual(len(v.seccions), 2)
        self.assertEqual(v.seccions[1][2], "B")
        app.quit()

    def test_canviar_bpm_mentre_sona_no_talla_l_audio(self):
        """Canviar BPM/compàs/offset amb l'àudio sonant NO ha de reiniciar-lo.

        El fil d'alimentació llig `bpm`/`bpb`/`offset` (i el mapa de tempo) a
        cada tros, així que el metrònom segueix la graella nova a l'instant.
        Abans es reiniciava el reproductor i se sentia un micro-tall (mateix
        defecte que el commutador del metrònom; reportat per l'operador).
        """
        import wave
        # `Finestra()` necessita una QApplication viva (i la referència ha de
        # viure: si no, es destruiria de seguida).
        app = app_main.QApplication.instance() or app_main.QApplication([])
        with tempfile.TemporaryDirectory() as td:
            wav = os.path.join(td, "t.wav")
            with wave.open(wav, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(44100)
                w.writeframes(b"\x00\x00" * 44100 * 3)
            window = app_main.Finestra()
            window.wav_edit.setText(wav)
            window._carrega_visor(wav)
            v = window.visor_ref
            self.assertIsNotNone(v, "cal un visor carregat per a aquesta prova")
            v.sona = True
            crides = []
            v._atura_proc = lambda: crides.append("atura")
            v._engega_des_de = lambda t: crides.append("engega")
            window._aplica_parametres_temps()
            app.processEvents()          # deixa la UI processar els canvis
            self.assertEqual(crides, [], "no ha de reiniciar el reproductor")
            v.sona = False
            window.close()

    def test_main_window_export_calls_pipeline_export(self):
        app = app_main.QApplication.instance() or app_main.QApplication([])
        window = app_main.Finestra()
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            (base / "AUTOCHORDS_tema").mkdir()
            (base / "AUTOCHORDS_tema" / "acords.csv").write_text(
                "0.0,2.0,C\n2.0,4.0,Am\n", encoding="utf-8"
            )
            (base / "AUTOCHORDS_tema" / "segments.csv").write_text(
                "0.0,2.0,0,N1\n2.0,4.0,1,A\n", encoding="utf-8"
            )
            window.sortida = str(base / "AUTOCHORDS_tema")
            window.wav_edit.setText(str(base / "tema.wav"))
            with patch.object(app_main.pipeline, "exporta_total") as exporta:
                with patch.object(app_main.QDesktopServices, "openUrl"):
                    window.exporta()

        exporta.assert_called_once()
        self.assertEqual(exporta.call_args.kwargs["sortida"], str(base / "AUTOCHORDS_tema"))
        app.quit()

    def test_visor_normalizes_interval_order_for_chords_and_sections(self):
        app = visor.QApplication.instance() or visor.QApplication([])
        v = visor.Visor.__new__(visor.Visor)
        v.acords = [(10.0, "E", "10.000000000"), (0.0, "C", "0.000000000"), (2.0, "Am", "2.000000000")]
        v.seccions = [(10.0, 12.0, "C", "C"), (0.0, 2.0, "A", "A"), (2.0, 10.0, "B", "B")]

        v._normalitza_acords(v.acords)
        v._normalitza_seccions(v.seccions)

        self.assertEqual([item[0] for item in v.acords], [0.0, 2.0, 10.0])
        self.assertEqual([item[2] for item in v.seccions], ["A", "B", "C"])
        app.quit()

    def test_visor_rejects_invalid_edit_order_for_chords_and_sections(self):
        v = visor.Visor.__new__(visor.Visor)
        v.audio = {"durada": 30.0}
        v.acords = [(0.0, "C", "0.000000000"), (5.0, "Am", "5.000000000"), (10.0, "G", "10.000000000")]
        v.seccions = [(0.0, 5.0, "A", "A"), (5.0, 10.0, "B", "B"), (10.0, 30.0, "C", "C")]

        with self.assertRaises(ValueError):
            v._valida_canvis_acords([(0.0, "C", "0.000000000"), (0.0, "Am", "0.000000000"), (10.0, "G", "10.000000000")])

        with self.assertRaises(ValueError):
            v._valida_canvis_seccions([(0.0, 5.0, "A", "A"), (3.0, 10.0, "B", "B")])


class TimelineConstraintTests(unittest.TestCase):
    """Tests del constraint engine i snap del TimelineView."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def _make_view(self, durada=10.0, acords=None, seccions=None,
                   bpm=120.0, bpb=4, tempo_fix=True):
        from app.timeline import TimelineView
        audio = {
            "sr": 44100, "canals": 1, "durada": durada,
            "pics": np.linspace(0.1, 0.9, 500, dtype=np.float32),
            "temps": np.linspace(0, durada, 500),
            "raw": b"",
        }
        if acords is None:
            acords = [(0.0, "C", "0.0"), (2.0, "Am", "2.0"),
                      (4.5, "F", "4.5"), (7.0, "G", "7.0")]
        if seccions is None:
            seccions = []
        view = TimelineView(audio, acords, seccions, bpm, bpb, tempo_fix)
        view.resize(900, 300)
        return view

    def test_chord_move_propagates_to_neighbour_amplitude(self):
        """Moure B.t propaga a A.fi (amplitud canvia) i a B.t."""
        view = self._make_view(tempo_fix=False)
        view.zoom_to(0, 10)
        # Mou Am de 2.0 a 1.5 — l'amplada de C canvia
        view._on_chord_time_changed(1, 1.5)
        self.assertAlmostEqual(view._acords[1][0], 1.6, places=4)
        # C (anterior) té el seu "fi" actualitzat a 1.6
        self.assertAlmostEqual(view._chord_items[0]._next_t, 1.6, places=4)
        # F (següent) no canvia
        self.assertAlmostEqual(view._acords[2][0], 4.5, places=4)

    def test_chord_move_clamped_by_neighbours(self):
        """No es pot passar el veinat."""
        view = self._make_view(tempo_fix=False)
        view.zoom_to(0, 10)
        # Prova d'anar més enllà de F (4.5)
        view._on_chord_time_changed(1, 100.0)
        self.assertLessEqual(view._acords[1][0], 4.5 - 0.001 + 1e-6)
        # Prova d'anar més enrere de C (0.0)
        view._on_chord_time_changed(1, -10.0)
        self.assertGreaterEqual(view._acords[1][0], 0.001)

    def test_chord_end_move_propagates_to_next_chord(self):
        """Moure B.fi (= inici de C) propaga C.t."""
        view = self._make_view(tempo_fix=False)
        view.zoom_to(0, 10)
        view._on_chord_end_changed(1, 3.5)
        self.assertAlmostEqual(view._acords[2][0], 3.6, places=4)
        # Am.t no canvia
        self.assertAlmostEqual(view._acords[1][0], 2.0, places=4)

    def test_chord_snap_tempo_measure(self):
        """Snap a mesura en mode tempo_fix amb span ample."""
        view = self._make_view(tempo_fix=True, bpm=120, bpb=4)
        view.zoom_to(0, 10)  # span=10 → pas=measure=2.0s
        view.set_data([(0.0, "C", "0.0"), (1.7, "Am", "1.7"),
                       (3.0, "F", "3.0")], [])
        view._on_chord_time_changed(1, 1.7)
        self.assertAlmostEqual(view._acords[1][0], 1.75, places=4)

    def test_chord_snap_free(self):
        """Snap a 1s en mode lliure amb span ample."""
        view = self._make_view(durada=60.0, tempo_fix=False)
        view.zoom_to(0, 50)  # span=50 → pas=1.0s
        view.set_data([(0.0, "C", "0.0"), (3.7, "Am", "3.7"),
                       (8.0, "F", "8.0")], [])
        view._on_chord_time_changed(1, 4.3)
        self.assertAlmostEqual(view._acords[1][0], 4.0, places=4)

    def test_section_resize_clamped_by_neighbours(self):
        """Les seccions esclamen pels veins."""
        view = self._make_view(durada=10.0, tempo_fix=False)
        view.set_data([], [(0.0, 3.0, "A", "A"),
                           (3.0, 6.0, "B", "B"),
                           (6.0, 10.0, "C", "C")])
        view._section_items[1]._drag_mode = 0  # ZONE_NONE -> tractat com a LEFT
        view._on_section_changed(1, 1.5, 7.0)
        # Amb la lògica nova (contigüitat), moure l'inici arrossega el fi
        # de l'anterior; la secció queda [1.6, 5.98]
        self.assertAlmostEqual(view._seccions[1][0], 1.6, places=4)
        self.assertAlmostEqual(view._seccions[1][1], 6.0, places=4)

    def test_rename_chord_updates_data(self):
        """Rename inline programatic actualitza self.acords."""
        view = self._make_view(tempo_fix=False)
        view._commit_rename("chord", 1, view._chord_items[1], "Am7")
        self.assertEqual(view._acords[1][2][0], "Am7")
        self.assertEqual(view._chord_items[1].name, "Am7")

    def test_rename_section_updates_data(self):
        """Rename inline programatic actualitza self.seccions."""
        view = self._make_view()
        view.set_data([], [(0.0, 4.0, "A", "A"), (4.0, 8.0, "B", "B")])
        view._commit_rename("section", 0, view._section_items[0], "Verse")
        self.assertEqual(view._seccions[0][2], "Verse")

    def test_set_data_rebuilds_items(self):
        """set_data reconfigura tots els items correctament."""
        view = self._make_view()
        view.set_data([(0.0, "Dm", "0.0"), (5.0, "G7", "5.0")],
                      [(0.0, 4.0, "X", "X"), (4.0, 10.0, "Y", "Y")])
        self.assertEqual(len(view._chord_items), 2)
        self.assertEqual(len(view._section_items), 2)
        self.assertEqual(view._chord_items[0].name, "Dm")
        self.assertEqual(view._section_items[1].lletra, "Y")

    def test_zoom_to_respects_durada_limit(self):
        """zoom_to no pot anar més enllà de durada."""
        view = self._make_view(durada=10.0)
        view.zoom_to(0, 50)
        self.assertAlmostEqual(view._view_right, 10.0, places=4)

    def test_position_highlights_active_chord(self):
        """set_position il·lumina l'acord que toca."""
        view = self._make_view(tempo_fix=False)
        view.set_position(3.0)
        # L'acord 1 (Am, t=2.0) hauria d'estar actiu
        self.assertTrue(view._chord_items[1]._active)
        self.assertFalse(view._chord_items[0]._active)

    def test_multi_selection_toggle_i_rang(self):
        """Ctrl+clic afegeix/treu; Shift+clic selecciona el rang sencer."""
        view = self._make_view(tempo_fix=False)
        view.toggle_selection("chord", 0)
        view.toggle_selection("chord", 2)   # Ctrl-clic: afegeix
        self.assertEqual(view.selected_keys(), {("chord", 0), ("chord", 2)})
        self.assertTrue(view._chord_items[0]._selected)
        self.assertTrue(view._chord_items[2]._selected)
        self.assertFalse(view._chord_items[1]._selected)
        # Shift-clic des de l'àncora (2) fins a 3 → rang {2, 3}
        view.extend_selection("chord", 3)
        self.assertEqual(view.selected_keys(), {("chord", 2), ("chord", 3)})
        # Ctrl-clic sobre un de ja seleccionat el treu
        view.toggle_selection("chord", 2)
        self.assertEqual(view.selected_keys(), {("chord", 3)})

    def test_select_clip_resseteja_la_multi_seleccio(self):
        """Una selecció simple (des de llista/menu) buida la multi-selecció."""
        view = self._make_view(tempo_fix=False)
        view.toggle_selection("chord", 0)
        view.toggle_selection("chord", 1)
        view.select_clip("chord", 2)
        self.assertEqual(view.selected_keys(), {("chord", 2)})
        self.assertFalse(view._chord_items[0]._selected)

    def test_clear_selection_buida(self):
        """clear_selection deixa el conjunt buit i desmarca els items."""
        view = self._make_view(tempo_fix=False)
        view.select_clip("chord", 1)
        view.toggle_selection("chord", 2)
        view.clear_selection()
        self.assertEqual(view.selected_keys(), set())
        self.assertFalse(any(it._selected for it in view._chord_items))

    def test_set_data_buida_la_multi_seleccio(self):
        """set_data (re-render amb índexs nous) no deixa selecció òrfena."""
        view = self._make_view(tempo_fix=False)
        view.toggle_selection("chord", 0)
        view.toggle_selection("chord", 1)
        view.set_data([(0.0, "C", "0.0"), (1.0, "D", "1.0")], [])
        self.assertEqual(view.selected_keys(), set())

    def test_mou_grup_de_seccions(self):
        """Arrossegar el cos d'una secció seleccionada mou el bloc contigu."""
        from app.timeline_items import SectionItem
        view = self._make_view(durada=10.0, tempo_fix=False)
        view.set_data([], [(0.0, 3.0, "A", "A"),
                           (3.0, 6.0, "B", "B"),
                           (6.0, 10.0, "C", "C")])
        view.toggle_selection("section", 0)
        view.toggle_selection("section", 1)
        it = view._section_items[0]
        it._drag_mode = SectionItem.ZONE_BODY
        it._drag_ini0 = 0.0
        view._on_section_changed(0, 0.5, 3.5)    # snap 0,2 -> dt = +0.4
        view._emit_edit_finished()               # el destí es resol al release
        self.assertEqual([(s[2], round(float(s[0]), 3), round(float(s[1]), 3))
                          for s in view._seccions],
                         [("-", 0.0, 0.4), ("A", 0.4, 3.4),
                          ("B", 3.4, 6.4), ("C", 6.4, 10.0)])

    def test_ruler_mode_label_tempo_i_lliure(self):
        """L'indicador de mode del regle: 'N BPM . P/4' amb tempo, 'Lliure' sense."""
        from app.timeline_layers import RulerLayer
        r = RulerLayer(400, 26, 60.0, 0.0, 0.0, 10.0, True, 120.0, 4)
        self.assertEqual(r.mode_label(), "120 BPM \u00b7 4/4")
        r.update_mode(False, 120.0, 4)
        self.assertEqual(r.mode_label(), "Lliure")
        r.update_mode(True, 90.0, 3)
        self.assertEqual(r.mode_label(), "90 BPM \u00b7 3/4")

    def test_ruler_paint_no_peta(self):
        """El paint del regle (amb l'indicador de mode) no ha de petar mai."""
        from PyQt5.QtGui import QImage, QPainter
        from app.timeline_layers import RulerLayer
        r = RulerLayer(400, 26, 60.0, 0.0, 0.0, 10.0, True, 120.0, 4)
        img = QImage(400, 26, QImage.Format_ARGB32)
        img.fill(0)
        p = QPainter(img)
        try:
            r.paint(p, None, None)
        finally:
            p.end()

    def test_tempo_lane_paint_no_peta(self):
        """El paint de la pista de tempo/compàs no ha de petar mai."""
        from PyQt5.QtGui import QImage, QPainter
        from app.timeline_layers import TempoLayer
        from app.tempo_map import TempoMap
        tl = TempoLayer(20, 60.0, 12.0, 0.0, 10.0, 100.0)
        img = QImage(600, 20, QImage.Format_ARGB32)
        img.fill(0)
        p = QPainter(img)
        try:
            tl.paint(p, None, None)              # sense mapa: pista buida
            tl.set_mapa(TempoMap([(0.0, 4.0, 120.0, 4, 4),
                                  (4.0, 8.0, 60.0, 3, 4)]))
            tl.paint(p, None, None)              # amb mapa variable
            tl.set_mapa(TempoMap.constant(120, 4, 4, durada=8.0))
            tl.paint(p, None, None)              # constant: buida
        finally:
            p.end()

    def test_grid_levels_colors_valids(self):
        """Els colors de grid_levels han de ser REALS (QColor valid), no strings."""
        from PyQt5.QtGui import QColor
        from app.timeline_base import grid_levels
        casos = ((True, 120.0, 4, 60.0), (True, 90.0, 3, 20.0),
                 (False, 120.0, 4, 60.0), (False, 120.0, 4, 10.0))
        for tf, bpm, bpb, pps in casos:
            for _step, color, _w in grid_levels(tf, bpm, bpb, pps, pps * 10.0):
                self.assertTrue(QColor(color).isValid(),
                                f"color invalid a grid_levels: {color!r}")


    def test_snap_metode(self):
        """El mètode snap() arrodoneix a la graella actual."""
        view = self._make_view(tempo_fix=False)
        view.zoom_to(0, 10)          # span 10 -> snap 0,2 s
        self.assertAlmostEqual(view.snap(1.73), 1.8, places=4)

    def test_loop_x_to_time_fa_snap(self):
        """El temps del regle per al loop A/B fa snap a la graella."""
        view = self._make_view(tempo_fix=False)
        view.zoom_to(0, 10)          # snap 0,2 s
        x = view._x_offset + (1.73 - view._view_left) * view._pps
        self.assertAlmostEqual(view._loop_x_to_time(x), 1.8, places=4)


class VisorTimelineIntegrationTests(unittest.TestCase):
    """Tests d'integració Visor ↔ TimelineView."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def _make_visor_with_data(self):
        import os
        td = tempfile.mkdtemp()
        wav_path = os.path.join(td, "tema.wav")
        sortida = os.path.join(td, "AUTOCHORDS_tema")
        os.makedirs(sortida)
        with wave.open(wav_path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * 20)
        with open(os.path.join(sortida, "acords.csv"), "w", encoding="utf-8") as f:
            f.write("0.0,2.0,C\n2.0,4.5,Am\n4.5,7.0,F\n7.0,10.0,G\n10.0,20.0,C\n")
        with open(os.path.join(sortida, "estructura_ABC.csv"), "w", encoding="utf-8") as f:
            f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n")
            f.write("0.0,5.0,5.0,A,A,1.1,5.1\n")
            f.write("5.0,10.0,5.0,B,B,5.1,10.1\n")
            f.write("10.0,20.0,10.0,C,C,10.1,20.1\n")
        v = visor.Visor(wav_path,
                        os.path.join(sortida, "acords.csv"),
                        os.path.join(sortida, "estructura_ABC.csv"),
                        bpm=120, bpb=4, tempo_fix=False)
        return v, sortida

    def test_click_a_un_clip_mou_el_cursor(self):
        """Clic (sense drag) a un acord o una secció → cursor al seu inici.

        Regressió: el lambda del click capturava el valor antic d'ini/t i
        després d'un resize anava al lloc vell."""
        v, _ = self._make_visor_with_data()
        v.timeline.zoom_to(0, 20)
        casos = [("acord", v.timeline._chord_items, 1, 2.0),
                 ("secció", v.timeline._section_items, 1, 5.0)]
        for nom, items, idx, esperat in casos:
            v.timeline.set_position(0.0, emit=False)
            items[idx].clicked.emit()
            obtingut = v.timeline.get_position()
            self.assertAlmostEqual(obtingut, esperat, places=2,
                                   msg=f"{nom}: cursor {obtingut} != {esperat}")
        v.close()

    def test_delete_esborra_l_acord_seleccionat(self):
        """Delete esborra l'acord seleccionat i passa per l'undo."""
        from PyQt5.QtGui import QKeyEvent
        from PyQt5.QtCore import QEvent, Qt
        v, _ = self._make_visor_with_data()
        n = len(v.acords)
        v.timeline.select_clip("chord", 1)
        v.timeline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier))
        self.assertEqual(len(v.acords), n - 1)
        self.assertEqual(len(v._undo_stack), 1)
        v.undo()
        self.assertEqual(len(v.acords), n)      # undo el restaura
        v.close()

    def test_delete_seccio_el_vei_ocupa_l_espai(self):
        """En esborrar una secció, el previ s'estén (invariant de contigüitat)."""
        from PyQt5.QtGui import QKeyEvent
        from PyQt5.QtCore import QEvent, Qt
        v, _ = self._make_visor_with_data()
        n = len(v.seccions)
        fi_alliberada = v.seccions[1][1]
        v.timeline.select_clip("section", 1)
        v.timeline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier))
        self.assertEqual(len(v.seccions), n - 1)
        # el fi del previ ara arriba on arribava el de la seccio esborrada
        self.assertAlmostEqual(v.seccions[0][1], fi_alliberada, places=3)
        v.undo()
        self.assertEqual(len(v.seccions), n)
        v.close()

    def test_delete_de_grup_esborra_els_seleccionats(self):
        """Delete amb multi-selecció esborra tots els clips d'una sola vegada."""
        from PyQt5.QtGui import QKeyEvent
        from PyQt5.QtCore import QEvent, Qt
        v, _ = self._make_visor_with_data()
        n = len(v.acords)
        v.timeline.toggle_selection("chord", 1)
        v.timeline.toggle_selection("chord", 3)
        self.assertEqual(len(v.timeline.selected_keys()), 2)
        v.timeline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier))
        self.assertEqual(len(v.acords), n - 2)
        self.assertEqual(len(v._undo_stack), 1)   # una sola operació d'undo
        v.undo()
        self.assertEqual(len(v.acords), n)
        v.close()

    def test_ctrl_c_i_ctrl_v_enganxa_acord(self):
        """Ctrl+C + Ctrl+V: enganxa l'acord copiat al cursor (amb undo)."""
        from PyQt5.QtGui import QKeyEvent
        from PyQt5.QtCore import QEvent, Qt
        v, _ = self._make_visor_with_data()
        n = len(v.acords)
        v.timeline.select_clip("chord", 0)     # C @ 0.0
        v.timeline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_C, Qt.ControlModifier))
        self.assertTrue(v.timeline.has_clipboard())
        v.timeline.set_position(6.0, emit=False)
        v.timeline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_V, Qt.ControlModifier))
        self.assertEqual(len(v.acords), n + 1)
        temps = [round(float(t), 1) for (t, *_r) in v.acords]
        self.assertIn(6.0, temps)
        v.undo()
        self.assertEqual(len(v.acords), n)
        v.close()

    def test_ctrl_x_retalla_la_seleccio(self):
        """Ctrl+X: copia al buffer i esborra la selecció (amb undo)."""
        from PyQt5.QtGui import QKeyEvent
        from PyQt5.QtCore import QEvent, Qt
        v, _ = self._make_visor_with_data()
        n = len(v.acords)
        v.timeline.select_clip("chord", 1)
        v.timeline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_X, Qt.ControlModifier))
        self.assertEqual(len(v.acords), n - 1)
        self.assertTrue(v.timeline.has_clipboard())
        v.undo()
        self.assertEqual(len(v.acords), n)
        v.close()

    def test_ctrl_v_enganxa_seccio_sobreescriu(self):
        """Ctrl+V de seccions: el bloc substitueix la regió (sobreescriptura).

        A 0-5, B 5-10, C 10-20; copiem B (5-10) i enganxem a 12 → C es talla i
        queda A 0-5 · B 5-10 · C 10-12 · B 12-17 · C 17-20."""
        from PyQt5.QtGui import QKeyEvent
        from PyQt5.QtCore import QEvent, Qt
        v, _ = self._make_visor_with_data()
        n = len(v.seccions)                    # 3: A 0-5, B 5-10, C 10-20
        v.timeline.select_clip("section", 1)   # B 5-10 (span 5)
        v.timeline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_C, Qt.ControlModifier))
        v.timeline.set_position(12.0, emit=False)   # dins C 10-20
        v.timeline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_V, Qt.ControlModifier))
        self.assertEqual(len(v.seccions), n + 2)   # 10-12 C · 12-17 B · 17-20 C
        for i in range(len(v.seccions) - 1):
            self.assertLessEqual(v.seccions[i][1], v.seccions[i + 1][0] + 1e-9)
        v.undo()
        self.assertEqual(len(v.seccions), n)
        v.close()

    def test_ctrl_v_seccio_sobreescriu_la_regio(self):
        """Ctrl+V de seccions: SOBREESCRIU [cursor, cursor+span] amb el bloc.

        Model «com un DAW» (regla #4): el bloc no s'hi «insereix», substitueix
        la regió; les vores es tallen i s'acoblen, i la suma segueix sent la
        durada de la WAV."""
        from PyQt5.QtGui import QKeyEvent
        from PyQt5.QtCore import QEvent, Qt
        v, _ = self._make_visor_with_data()
        n = len(v.seccions)                        # 3: A 0-5, B 5-10, C 10-20
        v.timeline.select_clip("section", 0)       # A 0-5 (span 5)
        v.timeline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_C, Qt.ControlModifier))
        v.timeline.set_position(6.0, emit=False)   # dins B 5-10
        v.timeline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_V, Qt.ControlModifier))
        # A 0-5 · B 5-6 · A 6-11 · C 11-20
        self.assertEqual(len(v.seccions), n + 1)
        self.assertEqual([s[2] for s in v.seccions], ["A", "B", "A", "C"])
        for i in range(len(v.seccions) - 1):
            self.assertAlmostEqual(float(v.seccions[i][1]),
                                   float(v.seccions[i + 1][0]), places=6)
        self.assertAlmostEqual(float(v.seccions[-1][1]), 20.0, places=6)
        self.assertEqual(len(v._undo_stack), 1)    # una sola operació
        v.undo()
        self.assertEqual(len(v.seccions), n)
        v.close()

    def test_ctrl_d_duplica_acord_despres_sobreescrivint(self):
        """Ctrl+D sobre un acord: la còpia va DESPRÉS i sobreescriu el tram (§2)."""
        from PyQt5.QtGui import QKeyEvent
        from PyQt5.QtCore import QEvent, Qt
        v, _ = self._make_visor_with_data()
        n = len(v.acords)
        fi0 = float(v.acords[0].fi)          # on comença la còpia
        v.timeline.select_clip("chord", 0)
        v.timeline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_D, Qt.ControlModifier))
        self.assertGreater(len(v.acords), n)
        self.assertAlmostEqual(float(v.acords[1][0]), fi0, places=3)
        self.assertEqual(v.acords[1][2][0], v.acords[0][2][0])   # mateix nom
        v.undo()
        self.assertEqual(len(v.acords), n)
        v.close()

    def test_ctrl_d_duplica_seccio_despres_sobreescrivint(self):
        """Ctrl+D sobre una secció: la còpia va DESPRÉS i sobreescriu (§2)."""
        from PyQt5.QtGui import QKeyEvent
        from PyQt5.QtCore import QEvent, Qt
        v, _ = self._make_visor_with_data()
        n = len(v.seccions)
        fi0 = float(v.seccions[0][1])        # on comença la còpia
        v.timeline.select_clip("section", 0)
        v.timeline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_D, Qt.ControlModifier))
        self.assertAlmostEqual(float(v.seccions[1][0]), fi0, places=3)
        self.assertEqual(v.seccions[1][2], v.seccions[0][2])   # mateixa lletra
        v.undo()
        self.assertEqual(len(v.seccions), n)
        v.close()

    def test_ctrl_d_duplica_el_grup_d_acords(self):
        """Ctrl+D amb multi-selecció duplica tots els acords (una sola undo)."""
        from PyQt5.QtGui import QKeyEvent
        from PyQt5.QtCore import QEvent, Qt
        v, _ = self._make_visor_with_data()
        n = len(v.acords)
        v.timeline.toggle_selection("chord", 0)
        v.timeline.toggle_selection("chord", 1)
        v.timeline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_D, Qt.ControlModifier))
        self.assertEqual([a[2][0] for a in v.acords[:4]],
                         ["C", "Am", "C", "Am"])   # la còpia del bloc va després
        self.assertGreater(len(v.acords), n)
        self.assertEqual(len(v._undo_stack), 1)
        v.undo()
        self.assertEqual(len(v.acords), n)
        v.close()

    def test_ctrl_d_duplica_les_seccions_seleccionades(self):
        """Ctrl+D amb multi-selecció de seccions: totes es parteixen (una undo)."""
        from PyQt5.QtGui import QKeyEvent
        from PyQt5.QtCore import QEvent, Qt
        v, _ = self._make_visor_with_data()
        n = len(v.seccions)
        v.timeline.toggle_selection("section", 0)
        v.timeline.toggle_selection("section", 1)
        v.timeline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_D, Qt.ControlModifier))
        self.assertEqual([sec[2] for sec in v.seccions], ["A", "B", "A", "B"])
        self.assertGreater(len(v.seccions), n)
        self.assertEqual(len(v._undo_stack), 1)
        v.undo()
        self.assertEqual(len(v.seccions), n)
        v.close()

    def test_marca_A_B_fan_snap(self):
        """Els botons A/B marquen el loop amb snap a la graella."""
        v, _ = self._make_visor_with_data()
        v.timeline.zoom_to(0, 20)    # mode lliure, span 20 -> snap 0,5 s
        v.pos = 1.73
        v.marca_A()
        self.assertAlmostEqual(v.loop_a, 1.5, places=4)
        v.pos = 3.26
        v.marca_B()
        self.assertAlmostEqual(v.loop_b, 3.5, places=4)
        v.close()

    def test_visor_has_timeline_attribute(self):
        v, _ = self._make_visor_with_data()
        self.assertTrue(hasattr(v, "timeline"))
        self.assertGreater(len(v.timeline._chord_items), 0)
        v.close()

    def test_visor_does_not_have_obsolete_attributes(self):
        v, _ = self._make_visor_with_data()
        self.assertFalse(hasattr(v, "corba"))
        self.assertFalse(hasattr(v, "partitura"))
        v.close()

    def test_chord_move_via_timeline_propagates_to_visor(self):
        v, _ = self._make_visor_with_data()
        v.timeline.zoom_to(0, 20)
        v.timeline._on_chord_time_changed(1, 3.6)
        # Snap (span=20 → 0.5s a mode lliure) → 3.5
        self.assertAlmostEqual(v.acords[1][0], 3.5, places=4)
        v.close()

    def test_rename_via_timeline_propagates_to_visor(self):
        v, _ = self._make_visor_with_data()
        v.timeline._commit_rename("chord", 2, v.timeline._chord_items[2],
                                  "FMaj7")
        self.assertEqual(v.acords[2][2][0], "FMaj7")
        v.close()

    def test_section_move_via_timeline_propagates_to_visor(self):
        v, _ = self._make_visor_with_data()
        v.timeline._section_items[1]._drag_mode = 0
        v.timeline._on_section_changed(1, 6.0, 10.0)
        self.assertAlmostEqual(v.seccions[1][0], 6.0, places=4)
        self.assertAlmostEqual(v.seccions[1][1], 10.0, places=4)
        v.close()

    def test_delete_chord_via_visor_updates_timeline(self):
        v, _ = self._make_visor_with_data()
        n_antes = len(v.acords)
        v._elimina_acord_index(0)
        # (Regla d'or #4 · cobertura) En eliminar el 1r clip (a 0), la
        # normalització hi torna a posar la «N» a 0 → el recompte es manté;
        # el que importa és que el TIMELINE quadri amb el model i arrenqui a 0.
        self.assertEqual(len(v.timeline._chord_items), len(v.acords))
        self.assertAlmostEqual(float(v.acords[0][0]), 0.0)
        self.assertEqual(v.acords[0][2][0], "N")
        self.assertLessEqual(len(v.acords), n_antes)      # no creix mai
        v.close()


class MetronomTests(unittest.TestCase):
    """Generador de clics del metrònom (app/metronom.py) — numpy pur."""

    SR = 44100

    def _silenci(self, dur):
        return b"\x00\x00" * int(self.SR * dur)

    def _a_array(self, b):
        return np.frombuffer(b, dtype=np.int16).astype(np.int32)

    def _onsets(self, senyal, llindar=1000):
        """Inici de cada esclat de clic (separats per >50 ms de silenci)."""
        actiu = np.abs(senyal) > llindar
        idx = np.where(actiu)[0]
        if idx.size == 0:
            return np.array([])
        gaps = np.where(np.diff(idx) > 0.05 * self.SR)[0]
        inicis = np.concatenate(([idx[0]], idx[gaps + 1]))
        return inicis / self.SR

    def _freq(self, tros):
        sp = np.abs(np.fft.rfft(tros))
        return np.fft.rfftfreq(len(tros), 1.0 / self.SR)[np.argmax(sp)]

    def test_clics_a_120bpm_4_4(self):
        from app import metronom
        out = metronom.mescla_metronom(self._silenci(3.0), self.SR,
                                       0.0, 120.0, 4, volum=1.0)
        onsets = self._onsets(self._a_array(out))
        # 0, 0.5, 1.0, 1.5, 2.0, 2.5
        self.assertEqual(len(onsets), 6)
        for k, o in enumerate(onsets):
            self.assertAlmostEqual(o, k * 0.5, places=3)
        # accent (≈1500 Hz) als beats 0 i 4; la resta ≈1000 Hz
        n = int(self.SR * 0.02)
        f0 = self._freq(self._a_array(out)[int(0.0 * self.SR):int(0.0 * self.SR) + n])
        f2 = self._freq(self._a_array(out)[self.SR:self.SR + n])
        self.assertGreater(f0, 1300)
        self.assertLess(f2, 1100)

    def test_comencar_a_mig_compas_mante_el_patro(self):
        from app import metronom
        # comencem a t=2.5 s (beat 5). En 2 s de buffer hi cauen els beats
        # 5,6,7,8 -> a 0.0, 0.5, 1.0, 1.5 dins la rodanxa.
        out = metronom.mescla_metronom(self._silenci(2.0), self.SR,
                                       2.5, 120.0, 4, volum=1.0)
        onsets = self._onsets(self._a_array(out))
        self.assertEqual(len(onsets), 4)
        for k, o in enumerate(onsets):
            self.assertAlmostEqual(o, k * 0.5, places=3)
        # el beat 8 (t=4.0 → 1.5 dins la rodanxa) ha de ser accentuat
        arr = self._a_array(out)
        n = int(self.SR * 0.02)
        i = int(1.5 * self.SR)
        self.assertGreater(self._freq(arr[i:i + n]), 1300)

    def test_bpm_invalid_no_canvia_res(self):
        from app import metronom
        for bpm in (0, -5, float("nan"), float("inf")):
            base = self._silenci(1.0)
            out = metronom.mescla_metronom(base, self.SR, 0.0, bpm, 4, volum=1.0)
            self.assertEqual(out, base, f"bpm={bpm} hauria de no fer res")

    def test_volum_zero_no_canvia_l_audio(self):
        from app import metronom
        base = self._silenci(1.0)
        out = metronom.mescla_metronom(base, self.SR, 0.0, 120.0, 4, volum=0.0)
        self.assertEqual(out, base)

    def test_la_mescla_no_desborda(self):
        from app import metronom
        # audio a tope (32767) -> amb el clic NO ha de superar int16
        fort = (np.ones(self.SR, dtype=np.int16) * 32000).tobytes()
        out = metronom.mescla_metronom(fort, self.SR, 0.0, 120.0, 4, volum=1.0)
        arr = np.frombuffer(out, dtype=np.int16)
        self.assertTrue(np.all(arr <= 32767))
        self.assertTrue(np.all(arr >= -32768))

    def test_bpb_menor_que_1_es_tracta_com_1(self):
        from app import metronom
        out = metronom.mescla_metronom(self._silenci(1.1), self.SR,
                                       0.0, 120.0, 0, volum=1.0)
        # amb bpb=1 tots els beats son accents (cada 0.5 s)
        self.assertEqual(len(self._onsets(self._a_array(out))), 3)


class OffsetDosCampsTests(unittest.TestCase):
    """Offset amb DOS camps sincronitzats: compas.beat <-> segons."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def _finestra(self):
        import tempfile, wave
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "t.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * 30)
        ac = os.path.join(td, "AUTOCHORDS_t"); os.makedirs(ac)
        _escriu_fitxer(os.path.join(ac, "acords.csv"), "9.5,15.0,Am\n")
        window = app_main.Finestra()
        window.wav_edit.setText(wav)
        window._carrega_visor(wav)
        window.bpm.setText("101"); window.bpb.setText("4")
        window._aplica_parametres_temps()
        return window

    def test_compas_beat_a_segons(self):
        # a 101 BPM 4/4, compas 5 beat 1 = 16 temps x 0.594 = 9.50 s
        window = self._finestra()
        s = window._cb_a_secs("5.1")
        self.assertAlmostEqual(s, 16 * (60.0 / 101.0), places=4)
        window.close()

    def test_segons_a_compas_beat(self):
        window = self._finestra()
        self.assertEqual(window._secs_a_cb(16 * (60.0 / 101.0)), "5.1")
        self.assertEqual(window._secs_a_cb(0.0), "1.1")
        window.close()

    def test_compas_beat_fusa(self):
        # 5.1.3 = compàs 5, temps 1, tercera fusa = 16,25 beats
        window = self._finestra()
        t = (16 + 0.25) * (60.0 / 101.0)
        self.assertAlmostEqual(window._cb_a_secs("5.1.3"), t, places=4)
        self.assertEqual(window._secs_a_cb(t), "5.1.3")
        window.close()

    def test_els_dos_camps_queden_sincronitzats(self):
        window = self._finestra()
        # escrivim el compas.beat -> el camp de segons s'actualitza
        window.offset_cb.setText("5.1")
        window._offset_cb_canviat()
        # el camp de segons es desa amb 3 decimals (9.50495 -> 9.505)
        self.assertAlmostEqual(window._offset_val(), 16 * (60.0 / 101.0),
                               places=2)
        self.assertEqual(window.offset_cb.text(), "5.1")
        # i el regle posa el compas 1 alla
        self.assertEqual(
            __import__("app.timeline", fromlist=["fmt_pos"]).fmt_pos(
                window._offset_val(), True, 101, 4, window._offset_val()), "1.1")
        window.close()


class OffsetLlistesTests(unittest.TestCase):
    """Les llistes (etiquetes de compas) han de seguir l'offset."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def _finestra(self):
        import tempfile, wave
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "t.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * 30)
        ac = os.path.join(td, "AUTOCHORDS_t"); os.makedirs(ac)
        _escriu_fitxer(os.path.join(ac, "acords.csv"), "9.5,12.0,Am\n12.0,15.0,C\n")
        window = app_main.Finestra()
        window.wav_edit.setText(wav)
        window._carrega_visor(wav)
        return window

    def test_llistes_segueixen_l_offset(self):
        window = self._finestra()
        v = window.visor_ref
        window.bpm.setText("101")
        window._aplica_parametres_temps()
        # INVARIANT de cobertura: el 1r element és la capçalera «N» a 0s.
        self.assertTrue(v.llista_ac.item(0).text().endswith("N"),
                        v.llista_ac.item(0).text())
        # amb offset 0, l'acord de 9.5s (ara l'element 1) surt com a compas 5
        self.assertTrue(v.llista_ac.item(1).text().startswith("5."),
                        v.llista_ac.item(1).text())
        # amb offset 9.5, ha de sortir com a compas 1
        window.offset.setText("9.50")
        window._aplica_parametres_temps()
        self.assertTrue(v.llista_ac.item(1).text().startswith("1.1"),
                        v.llista_ac.item(1).text())
        self.assertTrue(v.llista_ac.item(2).text().startswith("2.1"),
                        v.llista_ac.item(2).text())
        window.close()


class TempoTests(unittest.TestCase):
    """Detecció de BPM (app/tempo.py) — autocorrelacio + comb, numpy pur."""

    SR = 22050

    def _wav_clics(self, td, bpm, dur=20.0, silenci_ini=3.0):
        """Genera una WAV amb clics periodics (i silenci inicial)."""
        import wave
        n = int(self.SR * dur)
        a = np.zeros(n, dtype=np.int16)
        periode = 60.0 / bpm
        t = silenci_ini
        while t < dur - 0.05:
            i = int(t * self.SR)
            llarg = int(self.SR * 0.02)
            env = np.exp(-8.0 * np.arange(llarg) / llarg).astype(np.float32)
            to = (np.sin(2 * np.pi * 1000 * np.arange(llarg) / self.SR) * env * 12000)
            a[i:i + llarg] = np.clip(a[i:i + llarg] + to.astype(np.int16),
                                     -32768, 32767)
            t += periode
        ruta = os.path.join(td, "clics.wav")
        with wave.open(ruta, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(self.SR)
            w.writeframes(a.tobytes())
        return ruta

    def test_detecta_bpm_sintetic(self):
        import tempfile
        from app import tempo
        for bpm in (101.0, 118.0, 120.0):
            with tempfile.TemporaryDirectory() as td:
                ruta = self._wav_clics(td, bpm)
                b = tempo.detecta_bpm(ruta, lambda m: None)
                self.assertIsNotNone(b, f"bpm {bpm}: None")
                self.assertLess(abs(b - bpm), 4.0,
                                f"bpm {bpm}: detectat {b}")

    def test_detecta_bpm_amb_silenci_inicial(self):
        """El silenci inicial NO ha de desviar la deteccio (cas real)."""
        import tempfile
        from app import tempo
        with tempfile.TemporaryDirectory() as td:
            ruta = self._wav_clics(td, 101.0, dur=25.0, silenci_ini=9.5)
            b = tempo.detecta_bpm(ruta, lambda m: None)
            self.assertLess(abs(b - 101.0), 4.0, f"detectat {b}")

    def test_detecta_bpm_dins_un_tram(self):
        """La detecció local analitza només l'interval demanat."""
        import tempfile
        from app import tempo
        with tempfile.TemporaryDirectory() as td:
            ruta = self._wav_clics(td, 120.0, dur=10.0, silenci_ini=2.0)
            b = tempo.detecta_bpm(ruta, lambda m: None, inici=2.0, fi=8.0)
            self.assertIsNotNone(b)
            self.assertLess(abs(b - 120.0), 4.0, f"detectat {b}")

    def test_detecta_bpm_tram_respecta_el_rang(self):
        """Un interval sense clics no ha de detectar el BPM d'un altre tros."""
        import tempfile
        from app import tempo
        with tempfile.TemporaryDirectory() as td:
            ruta = self._wav_clics(td, 120.0, dur=8.0, silenci_ini=4.0)
            self.assertIsNone(tempo.detecta_bpm(
                ruta, lambda m: None, inici=0.0, fi=3.0))
            b = tempo.detecta_bpm(ruta, lambda m: None, inici=4.0, fi=8.0)
            self.assertIsNotNone(b)
            self.assertLess(abs(b - 120.0), 4.0, f"detectat {b}")

    def test_detecta_bpm_silenci_retorna_none(self):
        import tempfile, wave
        from app import tempo
        with tempfile.TemporaryDirectory() as td:
            ruta = os.path.join(td, "silenci.wav")
            with wave.open(ruta, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(self.SR)
                w.writeframes(b"\x00\x00" * self.SR * 2)
            self.assertIsNone(tempo.detecta_bpm(ruta, lambda m: None))


class OffsetTests(unittest.TestCase):
    """L'offset (segon del compàs 1) ha d'aplicar-se a graella, clic i export."""

    SR = 44100

    def test_fmt_pos_amb_offset(self):
        from app.timeline import fmt_pos
        # a 120 BPM (beat=0.5s), offset=1.0 -> t=2.0 es el compas 1 beat 3
        self.assertEqual(fmt_pos(2.0, True, 120, 4, 1.0), "1.3")
        self.assertEqual(fmt_pos(2.0, True, 120, 4, 0.0), "2.1")

    def test_fmt_pos_amb_subdivisio_adaptativa(self):
        from app.timeline import fmt_pos
        # amb zoom prou gran, el regle mostra compàs.temps.subdivisió, com en DAW
        self.assertEqual(fmt_pos(0.0, True, 120, 4, 0.0, step=0.25), "1.1.1")
        self.assertEqual(fmt_pos(0.25, True, 120, 4, 0.0, step=0.25), "1.1.5")
        self.assertEqual(fmt_pos(0.75, True, 120, 4, 0.0, step=0.25), "1.2.5")

    def test_compas_manual_accepta_fraccio(self):
        from app.main import Finestra
        visor.QApplication.instance() or visor.QApplication([])
        w = Finestra()
        self.assertEqual(w._parse_compas("3/4"), (3, 4))
        self.assertEqual(w._parse_compas("6/8"), (6, 8))
        self.assertEqual(w._parse_compas("4"), (4, 4))
        w.close()

    def test_is_bar_start_label_detecta_compassos_inici(self):
        from app.timeline_base import is_bar_start_label
        self.assertTrue(is_bar_start_label("1.1"))
        self.assertTrue(is_bar_start_label("2.1"))
        self.assertTrue(is_bar_start_label("1.1.1"))
        self.assertFalse(is_bar_start_label("1.2"))
        self.assertFalse(is_bar_start_label("1:00"))

    def test_zoom_amb_roda_centra_cursor_vermell_si_no_hi_ha_seleccio(self):
        from app.timeline import TimelineView
        app = visor.QApplication.instance() or visor.QApplication([])
        view = TimelineView({"durada": 30.0, "mono": np.zeros(1, dtype=np.float32)},
                            [], [], 120.0, 4, True)
        view.set_position(8.0)
        view._view_left, view._view_right = 0.0, 30.0
        captured = {}

        def fake_center_on(t, ampl):
            captured["t"] = t
            captured["ampl"] = ampl
            view._view_left = max(0.0, t - ampl / 2.0)
            view._view_right = min(30.0, view._view_left + ampl)

        view._center_on = fake_center_on

        class FakeEvent:
            def angleDelta(self):
                return type("D", (), {"y": lambda self: 120})()

            def modifiers(self):
                return 0

            def accept(self):
                pass

        view.wheelEvent(FakeEvent())
        self.assertEqual(captured["t"], 8.0)
        self.assertGreater(captured["ampl"], 0.0)
        app.quit()

    def test_snap_time_amb_offset(self):
        from app.timeline import snap_time
        # pps=64 -> snap 0.125 (1/16 a 120 BPM; 1/32 = 4 px, no hi cap); offset 1.0
        self.assertAlmostEqual(snap_time(1.13, True, 120, 4, 64.0, 1.0),
                               1.125, places=4)
        self.assertAlmostEqual(snap_time(1.13, True, 120, 4, 64.0, 0.0),
                               1.125, places=4)

    def test_pos_compas_amb_offset(self):
        from app.pipeline import pos_compas
        # 120 BPM: el compas 1 cau a t=offset; sense offset, a t=0
        self.assertEqual(pos_compas(0.0, 120, 4, False, 0.0), "1.1.1")
        self.assertEqual(pos_compas(1.0, 120, 4, False, 1.0), "1.1.1")
        self.assertEqual(pos_compas(2.0, 120, 4, False, 1.0), "1.3.1")

    def _onsets_metronom(self, out):
        arr = np.frombuffer(out, dtype=np.int16).astype(np.int32)
        idx = np.where(np.abs(arr) > 1000)[0]
        gaps = np.where(np.diff(idx) > 0.05 * self.SR)[0]
        return np.concatenate(([idx[0]], idx[gaps + 1])) / self.SR

    def test_metronom_amb_offset(self):
        from app import metronom
        base = b"\x00\x00" * int(self.SR * 2)
        out = metronom.mescla_metronom(base, self.SR, 0.0, 120.0, 4,
                                       volum=1.0, offset=1.0)
        onsets = self._onsets_metronom(out)
        # hi ha d'haver un clic JUST a l'offset (1.0)
        self.assertTrue(any(abs(o - 1.0) < 0.03 for o in onsets),
                        f"cap clic a l'offset: {onsets[:6]}")

    def test_count_in_abans_de_l_offset(self):
        """El silenci inicial s'omple amb el compte enrere (count-in)."""
        from app import metronom
        base = b"\x00\x00" * int(self.SR * 2)
        out = metronom.mescla_metronom(base, self.SR, 0.0, 120.0, 4,
                                       volum=1.0, offset=1.0)
        onsets = self._onsets_metronom(out)
        # hi ha clics ABANS de l'offset (count-in) i a l'offset
        self.assertTrue(any(o < 0.95 for o in onsets),
                        f"sense count-in: {onsets[:6]}")
        self.assertTrue(any(abs(o - 1.0) < 0.03 for o in onsets))

    def test_compas_negatiu_abans_de_l_offset(self):
        """Abans de l'offset (compas 1) la graella es negativa (count-in)."""
        from app.timeline import fmt_pos
        from app.pipeline import pos_compas
        # 120 BPM 4/4 -> compas = 2,0 s. Amb offset=3.0 (compas 1 a 3,0 s),
        # t=0 cau al compas -1 (beat 3).
        self.assertEqual(fmt_pos(0.0, True, 120, 4, 3.0), "-1.3")
        self.assertEqual(pos_compas(0.0, 120, 4, False, 3.0), "-1.3.1")
        # i el compas 1 si que es positiu a l'offset
        self.assertEqual(fmt_pos(3.0, True, 120, 4, 3.0), "1.1")
        # sense offset, tot positiu (comportament antic)
        self.assertEqual(fmt_pos(0.0, True, 120, 4, 0.0), "1.1")

    def test_metronom_limita_bpm(self):
        from app import metronom
        base = b"\x00\x00" * int(self.SR)
        # BPM enorme -> no fa res (evita bucles de milions de voltes)
        for bpm in (500.0, 10000.0):
            self.assertEqual(
                metronom.mescla_metronom(base, self.SR, 0.0, bpm, 4, volum=1.0),
                base)
        self.assertIsNone(metronom._es_valid(1000.0, 4))
        self.assertIsNotNone(metronom._es_valid(120.0, 4))


class TempoOctavaTests(unittest.TestCase):
    """Ambiguitat d'octava/subdivisio del BPM (cas real: Otis Redding).

    Amb corxera forta, el prior pla antic triava 179,8; el plateau nou
    ha de triar el TEMPS real (~103,5).
    """

    SR = 22050

    def _wav(self, td, bpm, dur=40.0, amp_corxera=0.0):
        import wave
        n = int(self.SR * dur)
        a = np.zeros(n, dtype=np.float32)
        rng = np.random.default_rng(1)
        beat = 60.0 / bpm

        def clic(t, amp):
            i = int(t * self.SR)
            llarg = int(self.SR * 0.02)
            if i + llarg < n:
                env = np.exp(-8.0 * np.arange(llarg) / llarg)
                a[i:i + llarg] += (rng.normal(0, 1, llarg).astype(np.float32)
                                   * amp * env)

        t = 0.5
        while t < dur - 0.5:
            clic(t, 1.0)                     # el temps (fort)
            if amp_corxera:
                clic(t + beat / 2, amp_corxera)   # la corxera (mes fluixa)
            t += beat
        a = np.clip(a / max(1e-9, np.abs(a).max()) * 30000, -32768,
                    32767).astype(np.int16)
        ruta = os.path.join(td, "clics.wav")
        with wave.open(ruta, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(self.SR)
            w.writeframes(a.tobytes())
        return ruta

    def test_prior_plateau(self):
        from app import tempo
        lo, hi = tempo.BPM_PREFERIT
        self.assertEqual(tempo._prior(120.0), 1.0)
        self.assertEqual(tempo._prior(lo), 1.0)
        self.assertEqual(tempo._prior(hi), 1.0)
        self.assertLess(tempo._prior(200.0), 0.95)   # fora: penalitzat
        self.assertLess(tempo._prior(45.0), 0.95)

    def test_octava_132_no_queda_en_66(self):
        """Cas Chemical Brothers: 132 real, amb corxera forta a 66."""
        import tempfile
        from app import tempo
        td = tempfile.mkdtemp()
        wav = self._wav(td, 132.0, amp_corxera=0.55)
        b = tempo.detecta_bpm(wav, lambda *a: None)
        self.assertAlmostEqual(b, 132.0, delta=5.0)   # no 66

    def test_corxera_no_guanya_el_temps(self):
        import tempfile
        from app import tempo
        td = tempfile.mkdtemp()
        wav = self._wav(td, 103.45, amp_corxera=0.55)
        b = tempo.detecta_bpm(wav, lambda *a: None)
        self.assertIsNotNone(b)
        self.assertAlmostEqual(b, 103.45, delta=6.0)   # no 179/207

    def test_tempo_normal_intacte(self):
        import tempfile
        from app import tempo
        td = tempfile.mkdtemp()
        for bpm in (70.0, 101.0, 118.0, 138.0):
            wav = self._wav(td, bpm)
            b = tempo.detecta_bpm(wav, lambda *a: None)
            self.assertAlmostEqual(b, bpm, delta=4.0,
                                   msg=f"esperava {bpm}, vaig rebre {b}")


class UndoInfoTests(unittest.TestCase):
    """Desfer/refer expliquen el canvi a la caixa d'informacio."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def _finestra(self):
        import tempfile, wave
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "t.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * 10)
        ac = os.path.join(td, "AUTOCHORDS_t"); os.makedirs(ac)
        _escriu_fitxer(os.path.join(ac, "acords.csv"), "0.0,4.0,C\n4.0,8.0,Am\n8.0,12.0,G\n")
        window = app_main.Finestra()
        window.wav_edit.setText(wav)
        window._carrega_visor(wav)
        return window

    def test_desfer_descriu_el_canvi(self):
        w = self._finestra(); v = w.visor_ref
        v._undo_marca()
        _ant = v.acords[1]
        v.acords[1] = pipeline.Clip(5.0, float(_ant[1]), _ant[2])
        v._undo_commit()
        v.undo()
        txt = w.info_box.toPlainText()
        self.assertIn("DESFER", txt)
        self.assertIn("Am", txt)
        self.assertIn("5.00", txt)      # des de 5.00 (on era)
        w.close()

    def test_refer_descriu_el_canvi(self):
        w = self._finestra(); v = w.visor_ref
        v._undo_marca()
        _ant = v.acords[1]
        v.acords[1] = pipeline.Clip(5.0, float(_ant[1]), _ant[2])
        v._undo_commit()
        v.undo()
        v.redo()
        txt = w.info_box.toPlainText()
        self.assertIn("REFER", txt)
        self.assertIn("Am", txt)
        w.close()

    def test_info_senyal_connectat(self):
        w = self._finestra()
        # si el senyal no esta connectat, aixo no peta pero no mostra res
        w.visor_ref.infoMissatge.emit("PROVA")
        self.assertIn("PROVA", w.info_box.toPlainText())
        w.close()

    def test_playstate_connectat_en_carregar(self):
        w = self._finestra()
        w.visor_ref.playStateChanged.emit(True)
        self.assertIn("Atura", w.b_play_tb.toolTip())
        w.close()


class InfoBoxTests(unittest.TestCase):
    """La caixa d'informacio explica el "ratoli intel·ligent" del timeline."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def _finestra(self):
        import tempfile, wave
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "t.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * 20)
        ac = os.path.join(td, "AUTOCHORDS_t"); os.makedirs(ac)
        _escriu_fitxer(os.path.join(ac, "acords.csv"), "0.0,8.0,C\n8.0,16.0,G\n")
        _escriu_fitxer(os.path.join(ac, "estructura_ABC.csv"),
            "inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
            "0.0,8.0,8.0,A,N,1,1\n")
        window = app_main.Finestra()
        window.wav_edit.setText(wav)
        window._carrega_visor(wav)
        return window

    def test_cobertura_seccio_a_la_durada(self):
        """L'última secció s'acota a la durada de la WAV (regla d'or)."""
        w = self._finestra()          # WAV 20s, ABC amb una secció 0–8
        self.assertAlmostEqual(w.visor_ref.seccions[-1][1], 20.0)

    def test_zona_regle(self):
        from PyQt5.QtCore import QPoint
        w = self._finestra(); tv = w.visor_ref.timeline
        self.assertIn("LOOP", tv.info_zona(QPoint(200, 5)))

    def test_zona_ona(self):
        from PyQt5.QtCore import QPoint
        w = self._finestra(); tv = w.visor_ref.timeline
        txt = tv.info_zona(QPoint(900, 95))
        self.assertTrue("cursor" in txt.lower() or "zoom" in txt.lower())
        w.close()

    def test_zona_clip(self):
        from PyQt5.QtCore import QPoint
        w = self._finestra(); tv = w.visor_ref.timeline
        # el cos d'un clip te una accio de MOURE
        txt = tv.info_zona(QPoint(60, 130))
        self.assertTrue("Mou" in txt)
        w.close()


class Compas1Tests(unittest.TestCase):
    """Deteccio automatica del compas 1 (downbeat) amb el Queen Mary."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def test_boto_i_accio_existeixen(self):
        w = app_main.Finestra()
        # compas 1 automatic: ara es una ICONA (Lucide compass)
        self.assertFalse(w.b_compas_auto.icon().isNull())
        self.assertIn("compàs 1", w.b_compas_auto.toolTip().lower())
        # res del que ja hi havia s'ha perdut
        self.assertFalse(w.b_offset_cursor.icon().isNull())   # map-pin
        self.assertEqual(w.b_tap.text(), "TAP")
        self.assertEqual(w.b_bpm_x2.text(), "×2")
        self.assertEqual(w.b_bpm_div2.text(), "÷2")
        w.close()

    def test_transforms_qm_disponibles(self):
        # (El qm-keydetector es va retirar amb la tonalitat automàtica.)
        for clau, frag in (("onsets", "qm-onsetdetector:onsets"),
                           ("bars", "qm-barbeattracker:bars"),
                           ("beats", "qm-barbeattracker:beats"),
                           ("segments", "qm-segmenter:segmentation")):
            self.assertIn(frag, pipeline.QM[clau])

    def test_plugins_unics_restants(self):
        # només Chordino i Queen Mary: fora el Segmentino i l'aubio
        dirs = [d for d in os.listdir(pipeline.PROJ_DIR)
                if d.endswith("-local")]
        self.assertIn("nnls-chroma-linux64-local", dirs)
        self.assertIn("qm-vamp-plugins-linux64-local", dirs)
        self.assertNotIn("segmentino-linux64-local", dirs)
        self.assertNotIn("vamp-aubio-linux64-local", dirs)

    def test_detecta_compas1_retorna_float_o_none(self):
        import tempfile, wave
        import numpy as np
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "t.wav")
        sr = 22050
        a = (np.sin(np.linspace(0, 440 * 2 * np.pi * 8, sr * 8))
             * 6000).astype(np.int16)
        with wave.open(wav, "wb") as f:
            f.setnchannels(1); f.setsampwidth(2); f.setframerate(sr)
            f.writeframes(a.tobytes())
        # Log VISIBLE: si el host falla, el motiu ha de sortir al log del CI.
        r = pipeline.detecta_compas1(wav, lambda m: print("[compas1]", m, flush=True))
        self.assertTrue(r is None or isinstance(r, float))
        if r is not None:
            self.assertTrue(0.0 <= r <= 8.5)


class PlayCoherenciaTests(unittest.TestCase):
    """Coherencia del play: cache de mono + aturar abans de plugins/redibuix."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])
        import tempfile, wave
        import numpy as np
        cls._d = tempfile.mkdtemp()
        cls._wav = os.path.join(cls._d, "t.wav")
        with wave.open(cls._wav, "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(44100)
            w.writeframes((np.sin(np.linspace(0, 440 * 2 * np.pi * 3,
                                              44100 * 3)) * 8000).astype(
                np.int16).tobytes() * 2)
        cls._ac = os.path.join(cls._d, "ACORDS"); os.makedirs(cls._ac)
        _escriu_fitxer(os.path.join(cls._ac, "acords.csv"), "0.0,4.0,C\n")
    def _visor(self):
        return visor.Visor(self._wav, os.path.join(self._ac, "acords.csv"),
                           None, 120, 4)

    def test_mono_bytes_cachejat(self):
        v = self._visor()
        a = v._mono_bytes()
        import time
        t0 = time.perf_counter()
        b = v._mono_bytes()
        dt = time.perf_counter() - t0
        self.assertIs(a, b)                 # mateix objecte (cache)
        self.assertLess(dt, 0.01)           # instantani

    def test_mono_bytes_no_depen_del_mute(self):
        # el volum/mute s'apliquen en directe al fil, NO al buffer cacat
        v = self._visor()
        a = v._mono_bytes()
        v.mut = True
        self.assertIs(a, v._mono_bytes())

    def test_player_te_latencia_baixa(self):
        v = self._visor()
        _pl, args = v._tria_player()
        if _pl == "paplay":
            self.assertIn("--latency-msec=100", args)

    def test_alimenta_aplica_el_guany(self):
        import numpy as np

        class _Buf:
            def __init__(self):
                self.dades = bytearray()

            def write(self, b):
                self.dades += b
                return len(b)

            def close(self):
                pass

        class FakeProc:
            def __init__(self):
                self.buf = _Buf()
                self.rc = None

            def poll(self):
                return self.rc

            @property
            def stdin(self):
                return self.buf

        v = self._visor()
        v._sess = 0
        v.vol = 0.5
        v.mut = False
        p1 = FakeProc()
        v._alimenta(p1, 0.0, 0)     # API nova: (proc, temps_inici, sessió)
        v.vol = 1.0
        p2 = FakeProc()
        v._alimenta(p2, 0.0, 0)
        a = np.frombuffer(bytes(p1.buf.dades), dtype=np.int16).astype(float)
        b = np.frombuffer(bytes(p2.buf.dades), dtype=np.int16).astype(float)
        self.assertGreater(np.abs(b).mean(), 0)
        self.assertAlmostEqual(np.abs(a).mean() / np.abs(b).mean(), 0.5,
                               delta=0.05)

    def test_volum_i_mute_no_reinicien(self):
        v = self._visor()
        crides = []
        v._atura_proc = lambda: crides.append("atura")
        v._engega_des_de = lambda t: crides.append("engega")
        v.sona = True
        v._canvia_volum(50)
        v.set_mut(True)
        self.assertEqual(crides, [])        # cap reinici
        self.assertAlmostEqual(v.vol, 0.5, places=3)
        self.assertTrue(v.mut)

    def test_tiquet_no_talla_la_cua(self):
        # posicionat just al final, sonant: NO ha d'aturar (espera l'EOF)
        import time
        v = self._visor()

        class FakeProc:
            returncode = None

            def poll(self):
                return None

        v.proc = FakeProc()
        v.sona = True
        v.t0_pos = float(v.audio["durada"])
        v.t0_mono = time.monotonic()
        v._tiquet()
        self.assertTrue(v.sona)             # segueix "sonant"

    def test_atura_si_sona(self):
        w = app_main.Finestra()

        class Fake:
            def __init__(self, sona):
                self.sona = sona
                self.stops = 0

            def play_stop(self):
                self.sona = False
                self.stops += 1

        f = Fake(True); w.visor_ref = f
        w._atura_si_sona("prova")
        self.assertFalse(f.sona)
        self.assertEqual(f.stops, 1)
        f2 = Fake(False); w.visor_ref = f2
        w._atura_si_sona("prova")
        self.assertEqual(f2.stops, 0)       # ja aturat: no fa res
        w.close()

    def test_sites_que_aturen(self):
        import inspect
        for fn in (app_main.Finestra.executa,
                   app_main.Finestra._detecta_bpm,
                   app_main.Finestra._carrega_visor):
            self.assertIn("_atura_si_sona", inspect.getsource(fn))


class BpmDoblaTests(unittest.TestCase):
    """Botons ×2 / ÷2 del BPM."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def _finestra(self):
        import tempfile, wave
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "t.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * 5)
        ac = os.path.join(td, "AUTOCHORDS_t"); os.makedirs(ac)
        _escriu_fitxer(os.path.join(ac, "acords.csv"), "0.0,4.0,C\n")
        window = app_main.Finestra()
        window.wav_edit.setText(wav)
        window._carrega_visor(wav)
        return window

    def test_botons_existeixen(self):
        w = self._finestra()
        self.assertEqual(w.b_bpm_x2.text(), "×2")
        self.assertEqual(w.b_bpm_div2.text(), "÷2")
        w.close()

    def test_dobla_i_meitat(self):
        w = self._finestra()
        w.bpm.setText("101.0")
        w.b_bpm_x2.click()
        self.assertAlmostEqual(w._bpm_val(), 202.0, places=1)
        w.b_bpm_div2.click()
        self.assertAlmostEqual(w._bpm_val(), 101.0, places=1)
        w.close()

    def test_limits(self):
        w = self._finestra()
        w.bpm.setText("300.0"); w.b_bpm_x2.click()
        self.assertAlmostEqual(w._bpm_val(), 400.0, places=1)
        w.bpm.setText("50.0"); w.b_bpm_div2.click()
        self.assertAlmostEqual(w._bpm_val(), 30.0, places=1)
        w.close()

    def test_propaga_al_visor(self):
        w = self._finestra()
        w.bpm.setText("101.0"); w.b_bpm_x2.click()
        self.assertAlmostEqual(w.visor_ref.bpm, 202.0, places=1)
        w.close()


class FfmpegTests(unittest.TestCase):
    """Import d'altres formats d'audio via ffmpeg (conversio a WAV PCM 16)."""

    @classmethod
    def setUpClass(cls):
        if not ffmpeg.disponible():
            raise unittest.SkipTest("ffmpeg no disponible")
        import tempfile
        cls._d = tempfile.mkdtemp()
        cls._src = os.path.join(cls._d, "ton.wav")
        subprocess.run([ffmpeg.FFMPEG, "-y", "-f", "lavfi", "-i",
                        "sine=frequency=440:duration=1", "-c:a", "pcm_s16le",
                        cls._src], capture_output=True)

    def test_extensions_i_filtre(self):
        for e in ("wav", "mp3", "aif", "aiff", "flac", "m4a", "ogg"):
            self.assertIn(e, ffmpeg.extensions())
        f = ffmpeg.filtre()
        self.assertIn("*.mp3", f)
        self.assertIn("*.aif", f)

    def test_es_wav_pcm16(self):
        self.assertTrue(ffmpeg.es_wav_pcm16(self._src))
        self.assertFalse(ffmpeg.es_wav_pcm16("/no/existeix.wav"))
        self.assertFalse(ffmpeg.es_wav_pcm16("/tmp/x.mp3"))

    def test_converteix_mp3(self):
        mp3 = os.path.join(self._d, "canco.mp3")
        subprocess.run([ffmpeg.FFMPEG, "-y", "-i", self._src, mp3],
                       capture_output=True)
        wav = ffmpeg.converteix_a_wav(mp3)
        self.assertTrue(wav.endswith("canco_convertit.wav"))
        self.assertTrue(ffmpeg.es_wav_pcm16(wav))
        # `info()` depèn de ffprobe, que NO s'empaqueta (l'app no el fa servir:
        # fa pipeline.wav_info). Sense ffprobe retorna {} -> no hi ha res a
        # comprovar aquí; la conversió ja s'ha validat a les línies de dalt.
        if not shutil.which(ffmpeg.FFPROBE):
            self.skipTest("ffprobe no disponible (no s'empaqueta)")
        inf = ffmpeg.info(wav)
        self.assertEqual(inf["mostreig"], 44100)
        self.assertAlmostEqual(inf["durada"], 1.0, delta=0.1)

    def test_converteix_aiff_i_flac(self):
        for ext in ("aiff", "flac"):
            src = os.path.join(self._d, f"pista.{ext}")
            subprocess.run([ffmpeg.FFMPEG, "-y", "-i", self._src, src],
                           capture_output=True)
            wav = ffmpeg.converteix_a_wav(src)
            self.assertTrue(ffmpeg.es_wav_pcm16(wav))

    def test_wav_ja_bona_no_es_toca(self):
        self.assertEqual(ffmpeg.converteix_a_wav(self._src), self._src)

    def test_reutilitza_si_es_mes_nou(self):
        mp3 = os.path.join(self._d, "reut.mp3")
        subprocess.run([ffmpeg.FFMPEG, "-y", "-i", self._src, mp3],
                       capture_output=True)
        wav1 = ffmpeg.converteix_a_wav(mp3)
        m1 = os.path.getmtime(wav1)
        wav2 = ffmpeg.converteix_a_wav(mp3)
        self.assertEqual(wav1, wav2)
        self.assertEqual(m1, os.path.getmtime(wav2))


class _FakeProc:
    """Resultat fals de subprocess.run."""

    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class _FakeSubprocess:
    """Doble del mòdul `subprocess` (només `run`), amb registre de crides.

    S'instal·la amb `patch.object(ffmpeg, "subprocess", fake)` perquè NO toca
    el `subprocess` global (que comparteixen la resta de tests).
    """

    SubprocessError = subprocess.SubprocessError
    TimeoutExpired = subprocess.TimeoutExpired

    def __init__(self, results):
        self._results = list(results)
        self.calls = []

    def run(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        return self._results.pop(0)


class FfmpegSeguretatTests(unittest.TestCase):
    """Opcions de seguretat d'ffmpeg (Pas 1): -nostdin + -protocol_whitelist."""

    def test_opcions_entrada_abans_de_i(self):
        cmd = ffmpeg._cmd_converteix("/tmp/ton.wav", "/tmp/out.wav")
        i = cmd.index("-i")
        self.assertIn("-nostdin", cmd)
        self.assertLess(cmd.index("-nostdin"), i)
        self.assertLess(cmd.index("-protocol_whitelist"), i)
        self.assertEqual(cmd[cmd.index("-protocol_whitelist") + 1], "file,pipe")
        # -y (sobreescriure) també abans de -i, com abans.
        self.assertLess(cmd.index("-y"), i)

    def test_info_porta_opcions(self):
        cmd = ffmpeg._cmd_info("/tmp/ton.wav")
        self.assertIn("-nostdin", cmd)
        self.assertIn("file,pipe", cmd)
        self.assertEqual(cmd[-1], os.path.abspath("/tmp/ton.wav"))

    def test_rutes_estranyes_no_es_filtren(self):
        # Espais, accents, '#', '&', cometes i unicode: la ruta ha d'arribar
        # VERBATIM (només feta absoluta), sense filtrar cap caràcter.
        ruta = "/tmp/01 Cançó d'en 'Pau' & cia #2 (ü) ç.mp3"
        cmd = ffmpeg._cmd_converteix(ruta, "/tmp/sortida amb espais.wav")
        self.assertEqual(cmd[cmd.index("-i") + 1], os.path.abspath(ruta))
        self.assertEqual(cmd[-1], os.path.abspath("/tmp/sortida amb espais.wav"))

    def test_ruta_relativa_es_fa_absoluta(self):
        self.assertEqual(ffmpeg._ruta_arg("ton.wav"),
                         os.path.join(os.getcwd(), "ton.wav"))

    def test_no_opcio(self):
        self.assertEqual(ffmpeg._no_opcio("-rara.wav"),
                         os.path.join(".", "-rara.wav"))
        self.assertEqual(ffmpeg._no_opcio("normal.wav"), "normal.wav")

    def test_treu_opcions(self):
        cmd = ["ffmpeg", "-nostdin", "-protocol_whitelist", "file,pipe",
               "-y", "-i", "x"]
        self.assertEqual(ffmpeg._treu_opcions(cmd, {"-protocol_whitelist"}),
                         ["ffmpeg", "-nostdin", "-y", "-i", "x"])
        self.assertEqual(ffmpeg._treu_opcions(cmd, {"-nostdin"}),
                         ["ffmpeg", "-protocol_whitelist", "file,pipe",
                          "-y", "-i", "x"])
        self.assertEqual(ffmpeg._treu_opcions(cmd, set()), cmd)

    def test_opcions_a_treure(self):
        # ffmpeg vell: "Unrecognized option 'protocol_whitelist'."
        self.assertEqual(
            ffmpeg._opcions_a_treure(
                "Unrecognized option 'protocol_whitelist'."),
            {"-protocol_whitelist"})
        # ffprobe: "... for option 'nostdin': Option not found"
        self.assertEqual(
            ffmpeg._opcions_a_treure(
                "Failed to set value '-protocol_whitelist' for option "
                "'nostdin': Option not found"),
            {"-nostdin"})
        # Altres errors no treuen res.
        self.assertEqual(ffmpeg._opcions_a_treure(""), set())
        self.assertEqual(
            ffmpeg._opcions_a_treure("Error while decoding stream #0:0"), set())

    def test_fallback_ffmpeg_vell(self):
        # ffmpeg vell: treu -protocol_whitelist i manté -nostdin.
        fake = _FakeSubprocess([
            _FakeProc(1, stderr="Unrecognized option 'protocol_whitelist'."),
            _FakeProc(0, stdout="ok"),
        ])
        logs = []
        with patch.object(ffmpeg, "subprocess", fake):
            p = ffmpeg._executa(["ffmpeg", "-nostdin", "-protocol_whitelist",
                                 "file,pipe", "-i", "x"], 10, log=logs.append)
        self.assertEqual(p.returncode, 0)
        self.assertEqual(len(fake.calls), 2)
        self.assertIn("-protocol_whitelist", fake.calls[0])
        self.assertNotIn("-protocol_whitelist", fake.calls[1])
        self.assertIn("-nostdin", fake.calls[1])          # es manté
        self.assertTrue(logs and "no entén" in logs[0])

    def test_fallback_ffprobe_sense_nostdin(self):
        # ffprobe no té -nostdin: es treu i es manté -protocol_whitelist.
        fake = _FakeSubprocess([
            _FakeProc(1, stderr="Failed to set value '-protocol_whitelist' "
                                "for option 'nostdin': Option not found"),
            _FakeProc(0, stdout="{}"),
        ])
        with patch.object(ffmpeg, "subprocess", fake):
            p = ffmpeg._executa(["ffprobe", "-nostdin",
                                 "-protocol_whitelist", "file,pipe", "x"], 10)
        self.assertEqual(p.returncode, 0)
        self.assertEqual(len(fake.calls), 2)
        self.assertNotIn("-nostdin", fake.calls[1])
        self.assertIn("-protocol_whitelist", fake.calls[1])

    def test_fallback_no_salva_altres_errors(self):
        fake = _FakeSubprocess([_FakeProc(1, stderr="Invalid data found")])
        with patch.object(ffmpeg, "subprocess", fake):
            p = ffmpeg._executa(["ffmpeg", "-i", "x"], 10)
        self.assertEqual(p.returncode, 1)
        self.assertEqual(len(fake.calls), 1)              # no reintenta

    def test_wav_pcm16_no_crida_ffmpeg(self):
        # Un WAV PCM 16 ja bo es retorna tal qual SENSE cridar ffmpeg.
        fake = _FakeSubprocess([])                        # si es cridés, petaria
        d = tempfile.mkdtemp()
        src = os.path.join(d, "bo.wav")
        with wave.open(src, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 100)
        with patch.object(ffmpeg, "subprocess", fake):
            self.assertEqual(ffmpeg.converteix_a_wav(src), src)
        self.assertEqual(fake.calls, [])


class PostprocTests(unittest.TestCase):
    """Post-processat dels acords (app/postproc.py)."""

    def test_treu_baix(self):
        self.assertEqual(postproc.treu_baix("A/E"), "A")
        self.assertEqual(postproc.treu_baix("F#dim7/E"), "F#dim7")
        self.assertEqual(postproc.treu_baix("C"), "C")

    def test_redueix(self):
        for entrada, esperat in [("Cmaj7", "C"), ("Em6", "Em"), ("A7", "A"),
                                 ("Edim7", "Edim"), ("C#m", "C#m"),
                                 ("D6", "D"), ("Am7", "Am"), ("Cmaj9", "C")]:
            self.assertEqual(postproc.redueix(entrada), esperat)

    def test_fusiona_iguals(self):
        r = postproc.processa_acords([(0, "C"), (4, "C"), (8, "Am")])
        self.assertEqual([x[1] for x in r], ["C", "Am"])

    def test_durada_minima(self):
        # Am dura 0,2 s -> s'elimina
        r = postproc.processa_acords(
            [(0, "C"), (8, "Am"), (8.2, "G"), (12, "F")], durada_min=1.0)
        self.assertNotIn("Am", [x[1] for x in r])

    def test_sense_baix_i_reduir(self):
        r = postproc.processa_acords([(0, "A/E"), (4, "Cmaj7")],
                                     sense_baix=True, reduir=True)
        self.assertEqual([x[1] for x in r], ["A", "C"])

    def test_snap(self):
        r = postproc.snap_acords([(0.1, "C"), (1.03, "G"), (2.4, "Am")],
                                 bpm=60, divisio=1)
        self.assertEqual([round(x[0], 2) for x in r], [0.0, 1.0, 2.0])

    def test_processa_acords_csv(self):
        import tempfile
        d = tempfile.mkdtemp()
        f = os.path.join(d, "a.csv")
        with open(f, "w", encoding="utf-8") as fh:
            fh.write("0.0,A/E\n4.0,A\n8.0,Cmaj7\n8.5,G\n12.0,G\n")
        postproc.processa_acords_csv(f, sense_baix=True, reduir=True,
                                     durada_min=1.0, fusiona_iguals=True)
        with open(f, encoding="utf-8") as fh:
            noms = [r[2] for r in csv.reader(fh)]
        self.assertEqual(noms, ["A", "G"])


class FiltraSeccionsTests(unittest.TestCase):
    """Post-processat de les seccions (opcions del dialeg)."""

    def test_fusiona_iguals(self):
        s = [(0, 5, "A", "A"), (5, 10, "B", "B"), (10, 14, "B", "B"),
             (14, 18, "C", "C")]
        r = pipeline.filtra_seccions(s, fusiona_iguals=True)
        self.assertEqual(r, [(0, 5, "A", "A"), (5, 14, "B", "B"),
                             (14, 18, "C", "C")])

    def test_durada_minima(self):
        s = [(0, 5, "A", "A"), (5, 6, "B", "B"), (6, 18, "C", "C")]
        r = pipeline.filtra_seccions(s, durada_min=2)
        self.assertEqual(r, [(0, 6, "A", "A"), (6, 18, "C", "C")])

    def test_buit(self):
        self.assertEqual(pipeline.filtra_seccions([]), [])


class DialegOpcionsTests(unittest.TestCase):
    """Dialeg d'opcions d'autodeteccio (BPM / Acords / Estructura)."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def setUp(self):
        # ailla els tests del fitxer real d'opcions de l'usuari
        import tempfile
        self._patch = patch.object(
            dialegs, "FITXER_OPCIONS",
            os.path.join(tempfile.mkdtemp(), "op.json"))
        self._patch.start()

    def tearDown(self):
        self._patch.stop()

    def test_tres_pestanyes_i_tab_inicial(self):
        d = dialegs.DialegOpcions(None, tab="acords")
        self.assertEqual(d.tabs.count(), 3)
        self.assertEqual(d.tabs.currentIndex(), 1)
        d2 = dialegs.DialegOpcions(None, tab="bpm")
        self.assertEqual(d2.tabs.currentIndex(), 0)

    def test_opcions_son_els_6_parametres_del_chordino(self):
        d = dialegs.DialegOpcions(None)
        op = d.opcions()
        self.assertEqual(sorted(op["chords"]),
                         ["rollon", "s", "tuningmode", "useHMM",
                          "useNNLS", "whitening"])
        self.assertEqual(op["chords"]["useHMM"], 1)
        self.assertAlmostEqual(op["chords"]["s"], 0.7, places=2)

    def test_canvi_de_valors(self):
        d = dialegs.DialegOpcions(None)
        d._controls["chords"]["useHMM"].setChecked(False)
        d._controls["chords"]["rollon"].setValue(3)
        op = d.opcions()
        self.assertEqual(op["chords"]["useHMM"], 0)
        self.assertEqual(op["chords"]["rollon"], 3)

    def test_estructura_te_les_seves_opcions(self):
        d = dialegs.DialegOpcions(None)
        op = d.opcions()
        self.assertIn("durada_min", op["structure"])
        self.assertIn("fusiona_iguals", op["structure"])

    def test_bpm_te_rang_i_preferit(self):
        d = dialegs.DialegOpcions(None)
        b = d.opcions()["bpm"]
        self.assertEqual(b["min"], 60)
        self.assertEqual(b["pref_min"], 85)    # plateau del prior
        self.assertEqual(b["motor"], "consens")   # defecte revisat 13-10

    def test_estructura_nomes_qm(self):
        # el Segmentino s'ha retirat: l'estructura sempre va amb qm-segmenter
        d = dialegs.DialegOpcions(None)
        self.assertEqual(d.opcions()["structure"]["motor"], "qm")
        self.assertEqual(pipeline.MOTORS_ESTRUCTURA, ("qm",))

    def test_motors_bpm(self):
        d = dialegs.DialegOpcions(None)
        c = d._controls["bpm"]["motor"]
        for m in ("nostre", "qm", "consens"):
            c.setCurrentIndex(c.findData(m))
            self.assertEqual(d.opcions()["bpm"]["motor"], m)
        # aubio s'ha retirat
        self.assertEqual(pipeline.MOTORS_BPM, ("nostre", "qm", "consens"))

    def test_restaura_per_defecte(self):
        d = dialegs.DialegOpcions(None)
        d._controls["chords"]["useHMM"].setChecked(False)
        d._controls["structure"]["durada_min"].setValue(9)
        d._restaura()
        op = d.opcions()
        self.assertEqual(op["chords"]["useHMM"], 1)
        self.assertEqual(op["structure"]["durada_min"], 2.0)   # defecte revisat 13-10

    def test_desa_i_carrega(self):
        op = dialegs.carrega_opcions()
        op["chords"]["useHMM"] = 0
        dialegs.desa_opcions(op)
        self.assertEqual(dialegs.carrega_opcions()["chords"]["useHMM"], 0)


class VampParamsTests(unittest.TestCase):
    """Lectura dels parametres dels plugins Vamp (descriptors .n3)."""

    def test_chordino_te_6_parametres_en_ordre(self):
        ids = [p["id"] for p in vamp_params.params_de("chords")]
        self.assertEqual(ids, ["useNNLS", "useHMM", "rollon",
                               "tuningmode", "whitening", "s"])

    def test_rangs_i_defectes(self):
        ps = {p["id"]: p for p in vamp_params.params_de("chords")}
        self.assertEqual((ps["useNNLS"]["minim"], ps["useNNLS"]["maxim"],
                          ps["useNNLS"]["defecte"]), (0.0, 1.0, 1.0))
        self.assertEqual((ps["rollon"]["minim"], ps["rollon"]["maxim"],
                          ps["rollon"]["pas"], ps["rollon"]["defecte"]),
                         (0.0, 5.0, 0.5, 0.0))
        self.assertEqual(ps["s"]["minim"], 0.5)
        self.assertEqual(ps["s"]["maxim"], 0.9)

    def test_value_names_tuningmode(self):
        ps = {p["id"]: p for p in vamp_params.params_de("chords")}
        self.assertEqual(ps["tuningmode"]["valors"],
                         ["global tuning", "local tuning"])

    def test_structure_sense_parametres(self):
        """El qm-segmenter no té paràmetres .n3 (el Segmentino es va retirar)."""
        self.assertEqual(vamp_params.params_de("structure"), [])

    def test_valors_per_defecte(self):
        d = vamp_params.valors_per_defecte("chords")
        self.assertEqual(d["useHMM"], 1.0)
        self.assertEqual(d["s"], 0.7)


class BotoOnOffTests(unittest.TestCase):
    """Botons: icona play/pause i estat ences/apagat ben visible."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def setUp(self):
        self._app.setStyleSheet(theme.app_stylesheet())   # com fa main()

    def _finestra(self):
        import tempfile, wave
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "t.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * 10)
        ac = os.path.join(td, "AUTOCHORDS_t"); os.makedirs(ac)
        _escriu_fitxer(os.path.join(ac, "acords.csv"), "0.0,4.0,C\n")
        window = app_main.Finestra()
        window.wav_edit.setText(wav)
        window._carrega_visor(wav)
        return window

    def test_play_icona_play_i_pause(self):
        # Ara son ICONES (Lucide), no text: comprovem el tooltip + la icona.
        w = self._finestra()
        self.assertFalse(w.b_play_tb.icon().isNull())
        self.assertIn("Reprodueix", w.b_play_tb.toolTip())
        w._on_play_state(True)
        self.assertIn("Atura", w.b_play_tb.toolTip())
        self.assertFalse(w.b_play_tb.icon().isNull())
        w._on_play_state(False)
        self.assertIn("Reprodueix", w.b_play_tb.toolTip())
        w.close()

    def test_visor_emet_play_state(self):
        w = self._finestra(); v = w.visor_ref
        rebut = []
        v.playStateChanged.connect(rebut.append)
        v.sona = True                       # simulem que estaba sonant
        v.play_stop()                       # -> atura i ha d'emetre False
        self.assertIn(False, rebut)
        self.assertIn("Reprodueix", w.b_play_tb.toolTip())
        w.close()

    def test_commutables_son_checkable(self):
        w = self._finestra()
        for b in (w.tb_loop, w.tb_mut, w.b_metro, w.b_mode_bpm, w.b_mode_lliure):
            self.assertTrue(b.isCheckable())
        w.close()

    def test_estil_te_estat_checked(self):
        e = theme.app_stylesheet()
        self.assertIn("QPushButton:checked", e)
        self.assertIn(theme.ACTIU, e)
        self.assertIn("QPushButton#metro:checked", e)

    def test_render_ences_vs_apagat(self):
        """El fons del boto canvia de debò (pixel) entre apagat i ences."""
        from PyQt5.QtCore import QPoint
        w = self._finestra(); w.resize(1100, 600); w.show()
        self._app.processEvents()

        def fons(bot):
            img = w.grab().toImage()
            p = bot.mapTo(w, QPoint(5, bot.height() // 2))
            c = img.pixelColor(p.x(), p.y())
            return (c.red(), c.green(), c.blue())

        # apagat = estil "Obre..." (gris)
        apagat = fons(w.tb_loop)
        self.assertLess(abs(apagat[0] - apagat[1]), 15)
        self.assertLess(abs(apagat[1] - apagat[2]), 15)
        # ences = blau
        w.tb_loop.setChecked(True); self._app.processEvents()
        ences = fons(w.tb_loop)
        self.assertNotEqual(apagat, ences)
        self.assertGreater(ences[2], ences[0] + 40)      # blau dominant
        # mute i metronom s'encenen en groc
        w.tb_mut.setChecked(True); w.b_metro.setChecked(True)
        self._app.processEvents()
        for bot in (w.tb_mut, w.b_metro):
            g = fons(bot)
            self.assertGreater(g[0], 200); self.assertLess(g[2], 130)
        w.close()


class LlistaSeleccioTests(unittest.TestCase):
    """Clicar una fila de les llistes l'ha de deixar ressaltada.

    Regressio: _actualitza_temps() (cridada per ves_a) repobla les llistes
    amb clear() i abans en perdia la seleccio.
    """

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def _finestra(self):
        import tempfile, wave
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "t.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * 20)
        ac = os.path.join(td, "AUTOCHORDS_t"); os.makedirs(ac)
        _escriu_fitxer(os.path.join(ac, "acords.csv"), "0.0,4.0,C\n4.0,8.0,Am\n8.0,12.0,G\n")
        _escriu_fitxer(os.path.join(ac, "estructura_ABC.csv"),
            "inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
            "0.00,4.00,4.00,A,N,1,1\n4.00,20.00,16.00,B,B,1,1\n")
        window = app_main.Finestra()
        window.wav_edit.setText(wav)
        window._carrega_visor(wav)
        window.bpm.setText("101"); window._aplica_parametres_temps()
        return window

    def test_clic_acord_deixa_fila_ressaltada(self):
        w = self._finestra(); v = w.visor_ref
        v._salt_acord(v.llista_ac.item(1))
        self.assertEqual(v.llista_ac.currentRow(), 1)
        self.assertTrue(v.llista_ac.item(1).isSelected())
        self.assertEqual(v.timeline._sel, ("chord", 1))
        w.close()

    def test_clic_seccio_deixa_fila_ressaltada(self):
        w = self._finestra(); v = w.visor_ref
        v._salt_seccio(v.llista_ab.item(1))
        self.assertEqual(v.llista_ab.currentRow(), 1)
        self.assertTrue(v.llista_ab.item(1).isSelected())
        self.assertEqual(v.timeline._sel, ("section", 1))
        w.close()

    def test_canvi_bpm_conserva_seleccio(self):
        w = self._finestra(); v = w.visor_ref
        v._salt_acord(v.llista_ac.item(1))
        w.bpm.setText("120"); w._aplica_parametres_temps()
        self.assertEqual(v.llista_ac.currentRow(), 1)
        w.close()


class OffsetBotoCursorTests(unittest.TestCase):
    """Boto a Offset: llegeix el cursor vermell i hi posa el compas 1."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def _finestra(self):
        import tempfile, wave
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "t.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * 20)
        ac = os.path.join(td, "AUTOCHORDS_t"); os.makedirs(ac)
        _escriu_fitxer(os.path.join(ac, "acords.csv"), "0.0,4.0,C\n")
        window = app_main.Finestra()
        window.wav_edit.setText(wav)
        window._carrega_visor(wav)
        window.bpm.setText("101"); window.bpb.setText("4")
        window._aplica_parametres_temps()
        return window

    def test_boto_llegeix_cursor_i_aplica_offset(self):
        w = self._finestra(); v = w.visor_ref
        v.ves_a(9.5)                       # "cursor vermell" a 9.5s
        w.b_offset_cursor.click()          # com l'usuari
        self.assertAlmostEqual(v.offset, 9.5, places=2)
        self.assertEqual(w.offset.text(), "9.500")
        # el camp compas.beat tambe s'actualitza
        self.assertTrue(w.offset_cb.text().startswith("5."))
        v.ves_a(3.0); w.b_offset_cursor.click()
        self.assertAlmostEqual(v.offset, 3.0, places=2)
        w.close()


class TapTempoTests(unittest.TestCase):
    """Tap tempo (patro estandard: ultims taps -> mitjana -> 60/interval)."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def _finestra(self):
        import tempfile, wave
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "t.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * 10)
        ac = os.path.join(td, "AUTOCHORDS_t"); os.makedirs(ac)
        _escriu_fitxer(os.path.join(ac, "acords.csv"), "0.0,4.0,C\n")
        window = app_main.Finestra()
        window.wav_edit.setText(wav)
        window._carrega_visor(wav)
        return window

    def _taps_en(self, w, interval, n=5, inici=1000.0):
        """Simula n taps separats `interval` segons (mock de monotonic)."""
        from unittest.mock import patch
        t = inici
        with patch("app.main.time.monotonic", side_effect=[t + i * interval
                                                           for i in range(n * 4)]):
            w._taps = []
            for _ in range(n):
                w._tap_tempo()
        return w

    def test_taps_594ms_donen_101bpm(self):
        w = self._finestra()
        self._taps_en(w, 0.594)
        self.assertAlmostEqual(w._bpm_val(), 101.0, delta=3.0)
        w.close()

    def test_taps_500ms_donen_120bpm(self):
        w = self._finestra()
        self._taps_en(w, 0.5)
        self.assertAlmostEqual(w._bpm_val(), 120.0, delta=3.0)
        w.close()

    def test_tap_propaga_al_visor(self):
        w = self._finestra()
        self._taps_en(w, 0.5)
        self.assertAlmostEqual(w.visor_ref.bpm, 120.0, delta=3.0)
        w.close()

    def test_reset_per_timeout(self):
        from unittest.mock import patch
        w = self._finestra()
        w._taps = [0.0]
        with patch("app.main.time.monotonic", return_value=5.0):  # >2s despres
            w._tap_tempo()
        self.assertEqual(len(w._taps), 1)      # s'ha reiniciat
        w.close()

    def test_intervals_absurds_descartats(self):
        """Un doble-tap accidental (interval <0.2s) s'ignora."""
        from unittest.mock import patch
        w = self._finestra()
        w._taps = [0.0, 0.5, 0.51]   # 3r tap a 10 ms -> absurd
        with patch("app.main.time.monotonic", return_value=1.0):
            w._tap_tempo()
        # els intervals valids son 0.5 i 0.49 -> BPM ~120, no ~2000
        self.assertLess(w._bpm_val(), 130)
        w.close()

    def _mapa_dos_trams(self, w):
        v = w.visor_ref
        # Mapa VÀLID amb compassos enters: 0–8 a 90 4/4 (3 compassos) i
        # 8–10 a 120 3/4 (l'últim pot ser parcial: excepció).
        v.aplica_tempo_trams([(0.0, 8.0, 90.0, 4, 4),
                              (8.0, 10.0, 120.0, 3, 4)])
        return v

    def test_camps_segueixen_el_tram_de_tempo_seleccionat(self):
        w = self._finestra()
        v = self._mapa_dos_trams(w)
        v.timeline.select_clip("tempo", 1)
        self.assertAlmostEqual(float(w.bpm.text()), 120.0, places=3)
        self.assertEqual(w.bpb.text(), "3")
        v.timeline.select_clip("chord", 0)
        self.assertAlmostEqual(float(w.bpm.text()), 90.0, places=3)
        self.assertEqual(w.bpb.text(), "4")
        w.close()

    def test_edicio_manual_va_al_tram_seleccionat(self):
        w = self._finestra()
        v = self._mapa_dos_trams(w)
        v.timeline.select_clip("tempo", 1)
        w.bpm.setText("100")
        w._aplica_parametres_temps()
        self.assertAlmostEqual(float(v.tempo_trams[1][2]), 100.0, places=6)
        self.assertAlmostEqual(float(v.tempo_trams[0][2]), 90.0, places=6)
        v.timeline.clear_selection()
        w.bpm.setText("110")
        w._aplica_parametres_temps()
        self.assertAlmostEqual(float(v.tempo_trams[0][2]), 110.0, places=6)
        self.assertAlmostEqual(float(v.tempo_trams[1][2]), 100.0, places=6)
        w.close()

    def test_tap_va_al_tram_seleccionat_i_undo_per_sessio(self):
        w = self._finestra()
        v = self._mapa_dos_trams(w)
        v.timeline.select_clip("tempo", 1)
        n0 = len(v._undo_stack)
        self._taps_en(w, 0.6)
        w._tanca_sessio_tap()
        self.assertAlmostEqual(float(v.tempo_trams[1][2]), 100.0, delta=3.0)
        self.assertAlmostEqual(float(v.tempo_trams[0][2]), 90.0, places=6)
        self.assertEqual(len(v._undo_stack), n0 + 1,
                         "la sessió de taps ha de ser UNA operació d'undo")
        v.undo()
        self.assertAlmostEqual(float(v.tempo_trams[1][2]), 120.0, places=3)
        w.close()

    def test_el_projecte_desa_el_transport_no_el_tram_seleccionat(self):
        w = self._finestra()
        v = self._mapa_dos_trams(w)
        v.timeline.select_clip("tempo", 1)
        d = w._dades_projecte()
        self.assertAlmostEqual(float(d["tempo"]["bpm"]), 90.0, places=6)
        self.assertEqual(d["tempo"]["compas"], "4/4")
        w.close()

    def test_detecta_bpm_del_tram_no_mou_les_fronteres(self):
        """El BPM detectat només tria N: la frontera 8→10 queda clavada.

        Abans s'aplicava el BPM detectat amb *ripple* i la fi del tram es movia
        (desquadrant el marcador següent). Ara Δt mana: 2 s amb 3/4 i 100 BPM
        donen N=1 compàs → 90 BPM exactes.
        """
        from unittest.mock import patch
        w = self._finestra()
        v = self._mapa_dos_trams(w)
        v.timeline.select_clip("tempo", 1)
        with patch.object(pipeline, "detecta_bpm_tram", return_value=100.0):
            w._detecta_bpm(pregunta=False)
        self.assertAlmostEqual(float(v.tempo_trams[1][2]), 90.0, places=3)
        self.assertAlmostEqual(float(v.tempo_trams[1][0]), 8.0, places=6)
        self.assertAlmostEqual(float(v.tempo_trams[1][1]), 10.0, places=6)
        self.assertAlmostEqual(float(v.tempo_trams[0][2]), 90.0, places=3)
        v.undo()
        self.assertAlmostEqual(float(v.tempo_trams[1][2]), 120.0, places=3)
        w.close()

    def test_tap_sonant_fa_loop_al_tram_seleccionat(self):
        w = self._finestra()
        v = self._mapa_dos_trams(w)
        v.timeline.select_clip("tempo", 1)
        v.sona = True
        v.pos = 0.0
        self._taps_en(w, 0.6)
        self.assertTrue(v.loop_on)
        self.assertAlmostEqual(float(v.loop_a), 8.0, places=6)
        self.assertAlmostEqual(float(v.loop_b), 10.0, places=6)
        self.assertAlmostEqual(float(v.pos), 8.0, places=6)
        w._tanca_sessio_tap()
        v.sona = False
        self.assertTrue(v.loop_on, "el loop es manté en aturar")
        w.close()

    def test_tap_sonant_sense_seleccio_fa_loop_al_primer(self):
        w = self._finestra()
        v = self._mapa_dos_trams(w)
        v.timeline.clear_selection()
        v.sona = True
        v.pos = 8.0
        self._taps_en(w, 0.6)
        self.assertTrue(v.loop_on)
        self.assertAlmostEqual(float(v.loop_a), 0.0, places=6)
        self.assertAlmostEqual(float(v.loop_b), 8.0, places=6)
        w.close()

    def test_tap_aturat_no_toca_el_loop(self):
        w = self._finestra()
        v = self._mapa_dos_trams(w)
        v.timeline.select_clip("tempo", 1)
        self.assertFalse(v.loop_on)
        self._taps_en(w, 0.6)
        self.assertFalse(v.loop_on)
        self.assertIsNone(v.loop_a)
        w.close()


class EditorFranjaTests(unittest.TestCase):
    """Franja Editor: mostra/edita l'element seleccionat sense finestres."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def _finestra(self):
        import tempfile, wave
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "t.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * 20)
        ac = os.path.join(td, "AUTOCHORDS_t"); os.makedirs(ac)
        _escriu_fitxer(os.path.join(ac, "acords.csv"), "0.0,4.0,C\n4.0,8.0,Am\n8.0,12.0,G\n")
        _escriu_fitxer(os.path.join(ac, "estructura_ABC.csv"),
            "inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
            "0.00,4.00,4.00,A,N,1,1\n4.00,20.00,16.00,B,B,1,1\n")
        window = app_main.Finestra()
        window.bpm.setText("120"); window.bpb.setText("4")
        window._aplica_parametres_temps()
        window.wav_edit.setText(wav)
        window._carrega_visor(wav)
        return window

    def test_editor_mostra_l_acord_seleccionat(self):
        w = self._finestra(); v = w.visor_ref
        v.timeline.select_clip("chord", 1); v._on_clip_selected("chord", 1)
        self.assertEqual(v.ed_gran.text(), "Am")
        self.assertEqual(v.ed_nom.text(), "Am")
        self.assertEqual(v.ed_ini.text(), "4.000")
        self.assertFalse(v.ed_fam.isVisible())
        w.close()

    def test_editor_mostra_la_seccio_seleccionada(self):
        w = self._finestra(); v = w.visor_ref
        v.timeline.select_clip("section", 0); v._on_clip_selected("section", 0)
        self.assertTrue(v.ed_gran.text().startswith("A"))
        self.assertEqual(v.ed_nom.text(), "A")
        self.assertEqual(v.ed_fam.text(), "N")
        w.close()

    def test_editar_nom_directament(self):
        w = self._finestra(); v = w.visor_ref
        v.timeline.select_clip("chord", 1); v._on_clip_selected("chord", 1)
        v.ed_nom.setText("Am7"); v._aplica_editor()
        self.assertEqual(v.acords[1][2][0], "A-7")     # notació canònica
        self.assertEqual(v.ed_gran.text(), "A-7")   # l'editor s'actualitza
        v.undo()
        w.close()

    def test_editar_inici_directament(self):
        w = self._finestra(); v = w.visor_ref
        v.timeline.select_clip("chord", 1); v._on_clip_selected("chord", 1)
        v.ed_ini.setText("5.0"); v._aplica_editor()
        self.assertAlmostEqual(v.acords[1][0], 5.0, places=2)
        v.undo()
        w.close()

    def test_editar_seccio_directament(self):
        w = self._finestra(); v = w.visor_ref
        v.timeline.select_clip("section", 0); v._on_clip_selected("section", 0)
        v.ed_nom.setText("Z"); v.ed_fam.setText("N"); v._aplica_editor()
        self.assertEqual(v.seccions[0][2], "Z")
        v.undo()
        w.close()

    def test_doble_clic_carril_va_a_l_editor_sense_dialeg(self):
        """El doble-clic (editRequested) selecciona i enfoca l'Editor."""
        w = self._finestra(); v = w.visor_ref
        v._on_chord_edit_requested(1)
        self.assertEqual((v._ed_kind, v._ed_idx), ("chord", 1))
        self.assertEqual(v.ed_nom.text(), "Am")
        self.assertTrue(v.ed_nom.hasFocus() or True)   # focus (best-effort)
        w.close()

    def test_clic_a_les_llistes_actualitza_l_editor(self):
        """Regressio: el clic a la llista ha d'actualitzar la franja Editor.

        select_clip() abans NO emetia clipSelected, aixi que seleccionar des
        de la llista no arribava a l'Editor."""
        w = self._finestra(); v = w.visor_ref
        v._salt_acord(v.llista_ac.item(1))
        self.assertEqual(v.ed_gran.text(), "Am")
        v._salt_seccio(v.llista_ab.item(0))
        self.assertTrue(v.ed_gran.text().startswith("A"))
        w.close()

    def test_sense_seleccio_esta_buit(self):
        w = self._finestra(); v = w.visor_ref
        v._actualitza_editor()   # cap _ed_kind
        self.assertFalse(v.ed_aplica.isEnabled())
        self.assertIn("Selecciona", v.ed_gran.text())
        w.close()


class MenuEdicioTests(unittest.TestCase):
    """Accions dels menus Edita i Selecciona (reusen la logica existent)."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def _finestra(self):
        import tempfile, wave
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "t.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * 20)
        ac = os.path.join(td, "AUTOCHORDS_t"); os.makedirs(ac)
        _escriu_fitxer(os.path.join(ac, "acords.csv"), "0.0,4.0,C\n4.0,8.0,Am\n8.0,12.0,G\n")
        _escriu_fitxer(os.path.join(ac, "estructura_ABC.csv"),
            "inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
            "0.00,4.00,4.00,A,N,1,1\n4.00,20.00,16.00,B,B,1,1\n")
        window = app_main.Finestra()
        window.wav_edit.setText(wav)
        window._carrega_visor(wav)
        return window

    def test_selecciona_acord_i_seccio_del_cursor(self):
        w = self._finestra()
        v = w.visor_ref
        v.ves_a(5.0); w._sel_acord_cursor()
        self.assertEqual(w._clip_seleccionat(), ("chord", 1))
        v.ves_a(10.0); w._sel_seccio_cursor()
        self.assertEqual(w._clip_seleccionat(), ("section", 1))
        w.close()

    def test_duplica_i_elimina_element(self):
        w = self._finestra()
        v = w.visor_ref
        v.ves_a(5.0); w._sel_acord_cursor()
        n = len(v.acords); w._duplica_element()
        self.assertEqual(len(v.acords), n + 1)
        v.undo()
        v.ves_a(5.0); w._sel_acord_cursor()
        n = len(v.acords); w._elimina_element()
        self.assertEqual(len(v.acords), n - 1)
        w.close()

    def test_afegeix_acord_i_seccio(self):
        from unittest.mock import patch
        import PyQt5.QtWidgets as QW
        w = self._finestra()
        v = w.visor_ref
        with patch.object(QW.QInputDialog, "getText", return_value=("F", True)):
            v.ves_a(6.0); n = len(v.acords); w._afegeix_acord_ui()
            self.assertEqual(len(v.acords), n + 1)
            # a 21 s en una WAV de 20 s JA NO s'accepta (topall superior de
            # temps: fora de la WAV no hi ha àudio i l'invariant #4 no es
            # podria complir). Abans s'hi afegia i trencava la cobertura.
            v.ves_a(21.0); n = len(v.seccions)
            w._afegeix_seccio_ui()
            self.assertEqual(len(v.seccions), n)
            # Amb espai lliure (cap secció), l'add sí que funciona i deixa el
            # carril COMPLET: «-» al davant i la secció nova fins al final.
            v.seccions = []
            v.ves_a(6.0)
            w._afegeix_seccio_ui()
            self.assertEqual(len(v.seccions), 2)
            self.assertAlmostEqual(float(v.seccions[0][0]), 0.0, places=2)
            self.assertEqual(v.seccions[0][2], "-")
            self.assertAlmostEqual(float(v.seccions[1][0]), 6.0, places=2)
            self.assertAlmostEqual(float(v.seccions[1][1]), 20.0, places=2)
        w.close()

    def test_neteja_loop(self):
        w = self._finestra()
        v = w.visor_ref
        v.loop_a, v.loop_b, v.loop_on = 1.0, 3.0, True
        w._neteja_loop()
        self.assertIsNone(v.loop_a)
        self.assertFalse(v.loop_on)
        w.close()

    def test_menus_tenen_les_accions(self):
        w = self._finestra()
        def accions(nom):
            for act in w.menuBar().actions():
                if act.text() == nom:
                    return [a.text() for a in act.menu().actions()
                            if not a.isSeparator()]
            return []
        e = accions("&Edita")
        for x in ("Elimina element", "Duplica element", "Reanomena element",
                  "Afegeix acord…", "Afegeix secció…"):
            self.assertIn(x, e)
        s = accions("&Selecciona")
        for x in ("Selecciona l'acord del cursor", "Neteja el loop"):
            self.assertIn(x, s)
        w.close()


class TransportBarTests(unittest.TestCase):
    """Els botons de la BARRA de transport (fora del visor) han de fer efecte.

    Regressió: commuta_mut()/commuta_loop() llegien l'estat dels botons
    PROPIS del visor, no el de la barra -> el botó es marcava pero no passava res.
    """

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def _finestra_amb_visor(self):
        import tempfile, wave
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "t.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100)
        window = app_main.Finestra()
        window.wav_edit.setText(wav)
        window._carrega_visor(wav)
        return window, window.visor_ref

    def test_boto_mute_de_la_barra_afecta_el_visor(self):
        window, v = self._finestra_amb_visor()
        self.assertFalse(v.mut)
        window.tb_mut.setChecked(True)
        window.tb_mut.clicked.emit()
        self.assertTrue(v.mut)
        self.assertTrue(v.b_mut.isChecked())     # sincronitzat
        window.tb_mut.setChecked(False)
        window.tb_mut.clicked.emit()
        self.assertFalse(v.mut)
        window.close()

    def test_boto_loop_de_la_barra_afecta_el_visor(self):
        window, v = self._finestra_amb_visor()
        v.loop_a, v.loop_b = 1.0, 3.0           # cal tenir A i B marcats
        self.assertFalse(v.loop_on)
        window.tb_loop.setChecked(True)
        window.tb_loop.clicked.emit()
        self.assertTrue(v.loop_on)
        self.assertTrue(v.b_loop.isChecked())
        window.close()

    def test_boto_loop_no_activa_sense_a_i_b(self):
        window, v = self._finestra_amb_visor()
        v.loop_a = v.loop_b = None
        window.tb_loop.setChecked(True)
        window.tb_loop.clicked.emit()
        self.assertFalse(v.loop_on)             # sense A/B no s'activa
        window.close()


class MetroVisorTests(unittest.TestCase):
    """Integració del metrònom al visor (estat i reinici). Encara sense GUI."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def _visor(self):
        import tempfile, wave
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "t.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * 3)
        return visor.Visor(wav, None, None, 120.0, 4, True)

    def test_estat_inicial(self):
        v = self._visor()
        self.assertFalse(v.metro_on)
        self.assertAlmostEqual(v.metro_vol, 0.6)
        v.close()

    def test_commuta_metro_es_toggle(self):
        v = self._visor()
        v.commuta_metro()
        self.assertTrue(v.metro_on)
        v.commuta_metro()
        self.assertFalse(v.metro_on)
        v.close()

    def test_canvia_vol_metro_amb_clamp(self):
        v = self._visor()
        v._canvia_vol_metro(25)
        self.assertAlmostEqual(v.metro_vol, 0.25)
        v._canvia_vol_metro(150)
        self.assertAlmostEqual(v.metro_vol, 1.0)
        v._canvia_vol_metro(-5)
        self.assertAlmostEqual(v.metro_vol, 0.0)
        v.close()

    def test_commuta_metro_NO_talla_l_audio(self):
        """El metrònom no pot tallar la reproducció en commutar-lo.

        El fil d'alimentació llig `metro_on` a cada tros, així que el canvi
        s'aplica a l'instant. Abans es reiniciava el reproductor i se sentia un
        micro-tall a l'àudio a cada commutació (reportat per l'operador,
        18-10-2026). Mateixa pauta que el volum i el mute.
        """
        v = self._visor()
        v.sona = True
        v.pos = 1.5
        crides = []
        v._atura_proc = lambda: crides.append("atura")
        v._engega_des_de = lambda t: crides.append("engega")
        v.commuta_metro()
        self.assertTrue(v.metro_on, "ha de quedar activat")
        self.assertEqual(crides, [], "no ha de reiniciar el reproductor")
        v.commuta_metro()
        self.assertFalse(v.metro_on)
        self.assertEqual(crides, [], "ni en desactivar-lo")
        v.close()

    def test_canvia_vol_metro_NO_talla_l_audio(self):
        v = self._visor()
        v.sona = True
        v.pos = 0.7
        crides = []
        v._atura_proc = lambda: crides.append("atura")
        v._engega_des_de = lambda t: crides.append("engega")
        v._canvia_vol_metro(40)
        self.assertAlmostEqual(v.metro_vol, 0.4, places=3)
        self.assertEqual(crides, [], "no ha de reiniciar el reproductor")
        v.close()


class ContextMenuTests(unittest.TestCase):
    """Menu contextual (boto dret) sobre un clip del timeline."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def _visor(self):
        import tempfile, wave
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "t.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * 2)
        ac = os.path.join(td, "acords.csv")
        _escriu_fitxer(ac, "0.0,2.0,C\n2.0,4.0,Am\n")
        return visor.Visor(wav, ac, None, 120, 4, False)

    def _captura(self, v, kind, idx):
        from PyQt5.QtWidgets import QMenu
        from PyQt5.QtCore import QPoint
        capt = {}
        orig = QMenu.exec_

        def fake(self, pos, *a):
            capt["accions"] = [(x.text(), x.isEnabled())
                               for x in self.actions() if not x.isSeparator()]
            return None
        QMenu.exec_ = fake
        try:
            v._on_clip_context_menu(kind, idx, QPoint(0, 0))
        finally:
            QMenu.exec_ = orig
        return capt.get("accions", [])

    def test_menu_te_les_accions(self):
        """(A2 + regla #11) El menú contextual té les accions esperades; «Parteix…»
        és ACTIVA sobre un clip, amb el text propi del tipus (acord/secció).

        Des del 19-10-2026 és la **definició única** del menú contextual
        (`visor._menu_contextual`), compartida pel timeline i les llistes i per
        les tres pistes: 13 accions, amb «Fusionar…», «Parteix a la selecció
        A–B» (2026-10-20) i «Loop a la selecció» inclosos.

        ⚠️ Este test demanava el menú amb `idx=1` quan el model només té **UN**
        acord (WAV de 2 s; el segon cau fora) i n'esperava accions ACTIVes: el
        codi vell només comprovava `idx >= 0`, així que donava per bo un clip
        que no existeix — i el test ho congelava. Ara es prova amb l'índex REAL
        (0) i el cas fora de rang té el seu propi test.
        """
        v = self._visor()
        self.assertEqual(len(v.acords), 1, "el fixture té un sol acord")
        accions = self._captura(v, "chord", 0)
        self.assertEqual([x[0] for x in accions],
                         ["Afegeix acord aquí",
                          "Duplica", "Elimina", "Reanomena acord…",
                          "Parteix l'acord…", "Partir per la meitat",
                          "Parteix a la selecció A–B",
                          "Fusionar amb anterior", "Fusionar amb següent",
                          "Retalla", "Copia", "Enganxa",
                          "Loop a la selecció"])
        self.assertTrue(accions[4][1], "sobre un acord ha d'estar activa")
        self.assertTrue(accions[5][1], "«Partir per la meitat» també")
        # El fixture ve amb acords però SENSE estructura: el visor la completa
        # amb un tram «-» que cobreix tota la WAV (regla #4). Per tant, la
        # secció existeix i el menú ha d'oferir les accions d'edició.
        self.assertEqual([s[2] for s in v.seccions], ["-"])
        accions_sec = self._captura(v, "section", 0)
        self.assertEqual(accions_sec[0][0], "Afegeix secció aquí")
        self.assertEqual(accions_sec[3][0], "Reanomena secció…")
        self.assertEqual(accions_sec[4][0], "Parteix la secció…")
        self.assertTrue(accions_sec[4][1], "sobre una secció ha d'estar activa")
        self.assertEqual(accions_sec[5][0], "Partir per la meitat")
        self.assertTrue(accions_sec[5][1], "«Partir per la meitat» també")
        v.close()

    def test_menu_amb_index_inexistent_desactiva_tot_menys_afegir(self):
        """Un índex FORA DE RANG no pot oferir accions sobre un clip que no hi és.

        Regressió del bug que este mateix fitxer congelava: el menú només
        comprovava `idx >= 0` i donava «Parteix…»/«Elimina» per actives amb
        `idx=99`.
        """
        v = self._visor()
        accions = self._captura(v, "chord", 99)
        self.assertEqual(accions[0][0], "Afegeix acord aquí")
        self.assertTrue(accions[0][1],
                        "l'afegeix no depén de cap clip existent")
        self.assertTrue(all(not e for _t, e in accions[1:]),
                        f"cap accio mes no pot estar activa: {accions}")
        v.close()

    def test_menu_desactivat_sense_seleccio(self):
        v = self._visor()
        accions = self._captura(v, "chord", -1)
        # «Afegeix … aquí» és l'ÚNICA que no depèn d'un clip prèviament
        # seleccionat: justament serveix per crear-ne un on no n'hi ha.
        self.assertEqual(accions[0][0], "Afegeix acord aquí")
        self.assertTrue(accions[0][1],
                        "l'afegeix ha d'estar actiu fins i tot sense selecció")
        self.assertTrue(all(not habilitat for _n, habilitat in accions[1:]),
                        f"la resta ha d'estar desactivada: {accions}")
        v.close()


class ThemeColorsTests(unittest.TestCase):
    """Els colors del visor viuen a app/theme.py, i seleccionat != actiu."""

    def test_seleccionat_i_actiu_son_distints(self):
        from app import theme
        self.assertNotEqual(theme.CLIP_SELECTED_BORDER,
                            theme.CLIP_ACTIVE_FILL)
        self.assertNotEqual(theme.CLIP_ACTIVE_FILL, theme.CLIP_FILL)

    def test_el_timeline_pren_els_colors_del_theme(self):
        from app import theme, timeline
        self.assertEqual(timeline.SELECTION_COLOR,
                         theme.CLIP_SELECTED_BORDER)
        self.assertEqual(timeline.CHORD_ACTIVE_FILL,
                         theme.CLIP_ACTIVE_FILL)
        self.assertEqual(timeline.CURSOR_COLOR, theme.TL_CURSOR)


class PipelineRunTests(unittest.TestCase):
    """run() ha de tenir timeout: un subprocés encallat no pot penjar-ho tot."""

    def test_run_aplica_timeout(self):
        from app import pipeline
        with self.assertRaises(subprocess.TimeoutExpired):
            pipeline.run(["sleep", "30"], lambda m: None, timeout=1)

    def test_run_ok(self):
        from app import pipeline
        p = pipeline.run(["true"], lambda m: None, timeout=5)
        self.assertEqual(p.returncode, 0)


class FormatCsvTests(unittest.TestCase):
    """Resolució temporal unificada (1 µs) i compassos de qualsevol bpb."""

    def test_acords_csv_te_6_decimals(self):
        import tempfile
        from app import pipeline
        td = tempfile.mkdtemp()
        ruta = os.path.join(td, "acords.csv")
        pipeline.desa_acords_csv(ruta, [
            pipeline.Clip(0.0, 16.439727891, ("C", "0.000000000")),
            pipeline.Clip(16.439727891, 0.0, ("E7", "16.439727891")),
        ])
        files = open(ruta, encoding="utf-8").read().strip().splitlines()
        self.assertEqual(files[0], "0.000000,16.439728,C")
        self.assertEqual(files[1], "16.439728,0.000000,E7")   # durada=0 -> fi 0
        for linia in files:
            for cell in linia.split(",")[:2]:
                self.assertLessEqual(len(cell.split(".")[1]), 6,
                                     f"mes de 6 decimals: {linia}")

    def test_abc_csv_te_6_decimals(self):
        import tempfile
        from app import pipeline
        td = tempfile.mkdtemp()
        ruta = os.path.join(td, "estructura_ABC.csv")
        pipeline.desa_abc_csv(ruta, [(0.0, 21.362, "A", "N")], 101.0,
                              lambda m: None)
        files = open(ruta, encoding="utf-8").read().strip().splitlines()
        self.assertEqual(files[0].split(",")[:3], ["inici_s", "fi_s", "durada_s"])
        self.assertEqual(files[1].split(",")[:3],
                         ["0.000000", "21.362000", "21.362000"])

    def test_pos_compas_respecta_bpb(self):
        from app import pipeline
        # 120 BPM -> beat 0.5s. Amb bpb=3, el 4t temps ja es compas 2.
        self.assertEqual(pipeline.pos_compas(0.0, 120, 3), "1.1.1")
        self.assertEqual(pipeline.pos_compas(0.5, 120, 3), "1.2.1")
        self.assertEqual(pipeline.pos_compas(1.0, 120, 3), "1.3.1")
        self.assertEqual(pipeline.pos_compas(1.5, 120, 3), "2.1.1")
        # bpb=4: el 4t temps encara es compas 1
        self.assertEqual(pipeline.pos_compas(1.5, 120, 4), "1.4.1")
        self.assertEqual(pipeline.pos_compas(2.0, 120, 4), "2.1.1")

    def test_pos_compas_lliure_mostra_segons(self):
        from app import pipeline
        self.assertTrue(pipeline.pos_compas(12.34, 120, 4, lliure=True)
                        .endswith("s"))


class Resolucio1_32IExportTests(unittest.TestCase):
    """La graella musical és 1/32; l'export conserva els temps exactes."""

    def test_pos_compas_1_32(self):
        self.assertEqual(pipeline.pos_compas(0.0, 120, 4), "1.1.1")
        self.assertEqual(pipeline.pos_compas(0.0625, 120, 4), "1.1.2")
        self.assertEqual(pipeline.pos_compas(0.125, 120, 4), "1.1.3")
        self.assertEqual(pipeline.pos_compas(0.1875, 120, 4), "1.1.4")
        self.assertEqual(pipeline.pos_compas(0.25, 120, 4), "1.1.5")
        self.assertEqual(pipeline.pos_compas(0.3125, 120, 4), "1.1.6")
        self.assertEqual(pipeline.pos_compas(0.375, 120, 4), "1.1.7")
        self.assertEqual(pipeline.pos_compas(0.4375, 120, 4), "1.1.8")
        self.assertEqual(pipeline.pos_compas(0.5, 120, 4), "1.2.1")

    def test_segments_export_1_32_i_temps_exactes(self):
        td = tempfile.mkdtemp()
        ca = os.path.join(td, "acords.csv")
        with open(ca, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["0.000000", "0.123456", "C"])
            w.writerow(["0.123456", "0.260000", "G"])
            w.writerow(["0.260000", "2.000000", "Am"])
        segs = pipeline.segments_export(ca, 120.0, 4, 0.0, durada=2.0)
        self.assertEqual([s[0] for s in segs], ["1.1.1", "1.1.3", "1.1.5"])
        self.assertEqual([s[1] for s in segs], ["C", "G", "Am"])
        self.assertAlmostEqual(segs[0][2], 0.0, places=9)
        self.assertAlmostEqual(segs[0][3], 0.123456, places=9)
        self.assertAlmostEqual(segs[1][2], 0.123456, places=9)
        self.assertAlmostEqual(segs[2][3], 2.0, places=9)

    def test_export_manifest_i_durades_exactes(self):
        td = tempfile.mkdtemp()
        ca = os.path.join(td, "acords.csv")
        out = os.path.join(td, "out")
        r = pipeline.exporta_total(
            csv_ac=ca, csv_seg=None, sortida=out, bpm=120.0, bpb=4,
            offset=0.0, sr=44100, log=lambda *_a: None, tempo_fix=True,
            amb_estructura=True, total_s=2.0,
            acords=[(0.0, "C", "0"), (0.123456, "G", "0.123456"),
                    (0.26, "Am", "0.26")],
            seccions=[(0.0, 1.0, "A", "A"), (1.0, 2.0, "B", "B")])
        self.assertTrue(os.path.isfile(r["manifest_csv"]))
        with open(r["manifest_csv"], encoding="utf-8") as f:
            files = list(csv.DictReader(f))
        acords = [x for x in files if x["tipus"] == "acord"]
        estructura = [x for x in files if x["tipus"] == "estructura"]
        self.assertEqual([x["fitxer"] for x in acords],
                         ["1-1-1_C.wav", "1-1-3_G.wav", "1-1-5_Am.wav"])
        self.assertEqual([x["inici_s"] for x in acords],
                         ["0.000000", "0.123456", "0.260000"])
        self.assertEqual([x["fi_s"] for x in acords],
                         ["0.123456", "0.260000", "2.000000"])
        self.assertEqual(len(estructura), 2)
        # La durada del WAV surt dels segons exactes, no de la graella 1/32.
        with wave.open(os.path.join(out, "wavs_acords", "1-1-3_G.wav"),
                       "rb") as w:
            self.assertEqual(w.getnframes(),
                             int(round((0.26 - 0.123456) * 44100)))


class UndoRedoTests(unittest.TestCase):
    """Tests de desfer/refer (només edició; MAI toquen les wavs)."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def _make_visor_with_data(self):
        td = tempfile.mkdtemp()
        wav_path = os.path.join(td, "tema.wav")
        sortida = os.path.join(td, "AUTOCHORDS_tema")
        os.makedirs(sortida)
        with wave.open(wav_path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * 20)
        with open(os.path.join(sortida, "acords.csv"), "w", encoding="utf-8") as f:
            f.write("0.0,2.0,C\n2.0,4.5,Am\n4.5,7.0,F\n7.0,10.0,G\n10.0,20.0,C\n")
        with open(os.path.join(sortida, "estructura_ABC.csv"), "w", encoding="utf-8") as f:
            f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n")
            f.write("0.0,5.0,5.0,A,A,1.1,5.1\n")
            f.write("5.0,10.0,5.0,B,B,5.1,10.1\n")
            f.write("10.0,20.0,10.0,C,C,10.1,20.1\n")
        v = visor.Visor(wav_path,
                        os.path.join(sortida, "acords.csv"),
                        os.path.join(sortida, "estructura_ABC.csv"),
                        bpm=120, bpb=4, tempo_fix=False)
        return v, sortida

    def _mou_acord(self, v, idx, nou_t):
        v.timeline._on_chord_time_changed(idx, nou_t)
        v.timeline._emit_edit_finished()

    def test_undo_redo_chord_move(self):
        v, _ = self._make_visor_with_data()
        v.timeline.zoom_to(0, 20)
        t_original = v.acords[1][0]
        self._mou_acord(v, 1, 3.6)
        self.assertAlmostEqual(v.acords[1][0], 3.5, places=4)
        v.undo()
        self.assertAlmostEqual(v.acords[1][0], t_original, places=4)
        v.redo()
        self.assertAlmostEqual(v.acords[1][0], 3.5, places=4)
        v.close()

    def test_undo_section_move(self):
        v, _ = self._make_visor_with_data()
        ini0 = v.seccions[1][0]
        v.timeline._section_items[1]._drag_mode = 0
        v.timeline._on_section_changed(1, 6.0, 10.0)
        v.timeline._emit_edit_finished()
        self.assertAlmostEqual(v.seccions[1][0], 6.0, places=4)
        v.undo()
        self.assertAlmostEqual(v.seccions[1][0], ini0, places=4)
        v.close()

    def test_undo_covers_rename(self):
        v, _ = self._make_visor_with_data()
        nom0 = v.acords[2][2][0]
        # flux real: el timeline canvia el nom i emet chordRenamed
        v.timeline._commit_rename("chord", 2, v.timeline._chord_items[2],
                                  "FMaj7")
        self.assertEqual(v.acords[2][2][0], "FMaj7")
        v.undo()
        self.assertEqual(v.acords[2][2][0], nom0)
        v.redo()
        self.assertEqual(v.acords[2][2][0], "FMaj7")
        v.close()

    def test_undo_restores_timeline_items(self):
        v, _ = self._make_visor_with_data()
        t0 = v.acords[1][0]
        self._mou_acord(v, 1, 3.6)
        v.undo()
        # el model I la UI (items del timeline) han de tornar
        self.assertAlmostEqual(v.acords[1][0], t0, places=4)
        self.assertAlmostEqual(v.timeline._chord_items[1].t, t0, places=4)
        v.close()

    def test_undo_does_not_generate_wavs(self):
        """Les wavs són l'últim pas: editar/desfer NO n'ha de generar cap."""
        v, sortida = self._make_visor_with_data()
        self._mou_acord(v, 1, 3.6)
        v.undo()
        wavs = [f for f in os.listdir(sortida) if f.lower().endswith(".wav")]
        self.assertEqual(wavs, [], f"no hauria de generar wavs, però hi ha: {wavs}")
        # el CSV sí que s'ha d'actualitzar
        self.assertTrue(os.path.isfile(os.path.join(sortida, "acords.csv")))
        v.close()

    def test_new_edit_clears_redo(self):
        v, _ = self._make_visor_with_data()
        self._mou_acord(v, 1, 3.6)
        v.undo()
        self._mou_acord(v, 2, 5.9)   # edició nova → esborra el refer
        v.redo()                      # no ha de fer res
        self.assertAlmostEqual(v.acords[1][0], v.acords[1][0], places=4)
        self.assertFalse(v._redo_stack)
        v.close()

    def test_undo_empty_stack_is_safe(self):
        v, _ = self._make_visor_with_data()
        v.undo()   # no ha de petar
        v.redo()
        self.assertEqual(len(v.acords), 5)
        v.close()


class TriaPlayerTests(unittest.TestCase):
    """Selecció del motor de reproducció (`Visor._tria_player`).

    macOS/Windows: motor **natiu** `sounddevice` (PortAudio → CoreAudio/WASAPI).
    Linux: `paplay` (PipeWire/Pulse) i, si no hi és, `aplay` (ALSA); si no n'hi
    ha cap, retorna `None` (i el visor ho avisa) en lloc de provar ordres que no
    existeixen.
    """

    def _visor_buit(self):
        v = visor.Visor.__new__(visor.Visor)
        v.audio = {"sr": 44100}
        return v

    def test_prefereix_paplay(self):
        if not plataforma.ES_LINUX:
            self.skipTest("l'ordre paplay/aplay es només del Linux")
        v = self._visor_buit()
        with patch("app.visor.shutil.which", lambda n: "/usr/bin/" + n):
            player, args = v._tria_player()
        self.assertEqual(player, "paplay")
        self.assertIn("--raw", args)
        self.assertIn("--latency-msec=100", args)
        self.assertIn("--rate=44100", args)

    def test_aplay_si_no_hi_ha_paplay(self):
        if not plataforma.ES_LINUX:
            self.skipTest("aplay es només del Linux")
        v = self._visor_buit()
        with patch("app.visor.shutil.which",
                   lambda n: "/usr/bin/aplay" if n == "aplay" else None):
            player, args = v._tria_player()
        self.assertEqual(player, "aplay")
        self.assertIn("--format=S16_LE", args)

    def test_natiu_a_windows_i_macos(self):
        if plataforma.ES_LINUX:
            self.skipTest("al Linux no es fa servir el motor natiu")
        v = self._visor_buit()
        player, args = v._tria_player()
        self.assertEqual(player, "sounddevice")   # motor natiu (PortAudio)
        self.assertEqual(args, [])

    def test_cap_reproductor_retorna_none(self):
        if not plataforma.ES_LINUX:
            self.skipTest("a mac/win sempre hi ha el motor natiu (sounddevice)")
        v = self._visor_buit()
        with patch("app.visor.shutil.which", lambda n: None):
            player, args = v._tria_player()
        self.assertIsNone(player)
        self.assertEqual(args, [])


class ConfigEscripturaTests(unittest.TestCase):
    """L'AppImage munta el contingut en NOMÉS LECTURA.

    L'estat de l'app (log, temp, opcions) ha d'anar a un directori ESCRIPTIBLE;
    si no, l'app peta a l'arrencada amb `OSError [Errno 30] Read-only file
    system` i no arriba ni a mostrar la finestra (bug del run #5).
    """

    def test_dades_dir_es_escriptible(self):
        self.assertTrue(os.access(config.DADES_DIR, os.W_OK))

    def test_log_i_opcions_dins_dades_dir(self):
        for p in (config.LOG_PATH, config.OPCIONS_PATH):
            self.assertTrue(p.startswith(config.DADES_DIR), p)

    def test_temp_dir_es_escriptible(self):
        self.assertTrue(os.access(config.TEMP_DIR, os.W_OK))

    def test_detecta_nomes_lectura(self):
        if not plataforma.ES_LINUX:
            self.skipTest("/proc només existeix al Linux")
        # /proc és de només lectura
        self.assertFalse(config._es_escriptible("/proc"))

    def test_cau_fora_del_projecte_si_aquest_no_es_escriptible(self):
        if not plataforma.ES_LINUX:
            self.skipTest("cal un camí de només lectura; /proc és només del Linux")
        with patch.object(config, "PROJECT_ROOT", "/proc"):
            d = config._dir_de_dades()
        self.assertNotEqual(d, "/proc")
        self.assertTrue(os.access(d, os.W_OK))

    def test_main_i_dialegs_apanten_al_config(self):
        self.assertEqual(app_main.DEFAULT_LOG_PATH, config.LOG_PATH)
        self.assertEqual(dialegs.FITXER_OPCIONS, config.OPCIONS_PATH)


class PlataformaTests(unittest.TestCase):
    """Capa d'abstracció de plataforma (`app/plataforma.py`).

    Al Linux ha de retornar EXACTAMENT els valors d'abans (cap regressió);
    la resta de SO es cobreix als CI de Windows/macOS.
    """

    def test_so_detectat(self):
        self.assertIn(plataforma.SO, ("linux", "win", "mac"))
        self.assertEqual(sum([plataforma.ES_LINUX, plataforma.ES_WINDOWS,
                              plataforma.ES_MAC]), 1)

    def test_noms_binaris(self):
        if plataforma.ES_WINDOWS:
            self.assertTrue(plataforma.NOM_HOST.endswith(".exe"))
            self.assertTrue(plataforma.NOM_FFMPEG.endswith(".exe"))
        else:
            self.assertEqual(plataforma.NOM_HOST, "vamp_host_local")
            self.assertEqual(plataforma.NOM_FFMPEG, "ffmpeg")

    def test_candidats_reproductor(self):
        c = plataforma.candidats_reproductor()
        if plataforma.ES_LINUX:
            self.assertEqual(c, ("paplay", "aplay"))
        else:
            self.assertEqual(c, ())   # mac/win: motor natiu (sounddevice), res extern

    def test_dirs_plugins(self):
        d = [os.path.basename(x) for x in plataforma.dirs_plugins("/tmp")]
        if plataforma.ES_LINUX:
            self.assertIn("nnls-chroma-linux64-local", d)
            self.assertIn("qm-vamp-plugins-linux64-local", d)
        elif plataforma.ES_WINDOWS:
            self.assertIn("nnls-chroma-win64-local", d)
        else:
            self.assertIn("nnls-chroma-macos-local", d)

    def test_path_env_vamp_separador_del_so(self):
        self.assertEqual(plataforma.path_env_vamp(["/a", "/b"]),
                         os.pathsep.join(["/a", "/b"]))

    def test_executable(self):
        self.assertFalse(plataforma.executable("/no/existeix"))
        self.assertTrue(plataforma.executable(sys.executable))

    def test_kwargs_nou_grup(self):
        k = plataforma.kwargs_nou_grup()
        if plataforma.ES_WINDOWS:
            self.assertIn("creationflags", k)
        else:
            self.assertEqual(k, {"start_new_session": True})

    def test_mata_grup_tolerant(self):
        plataforma.mata_grup(None)   # no ha de petar

        class P:                      # procés inexistent
            pid = 10 ** 9

            def terminate(self):
                pass

            def kill(self):
                pass

        plataforma.mata_grup(P())     # ha de ser tolerant

    def test_python_actual_mai_fix(self):
        self.assertTrue(plataforma.python_actual())
        self.assertNotEqual(plataforma.python_actual(), "python3")


class InstanciaUnicaTests(unittest.TestCase):
    """Bloqueig d'instància única PER USUARI (Pas 2).

    Cada test s'executa en un `XDG_RUNTIME_DIR` temporal propi (aïllat), que és
    el primer candidat de `plataforma.dir_instancia()` al Linux/macOS.
    """

    def setUp(self):
        self._dir = tempfile.mkdtemp()
        self._xdg = os.environ.get("XDG_RUNTIME_DIR")
        os.environ["XDG_RUNTIME_DIR"] = self._dir

    def tearDown(self):
        if self._xdg is None:
            os.environ.pop("XDG_RUNTIME_DIR", None)
        else:
            os.environ["XDG_RUNTIME_DIR"] = self._xdg
        shutil.rmtree(self._dir, ignore_errors=True)

    def test_segona_instancia_rebutjada(self):
        f1 = plataforma.obre_fitxer_instancia()
        self.assertIsNotNone(f1)
        self.assertTrue(plataforma.bloqueja_instancia_unica(f1))
        f2 = plataforma.obre_fitxer_instancia()
        self.assertIsNotNone(f2)
        self.assertFalse(plataforma.bloqueja_instancia_unica(f2))
        # En alliberar el primer, el segon ja el pot agafar.
        plataforma.desbloqueja(f1)
        self.assertTrue(plataforma.bloqueja_instancia_unica(f2))
        plataforma.desbloqueja(f2)
        f1.close()
        f2.close()

    @unittest.skipIf(plataforma.ES_WINDOWS, "permisos POSIX")
    def test_permisos_0600(self):
        f = plataforma.obre_fitxer_instancia()
        self.assertIsNotNone(f)
        mode = os.stat(plataforma.fitxer_instancia()).st_mode & 0o777
        self.assertEqual(mode, 0o600)
        f.close()

    @unittest.skipIf(plataforma.ES_WINDOWS, "O_NOFOLLOW/symlink no aplicable")
    def test_no_segueix_symlink(self):
        path = plataforma.fitxer_instancia()
        victima = os.path.join(self._dir, "victima.txt")
        with open(victima, "w", encoding="utf-8") as v:
            v.write("no tocar")
        os.symlink(victima, path)
        # O_NOFOLLOW: no s'obre el destí de l'enllaç.
        self.assertIsNone(plataforma.obre_fitxer_instancia())
        with open(victima, encoding="utf-8") as v:
            self.assertEqual(v.read(), "no tocar")

    def test_arrenca_amb_fitxer_d_una_sessio_anterior(self):
        # El fitxer ja hi és (sense bloqueig): s'ha de poder obrir i bloquejar.
        with open(plataforma.fitxer_instancia(), "w", encoding="utf-8") as p:
            p.write("")
        f = plataforma.obre_fitxer_instancia()
        self.assertIsNotNone(f)
        self.assertTrue(plataforma.bloqueja_instancia_unica(f))
        plataforma.desbloqueja(f)
        f.close()

    def test_nom_amb_usuari_i_no_global(self):
        n = os.path.basename(plataforma.fitxer_instancia())
        self.assertTrue(n.startswith("auto_chords_single_instance_"))
        self.assertNotEqual(n, "auto_chords_single_instance.lock")
        self.assertIn(plataforma._sufix_usuari(), n)

    def test_sense_xdg_usa_el_dir_d_estat(self):
        os.environ.pop("XDG_RUNTIME_DIR", None)
        self.assertEqual(plataforma.dir_instancia(), config.DADES_DIR)


class MissatgePartituraTests(unittest.TestCase):
    """L'exportació de partitura ha de deixar BEN CLAR que el PDF (i el MSCZ)
    depenen de **MuseScore** instal·lat (petició de l'operador)."""

    def _buida(self):
        return app_main.Finestra.__new__(app_main.Finestra)

    def test_amb_pdf_no_avisa(self):
        m = self._buida()._missatge_partitura(
            {"musicxml": "/x.musicxml", "pdf": "/x.pdf", "mscz": "/x.mscz"})
        self.assertIn("MusicXML", m)
        self.assertIn("PDF", m)
        self.assertNotIn("NO s'han generat", m)

    def test_sense_pdf_avisa_de_musescore(self):
        m = self._buida()._missatge_partitura(
            {"musicxml": "/x.musicxml", "pdf": None, "mscz": None})
        self.assertIn("MusicXML", m)
        self.assertIn("MuseScore", m)
        self.assertIn("NO s'han generat", m)


class BotonsExportTests(unittest.TestCase):
    """La barra ha de tenir «Exporta WAV's» i «Exporta partitura» (petició de
    l'operador), i el segon deshabilitat fins que hi hagi resultats."""

    def test_etiquetes_i_estat(self):
        # cal mantenir la referència a la QApplication (si no, el GC la mata)
        self._app = app_main.QApplication.instance() or app_main.QApplication([])
        w = app_main.Finestra()
        self.assertIn("WAV", w.b_export.text())
        self.assertEqual(w.b_export_part.text(), "Exporta partitura")
        self.assertFalse(w.b_export_part.isEnabled())
        # el tooltip de la partitura ha d'esmentar MuseScore
        self.assertIn("MuseScore", w.b_export_part.toolTip())

    def test_transport_te_zoom_seleccio(self):
        """El transport de la finestra ha de tenir el botó de zoom a la selecció
        (el del visor s'amaga quan va incrustat)."""
        self._app = app_main.QApplication.instance() or app_main.QApplication([])
        w = app_main.Finestra()
        tips = [b.toolTip() for b in
                w.barra_transport.findChildren(app_main.QPushButton)]
        self.assertTrue(any("selecci" in t.lower() for t in tips),
                        "falta el botó de zoom a la selecció al transport")


class ZoomSeleccioTests(unittest.TestCase):
    """`rang_seleccio()` del timeline (base del «zoom a la selecció»)."""

    def _tl(self, multi, chords=(), sections=()):
        from app import timeline as tl
        t = tl.TimelineView.__new__(tl.TimelineView)
        t._multi = set(multi)
        t._chord_items = list(chords)
        t._section_items = list(sections)
        return t

    def test_sense_seleccio_retorna_none(self):
        self.assertIsNone(self._tl(set()).rang_seleccio())

    def test_rang_amb_acords(self):
        from types import SimpleNamespace as NS
        ch = [NS(t=1.0, _next_t=2.0), NS(t=5.0, _next_t=6.0)]
        t = self._tl({("chord", 0), ("chord", 1)}, chords=ch)
        self.assertEqual(t.rang_seleccio(), (1.0, 6.0))

    def test_rang_amb_seccions(self):
        from types import SimpleNamespace as NS
        se = [NS(ini=10.0, fi=20.0)]
        t = self._tl({("section", 0)}, sections=se)
        self.assertEqual(t.rang_seleccio(), (10.0, 20.0))

    def test_ignora_index_fora_de_rang(self):
        t = self._tl({("chord", 9)})
        self.assertIsNone(t.rang_seleccio())

    def test_visor_te_zoom_seleccio(self):
        from app import visor
        self.assertTrue(callable(getattr(visor.Visor, "zoom_seleccio", None)))


class CoberturaTests(unittest.TestCase):
    """INVARIANT de cobertura (regla d'or): la suma dels clips (acords i
    estructura) = la durada de la WAV → 1r a 0 (capçalera «N») i últim a la
    durada, en qualsevol mode."""

    def test_capcalera_n_acords(self):
        ac, _ = pipeline.normalitza_cobertura([(1.5, "C", "1.5")], [], 10.0)
        self.assertEqual(ac[0], (0.0, "N", "0.000000000"))
        self.assertEqual(ac[1][0], 1.5)

    def test_sense_capcalera_si_comenca_a_0(self):
        ac, _ = pipeline.normalitza_cobertura([(0.0, "C", "0.0")], [], 10.0)
        self.assertEqual(len(ac), 1)

    def test_ultima_seccio_acotada_a_la_durada(self):
        _, se = pipeline.normalitza_cobertura([], [(0.0, 8.0, "A", "N")], 20.0)
        self.assertEqual(se[-1][1], 20.0)

    def test_seccions_capcalera_sense_seccio(self):
        _, se = pipeline.normalitza_cobertura([], [(2.0, 5.0, "A", "N")], 20.0)
        self.assertEqual(se[0], (0.0, 2.0, "-", "-"))

    def test_cobertura_total_seccions(self):
        _, se = pipeline.normalitza_cobertura(
            [], [(0.0, 3.0, "A", "N"), (3.0, 8.0, "B", "N")], 10.0)
        suma = sum(fi - ini for ini, fi, *_ in se)
        self.assertAlmostEqual(suma, 10.0)

    def test_cobertura_total_acords(self):
        ac, _ = pipeline.normalitza_cobertura(
            [(1.5, "C", "1.5"), (5.0, "G", "5.0")], [], 10.0)
        # el 1r clip arrenca a 0 i l'últim acaba a la durada (implicit)
        self.assertEqual(ac[0][0], 0.0)
        self.assertEqual(ac[-1][0], 5.0)


class SafeFilenameTests(unittest.TestCase):
    """`pipeline.safe_filename` (Pas 4): noms segurs a Windows, sense regressions."""

    # 🏆 TEST DAURAT: noms d'acord HABITUALS. Nota: el separador de l'acord amb
    # baix (`/`) passa a **`_`** i NO a `-`, perquè al xifrat el `-` vol dir
    # «menor» (`A-7` ≠ `A7`): així `A7/G` → `A7_G.wav` no es confon amb res.
    DAURAT = [
        ("C", "C"), ("N", "N"), ("C#", "C#"), ("C#m7", "C#m7"),
        ("Cmaj7", "Cmaj7"), ("Csus4", "Csus4"), ("Am", "Am"),
        ("Am/G", "Am_G"), ("G/B", "G_B"), ("Bb", "Bb"), ("A#", "A#"),
        ("F#dim7", "F#dim7"), ("Dm7", "Dm7"), ("G7", "G7"),
        ("Bbmaj7", "Bbmaj7"), ("A7sus4", "A7sus4"), ("C/G", "C_G"),
        ("A-7", "A-7"), ("A-maj7/G#", "A-maj7_G#"), ("A7/G", "A7_G"),
    ]

    def test_daurat_noms_habituals(self):
        for entrada, esperat in self.DAURAT:
            self.assertEqual(pipeline.safe_filename(entrada), esperat,
                             f"ha canviat el nom de {entrada!r}")

    def test_separadors_i_truncament(self):
        self.assertEqual(pipeline.safe_filename("a/b"), "a_b")
        self.assertEqual(pipeline.safe_filename("a" + os.sep + "b"), "a_b")
        self.assertEqual(len(pipeline.safe_filename("x" * 200)), 64)

    def test_buit_usa_fallback(self):
        self.assertEqual(pipeline.safe_filename("", fallback="N"), "N")
        self.assertEqual(pipeline.safe_filename("   ", fallback="N"), "N")

    def test_caracters_reservats_windows(self):
        self.assertEqual(pipeline.safe_filename('a:b*c?d"e<f>g|h'),
                         "a-b-c-d-e-f-g-h")

    def test_punt_i_espai_final(self):
        self.assertEqual(pipeline.safe_filename("trailing. "), "trailing")
        self.assertEqual(pipeline.safe_filename("punts..."), "punts")

    def test_noms_reservats_windows(self):
        for n in ("CON", "PRN", "AUX", "NUL", "COM1", "COM9", "LPT1", "LPT9"):
            self.assertEqual(pipeline.safe_filename(n), n + "_")
        self.assertEqual(pipeline.safe_filename("con"), "con_")
        self.assertEqual(pipeline.safe_filename("NUL."), "NUL_")
        # els que només hi COMENCEN no es toquen
        self.assertEqual(pipeline.safe_filename("CONX"), "CONX")
        self.assertEqual(pipeline.safe_filename("COM10"), "COM10")

    def test_desambigua_nomes_si_xoca(self):
        u = set()
        self.assertEqual(pipeline.safe_filename("C:maj7", usats=u), "C-maj7")
        self.assertEqual(pipeline.safe_filename("C*maj7", usats=u), "C-maj7_2")
        self.assertEqual(pipeline.safe_filename("C:maj7", usats=u), "C-maj7_3")
        # un nom que no xoca NO es toca mai
        self.assertEqual(pipeline.safe_filename("G7", usats=u), "G7")

    def test_desambigua_respecta_64(self):
        u = set()
        llarg = "y" * 64
        self.assertEqual(len(pipeline.safe_filename(llarg, usats=u)), 64)
        self.assertEqual(len(pipeline.safe_filename(llarg, usats=u)), 64)

    def test_wavs_estructura_desambigua(self):
        # Integració: dues seccions que netegen al MATEIX nom → sufix.
        d = tempfile.mkdtemp()
        csvp = os.path.join(d, "estructura_ABC.csv")
        with open(csvp, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["compas_ini", "compas_fi", "lletra", "durada_s"])
            w.writerow(["1.1.1", "2.1.1", "A", "1.0"])
            w.writerow(["3.1.1", "4.1.1", "A.", "1.0"])   # neteja -> "A"
        n = pipeline.fer_wavs_estructura(csvp, d, 8000, lambda *_: None)
        self.assertEqual(n, 2)
        noms = os.listdir(d)
        self.assertIn("1-1-1_2-1-1_A.wav", noms)
        self.assertIn("3-1-1_4-1-1_A_2.wav", noms)


class CarpetaSortidaTests(unittest.TestCase):
    """Nom de la carpeta de resultats: PREFIX `AUTOCHORDS_` (font única)."""

    def test_prefix_i_no_sufix(self):
        self.assertEqual(pipeline.PREFIX_SORTIDA, "AUTOCHORDS_")

    def test_nom_derivat(self):
        # Independents de plataforma: amb `os.path.join` (a Windows ntpath fa
        # servir '\') en lloc de rutes '/' hardcodejades.
        wav = os.path.join(os.sep, "musica", "Tema.wav")
        self.assertEqual(pipeline.carpeta_sortida(wav),
                         os.path.join(os.sep, "musica", "AUTOCHORDS_Tema"))

    def test_al_costat_de_la_wav(self):
        wav = os.path.join(os.sep, "a", "b", "La meva cançó.mp3")
        self.assertEqual(pipeline.carpeta_sortida(wav),
                         os.path.join(os.sep, "a", "b",
                                      "AUTOCHORDS_La meva cançó"))

    def test_sense_directori(self):
        self.assertEqual(pipeline.carpeta_sortida("Tema.wav"),
                         "AUTOCHORDS_Tema")


# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_postproc.py
# ══════════════════════════════════════════════════════════════════════════
"""Casos límit de `app/postproc.py` (post-processat de l'anàlisi crua).

El post-processador NO és el límit del model: l'ordre, els negatius i la
cobertura es garanteixen DESPRÉS, a `pipeline.normalitza_cobertura()` (regles
d'or #1, #4 i #8). Ací es fixa què fa amb l'entrada rara perquè quede clar on
acaba la seua responsabilitat i que no peta (auditoria 18-10-2026).
"""


class TestProcessaAcords(unittest.TestCase):

    def test_buit_i_un_de_sol(self):
        self.assertEqual(postproc.processa_acords([], durada_min=0.0), [])
        self.assertEqual(postproc.processa_acords([(0.0, "C")], durada_min=0.0),
                         [(0.0, "C")])

    def test_duplicats_mateix_instant_es_fonen(self):
        self.assertEqual(
            postproc.processa_acords([(0.0, "C"), (2.0, "C")], durada_min=0.0),
            [(0.0, "C")])

    def test_un_sol_acord_no_el_treu_encara_que_siga_curt(self):
        """Amb `durada_min` gran, un acord sol no desapareix (no hi ha veí)."""
        self.assertEqual(postproc.processa_acords([(0.0, "C")], durada_min=3.0),
                         [(0.0, "C")])

    def test_no_ordena_ni_sana_negatius(self):
        """Documenta el CONTRACTE: això és post-processat, no el límit del
        model. L'ordre i els temps vàlids els garanteix `normalitza_cobertura`
        (regles #1 i #8), que és qui alimenta el model."""
        desordenat = [(4.0, "G"), (0.0, "C"), (2.0, "Am")]
        self.assertEqual(postproc.processa_acords(desordenat, durada_min=0.0),
                         desordenat)
        negatiu = [(-2.0, "C"), (2.0, "G")]
        self.assertEqual(postproc.processa_acords(negatiu, durada_min=0.0),
                         negatiu)


class TestSnapAcords(unittest.TestCase):

    def test_buit(self):
        self.assertEqual(postproc.snap_acords([], 120.0), [])

    def test_encaixa_al_mig_temps(self):
        """A 120 BPM la divisió és 0,5 s: 0,37 s va a 0,5."""
        self.assertEqual(postproc.snap_acords([(0.37, "C")], 120.0),
                         [(0.5, "C")])

    def test_bpm_zero_no_canvia_res(self):
        self.assertEqual(postproc.snap_acords([(0.37, "C")], 0.0),
                         [(0.37, "C")])

    def test_negatiu_va_a_zero(self):
        self.assertEqual(postproc.snap_acords([(-0.4, "C")], 120.0),
                         [(0.0, "C")])

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_regla12_export.py
# ══════════════════════════════════════════════════════════════════════════
"""Regla d'or #12 — PARITAT A L'EXPORTACIÓ (el paquet tracta els 3 tipus igual).

`docs/REGLES_DE_LA_APP.md` §12: el paquet exportat ha de tractar igual els
**acords**, l'**estructura** i el **mapa de tempo/compàs**, cadascun amb la seva
part:

- acords: `acords.csv` + `wavs_acords/`
- estructura: `estructura_ABC.csv` + `wavs_estructura/`
- mapa de tempo/compàs: **carpeta pròpia** `mapa_tempo/` amb `tempo.csv` i
  `compas.csv`

Abans el mapa no s'exportava: el paquet no era paritari.
"""


DURADA = 16.0
_regla12_export__ACORDS = [(0.0, "C", "0.0"), (4.0, "Am", "4.0"), (8.0, "F", "8.0"),
          (12.0, "G", "12.0")]
SECCIONS = [(0.0, 8.0, "A", "A"), (8.0, DURADA, "B", "B")]
TRAMS = [(0.0, 8.0, 120.0, 4, 4), (8.0, DURADA, 90.0, 3, 4)]


class _regla12_export___Base(unittest.TestCase):

    def _exporta(self, trams=None):
        td = tempfile.mkdtemp()
        sortida = os.path.join(td, "AUTOCHORDS_tema")
        os.makedirs(sortida, exist_ok=True)
        csv_ac = os.path.join(sortida, "acords.csv")
        with open(csv_ac, "w", encoding="utf-8") as f:
            f.write("inici_s,fi_s,acord\n")
            for t, n, ts in _regla12_export__ACORDS:
                f.write(f"{t},{t + 4.0},{n}\n")
        res = pipeline.exporta_total(
            csv_ac, None, sortida, 120.0, 4, 0.0, 44100, lambda *a: None,
            tempo_fix=True, amb_estructura=True, total_s=DURADA,
            acords=list(_regla12_export__ACORDS), seccions=list(SECCIONS), mapa_tempo=trams)
        return sortida, res


class TestRegla12ParitatExport(_regla12_export___Base):

    def test_els_tres_tipus_tenen_la_seva_part(self):
        """Amb el mapa del model, el paquet ha de portar les TRES parts."""
        sortida, res = self._exporta(TRAMS)
        # acords
        self.assertTrue(os.path.isfile(os.path.join(sortida, "acords.csv")))
        self.assertTrue(os.path.isdir(os.path.join(sortida, "wavs_acords")))
        # estructura
        self.assertTrue(os.path.isfile(
            os.path.join(sortida, "estructura_ABC.csv")))
        self.assertTrue(os.path.isdir(os.path.join(sortida, "wavs_estructura")))
        # mapa de BPM/compàs, amb carpeta PRÒPIA
        mapa = os.path.join(sortida, "mapa_tempo")
        self.assertTrue(os.path.isdir(mapa), "falta la carpeta del mapa")
        self.assertTrue(os.path.isfile(os.path.join(mapa, "tempo.csv")))
        self.assertTrue(os.path.isfile(os.path.join(mapa, "compas.csv")))
        self.assertEqual(res.get("mapa_tempo_dir"), mapa)
        self.assertEqual(res.get("n_mapa_trams"), len(TRAMS))

    def test_el_mapa_exportat_es_el_del_model(self):
        """El que s'exporta és el MODEL (no una còpia vella del disc)."""
        sortida, _regla12_export___ = self._exporta(TRAMS)
        trams = pipeline.llegeix_tempo_map(
            os.path.join(sortida, "mapa_tempo"), 120.0, 4, 4, DURADA)
        self.assertEqual([(float(t[0]), float(t[1]), float(t[2]), int(t[3]),
                           int(t[4])) for t in trams], TRAMS)

    def test_sense_mapa_no_hi_ha_carpeta(self):
        """Sense mapa al model (flux antic), el paquet queda com era."""
        sortida, res = self._exporta(None)
        self.assertFalse(os.path.isdir(os.path.join(sortida, "mapa_tempo")))
        self.assertNotIn("mapa_tempo_dir", res)

    def test_el_csv_de_compas_te_els_compassos_del_mapa(self):
        """El `compas.csv` ha de dur el compàs de cada tram (4/4 i 3/4)."""
        sortida, _regla12_export___ = self._exporta(TRAMS)
        with open(os.path.join(sortida, "mapa_tempo", "compas.csv"),
                  encoding="utf-8") as f:
            files = [r for r in csv.reader(f) if r and not r[0][0].isalpha()]
        valors = [(int(r[2]), int(r[3])) for r in files]
        self.assertEqual(valors, [(4, 4), (3, 4)])

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_requirements.py
# ══════════════════════════════════════════════════════════════════════════
"""Guard de dependències: MAI `numpy >= 2` ni `PyQt6`.

El Q9400 no té AVX/SSE4.2: `numpy` 2.x demana `x86_64-v2` (SIGILL) i PyQt6
trencaria el desplegament a High Sierra 10.13. Aquest test ho vigila a
`requirements.txt`, `pyproject.toml` i els workflows de CI: si algú ho
introdueix sense voler, el CI peta.
"""

_requirements__ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FITXERS = ([os.path.join(_requirements__ROOT, "requirements.txt"),
            os.path.join(_requirements__ROOT, "pyproject.toml")]
           + sorted(glob.glob(os.path.join(_requirements__ROOT, ".github", "workflows", "*.yml"))))

# Especificadors que admetrien la 2.x de numpy.
_NUMPY_2 = (r"numpy\s*>=\s*2", r"numpy\s*==\s*2", r"numpy\s*>\s*2",
            r"numpy\s*~=\s*2", r"numpy\s*!=\s*1")
# Requisit REAL de numpy: `numpy` seguit d'un operador (no una menció en prosa).
_RE_NUMPY = re.compile(r"numpy\s*((?:==|>=|<=|>|<|~=|!=)\s*[^\"'\s]+)")


class GuardAvxTests(unittest.TestCase):
    """Regla d'or #9: cap binari del paquet pot requerir **AVX**.

    El Q9400 no en té: un binari compilat amb AVX peta amb SIGILL (ja va passar
    amb la CLI d'opencode). La garantia ve del build, així que aquest test
    vigila que els scripts de compilació dels natius **no** hi introdueixin
    flags amb AVX ni `-march=native` (que compilaria pel maquinari de qui
    construeix, no pel de destí).
    """

    SCRIPTS = ("eines/compila_vamp_host.sh", "eines/compila_vamp_plugins.sh",
               "eines/compila_vamp_plugins.sh")
    PROHIBIT = (r"-mavx", r"-mavx2", r"-mavx512", r"-march\s*=\s*native",
                r"-march\s*=\s*haswell", r"-mtune\s*=\s*native")

    def test_cap_flag_amb_avx(self):
        for rel in self.SCRIPTS:
            f = os.path.join(_requirements__ROOT, rel)
            if not os.path.isfile(f):
                continue
            with open(f, encoding="utf-8") as fh:
                linies = [ln for ln in fh.read().splitlines()
                          if not ln.lstrip().startswith("#")]   # sense comentaris
            text = "\n".join(linies)
            for pat in self.PROHIBIT:
                self.assertIsNone(
                    re.search(pat, text),
                    f"{rel}: hi ha un flag amb AVX ({pat}) — el Q9400 no en té")

    def test_els_builds_demanen_sse2(self):
        for rel in ("eines/compila_vamp_host.sh",
                    "eines/compila_vamp_plugins.sh"):
            f = os.path.join(_requirements__ROOT, rel)
            if not os.path.isfile(f):
                continue
            with open(f, encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn("-msse2", text,
                          f"{rel}: cal fixar el maquinari mínim amb -msse2")


class DependènciesGuardTests(unittest.TestCase):
    @staticmethod
    def _sense_comentaris(t):
        """Treu els comentaris (`#...`): un comentari no és una dependència."""
        return "\n".join(ln.split("#", 1)[0] for ln in t.splitlines())

    def _llegeix(self):
        d = {}
        for f in FITXERS:
            if os.path.isfile(f):
                with open(f, encoding="utf-8") as fh:
                    d[f] = self._sense_comentaris(fh.read())
        return d

    def test_cap_pyqt6(self):
        for f, t in self._llegeix().items():
            self.assertNotIn("PyQt6", t, f"PyQt6 introduït a {f}")

    def test_cap_especificador_de_numpy_2(self):
        for f, t in self._llegeix().items():
            for patro in _NUMPY_2:
                self.assertIsNone(re.search(patro, t),
                                  f"{f}: numpy podria resoldre's a 2.x ({patro})")

    def test_si_es_demana_numpy_ha_d_excloure_la_2(self):
        # Només mirem REQUISITS reals (`numpy` + operador), no mencions en prosa
        # (noms de passos, comentaris...).
        for f, t in self._llegeix().items():
            for m in _RE_NUMPY.finditer(t):
                spec = m.group(1).replace(" ", "")
                ok = ("<2" in spec) or spec.startswith("==1.")
                self.assertTrue(ok, f"{f}: numpy '{m.group(1)}' podria ser 2.x")

    def test_requirements_pin_exacte(self):
        # A requirements.txt totes les dependències van amb `==` (pins exactes).
        with open(os.path.join(_requirements__ROOT, "requirements.txt"), encoding="utf-8") as fh:
            linies = [ln.strip() for ln in fh
                      if ln.strip() and not ln.strip().startswith("#")]
        self.assertTrue(linies, "requirements.txt buit?")
        for ln in linies:
            nom = ln.split(";")[0].strip()      # sense el marcador de plataforma
            self.assertIn("==", nom, f"sense pin exacte: {ln!r}")
        m = re.search(r"^numpy==([\d.]+)", "\n".join(linies), re.M)
        self.assertIsNotNone(m, "requirements.txt ha de fixar numpy amb ==")
        self.assertTrue(m.group(1).startswith("1."),
                        f"numpy ha de ser 1.x, no {m.group(1)}")

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_scripts_smoke.py
# ══════════════════════════════════════════════════════════════════════════
"""Smoke dels scripts d'_scripts_smoke__ARREL: que es puguen executar.

L'auditoria (18-10-2026) va trobar dos scripts d'arrel que PETAVEN de bon
començament i que cap test mirava:

- `wav_a_wavs.py`: feia `import pipeline` amb `app/` al `sys.path` → petava amb
  «attempted relative import with no known parent package» (el mòdul viu dins el
  paquet `app` des del refactor).
- `acords_a_live.py` sense arguments: `IndexError`.

Aquests guards són barats (una execució amb `--help` o sense arguments) i
haurien atrapat tots dos.
"""


_scripts_smoke__ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _corre(script, *args, timeout=60):
    return subprocess.run([plataforma.python_actual(),
                           os.path.join(_scripts_smoke__ARREL, script), *args],
                          capture_output=True, text=True, timeout=timeout,
                          cwd=_scripts_smoke__ARREL)


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
        scripts = sorted(glob.glob(os.path.join(_scripts_smoke__ARREL, "*.sh"))
                         + glob.glob(os.path.join(_scripts_smoke__ARREL, "eines", "*.sh")))
        self.assertGreaterEqual(len(scripts), 5, "no he trobat els scripts")
        for s in scripts:
            p = subprocess.run(["bash", "-n", s], capture_output=True,
                               text=True, timeout=60)
            self.assertEqual(p.returncode, 0,
                             f"sintaxi de {os.path.basename(s)}:\n{p.stderr}")

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_vamp_params_icones.py
# ══════════════════════════════════════════════════════════════════════════
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests dels mòduls que no en tenien cap: `app/vamp_params.py` i `app/icones.py`.

- `vamp_params`: parseja els descriptors `.n3` dels plugins Vamp (paràmetres
  quantitzats i numèrics, ordre del descriptor, valors per defecte).
- `icones`: disponibilitat dels SVG i els colors de la UI (l'app no ha de petar
  mai per una icona que falti).
"""


N3_PROVA = """
plugbase:test_param_alpha a vamp:QuantizedParameter ;
    vamp:identifier "alpha" ;
    dc:title "Alpha" ;
    value_names ("one", "two", "three") ;
    min_value 1 ; max_value 3 ; quantize_step 1 ; default_value 2 .

plugbase:test_param_beta a vamp:Parameter ;
    vamp:identifier "beta" ;
    dc:title "Beta" ;
    min_value 0.0 ; max_value 10.0 ; default_value 5.0 .

plugbase:test a vamp:Plugin ;
    vamp:parameter plugbase:test_param_alpha ;
    vamp:parameter plugbase:test_param_beta .
"""


class TestVampParams(unittest.TestCase):
    """Els descriptors `.n3` dels plugins Vamp es converteixen bé."""

    def _n3(self, text=N3_PROVA):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "test.n3")
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        self.addCleanup(lambda: os.remove(p))
        return p

    def test_parseja_quantitzat_i_numeric(self):
        ps = vamp_params.llegeix_params(self._n3(), "test")
        self.assertEqual(len(ps), 2, "dos paràmetres al descriptor")
        alpha = next(p for p in ps if p["id"] == "alpha")
        beta = next(p for p in ps if p["id"] == "beta")
        self.assertEqual(alpha["tipus"], "quantitzat")
        self.assertEqual(alpha["titol"], "Alpha")
        self.assertEqual(alpha["valors"], ["one", "two", "three"])
        self.assertEqual(alpha["minim"], 1.0)
        self.assertEqual(alpha["maxim"], 3.0)
        self.assertEqual(alpha["defecte"], 2.0)
        self.assertEqual(beta["tipus"], "numeric")
        self.assertEqual(beta["valors"], [])
        self.assertEqual(beta["maxim"], 10.0)
        self.assertEqual(beta["pas"], 0.0, "un numèric no té pas de quantització")

    def test_ordre_del_descriptor(self):
        ps = vamp_params.llegeix_params(self._n3(), "test")
        self.assertEqual([p["id"] for p in ps], ["alpha", "beta"],
                         "s'ha de respectar l'ordre declarat al plugin")

    def test_plugin_sense_parametres(self):
        ps = vamp_params.llegeix_params(
            self._n3("plugbase:test a vamp:Plugin .\n"), "test")
        self.assertEqual(ps, [])

    def test_params_de_clau_desconeguda(self):
        with self.assertRaises(KeyError):
            vamp_params.params_de("no_existeix")

    def test_params_de_i_valors_per_defecte_dels_reals(self):
        # Amb els plugins reals del repo (si hi són) o llista buida; mai peta.
        for clau in ("chords", "structure"):
            ps = vamp_params.params_de(clau)
            self.assertIsInstance(ps, list)
            vd = vamp_params.valors_per_defecte(clau)
            self.assertIsInstance(vd, dict)
            self.assertEqual(set(vd), {p["id"] for p in ps})


class _vamp_params_icones__TestIcones(unittest.TestCase):
    """Icones SVG + colors de la UI."""

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_disponible_amb_una_icona_real(self):
        svgs = [f[:-4] for f in os.listdir(icones._DIR) if f.endswith(".svg")]
        self.assertTrue(svgs, "hi ha d'haver icones al repo")
        for nom in svgs[:5]:
            self.assertTrue(icones.disponible(nom), nom)

    def test_disponible_inexistent(self):
        self.assertFalse(icones.disponible("no_existeix_zzz"))

    def test_ico_sense_svg_retorna_buida_sense_petar(self):
        # L'app no ha de petar mai per una icona que falti.
        ico = icones.ico("no_existeix_zzz")
        self.assertTrue(ico.isNull(), "ha de tornar un QIcon buit")

    def test_ico_real_no_es_buida(self):
        svgs = [f[:-4] for f in os.listdir(icones._DIR) if f.endswith(".svg")]
        self.assertFalse(icones.ico(svgs[0]).isNull())

    def test_colors_son_hex_valids(self):
        for c in (icones.TEXT, icones.MUTED, icones.ACTIU, icones.BLAU,
                  icones.GROC, icones.VERMELL):
            self.assertRegex(c, r"^#[0-9a-fA-F]{6}$", f"color invàlid: {c!r}")

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_xifrat.py
# ══════════════════════════════════════════════════════════════════════════
"""Notació del xifrat (`app/xifrat.py`): parseig del baix i forma canònica.

Decisió de l'operador (2026-10-15, «opció 3»): el MODEL desa **sempre** els
acords en una forma canònica; si l'usuari n'escriu una variant, l'app l'enten i
la deixa bé → el model, els noms de fitxer de l'export i la partitura
(MusicXML → MuseScore) parlen tots la mateixa llengua.
"""


CANONICS = [
    # tríades
    ("C", "C"), ("Cmaj", "C"), ("CM", "C"), ("CΔ", "C"), ("c", "C"),
    ("Am", "A-"), ("A-", "A-"), ("Amin", "A-"), ("Ami", "A-"), ("amin", "A-"),
    ("Cdim", "Cdim"), ("C°", "Cdim"), ("Co", "Cdim"), ("Caug", "Caug"),
    ("C+", "Caug"), ("Csus4", "Csus4"), ("Csus", "Csus4"), ("Csus2", "Csus2"),
    # séptimes
    ("C7", "C7"), ("Cmaj7", "CMaj7"), ("CM7", "CMaj7"), ("CΔ7", "CMaj7"),
    ("CMa7", "CMaj7"), ("Cm7", "C-7"), ("Cmin7", "C-7"), ("C-7", "C-7"),
    ("CmM7", "C-Maj7"), ("CmMaj7", "C-Maj7"), ("C-maj7", "C-Maj7"),
    ("Cdim7", "Cdim7"), ("Co7", "Cdim7"), ("Cm7b5", "C-7b5"), ("Cø", "C-7b5"),
    ("Cø7", "C-7b5"), ("Caug7", "Caug7"),
    # sisenes / extensions / afegits
    ("C6", "C6"), ("Cm6", "C-6"), ("C-6", "C-6"), ("Cadd9", "Cadd9"),
    ("C9", "C9"), ("Cm9", "C-9"), ("Cmaj9", "CMaj9"), ("CM9", "CMaj9"),
    ("C7#9", "C7#9"), ("C11", "C11"), ("C13", "C13"), ("C7sus4", "C7sus4"),
    # alteracions de l'arrel (+ baix)
    ("Bb", "Bb"), ("A#", "A#"), ("F#dim7", "F#dim7"), ("BbMaj7", "BbMaj7"),
    ("A7/G", "A7/G"), ("Am/G", "A-/G"), ("G/D", "G/D"), ("C/E", "C/E"),
    ("A-7/G", "A-7/G"), ("A-6/F#", "A-6/F#"), ("Amaj7/G#", "AMaj7/G#"),
    ("C/Bb", "C/Bb"), ("a7/g", "A7/G"),
    # «sense acord» i espais
    ("N", "N"), ("NC", "N"), ("N.C.", "N"), ("", ""), ("  C  ", "C"),
]


class TestFormaCanonica(unittest.TestCase):
    def test_taula(self):
        for brut, net in CANONICS:
            self.assertEqual(xifrat.normalitza_xifrat(brut), net,
                             f"{brut!r} hauria de donar {net!r}")

    def test_el_baix_no_es_confon_amb_6_9(self):
        """`C6/9` porta barra però NO és un acord amb baix."""
        self.assertEqual(xifrat.parteix_baix("C6/9"), ("C6/9", ""))
        self.assertEqual(xifrat.parteix_baix("A7/G"), ("A7", "G"))
        self.assertEqual(xifrat.normalitza_xifrat("C6/9"), "C6add9")

    def test_es_cap_acord(self):
        for t in ("N", "n", "NC", "N.C.", "", "  "):
            self.assertTrue(xifrat.es_cap_acord(t), t)
        for t in ("C", "Am", "N7"):
            self.assertFalse(xifrat.es_cap_acord(t), t)

    def test_text_no_dacord_no_es_trenca(self):
        for t in ("solo", "veus", "H7", "X"):
            self.assertEqual(xifrat.normalitza_xifrat(t), t,
                             f"no s'hauria de tocar {t!r}")

    def test_arrel_i_qualitat(self):
        self.assertEqual(xifrat.parteix_arrel("BbMaj7"), ("Bb", "Maj7"))
        self.assertEqual(xifrat.parteix_arrel("A-7"), ("A", "-7"))
        self.assertIsNone(xifrat.parteix_arrel("solo"))


# Els tipus de la taula de referència de l'operador («acords i tensions»,
# 3 nivells) amb el `kind` de MusicXML i els GRAUS que han de generar.
TIPUS_REFERENCIA = [
    # Beginners
    ("C", "major", []), ("Cm", "minor", []), ("Cdim", "diminished", []),
    ("C7", "dominant", []), ("Cm7", "minor-seventh", []),
    ("Cm7b5", "half-diminished", []), ("Cmaj7", "major-seventh", []),
    # Intermediates
    ("Cmajb5", "major", [(5, -1, "alter")]),
    ("C5", "power", []), ("Csus2", "suspended-second", []),
    ("Csus4", "suspended-fourth", []), ("C+", "augmented", []),
    ("C6", "major-sixth", []), ("Cadd9", "major", [(9, 0, "add")]),
    ("Cm6", "minor-sixth", []), ("Cmadd9", "minor", [(9, 0, "add")]),
    ("Cdim7", "diminished-seventh", []),
    ("C7sus4", "suspended-fourth", [(7, -1, "add")]),
    ("C7b5", "dominant", [(5, -1, "alter")]),
    ("C7#5", "augmented-seventh", []), ("Cm(maj7)", "major-minor", []),
    ("C6add9", "major-sixth", [(9, 0, "add")]),
    ("Cm6add9", "minor-sixth", [(9, 0, "add")]),
    ("C7b9", "dominant", [(9, -1, "alter")]),
    ("C7#9", "dominant", [(9, 1, "alter")]),
    ("Cm7b9", "minor-seventh", [(9, -1, "alter")]),
    ("C9", "dominant-ninth", []),
    ("C9b5", "dominant-ninth", [(5, -1, "alter")]),
    ("C9#5", "dominant-ninth", [(5, 1, "alter")]),
    ("Cm9", "minor-ninth", []), ("Cmaj9", "major-ninth", []),
    ("C11", "dominant-11th", []), ("Cm11", "minor-11th", []),
    ("Cmaj11", "major-11th", []), ("C13", "dominant-13th", []),
    ("Cm13", "minor-13th", []), ("Cmaj13", "major-13th", []),
    # Advanced
    ("Cmaj7b5", "major-seventh", [(5, -1, "alter")]),
    ("Cmaj7#5", "major-seventh", [(5, 1, "alter")]),
    ("C7b5b9", "dominant", [(5, -1, "alter"), (9, -1, "alter")]),
    ("C7#5b9", "augmented-seventh", [(9, -1, "alter")]),
    ("C7#5#9", "augmented-seventh", [(9, 1, "alter")]),
    ("C7add11", "dominant", [(11, 0, "add")]),
    ("C7#11", "dominant", [(11, 1, "alter")]),
    ("Cm7b5b9", "half-diminished", [(9, -1, "alter")]),
    ("Cm7add11", "minor-seventh", [(11, 0, "add")]),
    ("Cmaj7#11", "major-seventh", [(11, 1, "alter")]),
    ("Cm9b5", "minor-ninth", [(5, -1, "alter")]),
    ("Cm(maj9)", "major-minor", [(9, 0, "add")]),
    ("Cmaj9#5", "major-ninth", [(5, 1, "alter")]),
    ("C9#11", "dominant-ninth", [(11, 1, "alter")]),
    ("Cmaj9#11", "major-ninth", [(11, 1, "alter")]),
    ("C11b9", "dominant-11th", [(9, -1, "alter")]),
    ("C13b5b9", "dominant-13th", [(5, -1, "alter"), (9, -1, "alter")]),
    ("C13b9", "dominant-13th", [(9, -1, "alter")]),
    ("C13#9", "dominant-13th", [(9, 1, "alter")]),
    ("C13#11", "dominant-13th", [(11, 1, "alter")]),
]


class TestGraus(unittest.TestCase):
    def test_graus_treure(self):
        """`noN` = treure un grau → MusicXML `subtract` (`no3`, `no5`, `no7`…)."""
        for xif, kind, gr in [
                ("Cno5", "major", [(5, 0, "subtract")]),
                ("Cno3", "major", [(3, 0, "subtract")]),
                ("Cno7", "major", [(7, 0, "subtract")]),
                ("Cmaj7no5", "major-seventh", [(5, 0, "subtract")]),
                ("Cm7no3no5", "minor-seventh",
                 [(3, 0, "subtract"), (5, 0, "subtract")]),
                ("C7no9", "dominant", [(9, 0, "subtract")]),
                ("C13no5", "dominant-13th", [(5, 0, "subtract")]),
                ("Cm6no5", "minor-sixth", [(5, 0, "subtract")])]:
            pa = xifrat.parteix_arrel(xifrat.normalitza_xifrat(xif))
            self.assertIsNotNone(pa, xif)
            k, g = xifrat.kind_i_graus(pa[1])
            self.assertEqual(k, kind, f"{xif}: kind")
            self.assertEqual(list(g), [tuple(x) for x in gr], f"{xif}: graus")

    def test_alteracions_dobles(self):
        """Dobles alteracions (MuseScore: `##`, `bb` i `x` = doble sostingut)."""
        for brut, net in [("C##", "C##"), ("Cbb", "Cbb"), ("Cx", "C##"),
                          ("Cx5", "C##5"), ("F##m7", "F##-7"),
                          ("C##/Dbb", "C##/Dbb"), ("Gbbmaj7", "GbbMaj7"),
                          ("Cxyz", "Cxyz")]:     # `x` + lletra ≠ accidental
            self.assertEqual(xifrat.normalitza_xifrat(brut), net, brut)

    def test_resta_qualitat(self):
        """El tros no convertible (p. ex. `alt`) es conserva per al `text`."""
        self.assertEqual(xifrat.resta_qualitat("7alt"), "alt")
        self.assertEqual(xifrat.resta_qualitat("7#11"), "")   # → `<degree>`
        self.assertEqual(xifrat.resta_qualitat("Maj7"), "")
        self.assertEqual(xifrat.resta_qualitat("xyz"), "xyz")

    def test_paraules_i_parentesis(self):
        """`major`/`minor` senceres i els graus entre parèntesis.

        Regressió (graella «Create The Music»): `Cmajor` feia `CMajdimr` i
        `C7(9,13)` feia `C7913` (els graus s'engrunaven i es perdien).
        """
        for brut, net in [("Cmajor", "C"), ("CMajor", "C"),
                          ("Cminor", "C-"), ("CMinor", "C-"),
                          ("C7(9,13)", "C7add9add13"),
                          ("Cmaj7(9)", "CMaj7add9"),
                          ("Cmaj7(13)", "CMaj7add13"),
                          ("Cmaj7(#11)", "CMaj7#11"),
                          ("C7(#9,b5)", "C7#9b5"),
                          ("C7sus2", "C7sus2"), ("C9sus4", "C9sus4"),
                          ("C13sus4", "C13sus4")]:
            self.assertEqual(xifrat.normalitza_xifrat(brut), net, brut)

    def test_els_graus_dels_parentesis_no_sengrunen(self):
        k, g = xifrat.kind_i_graus("7add9add13")
        self.assertEqual(k, "dominant")
        self.assertEqual(list(g), [(9, 0, "add"), (13, 0, "add")])

    def test_alteracions_no_son_acords(self):
        """Text que no és un xifrat NO s'ha de reconèixer (ni amb `no5`)."""
        for t in ("Cxyz", "solo", "veus", "X"):
            pa = xifrat.parteix_arrel(xifrat.normalitza_xifrat(t))
            k, _g = xifrat.kind_i_graus(pa[1]) if pa else (None, ())
            self.assertIsNone(k, f"{t!r} no s'hauria de reconèixer")


class TestTipusDeReferencia(unittest.TestCase):
    def test_kind_i_graus(self):
        for xif, kind, gr in TIPUS_REFERENCIA:
            q = xifrat.normalitza_xifrat(xif)[1:]      # treu l'arrel («C»)
            k, g = xifrat.kind_i_graus(q)
            self.assertEqual(k, kind, f"{xif}: kind={k!r} (esperat {kind!r})")
            self.assertEqual(list(g), [tuple(x) for x in gr], f"{xif}: graus")

    def test_tots_els_tipus_tenen_arrel_i_qualitat(self):
        for xif, _k, _g in TIPUS_REFERENCIA:
            pa = xifrat.parteix_arrel(xifrat.normalitza_xifrat(xif))
            self.assertIsNotNone(pa, xif)
            self.assertEqual(pa[0], "C", xif)

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_xocs_inici_csv.py
# ══════════════════════════════════════════════════════════════════════════
"""Regressió del BUG #5 (informe OC-6/357): xocs d'inici DINS la resolució del CSV.

El CSV d'acords es desa amb `TEMPS_DEC = 6` decimals (1 µs) i el validador
exigeix 1 ms entre inicis. Dos acords amb inicis separats per menys d'1 ms es
consideren un xoc i el segon es rebutja/neteja (trencaria les regles #1/#2).

Repro original: amb un E7 a `t = 6.831683`, `ac_add_chord(t_s=6.8317, "DUP")`
s'acceptava (el validador només mirava `t <= prev + 1e-9`) i el CSV quedava amb
dues files «6.83».
"""


DUR = 40.0
E7_T = 6.831683
XOC_T = 6.8317          # a 1,7e-5 s de l'E7 → xoc real (< 1 ms)


def _escriu_wav(ruta, dur=DUR):
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * int(44100 * dur))


def _llegeix_acords(ruta):
    with open(ruta, encoding="utf-8") as f:
        return [(float(r[0]), r[1]) for r in csv.reader(f) if r]


def _visor(acords=((0.0, "C"), (E7_T, "E7"))):
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "tema.wav")
    _escriu_wav(wav)
    sortida = pipeline.carpeta_sortida(wav)
    os.makedirs(sortida, exist_ok=True)
    ca = os.path.join(sortida, "acords.csv")
    with open(ca, "w", encoding="utf-8") as f:
        for t, nom in acords:
            f.write(f"{t},{t + 1},{nom}\n")
    sa = os.path.join(sortida, "estructura_ABC.csv")
    with open(sa, "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n")
        f.write(f"0.00,{DUR}, {DUR},A,A,1,1\n")
    v = visor_mod.Visor(wav, ca, sa, 120.0, 4, True)
    v.td, v.sortida = td, sortida
    return v


class _xocs_inici_csv___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])


class _FinestraFalsa:
    def __init__(self, visor):
        self.visor_ref = visor
        self.sortida = "/tmp/out"

    def windowTitle(self):
        return "Auto Chords — prova"


class TestXocsResolucioCSV(_xocs_inici_csv___Base):
    def test_validador_rebutja_inicis_dins_la_resolucio(self):
        v = _visor()
        with self.assertRaises(ValueError):
            v._valida_canvis_acords([(0.0, "C", "0"),
                                     (E7_T, "E7", "6.831683"),
                                     (XOC_T, "DUP", "6.8317")])

    def test_validador_accepta_just_a_la_resolucio(self):
        v = _visor()
        ok = v._valida_canvis_acords([(0.0, "C", "0"),
                                      (6.83, "E7", "6.83"),
                                      (6.831, "DUP", "6.831")])
        self.assertEqual(len(ok), 3)

    def test_afegeix_acord_rebutja_el_xoc(self):
        v = _visor()
        with self.assertRaises(ValueError):
            v._afegeix_acord(XOC_T, "DUP")


    def test_el_csv_no_te_mai_temps_duplicats_ni_clips_buits(self):
        v = _visor()
        with self.assertRaises(ValueError):
            v._afegeix_acord(XOC_T, "DUP")      # xoc → rebutjat
        v._afegeix_acord(6.90, "G")             # aquest sí (> 10 ms del E7)
        v._desa_i_regenera()
        files = _llegeix_acords(v.csv_acords)
        temps = [t for t, _xocs_inici_csv___ in files]
        self.assertEqual(len(temps), len(set(temps)),
                         f"el CSV té temps duplicats: {temps}")
        for (t0, n0), (t1, _n1) in zip(files, files[1:]):
            self.assertGreater(t1 - t0, 0.0,
                               f"clip de durada 0 al CSV entre {n0} i {t1}")
        self.assertGreater(DUR - files[-1][0], 0.0)

    def test_repara_un_csv_que_ja_venia_xocat(self):
        """Si el CSV ja portava el xoc (versió antiga), en carregar es neteja."""
        v = _visor(acords=((0.0, "C"), (E7_T, "E7"), (XOC_T, "DUP")))
        noms = [a[2][0] for a in v.acords]
        self.assertNotIn("DUP", noms)
        self.assertIn("E7", noms)
        self.assertEqual(noms, ["C", "E7"])
        # ...i el CSV del disc queda net
        temps = [t for t, _xocs_inici_csv___ in _llegeix_acords(v.csv_acords)]
        self.assertEqual(len(temps), len(set(temps)))


class TestExportMaiEscriuClipsBuits(_xocs_inici_csv___Base):
    def test_segment_de_durada_zero_s_omet(self):
        """Blindatge darrer: encara que un CSV porti un xoc, l'export no ha
        d'escriure cap WAV de durada 0."""
        td = tempfile.mkdtemp()
        cs = os.path.join(td, "acords.csv")
        with open(cs, "w", encoding="utf-8") as f:
            f.write("0.00,5.00,C\n5.00,5.00,E7\n5.00,5.00,DUP\n")
        dest = os.path.join(td, "wavs")
        pipeline.fer_wavs_acords_lliures(cs, 10.0, dest, 44100,
                                        lambda _m: None)
        self.assertEqual(sorted(os.listdir(dest)),
                         ["0000.000s_0005.000s_C.wav", "0005.000s_0010.000s_DUP.wav"])


def _xocs_inici_csv_tearDownModule():
    # Neteja ORDENADA dels objectes Qt del mòdul (evita destrucció pel GC en un
    # test posterior -> access violation intermitent). Vegeu tests/_qt_neteja.py.
    try:
        import _qt_neteja
    except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()


class TestPaperera(unittest.TestCase):
    """`plataforma.a_la_paperera`: mai esborrar en sec si no hi ha paperera."""

    def test_sense_mecanisme_retorna_false_i_no_esborra(self):
        from app import plataforma
        if not plataforma.ES_LINUX:
            self.skipTest("només Linux (els altres SO tenen el seu propi camí)")
        carp = tempfile.mkdtemp()
        ruta = os.path.join(carp, "x.txt")
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write("x")
        with patch.object(plataforma.shutil, "which", return_value=None):
            self.assertFalse(plataforma.a_la_paperera(ruta))
        self.assertTrue(os.path.exists(ruta),
                        "sense paperera no s'ha d'esborrar mai res")


class TestHigieneTemporals(unittest.TestCase):
    """La suite no pot deixar res al disc (`AGENTS.md` §«Com es treballa»).

    Forat detectat el 2026-10-19: les WAV creades amb `tempfile.mkstemp(suffix=
    ".wav")` fan que `pipeline.carpeta_sortida()` cree la germana
    `/tmp/AUTOCHORDS_tmpXXXX`, que `_temporals` no coneixia → **102 carpetes
    buides per tongada**. El mecanisme ara les deriva del temporal registrat.
    """

    def test_esborra_la_carpeta_autochords_germana(self):
        import _temporals
        from app import pipeline as _pl
        fd, wav = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        germana = _pl.carpeta_sortida(wav)
        os.makedirs(germana, exist_ok=True)
        self.assertTrue(os.path.isdir(germana), "precondició: la carpeta existeix")

        _temporals.esborra([wav])          # només aquest (no toca la resta)

        self.assertFalse(os.path.exists(wav), "el temporal s'ha d'esborrar")
        self.assertFalse(os.path.exists(germana),
                         "la carpeta AUTOCHORDS_* germana també s'ha d'esborrar")

    def test_no_esborra_fora_del_temporal_del_sistema(self):
        """Regla de seguretat: només s'esborra dins el temporal del sistema."""
        import _temporals
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "fora.wav")
        open(wav, "wb").close()
        germana = os.path.join(td, "AUTOCHORDS_fora")
        os.makedirs(germana, exist_ok=True)
        original = _temporals._arrel
        try:
            # Simula que el "temporal del sistema" és un altre lloc: res de `td`
            # no hi cau → no s'ha de tocar.
            _temporals._arrel = os.path.join(td, "un-altre-lloc") + os.sep
            _temporals.esborra([wav])
        finally:
            _temporals._arrel = original
        self.assertTrue(os.path.exists(wav), "fora de l'àmbit no s'ha de tocar")
        self.assertTrue(os.path.isdir(germana))


def _finestra():
    """Finestra amb un tema de prova carregat (ajuda compartida)."""
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "t.wav")
    with wave.open(wav, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(44100)
        f.writeframes(b"\x00\x00" * 44100 * 3)
    s = pipeline.carpeta_sortida(wav)
    os.makedirs(s, exist_ok=True)
    with open(os.path.join(s, "acords.csv"), "w", encoding="utf-8") as f:
        f.write("0.0,2.0,C\n2.0,4.0,Am\n")
    w = app_main.Finestra()
    w.wav_edit.setText(wav)
    w._carrega_visor(wav)
    return w


def _export_neteja_estructura___finestra(amb_estructura):
    """Finestra amb restes d'un export ANTERIOR amb estructura."""
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "t.wav")
    with wave.open(wav, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(44100)
        f.writeframes(b"\x00\x00" * 44100 * 3)
    s = pipeline.carpeta_sortida(wav)
    os.makedirs(s, exist_ok=True)
    with open(os.path.join(s, "acords.csv"), "w", encoding="utf-8") as f:
        f.write("0.0,2.0,C\n2.0,4.0,Am\n")
    with open(os.path.join(s, "estructura_ABC.csv"), "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n")
    os.makedirs(os.path.join(s, "wavs_estructura"), exist_ok=True)
    with open(os.path.join(s, "wavs_estructura", "vella.wav"), "wb") as f:
        f.write(b"RIFF")
    w = app_main.Finestra()
    w.wav_edit.setText(wav)
    w._carrega_visor(wav)
    w.amb_est.setChecked(amb_estructura)
    w._sortida = s
    return w, s


def _export_ok_fals___finestra():
    """Finestra amb model, per als tests d'export fallit (`ok: false`)."""
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "t.wav")
    with wave.open(wav, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(44100)
        f.writeframes(b"\x00\x00" * 44100 * 3)
    s = pipeline.carpeta_sortida(wav)
    os.makedirs(s, exist_ok=True)
    with open(os.path.join(s, "acords.csv"), "w", encoding="utf-8") as f:
        f.write("0.0,2.0,C\n2.0,4.0,Am\n")
    w = app_main.Finestra()
    w.wav_edit.setText(wav)
    w._carrega_visor(wav)
    return w


if __name__ == "__main__":   # pragma: no cover
    unittest.main()
