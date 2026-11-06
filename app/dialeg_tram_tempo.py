"""Diàleg per editar un tram de tempo/compàs."""
from PyQt5.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel,
    QLineEdit, QMessageBox, QVBoxLayout,
)

from app import bpm_unit, limits, tempo_map

class DialegTramTempo(QDialog):
    """Edita un **tros** del mapa: BPM i compàs (on comença es mostra)."""

    def __init__(self, parent=None, inici=0.0, bpm=120.0, num=4, den=4,
                 inicial=False, text_inici=None, unit=bpm_unit.DEFECTE):
        super().__init__(parent)
        self._unit = bpm_unit.normalitza(unit)
        self.setWindowTitle("BPM i compàs")
        self.setMinimumWidth(330)
        lay = QVBoxLayout(self)
        if inicial:
            cap = "Valor inicial (compàs 1)."
        else:
            cap = f"Comença a {float(inici):.3f} s"
            if text_inici:
                cap += f" (compàs {text_inici})"
        avis = QLabel(cap)
        avis.setWordWrap(True)
        lay.addWidget(avis)
        form = QFormLayout()
        self.sp_bpm = QDoubleSpinBox()
        _factor = bpm_unit.factor(self._unit)
        self.sp_bpm.setRange(limits.BPM_MIN / _factor,
                             limits.BPM_MAX / _factor)
        self.sp_bpm.setDecimals(3)
        self.sp_bpm.setValue(bpm_unit.de_quarter(bpm, self._unit))
        self._den_defecte = int(den) if int(den) > 0 else 4
        self.ed_compas = QLineEdit(f"{int(num)}/{int(den)}")
        self.ed_compas.setPlaceholderText("4/4, 3/4, 2/4, 1/4…")
        form.addRow(f"BPM ({bpm_unit.etiqueta(self._unit).lower()}):",
                    self.sp_bpm)
        form.addRow("Compàs:", self.ed_compas)
        lay.addLayout(form)
        self.chk_segons = QCheckBox("En segons (sense compàs: rubato)")
        self.chk_segons.setToolTip(
            "El clip dura el que diu l'àudio, sense graella ni compassos "
            "enters. Per a la partitura es pren a 100 BPM.")
        self.chk_segons.setChecked(int(num) <= 0 or int(den) <= 0)
        self.chk_segons.toggled.connect(self._segons_canviat)
        lay.addWidget(self.chk_segons)
        self._segons_canviat(self.chk_segons.isChecked())
        botons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botons.accepted.connect(self.accept)
        botons.rejected.connect(self.reject)
        lay.addWidget(botons)

    def accept(self):
        try:
            self.valors()
        except ValueError as e:
            QMessageBox.warning(self, "Tempo invàlid", str(e))
            return
        super().accept()

    def _segons_canviat(self, actiu):
        """En segons el compàs no té sentit: s'apaga l'edició del camp."""
        self.ed_compas.setEnabled(not bool(actiu))

    def valors(self):
        """`(bpm, num, den)`; «num/den» o «num»."""
        if self.chk_segons.isChecked():
            raise ValueError(
                "El rubato es crea amb «Marca com a rubato» o «Converteix a "
                "rubato»; no des del diàleg de tram.")
        num, den = 4, self._den_defecte
        txt = (self.ed_compas.text() or "").strip().replace(" ", "")
        if "/" in txt:
            try:
                a, b = txt.split("/", 1)
                num, den = int(a), int(b)
            except ValueError as e:
                raise ValueError(f"El compàs «{txt}» no és vàlid") from e
        elif txt.isdigit():
            num = int(txt)
        else:
            raise ValueError(f"El compàs «{txt}» no és vàlid")
        return tempo_map.valida_tempo(
            bpm_unit.a_quarter(float(self.sp_bpm.value()), self._unit),
            num, den)
