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
import re

from . import graella

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


def _grid_target(t, grid, bpm, bpb, offset, mapa):
    """Instant de graella més pròxim; amb mapa variable, mana el mapa."""
    d = graella.DIVISIONS.get(grid)
    if d is None:
        return float(t)
    if mapa is not None:
        return float(mapa.snap(float(t), d))
    step = graella.divisio_segons(
        grid, bpm, True, bpb, 4)
    if step <= 0:
        return float(t)
    off = float(offset or 0.0)
    return max(0.0, off + round((float(t) - off) / step) * step)


def _snap_a_graella(items, durada, grid, bpm, bpb, offset, mapa, log):
    """Aplica el mateix nucli de Quantitza a una llista d'onsets d'acords."""
    items = sorted((float(t), str(n)) for t, n in (items or ()))
    if not items:
        return []
    durada = float(durada or 0.0)
    if durada <= 0:
        return items
    if items[0][0] > 1e-9:
        # Capçalera N perquè la cadena comence a 0; el snap no la mou.
        items.insert(0, (0.0, "N"))
    clips = []
    for i, (t, nom) in enumerate(items):
        fi = items[i + 1][0] if i + 1 < len(items) else durada
        clips.append((max(0.0, t), max(0.0, fi), (nom,)))
    starts = [_grid_target(t, grid, bpm, bpb, offset, mapa)
              for t, _fi, _p in clips]
    res = graella.quantitza_boundaries(
        clips, starts, set(range(len(clips))), durada, log=log)
    return [(float(ini), str(payload[0])) for ini, _fi, payload in res]


def processa_acords_csv(ruta, durada_min=0.0, fusiona_iguals=True,
                        sense_baix=False, reduir=False,
                        snap=False, bpm=None, bpb=4, offset=0.0, divisio=1,
                        grid=None, mapa=None, log=None, durada=None):
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
    if snap:
        g = grid
        if g not in graella.DIVISIONS:
            g = {1: "negra", 2: "corxera", 4: "semicorxera",
                 8: "fusa"}.get(int(divisio or 2), "corxera")
        items = _snap_a_graella(
            items, durada, g, bpm, bpb, offset, mapa, log)
    # INVARIANT de COBERTURA: els acords cobreixen tota la WAV (0 → durada).
    from app import pipeline           # import local: evita cicle d'imports
    clips = pipeline.clips_d_acords(items, durada)
    if durada:
        clips = pipeline.normalitza_clips(
            clips, durada, pipeline.FORAT_ACORD,
            arrodoneix=True, deriva_fi=True, log=log)
        items = pipeline.acords_de_clips(clips)
    # El MODEL sempre s'escriu com a clips `inici,fi,acord` (S3).
    pipeline.desa_acords_csv(ruta, clips, durada)
    if log and len(items) != n_abans:
        log(f"  neteja d'acords: {n_abans} -> {len(items)}")
    return items
