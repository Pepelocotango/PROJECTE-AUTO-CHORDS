# -*- coding: utf-8 -*-
"""Autoproves del GENERADOR (no del detector).

Comprova que l'instrument de mesura fa el que diu abans de fiar-se'n:
reproduïbilitat, referències coherents, fase fraccionària, SNR real, format de
fitxers, blocatge del conjunt de validació i anotador virtual. No importa cap
detector.   Ús:  python3 -m banc_onsets.autotest_generador
"""
from __future__ import annotations

import os
import sys
import tempfile

import numpy as np
from scipy.io import wavfile

from . import anotador_virtual as av
from . import generador as g

CONDS = {c["id"]: c for c in g.condicions_v1()}


def _cond(id_):
    return CONDS[id_]


def test_no_importa_detector():
    g.renderitza(_cond("A1_bombo_r2"), 1)
    prohibits = [m for m in sys.modules if m == "app" or m.startswith("app.")
                 or m.endswith(".tempo") or m == "tempo"]
    assert not prohibits, f"s'ha importat codi del detector: {prohibits}"


def test_condicions_ben_formades():
    ids = [c["id"] for c in g.condicions_v1()]
    assert len(ids) == len(set(ids)), "ids de condició duplicats"
    grups = {c["grup"] for c in g.condicions_v1()}
    assert grups == set("ABCDEFGN"), grups
    for c in g.condicions_v1():
        if c["grup"] == "N":
            assert c["tipus_esperat"] == "cap" and c["criteri"] == {"onsets_max": 0}
    assert sum(c["opcional"] for c in g.condicions_v1()) == 5


def test_reproduible_per_llavor():
    c = _cond("A3_acord_r25_cosinus")
    a, b = g.renderitza(c, 7), g.renderitza(c, 7)
    assert np.array_equal(a.senyal, b.senyal) and a.refs == b.refs
    assert not np.array_equal(a.senyal, g.renderitza(c, 8).senyal)


def test_referencies_coherents():
    for c in g.selecciona(opcionals=True):
        if not c["font"]:
            continue
        for s in (1, 2, 3):
            r = g.renderitza(c, s, amb_soroll=False).refs
            e = 1.0 / (g.SOBREMOSTREIG * c["sr"])
            assert r["t_fisic"] - e <= r["t10"] <= r["t50"] <= r["t_pic"] + 1e-12, \
                (c["id"], s, r)
            assert r["t_pic"] <= r["t_fisic"] + g.FINESTRA_REF_S + 2 * e, (c["id"], r)


def test_fase_fraccionaria():
    c = _cond("A1_bombo_r2")
    t0s = np.array([g.renderitza(c, s, amb_soroll=False).t0 for s in range(1, 61)])
    assert t0s.min() >= g.T0_BASE_S and t0s.max() < g.T0_BASE_S + g.T0_JITTER_S
    frac = (t0s * c["sr"]) % 1.0
    assert frac.min() < 0.15 and frac.max() > 0.85, "t0 cau massa sovint a mostres senceres"
    bloc = ((t0s - g.T0_BASE_S) / g.T0_JITTER_S)
    assert bloc.min() < 0.2 and bloc.max() > 0.8, "fase dins del bloc de 10 ms poc variada"


def test_snr_real():
    for c in g.selecciona(["B", "N"]):
        if c["soroll"] is None:                       # silenci digital
            assert not np.any(g.renderitza(c, 1).senyal), c["id"]
            continue
        for s in (1, 2):
            amb = g.renderitza(c, s)
            net = g.renderitza(c, s, amb_soroll=False)
            soroll = amb.senyal - net.senyal
            rms = float(np.sqrt(np.mean(soroll ** 2)))
            f = c["soroll"]
            esperat = (net.refs["pic"] * 10 ** (-f["snr_db"] / 20)
                       if "snr_db" in f else f["sigma"])
            err_db = abs(20 * np.log10(rms / esperat))
            assert err_db < 0.3, (c["id"], s, err_db)


def test_decimat_coherent_amb_referencia():
    dif = []
    for c in g.selecciona(["A"]):
        if c["informatiu"] or not c["font"]:
            continue
        for s in range(1, 6):
            cas = g.renderitza(c, s, amb_soroll=False)
            a = np.abs(cas.senyal)
            ini = int(round((cas.refs["t_fisic"] - 0.02) * cas.sr))
            llindar = 0.10 * cas.refs["pic"]
            i = ini + int(np.argmax(a[ini:] > llindar))
            d = i / cas.sr - cas.refs["t10"]
            assert -1e-9 <= d <= 0.0002, (c["id"], s, d)
            dif.append(d * cas.sr)
    assert np.median(dif) <= 1.5, f"mediana {np.median(dif):.2f} mostres"


def test_escriptura_wav_roundtrip():
    cas = g.renderitza(_cond("F3_estereo_correlat"), 1)
    with tempfile.TemporaryDirectory() as d:
        for fmt in ("pcm16", "pcm24", "float32"):
            p = os.path.join(d, f"{fmt}.wav")
            g.escriu_wav(p, cas.senyal, cas.sr, fmt)
            sr, x = wavfile.read(p)
            assert sr == cas.sr and x.shape == cas.senyal.shape, (fmt, x.shape)
            if fmt == "pcm16":
                y = x / 32768.0
            elif fmt == "pcm24":
                y = x.astype(np.float64) / 2 ** 31
            else:
                y = x.astype(np.float64)
            assert np.max(np.abs(y - cas.senyal)) < 2e-4, (fmt,)


def test_blocatge_validacio():
    h = g.hash_parametres()
    with tempfile.TemporaryDirectory() as d:
        for args in (["--conjunt", "val", "--sortida", d, "--grups", "N", "--reps", "1"],
                     ["--conjunt", "val", "--sortida", d, "--grups", "N", "--reps", "1",
                      "--permet-validacio", "--hash-congelat", "0" * 64]):
            try:
                g.main(args)
            except SystemExit:
                continue
            raise AssertionError("la validació no s'ha bloquejat")
        g.main(["--conjunt", "val", "--sortida", d, "--grups", "N", "--reps", "1",
                "--permet-validacio", "--hash-congelat", h])
        assert os.path.exists(os.path.join(d, "casos.jsonl"))
    assert g.llavors("val", 3)[0] >= g.LLAVORS_VAL_INICI
    assert max(g.llavors("dev", 30)) <= g.LLAVORS_DEV[1]


def test_expectatives_E():
    esp = {c["a_off_s"]: g._esperat(c) for c in g.selecciona(["E"], opcionals=True)}
    assert esp[-0.080]["onsets_ab"]["tipus"] == "atac"
    assert esp[0.0]["detecta_onsets"]["tipus"] == "frontera"
    assert esp[0.015]["onsets_ab"]["tipus"] == "atac_fora_rang"
    assert esp[0.015]["detecta_onsets"]["tipus"] == "cap_atac_objectiu"
    assert esp[0.029]["onsets_ab"]["tipus"] == "atac_fora_rang"
    assert esp[0.031]["onsets_ab"]["tipus"] == "cap_atac_objectiu"
    assert esp[0.040]["onsets_ab"]["tipus"] == "cap_atac_objectiu"


def test_anotador_virtual():
    ra = _cond("A1_bombo_r2")
    for s in range(1, 21):
        cas = g.renderitza(ra, s)
        t = av.anota(cas.senyal, cas.sr, cas.refs["t10"])
        assert t is not None, s
        assert cas.refs["t_fisic"] - 0.001 <= t <= cas.refs["t10"] + 1e-9, (s, t, cas.refs)
    lent = _cond("A3_acord_r50_lineal")
    for s in range(1, 21):
        cas = g.renderitza(lent, s)
        t = av.anota(cas.senyal, cas.sr, cas.refs["t10"], base="fix")
        assert t is not None and cas.refs["t_fisic"] - 0.001 <= t <= cas.refs["t10"] + 0.020, (s, t, cas.refs)
    for id_ in ("N1_soroll_blanc_54dB", "N7_silenci_digital"):
        trobats = 0
        for s in range(1, 21):
            cas = g.renderitza(_cond(id_), s)
            trobats += av.anota(cas.senyal, cas.sr, 0.4) is not None
        assert trobats <= 1, (id_, trobats)


def main():
    proves = [(n, f) for n, f in sorted(globals().items())
              if n.startswith("test_") and callable(f)]
    fallos = 0
    for n, f in proves:
        try:
            f()
            print(f"  OK    {n}")
        except Exception as e:  # noqa: BLE001
            fallos += 1
            print(f"  FALLA {n}: {type(e).__name__}: {e}")
    print(f"\n{len(proves) - fallos}/{len(proves)} proves correctes")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
