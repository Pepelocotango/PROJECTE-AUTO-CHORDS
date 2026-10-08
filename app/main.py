#!/usr/bin/env python3
# main.py — Auto Chords (PyQt5/Qt5: l'únic Qt que corre al Q9400) —
#           wav -> acords + estructura -> carpetes. Tot en català.
import logging
import os
import sys
import time
import tempfile
import traceback

from PyQt5.QtCore import QThread, Qt, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QCursor, QDesktopServices, QKeySequence
from PyQt5.QtWidgets import (
    QAction, QApplication, QButtonGroup, QCheckBox, QFileDialog, QDockWidget,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QInputDialog, QMessageBox, QProgressBar, QPushButton, QShortcut, QSlider,
    QDialog,
    QTextEdit,
    QStackedWidget, QToolBar,
    QVBoxLayout, QWidget,
)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(APP_DIR)
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
import ffmpeg  # noqa: E402
import partitura  # noqa: E402
import pipeline  # noqa: E402
import postproc  # noqa: E402
import theme  # noqa: E402
from . import config  # noqa: E402
from . import dialegs  # noqa: E402
from . import icones  # noqa: E402
from . import plataforma  # noqa: E402
from . import visor as visor_mod  # noqa: E402

# Sempre a un directori ESCRIPTIBLE: en una AppImage muntada la carpeta del
# projecte és de només lectura i escriure-hi el log petava a l'arrencada.
DEFAULT_LOG_PATH = config.LOG_PATH


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


class Feina(QThread):
    missatge = pyqtSignal(str)
    progres = pyqtSignal(int)
    feta = pyqtSignal(bool, str)

    def __init__(self, wav, sortida, bpm, bpb, offset, amb_estructura,
                 tempo_fix=True, opcions=None):
        super().__init__()
        self.wav = wav
        self.sortida = sortida
        self.bpm = bpm
        self.bpb = bpb
        self.offset = offset
        self.amb_estructura = amb_estructura
        self.tempo_fix = tempo_fix
        self.opcions = opcions or {}

    def log(self, t):
        self.missatge.emit(t)

    def run(self):
        """ANALITZA: nomes extreu els CSVs. Les wavs es generen a l'EXPORTAR.

        Disseny (decisio de l'operador): les `wavs_acords/`/`wavs_estructura/`
        no tenen cap paper en la visualitzacio ni l'edicio; son l'ULTIM pas.
        Aqui nomes es creen `acords.csv`, `segments.csv` i `estructura_ABC.csv`
        (els locators/guia i les wavs els fa `pipeline.exporta_total`).
        """
        try:
            os.makedirs(self.sortida, exist_ok=True)
            csv_ac = os.path.join(self.sortida, "acords.csv")
            self.log("1/3 extreu acords (Chordino)...")
            pipeline.extract_chords(self.wav, csv_ac, self.log,
                                    params=(self.opcions.get("chords") or None))
            # Neteja posterior dels acords (opcions del dialeg).
            cl = self.opcions.get("clean") or {}
            if cl:
                self.log("1b/3 neteja dels acords...")
                postproc.processa_acords_csv(
                    csv_ac,
                    durada_min=float(cl.get("durada_min", 0.0)),
                    fusiona_iguals=bool(cl.get("fusiona_iguals", True)),
                    sense_baix=bool(cl.get("sense_baix", False)),
                    reduir=bool(cl.get("reduir", False)),
                    snap=bool(cl.get("snap", False)),
                    bpm=self.bpm, bpb=self.bpb, offset=self.offset,
                    divisio=int(cl.get("divisio", 1)), log=self.log)
            self.progres.emit(50)
            csv_seg = None
            if self.amb_estructura:
                csv_seg = os.path.join(self.sortida, "segments.csv")
                self.log("2/3 extreu estructura (qm-segmenter)...")
                pipeline.extract_segments(
                    self.wav, csv_seg, self.log,
                    motor=(self.opcions.get("structure") or {}).get(
                        "motor", "qm"))
                self.progres.emit(75)
                self.log("3/3 ABC (estructura)...")
                abc = os.path.join(self.sortida, "estructura_ABC.csv")
                _est = self.opcions.get("structure") or {}
                pipeline.fer_abc(csv_seg, abc, self.bpm, self.log,
                                 lliure=not self.tempo_fix, bpb=self.bpb,
                                 offset=self.offset,
                                 durada_min=float(_est.get("durada_min", 0.0)),
                                 fusiona_iguals=bool(_est.get("fusiona_iguals", True)))
            self.log("Analisi feta. Les wavs es generaran en 'Exporta'.")
            self.progres.emit(100)
            self.feta.emit(True, self.sortida)
        except Exception as e:  # noqa: BLE001
            self.feta.emit(False, str(e))


class Finestra(QMainWindow):
    # Els `except Exception` d'aquesta classe protegeixen accions de l'usuari:
    # sempre registren l'error i/o mostren un diàleg, mai l'amaguen.
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("auto_chords")
        self.opcions = dialegs.carrega_opcions()    # ultimes opcions d'autodeteccio
        self.wav_original = ""                     # si ve d'un format convertit
        self._info_msg_fins = 0.0                  # missatge transitori info box
        self.setWindowTitle("Auto Chords — wav → acords + estructura")
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
        b_obre = QPushButton("Obre…")
        b_obre.setObjectName("secundari")
        b_obre.setToolTip("Obre una WAV (Ctrl+O)")
        b_obre.clicked.connect(self.tria_wav)

        # 2. temps i paràmetres — BARRA compacta d'una sola línia (estil DAW)
        #    (abans era un QGroupBox «2 · Temps i paràmetres»)
        self.b_mode_bpm = QPushButton("BPM · compàs")
        self.b_mode_bpm.setCheckable(True)
        self.b_mode_bpm.setChecked(True)
        self.b_mode_bpm.setToolTip("Treballar amb BPM i compassos.")
        self.b_mode_lliure = QPushButton("Lliure")
        self.b_mode_lliure.setCheckable(True)
        self.b_mode_lliure.setToolTip("Treballar amb temps real hh:mm:ss (sense compassos).")
        grp_mode = QButtonGroup(self)
        grp_mode.setExclusive(True)
        grp_mode.addButton(self.b_mode_bpm)
        grp_mode.addButton(self.b_mode_lliure)
        self.b_mode_bpm.clicked.connect(lambda: self._canvia_mode_temps(True))
        self.b_mode_lliure.clicked.connect(lambda: self._canvia_mode_temps(False))

        # camps d'entrada MANUAL de text (sense fletxes ▲▼)
        self.bpm = QLineEdit("120.0")
        self.bpm.setMaximumWidth(70)
        self.bpm.setPlaceholderText("120.0")
        self.bpm.setToolTip("BPM del tema. Entrada manual (text).")
        self.bpb = QLineEdit("4")
        self.bpb.setMaximumWidth(40)
        self.bpb.setPlaceholderText("4")
        self.bpb.setToolTip("Temps per compàs (p. ex. 4).")
        self.offset = QLineEdit("0.0")
        self.offset.setMaximumWidth(60)
        self.offset.setPlaceholderText("0.0")
        self.offset.setToolTip("Offset del compàs 1, en segons.")
        self.b_detecta = QPushButton(" Detecta")
        self.b_detecta.setIcon(icones.ico("target"))
        self.b_detecta.setIconSize(icones.pm_mida(16))
        self.b_detecta.setObjectName("secundari")
        self.b_detecta.setToolTip("Detecta el BPM automàticament (motor triable).")
        self.b_detecta.clicked.connect(lambda: self._detecta_bpm())
        for camp in (self.bpm, self.bpb, self.offset):
            camp.editingFinished.connect(self._aplica_parametres_temps)

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
            b.setMaximumWidth(46)
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
        hp.addWidget(QLabel("Compàs:"))
        hp.addWidget(self.bpb)
        hp.addWidget(QLabel("Offset:"))
        hp.addWidget(self.offset)                 # segons
        self.b_offset_cursor = QPushButton()
        self.b_offset_cursor.setIcon(icones.ico("map-pin"))
        self.b_offset_cursor.setObjectName("secundari")
        self.b_offset_cursor.setToolTip(
            "Posa l'offset a la posició del cursor vermell (compàs 1 aquí)")
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
        self.amb_est.setChecked(True)
        self.amb_est.setToolTip("Genera la jerarquia de seccions i l’ABC de l’estructura del tema.")

        # "Inclou la partitura": accio commutable al menu Fitxer. Per defecte NO
        # (el render amb MuseScore pot trigar); es tolerant si falta MuseScore.
        self.amb_part = QAction("Inclou la partitura (xifrat)", self)
        self.amb_part.setCheckable(True)
        self.amb_part.setChecked(False)
        self.amb_part.setToolTip(
            "En exportar, genera tambe un lead sheet de xifrats: MusicXML i, si "
            "hi ha MuseScore, PDF/MSCZ. Nomes en mode BPM · compàs.")

        # "Tonalitat automàtica": calcula l'armadura (fifths) amb el
        # qm-keydetector abans de generar la partitura. Opcional i per defecte
        # NO (triga uns segons); només té efecte si «Inclou la partitura» està
        # marcat.
        self.tonalitat_auto = QAction("Tonalitat automàtica (qm-keydetector)", self)
        self.tonalitat_auto.setCheckable(True)
        self.tonalitat_auto.setChecked(False)
        self.tonalitat_auto.setToolTip(
            "Detecta la tonalitat amb el qm-keydetector i posa l'armadura a la "
            "partitura. Si falla, surt sense armadura (no trenca res).")

        # estat `tempo_fix` (ocult): el visor i la resta de codi el consulten
        self.tempo_fix = QCheckBox()
        self.tempo_fix.setChecked(True)
        self.tempo_fix.setVisible(False)
        self.tempo_fix.toggled.connect(self._canvia_tempo)

        # 3. «Analitza» i «Exporta» són ACCIONS (no passos d'assistent).
        self.b_exec = QPushButton("Analitza")
        self.b_exec.setObjectName("principal")
        self.b_exec.setToolTip("Extreu acords i estructura de la WAV (F5)")
        self.b_exec.clicked.connect(lambda: self.executa())
        self.b_exec.setEnabled(False)          # fins que hi hagi WAV
        self.b_export = QPushButton("Exporta")
        self.b_export.setToolTip("Exporta el paquet final (Ctrl+E)")
        self.b_export.setEnabled(False)       # fins que hi hagi pistes
        self.b_export.clicked.connect(self.exporta)

        # 1a BARRA: en ORDRE DE FLUX de treball →
        #   1) Obre  ·  2) opcions de temps  ·  3) Analitza i Exporta (al final)
        barra = QToolBar("Treball")
        barra.setObjectName("barra_principal")
        barra.setMovable(False)
        barra.addWidget(b_obre)
        barra.addSeparator()
        barra.addWidget(self.b_mode_bpm)
        barra.addWidget(self.b_mode_lliure)
        barra.addSeparator()
        barra.addWidget(self._params_temps)
        barra.addSeparator()
        barra.addWidget(self.b_exec)
        barra.addWidget(self.b_export)
        self.addToolBar(Qt.TopToolBarArea, barra)
        self.barra_principal = barra
        self.barra_temps = barra

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
        self.log_dock.setVisible(True)      # sortida de l'anàlisi, visible
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)

        # (L'inspector lateral s'ha retirat: les llistes tornen sota l'ona,
        #  dins el visor, que és on tenen l'espai natural.)

        # 5. BARRA DE TRANSPORT única (fora del visor). Reutilitza els
        #    mètodes del visor (play_stop, stop_inici, ves_a, marca_A/B,
        #    commuta_loop, zoom, zoom_tot, commuta_mut): no es reescriu res.
        barra_transport = QToolBar("Transport")
        barra_transport.setObjectName("barra_transport")
        barra_transport.setMovable(False)
        self._crea_transport(barra_transport)
        # 2 files: fila 1 = opcions + Analitza/Exporta; fila 2 = transport.
        self.addToolBarBreak(Qt.TopToolBarArea)
        self.addToolBar(Qt.TopToolBarArea, barra_transport)
        self.barra_transport = barra_transport

        self.sortida = ""
        self.b_export.setEnabled(False)
        # Drecera: espai = play/pausa (a la finestra principal, perquè el
        # visor està incrustat i el seu propi QShortcut no s'activaria).
        self._sc_play = QShortcut(QKeySequence(Qt.Key_Space), self)
        self._sc_play.activated.connect(self._toggle_play)
        self._taps = []                       # instants dels taps (tap tempo)
        self._sc_tap = QShortcut(QKeySequence(Qt.Key_T), self)
        self._sc_tap.activated.connect(self._tap_tempo)
        self._crea_menus()
        for p in (pipeline.SONIC, pipeline.ACORDS_PY,
                  *pipeline.VAMP_DIRS):
            if not os.path.exists(p):
                self.registra(f"AVÍS: no trobo {p}")

    def _missatge_info(self, text):
        """Mostra un missatge transitori a la caixa d'informacio (no el
        sobreescriu el ratoli fins passats uns segons)."""
        import time as _t
        self.info_box.setHtml(
            f"<b style='color:{theme.BLAU_INFO}'>{text}</b>")
        self._info_msg_fins = _t.monotonic() + 4.0

    def _on_play_state(self, on):
        """Icona del boto de transport: ▶ aturat / ⏸ sonant."""
        if hasattr(self, "b_play_tb"):
            self.b_play_tb.setIcon(icones.ico("pause" if on else "play", 16))
            self.b_play_tb.setToolTip("Atura  (Espai)" if on
                                      else "Reprodueix  (Espai)")

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
        self._act(m, "Obre WAV…", "Ctrl+O", self.tria_wav)
        m.addSeparator()
        self._act(m, "Exporta…", "Ctrl+E", self.exporta)
        self._act(m, "Exporta la partitura…", "", self.exporta_partitura_ara)
        m.addAction(self.amb_part)      # Inclou la partitura (commutable)
        m.addAction(self.tonalitat_auto)  # Tonalitat automàtica (commutable)
        self._act(m, "Obre la carpeta de sortida", "", self.obre_carpeta)
        m.addSeparator()
        self._act(m, "Surt", "Ctrl+Q", self.close)
        # --- Edita ---
        m = mb.addMenu("&Edita")
        self._act(m, "Desfer", "Ctrl+Z", self._undo_visor)
        self._act(m, "Refer", "Ctrl+Y", self._redo_visor)
        self._act(m, "Refer (alternatiu)", "Ctrl+Shift+Z", self._redo_visor)
        m.addSeparator()
        self._act(m, "Afegeix acord…", "Ctrl+Shift+A", self._afegeix_acord_ui)
        self._act(m, "Afegeix secció…", "Ctrl+Shift+S", self._afegeix_seccio_ui)
        m.addSeparator()
        self._act(m, "Elimina element", "Del", self._elimina_element)
        self._act(m, "Duplica element", "Ctrl+D", self._duplica_element)
        self._act(m, "Reanomena element", "F2", self._renomena_element)
        m.addSeparator()
        self._act(m, "Paràmetres…", "", self._focus_parametres)
        # --- Selecciona ---
        m = mb.addMenu("&Selecciona")
        self._act(m, "Selecciona l'acord del cursor", "", self._sel_acord_cursor)
        self._act(m, "Selecciona la secció del cursor", "", self._sel_seccio_cursor)
        m.addSeparator()
        self._act(m, "Marca inici de loop (A)", "Ctrl+[", self._marca_A_visor)
        self._act(m, "Marca fi de loop (B)", "Ctrl+]", self._marca_B_visor)
        self._act(m, "Neteja el loop", "", self._neteja_loop)
        self._act(m, "Activa/desactiva loop", "", self._loop_visor)
        # --- Visualitza ---
        m = mb.addMenu("&Visualitza")
        self._act(m, "Zoom +", "Ctrl++", lambda: self._zoom_visor(0.5))
        self._act(m, "Zoom −", "Ctrl+-", lambda: self._zoom_visor(2.0))
        self._act(m, "Zoom total", "Ctrl+0", self._zoom_tot_visor)
        m.addSeparator()
        # (El visor és ara el widget central: ja no cal «Mostra el visor»)
        m.addAction(self.log_dock.toggleViewAction())
        self.log_dock.toggleViewAction().setText("Mostra el log")
        m.addSeparator()
        self.a_metro = self._act(m, "Metrònom", "", self._toggle_metro, checkable=True)
        self.a_metro.setToolTip("Clic de metrònom (només en mode BPM · compàs)")
        # --- Analitza ---
        m = mb.addMenu("&Analitza")
        self._act(m, "Analitza l'àudio", "F5", lambda: self.executa())
        m.addSeparator()
        self._act(m, "Detecta el compàs 1 automàticament", None,
                    lambda: self._detecta_compas1())
        self._act(m, "Marca el compàs 1 aquí", "", self._marca_compas_1)
        m.addSeparator()
        m.addAction(self.amb_est)      # Inclou estructura (commutable)
        # --- Ajuda ---
        m = mb.addMenu("A&juda")
        self._act(m, "Dreceres de teclat", "", self._mostra_dreceres)
        self._act(m, "Quant a Auto Chords", "", self._quant_a)

    def _undo_visor(self):
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            vr.undo()
        else:
            self.registra("Edita: no hi ha visor carregat")

    def _redo_visor(self):
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            vr.redo()
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

    def _mostra_dreceres(self):
        QMessageBox.information(self, "Dreceres de teclat",
            "<b>Reproducció</b><br>"
            "Espai — play / pausa<br><br>"
            "<b>Edició</b><br>"
            "Ctrl+Z — desfer<br>"
            "Ctrl+Y / Ctrl+Shift+Z — refer<br><br>"
            "<b>Visor</b><br>"
            "Roda del ratolí — zoom<br>"
            "Botó dret arrossegant — desplaçar (pan)<br>"
            "Arrossega sobre el regle — loop A/B<br>"
            "Clic a un clip — posa el cursor al seu inici")

    def _quant_a(self):
        QMessageBox.about(self, "Quant a Auto Chords",
            "<b>Auto Chords</b><br>"
            "wav → acords + estructura<br><br>"
            "Visor DAW-like (PyQt5).<br>"
            "Motor: Chordino (acords) + Queen Mary/qm (estructura) · Vamp.")

    def registra(self, t):
        self.logger.info("UI: %s", t)
        self.log.append(t)

    # ---- lectura manual dels camps de text ----
    @staticmethod
    def _llegeix_num(w, defecte, minim, maxim, enter=False):
        try:
            v = float(str(w.text()).replace(",", ".").strip())
        except (ValueError, AttributeError):
            return defecte
        v = max(minim, min(maxim, v))
        return int(round(v)) if enter else v

    def _bpm_val(self):
        # rang ampli (30-400): els botons ×2/÷2 i el metrònom (BPM_MAX=400)
        # ho necessiten; abans 40-240 tallava el doble de temes ràpids.
        return self._llegeix_num(self.bpm, 120.0, 30, 400)

    def _bpb_val(self):
        return self._llegeix_num(self.bpb, 4, 2, 12, enter=True)

    def _offset_val(self):
        return self._llegeix_num(self.offset, 0.0, 0.0, 60.0)

    def _cb_a_secs(self, text):
        """'C.B' (compàs.beat) -> segons a la graella ORIGINAL (offset=0)."""
        import re
        m = re.match(r"\s*(-?\d+)\s*[.,]\s*(\d+)\s*$", str(text))
        if not m:
            return None
        c, b = int(m.group(1)), int(m.group(2))
        beat_len = 60.0 / max(self._bpm_val(), 1e-9)
        n = (c - 1) * max(1, self._bpb_val()) + (b - 1)
        return max(0.0, min(60.0, n * beat_len))

    def _secs_a_cb(self, t):
        """Segons -> 'C.B' a la graella ORIGINAL (offset=0)."""
        beat_len = 60.0 / max(self._bpm_val(), 1e-9)
        bpb = max(1, self._bpb_val())
        beats = float(t) / beat_len
        c = int(beats // bpb) + 1
        b = int(round(beats % bpb)) + 1
        if b > bpb:
            c += 1
            b = 1
        return f"{c}.{b}"

    def _offset_cb_canviat(self):
        """L'usuari ha escrit el camp compàs.beat -> passa-ho a segons."""
        s = self._cb_a_secs(self.offset_cb.text())
        if s is None:
            return
        self.offset.setText(f"{s:.2f}")
        self._aplica_parametres_temps()

    def _canvia_mode_temps(self, bpm_compas):
        """Canvia entre mode BPM·compàs i mode Lliure (hh:mm:ss)."""
        self._params_temps.setVisible(bool(bpm_compas))
        self.tempo_fix.setChecked(bool(bpm_compas))
        self._actualitza_metro_ui()

    def _detecta_bpm(self, pregunta=True):
        """Obre el dialeg d'opcions de BPM i detecta (l'usuari pot editar-lo)."""
        wav = self.wav_edit.text().strip()
        if not wav or not os.path.isfile(wav):
            QMessageBox.warning(self, "Detecta BPM",
                                "Primer tria una WAV.")
            return
        if pregunta:
            dlg = dialegs.DialegOpcions(self, tab="bpm", opcions=self.opcions)
            if dlg.exec_() != QDialog.Accepted:
                return
            self.opcions = dlg.opcions()
            dialegs.desa_opcions(self.opcions)
        b = self.opcions.get("bpm", {})
        self._atura_si_sona("deteccio de BPM")
        self.registra("Detectant el BPM…")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            bpm = pipeline.detecta_bpm(
                wav, self.registra,
                bpm_min=b.get("min"), bpm_max=b.get("max"),
                preferit=(b.get("pref_min"), b.get("pref_max")),
                motor=b.get("motor", "nostre"))
        finally:
            QApplication.restoreOverrideCursor()
        if bpm:
            self.bpm.setText(f"{bpm:.1f}")
            self.registra(f"BPM detectat: {bpm:.1f} (pots editar-lo)")
        else:
            QMessageBox.information(
                self, "Detecta BPM",
                "No s'ha pogut estimar el BPM.\n"
                "Pot ser un tema en directe o molt irregular: escriu-lo a mà.")

    def _actualitza_info_widget(self):
        """Mostra a la caixa d'informacio el tooltip del widget sota el ratolí."""
        import time as _t
        if _t.monotonic() < getattr(self, "_info_msg_fins", 0.0):
            return          # hi ha un missatge transitori (desfer/refer...)
        try:
            w = QApplication.widgetAt(QCursor.pos())
        except Exception:  # noqa: BLE001
            # timer de hover (hot): fallback silenciós intencionat
            return
        if w is None:
            return
        # El VISOR (timeline) es un sol giny: li demanem la zona del ratoli
        # (el seu "ratoli intel·ligent") per explicar quina accio hi faria.
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            tv = getattr(vr, "timeline", None)
            if tv is not None and (w is tv or w is tv.viewport()):
                try:
                    pos = tv.viewport().mapFromGlobal(QCursor.pos())
                    html = f"<b>{tv.info_zona(pos)}</b>"
                    if self.info_box.toHtml() != html:
                        self.info_box.setHtml(html)
                except Exception:  # noqa: BLE001
                    # timer de hover (hot): fallback silenciós intencionat
                    pass
                return
        # pugem fins a un widget que tingui tooltip (els fills solen no tenir-ne)
        x = w
        while x is not None and not x.toolTip():
            x = x.parentWidget()
        if x is None:
            return
        nom = x.text() if hasattr(x, "text") else ""
        tip = x.toolTip()
        html = f"<b>{nom}</b><br>{tip}" if nom else f"<b>{tip}</b>"
        if self.info_box.toHtml() != html:
            self.info_box.setHtml(html)

    # ---- accions d'edició des del menú (reutilitzen la lògica existent) ----
    def _clip_seleccionat(self):
        """Retorna (kind, idx) de l'element seleccionat al timeline."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return None, -1
        for items, kind in ((vr.timeline._chord_items, "chord"),
                            (vr.timeline._section_items, "section")):
            for it in items:
                if getattr(it, "_selected", False):
                    return kind, getattr(it, "idx", -1)
        return None, -1

    def _elimina_element(self):
        kind, idx = self._clip_seleccionat()
        if kind is None:
            return
        vr = self.visor_ref
        if kind == "chord":
            vr._elimina_acord_index(idx)
        else:
            vr._elimina_seccio_index(idx)

    def _duplica_element(self):
        kind, idx = self._clip_seleccionat()
        if kind is None:
            return
        vr = self.visor_ref
        if kind == "chord":
            vr._duplica_acord_index(idx)
        else:
            vr._duplica_seccio_index(idx)

    def _renomena_element(self):
        kind, idx = self._clip_seleccionat()
        if kind is None:
            return
        tl = self.visor_ref.timeline
        if kind == "chord":
            tl.chordEditRequested.emit(idx)
        else:
            tl.sectionEditRequested.emit(idx)

    def _afegeix_acord_ui(self):
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return
        nom, ok = QInputDialog.getText(
            self, "Afegeix acord", f"Acord a {vr.pos:.2f} s", text="N")
        if not ok or not nom.strip():
            return
        try:
            vr._afegeix_acord(vr.pos, nom.strip())
            vr._desa_i_regenera()
            vr.timeline.set_data(vr.acords, vr.seccions)
            self.registra(f"afegit acord a {vr.pos:.2f}s: {nom.strip()}")
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Auto Chords", f"No s'ha pogut afegir:\n{e}")

    def _afegeix_seccio_ui(self):
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return
        lletra, ok = QInputDialog.getText(
            self, "Afegeix secció", f"Lletra a {vr.pos:.2f} s", text="A")
        if not ok or not lletra.strip():
            return
        try:
            vr._afegeix_seccio(vr.pos, vr.pos + 2.0, lletra.strip()[:1].upper())
            vr._regenera_abc_des_de_totes_les_seccions("secció afegida")
            vr.timeline.set_data(vr.acords, vr.seccions)
            self.registra(f"afegida secció a {vr.pos:.2f}s")
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Auto Chords", f"No s'ha pogut afegir:\n{e}")

    def _sel_acord_cursor(self):
        """Selecciona l'acord que conté la posició del cursor."""
        vr = getattr(self, "visor_ref", None)
        if vr is None or not vr.acords:
            return
        idx = 0
        for i, a in enumerate(vr.acords):
            if a[0] <= vr.pos:
                idx = i
            else:
                break
        vr.timeline.select_clip("chord", idx)

    def _sel_seccio_cursor(self):
        """Selecciona la secció que conté la posició del cursor."""
        vr = getattr(self, "visor_ref", None)
        if vr is None or not vr.seccions:
            return
        idx = 0
        for i, s in enumerate(vr.seccions):
            if s[0] <= vr.pos:
                idx = i
            else:
                break
        vr.timeline.select_clip("section", idx)

    def _neteja_loop(self):
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return
        vr.loop_a = vr.loop_b = None
        vr.loop_on = False
        if hasattr(vr, "b_loop"):
            vr.b_loop.setChecked(False)
        if hasattr(self, "tb_loop"):
            self.tb_loop.setChecked(False)
        vr.timeline.set_loop(None, None)
        self.registra("loop netejat")

    def _dobla_bpm(self, factor):
        """Multiplica (×2) o divideix (÷2) el BPM actual."""
        b = self._bpm_val() * float(factor)
        b = max(30.0, min(400.0, b))
        self.bpm.setText(f"{b:.1f}")
        self._aplica_parametres_temps()
        self.registra(f"BPM {'×2' if factor > 1 else '÷2'} → {b:.1f}")

    def _tap_tempo(self):
        """Tap tempo (com als DAWs): intervals dels ultims taps -> BPM.

        Segueix el patro estandard: reset si passa de 2 s (LMMS), mitjana
        dels ultims intervals i descart dels intervals fora de 30-300 BPM
        (Max/Dobrian) per ignorar dobles-taps i gaps llargs.
        """
        ara = time.monotonic()
        if self._taps and (ara - self._taps[-1]) > 2.0:
            self._taps = []                      # reset per timeout (2 s)
        self._taps.append(ara)
        if len(self._taps) > 8:
            self._taps = self._taps[-8:]         # finestra dels ultims 8
        if len(self._taps) < 2:
            self.b_tap.setText("TAP (1)")
            return
        ivs = [b - a for a, b in zip(self._taps, self._taps[1:])]
        ivs = [x for x in ivs if 0.2 <= x <= 2.0]   # 30-300 BPM
        if not ivs:
            self.b_tap.setText(f"TAP ({len(self._taps)})")
            return
        bpm = 60.0 / (sum(ivs) / len(ivs))
        self.bpm.setText(f"{bpm:.1f}")
        # propaga al visor (regle + clic) SENSE reengegar l'audio en curs
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            vr.bpm = self._bpm_val()
            vr._actualitza_temps()
        self.b_tap.setText(f"TAP ({len(self._taps)}) {bpm:.0f}")
        self.registra(f"tap tempo: {bpm:.1f} BPM ({len(self._taps)} taps)")

    def _marca_compas_1(self):
        """Posa l'offset a la posició del cursor: la graella hi comença.

        Aixi el regle, el metrònom i l'export queden alineats amb la música.
        """
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return
        off = float(vr.pos)
        self.offset.setText(f"{off:.2f}")
        self._aplica_parametres_temps()      # propaga + actualitza el camp cb
        self.registra(f"Compàs 1 marcat a {off:.2f}s")

    def _detecta_compas1(self):
        """Detecta el compàs 1 (primer downbeat) i hi posa l'offset.

        Usa el detector d'onsets + el de compassos del Queen Mary
        (`pipeline.detecta_compas1`). No toca el BPM.
        """
        wav = self.wav_edit.text().strip()
        if not wav or not os.path.isfile(wav):
            QMessageBox.warning(self, "Compàs 1", "Primer tria un àudio.")
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
            QMessageBox.information(
                self, "Compàs 1",
                "No s'ha pogut detectar el compàs 1.\n"
                "Pots posar-lo a mà amb el botó 📍 (al cursor).")
            return
        self.offset.setText(f"{seg:.2f}")
        self._aplica_parametres_temps()
        self.registra(f"Compàs 1 detectat a {seg:.2f}s ✔")

    def _aplica_parametres_temps(self):
        """Propaga BPM/compàs/offset al visor. Si sona, reengega perquè el
        metrònom segueixi la nova graella des de la posició actual."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return
        vr.bpm = self._bpm_val()
        vr.bpb = self._bpb_val()
        vr.offset = self._offset_val()
        self.offset_cb.setText(self._secs_a_cb(vr.offset))
        vr._actualitza_temps()
        self._reenvia_si_sona()

    def _reenvia_si_sona(self):
        """En canviar BPM/compàs amb la reproducció en marxa, reengega perquè
        el metrònom segueixi la nova graella des de la posició actual."""
        vr = getattr(self, "visor_ref", None)
        if vr is not None and getattr(vr, "sona", False):
            pos = vr.pos
            vr._atura_proc()
            vr._engega_des_de(pos)

    def _canvia_tempo(self, fix):
        for w in (self.bpm, self.bpb, self.offset):
            w.setEnabled(fix)
        if hasattr(self, "visor_ref") and self.visor_ref is not None:
            self.visor_ref.tempo_fix = bool(fix)
            self.visor_ref.bpm = self._bpm_val()
            self.visor_ref.bpb = self._bpb_val()
            self.visor_ref._actualitza_temps()
            self.visor_ref.timeline.set_tempo_mode(
                bool(fix), self._bpm_val(), self._bpb_val())

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
        base = os.path.splitext(os.path.basename(wav))[0]
        sortida = os.path.join(os.path.dirname(wav), base + "_ACORDS")
        if os.path.isdir(sortida):
            return sortida
        return ""

    def _carrega_visor(self, wav):
        self._atura_si_sona("recarrega del visor")
        if not wav or not os.path.isfile(wav):
            self.logger.warning("No s'ha pogut carregar la WAV: %s", wav)
            self.visor_ref = None
            self.b_exec.setEnabled(False)
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
            )
            self.visor_ref = visor
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
            self.visor_widget = visor.centralWidget()
            self.visor_widget.setParent(self._stack)
            if self._stack.indexOf(self.visor_widget) < 0:
                self._stack.addWidget(self.visor_widget)   # pagina 1 = visor
            self._stack.setCurrentWidget(self.visor_widget)
            self.visor_widget.show()
            self.b_exec.setEnabled(True)     # hi ha WAV -> es pot analitzar
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
        except Exception:  # noqa: BLE001
            self.logger.exception("Crash en carregar el visor per %s", wav)
            self.registra(f"Visor ERROR: {traceback.format_exc()}")
            self.visor_ref = None
            self._mostra_placeholder_visor()

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

    def tria_wav(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Tria un àudio", "", ffmpeg.filtre())
        if not ruta:
            return
        self.wav_original = ""
        try:
            treball = self._assegura_wav(ruta)
            if treball != ruta:
                self.wav_original = os.path.abspath(ruta)
            self.wav_edit.setText(treball)
            info = pipeline.wav_info(treball)
            self.sortida = self._detecta_sortida_wav(treball)
            self.logger.info("WAV seleccionada: %s | info=%s | sortida_detectada=%s", treball, info, self.sortida)
            self._actualitza_info_wav(treball, info)
            if self.wav_original:
                self.wav_info.setText(
                    self.wav_info.text() +
                    f"   ·   convertit de «{os.path.basename(self.wav_original)}»")
            self._carrega_visor(treball)
        except Exception as e:  # noqa: BLE001
            self.logger.exception("Àudio no vàlid: %s", ruta)
            self.wav_info.setText(f"No s'ha pogut obrir: {e}")
            self._mostra_placeholder_visor()

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
        bar.addSeparator()
        boto("🔍−", "Allunya el zoom", lambda: self._acc_visor("zoom", 2.0),
             icona="zoom-out")
        boto("🔍+", "Apropa el zoom", lambda: self._acc_visor("zoom", 0.5),
             icona="zoom-in")
        boto("Tot", "Zoom total (veure-ho tot)",
             lambda: self._acc_visor("zoom_tot"), icona="maximize")
        self.tb_mut = boto("🔇", "Silencia / reactiva el so",
                           lambda: None, checkable=True, icona="volume-x")
        self.tb_mut.setObjectName("mute")
        self.tb_mut.clicked.connect(
            lambda: self._acc_visor("set_mut", self.tb_mut.isChecked()))
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

    def _actualitza_metro_ui(self):
        """El metrònom només està disponible en mode BPM · compàs."""
        vr = getattr(self, "visor_ref", None)
        disponible = vr is not None and vr.metro_disponible()
        for w in (self.b_metro, self.vol_metro, self.a_metro):
            w.setEnabled(disponible)
        if not disponible:
            # en mode Lliure: desmarcat i amb tooltip explicatiu
            self.b_metro.setChecked(False)
            self.a_metro.setChecked(False)
            tip = "Només disponible en mode BPM · compàs"
            self.b_metro.setToolTip(tip)
            self.vol_metro.setToolTip(tip)
            self.a_metro.setToolTip(tip)
        else:
            self.b_metro.setToolTip("Metrònom")
            self.vol_metro.setToolTip("Volum del clic del metrònom (%)")
            self.a_metro.setToolTip("Clic de metrònom")

    def _actualitza_info_wav(self, ruta, info=None):
        """Nom del fitxer al títol i la info (durada/Hz) a la barra d'estat."""
        nom = os.path.basename(ruta)
        self.setWindowTitle(f"{nom} — Auto Chords")
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

    def executa(self, pregunta=True):
        wav = self.wav_edit.text().strip()
        if not wav or not os.path.isfile(wav):
            QMessageBox.warning(self, "Auto Chords",
                                "Tria un àudio vàlid primer.")
            return
        if not ffmpeg.es_wav_pcm16(wav):
            try:
                wav = self._assegura_wav(wav)
                self.wav_edit.setText(wav)
            except Exception as e:  # noqa: BLE001
                QMessageBox.critical(self, "Auto Chords",
                                     f"No s'ha pogut convertir: {e}")
                return
        if pregunta:
            dlg = dialegs.DialegOpcions(self, tab="acords",
                                        opcions=self.opcions)
            if dlg.exec_() != QDialog.Accepted:
                return
            self.opcions = dlg.opcions()
            dialegs.desa_opcions(self.opcions)
        self._atura_si_sona("analisi amb els plugins")
        base = os.path.splitext(os.path.basename(wav))[0]
        self.sortida = os.path.join(os.path.dirname(wav), base + "_ACORDS")
        self.log.clear()
        self.barra.setValue(0)
        self.registra(f"Sortida: {self.sortida}")
        self.b_exec.setEnabled(False)
        self.b_export.setEnabled(False)
        self.feina = Feina(wav, self.sortida, self._bpm_val(),
                           self._bpb_val(), self._offset_val(),
                           self.amb_est.isChecked(),
                           self.tempo_fix.isChecked(),
                           opcions=self.opcions)
        self.feina.missatge.connect(self.registra)
        self.feina.progres.connect(self.barra.setValue)
        self.feina.feta.connect(self.acabada)
        self.feina.start()

    def _executa_i_exporta_final(self):
        self.executa(pregunta=False)      # ja hem preguntat abans

    def acabada(self, be, dada):
        self.b_exec.setEnabled(True)
        if be:
            self.b_export.setEnabled(True)
            self.registra("FET ✅ — ara pots revisar el visor i fer «Exporta».")
            self.barra.setValue(100)
            wav = self.wav_edit.text().strip()
            if wav and os.path.isfile(wav):
                self._carrega_visor(wav)
        else:
            self.b_export.setEnabled(False)
            self.registra(f"ERROR: {dada}")
            self.log_dock.setVisible(True)    # en cas d'error, obrim el log
            QMessageBox.critical(self, "Auto Chords", dada)

    def exporta(self):
        wav = self.wav_edit.text().strip()
        if not self.sortida:
            if not wav or not os.path.isfile(wav):
                QMessageBox.warning(self, "Auto Chords",
                                    "Tria una wav vàlida abans d'exportar.")
                return
            base = os.path.splitext(os.path.basename(wav))[0]
            self.sortida = os.path.join(os.path.dirname(wav), base + "_ACORDS")

        csv_ac = os.path.join(self.sortida, "acords.csv")
        csv_seg = os.path.join(self.sortida, "segments.csv")
        if not os.path.isfile(csv_ac):
            if not wav or not os.path.isfile(wav):
                QMessageBox.warning(self, "Auto Chords",
                                    "No hi ha CSVs d'exportació. Fes 'Executa' primer.")
                return
            QMessageBox.information(
                self, "Auto Chords",
                "Encara no hi ha CSVs generats. Fes 'Executa' primer.")
            return

        amb_estructura = self.amb_est.isChecked() and os.path.isfile(csv_seg)
        try:
            self.registra(f"Exportant a: {self.sortida}")
            pipeline.exporta_total(
                csv_ac=csv_ac,
                csv_seg=csv_seg if amb_estructura else None,
                sortida=self.sortida,
                bpm=self._bpm_val(),
                bpb=self._bpb_val(),
                offset=self._offset_val(),
                sr=44100,
                log=self.registra,
                tempo_fix=self.tempo_fix.isChecked(),
                amb_estructura=amb_estructura,
            )
            if self.amb_part.isChecked():
                self._exporta_partitura()
            self.registra("Exportació feta ✅")
            QMessageBox.information(
                self, "Auto Chords",
                f"Exportació feta a:\n{self.sortida}")
            self.obre_carpeta()
        except Exception as e:  # noqa: BLE001
            self.registra(f"exporta ERROR: {e}")
            QMessageBox.critical(self, "Auto Chords",
                                 f"No s'ha pogut exportar:\n{e}")

    def _exporta_partitura(self):
        """Genera el lead sheet de xifrats de la carpeta de sortida.

        Es **tolerant**: `app/partitura.py` escriu sempre el MusicXML i, només
        si troba el MuseScore, el PDF/MSCZ. Cap error d'aquí no ha de fer caure
        l'exportació normal. Retorna el diccionari de resultats (o None).

        Si l'acció «Tonalitat automàtica» està marcada, calcula l'armadura amb
        `partitura.detecta_fifths` (qm-keydetector; tolerant: 0 si falla).
        """
        wav = self.wav_edit.text().strip() or None
        key_fifths = 0
        if self.tonalitat_auto.isChecked() and wav:
            key_fifths = partitura.detecta_fifths(wav, self.registra)
        try:
            res = partitura.exporta_partitura(
                self.sortida,
                log=self.registra,
                bpm=self._bpm_val(),
                bpb=self._bpb_val(),
                offset=self._offset_val(),
                wav=wav,
                key_fifths=key_fifths,
                new_system_each=4,     # 4 compassos per línia (lead sheet)
            )
            if res.get("error"):
                self.registra(f"partitura: sense resultat ({res['error']})")
            return res
        except Exception as e:  # noqa: BLE001
            self.registra(f"partitura ERROR: {e}")
            return None

    def exporta_partitura_ara(self):
        """Accio de menu: genera NOMES la partitura de la sortida actual."""
        if not self.sortida:
            QMessageBox.warning(self, "Auto Chords",
                                "Exporta primer (cal la carpeta de resultats).")
            return
        res = self._exporta_partitura()
        if not res or res.get("error"):
            QMessageBox.warning(
                self, "Auto Chords",
                "No s'ha pogut generar la partitura.\n"
                "Cal haver exportat abans, en mode BPM · compàs "
                "(hi ha d'haver acords_locators.txt). Detall al log.")
            return
        ruta = res.get("musicxml") or res.get("pdf") or self.sortida
        QMessageBox.information(self, "Auto Chords",
                                f"Partitura generada:\n{ruta}")
        self.obre_carpeta()

    def obre_carpeta(self):
        if self.sortida and os.path.isdir(self.sortida):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.sortida))
        else:
            QMessageBox.information(self, "Auto Chords",
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

    lock_path = os.path.join(tempfile.gettempdir(), "auto_chords_single_instance.lock")
    lock_file = open(lock_path, "w", encoding="utf-8")
    if not plataforma.bloqueja_instancia_unica(lock_file):
        logger.warning("Ja hi ha una instància d'Auto Chords en execució; s'aborta la segona.")
        print("[main] Auto Chords ja està en execució; no es permet iniciar-ne una segona instància.", file=sys.stderr)
        lock_file.close()
        return 1

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(FOSC)
    w = Finestra()
    w.show()
    try:
        sys.exit(app.exec_())
    finally:
        logger.info("Sortida de l'aplicació")
        plataforma.desbloqueja(lock_file)
        lock_file.close()
        try:
            os.unlink(lock_path)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
