"""Diàleg d'opcions d'autodetecció (BPM/acords/estructura)."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox,
    QLabel, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from app import graella, limits, vamp_params
from .opcions import (
    AJUDA_CA, DEFECTES, NOMS_CA, _checkbox, _combo, _spin,
    carrega_opcions,
)

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
        fn.addRow(QLabel("Activa l'encaix a la graella"), c)
        c = QComboBox()
        for et, clau in graella.GRID_ACORDS:
            c.addItem(et, clau)
        valor = dnet.get("grid")
        if valor not in {clau for _et, clau in graella.GRID_ACORDS}:
            # Migració dels projectes/opcions vells per subdivisions.
            valor = {1: "negra", 2: "corxera",
                     4: "semicorxera", 8: "fusa"}.get(
                         int(dnet.get("divisio", 2) or 2), "corxera")
        i = c.findData(valor)
        if i >= 0:
            c.setCurrentIndex(i)
        c.setToolTip("Graella on encaixar l'inici de cada acord (la mateixa "
                     "que «Quantitza el model»).")
        self._controls["clean"]["grid"] = c
        fn.addRow(QLabel("Encaixar a la graella"), c)
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
        idx = cl["grid"].findData(dc["grid"])
        if idx >= 0:
            cl["grid"].setCurrentIndex(idx)
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
            "grid": cl["grid"].currentData(),
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
