"""metronom.py — generador de clics de metrònom (numpy pur, sense Qt).

Els clics es MESCLEN al buffer d'àudio que s'envia al reproductor, en comptes
de fer servir un segon reproductor o un QTimer (que derivaria respecte a la
cançó). Veure `app/visor.py` (_engega_des_de / _mono_bytes).

La graella és la MATEIXA que la del regle del visor: el beat és el que defineix
el **denominador** del compàs (`4/den` negres) i el compàs té `num` beats. Així
`4/4` clica negres, `6/8` i `12/8` cliquen corxeres, i `2/2` clica blanques.
"""
import numpy as np
from app import limits

# El metrònom rebutja els valors fora de la banda d'edició compartida.
BPM_MAX = limits.BPM_MAX

# Patrons de clic. `auto` = tots els temps + accents de compàs i grup.
MODES = ("auto", "compas", "temps", "grup")

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


def _es_valid(bpm, bpb, den=4):
    """BPM ha de ser finit i dins la banda; bpb < 1 es tracta com a 1."""
    try:
        if not np.isfinite(bpm) or not limits.BPM_MIN <= bpm <= BPM_MAX:
            return None
    except TypeError:
        return None
    try:
        den = int(den)
    except (TypeError, ValueError):
        den = 4
    if den not in limits.DENOMINADORS_ADMESOS:
        den = 4
    return max(1, int(bpb)), den


def _normalitza_mode(mode):
    """Retorna un mode vàlid; qualsevol valor estrany cau a `auto`."""
    return mode if mode in MODES else "auto"


def _es_compost(num, den):
    """`6/8`, `9/8` i `12/8` tenen grups de 3 corxeres.

    Els compassos de denominador 8 amb numerador múltiple de 3 (excepte 3/8,
    que només té un grup) reben accent secundari cada 3 beats.
    """
    return int(den) == 8 and int(num) >= 6 and int(num) % 3 == 0


def _accent_grup(beat, num, den):
    """True si `beat` (1-based) és l'inici d'un grup compost."""
    return (_es_compost(num, den) and beat > 1
            and (beat - 1) % 3 == 0)


def _ha_de_sonar(mode, beat, num, den):
    """Decideix si hi ha clic en este beat segons el patró."""
    mode = _normalitza_mode(mode)
    if mode == "compas":
        return beat == 1
    if mode == "grup":
        return beat == 1 or _accent_grup(beat, num, den)
    # `auto` i `temps`: tots els temps.
    return True


def _es_accent(mode, beat, num, den):
    """True per al clic fort (compàs) o per a l'accent secundari de grup."""
    mode = _normalitza_mode(mode)
    if beat == 1:
        return True
    return mode in ("auto", "grup") and _accent_grup(beat, num, den)


def beats_a_temps(k, bpm, offset=0.0, den=4):
    """Temps (s) del beat global `k` segons la graella.

    `den` és el denominador del compàs; per defecte 4 (negra), que és la unitat
    de BPM de l'app. Amb den=8, cada beat és una corxera.
    """
    beat_len = (4.0 / float(den)) * 60.0 / float(bpm)
    return k * beat_len + float(offset)


def mescla_metronom(mono_bytes, sr, t_inici, bpm, bpb,
                    volum=0.6, offset=0.0, mapa=None, factor=1.0,
                    den=4, mode="auto"):
    """Mescla els clics a la rodanxa `mono_bytes` (int16 mono, a partir de
    `t_inici` segons de la cançó) i retorna els bytes int16 resultants.

    - `bpb` és el **numerador** del compàs i `den` el **denominador**. El beat
      fa `(4/den) * 60/bpm` segons; per això `12/8` clica 12 corxeres, no 12
      negres.
    - `mode`: `auto` (tots els temps + accents de compàs i grup), `compas`
      (només el primer temps), `temps` (tots els temps, sense accents de grup)
      o `grup` (només compàs i inicis de grup en compassos compostos).
    - Només genera els clics que cauen dins la rodanxa (funciona des de
      qualsevol posició i amb el loop A/B).
    - Suma en float32 i fa clip a int16 per evitar desbordament.
    - volum 0 (o BPM invàlid) → retorna l'àudio sense canvis.
    - `factor` = velocitat de reproducció del visor (0,5–3×, to mantingut):
      la rodanxa cobreix `factor` cops més de cançó per segon real, així que
      els clics s'han de col·locar dividint per `factor` (si no, amb 2× el
      metrònom aniria a la meitat del tempo que sona). A 1,0× és idèntic.
    """
    valid = _es_valid(bpm, bpb, den)
    if valid is None or volum <= 0:
        return mono_bytes
    _bpb, _den = valid
    mode = _normalitza_mode(mode)
    try:
        factor = float(factor)
    except (TypeError, ValueError):
        factor = 1.0
    if not np.isfinite(factor) or factor <= 0:
        factor = 1.0

    buf = np.frombuffer(mono_bytes, dtype=np.int16).astype(np.float32)
    if buf.size == 0:
        return mono_bytes
    sr = float(sr)
    # Durada de la rodanxa en SEGONS DE CANÇÓ (a `factor`× n'hi cap més).
    dur = buf.size / sr * factor
    beat_len = (4.0 / float(_den)) * 60.0 / float(bpm)

    # genera_clic() retorna ±1 normalitzat: cal escalar-lo a la gamma int16
    guany = 32767.0 * float(volum)
    clic_accent = genera_clic(sr, True) * guany
    clic_normal = genera_clic(sr, False) * guany

    def _posa(t_b, accent):
        i = int(round(t_b / factor * sr))
        clic = clic_accent if accent else clic_normal
        n = min(clic.size, buf.size - i)
        if n > 0:
            buf[i:i + n] += clic[:n]

    # ── Amb un mapa de tempo/compàs VARIABLE (regla d'or #5: el mapa és la
    # font), els clics van als TEMPS DEL MAPA. Recorrem la graella a resolució
    # de corxera (0,5 negres) i filtrem els punts que són inici de beat; així
    # funciona amb qualsevol denominador 2/4/8, canvis de compàs i rubato.
    if mapa is not None and not mapa.es_constant():
        q = float(mapa.quarters(float(t_inici)))
        # Comença una mica abans per no perdre el beat que conté `t_inici`.
        q = float(np.floor(q * 2.0) / 2.0 - 1.0)
        while True:
            t_abs = float(mapa.t_de_quarters(q))
            t_b = t_abs - float(t_inici)
            if t_b >= dur:
                break
            if t_b >= 0.0:
                _c, b, s = mapa.pos(t_abs)
                if s == 1:
                    num_m, den_m = mapa.signatura(t_abs)
                    b = max(1, int(b))
                    if _ha_de_sonar(mode, b, num_m, den_m):
                        _posa(t_b, _es_accent(mode, b, num_m, den_m))
            q += 0.5
        np.clip(buf, -32768.0, 32767.0, out=buf)
        return buf.astype(np.int16).tobytes()

    # Primer beat amb temps >= t_inici, pero mai abans de t=0 de la canco:
    # aixi el SILENCI INICIAL tambe s'omple amb el compte enrere (count-in).
    k0 = int(np.ceil((t_inici - offset) / beat_len))
    k_min = int(np.ceil((0.0 - offset) / beat_len))
    if k0 < k_min:
        k0 = k_min
    k = k0
    while True:
        t_b = beats_a_temps(k, bpm, offset, _den) - float(t_inici)
        if t_b >= dur:
            break
        if t_b >= 0.0:
            beat = (k % _bpb) + 1
            if _ha_de_sonar(mode, beat, _bpb, _den):
                _posa(t_b, _es_accent(mode, beat, _bpb, _den))
        k += 1

    np.clip(buf, -32768.0, 32767.0, out=buf)
    return buf.astype(np.int16).tobytes()
