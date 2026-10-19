"""Despatx ÚNIC d'edició (regla d'or #11) — contracte de superfícies.

Objectiu: que **totes** les superfícies (menú contextual, menú principal,
teclat del timeline, porta-retalls del loop) envien la intenció a
`Visor.executa_edicio()` i que cap d'elles decidisca per si mateixa com
s'edita un carril. Així el carril ③ (BPM/compàs) no pot quedar-se fora
d'una operació (bug real: Ctrl+clic esborrava la selecció, Shift+clic no
feia rang, Del/F2/Ctrl+D no arribaven al tempo i «Reanomena» amb 2 trams
renombrava seccions).
"""
import inspect
import csv
import os
import sys
import tempfile
import types
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402,F401  (higiene: esborra els temporals)
_ = _temporals

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PyQt5.QtGui import QKeyEvent  # noqa: E402
from PyQt5.QtTest import QTest  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from app import main as app_main, pipeline  # noqa: E402
from app import visor as visor_mod  # noqa: E402
from app import timeline_base as tb  # noqa: E402
from app.timeline import TimelineView  # noqa: E402
from app.timeline_items import ChordItem  # noqa: E402


_DUR = 30.0


def _escriu_wav(ruta, dur=_DUR):
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
        f.write("0,10,C\n10,20,Am\n20,30,F\n")
    sa = os.path.join(sortida, "estructura_ABC.csv")
    with open(sa, "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
                "0,10,10,A,A,1,1\n10,20,10,B,B,1,1\n20,30,10,C,C,1,1\n")
    v = visor_mod.Visor(wav, ca, sa, 120.0, 4, True)
    v.aplica_tempo_trams([(0.0, 10.0, 120.0, 4, 4),
                          (10.0, 30.0, 90.0, 3, 4)])
    v.td, v.sortida = td, sortida
    return v


def _tecla(key, mods=Qt.NoModifier):
    return QKeyEvent(QEvent.KeyPress, key, mods)


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])


class TestSeleccioUnica(_Base):
    def test_seleccio_activa_inclou_els_tres_carrils(self):
        v = _visor()
        try:
            for kind, idx in (("chord", 1), ("section", 1), ("tempo", 1)):
                v.timeline.select_clip(kind, idx)
                self.assertEqual(v.seleccio_activa(), (kind, idx))
                self.assertEqual(v.clips_seleccionats(), {(kind, idx)})
        finally:
            v.close()

    def test_modes_set_toggle_extend(self):
        v = _visor()
        try:
            tl = v.timeline
            self.assertTrue(tl.selecciona("tempo", 0))
            self.assertTrue(tl.selecciona("tempo", 1, "toggle"))
            self.assertEqual(tl.selected_keys(), {("tempo", 0), ("tempo", 1)})
            self.assertTrue(tl.selecciona("tempo", 0, "toggle"))
            self.assertEqual(tl.selected_keys(), {("tempo", 1)})
            tl.selecciona("tempo", 0)
            self.assertTrue(tl.selecciona("tempo", 1, "extend"))
            self.assertEqual(tl.selected_keys(), {("tempo", 0), ("tempo", 1)})
            self.assertFalse(tl.selecciona("tempo", 99))
            self.assertFalse(tl.selecciona("cap", 0))
        finally:
            v.close()


class TestTeclatDespatx(_Base):
    def test_les_tecles_emeten_ordres_al_despatx(self):
        v = _visor()
        try:
            v.timeline.select_clip("chord", 0)
            ordres = []
            v.timeline.editCommandRequested.connect(
                lambda op, kw: ordres.append(op))
            for key, mods in (
                    (Qt.Key_Left, Qt.NoModifier),
                    (Qt.Key_Right, Qt.NoModifier),
                    (Qt.Key_C, Qt.ControlModifier),
                    (Qt.Key_X, Qt.ControlModifier),
                    (Qt.Key_V, Qt.ControlModifier),
                    (Qt.Key_D, Qt.ControlModifier)):
                v.timeline.keyPressEvent(_tecla(key, mods))
            v.timeline.select_clip("chord", 0)
            v.timeline.keyPressEvent(_tecla(Qt.Key_Delete))
            self.assertEqual(ordres, ["nudge", "nudge", "copia", "retalla",
                                      "enganxa", "duplica", "elimina"])
        finally:
            v.close()


class TestMenuContextualDespatx(_Base):
    def test_cada_clau_va_al_despatx(self):
        v = _visor()
        try:
            crides = []

            def rec(op, kind=None, idx=None, **kw):
                crides.append((op, kind, idx, kw))
                return True

            v.executa_edicio = rec
            esperat = {
                "afegeix": "afegeix",
                "duplica": "duplica",
                "elimina": "elimina",
                "reanomena": "reanomena",
                "parteix": "parteix",
                "meitat": "parteix_meitat",
                "fusiona_anterior": "fusiona",
                "fusiona_seguent": "fusiona",
                "retalla": "retalla",
                "copia": "copia",
                "enganxa": "enganxa",
            }
            for clau, op in esperat.items():
                v._executa_contextual("chord", 0, 3.0, clau)
                self.assertEqual(crides[-1][0], op, clau)
            self.assertTrue(all(c[1] == "chord" for c in crides))
            self.assertEqual(crides[0][3], {"t": 3.0})
            self.assertEqual(crides[1][3], {})
            self.assertEqual(crides[6][3], {"amb": "anterior"})
            self.assertEqual(crides[7][3], {"amb": "seguent"})
        finally:
            v.close()


class TestMenuPrincipalDespatx(_Base):
    def test_les_accions_de_menú_deleguen_al_despatx(self):
        v = _visor()
        try:
            crides = []

            def rec(op, kind=None, idx=None, **kw):
                crides.append((op, kind, idx, kw))
                return True

            v.executa_edicio = rec
            v.pos = 5.0
            w = types.SimpleNamespace(visor_ref=v,
                                      registra=lambda *a, **k: None)
            w._sel_cursor = types.MethodType(app_main.Finestra._sel_cursor, w)
            for metode, op in (
                    ("_elimina_element", "elimina"),
                    ("_duplica_element", "duplica"),
                    ("_renomena_element", "reanomena"),
                    ("_copia_clips", "copia"),
                    ("_retalla_clips", "retalla"),
                    ("_enganxa_clips", "enganxa")):
                getattr(app_main.Finestra, metode)(w)
                self.assertEqual(crides[-1][0], op, metode)
            for metode, kind in (
                    ("_afegeix_acord_ui", "chord"),
                    ("_afegeix_seccio_ui", "section"),
                    ("_afegeix_tram_ui", "tempo")):
                getattr(app_main.Finestra, metode)(w)
                self.assertEqual(crides[-1][:2], ("afegeix", kind), metode)
                self.assertEqual(crides[-1][3], {"t": 5.0})
            for metode, kind in (
                    ("_parteix_acord_ui", "chord"),
                    ("_parteix_seccio_ui", "section"),
                    ("_parteix_tram_ui", "tempo")):
                getattr(app_main.Finestra, metode)(w)
                self.assertEqual(crides[-1][:2], ("parteix", kind), metode)
            # selecció des dels menús: també pel despatx
            for metode, kind in (
                    ("_sel_acord_cursor", "chord"),
                    ("_sel_seccio_cursor", "section"),
                    ("_sel_tram_cursor", "tempo")):
                getattr(app_main.Finestra, metode)(w)
                self.assertEqual(crides[-1][0], "selecciona")
                self.assertEqual(crides[-1][1], kind)
                self.assertEqual(crides[-1][3], {"mode": "set"})
        finally:
            v.close()

    def test_clip_seleccionat_inclou_tempo(self):
        v = _visor()
        try:
            v.timeline.select_clip("tempo", 1)
            w = types.SimpleNamespace(visor_ref=v)
            self.assertEqual(app_main.Finestra._clip_seleccionat(w),
                             ("tempo", 1))
        finally:
            v.close()

    def test_no_queden_despatxos_paral_les_a_main(self):
        """Contracte estàtic: les accions de menú només criden el despatx."""
        propis = (
            "_elimina_element", "_duplica_element", "_renomena_element",
            "_copia_clips", "_retalla_clips", "_enganxa_clips",
            "_afegeix_acord_ui", "_afegeix_seccio_ui", "_afegeix_tram_ui",
            "_parteix_acord_ui", "_parteix_seccio_ui", "_parteix_tram_ui",
            "_sel_acord_cursor", "_sel_seccio_cursor", "_sel_tram_cursor",
            "_sel_cursor",
        )
        prohibits = (
            "_elimina_acord_index", "_elimina_seccio_index",
            "_duplica_acord_index", "_duplica_seccio_index",
            "_elimina_seleccio", "_duplica_seleccio",
            "_afegeix_acord", "_afegeix_seccio", "_afegeix_tall",
            "parteix_acord", "parteix_seccio", "fusiona_acord",
            "fusiona_seccio", "copy_selection", "cut_selection",
            "paste_at_cursor", "_on_tempo_edit", "select_clip",
        )
        for nom in propis:
            src = inspect.getsource(getattr(app_main.Finestra, nom))
            # Traiem la línia `def ...` perquè el NOM del mètode conté
            # substrings com «_afegeix_acord» o «parteix_acord».
            cos = "\n".join(src.splitlines()[1:])
            if nom in ("_sel_acord_cursor", "_sel_seccio_cursor",
                       "_sel_tram_cursor"):
                # Els tres wrappers comparteixen `_sel_cursor`, que és qui
                # crida el despatx (una sola implementació per als 3 carrils).
                self.assertIn("_sel_cursor", cos, f"{nom} no delega")
            else:
                self.assertIn("executa_edicio", cos,
                              f"{nom} no delega al despatx")
            for p in prohibits:
                self.assertNotIn(p, cos, f"{nom} encara crida {p} directament")
        src = inspect.getsource(app_main.Finestra._clip_seleccionat)
        self.assertIn("seleccio_activa", src)


class TestTempoNoEsConfon(_Base):
    def test_reanomena_multi_tempo_no_toca_seccions(self):
        v = _visor()
        try:
            v.timeline.select_multi({("tempo", 0), ("tempo", 1)})
            abans = [s[2] for s in v.seccions]
            cridat = []
            v._on_tempo_edit = lambda idx: cridat.append(idx) or True
            self.assertTrue(v.executa_edicio("reanomena"))
            self.assertEqual(cridat, [0])          # tram actiu, no seccions
            self.assertEqual([s[2] for s in v.seccions], abans)
        finally:
            v.close()

    def test_del_i_ctrl_d_arriben_al_tempo(self):
        v = _visor()
        try:
            v.timeline.select_clip("tempo", 1)
            n = len(v.tempo_trams)
            v.timeline.keyPressEvent(_tecla(Qt.Key_Delete))
            self.assertEqual(len(v.tempo_trams), n - 1)
            v.undo()
            v.timeline.select_clip("tempo", 0)
            n = len(v.tempo_trams)
            v.timeline.keyPressEvent(_tecla(Qt.Key_D, Qt.ControlModifier))
            self.assertEqual(len(v.tempo_trams), n + 1)
        finally:
            v.close()


class _EvItem:
    """Esdeveniment mínim per als gestos dels items/layers (sense Qt real)."""

    def __init__(self, x, boto=Qt.LeftButton):
        self._x = float(x)
        self._boto = boto
        self.acceptat = False

    def pos(self):
        return QPointF(self._x, 0.0)

    def button(self):
        return self._boto

    def accept(self):
        self.acceptat = True


class TestFase2Gestos(_Base):
    def test_micro_moviment_no_emet_fins_al_llindar(self):
        it = ChordItem(0, 0.0, "C", 10.0, pps=10.0, x_offset=0.0,
                       lane_y=0.0, lane_h=20.0)
        it._drag_mode = it.ZONE_BODY
        it._drag_x0 = 100.0
        it._drag_t0 = 0.0
        it._drag_next_t0 = 10.0
        vist = []
        it.timeChanged.connect(vist.append)
        it.mouseMoveEvent(_EvItem(103.0))       # 3 px: res
        self.assertFalse(it._drag_moved)
        self.assertEqual(vist, [])
        it.mouseMoveEvent(_EvItem(111.0))       # 11 px: gest real
        self.assertTrue(it._drag_moved)
        self.assertTrue(vist)

    def test_clic_no_deixa_undo_penjada(self):
        v = _visor()
        try:
            v.resize(1000, 700)
            v.show()
            self._app.processEvents()
            v.timeline.set_position(0.0)
            p = v.timeline.mapFromScene(QPointF(
                v.timeline._x_offset + (5.0 - v.timeline._view_left) *
                v.timeline._pps, tb.LANE_ACC_TOP + 20))
            QTest.mouseClick(v.timeline.viewport(), Qt.LeftButton,
                             Qt.NoModifier, p)
            self._app.processEvents()
            self.assertIsNone(v._undo_pending,
                              "un clic no pot deixar la marca d'undo oberta")
            self.assertAlmostEqual(float(v.timeline._chord_items[0].t),
                                   float(v.acords[0].ini), places=6)
        finally:
            v.close()

    def test_el_release_del_tempo_aplica_abans_de_commitar(self):
        """El layer ha d'emetre `tramMoved` ABANS de `editFinished` (undo)."""
        src = inspect.getsource(TimelineView.mouseReleaseEvent)
        self.assertLess(src.index("super().mouseReleaseEvent(event)"),
                        src.index("self.editFinished.emit()"),
                        "editFinished s'avança a l'aplicació del canvi de tempo")

    def test_tempo_drag_entra_a_l_undo(self):
        v = _visor()
        try:
            tl = v.timeline
            self.assertAlmostEqual(float(v.tempo_trams[1][0]), 10.0, places=6)

            def lx(t):
                return (float(t) - tl._view_left) * tl._pps

            v._undo_marca()
            tl._tempo_gest = True
            tl._tempo_mogut = False
            tl._tempo_lane.mousePressEvent(_EvItem(lx(10.0)))
            tl._tempo_lane.mouseMoveEvent(_EvItem(lx(12.0)))
            tl._tempo_lane.mouseReleaseEvent(_EvItem(lx(12.0)))
            self.assertTrue(tl._tempo_mogut)
            tl.editFinished.emit()
            self.assertAlmostEqual(float(v.tempo_trams[1][0]), 12.0, places=2)
            v.undo()
            self.assertAlmostEqual(float(v.tempo_trams[1][0]), 10.0, places=2)
        finally:
            v.close()

    def test_el_layer_de_tempo_snapa_com_el_timeline(self):
        v = _visor()
        try:
            t = 1.13
            self.assertAlmostEqual(v.timeline._tempo_lane._snap_t(t),
                                   v.timeline._snap(t), places=9)
        finally:
            v.close()

    def test_seccio_moguda_no_escriu_l_abc_fins_al_release(self):
        from unittest.mock import patch
        v = _visor()
        try:
            with patch.object(pipeline, "desa_abc_csv") as m:
                v._on_section_moved(0, 1.0, 2.0)
            self.assertFalse(m.called,
                             "moure una secció no pot desar l'ABC a cada move")
        finally:
            v.close()

    def test_editor_es_buida_en_seleccionar_un_tram(self):
        v = _visor()
        try:
            v.timeline.select_clip("chord", 0)
            self.assertEqual(v._ed_kind, "chord")
            v.timeline.select_clip("tempo", 0)
            self.assertIsNone(v._ed_kind)
            self.assertFalse(v.ed_nom.isEnabled())
        finally:
            v.close()

    def test_enganxar_selecciona_els_trams(self):
        v = _visor()
        try:
            tl = v.timeline
            tl.select_clip("tempo", 0)
            tl.copy_selection()
            tl.set_position(12.0, snap=False)
            tl.paste_at_cursor()
            self._app.processEvents()
            self.assertTrue(any(k == "tempo" for k, _i in tl.selected_keys()))
        finally:
            v.close()

    def test_cos_del_tram_de_tempo_mou_la_frontera_no_el_bloc(self):
        """Decisió 3: el cos mou ON CANVIA el tempo (no un bloc de durada fixa)."""
        v = _visor()
        try:
            tl = v.timeline

            def lx(t):
                return (float(t) - tl._view_left) * tl._pps

            v._undo_marca()
            tl._tempo_gest = True
            tl._tempo_mogut = False
            tl._tempo_lane.mousePressEvent(_EvItem(lx(15.0)))   # cos del 2n
            tl._tempo_lane.mouseMoveEvent(_EvItem(lx(12.0)))
            tl._tempo_lane.mouseReleaseEvent(_EvItem(lx(12.0)))
            tl.editFinished.emit()
            # La frontera s'ha mogut a 12; el final del tram continua a 30 i
            # cada costat conserva el seu BPM (90 el segon, 120 el primer).
            self.assertAlmostEqual(float(v.tempo_trams[0][1]), 12.0, places=2)
            self.assertAlmostEqual(float(v.tempo_trams[1][0]), 12.0, places=2)
            self.assertAlmostEqual(float(v.tempo_trams[1][1]), 30.0, places=2)
            self.assertEqual(float(v.tempo_trams[1][2]), 90.0)
            self.assertEqual(float(v.tempo_trams[0][2]), 120.0)
        finally:
            v.close()

    def test_rang_i_ressaltat_de_diversos_trams(self):
        v = _visor()
        try:
            tl = v.timeline
            tl.select_multi({("tempo", 0), ("tempo", 1)})
            self.assertEqual(tl._tempo_lane._sel_multi, {0, 1})
            self.assertEqual(tl.rang_seleccio(), (0.0, 30.0))
        finally:
            v.close()


class TestCoberturaAlta(_Base):
    """Decisió 1: tota alta deixa el model cobert (0 → durada) als 3 carrils."""

    def _assert_cobert(self, v):
        dur = float(v.audio["durada"])
        self.assertAlmostEqual(float(v.acords[0].ini), 0.0, places=6)
        self.assertAlmostEqual(float(v.acords[-1].fi), dur, places=6)
        self.assertAlmostEqual(float(v.seccions[0][0]), 0.0, places=6)
        self.assertAlmostEqual(float(v.seccions[-1][1]), dur, places=6)
        self.assertAlmostEqual(float(v.tempo_trams[0][0]), 0.0, places=6)
        self.assertAlmostEqual(float(v.tempo_trams[-1][1]), dur, places=6)

    def test_obre_amb_estructura_buida_i_la_completa(self):
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "tema.wav")
        _escriu_wav(wav, 10.0)
        ca = os.path.join(td, "acords.csv")
        with open(ca, "w", encoding="utf-8") as f:
            f.write("0,10,C\n")
        v = visor_mod.Visor(wav, ca, None, 120.0, 4, True)
        try:
            self.assertEqual([s[2] for s in v.seccions],
                             [pipeline.SENSE_SECCIO])
            self._assert_cobert(v)
        finally:
            v.close()

    def test_obre_amb_acords_buits_i_els_completa(self):
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "tema.wav")
        _escriu_wav(wav, 10.0)
        sa = os.path.join(td, "estructura_ABC.csv")
        with open(sa, "w", encoding="utf-8") as f:
            f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
                    "0,10,10,A,A,1,1\n")
        v = visor_mod.Visor(wav, None, sa, 120.0, 4, True)
        try:
            self.assertEqual(v.acords[0].payload[0], pipeline.SENSE_ACORD)
            self._assert_cobert(v)
        finally:
            v.close()

    def test_afegeix_seccio_en_estructura_buida(self):
        from unittest.mock import patch
        from PyQt5.QtWidgets import QInputDialog
        v = _visor()
        try:
            v.seccions = []
            v.timeline.set_data(v.acords, v.seccions)
            with patch.object(QInputDialog, "getText",
                              return_value=("Z", True)):
                self.assertTrue(v._afegeix_a_la_posicio("section", 6.0))
            self.assertIn("Z", [s[2] for s in v.seccions])
            self._assert_cobert(v)
        finally:
            v.close()

    def test_afegeix_acord_en_carril_buit(self):
        from unittest.mock import patch
        from PyQt5.QtWidgets import QInputDialog
        v = _visor()
        try:
            v.acords = []
            v.timeline.set_data(v.acords, v.seccions)
            with patch.object(QInputDialog, "getText",
                              return_value=("G", True)):
                self.assertTrue(v._afegeix_a_la_posicio("chord", 6.0))
            noms = [a.payload[0] for a in v.acords]
            self.assertIn("G", noms)
            self.assertEqual(noms[0], pipeline.SENSE_ACORD)
            self._assert_cobert(v)
        finally:
            v.close()

    def test_afegeix_tram_de_tempo(self):
        v = _visor()
        try:
            self.assertTrue(v._afegeix_a_la_posicio("tempo", 6.0))
            self._assert_cobert(v)
        finally:
            v.close()


class TestDuplicatSenseLloc(_Base):
    """Decisió 2: si la còpia sencera no cap després, no es duplica i s'avisa."""

    def _recull_avisos(self, v):
        avisos = []
        v.infoMissatge.connect(avisos.append)
        return avisos

    def test_ultim_acord_no_es_duplica(self):
        v = _visor()
        try:
            v.timeline.select_clip("chord", 2)      # 20–30 (últim)
            avisos = self._recull_avisos(v)
            self.assertFalse(v.executa_edicio("duplica"))
            self.assertEqual([a.payload[0] for a in v.acords],
                             ["C", "Am", "F"])
            self.assertTrue(any("lloc" in m for m in avisos), avisos)
            self.assertIsNone(v._undo_pending)
        finally:
            v.close()

    def test_acord_amb_lloc_si_es_duplica(self):
        v = _visor()
        try:
            v.timeline.select_clip("chord", 0)      # 0–10; hi cap 10–20
            self.assertTrue(v.executa_edicio("duplica"))
            self.assertEqual(v.acords[1].payload[0], "C")
        finally:
            v.close()

    def test_ultima_seccio_no_es_duplica(self):
        v = _visor()
        try:
            v.timeline.select_clip("section", 2)    # 20–30 (última)
            avisos = self._recull_avisos(v)
            self.assertFalse(v.executa_edicio("duplica"))
            self.assertEqual([s[2] for s in v.seccions], ["A", "B", "C"])
            self.assertTrue(any("lloc" in m for m in avisos), avisos)
        finally:
            v.close()

    def test_bloc_sense_lloc_no_es_duplica(self):
        v = _visor()
        try:
            v.timeline.select_multi({("section", 1), ("section", 2)})
            avisos = self._recull_avisos(v)
            self.assertFalse(v.executa_edicio("duplica"))
            self.assertEqual([s[2] for s in v.seccions], ["A", "B", "C"])
            self.assertTrue(any("lloc" in m for m in avisos), avisos)
        finally:
            v.close()

    def test_ultim_tram_de_tempo_no_es_duplica(self):
        v = _visor()
        try:
            v.timeline.select_clip("tempo", 1)      # 10–30 (últim)
            n = len(v.tempo_trams)
            avisos = self._recull_avisos(v)
            self.assertFalse(v.executa_edicio("duplica"))
            self.assertEqual(len(v.tempo_trams), n)
            self.assertTrue(any("lloc" in m for m in avisos), avisos)
        finally:
            v.close()


class TestPartirAlClic(_Base):
    """Decisió 4: el menú contextual talla al clic (amb snap), no al cursor."""

    def _parteix(self, v, kind, idx, t, text="Z"):
        from unittest.mock import patch
        from PyQt5.QtWidgets import QInputDialog
        with patch.object(QInputDialog, "getText", return_value=(text, True)):
            return v._executa_contextual(kind, idx, t, "parteix")

    def test_acord_amb_snap(self):
        v = _visor()
        try:
            v.ves_a(2.0)                    # cursor lluny del clip clicat
            t = 15.3
            ts = v.timeline._snap(t)
            self.assertTrue(self._parteix(v, "chord", 1, t))
            starts = [round(float(a.ini), 6) for a in v.acords]
            self.assertIn(round(float(ts), 6), starts)
            self.assertEqual(v.acords[0].payload[0], "C")   # el cursor no l'ha tocat
            idx = starts.index(round(float(ts), 6))
            self.assertEqual(v.acords[idx].payload[0], "Z")
        finally:
            v.close()

    def test_acord_sense_snap(self):
        v = _visor()
        try:
            v.timeline.set_snap(on=False)
            v.ves_a(2.0)
            self.assertTrue(self._parteix(v, "chord", 1, 15.3))
            starts = [round(float(a.ini), 6) for a in v.acords]
            self.assertIn(15.3, starts)
        finally:
            v.close()

    def test_seccio_amb_snap(self):
        v = _visor()
        try:
            v.ves_a(2.0)
            t = 15.3
            ts = v.timeline._snap(t)
            self.assertTrue(self._parteix(v, "section", 1, t))
            starts = [round(float(s[0]), 6) for s in v.seccions]
            self.assertIn(round(float(ts), 6), starts)
            self.assertEqual(v.seccions[0][2], "A")
            idx = starts.index(round(float(ts), 6))
            self.assertEqual(v.seccions[idx][2], "Z")
        finally:
            v.close()

    def test_tempo_amb_snap(self):
        v = _visor()
        try:
            v.ves_a(2.0)
            t = 15.3
            ts = v.timeline._snap(t)
            self.assertTrue(self._parteix(v, "tempo", 1, t))
            starts = [round(float(tr[0]), 6) for tr in v.tempo_trams]
            self.assertIn(round(float(ts), 6), starts)
        finally:
            v.close()

    def test_si_el_clic_no_val_fa_servir_el_cursor(self):
        v = _visor()
        try:
            v.ves_a(12.0)                  # cursor DINS del 2n acord
            # clic exactament a la vora (10.0): no deixa marge → cursor
            self.assertTrue(self._parteix(v, "chord", 1, 10.0))
            starts = [round(float(a.ini), 6) for a in v.acords]
            self.assertIn(12.0, starts)
        finally:
            v.close()


class TestPosicionsMusicals(_Base):
    """Bloc 1: els segons manen; els compassos derivats es recalculen."""

    def test_canviar_bpm_no_mou_segons_i_recalcula_compassos(self):
        v = _visor()
        try:
            abc = os.path.join(v._carpeta_acords(), "estructura_ABC.csv")

            def files():
                with open(abc, encoding="utf-8") as f:
                    return [r for r in csv.reader(f) if r]

            abans = files()
            h = abans[0]
            i_ini, i_fi = h.index("inici_s"), h.index("fi_s")
            i_ci, i_cf = h.index("compas_ini"), h.index("compas_fi")
            segons_abans = [(r[i_ini], r[i_fi]) for r in abans[1:]]
            compas_abans = [(r[i_ci], r[i_cf]) for r in abans[1:]]

            v.aplica_tempo_trams([(0.0, 10.0, 60.0, 4, 4),
                                  (10.0, 30.0, 90.0, 3, 4)])

            self.assertEqual([(round(float(s[0]), 6), round(float(s[1]), 6))
                              for s in v.seccions],
                             [(0.0, 10.0), (10.0, 20.0), (20.0, 30.0)])
            ara = files()
            h = ara[0]
            i_ini, i_fi = h.index("inici_s"), h.index("fi_s")
            i_ci, i_cf = h.index("compas_ini"), h.index("compas_fi")
            self.assertEqual([(r[i_ini], r[i_fi]) for r in ara[1:]],
                             segons_abans)
            self.assertNotEqual([(r[i_ci], r[i_cf]) for r in ara[1:]],
                                compas_abans)
        finally:
            v.close()


class TestLoopSeleccio(_Base):
    """Bloc 4: «Loop a la selecció» als 3 carrils, unió i undo."""

    def test_un_sol_clip(self):
        v = _visor()
        try:
            v.timeline.select_clip("chord", 1)      # 10–20
            self.assertTrue(v.executa_edicio("loop_seleccio"))
            self.assertTrue(v.loop_on)
            self.assertAlmostEqual(float(v.loop_a), 10.0, places=6)
            self.assertAlmostEqual(float(v.loop_b), 20.0, places=6)
            v.undo()
            self.assertIsNone(v.loop_a)
            self.assertFalse(v.loop_on)
        finally:
            v.close()

    def test_seleccio_mixta_es_la_unio(self):
        v = _visor()
        try:
            v.timeline.select_multi({("chord", 0), ("section", 2),
                                     ("tempo", 1)})
            self.assertTrue(v.executa_edicio("loop_seleccio"))
            self.assertAlmostEqual(float(v.loop_a), 0.0, places=6)
            self.assertAlmostEqual(float(v.loop_b), 30.0, places=6)
        finally:
            v.close()

    def test_sense_seleccio_no_fa_res(self):
        v = _visor()
        try:
            v.timeline.clear_selection()
            avisos = []
            v.infoMissatge.connect(avisos.append)
            self.assertFalse(v.executa_edicio("loop_seleccio"))
            self.assertFalse(v.loop_on)
            self.assertTrue(any("selecci" in a.lower() for a in avisos))
        finally:
            v.close()

    def test_si_sona_alinea_el_cursor(self):
        v = _visor()
        try:
            v.timeline.select_clip("section", 1)    # 10–20
            v.sona = True
            v.pos = 0.0
            self.assertTrue(v.executa_edicio("loop_seleccio"))
            self.assertAlmostEqual(float(v.pos), 10.0, places=6)
        finally:
            v.sona = False
            v.close()

    def test_el_menu_el_te_als_tres_carrils(self):
        v = _visor()
        try:
            for kind in ("chord", "section", "tempo"):
                menu = v._menu_contextual(kind, 0, 5.0)
                textos = [a.text() for a in menu.actions()
                          if not a.isSeparator()]
                self.assertIn("Loop a la selecció", textos, kind)
        finally:
            v.close()


def tearDownModule():
    try:
        import _qt_neteja
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()


if __name__ == "__main__":
    unittest.main()
