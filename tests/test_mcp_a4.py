"""A4: exportar la PARTITURA des de l'MCP (i poder incloure-la amb els WAVs).

La partitura era una acció separada de la GUI (`Fitxer ▸ Exporta la partitura…`)
i l'MCP no la podia demanar. Ara hi ha `ac_export_partitura` (sense obrir cap
finestra ni carpeta) i `ac_export_wav` accepta `partitura` per incloure-la en
aquella exportació sense canviar la marca de l'app.
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
from unittest.mock import patch  # noqa: E402

import PyQt5.QtWidgets as QW  # noqa: E402

from app import main as app_main  # noqa: E402
from app import mcp_bridge  # noqa: E402
from app import pipeline  # noqa: E402


def _finestra():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "t.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * 3)
    w = app_main.Finestra()
    w.wav_edit.setText(wav)
    w._carrega_visor(wav)
    return w


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QW.QApplication.instance() or QW.QApplication([])

    def ctx(self, w):
        return mcp_bridge._Context(w)


class TestExportPartitura(_Base):
    def test_sense_carpeta_de_sortida_es_rebutja(self):
        w = _finestra()
        w.sortida = ""
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_export_partitura(self.ctx(w), {})

    def test_sense_locators_es_rebutja_amb_missatge(self):
        w = _finestra()
        w.sortida = tempfile.mkdtemp()
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_export_partitura(self.ctx(w), {})

    def test_locators_vells_es_regeneren(self):
        """Bug: exportar NOMÉS la partitura reutilitzava els locators VELLS.

        La partitura es construeix a partir de `acords_locators.txt`, que és un
        DERIVAT del model. Si el CSV s'ha editat després de l'últim export de
        WAVs, els locators del disc són vells i la partitura sortia amb els
        acords antics.
        """
        w = _finestra()
        sortida = pipeline.carpeta_sortida(w.wav_edit.text().strip())
        w.sortida = sortida
        os.makedirs(sortida, exist_ok=True)
        csv_ac = os.path.join(sortida, "acords.csv")
        with open(csv_ac, "w", encoding="utf-8") as f:
            f.write("0.0,4.0,C\n")
        loc = os.path.join(sortida, "acords_locators.txt")
        with open(loc, "w", encoding="utf-8") as f:
            f.write("posició acord durada\n")
        os.utime(loc, (os.path.getmtime(csv_ac) - 60,) * 2)   # locators VELLS
        with patch.object(pipeline, "run_acords_py") as m:
            self.assertTrue(w._assegura_locators())
            m.assert_called_once()
        os.utime(loc, None)          # com si s'haguessin reescrit
        with patch.object(pipeline, "run_acords_py") as m2:
            self.assertTrue(w._assegura_locators())
            m2.assert_not_called()   # ja estan al dia → no es toca res

    def test_retorna_els_camins_generats(self):
        w = _finestra()
        w.sortida = tempfile.mkdtemp()
        fals = {"musicxml": "/x/a.musicxml", "pdf": "/x/a.pdf",
                "mscz": "/x/a.mscz"}
        with patch.object(w, "_exporta_partitura", return_value=fals):
            r = mcp_bridge._op_export_partitura(self.ctx(w), {})
        self.assertTrue(r.get("ok"))
        self.assertEqual(r.get("musicxml"), "/x/a.musicxml")
        self.assertEqual(r.get("pdf"), "/x/a.pdf")
        self.assertIn("MusicXML", r.get("missatge", ""))

    def test_no_obre_cap_finestra_ni_carpeta(self):
        w = _finestra()
        w.sortida = tempfile.mkdtemp()
        with patch.object(w, "_exporta_partitura",
                          return_value={"musicxml": "/x/a.musicxml"}), \
                patch.object(w, "obre_carpeta") as ob, \
                patch.object(QW.QMessageBox, "information") as inf:
            mcp_bridge._op_export_partitura(self.ctx(w), {})
        self.assertFalse(ob.called, "no ha d'obrir carpetes")
        self.assertFalse(inf.called, "no ha de mostrar diàlegs")


class TestExportWavAmbPartitura(_Base):
    def test_partitura_true_inclou_la_partitura_i_restaura_la_marca(self):
        w = _finestra()
        vist = {}
        with patch.object(w, "exporta", lambda: vist.update(
                durant=w.amb_part.isChecked())):
            mcp_bridge._op_export_wav(self.ctx(w), {"partitura": True})
        self.assertTrue(vist.get("durant"), "durant l'export havia d'estar ON")
        self.assertFalse(w.amb_part.isChecked(), "la marca s'ha de restaurar")

    def test_partitura_false_la_treu_nomes_durant_l_export(self):
        w = _finestra()
        w.amb_part.setChecked(True)
        vist = {}
        with patch.object(w, "exporta", lambda: vist.update(
                durant=w.amb_part.isChecked())):
            mcp_bridge._op_export_wav(self.ctx(w), {"partitura": False})
        self.assertFalse(vist.get("durant"))
        self.assertTrue(w.amb_part.isChecked(), "la marca s'ha de restaurar")

    def test_sense_el_parametre_no_toca_la_marca(self):
        w = _finestra()
        w.amb_part.setChecked(True)
        with patch.object(w, "exporta"):
            mcp_bridge._op_export_wav(self.ctx(w), {})
        self.assertTrue(w.amb_part.isChecked())



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
