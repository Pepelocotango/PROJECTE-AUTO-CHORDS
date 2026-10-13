"""Regressió del BUG #5 (informe OC-6/357): xocs d'inici DINS la resolució del CSV.

El CSV d'acords es desa amb `TEMPS_DEC = 2` decimals (10 ms). Dos acords amb
inicis separats per menys de 10 ms cauen a la **mateixa fila** del CSV i el
primer queda amb un clip de durada ~0 a l'export (trenca les regles #1/#2).

Repro original: amb un E7 a `t = 6.831683`, `ac_add_chord(t_s=6.8317, "DUP")`
s'acceptava (el validador només mirava `t <= prev + 1e-9`) i el CSV quedava amb
dues files «6.83».
"""
import csv
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtWidgets import QApplication  # noqa: E402

from app import mcp_bridge, pipeline  # noqa: E402
from app import visor as visor_mod  # noqa: E402

DUR = 40.0
E7_T = 6.831683
XOC_T = 6.8317          # a 1,7e-5 s de l'E7 → mateixa fila «6.83» del CSV


def _escriu_wav(ruta, dur=DUR):
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * int(44100 * dur))


def _llegeix_acords(ruta):
    with open(ruta, encoding="utf-8") as f:
        return [(float(r[0]), r[1]) for r in csv.reader(f) if r]


def _visor(acords=((0.0, "C"), (E7_T, "E7"))):
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "tema.wav")
    _escriu_wav(wav)
    sortida = pipeline.carpeta_sortida(wav)
    os.makedirs(sortida, exist_ok=True)
    ca = os.path.join(sortida, "acords.csv")
    with open(ca, "w", encoding="utf-8") as f:
        for t, nom in acords:
            f.write(f"{t},{nom}\n")
    sa = os.path.join(sortida, "estructura_ABC.csv")
    with open(sa, "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n")
        f.write(f"0.00,{DUR}, {DUR},A,A,1,1\n")
    v = visor_mod.Visor(wav, ca, sa, 120.0, 4, True)
    v.td, v.sortida = td, sortida
    return v


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])


class _FinestraFalsa:
    def __init__(self, visor):
        self.visor_ref = visor
        self.sortida = "/tmp/out"

    def windowTitle(self):
        return "Auto Chords — prova"


class TestXocsResolucioCSV(_Base):
    def test_validador_rebutja_inicis_dins_la_resolucio(self):
        v = _visor()
        with self.assertRaises(ValueError):
            v._valida_canvis_acords([(0.0, "C", "0"),
                                     (E7_T, "E7", "6.831683"),
                                     (XOC_T, "DUP", "6.8317")])

    def test_validador_accepta_just_a_la_resolucio(self):
        v = _visor()
        ok = v._valida_canvis_acords([(0.0, "C", "0"),
                                      (6.83, "E7", "6.83"),
                                      (6.84, "DUP", "6.84")])
        self.assertEqual(len(ok), 3)

    def test_afegeix_acord_rebutja_el_xoc(self):
        v = _visor()
        with self.assertRaises(ValueError):
            v._afegeix_acord(XOC_T, "DUP")

    def test_mcp_add_chord_rebutja_el_xoc(self):
        v = _visor()
        ctx = mcp_bridge._Context(_FinestraFalsa(v))
        with self.assertRaises(mcp_bridge.BridgeError):
            mcp_bridge._op_add_chord(ctx, {"t_s": XOC_T, "acord": "DUP"})
        # i el model no ha quedat tocat
        self.assertNotIn("DUP", [a[1] for a in v.acords])

    def test_el_csv_no_te_mai_temps_duplicats_ni_clips_buits(self):
        v = _visor()
        with self.assertRaises(ValueError):
            v._afegeix_acord(XOC_T, "DUP")      # xoc → rebutjat
        v._afegeix_acord(6.90, "G")             # aquest sí (> 10 ms del E7)
        v._desa_i_regenera()
        files = _llegeix_acords(v.csv_acords)
        temps = [t for t, _ in files]
        self.assertEqual(len(temps), len(set(temps)),
                         f"el CSV té temps duplicats: {temps}")
        for (t0, n0), (t1, _n1) in zip(files, files[1:]):
            self.assertGreater(t1 - t0, 0.0,
                               f"clip de durada 0 al CSV entre {n0} i {t1}")
        self.assertGreater(DUR - files[-1][0], 0.0)

    def test_repara_un_csv_que_ja_venia_xocat(self):
        """Si el CSV ja portava el xoc (versió antiga), en carregar es neteja."""
        v = _visor(acords=((0.0, "C"), (E7_T, "E7"), (XOC_T, "DUP")))
        noms = [a[1] for a in v.acords]
        self.assertNotIn("DUP", noms)
        self.assertIn("E7", noms)
        self.assertEqual(noms, ["C", "E7"])
        # ...i el CSV del disc queda net
        temps = [t for t, _ in _llegeix_acords(v.csv_acords)]
        self.assertEqual(len(temps), len(set(temps)))


class TestExportMaiEscriuClipsBuits(_Base):
    def test_segment_de_durada_zero_s_omet(self):
        """Blindatge darrer: encara que un CSV porti un xoc, l'export no ha
        d'escriure cap WAV de durada 0."""
        td = tempfile.mkdtemp()
        cs = os.path.join(td, "acords.csv")
        with open(cs, "w", encoding="utf-8") as f:
            f.write("0.00,C\n5.00,E7\n5.00,DUP\n")
        dest = os.path.join(td, "wavs")
        pipeline.fer_wavs_acords_lliures(cs, 10.0, dest, 44100,
                                        lambda _m: None)
        self.assertEqual(sorted(os.listdir(dest)),
                         ["0000.00s_0005.00s_C.wav", "0005.00s_0010.00s_DUP.wav"])


if __name__ == "__main__":
    unittest.main()
