"""Diàleg de detecció de tempo per trams."""
from PyQt5.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QLabel, QSpinBox, QVBoxLayout,
)

from app import bpm_unit
from app.finestres import GeometriaMixin
from app.info_box import InfoDialogMixin

class DialegTempoPerTrams(InfoDialogMixin, GeometriaMixin, QDialog):
    """«Detecta el tempo per trams»: mapa de BPM cada N compassos.

    És l'acció automàtica per a cançons amb **tempo variable**: es detecta un
    BPM cada `cada` compassos (per defecte 4) i les fronteres cauen sempre en
    una línia de compàs. Els veïns amb un BPM quasi igual es fusionen.
    """

    def __init__(self, parent, durada=0.0, num=4, den=4, cada=4,
                 tolerancia=2, unit=None):
        super().__init__(parent)
        self.setWindowTitle("Detecta el tempo per trams")
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        exp = QLabel(
            "Analitza els temps de la cançó i crea un tram de BPM cada pocs "
            "compassos. Pensat per a temes amb tempo variable (directes, "
            "ritardandos, canvis de secció).")
        exp.setWordWrap(True)
        lay.addWidget(exp)
        form = QFormLayout()
        self.sp_cada = QSpinBox()
        self.sp_cada.setRange(1, 64)
        self.sp_cada.setValue(max(1, int(cada)))
        self.sp_cada.setSuffix(" compassos")
        self.sp_cada.setToolTip(
            "Cada quants compassos es mesura un BPM nou. 4 és un bon equilibri "
            "entre precisió i nombre de trams.")
        form.addRow("Nova mesura cada:", self.sp_cada)
        self.sp_tol = QDoubleSpinBox()
        self.sp_tol.setRange(0.0, 10.0)
        self.sp_tol.setDecimals(1)
        self.sp_tol.setSingleStep(0.5)
        self.sp_tol.setValue(float(tolerancia))
        self.sp_tol.setSuffix(" %")
        self.sp_tol.setToolTip(
            "Els trams veïns amb menys diferència de BPM es fusionen en un de "
            "sol (evita mapes de mil trams per vibrato o micro-deriva).")
        form.addRow("Fusiona si el BPM difereix menys de:", self.sp_tol)
        self.cb_unitat = QComboBox()
        self.cb_unitat.setToolTip(
            "Figura que segueix el detector de beats. En 2/2 pot ser blanca "
            "o negra; en 3/8, corxera o negra amb punt. Si no ho tens clar, "
            "deixa la unitat per defecte del compàs.")
        for _clau, _et in bpm_unit.opcions():
            if bpm_unit.encaixa_en_compas(_clau, int(num), int(den)):
                self.cb_unitat.addItem(_et, _clau)
        _unit = bpm_unit.normalitza(
            unit or bpm_unit.unitat_per_defecte(int(num), int(den), ""))
        _idx = self.cb_unitat.findData(_unit)
        if _idx < 0:
            _idx = 0
        if _idx >= 0:
            self.cb_unitat.setCurrentIndex(_idx)
        form.addRow("Pols que segueix el detector:", self.cb_unitat)
        lay.addLayout(form)
        self.lb_info = QLabel(
            f"Durada del tema: {float(durada):.2f}s · compàs {int(num)}/"
            f"{int(den)}")
        self.lb_info.setObjectName("secundari")
        lay.addWidget(self.lb_info)
        botons = QDialogButtonBox(QDialogButtonBox.Ok
                                  | QDialogButtonBox.Cancel)
        botons.button(QDialogButtonBox.Ok).setText("Detecta")
        botons.button(QDialogButtonBox.Ok).setToolTip("Detecta el mapa de tempo per trams amb els parametres triats.")
        botons.button(QDialogButtonBox.Ok).setDefault(True)
        botons.button(QDialogButtonBox.Cancel).setText("Cancel·la")
        botons.button(QDialogButtonBox.Cancel).setToolTip("Cancel.la i tanca sense detectar.")
        botons.accepted.connect(self.accept)
        botons.rejected.connect(self.reject)
        lay.addWidget(botons)

    def valors(self):
        """`(cada_compassos, tolerancia_fraccio)`."""
        return (int(self.sp_cada.value()),
                float(self.sp_tol.value()) / 100.0)

    def unitat(self):
        """Unitat del beat que segueix el detector."""
        return self.cb_unitat.currentData() or bpm_unit.DEFECTE
