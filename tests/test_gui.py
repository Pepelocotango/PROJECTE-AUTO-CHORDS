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
os.environ["AUTO_CHORDS_TEST"] = "1"      # no llegir recents reals

# HIGIENE: la suite no ha d'escriure la llista de recents ni el marcador de
# sessió de l'usuari. Abans hi quedaven desenes de `/tmp/tmpXXXX/P1/P1.acproj`.
# Es redirigixen els FITXERS a un directori temporal (no es desactiva la
# funcionalitat: els tests que la comproven continuen veient el fitxer).
import tempfile as _tempfile  # noqa: E402
from unittest.mock import patch as _patch  # noqa: E402
from app.main import Finestra as _Finestra  # noqa: E402
_DIR_SUITE = _tempfile.mkdtemp(prefix="ac_suite_")
_patch.object(_Finestra, "_recents_path",
              lambda self: os.path.join(_DIR_SUITE, "recents.json")).start()
_patch.object(_Finestra, "_sessio_path",
              lambda self: os.path.join(_DIR_SUITE, "sessio.json")).start()

import unittest
import uuid
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
from app import graella
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
        # el diàleg edita 4 seccions però ha de **conservar** les altres
        # (p. ex. «guiat»: abans es perdien en desar des d'Opcions)
        self.assertEqual(set(out), {"bpm", "chords", "structure", "clean",
                                    "guiat", "analisi"})
        self.assertEqual(out["guiat"], dialegs.DEFECTES["guiat"])
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
        # QUÈ S'ANALITZA: les 3 etapes (BPM · acords · estructura)
        self.assertEqual(out["analisi"], dialegs.DEFECTES["analisi"])

    def test_seccions_que_no_edita_es_conserven(self):
        """`guiat` (i qualsevol secció futura) no es perd en desar."""
        base = dict(dialegs.DEFECTES)
        base["guiat"] = {"compassos": 16, "confirma": False}
        out = dialegs.DialegOpcions(None, opcions=base).opcions()
        self.assertEqual(out["guiat"], {"compassos": 16, "confirma": False})

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


class TestDialegQuantitza(_dialegs___Base):
    """El diàleg de quantització: abast + graelles lògiques."""

    def test_abast_i_graelles(self):
        d = dialegs.DialegQuantitza(None, abast="tot")
        self.assertEqual(d.abast(), "tot")
        self.assertGreater(d.cb_acords.count(), 0)
        self.assertGreater(d.cb_estructura.count(), 0)
        self.assertTrue(d.cb_acords.isEnabled())
        self.assertTrue(d.cb_estructura.isEnabled())
        self.assertIn(d.grid_acords(), [c for _e, c in graella.GRID_ACORDS])
        self.assertIn(d.grid_estructura(),
                      [c for _e, c in graella.GRID_ESTRUCTURA])

    def test_abast_apaga_la_graella_que_no_toca(self):
        d = dialegs.DialegQuantitza(None, abast="acords")
        self.assertTrue(d.cb_acords.isEnabled())
        self.assertFalse(d.cb_estructura.isEnabled())
        d.cb_abast.setCurrentIndex(d.cb_abast.findData("estructura"))
        self.assertFalse(d.cb_acords.isEnabled())
        self.assertTrue(d.cb_estructura.isEnabled())

    def test_seleccio_nomes_activa_els_tipus_presents(self):
        d = dialegs.DialegQuantitza(None, abast="seleccio",
                                    te_acords=True, te_seccions=False)
        self.assertTrue(d.cb_acords.isEnabled())
        self.assertFalse(d.cb_estructura.isEnabled())


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
              "reduir": False, "snap": True, "divisio": 4},
    # anàlisi guiat: mida del tram i doble comprovació (21-10)
    "guiat": {"compassos": 4, "confirma": True},
    # QUÈ S'ANALITZA: les 3 etapes, activables per separat (21-10)
    "analisi": {"bpm": True, "acords": True, "estructura": True},
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

    def test_botons_obre_audio_i_quantitza(self):
        """«Obre àudio» a Treball i «Quantitza» just abans de «Snap» a Transport."""
        texts = [b.text()
                 for b in self.w.barra_principal.findChildren(QPushButton)]
        self.assertIn("Obre àudio", texts)
        transport = [b.text()
                     for b in self.w.barra_transport.findChildren(QPushButton)]
        self.assertIn("Quantitza", transport)
        self.assertIn("Snap", transport)
        self.assertLess(transport.index("Quantitza"), transport.index("Snap"))
        self.assertIsNotNone(getattr(self.w, "b_quantitza", None))

    def test_boto_analisi_guitat_muntat(self):
        """«Anàlisi guiat» viu a Treball, entre «Obre àudio» i el mode BPM."""
        texts = [b.text()
                 for b in self.w.barra_principal.findChildren(QPushButton)]
        self.assertIn("Obre àudio", texts)
        self.assertIn("Anàlisi guiat", texts)
        self.assertIn("BPM · compàs", texts)
        self.assertLess(texts.index("Obre àudio"),
                        texts.index("Anàlisi guiat"))
        self.assertLess(texts.index("Anàlisi guiat"),
                        texts.index("BPM · compàs"))
        # des del 21-10 el botó obri la GUIA (només informació); el treball
        # es fa amb marcadors en viu. Sense WAV el botó està desactivat.
        self.assertIsNotNone(getattr(self.w, "b_guia", None))
        self.assertFalse(self.w.b_guia.isEnabled())
        self.assertIn("＋ Marker", texts)        # el botó del marcador hi és
        self.assertFalse(self.w.b_marker.isEnabled())
        with patch.object(app_main, "dialeg_guia_rapida") as mod:
            self.w._obre_guia_rapida()
        self.assertEqual(mod.DialegGuiaRapida.call_count, 1)

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
        self.velocitat = 1.0
        self._estirat = {}

    def _mono_bytes(self):
        return self._mono

    def _mono_a(self, factor):
        """Buffer ja estirat: `1/factor` mostres per mostra de cançó."""
        f = round(float(factor), 4)
        if f not in self._estirat:
            n = int(round(len(self._mono) / 2 / f))
            arr = np.full(n, 1000, dtype=np.int16)
            self._estirat[f] = arr.tobytes()
        return self._estirat[f]


def _max_run_zeros(data):
    run = mx = 0
    for v in (data == 0):
        run = run + 1 if v else 0
        if run > mx:
            mx = run
    return mx


class TestLoopContinu(unittest.TestCase):
    def test_a_2x_el_fil_esgota_tota_la_canco(self):
        """A 2× el buffer dura la meitat: el fil ha de recórrer la cançó
        SENcera (abans es quedava a mig camí: índex de buffer mal calculat)."""
        doble = _Doble(np.full(2000, 1000, dtype=np.int16), 1000)
        doble.velocitat = 2.0
        proc = _FakeProc(10_000_000)
        Visor._alimenta(doble, proc, 0.0, 0)
        data = np.frombuffer(bytes(proc.stdin.buf), dtype=np.int16)
        # sortida = mostres del buffer estirat = 2000/2 = 1000 (1 s real)
        self.assertEqual(data.size, 1000)
        self.assertTrue(proc.stdin.tancat)

    def test_a_mig_x_el_fil_esgota_tota_la_canco(self):
        doble = _Doble(np.full(2000, 1000, dtype=np.int16), 1000)
        doble.velocitat = 0.5
        proc = _FakeProc(10_000_000)
        Visor._alimenta(doble, proc, 0.0, 0)
        data = np.frombuffer(bytes(proc.stdin.buf), dtype=np.int16)
        self.assertEqual(data.size, 4000)      # 2000/0,5 (4 s reals)

    def test_loop_a_2x_fa_voltes_sense_tall(self):
        doble = _Doble(np.full(2000, 1000, dtype=np.int16), 1000,
                       loop=(0.1, 0.2))
        doble.velocitat = 2.0
        proc = _FakeProc(3000)
        Visor._alimenta(doble, proc, 0.15, 0)
        data = np.frombuffer(bytes(proc.stdin.buf), dtype=np.int16)
        self.assertGreater(data.size, 1000, "ha de fer més d'una volta")

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

    def test_la_nansa_te_8_px_de_marge(self):
        """La frontera s'agarra 8 px a cada costat (nansa pintada al paint).

        Abans el marge era d'1 px i, amb zoom normal, era impossible encertar
        la frontera per moure-la; a més la nansa no es veia.
        """
        capa = self._capa()
        self.assertEqual(capa._zona(300.0 - 7.0), (0, "fi"))
        self.assertEqual(capa._zona(300.0 + 7.0)[1], "ini")
        self.assertEqual(capa._zona(300.0 - 9.0), (0, "cos"))
        self.assertEqual(capa._zona(300.0 + 9.0), (1, "cos"))

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

class TestParteixALoop(unittest.TestCase):
    """«Parteix a la selecció A–B» als TRES carrils (regla d'or #11).

    És el «parteix aquí» als DOS punts alhora: cada frontera del loop (A i B)
    que caiga dins del clip seleccionat hi deixa un tall nou (2 o 3 trossos amb
    el mateix nom) i el tros d'A a B queda seleccionat; un sol desfer.
    """

    def setUp(self):
        self._app = QApplication.instance() or QApplication([])
        self.td = tempfile.mkdtemp()
        # Nom ÚNIC: si es diu «tema.wav», `tria_wav` pot reutilitzar un
        # projecte recent amb eixe nom i contaminar el test.
        self.wav = os.path.join(self.td, f"tema_{uuid.uuid4().hex[:8]}.wav")
        with wave.open(self.wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * 20)     # 20 s
        self.w = Finestra()
        acproj = os.path.join(self.td, "P1.acproj")
        with patch.object(QFileDialog, "getOpenFileName",
                          return_value=(self.wav, "")), \
                patch.object(QFileDialog, "getSaveFileName",
                             return_value=(acproj, "")):
            self.w.tria_wav()
        self.vr = self.w.visor_ref
        # model de prova: 3 clips per carril (0–4, 4–8, 8–20)
        C = pipeline.Clip
        self.vr.acords = [C(0.0, 4.0, ("C", "0")), C(4.0, 8.0, ("G", "4")),
                          C(8.0, 20.0, ("Am", "8"))]
        self.vr.seccions = [(0.0, 4.0, "A", "A"), (4.0, 8.0, "B", "B"),
                            (8.0, 20.0, "A", "A")]
        self.vr.tempo_trams = [(0.0, 4.0, 120.0, 4, 4),
                               (4.0, 8.0, 120.0, 4, 4),
                               (8.0, 20.0, 120.0, 4, 4)]
        self.vr._refresca_tempo_map()
        self.vr.timeline.set_data(self.vr.acords, self.vr.seccions)
        self.vr._undo_init()          # la base del desfer és el model de prova
        self.vr._undo_touch_base()
        self.avisos = []
        self.vr.avis_editor = lambda text: self.avisos.append(text)
        self.vr.loop_a, self.vr.loop_b = 5.0, 6.0

    def tearDown(self):
        self.w.close()
        shutil.rmtree(self.td, ignore_errors=True)

    def test_acord_es_parteix_a_A_i_B(self):
        vr = self.vr
        self.assertTrue(vr.parteix_a_loop("chord", 1))   # G 4–8 → 4–5|5–6|6–8
        self.assertEqual(len(vr.acords), 5)
        self.assertEqual([round(c.ini, 3) for c in vr.acords],
                         [0.0, 4.0, 5.0, 6.0, 8.0])
        self.assertEqual([c.nom for c in vr.acords[1:4]], ["G", "G", "G"])
        # el tros d'A a B queda seleccionat
        self.assertEqual(vr.clips_seleccionats(), {("chord", 2)})
        vr.undo()
        self.assertEqual(len(vr.acords), 3)
        self.assertEqual([round(c.ini, 3) for c in vr.acords], [0.0, 4.0, 8.0])

    def test_seccio_es_parteix_a_A_i_B(self):
        vr = self.vr
        vr.loop_a, vr.loop_b = 4.5, 7.25
        self.assertTrue(vr.parteix_a_loop("section", 1))
        self.assertEqual([(round(s[0], 3), round(s[1], 3)) for s in vr.seccions],
                         [(0.0, 4.0), (4.0, 4.5), (4.5, 7.25), (7.25, 8.0),
                          (8.0, 20.0)])
        self.assertEqual(vr.seccions[2][2], "B")
        vr.undo()
        self.assertEqual(len(vr.seccions), 3)

    def test_tram_de_tempo_es_parteix_a_A_i_B(self):
        vr = self.vr
        # 240 BPM 4/4 → un compàs cada segon: 5.0 i 6.0 SÍ que són línies.
        vr.tempo_trams = [(0.0, 4.0, 240.0, 4, 4), (4.0, 8.0, 240.0, 4, 4),
                          (8.0, 20.0, 240.0, 4, 4)]
        vr._refresca_tempo_map()
        vr.loop_a, vr.loop_b = 5.0, 6.0
        self.assertTrue(vr.parteix_a_loop("tempo", 1))
        self.assertEqual([round(t[0], 3) for t in vr.tempo_trams],
                         [0.0, 4.0, 5.0, 6.0, 8.0])
        vr.undo()
        self.assertEqual(len(vr.tempo_trams), 3)

    def test_tempo_A_i_B_al_mateix_compas_deixen_un_sol_tall(self):
        """A i B s'imanten al mateix compàs → un únic tall (no peta)."""
        vr = self.vr
        vr.loop_a, vr.loop_b = 4.9, 5.1    # 120 BPM 4/4: l'únic compàs és 6
        self.assertTrue(vr.parteix_a_loop("tempo", 1))
        self.assertEqual([round(t[0], 3) for t in vr.tempo_trams],
                         [0.0, 4.0, 6.0, 8.0])

    def test_nomes_una_frontera_dins(self):
        """Si només A cau dins del clip, es parteix només allà."""
        vr = self.vr
        vr.loop_a, vr.loop_b = 5.0, 9.5         # B cau a l'Am (8–20)
        self.assertTrue(vr.parteix_a_loop("chord", 1))
        self.assertEqual(len(vr.acords), 4)
        self.assertEqual([round(c.ini, 3) for c in vr.acords],
                         [0.0, 4.0, 5.0, 8.0])

    def test_cap_frontera_dins_no_fa_res(self):
        vr = self.vr
        vr.loop_a, vr.loop_b = 1.0, 2.0         # tot dins del primer acord
        self.assertFalse(vr.parteix_a_loop("chord", 1))
        self.assertEqual(len(vr.acords), 3)
        self.assertIn("no hi ha res a partir", self.avisos[0])

    def test_sense_loop_no_fa_res(self):
        vr = self.vr
        vr.loop_a = vr.loop_b = None
        self.assertFalse(vr.parteix_a_loop("chord", 1))
        self.assertEqual(len(vr.acords), 3)
        self.assertEqual(len(self.avisos), 1)

    def test_vores_exactes_no_tallen(self):
        """A o B coincidents amb la vora del clip no són cap tall."""
        vr = self.vr
        vr.loop_a, vr.loop_b = 4.0, 8.0         # = vores del G
        self.assertFalse(vr.parteix_a_loop("chord", 1))
        self.assertEqual(len(vr.acords), 3)

    def test_el_despatx_unic_hi_arriba(self):
        vr = self.vr
        self.assertTrue(vr.executa_edicio("parteix_loop", "chord", 1))
        self.assertEqual(len(vr.acords), 5)

    def test_el_menu_ho_ofereix_als_tres_carrils(self):
        vr = self.vr
        for kind in ("chord", "section", "tempo"):
            menu = vr._menu_contextual(kind, 1, 0.0)
            acts = [a for a in menu.actions() if a.data() == "parteix_loop"]
            self.assertEqual(len(acts), 1, kind)
            self.assertTrue(acts[0].isEnabled(), kind)
            self.assertIn("5.00–6.00s", acts[0].text())

    def test_el_menu_el_desactiva_sense_loop(self):
        vr = self.vr
        vr.loop_a = vr.loop_b = None
        menu = vr._menu_contextual("chord", 1, 0.0)
        act = next(a for a in menu.actions() if a.data() == "parteix_loop")
        self.assertFalse(act.isEnabled())
        self.assertNotIn("s)", act.text())      # sense valors A–B


class TestTempoLayerCursorAlClic(_timeline_layers___Base):
    """Paritat amb els clips: clic a un bloc de ③ → cursor al SEU INICI.

    Abans, clicar un bloc de BPM/compàs només el seleccionava: el cursor es
    quedava on era i el bloc quedava «seleccionat sense cursor», a diferència
    dels clips d'acords/seccions (report de l'operador, 20-10-2026).
    """

    def _capa(self):
        capa = L.TempoLayer(20, 60.0, 0.0, 0.0, 20.0)
        capa.set_mapa(tm.TempoMap(TRAMS), True)
        return capa

    def _clic(self, capa, x):
        capa.mousePressEvent(_Ev(x, Qt.LeftButton))
        capa.mouseReleaseEvent(_Ev(x, Qt.LeftButton))

    def test_clic_emet_linici_del_bloc(self):
        capa = self._capa()
        destins = []
        capa.tramCursorRequested.connect(destins.append)
        self._clic(capa, 450.0)          # cos del tram 1 (5–10 s a 60 px/s)
        self.assertEqual(destins, [5.0])

    def test_clic_al_primer_bloc_dona_zero(self):
        capa = self._capa()
        destins = []
        capa.tramCursorRequested.connect(destins.append)
        self._clic(capa, 60.0)           # dins del tram 0 (0–5 s)
        self.assertEqual(destins, [0.0])

    def test_arrossegar_no_mou_el_cursor(self):
        """Si hi ha arrossegada (canvi de frontera), NO s'ha de moure el cursor."""
        capa = self._capa()
        destins = []
        capa.tramCursorRequested.connect(destins.append)
        capa.mousePressEvent(_Ev(300.0, Qt.LeftButton))   # vora ini del tram 1
        capa._t_guia = 4.6                                # simulació d'arrossegada
        capa.mouseReleaseEvent(_Ev(276.0, Qt.LeftButton))
        self.assertEqual(destins, [])

    def test_boto_dret_no_mou_el_cursor(self):
        capa = self._capa()
        destins = []
        capa.tramCursorRequested.connect(destins.append)
        capa.mousePressEvent(_Ev(450.0, Qt.RightButton))
        capa.mouseReleaseEvent(_Ev(450.0, Qt.RightButton))
        self.assertEqual(destins, [])

    def test_el_timeline_hi_posa_el_cursor(self):
        """El handler del timeline deixa el cursor exactament a l'inici."""
        w = self._w_amb_timeline()
        tl = w.visor_ref.timeline
        tl.set_position(0.0, emit=False, snap=False)
        tl._on_tempo_cursor(7.25)        # frontera LLIURE (no cau a la graella)
        self.assertAlmostEqual(tl.get_position(), 7.25, places=6)

    def _w_amb_timeline(self):
        if getattr(self, "_w_cache", None) is not None:
            return self._w_cache
        import tempfile, wave
        from app.main import Finestra
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "tema.wav")
        with wave.open(wav, "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(44100)
            f.writeframes(b"\x00\x00" * 44100 * 10)     # 10 s
        w = Finestra()
        with patch.object(QFileDialog, "getOpenFileName",
                          return_value=(wav, "")), \
                patch.object(QFileDialog, "getSaveFileName",
                             return_value=(os.path.join(td, "P1.acproj"), "")):
            w.tria_wav()
        self.addCleanup(w.close)
        self.addCleanup(shutil.rmtree, td, True)
        self._w_cache = w
        return w


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


# ── Anàlisi guiat: diàlegs + flux de l'assistent ──────────
class TestDialegGuia(unittest.TestCase):
    """Diàlegs de l'«Anàlisi guiat» (docs/ANALISI_GUIAT.md), sense visor."""

    def setUp(self):
        self._app = QApplication.instance() or QApplication([])

    def _dlg(self):
        return dialegs.DialegGuiaBpm(
            None, 3, 12.5, 22.1, "compàs 20")

    def test_inicia_detectant_i_no_accepta(self):
        d = self._dlg()
        self.assertTrue(d.detectant())
        d.accept()
        self.assertEqual(d.result(), 0)     # Enter mentre detecta → res

    def test_mostra_bpm_habilita_i_accepta(self):
        d = self._dlg()
        d.mostra_bpm(93.37)
        self.assertFalse(d.detectant())
        self.assertEqual(d.valors(), 93.37)
        d.accept()
        self.assertEqual(d.result(), 1)     # QDialog.Accepted

    def test_deteccio_fallida_permet_editar(self):
        d = self._dlg()
        d.mostra_bpm(None)
        self.assertFalse(d.detectant())
        d.ed_bpm.setText("140,5")           # comma decimal suportada
        self.assertEqual(d.valors(), 140.5)

    def test_escala_x2_i_mig(self):
        d = self._dlg()
        d.mostra_bpm(93.37)
        for btn in d.findChildren(QPushButton):
            if btn.text().startswith("×2"):
                btn.click()
                break
        self.assertEqual(d.valors(), 186.74)
        for btn in d.findChildren(QPushButton):
            if btn.text().startswith("÷2"):
                btn.click()
                break
        self.assertEqual(d.valors(), 93.37)

    def test_escala_tanca_al_rang(self):
        d = self._dlg()
        d.mostra_bpm(280.0)
        for btn in d.findChildren(QPushButton):
            if btn.text().startswith("×2"):
                btn.click()
                break
        self.assertEqual(d.valors(), 300.0)

    def test_valors_no_valids(self):
        d = self._dlg()
        d.mostra_bpm(90.0)
        d.ed_bpm.setText("abc")
        self.assertIsNone(d.valors())
        d.ed_bpm.setText("")
        self.assertIsNone(d.valors())
        d.ed_bpm.setText("500")             # fora del rang guardat
        self.assertIsNone(d.valors())
        d.ed_bpm.setText("10")              # massa lent
        self.assertIsNone(d.valors())


class _FilFals(app_main.FilGuiaBpm):
    """Substituciï del fil de detecció per als tests: `start` no fa res."""

    def start(self, *a, **k):
        pass


class TestDialegGuiaCandidats(unittest.TestCase):
    """Diàleg del guiat: alternatives amb fiabilitat + avís de rang."""

    def setUp(self):
        self._app = QApplication.instance() or QApplication([])
        self.td = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.td, ignore_errors=True)
        # Els diàlegs són top-level (parent=None): destruir-los ACÍ i no pas
        # al GC d'un test posterior (un DeferredDelete tardà feia petar
        # `processa_esborrats` uns quants tests més enllà).
        import _qt_neteja
        _qt_neteja.processa_esborrats()

    def _dlg(self, **kw):
        return dialegs.DialegGuiaBpm(None, 1, 0.0, 8.0, "1.1", **kw)

    def test_mostra_alternatives_i_tria(self):
        d = self._dlg()
        d.mostra_bpm(103.4,
                     candidats=[(103.4, 1.0), (101.3, 0.97), (105.5, 0.95)],
                     alternatives=[(52.0, 0.6)], ref=103.4)
        self.assertEqual(d.valors(), 103.4)
        visibles = [b for b in d._b_cand if b.isVisibleTo(d)]
        self.assertEqual(len(visibles), 2)
        self.assertIn("101.30", visibles[0].text())
        d._tria_candidat(0)                  # clic a l'alternativa
        self.assertAlmostEqual(d.valors(), 101.3, places=2)
        self.assertIn("52.00", d.lb_estat.text())      # avís fora de rang
        self.assertIn("103.40", d.lb_ref.text())
        d.close()

    def test_sense_candidats_es_com_de_sempre(self):
        d = self._dlg()
        d.mostra_bpm(120.0)
        self.assertEqual(d.valors(), 120.0)
        self.assertFalse(any(b.isVisibleTo(d) for b in d._b_cand))
        d._escala(4.0 / 3.0)
        self.assertAlmostEqual(d.valors(), 160.0, places=1)
        d._escala(3.0 / 4.0)
        self.assertAlmostEqual(d.valors(), 120.0, places=1)
        d.close()

    def test_error_allow_editar(self):
        d = self._dlg()
        d.mostra_bpm(None, candidats=[(120.0, 1.0)])
        self.assertTrue(d.ed_bpm.isEnabled())
        self.assertTrue(d.b_ok.isEnabled())
        d.close()


class TestOpcionsRangBpm(unittest.TestCase):
    """Pestanya BPM: avís de rang estret + botó de valors recomanats."""

    def setUp(self):
        self._app = QApplication.instance() or QApplication([])

    def test_avisa_rang_estret(self):
        d = dialegs.DialegOpcions(None, tab="bpm", opcions={
            "bpm": {"motor": "consens", "min": 50, "max": 100,
                    "pref_min": 50, "pref_max": 100}})
        self.assertIn("50–100", d.lb_rang.text())
        d.deleteLater()

    def test_valors_recomanats(self):
        d = dialegs.DialegOpcions(None, tab="bpm", opcions={
            "bpm": {"motor": "consens", "min": 50, "max": 100,
                    "pref_min": 50, "pref_max": 100}})
        d._bpm_recomanat()
        c = d._controls["bpm"]
        self.assertEqual((c["min"].value(), c["max"].value(),
                          c["pref_min"].value(), c["pref_max"].value()),
                         (60, 180, 85, 150))
        self.assertEqual(d.lb_rang.text(), "")
        d.deleteLater()

    def test_preferit_fora_del_rang(self):
        d = dialegs.DialegOpcions(None, tab="bpm", opcions={
            "bpm": {"motor": "nostre", "min": 60, "max": 180,
                    "pref_min": 100, "pref_max": 260}})
        self.assertIn("preferit", d.lb_rang.text())
        d.deleteLater()


class TestDialegTempoPerTrams(unittest.TestCase):
    """Diàleg «Detecta el tempo per trams»: valors per defecte i extrems."""

    def setUp(self):
        self._app = QApplication.instance() or QApplication([])

    def test_valors_per_defecte(self):
        d = dialegs.DialegTempoPerTrams(None, durada=180.0)
        self.assertEqual(d.valors(), (4, 0.02, True))
        self.assertIn("180.00", d.lb_info.text())
        d.deleteLater()

    def test_valors_al_extrem(self):
        d = dialegs.DialegTempoPerTrams(None, durada=60.0, cada=1,
                                        tolerancia=5.5, offset_auto=False)
        cada, tol, auto = d.valors()
        self.assertEqual(cada, 1)
        self.assertAlmostEqual(tol, 0.055, places=6)
        self.assertFalse(auto)
        d.deleteLater()


class TestTempoPerTramsGui(unittest.TestCase):
    """Acció de menú → fil → aplicació del mapa amb UN sol desfer."""

    def setUp(self):
        self._app = QApplication.instance() or QApplication([])
        self.td = tempfile.mkdtemp()
        # Nom ÚNIC: si es diu «tema.wav», `tria_wav` pot reutilitzar un
        # projecte recent amb eixe nom i contaminar el test.
        self.wav = os.path.join(self.td, f"tema_{uuid.uuid4().hex[:8]}.wav")
        with wave.open(self.wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * 20)     # 20 s
        self.w = Finestra()
        acproj = os.path.join(self.td, "P1.acproj")
        with patch.object(QFileDialog, "getOpenFileName",
                          return_value=(self.wav, "")), \
                patch.object(QFileDialog, "getSaveFileName",
                             return_value=(acproj, "")):
            self.w.tria_wav()

    def tearDown(self):
        self.w.dirty = False       # sense prompt de tancament als tests
        self.w.close()
        shutil.rmtree(self.td, ignore_errors=True)

    def test_llanca_el_fil_amb_els_parametres(self):
        w = self.w
        capturat = []

        class _FilFals(app_main.FilTempoTrams):
            def __init__(self, wav, durada, num, den, cada, tol, **kw):
                capturat.append((wav, durada, num, den, cada, tol, kw))
                super().__init__(wav, durada, num, den, cada, tol, **kw)

            def start(self, *a, **k):
                pass

        class _DlgOK:
            def __init__(self, *a, **k):
                pass

            def exec_(self):
                return QW.QDialog.Accepted

            def valors(self):
                return (2, 0.03, False)

        with patch.object(app_main, "FilTempoTrams", _FilFals), \
                patch.object(dialegs, "DialegTempoPerTrams", _DlgOK):
            w._detecta_tempo_per_trams()
        try:
            self.assertEqual(len(capturat), 1)
            _wav, _dur, num, den, cada, tol, kw = capturat[0]
            self.assertEqual(cada, 2)
            self.assertAlmostEqual(tol, 0.03)
            self.assertEqual(kw.get("offset"), 0.0)   # offset_auto OFF
            self.assertIsNotNone(w._fil_trams)
        finally:
            # El fil no s'ha arrencat mai (start és no-op): n'hi ha prou de
            # deixar-lo anar. Un `deleteLater()` d'un QThread ací acaba en un
            # DeferredDelete dins del teardown d'un altre test → segfault.
            fil = w._fil_trams
            w._fil_trams = None
            if fil is not None:
                fil.wait(500)

    def test_aplica_el_mapa_en_un_sol_desfer(self):
        w = self.w
        vr = w.visor_ref
        from app import tempo_map
        # amb offset 0.5 les línies de compàs comencen a 0.5
        b1 = tempo_map.durada_compas(120.0, 4, 4)
        b2 = tempo_map.durada_compas(124.0, 4, 4)
        t1 = 0.5 + 4 * b1
        t2 = t1 + 4 * b2
        trams = [(0.0, t1, 120.0, 4, 4), (t1, t2, 124.0, 4, 4),
                 (t2, 20.0, 124.0, 4, 4)]
        abans = vr._undo_stack.__len__()
        w._tempo_trams_fet({"trams": trams, "offset": 0.5, "bpm_base": 120.0})
        self.assertAlmostEqual(float(vr.offset), 0.5, places=6)
        self.assertEqual(len(vr.tempo_trams), 3)
        self.assertEqual(len(vr._undo_stack), abans + 1)
        vr.undo()
        self.assertNotEqual(len(vr.tempo_trams), 3)

    def test_mapa_invalid_no_s_aplica(self):
        w = self.w
        vr = w.visor_ref
        abans = list(vr.tempo_trams or [])
        with patch.object(w, "avisa_info") as mock:
            # dues fronteres: la de 7,3 s no cau en cap línia de compàs
            w._tempo_trams_fet({"trams": [(0.0, 7.3, 121.7, 4, 4),
                                          (7.3, 20.0, 121.7, 4, 4)],
                                "offset": 0.0, "bpm_base": 121.7})
        self.assertEqual(mock.call_count, 1)
        self.assertEqual(list(vr.tempo_trams or []), abans)

    def test_sense_trams_avisa(self):
        w = self.w
        with patch.object(w, "avisa_info") as mock:
            w._tempo_trams_fet({"trams": [], "offset": 0.0,
                                "bpm_base": None})
        self.assertEqual(mock.call_count, 1)


def _opcions_temporals(test, carpeta):
    """Redirigir `opcions_detecta.json` a un fitxer temporal del test.

    El guiat hi desa la mida de tram i la confirmació: una prova que trie 5
    compassos contaminaria la sessió real de l'usuari (vist 21-10).
    """
    p = os.path.join(carpeta, "opcions_test.json")
    pedac = patch.object(dialegs, "FITXER_OPCIONS", p)
    pedac.start()
    test.addCleanup(pedac.stop)
    # Els tests NO han de contaminar la llista de recents de l'usuari (abans
    # hi apareixien desenes de `/tmp/tmpXXXX/P1/P1.acproj`).
    pedac2 = patch.object(app_main.Finestra, "_guarda_recents",
                          lambda self: None)
    pedac2.start()
    test.addCleanup(pedac2.stop)
    return p


class TestGuiaFlux(unittest.TestCase):
    """Flux de l'assistent a la Finestra, amb la detecció ANUL·LADA.

    `FilGuiaBpm` es substitueix per `_FilFals` (sense fil de veritat) i el
    flux es condueix amb `_guia_bpm_ditectat(bpm)` + `_guia_fenestra_aplica
    (dlg)` — exactament el que fan el fil i el diàleg de resultats en viu,
    però síncron.
    """

    def setUp(self):
        self._app = QApplication.instance() or QApplication([])
        self.td = tempfile.mkdtemp()
        # Nom ÚNIC: si es diu «tema.wav», `tria_wav` pot reutilitzar un
        # projecte recent amb eixe nom i contaminar el test.
        self.wav = os.path.join(self.td, f"tema_{uuid.uuid4().hex[:8]}.wav")
        with wave.open(self.wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * 20)   # 20 s
        self.w = Finestra()
        # patró `_obre_wav`: tria_wav també pregunta ON crear el projecte
        acproj = os.path.join(self.td, "P1.acproj")
        with patch.object(QFileDialog, "getOpenFileName",
                          return_value=(self.wav, "")), \
                patch.object(QFileDialog, "getSaveFileName",
                             return_value=(acproj, "")):
            self.w.tria_wav()
        self._p_fil = patch.object(app_main, "FilGuiaBpm", _FilFals)
        self._p_fil.start()
        # estat del guiat determinista (no depén de les opcions desades)
        self.w.opcions["guiat"] = {"compassos": 4, "confirma": False}
        _opcions_temporals(self, self.td)
        # el guiat v2 posa el tram en bucle: motor fals perquè la suite no
        # òbriga cap `paplay` de veritat
        self._p_motor = patch.object(audio_out, "crea_motor",
                                     lambda *_a, **_k: _MotorMut())
        self._p_motor.start()

    def tearDown(self):
        self.w.close()
        self._p_fil.stop()
        self._p_motor.stop()
        shutil.rmtree(self.td, ignore_errors=True)

    def _posa_cursor(self, t):
        self.w.visor_ref.pos = t
        self.w.visor_ref.timeline.set_position(t, emit=False, snap=False)

    def test_pas1_offset_tall_i_finestra(self):
        w = self.w
        w._analisi_guitat()
        self.assertIn("dlg1", w._guia)
        self._posa_cursor(2.0)
        w._guia_pas1_fet()
        vr = w.visor_ref
        self.assertEqual(w.offset.text(), "2.000")
        trams = vr.tempo_trams
        self.assertEqual(len(trams), 2)
        self.assertAlmostEqual(trams[0][1], 2.0, places=6)
        self.assertAlmostEqual(trams[1][0], 2.0, places=6)
        # pas 4 del disseny: el bucle ja treballa en mode BPM + snap negra
        self.assertTrue(w.b_mode_bpm.isChecked())
        self.assertTrue(w.tb_snap.isChecked())
        self.assertIn("dlg2", w._guia)
        w._guia_cancel()

    def test_flux_complet_fins_al_final(self):
        """Pas 1 + 1a finestra + última (absorbeix) + fusió + executa()."""
        w = self.w
        crides = []
        w.executa = lambda: crides.append(1)   # no obris res de modal
        w._analisi_guitat()
        self._posa_cursor(2.0)
        w._guia_pas1_fet()
        vr = w.visor_ref
        # finestra 1 · 90 BPM (bar 2.667 s · 4 compasos → t_seg 12.667 s)
        w._guia_bpm_ditectat(90.0)
        dlg2 = w._guia["dlg2"]
        self.assertEqual(dlg2.valors(), 90.0)
        w._guia_fenestra_aplica(dlg2)
        self.assertAlmostEqual(vr.tempo_trams[1][0], 2.0, places=6)
        self.assertAlmostEqual(vr.tempo_trams[1][2], 90.0, places=6)
        self.assertAlmostEqual(vr.tempo_trams[1][1], 12.667, places=3)
        # en aplicar la finestra 1 ja s'obre la 2 → n=2 (correlatiu; amb el
        # doble increment hauria estat 3 i la numeració saltaria 1, 3, 5…)
        self.assertEqual(w._guia["n"], 2)
        # finestra 2 · 74 BPM: la finestra sobrepassa la fi → ABSORBEIX
        self.assertAlmostEqual(w._guia["t_k"], 12.667, places=3)
        w._guia_bpm_ditectat(74.0)
        dlg3 = w._guia["dlg2"]
        w._guia_fenestra_aplica(dlg3)
        # mode BPM + snap negra restaurats; executa() cridat; estat net
        self.assertTrue(w.b_mode_bpm.isChecked())
        self.assertTrue(w.tb_snap.isChecked())
        self.assertEqual(w.cb_graella.currentData(), "negra")
        self.assertEqual(crides, [1])
        self.assertEqual(w._guia, {})
        # mapa final vàlid (contracte de compasos enters amb l'offset)
        from app import tempo_map
        val = tempo_map.valida_i_normalitza_compassos(
            vr.tempo_trams, vr._durada_wav(), offset=2.0)
        self.assertAlmostEqual(val[-1][1], vr._durada_wav(), places=6)
        self.assertAlmostEqual(vr.tempo_trams[-1][2], 74.0, places=6)

    def test_cancel_restaura(self):
        w = self.w
        w._analisi_guitat()
        w._guia_cancel()
        self.assertTrue(w.b_mode_bpm.isChecked())
        self.assertTrue(w.tb_snap.isChecked())
        self.assertEqual(w.cb_graella.currentData(), "negra")
        self.assertEqual(w._guia, {})

    def test_sense_wav_avis(self):
        w = self.w
        w.wav_edit.setText("/no/existeix.wav")
        with patch.object(w, "avisa") as mock:
            w._analisi_guitat()
        self.assertEqual(mock.call_count, 1)
        self.assertEqual(w._guia, {})


class TestGuiaFilReal(unittest.TestCase):
    """El camí de la caçada real: fil DE VERITAT + senyals QUEUED.

    Bug del 20-10-2026: `FilGuiaBpm` cridava `Finestra.registra` DIRECTE
    des del fil (`QTextEdit.append`) → UB Qt → segfault al bucle principal
    ("Cannot queue arguments of type 'QTextCursor'"). El test anula el fil
    i cridava els mètodes a mà, així que no excercitava cap camí real.
    Ací: fil real (detecció sobre silenci → BPM None), espiant el resultat
    amb el bucle d'esdeveniments de veritat.
    """

    def setUp(self):
        self._app = QApplication.instance() or QApplication([])
        self.td = tempfile.mkdtemp()
        # Nom ÚNIC: si es diu «tema.wav», `tria_wav` pot reutilitzar un
        # projecte recent amb eixe nom i contaminar el test.
        self.wav = os.path.join(self.td, f"tema_{uuid.uuid4().hex[:8]}.wav")
        with wave.open(self.wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * 20)   # 20 s de silenci
        self.w = Finestra()
        acproj = os.path.join(self.td, "P1.acproj")
        with patch.object(QFileDialog, "getOpenFileName",
                          return_value=(self.wav, "")), \
                patch.object(QFileDialog, "getSaveFileName",
                             return_value=(acproj, "")):
            self.w.tria_wav()

    def tearDown(self):
        self.w.close()
        shutil.rmtree(self.td, ignore_errors=True)

    def _espera_dlg_eines(self, app, motiu, segons=20.0):
        """Espera (baixant esdeveniments) fins que el diàleg siga editable."""
        dret = time.time() + segons
        d = self.w._guia.get("dlg2")
        while time.time() < dret and d is not None and d.detectant():
            app.processEvents()
            time.sleep(0.02)
            d = self.w._guia.get("dlg2")
        return d

    def test_finestra_amb_fil_real(self):
        app = self._app
        w = self.w
        w._analisi_guitat()
        w.visor_ref.pos = 2.0
        w._guia_pas1_fet()
        d = self._espera_dlg_eines(app, None)
        self.assertIsNotNone(d)
        self.assertFalse(d.detectant())
        d.ed_bpm.setText("96")
        d.accept()
        app.processEvents()
        self.assertAlmostEqual(w.visor_ref.tempo_trams[1][2], 96.0, places=6)
        w._guia_cancel()


class TestSeleccioBpmICompas1(unittest.TestCase):
    """Selecció A–B per al BPM + «compàs 1 al cursor» complet (2026-10-20).

    - BPM: si hi ha loop A–B marcat, la detecció fa servir NOMÉS eixe rang
      (mana sobre el tram de tempo seleccionat i sobre el tema sencer).
    - Compàs 1 al cursor: offset + TALL del carril de tempo + inici del clip
      de tempo en eixa posició, tot en UN sol pas de desfer.
    """

    def setUp(self):
        self._app = QApplication.instance() or QApplication([])
        self.td = tempfile.mkdtemp()
        # Nom ÚNIC: si es diu «tema.wav», `tria_wav` pot reutilitzar un
        # projecte recent amb eixe nom i contaminar el test.
        self.wav = os.path.join(self.td, f"tema_{uuid.uuid4().hex[:8]}.wav")
        with wave.open(self.wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * 20)     # 20 s
        self.w = Finestra()
        acproj = os.path.join(self.td, "P1.acproj")
        with patch.object(QFileDialog, "getOpenFileName",
                          return_value=(self.wav, "")), \
                patch.object(QFileDialog, "getSaveFileName",
                             return_value=(acproj, "")):
            self.w.tria_wav()

    def tearDown(self):
        self.w.close()
        shutil.rmtree(self.td, ignore_errors=True)

    # --- BPM només de la selecció -----------------------------------------
    def test_detecta_bpm_nomes_de_la_seleccio(self):
        w = self.w
        vr = w.visor_ref
        vr.loop_a, vr.loop_b = 1.0, 5.0
        crides = []

        def _tram(wav, ini, fi, *a, **k):
            crides.append((wav, ini, fi))
            return 120.0

        with patch.object(app_main.pipeline, "detecta_bpm_tram", _tram), \
                patch.object(app_main.pipeline, "detecta_bpm",
                             lambda *a, **k: self.fail(
                                 "amb loop no s'ha de detectar el tema sencer")):
            w._detecta_bpm(pregunta=False)
        self.assertEqual(len(crides), 1)
        self.assertEqual(crides[0][1:], (1.0, 5.0))
        self.assertEqual(w.bpm.text(), "120.000")
        self.assertIn("selecció A–B", w.log.toPlainText())

    def test_sense_loop_detecta_el_tema(self):
        w = self.w
        crides = []
        with patch.object(app_main.pipeline, "detecta_bpm",
                          lambda *a, **k: crides.append("tema") or 100.0), \
                patch.object(app_main.pipeline, "detecta_bpm_tram",
                             lambda *a, **k: self.fail(
                                 "sense loop ha de detectar el tema")):
            w._detecta_bpm(pregunta=False)
        self.assertEqual(crides, ["tema"])

    def test_loop_massa_curt_es_ignora(self):
        w = self.w
        vr = w.visor_ref
        vr.loop_a, vr.loop_b = 1.0, 1.2      # 0.2 s: no és una selecció útil
        crides = []
        with patch.object(app_main.pipeline, "detecta_bpm",
                          lambda *a, **k: crides.append("tema") or 100.0):
            w._detecta_bpm(pregunta=False)
        self.assertEqual(crides, ["tema"])

    # --- Compàs 1 al cursor: offset + tall + inici de clip -----------------
    def test_compas1_offset_tall_i_clip_en_un_desfer(self):
        w = self.w
        vr = w.visor_ref
        durada = vr._durada_wav()
        self.assertEqual(len(vr.tempo_trams), 1)     # tot el tema, 1 tram
        vr.pos = 3.0
        w._marca_compas_1()
        # offset + clip de tempo nou a 3.0 s
        self.assertAlmostEqual(float(vr.offset), 3.0, places=6)
        self.assertEqual(w.offset.text(), "3.000")
        trams = vr.tempo_trams
        self.assertEqual(len(trams), 2)
        self.assertAlmostEqual(trams[0][1], 3.0, places=6)
        self.assertAlmostEqual(trams[1][0], 3.0, places=6)
        self.assertAlmostEqual(trams[1][1], durada, places=6)
        # el clip nou queda seleccionat (els camps BPM/compàs l'editen)
        self.assertIn(("tempo", 1), vr.timeline.selected_keys())
        # UN sol desfer ho desfà tot (offset i tall)
        vr.undo()
        self.assertAlmostEqual(float(vr.offset), 0.0, places=6)
        self.assertEqual(len(vr.tempo_trams), 1)

    def test_compas1_sobre_una_frontera_no_afegeix_tall(self):
        w = self.w
        vr = w.visor_ref
        durada = vr._durada_wav()
        vr.tempo_trams = [(0.0, 3.0, 120.0, 4, 4),
                          (3.0, durada, 120.0, 4, 4)]
        vr.pos = 3.0
        w._marca_compas_1()
        self.assertAlmostEqual(float(vr.offset), 3.0, places=6)
        self.assertEqual(len(vr.tempo_trams), 2)     # sense tall nou

    def test_compas1_al_final_avisa_i_no_toca_res(self):
        w = self.w
        vr = w.visor_ref
        avisos = []
        w.avisa = lambda titol, text: avisos.append(titol)
        vr.pos = vr._durada_wav()
        w._marca_compas_1()
        self.assertEqual(len(avisos), 1)
        self.assertAlmostEqual(float(vr.offset), 0.0, places=6)
        self.assertEqual(len(vr.tempo_trams), 1)

    # --- El guiat detecta només el tros del loop dins la finestra ---------
    def test_guia_finestra_usa_el_loop_per_detectar(self):
        w = self.w
        vr = w.visor_ref
        vr.loop_a, vr.loop_b = 1.0, 4.0
        w._guia = {"durada": vr._durada_wav(), "n": 0}
        capturat = []

        class _FilCaptura(app_main.FilGuiaBpm):
            def __init__(self, wav, ini, fi, **kw):
                capturat.append((ini, fi))
                super().__init__(wav, ini, fi, **kw)

            def start(self, *a, **k):
                pass

        with patch.object(app_main, "FilGuiaBpm", _FilCaptura):
            w._guia_fenestra()
        try:
            self.assertEqual(len(capturat), 1)
            self.assertAlmostEqual(capturat[0][0], 1.0, places=6)
            self.assertAlmostEqual(capturat[0][1], 4.0, places=6)
            d = w._guia["dlg2"]
            self.assertIn("A–B", d.lb_nota.text())
        finally:
            w._guia_cancel()

    def test_guia_bpm_dict_omple_candidats_i_ref(self):
        """El fil del guiat arriba amb alternatives → diàleg i referència."""
        w = self.w
        vr = w.visor_ref
        w._guia = {"durada": vr._durada_wav(), "n": 0, "loop": None,
                   "ref": None}

        class _FilCaptura(app_main.FilGuiaBpm):
            def start(self, *a, **k):
                pass

        with patch.object(app_main, "FilGuiaBpm", _FilCaptura):
            w._guia_fenestra()
        try:
            d = w._guia["dlg2"]
            w._guia_bpm_ditectat({
                "bpm": 103.4,
                "candidats": [(103.4, 1.0), (101.3, 0.97)], 
                "alternatives": [], "ref": 103.4})
            self.assertAlmostEqual(d.valors(), 103.4, places=2)
            self.assertAlmostEqual(w._guia["ref"], 103.4, places=6)
            self.assertTrue(d.lb_ref.isVisibleTo(d))
            # compatibilitat: un float també s'accepta (fils de prova)
            w._guia_bpm_ditectat(99.5)
            self.assertAlmostEqual(d.valors(), 99.5, places=2)
        finally:
            w._guia_cancel()

    def test_guia_finestra_loop_fora_de_la_finestra_no_acota(self):
        """Si el loop no cau dins la finestra, es mesura la finestra sencera."""
        w = self.w
        vr = w.visor_ref
        vr.loop_a, vr.loop_b = 15.0, 19.0      # molt més enllà de la 1a finestra
        w._guia = {"durada": vr._durada_wav(), "n": 0}
        capturat = []

        class _FilCaptura(app_main.FilGuiaBpm):
            def __init__(self, wav, ini, fi, **kw):
                capturat.append((ini, fi))
                super().__init__(wav, ini, fi, **kw)

            def start(self, *a, **k):
                pass

        with patch.object(app_main, "FilGuiaBpm", _FilCaptura):
            w._guia_fenestra()
        try:
            self.assertEqual(len(capturat), 1)
            self.assertAlmostEqual(capturat[0][0], 0.0, places=6)
            # la 1a finestra fa 8 s i no s'acota al loop (que és fora)
            self.assertAlmostEqual(capturat[0][1], 8.0, places=6)
            self.assertIsNone(getattr(w._guia["dlg2"], "lb_nota", None))
        finally:
            w._guia_cancel()

    def test_guia_finestra_sense_loop_usa_la_finestra(self):
        w = self.w
        vr = w.visor_ref
        w._guia = {"durada": vr._durada_wav(), "n": 0}
        capturat = []

        class _FilCaptura(app_main.FilGuiaBpm):
            def __init__(self, wav, ini, fi, **kw):
                capturat.append((ini, fi))
                super().__init__(wav, ini, fi, **kw)

            def start(self, *a, **k):
                pass

        with patch.object(app_main, "FilGuiaBpm", _FilCaptura):
            w._guia_fenestra()
        try:
            self.assertEqual(len(capturat), 1)
            self.assertAlmostEqual(capturat[0][0], 0.0, places=6)
            self.assertGreater(capturat[0][1], 0.0)
            self.assertIsNone(getattr(w._guia["dlg2"],
                                      "lb_nota", None))
        finally:
            w._guia_cancel()


class TestGuiatOpcioTram(unittest.TestCase):
    """Guiat v2: mida del tram a l'anàlisi (4/8/16/32) i doble comprovació."""

    def setUp(self):
        self._app = QApplication.instance() or QApplication([])
        self._oberts = []
        self.td = tempfile.mkdtemp()
        _opcions_temporals(self, self.td)

    def tearDown(self):
        for d in self._oberts:
            d.close()
        shutil.rmtree(self.td, ignore_errors=True)

    def _pas1(self, compassos=4, confirma=True):
        d = dialegs.DialegGuiaDownbeat(None, compassos=compassos,
                                       confirma=confirma)
        self._oberts.append(d)
        return d

    def test_presets_i_valor_inicial(self):
        d = self._pas1(compassos=16)
        textos = [d.cb_compassos.itemText(i)
                  for i in range(d.cb_compassos.count())]
        self.assertEqual(textos, ["4 compassos", "8 compassos",
                                  "16 compassos", "32 compassos"])
        self.assertEqual(d.compassos(), 16)
        self.assertTrue(d.confirma())

    def test_desmarcar_la_confirmacio(self):
        d = self._pas1(confirma=False)
        self.assertFalse(d.confirma())
        d.ck_confirma.setChecked(True)
        self.assertTrue(d.confirma())

    def test_mida_que_no_es_preset_no_es_perd(self):
        d = self._pas1(compassos=6)
        self.assertEqual(d.compassos(), 6)
        self.assertEqual(d.cb_compassos.currentText(), "6 compassos")

    def test_es_desa_a_les_opcions_del_guiat(self):
        """La tria es recorda (fitxer temporal de la suite, mai el real)."""
        from app import dialegs as dl
        self.assertEqual(dialegs.DEFECTES["guiat"]["compassos"], 4)
        self.assertTrue(dialegs.DEFECTES["guiat"]["confirma"])
        dl.desa_opcions({"guiat": {"compassos": 32, "confirma": False}})
        self.assertEqual(dl.carrega_opcions()["guiat"],
                         {"compassos": 32, "confirma": False})


class _MotorMut:
    """Motor d'àudio fals: no sona res i no bloqueja el fil de farciment."""

    def __init__(self):
        self.pid = 4242
        self.stdin = self
        self.aturat = False

    def write(self, b):
        time.sleep(0.002)          # el fil avança a poc a poc, sense cremar CPU
        return len(b)

    def close(self):
        pass

    def flush(self):
        pass

    def poll(self):
        return None

    def atura(self):
        self.aturat = True


class _RellotgeFals:
    """`time` de mentida per als TAP (`monotonic` fix o per llista)."""

    def __init__(self, valors):
        self.valors = list(valors)

    def monotonic(self):
        if len(self.valors) > 1:
            return self.valors.pop(0)
        return self.valors[0]


class TestDialegGuiaAudicio(unittest.TestCase):
    """Guiat v2 al diàleg: mètrica, compassos, TAP i senyals (sense fils)."""

    def setUp(self):
        self._app = QApplication.instance() or QApplication([])
        self._oberts = []

    def tearDown(self):
        for d in self._oberts:
            d.close()
        self._oberts = []

    def _dlg(self, num=4, den=4, compassos=4):
        d = dialegs.DialegGuiaBpm(None, 1, 0.0, 8.0, "1.1", num=num,
                                  den=den, compassos=compassos)
        self._oberts.append(d)
        return d

    def test_metrica_inicial_i_presets(self):
        d = self._dlg(num=3, den=4)
        self.assertEqual(d.metrica(), (3, 4))      # la vigent, encara que
        self.assertEqual(d.compassos(), 4)         # no siga al catàleg
        for txt in ("4/4", "3/4", "2/4", "6/8", "12/8"):
            self.assertGreaterEqual(d.cb_metrica.findText(txt), 0, txt)
        self.assertEqual(d.cb_metrica.count(), 5)     # sense duplicats

    def test_metrica_no_preset_s_afegeix(self):
        d = self._dlg(num=5, den=8)
        self.assertEqual(d.metrica(), (5, 8))
        self.assertGreaterEqual(d.cb_metrica.findText("5/8"), 0)

    def test_compassos_amb_limits(self):
        d = self._dlg()
        d._canvia_compassos(+1)
        self.assertEqual(d.compassos(), 5)
        self.assertIn("5", d.lb_compassos.text())
        for _ in range(20):
            d._canvia_compassos(-1)
        self.assertEqual(d.compassos(), d.COMPASSOS_MIN)
        for _ in range(60):
            d._canvia_compassos(+1)
        self.assertEqual(d.compassos(), d.COMPASSOS_MAX)
        self.assertIn("compassos", d.lb_compassos.text())
        d2 = self._dlg(compassos=1)
        self.assertIn("1 compàs", d2.lb_compassos.text())

    def test_tap_calcula_bpm(self):
        d = self._dlg()
        rellotge = _RellotgeFals([100.0, 100.5, 101.0, 101.52])
        with patch.object(dialegs, "time", rellotge):
            for _ in range(4):
                d._tap()
        self.assertAlmostEqual(d.valors(), 60.0 / 0.5, places=1)  # 120 BPM
        self.assertIn("120", d.lb_tap.text())
        self.assertIn("TAP (4)", d.b_tap.text())

    def test_tap_usa_mediana(self):
        d = self._dlg()
        # intervals 0,5 · 0,9 (outlier) · 0,5 → mediana 0,5 → 120 BPM
        rellotge = _RellotgeFals([0.0, 0.5, 1.4, 1.9])
        with patch.object(dialegs, "time", rellotge):
            for _ in range(4):
                d._tap()
        self.assertAlmostEqual(d.valors(), 120.0, places=1)

    def test_tap_reinicia_si_passa_estona(self):
        d = self._dlg()
        rellotge = _RellotgeFals([0.0, 0.5, 10.0, 10.5])
        with patch.object(dialegs, "time", rellotge):
            for _ in range(4):
                d._tap()
        self.assertIn("TAP (2)", d.b_tap.text())
        self.assertAlmostEqual(d.valors(), 120.0, places=1)

    def test_emet_bpm_amb_escala_i_candidats(self):
        d = self._dlg()
        rebuts = []
        d.bpm_canviat.connect(rebuts.append)
        d.mostra_bpm(120.0, candidats=[(120.0, 0.9), (103.0, 0.7)])
        d._escala(2.0)                              # ×2 → 240
        self.assertAlmostEqual(rebuts[-1], 240.0, places=1)
        d.ed_bpm.setText("96.5")
        d._bpm_escrit("96.5")
        self.assertAlmostEqual(rebuts[-1], 96.5, places=2)
        d.ed_bpm.setText("")
        d._bpm_escrit("")
        self.assertAlmostEqual(rebuts[-1], 96.5, places=2)   # res vàlid: no emet

    def test_tria_candidat_emet(self):
        d = self._dlg()
        rebuts = []
        d.bpm_canviat.connect(rebuts.append)
        d.mostra_bpm(120.0, candidats=[(120.0, 0.9), (103.4, 0.7)])
        d._tria_candidat(0)                         # la 1a alternativa
        self.assertAlmostEqual(d.valors(), 103.4, places=2)
        self.assertAlmostEqual(rebuts[-1], 103.4, places=2)

    def test_tecles_t_i_espai(self):
        from PyQt5.QtCore import QEvent, Qt
        from PyQt5.QtGui import QKeyEvent
        d = self._dlg()
        cops = []
        d.vol_reproduir.connect(lambda: cops.append(1))
        d.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Space,
                                  Qt.NoModifier))
        self.assertEqual(len(cops), 1)
        rellotge = _RellotgeFals([1.0, 1.5])
        with patch.object(dialegs, "time", rellotge):
            for _ in range(2):
                d.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_T,
                                          Qt.NoModifier))
        self.assertAlmostEqual(d.valors(), 120.0, places=1)

    def test_tecles_no_activen_mentre_s_edita(self):
        from PyQt5.QtCore import QEvent, Qt
        from PyQt5.QtGui import QKeyEvent
        d = self._dlg()
        cops = []
        d.vol_reproduir.connect(lambda: cops.append(1))
        with patch.object(d, "focusWidget", return_value=d.ed_bpm):
            d.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Space,
                                      Qt.NoModifier))
        self.assertEqual(cops, [])

    def test_set_reproduint(self):
        d = self._dlg()
        d.set_reproduint(True)
        self.assertIn("Pausa", d.b_repro.text())
        d.set_reproduint(False)
        self.assertIn("Escolta", d.b_repro.text())

    def test_tecla_0_tambe_es_tap(self):
        from PyQt5.QtCore import QEvent, Qt
        from PyQt5.QtGui import QKeyEvent
        d = self._dlg()
        rellotge = _RellotgeFals([1.0, 1.5])
        with patch.object(dialegs, "time", rellotge):
            for k in (Qt.Key_0, Qt.Key_0):
                d.keyPressEvent(QKeyEvent(QEvent.KeyPress, k,
                                          Qt.NoModifier))
        self.assertAlmostEqual(d.valors(), 120.0, places=1)
        self.assertIn("TAP (2)", d.b_tap.text())

    def test_combo_de_mides_del_tram(self):
        d = self._dlg()
        textos = [d.cb_compassos.itemText(i)
                  for i in range(d.cb_compassos.count())]
        self.assertEqual(textos, ["4 compassos", "8 compassos",
                                  "16 compassos", "32 compassos"])
        d.cb_compassos.setCurrentIndex(d.cb_compassos.findText("16 compassos"))
        self.assertEqual(d.compassos(), 16)
        d._canvia_compassos(+1)                     # 17: no és preset
        self.assertEqual(d.compassos(), 17)
        self.assertEqual(d.cb_compassos.currentText(), "17 compassos")
        d._canvia_compassos(-1)                     # torna a 16 (preset)
        self.assertEqual(d.cb_compassos.currentText(), "16 compassos")

    def test_historia_de_bpm_anterior(self):
        d = self._dlg()
        d.mostra_bpm(104.0, hist=[(3, 103.4), (2, 103.1)])
        self.assertEqual(d._b_hist[0].text(), "tram 3 · 103.40")
        self.assertEqual(d._b_hist[1].text(), "tram 2 · 103.10")
        self.assertTrue(d._b_hist[0].isVisibleTo(d))
        rebuts = []
        d.bpm_canviat.connect(rebuts.append)
        d._tria_hist(1)
        self.assertAlmostEqual(d.valors(), 103.1, places=2)
        self.assertAlmostEqual(rebuts[-1], 103.1, places=2)
        # sense història, les pastilles s'amaguen
        d.mostra_bpm(104.0)
        self.assertFalse(d._b_hist[0].isVisibleTo(d))

    def test_set_confirmacio(self):
        d = self._dlg()
        d.set_confirmacio({"detall": "✓ fiable (tram anterior 103.40)"})
        self.assertIn("fiable", d.lb_confirma.text())
        self.assertTrue(d.lb_confirma.isVisibleTo(d))
        d.set_confirmacio({})
        self.assertFalse(d.lb_confirma.isVisibleTo(d))


class TestGuiatAudicio(unittest.TestCase):
    """Guiat v2 a la Finestra: bucle del tram + metrònom forçat en viu."""

    def setUp(self):
        self._app = QApplication.instance() or QApplication([])
        self.td = tempfile.mkdtemp()
        # Nom ÚNIC: si es diu «tema.wav», `tria_wav` pot reutilitzar un
        # projecte recent amb eixe nom i contaminar el test.
        self.wav = os.path.join(self.td, f"tema_{uuid.uuid4().hex[:8]}.wav")
        with wave.open(self.wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * 60)          # 60 s
        self.motors = []
        self._p_motor = patch.object(audio_out, "crea_motor", self._motor)
        self._p_motor.start()
        self._p_fil = patch.object(app_main, "FilGuiaBpm", _FilFals)
        self._p_fil.start()
        self.w = Finestra()
        self.w.opcions["guiat"] = {"compassos": 4, "confirma": True}
        _opcions_temporals(self, self.td)
        acproj = os.path.join(self.td, "P1.acproj")
        with patch.object(QFileDialog, "getOpenFileName",
                          return_value=(self.wav, "")), \
                patch.object(QFileDialog, "getSaveFileName",
                             return_value=(acproj, "")):
            self.w.tria_wav()

    def _motor(self, *_a, **_k):
        m = _MotorMut()
        self.motors.append(m)
        return m

    def tearDown(self):
        for m in self.motors:
            m.atura()
        self.w.close()
        self._p_fil.stop()
        self._p_motor.stop()
        shutil.rmtree(self.td, ignore_errors=True)

    def _arrenca(self, t=1.0):
        w = self.w
        w._analisi_guitat()
        w.visor_ref.pos = t
        w._guia_pas1_fet()
        return w, w.visor_ref

    def test_audicio_loop_i_metronom(self):
        w, vr = self._arrenca(t=1.0)
        try:
            self.assertIn("dlg2", w._guia)
            w._guia_bpm_ditectat(120.0)
            t_k = w._guia["t_k"]
            self.assertAlmostEqual(t_k, 1.0, places=6)
            # 4 compassos de 4/4 a 120 BPM = 8 s
            self.assertAlmostEqual(vr.loop_a, t_k, places=6)
            self.assertAlmostEqual(vr.loop_b, 9.0, places=6)
            self.assertEqual(tuple(vr.metro_forcat), (120.0, 4, 1.0))
            self.assertTrue(vr.metro_on)
            aud = w._guia["audicio"]
            self.assertAlmostEqual(aud[1], 9.0, places=6)
            self.assertEqual(aud[2], 120.0)
            self.assertIn("Pausa", w._guia["dlg2"].b_repro.text())
        finally:
            w._guia_cancel()
        self.assertIsNone(vr.metro_forcat)
        self.assertFalse(vr.metro_on)

    def test_bpm_en_viu_mou_el_metronom_i_el_bucle(self):
        w, vr = self._arrenca(t=1.0)
        try:
            w._guia_bpm_ditectat(120.0)
            w._guia_bpm_canviat(100.0)
            self.assertEqual(tuple(vr.metro_forcat), (100.0, 4, 1.0))
            # 4 compassos de 4/4 a 100 BPM = 9,6 s → 10,6 (cap dins 12 s)
            self.assertAlmostEqual(vr.loop_b, 10.6, places=6)
        finally:
            w._guia_cancel()

    def test_bpm_canviat_sense_audicio_no_fa_res(self):
        w, vr = self._arrenca(t=1.0)
        try:
            abans = (vr.loop_a, vr.loop_b, vr.metro_forcat)
            w._guia_bpm_canviat(140.0)
            self.assertEqual((vr.loop_a, vr.loop_b, vr.metro_forcat), abans)
        finally:
            w._guia_cancel()

    def test_play_pausa(self):
        w, vr = self._arrenca(t=1.0)
        try:
            w._guia["dlg2"].mostra_bpm(120.0)
            w._guia_play_pausa()            # arrenca (audició amb metrònom)
            self.assertTrue(vr.sona)
            w._guia_play_pausa()            # pausa
            self.assertFalse(vr.sona)
            self.assertIn("Escolta", w._guia["dlg2"].b_repro.text())
        finally:
            w._guia_cancel()

    def test_metrica_i_compassos_del_dialeg_manen(self):
        w, vr = self._arrenca(t=1.0)
        try:
            d = w._guia["dlg2"]
            d.cb_metrica.setCurrentIndex(d.cb_metrica.findText("3/4"))
            d._canvia_compassos(+1)                 # 5 compassos de 3/4
            w._guia_bpm_ditectat(120.0)
            # 5 × 1,5 s = 7,5 s
            self.assertAlmostEqual(vr.loop_b, 8.5, places=6)
            w._guia_fenestra_aplica(d)
            trams = vr.tempo_trams
            self.assertTrue(any(t[2] == 120.0 and t[3] == 3 and t[4] == 4
                                for t in trams), trams)
            tram = [t for t in trams if abs(t[0] - 1.0) < 1e-6][0]
            self.assertAlmostEqual(tram[1], 8.5, places=6)
        finally:
            w._guia_cancel()

    def test_mida_8_compassos_amplia_la_finestra_i_es_desa(self):
        """La mida triada mana a la finestra, a la detecció i al tram."""
        w = self.w
        w.opcions["guiat"] = {"compassos": 8, "confirma": False}
        capturat = []

        class _FilCap(app_main.FilGuiaBpm):
            def __init__(self, wav, ini, fi, **kw):
                capturat.append({"ini": ini, "fi": fi, **kw})
                super().__init__(wav, ini, fi, **kw)

            def start(self, *_a, **_k):
                pass

        with patch.object(app_main, "FilGuiaBpm", _FilCap):
            w._analisi_guitat()
            w.visor_ref.pos = 2.0
            w._guia_pas1_fet()
        try:
            self.assertEqual(w._guia["compassos"], 8)
            c = capturat[0]
            # 8 compassos a 120 BPM (suposat al 1r tram) = 16 s
            self.assertAlmostEqual(c["ini"], 2.0, places=6)
            self.assertAlmostEqual(c["fi"] - c["ini"], 16.0, places=6)
            self.assertFalse(c["confirmar"])
            self.assertIsNone(c["prev"])
            # el tros llarg de reforç demana el doble de finestra
            self.assertAlmostEqual(c["fi_llarga"], 34.0, places=6)
        finally:
            w._guia_cancel()

    def test_confirma_i_tros_llarg_arriben_al_fil(self):
        w = self.w
        w.opcions["guiat"] = {"compassos": 4, "confirma": True}
        capturat = []

        class _FilCap(app_main.FilGuiaBpm):
            def __init__(self, wav, ini, fi, **kw):
                capturat.append({"ini": ini, "fi": fi, **kw})
                super().__init__(wav, ini, fi, **kw)

            def start(self, *_a, **_k):
                pass

        with patch.object(app_main, "FilGuiaBpm", _FilCap):
            w._analisi_guitat()
            w.visor_ref.pos = 2.0
            w._guia_pas1_fet()
        try:
            self.assertTrue(capturat[0]["confirmar"])
            # 4 compassos a 120 = 8 s; el reforç llarg = 16 s
            self.assertAlmostEqual(capturat[0]["fi_llarga"], 18.0, places=6)
        finally:
            w._guia_cancel()

    def test_confirmacio_dubtosa_al_dialeg(self):
        w, vr = self._arrenca(t=1.0)
        try:
            w._guia_bpm_ditectat(
                {"bpm": 51.7, "candidats": [], "alternatives": [],
                 "ref": 103.4,
                 "confirma": {"prev": 103.0, "banda": 103.4,
                              "llarga": 103.5}})
            txt = w._guia["dlg2"].lb_confirma.text()
            self.assertIn("dubtós", txt)
            self.assertIn("51.70", txt)
        finally:
            w._guia_cancel()

    def test_confirmacio_fiable_al_dialeg(self):
        w, vr = self._arrenca(t=1.0)
        try:
            w._guia_bpm_ditectat(
                {"bpm": 103.4, "candidats": [], "alternatives": [],
                 "ref": 103.4,
                 "confirma": {"prev": 103.0, "banda": 103.5,
                              "llarga": 103.3}})
            self.assertIn("fiable", w._guia["dlg2"].lb_confirma.text())
        finally:
            w._guia_cancel()

    def test_historia_de_bpm_arriba_al_tram_seguent(self):
        w, vr = self._arrenca(t=1.0)
        try:
            w._guia_bpm_ditectat(103.4)
            d1 = w._guia["dlg2"]
            self.assertEqual(w._guia["bpm_hist"], [])
            w._guia_fenestra_aplica(d1)          # tram 1 aplicat → tram 2
            d2 = w._guia["dlg2"]
            w._guia_bpm_ditectat(103.6)
            self.assertEqual(d2._b_hist[0].text(), "tram 1 · 103.40")
            self.assertEqual(w._guia["bpm_hist"], [(1, 103.4)])
            # clicar la pastilla posa el BPM al camp
            d2._tria_hist(0)
            self.assertAlmostEqual(d2.valors(), 103.4, places=2)
        finally:
            w._guia_cancel()

    def test_la_mida_del_tram_es_recorda_per_al_seguent(self):
        w, vr = self._arrenca(t=1.0)
        try:
            d1 = w._guia["dlg2"]
            d1.cb_compassos.setCurrentIndex(
                d1.cb_compassos.findText("16 compassos"))
            w._guia_bpm_ditectat(120.0)
            w._guia_fenestra_aplica(d1)
            self.assertEqual(w._guia["compassos"], 16)
            self.assertEqual(w._guia["dlg2"].compassos(), 16)
            # i queda desada a les opcions (fitxer temporal de la suite)
            self.assertEqual(dialegs.carrega_opcions()["guiat"]["compassos"],
                             16)
        finally:
            w._guia_cancel()

    def test_mesura_usa_la_instantania_i_no_l_audicio(self):
        w = self.w
        vr = w.visor_ref
        vr._fixa_loop(2.0, 8.0, alinea=False)       # loop de l'usuari
        w._analisi_guitat()
        vr.pos = 2.0
        w._guia_pas1_fet()
        try:
            self.assertEqual(tuple(w._guia["loop"]), (2.0, 8.0))
            w._guia_bpm_ditectat(120.0)
            self.assertAlmostEqual(vr.loop_a, 2.0, places=6)
            self.assertAlmostEqual(vr.loop_b, 10.0, places=6)   # audició
            # la instantània no s'ha tocat: la mesura no veu el bucle nou
            self.assertEqual(tuple(w._guia["loop"]), (2.0, 8.0))
        finally:
            w._guia_cancel()
        # en cancel·lar, el loop de l'usuari torna
        self.assertAlmostEqual(vr.loop_a, 2.0, places=6)
        self.assertAlmostEqual(vr.loop_b, 8.0, places=6)
        self.assertFalse(vr.metro_on)


# ===========================================================================
# Diàleg d'ancoratges (Anàlisi guiat v3) — doc: docs/ANALISI_GUIAT_v3.md
# ===========================================================================
class TestDialegAncoratges(unittest.TestCase):
    """La finestra de l'operador: TAP, desfer, esborrar, llindars i generar."""

    @classmethod
    def setUpClass(cls):
        cls._app = QW.QApplication.instance() or QW.QApplication([])

    def setUp(self):
        from app.dialeg_ancoratges import DialegAncoratges
        self._dlg = []
        self.D = DialegAncoratges

    def tearDown(self):
        for d in self._dlg:
            d._neteja()
            d.deleteLater()

    def _nou(self, **kw):
        kw.setdefault("opcions", {"velocitat": 1.0})
        d = self.D(None, "/tmp/no_existeix_ac.wav", 12.0, **kw)
        self._dlg.append(d)
        return d

    @staticmethod
    def _marcs(d, t1=0.5, t2=2.5):
        """Fix els dos marcs (① compàs 1, ② compàs 2) sense passar per la UI."""
        d._marcs = [t1, t2]
        d._actualitza_rang()

    def test_afegeix_i_desfer_torna_enrere(self):
        d = self._nou()
        d._pos = 3.0
        self.assertTrue(d._afegeix())
        self.assertEqual(len(d.ancoratges()), 1)
        self.assertAlmostEqual(d.ancoratges()[0]["t"], 3.0)
        d._desfer()
        self.assertEqual(d.ancoratges(), [])
        self.assertAlmostEqual(d._pos, 1.0)      # 2 s enrere (R13)
        self.assertFalse(d.b_genera.isEnabled() is None)

    def test_autorepeticio_no_duplica(self):
        d = self._nou()
        d._pos = 2.0
        self.assertTrue(d._afegeix())
        d._pos = 2.10                            # < 0,15 s: rebot
        self.assertFalse(d._afegeix())
        self.assertEqual(len(d.ancoratges()), 1)

    def test_esborra_i_desfer(self):
        d = self._nou()
        d._pos = 1.0
        d._afegeix()
        d._pos = 4.0
        d._afegeix()
        d._esborra(0)
        self.assertEqual(len(d.ancoratges()), 1)
        self.assertAlmostEqual(d.ancoratges()[0]["t"], 4.0)
        d._desfer()
        self.assertEqual(len(d.ancoratges()), 2)
        self.assertAlmostEqual(d.ancoratges()[0]["t"], 1.0)

    def test_metre_de_l_ancoratge_i_canvi(self):
        d = self._nou()
        d.cb_compas.setCurrentText("3/4")
        d._pos = 2.0
        d._afegeix()
        self.assertEqual((d.ancoratges()[0]["num"], d.ancoratges()[0]["den"]),
                         (3, 4))
        self.assertTrue(d._canvia_metre(0, "7/8"))
        self.assertEqual((d.ancoratges()[0]["num"], d.ancoratges()[0]["den"]),
                         (7, 8))
        self.assertFalse(d._canvia_metre(0, "0/4"))

    def test_delay_retroactiu(self):
        d = self._nou()
        d.sp_delay.setValue(150)
        d._pos = 5.0
        d._afegeix()
        self.assertAlmostEqual(d.ancoratges()[0]["t"], 4.85)

    def test_llindars_han_de_ser_creixents(self):
        d = self._nou()
        self.assertFalse(d.b_genera.isEnabled())   # falten els 2 marcs
        self._marcs(d)
        d._pos = 3.0
        d._afegeix()
        self.assertTrue(d.b_genera.isEnabled())
        d.sp_sosp.setValue(0.5)                  # nota=1 > sosp=0,5
        self.assertFalse(d.b_genera.isEnabled())
        d.sp_sosp.setValue(3.0)
        self.assertTrue(d.b_genera.isEnabled())

    def test_genera_encaixa_i_aplica(self):
        rebut = {}
        def aplicar(trams, offset, ancoratges):
            rebut.update(trams=trams, offset=offset, anc=ancoratges)
            return True
        d = self._nou(bpm_global=120.0, aplicar=aplicar)
        self._marcs(d, 0.5, 2.5)
        for t in (0.5, 2.5, 4.5):
            d._pos = t
            d._afegeix()
        d._genera()
        self.assertIn("trams", rebut)
        self.assertAlmostEqual(rebut["offset"], 0.5)
        self.assertEqual(len(rebut["trams"]), 3)
        self.assertAlmostEqual(rebut["trams"][0][2], 120.0, places=3)
        self.assertEqual(d.result(), d.Accepted)

    def test_no_encaixa_no_aplica_res(self):
        crides = []
        d = self._nou(bpm_global=120.0,
                      aplicar=lambda *a: crides.append(a) or True)
        d.sp_no.setValue(0.3)                    # 0,3 %: massa estret
        d.sp_sosp.setValue(0.2)
        d.sp_nota.setValue(0.1)
        self._marcs(d, 0.0, 2.0)
        for t in (0.0, 2.0, 2.3):                # el 2n interval (0,3 s) no
            d._pos = t                           # cap a cap BPM del rang
            d._afegeix()
        d._genera()
        self.assertEqual(crides, [])
        self.assertNotEqual(d.result(), d.Accepted)
        self.assertNotEqual(d._resultat["intervals"][1]["estat"], "ok")
        self.assertIn("interval 2", d.lb_avis.text())   # missatge amb detall

    def test_dos_marcs_donen_el_rang_de_bpm(self):
        """①②: compàs 1 (offset) i compàs 2 → BPM aproximat i rang ±10 %."""
        pos = {"t": 2.0}
        d = self._nou(posicio_cursor=lambda: pos["t"])
        pos["t"] = 2.0
        d._marca(1)                     # compàs 1 → offset + ancoratge
        self.assertEqual(len(d.ancoratges()), 1)
        self.assertAlmostEqual(d.ancoratges()[0]["t"], 2.0)
        pos["t"] = 4.3
        d._marca(2)                     # compàs 2 a 2,3 s → 1 compàs 4/4
        # 4 · 60 / 2,3 = 104,35 BPM; rang 93,9–114,8
        self.assertAlmostEqual(d._bpm_prov, 4 * 60 / 2.3, places=3)
        lo, hi = d._rang
        self.assertAlmostEqual(lo, 104.35 * 0.9, places=1)
        self.assertAlmostEqual(hi, 104.35 * 1.1, places=1)
        self.assertIn("104", d.lb_rang.text())
        self.assertTrue(d.b_genera.isEnabled())

    def test_sense_marcs_no_es_genera(self):
        d = self._nou(bpm_global=120.0)
        d._pos = 2.0
        d._afegeix()
        self.assertFalse(d.b_genera.isEnabled())
        self.assertIn("compàs 1", d.lb_avis.text())
        d._genera()                     # no fa res (no aplica ni accepta)
        self.assertIsNone(d._resultat)
        self.assertNotEqual(d.result(), d.Accepted)

    def test_el_rang_descarta_el_doble_de_bpm(self):
        """Amb el tema a ~104, un n que donaria 208 ha de quedar fora."""
        d = self._nou()
        self._marcs(d, 2.0, 4.3)        # ~104 BPM
        for t in (2.0, 4.3):
            d._pos = t
            d._afegeix()
        d._genera()
        self.assertEqual(d._resultat["intervals"][0]["n"], 1)
        self.assertAlmostEqual(d._resultat["intervals"][0]["bpm"], 104.35,
                               places=2)

    def test_doble_i_meitat_de_compassos(self):
        """R8: ×2 / ÷2 per interval (força `n`) — no toca els ancoratges."""
        d = self._nou(bpm_global=120.0)
        self._marcs(d, 0.5, 2.5)
        for t in (0.5, 2.5, 4.5):
            d._pos = t
            d._afegeix()
        d._genera()                              # 2 intervals d'1 compàs
        self.assertEqual([i["n"] for i in d._resultat["intervals"]], [1, 1])
        self.assertTrue(d._canvia_n(0, 2))       # ×2 al primer
        self.assertEqual(d._resultat["intervals"][0]["n"], 2)
        self.assertAlmostEqual(d._resultat["intervals"][0]["bpm"], 240.0,
                               places=3)
        self.assertTrue(d._canvia_n(0, 0.5))     # ÷2 torna a 1
        self.assertEqual(d._resultat["intervals"][0]["n"], 1)
        self.assertEqual(len(d.ancoratges()), 3)   # els ancoratges no es toquen

    def test_deteccio_nomes_als_intervals_dolents(self):
        """R6: només es detecta on la cadena no quadra, i només si millora."""
        crides = []

        def detector(ini, fi):
            crides.append((round(ini, 2), round(fi, 2)))
            return 120.0

        d = self._nou(bpm_global=120.0, detector=detector)
        self._marcs(d, 0.5, 2.5)
        for t in (0.5, 2.5, 4.5):
            d._pos = t
            d._afegeix()
        d._genera()
        self.assertEqual(crides, [])             # tot encaixa: ni una detecció

        d2 = self._nou(bpm_global=60.0, detector=lambda a, b: 120.0)
        self._marcs(d2, 0.5, 2.5)
        for t in (0.5, 2.5, 4.5):
            d2._pos = t
            d2._afegeix()
        d2._genera()                              # 120 vs 60 → dolents
        self.assertTrue(crides or d2._resultat is not None)

    def test_opcions_rodones(self):
        d = self._nou(opcions={"delay_ms": 40, "velocitat": 0.5,
                               "compas": "6/8", "n_max": 32,
                               "desv_nota": 0.01, "desv_sospitos": 0.03,
                               "desv_no_encaixa": 0.10})
        o = d.opcions()
        self.assertEqual(o["delay_ms"], 40)
        self.assertAlmostEqual(o["velocitat"], 0.5)
        self.assertEqual(o["compas"], "6/8")
        self.assertEqual(o["n_max"], 32)
        self.assertAlmostEqual(o["desv_sospitos"], 0.03)

    def test_temporals_a_la_paperera(self):
        d = self._nou()
        d._temporals = ["/tmp/inventat_ac_vel_0.5.wav"]
        from app import plataforma
        with patch.object(plataforma, "a_la_paperera") as f:
            d._neteja()
        f.assert_called_once_with("/tmp/inventat_ac_vel_0.5.wav")
        self.assertEqual(d._temporals, [])

    def test_cursor_del_visor_segueix_l_audicio(self):
        """Integració: el cursor del visor avança amb el só del diàleg."""
        vist = []
        d = self._nou(mou_cursor=vist.append, inici=7.5)
        self.assertAlmostEqual(d._pos, 7.5)          # arrenca on era el cursor
        d._pausa_i_vés(12.0)                         # salt d'un ancoratge
        self.assertAlmostEqual(vist[-1], 12.0)

        class _Rep:
            def esta_sonant(self):
                return True

            def posicio(self):
                return 3.0

            def pausa(self):
                pass

            def atura(self):
                pass

            def tanca(self):
                pass

        d._rep = _Rep()
        d._tick()
        self.assertAlmostEqual(vist[-1], 3.0)        # el tick mou el cursor

    def test_botons_de_velocitat_amb_1_5(self):
        from PyQt5.QtTest import QTest
        d = self._nou()
        d.show()
        b = {x.text(): x for x in d.findChildren(QW.QPushButton)
             if x.property("vel") is not None}
        self.assertEqual(sorted(b), sorted(["½", "⅔", "1×", "1,5×", "2×", "4×"]))
        self.assertTrue(b["1×"].isChecked())
        b["1,5×"].click()
        self.assertAlmostEqual(d.opcions()["velocitat"], 1.5)
        self.assertTrue(b["1,5×"].isChecked())
        self.assertFalse(b["1×"].isChecked())
        b["⅔"].click()                         # ÷1,5
        self.assertAlmostEqual(d.opcions()["velocitat"], 2.0 / 3.0)
        # tecles 1…6 en el mateix ordre
        QTest.keyClick(d, Qt.Key_4)
        self.assertAlmostEqual(d.opcions()["velocitat"], 1.5)
        QTest.keyClick(d, Qt.Key_2)
        self.assertAlmostEqual(d.opcions()["velocitat"], 2.0 / 3.0)
        d.hide()

    def test_tecla_mes_afegeix_ancoratge(self):
        from PyQt5.QtTest import QTest
        d = self._nou()
        d.show()
        d._pos = 3.5
        QTest.keyClick(d, Qt.Key_Plus)                 # «+» de dalt del teclat
        self.assertEqual(len(d.ancoratges()), 1)
        self.assertAlmostEqual(d.ancoratges()[0]["t"], 3.5)
        d._pos = 6.0
        QTest.keyClick(d, Qt.Key_Plus, Qt.KeypadModifier)   # «+» del NUMÈRIC
        self.assertEqual(len(d.ancoratges()), 2)
        self.assertAlmostEqual(d.ancoratges()[1]["t"], 6.0)
        d._pos = 9.0
        QTest.keyClick(d, Qt.Key_Equal, Qt.ShiftModifier)   # Maj+«=»
        self.assertEqual(len(d.ancoratges()), 3)
        self.assertAlmostEqual(d.ancoratges()[1]["t"], 6.0)
        # el «+» del NUMÈRIC i el de dalt són atalls de finestra (no depenen
        # del focus: un QLineEdit s'empassa la tecla i no arriba al diàleg)
        claus = [sc.key().toString() for sc in d._atallets]
        self.assertEqual(len(claus), 2)
        self.assertIn("+", claus)
        # les fletxes JA NO afiguen res (donaven problemes)
        d._pos = 20.0
        QTest.keyClick(d, Qt.Key_Down)
        QTest.keyClick(d, Qt.Key_Up)
        self.assertEqual(len(d.ancoratges()), 3)
        QTest.keyClick(d, Qt.Key_Space)      # Espai = play/pausa del diàleg
        d.hide()

    def test_velocitat_canvia_el_factor(self):
        d = self._nou()
        d._velocitat(0.5)
        self.assertAlmostEqual(d.opcions()["velocitat"], 0.5)
        self.assertAlmostEqual(d._rep.factor if d._rep else 0.5, 0.5)



class TestAncoratgesFinestra(unittest.TestCase):
    """v3 a la Finestra: el mapa encaixat s'aplica com UN sol desfer."""

    @classmethod
    def setUpClass(cls):
        cls._app = QW.QApplication.instance() or QW.QApplication([])

    def setUp(self):
        self.td = tempfile.mkdtemp()
        # Nom ÚNIC: si es diu «tema.wav», `tria_wav` pot reutilitzar un
        # projecte recent amb eixe nom i contaminar el test.
        self.wav = os.path.join(self.td, f"tema_{uuid.uuid4().hex[:8]}.wav")
        with wave.open(self.wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * 60)          # 60 s
        self.motors = []
        self._p_motor = patch.object(audio_out, "crea_motor",
                                     lambda *a, **k: self.motors.append(
                                         _MotorMut()) or self.motors[-1])
        self._p_motor.start()
        _opcions_temporals(self, self.td)
        self.w = Finestra()
        acproj = os.path.join(self.td, "P1.acproj")
        with patch.object(QFileDialog, "getOpenFileName",
                          return_value=(self.wav, "")), \
                patch.object(QFileDialog, "getSaveFileName",
                             return_value=(acproj, "")):
            self.w.tria_wav()
        # Estat de partida CONEGUT: si l'app ha recuperat una sessió o un
        # projecte d'una prova anterior, el test ha de començar igualment net.
        vr0 = self.w.visor_ref
        vr0.offset = 0.0
        vr0.aplica_tempo_trams([(0.0, 60.0, 120.0, 4, 4)])
        vr0.seccions = [(0.0, 60.0, "A", "A")]
        vr0.marcadors = []
        vr0._pinta_marcadors()
        vr0.timeline.set_data(vr0.acords, vr0.seccions)
        vr0._undo_stack.clear()
        vr0._undo_base = vr0._estat_complet()

    def tearDown(self):
        for m in self.motors:
            m.atura()
        self.w.close()
        self._p_motor.stop()
        shutil.rmtree(self.td, ignore_errors=True)

    def test_aplica_el_mapa_i_es_un_sol_desfer(self):
        vr = self.w.visor_ref
        abans = [tuple(t) for t in (vr.tempo_trams or [])]
        trams = [(1.0, 3.0, 120.0, 4, 4), (3.0, 5.0, 120.0, 4, 4),
                 (5.0, 60.0, 120.0, 4, 4)]
        sec0 = list(vr.seccions)
        self.assertTrue(self.w._aplica_ancoratges(
            trams, 1.0, [{"t": 1.0}, {"t": 3.0}, {"t": 5.0}]))
        self.assertAlmostEqual(vr.offset, 1.0, places=6)
        # el validador afig el tros del «cap» (0→1 s): el mapa té 3 trams
        # d'ancoratge + eixe, i el primer que comença a l'offset és el bo.
        tr = next(t for t in vr.tempo_trams if abs(t[0] - 1.0) < 1e-6)
        self.assertAlmostEqual(tr[2], 120.0, places=3)
        self.assertEqual(len([t for t in vr.tempo_trams if t[0] >= 1.0 - 1e-9]),
                         3)
        # el camp de compàs.beat del compàs 1 també s'ha refrescat
        self.assertTrue(self.w.offset_cb.text())
        # L'ESTRUCTURA també s'ha creat (1 secció per interval + «Intro»):
        # cada + és compàs 1 i secció nova (D3).
        lletres = [s[2] for s in vr.seccions]
        self.assertEqual(lletres, ["Intro", "A", "B", "C"])
        self.assertEqual(vr.seccions[0][0], 0.0)
        self.assertAlmostEqual(vr.seccions[-1][1], 60.0, places=6)
        # L'offset s'ha desat al document del projecte (si no, en reobrir-lo
        # la graella tornaria a compàs 1 = 0 i el mapa no quadraria)
        self.assertAlmostEqual(
            self.w.projecte.dades["tempo"]["offset"], 1.0, places=6)
        # UN sol desfer: mapa, offset, estructura i ABC tornen enrere alhora
        vr.undo()
        self.assertEqual([tuple(t) for t in (vr.tempo_trams or [])], abans)
        self.assertAlmostEqual(vr.offset, 0.0, places=6)
        self.assertEqual([tuple(s) for s in vr.seccions], sec0)

    def test_elimina_i_fusiona_despres_del_guiat(self):
        """Bug 21-10: després d'aplicar ancoratges, eliminar/fusionar un tram
        de tempo ha de funcionar (abans: «La frontera … no cau en una línia de
        compàs» per mil·lèsimes) i ha de ser UN sol desfer."""
        from app import ancoratges as A
        vr = self.w.visor_ref
        anc = [{"t": 27.989, "num": 4, "den": 4}, {"t": 30.379, "num": 4, "den": 4},
               {"t": 35.157, "num": 4, "den": 4}, {"t": 39.595, "num": 4, "den": 4}]
        r = A.encaixa_ancoratges(anc, 60.0, None, 120.0)
        self.assertTrue(self.w._aplica_ancoratges(r["trams"], r["offset"], anc))
        abans = [tuple(t) for t in vr.tempo_trams]
        self.assertTrue(vr._elimina_tram(1))
        self.assertEqual(len(vr.tempo_trams), len(abans) - 1)
        self.assertAlmostEqual(vr.tempo_trams[0][1], 35.159, places=3)
        vr.undo()
        self.assertEqual([tuple(t) for t in vr.tempo_trams], abans)
        self.assertTrue(vr._fusiona_tram(0))
        self.assertEqual(len(vr.tempo_trams), len(abans) - 1)

    def test_arrossegar_una_vora_de_tempo_segueix_el_ratoli(self):
        """Re-tempo (21-10-2026): la frontera va ON deixa anar el ratolí.

        Abans s'imantava a una línia de compàs del tram anterior i
        s'arrossegaven els trams següents (`_ripple`); ara mana el punter
        (`docs/FLUX DE TEMPO VARIABLE.md` §2) i cap altre tram es mou.
        """
        from app import ancoratges as A
        vr = self.w.visor_ref
        anc = [{"t": 27.989, "num": 4, "den": 4}, {"t": 30.379, "num": 4, "den": 4},
               {"t": 35.157, "num": 4, "den": 4}, {"t": 39.595, "num": 4, "den": 4}]
        r = A.encaixa_ancoratges(anc, 60.0, None, 120.0)
        self.assertTrue(self.w._aplica_ancoratges(r["trams"], r["offset"], anc))
        abans = [tuple(t) for t in vr.tempo_trams]

        def arrossega(idx, vora, t):        # el gest real: marca → mou → tanca
            vr.timeline.editStarted.emit()
            vr._on_tempo_mogut(idx, vora, t)
            vr.timeline.editFinished.emit()

        fi_ultim = float(vr.tempo_trams[-1][1])
        arrossega(0, "fi", 31.5)                   # cap a la dreta
        self.assertAlmostEqual(vr.tempo_trams[0][1], 31.5, places=3)
        self.assertAlmostEqual(float(vr.tempo_trams[-1][1]), fi_ultim,
                               places=6)           # cap altre tram no es mou
        self.assertNotEqual([tuple(t) for t in vr.tempo_trams], abans)
        vr.undo()
        self.assertEqual([tuple(t) for t in vr.tempo_trams], abans)
        arrossega(1, "ini", 29.0)                  # cap a l'esquerra
        self.assertAlmostEqual(vr.tempo_trams[0][1], 29.0, places=3)

    def test_esborrar_diversos_trams_de_cop(self):
        """La multi-selecció del carril de tempo també s'ha de poder esborrar."""
        from app import ancoratges as A
        vr = self.w.visor_ref
        anc = [{"t": 27.989, "num": 4, "den": 4}, {"t": 30.379, "num": 4, "den": 4},
               {"t": 35.157, "num": 4, "den": 4}, {"t": 39.595, "num": 4, "den": 4}]
        r = A.encaixa_ancoratges(anc, 60.0, None, 120.0)
        self.assertTrue(self.w._aplica_ancoratges(r["trams"], r["offset"], anc))
        n = len(vr.tempo_trams)
        vr._elimina_seleccio([("tempo", 1), ("tempo", 2)])
        self.assertEqual(len(vr.tempo_trams), n - 2)
        TM = __import__("app.tempo_map", fromlist=["x"])
        TM.valida_i_normalitza_compassos(vr.tempo_trams, 60.0, vr.offset)

    def test_mapa_invalid_no_toca_res(self):
        vr = self.w.visor_ref
        abans = [tuple(t) for t in (vr.tempo_trams or [])]
        # frontera interior que no és línia de compàs (2 s a 120 BPM = 1 compàs,
        # però el tros 1→2 només en té mig)
        with patch.object(vr, "avis_editor") as av:
            self.assertFalse(self.w._aplica_ancoratges(
                [(1.0, 2.0, 120.0, 4, 4), (2.0, 60.0, 120.0, 4, 4)], 1.0, []))
        av.assert_called_once()          # avisa pel visor (l'editor del tempo)
        self.assertEqual([tuple(t) for t in (vr.tempo_trams or [])], abans)
        self.assertAlmostEqual(vr.offset, 0.0, places=6)

    def test_opcions_del_dialeg_es_desen(self):
        """Regressió 21-10: `_desa_opcions` no existia → AttributeError en
        acceptar el diàleg (el mapa s'aplicava però es perdia la configuració)."""
        from app import dialeg_ancoratges as DA
        import json

        class _Dlg:
            Accepted = 1

            def __init__(self, *a, **kw):
                pass

            def exec_(self):
                return 1

            def opcions(self):
                return {"velocitat": 1.5, "delay_ms": 30, "compas": "6/8",
                        "n_max": 32, "desv_nota": 0.01,
                        "desv_sospitos": 0.03, "desv_no_encaixa": 0.1}

        with patch.object(DA, "DialegAncoratges", _Dlg):
            self.w._analisi_ancoratges()
        self.assertAlmostEqual(self.w.opcions["ancoratges"]["velocitat"], 1.5)
        with open(dialegs.FITXER_OPCIONS, encoding="utf-8") as f:
            desat = json.load(f)
        self.assertAlmostEqual(desat["ancoratges"]["velocitat"], 1.5)

    def test_cursor_del_visor_segueix_el_temps(self):
        vr = self.w.visor_ref
        self.w._mou_cursor_guia(12.5)
        self.assertAlmostEqual(vr.pos, 12.5, places=6)
        self.assertAlmostEqual(vr.timeline._pos_t, 12.5, places=6)
        self.assertEqual(vr.lliscador.value(), 1250)  # barra lliscant al dia

    def test_marcador_crea_inicis_de_clip_i_va_lligat_a_la_frontera(self):
        """Un marcador = inici de clip a BPM/compàs I a estructura; després
        **viatja amb la frontera** i desapareix si la frontera desapareix
        (decisió de l'operador 21-10-2026, `docs/FLUX DE TEMPO VARIABLE.md`
        §4.C)."""
        vr = self.w.visor_ref
        vr.tempo_trams = [(0.0, 60.0, 120.0, 4, 4)]
        vr.seccions = [(0.0, 60.0, "A", "A")]
        vr.timeline.set_data(vr.acords, vr.seccions)
        vr.marcadors = []
        vr._undo_touch_base()          # estat de partida consolidat
        vr.pos = 12.0
        self.assertTrue(vr.afegeix_marcador())
        self.assertEqual(len(vr.marcadors), 1)
        self.assertAlmostEqual(vr.marcadors[0], 12.0, places=6)
        # inicia un clip de tempo a 12 s i una secció a 12 s
        self.assertEqual(len(vr.tempo_trams), 2)
        self.assertAlmostEqual(vr.tempo_trams[1][0], 12.0, places=6)
        self.assertEqual(len(vr.seccions), 2)
        self.assertAlmostEqual(vr.seccions[1][0], 12.0, places=6)
        # MOURE la frontera arrossega el marcador (dins del mateix desfer)
        vr._on_tempo_mogut(1, "ini", 13.0)
        self.assertAlmostEqual(vr.tempo_trams[1][0], 13.0, places=6)
        self.assertAlmostEqual(vr.marcadors[0], 13.0, places=6)
        vr.undo()
        self.assertAlmostEqual(vr.marcadors[0], 12.0, places=6)
        # ELIMINAR la frontera s'endú el marcador associat
        self.assertTrue(vr._elimina_tram(1))
        self.assertEqual(len(vr.tempo_trams), 1)
        self.assertEqual(len(vr.marcadors), 0, "la frontera se l'ha endut")
        # es desfà tot (mapa, marcador i clau) en un sol pas
        vr.undo()
        self.assertEqual(len(vr.marcadors), 1)
        self.assertEqual(len(vr.tempo_trams), 2)

    def test_fusionar_una_frontera_amb_marcador_esborra_el_marcador(self):
        """§4.C: la frontera que desapareix s'endú el seu marcador (i es desfà)."""
        vr = self.w.visor_ref
        vr.tempo_trams = [(0.0, 30.0, 120.0, 4, 4),
                          (30.0, 60.0, 120.0, 4, 4)]
        vr.marcadors = [30.0]
        vr._undo_touch_base()          # estat de partida consolidat
        self.assertTrue(vr._fusiona_tram(0, "seguent"))
        self.assertEqual(len(vr.tempo_trams), 1)
        self.assertEqual(vr.marcadors, [])
        vr.undo()
        self.assertEqual(len(vr.tempo_trams), 2)
        self.assertEqual(len(vr.marcadors), 1)
        self.assertAlmostEqual(vr.marcadors[0], 30.0, places=6)

    def test_tecla_mes_crea_marcador_a_la_finestra(self):
        """`+` és un atall de finestra (no depén del focus) que crida l'acció."""
        vr = self.w.visor_ref
        vr.pos = 20.0
        self.assertTrue(self.w._afegeix_marcador())     # acció de l'atall
        self.assertEqual(len(vr.marcadors), 1)
        self.assertFalse(self.w._afegeix_marcador())    # mateix punt: rebot
        vr.pos = 30.0
        self.assertTrue(self.w._afegeix_marcador())
        self.assertEqual(len(vr.marcadors), 2)
        # i s'esborra l'últim des del menú
        self.assertTrue(self.w._esborra_ultim_marcador())
        self.assertEqual(len(vr.marcadors), 1)

    def test_escriure_un_plus_en_un_camp_no_crea_marcador(self):
        """Escriure «+» al nom d'un acord no ha d'afegir cap marcador."""
        from PyQt5.QtTest import QTest
        vr = self.w.visor_ref
        vr.pos = 15.0
        vr.ed_nom.setEnabled(True)      # (amb un clip seleccionat ho està)
        vr.ed_nom.setFocus()
        QTest.keyClick(vr.ed_nom, Qt.Key_Plus)
        QTest.keyClick(vr.ed_nom, Qt.Key_Equal, Qt.ShiftModifier)
        self.assertEqual(len(vr.marcadors), 0)
        self.assertIn("+", vr.ed_nom.text())     # el «+» s'ha escrit

    def test_bpm_dels_marcadors_deixa_els_clips_editables(self):
        """El flux real: marcadors → BPM dels marcadors → clips editables."""
        from app import tempo_map as TM
        vr = self.w.visor_ref
        # tema a 96 BPM 4/4 (compàs 2,5 s), marcadors a 4/8/16 compassos
        t, ks = 8.1, (4, 4, 8, 4)          # 8.1, 18.1, 28.1, 48.1 (< 60 s)
        for k in ks:
            vr.pos = t
            self.assertTrue(vr.afegeix_marcador())
            t += k * 2.5
        self.assertEqual(len(vr.marcadors), len(ks))
        cands = vr.candidats_bpm_marcadors(120.0, 4, 4)
        triat = next(c for c in cands if abs(c["bpm"] - 96.0) < 0.2)
        self.assertTrue(vr.aplica_bpm_marcadors(triat, 4, 4))
        self.assertAlmostEqual(vr.bpm, 96.0, places=2)
        self.assertAlmostEqual(vr.offset, 8.1, places=3)
        # el mapa complix el contracte de compassos enters...
        TM.valida_i_normalitza_compassos(vr.tempo_trams, 60.0, vr.offset)
        # ...i per tant els clips es poden editar i suprimir
        self.assertTrue(vr.edita_tempo_objectiu(1, 97.0, 4, 4))
        self.assertTrue(vr._elimina_tram(1))
        # tot és un sol desfer per operació
        vr.undo()
        self.assertEqual(len(vr.tempo_trams), len(ks) + 1)

    def test_edita_tempo_objectiu_no_arrossega_els_trams(self):
        """Diàleg/transport = re-tempo local (§7): només es mou la frontera."""
        vr = self.w.visor_ref
        trams = [(0.0, 10.0, 120.0, 4, 4), (10.0, 30.0, 90.0, 3, 4),
                 (30.0, 60.0, 120.0, 4, 4)]
        self.assertTrue(vr.aplica_tempo_trams(trams))
        self.assertTrue(vr.edita_tempo_objectiu(1, 100.0, 3, 4))
        self.assertEqual(len(vr.tempo_trams), 3)
        self.assertEqual(vr.tempo_trams[0], trams[0])       # intacte
        self.assertAlmostEqual(vr.tempo_trams[1][2], 100.0, places=6)
        self.assertAlmostEqual(vr.tempo_trams[1][1], 28.0, places=6)
        # El veí de la dreta (últim) conserva el BPM i el seu final.
        self.assertAlmostEqual(vr.tempo_trams[2][0], 28.0, places=6)
        self.assertAlmostEqual(vr.tempo_trams[2][1], 60.0, places=6)
        self.assertAlmostEqual(vr.tempo_trams[2][2], 120.0, places=6)

    def test_el_marcador_arrossega_la_frontera_d_estructura(self):
        """El clip de secció que va crear el `+` seguix el marcador (§4.C)."""
        vr = self.w.visor_ref
        vr.seccions = [(0.0, 10.0, "A", "A"), (10.0, 20.0, "B", "B"),
                       (20.0, 60.0, "A", "A")]
        vr.marcadors = [10.0]
        vr.timeline.set_data(vr.acords, vr.seccions)
        self.assertTrue(vr._mou_marcador(10.0, 12.0))
        self.assertAlmostEqual(float(vr.marcadors[0]), 12.0, places=6)
        self.assertAlmostEqual(float(vr.seccions[0][1]), 12.0, places=6)
        self.assertAlmostEqual(float(vr.seccions[1][0]), 12.0, places=6)
        self.assertEqual(vr.seccions[0][2:], ("A", "A"))
        self.assertEqual(vr.seccions[1][2:], ("B", "B"))

    def test_el_marcador_no_buida_una_seccio_que_no_hi_cap(self):
        """Si la secció no pot seguir el marcador, no es toca (no queda buida)."""
        vr = self.w.visor_ref
        vr.seccions = [(0.0, 10.0, "A", "A"), (10.0, 10.5, "B", "B"),
                       (10.5, 60.0, "C", "C")]
        vr.marcadors = [10.0]
        vr.timeline.set_data(vr.acords, vr.seccions)
        before = list(vr.seccions)
        self.assertTrue(vr._mou_marcador(10.0, 10.6))
        self.assertAlmostEqual(float(vr.marcadors[0]), 10.6, places=6)
        self.assertEqual(vr.seccions, before)

    def test_frontera_de_tempo_arrossega_marcador_i_estructura(self):
        """El gest complet: frontera → marcador → inici del clip de secció."""
        vr = self.w.visor_ref
        trams = [(0.0, 16.0, 120.0, 4, 4), (16.0, 32.0, 120.0, 4, 4),
                 (32.0, 60.0, 120.0, 4, 4)]
        self.assertTrue(vr.aplica_tempo_trams(trams))
        vr.seccions = [(0.0, 16.0, "A", "A"), (16.0, 32.0, "B", "B"),
                       (32.0, 60.0, "A", "A")]
        vr.marcadors = [16.0]
        vr.timeline.set_data(vr.acords, vr.seccions)
        vr._on_tempo_mogut(0, "fi", 18.0)
        self.assertAlmostEqual(float(vr.tempo_trams[1][0]), 18.0, places=6)
        self.assertAlmostEqual(float(vr.marcadors[0]), 18.0, places=6)
        self.assertAlmostEqual(float(vr.seccions[0][1]), 18.0, places=6)
        self.assertAlmostEqual(float(vr.seccions[1][0]), 18.0, places=6)

    def test_marcador_durant_el_play_usa_el_cursor_del_so(self):
        """El cas real: donar-li a `+` mentre SONA (el cursor és el playhead)."""
        from PyQt5.QtTest import QTest
        vr = self.w.visor_ref
        with patch.object(audio_out, "crea_motor", lambda *a, **k: _MotorMut()):
            vr.play_stop()
            QTest.qWait(400)
            pos = float(vr.pos)
            self.assertGreater(pos, 0.05)       # el cursor s'ha mogut
            self.assertTrue(self.w._afegeix_marcador())
            vr.play_stop()
        self.assertAlmostEqual(vr.marcadors[0], pos, places=1)

    def test_marcador_no_talla_dues_vegades_el_mateix_punt(self):
        vr = self.w.visor_ref
        vr.pos = 10.0
        self.assertTrue(vr.afegeix_marcador())
        self.assertFalse(vr.afegeix_marcador())     # mateix instant
        vr.pos = 0.0
        self.assertFalse(vr.afegeix_marcador())     # no es pot a l'inici

    def test_analitzar_nomes_acords_omet_l_estructura(self):
        """F6 / «Només els acords»: no passa el qm-segmenter ni toca l'ABC."""
        from app import main as app_main
        w = self.w
        w.amb_est.setChecked(True)
        w.opcions["analisi"] = {"estructura": True}
        vist = {}

        def _extreu_chords(wav, csv, log, params=None):
            open(csv, "w", encoding="utf-8").write("0.0,1.0,N\n")
            vist["chords"] = True

        def _extreu_segments(*a, **k):
            vist["segments"] = True

        with patch.object(app_main.pipeline, "extract_chords",
                          _extreu_chords), \
                patch.object(app_main.pipeline, "extract_segments",
                             _extreu_segments), \
                patch.object(app_main.pipeline, "wav_info",
                             lambda p: {"durada": 60.0}):
            fil = app_main.Feina(w.wav_edit.text().strip(), self.td, 120.0, 4,
                                 0.0, False, opcions={}, amb_bpm=False)
            fil.run()
        self.assertTrue(vist.get("chords"))
        self.assertNotIn("segments", vist)
        self.assertTrue(os.path.exists(os.path.join(self.td, "acords.csv")))
        self.assertFalse(os.path.exists(
            os.path.join(self.td, "estructura_ABC.csv")))

    # -- velocitat de reproducció (0,5–3×, to mantingut) ------------------
    def test_velocitat_1x_es_el_buffer_de_sempre(self):
        """A 1× no es renderitza res: es fa servir el PCM del visor."""
        vr = self.w.visor_ref
        self.assertEqual(vr._mono_a(1.0), vr._mono_bytes())

    def test_selector_de_velocitat_sincronitzat(self):
        """`_sincronitza_selector_velocitat` no ha de disparar el canvi."""
        vr = self.w.visor_ref
        try:
            vr.velocitat = 1.5
            vr._sincronitza_selector_velocitat()
            self.assertEqual(vr.cmb_vel.currentData(), 1.5)
            self.assertEqual(self.w.cmb_vel_tb.currentData(), 1.0)
        finally:
            vr.velocitat = 1.0
            vr._sincronitza_selector_velocitat()

    def test_velocitat_canviada_sincronitza_la_barra(self):
        vr = self.w.visor_ref
        try:
            vr.velocitatCanviada.emit(2.0)
            self.assertEqual(self.w.cmb_vel_tb.currentData(), 2.0)
        finally:
            vr.velocitatCanviada.emit(1.0)
        self.assertEqual(self.w.cmb_vel_tb.currentData(), 1.0)

    def test_cursor_a_doble_velocitat_avanca_el_doble(self):
        """El rellotge del cursor va en temps de cançó (× velocitat)."""
        import time as _t
        vr = self.w.visor_ref
        try:
            vr.velocitat = 2.0
            vr.loop_on = False
            vr.t0_pos = 0.0
            vr.t0_mono = _t.monotonic() - 1.0
            vr._tiquet()
            self.assertAlmostEqual(vr.pos, 2.0, delta=0.15)
        finally:
            vr.velocitat = 1.0

    @unittest.skipUnless(app_visor.ffmpeg.disponible(),
                         "cal ffmpeg per canviar la velocitat")
    def test_selector_de_la_barra_mou_el_visor(self):
        """El desplegable del transport (finestra) arriba al visor."""
        vr = self.w.visor_ref
        try:
            self.w.cmb_vel_tb.setCurrentIndex(3)          # 1,25×
            self.assertEqual(vr.velocitat, 1.25)
            self.assertEqual(vr.cmb_vel.currentData(), 1.25)
        finally:
            self.w.cmb_vel_tb.setCurrentIndex(2)          # torna a 1×
        self.assertEqual(vr.velocitat, 1.0)
        vr._neteja_velocitat()

    def test_velocitat_sense_ffmpeg_no_canvia_res(self):
        """Si no hi ha ffmpeg, s'avisa i la velocitat es queda com estava."""
        from app import visor as V
        vr = self.w.visor_ref
        with patch.object(V.ffmpeg, "disponible", lambda: False):
            vr.set_velocitat(2.0, avisar=False)
        self.assertEqual(vr.velocitat, 1.0)
        self.assertEqual(vr.cmb_vel.currentData(), 1.0)

    def test_neteja_velocitat_va_a_la_paperera(self):
        """Els temporals d'`atempo` s'esborren per la paperera (mai `rm`)."""
        from app import plataforma
        from app import visor as V
        vr = self.w.visor_ref
        tmp = os.path.join(self.td, "vel_prova.wav")
        open(tmp, "wb").close()
        cridats = []
        try:
            vr._vel_temporals = [tmp]
            vr._vel_cache = {2.0: b"x"}
            with patch.object(V.plataforma, "a_la_paperera",
                              lambda r: cridats.append(r) or True):
                vr._neteja_velocitat()
            self.assertEqual(cridats, [tmp])
            self.assertEqual(vr._vel_temporals, [])
            self.assertEqual(vr._vel_cache, {})
        finally:
            plataforma.a_la_paperera(tmp)

    def test_les_tres_etapes_al_dialeg(self):
        """BPM · acords · estructura: una casella independent per pestanya."""
        from app import dialegs as D
        d = D.DialegOpcions(None, "acords",
                            {"analisi": {"bpm": False, "acords": True,
                                         "estructura": False},
                             "guiat": {"compassos": 8}})
        self.assertFalse(d._cb_bpm.isChecked())
        self.assertTrue(d._cb_acords.isChecked())
        self.assertFalse(d._cb_estructura.isChecked())
        o = d.opcions()
        self.assertEqual(o["analisi"], {"bpm": False, "acords": True,
                                        "estructura": False})
        self.assertEqual(o["guiat"], {"compassos": 8})   # es conserva
        d._cb_bpm.setChecked(True)
        d._cb_estructura.setChecked(True)
        self.assertEqual(d.opcions()["analisi"],
                         {"bpm": True, "acords": True, "estructura": True})

    def test_analitza_tambe_detecta_el_bpm(self):
        """«Analitza» amb l'etapa BPM activa: detecta i aplica el tempo."""
        from app import main as app_main
        w = self.w
        vist = {}

        def _detecta(*a, **k):
            vist["bpm"] = True
            return 101.0

        def _extreu_chords(wav, csv, log, params=None):
            open(csv, "w", encoding="utf-8").write("0.0,1.0,N\n")

        def _abc(*a, **k):
            open(os.path.join(self.td, "estructura_ABC.csv"), "w",
                 encoding="utf-8").write("0.0,60.0,60.0,A,A,1,1\n")

        with patch.object(app_main.pipeline, "detecta_bpm", _detecta), \
                patch.object(app_main.pipeline, "extract_chords",
                             _extreu_chords), \
                patch.object(app_main.pipeline, "extract_segments",
                             lambda *a, **k: None), \
                patch.object(app_main.pipeline, "fer_abc", _abc), \
                patch.object(app_main.pipeline, "wav_info",
                             lambda p: {"durada": 60.0}):
            fil = app_main.Feina(w.wav_edit.text().strip(), self.td, 120.0, 4,
                                 0.0, True, opcions={})
            fil.run()
        self.assertTrue(vist.get("bpm"))
        self.assertEqual(fil.bpm_detectat, 101.0)
        self.assertEqual(fil.bpm, 101.0)     # el BPM detectat mana al pipeline

    def test_etapa_acords_desactivada_no_toca_el_csv(self):
        """Amb l'etapa d'acords OFF, el model d'acords es conserva intacte."""
        from app import main as app_main
        w = self.w
        csv_ac = os.path.join(self.td, "acords.csv")
        with open(csv_ac, "w", encoding="utf-8") as f:
            f.write("0.0,60.0,N\n")
        abans = open(csv_ac, encoding="utf-8").read()
        vist = {}

        with patch.object(app_main.pipeline, "detecta_bpm",
                          lambda *a, **k: 120.0), \
                patch.object(app_main.pipeline, "extract_chords",
                             lambda *a, **k: vist.setdefault("chords", True)), \
                patch.object(app_main.pipeline, "extract_segments",
                             lambda *a, **k: vist.setdefault("segments", True)), \
                patch.object(app_main.pipeline, "fer_abc",
                             lambda *a, **k: None), \
                patch.object(app_main.pipeline, "wav_info",
                             lambda p: {"durada": 60.0}):
            fil = app_main.Feina(w.wav_edit.text().strip(), self.td, 120.0, 4,
                                 0.0, True, opcions={}, amb_acords=False)
            fil.run()
        self.assertNotIn("chords", vist)
        self.assertIn("segments", vist)
        self.assertEqual(open(csv_ac, encoding="utf-8").read(), abans)

    def test_obre_el_dialeg_amb_les_dades(self):
        from app import dialeg_ancoratges as DA
        rebut = {}

        class _Dlg:
            Accepted = 1

            def __init__(self, parent, wav, durada, **kw):
                rebut.update(wav=wav, durada=durada, **kw)

            def exec_(self):
                return 0

            def opcions(self):
                return {"velocitat": 2.0}

        visor_sc = self.w.visor_ref._sc_play
        sc_play = self.w._sc_play
        vist = {}

        class _Dlg2(_Dlg):
            def exec_(self):
                # mentre el diàleg és obert, l'Espai NO pot arrancar el visor
                vist["main"] = sc_play.isEnabled()
                vist["visor"] = visor_sc.isEnabled()
                return 0

        with patch.object(DA, "DialegAncoratges", _Dlg2):
            self.w._analisi_ancoratges()
        self.assertFalse(vist["main"])
        self.assertFalse(vist["visor"])
        self.assertTrue(sc_play.isEnabled())        # i es torna a activar
        self.assertTrue(visor_sc.isEnabled())
        # `tria_wav` copia l'àudio dins del projecte: mana la ruta viva
        self.assertEqual(rebut["wav"], self.w.wav_edit.text().strip())
        self.assertAlmostEqual(rebut["durada"], 60.0, places=3)
        self.assertTrue(callable(rebut["aplicar"]))
        self.assertAlmostEqual(rebut["bpm_global"], 120.0, places=3)



if __name__ == "__main__":   # pragma: no cover
    unittest.main()
