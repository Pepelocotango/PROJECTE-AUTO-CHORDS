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
    if not ruta or not os.path.isfile(str(ruta)):
        raise ValueError(f"Fitxer d'àudio no trobat o no vàlid: {ruta!r}")

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


# --- Velocitat amb el to mantingut (Anàlisi guiat v3, R11) -------------------
#: Velocitats que ofereix el diàleg d'ancoratges: ½ · ⅔ (1÷1,5) · 1 · 1,5 · 2 · 4.
VELOCITATS = (0.5, 1.0 / 1.5, 1.0, 1.5, 2.0, 4.0)
#: Prefix dels temporals d'estirament (R19: viuen al directori temporal).
PREFIX_VELOCITAT = "auto_chords_vel_"


def cadena_atempo(factor):
    """Cadena de filtres `atempo` per a un factor qualsevol (to mantingut).

    `atempo` només accepta 0,5–2 per filtre: els factors grans es fan amb
    una cadena (4× = dos cops 2×).
    """
    try:
        f = float(factor)
    except (TypeError, ValueError):
        raise ValueError("El factor de velocitat no és un número") from None
    if f <= 0:
        raise ValueError("El factor de velocitat ha de ser > 0")
    parts = []
    while f > 2.0 + 1e-9:
        parts.append("atempo=2.0")
        f /= 2.0
    while f < 0.5 - 1e-9:
        parts.append("atempo=0.5")
        f /= 0.5
    parts.append(f"atempo={f:.6f}")
    return ",".join(parts)


def ruta_velocitat(ruta, factor, carpeta=None):
    """Ruta del temporal d'estirament per a `ruta` a `factor` (determinista)."""
    import hashlib
    import tempfile
    st = os.stat(ruta)
    clau = "%s|%d|%d|%s|mono" % (os.path.abspath(ruta), int(st.st_mtime),
                                 int(st.st_size),
                                 repr(round(float(factor), 4)))
    h = hashlib.md5(clau.encode("utf-8")).hexdigest()[:12]
    base = os.path.splitext(os.path.basename(ruta))[0]
    base = re.sub(r"[^A-Za-z0-9_.-]+", "_", base)[:40]
    carpeta = carpeta or tempfile.gettempdir()
    return os.path.join(carpeta, f"{PREFIX_VELOCITAT}{base}_{h}_"
                                 f"{float(factor):g}x.wav")


def _es_mono_pcm16(ruta):
    """True si el WAV és mono PCM 16 bits (el que mengen els reproductors)."""
    try:
        import wave
        with wave.open(str(ruta), "rb") as wf:
            return int(wf.getnchannels()) == 1 and int(wf.getsampwidth()) == 2
    except (OSError, EOFError, ValueError, ImportError):
        return False


def prepara_escolta(ruta, factor=1.0, log=None, carpeta=None):
    """Còpia **mono PCM16** reproduïble a `factor`×, per al diàleg del guiat.

    El transport del guiat envia PCM mono als reproductors (`paplay`/`aplay` i el
    motor natiu), així que un WAV original **estèreo** (la majoria) s'ha de
    convertir: si ja és mono a 1,0× es torna la mateixa ruta; si no, es
    renderitza (una sola vegada: caché per mtime+mida+factor).
    """
    if not ruta or not os.path.isfile(str(ruta)):
        raise ValueError(f"Fitxer d'àudio no trobat: {ruta!r}")
    f = float(factor)
    if f <= 0:
        raise ValueError("El factor de velocitat ha de ser > 0")
    if abs(f - 1.0) < 1e-9 and _es_mono_pcm16(ruta):
        return ruta
    return _render(ruta, f, log, carpeta)


def estira_a_wav(ruta, factor, log=None, carpeta=None):
    """Còpia de `ruta` reproduïble a `factor`× **mantenint el to** (R11).

    A 1,0× torna la mateixa ruta. La resta es renderitzen amb `ffmpeg atempo` a
    un WAV PCM 16 del directori temporal (caché: es reutilitza si ja hi és i és
    més nou que l'original). La relació amb el temps real és
    ``t_real = t_estirat × factor`` (a ½, 1 s de música ocupa 2 s de fitxer).
    """
    if not ruta or not os.path.isfile(str(ruta)):
        raise ValueError(f"Fitxer d'àudio no trobat: {ruta!r}")
    f = float(factor)
    if f <= 0:
        raise ValueError("El factor de velocitat ha de ser > 0")
    if abs(f - 1.0) < 1e-9:
        return ruta
    return _render(ruta, f, log, carpeta)


def _render(ruta, f, log=None, carpeta=None):
    """Renderitza `ruta` a `f`× en mono PCM16 (caché). Vore `estira_a_wav`."""
    if not disponible():
        raise RuntimeError("Cal ffmpeg per a canviar la velocitat")
    dest = ruta_velocitat(ruta, f, carpeta)

    def _log(t):
        if log:
            log(t)

    if (os.path.exists(dest)
            and os.path.getmtime(dest) >= os.path.getmtime(ruta)):
        _log(f"velocitat {f:g}× en caché: {os.path.basename(dest)}")
        return dest
    cmd = [FFMPEG, *_OPCIONS_ENTRADA, "-y", "-i", _ruta_arg(ruta), "-vn"]
    if abs(f - 1.0) > 1e-9:
        # a 1,0× només es canvia a mono: `atempo=1` retallaria 32 ms de cua
        cmd += ["-filter:a", cadena_atempo(f)]
    cmd += ["-ac", "1", "-c:a", "pcm_s16le", _ruta_arg(dest)]
    _log("$ " + " ".join(cmd))
    try:
        p = _executa(cmd, timeout=1800, log=_log)
    except subprocess.TimeoutExpired:
        raise RuntimeError("ffmpeg: estirament massa llarg (timeout)")
    if p.returncode != 0 or not os.path.exists(dest):
        cua = (p.stderr or "").strip().splitlines()[-3:]
        raise RuntimeError("ffmpeg no ha pogut canviar la velocitat: "
                           + " | ".join(cua))
    _log(f"velocitat {f:g}× → {os.path.basename(dest)}")
    return dest
