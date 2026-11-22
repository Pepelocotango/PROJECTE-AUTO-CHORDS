"""Diàleg per editar un tram de tempo/compàs."""
from PyQt5.QtCore import QEvent, Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QSpinBox, QVBoxLayout, QWidget,
)

from app.camp_text import CampText
from app import bpm_unit, limits, tempo_map, theme

from app.finestres import GeometriaMixin
from app.info_box import InfoDialogMixin


class DialegTramTempo(InfoDialogMixin, GeometriaMixin, QDialog):
    """Edita un **tros** del mapa: BPM i compàs (on comença es mostra)."""

    #: «Recalcula»: mode «fix» o «mobil», amb les opcions del bloc Opcions.
    recalculRequested = pyqtSignal(str)
    def __init__(self, parent=None, inici=0.0, bpm=120.0, num=4, den=4,
                 inicial=False, text_inici=None, unit=bpm_unit.DEFECTE,
                 n_actual=None, durada=None, info=None,
                 beat_unit=bpm_unit.DEFECTE):
        super().__init__(parent)
        self._unit = bpm_unit.normalitza(unit)
        self._durada = float(durada) if durada is not None else 0.0
        self._n_actual = n_actual
        self._info = dict(info or {})
        self._ini0 = float(inici)
        self._bpm0 = float(bpm)
        self._num0 = int(num)
        self._den0 = int(den)
        self._inicial = bool(inicial)
        self._beat_unit = bpm_unit.normalitza(beat_unit)
        self._unit_inicial = self._unit
        self._bpm_manual = False
        info_dict = dict(info or {})
        self._agr0 = str(info_dict.get("agrupacio")
                         or info_dict.get("agrupacio_ef") or "")
        self.setWindowTitle("Tram de tempo")
        self.setMinimumWidth(1000)
        # Indicador de les caselles visible sobre fons fosc (quadre buit /
        # quadre ple), perquè es vega clar on s'activa cada opció.
        self.setStyleSheet(f"""
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {theme.BORDER_SOFT};
    border-radius: 3px;
    background: {theme.SURFACE};
}}
QCheckBox::indicator:checked {{
    background: {theme.BLAU_INFO};
    border: 1px solid {theme.BLAU_INFO};
}}
QCheckBox::indicator:disabled {{
    background: {theme.BG_2};
    border: 1px solid {theme.BORDER};
}}
""")
        lay = QVBoxLayout(self)
        cols = QHBoxLayout()
        lay.addLayout(cols)
        col_ed = QVBoxLayout()
        col_info = QVBoxLayout()
        cols.addLayout(col_ed, 0)
        cols.addLayout(col_info, 1)

        if inicial:
            cap = "Valor inicial (compàs 1)."
        else:
            cap = f"Comença a {float(inici):.3f} s"
            if text_inici:
                cap += f" (compàs {text_inici})"
        avis = QLabel(cap)
        avis.setWordWrap(True)
        col_ed.addWidget(avis)

        self._den_defecte = int(den) if int(den) > 0 else 4
        grup_fix = QGroupBox("Recalcul fix")
        lay_fix = QVBoxLayout(grup_fix)
        form_fix = QFormLayout()
        (self.sp_n, self.ed_compas,
         self.sp_bpm) = self._crea_camps(form_fix)
        lay_fix.addLayout(form_fix)
        self.chk_n = QCheckBox("N mana (el BPM es recalcula)")
        self.chk_n.setChecked(False)
        self.chk_n.setEnabled(n_actual is not None and self._durada > 0)
        self.chk_n.setToolTip(
            "Si està activat, es respecten els compassos del camp N i el "
            "BPM es recalcula per encaixar-hi. Si està desactivat, el BPM "
            "és l'objectiu i el motor tria el N enter més pròxim.")
        lay_fix.addWidget(self.chk_n)
        self.b_recalc_fix = QPushButton("Recalcula")
        self.b_recalc_fix.setToolTip(
            "Recalcul fix: manté l'inici i la fi del clip i deriva el BPM.")
        self.b_recalc_fix.clicked.connect(lambda: self._recalcula("fix"))
        lay_fix.addWidget(self.b_recalc_fix)
        self.ajuda = QLabel(
            "Prem «Recalcula» per aplicar el recalcul fix. El recalcul mòbil "
            "es fa des de la franja Editor o arrossegant les fronteres.")
        self.ajuda.setWordWrap(True)
        self.ajuda.setObjectName("secundari")
        lay_fix.addWidget(self.ajuda)
        col_ed.addWidget(grup_fix)
        col_ed.addStretch(1)

        self.chk_n.toggled.connect(self._n_canviat)
        self.sp_n.valueChanged.connect(self._actualitza_bpm_n)
        self.ed_compas.textChanged.connect(self._actualitza_bpm_n)
        self._n_canviat(self.chk_n.isChecked())

        # --- columna dreta: informació completa, NOMÉS lectura.
        grup_info = QGroupBox("Informació del clip (no editable)")
        self.info_clip = grup_info
        _li = QVBoxLayout(grup_info)
        _host = QWidget()
        self._info_grid = QGridLayout(_host)
        self._info_grid.setVerticalSpacing(1)
        self._info_grid.setHorizontalSpacing(8)
        self._info_grid.setContentsMargins(10, 8, 10, 8)
        _li.addWidget(_host)
        _li.addStretch(1)
        self._omple_info(self._valors_info())
        col_info.addWidget(grup_info)
        col_info.addStretch(1)

        botons = QDialogButtonBox(QDialogButtonBox.Close)
        botons.button(QDialogButtonBox.Close).setText("Tanca")
        botons.button(QDialogButtonBox.Close).setToolTip(
            "Tanca el diàleg. Els canvis del recalcul ja s'han aplicat.")
        botons.rejected.connect(self.reject)
        lay.addWidget(botons)
        self.installEventFilter(self)
        for w in self.findChildren(QWidget):
            w.installEventFilter(self)

    def eventFilter(self, obj, ev):
        """Passa a la fila «Ajuda» el tooltip del giny sota el ratolí."""
        if ev.type() in (QEvent.Enter, QEvent.HoverEnter, QEvent.ToolTip):
            w = obj if isinstance(obj, QWidget) else None
            while w is not None and not w.toolTip():
                w = w.parentWidget()
            if w is not None and w.toolTip():
                tip = w.toolTip()
                if hasattr(self, "ajuda") and self.ajuda.text() != tip:
                    self.ajuda.setText(tip)
        return super().eventFilter(obj, ev)

    def _crea_camps(self, form):
        """Crea el joc N/compàs/BPM del recalcul fix."""
        sp_bpm = QDoubleSpinBox()
        _factor = bpm_unit.factor(self._unit)
        sp_bpm.setRange(limits.BPM_MIN / _factor,
                        limits.BPM_MAX / _factor)
        sp_bpm.setDecimals(3)
        sp_bpm.setValue(bpm_unit.de_quarter(self._bpm0, self._unit))
        sp_bpm.setToolTip(
            "BPM del clip en la unitat activa. El recalc fix el deriva de "
            "l'N, el compàs i la durada.")
        ed_compas = CampText(f"{self._num0}/{self._den0}")
        ed_compas.setPlaceholderText("4/4, 3/4, 2/4, 1/4…")
        ed_compas.setToolTip(
            "Compàs del clip en format num/den (numerador 1–12; "
            "denominador 2, 4, 8 o 16).")
        sp_n = QSpinBox()
        sp_n.setRange(1, 9999)
        sp_n.setValue(
            max(1, int(round(self._n_actual)))
            if self._n_actual is not None else 1)
        sp_n.setToolTip(
            "Nombre de compassos del clip. Amb «N mana», el BPM es recalcula "
            "perquè N compassos hi caben sense moure les fronteres.")
        sp_n.setEnabled(self._n_actual is not None and self._durada > 0)
        form.addRow("N compassos:", sp_n)
        form.addRow("Compàs:", ed_compas)
        form.addRow(f"BPM ({bpm_unit.etiqueta(self._unit).lower()}):", sp_bpm)
        for w in (sp_n, ed_compas, sp_bpm):
            lbl = form.labelForField(w)
            if lbl is not None:
                lbl.setToolTip(w.toolTip())
        return sp_n, ed_compas, sp_bpm

    def _info_per_defecte(self):
        """Informació mínima si el diàleg s'ha construït sense `info`."""
        bpm = self._bpm0
        num, den = self._num0, self._den0
        durada = self._durada
        bq = (num * 4.0 / den) if num > 0 and den > 0 else 0.0
        dur_compas = (bq * 60.0 / bpm) if bq > 0 and bpm > 0 else 0.0
        n_real = (durada / dur_compas) if dur_compas > 0 else self._n_actual
        n_enter = None
        if n_real is not None:
            n_enter = max(1, tempo_map._enter_mes_proper(float(n_real)))
        agr_ef = ""
        if num > 0 and den > 0:
            agr_ef = tempo_map.agrupacio_a_text(
                tempo_map.agrupacio_compas(num, den))
        vei_bpm = None
        ref_num, ref_den = 0, 0
        desviacio = None
        sospita = False
        return {
            "idx": 1, "total": 1,
            "rol": "unic" if self._inicial else "clip",
            "tipus": "normal",
            "ini": self._ini0, "fi": self._ini0 + durada,
            "durada": durada, "ini_cb": "—", "fi_cb": "—",
            "compassos": f"{num}/{den}" if num > 0 and den > 0 else "—",
            "bar_quarters": bq, "durada_compas": dur_compas,
            "agrupacio": "", "agrupacio_ef": agr_ef,
            "n": self._n_actual, "n_real": n_real, "n_enter": n_enter,
            "n_valid": (n_real is not None and n_enter is not None
                        and abs(float(n_real) - float(n_enter)) <= 1e-6),
            "bpm": bpm,
            "bpm_mostra": bpm_unit.de_quarter(bpm, self._unit),
            "bpm_unit": bpm_unit.etiqueta(self._unit),
            "vei_bpm": vei_bpm,
            "vei_compas": "—" if vei_bpm is None else f"{ref_num}/{ref_den}",
            "desviacio": desviacio, "sospita_octava": sospita,
            "beat_unit": bpm_unit.etiqueta(bpm_unit.DEFECTE),
            "snap": "—", "n_qm": None, "negres_qm": None,
            "primer_beat": None, "ultim_beat": None,
            "beats_frontera": [],
            "extrem_ini": ("fix (inici de la WAV)" if self._inicial
                           else "lliure"),
            "extrem_fi": "lliure",
            "vei_esq": None, "vei_dret": None,
            "bpm_ok": limits.BPM_MIN <= bpm <= limits.BPM_MAX,
            "durada_ok": durada >= limits.TEMPS_MIN_CLIP,
            "min_durada": limits.TEMPS_MIN_CLIP,
        }

    def _valors_info(self):
        """Files de la columna d'informació: `("H", títol)` o 4 cel·les."""
        info = self._info_per_defecte()
        info.update(self._info)

        def num_txt(v, dec=3, buit="—"):
            if v is None:
                return buit
            try:
                return f"{float(v):.{int(dec)}f}"
            except (TypeError, ValueError):
                return buit

        def si_no(v):
            return "sí" if v else "no"

        def vei(v):
            if not v:
                return "—"
            return (f"clip {v.get('idx')} · {num_txt(v.get('bpm'), 3)} BPM ·"
                    f" {v.get('compassos')} · N {num_txt(v.get('n'), 3)}")

        idx = int(info.get("idx") or 1)
        total = int(info.get("total") or 1)
        durada = float(info.get("durada") or 0.0)
        n_real = info.get("n_real")
        n_enter = info.get("n_enter")
        n_desat = info.get("n")
        n_valid = bool(info.get("n_valid"))
        bq = float(info.get("bar_quarters") or 0.0)
        dur_compas = float(info.get("durada_compas") or 0.0)
        unit = str(info.get("bpm_unit") or "")
        agr = str(info.get("agrupacio") or "")
        agr_ef = str(info.get("agrupacio_ef") or "")
        desv = info.get("desviacio")
        desv_txt = "—" if desv is None else f"{float(desv):+.1f}%"
        n_qm = info.get("n_qm")
        negres = info.get("negres_qm")
        primer = info.get("primer_beat")
        ultim = info.get("ultim_beat")
        frontera = list(info.get("beats_frontera") or ())

        files = [
            ("H", f"Clip {idx} de {total} · {info.get('rol')} ·"
                  f" {info.get('tipus')}"),
            ("H", "ÀUDIO"),
            ("Inici", f"{num_txt(info.get('ini'), 3)} s"
                      f" ({info.get('ini_cb') or '—'})",
             "Fi", f"{num_txt(info.get('fi'), 3)} s"
                   f" ({info.get('fi_cb') or '—'})"),
            ("Durada", f"{num_txt(durada, 3)} s",
             "Extrems", f"inici {info.get('extrem_ini')} ·"
                        f" fi {info.get('extrem_fi')}"),
            ("H", "MÈTRICA"),
            ("Compàs", f"{info.get('compassos')} ·"
                       f" {num_txt(dur_compas, 3)} s/compàs"
                       f" ({bq:g} negres)",
             "Agrupació", f"{agr or 'automàtica'}"
                           f" ({agr_ef or '—'})"),
            ("N", f"{num_txt(n_real, 3)} → {n_enter}"
                  f" ({'vàlid' if n_valid else 'NO VÀLID'})",
             "Camp desat", num_txt(n_desat, 3)),
            ("BPM", f"{num_txt(info.get('bpm_mostra'), 3)} {unit.lower()}",
             "Intern", f"{num_txt(info.get('bpm'), 3)} negres/min"),
            ("H", "CONTEXT"),
            ("Octava", "sospita (×2/÷2)" if info.get("sospita_octava")
                       else "sense sospita",
             "Unitats", f"BPM {unit} · beat {info.get('beat_unit')}"),
            ("Snap", info.get("snap"),
             "Beats QM", ("cap (sense anàlisi)" if n_qm is None
                          else f"{n_qm} dins · {num_txt(negres, 1)} negres")),
        ]
        if idx > 1 and info.get("vei_bpm") is not None:
            files.append(("Veí esquerre", f"{num_txt(info.get('vei_bpm'), 3)} "
                          f"BPM · {info.get('vei_compas')} · {desv_txt}",
                          None, None))
        if n_qm is not None:
            files.append(("Primer beat", f"{num_txt(primer, 3)} s",
                          "Últim beat", f"{num_txt(ultim, 3)} s"))
        if frontera:
            files.append((
                "Ambigus", ", ".join(f"{float(t):.3f}" for t in frontera)
                + " s (frontera ±50 ms)", None, None))
        files += [
            ("H", "VEÏNS"),
            ("Esquerre", vei(info.get("vei_esq")),
             "Dret", vei(info.get("vei_dret"))),
            ("H", "VALIDACIÓ"),
            ("BPM 30–350", "OK" if info.get("bpm_ok") else "FORA DE RANG",
             "Durada mín.", f"{'OK' if info.get('durada_ok') else 'MASSA CURT'}"
                            f" ({num_txt(durada, 3)} ≥"
                            f" {num_txt(info.get('min_durada'), 3)} s)"),
            ("N enter", "OK" if n_valid else "NO", None, None),
        ]
        return files

    def _omple_info(self, files):
        """Pinta les files d'informació en una graella compacta, sense scroll."""
        f_titol = QFont(self.font())
        f_titol.setPointSize(8)
        f_titol.setBold(True)
        f_text = QFont(self.font())
        f_text.setPointSize(8)
        fila = 0
        for item in files:
            if item[0] == "H":
                lbl = QLabel(item[1])
                lbl.setFont(f_titol)
                self._info_grid.addWidget(lbl, fila, 0, 1, 4)
                fila += 1
                continue
            et1, val1, et2, val2 = item
            l1 = QLabel(f"{et1}:")
            l1.setFont(f_text)
            l1.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            v1 = QLabel(str(val1))
            v1.setFont(f_text)
            v1.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self._info_grid.addWidget(l1, fila, 0)
            self._info_grid.addWidget(v1, fila, 1)
            if et2:
                l2 = QLabel(f"{et2}:")
                l2.setFont(f_text)
                l2.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                v2 = QLabel(str(val2))
                v2.setFont(f_text)
                v2.setTextInteractionFlags(Qt.TextSelectableByMouse)
                self._info_grid.addWidget(l2, fila, 2)
                self._info_grid.addWidget(v2, fila, 3)
            fila += 1

    def valors_camps(self):
        """`(bpm, num, den, n)` tal com estan als camps, sense derivar res."""
        num, den = self._parse_compas()
        bpm = bpm_unit.a_quarter(float(self.sp_bpm.value()), self._unit)
        return bpm, int(num), int(den), int(self.sp_n.value())

    def opcions_recalc(self):
        """Opcions fixes del recalcul: només canvia si mana N."""
        return {
            # L'Editor ja no fa servir QM; els Talls QM tenen el seu propi flux.
            "beats": False,
            "segons": True,
            "unitat": True,
            "compas": False,
            "n_fix": self.n_auto(),
            "rubato": False,
        }

    def _recalcula(self, mode):
        """Valida els camps i demana el recalcul fix."""
        try:
            bpm, num, den, _n = self.valors_camps()
            tempo_map.valida_tempo(bpm, num, den)
        except ValueError as e:
            QMessageBox.warning(self, "Tempo invàlid", str(e))
            return
        self.recalculRequested.emit(str(mode))

    def unitat(self):
        """Unitat de pols que s'aplicarà amb Aplicar/OK."""
        return self._beat_unit

    def actualitza_estat(self, info):
        """Refresca camps i informació després d'un «Ajusta» correcte."""
        info = dict(info or {})
        if not info:
            return
        self._info = info
        try:
            self._durada = float(info.get("durada"))
        except (TypeError, ValueError):
            pass
        try:
            self._ini0 = float(info.get("ini"))
        except (TypeError, ValueError):
            pass
        try:
            self._bpm0 = float(info.get("bpm"))
        except (TypeError, ValueError):
            pass
        compassos = str(info.get("compassos") or "")
        if "/" in compassos:
            try:
                self._num0, self._den0 = (
                    int(x) for x in compassos.split("/", 1))
            except (TypeError, ValueError):
                pass
        n_real = info.get("n_real")
        self._n_actual = n_real
        bpm = info.get("bpm")
        if bpm is not None:
            self.sp_bpm.blockSignals(True)
            try:
                self.sp_bpm.setValue(
                    bpm_unit.de_quarter(float(bpm), self._unit))
            finally:
                self.sp_bpm.blockSignals(False)
        if compassos:
            self.ed_compas.blockSignals(True)
            try:
                self.ed_compas.setText(compassos)
            finally:
                self.ed_compas.blockSignals(False)
        if n_real is not None:
            self.sp_n.blockSignals(True)
            try:
                self.sp_n.setValue(
                    min(9999, max(1, int(round(float(n_real))))))
            except (TypeError, ValueError):
                pass
            finally:
                self.sp_n.blockSignals(False)
        self.chk_n.blockSignals(True)
        try:
            self.chk_n.setChecked(False)
            self.chk_n.setEnabled(n_real is not None and self._durada > 0)
        finally:
            self.chk_n.blockSignals(False)
        self._refresca_graella_info()

    def _refresca_graella_info(self):
        """Re-pinta la informació (no editable) amb l'estat actual."""
        while self._info_grid.count():
            elem = self._info_grid.takeAt(0)
            w = elem.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._omple_info(self._valors_info())

    def set_assistencia(self, text):
        """Mostra el resum del recalcul fix."""
        self.ajuda.setText(str(text or ""))

    def accept(self):
        try:
            self.valors()
        except ValueError as e:
            QMessageBox.warning(self, "Tempo invàlid", str(e))
            return
        super().accept()

    def reject(self):
        super().reject()

    def closeEvent(self, ev):
        super().closeEvent(ev)

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
        self.sp_bpm.setEnabled(True)
        if actiu:
            self._actualitza_bpm_n()

    def valors(self):
        """`(bpm, num, den)`; «num/den» o «num»."""
        num, den = self._parse_compas()
        if self.n_auto():
            bpm = (float(self.sp_n.value())
                   * (float(num) * 4.0 / float(den)) * 60.0 / self._durada)
            return tempo_map.valida_tempo(bpm, num, den)
        return tempo_map.valida_tempo(
            bpm_unit.a_quarter(float(self.sp_bpm.value()), self._unit),
            num, den)

