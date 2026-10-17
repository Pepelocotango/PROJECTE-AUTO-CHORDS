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
# Tolerància (en PÍXELS, per tant depèn del zoom) per enganxar una edició a una
# MARCA del model. És el «snap distance» dels DAWs (Reaper), i el que fa que
# l'snap als events sigui visual i no un valor de temps fix.
SNAP_MARCA_PX = 10.0


# -----------------------------------------------------------------------------
# Utilitats de temps i snap
# -----------------------------------------------------------------------------
# Llindars en PIXELS (com els DAWs): un nivell de grid es dibuixa si el seu
# espaiat en px hi arriba; l'etiqueta del regle només es posa si hi cap.
MIN_LINE_PX = 8.0
MIN_LABEL_PX = 30.0


def _divisions(tempo_fix, bpm, bpb, mapa=None):
    """Llista de divisions (step_s, kind) de GRUIXUT a FI.

    kind: 'bar' (nivell gran), 'beat' (temps), 'sub' (subdivisió).
    Amb un `mapa` de tempo/compàs **variable**, les durades són les del mapa
    (representatives, per decidir el nivell pel zoom); si és constant, la via
    de sempre (idèntica).
    """
    if tempo_fix:
        if mapa is not None and not mapa.es_constant():
            bar, beat, _sub = mapa.durations(mapa.offset)
            return [(bar, "bar"), (beat, "beat"),
                    (beat / 2.0, "sub"), (beat / 4.0, "sub")]
        beat = 60.0 / max(float(bpm), 1e-9)
        measure = beat * max(int(bpb), 1)
        return [(measure, "bar"), (beat, "beat"),
                (beat / 2.0, "sub"), (beat / 4.0, "sub")]
    return [(600.0, "bar"), (300.0, "bar"), (60.0, "bar"), (30.0, "bar"),
            (10.0, "bar"), (5.0, "bar"), (2.0, "bar"), (1.0, "bar"),
            (0.5, "sub"), (0.2, "sub"), (0.1, "sub"), (0.05, "sub"),
            (0.02, "sub")]


def snap_step(tempo_fix, bpm, bpb, pps, mapa=None):
    """Divisió de snap/grid: la més fina que hi cap (px >= MIN_LINE_PX)."""
    pps = max(float(pps), 1e-9)
    divs = _divisions(tempo_fix, bpm, bpb, mapa)
    fit = [s for (s, _k) in divs if s * pps >= MIN_LINE_PX]
    return fit[-1] if fit else divs[-1][0]


def grid_plan(tempo_fix, bpm, bpb, pps, view_px, min_line_px=MIN_LINE_PX,
              min_label_px=MIN_LABEL_PX, mapa=None):
    """Pla ÚNIC de grid (font de veritat per a grid, regle i snap).

    Es decideix segons el **zoom en píxels** (com els DAWs), no per segons:
      - 'snap':  divisió de snap = la més fina que hi cap (px >= min_line_px).
      - 'lines': [(step, kind), ...] de gruixut a fi: el nivell gran més gruixut
                 **encara visible** (px <= view_px) + un de mig + el snap.
      - 'label': nivell de les etiquetes = el més gruixut que hi cap
                 (px >= min_label_px).
    """
    pps = max(float(pps), 1e-9)
    divs = _divisions(tempo_fix, bpm, bpb, mapa)
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


def grid_positions(view_left, view_right, step, offset=0.0, tol=1e-9,
                   mapa=None, kind=None):
    """Genera les posicions de graella ``t = offset + k*step`` dins de la vista.

    Cada posició es calcula a partir de l'**índex enter** ``k`` — MAI acumulant
    ``t += step``. Amb acumulació, l'error de coma flotant es va sumant i, al
    regle/grid, els inicis de compàs acabaven sortint com «(N-1).4» en lloc de
    «N.1» (i les línies, desplaçades).

    S'usa idènticament al regle i al grid → quadren sempre.
    """
    if mapa is not None and kind is None and not mapa.es_constant():
        # Dedueix el nivell musical del `step` (per a les capes que no el saben).
        bar_s, beat_s, _s = mapa.durations(float(view_left))
        if step is not None and step >= bar_s - 1e-9:
            kind = "bar"
        elif step is not None and step >= beat_s - 1e-9:
            kind = "beat"
        else:
            kind = "sub"
    if mapa is not None and kind is not None and not mapa.es_constant():
        # Graella MUSICAL del mapa (l'espaiat varia amb el tempo/compàs).
        for t in mapa.grid_lines(float(view_left), float(view_right), kind):
            yield t
        return
    if step is None or step <= tol:
        return
    k = math.floor((view_left - float(offset)) / step)
    t = float(offset) + k * step
    while t <= view_right + tol:
        yield t
        k += 1
        t = float(offset) + k * step


# Tolerància (en píxels) per agafar les vores del loop A/B al regle.
LOOP_GRAB_PX = 6.0


def loop_after_drag(mode, t, t0, a0, b0, durada, min_len=0.05):
    """Nou interval (A, B) del loop després d'arrossegar al regle.

    - ``'a'``: mou el costat **A** (l'inici del loop); B no canvia.
    - ``'b'``: mou el costat **B** (el final); A no canvia.
    - ``'move'``: desplaça el loop **sencer** (manté la durada).

    ``t`` = temps actual (ja amb snap); ``t0`` = temps on va començar
    l'arrossegada (només per a ``'move'``). El resultat queda sempre dins de
    ``[0, durada]`` amb ``A < B`` (separació mínima ``min_len``).
    """
    a0 = float(a0)
    b0 = float(b0)
    durada = float(durada)
    if mode == "a":
        a = max(0.0, min(float(t), b0 - min_len))
        return (a, b0)
    if mode == "b":
        b = min(durada, max(float(t), a0 + min_len))
        return (a0, b)
    if mode == "move":
        length = b0 - a0
        na = a0 + (float(t) - float(t0))
        na = max(0.0, min(durada - length, na))
        return (na, na + length)
    return (a0, b0)


def snap_time(t: float, tempo_fix: bool, bpm: float, bpb: int,
              pps: float, offset: float = 0.0, mapa=None) -> float:
    """Arrodoneix t a la divisió de grid actual (que depèn del zoom, en px).

    Fa servir el MATEIX `grid_plan` que el grid i el regle → sempre quadren.
    """
    if mapa is not None and not mapa.es_constant():
        bar_s, beat_s, sub_s = mapa.durations(t)
        step = snap_step(tempo_fix, bpm, bpb, pps, mapa)
        if step <= 0:
            return t
        if step >= bar_s - 1e-9:
            return mapa.snap(t, ("bars", 1))
        if step >= beat_s - 1e-9:
            return mapa.snap(t, ("beat", 1.0))
        if step >= sub_s - 1e-9:
            return mapa.snap(t, ("beat", 0.5))
        return mapa.snap(t, ("beat", 0.25))
    step = snap_step(tempo_fix, bpm, bpb, pps)
    if step <= 0:
        return t
    off = float(offset)
    return round((t - off) / step) * step + off


def fmt_pos(t: float, tempo_fix: bool, bpm: float, bpb: int,
            offset: float = 0.0, step=None, mapa=None) -> str:
    """Formata t per al regle: 'm:ss[.d]' (temps) o 'compàs.beat[.subdivisió]' (tempo).

    `offset` = segon on cau el compàs 1 (la graella hi comença).
    `step` = pas de l'etiqueta. Quan és més fi que el beat, es mostra el 3r
    camp (`compàs.beat.subdivisió`), com en DAWs professionals.
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
    if mapa is not None and not mapa.es_constant():
        c, b, sub = mapa.pos(t)
        _bar_s, beat_s, _sub_s = mapa.durations(t)
        if step is not None and 0 < step < beat_s - 1e-9:
            return f"{c}.{b}.{sub}"
        return f"{c}.{b}"
    beat = 60.0 / max(bpm, 1e-9)
    # Sense clampar: abans de l'offset (el compàs 1) la graella és NEGATIVA
    # -> el silenci inicial es llegeix com un compte enrere (-1, -2...).
    # `round(...,6)` neteja el soroll de coma flotant (ex. 27.999999999999996):
    # sense això, una posició d'INICI de compàs faria `floor(beats % bpb) ==
    # bpb-1` i l'etiqueta sortiria com «7.4» en lloc de «8.1» (bug del regle).
    beats = round((t - float(offset)) / beat, 6)
    compas = math.floor(beats / bpb) + 1
    beat_idx = int(math.floor(beats % bpb)) + 1
    if beat_idx > bpb:
        compas += 1
        beat_idx = 1
    if step is not None and step > 0 and step < beat - 1e-9:
        divs = max(1, int(round(beat / step)))
        phase = beats - math.floor(beats)
        if phase < 0:
            phase += 1.0
        sub_idx = int(math.floor(phase * divs)) + 1
        if sub_idx > divs:
            sub_idx = divs
        return f"{compas}.{beat_idx}.{sub_idx}"
    return f"{compas}.{beat_idx}"


def is_bar_start_label(label: str) -> bool:
    """True per a etiquetes de l'inici de compàs, p.e. '1.1', '2.1', '1.1.1'."""
    if label is None:
        return False
    text = str(label).strip()
    if not text or ":" in text or "." not in text:
        return False
    try:
        return int(text.split(".")[-1]) == 1
    except ValueError:
        return False


def grid_levels(tempo_fix, bpm, bpb, pps, view_px, mapa=None):
    """[(step_s, color, width), ...] de menys a més important (GridLayer).

    `color` és un valor de color REAL (resolt de `theme`). Deriva del **pla
    únic** (`grid_plan`), així el grid i el regle sempre coincideixen.
    """
    col = {"bar": theme.TL_GRID_MEASURE, "beat": theme.TL_GRID_BEAT,
           "sub": theme.TL_GRID_SUB}
    plan = grid_plan(tempo_fix, bpm, bpb, pps, view_px, mapa=mapa)
    # de fi a gruixut, perquè els nivells gruixuts es pintin al damunt
    return [(s, col[k], 1) for (s, k) in reversed(plan["lines"])]
