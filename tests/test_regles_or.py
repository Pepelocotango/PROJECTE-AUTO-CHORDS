"""Regressió de les REGLES D'OR que encara no tenien test propi.

`docs/REGLES_DE_LA_APP.md` diu que les regles **1, 2, 4, 7, 8** ja en tenen;
aquí blindem les que no: **3** (durades derivades), **5** (una sola font de
veritat), **6** (les WAVs només via `exporta()`) i **8** (temps vàlids).
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


def _visor(dur=10.0):
    """Visor amb una WAV de `dur` s i 3 acords + 2 seccions."""
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "tema.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * int(44100 * dur))
    sortida = pipeline.carpeta_sortida(wav)
    os.makedirs(sortida, exist_ok=True)
    ca = os.path.join(sortida, "acords.csv")
    with open(ca, "w", encoding="utf-8") as f:
        f.write("0.0,C\n2.0,Am\n5.0,F\n")
    sa = os.path.join(sortida, "estructura_ABC.csv")
    with open(sa, "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n")
        f.write("0.0,5.0,5.0,A,A,1.1,5.1\n")
        f.write("5.0,10.0,5.0,B,B,5.1,10.1\n")
    v = visor_mod.Visor(wav, ca, sa, 120.0, 4, True)
    v.td, v.sortida = td, sortida
    return v


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])


class TestRegla3DuradesDerivades(_Base):
    """Regla 3: la durada d'un clip es DERIVA, no s'emmagatzema."""

    def test_cap_camp_de_durada_al_model(self):
        v = _visor()
        for a in v.acords:
            self.assertEqual(len(a), 3, f"acord amb camps estranys: {a!r}")
        for s in v.seccions:
            self.assertEqual(len(s), 4, f"secció amb camps estranys: {s!r}")

    def test_la_durada_del_darrer_clip_es_deriva_de_la_wav(self):
        v = _visor()
        self.assertAlmostEqual(float(v.seccions[-1][1]),
                               float(v.audio["durada"]), places=2)


class TestRegla5FontDeVeritat(_Base):
    """Regla 5: el CSV del disc reflexa el MODEL (font única = pipeline)."""

    def test_el_csv_del_disc_reflecteix_el_model(self):
        v = _visor()
        v._afegeix_acord(3.0, "G")
        v._elimina_acord(0)
        v._desa_i_regenera()
        with open(v.csv_acords, encoding="utf-8") as f:
            files = [r for r in csv.reader(f) if r]
        self.assertEqual(len(files), len(v.acords))
        for fila, model in zip(files, v.acords):
            self.assertAlmostEqual(float(fila[0]), float(model[0]), places=2)
            self.assertEqual(fila[1], model[1])


class TestRegla6WavsNomesViaExporta(_Base):
    """Regla 6: l'edició MAI toca les WAVs generades."""

    def test_editar_no_crea_ni_toca_cap_wav(self):
        v = _visor()
        dest = os.path.join(v.sortida, "wavs_acords")
        os.makedirs(dest, exist_ok=True)
        centinella = os.path.join(dest, "00.00s_02.00s_C.wav")
        with open(centinella, "wb") as f:
            f.write(b"RIFF....")           # contingut qualsevol
        m0 = os.path.getmtime(centinella)
        abans = set(os.listdir(dest))
        # Edicions com les de la GUI/el MCP (incloent el guardat del CSV).
        v._afegeix_acord(3.0, "G")
        v._elimina_acord(0)
        v._desa_i_regenera()
        self.assertEqual(os.path.getmtime(centinella), m0,
                         "una edició no pot tocar el fitxer WAV")
        self.assertEqual(set(os.listdir(dest)), abans,
                         "una edició no pot crear cap WAV")
        self.assertFalse(os.path.isdir(os.path.join(v.sortida, "wavs_estructura")),
                         "l'edició no ha de generar wavs d'estructura")


class TestRegla8TempsValids(_Base):
    """Regla 8: cap temps negatiu ni durada <= 0."""

    def test_acord_amb_inici_negatiu_es_rebutjat(self):
        v = _visor()
        with self.assertRaises(ValueError):
            v._valida_canvis_acords([(-0.5, "C", "-0.5")])

    def test_seccio_negativa_o_de_durada_nula_es_rebutjada(self):
        v = _visor()
        with self.assertRaises(ValueError):
            v._valida_canvis_seccions([(-1.0, 5.0, "A", "A")])
        with self.assertRaises(ValueError):
            v._valida_canvis_seccions([(5.0, 5.0, "A", "A")])



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
