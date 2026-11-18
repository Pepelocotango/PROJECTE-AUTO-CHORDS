"""Diàleg per quadrar els extrems de la còpia WAV a compassos sencers."""
from PyQt5.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout,
)

from app import audio_edit, bpm_unit, limits, mapa_tempo, pipeline, tempo_map
from app.camp_text import CampText
from app.finestres import GeometriaMixin


def _mostra_delta(frames, sr):
    signe = "+" if frames > 0 else ""
    return f"{signe}{frames / float(sr):.3f} s ({signe}{frames} mostres)"


class DialegQuadratura(GeometriaMixin, QDialog):
    """Ajusta l'inici i/o el final a `N` compassos sencers.

    No modifica res: només calcula un pla. El visor l'aplica de forma atòmica
    (WAV + model + desat) quan l'usuari prem «Aplica».
    """

    def __init__(self, parent=None, durada=0.0, sr=44100, pos=0.0,
                 trams=None, mode="ambdos"):
        super().__init__(parent)
        self.setWindowTitle("Quadra els extrems de la WAV")
        self.setMinimumWidth(760)
        self.durada = float(durada)
        self.sr = int(sr)
        self.trams = [mapa_tempo.des_de_tupla(t) for t in (trams or ())]
        self._pla = None
        if not self.trams:
            raise ValueError("Cal un mapa de tempo/compàs per a quadrar")
        self._primer = self.trams[0]
        self._ultim = self.trams[-1]
        self._unit_ini = self._unitat_tram(self._primer)
        self._unit_fi = self._unitat_tram(self._ultim)
        self._t1_defecte = max(0.0, min(float(pos), self.durada))
        self._t_final_defecte = max(
            0.0, min(float(pos), self.durada))
        self._n_fi_actual = audio_edit.calcula_n_cua(
            self.durada, self._t_final_defecte, self._ultim.bpm,
            self._ultim.num, self._ultim.den, "ceil")

        lay = QVBoxLayout(self)
        intro = QLabel(
            "Ajusta només la <b>còpia de treball</b> (l'àudio original no es "
            "toca). Marca on entra la cançó i l'app afig o retalla el silenci "
            "necessari perquè l'inici o el final queden en compassos sencers.")
        intro.setWordWrap(True)
        lay.addWidget(intro)

        self.g_ini = QGroupBox(
            "Inici: quants compassos hi ha abans que comence la cançó?")
        self.g_ini.setCheckable(True)
        self.g_ini.setChecked(True)
        f_ini = QFormLayout(self.g_ini)
        self.sp_t1 = QDoubleSpinBox()
        self.sp_t1.setRange(0.0, max(0.0, self.durada))
        self.sp_t1.setDecimals(6)
        self.sp_t1.setSuffix(" s")
        self.sp_t1.setValue(self._t1_defecte)
        self.sp_t1.setToolTip(
            "Temps real on entra el compàs 1 de la cançó, dins la WAV actual.")
        f_ini.addRow("On comença la cançó (temps 1):", self.sp_t1)

        self.sp_bpm_ini = QDoubleSpinBox()
        self.sp_bpm_ini.setDecimals(6)
        self._configura_bpm_spin(self.sp_bpm_ini, self._unit_ini,
                                 float(self._primer.bpm))
        self.sp_bpm_ini.setToolTip(
            "BPM del compàs d'entrada en la unitat de pols triada; "
            "l'intern es recalcula en aplicar.")
        self.ed_compas_ini = CampText(
            f"{int(self._primer.num)}/{int(self._primer.den)}")
        self.ed_compas_ini.setToolTip("Compàs d'entrada de l'introducció.")
        self.cb_unitat_ini = QComboBox()
        self._omple_unitats(self.cb_unitat_ini, self._unit_ini)
        self.cb_unitat_ini.setToolTip(
            "Unitat amb què s'expressa el BPM de l'inici (negra, negra amb "
            "punt, blanca…). Canviar-la manté el tempo intern.")
        f_ini.addRow("Compàs de l'inici:", self.ed_compas_ini)
        f_ini.addRow("Unitat del BPM de l'inici:", self.cb_unitat_ini)
        f_ini.addRow("BPM de l'inici:", self.sp_bpm_ini)

        self.sp_n_ini = QSpinBox()
        self.sp_n_ini.setRange(0, 9999)
        self.sp_n_ini.setValue(self._n_ini("ceil"))
        self.sp_n_ini.setToolTip(
            "Compàs 1..N seran introducció; N=0 talla fins al temps 1.")
        f_ini.addRow("Quants compassos abans de la cançó:", self.sp_n_ini)

        fila = QHBoxLayout()
        for text, tip, mode_preset in (
                ("Conserva el so i afig silenci",
                 "Conserva tot el so anterior i afig només el silenci que "
                 "falta fins al pròxim compàs sencer.", "ceil"),
                ("Retalla el tros sobrant",
                 "Retalla només la part que sobra del compàs anterior; no "
                 "afig silenci.", "floor"),
                ("Deixa 1 compàs d'introducció",
                 "Força exactament un compàs abans del temps 1; afig o "
                 "retalla el que calga.", "un"),
                ("Comença directament al temps 1",
                 "Retalla tot el que hi ha abans del temps 1; no deixa cap "
                 "compàs d'introducció.", "zero")):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(
                lambda _=False, m=mode_preset: self._posa_n_ini(m))
            fila.addWidget(b)
        f_ini.addRow("", fila)
        lay.addWidget(self.g_ini)

        self.g_fi = QGroupBox(
            "Final: on acaba la música i quants compassos de cua vols?")
        self.g_fi.setCheckable(True)
        self.g_fi.setChecked(False)
        f_fi = QFormLayout(self.g_fi)
        self.sp_fort = QDoubleSpinBox()
        self.sp_fort.setRange(0.0, max(0.0, self.durada))
        self.sp_fort.setDecimals(6)
        self.sp_fort.setSuffix(" s")
        self.sp_fort.setValue(self._t_final_defecte)
        self.sp_fort.setToolTip(
            "Punt on s'acaba la música i comença la cua o els aplaudiments. "
            "El tall o l'estirament es fa des d'ací fins al final de la WAV.")
        f_fi.addRow("On s'acaba la música (inici de la cua):", self.sp_fort)

        self.sp_bpm_fi = QDoubleSpinBox()
        self.sp_bpm_fi.setDecimals(6)
        self._configura_bpm_spin(self.sp_bpm_fi, self._unit_fi,
                                 float(self._ultim.bpm))
        self.sp_bpm_fi.setToolTip(
            "BPM del tram de cua en la unitat de pols triada; pot ser "
            "diferent del tram normal anterior.")
        self.ed_compas_fi = CampText(
            f"{int(self._ultim.num)}/{int(self._ultim.den)}")
        self.ed_compas_fi.setToolTip(
            "Compàs del tram de cua (4/4, 3/4, 6/8…).")
        self.cb_unitat_fi = QComboBox()
        self._omple_unitats(self.cb_unitat_fi, self._unit_fi)
        self.cb_unitat_fi.setToolTip(
            "Unitat amb què s'expressa el BPM de la cua. Canviar-la manté "
            "el tempo intern.")
        f_fi.addRow("Compàs de l'últim tram:", self.ed_compas_fi)
        f_fi.addRow("Unitat del BPM de la cua:", self.cb_unitat_fi)
        f_fi.addRow("BPM de l'últim tram:", self.sp_bpm_fi)

        self.sp_n_fi = QSpinBox()
        self.sp_n_fi.setRange(1, 9999)
        self.sp_n_fi.setValue(self._n_fi_actual)
        self.sp_n_fi.setToolTip(
            "N objectiu de l'últim tram. Si activeu la protecció del fort, "
            "pot caldre apujar-lo; la previsualització mostra el resultat real.")
        self.lb_n_fi_actual = QLabel(
            f"La cua actual té {self._n_fi_actual} compassos sencers.")
        self.lb_n_fi_actual.setObjectName("secundari")
        f_fi.addRow("N final (objectiu):", self.sp_n_fi)
        f_fi.addRow("", self.lb_n_fi_actual)

        fila = QHBoxLayout()
        b = QPushButton("Conserva tota la cua i afig silenci")
        b.setToolTip(
            "Manté tots els aplaudiments o la cua i afig només el silenci "
            "que falta per al pròxim compàs sencer.")
        b.clicked.connect(lambda: self._posa_n_fi("ceil"))
        fila.addWidget(b)
        b = QPushButton("Retalla la cua sobrant")
        b.setToolTip(
            "Retalla només la fracció de compàs que sobra al final, sense "
            "passar-se del temps fort protegit.")
        b.clicked.connect(lambda: self._posa_n_fi("floor"))
        fila.addWidget(b)
        f_fi.addRow("", fila)

        fila = QHBoxLayout()
        self.sp_k = QSpinBox()
        self.sp_k.setRange(0, 999)
        self.sp_k.setValue(1)
        self.sp_k.setToolTip("Compassos de cua després del temps fort final.")
        b = QPushButton("Deixa K compassos després del fort")
        b.clicked.connect(self._posa_k)
        fila.addWidget(self.sp_k)
        fila.addWidget(b)
        f_fi.addRow("Cua després del fort:", fila)
        lay.addWidget(self.g_fi)

        self.previsualitzacio = QLabel()
        self.previsualitzacio.setWordWrap(True)
        self.previsualitzacio.setObjectName("secundari")
        lay.addWidget(self.previsualitzacio)
        self.avis_n = QLabel(
            "Els compassos inicials es veuran com a compassos de silenci "
            "(acord N) a la partitura; no canvien el temps de la música.")
        self.avis_n.setWordWrap(True)
        lay.addWidget(self.avis_n)

        self.botons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.botons.button(QDialogButtonBox.Ok).setText("Aplica l'ajust")
        self.botons.button(QDialogButtonBox.Cancel).setText("Cancel·la")
        self.botons.accepted.connect(self.accept)
        self.botons.rejected.connect(self.reject)
        lay.addWidget(self.botons)

        for w in (self.sp_t1, self.sp_bpm_ini, self.sp_n_ini,
                  self.sp_bpm_fi, self.sp_n_fi, self.sp_fort, self.sp_k):
            w.valueChanged.connect(self._actualitza)
        for w in (self.ed_compas_ini, self.ed_compas_fi):
            w.textChanged.connect(self._actualitza)
        self.cb_unitat_ini.currentIndexChanged.connect(
            lambda _i: self._canvia_unitat(self.cb_unitat_ini,
                                           self.sp_bpm_ini, "_unit_ini"))
        self.cb_unitat_fi.currentIndexChanged.connect(
            lambda _i: self._canvia_unitat(self.cb_unitat_fi,
                                           self.sp_bpm_fi, "_unit_fi"))
        for w in (self.g_ini, self.g_fi):
            w.toggled.connect(self._actualitza)
        mode = str(mode or "ambdos").strip().lower()
        if mode == "inici":
            self.g_ini.setChecked(True)
            self.g_fi.setChecked(False)
        elif mode == "final":
            self.g_ini.setChecked(False)
            self.g_fi.setChecked(True)
        self._actualitza()

    @staticmethod
    def _unitat_tram(tr):
        unit = getattr(tr, "beat_unit", None)
        if not unit:
            unit = bpm_unit.unitat_per_defecte(
                int(tr.num), int(tr.den), getattr(tr, "agrupacio", ""))
        return bpm_unit.normalitza(unit)

    @staticmethod
    def _omple_unitats(combo, unit):
        for clau, etiqueta in bpm_unit.opcions():
            combo.addItem(etiqueta, clau)
        idx = combo.findData(bpm_unit.normalitza(unit))
        if idx >= 0:
            combo.setCurrentIndex(idx)

    @staticmethod
    def _configura_bpm_spin(spin, unit, bpm_intern):
        unit = bpm_unit.normalitza(unit)
        factor = bpm_unit.factor(unit)
        spin.blockSignals(True)
        spin.setRange(limits.BPM_MIN / factor, limits.BPM_MAX / factor)
        spin.setValue(bpm_unit.de_quarter(float(bpm_intern), unit))
        spin.blockSignals(False)

    def _canvia_unitat(self, combo, spin, attr):
        """Canvia la unitat de presentació mantenint el BPM intern."""
        nou = bpm_unit.normalitza(combo.currentData())
        vell = getattr(self, attr)
        if nou == vell:
            return
        intern = bpm_unit.a_quarter(float(spin.value()), vell)
        setattr(self, attr, nou)
        self._configura_bpm_spin(spin, nou, intern)
        self._actualitza()

    def _bpm(self, edit, spin, unit=None):
        valor = bpm_unit.a_quarter(
            float(spin.value()), unit or bpm_unit.DEFECTE)
        text = edit.text().strip()
        if "/" not in text:
            raise ValueError("El compàs ha de ser num/den")
        num, den = (int(x) for x in text.split("/", 1))
        tempo_map.valida_tempo(valor, num, den)
        u = bpm_unit.normalitza(unit or bpm_unit.DEFECTE)
        if not bpm_unit.encaixa_en_compas(u, num, den):
            sugg = bpm_unit.unitat_per_defecte(num, den)
            raise ValueError(
                f"La unitat {u} no encaixa amb el compàs {num}/{den}; "
                f"tria {sugg} o canvia el compàs")
        return valor, num, den, u

    @staticmethod
    def _bpm_text(bpm, unit):
        u = bpm_unit.normalitza(unit)
        return (f"{bpm_unit.de_quarter(float(bpm), u):g} "
                f"{bpm_unit.etiqueta(u).lower()}/min "
                f"({float(bpm):g} negres/min)")

    def _n_ini(self, mode):
        try:
            bpm, num, den, _u = self._bpm(
                self.ed_compas_ini, self.sp_bpm_ini, self._unit_ini)
            return audio_edit.calcula_n_inici(
                self.sp_t1.value(), bpm, num, den, mode)
        except Exception:
            return 0

    def _n_fi(self, mode):
        try:
            bpm, num, den, _u = self._bpm(
                self.ed_compas_fi, self.sp_bpm_fi, self._unit_fi)
            return audio_edit.calcula_n_cua(
                self.durada, self.sp_fort.value(), bpm, num, den, mode)
        except Exception:
            return 1

    def _posa_n_ini(self, mode):
        self.sp_n_ini.setValue(self._n_ini(mode))

    def _posa_n_fi(self, mode):
        self.sp_n_fi.setValue(self._n_fi(mode))

    def _posa_k(self):
        self.sp_n_fi.setValue(max(1, int(self.sp_k.value())))

    def _actualitza(self):
        self.avis_n.setVisible(self.g_ini.isChecked()
                               and self.sp_n_ini.value() > 0)
        try:
            pla = self._calcula()
            self._pla = pla
            text = []
            if pla["aplica_inici"]:
                text.append(
                    f"Inici: {_mostra_delta(pla['silenci_ini']
                                            - pla['retalla_ini'], self.sr)} · "
                    f"{pla['n_ini']} compassos a "
                    f"{self._bpm_text(pla['bpm_ini'], pla.get('beat_unit_ini'))} "
                    f"({pla['num_ini']}/{pla['den_ini']}).")
            if pla["aplica_final"]:
                text.append(
                    f"Final: {_mostra_delta(pla['silenci_fi']
                                            - pla['retalla_fi'], self.sr)} · "
                    f"objectiu {pla.get('n_cua', pla['n_fi'])} compassos "
                    f"de cua a "
                    f"{self._bpm_text(pla['bpm_fi'], pla.get('beat_unit_fi'))} "
                    f"({pla['num_fi']}/{pla['den_fi']}).")
                if pla.get("target_final_point") is not None:
                    tall = float(pla["target_final_point"])
                    rest = max(0.0, self.durada - tall)
                    text.append(
                        f"Queden {rest:.3f} s des del tall. Amb "
                        f"{pla['num_fi']}/{pla['den_fi']} a "
                        f"{self._bpm_text(pla['bpm_fi'], pla.get('beat_unit_fi'))} "
                        f"hi caben "
                        f"{rest / (float(pla['num_fi']) * 4.0 / float(pla['den_fi']) * 60.0 / pla['bpm_fi']):.3f} "
                        f"compassos; N final objectiu "
                        f"{pla.get('n_cua', pla['n_fi'])}.")
            tr = audio_edit.transforma_model_extrems(
                [pipeline.Clip(0.0, self.durada, ("C", "0"))],
                [(0.0, self.durada, "A", "A")], self.trams, [],
                self.durada, pla)
            ini = tr["trams"][0]
            fi = tr["trams"][-1]
            text.append(
                f"Tram inicial resultant: {float(ini.n):g} compassos a "
                f"{self._bpm_text(float(ini.bpm), ini.beat_unit)} "
                f"({ini.compassos}).")
            if fi is not ini:
                text.append(
                    f"Tram final resultant: {float(fi.n):g} compassos a "
                    f"{self._bpm_text(float(fi.bpm), fi.beat_unit)} "
                    f"({fi.compassos}).")
            text.append(f"Nova durada: {pla['durada_nova']:.3f} s.")
            self.previsualitzacio.setText(" ".join(text))
            self.botons.button(QDialogButtonBox.Ok).setEnabled(True)
        except Exception as e:  # noqa: BLE001
            self._pla = None
            self.previsualitzacio.setText(f"No es pot aplicar: {e}")
            self.botons.button(QDialogButtonBox.Ok).setEnabled(False)

    def _calcula(self):
        if not (self.g_ini.isChecked() or self.g_fi.isChecked()):
            raise ValueError("Tria l'inici, el final o tots dos")
        bpm_ini = num_ini = den_ini = unit_ini = None
        if self.g_ini.isChecked():
            bpm_ini, num_ini, den_ini, unit_ini = self._bpm(
                self.ed_compas_ini, self.sp_bpm_ini, self._unit_ini)
        bpm_fi = num_fi = den_fi = unit_fi = None
        if self.g_fi.isChecked():
            bpm_fi, num_fi, den_fi, unit_fi = self._bpm(
                self.ed_compas_fi, self.sp_bpm_fi, self._unit_fi)
        fort = self.sp_fort.value() if self.g_fi.isChecked() else None
        return audio_edit.planifica_extrems(
            self.durada, self.sr, self.trams,
            t_temps1=self.sp_t1.value(),
            n_ini=self.sp_n_ini.value(),
            t_ultim_fort=fort,
            n_fi=self.sp_n_fi.value(),
            aplica_inici=self.g_ini.isChecked(),
            aplica_final=self.g_fi.isChecked(),
            bpm_ini=bpm_ini, num_ini=num_ini, den_ini=den_ini,
            beat_unit_ini=unit_ini,
            t_final=fort, bpm_fi=bpm_fi, num_fi=num_fi, den_fi=den_fi,
            beat_unit_fi=unit_fi)

    def plan(self):
        if self._pla is None:
            self._calcula()
        return self._pla
