"""DESTÍ del moviment d'un BLOC d'acords (PLA_EDICIO_LLIURE §6.3).

Regla de l'operador (17-10-2026): en moure un bloc (1 o més clips
consecutius) es **preserva la durada** del bloc i, al **destí**, el que queda
**a sota** es **talla** (se'n conserva el tros de fora) o **s'elimina** (si no
en queda cap tros). «Mana l'últim editat»: el bloc sempre guanya.

L'**origen** el tanca el veí: endavant, l'anterior s'estira fins a l'inici nou;
endarrere, el posterior s'estira fins al final nou.

Els dos exemples de l'operador (MATEIX dibuix, 10 s):
    C[0,2) Am[2,4) F[4,6) G[6,8) Em[8,10)
  · ENDAVANT: bloc [Am,F] +2 → C@0 Am@4 F@6 Em@8   (G, queia sota, eliminat)
  · ENDARRERE: bloc [F,G] −2 → C@0 F@2 G@4 Em@6    (Am, queia sota, eliminat)
"""
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app import pipeline  # noqa: E402
from app import visor as visor_mod  # noqa: E402

DURADA = 10.0
# C · Am · F · G · Em   (un clip de 2 s a 0, 2, 4, 6 i 8)
BASE = [(0.0, "C", "0"), (2.0, "Am", "0"), (4.0, "F", "0"),
        (6.0, "G", "0"), (8.0, "Em", "0")]
ACORDS = "0.0,C\n2.0,Am\n4.0,F\n6.0,G\n8.0,Em\n"
SECCIONS = ("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
            "0.0,5.0,5.0,A,A,1.1,5.1\n"
            "5.0,10.0,5.0,B,B,5.1,10.1\n")


def _times(acords):
    return [round(float(a[0]), 3) for a in acords]


def _noms(acords):
    return [a[1] for a in acords]


def _parells(acords, durada=DURADA):
    return [(round(float(a[0]), 3), a[1]) for a in acords]


def _clips(acords, durada=DURADA):
    """[(nom, inici, fi), …] — els clips són les marques consecutives."""
    out = []
    for i, (t, nom, *_r) in enumerate(acords):
        fi = float(acords[i + 1][0]) if i + 1 < len(acords) else durada
        out.append((nom, round(float(t), 3), round(float(fi), 3)))
    return out


class TestMouBlocAcords(unittest.TestCase):
    """La funció pura `pipeline.mou_bloc_acords` (model de marques)."""

    def test_exemple_endavant(self):
        """El 1r exemple de l'operador: bloc [Am,F] +2 → C@0 Am@4 F@6 Em@8."""
        nou = pipeline.mou_bloc_acords(BASE, 1, 2, +2.0, DURADA)
        self.assertEqual(_parells(nou),
                         [(0.0, "C"), (4.0, "Am"), (6.0, "F"), (8.0, "Em")])

    def test_exemple_endarrere(self):
        """El 2n exemple: bloc [F,G] −2 → C@0 F@2 G@4 Em@6."""
        nou = pipeline.mou_bloc_acords(BASE, 2, 3, -2.0, DURADA)
        self.assertEqual(_parells(nou),
                         [(0.0, "C"), (2.0, "F"), (4.0, "G"), (6.0, "Em")])

    def test_preserva_la_durada_del_bloc(self):
        """El bloc conserva la seva durada (2 clips = 4 s) en tots dos sentits."""
        for dt in (+1.0, +2.0, -1.0, -2.0):
            nou = pipeline.mou_bloc_acords(BASE, 1, 2, dt, DURADA)
            noms = _noms(nou)
            i1 = noms.index("Am")              # 1r clip del bloc
            i2 = noms.index("F")               # últim clip del bloc
            d = _times(nou)
            # la durada del bloc = de la 1a marca del bloc a la marca SEGÜENT
            self.assertAlmostEqual(d[i2 + 1] - d[i1], 4.0, places=6,
                                   msg=f"durada del bloc amb dt={dt}")

    def test_endavant_talla_el_que_queda_sota(self):
        """§6.3 endavant: el bloc tapa el seu tram nou; el que hi cau a sota es
        talla i el que en queda fora es conserva.

        Bloc [Am] (2 s) +3 → [5,7):  G (inici 6, sota el bloc) perd el cap
        → queda [7,8);  F (que acabava a 6) perd la cua → queda [4,5).
        """
        nou = pipeline.mou_bloc_acords(BASE, 1, 1, +3.0, DURADA)
        self.assertEqual(_clips(nou),
                         [("C", 0.0, 4.0), ("F", 4.0, 5.0), ("Am", 5.0, 7.0),
                          ("G", 7.0, 8.0), ("Em", 8.0, 10.0)])

    def test_endavant_llarg_no_toca_els_clips_del_mig(self):
        """🐞 Regressió (17-10-2026): un salt LLARG no s'ha de menjar els clips
        que queden entre l'origen i el destí — només s'ha de tapar el tram nou
        del bloc.

        El bloc [C] va de [0,2) a [5,7):  Am i F es queden QUIETS;  G (que cau
        sota el bloc) s'elimina;  la marca de 7 (material de sota) s'hi afegeix
        per preservar la durada.
        """
        nou = pipeline.mou_bloc_acords(BASE, 0, 0, +5.0, DURADA)
        self.assertEqual(_clips(nou),
                         [("Am", 2.0, 4.0), ("F", 4.0, 5.0), ("C", 5.0, 7.0),
                          ("G", 7.0, 8.0), ("Em", 8.0, 10.0)])
        self.assertEqual([n for _t, n in _parells(nou)],
                         ["Am", "F", "C", "G", "Em"])

    def test_endarrere_llarg_no_esborra_els_clips_del_mig(self):
        """Mirall endarrere: un salt llarg cap enrere tampoc no esborra res.

        Bloc [G] de [6,8) a [1,3):  Am (sota el bloc) s'elimina;  C i F es
        queden (F s'estira fins al buit que deixa el bloc). El bloc conserva
        la seva durada (2 s).
        """
        nou = pipeline.mou_bloc_acords(BASE, 3, 3, -5.0, DURADA)
        noms = _noms(nou)
        self.assertIn("C", noms)
        self.assertIn("F", noms)
        self.assertIn("G", noms)
        self.assertNotIn("Am", noms)          # sota el bloc → fora
        d, i = _times(nou), noms.index("G")
        self.assertAlmostEqual(d[i + 1] - d[i], 2.0, places=6)

    def test_endarrere_talla_el_final_i_elimina_el_principi(self):
        """§6.3 endarrere: el clip de sota perd la cua; si l'inici cau dins, fora.

        Bloc [G] (2 s) −3 → [3,5):  Am (final 4, cau dins) SE LI TALLA EL FINAL
        → [2,3);  F (inici 4, dins del bloc) S'ELIMINA.
        """
        nou = pipeline.mou_bloc_acords(BASE, 3, 3, -3.0, DURADA)
        self.assertEqual(_clips(nou),
                         [("C", 0.0, 2.0), ("Am", 2.0, 3.0),
                          ("G", 3.0, 5.0), ("Em", 5.0, 10.0)])
        self.assertNotIn("F", _noms(nou))

    def test_endavant_tapa_amb_el_vei_anterior(self):
        """L'origen el tanca l'anterior (s'estira fins a l'inici nou)."""
        # Bloc [F] de [4,6) a [5,7): Am (anterior) s'estira i tapa [2,5)
        nou = pipeline.mou_bloc_acords(BASE, 2, 2, +1.0, DURADA)
        self.assertEqual(_clips(nou), [("C", 0.0, 2.0), ("Am", 2.0, 5.0),
                                       ("F", 5.0, 7.0), ("G", 7.0, 8.0),
                                       ("Em", 8.0, 10.0)])

    def test_endarrere_tapa_amb_el_vei_posterior(self):
        """L'origen el tanca el posterior (s'estira fins al final nou)."""
        # Bloc [G] de [6,8) a [4,6): Em s'estira enrere fins a 6
        nou = pipeline.mou_bloc_acords(BASE, 3, 3, -2.0, DURADA)
        self.assertEqual(_clips(nou), [("C", 0.0, 2.0), ("Am", 2.0, 4.0),
                                       ("G", 4.0, 6.0), ("Em", 6.0, 10.0)])

    def test_primer_clip_deixa_forat_a_zero(self):
        """Si el bloc és el 1r i va endavant, el forat [0,a') no té veí: es
        queda perquè `normalitza_cobertura` hi posi la «N» (§6.1)."""
        nou = pipeline.mou_bloc_acords(BASE, 0, 0, +1.0, DURADA)
        self.assertEqual(round(float(nou[0][0]), 3), 1.0)
        self.assertEqual(_noms(nou)[0], "C")
        # la normalització hi afegeix la N de capçalera:
        net, _ = pipeline.normalitza_cobertura(nou, [], DURADA)
        self.assertEqual(_parells(net)[0], (0.0, "N"))

    def test_bloc_sencer_no_es_pot_moure(self):
        """Un bloc que ja ocupa tota la WAV no té lloc: no es mou."""
        self.assertEqual(pipeline.mou_bloc_acords(BASE, 0, 4, +0.5, DURADA),
                         [tuple(a) for a in BASE])
        self.assertEqual(pipeline.mou_bloc_acords(BASE, 0, 4, -0.5, DURADA),
                         [tuple(a) for a in BASE])

    def test_clamp_a_la_wav(self):
        """El bloc no pot sortir de la WAV (ni pel davant ni pel darrere)."""
        fwd = pipeline.mou_bloc_acords(BASE, 1, 2, +99.0, DURADA)
        self.assertLessEqual(max(_times(fwd)), DURADA)
        self.assertAlmostEqual(_clips(fwd)[-1][2], DURADA, places=6)  # cobrint el final
        bwd = pipeline.mou_bloc_acords(BASE, 2, 3, -99.0, DURADA)
        self.assertAlmostEqual(_times(bwd)[0], 0.0, places=6)

    def test_delta_zero_no_canvia_res(self):
        self.assertEqual(pipeline.mou_bloc_acords(BASE, 1, 2, 0.0, DURADA),
                         [tuple(a) for a in BASE])

    def test_la_cobertura_es_te_que_poder_normalitzar_sempre(self):
        """Després de qualsevol moviment, el model cobreix tota la WAV (un cop
        normalitzat): la normalització no ha de petar mai."""
        for first, last in [(0, 0), (1, 1), (4, 4), (0, 1), (1, 3), (2, 4)]:
            for dt in (-3.0, -1.0, +1.0, +3.0):
                nou = pipeline.mou_bloc_acords(BASE, first, last, dt, DURADA)
                net, _ = pipeline.normalitza_cobertura(nou, [], DURADA)
                self.assertAlmostEqual(float(net[0][0]), 0.0, places=6)
                self.assertLess(float(net[-1][0]), DURADA)


# --------------------------------------------------------------------------
# El gest complet (Visor + Timeline): arrossegar el cos d'un clip seleccionat
# --------------------------------------------------------------------------
class _BaseGest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = (visor_mod.QApplication.instance()
                    or visor_mod.QApplication([]))

    def _visor(self):
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "tema.wav")
        out = os.path.join(td, "AUTOCHORDS_tema")
        os.makedirs(out)
        with wave.open(wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * int(DURADA))
        ca = os.path.join(out, "acords.csv")
        sa = os.path.join(out, "estructura_ABC.csv")
        with open(ca, "w", encoding="utf-8") as f:
            f.write(ACORDS)
        with open(sa, "w", encoding="utf-8") as f:
            f.write(SECCIONS)
        v = visor_mod.Visor(wav, ca, sa, bpm=120, bpb=4, tempo_fix=False)
        v.td, v.sortida = td, out
        return v

    def _arrossega(self, v, idx, dt, seleccio):
        """Simula el gest: arrossegar el COS del clip `idx` un delta `dt`."""
        from app.timeline_items import ChordItem
        tl = v.timeline
        tl.set_snap(False)                     # determinisme
        tl.select_multi({("chord", i) for i in seleccio})
        it = tl._chord_items[idx]
        it._drag_mode = ChordItem.ZONE_BODY
        it._drag_t0 = float(tl._acords[idx][0])
        tl.editStarted.emit()                  # = mousePress (marca el desfer)
        tl._on_chord_time_changed(idx, it._drag_t0 + dt)
        # el cos també emet endTimeChanged: no ha de moure res
        tl._on_chord_end_changed(idx, it._drag_t0 + dt)
        tl._emit_edit_finished()
        return tl


class TestGestMoviment(_BaseGest):
    def test_endavant_exemple_operador(self):
        v = self._visor()
        self._arrossega(v, 1, +2.0, {1, 2})    # bloc [Am,F] +2
        self.assertEqual(_parells(v.acords),
                         [(0.0, "C"), (4.0, "Am"), (6.0, "F"), (8.0, "Em")])
        v.close()

    def test_endarrere_exemple_operador(self):
        v = self._visor()
        self._arrossega(v, 2, -2.0, {2, 3})    # bloc [F,G] −2
        self.assertEqual(_parells(v.acords),
                         [(0.0, "C"), (2.0, "F"), (4.0, "G"), (6.0, "Em")])
        v.close()

    def test_un_sol_desfer_reverteix_el_moviment(self):
        v = self._visor()
        self._arrossega(v, 1, +2.0, {1, 2})
        v.undo()
        self.assertEqual(_parells(v.acords), _parells(BASE))
        v.close()

    def test_el_timeline_i_el_visor_queden_d_acord(self):
        v = self._visor()
        tl = self._arrossega(v, 1, +2.0, {1, 2})
        self.assertEqual(_parells(tl._acords), _parells(v.acords))
        # el re-render dels items es fa al cicle següent (QTimer): en processar
        # els events, els items han de quadrar amb el model nou.
        self._app.processEvents()
        items = [(round(it.t, 3), it.name) for it in tl._chord_items]
        self.assertEqual(items, [(0.0, "C"), (4.0, "Am"), (6.0, "F"),
                                 (8.0, "Em")])
        v.close()


# --------------------------------------------------------------------------
# Paritat d'edició #11: la MATEIXA regla per a l'estructura (§6.3)
# --------------------------------------------------------------------------
SECCIONS_BASE = [(0.0, 16.15, "A", "A"), (16.15, 31.97, "B", "B"),
                 (31.97, 48.0, "C", "C"), (48.0, 68.0, "D", "D"),
                 (68.0, 90.0, "E", "E"), (90.0, 112.0, "F", "F"),
                 (112.0, 128.0, "G", "G"), (128.0, 165.7339, "H", "H")]
DURADA_S = 165.7339


class TestMouBlocSeccions(unittest.TestCase):
    """`pipeline.mou_bloc_seccions`: mateixa regla que `mou_bloc_acords` (#11)."""

    def _taula(self, seccions):
        return [(s[2], round(float(s[0]), 3), round(float(s[1]), 3))
                for s in seccions]

    def _contigu_i_cobert(self, seccions):
        if abs(float(seccions[0][0])) > 1e-6:
            return False
        if abs(float(seccions[-1][1]) - DURADA_S) > 1e-6:
            return False
        return all(abs(float(x[1]) - float(y[0])) < 1e-6
                   for x, y in zip(seccions, seccions[1:]))

    def test_cas_operador_A_al_compas_29(self):
        """La secció A [0,16.15) al compàs 29.1 (64,615385 s): conserva la
        durada, el forat de l'origen queda en «-» i el destí es talla (D i E)."""
        nou = pipeline.mou_bloc_seccions(SECCIONS_BASE, 0, 0, 64.615385,
                                         DURADA_S)
        self.assertEqual(self._taula(nou),
                         [("-", 0.0, 16.15), ("B", 16.15, 31.97),
                          ("C", 31.97, 48.0), ("D", 48.0, 64.615),
                          ("A", 64.615, 80.765), ("E", 80.765, 90.0),
                          ("F", 90.0, 112.0), ("G", 112.0, 128.0),
                          ("H", 128.0, 165.734)])
        self.assertTrue(self._contigu_i_cobert(nou))

    def test_conserva_la_durada_i_no_toca_el_mig(self):
        """Bloc [E,F] −10 s: E i F conserven els seus 22 s; D i G queden tallats
        (no es perd cap secció)."""
        nou = pipeline.mou_bloc_seccions(SECCIONS_BASE, 4, 5, -10.0, DURADA_S)
        L = {s[2]: (float(s[0]), float(s[1])) for s in nou}
        self.assertAlmostEqual(L["E"][1] - L["E"][0], 22.0, places=6)
        self.assertAlmostEqual(L["F"][1] - L["F"][0], 22.0, places=6)
        self.assertEqual(set(L), {"A", "B", "C", "D", "E", "F", "G", "H"})
        self.assertAlmostEqual(L["D"][1], 58.0, places=6)    # tallat
        self.assertAlmostEqual(L["G"][0], 102.0, places=6)   # s'estira al forat
        self.assertTrue(self._contigu_i_cobert(nou))

    def test_no_surt_de_la_wav(self):
        for dt in (-999.0, +999.0):
            nou = pipeline.mou_bloc_seccions(SECCIONS_BASE, 2, 3, dt, DURADA_S)
            self.assertTrue(self._contigu_i_cobert(nou))


if __name__ == "__main__":   # pragma: no cover
    unittest.main()
