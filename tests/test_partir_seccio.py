"""A2: PARTIR una secció.

En un model saturat —les seccions cobreixen TOTA la WAV (regla d'or #4)— el
menú «Afegeix secció» no pot afegir res (qualsevol secció nova solaparia). La
manera natural d'afegir-ne una de nova és **partir** la que hi ha al punt del
cursor: `Visor.parteix_seccio()` (+ l'acció de menú i el menú contextual).
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

from app import main as app_main  # noqa: E402
from app import pipeline  # noqa: E402
from app import visor as visor_mod  # noqa: E402

DUR = 30.0
SECCIONS = [(0.0, 10.0, "A", "A"), (10.0, DUR, "B", "B")]


def _escriu_wav(ruta, dur=DUR):
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * int(44100 * dur))


def _llegeix_abc(ruta):
    files = []
    with open(ruta, encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) < 4 or row[0].startswith("inici"):
                continue
            files.append((float(row[0]), float(row[1]), row[3], row[4]))
    return files


def _visor(seccions=None):
    seccions = SECCIONS if seccions is None else seccions
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "tema.wav")
    _escriu_wav(wav)
    sortida = pipeline.carpeta_sortida(wav)
    os.makedirs(sortida, exist_ok=True)
    ca = os.path.join(sortida, "acords.csv")
    with open(ca, "w", encoding="utf-8") as f:
        f.write("0.0,C\n4.0,Am\n")
    sa = os.path.join(sortida, "estructura_ABC.csv")
    with open(sa, "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n")
        for ini, fi, L, fam in seccions:
            f.write(f"{ini},{fi},{fi - ini},{L},{fam},1,1\n")
    v = visor_mod.Visor(wav, ca, sa, 120.0, 4, True)
    v.td, v.sortida, v.abc_csv = td, sortida, sa
    return v


def _finestra():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "t.wav")
    _escriu_wav(wav)
    ac = os.path.join(td, "AUTOCHORDS_t")
    os.makedirs(ac)
    with open(os.path.join(ac, "acords.csv"), "w", encoding="utf-8") as f:
        f.write("0.0,C\n4.0,Am\n")
    with open(os.path.join(ac, "estructura_ABC.csv"), "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n")
        for ini, fi, L, fam in SECCIONS:
            f.write(f"{ini},{fi},{fi - ini},{L},{fam},1,1\n")
    w = app_main.Finestra()
    w.wav_edit.setText(wav)
    w._carrega_visor(wav)
    return w


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])


class TestPartirSeccio(_Base):
    def test_parteix_en_dos_trossos(self):
        v = _visor()
        self.assertEqual(v.parteix_seccio(0, 4.0, "Z"), 1)
        self.assertEqual([s[2] for s in v.seccions], ["A", "Z", "B"])
        self.assertAlmostEqual(v.seccions[0][1], 4.0, places=6)
        self.assertAlmostEqual(v.seccions[1][0], 4.0, places=6)
        self.assertAlmostEqual(v.seccions[1][1], 10.0, places=6)
        # la cobertura (#4) i la contigüitat (#2) es mantenen
        self.assertAlmostEqual(sum(float(b) - float(a) for a, b, _L, _F
                                   in v.seccions), DUR, places=6)

    def test_lletra_i_familia_per_defecte(self):
        v = _visor()
        v.parteix_seccio(1, 20.0)
        self.assertEqual([s[2] for s in v.seccions], ["A", "B", "B"])
        self.assertEqual(v.seccions[2][3], "B", "la família s'ha de conservar")

    def test_fora_de_la_seccio_es_rebutja(self):
        v = _visor()
        self.assertFalse(v.parteix_seccio(0, 12.0, "Z"))
        self.assertEqual(v.seccions, SECCIONS)

    def test_massa_a_prop_de_la_vora_es_rebutja(self):
        v = _visor()
        self.assertFalse(v.parteix_seccio(0, 0.01, "Z"))    # < MIN_SECCIO_S
        self.assertFalse(v.parteix_seccio(0, 9.99, "Z"))
        self.assertEqual(v.seccions, SECCIONS)

    def test_index_invalid(self):
        v = _visor()
        self.assertFalse(v.parteix_seccio(9, 4.0))
        self.assertEqual(v.seccions, SECCIONS)

    def test_es_pot_desfer(self):
        v = _visor()
        v.parteix_seccio(0, 4.0, "Z")
        self.assertEqual(len(v.seccions), 3)
        v.undo()
        self.assertEqual(v.seccions, SECCIONS)


class TestMenuContextual(_Base):
    def test_l_entrada_esta_activa_en_una_seccio(self):
        from PyQt5.QtCore import QPoint
        from PyQt5.QtWidgets import QMenu
        v = _visor()
        capt = {}
        orig = QMenu.exec_

        def fake(self, pos, *a):
            capt["a"] = [(x.text(), x.isEnabled()) for x in self.actions()
                         if not x.isSeparator()]
            return None
        QMenu.exec_ = fake
        try:
            v._on_clip_context_menu("section", 0, QPoint(0, 0))
        finally:
            QMenu.exec_ = orig
        self.assertTrue(dict(capt["a"]).get("Parteix la secció…"),
                        "hauria d'estar activa sobre una secció")


class TestPartirDesDelMenu(_Base):
    def test_el_menu_parteix_al_cursor(self):
        from unittest.mock import patch
        import PyQt5.QtWidgets as QW
        w = _finestra()
        v = w.visor_ref
        v.ves_a(4.0)
        with patch.object(QW.QInputDialog, "getText", return_value=("Z", True)):
            w._parteix_seccio_ui()
        self.assertEqual([s[2] for s in v.seccions], ["A", "Z", "B"])
        self.assertAlmostEqual(float(v.seccions[0][1]), 4.0, places=3)
        # i el CSV d'estructura del disc reflecteix el tall
        self.assertEqual(len(_llegeix_abc(v._carpeta_acords() +
                                          "/estructura_ABC.csv")), 3)

    def test_el_menu_avisa_si_no_hi_ha_seccio_al_cursor(self):
        w = _finestra()
        v = w.visor_ref
        v.seccions = []
        v.timeline.set_data(v.acords, v.seccions)
        v.ves_a(4.0)
        w._parteix_seccio_ui()          # no ha de petar ni canviar res
        self.assertEqual(len(v.seccions), 0)

    def test_es_desfer_des_del_menu(self):
        from unittest.mock import patch
        import PyQt5.QtWidgets as QW
        w = _finestra()
        v = w.visor_ref
        v.ves_a(4.0)
        with patch.object(QW.QInputDialog, "getText", return_value=("Z", True)):
            w._parteix_seccio_ui()
        self.assertEqual(len(v.seccions), 3)
        w._undo_visor()
        self.assertEqual(len(v.seccions), 2)



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
