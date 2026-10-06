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
import math
from typing import Callable, List, Optional, Sequence

import numpy as np
from PyQt5.QtCore import QLineF, QPoint, QPointF, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import (
    QBrush, QColor, QCursor, QFont, QFontMetricsF, QImage, QPainter,
    QPainterPath, QPen, QPixmap,
)
from PyQt5.QtWidgets import (
    QGraphicsItem, QGraphicsLineItem, QGraphicsObject, QGraphicsPixmapItem,
    QGraphicsRectItem, QGraphicsScene, QGraphicsView, QLineEdit, QWidget,
)


# -----------------------------------------------------------------------------
# Constants de layout i colors
# -----------------------------------------------------------------------------
RULER_H = 26            # alçada del regle de temps (a dalt)
WAVEFORM_H = 170        # alçada de la pista d'ona
LEFT_PAD = 12           # marge intern a l'esquerra
RIGHT_PAD = 12          # marge intern a la dreta
# Els 2 carrils (estructura + acords) van SOBREPOSATS a l'ona, en
# fraccions de WAVEFORM_H — estil DAW amb lanes semitransparents.
LANE_H_FRAC = 0.32
LANE_SEC_TOP_FRAC = 0.04
LANE_ACC_TOP_FRAC = 0.46
LANE_H = int(WAVEFORM_H * LANE_H_FRAC)
LANE_SEC_TOP = RULER_H + WAVEFORM_H * LANE_SEC_TOP_FRAC
LANE_ACC_TOP = RULER_H + WAVEFORM_H * LANE_ACC_TOP_FRAC
TOTAL_H = RULER_H + WAVEFORM_H
RULER_BG = "#10131a"
# Colors de l'ona (BGRA — ordre de memòria de QImage.Format_RGB32)
WF_BG = (0x1c, 0x15, 0x10)   # fons #10151c
WF_ENV = (0xff, 0xc8, 0x7a)  # envolupant #7ac8ff (blau brillant)
WF_MID = (0x50, 0x3e, 0x2c)  # línia central #2c3e50
WF_GAIN = 1.7  # amplificació de visualització de l'ona
WAVEFORM_BG = "#0f1218"
LANE_BG_A = "#1a1d23"
LANE_BG_B = "#15181d"
LANE_DIVIDER = "#2a2f37"
RULER_TEXT = "#c4d0e2"
WAVEFORM_COLOR = "#8ab4f8"
CHORD_FILL = "#2e3844"
CHORD_ACTIVE_FILL = "#dce8ff"
CHORD_TEXT = "#edf3ff"
CHORD_ACTIVE_TEXT = "#141b22"
CHORD_BORDER = "#b8c7dc"
CHORD_HANDLE = "#5b8dd6"
CHORD_HANDLE_ACTIVE = "#ffd166"
SECTION_FILLS = ["#3a4655", "#475a70", "#5d6f82", "#70849a", "#8996aa"]
SECTION_TEXT = "#edf3ff"
CURSOR_COLOR = "#ff6b6b"
GUIDE_COLOR = "#ffd166"
SELECTION_COLOR = "#ffd166"
PIXELS_PER_SECOND_DEFAULT = 60.0
MIN_GAP_S = 0.02         # gap mínim entre inicis d'acords
MIN_SEC_LEN_S = 0.05     # durada mínima d'una secció


# -----------------------------------------------------------------------------
# Utilitats de temps i snap
# -----------------------------------------------------------------------------
def _best_step_free(span_s: float) -> float:
    """Pas de snap per a mode lliure (sense tempo)."""
    if span_s <= 5.0:
        return 0.1
    if span_s <= 20.0:
        return 0.5
    if span_s <= 60.0:
        return 1.0
    if span_s <= 300.0:
        return 5.0
    return 10.0


def _best_step_tempo(span_s: float, bpm: float, bpb: int) -> float:
    """Pas de snap per a mode tempo_fix."""
    beat = 60.0 / max(bpm, 1e-9)
    measure = beat * max(bpb, 1)
    if span_s <= beat * 4:
        return beat / 2.0      # corxera
    if span_s <= measure * 2:
        return beat            # beat
    return measure             # compàs


def snap_time(t: float, tempo_fix: bool, bpm: float, bpb: int,
              view_span: float) -> float:
    """Arrodoneix t al pas de snap adequat segons el zoom (view_span).

    Amb BPM: mai no s'arrodoneix al compàs sencer (massa gruixut) — com a
    màxim a un temps; segons el zoom, es va a corxera o setzena.
    Sense BPM: 0,1 s (o més fi si el zoom és molt proper).
    """
    if tempo_fix:
        beat = 60.0 / max(float(bpm), 1e-9)
        if view_span <= beat * 8:
            step = beat / 4.0      # setzena
        elif view_span <= beat * 32:
            step = beat / 2.0      # corxera
        else:
            step = beat            # temps (mai compàs)
    else:
        if view_span <= 2.0:
            step = 0.02
        elif view_span <= 5.0:
            step = 0.05
        elif view_span <= 20.0:
            step = 0.1
        elif view_span <= 60.0:
            step = 0.5
        else:
            step = 1.0
    if step <= 0:
        return t
    return round(t / step) * step


def fmt_pos(t: float, tempo_fix: bool, bpm: float, bpb: int) -> str:
    """Formata t per al ruler o status: '12.3s' o '3.2' (compàs.beat)."""
    if not tempo_fix:
        return f"{t:.1f}s"
    beat = 60.0 / max(bpm, 1e-9)
    beats = max(0.0, t) / beat
    compas = int(beats // bpb) + 1
    beat_idx = int(round(beats % bpb)) + 1
    if beat_idx > bpb:
        compas += 1
        beat_idx = 1
    return f"{compas}.{beat_idx}"


# -----------------------------------------------------------------------------
# WaveformLayer — l'ona pintada com a pixmap (estil Audacity/DAW)
# -----------------------------------------------------------------------------
class WaveformLayer(QGraphicsPixmapItem):
    """L'ona amb envolupant plena (min/max per columna de píxel).

    Es recalcula per al tram visible cada cop que canvia el zoom/pan →
    sempre nítida, com fa Audacity. Colors en ordre BGRA (Format_RGB32).
    """

    def __init__(self, samples, sr, height, pps, x_offset, top,
                 parent=None):
        super().__init__(parent)
        self._samples = np.ascontiguousarray(samples, dtype=np.int16)
        self._sr = int(sr) or 1
        self._height = int(height)
        self._pps = float(pps)
        self._x_offset = float(x_offset)
        self._top = float(top)
        self.setZValue(-10)
        self.setPos(self._x_offset, self._top)
        self._render(0.0, self.durada())

    def durada(self):
        return len(self._samples) / float(self._sr)

    def update_geometry(self, pps, x_offset, left, right):
        self._pps = float(pps)
        self._x_offset = float(x_offset)
        self.setPos(self._x_offset, self._top)
        self._render(left, right)

    def _render(self, left=None, right=None):
        h = max(2, self._height)
        n = len(self._samples)
        if n == 0:
            self.setPixmap(QPixmap(1, h))
            return
        durada = self.durada()
        if left is None:
            left = 0.0
        if right is None:
            right = durada
        left = max(0.0, min(float(left), durada))
        right = max(left + 1e-6, min(float(right), durada))
        s0 = max(0, min(int(left * self._sr), n - 1))
        s1 = max(s0 + 1, min(int(right * self._sr) + 1, n))
        n_cols = max(1, int(round((right - left) * self._pps)))
        n_cols = max(1, min(n_cols, s1 - s0))
        starts = np.linspace(s0, s1 - 1, n_cols).astype(np.int64)
        starts = np.maximum.accumulate(starts)
        mins = np.minimum.reduceat(self._samples, starts).astype(np.float32)
        maxs = np.maximum.reduceat(self._samples, starts).astype(np.float32)
        mins /= 32768.0
        maxs /= 32768.0
        # Gain de visualització (com fan els DAW): la majoria d'àudio no
        # arriba a ±1.0 i queda prim. El multipliquem i clampejem a ±1.
        mins = np.clip(mins * WF_GAIN, -1.0, 1.0)
        maxs = np.clip(maxs * WF_GAIN, -1.0, 1.0)
        img = np.empty((h, n_cols, 4), dtype=np.uint8)
        img[..., 0] = WF_BG[0]
        img[..., 1] = WF_BG[1]
        img[..., 2] = WF_BG[2]
        img[..., 3] = 255
        mig = (h - 1) / 2.0
        amp = (h / 2.0) - 2.0
        y_top = np.clip(np.round(mig - maxs * amp).astype(np.int32), 0, h - 1)
        y_bot = np.clip(np.round(mig - mins * amp).astype(np.int32), 0, h - 1)
        rows = np.arange(h, dtype=np.int32)[:, None]
        mask = (rows >= y_top[None, :]) & (rows <= y_bot[None, :])
        for ch_i in range(3):
            plane = img[..., ch_i]
            plane[mask] = WF_ENV[ch_i]
        mig_i = int(round(mig))
        if 0 <= mig_i < h:
            img[mig_i, :, 0] = WF_MID[0]
            img[mig_i, :, 1] = WF_MID[1]
            img[mig_i, :, 2] = WF_MID[2]
        qimg = QImage(img.data, n_cols, h, n_cols * 4,
                      QImage.Format_RGB32).copy()
        self.setPixmap(QPixmap.fromImage(qimg))
        self.setPos(self._x_offset, self._top)


# -----------------------------------------------------------------------------
# grid_levels — nivells de la graella segons zoom i mode (temps/BPM)
# -----------------------------------------------------------------------------
def grid_levels(tempo_fix, bpm, bpb, span):
    """Retorna [(step_s, color, width), ...] de menys a més important."""
    if tempo_fix:
        beat = 60.0 / max(float(bpm), 1e-9)
        measure = beat * max(int(bpb), 1)
        levels = [(measure, "#55677f", 1)]
        if span <= measure * 16:
            levels.insert(0, (beat, "#3d4c60", 1))
        if span <= beat * 8:
            levels.insert(0, (beat / 2.0, "#303a48", 1))
        return levels
    step = _best_step_free(span)
    levels = [(step, "#55677f", 1)]
    if span <= 30.0:
        levels.insert(0, (step / 5.0, "#303a48", 1))
    return levels


# -----------------------------------------------------------------------------
# GridLayer — línies verticals de la graella sobre l'ona (estil DAW)
# -----------------------------------------------------------------------------
class GridLayer(QGraphicsItem):
    """Línies verticals de compàs/beat/subdivisió sobre l'ona."""

    def __init__(self, height, pps, x_offset, view_left, view_right,
                 tempo_fix, bpm, bpb, top, parent=None):
        super().__init__(parent)
        self._height = int(height)
        self._pps = float(pps)
        self._x_offset = float(x_offset)
        self._view_left = float(view_left)
        self._view_right = float(view_right)
        self._tempo_fix = bool(tempo_fix)
        self._bpm = float(bpm)
        self._bpb = int(bpb)
        self._top = float(top)
        self.setZValue(-6)
        self.setPos(self._x_offset, self._top)

    def boundingRect(self):
        return QRectF(0, 0, max(1.0, (self._view_right - self._view_left) *
                                self._pps), self._height)

    def update_geometry(self, pps, x_offset, view_left, view_right):
        self._pps = float(pps)
        self._x_offset = float(x_offset)
        self._view_left = float(view_left)
        self._view_right = float(view_right)
        # Mateix raonament que el regle: coords relatives a view_left →
        # cal desplaçar la posició perquè el grid caigui al lloc absolut.
        self.prepareGeometryChange()
        self.setPos(self._x_offset, self._top)
        self.update()

    def update_mode(self, tempo_fix, bpm, bpb):
        self._tempo_fix = bool(tempo_fix)
        self._bpm = float(bpm)
        self._bpb = int(bpb)
        self.update()

    def paint(self, painter, option, widget=None):
        p = painter
        p.setRenderHint(QPainter.Antialiasing, False)
        span = max(self._view_right - self._view_left, 1e-6)
        for step, color, width in grid_levels(self._tempo_fix, self._bpm,
                                              self._bpb, span):
            if step <= 1e-9:
                continue
            p.setPen(QPen(QColor(color), width))
            t = math.floor(self._view_left / step) * step
            if t < 0:
                t = 0.0
            while t <= self._view_right + 1e-9:
                x = (t - self._view_left) * self._pps
                p.drawLine(QPointF(x, 0), QPointF(x, self._height))
                t += step


# -----------------------------------------------------------------------------
# RulerLayer — el regle de temps (a dalt, estil DAW)
# -----------------------------------------------------------------------------
class RulerLayer(QGraphicsItem):
    """El regle de temps: ticks i etiquetes (compàs.beat o segons)."""

    def __init__(self, width, height, pps, x_offset, view_left, view_right,
                 tempo_fix, bpm, bpb, top=0, parent=None):
        super().__init__(parent)
        self._height = int(height)
        self._pps = float(pps)
        self._x_offset = float(x_offset)
        self._view_left = float(view_left)
        self._view_right = float(view_right)
        self._tempo_fix = bool(tempo_fix)
        self._bpm = float(bpm)
        self._bpb = int(bpb)
        self._top = float(top)
        self.setZValue(-4)
        self.setPos(self._x_offset, self._top)

    def boundingRect(self):
        return QRectF(0, 0, max(1.0, (self._view_right - self._view_left) *
                                self._pps), self._height)

    def update_geometry(self, pps, x_offset, view_left, view_right):
        self._pps = float(pps)
        self._x_offset = float(x_offset)
        self._view_left = float(view_left)
        self._view_right = float(view_right)
        # IMPORTANT: el regle pinta en coords relatives a view_left, per tant
        # la seva posició ha de ser _x_offset + view_left*pps perquè les
        # etiquetes caiguin al mateix x absolut que els clips/ona.
        self.prepareGeometryChange()
        self.setPos(self._x_offset, self._top)
        self.update()

    def update_mode(self, tempo_fix, bpm, bpb):
        self._tempo_fix = bool(tempo_fix)
        self._bpm = float(bpm)
        self._bpb = int(bpb)
        self.update()

    def paint(self, painter, option, widget=None):
        p = painter
        p.setRenderHint(QPainter.Antialiasing, False)
        rect = self.boundingRect()
        p.fillRect(rect, QColor(RULER_BG))
        p.setPen(QPen(QColor("#2f3640"), 1))
        p.drawLine(QPointF(0, self._height - 1),
                   QPointF(rect.width(), self._height - 1))
        span = max(self._view_right - self._view_left, 1e-6)
        levels = grid_levels(self._tempo_fix, self._bpm, self._bpb, span)
        # ticks dels nivells secundaris
        for sub, subcolor, _w in levels[:-1]:
            if sub <= 1e-9:
                continue
            p.setPen(QPen(QColor(subcolor), 1))
            t = math.floor(self._view_left / sub) * sub
            if t < 0:
                t = 0.0
            while t <= self._view_right + 1e-9:
                x = (t - self._view_left) * self._pps
                p.drawLine(QPointF(x, self._height - 4),
                           QPointF(x, self._height - 1))
                t += sub
        # ticks principals + etiquetes
        step, color, _w = levels[-1]
        font = QFont("Sans Serif", 8)
        p.setFont(font)
        fm = QFontMetricsF(font)
        t = math.floor(self._view_left / step) * step
        if t < 0:
            t = 0.0
        last_label_x = -1e9
        while t <= self._view_right + 1e-9:
            x = (t - self._view_left) * self._pps
            p.setPen(QPen(QColor(color), 1))
            p.drawLine(QPointF(x, self._height - 8),
                       QPointF(x, self._height - 1))
            lab = fmt_pos(t, self._tempo_fix, self._bpm, self._bpb)
            wlab = fm.width(lab)
            if x - wlab / 2 > last_label_x:
                p.setPen(QPen(QColor(RULER_TEXT), 1))
                p.drawText(QPointF(x - wlab / 2, self._height - 11), lab)
                last_label_x = x + wlab / 2
            t += step


# -----------------------------------------------------------------------------
# LaneBackground — fons dels 2 carrils
# -----------------------------------------------------------------------------
class LaneBackground(QGraphicsRectItem):
    """Rectangle de fons d'un carril."""

    def __init__(self, x: float, y: float, w: float, h: float,
                 fill: str, parent: Optional[QGraphicsItem] = None):
        super().__init__(x, y, w, h, parent)
        self.setBrush(QBrush(QColor(fill)))
        self.setPen(QPen(QColor(LANE_DIVIDER), 1))
        self.setZValue(-8)


# -----------------------------------------------------------------------------
# CursorLine — cursor vertical de reproducció
# -----------------------------------------------------------------------------
class CursorLine(QGraphicsLineItem):
    def __init__(self, y_top: float, y_bottom: float,
                 parent: Optional[QGraphicsItem] = None):
        super().__init__(QLineF(0, y_top, 0, y_bottom), parent)
        self.setPen(QPen(QColor(CURSOR_COLOR), 2))
        self.setZValue(50)
        self._y_top = y_top
        self._y_bottom = y_bottom

    def set_time(self, t: float, pps: float, x_offset: float,
                 view_left: float = 0.0) -> None:
        x = x_offset + (t - view_left) * pps
        line = self.line()
        line.setP1(QPointF(x, self._y_top))
        line.setP2(QPointF(x, self._y_bottom))
        self.setLine(line)

    def set_y_range(self, y_top: float, y_bottom: float) -> None:
        self._y_top = y_top
        self._y_bottom = y_bottom
        line = self.line()
        line.setP1(QPointF(line.p1().x(), y_top))
        line.setP2(QPointF(line.p2().x(), y_bottom))
        self.setLine(line)


# -----------------------------------------------------------------------------
# ChordItem — un acord (caixa amb nanses + edició inline)
# -----------------------------------------------------------------------------
class ChordItem(QGraphicsObject):
    """Un acord: rectangle amb 3 zones (handle-esq | cos | handle-dreta).

    El Rectangle té:
      - x     = self.t * pps + x_offset
      - width = (self.next_t - self.t) * pps  (0 si no té següent: durada 1px)
    """

    ZONE_NONE = 0
    ZONE_LEFT = 1
    ZONE_BODY = 2
    ZONE_RIGHT = 3
    HANDLE_W = 10
    MIN_W = 24           # ample mínim visual
    MIN_GAP_PX = 2       # separació visual mínima entre acords

    timeChanged = pyqtSignal(float)          # self.t ha canviat
    endTimeChanged = pyqtSignal(float)       # self.next_t ha canviat (el del següent)
    renameRequested = pyqtSignal(str)         # usuari ha escrit nom nou
    deleteRequested = pyqtSignal()
    editRequested = pyqtSignal()
    clicked = pyqtSignal()  # click sense drag → seek
    dragStarted = pyqtSignal()   # INICI de gest (mouse press sobre el clip)
    dragFinished = pyqtSignal()  # fi de drag (moure/redimensionar)

    def __init__(self, idx: int, t: float, name: str, next_t: float,
                 pps: float, x_offset: float, lane_y: float, lane_h: float,
                 parent: Optional[QGraphicsItem] = None):
        super().__init__(parent)
        self.idx = idx
        self.t = float(t)
        self.name = str(name)
        self._next_t = float(next_t)        # inici del següent (o durada_total)
        self._pps = float(pps)
        self._x_offset = float(x_offset)
        self._view_left = 0.0   # coords RELATIVES a la vista
        self._lane_y = float(lane_y)
        self._lane_h = float(lane_h)
        self._selected = False
        self._editing = False
        self._drag_mode = self.ZONE_NONE
        self._drag_x0 = 0.0
        self._drag_t0 = 0.0
        self._drag_next_t0 = 0.0
        self._active = False
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(10)

    # -- mètodes de geometria -------------------------------------------------
    def set_pps(self, pps: float, x_offset: float,
                view_left: float = 0.0) -> None:
        self.prepareGeometryChange()
        self._pps = float(pps)
        self._x_offset = float(x_offset)
        self._view_left = float(view_left)
        self.update()

    def set_next_t(self, next_t: float) -> None:
        self.prepareGeometryChange()
        self._next_t = float(next_t)
        self.update()

    def set_time(self, t: float) -> None:
        self.prepareGeometryChange()
        self.t = float(t)
        self.update()

    def set_active(self, active: bool) -> None:
        self._active = bool(active)
        self.update()

    def set_selected(self, selected: bool) -> None:
        self._selected = bool(selected)
        self.update()

    def _x_left(self) -> float:
        return self._x_offset + (self.t - self._view_left) * self._pps

    def _x_right(self) -> float:
        if self._next_t > self.t:
            return self._x_offset + (self._next_t - self._view_left) * self._pps
        return self._x_left() + self.MIN_W

    def boundingRect(self) -> QRectF:
        x = self._x_left()
        w = max(self.MIN_W, self._x_right() - x)
        # sense padding: evita solapament amb el clip adjacent
        return QRectF(x, self._lane_y, w, self._lane_h)

    # -- dibuix ---------------------------------------------------------------
    def paint(self, painter: QPainter, option, widget=None) -> None:
        x = self._x_left()
        right = self._x_right()
        w = max(self.MIN_W, right - x)
        y = self._lane_y + 4
        h = self._lane_h - 8
        fill = QColor(CHORD_ACTIVE_FILL if self._active else CHORD_FILL)
        fill.setAlpha(240 if self._active else 170)  # semitransparent
        border = QPen(QColor(SELECTION_COLOR if self._selected
                             else CHORD_BORDER), 2 if self._selected else 1)
        painter.setBrush(QBrush(fill))
        painter.setPen(border)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(x, y, w, h)
        painter.drawRoundedRect(rect, 6, 6)
        # nanses laterals
        if w > self.MIN_W + 2 * self.HANDLE_W:
            handle_col = QColor(CHORD_HANDLE_ACTIVE if self._selected
                                else CHORD_HANDLE)
            painter.setPen(QPen(handle_col, 2))
            painter.drawLine(QPointF(x + 3, y + 4), QPointF(x + 3, y + h - 4))
            painter.drawLine(QPointF(x + w - 3, y + 4),
                             QPointF(x + w - 3, y + h - 4))
        # text (nom de l'acord), centrat
        if not self._editing:
            text_color = QColor(CHORD_ACTIVE_TEXT if self._active
                                else CHORD_TEXT)
            painter.setPen(QPen(text_color, 1))
            font = QFont("Sans Serif", 10, QFont.Bold)
            painter.setFont(font)
            fm = QFontMetricsF(font)
            tname = self.name
            if fm.width(tname) > w - 16:
                # retalla amb ...
                while tname and fm.width(tname + "…") > w - 16:
                    tname = tname[:-1]
                if tname:
                    tname = tname + "…"
            painter.drawText(QRectF(x, y, w, h), Qt.AlignCenter, tname or "")

    # -- hit-test -------------------------------------------------------------
    def _zone_at(self, x: float) -> int:
        lx = self._x_left()
        rx = self._x_right()
        if x < lx or x > rx:
            return self.ZONE_NONE
        if x <= lx + self.HANDLE_W:
            return self.ZONE_LEFT
        if x >= rx - self.HANDLE_W:
            return self.ZONE_RIGHT
        return self.ZONE_BODY

    # -- events ---------------------------------------------------------------
    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return
        z = self._zone_at(event.pos().x())
        self._drag_mode = z
        self._drag_x0 = event.pos().x()
        self._drag_t0 = self.t
        self._drag_next_t0 = self._next_t
        self._drag_moved = False
        if z in (self.ZONE_LEFT, self.ZONE_RIGHT):
            self.setCursor(Qt.SizeHorCursor)
        elif z == self.ZONE_BODY:
            self.setCursor(Qt.ClosedHandCursor)
        if z != self.ZONE_NONE:
            self.dragStarted.emit()   # captura l'estat ABANS de cap canvi
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_mode == self.ZONE_NONE:
            z = self._zone_at(event.pos().x())
            if z in (self.ZONE_LEFT, self.ZONE_RIGHT):
                self.setCursor(Qt.SizeHorCursor)
            elif z == self.ZONE_BODY:
                self.setCursor(Qt.OpenHandCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
            super().mouseMoveEvent(event)
            return
        # el moviment es delega al TimelineView via signals (millor control de|
        # snap i propagació). Aquí només calculem deltas i emetem.|
        dx = event.pos().x() - self._drag_x0
        if abs(dx) > 5:
            self._drag_moved = True
        dt = dx / self._pps if self._pps > 0 else 0.0
        if self._drag_mode == self.ZONE_LEFT:
            new_t = self._drag_t0 + dt
            self.timeChanged.emit(new_t)
        elif self._drag_mode == self.ZONE_RIGHT:
            new_next_t = self._drag_next_t0 + dt
            self.endTimeChanged.emit(new_next_t)
        elif self._drag_mode == self.ZONE_BODY:
            new_t = self._drag_t0 + dt
            new_next_t = self._drag_next_t0 + dt
            self.timeChanged.emit(new_t)
            self.endTimeChanged.emit(new_next_t)
        event.accept()

    def hoverMoveEvent(self, event) -> None:
        z = self._zone_at(event.pos().x())
        if z in (self.ZONE_LEFT, self.ZONE_RIGHT):
            self.setCursor(Qt.SizeHorCursor)
        elif z == self.ZONE_BODY:
            self.setCursor(Qt.OpenHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        super().hoverMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        moved = getattr(self, "_drag_moved", False)
        self._drag_mode = self.ZONE_NONE
        super().mouseReleaseEvent(event)
        if moved:
            self.dragFinished.emit()
        else:
            self.clicked.emit()

    def mouseDoubleClickEvent(self, event) -> None:
        self.editRequested.emit()
        event.accept()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.deleteRequested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


# -----------------------------------------------------------------------------
# SectionItem — una secció (rectangle amb nanses)
# -----------------------------------------------------------------------------
class SectionItem(QGraphicsObject):
    """Una secció: rectangle amb (ini, fi) explícits."""

    ZONE_NONE = 0
    ZONE_LEFT = 1
    ZONE_BODY = 2
    ZONE_RIGHT = 3
    HANDLE_W = 10
    MIN_W = 28

    timeChanged = pyqtSignal(float, float)    # (new_ini, new_fi)
    renameRequested = pyqtSignal(str)
    deleteRequested = pyqtSignal()
    editRequested = pyqtSignal()
    clicked = pyqtSignal()  # click sense drag → seek
    dragStarted = pyqtSignal()   # INICI de gest (mouse press sobre el clip)
    dragFinished = pyqtSignal()  # fi de drag (moure/redimensionar)

    def __init__(self, idx: int, ini: float, fi: float, lletra: str,
                 familia: str, pps: float, x_offset: float,
                 lane_y: float, lane_h: float,
                 parent: Optional[QGraphicsItem] = None):
        super().__init__(parent)
        self.idx = idx
        self.ini = float(ini)
        self.fi = float(fi)
        self.lletra = str(lletra)
        self.familia = str(familia)
        self._pps = float(pps)
        self._x_offset = float(x_offset)
        self._view_left = 0.0   # coords RELATIVES a la vista
        self._lane_y = float(lane_y)
        self._lane_h = float(lane_h)
        self._selected = False
        self._editing = False
        self._active = False
        self._drag_mode = self.ZONE_NONE
        self._drag_x0 = 0.0
        self._drag_ini0 = 0.0
        self._drag_fi0 = 0.0
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(8)

    def set_pps(self, pps: float, x_offset: float,
                view_left: float = 0.0) -> None:
        self.prepareGeometryChange()
        self._pps = float(pps)
        self._x_offset = float(x_offset)
        self._view_left = float(view_left)
        self.update()

    def set_ini(self, ini: float) -> None:
        self.prepareGeometryChange()
        self.ini = float(ini)
        self.update()

    def set_fi(self, fi: float) -> None:
        self.prepareGeometryChange()
        self.fi = float(fi)
        self.update()

    def set_active(self, active: bool) -> None:
        self._active = bool(active)
        self.update()

    def set_selected(self, selected: bool) -> None:
        self._selected = bool(selected)
        self.update()

    def _x_left(self) -> float:
        return self._x_offset + (self.ini - self._view_left) * self._pps

    def _x_right(self) -> float:
        return self._x_offset + (self.fi - self._view_left) * self._pps

    def boundingRect(self) -> QRectF:
        x = self._x_left()
        w = max(self.MIN_W, self._x_right() - x)
        return QRectF(x, self._lane_y, w, self._lane_h)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        x = self._x_left()
        rx = self._x_right()
        w = max(self.MIN_W, rx - x)
        y = self._lane_y + 4
        h = self._lane_h - 8
        fills = [QColor(c) for c in SECTION_FILLS]
        fill = fills[hash(self.lletra) % len(fills)]
        fill.setAlpha(180)  # semitransparent (es veu l'ona a sota)
        if self._active:
            fill = fill.lighter(140)
        border = QPen(QColor(SELECTION_COLOR if self._selected
                             else "#dfe7f5"), 2 if self._selected else 1)
        painter.setBrush(QBrush(fill))
        painter.setPen(border)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(x, y, w, h)
        painter.drawRoundedRect(rect, 6, 6)
        # nanses
        if w > self.MIN_W + 2 * self.HANDLE_W:
            handle_col = QColor(CHORD_HANDLE_ACTIVE if self._selected
                                else CHORD_HANDLE)
            painter.setPen(QPen(handle_col, 2))
            painter.drawLine(QPointF(x + 3, y + 4),
                             QPointF(x + 3, y + h - 4))
            painter.drawLine(QPointF(x + w - 3, y + 4),
                             QPointF(x + w - 3, y + h - 4))
        if not self._editing:
            painter.setPen(QPen(QColor(SECTION_TEXT), 1))
            font = QFont("Sans Serif", 10, QFont.Bold)
            painter.setFont(font)
            fm = QFontMetricsF(font)
            txt = f"{self.lletra} · {self.familia}" if self.familia and \
                self.familia != self.lletra else self.lletra
            if fm.width(txt) > w - 16:
                while txt and fm.width(txt + "…") > w - 16:
                    txt = txt[:-1]
                if txt:
                    txt = txt + "…"
            painter.drawText(QRectF(x, y, w, h), Qt.AlignCenter, txt or "")

    def _zone_at(self, x: float) -> int:
        lx = self._x_left()
        rx = self._x_right()
        if x < lx or x > rx:
            return self.ZONE_NONE
        if x <= lx + self.HANDLE_W:
            return self.ZONE_LEFT
        if x >= rx - self.HANDLE_W:
            return self.ZONE_RIGHT
        return self.ZONE_BODY

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return
        z = self._zone_at(event.pos().x())
        self._drag_mode = z
        self._drag_x0 = event.pos().x()
        self._drag_ini0 = self.ini
        self._drag_fi0 = self.fi
        self._drag_moved = False
        if z != self.ZONE_NONE:
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_mode == self.ZONE_NONE:
            z = self._zone_at(event.pos().x())
            if z in (self.ZONE_LEFT, self.ZONE_RIGHT):
                self.setCursor(Qt.SizeHorCursor)
            elif z == self.ZONE_BODY:
                self.setCursor(Qt.OpenHandCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
            super().mouseMoveEvent(event)
            return
        dx = event.pos().x() - self._drag_x0
        if abs(dx) > 5:
            self._drag_moved = True
        dt = dx / self._pps if self._pps > 0 else 0.0
        if self._drag_mode == self.ZONE_LEFT:
            self.timeChanged.emit(self._drag_ini0 + dt, self._drag_fi0)
        elif self._drag_mode == self.ZONE_RIGHT:
            self.timeChanged.emit(self._drag_ini0, self._drag_fi0 + dt)
        elif self._drag_mode == self.ZONE_BODY:
            # Com els acords: el cos mou inici I fi alhora (desplaça la secció)
            self.timeChanged.emit(self._drag_ini0 + dt, self._drag_fi0 + dt)
        event.accept()

    def hoverMoveEvent(self, event) -> None:
        z = self._zone_at(event.pos().x())
        if z in (self.ZONE_LEFT, self.ZONE_RIGHT):
            self.setCursor(Qt.SizeHorCursor)
        elif z == self.ZONE_BODY:
            self.setCursor(Qt.OpenHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        super().hoverMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        moved = getattr(self, "_drag_moved", False)
        self._drag_mode = self.ZONE_NONE
        super().mouseReleaseEvent(event)
        if moved:
            self.dragFinished.emit()
        else:
            self.clicked.emit()

    def mouseDoubleClickEvent(self, event) -> None:
        self.editRequested.emit()
        event.accept()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.deleteRequested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


# -----------------------------------------------------------------------------
# RenameEditor — QLineEdit overlay per a edició inline
# -----------------------------------------------------------------------------
class RenameEditor(QLineEdit):
    """Petit QLineEdit que es posiciona sobre un QGraphicsItem per reanomenar."""

    def __init__(self, parent_widget: QWidget,
                 initial: str, on_commit: Callable[[str], None],
                 on_cancel: Callable[[], None], width: int = 120):
        super().__init__(parent_widget)
        self._on_commit = on_commit
        self._on_cancel = on_cancel
        self._committed = False
        self.setText(initial)
        self.selectAll()
        self.resize(int(width), 28)
        self.setWindowFlags(Qt.SubWindow)
        self.returnPressed.connect(self._commit)
        self.show()
        self.setFocus()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self._cancel()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event) -> None:
        if not self._committed:
            self._commit()
        super().focusOutEvent(event)

    def _commit(self) -> None:
        if self._committed:
            return
        self._committed = True
        try:
            self._on_commit(self.text())
        finally:
            self.deleteLater()

    def _cancel(self) -> None:
        if self._committed:
            return
        self._committed = True
        try:
            self._on_cancel()
        finally:
            self.deleteLater()


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
    sectionEditRequested = pyqtSignal(int)

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
        self._loop_item = None     # banda de loop A/B
        self._loop_a = None
        self._loop_b = None
        self._loop_drag = False

        # escena
        self._scene = QGraphicsScene(self)
        self._scene.setBackgroundBrush(QBrush(QColor("#0f0f10")))
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
        self._rebuild_chord_items()
        self._rebuild_section_items()

    def set_tempo_mode(self, tempo_fix: bool, bpm: float, bpb: int) -> None:
        self._tempo_fix = bool(tempo_fix)
        self._bpm = float(bpm)
        self._bpb = int(bpb)
        self._ruler.update_mode(self._tempo_fix, self._bpm, self._bpb)
        self._grid.update_mode(self._tempo_fix, self._bpm, self._bpb)
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

    def set_loop(self, a: float, b: float) -> None:
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
        self._sel = (kind, index)
        for it in self._chord_items:
            it.set_selected(kind == "chord" and getattr(it, "idx", -1) == index)
        for it in self._section_items:
            it.set_selected(kind == "section" and getattr(it, "idx", -1) == index)

    # -- gestió d'events dels items (constraint + propagació) -----------------
    def _on_chord_time_changed(self, idx: int, new_t: float) -> None:
        """Mou l'inici de l'acord idx a new_t (amb snap + constraint)."""
        if idx < 0 or idx >= len(self._acords):
            return
        old_t, name, *_r = self._acords[idx]
        # veïns
        prev_t = self._acords[idx - 1][0] if idx - 1 >= 0 else 0.0
        next_t = self._acords[idx + 1][0] if idx + 1 < len(self._acords) \
            else self._durada
        # snap
        span = self._view_right - self._view_left
        new_t_s = snap_time(new_t, self._tempo_fix, self._bpm, self._bpb, span)
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
        old_t, name, *_r = self._acords[idx]
        # el final de l'acord idx és igual a l'inici de idx+1 (o durada total)
        # limita:
        #   - per sota: old_t + MIN_GAP_S (no pot ser més petit que l'inici)
        #   - per sobre: si hi ha idx+2, (idx+2).t - MIN_GAP_S;
        #                si no, self._durada
        max_end = (self._acords[idx + 2][0] - MIN_GAP_S
                   if idx + 2 < len(self._acords) else self._durada)
        span = self._view_right - self._view_left
        new_t_s = snap_time(new_next_t, self._tempo_fix, self._bpm, self._bpb,
                            span)
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
        ini_o, fi_o, lletra, familia = self._seccions[idx]
        span = self._view_right - self._view_left
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
            nt = snap_time(new_fi, self._tempo_fix, self._bpm, self._bpb, span)
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
            nt = snap_time(new_ini, self._tempo_fix, self._bpm, self._bpb, span)
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
        nt = snap_time(new_ini, self._tempo_fix, self._bpm, self._bpb, span)
        nt = max(lo, min(hi, nt))
        self._seccions[idx] = (nt, fi_o, lletra, familia)
        self._section_items[idx].set_ini(nt)
        if idx - 1 >= 0:
            p = self._seccions[idx - 1]
            self._seccions[idx - 1] = (p[0], nt, p[2], p[3])
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
        # Clip seleccionat? -> centrem la vista al seu centre.
        # Si no, el zoom es centra al punt on apunta el cursor.
        centre = self.selected_center()
        ampl = max((self._view_right - self._view_left) *
                   (0.85 if delta > 0 else (1.0 / 0.85)), 0.3)
        if centre is not None:
            self._center_on(centre, ampl)
            event.accept()
            return
        l, r = self._view_left, self._view_right
        try:
            x = event.position().x()
        except AttributeError:
            x = float(event.pos().x())
        ample_vp = max(self.viewport().width() - LEFT_PAD - RIGHT_PAD, 1)
        frac = max(0.0, min(1.0, (x - LEFT_PAD) / ample_vp))
        t_cursor = l + frac * (r - l)
        self._center_on(t_cursor, ampl)
        event.accept()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.RightButton:
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
                t = max(0.0, min(self._durada, self._x_to_time(sp.x())))
                self._loop_drag = True
                self._loop_a = t
                self._loop_b = t
                self._update_loop_item()
                event.accept()
                return
            it = self.itemAt(event.pos())
            if isinstance(it, (ChordItem, SectionItem)):
                super().mousePressEvent(event)
                return
            # Click al fons -> mou el cursor
            try:
                pos = event.position() if hasattr(event, "position") else event.pos()
                scene_pt = self.mapToScene(pos)
                t = max(0.0, min(self._durada, self._x_to_time(scene_pt.x())))
                self.set_position(t)
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
            t = max(0.0, min(self._durada, self._x_to_time(sp.x())))
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
        if event.key() == Qt.Key_Space:
            self.playRequested.emit()
            event.accept()
            return
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            # Esborra el clip SELECCIONAT. Els items no reben tecles (no son
            # focusables), per tant ho gestionem aquí, que si tenim el focus.
            for items, sig in ((self._chord_items, self.chordDeleteRequested),
                               (self._section_items, self.sectionDeleteRequested)):
                for it in items:
                    if getattr(it, "_selected", False):
                        sig.emit(getattr(it, "idx", -1))
                        event.accept()
                        return
        if (event.modifiers() & Qt.ControlModifier) and event.key() == Qt.Key_D:
            # Ctrl+D: duplica el clip seleccionat
            for items, sig in ((self._chord_items, self.chordDuplicateRequested),
                               (self._section_items, self.sectionDuplicateRequested)):
                for it in items:
                    if getattr(it, "_selected", False):
                        sig.emit(getattr(it, "idx", -1))
                        event.accept()
                        return
        super().keyPressEvent(event)

    def leaveEvent(self, event) -> None:
        self._hide_guide()
        super().leaveEvent(event)