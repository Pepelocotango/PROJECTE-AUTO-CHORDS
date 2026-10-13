"""Import d'altres formats d'àudio via ffmpeg.

L'app treballa amb **WAV PCM 16 bits**; si l'usuari obre un mp3, aif, flac,
m4a… el convertim automàticament amb **ffmpeg** (que ja és al sistema) i
treballem amb el WAV resultant.

El WAV convertit es deixa **al costat de l'original** com `<nom>_convertit.wav`
(i es reutilitza si ja és més nou que l'original). Així el pipeline hi pot
escriure la carpeta `AUTOCHORDS_<nom>` al costat.

Tot en català.
"""

import json
import os
import re
import subprocess
import wave

from app import plataforma

# Els binaris poden ser dins el projecte (portable/bin, fases 2-3 de
# portabilitat) o al sistema. Es prefereix el local. Noms amb `.exe` a Windows i
# comprovació d'executable tolerant (allà `os.access(X_OK)` no és fiable):
# vegeu `app/plataforma.py`.
_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LOCAL_FFMPEG = os.path.join(_PROJ, "portable", "bin", plataforma.NOM_FFMPEG)
_LOCAL_FFPROBE = os.path.join(_PROJ, "portable", "bin", plataforma.NOM_FFPROBE)
FFMPEG = _LOCAL_FFMPEG if plataforma.executable(_LOCAL_FFMPEG) else plataforma.NOM_FFMPEG
FFPROBE = _LOCAL_FFPROBE if plataforma.executable(_LOCAL_FFPROBE) else plataforma.NOM_FFPROBE
SUFIX = "_convertit"

# Opcions de seguretat per als INPUTS. Van SEMPRE abans de `-i` (a ffprobe,
# abans de la ruta): `-nostdin` evita que el binari llegeixi de l'entrada
# estàndard, i `-protocol_whitelist file,pipe` impedeix que un fitxer
# disfressat (playlist HLS/concat, subtítol…) faci que ffmpeg llegeixi altres
# fitxers o faci peticions de xarxa. No afecten la lectura d'un àudio local
# normal (que va pel protocol `file`).
_OPCIONS_ENTRADA = ["-nostdin", "-protocol_whitelist", "file,pipe"]
# Opcions que el fallback pot treure si el binari les rebutja:
#  · `-nostdin` NO existeix a ffprobe (no hi té sentit: no llegeix stdin).
#  · `-protocol_whitelist` NO existeix a ffmpeg molt vells.
_OPCIONS_FALLBACK = ("-nostdin", "-protocol_whitelist")
# Reconeix el nom de l'opció rebutjada a l'stderr:
#  · ffmpeg:  "Unrecognized option 'protocol_whitelist'."
#  · ffprobe: "Failed to set value '…' for option 'nostdin': Option not found"
_RE_OPCIO = re.compile(
    r"(?:unrecognized|unknown|invalid) option[ :]*'?(-?[a-z0-9_]+)'?"
    r"|for option '(-?[a-z0-9_]+)'")

# Extensions d'àudio que acceptem obrir (es converteixen si cal).
EXTENSIONS = [
    "wav", "mp3", "aif", "aiff", "aifc", "flac", "m4a", "aac", "ogg", "oga",
    "opus", "wma", "mp2", "caf", "w64", "au", "wv", "ape", "alac",
]


def disponible():
    """Hi ha ffmpeg? (ffprobe és OPCIONAL: només el fa servir info())."""
    try:
        subprocess.run([FFMPEG, "-version"], capture_output=True, timeout=15)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def extensions():
    return list(EXTENSIONS)


def filtre():
    """Filtre per al QFileDialog (tots els formats acceptats)."""
    pats = " ".join(f"*.{e}" for e in EXTENSIONS)
    return f"Àudio ({pats});;WAV (*.wav);;Tots els fitxers (*)"


def es_wav_pcm16(ruta):
    """Cert si `ruta` és un WAV PCM 16 bits (el que l'app necessita)."""
    if not str(ruta).lower().endswith(".wav"):
        return False
    try:
        with wave.open(ruta, "rb") as w:
            return w.getsampwidth() == 2 and w.getcomptype() == "NONE"
    except (wave.Error, OSError, EOFError):
        return False


def _no_opcio(ruta):
    """Evita que una ruta es llegeixi com una opció d'ffmpeg (comença amb `-`).

    NO filtra cap caràcter de la ruta; només hi anteposa `./` si cal.
    """
    return os.path.join(".", ruta) if ruta.startswith("-") else ruta


def _ruta_arg(ruta):
    """Ruta absoluta per passar a ffmpeg/ffprobe (sense filtrar res).

    L'app ha de poder obrir QUALSEVOL ruta: espais, accents, `#`, `&`, cometes,
    unicode, unitats externes, carpetes de xarxa/UNC, enllaços simbòlics i
    rutes llargues. Només la fem absoluta i, per si de cas, evitem que comenci
    amb `-` (`_no_opcio`).
    """
    return _no_opcio(os.path.abspath(ruta))


def _opcions_a_treure(stderr):
    """Opcions de seguretat que el binari ha rebutjat (per al fallback)."""
    fora = set()
    for m in _RE_OPCIO.finditer((stderr or "").lower()):
        nom = (m.group(1) or m.group(2) or "").lstrip("-").lower()
        if nom:
            fora.add("-" + nom)
    return fora & set(_OPCIONS_FALLBACK)


def _treu_opcions(cmd, fora):
    """Còpia de `cmd` sense les opcions de `fora` (i el seu valor, si en té)."""
    out = []
    i = 0
    while i < len(cmd):
        if cmd[i] in fora:
            i += 2 if cmd[i] == "-protocol_whitelist" else 1
            continue
        out.append(cmd[i])
        i += 1
    return out


def _executa(cmd, timeout, log=None):
    """Executa `cmd` amb fallback de seguretat.

    Si el binari no entén alguna de les opcions de seguretat (`-nostdin` a
    ffprobe; `-protocol_whitelist` a ffmpeg molt vells), reintenta sense ella i
    ho registra. Mai llança per culpa d'una d'aquestes opcions.

    Deixa passar `subprocess.TimeoutExpired` i `OSError` (els gestiona qui
    crida), igual que abans.
    """
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    fora = _opcions_a_treure(p.stderr) if p.returncode != 0 else set()
    if fora:
        if log:
            log("avís: aquest binari no entén %s; reintent sense l'opció "
                "de seguretat" % ", ".join(sorted(fora)))
        p = subprocess.run(_treu_opcions(cmd, fora), capture_output=True,
                           text=True, timeout=timeout)
    return p


def _cmd_converteix(ruta, dest):
    """Comanda d'ffmpeg per convertir `ruta` a WAV PCM 16 bits."""
    return [FFMPEG, *_OPCIONS_ENTRADA, "-y", "-i", _ruta_arg(ruta),
            "-vn", "-c:a", "pcm_s16le", _ruta_arg(dest)]


def _cmd_info(ruta):
    """Comanda de ffprobe per llegir durada/mostreig/canals."""
    return [FFPROBE, *_OPCIONS_ENTRADA, "-v", "error", "-show_entries",
            "format=duration:stream=sample_rate,channels",
            "-of", "json", _ruta_arg(ruta)]


def info(ruta, log=None):
    """Durada/mostreig/canals d'un àudio qualsevol (via ffprobe).

    Retorna un dict (o {} si no es pot llegir).
    """
    cmd = _cmd_info(ruta)
    try:
        p = _executa(cmd, timeout=60, log=log)
        dades = json.loads(p.stdout or "{}")
    except (OSError, subprocess.SubprocessError, ValueError):
        return {}
    sr = canals = None
    for st in dades.get("streams", []):
        if st.get("sample_rate"):
            sr = int(st["sample_rate"])
            canals = int(st.get("channels") or 1)
            break
    dur = dades.get("format", {}).get("duration")
    return {
        "mostreig": sr,
        "canals": canals,
        "durada": float(dur) if dur else None,
    }


def converteix_a_wav(ruta, log=None, dest=None):
    """Converteix `ruta` a WAV PCM 16 bits (manté mostreig i canals).

    Retorna la ruta del WAV. Si ja n'hi ha un de més nou, el reutilitza.
    Si `ruta` ja és WAV PCM 16 bits, la torna tal qual.
    """
    def _log(t):
        if log:
            log(t)

    if es_wav_pcm16(ruta):
        return ruta
    if dest is None:
        dest = os.path.splitext(ruta)[0] + SUFIX + ".wav"
    if (os.path.exists(dest)
            and os.path.getmtime(dest) >= os.path.getmtime(ruta)):
        _log(f"WAV convertit ja existent: {os.path.basename(dest)}")
        return dest
    cmd = _cmd_converteix(ruta, dest)
    _log("$ " + " ".join(cmd))
    try:
        p = _executa(cmd, timeout=1800, log=_log)
    except subprocess.TimeoutExpired:
        raise RuntimeError("ffmpeg: conversió massa llarga (timeout)")
    if p.returncode != 0 or not os.path.exists(dest):
        cua = (p.stderr or "").strip().splitlines()[-3:]
        raise RuntimeError("ffmpeg ha fallat: " + " | ".join(cua))
    _log(f"convertit → {os.path.basename(dest)}")
    return dest
