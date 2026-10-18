"""Paritat d'ACCIONS MCP ↔ GUI: tot el que l'usuari pot fer, l'MCP també.

Aquí provem les eines noves del 17-10-2026 **amb la Finestra REAL** (i el seu
visor/timeline reals): porta-retalls (copiar/retallar/enganxar), esborrar/
duplicar/reanomenar la SELECCIÓ, selecció per rang i del loop, nudge, moure un
bloc d'acords, troba i reemplaça, revertir, netejar el loop, l'eina del
timeline i els commutadors d'incloure estructura/partitura.

Cap crida ha de poder obrir un diàleg modal (deixaria l'agent penjat): els
tests deixen el pont «actiu» (`mcp_actiu`) on toca i cap diàleg s'ha d'obrir.
"""
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app import main as app_main  # noqa: E402
from app import mcp_bridge  # noqa: E402

DURADA_S = 10
# C[0,2) Am[2,4) F[4,6) G[6,8) Em[8,10)
ACORDS = "0.0,2.0,C\n2.0,4.0,Am\n4.0,6.0,F\n6.0,8.0,G\n8.0,10.0,Em\n"
SECCIONS = ("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
            "0.0,4.0,4.0,A,A,1.1,5.1\n"
            "4.0,8.0,4.0,B,B,5.1,9.1\n"
            "8.0,10.0,2.0,B,B,9.1,11.1\n")

_VIVES = []


def _ctx(w):
    return mcp_bridge._Context(w)


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = (app_main.QApplication.instance()
                    or app_main.QApplication([]))

    def _finestra(self, acords=ACORDS, seccions=SECCIONS):
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "tema.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * DURADA_S)
        sortida = os.path.join(td, "AUTOCHORDS_tema")
        os.makedirs(sortida, exist_ok=True)
        with open(os.path.join(sortida, "acords.csv"), "w",
                  encoding="utf-8") as f:
            f.write(acords)
        with open(os.path.join(sortida, "estructura_ABC.csv"), "w",
                  encoding="utf-8") as f:
            f.write(seccions)
        w = app_main.Finestra()
        w.wav_edit.setText(wav)
        w._carrega_visor(wav)
        _VIVES.append(w)
        return w

    def tearDown(self):
        try:
            import _qt_neteja
        except ImportError:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import _qt_neteja
        ws, _VIVES[:] = _VIVES[:], []
        _qt_neteja.tanca_i_destrueix(*ws)

    # -- helpers -------------------------------------------------------------
    def _acords(self, w):
        return [(round(float(a[0]), 3), a[2][0]) for a in w.visor_ref.acords]

    def _selecciona(self, w, *keys):
        w.visor_ref.timeline.select_multi({(k, i) for (k, i) in keys})


class TestMapaTempo(_Base):
    """Eines MCP del MAPA de BPM/compàs (el mirall del que fa la GUI)."""

    def test_list_tempo(self):
        w = self._finestra()
        w.visor_ref.aplica_tempo_trams([(0.0, 4.0, 120.0, 4, 4),
                                        (4.0, DURADA_S, 90.0, 3, 4)])
        r = mcp_bridge._op_list_tempo(_ctx(w), {})
        self.assertEqual(len(r["trams"]), 2)
        self.assertEqual(r["trams"][1]["bpm"], 90.0)
        self.assertEqual(r["trams"][1]["bpb"], 3)
        w.close()

    def test_afegeix_i_elimina_tall(self):
        w = self._finestra()
        w.visor_ref.aplica_tempo_trams([(0.0, DURADA_S, 120.0, 4, 4)])
        mcp_bridge._op_afegeix_tall(_ctx(w), {"t_s": 4.0})
        self.assertEqual(len(w.visor_ref.tempo_trams), 2)
        self.assertAlmostEqual(float(w.visor_ref.tempo_trams[1][0]), 4.0,
                               places=3)
        mcp_bridge._op_elimina_tall(_ctx(w), {"index": 1})
        self.assertEqual(len(w.visor_ref.tempo_trams), 1)
        w.close()

    def test_elimina_l_unic_tram_dona_error(self):
        w = self._finestra()
        w.visor_ref.aplica_tempo_trams([(0.0, DURADA_S, 120.0, 4, 4)])
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_elimina_tall(_ctx(w), {"index": 0})
        w.close()

    def test_mou_tall(self):
        w = self._finestra()
        w.visor_ref.aplica_tempo_trams([(0.0, 4.0, 120.0, 4, 4),
                                        (4.0, DURADA_S, 90.0, 3, 4)])
        mcp_bridge._op_mou_tall(_ctx(w), {"index": 1, "t_s": 6.0})
        self.assertAlmostEqual(float(w.visor_ref.tempo_trams[0][1]), 6.0,
                               places=3)
        w.close()


class TestPortaRetalls(_Base):
    def test_copiar_i_enganxar_sobreescriu(self):
        w = self._finestra()
        # Copiem [Am,F] (2 clips, 4 s) i enganxem a 8 s → sobreescriu el tram
        self._selecciona(w, ("chord", 1), ("chord", 2))
        mcp_bridge._op_copia_seleccio(_ctx(w), {})
        mcp_bridge._op_enganxa_seleccio(_ctx(w), {"t_s": 6.0})
        noms = [n for _t, n in self._acords(w)]
        self.assertGreaterEqual(noms.count("Am"), 1)
        w.close()

    def test_retallar_treu_la_seleccio(self):
        w = self._finestra()
        n0 = len(w.visor_ref.acords)
        self._selecciona(w, ("chord", 1), ("chord", 2))
        mcp_bridge._op_retalla_seleccio(_ctx(w), {})
        # El porta-retalls queda ple i el model ha perdut marques
        self.assertTrue(w.visor_ref.timeline.has_clipboard())
        self.assertLess(len(w.visor_ref.acords), n0)
        w.close()

    def test_enganxar_sense_porta_retalls_dona_error(self):
        w = self._finestra()
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_enganxa_seleccio(_ctx(w), {})
        w.close()

    def test_copiar_sense_seleccio_dona_error(self):
        w = self._finestra()
        w.visor_ref.timeline.clear_selection()
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_copia_seleccio(_ctx(w), {})
        w.close()


class TestSeleccioEdicio(_Base):
    def test_esborra_seleccio(self):
        w = self._finestra()
        n0 = len(w.visor_ref.acords)
        self._selecciona(w, ("chord", 1), ("chord", 2))
        mcp_bridge._op_esborra_seleccio(_ctx(w), {})
        self.assertLess(len(w.visor_ref.acords), n0)
        w.close()

    def test_duplica_seleccio(self):
        w = self._finestra()
        self._selecciona(w, ("chord", 1))
        mcp_bridge._op_duplica_seleccio(_ctx(w), {})
        # La còpia va DESPRÉS i sobreescriu (§2): el recompte pot no créixer.
        self.assertEqual([n for _t, n in self._acords(w)],
                         ["C", "Am", "Am", "G", "Em"])
        w.close()

    def test_renomena_seleccio(self):
        w = self._finestra()
        self._selecciona(w, ("chord", 1), ("chord", 2))
        mcp_bridge._op_renomena_seleccio(_ctx(w), {"nom": "CMaj7"})
        noms = [n for _t, n in self._acords(w)]
        self.assertEqual(noms.count("CMaj7"), 2)
        w.close()

    def test_renomena_seleccio_sense_nom_dona_error(self):
        w = self._finestra()
        self._selecciona(w, ("chord", 1), ("chord", 2))
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_renomena_seleccio(_ctx(w), {})
        w.close()

    def test_selecciona_rang(self):
        w = self._finestra()
        r = mcp_bridge._op_selecciona_rang(_ctx(w), {"t0": 1.0, "t1": 5.0,
                                                     "kind": "chord"})
        idxs = sorted(i for k, i in r["seleccio"] if k == "chord")
        self.assertEqual(idxs, [1, 2])       # Am (2 s) i F (4 s)
        w.close()

    def test_selecciona_loop(self):
        w = self._finestra()
        vr = w.visor_ref
        vr.ves_a(2.0)
        mcp_bridge._op_mark_loop_a(_ctx(w), {})
        vr.ves_a(6.0)
        mcp_bridge._op_mark_loop_b(_ctx(w), {})
        r = mcp_bridge._op_selecciona_loop(_ctx(w), {})
        self.assertTrue(r["seleccio"])
        w.close()

    def test_selecciona_loop_sense_loop_dona_error(self):
        w = self._finestra()
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_selecciona_loop(_ctx(w), {})
        w.close()


class TestEdicioFina(_Base):
    def test_nudge_mou_la_vora(self):
        w = self._finestra()
        vr = w.visor_ref
        vr.timeline.select_clip("chord", 1)          # Am @ 2.0
        t0 = float(vr.acords[1][0])
        mcp_bridge._op_nudge(_ctx(w), {"direccio": "dreta", "pas": 0.5})
        self.assertAlmostEqual(float(vr.acords[1][0]), t0 + 0.5, places=3)
        w.close()

    def test_nudge_sense_seleccio_dona_error(self):
        w = self._finestra()
        w.visor_ref.timeline.clear_selection()
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_nudge(_ctx(w), {"direccio": "dreta"})
        w.close()

    def test_mou_bloc_preserva_durada_i_sobreescriu(self):
        w = self._finestra()
        # bloc [Am,F] (2 clips, 4 s) +2 s → C@0 Am@4 F@6 Em@8 (G eliminat)
        self._selecciona(w, ("chord", 1), ("chord", 2))
        mcp_bridge._op_mou_bloc(_ctx(w), {"dt_s": 2.0})
        self.assertEqual(self._acords(w),
                         [(0.0, "C"), (4.0, "Am"), (6.0, "F"), (8.0, "Em")])
        w.close()

    def test_mou_bloc_endarrere(self):
        w = self._finestra()
        self._selecciona(w, ("chord", 2), ("chord", 3))   # bloc [F,G] −2 s
        mcp_bridge._op_mou_bloc(_ctx(w), {"dt_s": -2.0})
        self.assertEqual(self._acords(w),
                         [(0.0, "C"), (2.0, "F"), (4.0, "G"), (6.0, "Em")])
        w.close()

    def test_troba_i_reemplaca(self):
        w = self._finestra()
        r = mcp_bridge._op_troba_i_reemplaca(
            _ctx(w), {"camp": "acords", "troba": "Am", "reemplaca": "A-"})
        self.assertEqual(r["substituits"], 1)
        self.assertIn("A-", [n for _t, n in self._acords(w)])
        w.close()

    def test_troba_i_reemplaca_estructura(self):
        w = self._finestra()
        r = mcp_bridge._op_troba_i_reemplaca(
            _ctx(w), {"camp": "estructura", "troba": "B", "reemplaca": "Est"})
        self.assertGreaterEqual(r["substituits"], 1)
        w.close()


class TestVistaIOpcions(_Base):
    def test_neteja_loop(self):
        w = self._finestra()
        vr = w.visor_ref
        vr.ves_a(1.0)
        mcp_bridge._op_mark_loop_a(_ctx(w), {})
        vr.ves_a(5.0)
        mcp_bridge._op_mark_loop_b(_ctx(w), {})
        mcp_bridge._op_neteja_loop(_ctx(w), {})
        r = mcp_bridge._op_status(_ctx(w), {})
        self.assertIsNone(r["transport"]["loop"]["a"])
        self.assertIsNone(r["transport"]["loop"]["b"])
        self.assertFalse(r["transport"]["loop"]["on"])
        w.close()

    def test_set_eina(self):
        w = self._finestra()
        mcp_bridge._op_set_eina(_ctx(w), {"mode": "marc"})
        self.assertTrue(w.b_eina.isChecked())
        self.assertEqual(w.visor_ref.timeline._tool, "marc")
        mcp_bridge._op_set_eina(_ctx(w), {"mode": "intel·ligent"})
        self.assertFalse(w.b_eina.isChecked())
        w.close()

    def test_set_eina_ko(self):
        w = self._finestra()
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_set_eina(_ctx(w), {"mode": "potato"})
        w.close()

    def test_set_inclou_estructura_i_partitura(self):
        w = self._finestra()
        mcp_bridge._op_set_inclou_estructura(_ctx(w), {"on": False})
        self.assertFalse(w.amb_est.isChecked())
        mcp_bridge._op_set_inclou_estructura(_ctx(w), {"on": True})
        self.assertTrue(w.amb_est.isChecked())
        mcp_bridge._op_set_inclou_partitura(_ctx(w), {"on": True})
        self.assertTrue(w.amb_part.isChecked())
        mcp_bridge._op_set_inclou_partitura(_ctx(w), {"on": False})
        self.assertFalse(w.amb_part.isChecked())
        w.close()

    def test_reverteix_no_obre_cap_dialeg_amb_pont(self):
        """Amb el pont actiu, `reverteix` no ha de demanar confirmació modal."""
        w = self._finestra()
        w.mcp_actiu = True
        r = mcp_bridge._op_reverteix(_ctx(w), {})   # no projecte → avís, no penja
        self.assertIn("projecte", r["avis"].lower())
        w.close()


if __name__ == "__main__":   # pragma: no cover
    unittest.main()
