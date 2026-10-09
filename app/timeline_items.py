#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
timeline_items.py — Elements editables de l'editor de timeline (DAW).

Agrupa els QGraphicsItem que l'usuari pot arrossegar/editar, extrets de
`timeline.py` per alleugerir-lo:

- ChordItem    — un acord (caixa amb nanses + edició inline del nom).
- SectionItem  — una secció (rectangle amb nanses + etiqueta).
- RenameEditor — QLineEdit overlay per a l'edició inline del nom.

Tot en català. Sense dependències noves.
"""
from typing import Callable, Optional

from PyQt5.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QFont, QFontMetricsF, QPainter, QPen
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsObject, QLineEdit, QWidget

from app import theme      # noqa: E402  (paleta centralitzada)
from app.timeline_base import (   # noqa: E402
    CHORD_ACTIVE_FILL, CHORD_ACTIVE_TEXT, CHORD_BORDER, CHORD_FILL,
    CHORD_HANDLE, CHORD_HANDLE_ACTIVE, CHORD_TEXT,
    SECTION_FILLS,
    SECTION_TEXT, SELECTION_COLOR,
)


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
                             else CHORD_BORDER), theme.CLIP_SELECTED_WIDTH if self._selected else 1)
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
                             else theme.CLIP_SECTION_BORDER), theme.CLIP_SELECTED_WIDTH if self._selected else 1)
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
