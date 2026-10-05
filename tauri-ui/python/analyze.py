#!/usr/bin/env python3
# analyze.py — Executa el pipeline d'Auto Chords i retorna el resultat en JSON.
#
# Ús:
#   python3 analyze.py <wav> [bpm] [bpb] [--no-estructura] [--tempo-lliure]
#
# Sortida:
#   - stdout: JSON net (per al frontend Tauri) — cap missatge extra
#   - stderr: progrés i errors (per als logs)
#
# El JSON retornat té aquesta forma:
#   {
#     "wav": "/path/to/song.wav",
#     "sortida": "/path/to/song_ACORDS",
#     "durada_s": 223.37,
#     "bpm": 138.0,
#     "bpb": 4,
#     "acords": [[0.0, "N"], [16.44, "E7"], ...],
#     "seccions": [[0.0, 21.36, "A", "N"], ...]
#   }
#
# Tot en català.
import argparse
import csv
import json
import os
import subprocess
import sys
import wave

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# tauri-ui/python/ → PROJECTE AUTO CHORDS/
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
WAV_A_WAVS = os.path.join(PROJECT_ROOT, "wav_a_wavs.py")


def log(msg: str) -> None:
    """Escriu un missatge de progrés a stderr (mai a stdout)."""
    print(msg, file=sys.stderr, flush=True)


def wav_duration(path: str) -> float:
    with wave.open(path, "rb") as w:
        sr = w.getframerate()
        if sr <= 0:
            raise ValueError(f"WAV amb sample rate invàlid: {sr}")
        return w.getnframes() / sr


def read_acords(path: str):
    """Llegeix acords.csv (format: time,"chord") → [[t, nom], ...]."""
    items = []
    with open(path, encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) < 2:
                continue
            try:
                t = float(row[0])
            except ValueError:
                continue
            name = row[1].strip()
            items.append([round(t, 3), name])
    return items


def read_seccions(path: str):
    """Llegeix estructura_ABC.csv → [[ini, fi, lletra, familia], ...]."""
    if not os.path.isfile(path):
        return []
    items = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                items.append([
                    round(float(r["inici_s"]), 3),
                    round(float(r["fi_s"]), 3),
                    r["lletra"],
                    r.get("família", r.get("familia", "")),
                ])
            except (ValueError, KeyError):
                continue
    return items


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Executa el pipeline d'Auto Chords i retorna JSON a stdout."
    )
    ap.add_argument("wav", help="fitxer .wav d'entrada")
    ap.add_argument("bpm", type=float, nargs="?", default=138.0)
    ap.add_argument("bpb", type=int, nargs="?", default=4)
    ap.add_argument("--no-estructura", action="store_true",
                    help="no extreure estructura amb Segmentino")
    ap.add_argument("--tempo-lliure", action="store_true",
                    help="no assumir BPM fix (segons reals)")
    a = ap.parse_args()

    wav = os.path.abspath(a.wav)
    if not os.path.isfile(wav):
        json.dump({"error": f"No trobo la WAV: {wav}"}, sys.stdout)
        return 1

    if not os.path.isfile(WAV_A_WAVS):
        json.dump(
            {"error": f"No trobo el pipeline: {WAV_A_WAVS}"},
            sys.stdout,
        )
        return 1

    # 1. Executar el pipeline (el seu stdout/stderr va al nostre stderr)
    cmd = [sys.executable, WAV_A_WAVS, wav, str(a.bpm), str(a.bpb)]
    if a.no_estructura:
        cmd.append("--sense-estructura")
    if a.tempo_lliure:
        cmd.append("--tempo-lliure")
    log("Executant: " + " ".join(cmd))
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        json.dump({"error": "El pipeline ha superat el temps límit (600 s)"},
                  sys.stdout)
        return 1
    for line in (p.stdout + p.stderr).splitlines():
        if line.strip():
            log("  " + line)
    if p.returncode != 0:
        json.dump(
            {"error": f"El pipeline ha fallat (codi {p.returncode}). "
                      f"Comprova que sonic-annotator i els plugins Vamp hi són."},
            sys.stdout,
        )
        return 1

    # 2. Llegir les sortides
    base = os.path.splitext(os.path.basename(wav))[0]
    sortida = os.path.join(os.path.dirname(wav), base + "_ACORDS")
    acords_csv = os.path.join(sortida, "acords.csv")
    abc_csv = os.path.join(sortida, "estructura_ABC.csv")

    try:
        durada = wav_duration(wav)
    except Exception as e:  # noqa: BLE001
        json.dump({"error": f"WAV invàlida: {e}"}, sys.stdout)
        return 1

    result = {
        "wav": wav,
        "sortida": sortida,
        "durada_s": round(durada, 3),
        "bpm": a.bpm,
        "bpb": a.bpb,
        "tempo_lliure": bool(a.tempo_lliure),
        "acords": read_acords(acords_csv) if os.path.isfile(acords_csv) else [],
        "seccions": read_seccions(abc_csv),
    }
    json.dump(result, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
