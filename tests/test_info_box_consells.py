"""Caixa d'informacio: quan el ratoli NO es sobre cap boto/area amb info, ha de
mostrar un **rotatori de consells i dreceres** (panells que giren cada
`_INFO_ROTACIO_S`), amb el 1r panell **adaptat a l'eina vigent** del timeline.

Tambe cobreix la interaccio: un **clic** a la caixa **para** el rotatori
(`_INFO_PAUSA_S`) i el clic següent **avanca** de «pantalla».

Es el complement del «ratoli intel·ligent»: si hi ha info concreta s'explica; si
no, la caixa no queda morta ni amb un text vell.
"""
import os
import sys
import tempfile
import time
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

    def test_panells_inclouen_eina_consells_i_dreceres(self):
        w = _finestra()
        panells = w._info_panells()
        # 1r = eina del timeline; 2n = consells; la resta = dreceres reals.
        self.assertGreaterEqual(len(panells), 3)
        self.assertTrue(panells[0][0].startswith("Eina del timeline"))
        titols = [t for t, _p in panells]
        self.assertIn("Consells rapids", titols)
        self.assertIn("Fitxer", titols)
        w.close()

    def test_panell_eina_segueix_l_eina_vigent(self):
        w = _finestra()
        w.visor_ref.timeline.set_tool("marc")
        t_marc, _p = w._panell_eina()
        self.assertIn("MARC", t_marc)
        w.visor_ref.timeline.set_tool("intel·ligent")
        t_int, _p = w._panell_eina()
        self.assertIn("intel·ligent", t_int)
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

    def test_rota_segons_el_interval_configurat(self):
        w = _finestra()
        n = len(w._info_panells())
        w._info_panell = 0
        w._info_panell_t = 0.0
        w._info_pausa_fins = 0.0
        inc = app_main._INFO_ROTACIO_S
        h0 = w._info_defecte_html(100.0, rota=True)                 # fixa t0
        h1 = w._info_defecte_html(100.0 + inc - 1.0, rota=True)     # encara no
        self.assertEqual(h0, h1)
        h2 = w._info_defecte_html(100.0 + inc + 0.1, rota=True)     # ara sí
        self.assertNotEqual(h1, h2)
        self.assertEqual(w._info_panell, 1 % n)
        w.close()

    def test_no_rota_si_el_ratoli_es_a_la_caixa(self):
        w = _finestra()
        w._info_panell = 0
        w._info_panell_t = 0.0
        w._info_pausa_fins = 0.0
        w._info_defecte_html(100.0, rota=True)
        w._info_defecte_html(200.0, rota=False)         # congelat
        self.assertEqual(w._info_panell, 0)
        w.close()

    def test_clic_pausa_i_el_seguent_avanca(self):
        """1r clic → PARA (i allarga la pausa); 2n clic → AVANÇA de pantalla."""
        w = _finestra()
        w._info_timer.stop()          # aillament: que no dispari el rotatori
        w._info_panell = 0
        w._info_panell_t = time.monotonic() - 100.0   # vell (ja tocaria rotar)
        w._info_pausa_fins = 0.0
        w._clic_info_box()                            # 1r: pausa, no avança
        self.assertGreater(w._info_pausa_fins, time.monotonic())
        self.assertEqual(w._info_panell, 0)
        w._clic_info_box()                            # 2n: avança
        self.assertEqual(w._info_panell, 1)
        # Dins la pausa (encara que passi estona), el rotatori NO es mou sol.
        w._info_defecte_html(time.monotonic() + app_main._INFO_PAUSA_S - 5.0,
                             rota=True)
        self.assertEqual(w._info_panell, 1)
        w.close()

    def test_missatge_transitori_te_format_propi(self):
        w = _finestra()
        w._missatge_info("PROVA")
        txt = w.info_box.toPlainText()
        self.assertIn("PROVA", txt)
        self.assertIn("Missatge", txt)      # banner distint del rotatori
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
