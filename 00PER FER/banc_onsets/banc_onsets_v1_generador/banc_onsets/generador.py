# -*- coding: utf-8 -*-
"""Generador del banc sintètic d'atacs · Fase 0.A · especificació v1.

És l'INSTRUMENT DE MESURA. No importa ni executa cap detector (ni `app.tempo`):
només genera senyals amb referència analítica coneguda.

Principis (de l'especificació congelada, Fase 0.C):

* L'atac es genera a una **posició fraccionària de mostra**: `t0 = 0,300 s +
  U[0, 10 ms)`, i els senyals s'avaluen en temps continu.
* Les **referències** (inici físic, 10 %, 50 %, pic) es calculen sobre el senyal
  net **sobremostrejat x16**, ja filtrat, amb codi independent del detector.
  Finestra de referència: [t0, t0 + 80 ms].
* Conjunts separats: desenvolupament (llavors 1-999) i validació (10000+). La
  validació només es genera amb `--permet-validacio` i `--hash-congelat`
  coincident amb el hash dels paràmetres.
* Cada cas es desa amb la seva llavor i els paràmetres resolts (JSONL).

Decisions que el generador ha hagut de prendre i que l'operador ha de
confirmar abans de congelar (vegeu LLEGEIX.md).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import sys
import wave
import zlib
from dataclasses import dataclass, field

import numpy as np
from scipy import signal

from . import anotador_virtual

VERSIO = "v1"
DURADA_S = 0.9
T0_BASE_S = 0.300
T0_JITTER_S = 0.010
SOBREMOSTREIG = 16
FINESTRA_REF_S = 0.080
SNR_NET_DB = 60.0          # «net» = SNR pic/soroll de 60 dB (decisió d'aquest build)
PIC_OBJ = 0.80
MARGE_AB_S = 0.030
REPS_DEFECTE = 30
LLAVORS_DEV = (1, 999)
LLAVORS_VAL_INICI = 10000
FADE_IN_S = 0.6
FADE_SOSTINGUT_S = 0.05
FONS_NET = {"tipus": "blanc", "snr_db": SNR_NET_DB}

CRIT_NET = {"p95_ms": 1.0, "max_ms": 2.0, "fallback_max_pct": 0.0}


# ---------------------------------------------------------------------------
# Condicions (especificació v1)
# ---------------------------------------------------------------------------
def _cond(id_, grup, font=None, **kw):
    c = {
        "id": id_, "grup": grup, "font": font, "altres": [], "sostingut": [],
        "filtre": None, "soroll": FONS_NET, "sr": 44100, "fmt": "pcm16",
        "canals": "mono", "a_off_s": -0.080, "tipus_esperat": "atac",
        "criteri": dict(CRIT_NET), "informatiu": False, "opcional": False,
        "nota": "",
    }
    c.update(kw)
    return c


def condicions_v1():
    """Llista completa de condicions (inclou les opcionals, marcades)."""
    C = []

    # --- A: atacs nets -----------------------------------------------------
    for r in (1.0, 2.0, 4.0):
        C.append(_cond(f"A1_bombo_r{r:g}", "A", {"tipus": "bombo", "rise_ms": r}))
    for r in (1.0, 2.0, 3.0):
        C.append(_cond(f"A2_caixa_r{r:g}", "A", {"tipus": "caixa", "rise_ms": r}))
    for r in (10.0, 25.0, 50.0):
        for forma in ("lineal", "cosinus", "exponencial"):
            C.append(_cond(f"A3_acord_r{r:g}_{forma}", "A",
                           {"tipus": "acord", "rise_ms": r, "forma": forma}))
    for r in (30.0, 60.0):
        C.append(_cond(f"A4_baix_r{r:g}", "A", {"tipus": "baix", "rise_ms": r},
                       criteri={"p95_ms": 2.0, "fallback_max_pct": 0.0}))
    C.append(_cond("A4_baix_r120", "A", {"tipus": "baix", "rise_ms": 120.0},
                   criteri={}, informatiu=True, tipus_esperat="informatiu",
                   nota="Pujada de 120 ms > finestra de referència de 80 ms: "
                        "el pic de la referència queda tallat. Límit conegut."))
    for sep in (10.0, 15.0, 30.0):   # OPCIONAL: no és a l'especificació congelada
        C.append(_cond(f"A5_flam_{sep:g}ms", "A",
                       {"tipus": "bombo", "rise_ms": 2.0},
                       altres=[{"tipus": "bombo", "rise_ms": 2.0,
                                "dt_s": sep / 1000.0, "ratio": 0.9}],
                       criteri={}, informatiu=True, opcional=True,
                       nota="Referència = primer atac."))

    # --- B: soroll ---------------------------------------------------------
    fonts_b = (("bombo", {"tipus": "bombo", "rise_ms": 2.0}),
               ("acord", {"tipus": "acord", "rise_ms": 25.0, "forma": "lineal"}))
    for nom, f in fonts_b:
        for color in ("blanc", "rosa"):
            for snr in (60.0, 40.0, 30.0, 20.0, 12.0):
                if snr >= 30:
                    crit, inf = {"p95_ms": 2.0}, False
                elif snr >= 20:
                    crit, inf = {"p95_ms": 4.0, "fallback_max_pct": 5.0}, False
                else:
                    crit, inf = {}, True
                C.append(_cond(f"B_{nom}_{color}_{snr:g}dB", "B", dict(f),
                               soroll={"tipus": color, "snr_db": snr},
                               criteri=crit, informatiu=inf,
                               tipus_esperat="informatiu" if inf else "atac"))

    # --- C: fons que emmascaren -------------------------------------------
    crit_c = {"p95_ms": 3.0, "equivocat_max_pct": 0.0}
    for nom, f in fonts_b:
        C.append(_cond(f"C1_baix_sostingut_{nom}", "C", dict(f),
                       sostingut=[{"tipus": "baix_sostingut", "hz": 55.0,
                                   "db": -20.0}], criteri=dict(crit_c)))
        C.append(_cond(f"C2_pad_{nom}", "C", dict(f),
                       sostingut=[{"tipus": "pad", "db": -18.0}],
                       criteri=dict(crit_c)))
    for dist in (150.0, 80.0, 40.0):
        for ratio in (1.0, 0.5, 0.2):
            C.append(_cond(f"C3_previ_{dist:g}ms_x{ratio:g}", "C",
                           {"tipus": "bombo", "rise_ms": 2.0},
                           altres=[{"tipus": "bombo", "rise_ms": 2.0,
                                    "dt_s": -dist / 1000.0, "ratio": ratio}],
                           a_off_s=-0.020, criteri=dict(crit_c),
                           nota="A = 20 ms abans del 10 %: l'esdeveniment previ "
                                "queda fora de [A,B) i només actua com a màscara."))

    # --- D: filtres (combinacions amb energia; les altres s'ometen) -------
    d = [("bombo", {"tipus": "bombo", "rise_ms": 2.0},
          [("passabaix_200", {"tipus": "passabaix", "fc": 200.0}),
           ("passabanda_100_5k", {"tipus": "passabanda", "f1": 100.0, "f2": 5000.0})]),
         ("caixa", {"tipus": "caixa", "rise_ms": 2.0},
          [("passabaix_200", {"tipus": "passabaix", "fc": 200.0}),
           ("passaalt_2k", {"tipus": "passaalt", "fc": 2000.0}),
           ("passabanda_100_5k", {"tipus": "passabanda", "f1": 100.0, "f2": 5000.0})]),
         ("acord", {"tipus": "acord", "rise_ms": 25.0, "forma": "lineal"},
          [("passabaix_600", {"tipus": "passabaix", "fc": 600.0}),
           ("passabanda_100_5k", {"tipus": "passabanda", "f1": 100.0, "f2": 5000.0})])]
    for nom, f, fils in d:
        for nf, spec in fils:
            C.append(_cond(f"D_{nom}_{nf}", "D", dict(f), filtre=spec,
                           criteri={"p95_ms": 2.0}))

    # --- E: posició d'A respecte del 10 % de l'atac objectiu -------------
    e_fonts = (("bombo", {"tipus": "bombo", "rise_ms": 2.0}),
               ("acord", {"tipus": "acord", "rise_ms": 25.0, "forma": "lineal"}))
    for nom, f in e_fonts:
        for off_ms in (-80, -20, 0, 15, 25, 40):
            C.append(_cond(f"E_{nom}_A{off_ms:+d}ms", "E", dict(f),
                           a_off_s=off_ms / 1000.0, tipus_esperat="E",
                           criteri={"p95_ms": 1.0}))
    for off_ms in (29, 31):          # OPCIONAL: frontera del marge
        C.append(_cond(f"E_bombo_A{off_ms:+d}ms", "E",
                       {"tipus": "bombo", "rise_ms": 2.0},
                       a_off_s=off_ms / 1000.0, tipus_esperat="E",
                       criteri={}, informatiu=True, opcional=True))

    # --- F: format, freqüència, canals ------------------------------------
    bombo = {"tipus": "bombo", "rise_ms": 2.0}
    C.append(_cond("F1_pcm16", "F", dict(bombo), fmt="pcm16"))
    for fmt in ("pcm24", "float32"):
        C.append(_cond(f"F1a_{fmt}", "F", dict(bombo), fmt=fmt,
                       tipus_esperat="error_explicit", criteri={},
                       nota="Detector directe: ha de rebutjar el format."))
    C.append(_cond("F2_48000", "F", dict(bombo), sr=48000))
    for can in ("estereo_correlat", "un_canal", "oposicio"):
        C.append(_cond(f"F3_{can}", "F", dict(bombo), canals=can,
                       nota="Oposició de fase: defecte que el banc ha de "
                            "reproduir i que cal corregir." if can == "oposicio" else ""))

    # --- G: robustesa (informatiu) ----------------------------------------
    C.append(_cond("G_dc_2pc", "G", dict(bombo), dc=0.02, criteri={},
                   informatiu=True, tipus_esperat="informatiu"))
    C.append(_cond("G_clipping", "G", dict(bombo), pic_obj=1.4, clip=True,
                   criteri={}, informatiu=True, tipus_esperat="informatiu"))
    C.append(_cond("G_fade_in", "G", dict(bombo), fade_in=True, criteri={},
                   informatiu=True, tipus_esperat="informatiu"))

    # --- N: controls negatius (0 onsets) ----------------------------------
    cn = dict(grup="N", tipus_esperat="cap", criteri={"onsets_max": 0})
    C.append(_cond("N1_soroll_blanc_54dB", font=None,
                   soroll={"tipus": "blanc", "sigma": 0.002}, a_abs_s=0.1, **cn))
    C.append(_cond("N2_soroll_blanc_30dB", font=None,
                   soroll={"tipus": "blanc", "sigma": 0.03}, a_abs_s=0.1, **cn))
    C.append(_cond("N3_soroll_rosa", font=None,
                   soroll={"tipus": "rosa", "sigma": 0.01}, a_abs_s=0.1, **cn))
    C.append(_cond("N4_to_sostingut_220Hz", font=None,
                   sostingut=[{"tipus": "to", "hz": 220.0, "nivell_abs": 0.3}],
                   soroll={"tipus": "blanc", "sigma": 0.002}, a_abs_s=0.1, **cn))
    C.append(_cond("N5_pad_sostingut", font=None,
                   sostingut=[{"tipus": "pad", "nivell_abs": 0.2}],
                   soroll={"tipus": "blanc", "sigma": 0.002}, a_abs_s=0.1, **cn))
    C.append(_cond("N6_decaiment_pur", font={"tipus": "bombo", "rise_ms": 2.0},
                   t0_base_s=0.100, a_off_s=0.200, **cn))
    C.append(_cond("N7_silenci_digital", font=None, soroll=None, a_abs_s=0.1, **cn))
    return C


def parametres_banc():
    """Tots els paràmetres del banc (és el que l'operador converteix en hash)."""
    return {
        "versio": VERSIO,
        "durada_s": DURADA_S, "t0_base_s": T0_BASE_S, "t0_jitter_s": T0_JITTER_S,
        "sobremostreig": SOBREMOSTREIG, "finestra_referencia_s": FINESTRA_REF_S,
        "snr_net_db": SNR_NET_DB, "pic_obj": PIC_OBJ, "marge_ab_s": MARGE_AB_S,
        "fade_in_s": FADE_IN_S, "fade_sostingut_s": FADE_SOSTINGUT_S,
        "reps_defecte": REPS_DEFECTE,
        "llavors_dev": list(LLAVORS_DEV), "llavors_val_inici": LLAVORS_VAL_INICI,
        "definicio_snr": "pic de |x| del senyal net de l'objectiu a [t0, t0+80ms] "
                         "/ RMS del soroll",
        "anotador_virtual": anotador_virtual.parametres(),
        "condicions": condicions_v1(),
    }


def hash_parametres():
    canonic = json.dumps(parametres_banc(), sort_keys=True,
                         separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonic.encode("ascii")).hexdigest()


# ---------------------------------------------------------------------------
# Síntesi (en temps continu, a fs16 = 16 x sr)
# ---------------------------------------------------------------------------
def _pujada(tau, rise_s, forma):
    x = np.clip(tau / rise_s, 0.0, 1.0)
    if forma == "lineal":
        return x
    if forma == "cosinus":
        return 0.5 * (1.0 - np.cos(np.pi * x))
    if forma == "exponencial":
        return (np.exp(4.0 * x) - 1.0) / (np.exp(4.0) - 1.0)
    raise ValueError(f"forma desconeguda: {forma!r}")


def _env(tau, rise_s, decay, forma="lineal"):
    pos = np.maximum(tau, 0.0)
    return np.where(tau >= 0.0,
                    _pujada(tau, rise_s, forma) * np.exp(-decay * pos), 0.0)


def _sintetitza(t, t0, spec, rng):
    """Retorna (senyal cru, paràmetres resolts)."""
    tip = spec["tipus"]
    tau = t - t0
    pos = np.maximum(tau, 0.0)
    rise = float(spec.get("rise_ms", 2.0)) / 1000.0
    forma = spec.get("forma", "lineal")
    if tip == "bombo":
        p = {"f_ini": float(rng.uniform(100, 150)), "f_fi": float(rng.uniform(40, 60)),
             "k_f": float(rng.uniform(30, 50)), "decay": float(rng.uniform(15, 40))}
        fase = 2 * np.pi * (p["f_fi"] * pos + (p["f_ini"] - p["f_fi"])
                            * (1 - np.exp(-p["k_f"] * pos)) / p["k_f"])
        return _env(tau, rise, p["decay"], forma) * np.sin(fase), p
    if tip == "caixa":
        p = {"decay": float(rng.uniform(25, 45))}
        return _env(tau, rise, p["decay"], forma) * rng.standard_normal(t.size), p
    if tip == "acord":
        n = int(rng.integers(4, 7))
        f0 = float(rng.uniform(130, 520))
        ratios = [1.0, 1.26, 1.5, 2.0, 2.52, 3.0][:n]
        fases = rng.uniform(0, 2 * np.pi, n)
        p = {"f0": f0, "parcials": n, "decay": float(rng.uniform(2.5, 3.5)),
             "fases": [float(v) for v in fases]}
        s = sum(np.sin(2 * np.pi * f0 * r * pos + ph) / (i + 1)
                for i, (r, ph) in enumerate(zip(ratios, fases)))
        return _env(tau, rise, p["decay"], forma) * s, p
    if tip == "baix":
        p = {"f0": float(rng.uniform(41, 98)), "decay": float(rng.uniform(3, 5)),
             "fase": float(rng.uniform(0, 2 * np.pi))}
        return _env(tau, rise, p["decay"], forma) * np.sin(
            2 * np.pi * p["f0"] * pos + p["fase"]), p
    raise ValueError(f"font desconeguda: {tip!r}")


def _sostingut(t, spec, rng):
    tip = spec["tipus"]
    rampa = np.clip(t / FADE_SOSTINGUT_S, 0.0, 1.0)
    if tip in ("baix_sostingut", "to"):
        return rampa * np.sin(2 * np.pi * float(spec["hz"]) * t
                              + rng.uniform(0, 2 * np.pi))
    if tip == "pad":
        fr = (196.0, 246.9, 293.7, 392.0)
        return rampa * sum(np.sin(2 * np.pi * f * t + rng.uniform(0, 2 * np.pi))
                           for f in fr)
    raise ValueError(f"sostingut desconegut: {tip!r}")


def _lp_antialias(x, fs16, sr):
    sos = signal.butter(4, 0.45 * sr, btype="low", fs=fs16, output="sos")
    return signal.sosfilt(sos, x)


def _filtre_cas(x, fs16, spec):
    if not spec:
        return x
    t = spec["tipus"]
    if t == "passabaix":
        sos = signal.butter(4, spec["fc"], "low", fs=fs16, output="sos")
    elif t == "passaalt":
        sos = signal.butter(4, spec["fc"], "high", fs=fs16, output="sos")
    elif t == "passabanda":
        sos = signal.butter(4, [spec["f1"], spec["f2"]], "band", fs=fs16,
                            output="sos")
    else:
        raise ValueError(f"filtre desconegut: {t!r}")
    return signal.sosfilt(sos, x)


def _norm_pic(x, pic):
    m = float(np.max(np.abs(x)))
    return x * (pic / m) if m > 0 else x


def _soroll(tipus, n, sigma, rng):
    if tipus == "blanc":
        return rng.standard_normal(n) * sigma
    if tipus == "rosa":
        X = np.fft.rfft(rng.standard_normal(n))
        f = np.arange(X.size, dtype=np.float64)
        f[0] = 1.0
        X = X / np.sqrt(f)
        X[0] = 0.0
        y = np.fft.irfft(X, n)
        return y / y.std() * sigma
    raise ValueError(f"soroll desconegut: {tipus!r}")


def referencies(x16, fs16, t0):
    """Referències analítiques sobre el senyal net sobremostrejat."""
    i0 = int(round(t0 * fs16))
    i1 = i0 + int(round(FINESTRA_REF_S * fs16))
    seg = np.abs(x16[i0:i1])
    pic = float(seg.max())
    if pic <= 0:
        raise ValueError("objectiu sense energia a la finestra de referència")

    def creua(frac):
        return (i0 + int(np.argmax(seg > frac * pic))) / fs16

    return {"t_fisic": float(t0), "t10": creua(0.10), "t50": creua(0.50),
            "t_pic": (i0 + int(np.argmax(seg))) / fs16, "pic": pic}


def _esperat(cond):
    tip = cond["tipus_esperat"]
    if tip == "atac":
        e = {"tipus": "atac", "ref": "t10"}
        return {"detecta_onsets": e, "onsets_ab": e}
    if tip == "informatiu":
        e = {"tipus": "informatiu", "ref": "t10"}
        return {"detecta_onsets": e, "onsets_ab": e}
    if tip == "error_explicit":
        e = {"tipus": "error_explicit"}
        return {"detecta_onsets": e, "onsets_ab": e}
    if tip == "cap":
        e = {"tipus": "cap"}
        return {"detecta_onsets": e, "onsets_ab": e}
    if tip == "E":
        off = cond["a_off_s"]
        atac = {"tipus": "atac", "ref": "t10"}
        cap = {"tipus": "cap_atac_objectiu"}
        if off < -1e-9:
            return {"detecta_onsets": atac, "onsets_ab": atac}
        if abs(off) <= 1e-9:
            return {"detecta_onsets": {"tipus": "frontera"}, "onsets_ab": atac}
        if off <= MARGE_AB_S + 1e-9:
            return {"detecta_onsets": cap,
                    "onsets_ab": {"tipus": "atac_fora_rang", "ref": "t10"}}
        return {"detecta_onsets": cap, "onsets_ab": cap}
    raise ValueError(f"tipus_esperat desconegut: {tip!r}")


# ---------------------------------------------------------------------------
# Renderitzat d'un cas
# ---------------------------------------------------------------------------
@dataclass
class Cas:
    id: str
    grup: str
    cond_id: str
    seed: int
    sr: int
    fmt: str
    canals: str
    t0: float | None
    A: float
    B: float
    refs: dict | None
    esperat: dict
    criteri: dict
    informatiu: bool
    opcional: bool
    params_font: dict
    snr_db: float | None
    rise_ms: float | None
    filtre: str
    senyal: np.ndarray = field(repr=False, default=None)

    def descripcio(self):
        d = {k: v for k, v in self.__dict__.items() if k != "senyal"}
        return d


def _seed_seq(cond_id, seed, extra=0):
    return np.random.SeedSequence([int(seed), zlib.crc32(cond_id.encode()), extra])


def renderitza(cond, seed, amb_soroll=True):
    sr = int(cond["sr"])
    fs16 = sr * SOBREMOSTREIG
    n = int(round(DURADA_S * sr))
    n16 = n * SOBREMOSTREIG
    t16 = np.arange(n16) / fs16
    rng = np.random.default_rng(_seed_seq(cond["id"], seed))
    t0 = float(cond.get("t0_base_s", T0_BASE_S) + rng.uniform(0, T0_JITTER_S))
    pic_obj = float(cond.get("pic_obj", PIC_OBJ))
    filtre = cond.get("filtre")

    def prepara(x):
        return _filtre_cas(_lp_antialias(x, fs16, sr), fs16, filtre)

    def modifica(x):
        if cond.get("fade_in"):
            x = x * np.clip(t16 / FADE_IN_S, 0.0, 1.0)
        if cond.get("clip"):
            x = np.clip(x, -1.0, 1.0)
        return x

    params = {}
    target16 = refs = pic_ref = None
    if cond.get("font"):
        raw, params["font"] = _sintetitza(t16, t0, cond["font"], rng)
        target16 = _norm_pic(prepara(raw), pic_obj)
        t_mod = modifica(target16)
        refs = referencies(t_mod, fs16, t0)
        pic_ref = refs["pic"]
    mix16 = np.zeros(n16)
    if target16 is not None:
        mix16 += target16
    params["altres"] = []
    for alt in cond.get("altres", []):
        raw, pr = _sintetitza(t16, t0 + alt["dt_s"], alt, rng)
        mix16 += _norm_pic(prepara(raw), pic_obj * float(alt["ratio"]))
        params["altres"].append(pr)
    for s in cond.get("sostingut", []):
        x = _norm_pic(prepara(_sostingut(t16, s, rng)), 1.0)
        if "db" in s:
            if pic_ref is None:
                raise ValueError("nivell relatiu sense objectiu")
            amp = pic_ref * 10 ** (float(s["db"]) / 20.0)
        else:
            amp = float(s["nivell_abs"])
        mix16 += amp * x
    mix16 = modifica(mix16)

    mix = mix16[::SOBREMOSTREIG].copy()          # senyal limitat en banda
    snr_db = None
    fons = cond.get("soroll")
    if fons and amb_soroll:
        rng_s = np.random.default_rng(_seed_seq(cond["id"], seed, 1))
        if "snr_db" in fons:
            snr_db = float(fons["snr_db"])
            sigma = pic_ref * 10 ** (-snr_db / 20.0)
        else:
            sigma = float(fons["sigma"])
        mix += _soroll(fons["tipus"], n, sigma, rng_s)
    if cond.get("dc"):
        mix += float(cond["dc"])

    can = cond["canals"]
    if can == "mono":
        sen = mix
    elif can == "estereo_correlat":
        sen = np.stack([mix, 0.9 * mix], axis=1)
    elif can == "un_canal":
        sen = np.stack([mix, np.zeros_like(mix)], axis=1)
    elif can == "oposicio":
        sen = np.stack([mix, -mix], axis=1)
    else:
        raise ValueError(f"canals desconeguts: {can!r}")

    if refs is not None:
        A = max(0.0, refs["t10"] + float(cond["a_off_s"]))
    else:
        A = float(cond.get("a_abs_s", 0.1))
    f = cond.get("font") or {}
    return Cas(
        id=f"{cond['id']}__s{int(seed):05d}", grup=cond["grup"], cond_id=cond["id"],
        seed=int(seed), sr=sr, fmt=cond["fmt"], canals=can, t0=t0, A=float(A),
        B=float(DURADA_S), refs=refs, esperat=_esperat(cond),
        criteri=cond["criteri"], informatiu=bool(cond["informatiu"]),
        opcional=bool(cond["opcional"]), params_font=params, snr_db=snr_db,
        rise_ms=f.get("rise_ms"),
        filtre=(filtre["tipus"] if filtre else "completa"), senyal=sen)


# ---------------------------------------------------------------------------
# Escriptura de WAV (PCM16, PCM24, float32)
# ---------------------------------------------------------------------------
def escriu_wav(path, senyal, sr, fmt="pcm16"):
    x = np.clip(np.asarray(senyal, dtype=np.float64), -1.0, 1.0)
    canals = 1 if x.ndim == 1 else x.shape[1]
    inter = x.reshape(-1)
    if fmt == "pcm16":
        dades = np.round(inter * 32767).astype("<i2").tobytes()
        sw = 2
    elif fmt == "pcm24":
        i32 = np.round(inter * 8388607).astype("<i4")
        dades = i32.view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
        sw = 3
    elif fmt == "float32":
        dades = inter.astype("<f4").tobytes()
        sw = 4
    else:
        raise ValueError(f"format desconegut: {fmt!r}")
    if fmt in ("pcm16", "pcm24"):
        with wave.open(path, "wb") as w:
            w.setnchannels(canals)
            w.setsampwidth(sw)
            w.setframerate(int(sr))
            w.writeframes(dades)
        return
    frames = inter.size // canals
    fmt_chunk = struct.pack("<HHIIHH", 3, canals, int(sr), int(sr) * canals * 4,
                            canals * 4, 32)
    fact = struct.pack("<I", frames)
    cos = (b"WAVE" + b"fmt " + struct.pack("<I", len(fmt_chunk)) + fmt_chunk
           + b"fact" + struct.pack("<I", 4) + fact
           + b"data" + struct.pack("<I", len(dades)) + dades)
    with open(path, "wb") as fh:
        fh.write(b"RIFF" + struct.pack("<I", len(cos)) + cos)


# ---------------------------------------------------------------------------
# Enumeració i CLI
# ---------------------------------------------------------------------------
def llavors(conjunt, reps):
    if conjunt == "dev":
        if not (1 <= reps <= LLAVORS_DEV[1]):
            raise ValueError("reps fora de 1..999 per al conjunt dev")
        return list(range(LLAVORS_DEV[0], LLAVORS_DEV[0] + reps))
    if conjunt == "val":
        return list(range(LLAVORS_VAL_INICI + 1, LLAVORS_VAL_INICI + 1 + reps))
    raise ValueError(f"conjunt desconegut: {conjunt!r}")


def selecciona(grups=None, opcionals=False):
    out = []
    for c in condicions_v1():
        if c["opcional"] and not opcionals:
            continue
        if grups and c["grup"] not in grups:
            continue
        out.append(c)
    return out


def itera_casos(conjunt="dev", grups=None, reps=REPS_DEFECTE, opcionals=False,
                amb_soroll=True):
    for cond in selecciona(grups, opcionals):
        for s in llavors(conjunt, reps):
            yield renderitza(cond, s, amb_soroll=amb_soroll)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generador del banc sintètic d'atacs")
    ap.add_argument("--conjunt", choices=["dev", "val"], default="dev")
    ap.add_argument("--sortida", required=True)
    ap.add_argument("--grups", default="", help="p. ex. A,B,N (buit = tots)")
    ap.add_argument("--reps", type=int, default=REPS_DEFECTE)
    ap.add_argument("--opcionals", action="store_true")
    ap.add_argument("--hash-congelat", default="")
    ap.add_argument("--permet-validacio", action="store_true")
    a = ap.parse_args(argv)

    h = hash_parametres()
    if a.conjunt == "val":
        if not a.permet_validacio or a.hash_congelat != h:
            sys.exit("Validació bloquejada: cal --permet-validacio i "
                     "--hash-congelat igual al hash actual dels paràmetres.\n"
                     f"hash actual: {h}")
    elif a.hash_congelat and a.hash_congelat != h:
        print(f"AVÍS: el hash congelat no coincideix amb l'actual ({h}).",
              file=sys.stderr)

    grups = [g for g in a.grups.split(",") if g]
    os.makedirs(a.sortida, exist_ok=True)
    with open(os.path.join(a.sortida, "parametres_v1.json"), "w",
              encoding="utf-8") as fh:
        json.dump(parametres_banc(), fh, indent=1, sort_keys=True,
                  ensure_ascii=False)
    n = 0
    with open(os.path.join(a.sortida, "casos.jsonl"), "w", encoding="utf-8") as jl:
        for cas in itera_casos(a.conjunt, grups or None, a.reps, a.opcionals):
            rel = os.path.join(cas.grup, cas.cond_id, f"s{cas.seed:05d}.wav")
            os.makedirs(os.path.join(a.sortida, os.path.dirname(rel)), exist_ok=True)
            escriu_wav(os.path.join(a.sortida, rel), cas.senyal, cas.sr, cas.fmt)
            d = cas.descripcio()
            d["fitxer"] = rel
            jl.write(json.dumps(d, ensure_ascii=False) + "\n")
            n += 1
    print(f"{n} casos a {a.sortida} · conjunt {a.conjunt} · hash {h}")


if __name__ == "__main__":
    main()
