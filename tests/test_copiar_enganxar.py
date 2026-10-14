"""Copiar/enganxar de clips (Ctrl+C / Ctrl+V), model «sobreescriure».

Regla d'or #4: els clips cobreixen SEMPRE tota la WAV i la cançó no pot
créixer → enganxar **substitueix** el tram `[T, T+L]` (les vores es tallen i
s'acoblen), mai insereix. Àncora `T` = cursor; si el cursor no s'ha mogut des de
la còpia, el final del bloc copiat.
"""
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from app import visor as visor_mod  # noqa: E402

# acords: 0 C · 2 Am · 4.5 F · 7 G · 10 C   |   durada 20 s
# seccions: A 0-5 · B 5-10 · C 10-20
ACORDS = "0.0,C\n2.0,Am\n4.5,F\n7.0,G\n10.0,C\n"
SECCIONS = ("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
            "0.0,5.0,5.0,A,A,1.1,5.1\n"
            "5.0,10.0,5.0,B,B,5.1,10.1\n"
            "10.0,20.0,10.0,C,C,10.1,20.1\n")


def _visor():
    td = tempfile.mkdtemp()
    wav_path = os.path.join(td, "tema.wav")
    sortida = os.path.join(td, "AUTOCHORDS_tema")
    os.makedirs(sortida)
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * 20)
    ca = os.path.join(sortida, "acords.csv")
    with open(ca, "w", encoding="utf-8") as f:
        f.write(ACORDS)
    sa = os.path.join(sortida, "estructura_ABC.csv")
    with open(sa, "w", encoding="utf-8") as f:
        f.write(SECCIONS)
    v = visor_mod.Visor(wav_path, ca, sa, bpm=120, bpb=4, tempo_fix=False)
    v.td, v.sortida = td, sortida
    return v


def _temps_acords(v):
    return [round(float(t), 3) for (t, *_r) in v.acords]


def _noms_acords(v):
    return [a[1] for a in v.acords]


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])

    def _copia(self, v):
        v.timeline.copy_selection()
        self.assertTrue(v.timeline.has_clipboard())


class TestSobreescriureAcords(_Base):
    def test_bloc_d_acords_sobreescriu_la_regio(self):
        v = _visor()
        v.timeline.select_clip("chord", 0)
        v.timeline.extend_selection("chord", 1)   # Shift: rang {0,1} → C, Am
        self._copia(v)
        v.timeline.set_position(6.0, emit=False)  # cursor MOGUT → T=6
        v.timeline.paste_at_cursor()
        # 0C · 2Am · 4.5F · 6C · 8Am · 10.5C
        self.assertEqual(_noms_acords(v), ["C", "Am", "F", "C", "Am", "C"])
        self.assertEqual(_temps_acords(v), [0.0, 2.0, 4.5, 6.0, 8.0, 10.5])
        for i in range(len(v.acords) - 1):
            self.assertLess(float(v.acords[i][0]), float(v.acords[i + 1][0]))
        self.assertEqual(len(v._undo_stack), 1)
        v.undo()
        self.assertEqual(_noms_acords(v), ["C", "Am", "F", "G", "C"])
        v.close()

    def test_ancora_per_defecte_es_el_final_del_bloc(self):
        """Si el cursor NO s'ha mogut des de la còpia, s'enganxa just després."""
        v = _visor()
        v.timeline.select_clip("chord", 0)        # C @ 0, bloc = [0, 2]
        self._copia(v)
        v.timeline.paste_at_cursor()              # sense moure el cursor
        # C @ 0 · C @ 2 (enganxat) · Am @ 4 · F 4.5 · G 7 · C 10
        self.assertEqual(_temps_acords(v), [0.0, 2.0, 4.0, 4.5, 7.0, 10.0])
        self.assertEqual(_noms_acords(v), ["C", "C", "Am", "F", "G", "C"])
        v.close()

    def test_retalla_al_final(self):
        v = _visor()
        v.timeline.select_clip("chord", 4)        # últim C @ 10 (fins a 20)
        self._copia(v)
        v.timeline.set_position(15.0, emit=False)
        v.timeline.paste_at_cursor()
        # … C @ 15 (segella fins a 20; mai s'allarga la cançó)
        self.assertEqual(_temps_acords(v)[-1], 15.0)
        self.assertAlmostEqual(float(v.acords[-1][0]), 15.0, places=6)
        v.close()


class TestSobreescriureSeccions(_Base):
    def test_selecciona_el_bloc_enganxat(self):
        v = _visor()
        v.timeline.select_clip("section", 1)      # B 5-10 (span 5)
        self._copia(v)
        v.timeline.set_position(12.0, emit=False)
        v.timeline.paste_at_cursor()
        # A 0-5 · B 5-10 · C 10-12 · B 12-17 · C 17-20
        self.assertEqual([s[2] for s in v.seccions], ["A", "B", "C", "B", "C"])
        sel = v.timeline.selected_keys()
        for k, i in sel:
            self.assertEqual(k, "section")
            self.assertEqual(v.seccions[i][2], "B")   # el bloc B enganxat
        v.close()


class TestSeleccioMixta(_Base):
    def test_seleccio_mixta_enganxa_els_dos_carrils(self):
        v = _visor()
        v.timeline.select_clip("chord", 0)        # C @ 0  (span 2)
        v.timeline.toggle_selection("section", 0)  # A 0-5 (span 5)  → mixta
        self._copia(v)
        v.timeline.set_position(10.0, emit=False)
        v.timeline.paste_at_cursor()
        # acords: … C @ 10, C @ 12 (marca)  |  seccions: A 10-15 dins C 10-20
        self.assertEqual(_noms_acords(v), ["C", "Am", "F", "G", "C", "C"])
        self.assertEqual([s[2] for s in v.seccions], ["A", "B", "A", "C"])
        for i in range(len(v.seccions) - 1):
            self.assertAlmostEqual(float(v.seccions[i][1]),
                                   float(v.seccions[i + 1][0]), places=6)
        v.close()


class TestSeleccioMixtaNoDeixaForats(_Base):
    def test_arranjaments_no_coincidents(self):
        """Selecció mixta amb clips que NO comencen alhora → sense forats."""
        v = _visor()
        v.timeline.select_clip("chord", 0)         # C @ 0
        v.timeline.toggle_selection("section", 1)  # B 5-10
        self._copia(v)
        v.timeline.set_position(12.0, emit=False)
        v.timeline.paste_at_cursor()
        for i in range(len(v.seccions) - 1):
            self.assertAlmostEqual(float(v.seccions[i][1]),
                                   float(v.seccions[i + 1][0]), places=6)
        self.assertAlmostEqual(float(v.seccions[0][0]), 0.0, places=6)
        self.assertAlmostEqual(float(v.seccions[-1][1]), 20.0, places=6)
        v.close()


class TestCasosBuits(_Base):
    def test_sense_clipboard_no_fa_res(self):
        v = _visor()
        n_ac, n_sec = len(v.acords), len(v.seccions)
        v.timeline.set_position(6.0, emit=False)
        v.timeline.paste_at_cursor()              # buffer buit → res
        self.assertEqual(len(v.acords), n_ac)
        self.assertEqual(len(v.seccions), n_sec)
        self.assertEqual(len(v._undo_stack), 0)
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
