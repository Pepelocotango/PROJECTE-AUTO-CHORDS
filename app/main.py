#!/usr/bin/env python3
# main.py — Auto Chords (PyQt5/Qt5: l'únic Qt que corre al Q9400) —
#           wav -> acords + estructura -> carpetes. Tot en català.
import fcntl
import logging
import os
import sys
import tempfile
import traceback

from PyQt5.QtCore import QThread, Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices, QKeySequence
from PyQt5.QtWidgets import (
    QAction, QApplication, QButtonGroup, QCheckBox, QFileDialog, QDockWidget,
    QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QProgressBar, QPushButton, QShortcut, QSlider, QTextEdit,
    QStackedWidget, QToolBar,
    QVBoxLayout, QWidget,
)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(APP_DIR)
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
import pipeline  # noqa: E402
import theme  # noqa: E402
from . import visor as visor_mod  # noqa: E402

DEFAULT_LOG_PATH = os.path.join(PROJECT_ROOT, "auto_chords.log")


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
                 tempo_fix=True):
        super().__init__()
        self.wav = wav
        self.sortida = sortida
        self.bpm = bpm
        self.bpb = bpb
        self.offset = offset
        self.amb_estructura = amb_estructura
        self.tempo_fix = tempo_fix

    def log(self, t):
        self.missatge.emit(t)

    def run(self):
        try:
            os.makedirs(self.sortida, exist_ok=True)
            csv_ac = os.path.join(self.sortida, "acords.csv")
            self.log("1/5 extreu acords (Chordino)...")
            pipeline.extract_chords(self.wav, csv_ac, self.log)
            self.progres.emit(35)
            if self.amb_estructura:
                csv_seg = os.path.join(self.sortida, "segments.csv")
                self.log("2/5 extreu estructura (Segmentino)...")
                pipeline.extract_segments(self.wav, csv_seg, self.log)
                self.progres.emit(60)
            else:
                csv_seg = None
            self.progres.emit(65)
            if self.tempo_fix:
                self.log("3/5 locators + guia...")
                loc, _guia = pipeline.run_acords_py(
                    csv_ac, self.bpm, self.bpb, self.offset, self.sortida,
                    self.log)
                self.progres.emit(75)
                self.log("4/5 wavs d'acords...")
                pipeline.fer_wavs_acords(
                    loc, self.bpm, os.path.join(self.sortida, "wavs_acords"),
                    44100, self.log, self.bpb)
            else:
                self.log("3-4/5 segments en segons + wavs...")
                info = pipeline.wav_info(self.wav)
                pipeline.fer_wavs_acords_lliures(
                    csv_ac, info["durada"],
                    os.path.join(self.sortida, "wavs_acords"), 44100,
                    self.log)
            self.progres.emit(88)
            if csv_seg:
                self.log("5/5 ABC + wavs d'estructura...")
                abc = os.path.join(self.sortida, "estructura_ABC.csv")
                pipeline.fer_abc(csv_seg, abc, self.bpm, self.log,
                                 lliure=not self.tempo_fix, bpb=self.bpb,
                                 offset=self.offset)
                pipeline.fer_wavs_estructura(
                    abc, os.path.join(self.sortida, "wavs_estructura"),
                    44100, self.log)
            self.progres.emit(100)
            self.feta.emit(True, self.sortida)
        except Exception as e:  # noqa: BLE001
            self.feta.emit(False, str(e))


class Finestra(QMainWindow):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("auto_chords")
        self.setWindowTitle("Auto Chords — wav → acords + estructura")
        self.resize(1500, 900)
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

        # barra d'eines principal: Obre (els passos 3/4 hi afegiran Analitza/Exporta)
        barra_principal = QToolBar("Principal")
        barra_principal.setObjectName("barra_principal")
        barra_principal.setMovable(False)
        b_obre = QPushButton("Obre…")
        b_obre.setObjectName("secundari")
        b_obre.setToolTip("Obre una WAV (Ctrl+O)")
        b_obre.clicked.connect(self.tria_wav)
        barra_principal.addWidget(b_obre)
        barra_principal.addSeparator()
        self.barra_principal = barra_principal
        self.addToolBar(Qt.TopToolBarArea, barra_principal)

        # 2. temps i paràmetres — BARRA compacta d'una sola línia (estil DAW)
        #    (abans era un QGroupBox «2 · Temps i paràmetres»)
        self.b_mode_bpm = QPushButton("BPM · compàs")
        self.b_mode_bpm.setCheckable(True)
        self.b_mode_bpm.setChecked(True)
        self.b_mode_bpm.setToolTip("Treballar amb BPM i compassos.")
        self.b_mode_lliure = QPushButton("Lliure (hh:mm:ss)")
        self.b_mode_lliure.setCheckable(True)
        self.b_mode_lliure.setToolTip("Treballar amb temps real (sense compassos).")
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
        self.b_detecta = QPushButton("🎯 Detecta")
        self.b_detecta.setObjectName("secundari")
        self.b_detecta.setToolTip("Detecta el BPM automàticament amb aubio.")
        self.b_detecta.clicked.connect(self._detecta_bpm)
        for camp in (self.bpm, self.bpb, self.offset):
            camp.editingFinished.connect(self._aplica_parametres_temps)

        self._params_temps = QWidget()      # s'amaga sencer en mode Lliure
        hp = QHBoxLayout(self._params_temps)
        hp.setContentsMargins(0, 0, 0, 0)
        hp.setSpacing(6)
        hp.addWidget(QLabel("BPM:"))
        hp.addWidget(self.bpm)
        hp.addWidget(self.b_detecta)
        hp.addWidget(QLabel("Compàs:"))
        hp.addWidget(self.bpb)
        hp.addWidget(QLabel("Offset:"))
        hp.addWidget(self.offset)                 # segons
        hp.addWidget(QLabel("≈"))
        self.offset_cb = QLineEdit("1.1")         # el mateix, en compàs.beat
        self.offset_cb.setMaximumWidth(46)
        self.offset_cb.setPlaceholderText("1.1")
        self.offset_cb.setToolTip(
            "Posició del compàs 1 en compàs.beat (graella original, offset=0).\n"
            "Ex. 5.1 = el compàs 1 va on la graella diu 5.1")
        hp.addWidget(self.offset_cb)
        self.offset_cb.editingFinished.connect(self._offset_cb_canviat)

        self.amb_est = QCheckBox("Inclou estructura")
        self.amb_est.setChecked(True)
        self.amb_est.setToolTip("Genera la jerarquia de seccions i l’ABC de l’estructura del tema.")

        # estat `tempo_fix` (ocult): el visor i la resta de codi el consulten
        self.tempo_fix = QCheckBox()
        self.tempo_fix.setChecked(True)
        self.tempo_fix.setVisible(False)
        self.tempo_fix.toggled.connect(self._canvia_tempo)

        # la barra pròpiament
        barra_temps = QToolBar("Temps i paràmetres")
        barra_temps.setObjectName("barra_temps")
        barra_temps.setMovable(False)
        barra_temps.addWidget(QLabel(" Temps: "))
        barra_temps.addWidget(self.b_mode_bpm)
        barra_temps.addWidget(self.b_mode_lliure)
        barra_temps.addSeparator()
        barra_temps.addWidget(self._params_temps)
        barra_temps.addSeparator()
        barra_temps.addWidget(self.amb_est)
        self.addToolBar(Qt.TopToolBarArea, barra_temps)
        self.barra_temps = barra_temps

        # 3. «Analitza» és una ACCIÓ sobre el que es veu (ja no un pas d'assistent).
        self.b_exec = QPushButton("Analitza")
        self.b_exec.setObjectName("principal")
        self.b_exec.setToolTip("Extreu acords i estructura de la WAV (F5)")
        self.b_exec.clicked.connect(self.executa)
        self.b_exec.setEnabled(False)          # fins que hi hagi WAV
        self.barra_principal.addWidget(self.b_exec)

        # «Exporta» és una acció de Fitxer (vegeu el menú); botó a la barra
        self.b_export = QPushButton("Exporta")
        self.b_export.setToolTip("Exporta el paquet final (Ctrl+E)")
        self.b_export.setEnabled(False)       # fins que hi hagi pistes
        self.b_export.clicked.connect(self.exporta)
        self.barra_principal.addWidget(self.b_export)

        # progrés → barra d'estat (permanent)
        self.barra = QProgressBar()
        self.barra.setMaximumWidth(180)
        self.barra.setTextVisible(False)
        self.statusBar().addPermanentWidget(self.barra)

        # log → tauler plegable a baix (tancat per defecte)
        self.log = QTextEdit()
        self.log.setObjectName("log")
        self.log.setReadOnly(True)
        self.log_dock = QDockWidget("Log", self)
        self.log_dock.setObjectName("dock_log")
        self.log_dock.setWidget(self.log)
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
        self.addToolBarBreak(Qt.TopToolBarArea)   # el transport, a la seva fila
        self.addToolBar(Qt.TopToolBarArea, barra_transport)
        self.barra_transport = barra_transport

        self.sortida = ""
        self.b_export.setEnabled(False)
        # Drecera: espai = play/pausa (a la finestra principal, perquè el
        # visor està incrustat i el seu propi QShortcut no s'activaria).
        self._sc_play = QShortcut(QKeySequence(Qt.Key_Space), self)
        self._sc_play.activated.connect(self._toggle_play)
        self._crea_menus()
        for p in (pipeline.SONIC, pipeline.ACORDS_PY,
                  *pipeline.VAMP_DIRS):
            if not os.path.exists(p):
                self.registra(f"AVÍS: no trobo {p}")

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
        self._act(m, "Obre la carpeta de sortida", "", self.obre_carpeta)
        m.addSeparator()
        self._act(m, "Surt", "Ctrl+Q", self.close)
        # --- Edita ---
        m = mb.addMenu("&Edita")
        self._act(m, "Desfer", "Ctrl+Z", self._undo_visor)
        self._act(m, "Refer", "Ctrl+Y", self._redo_visor)
        self._act(m, "Refer (alternatiu)", "Ctrl+Shift+Z", self._redo_visor)
        m.addSeparator()
        self._act(m, "Paràmetres…", "", self._focus_parametres)
        # --- Selecciona ---
        m = mb.addMenu("&Selecciona")
        self._act(m, "Marca inici de loop (A)", "", self._marca_A_visor)
        self._act(m, "Marca fi de loop (B)", "", self._marca_B_visor)
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
        self._act(m, "Processa el WAV", "F5", self.executa)
        m.addSeparator()
        self._act(m, "Marca el compàs 1 aquí", "", self._marca_compas_1)
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
            "Motor: chordino + segmentino (vamp).")

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
        return self._llegeix_num(self.bpm, 120.0, 40, 240)

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

    def _detecta_bpm(self):
        """Detecta el BPM amb aubio i l'escriu al camp (l'usuari pot editar-lo)."""
        wav = self.wav_edit.text().strip()
        if not wav or not os.path.isfile(wav):
            QMessageBox.warning(self, "Detecta BPM",
                                "Primer tria una WAV.")
            return
        self.registra("Detectant el BPM amb aubio…")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            bpm = pipeline.detecta_bpm(wav, self.registra)
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

    def tria_wav(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Tria la wav", "", "Àudio WAV (*.wav)")
        if ruta:
            self.wav_edit.setText(ruta)
            try:
                info = pipeline.wav_info(ruta)
                self.sortida = self._detecta_sortida_wav(ruta)
                self.logger.info("WAV seleccionada: %s | info=%s | sortida_detectada=%s", ruta, info, self.sortida)
                self._actualitza_info_wav(ruta, info)
                self._carrega_visor(ruta)
            except Exception as e:  # noqa: BLE001
                self.logger.exception("WAV no vàlida: %s", ruta)
                self.wav_info.setText(f"No és una wav vàlida: {e}")
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
        def boto(text, tip, accio, checkable=False):
            b = QPushButton(text)
            b.setToolTip(tip)
            if checkable:
                b.setCheckable(True)
            b.clicked.connect(accio)
            bar.addWidget(b)
            return b

        boto("▶ Escolta", "Reprodueix / atura  (Espai)",
             lambda: self._acc_visor("play_stop"))
        boto("⏹", "Atura i torna a l'inici",
             lambda: self._acc_visor("stop_inici"))
        boto("−10s", "Endarrere 10 s",
             lambda: self._acc_visor("menys10"))
        boto("+10s", "Endavant 10 s",
             lambda: self._acc_visor("mes10"))
        bar.addSeparator()
        boto("A⟨", "Marca inici de loop (A)",
             lambda: self._acc_visor("marca_A"))
        boto("⟩B", "Marca fi de loop (B)",
             lambda: self._acc_visor("marca_B"))
        self.tb_loop = boto("🔁", "Activa/desactiva el loop A-B",
                            lambda: None, checkable=True)
        self.tb_loop.clicked.connect(
            lambda: self._acc_visor("set_loop", self.tb_loop.isChecked()))
        bar.addSeparator()
        boto("🔍−", "Allunya el zoom", lambda: self._acc_visor("zoom", 2.0))
        boto("🔍+", "Apropa el zoom", lambda: self._acc_visor("zoom", 0.5))
        boto("Tot", "Zoom total (veure-ho tot)",
             lambda: self._acc_visor("zoom_tot"))
        self.tb_mut = boto("🔇", "Silencia / reactiva el so",
                           lambda: None, checkable=True)
        self.tb_mut.clicked.connect(
            lambda: self._acc_visor("set_mut", self.tb_mut.isChecked()))
        bar.addSeparator()
        # metrònom: només en mode BPM · compàs (vegeu _actualitza_metro_ui)
        self.b_metro = QPushButton("🥁")
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
            except Exception:  # noqa: BLE001
                info = None
        if info:
            self.wav_info.setText(
                f"{info['durada']:.1f} s · {info['canals']} canals · "
                f"{info['mostreig']} Hz")

    def executa(self):
        wav = self.wav_edit.text().strip()
        if not wav or not os.path.isfile(wav):
            QMessageBox.warning(self, "Auto Chords",
                                "Tria una wav vàlida primer.")
            return
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
                           self.tempo_fix.isChecked())
        self.feina.missatge.connect(self.registra)
        self.feina.progres.connect(self.barra.setValue)
        self.feina.feta.connect(self.acabada)
        self.feina.start()

    def _executa_i_exporta_final(self):
        self.executa()

    def acabada(self, be, dada):
        self.b_exec.setEnabled(True)
        if be:
            self.b_export.setEnabled(True)
            self.registra("FET ✅ — ara pots revisar el visor i fer Finalitza i publica.")
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
            self.registra("Exportació feta ✅")
            QMessageBox.information(
                self, "Auto Chords",
                f"Exportació feta a:\n{self.sortida}")
            self.obre_carpeta()
        except Exception as e:  # noqa: BLE001
            self.registra(f"exporta ERROR: {e}")
            QMessageBox.critical(self, "Auto Chords",
                                 f"No s'ha pogut exportar:\n{e}")

    def obre_carpeta(self):
        if self.sortida and os.path.isdir(self.sortida):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.sortida))
        else:
            QMessageBox.information(self, "Auto Chords",
                                    "Encara no hi ha cap resultat.")


def main():
    logger = setup_logging(DEFAULT_LOG_PATH)
    logger.info("Inici de l'aplicació | argv=%s cwd=%s", sys.argv, os.getcwd())

    lock_path = os.path.join(tempfile.gettempdir(), "auto_chords_single_instance.lock")
    lock_file = open(lock_path, "w", encoding="utf-8")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
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
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()
        try:
            os.unlink(lock_path)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
