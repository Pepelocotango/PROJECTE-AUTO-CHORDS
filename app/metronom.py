"""metronom.py — generador de clics de metrònom (numpy pur, sense Qt).

Els clics es MESCLEN al buffer d'àudio que s'envia al reproductor, en comptes
de fer servir un segon reproductor o un QTimer (que derivaria respecte a la
cançó). Veure `app/visor.py` (_engega_des_de / _mono_bytes).

La graella és la MATEIXA que la del regle del visor: beat = 60/bpm, compàs =
cada `bpb` beats, sense offset (el visor no n'aplica cap a la visualització).
"""
import numpy as np

# Sense clics per sobre d'aquest BPM: evita bucles enormes (i no té sentit
# musical). Tambe protegeix contra un BPM exagerat escrit a mà.
BPM_MAX = 400.0

# Durada d'un clic (ms) i freqüències (Hz): accent = temps 1 de cada compàs.
CLIC_MS = 25.0
FREQ_ACCENT = 1500.0
FREQ_NORMAL = 1000.0
# Caiguda de l'envolupant: exp(-DECAY) al final del clic (~0,25 %)
_DECAY = 6.0


def genera_clic(sr, accent=True):
    """Retorna un clic com a array float32 (accentuat o normal).

    Sinusoide curta amb envolupant exponencial decreixent; comença a 0
    (sin(0)) i acaba pràcticament a 0 → sense pops.
    """
    n = max(1, int(round(sr * CLIC_MS / 1000.0)))
    t = np.arange(n, dtype=np.float32) / float(sr)
    freq = FREQ_ACCENT if accent else FREQ_NORMAL
    env = np.exp(-_DECAY * (t / t[-1] if n > 1 else 0.0)).astype(np.float32)
    return (np.sin(2.0 * np.pi * freq * t) * env).astype(np.float32)


def _es_valid(bpm, bpb):
    """BPM ha de ser finit i > 0; bpb < 1 es tracta com a 1."""
    try:
        if not np.isfinite(bpm) or bpm <= 0 or bpm > BPM_MAX:
            return None
    except TypeError:
        return None
    return max(1, int(bpb))


def beats_a_temps(k, bpm, offset=0.0):
    """Temps (s) del beat global `k` segons la graella."""
    return k * (60.0 / float(bpm)) + float(offset)


def mescla_metronom(mono_bytes, sr, t_inici, bpm, bpb,
                    volum=0.6, offset=0.0):
    """Mescla els clics a la rodanxa `mono_bytes` (int16 mono, a partir de
    `t_inici` segons de la cançó) i retorna els bytes int16 resultants.

    - Només genera els clics que cauen dins la rodanxa (funciona des de
      qualsevol posició i amb el loop A/B).
    - Suma en float32 i fa clip a int16 per evitar desbordament.
    - volum 0 (o BPM invàlid) → retorna l'àudio sense canvis.
    """
    _bpb = _es_valid(bpm, bpb)
    if _bpb is None or volum <= 0:
        return mono_bytes

    buf = np.frombuffer(mono_bytes, dtype=np.int16).astype(np.float32)
    if buf.size == 0:
        return mono_bytes
    sr = float(sr)
    dur = buf.size / sr
    beat_len = 60.0 / float(bpm)

    # genera_clic() retorna ±1 normalitzat: cal escalar-lo a la gamma int16
    guany = 32767.0 * float(volum)
    clic_accent = genera_clic(sr, True) * guany
    clic_normal = genera_clic(sr, False) * guany

    # Primer beat global amb temps >= t_inici (arrodonint cap amunt)
    k0 = int(np.ceil((t_inici - offset) / beat_len))
    if k0 < 0:
        k0 = 0
    k = k0
    while True:
        t_b = beats_a_temps(k, bpm, offset) - float(t_inici)
        if t_b >= dur:
            break
        if t_b >= 0.0:
            i = int(round(t_b * sr))
            clic = clic_accent if (k % _bpb == 0) else clic_normal
            n = min(clic.size, buf.size - i)
            if n > 0:
                buf[i:i + n] += clic[:n]
        k += 1

    np.clip(buf, -32768.0, 32767.0, out=buf)
    return buf.astype(np.int16).tobytes()
