"""Diàleg de trobar i reemplaçar xifrats o etiquetes."""
from PyQt5.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit,
    QVBoxLayout,
)

class DialegTrobaReemplaca(QDialog):
    """Troba i reemplaça un xifrat (acords) o una etiqueta (estructura), a tot el tema."""

    def __init__(self, parent=None, camp="acords"):
        super().__init__(parent)
        self.setWindowTitle("Troba i reemplaça")
        self.setMinimumWidth(400)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.cb_camp = QComboBox()
        self.cb_camp.addItem("Acords (xifrats)", "acords")
        self.cb_camp.addItem("Estructura (etiquetes)", "estructura")
        self.cb_camp.setCurrentIndex(1 if camp == "estructura" else 0)
        self.ed_troba = QLineEdit()
        self.ed_troba.setPlaceholderText("p. ex. Cmaj7   ·   D")
        self.ed_reemplaca = QLineEdit()
        self.ed_reemplaca.setPlaceholderText("p. ex. C9   ·   estribillo")
        form.addRow("Camp:", self.cb_camp)
        form.addRow("Troba:", self.ed_troba)
        form.addRow("Reemplaça per:", self.ed_reemplaca)
        lay.addLayout(form)
        avis = QLabel("Substitueix TOTES les aparicions exactes al tema, en una "
                      "sola operació de desfer. Si no en troba cap, no fa res.")
        avis.setWordWrap(True)
        lay.addWidget(avis)
        botons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botons.accepted.connect(self.accept)
        botons.rejected.connect(self.reject)
        lay.addWidget(botons)

    def camp(self):
        return self.cb_camp.currentData()

    def troba(self):
        return self.ed_troba.text().strip()

    def reemplaca(self):
        return self.ed_reemplaca.text().strip()
