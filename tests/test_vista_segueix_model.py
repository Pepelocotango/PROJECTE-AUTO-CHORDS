"""EL VISOR SEGUEIX EL MODEL — xarxa de regressió de les REGLES D'OR.

Regla del preàmbul de `docs/REGLES_DE_LA_APP.md`: «**el que es veu a la pantalla
reflecteix el model vàlid**». Aquest mòdul comprova, **després de cada operació**
d'una tongada pseudo-aleatòria *determinista* (seeds fixos), que:

- **R1** ordre estricte · **R2** contigüitat · **R4** cobertura (0 → durada) ·
  **R8** temps vàlids — a les TRES famílies (acords, estructura, BPM/compàs);
- i que els **items pintats al timeline** quadren amb el model
  (`ChordItem.t/_next_t` vs `acords`; `SectionItem.ini/fi` vs `seccions`;
  `timeline._mapa` vs `tempo_trams`).

⚠️ Per què existeix (19-10-2026): una tongada de 12 h va donar la paritat i les
regles per fetes, però l'operador va veure que **el visor no s'actualitzava bé**.
El fuzzer va trobar el forat real:

1. **Afegir un clip no el pintava**: `_desa_i_regenera()` només refresca el
   timeline si la **cobertura** ha canviat, i afegir una marca DINS de la cançó
   no la canvia → el clip nou no eixia fins que tocaves una altra cosa.
2. **Després d'un gest** la vista es quedava amb la posició **previsual** que
   havien adoptat els items, mentre el model n'havia adoptat una altra
   (acotament del destí, snap, normalització del veí). Cas verificat (seed 9):
   l'item 0 pintat a `(0.000, 0.000)` amb el model ja a `(0.000, 2.000)`.

Els dos s'han arreglat centralitzant la sincronització a
`visor._sincronitza_vista()` (i fent que la criden les **primitives** de mutació,
no cada camí d'usuari).
"""
import os
import random
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
from PyQt5.QtWidgets import QApplication, QInputDialog, QMessageBox  # noqa: E402

from app import pipeline  # noqa: E402
from app import tempo_map as tm  # noqa: E402
from app import visor as visor_mod  # noqa: E402

DUR = 40.0


def _wav():
    td = tempfile.mkdtemp()
    ruta = os.path.join(td, "tema.wav")
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * int(44100 * DUR))
    return ruta


def _visor():
    wav = _wav()
    sortida = pipeline.carpeta_sortida(wav)
    os.makedirs(sortida, exist_ok=True)
    ca = os.path.join(sortida, "acords.csv")
    with open(ca, "w", encoding="utf-8") as f:
        for t, nom in [(0, "C"), (10, "Am"), (20, "F"), (30, "G")]:
            f.write(f"{t},{t + 1},{nom}\n")
    sa = os.path.join(sortida, "estructura_ABC.csv")
    with open(sa, "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n")
        for ini, fi, L in [(0, 10, "A"), (10, 20, "B"), (20, 30, "C"),
                           (30, DUR, "D")]:
            f.write(f"{ini},{fi},{fi - ini},{L},{L},1,1\n")
    v = visor_mod.Visor(wav, ca, sa, 120.0, 4, True)
    v.td, v.sortida, v.abc_csv = os.path.dirname(wav), sortida, sa
    v.aplica_tempo_trams([(0.0, 20.0, 120.0, 4, 4),
                          (20.0, DUR, 120.0, 4, 4)])
    return v


def _families(v):
    return [("acords", [(float(c.ini), float(c.fi)) for c in v.acords]),
            ("seccions", [(float(s[0]), float(s[1])) for s in v.seccions]),
            ("tempo", [(float(t[0]), float(t[1]))
                       for t in (v.tempo_trams or [])])]


def _viola_regles(v):
    fall = []
    for nom, clips in _families(v):
        if not clips:
            fall.append(f"[{nom}] R4: carril buit")
            continue
        if abs(clips[0][0]) > 1e-6:
            fall.append(f"[{nom}] R4: comença a {clips[0][0]} (no a 0)")
        if abs(clips[-1][1] - DUR) > 1e-3:
            fall.append(f"[{nom}] R4: acaba a {clips[-1][1]:.4f} (no a {DUR})")
        for i, (ini, fi) in enumerate(clips):
            if ini < -1e-6:
                fall.append(f"[{nom}] R8: inici negatiu {ini}")
            if fi - ini <= 1e-6:
                fall.append(f"[{nom}] R8: durada <= 0 al clip {i}")
            if i and abs(clips[i - 1][1] - ini) > 1e-3:
                fall.append(f"[{nom}] R2: forat/encavalcament entre {i-1} i {i}")
    return fall


def _viola_vista(v):
    """Els items PINTATS han d'encarnar el model (regla del preàmbul)."""
    tl = v.timeline
    fall = []
    if len(tl._chord_items) != len(v.acords):
        fall.append(f"[vista acords] pintats={len(tl._chord_items)} != "
                    f"model={len(v.acords)}")
    else:
        for i, (it, c) in enumerate(zip(tl._chord_items, v.acords)):
            if (abs(it.t - float(c.ini)) > 1e-3
                    or abs(it._next_t - float(c.fi)) > 1e-3):
                fall.append(f"[vista acords] item {i}=({it.t:.3f},"
                            f"{it._next_t:.3f}) != model=({float(c.ini):.3f},"
                            f"{float(c.fi):.3f})")
                break
    if len(tl._section_items) != len(v.seccions):
        fall.append(f"[vista seccions] pintats={len(tl._section_items)} != "
                    f"model={len(v.seccions)}")
    else:
        for i, (it, s) in enumerate(zip(tl._section_items, v.seccions)):
            if (abs(it.ini - float(s[0])) > 1e-3
                    or abs(it.fi - float(s[1])) > 1e-3):
                fall.append(f"[vista seccions] item {i}=({it.ini:.3f},"
                            f"{it.fi:.3f}) != model=({float(s[0]):.3f},"
                            f"{float(s[1]):.3f})")
                break
    trams = v.tempo_trams or []
    if trams and tl._mapa is None:
        fall.append("[vista tempo] el timeline no té mapa (pista no pintable)")
    elif tl._mapa is not None and len(tl._mapa.trams) != len(trams):
        fall.append(f"[vista tempo] _mapa={len(tl._mapa.trams)} != "
                    f"model={len(trams)}")
    return fall


# ── les operacions (les mateixes eines que l'usuari, inclosos els GESTOS) ────
def _ops(r):
    v_ops = [
        ("afegeix acord",
         lambda v: v._afegeix_a_la_posicio("chord", r.uniform(0, DUR))),
        ("afegeix seccio",
         lambda v: v._afegeix_a_la_posicio("section", r.uniform(0, DUR))),
        ("elimina acord",
         lambda v: (v._elimina_acord_index(r.randrange(len(v.acords)))
                    if len(v.acords) > 1 else None)),
        ("elimina seccio",
         lambda v: (v._elimina_seccio_index(r.randrange(len(v.seccions)))
                    if len(v.seccions) > 1 else None)),
        ("duplica acord",
         lambda v: v._duplica_acord_index(r.randrange(len(v.acords)))),
        ("duplica seccio",
         lambda v: v._duplica_seccio_index(r.randrange(len(v.seccions)))),
        ("partir acord meitat",
         lambda v: v.parteix_per_la_meitat("chord",
                                           r.randrange(len(v.acords)))),
        ("partir tram meitat",
         lambda v: v._parteix_tram_per_la_meitat(
             r.randrange(len(v.tempo_trams or [])))),
        ("afegeix tall tempo",
         lambda v: v.aplica_tempo_trams(tm.afegeix_tall(
             list(v.tempo_trams or []), r.uniform(0, DUR)))),
        ("elimina seleccio mixta",
         lambda v: v._elimina_seleccio(
             [("chord", r.randrange(len(v.acords))),
              ("tempo", r.randrange(len(v.tempo_trams or [])))])),
        ("duplica seleccio",
         lambda v: v._duplica_seleccio(
             [("section", r.randrange(len(v.seccions)))])),
        ("gest mou inici acord", lambda v: _gest(v, r, "mou_inici_acord")),
        ("gest estira fi acord", lambda v: _gest(v, r, "estira_fi_acord")),
        ("gest mou seccio", lambda v: _gest(v, r, "mou_seccio")),
        ("gest cos acord", lambda v: _gest(v, r, "cos_acord")),
        ("gest cos seccio", lambda v: _gest(v, r, "cos_seccio")),
        ("gest frontera tempo", lambda v: _gest(v, r, "frontera_tempo")),
        ("desfer/refer", lambda v: (v.undo(),
                                    v.redo() if r.random() < 0.5 else None)),
    ]
    return r.choice(v_ops)


def _gest(v, r, tipus):
    """Gest del ratolí, pel MATEIX contracte que la GUI (`_emit_edit_finished`)."""
    tl = v.timeline
    if tipus == "mou_inici_acord":
        i = r.randrange(len(v.acords))
        tl._on_chord_time_changed(i, float(v.acords[i].ini) + r.uniform(-6, 6))
    elif tipus == "estira_fi_acord":
        i = r.randrange(len(v.acords))
        tl._on_chord_end_changed(i, float(v.acords[i].fi) + r.uniform(-6, 6))
    elif tipus == "mou_seccio":
        i = r.randrange(len(v.seccions))
        ini, fi = float(v.seccions[i][0]), float(v.seccions[i][1])
        d = r.uniform(-6, 6)
        tl._on_section_changed(i, ini + d, fi + d)
    elif tipus == "cos_acord":
        i = r.randrange(len(v.acords))
        tl._on_chord_body_drag(i, float(v.acords[i].ini) + r.uniform(-10, 10))
    elif tipus == "cos_seccio":
        i = r.randrange(len(v.seccions))
        ini, fi = float(v.seccions[i][0]), float(v.seccions[i][1])
        d = r.uniform(-10, 10)
        tl._on_section_body_drag(i, ini + d, fi + d)
    elif tipus == "frontera_tempo":
        trams = v.tempo_trams or []
        if len(trams) < 2:
            return
        i = r.randrange(len(trams))
        vora = r.choice(["ini", "fi"])
        base = float(trams[i][0]) if vora == "ini" else float(trams[i][1])
        v._on_tempo_mogut(i, vora, base + r.uniform(-8, 8))
        tl.editFinished.emit()
        return
    tl._emit_edit_finished()


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        # Cap diàleg emergent pot penjar la suite (mateix patró que altres tests).
        self._p = [patch.object(QInputDialog, "getText",
                                return_value=("Z", True))]
        for m in ("warning", "information", "critical"):
            self._p.append(patch.object(QMessageBox, m,
                                        return_value=QMessageBox.Ok))
        for p in self._p:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self._p])


class TestFuzzerReglesIVista(_Base):
    """Tongada pseudo-aleatòria, amb seeds FIXOS (reproduïble, no flaky)."""

    def _tongada(self, seed, n):
        r = random.Random(seed)
        v = _visor()
        for pas in range(n):
            nom, op = _ops(r)
            try:
                op(v)
            except Exception as e:          # noqa: BLE001
                self.fail(f"seed {seed} pas {pas}: l'operacio ha petat: "
                          f"{type(e).__name__}: {e}")
            self._app.processEvents()       # com la GUI: buida els renders diferits
            fall = _viola_regles(v) + _viola_vista(v)
            self.assertFalse(
                fall, f"seed {seed} pas {pas} ({nom}): violacio de regla/vista: "
                      f"{fall}")
        return v

    def test_tongada_llarga(self):
        """Seeds 9 i 15: són els que **detecten** el bug del gest (la vista es
        quedava amb la posició previsual). Verificat per mutació — no els
        traguis ni rebaixis `n` per davall de 60 (el cas ix al pas 56 / 48)."""
        for seed in (9, 15):
            self._tongada(seed, 60)

    def test_tongada_general(self):
        for seed in (1, 2):
            self._tongada(seed, 40)


class TestElsDosBugsDeLaRonda12h(_Base):
    """Els dos casos concrets que van fer dir «el visor no actualitza bé»."""

    def test_afegir_un_acord_es_pinta_a_l_instant(self):
        v = _visor()
        n = len(v.acords)
        v._afegeix_a_la_posicio("chord", 25.0)
        self.assertEqual(len(v.acords), n + 1)
        # SENSE processEvents: l'alta ha de pintar-se ja (el bug era aquest)
        self.assertEqual(len(v.timeline._chord_items), n + 1,
                         "l'acord nou no s'ha pintat al timeline")
        self._app.processEvents()
        self.assertFalse(_viola_vista(v), _viola_vista(v))

    def test_afegir_una_seccio_es_pinta_a_l_instant(self):
        v = _visor()
        n = len(v.seccions)
        v._afegeix_a_la_posicio("section", 22.0)
        self.assertEqual(len(v.seccions), n + 1)
        self.assertEqual(len(v.timeline._section_items), n + 1)
        self.assertFalse(_viola_vista(v), _viola_vista(v))

    def test_la_primitiva_d_afegir_tambe_refresca(self):
        """Cap camí (ni els futurs) no s'ha de poder oblidar de refrescar."""
        v = _visor()
        n = len(v.acords)
        v._afegeix_acord(25.0, "G")
        self.assertEqual(len(v.timeline._chord_items), n + 1)

    def test_gest_arrossegament_acaba_quadrant_amb_el_model(self):
        v = _visor()
        i = 1
        ini, fi = float(v.seccions[i][0]), float(v.seccions[i][1])
        v.timeline._on_section_body_drag(i, ini + 7, fi + 7)
        v.timeline._emit_edit_finished()     # el contracte del release de la GUI
        self._app.processEvents()
        self.assertFalse(_viola_vista(v), _viola_vista(v))
        self.assertFalse(_viola_regles(v), _viola_regles(v))

    def test_estirar_una_vora_acaba_quadrant(self):
        v = _visor()
        v.timeline._on_chord_end_changed(0, 25.0)
        v.timeline._emit_edit_finished()
        self._app.processEvents()
        self.assertFalse(_viola_vista(v), _viola_vista(v))


def tearDownModule():
    import _qt_neteja
    _qt_neteja.processa_esborrats()


if __name__ == "__main__":
    unittest.main()
