# -*- coding: utf-8 -*-
"""Informe: què faria l'anotador virtual en cada condició (sense detector).

Per condició amb objectiu, aplica el criteri literal (3 x RMS dels 20 ms previs,
3 samples seguits; i el 5 % del pic) i compara amb les referències analítiques:

  avanc_10   = t10 - t_anotat       (>0: l'anotador marca ABANS del 10 %)
  des_fisic  = t_anotat - t_fisic   (>0: l'anotador marca DESPRÉS de l'inici físic)

`avanc_10` és la PREDICCIÓ de `t_detector - t_anotador` si el detector és
perfecte respecte del seu 10 %: el biaix que s'hauria de veure amb persones.
Ús:  python3 -m banc_onsets.informe_anotador_virtual --reps 30 [--json out.json]
"""
from __future__ import annotations

import argparse
import json

import numpy as np

from . import anotador_virtual as av
from . import generador as g


def _stats(v):
    v = np.array([x for x in v if x is not None], dtype=float) * 1000.0
    if v.size == 0:
        return None
    return {"med": float(np.median(v)), "p95_abs": float(np.percentile(np.abs(v), 95)),
            "n": int(v.size)}


def informe(grups, reps):
    files = []
    for c in g.selecciona(grups):
        if not c["font"] or c["grup"] in ("N",):
            continue
        res = {m: {"avanc": [], "fisic": []} for m in ("fix", "lliscant", "pic")}
        for s in g.llavors("dev", reps):
            cas = g.renderitza(c, s)
            for m, (crit, base) in {"fix": ("rms", "fix"), "lliscant": ("rms", "lliscant"),
                                    "pic": ("pic", "fix")}.items():
                t = av.anota(cas.senyal, cas.sr, cas.refs["t10"], criteri=crit, base=base)
                if t is None:
                    res[m]["avanc"].append(None)
                    res[m]["fisic"].append(None)
                else:
                    res[m]["avanc"].append(cas.refs["t10"] - t)
                    res[m]["fisic"].append(t - cas.refs["t_fisic"])
        files.append({"id": c["id"], "informatiu": c["informatiu"],
                      "snr_db": c["soroll"].get("snr_db") if c["soroll"] else None,
                      "rise_ms": c["font"].get("rise_ms"),
                      **{m: {"avanc_10": _stats(r["avanc"]), "des_fisic": _stats(r["fisic"]),
                             "no_trobat_pc": 100.0 * sum(x is None for x in r["avanc"]) / len(r["avanc"])}
                         for m, r in res.items()}})
    return files


def imprimeix(files):
    print(f"{'condició':34s}{'rise':>6s}{'SNR':>5s} | {'fix: avanç10 med/p95':>22s} "
          f"{'lliscant med':>13s} {'pic5% med':>10s} | no trobat % (fix/llis/pic)")
    for f in files:
        def med(m):
            s = f[m]["avanc_10"]
            return f"{s['med']:+.2f}" if s else "  —"
        fx = f["fix"]["avanc_10"]
        cel = f"{fx['med']:+6.2f} / {fx['p95_abs']:5.2f}" if fx else "      —"
        snr = "" if f["snr_db"] is None else f"{f['snr_db']:g}"
        print(f"{f['id']:34s}{f['rise_ms']:6g}{snr:>5s} | {cel:>22s} {med('lliscant'):>13s} "
              f"{med('pic'):>10s} | {f['fix']['no_trobat_pc']:.0f}/"
              f"{f['lliscant']['no_trobat_pc']:.0f}/{f['pic']['no_trobat_pc']:.0f}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=g.REPS_DEFECTE)
    ap.add_argument("--grups", default="A,B,C,D")
    ap.add_argument("--json", default="")
    a = ap.parse_args(argv)
    files = informe([x for x in a.grups.split(",") if x], a.reps)
    imprimeix(files)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(files, fh, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
