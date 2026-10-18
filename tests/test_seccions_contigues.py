"""Regressió del BUG #3 (informe OC-6/340): moure una secció cap endavant
creava un **FORAT INTERN** que l'app acceptava.

Regles d'or afectades: **#2** (contigüitat: `prev.fi == curr.ini`) i **#4**
(la suma de les durades dels clips == durada de la WAV).

Cobreix els 3 camins que podien crear el forat: el **MCP** (`move_section`),
l'**editor** de la franja Editor, i la **càrrega** d'un CSV que ja venia amb
forat (que s'ha de normalitzar també AL DISC).
"""
import csv
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene dels tests: l'import té efecte (esborra els temporals en plegar)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtWidgets import QApplication  # noqa: E402

from app import mcp_bridge, pipeline  # noqa: E402
from app import visor as visor_mod  # noqa: E402

DUR = 40.0
# 4 seccions contigües que cobreixen 0–40: A, B, C, D
SECCIONS = [(0.0, 10.0, "A", "A"), (10.0, 20.0, "B", "B"),
            (20.0, 30.0, "C", "C"), (30.0, 40.0, "D", "D")]


def _escriu_wav(ruta, dur=DUR):
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * int(44100 * dur))


def _escriu_abc(ruta, seccions):
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n")
        for ini, fi, L, fam in seccions:
            f.write(f"{ini},{fi},{fi - ini},{L},{fam},1.1,2.1\n")


def _llegeix_abc(ruta):
    files = []
    with open(ruta, encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) < 4 or row[0].startswith("inici"):
                continue
            files.append((float(row[0]), float(row[1]), row[3], row[4]))
    return files


def _suma(seccions):
    return sum(float(fi) - float(ini) for ini, fi, _L, _F in seccions)


def _contigues(seccions, tol=1e-6):
    """Regla d'or #2: cada secció arrenca exactament on acaba l'anterior."""
    for (a, b, _L1, _F1), (ini, _fi, L2, _F2) in zip(seccions, seccions[1:]):
        if abs(float(b) - float(ini)) > tol:
            return False
    return True


def _visor(seccions=None):
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "tema.wav")
    _escriu_wav(wav)
    sortida = pipeline.carpeta_sortida(wav)
    os.makedirs(sortida, exist_ok=True)
    ca = os.path.join(sortida, "acords.csv")
    with open(ca, "w", encoding="utf-8") as f:
        f.write("0.0,10.0,C\n")
    sa = os.path.join(sortida, "estructura_ABC.csv")
    _escriu_abc(sa, SECCIONS if seccions is None else seccions)
    v = visor_mod.Visor(wav, ca, sa, 120.0, 4, True)
    v.td, v.sortida, v.abc_csv = td, sortida, sa
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


class TestMoureSeccioManteContiguitat(_Base):
    def test_moure_l_inici_endavant_no_deixa_forat(self):
        """Repro exacte del bug: moure la secció 2 a 25.0–30.0."""
        v = _visor()
        self.assertTrue(v.mou_seccio(2, 25.0, 30.0))
        # #2: B s'estén fins al nou inici i C arrenca allà mateix
        self.assertAlmostEqual(float(v.seccions[1][1]), 25.0, places=6)
        self.assertAlmostEqual(float(v.seccions[2][0]), 25.0, places=6)
        # #4: la suma continua sent la durada de la WAV
        self.assertAlmostEqual(_suma(v.seccions), DUR, places=6)
        self.assertTrue(_contigues(v.seccions))

    def test_moure_el_fi_arrossega_la_seguent(self):
        v = _visor()
        self.assertTrue(v.mou_seccio(1, 10.0, 24.0))     # B = 10–24
        self.assertAlmostEqual(float(v.seccions[2][0]), 24.0, places=6)
        self.assertAlmostEqual(_suma(v.seccions), DUR, places=6)
        self.assertTrue(_contigues(v.seccions))

    def test_el_csv_del_disc_queda_normalitzat(self):
        v = _visor()
        v.mou_seccio(2, 25.0, 30.0)
        v._desa_i_regenera()
        s = _llegeix_abc(v.abc_csv)
        self.assertTrue(_contigues(s), "el CSV del disc té un forat intern")
        self.assertAlmostEqual(_suma(s), DUR, places=3)

    def test_moure_el_primer_obre_capcalera_sense_seccio(self):
        """Moure el 1r clip cap endavant no crea forat: s'hi posa una «-»."""
        v = _visor()
        self.assertTrue(v.mou_seccio(0, 2.0, 10.0))
        v._desa_i_regenera()
        self.assertTrue(_contigues(v.seccions))
        self.assertAlmostEqual(_suma(v.seccions), DUR, places=6)
        self.assertEqual(v.seccions[0][2], "-")
        self.assertTrue(_contigues(_llegeix_abc(v.abc_csv)))

    def test_xarxa_de_seguretat_si_un_cami_oblida_la_contiguitat(self):
        """Doble protecció: encara que una mutació crua deixi un forat, en
        desar el model queda normalitzat (amb «-» al forat) i el CSV net."""
        v = _visor()
        v.seccions[2] = (25.0, 30.0, "C", "C")     # mutació a pèl (vella manera)
        self.assertFalse(_contigues(v.seccions))
        v._desa_i_regenera()                        # → invariant de cobertura
        self.assertTrue(_contigues(v.seccions))
        self.assertAlmostEqual(_suma(v.seccions), DUR, places=6)
        self.assertEqual([s[2] for s in v.seccions], ["A", "B", "-", "C", "D"])
        self.assertTrue(_contigues(_llegeix_abc(v.abc_csv)))

    def test_la_xarxa_tambe_arregla_encavalcaments_i_durades_nulles(self):
        """Regles #2 i #8 a la xarxa de seguretat: un CSV editat a mà (o un
        projecte vell) pot portar seccions encavalcades o de durada zero.

        Auditoria 18-10-2026: sobrevivien. Mana la secció que ARRENCA MÉS TARD
        (el seu inici retalla el fi de l'anterior); les de durada nul·la fora.
        """
        a, b = pipeline.normalitza_cobertura(
            [], [(0.0, 10.0, "A", "A"), (5.0, 20.0, "B", "B")], DUR)
        self.assertEqual([(float(s[0]), float(s[1]), s[2]) for s in b],
                         [(0.0, 5.0, "A"), (5.0, DUR, "B")])
        self.assertTrue(_contigues(b))
        a, b = pipeline.normalitza_cobertura(
            [], [(0.0, 5.0, "A", "A"), (5.0, 5.0, "B", "B"),
                 (5.0, DUR, "C", "C")], DUR)
        self.assertEqual([s[2] for s in b], ["A", "C"])       # la nul·la, fora
        self.assertTrue(_contigues(b))
        a, b = pipeline.normalitza_cobertura(
            [], [(0.0, 20.0, "A", "A"), (2.0, 3.0, "B", "B"),
                 (5.0, DUR, "C", "C")], DUR)
        self.assertTrue(_contigues(b))
        self.assertAlmostEqual(_suma(b), DUR, places=6)

    def test_rebutja_si_un_vei_queda_sense_marge(self):
        v = _visor()
        with self.assertRaises(ValueError):
            v.mou_seccio(2, 10.01, 30.0)     # deixaria B amb 0,01 s (veí previ)
        with self.assertRaises(ValueError):
            v.mou_seccio(2, 20.0, 39.99)     # deixaria D amb 0,01 s (veí següent)
        # I el model NO ha quedat tocat pels intents rebutjats.
        self.assertEqual(v.seccions, SECCIONS)


class TestCamiMCP(_Base):
    """El camí que va reportar OC-6: `ac_move_section` pel pont."""

    def test_op_move_section_mante_la_contiguitat(self):
        v = _visor()
        ctx = mcp_bridge._Context(_FinestraFalsa(v))
        mcp_bridge._op_move_section(ctx, {"index": 2, "ini_s": 25.0, "fi_s": 30.0})
        self.assertAlmostEqual(float(v.seccions[1][1]), 25.0, places=6)
        self.assertTrue(_contigues(v.seccions))
        self.assertAlmostEqual(_suma(v.seccions), DUR, places=3)
        # i al disc (el pont hi desa)
        s = _llegeix_abc(v.abc_csv)
        self.assertTrue(_contigues(s))
        self.assertAlmostEqual(_suma(s), DUR, places=3)


class TestEditorDeSeccions(_Base):
    def test_canviar_l_inici_al_editor_mante_la_contiguitat(self):
        v = _visor()
        v._ed_kind, v._ed_idx = "section", 2
        v.ed_ini.setText("25.0")
        v.ed_nom.setText("C")
        v.ed_fam.setText("C")
        v._aplica_editor()
        self.assertAlmostEqual(float(v.seccions[1][1]), 25.0, places=2)
        self.assertTrue(_contigues(v.seccions))
        self.assertAlmostEqual(_suma(v.seccions), DUR, places=3)


class TestCarregaCSVAmbForat(_Base):
    def test_el_model_i_el_disc_queden_normalitzats_en_carregar(self):
        # CSV "antic"/dolent: A 0–10 i B 12–40 → forat de 10 a 12 s
        v = _visor(seccions=[(0.0, 10.0, "A", "A"), (12.0, 40.0, "B", "B")])
        # El MODEL queda contigu (amb una «-» que tapa el forat)
        self.assertTrue(_contigues(v.seccions))
        self.assertAlmostEqual(_suma(v.seccions), DUR, places=6)
        self.assertIn("-", [s[2] for s in v.seccions])
        # ... I el CSV DEL DISC ja s'ha reescrit (abans calia editar/exportar)
        s = _llegeix_abc(v.abc_csv)
        self.assertTrue(_contigues(s), "el CSV del disc encara té el forat")
        self.assertAlmostEqual(_suma(s), DUR, places=3)



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
