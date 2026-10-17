"""Validació — regla d'or #4 (COBERTURA) amb casos RARS, als 4 punts.

Esborrar el primer/últim clip, moure el primer més enllà de 0, esborrar-ho tot,
i l'export després d'editar. La #4 mana: si el 1r clip no arrenca a 0 s'hi afegeix
una «N»; l'últim arriba a la durada; el CSV i l'export surten del MODEL.
"""
import csv
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from app import pipeline  # noqa: E402
from app import visor as visor_mod  # noqa: E402

DUR = 20.0


def _wav(dur=DUR):
    fd, ruta = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * int(44100 * dur))
    return ruta


def _csv_ac(ruta, items):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for t, c in items:
            w.writerow([f"{float(t):.9f}", f"{float(t):.9f}", c])


def _cs_seg(ruta, seccions):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["inici_s", "fi_s", "durada_s", "lletra", "família",
                    "compas_ini", "compas_fi"])
        for ini, fi, L, fam in seccions:
            w.writerow([f"{ini:.2f}", f"{fi:.2f}", f"{fi - ini:.2f}", L, fam,
                        "1.1", "1.1"])


def _llegeix_ca(ruta):
    with open(ruta, encoding="utf-8") as f:
        return [r for r in csv.reader(f) if r]


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])

    def _visor(self, acords, seccions=None):
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "tema.wav")
        os.replace(_wav(), wav)
        ca = os.path.join(td, "acords.csv")
        _csv_ac(ca, acords)
        sa = os.path.join(td, "abc.csv")
        if seccions:
            _cs_seg(sa, seccions)
        out = os.path.join(td, "AUTOCHORDS_tema")
        os.makedirs(out, exist_ok=True)
        v = visor_mod.Visor(wav, ca, sa if seccions else None, 120.0, 4, False)
        v.td, v.sortida = td, out
        return v

    def _cobreix(self, v):
        self.assertAlmostEqual(float(v.acords[0][0]), 0.0, places=6)


class TestCoberturaRare(_Base):
    def test_eliminar_ultim_acord(self):
        v = self._visor([(0.0, "C"), (2.0, "G"), (5.0, "F")])
        v._elimina_acord_index(2)                    # treu l'últim (F)
        self.assertEqual(len(v.acords), 2)
        self._cobreix(v)
        # el CSV reflecteix el model
        files = _llegeix_ca(os.path.join(v._carpeta_acords(), "acords.csv"))
        self.assertEqual(len(files), 2)
        v.close()

    def test_eliminar_primer_i_ultima_seccio(self):
        v = self._visor([(0.0, "C"), (2.0, "G")],
                        seccions=[(0.0, 5.0, "A", "A"), (5.0, 12.0, "B", "B"),
                                  (12.0, 20.0, "C", "C")])
        v._elimina_seccio_index(0)                   # treu A: B ha d'arrencar a 0
        self.assertAlmostEqual(float(v.seccions[0][0]), 0.0, places=6)
        v._elimina_seccio_index(len(v.seccions) - 1)  # treu l'última → fi = durada
        self.assertAlmostEqual(float(v.seccions[-1][1]), DUR, places=2)
        v.close()

    def test_moure_el_primer_acord_afegeix_N(self):
        v = self._visor([(0.0, "C"), (2.0, "G")])
        v._ed_kind, v._ed_idx = "chord", 0
        v.ed_nom.setText("C")
        v.ed_ini.setText("1.00")
        v.ed_cb.setText("")
        v._aplica_editor()                           # mou el 1r acord a 1,0 s
        self.assertEqual(v.acords[0][2][0], "N")        # cobertura: «N» a 0
        self.assertAlmostEqual(float(v.acords[0][0]), 0.0, places=6)
        v.close()

    def test_no_es_pot_deixar_sense_cobertura(self):
        """La cobertura #4 impedeix quedar-se sense clips: sempre torna la «N»."""
        v = self._visor([(0.0, "C"), (2.0, "G")])
        for _ in range(4):
            v._elimina_acord_index(0)
        self.assertGreaterEqual(len(v.acords), 1)
        self.assertAlmostEqual(float(v.acords[0][0]), 0.0, places=6)
        self.assertGreaterEqual(len(_llegeix_ca(
            os.path.join(v._carpeta_acords(), "acords.csv"))), 1)
        v.close()

    def test_export_despres_d_editar_usa_el_model(self):
        v = self._visor([(0.0, "C"), (2.0, "G"), (5.0, "F")])
        v._elimina_acord_index(2)                    # F fora
        ca = os.path.join(v._carpeta_acords(), "acords.csv")
        pipeline.exporta_total(
            csv_ac=ca, csv_seg=None, sortida=os.path.join(v.td, "out"),
            bpm=120.0, bpb=4, offset=0.0, sr=44100, log=lambda *_: None,
            tempo_fix=False, amb_estructura=False, total_s=DUR,
            acords=v.acords, seccions=None)
        with open(ca, encoding="utf-8") as f:
            files = [r for r in csv.reader(f) if r]
        self.assertEqual(len(files), 2)              # només C i G (no F)
        self.assertTrue(files[0][0].startswith("0.00"))
        self.assertNotIn("F", " ".join(r[1] for r in files))
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
