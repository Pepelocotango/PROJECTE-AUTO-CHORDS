#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ancoratges humans → mapa de tempo/compàs (Anàlisi guiat **v3**)

Especificació: `docs/ANALISI_GUIAT_v3.md` (R1–R9). Este mòdul és el **nucli
pur** (sense PyQt, sense àudio): rep els ancoratges que ha punxat l'operador i
torna el mapa de tempo/compàs que hi passa **exactament** per damunt, més
l'informe per interval (compassos triats, BPM derivat, desviació, estat).

Model (el que fa possible que tot encaixe):

- El **primer ancoratge és la línia del compàs 1**: és l'`offset` del mapa. La
  zona anterior («cap») no és cap tram propi; el contracte de compassos ja
  permet que el primer tram comence a mig compàs.
- Cada **interval** entre dos ancoratges és **un tram** del mapa, amb metre
  constant (el de l'ancoratge d'inici) i el BPM **derivat** de Δt i del nombre
  enter de compassos:  ``bpm = n · num · (4/den) · 60 / Δt``.
- La **cua** (de l'últim ancoratge al final de l'àudio) allarga l'últim tram
  amb el seu BPM; el final pot ser parcial (excepció del contracte).

Res del que passa ací estima el tempo: només es tria `n` (R5) i es fa
l'aritmètica (R4).
"""
import math

from app import tempo_map

# --- Estats d'un interval (els de R7 + els casos sense decisió) -------------
ESTAT_OK = "ok"
ESTAT_NOTA = "nota"
ESTAT_SOSPITOS = "sospitos"
ESTAT_NO_ENCAIXA = "no_encaixa"
ESTAT_SENSE_REFERENCIA = "sense_referencia"
ESTAT_MASSA_CURT = "massa_curt"
ESTAT_MANUAL = "manual"

# --- Valors per defecte (R5, R7, R12) ---------------------------------------
N_MAX = 64
DESV_NOTA = 0.01
DESV_SOSPITOS = 0.03
DESV_NO_ENCAIXA = 0.10
SEPARACIO_MIN = 0.15        # dos ancoratges més junts que això són un rebot

#: Tolerància del «empat tècnic» en la tria de `n` (R5).
TOL_EMPAT = 0.002


#: El «cap» més curt que això s'absorbeix a la primera secció.
INTRO_MIN = 0.05


def _lletra(i):
    """Lletra de secció: A…Z i després S27, S28… (mai buida)."""
    return chr(ord("A") + i) if 0 <= i < 26 else f"S{i + 1}"


def seccions_de_ancoratges(ancoratges, durada, intro="Intro"):
    """Estructura derivada dels ancoratges: una secció per interval (+ cap).

    Cada **+** és inici de compàs **i** de secció (decisió D3): el tram entre
    dos ancoratges és una secció amb lletra A, B, C…; l'última arriba fins a la
    fi de la WAV. El **cap** (abans del primer ancoratge) és la secció «Intro»
    si dura més de `INTRO_MIN`; si no, s'absorbeix a la primera.
    """
    durada = float(durada or 0.0)
    anc = normalitza_ancoratges(ancoratges, durada)
    if not anc or durada <= 0:
        return []
    talls = [float(a["t"]) for a in anc]
    talls.append(durada)
    out = []
    i_lletra = 0
    for a, b in zip(talls, talls[1:]):
        if b - a <= 1e-9:
            continue
        if not out and a > INTRO_MIN:
            out.append((0.0, a, str(intro), ""))
        out.append((float(a), float(b), _lletra(i_lletra), ""))
        i_lletra += 1
    return out


def bpm_de_n(n, num, den, dt):
    """BPM que fa que `n` compassos `num/den` duren exactament `dt` (R4)."""
    n, num, den, dt = int(n), int(num), int(den), float(dt)
    if dt <= 0:
        raise ValueError("La durada de l'interval ha de ser positiva")
    if n < 1 or num < 1 or den < 1:
        raise ValueError("n, num i den han de ser enters positius")
    return float(n) * float(num) * (4.0 / float(den)) * 60.0 / dt


def normalitza_ancoratges(ancoratges, durada, separacio_min=SEPARACIO_MIN):
    """Valida i ordena els ancoratges.

    Accepta diccionaris (`{"t":…, "num":…, "den":…}`) o tuples
    `(t, num, den)`. Torna una llista de diccionaris ordenada per temps.
    Aixeca `ValueError` amb missatge d'usuari si no es poden fer servir.
    """
    durada = float(durada or 0.0)
    out = []
    for k, a in enumerate(ancoratges or ()):
        if isinstance(a, dict):
            t = a.get("t")
            num = a.get("num", 4)
            den = a.get("den", 4)
        else:
            try:
                t, num, den = a
            except (TypeError, ValueError):
                raise ValueError(
                    f"Ancoratge {k + 1}: format no reconegut") from None
        try:
            t = float(t)
            num = int(num)
            den = int(den)
        except (TypeError, ValueError):
            raise ValueError(f"Ancoratge {k + 1}: valors no numèrics") from None
        if not math.isfinite(t):
            raise ValueError(f"Ancoratge {k + 1}: temps no vàlid")
        if num < 1 or den < 1:
            raise ValueError(f"Ancoratge {k + 1}: compàs {num}/{den} no vàlid")
        if t < -1e-9:
            raise ValueError(f"Ancoratge {k + 1}: temps negatiu ({t:.3f}s)")
        if durada > 0 and t > durada + 1e-6:
            raise ValueError(
                f"Ancoratge {k + 1}: cau fora de l'àudio ({t:.3f}s > "
                f"{durada:.3f}s)")
        out.append({"t": max(0.0, t), "num": num, "den": den})
    out.sort(key=lambda d: d["t"])
    for a, b in zip(out, out[1:]):
        if b["t"] - a["t"] < float(separacio_min):
            raise ValueError(
                "Hi ha dos ancoratges a menys de "
                f"{float(separacio_min):.2f}s ({a['t']:.3f} i {b['t']:.3f})")
    return out


def _ref(detectat, anterior, global_, preferit):
    """Referència `b0` per a un interval, per l'orde de R6."""
    if detectat is not None and float(detectat) > 0:
        return float(detectat), "deteccio"
    if anterior is not None and float(anterior) > 0:
        return float(anterior), "anterior"
    if global_ is not None and float(global_) > 0:
        return float(global_), "global"
    if preferit is not None and float(preferit) > 0:
        return float(preferit), "preferit"
    return None, None


def _candidats(dt, num, den, bpm_min, bpm_max, n_max):
    """`n` enters que deixen el BPM dins del rang (R5)."""
    out = []
    for n in range(1, int(n_max) + 1):
        bpm = bpm_de_n(n, num, den, dt)
        if bpm < float(bpm_min) - 1e-9 or bpm > float(bpm_max) + 1e-9:
            continue
        out.append((n, bpm))
    return out


def _tria(candidats, b0, anterior):
    """Tria `(n, bpm, desviacio)` amb empat tècnic resolt per continuïtat."""
    val = [(abs(bpm - b0) / b0, n, bpm) for n, bpm in candidats]
    val.sort(key=lambda v: (v[0], v[1]))
    millor = val[0][0]
    quasi = [v for v in val if v[0] - millor <= TOL_EMPAT]
    if anterior and len(quasi) > 1:
        quasi.sort(key=lambda v: (abs(v[2] - anterior) / anterior, v[0]))
        elegit = quasi[0]
    else:
        elegit = val[0]
    return elegit[1], elegit[2], elegit[0]


def _estat(desv, desv_nota, desv_sospitos, desv_no_encaixa):
    if desv <= desv_nota:
        return ESTAT_OK
    if desv <= desv_sospitos:
        return ESTAT_NOTA
    if desv <= desv_no_encaixa:
        return ESTAT_SOSPITOS
    return ESTAT_NO_ENCAIXA


def encaixa_ancoratges(ancoratges, durada, deteccions=None, bpm_ref=None, *,
                       bpm_min=60.0, bpm_max=180.0, n_max=N_MAX,
                       desv_nota=DESV_NOTA, desv_sospitos=DESV_SOSPITOS,
                       desv_no_encaixa=DESV_NO_ENCAIXA, n_manual=None,
                       bpm_preferit=None, separacio_min=SEPARACIO_MIN):
    """Encaixa el mapa de tempo/compàs pels ancoratges (nucli de v3).

    Paràmetres
    ----------
    ancoratges : llista de `{"t","num","den"}` o tuples `(t, num, den)`.
    durada : durada de l'àudio, en segons.
    deteccions : un BPM detectat **per interval** (llargada `len(ancoratges)-1`)
        o `None` (llavors mana la referència global/el preferit).
    bpm_ref : referència global del tema (BPM), si n'hi ha.
    n_manual : `{índex_interval: n}` per a forçar compassos (correcció a mà).
    desv_* : llindars de R7 (els mou l'usuari al diàleg).

    Retorna un diccionari::

        {"ok": bool,
         "offset": t_del_primer_ancoratge,
         "trams": [(ini, fi, bpm, num, den), …] | None,
         "intervals": [{idx, ini, fi, dt, num, den, b0, font_b0,
                        n, bpm, desv, estat, nota}, …],
         "sospitosos": [idx…], "no_encaixen": [idx…],
         "cap": segons_abans_del_primer_ancoratge,
         "cua": segons_despres_de_l_ultim,
         "error": str | None}
    """
    durada = float(durada or 0.0)
    if durada <= 0:
        raise ValueError("Cal una durada d'àudio > 0")
    llindars = (float(desv_nota), float(desv_sospitos), float(desv_no_encaixa))
    if not (0 <= llindars[0] < llindars[1] < llindars[2]):
        raise ValueError(
            "Els llindars han de ser creixents (nota < sospitós < no encaixa)")
    if float(bpm_min) <= 0 or float(bpm_max) <= float(bpm_min):
        raise ValueError("El rang de BPM no és vàlid")
    if int(n_max) < 1:
        raise ValueError("N_MAX ha de ser ≥ 1")
    n_manual = dict(n_manual or {})
    anc = normalitza_ancoratges(ancoratges, durada, separacio_min)
    if not anc:
        raise ValueError("Cal almenys un ancoratge")
    realn = len(anc) - 1
    if deteccions is None:
        deteccions = [None] * realn
    deteccions = list(deteccions)
    if len(deteccions) != realn:
        raise ValueError(
            f"Cal un BPM detectat per interval ({realn}), no {len(deteccions)}")

    intervals = []
    trams = []
    anterior = None
    for i in range(realn):
        ini, fi = anc[i]["t"], anc[i + 1]["t"]
        dt = fi - ini
        num, den = anc[i]["num"], anc[i]["den"]
        b0, font = _ref(deteccions[i], anterior, bpm_ref, bpm_preferit)
        info = {"idx": i, "ini": ini, "fi": fi, "dt": dt,
                "num": num, "den": den, "b0": b0, "font_b0": font,
                "n": None, "bpm": None, "desv": None,
                "estat": ESTAT_OK, "nota": ""}
        if b0 is None:
            info["estat"] = ESTAT_SENSE_REFERENCIA
            info["nota"] = "Sense cap BPM de referència"
        elif dt < tempo_map.durada_compas(bpm_max, num, den) - 1e-9:
            info["estat"] = ESTAT_MASSA_CURT
            info["nota"] = "No hi cap un compàs a este tempo"
        else:
            cands = _candidats(dt, num, den, bpm_min, bpm_max, n_max)
            if not cands:
                info["estat"] = ESTAT_NO_ENCAIXA
                info["nota"] = ("Cap nombre de compassos dóna un BPM dins "
                                f"del rang {bpm_min:g}–{bpm_max:g}")
            else:
                n, bpm, desv = _tria(cands, b0, anterior)
                info.update({"n": n, "bpm": bpm, "desv": desv})
                info["estat"] = _estat(desv, *llindars)
                if info["estat"] == ESTAT_NO_ENCAIXA:
                    if font in ("global", "preferit"):
                        # El primer interval (o un sense cadena) MANA: no es
                        # pot rebutjar per allunyar-se d'una referència global
                        # que sovint és el 120 per defecte de l'app (cas real
                        # 21-10: tema a ~100 BPM → tot el guiat bloquejat).
                        info["estat"] = ESTAT_NOTA
                        info["nota"] = (
                            f"BPM derivat {bpm:.2f}: s'allunya un "
                            f"{desv * 100:.1f} % del de la barra ({b0:.2f}); "
                            "s'accepta com a referència del tema")
                    else:
                        info["nota"] = (f"El BPM derivat ({bpm:.2f}) s'allunya "
                                        f"un {desv * 100:.1f} % del de "
                                        f"l'interval anterior ({b0:.2f})")
        if i in n_manual:
            n = int(n_manual[i])
            if n < 1:
                raise ValueError("n manual ha de ser ≥ 1")
            bpm = bpm_de_n(n, num, den, dt)
            info.update({"n": n, "bpm": bpm,
                         "desv": abs(bpm - b0) / b0 if b0 else None,
                         "estat": ESTAT_MANUAL,
                         "nota": "Compassos forçats a mà"})
        if info["n"] is not None:
            anterior = info["bpm"]
        intervals.append(info)

    offset = anc[0]["t"]
    bons = (ESTAT_OK, ESTAT_NOTA, ESTAT_SOSPITOS, ESTAT_MANUAL)
    if any(d["estat"] not in bons for d in intervals):
        return {"ok": False, "offset": offset, "trams": None,
                "intervals": intervals,
                "sospitosos": [d["idx"] for d in intervals
                               if d["estat"] == ESTAT_SOSPITOS],
                "no_encaixen": [d["idx"] for d in intervals
                                if d["estat"] not in bons],
                "cap": offset, "cua": max(0.0, durada - anc[-1]["t"]),
                "error": "Hi ha intervals sense encaixar"}

    # --- Construcció del mapa -------------------------------------------
    if not intervals:
        # Un sol ancoratge: tot el tema amb el BPM de referència (R6/R9).
        b0, _font = _ref(None, None, bpm_ref, bpm_preferit)
        if b0 is None:
            return {"ok": False, "offset": offset, "trams": None,
                    "intervals": intervals, "sospitosos": [],
                    "no_encaixen": [], "cap": offset,
                    "cua": durada - anc[0]["t"],
                    "error": "Amb un sol ancoratge cal un BPM de "
                             "referència (detecta el tempo o posa'n un)"}
        trams = [(0.0, durada, b0, anc[0]["num"], anc[0]["den"])]
    else:
        for i, d in enumerate(intervals):
            ini = 0.0 if i == 0 else d["ini"]  # el cap s'absorbeix (offset)
            trams.append((ini, d["fi"], d["bpm"], d["num"], d["den"]))
        if durada > anc[-1]["t"] + 1e-9:
            ult = intervals[-1]
            trams.append((anc[-1]["t"], durada, ult["bpm"], ult["num"],
                          ult["den"]))

    error = None
    try:
        trams = tempo_map.valida_i_normalitza_compassos(
            trams, durada, offset=offset)
    except ValueError as e:  # contracte de compassos (R15)
        error = str(e)
        return {"ok": False, "offset": offset, "trams": None,
                "intervals": intervals,
                "sospitosos": [d["idx"] for d in intervals
                               if d["estat"] == ESTAT_SOSPITOS],
                "no_encaixen": [], "cap": offset,
                "cua": max(0.0, durada - anc[-1]["t"]), "error": error}

    return {"ok": True, "offset": offset, "trams": trams,
            "intervals": intervals,
            "sospitosos": [d["idx"] for d in intervals
                           if d["estat"] == ESTAT_SOSPITOS],
            "no_encaixen": [d["idx"] for d in intervals
                            if d["estat"] == ESTAT_NO_ENCAIXA],
            "cap": offset, "cua": max(0.0, durada - anc[-1]["t"]),
            "error": error}


def linies_de_compas(trams, offset=0.0):
    """Temps de les línies de compàs del mapa (mateixa lògica que el mapa)."""
    out = []
    for idx, tram in enumerate(trams or ()):
        ini, fi, bpm, num, den = (float(tram[0]), float(tram[1]),
                                  float(tram[2]), int(tram[3]), int(tram[4]))
        b = tempo_map.durada_compas(bpm, num, den)
        if b <= 1e-12:
            continue
        base = float(offset) if (idx == 0 and abs(ini) <= 1e-9
                                 and float(offset) > 1e-9) else ini
        k0 = int(math.floor((ini - base) / b)) - 1
        k1 = int(math.ceil((fi - base) / b)) + 1
        out += [base + k * b for k in range(k0, k1 + 1)]
    return sorted(out)


def verifica_ancoratges(trams, ancoratges, offset=0.0, tol=1e-6):
    """True si **cada** ancoratge cau en una línia de compàs (R2)."""
    linies = linies_de_compas(trams, offset)
    if not linies:
        return False
    anc = normalitza_ancoratges(ancoratges, 0.0, separacio_min=0.0)
    for a in anc:
        if not any(abs(a["t"] - t) <= tol for t in linies):
            return False
    return True
