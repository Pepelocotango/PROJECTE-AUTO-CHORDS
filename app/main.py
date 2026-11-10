#!/usr/bin/env python3
# main.py — Auto Chords (PyQt5/Qt5: l'únic Qt que corre al Q9400) —
#           wav -> acords + estructura -> carpetes. Tot en català.
import faulthandler
import logging
import math
import os
import sys
import time  # patch("app.main.time.monotonic") als tests de TAP

from PyQt5.QtCore import QCoreApplication, QEvent, Qt, QTimer, QUrl
from PyQt5.QtGui import QDesktopServices, QKeySequence
from PyQt5.QtWidgets import (
    QAction, QApplication, QButtonGroup, QCheckBox, QDockWidget,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QComboBox,
    QMessageBox, QProgressBar, QPushButton, QShortcut,
    QDialog, QInputDialog,
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
from app.camp_text import CampText
from . import bpm_unit as bpm_unit_mod  # noqa: E402
from . import ffmpeg, partitura, pipeline, postproc, theme  # noqa: F401
from . import config  # noqa: E402
from . import dialeg_guia_rapida  # noqa: E402
from . import dialegs  # noqa: E402
from . import icones  # noqa: E402
from . import panell_xifrat  # noqa: E402
from . import plataforma  # noqa: E402
from . import tempo_map  # noqa: E402
from . import limits  # noqa: E402

# Sempre a un directori ESCRIPTIBLE: en una AppImage muntada la carpeta del
# projecte és de només lectura i escriure-hi el log petava a l'arrencada.
DEFAULT_LOG_PATH = config.LOG_PATH
from .info_box import (  # noqa: F401  (re-exportats per als tests)
    InfoBoxMixin, _INFO_ROTACIO_S, _INFO_PAUSA_S,
)
from .feines import Feina, FilTempoTrams
from .drag_drop_ui import DragDropMixin
from .menus import MenusMixin
from .edicio_ui import EdicioMixin
from .barres import BarresMixin
from .projecte_ui import ProjecteMixin
from .temps_ui import TempsMixin
from .marcadors_ui import MarcadorsMixin
from .tap_ui import TapMixin
from .visor_ui import VisorUIMixin
from .analisi_ui import AnalisiMixin
from .export_ui import ExportMixin

# Re-export de mòduls que els tests comproven com a objecte únic.
_MODULS_REEXPORTATS = (postproc, Feina, partitura, time)

# Re-export perquè els tests consulten `app_main._INFO_ROTACIO_S`.
_INFO_COMPAT = (_INFO_ROTACIO_S, _INFO_PAUSA_S)

# Sempre a un directori ESCRIPTIBLE: en una AppImage muntada la carpeta del
# projecte és de només lectura i escriure-hi el log petava a l'arrencada.


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




class Finestra(QMainWindow, InfoBoxMixin, DragDropMixin, MenusMixin,
                EdicioMixin, BarresMixin, ProjecteMixin, TempsMixin,
                MarcadorsMixin, TapMixin, VisorUIMixin, AnalisiMixin,
                ExportMixin):
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
        self.wav_edit = CampText()      # només com a magatzem de la ruta
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
        # Arrossegar un àudio des de l'explorador de fitxers obre'l. Els
        # esdeveniments de drag es reben a la finestra i, si cauen sobre un
        # fill que accepta drops (camps de text, log…), l'eventFilter els
        # desvia igualment (vegeu `_drag_*`).
        self.setAcceptDrops(True)

        # Botó «Guia ràpida»: explicació del flux (només informació, no toca
        # el model). El treball real es fa amb marcadors en viu: `+`.
        self.b_guia = QPushButton("Guia ràpida")
        self.b_guia.setObjectName("secundari")
        self.b_guia.setToolTip(
            "Guia ràpida del flux de treball. Per tallar tempo i estructura "
            "en viu, fes servir ＋ o la tecla +; M afig només un marcador.")
        self.b_guia.setEnabled(False)          # fins que hi hagi WAV
        self.b_guia.clicked.connect(self._obre_guia_rapida)
        self.b_marker = QPushButton("＋ Temps+Secció")
        self.b_marker.setObjectName("secundari")
        self.b_marker.setIcon(icones.ico("compass", 16))
        self.b_marker.setIconSize(icones.pm_mida(16))
        self.b_marker.setToolTip(
            "Parteix el tempo i l'estructura al cursor (tecla +).")
        self.b_marker.setEnabled(False)
        self.b_marker.clicked.connect(self._talla_tempo_i_estructura_cursor)

        self.b_marker_compas = QPushButton("＋ Marcador")
        self.b_marker_compas.setObjectName("secundari")
        self.b_marker_compas.setIcon(icones.ico("map-pin", 16))
        self.b_marker_compas.setIconSize(icones.pm_mida(16))
        self.b_marker_compas.setToolTip(
            "Afig només un marcador al cursor (tecla M); no talla res.")
        self.b_marker_compas.setEnabled(False)
        self.b_marker_compas.clicked.connect(self._marcador_cursor)

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
        self.bpm = CampText("120.000")
        self.bpm.setFixedWidth(70)
        self.bpm.setPlaceholderText("120.000")
        self.bpm.setToolTip(
            "BPM del tema en negres/minut, com als DAW. Entrada manual (text).")
        self.bpb = CampText("4/4")
        self.bpb.setFixedWidth(60)
        self.bpb.setPlaceholderText("4/4")
        self.bpb.setToolTip("Compàs manual: 4/4, 3/4, 2/4, 1/4, 6/8, etc.")
        # Referència MANUAL del recalcul (no canvia el transport ni els clips).
        self.ref_bpm = CampText("120.000")
        self.ref_bpm.setFixedWidth(64)
        self.ref_bpm.setPlaceholderText("120.000")
        self.ref_bpm.setToolTip(
            "BPM de referència per a tots els recalcs. No canvia el clip: "
            "només és l'àncora de la cerca de BPM/compàs/N.")
        self.ref_bpb = CampText("4/4")
        self.ref_bpb.setFixedWidth(46)
        self.ref_bpb.setPlaceholderText("4/4")
        self.ref_bpb.setToolTip(
            "Compàs de referència (x/y) per als recalcs. Els beats detectats "
            "poden corregir-lo si cal (p. ex. 14 beats → 7/4).")
        self._ref_manual = False
        self.cb_beat = QComboBox()
        for _clau, _et in bpm_unit_mod.opcions():
            self.cb_beat.addItem(_et, _clau)
        self.cb_beat.setCurrentIndex(0)
        self.cb_beat.setFixedWidth(118)
        self.cb_beat.setSizeAdjustPolicy(
            QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.cb_beat.setMinimumContentsLength(10)
        self.cb_beat.setToolTip(
            "Unitat del beat detectat i valor dels taps (negra, negra amb "
            "punt, corxera o blanca). El recalcul convertix K a negres i el "
            "TAP multiplica els taps/min pel valor triat. En 6/8, tria negra "
            "amb punt si toques cada grup de 3 corxeres.")
        self.cb_beat.currentIndexChanged.connect(self._canvia_beat_unit)
        self.offset = CampText("0.000")
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
        for camp in (self.ref_bpm, self.ref_bpb):
            camp.editingFinished.connect(self._aplica_ref_recalc)

        self._params_temps = QWidget()      # s'amaga sencer en mode Lliure
        hp = QHBoxLayout(self._params_temps)
        hp.setContentsMargins(0, 0, 0, 0)
        hp.setSpacing(6)
        hp.addWidget(QLabel("BPM:"))
        hp.addWidget(self.bpm)
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
        hp.addWidget(QLabel("Ref. recalc:"))
        hp.addWidget(self.ref_bpm)
        hp.addWidget(self.ref_bpb)
        hp.addWidget(QLabel("Beat/TAP:"))
        hp.addWidget(self.cb_beat)
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
        hp.addWidget(QLabel("≈"))
        self.offset_cb = CampText("1.1")         # el mateix, en compàs.beat
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
        self.b_analitza_beats = QPushButton("Beats/BPM")
        self.b_analitza_beats.setObjectName("secundari")
        self.b_analitza_beats.setIcon(icones.ico("target", 16))
        self.b_analitza_beats.setIconSize(icones.pm_mida(16))
        self.b_analitza_beats.setToolTip(
            "Analitza beats, downbeats i BPM de la WAV (F7). No toca acords "
            "ni estructura.")
        self.b_analitza_beats.clicked.connect(self._analitza_bpm)
        self.b_analitza_beats.setEnabled(False)  # fins que hi haja WAV

        # 1a BARRA: en ORDRE DE FLUX de treball →
        #   1) Obre  ·  2) opcions de temps  ·  3) Analitza i Exporta (al final)
        barra = QToolBar("Treball")
        barra.setObjectName("barra_principal")
        barra.setMovable(False)
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
        barra.addWidget(self.b_analitza_beats)
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
        # El panell de tipus d'acord arrenca tancat; s'obri des de Visualitza.
        self.dock_xifrat.setVisible(False)

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
        # Els camps de text no han de capturar el drop d'àudio.
        self._desactiva_drops_fills()

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


    def obre_carpeta_registre(self):
        """Obre la carpeta on viu el log de l'app (per reportar errors de beta)."""
        d = os.path.dirname(config.LOG_PATH) or "."
        if os.path.isdir(d):
            QDesktopServices.openUrl(QUrl.fromLocalFile(d))
        else:
            self.avisa_info("Auto Chords", f"No trobo la carpeta del registre:\n{d}")

    def _beat_unit_val(self):
        cb = getattr(self, "cb_beat", None)
        return bpm_unit_mod.normalitza(cb.currentData() if cb else None)

    def _posa_beat_unit(self, unit):
        cb = getattr(self, "cb_beat", None)
        if cb is None:
            return
        idx = cb.findData(bpm_unit_mod.normalitza(unit))
        if idx >= 0:
            cb.blockSignals(True)
            cb.setCurrentIndex(idx)
            cb.blockSignals(False)

    def _canvia_beat_unit(self, _idx=None):
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            vr.set_beat_unit(self._beat_unit_val())
        self._marca_dirty()
        self.registra(f"Beat/TAP: {self._beat_unit_val()}")

    def _latencia_cursor_val(self):
        """Retard visual del cursor (ms) desat a les opcions del projecte."""
        rep = self.opcions.get("reproduccio") or {}
        try:
            return max(0.0, min(1000.0, float(
                rep.get("latencia_cursor_ms", 0.0))))
        except (TypeError, ValueError):
            return 0.0

    def _ajusta_latencia_cursor(self):
        """Calibratge manual del cursor respecte al so (un sol valor)."""
        vr = getattr(self, "visor_ref", None)
        actual = self._latencia_cursor_val()
        val, ok = QInputDialog.getDouble(
            self, "Retard global de reproducció",
            "Mil·lisegons de retard global per a cursor, llistes, temps i "
            "ressaltat (0 = sense compensació; apuja'l si el que es veu va "
            "per davant del so):",
            actual, 0.0, 500.0, 1)
        if not ok:
            return
        self.opcions.setdefault("reproduccio", {})[
            "latencia_cursor_ms"] = float(val)
        dialegs.desa_opcions(self.opcions)
        if vr is not None:
            vr.set_latencia_cursor_ms(val)
        self._marca_dirty()
        self.registra(f"Reproducció: retard global de {float(val):.0f} ms")

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
                     None if bpm is None else f"{float(bpm):.3f}"),
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

    def _quantitza_bpm_ui(self, decimals=None):
        """Quantitza només els clips normals de BPM amb 0, 1 o 2 decimals."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.avisa_info("Quantitza BPM", "Obre un projecte primer.")
            return False
        if not getattr(vr, "tempo_fix", False):
            self.avisa_info("Quantitza BPM",
                            "Cal el mode BPM · compàs.")
            return False
        if decimals is None:
            opcions = ("Sense decimals", "1 decimal", "2 decimals")
            triat, ok = QInputDialog.getItem(
                self, "Quantitza BPM",
                "Decimals del BPM:", opcions, 1, False)
            if not ok:
                return False
            decimals = {"Sense decimals": 0, "1 decimal": 1,
                        "2 decimals": 2}[triat]
        decimals = max(0, min(2, int(decimals)))
        ok = bool(vr.quantitza_bpm(decimals))
        if ok:
            self._sincronitza_temps_del_visor()
            txt = ("sense decimals" if decimals == 0
                   else f"{decimals} decimal" + ("" if decimals == 1 else "s"))
            self._missatge_info(
                f"BPM quantitzat {txt}; els rubatos no s'han quantitzat i "
                "les fronteres s'han reencaixat.")
        else:
            self._missatge_info("Quantitza BPM: sense canvis.")
        return ok


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



    def registra(self, t):
        self.logger.info("UI: %s", t)
        self.log.append(t)

    # ---------------- MARCADORS EN VIU (compàs i secció) ----------------


    def _obre_guia_rapida(self):
        """Guia de benvinguda (només informació, sense tocar el model)."""
        dlg = dialeg_guia_rapida.DialegGuiaRapida(self)
        dlg.exec_()

    # --- estació d'audició (guiat v2) --------------------------------------

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

        1. Tecles de tall: **`+`** (tempo + estructura), **`Enter`** (només
           tempo), **`0`** (només estructura) i **`M`** (marcador lliure). Si
           s'està escrivint en un camp, la tecla s'hi escriu normalment.
        2. **Clic** dins la caixa d'informació (només lectura): pausa el
           rotatori i passa de pantalla sense esperar.
        3. **Drag & drop d'àudio** sobre qualsevol fill que accepti drops
           (camps de text, log…): el desviem a l'obertura d'àudio en lloc de
           deixar que s'hi enganxe la ruta com a text. La finestra principal
           (quan el destí és ella) va pels seus `drag*Event`.
        """
        tipus_drag = (QEvent.DragEnter, QEvent.DragMove, QEvent.Drop,
                      QEvent.DragLeave)
        if (ev.type() in tipus_drag
                and isinstance(obj, QWidget)
                and obj is not self
                and obj.window() is self):
            try:
                if ev.type() == QEvent.DragEnter:
                    if self._drag_entra(ev):
                        return True
                elif ev.type() == QEvent.DragMove:
                    if self._drag_mou(ev):
                        return True
                elif ev.type() == QEvent.Drop:
                    if self._drag_deixa(ev):
                        return True
                else:
                    self.statusBar().clearMessage()
            except (RuntimeError, AttributeError):
                pass
        try:
            if (ev.type() == QEvent.KeyPress
                    and getattr(self, "visor_ref", None) is not None
                    and isinstance(obj, QWidget)
                    and obj.window() is self):
                tecla, txt, mods = ev.key(), ev.text(), ev.modifiers()
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
                    return False
                es_plus = (tecla == Qt.Key_Plus
                           or (tecla == Qt.Key_Equal
                               and (txt == "+" or mods & Qt.ShiftModifier)))
                if es_plus:
                    # El MATEIX esdeveniment pot passar dos voltes pel filtre
                    # (el camp el rebutja i puja al pare): la segona no compta.
                    if getattr(self, "_plus_ev", None) is ev:
                        return True
                    self._plus_ev = ev
                    self._talla_tempo_i_estructura_cursor()
                    return True
                if tecla == Qt.Key_M:
                    self._marcador_cursor()
                    return True
                if tecla == Qt.Key_0:
                    self._talla_estructura_cursor()
                    return True
                if tecla in (Qt.Key_Return, Qt.Key_Enter):
                    # Enter només al timeline/visor: en formularis i diàlegs
                    # ha de continuar confirmant el camp o el botó.
                    vr = getattr(self, "visor_ref", None)
                    w2 = obj
                    while w2 is not None:
                        if w2 is getattr(vr, "timeline", None):
                            self._talla_tempo_cursor()
                            return True
                        w2 = w2.parentWidget()
        except (RuntimeError, AttributeError):
            pass
        caixa = getattr(self, "info_box", None)
        if (caixa is not None
                and obj in (caixa, caixa.viewport())
                and ev.type() == QEvent.MouseButtonPress):
            self._clic_info_box()
            return True         # el clic no ha de moure el cursor de text
        return super().eventFilter(obj, ev)


    # ---- accions d'edició des del menú (reutilitzen la lògica existent) ----

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
        dlg = dialegs.DialegTempoMapa(self, trams, vr._durada_wav())
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
        info = getattr(self, "_beats_actuals", None)
        temps = list(info.get("beats") or ()) if isinstance(info, dict) else []
        if temps:
            self.registra(
                f"detecta tempo: {len(temps)} beats del resultat d'Analitza "
                "BPM (sense tornar a detectar)")
        else:
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

    def _talla_i_offset(self, t, primer_a_compas=False):
        """Offset del compàs 1 al cursor + tall del carril de tempo (1 desfer).

        El **clip de tempo** nou (si el cursor no era ja una frontera) arrenca
        exactament a `t`. Si `primer_a_compas`, el pre-roll es recalcula com
        un compàs sencer amb el BPM més pròxim al clip musical següent.
        Retorna `(trams, idx)` o `None` si no hi ha visor.
        """
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return None
        durada = vr._durada_wav()
        t = max(0.0, min(float(t), durada))
        nous = tempo_map.parteix_trams_a(list(vr.tempo_trams or []), t, durada)
        if primer_a_compas:
            # El primer clip és el pre-roll: en fixar el compàs 1, ha de
            # quedar com un compàs sencer amb el BPM més pròxim possible al
            # clip musical següent (p. ex. 2/4 en un pre-roll curt).
            nous = tempo_map.ajusta_primer_clip_a_compas(nous, durada, t)
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
        res = self._talla_i_offset(t, primer_a_compas=True)
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
        # L'offset és part del document (`tempo.offset`), no del CSV de
        # mapa. Cal desar-lo immediatament perquè reobrir no el perda.
        self._desa_meta_silencios()
        if len(res[0]) > 2:
            self.registra("Atenció: el mapa té trams interiors — comprova "
                          "que les fronteres caiguen en línia de compàs "
                          "(o passa l'Anàlisi guiat).")

    def _downbeat_del_resultat(self):
        """Primer downbeat del resultat d'Analitza BPM, si n'hi ha.

        Mateixa regla que `pipeline.detecta_compas1`: el primer bar a partir
        del primer beat (marge 0,35 s). Així el compàs 1 i les línies de
        downbeats ixen del **mateix** resultat de detecció.
        """
        info = getattr(self, "_beats_actuals", None)
        if not isinstance(info, dict):
            return None
        bars = []
        for b in (info.get("downbeats") or ()):
            try:
                b = float(b)
            except (TypeError, ValueError):
                continue
            if math.isfinite(b):
                bars.append(b)
        if not bars:
            return None
        inici = 0.0
        for b in (info.get("beats") or ()):
            try:
                b = float(b)
            except (TypeError, ValueError):
                continue
            if math.isfinite(b):
                inici = b
                break
        marge = 0.35
        cand = [b for b in bars if b >= inici - marge]
        return float(cand[0] if cand else bars[0])

    def _detecta_compas1(self):
        """Detecta el compàs 1 (primer downbeat) i hi posa l'offset.

        Si hi ha un resultat d'Analitza BPM, usa el seu primer downbeat. Si no,
        usa el detector d'onsets + compassos del Queen Mary
        (`pipeline.detecta_compas1`). No toca el BPM.
        """
        wav = self.wav_edit.text().strip()
        if not wav or not os.path.isfile(wav):
            self.avisa("Compàs 1", "Primer tria un àudio.")
            return
        self._atura_si_sona("detecció del compàs 1")
        seg = self._downbeat_del_resultat()
        if seg is not None:
            self.registra(
                f"compàs 1: downbeat guardat a {seg:.3f}s "
                "(resultat d'Analitza BPM)")
        else:
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




    # ---- Drag & drop d'àudio des de l'explorador de fitxers -----------------
    def dragEnterEvent(self, ev):
        if not self._drag_entra(ev):
            super().dragEnterEvent(ev)

    def dragMoveEvent(self, ev):
        if not self._drag_mou(ev):
            super().dragMoveEvent(ev)

    def dragLeaveEvent(self, ev):
        self.statusBar().clearMessage()
        super().dragLeaveEvent(ev)

    def dropEvent(self, ev):
        if not self._drag_deixa(ev):
            super().dropEvent(ev)





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
