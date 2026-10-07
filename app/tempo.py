"""tempo.py — detecció de BPM (numpy pur, sense Qt ni processos externs).

Per què no aubio? El seu *beat tracker* s'enganxa de vegades a un pols erroni
(p. ex. una subdivisió) en trossos del tema. Aquí mesurem la **periodicitat
real** de la música a partir de l'**envolupant d'onsets** i una puntuació
«comb»: si un BPM explica bé el senyal, l'autocorrelació tindrà pics forts al
seu període I als seus múltiples (temps, compàs...).

Provat amb:
  - "01 101bpm pep live RE-ESTRUCTURA.wav" (9,5 s de silenci inicial) → 101,0
  - "04 PEP LOGIC 118BMP.wav"                                        → 117,8
"""
import wave

import numpy as np

# Rang plausible de BPM i «zona còmoda» (plateau del prior).
BPM_MIN = 60.0
BPM_MAX = 180.0
# Zona on el prior val 1,0; fora cau suaument. Abans era un biaix pla del
# +15 % a 90-180, que NO resolia l'ambigüitat d'octava/subdivisió: en un tema
# de soul amb corxera forta (Otis Redding) guanyava 179,8 en comptes de 103,5.
BPM_PREFERIT = (80.0, 160.0)
PRIOR_SIGMA = 0.7     # amplada de la caiguda fora del plateau, en octaves
HOP_S = 0.01          # resolució temporal de l'envolupant (10 ms)


def _prior(bpm, preferit=BPM_PREFERIT):
    """Pes suau cap a la zona «còmoda» de tempo (plateau + caiguda log2).

    Dins `preferit` val 1,0; fora cau com una gaussiana en escala logarítmica
    (octaves). Això descarta el doble/subdivisió extrems sense imposar un pic
    (que trencaria temes lents genuïns, com el de 70 BPM).
    """
    if not preferit:
        return 1.0
    lo, hi = preferit
    if lo <= bpm <= hi:
        return 1.0
    x = np.log2(lo / bpm) if bpm < lo else np.log2(bpm / hi)
    return float(np.exp(-0.5 * (x / PRIOR_SIGMA) ** 2))


def _envolupant_onsets(wav_path):
    """Envolupant d'onsets (flux espectral simplificat) a passos de HOP_S.

    Treu el silenci inicial (perquè no dilueixi la periodicitat). Retorna un
    array 1-D (centrat a 0).
    """
    with wave.open(wav_path, "rb") as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        d = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    d = d.astype(np.float32)
    if ch > 1:
        d = d.reshape(-1, ch).mean(axis=1)
    if d.size == 0:
        return np.zeros(0, dtype=np.float32), sr
    hop = max(1, int(sr * HOP_S))
    n = d.size // hop
    if n < 4:
        return np.zeros(0, dtype=np.float32), sr
    fr = np.abs(d[:n * hop].reshape(n, hop))
    # flux positiu: quant creix l'energia entre fotogrames consecutius
    env = np.diff(fr, axis=1).clip(min=0).sum(axis=1)
    env = env - env.mean()
    # fora el silenci inicial (per sota del 15 % del màxim)
    if env.size:
        llindar = env.max() * 0.15
        idx = np.where(env > llindar)[0]
        if idx.size:
            env = env[idx[0]:]
    return env, sr


def _comb_bpm(env, hop_s=HOP_S, bpm_min=BPM_MIN, bpm_max=BPM_MAX,
              preferit=BPM_PREFERIT):
    """Millor BPM segons una puntuació «comb» sobre l'autocorrelació."""
    if env.size < 8:
        return None
    ac = np.correlate(env, env, "full")[env.size - 1:]
    if ac[0] <= 0:
        return None
    ac = ac / ac[0]

    best = None
    for bpm in np.arange(bpm_min, bpm_max, 0.25):
        lag = (60.0 / bpm) / hop_s
        if lag < 1 or lag >= ac.size:
            continue
        sc = 0.0
        for m in (1, 2, 3, 4):
            L = lag * m
            if L >= ac.size:
                break
            i = int(L)
            f = L - i
            v = ac[i] * (1 - f) + ac[i + 1] * f if i + 1 < ac.size else ac[i]
            sc += v / m
        sc *= _prior(bpm, preferit)
        if best is None or sc > best[0]:
            best = (sc, float(bpm))
    return best[1] if best else None


def detecta_bpm(wav_path, log, bpm_min=BPM_MIN, bpm_max=BPM_MAX,
                preferit=BPM_PREFERIT):
    """Estima el BPM d'una WAV. Retorna float o None si no es pot.

    Pur numpy: no cal cap procés extern ni el plugin d'aubio.
    `bpm_min`/`bpm_max` limiten la cerca; `preferit` premia el rang musical
    habitual (per evitar el doble/meitat). Vegeu el dialeg d'opcions.
    """
    try:
        env, sr = _envolupant_onsets(wav_path)
        bpm = _comb_bpm(env, bpm_min=bpm_min, bpm_max=bpm_max,
                        preferit=preferit)
        if bpm is None:
            log("BPM: senyal massa curt o silenciós")
            return None
        log(f"BPM detectat: {bpm:.1f} (envolupant d'onsets, {sr} Hz)")
        return bpm
    except Exception as e:  # noqa: BLE001
        log(f"BPM: no s'ha pogut detectar ({e})")
        return None
