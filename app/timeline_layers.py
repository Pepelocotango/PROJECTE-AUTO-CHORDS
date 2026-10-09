#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
timeline_layers.py — Capes de fons de l'editor de timeline (DAW).

Agrupa els QGraphicsItem "de fons" que es pinten sobre/sota l'ona, extrets
de `timeline.py` per alleugerir-lo:

- WaveformLayer  — l'ona com a QPixmap (estil Audacity/DAW).
- GridLayer      — línies verticals de compàs/beat/subdivisió.
- RulerLayer     — el regle de temps (a dalt).
- LaneBackground — fons dels 2 carrils (estructura + acords).
- CursorLine     — cursor vertical de reproducció.

Tot en català. Sense dependències noves.
"""
import math
from typing import Optional

import numpy as np
from PyQt5.QtCore import QLineF, QPointF, QRectF
from PyQt5.QtGui import (
    QBrush, QColor, QFont, QFontMetricsF, QImage, QPainter, QPen, QPixmap,
)
from PyQt5.QtWidgets import (
    QGraphicsItem, QGraphicsLineItem, QGraphicsPixmapItem, QGraphicsRectItem,
)

from app import theme      # noqa: E402  (paleta centralitzada)
from app.timeline_base import (   # noqa: E402
    CURSOR_COLOR,
    LANE_DIVIDER,
    RULER_BG, RULER_TEXT,
    WF_BG, WF_ENV, WF_GAIN, WF_MID,
    fmt_pos, grid_levels, grid_plan,
)


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

    def update_mode(self, tempo_fix, bpm, bpb, offset=0.0):
        self._tempo_fix = bool(tempo_fix)
        self._bpm = float(bpm)
        self._bpb = int(bpb)
        self._offset = float(offset)
        self.update()

    def paint(self, painter, option, widget=None):
        p = painter
        p.setRenderHint(QPainter.Antialiasing, False)
        off = getattr(self, "_offset", 0.0)
        view_px = max(self._view_right - self._view_left, 1e-6) * self._pps
        for step, color, width in grid_levels(self._tempo_fix, self._bpm,
                                              self._bpb, self._pps, view_px):
            if step <= 1e-9:
                continue
            p.setPen(QPen(QColor(color), width))
            t = off + math.floor((self._view_left - off) / step) * step
            if t < 0:
                t = off
            while t <= self._view_right + 1e-9:
                if t >= 0:
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

    def update_mode(self, tempo_fix, bpm, bpb, offset=0.0):
        self._tempo_fix = bool(tempo_fix)
        self._bpm = float(bpm)
        self._bpb = int(bpb)
        self._offset = float(offset)
        self.update()

    def mode_label(self) -> str:
        """Text de l'indicador de mode del regle.

        Amb tempo: '120 BPM . 4/4' (BPM i pulsacions per compas). Sense tempo
        (mode lliure): 'Lliure'.
        """
        if self._tempo_fix:
            return f"{self._bpm:.0f} BPM \u00b7 {self._bpb}/4"
        return "Lliure"

    def paint(self, painter, option, widget=None):
        p = painter
        p.setRenderHint(QPainter.Antialiasing, False)
        off = getattr(self, "_offset", 0.0)
        rect = self.boundingRect()
        p.fillRect(rect, QColor(RULER_BG))
        p.setPen(QPen(QColor(theme.TL_WAVE_MID), 1))
        p.drawLine(QPointF(0, self._height - 1),
                   QPointF(rect.width(), self._height - 1))
        view_px = max(self._view_right - self._view_left, 1e-6) * self._pps
        plan = grid_plan(self._tempo_fix, self._bpm, self._bpb, self._pps,
                         view_px)
        col = {"bar": theme.TL_GRID_MEASURE, "beat": theme.TL_GRID_BEAT,
               "sub": theme.TL_GRID_SUB}
        # ticks dels nivells secundaris (els més fins que el d'etiqueta)
        for (sub, kind) in plan["lines"]:
            if sub <= 1e-9 or sub >= plan["label"] - 1e-9:
                continue
            p.setPen(QPen(QColor(col[kind]), 1))
            t = off + math.floor((self._view_left - off) / sub) * sub
            if t < 0:
                t = off
            while t <= self._view_right + 1e-9:
                if t >= 0:
                    x = (t - self._view_left) * self._pps
                    p.drawLine(QPointF(x, self._height - 4),
                               QPointF(x, self._height - 1))
                t += sub
        # ticks principals + etiquetes (AMB l'offset, com el GridLayer: si no,
        # les etiquetes queden desplaçades respecte de les linies del grid)
        step = plan["label"]
        font = QFont("Sans Serif", 8)
        p.setFont(font)
        fm = QFontMetricsF(font)
        t = off + math.floor((self._view_left - off) / step) * step
        if t < 0:
            t = off
        last_label_x = -1e9
        while t <= self._view_right + 1e-9:
            if t >= 0:
                x = (t - self._view_left) * self._pps
                p.setPen(QPen(QColor(theme.TL_GRID_MEASURE), 1))
                p.drawLine(QPointF(x, self._height - 8),
                           QPointF(x, self._height - 1))
                lab = fmt_pos(t, self._tempo_fix, self._bpm, self._bpb, off, step)
                wlab = fm.width(lab)
                if x - wlab / 2 > last_label_x:
                    p.setPen(QPen(QColor(RULER_TEXT), 1))
                    p.drawText(QPointF(x - wlab / 2, self._height - 11), lab)
                    last_label_x = x + wlab / 2
            t += step

        # Indicador de MODE (fix a la dreta del regle): '120 BPM . 4/4' o
        # 'Lliure'. Va al final perque quedi per sobre de les etiquetes.
        etq = self.mode_label()
        font_b = QFont("Sans Serif", 8, QFont.Bold)
        p.setFont(font_b)
        fmb = QFontMetricsF(font_b)
        wb = fmb.width(etq) + 12.0
        xb = rect.width() - wb - 4.0
        if xb > 2.0:
            p.fillRect(QRectF(xb, 3, wb, self._height - 8),
                       QColor(theme.TL_WAVE_MID))
            p.setPen(QPen(QColor(RULER_TEXT), 1))
            p.drawText(QPointF(xb + 6.0, self._height - 7), etq)


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
