"""Diàleg per editar un tram de tempo/compàs."""
from PyQt5.QtCore import QEvent, Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QSpinBox, QVBoxLayout,
    QWidget,
)

from app.camp_text import CampText
from app.dialeg_canvi_unitat import PanellCanviUnitat
from app import bpm_unit, limits, tempo_map, theme

from app.finestres import GeometriaMixin


#: Ajuda de cada casella del bloc «Opcions»: `(nom, activada, desactivada)`.
#: S'usa com a tooltip i, per tant, també com a text de la secció «Ajuda».
AJUDA_OPCIONS = {
    "chk_beats": (
        "Beats QM",
        "usa els beats QM detectats dins el tram com a restricció forta per "
        "triar N i compàs (poden corregir la signatura).",
        "ignora els beats QM; N i compàs es deriven només de la durada, el "
        "BPM i el veí esquerre.",
    ),
    "chk_segons_durada": (
        "Segons del tram",
        "usa la durada real del clip (fi − ini) com a referència.",
        "deriva la durada de referència de N, compàs i BPM dels camps.",
    ),
    "chk_unitat_beat": (
        "Unitat del beat",
        "interpreta els beats QM amb la unitat de Beat/TAP activa (negra, "
        "negra amb punt, corxera o blanca).",
        "tracta els beats QM sempre com a negres.",
    ),
    "chk_compas_lliure": (
        "Canviar compàs",
        "el recalcul pot triar una signatura diferent de la de referència.",
        "manté fixa la signatura de referència i només ajusta N i BPM.",
    ),
    "chk_n": (
        "N fix",
        "pren els compassos del camp com a restricció i deriva el BPM quan "
        "cal.",
        "deixa que el recalcul trie N per encaixar la durada i els beats.",
    ),
    "chk_silencia_factor": (
        "Silencia avís 1,5×",
        "els avisos de factor 1,5×/2/3 d'este tram no es mostren; el "
        "resultat continua sent MITJÀ i no s'auto-aplica.",
        "es mostra l'avís de factor 1,5×/2/3 i cal revisar-lo.",
    ),
    "chk_segons": (
        "En segons (rubato)",
        "el clip dura el que diu l'àudio, sense graella ni compassos enters "
        "(la partitura es pren a 100 BPM); desactiva els botons Recalcula i "
        "l'edició del compàs.",
        "el clip s'interpreta amb compàs i BPM normals.",
    ),
}


def _ajuda_opcio(clau):
    """Text d'ajuda d'una casella amb l'estat activat i desactivat."""
    nom, activada, desactivada = AJUDA_OPCIONS[clau]
    return (f"{nom}\n"
            f"Activada: {activada}\n"
            f"Desactivada: {desactivada}")


class DialegTramTempo(GeometriaMixin, QDialog):
    """Edita un **tros** del mapa: BPM i compàs (on comença es mostra)."""

    #: «Ajusta»: aplica els canvis sense tancar el diàleg.
    aplicaRequested = pyqtSignal()
    #: «Recalcula»: mode «fix» o «mobil», amb les opcions del bloc Opcions.
    recalculRequested = pyqtSignal(str)
    def __init__(self, parent=None, inici=0.0, bpm=120.0, num=4, den=4,
                 inicial=False, text_inici=None, unit=bpm_unit.DEFECTE,
                 n_actual=None, durada=None, info=None,
                 beat_unit=bpm_unit.DEFECTE,
                 silencia_factor=False):
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
        self._silencia_factor = bool(silencia_factor)
        self.setWindowTitle("BPM, compàs i compassos")
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

        # --- columna esquerra: 3 blocs (fix, mòbil i opcions comunes)
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
        self.b_recalc_fix = QPushButton("Recalcula")
        self.b_recalc_fix.setToolTip(
            "Recalcul fix: manté l'inici i la fi del clip i deriva el BPM.")
        self.b_recalc_fix.clicked.connect(lambda: self._recalcula("fix"))
        lay_fix.addWidget(self.b_recalc_fix)
        col_ed.addWidget(grup_fix)

        grup_mob = QGroupBox("Recalcul mòbil")
        lay_mob = QVBoxLayout(grup_mob)
        form_mob = QFormLayout()
        (self.sp_n_mob, self.ed_compas_mob,
         self.sp_bpm_mob) = self._crea_camps(form_mob)
        lay_mob.addLayout(form_mob)
        self.b_recalc_mob = QPushButton("Recalcula")
        self.b_recalc_mob.setToolTip(
            "Recalcul mòbil: mou la frontera compartida amb l'N/compàs "
            "resultants i el BPM del camp.")
        self.b_recalc_mob.clicked.connect(lambda: self._recalcula("mobil"))
        lay_mob.addWidget(self.b_recalc_mob)
        col_ed.addWidget(grup_mob)
        self._enllaça_camps(self.sp_n, self.sp_n_mob)
        self._enllaça_camps(self.ed_compas, self.ed_compas_mob)
        self._enllaça_camps(self.sp_bpm, self.sp_bpm_mob)

        grup_opc = QGroupBox("Opcions")
        lay_opc = QVBoxLayout(grup_opc)
        _etq = QLabel("Què ha de tindre en compte el recalc:")
        _etq.setWordWrap(True)
        lay_opc.addWidget(_etq)
        self.chk_beats = QCheckBox("Beats QM")
        self.chk_beats.setToolTip(_ajuda_opcio("chk_beats"))
        self.chk_beats.setChecked(True)
        self.chk_segons_durada = QCheckBox("Segons del tram")
        self.chk_segons_durada.setToolTip(_ajuda_opcio("chk_segons_durada"))
        self.chk_segons_durada.setChecked(True)
        self.chk_unitat_beat = QCheckBox("Unitat del beat")
        self.chk_unitat_beat.setToolTip(_ajuda_opcio("chk_unitat_beat"))
        self.chk_unitat_beat.setChecked(True)
        self.chk_compas_lliure = QCheckBox("Canviar compàs")
        self.chk_compas_lliure.setToolTip(_ajuda_opcio("chk_compas_lliure"))
        self.chk_compas_lliure.setChecked(True)
        self.chk_n = QCheckBox("N fix")
        self.chk_n.setToolTip(_ajuda_opcio("chk_n"))
        _te_n = (n_actual is not None and self._durada > 0)
        self.chk_n.setChecked(_te_n)
        self.chk_n.setEnabled(_te_n)
        self.chk_segons = QCheckBox("En segons (rubato)")
        self.chk_segons.setToolTip(_ajuda_opcio("chk_segons"))
        self.chk_segons.setChecked(int(num) <= 0 or int(den) <= 0)
        self.chk_silencia_factor = QCheckBox("Silencia avís 1,5×")
        self.chk_silencia_factor.setToolTip(
            _ajuda_opcio("chk_silencia_factor"))
        self.chk_silencia_factor.setChecked(self._silencia_factor)
        grid_opc = QGridLayout()
        grid_opc.setHorizontalSpacing(12)
        grid_opc.setVerticalSpacing(2)
        grid_opc.addWidget(self.chk_beats, 0, 0)
        grid_opc.addWidget(self.chk_segons_durada, 0, 1)
        grid_opc.addWidget(self.chk_unitat_beat, 1, 1)
        grid_opc.addWidget(self.chk_compas_lliure, 2, 0)
        grid_opc.addWidget(self.chk_n, 2, 1)
        grid_opc.addWidget(self.chk_segons, 3, 0, 1, 2)
        grid_opc.addWidget(self.chk_silencia_factor, 4, 0, 1, 2)
        lay_opc.addLayout(grid_opc)
        beat_row = QHBoxLayout()
        l_beat = QLabel("Beat/TAP:")
        self.cb_beat = QComboBox()
        for _clau, _et in bpm_unit.opcions():
            self.cb_beat.addItem(_et, _clau)
        _idx = self.cb_beat.findData(self._beat_unit)
        if _idx >= 0:
            self.cb_beat.setCurrentIndex(_idx)
        self.cb_beat.setToolTip(
            "Unitat del beat detectat i del TAP: qualsevol figura simple "
            "o amb punt (rodona, blanca, negra, corxera, semicorxera).")
        l_beat.setToolTip(self.cb_beat.toolTip())
        self.cb_beat.currentIndexChanged.connect(self._canvia_beat)
        beat_row.addWidget(l_beat)
        beat_row.addWidget(self.cb_beat)
        beat_row.addStretch(1)
        lay_opc.addLayout(beat_row)
        self.chk_mantenir_pulsacio = QCheckBox(
            "Mantenir la pulsació (BPM visible) en canviar el compàs")
        self.chk_mantenir_pulsacio.setChecked(True)
        self.chk_mantenir_pulsacio.setToolTip(
            "Per defecte, en canviar el compàs es conserva el número de BPM "
            "visible en la unitat de pulsació (Cas B). Desactiva-ho per "
            "conservar el BPM intern en negres/minut (Cas A).")
        lay_opc.addWidget(self.chk_mantenir_pulsacio)
        self.lbl_previsio_pulsacio = QLabel("")
        self.lbl_previsio_pulsacio.setWordWrap(True)
        self.lbl_previsio_pulsacio.setObjectName("secundari")
        lay_opc.addWidget(self.lbl_previsio_pulsacio)
        self.grup_unitat = QGroupBox("Canvi d'unitat")
        lay_unitat = QVBoxLayout(self.grup_unitat)
        self.panell_unitat = PanellCanviUnitat(self)
        for _w in self.panell_unitat._widgets:
            lay_unitat.addWidget(_w)
        self.panell_unitat.rb_tempo.toggled.connect(
            self._actualitza_panell_unitat)
        self.panell_unitat.rb_numero.toggled.connect(
            self._actualitza_panell_unitat)
        self.grup_unitat.setVisible(False)
        lay_opc.addWidget(self.grup_unitat)
        col_ed.addWidget(grup_opc)
        col_ed.addStretch(1)

        self.chk_n.toggled.connect(self._n_canviat)
        for sp in (self.sp_n, self.sp_n_mob):
            sp.valueChanged.connect(self._actualitza_bpm_n)
        for ed in (self.ed_compas, self.ed_compas_mob):
            ed.textChanged.connect(self._actualitza_bpm_n)
        self.chk_segons.toggled.connect(self._segons_canviat)
        self._segons_canviat(self.chk_segons.isChecked())
        for ed in (self.ed_compas, self.ed_compas_mob):
            ed.textChanged.connect(self._actualitza_previsio_pulsacio)
        for sp in (self.sp_bpm, self.sp_bpm_mob):
            sp.valueChanged.connect(self._actualitza_previsio_pulsacio)
            sp.valueChanged.connect(self._marca_bpm_manual)
        self.chk_mantenir_pulsacio.toggled.connect(
            self._actualitza_previsio_pulsacio)
        self._actualitza_previsio_pulsacio()

        # --- columna dreta: informació completa, NOMÉS lectura.
        # No participa en l'acceptació del diàleg ni en cap càlcul d'edició.
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

        # Fila independent d'ajuda: replica la info que mostra la infobox
        # principal en passar el ratolí per un camp, botó o casella.
        grup_ajuda = QGroupBox("Ajuda")
        lay_ajuda = QVBoxLayout(grup_ajuda)
        self.ajuda = QLabel(
            "Passa el ratolí per un camp, botó o casella per vore què fa. "
            "Cada casella explica què fa activada i desactivada.")
        self.ajuda.setWordWrap(True)
        self.ajuda.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.ajuda.setMinimumHeight(72)
        lay_ajuda.addWidget(self.ajuda)
        self.alternatives = QListWidget()
        self.alternatives.setMaximumHeight(72)
        self.alternatives.setVisible(False)
        self.alternatives.setToolTip(
            "Alternatives del recalcul; doble-clic per carregar-ne una als "
            "camps (després Ajusta/OK per aplicar).")
        self.alternatives.itemDoubleClicked.connect(self._triar_alternativa)
        lay_ajuda.addWidget(self.alternatives)
        self.b_escolta = QPushButton("Escolta la proposta")
        self.b_escolta.setToolTip(
            "Reprodueix el clip en bucle amb el metrònom al BPM, compàs i "
            "unitat proposats, sense aplicar cap canvi. Torna a prémer per "
            "aturar-ho; Ajusta/OK ho atura abans d'aplicar.")
        self.b_escolta.clicked.connect(self._escolta)
        self.b_escolta.setVisible(hasattr(parent, "escolta_tram"))
        self._audicio_activa = False
        lay_ajuda.addWidget(self.b_escolta)
        col_info.addWidget(grup_ajuda)
        col_info.addStretch(1)

        botons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.b_ajusta = botons.addButton(
            "Ajusta", QDialogButtonBox.ActionRole)
        self.b_ajusta.setToolTip(
            "Aplica els canvis d'edició/recalcul sense tancar la finestra "
            "i actualitza la informació del clip.")
        self.b_ajusta.clicked.connect(self._ajusta)
        botons.button(QDialogButtonBox.Ok).setToolTip(
            "Aplica els canvis i tanca el diàleg.")
        botons.button(QDialogButtonBox.Cancel).setToolTip(
            "Tanca el diàleg sense aplicar cap canvi pendent.")
        botons.accepted.connect(self.accept)
        botons.rejected.connect(self.reject)
        lay.addWidget(botons)
        # L'ajuda s'actualitza amb el tooltip del giny que hi ha davall el
        # ratolí (la mateixa informació que la infobox de la finestra).
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
        """Crea el joc N/compàs/BPM d'un bloc (fix o mòbil)."""
        sp_bpm = QDoubleSpinBox()
        _factor = bpm_unit.factor(self._unit)
        sp_bpm.setRange(limits.BPM_MIN / _factor,
                        limits.BPM_MAX / _factor)
        sp_bpm.setDecimals(3)
        sp_bpm.setValue(bpm_unit.de_quarter(self._bpm0, self._unit))
        sp_bpm.setToolTip(
            "BPM del clip en la unitat activa. El recalc fix el deriva de "
            "l'N, el compàs i la durada; el mòbil l'usa com a objectiu.")
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

    @staticmethod
    def _enllaça_camps(a, b):
        """Manté sincronitzats dos camps equivalents (fix ↔ mòbil)."""
        def _copia(src, dst):
            dst.blockSignals(True)
            try:
                if hasattr(dst, "value"):
                    dst.setValue(src.value())
                else:
                    dst.setText(src.text())
            finally:
                dst.blockSignals(False)

        if hasattr(a, "valueChanged"):
            a.valueChanged.connect(lambda *_v: _copia(a, b))
            b.valueChanged.connect(lambda *_v: _copia(b, a))
        else:
            a.textChanged.connect(lambda *_v: _copia(a, b))
            b.textChanged.connect(lambda *_v: _copia(b, a))

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
        """Opcions comunes que ha de tindre en compte cada recalcul."""
        return {
            "beats": self.chk_beats.isChecked(),
            "segons": self.chk_segons_durada.isChecked(),
            "unitat": self.chk_unitat_beat.isChecked(),
            "compas": self.chk_compas_lliure.isChecked(),
            "n_fix": self.chk_n.isChecked(),
            "rubato": self.chk_segons.isChecked(),
            "silencia_factor": self.chk_silencia_factor.isChecked(),
        }

    def _recalcula(self, mode):
        """Valida els camps i demana un recalcul fix o mòbil."""
        if self.chk_segons.isChecked():
            QMessageBox.warning(
                self, "Recalcula",
                "El rubato no es recalcula des d'este diàleg.")
            return
        try:
            bpm, num, den, _n = self.valors_camps()
            tempo_map.valida_tempo(bpm, num, den)
        except ValueError as e:
            QMessageBox.warning(self, "Tempo invàlid", str(e))
            return
        self.recalculRequested.emit(str(mode))

    def _posa_bpm_unitat(self, bpm_quarter, unit):
        """Escriu el BPM en la unitat donada als dos jocs de camps."""
        val = bpm_unit.de_quarter(float(bpm_quarter), unit)
        for sp in (self.sp_bpm, self.sp_bpm_mob):
            sp.blockSignals(True)
            try:
                sp.setValue(val)
            finally:
                sp.blockSignals(False)

    def _canvia_beat(self, _idx=None):
        """Mostra el panell inline de canvi d'unitat (no aplica encara)."""
        unit = bpm_unit.normalitza(
            self.cb_beat.currentData() or self._beat_unit)
        if unit == self._beat_unit:
            self.grup_unitat.setVisible(False)
            return
        bpm_int = bpm_unit.a_quarter(float(self.sp_bpm.value()), self._unit)
        self.panell_unitat.set_dades(
            "Beat/TAP", bpm_int, self._beat_unit, unit)
        self.panell_unitat.rb_tempo.setChecked(True)
        self.grup_unitat.setVisible(True)
        self._actualitza_panell_unitat()
        self._actualitza_previsio_pulsacio()

    def _actualitza_panell_unitat(self, *_a):
        if not getattr(self, "grup_unitat", None) or \
                self.grup_unitat.isHidden():
            return
        bpm, unit = self.panell_unitat.resultat()
        self._beat_unit = unit
        self._unit = unit
        self._posa_bpm_unitat(bpm, unit)
        self._actualitza_previsio_pulsacio()

    def unitat(self):
        """Unitat de pols que s'aplicarà amb Aplicar/OK."""
        return self._beat_unit

    def silencia_factor(self):
        return bool(self.chk_silencia_factor.isChecked())

    def actualitza_beat_unit(self, unit):
        """Refresca el selector i els camps amb la unitat aplicada."""
        unit = bpm_unit.normalitza(unit)
        bpm_int = bpm_unit.a_quarter(float(self.sp_bpm.value()), self._unit)
        self._beat_unit = unit
        self._unit = unit
        self._posa_bpm_unitat(bpm_int, unit)
        idx = self.cb_beat.findData(unit)
        if idx >= 0:
            self.cb_beat.blockSignals(True)
            try:
                self.cb_beat.setCurrentIndex(idx)
            finally:
                self.cb_beat.blockSignals(False)
        self.grup_unitat.setVisible(False)

    def _escolta(self):
        """Escolta la proposta en bucle (sense aplicar-la) o l'atura."""
        if self._audicio_activa:
            self._atura_escolta()
            return
        vr = self.parent()
        if not hasattr(vr, "escolta_tram"):
            return
        try:
            bpm, num, den = self.valors()
        except ValueError as e:
            QMessageBox.warning(self, "Tempo invàlid", str(e))
            return
        fi = self._ini0 + self._durada
        if fi <= self._ini0:
            return
        ok = bool(vr.escolta_tram(
            self._ini0, fi, bpm, num, den, self._beat_unit))
        self._audicio_activa = ok
        self.b_escolta.setText(
            "Atura l'escolta" if ok else "Escolta la proposta")
        if ok:
            self.set_assistencia(
                "Escoltant la proposta en bucle. Ajusta/OK l'aplica; "
                "Atura o Cancel només para l'àudio.")
        else:
            self.set_assistencia(
                "No s'ha pogut iniciar l'àudio per escoltar la proposta.")

    def _atura_escolta(self):
        """Atura l'audició i restaura l'estat previ del visor."""
        if not self._audicio_activa:
            return
        self._audicio_activa = False
        vr = self.parent()
        if hasattr(vr, "atura_escolta_tram"):
            vr.atura_escolta_tram()
        self.b_escolta.setText("Escolta la proposta")

    def _ajusta(self):
        """Aplica els canvis sense tancar el diàleg (emet `aplicaRequested`)."""
        self._atura_escolta()
        try:
            self.valors()
        except ValueError as e:
            QMessageBox.warning(self, "Tempo invàlid", str(e))
            return
        self.aplicaRequested.emit()

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
            for sp in (self.sp_bpm, self.sp_bpm_mob):
                sp.blockSignals(True)
                try:
                    sp.setValue(
                        bpm_unit.de_quarter(float(bpm), self._unit))
                finally:
                    sp.blockSignals(False)
        if compassos:
            for ed in (self.ed_compas, self.ed_compas_mob):
                ed.blockSignals(True)
                try:
                    ed.setText(compassos)
                finally:
                    ed.blockSignals(False)
        if n_real is not None:
            for sp in (self.sp_n, self.sp_n_mob):
                sp.blockSignals(True)
                try:
                    sp.setValue(
                        min(9999, max(1, int(round(float(n_real))))))
                except (TypeError, ValueError):
                    pass
                finally:
                    sp.blockSignals(False)
        self._refresca_graella_info()
        self._segons_canviat(self.chk_segons.isChecked())

    def _refresca_graella_info(self):
        """Re-pinta la informació (no editable) amb l'estat actual."""
        while self._info_grid.count():
            elem = self._info_grid.takeAt(0)
            w = elem.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._omple_info(self._valors_info())

    def set_assistencia(self, text, alternatives=None):
        """Mostra el resum del recalcul i, si cal, alternatives triables."""
        self.ajuda.setText(str(text or ""))
        self.alternatives.clear()
        alts = list(alternatives or ())
        for c in alts:
            try:
                item = QListWidgetItem(
                    f"{float(c['bpm']):.3f} BPM · {int(c['num'])}/"
                    f"{int(c['den'])} · N={int(c['n'])}")
            except (KeyError, TypeError, ValueError):
                continue
            item.setData(Qt.UserRole, dict(c))
            self.alternatives.addItem(item)
        self.alternatives.setVisible(bool(self.alternatives.count()))

    def _triar_alternativa(self, item):
        """Carrega una alternativa als camps (no l'aplica automàticament)."""
        c = item.data(Qt.UserRole)
        if not c:
            return
        unit = self._beat_unit
        for sp in (self.sp_n, self.sp_n_mob):
            sp.blockSignals(True)
            try:
                sp.setValue(max(1, int(c.get("n") or 1)))
            finally:
                sp.blockSignals(False)
        for ed in (self.ed_compas, self.ed_compas_mob):
            ed.blockSignals(True)
            try:
                ed.setText(f"{int(c['num'])}/{int(c['den'])}")
            finally:
                ed.blockSignals(False)
        self._posa_bpm_unitat(float(c["bpm"]), unit)
        self.set_assistencia(
            f"Alternativa carregada: {float(c['bpm']):.3f} BPM · "
            f"{int(c['num'])}/{int(c['den'])} · N={int(c['n'])}. "
            "Prem Ajusta/OK per aplicar.")

    def actualitza_info(self, info):
        """Refresca només la graella d'informació, sense tocar els camps."""
        info = dict(info or {})
        if not info:
            return
        self._info = info
        self._refresca_graella_info()

    def accept(self):
        self._atura_escolta()
        try:
            self.valors()
        except ValueError as e:
            QMessageBox.warning(self, "Tempo invàlid", str(e))
            return
        super().accept()

    def reject(self):
        self._atura_escolta()
        super().reject()

    def closeEvent(self, ev):
        self._atura_escolta()
        super().closeEvent(ev)

    def _segons_canviat(self, actiu):
        """En segons el compàs no té sentit: s'apaga l'edició dels camps."""
        for b in (self.b_recalc_fix, self.b_recalc_mob):
            b.setEnabled(not bool(actiu))
        for ed in (self.ed_compas, self.ed_compas_mob):
            ed.setEnabled(not bool(actiu))
        actiu_n = not bool(actiu) and self.chk_n.isEnabled()
        for sp in (self.sp_n, self.sp_n_mob):
            sp.setEnabled(actiu_n)
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
        for sp in (self.sp_bpm, self.sp_bpm_mob):
            sp.blockSignals(True)
            try:
                sp.setValue(bpm_unit.de_quarter(bpm, self._unit))
            finally:
                sp.blockSignals(False)

    def mantenir_pulsacio(self):
        """True si en canviar el compàs s'ha de conservar el BPM visible."""
        return bool(getattr(self, "chk_mantenir_pulsacio", None)
                    and self.chk_mantenir_pulsacio.isChecked())

    def _unitat_objectiu_compas(self):
        """Unitat que correspondrà al compàs escrit, respectant una tria explícita."""
        try:
            num, den = self._parse_compas()
        except ValueError:
            return self._beat_unit
        if (num, den) == (self._num0, self._den0):
            return self._beat_unit
        actual = bpm_unit.normalitza(self._beat_unit)
        derivada_vella = bpm_unit.unitat_per_defecte(
            self._num0, self._den0, self._agr0)
        if actual != derivada_vella:
            return actual
        return bpm_unit.unitat_per_defecte(num, den, "")

    def _marca_bpm_manual(self, *_a):
        """Recorda que l'usuari ha tocat el BPM (no el recalc de N)."""
        self._bpm_manual = True

    def bpm_visible(self):
        """BPM visible de referència per al Cas B, en la unitat inicial."""
        if getattr(self, "_bpm_manual", False):
            return self._bpm_visible_actual()
        return bpm_unit.de_quarter(self._bpm0, self._unit_inicial)

    def _bpm_visible_actual(self):
        """BPM visible equivalent al camp, expressat en la unitat inicial."""
        try:
            intern = bpm_unit.a_quarter(float(self.sp_bpm.value()), self._unit)
            return bpm_unit.de_quarter(intern, self._unit_inicial)
        except (AttributeError, TypeError, ValueError, ZeroDivisionError):
            return bpm_unit.de_quarter(self._bpm0, self._unit_inicial)

    def _actualitza_previsio_pulsacio(self, *_a):
        """Mostra els dos BPM (visible i intern) abans d'aplicar el compàs."""
        lbl = getattr(self, "lbl_previsio_pulsacio", None)
        if lbl is None:
            return
        if not self.mantenir_pulsacio():
            lbl.setText(
                f"Cas A: es conserva el tempo intern "
                f"({self._bpm0:.3f} negres/min); canviarà el BPM visible.")
            return
        try:
            num, den = self._parse_compas()
        except ValueError:
            lbl.setText("Pulsació: compàs encara no vàlid.")
            return
        if (num, den) == (self._num0, self._den0):
            lbl.setText("Pulsació: sense canvi de compàs.")
            return
        unit_nova = self._unitat_objectiu_compas()
        visible = self.bpm_visible()
        intern_nou = bpm_unit.a_quarter(visible, unit_nova)
        lbl.setText(
            f"Cas B: {visible:.3f} {bpm_unit.etiqueta(self._unit_inicial).lower()}"
            f" → {visible:.3f} {bpm_unit.etiqueta(unit_nova).lower()} · "
            f"intern {self._bpm0:.3f} → {intern_nou:.3f} negres/min.")

    def _n_canviat(self, actiu):
        actiu = bool(actiu) and self._durada > 0
        for sp in (self.sp_n, self.sp_n_mob):
            sp.setEnabled(actiu)
        # El BPM continua editable: és l'objectiu del recalc mòbil.
        for sp in (self.sp_bpm, self.sp_bpm_mob):
            sp.setEnabled(True)
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
