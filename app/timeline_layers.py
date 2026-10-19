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
from typing import Optional

import numpy as np
from PyQt5.QtCore import QLineF, QPointF, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import (
    QBrush, QColor, QFont, QFontMetricsF, QImage, QPainter, QPen, QPixmap,
)
from PyQt5.QtWidgets import (
    QGraphicsItem, QGraphicsLineItem, QGraphicsObject, QGraphicsPixmapItem,
    QGraphicsRectItem,
)

from app import graella, theme      # noqa: E402  (paleta centralitzada)
from app.timeline_base import (   # noqa: E402
    CHORD_HANDLE, CHORD_HANDLE_ACTIVE, CURSOR_COLOR, LANE_DIVIDER,
    RULER_BG, RULER_TEXT, SECTION_FILLS, SECTION_TEXT, SELECTION_COLOR,
    WF_BG, WF_ENV, WF_GAIN, WF_MID,
    fmt_pos, grid_levels, grid_plan, grid_positions, is_bar_start_label,
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
        self._beat_type = 4
        self._mapa = None
        self._divisio = ""      # divisió manual del snap ("" = automàtic)
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

    def update_mode(self, tempo_fix, bpm, bpb, offset=0.0, beat_type=4,
                    mapa=None):
        self._tempo_fix = bool(tempo_fix)
        self._bpm = float(bpm)
        self._bpb = int(bpb)
        self._beat_type = int(beat_type or 4)
        self._offset = float(offset)
        self._mapa = mapa
        self.update()

    def set_divisio(self, divisio):
        """Divisió manual del snap ('' = automàtic); afecta el grid visual."""
        self._divisio = str(divisio or "")
        self.update()

    def paint(self, painter, option, widget=None):
        p = painter
        p.setRenderHint(QPainter.Antialiasing, False)
        off = getattr(self, "_offset", 0.0)
        view_px = max(self._view_right - self._view_left, 1e-6) * self._pps
        div = graella.DIVISIONS.get(self._divisio) if self._divisio else None
        for step, color, width in grid_levels(self._tempo_fix, self._bpm,
                                              self._bpb, self._pps, view_px,
                                              mapa=self._mapa, divisio=div):
            if step <= 1e-9:
                continue
            p.setPen(QPen(QColor(color), width))
            # posicions per índex (sense acumular → sense deriva de coma flotant)
            for t in grid_positions(self._view_left, self._view_right, step, off,
                                    mapa=self._mapa):
                if t >= 0:
                    x = (t - self._view_left) * self._pps
                    p.drawLine(QPointF(x, 0), QPointF(x, self._height))


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
        self._beat_type = 4
        self._mapa = None
        self._divisio = ""      # divisió manual del snap ("" = automàtic)
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

    def update_mode(self, tempo_fix, bpm, bpb, offset=0.0, beat_type=4,
                    mapa=None):
        self._tempo_fix = bool(tempo_fix)
        self._bpm = float(bpm)
        self._bpb = int(bpb)
        self._beat_type = int(beat_type or 4)
        self._offset = float(offset)
        self._mapa = mapa
        self.update()

    def set_divisio(self, divisio):
        """Divisió manual del snap ('' = automàtic); afecta el regle/grid."""
        self._divisio = str(divisio or "")
        self.update()

    def mode_label(self) -> str:
        """Text de l'indicador de mode del regle.

        Amb tempo: '120 BPM · 3/4' / '120 BPM · 6/8' (BPM i compàs). Sense tempo
        (mode lliure): 'Lliure'.
        """
        if self._tempo_fix:
            return f"{self._bpm:.0f} BPM \u00b7 {self._bpb}/{self._beat_type}"
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
        div = graella.DIVISIONS.get(self._divisio) if self._divisio else None
        plan = grid_plan(self._tempo_fix, self._bpm, self._bpb, self._pps,
                         view_px, mapa=self._mapa, divisio=div)
        col = {"bar": theme.TL_GRID_MEASURE, "beat": theme.TL_GRID_BEAT,
               "sub": theme.TL_GRID_SUB}
        # ticks dels nivells secundaris (els més fins que el d'etiqueta)
        for (sub, kind) in plan["lines"]:
            if sub <= 1e-9 or sub >= plan["label"] - 1e-9:
                continue
            kind_name = kind[0] if isinstance(kind, tuple) else kind
            p.setPen(QPen(QColor(col[kind_name]), 1))
            for t in grid_positions(self._view_left, self._view_right, sub, off,
                                    mapa=self._mapa):
                if t >= 0:
                    x = (t - self._view_left) * self._pps
                    p.drawLine(QPointF(x, self._height - 4),
                               QPointF(x, self._height - 1))
        # ticks principals + etiquetes (AMB l'offset, com el GridLayer: si no,
        # les etiquetes queden desplaçades respecte de les linies del grid)
        step = plan["label"]
        font = QFont("Sans Serif", 8)
        p.setFont(font)
        fm = QFontMetricsF(font)
        last_label_x = -1e9
        # posicions per índex (sense acumular → les etiquetes d'inici de compàs
        # ja no deriven a «(N-1).4»)
        for t in grid_positions(self._view_left, self._view_right, step, off,
                                mapa=self._mapa):
            if t >= 0:
                x = (t - self._view_left) * self._pps
                p.setPen(QPen(QColor(theme.TL_GRID_MEASURE), 1))
                p.drawLine(QPointF(x, self._height - 8),
                           QPointF(x, self._height - 1))
                lab = fmt_pos(t, self._tempo_fix, self._bpm, self._bpb, off,
                              step, mapa=self._mapa)
                is_bar = is_bar_start_label(lab)
                label_font = QFont("Sans Serif", 9 if is_bar else 8,
                                   QFont.Bold if is_bar else QFont.Normal)
                p.setFont(label_font)
                fm = QFontMetricsF(label_font)
                wlab = fm.width(lab)
                # La col·lisió es calcula amb la posició SENSE clamp; si no,
                # la primera etiqueta (desplaçada a x=2) feia saltar la segona.
                label_left = x - wlab / 2
                if label_left > last_label_x:
                    tx = label_left
                    if tx < 2.0:
                        tx = 2.0
                    elif tx + wlab > rect.width() - 2.0:
                        tx = max(2.0, rect.width() - 2.0 - wlab)
                    if is_bar:
                        bg = QColor(theme.TL_GRID_MEASURE)
                        bg.setAlpha(90)
                        p.fillRect(QRectF(tx - 3, self._height - 18,
                                          wlab + 6, 13), bg)
                    p.setPen(QPen(QColor(theme.TL_GRID_MEASURE if is_bar else RULER_TEXT), 1))
                    p.drawText(QPointF(tx, self._height - 11), lab)
                    last_label_x = label_left + wlab + 4.0

        # CANVIS de tempo/compàs (com la «tempo track» d'un DAW): un marcador a
        # cada frontera del mapa, amb el valor nou.
        mapa = getattr(self, "_mapa", None)
        if mapa is not None and not mapa.es_constant():
            font_m = QFont("Sans Serif", 7, QFont.Bold)
            p.setFont(font_m)
            for s in mapa.trams:
                if s.ini <= self._view_left - 1e-9 or \
                        s.ini > self._view_right + 1e-9:
                    continue
                x = (s.ini - self._view_left) * self._pps
                pen = QPen(QColor(theme.TL_GRID_MEASURE), 2)
                p.setPen(pen)
                p.drawLine(QPointF(x, 0), QPointF(x, self._height - 1))
                txt = f"{s.bpm:g} · {s.num}/{s.den}"
                p.setPen(QPen(QColor(RULER_TEXT), 1))
                p.drawText(QPointF(x + 3, 9), txt)

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


# -----------------------------------------------------------------------------
# TempoLayer — la pista de TEMPO i COMPÀS (blocs de cada tros del mapa)
# -----------------------------------------------------------------------------
class TempoLayer(QGraphicsObject):
    """Pista EDITABLE del mapa de **BPM/compàs** (un bloc per tros del mapa).

    Només es mostra en mode **BPM·compàs** i amb mapa **variable** (amb un sol
    tros no hi ha res a editar; tot es comporta com abans). Els gestos són els
    mateixos que a la resta de pistes: **clic** a un bloc → diàleg per al BPM i
    el compàs; **arrossegar una vora** → on canvia el tempo (el veí s'ajusta);
    **botó dret** → menú (afegir/eliminar).
    """

    tramSelected = pyqtSignal(int)         # selecció d'un bloc (índex)
    tramClicked = pyqtSignal(int)          # doble-clic a un bloc (índex)
    tramMoved = pyqtSignal(int, str, float)   # vora soltada (índex, vora, t)
    menuRequested = pyqtSignal(int, float)    # botó dret (índex; -1=fora, t)

    def __init__(self, height, pps, x_offset, view_left, view_right, top=0,
                 parent=None):
        super().__init__(parent)
        self._height = int(height)
        self._pps = float(pps)
        self._x_offset = float(x_offset)
        self._view_left = float(view_left)
        self._view_right = float(view_right)
        self._mapa = None
        self._actiu = True
        self._top = float(top)
        self._press = None
        self._t_guia = None
        self._sel = -1          # bloc seleccionat (resaltat)
        self.setZValue(2)
        self.setPos(self._x_offset, self._top)
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.LeftButton | Qt.RightButton)

    def boundingRect(self):
        return QRectF(0, 0, max(1.0, (self._view_right - self._view_left) *
                                self._pps), self._height)

    def update_geometry(self, pps, x_offset, view_left, view_right):
        self._pps = float(pps)
        self._x_offset = float(x_offset)
        self._view_left = float(view_left)
        self._view_right = float(view_right)
        self.prepareGeometryChange()
        self.setPos(self._x_offset, self._top)
        self.update()

    def select(self, idx):
        """Marca el bloc `idx` com a seleccionat (o -1 per a cap)."""
        if idx != self._sel:
            self._sel = idx
            self.update()

    def deselecciona(self):
        """Treu el resaltat del bloc de BPM/compàs (clic al fons)."""
        if self._sel != -1:
            self._sel = -1
            self.update()

    def set_mapa(self, mapa, actiu=True):
        """`mapa` = el TempoMap; `actiu` = mode BPM·compàs (si no, pista buida)."""
        self._mapa = mapa
        self._actiu = bool(actiu)
        self.update()

    # -- geometria/hit-test ---------------------------------------------
    def _visible(self):
        # Es mostra sempre que el mode siga BPM·compàs (encara que el mapa
        # siga d'un sol tros: així s'hi pot fer botó dret per afegir canvis).
        return self._actiu and self._mapa is not None

    def _idx_a(self, x):
        """Índex del bloc a la x de l'item, o -1."""
        if not self._visible():
            return -1
        for i, s in enumerate(self._mapa.trams):
            x0 = (s.ini - self._view_left) * self._pps
            x1 = (s.fi - self._view_left) * self._pps
            if x0 - 2 <= x <= x1 + 2:
                return i
        return -1

    def _zona(self, x):
        """(índex, zona) — zona ∈ {ini, fi, cos, None}."""
        i = self._idx_a(x)
        if i < 0:
            return -1, None
        n = len(self._mapa.trams)
        s = self._mapa.trams[i]
        x0 = (s.ini - self._view_left) * self._pps
        x1 = (s.fi - self._view_left) * self._pps
        if i > 0 and x <= x0 + 5:
            return i, "ini"
        if i + 1 < n and x >= x1 - 5:
            return i, "fi"
        return i, "cos"

    # -- esdeveniments --------------------------------------------------
    @staticmethod
    def _cursor_de_zona(z):
        """Cursor de cada zona — **idèntic** al d'acords i estructura (#11).

        ↔ a les vores (es pot arrossegar), mà **oberta** al cos (mou el punt de
        canvi) i fletxa al buit. És una funció pura a posta: així es pot provar
        sense haver de fabricar un event de *hover* (PyQt5 no en deixa).
        """
        if z in ("ini", "fi"):
            return Qt.SizeHorCursor
        if z == "cos":
            return Qt.OpenHandCursor
        return Qt.ArrowCursor

    def hoverMoveEvent(self, ev):
        _i, z = self._zona(ev.pos().x())
        self.setCursor(self._cursor_de_zona(z))
        super().hoverMoveEvent(ev)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.RightButton:
            i, _z = self._zona(ev.pos().x())
            # Paritat amb els clips (regla d'or #11): el botó dret SELECCIONA
            # el tram abans d'obrir el menú (si no, Copia/Retalla no tindrien
            # sobre què actuar). Un clic al buit (i = -1) no toca la selecció.
            self.tramSelected.emit(i)
            self.menuRequested.emit(
                i, self._view_left + ev.pos().x() / max(self._pps, 1e-9))
            ev.accept()
            return
        i, z = self._zona(ev.pos().x())
        self.tramSelected.emit(i)          # la selecció la mana el timeline
        if z in ("ini", "fi"):
            self.setCursor(Qt.SizeHorCursor)
        elif z == "cos":
            self.setCursor(Qt.ClosedHandCursor)
        self._press = ((i, z), ev.pos().x())
        ev.accept()

    def mouseMoveEvent(self, ev):
        if self._press is None:
            return
        (i, z), x0 = self._press
        # Les vores (i, en un DAW, el COS del bloc = el punt de canvi) mouen
        # on comenca el tros; el primer bloc (index 0) te l'inici fix.
        if ((z in ("ini", "fi")) or (z == "cos" and i > 0)) \
                and abs(ev.pos().x() - x0) > 5:
            self._t_guia = self._view_left + ev.pos().x() / max(self._pps, 1e-9)
            self.update()
        ev.accept()

    def mouseDoubleClickEvent(self, ev):
        i, _z = self._zona(ev.pos().x())
        if i >= 0:
            self.tramClicked.emit(i)
        ev.accept()

    def mouseReleaseEvent(self, ev):
        p = self._press
        self._press = None
        guia, self._t_guia = self._t_guia, None
        self.update()
        if p is None:
            return
        (i, z), _x0 = p
        if guia is not None and i >= 0 and (z in ("ini", "fi")
                                            or (z == "cos" and i > 0)):
            self.tramMoved.emit(i, "ini" if z == "cos" else z, float(guia))
        ev.accept()

    # -- pintura --------------------------------------------------------
    def paint(self, painter, option, widget=None):
        if not self._visible():
            return
        p = painter
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = self.boundingRect()
        bg = QColor(theme.TL_LANE_BG_B)
        bg.setAlphaF(0.18)                 # fons subtil, com els altres carrils
        p.fillRect(rect, bg)
        fills = [QColor(c) for c in SECTION_FILLS]
        font = QFont("Sans Serif", 9, QFont.Bold)
        for i, s in enumerate(self._mapa.trams):
            x0 = (s.ini - self._view_left) * self._pps
            x1 = (s.fi - self._view_left) * self._pps
            if x1 < 0 or x0 > rect.width():
                continue
            x0, x1 = max(0.0, x0), min(rect.width(), x1)
            # Mateix tracte visual que les SECCIONS (bloc arrodonit + nanses
            # + text centrat), pero en mitja alcada.
            sel = (i == self._sel)
            fill = QColor(fills[hash("tempo") % len(fills)])
            fill.setAlpha(180)                 # semitransparent, com les altres
            if sel:
                fill = fill.lighter(140)       # resaltat de selecció
            p.setBrush(QBrush(fill))
            p.setPen(QPen(QColor(SELECTION_COLOR if sel
                                 else theme.CLIP_SECTION_BORDER),
                          2 if sel else 1))
            bx = QRectF(x0 + 1, 1, max(2.0, x1 - x0 - 2), self._height - 3)
            p.drawRoundedRect(bx, 5, 5)
            if bx.width() > 20:
                p.setPen(QPen(QColor(CHORD_HANDLE_ACTIVE if sel
                                     else CHORD_HANDLE), 2))
                p.drawLine(QPointF(x0 + 4, 4), QPointF(x0 + 4, self._height - 6))
                p.drawLine(QPointF(x1 - 4, 4), QPointF(x1 - 4, self._height - 6))
            p.setPen(QPen(QColor(SECTION_TEXT), 1))
            p.setFont(font)
            p.drawText(bx, Qt.AlignCenter, f"{s.bpm:g} · {s.num}/{s.den}")
        if self._t_guia is not None:
            xg = (self._t_guia - self._view_left) * self._pps
            p.setPen(QPen(QColor(theme.TL_GUIDE if hasattr(theme, "TL_GUIDE")
                                 else RULER_TEXT), 1))
            p.drawLine(QPointF(xg, 0), QPointF(xg, self._height))
