"""Diàleg d'opcions de l'autodetecció (BPM / Acords / Estructura).

S'obre en clicar `🎯 Detecta` (pestanya BPM) o `Analitza` (pestanya Acords).
Els controls de la pestanya **Acords** es construeixen **dinàmicament** a
partir del descriptor `.n3` del Chordino (vegeu `app/vamp_params.py`), així
que si el plugin canvia, el diàleg s'adapta sol.

Tot en català.
"""

import json

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout,
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
              "reduir": False, "snap": True, "divisio": 2, "ritme": "off"},
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
        return w

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
        s = _spin(1, 4, 1, dnet.get("divisio", 1), 0)
        s.setToolTip("Subdivisions per temps on encaixar (1 = temps).")
        self._controls["clean"]["divisio"] = s
        fn.addRow(QLabel("Subdivisions per temps"), s)
        cb = QComboBox()
        for clau in ("off", "auto", "compas", "mig", "temps"):
            cb.addItem("Desactivat" if clau == "off"
                       else graella.ETIQUETES[clau], clau)
        i = cb.findData(dnet.get("ritme", "off"))
        if i >= 0:
            cb.setCurrentIndex(i)
        cb.setToolTip("Mode fàcil: re-deriva els acords de l'anàlisi CRUA a la "
                      "graella (un acord per cel·la) en analitzar.")
        self._controls["clean"]["ritme"] = cb
        fn.addRow(QLabel("Ritme harmònic (mode fàcil)"), cb)
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
        cl["ritme"].setCurrentIndex(max(0, cl["ritme"].findData(
            dc.get("ritme", "off"))))

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
            "ritme": cl["ritme"].currentData(),
        }
        return {"bpm": bpm, "chords": chords, "structure": est, "clean": clean}


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


class DialegModeFacil(QDialog):
    """Mode fàcil: preset d'estil + ritme harmònic + mòdul d'estructura."""

    def __init__(self, parent=None, preset="auto"):
        super().__init__(parent)
        self.setWindowTitle("Mode fàcil")
        self.setMinimumWidth(430)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.cb_preset = QComboBox()
        for clau, p in graella.PRESETS.items():
            self.cb_preset.addItem(p["etiqueta"], clau)
        if preset in graella.PRESETS:
            self.cb_preset.setCurrentIndex(list(graella.PRESETS).index(preset))
        self.cb_ritme = QComboBox()
        for clau in ("auto", "compas", "mig", "temps"):
            self.cb_ritme.addItem(graella.ETIQUETES[clau], clau)
        self.cb_modul = QComboBox()
        for v, et in ((0, "No tocar-ne els talls"), (1, "1 compàs"),
                      (2, "2 compassos"), (4, "4 compassos (blocs)"),
                      (8, "8 compassos"), (12, "12 compassos (blues)")):
            self.cb_modul.addItem(et, v)
        form.addRow("Preset d'estil:", self.cb_preset)
        form.addRow("Ritme harmònic:", self.cb_ritme)
        form.addRow("Estructura en blocs de:", self.cb_modul)
        lay.addLayout(form)
        avis = QLabel("Re-deriva els acords de l'anàlisi CRUA, els encaixa al "
                      "ritme harmònic i ajusta els talls de secció als blocs. "
                      "Tot és editable i es pot desfer.")
        avis.setWordWrap(True)
        lay.addWidget(avis)
        botons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botons.accepted.connect(self.accept)
        botons.rejected.connect(self.reject)
        lay.addWidget(botons)
        self.cb_preset.currentIndexChanged.connect(self._aplica_preset)
        self._aplica_preset()

    def _aplica_preset(self):
        p = graella.PRESETS.get(self.cb_preset.currentData())
        if not p:
            return
        i = self.cb_ritme.findData(p.get("ritme", "auto"))
        if i >= 0:
            self.cb_ritme.setCurrentIndex(i)
        j = self.cb_modul.findData(int(p.get("modul", 4)))
        if j >= 0:
            self.cb_modul.setCurrentIndex(j)

    def preset(self):
        return self.cb_preset.currentData()

    def ritme(self):
        return self.cb_ritme.currentData()

    def modul(self):
        return int(self.cb_modul.currentData())


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
            it0 = QTableWidgetItem("0.00" if i == 0 else f"{float(s[0]):.2f}")
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
            txt_ini = _t("0", "0").replace(",", ".").strip().lower()
            try:
                bpm = float(_t("1", "120").replace(",", "."))
                if r == 0:
                    ini = 0.0
                elif txt_ini.startswith("c"):
                    ini = self._temps_de_compas(txt_ini[1:])
                else:
                    ini = float(txt_ini)
            except (ValueError, IndexError):
                continue
            comp = _t("2", "4/4").replace(" ", "")
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
        t = 0.0
        if self._trams:
            s = self._trams[-1]
            t = (float(s[0]) + float(s[1])) / 2.0
        self._trams = tempo_map.normalitza_trams(
            tempo_map.afegeix_tall(self._trams, t), self._durada)
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
            cap = f"Comença a {float(inici):.2f} s"
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
