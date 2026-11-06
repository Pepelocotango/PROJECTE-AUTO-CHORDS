"""Geometria pura del timeline (F2).

Funcions sense estat ni Qt per a conversions temps↔x, hit-test del loop,
selecció per rang/marquee i blocs de gest. `TimelineView` les embolcalla per
mantenir la mateixa API.
"""
from typing import Optional

from .timeline_base import LOOP_GRAB_PX


def time_to_x(t: float, view_left: float, x_offset: float, pps: float) -> float:
    return x_offset + (float(t) - view_left) * pps


def x_to_time(x: float, view_left: float, x_offset: float, pps: float) -> float:
    return view_left + (x - x_offset) / max(pps, 1e-9)


def loop_px(t: float, view_left: float, x_offset: float, pps: float) -> float:
    return x_offset + (float(t) - view_left) * pps


def loop_mode_at(x: float, loop_a, loop_b, view_left: float,
                 x_offset: float, pps: float):
    if loop_a is None or loop_b is None:
        return None
    xa = loop_px(loop_a, view_left, x_offset, pps)
    xb = loop_px(loop_b, view_left, x_offset, pps)
    if abs(x - xa) <= LOOP_GRAB_PX:
        return "a"
    if abs(x - xb) <= LOOP_GRAB_PX:
        return "b"
    if xa < x < xb:
        return "move"
    return None


def bloc_del_gest(multi, idx: int, kind: str = "chord"):
    sel = sorted(i for (k, i) in multi if k == kind)
    if idx not in sel:
        return idx, idx
    first = idx
    while first - 1 in sel:
        first -= 1
    last = idx
    while last + 1 in sel:
        last += 1
    return first, last


def selected_center(sel, chord_items, section_items) -> Optional[float]:
    kind, idx = sel
    if kind == "chord" and 0 <= idx < len(chord_items):
        it = chord_items[idx]
        return (it.t + it._next_t) / 2.0
    if kind == "section" and 0 <= idx < len(section_items):
        it = section_items[idx]
        return (it.ini + it.fi) / 2.0
    return None


def trams_tempo(mapa) -> list:
    return [tuple(t) for t in mapa.trams] if mapa is not None else []


def temps_item(kind: str, idx: int, acords, seccions, trams):
    if kind == "chord" and 0 <= idx < len(acords):
        return float(acords[idx][0])
    if kind == "section" and 0 <= idx < len(seccions):
        return float(seccions[idx][0])
    if kind == "tempo" and 0 <= idx < len(trams):
        return float(trams[idx][0])
    return None


def keys_dins_rang(acords, seccions, trams, lo: float, hi: float,
                   inclou_fi: bool = True, tempo: bool = False) -> set:
    lo, hi = sorted((float(lo), float(hi)))
    tol = 1e-6

    def _dins(t):
        if t < lo - tol:
            return False
        return (t <= hi + tol) if inclou_fi else (t < hi - tol)

    keys = set()
    for i, ac in enumerate(acords):
        if _dins(float(ac[0])):
            keys.add(("chord", i))
    for i, sec in enumerate(seccions):
        if _dins(float(sec[0])):
            keys.add(("section", i))
    if tempo:
        for i, tr in enumerate(trams):
            if _dins(float(tr[0])):
                keys.add(("tempo", i))
    return keys


def keys_dins_marc(acords, seccions, trams, durada, t0: float, t1: float,
                   chords: bool = True, sections: bool = True,
                   tempo: bool = True) -> set:
    t0, t1 = sorted((float(t0), float(t1)))
    durada = float(durada)
    tol = 1e-6
    keys = set()
    if chords:
        for i, a in enumerate(acords):
            ini = float(a[0])
            fi = (float(acords[i + 1][0])
                  if i + 1 < len(acords) else durada)
            if fi > t0 + tol and ini < t1 - tol:
                keys.add(("chord", i))
    if sections:
        for i, s in enumerate(seccions):
            ini, fi = float(s[0]), float(s[1])
            if fi > t0 + tol and ini < t1 - tol:
                keys.add(("section", i))
    if tempo:
        for i, tr in enumerate(trams):
            ini, fi = float(tr[0]), float(tr[1])
            if fi > t0 + tol and ini < t1 - tol:
                keys.add(("tempo", i))
    return keys
