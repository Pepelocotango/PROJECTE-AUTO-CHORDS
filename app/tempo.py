"""tempo.py — detecció de BPM i mapa de tempo (numpy pur, sense Qt).

Per què no aubio? El seu *beat tracker* s'enganxa de vegades a un pols erroni
(p. ex. una subdivisió) en trossos del tema. Aquí mesurem la **periodicitat
real** de la música a partir de l'**envolupant d'onsets** i una puntuació
«comb»: si un BPM explica bé el senyal, l'autocorrelació tindrà pics forts al
seu període I als seus múltiples (temps, compàs...).

Des del 2026-10-21 hi ha dos nivells:
  1. **BPM puntual** (`detecta_bpm`, `detecta_bpm_candidats`): autocorrelació
     normalitzada + prior + alternatives amb fiabilitat (com Logic).
  2. **Mapa de tempo** (`segueix_beats` + `beats_a_trams`): beat tracking per
     programació dinàmica (Ellis 2007) i un tram de BPM cada N compassos.
     És el que fa servir l'acció «Detecta el tempo per trams» i el que permet
     quadrar cançons amb BPM variable (cada bloc es mesura sol).

Provat amb:
  - "01 101bpm pep live RE-ESTRUCTURA.wav" (9,5 s de silenci inicial) → 101,0
  - "04 PEP LOGIC 118BMP.wav"                                        → 117,8
  - Otis "Dock of the Bay": 103,5 (sencer) / 104,5 (loop 1,98–11,25 s)
"""
import struct
import wave

from app import bpm_unit

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


def _envolupant_onsets(wav_path, inici=0.0, fi=None, retorna_offset=False):
    """Envolupant d'onsets (flux espectral simplificat) a passos de HOP_S.

    `inici`/`fi` (segons) permeten analitzar **només un tros** de la WAV: és
    el que fa servir la detecció de BPM dins d'un tram de tempo. Sense eixos
    arguments, analitza tota la WAV (comportament de sempre).

    Treu el silenci inicial (perquè no diluïsca la periodicitat). Retorna un
    array 1-D (centrat a 0) i el sample rate. Amb `retorna_offset=True`
    retorna també **on comença** l'envolupant (segons des de l'inici del
    fitxer): el beat tracking ho necessita per donar temps absoluts.
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
        if retorna_offset:
            return np.zeros(0, dtype=np.float32), sr, float(inici or 0.0)
        return np.zeros(0, dtype=np.float32), sr
    hop = max(1, int(sr * HOP_S))
    n = d.size // hop
    if n < 4:
        if retorna_offset:
            return np.zeros(0, dtype=np.float32), sr, float(inici or 0.0)
        return np.zeros(0, dtype=np.float32), sr
    fr = np.abs(d[:n * hop].reshape(n, hop))
    # flux positiu: quant creix l'energia entre fotogrames consecutius
    env = np.diff(fr, axis=1).clip(min=0).sum(axis=1)
    env = env - env.mean()
    # fora el silenci inicial (per sota del 15 % del màxim)
    t0 = float(inici or 0.0)
    if env.size:
        llindar = env.max() * 0.15
        idx = np.where(env > llindar)[0]
        if idx.size:
            env = env[idx[0]:]
            t0 += float(idx[0]) * HOP_S
    if retorna_offset:
        return env, sr, t0
    return env, sr


def _autocorrelacio(env):
    """Autocorrelació **normalitzada per la superposició** (N−lag).

    `np.correlate` suma menys mostres a mesura que creix el lag: sense
    normalitzar, els tempos ràpids queden afavorits i les finestres curtes
    ballen molt (en l'intro d'Otis, 4 s donaven 69 BPM i 8 s donaven 52).
    Normalitzar-ho fa que la mateixa música done el mateix valor amb
    finestres de 4 a 9 s (verificat amb clics sintètics de 52–120 BPM).
    """
    n = int(env.size)
    if n < 8:
        return None
    ac = np.correlate(env, env, "full")[n - 1:]
    if ac[0] <= 0:
        return None
    return ac / np.maximum(1.0, n - np.arange(n, dtype=float))


def _punt_comb(ac, bpm, harmonics=(1, 2, 3, 4), hop_s=HOP_S):
    """Puntuació «comb» d'un BPM: pics de l'autocorrelació a 1..4× període.

    Els múltiples són els que fan que un tempo explique el compàs sencer i no
    només la subdivisió (una corxera forta no ha de guanyar el temps).
    """
    lag = (60.0 / float(bpm)) / hop_s
    if lag < 1.0 or lag >= ac.size:
        return 0.0
    sc = 0.0
    for m in harmonics:
        L = lag * m
        if L >= ac.size:
            break
        i = int(L)
        f = L - i
        v = ac[i] * (1.0 - f) + (ac[i + 1] if i + 1 < ac.size else ac[i]) * f
        sc += v / m
    return float(sc)


def _punt_fase_x(x, bpm, phase, hop_s=HOP_S):
    """Suma d'onsets en una graella de beats amb fase `phase` (frames)."""
    n = int(x.size)
    if n < 8:
        return 0.0
    P = (60.0 / float(bpm)) / float(hop_s)
    if P < 2.0:
        return 0.0
    phase = float(phase)
    if phase < 0.0 or phase >= P:
        phase = phase % P
    k = np.arange(0, max(0, int((n - 1 - phase) / P) + 1), dtype=float)
    idx = phase + k * P
    if idx.size == 0:
        return 0.0
    return float(np.interp(idx, np.arange(n, dtype=float), x,
                           left=0.0, right=0.0).sum())


def _millor_fase_x(x, bpm, pas_fase_s=0.01, hop_s=HOP_S):
    """Millor fase (en frames) per a un BPM, amb pas temporal configurable."""
    P = (60.0 / float(bpm)) / float(hop_s)
    if P < 2.0:
        return 0.0, 0.0
    pas = max(0.2, float(pas_fase_s) / float(hop_s))
    millor = -1.0
    fase_bona = 0.0
    for phase in np.arange(0.0, P, pas):
        sc = _punt_fase_x(x, bpm, phase, hop_s=hop_s)
        if sc > millor:
            millor = sc
            fase_bona = float(phase)
    return millor, fase_bona


def _refina_bpm_fase(env, bpm, hop_s=HOP_S, radi=0.75):
    """Refina un candidat amb cerca fina de BPM i fase.

    La cerca grossera de candidats treballa amb una graella de 0,1–0,25 BPM.
    Ací es corregix eixe biaix provant BPM i fase contra els onsets reals del
    cos. Retorna `(bpm, puntuacio)`.
    """
    x = np.maximum(np.asarray(env, dtype=float), 0.0)
    bpm = float(bpm)
    if bpm <= 0 or x.size < 8:
        return bpm, 0.0
    lo = max(1.0, bpm - float(radi))
    hi = bpm + float(radi)
    millor = (-1.0, bpm, 0.0)
    for b in np.arange(lo, hi + 1e-9, 0.1):
        sc, ph = _millor_fase_x(x, b, pas_fase_s=0.01, hop_s=hop_s)
        if sc > millor[0]:
            millor = (sc, float(b), ph)
    # Segona passada fina al voltant del millor BPM.
    b0 = millor[1]
    for b in np.arange(max(1.0, b0 - 0.1), b0 + 0.1 + 1e-9, 0.005):
        sc, ph = _millor_fase_x(x, b, pas_fase_s=0.005, hop_s=hop_s)
        if sc > millor[0]:
            millor = (sc, float(b), ph)
    return millor[1], millor[0]


def _hipotesis_bpm(env, bpm_min, bpm_max, preferit, n=5):
    """Candidats amplis, amb família meitat/doble, sense decidir encara."""
    bpm_min = float(bpm_min or BPM_MIN)
    bpm_max = float(bpm_max or BPM_MAX)
    if bpm_max <= bpm_min:
        bpm_max = bpm_min + 1.0
    base = []
    for pref in (preferit, None):
        for b, _c in candidats_bpm(env, bpm_min, bpm_max, pref,
                                   n=max(3, int(n)), pas=0.1):
            base.append(float(b))
    hip = []
    for b in base:
        for factor in (1.0, 0.5, 2.0):
            v = b * factor
            if bpm_min - 1e-9 <= v <= bpm_max + 1e-9:
                if not any(abs(v - u) / u <= 0.02 for u in hip):
                    hip.append(v)
    return hip[:max(4, int(n) * 2)]


def _candidats_fase(env, bpm_min, bpm_max, preferit, n=3, hop_s=HOP_S):
    """Candidats refinats per fase, amb confiança relativa."""
    hip = _hipotesis_bpm(env, bpm_min, bpm_max, preferit, n=max(3, n * 2))
    # Per a la decisió escalar només calen els dos millors; per a les
    # alternatives es refinen uns quants més.
    hip = hip[:max(2, int(n) + 1)]
    vals = []
    for b in hip:
        b2, sc = _refina_bpm_fase(env, b, hop_s=hop_s)
        if b2 > 0 and sc > 0:
            vals.append((b2, sc))
    if not vals:
        return []
    vals.sort(key=lambda x: -x[1])
    top = vals[0][1]
    out = []
    for b, sc in vals:
        if any(abs(b - u) / u <= 0.02 for u, _s in out):
            continue
        out.append((b, sc / top))
        if len(out) >= int(n):
            break
    return out


def _millor_bpm_fase(env, bpm_min=BPM_MIN, bpm_max=BPM_MAX,
                     preferit=BPM_PREFERIT, hop_s=HOP_S):
    """Millor BPM després de refinar per fase (API interna)."""
    cands = _candidats_fase(env, bpm_min, bpm_max, preferit, n=1,
                            hop_s=hop_s)
    return cands[0][0] if cands else None


def candidats_bpm(env, bpm_min=BPM_MIN, bpm_max=BPM_MAX,
                  preferit=BPM_PREFERIT, n=3, hop_s=HOP_S, pas=0.1):
    """Els `n` millors BPM d'una envolupant, amb **fiabilitat** 0..1.

    Retorna `[(bpm, fiabilitat), …]` de millor a pitjor. La fiabilitat és la
    puntuació relativa a la guanyadora (1.0 = la millor) i serveix per a
    ensenyar alternatives a l'usuari (com fa Logic amb les seues 5
    propostes). Es descarten candidats a menys d'un 2 % (seria el mateix
    tempo, no una alternativa).
    """
    ac = _autocorrelacio(env)
    if ac is None:
        return []
    bpm_min = float(bpm_min or BPM_MIN)
    bpm_max = float(bpm_max or BPM_MAX)
    if bpm_max <= bpm_min:
        bpm_max = bpm_min + 1.0
    vals = []
    for bpm in np.arange(bpm_min, bpm_max + 1e-9, float(pas)):
        sc = _punt_comb(ac, bpm, hop_s=hop_s) * _prior(bpm, preferit)
        if sc > 0:
            vals.append((float(bpm), float(sc)))
    if not vals:
        return []
    vals.sort(key=lambda x: -x[1])
    top = vals[0][1]
    out = []
    for bpm, sc in vals:
        if any(abs(bpm - b) / b <= 0.02 for b, _c in out):
            continue
        out.append((bpm, sc / top))
        if len(out) >= int(n):
            break
    return out


def detecta_bpm_candidats(wav_path, log=None, bpm_min=BPM_MIN,
                          bpm_max=BPM_MAX, preferit=BPM_PREFERIT,
                          inici=0.0, fi=None, n=3, amplia=True):
    """Detecció amb **alternatives**: guanyadora, candidates i fora de rang.

    Retorna un diccionari::

        {"bpm": 103.5 | None,
         "candidats": [(bpm, fiabilitat), …],       # dins del rang demanat
         "alternatives": [(bpm, fiabilitat), …]}    # rang ampli 40–240

    `alternatives` serveix per a avisar quan el rang configurat (p. ex.
    50–100) està forçant la meitat o el doble del tempo real: es torna a
    puntuar amb el **mateix prior** i un rang ampli, i es mostren els valors
    que queden fora del rang demanat.
    """
    log = log or (lambda *a: None)
    res = {"bpm": None, "candidats": [], "alternatives": []}
    try:
        env, _sr = _envolupant_onsets(wav_path, inici=inici, fi=fi)
    except Exception as e:  # noqa: BLE001
        log(f"BPM: no s'ha pogut llegir el senyal ({e})")
        return res
    if env.size < 8:
        log("BPM: senyal massa curt o silenciós")
        return res
    cands = _candidats_fase(env, bpm_min, bpm_max, preferit, n=n)
    if not cands:
        log("BPM: no s'ha trobat cap periodicitat clara")
        return res
    res["candidats"] = cands
    res["bpm"] = cands[0][0]
    if amplia:
        ample = candidats_bpm(env, min(40.0, float(bpm_min or 40.0)),
                              max(240.0, float(bpm_max or 240.0)),
                              preferit, n=max(3, int(n) + 2))
        lo = float(bpm_min or BPM_MIN)
        hi = float(bpm_max or BPM_MAX)
        res["alternatives"] = [(b, c) for b, c in ample
                               if not (lo - 1e-9 <= b <= hi + 1e-9)
                               and c >= 0.5 * cands[0][1]]
    log(f"BPM detectat: {res['bpm']:.2f} "
        f"(fiabilitat {cands[0][1]:.2f}; "
        f"altres dins del rang: "
        f"{', '.join(f'{b:.1f}' for b, _c in cands[1:]) or 'cap'}; "
        f"fora del rang: "
        f"{', '.join(f'{b:.1f}' for b, _c in res['alternatives']) or 'cap'})")
    return res


def _comb_bpm(env, hop_s=HOP_S, bpm_min=BPM_MIN, bpm_max=BPM_MAX,
              preferit=BPM_PREFERIT, pas=0.25):
    """Millor BPM (API de sempre): delega en `candidats_bpm`."""
    c = candidats_bpm(env, bpm_min, bpm_max, preferit, n=1, hop_s=hop_s,
                      pas=pas)
    return c[0][0] if c else None


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
        bpm = _millor_bpm_fase(env, bpm_min=bpm_min, bpm_max=bpm_max,
                               preferit=preferit)
        if bpm is None:
            log("BPM: senyal massa curt o silenciós")
            return None
        # El refinament pot donar 144,725; el valor nominal que es mostra i
        # s'aplica és 144,7. Els detalls queden a `detecta_bpm_candidats`.
        bpm = round(float(bpm), 1)
        log(f"BPM detectat: {bpm:.1f} (envolupant d'onsets, {sr} Hz, "
            f"{float(inici):.3f}–{float(fi) if fi is not None else 'fi'} s)")
        return bpm
    except Exception as e:  # noqa: BLE001
        log(f"BPM: no s'ha pogut detectar ({e})")
        return None


# --- mapa de tempo per trams (beat tracking + blocs de compassos) ----------

def _suavitza(env, period_s, hop_s=HOP_S):
    """Suavitza l'envolupant amb una gaussiana d'ample `period_s/32` (Ellis)."""
    sigma = max(1.0, (float(period_s) / 32.0) / float(hop_s))
    radi = max(1, int(round(3.0 * sigma)))
    x = np.arange(-radi, radi + 1) / sigma
    k = np.exp(-0.5 * x * x)
    s = k.sum()
    if s <= 0:
        return np.asarray(env, dtype=float)
    return np.convolve(np.asarray(env, dtype=float), k / s, mode="same")


def _dp_beats(localscore, period_s, tightness=100.0, hop_s=HOP_S):
    """Índexs dels beats segons la programació dinàmica d'Ellis (2007).

    Es maximitza la suma de la corba d'onsets als beats amb una penalització
    per desviar-se del període: `tightness * log(lag/P)^2`. Amb
    `tightness` baix (30) el tempo pot **derivar** (cançons amb BPM variable);
    amb 100 s'hi enganxa fort (com fa librosa per defecte).
    """
    ls = np.asarray(localscore, dtype=float)
    n = int(ls.size)
    P = float(period_s) / float(hop_s)
    if n < 8 or P < 2.0:
        return np.zeros(0, dtype=int)
    # escala la corba perquè la penalització (tightness) compte igual en
    # qualsevol cançó: si no, l'envolupant crua ofega el prior i el DP pot
    # saltar a la meitat o al doble del tempo (vist a Otis: 304 beats a 154).
    sd = float(ls.std())
    if sd > 0:
        ls = (ls - ls.mean()) / sd
    lo = max(1, int(round(0.5 * P)))
    hi = max(lo + 1, int(round(2.0 * P)))
    hi = min(hi, n - 1)
    if hi <= lo:
        return np.zeros(0, dtype=int)
    lags = np.arange(lo, hi + 1, dtype=float)
    pen = float(tightness) * np.log(lags / P) ** 2
    cum = np.full(n, -np.inf)
    back = np.full(n, -1, dtype=int)
    for t in range(n):
        if t >= lo:
            u = t - lags.astype(int)
            ok = u >= 0
            if ok.any():
                vals = cum[u[ok]] - pen[ok]
                k = int(np.argmax(vals))
                if np.isfinite(vals[k]):
                    cum[t] = ls[t] + vals[k]
                    back[t] = t - int(lags[ok][k])
                    continue
        cum[t] = ls[t]
    cua = max(1, int(round(2.0 * P)))
    fi = int(np.argmax(cum[-cua:]) + (n - cua)) if n > cua else int(np.argmax(cum))
    idx = []
    t = fi
    while t >= 0:
        idx.append(int(t))
        t = int(back[t])
    idx.reverse()
    return np.asarray(idx, dtype=int)


def segueix_beats(wav_path, log=None, bpm=None, inici=0.0, fi=None,
                  bpm_min=BPM_MIN, bpm_max=BPM_MAX, preferit=BPM_PREFERIT,
                  tightness=30.0):
    """Segueix els beats d'una WAV o d'un tros. Retorna `(beats_s, bpm_base)`.

    `bpm` (opcional) fixa el període inicial; si no es dona, es detecta amb
    `candidats_bpm`. Els temps tornen **en segons absoluts** del fitxer.
    """
    log = log or (lambda *a: None)
    try:
        env, _sr, t0 = _envolupant_onsets(wav_path, inici=inici, fi=fi,
                                         retorna_offset=True)
    except Exception as e:  # noqa: BLE001
        log(f"beats: no s'ha pogut llegir el senyal ({e})")
        return [], None
    if env.size < 16:
        log("beats: senyal massa curt o silenciós")
        return [], None
    base = float(bpm) if bpm else None
    if not base:
        c = _candidats_fase(env, bpm_min, bpm_max, preferit, n=1)
        base = round(float(c[0][0]), 1) if c else None
    if not base:
        log("beats: no s'ha trobat cap periodicitat clara")
        return [], None
    period = 60.0 / base
    ls = _suavitza(env, period)
    idx = _dp_beats(ls, period, tightness=tightness)
    if idx.size < 2:
        log(f"beats: seguiment fallit (bpm base {base:.1f})")
        return [], base
    beats = [round(float(t0) + float(i) * HOP_S, 6) for i in idx]
    log(f"beats: {len(beats)} temps seguits (bpm base {base:.2f}, "
        f"tightness {tightness:g}, inici {t0:.3f} s)")
    return beats, base


def _ibi_mediana(beats):
    """Interval entre beats típic (mediana; ignora forats d'un beat perdut)."""
    d = np.diff(np.asarray(beats, dtype=float))
    if d.size == 0:
        return 0.0
    med = float(np.median(d))
    if med <= 0:
        return 0.0
    bona = d[(d > 0.6 * med) & (d < 1.6 * med)]
    return float(np.median(bona)) if bona.size else med


def beats_a_trams(beats, durada, num=4, den=4, cada_compassos=4,
                  tolerancia=0.01, offset=None, beat_unit=None):
    """Mapa de tempo per blocs de compassos a partir dels beats seguits.

    Contracte de la graella: **cada tram ha de contindre un nombre enter de
    compassos** i les fronteres han de caure en una línia de compàs
    (`tempo_map.valida_i_normalitza_compassos`). Per això el BPM de cada tram
    es **deriva** de la seua pròpia durada (`bq * 60 * m / (fi - base)`): la
    frontera queda exactament damunt d'una línia de compàs encara que la
    cançó derive. El tram inicial pot ser parcial des de 0 fins a `offset`
    (compte enrere), que és l'única excepció permesa al començament.

    `beat_unit` és la figura que segueix el detector (negra, negra amb punt,
    corxera…). Si no es passa, s'usa la unitat per defecte del compàs. Això
    evita assumir que tot beat detectat és una negra.
    Retorna `(trams, offset)`, amb `offset` = primer beat seguit. Els veïns
    amb BPM a menys de `tolerancia` (fracció) es fusionen.
    """
    durada = float(durada or 0.0)
    bq = float(num) * 4.0 / float(den or 4)
    unit = bpm_unit.normalitza(
        beat_unit or bpm_unit.unitat_per_defecte(num, den, ""))
    q_per_beat = bpm_unit.factor(unit)
    beats_per_bar = (bq / q_per_beat) if q_per_beat > 0 else bq
    ts = sorted({round(float(t), 6) for t in (beats or ())
                 if 0.0 <= float(t) < durada - 1e-6})
    if len(ts) < 4 or durada <= 0 or bq <= 0:
        return [], 0.0
    # `offset=None` = el compàs 1 cau al primer beat seguit (recomanat);
    # `offset=0` = la graella arrenca a 0 i la pickup s'absorbix al 1r tram.
    offset = float(ts[0]) if offset is None else float(offset)
    # Els beats detectats no sempre són negres: poden ser blanques, negres
    # amb punt o corxeres. Triem el primer nombre de compassos >= `cada` que
    # done un nombre enter de beats, perquè `pas` siga un índex vàlid.
    cada = max(1, int(cada_compassos))
    bars = cada
    for _ in range(32):
        if abs(bars * beats_per_bar - round(bars * beats_per_bar)) <= 1e-9:
            break
        bars += 1
    pas = max(1, int(round(bars * beats_per_bar)))
    blocs = []                                   # (ini, fi, compassos, base)
    i = 0
    # Només blocs **sencers** de `pas` beats: la resta final no es mesura a
    # banda (no sabem si és un canvi de tempo o només la cua) i s'annexa a
    # l'últim tram conservant el seu BPM.
    while i + pas <= len(ts) - 1:
        ini = ts[i] if i > 0 else 0.0
        base = ts[i] if i > 0 else offset        # rellotge de les línies
        fi = ts[i + pas]
        ibi = _ibi_mediana(ts[i:i + pas + 1])
        if ibi <= 0 or fi - base <= 0:
            i += pas
            continue
        m = max(1, int(round((fi - base) / (beats_per_bar * ibi))))
        blocs.append((ini, fi, m, base))
        i += pas
    if not blocs:
        ibi = _ibi_mediana(ts)
        if ibi <= 0:
            return [], offset
        return [(0.0, durada, (60.0 / ibi) * q_per_beat,
                 int(num), int(den))], offset
    # fusió de veïns amb BPM quasi igual (recalculant el total de compassos)
    out = []
    for ini, fi, m, base in blocs:
        if out:
            p_ini, p_fi, p_m, p_base = out[-1]
            bpm_p = bq * 60.0 * p_m / (p_fi - p_base)
            bpm_n = bq * 60.0 * m / (fi - base)
            if bpm_p > 0 and abs(bpm_n - bpm_p) / bpm_p <= float(tolerancia):
                out[-1] = (p_ini, fi, p_m + m, p_base)
                continue
        out.append((ini, fi, m, base))
    trams = [(ini, fi, bq * 60.0 * m / (fi - base), int(num), int(den))
             for ini, fi, m, base in out]
    # L'últim tram és l'únic que pot quedar parcial: s'allarga fins al final
    # conservant el SEU tempo (no s'inventa un BPM per a la cua).
    if trams:
        ini, _fi, bpm, n_, d_ = trams[-1]
        if durada - ini > 1e-6:
            trams[-1] = (ini, durada, bpm, n_, d_)
    return trams, offset


def mapa_tempo_automatic(wav_path, log=None, durada=None, num=4, den=4,
                         cada_compassos=4, tolerancia=0.01,
                         bpm_min=BPM_MIN, bpm_max=BPM_MAX,
                         preferit=BPM_PREFERIT, tightness=30.0, bpm=None,
                         offset=None, beat_unit=None):
    """Motor complet del mapa de tempo: BPM base → beats → trams.

    Retorna `(trams, offset, bpm_base)`; `([], 0.0, None)` si no ha pogut.
    """
    log = log or (lambda *a: None)
    beats, base = segueix_beats(wav_path, log, bpm=bpm, bpm_min=bpm_min,
                                bpm_max=bpm_max, preferit=preferit,
                                tightness=tightness)
    if not beats:
        return [], 0.0, base
    if durada is None:
        durada = beats[-1] + 0.5
    trams, offset = beats_a_trams(beats, durada, num=num, den=den,
                                  cada_compassos=cada_compassos,
                                  tolerancia=tolerancia, offset=offset,
                                  beat_unit=beat_unit)
    log(f"mapa: {len(trams)} tram(s) de tempo, offset {offset:.3f} s")
    return trams, offset, base


# --- pistes de tempo dels metadades (ACID / nom de fitxer) -----------------

def _riff_chunks(f, limit=1 << 22):
    """Recorre els chunks RIFF d'una WAV oberta (`(id, offset, size)`)."""
    f.seek(12)
    while True:
        off = f.tell()
        cap = f.read(8)
        if len(cap) < 8 or off > limit:
            return
        cid, size = cap[:4], struct.unpack("<I", cap[4:])[0]
        yield cid, off + 8, size
        f.seek(off + 8 + size + (size & 1))


def llegeix_pistes_tempo(wav_path):
    """BPM «declarat» pel fitxer: chunk ACID o el nom (`103bpm`).

    Retorna `[(bpm, origen), …]` (origen `"acid"` o `"nom"`). És només una
    **pista**: el detector la fa servir com a referència, no com a veritat.
    """
    out = []
    try:
        with open(wav_path, "rb") as f:
            if f.read(4) == b"RIFF":
                f.seek(0)
                for cid, off, size in _riff_chunks(f):
                    if cid == b"acid" and size >= 24:
                        f.seek(off)
                        d = f.read(size)
                        if len(d) >= 20:
                            bpm = struct.unpack("<f", d[16:20])[0]
                            if 20.0 <= bpm <= 300.0:
                                out.append((round(float(bpm), 4), "acid"))
    except Exception:  # noqa: BLE001
        pass
    import os
    import re
    m = re.search(r"(?i)(\d{2,3}(?:[.,]\d+)?)\s*bpm", os.path.basename(
        str(wav_path)))
    if m:
        try:
            bpm = float(m.group(1).replace(",", "."))
            if 20.0 <= bpm <= 300.0:
                out.append((round(bpm, 4), "nom"))
        except ValueError:
            pass
    return out
