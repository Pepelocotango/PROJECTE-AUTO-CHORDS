#!/usr/bin/env python3
"""Genera `docs/COMPONENTS_I_VERSIONS.md`: què porta l'app a dins i quina versió.

És **només lectura**: mira l'entorn del projecte (venv, `portable/`, plugins
compilats, `eines/deps_fixades.env`) i escriu **un sol document**. No instal·la,
no baixa i no modifica res més.

Per a què serveix: quan es publica un **avís de seguretat** d'un d'aquests
components, mirar aquesta pàgina diu de seguida si ens afecta i quina versió en
fem servir.

Ús:
    python3 eines/genera_inventari.py            # escriu el document
    python3 eines/genera_inventari.py -          # ho imprimeix per pantalla
"""
import glob
import os
import re
import subprocess
import sys
import time

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESTI = os.path.join(ARREL, "docs", "COMPONENTS_I_VERSIONS.md")


def _corre(cmd, timeout=30):
    """Executa una comanda i retorna la primera línia de sortida (o '')."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = (p.stdout or "") + (p.stderr or "")
        return out.strip().splitlines()[0].strip() if out.strip() else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _versio_ffmpeg(binari):
    """(versió, línies de les llibreries internes, biblioteques habilitades)."""
    if not (binari and os.path.isfile(binari)):
        return None, [], []
    primera = _corre([binari, "-version"])
    m = re.search(r"ffmpeg version (\S+)", primera)
    ver = m.group(1) if m else ""
    internes = []
    for ln in _corre_tot([binari, "-version"]):
        if re.match(r"^\s*lib(av|sw)\w+\s+\d", ln):
            internes.append(ln.strip())
    habilitades = []
    for ln in _corre_tot([binari, "-buildconf"]):
        for m2 in re.finditer(r"--enable-(lib[a-z0-9_]+)", ln):
            habilitades.append(m2.group(1))
    return ver, internes, sorted(set(habilitades))


def _corre_tot(cmd, timeout=30):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return ((p.stdout or "") + (p.stderr or "")).splitlines()
    except (OSError, subprocess.SubprocessError):
        return []


def _paquets_de(site_packages):
    """{nom: versió} llegint els `*.dist-info` d'una carpeta site-packages."""
    d = {}
    if not site_packages or not os.path.isdir(site_packages):
        return d
    for info in glob.glob(os.path.join(site_packages, "*.dist-info")):
        base = os.path.basename(info)[:-len(".dist-info")]
        if "-" not in base:
            continue
        nom, _, ver = base.rpartition("-")
        d[nom.lower()] = ver
    return d


def _paquets_venv():
    """Paquets del `.venv` (via pip freeze; si no, mirant site-packages)."""
    py = os.path.join(ARREL, ".venv", "bin", "python")
    if os.path.isfile(py):
        linies = _corre_tot([py, "-m", "pip", "freeze"])
        d = {}
        for ln in linies:
            if "==" in ln:
                nom, _, ver = ln.partition("==")
                d[nom.strip().lower()] = ver.strip()
        if d:
            return d
    return _paquets_de(os.path.join(ARREL, ".venv", "lib",
                                    "python3.12", "site-packages"))


def _python_portable():
    py = os.path.join(ARREL, "portable", "python", "bin", "python3")
    if not os.path.isfile(py):
        return "", {}
    ver = _corre([py, "--version"]).replace("Python ", "")
    site = os.path.join(ARREL, "portable", "python", "lib", "python3.12",
                        "site-packages")
    return ver, _paquets_de(site)


def _vars_deps():
    """Variables de `eines/deps_fixades.env` (les que no depenen d'altres)."""
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
    """{nom: versió} dels pins exactes de `requirements.txt` (fallback)."""
    d = {}
    ruta = os.path.join(ARREL, "requirements.txt")
    if not os.path.isfile(ruta):
        return d
    with open(ruta, encoding="utf-8") as f:
        for ln in f:
            ln = ln.split("#", 1)[0].strip()
            if not ln or "==" not in ln:
                continue
            nom, _, resta = ln.partition("==")
            ver = resta.split(";")[0].strip().split(",")[0].strip()
            d.setdefault(nom.strip().lower(), ver)
    return d


def _plugins():
    """Plugins Vamp compilats que hi ha al projecte."""
    trobats = []
    for patro in ("*-local/*.so", "*-local/*.dylib", "*-local/*.dll"):
        for p in sorted(glob.glob(os.path.join(ARREL, patro))):
            trobats.append(os.path.relpath(p, ARREL))
    return trobats


def construeix():
    """Retorna el text del document."""
    deps = _vars_deps()
    venv = _paquets_venv()
    pins = _pins_requirements()

    def pkg(nom, defecte="—"):
        """Versió del paquet: primer la instal·lada, si no el pin de requirements."""
        return venv.get(nom) or pins.get(nom) or defecte

    py_venv = _corre([os.path.join(ARREL, ".venv", "bin", "python"), "--version"])
    py_port, paquets_port = _python_portable()
    ff = os.path.join(ARREL, "portable", "bin", "ffmpeg")
    ver_ff, internes_ff, habilitats_ff = _versio_ffmpeg(ff)
    host = os.path.isfile(os.path.join(ARREL, "vamp_host_local"))
    plugins = _plugins()

    def v(d, clau, defecte="—"):
        return d.get(clau, defecte)

    L = []
    L.append("# Components i versions")
    L.append("")
    L.append("> Generat per **`eines/genera_inventari.py`** (només lectura) — "
             f"{time.strftime('%Y-%m-%d')}.")
    L.append("> Serveix per **vigilar avisos de seguretat**: si se'n publica un "
             "d'un d'aquests components,")
    L.append("> aquí es veu quina versió en fem servir i on es fixa.")
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
    L.append(f"| Python (venv de desenvolupament) | {py_venv.replace('Python ', '') or '—'} | del sistema |")
    L.append(f"| Python (portable, el que s'empaqueta) | {py_port or '—'} | python-build-standalone **{v(deps, 'PYBS_TAG')}** |")
    L.append(f"| PyQt5 | {pkg('pyqt5')} | PyPI (a macOS 10.13: 5.15.10) |")
    L.append(f"| PyQt5-Qt5 | {pkg('pyqt5-qt5')} | PyPI |")
    L.append(f"| PyQt5_sip | {pkg('pyqt5_sip')} | PyPI |")
    L.append(f"| numpy | {pkg('numpy')} | PyPI (**1.x**: el Q9400 no té AVX) |")
    L.append(f"| sounddevice | {pkg('sounddevice')} | PyPI (àudio natiu mac/win) |")
    L.append(f"| cffi | {pkg('cffi')} | PyPI |")
    L.append(f"| ffmpeg | {ver_ff or '—'} | {'johnvansickle (estàtic)' if ver_ff else '—'} **{v(deps, 'FFMPEG_LINUX_VER')}** |")
    L.append(f"| appimagetool | **{v(deps, 'APPIMAGETOOL_VER')}** | GitHub (AppImage) |")
    L.append("| Vamp: nnls-chroma (Chordino) | compilat | codi font del projecte |")
    L.append(f"| Vamp: qm-vamp-plugins | compilat | commit `{v(deps, 'QM_VAMP_PLUGINS_COMMIT')[:12]}…` |")
    L.append(f"| Vamp: qm-dsp | compilat | commit `{v(deps, 'QM_DSP_COMMIT')[:12]}…` |")
    L.append(f"| Vamp: vamp-plugin-sdk | compilat | commit `{v(deps, 'VAMP_PLUGIN_SDK_COMMIT')[:12]}…` |")
    L.append(f"| Vamp host (`vamp_host_local`) | {'present' if host else 'no compilat'} | codi font del projecte |")
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
    L.append("> Els SHA256 de cada baixada són al mateix fitxer "
             "(`..._SHA256`) i es verifiquen a cada descàrrega; les URLs "
             "(`..._URL`) també hi són.")
    L.append("")
    if internes_ff:
        L.append("## Llibreries internes d'ffmpeg")
        L.append("")
        L.append("> Són les que porta l'ffmpeg estàtic; també tenen avisos de "
                 "seguretat propis.")
        L.append("")
        L.append("```")
        for ln in internes_ff:
            L.append(ln)
        L.append("```")
        L.append("")
    if habilitats_ff:
        L.append("## Llibreries de tercers que porta l'ffmpeg")
        L.append("")
        L.append("Habilitades al build d'ffmpeg (la versió exacta ve donada pel "
                 "mateix build d'ffmpeg):")
        L.append("")
        L.append(", ".join(f"`{h}`" for h in habilitats_ff))
        L.append("")
    if paquets_port:
        L.append("## Paquets del Python portable (el que s'empaqueta)")
        L.append("")
        L.append("| Paquet | Versió |")
        L.append("|---|---|")
        for k in sorted(paquets_port):
            L.append(f"| {k} | {paquets_port[k]} |")
        L.append("")
    if plugins:
        L.append("## Fitxers de plugins compilats al projecte")
        L.append("")
        for p in plugins:
            L.append(f"- `{p}`")
        L.append("")
    L.append("## Com s'actualitza")
    L.append("")
    L.append("1. Canvia la versió a `eines/deps_fixades.env` (i, si cal, al "
             "script que la fa servir).")
    L.append("2. Calcula el SHA256 nou: "
             "`python3 eines/baixa_verificat.py \"<URL>\" - /tmp/x`.")
    L.append("3. Regenera aquest document: "
             "`python3 eines/genera_inventari.py`.")
    L.append("4. Comprova que el build segueix funcionant (i, a macOS, el "
             "mínim 10.13).")
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
