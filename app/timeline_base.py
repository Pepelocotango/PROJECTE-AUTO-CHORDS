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
# Llindars en PIXELS (com els DAWs): un nivell de grid es dibuixa si el seu
# espaiat en px hi arriba; l'etiqueta del regle només es posa si hi cap.
MIN_LINE_PX = 8.0
MIN_LABEL_PX = 30.0


def _divisions(tempo_fix, bpm, bpb):
    """Llista de divisions (step_s, kind) de GRUIXUT a FI.

    kind: 'bar' (nivell gran), 'beat' (temps), 'sub' (subdivisió).
    """
    if tempo_fix:
        beat = 60.0 / max(float(bpm), 1e-9)
        measure = beat * max(int(bpb), 1)
        return [(measure, "bar"), (beat, "beat"),
                (beat / 2.0, "sub"), (beat / 4.0, "sub")]
    return [(600.0, "bar"), (300.0, "bar"), (60.0, "bar"), (30.0, "bar"),
            (10.0, "bar"), (5.0, "bar"), (2.0, "bar"), (1.0, "bar"),
            (0.5, "sub"), (0.2, "sub"), (0.1, "sub"), (0.05, "sub"),
            (0.02, "sub")]


def snap_step(tempo_fix, bpm, bpb, pps):
    """Divisió de snap/grid: la més fina que hi cap (px >= MIN_LINE_PX)."""
    pps = max(float(pps), 1e-9)
    divs = _divisions(tempo_fix, bpm, bpb)
    fit = [s for (s, _k) in divs if s * pps >= MIN_LINE_PX]
    return fit[-1] if fit else divs[-1][0]


def grid_plan(tempo_fix, bpm, bpb, pps, view_px, min_line_px=MIN_LINE_PX,
              min_label_px=MIN_LABEL_PX):
    """Pla ÚNIC de grid (font de veritat per a grid, regle i snap).

    Es decideix segons el **zoom en píxels** (com els DAWs), no per segons:
      - 'snap':  divisió de snap = la més fina que hi cap (px >= min_line_px).
      - 'lines': [(step, kind), ...] de gruixut a fi: el nivell gran més gruixut
                 **encara visible** (px <= view_px) + un de mig + el snap.
      - 'label': nivell de les etiquetes = el més gruixut que hi cap
                 (px >= min_label_px).
    """
    pps = max(float(pps), 1e-9)
    divs = _divisions(tempo_fix, bpm, bpb)
    fit = [(s, k) for (s, k) in divs if s * pps >= min_line_px]
    if not fit:
        snap, snap_k = divs[-1]
        return {"snap": snap, "lines": [(snap, snap_k)], "label": divs[0][0]}
    snap, snap_k = fit[-1]
    majors = [x for x in fit if x[0] * pps <= view_px] or [fit[0]]
    major = majors[0]
    lines = [major]
    if len(fit) >= 3:
        gm = math.sqrt(major[0] * snap)
        mid = min(fit, key=lambda x: abs(math.log(x[0] / gm)))
        if abs(mid[0] - major[0]) > 1e-9 and abs(mid[0] - snap) > 1e-9:
            lines.append(mid)
    if abs(lines[-1][0] - snap) > 1e-9:
        lines.append((snap, snap_k))
    # label: el MÉS FI que hi cap (densitat MÀXIMA sense solapar). El regle,
    # a més, salta les etiquetes que no hi caben segons l'amplada del text.
    cands = [s for (s, _k) in divs if s * pps >= min_label_px]
    lab = cands[-1] if cands else major[0]
    return {"snap": snap, "lines": lines, "label": lab}


def snap_time(t: float, tempo_fix: bool, bpm: float, bpb: int,
              pps: float, offset: float = 0.0) -> float:
    """Arrodoneix t a la divisió de grid actual (que depèn del zoom, en px).

    Fa servir el MATEIX `grid_plan` que el grid i el regle → sempre quadren.
    """
    step = snap_step(tempo_fix, bpm, bpb, pps)
    if step <= 0:
        return t
    off = float(offset)
    return round((t - off) / step) * step + off


def fmt_pos(t: float, tempo_fix: bool, bpm: float, bpb: int,
            offset: float = 0.0, step=None) -> str:
    """Formata t per al regle: 'm:ss[.d]' (temps) o 'compàs.beat' (tempo).

    `offset` = segon on cau el compàs 1 (la graella hi comença).
    `step` = pas de l'etiqueta; en mode temps, si és < 1 s s'hi afegeix un
    decimal (m:ss.d), com fan els DAWs.
    """
    if not tempo_fix:
        neg = t < -1e-9
        tt = abs(float(t))
        m = int(tt // 60)
        s = tt - m * 60
        if step is not None and step < 1.0:
            txt = f"{m}:{s:04.1f}"              # m:ss.d
        else:
            txt = f"{m}:{int(round(s)):02d}"    # m:ss
        return ("-" if neg else "") + txt
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


def grid_levels(tempo_fix, bpm, bpb, pps, view_px):
    """[(step_s, color, width), ...] de menys a més important (GridLayer).

    `color` és un valor de color REAL (resolt de `theme`). Deriva del **pla
    únic** (`grid_plan`), així el grid i el regle sempre coincideixen.
    """
    col = {"bar": theme.TL_GRID_MEASURE, "beat": theme.TL_GRID_BEAT,
           "sub": theme.TL_GRID_SUB}
    plan = grid_plan(tempo_fix, bpm, bpb, pps, view_px)
    # de fi a gruixut, perquè els nivells gruixuts es pintin al damunt
    return [(s, col[k], 1) for (s, k) in reversed(plan["lines"])]
