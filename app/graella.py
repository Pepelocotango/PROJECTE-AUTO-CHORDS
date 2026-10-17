#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Graella musical — la «matemàtica» de compàs·temps.

Amb un BPM constant, qualsevol instant es pot expressar en graella
(`compàs.temps.subdivisió`) i, a l'inrevés, qualsevol decisió musical es pot
prendre **en unitats musicals** i convertir-la a segons amb el BPM. Això és el
que permet que una opció com «canvia d'acord cada compàs» siga correcta a
qualsevol tempo (a 120 BPM un compàs són 2,00 s; a 90 BPM, 2,67 s).

Aquí hi ha:
- conversions (`nivell_segons`, `snap_a_nivell`),
- el **nucli únic de regularització** (`regularitza_clips`): encaixa els clips
  a la graella i en deixa el dominant per tram — el fan servir tant els acords
  (`regularitza_acords`) com l'estructura (`regularitza_seccions`),
- la **inferència automàtica** del ritme harmònic (`infereix_nivell`): el mode
  fàcil.

Tot en català, només biblioteca estàndard.
"""
from __future__ import annotations

# Nivells de ritme harmònic suportats (de més gruixut a més fi).
NIVELLS = ("compas", "mig", "temps")

# Etiquetes per a la UI (ordre de presentació, amb «auto» al davant).
ETIQUETES = {
    "auto": "Auto (dedueix-ho)",
    "compas": "Cada compàs",
    "mig": "Cada mig compàs",
    "temps": "Cada temps",
}

# PRESETS D'ESTIL: només són VALORS INICIALS de la graella (metre + ritme harmònic
# + mòdul d'estructura en compassos). El motor fa la resta; tot és editable.
#   bpb/den  = compàs (ex. 4/4, 12/8)   ·  ritme = nivell del canvi d'acord
#   modul    = mida del bloc d'estructura (0 = no tocar-ne els talls)
PRESETS = {
    "auto":       {"etiqueta": "Auto (dedueix-ho)",         "bpb": 4, "den": 4,
                   "ritme": "auto",  "modul": 4},
    "pop":        {"etiqueta": "Pop / Rock 4/4",            "bpb": 4, "den": 4,
                   "ritme": "mig",   "modul": 4},
    "balada":     {"etiqueta": "Balada 4/4",                "bpb": 4, "den": 4,
                   "ritme": "compas", "modul": 8},
    "blues":      {"etiqueta": "Blues de 12",               "bpb": 4, "den": 4,
                   "ritme": "compas", "modul": 12},
    "swing":      {"etiqueta": "Swing / Jazz (ternari)",    "bpb": 4, "den": 4,
                   "ritme": "temps", "modul": 8},
    "bossa":      {"etiqueta": "Bossa / Latin 4/4",         "bpb": 4, "den": 4,
                   "ritme": "mig",   "modul": 8},
    "funk":       {"etiqueta": "Funk / Soul 4/4",           "bpb": 4, "den": 4,
                   "ritme": "compas", "modul": 4},
    "reggae":     {"etiqueta": "Reggae / Ska 4/4",          "bpb": 4, "den": 4,
                   "ritme": "compas", "modul": 4},
    "vals":       {"etiqueta": "Vals 3/4",                  "bpb": 3, "den": 4,
                   "ritme": "compas", "modul": 8},
    "bolero":     {"etiqueta": "Bolero 4/4",                "bpb": 4, "den": 4,
                   "ritme": "compas", "modul": 8},
    "sevillanes": {"etiqueta": "Sevillanes 3/4",            "bpb": 3, "den": 4,
                   "ritme": "compas", "modul": 4},
    "rumba":      {"etiqueta": "Rumba flamenca 4/4",        "bpb": 4, "den": 4,
                   "ritme": "mig",   "modul": 4},
    "tangos":     {"etiqueta": "Tangos / Tientos 4/4",      "bpb": 4, "den": 4,
                   "ritme": "mig",   "modul": 4},
    "buleria":    {"etiqueta": "Bulería 12/8",              "bpb": 12, "den": 8,
                   "ritme": "temps", "modul": 1},
}


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
    "treset": ("beat", 1.0 / 3.0),   # treset de negra
    "compas1": ("bars", 1),
    "compas4": ("bars", 4),
    "compas8": ("bars", 8),
    "compas16": ("bars", 16),
}


def divisio_segons(nom, bpm, tempo_fix, bpb=4):
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
        return beat * max(1, int(bpb or 4)) * int(val)
    return beat * float(val)


def nivell_segons(nivell, bpm, bpb):
    """Segons per «cel·la» del nivell donat (`compas` / `mig` / `temps`)."""
    beat = beat_segons(bpm)
    if beat <= 0:
        return 0.0
    compass = beat * max(1, int(bpb or 4))
    if nivell == "compas":
        return compass
    if nivell == "mig":
        return compass / 2.0
    if nivell == "temps":
        return beat
    raise ValueError(f"nivell desconegut: {nivell!r}")


def snap_a_nivell(t, nivell, bpm, bpb, offset=0.0):
    """Temps `t` encaixat a la frontera MÉS PROPERA del nivell."""
    pas = nivell_segons(nivell, bpm, bpb)
    if pas <= 0:
        return float(t)
    k = round((float(t) - float(offset)) / pas)
    return max(0.0, float(offset) + k * pas)


# Tolerància temporal pròpia de la graella (evita falsos positius de coma flotant).
_TOL = 1e-6


def regularitza_clips(clips, pas, offset, durada, log=None):
    """NUCLI ÚNIC de la regularització del mode fàcil, sobre clips `ini`+`fi`.

    Un «clip» aquí és `(ini, fi, payload)` — el mateix model que el `Clip` del
    pipeline (`ini`, `fi`, `payload`). L'operació encaixa l'**inici** de cada
    clip a la frontera MÉS PROPERA de la graella (`offset + k·pas`) i
    reconstrueix la cadena: cada tram resolt pren el payload del clip que **més
    temps hi ocupa** (el **dominant**; davant d'empat, el primer, que és el més
    antic). Els clips que hi queden dins queden **absorbits** i els laterals
    **tallats** per la frontera nova → la contigüitat (#2) es manté.

    És el mateix nucli per als **acords** i per a l'**estructura** (#11): el que
    canvia, a cada wrapper, és com es construeixen els clips d'entrada i el
    `payload`. No muta l'entrada; retorna una llista NOVA de tuples.
    """
    clips = sorted(((float(c[0]), float(c[1]), tuple(c[2]))
                    for c in (clips or ())), key=lambda c: c[0])
    if not clips or not pas or pas <= 0:
        return clips
    durada = float(durada or 0.0)
    off = float(offset or 0.0)
    talls = []
    for c in clips:
        s = max(0.0, off + round((c[0] - off) / pas) * pas)
        if durada > 0 and s >= durada - _TOL:
            continue
        if not talls or s > talls[-1] + _TOL:
            talls.append(s)
    if not talls:
        return []
    if durada > 0:
        talls.append(durada)
    else:
        talls.append(talls[-1] + pas)      # sense durada: tanca el darrer tram
    out = []
    for j in range(len(talls) - 1):
        p, q = talls[j], talls[j + 1]
        if q - p <= _TOL:
            continue
        millor, cobertura = None, 0.0
        for c in clips:
            ov = min(q, c[1]) - max(p, c[0])
            if ov > cobertura + _TOL:
                millor, cobertura = c, ov
        if millor is not None:
            out.append((p, q, millor[2]))
    if log:
        log(f"graella: {len(clips)} clips → {len(out)} trams")
    return out


def regularitza_acords(items, bpm, bpb, offset, nivell, durada, log=None):
    """Un acord per cel·la de la graella (ritme harmònic), a partir dels canvis crus.

    Wrapper del nucli únic `regularitza_clips` (#11): cada canvi cru és l'inici
    d'un clip (el `fi`, la marca següent o la durada) i el nucli en deixa el
    **dominant** per cel·la. Les cel·les sense canvi queden cobertes pel clip
    que hi arriba en aplicar-hi la cobertura total (#4) a fora.
    Retorna `[(t_cel·la, nom), …]` ordenat. No muta l'entrada.
    """
    items = [(float(t), str(n)) for (t, n) in items]
    if not items:
        return []
    pas = nivell_segons(nivell, bpm, bpb)
    if pas <= 0:
        return sorted(items, key=lambda x: x[0])
    durada = float(durada or 0.0)
    if durada <= 0:                       # sense WAV no hi ha graella on encaixar
        return sorted(items, key=lambda x: x[0])
    n = len(items)
    clips = [(t, (items[i + 1][0] if i + 1 < n else durada), (nom,))
             for i, (t, nom) in enumerate(items)]
    out = regularitza_clips(clips, pas, offset, durada)
    if log:
        log(f"ritme harmònic ({nivell}): {n} canvis → {len(out)} acords")
    return [(c[0], c[2][0]) for c in out]


def infereix_nivell(items, bpm, bpb, offset, durada, log=None):
    """Dedueix el ritme harmònic: el nivell MÉS GRUIXUT que explica els canvis.

    Si ≥85% dels canvis crus cauen sobre les fronteres d'un nivell, aquell nivell
    els explica; es tria el més gruixut que hi encaixa (Occam). Si cap hi encaixa
    bé, es cau a `temps` (el més fi).
    """
    ts = [float(t) for (t, *_r) in items]
    if len(ts) < 2:
        return "compas"
    off = float(offset or 0.0)
    for nivell in NIVELLS:
        pas = nivell_segons(nivell, bpm, bpb)
        if pas <= 0:
            continue
        tol = max(0.03, 0.15 * pas)
        bons = 0
        for t in ts:
            k = round((t - off) / pas)
            if abs((t - off) - k * pas) <= tol:
                bons += 1
        if bons >= 0.85 * len(ts):
            if log:
                log(f"ritme harmònic auto → «{nivell}» "
                    f"({bons}/{len(ts)} canvis encaixen)")
            return nivell
    if log:
        log("ritme harmònic auto → «temps» (cap nivell encaixa gairebé tot)")
    return "temps"


def regularitza_seccions(seccions, bpm, bpb, offset, durada,
                         modul_compassos=4, log=None):
    """Encaixa els talls de secció a MÚLTIPLES de `modul_compassos` compassos.

    Wrapper del nucli únic `regularitza_clips` (#11): cada secció és un clip
    `(ini, fi, (lletra, família))` i el `pas` de la graella és el bloc de
    `modul_compassos` compassos. El nucli encaixa els talls interiors i deixa,
    per tram, la secció **dominant**; preserva la cobertura [0, durada] i no
    muta l'entrada.
    """
    seccions = [(float(i), float(f), str(l), str(fa)) for (i, f, l, fa) in seccions]
    if len(seccions) < 2 or not modul_compassos or modul_compassos <= 0:
        return seccions
    pas = nivell_segons("compas", bpm, bpb) * int(modul_compassos)
    if pas <= 0:
        return seccions
    durada = float(durada or seccions[-1][1])
    clips = [(i, f, (l, fa)) for (i, f, l, fa) in seccions]
    out = regularitza_clips(clips, pas, offset, durada, log=log)
    if log:
        log(f"estructura: {len(seccions)} → {len(out)} seccions "
            f"(blocs de {int(modul_compassos)} compassos)")
    return [(c[0], c[1], c[2][0], c[2][1]) for c in out]


def _seq_per_compas(items, bpm, bpb, offset, durada):
    """Seqüència d'acords per compàs (una entrada per compàs), o `[]`."""
    pas = nivell_segons("compas", bpm, bpb)
    if pas <= 0 or not items:
        return []
    off = float(offset or 0.0)
    durada = float(durada or 0.0)
    ordenats = sorted((float(t), str(n)) for (t, n) in items)
    if durada <= 0:
        durada = ordenats[-1][0] + pas
    nbars = int(round((durada - off) / pas))
    if nbars < 1:
        return []
    seq = [None] * nbars
    n = len(ordenats)
    for i, (t, nom) in enumerate(ordenats):
        fi = ordenats[i + 1][0] if i + 1 < n else durada
        k0 = int(round((t - off) / pas))
        k1 = int(round((fi - off) / pas))
        for k in range(max(0, k0), min(nbars, k1 if k1 > k0 else k0 + 1)):
            seq[k] = nom
    return seq


def infereix_cicle_compassos(items, bpm, bpb, offset, durada, log=None):
    """Període (compassos) més probable del patró d'acords, o `None`.

    Busca el bloc més petit (2,3,4,6,8,12,16,24,32) tal que la seqüència per
    compàs es repeteixi prou bé (≥75% de coincidències). Dóna la pista per al
    mòdul d'estructura (blues→12, pop→4/8…) i per als presets d'estil.
    """
    seq = _seq_per_compas(items, bpm, bpb, offset, durada)
    nbars = len(seq)
    if nbars < 4:
        return None
    for p in (2, 3, 4, 6, 8, 12, 16, 24, 32):
        if 2 * p > nbars:
            continue
        iguals = total = 0
        for i in range(p, nbars):
            if seq[i] is not None and seq[i - p] is not None:
                total += 1
                if seq[i] == seq[i - p]:
                    iguals += 1
        if total and iguals / total >= 0.75:
            if log:
                log(f"cicle inferit: {p} compassos "
                    f"({iguals}/{total} coincidències)")
            return p
    return None
