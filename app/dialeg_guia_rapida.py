#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Guia ràpida d'«Anàlisi guiat» — informació i accions assistides.

Les accions de la barra inferior deleguen al visor: proposen onsets, BPM,
estabilitat i mapa, però no apliquen res sense confirmació. El treball fi
continua fent-se amb els **marcadors en viu** (`+`).
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton,
                             QStackedWidget, QVBoxLayout, QWidget)

PASSOS = (
    ("1 · Obri l'àudio i dona una pista",
     "Prem <b>Fitxer ▸ Obre àudio…</b> i tria la cançó. L'app la copia dins del "
     "projecte (pots moure-la de lloc quan vulgues).<br><br>"
     "A dalt, indica el <b>compàs</b> (per defecte <b>4/4</b>) i dona-li un "
     "<b>BPM orientatiu</b>:<br>"
     "• Si saps el tempo aproximat, escriu-lo a la casella.<br>"
     "• Si no el saps, prem <b>TAP</b> (o la tecla <b>T</b>) 4 vegades "
     "seguint el ritme, o prem <b>🎯 Detecta</b> per a una estimació "
     "ràpida.<br><br>"
     "No cal que siga exacte: només és la referència perquè l'app entenga "
     "les <b>frases musicals</b>."),
    ("2 · Afina el compàs",
     "Selecciona el clip de tempo i ajusta'n el <b>BPM</b>, el <b>compàs</b> "
     "i la <b>unitat de pols</b> a la franja Editor o al diàleg del clip."),
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


from app.finestres import GeometriaMixin
from app.info_box import InfoDialogMixin

class DialegGuiaRapida(InfoDialogMixin, GeometriaMixin, QDialog):
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

        fa = QHBoxLayout()
        self.b_prop_inici = QPushButton("Proposa inici")
        self.b_prop_inici.setToolTip(
            "Proposa els onsets més pròxims al cursor o al marcador d'inici")
        self.b_prop_final = QPushButton("Proposa final")
        self.b_prop_final.setToolTip(
            "Proposa els onsets més pròxims al cursor o al marcador final")
        self.b_prop_inici.clicked.connect(
            lambda: self._proposa("inici_analisi"))
        self.b_prop_final.clicked.connect(
            lambda: self._proposa("final_analisi"))
        self.b_prop_bpm = QPushButton("Proposa BPM")
        self.b_prop_bpm.setToolTip(
            "Proposa candidats de BPM per al rang d'anàlisi; no aplica res")
        self.b_prop_bpm.clicked.connect(self._proposa_bpm)
        self.b_estabilitat = QPushButton("Comprova estabilitat")
        self.b_estabilitat.setToolTip(
            "Ajusta un BPM constant al rang i mostra e(t); no aplica res")
        self.b_estabilitat.clicked.connect(self._comprova_estabilitat)
        self.b_mapa = QPushButton("Proposa mapa")
        self.b_mapa.setToolTip(
            "Proposa un mapa d'un sol BPM; conserva els clips de fora del "
            "rang i no aplica res")
        self.b_mapa.clicked.connect(self._proposa_mapa)
        self.b_aplica_bpm = QPushButton("Aplica BPM")
        self.b_aplica_bpm.setToolTip(
            "Aplica el BPM triat al mapa si només té un clip; demana confirmació")
        self.b_aplica_bpm.clicked.connect(self._aplica_bpm)
        self.b_aplica_mapa = QPushButton("Aplica mapa")
        self.b_aplica_mapa.setToolTip(
            "Aplica la proposta de mapa amb confirmació; conserva els clips "
            "fora del rang")
        self.b_aplica_mapa.clicked.connect(self._aplica_mapa)
        fa.addWidget(self.b_prop_inici)
        fa.addWidget(self.b_prop_final)
        fa.addWidget(self.b_prop_bpm)
        fa.addWidget(self.b_estabilitat)
        fa.addWidget(self.b_mapa)
        fa.addWidget(self.b_aplica_bpm)
        fa.addWidget(self.b_aplica_mapa)
        fa.addStretch(1)
        self.lb_guia = QLabel("")
        self.lb_guia.setObjectName("secundari")
        fa.addWidget(self.lb_guia)
        v.addLayout(fa)

        f = QHBoxLayout()
        self.b_ant = QPushButton("◀ Anterior")
        self.b_ant.setToolTip("Pantalla anterior de la guia")
        self.b_ant.clicked.connect(self._anterior)
        f.addWidget(self.b_ant)
        f.addStretch(1)
        self.b_seg = QPushButton("Següent ▶")
        self.b_seg.setToolTip("Pantalla seguent de la guia")
        self.b_seg.setDefault(True)
        self.b_seg.clicked.connect(self._seguent)
        f.addWidget(self.b_seg)
        self.b_tanca = QPushButton("Tanca")
        self.b_tanca.setToolTip("Tanca la guia rapiada")
        self.b_tanca.clicked.connect(self.accept)
        f.addWidget(self.b_tanca)
        v.addLayout(f)
        self._actualitza()

    def _proposa(self, tipus):
        pare = self.parent()
        if pare is not None and hasattr(pare, "_proposa_onsets_guia"):
            pare._proposa_onsets_guia(tipus)

    def _proposa_bpm(self):
        pare = self.parent()
        if pare is not None and hasattr(pare, "_proposa_bpm_guia"):
            text = pare._proposa_bpm_guia()
            if text:
                self.lb_guia.setText(text)

    def _comprova_estabilitat(self):
        pare = self.parent()
        if pare is not None and hasattr(pare, "_diagnostica_estabilitat_guia"):
            text = pare._diagnostica_estabilitat_guia()
            if text:
                self.lb_guia.setText(text)

    def _proposa_mapa(self):
        pare = self.parent()
        if pare is not None and hasattr(pare, "_proposa_mapa_guia"):
            text = pare._proposa_mapa_guia()
            if text:
                self.lb_guia.setText(text)

    def _aplica_bpm(self):
        pare = self.parent()
        if pare is not None and hasattr(pare, "_aplica_bpm_guia"):
            pare._aplica_bpm_guia()

    def _aplica_mapa(self):
        pare = self.parent()
        if pare is not None and hasattr(pare, "_aplica_mapa_guia"):
            pare._aplica_mapa_guia()

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
