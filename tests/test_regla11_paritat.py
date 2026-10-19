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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene dels tests: l'import té efecte (esborra els temporals en plegar)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PyQt5.QtWidgets import (  # noqa: E402
    QApplication, QInputDialog, QListWidget, QMenu)
from unittest.mock import patch  # noqa: E402

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
        # El RESSALTAT VISUAL de la pista ha de seguir la seleccio (prova de
        # mutacio 18-10-2026: sense aixo, trencar `_sync_selection_visual` no
        # feia petar cap test).
        tl.select_clip("tempo", 1)
        self.assertEqual(tl._tempo_lane._sel, 1)
        tl.clear_selection()
        self.assertEqual(tl._tempo_lane._sel, -1)

    def test_porta_retalls_dels_trams_de_tempo(self):
        """Copiar/enganxar, duplicar i retallar trams de BPM/compàs (#11)."""
        v = _visor()
        v.aplica_tempo_trams([(0.0, 6.0, 120.0, 4, 4), (6.0, DUR, 90.0, 3, 4)])
        tl = v.timeline

        def est():
            return [(round(float(t[0]), 2), round(float(t[1]), 2), t[2])
                    for t in v.tempo_trams]

        tl.select_clip("tempo", 0)
        tl.copy_selection()
        tl.set_position(12.0, snap=False)
        tl.paste_at_cursor()
        self.assertEqual(est(), [(0.0, 6.0, 120.0), (6.0, 12.0, 90.0),
                                 (12.0, 18.0, 120.0), (18.0, DUR, 90.0)])
        v.undo()
        self.assertEqual(est(), [(0.0, 6.0, 120.0), (6.0, DUR, 90.0)])
        # Ctrl+D: la còpia va DESPRÉS del bloc i n'hereta el BPM/compàs
        v._duplica_seleccio([("tempo", 0)])
        self.assertEqual([(t[0], t[2]) for t in est()],
                         [(0.0, 120.0), (6.0, 120.0), (12.0, 90.0)])
        v.undo()
        # Retallar: el tram esborrat deixa que el veí ocupi el seu espai
        tl.select_clip("tempo", 0)
        tl.cut_selection()
        self.assertEqual(est(), [(0.0, DUR, 90.0)])
        v.undo()
        self.assertEqual(est(), [(0.0, 6.0, 120.0), (6.0, DUR, 90.0)])

    def test_operacions_mixtes_les_tres_families(self):
        """Una sola operacio sobre les TRES families alhora (R11 cami a cami).

        Seleccionar un acord, una seccio i un tram i esborrar-los ha de ser UNA
        operacio de desfer; una copia mixta tambe s'enganxa tota de cop i es
        reverteix amb un sol Ctrl+Z (i es torna a fer amb Ctrl+Y).
        """
        v = _visor()
        v.aplica_tempo_trams([(0.0, 10.0, 120.0, 4, 4),
                              (10.0, DUR, 90.0, 3, 4)])

        def estat():
            return ([c.payload[0] for c in v.acords],
                    [s[2] for s in v.seccions],
                    [len(v.tempo_trams or [])])

        base = estat()
        v._elimina_seleccio([("chord", 0), ("section", 1), ("tempo", 1)])
        self.assertEqual(estat(), (["N", "Am", "F"], ["A", "C"], [1]))
        v.undo()
        self.assertEqual(estat(), base)
        v.redo()
        self.assertEqual(estat(), (["N", "Am", "F"], ["A", "C"], [1]))
        v.undo()
        self.assertEqual(estat(), base)
        # copia mixta (acord + tram) i enganxa: tot de cop, un sol desfer
        tl = v.timeline
        tl.select_multi({("chord", 0), ("tempo", 0)})
        tl.copy_selection()
        tl.set_position(5.0, snap=False)
        tl.paste_at_cursor()
        self.assertEqual([c.payload[0] for c in v.acords],
                         ["C", "C", "Am", "F"])
        self.assertEqual([t[2] for t in v.tempo_trams],
                         [120.0, 120.0, 120.0, 90.0])
        v.undo()
        self.assertEqual(estat(), base)

    def test_la_seleccio_del_loop_inclou_els_trams(self):
        """El LOOP selecciona tambe els trams de BPM/compàs (es poden copiar)."""
        v = _visor()
        v.aplica_tempo_trams([(0.0, 6.0, 120.0, 4, 4), (6.0, DUR, 90.0, 3, 4)])
        v.loop_a, v.loop_b = 2.0, 8.0
        n = v.selecciona_bloc_del_loop()
        self.assertTrue(n)
        self.assertIn(("tempo", 1), v.timeline.selected_keys())

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


def _claus_menu(fn, *args):
    """Les CLAUS de les accions (`QAction.data()`) + si estan actives.

    Serveix per comparar **l'operació** entre carrils: la redacció sí que canvia
    («Afegeix acord aquí» / «Afegeix un canvi aquí»), l'operació NO.
    """
    capt = {}
    orig = QMenu.exec_

    def fake(self, pos, *rest):
        acts = [a for a in self.actions() if not a.isSeparator()]
        capt["claus"] = [a.data() for a in acts]
        capt["actiu"] = [a.isEnabled() for a in acts]
        return None
    QMenu.exec_ = fake
    try:
        fn(*args)
    finally:
        QMenu.exec_ = orig
    return capt.get("claus", []), capt.get("actiu", [])


def _tria_menu(fn, text, *args):
    """Crida `fn` fent veure que l'usuari tria l'acció que conté `text`."""
    trobat = {"ok": False}

    def fake(self, pos, *rest):
        for a in self.actions():
            if not a.isSeparator() and text.lower() in a.text().lower():
                trobat["ok"] = True
                return a
        return None
    orig = QMenu.exec_
    QMenu.exec_ = fake
    try:
        fn(*args)
    finally:
        QMenu.exec_ = orig
    return trobat["ok"]


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
        # 11 accions = la definició ÚNICA del menú contextual (regla #11),
        # compartida amb el timeline (abans la llista en tenia 7 i el timeline 9).
        self.assertEqual(len(ac), 11, f"joc inesperat: {ac}")
        # Mateixa estructura (activació) i mateixa paraula de tipus a cada posició.
        self.assertEqual([e for _t, e in ac], [e for _t, e in se])
        self.assertIn("acord", ac[0][0].lower())
        self.assertIn("secció", se[0][0].lower())
        self.assertIn("acord", ac[3][0].lower())
        self.assertIn("secció", se[3][0].lower())

    def test_les_cinc_superficies_tenen_el_mateix_menu(self):
        """③ BPM/compàs + ④ estructura + ⑤ acords, al TIMELINE i a les LLISTES.

        Regla d'or #11: **una sola definició** de menú (`_menu_contextual`) per a
        totes les superfícies → mateixa OPERACIÓ, mateix ordre i mateixa
        activació. La redacció sí que pot canviar («Afegeix acord aquí» vs
        «Afegeix un canvi aquí»), per això es comparen les **claus**.
        """
        v = _visor()
        v.aplica_tempo_trams([(0.0, 10.0, 120.0, 4, 4),
                              (10.0, DUR, 90.0, 3, 4)])
        orig = QListWidget.indexAt
        QListWidget.indexAt = lambda self, pos: _Fila(0)
        try:
            jocs = {
                "TL acords": _claus_menu(v._on_clip_context_menu, "chord", 0,
                                         QPoint(0, 0), 3.0),
                "TL estructura": _claus_menu(v._on_clip_context_menu, "section",
                                             0, QPoint(0, 0), 3.0),
                "TL BPM": _claus_menu(v._on_tempo_menu, 0, 3.0),
                "LLISTA acords": _claus_menu(v._menu_acord, QPoint(1, 1)),
                "LLISTA estructura": _claus_menu(v._menu_seccio, QPoint(1, 1)),
            }
        finally:
            QListWidget.indexAt = orig
        base_claus, base_actiu = jocs["TL acords"]
        self.assertEqual(base_claus, [
            "afegeix", "duplica", "elimina", "reanomena", "parteix", "meitat",
            "fusiona_anterior", "fusiona_seguent", "retalla", "copia", "enganxa",
        ])
        for nom, (claus, actiu) in jocs.items():
            self.assertEqual(claus, base_claus,
                             f"«{nom}» no té el mateix joc/ordre d'operacions")
            self.assertEqual(actiu, base_actiu,
                             f"«{nom}» té una activació diferent")

    def test_l_operacio_que_nomes_era_a_les_llistes_ara_hi_es_a_tot_arreu(self):
        """«Fusionar amb anterior/seguint» existia només a les llistes."""
        v = _visor()
        v.aplica_tempo_trams([(0.0, 10.0, 120.0, 4, 4),
                              (10.0, DUR, 90.0, 3, 4)])
        for etq, args in (("TL acords", ("chord", 1, QPoint(0, 0), 3.0)),
                          ("TL estructura", ("section", 1, QPoint(0, 0), 3.0)),
                          ("TL BPM", (1, 3.0))):
            fn = v._on_tempo_menu if etq == "TL BPM" else v._on_clip_context_menu
            claus, actiu = _claus_menu(fn, *args)
            self.assertIn("fusiona_anterior", claus)
            self.assertIn("fusiona_seguent", claus)
            d = dict(zip(claus, actiu))
            self.assertTrue(d["fusiona_anterior"],
                            f"«{etq}»: amb un clip anterior, ha d'estar activa")

    def test_els_menus_tenen_les_onze_accions_esperades(self):
        """La llista blanca de les 11 accions (canviar-la és una decisió)."""
        v = _visor()
        v.aplica_tempo_trams([(0.0, 10.0, 120.0, 4, 4),
                              (10.0, DUR, 90.0, 3, 4)])
        joc = [t for t, _e in _captura_menu(v._on_tempo_menu, 0, 3.0)]
        self.assertEqual(joc, [
            "Afegeix un canvi aquí",
            "Duplica", "Elimina",
            "Reanomena (BPM/compàs)…",
            "Parteix aquest tros aquí", "Partir per la meitat",
            "Fusionar amb anterior", "Fusionar amb següent",
            "Retalla", "Copia", "Enganxa",
        ])

    def test_menu_contextual_parteix_per_a_tots_dos(self):
        v = _visor()
        ac = _captura_menu(v._on_clip_context_menu, "chord", 0, QPoint(0, 0))
        se = _captura_menu(v._on_clip_context_menu, "section", 0, QPoint(0, 0))
        self.assertTrue(dict(ac).get("Parteix l'acord…"),
                        f"hauria d'estar actiu sobre un acord: {ac}")
        self.assertTrue(dict(se).get("Parteix la secció…"),
                        f"hauria d'estar actiu sobre una secció: {se}")

    # ── ③ BPM/compàs: paritat amb ④ i ⑤ (report de l'operador, 19-10-2026) ──

    def _tres_menus(self):
        """Els tres menús contextuals amb un estat equivalent (idx 0 actiu)."""
        v = _visor()
        v.aplica_tempo_trams([(0.0, 10.0, 120.0, 4, 4),
                              (10.0, DUR, 90.0, 3, 4)])
        ac = _captura_menu(v._on_clip_context_menu, "chord", 0,
                           QPoint(0, 0), 3.0)
        se = _captura_menu(v._on_clip_context_menu, "section", 0,
                           QPoint(0, 0), 3.0)
        tp = _captura_menu(v._on_tempo_menu, 0, 3.0)
        return v, ac, se, tp

    def test_els_tres_menus_tenen_el_mateix_joc(self):
        """La pista ③ obre EL MATEIX joc d'accions que ④ i ⑤ (regla #11)."""
        _v, ac, se, tp = self._tres_menus()
        self.assertEqual(len(ac), len(se))
        self.assertEqual(len(ac), len(tp),
                         f"③ ha de tenir el mateix nombre d'accions:\n"
                         f"④/⑤={ac}\n③={tp}")
        self.assertEqual([e for _t, e in ac], [e for _t, e in se])
        self.assertEqual([e for _t, e in ac], [e for _t, e in tp],
                         f"activació diferent:\n④/⑤={ac}\n③={tp}")

    def test_l_afegeix_es_el_primer_a_les_tres(self):
        """Cada pista té el seu «Afegeix … aquí» al capdamunt i actiu."""
        _v, ac, se, tp = self._tres_menus()
        self.assertEqual(ac[0][0], "Afegeix acord aquí")
        self.assertEqual(se[0][0], "Afegeix secció aquí")
        self.assertEqual(tp[0][0], "Afegeix un canvi aquí")
        for joc in (ac, se, tp):
            self.assertTrue(joc[0][1], f"l'afegeix ha d'estar actiu: {joc}")

    def test_menu_tempo_afegeix_un_canvi(self):
        v, _ac, _se, _tp = self._tres_menus()
        self.assertTrue(
            _tria_menu(v._on_tempo_menu, "Afegeix un canvi", 0, 7.0))
        self.assertEqual([(round(float(t[0]), 2), round(float(t[1]), 2))
                          for t in v.tempo_trams],
                         [(0.0, 7.0), (7.0, 10.0), (10.0, DUR)])
        # la frontera nova HERETA el tempo/compàs del tros on cau
        self.assertEqual(v.tempo_trams[1][2:4], (120.0, 4))
        v.undo()
        self.assertEqual(len(v.tempo_trams), 2)

    def test_menu_tempo_parteix_per_la_meitat(self):
        v, _ac, _se, _tp = self._tres_menus()
        self.assertTrue(
            _tria_menu(v._on_tempo_menu, "Partir per la meitat", 0, 3.0))
        self.assertEqual([(round(float(t[0]), 2), round(float(t[1]), 2), t[2])
                          for t in v.tempo_trams],
                         [(0.0, 5.0, 120.0), (5.0, 10.0, 120.0),
                          (10.0, DUR, 90.0)])
        v.undo()
        self.assertEqual(len(v.tempo_trams), 2)

    def test_menu_tempo_duplica(self):
        v, _ac, _se, _tp = self._tres_menus()
        self.assertTrue(_tria_menu(v._on_tempo_menu, "Duplica", 0, 3.0))
        self.assertEqual([t[2] for t in v.tempo_trams], [120.0, 120.0, 90.0])
        v.undo()
        self.assertEqual(len(v.tempo_trams), 2)

    def test_menu_tempo_copia_i_enganxa(self):
        v, _ac, _se, _tp = self._tres_menus()
        self.assertTrue(_tria_menu(v._on_tempo_menu, "Copia", 0, 3.0))
        self.assertTrue(v.timeline.has_clipboard())
        v.timeline.set_position(15.0, snap=False)
        _tria_menu(v._on_tempo_menu, "Enganxa", 0, 3.0)
        # el bloc [0,10]=120 s'ha enganxat sobre [15,25]
        self.assertEqual([(round(float(t[0]), 2), round(float(t[1]), 2), t[2])
                          for t in v.tempo_trams],
                         [(0.0, 10.0, 120.0), (10.0, 15.0, 90.0),
                          (15.0, 25.0, 120.0), (25.0, DUR, 90.0)])

    def test_menu_acord_afegeix_a_la_posicio_del_clic(self):
        """«Afegeix acord aquí» cau a l'instant del CLIC, no al cursor."""
        v, _ac, _se, _tp = self._tres_menus()
        n0 = len(v.acords)
        with patch.object(QInputDialog, "getText", return_value=("G", True)):
            self.assertTrue(
                _tria_menu(v._on_clip_context_menu, "Afegeix acord",
                           "chord", 0, QPoint(0, 0), 3.0))
        self.assertEqual(len(v.acords), n0 + 1)
        self.assertAlmostEqual(float(v.acords[1].ini), 3.0, places=6)
        self.assertEqual(v.acords[1].payload[0], "G")
        v.undo()
        self.assertEqual(len(v.acords), n0)

    def test_menu_seccio_afegeix_a_la_posicio_del_clic(self):
        """AFEGIR secció = PARTIR la que conté el punt (model saturat).

        La versió anterior afegia un tros de 2 s que solapava → l'add petava
        SEMPRE (llista i timeline). Ara parteix, com diu `parteix_seccio`.
        """
        v, _ac, _se, _tp = self._tres_menus()
        n0 = len(v.seccions)
        with patch.object(QInputDialog, "getText",
                          side_effect=[("B2", True), ("B2", True)]):
            self.assertTrue(
                _tria_menu(v._on_clip_context_menu, "Afegeix secció",
                           "section", 0, QPoint(0, 0), 12.0))
        self.assertEqual(len(v.seccions), n0 + 1)
        self.assertEqual([round(float(s[1]), 2) for s in v.seccions][:3],
                         [10.0, 12.0, 20.0])
        self.assertEqual(v.seccions[2][2], "B2")
        v.undo()
        self.assertEqual(len(v.seccions), n0)

    def test_llista_afegeix_seccio_tambe_parteix(self):
        """El «Afegeix secció aquí» de la LLISTA tenia el mateix bug."""
        v = _visor()
        orig = QListWidget.indexAt
        QListWidget.indexAt = lambda self, pos: _Fila(0)
        try:
            v.pos = 12.0
            with patch.object(QInputDialog, "getText",
                              side_effect=[("Z", True), ("Z", True)]):
                self.assertTrue(_tria_menu(v._menu_seccio,
                                           "Afegeix secció", QPoint(1, 1)))
        finally:
            QListWidget.indexAt = orig
        self.assertIn("Z", [s[2] for s in v.seccions])


class TestMenuPrincipalParitat(_Base):
    """El menú principal ha de tindre les MATEIXES operacions a les 3 pistes.

    Era l'última superfície amb forat: hi havia «Afegeix acord…» i «Afegeix
    secció…» (i els dos «Parteix … al cursor…»), però **res** per a ③.
    """

    def _finestra(self):
        import tempfile
        from app import config
        from app import main as app_main
        td = tempfile.mkdtemp()
        p = patch.object(config, "DADES_DIR", td)
        p.start()
        self.addCleanup(p.stop)
        f = app_main.Finestra()
        self.addCleanup(self._tanca, f)
        return f

    @staticmethod
    def _tanca(f):
        import _qt_neteja
        f.dirty = False
        _qt_neteja.tanca_i_destrueix(f)

    def _menu_edita(self, f):
        for a in f.menuBar().actions():
            if "edita" in a.text().replace("&", "").lower():
                return a.menu()
        return None

    def test_les_tres_pistes_tenen_afegeix_i_parteix(self):
        f = self._finestra()
        m = self._menu_edita(f)
        self.assertIsNotNone(m, "no trobo el menu Edita")
        textos = [a.text() for a in m.actions()]
        for esperat in ("Afegeix acord…", "Afegeix secció…",
                        "Afegeix tram de tempo/compàs…",
                        "Parteix l'acord al cursor…",
                        "Parteix la secció al cursor…",
                        "Parteix el tram al cursor…"):
            self.assertIn(esperat, textos,
                          f"falta «{esperat}» al menu Edita: {textos}")

    def test_afegeix_i_parteix_tram_funcionen(self):
        """I fan la feina (no només hi són)."""
        f = self._finestra()
        v = _visor()
        f.visor_ref = v
        n0 = len(v.tempo_trams or [])
        v.pos = 12.0
        f._afegeix_tram_ui()
        self.assertEqual(len(v.tempo_trams), n0 + 1,
                         "«Afegeix tram» ha d'obrir una frontera nova")
        v.pos = 14.0
        n1 = len(v.tempo_trams)
        f._parteix_tram_ui()
        self.assertEqual(len(v.tempo_trams), n1 + 1,
                         "«Parteix el tram» ha de partir-lo pel cursor")


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
