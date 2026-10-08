"""Diàleg d'opcions de l'autodetecció (BPM / Acords / Estructura).

S'obre en clicar `🎯 Detecta` (pestanya BPM) o `Analitza` (pestanya Acords).
Els controls de la pestanya **Acords** es construeixen **dinàmicament** a
partir del descriptor `.n3` del Chordino (vegeu `app/vamp_params.py`), així
que si el plugin canvia, el diàleg s'adapta sol.

Tot en català.
"""

import json
import os

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QGroupBox, QLabel, QPushButton, QTabWidget, QVBoxLayout,
)

from app import config, postproc, tempo, vamp_params

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

DEFECTES = {
    # Els valors dels ACORDS son els del descriptor del plugin (buit = defecte).
    "chords": {},
    "bpm": {
        "motor": "nostre",
        "min": tempo.BPM_MIN, "max": tempo.BPM_MAX,
        "pref_min": tempo.BPM_PREFERIT[0], "pref_max": tempo.BPM_PREFERIT[1],
    },
    "structure": {"motor": "qm", "durada_min": 0.0,
                  "fusiona_iguals": True},
    # Neteja posterior dels acords (post-processat, app/postproc.py)
    "clean": {"durada_min": 0.0, "fusiona_iguals": True, "sense_baix": False,
              "reduir": False, "snap": False, "divisio": 1},
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
        s.setToolTip("Elimina els acords que duren menys d'aquesta estona.")
        self._controls["clean"]["durada_min"] = s
        fn.addRow(QLabel("Durada mínima d'un acord (s)"), s)
        c = _checkbox(dnet.get("snap", False))
        c.setToolTip("Mou l'inici de cada acord a la graella (BPM/compàs).")
        self._controls["clean"]["snap"] = c
        fn.addRow(QLabel("Encaixar a la graella"), c)
        s = _spin(1, 4, 1, dnet.get("divisio", 1), 0)
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
        f.addRow(QLabel("Durada mínima d'una secció (s)"), s)
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
        for clau, w in self._controls["bpm"].items():
            if clau != "motor":
                w.setValue(float(DEFECTES["bpm"][clau]))
        for p in vamp_params.params_de("chords"):
            w = self._controls["chords"][p["id"]]
            if isinstance(w, QCheckBox):
                w.setChecked(bool(p["defecte"]))
            elif isinstance(w, QComboBox):
                w.setCurrentIndex(int(p["defecte"]))
            else:
                w.setValue(float(p["defecte"]))
        self._controls["bpm"]["motor"].setCurrentIndex(
            self._controls["bpm"]["motor"].findData("nostre"))
        self._controls["structure"]["durada_min"].setValue(0.0)
        self._controls["structure"]["fusiona_iguals"].setChecked(True)
        cl = self._controls["clean"]
        cl["sense_baix"].setChecked(False)
        cl["reduir"].setChecked(False)
        cl["fusiona_iguals"].setChecked(True)
        cl["durada_min"].setValue(0.0)
        cl["snap"].setChecked(False)
        cl["divisio"].setValue(1)

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
        return {"bpm": bpm, "chords": chords, "structure": est, "clean": clean}
