"""Barra de transport, snap i metrònom (F3).

Extret de `app/main.py`: creació de la barra de transport, canvi de snap i
controls del metrònom. `BarresMixin` assumeix els widgets i slots de `Finestra`.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QComboBox, QLabel, QPushButton, QSlider

from . import bpm_unit as bpm_unit_mod, icones

class BarresMixin:
    """Transport, snap i metrònom."""

    def _acc_visor(self, nom, *args):
        """Crida un mètode del visor (o una acció derivada) si n'hi ha."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return
        if nom == "menys10":
            vr.ves_a(vr.pos - 10)
        elif nom == "mes10":
            vr.ves_a(vr.pos + 10)
        else:
            getattr(vr, nom)(*args)

    def _sincronitza_velocitat(self, f):
        """Posa el selector de velocitat de la barra al valor del visor."""
        c = getattr(self, "cmb_vel_tb", None)
        if c is None:
            return
        try:
            i = c.findData(round(float(f), 4))
        except (TypeError, ValueError):
            return
        if i < 0:
            return
        c.blockSignals(True)
        c.setCurrentIndex(i)
        c.blockSignals(False)

    def _crea_transport(self, bar):
        def boto(text, tip, accio, checkable=False, icona=None):
            b = QPushButton("" if icona else text)
            if icona:
                b.setIcon(icones.ico(icona, 16))
                b.setIconSize(icones.pm_mida(16))
            b.setToolTip(tip)
            if checkable:
                b.setCheckable(True)
            b.clicked.connect(accio)
            bar.addWidget(b)
            return b

        self.b_play_tb = boto("▶", "Reprodueix / atura  (Espai)",
                              lambda: self._acc_visor("play_stop"),
                              icona="play")
        boto("⏹", "Atura i torna a l'inici",
             lambda: self._acc_visor("stop_inici"), icona="square")
        boto("−10s", "Endarrere 10 s",
             lambda: self._acc_visor("menys10"), icona="rewind")
        boto("+10s", "Endavant 10 s",
             lambda: self._acc_visor("mes10"), icona="fast-forward")
        bar.addSeparator()
        boto("A⟨", "Marca inici de loop (A)",
             lambda: self._acc_visor("marca_A"), icona="arrow-left-to-line")
        boto("⟩B", "Marca fi de loop (B)",
             lambda: self._acc_visor("marca_B"), icona="arrow-right-to-line")
        self.tb_loop = boto("🔁", "Activa/desactiva el loop A-B",
                            lambda: None, checkable=True, icona="repeat-2")
        self.tb_loop.clicked.connect(
            lambda: self._acc_visor("set_loop", self.tb_loop.isChecked()))
        # Neteja el loop (treu A i B), al costat del botó del loop.
        self.tb_neteja_loop = boto("", "Neteja el loop (treu A i B)",
                                   self._neteja_loop, icona="x")
        bar.addSeparator()
        boto("🔍−", "Allunya el zoom", lambda: self._acc_visor("zoom", 2.0),
             icona="zoom-out")
        boto("🔍+", "Apropa el zoom", lambda: self._acc_visor("zoom", 0.5),
             icona="zoom-in")
        boto("Tot", "Zoom total (veure-ho tot)",
             lambda: self._acc_visor("zoom_tot"), icona="maximize")
        boto("", "Zoom a la selecció (ajusta la vista als clips seleccionats)",
             lambda: self._acc_visor("zoom_seleccio"), icona="focus")
        self.tb_mut = boto("🔇", "Silencia / reactiva el so",
                           lambda: None, checkable=True, icona="volume-x")
        self.tb_mut.setObjectName("mute")
        self.tb_mut.clicked.connect(
            lambda: self._acc_visor("set_mut", self.tb_mut.isChecked()))
        # Velocitat de reproducció (0,5–3×, to mantingut): el visor la prepara
        # i la barra només la manega; `velocitatCanviada` manté els dos
        # selectors sincronitzats.
        self.cmb_vel_tb = QComboBox()
        for v in (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0):
            self.cmb_vel_tb.addItem(f"{v:g}×", float(v))
        self.cmb_vel_tb.setCurrentIndex(2)
        self.cmb_vel_tb.setMaximumWidth(80)
        self.cmb_vel_tb.setToolTip(
            "Velocitat de reproducció (0,5–3×) amb el to mantingut (ffmpeg "
            "atempo, com el VLC). El cursor, el loop i el metrònom es mantenen "
            "alineats; el primer cop a cada velocitat pot trigar uns segons.")
        self.cmb_vel_tb.currentIndexChanged.connect(
            lambda _i: self._acc_visor("set_velocitat",
                                       self.cmb_vel_tb.currentData()))
        bar.addWidget(self.cmb_vel_tb)
        bar.addSeparator()
        # metrònom: només en mode BPM · compàs (vegeu _actualitza_metro_ui)
        self.b_metro = QPushButton()
        self.b_metro.setIcon(icones.ico("metronome"))
        self.b_metro.setObjectName("metro")
        self.b_metro.setCheckable(True)
        self.b_metro.setToolTip("Metrònom (només en mode BPM · compàs)")
        self.b_metro.clicked.connect(self._toggle_metro)
        bar.addWidget(self.b_metro)
        self.vol_metro = QSlider(Qt.Horizontal)
        self.vol_metro.setRange(0, 100)
        self.vol_metro.setValue(60)
        self.vol_metro.setMaximumWidth(90)
        self.vol_metro.setToolTip("Volum del clic del metrònom (%)")
        self.vol_metro.valueChanged.connect(self._canvia_vol_metro)
        bar.addWidget(self.vol_metro)
        self.cb_metro = QComboBox()
        for _et, _val in (("Auto", "auto"), ("Compàs", "compas"),
                          ("Temps", "temps"), ("Grup", "grup")):
            self.cb_metro.addItem(_et, _val)
        self.cb_metro.setCurrentIndex(0)
        self.cb_metro.setMaximumWidth(82)
        self.cb_metro.setToolTip(
            "Patró del metrònom: Auto (temps + accents de compàs i grup), "
            "Compàs (només el primer temps), Temps (sense accents de grup) "
            "o Grup (només compàs i inicis de grup).")
        self.cb_metro.currentIndexChanged.connect(self._canvia_mode_metro)
        bar.addWidget(self.cb_metro)
        bar.addWidget(QLabel("Clic:"))
        self.cb_metro_unit = QComboBox()
        self.cb_metro_unit.addItem("Denominador", "auto")
        for _clau, _et in bpm_unit_mod.opcions():
            self.cb_metro_unit.addItem(_et, _clau)
        self.cb_metro_unit.setCurrentIndex(0)
        self.cb_metro_unit.setMaximumWidth(110)
        self.cb_metro_unit.setToolTip(
            "Unitat de clic del metrònom: auto (denominador), negra, "
            "negra amb punt, corxera o blanca.")
        self.cb_metro_unit.currentIndexChanged.connect(
            self._canvia_metro_click_unit)
        bar.addWidget(self.cb_metro_unit)
        bar.addSeparator()
        # Quantitza: just abans del Snap (petició de l'operador). Recicla el
        # lloc de l'antic «Mode fàcil».
        self.b_quantitza = QPushButton("Quantitza")
        self.b_quantitza.setObjectName("secundari")
        self.b_quantitza.setToolTip(
            "Quantitza els inicis dels clips a la graella. Abast: tot, "
            "selecció, només acords o només estructura. No toca BPM, compàs "
            "ni el cru; es pot desfer i refer.")
        self.b_quantitza.clicked.connect(self._quantitza_ui)
        bar.addWidget(self.b_quantitza)
        self.b_quantitza_bpm = QPushButton("BPM…")
        self.b_quantitza_bpm.setObjectName("secundari")
        self.b_quantitza_bpm.setMaximumWidth(86)
        self.b_quantitza_bpm.setToolTip(
            "Quantitza el BPM dels clips normals amb 0, 1 o 2 decimals i "
            "re-encaixa les fronteres amb beats sencers. Els rubatos no es "
            "quantitzen.")
        self.b_quantitza_bpm.clicked.connect(self._quantitza_bpm_ui)
        self.barra_accions.addWidget(self.b_quantitza_bpm)
        self.barra_accions.addSeparator()
        self.barra_accions.addWidget(QLabel("Graella:"))
        # Graella configurable: interruptor de snap + divisió (habilita el nudge fi).
        self.tb_snap = boto("Snap", "Interruptor de snap (encaixar a la graella)",
                            self._canvia_snap, checkable=True)
        self.tb_snap.setChecked(True)
        self.cb_graella = QComboBox()
        self.cb_graella.setToolTip("Divisió de la graella: grid visual i snap")
        for et, val in (
                ("Beats QM", "qm_beats"),
                ("Auto (zoom)", ""), ("Negra (1/4)", "negra"),
                ("Corxera (1/8)", "corxera"),
                ("Semicorxera (1/16)", "semicorxera"),
                ("Fusa (1/32)", "fusa"),
                ("Treset de negra (2/3)", "treset_negra"),
                ("Treset de corxera (1/3)", "treset_corxera"),
                ("Treset de semicorxera (1/6)", "treset_semicorxera"),
                ("1 compàs", "compas1"), ("2 compassos", "compas2"),
                ("4 compassos", "compas4"), ("6 compassos", "compas6"),
                ("8 compassos", "compas8"), ("12 compassos", "compas12"),
                ("16 compassos", "compas16"), ("24 compassos", "compas24"),
                ("32 compassos", "compas32"), ("48 compassos", "compas48"),
                ("64 compassos", "compas64")):
            self.cb_graella.addItem(et, val)
        self.cb_graella.currentIndexChanged.connect(self._canvia_snap)
        self.barra_accions.addWidget(self.cb_graella)
        self.barra_accions.addSeparator()
        # Commutador d'EINA del timeline: «intel·ligent» (per defecte; la fletxa
        # s'adapta al que hi ha sota) o «marc» (arrossegar dibuixa un rectangle
        # de selecció i no mou clips). Viu aquí, darrere del snap, perquè és on
        # es decideix com respon el ratolí a la graella.
        self.b_eina = QPushButton("Eina: intel·ligent")
        self.b_eina.setObjectName("secundari")
        self.b_eina.setCheckable(True)
        self.b_eina.setChecked(False)          # intel·ligent = per defecte
        self.b_eina.setToolTip(
            "Eina del timeline (també al menú Selecciona i amb la tecla E):\n"
            "· intel·ligent: la fletxa s'adapta (mou/redimensiona clips, "
            "Shift+clic = rang, regla = loop).\n"
            "· selecció: arrossega per dibuixar un rectangle i queda "
            "seleccionat "
            "tot el que hi SONA a dins (només les pistes que cobreixi).")
        self.b_eina.toggled.connect(self._canvia_eina)
        self.barra_accions.addWidget(self.b_eina)

    def _canvia_snap(self):
        """Aplica l'interruptor de snap + la divisió de graella al visor."""
        vr = getattr(self, "visor_ref", None)
        if vr is None or not hasattr(self, "tb_snap"):
            return
        mode = self.cb_graella.currentData() or ""
        if mode == "qm_beats":
            info = getattr(self, "_beats_actuals", None)
            if not info:
                info = (getattr(getattr(self, "projecte", None), "dades", {})
                        .get("analisi_beats"))
            beats = (info or {}).get("beats") if isinstance(info, dict) else []
            vr.set_snap_beats(beats or [])
            if not beats:
                self.registra("Snap QM: no hi ha beats detectats.")
        vr.set_snap(on=self.tb_snap.isChecked(), divisio=mode)

    def _toggle_metro(self, on=None):
        """Activa/desactiva el metrònom (sincronitza botó i acció)."""
        if on is None:      # clicat des de l'acció de menú
            on = self.a_metro.isChecked()
        self.b_metro.setChecked(bool(on))
        self.a_metro.setChecked(bool(on))
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            vr.set_metro(bool(on))

    def _canvia_vol_metro(self, v):
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            vr._canvia_vol_metro(int(v))

    def _canvia_mode_metro(self, _idx=None):
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            vr.set_metro_mode(self.cb_metro.currentData())

    def _metro_click_unit_val(self):
        cb = getattr(self, "cb_metro_unit", None)
        return cb.currentData() if cb is not None else "auto"

    def _canvia_metro_click_unit(self, _idx=None):
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return
        if not vr.set_metro_click_unit(self._metro_click_unit_val()):
            idx = self.cb_metro_unit.findData(
                getattr(vr, "metro_click_unit", "auto"))
            if idx >= 0:
                self.cb_metro_unit.blockSignals(True)
                self.cb_metro_unit.setCurrentIndex(idx)
                self.cb_metro_unit.blockSignals(False)

    def _actualitza_metro_ui(self):
        """El metrònom només està disponible en mode BPM · compàs."""
        vr = getattr(self, "visor_ref", None)
        disponible = vr is not None and vr.metro_disponible()
        for w in (self.b_metro, self.vol_metro, self.cb_metro,
                  self.cb_metro_unit, self.a_metro):
            w.setEnabled(disponible)
        if not disponible:
            # en mode Lliure: desmarcat i amb tooltip explicatiu
            self.b_metro.setChecked(False)
            self.a_metro.setChecked(False)
            tip = "Només disponible en mode BPM · compàs"
            self.b_metro.setToolTip(tip)
            self.vol_metro.setToolTip(tip)
            self.cb_metro.setToolTip(tip)
            self.cb_metro_unit.setToolTip(tip)
            self.a_metro.setToolTip(tip)
        else:
            self.b_metro.setToolTip("Metrònom")
            self.vol_metro.setToolTip("Volum del clic del metrònom (%)")
            self.cb_metro.setToolTip(
                "Patró del metrònom: Auto, Compàs, Temps o Grup")
            self.cb_metro_unit.setToolTip(
                "Unitat de clic: auto (denominador), negra, negra amb punt, "
                "corxera o blanca")
            self.a_metro.setToolTip("Clic de metrònom")
            idx_u = self.cb_metro_unit.findData(
                getattr(vr, "metro_click_unit", "auto"))
            if idx_u >= 0 and idx_u != self.cb_metro_unit.currentIndex():
                self.cb_metro_unit.blockSignals(True)
                self.cb_metro_unit.setCurrentIndex(idx_u)
                self.cb_metro_unit.blockSignals(False)
            # Desactiva les unitats que no caben en algun compàs del mapa.
            model = self.cb_metro_unit.model()
            unit_actual = self._metro_click_unit_val()
            for i in range(self.cb_metro_unit.count()):
                unitat = self.cb_metro_unit.itemData(i)
                valid = unitat == "auto" or vr.click_unit_encaixa(unitat)
                it = model.item(i)
                if it is not None:
                    it.setEnabled(valid)
            if not vr.click_unit_encaixa(unit_actual):
                # El mapa ha canviat i la unitat triada ja no hi cap.
                auto = self.cb_metro_unit.findData("auto")
                self.cb_metro_unit.blockSignals(True)
                self.cb_metro_unit.setCurrentIndex(auto)
                self.cb_metro_unit.blockSignals(False)
                vr.metro_click_unit = "auto"
                vr.infoMissatge.emit(
                    "La unitat de clic anterior ja no encaixa en el nou "
                    "compàs; s'ha posat en auto.")
            idx = self.cb_metro.findData(getattr(vr, "metro_mode", "auto"))
            if idx >= 0 and idx != self.cb_metro.currentIndex():
                self.cb_metro.blockSignals(True)
                self.cb_metro.setCurrentIndex(idx)
                self.cb_metro.blockSignals(False)
