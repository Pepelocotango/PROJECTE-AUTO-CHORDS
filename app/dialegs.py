"""Diàleg d'opcions de l'autodetecció (BPM / Acords / Estructura).

S'obre en clicar `🎯 Detecta` (pestanya BPM) o `Analitza` (pestanya Acords).
Els controls de la pestanya **Acords** es construeixen **dinàmicament** a
partir del descriptor `.n3` del Chordino (vegeu `app/vamp_params.py`), així
que si el plugin canvia, el diàleg s'adapta sol.

Tot en català.
"""

import json
import time

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget,
    QVBoxLayout,
)

from app import config, graella, tempo, tempo_map, vamp_params

# Traducció al català dels títols dels paràmetres del Chordino (els que dona
# el plugin son en anglès) + una ajuda curta de quan tocar-los.
NOMS_CA = {
    "useNNLS": "Transcripció aproximada (NNLS)",
    "useHMM": "Suavitzat HMM (Viterbi)",
    "rollon": "Tall de greus (roll-on espectral)",
    "tuningmode": "Mode d'afinació",
    "whitening": "Equalització espectral",
    "s": "Forma espectral",
}
AJUDA_CA = {
    "useNNLS": "Converteix l'espectre a croma amb NNLS (normalment millor que "
               "la FFT simple). Deixa'l activat.",
    "useHMM": "Suavitza els acords amb un model de Markov: menys canvis "
              "nerviosos. Desactiva'l si vols detectar canvis ràpids.",
    "rollon": "Emmudeix les freqüències greus abans d'analitzar (0 = no en "
              "treu cap). Apuja'l si el baix confon els acords.",
    "tuningmode": "Afinació global (recomanat) o local. Prova la local si el "
                  "tema està desafinat o és en directe.",
    "whitening": "Iguala l'espectre abans d'analitzar. Normalment activat.",
    "s": "Forma espectral (0,5–0,9). Valors alts = més suau.",
}

# Traducció dels noms de valor (value_names) dels paràmetres.
VALORS_CA = {
    "global tuning": "afinació global",
    "local tuning": "afinació local",
}

# Fitxer on es recorden les últimes opcions. Viu a `config.DADES_DIR` (un
# directori ESCRIPTIBLE: el projecte si ho és, si no l'estat d'usuari) perquè
# en una AppImage muntada la carpeta del projecte és de només lectura.
FITXER_OPCIONS = config.OPCIONS_PATH

# Valors per defecte de fàbrica del diàleg d'autodetecció. Revisats i fixats
# amb l'operador (2026-10-13). Són els que es mostren la primera vegada i els
# que restaura el botó «Restaura per defecte».
DEFECTES = {
    # ACORDS: coincideixen amb els defectes del descriptor del Chordino, però
    # els fixem explícitament perquè siguin estables (no depenen del plugin).
    "chords": {"useNNLS": 1, "useHMM": 1, "rollon": 0.0, "tuningmode": 0,
               "whitening": 1.0, "s": 0.7},
    "bpm": {
        "motor": "consens",
        "min": tempo.BPM_MIN, "max": tempo.BPM_MAX,
        "pref_min": tempo.BPM_PREFERIT[0], "pref_max": tempo.BPM_PREFERIT[1],
    },
    "structure": {"motor": "qm", "durada_min": 2.0,
                  "fusiona_iguals": True},
    # Neteja posterior dels acords (post-processat, app/postproc.py)
    "clean": {"durada_min": 0.15, "fusiona_iguals": True, "sense_baix": False,
              "reduir": False, "snap": True, "divisio": 4},
    # Anàlisi guiat (docs/ANALISI_GUIAT.md §4.3): mida del tram i si es
    # confirma la detecció amb el BPM del tram anterior.
    "guiat": {"compassos": 4, "confirma": True},
}


def _spin(minim, maxim, pas, valor, decimals=2):
    s = QDoubleSpinBox()
    s.setRange(float(minim), float(maxim))
    s.setSingleStep(float(pas) if pas else 0.05)
    s.setDecimals(decimals)
    s.setValue(float(valor))
    return s


def _combo(opcions, valor):
    c = QComboBox()
    for i, nom in enumerate(opcions):
        c.addItem(VALORS_CA.get(nom, nom), i)
    c.setCurrentIndex(int(valor))
    return c


def _checkbox(valor):
    c = QCheckBox("activat")
    c.setChecked(bool(valor))
    return c


def carrega_opcions():
    """Llegeix les opcions desades (o torna els defectes)."""
    base = json.loads(json.dumps(DEFECTES))     # copia profunda
    try:
        with open(FITXER_OPCIONS, encoding="utf-8") as f:
            desat = json.load(f)
        for seccio in base:
            base[seccio].update(desat.get(seccio) or {})
    except (OSError, ValueError):
        pass
    return base


def desa_opcions(opcions):
    """Desa les opcions triades (silenciosament si no es pot)."""
    try:
        with open(FITXER_OPCIONS, "w", encoding="utf-8") as f:
            json.dump(opcions, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


class DialegOpcions(QDialog):
    """Diàleg amb pestanyes BPM / Acords / Estructura."""

    def __init__(self, parent=None, tab="acords", opcions=None):
        super().__init__(parent)
        self.setWindowTitle("Opcions d'autodetecció")
        self.setMinimumWidth(460)
        opcions = opcions or carrega_opcions()
        # el diàleg només reescriu bpm/chords/structure/clean: la resta de
        # seccions (p. ex. «guiat») es conserven tal com estaven
        self._base = dict(opcions)

        lay = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        lay.addWidget(self.tabs)
        self._controls = {}

        self.tabs.addTab(self._tab_bpm(opcions.get("bpm", {})), "BPM")
        self.tabs.addTab(self._tab_acords(opcions.get("chords", {})), "Acords")
        self.tabs.addTab(self._tab_estructura(opcions.get("structure", {})),
                         "Estructura")
        idx = {"bpm": 0, "acords": 1, "structure": 2}.get(tab, 0)
        self.tabs.setCurrentIndex(idx)

        # botons: restaura + OK/Cancel·la
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        restaurar = QPushButton("Restaura per defecte")
        restaurar.setObjectName("secundari")
        restaurar.clicked.connect(self._restaura)
        box.addButton(restaurar, QDialogButtonBox.ResetRole)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        lay.addWidget(box)

    # -- pestanyes ---------------------------------------------------------
    def _tab_bpm(self, val):
        w = QGroupBox("Detecció de BPM (`app/tempo.py`)")
        f = QFormLayout(w)
        self._controls["bpm"] = {}
        d = val or DEFECTES["bpm"]
        c = QComboBox()
        for m, lbl in (("nostre", "Nostre (tempo.py)"),
                       ("qm", "Queen Mary (qm-tempotracker)"),
                       ("consens", "Consens (nostre + qm)")):
            c.addItem(lbl, m)
        i = c.findData(d.get("motor", "nostre"))
        c.setCurrentIndex(i if i >= 0 else 0)
        c.setToolTip("Motor de detecció del BPM. «Consens» avisa si els dos "
                     "motors no coincideixen.")
        self._controls["bpm"]["motor"] = c
        f.addRow(QLabel("Motor de detecció"), c)
        for clau, etiqueta, (mn, mx, pas) in (
                ("min", "Rang de cerca · mínim (BPM)", (30, 400, 1)),
                ("max", "Rang de cerca · màxim (BPM)", (30, 400, 1)),
                ("pref_min", "Rang preferit · mínim (BPM)", (30, 400, 1)),
                ("pref_max", "Rang preferit · màxim (BPM)", (30, 400, 1))):
            s = _spin(mn, mx, pas, d.get(clau, DEFECTES["bpm"][clau]), 0)
            self._controls["bpm"][clau] = s
            f.addRow(QLabel(etiqueta), s)
        info = QLabel("El «preferit» premia el rang musical habitual "
                      "(evita el doble/meitat).")
        info.setWordWrap(True)
        info.setStyleSheet("color:#9aa6b8; font-size:11px;")
        f.addRow(info)
        b_rec = QPushButton("Valors recomanats (60–180 · 85–150)")
        b_rec.setToolTip(
            "Rang ample i zona còmoda: és el que evita que la detecció es "
            "quede amb la meitat o el doble del tempo real.")
        b_rec.clicked.connect(self._bpm_recomanat)
        f.addRow(b_rec)
        self.lb_rang = QLabel("")
        self.lb_rang.setWordWrap(True)
        self.lb_rang.setStyleSheet("color:#b26a00; font-size:11px;")
        f.addRow(self.lb_rang)
        for clau in ("min", "max", "pref_min", "pref_max"):
            self._controls["bpm"][clau].valueChanged.connect(self._avisa_rang)
        self._avisa_rang()
        return w

    def _bpm_recomanat(self):
        """Posa el rang recomanat (60–180 · 85–150) als quatre camps."""
        c = self._controls.get("bpm", {})
        for clau, valor in (("min", 60), ("max", 180), ("pref_min", 85),
                            ("pref_max", 150)):
            if clau in c:
                c[clau].setValue(int(valor))

    def _avisa_rang(self, *_a):
        """Avís en viu si el rang de BPM és massa estret o incoherent."""
        c = self._controls.get("bpm", {})
        try:
            mn = int(c["min"].value())
            mx = int(c["max"].value())
            pm = int(c["pref_min"].value())
            px = int(c["pref_max"].value())
        except (KeyError, AttributeError):
            return
        msg = ""
        if mx - mn < 80 or (mn > 0 and mx / float(mn) < 1.8):
            msg = (f"Rang estret ({mn}–{mx} BPM): si el tema va més "
                   "ràpid o més lent, la detecció donarà la meitat o el doble "
                   "del tempo real.")
        elif not (mn <= pm < px <= mx):
            msg = ("El rang preferit ha d'estar DINS del rang de cerca i amb "
                   f"mínim < màxim (ara {pm}–{px} amb cerca {mn}–{mx}).")
        self.lb_rang.setText(msg)

    def _tab_acords(self, val):
        w = QGroupBox("Acords (`Chordino`)")
        f = QFormLayout(w)
        self._controls["chords"] = {}
        d = val or {}
        for p in vamp_params.params_de("chords"):
            pid = p["id"]
            def_v = float(d.get(pid, p["defecte"]))
            if p["valors"]:
                c = _combo(p["valors"], def_v)
            elif p["maxim"] <= 1 and p["minim"] >= 0 and p["pas"] == 1:
                c = _checkbox(def_v)             # paràmetre 0/1
            else:
                c = _spin(p["minim"], p["maxim"], p["pas"] or 0.05, def_v)
            self._controls["chords"][pid] = c
            nom = NOMS_CA.get(pid, p["titol"])
            et = QLabel()
            et.setTextFormat(Qt.RichText)
            et.setText(f"{nom}<br><span style='color:#9aa6b8;"
                       f"font-size:10px'>{pid}</span>")
            et.setToolTip(AJUDA_CA.get(pid, ""))
            c.setToolTip(AJUDA_CA.get(pid, ""))
            f.addRow(et, c)
        info = QLabel("L'estructura (qm-segmenter) no té paràmetres propis: "
                      "es neteja des de la pestanya Estructura.")
        info.setWordWrap(True)
        info.setStyleSheet("color:#9aa6b8; font-size:11px;")
        f.addRow(info)

        # --- Neteja posterior (post-processat, vegeu app/postproc.py) ---
        self._controls["clean"] = {}
        net = QGroupBox("Neteja posterior dels acords")
        fn = QFormLayout(net)
        dnet = (val or {}).get("_clean", {}) or DEFECTES["clean"]
        c = _checkbox(dnet.get("sense_baix", False))
        c.setToolTip("Elimina el baix tallat: A/E → A.")
        self._controls["clean"]["sense_baix"] = c
        fn.addRow(QLabel("Treure el baix (A/E → A)"), c)
        c = _checkbox(dnet.get("reduir", False))
        c.setToolTip("Redueix a l'acord bàsic: Cmaj7 → C, Em6 → Em.")
        self._controls["clean"]["reduir"] = c
        fn.addRow(QLabel("Reduir a l'acord bàsic"), c)
        c = _checkbox(dnet.get("fusiona_iguals", True))
        c.setToolTip("Uneix acords consecutius iguals.")
        self._controls["clean"]["fusiona_iguals"] = c
        fn.addRow(QLabel("Fusionar acords iguals seguits"), c)
        s = _spin(0, 30, 0.1, dnet.get("durada_min", 0.0), 2)
        s.setToolTip("Elimina els canvis d'acord que duren menys d'aquesta "
                     "estona, en TEMPS (es converteix a segons amb el BPM).")
        self._controls["clean"]["durada_min"] = s
        fn.addRow(QLabel("Durada mínima d'un acord (temps)"), s)
        c = _checkbox(dnet.get("snap", False))
        c.setToolTip("Mou l'inici de cada acord a la graella (BPM/compàs).")
        self._controls["clean"]["snap"] = c
        fn.addRow(QLabel("Encaixar a la graella"), c)
        s = _spin(1, 8, 1, dnet.get("divisio", 1), 0)
        s.setToolTip("Subdivisions per temps on encaixar (1 = temps).")
        self._controls["clean"]["divisio"] = s
        fn.addRow(QLabel("Subdivisions per temps"), s)
        f.addRow(net)
        return w

    def _tab_estructura(self, val):
        w = QGroupBox("Estructura (post-processat)")
        f = QFormLayout(w)
        self._controls["structure"] = {}
        d = val or DEFECTES["structure"]
        s = _spin(0, 120, 0.5, d.get("durada_min", 0.0), 1)
        self._controls["structure"]["durada_min"] = s
        f.addRow(QLabel("Durada mínima d'una secció (compassos)"), s)
        c = _checkbox(d.get("fusiona_iguals", True))
        self._controls["structure"]["fusiona_iguals"] = c
        f.addRow(QLabel("Fusiona trossos consecutius iguals"), c)
        info = QLabel("El qm-segmenter no té paràmetres ajustables: això "
                      "neteja el seu resultat.")
        info.setWordWrap(True)
        info.setStyleSheet("color:#9aa6b8; font-size:11px;")
        f.addRow(info)
        return w

    # -- resultat ----------------------------------------------------------
    def _restaura(self):
        """Torna TOTS els controls als valors de fàbrica (`DEFECTES`).

        Abans hi havia valors escrits a mà aquí que podien quedar
        desincronitzats; ara llegeix sempre de `DEFECTES` (font única).
        """
        for clau, w in self._controls["bpm"].items():
            if clau == "motor":
                idx = w.findData(DEFECTES["bpm"]["motor"])
                w.setCurrentIndex(idx if idx >= 0 else 0)
            else:
                w.setValue(float(DEFECTES["bpm"][clau]))
        for p in vamp_params.params_de("chords"):
            pid = p["id"]
            valor = DEFECTES["chords"].get(pid, p["defecte"])
            w = self._controls["chords"][pid]
            if isinstance(w, QCheckBox):
                w.setChecked(bool(valor))
            elif isinstance(w, QComboBox):
                w.setCurrentIndex(int(valor))
            else:
                w.setValue(float(valor))
        est = DEFECTES["structure"]
        self._controls["structure"]["durada_min"].setValue(
            float(est["durada_min"]))
        self._controls["structure"]["fusiona_iguals"].setChecked(
            bool(est["fusiona_iguals"]))
        cl = self._controls["clean"]
        dc = DEFECTES["clean"]
        cl["sense_baix"].setChecked(bool(dc["sense_baix"]))
        cl["reduir"].setChecked(bool(dc["reduir"]))
        cl["fusiona_iguals"].setChecked(bool(dc["fusiona_iguals"]))
        cl["durada_min"].setValue(float(dc["durada_min"]))
        cl["snap"].setChecked(bool(dc["snap"]))
        cl["divisio"].setValue(float(dc["divisio"]))

    def opcions(self):
        """Retorna les opcions triades, a punt per al pipeline."""
        bpm = {"motor": self._controls["bpm"]["motor"].currentData()}
        for k, w in self._controls["bpm"].items():
            if k != "motor":
                bpm[k] = int(w.value())
        chords = {}
        for pid, w in self._controls["chords"].items():
            if isinstance(w, QCheckBox):
                chords[pid] = int(w.isChecked())
            elif isinstance(w, QComboBox):
                chords[pid] = int(w.currentIndex())
            else:
                chords[pid] = round(float(w.value()), 3)
        est = {
            "motor": "qm",
            "durada_min": round(float(
                self._controls["structure"]["durada_min"].value()), 2),
            "fusiona_iguals": bool(
                self._controls["structure"]["fusiona_iguals"].isChecked()),
        }
        cl = self._controls["clean"]
        clean = {
            "sense_baix": bool(cl["sense_baix"].isChecked()),
            "reduir": bool(cl["reduir"].isChecked()),
            "fusiona_iguals": bool(cl["fusiona_iguals"].isChecked()),
            "durada_min": round(float(cl["durada_min"].value()), 2),
            "snap": bool(cl["snap"].isChecked()),
            "divisio": int(cl["divisio"].value()),
        }
        fora = {k: v for k, v in self._base.items()
                if k not in ("bpm", "chords", "structure", "clean")}
        fora.update({"bpm": bpm, "chords": chords, "structure": est,
                     "clean": clean})
        return fora


class DialegTrobaReemplaca(QDialog):
    """Troba i reemplaça un xifrat (acords) o una etiqueta (estructura), a tot el tema."""

    def __init__(self, parent=None, camp="acords"):
        super().__init__(parent)
        self.setWindowTitle("Troba i reemplaça")
        self.setMinimumWidth(400)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.cb_camp = QComboBox()
        self.cb_camp.addItem("Acords (xifrats)", "acords")
        self.cb_camp.addItem("Estructura (etiquetes)", "estructura")
        self.cb_camp.setCurrentIndex(1 if camp == "estructura" else 0)
        self.ed_troba = QLineEdit()
        self.ed_troba.setPlaceholderText("p. ex. Cmaj7   ·   D")
        self.ed_reemplaca = QLineEdit()
        self.ed_reemplaca.setPlaceholderText("p. ex. C9   ·   estribillo")
        form.addRow("Camp:", self.cb_camp)
        form.addRow("Troba:", self.ed_troba)
        form.addRow("Reemplaça per:", self.ed_reemplaca)
        lay.addLayout(form)
        avis = QLabel("Substitueix TOTES les aparicions exactes al tema, en una "
                      "sola operació de desfer. Si no en troba cap, no fa res.")
        avis.setWordWrap(True)
        lay.addWidget(avis)
        botons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botons.accepted.connect(self.accept)
        botons.rejected.connect(self.reject)
        lay.addWidget(botons)

    def camp(self):
        return self.cb_camp.currentData()

    def troba(self):
        return self.ed_troba.text().strip()

    def reemplaca(self):
        return self.ed_reemplaca.text().strip()


class DialegQuantitza(QDialog):
    """Quantització del model: abast + graella d'acords i d'estructura.

    No toca BPM, compàs, offset ni el cru. Només decideix QUÈ es quantitza i
    amb quina graella; l'operació és una sola i es pot desfer/refer.
    """

    def __init__(self, parent=None, abast="tot", te_acords=True,
                 te_seccions=True):
        super().__init__(parent)
        self.setWindowTitle("Quantitza")
        self.setMinimumWidth(460)
        self._te_acords = bool(te_acords)
        self._te_seccions = bool(te_seccions)
        lay = QVBoxLayout(self)
        form = QFormLayout()

        self.cb_abast = QComboBox()
        for text, clau in (("Tot (acords i estructura)", "tot"),
                           ("Només la selecció", "seleccio"),
                           ("Tot, només acords", "acords"),
                           ("Tot, només estructura", "estructura")):
            self.cb_abast.addItem(text, clau)
        i = self.cb_abast.findData(abast)
        if i >= 0:
            self.cb_abast.setCurrentIndex(i)

        self.cb_acords = QComboBox()
        for et, clau in graella.GRID_ACORDS:
            self.cb_acords.addItem(et, clau)
        self.cb_estructura = QComboBox()
        for et, clau in graella.GRID_ESTRUCTURA:
            self.cb_estructura.addItem(et, clau)
        # Valors inicials raonables: negra per a l'harmonia, 4 compassos per a
        # les frases. L'usuari els pot canviar.
        i = self.cb_acords.findData("negra")
        if i >= 0:
            self.cb_acords.setCurrentIndex(i)
        i = self.cb_estructura.findData("compas4")
        if i >= 0:
            self.cb_estructura.setCurrentIndex(i)

        form.addRow("Abast:", self.cb_abast)
        form.addRow("Graella d'acords:", self.cb_acords)
        form.addRow("Graella d'estructura:", self.cb_estructura)
        lay.addLayout(form)

        avis = QLabel("Només es mouen els INICIS dels clips. El final de cada "
                      "clip es deriva del següent i l'últim arriba a la durada "
                      "del WAV. No es toca BPM, compàs, offset ni el cru de "
                      "l'anàlisi. Tot és una sola operació de desfer.")
        avis.setWordWrap(True)
        lay.addWidget(avis)

        self.botons = QDialogButtonBox(QDialogButtonBox.Ok |
                                       QDialogButtonBox.Cancel)
        self.botons.button(QDialogButtonBox.Ok).setText("Quantitza")
        self.botons.button(QDialogButtonBox.Cancel).setText("Cancel·la")
        self.botons.accepted.connect(self.accept)
        self.botons.rejected.connect(self.reject)
        lay.addWidget(self.botons)

        self.cb_abast.currentIndexChanged.connect(self._actualitza)
        self._actualitza()

    def _actualitza(self):
        abast = self.abast()
        te_ac = abast in ("tot", "acords") or (
            abast == "seleccio" and self._te_acords)
        te_es = abast in ("tot", "estructura") or (
            abast == "seleccio" and self._te_seccions)
        self.cb_acords.setEnabled(te_ac)
        self.cb_estructura.setEnabled(te_es)
        ok = self.botons.button(QDialogButtonBox.Ok)
        if ok is not None:
            ok.setEnabled(te_ac or te_es)

    def abast(self):
        return self.cb_abast.currentData()

    def grid_acords(self):
        return self.cb_acords.currentData()

    def grid_estructura(self):
        return self.cb_estructura.currentData()


class DialegTempoMapa(QDialog):
    """Editor del mapa de **tempo i compàs** (canvis al llarg del tema).

    Cada fila és un tros que val fins a la següent: «Des de (s)», «BPM» i
    «Compàs» (`num/den`). La primera fila («Des de 0 s») és el valor inicial.
    """

    def __init__(self, parent=None, trams=None, durada=0.0):
        super().__init__(parent)
        self.setWindowTitle("Mapa de tempo i compàs")
        self.setMinimumWidth(470)
        self._durada = float(durada or 0.0)
        self._trams = tempo_map.normalitza_trams(list(trams or []),
                                                 self._durada)
        lay = QVBoxLayout(self)
        avis = QLabel(
            "El tempo i el compàs poden **canviar** al llarg del tema (com un "
            "DAW). Cada fila val fins a la següent; la primera («Des de 0 s») "
            "és el valor inicial.\nA «Des de» pots escriure **segons** (p. ex. "
            "`90`) o un **compàs** fent-ho començar per `c` (p. ex. `c33` o "
            "`c33.1`).")
        avis.setWordWrap(True)
        lay.addWidget(avis)
        self.taula = QTableWidget(0, 3)
        self.taula.setHorizontalHeaderLabels(["Des de (s)", "BPM", "Compàs"])
        self.taula.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        lay.addWidget(self.taula)
        fila = QHBoxLayout()
        b_add = QPushButton("Afegeix un canvi")
        b_del = QPushButton("Elimina")
        b_add.clicked.connect(self._afegeix)
        b_del.clicked.connect(self._elimina)
        fila.addWidget(b_add)
        fila.addWidget(b_del)
        fila.addStretch(1)
        lay.addLayout(fila)
        botons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botons.accepted.connect(self.accept)
        botons.rejected.connect(self.reject)
        lay.addWidget(botons)
        self._omple()

    # -- taula <-> trossos ----------------------------------------------
    def _omple(self):
        self.taula.setRowCount(0)
        for i, s in enumerate(self._trams):
            r = self.taula.rowCount()
            self.taula.insertRow(r)
            it0 = QTableWidgetItem("0.000" if i == 0 else f"{float(s[0]):.3f}")
            if i == 0:
                it0.setFlags(Qt.ItemIsEnabled)      # el valor inicial: fix
            self.taula.setItem(r, 0, it0)
            self.taula.setItem(r, 1, QTableWidgetItem(f"{float(s[2]):g}"))
            self.taula.setItem(r, 2,
                               QTableWidgetItem(f"{int(s[3])}/{int(s[4])}"))

    def _sync(self):
        """Llegeix la taula cap a `self._trams` (encara per normalitzar)."""
        out = []
        for r in range(self.taula.rowCount()):
            def _t(c, d):
                it = self.taula.item(r, c)
                return ((it.text().strip() if it else "") or d)
            # El PRIMER argument de `_t` és la COLUMNA (un int): abans hi
            # passaven strings ("0"/"1"/"2"), cosa que feia petar
            # `self.taula.item(r, "0")` amb TypeError — i no es capturava, així
            # que el diàleg del mapa PETAVA en afegir/eliminar un tram o en
            # prémer OK (auditoria 18-10-2026, destapat pel primer test que
            # exercita el diàleg).
            txt_ini = _t(0, "0").replace(",", ".").strip().lower()
            try:
                bpm = float(_t(1, "120").replace(",", "."))
                if r == 0:
                    ini = 0.0
                elif txt_ini.startswith("c"):
                    ini = self._temps_de_compas(txt_ini[1:])
                else:
                    ini = float(txt_ini)
            except (ValueError, IndexError):
                continue
            comp = _t(2, "4/4").replace(" ", "")
            num, den = 4, 4
            if "/" in comp:
                try:
                    a, b = comp.split("/", 1)
                    num, den = int(a), int(b)
                except ValueError:
                    num, den = 4, 4
            if bpm <= 0 or num <= 0 or den <= 0:
                continue
            out.append((ini, ini, bpm, num, den))
        if out:
            self._trams = out

    def _temps_de_compas(self, text):
        """`33` / `33.1` (compàs[.temps]) → segons, segons el mapa actual."""
        from app.tempo_map import TempoMap
        mapa = TempoMap(tempo_map.normalitza_trams(self._trams,
                                                   self._durada))
        parts = str(text).split(".")
        bar = int(parts[0])
        beat = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
        return float(mapa.t_de_pos(bar, beat))

    def _afegeix(self):
        self._sync()
        # `_sync` deixa els trams com `(ini, ini, …)` (el `fi` encara per
        # derivar): cal NORMALITZAR abans de calcular el punt mig del darrer
        # tram, o el mig ix igual que la frontera i el tall es descarta (el
        # botó «+» no feia res — auditoria 18-10-2026).
        trams = tempo_map.normalitza_trams(self._trams, self._durada)
        t = 0.0
        if trams:
            s = trams[-1]
            t = (float(s[0]) + float(s[1])) / 2.0
        self._trams = tempo_map.normalitza_trams(
            tempo_map.afegeix_tall(trams, t), self._durada)
        self._omple()

    def _elimina(self):
        r = self.taula.currentRow()
        if r <= 0:                               # no es toca el valor inicial
            return
        self._sync()
        self._trams = tempo_map.normalitza_trams(
            tempo_map.elimina_tall(self._trams, r), self._durada)
        self._omple()

    def trams(self):
        """Els trossos editats (`(ini, fi, bpm, num, den)`, contigus)."""
        self._sync()
        return tempo_map.normalitza_trams(self._trams, self._durada)


class DialegTramTempo(QDialog):
    """Edita un **tros** del mapa: BPM i compàs (on comença es mostra)."""

    def __init__(self, parent=None, inici=0.0, bpm=120.0, num=4, den=4,
                 inicial=False, text_inici=None):
        super().__init__(parent)
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
        self.sp_bpm.setRange(1.0, 1000.0)
        self.sp_bpm.setDecimals(3)
        self.sp_bpm.setValue(float(bpm))
        self.ed_compas = QLineEdit(f"{int(num)}/{int(den)}")
        self.ed_compas.setPlaceholderText("4/4")
        form.addRow("BPM:", self.sp_bpm)
        form.addRow("Compàs:", self.ed_compas)
        lay.addLayout(form)
        botons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botons.accepted.connect(self.accept)
        botons.rejected.connect(self.reject)
        lay.addWidget(botons)

    def valors(self):
        """`(bpm, num, den)`; el compàs s'escriu «num/den» (o «num»)."""
        num, den = 4, 4
        txt = (self.ed_compas.text() or "").strip().replace(" ", "")
        if "/" in txt:
            try:
                a, b = txt.split("/", 1)
                num, den = int(a), int(b)
            except ValueError:
                num, den = 4, 4
        elif txt.isdigit():
            num = int(txt)
        return (float(self.sp_bpm.value()), max(1, num), max(1, den))


# ---------------------------------------------------------------------------
# Anàlisi guiat (docs/ANALISI_GUIAT.md)
# ---------------------------------------------------------------------------
class DialegGuiaDownbeat(QDialog):
    """Pas 1 de l'«Anàlisi guiat»: marcar el downbeat (compàs 1).

    MODELESS (s'obre amb `show()`, no amb `exec_()`): l'usuari ha de poder
    moure el cursor del visor mentre el diàleg és obert. Enter = Fet.
    """

    #: mides de tram oferides (compassos). La 1a és la de defecte.
    MIDA_TRAM = (4, 8, 16, 32)

    def __init__(self, parent=None, compassos=4, confirma=True):
        super().__init__(parent)
        self.setWindowTitle("Anàlisi guiat — pas 1: el compàs 1")
        self.setMinimumWidth(480)
        lay = QVBoxLayout(self)
        txt = QLabel(
            "1 · Poseu el cursor a la <b>primera marca del tema</b> "
            "(el primer cop sec, on comença el compte).<br>"
            "2 · Premeu <b>Fet (Enter)</b> aquí sota.<br><br>"
            "El guiat posarà l'offset del compàs 1 al cursor, farà un tall "
            "lliure del carril de tempo en aquell punt i seguirà amb la "
            "detecció del BPM finestra a finestra.")
        txt.setWordWrap(True)
        txt.setTextFormat(Qt.RichText)
        lay.addWidget(txt)
        # ── com es fa el procés (es recorda entre sessions) ──
        fila = QHBoxLayout()
        fila.addWidget(QLabel("Cada tram:"))
        self.cb_compassos = QComboBox()
        for m in self.MIDA_TRAM:
            self.cb_compassos.addItem(f"{m} compassos", m)
        m = int(compassos or 4)
        idx = self.cb_compassos.findText(f"{m} compassos")
        if idx < 0:
            self.cb_compassos.addItem(f"{m} compassos", m)
            idx = self.cb_compassos.count() - 1
        self.cb_compassos.setCurrentIndex(idx)
        self.cb_compassos.setToolTip(
            "Quants compassos per tram es detecten (i s'apliquen). Com més "
            "llarg és el tram, més estable és la mesura del BPM, però el mapa "
            "té menys punts per a seguir un rubato.")
        fila.addWidget(self.cb_compassos)
        fila.addStretch(1)
        lay.addLayout(fila)
        self.ck_confirma = QCheckBox(
            "Confirma amb el BPM del tram anterior i un tros llarg")
        self.ck_confirma.setChecked(bool(confirma))
        self.ck_confirma.setToolTip(
            "Fa dues mesures més del mateix tram: una acotada al ±8 % del BPM "
            "que vas posar al tram anterior i una altra sobre el doble de "
            "tros. Si les tres coincidixen, el BPM ix «fiable»; si no, "
            "«dubtós» i tries tu.")
        lay.addWidget(self.ck_confirma)
        botons = QDialogButtonBox(QDialogButtonBox.Ok
                                  | QDialogButtonBox.Cancel)
        botons.button(QDialogButtonBox.Ok).setText("Fet (Enter)")
        botons.button(QDialogButtonBox.Ok).setDefault(True)
        botons.button(QDialogButtonBox.Cancel).setText("Cancel·la el guiat")
        botons.accepted.connect(self.accept)
        botons.rejected.connect(self.reject)
        lay.addWidget(botons)

    def compassos(self):
        """Compàsos per tram triats per a tot el guiat (int)."""
        d = self.cb_compassos.currentData()
        return int(d) if d else 4

    def confirma(self):
        """`True` si vol la doble comprovació (tram anterior + tros llarg)."""
        return bool(self.ck_confirma.isChecked())


class DialegGuiaBpm(QDialog):
    """Pas 2 de l'«Anàlisi guiat»: confirmar el BPM d'una finestra.

    S'obre MODELESS amb el camp de BPM deshabilitat mentre el fil de detecció
    treballa; quan arriba el resultat, el camp s'omple i es pot editar (o
    duplicar/partir amb ×2/÷2). Enter = Accepta; tancar = Cancel·la el guiat.
    """

    BPM_MIN, BPM_MAX = 20.0, 300.0

    #: l'usuari ha canviat el BPM (teclat, ràtio, pastilla o TAP) → el
    #: metrònom de l'audició s'ha de moure a l'instant.
    bpm_canviat = pyqtSignal(float)
    #: play/pausa del bucle del tram sense tancar el diàleg (botó o Espai).
    vol_reproduir = pyqtSignal()

    #: compassos del tram oferits (l'usuari els pot pujar/baixar)
    COMPASSOS_MIN, COMPASSOS_MAX = 1, 32
    #: mides de tram del procés (docs/ANALISI_GUIAT.md §4.3)
    MIDA_TRAM = (4, 8, 16, 32)
    #: si passa més d'això entre dos TAPs, s'hi comença de nou
    TAP_REINICI_S = 2.5
    TAP_MAX = 6

    def __init__(self, parent, n_tram, t_ini, t_fi, etiqueta_ini="",
                 nota="", ref=None, rang=None, num=4, den=4, compassos=4):
        super().__init__(parent)
        self._cands = []
        self._avis = ""
        self._ref = ref
        self._rang = rang
        self._m = max(self.COMPASSOS_MIN,
                      min(self.COMPASSOS_MAX, int(compassos or 4)))
        self._num, self._den = int(num), int(den)
        self._taps = []
        self._reproduint = False
        self.setWindowTitle(f"Anàlisi guiat — tram {int(n_tram)}")
        self.setMinimumWidth(480)
        lay = QVBoxLayout(self)
        lbl = QLabel(
            f"Tram {int(n_tram)} · des de {etiqueta_ini or '—'} "
            f"({float(t_ini):.3f}s) fins a {float(t_fi):.3f}s "
            f"({float(t_fi) - float(t_ini):.1f}s de finestra)")
        lbl.setWordWrap(True)
        lay.addWidget(lbl)
        if nota:
            self.lb_nota = QLabel(str(nota))
            self.lb_nota.setWordWrap(True)
            self.lb_nota.setObjectName("secundari")
            lay.addWidget(self.lb_nota)
        form = QFormLayout()
        self.ed_bpm = QLineEdit()
        self.ed_bpm.setEnabled(False)
        self.ed_bpm.setPlaceholderText("detectant…")
        self.ed_bpm.textEdited.connect(self._bpm_escrit)
        form.addRow("BPM del tram:", self.ed_bpm)
        lay.addLayout(form)

        # ── mètrica i llargada del tram (contracte de compassos enters) ──
        fila_m = QHBoxLayout()
        fila_m.addWidget(QLabel("Compàs:"))
        self.cb_metrica = QComboBox()
        for n_, d_ in ((4, 4), (3, 4), (2, 4), (6, 8), (12, 8)):
            self.cb_metrica.addItem(f"{n_}/{d_}", (n_, d_))
        # si la mètrica vigent no és cap preset, s'afegeix (no es perd res)
        # per TEXT: `findData` amb una tupla no casa mai a PyQt5 i afegia
        # un «4/4» duplicat al desplegable (vist 21-10).
        idx = self.cb_metrica.findText(f"{self._num}/{self._den}")
        if idx < 0:
            self.cb_metrica.addItem(f"{self._num}/{self._den}",
                                    (self._num, self._den))
            idx = self.cb_metrica.count() - 1
        self.cb_metrica.setCurrentIndex(idx)
        self.cb_metrica.setToolTip(
            "Mètrica del tram. Canviar-la recalcula la llargada perquè siguen "
            "compassos SENCERS (la graella no accepta mig compàs).")
        fila_m.addWidget(self.cb_metrica)
        fila_m.addSpacing(12)
        fila_m.addWidget(QLabel("Tram:"))
        self.cb_compassos = QComboBox()
        for m in self.MIDA_TRAM:
            self.cb_compassos.addItem(f"{m} compassos", m)
        self.cb_compassos.setToolTip(
            "Compàsos per tram. Com més llarg, més estable la mesura del BPM "
            "i menys punts per a seguir un rubato. Es recorda per al guiat "
            "següent.")
        self.cb_compassos.currentIndexChanged.connect(
            lambda _i: self._estableix_compassos(
                self.cb_compassos.currentData()))
        fila_m.addWidget(self.cb_compassos)
        fila_m.addSpacing(12)
        self.b_menys = QPushButton("−1 compàs")
        self.b_menys.setToolTip("Escurça el tram un compàs")
        self.b_menys.clicked.connect(lambda: self._canvia_compassos(-1))
        self.b_mes = QPushButton("+1 compàs")
        self.b_mes.setToolTip("Allarga el tram un compàs")
        self.b_mes.clicked.connect(lambda: self._canvia_compassos(+1))
        self.lb_compassos = QLabel("")
        self.lb_compassos.setMinimumWidth(110)
        self.lb_compassos.setAlignment(Qt.AlignCenter)
        fila_m.addWidget(self.b_menys)
        fila_m.addWidget(self.lb_compassos)
        fila_m.addWidget(self.b_mes)
        fila_m.addStretch(1)
        lay.addLayout(fila_m)
        self._pinta_compassos()

        self.lb_estat = QLabel("Detectant el BPM del tram…")
        lay.addWidget(self.lb_estat)
        fila = QHBoxLayout()
        self.b_x2 = QPushButton("×2 (doblega)")
        self.b_x2.clicked.connect(lambda: self._escala(2.0))
        self.b_mig = QPushButton("÷2 (mig temps)")
        self.b_mig.clicked.connect(lambda: self._escala(0.5))
        self.b_x43 = QPushButton("×4/3")
        self.b_x43.setToolTip("Tresets: el pols és un terç més lent")
        self.b_x43.clicked.connect(lambda: self._escala(4.0 / 3.0))
        self.b_x34 = QPushButton("×3/4")
        self.b_x34.setToolTip("Tresets: el pols és un quart més ràpid")
        self.b_x34.clicked.connect(lambda: self._escala(3.0 / 4.0))
        for b in (self.b_x2, self.b_mig, self.b_x43, self.b_x34):
            b.setEnabled(False)
            fila.addWidget(b)
        fila.addStretch(1)
        lay.addLayout(fila)
        # Alternatives de la detecció (com les 5 propostes de Logic)
        self._fila_cand = QHBoxLayout()
        self.lb_cand = QLabel("Altres:")
        self.lb_cand.setObjectName("secundari")
        self._fila_cand.addWidget(self.lb_cand)
        self._b_cand = []
        for k in range(3):
            b = QPushButton("")
            b.setVisible(False)
            b.clicked.connect(lambda _c=False, i=k: self._tria_candidat(i))
            self._fila_cand.addWidget(b)
            self._b_cand.append(b)
        self._fila_cand.addStretch(1)
        lay.addLayout(self._fila_cand)
        self.lb_cand.setVisible(False)
        # BPM que l'usuari ja va confirmar en trams anteriors (pastilles)
        self._hist = []
        self._fila_hist = QHBoxLayout()
        self.lb_hist = QLabel("Tram anterior:")
        self.lb_hist.setObjectName("secundari")
        self._fila_hist.addWidget(self.lb_hist)
        self._b_hist = []
        for k in range(2):
            b = QPushButton("")
            b.setVisible(False)
            b.setToolTip("Posa este BPM al camp (el vas confirmar abans)")
            b.clicked.connect(lambda _c=False, i=k: self._tria_hist(i))
            self._fila_hist.addWidget(b)
            self._b_hist.append(b)
        self._fila_hist.addStretch(1)
        lay.addLayout(self._fila_hist)
        self.lb_hist.setVisible(False)
        self.lb_ref = QLabel("")
        self.lb_ref.setObjectName("secundari")
        self.lb_ref.setVisible(False)
        lay.addWidget(self.lb_ref)
        # resultat de la doble comprovació (tram anterior + tros llarg)
        self.lb_confirma = QLabel("")
        self.lb_confirma.setObjectName("secundari")
        self.lb_confirma.setWordWrap(True)
        self.lb_confirma.setVisible(False)
        lay.addWidget(self.lb_confirma)
        if ref:
            self._mostra_ref(ref)
        fila_tap = QHBoxLayout()
        self.b_repro = QPushButton("▶ Escolta el tram")
        self.b_repro.setToolTip("Reproduir/aturar el bucle del tram amb el "
                                "metrònom (Espai)")
        self.b_repro.clicked.connect(self.vol_reproduir.emit)
        fila_tap.addWidget(self.b_repro)
        fila_tap.addSpacing(12)
        self.b_tap = QPushButton("TAP")
        self.b_tap.setToolTip("Marcar el pols amb la tecla T o 0 (2–6 cops)")
        self.b_tap.clicked.connect(self._tap)
        fila_tap.addWidget(self.b_tap)
        self.lb_tap = QLabel("")
        self.lb_tap.setObjectName("secundari")
        fila_tap.addWidget(self.lb_tap)
        fila_tap.addStretch(1)
        lay.addLayout(fila_tap)

        botons = QDialogButtonBox(QDialogButtonBox.Ok
                                  | QDialogButtonBox.Cancel)
        self.b_ok = botons.button(QDialogButtonBox.Ok)
        self.b_ok.setText("Accepta (Enter)")
        self.b_ok.setDefault(True)
        self.b_ok.setEnabled(False)
        botons.button(QDialogButtonBox.Cancel).setText("Cancel·la el guiat")
        botons.accepted.connect(self.accept)
        botons.rejected.connect(self.reject)
        lay.addWidget(botons)

    # --- API per a l'orquestrador (main.Finestra) --------------------------
    def mostra_bpm(self, bpm, candidats=None, alternatives=None, ref=None,
                   hist=None):
        """Resultat de la detecció: omple el camp i ofereix alternatives.

        `candidats` = `[(bpm, fiabilitat), …]` (el primer és el detectat),
        `alternatives` = els que queden **fora** del rang configurat i
        `hist` = `[(n_tram, bpm), …]` els BPM confirmats en trams anteriors.
        """
        self._mostra_candidats(candidats, alternatives)
        self._mostra_hist(hist)
        if ref:
            self._mostra_ref(ref)
            self._ref = float(ref)
        if bpm is None:
            self.mostra_error(
                "No s'ha pogut detectar el BPM del tram. Escriu-lo a mà "
                "(o cancel·la el guiat).")
            return
        self.ed_bpm.setText(f"{float(bpm):.2f}")
        self.ed_bpm.setEnabled(True)
        self.b_ok.setEnabled(True)
        for b in (self.b_x2, self.b_mig, self.b_x43, self.b_x34):
            b.setEnabled(True)
        self.ed_bpm.setFocus()
        self.ed_bpm.selectAll()
        extra = ""
        if self._ref:
            extra = (" Prem una alternativa si el tema sencer "
                     f"({float(self._ref):.2f}) és més de fiar.")
        txt = ("Revisa el BPM: Enter per acceptar, ×2/÷2/×4/3 per corregir, "
               "o edita'l a mà." + extra)
        if self._avis:
            txt += " · " + self._avis
        self.lb_estat.setText(txt)

    def _mostra_candidats(self, candidats, alternatives):
        """Omple els botons d'alternatives (sense duplicar el detectat)."""
        self._cands = list(candidats or [])
        altres = self._cands[1:4]
        for i, b in enumerate(self._b_cand):
            if i < len(altres):
                v, conf = altres[i]
                b.setText(f"{float(v):.2f} ({float(conf) * 100:.0f} %)")
                b.setToolTip(f"Candidat alternatiu: {float(v):.2f} BPM "
                             f"(fiabilitat {float(conf) * 100:.0f} %)")
                b.setVisible(True)
            else:
                b.setVisible(False)
        self.lb_cand.setVisible(bool(altres))
        avis = ""
        if alternatives:
            avis = ("⚠️ Fora del rang configurat: "
                    + ", ".join(f"{float(v):.2f}" for v, _c in alternatives[:3])
                    + " BPM. Si el tema va per ahí, canvia el rang a "
                      "Opcions → BPM.")
        self._avis = avis
        if avis:
            self.lb_estat.setStyleSheet("color: #b26a00;")

    def _mostra_ref(self, ref):
        """Etiqueta amb el BPM del tema sencer (referència del guiat)."""
        self.lb_ref.setText(f"Referència del tema sencer: {float(ref):.2f} BPM")
        self.lb_ref.setVisible(True)

    def _tria_candidat(self, i):
        """Clic en una alternativa: la posa al camp (sense acceptar)."""
        altres = self._cands[1:4]
        if i >= len(altres):
            return
        self.ed_bpm.setText(f"{float(altres[i][0]):.2f}")
        self.ed_bpm.setFocus()
        self.ed_bpm.selectAll()
        self._emet_bpm()

    def mostra_error(self, text):
        """La detecció ha fallat: permet l'edició manual del BPM."""
        self.ed_bpm.setEnabled(True)
        self.b_ok.setEnabled(True)
        self.ed_bpm.setFocus()
        self.lb_estat.setText(text)

    def detectant(self):
        """`True` mentre el fil de detecció no ha arribat."""
        return not self.ed_bpm.isEnabled()

    def accept(self):
        """Enter mentre encara es detecta → no accepta res."""
        if self.detectant():
            return
        super().accept()

    def valors(self):
        """BPM confirmat (float) o `None` si el camp no té un valor vàlid."""
        txt = (self.ed_bpm.text() or "").strip().replace(",", ".")
        try:
            bpm = float(txt)
        except ValueError:
            return None
        if not (self.BPM_MIN <= bpm <= self.BPM_MAX):
            return None
        return bpm

    def _escala(self, f):
        if not self.ed_bpm.isEnabled():
            return
        v = self.valors()
        if v is None:
            return
        v = min(self.BPM_MAX, max(self.BPM_MIN, v * float(f)))
        self.ed_bpm.setText(f"{v:.2f}")
        self._emet_bpm()

    # --- mètrica i llargada del tram ---------------------------------------
    def metrica(self):
        """`(num, den)` triats al desplegable."""
        d = self.cb_metrica.currentData()
        return (int(d[0]), int(d[1])) if d else (self._num, self._den)

    def compassos(self):
        """Nombre de compassos triat per al tram (≥1)."""
        return int(self._m)

    def _etiqueta_compassos(self, m=None):
        m = self._m if m is None else int(m)
        return f"{m} compàs" if m == 1 else f"{m} compassos"

    def _pinta_compassos(self):
        self.lb_compassos.setText(self._etiqueta_compassos())
        self.b_menys.setEnabled(self._m > self.COMPASSOS_MIN)
        self.b_mes.setEnabled(self._m < self.COMPASSOS_MAX)
        cb = getattr(self, "cb_compassos", None)
        if cb is None:
            return
        txt = self._etiqueta_compassos()
        # ⚠️ `removeItem` de l'element que és l'actual fa canviar
        # `currentIndex` i EMET el senyal: si no està blocat, el lambda del
        # combo re-escriu `_m` amb el valor del veí (bug del 21-10: el comptador
        # saltava a 32 i no baixava mai).
        previ = cb.blockSignals(True)
        try:
            idx = cb.findText(txt)
            if idx < 0:
                # valor fi (p. ex. 6) que no és cap preset: s'afig al final
                if cb.count() > len(self.MIDA_TRAM):
                    cb.removeItem(cb.count() - 1)
                cb.addItem(txt, self._m)
                idx = cb.count() - 1
            cb.setCurrentIndex(idx)
        finally:
            cb.blockSignals(previ)

    def _estableix_compassos(self, m):
        """Fixar la mida del tram (combo de presets o ±1)."""
        if m is None:
            return
        self._m = max(self.COMPASSOS_MIN, min(self.COMPASSOS_MAX, int(m)))
        self._pinta_compassos()

    def _canvia_compassos(self, delta):
        self._estableix_compassos(self._m + int(delta))

    # --- història de BPM i confirmació -------------------------------------
    def _mostra_hist(self, hist=None):
        """Pastilles amb els BPM confirmats en trams anteriors."""
        self._hist = list(hist or [])
        for k, b in enumerate(self._b_hist):
            if k < len(self._hist):
                n_tram, bpm = self._hist[k]
                b.setText(f"tram {int(n_tram)} · {float(bpm):.2f}")
                b.setVisible(True)
            else:
                b.setText("")
                b.setVisible(False)
        self.lb_hist.setVisible(bool(self._hist))

    def _tria_hist(self, i):
        """Clic en un BPM anterior: al camp (sense acceptar)."""
        if i >= len(self._hist):
            return
        bpm = float(self._hist[i][1])
        self.ed_bpm.setEnabled(True)
        self.b_ok.setEnabled(True)
        for b in (self.b_x2, self.b_mig, self.b_x43, self.b_x34):
            b.setEnabled(True)
        self.ed_bpm.setText(f"{bpm:.2f}")
        self.ed_bpm.setFocus()
        self.ed_bpm.selectAll()
        self._emet_bpm()

    def set_confirmacio(self, res):
        """Ensenya el veredicte de `tempo_map.avalua_confirmacio`."""
        txt = (res or {}).get("detall") or ""
        self.lb_confirma.setText(txt)
        self.lb_confirma.setVisible(bool(txt))
        self.lb_confirma.setToolTip(
            "Es compara la detecció lliure amb (a) la mateixa finestra "
            "acotada al ±8 % del BPM del tram anterior i (b) el doble de "
            "tros. Si coincidixen, el número és de fiar.")

    # --- TAP i audició -----------------------------------------------------
    def _bpm_escrit(self, _txt):
        self._emet_bpm()

    def _emet_bpm(self):
        """Avisa l'orquestrador del BPM vigent (metrònom en viu)."""
        v = self.valors()
        if v is not None:
            self.bpm_canviat.emit(float(v))

    def _tap(self, *_a):
        """Marcar el pols: 2–6 cops → BPM per la mediana dels intervals."""
        ara = time.monotonic()
        if self._taps and ara - self._taps[-1] > self.TAP_REINICI_S:
            self._taps = []
        self._taps.append(ara)
        if len(self._taps) > self.TAP_MAX:
            del self._taps[0]
        self.b_tap.setText(f"TAP ({len(self._taps)})")
        if len(self._taps) < 2:
            self.lb_tap.setText("marca el pols…")
            return
        intervals = sorted(b - a for a, b in zip(self._taps, self._taps[1:]))
        mitja = intervals[len(intervals) // 2]       # mediana: menys outliers
        if mitja <= 0:
            return
        bpm = min(self.BPM_MAX, max(self.BPM_MIN, 60.0 / mitja))
        self.ed_bpm.setEnabled(True)
        self.b_ok.setEnabled(True)
        for b in (self.b_x2, self.b_mig, self.b_x43, self.b_x34):
            b.setEnabled(True)
        self.ed_bpm.setText(f"{bpm:.2f}")
        self.lb_tap.setText(f"→ {bpm:.1f} BPM")
        self._emet_bpm()

    def set_reproduint(self, sona):
        """Sincronitza el text del botó amb l'estat real de reproducció."""
        self._reproduint = bool(sona)
        self.b_repro.setText("⏸ Pausa (Espai)" if self._reproduint
                             else "▶ Escolta el tram")

    def keyPressEvent(self, ev):
        # T = TAP i Espai = play/pausa, sempre que no s'estiga escrivint al
        # camp del BPM (allà una «t» o un espai han de poder entrar).
        editant = isinstance(self.focusWidget(), QLineEdit)
        if not editant and ev.key() in (Qt.Key_T, Qt.Key_0):
            self._tap()
            return
        if not editant and ev.key() == Qt.Key_Space:
            self.vol_reproduir.emit()
            return
        super().keyPressEvent(ev)


class DialegTempoPerTrams(QDialog):
    """«Detecta el tempo per trams»: mapa de BPM cada N compassos.

    És l'acció automàtica per a cançons amb **tempo variable**: es detecta un
    BPM cada `cada` compassos (per defecte 4) i les fronteres cauen sempre en
    una línia de compàs. Els veïns amb un BPM quasi igual es fusionen.
    """

    def __init__(self, parent, durada=0.0, num=4, den=4, cada=4,
                 tolerancia=2, offset_auto=True):
        super().__init__(parent)
        self.setWindowTitle("Detecta el tempo per trams")
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        exp = QLabel(
            "Analitza els temps de la cançó i crea un tram de BPM cada pocs "
            "compassos. Pensat per a temes amb tempo variable (directes, "
            "ritardandos, canvis de secció).")
        exp.setWordWrap(True)
        lay.addWidget(exp)
        form = QFormLayout()
        self.sp_cada = QSpinBox()
        self.sp_cada.setRange(1, 64)
        self.sp_cada.setValue(max(1, int(cada)))
        self.sp_cada.setSuffix(" compassos")
        self.sp_cada.setToolTip(
            "Cada quants compassos es mesura un BPM nou. 4 és un bon equilibri "
            "entre precisió i nombre de trams.")
        form.addRow("Nova mesura cada:", self.sp_cada)
        self.sp_tol = QDoubleSpinBox()
        self.sp_tol.setRange(0.0, 10.0)
        self.sp_tol.setDecimals(1)
        self.sp_tol.setSingleStep(0.5)
        self.sp_tol.setValue(float(tolerancia))
        self.sp_tol.setSuffix(" %")
        self.sp_tol.setToolTip(
            "Els trams veïns amb menys diferència de BPM es fusionen en un de "
            "sol (evita mapes de mil trams per vibrato o micro-deriva).")
        form.addRow("Fusiona si el BPM difereix menys de:", self.sp_tol)
        lay.addLayout(form)
        self.ck_offset = QCheckBox(
            "Mou el compàs 1 al primer temps detectat (recomanat)")
        self.ck_offset.setChecked(bool(offset_auto))
        self.ck_offset.setToolTip(
            "Si la cançó comença amb anacrusi o silenci, el compàs 1 no cau a "
            "0 s: es col·loca al primer temps fort detectat.")
        lay.addWidget(self.ck_offset)
        self.lb_info = QLabel(
            f"Durada del tema: {float(durada):.2f}s · compàs {int(num)}/"
            f"{int(den)}")
        self.lb_info.setObjectName("secundari")
        lay.addWidget(self.lb_info)
        botons = QDialogButtonBox(QDialogButtonBox.Ok
                                  | QDialogButtonBox.Cancel)
        botons.button(QDialogButtonBox.Ok).setText("Detecta")
        botons.button(QDialogButtonBox.Ok).setDefault(True)
        botons.button(QDialogButtonBox.Cancel).setText("Cancel·la")
        botons.accepted.connect(self.accept)
        botons.rejected.connect(self.reject)
        lay.addWidget(botons)

    def valors(self):
        """`(cada_compassos, tolerancia_fraccio, offset_auto)`."""
        return (int(self.sp_cada.value()),
                float(self.sp_tol.value()) / 100.0,
                bool(self.ck_offset.isChecked()))
