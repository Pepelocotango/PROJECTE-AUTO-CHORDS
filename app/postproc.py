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


def grid_de_opcions(cl, divisio=1):
    """Graella efectiva de les opcions de neteja (amb migració de `divisio`)."""
    g = (cl or {}).get("grid")
    if g in graella.DIVISIONS:
        return g
    return {1: "negra", 2: "corxera", 4: "semicorxera",
            8: "fusa"}.get(int((cl or {}).get("divisio", divisio) or 2),
                           "corxera")


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


def _snap_a_graella(items, durada, grid, bpm, bpb, offset, mapa, log,
                    inici=0.0, fi=None, capcalera=True):
    """Aplica el mateix nucli de Quantitza a una llista d'onsets d'acords.

    Per defecte treballa sobre tot el tema (`inici=0`, `fi=durada`) i, si el
    primer onset no és a zero, hi posa la capçalera «N». Per a un rang A–B es
    passa `inici`/`fi` i `capcalera=False`: així no s'hi inventa cap «N» i el
    resultat només cobreix el tram.
    """
    durada = float(durada or 0.0)
    rang_explicit = fi is not None
    if durada <= 0 and not rang_explicit:
        # Sense durada no hi ha hagut mai filtre: es conserva el comportament.
        return sorted((float(t), str(n)) for t, n in (items or ()))
    inici = max(0.0, float(inici or 0.0))
    fi = durada if fi is None else min(float(fi), durada)
    if fi <= inici:
        return []
    items = sorted((float(t), str(n)) for t, n in (items or ())
                   if inici - 1e-9 <= float(t) < fi - 1e-9)
    if not items:
        return []
    if durada <= 0:
        return items
    if capcalera and items[0][0] > inici + 1e-9:
        # Capçalera N perquè la cadena comence a l'inici; el snap no la mou.
        items.insert(0, (inici, "N"))
    clips = []
    for i, (t, nom) in enumerate(items):
        fi_i = items[i + 1][0] if i + 1 < len(items) else fi
        clips.append((max(inici, t), max(inici, fi_i), (nom,)))
    starts = [max(inici, _grid_target(t, grid, bpm, bpb, offset, mapa))
              for t, _fi, _p in clips]
    res = graella.quantitza_boundaries(
        clips, starts, set(range(len(clips))), fi, log=log)
    return [(float(ini), str(payload[0])) for ini, _fi, payload in res]


def fusiona_acords_rang(existents, nous, inici, fi, durada, log=None):
    """Substituïx els acords de `[inici, fi)` pels `nous`, sense tocar fora.

    `existents` és el model actual (clips o tuples); `nous` són inicis
    absoluts `(t, nom)` ja netejats/quantitzats. Es conserven els inicis
    anteriors a `inici` i els posteriors a `fi`; si cal, es posa l'acord que
    ja hi havia a les fronteres perquè no quede cap forat ni canvie el costat.
    """
    from app import pipeline           # import local: evita cicle d'imports
    durada = float(durada or 0.0)
    a = max(0.0, float(inici or 0.0))
    b = min(float(fi), durada)
    if durada <= 0 or b <= a:
        return list(existents or ())
    ex = [c if isinstance(c, pipeline.Clip) else
          pipeline.Clip(float(c[0]), float(c[1]), tuple(c[2]))
          for c in (existents or ())]
    ex = pipeline.normalitza_clips(
        ex, durada, pipeline.FORAT_ACORD,
        arrodoneix=True, deriva_fi=True, log=log)
    if not ex:
        return []
    tol = 1e-6

    def _actiu(t):
        triat = None
        for c in ex:
            if float(c.ini) <= t + tol:
                triat = c
            else:
                break
        return triat.payload if triat is not None else pipeline.FORAT_ACORD

    def _abans(t):
        triat = None
        for c in ex:
            if float(c.ini) < t - tol:
                triat = c
            else:
                break
        return triat.payload if triat is not None else pipeline.FORAT_ACORD

    nous = sorted((float(t), str(n)) for t, n in (nous or ())
                  if a - tol <= float(t) < b - tol)
    if not nous:
        return ex

    act_a, act_b = _actiu(a), _actiu(b)
    act_abans = _abans(a)
    starts = [(float(c.ini), c.payload) for c in ex
              if float(c.ini) < a - tol]
    primer = nous[0]
    if primer[0] > a + tol and (
            primer[1] != str(act_a[0])
            or str(act_abans[0]) != str(act_a[0])):
        # Si el primer onset cau després d'«a», la frontera ha de conservar
        # el so que hi havia a l'esquerra (encara que el nom coincidisca).
        starts.append((a, act_a))
    for t, n in nous:
        # Si el nom no canvia respecte de la frontera anterior, no cal un
        # clip nou (evita «B | B» quan el rang comença a mitjan acord).
        if starts and str(starts[-1][1][0]) == n:
            continue
        starts.append((t, (n,)))
    ultim = nous[-1]
    if b < durada - tol and ultim[1] != str(act_b[0]):
        starts.append((b, act_b))
    starts.extend((float(c.ini), c.payload) for c in ex
                  if float(c.ini) >= b - tol)

    starts.sort(key=lambda x: x[0])
    unics = []
    for t, p in starts:
        if unics and abs(t - unics[-1][0]) < tol:
            # A la mateixa frontera mana l'últim (el costat de després).
            unics[-1] = (t, p)
        else:
            unics.append((t, p))
    clips = []
    for i, (t, p) in enumerate(unics):
        fi_i = unics[i + 1][0] if i + 1 < len(unics) else durada
        if fi_i > t + tol:
            clips.append(pipeline.Clip(t, fi_i, p))
    clips = pipeline.normalitza_clips(
        clips, durada, pipeline.FORAT_ACORD,
        arrodoneix=True, deriva_fi=True, log=log)
    if log:
        log(f"  acords del rang {a:.3f}–{b:.3f}s: {len(nous)} onsets")
    return clips


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
        g = grid if grid in graella.DIVISIONS else grid_de_opcions(
            {"grid": grid, "divisio": divisio}, divisio)
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
