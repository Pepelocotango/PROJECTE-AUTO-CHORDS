#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Triar el BPM deduït dels marcadors (llista de candidats).

Els marcadors són inicis de compàs, però la distància entre dos pot ser 4, 8 o
16 compassos: hi ha **ambigüitat** (10 s poden ser 4 compassos a 96 BPM o 6 a
144). Per això no s'imposa un valor: es mostren els candidats ordenats pel més
proper al BPM de la barra i decidix l'operador.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QDialog, QHBoxLayout, QLabel, QListWidget,
                             QListWidgetItem, QPushButton, QVBoxLayout)


class DialegBpmMarcadors(QDialog):
    """Llista de BPM compatibles amb els marcadors (doble clic = acceptar)."""

    def __init__(self, candidats, parent=None, num=4, den=4):
        super().__init__(parent)
        self.setWindowTitle("BPM a partir dels marcadors")
        self.setModal(True)
        self.resize(560, 300)
        self._cands = list(candidats or ())
        v = QVBoxLayout(self)
        info = QLabel(
            f"Els marcadors són inicis de compàs ({num}/{den}). Estes són les "
            "velocitats que fan que <b>tots</b> els intervals siguen compassos "
            "sencers.<br>Triues tu: la de dalt és la més propera al BPM actual "
            "de la barra.")
        info.setWordWrap(True)
        info.setTextFormat(Qt.RichText)
        v.addWidget(info)

        self.llista = QListWidget()
        for c in self._cands:
            ks = c.get("compassos") or []
            resum = " · ".join(str(k) for k in ks[:8])
            if len(ks) > 8:
                resum += " …"
            it = QListWidgetItem(
                f"{c['bpm']:.2f} BPM   (residu {c['residu']:.4f})\n"
                f"    compassos per tram: {resum}")
            it.setData(Qt.UserRole, c)
            self.llista.addItem(it)
        if self._cands:
            self.llista.setCurrentRow(0)
        self.llista.itemDoubleClicked.connect(lambda _i: self.accept())
        v.addWidget(self.llista, 1)

        f = QHBoxLayout()
        f.addStretch(1)
        self.b_ok = QPushButton("Aplica este BPM")
        self.b_ok.setDefault(True)
        self.b_ok.clicked.connect(self.accept)
        f.addWidget(self.b_ok)
        b_no = QPushButton("Cancel·la")
        b_no.clicked.connect(self.reject)
        f.addWidget(b_no)
        v.addLayout(f)

    def triat(self):
        """El candidat seleccionat (o `None`)."""
        it = self.llista.currentItem()
        return it.data(Qt.UserRole) if it is not None else None
