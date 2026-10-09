#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
timeline_base.py — Base compartida de l'editor de timeline (DAW).

Conté les **constants de layout i colors** i les **utilitats de temps/snap**
que fan servir tots els altres mòduls de la timeline. És el mòdul de més
baix nivell (no depèn de cap altre mòdul de la timeline), extret de
`timeline.py` per poder-hi treballar sense un fitxer de ~1.800 línies.

Tot en català. Sense dependències noves.
"""
import math

from app import theme      # noqa: E402  (paleta centralitzada)


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
RULER_BG = theme.TL_RULER_BG
# Colors de l'ona (BGRA — ordre de memòria de QImage.Format_RGB32)
WF_BG = (0x1c, 0x15, 0x10)   # fons #10151c
WF_ENV = (0xff, 0xc8, 0x7a)  # envolupant #7ac8ff (blau brillant)
WF_MID = (0x50, 0x3e, 0x2c)  # línia central #2c3e50
WF_GAIN = 1.7  # amplificació de visualització de l'ona
WAVEFORM_BG = theme.TL_BG
LANE_BG_A = theme.TL_LANE_BG_A
LANE_BG_B = theme.TL_LANE_BG_B
LANE_DIVIDER = theme.TL_LANE_DIVIDER
RULER_TEXT = theme.TL_RULER_TEXT
WAVEFORM_COLOR = theme.TL_WAVEFORM
CHORD_FILL = theme.CLIP_FILL
CHORD_ACTIVE_FILL = theme.CLIP_ACTIVE_FILL
CHORD_TEXT = theme.CLIP_TEXT
CHORD_ACTIVE_TEXT = theme.CLIP_ACTIVE_TEXT
CHORD_BORDER = theme.CLIP_BORDER
CHORD_HANDLE = theme.CLIP_HANDLE
CHORD_HANDLE_ACTIVE = theme.CLIP_HANDLE_SELECTED
SECTION_FILLS = list(theme.SECTION_FILLS)
SECTION_TEXT = theme.SECTION_TEXT
CURSOR_COLOR = theme.TL_CURSOR
GUIDE_COLOR = theme.TL_GUIDE
SELECTION_COLOR = theme.CLIP_SELECTED_BORDER
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
              view_span: float, offset: float = 0.0) -> float:
    """Arrodoneix t al pas de snap adequat segons el zoom (view_span).

    Amb BPM: mai no s'arrodoneix al compàs sencer (massa gruixut) — com a
    màxim a un temps; segons el zoom, es va a corxera o setzena.
    Sense BPM: 0,1 s (o més fi si el zoom és molt proper).
    """
    off = float(offset)
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
    return round((t - off) / step) * step + off


def fmt_pos(t: float, tempo_fix: bool, bpm: float, bpb: int,
            offset: float = 0.0) -> str:
    """Formata t per al ruler o status: '12.3s' o '3.2' (compàs.beat).

    `offset` = segon on cau el compàs 1 (la graella hi comença).
    """
    if not tempo_fix:
        return f"{t:.1f}s"
    beat = 60.0 / max(bpm, 1e-9)
    # Sense clampar: abans de l'offset (el compàs 1) la graella és NEGATIVA
    # -> el silenci inicial es llegeix com un compte enrere (-1, -2...).
    beats = (t - float(offset)) / beat
    compas = math.floor(beats / bpb) + 1
    beat_idx = int(round(beats % bpb)) + 1
    if beat_idx > bpb:
        compas += 1
        beat_idx = 1
    return f"{compas}.{beat_idx}"


def grid_levels(tempo_fix, bpm, bpb, span):
    """Retorna [(step_s, color, width), ...] de menys a més important.

    `color` és un valor de color REAL (ja resolt des de `theme`), llest per
    passar-lo directament a `QColor(...)`. (Abans eren strings literals
    "theme.TL_GRID_*" -> `QColor` els considerava invàlids i les línies del
    grid sortien negres.)
    """
    if tempo_fix:
        beat = 60.0 / max(float(bpm), 1e-9)
        measure = beat * max(int(bpb), 1)
        levels = [(measure, theme.TL_GRID_MEASURE, 1)]
        if span <= measure * 16:
            levels.insert(0, (beat, theme.TL_GRID_BEAT, 1))
        if span <= beat * 8:
            levels.insert(0, (beat / 2.0, theme.TL_GRID_SUB, 1))
        return levels
    step = _best_step_free(span)
    levels = [(step, theme.TL_GRID_MEASURE, 1)]
    if span <= 30.0:
        levels.insert(0, (step / 5.0, theme.TL_GRID_SUB, 1))
    return levels
