"""Tests dels valors per defecte del diàleg d'autodetecció (`app/dialegs.py`).

Blinda la decisió de l'operador (2026-10-13): els defectes de fàbrica que
mostra el diàleg en obrir-lo i als quals torna el botó «Restaura per defecte».
Si algú els canvia sense voler, el CI peta.
"""
import copy
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import dialegs  # noqa: E402

# Els 19 controls revisats amb l'operador (font única d'aquest acord).
ESPERATS = {
    "bpm": {"motor": "consens", "min": 60, "max": 180,
            "pref_min": 85, "pref_max": 150},
    "chords": {"useNNLS": 1, "useHMM": 1, "rollon": 0.0, "tuningmode": 0,
               "whitening": 1.0, "s": 0.7},
    "structure": {"motor": "qm", "durada_min": 2.0, "fusiona_iguals": True},
    "clean": {"durada_min": 0.15, "fusiona_iguals": True, "sense_baix": False,
              "reduir": False, "snap": True, "divisio": 2, "ritme": "off"},
}


class TestDefectes(unittest.TestCase):
    def test_defectes_fixats(self):
        self.assertEqual(dialegs.DEFECTES, ESPERATS)

    def test_carrega_opcions_sense_fitxer(self):
        antic = dialegs.FITXER_OPCIONS
        dialegs.FITXER_OPCIONS = os.path.join(
            tempfile.gettempdir(), "opcions_que_no_existeix_mai.json")
        try:
            self.assertEqual(dialegs.carrega_opcions(), ESPERATS)
        finally:
            dialegs.FITXER_OPCIONS = antic

    def test_carrega_opcions_merge_parcial(self):
        antic = dialegs.FITXER_OPCIONS
        fd, tmp = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"bpm": {"motor": "qm"}}, f)
        dialegs.FITXER_OPCIONS = tmp
        try:
            op = dialegs.carrega_opcions()
            self.assertEqual(op["bpm"]["motor"], "qm")      # sobreescrit
            self.assertEqual(op["bpm"]["min"], 60)          # de defecte
            self.assertEqual(op["clean"], ESPERATS["clean"])
        finally:
            dialegs.FITXER_OPCIONS = antic
            os.unlink(tmp)


class TestDialogDefectes(unittest.TestCase):
    def setUp(self):
        # Offscreen si no hi ha pantalla (CI/headless); no força res si n'hi ha.
        if not os.environ.get("DISPLAY") and not os.environ.get("QT_QPA_PLATFORM"):
            os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PyQt5.QtWidgets import QApplication
        self._app = QApplication.instance() or QApplication([])

    def test_el_dialeg_mostra_els_defectes(self):
        dlg = dialegs.DialegOpcions(opcions=copy.deepcopy(dialegs.DEFECTES))
        self.assertEqual(dlg.opcions(), ESPERATS)

    def test_restaura_torna_als_defectes(self):
        dlg = dialegs.DialegOpcions(opcions=copy.deepcopy(dialegs.DEFECTES))
        # embrutem uns quants controls...
        b = dlg._controls["bpm"]
        b["motor"].setCurrentIndex(b["motor"].findData("qm"))
        b["min"].setValue(80)
        c = dlg._controls["clean"]
        c["snap"].setChecked(False)
        c["divisio"].setValue(4)
        c["durada_min"].setValue(0.0)
        cl_chord = dlg._controls["chords"]["useHMM"]
        cl_chord.setChecked(False)
        dlg._controls["structure"]["durada_min"].setValue(0.0)
        # ...i premem «Restaura per defecte» → tot torna a DEFECTES
        dlg._restaura()
        self.assertEqual(dlg.opcions(), ESPERATS)


if __name__ == "__main__":
    unittest.main()
