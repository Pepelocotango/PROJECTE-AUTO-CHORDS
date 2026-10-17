"""Graella musical: conversió segons↔graella i regularització del ritme harmònic
(mode fàcil), a partir de l'ANÀLISI CRUA.

Exemple de fons: 120 BPM, 4/4 → compàs = 2,00 s · mig compàs = 1,00 s ·
temps = 0,50 s.
"""
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from app import graella  # noqa: E402
from app import pipeline  # noqa: E402
from app import visor as visor_mod  # noqa: E402


class TestGraella(unittest.TestCase):
    def test_nivell_segons(self):
        self.assertAlmostEqual(graella.nivell_segons("compas", 120, 4), 2.0)
        self.assertAlmostEqual(graella.nivell_segons("mig", 120, 4), 1.0)
        self.assertAlmostEqual(graella.nivell_segons("temps", 120, 4), 0.5)
        # canvia amb el BPM: a 90 BPM el compàs és 2,666… s
        self.assertAlmostEqual(graella.nivell_segons("compas", 90, 4),
                               8.0 / 3.0, places=6)

    def test_snap_a_nivell(self):
        self.assertAlmostEqual(graella.snap_a_nivell(2.1, "compas", 120, 4), 2.0)
        self.assertAlmostEqual(graella.snap_a_nivell(1.4, "mig", 120, 4), 1.0)
        self.assertAlmostEqual(graella.snap_a_nivell(0.6, "temps", 120, 4), 0.5)

    def test_regularitza_encaixa_a_la_graella(self):
        # canvis crus amb una mica de jitter, tots a prop de línies de compàs
        cru = [(0.04, "C"), (2.03, "G"), (4.05, "Am"), (5.98, "F")]
        res = graella.regularitza_acords(cru, 120, 4, 0.0, "compas", 8.0)
        self.assertEqual([round(t, 3) for t, _n in res], [0.0, 2.0, 4.0, 6.0])
        self.assertEqual([n for _t, n in res], ["C", "G", "Am", "F"])

    def test_regularitza_es_queda_el_dominant(self):
        # dins el compàs 1 (0–2 s) hi ha dos canvis: el "dominant" és el que dura més
        cru = [(0.0, "C"), (0.2, "X"), (2.0, "G")]
        res = graella.regularitza_acords(cru, 120, 4, 0.0, "compas", 4.0)
        self.assertEqual(res[0], (0.0, "X"))     # X dura 1,8 s > C (0,2 s)

    def test_infereix_compas_vs_temps(self):
        per_compas = [(0.0, "C"), (2.0, "G"), (4.0, "Am"), (6.0, "F")]
        self.assertEqual(graella.infereix_nivell(per_compas, 120, 4, 0.0, 8.0),
                         "compas")
        per_temps = [(0.0, "C"), (0.5, "G"), (1.0, "Am"), (1.5, "F")]
        self.assertEqual(graella.infereix_nivell(per_temps, 120, 4, 0.0, 8.0),
                         "temps")

    def test_regularitza_acords_csv(self):
        td = tempfile.mkdtemp()
        cru = os.path.join(td, "chords_raw.csv")
        dest = os.path.join(td, "acords.csv")
        with open(cru, "w", encoding="utf-8") as f:
            for t, n in [(0.04, "C"), (2.03, "G"), (4.05, "Am"), (5.98, "F")]:
                f.write(f"{t},{n}\n")
        res = pipeline.regularitza_acords_csv(cru, dest, 120, 4, 0.0,
                                              "compas", 8.0)
        self.assertEqual([round(float(t), 2) for (t, *_r) in res],
                         [0.0, 2.0, 4.0, 6.0])
        self.assertTrue(os.path.isfile(dest))
        self.assertIn("0.04", open(cru, encoding="utf-8").read(),
                      "el cru no s'ha de tocar")

    def test_presets_ben_formats(self):
        for clau, p in graella.PRESETS.items():
            self.assertIn("etiqueta", p, clau)
            self.assertIn(p["ritme"], ("auto",) + graella.NIVELLS, clau)
            self.assertIn(int(p["modul"]), (0, 1, 2, 4, 8, 12), clau)
        # hi ha estils representatius del que volíem cobrir
        for clau in ("pop", "blues", "swing", "buleria", "vals", "bossa"):
            self.assertIn(clau, graella.PRESETS)

    def test_infereix_cicle_blues12_i_loop4(self):
        bpm, bpb, durada = 120, 4, 48.0          # 24 compassos de 2 s
        blues = ["C", "C", "C", "C", "F", "F", "C", "C", "G", "F", "C", "G"]
        items = [(2.0 * k, blues[k % 12]) for k in range(24)]
        self.assertEqual(graella.infereix_cicle_compassos(items, bpm, bpb, 0.0,
                                                          durada), 12)
        loop4 = ["C", "G", "Am", "F"]
        items4 = [(2.0 * k, loop4[k % 4]) for k in range(24)]
        self.assertEqual(graella.infereix_cicle_compassos(items4, bpm, bpb, 0.0,
                                                          durada), 4)

    def test_regularitza_seccions_a_blocs(self):
        # 120 BPM 4/4 → compàs 2 s; blocs de 4 compassos = 8 s
        sec = [(0.0, 5.0, "A", "A"), (5.0, 10.0, "B", "B"), (10.0, 22.0, "C", "C")]
        res = graella.regularitza_seccions(sec, 120, 4, 0.0, 22.0,
                                           modul_compassos=4)
        # talls encaixats a múltiples de 8 s: 0 · 8 · 22
        self.assertEqual([round(s[0], 3) for s in res], [0.0, 8.0])
        self.assertAlmostEqual(res[-1][1], 22.0)
        self.assertEqual(res[-1][2], "C")            # el bloc del final és C
        self.assertAlmostEqual(res[0][0], 0.0)
        for i in range(len(res) - 1):
            self.assertAlmostEqual(res[i][1], res[i + 1][0], places=6)

    def test_regularitza_clips_nucli_unic(self):
        # El nucli únic treballa sobre clips `(ini, fi, payload)`.
        clips = [(0.0, 0.2, ("C",)), (0.2, 2.0, ("X",)), (2.0, 4.0, ("G",))]
        out = graella.regularitza_clips(clips, 2.0, 0.0, 4.0)
        self.assertEqual([c[0] for c in out], [0.0, 2.0])
        self.assertEqual([c[2] for c in out], [("X",), ("G",)])  # X domina

    def test_regularitza_seccions_segueix_el_nucli_dominant(self):
        # El tram resolt [16,22) el domina la secció C[10,20) (4 s) i NO la D
        # [20,22) (2 s): el nucli mira la COBERTURA del tram, no només qui hi
        # encaixa l'inici. Paritat estructural #11 amb els acords.
        sec = [(0.0, 5.0, "A", "A"), (5.0, 10.0, "B", "B"),
               (10.0, 20.0, "C", "C"), (20.0, 22.0, "D", "D")]
        res = graella.regularitza_seccions(sec, 120, 4, 0.0, 22.0,
                                           modul_compassos=4)
        self.assertEqual([(s[0], s[2]) for s in res],
                         [(0.0, "A"), (8.0, "C"), (16.0, "C")])

    # ── Casos límit (validació) ──────────────────────────────────────────────
    def test_regularitza_acords_durada_zero(self):
        cru = [(0.0, "C"), (2.0, "G")]
        self.assertEqual(graella.regularitza_acords(cru, 120, 4, 0.0, "compas",
                                                    0.0), cru)

    def test_regularitza_acords_buit(self):
        self.assertEqual(graella.regularitza_acords([], 120, 4, 0.0, "compas",
                                                    8.0), [])

    def test_infereix_nivell_pocs_items(self):
        self.assertEqual(graella.infereix_nivell([], 120, 4, 0.0, 8.0), "compas")
        self.assertEqual(graella.infereix_nivell([(0.0, "C")], 120, 4, 0.0, 8.0),
                         "compas")

    def test_infereix_cicle_poques_barres(self):
        self.assertIsNone(graella.infereix_cicle_compassos(
            [(0.0, "C"), (2.0, "G")], 120, 4, 0.0, 4.0))

    def test_regularitza_seccions_una_de_sola(self):
        sec = [(0.0, 10.0, "A", "A")]
        self.assertEqual(
            graella.regularitza_seccions(sec, 120, 4, 0.0, 10.0, 4), sec)

    def test_divisio_segons_compassos(self):
        # 120 BPM, 4/4 → compàs = 2 s
        self.assertAlmostEqual(graella.divisio_segons("compas1", 120, True, 4), 2.0)
        self.assertAlmostEqual(graella.divisio_segons("compas4", 120, True, 4), 8.0)
        self.assertAlmostEqual(graella.divisio_segons("compas8", 120, True, 4), 16.0)
        self.assertAlmostEqual(graella.divisio_segons("compas16", 120, True, 4), 32.0)
        # depèn del compàs: 3/4 → compàs 1,5 s
        self.assertAlmostEqual(graella.divisio_segons("compas1", 120, True, 3), 1.5)

    def test_divisio_segons_lliure(self):
        self.assertEqual(graella.divisio_segons("corxera", 120, False), 0.0)
        self.assertAlmostEqual(graella.divisio_segons("corxera", 120, True), 0.25)


def _visor(raw=None, bpm=120.0, bpb=4):
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "tema.wav")
    out = os.path.join(td, "AUTOCHORDS_tema")
    os.makedirs(out)
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * 8)
    ca = os.path.join(out, "acords.csv")
    sa = os.path.join(out, "estructura_ABC.csv")
    with open(ca, "w", encoding="utf-8") as f:
        f.write("0.0,C\n2.0,G\n4.0,Am\n6.0,F\n")
    with open(sa, "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
                "0.0,8.0,8.0,A,A,1.1,5.1\n")
    v = visor_mod.Visor(wav, ca, sa, bpm=bpm, bpb=bpb, tempo_fix=True)
    v.td, v.sortida = td, out
    if raw is not None:
        ana = pipeline.carpeta_analisi(out)
        os.makedirs(ana, exist_ok=True)
        with open(os.path.join(ana, pipeline.NOM_CRU_ACORDS), "w",
                  encoding="utf-8") as f:
            for t, n in raw:
                f.write(f"{t},{n}\n")
    return v


class TestModeFacilVisor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = visor_mod.QApplication.instance() or visor_mod.QApplication([])

    def test_regularitza_des_del_cru(self):
        v = _visor(raw=[(0.04, "C"), (2.03, "G"), (4.05, "Am"), (5.98, "F")])
        n = v.regularitza_des_de_cru("compas")
        self.assertGreater(n, 0)
        self.assertEqual([round(float(t), 2) for (t, *_r) in v.acords],
                         [0.0, 2.0, 4.0, 6.0])
        self.assertEqual([a[1] for a in v.acords], ["C", "G", "Am", "F"])
        # cobertura (#4): 0 → durada
        self.assertAlmostEqual(float(v.acords[0][0]), 0.0, places=6)
        self.assertEqual(len(v._undo_stack), 1)
        v.close()

    def test_auto_infereix_compas(self):
        v = _visor(raw=[(0.0, "C"), (2.0, "G"), (4.0, "Am"), (6.0, "F")])
        v.regularitza_des_de_cru("auto")
        self.assertEqual([a[1] for a in v.acords], ["C", "G", "Am", "F"])
        v.close()

    def test_la_capa_crua_no_es_toca(self):
        v = _visor(raw=[(0.04, "C"), (2.03, "G"), (4.05, "Am"), (5.98, "F")])
        cru = os.path.join(pipeline.carpeta_analisi(v.sortida),
                           pipeline.NOM_CRU_ACORDS)
        abans = open(cru, encoding="utf-8").read()
        v.regularitza_des_de_cru("compas")
        self.assertEqual(open(cru, encoding="utf-8").read(), abans,
                         "el mode fàcil no ha de tocar l'anàlisi crua")
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
