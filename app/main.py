#!/usr/bin/env python3
# main.py — Auto Chords (PyQt5/Qt5: l'únic Qt que corre al Q9400) —
#           wav -> acords + estructura -> carpetes. Tot en català.
import os
import subprocess
import sys

from PyQt5.QtCore import QObject, QThread, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QDoubleSpinBox, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QProgressBar, QPushButton, QSpinBox, QTextEdit, QVBoxLayout, QWidget,
)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
import pipeline  # noqa: E402

FOSC = """
QWidget { background: #202124; color: #e8eaed; font-size: 13px; }
QGroupBox { border: 1px solid #5f6368; border-radius: 6px; margin-top: 14px;
            padding-top: 8px; font-weight: bold; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; }
QLineEdit, QTextEdit { background: #303134; border: 1px solid #5f6368;
                       border-radius: 4px; padding: 4px; }
QPushButton { background: #8ab4f8; color: #202124; border-radius: 6px;
              padding: 7px 14px; font-weight: bold; }
QPushButton:disabled { background: #5f6368; color: #9aa0a6; }
QPushButton#secundari { background: #303134; color: #e8eaed;
                        border: 1px solid #5f6368; font-weight: normal; }
QProgressBar { border: 1px solid #5f6368; border-radius: 4px; height: 14px;
               text-align: center; }
QProgressBar::chunk { background: #8ab4f8; }
QSpinBox, QDoubleSpinBox { background: #303134; border: 1px solid #5f6368;
                           border-radius: 4px; padding: 3px; }
QTextEdit#log { font-family: monospace; font-size: 12px; }
"""


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
        self.setWindowTitle("Auto Chords — wav → acords + estructura")
        self.resize(640, 560)
        self.feina = None

        arrel = QWidget()
        self.setCentralWidget(arrel)
        capa = QVBoxLayout(arrel)

        # 1. wav
        g1 = QGroupBox("1 · Tria la wav")
        f1 = QHBoxLayout(g1)
        self.wav_edit = QLineEdit()
        self.wav_edit.setPlaceholderText("/camí/al/tema.wav")
        b_tria = QPushButton("Tria...")
        b_tria.setObjectName("secundari")
        b_tria.clicked.connect(self.tria_wav)
        f1.addWidget(self.wav_edit)
        f1.addWidget(b_tria)
        capa.addWidget(g1)
        self.wav_info = QLabel("")
        capa.addWidget(self.wav_info)

        # 2. paràmetres
        g2 = QGroupBox("2 · Paràmetres")
        f2 = QFormLayout(g2)
        self.bpm = QDoubleSpinBox()
        self.bpm.setRange(40, 240)
        self.bpm.setValue(138.0)
        self.bpb = QSpinBox()
        self.bpb.setRange(2, 12)
        self.bpb.setValue(4)
        self.offset = QDoubleSpinBox()
        self.offset.setRange(0, 60)
        self.offset.setSingleStep(0.1)
        self.offset.setValue(0.0)
        self.amb_est = QCheckBox("Inclou estructura (Segmentino → ABC)")
        self.amb_est.setChecked(True)
        self.tempo_fix = QCheckBox("La wav té tempo fix (graella BPM)")
        self.tempo_fix.setChecked(True)
        self.tempo_fix.toggled.connect(self._canvia_tempo)
        f2.addRow("BPM:", self.bpm)
        f2.addRow("Temps per compàs:", self.bpb)
        f2.addRow("Offset compàs 1 (s):", self.offset)
        f2.addRow(self.tempo_fix)
        f2.addRow(self.amb_est)
        capa.addWidget(g2)

        # 3. executa
        g3 = QGroupBox("3 · Executa")
        f3 = QVBoxLayout(g3)
        fila = QHBoxLayout()
        self.b_exec = QPushButton("Executa")
        self.b_exec.clicked.connect(self.executa)
        self.b_visor = QPushButton("Obre visor")
        self.b_visor.setObjectName("secundari")
        self.b_visor.clicked.connect(self.obre_visor)
        self.b_carpeta = QPushButton("Obre la carpeta")
        self.b_carpeta.setObjectName("secundari")
        self.b_carpeta.clicked.connect(self.obre_carpeta)
        fila.addWidget(self.b_exec)
        fila.addWidget(self.b_visor)
        fila.addWidget(self.b_carpeta)
        f3.addLayout(fila)
        self.barra = QProgressBar()
        f3.addWidget(self.barra)
        self.log = QTextEdit()
        self.log.setObjectName("log")
        self.log.setReadOnly(True)
        f3.addWidget(self.log)
        capa.addWidget(g3)

        self.sortida = ""
        for p in (pipeline.SONIC, pipeline.ACORDS_PY,
                  *pipeline.VAMP_DIRS):
            if not os.path.exists(p):
                self.registra(f"AVÍS: no trobo {p}")

    def registra(self, t):
        self.log.append(t)

    def _canvia_tempo(self, fix):
        for w in (self.bpm, self.bpb, self.offset):
            w.setEnabled(fix)

    def tria_wav(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Tria la wav", "", "Àudio WAV (*.wav)")
        if ruta:
            self.wav_edit.setText(ruta)
            try:
                info = pipeline.wav_info(ruta)
                self.wav_info.setText(
                    f"{info['durada']:.1f} s · {info['canals']} canals · "
                    f"{info['mostreig']} Hz")
            except Exception as e:  # noqa: BLE001
                self.wav_info.setText(f"No és una wav vàlida: {e}")

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
        self.feina = Feina(wav, self.sortida, self.bpm.value(),
                           self.bpb.value(), self.offset.value(),
                           self.amb_est.isChecked(),
                           self.tempo_fix.isChecked())
        self.feina.missatge.connect(self.registra)
        self.feina.progres.connect(self.barra.setValue)
        self.feina.feta.connect(self.acabada)
        self.feina.start()

    def acabada(self, be, dada):
        self.b_exec.setEnabled(True)
        if be:
            self.registra("FET ✅ — obre la carpeta i arrossega al DAW.")
            self.barra.setValue(100)
        else:
            self.registra(f"ERROR: {dada}")
            QMessageBox.critical(self, "Auto Chords", dada)

    def obre_visor(self):
        wav = self.wav_edit.text().strip()
        if not wav or not os.path.isfile(wav):
            QMessageBox.warning(self, "Auto Chords",
                                "Tria una wav vàlida abans d'obrir el visor.")
            return
        cmd = [sys.executable, os.path.join(os.path.dirname(__file__), "visor.py"), wav]
        if self.sortida:
            acords_csv = os.path.join(self.sortida, "acords.csv")
            abc_csv = os.path.join(self.sortida, "estructura_ABC.csv")
            if os.path.isfile(acords_csv):
                cmd.extend(["--acords", acords_csv])
            if os.path.isfile(abc_csv):
                cmd.extend(["--abc", abc_csv])
        cmd.extend(["--bpm", str(self.bpm.value()), "--bpb", str(self.bpb.value())])
        self.registra(f"Visor: {' '.join(cmd)}")
        try:
            subprocess.Popen(cmd, cwd=os.path.dirname(__file__), start_new_session=True)
            self.registra("Visor obert ✅")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Auto Chords",
                                 f"No s'ha pogut obrir el visor:\n{e}")

    def obre_carpeta(self):
        if self.sortida and os.path.isdir(self.sortida):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.sortida))
        else:
            QMessageBox.information(self, "Auto Chords",
                                    "Encara no hi ha cap resultat.")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(FOSC)
    w = Finestra()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
