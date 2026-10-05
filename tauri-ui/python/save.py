#!/usr/bin/env python3
# save.py — Desa els canvis editats: escriu acords.csv + estructura_ABC.csv
#           i regenera els clips WAV (wavs_acords/ + wavs_estructura/).
#
# Ús:
#   python3 save.py '<json>'
#
# El JSON d'entrada té la forma:
#   {
#     "sortida": "/path/to/song_ACORDS",
#     "wav": "/path/to/song.wav",
#     "durada_s": 223.37,
#     "bpm": 101.0,
#     "bpb": 4,
#     "tempo_lliure": false,
#     "acords": [[0.0, "N"], [16.44, "E7"], ...],
#     "seccions": [[0.0, 21.36, "A", "N"], ...]
#   }
#
# Sortida (stdout): JSON {ok, n_wavs_acords, n_wavs_estructura} o {error}.
# Progrés i errors → stderr.
#
# Tot en català.
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "app"))

import pipeline  # noqa: E402


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def out(obj: dict) -> None:
    json.dump(obj, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


def main() -> int:
    if len(sys.argv) < 2:
        out({"error": "Falta el JSON de dades"})
        return 1

    try:
        p = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        out({"error": f"JSON invàlid: {e}"})
        return 1

    sortida = p.get("sortida", "")
    if not sortida:
        out({"error": "Falta la carpeta de sortida"})
        return 1
    os.makedirs(sortida, exist_ok=True)

    bpm = float(p.get("bpm", 138.0))
    bpb = int(p.get("bpb", 4))
    tempo_lliure = bool(p.get("tempo_lliure", False))
    durada_s = float(p.get("durada_s", 0.0))

    acords_in = p.get("acords", [])
    seccions_in = p.get("seccions", [])

    try:
        # 1. acords.csv  (format: t,nom — conservant 9 decimals)
        acords = [
            (float(t), str(nom), f"{float(t):.9f}") for t, nom in acords_in
        ]
        acords_csv = os.path.join(sortida, "acords.csv")
        pipeline.desa_acords_csv(acords_csv, acords)
        log(f"desat {acords_csv} ({len(acords)} acords)")

        # 2. estructura_ABC.csv
        seccions = [
            (float(ini), float(fi), str(lletra), str(fam))
            for ini, fi, lletra, fam in seccions_in
        ]
        abc_csv = os.path.join(sortida, "estructura_ABC.csv")
        if seccions:
            pipeline.desa_abc_csv(abc_csv, seccions, bpm, log,
                                  lliure=tempo_lliure)
            log(f"desat {abc_csv} ({len(seccions)} seccions)")

        # 3. Regenerar wavs_acords
        n_ac = 0
        if acords:
            if durada_s <= 0:
                durada_s = max((t for t, _, _ in acords), default=0.0)
            n_ac = pipeline.regenera_wavs_acords(
                acords_csv, sortida, bpm, bpb, 0.0, durada_s,
                44100, log, tempo_fix=not tempo_lliure,
            )

        # 4. Regenerar wavs_estructura
        n_est = 0
        if seccions and os.path.isfile(abc_csv):
            n_est = pipeline.regenera_wavs_estructura(
                abc_csv, sortida, 44100, log
            )

        out({
            "ok": True,
            "n_wavs_acords": n_ac,
            "n_wavs_estructura": n_est,
        })
        return 0

    except Exception as e:  # noqa: BLE001
        log(f"ERROR: {e}")
        out({"error": str(e)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
