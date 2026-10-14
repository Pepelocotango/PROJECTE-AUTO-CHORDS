"""A3: el diàleg «Ajuda ▸ Dreceres de teclat» ha de llistar TOTES les reals.

Abans en llistava **6** (Espai, Ctrl+Z/Y/Shift+Z, roda, botó dret, regle, clic) i
en faltaven moltes d'actives (Ctrl+O/E, F5, Ctrl+D, Del, F2, Ctrl+C/X/V,
Ctrl+`[`/`]`, Ctrl+0/±…). Ara les de **menú** es dedueixen dels menús REALS i les
que no hi són (teclat del visor i ratolí) van llistades a part.
"""
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from app import main as app_main  # noqa: E402


def _finestra():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "t.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * 5)
    w = app_main.Finestra()
    w.wav_edit.setText(wav)
    w._carrega_visor(wav)
    return w


class TestDreceresCompletes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = app_main.QApplication.instance() or app_main.QApplication([])

    def test_totes_les_dreceres_de_menu_hi_surten(self):
        """El test mecànic: cap acció de menú amb drecera pot quedar fora."""
        w = _finestra()
        text = w._text_dreceres()
        faltes = []
        for accio in w.menuBar().actions():
            menu = accio.menu()
            if menu is None:
                continue
            for a in menu.actions():
                if a.isSeparator() or a.menu() is not None:
                    continue
                d = a.shortcut().toString()
                if d and d not in text:
                    faltes.append(f"{a.text().replace('&', '')} ({d})")
        self.assertEqual(faltes, [],
                         f"dreceres de menú que NO surten al diàleg: {faltes}")

    def test_hi_son_les_que_no_son_de_menu(self):
        w = _finestra()
        text = w._text_dreceres()
        for d in ("Espai", "T", "Ctrl+C", "Ctrl+X", "Ctrl+V",
                  "Roda del ratolí", "Botó dret"):
            self.assertIn(d, text, f"falta la drecera «{d}»")

    def test_les_dreceres_abans_faltaven(self):
        """Les que el diàleg antic no llistava (regressió explícita)."""
        w = _finestra()
        text = w._text_dreceres()
        for d in ("Ctrl+O", "Ctrl+E", "F5", "Ctrl+D", "Del", "F2",
                  "Ctrl+[", "Ctrl+]"):
            self.assertIn(d, text, f"encara falta «{d}»")

    def test_amb_el_pont_actiu_es_no_modal(self):
        """(3) Amb el pont MCP actiu, el diàleg de dreceres NO pot ser modal
        (encallaria el pont fins que algú el tanqués)."""
        from unittest.mock import patch
        import PyQt5.QtWidgets as QW
        w = _finestra()
        w.mcp_actiu = True
        with patch.object(QW.QMessageBox, "information") as modal, \
                patch.object(QW.QMessageBox, "show", lambda self: None):
            w._mostra_dreceres()
        self.assertFalse(modal.called, "amb el pont no pot haver-hi modal")

    def test_el_dialeg_no_peta(self):
        from unittest.mock import patch
        import PyQt5.QtWidgets as QW
        w = _finestra()
        with patch.object(QW.QMessageBox, "information", return_value=None) as m:
            w._mostra_dreceres()
        self.assertTrue(m.called)


if __name__ == "__main__":
    unittest.main()
