#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Àudio per ESCOLTAR un tipus d'acord — piano elèctric sintetitzat (numpy pur).

Per al botó **▶ Escoltar** del panell «Tipus d'acord»: agafa les notes del
xifrat (arrel + graus) i en genera l'àudio amb un **e-piano FM** (estil Rhodes:
atac de «tine» que cau de pressa + cos càlid; vegeu `_nota`).

- **Sense dependències noves**: `numpy` (que l'app ja fa servir) i prou. La
  reproducció la fa el MATEIX motor d'àudio de sempre (`app/audio_out.py`:
  `paplay`/`aplay` a Linux · `sounddevice`/PortAudio a macOS/Windows).
- **Sense clics**: l'envolupant comença a 0 i acaba pràcticament a 0.
- Els GRAUS surten de `xifrat.TAULA_TIPUS` («1,3,5,7», «1,b3,5,b7»…): d'aquí
  es deriven els intervals en semitons — mateixa font de veritat que la resta.

Funcions públiques: `notes_del_tipus()`, `notes_amb_baix()`, `pcm_acord()`,
`pcm_arpegi()`, `pcm_escolta()` (arpegi + bloc, el que fa el botó).
"""
from __future__ import annotations

import numpy as np

# --- notes -----------------------------------------------------------------
_LLETRES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_ALT = {"": 0, "#": 1, "b": -1, "##": 2, "bb": -2}

# Grau (el text de `xifrat.TAULA_TIPUS`) -> semitons des de l'arrel.
_INTERVALS = {
    "1": 0, "b2": 1, "2": 2, "#2": 3, "b3": 3, "3": 4, "b4": 4,
    "4": 5, "#4": 6, "b5": 6, "5": 7, "#5": 8, "b6": 8, "6": 9,
    "b7": 10, "7": 11, "b9": 13, "9": 14, "#9": 15, "11": 17,
    "#11": 18, "b13": 20, "13": 21,
}

# Rang còmode de l'e-piano (C3) i límit per no apilar octaves boges.
OCTAVA_BASE = 3
MIDI_MIN, MIDI_MAX = 24, 96


def nota_a_midi(nom: str, octava: int = OCTAVA_BASE):
    """`'C'`, `'F#'`, `'Bb'`… + octava -> número MIDI (o `None` si no és nota)."""
    nom = str(nom or "").strip()
    if not nom or nom[0].upper() not in _LLETRES:
        return None
    lletra = nom[0].upper()
    alt = nom[1:]
    if alt not in _ALT:
        return None
    midi = 12 * (int(octava) + 1) + _LLETRES[lletra] + _ALT[alt]
    return max(MIDI_MIN, min(MIDI_MAX, midi))


def notes_del_tipus(arrel: str, graus: str, octava: int = OCTAVA_BASE):
    """Notes MIDI del xifrat: l'arrel + els intervals dels GRAUS.

    `graus` és el text de la taula (`'1,3,5,7'`); els trossos no numèrics
    (p. ex. `'+alt'`) s'ignoren. Sense arrel vàlida, retorna `[]`.
    """
    base = nota_a_midi(arrel, octava)
    if base is None:
        return []
    notes = set()
    for tros in str(graus or "").replace(" ", "").split(","):
        if not tros:
            continue
        semis = _INTERVALS.get(tros)
        if semis is None:                 # `+alt`, coses rares: fora
            continue
        m = base + semis
        if MIDI_MIN <= m <= MIDI_MAX:
            notes.add(m)
    if not notes:
        notes.add(base)
    return sorted(notes)


# --- síntesi: piano elèctric (FM) ------------------------------------------
# --- síntesi: família PIANO (8 presets) ------------------------------------
# Referència (General MIDI, programes 1-8 de piano): Acoustic Grand · Bright ·
# Electric Grand · Honky-tonk · Electric Piano 1 (Rhodes) · Electric Piano 2
# (FM/DX7) · i, per arrodonir la família, Wurlitzer i piano de joguina.
# Els paràmetres FM segueixen les regles clàssiques: índex 1-2 = càlid ·
# 3-5 = «electric piano»; ratios 1:1 = cos, 1:11 = campanar, inarmònic = metall.
PRESETS = (
    ("piano", "Piano de cua"),
    ("brillant", "Piano brillant"),
    ("electric", "Piano elèctric de cua"),
    ("honky", "Honky-tonk"),
    ("rhodes", "E-piano Rhodes"),
    ("ep_fm", "E-piano FM (DX7)"),
    ("wurli", "Wurlitzer"),
    ("joguina", "Piano de joguina"),
)
PRESET_DEFECTE = "rhodes"


def _base(**kw):
    """Paràmetres d'una veu de piano + els canvis de cada preset."""
    p = dict(
        parcials=((1, 1.00, 1.0), (2, 0.48, 1.4), (3, 0.26, 1.9),
                  (4, 0.15, 2.5), (5, 0.085, 3.2), (6, 0.05, 4.2),
                  (8, 0.03, 5.6), (10, 0.02, 7.2)),
        inarm=0.00035,          # inharmonicitat (cordes de piano)
        veus=3, detune=0.0006,  # cordes lleugerament desafinades
        fm=(),                  # moduladors FM: (ratio, índex, decaïment)
        atac_ms=5.0, decau=0.30, decau_pitch=0.28,
        filtre=1.0,             # suavitzat d'aguts (més alt = més brillant)
        over=0.0, trem=0.0, trem_hz=4.6, amp=1.0,
    )
    p.update(kw)
    return p


_PARAMS = {
    "piano": _base(),
    "brillant": _base(
        parcials=((1, 1.00, 0.95), (2, 0.58, 1.15), (3, 0.36, 1.5),
                  (4, 0.24, 1.9), (5, 0.15, 2.4), (6, 0.10, 3.0),
                  (8, 0.06, 4.2), (10, 0.04, 5.5), (12, 0.025, 7.0)),
        atac_ms=3.5, filtre=1.9),
    "electric": _base(fm=((2.0, 0.55, 5.0),), atac_ms=5.0, filtre=1.4),
    "honky": _base(veus=3, detune=0.0032, atac_ms=4.0),
    "rhodes": _base(
        parcials=(), fm=((2.0, 1.15, 4.0), (4.0, 0.42, 11.0)),
        atac_ms=16.0, decau=0.35, decau_pitch=0.20, veus=2, detune=0.0007,
        trem=0.06),
    "ep_fm": _base(
        parcials=(), fm=((1.0, 1.00, 3.5), (11.0, 0.55, 26.0)),
        atac_ms=4.0, decau=0.55, decau_pitch=0.30, veus=2, detune=0.0011,
        filtre=1.6),
    "wurli": _base(
        parcials=((1, 0.90, 1.0), (3, 0.35, 2.2), (5, 0.18, 3.4),
                  (7, 0.08, 5.0)),
        fm=((1.0, 0.90, 6.0),), atac_ms=9.0, decau=0.60, decau_pitch=0.35,
        veus=1, over=0.35, filtre=0.9),
    "joguina": _base(
        parcials=((1, 1.00, 1.6), (2, 0.50, 2.6), (3, 0.20, 4.0),
                  (5, 0.12, 6.0), (7, 0.06, 8.0)),
        fm=((3.0, 0.70, 9.0),), atac_ms=3.0, decau=1.10, decau_pitch=0.60,
        veus=2, detune=0.0016, filtre=2.2),
}


def _freq(midi: float) -> float:
    return 440.0 * (2.0 ** ((float(midi) - 69.0) / 12.0))


def _nota(midi, dur_s, sr, preset=None):
    """Una nota amb el preset triat (vegeu `PRESETS`).

    El motor és el mateix per a tots: **parcials additius** amb **inharmonicitat**
    i diversa caiguda (piano) i/o **FM** amb l'índex que decau (e-pianos), amb
    cordes lleugerament desafinades, envolupant d'atac/decaïment, release final,
    tremolo opcional i un suavitzat d'aguts.
    """
    p = _PARAMS.get(preset) or _PARAMS[PRESET_DEFECTE]
    n = max(1, int(round(float(dur_s) * sr)))
    t = (np.arange(n, dtype=np.float32) / np.float32(sr))
    f = _freq(midi)
    dec = p["decau"] + (f / 220.0) * p["decau_pitch"]

    def _cordes(fd):
        """Parcials additius (inharmònics) amb la seva pròpia caiguda.

        Vectoritzat (una sola `sin`/`exp` per a tots els parcials): és el camí
        calent de la síntesi i així no es nota en clicar.
        """
        if not p["parcials"]:
            return np.zeros(n, dtype=np.float32)
        ks = np.array([k for (k, _a, _d) in p["parcials"]], dtype=np.float32)
        am = np.array([a for (_k, a, _d) in p["parcials"]], dtype=np.float32)
        dk = np.array([d for (_k, _a, d) in p["parcials"]], dtype=np.float32)
        fr = ks * fd * (1.0 + p["inarm"] * ks * ks)
        ok = fr < sr * 0.45               # per sobre de Nyquist: fora
        if not ok.any():
            return np.zeros(n, dtype=np.float32)
        fr, am, dk = fr[ok].astype(np.float32), am[ok], dk[ok].astype(np.float32)
        decaig = np.exp(-np.outer(dk * dec, t))
        return (np.sin(2.0 * np.pi * np.outer(fr, t)) * decaig
                * am[:, None]).sum(axis=0)

    veus = max(1, int(p["veus"]))
    y = np.zeros(n, dtype=np.float32)
    for i in range(veus):
        d = (i - (veus - 1) / 2.0) * p["detune"]
        y += _cordes(f * (1.0 + d))
    y /= veus

    if p["fm"]:                            # moduladors (e-pianos)
        mod = np.zeros(n, dtype=np.float32)
        for (r, idx, idc) in p["fm"]:
            mod += idx * np.exp(-t * idc) * np.sin(2.0 * np.pi * r * f * t)
        yf = np.sin(2.0 * np.pi * f * t + mod)
        y = (0.30 * y + yf) if p["parcials"] else yf

    env = (1.0 - np.exp(-t * (3000.0 / max(0.5, p["atac_ms"])))) * np.exp(-t * dec)
    rel = min(n, max(1, int(0.13 * sr)))
    if rel > 1:
        env[-rel:] *= np.linspace(1.0, 0.0, rel)
    y *= env
    if p["trem"]:
        y *= 1.0 + p["trem"] * np.sin(2.0 * np.pi * p["trem_hz"] * t)
    if p["over"]:
        y = np.tanh(y * (1.0 + 3.0 * p["over"])) / np.tanh(1.0 + 3.0 * p["over"])
    return _suavitza(y * p["amp"], tallit=p["filtre"])


def _suavitza(x, taps=11, tallit=1.0):
    """FIR curt (sinc amb finestra de Hann) → treu aguts sobrers (més càlid)."""
    k = np.arange(taps) - (taps - 1) / 2.0
    h = np.sinc(2.0 * tallit * k / taps) * np.hanning(taps)
    s = h.sum()
    if not s:
        return x
    return np.convolve(x, h / s, mode="same")


def _mescla(notes, sr, dur_s, guany=0.85, preset=None):
    """Suma les notes (acord) i normalitza pel PIC REAL (sense saturar)."""
    n = max(1, int(round(float(dur_s) * sr)))
    buf = np.zeros(n, dtype=np.float64)
    for m in notes:
        buf += _nota(m, dur_s, sr, preset)
    # Normalitzem pel pic real: els atacs de les notes coincideixen i sumar-los
    # amb un factor heurístic saturava (pic a fons d'escala → distorsió).
    pic = float(np.max(np.abs(buf))) or 1.0
    if pic > guany:
        buf *= guany / pic
    return buf


def _a_pcm(buf):
    """float (-1..1) -> bytes PCM 16 bits little-endian (sense clics)."""
    x = np.clip(np.nan_to_num(buf), -1.0, 1.0)
    return (x * 32767.0).astype("<i2").tobytes()


def pcm_acord(notes, sr=44100, dur_s=1.9, preset=None):
    """Les notes ALHORA (bloc), amb el preset triat. Bytes PCM 16 bits mono."""
    if not notes:
        return b""
    return _a_pcm(_mescla(list(notes), sr, dur_s, preset=preset))


def pcm_arpegi(notes, sr=44100, dur_s=1.5, pas_s=0.24, preset=None):
    """Les notes PER SEPARAT (una darrere l'altra). Retorna bytes PCM mono."""
    notes = list(notes)
    if not notes:
        return b""
    total = pas_s * (len(notes) - 1) + dur_s
    n = max(1, int(round(total * sr)))
    buf = np.zeros(n, dtype=np.float64)
    for i, m in enumerate(notes):
        y = _nota(m, dur_s, sr, preset)
        i0 = int(round(i * pas_s * sr))
        i1 = min(n, i0 + len(y))
        buf[i0:i1] += y[:i1 - i0]
    # normalitza pel pic real (l'arpegi no apila tantes notes)
    pic = float(np.max(np.abs(buf))) or 1.0
    if pic > 0.85:
        buf *= 0.85 / pic
    return _a_pcm(buf)


def notes_amb_baix(arrel: str, graus: str, baix: str = "",
                   octava: int = OCTAVA_BASE):
    """Notes de l'acord **+ el baix** (una octava sota l'arrel) si n'hi ha.

    Per als acords amb `/` (p. ex. `A7/G`): el baix sona a sota de l'acord, com
    a la guitarra/piano.
    """
    notes = notes_del_tipus(arrel, graus, octava)
    if not notes or not str(baix or "").strip():
        return notes
    b = nota_a_midi(baix, octava - 1)
    if b is None or b in notes:
        return notes
    return sorted([b, *notes])


def pcm_escolta(notes, sr=44100, pausa_s=0.18, preset=None):
    """El que fa el botó ▶ Escoltar: **arpegi** (per separat) + **bloc** (alhora)."""
    notes = list(notes)
    if not notes:
        return b""
    return (pcm_arpegi(notes, sr, preset=preset)
            + (b"\x00\x00" * int(pausa_s * sr))
            + pcm_acord(notes, sr, preset=preset))
