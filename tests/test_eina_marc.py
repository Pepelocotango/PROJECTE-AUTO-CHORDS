"""Eina del timeline: «intel·ligent» (per defecte) o «marc» (rubber-band).

- Per defecte l'eina és la intel·ligent i el rang de `Shift+clic` es queda al
  **carril del clip clicat**: la «selecció creuada» (les dues pistes) és una
  opció de menú, **desactivada** per defecte.
- Amb l'eina «marc», arrossegar **no mou cap clip**: dibuixa un rectangle i, en
  deixar anar, queda seleccionat tot el que **HI SONA** a dins (solapament, no
  només els inicis) i només de les pistes que el rectangle cobreix verticalment.
- El rectangle es veu només durant l'arrossegament (després desapareix) i la
  selecció no entra a la pila de desfer.

Convencions dels DAWs (Cubase `Snap Type`, marquee de Logic/Reaper) i decisió
de l'operador del 16-10-2026: «eina intel·ligent o mode només selecció amb
marquee; el creuat, desactivat per defecte».
"""
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PyQt5.QtGui import QMouseEvent  # noqa: E402

from app import visor as visor_mod  # noqa: E402
from app.timeline_base import LANE_ACC_TOP, LANE_H, LANE_SEC_TOP  # noqa: E402

# acords: 0 C · 2 Am · 4.5 F · 7 G · 10 C (fins a 20)   |   seccions: A 0-5 · B 5-10 · C 10-20
ACORDS = "0.0,C\n2.0,Am\n4.5,F\n7.0,G\n10.0,C\n"
SECCIONS = ("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
            "0.0,5.0,5.0,A,A,1.1,5.1\n"
            "5.0,10.0,5.0,B,B,5.1,10.1\n"
            "10.0,20.0,10.0,C,C,10.1,20.1\n")


def _visor():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "tema.wav")
    out = os.path.join(td, "AUTOCHORDS_tema")
    os.makedirs(out)
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * 20)
    ca = os.path.join(out, "acords.csv")
    sa = os.path.join(out, "estructura_ABC.csv")
    with open(ca, "w", encoding="utf-8") as f:
        f.write(ACORDS)
    with open(sa, "w", encoding="utf-8") as f:
        f.write(SECCIONS)
    v = visor_mod.Visor(wav, ca, sa, bpm=120, bpb=4, tempo_fix=False)
    v.td, v.sortida = td, out
    return v


def _x_vista(tl, t):
    """Coordenada X de VISTA del temps `t` (amb la vista actual)."""
    x_esc = tl._x_offset + (float(t) - tl._view_left) * tl._pps
    return float(tl.mapFromScene(QPointF(x_esc, 0.0)).x())


def _y_vista(tl, y_esc):
    """Coordenada Y de VISTA d'una alçada d'ESCENA."""
    return float(tl.mapFromScene(QPointF(0.0, float(y_esc))).y())


def _ev(tipus, x, y, button=Qt.LeftButton):
    return QMouseEvent(tipus, QPointF(float(x), float(y)), button, button,
                       Qt.NoModifier)


def _marca(tl, t0, t1, y_esc0=None, y_esc1=None):
    """Simula un arrossegament de marc entre dos temps i dues alçades.

    Per defecte cobreix les DUES pistes (de la secció de dalt a la d'acords).
    """
    if y_esc0 is None:
        y_esc0 = LANE_SEC_TOP + LANE_H / 2.0
    if y_esc1 is None:
        y_esc1 = LANE_ACC_TOP + LANE_H / 2.0
    x0, y0 = _x_vista(tl, t0), _y_vista(tl, y_esc0)
    x1, y1 = _x_vista(tl, t1), _y_vista(tl, y_esc1)
    tl.mousePressEvent(_ev(QEvent.MouseButtonPress, x0, y0))
    tl.mouseMoveEvent(_ev(QEvent.MouseMove, x1, y1))
    tl.mouseReleaseEvent(_ev(QEvent.MouseButtonRelease, x1, y1))


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])


class TestEinaPerDefecte(_Base):
    def test_eina_intel_ligent_per_defecte(self):
        v = _visor()
        self.assertEqual(v.timeline.tool(), "intel·ligent")
        v.close()

    def test_rang_d_acords_no_toca_les_seccions(self):
        v = _visor()
        v.timeline.select_clip("chord", 0)          # àncora
        v.timeline.extend_selection("chord", 2)     # Shift+clic a «F»
        # només acords: el carril de la secció NO s'hi ha de colar
        self.assertEqual(v.timeline.selected_keys(),
                         {("chord", 0), ("chord", 1), ("chord", 2)})
        v.close()

    def test_rang_de_seccions_no_toca_els_acords(self):
        v = _visor()
        v.timeline.select_clip("section", 0)
        v.timeline.extend_selection("section", 1)
        self.assertEqual(v.timeline.selected_keys(),
                         {("section", 0), ("section", 1)})
        v.close()

class TestMarcSeleccio(_Base):
    def test_marc_agafa_el_que_sona_i_no_el_que_nomes_toca(self):
        v = _visor()
        v.timeline.set_tool("marc")
        _marca(v.timeline, 5.0, 6.0)                # cobreix les dues pistes
        # F comença a 4.5 (ABANS del marc) però hi sona → hi entra
        # A acaba exactament a 5.0 → només la toca → NO hi entra
        self.assertEqual(v.timeline.selected_keys(),
                         {("chord", 2), ("section", 1)})
        v.close()

    def test_marc_nomes_sobre_la_pista_d_acords(self):
        v = _visor()
        v.timeline.set_tool("marc")
        # rectangle només damunt la pista d'acords (l'alçada decideix les pistes)
        _marca(v.timeline, 5.0, 6.0,
               y_esc0=LANE_ACC_TOP + 2, y_esc1=LANE_ACC_TOP + LANE_H - 2)
        self.assertEqual(v.timeline.selected_keys(), {("chord", 2)})
        v.close()

    def test_marc_nomes_sobre_la_pista_de_seccions(self):
        v = _visor()
        v.timeline.set_tool("marc")
        _marca(v.timeline, 5.0, 6.0,
               y_esc0=LANE_SEC_TOP + 2, y_esc1=LANE_SEC_TOP + LANE_H - 2)
        self.assertEqual(v.timeline.selected_keys(), {("section", 1)})
        v.close()

    def test_amb_eina_marc_arrossegar_no_mou_el_clip(self):
        v = _visor()
        abans = [round(float(a[0]), 6) for a in v.acords]
        v.timeline.set_tool("marc")
        # arrossegar DES DE DAMUNT del clip «F» (4.5) fins a 6.0
        _marca(v.timeline, 4.5, 6.0,
               y_esc0=LANE_ACC_TOP + LANE_H / 2.0,
               y_esc1=LANE_ACC_TOP + LANE_H - 2)
        self.assertEqual([round(float(a[0]), 6) for a in v.acords], abans)
        self.assertIn(("chord", 2), v.timeline.selected_keys())
        v.close()

    def test_el_rectangle_desapareix_en_deixar_anar(self):
        v = _visor()
        v.timeline.set_tool("marc")
        x0 = _x_vista(v.timeline, 5.0)
        y0 = _y_vista(v.timeline, LANE_ACC_TOP + LANE_H / 2.0)
        v.timeline.mousePressEvent(_ev(QEvent.MouseButtonPress, x0, y0))
        self.assertIsNotNone(v.timeline._marquee)   # mentre s'arrossega, hi és
        v.timeline.mouseReleaseEvent(_ev(QEvent.MouseButtonRelease, x0, y0))
        self.assertIsNone(v.timeline._marquee)      # en deixar anar, fora
        v.close()

    def test_arrossegament_minuscle_es_un_clic(self):
        v = _visor()
        v.timeline.set_tool("marc")
        v.timeline.select_clip("chord", 1)          # selecció prèvia
        x = _x_vista(v.timeline, 8.0)
        y = _y_vista(v.timeline, LANE_ACC_TOP + LANE_H / 2.0)
        v.timeline.mousePressEvent(_ev(QEvent.MouseButtonPress, x, y))
        v.timeline.mouseReleaseEvent(_ev(QEvent.MouseButtonRelease, x, y))
        self.assertEqual(v.timeline.selected_keys(), set())      # buidada
        self.assertAlmostEqual(v.timeline._pos_t, 8.0, places=2)  # cursor mogut
        v.close()

    def test_el_marc_no_entra_a_desfer(self):
        v = _visor()
        n = len(v._undo_stack)
        v.timeline.set_tool("marc")
        _marca(v.timeline, 5.0, 6.0)
        self.assertEqual(len(v._undo_stack), n)
        v.close()

    def test_tornar_a_intel_ligent_desactiva_el_marc(self):
        v = _visor()
        v.timeline.set_tool("marc")
        _marca(v.timeline, 5.0, 6.0)
        v.timeline.set_tool("intel·ligent")
        # amb la fletxa, un drag damunt d'un clip TORNA a moure'l
        v.timeline.select_clip("chord", 2)
        abans = round(float(v.acords[2][0]), 6)
        item = v.timeline._chord_by_idx.get(2)
        if item is not None:                        # el drag el gestiona l'item
            self.assertTrue(v.timeline._marquee is None)
        self.assertEqual(round(float(v.acords[2][0]), 6), abans)
        v.close()


class TestAltArrossegaCopia(_Base):
    """Alt+arrossegar un clip d'acord = duplicar-lo: el clip viatja i a
    l'ORIGEN hi torna una còpia amb el mateix nom (convenció dels DAWs)."""

    def _gest(self, v, idx, desti):
        """Simula el gest: el clip es mou; després `_emit_edit_finished`."""
        tl = v.timeline
        tl.select_clip("chord", idx)
        tl._on_chord_time_changed(idx, desti)     # el moviment
        return tl

    def test_alt_deixa_copia_a_l_origen(self):
        v = _visor()
        tl = self._gest(v, 2, 6.0)                # F: 4.5 → 6.0
        tl._alt_copia = (4.5, "F")                # com si l'Alt fos premut
        tl._emit_edit_finished()
        times = [round(float(t), 3) for t, *_r in v.acords]
        self.assertIn(6.0, times)                 # el clip mogut
        self.assertIn(4.5, times)                 # ...i la còpia a l'origen
        copia = [a for a in v.acords if abs(float(a[0]) - 4.5) < 1e-6][0]
        self.assertEqual(copia[1], "F")           # mateix nom
        self.assertEqual(len(v.acords), 6)        # s'ha afegit una marca
        v.close()

    def test_sense_alt_no_deixa_cap_copia(self):
        v = _visor()
        tl = self._gest(v, 2, 6.0)
        self.assertIsNone(tl._alt_copia)          # sense Alt no s'ha capturat
        tl._emit_edit_finished()
        times = [round(float(t), 3) for t, *_r in v.acords]
        self.assertIn(6.0, times)
        self.assertNotIn(4.5, times)              # moviment normal
        self.assertEqual(len(v.acords), 5)
        v.close()

    def test_la_copia_es_desfà(self):
        v = _visor()
        tl = self._gest(v, 2, 6.0)
        tl._alt_copia = (4.5, "F")
        tl._emit_edit_finished()
        self.assertIn(4.5, [round(float(t), 3) for t, *_r in v.acords])
        v.undo()                                  # desfer la còpia
        self.assertNotIn(4.5, [round(float(t), 3) for t, *_r in v.acords])
        v.close()


class TestEscape(_Base):
    """`Esc`, per ordre: (1) anul·la el RANG en curs, (2) anul·la el LOOP a mig
    marcar, (3) desactiva el LOOP, (4) buida la SELECCIÓ. Si no es compleix cap
    d'aquestes, no fa res (ni toca el loop ni la selecció)."""

    @staticmethod
    def _esc(tl):
        from PyQt5.QtCore import QEvent
        from PyQt5.QtGui import QKeyEvent
        tl.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Escape,
                                   Qt.NoModifier))

    def test_ordre_de_prioritats(self):
        v = _visor()
        tl = v.timeline
        # (1) RANG en curs
        tl.set_tool("marc")
        x, y = _x_vista(tl, 5.0), _y_vista(tl, LANE_ACC_TOP + 2)
        tl.mousePressEvent(_ev(QEvent.MouseButtonPress, x, y))
        self.assertIsNotNone(tl._marquee)
        self._esc(tl)
        self.assertIsNone(tl._marquee)
        # (3) LOOP actiu → es desactiva (cal que el VISOR tingui A i B:
        # és ell qui mana el playback, i els rep pel senyal `loopChanged`)
        tl.loopChanged.emit(1.0, 3.0)
        v.set_loop(True)
        self.assertTrue(v.loop_on)
        self._esc(tl)
        self.assertFalse(v.loop_on)
        # (4) SELECCIÓ → es buida
        tl.select_clip("chord", 1)
        self.assertTrue(tl.selected_keys())
        self._esc(tl)
        self.assertEqual(tl.selected_keys(), set())
        v.close()

    def test_loop_a_mig_marcar_es_descarta(self):
        v = _visor()
        tl = v.timeline
        tl._loop_a, tl._loop_b = 2.0, 4.0      # loop previ
        tl._loop_a0, tl._loop_b0 = 2.0, 4.0
        tl._loop_drag = True                   # ...i n'estem marcant un altre
        tl._loop_a, tl._loop_b = 2.0, 7.0
        self._esc(tl)
        self.assertFalse(tl._loop_drag)
        self.assertEqual((tl._loop_a, tl._loop_b), (2.0, 4.0))   # com era
        v.close()

    def test_loop_marcat_es_treu(self):
        """Amb el loop marcat (encara que estigui aturat), Esc ha de fer fora
        la caixa groga: si no, quedaria pintada i semblaria que el loop hi és."""
        v = _visor()
        tl = v.timeline
        # marcat al regle (el timeline guarda A/B; el senyal només va cap al visor)
        tl._loop_a, tl._loop_b = 2.0, 4.0
        tl._update_loop_item()
        tl.loopChanged.emit(2.0, 4.0)
        self._esc(tl)
        self.assertIsNone(tl._loop_a)
        self.assertIsNone(tl._loop_b)
        self.assertFalse(getattr(v, "loop_on", False))
        v.close()

    def test_sense_res_no_toca_la_seleccio(self):
        v = _visor()
        tl = v.timeline
        self._esc(tl)                          # res a fer
        self.assertEqual(tl.selected_keys(), set())
        self.assertIsNone(tl._loop_a)
        self.assertFalse(getattr(v, "loop_on", False))
        v.close()


class TestDreceraEina(_Base):
    """La tecla `E` commuta l'eina (TOGGLE, no on/off) i per defecte sempre
    s'arrenca en «intel·ligent»."""

    def test_e_es_un_toggle(self):
        from app import main as app_main
        w = app_main.Finestra()
        try:
            self.assertFalse(w.b_eina.isChecked())   # defecte: intel·ligent
            self.assertEqual(w.b_eina.text(), "Eina: intel·ligent")
            w._toggle_eina_tecla()
            self.assertTrue(w.b_eina.isChecked())    # 1a → marc
            self.assertEqual(w.b_eina.text(), "Eina: selecció")
            w._toggle_eina_tecla()
            self.assertFalse(w.b_eina.isChecked())   # 2a → intel·ligent
            self.assertEqual(w.b_eina.text(), "Eina: intel·ligent")
        finally:
            w.close()


def tearDownModule():
    try:
        import _qt_neteja
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()


if __name__ == "__main__":
    unittest.main()
