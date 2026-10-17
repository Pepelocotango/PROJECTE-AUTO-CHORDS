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
ACORDS = "0.0,2.0,C\n2.0,4.5,Am\n4.5,7.0,F\n7.0,10.0,G\n10.0,20.0,C\n"
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
    return [a[2][0] for a in v.acords]


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
        # Selecció NOMÉS d'acords (el Shift+clic ara abraça també les seccions;
        # aquí volem provar l'engaxament del bloc d'acords tot sol).
        v.timeline.select_multi({("chord", 0), ("chord", 1)})  # C, Am
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

    def test_copia_mou_el_cursor_al_final_del_bloc(self):
        """En copiar, el cursor va a l'inici del 1r clip NO seleccionat."""
        v = _visor()
        v.ves_a(0.0)
        v.timeline.select_multi({("chord", 0), ("chord", 1)})  # bloc C, Am
        v.timeline.copy_selection()
        self.assertAlmostEqual(float(v.timeline.get_position()), 4.5, places=6)
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
    def test_enganxa_seccions_retalla_al_final(self):
        v = _visor()
        v.timeline.select_clip("section", 0)          # A 0-5 (span 5)
        v.timeline.copy_selection()
        v.timeline.set_position(18.0, emit=False)     # 18+5 = 23 > 20 → retall
        v.timeline.paste_at_cursor()
        self.assertAlmostEqual(float(v.seccions[-1][0]), 18.0, places=6)
        self.assertAlmostEqual(float(v.seccions[-1][1]), 20.0, places=6)
        self.assertEqual(v.seccions[-1][2], "A")
        v.close()

    def test_copia_nomes_acords_no_toca_seccions(self):
        v = _visor()
        v.timeline.select_clip("chord", 0)
        v.timeline.copy_selection()
        sec_abans = [tuple(s) for s in v.seccions]
        v.timeline.set_position(6.0, emit=False)
        v.timeline.paste_at_cursor()
        self.assertEqual([tuple(s) for s in v.seccions], sec_abans,
                         "copiar només acords no ha de tocar l'estructura")
        v.close()

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


# ---------------------------------------------------------------------------
# Regressió del cas real (operador, 16-10-2026): «faig Ctrl+C i Ctrl+V i no
# funciona». El bloc d'acords 13.25→18.00 acaba EXACTAMENT a la marca següent
# (l'A de 18.500). La graella musical arrodonia l'àncora a 18.5019, la marca
# 18.500 sobrevivia a 1,9 ms de la nova i la validació (≥ 10 ms) rebuixava
# l'enganxat SENCER — i només ho deia al log (cap avís a pantalla).
# ---------------------------------------------------------------------------
ACORDS_OTIS = ("0.0,13.25,N\n13.25,13.50,Bbmaj7\n13.50,15.75,B\n15.75,17.25,C\n"
               "17.25,17.50,B/C#\n17.50,18.00,Bbmaj7\n18.00,18.50,Bbmaj7\n18.50,20.50,A\n"
               "20.50,22.50,G\n22.50,25.25,B\n25.25,30.00,C\n")
SECCIONS_OTIS = ("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
                 "0.0,15.0,15.0,A,A,1.1,7.1\n"
                 "15.0,30.0,15.0,B,B,7.1,14.1\n")


def _visor_otis():
    """Visor amb la graella del projecte d'Otis (el snap mou la vora ~2 ms)."""
    td = tempfile.mkdtemp()
    wav_path = os.path.join(td, "otis.wav")
    sortida = os.path.join(td, "AUTOCHORDS_otis")
    os.makedirs(sortida)
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * 30)
    ca = os.path.join(sortida, "acords.csv")
    with open(ca, "w", encoding="utf-8") as f:
        f.write(ACORDS_OTIS)
    sa = os.path.join(sortida, "estructura_ABC.csv")
    with open(sa, "w", encoding="utf-8") as f:
        f.write(SECCIONS_OTIS)
    v = visor_mod.Visor(wav_path, ca, sa, bpm=105.315, bpb=4, tempo_fix=True)
    v.td, v.sortida = td, sortida
    v.offset = 1.98
    v.timeline._offset = 1.98
    v.timeline._bpm, v.timeline._bpb = 105.315, 4
    v.timeline._tempo_fix = True
    v.timeline.set_snap(on=True, divisio="negra")
    return v


class TestAncoraDeMarca(_Base):
    """Prioritat de l'àncora: 1r EVENTS (marques del model), 2n graella."""

    def test_la_graella_mou_la_vora_del_bloc(self):
        v = _visor_otis()
        # la marca és a 18.500 i la graella musical hi arrodoneix ~2 ms més enllà
        self.assertAlmostEqual(v.timeline.snap(18.5), 18.5019, places=3)
        v.close()

    def test_la_marca_manda(self):
        v = _visor_otis()
        self.assertAlmostEqual(v.timeline.snap_a_marca(18.5), 18.5, places=9)
        self.assertAlmostEqual(v.timeline.snap_a_marca(15.0), 15.0, places=9)
        self.assertIsNone(v.timeline.snap_a_marca(11.0))   # lluny de totes
        v.close()


class TestEnganxatALaVoraDelBloc(_Base):
    """Regressió: enganxar un bloc que acaba a la marca següent ha de funcionar."""

    def _selecciona_bloc(self, v):
        # acords 13.25 · 13.50 · 15.75 · 17.25 · 17.50 · 18.00
        v.timeline.select_multi({("chord", i) for i in range(1, 7)})

    def test_enganxa_i_substitueix_la_regio(self):
        v = _visor_otis()
        self._selecciona_bloc(v)
        self._copia(v)
        # la còpia deixa el cursor al final del bloc (= la marca 18.500)
        self.assertAlmostEqual(v.timeline._pos_t, 18.5, places=6)
        v.timeline.paste_at_cursor()
        self.assertEqual(_temps_acords(v), [
            0.0, 13.25, 13.5, 15.75, 17.25, 17.5, 18.0,
            18.5, 18.75, 21.0, 22.5, 22.75, 23.25, 23.75, 25.25])
        self.assertEqual(_noms_acords(v), [
            "N", "Bbmaj7", "B", "C", "B/C#", "Bbmaj7", "Bbmaj7",
            "Bbmaj7", "B", "C", "B/C#", "Bbmaj7", "Bbmaj7", "B", "C"])
        # CAP marca a menys de 10 ms: era exactament la col·lisió que ho trencava
        for a, b in zip(v.acords, v.acords[1:]):
            self.assertGreaterEqual(float(b[0]) - float(a[0]), 0.01 - 1e-9)
        v.close()

    def test_rebuig_en_silenci_ja_no_existeix(self):
        """Un rebuig ha de sortir a pantalla (abans només anava al log)."""
        v = _visor_otis()
        avisos = []
        v.infoMissatge.connect(avisos.append)
        v._enganxa_seleccio({"chords": [(0.0, "X"), (0.002, "Y")],
                             "chord_len": 1.0, "bloc_fi": 18.5}, 18.5)
        self.assertTrue(avisos, "el rebuig hauria d'avisar a pantalla")
        self.assertIn("Enganxat no fet", avisos[0])
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
