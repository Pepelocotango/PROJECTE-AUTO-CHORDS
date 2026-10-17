"""Roadmap §14.1 — treballar SENSE analitzar (edició total per l'usuari).

En carregar un àudio **sense anàlisi**, el model ha de néixer amb **1 clip
d'acords** i **1 d'estructura** que cobreixen tota la cançó: el punt de partida
editable (partir/afegir/moure/renombrar). L'anàlisi (Chordino/qm) passa a ser
**opcional**, mai un requisit previ.

A vigilar: regla d'or **#4** (cobertura total) i que, sense anàlisi, **no** cal
la capa crua (`analisi/`).
"""
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app import main as app_main  # noqa: E402
from app import pipeline, projecte  # noqa: E402

_VIVES = []


def _wav(dur=12.0):
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

    def _finestra_amb_projecte(self, amb_csv=False):
        wav = _wav()
        p = projecte.Projecte.crea(os.path.join(os.path.dirname(wav), "P"),
                                   wav, bpm=120.0)
        if amb_csv:
            with open(p.ruta_csv_acords(), "w", encoding="utf-8") as f:
                f.write("0.0,4.0,C\n4.0,4.0,G\n")
            with open(os.path.join(p.carpeta, "estructura_ABC.csv"), "w",
                      encoding="utf-8") as f:
                f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,"
                        "compas_fi\n0.0,12.0,12.0,A,A,1.1,5.1\n")
        w = app_main.Finestra()
        _VIVES.append(w)
        w.avisa_info = lambda *a, **k: None
        w.avisa = lambda *a, **k: None
        w._activa_projecte(projecte.Projecte.obre(p.ruta_acproj))
        return w, p

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


class TestSenseAnalisi(_Base):
    def test_audio_nou_neix_amb_1_acord_i_1_seccio(self):
        w, _p = self._finestra_amb_projecte(amb_csv=False)
        vr = w.visor_ref
        self.assertEqual(len(vr.acords), 1, "1 clip d'acords")
        self.assertEqual(len(vr.seccions), 1, "1 clip d'estructura")
        self.assertEqual(vr.acords[0][2][0], "N")
        self.assertEqual(vr.seccions[0][2], "A")

    def test_cobertura_total(self):
        """Regla d'or #4: el clip únic ha de cobrir TOTA la durada."""
        w, _p = self._finestra_amb_projecte(amb_csv=False)
        vr = w.visor_ref
        dur = float(vr.audio["durada"])
        self.assertAlmostEqual(float(vr.acords[0][0]), 0.0, places=6)
        self.assertAlmostEqual(float(vr.seccions[0][0]), 0.0, places=6)
        self.assertAlmostEqual(float(vr.seccions[0][1]), dur, places=3)

    def test_export_habilitat_i_csvs_desats(self):
        w, p = self._finestra_amb_projecte(amb_csv=False)
        self.assertTrue(w.b_export.isEnabled(), "es pot exportar sense analitzar")
        self.assertTrue(w.b_export_part.isEnabled())
        for nom in ("acords.csv", "estructura_ABC.csv"):
            self.assertTrue(os.path.isfile(os.path.join(p.carpeta, nom)), nom)

    def test_sense_analisi_no_cal_la_capa_crua(self):
        _w, p = self._finestra_amb_projecte(amb_csv=False)
        self.assertFalse(os.path.isdir(os.path.join(p.carpeta, "analisi")),
                         "sense anàlisi no s'ha de crear analisi/")

    def test_es_editable_a_ma(self):
        """El punt de partida és editable: afegir un acord manté la cobertura."""
        w, _p = self._finestra_amb_projecte(amb_csv=False)
        vr = w.visor_ref
        self.assertTrue(vr._afegeix_acord(6.0, "C"))
        noms = [a[2][0] for a in vr.acords]
        self.assertIn("C", noms)
        vr._normalitza_cobertura()      # (no cal que canviï res)
        self.assertEqual(float(vr.acords[0][0]), 0.0)      # el 1r a 0
        self.assertAlmostEqual(float(vr.seccions[0][1]),
                               float(vr.audio["durada"]), places=3)

    def test_amb_csvs_no_es_toca(self):
        """Un projecte que JA té model (anàlisi feta) no s'ha de modificar."""
        w, _p = self._finestra_amb_projecte(amb_csv=True)
        vr = w.visor_ref
        self.assertEqual([a[2][0] for a in vr.acords], ["C", "G"])
        self.assertEqual(len(vr.seccions), 1)


class TestModelInicial(unittest.TestCase):
    def test_helper(self):
        ac, sec = pipeline.model_inicial(7.5)
        self.assertEqual(ac, [pipeline.Clip(0.0, 7.5, ("N", "0.000000000"))])
        self.assertEqual(sec, [(0.0, 7.5, "A", "A")])

    def test_durada_zero_no_peta(self):
        ac, sec = pipeline.model_inicial(0)
        self.assertEqual(ac[0][0], 0.0)
        self.assertEqual(sec[0][1], 0.0)


def tearDownModule():
    try:
        import _qt_neteja
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()


if __name__ == "__main__":
    unittest.main()
