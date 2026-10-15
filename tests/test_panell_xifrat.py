"""Panell «Tipus d'acord» (`app/panell_xifrat.py`) — dock esquerra desacoplable.

Comportament acordat amb l'operador (mockup aprovat):
- `Arrel` i `Baix` = camps de **text lliure** (poden anar buits).
- La llista és **plana** (de menys a més complex) amb `tipus·alternatius` +
  els **graus** a sota (dades de `xifrat.TAULA_TIPUS`).
- **Clicar un tipus NOMÉS omple** la casella «Nom» de l'editor: mai aplica.
- **Sense arrel** → s'hi escriu només el tipus (`Maj7`) i l'usuari l'acaba.
- Botó **▶ Escoltar** present però **desactivat** (plaçaholder per al MIDI).
"""
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtWidgets import QDockWidget, QMenu  # noqa: E402

from app import main as app_main  # noqa: E402
from app import xifrat  # noqa: E402

_VIVES = []


def _wav(dur=5.0):
    td = tempfile.mkdtemp()
    ruta = os.path.join(td, "t.wav")
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * int(44100 * dur))
    return ruta


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = app_main.QApplication.instance() or app_main.QApplication([])

    def _finestra(self, amb_visor=True):
        w = app_main.Finestra()
        _VIVES.append(w)
        w.avisa_info = lambda *a, **k: None
        w.avisa = lambda *a, **k: None
        if amb_visor:
            wav = _wav()
            w.wav_edit.setText(wav)
            w._carrega_visor(wav)
        return w

    def tearDown(self):
        ws, _VIVES[:] = _VIVES[:], []
        for w in ws:
            w.dirty = False
        try:
            import _qt_neteja
        except ImportError:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import _qt_neteja
        _qt_neteja.tanca_i_destrueix(*ws)


class TestTaula(unittest.TestCase):
    def test_composa(self):
        for a, q, b, esperat in [("Ab", "Maj7", "Db", "AbMaj7/Db"),
                                 ("C", "-7b5", "", "C-7b5"),
                                 ("Ab", "6add9", "Db", "Ab6add9/Db"),
                                 ("", "Maj7", "", "Maj7"),
                                 ("", "m7b5", "", "-7b5"),
                                 ("C", "", "", "C"),
                                 ("F#", "7", "G", "F#7/G")]:
            self.assertEqual(xifrat.composa(a, q, b), esperat,
                             f"({a!r},{q!r},{b!r})")

    def test_la_taula_cobreix_tots_els_tipus(self):
        """Cada `kind` de `TIPUS` ha de sortir a la TAULA (com a qualitat o
        com a alternativa) → el panell no en pot deixar cap fora."""
        quals = {q for _e, q, _a, _g in xifrat.TAULA_TIPUS}
        alts = "·".join(a for _e, _q, a, _g in xifrat.TAULA_TIPUS)
        faltes = [t for t in xifrat.TIPUS if t not in quals and t not in alts]
        self.assertEqual(faltes, [], f"tipus sense fila al panell: {faltes}")

    def test_la_taula_te_ordena_i_dades_completes(self):
        self.assertGreaterEqual(len(xifrat.TAULA_TIPUS), 60)
        for etiqueta, qual, alts, graus in xifrat.TAULA_TIPUS:
            self.assertTrue(etiqueta, "etiqueta buida")
            self.assertTrue(graus, f"{etiqueta}: sense graus")
            # la qualitat canònica ha de ser coherent amb el tipus
            self.assertEqual(xifrat.normalitza_qualitat(qual), qual,
                             f"{etiqueta}: la qualitat no és canònica")


class TestPanell(_Base):
    def test_dock_a_l_esquerra_i_desacoplable(self):
        w = self._finestra(amb_visor=False)
        self.assertEqual(w.dock_xifrat.windowTitle(), "Tipus d'acord")
        self.assertIs(w.dock_xifrat.widget(), w.panell_xifrat)
        f = w.dock_xifrat.features()
        self.assertTrue(f & QDockWidget.DockWidgetFloatable, "desacoplable")
        self.assertTrue(f & QDockWidget.DockWidgetMovable, "moble")
        # menú Visualitza → acció de mostrar
        textos = [a.text() for m in w.menuBar().findChildren(QMenu)
                  for a in m.actions()]
        self.assertIn("Mostra els tipus d'acord", textos)

    def test_llista_i_boto_escoltar(self):
        w = self._finestra(amb_visor=False)
        p = w.panell_xifrat
        self.assertEqual(p.llista.count(), len(xifrat.TAULA_TIPUS))
        self.assertFalse(p.b_escoltar.isEnabled(),
                         "el botó Escoltar és un plaçaholder (MIDI futur)")

    def test_clicar_un_tipus_omple_la_casella_nom(self):
        w = self._finestra()
        p = w.panell_xifrat
        p.arrel.setText("Ab")
        p.baix.setText("Db")
        it = next(p.llista.item(i) for i in range(p.llista.count())
                  if p.llista.item(i).text() == "maj7")
        p._on_clic(it)
        self.assertEqual(p.previsio.text(), "AbMaj7/Db")
        self.assertEqual(w.visor_ref.ed_nom.text(), "AbMaj7/Db")
        # NO s'ha aplicat res al model (cal «Aplica»)
        self.assertNotIn("AbMaj7/Db",
                          [a[1] for a in w.visor_ref.acords])

    def test_sense_arrel_escriu_nomes_el_tipus(self):
        w = self._finestra()
        p = w.panell_xifrat
        it = next(p.llista.item(i) for i in range(p.llista.count())
                  if p.llista.item(i).text() == "maj7")
        p._on_clic(it)
        self.assertEqual(w.visor_ref.ed_nom.text(), "Maj7")

    def test_sense_visor_avisa_i_no_peta(self):
        w = self._finestra(amb_visor=False)
        p = w.panell_xifrat
        it = next(p.llista.item(i) for i in range(p.llista.count())
                  if p.llista.item(i).text() == "m7b5")
        p._on_clic(it)          # no ha de petar (avisa per la caixa d'info)


def tearDownModule():
    try:
        import _qt_neteja
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()


if __name__ == "__main__":
    unittest.main()
