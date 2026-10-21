#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Guia ràpida d'«Anàlisi guiat» — **només informació**, pas a pas.

Substituïx el flux interactiu (v2 per trams i v3 per ancoratges, tots dos en
*stand by*): el treball real es fa amb **marcadors en viu** (`+`). Esta finestra
no toca el model: només explica, en 5 pantalles, com treballar.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton,
                             QStackedWidget, QVBoxLayout, QWidget)

PASSOS = (
    ("1 · Obri l'àudio",
     "Prem <b>Obre àudio…</b> i tria el tema. L'app el copia dins del seu "
     "projecte (així el pots moure de lloc quan vulgues).<br><br>"
     "El BPM i el compàs de dalt són la <b>referència</b>: si no els saps, "
     "deixa 120 i 4/4 — els marcadors ja ajustaran el mapa."),
    ("2 · Escolta i marca",
     "Prem <b>Espai</b> i, cada vegada que comence un compàs, prem "
     "<b>+</b> (o el botó <b>＋ Marker</b>).<br><br>"
     "El cursor del visor es mou amb la música, així que els marcadors cauen "
     "on tu els sents. Si t'equivoques: <b>Ctrl+Z</b> o "
     "<i>Analitza ▸ Esborra l'últim marcador</i>."),
    ("3 · Què fa un marcador",
     "Cada marcador crea <b>un inici de clip a BPM/compàs</b> i "
     "<b>un inici de clip a estructura</b> en eixe instant.<br><br>"
     "Després ja és <b>independent</b>: si mous o esborres eixos clips, el "
     "marcador es queda on el vas posar (es pinten com a ratlles grogues)."),
    ("4 · Ajusta el mapa",
     "Amb els marcadors posats, toca el <b>BPM</b> i el <b>compàs</b> de dalt, "
     "o arrossega les <b>vores</b> dels blocs de la pista de BPM/compàs "
     "(s'imanten a la línia de compàs).<br><br>"
     "El carril d'estructura també s'edita igual: doble clic per renombrar, "
     "vores per moure, botó dret per a més opcions."),
    ("5 · Acords i exporta",
     "Quan el mapa ja quadra, prem <b>Analitza l'àudio</b> (F5): els acords "
     "s'alineen amb la graella dels marcadors.<br><br>"
     "Després: <b>Exporta WAV's</b> (un fitxer per acord) o <b>Exporta la "
     "partitura</b>. Tot quede al projecte: pots tancar i tornar demà."),
)


class DialegGuiaRapida(QDialog):
    """Welcome de 5 pantalles amb «Anterior» / «Següent» / «Tanca»."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Anàlisi guiat — guia ràpida")
        self.setModal(True)
        self.resize(620, 380)
        v = QVBoxLayout(self)

        self._pila = QStackedWidget()
        for titol, text in PASSOS:
            pag = QWidget()
            pv = QVBoxLayout(pag)
            lb_t = QLabel(titol)
            lb_t.setStyleSheet("font-size: 14pt; font-weight: bold;")
            pv.addWidget(lb_t)
            lb = QLabel(text)
            lb.setWordWrap(True)
            lb.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            lb.setTextFormat(Qt.RichText)
            pv.addWidget(lb, 1)
            self._pila.addWidget(pag)
        v.addWidget(self._pila, 1)

        self._punts = QLabel("")
        self._punts.setAlignment(Qt.AlignCenter)
        self._punts.setStyleSheet("color: #777;")
        v.addWidget(self._punts)

        f = QHBoxLayout()
        self.b_ant = QPushButton("◀ Anterior")
        self.b_ant.clicked.connect(self._anterior)
        f.addWidget(self.b_ant)
        f.addStretch(1)
        self.b_seg = QPushButton("Següent ▶")
        self.b_seg.setDefault(True)
        self.b_seg.clicked.connect(self._seguent)
        f.addWidget(self.b_seg)
        self.b_tanca = QPushButton("Tanca")
        self.b_tanca.clicked.connect(self.accept)
        f.addWidget(self.b_tanca)
        v.addLayout(f)
        self._actualitza()

    # -- navegació --------------------------------------------------------
    def _idx(self):
        return self._pila.currentIndex()

    def _anterior(self):
        if self._idx() > 0:
            self._pila.setCurrentIndex(self._idx() - 1)
            self._actualitza()

    def _seguent(self):
        if self._idx() < self._pila.count() - 1:
            self._pila.setCurrentIndex(self._idx() + 1)
            self._actualitza()
        else:
            self.accept()

    def _actualitza(self):
        i, n = self._idx(), self._pila.count()
        self._punts.setText(" · ".join("●" if j == i else "○"
                                       for j in range(n)))
        self.b_ant.setEnabled(i > 0)
        self.b_seg.setText("Comença" if i == n - 1 else "Següent ▶")
