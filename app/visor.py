#!/usr/bin/env python3
# visor.py — Visor navegable (ona + acords + estructura + escolta + edició).
# Tot en català. Noves dependències aïllades: pyqtgraph + numpy<2 (Q9400).
# Ús: .venv/bin/python app/visor.py tema.wav [--acords acords.csv] [--abc estructura_ABC.csv] [--bpm 138] [--bpb 4]
import argparse
import atexit
import csv
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import wave

from PyQt5.QtCore import QObject, QThread, QTimer, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QInputDialog, QLabel,
    QListWidget, QMainWindow, QMenu, QMessageBox, QPushButton, QSlider,
    QSplitter, QTextEdit, QVBoxLayout, QWidget,
)

import numpy as np
import pyqtgraph as pg

APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
import pipeline  # noqa: E402

N_BUCKETS = 2000  # pics precalculats: obrir 250 s és instantani


class FeinaAnalitza(QThread):
    missatge = pyqtSignal(str)
    feta = pyqtSignal(bool, str, str)  # ok, csv_acords, csv_abc

    def __init__(self, wav, sortida, bpm):
        super().__init__()
        self.wav = wav
        self.sortida = sortida
        self.bpm = bpm

    def run(self):
        try:
            os.makedirs(self.sortida, exist_ok=True)
            csv_ac = os.path.join(self.sortida, "acords.csv")
            self.missatge.emit("analitza 1/3: acords (Chordino)...")
            pipeline.extract_chords(self.wav, csv_ac, self.missatge.emit)
            csv_seg = os.path.join(self.sortida, "segments.csv")
            self.missatge.emit("analitza 2/3: estructura (Segmentino)...")
            pipeline.extract_segments(self.wav, csv_seg, self.missatge.emit)
            abc = os.path.join(self.sortida, "estructura_ABC.csv")
            self.missatge.emit("analitza 3/3: ABC...")
            pipeline.fer_abc(csv_seg, abc, self.bpm, self.missatge.emit)
            self.feta.emit(True, csv_ac, abc)
        except Exception as e:  # noqa: BLE001
            self.feta.emit(False, str(e), "")


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
            "temps": temps, "pics": pics}


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
    def __init__(self, wav, acords, abc, bpm, bpb):
        super().__init__()
        self.setWindowTitle("Auto Chords — visor")
        self.resize(900, 600)
        self.wav_path = wav
        self.bpm, self.bpb = bpm, bpb
        self.offset = 0.0
        self.tempo_fix = True
        self.csv_acords = os.path.abspath(acords) if acords else None
        if not self.csv_acords:
            cand = os.path.join(self._carpeta_acords(), "acords.csv")
            if os.path.isfile(cand):
                self.csv_acords = cand
        try:
            self.audio = llegeix_wav(wav)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Visor", f"No puc obrir la wav: {e}")
            sys.exit(1)
        if not acords and self.csv_acords:
            acords = self.csv_acords
        self.acords = llegeix_acords(acords) if acords else []
        self.seccions = llegeix_abc(abc) if abc else []
        self.pos = 0.0  # segons

        arrel = QWidget()
        self.setCentralWidget(arrel)
        capa = QVBoxLayout(arrel)

        # ona
        self.corba = pg.PlotWidget()
        self.corba.setLabel("bottom", "segons")
        self.corba.plot(self.audio["temps"], self.audio["pics"], pen="#8ab4f8")
        self.cursor = pg.InfiniteLine(pos=0, angle=90, pen="#ff5252")
        self.corba.addItem(self.cursor)
        self.corba.scene().sigMouseClicked.connect(self._clic_ona)
        capa.addWidget(self.corba, stretch=3)

        # llistes + controls
        div = QSplitter(Qt.Horizontal)
        self.llista_ac = QListWidget()
        self.llista_ac.setToolTip("Clic: salta. Doble-clic: corregeix l'acord.")
        self._omple_llista_ac()
        self.llista_ac.itemClicked.connect(self._salt_acord)
        self.llista_ac.itemDoubleClicked.connect(self._edita_acord)
        div.addWidget(self.llista_ac)
        self.llista_ab = QListWidget()
        self.llista_ab.setContextMenuPolicy(Qt.CustomContextMenu)
        self._actualitza_llista_abc()
        self.llista_ab.itemClicked.connect(self._salt_seccio)
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
        self.b_obrir = QPushButton("Obre...")
        self.b_obrir.clicked.connect(self.obrir)
        self.b_analitza = QPushButton("🔍 Analitza")
        self.b_analitza.setToolTip("Chordino+Segmentino en segon pla i omple les llistes")
        self.b_analitza.clicked.connect(self.analitza)
        self.b_exporta = QPushButton("📦 Exporta")
        self.b_exporta.setToolTip("Genera locators, guia i wavs dels acords/estructura")
        self.b_exporta.clicked.connect(self.exporta)
        for b in (self.b_play, self.b_stop, self.b_menys, self.b_mes,
                  self.b_A, self.b_B, self.b_loop,
                  self.b_zm, self.b_zp, self.b_zt,
                  self.b_obrir, self.b_analitza, self.b_exporta):
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

    def _carpeta_acords(self):
        base = os.path.splitext(os.path.basename(self.wav_path))[0]
        return os.path.join(os.path.dirname(self.wav_path), base + "_ACORDS")

    def _omple_llista_ac(self):
        self.llista_ac.clear()
        for t, c, *_r in self.acords:
            self.llista_ac.addItem(f"{t:07.2f}s  {c}")

    def _edita_acord(self, item):
        fila = self.llista_ac.row(item)
        if fila < 0 or fila >= len(self.acords):
            return
        t, vell, *rest = self.acords[fila]
        tsrc = rest[0] if rest else f"{t:.9f}"
        nou, ok = QInputDialog.getText(
            self, "Corregeix l'acord",
            f"Acord a {t:.2f} s (abans: {vell})",
            text=vell)
        if not ok:
            return
        nou = nou.strip().replace(os.sep, "-").replace("\\", "-")
        if not nou or nou == vell:
            return
        self.acords[fila] = (t, nou, tsrc)
        self._omple_llista_ac()
        self.llista_ac.setCurrentRow(fila)
        try:
            nwavs = self._desa_i_regenera()
        except Exception as e:  # noqa: BLE001
            self.acords[fila] = (t, vell, tsrc)
            self._omple_llista_ac()
            self.llista_ac.setCurrentRow(fila)
            self.log(f"edició ERROR: {e}")
            QMessageBox.warning(self, "Visor",
                                f"No s'ha pogut desar l'acord:\n{e}")
            return
        self.log(f"acord {t:.2f}s: {vell} → {nou} "
                 f"(csv + {nwavs} wavs_acords)")

    def _desa_i_regenera(self):
        sortida = self._carpeta_acords()
        os.makedirs(sortida, exist_ok=True)
        self.csv_acords = os.path.join(sortida, "acords.csv")
        pipeline.desa_acords_csv(self.csv_acords, self.acords)
        self.log(f"desat {self.csv_acords}")
        n = pipeline.regenera_wavs_acords(
            self.csv_acords, sortida, self.bpm, self.bpb, self.offset,
            self.audio["durada"], 44100, self.log, self.tempo_fix)
        return n

    def log(self, msg):
        print(f"[visor] {msg}", flush=True)
        self.registre.append(msg)

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
        self._pinta_loop()

    def marca_B(self):
        self.loop_b = self.pos
        self.log(f"loop B = {self.loop_b:.2f}s")
        self._pinta_loop()

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
        for attr in ("_regio_loop",):
            if hasattr(self, attr):
                self.corba.removeItem(getattr(self, attr))
        if self.loop_a is not None and self.loop_b is not None \
                and self.loop_b > self.loop_a:
            self._regio_loop = pg.LinearRegionItem(
                values=(self.loop_a, self.loop_b),
                brush=pg.mkBrush(138, 180, 248, 40))
            self.corba.addItem(self._regio_loop)

    def zoom(self, factor):
        vb = self.corba.getViewBox()
        x0, x1 = vb.viewRange()[0]
        centre = self.pos
        ampl = (x1 - x0) * factor
        ampl = max(5.0, min(ampl, self.audio["durada"]))
        vb.setXRange(max(0, centre - ampl / 2), centre + ampl / 2,
                     padding=0)

    def zoom_tot(self):
        self.corba.getViewBox().setXRange(0, self.audio["durada"], padding=0)

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

    # navegació
    def ves_a(self, t):
        self.pos = max(0.0, min(t, self.audio["durada"]))
        self.cursor.setPos(self.pos)
        self.lliscador.setValue(int(self.pos * 100))
        self.temps.setText(f"{self._fmt(self.pos)} / {self._fmt(self.audio['durada'])}")
        if self.sona:
            self._atura_proc()
            self._engega_des_de(self.pos)

    def _clic_ona(self, ev):
        if ev.double():
            vb = self.corba.getViewBox()
            pt = vb.mapSceneToView(ev.scenePos())
            self.ves_a(pt.x())

    def _salt_acord(self, item):
        self.ves_a(float(item.text().split("s")[0]))

    def _actualitza_llista_abc(self):
        self.llista_ab.clear()
        for ini, fi, L, fam in self.seccions:
            self.llista_ab.addItem(f"{L} ({fam})  {ini:07.2f}s–{fi:07.2f}s")

    def _salt_seccio(self, item):
        self.ves_a(float(item.text().split("  ")[1].split("s")[0]))

    def _menu_seccio(self, pos):
        if not self.seccions:
            return
        idx = self.llista_ab.indexAt(pos).row()
        if idx < 0:
            return
        ini, fi, _L, _fam = self.seccions[idx]
        menu = QMenu(self)
        partir = menu.addAction("Partir secció aquí")
        fusionar_prev = menu.addAction("Fusionar amb anterior")
        fusionar_next = menu.addAction("Fusionar amb següent")
        accio = menu.exec_(self.llista_ab.mapToGlobal(pos))
        if accio is None:
            return
        if accio == partir:
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
                QMessageBox.warning(self, "Visor",
                                    f"No s'ha pogut partir la secció:\n{e}")
        elif accio == fusionar_prev:
            try:
                self.seccions = pipeline.fusiona_seccions(self.seccions, idx, amb="anterior")
                self._actualitza_llista_abc()
                self._regenera_abc_des_de_totes_les_seccions("seccions fusionades amb anterior")
            except Exception as e:  # noqa: BLE001
                QMessageBox.warning(self, "Visor",
                                    f"No s'ha pogut fusionar amb anterior:\n{e}")
        elif accio == fusionar_next:
            try:
                self.seccions = pipeline.fusiona_seccions(self.seccions, idx, amb="seguent")
                self._actualitza_llista_abc()
                self._regenera_abc_des_de_totes_les_seccions("seccions fusionades amb següent")
            except Exception as e:  # noqa: BLE001
                QMessageBox.warning(self, "Visor",
                                    f"No s'ha pogut fusionar amb següent:\n{e}")

    def _regenera_abc_des_de_totes_les_seccions(self, msg):
        sortida = self._carpeta_acords()
        os.makedirs(sortida, exist_ok=True)
        abc = os.path.join(sortida, "estructura_ABC.csv")
        pipeline.desa_abc_csv(abc, self.seccions, self.bpm, self.log,
                              lliure=not self.tempo_fix)
        pipeline.regenera_wavs_estructura(abc, sortida, 44100, self.log)
        self.log(f"ABC recalculat: {msg}")

    def _salt_lliscador(self, v):
        self.ves_a(v / 100.0)

    # escolta
    def _engega_des_de(self, t):
        self._atura_proc()
        inici = int(t * self.audio["sr"]) * 2  # 16 bits mono
        dades = self._mono_bytes()[inici:]
        self.log(f"play des de {t:.2f}s ({len(dades)} bytes) amb {self.player}...")
        self.fitxer_err = "/tmp/opencode/visor_player.log"
        try:
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
        if self.proc is not None:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
            except Exception:  # noqa: BLE001
                pass
            try:
                self.proc.wait(timeout=2)
            except Exception:  # noqa: BLE001
                try:
                    os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
                except Exception:  # noqa: BLE001
                    pass
        self.proc = None

    def play_stop(self):
        if self.sona:
            self.log(f"stop a {self.pos:.2f}s")
            self._atura_proc()
            self.rellotge.stop()
            self.sona = False
            self.b_play.setText("▶ Escolta")
        else:
            self._engega_des_de(self.pos)
            if self.proc is None:
                return
            self.rellotge.start()
            self.sona = True
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
        self.cursor.setPos(t)
        self.lliscador.setValue(int(t * 100))
        self.temps.setText(f"{self._fmt(t)} / {self._fmt(self.audio['durada'])}")
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

    def obrir(self):
        ruta, _ = QFileDialog.getOpenFileName(self, "Tria la wav", "",
                                              "Àudio WAV (*.wav)")
        if ruta:
            QMessageBox.information(
                self, "Visor",
                "Tanca i torna a obrir amb:\n.venv/bin/python app/visor.py " + ruta)

    def analitza(self):
        base = os.path.splitext(os.path.basename(self.wav_path))[0]
        sortida = os.path.join(os.path.dirname(self.wav_path), base + "_ACORDS")
        self.log(f"analitza → {sortida} (fil en segon pla)...")
        self.b_analitza.setEnabled(False)
        self.feina = FeinaAnalitza(self.wav_path, sortida, self.bpm)
        self.feina.missatge.connect(self.log)
        self.feina.feta.connect(self._analitza_feta)
        self.feina.start()

    def _analitza_feta(self, ok, csv_ac, abc):
        self.b_analitza.setEnabled(True)
        if not ok:
            self.log(f"analitza ERROR: {csv_ac}")
            QMessageBox.warning(self, "Visor", f"No s'ha pogut analitzar:\n{csv_ac}")
            return
        self.csv_acords = os.path.abspath(csv_ac)
        self.acords = llegeix_acords(csv_ac)
        self.seccions = llegeix_abc(abc)
        self._omple_llista_ac()
        self.llista_ab.clear()
        for ini, fi, L, fam in self.seccions:
            self.llista_ab.addItem(f"{L} ({fam})  {ini:07.2f}s–{fi:07.2f}s")
        self.etiqueta.setText(f"{self.audio['durada']:.1f} s · "
                              f"{len(self.acords)} acords · "
                              f"{len(self.seccions)} seccions")
        self.log(f"analitza FET: {len(self.acords)} acords, "
                 f"{len(self.seccions)} seccions — ja pots navegar")

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
                                      self.log, lliure=not self.tempo_fix)
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
        super().closeEvent(ev)
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
