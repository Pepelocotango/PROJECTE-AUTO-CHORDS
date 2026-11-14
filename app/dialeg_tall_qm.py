"""Diàleg conjunt per triar les opcions d'un tall amb Beats QM."""
from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QGridLayout, QLabel, QListWidget,
    QWidget,
)


class DialegTallQM(QDialog):
    """Dues columnes d'opcions, una per costat del tall.

    Si un costat només té una opció, es mostra com a resum fix. No hi ha cap
    selecció inicial: Aplica s'activa quan cada costat ambigu té una opció.
    """

    def __init__(self, parent, esquerra, dreta):
        super().__init__(parent)
        self.setWindowTitle("Tall de tempo — Beats QM")
        self._esquerra = list(esquerra or ())
        self._dreta = list(dreta or ())
        self._lista_esq = None
        self._lista_dreta = None

        lay = QGridLayout(self)
        lay.addWidget(QLabel("<b>Costat esquerre</b>"), 0, 0)
        lay.addWidget(QLabel("<b>Costat dret</b>"), 0, 1)
        lay.addWidget(self._columna(self._esquerra, "esq"), 1, 0)
        lay.addWidget(self._columna(self._dreta, "dreta"), 1, 1)

        self._botons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        self._botons.button(QDialogButtonBox.Ok).setText("Aplica")
        self._botons.button(QDialogButtonBox.Cancel).setText("Cancel·la")
        self._botons.accepted.connect(self.accept)
        self._botons.rejected.connect(self.reject)
        lay.addWidget(self._botons, 2, 0, 1, 2)
        self._actualitza_boto()
        self.resize(760, 320)

    def _columna(self, opcions, costat):
        w = QWidget(self)
        v = QGridLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        if len(opcions) <= 1:
            text = opcions[0]["etiqueta"] if opcions else "Sense opcions"
            lab = QLabel(text, w)
            lab.setWordWrap(True)
            lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
            v.addWidget(lab, 0, 0)
            return w
        lista = QListWidget(w)
        for o in opcions:
            lista.addItem(o["etiqueta"])
        lista.setSelectionMode(QListWidget.SingleSelection)
        lista.itemSelectionChanged.connect(self._actualitza_boto)
        v.addWidget(lista, 0, 0)
        if costat == "esq":
            self._lista_esq = lista
        else:
            self._lista_dreta = lista
        return w

    def _actualitza_boto(self):
        ok = True
        if self._lista_esq is not None and not self._lista_esq.selectedItems():
            ok = False
        if self._lista_dreta is not None and not self._lista_dreta.selectedItems():
            ok = False
        self._botons.button(QDialogButtonBox.Ok).setEnabled(ok)

    def seleccions(self):
        """Retorna `(idx_esquerra, idx_dreta)`; `0` si el costat és fix."""
        i_esq = (self._lista_esq.currentRow()
                 if self._lista_esq is not None else 0)
        i_dreta = (self._lista_dreta.currentRow()
                   if self._lista_dreta is not None else 0)
        return max(0, int(i_esq)), max(0, int(i_dreta))
