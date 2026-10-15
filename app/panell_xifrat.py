#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Panell «Tipus d'acord» — construeix un xifrat clicant (dock de l'esquerra).

- **Fila 1**: `Arrel` i `Baix` (camps de **text lliure**; poden anar buits).
- **Llista plana** de tots els tipus, de menys a més complex. Cada fila:
  `tipus·alternatius` (el tipus clar, els alternatius en verd) i, a sota, els
  **graus** (gris): dades de `xifrat.TAULA_TIPUS` (font única).
- **Clicar un tipus** → **només omple** la casella «Nom» de l'editor del visor
  (senyal `tipusTriat`); **no aplica** res — ho fa l'usuari amb «Aplica».
- Al peu, la **vista prèvia** i el botó **▶ Escoltar** (plaçaholder per a una
  funció FUTURA amb MIDI; ara **desactivat**, per no deixar un botó mort).
"""
from __future__ import annotations

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QPushButton, QStyle,
                             QStyledItemDelegate, QVBoxLayout, QWidget)

from app import theme, xifrat

# Colors (theme, amb els del mockup aprovat)
C_TIPUS = theme.TEXT
C_ALTS = "#7fd1a0"
C_GRAUS = "#7d8794"
C_SEL = theme.ACTIU
C_TIPUS_SEL = "#ffffff"
C_ALTS_SEL = "#d6f5e3"
C_GRAUS_SEL = "#cfe0ff"

ALT_FILA = 34            # alçada de cada fila (2 línies)


class _DelegatTipus(QStyledItemDelegate):
    """Pinta cada fila en 2 línies: `tipus·alternatius` + els graus."""

    def sizeHint(self, option, index):  # noqa: N802 (API Qt)
        return QSize(0, ALT_FILA)

    def paint(self, painter, option, index):  # noqa: N802 (API Qt)
        dades = index.data(Qt.UserRole) or ("", "", "")
        etiqueta, alts, graus = dades
        sel = bool(option.state & QStyle.State_Selected)
        r = option.rect
        painter.save()
        if sel:
            painter.fillRect(r, QColor(C_SEL))
        # línia 1: el tipus + els alternatius enganxats amb «·»
        f_tipus = QFont("Sans Serif", 10, QFont.Bold)
        painter.setFont(f_tipus)
        painter.setPen(QColor(C_TIPUS_SEL if sel else C_TIPUS))
        painter.drawText(r.adjusted(8, 2, 0, 0), Qt.AlignLeft | Qt.AlignTop,
                         etiqueta)
        if alts:
            ample = painter.fontMetrics().horizontalAdvance(etiqueta)
            painter.setFont(QFont("Sans Serif", 8))
            painter.setPen(QColor(C_ALTS_SEL if sel else C_ALTS))
            painter.drawText(r.adjusted(8 + ample + 1, 4, 0, 0),
                             Qt.AlignLeft | Qt.AlignTop, "·" + alts)
        # línia 2: els graus
        painter.setFont(QFont("Sans Serif", 7))
        painter.setPen(QColor(C_GRAUS_SEL if sel else C_GRAUS))
        painter.drawText(r.adjusted(8, 19, 0, 0), Qt.AlignLeft | Qt.AlignTop,
                         graus)
        painter.restore()


class PanellXifrat(QWidget):
    """El contingut del dock. Emet `tipusTriat` amb el xifrat canònic."""

    tipusTriat = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._qualitat = ""
        self._etiqueta = ""
        capa = QVBoxLayout(self)
        capa.setContentsMargins(8, 8, 8, 8)
        capa.setSpacing(6)

        # ── fila 1: arrel + baix (text lliure) ──────────────────────────────
        fila = QHBoxLayout()
        fila.setSpacing(6)
        fila.addWidget(QLabel("Arrel"))
        self.arrel = QLineEdit()
        self.arrel.setMaximumWidth(64)
        self.arrel.setPlaceholderText("C")
        self.arrel.setToolTip("Arrel de l'acord (text lliure: C, F#, Bb…). "
                              "Pot quedar buit.")
        fila.addWidget(self.arrel)
        fila.addWidget(QLabel("Baix"))
        self.baix = QLineEdit()
        self.baix.setMaximumWidth(64)
        self.baix.setPlaceholderText("—")
        self.baix.setToolTip("Nota del baix per a un acord amb inversió "
                             "(A7/G). Pot quedar buit.")
        fila.addWidget(self.baix)
        fila.addStretch(1)
        capa.addLayout(fila)

        # ── llista de tipus ─────────────────────────────────────────────────
        self.llista = QListWidget()
        self.llista.setItemDelegate(_DelegatTipus(self.llista))
        self.llista.setUniformItemSizes(True)
        self.llista.setToolTip("Clicar un tipus NOMÉS omple la casella «Nom» "
                               "de l'editor.")
        self._omple()
        capa.addWidget(self.llista, stretch=1)

        # ── peu: pista + vista prèvia + botó Escoltar (futur) ───────────────
        capa.addWidget(QLabel("▼ clic → s'escriu a la casella «Nom»"))
        peu = QHBoxLayout()
        peu.setSpacing(6)
        self.previsio = QLineEdit()
        self.previsio.setReadOnly(True)
        self.previsio.setObjectName("previsio_xifrat")
        self.previsio.setToolTip("Com quedarà el nom de l'acord.")
        peu.addWidget(self.previsio, stretch=1)
        self.b_escoltar = QPushButton("▶ Escoltar")
        self.b_escoltar.setObjectName("secundari")
        self.b_escoltar.setEnabled(False)          # futura funció MIDI
        self.b_escoltar.setToolTip("Properament: sentir els graus del xifrat "
                                   "per separat i alhora (MIDI).")
        peu.addWidget(self.b_escoltar)
        capa.addLayout(peu)

        # connexions
        self.arrel.textChanged.connect(self._actualitza_previsio)
        self.baix.textChanged.connect(self._actualitza_previsio)
        self.llista.itemClicked.connect(self._on_clic)
        self.llista.currentItemChanged.connect(
            lambda *_: self._actualitza_previsio())

    # -- API -------------------------------------------------------------------
    def _omple(self):
        """Carrega la llista des de `xifrat.TAULA_TIPUS` (font única)."""
        self.llista.clear()
        for etiqueta, qual, alts, graus in xifrat.TAULA_TIPUS:
            it = QListWidgetItem(etiqueta)
            it.setData(Qt.UserRole, (etiqueta, alts, graus))
            it.setData(Qt.AccessibleTextRole, f"{etiqueta}·{alts} {graus}")
            self.llista.addItem(it)

    def xifrat_actual(self) -> str:
        """El xifrat que s'escriuria ara (arrel + tipus + baix), o ''."""
        return xifrat.composa(self.arrel.text(), self._qualitat,
                              self.baix.text())

    def _actualitza_previsio(self):
        txt = self.xifrat_actual() or self._etiqueta
        self.previsio.setText(txt)

    def _on_clic(self, item):
        etiqueta, _alts, _graus = item.data(Qt.UserRole)
        # la qualitat canònica de la fila
        for e, qual, _a, _g in xifrat.TAULA_TIPUS:
            if e == etiqueta:
                self._qualitat, self._etiqueta = qual, etiqueta
                break
        self._actualitza_previsio()
        # Només EMPLENA (mai aplica): el visor ho posa a la casella «Nom».
        self.tipusTriat.emit(self.xifrat_actual() or etiqueta)
