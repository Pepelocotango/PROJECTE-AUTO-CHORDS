"""Suite de test — Edicio

> Suite CONSOLIDADA (Fase 4, 2026-10-19): fusiona 22 mòduls de test que abans
> vivien separats a `tests/`. Cada bloc conserva el seu codi original íntegre
> (només s'han renombrat els símbols de nivell superior que xocaven i s'han
> unificat els imports). Cobertura intacta: cap test eliminat.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene: esborra els temporals en plegar

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
import tempfile
import wave
from app import pipeline
from app import visor as visor_mod
import csv
from PyQt5.QtWidgets import QApplication
from app import main as app_main
from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtCore import QPoint, QPointF
from PyQt5.QtWidgets import QInputDialog, QListWidget, QMenu
from unittest.mock import patch
from app import timeline_items
from app import config, plataforma
from app import visor
from PyQt5.QtGui import QMouseEvent
from app.timeline_base import LANE_ACC_TOP, LANE_H, LANE_SEC_TOP
from app import projecte


def tearDownModule():
    _partir_seccio_tearDownModule()
    _copiar_enganxar_tearDownModule()
    _nudge_tearDownModule()
    _regla11_paritat_tearDownModule()
    _rename_sanejat_tearDownModule()
    _rename_seleccio_tearDownModule()
    _seccions_contigues_tearDownModule()
    _temps_fora_rang_tearDownModule()
    _cobertura_rare_tearDownModule()
    _cobertura_viu_tearDownModule()
    _regles_or_tearDownModule()
    _troba_reemplaca_tearDownModule()
    _undo_llarg_tearDownModule()
    _undo_temps_tearDownModule()
    _editor_renom_tearDownModule()
    _editor_feedback_tearDownModule()
    _eina_marc_tearDownModule()
    _sense_analisi_tearDownModule()
    _dreceres_completes_tearDownModule()


# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_moviment_desti.py
# ══════════════════════════════════════════════════════════════════════════
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


DURADA = 10.0
# C · Am · F · G · Em   (un clip de 2 s a 0, 2, 4, 6 i 8)
BASE = [(0.0, "C", "0"), (2.0, "Am", "0"), (4.0, "F", "0"),
        (6.0, "G", "0"), (8.0, "Em", "0")]
ACORDS = "0.0,2.0,C\n2.0,4.0,Am\n4.0,6.0,F\n6.0,8.0,G\n8.0,10.0,Em\n"
SECCIONS = ("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
            "0.0,5.0,5.0,A,A,1.1,5.1\n"
            "5.0,10.0,5.0,B,B,5.1,10.1\n")


def _times(acords):
    return [round(float(a[0]), 3) for a in acords]


def _noms(acords):
    return [a[1] for a in acords]


def _parells(acords, durada=DURADA):
    return [(round(float(a[0]), 3),
             a.nom if isinstance(a, pipeline.Clip) else a[1]) for a in acords]


def _clips(acords, durada=DURADA):
    """[(nom, inici, fi), …] — els clips són les marques consecutives."""
    out = []
    for i, a in enumerate(acords):
        fi = float(acords[i + 1][0]) if i + 1 < len(acords) else durada
        out.append(((a.nom if isinstance(a, pipeline.Clip) else a[1]),
                    round(float(a[0]), 3), round(float(fi), 3)))
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
        # 🔄 canònic (17-10): l'origen [0,2) no té veí anterior → hi va la «N».
        self.assertEqual(_clips(nou),
                         [("N", 0.0, 2.0), ("Am", 2.0, 4.0), ("F", 4.0, 5.0),
                          ("C", 5.0, 7.0), ("G", 7.0, 8.0), ("Em", 8.0, 10.0)])
        self.assertEqual([n for _t, n in _parells(nou)],
                         ["N", "Am", "F", "C", "G", "Em"])

    def test_endarrere_llarg_no_esborra_els_clips_del_mig(self):
        """Mirall endarrere: un salt llarg cap enrere tampoc no esborra res.

        Bloc [G] de [6,8) a [1,3):  C es talla ([0,1));  Am també es TALLA
        ([3,4): només quedava cobert en part → conserva el nom);  Em tanca
        l'origen ([6,10)). El bloc conserva la seva durada (2 s).
        """
        nou = pipeline.mou_bloc_acords(BASE, 3, 3, -5.0, DURADA)
        noms = _noms(nou)
        self.assertEqual(_clips(nou),
                         [("C", 0.0, 1.0), ("G", 1.0, 3.0), ("Am", 3.0, 4.0),
                          ("F", 4.0, 6.0), ("Em", 6.0, 10.0)])
        self.assertIn("Am", noms)          # 🔄 canònic: es talla, no s'esborra
        d, i = _times(nou), noms.index("G")
        self.assertAlmostEqual(d[i + 1] - d[i], 2.0, places=6)

    def test_endarrere_talla_el_final_i_elimina_el_principi(self):
        """§6.3 endarrere: el clip de sota perd la cua; si l'inici cau dins, fora.

        Bloc [G] (2 s) −3 → [3,5):  Am (final 4, cau dins) SE LI TALLA EL FINAL
        → [2,3);  F NO queda sobrepassat → es TALLA i conserva el nom → [5,6).
        """
        nou = pipeline.mou_bloc_acords(BASE, 3, 3, -3.0, DURADA)
        # 🔄 CAS DE REFERÈNCIA (corregit 17-10: abans el F s'absorbia dins l'Em).
        self.assertEqual(_clips(nou),
                         [("C", 0.0, 2.0), ("Am", 2.0, 3.0), ("G", 3.0, 5.0),
                          ("F", 5.0, 6.0), ("Em", 6.0, 10.0)])
        self.assertEqual(_times(nou)[_noms(nou).index("F")], 5.0)

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
        self.assertEqual(_parells(nou)[0], (0.0, "N"))   # 🔄 ho posa l'operació
        self.assertEqual(_noms(nou)[1], "C")
        self.assertEqual(round(float(nou[1][0]), 3), 1.0)
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

    def test_vores_lliures_estira_i_elimina_el_seguent(self):
        """Vores LLIURES (§6.6): estirar el fi d'un acord per damunt del veí
        l'elimina o el talla (§6.3), en comptes d'aturar-se a la seva vora."""
        v = self._visor()          # C[0,2) Am[2,4) F[4,6) G[6,8) Em[8,10)
        tl = v.timeline
        tl._on_chord_end_changed(0, 5.0)      # C fins a 5 → Am eliminat, F tallat
        self._app.processEvents()
        self.assertEqual(_parells(v.acords),
                         [(0.0, "C"), (5.0, "F"), (6.0, "G"), (8.0, "Em")])
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


# --------------------------------------------------------------------------
# Estirar/encongir les VORES (mateixa lògica que moure, §6.3)
# --------------------------------------------------------------------------
class TestRedimensionaAcord(unittest.TestCase):
    """`pipeline.redimensiona_acord`: el clip editat mana; el de sota es talla o
    s'elimina; el buit el tanca el veí o, si no n'hi ha, hi va «N»."""

    def test_estirar_dreta_es_menja_el_de_sota(self):
        """C (0→2) fins a 5: Am i F queden coberts → Am eliminat, F tallat."""
        nou = pipeline.redimensiona_acord(BASE, 0, "fi", 5.0, DURADA)
        self.assertEqual(_clips(nou),
                         [("C", 0.0, 5.0), ("F", 5.0, 6.0), ("G", 6.0, 8.0),
                          ("Em", 8.0, 10.0)])

    def test_encongir_dreta_estira_el_seguent(self):
        """C fins a 1,5: el següent (Am) s'estira enrere."""
        nou = pipeline.redimensiona_acord(BASE, 0, "fi", 1.5, DURADA)
        self.assertEqual(_clips(nou)[:2], [("C", 0.0, 1.5), ("Am", 1.5, 4.0)])

    def test_estirar_esquerra_es_menja_el_del_davant(self):
        """Em (8→10) fins a 5: G queda cobert i F escurçat."""
        nou = pipeline.redimensiona_acord(BASE, 4, "ini", 5.0, DURADA)
        self.assertEqual(_clips(nou),
                         [("C", 0.0, 2.0), ("Am", 2.0, 4.0), ("F", 4.0, 5.0),
                          ("Em", 5.0, 10.0)])

    def test_encongir_esquerra_estira_l_anterior(self):
        """Em fins a 9: G s'estira fins a 9."""
        nou = pipeline.redimensiona_acord(BASE, 4, "ini", 9.0, DURADA)
        self.assertEqual(_clips(nou)[-2:], [("G", 6.0, 9.0), ("Em", 9.0, 10.0)])

    def test_primer_clip_encongit_deixa_forat_amb_N(self):
        """El 1r clip encongit per l'esquerra: el forat [0,t) → «N» (normalitzant)."""
        nou = pipeline.redimensiona_acord(BASE, 0, "ini", 1.0, DURADA)
        net, _ = pipeline.normalitza_cobertura(nou, [], DURADA)
        self.assertEqual(_parells(net)[0], (0.0, "N"))
        self.assertEqual(_clips(net)[1], ("C", 1.0, 2.0))

    def test_ultim_clip_encongit_deixa_forat_amb_N(self):
        """El darrer clip encongit per la dreta: el buit [t, durada) → «N»."""
        nou = pipeline.redimensiona_acord(BASE, 4, "fi", 9.0, DURADA)
        self.assertEqual(_clips(nou)[-2:], [("Em", 8.0, 9.0), ("N", 9.0, 10.0)])

    def test_moure_el_darrer_bloc_deixa_N(self):
        """Regressió: moure enrere el darrer bloc no ha d'allargar el clip; el
        buit que queda → «N»."""
        nou = pipeline.mou_bloc_acords(BASE, 4, 4, -2.0, DURADA)
        self.assertEqual(_clips(nou),
                         [("C", 0.0, 2.0), ("Am", 2.0, 4.0), ("F", 4.0, 6.0),
                          ("Em", 6.0, 8.0), ("N", 8.0, 10.0)])

    def test_cap_moviment_si_no_canvia_res(self):
        self.assertEqual(pipeline.redimensiona_acord(BASE, 2, "fi", 6.0, DURADA),
                         [tuple(a) for a in BASE])


# --------------------------------------------------------------------------
# Vores de l'ESTRUCTURA (paritat #11: mateix nucli que els acords)
# --------------------------------------------------------------------------
SECC = [(0.0, 2.0, "A", "A"), (2.0, 4.0, "B", "B"), (4.0, 6.0, "C", "C"),
        (6.0, 8.0, "D", "D"), (8.0, 10.0, "E", "E")]


class TestRedimensionaSeccio(unittest.TestCase):
    """`pipeline.redimensiona_seccio`: la mateixa regla §6.3 que els acords."""

    def test_estirar_dreta_es_menja_el_de_sota(self):
        """A (0→2) fins a 5: B queda eliminada i C tallada."""
        nou = pipeline.redimensiona_seccio(SECC, 0, "fi", 5.0, 10.0)
        self.assertEqual(nou, [(0.0, 5.0, "A", "A"), (5.0, 6.0, "C", "C"),
                              (6.0, 8.0, "D", "D"), (8.0, 10.0, "E", "E")])

    def test_encongir_dreta_estira_el_seguent(self):
        nou = pipeline.redimensiona_seccio(SECC, 0, "fi", 1.5, 10.0)
        self.assertEqual(nou, [(0.0, 1.5, "A", "A"), (1.5, 4.0, "B", "B"),
                              (4.0, 6.0, "C", "C"), (6.0, 8.0, "D", "D"),
                              (8.0, 10.0, "E", "E")])

    def test_estirar_esquerra_es_menja_el_del_davant(self):
        """E (8→10) fins a 5: D eliminada, C escurçada i B intacta."""
        nou = pipeline.redimensiona_seccio(SECC, 4, "ini", 5.0, 10.0)
        self.assertEqual(nou, [(0.0, 2.0, "A", "A"), (2.0, 4.0, "B", "B"),
                              (4.0, 5.0, "C", "C"), (5.0, 10.0, "E", "E")])

    def test_encongir_esquerra_estira_l_anterior(self):
        nou = pipeline.redimensiona_seccio(SECC, 4, "ini", 9.0, 10.0)
        self.assertEqual(nou[-2:], [(6.0, 9.0, "D", "D"), (9.0, 10.0, "E", "E")])

    def test_primer_encongit_deixa_forat_amb_guio(self):
        """La 1a secció encongida: el forat [0,t) → «-» (normalitzat)."""
        nou = pipeline.redimensiona_seccio(SECC, 0, "ini", 1.0, 10.0)
        self.assertEqual(nou[0], (0.0, 1.0, "-", "-"))
        self.assertEqual(nou[1], (1.0, 2.0, "A", "A"))

    def test_ultim_encongit_deixa_forat_amb_guio(self):
        nou = pipeline.redimensiona_seccio(SECC, 4, "fi", 9.0, 10.0)
        self.assertEqual(nou[-2:], [(8.0, 9.0, "E", "E"), (9.0, 10.0, "-", "-")])

    def test_resultat_sempre_contigu_i_cobert(self):
        for idx, vora, t in ((0, "fi", 5.0), (0, "ini", 1.0), (2, "fi", 7.0),
                             (4, "ini", 3.0), (1, "fi", 3.0), (3, "ini", 5.0)):
            nou = pipeline.redimensiona_seccio(SECC, idx, vora, t, 10.0)
            self.assertAlmostEqual(nou[0][0], 0.0, msg=f"{idx}/{vora}/{t}")
            self.assertAlmostEqual(nou[-1][1], 10.0, msg=f"{idx}/{vora}/{t}")
            for a, b in zip(nou, nou[1:]):
                self.assertAlmostEqual(a[1], b[0], msg=f"{idx}/{vora}/{t}")

    def test_cap_moviment_si_no_canvia_res(self):
        self.assertEqual(pipeline.redimensiona_seccio(SECC, 2, "fi", 6.0, 10.0),
                         SECC)

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_partir_seccio.py
# ══════════════════════════════════════════════════════════════════════════
"""A2: PARTIR una secció.

En un model saturat —les seccions cobreixen TOTA la WAV (regla d'or #4)— el
menú «Afegeix secció» no pot afegir res (qualsevol secció nova solaparia). La
manera natural d'afegir-ne una de nova és **partir** la que hi ha al punt del
cursor: `Visor.parteix_seccio()` (+ l'acció de menú i el menú contextual).
"""


DUR = 30.0
_partir_seccio__SECCIONS = [(0.0, 10.0, "A", "A"), (10.0, DUR, "B", "B")]


def _escriu_wav(ruta, dur=DUR):
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * int(44100 * dur))


def _llegeix_abc(ruta):
    files = []
    with open(ruta, encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) < 4 or row[0].startswith("inici"):
                continue
            files.append((float(row[0]), float(row[1]), row[3], row[4]))
    return files


def _visor(seccions=None):
    seccions = _partir_seccio__SECCIONS if seccions is None else seccions
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "tema.wav")
    _escriu_wav(wav)
    sortida = pipeline.carpeta_sortida(wav)
    os.makedirs(sortida, exist_ok=True)
    ca = os.path.join(sortida, "acords.csv")
    with open(ca, "w", encoding="utf-8") as f:
        f.write("0.0,4.0,C\n4.0,10.0,Am\n")
    sa = os.path.join(sortida, "estructura_ABC.csv")
    with open(sa, "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n")
        for ini, fi, L, fam in seccions:
            f.write(f"{ini},{fi},{fi - ini},{L},{fam},1,1\n")
    v = visor_mod.Visor(wav, ca, sa, 120.0, 4, True)
    v.td, v.sortida, v.abc_csv = td, sortida, sa
    return v


def _finestra():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "t.wav")
    _escriu_wav(wav)
    ac = os.path.join(td, "AUTOCHORDS_t")
    os.makedirs(ac)
    with open(os.path.join(ac, "acords.csv"), "w", encoding="utf-8") as f:
        f.write("0.0,4.0,C\n4.0,10.0,Am\n")
    with open(os.path.join(ac, "estructura_ABC.csv"), "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n")
        for ini, fi, L, fam in _partir_seccio__SECCIONS:
            f.write(f"{ini},{fi},{fi - ini},{L},{fam},1,1\n")
    w = app_main.Finestra()
    w.wav_edit.setText(wav)
    w._carrega_visor(wav)
    return w


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])


class TestPartirSeccio(_Base):
    def test_parteix_en_dos_trossos(self):
        v = _visor()
        self.assertEqual(v.parteix_seccio(0, 4.0, "Z"), 1)
        self.assertEqual([s[2] for s in v.seccions], ["A", "Z", "B"])
        self.assertAlmostEqual(v.seccions[0][1], 4.0, places=6)
        self.assertAlmostEqual(v.seccions[1][0], 4.0, places=6)
        self.assertAlmostEqual(v.seccions[1][1], 10.0, places=6)
        # la cobertura (#4) i la contigüitat (#2) es mantenen
        self.assertAlmostEqual(sum(float(b) - float(a) for a, b, _L, _F
                                   in v.seccions), DUR, places=6)

    def test_lletra_i_familia_per_defecte(self):
        v = _visor()
        v.parteix_seccio(1, 20.0)
        self.assertEqual([s[2] for s in v.seccions], ["A", "B", "B"])
        self.assertEqual(v.seccions[2][3], "B", "la família s'ha de conservar")

    def test_fora_de_la_seccio_es_rebutja(self):
        v = _visor()
        self.assertFalse(v.parteix_seccio(0, 12.0, "Z"))
        self.assertEqual(v.seccions, _partir_seccio__SECCIONS)

    def test_massa_a_prop_de_la_vora_es_rebutja(self):
        v = _visor()
        self.assertFalse(v.parteix_seccio(0, 0.0001, "Z"))  # < MIN_SECCIO_S
        self.assertFalse(v.parteix_seccio(0, 9.9999, "Z"))
        self.assertEqual(v.seccions, _partir_seccio__SECCIONS)

    def test_index_invalid(self):
        v = _visor()
        self.assertFalse(v.parteix_seccio(9, 4.0))
        self.assertEqual(v.seccions, _partir_seccio__SECCIONS)

    def test_es_pot_desfer(self):
        v = _visor()
        v.parteix_seccio(0, 4.0, "Z")
        self.assertEqual(len(v.seccions), 3)
        v.undo()
        self.assertEqual(v.seccions, _partir_seccio__SECCIONS)


class TestMenuContextual(_Base):
    def test_l_entrada_esta_activa_en_una_seccio(self):
        from PyQt5.QtCore import QPoint
        from PyQt5.QtWidgets import QMenu
        v = _visor()
        capt = {}
        orig = QMenu.exec_

        def fake(self, pos, *a):
            capt["a"] = [(x.text(), x.isEnabled()) for x in self.actions()
                         if not x.isSeparator()]
            return None
        QMenu.exec_ = fake
        try:
            v._on_clip_context_menu("section", 0, QPoint(0, 0))
        finally:
            QMenu.exec_ = orig
        self.assertTrue(dict(capt["a"]).get("Parteix la secció…"),
                        "hauria d'estar activa sobre una secció")


class TestPartirDesDelMenu(_Base):
    def test_el_menu_parteix_al_cursor(self):
        from unittest.mock import patch
        import PyQt5.QtWidgets as QW
        w = _finestra()
        v = w.visor_ref
        v.ves_a(4.0)
        with patch.object(QW.QInputDialog, "getText", return_value=("Z", True)):
            w._parteix_seccio_ui()
        self.assertEqual([s[2] for s in v.seccions], ["A", "Z", "B"])
        self.assertAlmostEqual(float(v.seccions[0][1]), 4.0, places=3)
        # i el CSV d'estructura del disc reflecteix el tall
        self.assertEqual(len(_llegeix_abc(v._carpeta_acords() +
                                          "/estructura_ABC.csv")), 3)

    def test_el_menu_avisa_si_no_hi_ha_seccio_al_cursor(self):
        w = _finestra()
        v = w.visor_ref
        v.seccions = []
        v.timeline.set_data(v.acords, v.seccions)
        v.ves_a(4.0)
        w._parteix_seccio_ui()          # no ha de petar ni canviar res
        self.assertEqual(len(v.seccions), 0)

    def test_es_desfer_des_del_menu(self):
        from unittest.mock import patch
        import PyQt5.QtWidgets as QW
        w = _finestra()
        v = w.visor_ref
        v.ves_a(4.0)
        with patch.object(QW.QInputDialog, "getText", return_value=("Z", True)):
            w._parteix_seccio_ui()
        self.assertEqual(len(v.seccions), 3)
        w._undo_visor()
        self.assertEqual(len(v.seccions), 2)


def _partir_seccio_tearDownModule():
    # Neteja ORDENADA dels objectes Qt del mòdul (evita destrucció pel GC en un
    # test posterior -> access violation intermitent). Vegeu tests/_qt_neteja.py.
    try:
        import _qt_neteja
    except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_copiar_enganxar.py
# ══════════════════════════════════════════════════════════════════════════
"""Copiar/enganxar de clips (Ctrl+C / Ctrl+V), model «sobreescriure».

Regla d'or #4: els clips cobreixen SEMPRE tota la WAV i la cançó no pot
créixer → enganxar **substitueix** el tram `[T, T+L]` (les vores es tallen i
s'acoblen), mai insereix. Àncora `T` = cursor; si el cursor no s'ha mogut des de
la còpia, el final del bloc copiat.
"""


# acords: 0 C · 2 Am · 4.5 F · 7 G · 10 C   |   durada 20 s
# seccions: A 0-5 · B 5-10 · C 10-20
_copiar_enganxar__ACORDS = "0.0,2.0,C\n2.0,4.5,Am\n4.5,7.0,F\n7.0,10.0,G\n10.0,20.0,C\n"
_copiar_enganxar__SECCIONS = ("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
            "0.0,5.0,5.0,A,A,1.1,5.1\n"
            "5.0,10.0,5.0,B,B,5.1,10.1\n"
            "10.0,20.0,10.0,C,C,10.1,20.1\n")


def _copiar_enganxar___visor():
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
        f.write(_copiar_enganxar__ACORDS)
    sa = os.path.join(sortida, "estructura_ABC.csv")
    with open(sa, "w", encoding="utf-8") as f:
        f.write(_copiar_enganxar__SECCIONS)
    v = visor_mod.Visor(wav_path, ca, sa, bpm=120, bpb=4, tempo_fix=False)
    v.td, v.sortida = td, sortida
    return v


def _temps_acords(v):
    return [round(float(t), 3) for (t, *_r) in v.acords]


def _noms_acords(v):
    return [a[2][0] for a in v.acords]


class _copiar_enganxar___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])

    def _copia(self, v):
        v.timeline.copy_selection()
        self.assertTrue(v.timeline.has_clipboard())


class TestSobreescriureAcords(_copiar_enganxar___Base):
    def test_bloc_d_acords_sobreescriu_la_regio(self):
        v = _copiar_enganxar___visor()
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
        v = _copiar_enganxar___visor()
        v.ves_a(0.0)
        v.timeline.select_multi({("chord", 0), ("chord", 1)})  # bloc C, Am
        v.timeline.copy_selection()
        self.assertAlmostEqual(float(v.timeline.get_position()), 4.5, places=6)
        v.close()

    def test_ancora_per_defecte_es_el_final_del_bloc(self):
        """Si el cursor NO s'ha mogut des de la còpia, s'enganxa just després."""
        v = _copiar_enganxar___visor()
        v.timeline.select_clip("chord", 0)        # C @ 0, bloc = [0, 2]
        self._copia(v)
        v.timeline.paste_at_cursor()              # sense moure el cursor
        # C @ 0 · C @ 2 (enganxat) · Am @ 4 · F 4.5 · G 7 · C 10
        self.assertEqual(_temps_acords(v), [0.0, 2.0, 4.0, 4.5, 7.0, 10.0])
        self.assertEqual(_noms_acords(v), ["C", "C", "Am", "F", "G", "C"])
        v.close()

    def test_retalla_al_final(self):
        v = _copiar_enganxar___visor()
        v.timeline.select_clip("chord", 4)        # últim C @ 10 (fins a 20)
        self._copia(v)
        v.timeline.set_position(15.0, emit=False)
        v.timeline.paste_at_cursor()
        # … C @ 15 (segella fins a 20; mai s'allarga la cançó)
        self.assertEqual(_temps_acords(v)[-1], 15.0)
        self.assertAlmostEqual(float(v.acords[-1][0]), 15.0, places=6)
        v.close()


class TestSobreescriureSeccions(_copiar_enganxar___Base):
    def test_enganxa_seccions_retalla_al_final(self):
        v = _copiar_enganxar___visor()
        v.timeline.select_clip("section", 0)          # A 0-5 (span 5)
        v.timeline.copy_selection()
        v.timeline.set_position(18.0, emit=False)     # 18+5 = 23 > 20 → retall
        v.timeline.paste_at_cursor()
        self.assertAlmostEqual(float(v.seccions[-1][0]), 18.0, places=6)
        self.assertAlmostEqual(float(v.seccions[-1][1]), 20.0, places=6)
        self.assertEqual(v.seccions[-1][2], "A")
        v.close()

    def test_copia_nomes_acords_no_toca_seccions(self):
        v = _copiar_enganxar___visor()
        v.timeline.select_clip("chord", 0)
        v.timeline.copy_selection()
        sec_abans = [tuple(s) for s in v.seccions]
        v.timeline.set_position(6.0, emit=False)
        v.timeline.paste_at_cursor()
        self.assertEqual([tuple(s) for s in v.seccions], sec_abans,
                         "copiar només acords no ha de tocar l'estructura")
        v.close()

    def test_selecciona_el_bloc_enganxat(self):
        v = _copiar_enganxar___visor()
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


class TestSeleccioMixta(_copiar_enganxar___Base):
    def test_seleccio_mixta_enganxa_els_dos_carrils(self):
        v = _copiar_enganxar___visor()
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


class TestSeleccioMixtaNoDeixaForats(_copiar_enganxar___Base):
    def test_arranjaments_no_coincidents(self):
        """Selecció mixta amb clips que NO comencen alhora → sense forats."""
        v = _copiar_enganxar___visor()
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


class TestCasosBuits(_copiar_enganxar___Base):
    def test_sense_clipboard_no_fa_res(self):
        v = _copiar_enganxar___visor()
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


class TestAncoraDeMarca(_copiar_enganxar___Base):
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


class TestEnganxatALaVoraDelBloc(_copiar_enganxar___Base):
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
        # CAP marca a menys de 1 ms: era exactament la col·lisió que ho trencava
        for a, b in zip(v.acords, v.acords[1:]):
            self.assertGreaterEqual(float(b[0]) - float(a[0]), 0.001 - 1e-9)
        v.close()

    def test_rebuig_en_silenci_ja_no_existeix(self):
        """Un rebuig ha de sortir a pantalla (abans només anava al log)."""
        v = _visor_otis()
        avisos = []
        v.infoMissatge.connect(avisos.append)
        v._enganxa_seleccio({"chords": [(0.0, "X"), (0.0005, "Y")],
                             "chord_len": 1.0, "bloc_fi": 18.5}, 18.5)
        self.assertTrue(avisos, "el rebuig hauria d'avisar a pantalla")
        self.assertIn("Enganxat no fet", avisos[0])
        v.close()


def _copiar_enganxar_tearDownModule():
    try:
        import _qt_neteja
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_nudge.py
# ══════════════════════════════════════════════════════════════════════════
"""Nudge amb teclat: `←`/`→` mouen la frontera del clip seleccionat un pas de
graella. `Shift` = més fi; `Alt` = estira/encongeix (mou la vora dreta).

Una sola operació de desfer; només es mou UNA frontera → ordre i contigüitat
(regles d'or #1/#2) queden intactes.
"""


_nudge__ACORDS = "0.0,2.0,C\n2.0,4.5,Am\n4.5,7.0,F\n7.0,10.0,G\n10.0,20.0,C\n"
_nudge__SECCIONS = ("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
            "0.0,5.0,5.0,A,A,1.1,5.1\n"
            "5.0,10.0,5.0,B,B,5.1,10.1\n"
            "10.0,20.0,10.0,C,C,10.1,20.1\n")


def _nudge___visor():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "tema.wav")
    out = os.path.join(td, "AUTOCHORDS_tema")
    os.makedirs(out)
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * 20)
    ca = os.path.join(out, "acords.csv")
    sa = os.path.join(out, "estructura_ABC.csv")
    with open(ca, "w", encoding="utf-8") as f:
        f.write(_nudge__ACORDS)
    with open(sa, "w", encoding="utf-8") as f:
        f.write(_nudge__SECCIONS)
    v = visor_mod.Visor(wav, ca, sa, bpm=120, bpb=4, tempo_fix=True)
    v.td, v.sortida = td, out
    return v


def _key(key, mods=Qt.NoModifier):
    return QKeyEvent(QEvent.KeyPress, key, mods)


class _nudge___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])


class TestNudge(_nudge___Base):
    def test_acord_una_frontera_a_la_dreta(self):
        v = _nudge___visor()
        v.timeline.select_clip("chord", 1)
        pas = v.timeline._pas_nudge()
        t0 = float(v.acords[1][0])
        v.timeline.keyPressEvent(_key(Qt.Key_Right))
        self.assertAlmostEqual(float(v.acords[1][0]) - t0, pas, places=6)
        # cobertura/ordre intactes
        self.assertAlmostEqual(float(v.acords[0][0]), 0.0, places=6)
        v.close()

    def test_acord_una_frontera_a_l_esquerra(self):
        v = _nudge___visor()
        v.timeline.select_clip("chord", 2)          # F @ 4.5
        pas = v.timeline._pas_nudge()
        t0 = float(v.acords[2][0])
        v.timeline.keyPressEvent(_key(Qt.Key_Left))
        self.assertAlmostEqual(t0 - float(v.acords[2][0]), pas, places=6)
        v.close()

    def test_es_desfa_duna_sola_operacio(self):
        v = _nudge___visor()
        v.timeline.select_clip("chord", 1)
        t0 = float(v.acords[1][0])
        v.timeline.keyPressEvent(_key(Qt.Key_Right))
        self.assertEqual(len(v._undo_stack), 1)
        v.undo()
        self.assertAlmostEqual(float(v.acords[1][0]), t0, places=6)
        v.close()

    def test_alt_estira_la_vora_dreta(self):
        v = _nudge___visor()
        v.timeline.select_clip("chord", 1)          # Am @ 2 ; fi = 4.5 (inici de F)
        pas = v.timeline._pas_nudge()
        v.timeline.keyPressEvent(_key(Qt.Key_Right, Qt.AltModifier))
        self.assertAlmostEqual(float(v.acords[2][0]) - 4.5, pas, places=6)
        v.close()

    def test_seccio_nudge_la_frontera(self):
        v = _nudge___visor()
        v.timeline.select_clip("section", 1)        # B 5-10
        pas = v.timeline._pas_nudge()
        v.timeline.keyPressEvent(_key(Qt.Key_Right))
        # la frontera A/B es mou: B comença a 5+pas
        self.assertAlmostEqual(float(v.seccions[1][0]) - 5.0, pas, places=6)
        self.assertAlmostEqual(float(v.seccions[0][0]), 0.0, places=6)
        v.close()

    def test_nudge_seccio_primera_no_deixa_marca_penjada(self):
        """Nudgejar la 1a secció cap a l'esquerra no pot: no ha de deixar undo."""
        v = _nudge___visor()
        v.timeline.select_clip("section", 0)
        abans = [round(float(s[0]), 6) for s in v.seccions]
        v.timeline.keyPressEvent(_key(Qt.Key_Left))
        self.assertEqual([round(float(s[0]), 6) for s in v.seccions], abans)
        self.assertIsNone(getattr(v, "_undo_pending", None),
                          "no pot quedar una marca d'undo penjada")
        v.close()

    def test_estirar_ultim_acord_no_deixa_marca_penjada(self):
        v = _nudge___visor()
        v.timeline.select_clip("chord", len(v.acords) - 1)   # últim: no té fi
        abans = [round(float(a[0]), 6) for a in v.acords]
        v.timeline.keyPressEvent(_key(Qt.Key_Right, Qt.AltModifier))
        self.assertEqual([round(float(a[0]), 6) for a in v.acords], abans)
        self.assertIsNone(getattr(v, "_undo_pending", None))
        v.close()

    def test_tram_tempo_nudge_la_frontera(self):
        """← / → mouen la frontera del tram de BPM/compàs seleccionat (#11)."""
        v = _nudge___visor()
        v.aplica_tempo_trams([(0.0, 10.0, 120.0, 4, 4),
                              (10.0, 20.0, 90.0, 3, 4)])
        # El nudge de tempo mou COMPASSOS sencers: 4/4 a 120 BPM = 2 s.
        bar = 60.0 / 120.0 * 4
        v.timeline.select_clip("tempo", 1)
        v.timeline.keyPressEvent(_key(Qt.Key_Right))
        self.assertAlmostEqual(float(v.tempo_trams[1][0]) - 10.0, bar,
                               places=6)
        self.assertAlmostEqual(float(v.tempo_trams[0][0]), 0.0, places=6)
        # Alt+→ (estira) mou la frontera DRETA del tram
        v.timeline.keyPressEvent(_key(Qt.Key_Right, Qt.AltModifier))
        self.assertAlmostEqual(float(v.tempo_trams[1][1]), 20.0, places=6)
        v.close()

    def test_tram_tempo_edicio_es_desfeu(self):
        """Les edicions del mapa de BPM/compàs són desferibles (abans no!)."""
        v = _nudge___visor()
        v.aplica_tempo_trams([(0.0, 10.0, 120.0, 4, 4),
                              (10.0, 20.0, 90.0, 3, 4)])
        abans = [(round(float(t[0]), 6), round(float(t[1]), 6), t[2])
                 for t in v.tempo_trams]
        v.timeline.select_clip("tempo", 1)
        v.timeline.keyPressEvent(_key(Qt.Key_Right))
        self.assertNotEqual([round(float(t[0]), 6) for t in v.tempo_trams],
                            [a[0] for a in abans])
        v.undo()
        self.assertEqual(
            [(round(float(t[0]), 6), round(float(t[1]), 6), t[2])
             for t in v.tempo_trams], abans)
        v.close()

    def test_tram_tempo_extrems_son_immobils(self):
        """El 1r tram comença a la WAV i l'últim hi acaba: no s'hi pot nudgejar."""
        v = _nudge___visor()
        v.aplica_tempo_trams([(0.0, 10.0, 120.0, 4, 4),
                              (10.0, 20.0, 90.0, 3, 4)])
        abans = [(float(t[0]), float(t[1])) for t in v.tempo_trams]
        v.timeline.select_clip("tempo", 0)
        v.timeline.keyPressEvent(_key(Qt.Key_Left))           # 1r: no pot
        v.timeline.select_clip("tempo", 1)
        v.timeline.keyPressEvent(_key(Qt.Key_Right, Qt.AltModifier))
        self.assertEqual([(float(t[0]), float(t[1])) for t in v.tempo_trams],
                         abans)
        self.assertIsNone(getattr(v, "_undo_pending", None),
                          "no pot quedar una marca d'undo penjada")
        v.close()

    def test_sense_seleccio_no_canvia_res(self):
        v = _nudge___visor()
        abans = [round(float(a[0]), 6) for a in v.acords]
        v.timeline.keyPressEvent(_key(Qt.Key_Right))
        self.assertEqual([round(float(a[0]), 6) for a in v.acords], abans)
        v.close()


def _nudge_tearDownModule():
    try:
        import _qt_neteja
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_regla11_paritat.py
# ══════════════════════════════════════════════════════════════════════════
"""Regla d'or #11 — PARITAT d'edició i tracte visual (acords ↔ estructura).

`docs/REGLES_DE_LA_APP.md` §11: els clips d'**acords** i d'**estructura** han de
tenir **exactament les mateixes eines d'edició** i el **mateix tracte** al visor.
Aquest mòdul blinda la paritat:

- Backend: `pipeline.parteix_acord` / `fusiona_acords` (mirall de les de secció).
- Visor: `parteix_acord` / `fusiona_acord` / `fusiona_seccio`.
- Menús de llista: el d'acords i el de seccions presenten el MATEIX joc d'accions.
- Menú contextual del clip: «Parteix…» és disponible per a acords I seccions.
- Item visual: el `SectionItem` emet `dragStarted` (com el `ChordItem`).
"""


_regla11_paritat__DUR = 30.0
_regla11_paritat__ACORDS = [(0.0, "C", "0.0"), (10.0, "Am", "10.0"), (20.0, "F", "20.0")]
_regla11_paritat__SECCIONS = [(0.0, 10.0, "A", "A"), (10.0, 20.0, "B", "B"), (20.0, _regla11_paritat__DUR, "C", "C")]


def _regla11_paritat___escriu_wav(ruta, dur=_regla11_paritat__DUR):
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * int(44100 * dur))


def _regla11_paritat___visor():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "tema.wav")
    _regla11_paritat___escriu_wav(wav)
    sortida = pipeline.carpeta_sortida(wav)
    os.makedirs(sortida, exist_ok=True)
    ca = os.path.join(sortida, "acords.csv")
    with open(ca, "w", encoding="utf-8") as f:
        for t, nom, _src in _regla11_paritat__ACORDS:
            f.write(f"{t},{t + 1},{nom}\n")
    sa = os.path.join(sortida, "estructura_ABC.csv")
    with open(sa, "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n")
        for ini, fi, L, fam in _regla11_paritat__SECCIONS:
            f.write(f"{ini},{fi},{fi - ini},{L},{fam},1,1\n")
    v = visor_mod.Visor(wav, ca, sa, 120.0, 4, True)
    v.td, v.sortida, v.abc_csv = td, sortida, sa
    return v


class _Fila:
    """Stub per a `QListWidget.indexAt(...).row()` als tests de menú."""
    def __init__(self, r):
        self._r = r

    def row(self):
        return self._r


class _EvRatoli:
    """Esdeveniment de ratolí mínim per a `mousePressEvent` (sense Qt real)."""
    def __init__(self, x, boto=Qt.LeftButton):
        self._x, self._boto, self.acceptat = x, boto, False

    def button(self):
        return self._boto

    def pos(self):
        return QPointF(self._x, 0.0)

    def accept(self):
        self.acceptat = True


class _regla11_paritat___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])


# ── Backend ──────────────────────────────────────────────────────────────────
class TestBackendParitat(_regla11_paritat___Base):
    def test_parteix_acord_insereix_un_clip_amb_el_mateix_nom(self):
        nou = pipeline.parteix_acord(list(_regla11_paritat__ACORDS), 0, 4.0)
        self.assertEqual([(a[0], a[1]) for a in nou],
                         [(0.0, "C"), (4.0, "C"), (10.0, "Am"), (20.0, "F")])

    def test_parteix_acord_amb_nom_nou(self):
        nou = pipeline.parteix_acord(list(_regla11_paritat__ACORDS), 1, 15.0, "G")
        self.assertEqual(nou[1][1], "Am")
        self.assertEqual(nou[2][1], "G")
        self.assertAlmostEqual(nou[2][0], 15.0)

    def test_parteix_acord_fora_de_rang_peta(self):
        with self.assertRaises(ValueError):
            pipeline.parteix_acord(list(_regla11_paritat__ACORDS), 0, 12.0)
        with self.assertRaises(ValueError):
            # Sense `durada` no se sap on acaba l'últim clip (fi=0) → fora de rang.
            pipeline.parteix_acord(list(_regla11_paritat__ACORDS), 2, 25.0)

    def test_parteix_acord_l_ultim_amb_durada_es_parteix(self):
        """Paritat #11: l'últim acord es parteix igual que l'última secció."""
        nou = pipeline.parteix_acord(list(_regla11_paritat__ACORDS), 2, 25.0, durada=_regla11_paritat__DUR)
        self.assertEqual([(a[0], a[1]) for a in nou],
                         [(0.0, "C"), (10.0, "Am"), (20.0, "F"), (25.0, "F")])

    def test_fusiona_acords_esquena_l_harmonia_de_l_esquerre(self):
        # Fusionar 0 amb el següent → queda el "C" (esquerre) estès.
        self.assertEqual([(a[0], a[1]) for a in
                          pipeline.fusiona_acords(list(_regla11_paritat__ACORDS), 0, "seguent")],
                         [(0.0, "C"), (20.0, "F")])
        # Fusionar 1 amb l'anterior → queda el "C".
        self.assertEqual([(a[0], a[1]) for a in
                          pipeline.fusiona_acords(list(_regla11_paritat__ACORDS), 1, "anterior")],
                         [(0.0, "C"), (20.0, "F")])

    def test_mirall_de_les_seccions(self):
        """Les operacions d'acord i de secció han d'existir totes dues."""
        for nom in ("parteix_acord", "fusiona_acords",
                    "parteix_seccio", "fusiona_seccions"):
            self.assertTrue(callable(getattr(pipeline, nom, None)),
                            f"falta pipeline.{nom} (regla #11)")


# ── Visor ────────────────────────────────────────────────────────────────────
class TestVisorParitat(_regla11_paritat___Base):
    def test_parteix_acord_mante_cobertura_i_es_desfà(self):
        v = _regla11_paritat___visor()
        n0 = len(v.acords)
        self.assertEqual(v.parteix_acord(0, 4.0), 1)
        self.assertEqual(n0 + 1, len(v.acords))
        self.assertEqual(v.acords[0][2][0], "C")
        self.assertEqual(v.acords[1][2][0], "C")
        self.assertAlmostEqual(float(v.acords[1][0]), 4.0, places=6)
        # cobertura (#4): els acords segueixen cobrint tota la WAV de 0 a _regla11_paritat__DUR
        self.assertAlmostEqual(float(v.acords[0][0]), 0.0, places=6)
        v.undo()
        self.assertEqual(len(v.acords), n0)

    def test_visor_parteix_l_ultim_acord(self):
        """L'últim acord (que acaba a la WAV) TAMBÉ es pot partir (#11)."""
        v = _regla11_paritat___visor()
        n0 = len(v.acords)
        self.assertEqual(v.parteix_acord(n0 - 1, 25.0), n0)
        self.assertEqual(len(v.acords), n0 + 1)
        self.assertAlmostEqual(float(v.acords[-1].ini), 25.0, places=6)
        self.assertAlmostEqual(float(v.acords[-1].fi), _regla11_paritat__DUR, places=6)
        v.undo()
        self.assertEqual(len(v.acords), n0)

    def test_la_pista_de_tempo_entra_a_la_seleccio(self):
        """Els trams de BPM/compàs es seleccionen com la resta de clips (#11)."""
        v = _regla11_paritat___visor()
        v.aplica_tempo_trams([(0.0, 6.0, 120.0, 4, 4), (6.0, _regla11_paritat__DUR, 90.0, 3, 4)])
        tl = v.timeline
        trams = tl._trams_tempo()
        self.assertEqual([(t[0], t[1]) for t in trams],
                         [(0.0, 6.0), (6.0, _regla11_paritat__DUR)])
        # marquee (solapament): un marc de 10 a 12 cau dins del 2n tram
        keys = tl.keys_dins_marc(10.0, 12.0, chords=False, sections=False)
        self.assertEqual(keys, {("tempo", 1)})
        # un marc dels 2 trams els agafa tots dos
        keys = tl.keys_dins_marc(0.0, _regla11_paritat__DUR, chords=False, sections=False)
        self.assertEqual(keys, {("tempo", 0), ("tempo", 1)})
        # rang (Shift+clic): es queda al carril dels trams
        tl.select_clip("tempo", 0)
        tl.extend_selection("tempo", 1)
        self.assertEqual(tl.selected_keys(), {("tempo", 0), ("tempo", 1)})
        # Ctrl+clic = toggle (afegeix/treu)
        tl.toggle_selection("tempo", 0)
        self.assertEqual(tl.selected_keys(), {("tempo", 1)})
        # ... i el Ctrl+clic sobre un ACORD no arrossega cap tram
        tl.select_clip("chord", 0)
        tl.extend_selection("chord", 1)
        self.assertFalse([k for k in tl.selected_keys() if k[0] == "tempo"])
        # El RESSALTAT VISUAL de la pista ha de seguir la seleccio (prova de
        # mutacio 18-10-2026: sense aixo, trencar `_sync_selection_visual` no
        # feia petar cap test).
        tl.select_clip("tempo", 1)
        self.assertEqual(tl._tempo_lane._sel, 1)
        tl.clear_selection()
        self.assertEqual(tl._tempo_lane._sel, -1)

    def test_porta_retalls_dels_trams_de_tempo(self):
        """Copiar/enganxar, duplicar i retallar trams de BPM/compàs (#11)."""
        v = _regla11_paritat___visor()
        v.aplica_tempo_trams([(0.0, 6.0, 120.0, 4, 4), (6.0, _regla11_paritat__DUR, 90.0, 3, 4)])
        tl = v.timeline

        def est():
            return [(round(float(t[0]), 2), round(float(t[1]), 2), t[2])
                    for t in v.tempo_trams]

        tl.select_clip("tempo", 0)
        tl.copy_selection()
        tl.set_position(12.0, snap=False)
        tl.paste_at_cursor()
        self.assertEqual(est(), [(0.0, 6.0, 120.0), (6.0, 12.0, 90.0),
                                 (12.0, 18.0, 120.0), (18.0, _regla11_paritat__DUR, 90.0)])
        v.undo()
        self.assertEqual(est(), [(0.0, 6.0, 120.0), (6.0, _regla11_paritat__DUR, 90.0)])
        # Ctrl+D: la còpia va DESPRÉS del bloc i n'hereta el BPM/compàs
        v._duplica_seleccio([("tempo", 0)])
        self.assertEqual([(t[0], t[2]) for t in est()],
                         [(0.0, 120.0), (6.0, 120.0), (12.0, 90.0)])
        v.undo()
        # Retallar: el tram esborrat deixa que el veí ocupi el seu espai
        tl.select_clip("tempo", 0)
        tl.cut_selection()
        self.assertEqual(est(), [(0.0, _regla11_paritat__DUR, 90.0)])
        v.undo()
        self.assertEqual(est(), [(0.0, 6.0, 120.0), (6.0, _regla11_paritat__DUR, 90.0)])

    def test_operacions_mixtes_les_tres_families(self):
        """Una sola operacio sobre les TRES families alhora (R11 cami a cami).

        Seleccionar un acord, una seccio i un tram i esborrar-los ha de ser UNA
        operacio de desfer; una copia mixta tambe s'enganxa tota de cop i es
        reverteix amb un sol Ctrl+Z (i es torna a fer amb Ctrl+Y).
        """
        v = _regla11_paritat___visor()
        v.aplica_tempo_trams([(0.0, 10.0, 120.0, 4, 4),
                              (10.0, _regla11_paritat__DUR, 90.0, 3, 4)])

        def estat():
            return ([c.payload[0] for c in v.acords],
                    [s[2] for s in v.seccions],
                    [len(v.tempo_trams or [])])

        base = estat()
        v._elimina_seleccio([("chord", 0), ("section", 1), ("tempo", 1)])
        self.assertEqual(estat(), (["N", "Am", "F"], ["A", "C"], [1]))
        v.undo()
        self.assertEqual(estat(), base)
        v.redo()
        self.assertEqual(estat(), (["N", "Am", "F"], ["A", "C"], [1]))
        v.undo()
        self.assertEqual(estat(), base)
        # copia mixta (acord + tram) i enganxa: tot de cop, un sol desfer
        tl = v.timeline
        tl.select_multi({("chord", 0), ("tempo", 0)})
        tl.copy_selection()
        # El destí del bloc de tempo ha de caure en una línia de compàs (12 s).
        tl.set_position(12.0, snap=False)
        tl.paste_at_cursor()
        self.assertEqual([c.payload[0] for c in v.acords],
                         ["C", "Am", "C", "F"])
        self.assertEqual([t[2] for t in v.tempo_trams],
                         [120.0, 90.0, 120.0, 90.0])
        v.undo()
        self.assertEqual(estat(), base)

    def test_la_seleccio_del_loop_inclou_els_trams(self):
        """El LOOP selecciona tambe els trams de BPM/compàs (es poden copiar)."""
        v = _regla11_paritat___visor()
        v.aplica_tempo_trams([(0.0, 6.0, 120.0, 4, 4), (6.0, _regla11_paritat__DUR, 90.0, 3, 4)])
        v.loop_a, v.loop_b = 2.0, 8.0
        n = v.selecciona_bloc_del_loop()
        self.assertTrue(n)
        self.assertIn(("tempo", 1), v.timeline.selected_keys())

    def test_partir_per_la_meitat_acord_i_seccio(self):
        """«Partir per la meitat» = dues meitats exactes, als DOS tipus (#11)."""
        v = _regla11_paritat___visor()
        self.assertEqual(v.parteix_per_la_meitat("section", 0), 1)
        self.assertAlmostEqual(float(v.seccions[0][1]), 5.0, places=6)
        self.assertAlmostEqual(float(v.seccions[1][0]), 5.0, places=6)
        self.assertAlmostEqual(float(v.seccions[1][1]), 10.0, places=6)
        self.assertEqual(v.parteix_per_la_meitat("chord", 0), 1)
        self.assertAlmostEqual(float(v.acords[0].fi), 5.0, places=6)
        self.assertAlmostEqual(float(v.acords[1].ini), 5.0, places=6)
        self.assertEqual(v.acords[1].payload[0], "C")
        # tambe funciona amb l'ULTIM clip (acaba a la WAV)
        n = len(v.acords)
        self.assertEqual(v.parteix_per_la_meitat("chord", n - 1), n)
        self.assertAlmostEqual(float(v.acords[-1].fi), _regla11_paritat__DUR, places=6)

    def test_ultim_acord_fi_editable_crea_clip_de_cua(self):
        """Paritat #11: l'últim clip també s'encongeix per la vora dreta.

        Abans el timeline ho bloquejava (`pass`): la fi de l'últim acord no
        s'editava mai i no hi havia manera de deixar un tros de cua.
        """
        v = _regla11_paritat___visor()
        n0 = len(v.acords)
        v.timeline._on_chord_end_changed(n0 - 1, _regla11_paritat__DUR - 2.0)
        cl = list(v.timeline._acords)
        self.assertEqual(len(cl), n0 + 1)
        self.assertAlmostEqual(float(cl[-1].ini), _regla11_paritat__DUR - 2.0, places=6)
        self.assertAlmostEqual(float(cl[-1].fi), _regla11_paritat__DUR, places=6)
        self.assertEqual(cl[-1].payload[0], pipeline.SENSE_ACORD)

    def test_fusiona_acord(self):
        v = _regla11_paritat___visor()
        n0 = len(v.acords)
        self.assertTrue(v.fusiona_acord(0, "seguent"))
        self.assertEqual(len(v.acords), n0 - 1)
        self.assertEqual(v.acords[0][2][0], "C")
        v.undo()
        self.assertEqual(len(v.acords), n0)

    def test_visor_te_les_mateixes_operacions_per_a_tots_dos(self):
        v = _regla11_paritat___visor()
        for nom in ("parteix_acord", "_parteix_acord_dialog", "fusiona_acord",
                    "parteix_seccio", "_parteix_seccio_dialog", "fusiona_seccio"):
            self.assertTrue(callable(getattr(v, nom, None)),
                            f"falta Visor.{nom} (regla #11)")


# ── Menús ────────────────────────────────────────────────────────────────────
def _captura_menu(fn, *args):
    capt = {}
    orig = QMenu.exec_

    def fake(self, pos, *rest):
        capt["accions"] = [(a.text(), a.isEnabled())
                           for a in self.actions() if not a.isSeparator()]
        return None
    QMenu.exec_ = fake
    try:
        fn(*args)
    finally:
        QMenu.exec_ = orig
    return capt.get("accions", [])


def _claus_menu(fn, *args):
    """Les CLAUS de les accions (`QAction.data()`) + si estan actives.

    Serveix per comparar **l'operació** entre carrils: la redacció sí que canvia
    («Afegeix acord aquí» / «Afegeix un canvi aquí»), l'operació NO.
    """
    capt = {}
    orig = QMenu.exec_

    def fake(self, pos, *rest):
        acts = [a for a in self.actions() if not a.isSeparator()]
        capt["claus"] = [a.data() for a in acts]
        capt["actiu"] = [a.isEnabled() for a in acts]
        return None
    QMenu.exec_ = fake
    try:
        fn(*args)
    finally:
        QMenu.exec_ = orig
    return capt.get("claus", []), capt.get("actiu", [])


def _tria_menu(fn, text, *args):
    """Crida `fn` fent veure que l'usuari tria l'acció que conté `text`."""
    trobat = {"ok": False}

    def fake(self, pos, *rest):
        for a in self.actions():
            if not a.isSeparator() and text.lower() in a.text().lower():
                trobat["ok"] = True
                return a
        return None
    orig = QMenu.exec_
    QMenu.exec_ = fake
    try:
        fn(*args)
    finally:
        QMenu.exec_ = orig
    return trobat["ok"]


class TestMenusParitat(_regla11_paritat___Base):
    def _amb_fila(self, fn):
        orig = QListWidget.indexAt
        QListWidget.indexAt = lambda self, pos: _Fila(0)
        try:
            return _captura_menu(fn, QPoint(1, 1))
        finally:
            QListWidget.indexAt = orig

    def test_menus_de_llista_mateix_joc_d_accions(self):
        v = _regla11_paritat___visor()
        ac = self._amb_fila(v._menu_acord)
        se = self._amb_fila(v._menu_seccio)
        self.assertEqual(len(ac), len(se),
                         f"jocs d'accions diferents: {ac} vs {se}")
        # 13 accions = la definició ÚNICA del menú contextual (regla #11),
        # compartida amb el timeline (abans la llista en tenia 7 i el timeline 9).
        # 13a: «Parteix a la selecció A–B» (2026-10-20).
        self.assertEqual(len(ac), 13, f"joc inesperat: {ac}")
        # Mateixa estructura (activació) i mateixa paraula de tipus a cada posició.
        self.assertEqual([e for _t, e in ac], [e for _t, e in se])
        self.assertIn("acord", ac[0][0].lower())
        self.assertIn("secció", se[0][0].lower())
        self.assertIn("acord", ac[3][0].lower())
        self.assertIn("secció", se[3][0].lower())

    def test_les_cinc_superficies_tenen_el_mateix_menu(self):
        """③ BPM/compàs + ④ estructura + ⑤ acords, al TIMELINE i a les LLISTES.

        Regla d'or #11: **una sola definició** de menú (`_menu_contextual`) per a
        totes les superfícies → mateixa OPERACIÓ, mateix ordre i mateixa
        activació. La redacció sí que pot canviar («Afegeix acord aquí» vs
        «Afegeix un canvi aquí»), per això es comparen les **claus**.
        """
        v = _regla11_paritat___visor()
        v.aplica_tempo_trams([(0.0, 10.0, 120.0, 4, 4),
                              (10.0, _regla11_paritat__DUR, 90.0, 3, 4)])
        orig = QListWidget.indexAt
        QListWidget.indexAt = lambda self, pos: _Fila(0)
        try:
            jocs = {
                "TL acords": _claus_menu(v._on_clip_context_menu, "chord", 0,
                                         QPoint(0, 0), 3.0),
                "TL estructura": _claus_menu(v._on_clip_context_menu, "section",
                                             0, QPoint(0, 0), 3.0),
                "TL BPM": _claus_menu(v._on_tempo_menu, 0, 3.0),
                "LLISTA acords": _claus_menu(v._menu_acord, QPoint(1, 1)),
                "LLISTA estructura": _claus_menu(v._menu_seccio, QPoint(1, 1)),
            }
        finally:
            QListWidget.indexAt = orig
        # Accions EXCLUSIVES del carril ③ (correcció mètrica discreta, §4.C del
        # flux de tempo variable): no tenen sentit als clips d'acords/seccions.
        extres_tercera = {"compas_mes1", "compas_menys1", "compas_x2",
                          "compas_div2"}
        base_claus, base_actiu = jocs["TL acords"]
        self.assertEqual(base_claus, [
            "afegeix", "duplica", "elimina", "reanomena", "parteix", "meitat",
            "parteix_loop", "fusiona_anterior", "fusiona_seguent", "retalla", "copia", "enganxa",
            "loop_seleccio",
        ])
        for nom, (claus, actiu) in jocs.items():
            comu = [c for c in claus if c not in extres_tercera]
            self.assertEqual(comu, base_claus,
                             f"«{nom}» no té el mateix joc/ordre d'operacions")
            if nom == "TL BPM":
                # ③ sí que porta els 4 extres, en bloc i darrere de «fusiona».
                self.assertEqual([c for c in claus if c in extres_tercera],
                                 ["compas_mes1", "compas_menys1",
                                  "compas_x2", "compas_div2"])
                base_actiu = [e for c, e in zip(claus, actiu)
                              if c not in extres_tercera]
            else:
                self.assertFalse([c for c in claus if c in extres_tercera],
                                 f"«{nom}» no pot tindre les accions de compassos")
            self.assertEqual([e for c, e in zip(claus, actiu)
                              if c not in extres_tercera], base_actiu,
                             f"«{nom}» té una activació diferent")

    def test_l_operacio_que_nomes_era_a_les_llistes_ara_hi_es_a_tot_arreu(self):
        """«Fusionar amb anterior/seguint» existia només a les llistes."""
        v = _regla11_paritat___visor()
        v.aplica_tempo_trams([(0.0, 10.0, 120.0, 4, 4),
                              (10.0, _regla11_paritat__DUR, 90.0, 3, 4)])
        for etq, args in (("TL acords", ("chord", 1, QPoint(0, 0), 3.0)),
                          ("TL estructura", ("section", 1, QPoint(0, 0), 3.0)),
                          ("TL BPM", (1, 3.0))):
            fn = v._on_tempo_menu if etq == "TL BPM" else v._on_clip_context_menu
            claus, actiu = _claus_menu(fn, *args)
            self.assertIn("fusiona_anterior", claus)
            self.assertIn("fusiona_seguent", claus)
            d = dict(zip(claus, actiu))
            self.assertTrue(d["fusiona_anterior"],
                            f"«{etq}»: amb un clip anterior, ha d'estar activa")

    def test_els_menus_tenen_les_tretze_accions_esperades(self):
        """La llista blanca de les 13 accions + les 4 de compassos del ③.

        Canviar-la és una decisió (regla #11).
        """
        v = _regla11_paritat___visor()
        v.aplica_tempo_trams([(0.0, 10.0, 120.0, 4, 4),
                              (10.0, _regla11_paritat__DUR, 90.0, 3, 4)])
        joc = [t for t, _e in _captura_menu(v._on_tempo_menu, 0, 3.0)]
        self.assertEqual(joc, [
            "Afegeix un canvi aquí",
            "Duplica", "Elimina",
            "Reanomena (BPM/compàs)…",
            "Parteix aquest tros aquí", "Partir per la meitat",
            "Parteix a la selecció A–B",
            "Fusionar amb anterior", "Fusionar amb següent",
            "Afegir 1 compàs (+1)", "Restar 1 compàs (−1)",
            "Doblar compassos (×2)", "Dividir compassos (÷2)",
            "Retalla", "Copia", "Enganxa", "Loop a la selecció",
        ])

    def test_menu_contextual_parteix_per_a_tots_dos(self):
        v = _regla11_paritat___visor()
        ac = _captura_menu(v._on_clip_context_menu, "chord", 0, QPoint(0, 0))
        se = _captura_menu(v._on_clip_context_menu, "section", 0, QPoint(0, 0))
        self.assertTrue(dict(ac).get("Parteix l'acord…"),
                        f"hauria d'estar actiu sobre un acord: {ac}")
        self.assertTrue(dict(se).get("Parteix la secció…"),
                        f"hauria d'estar actiu sobre una secció: {se}")

    # ── ③ BPM/compàs: paritat amb ④ i ⑤ (report de l'operador, 19-10-2026) ──

    def _tres_menus(self):
        """Els tres menús contextuals amb un estat equivalent (idx 0 actiu)."""
        v = _regla11_paritat___visor()
        v.aplica_tempo_trams([(0.0, 10.0, 120.0, 4, 4),
                              (10.0, _regla11_paritat__DUR, 90.0, 3, 4)])
        ac = _captura_menu(v._on_clip_context_menu, "chord", 0,
                           QPoint(0, 0), 3.0)
        se = _captura_menu(v._on_clip_context_menu, "section", 0,
                           QPoint(0, 0), 3.0)
        tp = _captura_menu(v._on_tempo_menu, 0, 3.0)
        return v, ac, se, tp

    def test_els_tres_menus_tenen_el_mateix_joc(self):
        """La pista ③ obre EL MATEIX joc d'accions que ④ i ⑤ (regla #11),
        més les 4 accions de COMPASSOS que només tenen sentit al tempo."""
        _v, ac, se, tp = self._tres_menus()
        extres = {"Afegir 1 compàs (+1)", "Restar 1 compàs (−1)",
                  "Doblar compassos (×2)", "Dividir compassos (÷2)"}
        tp_comu = [x for x in tp if x[0] not in extres]
        self.assertEqual(len(ac), len(se))
        self.assertEqual(len(ac), len(tp) - 4,
                         f"③ ha de tindre 4 accions més (compassos):\n"
                         f"④/⑤={ac}\n③={tp}")
        self.assertEqual({x[0] for x in tp if x[0] in extres}, extres)
        self.assertEqual([e for _t, e in ac], [e for _t, e in se])
        self.assertEqual([e for _t, e in ac], [e for _t, e in tp_comu],
                         f"activació diferent:\n④/⑤={ac}\n③={tp}")

    def test_l_afegeix_es_el_primer_a_les_tres(self):
        """Cada pista té el seu «Afegeix … aquí» al capdamunt i actiu."""
        _v, ac, se, tp = self._tres_menus()
        self.assertEqual(ac[0][0], "Afegeix acord aquí")
        self.assertEqual(se[0][0], "Afegeix secció aquí")
        self.assertEqual(tp[0][0], "Afegeix un canvi aquí")
        for joc in (ac, se, tp):
            self.assertTrue(joc[0][1], f"l'afegeix ha d'estar actiu: {joc}")

    def test_menu_tempo_afegeix_un_canvi(self):
        v, _ac, _se, _tp = self._tres_menus()
        self.assertTrue(
            _tria_menu(v._on_tempo_menu, "Afegeix un canvi", 0, 7.0))
        # El tall s'imanta a la línia de compàs més pròxima (6 s: 0, 2, 4, 6, 8…).
        self.assertEqual([(round(float(t[0]), 2), round(float(t[1]), 2))
                          for t in v.tempo_trams],
                         [(0.0, 6.0), (6.0, 10.0), (10.0, _regla11_paritat__DUR)])
        # la frontera nova HERETA el tempo/compàs del tros on cau
        self.assertEqual(v.tempo_trams[1][2:4], (120.0, 4))
        v.undo()
        self.assertEqual(len(v.tempo_trams), 2)

    def test_menu_tempo_parteix_per_la_meitat(self):
        v, _ac, _se, _tp = self._tres_menus()
        self.assertTrue(
            _tria_menu(v._on_tempo_menu, "Partir per la meitat", 0, 3.0))
        # El centre (5 s) s'imanta a la línia de compàs més pròxima (4 s).
        self.assertEqual([(round(float(t[0]), 2), round(float(t[1]), 2), t[2])
                          for t in v.tempo_trams],
                         [(0.0, 4.0, 120.0), (4.0, 10.0, 120.0),
                          (10.0, _regla11_paritat__DUR, 90.0)])
        v.undo()
        self.assertEqual(len(v.tempo_trams), 2)

    def test_menu_tempo_duplica(self):
        v, _ac, _se, _tp = self._tres_menus()
        self.assertTrue(_tria_menu(v._on_tempo_menu, "Duplica", 0, 3.0))
        self.assertEqual([t[2] for t in v.tempo_trams], [120.0, 120.0, 90.0])
        v.undo()
        self.assertEqual(len(v.tempo_trams), 2)

    def test_menu_tempo_copia_i_enganxa(self):
        v, _ac, _se, _tp = self._tres_menus()
        self.assertTrue(_tria_menu(v._on_tempo_menu, "Copia", 0, 3.0))
        self.assertTrue(v.timeline.has_clipboard())
        # El destí ha de caure en una línia de compàs del mapa (16 s: 10, 12,
        # 14, 16…). El bloc [0,10]=120 s'enganxa sobre [16,26].
        v.timeline.set_position(16.0, snap=False)
        _tria_menu(v._on_tempo_menu, "Enganxa", 0, 3.0)
        self.assertEqual([(round(float(t[0]), 2), round(float(t[1]), 2), t[2])
                          for t in v.tempo_trams],
                         [(0.0, 10.0, 120.0), (10.0, 16.0, 90.0),
                          (16.0, 26.0, 120.0),
                          (26.0, _regla11_paritat__DUR, 90.0)])

    def test_menu_acord_afegeix_a_la_posicio_del_clic(self):
        """«Afegeix acord aquí» cau a l'instant del CLIC, no al cursor."""
        v, _ac, _se, _tp = self._tres_menus()
        n0 = len(v.acords)
        with patch.object(QInputDialog, "getText", return_value=("G", True)):
            self.assertTrue(
                _tria_menu(v._on_clip_context_menu, "Afegeix acord",
                           "chord", 0, QPoint(0, 0), 3.0))
        self.assertEqual(len(v.acords), n0 + 1)
        self.assertAlmostEqual(float(v.acords[1].ini), 3.0, places=6)
        self.assertEqual(v.acords[1].payload[0], "G")
        v.undo()
        self.assertEqual(len(v.acords), n0)

    def test_menu_seccio_afegeix_a_la_posicio_del_clic(self):
        """AFEGIR secció = PARTIR la que conté el punt (model saturat).

        La versió anterior afegia un tros de 2 s que solapava → l'add petava
        SEMPRE (llista i timeline). Ara parteix, com diu `parteix_seccio`.
        """
        v, _ac, _se, _tp = self._tres_menus()
        n0 = len(v.seccions)
        with patch.object(QInputDialog, "getText",
                          side_effect=[("B2", True), ("B2", True)]):
            self.assertTrue(
                _tria_menu(v._on_clip_context_menu, "Afegeix secció",
                           "section", 0, QPoint(0, 0), 12.0))
        self.assertEqual(len(v.seccions), n0 + 1)
        self.assertEqual([round(float(s[1]), 2) for s in v.seccions][:3],
                         [10.0, 12.0, 20.0])
        self.assertEqual(v.seccions[2][2], "B2")
        v.undo()
        self.assertEqual(len(v.seccions), n0)

    def test_llista_afegeix_seccio_tambe_parteix(self):
        """El «Afegeix secció aquí» de la LLISTA tenia el mateix bug."""
        v = _regla11_paritat___visor()
        orig = QListWidget.indexAt
        QListWidget.indexAt = lambda self, pos: _Fila(0)
        try:
            v.pos = 12.0
            with patch.object(QInputDialog, "getText",
                              side_effect=[("Z", True), ("Z", True)]):
                self.assertTrue(_tria_menu(v._menu_seccio,
                                           "Afegeix secció", QPoint(1, 1)))
        finally:
            QListWidget.indexAt = orig
        self.assertIn("Z", [s[2] for s in v.seccions])


class TestMenuPrincipalParitat(_regla11_paritat___Base):
    """El menú principal ha de tindre les MATEIXES operacions a les 3 pistes.

    Era l'última superfície amb forat: hi havia «Afegeix acord…» i «Afegeix
    secció…» (i els dos «Parteix … al cursor…»), però **res** per a ③.
    """

    def _finestra(self):
        import tempfile
        from app import config
        from app import main as app_main
        td = tempfile.mkdtemp()
        p = patch.object(config, "DADES_DIR", td)
        p.start()
        self.addCleanup(p.stop)
        f = app_main.Finestra()
        self.addCleanup(self._tanca, f)
        return f

    @staticmethod
    def _tanca(f):
        import _qt_neteja
        f.dirty = False
        _qt_neteja.tanca_i_destrueix(f)

    def _menu_edita(self, f):
        for a in f.menuBar().actions():
            if "edita" in a.text().replace("&", "").lower():
                return a.menu()
        return None

    def test_les_tres_pistes_tenen_afegeix_i_parteix(self):
        f = self._finestra()
        m = self._menu_edita(f)
        self.assertIsNotNone(m, "no trobo el menu Edita")
        textos = [a.text() for a in m.actions()]
        for esperat in ("Afegeix acord…", "Afegeix secció…",
                        "Afegeix tram de tempo/compàs…",
                        "Parteix l'acord al cursor…",
                        "Parteix la secció al cursor…",
                        "Parteix el tram al cursor…"):
            self.assertIn(esperat, textos,
                          f"falta «{esperat}» al menu Edita: {textos}")

    def test_afegeix_i_parteix_tram_funcionen(self):
        """I fan la feina (no només hi són)."""
        f = self._finestra()
        v = _regla11_paritat___visor()
        f.visor_ref = v
        n0 = len(v.tempo_trams or [])
        v.pos = 12.0
        f._afegeix_tram_ui()
        self.assertEqual(len(v.tempo_trams), n0 + 1,
                         "«Afegeix tram» ha d'obrir una frontera nova")
        v.pos = 14.0
        n1 = len(v.tempo_trams)
        f._parteix_tram_ui()
        self.assertEqual(len(v.tempo_trams), n1 + 1,
                         "«Parteix el tram» ha de partir-lo pel cursor")


# ── Tracte visual ────────────────────────────────────────────────────────────
class TestTracteVisual(_regla11_paritat___Base):
    def test_sectionitem_emet_dragstarted(self):
        it = timeline_items.SectionItem(0, 0.0, 2.0, "A", "A",
                                        pps=10.0, x_offset=0.0,
                                        lane_y=0.0, lane_h=20.0)
        got = []
        it.dragStarted.connect(lambda: got.append(1))
        x = (it._x_left() + it._x_right()) / 2.0   # cos (ZONE_BODY)
        it.mousePressEvent(_EvRatoli(x))
        self.assertTrue(got, "SectionItem ha d'emetre dragStarted (paritat #11)")

    def test_chorditem_emet_dragstarted(self):
        it = timeline_items.ChordItem(0, 0.0, "C", 2.0,
                                      pps=10.0, x_offset=0.0,
                                      lane_y=0.0, lane_h=20.0)
        got = []
        it.dragStarted.connect(lambda: got.append(1))
        x = (it._x_left() + it._x_right()) / 2.0
        it.mousePressEvent(_EvRatoli(x))
        self.assertTrue(got)


def _regla11_paritat_tearDownModule():
    # Neteja ORDENADA dels objectes Qt del mòdul (evita destrucció pel GC en un
    # test posterior -> access violation intermitent). Vegeu tests/_qt_neteja.py.
    try:
        import _qt_neteja
    except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_rename_sanejat.py
# ══════════════════════════════════════════════════════════════════════════
"""Regressió: el sanejat del nom d'acord (tots els camins) i el símbol musical.

`visor._afegeix_acord` ja netejava el nom, però el rename —pel MCP
(`ac_rename_chord`) i per l'editor de la GUI— hi passava el text CRU.

CANVI DE CRITERI (2026-10-15): el xifrat és **notació musical** i es conserva
tal qual (`/` per a l'acord amb baix, `-` de menor, `#`, `b`…). Només es
netejen caràcters de control i espais sobrers. La seguretat per als noms de
FITXER la garanteix `pipeline.safe_filename`, que l'export aplica pel seu
compte (`A7/G` → `A7_G.wav`). Abans el sanejat del MODEL també tocava `/`, i
això impedia escriure acords amb baix.
"""


_rename_sanejat__DUR = 40.0
BRUT = "  A7/G  "        # espais sobrers → es netegen
NET = "A7/G"             # però el SÍMBOL es conserva (baix amb `/` inclòs)


def _rename_sanejat___visor():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "tema.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * int(44100 * _rename_sanejat__DUR))
    sortida = pipeline.carpeta_sortida(wav)
    os.makedirs(sortida, exist_ok=True)
    ca = os.path.join(sortida, "acords.csv")
    with open(ca, "w", encoding="utf-8") as f:
        f.write("0.0,4.0,C\n4.0,15.0,Am\n")
    sa = os.path.join(sortida, "estructura_ABC.csv")
    with open(sa, "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n")
        f.write(f"0.00,{_rename_sanejat__DUR},{_rename_sanejat__DUR},A,A,1,1\n")
    v = visor_mod.Visor(wav, ca, sa, 120.0, 4, True)
    v.td, v.sortida = td, sortida
    return v


def _csv_acords(v):
    with open(v.csv_acords, encoding="utf-8") as f:
        return [(float(r[0]), r[2]) for r in csv.reader(f) if r]


class _rename_sanejat___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])


class _FinestraFalsa:
    def __init__(self, visor):
        self.visor_ref = visor
        self.sortida = "/tmp/out"

    def windowTitle(self):
        return "Auto Chords — prova"


class TestSanejatCanonic(_rename_sanejat___Base):
    def test_forma_canonica(self):
        """Tots els camins desen en la MATEIXA notació canònica d'acord.

        Menor `-`, major sense marca, `Maj7`, `-7`, `-7b5`… (`app/xifrat.py`).
        """
        for brut, net in [("C", "C"), ("C#m7", "C#-7"), ("N", "N"),
                          ("Am/G", "A-/G"), ("A-7/G", "A-7/G"),
                          ("Amaj7", "AMaj7"), ("Bø", "B-7b5"),
                          ("Cmaj", "C"), ("F#dim7", "F#dim7"),
                          ("  C  ", "C")]:
            self.assertEqual(pipeline.saneja_nom_acord(brut), net, brut)

    def test_nom_buit(self):
        self.assertEqual(pipeline.saneja_nom_acord("   "), "")


class TestRenameEditor(_rename_sanejat___Base):
    def test_editor_saneja_el_nom(self):
        v = _rename_sanejat___visor()
        v._ed_kind, v._ed_idx = "chord", 1
        v.ed_ini.setText("4.0")
        v.ed_nom.setText(BRUT)
        v._aplica_editor()
        self.assertEqual(v.acords[1][2][0], NET)


class TestRenameInlineTimeline(_rename_sanejat___Base):
    def test_renom_inline_saneja(self):
        v = _rename_sanejat___visor()
        v._on_chord_renamed(0, "  A/B  ")
        self.assertEqual(v.acords[0][2][0], "A/B")     # símbol conservat, espais fora

    def test_renom_inline_normal_es_canonicalitza(self):
        v = _rename_sanejat___visor()
        v._on_chord_renamed(0, "C#m7")
        self.assertEqual(v.acords[0][2][0], "C#-7")    # notació canònica


class TestAltaCoherent(_rename_sanejat___Base):
    def test_afegeix_acord_usa_el_mateix_sanejat(self):
        v = _rename_sanejat___visor()
        self.assertTrue(v._afegeix_acord(10.0, BRUT))
        nou = [a[2][0] for a in v.acords if abs(float(a[0]) - 10.0) < 1e-6]
        self.assertEqual(nou, [NET])


def _rename_sanejat_tearDownModule():
    # Neteja ORDENADA dels objectes Qt del mòdul (evita destrucció pel GC en un
    # test posterior -> access violation intermitent). Vegeu tests/_qt_neteja.py.
    try:
        import _qt_neteja
    except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_rename_seleccio.py
# ══════════════════════════════════════════════════════════════════════════
"""Renombrar/editar: mantenir la selecció i refrescar la llista a l'instant,
i RENOM EN BLOC de la selecció del TIPUS ACTIU (amb selecció mixta es
renombren només els del tipus del clip actiu, opció A).

Com un DAW: editar no ha de perdre la selecció ni deixar la llista vella (regla
d'or #11: mateix tracte acords↔estructura). La selecció mixta serveix per a
operacions de BLOC (eliminar/copiar/enganxar/duplicar/moure) i per renombrar el
tipus actiu.
"""


_rename_seleccio__ACORDS = "0.0,2.0,C\n2.0,4.5,Am\n4.5,7.0,F\n7.0,10.0,G\n10.0,20.0,C\n"
_rename_seleccio__SECCIONS = ("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
            "0.0,5.0,5.0,A,A,1.1,5.1\n"
            "5.0,10.0,5.0,B,B,5.1,10.1\n"
            "10.0,20.0,10.0,C,C,10.1,20.1\n")


def _rename_seleccio___visor():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "tema.wav")
    out = os.path.join(td, "AUTOCHORDS_tema")
    os.makedirs(out)
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * 20)
    ca = os.path.join(out, "acords.csv")
    sa = os.path.join(out, "estructura_ABC.csv")
    with open(ca, "w", encoding="utf-8") as f:
        f.write(_rename_seleccio__ACORDS)
    with open(sa, "w", encoding="utf-8") as f:
        f.write(_rename_seleccio__SECCIONS)
    v = visor_mod.Visor(wav, ca, sa, bpm=120, bpb=4, tempo_fix=False)
    v.td, v.sortida = td, out
    return v


class _rename_seleccio___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])


class TestEditorManteSeleccio(_rename_seleccio___Base):
    def _aplica(self, v, kind, idx, nom, ini_txt):
        v._ed_kind, v._ed_idx = kind, idx
        v.ed_nom.setText(nom)
        v.ed_ini.setText(ini_txt)
        v.ed_cb.setText("")
        v._aplica_editor()

    def test_acord_queda_seleccionat_i_llista_al_dia(self):
        v = _rename_seleccio___visor()
        v.ves_a(7.0)
        v.timeline.select_clip("chord", 3)
        self._aplica(v, "chord", 3, "Gmaj7", "7.00")
        self.assertEqual(v.acords[3][2][0], "GMaj7")
        self.assertEqual(v.timeline.selected_keys(), {("chord", 3)},
                         "el clip editat ha de quedar seleccionat")
        self.assertEqual(v.llista_ac.currentRow(), 3)
        self.assertIn("GMaj7", v.llista_ac.currentItem().text(),
                      "la llista s'ha d'actualitzar a l'instant")
        self.assertAlmostEqual(v.pos, 7.0, places=6,
                               msg="editar no ha de moure el cursor")
        v.close()

    def test_seccio_queda_seleccionada_i_llista_al_dia(self):
        v = _rename_seleccio___visor()
        v.ves_a(12.0)
        v.timeline.select_clip("section", 2)
        v.ed_fam.setText("X")
        self._aplica(v, "section", 2, "Z", "12.00")
        self.assertEqual(v.seccions[2][2], "Z")
        self.assertEqual(v.timeline.selected_keys(), {("section", 2)})
        self.assertEqual(v.llista_ab.currentRow(), 2)
        self.assertIn("Z", v.llista_ab.currentItem().text())
        self.assertAlmostEqual(v.pos, 12.0, places=6)
        v.close()


class TestRenomEnBloc(_rename_seleccio___Base):
    def test_acords_en_bloc(self):
        v = _rename_seleccio___visor()
        v.timeline.select_clip("chord", 0)
        v.timeline.extend_selection("chord", 2)     # {0,1,2}
        with patch.object(QInputDialog, "getText",
                          return_value=("Am", True)):
            self.assertTrue(v.renomena_seleccio())
        self.assertEqual([a[2][0] for a in v.acords[:3]], ["A-", "A-", "A-"])
        self.assertEqual(v.timeline.selected_keys(),
                         {("chord", 0), ("chord", 1), ("chord", 2)})
        self.assertEqual(len(v._undo_stack), 1)     # una sola operació
        v.undo()
        self.assertEqual([a[2][0] for a in v.acords[:3]], ["C", "Am", "F"])
        v.close()

    def test_seccions_en_bloc(self):
        v = _rename_seleccio___visor()
        v.timeline.select_clip("section", 1)
        v.timeline.extend_selection("section", 2)   # {1,2}
        with patch.object(QInputDialog, "getText",
                          return_value=("R", True)):
            self.assertTrue(v.renomena_seleccio())
        self.assertEqual([s[2] for s in v.seccions[1:]], ["R", "R"])
        self.assertEqual(v.timeline.selected_keys(),
                         {("section", 1), ("section", 2)})
        v.close()

    def test_seleccio_mixta_renombra_el_tipus_actiu(self):
        """Opció A: amb selecció mixta es renombren NOMÉS els del tipus actiu."""
        v = _rename_seleccio___visor()
        v.timeline.select_clip("chord", 0)
        v.timeline.toggle_selection("section", 0)   # mixta; actiu = section 0
        with patch.object(QInputDialog, "getText", return_value=("R", True)):
            self.assertTrue(v.renomena_seleccio())
        self.assertEqual(v.seccions[0][2], "R")     # la secció sí
        self.assertEqual([a[2][0] for a in v.acords],
                         ["C", "Am", "F", "G", "C"])  # els acords, intactes
        self.assertEqual(len(v._undo_stack), 1)
        v.close()


class TestRenomInlineManteSeleccio(_rename_seleccio___Base):
    def test_inline_mante_seleccio_i_llista(self):
        v = _rename_seleccio___visor()
        v.ves_a(7.0)
        v.timeline.select_clip("chord", 3)
        # flux faithful: el timeline ja té el nom nou quan arriba el senyal
        v.timeline._acords[3] = (7.0, "G7", "7.0")
        v.timeline.chordRenamed.emit(3, "G7")
        self.assertEqual(v.acords[3][2][0], "G7")
        self.assertEqual(v.timeline.selected_keys(), {("chord", 3)})
        self.assertIn("G7", v.llista_ac.currentItem().text())
        v.close()


def _rename_seleccio_tearDownModule():
    try:
        import _qt_neteja
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_seleccio_creuada.py
# ══════════════════════════════════════════════════════════════════════════
"""Rang de selecció per TEMPS (Shift+clic) + renom en bloc estil fulla de càlcul
(opció A: amb selecció mixta, només el tipus actiu).

- `extend_selection`: el rang es calcula per temps i es queda SEMPRE al carril
  del clip clicat. (La «selecció creuada» es va retirar el 16-10-2026: per
  agafar clips de les dues pistes de cop es fa servir el **marquee**,
  Ctrl+arrossegant o amb l'eina «marc».)
- `_renomena_acords`/`_renomena_seccions`: renom de molts elements de cop, i
  el camp Nom + «Aplica» de l'editor també ho fa amb una multi-selecció.
Regla d'or #11: mateix tracte acords↔estructura.
"""


# acords: 0 C · 2 Am · 4.5 F · 7 G · 10 C   |   seccions: A 0-5 · B 5-10 · C 10-20
_seleccio_creuada__ACORDS = "0.0,2.0,C\n2.0,4.5,Am\n4.5,7.0,F\n7.0,10.0,G\n10.0,20.0,C\n"
_seleccio_creuada__SECCIONS = ("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
            "0.0,5.0,5.0,A,A,1.1,5.1\n"
            "5.0,10.0,5.0,B,B,5.1,10.1\n"
            "10.0,20.0,10.0,C,C,10.1,20.1\n")


def _seleccio_creuada___visor():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "tema.wav")
    out = os.path.join(td, "AUTOCHORDS_tema")
    os.makedirs(out)
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * 20)
    ca = os.path.join(out, "acords.csv")
    sa = os.path.join(out, "estructura_ABC.csv")
    with open(ca, "w", encoding="utf-8") as f:
        f.write(_seleccio_creuada__ACORDS)
    with open(sa, "w", encoding="utf-8") as f:
        f.write(_seleccio_creuada__SECCIONS)
    v = visor_mod.Visor(wav, ca, sa, bpm=120, bpb=4, tempo_fix=False)
    v.td, v.sortida = td, out
    return v


class _seleccio_creuada___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])


class TestRangDUnCarril(_seleccio_creuada___Base):
    def test_shift_de_chord_a_chord_nomes_acords(self):
        v = _seleccio_creuada___visor()
        try:
            tl = v.timeline
            tl.select_clip("chord", 0)
            tl.extend_selection("chord", 3)      # rang [0.0, 7.0]
            # NOMÉS el carril dels acords (el creuat es va retirar)
            self.assertEqual(tl.selected_keys(), {
                ("chord", 0), ("chord", 1), ("chord", 2), ("chord", 3)})
        finally:
            v.close()

    def test_shift_de_section_a_section_nomes_seccions(self):
        v = _seleccio_creuada___visor()
        try:
            tl = v.timeline
            tl.select_clip("section", 1)
            tl.extend_selection("section", 2)    # rang [5.0, 10.0]
            self.assertEqual(tl.selected_keys(),
                             {("section", 1), ("section", 2)})
        finally:
            v.close()

    def test_copia_enganxa_bloc_mixt(self):
        """Copiar «secció + acords» i enganxar-ho: canvien LES DUES pistes."""
        v = _seleccio_creuada___visor()
        try:
            tl = v.timeline
            tl.select_multi({("chord", 2), ("chord", 3), ("section", 1)})
            tl.copy_selection()
            tl.set_position(10.0, emit=False, snap=False)   # cursor mogut
            b = [s[2] for s in v.seccions].count("B")
            tl.paste_at_cursor()
            # acords: el bloc F(4.5), G(7.0) s'enganxa a 10.0 → 10 F, 12.5 G
            self.assertEqual(v.acords[4][2][0], "F")
            self.assertEqual(v.acords[5][2][0], "G")
            # estructura: la secció B s'ha sobreescrit al tram nou
            self.assertEqual([s[2] for s in v.seccions].count("B"), b + 1)
        finally:
            v.close()


class TestRenomMultiple(_seleccio_creuada___Base):
    def test_editor_aplica_renombra_tot_el_bloc(self):
        """Seleccionar acords 0,2,4 i «Aplica» → tots a G (com una fulla)."""
        v = _seleccio_creuada___visor()
        try:
            v.timeline.select_multi({("chord", 0), ("chord", 2), ("chord", 4)})
            v._ed_kind, v._ed_idx = "chord", 0
            v.ed_nom.setText("G")
            v._aplica_editor()
            self.assertEqual([a[2][0] for a in v.acords],
                             ["G", "Am", "G", "G", "G"])
            self.assertEqual(len(v._undo_stack), 1)      # una sola operació
            v.undo()
            self.assertEqual([a[2][0] for a in v.acords],
                             ["C", "Am", "F", "G", "C"])
        finally:
            v.close()

    def test_editor_aplica_mixt_renombra_el_tipus_actiu(self):
        v = _seleccio_creuada___visor()
        try:
            v.timeline.select_multi({("chord", 0), ("chord", 1),
                                     ("section", 0), ("section", 1)})
            v._ed_kind, v._ed_idx = "chord", 0          # actiu = acords
            v.ed_nom.setText("Dm")
            v._aplica_editor()
            self.assertEqual([a[2][0] for a in v.acords[:3]], ["D-", "D-", "F"])
            self.assertEqual([s[2] for s in v.seccions], ["A", "B", "C"])
        finally:
            v.close()

    def test_renomena_seccions_en_bloc_conserva_lletra_i_familia(self):
        v = _seleccio_creuada___visor()
        try:
            self.assertTrue(v._renomena_seccions([0, 2], "Z"))
            self.assertEqual([s[2] for s in v.seccions], ["Z", "B", "Z"])
            self.assertEqual([s[3] for s in v.seccions], ["Z", "B", "Z"])
        finally:
            v.close()

    def test_menu_de_llista_te_reanomena(self):
        """El menú contextual de les llistes ha d'oferir «Reanomena» (regla #11)."""
        for nom_menu, esperat in (("_menu_acord", "acord"),
                                  ("_menu_seccio", "secció")):
            v = _seleccio_creuada___visor()
            capt = {}
            orig_exec = QMenu.exec_
            orig_idx = QListWidget.indexAt

            class _Fila:
                def row(self):
                    return 0
            QMenu.exec_ = lambda self, pos, *a: capt.update(
                texts=[t.text() for t in self.actions() if not t.isSeparator()])
            QListWidget.indexAt = lambda self, pos: _Fila()
            try:
                getattr(v, nom_menu)(QPoint(1, 1))
            finally:
                QMenu.exec_ = orig_exec
                QListWidget.indexAt = orig_idx
            self.assertTrue(any("Reanomena" in t for t in capt["texts"]),
                            f"{nom_menu}: {capt['texts']}")
            self.assertTrue(any(esperat in t.lower() for t in capt["texts"]))
            v.close()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_seccions_contigues.py
# ══════════════════════════════════════════════════════════════════════════
"""Regressió del BUG #3 (informe OC-6/340): moure una secció cap endavant
creava un **FORAT INTERN** que l'app acceptava.

Regles d'or afectades: **#2** (contigüitat: `prev.fi == curr.ini`) i **#4**
(la suma de les durades dels clips == durada de la WAV).

Cobreix els 3 camins que podien crear el forat: el **MCP** (`move_section`),
l'**editor** de la franja Editor, i la **càrrega** d'un CSV que ja venia amb
forat (que s'ha de normalitzar també AL DISC).
"""


_seccions_contigues__DUR = 40.0
# 4 seccions contigües que cobreixen 0–40: A, B, C, D
_seccions_contigues__SECCIONS = [(0.0, 10.0, "A", "A"), (10.0, 20.0, "B", "B"),
            (20.0, 30.0, "C", "C"), (30.0, 40.0, "D", "D")]


def _seccions_contigues___escriu_wav(ruta, dur=_seccions_contigues__DUR):
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


def _seccions_contigues___llegeix_abc(ruta):
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


def _seccions_contigues___visor(seccions=None):
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "tema.wav")
    _seccions_contigues___escriu_wav(wav)
    sortida = pipeline.carpeta_sortida(wav)
    os.makedirs(sortida, exist_ok=True)
    ca = os.path.join(sortida, "acords.csv")
    with open(ca, "w", encoding="utf-8") as f:
        f.write("0.0,10.0,C\n")
    sa = os.path.join(sortida, "estructura_ABC.csv")
    _escriu_abc(sa, _seccions_contigues__SECCIONS if seccions is None else seccions)
    v = visor_mod.Visor(wav, ca, sa, 120.0, 4, True)
    v.td, v.sortida, v.abc_csv = td, sortida, sa
    return v


class _seccions_contigues___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])


class _seccions_contigues___FinestraFalsa:
    def __init__(self, visor):
        self.visor_ref = visor
        self.sortida = "/tmp/out"

    def windowTitle(self):
        return "Auto Chords — prova"


class TestMoureSeccioManteContiguitat(_seccions_contigues___Base):
    def test_moure_l_inici_endavant_no_deixa_forat(self):
        """Repro exacte del bug: moure la secció 2 a 25.0–30.0."""
        v = _seccions_contigues___visor()
        self.assertTrue(v.mou_seccio(2, 25.0, 30.0))
        # #2: B s'estén fins al nou inici i C arrenca allà mateix
        self.assertAlmostEqual(float(v.seccions[1][1]), 25.0, places=6)
        self.assertAlmostEqual(float(v.seccions[2][0]), 25.0, places=6)
        # #4: la suma continua sent la durada de la WAV
        self.assertAlmostEqual(_suma(v.seccions), _seccions_contigues__DUR, places=6)
        self.assertTrue(_contigues(v.seccions))

    def test_moure_el_fi_arrossega_la_seguent(self):
        v = _seccions_contigues___visor()
        self.assertTrue(v.mou_seccio(1, 10.0, 24.0))     # B = 10–24
        self.assertAlmostEqual(float(v.seccions[2][0]), 24.0, places=6)
        self.assertAlmostEqual(_suma(v.seccions), _seccions_contigues__DUR, places=6)
        self.assertTrue(_contigues(v.seccions))

    def test_el_csv_del_disc_queda_normalitzat(self):
        v = _seccions_contigues___visor()
        v.mou_seccio(2, 25.0, 30.0)
        v._desa_i_regenera()
        s = _seccions_contigues___llegeix_abc(v.abc_csv)
        self.assertTrue(_contigues(s), "el CSV del disc té un forat intern")
        self.assertAlmostEqual(_suma(s), _seccions_contigues__DUR, places=3)

    def test_moure_el_primer_obre_capcalera_sense_seccio(self):
        """Moure el 1r clip cap endavant no crea forat: s'hi posa una «-»."""
        v = _seccions_contigues___visor()
        self.assertTrue(v.mou_seccio(0, 2.0, 10.0))
        v._desa_i_regenera()
        self.assertTrue(_contigues(v.seccions))
        self.assertAlmostEqual(_suma(v.seccions), _seccions_contigues__DUR, places=6)
        self.assertEqual(v.seccions[0][2], "-")
        self.assertTrue(_contigues(_seccions_contigues___llegeix_abc(v.abc_csv)))

    def test_xarxa_de_seguretat_si_un_cami_oblida_la_contiguitat(self):
        """Doble protecció: encara que una mutació crua deixi un forat, en
        desar el model queda normalitzat (amb «-» al forat) i el CSV net."""
        v = _seccions_contigues___visor()
        v.seccions[2] = (25.0, 30.0, "C", "C")     # mutació a pèl (vella manera)
        self.assertFalse(_contigues(v.seccions))
        v._desa_i_regenera()                        # → invariant de cobertura
        self.assertTrue(_contigues(v.seccions))
        self.assertAlmostEqual(_suma(v.seccions), _seccions_contigues__DUR, places=6)
        self.assertEqual([s[2] for s in v.seccions], ["A", "B", "-", "C", "D"])
        self.assertTrue(_contigues(_seccions_contigues___llegeix_abc(v.abc_csv)))

    def test_la_xarxa_tambe_arregla_encavalcaments_i_durades_nulles(self):
        """Regles #2 i #8 a la xarxa de seguretat: un CSV editat a mà (o un
        projecte vell) pot portar seccions encavalcades o de durada zero.

        Auditoria 18-10-2026: sobrevivien. Mana la secció que ARRENCA MÉS TARD
        (el seu inici retalla el fi de l'anterior); les de durada nul·la fora.
        """
        a, b = pipeline.normalitza_cobertura(
            [], [(0.0, 10.0, "A", "A"), (5.0, 20.0, "B", "B")], _seccions_contigues__DUR)
        self.assertEqual([(float(s[0]), float(s[1]), s[2]) for s in b],
                         [(0.0, 5.0, "A"), (5.0, _seccions_contigues__DUR, "B")])
        self.assertTrue(_contigues(b))
        a, b = pipeline.normalitza_cobertura(
            [], [(0.0, 5.0, "A", "A"), (5.0, 5.0, "B", "B"),
                 (5.0, _seccions_contigues__DUR, "C", "C")], _seccions_contigues__DUR)
        self.assertEqual([s[2] for s in b], ["A", "C"])       # la nul·la, fora
        self.assertTrue(_contigues(b))
        a, b = pipeline.normalitza_cobertura(
            [], [(0.0, 20.0, "A", "A"), (2.0, 3.0, "B", "B"),
                 (5.0, _seccions_contigues__DUR, "C", "C")], _seccions_contigues__DUR)
        self.assertTrue(_contigues(b))
        self.assertAlmostEqual(_suma(b), _seccions_contigues__DUR, places=6)

    def test_ubicar_l_unica_seccio_on_ja_es_no_es_cap_error(self):
        """Un moviment d'IDENTITAT no és un moviment (trobat per OC-13).

        `ac_move_section` a les mateixes coordenades ha de respondre OK (ubicar
        una cosa on ja és no és cap error), pero moure-la de debò sí que s'ha de
        refusar: només hi ha una secció i ha de cobrir tota la WAV (regla #4).
        """
        v = _seccions_contigues___visor()
        v.seccions = [(0.0, _seccions_contigues__DUR, "A", "A")]
        self.assertTrue(v.mou_seccio(0, 0.0, _seccions_contigues__DUR), "identitat -> OK")
        with self.assertRaises(ValueError):
            v.mou_seccio(0, 2.0, _seccions_contigues__DUR)      # això sí que trencaria la cobertura
        self.assertEqual([(float(s[0]), float(s[1]), s[2]) for s in v.seccions],
                         [(0.0, _seccions_contigues__DUR, "A")], "i el model no s'ha tocat")

    def test_rebutja_si_un_vei_queda_sense_marge(self):
        v = _seccions_contigues___visor()
        with self.assertRaises(ValueError):
            v.mou_seccio(2, 10.0001, 30.0)   # deixaria B amb 0,0001 s (veí previ)
        with self.assertRaises(ValueError):
            v.mou_seccio(2, 20.0, 39.9999)   # deixaria D amb 0,0001 s (veí següent)
        # I el model NO ha quedat tocat pels intents rebutjats.
        self.assertEqual(v.seccions, _seccions_contigues__SECCIONS)


class TestEditorDeSeccions(_seccions_contigues___Base):
    def test_canviar_l_inici_al_editor_mante_la_contiguitat(self):
        v = _seccions_contigues___visor()
        v._ed_kind, v._ed_idx = "section", 2
        v.ed_ini.setText("25.0")
        v.ed_nom.setText("C")
        v.ed_fam.setText("C")
        v._aplica_editor()
        self.assertAlmostEqual(float(v.seccions[1][1]), 25.0, places=2)
        self.assertTrue(_contigues(v.seccions))
        self.assertAlmostEqual(_suma(v.seccions), _seccions_contigues__DUR, places=3)


class TestCarregaCSVAmbForat(_seccions_contigues___Base):
    def test_el_model_i_el_disc_queden_normalitzats_en_carregar(self):
        # CSV "antic"/dolent: A 0–10 i B 12–40 → forat de 10 a 12 s
        v = _seccions_contigues___visor(seccions=[(0.0, 10.0, "A", "A"), (12.0, 40.0, "B", "B")])
        # El MODEL queda contigu (amb una «-» que tapa el forat)
        self.assertTrue(_contigues(v.seccions))
        self.assertAlmostEqual(_suma(v.seccions), _seccions_contigues__DUR, places=6)
        self.assertIn("-", [s[2] for s in v.seccions])
        # ... I el CSV DEL DISC ja s'ha reescrit (abans calia editar/exportar)
        s = _seccions_contigues___llegeix_abc(v.abc_csv)
        self.assertTrue(_contigues(s), "el CSV del disc encara té el forat")
        self.assertAlmostEqual(_suma(s), _seccions_contigues__DUR, places=3)


def _seccions_contigues_tearDownModule():
    # Neteja ORDENADA dels objectes Qt del mòdul (evita destrucció pel GC en un
    # test posterior -> access violation intermitent). Vegeu tests/_qt_neteja.py.
    try:
        import _qt_neteja
    except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_temps_fora_rang.py
# ══════════════════════════════════════════════════════════════════════════
"""Regressió del BUG #4 (informe OC-6/341): NO hi havia TOPALL SUPERIOR de temps.

Repro original (app viva, WAV de 199,604 s): `ac_add_chord(250)`,
`ac_move_chord(5,1000)` i `ac_add_section(200,250)` s'acceptaven → l'últim clip
quedava amb durada efectiva <= 0 i l'invariant #4 (suma == durada) ja no es
podia complir. El negatiu SÍ que es rebutjava.

**Decisió**: REBUTJAR (simètric amb el negatiu) en lloc d'acotar en silenci.
A la càrrega, però, el model es REPARA (acords fora de la WAV s'eliminen i el
`fi` d'una última secció que surt s'acota), i el CSV del disc s'hi reescriu.
"""


_temps_fora_rang__DUR = 40.0


def _temps_fora_rang___escriu_wav(ruta, dur=_temps_fora_rang__DUR):
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * int(44100 * dur))


def _llegeix_acords(ruta):
    with open(ruta, encoding="utf-8") as f:
        return [(float(r[0]), r[1]) for r in csv.reader(f) if r]


def _temps_fora_rang___llegeix_abc(ruta):
    files = []
    with open(ruta, encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) < 4 or row[0].startswith("inici"):
                continue
            files.append((float(row[0]), float(row[1]), row[3], row[4]))
    return files


def _temps_fora_rang___visor(acords=((0.0, "C"), (4.0, "G")), seccions=None):
    seccions = seccions or [(0.0, 20.0, "A", "A"), (20.0, _temps_fora_rang__DUR, "B", "B")]
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "tema.wav")
    _temps_fora_rang___escriu_wav(wav)
    sortida = pipeline.carpeta_sortida(wav)
    os.makedirs(sortida, exist_ok=True)
    ca = os.path.join(sortida, "acords.csv")
    with open(ca, "w", encoding="utf-8") as f:
        for t, nom in acords:
            f.write(f"{t},{t + 1},{nom}\n")
    if not acords:
        f_empty = open(ca, "w", encoding="utf-8")
        f_empty.close()
    sa = os.path.join(sortida, "estructura_ABC.csv")
    with open(sa, "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n")
        for ini, fi, L, fam in seccions:
            f.write(f"{ini},{fi},{fi - ini},{L},{fam},1.1,2.1\n")
    v = visor_mod.Visor(wav, ca, sa, 120.0, 4, True)
    v.td, v.sortida, v.csv_abc = td, sortida, sa
    return v


class _temps_fora_rang___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])


class _temps_fora_rang___FinestraFalsa:
    def __init__(self, visor):
        self.visor_ref = visor
        self.sortida = "/tmp/out"

    def windowTitle(self):
        return "Auto Chords — prova"


class TestTopallSuperiorAcords(_temps_fora_rang___Base):
    def test_validador_rebutja_acord_mes_enlla_de_la_wav(self):
        v = _temps_fora_rang___visor()
        with self.assertRaises(ValueError):
            v._valida_canvis_acords([(0.0, "C", "0"),
                                     (1000.0, "G", "1000.0")])

    def test_validador_rebutja_acord_al_final_exacte(self):
        """A la darrera mostra el clip tindria durada 0 → no és un clip."""
        v = _temps_fora_rang___visor()
        with self.assertRaises(ValueError):
            v._valida_canvis_acords([(_temps_fora_rang__DUR, "C", "40.0")])

    def test_validador_accepta_el_darrer_acord_dins_la_wav(self):
        v = _temps_fora_rang___visor()
        ok = v._valida_canvis_acords([(0.0, "C", "0"),
                                      (_temps_fora_rang__DUR - 0.01, "G", "39.99")])
        self.assertEqual(len(ok), 2)


class TestTopallSuperiorSeccions(_temps_fora_rang___Base):
    def test_validador_rebutja_seccio_que_surt_de_la_wav(self):
        v = _temps_fora_rang___visor()
        with self.assertRaises(ValueError):
            v._valida_canvis_seccions([(0.0, 10.0, "A", "A"),
                                       (20.0, 250.0, "B", "B")])

    def test_validador_accepta_fi_igual_a_la_durada(self):
        v = _temps_fora_rang___visor()
        self.assertEqual(
            len(v._valida_canvis_seccions([(0.0, _temps_fora_rang__DUR, "A", "A")])), 1)


class TestCarregaAmbTempsFora(_temps_fora_rang___Base):
    def test_acords_fora_de_la_wav_s_eliminen_i_el_disc_queda_net(self):
        v = _temps_fora_rang___visor(acords=((0.0, "C"), (4.0, "G"), (250.0, "X")))
        self.assertNotIn("X", [a[2][0] for a in v.acords])
        self.assertAlmostEqual(max(float(a[0]) for a in v.acords), 4.0, places=6)
        self.assertNotIn("X", [nom for _t, nom in _llegeix_acords(v.csv_acords)])

    def test_una_seccio_que_surt_de_la_wav_s_acota_en_carregar(self):
        v = _temps_fora_rang___visor(seccions=[(0.0, 10.0, "A", "A"), (10.0, 999.0, "B", "B")])
        self.assertAlmostEqual(float(v.seccions[-1][1]), _temps_fora_rang__DUR, places=3)
        self.assertAlmostEqual(float(_temps_fora_rang___llegeix_abc(v.csv_abc)[-1][1]), _temps_fora_rang__DUR,
                               places=3)


def _temps_fora_rang_tearDownModule():
    # Neteja ORDENADA dels objectes Qt del mòdul (evita destrucció pel GC en un
    # test posterior -> access violation intermitent). Vegeu tests/_qt_neteja.py.
    try:
        import _qt_neteja
    except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_cobertura_rare.py
# ══════════════════════════════════════════════════════════════════════════
"""Validació — regla d'or #4 (COBERTURA) amb casos RARS, als 4 punts.

Esborrar el primer/últim clip, moure el primer més enllà de 0, esborrar-ho tot,
i l'export després d'editar. La #4 mana: si el 1r clip no arrenca a 0 s'hi afegeix
una «N»; l'últim arriba a la durada; el CSV i l'export surten del MODEL.
"""


_cobertura_rare__DUR = 20.0


def _wav(dur=_cobertura_rare__DUR):
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


class _cobertura_rare___Base(unittest.TestCase):
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


class TestCoberturaRare(_cobertura_rare___Base):
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
        self.assertAlmostEqual(float(v.seccions[-1][1]), _cobertura_rare__DUR, places=2)
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
        for _cobertura_rare___ in range(4):
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
            bpm=120.0, bpb=4, offset=0.0, sr=44100, log=lambda *_cobertura_rare___: None,
            tempo_fix=False, amb_estructura=False, total_s=_cobertura_rare__DUR,
            acords=v.acords, seccions=None)
        with open(ca, encoding="utf-8") as f:
            files = [r for r in csv.reader(f) if r]
        self.assertEqual(len(files), 2)              # només C i G (no F)
        self.assertTrue(files[0][0].startswith("0.00"))
        self.assertNotIn("F", " ".join(r[1] for r in files))
        v.close()


def _cobertura_rare_tearDownModule():
    try:
        import _qt_neteja
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_cobertura_viu.py
# ══════════════════════════════════════════════════════════════════════════
"""Regressió de 2 bugs de producció (cobertura en viu + export del model).

- **(B) COBERTURA (regla d'or #4)**: en editar (p. ex. eliminar el 1r acord) el
  model i el CSV han de mantenir la «N» de capçalera a 0 (clips que cobreixen
  tota la WAV).
- **(A) EXPORT**: l'exportació ha d'usar el MODEL VIU (seccions editades), no el
  `segments.csv` cru de l'anàlisi.
"""


def _cobertura_viu___wav(segons=3.0, sr=44100):
    fd, ruta = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"\x00\x00" * int(sr * segons))
    return ruta


def _cobertura_viu___csv_acords(ruta, items):
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
        wav = _cobertura_viu___wav(3.0)
        ca = os.path.join(td, "acords.csv")
        _cobertura_viu___csv_acords(ca, acords or [(0.5, "C"), (1.5, "G")])
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
        self.assertEqual(v.acords[0][2][0], "N")
        self.assertEqual(len(v.acords), 3)          # N(0) · C(0.5) · G(1.5)
        # (B) Eliminar el 1r acord → ha de tornar a aparèixer la «N» a 0.
        v._elimina_acord(0)
        v._desa_i_regenera()
        self.assertAlmostEqual(float(v.acords[0][0]), 0.0)
        self.assertEqual(v.acords[0][2][0], "N")
        with open(v.csv_acords, encoding="utf-8") as f:
            primera = f.readline().strip()
        cols = primera.split(",")
        self.assertEqual(cols[0], "0.000000")
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
            bpm=120.0, bpb=4, offset=0.0, sr=44100, log=lambda *_cobertura_viu___: None,
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
        _cobertura_viu___csv_acords(ca, [(0.5, "C")])
        pipeline.exporta_total(
            csv_ac=ca, csv_seg=None, sortida=os.path.join(td, "out"),
            bpm=120.0, bpb=4, offset=0.0, sr=44100, log=lambda *_cobertura_viu___: None,
            tempo_fix=False, amb_estructura=False, total_s=3.0,
            acords=[(0.5, "C", "0.5")], seccions=None)
        with open(ca, encoding="utf-8") as f:
            primera = f.readline().strip()
        cols = primera.split(",")
        self.assertEqual(cols[0], "0.000000")
        self.assertEqual(cols[2], "N")

    def test_export_sense_model_segueix_llegint_el_csv(self):
        # Retrocompatibilitat: sense `acords`/`seccions` es llegeix el CSV (com abans).
        td = tempfile.mkdtemp()
        ca = os.path.join(td, "acords.csv")
        _cobertura_viu___csv_acords(ca, [(0.0, "N"), (1.0, "C")])
        r = pipeline.exporta_total(
            csv_ac=ca, csv_seg=None, sortida=os.path.join(td, "out"),
            bpm=120.0, bpb=4, offset=0.0, sr=44100, log=lambda *_cobertura_viu___: None,
            tempo_fix=False, amb_estructura=False, total_s=3.0)
        self.assertEqual(r["acords_csv"], os.path.abspath(ca))


def _cobertura_viu_tearDownModule():
    # Neteja ORDENADA dels objectes Qt del mòdul (evita destrucció pel GC en un
    # test posterior -> access violation intermitent). Vegeu tests/_qt_neteja.py.
    try:
        import _qt_neteja
    except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_regles_or.py
# ══════════════════════════════════════════════════════════════════════════
"""Regressió de les REGLES D'OR que encara no tenien test propi.

`docs/REGLES_DE_LA_APP.md` diu que les regles **2, 4, 9 i 11** ja en tenen;
aquí blindem les que no: **1** (ordre estricte — amb un gap conegut al backend,
vegeu el test), **3** (durades derivades), **5** (una sola font de veritat),
**6** (les WAVs només via `exporta()`), **7** (instància única), **8** (temps
vàlids) i **10** (estat en un directori escriptible).
"""


def _regles_or___visor(dur=10.0):
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
        f.write("0.0,2.0,C\n2.0,5.0,Am\n5.0,10.0,F\n")
    sa = os.path.join(sortida, "estructura_ABC.csv")
    with open(sa, "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n")
        f.write("0.0,5.0,5.0,A,A,1.1,5.1\n")
        f.write("5.0,10.0,5.0,B,B,5.1,10.1\n")
    v = visor_mod.Visor(wav, ca, sa, 120.0, 4, True)
    v.td, v.sortida = td, sortida
    return v


class _regles_or___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])


class TestRegla3DuradesDerivades(_regles_or___Base):
    """Regla 3: la durada d'un clip es DERIVA, no s'emmagatzema."""

    def test_cap_camp_de_durada_al_model(self):
        v = _regles_or___visor()
        for a in v.acords:
            self.assertEqual(len(a), 3, f"acord amb camps estranys: {a!r}")
        for s in v.seccions:
            self.assertEqual(len(s), 4, f"secció amb camps estranys: {s!r}")

    def test_la_durada_del_darrer_clip_es_deriva_de_la_wav(self):
        v = _regles_or___visor()
        self.assertAlmostEqual(float(v.seccions[-1][1]),
                               float(v.audio["durada"]), places=2)


class TestRegla5FontDeVeritat(_regles_or___Base):
    """Regla 5: el CSV del disc reflexa el MODEL (font única = pipeline)."""

    def test_el_csv_del_disc_reflecteix_el_model(self):
        v = _regles_or___visor()
        v._afegeix_acord(3.0, "G")
        v._elimina_acord(0)
        v._desa_i_regenera()
        with open(v.csv_acords, encoding="utf-8") as f:
            files = [r for r in csv.reader(f) if r]
        self.assertEqual(len(files), len(v.acords))
        for fila, model in zip(files, v.acords):
            self.assertAlmostEqual(float(fila[0]), float(model[0]), places=2)
            self.assertEqual(fila[2], model[2][0])


class TestRegla6WavsNomesViaExporta(_regles_or___Base):
    """Regla 6: l'edició MAI toca les WAVs generades."""

    def test_editar_no_crea_ni_toca_cap_wav(self):
        v = _regles_or___visor()
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


class TestRegla8TempsValids(_regles_or___Base):
    """Regla 8: cap temps negatiu ni durada <= 0."""

    def test_acord_amb_inici_negatiu_es_rebutjat(self):
        v = _regles_or___visor()
        with self.assertRaises(ValueError):
            v._valida_canvis_acords([(-0.5, "C", "-0.5")])

    def test_seccio_negativa_o_de_durada_nula_es_rebutjada(self):
        v = _regles_or___visor()
        with self.assertRaises(ValueError):
            v._valida_canvis_seccions([(-1.0, 5.0, "A", "A")])
        with self.assertRaises(ValueError):
            v._valida_canvis_seccions([(5.0, 5.0, "A", "A")])

    def test_les_xarxes_de_seguretat_tambe_ho_arreglen(self):
        """Els normalitzadors (l'última xarxa dels 4 camins) tambe compleixen
        la regla 8: cap valor negatiu ni impossible hi sobreviu.

        Auditoria 18-10-2026: abans `normalitza_cobertura` deixava passar un
        acord a -2 s i `normalitza_trams` un tram a -5 s amb bpm 0 (un CSV
        editat a mà o un projecte vell hi podien arribar).
        Nota (22-10-2026): el compàs 0/0 ja NO és un error: és un tram **en
        segons** (rubato), i s'ha de conservar.
        """
        from app import tempo_map as tempo
        ac, _sec = pipeline.normalitza_cobertura(
            [(-2.0, "C", "0"), (5.0, "G", "5")], [], 30.0)
        self.assertEqual(float(ac[0][0]), 0.0)
        a, b = pipeline.normalitza_cobertura(
            [], [(-3.0, -1.0, "X", "X"), (-1.0, 10.0, "A", "A"),
                 (10.0, 30.0, "B", "B")], 30.0)
        self.assertEqual([(float(s[0]), float(s[1]), s[2]) for s in b],
                         [(0.0, 10.0, "A"), (10.0, 30.0, "B")])
        trams = tempo.normalitza_trams(
            [(-5.0, 2.0, 0.0, 0, 0), (2.0, 30.0, 90.0, 3, 4)], 30.0)
        self.assertEqual(trams[0][0], 0.0)
        self.assertGreater(trams[0][2], 0)
        self.assertEqual(trams[0][2], 100.0)          # referència de notació
        self.assertEqual((trams[0][3], trams[0][4]), (0, 0))   # en segons

    def test_estructura_amb_linies_malmeses_no_peta(self):
        """El lector de l'ABC (cami de CARREGA) ha de ser tan robust com el
        dels acords: una linia malmesa es descarta amb avis i la resta del tema
        s'obre igual (abans petava i el tema no s'obria)."""
        import tempfile

        from app import visor as visor_mod
        td = tempfile.mkdtemp()
        ruta = os.path.join(td, "estructura_ABC.csv")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n")
            f.write("0.0,5.0,5.0,A,A,1.1,5.1\n")
            f.write("x,9.0,9.0,Z,Z,1.1,5.1\n")      # no numeric -> fora
            f.write("5.0,10.0,5.0,B\n")              # sense família -> la lletra
        self.assertEqual(visor_mod.llegeix_abc(ruta),
                         [(0.0, 5.0, "A", "A"), (5.0, 10.0, "B", "B")])

    def test_el_mapa_del_visor_no_pot_quedar_trencat(self):
        """Construir el mapa (R1/R2/R4/R8) sempre ix normalitzat, vinga d'on
        vinga la còpia: `_refresca_tempo_map` és el punt únic on es fa."""
        v = _regles_or___visor(dur=20.0)
        v.tempo_trams = [(5.0, 8.0, 0.0, 0, 0), (8.0, 30.0, 90.0, 3, 4)]
        v._refresca_tempo_map()
        self.assertEqual(float(v.tempo_trams[0][0]), 0.0)          # R1/R4
        self.assertGreater(float(v.tempo_trams[0][2]), 0.0)        # R8
        # Un 0/0 és un tros EN SEGONS (vàlid des del 22-10-2026), no un
        # valor trencat: es conserva i el BPM passa a la referència (100).
        self.assertEqual((int(v.tempo_trams[0][3]),
                          int(v.tempo_trams[0][4])), (0, 0))
        self.assertAlmostEqual(float(v.tempo_trams[0][2]), 100.0)
        # I un mapa mètric trencat sí que es repara amb el transport.
        v.tempo_trams = [(5.0, 8.0, 0.0, 4, 4), (8.0, 30.0, 90.0, 3, 4)]
        v._refresca_tempo_map()
        self.assertGreater(int(v.tempo_trams[0][3]), 0)
        self.assertAlmostEqual(float(v.tempo_trams[-1][1]), 20.0,  # R4
                               places=6)
        fis = [float(t[1]) for t in v.tempo_trams]
        inis = [float(t[0]) for t in v.tempo_trams]
        self.assertEqual(fis[:-1], inis[1:])                       # R2


class TestRegla1OrdreEstricte(_regles_or___Base):
    """Regla 1: els clips sempre ordenats per temps d'inici (sense inversions).

    ✅ **BLINDADA AL BACKEND** (2026-10-15, OC-5): `pipeline.normalitza_cobertura`
    —la «xarxa de seguretat» que s'aplica als **4 camins** (edició en viu, visor,
    CSV i export)— ara **reordena** els acords i les seccions. Abans l'ordre
    només el garantia el visor, i un CSV editat a mà hauria arribat a l'export
    desordenat (gap detectat per aquest test).
    """

    def test_el_backend_ordena(self):
        acords, _regles_or___ = pipeline.normalitza_cobertura(
            [(4.0, "C", "4.0"), (2.0, "Am", "2.0")], [], 6.0)
        ts = [a[0] for a in acords]
        self.assertEqual(ts, sorted(ts), "els acords han d'anar ordenats")
        self.assertEqual(ts[0], 0.0, "el 1r acord ha d'arrencar a 0 (capçalera N)")

    def test_el_backend_ordena_seccions(self):
        _regles_or___, ss = pipeline.normalitza_cobertura(
            [], [(5.0, 10.0, "B", "B"), (0.0, 5.0, "A", "A")], 10.0)
        inis = [s[0] for s in ss]
        self.assertEqual(inis, sorted(inis), "les seccions han d'anar ordenades")

    def test_el_visor_valida_i_ordena(self):
        v = _regles_or___visor()
        ordenats = v._valida_canvis_acords(
            [(5.0, "F", "5.0"), (1.0, "C", "1.0")])
        self.assertEqual([a[0] for a in ordenats], [1.0, 5.0],
                         "el visor ha d'ordenar")
        with self.assertRaises(ValueError):
            v._valida_canvis_acords([(2.0, "C", "2.0"), (2.0, "G", "2.0")])


class TestRegla7InstanciaUnica(unittest.TestCase):
    """Regla 7: una sola instància per usuari (bloqueig no bloquejant)."""

    def test_la_segona_instancia_es_rebutjada(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "lock")
            f1 = open(path, "a+")
            f2 = open(path, "a+")
            try:
                self.assertTrue(plataforma.bloqueja_instancia_unica(f1),
                                "la 1a instància ha de poder bloquejar")
                self.assertFalse(plataforma.bloqueja_instancia_unica(f2),
                                 "la 2a instància ha de ser rebutjada")
            finally:
                plataforma.desbloqueja(f1)
                f1.close()
                f2.close()

    def test_en_alliberar_es_pot_tornar_a_bloquejar(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "lock")
            f1 = open(path, "a+")
            self.assertTrue(plataforma.bloqueja_instancia_unica(f1))
            plataforma.desbloqueja(f1)
            f2 = open(path, "a+")
            try:
                self.assertTrue(plataforma.bloqueja_instancia_unica(f2),
                                "en alliberar, una altra instància hi ha d'entrar")
            finally:
                plataforma.desbloqueja(f2)
                f1.close()
                f2.close()


class TestRegla10EstatEscriptible(unittest.TestCase):
    """Regla 10: l'estat viu en un directori ESCRIPTIBLE (mai un de només lectura)."""

    def test_el_directori_de_dades_es_escriptible(self):
        d = config.DADES_DIR
        self.assertTrue(os.path.isdir(d), f"ha d'existir: {d}")
        self.assertTrue(os.access(d, os.W_OK), f"ha de ser escriptible: {d}")
        self.assertTrue(config.LOG_PATH.startswith(d))
        self.assertTrue(config.OPCIONS_PATH.startswith(d))


def _regles_or_tearDownModule():
    # Neteja ORDENADA dels objectes Qt del mòdul (evita destrucció pel GC en un
    # test posterior -> access violation intermitent). Vegeu tests/_qt_neteja.py.
    try:
        import _qt_neteja
    except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_troba_reemplaca.py
# ══════════════════════════════════════════════════════════════════════════
"""Troba i reemplaça: substitució GLOBAL d'un xifrat (acords) o d'una etiqueta
(estructura) a tot el tema. Exacte, una sola operació de desfer, i sense canviar
cap temps (regles d'or intactes).
"""


_troba_reemplaca__ACORDS = "0.0,2.0,Cmaj7\n2.0,4.0,Am\n4.0,6.0,Cmaj7\n6.0,8.0,G\n"
_troba_reemplaca__SECCIONS = ("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
            "0.0,4.0,4.0,A,A,1.1,4.1\n"
            "4.0,8.0,4.0,D,D,4.1,8.1\n")


def _troba_reemplaca___visor():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "tema.wav")
    out = os.path.join(td, "AUTOCHORDS_tema")
    os.makedirs(out)
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * 8)
    ca = os.path.join(out, "acords.csv")
    sa = os.path.join(out, "estructura_ABC.csv")
    with open(ca, "w", encoding="utf-8") as f:
        f.write(_troba_reemplaca__ACORDS)
    with open(sa, "w", encoding="utf-8") as f:
        f.write(_troba_reemplaca__SECCIONS)
    v = visor_mod.Visor(wav, ca, sa, bpm=120, bpb=4, tempo_fix=False)
    v.td, v.sortida = td, out
    return v


class _troba_reemplaca___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])


class TestTrobaReemplaca(_troba_reemplaca___Base):
    def test_acords_xifrat_global(self):
        v = _troba_reemplaca___visor()
        n = v.troba_i_reemplaca("acords", "Cmaj7", "C9")
        self.assertEqual(n, 2)
        self.assertEqual([a[2][0] for a in v.acords], ["C9", "Am", "C9", "G"])
        self.assertEqual(len(v._undo_stack), 1)
        v.undo()
        self.assertEqual([a[2][0] for a in v.acords], ["Cmaj7", "Am", "Cmaj7", "G"])
        v.close()

    def test_exacte_no_toca_parcials(self):
        v = _troba_reemplaca___visor()
        n = v.troba_i_reemplaca("acords", "A", "X")   # "Am" NO és "A"
        self.assertEqual(n, 0)
        self.assertEqual([a[2][0] for a in v.acords], ["Cmaj7", "Am", "Cmaj7", "G"])
        self.assertEqual(len(v._undo_stack), 0)
        v.close()

    def test_estructura_etiqueta_global(self):
        v = _troba_reemplaca___visor()
        n = v.troba_i_reemplaca("estructura", "D", "estribillo")
        self.assertEqual(n, 1)
        self.assertEqual([s[2] for s in v.seccions], ["A", "estribillo"])
        self.assertEqual(v.seccions[1][3], "estribillo",
                         "la família que coincidia també es canvia")
        self.assertEqual(len(v._undo_stack), 1)
        v.undo()
        self.assertEqual([s[2] for s in v.seccions], ["A", "D"])
        v.close()

    def test_sense_canvis_no_fa_res(self):
        v = _troba_reemplaca___visor()
        self.assertEqual(v.troba_i_reemplaca("acords", "Zzz", "Q"), 0)
        self.assertEqual(v.troba_i_reemplaca("estructura", "ZZ", "Y"), 0)
        self.assertEqual(len(v._undo_stack), 0)
        v.close()

    def test_camps_buits_no_fan_res(self):
        v = _troba_reemplaca___visor()
        self.assertEqual(v.troba_i_reemplaca("acords", "", "C9"), 0)
        self.assertEqual(v.troba_i_reemplaca("acords", "Cmaj7", ""), 0)
        v.close()


def _troba_reemplaca_tearDownModule():
    try:
        import _qt_neteja
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_undo_llarg.py
# ══════════════════════════════════════════════════════════════════════════
"""Validació — undo/redo en CADENES LLARGUES (consistència de les piles).

Després de N edicions, N desfers han de tornar EXACTAMENT a l'estat inicial, i
N refers al final; i una edició nova ha de netejar la pila de refer.
"""


_undo_llarg__ACORDS = "0.0,2.0,C\n2.0,4.0,G\n4.0,20.0,Am\n"


def _snapshot(v):
    return [(round(float(a[0]), 6), a[1]) for a in v.acords]


class _undo_llarg___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])

    def _visor(self):
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "tema.wav")
        out = os.path.join(td, "AUTOCHORDS_tema")
        os.makedirs(out)
        with wave.open(wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * 20)
        ca = os.path.join(out, "acords.csv")
        with open(ca, "w", encoding="utf-8") as f:
            f.write(_undo_llarg__ACORDS)
        v = visor_mod.Visor(wav, ca, None, 120.0, 4, False)
        v.td, v.sortida = td, out
        return v

    def _edita(self, v, t, nom):
        v._undo_marca()
        v.acords = v._normalitza_acords(v.acords + [(t, nom, f"{t:.9f}")])
        v._undo_commit()


class TestUndoLlarg(_undo_llarg___Base):
    def test_40_edicions_40_desfers_40_refers(self):
        v = self._visor()
        ini = _snapshot(v)
        for k in range(40):
            self._edita(v, 6.0 + k * 0.2, "X")
        self.assertEqual(len(v.acords), len(ini) + 40)
        self.assertEqual(len(v._undo_stack), 40)
        for _undo_llarg___ in range(40):
            v.undo()
        self.assertEqual(_snapshot(v), ini)
        self.assertEqual(len(v._undo_stack), 0)
        self.assertEqual(len(v._redo_stack), 40)
        for _undo_llarg___ in range(40):
            v.redo()
        self.assertEqual(len(v.acords), len(ini) + 40)
        self.assertEqual(len(v._redo_stack), 0)
        v.close()

    def test_redo_es_neteja_amb_edicio_nova(self):
        v = self._visor()
        self._edita(v, 6.0, "X")
        v.undo()
        self.assertEqual(len(v._redo_stack), 1)
        self._edita(v, 8.0, "Y")          # edició nova → el refer es descarta
        self.assertEqual(len(v._redo_stack), 0)
        self.assertEqual(len(v._undo_stack), 1)
        v.close()

    def test_desfer_amb_pila_buida_no_peta(self):
        v = self._visor()
        ini = _snapshot(v)
        v.undo()
        v.redo()
        self.assertEqual(_snapshot(v), ini)
        v.close()


def _undo_llarg_tearDownModule():
    try:
        import _qt_neteja
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_undo_temps.py
# ══════════════════════════════════════════════════════════════════════════
"""A1: Desfer/Refer també ha de cobrir BPM, compàs, offset, mode i loop A-B.

Abans `Visor._estat_edicio()` només desava `(acords, seccions)`: canviar el BPM
o el loop era **irreversible** (Desfer no hi feia res). Ara la pila del
desfer/refer apila `(acords, seccions, temps)` amb `_estat_complet()`, i els
camins que canvien la graella o el loop hi marquen l'operació.
"""


def _undo_temps___finestra():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "t.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * 30)
    ac = os.path.join(td, "AUTOCHORDS_t")
    os.makedirs(ac)
    with open(os.path.join(ac, "acords.csv"), "w", encoding="utf-8") as f:
        f.write("0.0,4.0,C\n4.0,30.0,Am\n")
    with open(os.path.join(ac, "estructura_ABC.csv"), "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
                "0.00,15.00,15.00,A,A,1,1\n15.00,30.00,15.00,B,B,1,1\n")
    w = app_main.Finestra()
    w.wav_edit.setText(wav)
    w._carrega_visor(wav)
    return w


class _undo_temps___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])


class TestUndoTemps(_undo_temps___Base):
    def test_canviar_el_bpm_es_pot_desfer(self):
        w = _undo_temps___finestra()
        v = w.visor_ref
        self.assertAlmostEqual(float(v.bpm), 120.0, places=3)
        w.bpm.setText("101")
        w._aplica_parametres_temps()
        self.assertAlmostEqual(float(v.bpm), 101.0, places=3)
        w._undo_visor()
        self.assertAlmostEqual(float(v.bpm), 120.0, places=3,
                               msg="el BPM no s'ha desfet")
        # i el camp de la barra queda sincronitzat amb el visor
        self.assertAlmostEqual(float(w.bpm.text()), 120.0, places=3)

    def test_canviar_l_offset_es_pot_desfer(self):
        w = _undo_temps___finestra()
        v = w.visor_ref
        w.offset.setText("1.5")
        w._aplica_parametres_temps()
        self.assertAlmostEqual(float(v.offset), 1.5, places=3)
        w._undo_visor()
        self.assertAlmostEqual(float(v.offset), 0.0, places=3)
        self.assertAlmostEqual(float(w.offset.text()), 0.0, places=3)

    def test_canviar_el_compas_es_pot_desfer(self):
        w = _undo_temps___finestra()
        v = w.visor_ref
        w.bpb.setText("3")
        w._aplica_parametres_temps()
        self.assertEqual(int(v.bpb), 3)
        w._undo_visor()
        self.assertEqual(int(v.bpb), 4)

    def test_posar_el_clip_en_segons_des_de_la_barra(self):
        """Casella «En segons» de la barra → el clip objectiu queda 0/0."""
        w = _undo_temps___finestra()
        v = w.visor_ref
        w.chk_segons.setChecked(True)
        self.assertEqual((int(v.tempo_trams[-1][3]),
                          int(v.tempo_trams[-1][4])), (0, 0))
        self.assertTrue(v.tempo_map.es_lliure(float(v.pos)))
        # I el text del compàs queda en 0/0.
        self.assertEqual(w.bpb.text().strip(), "0/0")
        # Desfer torna a compàs.
        w._undo_visor()
        self.assertNotEqual((int(v.tempo_trams[-1][3]),
                             int(v.tempo_trams[-1][4])), (0, 0))

    def test_bpm_zero_avisa_i_no_aplica_res(self):
        w = _undo_temps___finestra()
        v = w.visor_ref
        abans = [tuple(t) for t in v.tempo_trams]
        w.avis_info = __import__("unittest.mock", fromlist=["Mock"]).Mock()
        w.bpm.setText("0")
        w._aplica_parametres_temps()
        self.assertTrue(w.avis_info.called)
        self.assertEqual([tuple(t) for t in v.tempo_trams], abans)

    def test_activar_el_loop_es_pot_desfer(self):
        w = _undo_temps___finestra()
        v = w.visor_ref
        v.loop_a, v.loop_b = 2.0, 6.0
        v.set_loop(True)
        self.assertTrue(v.loop_on)
        w._undo_visor()
        self.assertFalse(v.loop_on, "l'activació del loop no s'ha desfet")
        self.assertFalse(w.tb_loop.isChecked())

    def test_rang_de_loop_es_pot_desfer(self):
        w = _undo_temps___finestra()
        v = w.visor_ref
        v._on_loop_changed(2.0, 6.0)          # com en acabar d'arrossegar el regle
        self.assertAlmostEqual(v.loop_a, 2.0, places=3)
        w._undo_visor()
        self.assertIsNone(v.loop_a)
        self.assertIsNone(v.loop_b)

    def test_el_desfer_del_model_encara_funciona(self):
        """No regressió + bug trobat: l'alta des del MENÚ no marcava undo."""
        from unittest.mock import patch
        import PyQt5.QtWidgets as QW
        w = _undo_temps___finestra()
        v = w.visor_ref
        n = len(v.acords)
        with patch.object(QW.QInputDialog, "getText", return_value=("G", True)):
            v.ves_a(10.0)
            w._afegeix_acord_ui()
        self.assertEqual(len(v.acords), n + 1)
        w._undo_visor()
        self.assertEqual(len(v.acords), n,
                         "l'alta des del menú no era desfer-able")

    def test_afegir_seccio_des_del_menu_es_desfe(self):
        from unittest.mock import patch
        import PyQt5.QtWidgets as QW
        w = _undo_temps___finestra()
        v = w.visor_ref
        v.seccions = []               # sense res: hi ha espai per afegir-hi
        v.timeline.set_data(v.acords, v.seccions)
        v._undo_commit()              # consolida aquest estat com a base
        with patch.object(QW.QInputDialog, "getText", return_value=("X", True)):
            v.ves_a(10.0)
            w._afegeix_seccio_ui()
        # Regla #4: el carril queda cobert («-» al davant + la secció nova
        # fins al final), no un illot de 2 s.
        self.assertEqual(len(v.seccions), 2)
        self.assertAlmostEqual(float(v.seccions[0][0]), 0.0, places=2)
        self.assertAlmostEqual(float(v.seccions[-1][1]),
                               float(v.audio["durada"]), places=2)
        self.assertIn("X", [s[2] for s in v.seccions])
        w._undo_visor()
        self.assertEqual(len(v.seccions), 0)

    def test_la_descripcio_esmenta_el_canvi_de_temps(self):
        w = _undo_temps___finestra()
        v = w.visor_ref
        abans = v._estat_complet()
        v.bpm = 101.0
        ara = v._estat_complet()
        self.assertIn("BPM", v._descriu_canvi(abans, ara))
        # i el contracte del pont MCP (2-tuple) no ha canviat
        self.assertEqual(len(v._estat_edicio()), 2)


def _undo_temps_tearDownModule():
    # Neteja ORDENADA dels objectes Qt del mòdul (evita destrucció pel GC en un
    # test posterior -> access violation intermitent). Vegeu tests/_qt_neteja.py.
    try:
        import _qt_neteja
    except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_editor_renom.py
# ══════════════════════════════════════════════════════════════════════════
"""Test de regressió: reanomenar una secció (o un acord) des de la franja
EDITOR no ha de fallar pel fet que l'inici es mostri amb 2 decimals.

Bug original: `Visor._aplica_editor` re-escrivia l'inici amb el valor ARRODONIT
que mostra l'editor (2 decimals). Com que una secció acaba EXACTAMENT on comença
la següent, reaplicar 16,63 en lloc de 16,633663 feia que la 2a secció «solapés»
la 1a → l'app rebutjava el canvi («Les seccions no poden solapar-se…») i el nom
de qualsevol secció que no fos la primera no es podia canviar mai.

Arreglament: si l'inici NO s'ha tocat (el valor de l'editor és el mateix dins
l'error d'arrodoniment de 2 decimals), es conserva el valor INTERN de precisió
completa. Mateix criteri per als acords.
"""


def _wav_silenci(segons=40):
    fd, ruta = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * segons)
    return ruta


FRONTERA = 16.633663          # 28 compassos a 101 BPM (precisió interna real)


class TestEditorRenom(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def _visor(self):
        v = visor.Visor(_wav_silenci(), None, None, 101.0, 4, True)
        v.seccions = [(0.0, FRONTERA, "INTRO+RIFF", "A"),
                      (FRONTERA, 31.20, "C", "C")]
        v.timeline.set_data(v.acords, v.seccions)
        return v

    def test_renom_segona_seccio_des_de_leditor(self):
        v = self._visor()
        # l'editor mostra l'inici amb 2 decimals (com fa _actualitza_editor)
        v._ed_kind, v._ed_idx = "section", 1
        v.ed_nom.setText("NOU NOM")
        v.ed_fam.setText("C")
        v.ed_ini.setText(f"{FRONTERA:.2f}")      # -> "16.63"
        v.ed_cb.setText("8.1")
        v._aplica_editor()
        self.assertEqual(v.seccions[1][2], "NOU NOM",
                         "no s'ha pogut reanomenar la 2a secció")
        self.assertAlmostEqual(v.seccions[1][0], FRONTERA, places=5,
                               msg="l'inici s'ha arrodonit (pèrdua de precisió)")
        self.assertEqual(len(v.seccions), 2, "ha canviat el nombre de seccions")
        self.assertEqual(v.seccions[0][2], "INTRO+RIFF",
                         "la 1a secció no s'havia de tocar")

    def test_renom_segona_seccio_amb_inici_mogut_de_veritat(self):
        """Si l'inici SÍ que es canvia, s'ha de fer cas del valor nou."""
        v = self._visor()
        v._ed_kind, v._ed_idx = "section", 1
        v.ed_nom.setText("C")
        v.ed_fam.setText("C")
        v.ed_ini.setText("17.50")                # mogut de debò
        v.ed_cb.setText("")
        v._aplica_editor()
        self.assertAlmostEqual(v.seccions[1][0], 17.50, places=5,
                               msg="no s'ha aplicat l'inici nou")

    def test_renom_acord_proper_al_vei(self):
        v = self._visor()
        # El model duu la «N» de capçalera a 0 (regla d'or #4: els clips
        # cobreixen TOTA la WAV); el parell 7.13/7.144567 és el que prova
        # l'arrodoniment de l'editor. Han de distar >= 1 ms (resolució del
        # CSV): abans eren 7.13/7.134567 (4,6 ms) i arrodonien a la MATEIXA
        # fila «7.13» → col·lisió que el bug #5 ara rebutja.
        v.acords = v._valida_canvis_acords([
            (0.0, "N", "0.000000000"),
            (7.13, "A", "7.130000000"),
            (7.144567, "E-7", "7.144567000")])
        v.timeline.set_data(v.acords, v.seccions)
        v._ed_kind, v._ed_idx = "chord", 2
        v.ed_nom.setText("E7")
        v.ed_ini.setText("7.14")                 # arrodonit del valor real
        v._aplica_editor()
        self.assertEqual(v.acords[2][2][0], "E7",
                         "no s'ha pogut reanomenar l'acord")
        self.assertAlmostEqual(float(v.acords[2][0]), 7.144567, places=5)


def _editor_renom_tearDownModule():
    # Neteja ORDENADA dels objectes Qt del mòdul (evita destrucció pel GC en un
    # test posterior -> access violation intermitent). Vegeu tests/_qt_neteja.py.
    try:
        import _qt_neteja
    except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_editor_feedback.py
# ══════════════════════════════════════════════════════════════════════════
"""L'editor de la franja Editor NO pot fallar en silenci (OC-6/394).

Sis camins de `_aplica_editor` tornaven sense aplicar RES i sense dir res: el
botó «Aplica» semblava mort (CSV intacte, cap 'editor:' al log). Ara tots els
camins que no apliquen donen feedback visible (`avis_editor` → log + caixa
d'informació).
"""


def _editor_feedback___visor():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "t.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * 20)
    s = pipeline.carpeta_sortida(wav)
    os.makedirs(s, exist_ok=True)
    ca = os.path.join(s, "acords.csv")
    with open(ca, "w", encoding="utf-8") as f:
        f.write("0.0,4.0,C\n4.0,20.0,Am\n")
    sa = os.path.join(s, "estructura_ABC.csv")
    with open(sa, "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
                "0.00,10.00,10.00,A,A,1,1\n10.00,20.00,10.00,B,B,1,1\n")
    v = visor_mod.Visor(wav, ca, sa, 120.0, 4, True)
    v._missatges = []
    v.infoMissatge.connect(v._missatges.append)
    return v


class TestEditorFeedback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])

    def test_sense_seleccio_avisa(self):
        v = _editor_feedback___visor()
        v._ed_kind, v._ed_idx = None, -1
        v._aplica_editor()
        self.assertTrue(any("Selecciona" in m for m in v._missatges),
                        f"hauria d'avisar: {v._missatges}")

    def test_inici_no_numeric_avisa(self):
        v = _editor_feedback___visor()
        v._ed_kind, v._ed_idx = "chord", 1
        v.ed_ini.setText("abc")
        v.ed_nom.setText("Am")
        v._aplica_editor()
        self.assertTrue(any("número" in m for m in v._missatges),
                        f"hauria d'avisar: {v._missatges}")
        self.assertEqual(v.acords[1][2][0], "Am", "no s'ha d'haver aplicat res")

    def test_nom_buit_avisa(self):
        v = _editor_feedback___visor()
        v._ed_kind, v._ed_idx = "chord", 1
        v.ed_ini.setText("4.0")
        v.ed_nom.setText("   ")
        v._aplica_editor()
        self.assertTrue(any("nom" in m for m in v._missatges))

    def test_index_esborrat_avisa(self):
        v = _editor_feedback___visor()
        v._ed_kind, v._ed_idx = "section", 99
        v.ed_ini.setText("4.0")
        v.ed_nom.setText("X")
        v._aplica_editor()
        self.assertTrue(any("no existeix" in m for m in v._missatges))

    def test_validacio_que_falla_es_visible(self):
        """Un canvi que trenca la lògica temporal s'ha de VEURE, no només al log."""
        v = _editor_feedback___visor()
        v._ed_kind, v._ed_idx = "chord", 1
        v.ed_nom.setText("Am")
        v.ed_ini.setText("0.0")          # xocaria amb el 1r acord (t=0)
        v._aplica_editor()
        self.assertTrue(any("invalid" in m for m in v._missatges),
                        f"hauria d'avisar: {v._missatges}")

    def test_el_cami_bon_aplica_i_no_avisa(self):
        v = _editor_feedback___visor()
        v._ed_kind, v._ed_idx = "chord", 1
        v.ed_nom.setText("Gmaj7")
        v.ed_ini.setText("4.00")
        v._aplica_editor()
        self.assertEqual(v.acords[1][2][0], "GMaj7", "hauria d'haver aplicat")
        self.assertEqual(v._missatges, [], "el camí bo no ha d'avisar")


def _editor_feedback_tearDownModule():
    # Neteja ORDENADA dels objectes Qt del mòdul (evita destrucció pel GC en un
    # test posterior -> access violation intermitent). Vegeu tests/_qt_neteja.py.
    try:
        import _qt_neteja
    except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_eina_marc.py
# ══════════════════════════════════════════════════════════════════════════
"""Eina del timeline: «intel·ligent» (per defecte) o «marc» (rubber-band).

- Per defecte l'eina és la intel·ligent i el rang de `Shift+clic` es queda al
  **carril del clip clicat**: la «selecció creuada» (les dues pistes) és una
  opció de menú, **desactivada** per defecte.
- Amb l'eina «marc», arrossegar **no mou cap clip**: dibuixa un rectangle i, en
  deixar anar, queda seleccionat tot el que **HI SONA** a dins (solapament, no
  només els inicis) i només de les pistes que el rectangle cobreix verticalment.
- El rectangle es veu només durant l'arrossegament (després desapareix) i la
  selecció no entra a la pila de desfer.

Convencions dels DAWs (Cubase `Snap Type`, marquee de Logic/Reaper) i decisió
de l'operador del 16-10-2026: «eina intel·ligent o mode només selecció amb
marquee; el creuat, desactivat per defecte».
"""


# acords: 0 C · 2 Am · 4.5 F · 7 G · 10 C (fins a 20)   |   seccions: A 0-5 · B 5-10 · C 10-20
_eina_marc__ACORDS = "0.0,2.0,C\n2.0,4.5,Am\n4.5,7.0,F\n7.0,10.0,G\n10.0,20.0,C\n"
_eina_marc__SECCIONS = ("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
            "0.0,5.0,5.0,A,A,1.1,5.1\n"
            "5.0,10.0,5.0,B,B,5.1,10.1\n"
            "10.0,20.0,10.0,C,C,10.1,20.1\n")


def _eina_marc___visor():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "tema.wav")
    out = os.path.join(td, "AUTOCHORDS_tema")
    os.makedirs(out)
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * 20)
    ca = os.path.join(out, "acords.csv")
    sa = os.path.join(out, "estructura_ABC.csv")
    with open(ca, "w", encoding="utf-8") as f:
        f.write(_eina_marc__ACORDS)
    with open(sa, "w", encoding="utf-8") as f:
        f.write(_eina_marc__SECCIONS)
    v = visor_mod.Visor(wav, ca, sa, bpm=120, bpb=4, tempo_fix=False)
    v.td, v.sortida = td, out
    return v


def _x_vista(tl, t):
    """Coordenada X de VISTA del temps `t` (amb la vista actual)."""
    x_esc = tl._x_offset + (float(t) - tl._view_left) * tl._pps
    return float(tl.mapFromScene(QPointF(x_esc, 0.0)).x())


def _y_vista(tl, y_esc):
    """Coordenada Y de VISTA d'una alçada d'ESCENA."""
    return float(tl.mapFromScene(QPointF(0.0, float(y_esc))).y())


def _ev(tipus, x, y, button=Qt.LeftButton):
    return QMouseEvent(tipus, QPointF(float(x), float(y)), button, button,
                       Qt.NoModifier)


def _marca(tl, t0, t1, y_esc0=None, y_esc1=None):
    """Simula un arrossegament de marc entre dos temps i dues alçades.

    Per defecte cobreix les DUES pistes (de la secció de dalt a la d'acords).
    """
    if y_esc0 is None:
        y_esc0 = LANE_SEC_TOP + LANE_H / 2.0
    if y_esc1 is None:
        y_esc1 = LANE_ACC_TOP + LANE_H / 2.0
    x0, y0 = _x_vista(tl, t0), _y_vista(tl, y_esc0)
    x1, y1 = _x_vista(tl, t1), _y_vista(tl, y_esc1)
    tl.mousePressEvent(_ev(QEvent.MouseButtonPress, x0, y0))
    tl.mouseMoveEvent(_ev(QEvent.MouseMove, x1, y1))
    tl.mouseReleaseEvent(_ev(QEvent.MouseButtonRelease, x1, y1))


class _eina_marc___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])


class TestEinaPerDefecte(_eina_marc___Base):
    def test_eina_intel_ligent_per_defecte(self):
        v = _eina_marc___visor()
        self.assertEqual(v.timeline.tool(), "intel·ligent")
        v.close()

    def test_rang_d_acords_no_toca_les_seccions(self):
        v = _eina_marc___visor()
        v.timeline.select_clip("chord", 0)          # àncora
        v.timeline.extend_selection("chord", 2)     # Shift+clic a «F»
        # només acords: el carril de la secció NO s'hi ha de colar
        self.assertEqual(v.timeline.selected_keys(),
                         {("chord", 0), ("chord", 1), ("chord", 2)})
        v.close()

    def test_rang_de_seccions_no_toca_els_acords(self):
        v = _eina_marc___visor()
        v.timeline.select_clip("section", 0)
        v.timeline.extend_selection("section", 1)
        self.assertEqual(v.timeline.selected_keys(),
                         {("section", 0), ("section", 1)})
        v.close()

class TestMarcSeleccio(_eina_marc___Base):
    def test_marc_agafa_el_que_sona_i_no_el_que_nomes_toca(self):
        v = _eina_marc___visor()
        v.timeline.set_tool("marc")
        _marca(v.timeline, 5.0, 6.0)                # cobreix les dues pistes
        # F comença a 4.5 (ABANS del marc) però hi sona → hi entra
        # A acaba exactament a 5.0 → només la toca → NO hi entra
        self.assertEqual(v.timeline.selected_keys(),
                         {("chord", 2), ("section", 1)})
        v.close()

    def test_marc_nomes_sobre_la_pista_d_acords(self):
        v = _eina_marc___visor()
        v.timeline.set_tool("marc")
        # rectangle només damunt la pista d'acords (l'alçada decideix les pistes)
        _marca(v.timeline, 5.0, 6.0,
               y_esc0=LANE_ACC_TOP + 2, y_esc1=LANE_ACC_TOP + LANE_H - 2)
        self.assertEqual(v.timeline.selected_keys(), {("chord", 2)})
        v.close()

    def test_marc_nomes_sobre_la_pista_de_seccions(self):
        v = _eina_marc___visor()
        v.timeline.set_tool("marc")
        _marca(v.timeline, 5.0, 6.0,
               y_esc0=LANE_SEC_TOP + 2, y_esc1=LANE_SEC_TOP + LANE_H - 2)
        self.assertEqual(v.timeline.selected_keys(), {("section", 1)})
        v.close()

    def test_amb_eina_marc_arrossegar_no_mou_el_clip(self):
        v = _eina_marc___visor()
        abans = [round(float(a[0]), 6) for a in v.acords]
        v.timeline.set_tool("marc")
        # arrossegar DES DE DAMUNT del clip «F» (4.5) fins a 6.0
        _marca(v.timeline, 4.5, 6.0,
               y_esc0=LANE_ACC_TOP + LANE_H / 2.0,
               y_esc1=LANE_ACC_TOP + LANE_H - 2)
        self.assertEqual([round(float(a[0]), 6) for a in v.acords], abans)
        self.assertIn(("chord", 2), v.timeline.selected_keys())
        v.close()

    def test_el_rectangle_desapareix_en_deixar_anar(self):
        v = _eina_marc___visor()
        v.timeline.set_tool("marc")
        x0 = _x_vista(v.timeline, 5.0)
        y0 = _y_vista(v.timeline, LANE_ACC_TOP + LANE_H / 2.0)
        v.timeline.mousePressEvent(_ev(QEvent.MouseButtonPress, x0, y0))
        self.assertIsNotNone(v.timeline._marquee)   # mentre s'arrossega, hi és
        v.timeline.mouseReleaseEvent(_ev(QEvent.MouseButtonRelease, x0, y0))
        self.assertIsNone(v.timeline._marquee)      # en deixar anar, fora
        v.close()

    def test_arrossegament_minuscle_es_un_clic(self):
        v = _eina_marc___visor()
        v.timeline.set_tool("marc")
        v.timeline.select_clip("chord", 1)          # selecció prèvia
        x = _x_vista(v.timeline, 8.0)
        y = _y_vista(v.timeline, LANE_ACC_TOP + LANE_H / 2.0)
        v.timeline.mousePressEvent(_ev(QEvent.MouseButtonPress, x, y))
        v.timeline.mouseReleaseEvent(_ev(QEvent.MouseButtonRelease, x, y))
        self.assertEqual(v.timeline.selected_keys(), set())      # buidada
        self.assertAlmostEqual(v.timeline._pos_t, 8.0, places=2)  # cursor mogut
        v.close()

    def test_el_marc_no_entra_a_desfer(self):
        v = _eina_marc___visor()
        n = len(v._undo_stack)
        v.timeline.set_tool("marc")
        _marca(v.timeline, 5.0, 6.0)
        self.assertEqual(len(v._undo_stack), n)
        v.close()

    def test_tornar_a_intel_ligent_desactiva_el_marc(self):
        v = _eina_marc___visor()
        v.timeline.set_tool("marc")
        _marca(v.timeline, 5.0, 6.0)
        v.timeline.set_tool("intel·ligent")
        # amb la fletxa, un drag damunt d'un clip TORNA a moure'l
        v.timeline.select_clip("chord", 2)
        abans = round(float(v.acords[2][0]), 6)
        item = v.timeline._chord_by_idx.get(2)
        if item is not None:                        # el drag el gestiona l'item
            self.assertTrue(v.timeline._marquee is None)
        self.assertEqual(round(float(v.acords[2][0]), 6), abans)
        v.close()


class TestEinaTemporalCtrlShift(_eina_marc___Base):
    """Ctrl+Shift mantingut = eina «marc»; en deixar anar, torna a l'anterior."""

    def _press(self, tl, key, mods):
        tl.keyPressEvent(QKeyEvent(QEvent.KeyPress, key, mods))

    def _release(self, tl, key, mods):
        tl.keyReleaseEvent(QKeyEvent(QEvent.KeyRelease, key, mods))

    def test_ctrl_shift_activa_i_restaura_intelligent(self):
        v = _eina_marc___visor()
        tl = v.timeline
        self._press(tl, Qt.Key_Control, Qt.ControlModifier)
        self._press(tl, Qt.Key_Shift,
                    Qt.ControlModifier | Qt.ShiftModifier)
        self.assertEqual(tl.tool(), "marc")
        self._release(tl, Qt.Key_Shift, Qt.ControlModifier)
        self.assertEqual(tl.tool(), "intel·ligent")
        v.close()

    def test_restaura_l_eina_fixa_que_hi_havia(self):
        v = _eina_marc___visor()
        tl = v.timeline
        tl.set_tool("marc")
        self._press(tl, Qt.Key_Shift, Qt.ShiftModifier)
        self._press(tl, Qt.Key_Control,
                    Qt.ControlModifier | Qt.ShiftModifier)
        self.assertEqual(tl.tool(), "marc")
        self._release(tl, Qt.Key_Control, Qt.ShiftModifier)
        self.assertEqual(tl.tool(), "marc")
        v.close()


class TestEscape(_eina_marc___Base):
    """`Esc`, per ordre: (1) anul·la el RANG en curs, (2) anul·la el LOOP a mig
    marcar, (3) desactiva el LOOP, (4) buida la SELECCIÓ. Si no es compleix cap
    d'aquestes, no fa res (ni toca el loop ni la selecció)."""

    @staticmethod
    def _esc(tl):
        from PyQt5.QtCore import QEvent
        from PyQt5.QtGui import QKeyEvent
        tl.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Escape,
                                   Qt.NoModifier))

    def test_ordre_de_prioritats(self):
        v = _eina_marc___visor()
        tl = v.timeline
        # (1) RANG en curs
        tl.set_tool("marc")
        x, y = _x_vista(tl, 5.0), _y_vista(tl, LANE_ACC_TOP + 2)
        tl.mousePressEvent(_ev(QEvent.MouseButtonPress, x, y))
        self.assertIsNotNone(tl._marquee)
        self._esc(tl)
        self.assertIsNone(tl._marquee)
        # (3) LOOP actiu → es desactiva (cal que el VISOR tingui A i B:
        # és ell qui mana el playback, i els rep pel senyal `loopChanged`)
        tl.loopChanged.emit(1.0, 3.0)
        v.set_loop(True)
        self.assertTrue(v.loop_on)
        self._esc(tl)
        self.assertFalse(v.loop_on)
        # (4) SELECCIÓ → es buida
        tl.select_clip("chord", 1)
        self.assertTrue(tl.selected_keys())
        self._esc(tl)
        self.assertEqual(tl.selected_keys(), set())
        v.close()

    def test_loop_a_mig_marcar_es_descarta(self):
        v = _eina_marc___visor()
        tl = v.timeline
        tl._loop_a, tl._loop_b = 2.0, 4.0      # loop previ
        tl._loop_a0, tl._loop_b0 = 2.0, 4.0
        tl._loop_drag = True                   # ...i n'estem marcant un altre
        tl._loop_a, tl._loop_b = 2.0, 7.0
        self._esc(tl)
        self.assertFalse(tl._loop_drag)
        self.assertEqual((tl._loop_a, tl._loop_b), (2.0, 4.0))   # com era
        v.close()

    def test_loop_marcat_es_treu(self):
        """Amb el loop marcat (encara que estigui aturat), Esc ha de fer fora
        la caixa groga: si no, quedaria pintada i semblaria que el loop hi és."""
        v = _eina_marc___visor()
        tl = v.timeline
        # marcat al regle (el timeline guarda A/B; el senyal només va cap al visor)
        tl._loop_a, tl._loop_b = 2.0, 4.0
        tl._update_loop_item()
        tl.loopChanged.emit(2.0, 4.0)
        self._esc(tl)
        self.assertIsNone(tl._loop_a)
        self.assertIsNone(tl._loop_b)
        self.assertFalse(getattr(v, "loop_on", False))
        v.close()

    def test_sense_res_no_toca_la_seleccio(self):
        v = _eina_marc___visor()
        tl = v.timeline
        self._esc(tl)                          # res a fer
        self.assertEqual(tl.selected_keys(), set())
        self.assertIsNone(tl._loop_a)
        self.assertFalse(getattr(v, "loop_on", False))
        v.close()


class TestDreceraEina(_eina_marc___Base):
    """La tecla `E` commuta l'eina (TOGGLE, no on/off) i per defecte sempre
    s'arrenca en «intel·ligent»."""

    def test_e_es_un_toggle(self):
        from app import main as app_main
        w = app_main.Finestra()
        try:
            self.assertFalse(w.b_eina.isChecked())   # defecte: intel·ligent
            self.assertEqual(w.b_eina.text(), "Eina: intel·ligent")
            w._toggle_eina_tecla()
            self.assertTrue(w.b_eina.isChecked())    # 1a → marc
            self.assertEqual(w.b_eina.text(), "Eina: selecció")
            w._toggle_eina_tecla()
            self.assertFalse(w.b_eina.isChecked())   # 2a → intel·ligent
            self.assertEqual(w.b_eina.text(), "Eina: intel·ligent")
        finally:
            w.close()


def _eina_marc_tearDownModule():
    try:
        import _qt_neteja
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_sense_analisi.py
# ══════════════════════════════════════════════════════════════════════════
"""Roadmap §14.1 — treballar SENSE analitzar (edició total per l'usuari).

En carregar un àudio **sense anàlisi**, el model ha de néixer amb **1 clip
d'acords** i **1 d'estructura** que cobreixen tota la cançó: el punt de partida
editable (partir/afegir/moure/renombrar). L'anàlisi (Chordino/qm) passa a ser
**opcional**, mai un requisit previ.

A vigilar: regla d'or **#4** (cobertura total) i que, sense anàlisi, **no** cal
la capa crua (`analisi/`).
"""


_VIVES = []


def _sense_analisi___wav(dur=12.0):
    td = tempfile.mkdtemp()
    ruta = os.path.join(td, "t.wav")
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * int(44100 * dur))
    return ruta


class _sense_analisi___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = app_main.QApplication.instance() or app_main.QApplication([])

    def _finestra_amb_projecte(self, amb_csv=False):
        wav = _sense_analisi___wav()
        p = projecte.Projecte.crea(os.path.join(os.path.dirname(wav), "P"),
                                   wav, bpm=120.0)
        if amb_csv:
            with open(p.ruta_csv_acords(), "w", encoding="utf-8") as f:
                f.write("0.0,4.0,C\n4.0,4.0,G\n")
            with open(os.path.join(p.carpeta, "estructura_ABC.csv"), "w",
                      encoding="utf-8") as f:
                f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,"
                        "compas_fi\n0.0,12.0,12.0,A,A,1.1,5.1\n")
        w = app_main.Finestra()
        _VIVES.append(w)
        w.avisa_info = lambda *a, **k: None
        w.avisa = lambda *a, **k: None
        w._activa_projecte(projecte.Projecte.obre(p.ruta_acproj))
        return w, p

    def tearDown(self):
        ws, _VIVES[:] = _VIVES[:], []
        for w in ws:
            w.dirty = False
        try:
            import _qt_neteja
        except ImportError:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import _qt_neteja
        _qt_neteja.tanca_i_destrueix(*ws)


class TestSenseAnalisi(_sense_analisi___Base):
    def test_mapa_tempo_compas(self):
        """Fase 4: `aplica_tempo_trams` (des del diàleg) actualitza el model,
        el mapa i el disc."""
        w, p = self._finestra_amb_projecte()
        vr = w.visor_ref
        self.assertTrue(vr.aplica_tempo_trams(
            [(0.0, 2.0, 120.0, 4, 4), (2.0, 4.0, 90.0, 3, 4)]))
        self.assertEqual(len(vr.tempo_trams), 2)
        self.assertEqual(vr.tempo_map.label(0.0), "1.1.1")
        self.assertEqual(vr.tempo_map.signatura(3.0), (3, 4))
        tempo = pipeline.llegeix_tempo_csv(os.path.join(p.carpeta, "tempo.csv"))
        self.assertEqual(len(tempo), 2)
        self.assertAlmostEqual(float(tempo[1][2]), 90.0)

    def test_mou_la_frontera_del_mapa(self):
        """Fase 4b: arrossegar una vora de la pista de BPM/compàs mou on canvia."""
        w, p = self._finestra_amb_projecte()
        vr = w.visor_ref
        vr.aplica_tempo_trams([(0.0, 4.0, 120.0, 4, 4), (4.0, 8.0, 90.0, 3, 4)])
        vr._on_tempo_mogut(1, "ini", 6.0)          # frontera 4 s -> 6 s
        self.assertAlmostEqual(float(vr.tempo_trams[1][0]), 6.0, places=2)
        self.assertAlmostEqual(float(vr.tempo_trams[0][1]), 6.0, places=2)
        # Re-tempo (21-10-2026): la frontera segueix el ratolí TAL QUAL (3 s ja
        # no s'imanta a 2 s); N=2 a l'esquerre → 80 BPM en 6 s, i el tram dret
        # no es mou del seu lloc (acaba a 8 s).
        self.assertAlmostEqual(float(vr.tempo_trams[0][2]), 80.0, places=3)
        fi_dret = float(vr.tempo_trams[1][1])      # el final no s'ha de moure
        vr._on_tempo_mogut(0, "fi", 3.0)           # frontera 6 s -> 3 s
        self.assertAlmostEqual(float(vr.tempo_trams[1][0]), 3.0, places=2)
        self.assertAlmostEqual(float(vr.tempo_trams[1][1]), fi_dret, places=3)
        self.assertEqual(vr.tempo_map.signatura(4.0), (3, 4))

    def test_audio_nou_neix_amb_1_acord_i_1_seccio(self):
        w, _p = self._finestra_amb_projecte(amb_csv=False)
        vr = w.visor_ref
        self.assertEqual(len(vr.acords), 1, "1 clip d'acords")
        self.assertEqual(len(vr.seccions), 1, "1 clip d'estructura")
        self.assertEqual(vr.acords[0][2][0], "N")
        self.assertEqual(vr.seccions[0][2], "A")

    def test_cobertura_total(self):
        """Regla d'or #4: el clip únic ha de cobrir TOTA la durada."""
        w, _p = self._finestra_amb_projecte(amb_csv=False)
        vr = w.visor_ref
        dur = float(vr.audio["durada"])
        self.assertAlmostEqual(float(vr.acords[0][0]), 0.0, places=6)
        self.assertAlmostEqual(float(vr.seccions[0][0]), 0.0, places=6)
        self.assertAlmostEqual(float(vr.seccions[0][1]), dur, places=3)

    def test_export_habilitat_i_csvs_desats(self):
        w, p = self._finestra_amb_projecte(amb_csv=False)
        self.assertTrue(w.b_export.isEnabled(), "es pot exportar sense analitzar")
        self.assertTrue(w.b_export_part.isEnabled())
        for nom in ("acords.csv", "estructura_ABC.csv", "tempo.csv",
                    "compas.csv"):
            self.assertTrue(os.path.isfile(os.path.join(p.carpeta, nom)), nom)

    def test_sense_analisi_no_cal_la_capa_crua(self):
        _w, p = self._finestra_amb_projecte(amb_csv=False)
        self.assertFalse(os.path.isdir(os.path.join(p.carpeta, "analisi")),
                         "sense anàlisi no s'ha de crear analisi/")

    def test_es_editable_a_ma(self):
        """El punt de partida és editable: afegir un acord manté la cobertura."""
        w, _p = self._finestra_amb_projecte(amb_csv=False)
        vr = w.visor_ref
        self.assertTrue(vr._afegeix_acord(6.0, "C"))
        noms = [a[2][0] for a in vr.acords]
        self.assertIn("C", noms)
        vr._normalitza_cobertura()      # (no cal que canviï res)
        self.assertEqual(float(vr.acords[0][0]), 0.0)      # el 1r a 0
        self.assertAlmostEqual(float(vr.seccions[0][1]),
                               float(vr.audio["durada"]), places=3)

    def test_amb_csvs_no_es_toca(self):
        """Un projecte que JA té model (anàlisi feta) no s'ha de modificar."""
        w, _p = self._finestra_amb_projecte(amb_csv=True)
        vr = w.visor_ref
        self.assertEqual([a[2][0] for a in vr.acords], ["C", "G"])
        self.assertEqual(len(vr.seccions), 1)


class TestModelInicial(unittest.TestCase):
    def test_helper(self):
        ac, sec = pipeline.model_inicial(7.5)
        self.assertEqual(ac, [pipeline.Clip(0.0, 7.5, ("N", "0.000000000"))])
        self.assertEqual(sec, [(0.0, 7.5, "A", "A")])

    def test_durada_zero_no_peta(self):
        ac, sec = pipeline.model_inicial(0)
        self.assertEqual(ac[0][0], 0.0)
        self.assertEqual(sec[0][1], 0.0)


def _sense_analisi_tearDownModule():
    try:
        import _qt_neteja
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_edicio_operacions_doc.py
# ══════════════════════════════════════════════════════════════════════════
"""La taula única d'operacions d'edició (`docs/EDICIO_OPERACIONS.md`) no pot
quedar-se enrere: ha de llistar **totes** les eines `ac_*` del pont i cap
d'inventada.

És el document que creua GUI ↔ MCP ↔ paritat #11 (§2 del pla d'edició lliure).
"""


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, "docs", "EDICIO_OPERACIONS.md")


class TestDocEdicioOperacions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DOC, encoding="utf-8") as f:
            cls.text = f.read()


    def test_la_taula_diu_gui_i_pistes(self):
        """Cada fila ha de dir com es fa per GUI i si val per a cada pista
        (paritat d'edició #11)."""
        for capçalera in ("| GUI", "| Acords |", "| Estr. |"):
            self.assertIn(capçalera, self.text)

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_dreceres_completes.py
# ══════════════════════════════════════════════════════════════════════════
"""A3: el diàleg «Ajuda ▸ Dreceres de teclat» ha de llistar TOTES les reals.

Abans en llistava **6** (Espai, Ctrl+Z/Y/Shift+Z, roda, botó dret, regle, clic) i
en faltaven moltes d'actives (Ctrl+O/E, F5, Ctrl+D, Del, F2, Ctrl+C/X/V,
Ctrl+`[`/`]`, Ctrl+0/±…). Ara les de **menú** es dedueixen dels menús REALS i les
que no hi són (teclat del visor i ratolí) van llistades a part.
"""


def _dreceres_completes___finestra():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "t.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * 5)
    w = app_main.Finestra()
    w.wav_edit.setText(wav)
    w._carrega_visor(wav)
    return w


class TestDreceresCompletes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = app_main.QApplication.instance() or app_main.QApplication([])

    def test_totes_les_dreceres_de_menu_hi_surten(self):
        """El test mecànic: cap acció de menú amb drecera pot quedar fora."""
        w = _dreceres_completes___finestra()
        text = w._text_dreceres()
        faltes = []
        for accio in w.menuBar().actions():
            menu = accio.menu()
            if menu is None:
                continue
            for a in menu.actions():
                if a.isSeparator() or a.menu() is not None:
                    continue
                d = a.shortcut().toString()
                if d and d not in text:
                    faltes.append(f"{a.text().replace('&', '')} ({d})")
        self.assertEqual(faltes, [],
                         f"dreceres de menú que NO surten al diàleg: {faltes}")

    def test_hi_son_les_que_no_son_de_menu(self):
        w = _dreceres_completes___finestra()
        text = w._text_dreceres()
        for d in ("Espai", "T", "Ctrl+C", "Ctrl+X", "Ctrl+V",
                  "Roda del ratolí", "Botó dret"):
            self.assertIn(d, text, f"falta la drecera «{d}»")

    def test_les_dreceres_abans_faltaven(self):
        """Les que el diàleg antic no llistava (regressió explícita)."""
        w = _dreceres_completes___finestra()
        text = w._text_dreceres()
        for d in ("Ctrl+O", "Ctrl+E", "F5", "Ctrl+D", "Del", "F2",
                  "Ctrl+[", "Ctrl+]"):
            self.assertIn(d, text, f"encara falta «{d}»")


    def test_el_dialeg_no_peta(self):
        from unittest.mock import patch
        import PyQt5.QtWidgets as QW
        w = _dreceres_completes___finestra()
        with patch.object(QW.QMessageBox, "information", return_value=None) as m:
            w._mostra_dreceres()
        self.assertTrue(m.called)


def _dreceres_completes_tearDownModule():
    # Neteja ORDENADA dels objectes Qt del mòdul (evita destrucció pel GC en un
    # test posterior -> access violation intermitent). Vegeu tests/_qt_neteja.py.
    try:
        import _qt_neteja
    except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()


if __name__ == "__main__":   # pragma: no cover
    unittest.main()


class TestLlistaTempo(_undo_temps___Base):
    """La tercera llista (clips de tempo/compàs): taula + franja Editor."""

    def _prepara(self):
        w = _undo_temps___finestra()
        v = w.visor_ref
        v.tempo_trams = [(0.0, 10.0, 120.0, 4, 4), (10.0, 30.0, 100.0, 0, 0)]
        v._actualitza_temps()
        return w, v

    def test_una_fila_per_tram_amb_les_quatre_columnes(self):
        _w, v = self._prepara()
        t = v.llista_tempo
        self.assertEqual(t.rowCount(), 2)
        self.assertEqual([t.horizontalHeaderItem(c).text()
                          for c in range(4)],
                         ["Inici (s)", "Fi (s)", "BPM", "Compàs"])
        self.assertEqual(t.item(0, 0).text(), "0.000")
        self.assertEqual(t.item(0, 1).text(), "10.000")
        self.assertEqual(t.item(0, 2).text(), "120.000")
        self.assertEqual(t.item(0, 3).text(), "4/4")
        self.assertEqual(t.item(1, 3).text(), "segons")

    def test_clic_selecciona_el_clip_i_hi_porta_el_cursor(self):
        _w, v = self._prepara()
        v._salt_tempo(v.llista_tempo.item(1, 0))
        self.assertIn(("tempo", 1), v.timeline.selected_keys())
        self.assertAlmostEqual(float(v.pos), 10.0, places=6)

    def test_doble_clic_omple_la_franja_editor(self):
        _w, v = self._prepara()
        v.llista_tempo.setCurrentCell(1, 0)
        v._focus_editor("tempo", 1)
        self.assertEqual((v._ed_kind, v._ed_idx), ("tempo", 1))
        self.assertEqual(v.ed_nom_lbl.text(), "BPM:")
        self.assertEqual(v.ed_fam_lbl.text(), "Compàs:")
        self.assertEqual(v.ed_nom.text(), "100.000")
        self.assertEqual(v.ed_fam.text(), "0/0")
        self.assertEqual(v.ed_ini.text(), "10.000")
        self.assertFalse(v.ed_ini.isEnabled())

    def test_aplicar_des_de_l_editor_canvia_bpm_i_compas(self):
        _w, v = self._prepara()
        v._focus_editor("tempo", 1)
        v.ed_nom.setText("96")
        v.ed_fam.setText("3/4")
        v._aplica_editor()
        self.assertEqual((int(v.tempo_trams[1][3]),
                          int(v.tempo_trams[1][4])), (3, 4))
        self.assertAlmostEqual(float(v.tempo_trams[1][2]), 96.0, places=6)
        self.assertAlmostEqual(float(v.tempo_trams[1][0]), 10.0, places=6)
        self.assertAlmostEqual(float(v.tempo_trams[1][1]), 30.0, places=6)
        # La llista s'ha refrescat i la franja mostra el valor aplicat.
        self.assertEqual(v.llista_tempo.item(1, 3).text(), "3/4")
        self.assertEqual(v.ed_fam.text(), "3/4")

    def test_aplicar_zero_zero_el_deixa_en_segons(self):
        _w, v = self._prepara()
        v._focus_editor("tempo", 0)
        v.ed_fam.setText("0/0")
        v._aplica_editor()
        self.assertEqual((int(v.tempo_trams[0][3]),
                          int(v.tempo_trams[0][4])), (0, 0))
        self.assertTrue(v.tempo_map.es_lliure(1.0))
        self.assertEqual(v.llista_tempo.item(0, 3).text(), "segons")

    def test_compas_invalid_avisa_i_no_toca_res(self):
        _w, v = self._prepara()
        abans = list(v.tempo_trams)
        avisos = []
        v.avis_editor = lambda txt: avisos.append(txt)
        v._focus_editor("tempo", 0)
        v.ed_fam.setText("4/xx")
        v._aplica_editor()
        self.assertEqual(v.tempo_trams, abans)
        self.assertTrue(avisos and "compàs" in avisos[-1].lower())
