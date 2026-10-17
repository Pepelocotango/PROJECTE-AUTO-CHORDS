"""Regressió de 2 bugs de producció (cobertura en viu + export del model).

- **(B) COBERTURA (regla d'or #4)**: en editar (p. ex. eliminar el 1r acord) el
  model i el CSV han de mantenir la «N» de capçalera a 0 (clips que cobreixen
  tota la WAV).
- **(A) EXPORT**: l'exportació ha d'usar el MODEL VIU (seccions editades), no el
  `segments.csv` cru de l'anàlisi.
"""
import csv
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from app import pipeline, visor as visor_mod  # noqa: E402


def _wav(segons=3.0, sr=44100):
    fd, ruta = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"\x00\x00" * int(sr * segons))
    return ruta


def _csv_acords(ruta, items):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for t, c in items:
            w.writerow([f"{float(t):.9f}", f"{float(t):.9f}", c])


def _csv_segments(ruta, seccions):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["inici_s", "fi_s", "lletra", "família"])
        for ini, fi, L, fam in seccions:
            w.writerow([f"{float(ini):.2f}", f"{float(fi):.2f}", L, fam])


class TestCoberturaViu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])

    def _visor(self, acords=None, seccions=None):
        td = tempfile.mkdtemp()
        wav = _wav(3.0)
        ca = os.path.join(td, "acords.csv")
        _csv_acords(ca, acords or [(0.5, "C"), (1.5, "G")])
        sa = os.path.join(td, "abc.csv")
        if seccions:
            _csv_segments(sa, seccions)
        v = visor_mod.Visor(wav, ca, sa if seccions else None, 120.0, 4, False)
        v.td = td
        return v

    def test_eliminar_el_primer_acord_deixa_la_capcalera_N(self):
        v = self._visor()
        # en carregar, el visor ja normalitza la cobertura → «N» a 0.
        self.assertAlmostEqual(float(v.acords[0][0]), 0.0)
        self.assertEqual(v.acords[0][1], "N")
        self.assertEqual(len(v.acords), 3)          # N(0) · C(0.5) · G(1.5)
        # (B) Eliminar el 1r acord → ha de tornar a aparèixer la «N» a 0.
        v._elimina_acord(0)
        v._desa_i_regenera()
        self.assertAlmostEqual(float(v.acords[0][0]), 0.0)
        self.assertEqual(v.acords[0][1], "N")
        with open(v.csv_acords, encoding="utf-8") as f:
            primera = f.readline().strip()
        cols = primera.split(",")
        self.assertEqual(cols[0], "0.00")
        self.assertEqual(cols[2], "N")

    def test_export_usa_el_model_no_el_csv_vell(self):
        v = self._visor(seccions=[(0.0, 3.0, "A", "A")])
        # (A) El MODEL editat: 3 seccions (A/B/C).
        v.seccions = [(0.0, 1.0, "A", "A"), (1.0, 2.0, "B", "B"),
                      (2.0, 3.0, "C", "C")]
        v._normalitza_cobertura()
        seg_vell = os.path.join(v.td, "segments.csv")   # resultat CRU de l'anàlisi
        _csv_segments(seg_vell, [(0.0, 3.0, "Z", "Z")])
        sortida = os.path.join(v.td, "out")
        pipeline.exporta_total(
            csv_ac=v.csv_acords, csv_seg=seg_vell, sortida=sortida,
            bpm=120.0, bpb=4, offset=0.0, sr=44100, log=lambda *_: None,
            tempo_fix=False, amb_estructura=True, total_s=3.0,
            acords=v.acords, seccions=v.seccions)
        with open(os.path.join(sortida, "estructura_ABC.csv"),
                  encoding="utf-8") as f:
            text = f.read()
        self.assertIn("A", text)
        self.assertIn("B", text)
        self.assertIn("C", text)
        self.assertNotIn("Z", text)      # NO pot venir del segments.csv vell

    def test_export_normalitza_la_cobertura_dels_acords(self):
        # Acords sense «N» (forat inicial) passats directament a l'export →
        # el CSV resultant ha de portar la «N» a 0.
        td = tempfile.mkdtemp()
        ca = os.path.join(td, "acords.csv")
        _csv_acords(ca, [(0.5, "C")])
        pipeline.exporta_total(
            csv_ac=ca, csv_seg=None, sortida=os.path.join(td, "out"),
            bpm=120.0, bpb=4, offset=0.0, sr=44100, log=lambda *_: None,
            tempo_fix=False, amb_estructura=False, total_s=3.0,
            acords=[(0.5, "C", "0.5")], seccions=None)
        with open(ca, encoding="utf-8") as f:
            primera = f.readline().strip()
        cols = primera.split(",")
        self.assertEqual(cols[0], "0.00")
        self.assertEqual(cols[2], "N")

    def test_export_sense_model_segueix_llegint_el_csv(self):
        # Retrocompatibilitat: sense `acords`/`seccions` es llegeix el CSV (com abans).
        td = tempfile.mkdtemp()
        ca = os.path.join(td, "acords.csv")
        _csv_acords(ca, [(0.0, "N"), (1.0, "C")])
        r = pipeline.exporta_total(
            csv_ac=ca, csv_seg=None, sortida=os.path.join(td, "out"),
            bpm=120.0, bpb=4, offset=0.0, sr=44100, log=lambda *_: None,
            tempo_fix=False, amb_estructura=False, total_s=3.0)
        self.assertEqual(r["acords_csv"], os.path.abspath(ca))



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
