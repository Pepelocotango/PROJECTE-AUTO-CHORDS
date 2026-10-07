"""Import d'altres formats d'àudio via ffmpeg.

L'app treballa amb **WAV PCM 16 bits**; si l'usuari obre un mp3, aif, flac,
m4a… el convertim automàticament amb **ffmpeg** (que ja és al sistema) i
treballem amb el WAV resultant.

El WAV convertit es deixa **al costat de l'original** com `<nom>_convertit.wav`
(i es reutilitza si ja és més nou que l'original). Així el pipeline hi pot
escriure la carpeta `<nom>_ACORDS` al costat.

Tot en català.
"""

import json
import os
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


def info(ruta):
    """Durada/mostreig/canals d'un àudio qualsevol (via ffprobe).

    Retorna un dict (o {} si no es pot llegir).
    """
    cmd = [FFPROBE, "-v", "error", "-show_entries",
           "format=duration:stream=sample_rate,channels",
           "-of", "json", ruta]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
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
    cmd = [FFMPEG, "-y", "-i", ruta, "-vn", "-c:a", "pcm_s16le", dest]
    _log("$ " + " ".join(cmd))
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except subprocess.TimeoutExpired:
        raise RuntimeError("ffmpeg: conversió massa llarga (timeout)")
    if p.returncode != 0 or not os.path.exists(dest):
        cua = (p.stderr or "").strip().splitlines()[-3:]
        raise RuntimeError("ffmpeg ha fallat: " + " | ".join(cua))
    _log(f"convertit → {os.path.basename(dest)}")
    return dest
