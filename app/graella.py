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
- la **regularització del ritme harmònic** (`regularitza_acords`): encaixa els
  canvis crus a la graella, en deixa un per cel·la i omple els buits,
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


def regularitza_acords(items, bpm, bpb, offset, nivell, durada, log=None):
    """Un acord per cel·la de la graella (ritme harmònic), a partir dels canvis crus.

    - Cada canvi cru s'encaixa a la cel·la del nivell (`compas`/`mig`/`temps`).
    - Si diversos canvis cauen a la mateixa cel·la, es queda el **dominant**
      (el que, als crus, ocupa més temps).
    - Les cel·les sense canvi queden cobertes per l'acord que hi arriba (l'últim
      anterior) en aplicar-hi la cobertura total (#4) a fora.
    Retorna `[(t_cel·la, nom), …]` ordenat. No muta l'entrada.
    """
    items = [(float(t), str(n)) for (t, n) in items]
    if not items:
        return []
    pas = nivell_segons(nivell, bpm, bpb)
    if pas <= 0:
        return sorted(items, key=lambda x: x[0])
    durada = float(durada or 0.0)
    off = float(offset or 0.0)
    ordenats = sorted(items, key=lambda x: x[0])
    n = len(ordenats)
    cells = {}
    for i, (t, nom) in enumerate(ordenats):
        fi = ordenats[i + 1][0] if i + 1 < n else (durada or t)
        dur = max(0.0, fi - t)
        k = int(round((t - off) / pas))
        tc = off + k * pas
        if tc < -1e-9 or (durada and tc >= durada - 1e-9):
            continue
        if k not in cells or dur > cells[k][2]:
            cells[k] = (max(0.0, tc), nom, dur)
    res = [(cells[k][0], cells[k][1]) for k in sorted(cells)]
    if log:
        log(f"ritme harmònic ({nivell}): {n} canvis → {len(res)} acords")
    return res


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

    Amb l'estructura del pop (blocs de 4/8/16 compassos), els talls solen caure
    a fronteres de bloc. Aquí arrodonim cada tall interior a la frontera més
    propera d'un bloc de `modul_compassos`, mantenim l'etiqueta de la secció que
    «guanya» el tram, i preservem la cobertura [0, durada]. No muta l'entrada.
    """
    seccions = [(float(i), float(f), str(l), str(fa)) for (i, f, l, fa) in seccions]
    if len(seccions) < 2 or not modul_compassos or modul_compassos <= 0:
        return seccions
    pas = nivell_segons("compas", bpm, bpb) * int(modul_compassos)
    if pas <= 0:
        return seccions
    durada = float(durada or seccions[-1][1])
    off = float(offset or 0.0)

    def snap(t):
        return max(0.0, off + round((t - off) / pas) * pas)

    talls = [0.0]
    for i in range(1, len(seccions)):
        s = snap(seccions[i][0])
        if s > talls[-1] + 1e-6 and (not durada or s < durada - 1e-6):
            talls.append(s)
    talls.append(durada if durada else seccions[-1][1])
    res = []
    for j in range(len(talls) - 1):
        ini, fi = talls[j], talls[j + 1]
        if fi - ini <= 1e-6:
            continue
        mig = (ini + fi) / 2.0
        lab, fam = seccions[0][2], seccions[0][3]
        for (si, sf, sl, sfa) in seccions:
            if si <= mig < sf:
                lab, fam = sl, sfa
                break
        res.append((ini, fi, lab, fam))
    if log:
        log(f"estructura: {len(seccions)} → {len(res)} seccions "
            f"(blocs de {int(modul_compassos)} compassos)")
    return res


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
