#!/usr/bin/env python3
# concatena.py — Genera un únic fitxer amb tot el codi font del projecte.
# Ús: python3 concatena.py [sortida.txt]
# Exclou: entorns virtuals, .git, .deps, binaris, plugins i codi C++ de tercers.
import os
import sys
from datetime import datetime

ARREL = os.path.dirname(os.path.abspath(__file__))
SORTIDA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    ARREL, "CODI_concatenat.txt")

# Fitxers/dirs exclosos (relatius a l'arrel)
EXCLOSOS = {
    ".venv", ".git", ".deps", "temp", "__pycache__", "docs",
    "nnls-chroma-linux64-local", "qm-vamp-plugins-linux64-local",
}
# Extensions de text que sí que concatenem
EXTENSIONS = {".py", ".sh", ".toml", ".txt", ".md", ".desktop", ".json",
              ".cfg", ".ini", ".service"}
# Binaris o generats que no volem
EXCLOSOS_NOMS = {"CODI_concatenat.txt", "auto_chords.log", "sonic-annotator"}


def es_text(ruta):
    ext = os.path.splitext(ruta)[1].lower()
    return ext in EXTENSIONS


def recorre():
    for base, dirs, fitxers in os.walk(ARREL):
        dirs[:] = sorted(d for d in dirs if d not in EXCLOSOS)
        rel = os.path.relpath(base, ARREL)
        for nom in sorted(fitxers):
            if nom in EXCLOSOS_NOMS or nom.startswith("."):
                continue
            ruta = os.path.join(base, nom)
            if not es_text(ruta):
                continue
            yield os.path.normpath(os.path.join(rel, nom)) if rel != "." else nom


def main():
    fitxers = list(recorre())
    amb_data = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(SORTIDA, "w", encoding="utf-8") as f:
        f.write("=" * 78 + "\n")
        f.write("PROJECTE AUTO CHORDS — CODI CONCATENAT\n")
        f.write(f"Generat: {amb_data}\n")
        f.write(f"Fitxers: {len(fitxers)}\n")
        f.write("=" * 78 + "\n\n")
        f.write("ÍNDEX\n" + "-" * 78 + "\n")
        for i, r in enumerate(fitxers, 1):
            f.write(f"  {i:3d}. {r}\n")
        f.write("\n")
        total_linies = 0
        for i, r in enumerate(fitxers, 1):
            path = os.path.join(ARREL, r)
            try:
                contingut = open(path, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                continue
            total_linies += contingut.count("\n") + 1
            f.write("\n" + "=" * 78 + "\n")
            f.write(f"=== FITXER {i}/{len(fitxers)}: {r}\n")
            f.write("=" * 78 + "\n\n")
            f.write(contingut)
            if not contingut.endswith("\n"):
                f.write("\n")
    mida = os.path.getsize(SORTIDA)
    print(f"✅ {SORTIDA}")
    print(f"   {len(fitxers)} fitxers · {total_linies} línies · {mida/1024:.0f} KB")


if __name__ == "__main__":
    main()
