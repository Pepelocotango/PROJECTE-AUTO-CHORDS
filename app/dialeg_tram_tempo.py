"""Diàleg per editar un tram de tempo/compàs."""
from PyQt5.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel,
    QMessageBox, QSpinBox, QVBoxLayout,
)

from app.camp_text import CampText
from app import bpm_unit, limits, tempo_map

class DialegTramTempo(QDialog):
    """Edita un **tros** del mapa: BPM i compàs (on comença es mostra)."""

    def __init__(self, parent=None, inici=0.0, bpm=120.0, num=4, den=4,
                 inicial=False, text_inici=None, unit=bpm_unit.DEFECTE,
                 n_actual=None, durada=None):
        super().__init__(parent)
        self._unit = bpm_unit.normalitza(unit)
        self._durada = float(durada) if durada is not None else 0.0
        self._n_actual = n_actual
        self.setWindowTitle("BPM, compàs i compassos")
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
        self.ed_compas = CampText(f"{int(num)}/{int(den)}")
        self.ed_compas.setPlaceholderText("4/4, 3/4, 2/4, 1/4…")
        self.sp_n = QSpinBox()
        self.sp_n.setRange(1, 9999)
        self.sp_n.setValue(
            max(1, int(round(n_actual))) if n_actual is not None else 1)
        self.sp_n.setToolTip(
            "Nombre de compassos del clip. Amb «N mana», el BPM es recalcula "
            "perquè N compassos hi caben sense moure les fronteres.")
        self.chk_n = QCheckBox("N mana: el BPM es recalcula")
        self.chk_n.setToolTip(
            "Les fronteres en segons no es mouen. El BPM es calcula com "
            "N · (num·4/den) · 60 / durada.")
        _te_n = (n_actual is not None and self._durada > 0)
        self.chk_n.setChecked(_te_n)
        self.chk_n.setEnabled(_te_n)
        self.sp_n.setEnabled(_te_n)
        self.chk_n.toggled.connect(self._n_canviat)
        self.sp_n.valueChanged.connect(self._actualitza_bpm_n)
        self.ed_compas.textChanged.connect(self._actualitza_bpm_n)
        form.addRow("N compassos:", self.sp_n)
        form.addRow("Compàs:", self.ed_compas)
        form.addRow(f"BPM ({bpm_unit.etiqueta(self._unit).lower()}):",
                    self.sp_bpm)
        form.addRow("", self.chk_n)
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
        self.sp_n.setEnabled(not bool(actiu) and self.chk_n.isEnabled())
        self.chk_n.setEnabled(not bool(actiu) and self._durada > 0)
        if actiu:
            self.chk_n.setChecked(False)
        self._n_canviat(self.chk_n.isChecked() and not bool(actiu))

    def n_auto(self):
        """Cert si l'usuari vol que N mane i el BPM es recalcule."""
        return bool(self.chk_n.isChecked() and self.chk_n.isEnabled())

    def _parse_compas(self):
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
        return num, den

    def _actualitza_bpm_n(self, *_a):
        if not self.n_auto() or self._durada <= 0:
            return
        try:
            num, den = self._parse_compas()
            bq = float(num) * 4.0 / float(den)
            bpm = float(self.sp_n.value()) * bq * 60.0 / self._durada
            bpm = tempo_map.valida_tempo(bpm, num, den)[0]
        except (ValueError, ZeroDivisionError):
            return
        self.sp_bpm.blockSignals(True)
        try:
            self.sp_bpm.setValue(bpm_unit.de_quarter(bpm, self._unit))
        finally:
            self.sp_bpm.blockSignals(False)

    def _n_canviat(self, actiu):
        actiu = bool(actiu) and self._durada > 0
        self.sp_n.setEnabled(actiu)
        self.sp_bpm.setEnabled(not actiu)
        if actiu:
            self._actualitza_bpm_n()

    def valors(self):
        """`(bpm, num, den)`; «num/den» o «num»."""
        if self.chk_segons.isChecked():
            raise ValueError(
                "El rubato es crea amb «Marca com a rubato» o «Converteix a "
                "rubato»; no des del diàleg de tram.")
        num, den = self._parse_compas()
        if self.n_auto():
            bpm = (float(self.sp_n.value())
                   * (float(num) * 4.0 / float(den)) * 60.0 / self._durada)
            return tempo_map.valida_tempo(bpm, num, den)
        return tempo_map.valida_tempo(
            bpm_unit.a_quarter(float(self.sp_bpm.value()), self._unit),
            num, den)

    def valors_n(self):
        """`(bpm, num, den, n)` amb el BPM ja calculat si N mana."""
        bpm, num, den = self.valors()
        return bpm, num, den, int(self.sp_n.value())
