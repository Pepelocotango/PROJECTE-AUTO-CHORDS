"""Lectura de WAV i CSV del visor (F4).

Extret de `app/visor.py`: càrrega del PCM, clips d'acords i estructura ABC.
"""
import csv
import logging
import wave

import numpy as np

from . import pipeline

N_BUCKETS = 2000  # pics precalculats: obrir 250 s és instantani

def llegeix_wav(ruta):
    with wave.open(ruta, "rb") as w:
        n, ch, sr, nframes = (w.getsampwidth(), w.getnchannels(),
                              w.getframerate(), w.getnframes())
        if n != 2:
            raise ValueError("només wav PCM 16 bits")
        raw = w.readframes(nframes)
    mono = np.frombuffer(raw, dtype=np.int16)
    if ch > 1:
        mono = mono.reshape(-1, ch).mean(axis=1).astype(np.int16)
    durada = len(mono) / sr
    # pics per bucket (ràpid amb numpy 1.26, sense AVX)
    idx = np.linspace(0, len(mono), N_BUCKETS + 1).astype(int)
    pics = np.empty(N_BUCKETS, dtype=np.float32)
    for i in range(N_BUCKETS):
        tram = mono[idx[i]:idx[i + 1]]
        pics[i] = np.abs(tram).max() / 32768.0 if len(tram) else 0.0
    temps = np.linspace(0, durada, N_BUCKETS)
    return {"sr": sr, "canals": ch, "durada": durada, "raw": raw,
            "mono": mono, "temps": temps, "pics": pics}


def nom_acord(it):
    """Nom d'un clip d'acord (`Clip(ini, fi, payload)`)."""
    if isinstance(it, pipeline.Clip):
        return it.nom
    if len(it) >= 3 and isinstance(it[1], (int, float)):
        p = it[2]
        return p[0] if isinstance(p, tuple) else p
    return it[1]


def llegeix_acords(ruta):
    # Model d'acords com a CLIPS `inici,fi,acord` (S3+S4). El `fi` de la columna
    # 2 és el de la cadena de fronteres (es re-deriva a la normalització); el
    # `payload` duu (nom, tsrc).
    items = []
    with open(ruta, encoding="utf-8") as f:
        for fila in csv.reader(f):
            if len(fila) < 3 or fila[0].startswith("posici") \
                    or fila[0].startswith("inici"):
                continue
            try:
                items.append(pipeline.Clip(
                    float(fila[0]), float(fila[1]),
                    (fila[2].strip(), fila[0])))
            except ValueError:
                # linia malmesa al CSV: no la podem parsejar. Abans
                # s'ignorava en silenci (perdua de dades invisible).
                logging.getLogger("auto_chords").warning(
                    "acords: linia ignorada (no numerica): %r", fila)
                continue
    return items


def llegeix_abc(ruta):
    """Llig `estructura_ABC.csv` com a tuples `(ini, fi, lletra, família)`.

    Mateix tracte que `llegeix_acords` (paritat #11): una línia **malmesa**
    (columna que falta o valor no numèric) es **descarta amb avís**, no fa
    petar l'obertura del tema. I una lletra o família buida cau al valor per
    defecte del model («-» i, la família, la lletra) en comptes de quedar
    `None` — que després s'hauria escrit al CSV com «None».
    """
    items = []
    with open(ruta, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                ini = float(r["inici_s"])
                fi = float(r["fi_s"])
            except (TypeError, ValueError, KeyError):
                logging.getLogger("auto_chords").warning(
                    "estructura: linia ignorada (no vàlida): %r", r)
                continue
            lletra = str(r.get("lletra") or "").strip() or pipeline.SENSE_SECCIO
            fam = str(r.get("família") or "").strip() or lletra
            items.append((ini, fi, lletra, fam))
    return items
