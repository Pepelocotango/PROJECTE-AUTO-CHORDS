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
from PyQt5.QtCore import QPoint, QPointF, Qt, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QPainter, QPen
from PyQt5.QtWidgets import (
    QGraphicsItem, QGraphicsLineItem, QGraphicsRectItem, QGraphicsScene,
    QGraphicsView, QWidget,
)

from app import theme      # noqa: E402  (paleta centralitzada)


# -----------------------------------------------------------------------------
# Base compartida (constants i utilitats de temps/snap)
# -----------------------------------------------------------------------------
# Extret a app/timeline_base.py per alleugerir aquest fitxer. Es re-exporten
# tots els noms per mantenir la compatibilitat (from app.timeline import ...).
from app.timeline_base import (   # noqa: E402,F401
    CHORD_ACTIVE_FILL, CURSOR_COLOR, GUIDE_COLOR, LANE_ACC_TOP, LANE_BG_A,
    LANE_BG_B, LANE_H, LANE_SEC_TOP, LEFT_PAD, MIN_GAP_S, MIN_SEC_LEN_S,
    PIXELS_PER_SECOND_DEFAULT, RIGHT_PAD, RULER_H, SELECTION_COLOR, TOTAL_H,
    WAVEFORM_H, fmt_pos, grid_levels, snap_time,
)


# -----------------------------------------------------------------------------
# Capes de fons (extretes a app/timeline_layers.py)
# -----------------------------------------------------------------------------
# Es re-exporten per mantenir la compatibilitat (from app.timeline import ...).
from app.timeline_layers import (   # noqa: E402,F401
    CursorLine, GridLayer, LaneBackground, RulerLayer, WaveformLayer,
)

# API pública del mòdul (inclou els re-exports per compatibilitat amb codi i
# tests que fan `from app.timeline import ...`). Amb __all__ explícit, els
# re-exports no es marquen com a imports no usats.
__all__ = [
    "TimelineView", "ChordItem", "SectionItem", "RenameEditor",
    "WaveformLayer", "GridLayer", "RulerLayer", "LaneBackground", "CursorLine",
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
    chordTimeMoved = pyqtSignal(int, float)
    chordEndMoved = pyqtSignal(int, float)
    chordRenamed = pyqtSignal(int, str)
    chordDeleteRequested = pyqtSignal(int)
    chordDuplicateRequested = pyqtSignal(int)
    chordEditRequested = pyqtSignal(int)
    sectionMoved = pyqtSignal(int, float, float)
    sectionRenamed = pyqtSignal(int, str, str)
    sectionDeleteRequested = pyqtSignal(int)
    sectionDuplicateRequested = pyqtSignal(int)
    clipContextMenuRequested = pyqtSignal(str, int, QPoint)  # (kind, idx, pos)
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
        self._acords = list(acords) or []
        self._seccions = list(seccions) or []
        self._chord_items: List[ChordItem] = []
        self._section_items: List[SectionItem] = []
        self._chord_by_idx: dict = {}
        self._section_by_idx: dict = {}
        self._guide_line: Optional[QGraphicsLineItem] = None
        self._pos_t = 0.0          # temps del cursor (font de veritat)
        self._follow = False       # seguir el cursor durant el play
        self._sel = ("", -1)      # clip seleccionat (kind, index)
        self._multi: set = set()   # multi-selecció: {(kind, index), ...}
        self._clipboard: dict = {}  # buffer intern copiar/retallar (D.2)
        self._loop_item = None     # banda de loop A/B
        self._loop_a = None
        self._loop_b = None
        self._loop_drag = False

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
        self._acords = list(acords) or []
        self._seccions = list(seccions) or []
        # Els índexs canvien amb les dades noves: la multi-selecció antiga
        # queda òrfena, per tant la buidem (els items es reconstrueixen).
        self._multi = set()
        self._sel = ("", -1)
        self._rebuild_chord_items()
        self._rebuild_section_items()

    def set_tempo_mode(self, tempo_fix: bool, bpm: float, bpb: int,
                       offset: float = 0.0, beat_type: int = 4) -> None:
        self._tempo_fix = bool(tempo_fix)
        self._bpm = float(bpm)
        self._bpb = int(bpb)
        self._beat_type = int(beat_type or 4)
        self._offset = float(offset)
        self._ruler.update_mode(self._tempo_fix, self._bpm, self._bpb,
                                self._offset, self._beat_type)
        self._grid.update_mode(self._tempo_fix, self._bpm, self._bpb,
                               self._offset, self._beat_type)
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

    def set_position(self, t: float, emit: bool = True) -> None:
        t = max(0.0, min(float(t), self._durada))
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
        for i, (t, name, *_r) in enumerate(self._acords):
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
            self._loop_item.setBrush(QBrush(QColor(255, 209, 102, 40)))
            self._loop_item.setPen(QPen(QColor(255, 209, 102, 200), 1))
            self._loop_item.setZValue(-3)
            self._scene.addItem(self._loop_item)
        x0 = self._x_offset + (self._loop_a - self._view_left) * self._pps
        x1 = self._x_offset + (self._loop_b - self._view_left) * self._pps
        self._loop_item.setRect(0, 0, max(1.0, x1 - x0), self._total_h)
        self._loop_item.setPos(x0, 0)
        self._loop_item.setVisible(True)

    def _emit_edit_finished(self) -> None:
        """Fi de drag -> amaga la guia i reporta."""
        self._hide_guide()
        self.editFinished.emit()

    def _x_to_time(self, x: float) -> float:
        """De x de la vista a temps (coords relatives a la vista)."""
        return self._view_left + (x - self._x_offset) / max(self._pps, 1e-9)

    def snap(self, t: float) -> float:
        """Arrodoneix `t` a la graella de snap actual (BPM/offset o segons)."""
        return snap_time(t, self._tempo_fix, self._bpm, self._bpb, self._pps,
                         getattr(self, "_offset", 0.0))

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

    def extend_selection(self, kind: str, index: int) -> None:
        """Shift+clic: selecciona el rang entre l'àncora i el clip clicat.

        L'àncora és el darrer clip seleccionat (`self._sel`) i el rang només
        s'aplica dins del mateix carril (acords o seccions). Sense ànora,
        equival a una selecció simple."""
        akind, aidx = self._sel
        if akind != kind or aidx < 0:
            self.select_clip(kind, index)
            return
        lo, hi = sorted((aidx, index))
        self._multi = {(kind, i) for i in range(lo, hi + 1)}
        self._sel = (kind, index)
        self._sync_selection_visual()
        self.clipSelected.emit(kind, index)

    # -- buffer intern copiar/retallar/enganxar (D.2.b) -----------------------
    def has_clipboard(self) -> bool:
        """Hi ha alguna cosa al buffer intern de copiar/enganxar?"""
        return bool(self._clipboard)

    def copy_selection(self) -> None:
        """Copia la selecció al buffer intern, relativa al clip més antic.

        Els acords es guarden com (t_relatiu, nom) i les seccions com
        (ini_rel, fi_rel, lletra, família); `offset` és el temps absolut més
        antic per poder enganxar la peça sencera amb un sol desplaçament."""
        keys = self.selected_keys()
        if not keys:
            return
        chords, sections = [], []
        for kind, idx in keys:
            if kind == "chord" and 0 <= idx < len(self._acords):
                chords.append((float(self._acords[idx][0]),
                               str(self._acords[idx][1])))
            elif kind == "section" and 0 <= idx < len(self._seccions):
                ini, fi, lletra, fam = self._seccions[idx]
                sections.append((float(ini), float(fi), str(lletra), str(fam)))
        if not chords and not sections:
            return
        chords.sort(key=lambda x: x[0])
        sections.sort(key=lambda x: x[0])
        t0 = min([c[0] for c in chords] + [s[0] for s in sections])
        self._clipboard = {
            "offset": t0,
            "chords": [(t - t0, name) for (t, name) in chords],
            "sections": [(ini - t0, fi - t0, ll, fam)
                         for (ini, fi, ll, fam) in sections],
        }

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
    def _on_chord_time_changed(self, idx: int, new_t: float) -> None:
        """Mou l'inici de l'acord idx a new_t (amb snap + constraint)."""
        if idx < 0 or idx >= len(self._acords):
            return
        # Moviment de GRUP: si l'acord arrossegat (pel cos) forma part d'una
        # multi-selecció d'acords, movem TOTS els seleccionats amb el mateix
        # delta (els extrems de les nanses segueixen redimensionant un sol clip).
        if (len(self._multi) > 1
                and getattr(self._chord_items[idx], "_drag_mode", None)
                == ChordItem.ZONE_BODY):
            sel = sorted(i for (k, i) in self._multi if k == "chord")
            if len(sel) > 1 and idx in sel:
                self._move_chord_group(idx, sel, new_t)
                return
        old_t, name, *_r = self._acords[idx]
        # veïns
        prev_t = self._acords[idx - 1][0] if idx - 1 >= 0 else 0.0
        next_t = self._acords[idx + 1][0] if idx + 1 < len(self._acords) \
            else self._durada
        # snap
        new_t_s = snap_time(new_t, self._tempo_fix, self._bpm, self._bpb, self._pps,
                          getattr(self, '_offset', 0.0))
        # limita entre prev_t + MIN_GAP_S i next_t - MIN_GAP_S
        new_t_s = max(prev_t + MIN_GAP_S, min(next_t - MIN_GAP_S, new_t_s))
        self._show_guide_at(new_t_s)
        # si el new_t és igual a prev_t + MIN_GAP_S o next_t - MIN_GAP_S,
        # no propaguem (ja estava limitat). Però sí actualitzem l'item.
        if abs(new_t_s - old_t) < 1e-9:
            return
        self._acords[idx] = (new_t_s, name,
                             f"{new_t_s:.9f}" if len(self._acords[idx]) > 2
                             else f"{new_t_s:.9f}")
        # El propi clip: canvia l'inici
        self._chord_items[idx].set_time(new_t_s)
        # El clip ANTERIOR: el seu fi = aquest inici (contigüitat)
        if idx - 1 >= 0:
            self._chord_items[idx - 1].set_next_t(new_t_s)
        # El clip següent NO canvia (el seu inici segueix igual)
        self.chordTimeMoved.emit(idx, new_t_s)

    def _on_chord_end_changed(self, idx: int, new_next_t: float) -> None:
        """Mou el final de l'acord idx (= inici del següent) a new_next_t."""
        if idx < 0 or idx >= len(self._acords):
            return
        # En un moviment de grup (cos) el final el resol _move_chord_group;
        # aquí no hem de redimensionar el clip ni moure el veí.
        if (len(self._multi) > 1
                and getattr(self._chord_items[idx], "_drag_mode", None)
                == ChordItem.ZONE_BODY):
            sel = sorted(i for (k, i) in self._multi if k == "chord")
            if len(sel) > 1 and idx in sel:
                return
        old_t, name, *_r = self._acords[idx]
        # el final de l'acord idx és igual a l'inici de idx+1 (o durada total)
        # limita:
        #   - per sota: old_t + MIN_GAP_S (no pot ser més petit que l'inici)
        #   - per sobre: si hi ha idx+2, (idx+2).t - MIN_GAP_S;
        #                si no, self._durada
        max_end = (self._acords[idx + 2][0] - MIN_GAP_S
                   if idx + 2 < len(self._acords) else self._durada)
        new_t_s = snap_time(new_next_t, self._tempo_fix, self._bpm, self._bpb,
                            self._pps, getattr(self, "_offset", 0.0))
        new_t_s = max(old_t + MIN_GAP_S, min(max_end, new_t_s))
        self._show_guide_at(new_t_s)
        # si hi ha següent, actualitza'l
        if idx + 1 < len(self._acords):
            n_old_t, n_name, *_r2 = self._acords[idx + 1]
            if abs(new_t_s - n_old_t) < 1e-9:
                return
            self._acords[idx + 1] = (new_t_s, n_name,
                                      f"{new_t_s:.9f}")
            # El propi clip: canvia el seu fi
            self._chord_items[idx].set_next_t(new_t_s)
            # El clip següent: canvia el seu inici (i el seu fi NO)
            self._chord_items[idx + 1].set_time(new_t_s)
            self.chordEndMoved.emit(idx, new_t_s)
        else:
            # no hi ha següent: el final és la durada total. No podem moure'l.
            # ignora el canvi (l'últim hi no té "final" editable per re-validar).
            pass

    def _move_chord_group(self, idx: int, sel: list, new_t: float) -> None:
        """Mou tots els acords de `sel` amb el mateix delta que el clip `idx`.

        El delta es calcula respecte la posició a l'inici del drag i es limita
        perquè cap acord seleccionat ultrapassi el veí NO seleccionat més
        proper (esquerra/dreta). Es recalcula l'amplada (next_t) de tot el
        carril perquè els clips contigus es tornin a pintar bé."""
        item = self._chord_items[idx]
        t0 = float(getattr(item, "_drag_t0", self._acords[idx][0]))
        t_snap = snap_time(new_t, self._tempo_fix, self._bpm, self._bpb, self._pps,
                           getattr(self, "_offset", 0.0))
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
            self._acords[i] = (t_i, self._acords[i][1], f"{t_i:.9f}")
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
        # Moviment de GRUP de seccions (arrossegant el cos d'una de seleccionada)
        if (len(self._multi) > 1
                and getattr(self._section_items[idx], "_drag_mode", None)
                == SectionItem.ZONE_BODY):
            sel = sorted(i for (k, i) in self._multi if k == "section")
            if len(sel) > 1 and idx in sel:
                self._move_section_group(idx, sel, new_ini)
                return
        ini_o, fi_o, lletra, familia = self._seccions[idx]
        zone = self._section_items[idx]._drag_mode
        n = len(self._seccions)

        def prev_ini(i):
            return self._seccions[i - 1][0] if i - 1 >= 0 else 0.0

        def next_ini_of(i):
            return self._seccions[i + 1][0] if i + 1 < n else self._durada

        if zone == SectionItem.ZONE_RIGHT:
            # Mou el FI -> és l'inici de la següent
            max_end = (self._seccions[idx + 2][0] - MIN_GAP_S
                       if idx + 2 < n else self._durada)
            nt = snap_time(new_fi, self._tempo_fix, self._bpm, self._bpb, self._pps,
                      getattr(self, '_offset', 0.0))
            nt = max(ini_o + MIN_SEC_LEN_S, min(max_end, nt))
            self._seccions[idx] = (ini_o, nt, lletra, familia)
            self._section_items[idx].set_fi(nt)
            if idx + 1 < n:
                nx = self._seccions[idx + 1]
                self._seccions[idx + 1] = (nt, nx[1], nx[2], nx[3])
                self._section_items[idx + 1].set_ini(nt)
            self._show_guide_at(nt)
            self.sectionMoved.emit(idx, ini_o, nt)
            return

        if zone == SectionItem.ZONE_BODY:
            # Desplaça la secció sencera (inici i fi junts) — com l'acord
            dur = fi_o - ini_o
            nt = snap_time(new_ini, self._tempo_fix, self._bpm, self._bpb, self._pps,
                      getattr(self, '_offset', 0.0))
            lo = prev_ini(idx) + MIN_GAP_S
            # El fi propi (nt+dur) passa a ser l'inici del següent; per tant
            # el límit cap endavant és el FINAL del següent (= inici del
            # següent-següent, o la durada total).
            seguent_fi = (self._seccions[idx + 2][0] if idx + 2 < n
                          else self._durada)
            hi = max(lo, seguent_fi - dur - MIN_GAP_S)
            nt = max(lo, min(hi, nt))
            self._seccions[idx] = (nt, nt + dur, lletra, familia)
            self._section_items[idx].set_ini(nt)
            self._section_items[idx].set_fi(nt + dur)
            if idx - 1 >= 0:
                p = self._seccions[idx - 1]
                self._seccions[idx - 1] = (p[0], nt, p[2], p[3])
                self._section_items[idx - 1].set_fi(nt)
            if idx + 1 < n:
                x = self._seccions[idx + 1]
                self._seccions[idx + 1] = (nt + dur, x[1], x[2], x[3])
                self._section_items[idx + 1].set_ini(nt + dur)
            self._show_guide_at(nt)
            self.sectionMoved.emit(idx, nt, nt + dur)
            return

        # LEFT / NONE: mou l'INICI (i el fi de l'anterior)

        lo = prev_ini(idx) + MIN_GAP_S
        hi = fi_o - MIN_SEC_LEN_S
        nt = snap_time(new_ini, self._tempo_fix, self._bpm, self._bpb, self._pps,
                      getattr(self, '_offset', 0.0))
        nt = max(lo, min(hi, nt))
        self._seccions[idx] = (nt, fi_o, lletra, familia)
        self._section_items[idx].set_ini(nt)
        if idx - 1 >= 0:
            p = self._seccions[idx - 1]
            self._seccions[idx - 1] = (p[0], nt, p[2], p[3])
            self._section_items[idx - 1].set_fi(nt)
        self._show_guide_at(nt)
        self.sectionMoved.emit(idx, nt, fi_o)

    def _move_section_group(self, idx: int, sel: list, new_ini: float) -> None:
        """Mou totes les seccions de `sel` amb el mateix delta que `idx`.

        Només per a blocs CONTIGUS (el cas natural de Shift+clic). El delta es
        limita perquè les seccions veïnes NO seleccionades (que absorbeixen el
        desplaçament, com en el moviment individual) no baixin de la mida
        mínima. Els extrems dels veïns s'ajusten per mantenir la contigüitat."""
        first, last = sel[0], sel[-1]
        if sel != list(range(first, last + 1)):
            return
        item = self._section_items[idx]
        ini0 = float(getattr(item, "_drag_ini0", self._seccions[idx][0]))
        ini_s = snap_time(new_ini, self._tempo_fix, self._bpm, self._bpb, self._pps,
                          getattr(self, "_offset", 0.0))
        dt = ini_s - ini0
        first_ini = float(self._seccions[first][0])
        last_fi = float(self._seccions[last][1])
        if first - 1 >= 0:
            dt_lo = (float(self._seccions[first - 1][0]) + MIN_SEC_LEN_S
                     - first_ini)
        else:
            dt_lo = -first_ini
        if last + 1 < len(self._seccions):
            dt_hi = (float(self._seccions[last + 1][1]) - MIN_SEC_LEN_S
                     - last_fi)
        else:
            dt_hi = self._durada - last_fi
        dt = 0.0 if dt_lo > dt_hi else max(dt_lo, min(dt_hi, dt))
        for i in sel:
            ini_i, fi_i, L, fam = self._seccions[i]
            self._seccions[i] = (ini_i + dt, fi_i + dt, L, fam)
            self._section_items[i].set_ini(ini_i + dt)
            self._section_items[i].set_fi(fi_i + dt)
        if first - 1 >= 0:
            p = self._seccions[first - 1]
            self._seccions[first - 1] = (p[0], first_ini + dt, p[2], p[3])
            self._section_items[first - 1].set_fi(first_ini + dt)
        if last + 1 < len(self._seccions):
            n = self._seccions[last + 1]
            self._seccions[last + 1] = (last_fi + dt, n[1], n[2], n[3])
            self._section_items[last + 1].set_ini(last_fi + dt)
        self._show_guide_at(self._seccions[idx][0])
        self.sectionMoved.emit(idx, self._seccions[idx][0],
                               self._seccions[idx][1])

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
            t, old, *_r = self._acords[idx]
            self._acords[idx] = (t, text,
                                 f"{t:.9f}" if len(self._acords[idx]) > 2
                                 else f"{t:.9f}")
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
                t = self._loop_x_to_time(sp.x())
                self._loop_drag = True
                self._loop_a = t
                self._loop_b = t
                self._update_loop_item()
                event.accept()
                return
            it = self.itemAt(event.pos())
            if isinstance(it, (ChordItem, SectionItem)):
                kind = "chord" if isinstance(it, ChordItem) else "section"
                idx = getattr(it, "idx", -1)
                mods = event.modifiers()
                # Ctrl+clic = afegir/treure de la multi-selecció; Shift+clic =
                # estendre el rang. En tots dos casos NO s'inicia cap drag.
                if mods & Qt.ControlModifier:
                    self.setFocus()
                    self.toggle_selection(kind, idx)
                    event.accept()
                    return
                if mods & Qt.ShiftModifier:
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
        if getattr(self, "_loop_drag", False):
            sp = self.mapToScene(event.pos())
            t = self._loop_x_to_time(sp.x())
            self._loop_a, self._loop_b = min(self._loop_a, t), max(self._loop_a, t)
            self._update_loop_item()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.RightButton and getattr(self, "_pan_drag", False):
            self._pan_drag = False
            self.viewport().setCursor(Qt.ArrowCursor)
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

    def keyPressEvent(self, event) -> None:
        mods = event.modifiers()
        if event.key() == Qt.Key_Space:
            self.playRequested.emit()
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