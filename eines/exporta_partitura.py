#!/usr/bin/env python3
"""CLI: genera una partitura (xifrat) a partir d'una carpeta `*_ACORDS/`.

Ús:
    python3 eines/exporta_partitura.py "<carpeta_fins_a>/Tema_ACORDS" [opcions]

Opcions:
    --tema NOM          Nom base dels fitxers (per defecte: nom de la carpeta)
    --key auto|TONAL    Armadura. `auto` usa el qm-keydetector (cal --wav).
                        Ex.: G · F · "E minor" · C (per defecte: C)
    --wav RUTA          WAV original (només per a --key auto)
    --musescore RUTA    Binari/AppImage de MuseScore (si no, es detecta sol)
    --no-pdf / --no-mscz  No renderitzar aquest format
    --timeout SEGONS    Temps màxim per render (per defecte 300)
    --compassos-per-linia N  Força salt de sistema cada N compassos (línies regulars)
    --beat-type N       Denominador del compàs al MusicXML (per defecte 4; ex. 8 per 6/8)

Requereix que la carpeta tingui `acords_locators.txt` (mode BPM · compàs).
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import partitura  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description="Exporta una partitura xifrada.")
    ap.add_argument("carpeta", help="carpeta *_ACORDS amb els resultats")
    ap.add_argument("--tema", default=None)
    ap.add_argument("--key", default="C", help="auto | tonic (G, F, 'E minor'…)")
    ap.add_argument("--wav", default=None)
    ap.add_argument("--musescore", default=None)
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--no-mscz", action="store_true")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--compassos-per-linia", type=int, default=None,
                    help="salta de sistema cada N compassos (línies regulars)")
    ap.add_argument("--beat-type", type=int, default=4,
                    help="denominador del compàs (4, 8...)")
    a = ap.parse_args(argv)

    key_fifths = 0
    if str(a.key).strip().lower() == "auto":
        if not a.wav:
            print("--key auto necessita --wav", file=sys.stderr)
            return 2
        key_fifths = partitura.detecta_fifths(a.wav, print)
    else:
        key_fifths = partitura.fifths_de_to(a.key)

    res = partitura.exporta_partitura(
        a.carpeta, log=print, titol=a.tema, key_fifths=key_fifths, wav=a.wav,
        genera_pdf=not a.no_pdf, genera_mscz=not a.no_mscz,
        musescore=a.musescore, timeout=a.timeout,
        new_system_each=a.compassos_per_linia, beat_type=a.beat_type)

    if res.get("error"):
        print(f"AVORTAT: {res['error']}", file=sys.stderr)
        return 1
    print("\nFet:")
    for k in ("musicxml", "pdf", "mscz"):
        if res.get(k):
            print(f"  {k:8s} {res[k]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
