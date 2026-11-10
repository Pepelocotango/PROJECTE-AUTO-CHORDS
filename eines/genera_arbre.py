#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera l'arbre de projecte dins `ARBRE_DIRECTORIS.md`.

- **Bloc generat:** entre els marcadors `<!-- GENERAT: arbre ... -->` i
  `<!-- /GENERAT: arbre -->` de `ARBRE_DIRECTORIS.md`. No editar-lo a mà.
- **Versionat:** entrades preses del disc; 🟢 si `git ls-files` les conté,
  🟡 si no (locals o ignorades).
- **Carpetes grans o locals:** no es llisten recursivament (`DIRS_RESUM`):
  una entrada amb recurs directe i el recompte de fitxers.
- **Descripcions:** diccionari `DESCRIPCIONS` per a les entrades no-Python;
  per als `app/*.py` i `tests/*.py`, el docstring (com `genera_moduls.py`).
  Les entrades del diccionari que no existeixen al disc s'ignoren.
- **Fitxers efímers** de l'arrel (logs, recents, opcions locals…) no es
  llisten: la sortida no depén de la sessió de treball.

Ús:
    python3 eines/genera_arbre.py            # escriu el bloc
    python3 eines/genera_arbre.py --check    # diu si està al dia
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ARREL, "ARBRE_DIRECTORIS.md")
INICI = "<!-- GENERAT: arbre — no editar a mà -->"
FI = "<!-- /GENERAT: arbre -->"

EXCLOSOS_DIRS = {
    ".git",
    "__pycache__",
    ".baixades",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".cov-env",
    "htmlcov",
    "squashfs-root",
}

DIRS_RESUM = {
    "00PER FER",
    ".opencode",
    "CORPUS",
    "portable",
    "temp",
    ".venv",
    ".deps",
}

EXCLOSOS_ARXIU = {
    "opencode.json",
    "opencode.jsonc",
    "opcions_detecta.json",
    "recents.json",
    "sessio.json",
    ".coverage",
}

EXCLOSOS_ARXIU_PREFIX = (
    "CODI_concatenat", "crash_nadiu.log", "auto_chords.log",
    "auto-chords-audio", "auto-chords-audici",
)

DESCRIPCIONS = {
    "00PER FER": "Plans, auditories i instruccions pendents",
    "00PER FER/DECISIONS_RUBATO.md": "Subplà de rubato i doble graella",
    "00PER FER/PLA_FLUX_MARCADORS_BEATS.md": "Pla del flux de marcadors i beats",
    "00PER FER/PLA_SIMPLIFICACIO_TEMPO.md": "Pla per fases de simplificació del tempo",
    ".github": "GitHub Actions",
    ".github/workflows": "Workflows de GitHub Actions",
    ".github/workflows/build-all.yml": "Compila els 3 SO i comprova l'inventari",
    ".github/workflows/build-appimage.yml": "Linux: AppImage",
    ".github/workflows/build-macos.yml": "macOS 10.13+: .app i .dmg",
    ".github/workflows/build-windows.yml": "Windows x64: ZIP portable",
    ".github/workflows/qualitat.yml": "Fuzzer i proves sintètiques (no bloquejant)",
    ".github/workflows/release.yml": "Release idempotent amb els últims artefactes verds",
    ".opencode": "Configuració local d'OpenCode (no versionada)",
    ".opencode/agents": "Agents d'OpenCode",
    ".opencode/command": "Comandes locals d'OpenCode",
    ".opencode/skills": "Skills locals d'OpenCode",
    "app": "Codi de l'aplicació (PyQt5)",
    "codi_font_chordino": "Codi font del plugin Chordino (NNLS-Chroma)",
    "codi_font_chordino/regression": "Tests de regressió del plugin",
    "CORPUS": "Corpus local d'avaluació (no versionat)",
    "docs": "Contracte i documentació viva",
    "docs/README.md": "Índex de la documentació",
    "docs/REGLES_DE_LA_APP.md": "Regles d'or (1–12) i §13 (temps, compàs i graella)",
    "docs/ESQUEMA_UI.md": "Font de l'esquema visual de la UI",
    "docs/ESQUEMA_UI.html": "Generat des del `.md` (no editar)",
    "docs/ESQUEMA_UI.svg": "Generat des del `.md` (no editar)",
    "docs/EDICIO_OPERACIONS.md": "Taula única d'operacions d'edició",
    "docs/TIPUS_XIFRAT_ACORDS.md": "Catàleg de tipus, graus i `<kind>` MusicXML",
    "docs/FUNCIONALITATS_AUTO_CHORDS.ods": "Mapa complet de funcionalitats (generat; ODF)",
    "docs/COMPONENTS_I_VERSIONS.md": "Inventari generat (`eines/genera_inventari.py`)",
    "docs/recerca": "Documents de recerca (no descriuen l'estat viu)",
    "eines": "Build, empaquetat i cadena de subministrament",
    "eines/AutoChords-win.spec": "PyInstaller (Windows)",
    "eines/launcher_pyinstaller.py": "Punt d'entrada del paquet congelat",
    "eines/crea_icona.py": "Genera `.ico`/`.icns`",
    "eines/crea_portable.sh": "Crea l'entorn portable",
    "eines/empaqueta_portable.sh": "Empaqueta el portable",
    "eines/crea_appimage.sh": "Construeix l'AppImage",
    "eines/compila_vamp_host.sh": "Compila `vamp_host_local`",
    "eines/compila_vamp_plugins.sh": "Compila els plugins QM (sense AVX)",
    "eines/libreries_natives.sh": "Copia biblioteques natives",
    "eines/vamp_host.cpp": "Host Vamp propi (C++)",
    "eines/baixa_verificat.py": "Baixades verificades per SHA256 (caché `.baixades/`)",
    "eines/baixa_icones.sh": "Baixa les icones de Lucide",
    "eines/deps_fixades.env": "Pins de la cadena de subministrament",
    "eines/genera_inventari.py": "Genera `docs/COMPONENTS_I_VERSIONS.md`",
    "eines/genera_esquema_ui.py": "Genera `docs/ESQUEMA_UI.html` i `.svg`",
    "eines/genera_funcionalitats.py": "Genera `docs/FUNCIONALITATS_AUTO_CHORDS.ods`",
    "eines/funcionalitats_dades.json": "Font de dades del mapa de funcionalitats",
    "eines/genera_moduls.py": "Genera la taula de mòduls de `DEVELOPING.md`",
    "eines/genera_arbre.py": "Genera l'arbre d'aquest fitxer",
    "eines/notes_release.py": "Notes de release des del CHANGELOG",
    "eines/avalua_tempo.py": "Avaluador sintètic del mapa de tempo",
    "eines/ordre_aleatori.py": "Suite en ordre aleatori",
    "icona": "Icones de l'aplicació",
    "icones": "Icones SVG de la UI (Lucide, ISC)",
    "icones/LICENSE": "Llicència ISC de Lucide",
    "nnls-chroma-linux64-local": "Plugin Chordino compilat (local)",
    "qm-vamp-plugins-linux64-local": "Plugins Queen Mary compilats (local)",
    "tests": "Suite unittest offscreen",
    "temp": "Temporals de l'app (no versionat)",
    "temp/visor_player.log": "Log del reproductor",
    "portable": "Entorn portable local (regenerable)",
    ".venv": "Entorn virtual de Python (no versionat)",
    ".deps": "Dependències natives aïllades (no versionat)",
    "ARBRE_DIRECTORIS.md": "Mapa de carpetes i fitxers (generat, no editar a mà)",
    "AGENTS.md": "Guia del projecte i contracte d'abast",
    "README.md": "Producte: visió, instal·lació i flux",
    "DEVELOPING.md": "Entorn, mapa del codi, build i CI",
    "ROADMAP.md": "Full de ruta i estat actual (§2)",
    "ROADMAP_HISTORIA.md": "Historial del full de ruta (fases A–E i notes)",
    "CHANGELOG.md": "Historial de canvis",
    "SECURITY.md": "Canal de report de vulnerabilitats",
    "LLICENCIES_TERCERS.md": "Llicències de tercers",
    "LICENSE": "GPL-3.0-or-later",
    "pyproject.toml": "Metadades i pins del paquet",
    "requirements.txt": "Dependències de Python (pins)",
    "requirements-build.txt": "Pins addicionals del build",
    "requirements-dev.txt": "Eines de qualitat: pyflakes i coverage",
    "Makefile": "Comandes del projecte (test, lint, docs…)",
    "instal·la_local.sh": "Instal·lació local sense sudo",
    "AUTO_CHORDS.sh": "Llançador principal",
    "AUTO_CHORDS_dev.sh": "Llançador de desenvolupament",
    "dev_reload.py": "Recàrrega automàtica en dev",
    "concatena.py": "Genera un sol fitxer amb el codi indispensable",
    "wav_a_wavs.py": "CLI: WAV → WAVs d'acord/secció",
    "vamp_host_local": "Host Vamp compilat (binari)",
    ".gitignore": "Què no es versiona",
}

RESERVA_APP = {
    "main.py": "finestra principal, menús, barres, flux d'usuari i projectes",
    "pipeline.py": "façana del backend (re-exporta els símbols públics)",
    "visor.py": "visor DAW: ona, llistes, edició, reproducció i loop",
    "theme.py": "tema centralitzat (colors i estils Qt)",
}


def _primera_linia(text: str) -> str:
    for linia in (text or "").splitlines():
        linia = linia.strip()
        if linia:
            return linia
    return ""


def _docstring(cami: str, reserva: dict) -> str:
    nom = os.path.basename(cami)
    try:
        with open(cami, encoding="utf-8") as f:
            arbre = ast.parse(f.read(), filename=cami)
        text = ast.get_docstring(arbre) or ""
    except (OSError, SyntaxError):
        text = ""
    return _primera_linia(text) or reserva.get(nom, "—")


def _desc(ruta_rel: str, es_dir: bool) -> str:
    ruta_rel = ruta_rel.replace(os.sep, "/")
    if ruta_rel in DESCRIPCIONS:
        return DESCRIPCIONS[ruta_rel]
    if not es_dir:
        if (ruta_rel.startswith("app/") or ruta_rel.startswith("tests/")) \
                and ruta_rel.endswith(".py"):
            reserva = RESERVA_APP if ruta_rel.startswith("app/") else {}
            return _docstring(os.path.join(ARREL, *ruta_rel.split("/")), reserva)
    return ""


def _efimer(nom: str) -> bool:
    return nom in EXCLOSOS_ARXIU or nom.startswith(EXCLOSOS_ARXIU_PREFIX)


def _llista_tracked() -> set:
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"], cwd=ARREL,
            capture_output=True, check=True).stdout
        noms = {os.fsdecode(p) for p in out.split(b"\0") if p}
    except (OSError, subprocess.SubprocessError):
        noms = set()
    return noms


def _compta_fitxers(ruta: str) -> int:
    n = 0
    for _arrel, dirs, fitxers in os.walk(ruta):
        dirs[:] = [d for d in dirs if d not in EXCLOSOS_DIRS and
                   d != "node_modules"]
        n += len(fitxers)
    return n


def _flag(ruta: str, es_dir: bool, tracked: set) -> str:
    rel = os.path.relpath(ruta, ARREL).replace(os.sep, "/")
    if es_dir:
        dins = any(p.startswith(rel + "/") for p in tracked)
        return "🟢" if dins else "🟡"
    return "🟢" if rel in tracked else "🟡"


def _miler(n: int) -> str:
    xifres = f"{n:,}".replace(",", ".")
    return f"{xifres} {'fitxer' if n == 1 else 'fitxers'}"


def _linia(linies: list, prefix: str, ram: str, nom: str, flag: str,
           amplada: int, desc: str):
    base = f"{prefix}{ram}{nom:<{amplada}} {flag}"
    linies.append(base + (f"  # {desc}" if desc else ""))


def _amplada(entrades) -> int:
    return min(max(len(nom) for nom in entrades) if entrades else 0, 34)


def _ordrena(noms: list, carpeta: str, dirs_primer: bool):
    arxius = sorted((n for n in noms if os.path.isfile(os.path.join(carpeta, n))),
                    key=str.casefold)
    carpes = sorted((n for n in noms if os.path.isdir(os.path.join(carpeta, n))),
                    key=str.casefold)
    return (carpes + arxius) if dirs_primer else (arxius + carpes)


def _cami(linies: list, carpeta: str, prefix: str, tracked: set,
          dirs_primer: bool, nivell: int):
    """Llista recursiva d'una carpeta detallada."""
    noms = [n for n in os.listdir(carpeta) if n not in EXCLOSOS_DIRS]
    if nivell == 0:
        noms = [n for n in noms if not _efimer(n)]
    ordre = _ordrena(noms, carpeta, dirs_primer)
    amplada = _amplada(n + ("/" if os.path.isdir(os.path.join(carpeta, n)) else "")
                       for n in ordre)
    for i, nom in enumerate(ordre):
        ruta = os.path.join(carpeta, nom)
        es_dir = os.path.isdir(ruta)
        ultim = i == len(ordre) - 1
        ram = "└── " if ultim else "├── "
        cont = "    " if ultim else "│   "
        nom_vis = nom + ("/" if es_dir else "")
        flag = _flag(ruta, es_dir, tracked)
        if es_dir:
            directoris = []
            if nivell == 0:
                directoris.append(f"({_miler(_compta_fitxers(ruta))})")
        else:
            directoris = []
        desc = _desc(os.path.relpath(ruta, ARREL), es_dir)
        if desc and directoris:
            desc = desc + " " + directoris[0]
        elif directoris:
            desc = directoris[0]
        _linia(linies, prefix, ram, nom_vis, flag, amplada, desc)
        if es_dir:
            if nivell == 0 and nom in DIRS_RESUM:
                _resum(linies, ruta, prefix + cont, tracked)
            else:
                _cami(linies, ruta, prefix + cont, tracked, False, nivell + 1)


def _resum(linies: list, carpeta: str, prefix: str, tracked: set):
    """Una sola entrada de carpetas grans: recurs directe + recompte."""
    noms = [n for n in os.listdir(carpeta)
            if n not in EXCLOSOS_DIRS and n != "node_modules" and not _efimer(n)]
    ordre = _ordrena(noms, carpeta, False)
    amplada = _amplada(n + ("/" if os.path.isdir(os.path.join(carpeta, n)) else "")
                       for n in ordre)
    for i, nom in enumerate(ordre):
        ruta = os.path.join(carpeta, nom)
        es_dir = os.path.isdir(ruta)
        ultim = i == len(ordre) - 1
        ram = "└── " if ultim else "├── "
        nom_vis = nom + ("/" if es_dir else "")
        flag = _flag(ruta, es_dir, tracked)
        desc = _desc(os.path.relpath(ruta, ARREL), es_dir)
        if es_dir:
            recu = f"({_miler(_compta_fitxers(ruta))})"
            desc = desc + " " + recu if desc else recu
        _linia(linies, prefix, ram, nom_vis, flag, amplada, desc)


def _bloc_arbre() -> str:
    tracked = _llista_tracked()
    linies = ["PROJECTE AUTO CHORDS/"]
    _cami(linies, ARREL, "", tracked, True, 0)
    return "\n".join(linies)


def construeix() -> str:
    return "\n".join([INICI, "```text", _bloc_arbre(), "```", FI])


def _bloc_actual(contingut: str):
    a = contingut.find(INICI)
    b = contingut.find(FI)
    if a < 0 or b < 0 or b < a:
        return None
    return contingut[a:b + len(FI)]


def main(argv) -> int:
    text = construeix()
    if len(argv) > 1 and argv[1] == "-":
        print(text)
        return 0
    if not os.path.isfile(DOC):
        print(f"falta: {os.path.relpath(DOC, ARREL)}")
        return 1
    with open(DOC, encoding="utf-8") as f:
        contingut = f.read()
    actual = _bloc_actual(contingut)
    if actual is None:
        print(f"falten els marcadors a {os.path.relpath(DOC, ARREL)}")
        return 1
    if len(argv) > 1 and argv[1] == "--check":
        if actual != text:
            print("desactualitzat: ARBRE_DIRECTORIS.md (corre: python3 eines/genera_arbre.py)")
            return 1
        print("OK: ARBRE_DIRECTORIS.md")
        return 0
    nou = contingut.replace(actual, text)
    with open(DOC, "w", encoding="utf-8") as f:
        f.write(nou)
    print("escrit: ARBRE_DIRECTORIS.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
