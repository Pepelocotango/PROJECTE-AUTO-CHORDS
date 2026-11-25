#!/usr/bin/env python3
# concatena.py — Genera UN sol fitxer amb NOMÉS el codi/config indispensable del
# projecte, perquè un altre agent/LLM el pugui ENTENDRE i EXECUTAR.
#
# Ús: python3 concatena.py [--codi] [sortida.txt]
#   (defecte: CODI_concatenat.txt; amb --codi: CODI_codi.txt)
#
# --codi  perfil reduït centrat en els clips de temps (tempo/compàs/graella/
#         metrònom/marcadors/talls): inclou TOT `app/`, els tests del domini i
#         els docs de temps, i deixa fora CI, generadors, llançadors i els tests
#         generals (test_pipeline) i de xifrat/partitura.
#
# INCLOU (whitelist), EN ORDRE: primer el CONTEXT (`AGENTS.md`, `README.md`,
#   `ROADMAP.md`, `DEVELOPING.md`, les regles d'or, l'esquema d'UI i els docs
#   de comportament), després el CODI: `app/`, `eines/` (scripts de build +
#   host C++ + `deps_fixades.env`), `.github/workflows/` (CI), les dades de
#   build (`pyproject.toml`, `requirements*.txt`, `instal·la_local.sh`,
#   `Makefile`), els llançadors (Linux/Windows/dev), els scripts CLI i `tests/`.
#
# EXCLOU la resta (no indispensable): CHANGELOG/LLICENCIES, els docs no
#   essencials, el codi de tercers (`codi_font_chordino/`), binaris i plugins,
#   logs i arxius locals (`OLD/`, `opcions_detecta.json`, `portable/`,
#   `.venv/`, `.deps/`, `temp/`).
import os
import sys
from datetime import datetime

ARREL = os.path.dirname(os.path.abspath(__file__))

# --- Què SÍ que hi va (whitelist, relatiu a l'arrel) -----------------------
INCLOU = [
    # 1-3. Context del producte i normes de treball
    "AGENTS.md",            # abast, protocols i regles d'equip
    "README.md",            # visió general + com executar
    "ROADMAP.md",           # full de ruta (abast, fases, futur)
    "DEVELOPING.md",        # setup, entorn i desenvolupament
    "docs/README.md",       # índex de la documentació
    "docs/REGLES_DE_LA_APP.md",   # ⚠️ regles d'or (invariants) — IMPRESCINDIBLE
    "docs/ESQUEMA_UI.md",   # menús, botons, dreceres i diàlegs reals
    "docs/COMPONENTS_I_VERSIONS.md",  # inventari de components i versions
    # 3b. Context Tier A — contractes de comportament
    "docs/recerca/NOTACIO_XIFRAT.md",  # forma canònica del xifrat
    "docs/TIPUS_XIFRAT_ACORDS.md",  # els tipus + graus + <kind> MusicXML
    "docs/recerca/TAULA_COMPASSOS_X_X.md",  # compassos, pols i metrònom
    # 4+. El codi i la resta
    "app",                  # codi de l'aplicació (Python)
    "eines",                # scripts de build/empaquetat + host C++ (vamp_host.cpp)
    ".github/workflows",    # CI (build-appimage / windows / macos / release)
    "pyproject.toml",       # paquet + metadades
    "requirements.txt",     # dependències del venv
    "requirements-build.txt",  # pins del build (font única pels 3 workflows CI)
    "requirements-dev.txt", # eines de desenvolupament i tests
    "instal·la_local.sh",   # setup local (sense sudo)
    "Makefile",             # comandes del projecte (font de veritat del build)
    "AUTO_CHORDS.sh",       # llançador Linux
    "AUTO_CHORDS.bat",      # llançador Windows
    "AUTO_CHORDS_dev.sh",   # llançador de dev (recarrega automàtica)
    "dev_reload.py",        # recàrrega en viu usada pel llançador de dev
    "wav_a_wavs.py",        # CLI wav -> wavs
    "concatena.py",         # aquest mateix script
    # 5. Els tests (perquè qui revisi el codi pugui veure el comportament)
    "tests",
]

# --- Perfil reduït `--codi`: clips de temps (tempo/compàs/graella) ---------
# Tot `app/` hi és perquè la UI i el motor dels clips es necessiten entre si.
DOCS_TEMPS = [
    "docs/REGLES_DE_LA_APP.md",   # regles d'or (contracte)
    "docs/ESQUEMA_UI.md",         # menús, dreceres i diàlegs de tempo/compàs
    "docs/recerca/TAULA_COMPASSOS_X_X.md",
    "docs/recerca/GRAELLA_PPQ_TEMPS.md",
    "docs/recerca/COMPASSOS_COMPOSTOS_BPM_METRONOM.md",
    "docs/recerca/guia_tecnica_downbeat_onsets_beats.md",
    "docs/recerca/PLA_MAPA_TEMPS.md",
]
TESTS_TEMPS = [
    "tests/_temporals.py", "tests/_qt_neteja.py",
    "tests/test_edicio.py", "tests/test_despatx_edicio.py",
    "tests/test_tempo_map.py", "tests/test_tempo_trams.py",
    "tests/test_tempo_recalc.py", "tests/test_mapa_tempo.py",
    "tests/test_tempo_midi.py", "tests/test_tall_qm.py",
    "tests/test_dialeg_tall_qm.py", "tests/test_beats.py",
    "tests/test_ancoratges.py", "tests/test_avalua_tempo.py",
    "tests/test_audio_edit.py", "tests/test_timeline_contracte.py",
    "tests/test_pipeline_contracte.py", "tests/test_gui.py",
]
PROFIL_CODI = [
    "AGENTS.md", "DEVELOPING.md",
    *DOCS_TEMPS,
    "app",
    "eines/deps_fixades.env", "eines/vamp_host.cpp",
    "eines/avalua_tempo.py", "eines/explica_bpm.py",
    "pyproject.toml", "requirements.txt", "requirements-build.txt",
    "requirements-dev.txt", "Makefile",
    *TESTS_TEMPS,
    "concatena.py",
]

# --- Què NO que hi va (si apareix dins un directori inclòs) ----------------
EXCLOSOS_DIRS = {"__pycache__", ".venv", ".git", ".deps", "temp", "OLD"}
EXCLOSOS_NOMS = {"opcions_detecta.json", "auto_chords.log"}

# --- Extensions de text que concatenem -------------------------------------
EXTENSIONS = {
    ".py", ".sh", ".bat", ".cpp", ".h", ".c",  # codi
    ".toml", ".txt", ".cfg", ".ini", ".spec",  # build/config
    ".yml", ".yaml",                            # CI/workflows
    ".md",                                      # docs (els de la whitelist)
    ".desktop", ".json", ".env",
}
NOMS_SENSE_EXT = {"Makefile"}


def es_text(nom):
    return (os.path.splitext(nom)[1].lower() in EXTENSIONS
            or nom in NOMS_SENSE_EXT)


def recorre(inclou):
    """Retorna les rutes (relatives) dels fitxers a concatenar, en ordre."""
    for item in inclou:
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


def main(inclou, sortida, titol):
    fitxers = list(recorre(inclou))
    amb_data = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(sortida, "w", encoding="utf-8") as f:
        f.write("=" * 78 + "\n")
        f.write(f"PROJECTE AUTO CHORDS — {titol}\n")
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
                with open(path, encoding="utf-8") as fh:
                    contingut = fh.read()
            except (UnicodeDecodeError, OSError):
                continue
            total_linies += contingut.count("\n") + 1
            f.write("\n" + "=" * 78 + "\n")
            f.write(f"=== FITXER {i}/{len(fitxers)}: {r}\n")
            f.write("=" * 78 + "\n\n")
            f.write(contingut)
            if not contingut.endswith("\n"):
                f.write("\n")
    mida = os.path.getsize(sortida)
    print(f"✅ {sortida}")
    print(f"   {len(fitxers)} fitxers · {total_linies} línies · {mida/1024:.0f} KB")


if __name__ == "__main__":
    args = sys.argv[1:]
    codi = "--codi" in args
    args = [a for a in args if a != "--codi"]
    if codi:
        main(PROFIL_CODI, args[0] if args else os.path.join(ARREL, "CODI_codi.txt"),
             "CODI CONCATENAT · perfil clips de temps")
    else:
        main(INCLOU, args[0] if args else os.path.join(ARREL, "CODI_concatenat.txt"),
             "CODI CONCATENAT (només l'indispensable)")
