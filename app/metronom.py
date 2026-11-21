"""metronom.py — generador de clics de metrònom (numpy pur, sense Qt).

Els clics es MESCLEN al buffer d'àudio que s'envia al reproductor, en comptes
de fer servir un segon reproductor o un QTimer (que derivaria respecte a la
cançó). Veure `app/visor.py` (_engega_des_de / _mono_bytes).

La graella base és la del regle del visor: el beat és el **denominador** del
compàs (`4/den` negres). La GUI usa `click_unit="auto"`: clica el
**denominador** de cada tram i accentua els inicis de grup (`6/8` → 6
corxeres amb accents a 1 i 4, `9/8` → 9, `12/8` → 12, `4/4` → 4 negres,
`2/2` → 2 blanques). `click_unit="pols"` queda com a mode alternatiu per
clicar només la unitat de pols del tram.
Els accents de grup ixen de `tempo_map.agrupacio_compas()`: `6/8` → `3+3`,
`7/8` → `7`, `5/8` → `5`, `8/8` → `8`, etc.

El mode `qm` marca els **beats detectats per QM** (`beats=`), un a un i sense
accents. No passa per la graella del mapa: els instants poden no coincidir amb
cap compàs/beat teòric i es col·loquen allà on els ha detectat QM.

Els modes `percebuts` i `interns` cliquen **sense accents** la pols percebuda de
cada tram i la negra (BPM intern), respectivament. `interns` no exigix que la
negra òmpliga el compàs: clica cada negra encara que caiga a cavall de compàs.
"""
import numpy as np
from app import bpm_unit, limits, tempo_map

# El metrònom rebutja els valors fora de la banda d'edició compartida.
BPM_MAX = limits.BPM_MAX

# Patrons de clic. `auto` = tots els temps + accents de compàs i grup.
# `percebuts` i `interns` cliquen sense accents la unitat de pols del tram i la
# negra (BPM intern), respectivament.
MODES = ("auto", "compas", "temps", "grup", "qm", "percebuts", "interns")

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
    """`pols` = unitat del tram; `auto` = denominador (històric)."""
    if click_unit == "tram":
        click_unit = "pols"
    return (click_unit if click_unit in ("auto", "pols")
            or click_unit in bpm_unit.UNITATS else "auto")


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


def _normalitza_beats(beats):
    """Beats absoluts en segons, finits, no negatius, ordenats i sense duplicats."""
    out = []
    for b in beats or ():
        try:
            t = float(b)
        except (TypeError, ValueError):
            continue
        if np.isfinite(t) and t >= 0.0:
            out.append(t)
    out.sort()
    nets = []
    for t in out:
        if not nets or t - nets[-1] > 1e-9:
            nets.append(t)
    return nets


def _mescla_beats_qm(mono_bytes, sr, t_inici, beats, volum, factor):
    """Marca els beats QM detectats, sense accents ni graella teòrica."""
    if volum <= 0:
        return mono_bytes
    beats = _normalitza_beats(beats)
    if not beats:
        return mono_bytes
    try:
        sr = float(sr)
        t_inici = float(t_inici)
        factor = float(factor)
    except (TypeError, ValueError):
        return mono_bytes
    if not np.isfinite(sr) or sr <= 0 or not np.isfinite(factor) or factor <= 0:
        return mono_bytes
    if not np.isfinite(t_inici):
        return mono_bytes
    buf = np.frombuffer(mono_bytes, dtype=np.int16).astype(np.float32)
    if buf.size == 0:
        return mono_bytes
    dur = buf.size / sr * factor
    clic = genera_clic(sr, False) * (32767.0 * float(volum))
    for t_abs in beats:
        t_b = (t_abs - t_inici) / factor
        if 0.0 <= t_b < dur:
            i = int(round(t_b * sr))
            n = min(clic.size, buf.size - i)
            if n > 0:
                buf[i:i + n] += clic[:n]
    np.clip(buf, -32768.0, 32767.0, out=buf)
    return buf.astype(np.int16).tobytes()


def mescla_metronom(mono_bytes, sr, t_inici, bpm, bpb,
                    volum=0.6, offset=0.0, mapa=None, factor=1.0,
                    den=4, mode="auto", click_unit="auto", beats=None):
    """Mescla els clics a la rodanxa `mono_bytes` (int16 mono, a partir de
    `t_inici` segons de la cançó) i retorna els bytes int16 resultants.

    - `bpb` és el **numerador** del compàs i `den` el **denominador**. El beat
      fa `(4/den) * 60/bpm` segons. La GUI usa `click_unit="auto"` i clica el
      denominador (`12/8` → 12 corxeres); `click_unit="pols"` és el mode
      alternatiu per clicar només la unitat de cada tram (`12/8` → 4 negres
      amb punt).
    - `mode`: `auto` (tots els temps + accents de compàs i grup), `compas`
      (només el primer temps), `temps` (tots els temps, sense accents de grup),
      `grup` (només compàs i inicis de grup en compassos compostos), `qm`
      (beats QM de `beats`, sense accents; poden no coincidir amb la graella),
      `percebuts` (unitat de pols percebuda de cada tram, sense accents) o
      `interns` (negra, el BPM intern, sense accents).
    - `beats`: instants absoluts en segons dels beats detectats per QM. Només
      s'utilitzen amb `mode="qm"`.
    - Només genera els clics que cauen dins la rodanxa (funciona des de
      qualsevol posició i amb el loop A/B).
    - Suma en float32 i fa clip a int16 per evitar desbordament.
    - volum 0 (o BPM invàlid) → retorna l'àudio sense canvis.
    - `factor` = velocitat de reproducció del visor (0,5–3×, to mantingut):
      la rodanxa cobreix `factor` cops més de cançó per segon real, així que
      els clics s'han de col·locar dividint per `factor` (si no, amb 2× el
      metrònom aniria a la meitat del tempo que sona). A 1,0× és idèntic.
    """
    if mode == "qm":
        return _mescla_beats_qm(mono_bytes, sr, t_inici, beats, volum, factor)
    valid = _es_valid(bpm, bpb, den)
    if valid is None or volum <= 0:
        return mono_bytes
    _bpb, _den = valid
    mode = _normalitza_mode(mode)
    click_unit = _normalitza_click_unit(click_unit)
    if mode == "percebuts":
        # Pols percebuda de cada tram; sense mapa, la del compàs del transport.
        click_unit = ("pols" if mapa is not None
                      else bpm_unit.unitat_per_defecte(_bpb, _den))
    elif mode == "interns":
        # El BPM intern sempre compta negres, encara que no omplin el compàs.
        click_unit = "negra"
    else:
        if click_unit == "pols" and mapa is None:
            click_unit = "auto"
        if click_unit not in ("auto", "pols"):
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
        if mode in ("percebuts", "interns"):
            return True, False
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

    # ── Amb `pols`, el clic és la unitat de cada tram (no una unitat global).
    # És el pols que percep el músic: 6/8 → 2 clics, 9/8 → 3, 12/8 → 4.
    # Recorrem la graella fina (1/32) per trobar els inicis de beat reals i
    # comprovem si el beat és múltiple de la unitat del tram.
    if click_unit == "pols" and mapa is not None:
        # `TempoMap.pos()` treballa a 1/32 de nota (0,125 negres): esta és la
        # graella mínima comuna per a denominadors 4/8/16.
        pas_q = 0.125
        q = float(mapa.quarters(float(t_inici)))
        q = float(np.floor(q / pas_q) * pas_q - pas_q)
        while True:
            t_abs = float(mapa.t_de_quarters(q))
            t_b = t_abs - float(t_inici)
            if t_b >= dur:
                break
            if t_b >= 0.0:
                _c, b, s = mapa.pos(t_abs)
                num_m, den_m = mapa.signatura(t_abs)
                agr_m = mapa.agrupacio(t_abs)
                unit_m = mapa.unitat(t_abs)
                if not bpm_unit.encaixa_en_compas(unit_m, num_m, den_m):
                    unit_m = bpm_unit.unitat_per_defecte(
                        num_m, den_m, agr_m)
                beat_q = _beat_quarters(den_m)
                rel = bpm_unit.factor(unit_m) / beat_q
                clica_pos = False
                if rel >= 1.0:
                    pas_beats = int(round(rel))
                    clica_pos = (s == 1 and pas_beats >= 1
                                 and abs(rel - pas_beats) <= 1e-9
                                 and (max(1, int(b)) - 1) % pas_beats == 0)
                else:
                    # La unitat és més curta que el beat (corxera en 4/4…):
                    # 8 subdivisions per beat → cada `8·rel` subdivisions.
                    pas_sub = int(round(8.0 * rel))
                    clica_pos = (pas_sub >= 1
                                 and abs(8.0 * rel - pas_sub) <= 1e-9
                                 and (int(s) - 1) % pas_sub == 0)
                if clica_pos:
                    b = max(1, int(b))
                    es_bar = (b == 1 and s == 1)
                    es_grup = _accent_grup(b, num_m, den_m, agr_m)
                    clica, accent = _decideix(es_bar, es_grup, True)
                    if clica:
                        _posa(t_b, accent)
            q += pas_q
        np.clip(buf, -32768.0, 32767.0, out=buf)
        return buf.astype(np.int16).tobytes()

    # ── Amb un mapa de tempo/compàs VARIABLE (regla d'or #5: el mapa és la
    # font), els clics van als TEMPS DEL MAPA. Recorrem la graella a resolució
    # de 1/16 (0,25 negres) i filtrem els punts que són inici de beat; així
    # funciona amb qualsevol denominador 2/4/8/16, canvis de compàs i rubato.
    if mapa is not None and (not mapa.es_constant()
                             or mapa.te_agrupacions_explicites()):
        q = float(mapa.quarters(float(t_inici)))
        if click_unit == "auto":
            # Graella del denominador: hi ha clic a cada beat (s == 1).
            # 0,25 negres = 1/16: el denominador més xicotet admés. Un pas de
            # 0,5 (corxera) es menjava la meitat dels temps en x/16.
            pas_q = 0.25
            q = float(np.floor(q / pas_q) * pas_q - pas_q)
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
                q += pas_q
        else:
            # Unitat de clic explícita: ancorada a l'inici de cada compàs.
            # Un càlcul global `q = k*paso` desalinea mapes com 5/8 → 6/8.
            bars = mapa.compassos()
            q_start = float(mapa.quarters(float(t_inici)))
            final_q = float(mapa.quarters(float(mapa.trams[-1].fi)))
            for k, (q_bar, _t_bar, _num_b, den_b) in enumerate(bars):
                q_next = (bars[k + 1][0] if k + 1 < len(bars)
                          else final_q)
                if q_next <= q_start - 1e-9:
                    continue
                paso = _click_quarters(click_unit, den_b)
                n = max(0, int(np.floor((q_start - q_bar) / paso)) - 1)
                q = float(q_bar) + n * paso
                while q < q_next - 1e-9:
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
