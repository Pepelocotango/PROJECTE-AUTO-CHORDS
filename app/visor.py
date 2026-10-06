#!/usr/bin/env python3
# visor.py — Visor navegable (ona + acords + estructura + escolta + edició).
# Tot en català. Noves dependències aïllades: pyqtgraph + numpy<2 (Q9400).
# Ús: .venv/bin/python app/visor.py tema.wav [--acords acords.csv] [--abc estructura_ABC.csv] [--bpm 138] [--bpb 4]
import argparse
import copy
import atexit
import csv
import logging
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import wave

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QCloseEvent, QKeySequence
from PyQt5.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QInputDialog, QLabel,
    QListWidget, QMainWindow, QMenu, QMessageBox, QPushButton, QShortcut,
    QSlider, QSplitter, QTextEdit, QVBoxLayout, QWidget,
)

import numpy as np

APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
import pipeline  # noqa: E402
import theme  # noqa: E402
from .timeline import TimelineView  # noqa: E402

# Configuració centralitzada per al directori temporal (configurable)
from .config import TEMP_DIR as OPENCODE_DIR

VISOR_STYLESHEET = theme.visor_stylesheet()

N_BUCKETS = 2000  # pics precalculats: obrir 250 s és instantani


def llegeix_wav(ruta):
    with wave.open(ruta, "rb") as w:
        n, ch, sr, nframes = (w.getsampwidth(), w.getnchannels(),
                              w.getframerate(), w.getnframes())
        if n != 2:
            raise ValueError("només wav PCM 16 bits")
        raw = w.readframes(nframes)
    mono = np.frombuffer(raw, dtype=np.int16)
    if ch > 1:
        mono = mono.reshape(-1, ch).mean(axis=1).astype(np.int16)
    durada = len(mono) / sr
    # pics per bucket (ràpid amb numpy 1.26, sense AVX)
    idx = np.linspace(0, len(mono), N_BUCKETS + 1).astype(int)
    pics = np.empty(N_BUCKETS, dtype=np.float32)
    for i in range(N_BUCKETS):
        tram = mono[idx[i]:idx[i + 1]]
        pics[i] = np.abs(tram).max() / 32768.0 if len(tram) else 0.0
    temps = np.linspace(0, durada, N_BUCKETS)
    return {"sr": sr, "canals": ch, "durada": durada, "raw": raw,
            "mono": mono, "temps": temps, "pics": pics}


def llegeix_acords(ruta):
    # csv Chordino (temps,acord) o locators (posició acord durada) — tots dos valen
    items = []
    with open(ruta, encoding="utf-8") as f:
        for fila in csv.reader(f):
            if not fila or fila[0].startswith("posici"):
                continue
            if len(fila) == 2:
                try:
                    items.append((float(fila[0]), fila[1].strip(), fila[0]))
                except ValueError:
                    # linia malmesa al CSV: no la podem parsejar. Abans
                    # s'ignorava en silenci (perdua de dades invisible).
                    logging.getLogger("auto_chords").warning(
                        "acords: linia ignorada (no numerica): %r", fila)
                    continue
    return items


def llegeix_abc(ruta):
    items = []
    with open(ruta, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            items.append((float(r["inici_s"]), float(r["fi_s"]),
                          r["lletra"], r["família"]))
    return items




class Visor(QMainWindow):
    def __init__(self, wav, acords, abc, bpm, bpb, tempo_fix=True):
        super().__init__()
        self.logger = logging.getLogger("auto_chords")
        self._embedded = False
        # Lock curt per protegir self.proc entre fils (timer + alimentacio + UI)
        self._proc_lock = threading.Lock()
        self.setWindowTitle("Auto Chords — visor")
        self.resize(900, 600)
        self.wav_path = wav
        self.bpm, self.bpb = bpm, bpb
        self.offset = 0.0
        self.tempo_fix = bool(tempo_fix)
        self.csv_acords = os.path.abspath(acords) if acords else None
        self.logger.info("Inicialitzant visor per %s | bpm=%s bpb=%s tempo_fix=%s", wav, bpm, bpb, tempo_fix)
        if not self.csv_acords:
            cand = os.path.join(self._carpeta_acords(), "acords.csv")
            if os.path.isfile(cand):
                self.csv_acords = cand
        try:
            self.audio = llegeix_wav(wav)
        except Exception as e:  # noqa: BLE001
            self.logger.exception("No s'ha pogut carregar la WAV %s", wav)
            raise RuntimeError(f"No puc obrir la wav: {e}") from e
        if not acords and self.csv_acords:
            acords = self.csv_acords
        self.acords = llegeix_acords(acords) if acords else []
        self.seccions = llegeix_abc(abc) if abc else []
        self.pos = 0.0  # segons

        arrel = QWidget()
        self.setCentralWidget(arrel)
        self.setStyleSheet(VISOR_STYLESHEET)
        capa = QVBoxLayout(arrel)

        # Editor tipus DAW (ona + ruler + 2 carrils: acords + estructura)
        self.timeline = TimelineView(self.audio, self.acords, self.seccions,
                                    self.bpm, self.bpb, self.tempo_fix)
        self.timeline.positionChanged.connect(self.ves_a)
        self.timeline.clipSelected.connect(self._on_clip_selected)
        self.timeline.playRequested.connect(self.play_stop)
        self.timeline.editStarted.connect(self._on_edit_started)
        self.timeline.editFinished.connect(self._on_edit_finished)
        self.timeline.loopChanged.connect(self._on_loop_changed)
        self.timeline.chordTimeMoved.connect(self._on_chord_time_moved)
        self.timeline.chordEndMoved.connect(self._on_chord_end_moved)
        self.timeline.chordRenamed.connect(self._on_chord_renamed)
        self.timeline.chordDeleteRequested.connect(self._elimina_acord_index)
        self.timeline.chordDuplicateRequested.connect(self._duplica_acord_index)
        self.timeline.chordEditRequested.connect(self._on_chord_edit_requested)
        self.timeline.sectionMoved.connect(self._on_section_moved)
        self.timeline.sectionRenamed.connect(self._on_section_renamed)
        self.timeline.sectionDeleteRequested.connect(self._elimina_seccio_index)
        self.timeline.sectionDuplicateRequested.connect(self._duplica_seccio_index)
        self.timeline.clipContextMenuRequested.connect(
            self._on_clip_context_menu)
        self.timeline.sectionEditRequested.connect(self._on_section_edit_requested)
        # Dreceres de teclat: espai = play/pausa
        self._sc_play = QShortcut(QKeySequence(Qt.Key_Space), self)
        self._sc_play.activated.connect(self.play_stop)
        # NOTA: les dreceres de desfer/refer viuen a la FINESTRA PRINCIPAL
        # (menu Edita). Un QShortcut dins el visor incrustat no s'activa.

        capa.addWidget(self.timeline, stretch=4)

        # llistes + controls
        div = QSplitter(Qt.Horizontal)
        self.llista_ac = QListWidget()
        self.llista_ac.setContextMenuPolicy(Qt.CustomContextMenu)
        self.llista_ac.setToolTip("Clic: salta. Doble-clic: corregeix l'acord.")
        self._omple_llista_ac()
        self.llista_ac.itemClicked.connect(self._salt_acord)
        self.llista_ac.itemDoubleClicked.connect(self._edita_acord)
        self.llista_ac.customContextMenuRequested.connect(self._menu_acord)
        div.addWidget(self.llista_ac)
        self.llista_ab = QListWidget()
        self.llista_ab.setContextMenuPolicy(Qt.CustomContextMenu)
        self._actualitza_llista_abc()
        self.llista_ab.itemClicked.connect(self._salt_seccio)
        self.llista_ab.itemDoubleClicked.connect(self._edita_seccio)
        self.llista_ab.customContextMenuRequested.connect(self._menu_seccio)
        div.addWidget(self.llista_ab)
        capa.addWidget(div, stretch=2)

        fila = QHBoxLayout()
        self.b_play = QPushButton("▶ Escolta")
        self.b_play.clicked.connect(self.play_stop)
        self.b_stop = QPushButton("⏹")
        self.b_stop.setToolTip("Atura i torna a l'inici")
        self.b_stop.clicked.connect(self.stop_inici)
        self.b_menys = QPushButton("−10s")
        self.b_menys.clicked.connect(lambda: self.ves_a(self.pos - 10))
        self.b_mes = QPushButton("+10s")
        self.b_mes.clicked.connect(lambda: self.ves_a(self.pos + 10))
        self.b_A = QPushButton("A⟨")
        self.b_A.setToolTip("Marca inici de loop")
        self.b_A.clicked.connect(self.marca_A)
        self.b_B = QPushButton("⟩B")
        self.b_B.setToolTip("Marca fi de loop")
        self.b_B.clicked.connect(self.marca_B)
        self.b_loop = QPushButton("🔁")
        self.b_loop.setCheckable(True)
        self.b_loop.setToolTip("Activa loop A-B")
        self.b_loop.clicked.connect(self.commuta_loop)
        self.b_zm = QPushButton("🔍−")
        self.b_zm.clicked.connect(lambda: self.zoom(2.0))
        self.b_zp = QPushButton("🔍+")
        self.b_zp.clicked.connect(lambda: self.zoom(0.5))
        self.b_zt = QPushButton("Tot")
        self.b_zt.clicked.connect(self.zoom_tot)
        for b in (self.b_play, self.b_stop, self.b_menys, self.b_mes,
                  self.b_A, self.b_B, self.b_loop,
                  self.b_zm, self.b_zp, self.b_zt):
            fila.addWidget(b)
        capa.addLayout(fila)

        fila2 = QHBoxLayout()
        self.lliscador = QSlider(Qt.Horizontal)
        self.lliscador.setRange(0, int(self.audio["durada"] * 100))
        self.lliscador.sliderMoved.connect(self._salt_lliscador)
        fila2.addWidget(self.lliscador, stretch=1)
        self.temps = QLabel("00:00 / 00:00")
        fila2.addWidget(self.temps)
        self.b_mut = QPushButton("🔇")
        self.b_mut.setCheckable(True)
        self.b_mut.clicked.connect(self.commuta_mut)
        fila2.addWidget(self.b_mut)
        self.volum = QSlider(Qt.Horizontal)
        self.volum.setRange(0, 150)
        self.volum.setValue(100)
        self.volum.setMaximumWidth(110)
        self.volum.setToolTip("Volum (programari)")
        self.volum.valueChanged.connect(self._canvia_volum)
        fila2.addWidget(self.volum)
        self.etiqueta = QLabel(f"{self.audio['durada']:.1f} s · "
                               f"{len(self.acords)} acords · "
                               f"{len(self.seccions)} seccions")
        fila2.addWidget(self.etiqueta)
        capa.addLayout(fila2)
        self._actualitza_temps()

        # estat de transports
        self.vol = 1.0
        self.mut = False
        self.loop_a = None
        self.loop_b = None
        self.loop_on = False

        # registre visible (i a consola amb flush: el que cal per depurar)
        self.registre = QTextEdit()
        self.registre.setReadOnly(True)
        self.registre.setMaximumHeight(110)
        self.registre.setStyleSheet("font-family: monospace; font-size: 11px;")
        capa.addWidget(self.registre)

        # escolta amb reproductor extern (QtMultimedia petava: Violació de
        # segment — les rodes PyQt5 no porten el plugin d'àudio del sistema).
        # paplay = PipeWire/Pulse natiu; aplay = ALSA; ffplay = últim recurs.
        self.proc = None
        self._sess = 0  # generació d'alimentació: invalida fils vells
        self.t0_mono = 0.0
        self.t0_pos = 0.0
        self.rellotge = QTimer()
        self.rellotge.setInterval(50)
        self.rellotge.timeout.connect(self._tiquet)
        self.sona = False
        self.player, self.player_args = self._tria_player()
        a = self.audio
        self.log(f"wav: {os.path.basename(wav)} | {a['durada']:.1f}s "
                 f"{a['sr']}Hz {a['canals']}ch | pics max={a['pics'].max():.2f} "
                 f"mitjà={a['pics'].mean():.3f}")
        self.log(f"ona: {len(a['pics'])} punts dibuixats | acords={len(self.acords)} "
                 f"seccions={len(self.seccions)}")
        self.log(f"player: {self.player} {' '.join(self.player_args)}")
        self._undo_init()   # estat inicial = base per a la primera operacio

    def _carpeta_acords(self):
        base = os.path.splitext(os.path.basename(self.wav_path))[0]
        return os.path.join(os.path.dirname(self.wav_path), base + "_ACORDS")

    def _fmt_compas(self, s):
        if not self.tempo_fix:
            return f"{s:07.2f}s"
        beat_len = 60.0 / self.bpm
        beats = s / beat_len
        compas = int(beats // self.bpb) + 1
        beat = int(beats % self.bpb) + 1
        return f"{compas}.{beat}"




    def _parse_pos_label(self, text):
        if "s" in text:
            m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*s", text)
            if m:
                return float(m.group(1))
        m = re.search(r"(\d+)\.(\d+)", text)
        if m:
            compas = int(m.group(1))
            beat = int(m.group(2))
            return ((compas - 1) * self.bpb + (beat - 1)) * (60.0 / self.bpm)
        return float(text.split()[0])

    def _omple_llista_ac(self):
        self.llista_ac.clear()
        for t, c, *_r in self.acords:
            et = self._fmt_compas(t) if self.tempo_fix else f"{t:07.2f}s"
            self.llista_ac.addItem(f"{et}  {c}")

    def _valida_canvis_acords(self, items):
        if not items:
            return []
        ordenats = sorted(items, key=lambda x: float(x[0]))
        prev_t = None
        for item in ordenats:
            t = float(item[0])
            if t < 0:
                raise ValueError(f"L'acord {item[1]} té un inici negatiu ({t:.2f}s)")
            if prev_t is not None and t <= prev_t + 1e-9:
                raise ValueError(
                    "Els acords no poden compartir ni invertir el seu inici. "
                    "L'ordre ha de ser estricte i sense solapaments."
                )
            prev_t = t
        return ordenats

    def _normalitza_acords(self, items=None):
        items = self.acords if items is None else items
        ordenats = self._valida_canvis_acords(items)
        if isinstance(items, list):
            self.acords = ordenats
        return ordenats

    def _afegeix_acord(self, t, nom):
        if nom is None:
            nom = "N"
        nom = str(nom).strip().replace(os.sep, "-").replace("\\", "-")
        if not nom:
            return False
        item = (float(t), nom, f"{float(t):.9f}")
        nova = self._normalitza_acords(self.acords + [item])
        self.acords = nova
        if hasattr(self, "llista_ac"):
            self._omple_llista_ac()
        return True

    def _elimina_acord(self, idx):
        if idx is None:
            idx = getattr(self, "llista_ac", None).currentRow() if hasattr(self, "llista_ac") else -1
        if idx < 0 or idx >= len(self.acords):
            return False
        del self.acords[idx]
        if hasattr(self, "llista_ac"):
            self._omple_llista_ac()
        return True

    def _menu_acord(self, pos):
        if not hasattr(self, "llista_ac"):
            return
        idx = self.llista_ac.indexAt(pos).row()
        menu = QMenu(self)
        afegir = menu.addAction("Afegeix acord aquí")
        if idx >= 0:
            esborrar = menu.addAction("Elimina acord")
        accio = menu.exec_(self.llista_ac.mapToGlobal(pos))
        if accio is None:
            return
        if accio == afegir:
            nou, ok = QInputDialog.getText(self, "Afegeix acord",
                                            f"Acord a {self.pos:.2f} s", text="N")
            if not ok:
                return
            self._afegeix_acord(self.pos, nou)
            try:
                self._desa_i_regenera()
                self.log(f"afegit acord a {self.pos:.2f}s: {nou}")
            except Exception as e:  # noqa: BLE001
                self.log(f"ERROR: {e}")
                QMessageBox.warning(self, "Visor",
                                    f"No s'ha pogut afegir l'acord:\n{e}")
        elif idx >= 0 and accio == esborrar:
            try:
                self._elimina_acord(idx)
                self._desa_i_regenera()
                self.log(f"eliminat acord {idx}")
            except Exception as e:  # noqa: BLE001
                self.log(f"ERROR: {e}")
                QMessageBox.warning(self, "Visor",
                                    f"No s'ha pogut eliminar l'acord:\n{e}")

    def _edita_acord(self, item):
        fila = self.llista_ac.row(item)
        if fila < 0 or fila >= len(self.acords):
            return
        t, vell = self.acords[fila][0], self.acords[fila][1]
        nou_nom, ok_nom = QInputDialog.getText(
            self, "Corregeix l'acord",
            f"Nom de l'acord a {t:.2f} s (actual: {vell})",
            text=vell)
        if not ok_nom:
            return
        nou_nom = nou_nom.strip().replace(os.sep, "-").replace("\\", "-")
        if not nou_nom:
            return
        nou_t, ok_t = QInputDialog.getDouble(
            self, "Canvia l'inici de l'acord",
            f"Inici en segons (actual: {t:.2f}s)",
            float(t), 0.0, max(0.0, self.audio["durada"]), 3)
        if not ok_t:
            return
        nou_t = max(0.0, min(float(nou_t), self.audio["durada"]))
        antic = self.acords[fila]
        nova = list(self.acords)
        nova[fila] = (nou_t, nou_nom, f"{nou_t:.9f}")
        self._undo_marca()
        try:
            self.acords = self._normalitza_acords(nova)
        except ValueError as e:
            self.log(f"edició no vàlida: {e}")
            QMessageBox.warning(self, "Visor",
                                f"No es pot desar aquest canvi perquè trenca la lògica temporal:\n{e}")
            return
        self._omple_llista_ac()
        self._undo_commit()
        # reforç: la normalitzacio pot canviar el nom/timestamps -> index segur
        try:
            self.llista_ac.setCurrentRow(self.acords.index(self.acords[fila]))
        except (ValueError, IndexError):
            if fila < self.llista_ac.count():
                self.llista_ac.setCurrentRow(fila)
        try:
            nwavs = self._desa_i_regenera()
        except Exception as e:  # noqa: BLE001
            self.acords[fila] = antic
            self.acords = self._normalitza_acords(self.acords)
            self._omple_llista_ac()
            self.llista_ac.setCurrentRow(fila)
            self.log(f"edició ERROR: {e}")
            QMessageBox.warning(self, "Visor",
                                f"No s'ha pogut desar l'acord:\n{e}")
            return
        self.log(f"acord {t:.2f}s: {vell} → {nou_nom} @ {nou_t:.2f}s "
                 f"(csv + {nwavs} wavs_acords)")

    def _desa_i_regenera(self):
        """Desa NOMÉS el CSV (l'edició és sobre text).

        Les wavs són l'ÚLTIM pas: es generen explícitament amb `exporta()`
        quan tot està revisat i editat. Mai a cada edició.
        """
        sortida = self._carpeta_acords()
        os.makedirs(sortida, exist_ok=True)
        self.csv_acords = os.path.join(sortida, "acords.csv")
        pipeline.desa_acords_csv(self.csv_acords, self.acords)
        self.log(f"desat CSV {self.csv_acords}")
        return 0

    # ---------- Undo/Redo: NOMÉS el model d'edició ----------
    # Mai toca les wavs generades (aquestes són l'últim pas, via exporta()).
    def _estat_edicio(self):
        return (copy.deepcopy(list(self.acords)),
                copy.deepcopy(list(self.seccions)))

    def _undo_init(self):
        if not hasattr(self, "_undo_stack"):
            self._undo_stack = []
            self._redo_stack = []
            self._undo_base = self._estat_edicio()
            self._undo_pending = None

    def _undo_touch_base(self):
        """La base = el darrer estat CONSOLIDAT (fora d'una operacio).

        S'actualitza cada cop que se sincronitza el model sense operacio
        pendent, aixi mai queda obsoleta (analisi, carrega, edicions fetes
        per camins que no passen per _undo_marca)."""
        if getattr(self, "_undo_pending", None) is None:
            self._undo_base = self._estat_edicio()

    def _undo_reset(self):
        """Neteja l'historial (nou document / nova analisi)."""
        self._undo_stack = []
        self._redo_stack = []
        self._undo_base = self._estat_edicio()
        self._undo_pending = None

    def _undo_marca(self):
        """Inici d'una operació d'edició: captura l'estat 'abans'."""
        self._undo_init()
        if self._undo_pending is None:
            self._undo_pending = self._undo_base

    def _undo_commit(self):
        """Tanca l'operació d'edició i l'apila si hi ha hagut canvi."""
        self._undo_init()
        ara = self._estat_edicio()
        canvi = self._undo_pending is not None and ara != self._undo_pending
        if canvi:
            self._undo_stack.append(self._undo_pending)
            self._redo_stack.clear()
            self.log(f"undo: apilada (desfer={len(self._undo_stack)} "
                     f"refer={len(self._redo_stack)})")
        self._undo_base = ara
        self._undo_pending = None

    def _aplica_estat(self, estat):
        acords, seccions = estat
        self.acords = copy.deepcopy(acords)
        self.seccions = copy.deepcopy(seccions)
        self.timeline.set_data(self.acords, self.seccions)
        self._omple_llista_ac()
        self._actualitza_llista_abc()
        try:
            self._desa_i_regenera()
        except Exception as e:  # noqa: BLE001
            self.log(f"undo: no s'ha pogut desar el CSV: {e}")

    def undo(self):
        self._undo_init()
        self._undo_commit()  # tanca qualsevol operacio oberta
        if not self._undo_stack:
            self.log("DESFER: res a desfer")
            return
        self._redo_stack.append(self._estat_edicio())
        self._aplica_estat(self._undo_stack.pop())
        self._undo_base = self._estat_edicio()
        self._undo_pending = None
        self.log(f"DESFER fet (desfer={len(self._undo_stack)} "
                 f"refer={len(self._redo_stack)})")

    def redo(self):
        self._undo_init()
        self._undo_commit()
        if not self._redo_stack:
            self.log("REFER: res a refer")
            return
        self._undo_stack.append(self._estat_edicio())
        self._aplica_estat(self._redo_stack.pop())
        self._undo_base = self._estat_edicio()
        self._undo_pending = None
        self.log(f"REFER fet (desfer={len(self._undo_stack)} "
                 f"refer={len(self._redo_stack)})")

    def log(self, msg):
        print(f"[visor] {msg}", flush=True)
        self.registre.append(msg)
        try:
            import logging as _lg
            _lg.getLogger("auto_chords").info("VISOR: %s", msg)
        except Exception:  # noqa: BLE001
            pass

    def _tria_player(self):
        sr = self.audio["sr"]
        if shutil.which("paplay"):
            return ("paplay", ["--raw", "--format=s16le",
                               f"--rate={sr}", "--channels=1"])
        if shutil.which("aplay"):
            return ("aplay", ["--format=S16_LE", f"--rate={sr}",
                              "--channels=1", "-"])
        return ("ffplay", ["-nodisp", "-autoexit", "-f", "s16le",
                           "-ar", str(sr), "-ac", "1", "-i", "-"])

    def _mono_bytes(self):
        mono = np.frombuffer(self.audio["raw"], dtype=np.int16)
        ch = self.audio["canals"]
        if ch > 1:
            mono = mono.reshape(-1, ch).mean(axis=1).astype(np.int16)
        g = 0.0 if self.mut else self.vol
        if g != 1.0:
            mono = np.clip(mono.astype(np.float32) * g, -32768, 32767).astype(np.int16)
        return mono.tobytes()

    # transports
    def stop_inici(self):
        era = self.sona
        if era:
            self.play_stop()
        self.ves_a(0.0)
        self.log("stop → inici")

    def marca_A(self):
        self.loop_a = self.pos
        self.log(f"loop A = {self.loop_a:.2f}s")
        if self.loop_b is not None:
            self.timeline.set_loop(self.loop_a, self.loop_b)

    def marca_B(self):
        self.loop_b = self.pos
        self.log(f"loop B = {self.loop_b:.2f}s")
        if self.loop_a is not None:
            self.timeline.set_loop(self.loop_a, self.loop_b)

    def commuta_loop(self):
        self.loop_on = self.b_loop.isChecked()
        if self.loop_on and (self.loop_a is None or self.loop_b is None
                             or self.loop_b <= self.loop_a):
            self.log("loop: cal marcar A i B (B > A) primer")
            self.b_loop.setChecked(False)
            self.loop_on = False
            return
        self.log(f"loop {'ON' if self.loop_on else 'OFF'}")
        self._pinta_loop()

    def _pinta_loop(self):
        """El loop el dibuixa el mateix TimelineView."""
        if (self.loop_a is not None and self.loop_b is not None
                and self.loop_b > self.loop_a):
            self.timeline.set_loop(self.loop_a, self.loop_b)
        else:
            self.timeline.set_loop(0.0, 0.0)

    def zoom(self, factor):
        if factor < 1.0:
            self.timeline.zoom_in()
        else:
            self.timeline.zoom_out()

    def zoom_tot(self):
        self.timeline.zoom_full()

    def _canvia_volum(self, v):
        self.vol = v / 100.0
        if self.sona:  # s'aplica al proper tros (reinicia des d'aquí)
            pos = self.pos
            self._atura_proc()
            self._engega_des_de(pos)

    def commuta_mut(self):
        self.mut = self.b_mut.isChecked()
        self.log(f"mute {'ON' if self.mut else 'OFF'}")
        if self.sona:
            pos = self.pos
            self._atura_proc()
            self._engega_des_de(pos)

    @staticmethod
    def _fmt(s):
        m, r = divmod(int(s), 60)
        return f"{m:02d}:{r:02d}"

    def _fmt_timeline(self, s):
        if not self.tempo_fix:
            return f"{self._fmt(s)} / {self._fmt(self.audio['durada'])}"

        def _compas_beat(val):
            if val <= 0:
                return 1, 1
            beats = val * self.bpm / 60.0
            rem = beats % self.bpb
            if rem == 0:
                return int(beats // self.bpb), self.bpb
            return int(beats // self.bpb) + 1, int(rem) + 1

        compas, beat_idx = _compas_beat(s)
        total_compas, total_beat_idx = _compas_beat(self.audio["durada"])
        return f"{compas}.{beat_idx} / {total_compas}.{total_beat_idx}"

    def _actualitza_temps(self):
        self.timeline.set_tempo_mode(self.tempo_fix, self.bpm, self.bpb)
        self.temps.setText(self._fmt_timeline(self.pos))

    def _edita_acord_index(self, idx):
        if idx < 0 or idx >= len(self.acords):
            return
        if idx >= self.llista_ac.count():
            return
        item = self.llista_ac.item(idx)
        if item is not None:
            self._edita_acord(item)

    def _edita_seccio_index(self, idx):
        if idx < 0 or idx >= len(self.seccions):
            return
        if idx >= self.llista_ab.count():
            return
        item = self.llista_ab.item(idx)
        if item is not None:
            self._edita_seccio(item)

    # Handlers dels senyals del TimelineView (QGraphicsView DAW-like)
    def _sync_timeline_acords(self):
        """Recopiem els acords del timeline al model del Visor."""
        self.acords = list(self.timeline._acords)
        self._omple_llista_ac()
        self._undo_touch_base()

    def _sync_timeline_seccions(self):
        """Recopiem les seccions del timeline al model del Visor."""
        self.seccions = list(self.timeline._seccions)
        self._actualitza_llista_abc()
        self._undo_touch_base()

    def _on_chord_time_moved(self, idx, new_t):
        # Només sincronitzem el model/llista; el desat va al release
        self._undo_marca()
        self._sync_timeline_acords()
        self.log(f"acord {idx} → {new_t:.2f}s")

    def _on_chord_end_moved(self, idx, new_t):
        self._undo_marca()
        self._sync_timeline_acords()
        self.log(f"final acord {idx} → {new_t:.2f}s")

    def _on_edit_started(self):
        """Inici del gest (mouse press sobre un clip): captura l'estat 'abans'.

        Model Audacity: PushState() explicit al punt de l'accio, en comptes
        de dependre de senyals de canvi (que poden no arribar)."""
        self._undo_marca()

    def _on_edit_finished(self):
        """Fi d'un drag/resize → tanca l'operació i desa el CSV."""
        self._sync_timeline_acords()
        self._sync_timeline_seccions()
        self._undo_commit()
        try:
            self._desa_i_regenera()
            self._regenera_abc_des_de_totes_les_seccions("edició visual")
        except Exception as e:  # noqa: BLE001
            self.log(f"desat ERROR: {e}")

    def _on_loop_changed(self, a, b):
        """Loop A/B seleccionat al regle del timeline."""
        self.loop_a, self.loop_b = float(a), float(b)
        self.loop_on = True
        if hasattr(self, "b_loop"):
            self.b_loop.setChecked(True)
        self.log(f"loop A={a:.2f}s B={b:.2f}s")

    def _on_chord_renamed(self, idx, new_name):
        self._undo_marca()
        self._sync_timeline_acords()
        self._undo_commit()
        try:
            self._desa_i_regenera()
            self.log(f"acord {idx} reanomenat: {new_name}")
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR: {e}")
            QMessageBox.warning(self, "Visor", f"No s'ha pogut regenerar:\n{e}")

    def _on_chord_edit_requested(self, idx):
        # Doble-clic al ChordItem: edició completa (nom + inici) amb QInputDialog
        if idx < 0 or idx >= len(self.acords):
            return
        if idx < self.llista_ac.count():
            item = self.llista_ac.item(idx)
            if item is not None:
                self._edita_acord(item)

    def _on_clip_context_menu(self, kind, idx, pos):
        """Menú contextual (botó dret) sobre un clip del timeline."""
        te_clip = idx is not None and idx >= 0
        menu = QMenu(self)
        a_dup = menu.addAction("Duplica")
        a_del = menu.addAction("Elimina")
        menu.addSeparator()
        a_ren = menu.addAction("Reanomena")
        # desactivats si no hi ha cap clip seleccionat
        for a in (a_dup, a_del, a_ren):
            a.setEnabled(te_clip)
        accio = menu.exec_(pos)
        if accio is None or not te_clip:
            return
        if accio == a_dup:
            if kind == "chord":
                self._duplica_acord_index(idx)
            else:
                self._duplica_seccio_index(idx)
        elif accio == a_del:
            if kind == "chord":
                self._elimina_acord_index(idx)
            else:
                self._elimina_seccio_index(idx)
        elif accio == a_ren:
            # reutilitza el rename inline existent
            self.timeline.chordEditRequested.emit(idx) if kind == "chord" \
                else self.timeline.sectionEditRequested.emit(idx)

    def _duplica_acord_index(self, idx):
        """Duplica l'acord idx: s'insereix JUST DESPRES i es reparteix la

        durada — el duplicat va a mig camí entre l'original i el següent
        (així no cal desplaçar res i es mantenen les invariants)."""
        if idx < 0 or idx >= len(self.acords):
            return
        t, nom = self.acords[idx][0], self.acords[idx][1]
        seguent = (self.acords[idx + 1][0] if idx + 1 < len(self.acords)
                   else self.audio["durada"])
        nou_t = (t + seguent) / 2.0
        if nou_t - t < 0.02:          # massa poc espai per un duplicat
            self.log(f"no es pot duplicar l'acord {idx}: no hi ha espai")
            return
        self._undo_marca()
        self.acords.insert(idx + 1, (nou_t, nom, f"{nou_t:.9f}"))
        self.acords = self._normalitza_acords(self.acords)
        self._undo_commit()
        self.timeline.set_data(self.acords, self.seccions)
        try:
            self._desa_i_regenera()
            self.log(f"duplicat acord {idx} a {nou_t:.2f}s")
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR: {e}")

    def _duplica_seccio_index(self, idx):
        """Duplica la seccio idx: es parteix en dues (la meitat per a cada una).

        El duplicat va JUST DESPRES i comparteix la durada de l'original,
        sense desplaçar els seguents (manté les invariants)."""
        if idx < 0 or idx >= len(self.seccions):
            return
        ini, fi, L, fam = self.seccions[idx]
        mig = (ini + fi) / 2.0
        if mig - ini < 0.05 or fi - mig < 0.05:
            self.log(f"no es pot duplicar la secció {idx}: és massa curta")
            return
        self._undo_marca()
        self.seccions[idx] = (ini, mig, L, fam)
        self.seccions.insert(idx + 1, (mig, fi, L, fam))
        self._undo_commit()
        self.timeline.set_data(self.acords, self.seccions)
        try:
            self._regenera_abc_des_de_totes_les_seccions(
                f"secció {idx} duplicada")
            self.log(f"duplicada secció {idx}")
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR: {e}")

    def _elimina_acord_index(self, idx):
        if idx < 0 or idx >= len(self.acords):
            return
        self._undo_marca()
        if not self._elimina_acord(idx):
            return
        self._undo_commit()
        self.timeline.set_data(self.acords, self.seccions)
        try:
            self._desa_i_regenera()
            self.log(f"eliminat acord {idx}")
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR: {e}")
            QMessageBox.warning(self, "Visor",
                                f"No s'ha pogut eliminar:\n{e}")

    def _elimina_seccio_index(self, idx):
        if idx < 0 or idx >= len(self.seccions):
            return
        self._undo_marca()
        if not self._elimina_seccio(idx):
            return
        self._undo_commit()
        self.timeline.set_data(self.acords, self.seccions)
        try:
            self._regenera_abc_des_de_totes_les_seccions("secció eliminada")
            self.log(f"eliminada secció {idx}")
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR: {e}")
            QMessageBox.warning(self, "Visor",
                                f"No s'ha pogut eliminar:\n{e}")

    def _on_section_moved(self, idx, ini, fi):
        self._undo_marca()
        self._sync_timeline_seccions()
        try:
            self._regenera_abc_des_de_totes_les_seccions(
                f"secció {idx} moguda ({ini:.2f}-{fi:.2f})")
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR: {e}")
            QMessageBox.warning(self, "Visor", f"No s'ha pogut regenerar:\n{e}")

    def _on_section_renamed(self, idx, lletra, familia):
        self._undo_marca()
        self._sync_timeline_seccions()
        self._undo_commit()
        try:
            self._regenera_abc_des_de_totes_les_seccions(
                f"secció {idx} reanomenada: {lletra}")
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR: {e}")
            QMessageBox.warning(self, "Visor", f"No s'ha pogut regenerar:\n{e}")

    def _on_section_edit_requested(self, idx):
        if idx < 0 or idx >= len(self.seccions):
            return
        if idx < self.llista_ab.count():
            item = self.llista_ab.item(idx)
            if item is not None:
                self._edita_seccio(item)

    # navegació
    def ves_a(self, t):
        self.pos = max(0.0, min(float(t), self.audio["durada"]))
        self.timeline.set_position(self.pos, emit=False)
        self.lliscador.setValue(int(self.pos * 100))
        self._actualitza_temps()
        if self.sona:
            self._atura_proc()
            self._engega_des_de(self.pos)

    def _on_clip_selected(self, kind, index):
        """Click a un clip del timeline -> sincronitza la llista de sota."""
        if kind == "chord" and 0 <= index < self.llista_ac.count():
            self.llista_ac.setCurrentRow(index)
        elif kind == "section" and 0 <= index < self.llista_ab.count():
            self.llista_ab.setCurrentRow(index)

    def _salt_acord(self, item):
        row = self.llista_ac.row(item)
        if row >= 0:
            self.timeline.select_clip("chord", row)
        self.ves_a(self._parse_pos_label(item.text()))

    def _valida_canvis_seccions(self, items):
        if not items:
            return []
        ordenats = sorted(items, key=lambda x: float(x[0]))
        prev_fi = -1e-9
        for item in ordenats:
            ini = float(item[0])
            fi = float(item[1])
            if ini < 0 or fi < 0:
                raise ValueError(f"La secció {item[2]} té temps negatius ({ini:.2f}s–{fi:.2f}s)")
            if fi <= ini:
                raise ValueError(f"La secció {item[2]} té una durada no vàlida ({ini:.2f}s–{fi:.2f}s)")
            if ini < prev_fi - 1e-9:
                raise ValueError(
                    "Les seccions no poden solapar-se ni invertir-se. "
                    "L'ordre temporal ha de ser estricte."
                )
            prev_fi = fi
        return ordenats

    def _normalitza_seccions(self, items=None):
        items = self.seccions if items is None else items
        ordenats = self._valida_canvis_seccions(items)
        if isinstance(items, list):
            self.seccions = ordenats
        return ordenats

    def _actualitza_llista_abc(self):
        self.llista_ab.clear()
        for ini, fi, L, fam in self.seccions:
            if self.tempo_fix:
                ini_txt = self._fmt_compas(ini)
                fi_txt = self._fmt_compas(fi)
            else:
                ini_txt = f"{ini:07.2f}s"
                fi_txt = f"{fi:07.2f}s"
            self.llista_ab.addItem(f"{L} ({fam})  {ini_txt}–{fi_txt}")

    def _afegeix_seccio(self, ini, fi, lletra=None, fam=None):
        ini = float(ini)
        fi = float(fi)
        if fi <= ini:
            fi = ini + 1.0
        if fam is None:
            fam = str(lletra or "A").strip() or "A"
        if lletra is None:
            lletra = fam
        item = (ini, fi, str(lletra).strip() or "A", str(fam).strip() or "A")
        self.seccions = self._normalitza_seccions(self.seccions + [item])
        if hasattr(self, "llista_ab"):
            self._actualitza_llista_abc()
        return True

    def _elimina_seccio(self, idx):
        if idx < 0 or idx >= len(self.seccions):
            return False
        ini, fi, _L, _fam = self.seccions[idx]
        del self.seccions[idx]
        # Invariant: el fi d'una seccio = inici de la seguent. En treure'n una,
        # el vei ocupa l'espai buit (el previ s'esten, o el seguent comenca abans).
        if idx - 1 >= 0:
            pi, _pf, pl, pfam = self.seccions[idx - 1]
            self.seccions[idx - 1] = (pi, fi, pl, pfam)
        elif idx < len(self.seccions):
            _ni, nf, nl, nfam = self.seccions[idx]
            self.seccions[idx] = (ini, nf, nl, nfam)
        if hasattr(self, "llista_ab"):
            self._actualitza_llista_abc()
        return True

    def _salt_seccio(self, item):
        row = self.llista_ab.row(item)
        if row >= 0:
            self.timeline.select_clip("section", row)
        self.ves_a(self._parse_pos_label(item.text()))

    def _menu_seccio(self, pos):
        if not self.seccions:
            return
        idx = self.llista_ab.indexAt(pos).row()
        if idx < 0:
            return
        ini, fi, _L, _fam = self.seccions[idx]
        menu = QMenu(self)
        afegir = menu.addAction("Afegeix secció aquí")
        partir = menu.addAction("Partir secció aquí")
        fusionar_prev = menu.addAction("Fusionar amb anterior")
        fusionar_next = menu.addAction("Fusionar amb següent")
        eliminar = menu.addAction("Elimina secció")
        accio = menu.exec_(self.llista_ab.mapToGlobal(pos))
        if accio is None:
            return
        if accio == afegir:
            lletra, ok1 = QInputDialog.getText(self, "Afegeix secció",
                                               "Etiqueta de la secció", text="A")
            if not ok1:
                return
            fam, ok2 = QInputDialog.getText(self, "Afegeix secció",
                                            "Família", text=lletra.strip() or "A")
            if not ok2:
                return
            try:
                self._afegeix_seccio(self.pos, min(self.audio["durada"], self.pos + 2.0), lletra, fam)
                self._regenera_abc_des_de_totes_les_seccions(f"secció afegida a {self.pos:.2f}s")
            except Exception as e:  # noqa: BLE001
                self.log(f"ERROR: {e}")
                QMessageBox.warning(self, "Visor",
                                    f"No s'ha pogut afegir la secció:\n{e}")
        elif accio == partir:
            frac = (ini + fi) / 2.0
            nou, ok = QInputDialog.getDouble(
                self, "Partir secció",
                f"Tall en segons ({ini:.2f}–{fi:.2f})",
                frac, 0.0, fi - ini, 3)
            if not ok:
                return
            try:
                self.seccions = pipeline.parteix_seccio(self.seccions, idx, nou)
                self._actualitza_llista_abc()
                self._regenera_abc_des_de_totes_les_seccions(
                    f"secció partida a {nou:.2f}s")
            except Exception as e:  # noqa: BLE001
                self.log(f"ERROR: {e}")
                QMessageBox.warning(self, "Visor",
                                    f"No s'ha pogut partir la secció:\n{e}")
        elif accio == fusionar_prev:
            try:
                self.seccions = pipeline.fusiona_seccions(self.seccions, idx, amb="anterior")
                self._actualitza_llista_abc()
                self._regenera_abc_des_de_totes_les_seccions("seccions fusionades amb anterior")
            except Exception as e:  # noqa: BLE001
                self.log(f"ERROR: {e}")
                QMessageBox.warning(self, "Visor",
                                    f"No s'ha pogut fusionar amb anterior:\n{e}")
        elif accio == fusionar_next:
            try:
                self.seccions = pipeline.fusiona_seccions(self.seccions, idx, amb="seguent")
                self._actualitza_llista_abc()
                self._regenera_abc_des_de_totes_les_seccions("seccions fusionades amb següent")
            except Exception as e:  # noqa: BLE001
                self.log(f"ERROR: {e}")
                QMessageBox.warning(self, "Visor",
                                    f"No s'ha pogut fusionar amb següent:\n{e}")
        elif accio == eliminar:
            try:
                self._elimina_seccio(idx)
                self._regenera_abc_des_de_totes_les_seccions("secció eliminada")
            except Exception as e:  # noqa: BLE001
                self.log(f"ERROR: {e}")
                QMessageBox.warning(self, "Visor",
                                    f"No s'ha pogut eliminar la secció:\n{e}")

    def _regenera_abc_des_de_totes_les_seccions(self, msg):
        sortida = self._carpeta_acords()
        os.makedirs(sortida, exist_ok=True)
        abc = os.path.join(sortida, "estructura_ABC.csv")
        pipeline.desa_abc_csv(abc, self.seccions, self.bpm, self.log,
                              lliure=not self.tempo_fix, bpb=self.bpb)
        self.log(f"ABC recalculat (només CSV): {msg}")

    def _edita_seccio(self, item):
        fila = self.llista_ab.row(item)
        if fila < 0 or fila >= len(self.seccions):
            return
        ini, fi, vell_lletra, vell_fam = self.seccions[fila]
        nova_lletra, ok_l = QInputDialog.getText(
            self, "Corregeix la secció",
            f"Lletra de la secció {vell_lletra} ({ini:.2f}s–{fi:.2f}s)",
            text=vell_lletra)
        if not ok_l:
            return
        nova_lletra = str(nova_lletra).strip() or vell_lletra
        nou_inici, ok_t = QInputDialog.getDouble(
            self, "Canvia l'inici de la secció",
            f"Inici en segons (actual: {ini:.2f}s)",
            float(ini), 0.0, max(0.0, self.audio["durada"]), 3)
        if not ok_t:
            return
        nou_inici = max(0.0, min(float(nou_inici), self.audio["durada"]))
        antic = self.seccions[fila]
        nova = list(self.seccions)
        nova[fila] = (nou_inici, fi, nova_lletra, vell_fam)
        self._undo_marca()
        try:
            self.seccions = self._normalitza_seccions(nova)
        except ValueError as e:
            self.log(f"edició secció no vàlida: {e}")
            QMessageBox.warning(self, "Visor",
                                f"No es pot desar aquest canvi perquè trenca la lògica temporal:\n{e}")
            return
        self._actualitza_llista_abc()
        self._undo_commit()
        try:
            self.llista_ab.setCurrentRow(self.seccions.index(self.seccions[fila]))
        except (ValueError, IndexError):
            if fila < self.llista_ab.count():
                self.llista_ab.setCurrentRow(fila)
        try:
            self._regenera_abc_des_de_totes_les_seccions(f"secció {vell_lletra}→{nova_lletra} @ {nou_inici:.2f}s")
        except Exception as e:  # noqa: BLE001
            self.seccions[fila] = antic
            self.seccions = self._normalitza_seccions(self.seccions)
            self._actualitza_llista_abc()
            self.llista_ab.setCurrentRow(fila)
            self.log(f"edició secció ERROR: {e}")
            QMessageBox.warning(self, "Visor",
                                f"No s'ha pogut desar la secció:\n{e}")
            return
        self.log(f"secció {ini:.2f}s: {vell_lletra} → {nova_lletra} @ {nou_inici:.2f}s")

    def _salt_lliscador(self, v):
        self.ves_a(v / 100.0)

    # escolta
    def _engega_des_de(self, t):
        self._atura_proc()
        # Clamp per seguretat (validació prèvia pot ser absent en alguns
        # camins; evitem índex negatiu o inici més enllà de les dades).
        t = max(0.0, min(float(t), float(self.audio["durada"])))
        inici = int(t * self.audio["sr"]) * 2  # 16 bits mono
        dades = self._mono_bytes()[inici:]
        self.log(f"play des de {t:.2f}s ({len(dades)} bytes) amb {self.player}...")
        self.fitxer_err = os.path.join(OPENCODE_DIR, "visor_player.log")
        try:
            # Assegura que el directori temporal del projecte existeix
            try:
                os.makedirs(OPENCODE_DIR, exist_ok=True)
            except OSError as e:
                logging.getLogger("auto_chords").warning(
                    "no s'ha pogut crear el directori temporal %s: %s",
                    OPENCODE_DIR, e)
            with open(self.fitxer_err, "wb") as ferr:
                # start_new_session: el player queda en grup propi → el podem
                # matar sencer (ell + fills) encara que la finestra mori.
                self.proc = subprocess.Popen([self.player, *self.player_args],
                                             stdin=subprocess.PIPE,
                                             stdout=subprocess.DEVNULL,
                                             stderr=ferr,
                                             start_new_session=True)
                # L'escriptura va en fil propi: el pipe només empassa al
                # ritme del so i un write() sencer congelaria la GUI.
                sess = self._sess
                fil = threading.Thread(target=self._alimenta,
                                       args=(self.proc, dades, sess),
                                       daemon=True)
                fil.start()
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR engegar {self.player}: {e}")
            QMessageBox.warning(self, "Visor",
                                f"No puc engegar {self.player}: {e}")
            self.proc = None
            return
        self.t0_mono = time.monotonic()
        self.t0_pos = t
        self.log(f"proc {self.player} pid={self.proc.pid} en marxa")

    def _alimenta(self, proc, dades, sess):
        # escriu per trossos; si arriba una sessió nova o el proc mor, plega.
        try:
            vista = memoryview(dades)
            pas = 65536
            for i in range(0, len(dades), pas):
                if sess != self._sess or proc.poll() is not None:
                    break
                try:
                    proc.stdin.write(vista[i:i + pas])
                except (BrokenPipeError, ValueError):
                    break
            try:
                proc.stdin.close()
            except (BrokenPipeError, ValueError):
                pass
        except Exception as e:  # noqa: BLE001
            print(f"[visor] alimenta: {e}", flush=True)

    def _mostra_err_player(self):
        try:
            with open(self.fitxer_err, "rb") as f:
                txt = f.read()[-2000:].decode("utf-8", "replace").strip()
            if txt:
                self.log(f"stderr {self.player}:\n{txt}")
            else:
                self.log(f"stderr {self.player}: (buit)")
        except Exception as e:  # noqa: BLE001
            self.log(f"no puc llegir stderr: {e}")

    def _atura_proc(self):
        # invalida el fil d'alimentació i mata el grup sencer: res no queda sonant.
        self._sess += 1
        with self._proc_lock:
            proc = self.proc
            self.proc = None
            if proc is None:
                return
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except (ProcessLookupError, OSError):
                pass  # ja era mort
            try:
                proc.wait(timeout=2)
            except (subprocess.TimeoutExpired, OSError):
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except (ProcessLookupError, OSError):
                    pass
                # Re-collirem el zombie per no contaminar la taula de processos
                try:
                    proc.wait(timeout=1)
                except (subprocess.TimeoutExpired, OSError):
                    pass

    def play_stop(self):
        if self.sona:
            self.log(f"stop a {self.pos:.2f}s")
            self._atura_proc()
            self.rellotge.stop()
            self.sona = False
            self.timeline.set_follow(False)
            self.b_play.setText("▶ Escolta")
        else:
            # Comencem SEMPRE des del cursor visible (no d'un estat antic)
            self.pos = float(self.timeline.get_position())
            self._engega_des_de(self.pos)
            if self.proc is None:
                return
            self.rellotge.start()
            self.sona = True
            self.timeline.set_follow(True)   # la vista segueix el cursor
            self.b_play.setText("⏸ Atura")
            self.log("escoltant...")

    def _tiquet(self):
        # el cursor avança amb rellotge de paret des de l'inici real
        if self.proc and self.proc.poll() is not None:
            self.log(f"proc acabat (codi {self.proc.returncode})")
            self._mostra_err_player()
            self.play_stop()  # s'ha acabat el wav
            return
        t = self.t0_pos + (time.monotonic() - self.t0_mono)
        if self.loop_on and self.loop_a is not None and self.loop_b is not None \
                and t >= self.loop_b:
            self.log(f"loop → {self.loop_a:.2f}s")
            self.ves_a(self.loop_a)
            return
        if t >= self.audio["durada"]:
            self.play_stop()
            return
        self.pos = t
        self.timeline.set_position(self.pos, emit=False)
        self.lliscador.setValue(int(t * 100))
        self._actualitza_temps()
        self._ressalta(t)

    def _ressalta(self, t):
        # il·lumina l'acord i la secció que sonen (cerca lineal: prou ràpid)
        if self.acords:
            k = 0
            for i, (ta, _c, *_r) in enumerate(self.acords):
                if ta <= t:
                    k = i
                else:
                    break
            if self.llista_ac.currentRow() != k:
                self.llista_ac.setCurrentRow(k)
        if self.seccions:
            k = 0
            for i, (ini, fi, _L, _f) in enumerate(self.seccions):
                if ini <= t:
                    k = i
                else:
                    break
            if self.llista_ab.currentRow() != k:
                self.llista_ab.setCurrentRow(k)

    def exporta(self):
        if not self.acords:
            QMessageBox.warning(self, "Visor",
                                "Primer cal tenir acords carregats o analitzats.")
            return
        sortida = self._carpeta_acords()
        os.makedirs(sortida, exist_ok=True)
        self.csv_acords = os.path.join(sortida, "acords.csv")
        pipeline.desa_acords_csv(self.csv_acords, self.acords)
        self.log(f"exporta → {sortida}")
        try:
            if self.seccions:
                abc = os.path.join(sortida, "estructura_ABC.csv")
                pipeline.desa_abc_csv(abc, self.seccions, self.bpm,
                                      self.log, lliure=not self.tempo_fix,
                                      bpb=self.bpb)
                pipeline.regenera_wavs_acords(self.csv_acords, sortida,
                                              self.bpm, self.bpb,
                                              self.offset, self.audio["durada"],
                                              44100, self.log,
                                              self.tempo_fix)
                pipeline.regenera_wavs_estructura(abc, sortida, 44100,
                                                  self.log)
            else:
                seg_csv = os.path.join(sortida, "segments.csv")
                amb_est = os.path.isfile(seg_csv)
                pipeline.exporta_total(self.csv_acords, seg_csv if amb_est else None,
                                       sortida, self.bpm, self.bpb, self.offset,
                                       44100, self.log, tempo_fix=self.tempo_fix,
                                       amb_estructura=amb_est)
            self.log(f"exporta FET: {sortida}")
            QMessageBox.information(self, "Visor",
                                    f"Exportació feta a:\n{sortida}")
        except Exception as e:  # noqa: BLE001
            self.log(f"exporta ERROR: {e}")
            QMessageBox.warning(self, "Visor",
                                f"No s'ha pogut exportar:\n{e}")

    def closeEvent(self, ev):
        self.log("tanco: mato l'àudio...")
        self.rellotge.stop()
        self._atura_proc()
        # Disconnect dels signals del TimelineView per evitar memory leaks.
        # NOMÉS si és una finestra autònoma: en incrustar-se el visor dins
        # Finestra es fa `_embedded = True` + `close()` per amagar-lo, i
        # desconnectar-lo allà deixaria el visor SORD (no rebria cap senyal).
        if hasattr(self, "timeline") and not getattr(self, "_embedded", False):
            for sig, slot in [
                ("positionChanged", self.ves_a),
                ("clipSelected", self._on_clip_selected),
                ("playRequested", self.play_stop),
                ("editStarted", self._on_edit_started),
                ("editFinished", self._on_edit_finished),
                ("loopChanged", self._on_loop_changed),
                ("chordTimeMoved", self._on_chord_time_moved),
                ("chordEndMoved", self._on_chord_end_moved),
                ("chordRenamed", self._on_chord_renamed),
                ("chordDeleteRequested", self._elimina_acord_index),
                ("chordEditRequested", self._on_chord_edit_requested),
                ("sectionMoved", self._on_section_moved),
                ("sectionRenamed", self._on_section_renamed),
                ("sectionDeleteRequested", self._elimina_seccio_index),
                ("sectionEditRequested", self._on_section_edit_requested),
            ]:
                try:
                    getattr(self.timeline, sig).disconnect(slot)
                except (TypeError, RuntimeError):
                    pass  # ja estava disconnectat o signal inexistent
        super().closeEvent(ev)
        if getattr(self, "_embedded", False):
            return
        QApplication.instance().quit()


def main():
    ap = argparse.ArgumentParser(
        description="Visor: ona + acords + escolta + correcció.")
    ap.add_argument("wav", nargs="?", help="fitxer .wav")
    ap.add_argument("--acords", default="", help="csv Chordino o locators")
    ap.add_argument("--abc", default="", help="estructura_ABC.csv")
    ap.add_argument("--bpm", type=float, default=138.0)
    ap.add_argument("--bpb", type=int, default=4)
    a = ap.parse_args()
    if not a.wav:
        app0 = QApplication(sys.argv)
        wav, _ = QFileDialog.getOpenFileName(None, "Tria la wav", "",
                                             "Àudio WAV (*.wav)")
        if not wav:
            sys.exit(0)
        a.wav = wav
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    v = Visor(os.path.abspath(a.wav), a.acords or None, a.abc or None,
              a.bpm, a.bpb)
    v.show()
    codi = app.exec_()
    v._atura_proc()  # xarxa de seguretat: mai deixar àudio sonant
    sys.exit(codi)


if __name__ == "__main__":
    main()
