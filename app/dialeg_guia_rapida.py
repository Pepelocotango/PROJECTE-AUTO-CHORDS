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
    ("1 · Obri l'àudio i dona una pista",
     "Prem <b>Obre àudio…</b> i tria la cançó. L'app la copia dins del "
     "projecte (pots moure-la de lloc quan vulgues).<br><br>"
     "A dalt, indica el <b>compàs</b> (per defecte <b>4/4</b>) i dona-li un "
     "<b>BPM orientatiu</b>:<br>"
     "• Si saps el tempo aproximat, escriu-lo a la casella.<br>"
     "• Si no el saps, prem <b>TAP</b> (o la tecla <b>T</b>) 4 vegades "
     "seguint el ritme, o prem <b>🎯 Detecta</b> per a una estimació "
     "ràpida.<br><br>"
     "No cal que siga exacte: només és la referència perquè l'app entenga "
     "les <b>frases musicals</b>."),
    ("2 · Marca el compàs 1",
     "Moltes cançons tenen uns segons de silenci o una anacrusi al "
     "principi.<br><br>"
     "1. Posa el cursor vermell just al <b>primer cop fort</b> on comença el "
     "ritme de la cançó.<br>"
     "2. Prem el botó <b>📍</b> (<i>Compàs 1 al cursor</i>)."),
    ("3 · Escolta i marca les parts",
     "Prem <b>Espai</b> per escoltar. Cada vegada que comence una "
     "<b>secció nova</b> o una <b>frase musical</b> (cada 4, 8 o 16 "
     "compassos), prem <b>+</b> (o el botó <b>＋ Marker</b>).<br><br>"
     "<b>No cal marcar cada compàs!</b> L'app calcula quants compassos "
     "enters hi ha en cada tram i en dedueix el <b>BPM exacte</b> perquè la "
     "graella quede perfectament clavada.<br><br>"
     "Si t'equivoques prement <b>+</b>, desfés de seguida amb "
     "<b>Ctrl+Z</b>."),
    ("4 · Ajusta els talls a l'ona",
     "Si un marcador no ha caigut exactament damunt del cop de "
     "bateria:<br><br>"
     "1. Fes <b>zoom</b> amb la roda del ratolí per veure bé l'ona.<br>"
     "2. <b>Arrossega la vora</b> del tram fins al pic exacte del "
     "so.<br><br>"
     "El marcador es mou amb la vora i el <b>BPM es recalcula sol</b>: tu "
     "manes damunt de l'ona, l'app fa els números."),
    ("5 · Revisa i analitza els acords",
     "Si en algun tram l'app ha deduït 8 compassos però eren 9 (o al "
     "revés):<br>"
     "• Fes <b>clic dret</b> sobre el tram de tempo i tria <b>Afegir 1 "
     "compàs (+1)</b>, <b>Restar 1 compàs (−1)</b> o <b>Doblar / Dividir "
     "compassos (×2 / ÷2)</b>.<br>"
     "Els <b>segons queden quiets</b> i el BPM s'ajusta a l'acte.<br><br>"
     "Quan el mapa de tempo quadre amb la música:<br>"
     "• Prem <b>Analitza l'àudio</b> (<b>F5</b>): al diàleg pots desactivar "
     "<b>BPM</b> i <b>Estructura</b> si només vols els acords de "
     "Chordino.<br>"
     "• Prem <b>Exporta WAV's</b> per generar els clips llestos per al teu "
     "DAW."),
)


class DialegGuiaRapida(QDialog):
    """Welcome de 5 pantalles amb «Anterior» / «Següent» / «Tanca»."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Anàlisi guiat — guia ràpida")
        self.setModal(True)
        self.resize(680, 470)
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
