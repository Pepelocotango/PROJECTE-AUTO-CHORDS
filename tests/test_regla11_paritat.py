"""Regla d'or #11 — PARITAT d'edició i tracte visual (acords ↔ estructura).

`docs/REGLES_DE_LA_APP.md` §11: els clips d'**acords** i d'**estructura** han de
tenir **exactament les mateixes eines d'edició** i el **mateix tracte** al visor.
Aquest mòdul blinda la paritat:

- Backend: `pipeline.parteix_acord` / `fusiona_acords` (mirall de les de secció).
- Visor: `parteix_acord` / `fusiona_acord` / `fusiona_seccio`.
- Menús de llista: el d'acords i el de seccions presenten el MATEIX joc d'accions.
- Menú contextual del clip: «Parteix…» és disponible per a acords I seccions.
- Item visual: el `SectionItem` emet `dragStarted` (com el `ChordItem`).
"""
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PyQt5.QtWidgets import QApplication, QListWidget, QMenu  # noqa: E402

from app import pipeline  # noqa: E402
from app import timeline_items  # noqa: E402
from app import visor as visor_mod  # noqa: E402

DUR = 30.0
ACORDS = [(0.0, "C", "0.0"), (10.0, "Am", "10.0"), (20.0, "F", "20.0")]
SECCIONS = [(0.0, 10.0, "A", "A"), (10.0, 20.0, "B", "B"), (20.0, DUR, "C", "C")]


def _escriu_wav(ruta, dur=DUR):
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * int(44100 * dur))


def _visor():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "tema.wav")
    _escriu_wav(wav)
    sortida = pipeline.carpeta_sortida(wav)
    os.makedirs(sortida, exist_ok=True)
    ca = os.path.join(sortida, "acords.csv")
    with open(ca, "w", encoding="utf-8") as f:
        for t, nom, _src in ACORDS:
            f.write(f"{t},{t + 1},{nom}\n")
    sa = os.path.join(sortida, "estructura_ABC.csv")
    with open(sa, "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n")
        for ini, fi, L, fam in SECCIONS:
            f.write(f"{ini},{fi},{fi - ini},{L},{fam},1,1\n")
    v = visor_mod.Visor(wav, ca, sa, 120.0, 4, True)
    v.td, v.sortida, v.abc_csv = td, sortida, sa
    return v


class _Fila:
    """Stub per a `QListWidget.indexAt(...).row()` als tests de menú."""
    def __init__(self, r):
        self._r = r

    def row(self):
        return self._r


class _EvRatoli:
    """Esdeveniment de ratolí mínim per a `mousePressEvent` (sense Qt real)."""
    def __init__(self, x, boto=Qt.LeftButton):
        self._x, self._boto, self.acceptat = x, boto, False

    def button(self):
        return self._boto

    def pos(self):
        return QPointF(self._x, 0.0)

    def accept(self):
        self.acceptat = True


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])


# ── Backend ──────────────────────────────────────────────────────────────────
class TestBackendParitat(_Base):
    def test_parteix_acord_insereix_un_clip_amb_el_mateix_nom(self):
        nou = pipeline.parteix_acord(list(ACORDS), 0, 4.0)
        self.assertEqual([(a[0], a[1]) for a in nou],
                         [(0.0, "C"), (4.0, "C"), (10.0, "Am"), (20.0, "F")])

    def test_parteix_acord_amb_nom_nou(self):
        nou = pipeline.parteix_acord(list(ACORDS), 1, 15.0, "G")
        self.assertEqual(nou[1][1], "Am")
        self.assertEqual(nou[2][1], "G")
        self.assertAlmostEqual(nou[2][0], 15.0)

    def test_parteix_acord_fora_de_rang_peta(self):
        with self.assertRaises(ValueError):
            pipeline.parteix_acord(list(ACORDS), 0, 12.0)
        with self.assertRaises(ValueError):
            # Sense `durada` no se sap on acaba l'últim clip (fi=0) → fora de rang.
            pipeline.parteix_acord(list(ACORDS), 2, 25.0)

    def test_parteix_acord_l_ultim_amb_durada_es_parteix(self):
        """Paritat #11: l'últim acord es parteix igual que l'última secció."""
        nou = pipeline.parteix_acord(list(ACORDS), 2, 25.0, durada=DUR)
        self.assertEqual([(a[0], a[1]) for a in nou],
                         [(0.0, "C"), (10.0, "Am"), (20.0, "F"), (25.0, "F")])

    def test_fusiona_acords_esquena_l_harmonia_de_l_esquerre(self):
        # Fusionar 0 amb el següent → queda el "C" (esquerre) estès.
        self.assertEqual([(a[0], a[1]) for a in
                          pipeline.fusiona_acords(list(ACORDS), 0, "seguent")],
                         [(0.0, "C"), (20.0, "F")])
        # Fusionar 1 amb l'anterior → queda el "C".
        self.assertEqual([(a[0], a[1]) for a in
                          pipeline.fusiona_acords(list(ACORDS), 1, "anterior")],
                         [(0.0, "C"), (20.0, "F")])

    def test_mirall_de_les_seccions(self):
        """Les operacions d'acord i de secció han d'existir totes dues."""
        for nom in ("parteix_acord", "fusiona_acords",
                    "parteix_seccio", "fusiona_seccions"):
            self.assertTrue(callable(getattr(pipeline, nom, None)),
                            f"falta pipeline.{nom} (regla #11)")


# ── Visor ────────────────────────────────────────────────────────────────────
class TestVisorParitat(_Base):
    def test_parteix_acord_mante_cobertura_i_es_desfà(self):
        v = _visor()
        n0 = len(v.acords)
        self.assertEqual(v.parteix_acord(0, 4.0), 1)
        self.assertEqual(n0 + 1, len(v.acords))
        self.assertEqual(v.acords[0][2][0], "C")
        self.assertEqual(v.acords[1][2][0], "C")
        self.assertAlmostEqual(float(v.acords[1][0]), 4.0, places=6)
        # cobertura (#4): els acords segueixen cobrint tota la WAV de 0 a DUR
        self.assertAlmostEqual(float(v.acords[0][0]), 0.0, places=6)
        v.undo()
        self.assertEqual(len(v.acords), n0)

    def test_visor_parteix_l_ultim_acord(self):
        """L'últim acord (que acaba a la WAV) TAMBÉ es pot partir (#11)."""
        v = _visor()
        n0 = len(v.acords)
        self.assertEqual(v.parteix_acord(n0 - 1, 25.0), n0)
        self.assertEqual(len(v.acords), n0 + 1)
        self.assertAlmostEqual(float(v.acords[-1].ini), 25.0, places=6)
        self.assertAlmostEqual(float(v.acords[-1].fi), DUR, places=6)
        v.undo()
        self.assertEqual(len(v.acords), n0)

    def test_la_pista_de_tempo_entra_a_la_seleccio(self):
        """Els trams de BPM/compàs es seleccionen com la resta de clips (#11)."""
        v = _visor()
        v.aplica_tempo_trams([(0.0, 6.0, 120.0, 4, 4), (6.0, DUR, 90.0, 3, 4)])
        tl = v.timeline
        trams = tl._trams_tempo()
        self.assertEqual([(t[0], t[1]) for t in trams],
                         [(0.0, 6.0), (6.0, DUR)])
        # marquee (solapament): un marc de 10 a 12 cau dins del 2n tram
        keys = tl.keys_dins_marc(10.0, 12.0, chords=False, sections=False)
        self.assertEqual(keys, {("tempo", 1)})
        # un marc dels 2 trams els agafa tots dos
        keys = tl.keys_dins_marc(0.0, DUR, chords=False, sections=False)
        self.assertEqual(keys, {("tempo", 0), ("tempo", 1)})
        # rang (Shift+clic): es queda al carril dels trams
        tl.select_clip("tempo", 0)
        tl.extend_selection("tempo", 1)
        self.assertEqual(tl.selected_keys(), {("tempo", 0), ("tempo", 1)})
        # Ctrl+clic = toggle (afegeix/treu)
        tl.toggle_selection("tempo", 0)
        self.assertEqual(tl.selected_keys(), {("tempo", 1)})
        # ... i el Ctrl+clic sobre un ACORD no arrossega cap tram
        tl.select_clip("chord", 0)
        tl.extend_selection("chord", 1)
        self.assertFalse([k for k in tl.selected_keys() if k[0] == "tempo"])

    def test_partir_per_la_meitat_acord_i_seccio(self):
        """«Partir per la meitat» = dues meitats exactes, als DOS tipus (#11)."""
        v = _visor()
        self.assertEqual(v.parteix_per_la_meitat("section", 0), 1)
        self.assertAlmostEqual(float(v.seccions[0][1]), 5.0, places=6)
        self.assertAlmostEqual(float(v.seccions[1][0]), 5.0, places=6)
        self.assertAlmostEqual(float(v.seccions[1][1]), 10.0, places=6)
        self.assertEqual(v.parteix_per_la_meitat("chord", 0), 1)
        self.assertAlmostEqual(float(v.acords[0].fi), 5.0, places=6)
        self.assertAlmostEqual(float(v.acords[1].ini), 5.0, places=6)
        self.assertEqual(v.acords[1].payload[0], "C")
        # tambe funciona amb l'ULTIM clip (acaba a la WAV)
        n = len(v.acords)
        self.assertEqual(v.parteix_per_la_meitat("chord", n - 1), n)
        self.assertAlmostEqual(float(v.acords[-1].fi), DUR, places=6)

    def test_ultim_acord_fi_editable_crea_clip_de_cua(self):
        """Paritat #11: l'últim clip també s'encongeix per la vora dreta.

        Abans el timeline ho bloquejava (`pass`): la fi de l'últim acord no
        s'editava mai i no hi havia manera de deixar un tros de cua.
        """
        v = _visor()
        n0 = len(v.acords)
        v.timeline._on_chord_end_changed(n0 - 1, DUR - 2.0)
        cl = list(v.timeline._acords)
        self.assertEqual(len(cl), n0 + 1)
        self.assertAlmostEqual(float(cl[-1].ini), DUR - 2.0, places=6)
        self.assertAlmostEqual(float(cl[-1].fi), DUR, places=6)
        self.assertEqual(cl[-1].payload[0], pipeline.SENSE_ACORD)

    def test_fusiona_acord(self):
        v = _visor()
        n0 = len(v.acords)
        self.assertTrue(v.fusiona_acord(0, "seguent"))
        self.assertEqual(len(v.acords), n0 - 1)
        self.assertEqual(v.acords[0][2][0], "C")
        v.undo()
        self.assertEqual(len(v.acords), n0)

    def test_visor_te_les_mateixes_operacions_per_a_tots_dos(self):
        v = _visor()
        for nom in ("parteix_acord", "_parteix_acord_dialog", "fusiona_acord",
                    "parteix_seccio", "_parteix_seccio_dialog", "fusiona_seccio"):
            self.assertTrue(callable(getattr(v, nom, None)),
                            f"falta Visor.{nom} (regla #11)")


# ── Menús ────────────────────────────────────────────────────────────────────
def _captura_menu(fn, *args):
    capt = {}
    orig = QMenu.exec_

    def fake(self, pos, *rest):
        capt["accions"] = [(a.text(), a.isEnabled())
                           for a in self.actions() if not a.isSeparator()]
        return None
    QMenu.exec_ = fake
    try:
        fn(*args)
    finally:
        QMenu.exec_ = orig
    return capt.get("accions", [])


class TestMenusParitat(_Base):
    def _amb_fila(self, fn):
        orig = QListWidget.indexAt
        QListWidget.indexAt = lambda self, pos: _Fila(0)
        try:
            return _captura_menu(fn, QPoint(1, 1))
        finally:
            QListWidget.indexAt = orig

    def test_menus_de_llista_mateix_joc_d_accions(self):
        v = _visor()
        ac = self._amb_fila(v._menu_acord)
        se = self._amb_fila(v._menu_seccio)
        self.assertEqual(len(ac), len(se),
                         f"jocs d'accions diferents: {ac} vs {se}")
        self.assertEqual(len(ac), 7)          # + «Partir per la meitat» (#11)
        # Mateixa estructura (activació) i mateixa paraula de tipus a cada posició.
        self.assertEqual([e for _t, e in ac], [e for _t, e in se])
        self.assertIn("acord", ac[1][0].lower())
        self.assertIn("secció", se[1][0].lower())

    def test_menu_contextual_parteix_per_a_tots_dos(self):
        v = _visor()
        ac = _captura_menu(v._on_clip_context_menu, "chord", 0, QPoint(0, 0))
        se = _captura_menu(v._on_clip_context_menu, "section", 0, QPoint(0, 0))
        self.assertTrue(dict(ac).get("Parteix l'acord…"),
                        f"hauria d'estar actiu sobre un acord: {ac}")
        self.assertTrue(dict(se).get("Parteix la secció…"),
                        f"hauria d'estar actiu sobre una secció: {se}")


# ── Tracte visual ────────────────────────────────────────────────────────────
class TestTracteVisual(_Base):
    def test_sectionitem_emet_dragstarted(self):
        it = timeline_items.SectionItem(0, 0.0, 2.0, "A", "A",
                                        pps=10.0, x_offset=0.0,
                                        lane_y=0.0, lane_h=20.0)
        got = []
        it.dragStarted.connect(lambda: got.append(1))
        x = (it._x_left() + it._x_right()) / 2.0   # cos (ZONE_BODY)
        it.mousePressEvent(_EvRatoli(x))
        self.assertTrue(got, "SectionItem ha d'emetre dragStarted (paritat #11)")

    def test_chorditem_emet_dragstarted(self):
        it = timeline_items.ChordItem(0, 0.0, "C", 2.0,
                                      pps=10.0, x_offset=0.0,
                                      lane_y=0.0, lane_h=20.0)
        got = []
        it.dragStarted.connect(lambda: got.append(1))
        x = (it._x_left() + it._x_right()) / 2.0
        it.mousePressEvent(_EvRatoli(x))
        self.assertTrue(got)


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
