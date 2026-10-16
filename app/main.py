#!/usr/bin/env python3
# main.py — Auto Chords (PyQt5/Qt5: l'únic Qt que corre al Q9400) —
#           wav -> acords + estructura -> carpetes. Tot en català.
import faulthandler
import json
import logging
import os
import shutil
import sys
import time
import traceback

from PyQt5.QtCore import QEvent, QThread, Qt, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QCursor, QDesktopServices, QKeySequence
from PyQt5.QtWidgets import (
    QAction, QApplication, QButtonGroup, QCheckBox, QFileDialog, QDockWidget,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QComboBox,
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
# UN SOL objecte per mòdul (vegeu visor.py): els imports crus creaven objectes
# diferents dels que veuen la resta de mòduls i els tests.
from . import ffmpeg, graella, partitura, pipeline, postproc, theme  # noqa: F401
from . import config  # noqa: E402
from . import dialegs  # noqa: E402
from . import icones  # noqa: E402
from . import panell_xifrat  # noqa: E402
from . import plataforma  # noqa: E402
from . import projecte  # noqa: E402
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
    congelava la finestra i —si venia d'una crida MCP— deixava el pont sense
    resposta fins al final. Aquí el progrés arriba per senyal (segur entre
    fils) i el pont pot retornar de seguida.
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
            # Durada de la WAV → invariant de cobertura dels clips (0 → durada).
            try:
                durada_wav = float(pipeline.wav_info(self.wav)["durada"])
            except Exception:  # noqa: BLE001
                durada_wav = None
            self.log("1/3 extreu acords (Chordino)...")
            pipeline.extract_chords(self.wav, csv_ac, self.log,
                                    params=(self.opcions.get("chords") or None))
            # CAPA CRUA: desa el resultat de Chordino ABANS de netejar-lo. És
            # l'evidència de l'anàlisi i NO es toca mai (ni l'edició, ni el mode
            # fàcil, ni els canvis de compàs/BPM/mode).
            ana = pipeline.carpeta_analisi(self.sortida)
            try:
                os.makedirs(ana, exist_ok=True)
                if os.path.isfile(csv_ac):
                    shutil.copy2(csv_ac, os.path.join(
                        ana, pipeline.NOM_CRU_ACORDS))
            except OSError as e:  # noqa: BLE001
                self.log(f"no s'ha pogut desar l'anàlisi crua dels acords: {e}")
            # Neteja posterior dels acords (opcions del dialeg).
            cl = self.opcions.get("clean") or {}
            beat = (60.0 / float(self.bpm)) if self.bpm else 0.0
            if cl:
                self.log("1b/3 neteja dels acords...")
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
            # Mode fàcil: si està activat, re-regularitza els acords de l'anàlisi CRUA.
            ritme = str(cl.get("ritme") or "off")
            if ritme and ritme != "off":
                self.log("1c/3 mode fàcil (ritme harmònic)...")
                try:
                    raw = os.path.join(ana, pipeline.NOM_CRU_ACORDS)
                    if os.path.isfile(raw):
                        pipeline.regularitza_acords_csv(
                            raw, csv_ac, self.bpm, self.bpb, self.offset,
                            ritme, durada_wav, log=self.log)
                except Exception as e:  # noqa: BLE001
                    self.log(f"mode fàcil ERROR: {e}")
            self.progres.emit(50)
            csv_seg = None
            if self.amb_estructura:
                csv_seg = os.path.join(self.sortida, "segments.csv")
                self.log("2/3 extreu estructura (qm-segmenter)...")
                pipeline.extract_segments(
                    self.wav, csv_seg, self.log,
                    motor=(self.opcions.get("structure") or {}).get(
                        "motor", "qm"))
                try:
                    if os.path.isfile(csv_seg):
                        shutil.copy2(csv_seg, os.path.join(
                            ana, pipeline.NOM_CRU_SEGMENTS))
                except OSError:
                    pass
                self.progres.emit(75)
                self.log("3/3 ABC (estructura)...")
                abc = os.path.join(self.sortida, "estructura_ABC.csv")
                _est = self.opcions.get("structure") or {}
                compas = beat * max(1, int(self.bpb or 4))
                pipeline.fer_abc(csv_seg, abc, self.bpm, self.log,
                                 lliure=not self.tempo_fix, bpb=self.bpb,
                                 offset=self.offset,
                                 # `durada_min` s'expressa en COMPASSOS → a segons
                                 durada_min=float(_est.get("durada_min", 0.0)) * compas,
                                 fusiona_iguals=bool(_est.get("fusiona_iguals", True)),
                                 durada=durada_wav)
            try:
                os.makedirs(ana, exist_ok=True)
                with open(os.path.join(ana, pipeline.NOM_ANALISI_META), "w",
                          encoding="utf-8") as f:
                    json.dump({"wav": self.wav, "durada": durada_wav,
                               "bpm": self.bpm, "bpb": self.bpb,
                               "offset": self.offset,
                               "tempo_fix": self.tempo_fix,
                               "opcions": self.opcions,
                               "data": time.strftime("%Y-%m-%dT%H:%M:%S")},
                              f, ensure_ascii=False, indent=2)
            except OSError as e:  # noqa: BLE001
                self.log(f"no s'ha pogut desar la meta de l'anàlisi: {e}")
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
        # PROJECTE (carpeta autocontinguda): el document viu + «canvis sense desar».
        self.projecte = None
        self.dirty = False
        self.recents = self._carrega_recents()
        self.wav_original = ""                     # si ve d'un format convertit
        self._info_msg_fins = 0.0                  # missatge transitori info box
        # Pont MCP actiu? → cap avís pot ser MODAL (encallaria el pont) i el
        # darrer avís queda a `ultim_avis` per retornar-lo a l'agent.
        self.mcp_actiu = False
        self.ultim_avis = ""
        # A5: export asíncron (progrés llegible des de l'MCP a `ac_status`).
        # `exporta_error`: motiu de l'últim export fallit ("" = cap) → l'MCP el
        # pot retornar amb `ok: false` en comptes de dir que tot ha anat bé.
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
        self.bpm = QLineEdit("120.0")
        self.bpm.setMaximumWidth(70)
        self.bpm.setPlaceholderText("120.0")
        self.bpm.setToolTip("BPM del tema. Entrada manual (text).")
        self.bpb = QLineEdit("4/4")
        self.bpb.setMaximumWidth(60)
        self.bpb.setPlaceholderText("4/4")
        self.bpb.setToolTip("Compàs manual: 4/4, 3/4, 6/8, etc.")
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
            camp.editingFinished.connect(self._marca_dirty)

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
            "En exportar, genera també un lead sheet de xifrats. El MusicXML "
            "es genera SEMPRE (sense dependències). El PDF i el MSCZ NOMÉS es "
            "poden fer si tens MuseScore instal·lat (l'app no l'inclou). "
            "Només en mode BPM · compàs.")

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
        barra.addSeparator()
        barra.addWidget(self.b_mode_bpm)
        barra.addWidget(self.b_mode_lliure)
        barra.addSeparator()
        barra.addWidget(self._params_temps)
        barra.addSeparator()
        # «Mode fàcil» també a la barra (abans només era al menú Analitza):
        # acció d'un clic que regularitza els acords a la graella.
        self.b_mode_facil = QPushButton("Mode fàcil")
        self.b_mode_facil.setObjectName("secundari")
        self.b_mode_facil.setToolTip(
            "Mode fàcil: re-regularitza els acords a la graella (ritme "
            "harmònic). Treballa sobre l'ANÀLISI CRUA (`analisi/`), per això "
            "depèn d'«Analitza»: sense anàlisi no hi ha res a re-regularitzar. "
            "Es pot desfer i repetir amb un altre nivell.")
        self.b_mode_facil.clicked.connect(self._mode_facil_ui)
        barra.addWidget(self.b_mode_facil)
        # (El commutador d'EINA del timeline viu a la barra de transport, just
        #  darrere del snap i la seva divisió — vegeu la resta d'aquest mètode.)
        barra.addSeparator()
        self.addToolBar(Qt.TopToolBarArea, barra)
        self.barra_principal = barra
        self.barra_temps = barra

        # 1b. SEGONA FILA de la barra 1: les ACCIONS (Analitza + exportacions).
        barra_accions = QToolBar("Accions")
        barra_accions.setObjectName("barra_accions")
        barra_accions.setMovable(False)
        barra_accions.addWidget(self.b_exec)
        barra_accions.addWidget(self.b_export)
        barra_accions.addWidget(self.b_export_part)
        # Botons afegits (petició de l'operador): obrir la carpeta de sortida
        # (just després d'exportar) i desfer/refer (d'ús constant).
        barra_accions.addSeparator()
        self.b_obre_carpeta = QPushButton("Obre la carpeta de sortida")
        self.b_obre_carpeta.setObjectName("secundari")
        self.b_obre_carpeta.setToolTip(
            "Obre la carpeta on es desen els WAV's exportats")
        self.b_obre_carpeta.clicked.connect(self.obre_carpeta)
        barra_accions.addWidget(self.b_obre_carpeta)
        barra_accions.addSeparator()
        self.b_desfer = QPushButton()
        self.b_desfer.setObjectName("secundari")
        self.b_desfer.setIcon(icones.ico("undo-2", 16))
        self.b_desfer.setIconSize(icones.pm_mida(16))
        self.b_desfer.setToolTip("Desfer  (Ctrl+Z)")
        self.b_desfer.clicked.connect(self._undo_visor)
        barra_accions.addWidget(self.b_desfer)
        self.b_refer = QPushButton()
        self.b_refer.setObjectName("secundari")
        self.b_refer.setIcon(icones.ico("redo-2", 16))
        self.b_refer.setIconSize(icones.pm_mida(16))
        self.b_refer.setToolTip("Refer  (Ctrl+Y)")
        self.b_refer.clicked.connect(self._redo_visor)
        barra_accions.addWidget(self.b_refer)
        # `addToolBarBreak` força una FILA NOVA (sense això Qt posa les dues
        # barres en la mateixa línia si hi caben).
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
        self._sc_tap = QShortcut(QKeySequence(Qt.Key_T), self)
        # `E`: commuta l'EINA del timeline (intel·ligent ⇄ marc). És un TOGGLE:
        # cada pulsació canvia d'estat; per defecte sempre s'arrenca en
        # intel·ligent (no hi ha estat «off»).
        self._sc_eina = QShortcut(QKeySequence(Qt.Key_E), self)
        self._sc_eina.activated.connect(self._toggle_eina_tecla)
        self._sc_tap.activated.connect(self._tap_tempo)
        self._crea_menus()
        # Autocomprovació dels fitxers que l'app NECESSITA per analitzar. NO hi
        # posem `pipeline.SONIC` (`OLD/sonic-annotator`): és una **reserva
        # llegat** que no s'empaqueta mai (l'app fa servir `vamp_host_local`), i
        # avisar-ne confonia en arrencar l'app congelada (mac/win/AppImage).
        for p in (pipeline.ACORDS_PY, *pipeline.VAMP_DIRS):
            if not os.path.exists(p):
                self.registra(f"AVÍS: no trobo {p}")
        # A9: ffmpeg és imprescindible per OBRIR qualsevol format que no sigui
        # WAV PCM 16 bits (mp3, flac, m4a, ogg…). Si no hi és, l'obertura
        # fallaria tard i amb un error críptic → millor saber-ho d'entrada.
        if not ffmpeg.disponible():
            self.registra("AVÍS: no trobo ffmpeg — només podré obrir WAV PCM "
                          "16 bits (mp3/flac/m4a/ogg… no)")

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
        self._act(m, "Obre projecte…", "Ctrl+Shift+O", self._obre_projecte)
        self._act(m, "Obre recent…", "", self._obre_recent)
        m.addSeparator()
        self._act(m, "Desa", "Ctrl+S", self._desa_projecte)
        self._act(m, "Desa com…", "Ctrl+Shift+S", self._desa_projecte_com)
        self._act(m, "Desa una còpia…", "", self._desa_copia)
        self._act(m, "Reverteix", "", self._reverteix)
        m.addSeparator()
        self._act(m, "Exporta WAV's…", "Ctrl+E", self.exporta)
        a_part = self._act(m, "Exporta la partitura…", "",
                           self.exporta_partitura_ara)
        a_part.setStatusTip("Genera la partitura (xifrat). El MusicXML sempre; "
                            "el PDF i el MSCZ NOMÉS si hi ha MuseScore instal·lat.")
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
        self._act(m, "Retalla", "Ctrl+X", self._retalla_clips)
        self._act(m, "Copia", "Ctrl+C", self._copia_clips)
        self._act(m, "Enganxa", "Ctrl+V", self._enganxa_clips)
        m.addSeparator()
        self._act(m, "Afegeix acord…", "Ctrl+Shift+A", self._afegeix_acord_ui)
        self._act(m, "Afegeix secció…", "Ctrl+Shift+S", self._afegeix_seccio_ui)
        # A2 + regla d'or #11: en un model saturat (els clips cobreixen tota la
        # WAV) no hi ha forat per afegir-ne: cal PARTIR el clip que hi ha al
        # cursor — MATEIXA acció per a acord i secció.
        self._act(m, "Parteix l'acord al cursor…", "", self._parteix_acord_ui)
        self._act(m, "Parteix la secció al cursor…", "", self._parteix_seccio_ui)
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
        m.addSeparator()
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
        self._act(m, "Analitza l'àudio", "F5", lambda: self.executa())
        m.addSeparator()
        self._act(m, "Detecta el compàs 1 automàticament", None,
                    lambda: self._detecta_compas1())
        self._act(m, "Marca el compàs 1 aquí", "", self._marca_compas_1)
        self._act(m, "Mode fàcil: re-regularitza a la graella…", "",
                  self._mode_facil_ui)
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
        """Refresca els camps de temps/loop de la barra des del visor.

        Cal després de desfer/refer: l'undo pot haver restaurat BPM, compàs,
        offset, mode o el loop A-B (A1). Només reescriu el text si el valor
        difereix, per no reformatejar el que l'usuari hi ha escrit.
        """
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return
        # El compàs viu al camp `bpb` («4» o «4/4»): el numerador és `vr.bpb` i
        # el denominador `vr.beat_type` (no hi ha camp propi per al denominador).
        num, den = getattr(vr, "bpb", None), getattr(vr, "beat_type", None)
        compas = None
        if num is not None:
            compas = str(int(num)) if (den is None or int(den) == 4) \
                else f"{int(num)}/{int(den)}"
        for camp, valor, text in ((self.bpm, getattr(vr, "bpm", None), None),
                                  (self.bpb, num, compas),
                                  (self.offset, getattr(vr, "offset", None),
                                   None)):
            if valor is None:
                continue
            try:
                igual = abs(float(camp.text().replace(",", "."))
                            - float(valor)) <= 1e-9
            except (TypeError, ValueError):
                igual = False
            if not igual:
                camp.setText(text if text is not None else f"{float(valor):g}")
        try:
            self.offset_cb.setText(self._secs_a_cb(float(getattr(vr, "offset", 0.0))))
        except (TypeError, ValueError, AttributeError):
            pass
        self._on_loop_state(getattr(vr, "loop_on", False))

    def _undo_visor(self):
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            vr.undo()
            self._sincronitza_temps_del_visor()
        else:
            self.registra("Edita: no hi ha visor carregat")

    def _redo_visor(self):
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
            ("DUPLICAR-LO: l'original es queda a lloc",
             "Ctrl+Shift+arrossega el cos"),
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
            ("enganxar SALTANT-SE el snap", "Ctrl+Shift+V"),
            ("moure un clip un pas de graella (Alt = vora dreta)",
             "← / →"),
            ("cancel·lar: rang en curs · loop · selecció", "Esc"),
            ("desfer / refer", "Ctrl+Z / Ctrl+Y"),
            ("reanomenar (clip o grup del tipus actiu)", "F2"),
            ("esborrar la selecció", "Del"),
        ]))
        return grups

    # ---------- Avisos (mai modals si el pont MCP és actiu) -------------------
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
        """Mostra un avís SENSE poder encallar el pont MCP.

        Amb el pont actiu, un `QMessageBox` MODAL deixa el pont bloquejat fins
        que algú el tanca: l'agent que ha disparat l'acció (exportar, analitzar)
        no rebria mai la resposta i es quedaria penjat. En aquest cas s'ensenya
        **no modal**, s'auto-tanca al cap de 10 s i el text queda a
        `self.ultim_avis` perquè el pont el pugui retornar a l'agent. Sense
        pont, el comportament és exactament l'de sempre (modal).
        """
        text = str(text)
        self.ultim_avis = text
        if not getattr(self, "mcp_actiu", False):
            return getattr(QMessageBox, tipus)(self, titol, text)
        self.logger.warning("avís (pont MCP actiu, sense modal): %s", text)
        try:
            self.registra(f"AVÍS: {text}")
        except Exception:  # noqa: BLE001
            pass
        # Un sol avís no modal alhora: tanquem l'anterior (evita acumular
        # finestres fill que després es destrueixen amb la Finestra).
        self._tanca_avis_box()
        box = QMessageBox(getattr(QMessageBox, tipus.capitalize()), titol, text,
                          QMessageBox.Ok, self)
        box.setWindowModality(Qt.NonModal)
        box.setAttribute(Qt.WA_DeleteOnClose, True)
        self._avis_box = box   # (sense destroyed.connect: era un parany de GC)
        box.show()
        # El timer és FILL del box: mor amb ell (abans, `QTimer.singleShot`
        # sobre `box.close` podia disparar-se amb el box/la finestra ja destruïts).
        t = QTimer(box)
        t.setSingleShot(True)
        t.timeout.connect(box.close)
        t.start(10000)
        return None

    def _tanca_avis_box(self):
        box = getattr(self, "_avis_box", None)
        self._avis_box = None
        if box is None:
            return
        try:
            box.close()
        except RuntimeError:      # ja destruït per C++ (WA_DeleteOnClose)
            pass

    def _text_dreceres(self):
        """El diàleg de dreceres en HTML (separat per poder-lo testar)."""
        blocs = []
        for grup, parells in self._dreceres():
            blocs.append(f"<b>{grup}</b><br>" + "<br>".join(
                f"{text} — {drecera}" for text, drecera in parells))
        return "<br><br>".join(blocs)

    def _mostra_dreceres(self):
        # (3) Amb el pont MCP actiu, un modal encallaria el pont: no-modal.
        if getattr(self, "mcp_actiu", False):
            return self._avis("Dreceres de teclat", self._text_dreceres(),
                              "information")
        QMessageBox.information(self, "Dreceres de teclat", self._text_dreceres())

    def _quant_a(self):
        text = (
            "<b>Auto Chords</b><br>"
            f"Versió <b>{__version__}</b><br>"
            "wav → acords + estructura<br><br>"
            "Visor DAW-like (PyQt5).<br>"
            "Motor: Chordino (acords) + Queen Mary/qm (estructura) · Vamp.")
        # (3) Amb el pont MCP actiu, no-modal (un modal encallaria el pont).
        if getattr(self, "mcp_actiu", False):
            return self._avis("Quant a Auto Chords", text, "information")
        QMessageBox.about(self, "Quant a Auto Chords", text)

    def registra(self, t):
        self.logger.info("UI: %s", t)
        self.log.append(t)

    # ---- lectura manual dels camps de text ----
    @staticmethod
    def _parse_compas(text, defecte_num=4, defecte_den=4):
        """Accepta '4', '4/4', '3/4', '6/8' i retorna (num, den)."""
        s = str(text).strip()
        if not s:
            return defecte_num, defecte_den
        if "/" in s:
            parts = s.split("/", 1)
            try:
                numer = int(float(parts[0].strip().replace(",", ".")))
                den = int(float(parts[1].strip().replace(",", ".")))
            except ValueError:
                return defecte_num, defecte_den
            if numer <= 0:
                numer = defecte_num
            if den <= 0:
                den = defecte_den
            return numer, den
        try:
            v = float(s.replace(",", "."))
        except ValueError:
            return defecte_num, defecte_den
        v = max(1, int(round(v)))
        return v, defecte_den

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
        num, _den = self._parse_compas(self.bpb.text(), defecte_num=4, defecte_den=4)
        return max(1, min(12, int(num)))

    def _beat_type_val(self):
        _num, den = self._parse_compas(self.bpb.text(), defecte_num=4, defecte_den=4)
        return max(1, min(16, int(den)))

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
            self.avisa_info(
                "Detecta BPM",
                "No s'ha pogut estimar el BPM.\n"
                "Pot ser un tema en directe o molt irregular: escriu-lo a mà.")

    def eventFilter(self, obj, ev):
        """Filtre d'esdeveniments: un CLIC dins la caixa d'informacio.

        La caixa es de nomes lectura, pero els clics hi arriben; els fem servir
        per **pausar** el rotatori i **passar de pantalla** sense esperar.
        """
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
                ("El clip viatja i a l'origen en queda una còpia (mateix nom)",
                 "Ctrl+Shift+arrossega el cos"),
                ("Duplicar l'element seleccionat", "Ctrl+D"),
            ]),
            ("Moure i redimensionar", [
                ("Moure (tot el grup si està seleccionat)",
                 "Arrossega el cos del clip"),
                ("Moure l'inici o el final", "Arrossega una vora"),
                ("Un pas de graella", "← / →"),
                ("La vora DRETA un pas de graella", "Alt+← / Alt+→"),
            ]),
            ("Copiar, retallar i enganxar", [
                ("Al cursor", "Ctrl+C / Ctrl+X / Ctrl+V"),
                ("L'enganxat SUBSTITUEIX el tram: la cançó no creix mai", ""),
                ("Enganxar saltant-se el snap", "Ctrl+Shift+V"),
            ]),
            ("Loop A-B", [
                ("Crear-lo o editar-lo", "Arrossega sobre el regle"),
                ("Marcar l'inici / el final al cursor", "Ctrl+[ / Ctrl+]"),
                ("Seleccionar TOT el que hi ha a dins", "Doble-clic al loop"),
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
            ("Mode fàcil: què fa i per què va amb «Analitza»", [
                ("Posa els acords a la GRAELLA: els arrodoneix al compàs i al "
                 "temps (ritme harmònic net)", ""),
                ("Treballa sobre l'ANÀLISI CRUA (carpeta `analisi/`), no sobre "
                 "el model que veus", ""),
                ("Per això depèn d'«Analitza»: sense anàlisi no hi ha res a "
                 "re-regularitzar", ""),
                ("No toca l'anàlisi crua: pots desfer (Ctrl+Z) i tornar-hi "
                 "amb un altre nivell", ""),
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

    def _mode_facil_ui(self):
        """Mode fàcil: preset d'estil + ritme harmònic + mòdul → regularitza."""
        vr = self.visor_ref
        if vr is None or not vr.acords:
            self.avisa_info("Auto Chords", "Analitza un tema primer.")
            return
        dlg = dialegs.DialegModeFacil(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        p = graella.PRESETS.get(dlg.preset()) or {}
        bpb = int(p.get("bpb") or self._bpb_val())
        den = int(p.get("den") or 4)
        nou = f"{bpb}/{den}"      # sempre en format complet (4/4, no «4»)
        if self.bpb.text().strip() != nou:
            self.bpb.setText(nou)
            self._aplica_parametres_temps()
        n = vr.regularitza_des_de_cru(dlg.ritme(), modul_compassos=dlg.modul())
        if n:
            self.registra(f"mode fàcil: {n} acords a la graella "
                          f"({p.get('etiqueta', '')})")

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
            vr.timeline.copy_selection()

    def _retalla_clips(self):
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            vr.timeline.cut_selection()

    def _enganxa_clips(self):
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            vr.timeline.paste_at_cursor()

    def _renomena_element(self):
        vr = self.visor_ref
        if vr is None:
            return
        keys = vr.timeline.selected_keys()
        # >1 clip seleccionat → renom EN BLOC del tipus ACTIU. Amb selecció
        # mixta es renombren NOMÉS els del tipus del clip actiu (opció A).
        if len(keys) > 1:
            vr.renomena_seleccio()
            return
        kind, idx = self._clip_seleccionat()
        if kind is None:
            return
        tl = vr.timeline
        if kind == "chord":
            tl.chordEditRequested.emit(idx)
        else:
            tl.sectionEditRequested.emit(idx)

    def _idx_acord_del_cursor(self):
        """Índex de l'acord que CONTÉ el cursor (o `None`). Regla d'or #11."""
        vr = getattr(self, "visor_ref", None)
        if vr is None or not vr.acords:
            return None
        idx = None
        for i, a in enumerate(vr.acords):
            if float(a[0]) <= float(vr.pos):
                idx = i
            else:
                break
        return idx

    def _parteix_acord_ui(self):
        """Parteix l'acord que conté el cursor pel punt del cursor (regla #11)."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.registra("Parteix: no hi ha visor carregat")
            return
        idx = self._idx_acord_del_cursor()
        if idx is None:
            self.registra("Parteix: el cursor no és dins cap acord")
            return
        if vr._parteix_acord_dialog(idx):
            self.registra(f"acord partit a {vr.pos:.2f} s")

    def _idx_seccio_del_cursor(self):
        """Índex de la secció que CONTÉ el cursor (o `None`). A2."""
        vr = getattr(self, "visor_ref", None)
        if vr is None or not vr.seccions:
            return None
        for i, s in enumerate(vr.seccions):
            if float(s[0]) <= float(vr.pos) < float(s[1]):
                return i
        return None

    def _parteix_seccio_ui(self):
        """Parteix la secció que conté el cursor pel punt del cursor (A2)."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.registra("Parteix: no hi ha visor carregat")
            return
        idx = self._idx_seccio_del_cursor()
        if idx is None:
            self.registra("Parteix: el cursor no és dins cap secció")
            return
        if vr._parteix_seccio_dialog(idx):
            self.registra(f"secció partida a {vr.pos:.2f} s")

    def _afegeix_acord_ui(self):
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return
        nom, ok = QInputDialog.getText(
            self, "Afegeix acord", f"Acord a {vr.pos:.2f} s", text="N")
        if not ok or not nom.strip():
            return
        try:
            vr._undo_marca()      # A1: l'alta des del MENÚ també és desfer/fer
            vr._afegeix_acord(vr.pos, nom.strip())
            vr._desa_i_regenera()
            vr.timeline.set_data(vr.acords, vr.seccions)
            vr._undo_commit()
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
            vr._undo_marca()      # A1: l'alta des del MENÚ també és desfer/fer
            vr._afegeix_seccio(vr.pos, vr.pos + 2.0, lletra.strip()[:1].upper())
            vr._regenera_abc_des_de_totes_les_seccions("secció afegida")
            vr.timeline.set_data(vr.acords, vr.seccions)
            vr._undo_commit()
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
        self.offset.setText(f"{seg:.2f}")
        self._aplica_parametres_temps()
        self.registra(f"Compàs 1 detectat a {seg:.2f}s ✔")

    def _aplica_parametres_temps(self):
        """Propaga BPM/compàs/offset al visor. Si sona, reengega perquè el
        metrònom segueixi la nova graella des de la posició actual."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return
        vr._undo_marca()          # A1: el BPM/compàs/offset també és desfer/fer
        vr.bpm = self._bpm_val()
        vr.bpb = self._bpb_val()
        vr.beat_type = self._beat_type_val()
        vr.offset = self._offset_val()
        self.offset_cb.setText(self._secs_a_cb(vr.offset))
        vr._actualitza_temps()
        self._reenvia_si_sona()
        vr._undo_commit()

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
            self.visor_ref.beat_type = self._beat_type_val()
            self.visor_ref._actualitza_temps()
            self.visor_ref.timeline.set_tempo_mode(
                bool(fix), self._bpm_val(), self._bpb_val(),
                self._offset_val(), self._beat_type_val())

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
            )
            self.visor_ref = visor
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
            self._on_loop_state(getattr(visor, "loop_on", False))
            self.visor_widget = visor.centralWidget()
            self.visor_widget.setParent(self._stack)
            if self._stack.indexOf(self.visor_widget) < 0:
                self._stack.addWidget(self.visor_widget)   # pagina 1 = visor
            self._stack.setCurrentWidget(self.visor_widget)
            self.visor_widget.show()
            self.b_exec.setEnabled(True)     # hi ha WAV -> es pot analitzar
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
        return {
            "tempo": {"bpm": self._bpm_val(), "bpb": self._bpb_val(),
                      "offset": self._offset_val(),
                      "fix": self.tempo_fix.isChecked(),
                      "compas": self.bpb.text().strip()},
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
        self.wav_original = ""
        self.wav_edit.setText(wav)
        tempo = p.dades.get("tempo") or {}
        self.bpm.setText(f"{float(tempo.get('bpm', 120.0)):.1f}")
        compas = tempo.get("compas")
        # Format COMPLET (4/4, no «4»): un «4» sol sembla el compàs denormalitzat
        # i confon; el parser accepta els dos, però el camp sempre el mostra bé.
        self.bpb.setText(str(compas) if compas
                         else f"{int(tempo.get('bpb', 4))}/4")
        self.offset.setText(f"{float(tempo.get('offset', 0.0)):.2f}")
        self.tempo_fix.setChecked(bool(tempo.get("fix", False)))
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
        """Torna el projecte a l'últim estat desat."""
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

    def _obri_des_de_wav(self, ruta):
        """Crea un projecte AUTOCONTINGUT a partir d'un WAV (preguntant ON)."""
        if not self._pot_descartar():
            return
        self.wav_original = ""
        try:
            treball = self._assegura_wav(ruta)
        except Exception as e:  # noqa: BLE001
            self.logger.exception("Àudio no vàlid: %s", ruta)
            self.wav_info.setText(f"No s'ha pogut obrir: {e}")
            self._mostra_placeholder_visor()
            return
        if treball != ruta:
            self.wav_original = os.path.abspath(ruta)
        # Pregunta ON crear el projecte (per defecte, al costat del WAV).
        base = os.path.splitext(os.path.basename(treball))[0]
        desti = self._demana_ubicacio_projecte(
            os.path.dirname(treball), pipeline.PREFIX_SORTIDA + base,
            "Crea el projecte")
        if not desti:
            return
        # Un WAV NOU no ha d'heretar el BPM del tema anterior (OC-6/415).
        if self.bpm.text().strip() not in ("", "120.0", "120"):
            self.registra("WAV nou → BPM reiniciat a 120.0 "
                          "(detecta'l o posa'l a mà)")
            self.bpm.setText("120.0")
        # Migració: si hi ha una AUTOCHORDS_<nom>/ vella al costat del WAV,
        # n'importem els CSVs (i, si el destí és la mateixa carpeta, in situ).
        antic = projecte.carpeta_autochords(treball)
        ca = os.path.join(antic, projecte.NOM_CSV_ACORDS) if antic else None
        sa = os.path.join(antic, projecte.NOM_CSV_ESTRUCTURA) if antic else None
        in_situ = bool(antic) and os.path.abspath(desti) == os.path.abspath(antic)
        try:
            p = projecte.Projecte.crea(
                desti, treball, nom=os.path.basename(desti),
                bpm=self._bpm_val(), bpb=self._bpb_val(),
                offset=self._offset_val(), fix=self.tempo_fix.isChecked(),
                opcions=self.opcions, compas=self.bpb.text().strip(),
                csv_acords=ca if ca and os.path.isfile(ca) else None,
                csv_estructura=sa if sa and os.path.isfile(sa) else None,
                permet_existent=in_situ)
        except (projecte.ProjecteError, OSError) as e:
            self.avisa("Auto Chords", f"No s'ha pogut crear el projecte:\n{e}")
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
        bar.addSeparator()
        # Graella configurable: interruptor de snap + divisió (habilita el nudge fi).
        self.tb_snap = boto("Snap", "Interruptor de snap (encaixar a la graella)",
                            self._canvia_snap, checkable=True)
        self.tb_snap.setChecked(True)
        self.cb_graella = QComboBox()
        self.cb_graella.setToolTip("Divisió de la graella (on encaixa el snap)")
        for et, val in (("Auto (zoom)", ""), ("Negra (1/4)", "negra"),
                        ("Corxera (1/8)", "corxera"),
                        ("Semicorxera (1/16)", "semicorxera"),
                        ("Fusa (1/32)", "fusa"), ("Treset (1/12)", "treset"),
                        ("1 compàs", "compas1"), ("4 compassos", "compas4"),
                        ("8 compassos", "compas8"),
                        ("16 compassos", "compas16")):
            self.cb_graella.addItem(et, val)
        self.cb_graella.currentIndexChanged.connect(self._canvia_snap)
        bar.addWidget(self.cb_graella)
        bar.addSeparator()
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
        bar.addWidget(self.b_eina)

    def _canvia_snap(self):
        """Aplica l'interruptor de snap + la divisió de graella al visor."""
        vr = getattr(self, "visor_ref", None)
        if vr is None or not hasattr(self, "tb_snap"):
            return
        vr.set_snap(on=self.tb_snap.isChecked(),
                    divisio=self.cb_graella.currentData() or "")

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

    def executa(self, pregunta=True):
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
            if dlg.exec_() != QDialog.Accepted:
                return
            self.opcions = dlg.opcions()
            dialegs.desa_opcions(self.opcions)
            self._marca_dirty()
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
        self.b_export.setEnabled(False)
        self.b_export_part.setEnabled(False)
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
            self.b_export_part.setEnabled(True)
            self.registra("FET ✅ — ara pots revisar el visor i fer «Exporta WAV's».")
            self.barra.setValue(100)
            wav = self.wav_edit.text().strip()
            if wav and os.path.isfile(wav):
                self._carrega_visor(wav)
        else:
            self.b_export.setEnabled(False)
            self.b_export_part.setEnabled(False)
            self.registra(f"ERROR: {dada}")
            self.log_dock.setVisible(True)    # en cas d'error, obrim el log
            self.avisa_crit("Auto Chords", dada)

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
        csv_seg = os.path.join(self.sortida, "segments.csv")
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
        amb_estructura = self.amb_est.isChecked() and (
            seccions_model is not None or os.path.isfile(csv_seg))
        # (2) Amb «Inclou estructura» OFF, les restes d'un export ANTERIOR
        # (`wavs_estructura/`) quedaven a la carpeta i semblava que l'export
        # actual hagués inclòs estructura → s'ofereix treure-les (amb
        # confirmació). El MODEL (`estructura_ABC.csv`) NO es toca mai.
        if not amb_estructura:
            self._neteja_estructura_vella(self.sortida)
        return dict(
            csv_ac=csv_ac,
            csv_seg=csv_seg if amb_estructura else None,
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
        )

    def _neteja_estructura_vella(self, sortida):
        """Treu les restes d'un export ANTERIOR quan l'actual NO inclou estructura.

        **(a) MAI toca el MODEL del projecte** (`estructura_ABC.csv`): la marca
        «Inclou estructura» decideix què s'**exporta**, no què es **conserva**.
        Només s'ofereix treure els **derivats de l'export** (`wavs_estructura/`).

        **(c) Sempre amb confirmació**: (1) només es pregunta si hi ha restes a
        treure; (2) amb el pont MCP actiu no s'esborra mai res (evita encallar
        el pont amb un diàleg modal — vegeu `test_avis_no_modal`).
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
        """Demana confirmació (Sí/No). Amb el pont MCP actiu (o sense sessió
        interactiva, `offscreen`) respon **No** i no mostra cap diàleg modal
        (no s'ha d'encallar el pont ni petar el CI; cf. `_avis`/`_interactiu`)."""
        if getattr(self, "mcp_actiu", False) or not self._interactiu():
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

    def _exporta_acabada(self, res_part=None):
        """Missatges de final d'exportació (compartit pel camí síncron i el fil)."""
        self.registra("Exportació feta ✅")
        msg = f"Exportació feta a:\n{self.sortida}"
        if res_part is not None and not res_part.get("pdf"):
            msg += ("\n\n⚠️ La partitura s'ha generat NOMÉS en MusicXML: el "
                    "PDF necessita MuseScore instal·lat.")
        self.avisa_info("Auto Chords", msg)
        # Amb el pont MCP actiu NO s'obre el gestor de fitxers: l'agent que ha
        # demanat l'export no necessita finestres a l'escriptori de l'usuari.
        if not getattr(self, "mcp_actiu", False):
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
        fil acaba. El progrés es veu a la barra i a `self.exportant` (que l'MCP
        llegeix a `ac_status`).
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

    def _assegura_locators(self):
        """Regenera `acords_locators.txt` si és MÉS VELL que el model.

        La partitura es construeix a partir dels **locators**, que són un
        DERIVAT del CSV (els fa `acords_a_live.py`). Si s'ha editat el model
        després de l'últim export de WAVs, els locators del disc són VELLS i la
        partitura sortia amb els acords antics (bug real, 2026-10-15).
        """
        sortida = self.sortida or ""
        csv_ac = os.path.join(sortida, "acords.csv")
        loc = os.path.join(sortida, "acords_locators.txt")
        if not (sortida and os.path.isfile(csv_ac) and os.path.isfile(loc)):
            return False            # sense locators, `partitura` ja avisa
        try:
            if os.path.getmtime(loc) >= os.path.getmtime(csv_ac):
                return True         # ja estan al dia
        except OSError:
            pass
        vr = getattr(self, "visor_ref", None)
        try:
            pipeline.run_acords_py(
                csv_ac, self._bpm_val(), self._bpb_val(), self._offset_val(),
                sortida, self.registra,
                durada=(vr.audio["durada"] if vr is not None else None))
            self.registra("partitura: locators regenerats (el model havia "
                          "canviat des de l'últim export de WAVs)")
            return True
        except Exception as e:  # noqa: BLE001
            self.registra(f"AVÍS: no he pogut regenerar els locators: {e}")
            return False

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
            # Els locators són un derivat del model: si és vell, es regenera.
            self._assegura_locators()
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
                "(hi ha d'haver acords_locators.txt). Detall al log.")
            return
        self.avisa_info("Auto Chords",
                                self._missatge_partitura(res))
        if not getattr(self, "mcp_actiu", False):    # cf. `_exporta_acabada`
            self.obre_carpeta()

    def closeEvent(self, ev):
        """Neteja ordenada abans que Qt destrueixi la finestra.

        Sense això, es destruïa la Finestra amb fils vius (`FeinaExporta`), el
        reproductor del visor sonant, el pont MCP obert i un avís no modal fill
        visible: destrucció en ordre arbitrari = risc d'access violation.
        """
        if not self._pot_descartar():
            ev.ignore()
            return
        fe = getattr(self, "feina_export", None)
        try:
            if fe is not None and fe.isRunning():
                fe.wait(10000)
        except RuntimeError:
            pass
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            try:
                vr.rellotge.stop()
                vr._atura_proc()
            except (RuntimeError, AttributeError):
                pass
        pont = getattr(self, "_mcp_pont", None)
        if pont is not None:
            try:
                pont.tanca()
            except Exception:  # noqa: BLE001
                pass
        self._tanca_avis_box()
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
