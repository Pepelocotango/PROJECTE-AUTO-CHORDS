"""Graella musical — divisions, snap i quantització (stdlib pur).

Conté:
- les divisions musicals (`DIVISIONS`): de 1/32 a 64 compassos;
- les graelles lògiques de quantització (`GRID_ACORDS`, `GRID_ESTRUCTURA`);
- el nucli de quantització (`quantitza_boundaries`), que mou només els inicis
  seleccionats i manté la cadena contigua;
- conversions de divisions a segons (`divisio_segons`).

No conté cap lògica de «mode fàcil» ni d'inferència sobre el cru de l'anàlisi.
Tot en català, només biblioteca estàndard.
"""
from __future__ import annotations

MIN_GAP_QUANTITZA = 0.001
_TOL_Q = 1e-6

# Graelles lògiques de QUANTITZACIÓ (no són les del snap visual).
#   Acords: de corxera a 1 compàs (l'harmonia no canvia a 1/32 ni a 64 compassos).
#   Estructura: de 1 a 64 compassos (frases i blocs).
GRID_ACORDS = (
    ("Corxera (1/8)", "corxera"),
    ("Treset de corxera (1/3)", "treset_corxera"),
    ("Negra (1/4)", "negra"),
    ("Treset de negra (2/3)", "treset_negra"),
    ("Blanca (1/2)", "blanca"),
    ("1 compàs", "compas1"),
)
GRID_ESTRUCTURA = tuple(
    (f"{n} compàs" if n == 1 else f"{n} compassos", f"compas{n}")
    for n in (1, 2, 4, 6, 8, 12, 16, 24, 32, 48, 64)
)


def quantitza_boundaries(clips, starts, selected, durada, log=None):
    """Nucli de QUANTITZACIÓ sobre clips contigus.

    `clips` = `[(ini, fi, payload), …]`; `starts` = inici proposat per a cada
    clip (ja quantitzat a la graella pel cridador); `selected` = índexs que es
    poden moure (`None` = tots). Els clips NO seleccionats queden clavats.

    Els inicis seleccionats es limiten entre els veïns NO seleccionats (per no
    invertir l'ordre) i, si dos inicis cauen al mateix punt, sobreviu el primer
    (el clip posterior s'absorbix i el seu temps passa al clip anterior). Així
    el model continua sent una cadena contigua i vàlida.
    """
    clips = [(float(c[0]), float(c[1]), tuple(c[2])) for c in (clips or ())]
    n = len(clips)
    if n == 0:
        return []
    durada = float(durada or 0.0)
    selected = set(range(n)) if selected is None else set(selected)
    props = [float(x) for x in starts]
    # Els no seleccionats no es mouen: tanquen l'interval dels seleccionats.
    fixos = [i for i in range(n) if i not in selected]
    for i in selected:
        previ = max((j for j in fixos if j < i), default=None)
        seguent = min((j for j in fixos if j > i), default=None)
        lo = (clips[previ][0] + MIN_GAP_QUANTITZA) if previ is not None else 0.0
        hi = ((clips[seguent][0] - MIN_GAP_QUANTITZA) if seguent is not None
              else max(0.0, durada - MIN_GAP_QUANTITZA))
        if hi < lo:
            hi = lo
        props[i] = max(lo, min(hi, props[i]))
    # Ordre per inici proposat (i índex original com a desempat).
    def _forat(payload):
        return str(payload[0]).strip() in ("N", "-", "")

    def _durada(i):
        return max(0.0, clips[i][1] - clips[i][0])

    ordre = sorted(range(n), key=lambda i: (props[i], i))
    talls = []      # (temps, payload, índex original, seleccionat)
    for i in ordre:
        t = props[i]
        if t < 0:
            t = 0.0
        if durada > 0 and t >= durada - _TOL_Q:
            continue
        if talls and t < talls[-1][0] + MIN_GAP_QUANTITZA - _TOL_Q:
            # Col·lisió: si els dos són seleccionables, mana el contingut real
            # (no la capçalera N) i, si cal, el clip que durava més.
            j = talls[-1]
            actual_sel = i in selected
            if actual_sel and j[3]:
                actual_forat = _forat(clips[i][2])
                antic_forat = _forat(j[1])
                if ((antic_forat and not actual_forat) or
                        (actual_forat == antic_forat and
                         _durada(i) > _durada(j[2]) + _TOL_Q)):
                    talls[-1] = (j[0], clips[i][2], i, True)
            if log:
                log(f"quantitza: inici {t:.6f} s absorbit per "
                    f"{talls[-1][0]:.6f} s")
            continue
        talls.append((t, clips[i][2], i, i in selected))
    out = []
    for j, (t, payload, _i, _sel) in enumerate(talls):
        fi = talls[j + 1][0] if j + 1 < len(talls) else durada
        if fi > t + _TOL_Q:
            out.append((t, fi, payload))
    return out


def beat_segons(bpm):
    """Durada d'un temps (beat) en segons."""
    bpm = float(bpm or 0.0)
    return 60.0 / bpm if bpm > 0 else 0.0


# Divisions de la graella: nom → (mena, valor).
#   ("beat", frac) = fracció d'un temps  ·  ("bars", n) = n compassos
DIVISIONS = {
    "negra": ("beat", 1.0),          # 1/4
    "corxera": ("beat", 0.5),        # 1/8
    "semicorxera": ("beat", 0.25),   # 1/16
    "fusa": ("beat", 0.125),         # 1/32
    "blanca": ("beat", 2.0),         # 1/2 (2 temps)
    # Treset: 3 notes en el lloc de 2.
    "treset_negra": ("beat", 2.0 / 3.0),        # 3 negres en 2 temps
    "treset_corxera": ("beat", 1.0 / 3.0),      # 3 corxeres en 1 temps
    "treset_semicorxera": ("beat", 1.0 / 6.0),  # 3 semicorxeres en 1/2 temps
    "treset": ("beat", 1.0 / 3.0),   # àlies històric = treset de corxera
    # Blocs de compàs (estructura pop, blues i partits).
    "compas1": ("bars", 1),
    "compas2": ("bars", 2),
    "compas4": ("bars", 4),
    "compas6": ("bars", 6),
    "compas8": ("bars", 8),
    "compas12": ("bars", 12),
    "compas16": ("bars", 16),
    "compas24": ("bars", 24),
    "compas32": ("bars", 32),
    "compas48": ("bars", 48),
    "compas64": ("bars", 64),
}


def divisio_segons(nom, bpm, tempo_fix, bpb=4, beat_type=4):
    """Segons per cel·la de la divisió triada (0 = automàtic/zoom).

    Les divisions en **compassos** depenen del compàs (`bpb`). Només en mode
    BPM·compàs (en Lliure es retorna 0 → mana el snap lligat al zoom).
    """
    if not tempo_fix:
        return 0.0
    d = DIVISIONS.get(nom)
    if not d:
        return 0.0
    beat = beat_segons(bpm)
    if beat <= 0:
        return 0.0
    mena, val = d
    if mena == "bars":
        den = max(1, int(beat_type or 4))
        return beat * max(1, int(bpb or 4)) * (4.0 / den) * int(val)
    return beat * float(val)
