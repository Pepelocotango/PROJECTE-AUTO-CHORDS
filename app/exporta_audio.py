"""Exportació de l'àudio de treball a altres formats (Fase 6).

L'app treballa sempre amb una **còpia WAV PCM 16 bits** dins el projecte.
Aquest mòdul exporta eixa còpia (ja editada) a un fitxer **nou** triat per
l'usuari, amb un perfil de qualitat senzill i sense tocar mai l'original ni la
còpia de treball.

Els perfils són una llista curta i deliberadament simple:

- **WAV** PCM 16 bits (mostreig original, 44,1 kHz o 48 kHz), 24 bits i
  32 bits float.
- **MP3** 128, 192 i 320 kbps (CBR).
- **FLAC** sense pèrdua (16 bits).
- **AAC/M4A** 256 kbps, **OGG Vorbis** q6 i **Opus** 160 kbps.

Només s'ofereixen els perfils que el `ffmpeg` del paquet sap escriure de
veritat: la disponibilitat es consulta amb `ffmpeg.encoders()`.

L'escriptura és **atòmica**: ffmpeg treballa en un temporal dins la carpeta de
destí i només se substitueix el fitxer final si tot ha anat bé. Un error no
deixa fitxers a mitges ni toca res del projecte.
"""

import os
import subprocess
import tempfile

from app import ffmpeg

# Un perfil és: id intern, etiqueta visible, extensió, codecs candidats (el
# primer disponible mana) i opcions extra per a ffmpeg.
PERFILS = (
    {"id": "wav16_origen", "etiqueta": "WAV PCM 16 bits · mostreig original",
     "ext": "wav", "codecs": ("pcm_s16le",), "args": ()},
    {"id": "wav16_441", "etiqueta": "WAV PCM 16 bits · 44,1 kHz",
     "ext": "wav", "codecs": ("pcm_s16le",), "args": ("-ar", "44100")},
    {"id": "wav16_48", "etiqueta": "WAV PCM 16 bits · 48 kHz",
     "ext": "wav", "codecs": ("pcm_s16le",), "args": ("-ar", "48000")},
    {"id": "wav24_48", "etiqueta": "WAV PCM 24 bits · 48 kHz",
     "ext": "wav", "codecs": ("pcm_s24le",), "args": ("-ar", "48000")},
    {"id": "wav32_48", "etiqueta": "WAV PCM 32 bits float · 48 kHz",
     "ext": "wav", "codecs": ("pcm_f32le",), "args": ("-ar", "48000")},
    {"id": "mp3_128", "etiqueta": "MP3 128 kbps",
     "ext": "mp3", "codecs": ("libmp3lame",), "args": ("-b:a", "128k")},
    {"id": "mp3_192", "etiqueta": "MP3 192 kbps",
     "ext": "mp3", "codecs": ("libmp3lame",), "args": ("-b:a", "192k")},
    {"id": "mp3_320", "etiqueta": "MP3 320 kbps",
     "ext": "mp3", "codecs": ("libmp3lame",), "args": ("-b:a", "320k")},
    {"id": "flac", "etiqueta": "FLAC 16 bits (sense pèrdua)",
     "ext": "flac", "codecs": ("flac",), "args": ("-sample_fmt", "s16")},
    {"id": "m4a_256", "etiqueta": "AAC/M4A 256 kbps",
     "ext": "m4a", "codecs": ("aac", "libfdk_aac"), "args": ("-b:a", "256k")},
    {"id": "ogg_q6", "etiqueta": "OGG Vorbis q6 (~192 kbps)",
     "ext": "ogg", "codecs": ("libvorbis",), "args": ("-q:a", "6")},
    {"id": "opus_160", "etiqueta": "Opus 160 kbps",
     "ext": "opus", "codecs": ("libopus",), "args": ("-b:a", "160k")},
)


def _amb_codec(perfil, disponibles):
    """Còpia del perfil amb el primer còdec disponible, o `None`."""
    for codec in perfil["codecs"]:
        if codec in disponibles:
            return {**perfil, "codec": codec, "args": tuple(perfil["args"])}
    return None


def perfils_disponibles(disponibles=None):
    """Perfils que aquest ffmpeg pot escriure (en l'orde de `PERFILS`)."""
    if disponibles is None:
        disponibles = ffmpeg.encoders()
    if not disponibles:
        return []
    out = []
    for perfil in PERFILS:
        p = _amb_codec(perfil, disponibles)
        if p is not None:
            out.append(p)
    return out


def filtre(perfil):
    """Text del filtre per a `QFileDialog` (etiqueta + extensió)."""
    return f"{perfil['etiqueta']} (*.{perfil['ext']})"


def perfil_de_filtre(text, perfils=None):
    """Retorna el perfil corresponent al filtre triat (o `None`)."""
    for perfil in (perfils if perfils is not None else perfils_disponibles()):
        if text == filtre(perfil) or text == perfil["etiqueta"]:
            return perfil
    return None


def exporta(origen, desti, perfil, log=None):
    """Exporta `origen` a `desti` amb el `perfil` indicat.

    Retorna la ruta final. Rebutja exportar sobre el mateix fitxer, una
    extensió que no corresponga al perfil o un còdec que aquest ffmpeg no
    tinga. Escriu en un temporal i només publica el fitxer si acaba bé.
    """
    origen = os.path.abspath(str(origen or ""))
    desti = os.path.abspath(str(desti or ""))
    if not origen or not os.path.isfile(origen):
        raise ValueError(f"Fitxer d'àudio no trobat: {origen!r}")
    if not desti:
        raise ValueError("Cal indicar un fitxer de destinació")
    if os.path.realpath(origen) == os.path.realpath(desti):
        raise ValueError("No es pot exportar sobre el mateix fitxer d'origen")
    ext = os.path.splitext(desti)[1].lstrip(".").lower()
    if ext != str(perfil.get("ext", "")).lower():
        raise ValueError(
            f"L'extensió «.{ext}» no correspon al format «{perfil['etiqueta']}»")
    carpeta = os.path.dirname(desti) or "."
    if not os.path.isdir(carpeta):
        raise ValueError(f"La carpeta de destinació no existeix: {carpeta}")

    disponibles = ffmpeg.encoders()
    codec = perfil.get("codec")
    if not disponibles or codec not in disponibles:
        raise ValueError(
            f"Aquest ffmpeg no pot escriure el format «{perfil['etiqueta']}»")

    fd, temporal = tempfile.mkstemp(
        prefix=".auto-chords-export-", suffix="." + ext, dir=carpeta)
    os.close(fd)
    try:
        cmd = ffmpeg.comanda_exporta(origen, temporal, codec,
                                     perfil.get("args", ()))
        if log:
            log("$ " + " ".join(cmd))
        try:
            p = ffmpeg._executa(cmd, timeout=3600, log=log)
        except subprocess.TimeoutExpired:
            raise RuntimeError("ffmpeg: exportació massa llarga (timeout)")
        if p.returncode != 0 or not os.path.exists(temporal) \
                or os.path.getsize(temporal) == 0:
            cua = (p.stderr or "").strip().splitlines()[-3:]
            raise RuntimeError("ffmpeg ha fallat: " + " | ".join(cua))
        os.replace(temporal, desti)
    finally:
        if os.path.exists(temporal):
            os.remove(temporal)
    if log:
        log(f"exportat → {os.path.basename(desti)}")
    return desti
