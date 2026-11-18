"""Diàleg per quadrar els extrems de la còpia WAV a compassos sencers."""
from PyQt5.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout,
)

from app import audio_edit, limits, mapa_tempo, pipeline, tempo_map
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
                 trams=None):
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
        self._t1_defecte = max(0.0, min(float(pos), self.durada))

        lay = QVBoxLayout(self)
        intro = QLabel(
            "Marca on cau el <b>temps 1 real</b> de la cançó (després de la "
            "introducció, el silenci o els aplaudiments) i, si cal, on és el "
            "<b>darrer temps fort</b> que no vols tallar. L'app ajusta només "
            "la còpia de treball; l'àudio original no es toca.")
        intro.setWordWrap(True)
        lay.addWidget(intro)

        self.g_ini = QGroupBox("Inici: compassos sencers abans del temps 1")
        self.g_ini.setCheckable(True)
        self.g_ini.setChecked(True)
        f_ini = QFormLayout(self.g_ini)
        self.sp_t1 = QDoubleSpinBox()
        self.sp_t1.setRange(0.0, max(0.0, self.durada))
        self.sp_t1.setDecimals(3)
        self.sp_t1.setSuffix(" s")
        self.sp_t1.setValue(self._t1_defecte)
        self.sp_t1.setToolTip(
            "Temps real on entra el compàs 1 de la cançó, dins la WAV actual.")
        f_ini.addRow("Temps 1 real:", self.sp_t1)

        self.sp_bpm_ini = QDoubleSpinBox()
        self.sp_bpm_ini.setRange(limits.BPM_MIN, limits.BPM_MAX)
        self.sp_bpm_ini.setDecimals(3)
        self.sp_bpm_ini.setValue(float(self._primer.bpm))
        self.sp_bpm_ini.setToolTip("BPM del compàs d'entrada, en negres/minut.")
        self.ed_compas_ini = CampText(
            f"{int(self._primer.num)}/{int(self._primer.den)}")
        self.ed_compas_ini.setToolTip("Compàs d'entrada de l'introducció.")
        f_ini.addRow("BPM d'entrada:", self.sp_bpm_ini)
        f_ini.addRow("Compàs d'entrada:", self.ed_compas_ini)

        self.sp_n_ini = QSpinBox()
        self.sp_n_ini.setRange(0, 9999)
        self.sp_n_ini.setValue(self._n_ini("ceil"))
        self.sp_n_ini.setToolTip(
            "Compàs 1..N seran introducció; N=0 talla fins al temps 1.")
        f_ini.addRow("N compassos inicials:", self.sp_n_ini)

        fila = QHBoxLayout()
        for text, mode in (
                ("Conserva-ho tot (ceil)", "ceil"),
                ("Retalla el sobrant (floor)", "floor"),
                ("1 compàs", "un"),
                ("Directe al temps 1 (0)", "zero")):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, m=mode: self._posa_n_ini(m))
            fila.addWidget(b)
        f_ini.addRow("", fila)
        lay.addWidget(self.g_ini)

        self.g_fi = QGroupBox("Final: cua i aplaudiments en compassos sencers")
        self.g_fi.setCheckable(True)
        self.g_fi.setChecked(False)
        f_fi = QFormLayout(self.g_fi)
        self.chk_fort = QCheckBox("Protegeix el darrer temps fort")
        self.chk_fort.setToolTip(
            "El retall no pot quedar-se abans d'este temps fort; es "
            "conserva almenys un compàs de resolució després.")
        f_fi.addRow(self.chk_fort)
        self.sp_fort = QDoubleSpinBox()
        self.sp_fort.setRange(0.0, max(0.0, self.durada))
        self.sp_fort.setDecimals(3)
        self.sp_fort.setSuffix(" s")
        self.sp_fort.setValue(max(0.0, self.durada - 0.001))
        self.sp_fort.setEnabled(False)
        f_fi.addRow("Temps fort final:", self.sp_fort)

        self.sp_bpm_fi = QDoubleSpinBox()
        self.sp_bpm_fi.setRange(limits.BPM_MIN, limits.BPM_MAX)
        self.sp_bpm_fi.setDecimals(3)
        self.sp_bpm_fi.setValue(float(self._ultim.bpm))
        self.sp_bpm_fi.setToolTip("BPM de l'últim tram, en negres/minut.")
        self.ed_compas_fi = CampText(
            f"{int(self._ultim.num)}/{int(self._ultim.den)}")
        self.sp_bpm_fi.setReadOnly(True)
        self.ed_compas_fi.setReadOnly(True)
        self.sp_bpm_fi.setToolTip(
            "BPM de l'últim tram (es canvia al mapa abans de quadrar).")
        self.ed_compas_fi.setToolTip(
            "Compàs de l'últim tram (es canvia al mapa abans de quadrar).")
        f_fi.addRow("BPM final:", self.sp_bpm_fi)
        f_fi.addRow("Compàs final:", self.ed_compas_fi)

        self.sp_n_fi = QSpinBox()
        self.sp_n_fi.setRange(1, 9999)
        self.sp_n_fi.setValue(self._n_fi("ceil"))
        self.sp_n_fi.setToolTip(
            "Compassos de l'últim tram. Sempre respecta la protecció del fort.")
        f_fi.addRow("N compassos finals:", self.sp_n_fi)

        fila = QHBoxLayout()
        b = QPushButton("Conserva tota la cua (ceil)")
        b.clicked.connect(lambda: self._posa_n_fi("ceil"))
        fila.addWidget(b)
        b = QPushButton("Retalla el sobrant (floor)")
        b.clicked.connect(lambda: self._posa_n_fi("floor"))
        fila.addWidget(b)
        f_fi.addRow("", fila)

        fila = QHBoxLayout()
        self.sp_k = QSpinBox()
        self.sp_k.setRange(0, 999)
        self.sp_k.setValue(1)
        self.sp_k.setToolTip("Compassos de cua després del temps fort final.")
        b = QPushButton("K compassos després del fort")
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
        self.botons.button(QDialogButtonBox.Ok).setText("Aplica")
        self.botons.button(QDialogButtonBox.Cancel).setText("Cancel·la")
        self.botons.accepted.connect(self.accept)
        self.botons.rejected.connect(self.reject)
        lay.addWidget(self.botons)

        for w in (self.sp_t1, self.sp_bpm_ini, self.sp_n_ini,
                  self.sp_bpm_fi, self.sp_n_fi, self.sp_fort, self.sp_k):
            w.valueChanged.connect(self._actualitza)
        for w in (self.ed_compas_ini, self.ed_compas_fi):
            w.textChanged.connect(self._actualitza)
        for w in (self.g_ini, self.g_fi, self.chk_fort):
            if isinstance(w, QGroupBox):
                w.toggled.connect(self._actualitza)
            else:
                w.toggled.connect(self._fort_canviat)
        self._actualitza()

    def _bpm(self, edit, spin):
        valor = float(spin.value())
        text = edit.text().strip()
        if "/" not in text:
            raise ValueError("El compàs ha de ser num/den")
        num, den = (int(x) for x in text.split("/", 1))
        tempo_map.valida_tempo(valor, num, den)
        return valor, num, den

    def _n_ini(self, mode):
        try:
            bpm, num, den = self._bpm(self.ed_compas_ini,
                                      self.sp_bpm_ini)
            return audio_edit.calcula_n_inici(
                self.sp_t1.value(), bpm, num, den, mode)
        except Exception:
            return 0

    def _n_fi(self, mode):
        try:
            bpm, num, den = self._bpm(self.ed_compas_fi,
                                      self.sp_bpm_fi)
            fort = self.sp_fort.value() if self.chk_fort.isChecked() else None
            return audio_edit.calcula_n_fi(
                self.durada, self._ultim.ini, bpm, num, den, mode,
                t_ultim_fort=fort)
        except Exception:
            return 1

    def _posa_n_ini(self, mode):
        self.sp_n_ini.setValue(self._n_ini(mode))

    def _posa_n_fi(self, mode):
        self.sp_n_fi.setValue(self._n_fi(mode))

    def _posa_k(self):
        try:
            bpm, num, den = self._bpm(self.ed_compas_fi,
                                      self.sp_bpm_fi)
            fort = (self.sp_fort.value() if self.chk_fort.isChecked()
                    else self._ultim.ini)
            self.sp_n_fi.setValue(audio_edit.n_fi_despres_fort(
                fort, self._ultim.ini, bpm, num, den,
                self.sp_k.value()))
        except Exception:
            pass

    def _fort_canviat(self, actiu):
        self.sp_fort.setEnabled(bool(actiu))
        self._actualitza()

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
                    f"{pla['bpm_ini']:g} BPM ({pla['num_ini']}/"
                    f"{pla['den_ini']}).")
            if pla["aplica_final"]:
                text.append(
                    f"Final: {_mostra_delta(pla['silenci_fi']
                                            - pla['retalla_fi'], self.sr)} · "
                    f"{pla['n_fi']} compassos a "
                    f"{pla['bpm_fi']:g} BPM ({pla['num_fi']}/"
                    f"{pla['den_fi']}).")
            tr = audio_edit.transforma_model_extrems(
                [pipeline.Clip(0.0, self.durada, ("C", "0"))],
                [(0.0, self.durada, "A", "A")], self.trams, [],
                self.durada, pla)
            ini = tr["trams"][0]
            fi = tr["trams"][-1]
            text.append(
                f"Tram inicial resultant: {float(ini.n):g} compassos a "
                f"{float(ini.bpm):g} BPM ({ini.compassos}).")
            if fi is not ini:
                text.append(
                    f"Tram final resultant: {float(fi.n):g} compassos a "
                    f"{float(fi.bpm):g} BPM ({fi.compassos}).")
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
        bpm_ini = num_ini = den_ini = None
        if self.g_ini.isChecked():
            bpm_ini, num_ini, den_ini = self._bpm(
                self.ed_compas_ini, self.sp_bpm_ini)
        if self.g_fi.isChecked():
            bpm, num, den = self._bpm(self.ed_compas_fi, self.sp_bpm_fi)
            if (abs(bpm - self._ultim.bpm) > 1e-9
                    or num != self._ultim.num or den != self._ultim.den):
                raise ValueError(
                    "El final només pot usar el BPM/compàs de l'últim tram "
                    "(modifica'l abans al mapa)")
        fort = self.sp_fort.value() if self.chk_fort.isChecked() else None
        return audio_edit.planifica_extrems(
            self.durada, self.sr, self.trams,
            t_temps1=self.sp_t1.value(),
            n_ini=self.sp_n_ini.value(),
            t_ultim_fort=fort,
            n_fi=self.sp_n_fi.value(),
            aplica_inici=self.g_ini.isChecked(),
            aplica_final=self.g_fi.isChecked(),
            bpm_ini=bpm_ini, num_ini=num_ini, den_ini=den_ini)

    def plan(self):
        if self._pla is None:
            self._calcula()
        return self._pla
