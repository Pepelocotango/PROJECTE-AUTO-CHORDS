"""Canvi explícit d'unitat de pols (clip)."""
from PyQt5.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QLabel, QRadioButton, QVBoxLayout,
)

from app import bpm_unit, limits
from app.finestres import GeometriaMixin
from app.info_box import InfoDialogMixin


class PanellCanviUnitat:
    """Contingut reutilitzable: radios + previsualització de conseqüències."""

    def __init__(self, parent=None):
        self.etiqueta = QLabel("")
        self._lbl_nova = QLabel("Unitat nova:")
        self.cb_unitat = QComboBox()
        for clau, etiqueta in bpm_unit.opcions():
            self.cb_unitat.addItem(etiqueta, clau)
        self.cb_unitat.setToolTip(
            "Unitat de pols que s'aplicarà en acceptar.")
        self.rb_tempo = QRadioButton("Mantén el tempo (canvia el número)")
        self.rb_tempo.setToolTip("Conserva el BPM intern; el numero de compassos es recalcula.")
        self.rb_numero = QRadioButton("Mantén el número (canvia el tempo)")
        self.rb_numero.setToolTip("Conserva el numero de compassos; el BPM intern es recalcula.")
        self.previsio = QLabel("")
        self.previsio.setWordWrap(True)
        self._bpm = 120.0
        self._u0 = bpm_unit.DEFECTE
        self._u1 = bpm_unit.DEFECTE
        self.rb_tempo.setChecked(True)
        self.rb_tempo.toggled.connect(self._actualitza)
        self.cb_unitat.currentIndexChanged.connect(self._actualitza)
        self._widgets = [self.etiqueta, self._lbl_nova, self.cb_unitat,
                         self.rb_tempo, self.rb_numero, self.previsio]

    def set_dades(self, etiqueta, bpm_quarter, unit_vella, unit_nova):
        self._bpm = float(bpm_quarter)
        self._u0 = bpm_unit.normalitza(unit_vella)
        self._u1 = bpm_unit.normalitza(unit_nova)
        idx = self.cb_unitat.findData(self._u1)
        if idx >= 0:
            self.cb_unitat.blockSignals(True)
            self.cb_unitat.setCurrentIndex(idx)
            self.cb_unitat.blockSignals(False)
        self._actualitza()

    def mode(self):
        return "mantenir_tempo" if self.rb_tempo.isChecked() else \
            "mantenir_numero"

    def unitat(self):
        """Unitat nova seleccionada al desplegable."""
        return bpm_unit.normalitza(
            self.cb_unitat.currentData() or self._u1)

    def resultat(self):
        u1 = self.unitat()
        self._u1 = u1
        if self.mode() == "mantenir_tempo":
            bpm = float(self._bpm)
        else:
            visible = bpm_unit.de_quarter(self._bpm, self._u0)
            bpm = bpm_unit.a_quarter(visible, u1)
        self.etiqueta.setText(
            f"{bpm_unit.etiqueta(self._u0)} → "
            f"{bpm_unit.etiqueta(u1)}")
        return float(bpm), u1

    def es_valid(self):
        bpm, _u = self.resultat()
        return limits.BPM_MIN <= bpm <= limits.BPM_MAX

    def _actualitza(self):
        if not hasattr(self, "previsio"):
            return
        bpm, u1 = self.resultat()
        vella = bpm_unit.de_quarter(self._bpm, self._u0)
        nova = bpm_unit.de_quarter(bpm, u1)
        if self.mode() == "mantenir_tempo":
            text = (f"El so no canvia; el número passa de {vella:g} "
                    f"{bpm_unit.etiqueta(self._u0).lower()} a {nova:g} "
                    f"{bpm_unit.etiqueta(u1).lower()}.")
        else:
            ratio = bpm / self._bpm if self._bpm else 1.0
            text = (f"El número no canvia; la cançó passa de {self._bpm:g} "
                    f"a {bpm:g} negres/min ({ratio:.2f}×).")
        if not self.es_valid():
            text += (f" Fora del rang intern {limits.BPM_MIN:g}–"
                     f"{limits.BPM_MAX:g}.")
        self.previsio.setText(text)


class DialegCanviUnitat(InfoDialogMixin, GeometriaMixin, QDialog):
    """Modal petit per aplicar el canvi d'unitat amb Cancel·la."""

    def __init__(self, parent=None, etiqueta="Clip", bpm=120.0,
                 unit_vella=bpm_unit.DEFECTE, unit_nova=bpm_unit.DEFECTE):
        super().__init__(parent)
        self.setWindowTitle("Canvi d'unitat de pols")
        self.panell = PanellCanviUnitat(self)
        lay = QVBoxLayout(self)
        for w in self.panell._widgets:
            lay.addWidget(w)
        self.botons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.botons.button(QDialogButtonBox.Ok).setToolTip("Aplica el canvi d'unitat")
        self.botons.button(QDialogButtonBox.Cancel).setToolTip("Cancel·la sense aplicar")
        self.botons.accepted.connect(self.accept)
        self.botons.rejected.connect(self.reject)
        lay.addWidget(self.botons)
        self.panell.set_dades(etiqueta, bpm, unit_vella, unit_nova)
        self.panell.rb_tempo.toggled.connect(self._actualitza_ok)
        self.panell.rb_numero.toggled.connect(self._actualitza_ok)
        self.panell.cb_unitat.currentIndexChanged.connect(
            self._actualitza_ok)
        self._actualitza_ok()

    def _actualitza_ok(self, *_a):
        self.botons.button(QDialogButtonBox.Ok).setEnabled(
            self.panell.es_valid())

    def resultat(self):
        return self.panell.resultat() + (self.panell.mode(),)
