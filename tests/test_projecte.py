"""Projectes — carpeta AUTOCONTINGUDA (regla de producte «com un DAW»).

Comprova que `app/projecte.py` crea una carpeta que ho conté tot (l'àudio
copiat a `audio/`, els CSVs i el document `.acproj`) i que **no depèn de fora**:
si s'esborra l'original o es mou la carpeta sencera, el projecte s'obre igual.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _temporals  # noqa: E402
_ = _temporals  # higiene dels tests: l'import té efecte (esborra en plegar)

from app import pipeline  # noqa: E402
from app import projecte  # noqa: E402


def _wav(ruta, dur=5.0):
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * int(44100 * dur))


class BaseProjecte(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.td, ignore_errors=True)


class TestCrea(BaseProjecte):
    def test_carpeta_autocontinguda(self):
        wav = os.path.join(self.td, "tema.wav")
        _wav(wav)
        carp = os.path.join(self.td, "La meva cançó")
        p = projecte.Projecte.crea(carp, wav, bpm=138.0, bpb=4)
        self.assertTrue(os.path.isfile(p.ruta_acproj))
        self.assertTrue(os.path.isfile(p.ruta_audio()),
                        "l'àudio s'ha de copiar dins el projecte")
        self.assertTrue(os.path.isdir(os.path.join(carp, "audio")))
        # ruta d'àudio RELATIVA, dins el projecte
        self.assertEqual(p.dades["audio"], os.path.join("audio", "tema.wav"))
        self.assertEqual(p.dades["format"], projecte.FORMAT)

    def test_no_trepitja_carpeta_amb_contingut(self):
        wav = os.path.join(self.td, "tema.wav")
        _wav(wav)
        carp = os.path.join(self.td, "no-buida")
        os.makedirs(carp)
        with open(os.path.join(carp, "cosa.txt"), "w") as f:
            f.write("x")
        with self.assertRaises(projecte.ProjecteError):
            projecte.Projecte.crea(carp, wav)

    def test_audio_inexistent_peta(self):
        with self.assertRaises(projecte.ProjecteError):
            projecte.Projecte.crea(os.path.join(self.td, "P"),
                                   os.path.join(self.td, "no.wav"))


class TestAutocontencio(BaseProjecte):
    def test_esborra_original_i_mou_la_carpeta(self):
        wav = os.path.join(self.td, "tema.wav")
        _wav(wav)
        carp = os.path.join(self.td, "P1")
        p = projecte.Projecte.crea(carp, wav, bpm=99.0)
        self.assertEqual(p.dades["tempo"]["bpm"], 99.0)

        os.remove(wav)                       # l'original desapareix
        munt = os.path.join(self.td, "TOTALMENT_ALTRA_UBICACIO")
        shutil.move(carp, munt)              # movem la carpeta SENcera

        p2 = projecte.Projecte.obre(munt)
        self.assertTrue(p2.audio_present(), "el projecte ha de ser autocontingut")
        self.assertEqual(p2.nom, "P1")
        self.assertEqual(p2.dades["tempo"]["bpm"], 99.0)


class TestObreDesa(BaseProjecte):
    def _projecte(self, nom="P"):
        wav = os.path.join(self.td, nom + ".wav")
        _wav(wav)
        return projecte.Projecte.crea(os.path.join(self.td, nom), wav,
                                      bpm=120.0, bpb=3, offset=0.5, fix=True,
                                      opcions={"chords": {"foo": 1}},
                                      vista={"zoom": 7})

    def test_obre_per_carpeta_i_per_fitxer(self):
        p = self._projecte()
        per_carpeta = projecte.Projecte.obre(p.carpeta)
        per_fitxer = projecte.Projecte.obre(p.ruta_acproj)
        self.assertEqual(per_carpeta.dades["tempo"]["bpb"], 3)
        self.assertEqual(per_fitxer.dades["tempo"]["bpb"], 3)

    def test_roundtrip_tempo_opcions_vista(self):
        p = self._projecte("RT")
        p.dades["tempo"]["bpm"] = 144.5
        p.desa()
        p2 = projecte.Projecte.obre(p.carpeta)
        self.assertEqual(p2.dades["tempo"]["bpm"], 144.5)
        self.assertEqual(p2.dades["opcions"], {"chords": {"foo": 1}})
        self.assertEqual(p2.dades["vista"], {"zoom": 7})

    def test_desa_es_valid_i_no_deixa_temporals(self):
        p = self._projecte("AT")
        p.desa()
        with open(p.ruta_acproj, encoding="utf-8") as f:
            json.load(f)                     # ha de ser JSON vàlid
        sobres = [f for f in os.listdir(p.carpeta) if f.endswith(".tmp")]
        self.assertEqual(sobres, [], f"no han de quedar temporals: {sobres}")

    def test_format_antic_es_migra(self):
        """Un projecte sense `format` (versió 0) s'obre i queda al format viu."""
        td = tempfile.mkdtemp()
        ap = os.path.join(td, "vell.acproj")
        with open(ap, "w", encoding="utf-8") as f:
            json.dump({"nom": "VELL", "tempo": {"bpm": 120, "bpb": 4}}, f)
        p = projecte.Projecte.obre(ap)
        self.assertEqual(p.dades["format"], projecte.FORMAT)
        self.assertEqual(p.dades["nom"], "VELL")

    def test_format_mes_nou_peta(self):
        p = self._projecte("FUT")
        with open(p.ruta_acproj, "w", encoding="utf-8") as f:
            f.write(json.dumps({"format": 99, "nom": "FUT"}))
        with self.assertRaises(projecte.ProjecteError):
            projecte.Projecte.obre(p.carpeta)

    # ── Casos límit (validació) ──────────────────────────────────────────────
    def test_obre_amb_dos_acproj_peta(self):
        p = self._projecte("DOS")
        with open(os.path.join(p.carpeta, "altre.acproj"), "w",
                  encoding="utf-8") as f:
            f.write("{}")
        with self.assertRaises(projecte.ProjecteError):
            projecte.Projecte.obre(p.carpeta)

    def test_no_sobreescriu_projecte_existent(self):
        wav = os.path.join(self.td, "tema.wav")
        _wav(wav)
        carp = os.path.join(self.td, "P")
        projecte.Projecte.crea(carp, wav)
        with self.assertRaises(projecte.ProjecteError):
            projecte.Projecte.crea(carp, wav)

    def test_no_es_projecte(self):
        self.assertFalse(projecte.es_projecte(os.path.join(self.td, "res")))
        wav = os.path.join(self.td, "sol.wav")
        _wav(wav)
        self.assertFalse(projecte.es_projecte(wav))


class TestDuplica(BaseProjecte):
    def test_desa_com_canvia_de_carpeta_i_nom(self):
        wav = os.path.join(self.td, "tema.wav")
        _wav(wav)
        p = projecte.Projecte.crea(os.path.join(self.td, "Original"), wav)
        desti = os.path.join(self.td, "Còpia")
        q = p.duplica(desti)
        self.assertTrue(os.path.isfile(q.ruta_acproj))
        self.assertTrue(os.path.isfile(q.ruta_audio()))
        self.assertEqual(os.path.basename(q.ruta_acproj), "Còpia" + projecte.EXT)
        self.assertEqual(q.nom, "Còpia")
        # el projecte original no s'ha tocat
        self.assertTrue(os.path.isfile(p.ruta_acproj))

    def test_desti_existent_peta(self):
        wav = os.path.join(self.td, "tema.wav")
        _wav(wav)
        p = projecte.Projecte.crea(os.path.join(self.td, "A"), wav)
        os.makedirs(os.path.join(self.td, "B"))
        with self.assertRaises(projecte.ProjecteError):
            p.duplica(os.path.join(self.td, "B"))

    def test_no_es_pot_copiar_dins_d_ell_mateix(self):
        wav = os.path.join(self.td, "tema.wav")
        _wav(wav)
        p = projecte.Projecte.crea(os.path.join(self.td, "A"), wav)
        with self.assertRaises(projecte.ProjecteError):
            p.duplica(os.path.join(p.carpeta, "sub"))


class TestMigracioAutochords(BaseProjecte):
    def _autochords_antic(self):
        wav = os.path.join(self.td, "tema.wav")
        _wav(wav)
        carp = pipeline.carpeta_sortida(wav)      # AUTOCHORDS_tema/
        os.makedirs(carp, exist_ok=True)
        with open(os.path.join(carp, "acords.csv"), "w", encoding="utf-8") as f:
            f.write("0.0,1.0,C\n1.0,5.0,Am\n")
        with open(os.path.join(carp, "estructura_ABC.csv"), "w",
                  encoding="utf-8") as f:
            f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n")
            f.write("0.0,5.0,5.0,A,A,1.1,1.5\n")
        return wav, carp

    def test_importa_en_el_lloc(self):
        wav, carp = self._autochords_antic()
        p = projecte.importa_autochords(wav)
        # a la MATEIXA carpeta, però ara amb àudio + document
        self.assertEqual(os.path.abspath(p.carpeta), os.path.abspath(carp))
        self.assertTrue(os.path.isfile(p.ruta_audio()))
        self.assertTrue(os.path.isfile(p.ruta_acproj))
        # els CSVs existents s'han conservat
        self.assertTrue(os.path.isfile(p.ruta_csv_acords()))
        self.assertTrue(os.path.isfile(p.ruta_csv_estructura()))
        # i el projecte es pot obrir des del WAV
        self.assertTrue(projecte.es_projecte(wav))

    def test_sense_carpeta_autochords_peta(self):
        wav = os.path.join(self.td, "net.wav")
        _wav(wav)
        with self.assertRaises(projecte.ProjecteError):
            projecte.importa_autochords(wav)


if __name__ == "__main__":
    unittest.main()
