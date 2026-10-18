#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
timeline.py — Editor visual de la pista tipus DAW (QGraphicsView).

L'objectiu és oferir una interfície amable per navegar, corregir i editar
acords i estructura sobre una WAV, substituint el pintat monolític de
PartituraView (visor.py) per un editor basat en QGraphicsView on:

- L'ona es pinta un sol cop com a QPixmap (WaveformLayer).
- Sobre l'ona hi ha el grid de temps (RulerLayer) amb snap a beat/compàs.
- Sota el grid hi ha 2 carrils (Lane): un d'acords i un d'estructura.
- Cada acord i cada secció és un QGraphicsItem propi (ChordItem/SectionItem)
  amb nanses d'arrossegament als extrems i cos central per moure'l sencer.
- Quan s'arrossega un element, el final de l'anterior i l'inici del següent
  es propaguen automàticament (constraint live, línia guia visible).
- Snap a beat/compàs (tempo_fix) o a segons (lliure), configurable.
- Doble-clic → edició inline del nom (QLineEdit overlay).
- Zoom amb roda + Ctrl, pan amb roda, click al fons per moure cursor.

El model de dades continua sent el del projecte:
    acords   = [(t, nom, tsrc), ...]            # durada implícita (next.t - t)
    seccions = [(ini, fi, lletra, família), ...] # durada explícita
    invarianta: prev.fi == curr.t per a acords; ordre estricte per a tothom.

Tot en català. Sense dependències noves (PyQt5.QtWidgets + numpy).
"""
from typing import List, Optional, Sequence

import numpy as np
from PyQt5.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QPainter, QPen
from PyQt5.QtWidgets import (
    QApplication, QGraphicsItem, QGraphicsLineItem, QGraphicsRectItem,
    QGraphicsScene, QGraphicsView, QWidget,
)

from app import theme      # noqa: E402  (paleta centralitzada)


# -----------------------------------------------------------------------------
# Base compartida (constants i utilitats de temps/snap)
# -----------------------------------------------------------------------------
# Extret a app/timeline_base.py per alleugerir aquest fitxer. Es re-exporten
# tots els noms per mantenir la compatibilitat (from app.timeline import ...).
from app.timeline_base import (   # noqa: E402,F401
    CHORD_ACTIVE_FILL, CURSOR_COLOR, GUIDE_COLOR, LANE_ACC_TOP, LANE_BG_A,
    LANE_BG_B, LANE_H, LANE_SEC_TOP, LANE_TEMPO_H, LANE_TEMPO_TOP,
    LEFT_PAD, LOOP_GRAB_PX, MIN_GAP_S,
    MIN_SEC_LEN_S, PIXELS_PER_SECOND_DEFAULT, RIGHT_PAD, RULER_H,
    SELECTION_COLOR, SNAP_MARCA_PX, TOTAL_H, WAVEFORM_H, fmt_pos, grid_levels,
    loop_after_drag, snap_step, snap_time,
)
from app import graella  # noqa: E402
from app import pipeline  # noqa: E402  (DESTÍ del moviment d'un bloc, §6.3)


# -----------------------------------------------------------------------------
# Capes de fons (extretes a app/timeline_layers.py)
# -----------------------------------------------------------------------------
# Es re-exporten per mantenir la compatibilitat (from app.timeline import ...).
from app.timeline_layers import (   # noqa: E402,F401
    CursorLine, GridLayer, LaneBackground, RulerLayer, TempoLayer,
    WaveformLayer,
)

# API pública del mòdul (inclou els re-exports per compatibilitat amb codi i
# tests que fan `from app.timeline import ...`). Amb __all__ explícit, els
# re-exports no es marquen com a imports no usats.
__all__ = [
    "TimelineView", "ChordItem", "SectionItem", "RenameEditor",
    "WaveformLayer", "GridLayer", "RulerLayer", "LaneBackground", "CursorLine",
    "TempoLayer",
    "fmt_pos", "snap_time", "grid_levels", "CURSOR_COLOR",
    "CHORD_ACTIVE_FILL", "SELECTION_COLOR",
]


# -----------------------------------------------------------------------------
# Elements editables (extrets a app/timeline_items.py)
# -----------------------------------------------------------------------------
# Es re-exporten per mantenir la compatibilitat (from app.timeline import ...).
from app.timeline_items import (   # noqa: E402,F401
    ChordItem, RenameEditor, SectionItem,
)


# -----------------------------------------------------------------------------
# TimelineView — la vista QGraphicsView principal
# -----------------------------------------------------------------------------
def _acords_a_clips(acords, durada):
    """Converteix el model d'acords a **clips** (S4); accepta marques (pont)."""
    return pipeline.clips_de_model(acords, durada)


class TimelineView(QGraphicsView):
    """Vista amb ona + ruler + 2 carrils (acords + estructura).

    Senyals:
      positionChanged(t)     — quan el cursor canvia (click al fons o bé|
                              externament via set_position).|
      chordTimeMoved(i, t)   — l'inici de l'acord i ha canviat a t.|
      chordEndMoved(i, t)    — el final de l'acord i (= inici del següent)|
                              ha canviat a t. També propaga al següent.|
      chordRenamed(i, name)  — l'acord i ha estat reanomenat.|
      chordDeleteRequested(i) — l'acord i vol ser eliminat.|
      chordEditRequested(i)   — l'acord i vol ser editat (doble-clic).|
      sectionMoved(i, ini, fi) — la secció i ha canviat.||
      sectionRenamed(i, lletra, familia) — la secció i ha estat reanomenada.|
      sectionDeleteRequested(i) — la secció i vol ser eliminada.|
      sectionEditRequested(i)   — la secció i vol ser editada.|
    """

    positionChanged = pyqtSignal(float)
    clipSelected = pyqtSignal(str, int)   # ('chord'|'section', index)
    editStarted = pyqtSignal()            # inici d'un gest d'edicio (undo)
    editFinished = pyqtSignal()           # fi d'un drag (cal persistir)
    loopChanged = pyqtSignal(float, float)  # nou loop A/B (segons)
    playRequested = pyqtSignal()          # espai premut
    escapePressed = pyqtSignal()          # Esc (el resol el visor, per ordre)
    chordTimeMoved = pyqtSignal(int, float)
    chordEndMoved = pyqtSignal(int, float)
    chordRenamed = pyqtSignal(int, str)
    chordDeleteRequested = pyqtSignal(int)
    chordDuplicateRequested = pyqtSignal(int)
    # Alt+arrossegar un clip d'acord: el clip viatja i a l'ORIGEN en queda una
    # còpia (convenció universal dels DAWs: Alt+drag = duplicar). Payload:
    # (instant ORIGINAL on s'ha de deixar la còpia, nom de l'acord).
    chordCopyRequested = pyqtSignal(float, str)
    chordEditRequested = pyqtSignal(int)
    sectionMoved = pyqtSignal(int, float, float)
    sectionRenamed = pyqtSignal(int, str, str)
    sectionDeleteRequested = pyqtSignal(int)
    sectionDuplicateRequested = pyqtSignal(int)
    # Ctrl+Shift+arrossegar una SECCIÓ: viatja i a l'ORIGEN hi torna una còpia
    # (mateixa lletra i família) sobre el mateix tram. Payload:
    # (ini, fi, lletra, família) de la secció original.
    sectionCopyRequested = pyqtSignal(float, float, str, str)
    # Pista de BPM/compàs (fase 4b editable): clic a un bloc, vora arrossegada
    # i botó dret (índex del bloc; -1 = fora).
    tempoEditRequested = pyqtSignal(int)
    tempoChangeMoved = pyqtSignal(int, str, float)
    tempoMenuRequested = pyqtSignal(int, float)
    clipContextMenuRequested = pyqtSignal(str, int, QPoint)  # (kind, idx, pos)
    loopContextMenuRequested = pyqtSignal(QPoint)  # botó dret dins del loop
    loopDoubleClicked = pyqtSignal()   # doble-clic dins del loop (a dalt)
    sectionEditRequested = pyqtSignal(int)
    multiDeleteRequested = pyqtSignal(list)  # [(kind, idx), ...] multi-selecció
    pasteRequested = pyqtSignal(dict, float)  # (buffer intern, temps d'enganxar)
    groupDuplicateRequested = pyqtSignal(list)  # [(kind, idx), ...] duplicar grup

    def info_zona(self, pos_vista) -> str:
        """Text d'ajuda per a la caixa d'informacio, segons on es el ratoli.

        Es el costat "visible" del ratoli intel·ligent: la info box explica
        quina accio fa el ratoli en aquesta zona (moure, redimensionar,
        loop, pan, zoom...).
        """
        p = self.mapToScene(pos_vista)
        if p.y() < RULER_H:
            return ("Regle: arrossega per crear un LOOP A/B · clic per saltar-hi")
        it = self.itemAt(pos_vista)
        if isinstance(it, ChordItem):
            nom = getattr(it, "name", "?")
            z = it._zone_at(it.mapFromScene(p).x())
            if z == ChordItem.ZONE_LEFT:
                return f"↔ Mou l'INICI de l'acord «{nom}»"
            if z == ChordItem.ZONE_RIGHT:
                return (f"↔ Mou el FINAL de «{nom}» (mou també l'inici del "
                        "següent)")
            return (f"✋ Mou l'acord «{nom}» · doble-clic: editar · "
                    "botó dret: menú")
        if isinstance(it, SectionItem):
            L = getattr(it, "lletra", "?")
            fam = getattr(it, "familia", "")
            et = f"{L} · {fam}" if fam and fam != L else L
            z = it._zone_at(it.mapFromScene(p).x())
            if z == SectionItem.ZONE_LEFT:
                return f"↔ Mou l'INICI de la secció «{et}»"
            if z == SectionItem.ZONE_RIGHT:
                return f"↔ Mou el FINAL de la secció «{et}»"
            return (f"✋ Mou la secció «{et}» · doble-clic: editar · "
                    "botó dret: menú")
        # zona buida (ona)
        if self._cursor is not None and abs(p.x() - self._cursor.scenePos().x()) < 5:
            return "CURSOR: clic per moure'l · arrossega el regle per fer un loop"
        return ("Ona: clic = posar el cursor · botó dret = moure la vista · "
                "roda = zoom · Shift+roda = desplaçar")

    def __init__(self, audio: dict, acords: Sequence, seccions: Sequence,
                 bpm: float, bpb: int, tempo_fix: bool,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._audio = audio
        self._durada = float(audio.get("durada", 1.0))
        self._pps = PIXELS_PER_SECOND_DEFAULT
        self._x_offset = LEFT_PAD
        self._view_left = 0.0
        self._view_right = self._durada
        self._tempo_fix = bool(tempo_fix)
        self._bpm = float(bpm)
        self._bpb = int(bpb)
        self._mapa = None      # mapa de tempo/compàs (fase 3; None = uniforme)
        self._acords = _acords_a_clips(acords, self._durada)
        self._seccions = list(seccions) or []
        self._chord_items: List[ChordItem] = []
        self._section_items: List[SectionItem] = []
        self._chord_by_idx: dict = {}
        self._section_by_idx: dict = {}
        self._guide_line: Optional[QGraphicsLineItem] = None
        self._pos_t = 0.0          # temps del cursor (font de veritat)
        self._snap_on = True       # interruptor de snap
        self._snap_div_nom = ""    # "" = automàtic (zoom); o "corxera"…
        self._follow = False       # seguir el cursor durant el play
        self._sel = ("", -1)      # clip seleccionat (kind, index)
        self._multi: set = set()   # multi-selecció: {(kind, index), ...}
        self._clipboard: dict = {}  # buffer intern copiar/retallar (D.2)
        # Eina del timeline: «intel·ligent» (per defecte; la fletxa s'adapta al
        # que hi ha sota: mou, redimensiona, loop…) o «marc» (arrossegar dibuixa
        # un rectangle de selecció i NO mou clips, com el marquee dels DAWs).
        self._tool = "intel·ligent"
        # (El rang de Shift+clic és SEMPRE del carril del clip clicat: per agafar
        # clips de les dues pistes es fa servir el marquee, Ctrl+arrossegant.)
        self._marquee = None       # rectangle en curs: [x0,y0,x1,y1] de la vista
        # El rectangle ve d'un Ctrl+arrossegament TEMPORAL (no de l'eina «marc»):
        # si és minúscul (un clic) es resol com a toggle, i en deixar anar tot
        # torna a l'eina intel·ligent.
        self._marquee_ctrl = False
        # Alt+arrossegament en curs: (idx, t original) per deixar-hi la còpia.
        self._alt_copia = None
        # El mateix per a les SECCIONS: (ini, fi, lletra, família) originals.
        self._copia_sec = None
        # Moviment d'un BLOC d'acords en curs (PLA_EDICIO_LLIURE §6.3): dict
        # {first, last, idx, t0, dt, acords0}. El DESTÍ (tallar/eliminar) es
        # resol sencer al final del gest (`_tanca_bloc`), perquè pot esborrar
        # marques i cal reconstruir el timeline.
        self._bloc_gest = None
        self._loop_item = None     # banda de loop A/B
        self._loop_a = None
        self._loop_b = None
        self._loop_drag = False    # creant un loop nou (arrossegant el regle)
        # Manipulació del loop DES DEL REGLE: 'a'/'b' = moure una vora, 'move'
        # = desplaçar-lo sencer. (La banda del canvas no és interactiva.)
        self._loop_mode = None
        self._loop_a0 = None       # A/B de partida de l'arrossegada
        self._loop_b0 = None
        self._loop_t0 = None       # temps on va començar (per a 'move')

        # escena
        self._scene = QGraphicsScene(self)
        self._scene.setBackgroundBrush(QBrush(QColor(theme.TL_SCENE_BG)))
        self.setScene(self._scene)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        # FullViewportUpdate: evita imatges fantasma amb els carrils
        # semitransparents sobreposats (l'escena és petita: cost negligible).
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setContextMenuPolicy(Qt.NoContextMenu)  # botó dret = pan

        # fons subtils dels 2 carrils (sobreposats a l'ona)
        self._bg_chord = LaneBackground(0, LANE_ACC_TOP, 1, LANE_H,
                                        LANE_BG_A, parent=None)
        self._bg_chord.setOpacity(0.18)
        self._bg_section = LaneBackground(0, LANE_SEC_TOP, 1, LANE_H,
                                          LANE_BG_B, parent=None)
        self._bg_section.setOpacity(0.18)
        for bg in (self._bg_chord, self._bg_section):
            self._scene.addItem(bg)

        # ona (envolupant plena) — a sota de tot
        samples = audio.get("mono")
        if samples is None or len(samples) == 0:
            samples = np.zeros(1024, dtype=np.int16)
        sr = int(audio.get("sr", 44100))
        self._waveform = WaveformLayer(samples, sr, WAVEFORM_H, self._pps,
                                       self._x_offset, RULER_H)
        self._scene.addItem(self._waveform)

        # graella (línies verticals sobre l'ona)
        self._grid = GridLayer(WAVEFORM_H, self._pps, self._x_offset,
                               self._view_left, self._view_right,
                               self._tempo_fix, self._bpm, self._bpb, RULER_H)
        self._scene.addItem(self._grid)

        # regle de temps (a dalt)
        self._ruler = RulerLayer(1, RULER_H, self._pps, self._x_offset,
                                 self._view_left, self._view_right,
                                 self._tempo_fix, self._bpm, self._bpb, top=0)
        self._scene.addItem(self._ruler)

        # pista de TEMPO i COMPÀS (blocs; només amb mapa variable)
        self._tempo_lane = TempoLayer(LANE_TEMPO_H, self._pps,
                                      self._x_offset, self._view_left,
                                      self._view_right, LANE_TEMPO_TOP)
        self._scene.addItem(self._tempo_lane)
        self._tempo_lane.tramClicked.connect(self.tempoEditRequested.emit)
        self._tempo_lane.tramMoved.connect(self.tempoChangeMoved.emit)
        self._tempo_lane.menuRequested.connect(self.tempoMenuRequested.emit)

        # cursor
        self._cursor = CursorLine(0, TOTAL_H - 2)
        self._scene.addItem(self._cursor)

        # items inicials
        self._rebuild_chord_items()
        self._rebuild_section_items()

        # mida inicial de l'escena (es força des de resizeEvent)
        self._total_h = TOTAL_H
        self._scene.setSceneRect(0, 0, 1, self._total_h)
        self.setMinimumHeight(self._total_h + 4)

        self._zoom_full()

    # -- API pública ----------------------------------------------------------
    def set_data(self, acords: Sequence, seccions: Sequence) -> None:
        # El model d'acords són **clips** (S4). Acceptem també **marques**
        # `(t, nom[, tsrc])` (pont per a crides directes/tests): s'hi deriva el fi.
        self._acords = _acords_a_clips(acords, self._durada)
        self._seccions = list(seccions) or []
        # Els índexs canvien amb les dades noves: la multi-selecció antiga
        # queda òrfena, per tant la buidem (els items es reconstrueixen).
        self._multi = set()
        self._sel = ("", -1)
        self._bloc_gest = None      # el gest de moviment no sobreviu a un re-render
        self._rebuild_chord_items()
        self._rebuild_section_items()

    def set_tempo_mode(self, tempo_fix: bool, bpm: float, bpb: int,
                       offset: float = 0.0, beat_type: int = 4,
                       mapa=None) -> None:
        self._tempo_fix = bool(tempo_fix)
        self._bpm = float(bpm)
        self._bpb = int(bpb)
        self._beat_type = int(beat_type or 4)
        self._offset = float(offset)
        self._mapa = mapa
        self._ruler.update_mode(self._tempo_fix, self._bpm, self._bpb,
                                self._offset, self._beat_type, mapa)
        self._grid.update_mode(self._tempo_fix, self._bpm, self._bpb,
                               self._offset, self._beat_type, mapa)
        self._tempo_lane.set_mapa(mapa, self._tempo_fix)
        self.update()

    def set_follow(self, enabled: bool) -> None:
        """Activa/desactiva el seguiment del cursor durant la reproducció."""
        self._follow = bool(enabled)

    def _follow_cursor(self, t: float) -> None:
        """Si el cursor surt de la zona còmoda (o va endavant), desplaça la
        vista perquè quedi a ~15% de l'esquerra (estil DAW)."""
        span = self._view_right - self._view_left
        if span <= 0:
            return
        frac = (t - self._view_left) / span
        if 0.0 <= frac <= 0.85:
            return
        new_l = max(0.0, t - span * 0.15)
        new_r = min(self._durada, new_l + span)
        if new_r - new_l < span:
            new_l = max(0.0, new_r - span)
            new_r = new_l + span
        self._set_view_range(new_l, new_r)

    def set_position(self, t: float, emit: bool = True, snap=None) -> None:
        t = float(t)
        # Amb el snap actiu, el cursor SEGUEIX la graella (com un DAW). Els
        # camins de reproducció/alineació del loop hi passen `snap=False`.
        if snap is None:
            snap = self._snap_on
        if snap:
            t = self._snap(t)
        t = max(0.0, min(t, self._durada))
        self._pos_t = t
        self._cursor.set_time(t, self._pps, self._x_offset, self._view_left)
        self._highlight_active(t)
        if self._follow:
            self._follow_cursor(t)
        if emit:
            self.positionChanged.emit(t)

    def zoom_in(self) -> None:
        self._zoom_at(0.5)

    def zoom_out(self) -> None:
        self._zoom_at(2.0)

    def zoom_full(self) -> None:
        self._zoom_full()

    def zoom_to(self, left: float, right: float) -> None:
        self._set_view_range(max(0.0, left), min(self._durada, right))

    # -- mètodes interns ------------------------------------------------------
    def _zoom_at(self, factor: float) -> None:
        l, r = self._view_left, self._view_right
        ampl = max((r - l) * factor, 0.3)
        centre = self.selected_center()
        if centre is None:
            centre = self._pos_t
        self._center_on(centre, ampl)

    def _zoom_full(self) -> None:
        self._set_view_range(0.0, max(self._durada, 0.5))

    def _set_view_range(self, left: float, right: float) -> None:
        if right <= left:
            right = left + 0.5
        self._view_left = max(0.0, left)
        self._view_right = min(self._durada, right)
        # pps = ample de la viewport en pixels / (right - left)
        w = max(1, self.viewport().width() - LEFT_PAD - RIGHT_PAD)
        self._pps = max(1.0, w / (self._view_right - self._view_left))
        # actualitza items
        self._ruler.update_geometry(self._pps, self._x_offset,
                                    self._view_left, self._view_right)
        self._grid.update_geometry(self._pps, self._x_offset,
                                   self._view_left, self._view_right)
        self._waveform.update_geometry(self._pps, self._x_offset,
                                       self._view_left, self._view_right)
        self._tempo_lane.update_geometry(self._pps, self._x_offset,
                                         self._view_left, self._view_right)
        for it in self._chord_items:
            it.set_pps(self._pps, self._x_offset, self._view_left)
        for it in self._section_items:
            it.set_pps(self._pps, self._x_offset, self._view_left)
        # El cursor manté el TEMPS (no la x) en fer zoom/pan
        self._cursor.set_time(self._pos_t, self._pps, self._x_offset,
                              self._view_left)
        self._update_loop_item()
        # L'escena = mida de la viewport (no hi ha scroll del QGraphicsView:
        # tot es dibuixa en coords relatives a la vista)
        wv = max(200, self.viewport().width())
        self._scene.setSceneRect(0, 0, wv, self._total_h)
        self._update_guide_line()

    def _update_guide_line(self) -> None:
        if self._guide_line is None:
            self._guide_line = QGraphicsLineItem()
            pen = QPen(QColor(GUIDE_COLOR), 1, Qt.DashLine)
            self._guide_line.setPen(pen)
            self._guide_line.setZValue(40)
            self._scene.addItem(self._guide_line)
        # amaga'l per defecte
        line = self._guide_line.line()
        line.setP1(QPointF(-10000, 0))
        line.setP2(QPointF(-10000, 0))
        self._guide_line.setLine(line)
        self._guide_line.setVisible(False)

    def _show_guide_at(self, t: float) -> None:
        if self._guide_line is None:
            self._update_guide_line()
        x = self._x_offset + (t - self._view_left) * self._pps
        line = self._guide_line.line()
        line.setP1(QPointF(x, 0))
        line.setP2(QPointF(x, self._total_h))
        self._guide_line.setLine(line)
        self._guide_line.setVisible(True)

    def _hide_guide(self) -> None:
        if self._guide_line is not None:
            self._guide_line.setVisible(False)

    def _rebuild_chord_items(self) -> None:
        for it in self._chord_items:
            self._scene.removeItem(it)
        self._chord_items.clear()
        self._chord_by_idx.clear()
        n = len(self._acords)
        for i in range(n):
            _c = self._acords[i]
            t, name = _c[0], pipeline.nom_d_acord(_c)
            next_t = self._acords[i + 1][0] if i + 1 < n else self._durada
            item = ChordItem(i, float(t), str(name), float(next_t),
                             self._pps, self._x_offset,
                             LANE_ACC_TOP, LANE_H)
            item.timeChanged.connect(
                lambda nt, idx=i: self._on_chord_time_changed(idx, nt))
            item.endTimeChanged.connect(
                lambda nt, idx=i: self._on_chord_end_changed(idx, nt))
            item.clicked.connect(
                lambda it=item: self._seek_to(
                    float(it.t), "chord", getattr(it, "idx", -1)))
            item.dragStarted.connect(self.editStarted.emit)
            item.dragFinished.connect(self._emit_edit_finished)
            item.editRequested.connect(
                lambda idx=i: self._on_chord_edit(idx))
            item.deleteRequested.connect(
                lambda idx=i: self.chordDeleteRequested.emit(idx))
            # FIX: el constructor fixa `view_left=0` → cal aplicar-hi la VISTA
            # ACTUAL, si no els items reconstruïts (undo/editar/renombrar/paste)
            # es pinten com si no hi hagués zoom i el clip «salta» fora de vista.
            item.set_pps(self._pps, self._x_offset, self._view_left)
            self._scene.addItem(item)
            self._chord_items.append(item)
            self._chord_by_idx[i] = item

    def _rebuild_section_items(self) -> None:
        for it in self._section_items:
            self._scene.removeItem(it)
        self._section_items.clear()
        self._section_by_idx.clear()
        for i, (ini, fi, lletra, familia) in enumerate(self._seccions):
            item = SectionItem(i, float(ini), float(fi), str(lletra),
                               str(familia), self._pps, self._x_offset,
                               LANE_SEC_TOP, LANE_H)
            item.timeChanged.connect(
                lambda ni, nf, idx=i: self._on_section_changed(idx, ni, nf))
            item.clicked.connect(
                lambda it=item: self._seek_to(
                    float(it.ini), "section", getattr(it, "idx", -1)))
            item.dragStarted.connect(self.editStarted.emit)
            item.dragFinished.connect(self._emit_edit_finished)
            item.editRequested.connect(
                lambda idx=i: self._on_section_edit(idx))
            item.deleteRequested.connect(
                lambda idx=i: self.sectionDeleteRequested.emit(idx))
            # (mateix FIX que als acords: la vista ACTUAL, no view_left=0)
            item.set_pps(self._pps, self._x_offset, self._view_left)
            self._scene.addItem(item)
            self._section_items.append(item)
            self._section_by_idx[i] = item

    def set_loop(self, a, b) -> None:
        """Fixa/neteja la banda de loop. a=b=None la treu."""
        if a is None or b is None:
            self._loop_a = self._loop_b = None
            self._update_loop_item()
            return
        """Defineix la regió de loop A/B (segons) i la dibuixa."""
        self._loop_a = float(a)
        self._loop_b = float(b)
        self._update_loop_item()

    def _update_loop_item(self) -> None:
        if (self._loop_a is None or self._loop_b is None
                or self._loop_b - self._loop_a <= 1e-9):
            if self._loop_item is not None:
                self._loop_item.setVisible(False)
            return
        if self._loop_item is None:
            self._loop_item = QGraphicsRectItem()
            # Taronja suau (abans groc #ffd166): mateix to que `theme.TL_GUIDE`.
            self._loop_item.setBrush(QBrush(QColor(255, 178, 107, 40)))
            self._loop_item.setPen(QPen(QColor(255, 178, 107, 200), 1))
            self._loop_item.setZValue(-3)
            self._scene.addItem(self._loop_item)
        x0 = self._x_offset + (self._loop_a - self._view_left) * self._pps
        x1 = self._x_offset + (self._loop_b - self._view_left) * self._pps
        self._loop_item.setRect(0, 0, max(1.0, x1 - x0), self._total_h)
        self._loop_item.setPos(x0, 0)
        self._loop_item.setVisible(True)

    def _loop_px(self, t: float) -> float:
        """Coordenada x d'escena per a un temps (per a la hit-test del loop)."""
        return self._x_offset + (t - self._view_left) * self._pps

    def _loop_mode_at(self, x: float):
        """Què farà un clic al regle segons l'x (o None = crear loop nou).

        'a'/'b' = vores (dins de ±LOOP_GRAB_PX) → redimensionar; 'move' = dins
        del loop → desplaçar-lo; None = fora → començar un loop nou.
        """
        if self._loop_a is None or self._loop_b is None:
            return None
        xa = self._loop_px(self._loop_a)
        xb = self._loop_px(self._loop_b)
        if abs(x - xa) <= LOOP_GRAB_PX:
            return "a"
        if abs(x - xb) <= LOOP_GRAB_PX:
            return "b"
        if xa < x < xb:
            return "move"
        return None

    def _cursor_regle(self, x: float):
        """Cursor de feedback sobre el regle (vores = ↔, cos = ✥)."""
        m = self._loop_mode_at(x)
        if m in ("a", "b"):
            return Qt.SizeHorCursor
        if m == "move":
            return Qt.SizeAllCursor
        return Qt.ArrowCursor

    def _emit_edit_finished(self) -> None:
        """Fi de drag -> amaga la guia i reporta.

        Si el gest era un **Alt+arrossegament** d'un acord, el clip s'ha mogut i
        ara cal deixar-ne una **còpia a l'origen** (Alt+drag = duplicar, la
        convenció dels DAWs). S'emet DESPRÉS de `editFinished` perquè el moviment
        ja estigui consolidat: així la còpia és una segona operació neta.
        """
        self._hide_guide()
        self._tanca_bloc()          # DESTÍ del moviment del bloc (§6.3)
        self.editFinished.emit()
        if self._alt_copia is not None:
            t0, nom = self._alt_copia
            self._alt_copia = None
            self.chordCopyRequested.emit(float(t0), str(nom))
        if self._copia_sec is not None:
            ini, fi, ll, fam = self._copia_sec
            self._copia_sec = None
            self.sectionCopyRequested.emit(float(ini), float(fi), str(ll),
                                           str(fam))

    def _x_to_time(self, x: float) -> float:
        """De x de la vista a temps (coords relatives a la vista)."""
        return self._view_left + (x - self._x_offset) / max(self._pps, 1e-9)

    def snap(self, t: float) -> float:
        """Arrodoneix `t` a la graella de snap actual (BPM/offset o segons)."""
        return self._snap(t)

    def marques_temps(self) -> List[float]:
        """Instants de les MARQUES del model (= vores de clip).

        Un acord és una marca d'inici; una secció té inici I final. Són els
        «events» o «edit points» de la terminologia dels DAWs.
        """
        marks = [float(a[0]) for a in self._acords]
        for s in self._seccions:
            marks.append(float(s[0]))
            marks.append(float(s[1]))
        return marks

    def snap_a_marca(self, t: float) -> Optional[float]:
        """Àncora d'edició: si `t` cau a prop d'una MARCA del model, torna
        l'instant EXACTE d'aquella marca; si no, `None`.

        És el snap als *events* dels DAWs professionals (Cubase `Snap Type:
        Events`, Reaper «snap media items/markers»). Cal perquè les marques del
        model VÉNEN DE L'ANÀLISI i no cauen a la graella musical: arrodonir-les
        a la graella les mou uns mil·lisegons i, en una edició que substitueix
        una regió, deixa la vora que s'havia de substituir a 2 ms de la nova i
        la validació (≥ 10 ms) rebutja l'operació sencera.

        La tolerància és en PÍXELS (depèn del zoom), com el «snap distance» del
        Reaper: a dins es veu clar, i a fora no s'hi enganxa res.
        """
        if not self._acords and not self._seccions:
            return None
        tol = SNAP_MARCA_PX / max(1.0, float(self._pps))
        millor, dist = None, None
        for m in self.marques_temps():
            d = abs(m - float(t))
            if d <= tol and (dist is None or d < dist):
                millor, dist = m, d
        return millor

    def _loop_x_to_time(self, x: float) -> float:
        """Temps del regle per a un x d'escena, amb SNAP a la graella.

        S'usa per a la selecció de loop A/B: el loop **sí** que fa snap (com
        els clips). El cursor/playhead continua sent lliure."""
        t = self._x_to_time(x)
        return max(0.0, min(self._durada, self.snap(t)))

    def selected_center(self) -> Optional[float]:
        """Centre temporal del clip seleccionat (o None)."""
        kind, idx = getattr(self, "_sel", ("", -1))
        if kind == "chord" and 0 <= idx < len(self._chord_items):
            it = self._chord_items[idx]
            return (it.t + it._next_t) / 2.0
        if kind == "section" and 0 <= idx < len(self._section_items):
            it = self._section_items[idx]
            return (it.ini + it.fi) / 2.0
        return None

    def rang_seleccio(self):
        """Rang temporal `(inici, fi)` de TOTS els clips seleccionats, o `None`.

        Serveix per al **«zoom a la selecció»**. Els acords usen `t`/`_next_t`;
        les seccions, `ini`/`fi`.
        """
        t0s, t1s = [], []
        for kind, idx in getattr(self, "_multi", set()):
            if kind == "chord" and 0 <= idx < len(self._chord_items):
                it = self._chord_items[idx]
                t0s.append(it.t)
                t1s.append(it._next_t)
            elif kind == "section" and 0 <= idx < len(self._section_items):
                it = self._section_items[idx]
                t0s.append(it.ini)
                t1s.append(it.fi)
        if not t0s:
            return None
        return (min(t0s), max(t1s))

    def zoom_selection(self) -> None:
        """Ajusta la vista perquè es vegi TOTA la selecció (amb un petit marge)."""
        r = self.rang_seleccio()
        if r is None:
            return
        lo, hi = r
        marge = max(0.5, (hi - lo) * 0.05)
        self._set_view_range(max(0.0, lo - marge), min(self._durada, hi + marge))

    def ensure_cursor_visible(self, landing: float = 0.15) -> None:
        """Desplaça la vista (pan) perquè el cursor vermell quedi visible,
        MANTENINT el ZOOM actual (no el canvia).

        Si el cursor ja és dins de la zona còmoda no fa res. Si se surt (com el
        seek des de les llistes: un salt lluny), desplaça la vista perquè hi
        entri pel ~`landing` des de l'esquerra (mateixa idea que el seguiment
        de la reproducció, `_follow_cursor`).
        """
        span = self._view_right - self._view_left
        if span <= 0:
            return
        frac = (self._pos_t - self._view_left) / span
        if 0.0 <= frac <= 0.85:
            return
        new_l = max(0.0, min(self._pos_t - span * landing,
                             max(0.0, self._durada - span)))
        self._set_view_range(new_l, new_l + span)

    def _center_on(self, centre: float, ampl: float) -> None:
        """Situa la vista centrada a `centre` amb amplada `ampl` (segons)."""
        ampl = max(ampl, 0.3)
        new_l = max(0.0, float(centre) - ampl / 2.0)
        new_r = min(self._durada, new_l + ampl)
        if new_r - new_l < ampl:
            new_l = max(0.0, new_r - ampl)
        self._set_view_range(new_l, new_r)

    def get_position(self) -> float:
        """Retorna el temps del cursor (marca vermella)."""
        return float(self._pos_t)

    def _seek_to(self, t: float, kind: str = "", index: int = -1) -> None:
        """Click a un clip → situa el cursor al seu inici i reporta selecció."""
        self.set_position(float(t), emit=True)
        if kind:
            self.select_clip(kind, index)
            self.clipSelected.emit(kind, index)

    def select_clip(self, kind: str, index: int) -> None:
        """Marca visualment el clip seleccionat (i desmarca la resta)."""
        self._sel = (kind, index) if kind else ("", -1)
        self._multi = {(kind, index)} if kind else set()
        self._sync_selection_visual()
        # Avisem els qui escolten (llistes, franja Editor...) tambe quan la
        # seleccio ve de fora (clic a la llista, menu, etc.), no nomes del
        # propi timeline.
        self.clipSelected.emit(kind, index)

    def _sync_selection_visual(self) -> None:
        """Pinta la vora de selecció a tots els items de `self._multi`."""
        for it in self._chord_items:
            it.set_selected(("chord", getattr(it, "idx", -1)) in self._multi)
        for it in self._section_items:
            it.set_selected(("section", getattr(it, "idx", -1)) in self._multi)

    def selected_keys(self) -> set:
        """Conjunt de (kind, idx) actualment seleccionats (multi-selecció)."""
        return set(self._multi)

    def clear_selection(self) -> None:
        """Buida la selecció (i ho notifica amb un clip buit)."""
        self._sel = ("", -1)
        self._multi = set()
        self._sync_selection_visual()
        self.clipSelected.emit("", -1)

    def select_multi(self, keys) -> None:
        """Fixa la multi-selecció a `keys` (conjunt de (kind, idx)).

        El fa servir el visor després d'enganxar, per deixar seleccionat el bloc
        enganxat."""
        self._multi = {(k, int(i)) for (k, i) in keys}
        self._sel = next(iter(sorted(self._multi)), ("", -1))
        self._sync_selection_visual()
        k, i = self._sel
        self.clipSelected.emit(k, i)

    def toggle_selection(self, kind: str, index: int) -> None:
        """Ctrl+clic: afegeix o treu el clip de la selecció múltiple."""
        key = (kind, index)
        if key in self._multi:
            self._multi.discard(key)
            self._sel = next(iter(self._multi), ("", -1))
        else:
            self._multi.add(key)
            self._sel = key
        self._sync_selection_visual()
        # Emetem sempre el nou `_sel` (no el clip clicat): si l'hem tret, la
        # franja Editor ha de mostrar el clip actiu que queda (o buidar-se).
        nkind, nidx = self._sel
        self.clipSelected.emit(nkind, nidx)

    def _temps_item(self, kind: str, idx: int):
        """Temps d'inici del clip (kind, idx), o `None` si no existeix."""
        if kind == "chord" and 0 <= idx < len(self._acords):
            return float(self._acords[idx][0])
        if kind == "section" and 0 <= idx < len(self._seccions):
            return float(self._seccions[idx][0])
        return None

    def extend_selection(self, kind: str, index: int) -> None:
        """Shift+clic: selecciona el RANG de clips entre l'àncora i el clicat.

        El rang es calcula per TEMPS (no per índex) i es queda SEMPRE al
        **carril del clip clicat**. Per agafar clips de les dues pistes de cop
        es fa servir el **marquee** (Ctrl+arrossegant, o l'eina «marc»).
        Sense àncora vàlida equival a una selecció simple.
        """
        akind, aidx = self._sel
        t_anc = self._temps_item(akind, aidx)
        t_clic = self._temps_item(kind, index)
        if t_anc is None or t_clic is None:
            self.select_clip(kind, index)
            return
        keys = self.keys_dins_rang(t_anc, t_clic)
        keys = {k for k in keys if k[0] == kind}
        if not keys:
            keys = {(kind, index)}
        self._multi = keys
        self._sel = (kind, index)
        self._sync_selection_visual()
        self.clipSelected.emit(kind, index)

    def keys_dins_rang(self, lo: float, hi: float, inclou_fi: bool = True) -> set:
        """Clips (acords i seccions) l'INICI dels quals cau dins `[lo, hi]`.

        Rang per TEMPS que abraça les dues pistes (Shift+clic i loop A/B).

        `inclou_fi=False` → interval **semi-obert** `[lo, hi)`: un clip que
        comenci EXACTAMENT a `hi` NO s'hi compta. És el que vol el loop (acaba
        a `hi`; el clip d'allà ja és fora); el Shift+clic, en canvi, ha
        d'incloure el clip clicat → `inclou_fi=True` (per defecte).
        """
        lo, hi = sorted((float(lo), float(hi)))
        tol = 1e-6            # «mateix instant» (la resolució del CSV és 10 ms)

        def _dins(t):
            if t < lo - tol:
                return False
            return (t <= hi + tol) if inclou_fi else (t < hi - tol)

        keys = set()
        for i, ac in enumerate(self._acords):
            if _dins(float(ac[0])):
                keys.add(("chord", i))
        for i, sec in enumerate(self._seccions):
            if _dins(float(sec[0])):
                keys.add(("section", i))
        return keys

    def keys_dins_marc(self, t0: float, t1: float, chords: bool = True,
                       sections: bool = True) -> set:
        """Clips que **SONEN** dins la finestra `[t0, t1]` (marquee/rubber-band).

        A diferència de `keys_dins_rang` (que mira els INICIS dels clips), aquí
        mana el **SOLAPAMENT**: un clip que comença abans de `t0` però hi sona a
        dins també hi entra — és el que fa el marquee dels DAWs.

        `chords`/`sections` decideixen quines pistes participen: el rectangle
        només agafa les pistes que cobreix verticalment, i així un marc només
        damunt dels acords agafa **només acords**.
        """
        t0, t1 = sorted((float(t0), float(t1)))
        durada = float(self._durada)
        tol = 1e-6
        keys = set()
        if chords:
            for i, a in enumerate(self._acords):
                ini = float(a[0])
                fi = (float(self._acords[i + 1][0])
                      if i + 1 < len(self._acords) else durada)
                if fi > t0 + tol and ini < t1 - tol:
                    keys.add(("chord", i))
        if sections:
            for i, s in enumerate(self._seccions):
                ini, fi = float(s[0]), float(s[1])
                if fi > t0 + tol and ini < t1 - tol:
                    keys.add(("section", i))
        return keys

    # -- eina del timeline (fletxa intel·ligent / marc de selecció) -----------
    def set_tool(self, nom: str) -> None:
        """Eina del timeline: «intel·ligent» (per defecte) o «marc»."""
        n = str(nom or "").strip().lower()
        self._tool = "marc" if n.startswith("marc") else "intel·ligent"
        self._marquee = None
        self.viewport().setCursor(
            Qt.CrossCursor if self._tool == "marc" else Qt.ArrowCursor)
        self.viewport().update()

    def tool(self) -> str:
        """Eina vigent: «intel·ligent» o «marc»."""
        return self._tool

    def _inicia_marc(self, event, temporal: bool = False) -> None:
        """Comença el rectangle de selecció (eina «marc» o Ctrl+arrossegament)."""
        p = (event.position() if hasattr(event, "position") else event.pos())
        self._marquee = [float(p.x()), float(p.y()), float(p.x()), float(p.y())]
        self._marquee_ctrl = bool(
            temporal and (event.modifiers() & Qt.ControlModifier))
        self.viewport().update()

    def _marc_o_clic(self, x0, y0, x1, y1, ctrl: bool = False) -> None:
        """Tanca el rectangle: selecciona el que HI SONA a dins.

        Un arrossegament minúscul es tracta com un clic (mou el cursor i buida
        la selecció) perquè l'usuari no es quedi amb una selecció fantasma.
        """
        if abs(x1 - x0) < 3.0 and abs(y1 - y0) < 3.0:
            if ctrl:
                # Ctrl+CLIC (sense arrossegar) = afegir/treure de la selecció:
                # la via temporal no ha de trencar el toggle de sempre.
                it = self.itemAt(QPoint(int(x0), int(y0)))
                if isinstance(it, (ChordItem, SectionItem)):
                    kind = ("chord" if isinstance(it, ChordItem)
                            else "section")
                    self.toggle_selection(kind, getattr(it, "idx", -1))
                    return
            sp = self.mapToScene(QPoint(int(x0), int(y0)))
            t = max(0.0, min(self._durada, self._x_to_time(sp.x())))
            self.set_position(t)
            if self._multi:
                self.clear_selection()
            return
        p0 = self.mapToScene(QPoint(int(min(x0, x1)), int(min(y0, y1))))
        p1 = self.mapToScene(QPoint(int(max(x0, x1)), int(max(y0, y1))))
        t0, t1 = sorted((self._x_to_time(p0.x()), self._x_to_time(p1.x())))
        y0s, y1s = sorted((p0.y(), p1.y()))
        cobra_acc = (y1s > LANE_ACC_TOP) and (y0s < LANE_ACC_TOP + LANE_H)
        cobra_sec = (y1s > LANE_SEC_TOP) and (y0s < LANE_SEC_TOP + LANE_H)
        keys = self.keys_dins_marc(t0, t1, chords=cobra_acc, sections=cobra_sec)
        if not keys:
            self.clear_selection()
            return
        self._multi = set(keys)
        self._sel = next(iter(sorted(self._multi)), ("", -1))
        self._sync_selection_visual()
        k, i = self._sel
        self.clipSelected.emit(k, i)

    def drawForeground(self, painter, rect) -> None:
        """Rectangle del marquee: es veu NOMÉS mentre s'arrossega.

        En deixar anar el botó desapareix: el rectangle era una guia visual, la
        selecció queda feta als clips.
        """
        if self._marquee is None:
            return
        x0, y0, x1, y1 = self._marquee
        p0 = self.mapToScene(QPoint(int(min(x0, x1)), int(min(y0, y1))))
        p1 = self.mapToScene(QPoint(int(max(x0, x1)), int(max(y0, y1))))
        r = QRectF(p0, p1).normalized()
        pen = QPen(QColor(theme.TL_CURSOR))
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        farc = QColor(theme.TL_CURSOR)
        farc.setAlpha(48)
        painter.setBrush(QBrush(farc))
        painter.drawRect(r)

    # -- buffer intern copiar/retallar/enganxar (D.2.b) -----------------------
    def has_clipboard(self) -> bool:
        """Hi ha alguna cosa al buffer intern de copiar/enganxar?"""
        return bool(self._clipboard)

    def copy_selection(self) -> None:
        """Copia la selecció al buffer intern, relativa al clip més antic.

        Guarda, per carril, les llistes relatives **i la llargada del bloc**
        (`chord_len`/`section_len`), més `bloc_fi` (final de la selecció = inici
        del primer clip NO seleccionat, que és l'àncora per defecte si el cursor
        no s'ha mogut) i `cursor_copy`. Així l'enganxat pot **sobreescriure** una
        regió (regla d'or #4: la suma de clips ha de ser sempre la durada de la
        WAV; la cançó no pot créixer)."""
        keys = self.selected_keys()
        if not keys:
            return
        durada = float(self._durada)
        chords, chord_fis, sections = [], [], []
        for kind, idx in sorted(keys, key=lambda k: (k[0], k[1])):
            if kind == "chord" and 0 <= idx < len(self._acords):
                t = float(self._acords[idx][0])
                fi = (float(self._acords[idx + 1][0])
                      if idx + 1 < len(self._acords) else durada)
                chords.append((t, str(pipeline.nom_d_acord(self._acords[idx]))))
                chord_fis.append(fi)
            elif kind == "section" and 0 <= idx < len(self._seccions):
                ini, fi, lletra, fam = self._seccions[idx]
                sections.append((float(ini), float(fi), str(lletra), str(fam)))
        if not chords and not sections:
            return
        chords.sort(key=lambda x: x[0])
        sections.sort(key=lambda x: x[0])
        # Cada carril es normalitza al SEU propi inici: així, en una selecció
        # mixta, els dos blocs s'enganxen a partir del cursor sense deixar forats.
        inici_ac = chords[0][0] if chords else 0.0
        inici_sec = sections[0][0] if sections else 0.0
        inici = min([c[0] for c in chords] + [s[0] for s in sections])
        bloc_fi = max(chord_fis + [s[1] for s in sections])
        self._clipboard = {
            "offset": inici,
            "chords": [(t - inici_ac, name) for (t, name) in chords],
            "chord_len": (max(chord_fis) - inici_ac) if chord_fis else 0.0,
            "sections": [(ini - inici_sec, fi - inici_sec, ll, fam)
                         for (ini, fi, ll, fam) in sections],
            "section_len": ((max(s[1] for s in sections) - inici_sec)
                            if sections else 0.0),
            "bloc_fi": bloc_fi,
            "cursor_copy": float(self._pos_t),
        }
        # El cursor va al FINAL del bloc copiat (= inici del 1r clip NO
        # seleccionat) perquè «Enganxa» hi pega just a continuació.
        self.set_position(float(bloc_fi), snap=False)

    def _delete_selection(self) -> None:
        """Esborra la selecció (1 clip -> senyal individual; >1 -> batch)."""
        multi = self.selected_keys()
        if len(multi) > 1:
            self.multiDeleteRequested.emit(sorted(multi))
            return
        for items, sig in ((self._chord_items, self.chordDeleteRequested),
                           (self._section_items, self.sectionDeleteRequested)):
            for it in items:
                if getattr(it, "_selected", False):
                    sig.emit(getattr(it, "idx", -1))
                    return

    def cut_selection(self) -> None:
        """Retalla: copia al buffer intern i esborra la selecció."""
        self.copy_selection()
        self._delete_selection()

    def paste_at_cursor(self) -> None:
        """Enganxa el buffer intern al cursor (la inserció la fa el visor)."""
        if not self._clipboard:
            return
        self.pasteRequested.emit(dict(self._clipboard), float(self._pos_t))

    # -- gestió d'events dels items (constraint + propagació) -----------------
    def _bloc_del_gest(self, idx: int, kind: str = "chord"):
        """Bloc **consecutiu** de clips del tipus `kind` que arrossega el gest.

        El gest mou el cos d'un clip; si forma part d'una multi-selecció
        contigua del seu tipus, el bloc és tot el que queda a cada banda
        (mateixa durada, §6.3). Els índexs llunyans o trencats no entren al bloc
        (només la correguda que conté `idx`)."""
        sel = sorted(i for (k, i) in self._multi if k == kind)
        if idx not in sel:
            return idx, idx
        first = idx
        while first - 1 in sel:
            first -= 1
        last = idx
        while last + 1 in sel:
            last += 1
        return first, last

    def _on_chord_body_drag(self, idx: int, new_t: float) -> None:
        """Arrossegar el COS d'un clip d'acord = moure el BLOC (§6.3).

        El destí pot **tallar/eliminar** marques de sota i, per tant, l'operació
        es resol SENCERA al final del gest (`_tanca_bloc`). Mentre dura el gest
        només es mostra un **avançament visual**: NO es toca el MODEL (`_acords`),
        perquè reconstruir els items des de dins de l'event de l'item que
        s'arrossega és invàlid (i perquè el bloc pot canviar de nombre de
        marques)."""
        item = self._chord_items[idx]
        g = self._bloc_gest
        if g is None or g.get("idx") != idx:
            first, last = self._bloc_del_gest(idx)
            g = {
                "first": first, "last": last, "idx": idx,
                "t0": float(self._acords[idx][0]),
                "dt": 0.0,
                "acords0": list(self._acords),
            }
            self._bloc_gest = g
        t0 = float(getattr(item, "_drag_t0", g["t0"]))
        a0 = float(g["acords0"][g["first"]][0])
        b0 = (float(g["acords0"][g["last"] + 1][0])
              if g["last"] + 1 < len(g["acords0"]) else self._durada)
        dt = self._snap(new_t) - t0
        dt = max(-a0, min(self._durada - b0, dt))
        g["dt"] = dt
        a2, b2 = a0 + dt, b0 + dt
        for i in range(g["first"], g["last"] + 1):
            self._chord_items[i].set_time(float(g["acords0"][i][0]) + dt)
        if g["last"] + 1 < len(self._chord_items):
            self._chord_items[g["last"]].set_next_t(b2)
        if g["first"] - 1 >= 0:
            self._chord_items[g["first"] - 1].set_next_t(a2)
        self._show_guide_at(a2)

    def _on_section_body_drag(self, idx: int, new_ini: float,
                              new_fi: float) -> None:
        """Arrossegar el COS d'una secció = moure el BLOC (§6.3, paritat #11).

        Mirall de `_on_chord_body_drag`: el DESTÍ es resol al final del gest
        (`_tanca_bloc`), que pot tallar/eliminar seccions i fer forats («-»)."""
        g = self._bloc_gest
        if (g is None or g.get("kind") != "section"
                or g.get("idx") != idx):
            first, last = self._bloc_del_gest(idx, "section")
            g = {"kind": "section", "first": first, "last": last, "idx": idx,
                 "t0": float(self._seccions[idx][0]), "dt": 0.0,
                 "items0": [tuple(s) for s in self._seccions]}
            self._bloc_gest = g
        a0 = float(g["items0"][g["first"]][0])
        b0 = float(g["items0"][g["last"]][1])
        dt = self._snap(new_ini) - float(g["items0"][idx][0])
        dt = max(-a0, min(self._durada - b0, dt))
        g["dt"] = dt
        for i in range(g["first"], g["last"] + 1):
            s = g["items0"][i]
            self._section_items[i].set_ini(float(s[0]) + dt)
            self._section_items[i].set_fi(float(s[1]) + dt)
        self._show_guide_at(a0 + dt)

    def _tanca_bloc(self) -> None:
        """Resol el DESTÍ del moviment del bloc en acabar el gest (§6.3).

        Val per a **acords** i **seccions** (paritat d'edició #11). Fixa el
        model (`mou_bloc_acords` / `mou_bloc_seccions`) sense tocar els items: el
        re-render es fa després, fora de l'event de l'item que s'acaba de deixar
        anar. El Visor llegirà el model ja resolt a `editFinished`."""
        g = self._bloc_gest
        self._bloc_gest = None
        if not g:
            return
        if abs(float(g.get("dt", 0.0))) < 1e-9:
            return
        canviat = False
        if g.get("kind") == "section":
            nou = pipeline.mou_bloc_seccions(
                g["items0"], g["first"], g["last"], g["dt"], self._durada)
            if nou != [tuple(s) for s in self._seccions]:
                self._seccions = [tuple(s) for s in nou]
                canviat = True
        else:
            nou = pipeline.mou_bloc_clips(g["acords0"], g["first"], g["last"],
                                          g["dt"], self._durada,
                                          pipeline.FORAT_ACORD)
            if nou != list(self._acords):
                self._acords = list(nou)
                canviat = True
        if canviat:
            # El re-render (set_data reconstrueix items) es fa al següent cicle
            # de l'esdeveniment: estem dins del release de l'item que s'ha
            # deixat anar i esborrar-lo aquí mateix no és segur.
            QTimer.singleShot(0, self._refresca_items)

    def _refresca_items(self) -> None:
        """Re-render del timeline amb el MODEL actual (items reconstruïts)."""
        dades_a = list(self._acords)
        dades_s = list(self._seccions)
        try:
            self.set_data(dades_a, dades_s)
        except RuntimeError:
            # L'escena ja s'ha destruït (el visor s'ha tancat entre el gest i el
            # `QTimer.singleShot`): no hi ha res a repintar.
            return

    def _on_chord_time_changed(self, idx: int, new_t: float) -> None:
        """Mou l'inici de l'acord idx a new_t (amb snap + constraint)."""
        if idx < 0 or idx >= len(self._acords):
            return
        # Arrossegar per DUPLICAR: capturem l'instant ORIGINAL (abans del
        # primer moviment). El `_emit_edit_finished` deixarà la còpia allà.
        # Només **Ctrl+Shift**: és l'única combinació lliure als 3 sistemes
        # (a Linux el gestor de finestres s'emporta Alt —MATE— i Super —GNOME—).
        mods = QApplication.keyboardModifiers()
        if self._alt_copia is None and (
                mods & Qt.ControlModifier and mods & Qt.ShiftModifier):
            self._alt_copia = (float(self._acords[idx][0]),
                               str(pipeline.nom_d_acord(self._acords[idx])))
        # MOVIMENT d'un bloc (arrossegar el cos): §6.3. El gest de DUPLICAR
        # (Ctrl+Shift) encara va pel camí antic (es reubicarà a la fase 4).
        if (self._alt_copia is None
                and getattr(self._chord_items[idx], "_drag_mode", None)
                == ChordItem.ZONE_BODY):
            self._on_chord_body_drag(idx, new_t)
            return
        # El gest de DUPLICAR (Ctrl+Shift) encara va pel camí de GRUP antic
        # (es reubicarà a la fase 4 del pla); aquí es conserva tal qual.
        if (self._alt_copia is not None and len(self._multi) > 1
                and getattr(self._chord_items[idx], "_drag_mode", None)
                == ChordItem.ZONE_BODY):
            sel = sorted(i for (k, i) in self._multi if k == "chord")
            if len(sel) > 1 and idx in sel:
                self._move_chord_group(idx, sel, new_t)
                return
        old_t = float(self._acords[idx][0])
        # Vores LLIURES (§6.6): el tall/eliminació del veí el resol
        # `redimensiona_clips` (§6.3); només cal que el clip no quede buit.
        new_t_s = max(0.0, min(float(self._acords[idx].fi) - MIN_GAP_S,
                               self._durada, self._snap(new_t)))
        if abs(new_t_s - old_t) < 1e-9:
            return
        self._show_guide_at(new_t_s)
        n_abans = len(self._acords)
        self._acords = list(pipeline.redimensiona_clips(
            self._acords, idx, "ini", new_t_s, self._durada,
            pipeline.FORAT_ACORD))
        if len(self._acords) != n_abans:      # ha tallat/eliminat un veí
            QTimer.singleShot(0, self._refresca_items)
        else:
            self._chord_items[idx].set_time(new_t_s)
            if idx - 1 >= 0:
                self._chord_items[idx - 1].set_next_t(new_t_s)
        self.chordTimeMoved.emit(idx, new_t_s)

    def _on_chord_end_changed(self, idx: int, new_next_t: float) -> None:
        """Mou el final de l'acord idx (= inici del següent) a new_next_t."""
        if idx < 0 or idx >= len(self._acords):
            return
        # En un moviment de BLOC (cos) ho resol `_on_chord_body_drag` +
        # `_tanca_bloc`; aquí no s'ha de moure res.
        if (self._alt_copia is None
                and getattr(self._chord_items[idx], "_drag_mode", None)
                == ChordItem.ZONE_BODY):
            return
        old_t = float(self._acords[idx][0])
        # Vores LLIURES (§6.6): només cal no invertir ni sortir de la WAV; el
        # tall/eliminació del que hi ha a sota el resol `redimensiona_clips`.
        new_t_s = max(old_t + MIN_GAP_S,
                      min(self._durada, self._snap(new_next_t)))
        self._show_guide_at(new_t_s)
        if idx + 1 < len(self._acords):
            n_old_t = float(self._acords[idx + 1][0])
            if abs(new_t_s - n_old_t) < 1e-9:
                return
            n_abans = len(self._acords)
            self._acords = list(pipeline.redimensiona_clips(
                self._acords, idx, "fi", new_t_s, self._durada,
                pipeline.FORAT_ACORD))
            if len(self._acords) != n_abans:  # ha tallat/eliminat un veí
                QTimer.singleShot(0, self._refresca_items)
            else:
                self._chord_items[idx].set_next_t(new_t_s)
                self._chord_items[idx + 1].set_time(new_t_s)
            self.chordEndMoved.emit(idx, new_t_s)
        else:
            # no hi ha següent: el final és la durada total (no s'edita).
            pass

    def _move_chord_group(self, idx: int, sel: list, new_t: float) -> None:
        """Mou tots els acords de `sel` amb el mateix delta que el clip `idx`.

        El delta es calcula respecte la posició a l'inici del drag i es limita
        perquè cap acord seleccionat ultrapassi el veí NO seleccionat més
        proper (esquerra/dreta). Es recalcula l'amplada (next_t) de tot el
        carril perquè els clips contigus es tornin a pintar bé."""
        item = self._chord_items[idx]
        t0 = float(getattr(item, "_drag_t0", self._acords[idx][0]))
        t_snap = self._snap(new_t)
        dt = t_snap - t0
        selset = set(sel)
        dt_lo, dt_hi = -1e18, 1e18
        for i in sel:
            p = i - 1
            while p >= 0 and p in selset:
                p -= 1
            n = i + 1
            while n < len(self._acords) and n in selset:
                n += 1
            lo = (self._acords[p][0] if p >= 0 else 0.0) + MIN_GAP_S
            hi = (self._acords[n][0] if n < len(self._acords)
                  else self._durada) - MIN_GAP_S
            t_i = self._acords[i][0]
            dt_lo = max(dt_lo, lo - t_i)
            dt_hi = min(dt_hi, hi - t_i)
        dt = 0.0 if dt_lo > dt_hi else max(dt_lo, min(dt_hi, dt))
        for i in sel:
            t_i = self._acords[i][0] + dt
            self._acords[i] = pipeline.Clip(
                t_i, float(self._acords[i][1]), self._acords[i][2])
            self._chord_items[i].set_time(t_i)
        # re-sincronitza l'amplada (next_t = inici del següent) de tot el carril
        for i in range(len(self._acords)):
            nxt = (self._acords[i + 1][0] if i + 1 < len(self._acords)
                   else self._durada)
            self._chord_items[i].set_next_t(nxt)
        self._show_guide_at(self._acords[idx][0])
        self.chordTimeMoved.emit(idx, self._acords[idx][0])

    def _on_chord_edit(self, idx: int) -> None:
        """Doble-clic: obre el RenameEditor inline."""
        item = self._chord_by_idx.get(idx)
        if item is None:
            return
        self._open_rename(item, item.name, idx, "chord")

    def _on_section_changed(self, idx: int, new_ini: float,
                            new_fi: float) -> None:
        """Redimensiona/mou una secció amb la MATEIXA lògica que els acords.

        Regla d'or: el fi d'una secció és l'inici de la següent.
          - vora esquerra: mou l'inici (i el fi de l'anterior)
          - vora dreta:    mou el fi (= inici de la següent)
          - cos:           desplaça la secció sencera
        """
        if idx < 0 or idx >= len(self._seccions):
            return
        # Ctrl+Shift+arrossegar = duplicar: capturem la secció ORIGINAL (abans
        # del primer moviment). El `_emit_edit_finished` hi deixarà la còpia.
        mods = QApplication.keyboardModifiers()
        if self._copia_sec is None and (
                mods & Qt.ControlModifier and mods & Qt.ShiftModifier):
            s = self._seccions[idx]
            self._copia_sec = (float(s[0]), float(s[1]), str(s[2]), str(s[3]))
        # Moviment de BLOC de seccions: l'arrossega `_on_section_body_drag`
        # (paritat #11 amb els acords; abans ho feia `_move_section_group`).
        ini_o, fi_o, lletra, familia = self._seccions[idx]
        zone = self._section_items[idx]._drag_mode
        n = len(self._seccions)

        def prev_ini(i):
            return self._seccions[i - 1][0] if i - 1 >= 0 else 0.0

        def next_ini_of(i):
            return self._seccions[i + 1][0] if i + 1 < n else self._durada

        if zone == SectionItem.ZONE_RIGHT:
            # Mou el FI -> és l'inici de la següent (vora LLIURE, §6.6)
            nt = max(ini_o + MIN_SEC_LEN_S,
                     min(self._durada, self._snap(new_fi)))
            n_abans = len(self._seccions)
            self._seccions = [tuple(s) for s in pipeline.redimensiona_seccio(
                self._seccions, idx, "fi", nt, self._durada)]
            if len(self._seccions) != n_abans:
                QTimer.singleShot(0, self._refresca_items)
            else:
                self._section_items[idx].set_fi(nt)
                if idx + 1 < n:
                    self._section_items[idx + 1].set_ini(nt)
            self._show_guide_at(nt)
            self.sectionMoved.emit(idx, ini_o, nt)
            return

        if zone == SectionItem.ZONE_BODY:
            # Arrossegar el COS = moure el BLOC (paritat d'edició #11 amb els
            # acords): el gest es resol sencer al `release` (`_tanca_bloc`).
            self._on_section_body_drag(idx, new_ini, new_fi)
            return

        # LEFT / NONE: mou l'INICI (i el fi de l'anterior)

        # Vora LLIURE (§6.6): només límit [0, fi-MIN]; el veí el resol el nucli.
        nt = max(0.0, min(fi_o - MIN_SEC_LEN_S, self._snap(new_ini)))
        n_abans = len(self._seccions)
        self._seccions = [tuple(s) for s in pipeline.redimensiona_seccio(
            self._seccions, idx, "ini", nt, self._durada)]
        if len(self._seccions) != n_abans:
            QTimer.singleShot(0, self._refresca_items)
        else:
            self._section_items[idx].set_ini(nt)
            if idx - 1 >= 0:
                self._section_items[idx - 1].set_fi(nt)
        self._show_guide_at(nt)
        self.sectionMoved.emit(idx, nt, fi_o)

    def _on_section_edit(self, idx: int) -> None:
        item = self._section_by_idx.get(idx)
        if item is None:
            return
        self._open_rename(item, item.lletra, idx, "section")

    def _open_rename(self, item: QGraphicsItem, initial: str, idx: int,
                    kind: str) -> None:
        # Calculem el centre de l'item en coordenades de viewport → finestra
        rect = item.boundingRect()
        scene_center = QPointF(rect.center().x(), rect.center().y())
        viewport_pt = self.mapFromScene(scene_center)
        global_pt = self.viewport().mapToGlobal(
            QPoint(viewport_pt.x(), viewport_pt.y()))
        editor = RenameEditor(
            self, initial,
            on_commit=lambda text: self._commit_rename(kind, idx, item, text),
            on_cancel=lambda: None,
            width=int(max(120, rect.width())),
        )
        # centra el QLineEdit a sobre de l'item
        editor.move(global_pt.x() - editor.width() // 2,
                    global_pt.y() - editor.height() // 2)
        editor.show()
        editor.raise_()
        editor.setFocus()

    def _commit_rename(self, kind: str, idx: int, item: QGraphicsItem,
                       text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        if kind == "chord":
            _c = self._acords[idx]
            self._acords[idx] = pipeline.Clip(
                float(_c[0]), float(_c[1]), (text,) + tuple(_c[2][1:]))
            item.name = text
            item.update()
            self.chordRenamed.emit(idx, text)
        else:
            ini, fi, _ll, fam = self._seccions[idx]
            self._seccions[idx] = (ini, fi, text, fam or text)
            item.lletra = text
            item.update()
            self.sectionRenamed.emit(idx, text, fam or text)

    # -- highlight de l'acord/secció activa -----------------------------------
    def _highlight_active(self, t: float) -> None:
        # acords: l'últim amb t <= t
        for it in self._chord_items:
            it.set_active(False)
        if self._chord_items:
            k = 0
            for i, (ta, *_r) in enumerate(self._acords):
                if ta <= t:
                    k = i
                else:
                    break
            if 0 <= k < len(self._chord_items):
                self._chord_items[k].set_active(True)
        # seccions
        for it in self._section_items:
            it.set_active(False)
        if self._section_items:
            for i, (ini, fi, *_r) in enumerate(self._seccions):
                if ini <= t < fi:
                    if 0 <= i < len(self._section_items):
                        self._section_items[i].set_active(True)
                    break

    # -- events de la vista ---------------------------------------------------
    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._set_view_range(self._view_left, self._view_right)

    def wheelEvent(self, event) -> None:
        """Roda = zoom centrat al cursor (mouse intel·ligent).
        Shift+roda = desplaçament horitzontal (pan)."""
        delta = event.angleDelta().y()
        if delta == 0:
            return
        if event.modifiers() & Qt.ShiftModifier:
            span = self._view_right - self._view_left
            dt = -delta / 120.0 * span * 0.1
            new_l = max(0.0, self._view_left + dt)
            new_r = min(self._durada, new_l + span)
            if new_r - new_l < span:
                new_l = max(0.0, new_r - span)
            self._set_view_range(new_l, new_r)
            event.accept()
            return
        # Si hi ha un clip seleccionat, centrem la vista al seu centre.
        # Si no, el zoom ha de quedar centrat al cursor vermell (playhead), no
        # al punt del ratolí.
        centre = self.selected_center()
        ampl = max((self._view_right - self._view_left) *
                   (0.85 if delta > 0 else (1.0 / 0.85)), 0.3)
        if centre is not None:
            self._center_on(centre, ampl)
            event.accept()
            return
        self._center_on(self._pos_t, ampl)
        event.accept()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.RightButton:
            # Si el botó dret cau SOBRE un clip -> menu contextual (i el
            # seleccionem). Si cau al buit -> pan, com sempre.
            it = self.itemAt(event.pos())
            if isinstance(it, TempoLayer):
                # Pista de BPM/compas: l'escena mostra el SEU menu.
                self.setFocus()
                super().mousePressEvent(event)
                event.accept()
                return
            if isinstance(it, (ChordItem, SectionItem)):
                kind = "chord" if isinstance(it, ChordItem) else "section"
                idx = getattr(it, "idx", -1)
                self.setFocus()
                self.select_clip(kind, idx)
                gp = event.globalPos() if hasattr(event, "globalPos") \
                    else self.mapToGlobal(event.pos())
                self.clipContextMenuRequested.emit(kind, idx, gp)
                event.accept()
                return
            # Botó dret DINS la banda del loop (i sense cap clip a sota) → menú
            # del loop (copiar/retallar/enganxar tot el que hi ha a dins).
            sp = self.mapToScene(event.pos())
            t = self._x_to_time(sp.x())
            if (self._loop_a is not None and self._loop_b is not None
                    and self._loop_a - 1e-9 <= t <= self._loop_b + 1e-9):
                gp = event.globalPos() if hasattr(event, "globalPos") \
                    else self.mapToGlobal(event.pos())
                self.loopContextMenuRequested.emit(gp)
                event.accept()
                return
            # Botó dret arrossegat = scroll horitzontal (pan)
            self._pan_drag = True
            self._pan_x0 = event.pos().x()
            self._pan_left0 = self._view_left
            self._pan_span0 = self._view_right - self._view_left
            self.viewport().setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        if event.button() == Qt.LeftButton:
            # Si hi ha un clip sota el cursor -> l'escena se n'encarrega
            # (drag / resize / selecció). Sense això, el drag mai arriba!
            self.setFocus()  # perquè Space arribi al timeline
            # Click al regle (a dalt) -> comença una selecció de loop A/B
            sp = self.mapToScene(event.pos())
            if sp.y() < RULER_H:
                # Al regle: vora del loop → redimensionar (A/B); dins → moure'l;
                # fora → crear-ne un de nou (com sempre).
                mode = self._loop_mode_at(sp.x())
                if mode is None:
                    t = self._loop_x_to_time(sp.x())
                    self._loop_drag = True
                    self._loop_a = t
                    self._loop_b = t
                    self._update_loop_item()
                else:
                    self._loop_mode = mode
                    self._loop_a0, self._loop_b0 = self._loop_a, self._loop_b
                    self._loop_t0 = self._loop_x_to_time(sp.x())
                event.accept()
                return
            # Ctrl+arrossegar = fer el MARC **temporalment** (a tot arreu de les
            # pistes). En deixar anar, tot torna a l'eina intel·ligent; i si el
            # gest és un clic (rectangle minúscul) es resol com a toggle.
            # (Ctrl+Shift té prioritat: és el d'DUPLICAR i va per un altre camí.)
            mods_ara = event.modifiers()
            if (mods_ara & Qt.ControlModifier
                    and not (mods_ara & Qt.ShiftModifier)):
                self.setFocus()
                self._inicia_marc(event, temporal=True)
                event.accept()
                return
            # Eina «marc»: el drag NO mou clips → dibuixa el rectangle de
            # selecció (rubber-band). Pot arrencar a qualsevol punt de les
            # pistes, també damunt d'un clip (com el marquee dels DAWs).
            if self._tool == "marc":
                p = (event.position() if hasattr(event, "position")
                     else event.pos())
                self._marquee = [float(p.x()), float(p.y()),
                                 float(p.x()), float(p.y())]
                self.viewport().update()
                self.setFocus()
                event.accept()
                return
            it = self.itemAt(event.pos())
            if isinstance(it, TempoLayer):
                # Pista de BPM/compas (eina intel·ligent): l'escena la gestiona.
                self.setFocus()
                super().mousePressEvent(event)
                return
            if isinstance(it, (ChordItem, SectionItem)):
                kind = "chord" if isinstance(it, ChordItem) else "section"
                idx = getattr(it, "idx", -1)
                mods = event.modifiers()
                # Aquí només hi arriben: Shift+clic (rang) i Ctrl+Shift
                # (duplicar arrossegant). El Ctrl sol ja s'ha resolt abans com a
                # MARC temporal, i el Ctrl+Shift cau a `super()` perquè l'item
                # iniciï l'arrossegament de la còpia.
                if mods & Qt.ControlModifier and mods & Qt.ShiftModifier:
                    self.setFocus()
                elif mods & Qt.ShiftModifier:
                    self.setFocus()
                    self.extend_selection(kind, idx)
                    event.accept()
                    return
                super().mousePressEvent(event)
                return
            # Click al fons -> mou el cursor i buida la selecció múltiple
            try:
                pos = event.position() if hasattr(event, "position") else event.pos()
                scene_pt = self.mapToScene(pos)
                t = max(0.0, min(self._durada, self._x_to_time(scene_pt.x())))
                self.set_position(t)
                if self._multi:
                    self.clear_selection()
                self._hide_guide()
                event.accept()
            except (TypeError, ValueError):
                super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        """Doble-clic DINS la banda del loop (i sense cap clip a sota) →
        selecciona TOT el que hi ha a dins (acords I seccions)."""
        if event.button() == Qt.LeftButton:
            it = self.itemAt(event.pos())
            if isinstance(it, TempoLayer):
                super().mouseDoubleClickEvent(event)
                return
            sp = self.mapToScene(event.pos())
            t = self._x_to_time(sp.x())
            dins = (self._loop_a is not None and self._loop_b is not None
                    and self._loop_a - 1e-9 <= t <= self._loop_b + 1e-9)
            if dins and not isinstance(it, (ChordItem, SectionItem)):
                self.setFocus()
                self.loopDoubleClicked.emit()
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if getattr(self, "_pan_drag", False):
            dx = event.pos().x() - self._pan_x0
            dt = -dx / max(self._pps, 1e-9)
            span = self._pan_span0
            max_l = max(0.0, self._durada - span)
            new_l = max(0.0, min(max_l, self._pan_left0 + dt))
            self._set_view_range(new_l, new_l + span)
            event.accept()
            return
        if self._marquee is not None:
            p = (event.position() if hasattr(event, "position")
                 else event.pos())
            self._marquee[2], self._marquee[3] = float(p.x()), float(p.y())
            self.viewport().update()
            event.accept()
            return
        if getattr(self, "_loop_drag", False):
            sp = self.mapToScene(event.pos())
            t = self._loop_x_to_time(sp.x())
            self._loop_a, self._loop_b = min(self._loop_a, t), max(self._loop_a, t)
            self._update_loop_item()
            event.accept()
            return
        if getattr(self, "_loop_mode", None):
            # Moure una vora ('a'/'b') o el loop sencer ('move'), amb snap.
            sp = self.mapToScene(event.pos())
            t = self._loop_x_to_time(sp.x())
            self._loop_a, self._loop_b = loop_after_drag(
                self._loop_mode, t, self._loop_t0, self._loop_a0,
                self._loop_b0, self._durada)
            self._update_loop_item()
            event.accept()
            return
        # Feedback de cursor sobre el regle (només si no arrosseguem res).
        if not (getattr(self, "_loop_drag", False)
                or getattr(self, "_pan_drag", False)):
            sp = self.mapToScene(event.pos())
            self.viewport().setCursor(
                self._cursor_regle(sp.x()) if sp.y() < RULER_H
                else Qt.ArrowCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._marquee is not None:
            x0, y0, x1, y1 = self._marquee
            ctrl = self._marquee_ctrl
            self._marquee = None          # el rectangle desapareix en deixar anar
            self._marquee_ctrl = False    # ...i tot torna a l'eina intel·ligent
            self.viewport().update()
            self._marc_o_clic(x0, y0, x1, y1, ctrl=ctrl)
            event.accept()
            return
        if event.button() == Qt.RightButton and getattr(self, "_pan_drag", False):
            self._pan_drag = False
            self.viewport().setCursor(Qt.ArrowCursor)
            event.accept()
            return
        if getattr(self, "_loop_mode", None):
            self._loop_mode = None
            self._loop_a0 = self._loop_b0 = self._loop_t0 = None
            if (self._loop_a is not None and self._loop_b is not None
                    and self._loop_b - self._loop_a > 1e-9):
                self.loopChanged.emit(self._loop_a, self._loop_b)
            event.accept()
            return
        if getattr(self, "_loop_drag", False):
            self._loop_drag = False
            if (self._loop_b is not None and self._loop_a is not None
                    and self._loop_b - self._loop_a > 0.1):
                self.loopChanged.emit(self._loop_a, self._loop_b)
            else:
                self._loop_a = self._loop_b = None
                self._update_loop_item()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def set_snap(self, on=None, divisio=None) -> None:
        """Configura el snap: `on` (interruptor) i `divisio` (nom de la graella)."""
        if on is not None:
            self._snap_on = bool(on)
        if divisio is not None:
            self._snap_div_nom = str(divisio)
        self.update()

    def _snap_step(self) -> float:
        """Pas de snap: la divisió triada (BPM·compàs) o la de zoom (auto)."""
        if self._snap_div_nom:
            s = graella.divisio_segons(self._snap_div_nom, self._bpm,
                                       self._tempo_fix, self._bpb)
            if s > 0:
                return s
        return snap_step(self._tempo_fix, self._bpm, self._bpb, self._pps,
                         mapa=getattr(self, "_mapa", None))

    def _snap(self, t: float) -> float:
        """Encaixa `t` a la graella (o el deixa tal qual si el snap és OFF)."""
        if not self._snap_on:
            return float(t)
        off = getattr(self, "_offset", 0.0)
        mapa = getattr(self, "_mapa", None)
        if mapa is not None and not mapa.es_constant():
            return snap_time(float(t), self._tempo_fix, self._bpm, self._bpb,
                             self._pps, off, mapa=mapa)
        step = self._snap_step()
        if step <= 0:
            return float(t)
        return round((float(t) - off) / step) * step + off

    def _pas_nudge(self) -> float:
        """Pas del nudge = la DIVISIÓ de graella vigent (la mateixa que el snap)."""
        step = self._snap_step()
        return step if step and step > 0 else 0.1

    def _nudge(self, direccio: int, estira: bool, pas: float) -> None:
        """Mou la frontera del clip seleccionat `pas` (nudge amb ←/→).

        - Per defecte: la **vora esquerra** (l'inici del clip). Per als acords és
          l'inici propi; per a les seccions, la frontera amb l'anterior (o sigui,
          el fi de la secció prèvia).
        - `estira=True` (Alt): la **vora dreta** (el fi = inici del següent).
        Una sola operació de desfer (editStarted/editFinished). Respecta les
        regles d'or (només mou una frontera → ordre i contigüitat intactes).
        """
        kind, idx = self._sel
        # Decideix si hi ha acció ABANS de marcar l'undo: si no, NO s'emet
        # editStarted (evitem deixar una marca d'undo penjada).
        if kind == "chord":
            if not (0 <= idx < len(self._acords)):
                return
            if estira and idx + 1 >= len(self._acords):
                return
        elif kind == "section":
            if not (0 <= idx < len(self._seccions)):
                return
            if not estira and idx <= 0:
                return
        else:
            return
        self.editStarted.emit()
        if kind == "chord":
            if estira:
                self._on_chord_end_changed(
                    idx, float(self._acords[idx + 1][0]) + direccio * pas)
            else:
                self._on_chord_time_changed(
                    idx, float(self._acords[idx][0]) + direccio * pas)
        elif estira:
            self._nudge_vora_seccio(
                idx, float(self._seccions[idx][1]) + direccio * pas)
        else:
            self._nudge_vora_seccio(
                idx - 1, float(self._seccions[idx - 1][1]) + direccio * pas)
        self._emit_edit_finished()

    def _nudge_vora_seccio(self, j: int, nou_fi: float) -> None:
        """Mou el FI de la secció `j` (= inici de la següent) amb la lògica de vora."""
        it = self._section_items[j]
        previ = getattr(it, "_drag_mode", SectionItem.ZONE_NONE)
        it._drag_mode = SectionItem.ZONE_RIGHT
        try:
            self._on_section_changed(j, float(self._seccions[j][0]), nou_fi)
        finally:
            it._drag_mode = previ

    def keyPressEvent(self, event) -> None:
        mods = event.modifiers()
        if event.key() == Qt.Key_Escape:
            # Esc: el resol el VISOR, per ordre — (1) el RANG en curs, (2) el
            # LOOP, (3) la SELECCIÓ. Si no es compleix cap, no fa res.
            self.escapePressed.emit()
            event.accept()
            return
        if event.key() == Qt.Key_Space:
            self.playRequested.emit()
            event.accept()
            return
        if (event.key() in (Qt.Key_Left, Qt.Key_Right) and self._sel[0]
                and not (mods & Qt.ControlModifier)):
            self._nudge(-1 if event.key() == Qt.Key_Left else 1,
                        bool(mods & Qt.AltModifier), self._pas_nudge())
            event.accept()
            return
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            # Esborra la selecció. Els items no reben tecles (no son
            # focusables), per tant ho gestionem aquí, que si tenim el focus.
            if self.selected_keys():
                self._delete_selection()
                event.accept()
                return
        if mods & Qt.ControlModifier:
            # Dreceres estàndard de DAW: copy/cut/paste (+ duplicar)
            if event.key() == Qt.Key_C:
                self.copy_selection()
                event.accept()
                return
            if event.key() == Qt.Key_X:
                self.cut_selection()
                event.accept()
                return
            if event.key() == Qt.Key_V:
                self.paste_at_cursor()
                event.accept()
                return
            if event.key() == Qt.Key_D:
                # Ctrl+D: duplica el clip seleccionat; amb multi-selecció,
                # duplica el GRUP sencer (el visor ho resol amb un sol undo).
                keys = self.selected_keys()
                if len(keys) > 1:
                    self.groupDuplicateRequested.emit(sorted(keys))
                    event.accept()
                    return
                for items, sig in ((self._chord_items,
                                    self.chordDuplicateRequested),
                                   (self._section_items,
                                    self.sectionDuplicateRequested)):
                    for it in items:
                        if getattr(it, "_selected", False):
                            sig.emit(getattr(it, "idx", -1))
                            event.accept()
                            return
        super().keyPressEvent(event)

    def leaveEvent(self, event) -> None:
        self._hide_guide()
        super().leaveEvent(event)