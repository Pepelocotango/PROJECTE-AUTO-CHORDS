"""Diàleg per veure i canviar totes les dreceres de teclat."""
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
    QKeySequenceEdit, QLineEdit, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from . import dreceres


class DialegDreceres(QDialog):
    """Taula editable de dreceres amb cerca, restauració i control de xocs."""

    def __init__(self, parent=None, entrades=None):
        super().__init__(parent)
        self.setWindowTitle("Dreceres de teclat")
        self.setMinimumSize(760, 520)
        self._entrades = list(entrades or ())
        self._editors = {}
        self.bindings = {}

        lay = QVBoxLayout(self)
        fila = QHBoxLayout()
        fila.addWidget(QLabel("Cerca:"))
        self.ed_cerca = QLineEdit()
        self.ed_cerca.setPlaceholderText("Filtra per acció o grup…")
        self.ed_cerca.textChanged.connect(self._filtra)
        fila.addWidget(self.ed_cerca, 1)
        lay.addLayout(fila)

        self.taula = QTableWidget(len(self._entrades), 3, self)
        self.taula.setHorizontalHeaderLabels(
            ["Acció", "Drecera", "Grup"])
        self.taula.verticalHeader().setVisible(False)
        self.taula.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.taula.setSelectionMode(QAbstractItemView.SingleSelection)
        self.taula.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.taula.horizontalHeader().setStretchLastSection(True)
        self.taula.setColumnWidth(0, 380)
        self.taula.setColumnWidth(1, 190)

        for i, e in enumerate(self._entrades):
            item = QTableWidgetItem(e["etiqueta"])
            item.setData(Qt.UserRole, e["id"])
            self.taula.setItem(i, 0, item)
            grup = QTableWidgetItem(e.get("grup") or "")
            grup.setFlags(grup.flags() & ~Qt.ItemIsEditable)
            self.taula.setItem(i, 2, grup)
            if e.get("tipus") == "fix":
                self.taula.setItem(i, 1, QTableWidgetItem(
                    e.get("defecte") or "—"))
                self.taula.item(i, 1).setFlags(
                    self.taula.item(i, 1).flags() & ~Qt.ItemIsEditable)
                continue
            ed = QKeySequenceEdit(self)
            if hasattr(ed, "setMaximumSequenceLength"):
                ed.setMaximumSequenceLength(1)
            ed.setKeySequence(QKeySequence(e.get("valor", e.get("defecte", ""))))
            self.taula.setCellWidget(i, 1, ed)
            self._editors[e["id"]] = (e, ed)
        lay.addWidget(self.taula, 1)

        peu = QHBoxLayout()
        self.b_esborra = QPushButton("Esborra la seleccionada")
        self.b_esborra.clicked.connect(self._esborra_seleccionada)
        self.b_restaura = QPushButton("Restaura la seleccionada")
        self.b_restaura.clicked.connect(self._restaura_seleccionada)
        self.b_restaura_tot = QPushButton("Restaura totes")
        self.b_restaura_tot.clicked.connect(self._restaura_totes)
        peu.addWidget(self.b_esborra)
        peu.addWidget(self.b_restaura)
        peu.addWidget(self.b_restaura_tot)
        peu.addStretch(1)
        lay.addLayout(peu)

        botons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botons.button(QDialogButtonBox.Ok).setText("Desa")
        botons.accepted.connect(self.accept)
        botons.rejected.connect(self.reject)
        lay.addWidget(botons)

    def _filtra(self, text):
        text = (text or "").strip().lower()
        for fila in range(self.taula.rowCount()):
            accio = self.taula.item(fila, 0)
            grup = self.taula.item(fila, 2)
            hay = (text in (accio.text() if accio else "").lower()
                   or text in (grup.text() if grup else "").lower())
            self.taula.setRowHidden(fila, bool(text) and not hay)

    def _clau_seleccionada(self):
        files = self.taula.selectionModel().selectedRows()
        if not files:
            return None
        item = self.taula.item(files[0].row(), 0)
        return item.data(Qt.UserRole) if item else None

    def _esborra_seleccionada(self):
        dades = self._editors.get(self._clau_seleccionada())
        if dades:
            dades[1].clear()

    def _restaura_seleccionada(self):
        dades = self._editors.get(self._clau_seleccionada())
        if dades:
            dades[1].setKeySequence(QKeySequence(dades[0]["defecte"] or ""))

    def _restaura_totes(self):
        for e, ed in self._editors.values():
            ed.setKeySequence(QKeySequence(e["defecte"] or ""))

    def _valors(self):
        out = {}
        for clau, (e, ed) in self._editors.items():
            out[clau] = dreceres.normalitza(
                ed.keySequence().toString(QKeySequence.PortableText))
        return out

    def accept(self):
        valors = self._valors()
        vistos = {}
        xocs = []
        for e in self._entrades:
            if e.get("tipus") == "fix":
                continue
            seq = valors.get(e["id"], "")
            if seq and QKeySequence(seq).count() > 1 \
                    and e.get("tipus") in ("raw", "timeline"):
                QMessageBox.warning(
                    self, "Drecera no vàlida",
                    f"«{e['etiqueta']}» necessita una sola tecla "
                    "(no una combinació de diverses pulsacions).")
                return
            if not seq:
                continue
            if seq in vistos:
                xocs.append(f"«{seq}»: {vistos[seq]} ↔ {e['etiqueta']}")
            else:
                vistos[seq] = e["etiqueta"]
        if xocs:
            QMessageBox.warning(
                self, "Dreceres en conflicte",
                "Hi ha dreceres repetides; canvia-les abans de desar:\n\n"
                + "\n".join(xocs))
            return
        self.bindings = valors
        super().accept()
