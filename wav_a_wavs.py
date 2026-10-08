#!/usr/bin/env python3
# wav_a_wavs.py — Script únic: wav -> wavs_acords (+ wavs_estructura).
# Reutilitza app/pipeline.py (mateixa lògica que la GUI), sense duplicar-la.
# Ús: python3 wav_a_wavs.py tema.wav 138 4 [offset] [--sense-estructura] [--tempo-lliure] [--sortida DIR]
# Tot en català.
import argparse
import os
import sys

APP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app")
sys.path.insert(0, APP_DIR)
import pipeline  # noqa: E402


def log(msg):
    print(msg, flush=True)


def main():
    ap = argparse.ArgumentParser(
        description="wav -> acords + wavs llestos per al Live/Reaper "
                    "(mateix motor que l'app).")
    ap.add_argument("wav", help="fitxer .wav d'entrada")
    ap.add_argument("bpm", type=float, nargs="?", default=138.0,
                    help="tempo en BPM (defecte 138; s'ignora amb --tempo-lliure)")
    ap.add_argument("bpb", type=int, nargs="?", default=4,
                    help="temps per compàs (defecte 4; s'ignora amb --tempo-lliure)")
    ap.add_argument("offset", type=float, nargs="?", default=0.0,
                    help="segons on cau el compàs 1 (defecte 0)")
    ap.add_argument("--sortida", default="",
                    help="carpeta de sortida (defecte: <nom_wav>_ACORDS al costat del wav)")
    ap.add_argument("--sense-estructura", action="store_true",
                    help="no extreu estructura (qm-segmenter -> ABC)")
    ap.add_argument("--tempo-lliure", action="store_true",
                    help="la wav NO té tempo fix: segments en segons, sense graella BPM")
    ap.add_argument("--sr", type=int, default=44100,
                    help="mostreig dels wavs guia (defecte 44100)")
    a = ap.parse_args()

    if not os.path.isfile(a.wav):
        sys.exit(f"No trobo la wav: {a.wav}")
    try:
        info = pipeline.wav_info(a.wav)
        log(f"Entrada: {info['durada']:.1f} s · {info['canals']} canals · "
            f"{info['mostreig']} Hz")
    except Exception as e:  # noqa: BLE001
        sys.exit(f"No és una wav vàlida: {e}")

    base = os.path.splitext(os.path.basename(a.wav))[0]
    sortida = a.sortida or os.path.join(os.path.dirname(a.wav), base + "_ACORDS")
    os.makedirs(sortida, exist_ok=True)
    log(f"Sortida: {sortida}")

    amb_est = not a.sense_estructura
    tempo_fix = not a.tempo_lliure

    csv_ac = os.path.join(sortida, "acords.csv")
    log("1/5 extreu acords (Chordino)...")
    pipeline.extract_chords(os.path.abspath(a.wav), csv_ac, log)

    csv_seg = None
    if amb_est:
        csv_seg = os.path.join(sortida, "segments.csv")
        log("2/5 extreu estructura (qm-segmenter)...")
        pipeline.extract_segments(os.path.abspath(a.wav), csv_seg, log)

    if tempo_fix:
        log("3/5 locators + guia...")
        loc, guia = pipeline.run_acords_py(csv_ac, a.bpm, a.bpb, a.offset,
                                           sortida, log)
        log(f"  -> {loc} + {guia}")
        log("4/5 wavs d'acords...")
        pipeline.fer_wavs_acords(loc, a.bpm,
                                 os.path.join(sortida, "wavs_acords"),
                                 a.sr, log, a.bpb)
    else:
        log("3-4/5 segments en segons + wavs...")
        pipeline.fer_wavs_acords_lliures(csv_ac, info["durada"],
                                         os.path.join(sortida, "wavs_acords"),
                                         a.sr, log)

    if csv_seg:
        log("5/5 ABC + wavs d'estructura...")
        abc = os.path.join(sortida, "estructura_ABC.csv")
        pipeline.fer_abc(csv_seg, abc, a.bpm, log, lliure=not tempo_fix, bpb=a.bpb,
                             offset=a.offset)
        pipeline.fer_wavs_estructura(abc,
                                     os.path.join(sortida, "wavs_estructura"),
                                     a.sr, log)

    log(f"FET ✅ — {sortida}")
    log("Arrossega wavs_acords/ (i wavs_estructura/) al DAW amb Snap OFF.")


if __name__ == "__main__":
    main()
