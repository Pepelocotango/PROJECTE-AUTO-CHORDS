#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Detecció de beats amb motors intercanviables i sensibilitat ajustable.

La sortida és **diagnòstic**: BPM, beats i downbeats en segons. No toca el
model de tempo/compàs; la finestra decideix si aplica el BPM o només pinta les
línies.

Motors:
- ``nostre``: `app.tempo` (envolupant d'onsets + DP d'Ellis).
- ``qm``: `qm-barbeattracker` de Queen Mary via el nostre host Vamp.

La sensibilitat és un valor 0–100:
- 0 = estable / estricte (menys canvis de tempo).
- 100 = sensible / flexible (accepta més variació).

Per al motor intern es tradueix a `tightness` (100 → 10). Per a QM es tradueix
a `alpha` (0.99 → 0.1). El valor és una comoditat d'usuari, no una mesura
absoluta: cada motor té la seua escala interna.
"""
from __future__ import annotations

import csv
import math
import os
import statistics
import tempfile

from . import pipeline, tempo, tempo_map

MOTORS = ("nostre", "qm")

_QM_BEATS = "vamp:qm-vamp-plugins:qm-barbeattracker:beats"
_QM_BARS = "vamp:qm-vamp-plugins:qm-barbeattracker:bars"
# Per al mode «només beats» no demanem bars: el tempotracker no agrupa en
# compassos ni necessita bpb.
_QM_ONLY_BEATS = "vamp:qm-vamp-plugins:qm-tempotracker:beats"


def _limita_sensibilitat(valor):
    try:
        v = float(valor)
    except (TypeError, ValueError):
        v = 50.0
    if not math.isfinite(v):
        v = 50.0
    return max(0.0, min(100.0, v))


def tightness_de_sensibilitat(sensibilitat):
    """0 = estable (100), 100 = flexible (10)."""
    s = _limita_sensibilitat(sensibilitat)
    return 100.0 - 0.9 * s


def alpha_de_sensibilitat(sensibilitat):
    """0 = estable (0.99), 100 = flexible (0.10)."""
    s = _limita_sensibilitat(sensibilitat)
    return 0.99 - 0.89 * s / 100.0


def _qm_temps(transform, wav, params, log):
    """Primera columna d'un output QM amb paràmetres (.n3)."""
    d = tempfile.mkdtemp(prefix="ac_qm_")
    out = os.path.join(d, "x.csv")
    try:
        pipeline.executa_transform(transform, out, wav, log, params)
        temps = []
        if os.path.exists(out):
            with open(out, newline="", encoding="utf-8") as f:
                for fila in csv.reader(f):
                    try:
                        temps.append(float(fila[0]))
                    except (ValueError, IndexError):
                        continue
        return sorted({round(t, 6) for t in temps if math.isfinite(t)})
    finally:
        pipeline.esborra_tmp([d])


def _bpm_de_beats(beats):
    if len(beats) < 2:
        return None
    intervals = [b - a for a, b in zip(beats, beats[1:]) if b > a]
    if not intervals:
        return None
    # Si hi ha forats, la mediana es mes robusta que la mitjana.
    bpm = 60.0 / statistics.median(intervals)
    # Guardrail: rebutjar BPM fora de banda (evita BPM absurds per forats grans).
    from app import limits
    if not (limits.BPM_MIN <= bpm <= limits.BPM_MAX):
        return None
    return bpm


def _detecta_nostre(wav, log, sensibilitat, bpb, den, bpm_hint,
                    bpm_min, bpm_max, preferit, nomes_beats=False):
    log(f"beats: motor nostre · sensibilitat {sensibilitat:.0f}%")
    # No deixar que None sobreescriga els defaults del motor: si no, es perd
    # el prior 85–150 i el detector pot triar la meitat (p. ex. 66 en lloc de
    # 132) en temes amb polsos forts a la subdivisió.
    bpm_min = tempo.BPM_MIN if bpm_min is None else bpm_min
    bpm_max = tempo.BPM_MAX if bpm_max is None else bpm_max
    preferit = tempo.BPM_PREFERIT if preferit is None else preferit
    bpm = tempo.detecta_bpm(wav, log, bpm_min=bpm_min, bpm_max=bpm_max,
                            preferit=preferit)
    if not bpm and bpm_hint:
        bpm = float(bpm_hint)
    tight = tightness_de_sensibilitat(sensibilitat)
    beats, base = tempo.segueix_beats(
        wav, log, bpm=bpm, bpm_min=bpm_min, bpm_max=bpm_max,
        preferit=preferit, tightness=tight)
    if bpm is None:
        bpm = base
    bars = []
    if beats and not nomes_beats:
        try:
            durada = float(pipeline.wav_info(wav)["durada"])
            trams, offset = tempo.beats_a_trams(
                beats, durada, num=int(bpb), den=int(den), offset=None)
            if trams:
                bars = [float(b[1]) for b in
                        tempo_map.TempoMap(trams, offset=offset).compassos()]
        except Exception as e:  # noqa: BLE001
            log(f"beats: no s'han pogut derivar els compassos ({e})")
    return {
        "motor": "nostre",
        "bpm": None if nomes_beats else (
            float(bpm) if bpm is not None else None),
        "beats": beats,
        "downbeats": bars,
        "sensibilitat": sensibilitat,
        "parametre": {"tightness": tight},
    }


def _detecta_qm(wav, log, sensibilitat, bpb, bpm_hint,
                nomes_beats=False):
    log(f"beats: motor QM · sensibilitat {sensibilitat:.0f}%")
    alpha = alpha_de_sensibilitat(sensibilitat)
    params = {
        "alpha": f"{alpha:.3f}",
        "inputtempo": str(int(round(float(bpm_hint or 120.0)))),
        "constraintempo": "0",
    }
    if not nomes_beats:
        params["bpb"] = str(max(1, int(bpb)))
        beats = _qm_temps(_QM_BEATS, wav, params, log)
        bars = _qm_temps(_QM_BARS, wav, params, log)
        bpm = pipeline.detecta_bpm_qm(wav, log)
        if bpm is None:
            bpm = _bpm_de_beats(beats)
    else:
        # qm-tempotracker: només beats, sense bars ni bpb. El tempo intern
        # del tracker només servix per seguir el pols; no s'exporta.
        beats = _qm_temps(_QM_ONLY_BEATS, wav, params, log)
        bars = []
        bpm = None
    return {
        "motor": "qm",
        "bpm": float(bpm) if bpm is not None else None,
        "beats": beats,
        "downbeats": bars,
        "sensibilitat": sensibilitat,
        "parametre": {"alpha": alpha},
    }


def detecta(wav, motor="nostre", sensibilitat=50.0, bpb=4, den=4,
            bpm_hint=None, bpm_min=None, bpm_max=None, preferit=None,
            log=None, nomes_beats=False):
    """Detecta BPM, beats i downbeats.

    Retorna un diccionari amb `motor`, `bpm`, `beats`, `downbeats`,
    `sensibilitat` i el paràmetre intern aplicat. Els temps són segons.
    """
    log = log or (lambda *a: None)
    motor = str(motor or "nostre")
    if motor not in MOTORS:
        raise ValueError(f"motor de beats desconegut: {motor!r}")
    sens = _limita_sensibilitat(sensibilitat)
    if motor == "qm":
        return _detecta_qm(wav, log, sens, int(bpb), bpm_hint,
                           nomes_beats=nomes_beats)
    return _detecta_nostre(wav, log, sens, int(bpb), int(den), bpm_hint,
                           bpm_min, bpm_max, preferit,
                           nomes_beats=nomes_beats)
