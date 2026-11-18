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

**QM i unitat de pols**: `bpb` és el nombre de beats QM per compàs i
`inputtempo` el BPM d'eixos beats. Si el clip és `6/8` amb negra amb punt,
s'envien `bpb=2` i `inputtempo=80` per a un BPM intern de 120; el BPM que
retorna QM es torna a convertir a negres/minut. Si la unitat no cap al rang
2–16 de QM, es cau a la unitat del denominador o a `qm-tempotracker` sense
bars.
"""
from __future__ import annotations

import math
import statistics

from . import bpm_unit, limits, pipeline, tempo, tempo_map

MOTORS = ("nostre", "qm")

_QM_BEATS = "vamp:qm-vamp-plugins:qm-barbeattracker:beats"
_QM_BARS = "vamp:qm-vamp-plugins:qm-barbeattracker:bars"
# Per al mode «només beats» no demanem bars: el tempotracker no agrupa en
# compassos ni necessita bpb.
_QM_ONLY_BEATS = "vamp:qm-vamp-plugins:qm-tempotracker:beats"

# Alias estable: històricament `beats._qm_temps` era una còpia local. Ara tota
# l'extracció QM passa pel mateix helper de `pipeline_vamp`.
_qm_temps = pipeline.qm_temps


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


def _bpm_de_beats(beats):
    if len(beats) < 2:
        return None
    intervals = [b - a for a, b in zip(beats, beats[1:]) if b > a]
    if not intervals:
        return None
    # Si hi ha forats, la mediana és més robusta que la mitjana.
    bpm = 60.0 / statistics.median(intervals)
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
                        tempo_map.TempoMap(trams).compassos()]
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


def _unitat_denominador(den):
    """Unitat simple del denominador (`4/den` negres) per al fallback QM."""
    factor = 4.0 / float(den)
    for clau, (_et, f) in bpm_unit.UNITATS.items():
        if abs(float(f) - factor) <= 1e-9:
            return clau
    return bpm_unit.DEFECTE


def _qm_beats_per_bar(bpb, den, beat_unit):
    """Retorna `(bpb_qm, factor, unitat, pot_agrupar)`.

    QM treballa amb els seus propis beats: `bpb` és quants n'hi ha per compàs
    i `inputtempo` és el BPM d'eixos beats. Si la unitat percebuda no cap en el
    rang 2–16 de QM, es cau a la unitat del denominador; si tampoc, es fa
    tracking sense bars.
    """
    try:
        bpb = int(bpb)
        den = int(den)
    except (TypeError, ValueError):
        bpb, den = 4, 4
    if bpb <= 0 or den <= 0:
        bpb, den = 4, 4
    unit = bpm_unit.normalitza(beat_unit or bpm_unit.DEFECTE)
    factor = bpm_unit.factor(unit)
    bar_quarters = bpb * 4.0 / float(den)
    quin = bar_quarters / factor
    n = int(round(quin))
    if abs(quin - n) <= 1e-6 and 2 <= n <= 16:
        return n, factor, unit, True
    # Fallback: la unitat del denominador (6/8 → corxera, 4/4 → negra…).
    unit = _unitat_denominador(den)
    factor = bpm_unit.factor(unit)
    n = int(round(bar_quarters / factor))
    if 2 <= n <= 16:
        return n, factor, unit, True
    return None, factor, unit, False


def _detecta_qm(wav, log, sensibilitat, bpb, den, bpm_hint,
                nomes_beats=False, beat_unit=None):
    log(f"beats: motor QM · sensibilitat {sensibilitat:.0f}%")
    alpha = alpha_de_sensibilitat(sensibilitat)
    bpb_qm, factor, unit, pot_agrupar = _qm_beats_per_bar(
        bpb, den, beat_unit)
    bpm_qm = float(bpm_hint or 120.0) / factor
    params = {
        "alpha": f"{alpha:.3f}",
        "inputtempo": str(int(round(bpm_qm))),
        "constraintempo": "0",
    }
    if not nomes_beats and pot_agrupar:
        params["bpb"] = str(int(bpb_qm))
        beats = _qm_temps(_QM_BEATS, wav, params, log)
        bars = _qm_temps(_QM_BARS, wav, params, log)
        bpm_qm = pipeline.detecta_bpm_qm(wav, log)
        if bpm_qm is None:
            bpm_qm = _bpm_de_beats(beats)
        log(f"beats: QM bpb={bpb_qm} · inputtempo={params['inputtempo']} "
            f"({unit})")
    else:
        # qm-tempotracker: només beats, sense bars ni bpb. El tempo intern
        # del tracker només servix per seguir el pols; no s'exporta.
        beats = _qm_temps(_QM_ONLY_BEATS, wav, params, log)
        bars = []
        bpm_qm = None
        if not nomes_beats:
            log("beats: QM no pot agrupar compassos amb bpb fora de 2–16; "
                "es fan només beats.")
    bpm = None if bpm_qm is None else float(bpm_qm) * factor
    return {
        "motor": "qm",
        "bpm": bpm,
        "beats": beats,
        "downbeats": bars,
        "sensibilitat": sensibilitat,
        "parametre": {
            "alpha": alpha,
            "bpb": bpb_qm,
            "inputtempo": params["inputtempo"],
            "beat_unit": unit,
        },
    }


def detecta(wav, motor="qm", sensibilitat=50.0, bpb=4, den=4,
            bpm_hint=None, bpm_min=None, bpm_max=None, preferit=None,
            log=None, nomes_beats=False, beat_unit=None):
    """Detecta BPM, beats i downbeats.

    Retorna un diccionari amb `motor`, `bpm`, `beats`, `downbeats`,
    `sensibilitat` i el paràmetre intern aplicat. Els temps són segons.
    """
    log = log or (lambda *a: None)
    motor = str(motor or "qm")
    if motor not in MOTORS:
        raise ValueError(f"motor de beats desconegut: {motor!r}")
    sens = _limita_sensibilitat(sensibilitat)
    if motor == "qm":
        return _detecta_qm(wav, log, sens, int(bpb), int(den), bpm_hint,
                           nomes_beats=nomes_beats, beat_unit=beat_unit)
    return _detecta_nostre(wav, log, sens, int(bpb), int(den), bpm_hint,
                           bpm_min, bpm_max, preferit,
                           nomes_beats=nomes_beats)
