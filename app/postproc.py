"""Post-processat de les deteccions (opcions del diàleg d'autodetecció).

Els motors Vamp donen un resultat «cru»; aquí el netegem sense tocar el motor:

- **Acords** (`processa_acords`):
  - `treu_baix`:  elimina el baix tallat (`A/E` -> `A`, `F#dim7/E` -> `F#dim7`).
  - `redueix`:    redueix a l'acord bàsic (`Cmaj7` -> `C`, `Em6` -> `Em`,
                  `A7` -> `A`, `Edim7` -> `Edim`), conservant m/maj/dim/aug/sus.
  - `fusiona_iguals`: uneix acords consecutius iguals (després de simplificar).
  - `durada_min`: elimina els acords que duren menys d'aquest temps (soroll).
  - `snap`:       arrodoneix l'inici de cada acord a la graella (beat/compàs).

- **Estructura**: `pipeline.filtra_seccions` (durada mínima + fusionar iguals).

Tot són funcions pures (llistes -> llistes), fàcils de provar.
"""

import csv
import os
import re

_RE_BAIX = re.compile(r"/[A-G][#b]?$")
_RE_QUAL = re.compile(r"^([A-G][#b]?)(maj|min|dim|aug|sus|m)?")
_MAPA_QUAL = {"min": "m", "maj": "", "m": "m", "dim": "dim", "aug": "aug",
              "sus": "sus"}


def treu_baix(nom):
    """`A/E` -> `A`; `F#dim7/E` -> `F#dim7`."""
    return _RE_BAIX.sub("", str(nom).strip())


def redueix(nom):
    """Redueix a l'acord bàsic: `Cmaj7`->`C`, `Em6`->`Em`, `Edim7`->`Edim`."""
    n = treu_baix(nom)
    m = _RE_QUAL.match(n)
    if not m:
        return n
    arrel, qual = m.group(1), (m.group(2) or "")
    return arrel + _MAPA_QUAL.get(qual, qual)


def processa_acords(acords, durada_min=0.0, fusiona_iguals=True,
                    sense_baix=False, reduir=False):
    """Neteja una llista d'acords `(t, nom[, ...])`.

    Retorna la mateixa forma (les columnes extra es conserven).
    """
    out = []
    for it in acords:
        t, nom = float(it[0]), str(it[1]).strip()
        n = nom
        if sense_baix:
            n = treu_baix(n)
        if reduir:
            n = redueix(n)
        if fusiona_iguals and out and out[-1][1] == n:
            continue                     # C C -> un de sol
        out.append((t, n, *list(it[2:])))
    if durada_min and durada_min > 0 and len(out) > 1:
        i = 0
        while i < len(out) - 1:
            if out[i + 1][0] - out[i][0] < durada_min:
                del out[i]               # acord massa curt -> fora
            else:
                i += 1
    return out


def snap_acords(acords, bpm, bpb=4, offset=0.0, divisio=1):
    """Mou l'inici de cada acord a la subdivisió més propera de la graella.

    `divisio` = subdivisions per temps (1 = temps, 2 = corxera…).
    """
    if not bpm or bpm <= 0:
        return list(acords)
    beat = 60.0 / float(bpm) / max(1, int(divisio))
    out = []
    for it in acords:
        t = float(it[0])
        p = round((t - float(offset)) / beat)
        nou = max(0.0, float(offset) + p * beat)
        if out and abs(nou - out[-1][0]) < 1e-9:
            continue                     # dos acords al mateix punt -> un
        out.append((nou, *list(it[1:])))
    return out


def processa_acords_csv(ruta, durada_min=0.0, fusiona_iguals=True,
                        sense_baix=False, reduir=False,
                        snap=False, bpm=None, bpb=4, offset=0.0, divisio=1,
                        log=None):
    """Llegeix un CSV (temps, acord), el neteja i el reescriu al mateix lloc."""
    with open(ruta, encoding="utf-8") as f:
        items = []
        for fila in csv.reader(f):
            if not fila or fila[0].startswith("posici"):
                continue
            try:
                items.append((float(fila[0]), fila[1].strip()))
            except (ValueError, IndexError):
                continue
    n_abans = len(items)
    items = processa_acords(items, durada_min=durada_min,
                            fusiona_iguals=fusiona_iguals,
                            sense_baix=sense_baix, reduir=reduir)
    if snap and bpm:
        items = snap_acords(items, bpm, bpb, offset, divisio)
    tmp = ruta + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for it in items:
            w.writerow([f"{float(it[0]):.9f}", it[1]])
    os.replace(tmp, ruta)
    if log and len(items) != n_abans:
        log(f"  neteja d'acords: {n_abans} -> {len(items)}")
    return items
