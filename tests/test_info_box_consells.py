"""Caixa d'informacio: quan el ratoli NO es sobre cap boto/area amb info, ha de
mostrar un **rotatori de dreceres i consells** (panells que giren cada ~8 s).

Es el complement del «ratoli intel·ligent»: si hi ha info concreta s'explica; si
no, la caixa no queda morta ni amb un text vell.
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


class TestInfoBoxConsells(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = app_main.QApplication.instance() or app_main.QApplication([])

    def test_panells_inclouen_consells_i_dreceres(self):
        w = _finestra()
        panells = w._info_panells()
        # 1r = consells; la resta = grups de dreceres reals dels menus.
        self.assertGreaterEqual(len(panells), 2)
        self.assertEqual(panells[0][0], "Consells rapids")
        titols = [t for t, _p in panells]
        self.assertIn("Fitxer", titols)
        w.close()

    def test_html_per_defecte_porta_dreceres_reals(self):
        w = _finestra()
        n = len(w._info_panells())
        vist = ""
        for i in range(n):
            w._info_panell = i
            vist += w._info_defecte_html(1.0, rota=False) or ""
        self.assertIn("Dreceres i consells", vist)
        self.assertIn("Ctrl+O", vist)      # Fitxer ▸ Obre àudio
        self.assertIn("Ctrl+Z", vist)      # Edita ▸ Desfer
        self.assertIn("F5", vist)          # Analitza l'àudio
        w.close()

    def test_rota_cada_8_segons(self):
        w = _finestra()
        n = len(w._info_panells())
        w._info_panell = 0
        w._info_panell_t = 0.0
        h0 = w._info_defecte_html(100.0, rota=True)     # fixa t0, sense rotar
        h1 = w._info_defecte_html(105.0, rota=True)     # < 8 s → igual
        self.assertEqual(h0, h1)
        h2 = w._info_defecte_html(110.0, rota=True)     # >= 8 s → avança
        self.assertNotEqual(h1, h2)
        self.assertEqual(w._info_panell, 1 % n)
        w.close()

    def test_no_rota_si_el_ratoli_es_a_la_caixa(self):
        w = _finestra()
        w._info_panell = 0
        w._info_panell_t = 0.0
        w._info_defecte_html(100.0, rota=True)
        w._info_defecte_html(200.0, rota=False)         # congelat
        self.assertEqual(w._info_panell, 0)
        w.close()

    def test_posa_info_nomes_reescriu_si_canvia(self):
        w = _finestra()
        w._info_html_actual = None
        w._posa_info("<b>hola</b>")
        self.assertEqual(w._info_html_actual, "<b>hola</b>")
        w.info_box.setPlainText("no m'has de tocar")
        w._posa_info("<b>hola</b>")                     # mateix → no reescriu
        self.assertEqual(w.info_box.toPlainText(), "no m'has de tocar")
        w._posa_info("<b>hola</b>2")                    # diferent → reescriu
        self.assertIn("hola", w.info_box.toPlainText())
        w.close()


if __name__ == "__main__":
    unittest.main()
