#!/usr/bin/env python3
# visor.py — Visor navegable (ona + acords + estructura + escolta + edició).
# Tot en català. Dependències aïllades: PyQt5 + numpy<2 (Q9400).
# Ús: .venv/bin/python -m app.visor tema.wav [--acords acords.csv] [--abc estructura_ABC.csv] [--bpm 138] [--bpb 4]
import argparse
import copy
import csv
import logging
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import wave

from PyQt5.QtCore import QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QCursor, QKeySequence
from PyQt5.QtWidgets import (
    QApplication, QDialog, QFileDialog, QHBoxLayout, QInputDialog, QLabel,
    QListWidget, QMainWindow, QMenu, QMessageBox, QPushButton, QShortcut,
    QSlider, QSplitter, QTextEdit, QVBoxLayout, QWidget,
    QLineEdit,
)

import numpy as np

APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
import metronom  # noqa: E402
# UN SOL objecte per mòdul: els imports crus (`import pipeline`) creaven un
# objecte DIFERENT del que veuen main.py i els tests → estat divergent i
# monkey-patching que no funciona (ho va caçar `test_imports_unificats`).
# Forma d'execució suportada: `python -m app.visor` (el directe ja demana
# l'arrel al sys.path per altres imports relatius d'aquest fitxer).
from . import graella, icones, pipeline, theme  # noqa: F401
from . import acord_audio  # noqa: E402
from . import dialegs  # noqa: E402
from . import tempo_map  # noqa: E402
from .timeline import TimelineView  # noqa: E402

# Configuració centralitzada per al directori temporal (configurable)
from .config import TEMP_DIR as OPENCODE_DIR
from . import plataforma  # noqa: E402
from . import audio_out  # noqa: E402

VISOR_STYLESHEET = theme.visor_stylesheet()

N_BUCKETS = 2000  # pics precalculats: obrir 250 s és instantani

# A partir de quant avisem que el fitxer és MOLT llarg: el visor carrega el PCM
# sencer a memòria (`raw` + la còpia `mono`) → ~3× la mida del fitxer (prova
# real: 1 h ≈ 2 GB de pic; als 8 GB va, però 2 h+ potser no).
LLARG_MIN_S = 45 * 60


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


def nom_acord(it):
    """Nom d'un clip d'acord (`Clip(ini, fi, payload)`) o d'una marca `(t, nom[, tsrc])`."""
    return pipeline.nom_d_acord(it)


def llegeix_acords(ruta):
    # Model d'acords com a CLIPS `inici,fi,acord` (S3+S4). El `fi` de la columna
    # 2 és el de la cadena de fronteres (es re-deriva a la normalització); el
    # `payload` duu (nom, tsrc).
    items = []
    with open(ruta, encoding="utf-8") as f:
        for fila in csv.reader(f):
            if len(fila) < 3 or fila[0].startswith("posici") \
                    or fila[0].startswith("inici"):
                continue
            try:
                items.append(pipeline.Clip(
                    float(fila[0]), float(fila[1]),
                    (fila[2].strip(), fila[0])))
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
    # Els `except Exception` d'aquesta classe protegeixen accions de l'usuari:
    # sempre registren l'error i/o mostren un diàleg, mai l'amaguen.
    # avisa la barra de fora (icona play/pause) quan canvia l'estat de so
    playStateChanged = pyqtSignal(bool)
    # avisa la barra de fora (botó 🔁) quan canvia l'estat del loop A-B: el loop
    # es pot activar SENSE tocar el botó (arrossegant el regle) → sense això el
    # botó quedava desactivat mentre el play ja feia loop.
    loopStateChanged = pyqtSignal(bool)
    # missatge per a la caixa d'informacio (desfer/refer, etc.)
    infoMissatge = pyqtSignal(str)
    canvis = pyqtSignal()      # el model (acords/seccions) ha canviat per edició
    def __init__(self, wav, acords, abc, bpm, bpb, tempo_fix=True, sortida=None):
        super().__init__()
        self.logger = logging.getLogger("auto_chords")
        self._embedded = False
        # Lock curt per protegir self.proc entre fils (timer + alimentacio + UI)
        self._proc_lock = threading.Lock()
        self.setWindowTitle("Auto Chords — visor")
        self.resize(900, 600)
        self.wav_path = wav
        # Carpeta de sortida (projecte autocontingut) DES DEL PRINCIPI: el
        # constructor pot desar CSV normalitzats (vegeu més avall) i, sense
        # això, anaven a la carpeta derivada del WAV
        # (`<projecte>/audio/AUTOCHORDS_…/`) → còpia estranya dins `audio/`.
        self.sortida = sortida or pipeline.carpeta_sortida(wav)
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
        # Roadmap §14.1 — «treballar SENSE analitzar»: si el model ve BUIT (cap
        # anàlisi encara), es crea el punt de partida editable: **1 clip
        # d'acords i 1 d'estructura** que cobreixen tota la cançó. L'anàlisi
        # (Chordino/qm) passa a ser OPCIONAL, mai un requisit previ.
        nou_model = False
        if not self.acords and not self.seccions:
            self.acords, self.seccions = pipeline.model_inicial(
                self._durada_wav(), log=self.log)
            nou_model = True
        # INVARIANT de COBERTURA (regla d'or): els clips cobreixen TOTA la WAV
        # (0 → durada): 1r a 0 (capçalera «N» si cal) i últim a la durada.
        # Els ACORDS ara són **clips** (S4): es normalitzen amb `normalitza_clips`.
        _a0, _s0 = list(self.acords), list(self.seccions)
        self.acords = pipeline.normalitza_clips(
            self.acords, self._durada_wav(), pipeline.FORAT_ACORD,
            arrodoneix=True, deriva_fi=True, log=self.log)
        _, self.seccions = pipeline.normalitza_cobertura(
            [], self.seccions, self._durada_wav(), log=self.log)
        # Mapa de TEMPO i COMPÀS (fase 2): dels CSVs del projecte o, si no n'hi
        # ha, un **sol tros** amb el BPM·compàs actual (zero canvi visible).
        self.tempo_trams = pipeline.llegeix_tempo_map(
            self._carpeta_acords(), self.bpm, self.bpb, 4, self._durada_wav())
        self.tempo_map = None
        self._refresca_tempo_map()
        # Si la normalització ha canviat el model (forats interns, capçalera
        # «N», últim fi acotat…), el CSV DEL DISC s'ha de normalitzar JA: abans
        # hi quedava el defecte fins a la 1a edició o export. I si el model és
        # NOU (sense anàlisi), s'ha de desar igualment.
        if nou_model or self.acords != _a0 or self.seccions != _s0:
            self._desa_csvs_base()
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
        self.timeline.escapePressed.connect(self._on_escape_pressed)
        self.timeline.chordTimeMoved.connect(self._on_chord_time_moved)
        self.timeline.chordEndMoved.connect(self._on_chord_end_moved)
        self.timeline.chordRenamed.connect(self._on_chord_renamed)
        self.timeline.chordDeleteRequested.connect(self._elimina_acord_index)
        self.timeline.chordDuplicateRequested.connect(self._duplica_acord_index)
        self.timeline.chordCopyRequested.connect(self._on_chord_copia)
        self.timeline.chordEditRequested.connect(self._on_chord_edit_requested)
        self.timeline.sectionMoved.connect(self._on_section_moved)
        self.timeline.sectionRenamed.connect(self._on_section_renamed)
        self.timeline.sectionDeleteRequested.connect(self._elimina_seccio_index)
        self.timeline.sectionDuplicateRequested.connect(self._duplica_seccio_index)
        self.timeline.sectionCopyRequested.connect(self._on_section_copia)
        self.timeline.multiDeleteRequested.connect(self._elimina_seleccio)
        self.timeline.pasteRequested.connect(self._enganxa_seleccio)
        self.timeline.groupDuplicateRequested.connect(self._duplica_seleccio)
        self.timeline.clipContextMenuRequested.connect(
            self._on_clip_context_menu)
        # Pista de BPM/compàs (editable)
        self.timeline.tempoEditRequested.connect(self._on_tempo_edit)
        self.timeline.tempoChangeMoved.connect(self._on_tempo_mogut)
        self.timeline.tempoMenuRequested.connect(self._on_tempo_menu)
        self.timeline.loopContextMenuRequested.connect(
            self._on_loop_context_menu)
        self.timeline.loopDoubleClicked.connect(self.selecciona_bloc_del_loop)
        self.timeline.sectionEditRequested.connect(self._on_section_edit_requested)
        # Dreceres de teclat: espai = play/pausa
        self._sc_play = QShortcut(QKeySequence(Qt.Key_Space), self)
        self._sc_play.activated.connect(self.play_stop)
        # NOTA: les dreceres de desfer/refer viuen a la FINESTRA PRINCIPAL
        # (menu Edita). Un QShortcut dins el visor incrustat no s'activa.

        capa.addWidget(self.timeline, stretch=4)

        # ---- FRANJA EDITOR: mostra en gran l'element seleccionat i permet
        #      editar-lo directament (Sense finestres emergents) ----
        self.editor = QWidget()
        self.editor.setObjectName("editor")
        _eh = QHBoxLayout(self.editor)
        _eh.setContentsMargins(8, 4, 8, 4)
        _eh.setSpacing(8)
        self.ed_icona = QLabel("—")
        self.ed_icona.setObjectName("ed_icona")
        self.ed_gran = QLabel("Selecciona un acord o una secció")
        self.ed_gran.setObjectName("ed_gran")
        _eh.addWidget(self.ed_icona)
        _eh.addWidget(self.ed_gran)
        _eh.addSpacing(12)
        _eh.addWidget(QLabel("Nom:"))
        self.ed_nom = QLineEdit()
        self.ed_nom.setMaximumWidth(90)
        self.ed_nom.setToolTip("Nom de l'acord o lletra de la secció")
        _eh.addWidget(self.ed_nom)
        self.ed_fam_lbl = QLabel("Família:")
        self.ed_fam = QLineEdit()
        self.ed_fam.setMaximumWidth(50)
        self.ed_fam.setToolTip("Família de la secció (p. ex. N, A, B)")
        _eh.addWidget(self.ed_fam_lbl)
        _eh.addWidget(self.ed_fam)
        _eh.addWidget(QLabel("Inici (s):"))
        self.ed_ini = QLineEdit()
        self.ed_ini.setMaximumWidth(70)
        self.ed_ini.setToolTip("Inici en segons")
        _eh.addWidget(self.ed_ini)
        _eh.addWidget(QLabel("≈"))
        self.ed_cb = QLineEdit()
        self.ed_cb.setMaximumWidth(50)
        self.ed_cb.setToolTip("Inici en compàs.beat (graella original)")
        _eh.addWidget(self.ed_cb)
        self.ed_aplica = QPushButton("Aplica")
        self.ed_aplica.setObjectName("principal")
        self.ed_aplica.setToolTip("Aplica els canvis (Enter)")
        self.ed_aplica.clicked.connect(self._aplica_editor)
        _eh.addWidget(self.ed_aplica)
        _eh.addStretch(1)
        for w in (self.ed_nom, self.ed_fam, self.ed_ini, self.ed_cb):
            w.returnPressed.connect(self._aplica_editor)
        capa.addWidget(self.editor)
        self._ed_kind = None
        self._ed_idx = -1
        self._actualitza_editor()

        # llistes + controls
        div = QSplitter(Qt.Horizontal)
        self.llista_ac = QListWidget()
        self.llista_ac.setContextMenuPolicy(Qt.CustomContextMenu)
        self.llista_ac.setToolTip("Clic: salta. Doble-clic: corregeix l'acord.")
        self._omple_llista_ac()
        self.llista_ac.itemClicked.connect(self._salt_acord)
        self.llista_ac.itemDoubleClicked.connect(
            lambda it: self._focus_editor("chord", self.llista_ac.row(it)))
        self.llista_ac.customContextMenuRequested.connect(self._menu_acord)
        div.addWidget(self.llista_ac)
        self.llista_ab = QListWidget()
        self.llista_ab.setContextMenuPolicy(Qt.CustomContextMenu)
        self._actualitza_llista_abc()
        self.llista_ab.itemClicked.connect(self._salt_seccio)
        self.llista_ab.itemDoubleClicked.connect(
            lambda it: self._focus_editor("section", self.llista_ab.row(it)))
        self.llista_ab.customContextMenuRequested.connect(self._menu_seccio)
        div.addWidget(self.llista_ab)
        # Les llistes viuen en un contenidor propi perque la finestra les
        # pugui posar en un tauler lateral («Inspector»). Si el visor va sol,
        # queden al mateix lloc de sempre.
        self.inspector = QWidget()
        _lay_insp = QVBoxLayout(self.inspector)
        _lay_insp.setContentsMargins(0, 0, 0, 0)
        _lay_insp.addWidget(div)
        capa.addWidget(self.inspector, stretch=2)

        fila = QHBoxLayout()
        self.b_play = QPushButton()
        self.b_play.setIcon(icones.ico("play"))
        self.b_play.setToolTip("Reprodueix / atura (Espai)")
        self.b_play.clicked.connect(self.play_stop)
        self.b_stop = QPushButton()
        self.b_stop.setIcon(icones.ico("square"))
        self.b_stop.setToolTip("Atura i torna a l'inici")
        self.b_stop.clicked.connect(self.stop_inici)
        self.b_menys = QPushButton("−10s")
        self.b_menys.clicked.connect(lambda: self.ves_a(self.pos - 10))
        self.b_mes = QPushButton("+10s")
        self.b_mes.clicked.connect(lambda: self.ves_a(self.pos + 10))
        self.b_A = QPushButton()
        self.b_A.setIcon(icones.ico("arrow-left-to-line"))
        self.b_A.setToolTip("Marca inici de loop")
        self.b_A.clicked.connect(self.marca_A)
        self.b_B = QPushButton()
        self.b_B.setIcon(icones.ico("arrow-right-to-line"))
        self.b_B.setToolTip("Marca fi de loop")
        self.b_B.clicked.connect(self.marca_B)
        self.b_loop = QPushButton()
        self.b_loop.setIcon(icones.ico("repeat-2"))
        self.b_loop.setCheckable(True)
        self.b_loop.setToolTip("Activa loop A-B")
        self.b_loop.clicked.connect(self.commuta_loop)
        self.b_zm = QPushButton()
        self.b_zm.setIcon(icones.ico("zoom-out"))
        self.b_zm.clicked.connect(lambda: self.zoom(2.0))
        self.b_zp = QPushButton()
        self.b_zp.setIcon(icones.ico("zoom-in"))
        self.b_zp.clicked.connect(lambda: self.zoom(0.5))
        self.b_zt = QPushButton()
        self.b_zt.setIcon(icones.ico("maximize"))
        self.b_zt.setToolTip("Zoom: veure tot el tema")
        self.b_zt.clicked.connect(self.zoom_tot)
        self.b_zs = QPushButton()
        self.b_zs.setIcon(icones.ico("focus"))
        self.b_zs.setToolTip("Zoom a la SELECCIÓ (ajusta la vista als clips seleccionats)")
        self.b_zs.clicked.connect(self.zoom_seleccio)
        for b in (self.b_play, self.b_stop, self.b_menys, self.b_mes,
                  self.b_A, self.b_B, self.b_loop,
                  self.b_zm, self.b_zp, self.b_zt, self.b_zs):
            fila.addWidget(b)
        # Encaixem la fila en un contenidor per poder-la AMAGAR quan el visor
        # va incrustat (aleshores el transport viu a la barra de la finestra).
        self.cont_transport = QWidget()
        self.cont_transport.setLayout(fila)
        capa.addWidget(self.cont_transport)

        fila2 = QHBoxLayout()
        self.lliscador = QSlider(Qt.Horizontal)
        self.lliscador.setRange(0, int(self.audio["durada"] * 100))
        self.lliscador.sliderMoved.connect(self._salt_lliscador)
        fila2.addWidget(self.lliscador, stretch=1)
        self.temps = QLabel("00:00 / 00:00")
        fila2.addWidget(self.temps)
        self.b_mut = QPushButton()
        self.b_mut.setIcon(icones.ico("volume-x"))
        self.b_mut.setObjectName("mute")
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
        # metrònom: clic mesclat al buffer (no afectat pel mute/volum cançó)
        self.metro_on = False
        self.metro_vol = 0.6
        self.loop_a = None
        self.loop_b = None
        self.loop_on = False

        # registre visible (i a consola amb flush: el que cal per depurar)
        self.registre = QTextEdit()
        self.registre.setReadOnly(True)
        self.registre.setMaximumHeight(110)
        self.registre.setStyleSheet("font-family: monospace; font-size: 11px;")
        capa.addWidget(self.registre)
        # AVÍS (no bloquejant, al panell) si el fitxer és MOLT llarg: el PCM
        # sencer viu a memòria (`raw` + `mono`) ≈ 3× la mida del fitxer
        # (prova real: 1 h ≈ 2 GB de pic).
        _dur = float(self.audio.get("durada", 0.0) or 0.0)
        if _dur > LLARG_MIN_S:
            self.log(f"⚠️ fitxer MOLT LLARG ({_dur/60:.0f} min): l'app carrega "
                     f"tot el PCM a memòria (~{_dur * 44100 * 2 * 2 * 3 / 1e9:.1f} "
                     "GB) i pot anar lenta")

        # escolta amb reproductor extern (QtMultimedia petava: Violació de
        # segment — les rodes PyQt5 no porten el plugin d'àudio del sistema).
        # paplay = PipeWire/Pulse natiu; aplay = ALSA. Sense cap dels dos no es
        # pot escoltar: l'app ho avisa i la resta funciona igual.
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
        self.log(f"player: {self.player or 'cap'} {' '.join(self.player_args)}")
        self._undo_init()   # estat inicial = base per a la primera operacio

    def _carpeta_acords(self):
        # El PROJECTE mana: si sabem la carpeta de sortida (projecte
        # autocontingut), és allà on van els CSV/export. Si no, es deriva del
        # WAV (comportament de llegat / visor standalone).
        return getattr(self, "sortida", "") or pipeline.carpeta_sortida(self.wav_path)

    def set_snap(self, on=None, divisio=None):
        """Snap de la graella: interruptor (`on`) i divisió (`divisio`, nom)."""
        if hasattr(self, "timeline"):
            self.timeline.set_snap(on=on, divisio=divisio)

    def _fmt_compas(self, s):
        if not self.tempo_fix:
            return f"{s:07.2f}s"
        # Mateixa graella que el regle: offset inclos i compassos negatius
        # (count-in) abans del compas 1.
        beat_len = 60.0 / self.bpm
        beats = (s - getattr(self, "offset", 0.0)) / beat_len
        compas = math.floor(beats / self.bpb) + 1
        beat = int(round(beats % self.bpb)) + 1
        if beat > self.bpb:
            compas += 1
            beat = 1
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
        # Preserva la fila seleccionada: _actualitza_temps() repobla la llista
        # i, sense aixo, el clear() en perdia la seleccio (bug: clicar una
        # fila no la deixava ressaltada perque ves_a()->_actualitza_temps()).
        cur = self.llista_ac.currentRow()
        self.llista_ac.clear()
        for _a in self.acords:
            t, c = float(_a[0]), nom_acord(_a)
            et = self._fmt_compas(t) if self.tempo_fix else f"{t:07.2f}s"
            self.llista_ac.addItem(f"{et}  {c}")
        if 0 <= cur < self.llista_ac.count():
            self.llista_ac.setCurrentRow(cur)

    def _valida_canvis_acords(self, items):
        """Valida i DERIVA el `fi` dels clips d'acord (S4).

        Mateixes regles que abans (ordre estricte per inici, sense duplicats ni
        xocs a la resolució del CSV, dins de la WAV), ara sobre clips: accepta
        clips `Clip(ini, fi, payload)` o marques `(t, nom[, tsrc])` i retorna
        clips amb el `fi` re-derivat de la cadena de fronteres.
        """
        if not items:
            return []
        durada = self._durada_wav()
        ordenats = sorted(items, key=lambda x: float(x[0]))
        n = len(ordenats)
        out = []
        prev_t, prev_nom = None, None
        for i, item in enumerate(ordenats):
            t = float(item[0])
            nom = nom_acord(item)
            if t < 0:
                raise ValueError(f"L'acord {nom} té un inici negatiu ({t:.2f}s)")
            # TOPALL superior: un acord al final de la WAV (o més enllà)
            # quedaria amb durada <= 0 i trencaria l'invariant de cobertura (#4).
            if durada > 0 and t >= durada - pipeline.TOL_TEMPS:
                raise ValueError(
                    f"L'acord {nom} no cap dins de la WAV ({t:.2f}s; la WAV "
                    f"fa {durada:.2f}s)")
            if prev_t is not None:
                if t <= prev_t + 1e-9:
                    raise ValueError(
                        "Els acords no poden compartir ni invertir el seu inici. "
                        "L'ordre ha de ser estricte i sense solapaments."
                    )
                # Resolució del CSV: dos inicis a menys de 10 ms cauen a la
                # MATEIXA fila del CSV (2 decimals) i el primer quedaria amb un
                # clip de durada ~0 a l'export (trenca #1/#2 a nivell de CSV).
                if t - prev_t < pipeline.RESOLUCIO_CSV - 1e-9:
                    raise ValueError(
                        f"Els acords {prev_nom} ({prev_t:.3f}s) i {nom} "
                        f"({t:.3f}s) estan a menys de "
                        f"{pipeline.RESOLUCIO_CSV * 1000:.0f} ms: al CSV "
                        f"({pipeline.TEMPS_DEC} decimals) quedarien al mateix "
                        f"instant i un clip tindria durada 0."
                    )
            prev_t, prev_nom = t, nom
            fi = float(ordenats[i + 1][0]) if i + 1 < n else durada
            payload = (tuple(item.payload) if isinstance(item, pipeline.Clip)
                       else tuple(item[1:]))
            out.append(pipeline.Clip(t, fi, payload))
        return out

    def _normalitza_acords(self, items=None):
        items = self.acords if items is None else items
        ordenats = self._valida_canvis_acords(items)
        if isinstance(items, list):
            self.acords = ordenats
        return ordenats

    def _afegeix_acord(self, t, nom):
        if nom is None:
            nom = "N"
        # Sanejat canònic (el mateix que l'export i el rename): separadors i
        # reservats de Windows passen a "-"; els noms habituals no canvien.
        nom = pipeline.saneja_nom_acord(nom)
        if not nom:
            return False
        item = (float(t), nom, f"{float(t):.9f}")
        nova = self._normalitza_acords(self.acords + [item])
        self.acords = nova
        if hasattr(self, "llista_ac"):
            self._omple_llista_ac()
        return True

    def _on_section_copia(self, ini, fi, lletra, familia):
        """`Ctrl+Shift`+arrossegar una **secció**: la secció viatja i a l'ORIGEN
        hi torna una còpia amb la **mateixa lletra i família**, sobre el mateix
        tram. (Paritat #11 amb els acords.)

        Les seccions cobreixen tota la cançó, així que la còpia **sobreviu** el
        tram: les vores es tallen i s'acoblen — la mateixa operació que fa un
        enganxament de secció (`_bloc_sobre_seccions`), reaprofitada.
        """
        durada = float(self.audio["durada"])
        ini0 = max(0.0, min(float(ini), durada))
        llargada = max(0.0, min(float(fi), durada) - ini0)
        if llargada <= 1e-6:
            return
        bloc = [(0.0, llargada, str(lletra), str(familia))]
        # (Sense desfer propi: s'aplega al de l'arrossegament → un sol Ctrl+Z
        # desfà el gest sencer. Paritat amb els acords.)
        try:
            noves = self._bloc_sobre_seccions(self.seccions, bloc, llargada,
                                              ini0, durada, 1e-6)
            cand = self._valida_canvis_seccions(noves)
        except ValueError as e:
            self.log(f"Ctrl+Shift+arrossegat (secció): no s'ha fet res ({e})")
            return
        self.seccions = cand
        self.timeline.set_data(self.acords, self.seccions)
        try:
            self._desa_i_regenera()
            self._regenera_abc_des_de_totes_les_seccions(
                "secció duplicada (Ctrl+Shift+arrossegar)")
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR: {e}")
        self.log(f"Ctrl+Shift+arrossegat (secció): còpia «{lletra}» a "
                 f"{ini0:.2f}s")

    def _on_chord_copia(self, t_original, nom):
        """`Ctrl+Shift`+arrossegar un clip d'acord: el clip viatja i **a
        l'ORIGEN hi torna una còpia** amb el mateix nom (duplicar, com als
        DAWs). Les seccions tenen el mateix gest (`_on_section_copia`).

        El model d'aquesta app són MARQUES, i el gest ja ha mogut la marca: per
        tant n'hi ha prou de tornar-ne a posar una a l'instant original. La
        cobertura de tota la cançó (regla d'or #4) es manté sola.
        """
        durada = float(self.audio["durada"])
        t = max(0.0, min(float(t_original), durada))
        # (Sense `_undo_marca`/`_undo_commit` propis: la còpia s'apleguen a
        # l'operació de desfer del mateix arrossegament, de manera que UN sol
        # Ctrl+Z desfà el gest sencer.)
        try:
            if not self._afegeix_acord(t, str(nom)):
                return
            self._normalitza_cobertura()
        except Exception as e:  # noqa: BLE001
            self.log(f"Ctrl+Shift+arrossegat: no s'ha pogut deixar la còpia ({e})")
            return
        self.timeline.set_data(self.acords, self.seccions)
        try:
            self._desa_i_regenera()
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR: {e}")
        self.log(f"Ctrl+Shift+arrossegat: còpia «{nom}» a {t:.2f}s")

    def _elimina_acord(self, idx):
        if idx is None:
            idx = getattr(self, "llista_ac", None).currentRow() if hasattr(self, "llista_ac") else -1
        if idx < 0 or idx >= len(self.acords):
            return False
        # Nucli únic `pipeline.elimina_acords` (§6.4): l'anterior s'estira; sense
        # anterior, hi va la «N»; si queda buit, la «N» canònica a 0.
        self.acords = pipeline.elimina_clips(
            self.acords, idx, self._durada_wav(), pipeline.FORAT_ACORD)
        if hasattr(self, "llista_ac"):
            self._omple_llista_ac()
        return True

    def _menu_acord(self, pos):
        # Regla d'or #11: MATEIX joc d'accions que el menú de les seccions.
        if not hasattr(self, "llista_ac"):
            return
        idx = self.llista_ac.indexAt(pos).row()
        menu = QMenu(self)
        afegir = menu.addAction("Afegeix acord aquí")
        partir = menu.addAction("Partir acord aquí")
        fusionar_prev = menu.addAction("Fusionar amb anterior")
        fusionar_next = menu.addAction("Fusionar amb següent")
        eliminar = menu.addAction("Elimina acord")
        n_sel = len({i for (k, i) in self.timeline.selected_keys()
                     if k == "chord"})
        reanomena = menu.addAction(
            f"Reanomena {n_sel} acords…" if n_sel >= 2 else "Reanomena acord…")
        te = 0 <= idx < len(self.acords)
        partir.setEnabled(te and idx + 1 < len(self.acords))
        fusionar_prev.setEnabled(te and idx > 0)
        fusionar_next.setEnabled(te and idx + 1 < len(self.acords))
        eliminar.setEnabled(te)
        reanomena.setEnabled(te or n_sel >= 1)
        accio = menu.exec_(self.llista_ac.mapToGlobal(pos))
        if accio is None:
            return
        if accio == afegir:
            nou, ok = QInputDialog.getText(self, "Afegeix acord",
                                            f"Acord a {self.pos:.2f} s", text="N")
            if not ok:
                return
            try:
                self._afegeix_acord(self.pos, nou)
                self._desa_i_regenera()
                self.log(f"afegit acord a {self.pos:.2f}s: {nou}")
            except Exception as e:  # noqa: BLE001
                self.log(f"ERROR: {e}")
                QMessageBox.warning(self, "Visor",
                                    f"No s'ha pogut afegir l'acord:\n{e}")
        elif accio == partir:
            self._parteix_acord_dialog(idx)
        elif accio == fusionar_prev:
            self.fusiona_acord(idx, "anterior")
        elif accio == fusionar_next:
            self.fusiona_acord(idx, "seguent")
        elif accio == eliminar:
            try:
                self._elimina_acord(idx)
                self._desa_i_regenera()
                self.log(f"eliminat acord {idx}")
            except Exception as e:  # noqa: BLE001
                self.log(f"ERROR: {e}")
                QMessageBox.warning(self, "Visor",
                                    f"No s'ha pogut eliminar l'acord:\n{e}")
        elif accio == reanomena:
            # >1 seleccionat → renom en bloc; si no, edita el clip del clic.
            if n_sel >= 2:
                self.renomena_seleccio()
            elif te:
                self._focus_editor("chord", idx)

    def _edita_acord(self, item):
        fila = self.llista_ac.row(item)
        if fila < 0 or fila >= len(self.acords):
            return
        t, vell = float(self.acords[fila][0]), nom_acord(self.acords[fila])
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

    def _durada_wav(self):
        """Durada de la WAV en segons (0.0 si no se sap).

        Va per `self.__dict__` A POSTA: hi ha tests que construeixen el Visor
        amb `__new__` sense `__init__`, i PyQt peta (`super-class __init__()…
        was never called`) en consultar-hi atributs que no existeixen.
        """
        return float((self.__dict__.get("audio") or {}).get("durada", 0.0) or 0.0)

    def _normalitza_cobertura(self):
        """Aplica l'INVARIANT de COBERTURA (regla d'or #4) al model VIU.

        Els clips (acords I estructura) han de cobrir **tota** la WAV
        (0 → durada): si el 1r element no arrenca a 0 s'hi afegeix una «N» a 0,
        i l'últim s'acota a la durada. Els acords ara són **clips** (S4), així
        que es normalitzen amb `normalitza_clips` (fi re-derivat de la cadena).

        Retorna `True` si el model ha canviat (perquè qui cridi refresqui).
        """
        a0 = list(self.acords)
        s0 = list(self.seccions)
        d = self._durada_wav()
        self.acords = pipeline.normalitza_clips(
            pipeline.clips_de_model(self.acords, d), d, pipeline.FORAT_ACORD,
            arrodoneix=True, deriva_fi=True, log=self.log)
        _, self.seccions = pipeline.normalitza_cobertura(
            [], self.seccions, d, log=self.log)
        return self.acords != a0 or self.seccions != s0

    def _desa_i_regenera(self):
        """Desa NOMÉS els CSV (l'edició és sobre text).

        Les wavs són l'ÚLTIM pas: es generen explícitament amb `exporta()`
        quan tot està revisat i editat. Mai a cada edició.

        ⚠️ Abans de desar aplica l'**INVARIANT de COBERTURA** (regla d'or #4):
        així el CSV del disc mai no queda amb forats ni sense la «N» de
        capçalera, passi el que passi amb l'edició en viu. Si el model ha
        canviat, refresca el timeline i les llistes perquè el visor hi quadri.
        """
        if self._normalitza_cobertura():
            self.timeline.set_data(self.acords, self.seccions)
            self._omple_llista_ac()
            self._actualitza_llista_abc()
        self._desa_csvs_base()
        self.canvis.emit()   # edició del model → el projecte queda «brut»
        return 0

    def _refresca_tempo_map(self):
        """(Re)construeix `self.tempo_map` a partir de `self.tempo_trams`.

        El mapa és la font del tempo/compàs variables (fase 2: només persistència;
        la graella encara fa servir `self.bpm`/`self.bpb`). Sense trossos, se'n
        crea un de sol amb el BPM·compàs actual.
        """
        from app.tempo_map import TempoMap
        trams = list(self.tempo_trams or [])
        d = self._durada_wav()
        den = int(getattr(self, "beat_type", 4) or 4)
        if len(trams) <= 1:
            # Un sol tros = el cas constant d'avui.
            trams = [(0.0, d, float(self.bpm), int(self.bpb), den)]
        else:
            # El tram 0 és el VALOR INICIAL (el transport mana).
            t0 = trams[0]
            trams[0] = (float(t0[0]), float(t0[1]), float(self.bpm),
                        int(self.bpb), den)
        self.tempo_trams = trams
        self.tempo_map = TempoMap(trams, offset=getattr(self, "offset", 0.0))
        return self.tempo_map

    def aplica_tempo_trams(self, trams):
        """Aplica un mapa de tempo/compàs nou (des del diàleg).

        Normalitza (contigu, cobreix la WAV), actualitza el **transport** amb el
        valor inicial, reconstrueix el mapa, refresca el timeline i desa. Retorna
        `True` si s'ha aplicat.
        """
        from app.tempo_map import normalitza_trams
        nous = normalitza_trams(trams, self._durada_wav())
        if not nous:
            return False
        self.bpm = float(nous[0][2])
        self.bpb = int(nous[0][3])
        self.beat_type = int(nous[0][4])
        self.tempo_trams = nous
        self._refresca_tempo_map()
        if hasattr(self, "timeline"):
            self.timeline.set_tempo_mode(
                self.tempo_fix, self.bpm, self.bpb,
                getattr(self, "offset", 0.0), mapa=self.tempo_map)
        try:
            pipeline.desa_tempo_map(self._carpeta_acords(), self.tempo_trams)
        except Exception as e:  # noqa: BLE001
            self.log(f"desa mapa tempo/compàs ERROR: {e}")
        self.log(f"mapa de tempo/compàs: {len(nous)} tros(s)")
        return True

    def _on_tempo_edit(self, idx):
        """Clic a un bloc de BPM/compàs → diàleg per editar-ne el valor."""
        trams = list(self.tempo_trams or [])
        if not (0 <= idx < len(trams)):
            return
        s = trams[idx]
        try:
            lbl = self.tempo_map.label(s[0]).split(".")[0]
        except Exception:  # noqa: BLE001
            lbl = None
        dlg = dialegs.DialegTramTempo(self, inici=s[0], bpm=s[2], num=s[3],
                                      den=s[4], inicial=(idx == 0),
                                      text_inici=lbl)
        if dlg.exec_() != QDialog.Accepted:
            return
        bpm, num, den = dlg.valors()
        nou = list(trams)
        nou[idx] = (s[0], s[1], bpm, num, den)
        self.aplica_tempo_trams(nou)

    def _on_tempo_mogut(self, idx, vora, t):
        """Vora d'un bloc de BPM/compàs arrossegada → mou on canvia."""
        trams = list(self.tempo_trams or [])
        if not (0 <= idx < len(trams)):
            return
        t = max(0.0, min(self._durada_wav(), float(t)))
        s = trams[idx]
        if vora == "ini":
            if idx == 0 or t >= s[1] - 0.02:
                return
            p = trams[idx - 1]
            nou = list(trams)
            nou[idx - 1] = (p[0], t, p[2], p[3], p[4])
            nou[idx] = (t, s[1], s[2], s[3], s[4])
        else:
            if idx + 1 >= len(trams) or t <= s[0] + 0.02:
                return
            n = trams[idx + 1]
            nou = list(trams)
            nou[idx] = (s[0], t, s[2], s[3], s[4])
            nou[idx + 1] = (t, n[1], n[2], n[3], n[4])
        self.aplica_tempo_trams(nou)

    def _on_tempo_menu(self, idx, t):
        """Menú contextual de la pista de BPM/compàs."""
        from app import tempo_map as tm
        # Mateixa estructura/redacció que el menú dels CLIPS (regla d'or #11).
        te = idx >= 0
        menu = QMenu(self)
        a_edit = menu.addAction("Reanomena (BPM/compàs)…")
        a_del = menu.addAction("Elimina")
        menu.addSeparator()
        a_part = menu.addAction("Parteix aquest tros aquí")
        menu.addSeparator()
        a_add = menu.addAction("Afegeix un canvi aquí")
        a_edit.setEnabled(te)
        a_del.setEnabled(idx > 0)
        a_part.setEnabled(te)
        acc = menu.exec_(QCursor.pos())
        if acc is None:
            return
        trams = list(self.tempo_trams or [])
        if acc == a_add or acc == a_part:
            # «Afegeix» i «Parteix aquí» són la mateixa operació al mapa (una
            # frontera nova al punt); «Parteix» la posa dins del tros clicat.
            self.aplica_tempo_trams(tm.afegeix_tall(trams, float(t)))
        elif acc == a_edit and idx >= 0:
            self._on_tempo_edit(idx)
        elif acc == a_del and idx > 0:
            self.aplica_tempo_trams(tm.elimina_tall(trams, idx))

    def _desa_csvs_base(self):
        """Desa els CSV d'acords i d'estructura (SENSE tocar la UI).

        Es pot cridar ABANS que existeixi el timeline (normalització en
        carregar) i és el que fa servir `_desa_i_regenera`.
        """
        sortida = self._carpeta_acords()
        os.makedirs(sortida, exist_ok=True)
        self.csv_acords = os.path.join(sortida, "acords.csv")
        pipeline.desa_acords_csv(self.csv_acords, self.acords,
                                 self._durada_wav())
        # L'estructura també (així el CSV de seccions del disc queda normalitzat).
        try:
            pipeline.desa_abc_csv(os.path.join(sortida, "estructura_ABC.csv"),
                                  self.seccions, self.bpm, self.log,
                                  lliure=not self.tempo_fix, bpb=self.bpb,
                                  offset=getattr(self, "offset", 0.0),
                                  mapa=getattr(self, "tempo_map", None))
        except Exception as e:  # noqa: BLE001
            self.log(f"desat ABC ERROR: {e}")
        # Mapa de tempo/compàs (fase 2): un sol tros → se sincronitza amb el
        # BPM·compàs actual (zero canvi visible); amb més trossos, es respecta.
        if len(self.tempo_trams) <= 1:
            self.tempo_trams = [(0.0, self._durada_wav(), float(self.bpm),
                                 int(self.bpb),
                                 int(getattr(self, "beat_type", 4) or 4))]
        try:
            pipeline.desa_tempo_map(sortida, self.tempo_trams)
        except Exception as e:  # noqa: BLE001
            self.log(f"desat tempo/compàs ERROR: {e}")
        self.log(f"desat CSV {self.csv_acords}")

    # ---------- Undo/Redo: el MODEL d'edició + la GRAELLA i el LOOP ----------
    # Mai toca les wavs generades (aquestes són l'últim pas, via exporta()).
    def _estat_edicio(self):
        """(acords, seccions) — el MODEL. El fa servir també el pont MCP."""
        return (copy.deepcopy(list(self.acords)),
                copy.deepcopy(list(self.seccions)))

    def _estat_temps(self):
        """Estat de la GRAELLA (BPM/compàs/offset) i del LOOP A-B.

        A1: desfer/refer també ha de tornar enrere aquests canvis (abans només
        el model, i canviar el BPM era irreversible).
        """
        return {
            "bpm": float(getattr(self, "bpm", 120.0)),
            "bpb": int(getattr(self, "bpb", 4)),
            "beat_type": int(getattr(self, "beat_type", 4)),
            "offset": float(getattr(self, "offset", 0.0)),
            "tempo_fix": bool(getattr(self, "tempo_fix", True)),
            "loop_a": getattr(self, "loop_a", None),
            "loop_b": getattr(self, "loop_b", None),
            "loop_on": bool(getattr(self, "loop_on", False)),
        }

    def _estat_complet(self):
        """Estat apilable pel desfer/refer: `(acords, seccions, temps)`."""
        return self._estat_edicio() + (self._estat_temps(),)

    def _aplica_temps(self, temps):
        """Restaura la graella/loop desats (i refresca la UI si ja existeix)."""
        for k in ("bpm", "bpb", "beat_type", "offset", "tempo_fix"):
            if temps.get(k) is not None:
                setattr(self, k, temps[k])
        self.loop_a, self.loop_b = temps.get("loop_a"), temps.get("loop_b")
        self.loop_on = bool(temps.get("loop_on", False))
        if hasattr(self, "timeline"):
            try:
                self._actualitza_temps()
            except Exception as e:  # noqa: BLE001
                self.log(f"desfer: no s'ha pogut refrescar la graella: {e}")
            try:
                self.timeline.set_loop(self.loop_a, self.loop_b)
            except Exception as e:  # noqa: BLE001
                self.log(f"desfer: no s'ha pogut refrescar el loop: {e}")
        # El botó 🔁 de la finestra ha de reflectir-ho.
        self.loopStateChanged.emit(self.loop_on)
        if hasattr(self, "_pinta_loop"):
            self._pinta_loop()

    def _undo_init(self):
        if not hasattr(self, "_undo_stack"):
            self._undo_stack = []
            self._redo_stack = []
            self._undo_base = self._estat_complet()
            self._undo_pending = None

    def _undo_touch_base(self):
        """La base = el darrer estat CONSOLIDAT (fora d'una operacio).

        S'actualitza cada cop que se sincronitza el model sense operacio
        pendent, aixi mai queda obsoleta (analisi, carrega, edicions fetes
        per camins que no passen per _undo_marca)."""
        if getattr(self, "_undo_pending", None) is None:
            self._undo_base = self._estat_complet()

    def _undo_reset(self):
        """Neteja l'historial (nou document / nova analisi)."""
        self._undo_stack = []
        self._redo_stack = []
        self._undo_base = self._estat_complet()
        self._undo_pending = None

    def _undo_marca(self):
        """Inici d'una operació d'edició: captura l'estat 'abans'."""
        self._undo_init()
        if self._undo_pending is None:
            self._undo_pending = self._undo_base

    def _undo_commit(self):
        """Tanca l'operació d'edició i l'apila si hi ha hagut canvi."""
        self._undo_init()
        ara = self._estat_complet()
        canvi = self._undo_pending is not None and ara != self._undo_pending
        if canvi:
            self._undo_stack.append(self._undo_pending)
            self._redo_stack.clear()
            self.log(f"undo: apilada (desfer={len(self._undo_stack)} "
                     f"refer={len(self._redo_stack)})")
        self._undo_base = ara
        self._undo_pending = None

    def _aplica_estat(self, estat):
        acords, seccions, temps = estat
        self.acords = copy.deepcopy(acords)
        self.seccions = copy.deepcopy(seccions)
        self.timeline.set_data(self.acords, self.seccions)
        self._aplica_temps(temps)
        self._omple_llista_ac()
        self._actualitza_llista_abc()
        try:
            self._desa_i_regenera()
        except Exception as e:  # noqa: BLE001
            self.log(f"undo: no s'ha pogut desar el CSV: {e}")

    def _descriu_canvi(self, abans, ara):
        """Descripcio curta del canvi entre dos estats (per a desfer/refer)."""
        # Ull: els bucles de sota fan servir t0/t1 per als temps dels clips, així
        # que els temps globals van amb un altre nom (tp0/tp1).
        ac0, se0, tp0 = abans
        ac1, se1, tp1 = ara
        if len(ac1) > len(ac0):
            return f"afegir un acord (ara {len(ac1)})"
        if len(ac1) < len(ac0):
            return "eliminar un acord"
        if len(se1) > len(se0):
            return f"afegir una secció (ara {len(se1)})"
        if len(se1) < len(se0):
            return "eliminar una secció"
        for a0, a1 in zip(ac0, ac1):
            if nom_acord(a0) != nom_acord(a1):
                return (f"reanomenar l'acord «{nom_acord(a0)}» → "
                        f"«{nom_acord(a1)}»")
            if abs(float(a0[0]) - float(a1[0])) > 1e-6:
                return (f"moure l'acord «{nom_acord(a1)}» "
                        f"({float(a0[0]):.2f}s → {float(a1[0]):.2f}s)")
        for (i0, f0, l0, fa0), (i1, f1, l1, fa1) in zip(se0, se1):
            if l0 != l1 or fa0 != fa1:
                return f"reanomenar la secció «{l0}» → «{l1}»"
            if abs(float(i0) - float(i1)) > 1e-6 or abs(float(f0) - float(f1)) > 1e-6:
                return (f"moure la secció «{l1}» "
                        f"({float(i0):.2f}s → {float(i1):.2f}s)")
        # A1: canvis de GRAELLA o de LOOP (que no toquen el model).
        if tp0.get("bpm") != tp1.get("bpm"):
            return f"canviar el BPM ({tp0['bpm']:g} → {tp1['bpm']:g})"
        if (tp0.get("bpb") != tp1.get("bpb")
                or tp0.get("beat_type") != tp1.get("beat_type")):
            return "canviar el compàs"
        if tp0.get("offset") != tp1.get("offset"):
            return (f"canviar l'offset ({tp0['offset']:.2f}s → "
                    f"{tp1['offset']:.2f}s)")
        if tp0.get("tempo_fix") != tp1.get("tempo_fix"):
            return "canviar el mode de temps (BPM·compàs / Lliure)"
        if ((tp0.get("loop_on"), tp0.get("loop_a"), tp0.get("loop_b"))
                != (tp1.get("loop_on"), tp1.get("loop_a"), tp1.get("loop_b"))):
            return "canviar el loop A-B"
        return "una edició"

    def undo(self):
        self._undo_init()
        self._undo_commit()  # tanca qualsevol operacio oberta
        if not self._undo_stack:
            self.log("DESFER: res a desfer")
            self.infoMissatge.emit("Desfer: no hi ha res a desfer")
            return
        abans = self._estat_complet()
        desti = self._undo_stack.pop()
        desc = self._descriu_canvi(abans, desti)   # el que fa el desfer
        self._redo_stack.append(abans)
        self._aplica_estat(desti)
        self.infoMissatge.emit(f"⟲ DESFER: {desc}")
        self._undo_base = self._estat_complet()
        self._undo_pending = None
        self.log(f"DESFER fet (desfer={len(self._undo_stack)} "
                 f"refer={len(self._redo_stack)})")

    def redo(self):
        self._undo_init()
        self._undo_commit()
        if not self._redo_stack:
            self.log("REFER: res a refer")
            self.infoMissatge.emit("Refer: no hi ha res a refer")
            return
        abans = self._estat_complet()
        desti = self._redo_stack.pop()
        desc = self._descriu_canvi(abans, desti)
        self._undo_stack.append(abans)
        self._aplica_estat(desti)
        self._undo_base = self._estat_complet()
        self._undo_pending = None
        self.log(f"REFER fet (desfer={len(self._undo_stack)} "
                 f"refer={len(self._redo_stack)})")
        self.infoMissatge.emit(f"⟳ REFER: {desc}")

    def log(self, msg):
        # La consola pot ser cp1252 (Windows) o no existir (app empaquetada
        # --windowed): un emoji no ha de fer caure mai res.
        try:
            print(f"[visor] {msg}", flush=True)
        except (UnicodeEncodeError, OSError, ValueError, AttributeError):
            pass
        if hasattr(self, "registre"):     # pot cridar-se abans de crear-lo
            self.registre.append(msg)
        try:
            import logging as _lg
            _lg.getLogger("auto_chords").info("VISOR: %s", msg)
        except Exception:  # noqa: BLE001
            # el logging no ha de fer caure mai el visor (no logem aquí: seria recursiu)
            pass

    def _tria_player(self):
        """Tria el motor de reproducció segons el SO (vegeu `app/plataforma.py`).

        macOS i Windows: **motor natiu** (`sounddevice`/PortAudio → CoreAudio a
        macOS, MME a Windows) **dins el procés** → no cal cap binari extern.
        Linux: reproductor extern `paplay` (PipeWire/Pulse) o `aplay` (ALSA) —
        els de qualsevol escriptori. Si no n'hi ha cap, retorna `(None, [])` i el
        visor ho avisa (missatge segons el SO); la resta de l'app funciona igual.
        """
        if plataforma.usa_audio_natiu():
            return (audio_out.NOM_NATIU, [])
        sr = self.audio["sr"]
        for nom in plataforma.candidats_reproductor():
            if not shutil.which(nom):
                continue
            if nom == "paplay":
                # --latency-msec=100 baixa el buffer del servidor (per defecte en
                # demana molt mes) -> el so arrenca abans i el cursor de paret
                # quadra millor amb el que se sent.
                return ("paplay", ["--raw", "--format=s16le",
                                   f"--rate={sr}", "--channels=1",
                                   "--latency-msec=100"])
            if nom == "aplay":
                return ("aplay", ["--format=S16_LE", f"--rate={sr}",
                                  "--channels=1", "-"])
        return (None, [])

    def toca_notes(self, notes, sr=None, preset=None):
        """Toca una llista de notes MIDI (audició d'un tipus d'acord).

        `preset` tria el timbre (vegeu `acord_audio.PRESETS`; per defecte, el
        piano elèctric Rhodes).

        Genera un **piano elèctric** sintetitzat (`acord_audio`: arpegi + bloc)
        i el reprodueix amb el MATEIX motor de sempre, en un **motor efímer**
        d'un sol ús → no toca el reproductor de la cançó. Retorna True si s'ha
        pogut engegar (mai aixeca: qualsevol error va al log).
        """
        notes = list(notes or [])
        if not notes:
            return False
        sr = int(sr or (self.audio or {}).get("sr") or 44100)
        # La síntesi (piano: parcials × cordes) pot trigar unes dècimes i
        # congelaria la interfície: es fa en un FIL, i el clic respon de
        # seguida. L'àudio el toca el mateix motor de sempre.
        if not hasattr(self, "_escoltes_fils"):
            self._escoltes_fils = []
        th = threading.Thread(target=self._escolta_al_fil,
                              args=(notes, sr, preset), daemon=True)
        th.start()
        self._escoltes_fils.append(th)
        self.log(f"escolta: {len(notes)} notes ({sr} Hz, {preset or acord_audio.PRESET_DEFECTE})")
        return True

    def _escolta_al_fil(self, notes, sr, preset):
        """Síntesi + reproducció de l'escolta (s'executa en un fil)."""
        try:
            pcm = acord_audio.pcm_escolta(notes, sr, preset=preset)
        except Exception as e:  # noqa: BLE001
            self.log(f"escolta ERROR (síntesi): {e}")
            return
        player, args = self._tria_player()
        if player is None:
            self.log("escolta: no hi ha cap reproductor d'àudio disponible")
            return
        self._neteja_escoltes()
        try:
            proc = audio_out.crea_motor(player, args, sr, subprocess.DEVNULL)
            proc.stdin.write(pcm)
            proc.stdin.close()          # el motor acaba la cua i surt sol
            self._escoltes.append(proc)
        except Exception as e:  # noqa: BLE001
            self.log(f"escolta ERROR: {e}")

    def _neteja_escoltes(self):
        """Treu els motors d'escolta ja acabats (evita processos zombis)."""
        vius = []
        for p in getattr(self, "_escoltes", []):
            try:
                if p.poll() is None:
                    vius.append(p)
                else:
                    p.atura()
            except Exception:  # noqa: BLE001
                pass
        self._escoltes = vius

    def _mono_bytes(self):
        """Mono 16 bits SENSE guany, cacat (es calcula un sol cop per fitxer).

        Convertir l'estereo a mono + copiar triga ~450 ms en temes llargs i
        es cridava a cada play/seek/reinici (congelava la GUI). Ara es guarda.
        El **volum/mute NO s'apliquen aquí**: els aplica en directe el fil
        d'alimentació (`_alimenta`), així es poden canviar SENSE reiniciar.
        """
        if getattr(self, "_mono_cache", None) is not None:
            return self._mono_cache
        mono = np.frombuffer(self.audio["raw"], dtype=np.int16)
        ch = self.audio["canals"]
        if ch > 1:
            mono = mono.reshape(-1, ch).mean(axis=1).astype(np.int16)
        self._mono_cache = mono.tobytes()
        return self._mono_cache

    # transports
    def stop_inici(self):
        era = self.sona
        if era:
            self.play_stop()
        self.ves_a(0.0)
        self.log("stop → inici")

    def marca_A(self):
        self._undo_marca()
        self.loop_a = self.timeline.snap(self.pos)
        self.log(f"loop A = {self.loop_a:.2f}s")
        if self.loop_b is not None:
            self.timeline.set_loop(self.loop_a, self.loop_b)
        if self.loop_on and getattr(self, "sona", False):
            self._alinea_cursor_loop(self.pos)   # moure A sonant: re-alinea
        self._undo_commit()

    def marca_B(self):
        self._undo_marca()
        self.loop_b = self.timeline.snap(self.pos)
        self.log(f"loop B = {self.loop_b:.2f}s")
        if self.loop_a is not None:
            self.timeline.set_loop(self.loop_a, self.loop_b)
        if self.loop_on and getattr(self, "sona", False):
            self._alinea_cursor_loop(self.pos)   # moure B sonant: re-alinea
        self._undo_commit()

    def _on_escape_pressed(self):
        """Esc al timeline, per ordre: (1) anul·la el **RANG en curs**, (2)
        **desactiva el loop**, (3) **buida la selecció**. Si no es compleix cap
        de les tres coses, NO fa res (ni ho diu)."""
        tl = self.timeline
        if getattr(tl, "_marquee", None) is not None:      # 1) rang en curs
            tl._marquee = None
            tl._marquee_ctrl = False
            tl.viewport().update()
            self.log("Esc: rang anul·lat")
            return
        if (getattr(tl, "_loop_drag", False)
                or getattr(tl, "_loop_mode", None)):       # 2) loop a mig fer
            # S'estava marcant/editant el loop amb el regle: es descarta i
            # es torna a com era abans de començar el gest.
            tl._loop_drag = False
            tl._loop_mode = None
            tl._loop_a, tl._loop_b = tl._loop_a0, tl._loop_b0
            tl._loop_a0 = tl._loop_b0 = tl._loop_t0 = None
            tl._update_loop_item()
            self.log("Esc: loop anul·lat (no s'ha acabat de marcar)")
            return
        if (getattr(self, "loop_on", False)
                or tl._loop_a is not None or tl._loop_b is not None):
            # 3) LOOP: es desactiva I s'ESBORRA — la caixa groga del timeline
            # ha de desaparèixer (si només aturéssim el playback, quedaria
            # pintada i semblaria que el loop encara hi és).
            self.set_loop(False)
            tl._loop_a = tl._loop_b = None
            tl._update_loop_item()
            self.loop_a = self.loop_b = None
            self.log("Esc: loop fora (desactivat i esborrat)")
            return
        if tl.selected_keys() or tl._sel[0]:               # 3) selecció
            tl.clear_selection()
            self.log("Esc: selecció buidada")
            return

    def set_loop(self, on):
        """Fixa l'estat del loop A-B (les barres de fora NO toquen b_loop)."""
        self._undo_marca()          # A1: el loop també és desfer/fer
        self.loop_on = bool(on)
        if self.loop_on and (self.loop_a is None or self.loop_b is None
                             or self.loop_b <= self.loop_a):
            self.log("loop: cal marcar A i B (B > A) primer")
            self.loop_on = False
        if hasattr(self, "b_loop") and self.b_loop.isChecked() != self.loop_on:
            self.b_loop.setChecked(self.loop_on)
        if self.loop_on and getattr(self, "sona", False):
            # Activar el loop MENTRES sona: el só hi salta tot sol (el feeder
            # llegeix `loop_on` en viu) → el cursor s'hi ha de posar també, o
            # queden desalineats («el que sona no és on el cursor és»).
            self._alinea_cursor_loop(self.pos)
        # Sincronitza el botó 🔁 de fora amb l'estat REAL (pot haver-se revertit
        # a OFF si faltaven A i B).
        self.loopStateChanged.emit(self.loop_on)
        self.log(f"loop {'ON' if self.loop_on else 'OFF'}")
        self._pinta_loop()
        self._undo_commit()

    def commuta_loop(self):
        self.set_loop(not self.loop_on)

    def _alinea_cursor_loop(self, t):
        """Alinea el CURSOR amb el só quan hi ha loop A/B actiu.

        `_alimenta` fa el salt pel seu compte («si el punt de generació queda
        fora del bucle, arrenca a `loop_a`»); aquest mètode fa el MATEIX amb la
        visualització: si `t` és FORA de `[loop_a, loop_b)`, el retorna muntat a
        `loop_a` i hi mou el cursor a l'instant (posició + timeline + lliscador +
        etiqueta de temps). Si el transport sona, re-ancora el rellotge perquè
        la visualització no derivi respecte al só. Retorna el `t` efectiu.
        """
        if (self.loop_on and self.loop_a is not None
                and self.loop_b is not None and self.loop_b > self.loop_a
                and not (self.loop_a <= t < self.loop_b)):
            t = float(self.loop_a)
            self.pos = t
            self.timeline.set_position(t, emit=False, snap=False)
            self.lliscador.setValue(int(t * 100))
            self.temps.setText(self._fmt_timeline(t))
            if getattr(self, "sona", False):
                self.t0_pos = t
                self.t0_mono = time.monotonic()
        return t

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

    def zoom_seleccio(self):
        """Ajusta la vista del timeline perquè es vegi tota la selecció."""
        if not self.timeline.selected_keys():
            self.log("Zoom selecció: no hi ha cap clip seleccionat "
                     "(fes Ctrl/Shift+clic al timeline).")
            return
        self.timeline.zoom_selection()
        self.log("Zoom a la selecció ✅")

    def _canvia_volum(self, v):
        # S'aplica en directe al fil d'alimentacio (vegeu _alimenta): NO
        # cal reiniciar el reproductor, aixi canviar el volum no fa cap tall.
        self.vol = v / 100.0

    def metro_disponible(self):
        """El metrònom només té sentit amb graella (mode BPM · compàs)."""
        return bool(self.tempo_fix)

    def set_metro(self, on):
        """Fixa l'estat del metrònom. Si sona, reinicia des de la posició."""
        on = bool(on)
        if on == self.metro_on:
            return
        self.metro_on = on
        self.log(f"metrònom {'ON' if self.metro_on else 'OFF'}")
        if self.sona:
            pos = self.pos
            self._atura_proc()
            self._engega_des_de(pos)

    def commuta_metro(self):
        """Activa/desactiva el metrònom. Si sona, reinicia des de la posició."""
        self.set_metro(not self.metro_on)

    def _canvia_vol_metro(self, v):
        """Volum del clic (0-100). Si sona, reinicia des de la posició."""
        self.metro_vol = max(0.0, min(1.0, v / 100.0))
        if self.sona:
            pos = self.pos
            self._atura_proc()
            self._engega_des_de(pos)

    def set_mut(self, on):
        """Fixa el mute (les barres de fora NO toquen b_mut)."""
        self.mut = bool(on)
        if hasattr(self, "b_mut") and self.b_mut.isChecked() != self.mut:
            self.b_mut.setChecked(self.mut)
        self.log(f"mute {'ON' if self.mut else 'OFF'}")
        # S'aplica en directe al fil d'alimentacio: sense reiniciar.

    def commuta_mut(self):
        self.set_mut(not self.mut)

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
        self._refresca_tempo_map()
        self.timeline.set_tempo_mode(self.tempo_fix, self.bpm, self.bpb,
                                     getattr(self, "offset", 0.0),
                                     mapa=self.tempo_map)
        # En mode Lliure el metrònom no té sentit: l'apaguem (i si sona,
        # reengega sense clic des de la posició actual).
        if not self.tempo_fix and getattr(self, "metro_on", False):
            self.set_metro(False)
        # Les llistes mostren la posicio en compassos -> cal repoblar-les
        # quan canvia la graella (offset/BPM/compas).
        self._omple_llista_ac()
        self._actualitza_llista_abc()
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
        """Loop A/B seleccionat al regle del timeline (1 cop per arrossegada)."""
        self._undo_marca()          # A1: el loop també és desfer/fer
        self.loop_a, self.loop_b = float(a), float(b)
        self.loop_on = True
        if hasattr(self, "b_loop"):
            self.b_loop.setChecked(True)
        # El botó 🔁 de la barra de fora ha de reflectir-ho (abans quedava
        # desactivat mentre el play ja feia loop).
        self.loopStateChanged.emit(True)
        self.log(f"loop A={a:.2f}s B={b:.2f}s")
        self._undo_commit()

    def _on_chord_renamed(self, idx, new_name):
        self._undo_marca()
        self._sync_timeline_acords()
        # El renom INLINE del timeline arriba amb el text cru: s'ha de sanejar
        # amb el mateix criteri que l'alta i l'export (si canvia, es corregeix
        # al model I al timeline perquè no divergeixin).
        net = pipeline.saneja_nom_acord(new_name)
        if net and 0 <= idx < len(self.acords) and nom_acord(self.acords[idx]) != net:
            nova = list(self.acords)
            _a = nova[idx]
            nova[idx] = pipeline.Clip(
                float(_a[0]), float(_a[1]), (net,) + tuple(_a[2][1:]))
            self.acords = nova
            self.timeline.set_data(self.acords, self.seccions)
        self._undo_commit()
        try:
            self._desa_i_regenera()
            self.log(f"acord {idx} reanomenat: {new_name}")
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR: {e}")
            QMessageBox.warning(self, "Visor", f"No s'ha pogut regenerar:\n{e}")
        self._refresca_post_edicio("chord", idx)

    def _on_chord_edit_requested(self, idx):
        # Doble-clic al ChordItem -> selecciona i enfoca la franja EDITOR
        # (sense cap finestra emergent).
        if idx < 0 or idx >= len(self.acords):
            return
        self._focus_editor("chord", idx)

    def _on_clip_context_menu(self, kind, idx, pos):
        """Menú contextual (botó dret) sobre un clip del timeline."""
        te_clip = idx is not None and idx >= 0
        menu = QMenu(self)
        a_dup = menu.addAction("Duplica")
        a_del = menu.addAction("Elimina")
        menu.addSeparator()
        a_ren = menu.addAction("Reanomena")
        menu.addSeparator()
        # A2 + regla d'or #11: partir pel cursor (en un model saturat és l'única
        # manera d'afegir-ne un de nou). Mateixa eina per a acord I secció.
        a_part = menu.addAction(
            "Parteix la secció…" if kind == "section" else "Parteix l'acord…")
        menu.addSeparator()
        a_ret = menu.addAction("Retalla")
        a_cop = menu.addAction("Copia")
        a_eng = menu.addAction("Enganxa")
        # desactivats si no hi ha cap clip seleccionat
        for a in (a_dup, a_del, a_ren):
            a.setEnabled(te_clip)
        a_part.setEnabled(te_clip)
        a_ret.setEnabled(te_clip)
        a_cop.setEnabled(te_clip)
        a_eng.setEnabled(self.timeline.has_clipboard())
        accio = menu.exec_(pos)
        if accio is None:
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
            # >1 seleccionat del mateix tipus → renom en bloc; si no, inline.
            n_same = len({i for (k, i) in self.timeline.selected_keys()
                          if k == kind})
            if n_same >= 2:
                self.renomena_seleccio()
            elif kind == "chord":
                self.timeline.chordEditRequested.emit(idx)
            else:
                self.timeline.sectionEditRequested.emit(idx)
        elif accio == a_part:
            if kind == "chord":
                self._parteix_acord_dialog(idx)
            else:
                self._parteix_seccio_dialog(idx)
        elif accio == a_ret:
            self.timeline.cut_selection()
        elif accio == a_cop:
            self.timeline.copy_selection()
        elif accio == a_eng:
            self.timeline.paste_at_cursor()

    def selecciona_bloc_del_loop(self):
        """Selecciona TOT el que hi ha dins el loop A/B i posa el cursor al final.

        Retorna quants clips s'han seleccionat (0 si no hi ha loop o és buit).
        És el pas previ de «Copia/Retalla el loop» i deixa el cursor al final
        perquè l'Enganxa següent hi caigui just després.
        """
        a, b = self.loop_a, self.loop_b
        if a is None or b is None or float(b) - float(a) <= 1e-9:
            self.log("loop: no hi ha cap loop definit (marca A i B al regle)")
            return 0
        keys = self.timeline.keys_dins_rang(float(a), float(b), inclou_fi=False)
        if not keys:
            self.log("loop: no hi ha cap clip dins del loop")
            return 0
        self.timeline.select_multi(keys)
        self.ves_a(float(b))          # cursor al FINAL del loop
        self.log(f"loop {float(a):.2f}–{float(b):.2f}s: {len(keys)} clip(s) "
                 f"seleccionats; cursor al final → ja pots enganxar")
        return len(keys)

    def _on_loop_context_menu(self, pos):
        """Botó dret dins de la banda del loop → copiar/retallar/enganxar el bloc."""
        if (self.loop_a is None or self.loop_b is None
                or float(self.loop_b) - float(self.loop_a) <= 1e-9):
            return
        menu = QMenu(self)
        a_cop = menu.addAction("Copia tot el que hi ha dins el loop")
        a_ret = menu.addAction("Retalla tot el que hi ha dins el loop")
        menu.addSeparator()
        a_eng = menu.addAction("Enganxa al cursor")
        a_eng.setEnabled(self.timeline.has_clipboard())
        accio = menu.exec_(pos)
        if accio is None:
            return
        if accio in (a_cop, a_ret):
            if not self.selecciona_bloc_del_loop():
                return
            if accio == a_cop:
                self.timeline.copy_selection()
            else:
                self.timeline.cut_selection()
            # copy/cut mouen el cursor al final del BLOC; el volem al final del
            # LOOP, perquè «Enganxa» hi caigui just després.
            self.ves_a(float(self.loop_b))
        elif accio == a_eng:
            self.timeline.paste_at_cursor()

    # --- nucli comú dels canvis d'un CARRIL (acords / estructura) -----------
    def _aplica_carril(self, kind, mut, missatge="", avisa=None):
        """Nucli ÚNIC dels canvis d'un carril (acords «chord» / estructura «section»).

        `mut(llista)` rep una còpia de la llista del carril i en retorna la nova
        (o `None` si no s'ha de fer res). Valida amb el validador del carril, fa
        UNA sola marca d'undo, assigna, refresca el timeline i la llista del
        carril, i desa (acords → CSV + wavs_acords; estructura → ABC). Un sol
        lloc per als despatxos que abans duplicaven acords i estructura (regla
        d'or #11). Retorna True si el canvi s'ha aplicat.
        """
        actual = self.acords if kind == "chord" else self.seccions
        nou = mut(list(actual))
        if nou is None:
            return False
        valida = (self._valida_canvis_acords if kind == "chord"
                  else self._valida_canvis_seccions)
        try:
            ordenat = valida(nou)
        except ValueError as e:
            self.log(f"{missatge or 'canvi'}: rebutjat ({e})")
            return False
        self._undo_marca()
        if kind == "chord":
            self.acords = ordenat
            if hasattr(self, "llista_ac"):
                self._omple_llista_ac()
        else:
            self.seccions = ordenat
            if hasattr(self, "llista_ab"):
                self._actualitza_llista_abc()
        self._undo_commit()
        self.timeline.set_data(self.acords, self.seccions)
        try:
            if kind == "chord":
                self._desa_i_regenera()
            else:
                self._regenera_abc_des_de_totes_les_seccions(
                    missatge or "canvi d'estructura")
            if missatge:
                self.log(missatge)
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR: {e}")
            if avisa:
                QMessageBox.warning(self, "Visor", f"{avisa}\n{e}")
            return False
        return True

    def _duplica_acord_index(self, idx):
        """Duplica l'acord idx: es parteix pel mig (nucli únic `duplica_acord`).

        El duplicat va JUST DESPRÉS i comparteix la durada de l'original (la
        meitat per a cadascun), així no cal desplaçar res i es mantenen els
        invariants. Regla d'or #11: mateix nucli que les seccions."""
        if idx < 0 or idx >= len(self.acords):
            return
        cand = pipeline.duplica_bloc_clips(
            self.acords, idx, idx, float(self.acords[idx].fi),
            self._durada_wav(), pipeline.FORAT_ACORD)
        if cand == list(self.acords):
            self.log(f"no es pot duplicar l'acord {idx}: no hi ha lloc")
            return
        self._aplica_carril("chord", lambda _L: cand,
                            f"duplicat acord {idx} (després, sobreescrivint)")

    def _duplica_seccio_index(self, idx):
        """Duplica la secció idx: es parteix en dues (nucli únic `duplica_seccio`).

        El duplicat va JUST DESPRÉS i comparteix la durada de l'original (la
        meitat per a cadascun), sense desplaçar els següents (manté els
        invariants). Regla d'or #11: mateix nucli que els acords."""
        if idx < 0 or idx >= len(self.seccions):
            return
        cand = pipeline.duplica_bloc_seccions(
            self.seccions, idx, idx, float(self.seccions[idx][1]),
            self._durada_wav())
        if cand == list(self.seccions):
            self.log(f"no es pot duplicar la secció {idx}: no hi ha lloc")
            return
        self._aplica_carril("section", lambda _L: cand,
                            f"secció {idx} duplicada (després, sobreescrivint)")

    def _duplica_seleccio(self, keys):
        """Duplica tots els clips de la multi-selecció en una sola operació.

        La còpia del bloc va DESPRÉS i **sobreescriu** el tram que ocupa (§2,
        §6.3/#11). Es calcula sobre còpies candidates i es valida ABANS de tocar
        el model."""
        keys = list(keys or [])
        idx_ac = sorted({int(i) for k, i in keys if k == "chord"}, reverse=True)
        idx_sec = sorted({int(i) for k, i in keys if k == "section"}, reverse=True)
        idx_ac = [i for i in idx_ac if 0 <= i < len(self.acords)]
        idx_sec = [i for i in idx_sec if 0 <= i < len(self.seccions)]
        if not idx_ac and not idx_sec:
            return
        durada = self._durada_wav()
        cand_ac = list(self.acords)
        if idx_ac:
            cand_ac = pipeline.duplica_bloc_clips(
                cand_ac, min(idx_ac), max(idx_ac),
                float(cand_ac[max(idx_ac)].fi), durada, pipeline.FORAT_ACORD)
        cand_sec = list(self.seccions)
        if idx_sec:
            cand_sec = pipeline.duplica_bloc_seccions(
                cand_sec, min(idx_sec), max(idx_sec),
                float(cand_sec[max(idx_sec)][1]), durada)
        try:
            cand_ac = self._valida_canvis_acords(cand_ac)
            if idx_sec:
                cand_sec = self._valida_canvis_seccions(cand_sec)
        except ValueError as e:
            self.log(f"duplica selecció: canvi invalid, no s'ha fet res ({e})")
            return
        self._undo_marca()
        self.acords = cand_ac
        if idx_sec:
            self.seccions = cand_sec
        self._undo_commit()
        self.timeline.set_data(self.acords, self.seccions)
        try:
            if idx_ac:
                self._desa_i_regenera()
            if idx_sec:
                self._regenera_abc_des_de_totes_les_seccions(
                    "selecció duplicada")
            self.log(f"duplicada la selecció "
                     f"({len(idx_ac)} acords, {len(idx_sec)} seccions)")
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR: {e}")
            QMessageBox.warning(self, "Visor", f"No s'ha pogut duplicar:\n{e}")

    def _elimina_acord_index(self, idx):
        if idx < 0 or idx >= len(self.acords):
            return
        self._aplica_carril(
            "chord",
            lambda L: pipeline.elimina_clips(L, idx, self._durada_wav(),
                                             pipeline.FORAT_ACORD),
            f"eliminat acord {idx}", "No s'ha pogut eliminar:")

    def _elimina_seccio_index(self, idx):
        if idx < 0 or idx >= len(self.seccions):
            return
        self._aplica_carril(
            "section",
            lambda L: pipeline.elimina_seccio(L, idx, self._durada_wav()),
            f"eliminada secció {idx}", "No s'ha pogut eliminar:")

    def _elimina_seleccio(self, keys):
        """Elimina tots els clips de la multi-selecció en una sola operació.

        Rep la llista [(kind, idx), ...] del TimelineView i resol l'esborrat
        d'una vegada: una única marca d'undo, esborrats en ordre descendent
        (perquè els índexs no es desplacin) i un sol `set_data` + regen."""
        keys = list(keys or [])
        idx_ac = sorted({int(i) for k, i in keys if k == "chord"}, reverse=True)
        idx_sec = sorted({int(i) for k, i in keys if k == "section"}, reverse=True)
        idx_tp = sorted({int(i) for k, i in keys if k == "tempo"}, reverse=True)
        idx_ac = [i for i in idx_ac if 0 <= i < len(self.acords)]
        idx_sec = [i for i in idx_sec if 0 <= i < len(self.seccions)]
        idx_tp = [i for i in idx_tp if 0 < i < len(self.tempo_trams or [])]
        if not idx_ac and not idx_sec and not idx_tp:
            return
        self._undo_marca()
        for i in idx_ac:
            self._elimina_acord(i)
        for i in idx_sec:
            self._elimina_seccio(i)
        if idx_tp:
            trams = list(self.tempo_trams or [])
            for i in idx_tp:
                trams = tempo_map.elimina_tall(trams, i)
            self.aplica_tempo_trams(trams)
        self._undo_commit()
        # INVARIANT #4 INSTANTANI: si l'esborrat ha deixat el model sense acords
        # (o sense estructura), s'hi torna a posar la marca canònica a 0 («N» /
        # «A»). Abans això només passava quan l'autosave desava, i mentrestant el
        # model quedava invàlid (0 clips): report de l'operador, 17-10-2026.
        self._normalitza_cobertura()
        self.timeline.set_data(self.acords, self.seccions)
        try:
            if idx_ac:
                self._desa_i_regenera()
            if idx_sec:
                self._regenera_abc_des_de_totes_les_seccions(
                    "selecció eliminada")
            self.log(f"eliminada la selecció "
                     f"({len(idx_ac)} acords, {len(idx_sec)} seccions)")
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR: {e}")
            QMessageBox.warning(self, "Visor",
                                f"No s'ha pogut eliminar:\n{e}")

    def _enganxa_seleccio(self, buf, at):
        """Enganxa el porta-retalls INTERN **sobreescrivint** una regió (Ctrl+V).

        Regla d'or #4: els clips cobreixen SEMPRE tota la WAV i la cançó no pot
        créixer → l'enganxat NO insereix: el bloc copiat **substitueix** el tram
        `[T, T+L]` de cada carril present (les vores es tallen i s'acoblen). Si
        el bloc sobrepassa el final, es **retalla**.

        Àncora `T`: el cursor; si el cursor NO s'ha mogut des de la còpia, el
        **final del bloc copiat** (enganxar just després). Tot en una sola
        operació de desfer, i després es deixa seleccionat el bloc enganxat.

        Snap de l'àncora, amb la prioritat dels DAWs professionals (Cubase
        `Snap Type`: Events · Grid · Cursor):
          1. **Events**: si el cursor cau a prop d'una marca del model (vora de
             clip), s'usa el SEU instant exacte. Imprescindible aquí perquè les
             marques vénen de l'anàlisi i NO són a la graella musical: arrodonir
             la vora que s'ha de substituir la deixava a 2 ms i la validació
             (≥ 10 ms) rebuixava l'operació sencera.
          2. **Graella** (BPM/offset) si no hi ha cap marca a prop.
          `Shift` (Ctrl+Shift+V) se salta el snap, com el «hold N» del Final Cut.
        El bloc viatja **rígid** (com `Grid Relative` del Cubase): no s'arrodoneix
        cada element, per no deformar l'espaiat intern de la còpia.
        """
        if not isinstance(buf, dict):
            return
        chords = list(buf.get("chords") or [])
        sections = list(buf.get("sections") or [])
        if not chords and not sections:
            return
        durada = float(self.audio["durada"])
        rel = 1e-6
        # -- àncora (prioritat dels DAWs: EVENTS → graella) --
        T = float(at)
        cc, bf = buf.get("cursor_copy"), buf.get("bloc_fi")
        if cc is not None and bf is not None and abs(T - float(cc)) <= 1e-6:
            T = float(bf)
        salta_snap = bool(QApplication.keyboardModifiers() & Qt.ShiftModifier)
        if (hasattr(self, "timeline") and self.timeline._snap_on
                and not salta_snap):
            # 1r) EVENTS: marca del model a prop → el seu instant EXACTE
            marca = self.timeline.snap_a_marca(T)
            if marca is not None:
                T = float(marca)
            else:
                # 2n) graella musical (BPM/offset)
                T = self.timeline.snap(T)
        T = max(0.0, min(T, durada))
        # El bloc viatja RÍGID: les posicions relatives copiades NO s'arrodoneixen
        # (equivalent al `Grid Relative` del Cubase o al «snap relative to grid»
        # del Reaper per als ítems que ja porten offset). Arrodonir cada element
        # deformava l'espaiat intern del bloc sense que ningú ho hagués demanat.

        # -- reconstrucció per carril (sobreescriptura) --
        nous_acords = (self._bloc_sobre_acords(
            self.acords, chords, float(buf.get("chord_len") or 0.0), T,
            durada, rel) if chords else None)
        noves_seccions = (self._bloc_sobre_seccions(
            self.seccions, sections, float(buf.get("section_len") or 0.0), T,
            durada, rel) if sections else None)
        # -- validació sense efectes (no assigna res) --
        try:
            cand_ac = (self._valida_canvis_acords(nous_acords)
                       if nous_acords is not None else list(self.acords))
            cand_sec = (self._valida_canvis_seccions(noves_seccions)
                        if noves_seccions is not None else list(self.seccions))
        except ValueError as e:
            self.log(f"enganxa: canvi invalid, no s'ha fet res ({e})")
            self.avis_editor(f"Enganxat no fet: {e}")
            return
        if cand_ac == self.acords and cand_sec == self.seccions:
            self.log("enganxa: res a fer")
            self.avis_editor("Enganxat: res a canviar (el bloc coincideix "
                             "amb el model actual).")
            return
        self._undo_marca()
        self.acords = cand_ac
        if noves_seccions is not None:
            self.seccions = cand_sec
        self._normalitza_cobertura()
        self._undo_commit()
        self.timeline.set_data(self.acords, self.seccions)
        try:
            self._desa_i_regenera()
            if sections:
                self._regenera_abc_des_de_totes_les_seccions("enganxat")
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR: {e}")
            QMessageBox.warning(self, "Visor", f"No s'ha pogut enganxar:\n{e}")
        self._selecciona_bloc_enganxat(T, chords, sections, tol=0.02)
        self.log(f"enganxat a {T:.2f}s (sobreescrivint): {len(chords)} "
                 f"acord(s), {len(sections)} secció(ns)")

    def _bloc_sobre_acords(self, acords, bloc, llargada, T, durada, rel):
        """Nova llista d'acords amb el bloc sobreescrit dins `[T, T+llargada]`.

        Els acords són marques (inici) amb final **derivat**: es mantenen les
        marques anteriors a `T`, s'hi posen les del bloc i s'assegura una marca a
        `T+llargada` (amb el nom del clip que hi havia) perquè l'últim acord
        copiat acabi exactament allà.
        """
        Te = min(T + float(llargada), durada)
        punts = []
        for (r, name) in bloc:
            t = T + float(r)
            if t < durada - rel:
                punts.append((t, str(name), f"{t:.9f}"))
        if not punts:
            return list(acords)
        # marca de tancament a Te
        marca = None
        for a in acords:
            if abs(float(a[0]) - Te) <= rel:
                marca = a
                break
        if marca is None and Te < durada - rel:
            after = None
            for a in acords:
                if float(a[0]) <= Te - rel:
                    after = a
                else:
                    break
            marca = (Te, str(nom_acord(after)) if after else punts[-1][1],
                     f"{Te:.9f}")
        nou = [a for a in acords if float(a[0]) < T - rel]
        nou += punts
        if marca is not None:
            if float(marca[0]) > float(punts[-1][0]) + pipeline.RESOLUCIO_CSV - 1e-6:
                nou.append(marca)
        nou += [a for a in acords if float(a[0]) > Te + rel]
        return nou

    def _bloc_sobre_seccions(self, seccions, bloc, llargada, T, durada, rel):
        """Nova llista de seccions amb el bloc sobreescrit dins `[T, T+llargada]`."""
        Te = min(T + float(llargada), durada)
        nou = []
        for (ini, fi, ll, fam) in seccions:
            ini, fi = float(ini), float(fi)
            if fi <= T + rel or ini >= Te - rel:
                nou.append((ini, fi, ll, fam))
                continue
            if ini < T - rel:              # part esquerra
                nou.append((ini, T, ll, fam))
            if fi > Te + rel:              # part dreta
                nou.append((Te, fi, ll, fam))
        for (ri, rf, ll, fam) in bloc:
            ini = T + float(ri)
            fi = min(T + float(rf), Te)
            if ini < durada - rel and fi - ini > rel:
                nou.append((ini, fi, str(ll), str(fam)))
        nou.sort(key=lambda s: float(s[0]))
        return [s for s in nou if float(s[1]) - float(s[0]) > rel]

    def _selecciona_bloc_enganxat(self, T, chords, sections, tol=0.02):
        """Deixa seleccionat el bloc acabat d'enganxar (acords i/o seccions)."""
        keys = set()
        for (r, _n) in chords:
            t = T + float(r)
            for i, a in enumerate(self.acords):
                if abs(float(a[0]) - t) <= tol:
                    keys.add(("chord", i))
                    break
        for (ri, _rf, _l, _f) in sections:
            ini = T + float(ri)
            for i, s in enumerate(self.seccions):
                if abs(float(s[0]) - ini) <= tol:
                    keys.add(("section", i))
                    break
        if keys and hasattr(self, "timeline"):
            self.timeline.select_multi(keys)

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
        self._refresca_post_edicio("section", idx)

    def _clips_per_renombrar(self):
        """(kind, índexs) del TIPUS ACTIU dins la selecció; `(None, [])` si no.

        Amb selecció **mixta** (acords + seccions) es renombren NOMÉS els del
        tipus del clip actiu (opció acordada): dins un full de càlcul tampoc no
        es barreja en una sola acció el contingut de files de tipus diferent.
        El clip «actiu» és el darrer seleccionat (`timeline._sel`).
        """
        keys = self.timeline.selected_keys()
        if not keys:
            return None, []
        akind, _aidx = getattr(self.timeline, "_sel", ("", -1))
        kinds = {k for (k, _i) in keys}
        if akind not in kinds:
            if len(kinds) != 1:
                return None, []
            akind = next(iter(kinds))
        idxs = sorted({i for (k, i) in keys
                       if k == akind and 0 <= i < len(
                           self.acords if akind == "chord" else self.seccions)})
        return akind, idxs

    def renomena_seleccio(self):
        """Reanomena EN BLOC la selecció del **tipus actiu** (acords O seccions).

        Amb selecció mixta es renombren només els del tipus actiu (opció A).
        Tot en una sola operació de desfer; al final queda seleccionat el bloc.
        """
        kind, idxs = self._clips_per_renombrar()
        if not idxs:
            self.log("reanomena en bloc: no hi ha res seleccionat")
            return False
        if kind == "chord":
            text, ok = QInputDialog.getText(
                self, "Reanomena acords",
                f"Nom nou per a {len(idxs)} acord(s):",
                text=nom_acord(self.acords[idxs[0]]))
            if not ok:
                return False
            return self._renomena_acords(idxs, text)
        text, ok = QInputDialog.getText(
            self, "Reanomena seccions",
            f"Lletra nova per a {len(idxs)} secció(ns):",
            text=self.seccions[idxs[0]][2])
        if not ok:
            return False
        return self._renomena_seccions(idxs, text)

    def _renomena_acords(self, idxs, nom):
        """Reanomena els acords `idxs` a `nom` (1 sola op. de desfer). True si OK."""
        idxs = sorted({i for i in idxs if 0 <= i < len(self.acords)})
        nom = pipeline.saneja_nom_acord(nom)
        if not idxs or not nom:
            self.log("reanomena acords: res a fer (nom o selecció buits)")
            return False
        self._undo_marca()
        nova = list(self.acords)
        for i in idxs:
            _a = nova[i]
            nova[i] = pipeline.Clip(float(_a[0]), float(_a[1]),
                                    (nom,) + tuple(_a[2][1:]))
        try:
            self.acords = self._valida_canvis_acords(nova)
        except ValueError as e:
            self.log(f"reanomena acords: {e}")
            return False
        self._undo_commit()
        self.timeline.set_data(self.acords, self.seccions)
        try:
            self._desa_i_regenera()
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR: {e}")
        self.timeline.select_multi({("chord", i) for i in idxs})
        self._omple_llista_ac()
        self.log(f"reanomenats {len(idxs)} acord(s) → {nom}")
        return True

    def _renomena_seccions(self, idxs, lletra):
        """Reanomena les seccions `idxs`: lletra i família passen a `lletra`."""
        idxs = sorted({i for i in idxs if 0 <= i < len(self.seccions)})
        if not idxs:
            self.log("reanomena seccions: res a fer")
            return False
        lletra = (str(lletra) if lletra is not None else "").strip() \
            or self.seccions[idxs[0]][2]
        self._undo_marca()
        nova = list(self.seccions)
        for i in idxs:
            ini, fi, _l, _f = nova[i]
            nova[i] = (ini, fi, lletra, lletra)
        try:
            self.seccions = self._valida_canvis_seccions(nova)
        except ValueError as e:
            self.log(f"reanomena seccions: {e}")
            return False
        self._undo_commit()
        self.timeline.set_data(self.acords, self.seccions)
        try:
            self._regenera_abc_des_de_totes_les_seccions("bloc reanomenat")
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR: {e}")
        self.timeline.select_multi({("section", i) for i in idxs})
        self._actualitza_llista_abc()
        self.log(f"reanomenades {len(idxs)} secció(ns) → {lletra}")
        return True

    def troba_i_reemplaca(self, camp, troba, reemplaca):
        """Substitueix TOTES les aparicions EXACTES d'un xifrat (acords) o d'una
        etiqueta (estructura) al tema. Retorna quants n'ha canviat (0 = cap).

        No canvia cap temps → les regles d'or (ordre/contigüitat/cobertura) queden
        intactes. Una sola operació de desfer.
        """
        troba = str(troba or "").strip()
        reemplaca = str(reemplaca or "").strip()
        if not troba or not reemplaca:
            return 0
        if camp == "estructura":
            lista, n = [], 0
            for (ini, fi, lletra, fam) in self.seccions:
                if str(lletra) == troba:
                    n += 1
                    fam = reemplaca if str(fam) == troba else fam
                    lletra = reemplaca
                lista.append((ini, fi, lletra, fam))
            if not n:
                return 0
            self._undo_marca()
            self.seccions = self._valida_canvis_seccions(lista)
            self._undo_commit()
            self.timeline.set_data(self.acords, self.seccions)
            try:
                self._regenera_abc_des_de_totes_les_seccions(
                    f"substitució estructura: {troba}→{reemplaca}")
            except Exception as e:  # noqa: BLE001
                self.log(f"ERROR: {e}")
            self._actualitza_llista_abc()
            self.log(f"substitució estructura: «{troba}» → «{reemplaca}» ({n})")
            return n
        # acords
        nou = pipeline.saneja_nom_acord(reemplaca)
        if not nou:
            return 0
        lista, n = [], 0
        for _a in self.acords:
            t, nom = float(_a[0]), nom_acord(_a)
            if str(nom) == troba:
                n += 1
                nom = nou
            lista.append((t, nom, f"{t:.9f}"))
        if not n:
            return 0
        self._undo_marca()
        self.acords = self._valida_canvis_acords(lista)
        self._undo_commit()
        self.timeline.set_data(self.acords, self.seccions)
        try:
            self._desa_i_regenera()
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR: {e}")
        self._omple_llista_ac()
        self.log(f"substitució acords: «{troba}» → «{nou}» ({n})")
        return n

    def regularitza_des_de_cru(self, nivell="auto", modul_compassos=0):
        """Mode fàcil: re-deriva els acords de l'ANÀLISI CRUA sobre la graella.

        `nivell`: "auto" | "compas" | "mig" | "temps" → **un acord per cel·la**
        (ritme harmònic). Si `modul_compassos` > 0, també **encaixa els talls de
        secció** a múltiples d'aquell nombre de compassos (blocs 4/8/16…).

        **No toca la capa crua** (`analisi/`). Una sola operació de desfer.
        Retorna quants acords ha deixat (0 = res a fer).
        """
        durada = float(self.audio["durada"])
        cru = os.path.join(pipeline.carpeta_analisi(self._carpeta_acords()),
                           pipeline.NOM_CRU_ACORDS)
        items = []
        if os.path.isfile(cru):
            try:
                with open(cru, encoding="utf-8") as f:
                    for fila in csv.reader(f):
                        if not fila or fila[0].startswith("posici"):
                            continue
                        try:
                            items.append((float(fila[0]), fila[1].strip()))
                        except (ValueError, IndexError):
                            continue
            except OSError:
                items = []
        if not items:
            items = [(float(a[0]), str(nom_acord(a))) for a in self.acords]
        bpm, bpb, off = self.bpm, self.bpb, self.offset
        if nivell in (None, "auto"):
            nivell = graella.infereix_nivell(items, bpm, bpb, off, durada,
                                             log=self.log)
        nou = graella.regularitza_acords(items, bpm, bpb, off,
                                         nivell or "compas", durada,
                                         log=self.log)
        nous_acords = []
        if nou:
            c, _ = pipeline.normalitza_cobertura(nou, [], durada, log=self.log)
            # Manté el 3r camp (precisió interna) com la resta del model.
            nous_acords = [(float(t), str(n), f"{float(t):.9f}") for (t, n) in c]
        noves_sec = self.seccions
        if modul_compassos and self.seccions:
            noves_sec = graella.regularitza_seccions(
                self.seccions, bpm, bpb, off, durada, modul_compassos,
                log=self.log)
        canvi_ac = bool(nous_acords)
        canvi_sec = modul_compassos and noves_sec != self.seccions
        if not canvi_ac and not canvi_sec:
            return 0
        self._undo_marca()
        if canvi_ac:
            self.acords = self._valida_canvis_acords(nous_acords)
        if canvi_sec:
            self.seccions = self._valida_canvis_seccions(noves_sec)
        self._undo_commit()
        self.timeline.set_data(self.acords, self.seccions)
        try:
            if canvi_ac:
                self._desa_i_regenera()
            if canvi_sec:
                self._regenera_abc_des_de_totes_les_seccions("mode fàcil")
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR: {e}")
        self._omple_llista_ac()
        self._actualitza_llista_abc()
        self.log(f"mode fàcil: {len(self.acords)} acords, {len(self.seccions)} "
                 f"seccions (ritme harmònic «{nivell}»)")
        return len(self.acords)

    def _on_section_edit_requested(self, idx):
        # Doble-clic al SectionItem -> franja EDITOR (sense finestra emergent).
        if idx < 0 or idx >= len(self.seccions):
            return
        self._focus_editor("section", idx)

    # navegació
    def ves_a(self, t):
        # Cerca PROGRAMÀTICA (barra lliscant, llistes, MCP): posició EXACTA.
        # El snap del cursor s'aplica als clics DIRECTES al timeline.
        self.pos = max(0.0, min(float(t), self.audio["durada"]))
        self.timeline.set_position(self.pos, emit=False, snap=False)
        self.lliscador.setValue(int(self.pos * 100))
        self._actualitza_temps()
        if self.sona:
            self._atura_proc()
            self._engega_des_de(self.pos)

    def _on_clip_selected(self, kind, index):
        """Click a un clip del timeline -> sincronitza la llista + l'editor."""
        if kind == "chord" and 0 <= index < self.llista_ac.count():
            self.llista_ac.setCurrentRow(index)
        elif kind == "section" and 0 <= index < self.llista_ab.count():
            self.llista_ab.setCurrentRow(index)
        elif kind == "tempo":
            return                          # la pista de BPM/compàs no té editor
        self._ed_kind, self._ed_idx = kind, index
        self._actualitza_editor()

    def _refresca_post_edicio(self, kind, idx):
        """Manté el clip editat SELECCIONAT i refresca les llistes a l'instant.

        Com un DAW: editar/renombrar no ha de perdre la selecció ni deixar la
        llista vella fins a tocar una altra cosa. Regla d'or #11: mateix tracte
        per a acords i seccions."""
        self._omple_llista_ac()
        self._actualitza_llista_abc()
        if hasattr(self, "timeline") and 0 <= idx:
            self.timeline.select_multi({(kind, idx)})

    def _actualitza_editor(self):
        """Mostra a la franja Editor l'element seleccionat (o el buit)."""
        k, i = getattr(self, "_ed_kind", None), getattr(self, "_ed_idx", -1)
        if k == "chord" and 0 <= i < len(self.acords):
            t, nom = float(self.acords[i][0]), nom_acord(self.acords[i])
            self.ed_icona.setPixmap(icones.ico("music", 20).pixmap(20, 20))
            self.ed_gran.setText(nom)
            self.ed_nom.setText(nom)
            self.ed_ini.setText(f"{float(t):.2f}")
            self.ed_cb.setText(self._secs_a_cb(float(t)))
            self.ed_fam.setVisible(False); self.ed_fam_lbl.setVisible(False)
            for w in (self.ed_nom, self.ed_ini, self.ed_cb, self.ed_aplica):
                w.setEnabled(True)
        elif k == "section" and 0 <= i < len(self.seccions):
            ini, fi, lletra, fam = self.seccions[i]
            self.ed_icona.setPixmap(icones.ico("piano", 20).pixmap(20, 20))
            self.ed_gran.setText(f"{lletra} ({fam})")
            self.ed_nom.setText(lletra)
            self.ed_fam.setText(fam)
            self.ed_ini.setText(f"{float(ini):.2f}")
            self.ed_cb.setText(self._secs_a_cb(float(ini)))
            self.ed_fam.setVisible(True); self.ed_fam_lbl.setVisible(True)
            for w in (self.ed_nom, self.ed_fam, self.ed_ini, self.ed_cb,
                      self.ed_aplica):
                w.setEnabled(True)
        else:
            self.ed_icona.clear()
            self.ed_gran.setText("Selecciona un acord o una secció")
            for w in (self.ed_nom, self.ed_fam, self.ed_ini, self.ed_cb,
                      self.ed_aplica):
                w.setEnabled(False)
            self.ed_nom.clear(); self.ed_fam.clear()
            self.ed_ini.clear(); self.ed_cb.clear()

    def _secs_a_cb(self, t):
        """Segons -> compas.beat (graella original offset=0)."""
        beat = 60.0 / max(self.bpm, 1e-9)
        beats = float(t) / beat
        bpb = max(1, int(self.bpb))
        c = int(math.floor(beats / bpb)) + 1
        b = int(round(beats % bpb)) + 1
        if b > bpb:
            c += 1; b = 1
        return f"{c}.{b}"

    def _cb_a_secs(self, text):
        """compas.beat -> segons (graella original offset=0)."""
        m = re.match(r"\s*(-?\d+)\s*[.,]\s*(\d+)\s*$", str(text))
        if not m:
            return None
        c, b = int(m.group(1)), int(m.group(2))
        beat = 60.0 / max(self.bpm, 1e-9)
        n = (c - 1) * max(1, int(self.bpb)) + (b - 1)
        return max(0.0, n * beat)

    def avis_editor(self, text):
        """Avís de la franja Editor: al log I a la caixa d'informació.

        MAI en silenci: abans, sis camins de `_aplica_editor` tornaven sense dir
        res i el botó «Aplica» semblava no fer res (OC-6/394).
        """
        self.log(f"editor: {text}")
        self.infoMissatge.emit(text)

    def _aplica_editor(self):
        """Aplica els canvis de la franja Editor al model (amb undo).

        Tots els camins que NO apliquen donen feedback visible (`avis_editor`):
        un botó que no fa res i no diu per què és un defecte.
        """
        k, i = getattr(self, "_ed_kind", None), getattr(self, "_ed_idx", -1)
        if k is None or i < 0:
            self.avis_editor("Selecciona un acord o una secció (clic al clip) "
                             "abans d'aplicar.")
            return
        # Multi-selecció del MATEIX tipus → renom EN BLOC (estil fulla de càlcul):
        # el camp Nom s'aplica a TOTS els seleccionats del tipus actiu. L'INICI
        # NO s'aplica en bloc (no s'han d'apilar tots els clips al mateix instant).
        _n = len(self.acords) if k == "chord" else len(self.seccions)
        idxs = sorted({j for (kk, j) in self.timeline.selected_keys()
                       if kk == k and 0 <= j < _n})
        if len(idxs) >= 2:
            nom = self.ed_nom.text().strip()
            if k == "chord":
                if not self._renomena_acords(idxs, nom):
                    self.avis_editor("Renom en bloc: nom o canvi no vàlid.")
            else:
                if not self._renomena_seccions(idxs, nom or self.seccions[i][2]):
                    self.avis_editor("Renom en bloc: lletra o canvi no vàlid.")
            return
        # inici: prioritza el camp de segons; si esta buit, el de compas.beat
        txt = self.ed_ini.text().strip()
        if txt:
            try:
                ini = float(txt.replace(",", "."))
            except ValueError:
                self.avis_editor(f"L'inici «{txt}» no és un número vàlid.")
                return
        else:
            ini = self._cb_a_secs(self.ed_cb.text())
            if ini is None:
                self.avis_editor(f"El compàs «{self.ed_cb.text()}» no és vàlid.")
                return
        nom = self.ed_nom.text().strip()
        if k == "chord":
            if not nom or not (0 <= i < len(self.acords)):
                self.avis_editor("Cal un nom, i l'acord ha d'existir (potser "
                                 "l'has esborrat).")
                return
            # Mateix sanejat que l'alta i l'export (coherència nom CSV ↔ WAV).
            nom = pipeline.saneja_nom_acord(nom)
            if not nom:
                self.avis_editor("El nom de l'acord no és vàlid.")
                return
            # Si l'inici NO s'ha tocat, conserva el valor INTERN de precisió
            # completa: l'editor només en mostra 2 decimals i re-escriure'l
            # arrodonit podria fer que l'acord "xoqui" amb el veí.
            if abs(ini - float(self.acords[i][0])) <= 0.005:
                ini = float(self.acords[i][0])
            self._undo_marca()
            nova = list(self.acords)
            _a = nova[i]
            nova[i] = pipeline.Clip(ini, float(_a[1]),
                                    (nom,) + tuple(_a[2][1:]))
            try:
                self.acords = self._normalitza_acords(nova)
            except ValueError as e:
                self.avis_editor(f"canvi invalid ({e})")
                return
            self._undo_commit()
            self.timeline.set_data(self.acords, self.seccions)
            self._desa_i_regenera()
            self.log(f"editor: acord {i} -> {nom} @ {ini:.2f}s")
            # Si s'ha mogut l'inici, l'acord pot haver canviat de fila → re-localitza.
            i = next((j for j, a in enumerate(self.acords)
                      if abs(float(a[0]) - ini) <= 1e-6
                      and nom_acord(a) == nom), i)
        else:
            if not (0 <= i < len(self.seccions)):
                self.avis_editor("Aquesta secció ja no existeix (potser l'has "
                                 "esborrada).")
                return
            _ini, fi, _ll, _f = self.seccions[i]
            # (mateix motiu que als acords) si l'inici no s'ha tocat, conserva
            # la precisió completa -> evita falsos solapaments amb la secció
            # anterior, que acaba EXACTAMENT aquí.
            if abs(ini - _ini) <= 0.005:
                ini = _ini
            lletra = nom or self.seccions[i][2]
            fam = self.ed_fam.text().strip() or self.seccions[i][3]
            self._undo_marca()
            nova = list(self.seccions)
            nova[i] = (ini, max(ini + 0.05, fi), lletra, fam)
            try:
                # Manté la contigüitat (#2) com el drag del timeline/MCP.
                nova = self._contiguitat_seccions(nova, i)
                self.seccions = self._normalitza_seccions(nova)
            except ValueError as e:
                self.avis_editor(f"canvi invalid ({e})")
                return
            self._undo_commit()
            self.timeline.set_data(self.acords, self.seccions)
            self._regenera_abc_des_de_totes_les_seccions("editat des de l'editor")
            self.log(f"editor: seccio {i} -> {lletra} @ {ini:.2f}s")
            i = next((j for j, s in enumerate(self.seccions)
                      if abs(float(s[0]) - ini) <= 1e-6 and s[2] == lletra), i)
        self._refresca_post_edicio(k, i)

    def posa_nom_editor(self, nom):
        """Posa `nom` a la casella «Nom» de la franja Editor (**sense aplicar**).

        El fa servir el panell «Tipus d'acord»: clicar un tipus només **omple**
        la casella; l'usuari decideix quan prem «Aplica» (o Enter).
        """
        self.ed_nom.setText(str(nom or ""))
        self.ed_nom.setFocus()
        self.ed_nom.selectAll()
        self.avis_editor(f"tipus d'acord: «{nom}» llest per aplicar")

    def _focus_editor(self, kind, idx):
        """Selecciona l'element i enganxa el focus a la franja Editor
        (en comptes d'obrir cap finestra emergent)."""
        self._ed_kind, self._ed_idx = kind, idx
        self.timeline.select_clip(kind, idx)
        self._actualitza_editor()
        self.ed_nom.setFocus()
        self.ed_nom.selectAll()

    def _salt_acord(self, item):
        row = self.llista_ac.row(item)
        if row >= 0:
            self.timeline.select_clip("chord", row)
        self.ves_a(self._parse_pos_label(item.text()))
        # Desplaça la vista cap al cursor NOMÉS si cal (manté el zoom).
        self.timeline.ensure_cursor_visible()

    def _valida_canvis_seccions(self, items):
        if not items:
            return []
        durada = self._durada_wav()
        ordenats = sorted(items, key=lambda x: float(x[0]))
        prev_fi = -1e-9
        for item in ordenats:
            ini = float(item[0])
            fi = float(item[1])
            if ini < 0 or fi < 0:
                raise ValueError(f"La secció {item[2]} té temps negatius ({ini:.2f}s–{fi:.2f}s)")
            if fi <= ini:
                raise ValueError(f"La secció {item[2]} té una durada no vàlida ({ini:.2f}s–{fi:.2f}s)")
            # TOPALL superior: cap secció pot sortir de la WAV (#4).
            if durada > 0 and fi > durada + pipeline.TOL_TEMPS:
                raise ValueError(
                    f"La secció {item[2]} surt de la WAV ({fi:.2f}s; la WAV fa "
                    f"{durada:.2f}s)")
            if ini < prev_fi - 1e-9:
                raise ValueError(
                    "Les seccions no poden solapar-se ni invertir-se. "
                    "L'ordre temporal ha de ser estricte."
                )
            prev_fi = fi
        return ordenats

    # Durada mínima d'una secció en moure'n una vora (evita seccions nul·les).
    MIN_SECCIO_S = 0.05

    # Durada mínima d'un acord en partir-lo (regla d'or #11; mirall de la secció).
    MIN_ACORD_S = 0.05

    def _contiguitat_seccions(self, items, idx):
        """Manté l'INVARIANT de CONTIGÜITAT (regla d'or #2) en moure `idx`.

        El `fi` de la secció anterior i l'`ini` de la següent segueixen les
        vores noves de la secció moguda (mateixa lògica que el drag del
        timeline i que `_elimina_seccio`): així no apareixen forats interns ni
        solapaments. Rebutja (`ValueError`) si algun veí quedaria sense marge.
        """
        items = list(items)
        ini, fi, L, _F = items[idx]
        if fi - ini < self.MIN_SECCIO_S:
            raise ValueError(
                f"La secció {L} quedaria massa curta ({ini:.2f}s–{fi:.2f}s)")
        if idx - 1 >= 0:
            pi, _pf, pl, pfam = items[idx - 1]
            if ini - pi < self.MIN_SECCIO_S:
                raise ValueError(
                    f"La secció {pl} quedaria massa curta: el nou inici "
                    f"({ini:.2f}s) no deixa marge")
            items[idx - 1] = (pi, ini, pl, pfam)
        if idx + 1 < len(items):
            _ni, nf, nl, nfam = items[idx + 1]
            if nf - fi < self.MIN_SECCIO_S:
                raise ValueError(
                    f"La secció {nl} quedaria massa curta: el nou fi "
                    f"({fi:.2f}s) no deixa marge")
            items[idx + 1] = (fi, nf, nl, nfam)
        return items

    def mou_seccio(self, idx, ini, fi):
        """Mou/redimensiona la secció `idx` a (`ini`,`fi`) mantenint la contigüitat.

        Camí CANÒNIC del moviment de seccions (MCP i editor): el veí anterior
        estén/arronsa el seu `fi` fins al nou inici, i el següent fa el mateix
        amb el seu `ini`. Sense això quedava un forat intern que l'app acceptava
        (la suma de durades ja no quadrava amb la WAV).

        NO fa undo ni desa: els qui criden (bridge/editor) ja ho fan, com la
        resta de mutacions del model. Retorna `False` si l'índex no existeix.
        """
        if not (0 <= idx < len(self.seccions)):
            return False
        ini, fi = float(ini), float(fi)
        nova = list(self.seccions)
        _i, _f, L, F = nova[idx]
        nova[idx] = (ini, fi, L, F)
        nova = self._contiguitat_seccions(nova, idx)
        self.seccions = self._normalitza_seccions(nova)
        if hasattr(self, "timeline"):
            self.timeline.set_data(self.acords, self.seccions)
        if hasattr(self, "llista_ab"):
            self._actualitza_llista_abc()
        return True

    def _normalitza_seccions(self, items=None):
        items = self.seccions if items is None else items
        ordenats = self._valida_canvis_seccions(items)
        if isinstance(items, list):
            self.seccions = ordenats
        return ordenats

    def _actualitza_llista_abc(self):
        cur = self.llista_ab.currentRow()    # preserva la seleccio (vegeu _omple_llista_ac)
        self.llista_ab.clear()
        for ini, fi, L, fam in self.seccions:
            if self.tempo_fix:
                ini_txt = self._fmt_compas(ini)
                fi_txt = self._fmt_compas(fi)
            else:
                ini_txt = f"{ini:07.2f}s"
                fi_txt = f"{fi:07.2f}s"
            self.llista_ab.addItem(f"{L} ({fam})  {ini_txt}–{fi_txt}")
        if 0 <= cur < self.llista_ab.count():
            self.llista_ab.setCurrentRow(cur)

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

    def parteix_acord(self, idx, t, nom=None):
        """Parteix l'acord `idx` pel temps `t` (regla d'or #11).

        Mirall de `parteix_seccio`: l'acord de l'esquerra conserva el nom i acaba
        a `t`; el clip NOU (a la dreta) comença a `t` amb el nom triat (per
        defecte, el MATEIX). Retorna l'índex del clip nou, o `False` si `t` no
        cau a dins (o si l'índex és l'últim acord, sense durada pròpia).
        """
        if not (0 <= idx < len(self.acords)):
            return False
        if idx + 1 >= len(self.acords):
            return False
        t = float(t)
        t0 = float(self.acords[idx][0])
        fi = float(self.acords[idx + 1][0])
        if not (t0 + self.MIN_ACORD_S <= t <= fi - self.MIN_ACORD_S):
            self.log(f"partir: {t:.2f}s no cau dins l'acord "
                     f"{nom_acord(self.acords[idx])} ({t0:.2f}s–{fi:.2f}s)")
            return False
        self._undo_marca()
        if nom is None:
            nom = nom_acord(self.acords[idx])
        try:
            nova = pipeline.parteix_clips(
                self.acords, idx, t, nou_payload=(nom, f"{t:.9f}"))
            self.acords = self._normalitza_acords(nova)
        except ValueError as e:
            self.log(f"partir: canvi invalid ({e})")
            return False
        self._undo_commit()
        if hasattr(self, "timeline"):
            self.timeline.set_data(self.acords, self.seccions)
        self._omple_llista_ac()
        return idx + 1

    def _parteix_acord_dialog(self, idx):
        """Parteix l'acord `idx` pel CURSOR, preguntant el nom nou (regla #11)."""
        if not (0 <= idx < len(self.acords)):
            return False
        t0 = float(self.acords[idx][0])
        nom = nom_acord(self.acords[idx])
        if idx + 1 >= len(self.acords):
            QMessageBox.information(
                self, "Parteix l'acord",
                "L'últim acord no es pot partir: la seva durada arriba al final "
                "de la WAV.")
            return False
        fi = float(self.acords[idx + 1][0])
        if not (t0 + self.MIN_ACORD_S <= self.pos <= fi - self.MIN_ACORD_S):
            self.log(f"partir: el cursor ({self.pos:.2f}s) no cau dins l'acord "
                     f"{nom} ({t0:.2f}s–{fi:.2f}s)")
            QMessageBox.information(
                self, "Parteix l'acord",
                f"Posa el cursor DINS l'acord «{nom}» ({t0:.2f}–{fi:.2f} s) "
                "al punt on vols el tall.")
            return False
        nou, ok = QInputDialog.getText(
            self, "Parteix l'acord",
            f"Parteix «{nom}» a {self.pos:.2f} s.\nNom de la part nova:",
            text=nom)
        if not ok:
            return False
        if not self.parteix_acord(idx, self.pos, nou):
            return False
        try:
            self._desa_i_regenera()
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR: {e}")
            QMessageBox.warning(self, "Visor", f"No s'ha pogut desar:\n{e}")
        return True

    def parteix_seccio(self, idx, t, lletra=None, fam=None):
        """Parteix la secció `idx` pel temps `t` (A2).

        En un model SATURAT —les seccions cobreixen tota la WAV, regla d'or #4—
        no hi ha cap forat on afegir-ne una de nova: «afegir» una secció vol dir
        **partir** la que hi ha. La meitat esquerra conserva lletra i família; la
        dreta rep la lletra nova (per defecte la MATEIXA: és la mateixa part
        musical, i el model admet lletres repetides).

        Retorna l'índex de la secció NOVA, o `False` si `t` no cau a dins (o si
        alguna de les dues meitats quedaria més curta que `MIN_SECCIO_S`).
        """
        if not (0 <= idx < len(self.seccions)):
            return False
        t = float(t)
        ini, fi, L, F = self.seccions[idx]
        ini, fi = float(ini), float(fi)
        if not (ini + self.MIN_SECCIO_S <= t <= fi - self.MIN_SECCIO_S):
            self.log(f"partir: {t:.2f}s no cau dins la secció {L} "
                     f"({ini:.2f}s–{fi:.2f}s)")
            return False
        L2 = (str(lletra).strip() if lletra else L) or L
        F2 = (str(fam).strip() if fam else (F or L2)) or L2
        self._undo_marca()
        nova = list(self.seccions)
        nova[idx] = (ini, t, L, F)
        nova.insert(idx + 1, (t, fi, L2, F2))
        try:
            self.seccions = self._normalitza_seccions(nova)
        except ValueError as e:
            self.log(f"partir: canvi invalid ({e})")
            return False
        self._undo_commit()
        if hasattr(self, "timeline"):
            self.timeline.set_data(self.acords, self.seccions)
        if hasattr(self, "llista_ab"):
            self._actualitza_llista_abc()
        return idx + 1

    def _parteix_seccio_dialog(self, idx):
        """Parteix la secció `idx` pel CURSOR, preguntant la lletra nova (A2)."""
        if not (0 <= idx < len(self.seccions)):
            return False
        ini, fi, L, _F = self.seccions[idx]
        ini, fi = float(ini), float(fi)
        if not (ini + self.MIN_SECCIO_S <= self.pos <= fi - self.MIN_SECCIO_S):
            self.log(f"partir: el cursor ({self.pos:.2f}s) no cau dins la "
                     f"secció {L} ({ini:.2f}s–{fi:.2f}s)")
            QMessageBox.information(
                self, "Parteix la secció",
                f"Posa el cursor DINS la secció «{L}» ({ini:.2f}–{fi:.2f} s) "
                "al punt on vols el tall.")
            return False
        nova, ok = QInputDialog.getText(
            self, "Parteix la secció",
            f"Parteix «{L}» a {self.pos:.2f} s.\nLletra de la part nova:",
            text=L)
        if not ok:
            return False
        if not self.parteix_seccio(idx, self.pos, nova):
            return False
        try:
            self._regenera_abc_des_de_totes_les_seccions(
                f"secció {L} partida a {self.pos:.2f}s")
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR: {e}")
            QMessageBox.warning(self, "Visor", f"No s'ha pogut regenerar:\n{e}")
        return True

    def fusiona_acord(self, idx, amb="seguent"):
        """Fusiona l'acord `idx` amb el veí (regla d'or #11).

        Mirall de `fusiona_seccio`: el clip que queda a l'esquerra conserva la
        seva harmonia. Retorna `True` si s'ha fet el canvi.
        """
        if not (0 <= idx < len(self.acords)):
            return False
        self._undo_marca()
        try:
            self.acords = self._normalitza_acords(
                pipeline.fusiona_clips(self.acords, idx, amb))
        except ValueError as e:
            self.log(f"fusiona acord: {e}")
            return False
        self._undo_commit()
        if hasattr(self, "timeline"):
            self.timeline.set_data(self.acords, self.seccions)
        self._omple_llista_ac()
        try:
            self._desa_i_regenera()
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR: {e}")
        return True

    def fusiona_seccio(self, idx, amb="seguent"):
        """Fusiona la secció `idx` amb el veí (regla d'or #11).

        Mirall de `fusiona_acord`: el clip que queda a l'esquerra conserva lletra
        i família. Retorna `True` si s'ha fet el canvi.
        """
        if not (0 <= idx < len(self.seccions)):
            return False
        self._undo_marca()
        try:
            self.seccions = self._normalitza_seccions(
                pipeline.fusiona_seccions(self.seccions, idx, amb=amb))
        except ValueError as e:
            self.log(f"fusiona secció: {e}")
            return False
        self._undo_commit()
        if hasattr(self, "timeline"):
            self.timeline.set_data(self.acords, self.seccions)
        self._actualitza_llista_abc()
        try:
            self._regenera_abc_des_de_totes_les_seccions(
                f"secció {idx} fusionada amb {amb}")
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR: {e}")
        return True

    def _elimina_seccio(self, idx):
        if idx < 0 or idx >= len(self.seccions):
            return False
        # Nucli únic `pipeline.elimina_seccio` (§6.4): mateix tracte que els
        # acords (#11); l'anterior s'estira i, sense anterior, hi va el «-».
        self.seccions = pipeline.elimina_seccio(
            self.seccions, idx, self._durada_wav())
        if hasattr(self, "llista_ab"):
            self._actualitza_llista_abc()
        return True

    def _salt_seccio(self, item):
        row = self.llista_ab.row(item)
        if row >= 0:
            self.timeline.select_clip("section", row)
        self.ves_a(self._parse_pos_label(item.text()))
        # Desplaça la vista cap al cursor NOMÉS si cal (manté el zoom).
        self.timeline.ensure_cursor_visible()

    def _menu_seccio(self, pos):
        # Regla d'or #11: MATEIX joc d'accions que el menú dels acords.
        if not self.seccions:
            return
        idx = self.llista_ab.indexAt(pos).row()
        menu = QMenu(self)
        afegir = menu.addAction("Afegeix secció aquí")
        partir = menu.addAction("Partir secció aquí")
        fusionar_prev = menu.addAction("Fusionar amb anterior")
        fusionar_next = menu.addAction("Fusionar amb següent")
        eliminar = menu.addAction("Elimina secció")
        n_sel = len({i for (k, i) in self.timeline.selected_keys()
                     if k == "section"})
        reanomena = menu.addAction(
            f"Reanomena {n_sel} seccions…" if n_sel >= 2 else "Reanomena secció…")
        te = 0 <= idx < len(self.seccions)
        partir.setEnabled(te and idx + 1 < len(self.seccions))
        fusionar_prev.setEnabled(te and idx > 0)
        fusionar_next.setEnabled(te and idx + 1 < len(self.seccions))
        eliminar.setEnabled(te)
        reanomena.setEnabled(te or n_sel >= 1)
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
            self._parteix_seccio_dialog(idx)
        elif accio == fusionar_prev:
            self.fusiona_seccio(idx, "anterior")
        elif accio == fusionar_next:
            self.fusiona_seccio(idx, "seguent")
        elif accio == eliminar:
            try:
                self._elimina_seccio(idx)
                self._regenera_abc_des_de_totes_les_seccions("secció eliminada")
            except Exception as e:  # noqa: BLE001
                self.log(f"ERROR: {e}")
                QMessageBox.warning(self, "Visor",
                                    f"No s'ha pogut eliminar la secció:\n{e}")
        elif accio == reanomena:
            # >1 seleccionat → renom en bloc; si no, edita la secció del clic.
            if n_sel >= 2:
                self.renomena_seleccio()
            elif te:
                self._focus_editor("section", idx)

    def _regenera_abc_des_de_totes_les_seccions(self, msg):
        sortida = self._carpeta_acords()
        os.makedirs(sortida, exist_ok=True)
        abc = os.path.join(sortida, "estructura_ABC.csv")
        pipeline.desa_abc_csv(abc, self.seccions, self.bpm, self.log,
                              lliure=not self.tempo_fix, bpb=self.bpb,
                              offset=getattr(self, "offset", 0.0),
                              mapa=getattr(self, "tempo_map", None))
        self.canvis.emit()   # l'estructura ha canviat → el projecte queda «brut»
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
        self._avis_audio_fet = False       # nou play → tornar a poder avisar
        self._atura_proc()
        # Clamp per seguretat (validació prèvia pot ser absent en alguns
        # camins; evitem índex negatiu o inici més enllà de les dades).
        t = max(0.0, min(float(t), float(self.audio["durada"])))
        # El PCM NO es pre-construieix aquí: el fil d'alimentació el genera
        # tros a tros (i, si hi ha loop, en fa la volta TOT SOL sense reiniciar
        # el reproductor → sense el tall a cada volta). El metrònom també es
        # mescla per tros, dins el feeder.
        if self.player is None:
            QMessageBox.information(self, "Reproducció",
                                    plataforma.missatge_sense_audio())
            return
        # AMB LOOP A/B ACTIU, el só arrenca SEMPRE a `loop_a` si el punt demanat
        # queda FORA del bucle: `_alimenta` hi salta tot sol. El cursor ha de
        # fer el MATEIX (vegeu `_alinea_cursor_loop`), o queden desalineats.
        t = self._alinea_cursor_loop(t)
        self.log(f"play des de {t:.2f}s amb {self.player}...")
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
                # Motor de reproducció: extern (Linux: paplay/aplay) o natiu
                # (mac/win: sounddevice/CoreAudio-MME). Vegeu app/audio_out.py.
                self.proc = audio_out.crea_motor(
                    self.player, self.player_args, self.audio["sr"], ferr)
                # L'escriptura va en fil propi: tant el pipe com el stream només
                # empassen al ritme del so i un write() sencer congelaria la GUI.
                sess = self._sess
                fil = threading.Thread(target=self._alimenta,
                                       args=(self.proc, t, sess),
                                       daemon=True)
                fil.start()
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR engegar {self.player}: {e}")
            QMessageBox.warning(self, "Visor",
                                f"No puc engegar el reproductor: {e}")
            self.proc = None
            return
        self.t0_mono = time.monotonic()
        self.t0_pos = t
        self.log(f"{self.player} pid={self.proc.pid} en marxa")

    # Durada del micro-fade anti-clic als extrems del loop (segons).
    FADE_LOOP_S = 0.004

    def _alimenta(self, proc, t_inici, sess):
        """Genera el PCM tros a tros i l'envia al reproductor.

        - **Sense reiniciar el reproductor**: si hi ha loop A/B actiu, en fa la
          VOLTA aquí mateix (dins el flux continu) → **no hi ha tall a cada
          volta** (abans es matava el reproductor i se n'engegava un altre).
        - El **guany** (volum/mute) i el **metrònom** s'apliquen per tros,
          llegint l'estat viu → es poden canviar sense reiniciar.
        - Als extrems del loop s'aplica un **micro-fade** (~4 ms) perquè la
          costura B→A no faci clic.
        """
        try:
            mono = memoryview(self._mono_bytes())
            sr = int(self.audio["sr"])
            n_mostres = len(mono) // 2
            pas = 32768  # mostres per tros
            fade = max(1, int(self.FADE_LOOP_S * sr))
            pos = int(max(0.0, min(float(t_inici),
                                   float(self.audio["durada"]))) * sr)
            while True:
                if sess != self._sess or proc.poll() is not None:
                    break
                bucle = (self.loop_on and self.loop_a is not None
                         and self.loop_b is not None)
                a = b = 0
                if bucle:
                    a = int(self.loop_a * sr)
                    b = int(self.loop_b * sr)
                    if b - a < 2:
                        bucle = False
                    elif pos < a or pos >= b:
                        pos = a
                fi = min(b if bucle else n_mostres, pos + pas)
                if fi <= pos:
                    break
                tros = bytes(mono[pos * 2:fi * 2])
                g = 0.0 if self.mut else self.vol
                if bucle or g != 1.0:
                    x = np.frombuffer(tros, dtype=np.int16).astype(np.float32)
                    if bucle:
                        idx = np.arange(pos - a, fi - a, dtype=np.float32)
                        env = np.minimum(np.minimum(1.0, idx / fade),
                                         np.minimum(1.0,
                                                    (b - a - 1 - idx) / fade))
                        x = x * (g * env)
                    else:
                        x = x * g
                    tros = np.clip(x, -32768, 32767).astype(np.int16).tobytes()
                if self.metro_on and self.metro_vol > 0:
                    tros = metronom.mescla_metronom(
                        tros, sr, pos / float(sr), self.bpm, self.bpb,
                        volum=self.metro_vol,
                        offset=getattr(self, "offset", 0.0))
                try:
                    proc.stdin.write(tros)
                except (BrokenPipeError, ValueError):
                    break
                pos = fi
                if bucle and pos >= b:
                    pos = a
                elif not bucle and pos >= n_mostres:
                    break
            try:
                proc.stdin.close()
            except (BrokenPipeError, ValueError):
                pass
        except Exception as e:  # noqa: BLE001
            # Fil d'àudio: l'error NO ha de quedar en silenci (AUDITORIA 1.6).
            # `logging` és thread-safe → es pot cridar des d'aquí sense tocar Qt.
            logging.getLogger("auto_chords").warning(
                "visor: el fil d'alimentació d'àudio ha fallat: %s", e)

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
        # invalida el fil d'alimentació i atura el motor: res no queda sonant.
        self._sess += 1
        with self._proc_lock:
            proc = self.proc
            self.proc = None
            if proc is None:
                return
        proc.atura()

    def play_stop(self):
        if self.sona:
            self.log(f"stop a {self.pos:.2f}s")
            self._atura_proc()
            self.rellotge.stop()
            self.sona = False
            self.timeline.set_follow(False)
            self.b_play.setIcon(icones.ico("play"))
            self.playStateChanged.emit(False)
        else:
            # Comencem SEMPRE des del cursor visible (no d'un estat antic)
            self.pos = float(self.timeline.get_position())
            self._engega_des_de(self.pos)
            if self.proc is None:
                return
            self.rellotge.start()
            self.sona = True
            self.timeline.set_follow(True)   # la vista segueix el cursor
            self.b_play.setIcon(icones.ico("pause"))
            self.playStateChanged.emit(True)
            self.log("escoltant...")

    def _tiquet(self):
        # el cursor avança amb rellotge de paret des de l'inici real
        if self.proc and self.proc.poll() is not None:
            codi = self.proc.returncode
            self._mostra_err_player()
            if codi not in (0, None):
                # El reproductor ha mort per error (glitch del servidor...).
                # AVÍS VISIBLE a més del log (AUDITORIA_PRODUCCIO 1.6 · AUDIO.md
                # «Pendent»), un sol cop per reproducció (`_avis_audio_fet` es
                # reinicia a `_engega_des_de`).
                msg = (f"El motor d'àudio s'ha aturat per un error (codi {codi}); "
                       "el so s'ha tallat.")
                self.log(f"⚠️ {msg}")
                if not getattr(self, "_avis_audio_fet", False):
                    self._avis_audio_fet = True
                    self.infoMissatge.emit(f"⚠️ {msg} — detalls al registre")
            else:
                self.log("final de la cançó")
            self.play_stop()
            return
        t = self.t0_pos + (time.monotonic() - self.t0_mono)
        if self.loop_on and self.loop_a is not None and self.loop_b is not None:
            dur = self.loop_b - self.loop_a
            if dur > 0.05 and t >= self.loop_b:
                # L'ÀUDIO ja ha fet la volta TOT SOL (el feeder, en continu,
                # sense reiniciar el reproductor → sense tall). Aquí només
                # movem el cursor VISUAL i re-ancorem el rellotge perquè no
                # derivi respecte a cada volta.
                t = self.loop_a + ((t - self.loop_a) % dur)
                self.t0_pos = t
                self.t0_mono = time.monotonic()
        fi = float(self.audio["durada"])
        if t >= fi:
            # NO aturem pel rellotge de paret: el reproductor te latencia i el
            # so va per darrere, aixi que aturar aquí tallava la cua. Esperem
            # que acabi ell (l'EOF de dalt). Nomes parem si el rellotge se'n
            # va massa lluny -> el reproductor s'ha encallat (xarxa de seguretat).
            if t >= fi + 15.0:
                self.log("⚠️ el rellotge va molt mes enlla del final: aturo")
                self.play_stop()
                return
            t = fi
        self.pos = t
        self.timeline.set_position(self.pos, emit=False, snap=False)
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
        pipeline.desa_acords_csv(self.csv_acords, self.acords,
                                 self._durada_wav())
        self.log(f"exporta → {sortida}")
        try:
            if self.seccions:
                abc = os.path.join(sortida, "estructura_ABC.csv")
                pipeline.desa_abc_csv(abc, self.seccions, self.bpm,
                                      self.log, lliure=not self.tempo_fix,
                                      bpb=self.bpb,
                                      offset=getattr(self, "offset", 0.0),
                                      mapa=getattr(self, "tempo_map", None))
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
    app = QApplication(sys.argv)
    app.setWindowIcon(icones.icona_app())
    if not a.wav:
        wav, _ = QFileDialog.getOpenFileName(None, "Tria la wav", "",
                                             "Àudio WAV (*.wav)")
        if not wav:
            sys.exit(0)
        a.wav = wav
    app.setStyle("Fusion")
    v = Visor(os.path.abspath(a.wav), a.acords or None, a.abc or None,
              a.bpm, a.bpb)
    v.show()
    codi = app.exec_()
    v._atura_proc()  # xarxa de seguretat: mai deixar àudio sonant
    sys.exit(codi)


if __name__ == "__main__":
    main()
