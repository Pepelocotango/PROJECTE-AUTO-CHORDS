"""A1: Desfer/Refer també ha de cobrir BPM, compàs, offset, mode i loop A-B.

Abans `Visor._estat_edicio()` només desava `(acords, seccions)`: canviar el BPM
o el loop era **irreversible** (Desfer no hi feia res). Ara la pila del
desfer/refer apila `(acords, seccions, temps)` amb `_estat_complet()`, i els
camins que canvien la graella o el loop hi marquen l'operació.
"""
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
from app import main as app_main  # noqa: E402
from app import visor as visor_mod  # noqa: E402


def _finestra():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "t.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * 30)
    ac = os.path.join(td, "AUTOCHORDS_t")
    os.makedirs(ac)
    with open(os.path.join(ac, "acords.csv"), "w", encoding="utf-8") as f:
        f.write("0.0,4.0,C\n4.0,30.0,Am\n")
    with open(os.path.join(ac, "estructura_ABC.csv"), "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
                "0.00,15.00,15.00,A,A,1,1\n15.00,30.00,15.00,B,B,1,1\n")
    w = app_main.Finestra()
    w.wav_edit.setText(wav)
    w._carrega_visor(wav)
    return w


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])


class TestUndoTemps(_Base):
    def test_canviar_el_bpm_es_pot_desfer(self):
        w = _finestra()
        v = w.visor_ref
        self.assertAlmostEqual(float(v.bpm), 120.0, places=3)
        w.bpm.setText("101")
        w._aplica_parametres_temps()
        self.assertAlmostEqual(float(v.bpm), 101.0, places=3)
        w._undo_visor()
        self.assertAlmostEqual(float(v.bpm), 120.0, places=3,
                               msg="el BPM no s'ha desfet")
        # i el camp de la barra queda sincronitzat amb el visor
        self.assertAlmostEqual(float(w.bpm.text()), 120.0, places=3)

    def test_canviar_l_offset_es_pot_desfer(self):
        w = _finestra()
        v = w.visor_ref
        w.offset.setText("1.5")
        w._aplica_parametres_temps()
        self.assertAlmostEqual(float(v.offset), 1.5, places=3)
        w._undo_visor()
        self.assertAlmostEqual(float(v.offset), 0.0, places=3)
        self.assertAlmostEqual(float(w.offset.text()), 0.0, places=3)

    def test_canviar_el_compas_es_pot_desfer(self):
        w = _finestra()
        v = w.visor_ref
        w.bpb.setText("3")
        w._aplica_parametres_temps()
        self.assertEqual(int(v.bpb), 3)
        w._undo_visor()
        self.assertEqual(int(v.bpb), 4)

    def test_activar_el_loop_es_pot_desfer(self):
        w = _finestra()
        v = w.visor_ref
        v.loop_a, v.loop_b = 2.0, 6.0
        v.set_loop(True)
        self.assertTrue(v.loop_on)
        w._undo_visor()
        self.assertFalse(v.loop_on, "l'activació del loop no s'ha desfet")
        self.assertFalse(w.tb_loop.isChecked())

    def test_rang_de_loop_es_pot_desfer(self):
        w = _finestra()
        v = w.visor_ref
        v._on_loop_changed(2.0, 6.0)          # com en acabar d'arrossegar el regle
        self.assertAlmostEqual(v.loop_a, 2.0, places=3)
        w._undo_visor()
        self.assertIsNone(v.loop_a)
        self.assertIsNone(v.loop_b)

    def test_el_desfer_del_model_encara_funciona(self):
        """No regressió + bug trobat: l'alta des del MENÚ no marcava undo."""
        from unittest.mock import patch
        import PyQt5.QtWidgets as QW
        w = _finestra()
        v = w.visor_ref
        n = len(v.acords)
        with patch.object(QW.QInputDialog, "getText", return_value=("G", True)):
            v.ves_a(10.0)
            w._afegeix_acord_ui()
        self.assertEqual(len(v.acords), n + 1)
        w._undo_visor()
        self.assertEqual(len(v.acords), n,
                         "l'alta des del menú no era desfer-able")

    def test_afegir_seccio_des_del_menu_es_desfe(self):
        from unittest.mock import patch
        import PyQt5.QtWidgets as QW
        w = _finestra()
        v = w.visor_ref
        v.seccions = []               # sense res: hi ha espai per afegir-hi
        v.timeline.set_data(v.acords, v.seccions)
        v._undo_commit()              # consolida aquest estat com a base
        with patch.object(QW.QInputDialog, "getText", return_value=("X", True)):
            v.ves_a(10.0)
            w._afegeix_seccio_ui()
        self.assertEqual(len(v.seccions), 1)
        w._undo_visor()
        self.assertEqual(len(v.seccions), 0)

    def test_la_descripcio_esmenta_el_canvi_de_temps(self):
        w = _finestra()
        v = w.visor_ref
        abans = v._estat_complet()
        v.bpm = 101.0
        ara = v._estat_complet()
        self.assertIn("BPM", v._descriu_canvi(abans, ara))
        # i el contracte del pont MCP (2-tuple) no ha canviat
        self.assertEqual(len(v._estat_edicio()), 2)



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
