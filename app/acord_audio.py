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
def _freq(midi: float) -> float:
    return 440.0 * (2.0 ** ((float(midi) - 69.0) / 12.0))


def _nota(midi, dur_s, sr):
    """Una nota d'e-piano (FM estil **Rhodes**), **càlida**.

    - **Atac SUAU** (~13 ms) i un «tine» molt discret ratio 4 (el martell, sense
      estridència).
    - **Poc índex de modulació** (1,15): menys harmònics alts → timbre càlid.
    - **Chorus lleu**: dues veus desafinades ±0,2 % (el «vibrato/chorus»
      clàssic del piano elèctric).
    - **Sustain llarg** (decaïment lent) + release final → acaba a 0.
    - **Suavitzat d'aguts** (FIR curt) per treure l'aspror → so més càlid.
    """
    n = max(1, int(round(float(dur_s) * sr)))
    t = np.arange(n, dtype=np.float64) / float(sr)
    f = _freq(midi)
    # modulació discreta: cos càlid (ratio 2) + campanar molt curt (ratio 4)
    idx = 1.15 * np.exp(-t * 4.0)
    tine = 0.42 * np.exp(-t * 11.0)

    def _veu(desaf):
        fd = f * (1.0 + desaf)
        return np.sin(2.0 * np.pi * fd * t
                      + idx * np.sin(2.0 * np.pi * 2.0 * fd * t)
                      + tine * np.sin(2.0 * np.pi * 4.0 * fd * t))

    # chorus MOLT lleu i asimètric: ±0,07 % (beat lent) i pes 62/38 perquè
    # no faci cap «forat» de cancel·lació (abans ±0,2 % donava un null).
    y = 0.62 * _veu(+0.0007) + 0.38 * _veu(-0.0007)
    decau = 0.35 + (f / 220.0) * 0.20
    env = (1.0 - np.exp(-t * 200.0)) * np.exp(-t * decau)
    rel = min(n, max(1, int(0.13 * sr)))
    if rel > 1:
        env[-rel:] *= np.linspace(1.0, 0.0, rel)
    y *= 1.0 + 0.06 * np.sin(2.0 * np.pi * 4.6 * t)   # tremolo suau
    return _suavitza(y * env)


def _suavitza(x, taps=11, tallit=1.0):
    """FIR curt (sinc amb finestra de Hann) → treu aguts sobrers (més càlid)."""
    k = np.arange(taps) - (taps - 1) / 2.0
    h = np.sinc(2.0 * tallit * k / taps) * np.hanning(taps)
    s = h.sum()
    if not s:
        return x
    return np.convolve(x, h / s, mode="same")


def _mescla(notes, sr, dur_s, guany=0.85):
    """Suma les notes (acord) i normalitza pel PIC REAL (sense saturar)."""
    n = max(1, int(round(float(dur_s) * sr)))
    buf = np.zeros(n, dtype=np.float64)
    for m in notes:
        buf += _nota(m, dur_s, sr)
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


def pcm_acord(notes, sr=44100, dur_s=1.9):
    """Les notes ALHORA (bloc). Retorna bytes PCM 16 bits mono."""
    if not notes:
        return b""
    return _a_pcm(_mescla(list(notes), sr, dur_s))


def pcm_arpegi(notes, sr=44100, dur_s=1.5, pas_s=0.24):
    """Les notes PER SEPARAT (una darrere l'altra). Retorna bytes PCM mono."""
    notes = list(notes)
    if not notes:
        return b""
    total = pas_s * (len(notes) - 1) + dur_s
    n = max(1, int(round(total * sr)))
    buf = np.zeros(n, dtype=np.float64)
    for i, m in enumerate(notes):
        y = _nota(m, dur_s, sr)
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


def pcm_escolta(notes, sr=44100, pausa_s=0.18):
    """El que fa el botó ▶ Escoltar: **arpegi** (per separat) + **bloc** (alhora)."""
    notes = list(notes)
    if not notes:
        return b""
    return (pcm_arpegi(notes, sr)
            + (b"\x00\x00" * int(pausa_s * sr))
            + pcm_acord(notes, sr))
