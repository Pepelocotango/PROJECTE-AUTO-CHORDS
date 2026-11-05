"""Diàleg d'opcions de l'autodetecció (BPM / Acords / Estructura).

S'obre en clicar `🎯 Detecta` (pestanya BPM) o `Analitza` (pestanya Acords).
Els controls de la pestanya **Acords** es construeixen **dinàmicament** a
partir del descriptor `.n3` del Chordino (vegeu `app/vamp_params.py`), així
que si el plugin canvia, el diàleg s'adapta sol.

Tot en català.
"""

import json
import math

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSlider,
    QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout,
    QWidget,
)

from app import bpm_unit, config, graella, limits, tempo, tempo_map, vamp_params

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
    # QUÈ fa «Analitza»: cada etapa es pot activar/desactivar per separat
    # (BPM · acords · estructura). El que està desactivat NO es toca: es
    # conserva el que ja hi ha al model. Decisió de l'operador (21-10-2026):
    # per defecte les tres ACTIVADES — «Analitza» detecta també el BPM.
    "analisi": {"bpm": True, "acords": True, "estructura": True},
}

# Valors per defecte de l'acció separada «Analitza BPM». No formen part del
# diàleg d'anàlisi d'acords/estructura: són una acció independent.
BEATS_DEFECTES = {"motor": "nostre", "sensibilitat": 50,
                  "mode": "beats", "aplica_bpm": True}



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
    def _casella_etapa(self, clau, text, tooltip, nota):
        """Capçalera comuna de cada pestanya: què s'analitza (sí/no).

        És la font ÚNICA de `opcions["analisi"]` (una entrada per etapa) i el
        que decideix què fa «Analitza»: el que està desactivat es conserva.
        """
        ana = QGroupBox("Què s'analitza")
        lay = QVBoxLayout(ana)
        c = QCheckBox(text)
        c.setToolTip(tooltip)
        c.setChecked(bool((self._base.get("analisi") or {}).get(clau, True)))
        lay.addWidget(c)
        lb = QLabel(nota)
        lb.setWordWrap(True)
        lb.setStyleSheet("color:#9aa6b8; font-size:11px;")
        lay.addWidget(lb)
        setattr(self, "_cb_" + clau, c)
        return ana

    def _lliga_etapa(self, clau, w):
        """La casella de l'etapa habilita/deshabilita els seus paràmetres.

        Amb l'etapa apagada els controls queden en gris (no es perden: si la
        tornes a encendre, hi tornen). Així es veu d'un cop d'ull què farà
        «Analitza» i què no.
        """
        cb = getattr(self, "_cb_" + clau)
        cb.toggled.connect(w.setEnabled)
        w.setEnabled(cb.isChecked())

    def _tab_bpm(self, val):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(self._casella_etapa(
            "bpm", "Analitza el BPM (i l'aplica al transport)",
            "Si està activada, «Analitza» detecta el tempo del tema amb el "
            "motor triat i l'escriu al camp BPM del transport (i al tram 0 "
            "del mapa). Si la desactives, el BPM que tinguis es conserva.",
            "El BPM detectat es fa servir també per a la neteja dels acords "
            "(durada mínima i encaix a la graella) i per a l'ABC."))
        grup = QGroupBox("Detecció de BPM (`app/tempo.py`)")
        v.addWidget(grup)
        self._lliga_etapa("bpm", grup)
        f = QFormLayout(grup)
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
                ("min", "Rang de cerca · mínim (BPM)",
                 (limits.BPM_MIN, limits.BPM_MAX, 1)),
                ("max", "Rang de cerca · màxim (BPM)",
                 (limits.BPM_MIN, limits.BPM_MAX, 1)),
                ("pref_min", "Rang preferit · mínim (BPM)",
                 (limits.BPM_MIN, limits.BPM_MAX, 1)),
                ("pref_max", "Rang preferit · màxim (BPM)",
                 (limits.BPM_MIN, limits.BPM_MAX, 1))):
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
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        # QUÈ S'ANALITZA (etapa d'acords). L'estructura té la seua casella a la
        # seua pestanya: les tres etapes són independents.
        v.addWidget(self._casella_etapa(
            "acords", "Analitza els acords (Chordino)",
            "Si està activada, «Analitza» passa el Chordino i reescriu "
            "acords.csv. Si la desactives, els acords que tinguis es "
            "conserven tal com estan (edicions manuals incloses).",
            "Desactivar-la és útil quan només vols refer l'estructura o el "
            "BPM sense tocar l'harmonia que ja tens revisada."))

        grup = QGroupBox("Acords (`Chordino`)")
        v.addWidget(grup)
        self._lliga_etapa("acords", grup)
        f = QFormLayout(grup)
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
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(self._casella_etapa(
            "estructura", "Analitza l'estructura (qm-segmenter)",
            "Si està activada, «Analitza» passa el qm-segmenter i reescriu "
            "estructura_ABC.csv. Si la desactives, les seccions que tinguis "
            "es conserven (les que hagis fet amb marcadors o a mà).",
            "És la part més lenta de l'anàlisi: si ja tens l'estructura feta, "
            "desactiva-la i estalvia temps."))
        grup = QGroupBox("Estructura (post-processat)")
        v.addWidget(grup)
        self._lliga_etapa("estructura", grup)
        f = QFormLayout(grup)
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
        # QUÈ S'ANALITZA (les 3 etapes): també torna a la fàbrica.
        da = DEFECTES["analisi"]
        for clau in ("bpm", "acords", "estructura"):
            getattr(self, "_cb_" + clau).setChecked(bool(da[clau]))

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
                if k not in ("bpm", "chords", "structure", "clean",
                             "analisi")}
        # QUÈ S'ANALITZA: una entrada per etapa (les 3 pestanyes).
        ana = {"bpm": self._cb_bpm.isChecked(),
               "acords": self._cb_acords.isChecked(),
               "estructura": self._cb_estructura.isChecked()}
        fora.update({"bpm": bpm, "chords": chords, "structure": est,
                     "clean": clean, "analisi": ana})
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

    def __init__(self, parent=None, trams=None, durada=0.0,
                 unit=bpm_unit.DEFECTE):
        super().__init__(parent)
        self._unit = bpm_unit.normalitza(unit)
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
            "`c33.1`).\nEls rubatos es creen des del visor amb «Marca com a "
            "rubato» o «Converteix a rubato».")
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
            bpm_mostra = bpm_unit.de_quarter(float(s[2]), self._unit)
            self.taula.setItem(r, 1, QTableWidgetItem(f"{bpm_mostra:g}"))
            self.taula.setItem(r, 2,
                               QTableWidgetItem(f"{int(s[3])}/{int(s[4])}"))

    def _sync(self):
        """Llegeix la taula cap a `self._trams` (encara per normalitzar)."""
        out = []
        for r in range(self.taula.rowCount()):
            def _t(c):
                it = self.taula.item(r, c)
                return it.text().strip() if it else ""
            # El PRIMER argument de `_t` és la COLUMNA (un int): abans hi
            # passaven strings ("0"/"1"/"2"), cosa que feia petar
            # `self.taula.item(r, "0")` amb TypeError — i no es capturava, així
            # que el diàleg del mapa PETAVA en afegir/eliminar un tram o en
            # prémer OK (auditoria 18-10-2026, destapat pel primer test que
            # exercita el diàleg).
            txt_ini = _t(0).replace(",", ".").strip().lower()
            try:
                bpm = bpm_unit.a_quarter(
                    float(_t(1).replace(",", ".")), self._unit)
                if r == 0:
                    ini = 0.0
                elif txt_ini.startswith("c"):
                    ini = self._temps_de_compas(txt_ini[1:])
                else:
                    ini = float(txt_ini)
            except (ValueError, IndexError) as e:
                raise ValueError(f"Fila {r + 1}: BPM o inici no vàlid") from e
            if not math.isfinite(ini):
                raise ValueError(f"Fila {r + 1}: l'inici ha de ser finit")
            if ini < 0:
                raise ValueError(f"Fila {r + 1}: l'inici no pot ser negatiu")
            if self._durada > 0 and ini >= self._durada:
                raise ValueError(f"Fila {r + 1}: l'inici queda fora de la WAV")
            if out and ini <= out[-1][0] + 1e-12:
                raise ValueError(
                    f"Fila {r + 1}: els inicis han d'anar en ordre creixent")
            comp = _t(2).replace(" ", "")
            if "/" in comp:
                try:
                    a, b = comp.split("/", 1)
                    num, den = int(a), int(b)
                except ValueError as e:
                    raise ValueError(
                        f"Fila {r + 1}: compàs «{comp}» no vàlid") from e
            else:
                raise ValueError(
                    f"Fila {r + 1}: escriu el compàs com num/den")
            try:
                bpm, num, den = tempo_map.valida_tempo(bpm, num, den)
            except ValueError as e:
                raise ValueError(f"Fila {r + 1}: {e}") from e
            if num == 0 and den == 0:
                raise ValueError(
                    f"Fila {r + 1}: el rubato es crea des del visor "
                    "(«Marca com a rubato» / «Converteix a rubato»).")
            out.append((ini, ini, bpm, num, den))
        if not out:
            raise ValueError("El mapa de tempo/compàs és buit")
        self._trams = out

    def accept(self):
        try:
            self.trams()
        except ValueError as e:
            QMessageBox.warning(self, "Mapa de tempo invàlid", str(e))
            return
        super().accept()

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
        try:
            self._sync()
        except ValueError as e:
            QMessageBox.warning(self, "Mapa de tempo invàlid", str(e))
            return
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
        try:
            self._sync()
        except ValueError as e:
            QMessageBox.warning(self, "Mapa de tempo invàlid", str(e))
            return
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


class DialegAnalitzaBPM(QDialog):
    """Opcions de l'acció separada «Analitza BPM».

    No detecta res: només tria motor i sensibilitat. La detecció la fa la
    finestra, perquè el diàleg no bloquege el fil de la GUI.
    """

    def __init__(self, parent=None, opcions=None):
        super().__init__(parent)
        self.setWindowTitle("Analitza BPM")
        self.setMinimumWidth(420)
        base = opcions or carrega_opcions()
        d = dict(BEATS_DEFECTES)
        d.update(base.get("beats") or {})
        lay = QVBoxLayout(self)

        info = QLabel(
            "Detecta beats i downbeats i els mostra com a línies sobre "
            "l'ona. No reanalitza acords ni estructura.")
        info.setWordWrap(True)
        info.setStyleSheet("color:#9aa6b8; font-size:11px;")
        lay.addWidget(info)

        form = QFormLayout()
        self.cb_mode = QComboBox()
        self.cb_mode.addItem("Només beats (sense BPM, compàs ni downbeats)",
                             "beats")
        self.cb_mode.addItem("BPM + beats + downbeats", "bpm")
        i = self.cb_mode.findData(d.get("mode", "beats"))
        self.cb_mode.setCurrentIndex(i if i >= 0 else 0)
        self.cb_mode.setToolTip(
            "Només beats: no agrupa en compassos, no mostra BPM ni downbeats. "
            "És el mode recomanat per a un WAV sense graella prèvia.")
        form.addRow("Què detects:", self.cb_mode)
        self.cb_mode.currentIndexChanged.connect(self._actualitza_mode)

        self.cb_motor = QComboBox()
        self.cb_motor.addItem("Nostre (tempo.py)", "nostre")
        self.cb_motor.addItem("Queen Mary (qm-barbeattracker)", "qm")
        i = self.cb_motor.findData(d.get("motor", "nostre"))
        self.cb_motor.setCurrentIndex(i if i >= 0 else 0)
        self.cb_motor.setToolTip(
            "Nostre: onsets + DP d'Ellis. Queen Mary: bar/beat tracker "
            "de Vamp. La sensibilitat s'adapta a cada motor.")
        form.addRow("Motor:", self.cb_motor)

        self.sl = QSlider(Qt.Horizontal)
        self.sl.setRange(0, 100)
        self.sl.setValue(int(d.get("sensibilitat", 50)))
        self.lb_sens = QLabel("")
        self.sl.valueChanged.connect(self._actualitza_sens)
        self._actualitza_sens()
        form.addRow("Sensibilitat:", self.sl)
        form.addRow("", self.lb_sens)

        self.cb_aplica = QCheckBox(
            "Aplica el BPM detectat al transport (si el mapa és d'un sol tram)")
        self._aplica_bpm_record = bool(d.get("aplica_bpm", True))
        self.cb_aplica.setChecked(self._aplica_bpm_record)
        form.addRow(self.cb_aplica)
        self._actualitza_mode()

        nota = QLabel(
            "Sensibilitat baixa = més estable (menys canvis). "
            "Sensibilitat alta = més flexible (accepta més variació).")
        nota.setWordWrap(True)
        nota.setStyleSheet("color:#9aa6b8; font-size:11px;")
        form.addRow(nota)
        lay.addLayout(form)

        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        lay.addWidget(box)

    def _actualitza_sens(self):
        v = int(self.sl.value())
        if v < 34:
            t = "estable"
        elif v < 67:
            t = "equilibrada"
        else:
            t = "sensible"
        self.lb_sens.setText(f"{v}/100 · {t}")

    def _actualitza_mode(self):
        nomes = self.cb_mode.currentData() == "beats"
        self.cb_aplica.setEnabled(not nomes)
        if nomes:
            self.cb_aplica.setChecked(False)
        elif hasattr(self, "_aplica_bpm_record"):
            self.cb_aplica.setChecked(self._aplica_bpm_record)

    def valors(self):
        mode = self.cb_mode.currentData()
        return {
            "motor": self.cb_motor.currentData(),
            "sensibilitat": int(self.sl.value()),
            "mode": mode,
            "aplica_bpm": bool(self.cb_aplica.isChecked()) and mode != "beats",
        }


class DialegRevisioSnap(QDialog):
    """Llista no modal de marcadors que el snap no ha pogut col·locar.

    No bloqueja ni pregunta res mentre sona: s'obri després del play i es pot
    deixar oberta. Doble clic en un tall porta el cursor a eixe punt per
    inspeccionar-lo.
    """

    def __init__(self, parent=None, ambigus=None, ves_a=None, snap=None):
        super().__init__(parent)
        self.setModal(False)
        self.setWindowTitle("Revisió del snap de compassos")
        self.setMinimumWidth(520)
        self._ves_a = ves_a
        self._snap = snap
        lay = QVBoxLayout(self)
        info = QLabel(
            "Estos marcadors no han trobat un beat/bar de QM dins de la "
            "tolerància. No s'han mogut. Doble clic per anar-hi.")
        info.setWordWrap(True)
        info.setStyleSheet("color:#9aa6b8; font-size:11px;")
        lay.addWidget(info)
        self.llista = QListWidget(self)
        for vell, proper, delta in (ambigus or ()):
            txt = (f"{float(vell):8.3f}s → {float(proper):8.3f}s "
                   f"({float(delta) * 1000:+.0f} ms)")
            item = QListWidgetItem(txt)
            item.setData(Qt.UserRole, float(vell))
            item.setData(Qt.UserRole + 1, float(proper))
            self.llista.addItem(item)
        self.llista.itemDoubleClicked.connect(self._anar)
        lay.addWidget(self.llista)
        box = QDialogButtonBox()
        self.b_snap = QPushButton("Snap al candidat")
        self.b_snap.setObjectName("secundari")
        self.b_snap.setEnabled(False)
        self.b_snap.clicked.connect(self._snap_seleccionat)
        box.addButton(self.b_snap, QDialogButtonBox.ActionRole)
        b_tanca = QPushButton("Tanca")
        b_tanca.clicked.connect(self.reject)
        box.addButton(b_tanca, QDialogButtonBox.RejectRole)
        lay.addWidget(box)
        self.llista.currentItemChanged.connect(
            lambda cur, _old: self.b_snap.setEnabled(cur is not None))

    def _anar(self, item):
        if self._ves_a is not None:
            try:
                self._ves_a(float(item.data(Qt.UserRole)))
            except Exception:  # noqa: BLE001
                pass

    def _snap_seleccionat(self):
        item = self.llista.currentItem()
        if item is None or self._snap is None:
            return
        vell = float(item.data(Qt.UserRole))
        proper = float(item.data(Qt.UserRole + 1))
        try:
            ok = bool(self._snap(vell, proper))
        except Exception:  # noqa: BLE001
            ok = False
        if ok:
            self.llista.takeItem(self.llista.row(item))
