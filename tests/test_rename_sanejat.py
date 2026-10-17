"""Regressió: el sanejat del nom d'acord (tots els camins) i el símbol musical.

`visor._afegeix_acord` ja netejava el nom, però el rename —pel MCP
(`ac_rename_chord`) i per l'editor de la GUI— hi passava el text CRU.

CANVI DE CRITERI (2026-10-15): el xifrat és **notació musical** i es conserva
tal qual (`/` per a l'acord amb baix, `-` de menor, `#`, `b`…). Només es
netejen caràcters de control i espais sobrers. La seguretat per als noms de
FITXER la garanteix `pipeline.safe_filename`, que l'export aplica pel seu
compte (`A7/G` → `A7_G.wav`). Abans el sanejat del MODEL també tocava `/`, i
això impedia escriure acords amb baix.
"""
import csv
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtWidgets import QApplication  # noqa: E402

from app import mcp_bridge, pipeline  # noqa: E402
from app import visor as visor_mod  # noqa: E402

DUR = 40.0
BRUT = "  A7/G  "        # espais sobrers → es netegen
NET = "A7/G"             # però el SÍMBOL es conserva (baix amb `/` inclòs)


def _visor():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "tema.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * int(44100 * DUR))
    sortida = pipeline.carpeta_sortida(wav)
    os.makedirs(sortida, exist_ok=True)
    ca = os.path.join(sortida, "acords.csv")
    with open(ca, "w", encoding="utf-8") as f:
        f.write("0.0,4.0,C\n4.0,15.0,Am\n")
    sa = os.path.join(sortida, "estructura_ABC.csv")
    with open(sa, "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n")
        f.write(f"0.00,{DUR},{DUR},A,A,1,1\n")
    v = visor_mod.Visor(wav, ca, sa, 120.0, 4, True)
    v.td, v.sortida = td, sortida
    return v


def _csv_acords(v):
    with open(v.csv_acords, encoding="utf-8") as f:
        return [(float(r[0]), r[2]) for r in csv.reader(f) if r]


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


class TestSanejatCanonic(_Base):
    def test_forma_canonica(self):
        """Tots els camins desen en la MATEIXA notació canònica d'acord.

        Menor `-`, major sense marca, `Maj7`, `-7`, `-7b5`… (`app/xifrat.py`).
        """
        for brut, net in [("C", "C"), ("C#m7", "C#-7"), ("N", "N"),
                          ("Am/G", "A-/G"), ("A-7/G", "A-7/G"),
                          ("Amaj7", "AMaj7"), ("Bø", "B-7b5"),
                          ("Cmaj", "C"), ("F#dim7", "F#dim7"),
                          ("  C  ", "C")]:
            self.assertEqual(pipeline.saneja_nom_acord(brut), net, brut)

    def test_nom_buit(self):
        self.assertEqual(pipeline.saneja_nom_acord("   "), "")


class TestRenameMCP(_Base):
    def test_rename_saneja_el_nom(self):
        v = _visor()
        ctx = mcp_bridge._Context(_FinestraFalsa(v))
        mcp_bridge._op_rename_chord(ctx, {"index": 1, "acord": BRUT})
        self.assertEqual(v.acords[1][2][0], NET)
        self.assertEqual(_csv_acords(v)[1][1], NET)   # i al CSV del disc

    def test_nom_que_queda_buit_es_rebutja(self):
        v = _visor()
        ctx = mcp_bridge._Context(_FinestraFalsa(v))
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_rename_chord(ctx, {"index": 1, "acord": "   "})


class TestRenameEditor(_Base):
    def test_editor_saneja_el_nom(self):
        v = _visor()
        v._ed_kind, v._ed_idx = "chord", 1
        v.ed_ini.setText("4.0")
        v.ed_nom.setText(BRUT)
        v._aplica_editor()
        self.assertEqual(v.acords[1][2][0], NET)


class TestRenameInlineTimeline(_Base):
    def test_renom_inline_saneja(self):
        v = _visor()
        v._on_chord_renamed(0, "  A/B  ")
        self.assertEqual(v.acords[0][2][0], "A/B")     # símbol conservat, espais fora

    def test_renom_inline_normal_es_canonicalitza(self):
        v = _visor()
        v._on_chord_renamed(0, "C#m7")
        self.assertEqual(v.acords[0][2][0], "C#-7")    # notació canònica


class TestAltaCoherent(_Base):
    def test_afegeix_acord_usa_el_mateix_sanejat(self):
        v = _visor()
        self.assertTrue(v._afegeix_acord(10.0, BRUT))
        nou = [a[2][0] for a in v.acords if abs(float(a[0]) - 10.0) < 1e-6]
        self.assertEqual(nou, [NET])



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
