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
BPM_PREFERIT = (85.0, 150.0)
PRIOR_SIGMA = 0.5     # amplada de la caiguda fora del plateau, en octaves
HOP_S = 0.01          # resolució temporal de l'envolupant (10 ms)


def _prior(bpm, preferit=BPM_PREFERIT):
    """Pes suau cap a la zona «còmoda» de tempo (plateau + caiguda log2).

    Dins `preferit` val 1,0; fora cau com una gaussiana en escala logarítmica
    (octaves). Això descarta el doble/subdivisió extrems sense imposar un pic
    (que trencaria temes lents genuïns, com el de 70 BPM).

    Valors triats amb 11 temes reals (rang 70-138 BPM + casos difícils):
    85-150 amb sigma 0,5 encerta tots els coneguts (101/138/70/117,8/107/
    103,5-Otis/132-Chemical) i només mou els genuïnament ambigus.
    """
    if not preferit:
        return 1.0
    lo, hi = preferit
    if lo <= bpm <= hi:
        return 1.0
    x = np.log2(lo / bpm) if bpm < lo else np.log2(bpm / hi)
    return float(np.exp(-0.5 * (x / PRIOR_SIGMA) ** 2))


def _envolupant_onsets(wav_path, inici=0.0, fi=None):
    """Envolupant d'onsets (flux espectral simplificat) a passos de HOP_S.

    `inici`/`fi` (segons) permeten analitzar **només un tros** de la WAV: és
    el que fa servir la detecció de BPM dins d'un tram de tempo. Sense eixos
    arguments, analitza tota la WAV (comportament de sempre).

    Treu el silenci inicial (perquè no diluïsca la periodicitat). Retorna un
    array 1-D (centrat a 0) i el sample rate.
    """
    with wave.open(wav_path, "rb") as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        nframes = w.getnframes()
        i0 = max(0, min(nframes, int(round(float(inici or 0.0) * sr))))
        i1 = nframes if fi is None else max(
            i0, min(nframes, int(round(float(fi) * sr))))
        w.setpos(i0)
        d = np.frombuffer(w.readframes(i1 - i0), dtype=np.int16)
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
                preferit=BPM_PREFERIT, inici=0.0, fi=None):
    """Estima el BPM d'una WAV (o d'un tros) amb numpy pur.

    `inici`/`fi` limiten l'anàlisi a un interval en segons (detecció dins d'un
    tram de tempo). Sense ells, analitza tota la WAV.
    `bpm_min`/`bpm_max` limiten la cerca; `preferit` premia el rang musical
    habitual (per evitar el doble/meitat). Vegeu el dialeg d'opcions.
    """
    try:
        env, sr = _envolupant_onsets(wav_path, inici=inici, fi=fi)
        bpm = _comb_bpm(env, bpm_min=bpm_min, bpm_max=bpm_max,
                        preferit=preferit)
        if bpm is None:
            log("BPM: senyal massa curt o silenciós")
            return None
        log(f"BPM detectat: {bpm:.1f} (envolupant d'onsets, {sr} Hz, "
            f"{float(inici):.3f}–{float(fi) if fi is not None else 'fi'} s)")
        return bpm
    except Exception as e:  # noqa: BLE001
        log(f"BPM: no s'ha pogut detectar ({e})")
        return None
