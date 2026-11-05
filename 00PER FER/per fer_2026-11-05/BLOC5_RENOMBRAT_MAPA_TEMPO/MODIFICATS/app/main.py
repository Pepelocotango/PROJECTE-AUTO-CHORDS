#!/usr/bin/env python3
# main.py — Auto Chords (PyQt5/Qt5: l'únic Qt que corre al Q9400) —
#           wav -> acords + estructura -> carpetes. Tot en català.
import csv
import faulthandler
import json
import logging
import os
import shutil
import sys
import statistics
import tempfile
import time
import traceback

from PyQt5.QtCore import (QCoreApplication, QEvent, QThread, Qt, QTimer,
                          QUrl, pyqtSignal)
from PyQt5.QtGui import QCursor, QDesktopServices, QKeySequence
from PyQt5.QtWidgets import (
    QAction, QApplication, QButtonGroup, QCheckBox, QFileDialog, QDockWidget,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QComboBox,
    QInputDialog, QMessageBox, QProgressBar, QPushButton, QShortcut, QSlider,
    QDialog,
    QAbstractSpinBox,
    QPlainTextEdit,
    QTextEdit,
    QStackedWidget, QToolBar,
    QVBoxLayout, QWidget,
)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(APP_DIR)
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
# UN SOL objecte per mòdul (vegeu visor.py): els imports crus creaven objectes
# diferents dels que veuen la resta de mòduls i els tests.
from . import beats as beats_mod  # noqa: E402
from . import bpm_unit as bpm_unit_mod  # noqa: E402
from . import ffmpeg, partitura, pipeline, postproc, theme  # noqa: F401
from . import config  # noqa: E402
from . import dialeg_bpm_marcadors  # noqa: E402
from . import dialeg_guia_rapida  # noqa: E402
from . import dialegs  # noqa: E402
from . import exporta_audio as exporta_audio_mod  # noqa: E402
from . import icones  # noqa: E402
from . import panell_xifrat  # noqa: E402
from . import plataforma  # noqa: E402
from . import projecte  # noqa: E402
from . import tempo_map  # noqa: E402
from . import limits  # noqa: E402
from . import visor as visor_mod  # noqa: E402
from . import __version__  # noqa: E402  (versió mostrada al «Quant a»)

# Sempre a un directori ESCRIPTIBLE: en una AppImage muntada la carpeta del
# projecte és de només lectura i escriure-hi el log petava a l'arrencada.
DEFAULT_LOG_PATH = config.LOG_PATH

# Caixa d'informacio (a baix, a la dreta del log): quan el ratoli no es sobre
# res amb info, hi gira el rotatori de consells i dreceres. Cada quan canvia de
# «pantalla», i quanta estona es queda aturada després d'un clic a la caixa.
# 8 s per «pantalla»: les pantalles ara són CURTES (3-4 línies) i moltes, així
# que el cicle sencer es veu abans. (Abans: 8 s amb pantalles llarguíssimes →
# no es llegien; després 14 s → el cicle no s'acabava mai.)
_INFO_ROTACIO_S = 8.0
_INFO_PAUSA_S = 30.0        # clic a la caixa → el rotatori es para aquest temps

def _instal·la_captura_excepcions():
    """Registra al log qualsevol excepcio no gestionada (evita crashes muts)."""
    import traceback
    logger = logging.getLogger("auto_chords")

    def _hook(tipus, valor, tb):
        if issubclass(tipus, KeyboardInterrupt):
            sys.__excepthook__(tipus, valor, tb)
            return
        logger.error("EXCEPCIO NO GESTIONADA:\n%s",
                     "".join(traceback.format_exception(tipus, valor, tb)))
    sys.excepthook = _hook

def setup_logging(log_path=None):
    log_file = log_path or DEFAULT_LOG_PATH
    log_dir = os.path.dirname(log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger("auto_chords")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    _instal·la_captura_excepcions()

    logger.info("Auto Chords startup | log=%s", log_file)
    return logger

FOSC = theme.app_stylesheet()

# El fitxer del faulthandler ha de viure TOT el procés (faulthandler no el tanca
# ni en guarda cap referència: si el GC el tanqués, el crash no deixaria res).
_FH_FITXER = None

def activa_faulthandler(log_path, logger=None):
    """Deixa la traça dels crashes NADIUS (SIGSEGV / access violation) a disc.

    Un segfault de Qt/PortAudio mata el procés sense passar per `excepthook` ni
    pel log: sense això, un informe de beta és «s'ha tancat sol». Escriu a
    `crash_nadiu.log` (al costat del log de l'app). Cal un FITXER propi: en un
    `.exe` sense consola `sys.stderr` és `None` i `faulthandler.enable()` pelat
    petaria. Si l'execució anterior va deixar una traça, es desa com a
    `crash_nadiu.log.anterior` i s'avisa al log (en sortida normal el fitxer
    queda buit, així que no hi ha falsos positius). Retorna la ruta o `None`.
    """
    global _FH_FITXER
    ruta = os.path.join(os.path.dirname(os.path.abspath(log_path)),
                        "crash_nadiu.log")
    try:
        if os.path.isfile(ruta) and os.path.getsize(ruta) > 0:
            anterior = ruta + ".anterior"
            os.replace(ruta, anterior)
            if logger is not None:
                logger.warning("L'execució anterior va acabar amb un crash "
                               "nadiu; traça desada a %s", anterior)
        nou = open(ruta, "w", encoding="utf-8")
        faulthandler.enable(file=nou, all_threads=True)
    except (OSError, RuntimeError, ValueError) as e:
        if logger is not None:
            logger.warning("faulthandler no activat: %s", e)
        return None
    vell, _FH_FITXER = _FH_FITXER, nou
    if vell is not None:
        try:
            vell.close()
        except OSError:
            pass
    return ruta

class FeinaExporta(QThread):
    """Exporta el paquet de WAV's en un FIL (A5).

    L'export pot trigar (una WAV per acord/secció): fet al fil de la UI,
    congelava la finestra. Aquí el progrés arriba per senyal (segur entre
    fils) i la UI no es queda encallada.
    """
    missatge = pyqtSignal(str)
    progres = pyqtSignal(int)
    feta = pyqtSignal(bool, str)

    def __init__(self, kwargs):
        super().__init__()
        self._kwargs = kwargs

    def log(self, t):
        self.missatge.emit(t)

    def run(self):
        try:
            self.progres.emit(10)
            pipeline.exporta_total(log=self.log, **self._kwargs)
            self.progres.emit(100)
            self.feta.emit(True, "")
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR a l'exportar: {e}")
            self.feta.emit(False, str(e))

class FeinaExportaAudio(QThread):
    """Exporta la còpia WAV de treball a un altre format (Fase 6).

    Igual que `FeinaExporta`, el log s'emet per senyal: cridar la GUI des del
    fil seria UB. El resultat arriba amb `feta(ok, error, desti)`.
    """
    missatge = pyqtSignal(str)
    feta = pyqtSignal(bool, str, str)

    def __init__(self, origen, desti, perfil):
        super().__init__()
        self._origen = origen
        self._desti = desti
        self._perfil = perfil

    def log(self, t):
        self.missatge.emit(t)

    def run(self):
        try:
            exporta_audio_mod.exporta(self._origen, self._desti,
                                      self._perfil, log=self.log)
            self.feta.emit(True, "", self._desti)
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR a l'exportar àudio: {e}")
            self.feta.emit(False, str(e), "")

class FilTempoTrams(QThread):
    """«Detecta el tempo per trams» en un fil (no bloqueja la GUI).

    Segueix els temps de tota la cançó (DP d'Ellis) i en fa un mapa de BPM
    cada N compassos. Emet `{"trams", "offset", "bpm_base"}`.
    """
    feta = pyqtSignal(object)
    missatge = pyqtSignal(str)

    def __init__(self, wav, durada, num, den, cada, tol, bpm_min=None,
                 bpm_max=None, preferit=None, offset=None, parent=None):
        super().__init__(parent)
        self._wav = wav
        self._durada = float(durada)
        self._num = int(num)
        self._den = int(den)
        self._cada = int(cada)
        self._tol = float(tol)
        self._min = bpm_min
        self._max = bpm_max
        self._pref = preferit
        self._offset = offset

    def log(self, t):
        self.missatge.emit(str(t))

    def run(self):
        res = {"trams": [], "offset": 0.0, "bpm_base": None}
        try:
            trams, offset, base = pipeline.detecta_tempo_per_trams(
                self._wav, self.log, self._durada, num=self._num,
                den=self._den, cada_compassos=self._cada,
                tolerancia=self._tol, bpm_min=self._min, bpm_max=self._max,
                preferit=self._pref, offset=self._offset)
            res = {"trams": trams, "offset": float(offset or 0.0),
                   "bpm_base": base}
        except Exception as e:  # noqa: BLE001
            self.log(f"tempo per trams: ERROR ({e})")
        self.feta.emit(res)

class Feina(QThread):
    missatge = pyqtSignal(str)
    progres = pyqtSignal(int)
    feta = pyqtSignal(bool, str)

    def __init__(self, wav, sortida, bpm, bpb, offset, amb_estructura,
                 tempo_fix=True, opcions=None, amb_bpm=True, amb_acords=True):
        super().__init__()
        # CRU de l'anàlisi EN MEMÒRIA: es desa dins el `.acproj` en acabar
        # (decisió 2026-10-19: ni `analisi/` ni `segments.csv` al disc).
        self.raw_chords = []       # [(t, acord), …] tal com l'ha donat Chordino
        self.raw_segments = []     # [(ini, durada, idx, etiqueta), …]
        self.analisi = None
        self.wav = wav
        self.sortida = sortida
        self.bpm = bpm
        self.bpb = bpb
        self.offset = offset
        self.amb_estructura = amb_estructura
        self.tempo_fix = tempo_fix
        self.opcions = opcions or {}
        # QUÈ S'ANALITZA (3 etapes independents, decisió 21-10-2026): el que
        # està desactivat NO es toca — es conserva el model que ja hi ha.
        self.amb_bpm = bool(amb_bpm)
        self.amb_acords = bool(amb_acords)
        #: BPM detectat en esta passada (None = no s'ha detectat o no tocava)
        self.bpm_detectat = None

    def log(self, t):
        self.missatge.emit(t)

    def _detecta_bpm(self, durada_wav=None):
        """BPM del tema **sencer** amb les opcions del diàleg (motor + rang).

        Retorna el número o `None`. No toca res: qui l'aplica és la Finestra
        (camp del transport) en acabar el fil.
        """
        b = self.opcions.get("bpm") or {}
        try:
            return pipeline.detecta_bpm(
                self.wav, self.log,
                bpm_min=b.get("min"), bpm_max=b.get("max"),
                preferit=(b.get("pref_min"), b.get("pref_max")),
                motor=b.get("motor", "nostre"))
        except Exception as e:  # noqa: BLE001
            self.log(f"BPM: ERROR a la detecció ({e})")
            return None

    def run(self):
        """ANALITZA: les **3 etapes** (BPM · acords · estructura), cadascuna
        activable/desactivable a les Opcions. Les wavs es generen a l'EXPORTAR.

        Disseny (decisio de l'operador): les `wavs_acords/`/`wavs_estructura/`
        no tenen cap paper en la visualitzacio ni l'edicio; son l'ULTIM pas.
        Ací només s'escriuen els CSV del MODEL (`acords.csv`,
        `estructura_ABC.csv`); el CRU es queda en memòria i es desa dins el
        `.acproj`. La guia i les wavs les fa `pipeline.exporta_total`.

        El que està **desactivat no es toca**: es conserva el model actual (el
        BPM del transport, els acords o les seccions que ja hi ha).
        """
        passos = []
        if self.amb_bpm:
            passos.append("bpm")
        if self.amb_acords:
            passos.append("acords")
        if self.amb_estructura:
            passos.append("estructura")
        n = len(passos) or 1
        comptador = {"i": 0}

        def _pas(text):
            comptador["i"] += 1
            return f"{comptador['i']}/{n} {text}"

        try:
            os.makedirs(self.sortida, exist_ok=True)
            csv_ac = os.path.join(self.sortida, "acords.csv")
            # Durada de la WAV → invariant de cobertura dels clips (0 → durada).
            try:
                durada_wav = float(pipeline.wav_info(self.wav)["durada"])
            except Exception:  # noqa: BLE001
                durada_wav = None

            # ── 1) BPM (nou: «Analitza» també el detecta) ─────────────────
            if self.amb_bpm:
                self.log(_pas("detecta el BPM..."))
                self.bpm_detectat = self._detecta_bpm(durada_wav)
                if self.bpm_detectat:
                    self.bpm = float(self.bpm_detectat)
                    self.log(f"BPM detectat: {self.bpm:.3f} "
                             "(s'aplicarà al transport)")
                else:
                    self.log("BPM: la detecció no ha donat cap número; es "
                             "conserva el del transport")
            else:
                self.log("BPM: OMÈS (es conserva el del transport)")
            self.progres.emit(20)

            # ── 2) acords ─────────────────────────────────────────────────
            beat = (60.0 / float(self.bpm)) if self.bpm else 0.0
            if self.amb_acords:
                self.log(_pas("extreu acords (Chordino)..."))
                pipeline.extract_chords(
                    self.wav, csv_ac, self.log,
                    params=(self.opcions.get("chords") or None))
                # CRU en memòria: el resultat de Chordino ABANS de netejar-lo
                # (es desa al `.acproj` com a caché; l'edició no el toca).
                self.raw_chords = _llegeix_cru_acords(csv_ac)
                # Neteja posterior dels acords (opcions del dialeg).
                cl = self.opcions.get("clean") or {}
                if cl:
                    self.log("neteja dels acords...")
                    postproc.processa_acords_csv(
                        csv_ac,
                        # `durada_min` s'expressa en TEMPS → a segons amb el BPM
                        durada_min=float(cl.get("durada_min", 0.0)) * beat,
                        fusiona_iguals=bool(cl.get("fusiona_iguals", True)),
                        sense_baix=bool(cl.get("sense_baix", False)),
                        reduir=bool(cl.get("reduir", False)),
                        snap=bool(cl.get("snap", False)),
                        bpm=self.bpm, bpb=self.bpb, offset=self.offset,
                        divisio=int(cl.get("divisio", 1)), log=self.log,
                        durada=durada_wav)
            else:
                self.log("acords: OMESOS (es conserva el model actual)")
            self.progres.emit(55)

            # ── 3) estructura ─────────────────────────────────────────────
            if self.amb_estructura:
                self.log(_pas("extreu estructura (qm-segmenter)..."))
                tmpd = tempfile.mkdtemp(prefix="ac_qm_")
                try:
                    seg = os.path.join(tmpd, "seg.csv")
                    pipeline.extract_segments(
                        self.wav, seg, self.log,
                        motor=(self.opcions.get("structure") or {}).get(
                            "motor", "qm"))
                    self.raw_segments = _llegeix_cru_segments(seg)
                finally:
                    pipeline.esborra_tmp([tmpd])
                self.progres.emit(80)
                self.log(_pas("ABC (estructura)..."))
                abc = os.path.join(self.sortida, "estructura_ABC.csv")
                _est = self.opcions.get("structure") or {}
                compas = beat * max(1, int(self.bpb or 4))
                pipeline.fer_abc(self.raw_segments, abc, self.bpm, self.log,
                                 lliure=not self.tempo_fix, bpb=self.bpb,
                                 offset=self.offset,
                                 # `durada_min` s'expressa en COMPASSOS → a segons
                                 durada_min=float(_est.get("durada_min", 0.0)) * compas,
                                 fusiona_iguals=bool(_est.get("fusiona_iguals", True)),
                                 durada=durada_wav)
            else:
                self.log("estructura: OMESA (es conserva la que hi ha)")
            self.analisi = {
                "data": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "durada": durada_wav,
                "bpm": self.bpm, "bpb": self.bpb, "offset": self.offset,
                "tempo_fix": self.tempo_fix,
                "opcions": self.opcions,
                "chords": self.raw_chords,
                "segments": self.raw_segments,
            }
            self.log("Analisi feta. Les wavs es generaran en 'Exporta'.")
            self.progres.emit(100)
            self.feta.emit(True, self.sortida)
        except Exception as e:  # noqa: BLE001
            # Mateixa traça que `FeinaExporta`: un error d'analisi tambe ha de
            # quedar AL REGISTRE (abans s'avisava per `feta` i prou, i al log no
            # n'hi havia constancia — auditoria 18-10-2026).
            self.log(f"ERROR a l'analisi: {e}")
            self.feta.emit(False, str(e))

def _llegeix_cru_acords(ruta):
    """CSV del host -> `[(t, acord), …]` (el CRU que es guarda al projecte)."""
    out = []
    try:
        with open(ruta, encoding="utf-8") as f:
            for fila in csv.reader(f):
                if len(fila) < 2 or not fila[0] or fila[0].startswith("posici"):
                    continue
                try:
                    out.append([float(fila[0]), fila[1].strip()])
                except ValueError:
                    continue
    except OSError:
        return []
    return out

def _llegeix_cru_segments(ruta):
    """CSV del qm-segmenter -> `[(ini, durada, idx, etiqueta), …]`."""
    out = []
    try:
        with open(ruta, encoding="utf-8") as f:
            for fila in csv.reader(f):
                if len(fila) < 4:
                    continue
                try:
                    out.append([float(fila[0]), float(fila[1]),
                                int(float(fila[2])), fila[3].strip()])
                except (ValueError, IndexError):
                    continue
    except OSError:
        return []
    return out

class Finestra(QMainWindow):
    # Els `except Exception` d'aquesta classe protegeixen accions de l'usuari:
    # sempre registren l'error i/o mostren un diàleg, mai l'amaguen.
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("auto_chords")
        self.opcions = dialegs.carrega_opcions()    # ultimes opcions d'autodeteccio
        # PROJECTE (carpeta autocontinguda): el document viu + «canvis sense desar».
        self.projecte = None
        self.dirty = False
        self._fil_trams = None                      # FilTempoTrams en curs
        self._fil_exporta_audio = None              # FeinaExportaAudio en curs
        self.recents = self._carrega_recents()
        self._info_msg_fins = 0.0                  # missatge transitori info box
        # A5: export asíncron (progrés a la barra d'estat).
        self.exporta_error = ""
        self.exportant = False
        self.exporta_iniciat = 0.0
        self.feina_export = None
        self.setWindowTitle("Auto Chords")
        self.resize(1500, 900)
        # Amplada minima: per sota, les barres d\'eines es tallarien.
        self.setMinimumWidth(1240)
        self.feina = None
        self.logger.info("Finestra inicialitzada")

        # El VISOR és el widget central (abans era un QDockWidget a la dreta).
        # Fem servir un QStackedWidget: pàgina 0 = placeholder, pàgina 1 = visor.
        self.wav_edit = QLineEdit()      # només com a magatzem de la ruta
        self.wav_edit.setVisible(False)
        self.wav_info = QLabel("")
        self.statusBar().addPermanentWidget(self.wav_info)

        arrel = QWidget()
        self.setCentralWidget(arrel)
        capa = QVBoxLayout(arrel)
        capa.setContentsMargins(0, 0, 0, 0)
        self._stack = QStackedWidget()
        capa.addWidget(self._stack, stretch=1)
        self.visor_widget = None
        self._mostra_placeholder_visor()

        # botó «Obre» (l'afegirem a la barra única, en ordre de flux)
        b_obre = QPushButton("Obre àudio")
        b_obre.setObjectName("secundari")
        b_obre.setToolTip("Obre un àudio: WAV/MP3/FLAC/AIFF… (Ctrl+O)")
        b_obre.clicked.connect(self.tria_wav)

        # botó «Guia ràpida»: guia interactiva explicativa del flux de treball
        self.b_guia = QPushButton("Guia ràpida")
        self.b_guia.setObjectName("secundari")
        self.b_guia.setToolTip(
            "Guia interactiva explicativa del funcionament del flux DAW i marcadors en viu")
        self.b_guia.setEnabled(False)          # fins que hi hagi WAV
        self.b_guia.clicked.connect(self._obre_guia_rapida)
        self.b_marker = QPushButton("＋ Secció")
        self.b_marker.setObjectName("secundari")
        self.b_marker.setToolTip(
            "Marca un compàs i una secció en el punt del cursor (tecla +).")
        self.b_marker.setEnabled(False)
        self.b_marker.clicked.connect(lambda: self._afegeix_marcador("seccio"))

        self.b_marker_compas = QPushButton("＋ Compàs")
        self.b_marker_compas.setObjectName("secundari")
        self.b_marker_compas.setToolTip(
            "Marca només un compàs en el punt del cursor (sense secció).")
        self.b_marker_compas.setEnabled(False)
        self.b_marker_compas.clicked.connect(lambda: self._afegeix_marcador("compas"))

        # 2. temps i paràmetres — BARRA compacta d'una sola línia (estil DAW)
        #    (abans era un QGroupBox «2 · Temps i paràmetres»)
        self.b_mode_bpm = QPushButton("BPM · compàs")
        self.b_mode_bpm.setCheckable(True)
        self.b_mode_bpm.setChecked(True)
        self.b_mode_bpm.setToolTip("Treballar amb BPM i compassos.")
        self.b_mode_lliure = QPushButton("hh:mm:ss")
        self.b_mode_lliure.setCheckable(True)
        self.b_mode_lliure.setToolTip(
            "Treballar amb temps real (hh:mm:ss, sense compassos): per a "
            "material lliure o rubato, on la graella musical no encaixa.")
        grp_mode = QButtonGroup(self)
        grp_mode.setExclusive(True)
        grp_mode.addButton(self.b_mode_bpm)
        grp_mode.addButton(self.b_mode_lliure)
        self.b_mode_bpm.clicked.connect(lambda: self._canvia_mode_temps(True))
        self.b_mode_lliure.clicked.connect(lambda: self._canvia_mode_temps(False))

        # camps d'entrada MANUAL de text (sense fletxes ▲▼)
        self.bpm = QLineEdit("120.000")
        self.bpm.setFixedWidth(70)
        self.bpm.setPlaceholderText("120.000")
        self.bpm.setToolTip("BPM del tema. Entrada manual (text).")
        self.cb_bpm_unit = QComboBox()
        for _clau, _et in bpm_unit_mod.opcions():
            self.cb_bpm_unit.addItem(_et, _clau)
        self.cb_bpm_unit.setCurrentIndex(0)
        self._bpm_unit_anterior = "negra"
        self.cb_bpm_unit.setFixedWidth(118)
        self.cb_bpm_unit.setSizeAdjustPolicy(
            QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.cb_bpm_unit.setMinimumContentsLength(10)
        self.cb_bpm_unit.setToolTip(
            "Unitat del BPM: negra (per defecte), negra amb punt, corxera o "
            "blanca. El model intern continua en negres/minut.")
        self.cb_bpm_unit.currentIndexChanged.connect(self._canvia_unitat_bpm)
        self.bpb = QLineEdit("4/4")
        self.bpb.setFixedWidth(60)
        self.bpb.setPlaceholderText("4/4")
        self.bpb.setToolTip("Compàs manual: 4/4, 3/4, 2/4, 1/4, 6/8, etc.")
        self.offset = QLineEdit("0.000")
        self.offset.setFixedWidth(60)
        self.offset.setPlaceholderText("0.000")
        self.offset.setToolTip("Offset del compàs 1, en segons.")
        # La GUI mostra 3 decimals, però el model pot tindre microsegons
        # (p. ex. 1.207438). Guardem el text exacte que hem pintat per no
        # arredonir l'offset quan es recarrega el visor o s'analitza.
        self._offset_ui_text = None
        self._offset_ui_exact = None
        self.b_detecta = QPushButton(" Detecta")
        self.b_detecta.setIcon(icones.ico("target"))
        self.b_detecta.setIconSize(icones.pm_mida(16))
        self.b_detecta.setObjectName("secundari")
        self.b_detecta.setToolTip("Detecta el BPM. Amb un tram de tempo seleccionat, analitza només eixe tram (el seu inici és el downbeat).")
        self.b_detecta.clicked.connect(lambda: self._detecta_bpm())
        for camp in (self.bpm, self.bpb, self.offset):
            camp.editingFinished.connect(self._aplica_parametres_temps)

        self._params_temps = QWidget()      # s'amaga sencer en mode Lliure
        hp = QHBoxLayout(self._params_temps)
        hp.setContentsMargins(0, 0, 0, 0)
        hp.setSpacing(6)
        hp.addWidget(QLabel("BPM:"))
        hp.addWidget(self.bpm)
        hp.addWidget(QLabel("Unitat:"))
        hp.addWidget(self.cb_bpm_unit)
        self.b_bpm_x2 = QPushButton("×2")
        self.b_bpm_div2 = QPushButton("÷2")
        for b, factor, tip in ((self.b_bpm_x2, 2.0, "Dobla el BPM (×2)"),
                               (self.b_bpm_div2, 0.5, "Meitat del BPM (÷2)")):
            b.setObjectName("secundari")
            b.setFixedWidth(46)
            b.setToolTip(tip + "  ·  útil quan la detecció agafa el doble/meitat")
            b.clicked.connect(lambda _=False, f=factor: self._dobla_bpm(f))
            hp.addWidget(b)
        hp.addWidget(self.b_detecta)
        self.b_tap = QPushButton("TAP")
        self.b_tap.setObjectName("secundari")
        self.b_tap.setToolTip("Tap tempo: marca el pols amb clics (o la tecla T). "
                              "2 s sense tocar = reinicia.")
        self.b_tap.clicked.connect(self._tap_tempo)
        hp.addWidget(self.b_tap)
        self.lb_desti_accions = QLabel("")
        self.lb_desti_accions.setObjectName("desti_accions")
        hp.addWidget(self.lb_desti_accions)
        hp.addWidget(QLabel("Compàs:"))
        hp.addWidget(self.bpb)
        self.chk_segons = QCheckBox("En segons")
        self.chk_segons.setToolTip(
            "El clip de tempo objectiu va en segons (rubato): sense compàs ni "
            "graella, dura el que diu l'àudio. A la partitura es pren a 100 BPM.")
        self.chk_segons.toggled.connect(self._segons_top_bar)
        hp.addWidget(self.chk_segons)
        hp.addWidget(QLabel("Offset:"))
        hp.addWidget(self.offset)                 # segons
        self.b_offset_cursor = QPushButton()
        self.b_offset_cursor.setIcon(icones.ico("map-pin"))
        self.b_offset_cursor.setObjectName("secundari")
        self.b_offset_cursor.setToolTip(
            "Compàs 1 al cursor: posa l'offset, TALLA el carril de tempo "
            "aquí i fa començar el clip de tempo en aquesta posició "
            "(es mostra en segons i en compàs.beat)")
        self.b_offset_cursor.clicked.connect(self._marca_compas_1)
        hp.addWidget(self.b_offset_cursor)
        self.b_compas_auto = QPushButton()
        self.b_compas_auto.setIcon(icones.ico("compass"))
        self.b_compas_auto.setObjectName("secundari")
        self.b_compas_auto.setToolTip(
            "Detecta el COMPÀS 1 automàticament (primer downbeat): posa "
            "l'offset on comença la música. Útil per a temes amb silenci inicial.")
        self.b_compas_auto.clicked.connect(lambda: self._detecta_compas1())
        hp.addWidget(self.b_compas_auto)
        hp.addWidget(QLabel("≈"))
        self.offset_cb = QLineEdit("1.1")         # el mateix, en compàs.beat
        self.offset_cb.setMaximumWidth(46)
        self.offset_cb.setPlaceholderText("1.1")
        self.offset_cb.setToolTip(
            "Posició del compàs 1 en compàs.beat (graella original, offset=0).\n"
            "Ex. 5.1 = el compàs 1 va on la graella diu 5.1")
        hp.addWidget(self.offset_cb)
        self.offset_cb.editingFinished.connect(self._offset_cb_canviat)

        # "Inclou estructura": abans era un QCheckBox a la barra d'eines; ara
        # es una ACCIO commutable al menu Analitza (la funcio es la mateixa).
        self.amb_est = QAction("Inclou estructura", self)
        self.amb_est.setCheckable(True)
        # Es recorda entre sessions (Opcions → «Només els acords»).
        self.amb_est.setChecked(bool((self.opcions.get("analisi") or {})
                                     .get("estructura", True)))
        self.amb_est.setToolTip("Genera la jerarquia de seccions i l’ABC de l’estructura del tema.")

        # "Inclou la partitura": accio commutable al menu Fitxer. Per defecte NO
        # (el render amb MuseScore pot trigar); es tolerant si falta MuseScore.
        self.amb_part = QAction("Inclou la partitura (xifrat)", self)
        self.amb_part.setCheckable(True)
        self.amb_part.setChecked(False)
        self.amb_part.setToolTip(
            "En exportar, genera també un lead sheet de xifrats. El MusicXML "
            "es genera SEMPRE (sense dependències). El PDF i el MSCZ NOMÉS es "
            "poden fer si tens MuseScore instal·lat (l'app no l'inclou). "
            "Només en mode BPM · compàs.")

        # estat `tempo_fix` (ocult): el visor i la resta de codi el consulten
        self.tempo_fix = QCheckBox()
        self.tempo_fix.setChecked(True)
        self.tempo_fix.setVisible(False)
        self.tempo_fix.toggled.connect(self._canvia_tempo)
        self.tempo_fix.toggled.connect(self._marca_dirty)

        # 3. «Analitza», «Exporta WAV's» i «Exporta partitura» són ACCIONS.
        self.b_exec = QPushButton("Analitza")
        self.b_exec.setObjectName("principal")
        self.b_exec.setToolTip("Extreu acords i estructura de la WAV (F5)")
        self.b_exec.clicked.connect(lambda: self.executa())
        self.b_exec.setEnabled(False)          # fins que hi hagi WAV
        self.b_export = QPushButton("Exporta WAV's")
        self.b_export.setToolTip("Exporta el paquet final de WAV's (Ctrl+E)")
        self.b_export.setEnabled(False)       # fins que hi hagi pistes
        self.b_export.clicked.connect(self.exporta)
        self.b_export_part = QPushButton("Exporta partitura")
        self.b_export_part.setToolTip(
            "Genera la partitura (xifrat). El MusicXML es genera SEMPRE; el "
            "PDF i el MSCZ NOMÉS si tens MuseScore instal·lat.\n"
            "Fes «Analitza» primer: mentre no hi hagi resultats el botó queda "
            "apagat (i un clic en un botó apagat no fa res).")
        self.b_export_part.setEnabled(False)  # fins que hi hagi resultats
        self.b_export_part.clicked.connect(self.exporta_partitura_ara)

        # 1a BARRA: en ORDRE DE FLUX de treball →
        #   1) Obre  ·  2) opcions de temps  ·  3) Analitza i Exporta (al final)
        barra = QToolBar("Treball")
        barra.setObjectName("barra_principal")
        barra.setMovable(False)
        barra.addWidget(b_obre)
        barra.addWidget(self.b_guia)
        barra.addWidget(self.b_marker)
        barra.addWidget(self.b_marker_compas)
        barra.addSeparator()
        barra.addWidget(self.b_mode_bpm)
        barra.addWidget(self.b_mode_lliure)
        # Accions d'anàlisi/exportació a la mateixa fila: abans tenien una
        # fila pròpia amb molt d'espai buit.
        barra.addSeparator()
        barra.addWidget(self.b_exec)
        barra.addWidget(self.b_export)
        barra.addWidget(self.b_export_part)
        self.b_obre_carpeta = QPushButton("Obre la carpeta de sortida")
        self.b_obre_carpeta.setObjectName("secundari")
        self.b_obre_carpeta.setToolTip(
            "Obre la carpeta on es desen els WAV's exportats")
        self.b_obre_carpeta.clicked.connect(self.obre_carpeta)
        barra.addWidget(self.b_obre_carpeta)
        self.b_desfer = QPushButton()
        self.b_desfer.setObjectName("secundari")
        self.b_desfer.setIcon(icones.ico("undo-2", 16))
        self.b_desfer.setIconSize(icones.pm_mida(16))
        self.b_desfer.setToolTip("Desfer  (Ctrl+Z)")
        self.b_desfer.clicked.connect(self._undo_visor)
        barra.addWidget(self.b_desfer)
        self.b_refer = QPushButton()
        self.b_refer.setObjectName("secundari")
        self.b_refer.setIcon(icones.ico("redo-2", 16))
        self.b_refer.setIconSize(icones.pm_mida(16))
        self.b_refer.setToolTip("Refer  (Ctrl+Y)")
        self.b_refer.clicked.connect(self._redo_visor)
        barra.addWidget(self.b_refer)
        # El bloc de paràmetres de temps viu en la seua pròpia fila: dins la
        # barra principal superava l'amplada de la finestra i QToolBar el
        # movia a l'overflow, on els QWidgetAction no es pinten (BPM/Unitat/
        # Compàs/TAP desapareixien visualment).
        self._params_temps.setFixedHeight(36)
        self._params_temps.setFixedWidth(self._params_temps.sizeHint().width())
        self.addToolBar(Qt.TopToolBarArea, barra)
        self.barra_principal = barra
        self.addToolBarBreak(Qt.TopToolBarArea)
        barra_temps = QToolBar("Temps")
        barra_temps.setObjectName("barra_temps")
        barra_temps.setMovable(False)
        barra_temps.addWidget(self._params_temps)
        self.addToolBar(Qt.TopToolBarArea, barra_temps)
        self.barra_temps = barra_temps

        # 1b. TERCERA FILA: edició de graella (Snap, Beats QM, eina).
        barra_accions = QToolBar("Edició")
        barra_accions.setObjectName("barra_accions")
        barra_accions.setMovable(False)
        self.addToolBarBreak(Qt.TopToolBarArea)
        self.addToolBar(Qt.TopToolBarArea, barra_accions)
        self.barra_accions = barra_accions

        # progrés → barra d'estat (permanent)
        self.barra = QProgressBar()
        self.barra.setMaximumWidth(180)
        self.barra.setTextVisible(False)
        self.statusBar().addPermanentWidget(self.barra)

        # log → tauler plegable a baix (tancat per defecte)
        self.log = QTextEdit()
        self.log.setObjectName("log")
        self.log.setReadOnly(True)
        # Caixa d'informacio «live»: a la dreta del log (1/4 de l'amplada).
        self.info_box = QTextEdit()
        self.info_box.setObjectName("info")
        self.info_box.setReadOnly(True)
        self.info_box.setMinimumWidth(220)
        self.info_box.setHtml(
            "<i>Passa el ratolí per sobre d'un botó, camp o opció i aquí "
            "veuràs què fa.</i>")
        _cont_log = QWidget()
        _hl = QHBoxLayout(_cont_log)
        _hl.setContentsMargins(0, 0, 0, 0)
        _hl.setSpacing(4)
        _hl.addWidget(self.log, stretch=3)
        _hl.addWidget(self.info_box, stretch=1)
        self.log_dock = QDockWidget("Log  ·  Informació", self)
        self.log_dock.setObjectName("dock_log")
        self.log_dock.setWidget(_cont_log)
        # Vigilant: cada 250 ms mira el widget sota el ratolí i mostra el seu
        # tooltip a la caixa d'informacio (com una ajuda «live»).
        self._info_timer = QTimer(self)
        self._info_timer.setInterval(250)
        self._info_timer.timeout.connect(self._actualitza_info_widget)
        self._info_timer.start()
        # Estat del rotatori de la caixa d'informacio: quan el ratoli no es
        # sobre res amb informacio, s'hi mostren els panells de consells i
        # dreceres (`_info_panells`), rotant cada `_INFO_ROTACIO_S`. Un CLIC a
        # la caixa el PARA (`_INFO_PAUSA_S`) i el clic següent avança de
        # «pantalla» (vegeu `_clic_info_box`).
        self._info_html_actual = None
        self._info_panell = 0
        self._info_panell_t = 0.0
        self._info_pausa_fins = 0.0
        # El clic dins la caixa (QTextEdit de nomes lectura) el capturem amb un
        # filtre d'esdeveniments → pausar/avançar el rotatori.
        self.info_box.installEventFilter(self)
        # ⚠️ Un QTextEdit és una QAbstractScrollArea: els clics els rep el seu
        # **viewport**, no el widget → cal filtrar-los tots dos. Sense això, la
        # caixa semblava no respondre a cap clic (reportat per l'operador).
        self.info_box.viewport().installEventFilter(self)
        self.info_box.setCursor(Qt.PointingHandCursor)
        self.log_dock.setVisible(True)      # sortida de l'anàlisi, visible
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)

        # 4b. PANELL «TIPUS D'ACORD» (esquerra, DESACOPLABLE): construeix un
        #     xifrat clicant (arrel + tipus + baix) i l'escriu a la casella
        #     «Nom» de l'editor. Clicar un tipus MAI aplica res: ho fa
        #     l'usuari amb «Aplica».
        self.panell_xifrat = panell_xifrat.PanellXifrat(self)
        self.dock_xifrat = QDockWidget("Tipus d'acord", self)
        self.dock_xifrat.setObjectName("dock_xifrat")
        self.dock_xifrat.setWidget(self.panell_xifrat)
        self.dock_xifrat.setMinimumWidth(250)
        self.panell_xifrat.tipusTriat.connect(self._posa_nom_editor)
        self.panell_xifrat.escoltarDemandat.connect(self._escolta_notes)
        self.panell_xifrat.avis.connect(
            lambda t: self.avisa_info("Tipus d'acord", t))
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_xifrat)

        # (L'inspector lateral s'ha retirat: les llistes tornen sota l'ona,
        #  dins el visor, que és on tenen l'espai natural.)

        # 5. BARRA DE TRANSPORT única (fora del visor). Reutilitza els
        #    mètodes del visor (play_stop, stop_inici, ves_a, marca_A/B,
        #    commuta_loop, zoom, zoom_tot, commuta_mut): no es reescriu res.
        barra_transport = QToolBar("Transport")
        barra_transport.setObjectName("barra_transport")
        barra_transport.setMovable(False)
        self._crea_transport(barra_transport)
        # Barra de TRANSPORT: una fila pròpia (fila 3).
        self.addToolBarBreak(Qt.TopToolBarArea)
        self.addToolBar(Qt.TopToolBarArea, barra_transport)
        self.barra_transport = barra_transport

        self.sortida = ""
        self.b_export.setEnabled(False)
        self.b_export_part.setEnabled(False)
        # Drecera: espai = play/pausa (a la finestra principal, perquè el
        # visor està incrustat i el seu propi QShortcut no s'activaria).
        self._sc_play = QShortcut(QKeySequence(Qt.Key_Space), self)
        self._sc_play.activated.connect(self._toggle_play)
        self._taps = []                       # instants dels taps (tap tempo)
        # Estat de la sessió de tap tempo: destí, undo obert i timer de
        # tancament (2 s sense tocar → una sola operació de desfer).
        self._tap_target = None
        self._tap_sessio_oberta = False
        self._tap_canviat = False
        self._actualitzant_temps = False
        self._tap_timer = QTimer(self)
        self._tap_timer.setSingleShot(True)
        self._tap_timer.setInterval(2000)
        self._tap_timer.timeout.connect(self._tanca_sessio_tap)
        self._sc_tap = QShortcut(QKeySequence(Qt.Key_T), self)
        # `E`: commuta l'EINA del timeline (intel·ligent ⇄ marc). És un TOGGLE:
        # cada pulsació canvia d'estat; per defecte sempre s'arrenca en
        # intel·ligent (no hi ha estat «off»).
        self._sc_eina = QShortcut(QKeySequence(Qt.Key_E), self)
        self._sc_eina.activated.connect(self._toggle_eina_tecla)
        self._sc_tap.activated.connect(self._tap_tempo)
        # `+` (de dalt i del teclat numèric) = **marcador** en viu, també
        # mentre sona. Va per un FILTRE d'esdeveniments (no un QShortcut):
        # així, si estas escrivint en un camp (nom d'acord, BPM…), el `+`
        # s'escriu normalment i NO afig cap marcador.
        QApplication.instance().installEventFilter(self)
        self._crea_menus()
        self._canvia_mode_temps(True)
        # Autocomprovació dels fitxers que l'app NECESSITA per analitzar
        # (els plugins Vamp; l'host és `vamp_host_local`).
        for p in pipeline.VAMP_DIRS:
            if not os.path.exists(p):
                self.registra(f"AVÍS: no trobo {p}")
        # A9: ffmpeg és imprescindible per OBRIR qualsevol format que no sigui
        # WAV PCM 16 bits (mp3, flac, m4a, ogg…). Si no hi és, l'obertura
        # fallaria tard i amb un error críptic → millor saber-ho d'entrada.
        if not ffmpeg.disponible():
            self.registra("AVÍS: no trobo ffmpeg — només podré obrir WAV PCM "
                          "16 bits (mp3/flac/m4a/ogg… no)")

    def showEvent(self, event):
        """Assegura que els paràmetres de temps es veuen en obrir la finestra.

        `QToolBar` pot deixar el QWidget intern ocult fins que la finestra ja
        és visible; si no es refresca ací, BPM/Unitat/Compàs/TAP desapareixen
        visualment fins que l'usuari canvia de mode.
        """
        super().showEvent(event)
        QTimer.singleShot(0, lambda: self._canvia_mode_temps(
            self.tempo_fix.isChecked()))

    def _filtre_audio(self):
        """Filtre del diàleg d'obertura (A9).

        Sense ffmpeg, oferir mp3/flac/m4a/ogg seria enganyós (fallarien en
        triar-los): en aquest cas el filtre només mostra WAV.
        """
        if ffmpeg.disponible():
            return ffmpeg.filtre()
        return "WAV PCM (*.wav);;Tots els fitxers (*)"

    def _missatge_info(self, text):
        """Missatge TRANSITORI a la caixa d'informacio (desfer/refer, avisos).

        Te un format propi (banner blau) per distingir-lo del **rotatori** de
        consells i dreceres, que es mostra quan no hi ha res a dir.
        """
        import time as _t
        cap = (f"<b style='color:{theme.BLAU_INFO}'>● Missatge</b> "
               f"<span style='color:{theme.MUTED}'>· torna al rotatori aviat"
               "</span>")
        self.info_box.setHtml(
            cap + f"<br><b style='color:{theme.BLAU_INFO}'>{text}</b>")
        self._info_html_actual = None   # força reescriure quan passi el temps
        self._info_msg_fins = _t.monotonic() + 4.0

    def _on_play_state(self, on):
        """Icona del boto de transport: ▶ aturat / ⏸ sonant."""
        if hasattr(self, "b_play_tb"):
            self.b_play_tb.setIcon(icones.ico("pause" if on else "play", 16))
            self.b_play_tb.setToolTip("Atura  (Espai)" if on
                                      else "Reprodueix  (Espai)")
        if not on and hasattr(self, "_tanca_sessio_tap"):
            # En aturar, la sessió de tap es tanca (una sola operació d'undo).
            self._tanca_sessio_tap()

    def _on_visor_seleccio(self, kind, idx):
        """La selecció del timeline ha canviat → camps BPM/compàs al dia."""
        self._tanca_sessio_tap()
        self._sincronitza_temps_del_visor()

    def _on_loop_state(self, on):
        """Sincronitza el botó 🔁 del transport amb l'estat REAL del loop.

        El loop es pot activar SENSE tocar el botó (arrossegant el regle per
        crear un rang A-B) → sense això el botó quedava desactivat mentre el
        play ja feia loop (incoherent). Cobreix també la neteja i el revert
        (si faltaven A/B).
        """
        if hasattr(self, "tb_loop"):
            self.tb_loop.setChecked(bool(on))

    def _toggle_play(self):
        """Espai → play/pausa del visor, si n'hi ha."""
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            vr.play_stop()

    # ---------------- BARRA DE MENUS + PROXIES CAP AL VISOR ----------------
    def _act(self, menu, text, shortcut, slot, checkable=False):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.setCheckable(checkable)
        a.triggered.connect(slot)
        menu.addAction(a)
        return a

    def _crea_menus(self):
        mb = self.menuBar()
        # --- Fitxer ---
        m = mb.addMenu("&Fitxer")
        self._act(m, "Obre àudio…", "Ctrl+O", self.tria_wav)
        self._act(m, "Obre projecte…", "", self._obre_projecte)
        self._act(m, "Obre recent…", "", self._obre_recent)
        m.addSeparator()
        self._act(m, "Desa", "Ctrl+S", self._desa_projecte)
        self._act(m, "Desa com…", "", self._desa_projecte_com)
        self._act(m, "Desa una còpia…", "", self._desa_copia)
        self._act(m, "Reverteix", "", self._reverteix)
        m.addSeparator()
        self._act(m, "Exporta WAV's…", "Ctrl+E", self.exporta)
        self.a_exporta_audio = self._act(
            m, "Exporta àudio…", "", self._exporta_audio_ui)
        self.a_exporta_audio.setStatusTip(
            "Exporta la còpia WAV de treball (ja editada) a WAV, MP3, FLAC, "
            "AAC/M4A, OGG o Opus.")
        self.a_exporta_audio.setEnabled(False)
        a_part = self._act(m, "Exporta la partitura…", "",
                           self.exporta_partitura_ara)
        a_part.setStatusTip("Genera la partitura (xifrat). El MusicXML sempre; "
                            "el PDF i el MSCZ NOMÉS si hi ha MuseScore instal·lat.")
        m.addAction(self.amb_part)      # Inclou la partitura (commutable)
        self._act(m, "Obre la carpeta de sortida", "", self.obre_carpeta)
        m.addSeparator()
        self._act(m, "Surt", "Ctrl+Q", self.close)
        # --- Edita ---
        m = mb.addMenu("&Edita")
        self._act(m, "Desfer", "Ctrl+Z", self._undo_visor)
        self._act(m, "Refer", "Ctrl+Y", self._redo_visor)
        self._act(m, "Refer (alternatiu)", "", self._redo_visor)
        m.addSeparator()
        self._act(m, "Retalla", "Ctrl+X", self._retalla_clips)
        self._act(m, "Copia", "Ctrl+C", self._copia_clips)
        self._act(m, "Enganxa", "Ctrl+V", self._enganxa_clips)
        m.addSeparator()
        self._act(m, "Afegeix acord…", "", self._afegeix_acord_ui)
        self._act(m, "Afegeix secció…", "", self._afegeix_seccio_ui)
        # A2 + regla d'or #11: en un model saturat (els clips cobreixen tota la
        # WAV) no hi ha forat per afegir-ne: cal PARTIR el clip que hi ha al
        # cursor — MATEIXA acció per a acord i secció.
        self._act(m, "Parteix l'acord al cursor…", "", self._parteix_acord_ui)
        self._act(m, "Parteix la secció al cursor…", "", self._parteix_seccio_ui)
        self._act(m, "Afegeix tram de tempo/compàs…", "",
                  self._afegeix_tram_ui)
        self._act(m, "Parteix el tram al cursor…", "", self._parteix_tram_ui)
        m.addSeparator()
        self._act(m, "Elimina element", "Del", self._elimina_element)
        self._act(m, "Duplica element", "Ctrl+D", self._duplica_element)
        self._act(m, "Reanomena element", "F2", self._renomena_element)
        self._act(m, "Troba i reemplaça…", "Ctrl+H", self._troba_i_reemplaca_ui)
        m.addSeparator()
        self._act(m, "Paràmetres…", "", self._focus_parametres)
        # --- Selecciona ---
        m = mb.addMenu("&Selecciona")
        self._act(m, "Selecciona l'acord del cursor", "", self._sel_acord_cursor)
        self._act(m, "Selecciona la secció del cursor", "", self._sel_seccio_cursor)
        self._act(m, "Selecciona el tram de tempo/compàs del cursor", "",
                  self._sel_tram_cursor)
        m.addSeparator()
        self._act(m, "Loop a la selecció", "L", self._loop_seleccio)
        self._act(m, "Marca inici de loop (A)", "Ctrl+[", self._marca_A_visor)
        self._act(m, "Marca fi de loop (B)", "Ctrl+]", self._marca_B_visor)
        self._act(m, "Neteja el loop", "", self._neteja_loop)
        self._act(m, "Activa/desactiva loop", "", self._loop_visor)
        m.addSeparator()
        # Eina del timeline i abast del rang (vegeu `timeline.set_tool`,
        # `keys_dins_marc` i `extend_selection`).
        self.a_eina_marc = self._act(
            m, "Eina de marc (rubber-band)", "", self._toggle_eina_marc,
            checkable=True)
        self.a_eina_marc.setToolTip(
            "Arrossegar pel timeline dibuixa un rectangle: queda seleccionat "
            "tot el que hi SONA a dins, i només de les pistes que cobreixi. "
            "El rectangle desapareix en deixar anar.")
        # (No hi ha opció de «selecció creuada»: el rang de Shift+clic és sempre
        # del carril clicat, i per agafar clips de les dues pistes es fa servir
        # el marquee — Ctrl+arrossega o l'eina «marc».)
        # --- Visualitza ---
        m = mb.addMenu("&Visualitza")
        self._act(m, "Zoom +", "Ctrl++", lambda: self._zoom_visor(0.5))
        self._act(m, "Zoom −", "Ctrl+-", lambda: self._zoom_visor(2.0))
        self._act(m, "Zoom total", "Ctrl+0", self._zoom_tot_visor)
        m.addSeparator()
        # (El visor és ara el widget central: ja no cal «Mostra el visor»)
        m.addAction(self.log_dock.toggleViewAction())
        self.log_dock.toggleViewAction().setText("Mostra el log")
        m.addAction(self.dock_xifrat.toggleViewAction())
        self.dock_xifrat.toggleViewAction().setText("Mostra els tipus d'acord")
        m.addSeparator()
        self.a_metro = self._act(m, "Metrònom", "", self._toggle_metro, checkable=True)
        self.a_metro.setToolTip("Clic de metrònom (només en mode BPM · compàs)")
        # --- Analitza ---
        m = mb.addMenu("&Analitza")
        self._act(m, "Analitza l'àudio (acords + estructura)", "F5",
                  lambda: self.executa())
        self._act(m, "Analitza només els acords…", "F6",
                  lambda: self.executa(nomes_acords=True))
        self._act(m, "Analitza BPM…", "F7", self._analitza_bpm)
        self._act(m, "Ajusta la graella als beats QM…", "",
                  self._ajusta_graella_beats)
        self._act(m, "Compàs del marcador…", "",
                  self._compas_del_marcador)
        m.addSeparator()
        self._act(m, "Detecta el compàs 1 automàticament", None,
                    lambda: self._detecta_compas1())
        self._act(m, "Marca el compàs 1 aquí", "", self._marca_compas_1)
        self._act(m, "Quantitza el model…", "", self._quantitza_ui)
        self._act(m, "Quantitza BPM a 1 decimal", "",
                  self._quantitza_bpm_ui)
        self._act(m, "Mapa de tempo i compàs…", "",
                  self._tempo_mapa_ui)
        self._act(m, "Marca el rang A–B com a rubato", "",
                  self._marca_rubato_rang)
        self._act(m, "Converteix el tram de tempo a rubato", "",
                  self._converteix_rubato_ui)
        self._act(m, "Converteix el rubato a normal", "",
                  self._converteix_normal_ui)
        self._act(m, "Detecta el tempo per trams…", "",
                  self._detecta_tempo_per_trams)
        self._act(m, "Detecta el mapa de tempo (per beats)…", "",
                  self._detecta_tempo_mapa)
        m.addSeparator()
        self._act(m, "Afegeix un marcador (inici de compàs)", "+",
                  self._afegeix_marcador)
        self._act(m, "Esborra l'últim marcador", "",
                  self._esborra_ultim_marcador)
        self._act(m, "BPM a partir dels marcadors…", "",
                  self._bpm_dels_marcadors)
        self._act(m, "Ajusta BPMs a partir dels marcadors per trams", "",
                  self._ajusta_bpms_marcadors)
        self._act(m, "Ajusta un BPM (mínims quadrats) a partir dels marcadors",
                  "", self._ajusta_bpm_minims_quadrats)
        m.addSeparator()
        m.addAction(self.amb_est)      # Inclou estructura (commutable)
        # --- Ajuda ---
        m = mb.addMenu("A&juda")
        self._act(m, "Dreceres de teclat", "", self._mostra_dreceres)
        self._act(m, "Obre la carpeta del registre", "",
                  self.obre_carpeta_registre)
        self._act(m, "Quant a Auto Chords", "", self._quant_a)

    def obre_carpeta_registre(self):
        """Obre la carpeta on viu el log de l'app (per reportar errors de beta)."""
        d = os.path.dirname(config.LOG_PATH) or "."
        if os.path.isdir(d):
            QDesktopServices.openUrl(QUrl.fromLocalFile(d))
        else:
            self.avisa_info("Auto Chords", f"No trobo la carpeta del registre:\n{d}")

    def _sincronitza_temps_del_visor(self):
        """Refresca els camps de temps/loop des del visor.

        El BPM i el compàs mostren el **clip de tempo seleccionat** (2B); si no
        n'hi ha cap, el transport (tram 0). L'offset és global. Només reescriu
        el text si el valor difereix, per no reformatejar el que l'usuari hi ha
        escrit.
        """
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return
        unit = bpm_unit_mod.normalitza(getattr(vr, "bpm_unit", "negra"))
        if self._bpm_unit_val() != unit:
            idx_unit = self.cb_bpm_unit.findData(unit)
            if idx_unit >= 0:
                self.cb_bpm_unit.blockSignals(True)
                self.cb_bpm_unit.setCurrentIndex(idx_unit)
                self.cb_bpm_unit.blockSignals(False)
                self._bpm_unit_anterior = unit
        try:
            _idx, bpm, num, den = vr.tempo_objectiu_vals()
        except Exception:  # noqa: BLE001
            bpm, num, den = getattr(vr, "bpm", None), getattr(vr, "bpb", None), \
                getattr(vr, "beat_type", None)
        compas = None
        if num is not None:
            compas = (str(int(num)) if (den is None or int(den) == 4)
                      else f"{int(num)}/{int(den)}")

        self._actualitzant_temps = True
        try:
            for camp, valor, text in (
                    (self.bpm, bpm,
                     None if bpm is None else
                     bpm_unit_mod.formata(float(bpm), vr.bpm_unit)),
                    (self.bpb, num, compas),
                    (self.offset, getattr(vr, "offset", None),
                     None if getattr(vr, "offset", None) is None
                     else f"{float(vr.offset):.3f}")):
                if valor is None or text is None:
                    continue
                if camp.text().strip() == text:
                    continue
                try:
                    if abs(float(camp.text().replace(",", "."))
                           - float(valor)) <= 1e-9:
                        continue
                except (TypeError, ValueError):
                    pass
                camp.setText(text)
            # Recorda el text exacte pintat per a l'offset. Així `_offset_val`
            # pot retornar el valor intern (1.207438) encara que la GUI mostre
            # 3 decimals (1.207), sense arredonir-lo en recarregar/analitzar.
            off_exact = getattr(vr, "offset", None)
            if off_exact is not None:
                self._offset_ui_text = f"{float(off_exact):.3f}"
                self._offset_ui_exact = float(off_exact)
            try:
                self.chk_segons.setChecked(num is not None and int(num) <= 0)
            except (TypeError, ValueError):
                pass
            try:
                self.offset_cb.setText(
                    self._secs_a_cb(float(getattr(vr, "offset", 0.0))))
            except (TypeError, ValueError, AttributeError):
                pass
        finally:
            self._actualitzant_temps = False
        self._on_loop_state(getattr(vr, "loop_on", False))
        self._actualitza_desti_accions()
        self._actualitza_metro_ui()

    def _quantitza_bpm_ui(self):
        """Quantitza només els clips normals de BPM a 1 decimal."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.avisa_info("Quantitza BPM", "Obre un projecte primer.")
            return False
        if not getattr(vr, "tempo_fix", False):
            self.avisa_info("Quantitza BPM",
                            "Cal el mode BPM · compàs.")
            return False
        ok = bool(vr.quantitza_bpm(1))
        if ok:
            self._sincronitza_temps_del_visor()
            self._missatge_info(
                "BPM quantitzat a 1 decimal; els rubatos no s'han "
                "quantitzat i les fronteres s'han reencaixat.")
        else:
            self._missatge_info("Quantitza BPM: sense canvis.")
        return ok

    def _actualitza_desti_accions(self):
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return
        try:
            # Detecta: prioritat A-B, tram seleccionat, tema sencer.
            loop = None
            try:
                loop = self._loop_actiu()
            except Exception:  # noqa: BLE001
                loop = None
            if loop is not None:
                desti_detecta = "Detecta: selecció A–B"
            else:
                kind, idx = vr.seleccio_activa()
                if kind == "tempo":
                    desti_detecta = f"Detecta: tram {idx}"
                else:
                    desti_detecta = "Detecta: tema sencer"
            # TAP: només amb un tram de tempo seleccionat (2026-11-01).
            kind, idx = vr.seleccio_activa()
            if kind == "tempo" and vr._index_valid("tempo", idx):
                desti_tap = f"TAP: tram {idx}"
            else:
                desti_tap = "TAP: tria un tram de tempo"
            self.lb_desti_accions.setText(
                f"{desti_detecta} · {desti_tap}")
        except Exception:  # noqa: BLE001
            pass

    def _undo_visor(self):
        self._tanca_sessio_tap()
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            vr.undo()
            self._sincronitza_temps_del_visor()
        else:
            self.registra("Edita: no hi ha visor carregat")

    def _redo_visor(self):
        self._tanca_sessio_tap()
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            vr.redo()
            self._sincronitza_temps_del_visor()
        else:
            self.registra("Edita: no hi ha visor carregat")

    def _zoom_visor(self, factor):
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            vr.zoom(factor)

    def _zoom_tot_visor(self):
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            vr.zoom_tot()

    def _marca_A_visor(self):
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            vr.marca_A()

    def _marca_B_visor(self):
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            vr.marca_B()

    def _loop_visor(self):
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            vr.commuta_loop()

    def _focus_parametres(self):
        self.bpm.setFocus()

    def _dreceres(self):
        """TOTES les dreceres, en grups (A3).

        Les de **menú** es llegeixen dels menús REALS (així el diàleg no pot
        quedar desfasat mai: si s'hi afegeix una drecera, hi surt sola); les que
        NO són de menú (teclat del visor i gestos de ratolí) van llistades aquí
        a mà, que és l'únic lloc on viuen.
        """
        grups = []
        for accio in self.menuBar().actions():
            menu = accio.menu()
            if menu is None:
                continue
            parells = []
            for a in menu.actions():
                if a.isSeparator() or a.menu() is not None:
                    continue
                drecera = a.shortcut().toString()
                if drecera:
                    parells.append((a.text().replace("&", ""), drecera))
            if parells:
                grups.append((accio.text().replace("&", ""), parells))
        grups.append(("Ratolí i tecles del visor (combinacions)", [
            ("seleccionar un clip", "Clic a un clip"),
            ("afegir / treure un clip de la selecció (disjunt)", "Ctrl+clic"),
            ("rang de clips del MATEIX carril", "Shift+clic"),
            ("moure un clip (tot el grup si està seleccionat)",
             "Arrossega el cos del clip"),
            ("duplicar l'element seleccionat (sense arrossegar)",
             "Ctrl+D"),
            ("eina de selecció temporal (mentre es mantenen)",
             "Ctrl+Shift"),
            ("redimensionar (inici / final)", "Arrossega una vora"),
            ("rectangle de selecció (marquee)",
             "Ctrl+arrossega (temporal) o Eina marc ▸ arrossega"),
            ("canviar d'eina del timeline (intel·ligent ⇄ marc)", "E"),
            ("cursor al punt clicat / buidar la selecció", "Clic al fons"),
            ("seleccionar TOT el que hi ha dins el loop", "Doble-clic al loop"),
            ("marcar / editar el loop A-B", "Arrossega sobre el regle"),
            ("menú d'accions del clip", "Botó dret a un clip"),
            ("desplaçar la vista (pan)", "Botó dret arrossegant"),
            ("zoom", "Roda del ratolí"),
            ("play / pausa", "Espai"),
            ("TAP del temps (tap tempo)", "T"),
            ("copiar / retallar / enganxar al cursor",
             "Ctrl+C / Ctrl+X / Ctrl+V"),
            ("enganxar SALTANT-SE el snap", "Ctrl+Alt+V"),
            ("moure un clip un pas de graella (Alt = vora dreta)",
             "← / →"),
            ("Alt+clic", "cap acció de l'app (el sistema pot interceptar-lo)"),
            ("cancel·lar: rang en curs · loop · selecció", "Esc"),
            ("desfer / refer", "Ctrl+Z / Ctrl+Y"),
            ("reanomenar (clip o grup del tipus actiu)", "F2"),
            ("esborrar la selecció", "Del"),
        ]))
        return grups

    # ---------- Avisos ---------------------------------------------------------
    def avisa(self, titol, text):
        """Avis d'advertència. Vegeu `_avis`."""
        return self._avis(titol, text, "warning")

    def avisa_info(self, titol, text):
        """Avis informatiu. Vegeu `_avis`."""
        return self._avis(titol, text, "information")

    def avisa_crit(self, titol, text):
        """Avis crític. Vegeu `_avis`."""
        return self._avis(titol, text, "critical")

    def _avis(self, titol, text, tipus):
        """Mostra un avís modal (no hi ha cap pont que puga quedar encallat)."""
        return getattr(QMessageBox, tipus)(self, titol, str(text))

    def _text_dreceres(self):
        """El diàleg de dreceres en HTML (separat per poder-lo testar)."""
        blocs = []
        for grup, parells in self._dreceres():
            blocs.append(f"<b>{grup}</b><br>" + "<br>".join(
                f"{text} — {drecera}" for text, drecera in parells))
        return "<br><br>".join(blocs)

    def _mostra_dreceres(self):
        QMessageBox.information(self, "Dreceres de teclat", self._text_dreceres())

    def _quant_a(self):
        text = (
            "<b>Auto Chords</b><br>"
            f"Versió <b>{__version__}</b><br>"
            "wav → acords + estructura<br><br>"
            "Visor DAW-like (PyQt5).<br>"
            "Motor: Chordino (acords) + Queen Mary/qm (estructura) · Vamp.")
        QMessageBox.about(self, "Quant a Auto Chords", text)

    def registra(self, t):
        self.logger.info("UI: %s", t)
        self.log.append(t)

    # ---- lectura manual dels camps de text ----
    @staticmethod
    def _parse_compas(text, defecte_num=4, defecte_den=4):
        """Accepta «4», «4/4», «3/4», «2/4», «1/4», «6/8»; `0/0` és rubato."""
        s = str(text).replace(" ", "").strip()
        if not s:
            raise ValueError("El compàs no pot estar buit")
        if "/" in s:
            parts = s.split("/", 1)
            if len(parts) != 2 or not all(p.isdigit() for p in parts):
                raise ValueError(f"El compàs «{text}» no és vàlid")
            numer, den = int(parts[0]), int(parts[1])
        elif s.isdigit():
            numer, den = int(s), int(defecte_den)
        else:
            raise ValueError(f"El compàs «{text}» no és vàlid")
        _, numer, den = tempo_map.valida_tempo(
            limits.BPM_MIN, numer, den)
        return numer, den

    @staticmethod
    def _llegeix_num(w, defecte, minim, maxim, enter=False):
        try:
            v = float(str(w.text()).replace(",", ".").strip())
        except (ValueError, AttributeError):
            return defecte
        v = max(minim, min(maxim, v))
        return int(round(v)) if enter else v

    def _bpm_unit_val(self):
        """Clau de la unitat de BPM triada a la barra (sempre vàlida)."""
        cb = getattr(self, "cb_bpm_unit", None)
        return bpm_unit_mod.normalitza(cb.currentData() if cb else None)

    def _posa_bpm_quarter(self, bpm_quarter, decimals=3):
        """Escriu al camp de BPM un valor INTERN (negres/min) en la unitat triada."""
        self.bpm.setText(bpm_unit_mod.formata(
            float(bpm_quarter), self._bpm_unit_val(), decimals))

    def _canvia_unitat_bpm(self, _idx=None):
        """Canvia la unitat mostrada sense tocar el valor intern del tempo."""
        vr = getattr(self, "visor_ref", None)
        unit = self._bpm_unit_val()
        if vr is not None:
            vr.set_bpm_unit(unit)
            try:
                _idx, q, _num, _den = vr.tempo_objectiu_vals()
            except Exception:  # noqa: BLE001
                q = float(getattr(vr, "bpm", 120.0))
        else:
            try:
                q = bpm_unit_mod.a_quarter(
                    float(self.bpm.text().replace(",", ".").strip()),
                    getattr(self, "_bpm_unit_anterior", "negra"))
            except ValueError:
                q = 120.0
        self._bpm_unit_anterior = unit
        # El camp ha de mostrar el mateix valor intern amb la unitat nova.
        self._actualitzant_temps = True
        try:
            self._posa_bpm_quarter(q)
        finally:
            self._actualitzant_temps = False
        self._marca_dirty()

    def _bpm_val(self):
        raw = str(self.bpm.text()).replace(",", ".").strip()
        try:
            quarter = bpm_unit_mod.a_quarter(float(raw), self._bpm_unit_val())
            return tempo_map.valida_tempo(quarter, 4, 4)[0]
        except (ValueError, TypeError) as e:
            raise ValueError(f"Tempo: {e}") from e

    def _bpb_val(self):
        num, den = self._parse_compas(self.bpb.text())
        return tempo_map.valida_tempo(self._bpm_val(), num, den)[1]

    def _beat_type_val(self):
        num, den = self._parse_compas(self.bpb.text())
        return tempo_map.valida_tempo(self._bpm_val(), num, den)[2]

    def _posa_offset_camp(self, valor):
        """Escriu l'offset amb 3 decimals, però conserva el valor exacte.

        També s'usa en carregar un projecte: el text de la GUI no pot ser la
        font de veritat de l'offset (1.207438 es veu com 1.207).
        """
        exact = float(valor)
        text = f"{exact:.3f}"
        self.offset.setText(text)
        self._offset_ui_text = text
        self._offset_ui_exact = exact

    def _offset_val(self):
        """Offset en segons sense perdre la precisió que no cap a la GUI.

        El camp mostra 3 decimals (`1.207`), però el model pot tindre
        `1.207438`. Si l'usuari no ha tocat el text que va pintar
        `_sincronitza_temps_del_visor`, es recupera el valor intern exacte.
        """
        text = str(self.offset.text()).strip()
        exact = getattr(self, "_offset_ui_exact", None)
        if (exact is not None
                and getattr(self, "_offset_ui_text", None) == text):
            return float(exact)
        return self._llegeix_num(self.offset, 0.0, 0.0, 60.0)

    def _cb_a_secs(self, text):
        """'C.B' o 'C.B.S' (compàs.beat.fusa) -> segons (offset=0)."""
        import re
        m = re.match(r"\s*(-?\d+)\s*[.,]\s*(\d+)"
                     r"(?:\s*[.,]\s*(\d+))?\s*$", str(text))
        if not m:
            return None
        c, b = int(m.group(1)), int(m.group(2))
        sub = int(m.group(3)) if m.group(3) else 1
        sub = max(1, min(8, sub))
        beat_len = 60.0 / max(self._bpm_val(), 1e-9)
        n = ((c - 1) * max(1, self._bpb_val()) + (b - 1)
             + (sub - 1) / 8.0)
        return max(0.0, min(60.0, n * beat_len))

    def _secs_a_cb(self, t):
        """Segons -> 'C.B' o 'C.B.S' (fusa) a la graella ORIGINAL."""
        beat_len = 60.0 / max(self._bpm_val(), 1e-9)
        bpb = max(1, self._bpb_val())
        p = int(round(float(t) / beat_len * 8))
        SB = bpb * 8
        c = p // SB + 1
        dins = p % SB
        b = dins // 8 + 1
        sub = dins % 8 + 1
        return f"{c}.{b}" if sub == 1 else f"{c}.{b}.{sub}"

    def _offset_cb_canviat(self):
        """L'usuari ha escrit el camp compàs.beat -> passa-ho a segons."""
        s = self._cb_a_secs(self.offset_cb.text())
        if s is None:
            return
        self._posa_offset_camp(s)
        self._aplica_parametres_temps()

    def _canvia_mode_temps(self, bpm_compas):
        """Canvia entre mode BPM·compàs i mode Lliure (hh:mm:ss)."""
        self._params_temps.setVisible(bool(bpm_compas))
        if hasattr(self, "barra_temps"):
            self.barra_temps.setVisible(bool(bpm_compas))
        self.tempo_fix.setChecked(bool(bpm_compas))
        self._actualitza_metro_ui()

    def _snap_marcador_qm(self, t):
        """Retorna el beat QM més pròxim a `t` (sempre, sense tolerància).

        El contracte nou fa que el `+` no es guarde mai a la posició crua del
        cursor si hi ha anàlisi de QM: el marcador ha de coincidir amb un beat
        de QM. Si no n'hi ha cap, retorna `None` i el cridador ha d'avisar.
        """
        info = getattr(self, "_beats_actuals", None)
        if not info:
            info = (getattr(getattr(self, "projecte", None), "dades", {})
                    .get("analisi_beats"))
        if not isinstance(info, dict):
            return None
        beats = [float(x) for x in (info.get("beats") or ())]
        downbeats = [float(x) for x in (info.get("downbeats") or ())]
        objectius = sorted(set(beats or downbeats))
        if not objectius:
            return None
        return min(objectius, key=lambda x: (abs(x - float(t)), x))

    def _afegeix_marcador(self, tipus="seccio"):
        """Marca un inici de compàs al cursor (o mentre sona). Tecla `+`.

        Contracte nou: sempre s'encaixa al **beat QM més pròxim**; si no hi ha
        QM, no es crea el marcador i s'avisa. El visor recalcula els clips
        afectats amb prioritat de BPM i ajust de compàs.
        """
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.avisa("Marcador", "Primer obri una WAV.")
            return False
        mode = (self.cb_graella.currentData()
                if hasattr(self, "cb_graella") else "") or ""
        if mode == "qm_beats":
            t = self._snap_marcador_qm(float(vr.pos))
            if t is None:
                msg = ("No s'ha afegit el marcador: el Snap està en "
                       "«Beats QM» però no hi ha beats QM. Executa "
                       "«Analitza BPM» o canvia la graella.")
                self.registra(msg)
                self._missatge_info(msg)
                return False
        else:
            # Fora del mode QM, mana la graella BPM/compàs del timeline.
            t = vr._snap_ui(float(vr.pos))
            if not (0.0 < t < vr._durada_wav() - 1e-3):
                msg = "No s'ha afegit el marcador: cau fora del tema."
                self.registra(msg)
                self._missatge_info(msg)
                return False
        ok = bool(vr.afegeix_marcador(t=t, tipus=tipus))
        if ok:
            self.registra(f"Marcador a {t:.3f}s "
                          f"({len(vr.marcadors)} en total)")
        else:
            prop = min((abs(float(m) - t) for m in (vr.marcadors or ())),
                       default=99.0)
            if prop < 0.05:
                msg = ("No s'ha afegit: ja hi ha un marcador a "
                       f"{t:.3f}s (o a menys de 50 ms).")
            else:
                msg = ("No s'ha pogut afegir el marcador: el clip resultant "
                       "no conté cap beat sencer de la graella del Snap.")
            self.registra(msg)
            self._missatge_info(msg)
        return ok

    def _bpm_dels_marcadors(self):
        """Deduu el BPM dels marcadors i reescriu el mapa (clips editables)."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.avisa("BPM dels marcadors", "Primer obri una WAV.")
            return False
        if len(vr.marcadors or ()) < 2:
            self.avisa("BPM dels marcadors",
                       "Calen almenys dos marcadors (prem + al compàs 1 i a un "
                       "altre compàs).")
            return False
        try:
            cands = vr.candidats_bpm_marcadors(self._bpm_val(),
                                               self._bpb_val(),
                                               self._beat_type_val())
        except ValueError as e:
            self.avisa("BPM dels marcadors", str(e))
            return False
        if not cands:
            self.avisa("BPM dels marcadors",
                       "Els marcadors no quadren amb cap BPM entre 60 i 180.")
            return False
        dlg = dialeg_bpm_marcadors.DialegBpmMarcadors(
            cands, self, self._bpb_val(), self._beat_type_val())
        if dlg.exec_() != dlg.Accepted:
            return False
        triat = dlg.triat()
        if not triat:
            return False
        ok = bool(vr.aplica_bpm_marcadors(triat, self._bpb_val(),
                                          self._beat_type_val()))
        if ok:
            self._sincronitza_temps_del_visor()
            self._desa_meta_silencios()
            self.registra(
                f"BPM dels marcadors: {triat['bpm']:.2f} · "
                f"{len(triat.get('intervals') or ())} trams · "
                f"compassos {triat.get('compassos')}")
        return ok

    def _ajusta_bpms_marcadors(self):
        """Acció per lot: un beat sencer a cada interval de marcador.

        Recorre els intervals entre marcadors, conserva el BPM de referència
        i ajusta el compàs (o, si cal, un BPM proper) perquè cada clip continga
        almenys un beat sencer. S'aplica en **una sola operació de desfer**.
        """
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.avisa("Ajusta BPMs", "Primer obri una WAV.")
            return False
        if len(vr.marcadors or ()) < 2:
            self.avisa("Ajusta BPMs",
                       "Calen almenys dos marcadors (prem + a cada inici de "
                       "compàs que vulgues ajustar).")
            return False
        self._atura_si_sona("ajust dels BPMs pels marcadors")
        abans = len(vr.tempo_trams or ())
        ok = bool(vr.ajusta_bpms_marcadors())
        if ok:
            self._sincronitza_temps_del_visor()
            self.registra(
                f"Ajusta BPMs pels marcadors: {len(vr.tempo_trams)} trams "
                f"(abans {abans}), compàs 1 a {float(vr.offset):.3f}s")
            self._missatge_info(
                f"BPMs ajustats amb {len(vr.marcadors)} marcadors "
                f"({len(vr.tempo_trams)} trams). Ctrl+Z ho desfà tot.")
        return ok

    def _ajusta_bpm_minims_quadrats(self):
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.avisa("Ajusta BPM", "Primer obri una WAV.")
            return False
        if len(vr.marcadors or ()) < 2:
            self.avisa("Ajusta BPM",
                       "Calen almenys dos marcadors.")
            return False
        self._atura_si_sona("ajust del BPM per mínims quadrats")
        abans = len(vr.tempo_trams or ())
        ok = bool(vr.ajusta_bpm_minims_quadrats())
        if ok:
            self._sincronitza_temps_del_visor()
            self.registra(
                f"Ajusta BPM mínims quadrats: {len(vr.tempo_trams)} trams "
                f"(abans {abans})")
            self._missatge_info(
                f"BPM ajustat per mínims quadrats "
                f"({len(vr.tempo_trams)} trams). Ctrl+Z ho desfà tot.")
        return ok

    def _esborra_ultim_marcador(self):
        vr = getattr(self, "visor_ref", None)
        if vr is None or not vr.elimina_marcador():
            return False
        return True

    def _obre_guia_rapida(self):
        """Guia de benvinguda (només informació, sense tocar el model)."""
        dlg = dialeg_guia_rapida.DialegGuiaRapida(self)
        dlg.exec_()

    def _detecta_bpm(self, pregunta=True):
        """Obre el dialeg d'opcions de BPM i detecta (l'usuari pot editar-lo)."""
        self._actualitza_desti_accions()
        wav = self.wav_edit.text().strip()
        if not wav or not os.path.isfile(wav):
            self.avisa("Detecta BPM",
                                "Primer tria una WAV.")
            return
        if pregunta:
            dlg = dialegs.DialegOpcions(self, tab="bpm", opcions=self.opcions)
            if dlg.exec_() != QDialog.Accepted:
                return
            self.opcions = dlg.opcions()
            dialegs.desa_opcions(self.opcions)
            self._marca_dirty()
            # La casella «Només els acords» i l'acció «Inclou estructura» són
            # el MATEIX estat: es sincronitzen (una sola font de veritat).
            self.amb_est.setChecked(
                bool((self.opcions.get("analisi") or {})
                     .get("estructura", True)))
        b = self.opcions.get("bpm", {})
        vr = getattr(self, "visor_ref", None)
        kind, idx = vr.seleccio_activa() if vr is not None else (None, -1)
        te_tempo = (kind == "tempo" and vr is not None
                    and 0 <= idx < len(vr.tempo_trams or []))
        tr = vr.tempo_trams[idx] if te_tempo else None
        # Selecció A–B: si hi ha loop marcat, el BPM surt NOMÉS d'eixe rang
        # (mana sobre el tram seleccionat i sobre el tema sencer).
        loop = self._loop_actiu()
        self._atura_si_sona("deteccio de BPM")
        if loop is not None:
            self.registra(f"Detectant el BPM de la selecció A–B "
                          f"({loop[0]:.3f}–{loop[1]:.3f}s)…")
        else:
            self.registra("Detectant el BPM…" if not te_tempo
                          else f"Detectant el BPM del tram {idx}…")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            if loop is not None:
                bpm = pipeline.detecta_bpm_tram(
                    wav, loop[0], loop[1], self.registra,
                    bpm_min=b.get("min"), bpm_max=b.get("max"),
                    preferit=(b.get("pref_min"), b.get("pref_max")))
            elif te_tempo:
                bpm = pipeline.detecta_bpm_tram(
                    wav, float(tr[0]), float(tr[1]), self.registra,
                    bpm_min=b.get("min"), bpm_max=b.get("max"),
                    preferit=(b.get("pref_min"), b.get("pref_max")))
            else:
                bpm = pipeline.detecta_bpm(
                    wav, self.registra,
                    bpm_min=b.get("min"), bpm_max=b.get("max"),
                    preferit=(b.get("pref_min"), b.get("pref_max")),
                    motor=b.get("motor", "nostre"))
        finally:
            QApplication.restoreOverrideCursor()
        if te_tempo:
            if bpm:
                ok = vr.retempo_tram_detectat(idx, bpm)
                if ok:
                    self._sincronitza_temps_del_visor()
                    aplicat = float(vr.tempo_trams[idx][2])
                    self.registra(
                        f"BPM del tram {idx}: {aplicat:.3f} "
                        f"(detectat {bpm:.3f}; fronteres intactes)")
                    self._missatge_info(
                        f"BPM del tram {idx}: {aplicat:.3f} "
                        "(ajustat sense moure les fronteres)")
                else:
                    self.avisa_info(
                        "Detecta BPM",
                        "El BPM detectat no canvia el tram o no es pot "
                        "aplicar dins del rang 30–350 BPM; no s'ha tocat "
                        "el mapa.")
            else:
                self.avisa_info(
                    "Detecta BPM",
                    "No s'ha pogut estimar el BPM del tram seleccionat.\n"
                    "Pot ser un tram massa curt o irregular: posa'l a mà.")
            return
        if bpm:
            self._posa_bpm_quarter(bpm)
            self.registra(f"BPM detectat: {bpm:.3f} (pots editar-lo)")
        else:
            self.avisa_info(
                "Detecta BPM",
                "No s'ha pogut estimar el BPM.\n"
                "Pot ser un tema en directe o molt irregular: escriu-lo a mà.")

    def eventFilter(self, obj, ev):
        """Filtre d'esdeveniments de la finestra.

        1. **`+`** (de dalt o del teclat numèric) → **marcador** en viu, també
           mentre sona. Si s'està escrivint en un camp, el `+` s'hi escriu.
        2. **Clic** dins la caixa d'informació (només lectura): pausa el
           rotatori i passa de pantalla sense esperar.
        """
        try:
            if (ev.type() == QEvent.KeyPress
                    and getattr(self, "visor_ref", None) is not None):
                tecla, txt, mods = ev.key(), ev.text(), ev.modifiers()
                es_plus = (tecla == Qt.Key_Plus
                           or (tecla == Qt.Key_Equal
                               and (txt == "+" or mods & Qt.ShiftModifier)))
                if es_plus:
                    # El MATEIX esdeveniment pot passar dos voltes pel filtre
                    # (el camp el rebutja i puja al pare): la segona no compta.
                    if getattr(self, "_plus_ev", None) is ev:
                        return True
                    self._plus_ev = ev
                    # Qui rep la tecla (o qui té el focus) manarà: si és un
                    # camp d'escriptura, el «+» s'hi escriu i no marca res.
                    w = obj if isinstance(obj, QWidget) \
                        else QApplication.focusWidget()
                    escrivint = False
                    while w is not None:
                        if isinstance(w, (QLineEdit, QAbstractSpinBox,
                                          QTextEdit, QPlainTextEdit)):
                            escrivint = True
                            break
                        w = w.parentWidget()
                    if escrivint:
                        return False        # que s'escriga el «+» al camp
                    self._afegeix_marcador()
                    return True
        except (RuntimeError, AttributeError):
            pass
        caixa = getattr(self, "info_box", None)
        if (caixa is not None
                and obj in (caixa, caixa.viewport())
                and ev.type() == QEvent.MouseButtonPress):
            self._clic_info_box()
            return True         # el clic no ha de moure el cursor de text
        return super().eventFilter(obj, ev)

    def _clic_info_box(self):
        """Clic a la caixa: 1r → PARA el rotatori (dura mes); seguents → avancen.

        Cada clic tambe **allarga** la pausa `_INFO_PAUSA_S`, de manera que es
        pot llegir al ritme de cadascu: clic per aturar, clic per passar de
        pagina. Passada la pausa, el rotatori es torna a moure sol.
        """
        import time as _t
        ara = _t.monotonic()
        if ara < getattr(self, "_info_pausa_fins", 0.0):
            # Ja estava pausat (per un clic anterior) → avanca una «pantalla».
            self._info_panell = getattr(self, "_info_panell", 0) + 1
            self._info_panell_t = ara
        self._info_pausa_fins = ara + _INFO_PAUSA_S
        self._actualitza_info_widget()

    def _actualitza_info_widget(self):
        """Mostra a la caixa d'informacio la info del que hi ha sota el ratoli.

        Si el ratoli es sobre un boto, un camp o una zona del visor amb
        informacio → l'explica. Si NO es sobre res amb info → passa al
        **rotatori de dreceres i consells** (`_info_panells`).
        """
        import time as _t
        if _t.monotonic() < getattr(self, "_info_msg_fins", 0.0):
            return          # hi ha un missatge transitori (desfer/refer...)
        try:
            w = QApplication.widgetAt(QCursor.pos())
        except Exception:  # noqa: BLE001
            # timer de hover (hot): fallback silenciós intencionat
            return
        html = None
        if w is not None:
            # El VISOR (timeline) es un sol giny: li demanem la zona del ratoli
            # (el seu "ratoli intel·ligent") per explicar quina accio hi faria.
            vr = getattr(self, "visor_ref", None)
            if vr is not None:
                tv = getattr(vr, "timeline", None)
                if tv is not None and (w is tv or w is tv.viewport()):
                    try:
                        pos = tv.viewport().mapFromGlobal(QCursor.pos())
                        zona = tv.info_zona(pos)
                        if zona:
                            html = f"<b>{zona}</b>"
                    except Exception:  # noqa: BLE001
                        # timer de hover (hot): fallback silenciós intencionat
                        pass
            if html is None:
                # pugem fins a un widget que tingui tooltip (els fills solen no
                # tenir-ne)
                x = w
                while x is not None and not x.toolTip():
                    x = x.parentWidget()
                if x is not None:
                    nom = x.text() if hasattr(x, "text") else ""
                    tip = x.toolTip()
                    html = f"<b>{nom}</b><br>{tip}" if nom else f"<b>{tip}</b>"
        if html is None:
            # Fora de qualsevol giny amb info → rotatori. Si el ratoli es sobre
            # la MATEIXA caixa, no rotem (que no canviï mentre es llegeix).
            html = self._info_defecte_html(_t.monotonic(),
                                           rota=(w is not self.info_box))
        if html:
            self._posa_info(html)

    def _posa_info(self, html):
        """Escriu la caixa d'informacio nomes si el contingut ha canviat.

        Comparar amb el darrer HTML escrit (i no amb `toHtml()`, que el
        normalitza) evita reescriure-la a cada tic del timer: si no, el
        desplaçament de la caixa es reiniciaria sense parar.
        """
        if html != getattr(self, "_info_html_actual", None):
            self._info_html_actual = html
            self.info_box.setHtml(html)

    def _info_panells(self):
        """Panells de la caixa d'informacio per defecte: consells + dreceres.

        Cada pantalla és **curta** (3-4 línies) i agrupada per **quan la
        necessites** (seleccionar, moure, copiar, loop, transport…), no per
        «la llista sencera de dreceres». El **primer** panell s'adapta a l'eina
        vigent del timeline. Les dreceres **dels menús** no hi surten: viuen
        senceres al dialeg **Ajuda ▸ Dreceres de teclat** (una sola font,
        `_dreceres()`), i l'últim panell ho recorda.
        """
        return [
            self._panell_eina(),
            ("Seleccionar clips", [
                ("Un clip", "Clic"),
                ("Afegir/treure un clip (disjunt)", "Ctrl+clic"),
                ("Rang del carril del clip clicat", "Shift+clic"),
                ("Eina de selecció temporal", "Ctrl+Shift"),
                ("Rectangle: el que HI SONA a dins", "Ctrl+arrossega"),
            ]),
            ("El rectangle (marquee)", [
                ("Agafa els clips que SONEN a dins, no només els que hi "
                 "comencen", ""),
                ("Només de les pistes que cobreix (si no toca les seccions, "
                 "no les agafa)", ""),
                ("Es temporal: Ctrl+arrossega · o fix: Eina marc", ""),
            ]),
            ("Duplicar un clip", [
                ("Duplicar l'element seleccionat (o el grup)", "Ctrl+D"),
                ("L'arrossegament normal mou; no duplica", ""),
            ]),
            ("Moure i redimensionar", [
                ("Moure (tot el grup si està seleccionat)",
                 "Arrossega el cos del clip"),
                ("Moure l'inici o el final", "Arrossega una vora"),
                ("Un pas de graella", "← / →"),
                ("La vora DRETA un pas de graella", "Alt+← / Alt+→"),
                ("Alt+clic", "cap acció de l'app"),
            ]),
            ("Copiar, retallar i enganxar", [
                ("Al cursor", "Ctrl+C / Ctrl+X / Ctrl+V"),
                ("L'enganxat SUBSTITUEIX el tram: la cançó no creix mai", ""),
                ("Enganxar saltant-se el snap", "Ctrl+Alt+V"),
            ]),
            ("Loop A-B", [
                ("Crear-lo o editar-lo", "Arrossega sobre el regle"),
                ("Marcar l'inici / el final al cursor", "Ctrl+[ / Ctrl+]"),
                ("Seleccionar TOT el que hi ha a dins", "Doble-clic al loop"),
                ("Loop a la selecció (unió dels 3 carrils)", "L"),
            ]),
            ("Transport", [
                ("Play / aturar", "Espai"),
                ("TAP del temps (tap tempo)", "T"),
                ("Canviar d'eina del timeline (intel·ligent ⇄ marc)", "E"),
            ]),
            ("Tecla Esc (cancel·lar)", [
                ("Rang en curs (rectangle) → l'anul·la", "Esc"),
                ("Loop a mig marcar → el descarta", "Esc"),
                ("Loop actiu → el desactiva i ESBORRA (fora la caixa groga)",
                 "Esc"),
                ("Alguna cosa seleccionada → la buida", "Esc"),
            ]),
            ("Editar i desfer", [
                ("Desfer / refer", "Ctrl+Z / Ctrl+Y"),
                ("Reanomenar (clip o grup del tipus actiu)", "F2"),
                ("Esborrar la selecció", "Del"),
            ]),
            ("Zoom i navegació", [
                ("Zoom", "Roda del ratolí"),
                ("Zoom + / − / total", "Ctrl++ / Ctrl+− / Ctrl+0"),
                ("Menú del clip (o pan arrossegant)", "Botó dret"),
            ]),
            ("Quantitza: què fa i què NO toca", [
                ("Mou només els INICIS dels clips a la graella; el final de "
                 "cada clip es deriva del següent", ""),
                ("Abast: tot, només la selecció, tot però només acords o tot "
                 "però només estructura", ""),
                ("Graella d'acords: de corxera a 1 compàs. Graella "
                 "d'estructura: d'1 a 64 compassos", ""),
                ("No toca BPM, compàs, offset ni el cru de l'anàlisi: "
                 "treballa sobre el model que veus", ""),
                ("És una sola operació: Ctrl+Z la desfà i Ctrl+Y la refer", ""),
            ]),
            ("Per què l'enganxat sobreescriu", [
                ("Els clips cobreixen SEMPRE tota la WAV (regla d'or #4)", ""),
                ("Per això copiar/enganxar és com una cinta: substitueix", ""),
                ("Totes les dreceres dels menús: Ajuda ▸ Dreceres de teclat", ""),
            ]),
        ]

    def _panell_eina(self):
        """Panell que **segueix l'eina vigent** del timeline (marc/intel·ligent)."""
        tool = "intel·ligent"
        try:
            tv = getattr(getattr(self, "visor_ref", None), "timeline", None)
            if tv is not None:
                tool = tv.tool()
        except Exception:  # noqa: BLE001
            pass
        if str(tool).startswith("marc"):
            return ("Eina del timeline: SELECCIÓ", [
                ("Arrossega pel timeline per DIBUIXAR un rectangle", ""),
                ("Selecciona el que hi SONA a dins, i només de les pistes "
                 "que cobreixi", ""),
                ("No mou cap clip; el rectangle desapareix en deixar anar", ""),
                ("Botó «Eina» a la barra (o Selecciona) per canviar d'eina", ""),
            ])
        return ("Eina del timeline: intel·ligent", [
            ("La fletxa s'adapta al que toques (no cal triar res)", ""),
            ("Cos del clip = MOURE · vores del clip = redimensionar", ""),
            ("Regle = crea el LOOP A-B · roda = zoom", ""),
            ("Shift+clic = rang · Ctrl+clic = afegir/treure de la selecció", ""),
            ("Botó «Eina» a la barra (o Selecciona) per passar a «marc»", ""),
        ])

    def _info_defecte_html(self, ara, rota=True):
        """HTML del panell actual de dreceres/consells (rotant cada ~14 s).

        `rota=False` congela el panell (ratoli sobre la caixa). I si hi ha una
        **pausa per clic** vigent (`_info_pausa_fins`), tampoc no rota.
        """
        panells = self._info_panells()
        if not panells:
            return None
        n = len(panells)
        if ara < getattr(self, "_info_pausa_fins", 0.0):
            rota = False        # pausat per un clic a la caixa
        t0 = getattr(self, "_info_panell_t", 0.0)
        if t0 <= 0.0:
            self._info_panell_t = ara          # primera vegada: sense rotar
        elif rota and ara - t0 >= _INFO_ROTACIO_S:
            self._info_panell = (getattr(self, "_info_panell", 0) + 1) % n
            self._info_panell_t = ara
        i = getattr(self, "_info_panell", 0) % n
        titol, parells = panells[i]
        files = []
        for text, dr in parells:
            files.append(f"{text} · <b>{dr}</b>" if dr else text)
        cap = (f"<b style='color:{theme.BLAU_INFO}'>Dreceres i consells</b> "
               f"<span style='color:{theme.MUTED}'>({i + 1}/{n})</span>")
        peu = ("<br><br><i style='color:%s'>Ratolí per un botó → què fa · "
               "<b>clic aquí</b> → atura i passa de pàgina.</i>" % theme.MUTED)
        return cap + f"<br><b>{titol}</b><br>" + "<br>".join(files) + peu

    # ---- accions d'edició des del menú (reutilitzen la lògica existent) ----
    def _clip_seleccionat(self):
        """Retorna (kind, idx) de l'element actiu del timeline (3 carrils)."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return None, -1
        return vr.seleccio_activa()

    def _elimina_element(self):
        """`Del`: el despatx únic resol la selecció (una o múltiple, 3 carrils)."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return False
        return vr.executa_edicio("elimina")

    def _duplica_element(self):
        """`Ctrl+D`: el despatx únic resol el clip o el grup seleccionat."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return False
        return vr.executa_edicio("duplica")

    def _troba_i_reemplaca_ui(self):
        """Troba i reemplaça xifrats (acords) o etiquetes (estructura) a tot el tema."""
        vr = self.visor_ref
        if vr is None:
            self.avisa_info("Auto Chords", "No hi ha cap tema obert.")
            return
        dlg = dialegs.DialegTrobaReemplaca(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        troba, reemplaca = dlg.troba(), dlg.reemplaca()
        if not troba or not reemplaca:
            self.avisa_info("Auto Chords",
                            "Cal omplir «Troba» i «Reemplaça per».")
            return
        n = vr.troba_i_reemplaca(dlg.camp(), troba, reemplaca)
        if n:
            self.registra(f"substituïts {n} elements: «{troba}» → «{reemplaca}»")
        else:
            self.avisa_info("Auto Chords",
                            f"No s'ha trobat cap «{troba}» per substituir.")

    def _marca_rubato_rang(self):
        """Marca el rang A–B com a rubato (fase 3.2)."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self._missatge_info("Obre un tema abans de marcar un rubato.")
            return
        loop = vr._loop_vals()
        if loop is None:
            self._missatge_info(
                "Marca primer un rang A–B (arrossega el regle o usa A/B).")
            return
        vr.crea_rubato_rang(*loop)

    def _converteix_rubato_ui(self):
        """Converteix el tram de tempo seleccionat a rubato."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self._missatge_info("Obre un tema abans de convertir un tram.")
            return
        kind, idx = vr.seleccio_activa()
        if kind != "tempo" or not vr._index_valid("tempo", idx):
            self._missatge_info(
                "Selecciona un clip del carril de BPM/compàs.")
            return
        vr.converteix_rubato(idx)

    def _converteix_normal_ui(self):
        """Converteix el rubato seleccionat en clips normals."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self._missatge_info("Obre un tema abans de convertir un rubato.")
            return
        kind, idx = vr.seleccio_activa()
        if kind != "tempo" or not vr._index_valid("tempo", idx):
            self._missatge_info(
                "Selecciona un clip del carril de BPM/compàs.")
            return
        vr.converteix_normal(idx)

    def _tempo_mapa_ui(self):
        """Mapa de tempo i compàs: canvis de BPM/compàs al llarg del tema."""
        vr = self.visor_ref
        if vr is None:
            self.avisa_info("Auto Chords", "Obre un tema primer.")
            return
        den0 = int(getattr(vr, "beat_type", 4) or 4)
        trams = getattr(vr, "tempo_trams", None) or [
            (0.0, vr._durada_wav(), float(vr.bpm), int(vr.bpb), den0)]
        if any(getattr(t, "tipus", None) == "rubato" for t in trams):
            self._missatge_info(
                "Aquest mapa té rubatos; l'editor de trams arribarà en la "
                "fase 3.2. Els rubatos es mostren al visor com a derivats.")
            return
        dlg = dialegs.DialegTempoMapa(self, trams, vr._durada_wav(),
                                      unit=vr.bpm_unit)
        if dlg.exec_() != QDialog.Accepted:
            return
        if not vr.aplica_tempo_validat(dlg.trams(), "Mapa de tempo"):
            self.avisa_info("Auto Chords", "El mapa no és vàlid.")
            return
        self._sincronitza_temps_del_visor()
        self.registra(f"mapa de tempo/compàs: {len(vr.tempo_trams)} tros(s)")

    def detecta_tempo_mapa(self, avis=True):
        """Inferir el mapa de tempo a partir dels temps (beats) detectats.

        NUCLI (sense diàlegs). Retorna el nombre de trams inferits (0 si el
        tempo és constant o si no s'ha pogut). Amb `avis=False` els problemes
        van per **excepció**: cap finestra emergent.
        """
        vr = self.visor_ref
        wav = self.wav_edit.text().strip()
        if vr is None or not wav:
            if not avis:
                raise RuntimeError("Cal obrir un tema primer.")
            self.avisa_info("Auto Chords", "Obre un tema primer.")
            return 0
        try:
            temps = pipeline.detecta_beats(wav, log=self.registra)
        except Exception as e:  # noqa: BLE001
            if not avis:
                raise
            self.avisa_info("Auto Chords",
                            f"No s'han pogut detectar els temps: {e}")
            return 0
        self.registra(f"detecta tempo: {len(temps)} temps trobats")
        trams = tempo_map.infereix_trams_beat(
            temps, vr._durada_wav(), int(vr.bpb),
            int(getattr(vr, "beat_type", 4) or 4))
        if len(trams) <= 1:
            self.registra("detecta tempo: és constant (cap canvi)")
            return 0
        if vr.aplica_tempo_validat(trams, "Mapa de tempo detectat"):
            self._sincronitza_temps_del_visor()
            self.registra(f"mapa de tempo inferit: {len(trams)} tros(s)")
            return len(trams)
        return 0

    def _detecta_tempo_per_trams(self):
        """Acció de menú: mapa de BPM cada N compassos (tempo variable)."""
        vr = getattr(self, "visor_ref", None)
        wav = self.wav_edit.text().strip()
        if vr is None or not wav or not os.path.isfile(wav):
            self.avisa_info("Auto Chords", "Primer obri un tema amb àudio.")
            return
        ft = getattr(self, "_fil_trams", None)
        if ft is not None and ft.isRunning():
            self.avisa_info("Auto Chords",
                            "Ja hi ha una detecció per trams en curs.")
            return
        durada = vr._durada_wav()
        dlg = dialegs.DialegTempoPerTrams(
            self, durada=durada, num=int(vr.bpb),
            den=int(getattr(vr, "beat_type", 4) or 4))
        if dlg.exec_() != QDialog.Accepted:
            return
        cada, tol, offset_auto = dlg.valors()
        self._atura_si_sona("detecció de tempo per trams")
        b = self.opcions.get("bpm", {})
        self.registra(f"Detectant el tempo per trams (1 BPM cada {cada} "
                      f"compassos, fusió {tol * 100:.1f} %)…")
        fil = FilTempoTrams(
            wav, durada, int(vr.bpb), int(getattr(vr, "beat_type", 4) or 4),
            cada, tol, bpm_min=b.get("min"), bpm_max=b.get("max"),
            preferit=(b.get("pref_min"), b.get("pref_max")),
            offset=None if offset_auto else 0.0, parent=self)
        fil.feta.connect(self._tempo_trams_fet)
        fil.missatge.connect(self.registra)
        fil.finished.connect(
            lambda: (setattr(self, "_fil_trams", None), fil.deleteLater()))
        self._fil_trams = fil
        fil.start()

    def _tempo_trams_fet(self, res):
        """Arriba el mapa de tempo per trams: s'aplica amb UN sol desfer."""
        vr = getattr(self, "visor_ref", None)
        trams = (res or {}).get("trams") or []
        offset = float((res or {}).get("offset") or 0.0)
        base = (res or {}).get("bpm_base")
        if vr is None or not trams:
            self.avisa_info("Tempo per trams",
                            "No s'ha pogut construir el mapa de tempo "
                            "(potser l'àudio no té pols clar).")
            return
        vr._undo_marca()
        if offset > 0:
            vr.offset = offset
        ok = vr.aplica_tempo_validat(trams, "Mapa de tempo per trams")
        vr._undo_commit()
        if not ok:
            self.avisa_info("Tempo per trams",
                            "El mapa detectat no ha passat la validació de "
                            "compassos: no s'ha aplicat.")
            return
        self._sincronitza_temps_del_visor()
        if offset > 0:
            self.offset_cb.setText(self._secs_a_cb(offset))
        bpms = sorted({round(float(t[2]), 2) for t in trams})
        self.registra(
            f"mapa de tempo per trams: {len(trams)} trams, compàs 1 a "
            f"{offset:.3f}s, BPM base {base if base is None else round(base, 2)}"
            f" (rang {bpms[0]}–{bpms[-1]})")

    def _detecta_tempo_mapa(self):
        """Acció de menú: infereix el mapa i avisa per pantalla si cal."""
        self.detecta_tempo_mapa(avis=True)

    def _quantitza_ui(self):
        """Quantitza el model: abast + graella d'acords/estructura."""
        vr = self.visor_ref
        if vr is None:
            self.avisa_info("Auto Chords", "Obre un àudio primer.")
            return
        if not getattr(vr, "tempo_fix", False):
            self.avisa_info("Auto Chords",
                            "La quantització necessita el mode BPM · compàs.")
            return
        sel = vr.timeline.selected_keys()
        te_ac = any(k == "chord" for k, _i in sel)
        te_es = any(k == "section" for k, _i in sel)
        abast = "seleccio" if (te_ac or te_es) else "tot"
        dlg = dialegs.DialegQuantitza(
            self, abast=abast, te_acords=te_ac, te_seccions=te_es)
        if dlg.exec_() != QDialog.Accepted:
            return
        n = vr.quantitza(dlg.abast(), dlg.grid_acords(),
                         dlg.grid_estructura())
        if n:
            self.registra(f"quantització: {n} clip(s) "
                          f"(abast: {dlg.abast()})")

    # -- eina del timeline + abast del rang ----------------------------------
    def _replica_eina(self):
        """Aplica al visor les opcions vigents d'eina i d'abast del rang."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return
        marc = bool(getattr(self, "b_eina", None) is not None
                    and self.b_eina.isChecked())
        vr.timeline.set_tool("marc" if marc else "intel·ligent")

    def _canvia_eina(self, activat):
        """Commutador d'eina del timeline: intel·ligent ⇄ marc."""
        marc = bool(activat)
        if (getattr(self, "a_eina_marc", None) is not None
                and self.a_eina_marc.isChecked() != marc):
            self.a_eina_marc.setChecked(marc)       # propaga via `triggered`
        self.b_eina.setText("Eina: selecció" if marc else "Eina: intel·ligent")
        self._replica_eina()
        self.registra("eina del timeline: "
                      + ("marc (rubber-band)" if marc else "intel·ligent"))

    def _toggle_eina_marc(self, activat):
        """El menú «Selecciona» i el botó de la barra comparteixen estat."""
        if self.b_eina.isChecked() != bool(activat):
            self.b_eina.setChecked(bool(activat))   # dispara `_canvia_eina`

    def _toggle_eina_tecla(self):
        """Drecera `E`: commuta l'eina del timeline (intel·ligent ⇄ marc).

        És un **toggle** (no un on/off): cada pulsació canvia d'estat, i per
        defecte sempre s'arrenca en «intel·ligent».
        """
        if hasattr(self, "b_eina"):
            self.b_eina.setChecked(not self.b_eina.isChecked())

    def _copia_clips(self):
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            return vr.executa_edicio("copia")
        return False

    def _retalla_clips(self):
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            return vr.executa_edicio("retalla")
        return False

    def _enganxa_clips(self):
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            return vr.executa_edicio("enganxa")
        return False

    def _renomena_element(self):
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            return vr.executa_edicio("reanomena")
        return False

    def _parteix_acord_ui(self):
        """Parteix l'acord que conté el cursor pel punt del cursor (regla #11)."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.registra("Parteix: no hi ha visor carregat")
            return False
        if vr.executa_edicio("parteix", "chord", t=vr.pos):
            self.registra(f"acord partit a {vr.pos:.3f} s")
            return True
        self.registra("Parteix: el cursor no és dins cap acord")
        return False

    def _parteix_seccio_ui(self):
        """Parteix la secció que conté el cursor pel punt del cursor (A2)."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.registra("Parteix: no hi ha visor carregat")
            return False
        if vr.executa_edicio("parteix", "section", t=vr.pos):
            self.registra(f"secció partida a {vr.pos:.3f} s")
            return True
        self.registra("Parteix: el cursor no és dins cap secció")
        return False

    def _afegeix_tram_ui(self):
        """«Afegeix un canvi de tempo/compàs» al cursor (despatx únic)."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return False
        if vr.executa_edicio("afegeix", "tempo", t=vr.pos):
            self.registra(f"afegit un canvi de tempo/compàs a {vr.pos:.3f} s")
            return True
        self.registra("Afegeix tram: ja hi ha una frontera en eixe punt")
        return False

    def _parteix_tram_ui(self):
        """Parteix el tram de tempo/compàs que conté el cursor (paritat #11)."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.registra("Parteix: no hi ha visor carregat")
            return False
        if vr.executa_edicio("parteix", "tempo", t=vr.pos):
            self.registra(f"tram de tempo/compàs partit a {vr.pos:.3f} s")
            return True
        self.registra("Parteix: el cursor ja és en una frontera del mapa")
        return False

    def _afegeix_acord_ui(self):
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return False
        if vr.executa_edicio("afegeix", "chord", t=vr.pos):
            self.registra(f"afegit acord a {vr.pos:.3f}s")
            return True
        return False

    def _afegeix_seccio_ui(self):
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return False
        if vr.executa_edicio("afegeix", "section", t=vr.pos):
            self.registra(f"afegida secció a {vr.pos:.3f}s")
            return True
        return False

    def _sel_cursor(self, kind):
        """Selecciona el clip de `kind` que conté el cursor (despatx únic)."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return False
        idx = vr._idx_a_t(kind, vr.pos)
        if idx is None:
            return False
        return bool(vr.executa_edicio("selecciona", kind, idx, mode="set"))

    def _sel_acord_cursor(self):
        """Selecciona l'acord que conté la posició del cursor."""
        return self._sel_cursor("chord")

    def _sel_tram_cursor(self):
        """Selecciona el tram de BPM/compàs que conté la posició del cursor."""
        return self._sel_cursor("tempo")

    def _sel_seccio_cursor(self):
        """Selecciona la secció que conté la posició del cursor."""
        return self._sel_cursor("section")

    def _loop_seleccio(self):
        """`L`: loop A/B a la unió de la selecció (3 carrils)."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.registra("Loop a la selecció: no hi ha visor carregat")
            return False
        return bool(vr.executa_edicio("loop_seleccio"))

    def _neteja_loop(self):
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return
        vr._undo_marca()          # A1: el loop també és desfer/fer
        vr.loop_a = vr.loop_b = None
        vr.loop_on = False
        if hasattr(vr, "b_loop"):
            vr.b_loop.setChecked(False)
        if hasattr(self, "tb_loop"):
            self.tb_loop.setChecked(False)
        vr.timeline.set_loop(None, None)
        self.registra("loop netejat")
        vr._undo_commit()

    def _dobla_bpm(self, factor):
        """Multiplica (×2) o divideix (÷2) el BPM actual."""
        try:
            b = self._bpm_val() * float(factor)
        except ValueError as e:
            self.avisa_info("Tempo invàlid", str(e))
            return
        if not limits.BPM_MIN <= b <= limits.BPM_MAX:
            self.avisa_info(
                "Tempo invàlid",
                f"El resultat ({b:.3f} BPM) queda fora de "
                f"{limits.BPM_MIN:g}–{limits.BPM_MAX:g} BPM.")
            return
        self._posa_bpm_quarter(b)
        self._aplica_parametres_temps()
        self.registra(f"BPM {'×2' if factor > 1 else '÷2'} → {b:.3f}")

    def _tanca_sessio_tap(self):
        """Tanca la sessió de taps: desa el canvi i apila UN sol undo.

        La sessió s'obri al primer toc (o quan canvia el clip objectiu) i es
        tanca al cap de 2 s sense tocar, en canviar de clip o en aturar el
        transport. Així `Ctrl+Z` desfà tota la mesura de cop.
        """
        if not getattr(self, "_tap_sessio_oberta", False):
            return
        self._tap_sessio_oberta = False
        try:
            self._tap_timer.stop()
        except (AttributeError, RuntimeError):
            pass
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            try:
                if getattr(self, "_tap_canviat", False):
                    vr._desa_i_regenera()
                vr._undo_commit()
            except Exception as e:  # noqa: BLE001
                self.registra(f"tap tempo: no s'ha pogut tancar la sessió ({e})")
            self._sincronitza_temps_del_visor()
        self._tap_canviat = False

    def _tap_tempo(self):
        """Tap tempo (com als DAWs): intervals dels últims taps → BPM.

        El destí és el **clip de tempo seleccionat**; sense un tram de
        BPM/compàs seleccionat, T no fa res. Una sessió de taps = una sola
        operació de desfer.
        """
        self._actualitza_desti_accions()
        ara = time.monotonic()
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return
        kind, idx = vr.seleccio_activa()
        if kind != "tempo" or not vr._index_valid("tempo", idx):
            # T només actua amb un clip de BPM/compàs seleccionat.
            return
        idx = int(idx)
        # Canvi de clip objectiu o pausa > 2 s → tanca la sessió anterior.
        if self._taps and (self._tap_target != idx):
            self._tanca_sessio_tap()
            self._taps = []
        if self._taps and (ara - self._taps[-1]) > 2.0:
            self._tanca_sessio_tap()
            self._taps = []
        if vr is not None and not self._tap_sessio_oberta:
            self._tap_sessio_oberta = True
            self._tap_canviat = False
            vr._undo_marca()
            # Decisió 3: si està SONANT, el tap tanca el loop al clip de tempo
            # seleccionat.
            if getattr(vr, "sona", False):
                trams = list(vr.tempo_trams or [])
                if 0 <= idx < len(trams):
                    a, b = float(trams[idx][0]), float(trams[idx][1])
                    if b > a:
                        vr._fixa_loop(a, b, activa=True, alinea=True)
                        self._tap_canviat = True
        self._tap_target = idx
        self._taps.append(ara)
        if len(self._taps) > 8:
            self._taps = self._taps[-8:]         # finestra dels últims 8
        if len(self._taps) < 2:
            self.b_tap.setText("TAP (1)")
            self._tap_timer.start()
            return
        ivs = [b - a for a, b in zip(self._taps, self._taps[1:])]
        ivs = [x for x in ivs if 60.0 / limits.BPM_MAX <= x <= 2.0]
        if not ivs:
            self.b_tap.setText(f"TAP ({len(self._taps)})")
            self._tap_timer.start()
            return
        # TAP robust (Fase 3): mediana + descart d'intervals clarament anòmals.
        mediana = statistics.median(ivs)
        ivs_robustos = [x for x in ivs
                        if mediana * 0.7 <= x <= mediana * 1.3]
        if not ivs_robustos:
            ivs_robustos = [mediana]
        bpm = 60.0 / statistics.median(ivs_robustos)
        if vr is not None:
            _, _bpm, num, den = vr.tempo_objectiu_vals()
            if vr.edita_tempo_objectiu(idx, bpm, num, den, desa=False):
                self._tap_canviat = True
            self._sincronitza_temps_del_visor()
        else:
            self._posa_bpm_quarter(bpm)
        self.b_tap.setText(f"TAP ({len(self._taps)}) {bpm:.0f}")
        self.registra(f"tap tempo: {bpm:.3f} BPM · tram {idx} "
                      f"({len(self._taps)} taps)")
        self._tap_timer.start()
        self._actualitza_desti_accions()

    def _loop_actiu(self, minim=1.0):
        """Rang A–B del visor si serveix com a selecció, o `None`.

        Basta que A i B estiguen marcats: **no cal** que el loop estiga
        sonant (es pot detectar amb el transport parat). `minim` descarta
        rangs massa curts per a un BPM fiable.
        """
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return None
        a = getattr(vr, "loop_a", None)
        b = getattr(vr, "loop_b", None)
        if a is None or b is None:
            return None
        a, b = sorted((float(a), float(b)))
        if b - a < float(minim):
            return None
        return (max(0.0, a), b)

    def _talla_i_offset(self, t):
        """Offset del compàs 1 al cursor + tall del carril de tempo (1 desfer).

        El **clip de tempo** nou (si el cursor no era ja una frontera) arrenca
        exactament a `t`. Retorna `(trams, idx)` amb l'índex del clip que
        comença a `t`, o `None` si no hi ha visor.
        """
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return None
        durada = vr._durada_wav()
        t = max(0.0, min(float(t), durada))
        nous = tempo_map.parteix_trams_a(list(vr.tempo_trams or []), t, durada)
        vr._undo_marca()
        vr.offset = t
        vr.aplica_tempo_trams(nous)
        vr._undo_commit()
        self._sincronitza_temps_del_visor()
        self.offset_cb.setText(self._secs_a_cb(t))
        idx = next((i for i, s in enumerate(nous)
                    if abs(float(s[0]) - t) <= 1e-6), 0)
        return (nous, idx)

    def _marca_compas_1(self):
        """Compàs 1 al cursor: offset + tall + inici del clip de tempo.

        Un sol pas de desfer fa les tres coses (si el cursor ja era una
        frontera del mapa no hi ha tall: només canvia l'offset). El clip de
        tempo que arrenca al cursor es mostra en **segons** i en
        **compàs.beat** (la graella original, abans de moure l'offset), i es
        deixa seleccionat perquè els camps BPM/compàs l'editen.
        """
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.avisa("Compàs 1", "Primer obri un àudio.")
            return
        t = float(vr.pos)
        durada = vr._durada_wav()
        if t >= durada - 1e-3:
            self.avisa("Compàs 1",
                       "El cursor és al final de la WAV: no hi ha res a "
                       "alinear-hi.")
            return
        cb_original = self._secs_a_cb(t)     # ABANS de moure l'offset
        res = self._talla_i_offset(t)
        if res is None:
            return
        _nous, idx = res
        try:
            vr.timeline.selecciona("tempo", idx)
        except Exception:  # noqa: BLE001
            pass
        self.registra(f"Compàs 1 a {t:.3f}s · clip de tempo {idx} des de "
                      f"{t:.3f}s = compàs 1.1 (graella original "
                      f"{cb_original})")
        if len(res[0]) > 2:
            # El tall és LLIURE (no busca línia de compàs): amb trams
            # interiors, les fronteres poden quedar fora de compàs.
            self.registra("Atenció: el mapa té trams interiors — comprova "
                          "que les fronteres caiguen en línia de compàs "
                          "(o passa l'Anàlisi guiat).")

    def _detecta_compas1(self):
        """Detecta el compàs 1 (primer downbeat) i hi posa l'offset.

        Usa el detector d'onsets + el de compassos del Queen Mary
        (`pipeline.detecta_compas1`). No toca el BPM.
        """
        wav = self.wav_edit.text().strip()
        if not wav or not os.path.isfile(wav):
            self.avisa("Compàs 1", "Primer tria un àudio.")
            return
        self._atura_si_sona("detecció del compàs 1")
        self.registra("Detectant el compàs 1 (downbeat)…")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            seg = pipeline.detecta_compas1(wav, self.registra)
        except Exception as e:  # noqa: BLE001
            seg = None
            self.registra(f"compàs 1: error ({e})")
        finally:
            QApplication.restoreOverrideCursor()
        if seg is None:
            self.avisa_info(
                "Compàs 1",
                "No s'ha pogut detectar el compàs 1.\n"
                "Pots posar-lo a mà amb el botó 📍 (al cursor).")
            return
        self._posa_offset_camp(seg)
        self._aplica_parametres_temps()
        self.registra(f"Compàs 1 detectat a {seg:.3f}s ✔")

    def _aplica_parametres_temps(self):
        """Aplica BPM/compàs/offset al VISOR, al clip de tempo objectiu.

        Decisió 2B (2026-10-19): si hi ha un tram de tempo seleccionat, els
        camps de dalt editen **eixe tram**; si no, el transport (tram 0).
        L'offset continua sent global. No es reinicia l'àudio: el fil
        d'alimentació llig el BPM/mapa a cada tros.
        """
        if getattr(self, "_actualitzant_temps", False):
            return
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return
        idx = vr.tempo_objectiu()
        free = bool(getattr(self, "chk_segons", None)
                    and self.chk_segons.isChecked())
        if free:
            self._missatge_info(
                "El rubato es crea amb «Marca com a rubato» o «Converteix a "
                "rubato», no amb el commutador «En segons».")
            self.chk_segons.setChecked(False)
            self._sincronitza_temps_del_visor()
            return
        if not free:
            # Escriure 0 BPM NO s'ha de convertir en 30 en silenci: és el gest
            # natural per demanar un clip en segons.
            raw = str(self.bpm.text()).replace(",", ".").strip()
            try:
                zero = abs(float(raw)) <= 1e-9
            except ValueError:
                zero = False
            if zero:
                self.avis_info(
                    "Auto Chords",
                    "Un BPM de 0 no és vàlid. Per a un passatge rubato, marca "
                    "«En segons» al costat del compàs.")
                self._sincronitza_temps_del_visor()
                return
        try:
            bpm = self._bpm_val()
            if free:
                bpm, num, den = tempo_map.valida_tempo(bpm, 0, 0)
            else:
                num, den = self._parse_compas(self.bpb.text())
                bpm, num, den = tempo_map.valida_tempo(bpm, num, den)
        except ValueError as e:
            self.avisa_info("Tempo o compàs invàlid", str(e))
            self._sincronitza_temps_del_visor()
            return
        offset = self._offset_val()
        try:
            _idx, _bpm, _num, _den = vr.tempo_objectiu_vals()
        except Exception:  # noqa: BLE001
            _bpm, _num, _den = vr.bpm, vr.bpb, getattr(vr, "beat_type", 4)
        if (abs(bpm - float(_bpm)) <= 1e-9 and num == int(_num)
                and den == int(_den)
                and abs(offset - float(getattr(vr, "offset", 0.0))) <= 1e-9):
            return
        vr._undo_marca()
        vr.offset = offset
        ok = vr.edita_tempo_objectiu(idx, bpm, num, den)
        vr._undo_commit()
        self.offset_cb.setText(self._secs_a_cb(offset))
        if ok:
            self.registra(f"tempo: tram {idx} → {bpm:.3f} BPM · "
                          f"{num}/{den} (offset {offset:.3f}s)")
        self._sincronitza_temps_del_visor()

    def _segons_top_bar(self, actiu):
        """Casella «En segons»: a 3.1 es rebutja; el rubato és de 3.2."""
        if getattr(self, "_actualitzant_temps", False):
            return
        if not actiu and self.bpb.text().strip() in ("0/0", "0", ""):
            self.bpb.setText("4/4")     # tornar a compàs: un valor real
        self._aplica_parametres_temps()

    def _canvia_tempo(self, fix):
        """Commuta BPM·compàs ↔ Lliure i refresca el visor.

        ⚠️ Aci NO es torna a cridar `timeline.set_tempo_mode(...)`: eixa crida
        era anterior al **mapa de tempo variable** i, sense el paràmetre
        `mapa=`, deixava el timeline amb `_mapa = None`. Això apagava la pista
        de BPM/compàs (`TempoLayer._visible()`) i la graella/regle tornaven a
        la graella constant. `_actualitza_temps()` ja fa la crida correcta
        (amb `mapa=self.tempo_map`); ací només cal deixar-hi l'offset al dia,
        que és el que `_actualitza_temps()` hi llig. (reportat per l'operador,
        19-10-2026: «canvio a hh:mm:ss i torne a BPM i ja no hi ha carril»).
        """
        for w in (self.bpm, self.cb_bpm_unit, self.bpb, self.offset):
            w.setEnabled(fix)
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            # Els camps poden estar mostrant un tram interior (2B): el canvi de
            # MODE no ha de copiar-los al transport. L'offset, però, és global
            # i el camp n'és la font (el test de commutació ho exigeix).
            vr.offset = self._offset_val()
            vr.tempo_fix = bool(fix)
            vr._actualitza_temps()
            self._sincronitza_temps_del_visor()

    def _mostra_placeholder_visor(self):
        cont = QWidget()
        cont.setObjectName("placeholder_visor")
        cont.setStyleSheet(f"QWidget {{ background: {theme.BG}; color: {theme.TEXT}; }}")
        lay = QVBoxLayout(cont)
        lay.setContentsMargins(20, 20, 20, 20)
        label = QLabel("Sense WAV carregada\n\nSelecciona una WAV per activar el visor.")
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        lay.addWidget(label)
        if self._stack.indexOf(cont) < 0:
            self._stack.insertWidget(0, cont)   # pagina 0 = placeholder
        self._stack.setCurrentWidget(cont)
        self.visor_widget = None

    def _detecta_sortida_wav(self, wav):
        if not wav or not os.path.isfile(wav):
            return ""
        sortida = pipeline.carpeta_sortida(wav)
        if os.path.isdir(sortida):
            return sortida
        return ""

    def _carrega_visor(self, wav):
        self._atura_si_sona("recarrega del visor")
        if not wav or not os.path.isfile(wav):
            self.logger.warning("No s'ha pogut carregar la WAV: %s", wav)
            self.visor_ref = None
            self.b_exec.setEnabled(False)
            self.b_guia.setEnabled(False)
            self.b_marker.setEnabled(False)
            self.b_marker_compas.setEnabled(False)
            self._mostra_placeholder_visor()
            return
        try:
            if not self.sortida:
                self.sortida = self._detecta_sortida_wav(wav)
            acords_csv = None
            abc_csv = None
            if self.sortida:
                acords_csv = os.path.join(self.sortida, "acords.csv")
                abc_csv = os.path.join(self.sortida, "estructura_ABC.csv")
                if not os.path.isfile(acords_csv):
                    acords_csv = None
                if not os.path.isfile(abc_csv):
                    abc_csv = None

            if acords_csv is None:
                self.logger.info("Sense resultat processat per %s; obro el visor amb pistes buides", wav)

            self.logger.info("Carregant visor per %s | sortida=%s", wav, self.sortida)
            visor = visor_mod.Visor(
                os.path.abspath(wav),
                acords_csv,
                abc_csv,
                self._bpm_val(),
                self._bpb_val(),
                tempo_fix=self.tempo_fix.isChecked(),
                # La carpeta de sortida del PROJECTE va al constructor: així
                # el visor no desa mai cap CSV a `audio/…` (carpeta derivada
                # del WAV).
                sortida=self.sortida or pipeline.carpeta_sortida(wav),
                offset=self._offset_val(),
                beat_type=self._beat_type_val(),
                bpm_unit=self._bpm_unit_val(),
            )
            self.visor_ref = visor
            self._aplica_beats_guardats(visor)
            visor.metro_click_unit = self._metro_click_unit_val()
            # El visor ha de desar els CSV/export a la carpeta de sortida del
            # PROJECTE (no derivar-la del WAV, que viu a <projecte>/audio/).
            visor.sortida = self.sortida or pipeline.carpeta_sortida(wav)
            visor.canvis.connect(self._marca_dirty)   # edicions → projecte «brut»
            if hasattr(self, "tb_snap"):
                self._canvia_snap()   # reaplica snap/divisió escollits
            self._replica_eina()      # reaplica eina + abast del rang
            # connectem els senyals del visor (icona play/pause + missatges
            # de la caixa d'informacio: desfer/refer...)
            try:
                visor.playStateChanged.disconnect(self._on_play_state)
            except (TypeError, AttributeError):
                pass
            visor.playStateChanged.connect(self._on_play_state)
            try:
                visor.infoMissatge.disconnect(self._missatge_info)
            except (TypeError, AttributeError):
                pass
            visor.infoMissatge.connect(self._missatge_info)
            try:
                visor.loopStateChanged.disconnect(self._on_loop_state)
            except (TypeError, AttributeError):
                pass
            visor.loopStateChanged.connect(self._on_loop_state)
            try:
                visor.timeline.clipSelected.disconnect(self._on_visor_seleccio)
            except (TypeError, AttributeError, RuntimeError):
                pass
            visor.timeline.clipSelected.connect(self._on_visor_seleccio)
            try:
                visor.tempoCanviat.disconnect(self._sincronitza_temps_del_visor)
            except (TypeError, AttributeError, RuntimeError):
                pass
            visor.tempoCanviat.connect(self._sincronitza_temps_del_visor)
            avisos_tempo = getattr(visor, "_avisos_csv_tempo", ())
            if avisos_tempo:
                self._missatge_info(
                    "El mapa CSV de tempo s'ha reparat: "
                    + " ".join(avisos_tempo))
            try:
                visor.velocitatCanviada.disconnect(
                    self._sincronitza_velocitat)
            except (TypeError, AttributeError, RuntimeError):
                pass
            visor.velocitatCanviada.connect(self._sincronitza_velocitat)
            self._sincronitza_velocitat(
                getattr(visor, "velocitat", 1.0))
            self._on_loop_state(getattr(visor, "loop_on", False))
            self.visor_widget = visor.centralWidget()
            self.visor_widget.setParent(self._stack)
            if self._stack.indexOf(self.visor_widget) < 0:
                self._stack.addWidget(self.visor_widget)   # pagina 1 = visor
            self._stack.setCurrentWidget(self.visor_widget)
            self.visor_widget.show()
            self.b_exec.setEnabled(True)     # hi ha WAV -> es pot analitzar
            self.b_guia.setEnabled(True)
            self.b_marker.setEnabled(True)
            self.b_marker_compas.setEnabled(True)
            # Si el visor ja porta MODEL (projecte obert, o anàlisi feta), les
            # exportacions també han d'estar disponibles. Abans només
            # s'activaven al final d'una ANÀLISI → OBRIR UN PROJECTE deixava
            # «Exporta WAV's»/«Exporta partitura» apagats i no feien res.
            self._habilita_export()
            self._actualitza_metro_ui()
            if hasattr(visor, "cont_transport"):
                # el transport viu a la barra de la finestra
                visor.cont_transport.setVisible(False)
            if hasattr(visor, "registre"):
                # el log viu al tauler plegable de la finestra (pas 3)
                visor.registre.setVisible(False)
            visor._embedded = True
            visor.setVisible(False)
            visor.close()
            # Els camps BPM/compàs han de mostrar el transport fins que es
            # seleccione un tram de tempo concret (2B).
            self._sincronitza_temps_del_visor()
        except Exception:  # noqa: BLE001
            self.logger.exception("Crash en carregar el visor per %s", wav)
            self.registra(f"Visor ERROR: {traceback.format_exc()}")
            self.visor_ref = None
            self._mostra_placeholder_visor()

    def _habilita_export(self):
        """Activa «Exporta WAV's»/«Exporta partitura» si el visor té MODEL.

        El model pot venir d'una anàlisi d'aquesta sessió **o** d'un projecte
        obert (els CSV ja hi són) → en tots dos casos s'ha de poder exportar.
        """
        vr = getattr(self, "visor_ref", None)
        te_model = vr is not None and bool(getattr(vr, "acords", None)
                                           or getattr(vr, "seccions", None))
        self.b_export.setEnabled(te_model)
        self.b_export_part.setEnabled(te_model)
        accio = getattr(self, "a_exporta_audio", None)
        if accio is not None:
            accio.setEnabled(bool(self._wav_treball()))

    def _wav_treball(self):
        """Ruta de la còpia WAV de treball del projecte (o del WAV obert)."""
        if self.projecte is not None:
            ruta = self.projecte.ruta_audio()
            if ruta and os.path.isfile(ruta):
                return ruta
        ruta = self.wav_edit.text().strip()
        return ruta if ruta and os.path.isfile(ruta) else ""

    def _posa_nom_editor(self, nom):
        """El panell «Tipus d'acord» vol escriure `nom` a la casella de l'editor.

        Només l'omple (el visor també hi posa el focus); **no aplica** res.
        """
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.avisa_info("Auto Chords", "Obre un tema i tria un acord abans "
                                           "de fer servir el panell dels tipus.")
            return
        vr.posa_nom_editor(nom)

    def _escolta_notes(self, notes, preset=""):
        """Audició d'un tipus d'acord (e-piano) demanada pel panell.

        Ho toca el visor amb un motor efímer (`Visor.toca_notes`): no toca la
        reproducció de la cançó i mai aixeca (si l'àudio falla, s'avisa).
        """
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.avisa_info("Tipus d'acord",
                            "Obre un tema abans d'escoltar l'acord.")
            return
        if not vr.toca_notes(notes, preset=preset or None):
            self.avisa("Tipus d'acord",
                       "No s'ha pogut reproduir l'àudio (mira el log).")

    def _atura_si_sona(self, motiu):
        """Atura el reproductor abans d'una operacio pesada (no te sentit
        continuar sonant mentre s'analitza o es redibuixa el visor)."""
        vr = getattr(self, "visor_ref", None)
        if vr is not None and getattr(vr, "sona", False):
            self.registra(f"⏸ aturo el reproductor ({motiu})")
            vr.play_stop()

    def _assegura_wav(self, ruta):
        """Si `ruta` no és un WAV PCM 16 bits, el converteix amb ffmpeg.

        Retorna la ruta del WAV de treball (o `ruta` si ja ho era).
        """
        if ffmpeg.es_wav_pcm16(ruta):
            return ruta
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.registra(f"Convertint «{os.path.basename(ruta)}» a WAV "
                          "(ffmpeg)…")
            wav = ffmpeg.converteix_a_wav(ruta, self.registra)
        finally:
            QApplication.restoreOverrideCursor()
        return wav

    # ── Gestió de projectes (carpeta autocontinguda, com un DAW) ────────────
    RECENTS_MAX = 8

    def _recents_path(self):
        return os.path.join(config.DADES_DIR, "recents.json")

    def _carrega_recents(self):
        # En la suite (AUTO_CHORDS_TEST=1) no es llig la llista de l'usuari:
        # si no, un test podria obrir el projecte d'un altre.
        if os.environ.get("AUTO_CHORDS_TEST"):
            return []
        try:
            with open(self._recents_path(), encoding="utf-8") as f:
                d = json.load(f)
            return [str(x) for x in d if isinstance(x, str)][:self.RECENTS_MAX]
        except (OSError, ValueError):
            return []

    def _guarda_recents(self):
        try:
            pipeline.escriu_atomic(
                self._recents_path(),
                lambda f: json.dump(self.recents, f, ensure_ascii=False,
                                    indent=2))
        except OSError:
            pass

    def _afegeix_recent(self, ruta_acproj):
        ruta_acproj = os.path.abspath(ruta_acproj)
        self.recents = ([ruta_acproj]
                        + [r for r in self.recents if r != ruta_acproj])
        self.recents = self.recents[:self.RECENTS_MAX]
        self._guarda_recents()

    def _actualitza_titol(self):
        base = (f"{self.projecte.nom} — Auto Chords" if self.projecte is not None
                else "Auto Chords")
        self.setWindowTitle(base + (" *" if self.dirty else ""))

    def _marca_dirty(self, *_):
        # Els canvis programàtics de la barra (sincronitzar BPM/compàs amb el
        # clip de tempo seleccionat) no han de marcar el projecte com a brut.
        if getattr(self, "_actualitzant_temps", False):
            return
        if not self.dirty:
            self.dirty = True
            self._actualitza_titol()

    def _te_canvis(self):
        return bool(self.dirty)

    def _interactiu(self):
        """Hi ha un usuari que pugui respondre un diàleg modal?

        Amb la plataforma Qt **`offscreen`** (tests i CI sense pantalla) NO n'hi
        ha: un `QMessageBox` modal s'encallaria — i a Windows, directament, fa
        **«access violation»** (crash natiu; vegeu `tests/test_avis_no_modal.py`).
        En aquest cas les confirmacions responen amb el valor **segur** i ho
        deixen al log, en comptes d'obrir un diàleg.
        """
        app = QApplication.instance()
        return app is not None and app.platformName() != "offscreen"

    def _confirma_descartar(self):
        """Prompt Desa/Descarta/Cancel·la. True = podem continuar.

        Si es tria «Desa» i el desat FALLA, es retorna False (no es continua:
        mai tancar/sobreescriure perdent feina).
        """
        if not self._interactiu():
            self.registra("sense sessió interactiva (offscreen): es continua "
                          "(la cançó —acords i estructura— ja és al CSV)")
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Canvis sense desar")
        box.setText("El projecte té canvis sense desar. Vols desar-los abans "
                    "de continuar?")
        box.setInformativeText(
            "La cançó (acords i estructura) es desa automàticament; el que no "
            "es desa són els ajustos del projecte (tempo, compàs, mode, vista).")
        b_desa = box.addButton("Desa", QMessageBox.AcceptRole)
        box.addButton("Descarta", QMessageBox.DestructiveRole)
        b_canc = box.addButton("Cancel·la", QMessageBox.RejectRole)
        box.setDefaultButton(b_desa)
        box.exec_()
        clic = box.clickedButton()
        if clic is None or clic is b_canc:
            return False
        if clic is b_desa:
            return self._desa_projecte()      # False si el desat ha fallat
        return True

    def _pot_descartar(self):
        return (not self._te_canvis()) or self._confirma_descartar()

    def _dades_projecte(self):
        # El document desa el TEMPO DEL TRANSPORT (tram 0), no el del clip de
        # tempo que estiga seleccionat en eixe moment (2B).
        vr = getattr(self, "visor_ref", None)
        if vr is not None and vr.tempo_objectiu() > 0:
            bpm = float(getattr(vr, "bpm", 120.0))
            bpb = int(getattr(vr, "bpb", 4) or 4)
            den = int(getattr(vr, "beat_type", 4) or 4)
            offset = float(getattr(vr, "offset", 0.0) or 0.0)
        else:
            # Sense clip de tempo seleccionat, la barra ÉS el transport: es
            # desa el que hi ha escrit (encara que no s'haja premut Enter).
            bpm, bpb = self._bpm_val(), self._bpb_val()
            den, offset = self._beat_type_val(), self._offset_val()
        return {
            "tempo": {"bpm": bpm, "bpb": bpb,
                      "offset": offset,
                      "fix": self.tempo_fix.isChecked(),
                      "compas": f"{bpb}/{den}",
                      "unit": self._bpm_unit_val(),
                      "metro_unit": self._metro_click_unit_val()},
            "opcions": self.opcions,
        }

    def _demana_ubicacio_projecte(self, base_dir, nom_suggerit, titol):
        """Pregunta ON crear/desar el projecte. Retorna la carpeta (o `None`).

        `base_dir` = carpeta on s'obre el diàleg; `nom_suggerit` = nom sense
        extensió. El resultat és la CARPETA del projecte (la que conté el
        `.acproj`), perquè un projecte és una carpeta autocontinguda.
        """
        suggerit = os.path.join(base_dir,
                                str(nom_suggerit).strip() + projecte.EXT)
        ruta, _ = QFileDialog.getSaveFileName(
            self, titol, suggerit, "Projecte AUTO CHORDS (*.acproj)")
        if not ruta:
            return None
        if not ruta.endswith(projecte.EXT):
            ruta += projecte.EXT
        nom = os.path.splitext(os.path.basename(ruta))[0]
        return os.path.join(os.path.dirname(ruta), nom)

    def _activa_projecte(self, p):
        """Carrega un projecte a la finestra (àudio, tempo, visor, títol)."""
        self._atura_si_sona("canvi de projecte")
        self.projecte = p
        self.sortida = p.carpeta
        wav = p.ruta_audio()
        self.wav_edit.setText(wav)
        tempo = p.dades.get("tempo") or {}
        unit = bpm_unit_mod.normalitza(tempo.get("unit"))
        idx_unit = self.cb_bpm_unit.findData(unit)
        if idx_unit >= 0:
            self.cb_bpm_unit.blockSignals(True)
            self.cb_bpm_unit.setCurrentIndex(idx_unit)
            self.cb_bpm_unit.blockSignals(False)
        self._bpm_unit_anterior = unit
        self._posa_bpm_quarter(float(tempo.get("bpm", 120.0)))
        munit = tempo.get("metro_unit", "auto")
        idx_m = self.cb_metro_unit.findData(munit)
        if idx_m >= 0:
            self.cb_metro_unit.blockSignals(True)
            self.cb_metro_unit.setCurrentIndex(idx_m)
            self.cb_metro_unit.blockSignals(False)
        compas = tempo.get("compas")
        # Format COMPLET (4/4, no «4»): un «4» sol sembla el compàs denormalitzat
        # i confon; el parser accepta els dos, però el camp sempre el mostra bé.
        self.bpb.setText(str(compas) if compas
                         else f"{int(tempo.get('bpb', 4))}/4")
        self._posa_offset_camp(float(tempo.get("offset", 0.0)))
        self.tempo_fix.setChecked(bool(tempo.get("fix", False)))
        self._canvia_mode_temps(bool(tempo.get("fix", False)))
        if isinstance(p.dades.get("opcions"), dict) and p.dades["opcions"]:
            self.opcions = p.dades["opcions"]
        if not p.audio_present():
            self.avisa("Auto Chords", f"Falta l'àudio del projecte:\n{wav}")
        if wav and os.path.isfile(wav):
            try:
                self._actualitza_info_wav(wav)
            except Exception:  # noqa: BLE001
                pass
            self._carrega_visor(wav)
        self.dirty = False
        self._actualitza_titol()
        self._afegeix_recent(p.ruta_acproj)
        self.registra(f"Projecte obert: {p.carpeta}")
        self._engega_autosave()
        self._marca_sessio()

    def _obre_ruta_projecte(self, ruta):
        if not self._pot_descartar():
            return
        try:
            p = projecte.Projecte.obre(ruta)
        except projecte.ProjecteError as e:
            self.avisa("Auto Chords", f"No s'ha pogut obrir el projecte:\n{e}")
            return
        self._activa_projecte(p)

    def _obre_projecte(self):
        if not self._pot_descartar():
            return
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Obre un projecte", "", "Projecte AUTO CHORDS (*.acproj)")
        if ruta:
            self._obre_ruta_projecte(ruta)

    def _obre_recent(self):
        self.recents = [r for r in self.recents if os.path.isfile(r)]
        if not self.recents:
            self.avisa_info("Auto Chords", "No hi ha projectes recents.")
            return
        etiqueta, ok = QInputDialog.getItem(
            self, "Projectes recents", "Obre un projecte recent:",
            self.recents, 0, False)
        if ok and etiqueta:
            self._obre_ruta_projecte(etiqueta)

    def _desa_projecte(self):
        """Desa el projecte. Retorna True si s'ha desat (False si ha fallat)."""
        if self.projecte is None:
            self.avisa_info("Auto Chords", "No hi ha cap projecte obert.")
            return False
        self._refresca_dades_projecte()
        try:
            self.projecte.desa()
        except OSError as e:
            self.avisa("Auto Chords", f"No s'ha pogut desar:\n{e}")
            return False
        self.dirty = False
        self._actualitza_titol()
        self._afegeix_recent(self.projecte.ruta_acproj)
        self.registra(f"Projecte desat: {self.projecte.ruta_acproj}")
        return True

    def _desa_projecte_com(self):
        if self.projecte is None:
            self.avisa_info("Auto Chords", "No hi ha cap projecte obert.")
            return
        desti = self._demana_ubicacio_projecte(
            os.path.dirname(self.projecte.carpeta), self.projecte.nom,
            "Desa el projecte com")
        if not desti:
            return
        if os.path.abspath(desti) == self.projecte.carpeta:
            self._desa_projecte()          # mateix lloc → «Desa» normal
            return
        self._refresca_dades_projecte()
        self.projecte.desa()
        try:
            nou = self.projecte.duplica(desti)
        except (projecte.ProjecteError, OSError) as e:
            self.avisa("Auto Chords", f"No s'ha pogut desar com:\n{e}")
            return
        self.projecte = nou
        self.sortida = nou.carpeta
        self.dirty = False
        self._actualitza_titol()
        self._afegeix_recent(nou.ruta_acproj)
        self.registra(f"Projecte desat com: {nou.carpeta}")

    def _desa_copia(self):
        """Desa una CÒPIA sense canviar el projecte actiu."""
        if self.projecte is None:
            self.avisa_info("Auto Chords", "No hi ha cap projecte obert.")
            return
        desti = self._demana_ubicacio_projecte(
            os.path.dirname(self.projecte.carpeta),
            self.projecte.nom + "_còpia", "Desa una còpia a")
        if not desti:
            return
        self._refresca_dades_projecte()
        self.projecte.desa()
        try:
            self.projecte.duplica(desti)
        except (projecte.ProjecteError, OSError) as e:
            self.avisa("Auto Chords", f"No s'ha pogut desar la còpia:\n{e}")
            return
        self.registra(f"Còpia desada a: {desti}")

    def _reverteix(self):
        """Torna el projecte a l'últim estat desat.

        No es demana confirmació: l'acció s'ha demanat explícitament i el
        descart és el seu significat.
        """
        if self.projecte is None:
            self.avisa_info("Auto Chords", "No hi ha cap projecte obert.")
            return
        if self._te_canvis() and not self._confirma_descartar():
            return
        try:
            p = projecte.Projecte.obre(self.projecte.ruta_acproj)
        except projecte.ProjecteError as e:
            self.avisa("Auto Chords", f"No s'ha pogut revertir:\n{e}")
            return
        self._activa_projecte(p)
        self.registra("Projecte reverit a l'últim desat.")

    # -- Autosave + sessió (recuperació després d'un tancament brusc) --------
    AUTOSAVE_MS = 60000

    def _refresca_dades_projecte(self):
        """Passa el tempo/opcions dels widgets al document en memòria."""
        if self.projecte is None:
            return
        d = self._dades_projecte()
        self.projecte.dades["tempo"] = d["tempo"]
        self.projecte.dades["opcions"] = d["opcions"]

    def _desa_meta_silencios(self):
        """Desa el document del projecte (tempo/offset/opcions) sense avisos."""
        if getattr(self, "projecte", None) is None:
            return
        try:
            self._refresca_dades_projecte()
            self.projecte.desa()
        except OSError as e:
            self.registra(f"no s'ha pogut desar el projecte: {e}")

    def _engega_autosave(self):
        if getattr(self, "_autosave", None) is None:
            self._autosave = QTimer(self)
            self._autosave.setInterval(self.AUTOSAVE_MS)
            self._autosave.timeout.connect(self._fes_autosave)
        self._autosave.start()

    def _fes_autosave(self):
        """Còpia de seguretat periòdica a `backup/` (només si hi ha canvis NOUS)."""
        if self.projecte is None or not self.dirty:
            return
        try:
            self._refresca_dades_projecte()
            dest = self.projecte.fes_backup()
            if dest:
                self.registra(f"autosave: còpia creada "
                              f"({len(self.projecte.backups())} guardades)")
        except OSError as e:
            self.registra(f"autosave ERROR: {e}")

    def _sessio_path(self):
        return os.path.join(config.DADES_DIR, "sessio.json")

    def _marca_sessio(self):
        """Marca que hi ha una sessió oberta (per detectar un crash)."""
        if self.projecte is None:
            return
        try:
            pipeline.escriu_atomic(self._sessio_path(), lambda f: json.dump(
                {"acproj": self.projecte.ruta_acproj, "pid": os.getpid(),
                 "inic": time.strftime("%Y-%m-%dT%H:%M:%S")},
                f, ensure_ascii=False, indent=2))
        except OSError:
            pass

    def _neteja_sessio(self):
        try:
            os.remove(self._sessio_path())
        except OSError:
            pass

    def _sessio_pendent(self):
        """`acproj` de la sessió inacabada (i neteja el marcador), o `None`."""
        try:
            with open(self._sessio_path(), encoding="utf-8") as f:
                s = json.load(f)
        except (OSError, ValueError):
            return None
        acproj = s.get("acproj") if isinstance(s, dict) else None
        self._neteja_sessio()          # no ho tornis a oferir
        if not acproj or not os.path.isfile(acproj):
            return None
        return acproj

    def _comprova_recuperacio(self):
        """A l'arrencada: si la sessió anterior no es va tancar bé, ofereix-la.

        Es crida NOMÉS des de l'entrada real de l'app (`main()`), mai des de
        `Finestra.__init__` — així els tests no disparen cap diàleg.
        """
        acproj = self._sessio_pendent()
        if not acproj:
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle("Recupera la sessió")
        box.setText("Sembla que l'app es va tancar inesperadament.")
        box.setInformativeText(f"Vols reobrir el darrer projecte?\n{acproj}")
        b_ok = box.addButton("Reobre", QMessageBox.AcceptRole)
        box.addButton("Descarta", QMessageBox.RejectRole)
        box.setDefaultButton(b_ok)
        box.exec_()
        if box.clickedButton() is b_ok:
            self._obre_ruta_projecte(acproj)

    def tria_wav(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Tria un àudio", "", self._filtre_audio())
        if not ruta:
            return
        self._obri_des_de_wav(ruta)

    def _projecte_associat(self, wav):
        """Projecte ja associat a aquest àudio, o `None`.

        1. La carpeta germana `AUTOCHORDS_<nom>/` (convenció de l'app).
        2. Si no hi és, els **recents**: un projecte desat en un altre lloc el
           `audio/` del qual es diu igual que aquest fitxer.
        """
        carp = projecte.carpeta_autochords(wav)
        if carp:
            try:
                return projecte.Projecte.obre(carp)
            except projecte.ProjecteError:
                pass
        base = os.path.basename(wav).lower()
        for ruta in list(self.recents or ()):
            try:
                p = projecte.Projecte.obre(ruta)
            except projecte.ProjecteError:
                continue
            try:
                if os.path.basename(p.ruta_audio()).lower() == base:
                    return p
            except (OSError, ValueError):
                continue
        return None

    def _pregunta_projecte_existent(self, p):
        """Carrega / sobreescriu / cancel·la el projecte que ja té aquest àudio.

        Retorna `"carrega"`, `"sobreescriu"` o `None` (cancel·la). Sense sessió
        interactiva (tests, `offscreen`) s'escull el camí **no destructiu**.
        """
        if not self._interactiu():
            self.registra("projecte existent: sense sessió interactiva → es "
                          "carrega (no es destrueix res)")
            return "carrega"
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle("Aquest àudio ja té projecte")
        box.setText("Ja hi ha un projecte associat a aquest àudio.")
        box.setInformativeText(
            f"{p.carpeta}\n\n"
            "Si el carregues, mana el projecte (el seu àudio, els seus acords i "
            "el seu tempo).\n"
            "Si el sobreescrius, la carpeta actual va a la PAPERERA i es crea "
            "de zero amb aquest àudio.")
        b_car = box.addButton("Carrega el projecte", QMessageBox.AcceptRole)
        b_sov = box.addButton("Sobreescriu (esborra'l)",
                              QMessageBox.DestructiveRole)
        box.addButton("Cancel·la", QMessageBox.RejectRole)
        box.setDefaultButton(b_car)
        box.exec_()
        clic = box.clickedButton()
        if clic is b_car:
            return "carrega"
        if clic is b_sov:
            return "sobreescriu"
        return None

    def _obri_des_de_wav(self, ruta):
        """Obre un àudio: reutilitza el projecte si ja n'hi ha, o en crea un."""
        if not self._pot_descartar():
            return

        # Un àudio que JA té projecte: l'usuari decideix (mai un error).
        previ = self._projecte_associat(ruta)
        desti = None
        if previ is not None:
            tria = self._pregunta_projecte_existent(previ)
            if tria is None:
                return
            if tria == "carrega":
                self._activa_projecte(previ)
                self.registra(f"Projecte existent carregat: {previ.carpeta}")
                return
            # SOBREESCRIURE: la carpeta vella a la paperera (recuperable) i es
            # recrea allí mateix, sense restes de l'anterior.
            desti = previ.carpeta
            if not plataforma.a_la_paperera(desti):
                self.avisa(
                    "Auto Chords",
                    "No s'ha pogut enviar el projecte actual a la paperera, "
                    "així que NO se sobreescriu res.\n"
                    f"Projecte: {desti}")
                return
            self.registra(f"Projecte anterior a la paperera: {desti}")

        if not desti:
            # Pregunta ON crear el projecte (per defecte, al costat del WAV).
            base = os.path.splitext(os.path.basename(ruta))[0]
            desti = self._demana_ubicacio_projecte(
                os.path.dirname(ruta), pipeline.PREFIX_SORTIDA + base,
                "Crea el projecte")
            if not desti:
                return
        # Un WAV NOU no ha d'heretar el BPM del tema anterior (OC-6/415).
        if self.bpm.text().strip() not in ("", "120.0", "120"):
            self.registra("WAV nou → BPM reiniciat a 120.0 "
                          "(detecta'l o posa'l a mà)")
            self._posa_bpm_quarter(120.0)
        # Migració: si hi ha una AUTOCHORDS_<nom>/ vella al costat del WAV,
        # n'importem els CSVs (i, si el destí és la mateixa carpeta, in situ).
        antic = projecte.carpeta_autochords(ruta)
        ca = os.path.join(antic, projecte.NOM_CSV_ACORDS) if antic else None
        sa = os.path.join(antic, projecte.NOM_CSV_ESTRUCTURA) if antic else None
        in_situ = bool(antic) and os.path.abspath(desti) == os.path.abspath(antic)
        if not ffmpeg.es_wav_pcm16(ruta):
            self.registra(f"Convertint «{os.path.basename(ruta)}» a WAV "
                          "dins del projecte (ffmpeg)…")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        error = None
        try:
            p = projecte.Projecte.crea(
                desti, ruta, nom=os.path.basename(desti),
                bpm=self._bpm_val(), bpb=self._bpb_val(),
                offset=self._offset_val(), fix=self.tempo_fix.isChecked(),
                opcions=self.opcions, compas=self.bpb.text().strip(),
                csv_acords=ca if ca and os.path.isfile(ca) else None,
                csv_estructura=sa if sa and os.path.isfile(sa) else None,
                permet_existent=in_situ, log=self.registra)
        except (projecte.ProjecteError, OSError) as e:
            self.logger.exception("No s'ha pogut crear el projecte des de %s",
                                  ruta)
            error = e
        finally:
            QApplication.restoreOverrideCursor()
        if error is not None:
            self.avisa("Auto Chords", f"No s'ha pogut crear el projecte:\n{error}")
            return
        self._activa_projecte(p)
        self.registra(f"Projecte creat a: {desti}")

    def _acc_visor(self, nom, *args):
        """Crida un mètode del visor (o una acció derivada) si n'hi ha."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return
        if nom == "menys10":
            vr.ves_a(vr.pos - 10)
        elif nom == "mes10":
            vr.ves_a(vr.pos + 10)
        else:
            getattr(vr, nom)(*args)

    def _sincronitza_velocitat(self, f):
        """Posa el selector de velocitat de la barra al valor del visor."""
        c = getattr(self, "cmb_vel_tb", None)
        if c is None:
            return
        try:
            i = c.findData(round(float(f), 4))
        except (TypeError, ValueError):
            return
        if i < 0:
            return
        c.blockSignals(True)
        c.setCurrentIndex(i)
        c.blockSignals(False)

    def _crea_transport(self, bar):
        def boto(text, tip, accio, checkable=False, icona=None):
            b = QPushButton("" if icona else text)
            if icona:
                b.setIcon(icones.ico(icona, 16))
                b.setIconSize(icones.pm_mida(16))
            b.setToolTip(tip)
            if checkable:
                b.setCheckable(True)
            b.clicked.connect(accio)
            bar.addWidget(b)
            return b

        self.b_play_tb = boto("▶", "Reprodueix / atura  (Espai)",
                              lambda: self._acc_visor("play_stop"),
                              icona="play")
        boto("⏹", "Atura i torna a l'inici",
             lambda: self._acc_visor("stop_inici"), icona="square")
        boto("−10s", "Endarrere 10 s",
             lambda: self._acc_visor("menys10"), icona="rewind")
        boto("+10s", "Endavant 10 s",
             lambda: self._acc_visor("mes10"), icona="fast-forward")
        bar.addSeparator()
        boto("A⟨", "Marca inici de loop (A)",
             lambda: self._acc_visor("marca_A"), icona="arrow-left-to-line")
        boto("⟩B", "Marca fi de loop (B)",
             lambda: self._acc_visor("marca_B"), icona="arrow-right-to-line")
        self.tb_loop = boto("🔁", "Activa/desactiva el loop A-B",
                            lambda: None, checkable=True, icona="repeat-2")
        self.tb_loop.clicked.connect(
            lambda: self._acc_visor("set_loop", self.tb_loop.isChecked()))
        # Neteja el loop (treu A i B), al costat del botó del loop.
        self.tb_neteja_loop = boto("", "Neteja el loop (treu A i B)",
                                   self._neteja_loop, icona="x")
        bar.addSeparator()
        boto("🔍−", "Allunya el zoom", lambda: self._acc_visor("zoom", 2.0),
             icona="zoom-out")
        boto("🔍+", "Apropa el zoom", lambda: self._acc_visor("zoom", 0.5),
             icona="zoom-in")
        boto("Tot", "Zoom total (veure-ho tot)",
             lambda: self._acc_visor("zoom_tot"), icona="maximize")
        boto("", "Zoom a la selecció (ajusta la vista als clips seleccionats)",
             lambda: self._acc_visor("zoom_seleccio"), icona="focus")
        self.tb_mut = boto("🔇", "Silencia / reactiva el so",
                           lambda: None, checkable=True, icona="volume-x")
        self.tb_mut.setObjectName("mute")
        self.tb_mut.clicked.connect(
            lambda: self._acc_visor("set_mut", self.tb_mut.isChecked()))
        # Velocitat de reproducció (0,5–3×, to mantingut): el visor la prepara
        # i la barra només la manega; `velocitatCanviada` manté els dos
        # selectors sincronitzats.
        self.cmb_vel_tb = QComboBox()
        for v in (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0):
            self.cmb_vel_tb.addItem(f"{v:g}×", float(v))
        self.cmb_vel_tb.setCurrentIndex(2)
        self.cmb_vel_tb.setMaximumWidth(80)
        self.cmb_vel_tb.setToolTip(
            "Velocitat de reproducció (0,5–3×) amb el to mantingut (ffmpeg "
            "atempo, com el VLC). El cursor, el loop i el metrònom es mantenen "
            "alineats; el primer cop a cada velocitat pot trigar uns segons.")
        self.cmb_vel_tb.currentIndexChanged.connect(
            lambda _i: self._acc_visor("set_velocitat",
                                       self.cmb_vel_tb.currentData()))
        bar.addWidget(self.cmb_vel_tb)
        bar.addSeparator()
        # metrònom: només en mode BPM · compàs (vegeu _actualitza_metro_ui)
        self.b_metro = QPushButton()
        self.b_metro.setIcon(icones.ico("metronome"))
        self.b_metro.setObjectName("metro")
        self.b_metro.setCheckable(True)
        self.b_metro.setToolTip("Metrònom (només en mode BPM · compàs)")
        self.b_metro.clicked.connect(self._toggle_metro)
        bar.addWidget(self.b_metro)
        self.vol_metro = QSlider(Qt.Horizontal)
        self.vol_metro.setRange(0, 100)
        self.vol_metro.setValue(60)
        self.vol_metro.setMaximumWidth(90)
        self.vol_metro.setToolTip("Volum del clic del metrònom (%)")
        self.vol_metro.valueChanged.connect(self._canvia_vol_metro)
        bar.addWidget(self.vol_metro)
        self.cb_metro = QComboBox()
        for _et, _val in (("Auto", "auto"), ("Compàs", "compas"),
                          ("Temps", "temps"), ("Grup", "grup")):
            self.cb_metro.addItem(_et, _val)
        self.cb_metro.setCurrentIndex(0)
        self.cb_metro.setMaximumWidth(82)
        self.cb_metro.setToolTip(
            "Patró del metrònom: Auto (temps + accents de compàs i grup), "
            "Compàs (només el primer temps), Temps (sense accents de grup) "
            "o Grup (només compàs i inicis de grup).")
        self.cb_metro.currentIndexChanged.connect(self._canvia_mode_metro)
        bar.addWidget(self.cb_metro)
        bar.addWidget(QLabel("Clic:"))
        self.cb_metro_unit = QComboBox()
        self.cb_metro_unit.addItem("Denominador", "auto")
        for _clau, _et in bpm_unit_mod.opcions():
            self.cb_metro_unit.addItem(_et, _clau)
        self.cb_metro_unit.setCurrentIndex(0)
        self.cb_metro_unit.setMaximumWidth(110)
        self.cb_metro_unit.setToolTip(
            "Unitat de clic del metrònom: auto (denominador), negra, "
            "negra amb punt, corxera o blanca.")
        self.cb_metro_unit.currentIndexChanged.connect(
            self._canvia_metro_click_unit)
        bar.addWidget(self.cb_metro_unit)
        bar.addSeparator()
        # Quantitza: just abans del Snap (petició de l'operador). Recicla el
        # lloc de l'antic «Mode fàcil».
        self.b_quantitza = QPushButton("Quantitza")
        self.b_quantitza.setObjectName("secundari")
        self.b_quantitza.setToolTip(
            "Quantitza els inicis dels clips a la graella. Abast: tot, "
            "selecció, només acords o només estructura. No toca BPM, compàs "
            "ni el cru; es pot desfer i refer.")
        self.b_quantitza.clicked.connect(self._quantitza_ui)
        bar.addWidget(self.b_quantitza)
        self.b_quantitza_bpm = QPushButton("BPM 0,1")
        self.b_quantitza_bpm.setObjectName("secundari")
        self.b_quantitza_bpm.setMaximumWidth(86)
        self.b_quantitza_bpm.setToolTip(
            "Quantitza el BPM dels clips normals a 1 decimal i re-encaixa "
            "les fronteres amb beats sencers. Els rubatos no es "
            "quantitzen.")
        self.b_quantitza_bpm.clicked.connect(self._quantitza_bpm_ui)
        self.barra_accions.addWidget(self.b_quantitza_bpm)
        self.barra_accions.addSeparator()
        self.barra_accions.addWidget(QLabel("Graella:"))
        # Graella configurable: interruptor de snap + divisió (habilita el nudge fi).
        self.tb_snap = boto("Snap", "Interruptor de snap (encaixar a la graella)",
                            self._canvia_snap, checkable=True)
        self.tb_snap.setChecked(True)
        self.cb_graella = QComboBox()
        self.cb_graella.setToolTip("Divisió de la graella: grid visual i snap")
        for et, val in (
                ("Beats QM", "qm_beats"),
                ("Auto (zoom)", ""), ("Negra (1/4)", "negra"),
                ("Corxera (1/8)", "corxera"),
                ("Semicorxera (1/16)", "semicorxera"),
                ("Fusa (1/32)", "fusa"),
                ("Treset de negra (2/3)", "treset_negra"),
                ("Treset de corxera (1/3)", "treset_corxera"),
                ("Treset de semicorxera (1/6)", "treset_semicorxera"),
                ("1 compàs", "compas1"), ("2 compassos", "compas2"),
                ("4 compassos", "compas4"), ("6 compassos", "compas6"),
                ("8 compassos", "compas8"), ("12 compassos", "compas12"),
                ("16 compassos", "compas16"), ("24 compassos", "compas24"),
                ("32 compassos", "compas32"), ("48 compassos", "compas48"),
                ("64 compassos", "compas64")):
            self.cb_graella.addItem(et, val)
        self.cb_graella.currentIndexChanged.connect(self._canvia_snap)
        self.barra_accions.addWidget(self.cb_graella)
        self.barra_accions.addSeparator()
        # Commutador d'EINA del timeline: «intel·ligent» (per defecte; la fletxa
        # s'adapta al que hi ha sota) o «marc» (arrossegar dibuixa un rectangle
        # de selecció i no mou clips). Viu aquí, darrere del snap, perquè és on
        # es decideix com respon el ratolí a la graella.
        self.b_eina = QPushButton("Eina: intel·ligent")
        self.b_eina.setObjectName("secundari")
        self.b_eina.setCheckable(True)
        self.b_eina.setChecked(False)          # intel·ligent = per defecte
        self.b_eina.setToolTip(
            "Eina del timeline (també al menú Selecciona i amb la tecla E):\n"
            "· intel·ligent: la fletxa s'adapta (mou/redimensiona clips, "
            "Shift+clic = rang, regla = loop).\n"
            "· selecció: arrossega per dibuixar un rectangle i queda "
            "seleccionat "
            "tot el que hi SONA a dins (només les pistes que cobreixi).")
        self.b_eina.toggled.connect(self._canvia_eina)
        self.barra_accions.addWidget(self.b_eina)

    def _canvia_snap(self):
        """Aplica l'interruptor de snap + la divisió de graella al visor."""
        vr = getattr(self, "visor_ref", None)
        if vr is None or not hasattr(self, "tb_snap"):
            return
        mode = self.cb_graella.currentData() or ""
        if mode == "qm_beats":
            info = getattr(self, "_beats_actuals", None)
            if not info:
                info = (getattr(getattr(self, "projecte", None), "dades", {})
                        .get("analisi_beats"))
            beats = (info or {}).get("beats") if isinstance(info, dict) else []
            vr.set_snap_beats(beats or [])
            if not beats:
                self.registra("Snap QM: no hi ha beats detectats.")
        vr.set_snap(on=self.tb_snap.isChecked(), divisio=mode)

    def _toggle_metro(self, on=None):
        """Activa/desactiva el metrònom (sincronitza botó i acció)."""
        if on is None:      # clicat des de l'acció de menú
            on = self.a_metro.isChecked()
        self.b_metro.setChecked(bool(on))
        self.a_metro.setChecked(bool(on))
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            vr.set_metro(bool(on))

    def _canvia_vol_metro(self, v):
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            vr._canvia_vol_metro(int(v))

    def _canvia_mode_metro(self, _idx=None):
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            vr.set_metro_mode(self.cb_metro.currentData())

    def _metro_click_unit_val(self):
        cb = getattr(self, "cb_metro_unit", None)
        return cb.currentData() if cb is not None else "auto"

    def _canvia_metro_click_unit(self, _idx=None):
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return
        if not vr.set_metro_click_unit(self._metro_click_unit_val()):
            idx = self.cb_metro_unit.findData(
                getattr(vr, "metro_click_unit", "auto"))
            if idx >= 0:
                self.cb_metro_unit.blockSignals(True)
                self.cb_metro_unit.setCurrentIndex(idx)
                self.cb_metro_unit.blockSignals(False)

    def _actualitza_metro_ui(self):
        """El metrònom només està disponible en mode BPM · compàs."""
        vr = getattr(self, "visor_ref", None)
        disponible = vr is not None and vr.metro_disponible()
        for w in (self.b_metro, self.vol_metro, self.cb_metro,
                  self.cb_metro_unit, self.a_metro):
            w.setEnabled(disponible)
        if not disponible:
            # en mode Lliure: desmarcat i amb tooltip explicatiu
            self.b_metro.setChecked(False)
            self.a_metro.setChecked(False)
            tip = "Només disponible en mode BPM · compàs"
            self.b_metro.setToolTip(tip)
            self.vol_metro.setToolTip(tip)
            self.cb_metro.setToolTip(tip)
            self.cb_metro_unit.setToolTip(tip)
            self.a_metro.setToolTip(tip)
        else:
            self.b_metro.setToolTip("Metrònom")
            self.vol_metro.setToolTip("Volum del clic del metrònom (%)")
            self.cb_metro.setToolTip(
                "Patró del metrònom: Auto, Compàs, Temps o Grup")
            self.cb_metro_unit.setToolTip(
                "Unitat de clic: auto (denominador), negra, negra amb punt, "
                "corxera o blanca")
            self.a_metro.setToolTip("Clic de metrònom")
            idx_u = self.cb_metro_unit.findData(
                getattr(vr, "metro_click_unit", "auto"))
            if idx_u >= 0 and idx_u != self.cb_metro_unit.currentIndex():
                self.cb_metro_unit.blockSignals(True)
                self.cb_metro_unit.setCurrentIndex(idx_u)
                self.cb_metro_unit.blockSignals(False)
            # Desactiva les unitats que no caben en algun compàs del mapa.
            model = self.cb_metro_unit.model()
            unit_actual = self._metro_click_unit_val()
            for i in range(self.cb_metro_unit.count()):
                unitat = self.cb_metro_unit.itemData(i)
                valid = unitat == "auto" or vr.click_unit_encaixa(unitat)
                it = model.item(i)
                if it is not None:
                    it.setEnabled(valid)
            if not vr.click_unit_encaixa(unit_actual):
                # El mapa ha canviat i la unitat triada ja no hi cap.
                auto = self.cb_metro_unit.findData("auto")
                self.cb_metro_unit.blockSignals(True)
                self.cb_metro_unit.setCurrentIndex(auto)
                self.cb_metro_unit.blockSignals(False)
                vr.metro_click_unit = "auto"
                vr.infoMissatge.emit(
                    "La unitat de clic anterior ja no encaixa en el nou "
                    "compàs; s'ha posat en auto.")
            idx = self.cb_metro.findData(getattr(vr, "metro_mode", "auto"))
            if idx >= 0 and idx != self.cb_metro.currentIndex():
                self.cb_metro.blockSignals(True)
                self.cb_metro.setCurrentIndex(idx)
                self.cb_metro.blockSignals(False)

    def _actualitza_info_wav(self, ruta, info=None):
        """Info (durada/Hz) a la barra d'estat. El títol el duu `_actualitza_titol`."""
        if info is None:
            try:
                info = pipeline.wav_info(ruta)
            except Exception as e:  # noqa: BLE001
                # error real i poc freqüent (WAV il·legible): warning al log de fitxer
                self.logger.warning("no es pot llegir la info del WAV %s: %s", ruta, e)
                info = None
        if info:
            self.wav_info.setText(
                f"{info['durada']:.1f} s · {info['canals']} canals · "
                f"{info['mostreig']} Hz")

    def _hi_ha_resultats(self):
        """Cert si ja hi ha un resultat d'anàlisi carregat al visor.

        Serveix per decidir si cal avisar que tornar a analitzar el
        sobreescriurà (i, amb ell, les edicions manuals de l'usuari).
        """
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return False
        return bool(getattr(vr, "acords", None)
                    or getattr(vr, "seccions", None))

    def _confirma_reanalisi(self):
        """Avís de sobreescriptura abans de re-analitzar.

        Retorna True per continuar i False per cancel·lar. Només pregunta si
        HI HA resultats a perdre: en la primera anàlisi d'un WAV nou no molesta.
        """
        if not self._hi_ha_resultats():
            return True
        if not self._interactiu():
            self.registra("sense sessió interactiva (offscreen): es continua "
                          "amb la reanàlisi")
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Tornar a analitzar")
        box.setText(
            "Tornar a analitzar <b>sobreescriurà els acords i l'estructura "
            "actuals</b>, incloent-hi les <b>edicions manuals</b> que hagis "
            "fet (moure, renombrar o eliminar acords, retallar seccions…).")
        box.setInformativeText(
            "Aquesta acció <b>no es pot desfer</b>: els fitxers de la carpeta "
            "de sortida es tornaran a generar.")
        b_go = box.addButton("Continua i descarta", QMessageBox.DestructiveRole)
        b_no = box.addButton("Cancel·la", QMessageBox.RejectRole)
        box.setDefaultButton(b_no)
        box.exec_()
        return box.clickedButton() is b_go

    def executa(self, pregunta=True, nomes_acords=False):
        """Analitza l'àudio (BPM · acords · estructura, segons les Opcions).

        Amb `nomes_acords` (F6) només es passen els acords: ni BPM ni
        estructura. Sense, mana el que hi haja a les 3 pestanyes del diàleg.
        """
        if nomes_acords:
            self.amb_est.setChecked(False)
            self.opcions["analisi"] = {"bpm": False, "acords": True,
                                       "estructura": False}
        wav = self.wav_edit.text().strip()
        if not wav or not os.path.isfile(wav):
            self.avisa("Auto Chords",
                                "Tria un àudio vàlid primer.")
            return
        if not ffmpeg.es_wav_pcm16(wav):
            try:
                wav = self._assegura_wav(wav)
                self.wav_edit.setText(wav)
            except Exception as e:  # noqa: BLE001
                self.avisa_crit("Auto Chords",
                                     f"No s'ha pogut convertir: {e}")
                return
        if pregunta:
            dlg = dialegs.DialegOpcions(self, tab="acords",
                                        opcions=self.opcions)
            # «Analitza» és només acords + estructura. El BPM té la seua
            # acció separada («Analitza BPM…»); no el tornem a oferir ací.
            if dlg.tabs.count() and dlg.tabs.tabText(0) == "BPM":
                dlg.tabs.removeTab(0)
            if dlg.exec_() != QDialog.Accepted:
                return
            self.opcions = dlg.opcions()
            self.opcions.setdefault("analisi", {})["bpm"] = False
            dialegs.desa_opcions(self.opcions)
            self._marca_dirty()
            # La casella «Només els acords» i l'acció «Inclou estructura» són
            # el MATEIX estat: es sincronitzen (una sola font de veritat).
            self.amb_est.setChecked(
                bool((self.opcions.get("analisi") or {})
                     .get("estructura", True)))
            # AVÍS OBLIGATORI: re-analitzar re-escriu els acords/estructura (i
            # les edicions manuals) i reinicia el desfer → no es recupera.
            if not self._confirma_reanalisi():
                return
        self._atura_si_sona("analisi amb els plugins")
        if self.projecte is not None:
            self.sortida = self.projecte.carpeta
        else:
            self.sortida = pipeline.carpeta_sortida(wav)
        self.log.clear()
        self.barra.setValue(0)
        self.registra(f"Sortida: {self.sortida}")
        self.b_exec.setEnabled(False)
        self.b_guia.setEnabled(False)        # res de guiat mentre s'analitza
        self.b_marker.setEnabled(False)
        self.b_marker_compas.setEnabled(False)
        self.b_export.setEnabled(False)
        self.b_export_part.setEnabled(False)
        _ana = self.opcions.get("analisi") or {}
        # Separació d'accions: «Analitza» només fa acords i estructura.
        # El BPM es detecta amb «Analitza BPM…» i es mostra com a capa.
        self.feina = Feina(wav, self.sortida, self._bpm_val(),
                           self._bpb_val(), self._offset_val(),
                           bool(_ana.get("estructura", True)),
                           self.tempo_fix.isChecked(),
                           opcions=self.opcions,
                           amb_bpm=False,
                           amb_acords=bool(_ana.get("acords", True)))
        self.feina.missatge.connect(self.registra)
        self.feina.progres.connect(self.barra.setValue)
        self.feina.feta.connect(self.acabada)
        self.feina.start()

    def acabada(self, be, dada):
        self.b_exec.setEnabled(True)
        self.b_guia.setEnabled(True)
        self.b_marker.setEnabled(True)
        self.b_marker_compas.setEnabled(True)
        self.b_export.setEnabled(True)
        self.b_export_part.setEnabled(True)
        self.registra("FET ✅ — ara pots revisar el visor i fer «Exporta WAV's».")
        self.barra.setValue(100)
        # El CRU de l'anàlisi es desa DINS el document (un sol fitxer).
        ana = getattr(self.feina, "analisi", None)
        if ana is not None and self.projecte is not None:
                net = projecte.saneja_analisi(ana)
                if net is None:
                    self.registra("AVÍS: l'anàlisi és massa gran (o no vàlida) "
                                  "per desar-la al projecte; el MODEL sí que "
                                  "hi és. Es pot tornar a analitzar.")
                    self.projecte.dades.pop("analisi", None)
                else:
                    self.projecte.dades["analisi"] = net
                try:
                    self.projecte.desa()
                    self.dirty = False
                    self._actualitza_titol()
                except OSError as e:
                    self.registra(f"AVÍS: no s'ha pogut desar l'anàlisi al "
                                  f"projecte: {e}")
        wav = self.wav_edit.text().strip()
        if wav and os.path.isfile(wav):
            self._carrega_visor(wav)
            # BPM detectat per l'anàlisi: al transport (tram 0) DESPRÉS de
            # carregar el visor, que si no el sobreescriu amb el del projecte.
            b_det = getattr(self.feina, "bpm_detectat", None)
            if b_det:
                self._aplica_bpm_detectat(float(b_det))
        else:
            self.b_export.setEnabled(False)
            self.b_export_part.setEnabled(False)
            self.registra(f"ERROR: {dada}")
            self.log_dock.setVisible(True)    # en cas d'error, obrim el log
            self.avisa_crit("Auto Chords", dada)

    def _aplica_beats_guardats(self, visor=None):
        """Restaura els beats QM del projecte i sincronitza l'estat de Finestra.

        `_beats_actuals` és la font que usa el `+` i el Snap QM; si no es
        neteja en obrir un altre projecte, el projecte nou hereta els beats
        del projecte anterior.
        """
        visor = visor or getattr(self, "visor_ref", None)
        dades = getattr(getattr(self, "projecte", None), "dades", None) or {}
        info = dades.get("analisi_beats")
        if not visor or not isinstance(info, dict):
            self._beats_actuals = None
            return
        beats = info.get("beats")
        downbeats = info.get("downbeats")
        if not isinstance(beats, list):
            self._beats_actuals = None
            return
        self._beats_actuals = info
        try:
            visor.timeline.set_beats(beats, downbeats if isinstance(
                downbeats, list) else [])
            visor.set_snap_beats(beats)
        except Exception as e:  # noqa: BLE001
            self.registra(f"beats: no s'han pogut restaurar ({e})")

    def _analitza_bpm(self):
        """Acció separada «Analitza BPM»: motor, sensibilitat i línies."""
        wav = self.wav_edit.text().strip()
        if not wav or not os.path.isfile(wav):
            self.avisa("Analitza BPM", "Primer tria una WAV.")
            return
        dlg = dialegs.DialegAnalitzaBPM(self, opcions=self.opcions)
        if dlg.exec_() != QDialog.Accepted:
            return
        cfg = dlg.valors()
        nomes_beats = cfg.get("mode") == "beats"
        opcions_bpm = self.opcions.get("bpm") or {}
        self._atura_si_sona("anàlisi de beats")
        self.registra(
            f"Analitzant {'beats' if nomes_beats else 'BPM'}: "
            f"{cfg['motor']} · sensibilitat {cfg['sensibilitat']}/100…")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            res = beats_mod.detecta(
                wav,
                motor=cfg["motor"],
                sensibilitat=cfg["sensibilitat"],
                bpb=self._bpb_val(),
                den=self._beat_type_val(),
                bpm_hint=self._bpm_val(),
                bpm_min=opcions_bpm.get("min"),
                bpm_max=opcions_bpm.get("max"),
                preferit=(opcions_bpm.get("pref_min"),
                          opcions_bpm.get("pref_max")),
                log=self.registra,
                nomes_beats=nomes_beats,
            )
        except Exception as e:  # noqa: BLE001
            self.registra(f"Analitza BPM ERROR: {e}")
            self.avisa_crit("Analitza BPM", f"No s'ha pogut detectar: {e}")
            return
        finally:
            QApplication.restoreOverrideCursor()

        self._beats_actuals = res
        beats = list(res.get("beats") or ())
        downbeats = list(res.get("downbeats") or ())
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            vr.timeline.set_beats(beats, downbeats)
            vr.set_snap_beats(beats)
        self.opcions["beats"] = dict(cfg)
        dialegs.desa_opcions(self.opcions)
        self._marca_dirty()
        bpm = res.get("bpm")
        if not nomes_beats and cfg.get("aplica_bpm") and bpm:
            self._aplica_bpm_detectat(float(bpm))
        if self.projecte is not None:
            self.projecte.dades["analisi_beats"] = {
                "motor": res.get("motor"),
                "sensibilitat": res.get("sensibilitat"),
                "mode": cfg.get("mode"),
                "bpm": bpm,
                "beats": beats,
                "downbeats": downbeats,
            }
            try:
                self.projecte.desa()
                self.dirty = False
                self._actualitza_titol()
            except OSError as e:
                self.registra(f"beats: no s'han pogut desar al projecte ({e})")
        if not beats:
            self.avisa_info("Analitza BPM",
                            "No s'ha detectat cap beat amb estes opcions.")
            return
        bpm_txt = f"{bpm:.2f}" if bpm is not None else "—"
        if nomes_beats:
            self._missatge_info(f"{len(beats)} beats (sense BPM ni compassos)")
            self.registra(
                f"{len(beats)} beats · només polsos · motor "
                f"{res.get('motor')} (sensibilitat "
                f"{res.get('sensibilitat'):.0f}/100)")
        else:
            self._missatge_info(
                f"BPM: {bpm_txt} · {len(beats)} beats · "
                f"{len(downbeats)} downbeats")
            self.registra(
                f"BPM: {bpm_txt} · {len(beats)} beats · "
                f"{len(downbeats)} downbeats · motor {res.get('motor')} "
                f"(sensibilitat {res.get('sensibilitat'):.0f}/100)")

    def _ajusta_graella_beats(self):
        """Acció de menú: snap dels marcadors a QM i ajust del mapa."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.avisa("Ajusta graella", "Primer obri una WAV.")
            return
        info = getattr(self, "_beats_actuals", None)
        if not info:
            info = (getattr(getattr(self, "projecte", None), "dades", {})
                    .get("analisi_beats"))
        if not isinstance(info, dict) or not info.get("beats"):
            self.avisa_info(
                "Ajusta graella",
                "No hi ha beats detectats. Executa «Analitza BPM» primer.")
            return
        beats = list(info.get("beats") or ())
        downbeats = list(info.get("downbeats") or ())
        # Ajustar la graella és una operació posterior al play: parem primer
        # per no mostrar cap diàleg mentre l'usuari està marcant compassos.
        self._atura_si_sona("ajust de la graella als beats")
        tolerancia, ok = QInputDialog.getDouble(
            self, "Ajusta la graella als beats QM",
            "Tolerància del snap (ms):", 120.0, 10.0, 500.0, 0)
        if not ok:
            return
        try:
            res = vr.ajusta_graella_a_beats(
                beats, downbeats, tolerancia=float(tolerancia) / 1000.0)
        except Exception as e:  # noqa: BLE001
            self.registra(f"Ajusta graella ERROR: {e}")
            self.avisa_crit("Ajusta graella", f"No s'ha pogut ajustar: {e}")
            return
        if res is None:
            return
        self._marca_dirty()
        self._missatge_info(
            f"Graella ajustada: {len(res.get('moguts') or [])} marcadors "
            f"snapats · {len(res.get('ambigus') or [])} dubtosos")
        self.registra(
            f"Ajusta graella: {len(res.get('moguts') or [])} snapats, "
            f"{len(res.get('ambigus') or [])} dubtosos, "
            f"{res.get('trams')} trams")
        self._mostra_revisio_snap(res.get("ambigus") or [])

    def _mostra_revisio_snap(self, ambigus):
        if not ambigus:
            return
        vr = getattr(self, "visor_ref", None)
        dlg = dialegs.DialegRevisioSnap(
            self, ambigus=ambigus,
            ves_a=(vr.ves_a if vr is not None else None),
            snap=self._snap_individual)
        self._revisio_snap = dlg
        dlg.show()

    def _snap_individual(self, vell, nou):
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return False
        try:
            ok = bool(vr.snap_un_marcador(float(vell), float(nou)))
        except Exception as e:  # noqa: BLE001
            self.registra(f"Snap individual ERROR: {e}")
            return False
        if ok:
            self._marca_dirty()
        return ok

    def _compas_del_marcador(self):
        """Obfri editar el compàs del tram que comença en un marcador."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.avisa("Compàs del marcador", "Primer obri una WAV.")
            return
        self._atura_si_sona("edició del compàs")
        t = float(getattr(vr, "pos", 0.0))
        idx_m = None
        dist = 0.25
        for i, m in enumerate(getattr(vr, "marcadors", []) or []):
            d = abs(float(m) - t)
            if d <= dist:
                idx_m, dist = i, d
        if idx_m is None:
            self.avisa_info(
                "Compàs del marcador",
                "Posa el cursor prop d'un marcador de compàs.")
            return
        t_m = float(vr.marcadors[idx_m])
        idx_t = None
        for i, s in enumerate(getattr(vr, "tempo_trams", []) or []):
            if abs(float(s[0]) - t_m) <= 0.06:
                idx_t = i
                break
        if idx_t is None:
            self.avisa_info(
                "Compàs del marcador",
                "No hi ha cap tram de tempo que comence en eixe marcador.")
            return
        vr._on_tempo_edit(idx_t)

    def _aplica_bpm_detectat(self, b):
        """Posa al transport el BPM que ha detectat «Analitza» (etapa BPM).

        Si el mapa de tempo té **més d'un tram**, no s'hi toca res: canviar-ne
        només el primer trencaria el contracte de beats sencers dels trams
        (regla de temps) — per a eixe cas hi ha «Detecta el tempo per trams».
        """
        b = float(b)
        self._posa_bpm_quarter(b)
        self._marca_dirty()
        self.registra(f"BPM detectat: {b:.3f}")
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return
        trams = list(getattr(vr, "tempo_trams", []) or [])
        if len(trams) > 1:
            self.registra(f"BPM detectat: no s'aplica al mapa ({len(trams)} "
                          "trams); fes servir «Detecta el tempo per trams»")
            return
        self._aplica_parametres_temps()

    def _prepara_export(self):
        """Valida i calcula els arguments de l'export (NOMÉS al fil de UI).

        Retorna el diccionari de kwargs per a `pipeline.exporta_total`, o
        `None` si no es pot exportar (i ja ha avisat). Els widgets es llegeixen
        AQUÍ perquè el fil de l'export (A5) no els pot tocar.
        """
        wav = self.wav_edit.text().strip()
        if not self.sortida:
            if not wav or not os.path.isfile(wav):
                self.avisa("Auto Chords",
                           "Tria una wav vàlida abans d'exportar.")
                return None
            self.sortida = pipeline.carpeta_sortida(wav)

        csv_ac = os.path.join(self.sortida, "acords.csv")
        if not os.path.isfile(csv_ac):
            if not wav or not os.path.isfile(wav):
                self.avisa("Auto Chords",
                           "No hi ha CSVs d'exportació. Fes 'Executa' primer.")
                return None
            self.avisa_info(
                "Auto Chords",
                "Encara no hi ha CSVs generats. Fes 'Executa' primer.")
            return None

        # (A) Si hi ha visor, l'export usa el MODEL VIU (no els CSV del disc):
        # així no es perden les edicions manuals de seccions (ni la cobertura).
        vr = getattr(self, "visor_ref", None)
        acords_model = list(vr.acords) if vr is not None else None
        seccions_model = list(vr.seccions) if vr is not None else None
        total_s = (float(vr.audio.get("durada", 0.0))
                   if vr is not None else None)
        # Regla d'or #12: el mapa de BPM/compàs del model viu també s'exporta.
        mapa_model = list(vr.tempo_trams) if vr is not None else None
        amb_estructura = self.amb_est.isChecked() and seccions_model is not None
        # (2) Amb «Inclou estructura» OFF, les restes d'un export ANTERIOR
        # (`wavs_estructura/`) quedaven a la carpeta i semblava que l'export
        # actual hagués inclòs estructura → s'ofereix treure-les (amb
        # confirmació). El MODEL (`estructura_ABC.csv`) NO es toca mai.
        if not amb_estructura:
            self._neteja_estructura_vella(self.sortida)
        return dict(
            csv_ac=csv_ac,
            csv_seg=None,
            sortida=self.sortida,
            bpm=self._bpm_val(),
            bpb=self._bpb_val(),
            offset=self._offset_val(),
            sr=44100,
            tempo_fix=self.tempo_fix.isChecked(),
            amb_estructura=amb_estructura,
            acords=acords_model,
            seccions=seccions_model,
            total_s=total_s,
            tempo_csv=mapa_model,
        )

    def _neteja_estructura_vella(self, sortida):
        """Treu les restes d'un export ANTERIOR quan l'actual NO inclou estructura.

        **(a) MAI toca el MODEL del projecte** (`estructura_ABC.csv`): la marca
        «Inclou estructura» decideix què s'**exporta**, no què es **conserva**.
        Només s'ofereix treure els **derivats de l'export** (`wavs_estructura/`).

        **(c) Sempre amb confirmació**: només es pregunta si hi ha restes a
        treure, i res no s'esborra sense un «sí» explícit.
        """
        wavs = os.path.join(sortida, "wavs_estructura")
        if not os.path.isdir(wavs):
            return
        if not self._ho_confirma(
                "Exporta sense estructura",
                "Aquest export no inclou l'estructura.\n\n"
                "El MODEL del projecte (estructura_ABC.csv) es conserva SEMPRE.\n"
                "Només es poden treure els WAVs de l'export anterior "
                "(wavs_estructura/).\n\nVols treure'ls?",
                "Treu-los"):
            self.registra("estructura: es conserven els derivats de l'export "
                          "anterior (wavs_estructura/)")
            return
        try:
            shutil.rmtree(wavs)
            self.registra("«Inclou estructura» OFF → tret l'export anterior: "
                          "wavs_estructura/ (el model estructura_ABC.csv es "
                          "conserva)")
        except OSError as e:
            self.registra(f"AVÍS: no he pogut treure {wavs}: {e}")

    def _ho_confirma(self, titol, text, boto_si):
        """Demana confirmació (Sí/No). Sense sessió interactiva (`offscreen`,
        CI) respon **No** i no mostra cap diàleg modal."""
        if not self._interactiu():
            return False
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle(titol)
        box.setText(text)
        b_si = box.addButton(boto_si, QMessageBox.DestructiveRole)
        b_no = box.addButton("Cancel·la", QMessageBox.RejectRole)
        box.setDefaultButton(b_no)
        box.exec_()
        return box.clickedButton() is b_si

    def _exporta_audio_ui(self):
        """Tria format i destí i exporta la còpia WAV de treball (Fase 6).

        Obre el diàleg natiu de desar. Els filtres són els perfils que aquest
        `ffmpeg` sap escriure de debò; el nom suggerit viu a la carpeta del
        projecte. Mai es pot triar la còpia de treball; per a qualsevol altre
        fitxer existent, el diàleg natiu demana confirmació.
        """
        origen = self._wav_treball()
        if not origen:
            self.avisa_info("Exporta àudio",
                            "Obre un àudio abans d'exportar-ne una còpia.")
            return
        perfils = exporta_audio_mod.perfils_disponibles()
        if not perfils:
            self.avisa(
                "Exporta àudio",
                "Aquest ffmpeg no té cap codificador d'àudio compatible.\n"
                "No s'ofereix cap format per no prometre'n un que fallaria.")
            return
        carpeta = (self.projecte.carpeta if self.projecte is not None
                   else os.path.dirname(origen))
        nom = ((self.projecte.nom if self.projecte is not None
                else os.path.splitext(os.path.basename(origen))[0])
               + "_editat")
        filtres = [exporta_audio_mod.filtre(p) for p in perfils]
        dlg = QFileDialog(self, "Exporta àudio", carpeta, ";;".join(filtres))
        dlg.setAcceptMode(QFileDialog.AcceptSave)
        dlg.setFileMode(QFileDialog.AnyFile)
        dlg.setConfirmOverwrite(True)
        dlg.setDefaultSuffix(perfils[0]["ext"])
        dlg.selectNameFilter(filtres[0])
        dlg.selectFile(os.path.join(carpeta,
                                    nom + "." + perfils[0]["ext"]))

        def _canvia_filtre(text):
            p = exporta_audio_mod.perfil_de_filtre(text, perfils)
            if p is not None:
                dlg.setDefaultSuffix(p["ext"])

        dlg.filterSelected.connect(_canvia_filtre)
        if dlg.exec_() != QFileDialog.Accepted:
            return
        ruta = dlg.selectedFiles()[0]
        perfil = exporta_audio_mod.perfil_de_filtre(
            dlg.selectedNameFilter(), perfils)
        if perfil is None:
            self.avisa("Exporta àudio",
                       "No s'ha pogut determinar el format triat.")
            return
        ext_esperada = "." + perfil["ext"]
        arrel, ext = os.path.splitext(ruta)
        if not ext:
            ruta = arrel + ext_esperada
        elif ext.lower() != ext_esperada:
            # No substituïm l'extensió en silenci: seria un fitxer amb un
            # contingut que no diu el nom.
            self.avisa(
                "Exporta àudio",
                f"El nom acaba en «{ext}», però el format triat és "
                f"«{perfil['etiqueta']}» ({ext_esperada}).\n"
                "Tria el format que corresponga a l'extensió o canvia el nom.")
            return
        protegits = {os.path.realpath(origen)}
        if os.path.realpath(ruta) in protegits:
            self.avisa(
                "Exporta àudio",
                "No es pot exportar sobre la còpia de treball del projecte.\n"
                "Tria un altre nom o una altra carpeta.")
            return
        if not os.path.isdir(os.path.dirname(os.path.abspath(ruta))):
            self.avisa("Exporta àudio",
                       "La carpeta de destinació no existeix.")
            return
        self.a_exporta_audio.setEnabled(False)
        self.registra(f"Exportant àudio ({perfil['etiqueta']}): {ruta}")
        fil = FeinaExportaAudio(origen, ruta, perfil)
        fil.missatge.connect(self.registra)
        fil.feta.connect(self._exporta_audio_acabada)
        self._fil_exporta_audio = fil
        fil.start()

    def _exporta_audio_acabada(self, ok, error, desti):
        """Tanca l'exportació d'àudio: log visible i estat de l'acció."""
        self._fil_exporta_audio = None
        if hasattr(self, "a_exporta_audio"):
            self.a_exporta_audio.setEnabled(bool(self._wav_treball()))
        if ok:
            self.registra(f"Exportació d'àudio feta: {desti}")
            self._missatge_info(f"Àudio exportat: {os.path.basename(desti)}")
        else:
            self.registra(f"ERROR a l'exportar àudio: {error}")
            self.avisa("Exporta àudio",
                       f"No s'ha pogut exportar l'àudio:\n{error}")

    def _exporta_acabada(self, res_part=None):
        """Missatges de final d'exportació (compartit pel camí síncron i el fil)."""
        self.registra("Exportació feta ✅")
        msg = f"Exportació feta a:\n{self.sortida}"
        if res_part is not None and not res_part.get("pdf"):
            msg += ("\n\n⚠️ La partitura s'ha generat NOMÉS en MusicXML: el "
                    "PDF necessita MuseScore instal·lat.")
        self.avisa_info("Auto Chords", msg)
        self.obre_carpeta()

    def exporta(self):
        """Exporta de forma SÍNCRONA (la UI espera). Vegeu `exporta_async`."""
        kwargs = self._prepara_export()
        if kwargs is None:
            return
        self.exporta_error = ""
        try:
            self.registra(f"Exportant a: {self.sortida}")
            pipeline.exporta_total(log=self.registra, **kwargs)
            res_part = self._exporta_partitura() if self.amb_part.isChecked() else None
            self._exporta_acabada(res_part)
        except Exception as e:  # noqa: BLE001
            self.exporta_error = str(e)
            self.registra(f"exporta ERROR: {e}")
            self.avisa_crit("Auto Chords",
                            f"No s'ha pogut exportar:\n{e}")

    def exporta_async(self):
        """Exporta en un FIL (A5). Retorna True si ha arrencat.

        La partitura (si la marca hi és) es fa DESPRÉS, al fil de la UI, quan el
        fil acaba. El progrés es veu a la barra i a `self.exportant`.
        """
        fe = getattr(self, "feina_export", None)
        if fe is not None and fe.isRunning():
            return False
        kwargs = self._prepara_export()
        if kwargs is None:
            return False
        self.registra(f"Exportant a: {self.sortida}")
        self.exporta_error = ""
        self.exportant = True
        self.exporta_iniciat = time.time()
        self.barra.setValue(0)
        self.feina_export = FeinaExporta(kwargs)
        self.feina_export.missatge.connect(self.registra)
        self.feina_export.progres.connect(self.barra.setValue)
        self.feina_export.feta.connect(self._exporta_async_feta)
        self.feina_export.start()
        return True

    def _exporta_async_feta(self, ok, error):
        self.exportant = False
        if not ok:
            self.exporta_error = error
            self.registra(f"exporta ERROR: {error}")
            self.avisa_crit("Auto Chords", f"No s'ha pogut exportar:\n{error}")
            return
        res_part = self._exporta_partitura() if self.amb_part.isChecked() else None
        self._exporta_acabada(res_part)

    def _exporta_partitura(self):
        """Genera el lead sheet de xifrats de la carpeta de sortida.

        Es **tolerant**: `app/partitura.py` escriu sempre el MusicXML i, només
        si troba el MuseScore, el PDF/MSCZ. Cap error d'aquí no ha de fer caure
        l'exportació normal. Retorna el diccionari de resultats (o None).

        """
        wav = self.wav_edit.text().strip() or None
        vr = getattr(self, "visor_ref", None)
        mapa = getattr(vr, "tempo_map", None)
        durada = float((getattr(vr, "audio", {}) or {}).get("durada", 0.0) or 0.0)
        # Els acords surten del MODEL viu (zero fitxers intermedis). Si encara
        # no n'hi ha, la partitura ja retorna el seu error net («sense acords»).
        ev = []
        try:
            ev = pipeline.events_partitura(
                os.path.join(self.sortida, "acords.csv"),
                self._bpm_val(), self._bpb_val(), self._offset_val(),
                durada=durada, mapa=mapa)
        except (RuntimeError, OSError) as e:
            self.registra(f"partitura: el model encara no té acords ({e})")
        rubatos = [
            (float(t.ini), float(t.fi), t.compassos)
            for t in (getattr(vr, "tempo_trams", None) or [])
            if getattr(t, "tipus", None) == "rubato"
        ]
        try:
            res = partitura.exporta_partitura(
                self.sortida,
                log=self.registra,
                bpm=self._bpm_val(),
                bpb=self._bpb_val(),
                offset=self._offset_val(),
                wav=wav,
                new_system_each=4,     # 4 compassos per línia (lead sheet)
                mapa=mapa,
                events=ev,
                durada=durada,
                rubatos=rubatos,
                bpm_unit=self._bpm_unit_val(),
            )
            if res.get("error"):
                self.registra(f"partitura: sense resultat ({res['error']})")
            return res
        except Exception as e:  # noqa: BLE001
            self.registra(f"partitura ERROR: {e}")
            return None

    def _missatge_partitura(self, res):
        """Text clar de què s'ha generat a la partitura, deixant palès que el
        PDF i el MSCZ depenen de **MuseScore** instal·lat (l'app no l'inclou)."""
        fets = ["MusicXML"]
        if res.get("pdf"):
            fets.append("PDF")
        if res.get("mscz"):
            fets.append("MSCZ")
        linies = ["S'ha generat: " + " + ".join(fets) + " ✓"]
        for clau, etiqueta in (("musicxml", "MusicXML"), ("pdf", "PDF"),
                               ("mscz", "MSCZ")):
            if res.get(clau):
                linies.append(f"{etiqueta}: {res[clau]}")
        if not res.get("pdf"):
            linies += ["",
                       "⚠️ El PDF (i el MSCZ) NO s'han generat: la partitura en "
                       "PDF necessita MuseScore instal·lat.",
                       "Pots obrir el MusicXML amb el MuseScore que tinguis, o "
                       "instal·lar-lo (o definir la variable AUTO_CHORDS_MUSESCORE)."]
        return "\n".join(linies)

    def exporta_partitura_ara(self):
        """Accio de menu: genera NOMES la partitura de la sortida actual."""
        if not self.sortida:
            self.avisa("Auto Chords",
                                "Exporta primer (cal la carpeta de resultats).")
            return
        res = self._exporta_partitura()
        if not res or res.get("error"):
            self.avisa(
                "Auto Chords",
                "No s'ha pogut generar la partitura.\n"
                "Cal haver exportat abans, en mode BPM · compàs "
                "(cal que el model tinga almenys un acord). Detall al log.")
            return
        self.avisa_info("Auto Chords",
                                self._missatge_partitura(res))
        self.obre_carpeta()

    @staticmethod
    def _buida_esdeveniments():
        """Entrega els esdeveniments JA postejats (p. ex. `finished` d'un fil).

        Per què: `QThread.wait()` espera que el fil acabe, però el senyal
        `finished` viatja **postejat** (connexió cua) i es pot entregar molt
        més tard, quan la finestra o el fil ja són destruïts → el slot corre
        sobre un objecte mort (segfault). Entregar-lo ací, amb tot viu, tanca
        el forat. Detectat al CI/teardown dels tests (2026-10-21).
        """
        try:
            QCoreApplication.sendPostedEvents(None, 0)
        except Exception:  # noqa: BLE001 — mai ha de fer fallar el tancament
            pass

    def closeEvent(self, ev):
        """Neteja ordenada abans que Qt destrueixi la finestra.

        Sense això, es destruïa la Finestra amb fils vius (`FeinaExporta`) i el
        reproductor del visor sonant: destrucció en ordre arbitrari = risc
        d'access violation.
        """
        if not self._pot_descartar():
            ev.ignore()
            return
        self._tanca_sessio_tap()
        ft = getattr(self, "_fil_trams", None)
        try:
            if ft is not None and ft.isRunning():
                ft.wait(20000)
        except RuntimeError:
            pass
        self._buida_esdeveniments()
        fa = getattr(self, "_fil_exporta_audio", None)
        try:
            if fa is not None and fa.isRunning():
                fa.wait(20000)
        except RuntimeError:
            pass
        self._buida_esdeveniments()
        fe = getattr(self, "feina_export", None)
        try:
            if fe is not None and fe.isRunning():
                fe.wait(10000)
        except RuntimeError:
            pass
        self._buida_esdeveniments()
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            try:
                vr.rellotge.stop()
                vr._atura_proc()
            except (RuntimeError, AttributeError):
                pass
        self._neteja_sessio()          # tancament NET: ja no cal recuperar
        super().closeEvent(ev)

    def obre_carpeta(self):
        if self.sortida and os.path.isdir(self.sortida):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.sortida))
        else:
            self.avisa_info("Auto Chords",
                                    "Encara no hi ha cap resultat.")

def main():
    # A Windows la consola sol ser cp1252 i els missatges porten emojis i
    # fletxes: sense això un simple print() peta amb UnicodeEncodeError
    # (trobat al CI amb test_exporta_includes_both_acord_and_structure_wavs).
    for _flux in (sys.stdout, sys.stderr):
        try:
            _flux.reconfigure(errors="replace")
        except (AttributeError, ValueError, OSError):
            pass
    logger = setup_logging(DEFAULT_LOG_PATH)
    logger.info("Inici de l'aplicació | argv=%s cwd=%s", sys.argv, os.getcwd())
    activa_faulthandler(DEFAULT_LOG_PATH, logger)

    lock_file = plataforma.obre_fitxer_instancia()
    if lock_file is None:
        logger.warning("No s'ha pogut crear el fitxer de bloqueig d'instància "
                       "única; s'aborta.")
        print("[main] No s'ha pogut crear el bloqueig d'instància única; "
              "s'aborta.", file=sys.stderr)
        return 1
    if not plataforma.bloqueja_instancia_unica(lock_file):
        logger.warning("Ja hi ha una instància d'Auto Chords en execució; s'aborta la segona.")
        print("[main] Auto Chords ja està en execució; no es permet iniciar-ne una segona instància.", file=sys.stderr)
        lock_file.close()
        return 1

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(FOSC)
    app.setWindowIcon(icones.icona_app())
    w = Finestra()
    w.show()
    # Smoke test del CI (AUTO_CHORDS_SMOKE=1): la finestra s'ha creat i mostrat
    # → ho deixem al log i sortim sols. Permet validar que l'app EMPAQUETADA
    # arrenca de debò (dyld, plugins de Qt, dades…) sense necessitar GUI.
    if os.environ.get("AUTO_CHORDS_SMOKE") == "1":
        logger.info("SMOKE: finestra principal creada correctament")
        # Comprovació del MOTOR D'ÀUDIO dins l'app EMPAQUETADA (mac/win): que
        # `sounddevice`/PortAudio es pugui IMPORTAR i carregar de debò (no només
        # que el fitxer hi sigui). Si falla, ho diem ben clar al log.
        if plataforma.usa_audio_natiu():
            try:
                import sounddevice as sd      # carrega PortAudio (cffi)
                try:
                    pv = sd.get_portaudio_version()[1]
                except Exception:  # noqa: BLE001
                    pv = "?"
                try:
                    nd = len(sd.query_devices())   # pot ser 0 en headless: no és error
                except Exception:  # noqa: BLE001
                    nd = -1
                logger.info("SMOKE: audio OK — sounddevice %s · PortAudio %s · "
                            "%d dispositius", sd.__version__, pv, nd)
            except Exception as e:  # noqa: BLE001
                logger.error("SMOKE: AUDIO ERROR — no s'ha pogut carregar "
                             "sounddevice/PortAudio: %s", e)
        QTimer.singleShot(1500, app.quit)
    else:
        w._comprova_recuperacio()
    try:
        sys.exit(app.exec_())
    finally:
        logger.info("Sortida de l'aplicació")
        # Només alliberem el bloqueig: NO esborrem el fitxer (esborrar-lo
        # podria crear una carrera entre instàncies: una altra instància
        # podria obrir el fitxer nou mentre aquesta encara el té bloquejat).
        plataforma.desbloqueja(lock_file)
        lock_file.close()

if __name__ == "__main__":
    raise SystemExit(main())
