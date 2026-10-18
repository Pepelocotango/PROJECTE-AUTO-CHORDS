"""Regla d'or #12 — PARITAT A L'EXPORTACIÓ (el paquet tracta els 3 tipus igual).

`docs/REGLES_DE_LA_APP.md` §12: el paquet exportat ha de tractar igual els
**acords**, l'**estructura** i el **mapa de tempo/compàs**, cadascun amb la seva
part:

- acords: `acords.csv` + `wavs_acords/`
- estructura: `estructura_ABC.csv` + `wavs_estructura/`
- mapa de tempo/compàs: **carpeta pròpia** `mapa_tempo/` amb `tempo.csv` i
  `compas.csv`

Abans el mapa no s'exportava: el paquet no era paritari.
"""
import csv
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import pipeline  # noqa: E402

DURADA = 16.0
ACORDS = [(0.0, "C", "0.0"), (4.0, "Am", "4.0"), (8.0, "F", "8.0"),
          (12.0, "G", "12.0")]
SECCIONS = [(0.0, 8.0, "A", "A"), (8.0, DURADA, "B", "B")]
TRAMS = [(0.0, 8.0, 120.0, 4, 4), (8.0, DURADA, 90.0, 3, 4)]


class _Base(unittest.TestCase):

    def _exporta(self, trams=None):
        td = tempfile.mkdtemp()
        sortida = os.path.join(td, "AUTOCHORDS_tema")
        os.makedirs(sortida, exist_ok=True)
        csv_ac = os.path.join(sortida, "acords.csv")
        with open(csv_ac, "w", encoding="utf-8") as f:
            f.write("inici_s,fi_s,acord\n")
            for t, n, ts in ACORDS:
                f.write(f"{t},{t + 4.0},{n}\n")
        res = pipeline.exporta_total(
            csv_ac, None, sortida, 120.0, 4, 0.0, 44100, lambda *a: None,
            tempo_fix=True, amb_estructura=True, total_s=DURADA,
            acords=list(ACORDS), seccions=list(SECCIONS), mapa_tempo=trams)
        return sortida, res


class TestRegla12ParitatExport(_Base):

    def test_els_tres_tipus_tenen_la_seva_part(self):
        """Amb el mapa del model, el paquet ha de portar les TRES parts."""
        sortida, res = self._exporta(TRAMS)
        # acords
        self.assertTrue(os.path.isfile(os.path.join(sortida, "acords.csv")))
        self.assertTrue(os.path.isdir(os.path.join(sortida, "wavs_acords")))
        # estructura
        self.assertTrue(os.path.isfile(
            os.path.join(sortida, "estructura_ABC.csv")))
        self.assertTrue(os.path.isdir(os.path.join(sortida, "wavs_estructura")))
        # mapa de BPM/compàs, amb carpeta PRÒPIA
        mapa = os.path.join(sortida, "mapa_tempo")
        self.assertTrue(os.path.isdir(mapa), "falta la carpeta del mapa")
        self.assertTrue(os.path.isfile(os.path.join(mapa, "tempo.csv")))
        self.assertTrue(os.path.isfile(os.path.join(mapa, "compas.csv")))
        self.assertEqual(res.get("mapa_tempo_dir"), mapa)
        self.assertEqual(res.get("n_mapa_trams"), len(TRAMS))

    def test_el_mapa_exportat_es_el_del_model(self):
        """El que s'exporta és el MODEL (no una còpia vella del disc)."""
        sortida, _ = self._exporta(TRAMS)
        trams = pipeline.llegeix_tempo_map(
            os.path.join(sortida, "mapa_tempo"), 120.0, 4, 4, DURADA)
        self.assertEqual([(float(t[0]), float(t[1]), float(t[2]), int(t[3]),
                           int(t[4])) for t in trams], TRAMS)

    def test_sense_mapa_no_hi_ha_carpeta(self):
        """Sense mapa al model (flux antic), el paquet queda com era."""
        sortida, res = self._exporta(None)
        self.assertFalse(os.path.isdir(os.path.join(sortida, "mapa_tempo")))
        self.assertNotIn("mapa_tempo_dir", res)

    def test_el_csv_de_compas_te_els_compassos_del_mapa(self):
        """El `compas.csv` ha de dur el compàs de cada tram (4/4 i 3/4)."""
        sortida, _ = self._exporta(TRAMS)
        with open(os.path.join(sortida, "mapa_tempo", "compas.csv"),
                  encoding="utf-8") as f:
            files = [r for r in csv.reader(f) if r and not r[0][0].isalpha()]
        valors = [(int(r[2]), int(r[3])) for r in files]
        self.assertEqual(valors, [(4, 4), (3, 4)])


if __name__ == "__main__":
    unittest.main()
