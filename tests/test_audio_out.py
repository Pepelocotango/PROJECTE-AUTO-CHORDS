"""Tests del motor d'àudio (`app/audio_out.py`, `app/plataforma.py`).

⚠️ **Per què són aquí i no al CI de cada SO**: el motor natiu (`sounddevice`/
PortAudio) només s'executa a macOS/Windows. Com que provar al Mac és car (temps),
aquí fem servir un **`sounddevice` FALS** (`FakeSD`) i **simulem el SO**, de
manera que aquests tests corren a **Linux** (locals i al CI) i caçen bugs de
**concurrència/teardown** (com el `Pa_CloseStream` doble que petava l'app a
macOS) **abans** de compilar.
"""
import os
import subprocess
import sys
import threading
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene dels tests: l'import té efecte (esborra els temporals en plegar)

from app import audio_out, plataforma  # noqa: E402


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
            for _ in range(300):
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
    """Reprodueix el camí EXACTE que petava a macOS: amb l'àudio sonant, canviar
    el BPM/compàs crida `_reenvia_si_sona` → `_atura_proc()` del motor vell +
    `_engega_des_de()` (motor nou), **mentre el fil d'alimentació vell encara
    tancava**. El motor vell s'ha de tancar UN sol cop."""

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

        vell.atura()                        # _reenvia_si_sona: atura el vell
        nou = _motor(fake=fake)             # ...i n'obre un de nou
        aturat.set()
        fil.join(timeout=5)

        self.assertEqual(st_vell.closes, 1, "el motor vell s'ha tancat més d'un cop!")
        self.assertIsNotNone(nou.stream)
        self.assertEqual(nou._fake.creats[-1].closes, 0)
        self.assertIsNone(nou.poll())



def tearDownModule():
    # Neteja ORDENADA dels objectes Qt del mòdul (evita destrucció pel GC en un
    # test posterior -> access violation intermitent). Vegeu tests/_qt_neteja.py.
    try:
        import _qt_neteja
    except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

if __name__ == "__main__":
    unittest.main()
