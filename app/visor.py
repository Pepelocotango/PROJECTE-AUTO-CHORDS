#!/usr/bin/env python3
# visor.py — Visor navegable (ona + acords + estructura + escolta + edició).
# Tot en català. Dependències aïllades: PyQt5 + numpy<2 (Q9400).
# Ús: .venv/bin/python -m app.visor tema.wav [--acords acords.csv] [--abc estructura_ABC.csv] [--bpm 138] [--bpb 4]
import argparse
import copy
import csv
import logging
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
    QAbstractItemView, QApplication, QDialog, QFileDialog, QHBoxLayout,
    QInputDialog, QLabel, QListWidget, QMainWindow, QMenu, QMessageBox,
    QPushButton, QShortcut, QSlider, QSplitter, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
    QLineEdit, QComboBox, QHeaderView,
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
from . import ffmpeg  # noqa: E402
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
    """Nom d'un clip d'acord (`Clip(ini, fi, payload)`)."""
    if isinstance(it, pipeline.Clip):
        return it.nom
    if len(it) >= 3 and isinstance(it[1], (int, float)):
        p = it[2]
        return p[0] if isinstance(p, tuple) else p
    return it[1]


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
    """Llig `estructura_ABC.csv` com a tuples `(ini, fi, lletra, família)`.

    Mateix tracte que `llegeix_acords` (paritat #11): una línia **malmesa**
    (columna que falta o valor no numèric) es **descarta amb avís**, no fa
    petar l'obertura del tema. I una lletra o família buida cau al valor per
    defecte del model («-» i, la família, la lletra) en comptes de quedar
    `None` — que després s'hauria escrit al CSV com «None».
    """
    items = []
    with open(ruta, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                ini = float(r["inici_s"])
                fi = float(r["fi_s"])
            except (TypeError, ValueError, KeyError):
                logging.getLogger("auto_chords").warning(
                    "estructura: linia ignorada (no vàlida): %r", r)
                continue
            lletra = str(r.get("lletra") or "").strip() or pipeline.SENSE_SECCIO
            fam = str(r.get("família") or "").strip() or lletra
            items.append((ini, fi, lletra, fam))
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
    # El mapa de tempo/compàs ha canviat (diàleg, drag, undo…): la finestra
    # principal ha de refrescar els camps BPM/compàs del clip objectiu.
    tempoCanviat = pyqtSignal()
    # Velocitat de reproducció canviada (0,5–3×): la barra de la finestra
    # principal té el seu propi selector i ha d'anar sincronitzada.
    velocitatCanviada = pyqtSignal(float)
    def __init__(self, wav, acords, abc, bpm, bpb, tempo_fix=True, sortida=None,
                 offset=0.0, beat_type=4):
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
        self.beat_type = int(beat_type or 4)
        self.offset = float(offset or 0.0)
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
        # Regla #4 a TOTES les pistes: un projecte pot arribar amb una pista
        # buida (p. ex. sense estructura). El visor sempre n'ha de mostrar una
        # que cobrisca 0 → durada, com fa el model inicial.
        _dur = self._durada_wav()
        if not self.acords:
            self.acords = [pipeline.Clip(0.0, _dur, pipeline.FORAT_ACORD)]
            nou_model = True
        if not self.seccions:
            self.seccions = [(0.0, _dur, pipeline.SENSE_SECCIO,
                              pipeline.SENSE_SECCIO)]
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
        # Mapa de TEMPO i COMPÀS: dels CSVs del projecte o, si no n'hi
        # ha, un **sol tros** amb el BPM·compàs actual (zero canvi visible).
        self.tempo_trams = pipeline.llegeix_tempo_map(
            self._carpeta_acords(), self.bpm, self.bpb, 4, self._durada_wav())
        # Neteja els duplicats de l'anàlisi/projectes vells: dos trams
        # adjacents amb el mateix BPM i compàs no són cap canvi musical.
        self.tempo_trams = tempo_map.fusiona_trams_iguals(
            self.tempo_trams, self._durada_wav())
        self.tempo_map = None
        self._refresca_tempo_map()
        # Marcadors humans (inici de compàs marcat a mà, en viu)
        self.marcadors = pipeline.llegeix_marcadors(
            self._carpeta_acords(), self._durada_wav())
        # Els projectes vells poden portar fronteres de tempo fora de compàs.
        # No es rebutgen en carregar, però l'usuari ha de saber que eixe mapa
        # no complirà la regla de compassos enters fins que l'edite.
        try:
            tempo_map.valida_i_normalitza_compassos(
                self.tempo_trams, self._durada_wav(),
                offset=getattr(self, "offset", 0.0))
        except ValueError as e:
            self.log(f"AVÍS: el mapa de tempo/compàs no complix els compassos "
                     f"enters: {e}")
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
        self._pinta_marcadors()      # els del projecte, si n'hi havia
        self.timeline.positionChanged.connect(self.ves_a)
        self.timeline.clipSelected.connect(self._on_clip_selected)
        self.timeline.playRequested.connect(self.play_stop)
        self.timeline.editStarted.connect(self._on_edit_started)
        self.timeline.editFinished.connect(self._on_edit_finished)
        self.timeline.editCancelled.connect(self._on_edit_cancelled)
        self.timeline.loopChanged.connect(self._on_loop_changed)
        self.timeline.escapePressed.connect(self._on_escape_pressed)
        self.timeline.chordTimeMoved.connect(self._on_chord_time_moved)
        self.timeline.chordEndMoved.connect(self._on_chord_end_moved)
        self.timeline.chordRenamed.connect(self._on_chord_renamed)
        self.timeline.chordDeleteRequested.connect(self._elimina_acord_index)
        self.timeline.chordEditRequested.connect(self._on_chord_edit_requested)
        self.timeline.sectionMoved.connect(self._on_section_moved)
        self.timeline.sectionRenamed.connect(self._on_section_renamed)
        self.timeline.sectionDeleteRequested.connect(self._elimina_seccio_index)
        self.timeline.multiDeleteRequested.connect(self._elimina_seleccio)
        self.timeline.pasteRequested.connect(self._enganxa_seleccio)
        self.timeline.clipContextMenuRequested.connect(
            self._on_clip_context_menu)
        # Despatx ÚNIC de les ordres d'edició que arriben del teclat del
        # timeline (Del, Ctrl+C/X/V/D, fletxes): el timeline només envia la
        # intenció i el Visor resol el carril i la selecció.
        self.timeline.editCommandRequested.connect(self._on_edit_command)
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
        self.ed_nom_lbl = QLabel("Nom:")
        _eh.addWidget(self.ed_nom_lbl)
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
        # Tercera llista: clips de tempo/compàs (una fila per tram). Taula per
        # veure inici/fi/BPM/compàs de colp d'ull; l'edició va a la franja
        # Editor, igual que a les llistes d'acords i seccions.
        self.llista_tempo = QTableWidget(0, 4)
        self.llista_tempo.setHorizontalHeaderLabels(
            ["Inici (s)", "Fi (s)", "BPM", "Compàs"])
        self.llista_tempo.verticalHeader().setVisible(False)
        self.llista_tempo.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.llista_tempo.setSelectionMode(QAbstractItemView.SingleSelection)
        self.llista_tempo.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.llista_tempo.setShowGrid(False)
        self.llista_tempo.setContextMenuPolicy(Qt.CustomContextMenu)
        self.llista_tempo.setToolTip(
            "Clic: salta. Doble-clic: edita a la franja Editor.")
        # Files: les xifres a la seua amplada i el BPM s'emporta el que sobra
        # (així «100.000» no es talla quan el tauler és estret).
        for _c in (0, 1, 3):
            self.llista_tempo.horizontalHeader().setSectionResizeMode(
                _c, QHeaderView.ResizeToContents)
        self.llista_tempo.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.Stretch)
        self._omple_llista_tempo()
        self.llista_tempo.itemClicked.connect(self._salt_tempo)
        self.llista_tempo.itemDoubleClicked.connect(
            lambda it: self._focus_editor("tempo", self.llista_tempo.row(it)))
        self.llista_tempo.customContextMenuRequested.connect(self._menu_tempo)
        div.addWidget(self.llista_tempo)
        # La taula de tempo necessita més amplada que una llista de noms.
        div.setStretchFactor(0, 3)
        div.setStretchFactor(1, 3)
        div.setStretchFactor(2, 4)
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
        # Velocitat de reproducció (0,5–3×, to mantingut amb `ffmpeg atempo`).
        fila2.addWidget(self._crea_selector_velocitat())
        self.etiqueta = QLabel(f"{self.audio['durada']:.1f} s · "
                               f"{len(self.acords)} acords · "
                               f"{len(self.seccions)} seccions")
        fila2.addWidget(self.etiqueta)
        capa.addLayout(fila2)
        self._actualitza_temps()

        # estat de transports
        self.vol = 1.0
        self.mut = False
        # Velocitat de reproducció (1,0× = normal). El buffer estirat es
        # renderitza UNA vegada per factor i es queda a `_vel_cache`; els
        # temporals de `ffmpeg` es netegen en tancar (paperera).
        self.velocitat = 1.0
        self._vel_cache = {}
        self._vel_temporals = []
        # metrònom: clic mesclat al buffer (no afectat pel mute/volum cançó)
        self.metro_on = False
        self.metro_vol = 0.6
        # Metrònom FORÇAT (None = normal): `(bpm, bpb, offset)` fa sonar el
        # clic sobre una graella pròpia, alineada a `offset`, sense passar pel
        # mapa de tempo. És el que permet escoltar un tram del guiat **encara
        # no aplicat** (i moure'n el BPM en viu).
        self.metro_forcat = None
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
            return f"{s:07.3f}s"
        # El MAPA mana: amb diversos trams de tempo/compàs, cada instant pot
        # tindre una durada de compàs distinta. La via constant de davall
        # queda només com a fallback si encara no hi ha mapa.
        mapa = getattr(self, "tempo_map", None)
        if mapa is not None:
            c, b, sub = mapa.pos(float(s))
            return f"{c}.{b}" if sub == 1 else f"{c}.{b}.{sub}"
        # Fallback constant (offset inclòs i compassos negatius/count-in).
        beat_len = 60.0 / self.bpm
        p = int(round((float(s) - getattr(self, "offset", 0.0))
                      / beat_len * 8))
        SB = max(1, int(self.bpb)) * 8
        compas = p // SB + 1
        dins = p % SB
        beat = dins // 8 + 1
        sub = dins % 8 + 1
        return f"{compas}.{beat}" if sub == 1 else f"{compas}.{beat}.{sub}"




    def _parse_pos_label(self, text):
        if "s" in text:
            m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*s", text)
            if m:
                return float(m.group(1))
        m = re.search(r"(-?\d+)\.(\d+)(?:\.(\d+))?", text)
        if m:
            compas = int(m.group(1))
            beat = int(m.group(2))
            sub = int(m.group(3)) if m.group(3) else 1
            sub = max(1, min(8, sub))
            mapa = getattr(self, "tempo_map", None)
            if mapa is not None:
                t = mapa.t_de_pos(compas, beat)
                if sub > 1:
                    _bar_s, beat_s, _sub_s = mapa.durations(t)
                    t += (sub - 1) / 8.0 * beat_s
                return max(0.0, float(t))
            return (((compas - 1) * self.bpb + (beat - 1)
                     + (sub - 1) / 8.0) * (60.0 / self.bpm))
        return float(text.split()[0])

    def _omple_llista_ac(self):
        # Preserva la fila seleccionada: _actualitza_temps() repobla la llista
        # i, sense aixo, el clear() en perdia la seleccio (bug: clicar una
        # fila no la deixava ressaltada perque ves_a()->_actualitza_temps()).
        cur = self.llista_ac.currentRow()
        self.llista_ac.clear()
        for _a in self.acords:
            t, c = float(_a[0]), nom_acord(_a)
            et = self._fmt_compas(t) if self.tempo_fix else f"{t:07.3f}s"
            self.llista_ac.addItem(f"{et}  {c}")
        if 0 <= cur < self.llista_ac.count():
            self.llista_ac.setCurrentRow(cur)

    def _valida_canvis_acords(self, items):
        """Delega la validació i derivació de `fi` d'acords a `pipeline`."""
        return pipeline.valida_canvis_acords(items, self._durada_wav())

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
        item = pipeline.Clip(float(t), float(t), (nom, f"{float(t):.9f}"))
        nova = self._normalitza_acords(self.acords + [item])
        self.acords = nova
        # Regla #4 per a TOT el carril: si el clip nou deixa un forat al
        # davant o al darrere, s'hi posa la «N» canònica. Així l'alta deixa
        # el model vàlid a l'instant (no només quan es desa).
        self._normalitza_cobertura()
        if hasattr(self, "llista_ac"):
            self._omple_llista_ac()
        # ⚠️ TOTA mutació del model refresca la VISTA (regla «el visor reflectix
        # el model»). Ho fa la pròpia primitiva perquè cap camí —present o
        # FUTUR— no puga oblidar-se'n i deixar un clip sense pintar (bug real
        # 19-10-2026, caçat amb el fuzzer de `test_vista_segueix_model`).
        self._sincronitza_vista()
        return True

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
        """Botó dret a la LLISTA d'acords (mateixa definició que el timeline)."""
        self._menu_de_llista("chord", getattr(self, "llista_ac", None), pos)

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
            pipeline.clips_d_acords(self.acords, d), d, pipeline.FORAT_ACORD,
            arrodoneix=True, deriva_fi=True, log=self.log)
        _, self.seccions = pipeline.normalitza_cobertura(
            [], self.seccions, d, log=self.log)
        return self.acords != a0 or self.seccions != s0

    def _index_valid(self, kind, idx):
        """L'índex `idx` encara existeix al carril `kind`? (per re-seleccionar)."""
        if kind == "chord":
            return 0 <= idx < len(self.acords)
        if kind == "section":
            return 0 <= idx < len(self.seccions)
        if kind == "tempo":
            return 0 <= idx < len(self.tempo_trams or [])
        return False

    def clips_seleccionats(self):
        """Conjunt `{(kind, idx)}` vàlid de la selecció del timeline (3 carrils)."""
        if getattr(self, "timeline", None) is None:
            return set()
        keys = self.timeline.selected_keys()
        return {(k, int(i)) for (k, i) in keys if self._index_valid(k, int(i))}

    def seleccio_activa(self):
        """`(kind, idx)` de l'element ACTIU, incloent-hi els trams de tempo.

        És l'equivalent únic de l'antic `main._clip_seleccionat()` (que només
        mirava acords i seccions). Si l'element actiu del timeline encara és
        vàlid, mana eixe; si no, es tria el primer vàlid de la selecció.
        """
        if getattr(self, "timeline", None) is None:
            return None, -1
        keys = self.clips_seleccionats()
        if not keys:
            return None, -1
        k, i = getattr(self.timeline, "_sel", ("", -1))
        if (k, i) in keys:
            return k, i
        return next(iter(sorted(keys)))

    def tempo_objectiu(self):
        """Índex del tram de tempo objectiu.

        Si hi ha un tram de tempo seleccionat, mana eixe (el clip actiu de la
        selecció); si no, el **transport** (tram 0). Decisió 2026-10-19.
        """
        kind, idx = self.seleccio_activa()
        if kind == "tempo" and self._index_valid("tempo", idx):
            return int(idx)
        return 0

    def tempo_objectiu_vals(self):
        """`(idx, bpm, num, den)` del tram objectiu (o del transport)."""
        trams = list(self.tempo_trams or [])
        idx = self.tempo_objectiu()
        if not trams:
            return (idx, float(self.bpm), int(self.bpb),
                    int(getattr(self, "beat_type", 4) or 4))
        idx = min(max(0, int(idx)), len(trams) - 1)
        s = trams[idx]
        return (idx, float(s[2]), int(s[3]), int(s[4]))

    def edita_tempo_objectiu(self, idx, bpm, num, den, desa=True):
        """Aplica BPM/compàs a un tram de tempo (0 = transport).

        Re-tempo local (`docs/REGLES_DE_LA_APP.md` §13.5): el tram conserva el
        seu nombre de compassos, la seua durada passa a `N · bq · 60 / BPM` i
        el veí de la dreta conserva els compassos i el seu final recalculant el
        BPM. Els trams posteriors **no es mouen** (sense *ripple*). Si el canvi
        no és vàlid, es rebutja amb un avís.

        Amb `desa=False` (tap en viu) el canvi queda només en memòria; el desat
        es fa en tancar la sessió de taps.
        """
        trams = list(self.tempo_trams or [])
        if not trams:
            trams = [(0.0, self._durada_wav(), float(bpm), int(num), int(den))]
        idx = min(max(0, int(idx)), len(trams) - 1)
        try:
            nous = tempo_map.canvia_bpm_local(
                trams, idx, float(bpm), self._durada_wav(),
                offset=getattr(self, "offset", 0.0),
                num=int(num), den=int(den))
        except ValueError as e:
            self.avis_editor(f"Tempo: {e}")
            return False
        if not nous:
            return False
        # El transport només pren valors d'un tros AMB compàs: un primer tros
        # «en segons» (0/0) no ha de deixar `bpb` a zero.
        if int(nous[0][3]) > 0 and int(nous[0][4]) > 0:
            self.bpm = float(nous[0][2])
            self.bpb = int(nous[0][3])
            self.beat_type = int(nous[0][4])
        if desa:
            return bool(self.aplica_tempo_trams(nous))
        # En memòria: el mapa es reconstrueix i la vista es refresca, però no
        # s'escriu cap CSV ni s'emet `canvis` (ho farà el tancament de sessió).
        self.tempo_trams = nous
        self._actualitza_temps()
        return True

    def _sincronitza_vista(self, preserva=False, difereix=False):
        """Punt ÚNIC de sincronització **MODEL → VISTA**.

        Regla del preàmbul de les regles d'or: «el que es veu a la pantalla
        reflecteix el model vàlid». Després de qualsevol mutació, els items del
        timeline i les llistes han de quadrar amb `self.acords`/`self.seccions`.

        Per què existeix: abans això estava repartit per desenes de camins i qui
        s'oblidava de refrescar deixava la vista **mentint** (p. ex. un acord
        acabat d'afegir sense pintar, o un clip arrossegat que es quedava a la
        posició de PREVISUALITZACIÓ mentre el model n'havia adoptat una altra).
        Bug real trobat el 19-10-2026 amb el fuzzer de `test_vista_segueix_model`.

        `preserva` → re-aplica la selecció prèvia (només els índexs que encara
        són vàlids, perquè `set_data` sempre buida la selecció).
        `difereix` → ho programa al cicle següent de l'esdeveniment. És
        OBLIGATORI quan s'edita des de DINS l'esdeveniment d'un item (el release
        d'un arrossegament): esborrar i reconstruir eixe mateix item allà no és
        segur (mateix motiu pel qual `timeline._tanca_bloc` difereix).
        """
        # Hi ha camins (i tests) que fan servir el Visor sense timeline.
        if getattr(self, "timeline", None) is None:
            return
        seleccio = sorted(self.timeline.selected_keys()) if preserva else []

        def _fer():
            try:
                self.timeline.set_data(self.acords, self.seccions)
            except RuntimeError:
                return          # l'escena ja s'ha destruït (visor tancat)
            if seleccio:
                viu = {(k, i) for (k, i) in seleccio if self._index_valid(k, i)}
                if viu:
                    self.timeline.select_multi(viu)
            if hasattr(self, "llista_ac"):
                self._omple_llista_ac()
            if hasattr(self, "llista_ab"):
                self._actualitza_llista_abc()

        if difereix:
            QTimer.singleShot(0, _fer)
        else:
            _fer()

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

        El mapa és la font del tempo/compàs variables: la graella, el regle, el
        snap i els exports en surten. Sense trossos, se'n crea un de sol amb el
        BPM·compàs actual.
        """
        from app.tempo_map import TempoMap, normalitza_trams
        d = self._durada_wav()
        # Regles 1, 2, 4 i 8: aquest és el PUNT ÚNIC on es construeix el mapa,
        # així que el que hi entra s'hi ha de complir sempre. Si la còpia no ho
        # complia (CSV editat a mà, un estat vell de l'undo, un client de
        # ací queda arreglada abans de construir l'objecte.
        trams = normalitza_trams(list(self.tempo_trams or []), d)
        den = int(getattr(self, "beat_type", 4) or 4)

        def _lliure(t):
            return int(t[3]) <= 0 or int(t[4]) <= 0

        if len(trams) <= 1:
            # Un sol tros = el cas constant d'avui, EXCEPTE si va en segons
            # (rubato): llavors el transport no hi té res a dir.
            if not (trams and _lliure(trams[0])):
                trams = [(0.0, d, float(self.bpm), int(self.bpb), den)]
        elif not _lliure(trams[0]):
            # El tram 0 és el VALOR INICIAL (el transport mana), però només
            # si té compàs: un primer clip en segons no s'ha de convertir
            # en 4/4 al BPM de la barra.
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
        # El transport només pren valors d'un tros AMB compàs: un primer tros
        # «en segons» (0/0) no ha de deixar `bpb` a zero.
        if int(nous[0][3]) > 0 and int(nous[0][4]) > 0:
            self.bpm = float(nous[0][2])
            self.bpb = int(nous[0][3])
            self.beat_type = int(nous[0][4])
        self.tempo_trams = nous
        # Refresca mapa + timeline + LLISTES (les etiquetes de compàs depenen
        # de l'offset i del BPM; `_actualitza_temps` és el punt únic).
        self._actualitza_temps()
        try:
            pipeline.desa_tempo_map(self._carpeta_acords(), self.tempo_trams)
        except Exception as e:  # noqa: BLE001
            self.log(f"desa mapa tempo/compàs ERROR: {e}")
        # Els compassos són una vista derivada del mapa: en canviar el tempo,
        # les columnes `compas_ini`/`compas_fi` de l'ABC han de quadrar amb la
        # graella nova. Els SEGONS no es mouen (model audio-first).
        self._regenera_posicions_musicals("canvi de tempo/compàs")
        # Si el canvi ve de FORA d'una operacio (carrega, analisi, el dialeg
        # del mapa...), la base del desfer s'ha de quedar al dia; si ve de
        # dins d'una operacio oberta, no fa res.
        self._undo_touch_base()
        self.canvis.emit()   # el mapa ha canviat → el projecte queda «brut»
        self.tempoCanviat.emit()   # la barra ha de refrescar BPM/compàs
        self.log(f"mapa de tempo/compàs: {len(nous)} tros(s)")
        return True

    def aplica_tempo_validat(self, trams, msg="Tempo"):
        """Aplica un mapa només si compleix els compassos enters.

        Punt d'entrada de la GUI per als canvis de mapa (diàleg, eliminar,
        fusionar, duplicar…). El backend `aplica_tempo_trams` continua
        permissiu per a càrregues de projectes vells i tests.
        """
        try:
            nous = tempo_map.valida_i_normalitza_compassos(
                trams, self._durada_wav(),
                offset=getattr(self, "offset", 0.0))
        except ValueError as e:
            self.avis_editor(f"{msg}: {e}")
            return False
        return bool(self.aplica_tempo_trams(nous))

    def _normalitza_mapa_viu(self, trams, msg=None):
        """Mapa validat per a un gest en viu, sense bloquejar-lo.

        Els gestos de tempo (marcador `+`, re-tempo pel ratolí, «Detecta»)
        construeixen el mapa perquè els trams afectats complisquen el contracte
        de compassos enters. Si un ALTRE tram arrossega una desviació vella, el
        mapa s'aplica normalitzat (permissiu): **no es mou cap frontera**, que
        és la veritat de l'operador (el lloc on ha deixat el marcador o la
        nansa). El que no pot passar és que una frontera heretada impedisca
        editar.
        """
        durada = self._durada_wav()
        offset = getattr(self, "offset", 0.0)
        try:
            return tempo_map.valida_i_normalitza_compassos(
                trams, durada, offset)
        except ValueError as e:
            if msg:
                self.log(f"{msg}: frontera heretada fora de graella ({e})")
            return tempo_map.normalitza_trams(trams, durada)

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
        self._undo_marca()
        self.edita_tempo_objectiu(idx, bpm, num, den)
        self._undo_commit()

    def _on_tempo_mogut(self, idx, vora, t):
        """Vora d'un bloc de BPM/compàs arrossegada → **re-tempo** (el ratolí mana).

        Des del 21-10-2026 (`docs/REGLES_DE_LA_APP.md` §13.5) la jerarquia
        està invertida: el punter fixa **Δt**, els **compassos N** dels dos
        costats es conserven i el **BPM** es recalcula. Per això ja no s'imanta
        a la línia de compàs del tram anterior ni s'arrosseguen els trams
        següents (`_ripple_des_de`): **cap altre tram no es mou** i la frontera
        cau sempre en línia de compàs per construcció (el validador de
        compassos enters ja no pot bloquejar el gest).

        Si el marcador humà d'eixa frontera coincidia, es mou amb ella (§4.C),
        tot dins del **mateix** desfer.
        """
        trams = list(self.tempo_trams or [])
        if not (0 <= idx < len(trams)):
            return
        # `idx` és el tram de la vora tocada; la frontera és el SEU inici
        # («ini»/«cos») o el del SEGÜENT («fi»). `mou_frontera_retempo` rep
        # l'índex del tram de la DRETA (la frontera és el seu inici).
        p_idx = int(idx) if str(vora).strip().lower() == "ini" else int(idx) + 1
        if not (0 < p_idx < len(trams)):
            # Els extrems del tema no es toquen: marquen l'inici i el final WAV.
            if p_idx <= 0:
                self.avis_editor(
                    "L'inici del primer clip marca l'inici de la WAV")
            else:
                self.avis_editor(
                    "La fi de l'últim clip marca el final de la WAV")
            return
        vell = float(trams[p_idx][0])
        offset = float(getattr(self, "offset", 0.0))
        if tempo_map.es_frontera_preroll(trams, p_idx, offset):
            # El tall és el COMPÀS 1 (el primer tram no té cap compàs): el gest
            # el mou a ell i el tram de música conserva els seus compassos.
            try:
                nous, nou_off = tempo_map.mou_frontera_preroll(
                    trams, p_idx, float(t), self._durada_wav(), offset)
            except ValueError as e:
                self.avis_editor(f"Compàs 1: {e}")
                return
            self._undo_marca()
            self.offset = float(nou_off)
            if self.aplica_tempo_trams(nous):
                self._mou_marcador(vell, float(self.tempo_trams[p_idx][0]))
            self._undo_commit()
            return
        try:
            nous = tempo_map.mou_frontera_retempo(
                trams, p_idx, float(t), self._durada_wav(), offset=offset)
        except ValueError as e:
            self.avis_editor(f"Frontera de tempo: {e}")
            return
        self._undo_marca()
        if self.aplica_tempo_trams(nous):
            self._mou_marcador(vell, float(self.tempo_trams[p_idx][0]))
        self._undo_commit()

    def canvia_compassos_tram(self, idx, delta_compassos=0, factor=None):
        """Correcció **mètrica** discreta d'un tram de tempo (§4.C del flux).

        `+1`/`−1` compassos o `×2`/`÷2`: els **segons queden immòbils**, els
        veïns no es toquen i el BPM es recalcula (`tempo_map.canvia_compassos_tram`).
        Un sol desfer. Retorna `True` si el mapa ha canviat.
        """
        trams = list(self.tempo_trams or [])
        idx = -1 if idx is None else int(idx)
        if not (0 <= idx < len(trams)):
            return False
        try:
            nous = tempo_map.canvia_compassos_tram(
                trams, idx, delta_compassos=delta_compassos,
                durada=self._durada_wav(),
                offset=getattr(self, "offset", 0.0), factor=factor)
        except ValueError as e:
            self.avis_editor(f"Compassos: {e}")
            return False
        if [tuple(x) for x in nous] == [tuple(x) for x in trams]:
            return False
        self._undo_marca()
        ok = self.aplica_tempo_trams(nous)
        self._undo_commit()
        if ok:
            self.log(f"compassos tram {idx}: {trams[idx][2]:g} → "
                     f"{self.tempo_trams[idx][2]:.2f} BPM "
                     f"({self._compassos_de(idx):g} compassos)")
        return bool(ok)

    def _compassos_de(self, idx):
        """Compassos (arredonits) del tram `idx` del mapa viu (per a missatges)."""
        trams = list(self.tempo_trams or [])
        if not (0 <= int(idx) < len(trams)):
            return 0
        try:
            n = tempo_map._compassos_del_tram(
                trams[int(idx)], int(idx), getattr(self, "offset", 0.0))
        except ValueError:
            return 0
        return tempo_map._enter_mes_proper(max(1.0, n))

    def _on_tempo_menu(self, idx, t):
        """Botó dret a la pista ③ BPM/compàs.

        Regla d'or #11: **la mateixa definició de menú** que ④ estructura i
        ⑤ acords (vegeu `_menu_contextual`), pel mateix camí d'usuari.
        """
        idx = -1 if idx is None else int(idx)
        menu = self._menu_contextual("tempo", idx, float(t))
        accio = menu.exec_(QCursor.pos())
        self._executa_contextual("tempo", idx, float(t),
                                 accio.data() if accio else None, "timeline")

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
        # Mapa de tempo/compàs: un sol tros → se sincronitza amb el
        # BPM·compàs actual (zero canvi visible); amb més trossos, es respecta.
        if (len(self.tempo_trams) <= 1
                and not (self.tempo_trams
                         and (int(self.tempo_trams[0][3]) <= 0
                              or int(self.tempo_trams[0][4]) <= 0))):
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
        """(acords, seccions) — el MODEL (font de veritat del backend)."""
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
            # El MAPA de tempo/compas tambe es desfeu (abans no: editar
            # els trams era irreversible i el Ctrl+Z no els tornava).
            "tempo_trams": copy.deepcopy(list(self.tempo_trams or [])),
            # Els marcadors humans també es desfan (es creen amb `+` en viu).
            "marcadors": list(getattr(self, "marcadors", []) or []),
        }

    def _estat_complet(self):
        """Estat apilable pel desfer/refer: `(acords, seccions, temps)`."""
        return self._estat_edicio() + (self._estat_temps(),)

    def _aplica_temps(self, temps):
        """Restaura la graella/loop desats (i refresca la UI si ja existeix)."""
        for k in ("bpm", "bpb", "beat_type", "offset", "tempo_fix"):
            if temps.get(k) is not None:
                setattr(self, k, temps[k])
        if "marcadors" in temps and temps.get("marcadors") is not None:
            self.marcadors = list(temps["marcadors"])
            self._pinta_marcadors()
        tt = temps.get("tempo_trams")
        if tt is not None:
            self.tempo_trams = copy.deepcopy(list(tt))
            try:
                self._refresca_tempo_map()
                if self.tempo_trams:
                    pipeline.desa_tempo_map(self._carpeta_acords(),
                                            self.tempo_trams)
            except Exception as e:  # noqa: BLE001
                self.log(f"tempo/compas: no s'ha pogut restaurar el mapa: {e}")
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
                        f"({float(a0[0]):.3f}s → {float(a1[0]):.3f}s)")
        for (i0, f0, l0, fa0), (i1, f1, l1, fa1) in zip(se0, se1):
            if l0 != l1 or fa0 != fa1:
                return f"reanomenar la secció «{l0}» → «{l1}»"
            if abs(float(i0) - float(i1)) > 1e-6 or abs(float(f0) - float(f1)) > 1e-6:
                return (f"moure la secció «{l1}» "
                        f"({float(i0):.3f}s → {float(i1):.3f}s)")
        # A1: canvis de GRAELLA o de LOOP (que no toquen el model).
        if tp0.get("bpm") != tp1.get("bpm"):
            return f"canviar el BPM ({tp0['bpm']:g} → {tp1['bpm']:g})"
        if (tp0.get("bpb") != tp1.get("bpb")
                or tp0.get("beat_type") != tp1.get("beat_type")):
            return "canviar el compàs"
        if tp0.get("offset") != tp1.get("offset"):
            return (f"canviar l'offset ({tp0['offset']:.3f}s → "
                    f"{tp1['offset']:.3f}s)")
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
        self.log(f"loop A = {self.loop_a:.3f}s")
        if self.loop_b is not None:
            self.timeline.set_loop(self.loop_a, self.loop_b)
        if self.loop_on and getattr(self, "sona", False):
            self._alinea_cursor_loop(self.pos)   # moure A sonant: re-alinea
        self._undo_commit()

    def marca_B(self):
        self._undo_marca()
        self.loop_b = self.timeline.snap(self.pos)
        self.log(f"loop B = {self.loop_b:.3f}s")
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

    def _fixa_loop(self, a, b, activa=True, alinea=True):
        """Fixa el loop A/B **sense** tocar l'undo (el caller el gestiona).

        Pensat per al tap tempo automàtic i per a «Loop a la selecció»: el
        canvi de loop forma part de la mateixa operació que l'edició. Si està
        sonant i el cursor queda fora, l'alinea a l'inici (so i cursor quadren).
        """
        self.loop_a = None if a is None else float(a)
        self.loop_b = None if b is None else float(b)
        self.loop_on = bool(
            activa and self.loop_a is not None and self.loop_b is not None
            and self.loop_b > self.loop_a)
        if hasattr(self, "b_loop"):
            self.b_loop.setChecked(self.loop_on)
        self.loopStateChanged.emit(self.loop_on)
        self._pinta_loop()
        if self.loop_on and alinea and getattr(self, "sona", False):
            self._alinea_cursor_loop(self.pos)
        self.log(f"loop {'ON' if self.loop_on else 'OFF'}"
                 + (f" A={self.loop_a:.3f}s B={self.loop_b:.3f}s"
                    if self.loop_on else ""))
        return self.loop_on

    def loop_a_la_seleccio(self, kind=None, idx=None):
        """Posa el loop A/B a la **unió** de la selecció (3 carrils).

        Un sol clip → les seues fronteres. Diversos (o selecció mixta) → del
        mínim inici al màxim final. Sense selecció, si el menú contextual ha
        apuntat un clip vàlid, s'usa eixe. És una sola operació d'undo i, si
        està sonant, alinea el cursor a l'inici del loop.
        """
        keys = self.clips_seleccionats()
        if not keys and kind in self._KINDS_EDICIO and idx is not None:
            i = int(idx)
            if self._index_valid(kind, i):
                keys = {(kind, i)}
        if not keys:
            self.avis_editor(
                "Loop a la selecció: no hi ha cap clip seleccionat.")
            return False
        inis, fis = [], []
        for k, i in keys:
            if k == "chord":
                c = self.acords[i]
                inis.append(float(c.ini))
                fis.append(float(c.fi))
            elif k == "section":
                s = self.seccions[i]
                inis.append(float(s[0]))
                fis.append(float(s[1]))
            elif k == "tempo":
                tr = (self.tempo_trams or [])[i]
                inis.append(float(tr[0]))
                fis.append(float(tr[1]))
        if not inis:
            return False
        a, b = min(inis), max(fis)
        if b <= a:
            return False
        self._undo_marca()
        self._fixa_loop(a, b, activa=True, alinea=True)
        self._undo_commit()
        self.avis_editor(f"Loop a la selecció: {a:.3f}–{b:.3f}s "
                         f"({len(keys)} clip(s))")
        return True

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

    # -- velocitat de reproducció (0,5–3×, to mantingut) -------------------
    VELOCITATS = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0)

    def _crea_selector_velocitat(self):
        """Desplegable de velocitat (es fa servir al visor i a la finestra)."""
        c = QComboBox()
        for v in self.VELOCITATS:
            c.addItem(f"{v:g}×", float(v))
        c.setToolTip("Velocitat de reproducció (0,5–3×) amb el TO MANTINGUT "
                     "(ffmpeg atempo, com el VLC). El cursor, el loop i el "
                     "metrònom es mantenen alineats. El primer cop a cada "
                     "velocitat pot trigar uns segons a preparar l'àudio.")
        c.setMaximumWidth(80)
        c.setCurrentIndex(self.VELOCITATS.index(1.0))
        c.currentIndexChanged.connect(
            lambda _i, cc=c: self.set_velocitat(cc.currentData()))
        self.cmb_vel = c
        return c

    def _sincronitza_selector_velocitat(self):
        """Posa el desplegable al valor vigent (sense disparar el canvi)."""
        c = getattr(self, "cmb_vel", None)
        if c is None:
            return
        i = c.findData(round(float(getattr(self, "velocitat", 1.0)), 4))
        if i < 0:
            return
        c.blockSignals(True)
        c.setCurrentIndex(i)
        c.blockSignals(False)

    def _mono_a(self, factor):
        """PCM mono 16 bits per reproduir a `factor`× (to mantingut).

        A 1,0× és el buffer de sempre (cost zero). La resta es renderitza amb
        `ffmpeg atempo` **una vegada per factor** (`ffmpeg.prepara_escolta`,
        que ja cacheja per mtime+mida+factor) i es queda a `_vel_cache`
        mentre el visor viu.
        """
        f = round(float(factor), 4)
        if abs(f - 1.0) < 1e-9:
            return self._mono_bytes()
        if f in self._vel_cache:
            return self._vel_cache[f]
        if not ffmpeg.disponible():
            raise RuntimeError("cal ffmpeg per canviar la velocitat")
        dest = ffmpeg.prepara_escolta(self.wav_path, f, log=self.log)
        try:
            mono = llegeix_wav(dest)["mono"]
        finally:
            # El temporal només es toca en tancar (paperera), mai `rm`.
            if dest != self.wav_path and dest not in self._vel_temporals:
                self._vel_temporals.append(dest)
        self._vel_cache[f] = mono.astype(np.int16).tobytes()
        # Memòria: com a molt 2 factors en caché (en un tema llarg, cadascun
        # pot ser de desenes de MB). Es descarta el més antic.
        while len(self._vel_cache) > 2:
            self._vel_cache.pop(next(iter(self._vel_cache)))
        return self._vel_cache[f]

    def set_velocitat(self, factor, avisar=True):
        """Canvia la velocitat de reproducció (0,5–3,0×, to mantingut).

        Si està sonant, es repren **exactament** a la mateixa posició de la
        cançó (el cursor no salta): el buffer estirat es llig des d'on toca.
        """
        try:
            f = float(factor)
        except (TypeError, ValueError):
            return
        f = round(max(0.5, min(3.0, f)), 2)
        if abs(f - float(getattr(self, "velocitat", 1.0))) < 1e-9:
            self._sincronitza_selector_velocitat()
            return
        # Preparar el buffer ABANS de tocar la reproducció: si falla, no canvia.
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                self._mono_a(f)
            finally:
                QApplication.restoreOverrideCursor()
        except (RuntimeError, OSError, ValueError) as e:
            self.log(f"velocitat {f:g}×: no s'ha pogut preparar ({e})")
            if avisar:
                QMessageBox.warning(self, "Velocitat",
                                    f"No s'ha pogut preparar l'àudio a "
                                    f"{f:g}×:\n{e}")
            self._sincronitza_selector_velocitat()
            return
        sonava = bool(self.sona)
        pos = float(self.pos)
        if sonava:
            self._atura_proc()     # invalida el fil vell (el rellotge segueix)
        self.velocitat = f
        self._sincronitza_selector_velocitat()
        self.log(f"velocitat: {f:g}×"
                 + (" (to mantingut)" if abs(f - 1.0) > 1e-9 else ""))
        if sonava:
            self._engega_des_de(pos)   # re-ancora t0 amb la velocitat nova
            if self.proc is None:
                self.play_stop()
        self.velocitatCanviada.emit(f)

    def metro_disponible(self):
        """El metrònom només té sentit amb graella (mode BPM · compàs)."""
        return bool(self.tempo_fix)

    def set_metro(self, on):
        """Fixa l'estat del metrònom — **sense tallar la reproducció**.

        El fil d'alimentació llig `metro_on`/`metro_vol` a **cada tros**, igual
        que fa amb el volum i el mute: el canvi s'aplica a l'instant. Abans es
        reiniciava el reproductor (`_atura_proc` + `_engega_des_de`) i se sentia
        un **micro-tall** a l'àudio cada cop que es posava o treia el metrònom
        (reportat per l'operador, 18-10-2026). El reinici era un vestigi de quan
        el clic es pre-mesclava a la memòria.
        """
        on = bool(on)
        if on == self.metro_on:
            return
        self.metro_on = on
        self.log(f"metrònom {'ON' if self.metro_on else 'OFF'}")

    def commuta_metro(self):
        """Activa/desactiva el metrònom (sense tallar la reproducció)."""
        self.set_metro(not self.metro_on)

    def set_metro_forcat(self, bpm=None, bpb=4, offset=0.0):
        """Metrònom sobre una graella pròpia: `bpm` + `bpb` des de `offset`.

        Amb `bpm=None` es torna al metrònom normal (mapa de tempo o BPM de la
        barra). El fil d'àudio ho llig **a cada tros**, així que el canvi de
        BPM o l'encesa/apagada s'apliquen a l'instant i **sense reiniciar** el
        reproductor (cap micro-tall).
        """
        if bpm is None:
            self.metro_forcat = None
            self.log("metrònom forçat: OFF (torna al mapa)")
            return
        bpm = float(bpm)
        if not (bpm > 0):
            self.metro_forcat = None
            return
        self.metro_forcat = (bpm, max(1, int(bpb)), float(offset))
        self.log(f"metrònom forçat: {bpm:.2f} BPM · compàs {int(bpb)} · "
                 f"des de {float(offset):.3f}s")

    def _canvia_vol_metro(self, v):
        """Volum del clic (0-100) — **sense tallar la reproducció**.

        Mateix motiu que `set_metro`: el fil ho llig a cada tros.
        """
        self.metro_vol = max(0.0, min(1.0, v / 100.0))

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
        self._omple_llista_tempo()
        self.temps.setText(self._fmt_timeline(self.pos))

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
        self.log(f"acord {idx} → {new_t:.3f}s")

    def _on_chord_end_moved(self, idx, new_t):
        self._undo_marca()
        self._sync_timeline_acords()
        self.log(f"final acord {idx} → {new_t:.3f}s")

    def _on_edit_started(self):
        """Inici del gest (mouse press sobre un clip): captura l'estat 'abans'.

        Model Audacity: PushState() explicit al punt de l'accio, en comptes
        de dependre de senyals de canvi (que poden no arribar)."""
        self._undo_marca()

    def _on_edit_command(self, operacio, kw):
        """Ordre d'edició vinguda del teclat del timeline → despatx únic."""
        return self.executa_edicio(operacio, **(kw or {}))

    def _on_edit_cancelled(self):
        """Fi d'un gest SENSE moviment (clic o micro-moviment).

        `dragStarted` ja havia obert una marca d'undo; ací es tanca sense
        apilar res (l'estat no ha canviat). Sense això la marca quedava penjada
        i la propera operació arrossegava un estat «abans» vell.
        """
        self._undo_commit()

    def _on_edit_finished(self):
        """Fi d'un drag/resize → tanca l'operació i desa el CSV.

        ⚠️ I **re-renderitza DES DEL MODEL** (diferit, i preservant la selecció):
        durant l'arrossegament els items es mouen només de manera
        **previsual**, i el resultat final pot no coincidir amb eixa previsió
        (acotament del destí, snap, normalització del veí). Sense aquest
        re-render la vista es quedava mentint: cas verificat pel fuzzer de
        `test_vista_segueix_model` (seed 9) — l'item 0 pintat a `(0.000, 0.000)`
        mentre el model ja deia `(0.000, 2.000)`.
        """
        self._sync_timeline_acords()
        self._sync_timeline_seccions()
        self._undo_commit()
        try:
            # `_desa_i_regenera` ja escriu els 4 CSV (acords, ABC i mapa de
            # tempo): no cal tornar a regenerar l'ABC ací (eren dos desats).
            self._desa_i_regenera()
            self._sincronitza_vista(preserva=True, difereix=True)
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
        self.log(f"loop A={a:.3f}s B={b:.3f}s")
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

    # ── Menú contextual d'un carril: DEFINICIÓ ÚNICA (regla d'or #11) ────────
    #
    # Les DUES superfícies (timeline i llistes) i les TRES pistes comparteixen
    # aquesta definició: mateix joc d'accions, mateix ordre i mateixa redacció.
    # Abans cada superfície tenia el seu menú escrit a mà i divergien (la llista
    # tenia «Fusionar…» i el timeline no; ③ anava pel seu compte). Afegir una
    # operació ACÍ la fa aparéixer a tot arreu, i `test_regla11_paritat` ho
    # comprova superfície per superfície.
    _ETQ_AFEGEIX = {"chord": "Afegeix acord aquí",
                    "section": "Afegeix secció aquí",
                    "tempo": "Afegeix un canvi aquí"}
    _ETQ_PARTEIX = {"chord": "Parteix l'acord…",
                    "section": "Parteix la secció…",
                    "tempo": "Parteix aquest tros aquí"}
    _ETQ_REANOMENA = {"chord": "Reanomena acord…",
                      "section": "Reanomena secció…",
                      "tempo": "Reanomena (BPM/compàs)…"}
    _PLURAL = {"chord": "acords", "section": "seccions", "tempo": "trams"}

    def _n_clips(self, kind):
        if kind == "chord":
            return len(self.acords)
        if kind == "section":
            return len(self.seccions)
        return len(self.tempo_trams or [])

    # ── DESPATX ÚNIC D'EDICIÓ ────────────────────────────────────────────────
    # Totes les superfícies (menú contextual, llistes, menú principal, teclat)
    # envien ACÍ la seua intenció. Cap superfície decideix per si mateixa com
    # s'edita un carril: així el carril ③ no pot quedar-se fora d'una operació
    # (regla d'or #11) i no hi ha dos camins que divergisquen.
    OPERACIONS_EDICIO = (
        "afegeix", "parteix", "parteix_meitat", "parteix_loop", "fusiona",
        "elimina",
        "reanomena", "duplica", "nudge", "copia", "retalla", "enganxa",
        "selecciona", "loop_seleccio", "quantitza", "compassos",
    )
    _KINDS_EDICIO = ("chord", "section", "tempo")

    def _elimina_un(self, kind, idx):
        """Elimina UN clip del carril indicat (nucli del despatx)."""
        if not self._index_valid(kind, idx):
            return False
        if kind == "chord":
            self._elimina_acord_index(idx)
        elif kind == "section":
            self._elimina_seccio_index(idx)
        else:
            return bool(self._elimina_tram(idx))
        return True

    def _hi_ha_lloc_duplicat(self, kind, keys):
        """True si la còpia SENCERA del clip/bloc cap després (sense créixer).

        Decisió 2026-10-19: si no cap, no es duplica res (abans el destí
        s'acotava i la còpia podia caure damunt de l'original o del veí).
        """
        idxs = sorted({int(i) for (k, i) in (keys or ()) if k == kind})
        idxs = [i for i in idxs if self._index_valid(kind, i)]
        if not idxs:
            return True
        if kind == "chord":
            a = float(self.acords[idxs[0]].ini)
            b = float(self.acords[idxs[-1]].fi)
        elif kind == "section":
            a = float(self.seccions[idxs[0]][0])
            b = float(self.seccions[idxs[-1]][1])
        elif kind == "tempo":
            tr = self.tempo_trams or []
            a = float(tr[idxs[0]][0])
            b = float(tr[idxs[-1]][1])
        else:
            return True
        return b + (b - a) <= self._durada_wav() + 1e-9

    def _avis_sense_lloc_duplicat(self):
        self.avis_editor(
            "Duplicar: no hi ha lloc després del clip o bloc seleccionat. "
            "La cançó no pot créixer; mou-lo o escurça'l abans de duplicar.")

    def _duplica_un(self, kind, idx):
        """Duplica UN clip del carril indicat (nucli del despatx)."""
        if not self._index_valid(kind, idx):
            return False
        if not self._hi_ha_lloc_duplicat(kind, [(kind, idx)]):
            self._avis_sense_lloc_duplicat()
            return False
        if kind == "chord":
            return bool(self._duplica_acord_index(idx))
        if kind == "section":
            return bool(self._duplica_seccio_index(idx))
        self.timeline.select_clip("tempo", idx)
        return bool(self._duplica_seleccio([("tempo", idx)]))

    def executa_edicio(self, operacio, kind=None, idx=None, **kw):
        """**Punt ÚNIC** de despatx de les edicions dels tres carrils.

        `operacio`: una de `OPERACIONS_EDICIO`.
        `kind`/`idx`: objectiu explícit (menú contextual); si no arriben, es
        resol la selecció del timeline (`seleccio_activa`).
        `kw`: paràmetres de l'operació (`t`, `amb`, `mode`, `direccio`…).

        Les superfícies NO han de duplicar el despatx per carril: criden ací i
        aquest mètode tria el nucli canònic (`_afegeix_a_la_posicio`,
        `parteix_*`, `fusiona_*`, `_elimina_*`, `_duplica_*`, `renomena_*`).
        """
        op = str(operacio or "").strip().lower()
        if op not in self.OPERACIONS_EDICIO:
            self.log(f"despatx: operació desconeguda «{operacio}»")
            return False

        kind = None if kind in (None, "", "active") else str(kind)
        if kind is not None and kind not in self._KINDS_EDICIO:
            self.log(f"despatx: carril desconegut «{kind}»")
            return False
        idx = -1 if idx is None else int(idx)

        # -- selecció (no necessita cap clip prèviament seleccionat) ----------
        if op == "selecciona":
            if kind is None or idx < 0:
                return False
            return bool(self.timeline.selecciona(
                kind, idx, kw.get("mode", "set")))

        if op == "loop_seleccio":
            return self.loop_a_la_seleccio(kind, idx)

        # -- nudge: la implementació viu al timeline (necessita el gest) ------
        if op == "nudge":
            if not hasattr(self, "timeline"):
                return False
            self.timeline.nudge(kw.get("direccio", 1),
                                bool(kw.get("estira", False)),
                                kw.get("pas"))
            return True

        # -- quantitza: abast + graelles (operació de model, no de clip) -----
        if op == "quantitza":
            return bool(self.quantitza(
                kw.get("abast", "tot"),
                kw.get("grid_acords", "compas1"),
                kw.get("grid_estructura", "compas4")))

        # -- porta-retalls: si l'objectiu explícit no és seleccionat, se
        #    selecciona ABANS de copiar/retallar (una sola regla per als 3) --
        if op in ("copia", "retalla"):
            if kind is not None and idx >= 0:
                if not self._index_valid(kind, idx):
                    return False
                if (kind, idx) not in self.timeline.selected_keys():
                    self.timeline.select_clip(kind, idx)
            if not self.timeline.selected_keys():
                return False
            if op == "copia":
                self.timeline.copy_selection()
            else:
                self.timeline.cut_selection()
            return True
        if op == "enganxa":
            if not self.timeline.has_clipboard():
                return False
            self.timeline.paste_at_cursor()
            return True

        # -- operacions amb objectiu explícit (menú contextual / menú) ------
        if kind is not None and idx < 0 and op in (
                "elimina", "duplica", "reanomena", "parteix_meitat", "fusiona"):
            ak, ai = self.seleccio_activa()
            if ak == kind:
                idx = ai

        # -- compassos: correcció métrica discreta del carril ③ (un sol desfer) --
        if op == "compassos":
            if kind not in (None, "tempo"):
                return False
            if idx < 0:
                ak, ai = self.seleccio_activa()
                if ak != "tempo":
                    return False
                idx = ai
            return bool(self.canvia_compassos_tram(
                idx, kw.get("delta_compassos", 0), kw.get("factor")))

        if op == "afegeix":
            if kind is None:
                return False
            t = float(kw.get("t", getattr(self, "pos", 0.0)))
            if kind == "tempo":
                # «Afegir» i «partir» a ③ són el mateix gest: tots dos amb snap.
                t = self._snap_ui(t)
            return bool(self._afegeix_a_la_posicio(kind, t))

        if op == "parteix":
            if kind is None:
                return False
            t = self._snap_ui(float(kw.get("t", getattr(self, "pos", 0.0))))
            if kind == "tempo":
                return bool(self._afegeix_tall(t))
            if idx < 0:
                i = self._idx_a_t(kind, t)
                if i is None:
                    return False
                idx = i
            if not self._index_valid(kind, idx):
                return False
            if kind == "chord":
                return bool(self._parteix_acord_dialog(idx, t=t))
            return bool(self._parteix_seccio_dialog(idx, t=t))

        if op == "parteix_meitat":
            if kind is None:
                kind, idx = self.seleccio_activa()
            if kind is None or idx < 0:
                return False
            return bool(self.parteix_per_la_meitat(kind, idx))

        if op == "parteix_loop":
            if kind is None or idx is None or idx < 0:
                kind, idx = self.seleccio_activa()
            if kind is None or idx < 0:
                return False
            return bool(self.parteix_a_loop(kind, idx))

        if op == "fusiona":
            if kind is None:
                kind, idx = self.seleccio_activa()
            if kind is None or idx < 0:
                return False
            amb = str(kw.get("amb", "seguent"))
            if kind == "tempo":
                return bool(self._fusiona_tram(idx, amb))
            if kind == "chord":
                return bool(self.fusiona_acord(idx, amb))
            return bool(self.fusiona_seccio(idx, amb))

        if op == "elimina":
            if kind is not None:
                return self._elimina_un(kind, idx) if idx >= 0 else False
            keys = self.clips_seleccionats()
            if not keys:
                return False
            if len(keys) > 1:
                self._elimina_seleccio(sorted(keys))
                return True
            k, i = next(iter(keys))
            return self._elimina_un(k, i)

        if op == "duplica":
            if kind is not None:
                return self._duplica_un(kind, idx) if idx >= 0 else False
            keys = self.clips_seleccionats()
            if not keys:
                return False
            if len(keys) > 1:
                return bool(self._duplica_seleccio(sorted(keys)))
            k, i = next(iter(keys))
            return self._duplica_un(k, i)

        if op == "reanomena":
            if kind is None:
                kind, idx = self.seleccio_activa()
            if kind is None:
                return False
            # ③ no té renom en bloc: sempre s'edita el tram actiu (mai les
            # seccions per error d'índex — bug reproduït el 19-10-2026).
            if kind == "tempo":
                if idx < 0:
                    return False
                return bool(self._on_tempo_edit(idx))
            n_sel = len({i for (k, i) in self.clips_seleccionats()
                         if k == kind})
            if n_sel >= 2:
                return bool(self.renomena_seleccio(kind=kind))
            if idx < 0:
                return False
            self._focus_editor(kind, idx)
            return True

        return False

    def _menu_contextual(self, kind, idx, t):
        """Construeix el menú contextual d'un carril (definició ÚNICA)."""
        n = self._n_clips(kind)
        te = 0 <= idx < n
        menu = QMenu(self)

        def act(clau, text, actiu=True):
            a = menu.addAction(text)
            a.setData(clau)
            a.setEnabled(actiu)
            return a

        act("afegeix", self._ETQ_AFEGEIX[kind])
        menu.addSeparator()
        # Duplicar un tram de tempo necessita lloc DESPRÉS (el mapa sempre acaba
        # a la WAV); eliminar-lo, que n'hi haja més d'un.
        act("duplica", "Duplica", te and (kind != "tempo" or idx + 1 < n))
        act("elimina", "Elimina", te and (kind != "tempo" or n > 1))
        menu.addSeparator()
        n_sel = len({i for (k, i) in self.timeline.selected_keys()
                     if k == kind})
        # ③ no té renom en bloc (el contingut és numèric i s'edita amb el
        # diàleg): amb diversos trams seleccionats, l'acció es desactiva en
        # comptes d'acabar renombrant les seccions (bug 19-10-2026).
        ren_bloc = (n_sel >= 2 and kind != "tempo")
        act("reanomena",
            (f"Reanomena {n_sel} {self._PLURAL[kind]}…" if ren_bloc
             else self._ETQ_REANOMENA[kind]),
            te or (n_sel >= 1 and kind != "tempo"))
        menu.addSeparator()
        act("parteix", self._ETQ_PARTEIX[kind], te)
        act("meitat", "Partir per la meitat", te)
        # Partir a la selecció A–B (2026-10-20): «parteix aquí» als DOS
        # llocs alhora — cada frontera del loop que caiga dins del clip hi
        # deixa un tall (2 o 3 trossos amb el mateix nom).
        loop = self._loop_vals()
        act("parteix_loop",
            ("Parteix a la selecció A–B" if loop is None else
             f"Parteix a la selecció A–B ({loop[0]:.2f}–{loop[1]:.2f}s)"),
            te and loop is not None)
        menu.addSeparator()
        # «Fusionar» = traure una frontera (a ③, fondre el tram amb el veí).
        # Era l'única operació que només existia a les llistes.
        act("fusiona_anterior", "Fusionar amb anterior", te and idx > 0)
        act("fusiona_seguent", "Fusionar amb següent", te and idx + 1 < n)
        if kind == "tempo":
            # Correcció MÈTRICA discreta (§4.C del flux de tempo variable):
            # els segons queden quiets, el N canvia i el BPM s'adapta.
            menu.addSeparator()
            act("compas_mes1", "Afegir 1 compàs (+1)", te)
            act("compas_menys1", "Restar 1 compàs (−1)", te)
            act("compas_x2", "Doblar compassos (×2)", te)
            act("compas_div2", "Dividir compassos (÷2)", te)
        menu.addSeparator()
        act("retalla", "Retalla", te)
        act("copia", "Copia", te)
        act("enganxa", "Enganxa", self.timeline.has_clipboard())
        menu.addSeparator()
        act("loop_seleccio", "Loop a la selecció",
            bool(self.clips_seleccionats()) or te)
        return menu

    def _executa_contextual(self, kind, idx, t, clau, superficie="timeline"):
        """Executa una acció del menú contextual (definició única).

        La superfície NO decideix res per carril: tradueix la clau del menú a
        una operació del despatx únic i li passa l'objectiu. `superficie`
        ("timeline" o "llista") es conserva per compatibilitat; el despatx ja
        no necessita saber d'on ve l'ordre.
        """
        if clau is None:
            return False
        mapa = {
            "afegeix": ("afegeix", {"t": float(t)}),
            "duplica": ("duplica", {}),
            "elimina": ("elimina", {}),
            "reanomena": ("reanomena", {}),
            "parteix": ("parteix", {"t": float(t)}),
            "meitat": ("parteix_meitat", {}),
            "parteix_loop": ("parteix_loop", {}),
            "fusiona_anterior": ("fusiona", {"amb": "anterior"}),
            "fusiona_seguent": ("fusiona", {"amb": "seguent"}),
            "compas_mes1": ("compassos", {"delta_compassos": 1}),
            "compas_menys1": ("compassos", {"delta_compassos": -1}),
            "compas_x2": ("compassos", {"factor": 2.0}),
            "compas_div2": ("compassos", {"factor": 0.5}),
            "retalla": ("retalla", {}),
            "copia": ("copia", {}),
            "enganxa": ("enganxa", {}),
            "loop_seleccio": ("loop_seleccio", {}),
        }
        desti = mapa.get(clau)
        if desti is None:
            self.log(f"menú contextual: acció desconeguda «{clau}»")
            return False
        operacio, kw = desti
        return self.executa_edicio(operacio, kind, idx, **kw)

    def _afegeix_tall(self, t):
        """Obre una frontera nova al mapa de tempo (l'«afegeix» de ③).

        El tall s'imanta a la línia de compàs del tram que el conté i ha de
        deixar compassos enters a les dues bandes (`REGLES_DE_LA_APP.md` §13.4).
        Retorna `True` NOMÉS si el mapa ha guanyat un tram.
        """
        trams = list(self.tempo_trams or [])
        if any(abs(float(s[0]) - float(t)) <= 1e-6 for s in trams):
            self.avis_editor("Afegeix tempo: ja hi ha una frontera en eixe punt")
            return False
        idx = None
        for i, s in enumerate(trams):
            if float(s[0]) - 1e-9 <= float(t) <= float(s[1]) + 1e-9:
                idx = i
                break
        if idx is None:
            self.avis_editor("Afegeix tempo: el punt no cau dins cap tram")
            return False
        abans = len(trams)
        try:
            _tall, nous = tempo_map.parteix_a_compas(
                trams, idx, float(t), self._durada_wav(),
                offset=getattr(self, "offset", 0.0))
        except ValueError as e:
            self.avis_editor(f"Afegeix tempo: {e}")
            return False
        self._undo_marca()
        self.aplica_tempo_trams(nous)
        self._undo_commit()
        return len(self.tempo_trams or []) > abans

    # ---------------- MARCADORS (inici de compàs, en viu) ----------------
    def _marcador_a(self, t, tol=0.05):
        """Índex del marcador humà que coincideix amb `t` (o `None`).

        Els marcadors es creen amb `+` i els seus ancestres són les fronteres
        de tempo; 0,05 s és prou per a emparellar-los sense confondre dos
        marcadors distints (entre ells sempre hi ha ≥ `SEPARACIO_MIN`).
        """
        t = float(t)
        for i, m in enumerate(self.marcadors or ()):
            if abs(float(m) - t) <= float(tol):
                return i
        return None

    def _mou_marcador(self, t_vell, t_nou):
        """Mou el marcador ancorat a una frontera que s'ha mogut (§4.C).

        Va DINS de l'operació de desfer del gest: el marcador, la frontera
        d'**estructura** que va crear i el mapa es desfan junts. Retorna `True`
        si n'hi havia cap.
        """
        from app import marcadors as M
        i = self._marcador_a(t_vell)
        if i is None:
            return False
        marques = [float(x) for x in (self.marcadors or ())]
        marques[i] = float(t_nou)
        nou = M.normalitza_marcadors(marques, self._durada_wav())
        if nou == list(self.marcadors or ()):
            return False
        self.marcadors = nou
        self._pinta_marcadors()
        self._mou_seccio_amb_marcador(t_vell, t_nou)
        try:
            pipeline.desa_marcadors(self._carpeta_acords(), self.marcadors)
        except OSError as e:
            self.log(f"marcadors: no s'han pogut desar ({e})")
        self.log(f"marcador mogut amb la frontera: {t_vell:.3f} → {t_nou:.3f}s")
        return True

    def _mou_seccio_amb_marcador(self, t_vell, t_nou):
        """Mou la frontera d'**estructura** que coincidia amb el marcador.

        El `+` crea alhora un inici de clip de BPM/compàs **i** d'estructura:
        si després es mou la frontera de tempo (i el marcador viatja amb ella,
        §4.C), el clip de secció també ha de seguir el marcador que el va
        crear. El vincle es resol per **coincidència de temps** (5 ms), sense
        desar cap identificador nou al projecte.

        Mou només les **dues** seccions que toquen la frontera (la de
        l'esquerra estira la fi i la de la dreta mou l'inici) i respecta
        `MIN_SECCIO_S`; si no hi cap, no toca res i ho deixa al registre.
        """
        seccions = list(self.seccions or [])
        if len(seccions) < 2:
            return False
        idx = next((j for j in range(1, len(seccions))
                    if abs(float(seccions[j][0]) - float(t_vell)) <= 0.005),
                   None)
        if idx is None:
            return False
        nou = float(t_nou)
        ini_a = float(seccions[idx - 1][0])
        fi_b = float(seccions[idx][1])
        if not (ini_a + self.MIN_SECCIO_S <= nou <= fi_b - self.MIN_SECCIO_S):
            self.log(f"marcador: la secció no pot seguir-lo ({nou:.3f}s)")
            return False
        nova = list(seccions)
        nova[idx - 1] = (ini_a, nou) + tuple(seccions[idx - 1][2:])
        nova[idx] = (nou, fi_b) + tuple(seccions[idx][2:])
        self.seccions = self._normalitza_seccions(nova)
        # El gest acaba al `release` del carril de tempo: NO podem re-sincronitzar
        # model←timeline (tornaria les seccions velles). Passem les dades noves
        # al timeline (sense reconstruir items ací mateix, que seria insegur
        # dins de l'esdeveniment) i deixem el re-render al cicle següent.
        tl = getattr(self, "timeline", None)
        if tl is not None:
            tl._seccions = [tuple(s) for s in self.seccions]
        self._actualitza_llista_abc()
        self._sincronitza_vista(preserva=True, difereix=True)
        self.log(f"estructura moguda amb el marcador: {t_vell:.3f} → "
                 f"{nou:.3f}s")
        return True

    def _esborra_marcador_a(self, t, tol=0.05):
        """Esborra el marcador d'una frontera que ha desaparegut (§4.C)."""
        from app import marcadors as M
        i = self._marcador_a(t, tol)
        if i is None:
            return False
        self.marcadors = M.elimina(list(self.marcadors or ()), i)
        self._pinta_marcadors()
        try:
            pipeline.desa_marcadors(self._carpeta_acords(), self.marcadors)
        except OSError as e:
            self.log(f"marcadors: no s'han pogut desar ({e})")
        self.log(f"marcador esborrat amb la frontera de {float(t):.3f}s")
        return True

    def afegeix_marcador(self, t=None):
        """Marca l'instant actual (o `t`) com a **inici de compàs**.

        Crea, en eixe punt, un **inici de clip al carril de BPM/compàs i al
        d'estructura**. El marcador queda **lligat a la frontera de tempo**
        (la segueix si s'arrossega i s'esborra amb ella, §4.C del flux de tempo
        variable) i el **clip d'estructura** que naix ací el seguix també
        (`_mou_seccio_amb_marcador`, vincle per coincidència de temps: si
        després s'edita la secció a mà i deixa de coincidir, deixa de seguir-lo).
        Es pot cridar mentre sona (tecla `+`). Un sol desfer ho desfà tot.

        El tram que es tanca **naix ja amb compassos enters i BPM derivat**
        (`tempo_map.parteix_tram_marcador`): si es conservara el BPM cec, el
        tram quedaria amb fraccions de compàs i bloquejaria qualsevol
        validació posterior (el bug que aturava el flux de tempo variable).
        """
        from app import marcadors as M
        durada = self._durada_wav()
        t = float(self.pos if t is None else t)
        if not (0.0 < t < durada - 1e-3):
            return False
        abans = list(self.marcadors or [])
        marques = M.afegeix(abans, t, durada)
        if marques == abans:
            return False
        trams = list(self.tempo_trams or [(0.0, durada, self.bpm, self.bpb,
                                           getattr(self, "beat_type", 4))])
        try:
            bpm_ref = float(self.tempo_map.bpm(t))
        except (AttributeError, TypeError, ValueError):
            bpm_ref = float(self.bpm)
        try:
            trams = tempo_map.parteix_tram_marcador(
                trams, t, durada, offset=getattr(self, "offset", 0.0),
                bpm_ref=bpm_ref)
        except ValueError as e:
            self.avis_editor(f"Marcador: {e}")
            return False
        trams = self._normalitza_mapa_viu(trams, "Marcador")
        seccions = list(self.seccions or [])
        idx = next((i for i, s in enumerate(seccions)
                    if float(s[0]) + 1e-6 < t < float(s[1]) - 1e-6), None)
        if idx is not None:
            try:
                seccions = pipeline.parteix_seccio(
                    seccions, idx, t, marge=self.MIN_SECCIO_S)
            except ValueError as e:
                self.log(f"marcador: no s'ha pogut partir l'estructura ({e})")
                seccions = list(self.seccions or [])
        self._undo_marca()
        self.marcadors = marques
        if [tuple(x) for x in trams] != [tuple(x) for x in
                                         (self.tempo_trams or [])]:
            self.aplica_tempo_trams(trams)
        if seccions != list(self.seccions or []):
            self.seccions = self._normalitza_seccions(seccions)
        self._undo_commit()
        self._pinta_marcadors()
        self._sincronitza_vista()
        try:
            pipeline.desa_marcadors(self._carpeta_acords(), self.marcadors)
        except OSError as e:
            self.log(f"marcadors: no s'han pogut desar ({e})")
        self.log(f"marcador a {t:.3f}s (n'hi ha {len(self.marcadors)})")
        return True

    def candidats_bpm_marcadors(self, preferit=None, num=None, den=None,
                                bpm_min=60.0, bpm_max=180.0):
        """BPMs compatibles amb els marcadors (tots els talls enters).

        `preferit` = BPM de la barra: servix per a ordenar els candidats (no
        decidix res: l'ambigüitat doble/meitat la resol l'operador).
        """
        from app import marcadors as M
        num = int(num or self.bpb)
        den = int(den or getattr(self, "beat_type", 4))
        return M.candidats_bpm(
            list(self.marcadors or ()), num, den, bpm_min, bpm_max,
            preferit=float(preferit if preferit else self.bpm))

    def aplica_bpm_marcadors(self, candidat, num=None, den=None):
        """Reescriu el mapa amb el BPM deduït dels marcadors (1 sol desfer).

        Cada interval entre marcadors passa a tindre **exactament `k`
        compassos** al BPM del propi interval: així totes les fronteres cauen
        en línia de compàs i els clips de tempo/compàs tornen a ser editables.
        El «cap» (abans del 1r marcador) va amb el primer BPM i l'offset passa a
        ser el primer marcador.
        """
        from app import marcadors as M
        ms = M.normalitza_marcadors(list(self.marcadors or ()),
                                    self._durada_wav())
        if len(ms) < 2:
            self.avis_editor("Calen almenys dos marcadors per a traure el BPM")
            return False
        num = int(num or self.bpb)
        den = int(den or getattr(self, "beat_type", 4))
        durada = self._durada_wav()
        inter = list(candidat.get("intervals") or ())
        if len(inter) != len(ms) - 1:
            self.log("BPM marcadors: els intervals no quadren amb els marcadors")
            return False
        trams = [(0.0, float(ms[0]), float(inter[0][2]), num, den)]
        ini = float(ms[0])
        for dt, _k, bpm_i in inter:
            fi = ini + float(dt)
            trams.append((ini, fi, float(bpm_i), num, den))
            ini = fi
        trams.append((ini, durada, float(inter[-1][2]), num, den))
        self._undo_marca()
        try:
            self.offset = float(ms[0])
            if not self.aplica_tempo_trams(trams):
                self.log("BPM marcadors: el mapa no s'ha pogut aplicar")
                return False
        finally:
            self._undo_commit()
        self.bpm = float(candidat.get("bpm") or self.bpm)
        self.bpb = num
        self.beat_type = den
        self._actualitza_temps()
        self._sincronitza_vista()
        self._desa_i_regenera()
        self.log(f"BPM dels marcadors: {self.bpm:.2f} (residu "
                 f"{float(candidat.get('residu') or 0):.4f}) · "
                 f"{len(trams)} trams · {len(ms)} marcadors")
        return True

    def retempo_tram_detectat(self, idx, bpm_detectat):
        """«Detecta» sobre un tram seleccionat: BPM nou **sense ripple**.

        Les fronteres del clip (i les dels veïns) **no es mouen**: el BPM
        detectat només decidix el nombre enter de compassos que hi caben i
        s'aplica el BPM exacte que els clava a la durada existent
        (`tempo_map.retempo_tram_detectat`). Així el següent marcador no es
        desquadra. Un sol desfer. Retorna `True` si el mapa ha canviat.
        """
        trams = list(self.tempo_trams or [])
        idx = int(idx)
        if not (0 <= idx < len(trams)):
            return False
        try:
            nous = tempo_map.retempo_tram_detectat(
                trams, idx, float(bpm_detectat), self._durada_wav(),
                offset=getattr(self, "offset", 0.0))
        except ValueError as e:
            self.avis_editor(f"Detecta BPM: {e}")
            return False
        if [tuple(x) for x in nous] == [tuple(x) for x in trams]:
            return False
        self._undo_marca()
        ok = self.aplica_tempo_trams(nous)
        self._undo_commit()
        if ok:
            self.log(f"BPM del tram {idx} detectat: {float(bpm_detectat):.3f} "
                     f"→ {float(self.tempo_trams[idx][2]):.3f} BPM "
                     f"({self._compassos_de(idx):g} compassos, sense moure "
                     "les fronteres)")
        return bool(ok)

    def ajusta_bpms_marcadors(self):
        """Ajusta **tot** el mapa a partir dels marcadors, en un sol desfer.

        Acció per lot: cada interval entre marcadors passa a tindre compassos
        enters amb el BPM derivat; el BPM vigent del mapa al centre de cada
        interval és la referència (l'àudio detectat, si l'operador l'ha aplicat
        abans, ja és al mapa). El «cap» i la «cua» queden com a excepcions i
        l'offset passa a ser el primer marcador (és un inici de compàs).
        Retorna `True` si el mapa ha canviat.
        """
        from app import marcadors as M
        durada = self._durada_wav()
        ms = M.normalitza_marcadors(list(self.marcadors or ()), durada)
        if len(ms) < 2:
            self.avis_editor(
                "Calen almenys dos marcadors per a ajustar els BPMs")
            return False
        referencies = []
        for a, b in zip(ms, ms[1:]):
            try:
                referencies.append(float(self.tempo_map.bpm((a + b) / 2.0)))
            except (AttributeError, TypeError, ValueError):
                referencies.append(float(self.bpm))
        try:
            nous = tempo_map.ajusta_trams_a_marcadors(
                list(self.tempo_trams or []), ms, durada,
                referencies=referencies)
        except ValueError as e:
            self.avis_editor(f"Ajusta BPMs: {e}")
            return False
        abans = [tuple(x) for x in (self.tempo_trams or [])]
        if [tuple(x) for x in nous] == abans and \
                abs(float(getattr(self, "offset", 0.0)) - float(ms[0])) < 1e-9:
            return False
        self._undo_marca()
        self.offset = float(ms[0])
        ok = self.aplica_tempo_trams(nous)
        self._undo_commit()
        if ok:
            self._sincronitza_vista()
            self.log(f"BPMs ajustats pels {len(ms)} marcadors: "
                     f"{len(nous)} trams · compàs 1 a {ms[0]:.3f}s")
        return bool(ok)

    def elimina_marcador(self, idx=None):
        """Esborra un marcador (per defecte, l'últim). Els clips NO es toquen."""
        from app import marcadors as M
        if not self.marcadors:
            return False
        idx = (len(self.marcadors) - 1) if idx is None else int(idx)
        abans = list(self.marcadors)
        marques = M.elimina(abans, idx)
        if marques == abans:
            return False
        self._undo_marca()
        self.marcadors = marques
        self._undo_commit()
        self._pinta_marcadors()
        try:
            pipeline.desa_marcadors(self._carpeta_acords(), self.marcadors)
        except OSError:
            pass
        self.log(f"marcador esborrat (en queden {len(self.marcadors)})")
        return True

    def _pinta_marcadors(self):
        tl = getattr(self, "timeline", None)
        if tl is not None and hasattr(tl, "set_marcadors"):
            tl.set_marcadors(list(self.marcadors or []))

    def aplica_ancoratges(self, trams, offset, seccions=None,
                          msg="Anàlisi guiat (ancoratges)"):
        """Aplica **offset + mapa de tempo + estructura** en UN sol desfer.

        Punt d'entrada de l'Anàlisi guiat v3 (`docs/ANALISI_GUIAT_v3.md`). La
        GUI no toca mai el model directament: valida el contracte de compassos
        enters (`tempo_map`) i la cobertura d'estructura (`pipeline`) ABANS de
        mutar res; si alguna cosa no quadra, no es toca ni el mapa ni l'offset.
        """
        durada = self._durada_wav()
        try:
            nous = tempo_map.valida_i_normalitza_compassos(
                trams, durada, offset=float(offset))
            sec = None
            if seccions is not None:
                sec = pipeline.valida_canvis_seccions(
                    pipeline.clips_de_seccions(seccions), durada)
                sec = pipeline.seccions_de_clips(sec)
        except ValueError as e:
            self.avis_editor(f"{msg}: {e}")
            return False
        self._undo_marca()
        self.offset = float(offset)
        self.aplica_tempo_trams(nous)
        if sec is not None:
            self.seccions = sec
        self._undo_commit()
        self._sincronitza_vista()
        if sec is not None:
            try:
                self._regenera_abc_des_de_totes_les_seccions(msg)
            except Exception as e:  # noqa: BLE001
                self.log(f"ERROR regenerant l'ABC: {e}")
        self.log(f"{msg}: offset {float(offset):.3f}s · {len(nous)} trams · "
                 f"{len(sec) if sec else len(self.seccions)} seccions")
        return True

    def _aplica_mapa_reparat(self, nous, msg):
        """Aplica un mapa i, si les fronteres hereten mil·lèsimes fora de
        graella, les imanta abans de rebutjar (bug 21-10: eliminar/fusionar/
        duplicar un tram fallava després de l'Anàlisi guiat)."""
        durada = self._durada_wav()
        offset = getattr(self, "offset", 0.0)
        try:
            fi = tempo_map.valida_i_normalitza_compassos(nous, durada, offset)
        except ValueError as e:
            try:
                fi = tempo_map.repara_fronteres(nous, durada, offset)
            except ValueError:
                self.avis_editor(f"{msg}: {e}")
                return False
            self.log(f"{msg}: fronteres imantades a la línia de compàs")
        return bool(self.aplica_tempo_trams(fi))

    def _elimina_tram(self, idx):
        """Elimina un tram del mapa (els veïns n'ocupen l'espai)."""
        trams = list(self.tempo_trams or [])
        if not (0 <= idx < len(trams)) or len(trams) <= 1:
            return False
        self._undo_marca()
        ok = self._aplica_mapa_reparat(
            tempo_map.elimina_tall(trams, idx), "Elimina tempo")
        if ok:
            # §4.C: la frontera desapareix → el marcador que hi ancorava, també.
            self._esborra_marcador_a(float(trams[idx][0]))
        self._undo_commit()
        return ok

    def _fusiona_tram(self, idx, amb="seguent"):
        """Fusiona el tram `idx` amb el veí (mirall de `fusiona_acord`, #11)."""
        trams = list(self.tempo_trams or [])
        nou = tempo_map.fusiona_trams(trams, idx, amb)
        if len(nou) == len(trams):
            return False
        # La frontera que desapareix depén de amb qui es fusiona.
        frontera = float(trams[idx][0]) if str(amb) == "anterior" \
            else float(trams[idx][1])
        self._undo_marca()
        ok = self._aplica_mapa_reparat(nou, "Fusiona tempo")
        if ok:
            self._esborra_marcador_a(frontera)
        self._undo_commit()
        return ok

    def _on_clip_context_menu(self, kind, idx, pos, t=None):
        """Botó dret sobre un clip del TIMELINE (definició única del menú).

        `t` = instant on s'ha clicat (per al «Afegeix … aquí»). Si no arriba
        (crides directes), s'usa el cursor, com fan els menús de les llistes.
        """
        if t is None:
            t = float(self.pos)
        idx = -1 if idx is None else int(idx)
        menu = self._menu_contextual(kind, idx, t)
        accio = menu.exec_(pos)
        self._executa_contextual(kind, idx, t,
                                 accio.data() if accio else None, "timeline")

    def _menu_de_llista(self, kind, llista, pos):
        """Botó dret a la LLISTA d'un carril: EL MATEIX menú que el timeline.

        L'«aquí» és el cursor (`self.pos`), com feien aquests menús abans.
        """
        if llista is None:
            return
        idx = llista.indexAt(pos).row()
        menu = self._menu_contextual(kind, idx, float(self.pos))
        accio = menu.exec_(llista.mapToGlobal(pos))
        self._executa_contextual(kind, idx, float(self.pos),
                                 accio.data() if accio else None, "llista")

    def _afegeix_a_la_posicio(self, kind, t):
        """«Afegeix acord/secció aquí» — **un sol camí** per a la LLISTA i el TIMELINE.

        En un model **saturat** (els clips cobreixen tota la WAV, regla d'or #4)
        «afegir» no pot ser inserir un tros nou: vol dir **obrir un clip nou**
        en aquell instant.
          - **acord**: una MARCA nova a `t` (el clip anterior s'hi acaba).
          - **secció**: **partir** la secció que conté `t`; la meitat dreta rep
            la lletra/família triades (`parteix_seccio` ja ho fa així).

        ⚠️ Bug arreglat (19-10-2026): la versió anterior deia «secció nova de
        2 s» i `_valida_canvis_seccions` la rebutjava SEMPRE per solapament →
        «Afegeix secció aquí» petava sempre (llista i timeline).

        Una sola operació de desfer (per al chord; `parteix_seccio` ja la fa).
        """
        t = float(t)
        if kind == "tempo":
            # A ③ «afegir» és OBRIR UN TALL (regla #11: a la pista de tempo
            # «afegir» i «partir» són el mateix gest).
            return self._afegeix_tall(t)
        if kind == "chord":
            nou, ok = QInputDialog.getText(
                self, "Afegeix acord", f"Acord a {t:.3f} s", text="N")
            if not ok:
                return False
            self._undo_marca()
            fet = False
            try:
                # (`_afegeix_acord` ja refresca la vista: la sincronització viu
                # a la primitiva perquè cap camí se n'oblide.)
                fet = bool(self._afegeix_acord(t, nou))
                if fet:
                    self._desa_i_regenera()
                    self.log(f"afegit acord a {t:.3f}s: {nou}")
                else:
                    self.log(f"afegir acord a {t:.3f}s: nom no vàlid")
            except Exception as e:  # noqa: BLE001
                self.log(f"ERROR: {e}")
                QMessageBox.warning(self, "Visor",
                                    f"No s'ha pogut afegir l'acord:\n{e}")
            self._undo_commit()
            return fet
        lletra, ok1 = QInputDialog.getText(
            self, "Afegeix secció", "Etiqueta de la secció", text="A")
        if not ok1:
            return False
        fam, ok2 = QInputDialog.getText(
            self, "Afegeix secció", "Família", text=lletra.strip() or "A")
        if not ok2:
            return False
        idx = self._seccio_a_t(t)
        if idx < 0:
            # Model NO saturat (p. ex. estructura buida): no hi ha cap secció
            # per partir. Es crea un tros de 2 s, com feia el menú principal.
            # (El despatx únic ha d'unificar els DOS camins, no triar-ne un.)
            self._undo_marca()
            try:
                self._afegeix_seccio(t, t + 2.0, lletra, fam)
                self._regenera_abc_des_de_totes_les_seccions(
                    f"secció nova a {t:.3f}s")
                self.log(f"afegida secció a {t:.3f}s")
                return True
            except Exception as e:  # noqa: BLE001
                self.log(f"afegir secció a {t:.3f}s: {e}")
                QMessageBox.warning(
                    self, "Visor", f"No s'ha pogut afegir la secció:\n{e}")
                return False
            finally:
                self._undo_commit()
        if not self.parteix_seccio(idx, t, lletra, fam):
            self.log(f"afegir secció a {t:.3f}s: punt no vàlid "
                     f"(fora de cap secció o massa a prop d'una vora)")
            QMessageBox.warning(
                self, "Visor",
                "No s'ha pogut afegir la secció: el punt ha de caure DINS "
                "d'una secció i no pot quedar a tocar d'una vora.")
            return False
        self._regenera_abc_des_de_totes_les_seccions(
            f"secció afegida a {t:.3f}s")
        return True

    def _idx_a_t(self, kind, t):
        """Índex del clip de `kind` que conté (o arrenca abans de) `t`.

        Punt únic per als tres carrils; el fan servir el despatx i els menús
        (abans `main.py` tenia tres còpies amb criteris lleugerament distints).
        Retorna `None` si no n'hi ha cap.
        """
        t = float(t)
        if kind == "chord":
            idx = -1
            for i, a in enumerate(self.acords):
                if float(a[0]) <= t:
                    idx = i
                else:
                    break
            return idx if idx >= 0 else None
        if kind == "section":
            for i, s in enumerate(self.seccions):
                if float(s[0]) - 1e-9 <= t < float(s[1]) - 1e-9:
                    return i
            return None
        if kind == "tempo":
            idx = -1
            for i, tr in enumerate(self.tempo_trams or []):
                if float(tr[0]) <= t:
                    idx = i
                else:
                    break
            return idx if idx >= 0 else None
        return None

    def _snap_ui(self, t):
        """Aplica el snap vigent a un temps que ve d'un clic o del cursor.

        Si el snap està apagat, `TimelineView._snap()` retorna el mateix temps.
        És el punt únic perquè els talls i els canvis de tempo des de la GUI
        respecten la graella sense duplicar la lògica.
        """
        if hasattr(self, "timeline") and hasattr(self.timeline, "_snap"):
            return float(self.timeline._snap(float(t)))
        return float(t)

    def _punt_de_tall(self, t, ini, fi, minim, nom):
        """Tria on tallar: primer `t` (clic), després el cursor; tots amb snap.

        Retorna el punt vàlid o `None`. Un punt és vàlid si deixa marge a les
        dues vores (les dues meitats han de tindre sentit).
        """
        def _valid(x):
            return ini + minim <= x <= fi - minim

        candidats = []
        if t is not None:
            candidats.append(float(t))
        candidats.append(float(getattr(self, "pos", 0.0)))
        vist = set()
        for c in candidats:
            cs = self._snap_ui(c)
            clau = round(cs, 9)
            if clau in vist:
                continue
            vist.add(clau)
            if _valid(cs):
                return cs
        self.log(f"partir: ni el clic ni el cursor no cauen dins «{nom}» "
                 f"({ini:.3f}s–{fi:.3f}s) amb marge suficient")
        return None

    def _seccio_a_t(self, t):
        """Índex de la secció que conté l'instant `t` (-1 si no n'hi ha cap)."""
        t = float(t)
        for i, (ini, fi, _L, _F) in enumerate(self.seccions or []):
            if float(ini) - 1e-9 <= t <= float(fi) + 1e-9:
                return i
        return -1

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
        keys = self.timeline.keys_dins_rang(float(a), float(b),
                                            inclou_fi=False, tempo=True)
        if not keys:
            self.log("loop: no hi ha cap clip dins del loop")
            return 0
        self.timeline.select_multi(keys)
        self.ves_a(float(b))          # cursor al FINAL del loop
        self.log(f"loop {float(a):.3f}–{float(b):.3f}s: {len(keys)} clip(s) "
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
            self.executa_edicio("copia" if accio == a_cop else "retalla")
            # copy/cut mouen el cursor al final del BLOC; el volem al final del
            # LOOP, perquè «Enganxa» hi caigui just després.
            self.ves_a(float(self.loop_b))
        elif accio == a_eng:
            self.executa_edicio("enganxa")

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
        self._sincronitza_vista()      # punt únic MODEL -> VISTA
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
        """Duplica l'acord `idx` DESPRÉS d'ell, conservant-ne la durada.

        La còpia **sobreescriu** el tram que ocupa (§6.3/#11). Si no hi ha lloc
        per a la còpia sencera després del clip, no es fa res i s'avisa (la
        cançó no pot créixer).
        """
        if idx < 0 or idx >= len(self.acords):
            return False
        if not self._hi_ha_lloc_duplicat("chord", [("chord", idx)]):
            self._avis_sense_lloc_duplicat()
            return False
        cand = pipeline.duplica_bloc_clips(
            self.acords, idx, idx, float(self.acords[idx].fi),
            self._durada_wav(), pipeline.FORAT_ACORD)
        if cand == list(self.acords):
            self.log(f"no es pot duplicar l'acord {idx}: no hi ha lloc")
            return False
        return bool(self._aplica_carril(
            "chord", lambda _L: cand,
            f"duplicat acord {idx} (després, sobreescrivint)"))

    def _duplica_seccio_index(self, idx):
        """Duplica la secció `idx` DESPRÉS d'ella, conservant-ne la durada.

        Mateixa regla que els acords (#11): si no cap sencera després, no es fa
        res i s'avisa.
        """
        if idx < 0 or idx >= len(self.seccions):
            return False
        if not self._hi_ha_lloc_duplicat("section", [("section", idx)]):
            self._avis_sense_lloc_duplicat()
            return False
        cand = pipeline.duplica_bloc_seccions(
            self.seccions, idx, idx, float(self.seccions[idx][1]),
            self._durada_wav())
        if cand == list(self.seccions):
            self.log(f"no es pot duplicar la secció {idx}: no hi ha lloc")
            return False
        return bool(self._aplica_carril(
            "section", lambda _L: cand,
            f"secció {idx} duplicada (després, sobreescrivint)"))

    def _duplica_seleccio(self, keys):
        """Duplica tots els clips de la multi-selecció en una sola operació.

        La còpia del bloc va DESPRÉS i **sobreescriu** el tram que ocupa (§2,
        §6.3/#11). Es calcula sobre còpies candidates i es valida ABANS de tocar
        el model."""
        keys = list(keys or [])
        idx_ac = sorted({int(i) for k, i in keys if k == "chord"}, reverse=True)
        idx_sec = sorted({int(i) for k, i in keys if k == "section"}, reverse=True)
        tr_tot = self.timeline._trams_tempo()
        idx_tp = sorted({int(i) for k, i in keys if k == "tempo"})
        idx_ac = [i for i in idx_ac if 0 <= i < len(self.acords)]
        idx_sec = [i for i in idx_sec if 0 <= i < len(self.seccions)]
        idx_tp = [i for i in idx_tp if 0 <= i < len(tr_tot)]
        if not idx_ac and not idx_sec and not idx_tp:
            return False
        # Decisió 2026-10-19: la còpia sencera ha de cabre DESPRÉS del bloc.
        # Si un dels carrils no hi cap, no es duplica res (una sola operació).
        for kind in ("chord", "section", "tempo"):
            if not self._hi_ha_lloc_duplicat(kind, keys):
                self._avis_sense_lloc_duplicat()
                return False
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
        cand_tp = None
        if idx_tp:
            first, last = min(idx_tp), max(idx_tp)
            ini0, fi0 = float(tr_tot[first][0]), float(tr_tot[last][1])
            bloc = [(float(t[0]) - ini0, float(t[1]) - ini0,
                     t[2], t[3], t[4]) for t in tr_tot[first:last + 1]]
            # §2: la còpia va DESPRÉS del bloc i n'hereta el BPM/compàs.
            cand_tp = tempo_map.normalitza_trams(
                self._bloc_sobre_trams(self.tempo_trams, bloc, fi0 - ini0,
                                       fi0, durada), durada)
        try:
            cand_ac = self._valida_canvis_acords(cand_ac)
            if idx_sec:
                cand_sec = self._valida_canvis_seccions(cand_sec)
            if cand_tp is not None:
                # Les fronteres heretades poden quedar a unes mil·lèsimes de
                # la línia de compàs: s'imanten abans de rebutjar (21-10).
                cand_tp = tempo_map.repara_fronteres(
                    cand_tp, durada, offset=getattr(self, "offset", 0.0))
        except ValueError as e:
            self.log(f"duplica selecció: canvi invalid, no s'ha fet res ({e})")
            self.avis_editor(f"Duplica: {e}")
            return False
        self._undo_marca()
        self.acords = cand_ac
        if idx_sec:
            self.seccions = cand_sec
        if cand_tp:
            self.aplica_tempo_trams(cand_tp)
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
            return False
        return True

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
        idx_tp = [i for i in idx_tp if 0 <= i < len(self.tempo_trams or [])]
        if not idx_ac and not idx_sec and not idx_tp:
            return
        durada = self._durada_wav()
        cand_tp = None
        if idx_tp:
            trams = list(self.tempo_trams or [])
            for i in idx_tp:
                trams = tempo_map.elimina_tall(trams, i)
            try:
                # Les fronteres heretades poden quedar a mil·lèsimes de la
                # graella: s'imanten abans de rebutjar (21-10).
                cand_tp = tempo_map.repara_fronteres(
                    trams, durada, offset=getattr(self, "offset", 0.0))
            except ValueError as e:
                self.avis_editor(f"Elimina tempo: {e}")
                return
        self._undo_marca()
        for i in idx_ac:
            self._elimina_acord(i)
        for i in idx_sec:
            self._elimina_seccio(i)
        if cand_tp:
            self.aplica_tempo_trams(cand_tp)
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
          `Alt` (Ctrl+Alt+V) se salta el snap, com el «hold N» del Final Cut.
        El bloc viatja **rígid** (com `Grid Relative` del Cubase): no s'arrodoneix
        cada element, per no deformar l'espaiat intern de la còpia.
        """
        if not isinstance(buf, dict):
            return
        chords = list(buf.get("chords") or [])
        sections = list(buf.get("sections") or [])
        trams_buf = list(buf.get("tempo") or [])
        if not chords and not sections and not trams_buf:
            return
        durada = float(self.audio["durada"])
        rel = 1e-6
        # -- àncora (prioritat dels DAWs: EVENTS → graella) --
        T = float(at)
        cc, bf = buf.get("cursor_copy"), buf.get("bloc_fi")
        if cc is not None and bf is not None and abs(T - float(cc)) <= 1e-6:
            T = float(bf)
        salta_snap = bool(QApplication.keyboardModifiers() & Qt.AltModifier)
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
        noves_trams = (self._bloc_sobre_trams(
            self.tempo_trams, trams_buf,
            float(buf.get("tempo_len") or 0.0), T, durada)
            if trams_buf else None)
        # -- validació sense efectes (no assigna res) --
        try:
            cand_ac = (self._valida_canvis_acords(nous_acords)
                       if nous_acords is not None else list(self.acords))
            cand_sec = (self._valida_canvis_seccions(noves_seccions)
                        if noves_seccions is not None else list(self.seccions))
            cand_tp = (tempo_map.valida_i_normalitza_compassos(
                noves_trams, durada, offset=getattr(self, "offset", 0.0))
                if noves_trams is not None
                else list(self.tempo_trams or []))
        except ValueError as e:
            self.log(f"enganxa: canvi invalid, no s'ha fet res ({e})")
            self.avis_editor(f"Enganxat no fet: {e}")
            return
        if (cand_ac == self.acords and cand_sec == self.seccions
                and cand_tp == list(self.tempo_trams or [])):
            self.log("enganxa: res a fer")
            self.avis_editor("Enganxat: res a canviar (el bloc coincideix "
                             "amb el model actual).")
            return
        self._undo_marca()
        self.acords = cand_ac
        if noves_seccions is not None:
            self.seccions = cand_sec
        if noves_trams is not None and cand_tp:
            self.aplica_tempo_trams(cand_tp)
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
        self._selecciona_bloc_enganxat(T, chords, sections, trams=trams_buf,
                                       tol=pipeline.MIN_GAP_TEMPS)
        self.log(f"enganxat a {T:.3f}s (sobreescrivint): {len(chords)} "
                 f"acord(s), {len(sections)} secció(ns), "
                 f"{len(trams_buf)} tram(s) de tempo/compàs")

    def _bloc_sobre_acords(self, acords, bloc, llargada, T, durada, rel):
        """Delega la sobreescriptura del bloc d'acords a `pipeline`."""
        return pipeline.bloc_sobre_acords(acords, bloc, llargada, T, durada, rel)

    def _bloc_sobre_trams(self, trams, bloc, llargada, T, durada):
        """Delega la sobreescriptura del bloc de trams a `tempo_map`."""
        return tempo_map.bloc_sobre_trams(trams, bloc, llargada, T, durada)

    def _bloc_sobre_seccions(self, seccions, bloc, llargada, T, durada, rel):
        """Delega la sobreescriptura del bloc de seccions a `pipeline`."""
        return pipeline.bloc_sobre_seccions(seccions, bloc, llargada, T, durada, rel)

    def _selecciona_bloc_enganxat(self, T, chords, sections, trams=None,
                                  tol=pipeline.MIN_GAP_TEMPS):
        """Deixa seleccionat el bloc acabat d'enganxar (acords, seccions i trams)."""
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
        for (r, _rfi, _b, _n, _d) in (trams or []):
            t = T + float(r)
            for i, tr in enumerate(self.tempo_trams or []):
                if abs(float(tr[0]) - t) <= tol:
                    keys.add(("tempo", i))
                    break
        if keys and hasattr(self, "timeline"):
            self.timeline.select_multi(keys)

    def _on_section_moved(self, idx, ini, fi):
        # Només sincronitzem el model/llista; el desat va al release
        # (`_on_edit_finished`), igual que als acords. Abans es reescrivia
        # l'ABC a cada `mouseMove` (disc i log per píxel).
        self._undo_marca()
        self._sync_timeline_seccions()
        self.log(f"secció {idx} moguda ({ini:.3f}-{fi:.3f})")

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

    def _clips_per_renombrar(self, kind=None):
        """(kind, índexs) del TIPUS indicat (o ACTIU) dins la selecció.

        Amb selecció **mixta** (acords + seccions) es renombren NOMÉS els del
        tipus indicat/actiu (opció acordada): dins un full de càlcul tampoc no
        es barreja en una sola acció el contingut de files de tipus diferent.
        Els **trams de BPM/compàs** no tenen renom en bloc (el contingut és
        numèric): es retorna `(None, [])` i el despatx obre el diàleg del tram.
        """
        keys = self.timeline.selected_keys()
        if not keys:
            return None, []
        akind = kind or getattr(self.timeline, "_sel", ("", -1))[0]
        if akind not in ("chord", "section"):
            return None, []
        kinds = {k for (k, _i) in keys}
        if akind not in kinds:
            if len(kinds) != 1:
                return None, []
            akind = next(iter(kinds))
            if akind not in ("chord", "section"):
                return None, []
        n = len(self.acords if akind == "chord" else self.seccions)
        idxs = sorted({i for (k, i) in keys if k == akind and 0 <= i < n})
        return akind, idxs

    def renomena_seleccio(self, kind=None):
        """Reanomena EN BLOC la selecció del **tipus actiu** (acords O seccions).

        Amb selecció mixta es renombren només els del tipus actiu (opció A).
        Tot en una sola operació de desfer; al final queda seleccionat el bloc.
        `kind` permet al despatx únic forçar el carril (i impedeix que un índex
        de tempo acabe renombrant seccions).
        """
        kind, idxs = self._clips_per_renombrar(kind)
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
        """Reanomena els acords `idxs` a `nom` delegant a `pipeline`."""
        try:
            cand, nom_net = pipeline.renomena_acords_model(
                self.acords, idxs, nom, self._durada_wav())
        except ValueError as e:
            self.log(f"reanomena acords: {e}")
            return False
        if cand is None:
            self.log("reanomena acords: res a fer (nom o selecció buits)")
            return False
        idxs = sorted({i for i in idxs if 0 <= i < len(self.acords)})
        self._undo_marca()
        self.acords = cand
        self._undo_commit()
        self._sincronitza_vista()
        try:
            self._desa_i_regenera()
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR: {e}")
        self.timeline.select_multi({("chord", i) for i in idxs})
        self.log(f"reanomenats {len(idxs)} acord(s) → {nom_net}")
        return True

    def _renomena_seccions(self, idxs, lletra):
        """Reanomena les seccions `idxs` delegant a `pipeline`."""
        try:
            cand, lletra_net = pipeline.renomena_seccions_model(
                self.seccions, idxs, lletra, self._durada_wav())
        except ValueError as e:
            self.log(f"reanomena seccions: {e}")
            return False
        if cand is None:
            self.log("reanomena seccions: res a fer")
            return False
        idxs = sorted({i for i in idxs if 0 <= i < len(self.seccions)})
        self._undo_marca()
        self.seccions = cand
        self._undo_commit()
        self._sincronitza_vista()
        try:
            self._regenera_abc_des_de_totes_les_seccions("bloc reanomenat")
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR: {e}")
        self.timeline.select_multi({("section", i) for i in idxs})
        self.log(f"reanomenades {len(idxs)} secció(ns) → {lletra_net}")
        return True

    def troba_i_reemplaca(self, camp, troba, reemplaca):
        """Substitueix TOTES les aparicions EXACTES delegant a `pipeline`."""
        troba = str(troba or "").strip()
        reemplaca = str(reemplaca or "").strip()
        if not troba or not reemplaca:
            return 0
        if camp == "estructura":
            cand, n, etq = pipeline.substitueix_en_model(
                self.seccions, "estructura", troba, reemplaca,
                self._durada_wav())
            if not n:
                return 0
            self._undo_marca()
            self.seccions = cand
            self._undo_commit()
            self._sincronitza_vista()
            try:
                self._regenera_abc_des_de_totes_les_seccions(
                    f"substitució estructura: {troba}→{etq}")
            except Exception as e:  # noqa: BLE001
                self.log(f"ERROR: {e}")
            self.log(f"substitució estructura: «{troba}» → «{etq}» ({n})")
            return n
        cand, n, nou = pipeline.substitueix_en_model(
            self.acords, "acords", troba, reemplaca, self._durada_wav())
        if not n:
            return 0
        self._undo_marca()
        self.acords = cand
        self._undo_commit()
        self._sincronitza_vista()
        try:
            self._desa_i_regenera()
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR: {e}")
        self.log(f"substitució acords: «{troba}» → «{nou}» ({n})")
        return n

    def _grid_target(self, t, grid, durada):
        """Instant de graella més proper per a un inici (mapa o BPM constant)."""
        t = float(t)
        d = graella.DIVISIONS.get(grid)
        if d is None:
            return t
        mapa = getattr(self, "tempo_map", None)
        if mapa is not None and not mapa.es_constant():
            return mapa.snap(t, d)
        step = graella.divisio_segons(grid, self.bpm, self.tempo_fix,
                                      self.bpb, getattr(self, "beat_type", 4))
        if step <= 0:
            return t
        off = float(getattr(self, "offset", 0.0))
        return max(0.0, off + round((t - off) / step) * step)

    def quantitza(self, abast="tot", grid_acords="compas1",
                  grid_estructura="compas4"):
        """Quantitza els INICIS dels clips del model (no el cru).

        `abast`: `"tot"` · `"seleccio"` · `"acords"` · `"estructura"`.
        Cada tipus usa la seua graella. Els clips no seleccionats no es mouen.
        Una sola operació de desfer; no toca BPM, compàs, offset ni el cru.
        Retorna quants clips (acords + seccions) ha canviat.
        """
        if not self.tempo_fix:
            self.log("quantitza: cal el mode BPM · compàs (graella musical)")
            return 0
        durada = float(self.audio["durada"])
        sel = set(self.timeline.selected_keys())
        if abast == "seleccio":
            ac_sel = {i for (k, i) in sel if k == "chord"}
            es_sel = {i for (k, i) in sel if k == "section"}
            if not ac_sel and not es_sel:
                self.log("quantitza: no hi ha cap clip seleccionat")
                return 0
        elif abast == "acords":
            ac_sel, es_sel = set(range(len(self.acords))), set()
        elif abast == "estructura":
            ac_sel, es_sel = set(), set(range(len(self.seccions)))
        else:
            ac_sel = set(range(len(self.acords)))
            es_sel = set(range(len(self.seccions)))

        canvi_ac = False
        canvi_sec = False
        nous_ac = list(self.acords)
        noves_sec = list(self.seccions)

        if ac_sel and self.acords:
            starts = [
                self._grid_target(c.ini, grid_acords, durada)
                if i in ac_sel else float(c.ini)
                for i, c in enumerate(self.acords)
            ]
            base = [(float(c.ini), float(c.fi), tuple(c.payload))
                    for c in self.acords]
            res = graella.quantitza_boundaries(
                base, starts, ac_sel, durada, log=self.log)
            nous_ac = pipeline.normalitza_clips(
                [pipeline.Clip(*c) for c in res], durada,
                pipeline.FORAT_ACORD, arrodoneix=True, deriva_fi=True,
                log=self.log)
            if not nous_ac:
                nous_ac = list(self.acords)
            try:
                nous_ac = self._valida_canvis_acords(nous_ac)
            except ValueError as e:
                self.log(f"quantitza: acords no vàlids ({e})")
                return 0
            canvi_ac = nous_ac != self.acords

        if es_sel and self.seccions:
            starts = [
                self._grid_target(float(s[0]), grid_estructura, durada)
                if i in es_sel else float(s[0])
                for i, s in enumerate(self.seccions)
            ]
            base = [(float(s[0]), float(s[1]),
                     (str(s[2]), str(s[3]))) for s in self.seccions]
            res = graella.quantitza_boundaries(
                base, starts, es_sel, durada, log=self.log)
            clips = pipeline.normalitza_clips(
                [pipeline.Clip(*c) for c in res], durada,
                pipeline.FORAT_SECCIO, log=self.log)
            noves_sec = pipeline.seccions_de_clips(clips)
            try:
                noves_sec = self._valida_canvis_seccions(noves_sec)
            except ValueError as e:
                self.log(f"quantitza: estructura no vàlida ({e})")
                return 0
            canvi_sec = noves_sec != self.seccions

        if not canvi_ac and not canvi_sec:
            self.log("quantitza: sense canvis (ja estava a la graella)")
            return 0

        self._undo_marca()
        if canvi_ac:
            self.acords = nous_ac
        if canvi_sec:
            self.seccions = noves_sec
        self._undo_commit()
        # Després de reconstruir el model, el `set_data` buida la selecció i
        # l'editor. Es recupera el clip que s'estava editant (si encara hi és)
        # perquè l'editor mostre el temps NOU, no el vell.
        ed = (getattr(self, "_ed_kind", None), getattr(self, "_ed_idx", -1))
        self.timeline.set_data(self.acords, self.seccions)
        try:
            if canvi_ac:
                self._desa_i_regenera()
            if canvi_sec:
                self._regenera_abc_des_de_totes_les_seccions("quantitza")
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR: {e}")
        self._omple_llista_ac()
        self._actualitza_llista_abc()
        if ed[0] in ("chord", "section") and self._index_valid(ed[0], ed[1]):
            self.timeline.select_clip(ed[0], ed[1])
        n = (len(self.acords) if canvi_ac else 0) + (
            len(self.seccions) if canvi_sec else 0)
        self.log(f"quantitza: {n} clip(s) (abast «{abast}», "
                 f"acords {grid_acords}, estructura {grid_estructura})")
        return n

    def _on_section_edit_requested(self, idx):
        # Doble-clic al SectionItem -> franja EDITOR (sense finestra emergent).
        if idx < 0 or idx >= len(self.seccions):
            return
        self._focus_editor("section", idx)

    # navegació
    def ves_a(self, t):
        # Cerca PROGRAMÀTICA (barra lliscant, llistes): posició EXACTA.
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
        if not kind:
            # El timeline ha perdut la selecció (re-render, quantitza, undo…):
            # l'editor no pot quedar-se mostrant un clip vell.
            if hasattr(self, "llista_ac"):
                self.llista_ac.setCurrentRow(-1)
            if hasattr(self, "llista_ab"):
                self.llista_ab.setCurrentRow(-1)
            if hasattr(self, "llista_tempo"):
                self.llista_tempo.setCurrentCell(-1, -1)
            self._ed_kind, self._ed_idx = None, -1
            self._actualitza_editor()
            return
        if kind == "chord" and 0 <= index < self.llista_ac.count():
            self.llista_ac.setCurrentRow(index)
        elif kind == "section" and 0 <= index < self.llista_ab.count():
            self.llista_ab.setCurrentRow(index)
        elif kind == "tempo":
            # El clip de tempo/compàs també s'edita a la franja Editor (BPM +
            # compàs). Es buiden les altres llistes perquè no quede un
            # acord/secció ressaltat mentre la franja mostra el tempo.
            self.llista_ac.setCurrentRow(-1)
            self.llista_ab.setCurrentRow(-1)
            if hasattr(self, "llista_tempo"):
                self.llista_tempo.setCurrentCell(int(index), 0)
            self._ed_kind, self._ed_idx = "tempo", int(index)
            self._actualitza_editor()
            return
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
        # La franja és compartida: cada mode hi posa les seues etiquetes.
        self.ed_nom_lbl.setText("Nom:")
        self.ed_fam_lbl.setText("Família:")
        self.ed_ini.setEnabled(True)
        self.ed_cb.setEnabled(True)
        if k == "tempo" and 0 <= i < len(getattr(self, "tempo_trams", None) or []):
            ini, fi, bpm, num, den = self.tempo_trams[i]
            lliure = int(num) <= 0 or int(den) <= 0
            self.ed_icona.setPixmap(icones.ico("metronome", 20).pixmap(20, 20))
            self.ed_gran.setText(
                f"Tempo · {float(fi) - float(ini):.2f} s"
                + (" · rubato" if lliure else ""))
            self.ed_nom_lbl.setText("BPM:")
            self.ed_nom.setToolTip("BPM del clip (30–350)")
            self.ed_nom.setText(f"{float(bpm):.3f}")
            self.ed_fam_lbl.setText("Compàs:")
            self.ed_fam.setToolTip(
                "Compàs num/den · 0/0 = clip en segons (rubato)")
            self.ed_fam.setText("0/0" if lliure else f"{int(num)}/{int(den)}")
            self.ed_fam.setVisible(True)
            self.ed_fam_lbl.setVisible(True)
            self.ed_ini.setText(f"{float(ini):.3f}")
            self.ed_cb.setText(self._secs_a_cb(float(ini)))
            # Inici/fi es mouen arrossegant la vora al timeline (re-tempo).
            self.ed_ini.setEnabled(False)
            self.ed_cb.setEnabled(False)
            for w in (self.ed_nom, self.ed_fam, self.ed_aplica):
                w.setEnabled(True)
        elif k == "chord" and 0 <= i < len(self.acords):
            t, nom = float(self.acords[i][0]), nom_acord(self.acords[i])
            self.ed_icona.setPixmap(icones.ico("music", 20).pixmap(20, 20))
            self.ed_gran.setText(nom)
            self.ed_nom.setText(nom)
            self.ed_nom.setToolTip("Nom de l'acord o lletra de la secció")
            self.ed_fam.setToolTip("Família de la secció (p. ex. N, A, B)")
            self.ed_ini.setText(f"{float(t):.3f}")
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
            self.ed_ini.setText(f"{float(ini):.3f}")
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
        """Segons → compàs.temps[.fusa] segons el MAPA de tempo vigent."""
        mapa = getattr(self, "tempo_map", None)
        if mapa is not None:
            if mapa.es_lliure(float(t)):
                return "—"          # rubato: no hi ha compàs
            c, b, sub = mapa.pos(float(t))
            return f"{c}.{b}" if sub == 1 else f"{c}.{b}.{sub}"
        beat = 60.0 / max(self.bpm, 1e-9)
        bpb = max(1, int(self.bpb))
        p = int(round(float(t) / beat * 8))
        SB = bpb * 8
        c = p // SB + 1
        dins = p % SB
        b = dins // 8 + 1
        sub = dins % 8 + 1
        return f"{c}.{b}" if sub == 1 else f"{c}.{b}.{sub}"

    def _cb_a_secs(self, text):
        """compàs.temps[.fusa] → segons segons el MAPA de tempo vigent."""
        m = re.match(r"\s*(-?\d+)\s*[.,]\s*(\d+)"
                     r"(?:\s*[.,]\s*(\d+))?\s*$", str(text))
        if not m:
            return None
        c, b = int(m.group(1)), int(m.group(2))
        sub = int(m.group(3)) if m.group(3) else 1
        sub = max(1, min(8, sub))
        mapa = getattr(self, "tempo_map", None)
        if mapa is not None:
            t = mapa.t_de_pos(c, b)
            if sub > 1:
                _bar_s, beat_s, _sub_s = mapa.durations(t)
                t += (sub - 1) / 8.0 * beat_s
            return max(0.0, float(t))
        beat = 60.0 / max(self.bpm, 1e-9)
        n = (c - 1) * max(1, int(self.bpb)) + (b - 1) + (sub - 1) / 8.0
        return max(0.0, n * beat)

    def avis_editor(self, text):
        """Avís de la franja Editor: al log I a la caixa d'informació.

        MAI en silenci: abans, sis camins de `_aplica_editor` tornaven sense dir
        res i el botó «Aplica» semblava no fer res (OC-6/394).
        """
        self.log(f"editor: {text}")
        self.infoMissatge.emit(text)

    def _aplica_editor_tempo(self, i):
        """Aplica BPM/compàs de la franja Editor a un clip de tempo.

        El compàs `0/0` (o buit, o «segons») deixa el clip en mode rubato;
        qualsevol altre valor ha de ser `num/den`.
        """
        trams = list(getattr(self, "tempo_trams", None) or [])
        if not (0 <= i < len(trams)):
            self.avis_editor("Aquest clip de tempo ja no existeix.")
            return
        txt = self.ed_nom.text().strip().replace(",", ".")
        try:
            bpm = float(txt)
        except ValueError:
            self.avis_editor(f"El BPM «{self.ed_nom.text()}» no és un número.")
            return
        txt_c = self.ed_fam.text().strip().lower()
        if txt_c in ("", "—", "-", "segons"):
            num = den = 0
        else:
            m = re.match(r"^\s*(\d+)\s*[/:]\s*(\d+)\s*$", txt_c)
            if not m:
                self.avis_editor(
                    f"El compàs «{self.ed_fam.text()}» no és vàlid "
                    "(num/den · 0/0 = segons).")
                return
            num, den = int(m.group(1)), int(m.group(2))
            if num <= 0 or den <= 0:
                num = den = 0          # 0/0 explícit = en segons
            elif not (1 <= num <= 12) or not (1 <= den <= 16):
                self.avis_editor(
                    f"Compàs {num}/{den} fora de rang (1–12 sobre 1–16).")
                return
        if num <= 0:
            if bpm < 1.0:
                bpm = 100.0
        self._undo_marca()
        # Si el canvi no és vàlid, `edita_tempo_objectiu` ja avisa; el commit
        # no apila res perquè l'estat no ha canviat.
        self.edita_tempo_objectiu(i, bpm, num, den)
        self._undo_commit()
        self._actualitza_editor()

    def _aplica_editor(self):
        """Aplica els canvis de la franja Editor al model (amb undo).

        Tots els camins que NO apliquen donen feedback visible (`avis_editor`):
        un botó que no fa res i no diu per què és un defecte.
        """
        k, i = getattr(self, "_ed_kind", None), getattr(self, "_ed_idx", -1)
        if k is None or i < 0:
            self.avis_editor("Selecciona un acord, una secció o un clip de "
                             "tempo (clic al clip) abans d'aplicar.")
            return
        if k == "tempo":
            self._aplica_editor_tempo(i)
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
            self.log(f"editor: acord {i} -> {nom} @ {ini:.3f}s")
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
            nova[i] = (ini, max(ini + self.MIN_SECCIO_S, fi), lletra, fam)
            try:
                # Manté la contigüitat (#2) com el drag del timeline.
                nova = self._contiguitat_seccions(nova, i)
                self.seccions = self._normalitza_seccions(nova)
            except ValueError as e:
                self.avis_editor(f"canvi invalid ({e})")
                return
            self._undo_commit()
            self.timeline.set_data(self.acords, self.seccions)
            self._regenera_abc_des_de_totes_les_seccions("editat des de l'editor")
            self.log(f"editor: seccio {i} -> {lletra} @ {ini:.3f}s")
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
        """Delega la validació d'estructura a `pipeline`."""
        return pipeline.valida_canvis_seccions(items, self._durada_wav())

    # Durada mínima d'una secció en moure'n una vora (evita seccions nul·les).
    MIN_SECCIO_S = 0.001

    # Durada mínima d'un acord en partir-lo (regla d'or #11; mirall de la secció).
    MIN_ACORD_S = 0.001

    def _contiguitat_seccions(self, items, idx):
        """Delega el manteniment de la contigüitat (#2) a `pipeline`."""
        return pipeline.contiguitat_seccions(items, idx, self.MIN_SECCIO_S)

    def mou_seccio(self, idx, ini, fi):
        """Mou/redimensiona la secció `idx` a (`ini`,`fi`) mantenint la contigüitat.

        Camí CANÒNIC del moviment de seccions (editor): el veí anterior
        estén/arronsa el seu `fi` fins al nou inici, i el següent fa el mateix
        amb el seu `ini`. Sense això quedava un forat intern que l'app acceptava
        (la suma de durades ja no quadrava amb la WAV).

        NO fa undo ni desa: els qui criden (bridge/editor) ja ho fan, com la
        resta de mutacions del model. Retorna `False` si l'índex no existeix.
        """
        if not (0 <= idx < len(self.seccions)):
            return False
        ini, fi = float(ini), float(fi)
        # Un «moviment» a les MATEIXES coordenades és un no-op LEGÍTIM (ubicar la
        # secció on ja és no és cap error) i es resol abans del guard de la
        # secció única: si no, una crida d'identitat rebria un error que no toca
        # (trobat per OC-13, 18-10-2026).
        actual = self.seccions[idx]
        if (abs(ini - float(actual[0])) <= 1e-6
                and abs(fi - float(actual[1])) <= 1e-6):
            return True
        # Amb una sola secció no hi ha res a moure: ha de cobrir tota la WAV
        # (regla d'or #4). Abans s'aplicava el canvi i el normalitzador de
        # cobertura el desfeia en silenci — l'usuari/agent veia "OK" i res no
        # canviava.
        if len(self.seccions) <= 1:
            raise ValueError(
                "És l'única secció: ha de cobrir tota la WAV (regla #4) i no "
                "es pot moure. Parteix-la primer si vols editar-ne un tros.")
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
                ini_txt = f"{ini:07.3f}s"
                fi_txt = f"{fi:07.3f}s"
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
        # Regla #4: la secció nova no pot deixar la resta de la cançó sense
        # etiqueta. Els forats es tapen amb «-» (el forat explícit), també si
        # el carril venia buit (llavors queden «-» | secció | «-»).
        self._normalitza_cobertura()
        if hasattr(self, "llista_ab"):
            self._actualitza_llista_abc()
        # Paritat #11 amb `_afegeix_acord`: la primitiva també refresca la vista.
        self._sincronitza_vista()
        return True

    def parteix_acord(self, idx, t, nom=None):
        """Parteix l'acord `idx` pel temps `t` (regla d'or #11).

        Mirall de `parteix_seccio`: l'acord de l'esquerra conserva el nom i acaba
        a `t`; el clip NOU (a la dreta) comença a `t` amb el nom triat (per
        defecte, el MATEIX). Retorna l'índex del clip nou, o `False` si `t` no
        cau a dins. L'ÚLTIM acord també es pot partir (acaba a la WAV).
        """
        if not (0 <= idx < len(self.acords)):
            return False
        t = float(t)
        t0 = float(self.acords[idx][0])
        # L'últim clip acaba a la WAV (regla d'or #4) i TAMBÉ es pot partir:
        # la meitat dreta queda fins al final (paritat #11 amb estructura).
        fi = float(self.acords[idx].fi)
        if not (t0 + self.MIN_ACORD_S <= t <= fi - self.MIN_ACORD_S):
            self.log(f"partir: {t:.3f}s no cau dins l'acord "
                     f"{nom_acord(self.acords[idx])} ({t0:.3f}s–{fi:.3f}s)")
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

    def parteix_per_la_meitat(self, kind, idx):
        """Parteix el clip `idx` just pel MIG (dues meitats iguals).

        `kind`: "chord", "section" o "tempo" (regla d'or #11: la mateixa eina
        per a les TRES pistes). El punt de tall és el centre exacte del clip /
        tram, de manera que totes dues meitats queden amb la mateixa durada.
        Retorna l'índex del clip NOU, o `False` si no es pot (clip inexistent o
        meitat massa curta).
        """
        if kind == "tempo":
            return self._parteix_tram_per_la_meitat(idx)
        if kind == "chord":
            if not (0 <= idx < len(self.acords)):
                return False
            c = self.acords[idx]
            t = (float(c.ini) + float(c.fi)) / 2.0
        else:
            if not (0 <= idx < len(self.seccions)):
                return False
            ini, fi = self.seccions[idx][0], self.seccions[idx][1]
            t = (float(ini) + float(fi)) / 2.0
        nou = (self.parteix_acord(idx, t) if kind == "chord"
               else self.parteix_seccio(idx, t))
        if not nou:
            self.log(f"partir per la meitat: {t:.3f}s no serveix pel clip "
                     f"{idx} ({kind})")
            return False
        nom = "acord" if kind == "chord" else "secció"
        try:
            if kind == "chord":
                self._desa_i_regenera()
            else:
                self._regenera_abc_des_de_totes_les_seccions(
                    f"secció partida per la meitat a {t:.3f}s")
            self.log(f"partit per la meitat el {nom} {idx} a {t:.3f}s")
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR: {e}")
            QMessageBox.warning(self, "Visor", f"No s'ha pogut desar:\n{e}")
        return nou

    # --- Partir a la selecció A–B (2026-10-20) -----------------------------
    def _loop_vals(self):
        """Rang A–B del loop si és vàlid (A<B i dins la WAV), o `None`."""
        a = getattr(self, "loop_a", None)
        b = getattr(self, "loop_b", None)
        if a is None or b is None:
            return None
        a, b = sorted((float(a), float(b)))
        durada = self._durada_wav()
        if b - a <= 1e-6 or a >= durada - 1e-6:
            return None
        return (max(0.0, a), min(b, durada))

    def _talls_del_loop(self, ini, fi, minim):
        """Punts de tall del loop que cauen DINS `[ini, fi]`, amb marge.

        A i B només parteixen si són **estrictament interiors** al clip (amb
        `minim` de marge a cada vora): una frontera que ja coincideix amb la
        vora no és cap tall.
        """
        loop = self._loop_vals()
        if loop is None:
            return None
        talls = [t for t in loop
                 if float(ini) + minim < t < float(fi) - minim]
        return sorted(set(round(t, 9) for t in talls))

    def _sel_despres_dels_talls(self, idx, talls):
        """Tros a seleccionar: el que comença a A, o el que acaba a B."""
        loop = self._loop_vals()
        if loop is not None and talls and abs(talls[0] - loop[0]) < 1e-6:
            return idx + 1
        return idx

    def parteix_a_loop(self, kind, idx):
        """**Parteix** el clip `idx` pels punts A i B del loop (un sol desfer).

        És el «parteix aquí» fet **als dos llocs alhora**: cada frontera del
        loop (A i B) que caiga **dins** del clip seleccionat hi deixa un tall
        nou, de manera que el clip queda en dos o tres trossos amb el MATEIX
        nom (④ acords · ⑤ estructura · ③ BPM/compàs). El tros que va d'A a B
        queda **seleccionat**. Si A i B cauen fora del clip, no es parteix res
        i s'avisa. Tot va en una sola operació de desfer.

        Retorna `True` si s'ha aplicat cap tall.
        """
        loop = self._loop_vals()
        if loop is None:
            self.avis_editor("Parteix a A–B: no hi ha cap loop A–B marcat.")
            return False
        if kind == "chord":
            return self._parteix_chord_a_loop(idx)
        if kind == "section":
            return self._parteix_seccio_a_loop(idx)
        if kind == "tempo":
            return self._parteix_tram_a_loop(idx)
        return False

    def _parteix_chord_a_loop(self, idx):
        items = list(self.acords)
        if not (0 <= idx < len(items)):
            return False
        ini, fi = float(items[idx].ini), float(items[idx].fi)
        talls = self._talls_del_loop(ini, fi, self.MIN_ACORD_S)
        if not talls:
            self.avis_editor(
                f"Parteix a A–B: ni A ni B cauen dins de l'acord {idx + 1} "
                f"({ini:.2f}–{fi:.2f}s); no hi ha res a partir.")
            return False
        nom = nom_acord(items[idx])
        i = idx
        try:
            for t in talls:
                items = pipeline.parteix_clips(
                    items, i, t, nou_payload=(nom, f"{t:.9f}"))
                i += 1
            items = self._normalitza_acords(items)
        except ValueError as e:
            self.avis_editor(f"Parteix a A–B: {e}")
            return False
        self._undo_marca()
        self.acords = items
        self._undo_commit()
        self._desa_i_regenera()
        sel = min(self._sel_despres_dels_talls(idx, talls),
                  len(self.acords) - 1)
        self._refresca_post_edicio("chord", sel)
        self.log(f"partit a A–B: acord {idx + 1} ({nom}) pels talls "
                 f"{', '.join(f'{t:.3f}s' for t in talls)}")
        return True

    def _parteix_seccio_a_loop(self, idx):
        items = list(self.seccions)
        if not (0 <= idx < len(items)):
            return False
        ini, fi = float(items[idx][0]), float(items[idx][1])
        talls = self._talls_del_loop(ini, fi, self.MIN_SECCIO_S)
        if not talls:
            self.avis_editor(
                f"Parteix a A–B: ni A ni B cauen dins de la secció "
                f"{items[idx][2]} ({ini:.2f}–{fi:.2f}s); no hi ha res a "
                "partir.")
            return False
        L, F = items[idx][2], items[idx][3]
        i = idx
        try:
            clips = pipeline.clips_de_seccions(self.seccions)
            for t in talls:
                clips = pipeline.parteix_clips(
                    clips, i, t, nou_payload=(L, F),
                    marge=self.MIN_SECCIO_S, etiqueta="secció")
                i += 1
            items = self._normalitza_seccions(
                pipeline.seccions_de_clips(clips))
        except ValueError as e:
            self.avis_editor(f"Parteix a A–B: {e}")
            return False
        self._undo_marca()
        self.seccions = items
        self._undo_commit()
        try:
            self._regenera_abc_des_de_totes_les_seccions("partit a A–B")
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR: {e}")
            self.avis_editor(f"Parteix a A–B: no s'ha pogut desar ({e})")
        sel = min(self._sel_despres_dels_talls(idx, talls),
                  len(self.seccions) - 1)
        self._refresca_post_edicio("section", sel)
        self.log(f"partida a A–B: secció {L} pels talls "
                 f"{', '.join(f'{t:.3f}s' for t in talls)}")
        return True

    def _parteix_tram_a_loop(self, idx):
        trams = list(self.tempo_trams or [])
        if not (0 <= idx < len(trams)):
            return False
        ini, fi = float(trams[idx][0]), float(trams[idx][1])
        loop = self._loop_vals() or (None, None)
        # ③: només es pot tallar en una **línia de compàs**; `parteix_a_compas`
        # imanta-hi el punt (el gest d'arrossegar ja ho fa igual).
        cands = [t for t in loop if t is not None and ini < t < fi]
        if not cands:
            self.avis_editor(
                f"Parteix a A–B: ni A ni B cauen dins del tram {idx + 1} "
                f"({ini:.2f}–{fi:.2f}s); no hi ha res a partir.")
            return False
        i = idx
        talls = []
        err = None
        for t in sorted(cands):
            try:
                tall, trams = tempo_map.parteix_a_compas(
                    trams, i, t, self._durada_wav(),
                    offset=float(getattr(self, "offset", 0.0) or 0.0))
            except ValueError as e:
                # Normalment vol dir que A i B s'imanten al MATEIX compàs
                # (el segon tall ja és una frontera): es descarta.
                err = e
                continue
            if talls and abs(tall - talls[-1]) <= 1e-6:
                continue
            talls.append(tall)
            i += 1
            if i >= len(trams):
                break
        if not talls:
            self.avis_editor(f"Parteix a A–B (compàs): {err}")
            return False
        self._undo_marca()
        self.aplica_tempo_trams(trams)
        self._undo_commit()
        sel = min(self._sel_despres_dels_talls(idx, talls),
                  len(self.tempo_trams) - 1)
        if hasattr(self, "timeline"):
            self.timeline.select_multi({("tempo", sel)})
        nota = ""
        if any(abs(t - c) > 1e-6 for t, c in zip(talls, sorted(cands))):
            nota = " (imantat a la línia de compàs)"
        self.log(f"partit a A–B: tram {idx + 1} pels talls "
                 f"{', '.join(f'{t:.3f}s' for t in talls)}{nota}")
        return True

    def _parteix_tram_per_la_meitat(self, idx):
        """«Partir per la meitat» d'un tram de BPM/compàs (③).

        El mapa és **saturat** i els trams interiors tenen compassos enters:
        el tall s'imanta a la línia de compàs més pròxima al centre. Si el
        tram només té un compàs, no es pot partir en dos trams enters i es
        rebutja. Una sola operació de desfer.
        """
        trams = list(self.tempo_trams or [])
        if not (0 <= idx < len(trams)):
            return False
        ini, fi = float(trams[idx][0]), float(trams[idx][1])
        t = (ini + fi) / 2.0
        try:
            _tall, nous = tempo_map.parteix_a_compas(
                trams, idx, t, self._durada_wav(),
                offset=getattr(self, "offset", 0.0))
        except ValueError as e:
            self.log(f"partir per la meitat: {e}")
            self.avis_editor(f"Partir tempo: {e}")
            return False
        self._undo_marca()
        self.aplica_tempo_trams(nous)
        self._undo_commit()
        self.log(f"partit per la meitat el tram de BPM/compàs {idx} a "
                 f"{t:.3f}s")
        return idx + 1

    def _parteix_acord_dialog(self, idx, t=None):
        """Parteix l'acord `idx` pel punt del clic (o el cursor), preguntant el nom.

        Decisió 2026-10-19: des del menú contextual mana el **punt del clic**
        (amb snap si està actiu); si no és vàlid, es fa servir el cursor. El
        menú principal hi passa el cursor. Regla #11: mateix criteri que les
        seccions i el tempo.
        """
        if not (0 <= idx < len(self.acords)):
            return False
        t0 = float(self.acords[idx][0])
        nom = nom_acord(self.acords[idx])
        fi = float(self.acords[idx].fi)
        tall = self._punt_de_tall(t, t0, fi, self.MIN_ACORD_S, nom)
        if tall is None:
            QMessageBox.information(
                self, "Parteix l'acord",
                f"Cal un punt DINS l'acord «{nom}» ({t0:.3f}–{fi:.3f} s), "
                "amb marge a les vores. Amb el snap actiu, pot caure a la vora.")
            return False
        nou, ok = QInputDialog.getText(
            self, "Parteix l'acord",
            f"Parteix «{nom}» a {tall:.3f} s.\nNom de la part nova:",
            text=nom)
        if not ok:
            return False
        if not self.parteix_acord(idx, tall, nou):
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
            self.log(f"partir: {t:.3f}s no cau dins la secció {L} "
                     f"({ini:.3f}s–{fi:.3f}s)")
            return False
        L2 = (str(lletra).strip() if lletra else L) or L
        F2 = (str(fam).strip() if fam else (F or L2)) or L2
        self._undo_marca()
        try:
            nova = pipeline.seccions_de_clips(
                pipeline.parteix_clips(
                    pipeline.clips_de_seccions(self.seccions), idx, t,
                    nou_payload=(L2, F2), marge=self.MIN_SECCIO_S,
                    etiqueta="secció"))
            self.seccions = self._normalitza_seccions(nova)
        except ValueError as e:
            self.log(f"partir: canvi invalid ({e})")
            return False
        self._undo_commit()
        self._sincronitza_vista()
        if hasattr(self, "llista_ab"):
            self._actualitza_llista_abc()
        return idx + 1

    def _parteix_seccio_dialog(self, idx, t=None):
        """Parteix la secció `idx` pel punt del clic (o el cursor), amb snap.

        Mateix criteri que els acords (#11 i decisió 2026-10-19): mana el punt
        del clic; si no és vàlid, el cursor.
        """
        if not (0 <= idx < len(self.seccions)):
            return False
        ini, fi, L, _F = self.seccions[idx]
        ini, fi = float(ini), float(fi)
        tall = self._punt_de_tall(t, ini, fi, self.MIN_SECCIO_S, L)
        if tall is None:
            QMessageBox.information(
                self, "Parteix la secció",
                f"Cal un punt DINS la secció «{L}» ({ini:.3f}–{fi:.3f} s), "
                "amb marge a les vores. Amb el snap actiu, pot caure a la vora.")
            return False
        nova, ok = QInputDialog.getText(
            self, "Parteix la secció",
            f"Parteix «{L}» a {tall:.3f} s.\nLletra de la part nova:",
            text=L)
        if not ok:
            return False
        if not self.parteix_seccio(idx, tall, nova):
            return False
        try:
            self._regenera_abc_des_de_totes_les_seccions(
                f"secció {L} partida a {tall:.3f}s")
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
        """Botó dret a la LLISTA d'estructura (mateixa definició que el timeline)."""
        self._menu_de_llista("section", getattr(self, "llista_ab", None), pos)

    # ---- Llista de clips de tempo/compàs -------------------------------
    def _omple_llista_tempo(self):
        """Una fila per tram del mapa (inici, fi, BPM, compàs).

        Es repobla des de `_actualitza_temps()`, el punt únic que ja criden
        tots els camins que canvien el mapa (barra, diàlegs, drag, undo).
        Preserva la fila seleccionada, com les altres dues llistes.
        """
        t = getattr(self, "llista_tempo", None)
        if t is None:
            return
        cur = t.currentRow()
        trams = list(getattr(self, "tempo_trams", None) or [])
        t.blockSignals(True)
        try:
            t.setRowCount(len(trams))
            for i, (ini, fi, bpm, num, den) in enumerate(trams):
                lliure = int(num) <= 0 or int(den) <= 0
                vals = (f"{float(ini):.3f}", f"{float(fi):.3f}",
                        f"{float(bpm):.3f}",
                        "segons" if lliure else f"{int(num)}/{int(den)}")
                for c, v in enumerate(vals):
                    it = t.item(i, c)
                    if it is None:
                        it = QTableWidgetItem()
                        it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                        t.setItem(i, c, it)
                    if it.text() != v:
                        it.setText(v)
        finally:
            t.blockSignals(False)
        if 0 <= cur < t.rowCount():
            t.setCurrentCell(cur, 0)

    def _salt_tempo(self, item):
        """Clic a la llista de tempo → selecciona el clip i hi porta el cursor."""
        row = self.llista_tempo.row(item)
        if row < 0:
            return
        self._ed_kind, self._ed_idx = "tempo", row
        self.timeline.select_clip("tempo", row)
        self._actualitza_editor()
        trams = getattr(self, "tempo_trams", None) or []
        if 0 <= row < len(trams):
            self.ves_a(float(trams[row][0]))
        self.timeline.ensure_cursor_visible()

    def _menu_tempo(self, pos):
        """Botó dret a la LLISTA de tempo (mateixa definició que el timeline)."""
        self._menu_de_llista("tempo", getattr(self, "llista_tempo", None), pos)

    def _regenera_posicions_musicals(self, msg):
        """Reescriu les **posicions musicals** derivades (compàs) de l'ABC.

        Decisió 2026-10-19: els segons són la font de veritat; canviar el BPM
        no mou cap acord ni secció. Però les columnes `compas_ini`/`compas_fi`
        de `estructura_ABC.csv` (i les etiquetes de la UI) sí que depenen del
        mapa de tempo i s'han de recalcular.
        """
        if not self.seccions:
            return False
        try:
            self._regenera_abc_des_de_totes_les_seccions(msg)
            return True
        except Exception as e:  # noqa: BLE001
            self.log(f"posicions musicals: ERROR ({e})")
            return False

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
        self.log(f"play des de {t:.3f}s amb {self.player}...")
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
            # VELOCITAT: si no és 1×, el buffer ja ve estirat (`atempo`, to
            # mantingut) → dura `1/factor` (a 2×, la meitat). `pos` va SEMPRE
            # en mostres de CANÇÓ (les mateixes que el model, el cursor, el
            # loop i el metrònom); al buffer li toca `pos/factor`.
            factor = max(0.5, min(3.0, float(getattr(self, "velocitat", 1.0))))
            if abs(factor - 1.0) < 1e-9:
                # 1×: el camí de sempre (cap còpia, cap dependència de ffmpeg)
                mono = memoryview(self._mono_bytes())
            else:
                try:
                    mono = memoryview(self._mono_a(factor))
                except (RuntimeError, OSError, ValueError) as e:
                    # Sense ffmpeg (o si el render falla) el so NO s'ha
                    # d'aturar: es torna a 1× i s'avisa al registre.
                    self.log(f"velocitat {factor:g}× no disponible ({e}); "
                             "es reprodueix a 1×")
                    factor = 1.0
                    mono = memoryview(self._mono_bytes())
            sr = int(self.audio["sr"])
            n_canco = (len(mono) // 2) * factor     # mostres de cançó
            pas = 32768  # mostres de SORTIDA per tros (a ritme real)
            fade = max(1, int(self.FADE_LOOP_S * sr))
            pos = float(max(0.0, min(float(t_inici),
                                     float(self.audio["durada"]))) * sr)
            while True:
                if sess != self._sess or proc.poll() is not None:
                    break
                bucle = (self.loop_on and self.loop_a is not None
                         and self.loop_b is not None)
                a = b = 0.0
                if bucle:
                    a = float(self.loop_a) * sr
                    b = float(self.loop_b) * sr
                    if b - a < 2:
                        bucle = False
                    elif pos < a or pos >= b:
                        pos = a
                # `pas` mostres de SORTIDA = `pas*factor` mostres de cançó
                fi = min(b if bucle else n_canco, pos + pas * factor)
                if fi <= pos:
                    break
                i_ini = int(round(pos / factor))
                i_fi = int(round(fi / factor))
                tros = bytes(mono[i_ini * 2:i_fi * 2])
                g = 0.0 if self.mut else self.vol
                if bucle or g != 1.0:
                    x = np.frombuffer(tros, dtype=np.int16).astype(np.float32)
                    if bucle:
                        a_buf = int(round(a / factor))
                        b_buf = int(round(b / factor))
                        idx = np.arange(i_ini - a_buf, i_fi - a_buf,
                                        dtype=np.float32)
                        env = np.minimum(np.minimum(1.0, idx / fade),
                                         np.minimum(1.0,
                                                    (b_buf - a_buf - 1 - idx)
                                                    / fade))
                        x = x * (g * env)
                    else:
                        x = x * g
                    tros = np.clip(x, -32768, 32767).astype(np.int16).tobytes()
                if self.metro_on and self.metro_vol > 0:
                    forc = getattr(self, "metro_forcat", None)
                    if forc is not None:
                        # graella pròpia (guiat): el clic s'alinea a `offset`
                        # encara que el mapa diga una altra cosa
                        mbpm, mbpb, moff = forc
                        tros = metronom.mescla_metronom(
                            tros, sr, pos / float(sr), mbpm, mbpb,
                            volum=self.metro_vol, offset=moff, mapa=None,
                            factor=factor)
                    else:
                        tros = metronom.mescla_metronom(
                            tros, sr, pos / float(sr), self.bpm, self.bpb,
                            volum=self.metro_vol,
                            offset=getattr(self, "offset", 0.0),
                            mapa=getattr(self, "tempo_map", None),
                            factor=factor)
                try:
                    proc.stdin.write(tros)
                except (BrokenPipeError, ValueError):
                    break
                pos = fi
                if bucle and pos >= b:
                    pos = a
                elif not bucle and pos >= n_canco:
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
            self.log(f"stop a {self.pos:.3f}s")
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
        # El cursor avança en TEMPS DE CANÇÓ: a 2× passa el doble de cançó per
        # segon real (el só ja va estirat, el rellotge ha d'anar al mateix pas).
        t = self.t0_pos + ((time.monotonic() - self.t0_mono)
                           * float(getattr(self, "velocitat", 1.0)))
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
                manifest = []
                pipeline.regenera_wavs_acords(self.csv_acords, sortida,
                                              self.bpm, self.bpb,
                                              self.offset, self.audio["durada"],
                                              44100, self.log,
                                              self.tempo_fix,
                                              manifest=manifest)
                pipeline.regenera_wavs_estructura(abc, sortida, 44100,
                                                  self.log,
                                                  manifest=manifest)
                if manifest:
                    pipeline.escriu_manifest(
                        os.path.join(sortida, "manifest.csv"), manifest)
            else:
                pipeline.exporta_total(self.csv_acords, None,
                                       sortida, self.bpm, self.bpb, self.offset,
                                       44100, self.log, tempo_fix=self.tempo_fix,
                                       amb_estructura=False,
                                       mapa_tempo=list(self.tempo_trams or []))
            self.log(f"exporta FET: {sortida}")
            QMessageBox.information(self, "Visor",
                                    f"Exportació feta a:\n{sortida}")
        except Exception as e:  # noqa: BLE001
            self.log(f"exporta ERROR: {e}")
            QMessageBox.warning(self, "Visor",
                                f"No s'ha pogut exportar:\n{e}")

    def _neteja_velocitat(self):
        """Els WAV estirats que ha creat `ffmpeg` → **paperera** (mai `rm`)."""
        for ruta in getattr(self, "_vel_temporals", []):
            try:
                plataforma.a_la_paperera(ruta)
            except OSError:
                pass
        self._vel_temporals = []
        self._vel_cache = {}

    def closeEvent(self, ev):
        self.log("tanco: mato l'àudio...")
        self.rellotge.stop()
        self._atura_proc()
        self._neteja_velocitat()
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
                ("editCancelled", self._on_edit_cancelled),
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
                ("editCommandRequested", self._on_edit_command),
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
    ap.add_argument("--acords", default="", help="csv d'acords (inici,fi,acord)")
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
