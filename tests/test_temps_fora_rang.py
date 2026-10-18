"""Regressió del BUG #4 (informe OC-6/341): NO hi havia TOPALL SUPERIOR de temps.

Repro original (app viva, WAV de 199,604 s): `ac_add_chord(250)`,
`ac_move_chord(5,1000)` i `ac_add_section(200,250)` s'acceptaven → l'últim clip
quedava amb durada efectiva <= 0 i l'invariant #4 (suma == durada) ja no es
podia complir. El negatiu SÍ que es rebutjava.

**Decisió**: REBUTJAR (simètric amb el negatiu) en lloc d'acotar en silenci.
A la càrrega, però, el model es REPARA (acords fora de la WAV s'eliminen i el
`fi` d'una última secció que surt s'acota), i el CSV del disc s'hi reescriu.
"""
import csv
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
from PyQt5.QtWidgets import QApplication  # noqa: E402

from app import mcp_bridge, pipeline  # noqa: E402
from app import visor as visor_mod  # noqa: E402

DUR = 40.0


def _escriu_wav(ruta, dur=DUR):
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * int(44100 * dur))


def _llegeix_acords(ruta):
    with open(ruta, encoding="utf-8") as f:
        return [(float(r[0]), r[1]) for r in csv.reader(f) if r]


def _llegeix_abc(ruta):
    files = []
    with open(ruta, encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) < 4 or row[0].startswith("inici"):
                continue
            files.append((float(row[0]), float(row[1]), row[3], row[4]))
    return files


def _visor(acords=((0.0, "C"), (4.0, "G")), seccions=None):
    seccions = seccions or [(0.0, 20.0, "A", "A"), (20.0, DUR, "B", "B")]
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "tema.wav")
    _escriu_wav(wav)
    sortida = pipeline.carpeta_sortida(wav)
    os.makedirs(sortida, exist_ok=True)
    ca = os.path.join(sortida, "acords.csv")
    with open(ca, "w", encoding="utf-8") as f:
        for t, nom in acords:
            f.write(f"{t},{t + 1},{nom}\n")
    if not acords:
        f_empty = open(ca, "w", encoding="utf-8")
        f_empty.close()
    sa = os.path.join(sortida, "estructura_ABC.csv")
    with open(sa, "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n")
        for ini, fi, L, fam in seccions:
            f.write(f"{ini},{fi},{fi - ini},{L},{fam},1.1,2.1\n")
    v = visor_mod.Visor(wav, ca, sa, 120.0, 4, True)
    v.td, v.sortida, v.csv_abc = td, sortida, sa
    return v


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])


class _FinestraFalsa:
    def __init__(self, visor):
        self.visor_ref = visor
        self.sortida = "/tmp/out"

    def windowTitle(self):
        return "Auto Chords — prova"


class TestTopallSuperiorAcords(_Base):
    def test_validador_rebutja_acord_mes_enlla_de_la_wav(self):
        v = _visor()
        with self.assertRaises(ValueError):
            v._valida_canvis_acords([(0.0, "C", "0"),
                                     (1000.0, "G", "1000.0")])

    def test_validador_rebutja_acord_al_final_exacte(self):
        """A la darrera mostra el clip tindria durada 0 → no és un clip."""
        v = _visor()
        with self.assertRaises(ValueError):
            v._valida_canvis_acords([(DUR, "C", "40.0")])

    def test_validador_accepta_el_darrer_acord_dins_la_wav(self):
        v = _visor()
        ok = v._valida_canvis_acords([(0.0, "C", "0"),
                                      (DUR - 0.01, "G", "39.99")])
        self.assertEqual(len(ok), 2)


class TestTopallSuperiorSeccions(_Base):
    def test_validador_rebutja_seccio_que_surt_de_la_wav(self):
        v = _visor()
        with self.assertRaises(ValueError):
            v._valida_canvis_seccions([(0.0, 10.0, "A", "A"),
                                       (20.0, 250.0, "B", "B")])

    def test_validador_accepta_fi_igual_a_la_durada(self):
        v = _visor()
        self.assertEqual(
            len(v._valida_canvis_seccions([(0.0, DUR, "A", "A")])), 1)


class TestCamiMCP(_Base):
    """Repro exacte d'OC-6: les 3 operacions MCP han de sortir REBUTJADES."""

    def _ctx(self, v):
        return mcp_bridge._Context(_FinestraFalsa(v))

    def test_add_chord_fora_de_la_wav(self):
        v = _visor()
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_add_chord(self._ctx(v), {"t_s": 250.0, "acord": "C"})

    def test_move_chord_fora_de_la_wav(self):
        v = _visor()
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_move_chord(self._ctx(v), {"index": 0, "t_s": 1000.0})

    def test_add_section_fora_de_la_wav(self):
        v = _visor()
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_add_section(self._ctx(v),
                                       {"ini_s": 200.0, "fi_s": 250.0})

    def test_l_estat_no_canvia_despres_del_rebuig(self):
        v = _visor()
        abans_a, abans_s = list(v.acords), list(v.seccions)
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_add_chord(self._ctx(v), {"t_s": 250.0, "acord": "X"})
        self.assertEqual(v.acords, abans_a)
        self.assertEqual(v.seccions, abans_s)


class TestCarregaAmbTempsFora(_Base):
    def test_acords_fora_de_la_wav_s_eliminen_i_el_disc_queda_net(self):
        v = _visor(acords=((0.0, "C"), (4.0, "G"), (250.0, "X")))
        self.assertNotIn("X", [a[2][0] for a in v.acords])
        self.assertAlmostEqual(max(float(a[0]) for a in v.acords), 4.0, places=6)
        self.assertNotIn("X", [nom for _t, nom in _llegeix_acords(v.csv_acords)])

    def test_una_seccio_que_surt_de_la_wav_s_acota_en_carregar(self):
        v = _visor(seccions=[(0.0, 10.0, "A", "A"), (10.0, 999.0, "B", "B")])
        self.assertAlmostEqual(float(v.seccions[-1][1]), DUR, places=3)
        self.assertAlmostEqual(float(_llegeix_abc(v.csv_abc)[-1][1]), DUR,
                               places=3)



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
