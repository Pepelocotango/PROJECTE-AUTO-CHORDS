#!/usr/bin/env python3
# concatena.py — Genera UN sol fitxer amb NOMÉS el codi/config indispensable del
# projecte, perquè un altre agent/LLM el pugui ENTENDRE i EXECUTAR.
#
# Ús: python3 concatena.py [sortida.txt]   (defecte: CODI_concatenat.txt)
#
# INCLOU (whitelist), EN ORDRE: primer el CONTEXT (`README.md`, `ROADMAP.md`,
#   `DEVELOPING.md`), després el CODI: `app/`, `eines/` (scripts de build +
#   host C++), `.github/workflows/` (CI), les dades de build (`pyproject.toml`,
#   `requirements.txt`, `instal·la_local.sh`), els llançadors i els scripts CLI.
#
# EXCLOU la resta (no indispensable): CHANGELOG/LLICENCIES, `docs/` detallats,
#   `tests/`, el codi de tercers (`codi_font_chordino/`), binaris i plugins,
#   logs, i arxius locals (`OLD/`, `opcions_detecta.json`,
#   `LOGS GITHUB ACTIONS/`, `00last_artifacts_githubactions/`, `portable/`,
#   `.venv/`, `.deps/`, `temp/`).
import os
import sys
from datetime import datetime

ARREL = os.path.dirname(os.path.abspath(__file__))
SORTIDA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    ARREL, "CODI_concatenat.txt")

# --- Què SÍ que hi va (whitelist, relatiu a l'arrel) -----------------------
INCLOU = [
    # 1-3. Context del producte (perquè un LLM entengui QUÈ és i cap on va)
    "README.md",            # visió general + com executar
    "ROADMAP.md",           # full de ruta (abast, fases, futur)
    "DEVELOPING.md",        # setup, entorn i desenvolupament
    # 4+. El codi i la resta
    "app",                  # codi de l'aplicació (Python)
    "eines",                # scripts de build/empaquetat + host C++ (vamp_host.cpp)
    ".github/workflows",    # CI (build-appimage / windows / macos / release)
    "pyproject.toml",       # paquet + metadades
    "requirements.txt",     # dependències del venv
    "instal·la_local.sh",   # setup local (sense sudo)
    "AUTO_CHORDS.sh",       # llançador
    "AUTO_CHORDS.desktop",  # drecera d'escriptori
    "acords_a_live.py",     # script del pipeline (CSV -> locators/guia)
    "wav_a_wavs.py",        # CLI wav -> wavs
    "concatena.py",         # aquest mateix script
]

# --- Què NO que hi va (si apareix dins un directori inclòs) ----------------
EXCLOSOS_DIRS = {"__pycache__", ".venv", ".git", ".deps", "temp", "OLD", "docs"}
EXCLOSOS_NOMS = {"opcions_detecta.json", "auto_chords.log"}

# --- Extensions de text que concatenem -------------------------------------
EXTENSIONS = {
    ".py", ".sh", ".cpp", ".h", ".c",          # codi
    ".toml", ".txt", ".cfg", ".ini", ".spec",  # build/config
    ".yml", ".yaml",                            # CI/workflows
    ".md",                                      # docs (les 2 de la whitelist)
    ".desktop", ".json",
}


def es_text(nom):
    return os.path.splitext(nom)[1].lower() in EXTENSIONS


def recorre():
    """Retorna les rutes (relatives) dels fitxers a concatenar, en ordre."""
    for item in INCLOU:
        cami = os.path.join(ARREL, item)
        if os.path.isfile(cami):
            if es_text(item):
                yield item
            continue
        if not os.path.isdir(cami):
            continue
        for base, dirs, fitxers in os.walk(cami):
            dirs[:] = sorted(d for d in dirs if d not in EXCLOSOS_DIRS)
            for nom in sorted(fitxers):
                if nom in EXCLOSOS_NOMS or nom.startswith("."):
                    continue
                if not es_text(nom):
                    continue
                rel = os.path.relpath(os.path.join(base, nom), ARREL)
                yield os.path.normpath(rel)


def main():
    fitxers = list(recorre())
    amb_data = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(SORTIDA, "w", encoding="utf-8") as f:
        f.write("=" * 78 + "\n")
        f.write("PROJECTE AUTO CHORDS — CODI CONCATENAT (només l'indispensable)\n")
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
