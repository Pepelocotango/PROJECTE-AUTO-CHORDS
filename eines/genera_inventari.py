#!/usr/bin/env python3
"""Genera `docs/COMPONENTS_I_VERSIONS.md`: què porta l'app a dins i quina versió.

És **només lectura** i, sobretot, **DETERMINISTA**: només mira **fitxers del
repositori** (`requirements.txt`, `eines/deps_fixades.env` i els globs dels
plugins), MAI l'entorn local (venv, `portable/`). Així el document es pot
**regenerar al CI i comprovar-lo amb `git diff --exit-code`** (si algú canvia
una versió i no regenera el document, el CI peta). Vegeu
`docs/archive/AUDITORIA_PRODUCCIO.md` (D.5).

⚠️ Conseqüència: si canvies una versió a `requirements.txt` o a
`deps_fixades.env`, HAS de tornar a córrer aquest script i commitejar el .md.

Ús:
    python3 eines/genera_inventari.py            # escriu el document
    python3 eines/genera_inventari.py -          # ho imprimeix per pantalla
"""
import glob
import os
import sys

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESTI = os.path.join(ARREL, "docs", "COMPONENTS_I_VERSIONS.md")


def _vars_deps():
    """Variables de `eines/deps_fixades.env` (font única de versions baixades)."""
    d = {}
    ruta = os.path.join(ARREL, "eines", "deps_fixades.env")
    if not os.path.isfile(ruta):
        return d
    with open(ruta, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln or ln.startswith("#") or "=" not in ln:
                continue
            k, _, v = ln.partition("=")
            d[k.strip()] = v.strip().strip('"')
    return d


def _pins_requirements():
    """{nom: versió} dels pins exactes de `requirements.txt` (font única Python).

    Algun paquet té **diversos pins amb marcadors** (per plataforma), p. ex.
    `PyQt5-Qt5==5.15.2; sys_platform == "win32"` i
    `PyQt5-Qt5==5.15.19; sys_platform != "win32"`. Ens quedem amb el **cas
    general** (el marcador amb `!=`, o el pin sense marcador), que és el que
    descriu la resta de sistemes.
    """
    ruta = os.path.join(ARREL, "requirements.txt")
    if not os.path.isfile(ruta):
        return {}
    linies = []
    with open(ruta, encoding="utf-8") as f:
        for ln in f:
            ln = ln.split("#", 1)[0].strip()
            if not ln or "==" not in ln:
                continue
            nom, _, resta = ln.partition("==")
            parts = resta.split(";", 1)
            ver = parts[0].strip().split(",")[0].strip()
            marcador = parts[1].strip() if len(parts) > 1 else ""
            linies.append((nom.strip().lower(), ver, marcador))

    def _general(marcador):
        # «cas general»: sense marcador, o un `!=` (descriu la majoria de SO).
        return marcador == "" or "!=" in marcador

    d = {}
    for nom, ver, marcador in linies:
        if nom not in d or (_general(marcador) and not _general(d[nom][1])):
            d[nom] = (ver, marcador)
    return {k: v[0] for k, v in d.items()}


def _plugins():
    """Plugins Vamp compilats que hi ha al projecte (glob del repositori)."""
    trobats = []
    for patro in ("*-local/*.so", "*-local/*.dylib", "*-local/*.dll"):
        for p in sorted(glob.glob(os.path.join(ARREL, patro))):
            trobats.append(os.path.relpath(p, ARREL))
    return trobats


def construeix():
    """Retorna el text del document (només a partir de fonts del repositori)."""
    deps = _vars_deps()
    pins = _pins_requirements()

    def pin(nom, defecte="—"):
        return pins.get(nom, defecte)

    def dep(clau, defecte="—"):
        return deps.get(clau, defecte)

    def commit(clau):
        c = deps.get(clau, "")
        return f"{c[:12]}…" if c else "—"

    host = os.path.isfile(os.path.join(ARREL, "vamp_host_local"))
    plugins = _plugins()

    L = []
    L.append("# Components i versions")
    L.append("")
    L.append("> Generat per **`eines/genera_inventari.py`** a partir de fonts del")
    L.append("> **repositori** (`requirements.txt` i `eines/deps_fixades.env`) —")
    L.append("> **sense mirar l'entorn local** — perquè el CI pugui comprovar que")
    L.append("> està al dia (`git diff --exit-code`).")
    L.append("> Serveix per **vigilar avisos de seguretat**: si se'n publica un d'un")
    L.append("> d'aquests components, aquí es veu quina versió en fem servir i on es fixa.")
    L.append(">")
    L.append("> Per regenerar-lo després de canviar una versió:")
    L.append("> ```")
    L.append("> python3 eines/genera_inventari.py")
    L.append("> ```")
    L.append("")
    L.append("## Resum")
    L.append("")
    L.append("| Component | Versió | Origen |")
    L.append("|---|---|---|")
    L.append(f"| Python (portable, el que s'empaqueta) | **{dep('PYBS_PYV')}** | "
             f"python-build-standalone **{dep('PYBS_TAG')}** |")
    L.append(f"| PyQt5 | {pin('pyqt5')} | PyPI (a macOS 10.13: 5.15.10) |")
    L.append(f"| PyQt5-Qt5 | {pin('pyqt5-qt5')} | PyPI |")
    L.append(f"| PyQt5_sip | {pin('pyqt5_sip')} | PyPI |")
    L.append(f"| numpy | {pin('numpy')} | PyPI (**1.x**: el Q9400 no té AVX) |")
    L.append(f"| sounddevice | {pin('sounddevice')} | PyPI (àudio natiu mac/win) |")
    L.append(f"| cffi | {pin('cffi')} | PyPI |")
    L.append(f"| ffmpeg (Linux) | **{dep('FFMPEG_LINUX_VER')}** | johnvansickle (estàtic) |")
    L.append(f"| ffmpeg (macOS) | **{dep('FFMPEG_MAC_VER')}** | evermeet.cx (estàtic) |")
    L.append(f"| ffmpeg (Windows) | **{dep('FFMPEG_WIN_VER')}** | gyan.dev (estàtic) |")
    L.append(f"| appimagetool | **{dep('APPIMAGETOOL_VER')}** | GitHub (AppImage) |")
    L.append(f"| Icones Lucide | **{dep('LUCIDE_TAG')}** | raw.githubusercontent |")
    L.append("| Vamp: nnls-chroma (Chordino) | compilat | codi font del projecte |")
    L.append(f"| Vamp: qm-vamp-plugins | compilat | commit `{commit('QM_VAMP_PLUGINS_COMMIT')}` |")
    L.append(f"| Vamp: qm-dsp | compilat | commit `{commit('QM_DSP_COMMIT')}` |")
    L.append(f"| Vamp: vamp-plugin-sdk | compilat | commit `{commit('VAMP_PLUGIN_SDK_COMMIT')}` |")
    L.append(f"| Vamp: libsndfile | compilat | commit `{commit('LIBSNDFILE_COMMIT')}` |")
    L.append(f"| Vamp host (`vamp_host_local`) | {'present' if host else 'no compilat'} | codi font del projecte |")
    L.append("")
    L.append("> El venv de desenvolupament i l'entorn portable instal·len **exactament")
    L.append("> aquests pins** (`requirements.txt`); aquest document NO llegeix cap")
    L.append("> entorn local, perquè sigui reproduïble al CI.")
    L.append("")
    L.append("## Versions fixades (`eines/deps_fixades.env`)")
    L.append("")
    L.append("| Clau | Valor |")
    L.append("|---|---|")
    for k in sorted(deps):
        if k.endswith("_SHA256") or k.endswith("_URL"):
            continue
        L.append(f"| `{k}` | `{deps[k]}` |")
    L.append("")
    L.append("> Els SHA256 de cada baixada són al mateix fitxer (`..._SHA256`) i es")
    L.append("> verifiquen a cada descàrrega; les URLs (`..._URL`) també hi són.")
    L.append("")
    if plugins:
        L.append("## Fitxers de plugins compilats al projecte")
        L.append("")
        for p in plugins:
            L.append(f"- `{p}`")
        L.append("")
    L.append("## Com s'actualitza")
    L.append("")
    L.append("1. Canvia la versió a `eines/deps_fixades.env` (i, si cal, al script")
    L.append("   que la fa servir) o el pin a `requirements.txt`.")
    L.append("2. Calcula el SHA256 nou: "
             "`python3 eines/baixa_verificat.py \"<URL>\" - /tmp/x`.")
    L.append("3. Regenera aquest document: `python3 eines/genera_inventari.py` "
             "(i commiteja'l).")
    L.append("4. Comprova que el build segueix funcionant (i, a macOS, el mínim 10.13).")
    L.append("")
    L.append("> Detall complet: `docs/SEGURETAT.md`.")
    L.append("")
    return "\n".join(L)


def main(argv):
    text = construeix()
    if len(argv) > 1 and argv[1] == "-":
        print(text)
        return 0
    os.makedirs(os.path.dirname(DESTI), exist_ok=True)
    with open(DESTI, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"escrit: {os.path.relpath(DESTI, ARREL)} ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
