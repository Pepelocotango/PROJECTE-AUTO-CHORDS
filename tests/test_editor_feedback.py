"""L'editor de la franja Editor NO pot fallar en silenci (OC-6/394).

Sis camins de `_aplica_editor` tornaven sense aplicar RES i sense dir res: el
botó «Aplica» semblava mort (CSV intacte, cap 'editor:' al log). Ara tots els
camins que no apliquen donen feedback visible (`avis_editor` → log + caixa
d'informació).
"""
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from app import pipeline  # noqa: E402
from app import visor as visor_mod  # noqa: E402


def _visor():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "t.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * 20)
    s = pipeline.carpeta_sortida(wav)
    os.makedirs(s, exist_ok=True)
    ca = os.path.join(s, "acords.csv")
    with open(ca, "w", encoding="utf-8") as f:
        f.write("0.0,C\n4.0,Am\n")
    sa = os.path.join(s, "estructura_ABC.csv")
    with open(sa, "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
                "0.00,10.00,10.00,A,A,1,1\n10.00,20.00,10.00,B,B,1,1\n")
    v = visor_mod.Visor(wav, ca, sa, 120.0, 4, True)
    v._missatges = []
    v.infoMissatge.connect(v._missatges.append)
    return v


class TestEditorFeedback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])

    def test_sense_seleccio_avisa(self):
        v = _visor()
        v._ed_kind, v._ed_idx = None, -1
        v._aplica_editor()
        self.assertTrue(any("Selecciona" in m for m in v._missatges),
                        f"hauria d'avisar: {v._missatges}")

    def test_inici_no_numeric_avisa(self):
        v = _visor()
        v._ed_kind, v._ed_idx = "chord", 1
        v.ed_ini.setText("abc")
        v.ed_nom.setText("Am")
        v._aplica_editor()
        self.assertTrue(any("número" in m for m in v._missatges),
                        f"hauria d'avisar: {v._missatges}")
        self.assertEqual(v.acords[1][1], "Am", "no s'ha d'haver aplicat res")

    def test_nom_buit_avisa(self):
        v = _visor()
        v._ed_kind, v._ed_idx = "chord", 1
        v.ed_ini.setText("4.0")
        v.ed_nom.setText("   ")
        v._aplica_editor()
        self.assertTrue(any("nom" in m for m in v._missatges))

    def test_index_esborrat_avisa(self):
        v = _visor()
        v._ed_kind, v._ed_idx = "section", 99
        v.ed_ini.setText("4.0")
        v.ed_nom.setText("X")
        v._aplica_editor()
        self.assertTrue(any("no existeix" in m for m in v._missatges))

    def test_validacio_que_falla_es_visible(self):
        """Un canvi que trenca la lògica temporal s'ha de VEURE, no només al log."""
        v = _visor()
        v._ed_kind, v._ed_idx = "chord", 1
        v.ed_nom.setText("Am")
        v.ed_ini.setText("0.0")          # xocaria amb el 1r acord (t=0)
        v._aplica_editor()
        self.assertTrue(any("invalid" in m for m in v._missatges),
                        f"hauria d'avisar: {v._missatges}")

    def test_el_cami_bon_aplica_i_no_avisa(self):
        v = _visor()
        v._ed_kind, v._ed_idx = "chord", 1
        v.ed_nom.setText("Gmaj7")
        v.ed_ini.setText("4.00")
        v._aplica_editor()
        self.assertEqual(v.acords[1][1], "GMaj7", "hauria d'haver aplicat")
        self.assertEqual(v._missatges, [], "el camí bo no ha d'avisar")



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
