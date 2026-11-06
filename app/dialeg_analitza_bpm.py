"""Diàleg d'anàlisi de BPM/beats."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel,
    QSlider, QVBoxLayout,
)

from .opcions import BEATS_DEFECTES, carrega_opcions

class DialegAnalitzaBPM(QDialog):
    """Opcions de l'acció separada «Analitza BPM».

    No detecta res: només tria motor i sensibilitat. La detecció la fa la
    finestra, perquè el diàleg no bloquege el fil de la GUI.
    """

    def __init__(self, parent=None, opcions=None):
        super().__init__(parent)
        self.setWindowTitle("Analitza BPM")
        self.setMinimumWidth(420)
        base = opcions or carrega_opcions()
        d = dict(BEATS_DEFECTES)
        d.update(base.get("beats") or {})
        lay = QVBoxLayout(self)

        info = QLabel(
            "Detecta beats i downbeats i els mostra com a línies sobre "
            "l'ona. No reanalitza acords ni estructura.")
        info.setWordWrap(True)
        info.setStyleSheet("color:#9aa6b8; font-size:11px;")
        lay.addWidget(info)

        form = QFormLayout()
        self.cb_mode = QComboBox()
        self.cb_mode.addItem("Només beats (sense BPM, compàs ni downbeats)",
                             "beats")
        self.cb_mode.addItem("BPM + beats + downbeats", "bpm")
        i = self.cb_mode.findData(d.get("mode", "beats"))
        self.cb_mode.setCurrentIndex(i if i >= 0 else 0)
        self.cb_mode.setToolTip(
            "Només beats: no agrupa en compassos, no mostra BPM ni downbeats. "
            "És el mode recomanat per a un WAV sense graella prèvia.")
        form.addRow("Què detects:", self.cb_mode)
        self.cb_mode.currentIndexChanged.connect(self._actualitza_mode)

        self.cb_motor = QComboBox()
        self.cb_motor.addItem("Nostre (tempo.py)", "nostre")
        self.cb_motor.addItem("Queen Mary (qm-barbeattracker)", "qm")
        i = self.cb_motor.findData(d.get("motor", "qm"))
        self.cb_motor.setCurrentIndex(i if i >= 0 else 0)
        self.cb_motor.setToolTip(
            "Nostre: onsets + DP d'Ellis. Queen Mary: bar/beat tracker "
            "de Vamp. La sensibilitat s'adapta a cada motor.")
        form.addRow("Motor:", self.cb_motor)

        self.sl = QSlider(Qt.Horizontal)
        self.sl.setRange(0, 100)
        self.sl.setValue(int(d.get("sensibilitat", 50)))
        self.lb_sens = QLabel("")
        self.sl.valueChanged.connect(self._actualitza_sens)
        self._actualitza_sens()
        form.addRow("Sensibilitat:", self.sl)
        form.addRow("", self.lb_sens)

        self.cb_aplica = QCheckBox(
            "Aplica el BPM detectat al transport (si el mapa és d'un sol tram)")
        self._aplica_bpm_record = bool(d.get("aplica_bpm", True))
        self.cb_aplica.setChecked(self._aplica_bpm_record)
        form.addRow(self.cb_aplica)
        self._actualitza_mode()

        nota = QLabel(
            "Sensibilitat baixa = més estable (menys canvis). "
            "Sensibilitat alta = més flexible (accepta més variació).")
        nota.setWordWrap(True)
        nota.setStyleSheet("color:#9aa6b8; font-size:11px;")
        form.addRow(nota)
        lay.addLayout(form)

        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        lay.addWidget(box)

    def _actualitza_sens(self):
        v = int(self.sl.value())
        if v < 34:
            t = "estable"
        elif v < 67:
            t = "equilibrada"
        else:
            t = "sensible"
        self.lb_sens.setText(f"{v}/100 · {t}")

    def _actualitza_mode(self):
        nomes = self.cb_mode.currentData() == "beats"
        self.cb_aplica.setEnabled(not nomes)
        if nomes:
            self.cb_aplica.setChecked(False)
        elif hasattr(self, "_aplica_bpm_record"):
            self.cb_aplica.setChecked(self._aplica_bpm_record)

    def valors(self):
        mode = self.cb_mode.currentData()
        return {
            "motor": self.cb_motor.currentData(),
            "sensibilitat": int(self.sl.value()),
            "mode": mode,
            "aplica_bpm": bool(self.cb_aplica.isChecked()) and mode != "beats",
        }
