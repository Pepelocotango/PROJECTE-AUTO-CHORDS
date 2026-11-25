"""Diàleg d'anàlisi de BPM/beats."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QLabel, QSlider, QVBoxLayout,
)

from app import bpm_unit
from .opcions import BEATS_DEFECTES, carrega_opcions

from app.finestres import GeometriaMixin
from app.info_box import InfoDialogMixin

class DialegAnalitzaBPM(InfoDialogMixin, GeometriaMixin, QDialog):
    """Opcions de l'acció separada «Analitza BPM».

    No detecta res: només tria motor i sensibilitat. La detecció la fa la
    finestra, perquè el diàleg no bloquege el fil de la GUI.
    """

    def __init__(self, parent=None, opcions=None, num=4, den=4,
                 beat_unit=None, bpm=120.0, permet_aplica_bpm=True):
        super().__init__(parent)
        self.setWindowTitle("Analitza beats, downbeats i BPM")
        self._permet_aplica_bpm = bool(permet_aplica_bpm)
        self.setMinimumWidth(460)
        self._num = int(num) if int(num) > 0 else 4
        self._den = int(den) if int(den) > 0 else 4
        self._bpm_intern = float(bpm or 120.0)
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

        self.cb_unitat = QComboBox()
        self._unitat_suggerida = bpm_unit.unitat_per_defecte(
            self._num, self._den)
        for clau, etiqueta in bpm_unit.opcions():
            if bpm_unit.encaixa_en_compas(clau, self._num, self._den):
                self.cb_unitat.addItem(etiqueta, clau)
        candidata = bpm_unit.normalitza(
            beat_unit or d.get("beat_unit") or self._unitat_suggerida)
        idx = self.cb_unitat.findData(candidata)
        if idx < 0:
            idx = self.cb_unitat.findData(self._unitat_suggerida)
        self.cb_unitat.setCurrentIndex(max(0, idx))
        self.cb_unitat.setToolTip(
            "Pols que perceb el músic i que ha de seguir el detector QM. "
            f"Per a {self._num}/{self._den} se suggerix "
            f"{bpm_unit.etiqueta(self._unitat_suggerida).lower()}, però pots "
            "triar negra, negra amb punt, corxera…")
        form.addRow("Pols percebuda (BPM):", self.cb_unitat)
        self.lb_bpm_percebut = QLabel("")
        self.lb_bpm_percebut.setObjectName("secundari")
        form.addRow("", self.lb_bpm_percebut)
        self.cb_unitat.currentIndexChanged.connect(self._actualitza_pols)
        self._actualitza_pols()

        self.sl = QSlider(Qt.Horizontal)
        self.sl.setToolTip("Sensibilitat del detector de beats (0=estable, 100=sensible)")
        self.sl.setRange(0, 100)
        self.sl.setValue(int(d.get("sensibilitat", 50)))
        self.lb_sens = QLabel("")
        self.sl.valueChanged.connect(self._actualitza_sens)
        self._actualitza_sens()
        form.addRow("Sensibilitat:", self.sl)
        form.addRow("", self.lb_sens)
        self.sp_prom = QDoubleSpinBox()
        self.sp_prom.setRange(0.0, 40.0)
        self.sp_prom.setSingleStep(1.0)
        self.sp_decimals = 1
        self.sp_prom.setDecimals(self.sp_decimals)
        self.sp_prom.setSuffix(" dB")
        self.sp_prom.setValue(float(d.get("prominencia_db", 0.0)))
        self.sp_prom.setToolTip(
            "Prominència mínima del pic respecte del percentil 90. "
            "0 = desactivat.")
        form.addRow("Prominència mínima:", self.sp_prom)

        self.sp_trans = QDoubleSpinBox()
        self.sp_trans.setRange(0.0, 24.0)
        self.sp_trans.setSingleStep(1.0)
        self.sp_trans.setDecimals(1)
        self.sp_trans.setSuffix(" dB")
        self.sp_trans.setValue(float(d.get("transiente_db", 0.0)))
        self.sp_trans.setToolTip(
            "Augment mínim de RMS entre els 20 ms abans i després de "
            "l'onset. 0 = desactivat.")
        form.addRow("Transitori mínim:", self.sp_trans)

        self.cb_aplica = QCheckBox(
            "Aplica el BPM detectat al transport (si el mapa és d'un sol tram)")
        self.cb_aplica.setToolTip("Si esta activat, el BPM detectat s'aplica al transport quan el mapa te un sol tram.")
        self._aplica_bpm_record = bool(d.get("aplica_bpm", True))
        self.cb_aplica.setChecked(self._aplica_bpm_record)
        if self._permet_aplica_bpm:
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
        box.button(QDialogButtonBox.Ok).setToolTip("Accepta les opcions i tanca")
        box.button(QDialogButtonBox.Cancel).setToolTip("Cancel.la i tanca")
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        lay.addWidget(box)

    def _actualitza_pols(self, *_a):
        unit = self.cb_unitat.currentData() or bpm_unit.DEFECTE
        visible = bpm_unit.de_quarter(self._bpm_intern, unit)
        self.lb_bpm_percebut.setText(
            f"BPM percebut: {visible:g} "
            f"{bpm_unit.etiqueta(unit).lower()}/min "
            f"(intern {self._bpm_intern:g} negres/min).")

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
        actiu = self._permet_aplica_bpm and not nomes
        self.cb_aplica.setEnabled(actiu)
        if not actiu:
            self.cb_aplica.setChecked(False)
        elif hasattr(self, "_aplica_bpm_record"):
            self.cb_aplica.setChecked(self._aplica_bpm_record)

    def valors(self):
        mode = self.cb_mode.currentData()
        return {
            "motor": self.cb_motor.currentData(),
            "sensibilitat": int(self.sl.value()),
            "prominencia_db": float(self.sp_prom.value()),
            "transiente_db": float(self.sp_trans.value()),
            "mode": mode,
            "beat_unit": self.cb_unitat.currentData() or bpm_unit.DEFECTE,
            "aplica_bpm": (bool(self.cb_aplica.isChecked())
                           and mode != "beats"
                           and self._permet_aplica_bpm),
        }
