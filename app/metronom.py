"""metronom.py — generador de clics de metrònom (numpy pur, sense Qt).

Els clics es MESCLEN al buffer d'àudio que s'envia al reproductor, en comptes
de fer servir un segon reproductor o un QTimer (que derivaria respecte a la
cançó). Veure `app/visor.py` (_engega_des_de / _mono_bytes).

La graella és la MATEIXA que la del regle del visor: el beat és el que defineix
el **denominador** del compàs (`4/den` negres) i el compàs té `num` beats. Així
`4/4` clica negres, `6/8` i `12/8` cliquen corxeres, i `2/2` clica blanques.
Els accents de grup ixen de `tempo_map.agrupacio_compas()`: `6/8` → `3+3`,
`7/8` → `2+2+3`, `5/8` → `3+2`, etc.
"""
import numpy as np
from app import bpm_unit, limits, tempo_map

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


def _click_quarters(click_unit, den):
    """Negres que fa una unitat de clic (`auto` = denominador del compàs)."""
    if click_unit in (None, "", "auto"):
        return 4.0 / float(den)
    return bpm_unit.factor(click_unit)


def _normalitza_click_unit(click_unit):
    return (click_unit if click_unit in ("auto",) or click_unit in bpm_unit.UNITATS
            else "auto")


def _inicis_grups(num, den, agrupacio=None):
    """Inicis de grup (unitats de denominador) per a una agrupació concreta."""
    agr = agrupacio or tempo_map.agrupacio_compas(num, den)
    out = []
    q = 0
    for mida in agr:
        out.append(q)
        q += int(mida)
    return tuple(out)


def _grups_alineats(click_unit, num, den, agrupacio=None):
    """True si la unitat de clic cau damunt dels inicis de grup."""
    pas = _click_quarters(click_unit, den) / _beat_quarters(den)
    if pas <= 0:
        return False
    return all(abs(inici / pas - round(inici / pas)) <= 1e-9
               for inici in _inicis_grups(num, den, agrupacio))


def _normalitza_mode(mode):
    """Retorna un mode vàlid; qualsevol valor estrany cau a `auto`."""
    return mode if mode in MODES else "auto"


def _beat_quarters(den):
    """Negres que fa un temps de denominador `den` (4→1, 8→0.5)."""
    return 4.0 / float(den)


def _accent_grup(beat, num, den, agrupacio=None):
    """True si `beat` (1-based) és l'inici d'un grup (no el compàs)."""
    return (int(beat) > 1
            and (int(beat) - 1) in _inicis_grups(num, den, agrupacio))


def mescla_metronom(mono_bytes, sr, t_inici, bpm, bpb,
                    volum=0.6, offset=0.0, mapa=None, factor=1.0,
                    den=4, mode="auto", click_unit="auto"):
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
    click_unit = _normalitza_click_unit(click_unit)
    if click_unit != "auto":
        signatures = [(_bpb, _den)]
        if mapa is not None:
            signatures = [(int(t.num_ef), int(t.den_ef))
                          for t in mapa.trams
                          if int(t.num_ef) > 0 and int(t.den_ef) > 0]
        if not signatures or not all(
                bpm_unit.encaixa_en_compas(click_unit, n, d)
                for n, d in signatures):
            click_unit = "auto"
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
    click_len = _click_quarters(click_unit, _den) * 60.0 / float(bpm)
    bar_q = float(_bpb) * 4.0 / float(_den)
    beat_q = _beat_quarters(_den)
    starts_q = [inici * beat_q
                for inici in tempo_map.inicis_grups(_bpb, _den)]

    def _decideix(es_bar, es_grup, grup_auto):
        """Retorna `(hi_ha_clic, es_accent)` per al patró triat."""
        if mode == "compas":
            return es_bar, es_bar
        if mode == "grup":
            valor = bool(es_bar or es_grup)
            return valor, valor
        if mode == "temps":
            return True, bool(es_bar)
        return True, bool(es_bar or (grup_auto and es_grup))

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
    if mapa is not None and (not mapa.es_constant()
                             or mapa.te_agrupacions_explicites()):
        q = float(mapa.quarters(float(t_inici)))
        if click_unit == "auto":
            # Graella del denominador: hi ha clic a cada beat (s == 1).
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
                        agr_m = mapa.agrupacio(t_abs)
                        b = max(1, int(b))
                        es_bar = (b == 1)
                        es_grup = _accent_grup(b, num_m, den_m, agr_m)
                        clica, accent = _decideix(
                            es_bar, es_grup,
                            _grups_alineats(click_unit, num_m, den_m, agr_m))
                        if clica:
                            _posa(t_b, accent)
                q += 0.5
        else:
            paso = _click_quarters(click_unit, _den)
            q = float(np.floor(q / paso) * paso - paso)
            while True:
                t_abs = float(mapa.t_de_quarters(q))
                t_b = t_abs - float(t_inici)
                if t_b >= dur:
                    break
                if t_b >= 0.0:
                    _c, b, s = mapa.pos(t_abs)
                    num_m, den_m = mapa.signatura(t_abs)
                    agr_m = mapa.agrupacio(t_abs)
                    b = max(1, int(b))
                    es_bar = (b == 1 and s == 1)
                    es_grup = _accent_grup(b, num_m, den_m, agr_m)
                    clica, accent = _decideix(
                        es_bar, es_grup,
                        _grups_alineats(click_unit, num_m, den_m, agr_m))
                    if clica:
                        _posa(t_b, accent)
                q += paso
        np.clip(buf, -32768.0, 32767.0, out=buf)
        return buf.astype(np.int16).tobytes()

    # Primer clic amb temps >= t_inici, pero mai abans de t=0 de la canco:
    # aixi el SILENCI INICIAL tambe s'omple amb el compte enrere (count-in).
    k0 = int(np.ceil((t_inici - offset) / click_len))
    k_min = int(np.ceil((0.0 - offset) / click_len))
    if k0 < k_min:
        k0 = k_min
    k = k0
    while True:
        t_b = k * click_len + float(offset) - float(t_inici)
        if t_b >= dur:
            break
        if t_b >= 0.0:
            pos_q = (k * click_len) * float(bpm) / 60.0
            in_bar = pos_q % bar_q
            es_bar = abs(in_bar) < 1e-6
            es_grup = (not es_bar
                       and any(abs(in_bar - q) < 1e-6 for q in starts_q))
            clica, accent = _decideix(
                es_bar, es_grup,
                _grups_alineats(click_unit, _bpb, _den))
            if clica:
                _posa(t_b, accent)
        k += 1

    np.clip(buf, -32768.0, 32767.0, out=buf)
    return buf.astype(np.int16).tobytes()
