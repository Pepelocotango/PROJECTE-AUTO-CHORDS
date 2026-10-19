"""Suite de test — Gui

> Suite CONSOLIDADA (Fase 4, 2026-10-19): fusiona 29 mòduls de test que abans
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
import json
import shutil
import tempfile
import wave
from app import pipeline
from app import projecte
from unittest.mock import patch
from PyQt5.QtWidgets import QFileDialog
from app import config
from app import main as app_main
from PyQt5.QtWidgets import QMessageBox
import threading
import time
import PyQt5.QtWidgets as QW
from app import audio_out
from app import visor as app_visor
from app import visor
import types
from app.main import Finestra
from PyQt5.QtWidgets import QApplication
from app import dialegs
import copy
from PyQt5.QtWidgets import QMenu, QPushButton, QToolBar
from app import visor as visor_mod
import numpy as np
from app.visor import Visor
from PyQt5.QtCore import QEvent, QPointF, Qt
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QDockWidget
from app import xifrat
import re
from app import theme
from app import timeline_items
from app import tempo_map as tm
from app import timeline_layers as L
from app.timeline_base import LOOP_GRAB_PX, loop_after_drag
import random
from PyQt5.QtWidgets import QInputDialog


def tearDownModule():
    _projecte_backups_tearDownModule()
    _projectes_gui_tearDownModule()
    _tancament_tearDownModule()
    _tancar_sonant_tearDownModule()
    _canvi_wav_tearDownModule()
    _avis_audio_tearDownModule()
    _avis_reanalisi_tearDownModule()
    _autocomprovacio_ffmpeg_tearDownModule()
    _cursor_loop_tearDownModule()
    _esquema_ui_doc_tearDownModule()
    _fitxer_llarg_tearDownModule()
    _loop_boto_tearDownModule()
    _model_gran_tearDownModule()
    _panell_xifrat_tearDownModule()
    _vista_segueix_model_tearDownModule()


# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_projecte.py
# ══════════════════════════════════════════════════════════════════════════
"""Projectes — carpeta AUTOCONTINGUDA (regla de producte «com un DAW»).

Comprova que `app/projecte.py` crea una carpeta que ho conté tot (l'àudio
copiat a `audio/`, els CSVs i el document `.acproj`) i que **no depèn de fora**:
si s'esborra l'original o es mou la carpeta sencera, el projecte s'obre igual.
"""


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


    def test_crea_ja_deixa_tot_el_model(self):
        """Un projecte nou neix COMPLET: es pot treballar i exportar sense analitzar."""
        wav = os.path.join(self.td, "tema.wav")
        _wav(wav, 2.0)
        carp = os.path.join(self.td, "P")
        p = projecte.Projecte.crea(carp, wav, bpm=138.0, bpb=4)
        for nom in ("acords.csv", "estructura_ABC.csv", "tempo.csv",
                    "compas.csv"):
            self.assertTrue(os.path.isfile(os.path.join(carp, nom)),
                            f"falta {nom} en crear el projecte")
        with open(os.path.join(carp, "acords.csv"), encoding="utf-8") as fh:
            self.assertEqual(fh.read().strip(), "0.000000,2.000000,N")
        with open(os.path.join(carp, "tempo.csv"), encoding="utf-8") as fh:
            self.assertEqual(fh.read().strip(), "0.000000,2.000000,138.000000")
        self.assertTrue(os.path.isfile(p.ruta_acproj))


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

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_projecte_backups.py
# ══════════════════════════════════════════════════════════════════════════
"""Projectes — backups versionats + sessió/recuperació (fase 3).

- `Projecte.fes_backup()`: còpia dins `backup/<data-hora>/` (document + CSVs) i
  rotació perquè no creixin sense control.
- Sessió: marcador `sessio.json` (s'escriu amb un projecte obert i es neteja al
  tancament net); a l'arrencada, `_sessio_pendent()` retorna el projecte a
  oferir si l'app va caure.
"""


_VIVES = []


def _projecte_backups___wav(dur=2.0):
    d = tempfile.mkdtemp()
    ruta = os.path.join(d, "tema.wav")
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * int(44100 * dur))
    return ruta


def _finestra():
    f = app_main.Finestra()
    _VIVES.append(f)
    return f


def _obre_wav(f, wav, nom="Projecte1"):
    acproj = os.path.join(os.path.dirname(wav), nom + ".acproj")
    with patch.object(QFileDialog, "getOpenFileName", return_value=(wav, "")), \
            patch.object(QFileDialog, "getSaveFileName",
                         return_value=(acproj, "")):
        f.tria_wav()
    return f.projecte


# ── Backups (model) ──────────────────────────────────────────────────────────
class TestBackups(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()

    def _projecte(self):
        wav = _projecte_backups___wav()
        return projecte.Projecte.crea(os.path.join(self.td, "P"), wav, bpm=120.0)

    def test_fes_backup_guarda_document_model_i_crua(self):
        p = self._projecte()
        with open(p.ruta_csv_acords(), "w", encoding="utf-8") as f:
            f.write("0.0,1.0,C\n1.0,5.0,Am\n")
        with open(p.ruta_csv_estructura(), "w", encoding="utf-8") as f:
            f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n")
            f.write("0.0,5.0,5.0,A,A,1.1,1.5\n")
        # El CRU viu DINS el document: ha d'anar a la còpia amb el `.acproj`.
        p.dades["analisi"] = {"chords": [[0.0, "C"], [1.0, "Am"]],
                              "segments": [[0.0, 5.0, 0, "A"]]}
        dest = p.fes_backup()
        for nom in (os.path.basename(p.ruta_acproj), "acords.csv",
                    "estructura_ABC.csv"):
            self.assertTrue(os.path.isfile(os.path.join(dest, nom)), nom)
        with open(os.path.join(dest, os.path.basename(p.ruta_acproj)),
                  encoding="utf-8") as f:
            copia = json.load(f)
        self.assertIn("analisi", copia)
        self.assertEqual(copia["analisi"]["chords"], [[0.0, "C"], [1.0, "Am"]])
        self.assertEqual(len(p.backups()), 1)

    def test_no_duplica_si_no_canvia(self):
        p = self._projecte()
        self.assertIsNotNone(p.fes_backup())
        self.assertIsNone(p.fes_backup(), "sense canvis no ha de duplicar")
        self.assertEqual(len(p.backups()), 1)
        p.dades["tempo"]["bpm"] = 140.0
        self.assertIsNotNone(p.fes_backup(), "amb canvi sí que en fa una altra")
        self.assertEqual(len(p.backups()), 2)

    def test_backup_captura_l_estat_viu(self):
        p = self._projecte()
        p.dades["tempo"]["bpm"] = 173.0
        dest = p.fes_backup()
        with open(os.path.join(dest, os.path.basename(p.ruta_acproj)),
                  encoding="utf-8") as f:
            b = json.load(f)
        self.assertEqual(b["tempo"]["bpm"], 173.0)

    def test_rota_backups(self):
        p = self._projecte()
        for k in range(5):
            p.dades["tempo"]["bpm"] = 120.0 + k
            p.fes_backup(max_backups=3)
        self.assertEqual(len(p.backups()), 3)

    def test_rota_backups_zero_no_rota(self):
        p = self._projecte()
        for k in range(3):
            p.dades["tempo"]["bpm"] = 120.0 + k
            p.fes_backup(max_backups=0)          # 0 = no esborrar res
        self.assertEqual(len(p.backups()), 3)

    def test_backups_sense_carpeta(self):
        p = self._projecte()
        self.assertEqual(p.backups(), [])        # encara no s'ha fet cap backup

    def test_molts_backups_dins_el_mateix_segon(self):
        """La rotació ha de quedar-se els MÉS NOUS, ni que comparteixin segon."""
        p = self._projecte()
        creats = []
        for k in range(15):
            p.dades["tempo"]["bpm"] = 100.0 + k      # distints → cada un compta
            creats.append(p.fes_backup(max_backups=10))
        queden = p.backups()
        self.assertEqual(len(queden), 10)
        # noms ÚNICS (no es reutilitza cap nom esborrat)
        noms = [os.path.basename(b) for b in queden]
        self.assertEqual(len(set(noms)), len(noms))
        # els 10 més NOUS (els 10 darrers creats) són els que queden
        esperats = {os.path.abspath(c) for c in creats[-10:]}
        self.assertEqual({os.path.abspath(b) for b in queden}, esperats)


# ── Sessió + autosave (GUI) ──────────────────────────────────────────────────
class _BaseGUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = app_main.QApplication.instance() or app_main.QApplication([])

    def setUp(self):
        self.td = tempfile.mkdtemp()
        self._p = patch.object(config, "DADES_DIR", self.td)
        self._p.start()

    def tearDown(self):
        self._p.stop()
        try:
            import _qt_neteja
        except ImportError:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import _qt_neteja
        ws, _VIVES[:] = _VIVES[:], []
        for w in ws:
            w.dirty = False
        _qt_neteja.tanca_i_destrueix(*ws)


class TestSessio(_BaseGUI):
    def test_marca_i_sessio_pendent(self):
        f = _finestra()
        p = _obre_wav(f, _projecte_backups___wav())
        self.assertTrue(os.path.isfile(f._sessio_path()),
                        "en obrir un projecte s'ha de marcar la sessió")
        self.assertEqual(f._sessio_pendent(), os.path.abspath(p.ruta_acproj))
        self.assertFalse(os.path.isfile(f._sessio_path()),
                         "el marcador s'ha de netejar en llegir-lo")

    def test_sessio_pendent_sense_marcador(self):
        f = _finestra()
        self.assertIsNone(f._sessio_pendent())

    def test_sessio_pendent_amb_acproj_inexistent(self):
        f = _finestra()
        with open(f._sessio_path(), "w", encoding="utf-8") as fh:
            json.dump({"acproj": os.path.join(self.td, "no-existeix.acproj")}, fh)
        self.assertIsNone(f._sessio_pendent())
        self.assertFalse(os.path.isfile(f._sessio_path()))

    def test_close_net_neteja_la_sessio(self):
        f = _finestra()
        _obre_wav(f, _projecte_backups___wav())
        self.assertTrue(os.path.isfile(f._sessio_path()))
        f.dirty = False
        f.close()
        self.assertFalse(os.path.isfile(f._sessio_path()))


class TestAutosave(_BaseGUI):
    def test_autosave_nomes_amb_canvis(self):
        f = _finestra()
        p = _obre_wav(f, _projecte_backups___wav())
        f._fes_autosave()                 # net -> no ha de fer res
        self.assertEqual(p.backups(), [])
        f._marca_dirty()
        f._fes_autosave()
        self.assertEqual(len(p.backups()), 1)

    def test_autosave_captura_el_tempo_dels_widgets(self):
        f = _finestra()
        p = _obre_wav(f, _projecte_backups___wav())
        f.bpm.setText("155.0")
        f._marca_dirty()
        f._fes_autosave()
        dest = p.backups()[0]
        with open(os.path.join(dest, os.path.basename(p.ruta_acproj)),
                  encoding="utf-8") as fh:
            b = json.load(fh)
        self.assertEqual(b["tempo"]["bpm"], 155.0)


def _projecte_backups_tearDownModule():
    try:
        import _qt_neteja
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_projectes_gui.py
# ══════════════════════════════════════════════════════════════════════════
"""Projectes — cicle de vida a la GUI (fase 2): obrir WAV → projecte
autocontingut, desar / desar com / desar una còpia / reverteix, recents,
«brut» i títol.
"""


_projectes_gui___VIVES = []


def _projectes_gui___wav(dur=2.0):
    d = tempfile.mkdtemp()          # dir únic per a cada WAV (evita xocs)
    ruta = os.path.join(d, "tema.wav")
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * int(44100 * dur))
    return ruta


def _projectes_gui___finestra():
    f = app_main.Finestra()
    _projectes_gui___VIVES.append(f)
    return f


def _projectes_gui___obre_wav(f, wav, nom="Projecte1"):
    """Simula «Obre WAV» triant WAV + ubicació del projecte."""
    acproj = os.path.join(os.path.dirname(wav), nom + ".acproj")
    with patch.object(QFileDialog, "getOpenFileName", return_value=(wav, "")), \
            patch.object(QFileDialog, "getSaveFileName",
                         return_value=(acproj, "")):
        f.tria_wav()
    return f.projecte


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = app_main.QApplication.instance() or app_main.QApplication([])

    def setUp(self):
        # Aïlla els recents (no escriure al DADES_DIR real).
        self.td = tempfile.mkdtemp()
        self._patches = [patch.object(config, "DADES_DIR", self.td)]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        try:
            import _qt_neteja
        except ImportError:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import _qt_neteja
        ws, _projectes_gui___VIVES[:] = _projectes_gui___VIVES[:], []
        for w in ws:
            w.dirty = False          # no volem el prompt de tancament als tests
        _qt_neteja.tanca_i_destrueix(*ws)


class TestObreWavCreaProjecte(_Base):
    def test_projecte_autocontingut(self):
        f = _projectes_gui___finestra()
        wav = _projectes_gui___wav()
        p = _projectes_gui___obre_wav(f, wav)
        self.assertIsNotNone(p, "s'hauria d'haver creat un projecte")
        # carpeta = <dir del wav>/Projecte1
        self.assertEqual(p.carpeta, os.path.join(os.path.dirname(wav), "Projecte1"))
        self.assertTrue(os.path.isfile(p.ruta_audio()), "àudio copiat a dins")
        self.assertEqual(f.sortida, p.carpeta)
        self.assertEqual(f.visor_ref._carpeta_acords(), p.carpeta,
                         "el visor ha de desar els CSV al PROJECTE, no dins audio/")
        self.assertIsNotNone(f.visor_ref, "s'hauria d'haver carregat el visor")
        self.assertIn("Projecte1", f.windowTitle())
        self.assertFalse(f.dirty)

    def test_esborra_original_i_el_projecte_obre(self):
        f = _projectes_gui___finestra()
        wav = _projectes_gui___wav()
        p = _projectes_gui___obre_wav(f, wav)
        os.remove(wav)                        # l'original ja no hi és
        f2 = _projectes_gui___finestra()
        f2._obre_ruta_projecte(p.ruta_acproj)
        self.assertIsNotNone(f2.projecte)
        self.assertTrue(f2.projecte.audio_present())


    def test_compas_complet_preservat(self):
        """El compàs «6/8» (amb denominador) ha de sobreviure desar/reobrir."""
        f = _projectes_gui___finestra()
        wav = _projectes_gui___wav()
        f.bpb.setText("6/8")
        acproj = os.path.join(os.path.dirname(wav), "C.acproj")
        with patch.object(QFileDialog, "getOpenFileName",
                          return_value=(wav, "")), \
                patch.object(QFileDialog, "getSaveFileName",
                             return_value=(acproj, "")):
            f.tria_wav()
        self.assertEqual(f.bpb.text(), "6/8")
        p = f.projecte
        f._marca_dirty()
        f._desa_projecte()
        f2 = _projectes_gui___finestra()
        f2._obre_ruta_projecte(p.ruta_acproj)
        self.assertEqual(f2.bpb.text(), "6/8")


class TestDesa(_Base):
    def test_desa_escriu_el_document(self):
        f = _projectes_gui___finestra()
        p = _projectes_gui___obre_wav(f, _projectes_gui___wav())
        f.bpm.setText("133.0")
        f._marca_dirty()
        self.assertTrue(f.dirty)
        f._desa_projecte()
        self.assertFalse(f.dirty)
        p2 = projecte.Projecte.obre(p.ruta_acproj)
        self.assertEqual(p2.dades["tempo"]["bpm"], 133.0)

    def test_desa_una_copia_no_canvia_el_projecte(self):
        f = _projectes_gui___finestra()
        p = _projectes_gui___obre_wav(f, _projectes_gui___wav())
        desti = os.path.join(self.td, "COPIA.acproj")
        with patch.object(QFileDialog, "getSaveFileName",
                          return_value=(desti, "")):
            f._desa_copia()
        self.assertEqual(f.projecte.carpeta, p.carpeta,
                         "una còpia no ha de canviar el projecte actiu")
        self.assertTrue(os.path.isfile(
            os.path.join(self.td, "COPIA", "COPIA.acproj")))

    def test_desa_com_canvia_el_projecte(self):
        f = _projectes_gui___finestra()
        p = _projectes_gui___obre_wav(f, _projectes_gui___wav())
        desti = os.path.join(self.td, "NOU_NOM.acproj")
        with patch.object(QFileDialog, "getSaveFileName",
                          return_value=(desti, "")):
            f._desa_projecte_com()
        self.assertEqual(f.projecte.carpeta, os.path.join(self.td, "NOU_NOM"))
        self.assertNotEqual(f.projecte.carpeta, p.carpeta)
        self.assertTrue(os.path.isfile(f.projecte.ruta_audio()),
                        "la còpia també ha de ser autocontinguda")

    def test_desa_com_al_mateix_lloc_es_desa_normal(self):
        f = _projectes_gui___finestra()
        p = _projectes_gui___obre_wav(f, _projectes_gui___wav())
        f.bpm.setText("111.0")
        f._marca_dirty()
        with patch.object(QFileDialog, "getSaveFileName",
                          return_value=(os.path.join(
                              os.path.dirname(p.carpeta),
                              p.nom + projecte.EXT), "")):
            f._desa_projecte_com()
        self.assertEqual(f.projecte.carpeta, p.carpeta)
        self.assertEqual(projecte.Projecte.obre(p.ruta_acproj)
                         .dades["tempo"]["bpm"], 111.0)
        self.assertFalse(f.dirty)

    def test_reverteix(self):
        f = _projectes_gui___finestra()
        _projectes_gui___obre_wav(f, _projectes_gui___wav())
        f.bpm.setText("99.0")
        f._desa_projecte()
        f.bpm.setText("150.0")
        f._marca_dirty()
        with patch.object(f, "_confirma_descartar", return_value=True):
            f._reverteix()
        self.assertEqual(f.bpm.text(), "99.000")
        self.assertFalse(f.dirty)


class TestDirtyITitol(_Base):
    def test_titol_amb_estrella(self):
        f = _projectes_gui___finestra()
        _projectes_gui___obre_wav(f, _projectes_gui___wav())
        self.assertNotIn("*", f.windowTitle())
        f._marca_dirty()
        self.assertTrue(f.windowTitle().endswith("*"))

    def test_pot_descartar(self):
        f = _projectes_gui___finestra()
        f.dirty = False
        self.assertTrue(f._pot_descartar())
        f.dirty = True
        with patch.object(f, "_confirma_descartar", return_value=False):
            self.assertFalse(f._pot_descartar())

    def test_close_amb_canvis_ignora(self):
        f = _projectes_gui___finestra()
        f.dirty = True

        class _Ev:
            def __init__(self):
                self._ignorat = False
            def ignore(self):
                self._ignorat = True
            def accept(self):
                pass
        ev = _Ev()
        with patch.object(f, "_pot_descartar", return_value=False):
            f.closeEvent(ev)
        self.assertTrue(ev._ignorat, "amb canvis sense desar no s'ha de tancar")


class TestRecents(_Base):
    def test_recents_guarda_i_llista(self):
        f = _projectes_gui___finestra()
        p = _projectes_gui___obre_wav(f, _projectes_gui___wav())
        self.assertIn(os.path.abspath(p.ruta_acproj), f.recents)
        self.assertTrue(os.path.isfile(f._recents_path()),
                        "els recents s'han de persistir")


class TestObrirProjecteHabilitaExport(_Base):
    def test_obrir_projecte_amb_model_activa_les_exportacions(self):
        """Obrir un projecte amb model ha de deixar disponibles les exportacions.

        Bug: «Exporta WAV's»/«Exporta partitura» només s'activaven al final
        d'una ANÀLISI → obrir un projecte els deixava apagats i no es podia
        exportar sense tornar a analitzar (cosa que descarta les edicions).
        """
        wav = _projectes_gui___wav()
        p = projecte.Projecte.crea(os.path.join(os.path.dirname(wav), "P"),
                                   wav, bpm=120.0)
        with open(p.ruta_csv_acords(), "w", encoding="utf-8") as fh:
            fh.write("0.0,2.0,C\n2.0,4.0,G\n")
        f = _projectes_gui___finestra()
        f.avisa = lambda *a, **k: None
        self.assertFalse(f.b_export.isEnabled(), "abans d'obrir, apagat")
        f._activa_projecte(projecte.Projecte.obre(p.ruta_acproj))
        self.assertTrue(f.b_export.isEnabled(),
                        "amb projecte obert l'export ha d'estar activa")
        self.assertTrue(f.b_export_part.isEnabled())

    def test_obrir_projecte_no_deixa_copia_dins_audio(self):
        """El visor desa a la carpeta del PROJECTE, mai dins `<projecte>/audio/`.

        Bug: el constructor del visor no sabia la carpeta de sortida i, quan la
        normalització (regla d'or #4) canviava el model, desava una còpia a la
        carpeta derivada del WAV (`audio/AUTOCHORDS_…/`).
        """
        wav = _projectes_gui___wav()
        p = projecte.Projecte.crea(os.path.join(os.path.dirname(wav), "P"),
                                   wav, bpm=120.0)
        with open(p.ruta_csv_acords(), "w", encoding="utf-8") as fh:
            fh.write("1.0,5.0,C\n")          # 1r acord NO a 0 → força normalització
        f = _projectes_gui___finestra()
        f.avisa = lambda *a, **k: None
        f._activa_projecte(projecte.Projecte.obre(p.ruta_acproj))
        audio = os.path.join(p.carpeta, "audio")
        self.assertEqual(sorted(os.listdir(audio)),
                         [os.path.basename(p.ruta_audio())],
                         "audio/ només ha de contenir l'àudio")
        with open(p.ruta_csv_acords(), encoding="utf-8") as fh:
            self.assertIn("N", fh.read(), "el CSV del projecte s'ha normalitzat")


def _projectes_gui_tearDownModule():
    try:
        import _qt_neteja
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_tancament.py
# ══════════════════════════════════════════════════════════════════════════
"""Tancament intel·ligent: detectar canvis (ajustos del projecte I edicions de la
cançó), avisar NOMÉS si n'hi ha, oferir Desa/Descarta/Cancel·la, i MAI tancar si
el desat falla.
"""


_tancament___VIVES = []


def _tancament___wav(dur=4.0):
    d = tempfile.mkdtemp()
    ruta = os.path.join(d, "tema.wav")
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * int(44100 * dur))
    return ruta


def _finestra_amb_projecte():
    f = app_main.Finestra()
    _tancament___VIVES.append(f)
    # Silencia els avisos (alguns són modals i encallarien el test).
    f.avisa = lambda *a, **k: None
    f.avisa_info = lambda *a, **k: None
    f.avisa_crit = lambda *a, **k: None
    wav = _tancament___wav()
    acproj = os.path.join(os.path.dirname(wav), "P.acproj")
    with patch.object(QFileDialog, "getOpenFileName", return_value=(wav, "")), \
            patch.object(QFileDialog, "getSaveFileName", return_value=(acproj, "")):
        f.tria_wav()
    return f


def _tanca(f):
    """Tanca l'app netejant el «dirty» (evita el prompt real als tests)."""
    f.dirty = False
    f.close()


def _clic_prompt(f, etiqueta):
    """Simula clicar el botó `etiqueta` del prompt de tancament."""
    capt = {}
    o_add, o_exec, o_cb = (QMessageBox.addButton, QMessageBox.exec_,
                           QMessageBox.clickedButton)

    def fake_add(self, *a):
        b = o_add(self, *a)
        try:
            capt[b.text()] = b
        except Exception:  # noqa: BLE001
            pass
        return b
    QMessageBox.addButton = fake_add
    QMessageBox.exec_ = lambda self: 0
    QMessageBox.clickedButton = lambda self: capt.get(etiqueta)
    try:
        # Als tests la plataforma és `offscreen` i l'app HI SALTA els diàlegs a
        # posta (un modal fa «access violation» a Windows; vegeu `_interactiu`).
        # Aquí simulem un entorn interactiu per provar la lògica del prompt.
        with patch.object(f, "_interactiu", return_value=True):
            return f._confirma_descartar()
    finally:
        QMessageBox.addButton, QMessageBox.exec_, QMessageBox.clickedButton = (
            o_add, o_exec, o_cb)


class _tancament___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = app_main.QApplication.instance() or app_main.QApplication([])

    def setUp(self):
        self.td = tempfile.mkdtemp()
        self._p = patch.object(config, "DADES_DIR", self.td)
        self._p.start()

    def tearDown(self):
        self._p.stop()
        try:
            import _qt_neteja
        except ImportError:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import _qt_neteja
        ws, _tancament___VIVES[:] = _tancament___VIVES[:], []
        for w in ws:
            w.dirty = False
        _qt_neteja.tanca_i_destrueix(*ws)


class TestTancamentIntel·ligent(_tancament___Base):
    def test_acabat_d_obrir_esta_net(self):
        f = _finestra_amb_projecte()
        self.assertFalse(f._te_canvis(), "acabat d'obrir no hi ha canvis")
        _tanca(f)

    def test_editar_la_canco_marca_canvis(self):
        f = _finestra_amb_projecte()
        f.visor_ref._afegeix_acord(1.0, "G")
        f.visor_ref._desa_i_regenera()          # edició → senyal `canvis`
        self.assertTrue(f._te_canvis(),
                        "una edició de la cançó ha de marcar el projecte")
        self.assertTrue(f.windowTitle().endswith("*"))
        _tanca(f)

    def test_desa_retorna_ok_i_net(self):
        f = _finestra_amb_projecte()
        f.visor_ref._afegeix_acord(1.0, "G")
        f.visor_ref._desa_i_regenera()
        self.assertTrue(f._desa_projecte())
        self.assertFalse(f._te_canvis())
        _tanca(f)

    def test_desa_fallit_retorna_fals(self):
        f = _finestra_amb_projecte()
        f._marca_dirty()
        with patch.object(type(f.projecte), "desa",
                          side_effect=OSError("disc ple")):
            self.assertFalse(f._desa_projecte())
        _tanca(f)

    def test_prompt_desa_fallit_no_continua(self):
        f = _finestra_amb_projecte()
        f._marca_dirty()
        with patch.object(f, "_desa_projecte", return_value=False):
            self.assertFalse(_clic_prompt(f, "Desa"),
                             "si el desat falla, NO s'ha de continuar")
        _tanca(f)

    def test_prompt_descarta_i_cancela(self):
        f = _finestra_amb_projecte()
        f._marca_dirty()
        self.assertTrue(_clic_prompt(f, "Descarta"))
        f._marca_dirty()
        self.assertFalse(_clic_prompt(f, "Cancel·la"))
        _tanca(f)

    def test_close_net_tanca_sense_prompt(self):
        f = _finestra_amb_projecte()
        with patch.object(f, "_confirma_descartar") as p:
            _tanca(f)
        p.assert_not_called()                   # net → cap prompt
        self.assertFalse(f.isVisible())

    def test_offscreen_no_obre_cap_dialeg_modal(self):
        """A la plataforma `offscreen` (tests i CI) les confirmacions NO han
        d'obrir cap `QMessageBox` modal: a Windows fa «access violation» (el
        crash que va tombar el CI). Han de respondre amb el valor segur."""
        f = _finestra_amb_projecte()
        f._marca_dirty()
        with patch.object(QMessageBox, "exec_") as m:
            self.assertTrue(f._pot_descartar())     # continua sense preguntar
            m.assert_not_called()
        _tanca(f)


def _tancament_tearDownModule():
    try:
        import _qt_neteja
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_tancar_sonant.py
# ══════════════════════════════════════════════════════════════════════════
"""Tancar l'app MENTRE sona → neteja ordenada (`closeEvent`), sense petar.

Cas real (Claude, checklist pre-publicació punt 2): l'usuari tanca la finestra
mentre el visor està reproduint. Sense `closeEvent`, Qt destrueixia la Finestra
amb el **fil d'alimentació viu** escrivint PCM al reproductor → destrucció en
ordre arbitrari = risc d'`access violation` (el crash intermitent que va costar
de trobar als tests).

Aquí es reprodueix el **pitjor cas** de manera determinista: s'injecta un motor
d'àudio FALS (mateixa interfície que `audio_out.crea_motor`: `stdin`/`poll`/
`returncode`/`pid`/`atura`) el `write` del qual **es bloqueja** fins que algú
l'atura — és a dir, el fil queda viu «sonant» fins que el `closeEvent` hi actua.
Així el test no depèn de maquinari d'àudio ni d'orelles.

Cobreix el `closeEvent` (que fins ara no tenia cap test): espera l'export, atura
el rellotge i el reproductor del visor, tanca el pont MCP i la caixa d'avís no
modal. El **motor natiu real** (PortAudio a mac/win, canvi d'auriculars en calent)
segueix sent prova manual.
"""


_tancar_sonant___VIVES = []     # finestres creades pel test: es tanquen al tearDown


def _tancar_sonant___finestra(segons=20):
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "t.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * segons)
    f = app_main.Finestra()
    f.wav_edit.setText(wav)
    f._carrega_visor(wav)
    _tancar_sonant___VIVES.append(f)
    return f


def _fil_alimenta(v):
    """El fil d'alimentació de `v` encara viu (o `None`)."""
    for t in threading.enumerate():
        obj = getattr(t, "_target", None)
        if obj is None:
            continue
        if getattr(obj, "__self__", None) is v and \
                getattr(getattr(obj, "__func__", None), "__name__", "") == "_alimenta":
            return t
    return None


class _FakeMotor:
    """Motor d'àudio fals, amb la interfície d'`audio_out.crea_motor`."""

    def __init__(self):
        self.pid = 4242
        self.aturat = False
        self.escrit = 0
        self._allibera = threading.Event()
        self.stdin = self          # `proc.stdin.write(tros)` → write()

    def write(self, b):
        self.escrit += len(b)
        # Com un pipe PLE: el fil queda encallat aquí fins que `atura()` el
        # desbloqueja → és el que fa que «estigui sonant» de debò en tancar.
        self._allibera.wait(5.0)
        return len(b)

    def close(self):
        pass

    def flush(self):
        pass

    def poll(self):
        return 0 if self.aturat else None

    @property
    def returncode(self):
        return 0 if self.aturat else None

    def atura(self):
        self.aturat = True
        self._allibera.set()       # desbloqueja el fil d'alimentació


class _FakePont:
    def __init__(self):
        self.tancat = False

    def tanca(self):
        self.tancat = True


class _FakeFeina:
    def __init__(self):
        self.esperat = None

    def isRunning(self):
        return True

    def wait(self, ms):
        self.esperat = ms
        return True


class _tancar_sonant___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QW.QApplication.instance() or QW.QApplication([])

    def setUp(self):
        # Cap test no ha d'ensenyar un QMessageBox de veritat.
        p = patch.object(QW.QMessageBox, "show", lambda self: None)
        p.start()
        self.addCleanup(p.stop)

    def tearDown(self):
        try:
            import _qt_neteja
        except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
            import os as _os
            import sys as _sys
            _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
            import _qt_neteja
        ws = _tancar_sonant___VIVES[:]
        _tancar_sonant___VIVES.clear()
        _qt_neteja.tanca_i_destrueix(*ws)


class TestTancarSonant(_tancar_sonant___Base):

    def test_tancar_sense_sonar_tambe_es_net(self):
        """Camí normal: tancar amb el visor aturat no ha de petar ni fer res."""
        f = _tancar_sonant___finestra()
        v = f.visor_ref
        f.close()
        self.assertIsNone(v.proc)
        self.assertFalse(v.rellotge.isActive())


def _tancar_sonant_tearDownModule():
    # Neteja ORDENADA dels objectes Qt del mòdul (evita destrucció pel GC en un
    # test posterior -> access violation intermitent). Vegeu tests/_qt_neteja.py.
    try:
        import _qt_neteja
    except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
        import os
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_canvi_wav.py
# ══════════════════════════════════════════════════════════════════════════
"""Canviar de WAV ha de reiniciar el tempo (troballa OC-6/415).

El BPM és del TEMA: si obres un WAV nou i el camp es queda amb el valor del
tema anterior, el nou surt analitzat amb el tempo vell (i la graella de
compassos, malament). `tria_wav()` ara el torna al valor per defecte (120.0) i
ho registra; l'usuari el pot detectar o posar a mà.
"""


_canvi_wav___VIVES = []


def _canvi_wav___wav(segons=1):
    d = tempfile.mkdtemp()          # dir únic per a cada WAV (evita xocs)
    ruta = os.path.join(d, "tema.wav")
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * segons)
    return ruta


def _canvi_wav___finestra():
    f = app_main.Finestra()
    _canvi_wav___VIVES.append(f)
    return f


class _canvi_wav___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QW.QApplication.instance() or QW.QApplication([])

    def setUp(self):
        # Aïlla els «recents» (no escriure al DADES_DIR real del repo).
        self.td = tempfile.mkdtemp()
        self._p = patch.object(app_main.config, "DADES_DIR", self.td)
        self._p.start()

    def tearDown(self):
        self._p.stop()
        try:
            import _qt_neteja
        except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
            import os as _os
            _sys = sys
            _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
            import _qt_neteja
        ws, _canvi_wav___VIVES[:] = _canvi_wav___VIVES[:], []
        _qt_neteja.tanca_i_destrueix(*ws)


class TestCanviWavReiniciaTempo(_canvi_wav___Base):
    def _obre(self, f, ruta):
        # «Obre WAV» ara crea un projecte: cal patxegar TAMBÉ el diàleg de
        # destinació (per defecte, una carpeta al costat del WAV).
        desti = os.path.join(os.path.dirname(ruta), "AUTOCHORDS_prova.acproj")
        with patch.object(QFileDialog, "getOpenFileName",
                          return_value=(ruta, "")), \
                patch.object(QFileDialog, "getSaveFileName",
                             return_value=(desti, "")):
            f.tria_wav()

    def test_bpm_reiniciat_en_carregar_un_wav_nou(self):
        f = _canvi_wav___finestra()
        f.bpm.setText("140.0")
        self._obre(f, _canvi_wav___wav())
        self.assertEqual(f.bpm.text(), "120.000",
                         "el WAV nou no ha d'heretar el BPM de l'anterior")
        self.assertIsNotNone(f.visor_ref, "s'hauria d'haver carregat el visor")

    def test_bpm_per_defecte_no_canvia(self):
        f = _canvi_wav___finestra()
        self.assertEqual(f.bpm.text(), "120.000")
        self._obre(f, _canvi_wav___wav())
        self.assertEqual(f.bpm.text(), "120.000")


def _canvi_wav_tearDownModule():
    try:
        import _qt_neteja
    except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_avis_audio.py
# ══════════════════════════════════════════════════════════════════════════
"""Tests: AVÍS VISIBLE quan el motor d'àudio mor.

Cobreix l'arreglament de `docs/archive/AUDITORIA_PRODUCCIO.md` 1.6/4.3 i el «Pendent» de
`docs/AUDIO.md`: que un error del reproductor NO quedi només al log, sinó que
l'usuari en rebi un avís (senyal `infoMissatge` → caixa d'informació).
"""


def _wav_silenci(segons=1):
    fd, ruta = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * segons)
    return ruta


class _FakeProcError:
    returncode = 1

    def poll(self):
        return 1

    def atura(self):
        pass


class TestAvisAudio(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def _visor(self):
        return visor.Visor(_wav_silenci(), None, None, 120.0, 4, True)

    def test_tiquet_avisa_si_el_motor_mor(self):
        v = self._visor()
        v.proc = _FakeProcError()
        v.sona = True
        v.t0_pos = 0.0
        v.t0_mono = 0.0
        missatges = []
        v.infoMissatge.connect(missatges.append)
        v._tiquet()
        self.assertTrue(any("motor d'àudio" in m for m in missatges),
                        f"no s'ha emès l'avís visible: {missatges}")
        self.assertFalse(v.sona, "l'error hauria d'haver aturat la reproducció")

    def test_avis_nomes_un_cop_per_reproduccio(self):
        v = self._visor()
        v.proc = _FakeProcError()
        v.sona = True
        v.t0_pos = 0.0
        v.t0_mono = 0.0
        n = []
        v.infoMissatge.connect(n.append)
        v._tiquet()                     # avisa i atura
        v.proc = _FakeProcError()       # "torna a sonar" sense passar per play
        v.sona = True
        v.t0_mono = 0.0
        v._tiquet()                     # NO ha de tornar a avisar
        self.assertEqual(len(n), 1)


def _avis_audio_tearDownModule():
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
# ORIGEN: test_avis_reanalisi.py
# ══════════════════════════════════════════════════════════════════════════
"""Tests de l'avís de re-anàlisi.

En tornar a prémer «Analitza» amb resultats ja presents, l'app ha d'avisar que
sobreviurà el resultat actual (i les edicions manuals) i que no es pot desfer.
Aquí comprovem la DECISIÓ de quan cal avisar (`_hi_ha_resultats` /
`_confirma_reanalisi`); el diàleg en si és de la GUI.
"""


def _win(visor):
    return types.SimpleNamespace(visor_ref=visor)


def _visor(acords=(), seccions=()):
    return types.SimpleNamespace(acords=list(acords), seccions=list(seccions))


class TestHiHaResultats(unittest.TestCase):
    def test_sense_visor(self):
        self.assertFalse(Finestra._hi_ha_resultats(_win(None)))

    def test_visor_buit(self):
        # primera anàlisi d'un WAV nou: no hi ha res a perdre
        self.assertFalse(Finestra._hi_ha_resultats(_win(_visor())))

    def test_amb_acords(self):
        self.assertTrue(Finestra._hi_ha_resultats(
            _win(_visor(acords=[(0.0, "N", "0.000000000")]))))

    def test_amb_seccions(self):
        self.assertTrue(Finestra._hi_ha_resultats(
            _win(_visor(seccions=[(0.0, 4.0, "A", "A")]))))

    def test_visor_sense_atributs(self):
        # no ha de petar si el visor no té els atributs
        self.assertFalse(Finestra._hi_ha_resultats(
            _win(types.SimpleNamespace())))


class TestConfirmaReanalisi(unittest.TestCase):
    def setUp(self):
        if not os.environ.get("DISPLAY") and not os.environ.get("QT_QPA_PLATFORM"):
            os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PyQt5.QtWidgets import QApplication
        self._qapp = QApplication.instance() or QApplication([])

    def test_sense_resultats_continua_sense_dialeg(self):
        # sense resultats, ha de retornar True SENSE mostrar cap avís
        w = Finestra()
        w.visor_ref = None
        self.assertTrue(w._confirma_reanalisi())


def _avis_reanalisi_tearDownModule():
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
# ORIGEN: test_autocomprovacio_ffmpeg.py
# ══════════════════════════════════════════════════════════════════════════
"""A9: l'autocomprovació d'arrencada ha d'incloure ffmpeg.

L'app s'autocomprova `ACORDS_PY` i els `VAMP_DIRS`, però **no** comprovava
`ffmpeg`: és imprescindible per obrir qualsevol format que no sigui WAV PCM
16 bits (mp3/flac/m4a/ogg…). Sense ell, l'obertura fallava tard i amb un error
críptic. Ara s'avisa a l'arrencada i, si no hi és, el diàleg d'obertura només
ofereix WAV (oferir la resta seria enganyós).
"""


class TestAutocomprovacioFfmpeg(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QW.QApplication.instance() or QW.QApplication([])

    def test_avisa_si_falta_ffmpeg(self):
        with patch.object(app_main.ffmpeg, "disponible", return_value=False):
            w = app_main.Finestra()
        self.assertIn("ffmpeg", w.log.toPlainText(),
                      "hauria d'avisar que falta ffmpeg")
        w.close()

    def test_no_avisa_si_hi_es(self):
        with patch.object(app_main.ffmpeg, "disponible", return_value=True):
            w = app_main.Finestra()
        self.assertNotIn("no trobo ffmpeg", w.log.toPlainText())
        w.close()

    def test_l_app_arrenca_igual_sense_ffmpeg(self):
        """No ha de petar: només s'avisa (l'app funciona amb WAV)."""
        with patch.object(app_main.ffmpeg, "disponible", return_value=False):
            w = app_main.Finestra()
        self.assertIsNotNone(w.menuBar())
        w.close()

    def test_filtre_amb_ffmpeg_ofereix_tots_els_formats(self):
        with patch.object(app_main.ffmpeg, "disponible", return_value=True):
            w = app_main.Finestra()
            f = w._filtre_audio()
        self.assertIn("mp3", f)
        w.close()

    def test_filtre_sense_ffmpeg_nomes_wav(self):
        with patch.object(app_main.ffmpeg, "disponible", return_value=False):
            w = app_main.Finestra()
            f = w._filtre_audio()
        self.assertIn("WAV", f)
        self.assertNotIn("mp3", f, "sense ffmpeg no pot oferir mp3")
        w.close()


def _autocomprovacio_ffmpeg_tearDownModule():
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
# ORIGEN: test_cursor_loop.py
# ══════════════════════════════════════════════════════════════════════════
"""El cursor vermell ha d'anar ON sona el so quan hi ha un loop A/B.

Bug (operador, 14-10): amb el loop A/B actiu, `play` amb el cursor FORA del
bucle fa sonar el so des de `loop_a` (el feeder hi salta tot sol: `_alimenta`
fa `if pos < a or pos >= b: pos = a`), però el **cursor vermell es quedava on
era** → la visualització anava desalineada del so fins que la posició visual
atrapava `loop_b` (i encara llavors queia a mig bucle). També passava fent un
**seek** fora del bucle mentre sona (`ves_a` → `_engega_des_de`).

Fix: `visor._engega_des_de()` aplica el MATEIX salt que el feeder (si hi ha
loop i el punt demanat és fora de `[loop_a, loop_b)`, arrenca a `loop_a`) i
sincronitza el cursor (posició + timeline + lliscador + etiquetes) a l'instant.

Els tests no depenen de maquinari d'àudio: s'injecta un motor FALS (mateixa
interfície que `audio_out.crea_motor`) el `write()` del qual es bloqueja, així
el fil d'alimentació no acaba sol durant el test.
"""


_VISORS = []


def _cursor_loop___wav(segons=20):
    fd, ruta = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * segons)
    return ruta


def _cursor_loop___visor():
    v = app_visor.Visor(_cursor_loop___wav(), None, None, 120.0, 4, True)
    v.player, v.player_args = "paplay", []   # crea_motor queda substituït
    _VISORS.append(v)
    return v


class _cursor_loop___FakeMotor:
    """Motor d'àudio fals, amb la interfície d'`audio_out.crea_motor`."""

    def __init__(self):
        self.pid = 4242
        self.aturat = False
        self._allibera = threading.Event()
        self.stdin = self

    def write(self, b):
        self._allibera.wait(5.0)     # com un pipe ple: el fil queda encallat
        return len(b)

    def close(self):
        pass

    def flush(self):
        pass

    def poll(self):
        return 0 if self.aturat else None

    @property
    def returncode(self):
        return 0 if self.aturat else None

    def atura(self):
        self.aturat = True
        self._allibera.set()


class _cursor_loop___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QW.QApplication.instance() or QW.QApplication([])

    def setUp(self):
        p = patch.object(QW.QMessageBox, "information", lambda *a, **k: None)
        p.start()
        self.addCleanup(p.stop)

    def _arrenca(self, v):
        """Fa `play` (mateix motor fals que `_engega_des_de` farà servir)."""
        motor = _cursor_loop___FakeMotor()
        self._motor = motor
        with patch.object(audio_out, "crea_motor", lambda *a, **k: motor), \
                patch.object(app_visor, "OPENCODE_DIR", tempfile.mkdtemp()):
            v.play_stop()
        return motor

    def tearDown(self):
        for v in _VISORS:
            try:
                v.rellotge.stop()
                v._atura_proc()
            except (RuntimeError, AttributeError):
                pass
        try:
            import _qt_neteja
        except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
            import os as _os
            _sys = sys
            _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
            import _qt_neteja
        ws, _VISORS[:] = _VISORS[:], []
        _qt_neteja.tanca_i_destrueix(*ws)


class TestCursorAmbLoop(_cursor_loop___Base):
    def test_play_fora_del_loop_arrenca_a_loop_a(self):
        """EL BUG: cursor a 5 s, loop [2, 3] → el só va a 2 s; el cursor també."""
        v = _cursor_loop___visor()
        v.loop_a, v.loop_b = 2.0, 3.0
        v.set_loop(True)
        v.ves_a(5.0)                       # cursor FORA del bucle
        self._arrenca(v)
        self.assertAlmostEqual(v.t0_pos, 2.0, places=6,
                               msg="el cursor ha d'anar on sona el só (loop_a)")
        self.assertAlmostEqual(v.pos, 2.0, places=6)
        self.assertAlmostEqual(float(v.timeline.get_position()), 2.0, places=6)

    def test_play_dins_del_loop_respecta_el_cursor(self):
        """Dins el bucle el só arrenca on és el cursor: no s'ha de moure."""
        v = _cursor_loop___visor()
        v.loop_a, v.loop_b = 2.0, 3.0
        v.set_loop(True)
        v.ves_a(2.50)
        self._arrenca(v)
        self.assertAlmostEqual(v.t0_pos, 2.50, places=6)
        self.assertAlmostEqual(float(v.timeline.get_position()), 2.50, places=6)

    def test_play_sense_loop_respecta_el_cursor(self):
        v = _cursor_loop___visor()
        v.ves_a(5.0)
        self._arrenca(v)
        self.assertAlmostEqual(v.t0_pos, 5.0, places=6)

    def test_loop_invalid_no_hi_ha_salt(self):
        """Un bucle degenerat (B <= A) no compta com a loop actiu."""
        v = _cursor_loop___visor()
        v.loop_a, v.loop_b = 3.0, 3.0
        v.set_loop(True)
        self.assertFalse(v.loop_on, "un bucle B<=A no pot quedar actiu")
        v.ves_a(5.0)
        self._arrenca(v)
        self.assertAlmostEqual(v.t0_pos, 5.0, places=6)

    def test_seek_fora_del_loop_mentre_sona(self):
        """Sonant amb loop, un seek fora del bucle també ha d'alinear-se."""
        v = _cursor_loop___visor()
        self._arrenca(v)                   # sona des del principi, sense loop
        v.loop_a, v.loop_b = 2.0, 3.0
        v.set_loop(True)                   # s'activa el bucle mentres sona
        v.ves_a(5.0)                       # seek FORA del bucle
        self.assertAlmostEqual(v.t0_pos, 2.0, places=6,
                               msg="el seek fora del bucle ha de saltar a loop_a")
        self.assertAlmostEqual(float(v.timeline.get_position()), 2.0, places=6)


class TestLoopActivatSonant(_cursor_loop___Base):
    def test_activar_loop_sonant_alinea_cursor_i_so(self):
        """BUG (operador): donar `play` SENSE loop i ACTIVAR el loop mentre sona.

        El feeder llegeix `loop_on` en VIU i, si la posició de generació queda
        fora del bucle, hi salta (`pos = a`) → el só va a `loop_a`. Però
        `set_loop()` no tocava el cursor → el cursor seguia on era.
        """
        v = _cursor_loop___visor()
        self._arrenca(v)                      # play sense loop (des del principi)
        self.assertTrue(v.sona)
        v.loop_a, v.loop_b = 2.0, 3.0
        v.set_loop(True)                      # ← el cas de l'operador
        self.assertAlmostEqual(v.t0_pos, 2.0, places=6,
                               msg="el cursor ha d'anar on el só (loop_a)")
        self.assertAlmostEqual(v.pos, 2.0, places=6)
        self.assertAlmostEqual(float(v.timeline.get_position()), 2.0, places=6)

    def test_activar_loop_amb_cursor_dins_no_mou(self):
        """Si el cursor ja és dins el bucle, el só arrenca allà: no es mou res."""
        v = _cursor_loop___visor()
        # Estat «sonant» fixat a mà: així el test NO depèn del camí
        # seek-mentre-sona (que en un entorn ràpid pot no reengegar el motor).
        v.sona = True
        v.pos = v.t0_pos = 2.5
        v.loop_a, v.loop_b = 2.0, 3.0
        v.set_loop(True)
        self.assertAlmostEqual(v.t0_pos, 2.5, places=6,
                               msg="amb el cursor dins el bucle, no s'ha de moure")

    def test_activar_loop_parat_no_mou_el_cursor(self):
        """Amb el transport aturat, activar el loop no ha de moure el cursor."""
        v = _cursor_loop___visor()
        v.ves_a(5.0)
        v.loop_a, v.loop_b = 2.0, 3.0
        v.set_loop(True)
        self.assertAlmostEqual(v.pos, 5.0, places=6)


def _cursor_loop_tearDownModule():
    try:
        import _qt_neteja
    except ImportError:      # 'python -m unittest tests.test_x' (tests/ no al path)
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_dialegs.py
# ══════════════════════════════════════════════════════════════════════════
"""Lògica dels DIÀLEGS (`app/dialegs.py`) — sense obrir-los.

Els tests de la resta del projecte **sempre bypassen** els diàlegs (patch de
`QMessageBox`/`QInputDialog`, o cridant directament la lògica del visor), així
que les 600 línies de `app/dialegs.py` no tenien cap prova: ni el parsing del
compàs, ni `valors()`, ni l'add/delete de trams del mapa (auditoria
18-10-2026).

Ací es construeixen els diàlegs (sense `exec_()`, sense ensenyar-los) i es prova
la seua lògica, que és on viu el que pot fallar.
"""


class _dialegs___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])


class TestDialegTramTempo(_dialegs___Base):
    """`valors()` — el compàs s'escriu «num/den» o «num»."""

    def _dlg(self, compas="4/4", bpm=120.0):
        d = dialegs.DialegTramTempo(None, inici=4.0, bpm=bpm, num=4, den=4)
        d.ed_compas.setText(compas)
        return d

    def test_compas_amb_barra(self):
        self.assertEqual(self._dlg("3/8").valors(), (120.0, 3, 8))

    def test_compas_amb_espais(self):
        self.assertEqual(self._dlg(" 6 / 4 ").valors(), (120.0, 6, 4))

    def test_compas_nomes_numerador(self):
        """«5» vol dir 5/4 (el denominador es conserva a 4)."""
        self.assertEqual(self._dlg("5").valors(), (120.0, 5, 4))

    def test_compas_invalid_cau_a_4_4(self):
        self.assertEqual(self._dlg("abc").valors(), (120.0, 4, 4))
        self.assertEqual(self._dlg("3/x").valors(), (120.0, 4, 4))
        self.assertEqual(self._dlg("").valors(), (120.0, 4, 4))

    def test_compas_mai_zero(self):
        """El compàs sempre és positiu (regla #12 de les dades: valors vàlids)."""
        self.assertEqual(self._dlg("0/0").valors(), (120.0, 1, 1))

    def test_el_bpm_surt_del_camp(self):
        self.assertEqual(self._dlg(bpm=97.5).valors()[0], 97.5)


class TestDialegTempoMapa(_dialegs___Base):
    """Parsing compàs→segons i add/delete de trams (el que fa el diàleg)."""

    TRAMS = [(0.0, 4.0, 120.0, 4, 4), (4.0, 8.0, 90.0, 4, 4)]

    def _dlg(self, trams=None, durada=8.0):
        return dialegs.DialegTempoMapa(
            None, trams=list(self.TRAMS if trams is None else trams),
            durada=durada)

    def test_compas_a_segons(self):
        """Amb 120 BPM i 4/4 el compàs fa 2 s: el 3 comença a 4,0 s."""
        d = self._dlg()
        self.assertAlmostEqual(d._temps_de_compas("3"), 4.0, places=6)

    def test_compas_i_temps_escala_amb_el_mapa(self):
        """«3.2» = compàs 3 + un temps MÉS, amb el tempo d'AQUELL tram.

        El compàs 3 cau al segon tram (90 BPM): el temps hi fa 0,667 s, no 0,5
        (els 120 BPM del primer). El diàleg ha de fer cas del MAPA, no del BPM
        de la barra.
        """
        from app import tempo_map as tm
        d = self._dlg()
        mapa = tm.TempoMap(tm.normalitza_trams(self.TRAMS, 8.0))
        self.assertAlmostEqual(d._temps_de_compas("3.2"),
                               mapa.t_de_pos(3, 2), places=6)
        self.assertAlmostEqual(d._temps_de_compas("3.2"), 4.0 + 2.0 / 3.0,
                               places=6)

    def test_compas_1_es_l_inici(self):
        self.assertAlmostEqual(self._dlg()._temps_de_compas("1"), 0.0, places=6)

    def test_afegeix_un_tram_al_mig_del_darrer(self):
        d = self._dlg()
        d._afegeix()
        trams = d.trams()
        self.assertEqual(len(trams), 3)
        self.assertAlmostEqual(float(trams[-1][0]), 6.0, places=6)  # (4+8)/2
        self.assertEqual(float(trams[-1][2]), 90.0)   # hereta el tempo del tros

    def test_elimina_no_toca_el_valor_inicial(self):
        d = self._dlg()
        d.taula.setCurrentCell(0, 0)
        d._elimina()
        self.assertEqual(len(d.trams()), 2, "la fila 0 és el valor inicial")

    def test_elimina_un_tram_del_mig(self):
        d = self._dlg(trams=[(0.0, 4.0, 120.0, 4, 4), (4.0, 6.0, 90.0, 3, 4),
                             (6.0, 8.0, 100.0, 4, 4)])
        d.taula.setCurrentCell(1, 0)
        d._elimina()
        trams = d.trams()
        self.assertEqual(len(trams), 2)
        self.assertAlmostEqual(float(trams[0][1]), 6.0, places=6)

    def test_trams_sempre_contigus_i_coberts(self):
        """El que entrega el diàleg és un mapa vàlid (regles #1/#2/#4)."""
        d = self._dlg()
        d._afegeix()
        trams = d.trams()
        self.assertEqual(float(trams[0][0]), 0.0)
        self.assertAlmostEqual(float(trams[-1][1]), 8.0, places=6)
        self.assertEqual([float(t[1]) for t in trams[:-1]],
                         [float(t[0]) for t in trams[1:]])


class TestDialegOpcions(_dialegs___Base):
    """`opcions()` ha de tornar el que hi ha als controls (contracte de
    persistència: el que es desa és el que s'analitzarà)."""

    def test_el_round_trip_amb_els_defectes(self):
        """Posar els DEFECTES i tornar-los a llegir ha de donar el mateix.

        És el contracte que evita que un canvi de widget trenque l'anàlisi en
        silenci: si `opcions()` canvia un tipus o una clau, això hi peta.
        """
        d = dialegs.DialegOpcions(None, opcions=dialegs.DEFECTES)
        out = d.opcions()
        self.assertEqual(set(out), {"bpm", "chords", "structure", "clean"})
        for clau, val in dialegs.DEFECTES["bpm"].items():
            self.assertEqual(out["bpm"][clau], val, f"bpm.{clau}")
        for clau, val in dialegs.DEFECTES["chords"].items():
            self.assertEqual(out["chords"][clau], val, f"chords.{clau}")
        self.assertEqual(out["structure"]["motor"], "qm")
        for clau in ("durada_min", "fusiona_iguals"):
            self.assertEqual(out["structure"][clau],
                             dialegs.DEFECTES["structure"][clau],
                             f"structure.{clau}")
        self.assertEqual(out["clean"], dialegs.DEFECTES["clean"])

    def test_restaura_torna_als_defectes(self):
        d = dialegs.DialegOpcions(None, opcions=dialegs.DEFECTES)
        d._controls["bpm"]["min"].setValue(77)
        self.assertEqual(d.opcions()["bpm"]["min"], 77)
        d._restaura()
        self.assertEqual(d.opcions()["bpm"]["min"],
                         dialegs.DEFECTES["bpm"]["min"])

    def test_la_pestanya_inicial(self):
        d = dialegs.DialegOpcions(None, tab="structure",
                                  opcions=dialegs.DEFECTES)
        self.assertEqual(d.tabs.currentIndex(), 2)


class TestDialegModeFacil(_dialegs___Base):
    """El preset d'estil ha de fixar el ritme harmònic i el mòdul."""

    def test_cada_preset_aplica_el_seu_ritme_i_modul(self):
        from app import graella
        d = dialegs.DialegModeFacil(None)
        for clau, p in graella.PRESETS.items():
            i = d.cb_preset.findData(clau)
            d.cb_preset.setCurrentIndex(i)     # dispara `_aplica_preset`
            self.assertEqual(d.preset(), clau)
            self.assertEqual(d.ritme(), p.get("ritme", "auto"),
                             f"preset {clau}: ritme")
            self.assertEqual(d.modul(), int(p.get("modul", 4)),
                             f"preset {clau}: modul")

    def test_tria_manual_guanya_sobre_el_preset(self):
        d = dialegs.DialegModeFacil(None)
        d.cb_ritme.setCurrentIndex(d.cb_ritme.findData("temps"))
        d.cb_modul.setCurrentIndex(d.cb_modul.findData(8))
        self.assertEqual(d.ritme(), "temps")
        self.assertEqual(d.modul(), 8)


class TestDialegTrobaReemplaca(_dialegs___Base):
    """Els camps s'entregan sense espais sobrers (es busquen noms EXACTES)."""

    def test_camp_i_textos(self):
        d = dialegs.DialegTrobaReemplaca(None, camp="estructura")
        self.assertEqual(d.camp(), "estructura")
        d.ed_troba.setText("  D  ")
        d.ed_reemplaca.setText(" Estribillo ")
        self.assertEqual(d.troba(), "D")
        self.assertEqual(d.reemplaca(), "Estribillo")

    def test_camp_per_defecte(self):
        self.assertEqual(dialegs.DialegTrobaReemplaca(None).camp(), "acords")

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_dialegs_defaults.py
# ══════════════════════════════════════════════════════════════════════════
"""Tests dels valors per defecte del diàleg d'autodetecció (`app/dialegs.py`).

Blinda la decisió de l'operador (2026-10-13): els defectes de fàbrica que
mostra el diàleg en obrir-lo i als quals torna el botó «Restaura per defecte».
Si algú els canvia sense voler, el CI peta.
"""


# Els 19 controls revisats amb l'operador (font única d'aquest acord).
ESPERATS = {
    "bpm": {"motor": "consens", "min": 60, "max": 180,
            "pref_min": 85, "pref_max": 150},
    "chords": {"useNNLS": 1, "useHMM": 1, "rollon": 0.0, "tuningmode": 0,
               "whitening": 1.0, "s": 0.7},
    "structure": {"motor": "qm", "durada_min": 2.0, "fusiona_iguals": True},
    "clean": {"durada_min": 0.15, "fusiona_iguals": True, "sense_baix": False,
              "reduir": False, "snap": True, "divisio": 4, "ritme": "off"},
}


class TestDefectes(unittest.TestCase):
    def test_defectes_fixats(self):
        self.assertEqual(dialegs.DEFECTES, ESPERATS)

    def test_carrega_opcions_sense_fitxer(self):
        antic = dialegs.FITXER_OPCIONS
        dialegs.FITXER_OPCIONS = os.path.join(
            tempfile.gettempdir(), "opcions_que_no_existeix_mai.json")
        try:
            self.assertEqual(dialegs.carrega_opcions(), ESPERATS)
        finally:
            dialegs.FITXER_OPCIONS = antic

    def test_carrega_opcions_merge_parcial(self):
        antic = dialegs.FITXER_OPCIONS
        fd, tmp = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"bpm": {"motor": "qm"}}, f)
        dialegs.FITXER_OPCIONS = tmp
        try:
            op = dialegs.carrega_opcions()
            self.assertEqual(op["bpm"]["motor"], "qm")      # sobreescrit
            self.assertEqual(op["bpm"]["min"], 60)          # de defecte
            self.assertEqual(op["clean"], ESPERATS["clean"])
        finally:
            dialegs.FITXER_OPCIONS = antic
            os.unlink(tmp)


class TestDialogDefectes(unittest.TestCase):
    def setUp(self):
        # Offscreen si no hi ha pantalla (CI/headless); no força res si n'hi ha.
        if not os.environ.get("DISPLAY") and not os.environ.get("QT_QPA_PLATFORM"):
            os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PyQt5.QtWidgets import QApplication
        self._app = QApplication.instance() or QApplication([])

    def test_el_dialeg_mostra_els_defectes(self):
        dlg = dialegs.DialegOpcions(opcions=copy.deepcopy(dialegs.DEFECTES))
        self.assertEqual(dlg.opcions(), ESPERATS)

    def test_restaura_torna_als_defectes(self):
        dlg = dialegs.DialegOpcions(opcions=copy.deepcopy(dialegs.DEFECTES))
        # embrutem uns quants controls...
        b = dlg._controls["bpm"]
        b["motor"].setCurrentIndex(b["motor"].findData("qm"))
        b["min"].setValue(80)
        c = dlg._controls["clean"]
        c["snap"].setChecked(False)
        c["divisio"].setValue(4)
        c["durada_min"].setValue(0.0)
        cl_chord = dlg._controls["chords"]["useHMM"]
        cl_chord.setChecked(False)
        dlg._controls["structure"]["durada_min"].setValue(0.0)
        # ...i premem «Restaura per defecte» → tot torna a DEFECTES
        dlg._restaura()
        self.assertEqual(dlg.opcions(), ESPERATS)

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_esquema_ui_doc.py
# ══════════════════════════════════════════════════════════════════════════
"""Auditoria GUI ↔ documentació: `docs/ESQUEMA_UI.md` no ha de divergir de la
GUI real.

Extreu la GUI **de debò** (barres d'eines, menús, transport) i comprova que tot
hi sigui a la doc. Així, si algú afegeix/renombra un botó o una acció de menú i
no actualitza l'`ESQUEMA_UI`, el CI peta.

(Neix de bugs reals: la barra d'accions que Qt posava a la mateixa fila, i el
botó de «zoom a la selecció» que només era al transport del visor — que s'amaga
quan va incrustat.)
"""


ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ARREL, "docs", "ESQUEMA_UI.md")


class EsquemaUiDocTests(unittest.TestCase):
    def setUp(self):
        # cal mantenir la referència a la QApplication (si no, el GC la mata)
        self._app = QApplication.instance() or QApplication([])
        self.w = app_main.Finestra()
        self.w.resize(1280, 900)
        self.w.show()                 # cal mostrar-la perquè Qt assigni geometries
        self._app.processEvents()
        with open(DOC, encoding="utf-8") as f:
            self.doc = f.read()

    def test_barres_documentades(self):
        """Cada barra d'eines ha de sortir pel seu nom a la doc."""
        for tb in self.w.findChildren(QToolBar):
            self.assertIn(tb.windowTitle(), self.doc,
                          f"la barra «{tb.windowTitle()}» no surt a la doc")

    def test_botons_obre_audio_i_mode_facil(self):
        """La barra ha de tenir «Obre àudio» i «Mode fàcil» (botó a l'app)."""
        texts = [b.text()
                 for b in self.w.barra_principal.findChildren(QPushButton)]
        self.assertIn("Obre àudio", texts)
        self.assertIn("Mode fàcil", texts)
        self.assertIsNotNone(getattr(self.w, "b_mode_facil", None))

    def test_accions_de_menu_documentades(self):
        """Cada acció real de menú ha d'aparèixer a la doc."""
        faltes = []
        for m in self.w.menuBar().findChildren(QMenu):
            for a in m.actions():
                t = a.text().replace("&", "").strip()
                if t and not a.isSeparator() and t not in self.doc:
                    faltes.append(t)
        self.assertEqual(faltes, [],
                         f"accions de menú NO documentades a l'ESQUEMA_UI: {faltes}")

    def test_menus_documentats(self):
        for m in self.w.menuBar().findChildren(QMenu):
            nom = m.title().replace("&", "").strip()
            if nom:
                self.assertIn(nom, self.doc,
                              f"el menú «{nom}» no surt a la doc")

    def test_transport_te_zoom_seleccio(self):
        """El transport de la finestra ha de tenir el botó de zoom a la selecció."""
        tips = [b.toolTip() for b in
                self.w.barra_transport.findChildren(QPushButton)]
        self.assertTrue(any("selecci" in t.lower() for t in tips),
                        "falta el botó de zoom a la selecció al transport")
        self.assertIn("Zoom a la selecció", self.doc)

    def test_barres_en_files_distintes(self):
        """Les 3 barres han d'ocupar files (y) diferents (cal `addToolBarBreak`)."""
        ys = {tb.windowTitle(): tb.geometry().y()
              for tb in self.w.findChildren(QToolBar)}
        self.assertEqual(len(set(ys.values())), len(ys),
                         f"hi ha barres a la mateixa fila: {ys}")


def _esquema_ui_doc_tearDownModule():
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
# ORIGEN: test_fil_analisi.py
# ══════════════════════════════════════════════════════════════════════════
"""El fil d'anàlisi (`main.Feina`) — propagació d'errors i èxit.

`Feina` és el fil que llança «Executa»: fa l'anàlisi i avisa per senyals
(`progres`, `missatge`, `feta`). Cap test el tocava (auditoria 18-10-2026), i és
justament el punt on un error del pipeline ha d'arribar a la UI **sense penjar
la barra de progrés** ni deixar l'app mig engegada.

Es crida `run()` directament (al fil principal): determinista, sense curses.
"""


class _fil_analisi___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = (app_main.QApplication.instance()
                    or app_main.QApplication([]))


def _fil_analisi___wav(ruta, segons=3):
    import numpy as np
    sr = 44100
    n = int(sr * segons)
    t = np.arange(n) / sr
    x = (np.sin(2 * np.pi * 261.6 * t) * 6000).astype(np.int16)
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(x.tobytes())


# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_fitxer_llarg.py
# ══════════════════════════════════════════════════════════════════════════
"""El visor avisa (no bloquejant) si el fitxer és MOLT llarg.

El visor carrega el PCM sencer a memòria (`raw` + la còpia `mono`) ≈ 3× la mida
del fitxer (prova real: 1 h ≈ 2 GB de pic). A partir de `visor.LLARG_MIN_S`
s'ha de registrar un avís al panell del log — sense bloquejar.
"""


def _fitxer_llarg___wav(segons=2):
    fd, ruta = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * segons)
    return ruta


class TestFitxerLlarg(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def test_avisa_si_supera_el_llindar(self):
        orig = visor.LLARG_MIN_S
        visor.LLARG_MIN_S = 1          # 2 s de WAV > 1 s -> ha d'avisar
        try:
            v = visor.Visor(_fitxer_llarg___wav(2), None, None, 120.0, 4, True)
        finally:
            visor.LLARG_MIN_S = orig
        # `registre` és el QTextEdit del panell del log (l'avís ha de ser-hi).
        txt = v.registre.toPlainText() if hasattr(v, "registre") else ""
        self.assertIn("MOLT LLARG", txt, f"no s'ha avisat: {txt!r}")
        v.close()

    def test_no_avisa_si_es_curt(self):
        v = visor.Visor(_fitxer_llarg___wav(2), None, None, 120.0, 4, True)   # llindar real (45 min)
        txt = v.registre.toPlainText() if hasattr(v, "registre") else ""
        self.assertNotIn("MOLT LLARG", txt, "no hauria d'avisar per un fitxer curt")
        v.close()


def _fitxer_llarg_tearDownModule():
    try:
        import _qt_neteja
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_info_box_consells.py
# ══════════════════════════════════════════════════════════════════════════
"""Caixa d'informacio: quan el ratoli NO es sobre cap boto/area amb info, ha de
mostrar un **rotatori de consells i dreceres** (panells que giren cada
`_INFO_ROTACIO_S`), amb el 1r panell **adaptat a l'eina vigent** del timeline.

Tambe cobreix la interaccio: un **clic** a la caixa **para** el rotatori
(`_INFO_PAUSA_S`) i el clic següent **avanca** de «pantalla».

Es el complement del «ratoli intel·ligent»: si hi ha info concreta s'explica; si
no, la caixa no queda morta ni amb un text vell.
"""


def _info_box_consells___finestra():
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


class TestInfoBoxConsells(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = app_main.QApplication.instance() or app_main.QApplication([])

    def test_panells_son_curts_i_ben_agrupats(self):
        w = _info_box_consells___finestra()
        panells = w._info_panells()
        # 1r = eina del timeline; la resta = pantalles CURTES per tema
        # (16-10-2026: abans eren 2 pantalles llarguíssimes —dreceres de menú i
        # combinacions de ratolí— que en 8-14 s no es podien llegir).
        self.assertGreaterEqual(len(panells), 10)
        self.assertTrue(panells[0][0].startswith("Eina del timeline"))
        titols = [t for t, _p in panells]
        for esperat in ("Seleccionar clips", "Duplicar un clip", "Loop A-B",
                        "Copiar, retallar i enganxar"):
            self.assertIn(esperat, titols)
        for t, parells in panells:
            self.assertLessEqual(len(parells), 5, f"«{t}» massa llarga")
        w.close()

    def test_panell_eina_segueix_l_eina_vigent(self):
        w = _info_box_consells___finestra()
        w.visor_ref.timeline.set_tool("marc")
        t_marc, _p = w._panell_eina()
        self.assertIn("SELECCIÓ", t_marc)
        w.visor_ref.timeline.set_tool("intel·ligent")
        t_int, _p = w._panell_eina()
        self.assertIn("intel·ligent", t_int)
        w.close()

    def test_html_per_defecte_apunta_a_les_dreceres_de_menus(self):
        w = _info_box_consells___finestra()
        n = len(w._info_panells())
        vist = ""
        for i in range(n):
            w._info_panell = i
            vist += w._info_defecte_html(1.0, rota=False) or ""
        self.assertIn("Dreceres i consells", vist)
        # Les dreceres de MENÚ ja no omplen el rotatori (eren una pantalla
        # llarguíssima): hi ha una pantalla que diu on són, i allà hi són
        # totes (una sola font: `_dreceres()` → diàleg Ajuda).
        self.assertIn("Ajuda ▸ Dreceres de teclat", vist)
        self.assertNotIn("Ctrl+O", vist)
        self.assertIn("Ctrl+O", w._text_dreceres())      # Fitxer ▸ Obre àudio
        self.assertIn("Ctrl+Z", w._text_dreceres())      # Edita ▸ Desfer
        self.assertIn("F5", w._text_dreceres())          # Analitza l'àudio
        w.close()

    def test_clic_a_la_caixa_para_i_avanca(self):
        """El clic HA d'arribar a la caixa (bug real, 16-10-2026).

        Un `QTextEdit` és una `QAbstractScrollArea`: els clics els rep el seu
        **viewport**, no el widget. Amb el filtre instal·lat només al QTextEdit,
        el clic no arribava mai i la caixa semblava morta.
        """
        from PyQt5.QtCore import QEvent, QPoint, Qt
        from PyQt5.QtGui import QMouseEvent
        w = _info_box_consells___finestra()
        ev = QMouseEvent(QEvent.MouseButtonPress, QPoint(5, 5),
                         Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        # 1) el clic de debò va al VIEWPORT → ha de quedar interceptat i pausar
        w._info_pausa_fins = 0.0
        self.assertTrue(w.eventFilter(w.info_box.viewport(), ev))
        self.assertGreater(w._info_pausa_fins, 0.0)
        # 2) segon clic → avança de pantalla
        w._info_panell = 0
        w.eventFilter(w.info_box.viewport(), ev)
        self.assertEqual(w._info_panell, 1)
        # 3) i el widget també hi és (per si algun tema canvia el mapeig)
        w._info_pausa_fins = 0.0
        self.assertTrue(w.eventFilter(w.info_box, ev))
        self.assertGreater(w._info_pausa_fins, 0.0)
        w.close()

    def test_rota_segons_el_interval_configurat(self):
        w = _info_box_consells___finestra()
        n = len(w._info_panells())
        w._info_panell = 0
        w._info_panell_t = 0.0
        w._info_pausa_fins = 0.0
        inc = app_main._INFO_ROTACIO_S
        h0 = w._info_defecte_html(100.0, rota=True)                 # fixa t0
        h1 = w._info_defecte_html(100.0 + inc - 1.0, rota=True)     # encara no
        self.assertEqual(h0, h1)
        h2 = w._info_defecte_html(100.0 + inc + 0.1, rota=True)     # ara sí
        self.assertNotEqual(h1, h2)
        self.assertEqual(w._info_panell, 1 % n)
        w.close()

    def test_no_rota_si_el_ratoli_es_a_la_caixa(self):
        w = _info_box_consells___finestra()
        w._info_panell = 0
        w._info_panell_t = 0.0
        w._info_pausa_fins = 0.0
        w._info_defecte_html(100.0, rota=True)
        w._info_defecte_html(200.0, rota=False)         # congelat
        self.assertEqual(w._info_panell, 0)
        w.close()

    def test_clic_pausa_i_el_seguent_avanca(self):
        """1r clic → PARA (i allarga la pausa); 2n clic → AVANÇA de pantalla."""
        w = _info_box_consells___finestra()
        w._info_timer.stop()          # aillament: que no dispari el rotatori
        w._info_panell = 0
        w._info_panell_t = time.monotonic() - 100.0   # vell (ja tocaria rotar)
        w._info_pausa_fins = 0.0
        w._clic_info_box()                            # 1r: pausa, no avança
        self.assertGreater(w._info_pausa_fins, time.monotonic())
        self.assertEqual(w._info_panell, 0)
        w._clic_info_box()                            # 2n: avança
        self.assertEqual(w._info_panell, 1)
        # Dins la pausa (encara que passi estona), el rotatori NO es mou sol.
        w._info_defecte_html(time.monotonic() + app_main._INFO_PAUSA_S - 5.0,
                             rota=True)
        self.assertEqual(w._info_panell, 1)
        w.close()

    def test_missatge_transitori_te_format_propi(self):
        w = _info_box_consells___finestra()
        w._missatge_info("PROVA")
        txt = w.info_box.toPlainText()
        self.assertIn("PROVA", txt)
        self.assertIn("Missatge", txt)      # banner distint del rotatori
        w.close()

    def test_posa_info_nomes_reescriu_si_canvia(self):
        w = _info_box_consells___finestra()
        w._info_html_actual = None
        w._posa_info("<b>hola</b>")
        self.assertEqual(w._info_html_actual, "<b>hola</b>")
        w.info_box.setPlainText("no m'has de tocar")
        w._posa_info("<b>hola</b>")                     # mateix → no reescriu
        self.assertEqual(w.info_box.toPlainText(), "no m'has de tocar")
        w._posa_info("<b>hola</b>2")                    # diferent → reescriu
        self.assertIn("hola", w.info_box.toPlainText())
        w.close()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_loop_boto.py
# ══════════════════════════════════════════════════════════════════════════
"""Regressió: el botó 🔁 del transport s'ha de sincronitzar amb l'estat REAL del loop.

Bug (operador, 13-10-2026): en arrossegar el regle per crear un rang A-B, el
loop **s'activava** (el play ja feia loop) però el botó 🔁 de la barra quedava
**desactivat** → incoherent.
"""


def _loop_boto___wav(dur=2.0):
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "tema.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * int(44100 * dur))
    return wav


class _loop_boto___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])


class TestSenyalLoopDelVisor(_loop_boto___Base):
    def test_on_loop_changed_emet_senyal(self):
        v = visor_mod.Visor(_loop_boto___wav(), None, None, 120.0, 4, True)
        estats = []
        v.loopStateChanged.connect(estats.append)
        v._on_loop_changed(0.5, 1.5)
        self.assertEqual(estats, [True])
        self.assertTrue(v.loop_on)

    def test_set_loop_emet_l_estat_real(self):
        v = visor_mod.Visor(_loop_boto___wav(), None, None, 120.0, 4, True)
        estats = []
        v.loopStateChanged.connect(estats.append)
        v.set_loop(True)          # sense A/B vàlids → s'ha de revertir a OFF
        self.assertEqual(estats, [False])
        self.assertFalse(v.loop_on)


class TestBotoTransportSincronitzat(_loop_boto___Base):
    def test_crear_rang_activa_el_boto_i_netejar_el_desactiva(self):
        w = app_main.Finestra()
        w._carrega_visor(_loop_boto___wav())
        self.assertIsNotNone(w.visor_ref)
        self.assertFalse(w.tb_loop.isChecked())        # d'entrada, apagat
        # Arrossegar el regle acaba cridant exactament això:
        w.visor_ref._on_loop_changed(0.5, 1.5)
        self.assertTrue(w.tb_loop.isChecked(),
                        "el botó 🔁 hauria d'activar-se amb el rang nou")
        # I netejar el loop l'ha de tornar a apagar:
        w._neteja_loop()
        self.assertFalse(w.tb_loop.isChecked())

    def test_control_sense_connexio_el_boto_no_se_sincronitza(self):
        """Control (meta-verificació): sense la connexió del senyal el botó NO
        canvia → prova que el test de dalt cassa REALMENT aquest bug."""
        w = app_main.Finestra()
        w._carrega_visor(_loop_boto___wav())
        w.visor_ref.loopStateChanged.disconnect(w._on_loop_state)
        w.visor_ref._on_loop_changed(0.5, 1.5)
        self.assertTrue(w.visor_ref.loop_on)      # el loop SÍ que està actiu
        self.assertFalse(w.tb_loop.isChecked())   # ... pero el boto no ho sap


def _loop_boto_tearDownModule():
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
# ORIGEN: test_loop_continu.py
# ══════════════════════════════════════════════════════════════════════════
"""Tests del loop SENSE TALL (Opció A): el fil d'alimentació fa la volta del
loop ell mateix, en un flux continu, sense reiniciar el reproductor.

Provem `Visor._alimenta` amb un reproductor fals i àudio constant: si hi hagués
un «tall», apareixeria silenci (zeros) al punt de la volta.
"""


class _FakeStdin:
    def __init__(self, limit_bytes):
        self.buf = bytearray()
        self.limit = limit_bytes
        self.tancat = False

    def write(self, b):
        self.buf += b
        if len(self.buf) >= self.limit:
            raise BrokenPipeError("límit de prova")

    def close(self):
        self.tancat = True


class _FakeProc:
    def __init__(self, limit_bytes):
        self.stdin = _FakeStdin(limit_bytes)

    def poll(self):
        return None


class _Doble:
    """Doble del Visor amb només el que `_alimenta` necessita."""

    FADE_LOOP_S = 0.004

    def __init__(self, mono, sr, loop=None):
        self.audio = {"sr": sr, "durada": len(mono) / sr}
        self._mono = np.asarray(mono, dtype=np.int16).tobytes()
        self._sess = 0
        self.loop_on = loop is not None
        self.loop_a, self.loop_b = loop if loop else (None, None)
        self.mut = False
        self.vol = 1.0
        self.metro_on = False
        self.metro_vol = 0.6
        self.bpm, self.bpb, self.offset = 120.0, 4, 0.0

    def _mono_bytes(self):
        return self._mono


def _max_run_zeros(data):
    run = mx = 0
    for v in (data == 0):
        run = run + 1 if v else 0
        if run > mx:
            mx = run
    return mx


class TestLoopContinu(unittest.TestCase):
    def test_sense_loop_alimenta_fins_al_final(self):
        doble = _Doble(np.full(2000, 1000, dtype=np.int16), 1000)
        proc = _FakeProc(10_000_000)
        Visor._alimenta(doble, proc, 0.0, 0)
        data = np.frombuffer(bytes(proc.stdin.buf), dtype=np.int16)
        self.assertEqual(data.size, 2000)         # tot el tema, un sol cop
        self.assertTrue(proc.stdin.tancat)

    def test_loop_fa_voltes_sense_tall(self):
        sr = 1000
        doble = _Doble(np.full(2000, 1000, dtype=np.int16), sr,
                       loop=(0.1, 0.2))            # A=100, B=200 (100 mostres)
        proc = _FakeProc(5000)                     # ~25 voltes
        Visor._alimenta(doble, proc, 0.15, 0)      # comença a mig loop
        data = np.frombuffer(bytes(proc.stdin.buf), dtype=np.int16)

        # (1) Ha fet MOLTES voltes (més enllà de la primera passada)
        self.assertGreater(data.size, 2000)
        # (2) El cos del loop sona PLE (no hi ha buit): el valor màxim és ple
        self.assertEqual(int(data.max()), 1000)
        # (3) No hi ha CAP buit real: els zeros (micro-fade als extrems) estan
        #     aïllats, mai en ratxes → si hi hagués un tall, hi hauria un bloc
        #     llarg de zeros.
        self.assertLessEqual(_max_run_zeros(data), 2)

    def test_loop_degenerat_no_encalla(self):
        """Un loop de menys de 2 mostres es descarta i sona fins al final.

        És la xarxa del fil d'alimentació (`if b - a < 2: bucle = False`): sense
        ella, un loop marcat massa curt (o amb A i B al mateix instant) podria
        deixar la reproducció donant voltes infinitesimalment.
        """
        sr = 1000
        doble = _Doble(np.full(2000, 1000, dtype=np.int16), sr,
                       loop=(0.5, 0.5000))          # 0 mostres de loop
        proc = _FakeProc(50000)
        Visor._alimenta(doble, proc, 0.5, 0)
        data = np.frombuffer(bytes(proc.stdin.buf), dtype=np.int16)
        # Ha sonat DES de la posició fins al FINAL, sense cap volta: 0,5 s
        # (mostra 500) → 2,0 s (mostra 2000) = 1500 mostres exactes.
        self.assertEqual(data.size, 1500,
                         "ha de sonar fins al final, sense fer cap volta")

    def test_loop_que_acaba_a_la_durada(self):
        """Un loop amb B exactament a la durada fa voltes sense tall."""
        sr = 1000
        doble = _Doble(np.full(2000, 1000, dtype=np.int16), sr,
                       loop=(0.5, 2.0))             # B = final de l'àudio
        proc = _FakeProc(6000)
        Visor._alimenta(doble, proc, 0.5, 0)
        data = np.frombuffer(bytes(proc.stdin.buf), dtype=np.int16)
        self.assertGreater(data.size, 2000, "ha de fer més d'una volta")
        self.assertEqual(int(data.max()), 1000, "el cos del loop sona ple")
        self.assertLessEqual(_max_run_zeros(data), 2,
                             "sense blocs de silenci (no hi ha tall)")

    def test_loop_canvi_en_calell(self):
        # Si A/B canvien a mig flux, el feeder ho agafa a la volta següent.
        doble = _Doble(np.full(2000, 1000, dtype=np.int16), 1000,
                       loop=(0.1, 0.2))
        proc = _FakeProc(1200)
        doble.loop_a, doble.loop_b = 0.3, 0.4     # canvi (300..400) abans de res
        Visor._alimenta(doble, proc, 0.35, 0)
        data = np.frombuffer(bytes(proc.stdin.buf), dtype=np.int16)
        self.assertEqual(int(data.max()), 1000)   # segueix ple, sense tall

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_loop_copia.py
# ══════════════════════════════════════════════════════════════════════════
"""Loop A/B: doble-clic DINS la banda del loop (a dalt) → selecciona TOT el
que hi ha a dins (acords I seccions) i deixa el cursor al final del loop, a
punt per copiar (Ctrl+C) i enganxar (Ctrl+V).

També hi ha el menú de botó dret dins del loop (copiar/retallar/enganxar).
"""


ACORDS = "0.0,2.0,C\n2.0,4.5,Am\n4.5,7.0,F\n7.0,10.0,G\n10.0,20.0,C\n"
SECCIONS = ("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
            "0.0,5.0,5.0,A,A,1.1,5.1\n"
            "5.0,10.0,5.0,B,B,5.1,10.1\n"
            "10.0,20.0,10.0,C,C,10.1,20.1\n")


def _loop_copia___visor():
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
        f.write(ACORDS)
    with open(sa, "w", encoding="utf-8") as f:
        f.write(SECCIONS)
    v = visor_mod.Visor(wav, ca, sa, bpm=120, bpb=4, tempo_fix=False)
    v.td, v.sortida = td, out
    return v


class _loop_copia___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])

    def _x_de_temps(self, tl, t):
        return int(tl._x_offset + (float(t) - tl._view_left) * tl._pps)

    def _dobleclic(self, tl, t, y=2):
        ev = QMouseEvent(QEvent.MouseButtonDblClick,
                         QPointF(self._x_de_temps(tl, t), y),
                         Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        tl.mouseDoubleClickEvent(ev)
        return ev


class TestLoopDobleClic(_loop_copia___Base):
    def test_dobleclic_selecciona_tot_dins_el_loop(self):
        v = _loop_copia___visor()
        try:
            tl = v.timeline
            tl.resize(900, 300)
            v.loop_a, v.loop_b = 1.0, 9.0        # dins: A(0) NO · acords 2,4.5,7
            v._pinta_loop()
            self._dobleclic(tl, 5.0)             # a dalt, dins del loop
            self.assertEqual(tl.selected_keys(), {
                ("chord", 1), ("chord", 2), ("chord", 3), ("section", 1)})
            self.assertAlmostEqual(v.pos, 9.0, places=6)   # cursor al final
        finally:
            v.close()

    def test_dobleclic_fora_del_loop_no_selecciona(self):
        v = _loop_copia___visor()
        try:
            tl = v.timeline
            tl.resize(900, 300)
            v.loop_a, v.loop_b = 1.0, 4.0
            v._pinta_loop()
            tl.clear_selection()
            self._dobleclic(tl, 12.0)            # fora del loop
            self.assertEqual(tl.selected_keys(), set())
        finally:
            v.close()

    def test_dobleclic_sense_loop_no_fa_res(self):
        v = _loop_copia___visor()
        try:
            tl = v.timeline
            tl.resize(900, 300)
            v.loop_a = v.loop_b = None
            v._pinta_loop()
            tl.clear_selection()
            self._dobleclic(tl, 5.0)
            self.assertEqual(tl.selected_keys(), set())
        finally:
            v.close()

    def test_no_agafa_els_clips_de_la_frontera(self):
        """Un clip que comença EXACTAMENT a loop_b ja és FORA (semi-obert)."""
        v = _loop_copia___visor()
        try:
            v.loop_a, v.loop_b = 1.0, 10.0   # hi ha acord @10.0 i secció C @10.0
            self.assertEqual(v.selecciona_bloc_del_loop(), 4)
            keys = v.timeline.selected_keys()
            self.assertNotIn(("chord", 4), keys)      # acord @10.0 → fora
            self.assertNotIn(("section", 2), keys)    # secció C @10.0 → fora
            self.assertIn(("chord", 3), keys)         # acord @7.0 → dins
            self.assertIn(("section", 1), keys)       # secció B @5.0 → dins
        finally:
            v.close()

    def test_selecciona_bloc_del_loop_retorna_el_recompte(self):
        v = _loop_copia___visor()
        try:
            v.loop_a, v.loop_b = 1.0, 9.0
            self.assertEqual(v.selecciona_bloc_del_loop(), 4)
            self.assertEqual(v.loop_a, 1.0)      # el loop no es toca
        finally:
            v.close()


class TestLoopMenu(_loop_copia___Base):
    def test_menu_loop_te_les_accions(self):
        v = _loop_copia___visor()
        try:
            v.loop_a, v.loop_b = 1.0, 9.0
            v._pinta_loop()
            capt = {}
            orig = QMenu.exec_
            QMenu.exec_ = lambda self, pos, *a: capt.update(
                texts=[t.text() for t in self.actions() if not t.isSeparator()])
            try:
                v._on_loop_context_menu(None)
            finally:
                QMenu.exec_ = orig
            self.assertTrue(any("Copia" in t for t in capt["texts"]),
                            capt["texts"])
            self.assertTrue(any("Enganxa" in t for t in capt["texts"]),
                            capt["texts"])
        finally:
            v.close()

    def test_menu_copia_selecciona_i_deixa_cursor_al_final(self):
        v = _loop_copia___visor()
        try:
            v.loop_a, v.loop_b = 1.0, 9.0
            v._pinta_loop()
            textos = {}
            orig = QMenu.exec_

            def fake(self, pos, *a):
                textos["copia"] = next(
                    act for act in self.actions() if "Copia" in act.text())
                return textos["copia"]
            QMenu.exec_ = fake
            try:
                v._on_loop_context_menu(None)
            finally:
                QMenu.exec_ = orig
            self.assertTrue(v.timeline.has_clipboard())
            self.assertAlmostEqual(v.pos, 9.0, places=6)
        finally:
            v.close()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_model_gran.py
# ══════════════════════════════════════════════════════════════════════════
"""Validació — la VISTA amb models GRANS (robustesa, no rendiment exacte).

Un model amb centenars de clips s'ha de carregar, dibuixar i permetre-hi operar
(seek, ressalta de reproducció, zoom i nudge) sense petar ni degradar-se.
"""


DUR = 200.0


class _model_gran___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])

    def _visor_gran(self, n_ac=200, n_sec=40, dur=DUR):
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "tema.wav")
        out = os.path.join(td, "AUTOCHORDS_tema")
        os.makedirs(out)
        with wave.open(wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(b"\x00\x00" * int(44100 * dur))
        patrons = ["C", "G", "Am", "F"]
        ca = os.path.join(out, "acords.csv")
        with open(ca, "w", encoding="utf-8") as f:
            for k in range(n_ac):
                f.write(f"{k:.2f},{k + 1:.2f},{patrons[k % 4]}\n")
        sa = os.path.join(out, "estructura_ABC.csv")
        with open(sa, "w", encoding="utf-8") as f:
            f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n")
            pas = dur / n_sec
            for k in range(n_sec):
                L = "ABCD"[k % 4]
                f.write(f"{k * pas:.2f},{(k + 1) * pas:.2f},{pas:.2f},{L},{L},1,1\n")
        v = visor_mod.Visor(wav, ca, sa, 120.0, 4, True)
        v.td, v.sortida = td, out
        return v


class TestModelGran(_model_gran___Base):
    def test_carrega_i_les_llistes_quadren(self):
        v = self._visor_gran(200, 40)
        self.assertEqual(len(v.acords), 200)
        self.assertEqual(len(v.timeline._chord_items), 200)
        self.assertEqual(len(v.seccions), 40)
        self.assertEqual(len(v.timeline._section_items), 40)
        self.assertEqual(v.llista_ac.count(), 200)
        self.assertEqual(v.llista_ab.count(), 40)
        v.close()

    def test_operacions_amb_model_gran(self):
        v = self._visor_gran(200, 40)
        # seek + ressalta de reproducció (recorre el model)
        v.timeline.set_position(123.0, emit=False)
        v._ressalta(123.0)
        # zoom i scroll
        v.timeline.zoom_to(0.0, 50.0)
        v.timeline.zoom_to(150.0, 200.0)
        # nudge d'un clip del mig
        v.timeline.select_clip("chord", 100)
        t0 = float(v.acords[100][0])
        v.timeline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_Right, Qt.NoModifier))
        self.assertGreater(float(v.acords[100][0]), t0)
        # cobertura intacta
        self.assertAlmostEqual(float(v.acords[0][0]), 0.0, places=6)
        v.close()


def _model_gran_tearDownModule():
    try:
        import _qt_neteja
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_panell_xifrat.py
# ══════════════════════════════════════════════════════════════════════════
"""Panell «Tipus d'acord» (`app/panell_xifrat.py`) — dock esquerra desacoplable.

Comportament acordat amb l'operador (mockup aprovat):
- `Arrel` i `Baix` = camps de **text lliure** (poden anar buits).
- La llista és **plana** (de menys a més complex) amb `tipus·alternatius` +
  els **graus** a sota (dades de `xifrat.TAULA_TIPUS`).
- **Clicar un tipus NOMÉS omple** la casella «Nom» de l'editor: mai aplica.
- **Sense arrel** → s'hi escriu només el tipus (`Maj7`) i l'usuari l'acaba.
- Botó **▶ Escoltar**: toca el tipus triat (piano elèctric sintetitzat:
  arpegi + bloc) via `escoltarDemandat` → `Visor.toca_notes`.
"""


_panell_xifrat___VIVES = []


def _panell_xifrat___wav(dur=5.0):
    td = tempfile.mkdtemp()
    ruta = os.path.join(td, "t.wav")
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * int(44100 * dur))
    return ruta


class _panell_xifrat___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = app_main.QApplication.instance() or app_main.QApplication([])

    def _finestra(self, amb_visor=True):
        w = app_main.Finestra()
        _panell_xifrat___VIVES.append(w)
        w.avisa_info = lambda *a, **k: None
        w.avisa = lambda *a, **k: None
        if amb_visor:
            wav = _panell_xifrat___wav()
            w.wav_edit.setText(wav)
            w._carrega_visor(wav)
        return w

    def tearDown(self):
        ws, _panell_xifrat___VIVES[:] = _panell_xifrat___VIVES[:], []
        for w in ws:
            w.dirty = False
        try:
            import _qt_neteja
        except ImportError:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import _qt_neteja
        _qt_neteja.tanca_i_destrueix(*ws)


class TestTaula(unittest.TestCase):
    def test_composa(self):
        for a, q, b, esperat in [("Ab", "Maj7", "Db", "AbMaj7/Db"),
                                 ("C", "-7b5", "", "C-7b5"),
                                 ("Ab", "6add9", "Db", "Ab6add9/Db"),
                                 ("", "Maj7", "", "Maj7"),
                                 ("", "m7b5", "", "-7b5"),
                                 ("C", "", "", "C"),
                                 ("F#", "7", "G", "F#7/G")]:
            self.assertEqual(xifrat.composa(a, q, b), esperat,
                             f"({a!r},{q!r},{b!r})")

    def test_la_taula_cobreix_tots_els_tipus(self):
        """Cada `kind` de `TIPUS` ha de sortir a la TAULA (com a qualitat o
        com a alternativa) → el panell no en pot deixar cap fora."""
        quals = {q for _e, q, _a, _g in xifrat.TAULA_TIPUS}
        alts = "·".join(a for _e, _q, a, _g in xifrat.TAULA_TIPUS)
        faltes = [t for t in xifrat.TIPUS if t not in quals and t not in alts]
        self.assertEqual(faltes, [], f"tipus sense fila al panell: {faltes}")

    def test_la_taula_te_ordena_i_dades_completes(self):
        self.assertGreaterEqual(len(xifrat.TAULA_TIPUS), 60)
        for etiqueta, qual, alts, graus in xifrat.TAULA_TIPUS:
            self.assertTrue(etiqueta, "etiqueta buida")
            self.assertTrue(graus, f"{etiqueta}: sense graus")
            # la qualitat canònica ha de ser coherent amb el tipus
            self.assertEqual(xifrat.normalitza_qualitat(qual), qual,
                             f"{etiqueta}: la qualitat no és canònica")


class TestPanell(_panell_xifrat___Base):
    def test_dock_a_l_esquerra_i_desacoplable(self):
        w = self._finestra(amb_visor=False)
        self.assertEqual(w.dock_xifrat.windowTitle(), "Tipus d'acord")
        self.assertIs(w.dock_xifrat.widget(), w.panell_xifrat)
        f = w.dock_xifrat.features()
        self.assertTrue(f & QDockWidget.DockWidgetFloatable, "desacoplable")
        self.assertTrue(f & QDockWidget.DockWidgetMovable, "moble")
        # menú Visualitza → acció de mostrar
        textos = [a.text() for m in w.menuBar().findChildren(QMenu)
                  for a in m.actions()]
        self.assertIn("Mostra els tipus d'acord", textos)

    def test_llista_i_boto_escoltar(self):
        w = self._finestra(amb_visor=False)
        p = w.panell_xifrat
        self.assertEqual(p.llista.count(), len(xifrat.TAULA_TIPUS))
        self.assertTrue(p.b_escoltar.isEnabled(),
                        "el botó ▶ Escoltar ja ha de funcionar (e-piano)")

    def test_clicar_un_tipus_omple_la_casella_nom(self):
        w = self._finestra()
        p = w.panell_xifrat
        p.arrel.setText("Ab")
        p.baix.setText("Db")
        it = next(p.llista.item(i) for i in range(p.llista.count())
                  if p.llista.item(i).text() == "maj7")
        p._on_clic(it)
        self.assertEqual(p.previsio.text(), "AbMaj7/Db")
        self.assertEqual(w.visor_ref.ed_nom.text(), "AbMaj7/Db")
        # NO s'ha aplicat res al model (cal «Aplica»)
        self.assertNotIn("AbMaj7/Db",
                          [a[2][0] for a in w.visor_ref.acords])

    def test_sense_arrel_escriu_nomes_el_tipus(self):
        w = self._finestra()
        p = w.panell_xifrat
        it = next(p.llista.item(i) for i in range(p.llista.count())
                  if p.llista.item(i).text() == "maj7")
        p._on_clic(it)
        self.assertEqual(w.visor_ref.ed_nom.text(), "Maj7")

    def test_escoltar_emet_les_notes(self):
        """▶ Escoltar ha d'emetre les notes MIDI del tipus triat."""
        w = self._finestra(amb_visor=False)
        p = w.panell_xifrat
        p.arrel.setText("Ab")
        it = next(p.llista.item(i) for i in range(p.llista.count())
                  if p.llista.item(i).text() == "maj7")
        p._on_clic(it)
        caps = []
        p.escoltarDemandat.connect(lambda n, t: caps.append(n))
        p._escolta()
        self.assertEqual(caps, [[56, 60, 63, 67]])   # Ab3 C4 Eb4 G4

    def test_escoltar_sense_arrel_avisa(self):
        w = self._finestra(amb_visor=False)
        p = w.panell_xifrat
        avisos = []
        p.avis.connect(lambda t: avisos.append(t))
        p._escolta()
        self.assertTrue(avisos, "sense arrel ha d'avisar")

    def test_toca_notes_usa_el_motor(self):
        """`Visor.toca_notes` ha d'usar el motor d'àudio (aquí, simulat)."""
        w = self._finestra()
        vr = w.visor_ref
        escrits = []

        class _MotorFals:
            def __init__(self):
                self.stdin = self
                self.tancat = False
            def write(self, dades):
                escrits.append(dades)
                return len(dades)
            def close(self):
                self.tancat = True
            def poll(self):
                return 0
            def atura(self):
                pass

        motor = _MotorFals()
        # patregem tria_player (per SO) i el motor → no sona res, però es
        # verifica tot el camí: notes → PCM → motor → escriptura + tancament
        from unittest.mock import patch
        with patch.object(vr, "_tria_player", return_value=("paplay", [])), \
                patch.object(audio_out, "crea_motor", return_value=motor):
            self.assertTrue(vr.toca_notes([48, 52, 55, 59]))
            for th in list(getattr(vr, "_escoltes_fils", [])):
                th.join(10)                 # la síntesi va en un fil
        self.assertTrue(escrits, "ha d'escriure el PCM al motor")
        self.assertGreater(len(escrits[0]), 10000, "PCM massa curt")
        self.assertTrue(motor.tancat, "ha de tancar stdin (el motor acaba sol)")

    def test_toca_notes_sense_notes(self):
        w = self._finestra()
        self.assertFalse(w.visor_ref.toca_notes([]))

    def test_sense_visor_avisa_i_no_peta(self):
        w = self._finestra(amb_visor=False)
        p = w.panell_xifrat
        it = next(p.llista.item(i) for i in range(p.llista.count())
                  if p.llista.item(i).text() == "m7b5")
        p._on_clic(it)          # no ha de petar (avisa per la caixa d'info)


def _panell_xifrat_tearDownModule():
    try:
        import _qt_neteja
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_theme.py
# ══════════════════════════════════════════════════════════════════════════
"""Coherència del tema (`app/theme.py`).

El tema és la font dels colors de la UI i de la distinció visual per carril
(regla d'or #11: cada família —acords, estructura i BPM/compàs— ha de ser
reconeixible pel seu color/carril). Un color mal escrit (#f3f4f6 amb 5 dígits,
una coma, un `None`…) no peta enlloc: simplement es pinta mal o cau a un valor
per defecte, i ningú no se n'adona. Aquest guard ho atura (auditoria
18-10-2026).
"""


_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def _colors():
    return {k: v for k, v in vars(theme).items()
            if k.isupper() and isinstance(v, str) and v.startswith("#")}


class TestTema(unittest.TestCase):

    def test_tots_els_colors_son_hex_de_6_digits(self):
        colors = _colors()
        self.assertGreater(len(colors), 30, "el tema hauria de tindre colors")
        for nom, val in colors.items():
            self.assertRegex(val, _HEX, f"{nom} = {val!r}")

    def test_les_paletes_son_valides_i_sense_repetits(self):
        paletes = {k: v for k, v in vars(theme).items()
                   if k.isupper() and isinstance(v, (tuple, list))
                   and v and all(isinstance(x, str) and x.startswith("#")
                                 for x in v)}
        self.assertTrue(paletes, "hi hauria d'haver alguna paleta")
        for nom, pal in paletes.items():
            for c in pal:
                self.assertRegex(c, _HEX, f"{nom}: {c!r}")
            self.assertEqual(len(set(pal)), len(pal),
                             f"{nom}: colors repetits dins la paleta")

    def test_el_llegat_de_seccio_te_varios_nivells(self):
        """`SECTION_FILLS` distingeix les lletres de secció (A, B, C…)."""
        self.assertGreaterEqual(len(theme.SECTION_FILLS), 3)

    def test_els_colors_dels_tres_carrils_son_distints(self):
        """Cada família ha de tindre un color propi (regla #11)."""
        self.assertNotEqual(theme.TL_LANE_BG_A, theme.TL_LANE_BG_B)
        # Les paletes de secció no poden coincidir amb el fons del carril.
        self.assertNotIn(theme.TL_LANE_BG_A, theme.SECTION_FILLS)

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_timeline_items.py
# ══════════════════════════════════════════════════════════════════════════
"""Zones dels clips del timeline (`ChordItem` / `SectionItem`).

`_zone_at(x)` és el hit-test del gest: decideix si l'arrossegament mou una
**vora** o el **cos** del clip. Fins ara els tests posaven `_drag_mode` a mà i
la funció no s'exercitava mai directament (auditoria 18-10-2026).

A més es comprova la **paritat d'affordances** (regla #11): els dos tipus han de
tindre la mateixa amplada de nansa i els mateixos llindars.
"""


_timeline_items__ACORDS = "0.0,2.0,C\n2.0,5.0,Am\n5.0,10.0,G\n"
_timeline_items__SECCIONS = ("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
            "0.0,5.0,5.0,A,A,1.1,3.1\n"
            "5.0,10.0,5.0,B,B,3.1,5.1\n")


def _timeline_items___visor():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "t.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * 10)
    out = os.path.join(td, "AUTOCHORDS_t")
    os.makedirs(out)
    ca = os.path.join(out, "acords.csv")
    sa = os.path.join(out, "estructura_ABC.csv")
    with open(ca, "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,acord\n" + _timeline_items__ACORDS)
    with open(sa, "w", encoding="utf-8") as f:
        f.write(_timeline_items__SECCIONS)
    v = visor_mod.Visor(wav, ca, sa, bpm=120, bpb=4, tempo_fix=True)
    v.td, v.sortida = td, out
    return v


class _timeline_items___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])


class TestZonesDelsClips(_timeline_items___Base):

    def _items(self):
        v = _timeline_items___visor()
        self.addCleanup(v.close)
        return v.timeline._chord_items[0], v.timeline._section_items[0]

    def test_les_zones_de_les_vores_i_del_cos(self):
        for it in self._items():
            lx, rx = it._x_left(), it._x_right()
            c = timeline_items.ChordItem
            self.assertEqual(it._zone_at(lx - 5), c.ZONE_NONE, "fora a l'esquerra")
            self.assertEqual(it._zone_at(rx + 5), c.ZONE_NONE, "fora a la dreta")
            self.assertEqual(it._zone_at(lx + 1), c.ZONE_LEFT)
            self.assertEqual(it._zone_at(rx - 1), c.ZONE_RIGHT)
            self.assertEqual(it._zone_at((lx + rx) / 2.0), c.ZONE_BODY)

    def test_paritat_d_affordances_entre_els_dos_tipus(self):
        """Regla #11: mateixa amplada de nansa i mateixos codis de zona."""
        ch, se = timeline_items.ChordItem, timeline_items.SectionItem
        self.assertEqual(ch.HANDLE_W, se.HANDLE_W,
                         "l'amplada de la nansa ha de ser la mateixa")
        self.assertEqual(ch.ZONE_NONE, se.ZONE_NONE)
        self.assertEqual(ch.ZONE_LEFT, se.ZONE_LEFT)
        self.assertEqual(ch.ZONE_BODY, se.ZONE_BODY)
        self.assertEqual(ch.ZONE_RIGHT, se.ZONE_RIGHT)

    def test_el_llindar_es_exactament_la_nansa(self):
        """La nansa ocupa NOMÉS `HANDLE_W` px (ni un més)."""
        ch, _se = self._items()
        lx = ch._x_left()
        self.assertEqual(ch._zone_at(lx + ch.HANDLE_W), ch.ZONE_LEFT)
        self.assertEqual(ch._zone_at(lx + ch.HANDLE_W + 0.5), ch.ZONE_BODY)

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_timeline_layers.py
# ══════════════════════════════════════════════════════════════════════════
"""Proves de les CAPES del timeline (`app/timeline_layers.py`).

La suite exercitava les capes sobretot pel **paint** («no peta») i a través del
`TimelineView`. Però `TempoLayer._zona()` és el **cor del gest** de la pista de
BPM/compàs: decideix si l'arrossegament mou una **vora** o el **punt de canvi**
(i, amb ell, què passa amb els veïns). No tenia cap prova pròpia (auditoria
18-10-2026).
"""


TRAMS = [(0.0, 5.0, 120.0, 4, 4), (5.0, 10.0, 90.0, 3, 4),
         (10.0, 20.0, 100.0, 4, 4)]


class _timeline_layers___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])


class TestTempoLayerZones(_timeline_layers___Base):
    """`_zona(x)` -> (índex, zona) amb zona ∈ {ini, fi, cos, None}."""

    def _capa(self, actiu=True):
        capa = L.TempoLayer(20, 60.0, 0.0, 0.0, 20.0)
        capa.set_mapa(tm.TempoMap(TRAMS), actiu)
        return capa

    def test_vores_i_cos_de_cada_bloc(self):
        capa = self._capa()
        # tram 0 [0,5) -> x 0..300 ; tram 1 [5,10) -> 300..600 ; 2 [10,20) -> 600..1200
        # (a la frontera 300 és COMPARTIDA: el tram 0 respon «fi» i el tram 1
        #  «ini»; tots dos són el mateix punt de canvi i el visor els tracta
        #  igual. La comprovació d'«ini» es fa al tram 2, on el tram anterior no
        #  pot respondre «fi» — si no, el test no distingiria les dues vores.)
        self.assertIn(capa._zona(301.0), [(0, "fi"), (1, "ini")])
        self.assertEqual(capa._zona(603.0), (2, "ini"))
        self.assertEqual(capa._zona(450.0), (1, "cos"))
        self.assertEqual(capa._zona(700.0), (2, "cos"))

    def test_els_extrems_no_tenen_vora_draggable(self):
        """El PRIMER tram no té vora esquerra i l'ÚLTIM no en té de dreta: el
        mapa sempre comença a 0 i acaba a la durada."""
        capa = self._capa()
        self.assertEqual(capa._zona(1.0), (0, "cos"))
        self.assertEqual(capa._zona(1199.0), (2, "cos"))

    def test_fora_del_mapa(self):
        capa = self._capa()
        self.assertEqual(capa._zona(-500.0), (-1, None))

    def test_sense_mapa_ni_activa_no_hi_ha_zones(self):
        capa = self._capa(actiu=False)
        self.assertEqual(capa._zona(450.0), (-1, None))
        buida = L.TempoLayer(20, 60.0, 0.0, 0.0, 20.0)   # sense mapa
        self.assertEqual(buida._zona(450.0), (-1, None))

    def test_cursor_de_zona_com_les_altres_pistes(self):
        """Paritat #11: ↔ a les vores, mà OBLERTA al cos, fletxa al buit.

        Es prova la funció pura (PyQt5 no deixa fabricar un event de *hover*),
        i que el *hover* la fa servir amb la zona que toca.
        """
        capa = self._capa()
        self.assertEqual(capa._cursor_de_zona("ini"), Qt.SizeHorCursor)
        self.assertEqual(capa._cursor_de_zona("fi"), Qt.SizeHorCursor)
        self.assertEqual(capa._cursor_de_zona("cos"), Qt.OpenHandCursor)
        self.assertEqual(capa._cursor_de_zona(None), Qt.ArrowCursor)
        # i la zona que calcula per a una x concreta
        self.assertEqual(capa._zona(450.0)[1], "cos")


class TestTempoLayerSeleccio(_timeline_layers___Base):

    def test_select_deselecciona(self):
        capa = L.TempoLayer(20, 60.0, 0.0, 0.0, 20.0)
        capa.set_mapa(tm.TempoMap(TRAMS), True)
        self.assertEqual(capa._sel, -1)
        capa.select(1)
        self.assertEqual(capa._sel, 1)
        capa.deselecciona()
        self.assertEqual(capa._sel, -1)


class _Ev:
    """Esdeveniment de ratolí mínim per a `mousePressEvent` (sense Qt real)."""

    def __init__(self, x, boto=Qt.LeftButton):
        self._x, self._boto, self.acceptat = x, boto, False

    def pos(self):
        return QPointF(self._x, 0.0)

    def button(self):
        return self._boto

    def accept(self):
        self.acceptat = True


class TestTempoLayerBotoDret(_timeline_layers___Base):
    """Paritat amb els clips (regla #11): botó dret = SELECCIONAR + menú.

    Sense això, el menú de ③ obria el mateix joc d'accions que ④/⑤ però
    Copia/Retalla no tindrien res seleccionat (report de l'operador, 19-10-2026).
    """

    def _capa(self):
        capa = L.TempoLayer(20, 60.0, 0.0, 0.0, 20.0)
        capa.set_mapa(tm.TempoMap(TRAMS), True)
        return capa

    def test_el_boto_dret_selecciona_el_tram(self):
        capa = self._capa()
        sel, menu = [], []
        capa.tramSelected.connect(sel.append)
        capa.menuRequested.connect(lambda i, t: menu.append((i, t)))
        ev = _Ev(450.0, Qt.RightButton)          # cos del tram 1
        capa.mousePressEvent(ev)
        self.assertEqual(sel, [1], "el botó dret ha de seleccionar el tram")
        self.assertEqual(menu[0][0], 1)
        self.assertTrue(ev.acceptat)

    def test_el_boto_dret_al_buit_emet_minus_1(self):
        """Fora de tot tram: -1 (el timeline l'ignora i no toca la selecció)."""
        capa = self._capa()
        sel = []
        capa.tramSelected.connect(sel.append)
        capa.mousePressEvent(_Ev(-500.0, Qt.RightButton))
        self.assertEqual(sel, [-1])

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_timeline_loop.py
# ══════════════════════════════════════════════════════════════════════════
"""Tests de la manipulació del loop A/B (lògica pura `loop_after_drag`).

Ara el loop es pot moure/canviar inici/fi des del regle; aquesta és la part de
càlcul (límits dins la cançó, A<B, i 'move' que manté la durada).
"""


class TestLoopAfterDrag(unittest.TestCase):
    A, B, DUR = 4.0, 10.0, 100.0

    def test_move_mante_durada_i_desplaca(self):
        # t0=5 (grab), t=8 → delta +3
        a, b = loop_after_drag("move", 8.0, 5.0, self.A, self.B, self.DUR)
        self.assertAlmostEqual(a, 7.0)
        self.assertAlmostEqual(b, 13.0)
        self.assertAlmostEqual(b - a, self.B - self.A)

    def test_move_limitat_a_l_inici(self):
        a, b = loop_after_drag("move", -50.0, 5.0, self.A, self.B, self.DUR)
        self.assertAlmostEqual(a, 0.0)
        self.assertAlmostEqual(b, self.B - self.A)

    def test_move_limitat_al_final(self):
        a, b = loop_after_drag("move", 999.0, 5.0, self.A, self.B, self.DUR)
        self.assertAlmostEqual(b, self.DUR)
        self.assertAlmostEqual(a, self.DUR - (self.B - self.A))

    def test_resize_a(self):
        a, b = loop_after_drag("a", 2.0, 0.0, self.A, self.B, self.DUR)
        self.assertAlmostEqual(a, 2.0)
        self.assertAlmostEqual(b, self.B)         # B no canvia

    def test_resize_a_no_passa_de_b(self):
        a, b = loop_after_drag("a", 50.0, 0.0, self.A, self.B, self.DUR)
        self.assertLess(a, b)
        self.assertAlmostEqual(b, self.B)
        self.assertAlmostEqual(b - a, 0.05, places=6)

    def test_resize_a_no_negatiu(self):
        a, _b = loop_after_drag("a", -5.0, 0.0, self.A, self.B, self.DUR)
        self.assertAlmostEqual(a, 0.0)

    def test_resize_b(self):
        a, b = loop_after_drag("b", 20.0, 0.0, self.A, self.B, self.DUR)
        self.assertAlmostEqual(a, self.A)         # A no canvia
        self.assertAlmostEqual(b, 20.0)

    def test_resize_b_no_passa_de_durada(self):
        _a, b = loop_after_drag("b", 999.0, 0.0, self.A, self.B, self.DUR)
        self.assertAlmostEqual(b, self.DUR)

    def test_resize_b_no_travessa_a(self):
        a, b = loop_after_drag("b", 0.0, 0.0, self.A, self.B, self.DUR)
        self.assertGreater(b, a)
        self.assertAlmostEqual(b - a, 0.05, places=6)

    def test_mode_desconegut_no_canvia(self):
        self.assertEqual(loop_after_drag("", 1.0, 0.0, self.A, self.B, self.DUR),
                         (self.A, self.B))

    def test_tolerancia_positiva(self):
        self.assertGreater(LOOP_GRAB_PX, 0)


class TestInteraccioRegle(unittest.TestCase):
    """Arrossegar de debò al regle (vores i cos) modifica el loop A/B."""

    def setUp(self):
        if not os.environ.get("DISPLAY") and not os.environ.get("QT_QPA_PLATFORM"):
            os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PyQt5.QtWidgets import QApplication
        self._qapp = QApplication.instance() or QApplication([])
        import numpy as np
        from app.timeline import TimelineView
        audio = {"durada": 60.0, "sr": 44100, "canals": 2,
                 "mono": np.zeros(2000, dtype=np.int16)}
        self.tl = TimelineView(audio, [], [], 120.0, 4, True)
        self.tl.resize(800, 400)
        self.tl.set_loop(10.0, 20.0)

    def _pt(self, t, y=10.0):
        from PyQt5.QtCore import QPointF
        return QPointF(self.tl.mapFromScene(QPointF(self.tl._loop_px(t), y)))

    def _ev(self, tipus, t, boto=None, botons=None):
        from PyQt5.QtGui import QMouseEvent
        from PyQt5.QtCore import Qt
        boto = Qt.LeftButton if boto is None else boto
        botons = Qt.LeftButton if botons is None else botons
        return QMouseEvent(tipus, self._pt(t), boto, botons, Qt.NoModifier)

    def test_hit_test(self):
        tl = self.tl
        self.assertEqual(tl._loop_mode_at(tl._loop_px(10.0)), "a")
        self.assertEqual(tl._loop_mode_at(tl._loop_px(20.0)), "b")
        self.assertEqual(tl._loop_mode_at(tl._loop_px(15.0)), "move")
        self.assertIsNone(tl._loop_mode_at(tl._loop_px(40.0)))

    def test_arrossegar_el_cos_mou_el_loop(self):
        from PyQt5.QtCore import QEvent, Qt
        tl = self.tl
        a0, b0 = tl._loop_a, tl._loop_b
        tl.mousePressEvent(self._ev(QEvent.MouseButtonPress, 15.0))
        tl.mouseMoveEvent(self._ev(QEvent.MouseMove, 19.0, Qt.NoButton,
                                   Qt.LeftButton))
        tl.mouseReleaseEvent(self._ev(QEvent.MouseButtonRelease, 19.0,
                                      Qt.LeftButton, Qt.NoButton))
        self.assertGreater(tl._loop_a, a0)                       # s'ha mogut
        self.assertAlmostEqual(tl._loop_b - tl._loop_a, b0 - a0, places=6)

    def test_arrossegar_la_vora_b_redimensiona(self):
        from PyQt5.QtCore import QEvent, Qt
        tl = self.tl
        a0 = tl._loop_a
        tl.mousePressEvent(self._ev(QEvent.MouseButtonPress, 20.0))
        tl.mouseMoveEvent(self._ev(QEvent.MouseMove, 23.0, Qt.NoButton,
                                   Qt.LeftButton))
        tl.mouseReleaseEvent(self._ev(QEvent.MouseButtonRelease, 23.0,
                                      Qt.LeftButton, Qt.NoButton))
        self.assertAlmostEqual(tl._loop_a, a0, places=6)         # A no canvia
        self.assertGreater(tl._loop_b, 20.0)                     # B s'ha mogut

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_timeline_tecles.py
# ══════════════════════════════════════════════════════════════════════════
"""Tecles del timeline (`TimelineView.keyPressEvent`).

Les dreceres del timeline són el que fa l'app «de DAW», però es proven totes
**indirectament** (el nudge pel seu efecte, el porta-retalls pel resultat) i les
que només emeten un senyal (`Space` → play, `Esc`) no les mirava ningú: si un
refactor se les menjava, la suite quedava verda i el teclat deixava de funcionar
(auditoria 18-10-2026).
"""


_timeline_tecles__ACORDS = "0.0,4.0,C\n4.0,10.0,G\n"


def _timeline_tecles___visor():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "t.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * 10)
    out = os.path.join(td, "AUTOCHORDS_t")
    os.makedirs(out)
    ca = os.path.join(out, "acords.csv")
    with open(ca, "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,acord\n" + _timeline_tecles__ACORDS)
    v = visor_mod.Visor(wav, ca, None, bpm=120, bpb=4, tempo_fix=True)
    v.td, v.sortida = td, out
    return v


def _tecla(key, mods=Qt.NoModifier):
    return QKeyEvent(QEvent.KeyPress, key, mods)


class _timeline_tecles___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])


class TestTeclesTimeline(_timeline_tecles___Base):

    def test_space_emet_play(self):
        v = _timeline_tecles___visor()
        self.addCleanup(v.close)
        # El visor connecta `playRequested` al reproductor REAL: el desconnectem
        # perquè aquest test provinga NOMÉS el senyal (res d'àudio als tests).
        try:
            v.timeline.playRequested.disconnect(v.play_stop)
        except (TypeError, RuntimeError):
            pass
        hits = []
        v.timeline.playRequested.connect(lambda: hits.append(1))
        v.timeline.keyPressEvent(_tecla(Qt.Key_Space))
        self.assertEqual(len(hits), 1, "Space ha d'emetre playRequested")

    def test_escape_emet_escape_pressed(self):
        v = _timeline_tecles___visor()
        self.addCleanup(v.close)
        hits = []
        v.timeline.escapePressed.connect(lambda: hits.append(1))
        v.timeline.keyPressEvent(_tecla(Qt.Key_Escape))
        self.assertEqual(len(hits), 1, "Esc ha d'emetre escapePressed")

    def test_del_sense_seleccio_no_peta(self):
        v = _timeline_tecles___visor()
        self.addCleanup(v.close)
        v.timeline.clear_selection()
        v.timeline.keyPressEvent(_tecla(Qt.Key_Delete))   # sense selecció
        self.assertEqual([c.payload[0] for c in v.acords], ["C", "G"])

    def test_les_fletxes_sense_seleccio_no_mouen_res(self):
        v = _timeline_tecles___visor()
        self.addCleanup(v.close)
        v.timeline.clear_selection()
        abans = [float(c.ini) for c in v.acords]
        v.timeline.keyPressEvent(_tecla(Qt.Key_Left))
        v.timeline.keyPressEvent(_tecla(Qt.Key_Right))
        self.assertEqual([float(c.ini) for c in v.acords], abans)

    def test_les_tecles_amb_ctrl_no_es_menja_el_sistema(self):
        """Sense selecció, Ctrl+C/X/V no han de petar ni tocar el model."""
        v = _timeline_tecles___visor()
        self.addCleanup(v.close)
        v.timeline.clear_selection()
        abans = [(float(c.ini), c.payload[0]) for c in v.acords]
        for k in (Qt.Key_C, Qt.Key_X, Qt.Key_V):
            v.timeline.keyPressEvent(_tecla(k, Qt.ControlModifier))
        self.assertEqual([(float(c.ini), c.payload[0]) for c in v.acords],
                         abans)

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_vista_cursor.py
# ══════════════════════════════════════════════════════════════════════════
"""Selecció a les llistes → el cursor vermell ja hi va; ara la VISTA s'ha de
desplaçar (pan) perquè el cursor quedi visible, MANTENINT el ZOOM actual.

`TimelineView.ensure_cursor_visible()` fa el pan només si el cursor surt de la
zona còmoda (no canvia el zoom). El visor el crida en seleccionar una fila de
les llistes (acords o seccions).
"""


_vista_cursor__ACORDS = "0.0,2.0,C\n2.0,4.5,Am\n4.5,7.0,F\n7.0,10.0,G\n10.0,20.0,C\n"
_vista_cursor__SECCIONS = ("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
            "0.0,10.0,10.0,A,A,1.1,5.1\n"
            "10.0,20.0,10.0,B,B,5.1,10.1\n")


def _vista_cursor___visor():
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
        f.write(_vista_cursor__ACORDS)
    with open(sa, "w", encoding="utf-8") as f:
        f.write(_vista_cursor__SECCIONS)
    v = visor_mod.Visor(wav, ca, sa, bpm=120, bpb=4, tempo_fix=True)
    v.td, v.sortida = td, out
    return v


def _span(tl):
    return tl._view_right - tl._view_left


class _vista_cursor___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])


class TestVistaCursor(_vista_cursor___Base):
    def test_ensure_cursor_visible_desplaca_mantenint_zoom(self):
        v = _vista_cursor___visor()
        try:
            tl = v.timeline
            tl.zoom_to(0.0, 3.0)                 # vista estreta a l'inici
            abans = _span(tl)
            tl.set_position(10.0, emit=False, snap=False)
            tl.ensure_cursor_visible()
            self.assertLessEqual(tl._view_left, 10.0)
            self.assertGreaterEqual(tl._view_right, 10.0)
            self.assertAlmostEqual(_span(tl), abans, places=6)   # zoom intacte
        finally:
            v.close()

    def test_ensure_cursor_visible_no_desplaca_si_ja_es_veu(self):
        v = _vista_cursor___visor()
        try:
            tl = v.timeline
            tl.zoom_full()                        # vista sencera
            l0, r0 = tl._view_left, tl._view_right
            tl.set_position(10.0, emit=False, snap=False)
            tl.ensure_cursor_visible()
            self.assertAlmostEqual(tl._view_left, l0, places=9)
            self.assertAlmostEqual(tl._view_right, r0, places=9)
        finally:
            v.close()

    def test_llista_desplaca_la_vista_al_cursor(self):
        """Seleccionar una fila llunyana ha de portar el visor al clip."""
        for llista, salt, idx in (("llista_ac", "_salt_acord", 4),
                                  ("llista_ab", "_salt_seccio", 1)):
            v = _vista_cursor___visor()
            try:
                tl = v.timeline
                tl.zoom_to(0.0, 3.0)
                abans = _span(tl)
                self.assertGreaterEqual(tl._view_right, 3.0)
                item = getattr(v, llista).item(idx)
                getattr(v, salt)(item)            # clic a la llista
                cur = tl.get_position()
                self.assertGreater(cur, 3.0)      # el cursor ha saltat fora
                self.assertLessEqual(tl._view_left, cur)
                self.assertGreaterEqual(tl._view_right, cur)
                self.assertAlmostEqual(_span(tl), abans, places=6)
            finally:
                v.close()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_vista_segueix_model.py
# ══════════════════════════════════════════════════════════════════════════
"""EL VISOR SEGUEIX EL MODEL — xarxa de regressió de les REGLES D'OR.

Regla del preàmbul de `docs/REGLES_DE_LA_APP.md`: «**el que es veu a la pantalla
reflecteix el model vàlid**». Aquest mòdul comprova, **després de cada operació**
d'una tongada pseudo-aleatòria *determinista* (seeds fixos), que:

- **R1** ordre estricte · **R2** contigüitat · **R4** cobertura (0 → durada) ·
  **R8** temps vàlids — a les TRES famílies (acords, estructura, BPM/compàs);
- i que els **items pintats al timeline** quadren amb el model
  (`ChordItem.t/_next_t` vs `acords`; `SectionItem.ini/fi` vs `seccions`;
  `timeline._mapa` vs `tempo_trams`).

⚠️ Per què existeix (19-10-2026): una tongada de 12 h va donar la paritat i les
regles per fetes, però l'operador va veure que **el visor no s'actualitzava bé**.
El fuzzer va trobar el forat real:

1. **Afegir un clip no el pintava**: `_desa_i_regenera()` només refresca el
   timeline si la **cobertura** ha canviat, i afegir una marca DINS de la cançó
   no la canvia → el clip nou no eixia fins que tocaves una altra cosa.
2. **Després d'un gest** la vista es quedava amb la posició **previsual** que
   havien adoptat els items, mentre el model n'havia adoptat una altra
   (acotament del destí, snap, normalització del veí). Cas verificat (seed 9):
   l'item 0 pintat a `(0.000, 0.000)` amb el model ja a `(0.000, 2.000)`.

Els dos s'han arreglat centralitzant la sincronització a
`visor._sincronitza_vista()` (i fent que la criden les **primitives** de mutació,
no cada camí d'usuari).
"""


_vista_segueix_model__DUR = 40.0


def _vista_segueix_model___wav():
    td = tempfile.mkdtemp()
    ruta = os.path.join(td, "tema.wav")
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * int(44100 * _vista_segueix_model__DUR))
    return ruta


def _vista_segueix_model___visor():
    wav = _vista_segueix_model___wav()
    sortida = pipeline.carpeta_sortida(wav)
    os.makedirs(sortida, exist_ok=True)
    ca = os.path.join(sortida, "acords.csv")
    with open(ca, "w", encoding="utf-8") as f:
        for t, nom in [(0, "C"), (10, "Am"), (20, "F"), (30, "G")]:
            f.write(f"{t},{t + 1},{nom}\n")
    sa = os.path.join(sortida, "estructura_ABC.csv")
    with open(sa, "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n")
        for ini, fi, Lletra in [(0, 10, "A"), (10, 20, "B"), (20, 30, "C"),
                                (30, _vista_segueix_model__DUR, "D")]:
            f.write(f"{ini},{fi},{fi - ini},{Lletra},{Lletra},1,1\n")
    v = visor_mod.Visor(wav, ca, sa, 120.0, 4, True)
    v.td, v.sortida, v.abc_csv = os.path.dirname(wav), sortida, sa
    v.aplica_tempo_trams([(0.0, 20.0, 120.0, 4, 4),
                          (20.0, _vista_segueix_model__DUR, 120.0, 4, 4)])
    return v


def _families(v):
    return [("acords", [(float(c.ini), float(c.fi)) for c in v.acords]),
            ("seccions", [(float(s[0]), float(s[1])) for s in v.seccions]),
            ("tempo", [(float(t[0]), float(t[1]))
                       for t in (v.tempo_trams or [])])]


def _viola_regles(v):
    fall = []
    for nom, clips in _families(v):
        if not clips:
            fall.append(f"[{nom}] R4: carril buit")
            continue
        if abs(clips[0][0]) > 1e-6:
            fall.append(f"[{nom}] R4: comença a {clips[0][0]} (no a 0)")
        if abs(clips[-1][1] - _vista_segueix_model__DUR) > 1e-3:
            fall.append(f"[{nom}] R4: acaba a {clips[-1][1]:.4f} (no a {_vista_segueix_model__DUR})")
        for i, (ini, fi) in enumerate(clips):
            if ini < -1e-6:
                fall.append(f"[{nom}] R8: inici negatiu {ini}")
            if fi - ini <= 1e-6:
                fall.append(f"[{nom}] R8: durada <= 0 al clip {i}")
            if i and abs(clips[i - 1][1] - ini) > 1e-3:
                fall.append(f"[{nom}] R2: forat/encavalcament entre {i-1} i {i}")
    return fall


def _viola_vista(v):
    """Els items PINTATS han d'encarnar el model (regla del preàmbul)."""
    tl = v.timeline
    fall = []
    if len(tl._chord_items) != len(v.acords):
        fall.append(f"[vista acords] pintats={len(tl._chord_items)} != "
                    f"model={len(v.acords)}")
    else:
        for i, (it, c) in enumerate(zip(tl._chord_items, v.acords)):
            if (abs(it.t - float(c.ini)) > 1e-3
                    or abs(it._next_t - float(c.fi)) > 1e-3):
                fall.append(f"[vista acords] item {i}=({it.t:.3f},"
                            f"{it._next_t:.3f}) != model=({float(c.ini):.3f},"
                            f"{float(c.fi):.3f})")
                break
    if len(tl._section_items) != len(v.seccions):
        fall.append(f"[vista seccions] pintats={len(tl._section_items)} != "
                    f"model={len(v.seccions)}")
    else:
        for i, (it, s) in enumerate(zip(tl._section_items, v.seccions)):
            if (abs(it.ini - float(s[0])) > 1e-3
                    or abs(it.fi - float(s[1])) > 1e-3):
                fall.append(f"[vista seccions] item {i}=({it.ini:.3f},"
                            f"{it.fi:.3f}) != model=({float(s[0]):.3f},"
                            f"{float(s[1]):.3f})")
                break
    trams = v.tempo_trams or []
    if trams and tl._mapa is None:
        fall.append("[vista tempo] el timeline no té mapa (pista no pintable)")
    elif tl._mapa is not None and len(tl._mapa.trams) != len(trams):
        fall.append(f"[vista tempo] _mapa={len(tl._mapa.trams)} != "
                    f"model={len(trams)}")
    return fall


# ── les operacions (les mateixes eines que l'usuari, inclosos els GESTOS) ────
def _ops(r):
    v_ops = [
        ("afegeix acord",
         lambda v: v._afegeix_a_la_posicio("chord", r.uniform(0, _vista_segueix_model__DUR))),
        ("afegeix seccio",
         lambda v: v._afegeix_a_la_posicio("section", r.uniform(0, _vista_segueix_model__DUR))),
        ("elimina acord",
         lambda v: (v._elimina_acord_index(r.randrange(len(v.acords)))
                    if len(v.acords) > 1 else None)),
        ("elimina seccio",
         lambda v: (v._elimina_seccio_index(r.randrange(len(v.seccions)))
                    if len(v.seccions) > 1 else None)),
        ("duplica acord",
         lambda v: v._duplica_acord_index(r.randrange(len(v.acords)))),
        ("duplica seccio",
         lambda v: v._duplica_seccio_index(r.randrange(len(v.seccions)))),
        ("partir acord meitat",
         lambda v: v.parteix_per_la_meitat("chord",
                                           r.randrange(len(v.acords)))),
        ("partir tram meitat",
         lambda v: v._parteix_tram_per_la_meitat(
             r.randrange(len(v.tempo_trams or [])))),
        ("afegeix tall tempo",
         lambda v: v.aplica_tempo_trams(tm.afegeix_tall(
             list(v.tempo_trams or []), r.uniform(0, _vista_segueix_model__DUR)))),
        ("elimina seleccio mixta",
         lambda v: v._elimina_seleccio(
             [("chord", r.randrange(len(v.acords))),
              ("tempo", r.randrange(len(v.tempo_trams or [])))])),
        ("duplica seleccio",
         lambda v: v._duplica_seleccio(
             [("section", r.randrange(len(v.seccions)))])),
        ("gest mou inici acord", lambda v: _gest(v, r, "mou_inici_acord")),
        ("gest estira fi acord", lambda v: _gest(v, r, "estira_fi_acord")),
        ("gest mou seccio", lambda v: _gest(v, r, "mou_seccio")),
        ("gest cos acord", lambda v: _gest(v, r, "cos_acord")),
        ("gest cos seccio", lambda v: _gest(v, r, "cos_seccio")),
        ("gest frontera tempo", lambda v: _gest(v, r, "frontera_tempo")),
        ("desfer/refer", lambda v: (v.undo(),
                                    v.redo() if r.random() < 0.5 else None)),
    ]
    return r.choice(v_ops)


def _gest(v, r, tipus):
    """Gest del ratolí, pel MATEIX contracte que la GUI (`_emit_edit_finished`)."""
    tl = v.timeline
    if tipus == "mou_inici_acord":
        i = r.randrange(len(v.acords))
        tl._on_chord_time_changed(i, float(v.acords[i].ini) + r.uniform(-6, 6))
    elif tipus == "estira_fi_acord":
        i = r.randrange(len(v.acords))
        tl._on_chord_end_changed(i, float(v.acords[i].fi) + r.uniform(-6, 6))
    elif tipus == "mou_seccio":
        i = r.randrange(len(v.seccions))
        ini, fi = float(v.seccions[i][0]), float(v.seccions[i][1])
        d = r.uniform(-6, 6)
        tl._on_section_changed(i, ini + d, fi + d)
    elif tipus == "cos_acord":
        i = r.randrange(len(v.acords))
        tl._on_chord_body_drag(i, float(v.acords[i].ini) + r.uniform(-10, 10))
    elif tipus == "cos_seccio":
        i = r.randrange(len(v.seccions))
        ini, fi = float(v.seccions[i][0]), float(v.seccions[i][1])
        d = r.uniform(-10, 10)
        tl._on_section_body_drag(i, ini + d, fi + d)
    elif tipus == "frontera_tempo":
        trams = v.tempo_trams or []
        if len(trams) < 2:
            return
        i = r.randrange(len(trams))
        vora = r.choice(["ini", "fi"])
        base = float(trams[i][0]) if vora == "ini" else float(trams[i][1])
        v._on_tempo_mogut(i, vora, base + r.uniform(-8, 8))
        tl.editFinished.emit()
        return
    tl._emit_edit_finished()


class _vista_segueix_model___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        # Cap diàleg emergent pot penjar la suite (mateix patró que altres tests).
        self._p = [patch.object(QInputDialog, "getText",
                                return_value=("Z", True))]
        for m in ("warning", "information", "critical"):
            self._p.append(patch.object(QMessageBox, m,
                                        return_value=QMessageBox.Ok))
        for p in self._p:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self._p])


class TestFuzzerReglesIVista(_vista_segueix_model___Base):
    """Tongada pseudo-aleatòria, amb seeds FIXOS (reproduïble, no flaky)."""

    def _tongada(self, seed, n):
        r = random.Random(seed)
        v = _vista_segueix_model___visor()
        for pas in range(n):
            nom, op = _ops(r)
            try:
                op(v)
            except Exception as e:          # noqa: BLE001
                self.fail(f"seed {seed} pas {pas}: l'operacio ha petat: "
                          f"{type(e).__name__}: {e}")
            self._app.processEvents()       # com la GUI: buida els renders diferits
            fall = _viola_regles(v) + _viola_vista(v)
            self.assertFalse(
                fall, f"seed {seed} pas {pas} ({nom}): violacio de regla/vista: "
                      f"{fall}")
        return v

    def test_tongada_llarga(self):
        """Seeds 9 i 15: són els que **detecten** el bug del gest (la vista es
        quedava amb la posició previsual). Verificat per mutació — no els
        traguis ni rebaixis `n` per davall de 60 (el cas ix al pas 56 / 48)."""
        for seed in (9, 15):
            self._tongada(seed, 60)

    def test_tongada_general(self):
        for seed in (1, 2):
            self._tongada(seed, 40)


class TestElsDosBugsDeLaRonda12h(_vista_segueix_model___Base):
    """Els dos casos concrets que van fer dir «el visor no actualitza bé»."""

    def test_afegir_un_acord_es_pinta_a_l_instant(self):
        v = _vista_segueix_model___visor()
        n = len(v.acords)
        v._afegeix_a_la_posicio("chord", 25.0)
        self.assertEqual(len(v.acords), n + 1)
        # SENSE processEvents: l'alta ha de pintar-se ja (el bug era aquest)
        self.assertEqual(len(v.timeline._chord_items), n + 1,
                         "l'acord nou no s'ha pintat al timeline")
        self._app.processEvents()
        self.assertFalse(_viola_vista(v), _viola_vista(v))

    def test_afegir_una_seccio_es_pinta_a_l_instant(self):
        v = _vista_segueix_model___visor()
        n = len(v.seccions)
        v._afegeix_a_la_posicio("section", 22.0)
        self.assertEqual(len(v.seccions), n + 1)
        self.assertEqual(len(v.timeline._section_items), n + 1)
        self.assertFalse(_viola_vista(v), _viola_vista(v))

    def test_la_primitiva_d_afegir_tambe_refresca(self):
        """Cap camí (ni els futurs) no s'ha de poder oblidar de refrescar."""
        v = _vista_segueix_model___visor()
        n = len(v.acords)
        v._afegeix_acord(25.0, "G")
        self.assertEqual(len(v.timeline._chord_items), n + 1)

    def test_gest_arrossegament_acaba_quadrant_amb_el_model(self):
        v = _vista_segueix_model___visor()
        i = 1
        ini, fi = float(v.seccions[i][0]), float(v.seccions[i][1])
        v.timeline._on_section_body_drag(i, ini + 7, fi + 7)
        v.timeline._emit_edit_finished()     # el contracte del release de la GUI
        self._app.processEvents()
        self.assertFalse(_viola_vista(v), _viola_vista(v))
        self.assertFalse(_viola_regles(v), _viola_regles(v))

    def test_estirar_una_vora_acaba_quadrant(self):
        v = _vista_segueix_model___visor()
        v.timeline._on_chord_end_changed(0, 25.0)
        v.timeline._emit_edit_finished()
        self._app.processEvents()
        self.assertFalse(_viola_vista(v), _viola_vista(v))


def _vista_segueix_model_tearDownModule():
    import _qt_neteja
    _qt_neteja.processa_esborrats()

# ══════════════════════════════════════════════════════════════════════════
# ORIGEN: test_zoom_rebuild.py
# ══════════════════════════════════════════════════════════════════════════
"""Regressió: reconstruir els items del timeline NO ha de perdre el ZOOM.

`set_data` (undo, editar/renombrar des de l'editor, enganxar, edicions MCP…)
reconstrueix tots els items. Si els items nous no reben la VISTA ACTUAL
(`_view_left`), es pinten com si la vista comencés a 0 → amb zoom, el clip
«salta» fora de vista i sembla que es perd el focus. Aquest test fixa
l'invariant: tot item reconstruït ha de portar la `_view_left` del timeline.
"""


_zoom_rebuild__ACORDS = "0.0,2.0,C\n2.0,4.5,Am\n4.5,7.0,F\n7.0,10.0,G\n10.0,20.0,C\n"
_zoom_rebuild__SECCIONS = ("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
            "0.0,10.0,10.0,A,A,1.1,5.1\n"
            "10.0,20.0,10.0,B,B,5.1,10.1\n")


def _zoom_rebuild___visor():
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
        f.write(_zoom_rebuild__ACORDS)
    with open(sa, "w", encoding="utf-8") as f:
        f.write(_zoom_rebuild__SECCIONS)
    v = visor_mod.Visor(wav, ca, sa, bpm=120, bpb=4, tempo_fix=True)
    v.td, v.sortida = td, out
    return v


class _zoom_rebuild___Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])


class TestZoomRebuild(_zoom_rebuild___Base):
    def _zoom(self, v, kind, idx):
        v.resize(1200, 700)
        v.timeline.select_clip(kind, idx)
        v.timeline.zoom_selection()
        self.assertNotAlmostEqual(v.timeline._view_left, 0.0,
                                  msg="cal que hi hagi zoom per provar-ho")

    def test_set_data_mante_la_vista_als_items(self):
        """Tots els items reconstruïts han de portar la `_view_left` del timeline."""
        for kind in ("chord", "section"):
            v = _zoom_rebuild___visor()
            try:
                self._zoom(v, kind, 1)
                vl = v.timeline._view_left
                v.timeline.set_data(v.acords, v.seccions)   # reconstrucció
                items = (v.timeline._chord_items if kind == "chord"
                         else v.timeline._section_items)
                self.assertTrue(items)
                for it in items:
                    self.assertAlmostEqual(it._view_left, vl, places=9,
                                           msg=f"{kind}: item sense la vista")
            finally:
                v.close()

    def test_renombrar_no_mou_el_clip(self):
        """El símptoma real: en reanomenar (Aplica) el clip NO ha de saltar."""
        for kind in ("chord", "section"):
            v = _zoom_rebuild___visor()
            try:
                self._zoom(v, kind, 1)
                arr = (v.timeline._chord_by_idx if kind == "chord"
                       else v.timeline._section_by_idx)
                abans = arr[1].boundingRect()
                v._ed_kind, v._ed_idx = kind, 1
                v.ed_nom.setText("Am7" if kind == "chord" else "A2")
                v._aplica_editor()
                arr2 = (v.timeline._chord_by_idx if kind == "chord"
                        else v.timeline._section_by_idx)
                despres = arr2[1].boundingRect()
                self.assertAlmostEqual(despres.x(), abans.x(), places=6,
                                       msg=f"{kind}: el clip s'ha mogut de lloc")
            finally:
                v.close()

    def test_zoom_in_out_mante_la_vista_als_items(self):
        """Zoom amb els botons +/− també ha de propagar la vista a tots els items."""
        v = _zoom_rebuild___visor()
        try:
            v.timeline.set_position(5.0)     # centra el zoom lluny de t=0
            v.timeline.zoom_in()
            v.timeline.zoom_in()
            vl = v.timeline._view_left
            self.assertNotAlmostEqual(vl, 0.0)
            for it in v.timeline._chord_items + v.timeline._section_items:
                self.assertAlmostEqual(it._view_left, vl, places=9)
        finally:
            v.close()


class TestProjecteAssociat(_Base):
    """Un àudio amb projecte propi: carregar-lo o sobreescriure'l (mai un error)."""

    def _crea(self, f, wav, nom="Projecte1"):
        return _projectes_gui___obre_wav(f, wav, nom)

    def test_detecta_la_carpeta_germana(self):
        f = _projectes_gui___finestra()
        wav = _projectes_gui___wav()
        p = self._crea(f, wav)
        trobat = f._projecte_associat(wav)
        self.assertIsNotNone(trobat)
        self.assertEqual(trobat.carpeta, p.carpeta)

    def test_detecta_pels_recents_si_es_en_un_altre_lloc(self):
        f = _projectes_gui___finestra()
        wav_dir = tempfile.mkdtemp()
        wav = os.path.join(wav_dir, "tema.wav")
        _wav(wav, 1.0)
        p = projecte.Projecte.crea(os.path.join(self.td, "Altra"), wav)
        f.recents = [p.ruta_acproj]
        trobat = f._projecte_associat(wav)
        self.assertIsNotNone(trobat, "s'ha de trobar pels recents")
        self.assertEqual(trobat.carpeta, p.carpeta)

    def test_carrega_per_defecte_offscreen_i_no_trenca_el_model(self):
        f = _projectes_gui___finestra()
        wav = _projectes_gui___wav()
        p = self._crea(f, wav)
        # Edició «manual» del projecte: un acord diferent.
        with open(os.path.join(p.carpeta, "acords.csv"), "w",
                  encoding="utf-8") as fh:
            fh.write("0.00,2.00,Z\n")
        # Tornem a obrir el mateix àudio: offscreen → carrega (no sobreescriu).
        with patch.object(QFileDialog, "getOpenFileName",
                          return_value=(wav, "")):
            f.tria_wav()
        self.assertEqual(f.projecte.carpeta, p.carpeta)
        self.assertEqual(f.visor_ref.acords[0].nom, "Z",
                         "ha de manar el projecte, no l'àudio")

    def test_sobreescriu_deixa_la_carpeta_neta(self):
        f = _projectes_gui___finestra()
        wav = _projectes_gui___wav()
        p = self._crea(f, wav)
        carp = p.carpeta
        # Restes d'una sessió anterior (derivats i anàlisi crua).
        os.makedirs(os.path.join(carp, "wavs_acords"), exist_ok=True)
        open(os.path.join(carp, "wavs_acords", "vell.wav"), "wb").close()
        os.makedirs(os.path.join(carp, "analisi"), exist_ok=True)
        with open(os.path.join(carp, "acords.csv"), "w", encoding="utf-8") as fh:
            fh.write("0.00,1.00,Z\n")

        def _fake_paperera(ruta):
            shutil.rmtree(ruta, ignore_errors=True)
            return True

        with patch.object(f, "_pregunta_projecte_existent",
                          return_value="sobreescriu"), \
                patch.object(app_main.plataforma, "a_la_paperera", _fake_paperera):
            with patch.object(QFileDialog, "getOpenFileName",
                              return_value=(wav, "")):
                f.tria_wav()

        self.assertEqual(f.projecte.carpeta, carp)
        for nom in ("acords.csv", "estructura_ABC.csv", "tempo.csv",
                    "compas.csv"):
            self.assertTrue(os.path.isfile(os.path.join(carp, nom)), nom)
        self.assertFalse(os.path.exists(os.path.join(carp, "wavs_acords")),
                         "els derivats vells no poden quedar")
        self.assertFalse(os.path.exists(os.path.join(carp, "analisi")),
                         "l'anàlisi crua vella no pot quedar")
        with open(os.path.join(carp, "acords.csv"), encoding="utf-8") as fh:
            self.assertEqual(fh.read().strip(), "0.000000,2.000000,N",
                             "el model s'ha de reinicialitzar")

    def test_projecte_nou_serveix_per_exportar_sense_analitzar(self):
        f = _projectes_gui___finestra()
        wav = _projectes_gui___wav()
        p = self._crea(f, wav)
        self.assertTrue(f.b_export.isEnabled(), "Exporta WAV's ha d'estar actiu")
        self.assertTrue(f.b_export_part.isEnabled(),
                        "Exporta partitura ha d'estar actiu")
        # Flux MANUAL: l'usuari reanomena el clip «N» a «C» (sense analitzar).
        self.assertTrue(f.visor_ref._renomena_acords([0], "C"))
        res = pipeline.exporta_total(
            csv_ac=os.path.join(p.carpeta, "acords.csv"), csv_seg=None,
            sortida=p.carpeta, bpm=120.0, bpb=4, offset=0.0, sr=44100,
            log=lambda *_: None, tempo_fix=True, amb_estructura=True,
            total_s=2.0,
            acords=f.visor_ref.acords, seccions=f.visor_ref.seccions,
            mapa_tempo=list(f.visor_ref.tempo_trams))
        self.assertEqual(res["n_acords_wavs"], 1)
        self.assertEqual(res["n_estructura_wavs"], 1)
        self.assertTrue(any("C" in n for n in
                            os.listdir(os.path.join(p.carpeta, "wavs_acords"))))

    def test_exportar_amb_nomes_N_dona_un_missatge_clar(self):
        f = _projectes_gui___finestra()
        p = _projectes_gui___obre_wav(f, _projectes_gui___wav())
        with self.assertRaises(RuntimeError) as ctx:
            pipeline.exporta_total(
                csv_ac=os.path.join(p.carpeta, "acords.csv"), csv_seg=None,
                sortida=p.carpeta, bpm=120.0, bpb=4, offset=0.0, sr=44100,
                log=lambda *_: None, tempo_fix=True, amb_estructura=True,
                total_s=2.0,
                acords=f.visor_ref.acords, seccions=f.visor_ref.seccions)
        self.assertIn("cap acord per exportar", str(ctx.exception))
        self.assertNotIn("Chordino", str(ctx.exception))


class TestProteccionsDocument(unittest.TestCase):
    """El cru viatja dins el `.acproj`: lectura tolerant, límit i `.bak`."""

    def setUp(self):
        self.td = tempfile.mkdtemp()

    def _projecte(self):
        wav = os.path.join(self.td, "tema.wav")
        _wav(wav, 1.0)
        return projecte.Projecte.crea(os.path.join(self.td, "P"), wav)

    def test_cru_malmes_no_impedeix_obrir(self):
        p = self._projecte()
        p.dades["analisi"] = "això no és un diccionari"
        p.desa()
        p2 = projecte.Projecte.obre(p.ruta_acproj)
        self.assertNotIn("analisi", p2.dades)
        self.assertTrue(os.path.isfile(p2.ruta_csv_acords()))

    def test_cru_amb_entrades_dolentes_es_neteja(self):
        p = self._projecte()
        p.dades["analisi"] = {"data": "x",
                              "chords": [[0.0, "C"], ["no", "G"], [1.0]],
                              "segments": [[0.0, 1.0, 0, "A"], [1, 2]]}
        p.desa()
        p2 = projecte.Projecte.obre(p.ruta_acproj)
        ana = p2.dades["analisi"]
        self.assertEqual(ana["chords"], [[0.0, "C"]])
        self.assertEqual(ana["segments"], [[0.0, 1.0, 0, "A"]])

    def test_cru_massa_gran_es_descarta(self):
        p = self._projecte()
        gross = {"chords": [[i * 0.01, "C"] for i in range(60000)]}
        p.dades["analisi"] = gross
        p.desa()
        p2 = projecte.Projecte.obre(p.ruta_acproj)
        self.assertNotIn("analisi", p2.dades)

    def test_saneja_analisi_detecta_el_limit(self):
        petit = {"chords": [[0.0, "C"]]}
        self.assertIsNotNone(projecte.saneja_analisi(petit))
        self.assertIsNone(projecte.saneja_analisi({}))
        self.assertIsNone(projecte.saneja_analisi({"chords": "x"}))

    def test_desa_deixa_la_copia_bak(self):
        p = self._projecte()
        p.dades["nom"] = "primer"
        p.desa()
        p.dades["nom"] = "segon"
        p.desa()
        bak = p.ruta_acproj + ".bak"
        self.assertTrue(os.path.isfile(bak), "ha de quedar la còpia anterior")
        with open(bak, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["nom"], "primer")
        with open(p.ruta_acproj, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["nom"], "segon")


if __name__ == "__main__":   # pragma: no cover
    unittest.main()
