"""Diàleg de quantització a la graella."""
from PyQt5.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QVBoxLayout,
)

from app import graella

class DialegQuantitza(QDialog):
    """Quantització del model: abast + graella d'acords i d'estructura.

    No toca BPM, compàs, offset ni el cru. Només decideix QUÈ es quantitza i
    amb quina graella; l'operació és una sola i es pot desfer/refer.
    """

    def __init__(self, parent=None, abast="tot", te_acords=True,
                 te_seccions=True):
        super().__init__(parent)
        self.setWindowTitle("Quantitza")
        self.setMinimumWidth(460)
        self._te_acords = bool(te_acords)
        self._te_seccions = bool(te_seccions)
        lay = QVBoxLayout(self)
        form = QFormLayout()

        self.cb_abast = QComboBox()
        for text, clau in (("Tot (acords i estructura)", "tot"),
                           ("Només la selecció", "seleccio"),
                           ("Tot, només acords", "acords"),
                           ("Tot, només estructura", "estructura")):
            self.cb_abast.addItem(text, clau)
        i = self.cb_abast.findData(abast)
        if i >= 0:
            self.cb_abast.setCurrentIndex(i)

        self.cb_acords = QComboBox()
        for et, clau in graella.GRID_ACORDS:
            self.cb_acords.addItem(et, clau)
        self.cb_estructura = QComboBox()
        for et, clau in graella.GRID_ESTRUCTURA:
            self.cb_estructura.addItem(et, clau)
        # Valors inicials raonables: negra per a l'harmonia, 4 compassos per a
        # les frases. L'usuari els pot canviar.
        i = self.cb_acords.findData("negra")
        if i >= 0:
            self.cb_acords.setCurrentIndex(i)
        i = self.cb_estructura.findData("compas4")
        if i >= 0:
            self.cb_estructura.setCurrentIndex(i)

        form.addRow("Abast:", self.cb_abast)
        form.addRow("Graella d'acords:", self.cb_acords)
        form.addRow("Graella d'estructura:", self.cb_estructura)
        lay.addLayout(form)

        avis = QLabel("Només es mouen els INICIS dels clips. El final de cada "
                      "clip es deriva del següent i l'últim arriba a la durada "
                      "del WAV. No es toca BPM, compàs, offset ni el cru de "
                      "l'anàlisi. Tot és una sola operació de desfer.")
        avis.setWordWrap(True)
        lay.addWidget(avis)

        self.botons = QDialogButtonBox(QDialogButtonBox.Ok |
                                       QDialogButtonBox.Cancel)
        self.botons.button(QDialogButtonBox.Ok).setText("Quantitza")
        self.botons.button(QDialogButtonBox.Cancel).setText("Cancel·la")
        self.botons.accepted.connect(self.accept)
        self.botons.rejected.connect(self.reject)
        lay.addWidget(self.botons)

        self.cb_abast.currentIndexChanged.connect(self._actualitza)
        self._actualitza()

    def _actualitza(self):
        abast = self.abast()
        te_ac = abast in ("tot", "acords") or (
            abast == "seleccio" and self._te_acords)
        te_es = abast in ("tot", "estructura") or (
            abast == "seleccio" and self._te_seccions)
        self.cb_acords.setEnabled(te_ac)
        self.cb_estructura.setEnabled(te_es)
        ok = self.botons.button(QDialogButtonBox.Ok)
        if ok is not None:
            ok.setEnabled(te_ac or te_es)

    def abast(self):
        return self.cb_abast.currentData()

    def grid_acords(self):
        return self.cb_acords.currentData()

    def grid_estructura(self):
        return self.cb_estructura.currentData()
