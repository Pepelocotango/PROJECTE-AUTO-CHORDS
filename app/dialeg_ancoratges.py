#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diàleg d'**ancoratges** — Anàlisi guiat **v3**.

Especificació: `docs/ANALISI_GUIAT_v3.md` (§5 flux, §6 finestra, §7 opcions).

L'operador escolta la cançó i prem **+** cada vegada que comença un compàs nou
(o canvia l'estructura): cada ancoratge és **inici de compàs i de secció**. En
acabar, el nucli `app.ancoratges` encaixa la graella perquè hi passe exactament
per damunt (el BPM es deriva, no s'estima).

Ací viu **només la interfície** (transport amb velocitat, TAP, llista, desfer,
llindars) i el reproductor del diàleg. La detecció de BPM i l'aplicació al model
arriben per *callbacks* (`detector`, `aplicar`): així el diàleg no toca mai ni el
fil d'àudio del visor ni el model.
"""
import shutil
import subprocess
import threading
import wave

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QAbstractSpinBox, QApplication, QComboBox, QDialog, QDoubleSpinBox,
    QHBoxLayout, QShortcut,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QToolButton, QVBoxLayout, QWidget)

from app import ancoratges as ANC
from app import audio_out, ffmpeg, plataforma

PRESETS_COMPAS = ("4/4", "3/4", "2/4", "5/4", "6/8", "7/8", "9/8", "12/8")
VELOCITATS = ffmpeg.VELOCITATS
#: Etiqueta i tecla de cada velocitat (l'ordre mana al teclat 1…6).
ETIQUETES_VELOCITAT = ((0.5, "½"), (1.0 / 1.5, "⅔"), (1.0, "1×"),
                       (1.5, "1,5×"), (2.0, "2×"), (4.0, "4×"))
#: Segons que retrocedeix el cursor al desfer un ancoratge (R13).
RETROCEDEIX = 2.0


class Reproductor:
    """Reproductor del diàleg: WAV mono s16 ja estirat (`ffmpeg atempo`).

    No toca el motor del visor (R20). El temps de l'usuari i el del fitxer es
    relacionen per ``t_real = t_fitxer × factor`` (R11).
    """

    BLOC = 16384  # frames per escriptura

    def __init__(self, ruta, factor):
        self.ruta = ruta
        self.factor = float(factor)
        self._motor = None
        self._fil = None
        self._stop = threading.Event()
        self._pos = 0
        with wave.open(ruta, "rb") as wf:
            self._sr = int(wf.getframerate())
            self._canals = int(wf.getnchannels())
            self._n = int(wf.getnframes())
        if self._canals != 1 or wf.getsampwidth() != 2:
            raise RuntimeError(
                "El reproductor del guiat espera un WAV mono PCM 16 bits")

    # -- estat ------------------------------------------------------------
    @property
    def durada_real(self):
        return self._n / float(self._sr) * self.factor

    def esta_sonant(self):
        return self._motor is not None and not self._stop.is_set()

    def posicio(self):
        """Temps real de la cançó (segons)."""
        return self._pos / float(self._sr) * self.factor

    # -- motor ------------------------------------------------------------
    def _motor_nou(self):
        if plataforma.usa_audio_natiu():
            return audio_out.crea_motor(audio_out.NOM_NATIU, [], self._sr,
                                        subprocess.DEVNULL)
        for nom in plataforma.candidats_reproductor():
            if not shutil.which(nom):
                continue
            if nom == "paplay":
                return audio_out.crea_motor(
                    "paplay",
                    ["--raw", "--format=s16le", f"--rate={self._sr}",
                     "--channels=1", "--latency-msec=100"],
                    self._sr, subprocess.DEVNULL)
            if nom == "aplay":
                return audio_out.crea_motor(
                    "aplay", ["--format=S16_LE", f"--rate={self._sr}",
                              "--channels=1", "-"],
                    self._sr, subprocess.DEVNULL)
        raise RuntimeError("No hi ha cap reproductor d'àudio disponible")

    def toca(self, desde=0.0):
        """Comença (o reprén) a `desde` segons **reals** de la cançó."""
        if self.esta_sonant():
            return
        self._stop = threading.Event()
        frame = int(max(0.0, float(desde)) / self.factor * self._sr)
        self._pos = max(0, min(frame, self._n))
        motor = self._motor_nou()
        wf = wave.open(self.ruta, "rb")
        wf.setpos(self._pos)
        self._motor = motor
        self._fil = threading.Thread(target=self._bucle, args=(motor, wf),
                                     daemon=True)
        self._fil.start()

    def _bucle(self, motor, wf):
        try:
            while not self._stop.is_set():
                dades = wf.readframes(self.BLOC)
                if not dades:
                    break
                motor.stdin.write(dades)
                self._pos += len(dades) // (2 * self._canals)
        except (BrokenPipeError, ValueError, OSError):
            pass
        finally:
            try:
                wf.close()
            except OSError:
                pass

    def pausa(self):
        self._stop.set()
        if self._fil is not None:
            self._fil.join(timeout=2)
            self._fil = None
        if self._motor is not None:
            try:
                self._motor.atura()
            except OSError:
                pass
            self._motor = None

    def tanca(self):
        self.pausa()


class DialegAncoratges(QDialog):
    """Finestra d'ancoratges (v3): punxar, desfer, esborrar i generar."""

    def __init__(self, parent, ruta_wav, durada, opcions=None, bpm_global=None,
                 detector=None, aplicar=None, bpm_min=60.0, bpm_max=180.0,
                 log=None, mou_cursor=None, inici=0.0, posicio_cursor=None,
                 marge=0.10):
        super().__init__(parent)
        self.setWindowTitle("Anàlisi guiat — ancoratges")
        self.setModal(True)
        self.resize(760, 560)
        self._ruta = str(ruta_wav)
        self._durada = float(durada or 0.0)
        self._bpm_global = bpm_global
        self._detector = detector
        self._aplicar = aplicar
        self._bpm_min, self._bpm_max = float(bpm_min), float(bpm_max)
        self._log = log or (lambda *_a, **_k: None)
        #: `mou_cursor(t)` → el visor de l'app SE MOU amb l'audició (integració)
        self._mou = mou_cursor or (lambda *_a, **_k: None)
        #: `posicio_cursor()` → on és el cursor del visor (per als 2 marcs)
        self._pos_cursor = posicio_cursor or (lambda: float(self._pos))
        opc = dict(opcions or {})
        self._anc = []          # [{"t", "num", "den"}] ordenats
        self._n_manual = {}     # {idx_interval: n} (×2 / ÷2, R8)
        self._marcs = [None, None]   # compàs 1 (offset) i compàs 2 (rang BPM)
        self._anc_marc1 = None       # l'ancoratge que fa de compàs 1
        self._bpm_prov = None
        self._rang = (float(bpm_min), float(bpm_max))
        self._marge = max(0.02, min(0.5, float(marge or 0.10)))
        self._durada = max(1e-6, self._durada)
        self._pila = []         # operacions per al desfer (R13)
        self._rep = None
        self._factor = float(opc.get("velocitat", 1.0) or 1.0)
        self._pos = max(0.0, min(float(inici or 0.0), self._durada))
        self._temporals = []
        self._resultat = None
        self._construix(opc)
        self._refresca_taula()
        self._valida_llindars()

    # -- construcció de la UI --------------------------------------------
    def _construix(self, opc):
        v = QVBoxLayout(self)

        intro = QLabel(
            "Escolta la cançó i prem <b>+</b> cada vegada que comença un compàs "
            "nou o canvia l'estructura.<br>Cada <b>+</b> és <b>inici de compàs I "
            "d'una secció nova</b>. Si t'equivoques: <b>↶ Desfés</b> "
            "(Ctrl+Z) o clica la <b>×</b> de la fila.")
        intro.setWordWrap(True)
        v.addWidget(intro)

        # dos marcs: compàs 1 (offset) i compàs 2 → rang de BPM del tema
        f0 = QHBoxLayout()
        self.b_marc1 = QPushButton("① Marca el compàs 1")
        self.b_marc1.setToolTip(
            "Posa el cursor del visor on comença el compàs 1 i prem ací: fixa "
            "l'offset i crea el primer ancoratge.")
        self.b_marc1.clicked.connect(lambda: self._marca(1))
        f0.addWidget(self.b_marc1)
        self.b_marc2 = QPushButton("② Marca el compàs 2")
        self.b_marc2.setToolTip(
            "Posa el cursor on comença un compàs posterior (per defecte el 2n) "
            "i prem ací: dona el BPM aproximat del tema.")
        self.b_marc2.clicked.connect(lambda: self._marca(2))
        f0.addWidget(self.b_marc2)
        f0.addWidget(QLabel("Compassos entre:"))
        self.sp_marc_comp = QSpinBox()
        self.sp_marc_comp.setRange(1, 32)
        self.sp_marc_comp.setValue(int(opc.get("marc_compassos", 1) or 1))
        self.sp_marc_comp.setFixedWidth(60)
        self.sp_marc_comp.valueChanged.connect(self._actualitza_rang)
        f0.addWidget(self.sp_marc_comp)
        self.lb_rang = QLabel("—")
        self.lb_rang.setStyleSheet("font-weight: bold;")
        f0.addWidget(self.lb_rang, 1)
        v.addLayout(f0)

        # transport
        f1 = QHBoxLayout()
        self.lb_temps = QLabel("00:00.00 / 00:00.00")
        self.lb_temps.setStyleSheet("font-family: monospace; font-size: 14pt;")
        f1.addWidget(self.lb_temps)
        self.b_play = QPushButton("▶ Escolta (Espai)")
        self.b_play.clicked.connect(self._play_pausa)
        f1.addWidget(self.b_play)
        f1.addSpacing(12)
        f1.addWidget(QLabel("Vel:"))
        for i, (f, et) in enumerate(ETIQUETES_VELOCITAT):
            b = QPushButton(et)
            b.setCheckable(True)
            b.setChecked(abs(self._factor - f) < 1e-9)
            b.setFixedWidth(52 if len(et) > 2 else 44)
            b.setToolTip(f"Velocitat {et} (tecla {i + 1}), amb el to mantingut")
            b.clicked.connect(lambda _x=False, f=f: self._velocitat(f))
            b.setProperty("vel", f)
            f1.addWidget(b)
        f1.addStretch(1)
        v.addLayout(f1)

        # ajustos
        f2 = QHBoxLayout()
        f2.addWidget(QLabel("Compàs:"))
        self.cb_compas = QComboBox()
        self.cb_compas.setEditable(True)
        self.cb_compas.addItems(list(PRESETS_COMPAS))
        comp = str(opc.get("compas", "4/4") or "4/4")
        if comp not in PRESETS_COMPAS:
            self.cb_compas.addItem(comp)
        self.cb_compas.setCurrentText(comp)
        self.cb_compas.setFixedWidth(80)
        self.cb_compas.currentTextChanged.connect(self._actualitza_rang)
        f2.addWidget(self.cb_compas)
        f2.addSpacing(12)
        f2.addWidget(QLabel("Delay:"))
        self.sp_delay = QSpinBox()
        self.sp_delay.setRange(0, 300)
        self.sp_delay.setSingleStep(5)
        self.sp_delay.setSuffix(" ms")
        self.sp_delay.setValue(int(opc.get("delay_ms", 0) or 0))
        self.sp_delay.setFixedWidth(90)
        f2.addWidget(self.sp_delay)
        f2.addSpacing(12)
        self.lb_anc = QLabel("Ancoratges: 0")
        f2.addWidget(self.lb_anc)
        f2.addStretch(1)
        self.b_desfer = QPushButton("↶ Desfés")
        self.b_desfer.clicked.connect(self._desfer)
        f2.addWidget(self.b_desfer)
        v.addLayout(f2)

        # llindars (R7) + N_MAX (R5)
        f3 = QHBoxLayout()
        f3.addWidget(QLabel("Encaix: nota >"))
        self.sp_nota = QDoubleSpinBox()
        self.sp_nota.setRange(0.0, 5.0)
        self.sp_nota.setDecimals(1)
        self.sp_nota.setSuffix(" %")
        self.sp_nota.setValue(100.0 * float(opc.get("desv_nota", ANC.DESV_NOTA)))
        f3.addWidget(self.sp_nota)
        f3.addWidget(QLabel("sospitós >"))
        self.sp_sosp = QDoubleSpinBox()
        self.sp_sosp.setRange(0.0, 20.0)
        self.sp_sosp.setDecimals(1)
        self.sp_sosp.setSuffix(" %")
        self.sp_sosp.setValue(
            100.0 * float(opc.get("desv_sospitos", ANC.DESV_SOSPITOS)))
        f3.addWidget(self.sp_sosp)
        f3.addWidget(QLabel("no encaixa >"))
        self.sp_no = QDoubleSpinBox()
        self.sp_no.setRange(0.0, 50.0)
        self.sp_no.setDecimals(1)
        self.sp_no.setSuffix(" %")
        self.sp_no.setValue(
            100.0 * float(opc.get("desv_no_encaixa", ANC.DESV_NO_ENCAIXA)))
        f3.addWidget(self.sp_no)
        f3.addSpacing(10)
        f3.addWidget(QLabel("N ≤"))
        self.sp_nmax = QSpinBox()
        self.sp_nmax.setRange(1, 512)
        self.sp_nmax.setValue(int(opc.get("n_max", ANC.N_MAX) or ANC.N_MAX))
        self.sp_nmax.setFixedWidth(70)
        f3.addWidget(self.sp_nmax)
        f3.addStretch(1)
        v.addLayout(f3)
        for w in (self.sp_nota, self.sp_sosp, self.sp_no):
            w.valueChanged.connect(self._valida_llindars)

        # taula
        self.tab = QTableWidget(0, 8)
        self.tab.setHorizontalHeaderLabels(
            ["#", "temps", "Δt", "compàs", "n", "BPM", "desv", "accions"])
        self.tab.verticalHeader().setVisible(False)
        self.tab.setSelectionBehavior(QTableWidget.SelectRows)
        self.tab.setEditTriggers(QTableWidget.NoEditTriggers)
        hh = self.tab.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        hh.setStretchLastSection(True)
        self.tab.cellDoubleClicked.connect(self._doble_clic)
        v.addWidget(self.tab, 1)

        # botons
        f4 = QHBoxLayout()
        self.lb_avis = QLabel("")
        self.lb_avis.setStyleSheet("color: #b35c00;")
        f4.addWidget(self.lb_avis, 1)
        self.b_genera = QPushButton("Genera i aplica")
        self.b_genera.setDefault(True)
        self.b_genera.clicked.connect(self._genera)
        f4.addWidget(self.b_genera)
        b_cancel = QPushButton("Cancel·la")
        b_cancel.clicked.connect(self.reject)
        f4.addWidget(b_cancel)
        v.addLayout(f4)

        # «+» com a ATALL, no com a keyPressEvent: així funciona igual amb el
        # «+» de dalt del teclat (Maj+«=»), amb el DEL TECLAT NUMÈRIC
        # (`Qt.Key_Plus` ± `KeypadModifier`) i encara que el focus siga al
        # combo, a un espín o a la taula (que s'empassaven la tecla).
        self._atallets = []
        for seq in (QKeySequence(Qt.Key_Plus), QKeySequence("Shift+=")):
            sc = QShortcut(seq, self)
            sc.setContext(Qt.WindowShortcut)
            sc.activated.connect(self._afegeix)
            self._atallets.append(sc)

        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self._actualitza_rang()
        self.b_play.setFocus()

    # -- utilitats --------------------------------------------------------
    def ancoratges(self):
        return [dict(a) for a in self._anc]

    def opcions(self):
        return {
            "delay_ms": self.sp_delay.value(),
            "velocitat": self._factor,
            "compas": self.cb_compas.currentText().strip(),
            "n_max": self.sp_nmax.value(),
            "desv_nota": self.sp_nota.value() / 100.0,
            "desv_sospitos": self.sp_sosp.value() / 100.0,
            "desv_no_encaixa": self.sp_no.value() / 100.0,
            "marge": self._marge,
            "marc_compassos": self.sp_marc_comp.value(),
        }

    def _metre(self):
        txt = self.cb_compas.currentText().strip().replace(" ", "")
        try:
            a, b = txt.split("/", 1)
            num, den = int(a), int(b)
            if num > 0 and den > 0:
                return num, den
        except (ValueError, AttributeError):
            pass
        return 4, 4

    def _delay_s(self):
        return self.sp_delay.value() / 1000.0

    def _es_edicio(self):
        w = self.focusWidget()
        return isinstance(w, (QLineEdit, QAbstractSpinBox, QComboBox))

    @staticmethod
    def _fmt(t):
        t = max(0.0, float(t))
        return f"{int(t // 60):02d}:{t % 60:05.2f}"

    # -- reproductor ------------------------------------------------------
    def _prepara(self):
        """Renderitza (si cal) la còpia a la velocitat actual."""
        if self._rep is not None:
            return True
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.lb_avis.setText("Preparant l'àudio a esta velocitat…")
        QApplication.processEvents()
        try:
            dest = ffmpeg.prepara_escolta(self._ruta, self._factor,
                                          log=self._log)
        except (RuntimeError, ValueError, OSError) as e:
            self._avis(f"No s'ha pogut preparar l'àudio: {e}")
            return False
        finally:
            QApplication.restoreOverrideCursor()
        if dest != self._ruta and dest not in self._temporals:
            self._temporals.append(dest)
        try:
            self._rep = Reproductor(dest, self._factor)
        except (RuntimeError, OSError, wave.Error) as e:
            self._avis(f"No s'ha pogut obrir l'àudio: {e}")
            return False
        self.lb_avis.setText("")
        return True

    def _play_pausa(self):
        if self._rep is not None and self._rep.esta_sonant():
            self._pos = self._rep.posicio()
            self._rep.pausa()
            self.b_play.setText("▶ Escolta (Espai)")
            self._log(f"guiat v3: pausa a {self._pos:.3f}s")
            return
        if not self._prepara():
            return
        self._rep.toca(self._pos)
        self.b_play.setText("⏸ Pausa (Espai)")
        self._mou(self._pos)
        self._log(f"guiat v3: play a {self._pos:.3f}s ({self._factor:g}×)")

    def _pausa_i_vés(self, t):
        if self._rep is not None:
            self._rep.pausa()
        self._pos = max(0.0, min(float(t), self._durada))
        self.b_play.setText("▶ Escolta (Espai)")
        self._pinta_temps()
        self._mou(self._pos)

    def _tick(self):
        if self._rep is not None and self._rep.esta_sonant():
            self._pos = self._rep.posicio()
            if self._pos >= self._durada - 0.05:
                self._rep.pausa()
                self.b_play.setText("▶ Escolta (Espai)")
        self._pinta_temps()
        if self._rep is not None and self._rep.esta_sonant():
            self._mou(self._pos)     # el cursor del visor avança amb el só

    def _pinta_temps(self):
        self.lb_temps.setText(f"{self._fmt(self._pos)} / {self._fmt(self._durada)}")

    def _velocitat(self, f):
        f = float(f)
        for b in self.findChildren(QPushButton):
            if b.property("vel") is not None:
                b.setChecked(abs(float(b.property("vel")) - f) < 1e-9)
        if abs(f - self._factor) < 1e-9:
            return
        sonava = self._rep is not None and self._rep.esta_sonant()
        pos = self._rep.posicio() if self._rep is not None else self._pos
        if self._rep is not None:
            self._rep.tanca()
            self._rep = None
        self._factor = f
        self._pos = pos
        if sonava and self._prepara():
            self._rep.toca(self._pos)

    # -- els dos marcs (rang de BPM) --------------------------------------
    def _marca(self, i):
        """`①` compàs 1 (offset + ancoratge) · `②` compàs posterior (rang)."""
        t = max(0.0, min(float(self._pos_cursor()), self._durada))
        if i == 1:
            a = self._anc_marc1 if self._anc_marc1 in self._anc else None
            if a is not None:
                a["t"] = t
                num, den = self._metre()
                a["num"], a["den"] = num, den
                self._anc.sort(key=lambda d: d["t"])
                self._log(f"guiat v3: compàs 1 mogut a {t:.3f}s")
            else:
                num, den = self._metre()
                a = {"t": t, "num": num, "den": den}
                self._anc.append(a)
                self._anc.sort(key=lambda d: d["t"])
                self._pila.append(("afegir", a))
                self._anc_marc1 = a
                self._log(f"guiat v3: compàs 1 a {t:.3f}s (compàs {num}/{den})")
            self._marcs[0] = t
            self._n_manual.clear()
            self._resultat = None
            self._refresca_taula()
        else:
            if self._marcs[0] is None:
                self._avis("Primer marca el compàs 1 (①).")
                return
            if t <= self._marcs[0] + 0.05:
                self._avis("El compàs 2 ha d'estar DESPRÉS del compàs 1.")
                return
            self._marcs[1] = t
            self._log(f"guiat v3: compàs 2 a {t:.3f}s")
        self._pausa_i_vés(t)
        self._actualitza_rang()

    def _actualitza_rang(self, *_a):
        """BPM aproximat pels dos marcs → **rang acceptat** (descarta octaves).

        Si el tema va a ~104, cap detecció a 208 o a 52 no ha d'entrar: el rang
        és `bpm ± marge` (10 % per defecte). Sense els dos marcs, el rang és
        l'absolut (60–180) i «Genera» queda bloquejat.
        """
        m1, m2 = self._marcs
        self._bpm_prov = None
        if m1 is not None and m2 is not None and m2 > m1:
            num, den = self._metre()
            n = max(1, self.sp_marc_comp.value())
            bpm = n * num * (4.0 / den) * 60.0 / (m2 - m1)
            self._bpm_prov = bpm
            lo = max(self._bpm_min, bpm * (1.0 - self._marge))
            hi = min(self._bpm_max, bpm * (1.0 + self._marge))
            self.lb_rang.setText(
                f"BPM ≈ {bpm:.2f} · s'accepta {lo:.1f}–{hi:.1f}")
        else:
            lo, hi = self._bpm_min, self._bpm_max
            self.lb_rang.setText(
                f"Falten marcs · s'accepta {lo:.0f}–{hi:.0f}")
        self._rang = (lo, hi)
        self._valida_llindars()

    # -- ancoratges -------------------------------------------------------
    def _afegeix(self):
        t = self._pos - self._delay_s()
        t = max(0.0, min(t, self._durada))
        if self._anc and abs(t - self._anc[-1]["t"]) < ANC.SEPARACIO_MIN:
            return False
        num, den = self._metre()
        a = {"t": t, "num": num, "den": den}
        self._anc.append(a)
        self._anc.sort(key=lambda d: d["t"])
        self._pila.append(("afegir", a))
        self._n_manual.clear()
        self._log(f"guiat v3: ancoratge a {t:.3f}s (compàs {num}/{den}, "
                  f"delay {self.sp_delay.value()} ms)")
        self._resultat = None
        self._refresca_taula()
        self._valida_llindars()
        return True

    def _desfer(self):
        if not self._pila:
            return
        op, a = self._pila.pop()
        self._log(f"guiat v3: desfet ({op} {a['t']:.3f}s)")
        if op == "afegir":
            self._anc = [x for x in self._anc if x is not a]
            self._pausa_i_vés(a["t"] - RETROCEDEIX)
        else:  # "esborrar"
            self._anc.append(a)
            self._anc.sort(key=lambda d: d["t"])
        self._resultat = None
        self._refresca_taula()
        self._valida_llindars()

    def _esborra(self, idx):
        if not (0 <= idx < len(self._anc)):
            return
        a = self._anc.pop(idx)
        self._pila.append(("esborrar", a))
        self._n_manual.clear()
        self._log(f"guiat v3: esborrat l'ancoratge de {a['t']:.3f}s")
        self._resultat = None
        self._refresca_taula()
        self._valida_llindars()

    def _salta(self, idx):
        if 0 <= idx < len(self._anc):
            self._pausa_i_vés(self._anc[idx]["t"])

    def _canvia_n(self, idx_interval, factor):
        """Força el nombre de compassos d'un interval (×2 / ÷2, R8)."""
        res = self._resultat
        if res is None:
            return False
        info = next((d for d in res["intervals"] if d["idx"] == idx_interval),
                    None)
        if info is None or not info.get("n"):
            return False
        n = max(1, int(round(int(info["n"]) * float(factor))))
        if n == int(info["n"]):
            return False
        self._n_manual[idx_interval] = n
        self._log(f"guiat v3: interval {idx_interval + 1} forçat a n={n}")
        self._genera()
        return True

    def _canvia_metre(self, idx, text):
        if not (0 <= idx < len(self._anc)):
            return False
        try:
            num, den = text.replace(" ", "").split("/", 1)
            num, den = int(num), int(den)
        except (ValueError, AttributeError):
            return False
        if num < 1 or den < 1:
            return False
        self._anc[idx]["num"] = num
        self._anc[idx]["den"] = den
        self._resultat = None
        self._refresca_taula()
        return True

    def _doble_clic(self, fila, col):
        from PyQt5.QtWidgets import QInputDialog
        if col != 3:
            return
        idx = self._idx_de_fila(fila)
        if idx is None:
            return
        a = self._anc[idx]
        txt, ok = QInputDialog.getItem(
            self, "Compàs de l'ancoratge",
            f"Compàs a partir de {self._fmt(a['t'])}:", list(PRESETS_COMPAS),
            PRESETS_COMPAS.index(f"{a['num']}/{a['den']}")
            if f"{a['num']}/{a['den']}" in PRESETS_COMPAS else 0, True)
        if ok:
            self._canvia_metre(idx, txt)

    def _idx_de_fila(self, fila):
        item = self.tab.item(fila, 0)
        if item is None:
            return None
        try:
            return int(item.text()) - 1
        except ValueError:
            return None

    # -- taula ------------------------------------------------------------
    def _refresca_taula(self):
        res = self._resultat
        self.tab.setRowCount(0)
        for idx in range(len(self._anc) - 1, -1, -1):
            a = self._anc[idx]
            r = self.tab.rowCount()
            self.tab.insertRow(r)
            dt = a["t"] - self._anc[idx - 1]["t"] if idx > 0 else a["t"]
            vals = [str(idx + 1), self._fmt(a["t"]), f"{dt:.2f}",
                    f"{a['num']}/{a['den']}"]
            info = None
            if res is not None:
                info = next((d for d in res["intervals"] if d["idx"] == idx - 1),
                            None) if idx >= 1 else None
            vals += [str(info["n"]) if info and info.get("n") else "",
                     f"{info['bpm']:.2f}" if info and info.get("bpm") else "",
                     f"{100 * info['desv']:.1f}%" if info and info.get(
                         "desv") is not None else ""]
            for c, txt in enumerate(vals):
                it = QTableWidgetItem(txt)
                it.setTextAlignment(Qt.AlignCenter)
                if info is not None and info["estat"] in (
                        ANC.ESTAT_SOSPITOS, ANC.ESTAT_NO_ENCAIXA,
                        ANC.ESTAT_MASSA_CURT, ANC.ESTAT_SENSE_REFERENCIA):
                    it.setBackground(Qt.yellow if info["estat"] ==
                                     ANC.ESTAT_SOSPITOS else Qt.red)
                self.tab.setItem(r, c, it)
            w = QWidget()
            h = QHBoxLayout(w)
            h.setContentsMargins(0, 0, 0, 0)
            b_go = QToolButton()
            b_go.setText("→")
            b_go.setToolTip("Vés a este ancoratge (i pausa)")
            b_go.clicked.connect(lambda _x=False, i=idx: self._salta(i))
            b_x = QToolButton()
            b_x.setText("×")
            b_x.setToolTip("Esborra l'ancoratge")
            b_x.clicked.connect(lambda _x=False, i=idx: self._esborra(i))
            h.addStretch(1)
            h.addWidget(b_go)
            h.addWidget(b_x)
            if idx >= 1 and res is not None and info is not None \
                    and info.get("n"):
                for et, fac, consell in (("×2", 2, "el doble de compassos"),
                                         ("÷2", 0.5, "la meitat")):
                    b_n = QToolButton()
                    b_n.setText(et)
                    b_n.setToolTip(f"Interpreta l'interval amb {consell} "
                                   f"(BPM ÷ 2 / × 2)")
                    b_n.clicked.connect(
                        lambda _x=False, i=idx - 1, f=fac: self._canvia_n(i, f))
                    h.addWidget(b_n)
            self.tab.setCellWidget(r, 7, w)
        self.lb_anc.setText(f"Ancoratges: {len(self._anc)}")
        self.b_desfer.setEnabled(bool(self._pila))

    # -- llindars ---------------------------------------------------------
    def _llindars(self):
        return (self.sp_nota.value() / 100.0, self.sp_sosp.value() / 100.0,
                self.sp_no.value() / 100.0)

    def _valida_llindars(self):
        nota, sosp, no = self._llindars()
        bo = 0 <= nota < sosp < no and bool(self._anc) \
            and self._marcs[0] is not None and self._marcs[1] is not None
        for w, malament in ((self.sp_nota, not (nota < sosp)),
                            (self.sp_sosp, not (nota < sosp < no)),
                            (self.sp_no, not (sosp < no))):
            w.setStyleSheet("" if not malament else "background: #ffcccc;")
        self.b_genera.setEnabled(bo)
        if 0 <= nota < sosp < no:
            if self._marcs[0] is None or self._marcs[1] is None:
                self.lb_avis.setText(
                    "Marca primer el compàs 1 (①) i el compàs 2 (②): així el "
                    "motor sap en quin rang de BPM ha de buscar.")
            elif not self._anc:
                self.lb_avis.setText("Punxa almenys un ancoratge (+).")
            elif self._resultat is None:
                self.lb_avis.setText("")
        else:
            self.lb_avis.setText("Els llindars han de ser creixents.")
        return bo

    # -- generar ----------------------------------------------------------
    def _encaixa(self, deteccions):
        nota, sosp, no = self._llindars()
        lo, hi = self._rang
        return ANC.encaixa_ancoratges(
            self._anc, self._durada, deteccions,
            self._bpm_prov if self._bpm_prov else self._bpm_global,
            bpm_min=lo, bpm_max=hi,
            n_max=self.sp_nmax.value(), desv_nota=nota,
            desv_sospitos=sosp, desv_no_encaixa=no,
            n_manual=dict(self._n_manual) or None)

    @staticmethod
    def _puntuacio(res):
        """Com de bo és un encaix: menys intervals dolents i menys desviació."""
        ordre = {ANC.ESTAT_OK: 0, ANC.ESTAT_MANUAL: 0, ANC.ESTAT_NOTA: 1,
                 ANC.ESTAT_SOSPITOS: 2, ANC.ESTAT_NO_ENCAIXA: 9}
        dolents = sum(ordre.get(d["estat"], 5) >= 2 for d in res["intervals"])
        desv = sum(d["desv"] for d in res["intervals"]
                   if d.get("desv") is not None)
        return (-dolents, -desv)

    def _detecta_dolents(self, res):
        """BPM detectat NOMÉS per als intervals dubtosos (cost acotat, R6).

        Detectar a tots els intervals seria lent i sorollós en finestres de 2-5 s;
        només es fa on la cadena de referències no quadra, i el resultat només
        s'accepta si **millora** (mai empitjora un encaix bo).
        """
        if self._detector is None:
            return res
        males = [d for d in res["intervals"]
                 if d["estat"] in (ANC.ESTAT_SOSPITOS, ANC.ESTAT_NO_ENCAIXA)]
        if not males:
            return res
        det = [None] * (len(self._anc) - 1)
        trobat = False
        for d in males:
            try:
                bpm = self._detector(d["ini"], d["fi"])
            except (RuntimeError, ValueError, OSError):
                bpm = None
            if bpm and float(bpm) > 0:
                det[d["idx"]] = float(bpm)
                trobat = True
        if not trobat:
            return res
        self._log(f"guiat v3: detecció per interval a "
                  f"{[d['idx'] + 1 for d in males]} → "
                  f"{[None if b is None else round(b, 2) for b in det]}")
        try:
            alt = self._encaixa(det)
        except ValueError:
            return res
        return alt if self._puntuacio(alt) > self._puntuacio(res) else res

    def _genera(self):
        if self._marcs[0] is None or self._marcs[1] is None:
            self._avis("Marca el compàs 1 (①) i el compàs 2 (②) abans de "
                       "generar: el rang de BPM ix d'eixos dos punts.")
            return
        if not self._anc:
            self._avis("Punxa almenys un ancoratge (+) abans de generar.")
            return
        if not self._valida_llindars():
            return
        try:
            res = self._encaixa(None)
        except ValueError as e:
            self._avis(str(e))
            return
        res = self._detecta_dolents(res)
        self._resultat = res
        self._refresca_taula()
        self._log("guiat v3: encaix " + ("OK" if res["ok"] else "NO") +
                  f" · {len(self._anc)} ancoratges · "
                  f"trams={len(res['trams'] or [])} · "
                  f"sospitosos={res['sospitosos']} · "
                  f"no_encaixen={res.get('no_encaixen')} · "
                  f"error={res['error']}")
        if not res["ok"]:
            self.lb_avis.setText(self._detall_error(res))
            return
        seccions = len(res["trams"])
        self.lb_avis.setText(
            f"Encaixat: {seccions} trams i seccions · "
            f"{len(res['sospitosos'])} sospitosos"
            + (" (mira les files grogues: ×2/÷2 o mou l'ancoratge)"
               if res["sospitosos"] else "."))
        if self._aplicar is None:
            self.accept()
            return
        try:
            fet = bool(self._aplicar(res["trams"], res["offset"],
                                     self.ancoratges()))
        except (RuntimeError, ValueError) as e:  # el model no s'ha tocat
            self._avis(f"No s'ha pogut aplicar: {e}")
            return
        if fet:
            self.accept()

    @staticmethod
    def _detall_error(res):
        """Missatge útil: QUIN interval falla, amb temps i motiu (no genèric)."""
        noms = {ANC.ESTAT_NO_ENCAIXA: "no encaixa",
                ANC.ESTAT_MASSA_CURT: "massa curt",
                ANC.ESTAT_SENSE_REFERENCIA: "sense referència"}
        trossos = []
        for d in res["intervals"]:
            if d["estat"] in noms:
                motiu = d.get("nota") or noms[d["estat"]]
                trossos.append(
                    f"interval {d['idx'] + 1} "
                    f"({DialegAncoratges._fmt(d['ini'])}→"
                    f"{DialegAncoratges._fmt(d['fi'])}): {motiu}")
        if not trossos:
            return res["error"] or "No encaixa"
        return ("No es pot encaixar · " + " · ".join(trossos[:3]) +
                (" …" if len(trossos) > 3 else "") +
                " — esborra o mou l'ancoratge, o canvia'n el compàs.")

    def _avis(self, text):
        self.lb_avis.setText(text)

    # -- teclat i tancament ----------------------------------------------
    @staticmethod
    def _es_tecla_ancoratge(ev):
        """«+»: el de dalt del teclat (Maj+«=») o **el del teclat numèric**.

        El numèric arriba com `Qt.Key_Plus` amb (o sense) `KeypadModifier`;
        el de dalt pot arribar com `Qt.Key_Plus` o com `Qt.Key_Equal`+Maj
        segons la distribució. Els tres casos compten.
        """
        if ev.key() == Qt.Key_Plus:
            return True
        if ev.key() == Qt.Key_Equal:
            return ev.text() == "+" or bool(ev.modifiers() & Qt.ShiftModifier)
        return False

    def keyPressEvent(self, ev):
        # (1) camí normal: l'esdeveniment arriba al diàleg
        if self._es_tecla_ancoratge(ev) and not self._es_edicio():
            self._afegeix()
            return
        if ev.key() == Qt.Key_Space and not self._es_edicio():
            self._play_pausa()
            return
        if (ev.key() == Qt.Key_Z and ev.modifiers() & Qt.ControlModifier):
            self._desfer()
            return
        if not self._es_edicio():
            for f, tecla in zip(VELOCITATS, (Qt.Key_1, Qt.Key_2, Qt.Key_3,
                                             Qt.Key_4, Qt.Key_5, Qt.Key_6)):
                if ev.key() == tecla:
                    self._velocitat(f)
                    return
        super().keyPressEvent(ev)

    def reject(self):
        if self._anc:
            r = QMessageBox.question(
                self, "Ancoratges sense aplicar",
                "Hi ha ancoratges que no s'han aplicat. Eixir igualment?")
            if r != QMessageBox.Yes:
                return
        self._neteja()
        super().reject()

    def accept(self):
        self._neteja()
        super().accept()

    def _neteja(self):
        self._timer.stop()
        if self._rep is not None:
            self._rep.tanca()
            self._rep = None
        for ruta in self._temporals:      # R19: paperera, mai `rm`
            try:
                plataforma.a_la_paperera(ruta)
            except OSError:
                pass
        self._temporals = []

    def closeEvent(self, ev):
        self._neteja()
        super().closeEvent(ev)
