#!/usr/bin/env python3
# main.py — Auto Chords (PyQt5/Qt5: l'únic Qt que corre al Q9400) —
#           wav -> acords + estructura -> carpetes. Tot en català.
import fcntl
import logging
import os
import sys
import tempfile
import traceback

from PyQt5.QtCore import QObject, QThread, Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QDoubleSpinBox, QDockWidget,
    QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QProgressBar, QPushButton, QSpinBox, QTextEdit, QVBoxLayout,
    QWidget,
)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(APP_DIR)
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
import pipeline  # noqa: E402
import theme  # noqa: E402
import visor as visor_mod  # noqa: E402

DEFAULT_LOG_PATH = os.path.join(PROJECT_ROOT, "auto_chords.log")


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
                                 lliure=not self.tempo_fix)
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

        arrel = QWidget()
        self.setCentralWidget(arrel)
        capa = QVBoxLayout(arrel)

        self.visor_dock = QDockWidget("Visor", self)
        self.visor_dock.setAllowedAreas(
            Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        self.visor_dock.setFeatures(
            QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.visor_dock.setVisible(True)
        self.addDockWidget(Qt.RightDockWidgetArea, self.visor_dock)
        self.visor_widget = None
        self._mostra_placeholder_visor()

        # 1. wav
        g1 = QGroupBox("1 · Tria la wav")
        f1 = QHBoxLayout(g1)
        self.wav_edit = QLineEdit()
        self.wav_edit.setPlaceholderText("/camí/al/tema.wav")
        self.wav_edit.setToolTip("Ruta de la fitxer WAV que vols analitzar.")
        b_tria = QPushButton("Tria...")
        b_tria.setObjectName("secundari")
        b_tria.setToolTip("Selecciona la cançó o la gravació WAV a processar.")
        b_tria.clicked.connect(self.tria_wav)
        f1.addWidget(self.wav_edit)
        f1.addWidget(b_tria)
        capa.addWidget(g1)
        self.wav_info = QLabel("")
        capa.addWidget(self.wav_info)

        self.flux_label = QLabel(
            "Flux: Tria WAV → Processa → Revisa i edita → Finalitza i publica"
        )
        self.flux_label.setStyleSheet("QLabel { color: #dfe3ea; font-weight: 600; }")
        capa.addWidget(self.flux_label)

        # 2. paràmetres
        g2 = QGroupBox("2 · Paràmetres")
        f2 = QFormLayout(g2)
        self.bpm = QDoubleSpinBox()
        self.bpm.setRange(40, 240)
        self.bpm.setValue(120.0)
        self.bpb = QSpinBox()
        self.bpb.setRange(2, 12)
        self.bpb.setValue(4)
        self.offset = QDoubleSpinBox()
        self.offset.setRange(0, 60)
        self.offset.setSingleStep(0.1)
        self.offset.setValue(0.0)
        self.amb_est = QCheckBox("Inclou estructura (Segmentino → ABC)")
        self.amb_est.setChecked(True)
        self.amb_est.setToolTip("Genera la jerarquia de seccions i l’ABC de l’estructura del tema.")
        self.tempo_fix = QCheckBox("El tema té tempo fix (BPM definit)")
        self.tempo_fix.setChecked(False)
        self.tempo_fix.setToolTip(
            "Desmarca-ho si el tema no té tempo fix i vols treballar per temps reals.")
        self.tempo_fix.toggled.connect(self._canvia_tempo)
        f2.addRow("BPM:", self.bpm)
        f2.addRow("Temps per compàs:", self.bpb)
        f2.addRow("Offset compàs 1 (s):", self.offset)
        f2.addRow(self.tempo_fix)
        f2.addRow(self.amb_est)
        capa.addWidget(g2)

        # 3. executa
        g3 = QGroupBox("3 · Analitza i exporta")
        f3 = QVBoxLayout(g3)
        fila = QHBoxLayout()
        self.b_exec = QPushButton("Processa")
        self.b_exec.setToolTip("Extreu acords i estructura i genera el flux de treball del tema.")
        self.b_exec.clicked.connect(self.executa)
        self.b_export = QPushButton("Finalitza i publica")
        self.b_export.setObjectName("secundari")
        self.b_export.setToolTip("Genera la sortida final i publica el paquet llest per al DAW.")
        self.b_export.setEnabled(False)
        self.b_export.clicked.connect(self.exporta)
        fila.addWidget(self.b_exec)
        fila.addWidget(self.b_export)
        f3.addLayout(fila)
        self.barra = QProgressBar()
        f3.addWidget(self.barra)
        self.log = QTextEdit()
        self.log.setObjectName("log")
        self.log.setReadOnly(True)
        f3.addWidget(self.log)
        capa.addWidget(g3)

        self.sortida = ""
        self.b_export.setEnabled(False)
        for p in (pipeline.SONIC, pipeline.ACORDS_PY,
                  *pipeline.VAMP_DIRS):
            if not os.path.exists(p):
                self.registra(f"AVÍS: no trobo {p}")

    def registra(self, t):
        self.logger.info("UI: %s", t)
        self.log.append(t)

    def _canvia_tempo(self, fix):
        for w in (self.bpm, self.bpb, self.offset):
            w.setEnabled(fix)
        if hasattr(self, "visor_ref") and self.visor_ref is not None:
            self.visor_ref.tempo_fix = bool(fix)
            self.visor_ref._actualitza_temps()
            self.visor_ref.corba.setLabel("bottom", "compàs" if fix else "segons")

    def _mostra_placeholder_visor(self):
        cont = QWidget()
        cont.setStyleSheet(f"QWidget {{ background: {theme.BG}; color: {theme.TEXT}; }}")
        lay = QVBoxLayout(cont)
        lay.setContentsMargins(20, 20, 20, 20)
        label = QLabel("Sense WAV carregada\n\nSelecciona una WAV per activar el visor.")
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        lay.addWidget(label)
        self.visor_dock.setWidget(cont)
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
                self.logger.info("No hi ha resultat processat per %s; mostro placeholder", wav)
                self.visor_ref = None
                self._mostra_placeholder_visor()
                return

            self.logger.info("Carregant visor per %s | sortida=%s", wav, self.sortida)
            visor = visor_mod.Visor(
                os.path.abspath(wav),
                acords_csv,
                abc_csv,
                self.bpm.value(),
                self.bpb.value(),
                tempo_fix=self.tempo_fix.isChecked(),
            )
            self.visor_ref = visor
            self.visor_widget = visor.centralWidget()
            self.visor_widget.setParent(self.visor_dock)
            self.visor_dock.setWidget(self.visor_widget)
            self.visor_widget.show()
            self.visor_dock.setVisible(True)
            self.visor_dock.raise_()
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
                self.wav_info.setText(
                    f"{info['durada']:.1f} s · {info['canals']} canals · "
                    f"{info['mostreig']} Hz")
                self._carrega_visor(ruta)
            except Exception as e:  # noqa: BLE001
                self.logger.exception("WAV no vàlida: %s", ruta)
                self.wav_info.setText(f"No és una wav vàlida: {e}")
                self._mostra_placeholder_visor()

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
        self.feina = Feina(wav, self.sortida, self.bpm.value(),
                           self.bpb.value(), self.offset.value(),
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
                bpm=self.bpm.value(),
                bpb=self.bpb.value(),
                offset=self.offset.value(),
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
