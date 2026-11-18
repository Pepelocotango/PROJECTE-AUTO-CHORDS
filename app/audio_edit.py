"""Edició destructiva i segura dels extrems d'una WAV PCM 16 bits."""

import math
import os
import tempfile
import wave
from dataclasses import replace

import numpy as np

from app import bpm_unit, limits, mapa_tempo, pipeline, tempo_map

RETALLA_INICI = "retalla_inici"
RETALLA_FINAL = "retalla_final"
SILENCI_INICI = "silenci_inici"
SILENCI_FINAL = "silenci_final"
FADE_MS = 4
_BLOC_FRAMES = 65536


def _fade_frames(sr, frames):
    return min(frames, max(1, int(round(sr * FADE_MS / 1000.0))))


def _copia_tram(origen, desti, inici, final, sortida,
                fade_in=False, fade_out=False):
    sr = origen.getframerate()
    canals = origen.getnchannels()
    mida_frame = canals * 2
    longitud = final - inici
    fade = _fade_frames(sr, longitud)
    origen.setpos(inici)
    copiats = 0
    while copiats < longitud:
        quants = min(_BLOC_FRAMES, longitud - copiats)
        raw = origen.readframes(quants)
        if len(raw) != quants * mida_frame:
            raise wave.Error("la WAV d'origen està truncada")
        if fade_in or fade_out:
            inici_bloc = sortida + copiats
            fi_bloc = inici_bloc + quants
            valors = np.frombuffer(raw, dtype="<i2").reshape(-1, canals)
            guany = np.ones(quants, dtype=np.float32)
            if fade_in:
                a = max(inici_bloc, sortida)
                b = min(fi_bloc, sortida + fade)
                if b > a:
                    idx = np.arange(a - sortida, b - sortida,
                                    dtype=np.float32)
                    guany[a - inici_bloc:b - inici_bloc] = (
                        idx / max(1, fade - 1))
            if fade_out:
                final_fade = sortida + longitud
                a = max(inici_bloc, final_fade - fade)
                b = min(fi_bloc, final_fade)
                if b > a:
                    idx = np.arange(a - (final_fade - fade),
                                    b - (final_fade - fade),
                                    dtype=np.float32)
                    guany[a - inici_bloc:b - inici_bloc] = (
                        1.0 - idx / max(1, fade - 1))
            valors = np.rint(valors * guany[:, None])
            raw = np.clip(valors, -32768, 32767).astype("<i2").tobytes()
        desti.writeframesraw(raw)
        copiats += quants


def escriu_wav_editada(origen, desti, operacio, frames):
    """Escriu una edició en temporal, la valida i la publica a `desti`.

    `frames` és la quantitat retallada (inici), la quantitat conservada
    (final) o la quantitat de silenci que s'afegeix.
    Retorna la durada nova en segons.
    """
    if os.path.abspath(origen) == os.path.abspath(desti):
        raise ValueError("l'edició necessita una destinació temporal diferent")
    if operacio not in (RETALLA_INICI, RETALLA_FINAL,
                        SILENCI_INICI, SILENCI_FINAL):
        raise ValueError(f"operació d'àudio desconeguda: {operacio!r}")
    if isinstance(frames, bool) or not isinstance(frames, int) or frames <= 0:
        raise ValueError("la quantitat de fotogrames ha de ser un enter positiu")

    temporal = None
    try:
        with wave.open(origen, "rb") as wav:
            total = wav.getnframes()
            sr = wav.getframerate()
            canals = wav.getnchannels()
            if wav.getsampwidth() != 2 or wav.getcomptype() != "NONE":
                raise ValueError("només es pot editar WAV PCM de 16 bits")
            if sr <= 0 or canals <= 0 or total <= 0:
                raise ValueError("la WAV no conté àudio vàlid")
            if operacio == RETALLA_INICI:
                if frames >= total:
                    raise ValueError("el retall deixaria la WAV sense àudio")
                nou_total = total - frames
            elif operacio == RETALLA_FINAL:
                if frames >= total:
                    raise ValueError("el retall no escurça la WAV")
                nou_total = frames
            else:
                nou_total = total + frames

            carpeta = os.path.dirname(os.path.abspath(desti))
            fd, temporal = tempfile.mkstemp(
                prefix=".audio-edit-", suffix=".wav", dir=carpeta)
            os.close(fd)
            with wave.open(temporal, "wb") as sortida:
                sortida.setparams((canals, 2, sr, 0, "NONE", "not compressed"))
                if operacio == RETALLA_INICI:
                    _copia_tram(wav, sortida, frames, total, 0, fade_in=True)
                elif operacio == RETALLA_FINAL:
                    _copia_tram(wav, sortida, 0, frames, 0, fade_out=True)
                elif operacio == SILENCI_INICI:
                    _escriu_silenci(sortida, frames, canals)
                    _copia_tram(wav, sortida, 0, total, frames, fade_in=True)
                else:
                    _copia_tram(wav, sortida, 0, total, 0, fade_out=True)
                    _escriu_silenci(sortida, frames, canals)
        with wave.open(temporal, "rb") as validada:
            if (validada.getsampwidth() != 2
                    or validada.getcomptype() != "NONE"
                    or validada.getnframes() != nou_total):
                raise wave.Error("la WAV editada no ha superat la validació")
        os.replace(temporal, desti)
        temporal = None
        return nou_total / float(sr)
    finally:
        if temporal and os.path.exists(temporal):
            os.unlink(temporal)


def _escriu_silenci(wav, frames, canals):
    mida_bloc = min(_BLOC_FRAMES, frames) * canals * 2
    silenci = bytes(mida_bloc)
    pendents = frames
    while pendents:
        quants = min(_BLOC_FRAMES, pendents)
        wav.writeframesraw(silenci[:quants * canals * 2])
        pendents -= quants


# --- Quadratura guiada dels extrems a compassos sencers --------------------
#: Presets de l'inici. `ceil` conserva tot el so i completa per excés;
#: `floor` retalla la fracció sobrant; `un` deixa un compàs; `zero` talla fins
#: al temps 1; `manual` usa el valor donat.
MODES_INICI = ("ceil", "floor", "un", "zero", "manual")
MODES_FINAL = ("ceil", "floor", "manual")
_TOL_PLA = 1e-9


def _valida_tram_tempo(bpm, num, den):
    tempo_map.valida_tempo(float(bpm), int(num), int(den))
    return float(bpm), int(num), int(den)


def _unitat_pols(unit, num, den, agrupacio=""):
    """Normalitza i valida la unitat de pols per al compàs donat (L3)."""
    base = unit or bpm_unit.unitat_per_defecte(num, den, agrupacio)
    u = bpm_unit.normalitza(base)
    if not bpm_unit.encaixa_en_compas(u, num, den):
        sugg = bpm_unit.unitat_per_defecte(num, den, agrupacio)
        raise ValueError(
            f"La unitat {u} no encaixa amb el compàs {int(num)}/{int(den)}; "
            f"tria {sugg} o canvia el compàs")
    return u


def calcula_n_inici(t_temps1, bpm, num, den, mode="ceil", n=None):
    """Compassos sencers que queden abans del temps 1 real.

    `t_temps1` és el temps real de l'inici musical dins la WAV actual.
    """
    t = float(t_temps1)
    if not math.isfinite(t) or t < 0:
        raise ValueError("El temps 1 ha de ser un temps positiu de la WAV")
    bpm, num, den = _valida_tram_tempo(bpm, num, den)
    compas = tempo_map.durada_compas(bpm, num, den)
    if compas <= 0:
        raise ValueError("El compàs d'entrada no té durada")
    q = t / compas
    mode = str(mode or "ceil").strip().lower()
    if mode not in MODES_INICI:
        raise ValueError(f"Mode d'inici desconegut: {mode!r}")
    if mode == "ceil":
        return max(1, _sostre(q))
    if mode == "floor":
        return max(0, _terra(q))
    if mode == "un":
        return 1
    if mode == "zero":
        return 0
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        raise ValueError("N inicial ha de ser un enter ≥ 0")
    return int(n)


def n_min_fi(t_ultim_fort, t_ini_ultim, bpm, num, den):
    """Compassos mínims de l'últim tram per no tallar el temps fort final."""
    start = float(t_ini_ultim)
    if t_ultim_fort is None:
        return 1
    fort = float(t_ultim_fort)
    if not math.isfinite(fort) or fort < 0:
        raise ValueError("El temps fort final ha de ser positiu")
    bpm, num, den = _valida_tram_tempo(bpm, num, den)
    compas = tempo_map.durada_compas(bpm, num, den)
    if compas <= 0:
        raise ValueError("El compàs final no té durada")
    if fort <= start + _TOL_PLA:
        return 1
    return max(1, _sostre((fort - start) / compas) + 1)


def calcula_n_fi(durada, t_ini_ultim, bpm, num, den, mode="ceil", n=None,
                 t_ultim_fort=None):
    """Compassos sencers de l'últim tram, respectant la protecció del fort."""
    durada = float(durada)
    start = float(t_ini_ultim)
    if durada <= 0 or start < 0 or start >= durada + _TOL_PLA:
        raise ValueError("L'últim tram no és dins la WAV")
    bpm, num, den = _valida_tram_tempo(bpm, num, den)
    compas = tempo_map.durada_compas(bpm, num, den)
    if compas <= 0:
        raise ValueError("El compàs final no té durada")
    if t_ultim_fort is not None and (
            not math.isfinite(float(t_ultim_fort))
            or float(t_ultim_fort) > durada + _TOL_PLA):
        raise ValueError("El temps fort final ha de ser dins la WAV")
    minim = n_min_fi(t_ultim_fort, start, bpm, num, den)
    mode = str(mode or "ceil").strip().lower()
    if mode not in MODES_FINAL:
        raise ValueError(f"Mode final desconegut: {mode!r}")
    q = max(0.0, durada - start) / compas
    if mode == "ceil":
        return max(minim, _sostre(q))
    if mode == "floor":
        return max(minim, _terra(q))
    if isinstance(n, bool) or not isinstance(n, int) or n < minim:
        raise ValueError(
            f"N final ha de ser un enter ≥ {minim} (protecció del temps fort)")
    return int(n)


def calcula_n_cua(durada, t_final, bpm, num, den, mode="ceil", n=None):
    """Compassos de cua des del final musical fins al final de la WAV."""
    durada = float(durada)
    t = float(t_final)
    if not (0.0 <= t <= durada + _TOL_PLA):
        raise ValueError("El final de la música ha de ser dins la WAV")
    bpm, num, den = _valida_tram_tempo(bpm, num, den)
    compas = tempo_map.durada_compas(bpm, num, den)
    if compas <= 0:
        raise ValueError("El compàs final no té durada")
    q = max(0.0, durada - t) / compas
    mode = str(mode or "ceil").strip().lower()
    if mode not in MODES_FINAL:
        raise ValueError(f"Mode final desconegut: {mode!r}")
    if mode == "ceil":
        return max(1, _sostre(q))
    if mode == "floor":
        return max(1, _terra(q))
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ValueError("N de cua ha de ser un enter ≥ 1")
    return int(n)


def n_fi_despres_fort(t_ultim_fort, t_ini_ultim, bpm, num, den, k=1):
    """`N` de l'últim tram: compassos fins al fort més `k` de cua.

    `k=0` deixa la protecció mínima (un compàs de resolució); `k=1` deixa un
    compàs de cua després del fort, etc.
    """
    if isinstance(k, bool) or not isinstance(k, int) or k < 0:
        raise ValueError("K ha de ser un enter ≥ 0")
    minim = n_min_fi(t_ultim_fort, t_ini_ultim, bpm, num, den)
    if t_ultim_fort is None:
        return int(max(1, k))
    start = float(t_ini_ultim)
    bpm, num, den = _valida_tram_tempo(bpm, num, den)
    compas = tempo_map.durada_compas(bpm, num, den)
    q = max(0, _sostre((float(t_ultim_fort) - start) / compas))
    return int(max(minim, q + k))


def _sostre(q):
    """`ceil` estable: un valor a tocar d'un enter no salta de compàs."""
    r = round(float(q))
    return int(r) if abs(float(q) - r) <= 1e-6 else int(math.ceil(q))


def _terra(q):
    """`floor` estable: un valor a tocar d'un enter no baixa de compàs."""
    r = round(float(q))
    return int(r) if abs(float(q) - r) <= 1e-6 else int(math.floor(q))


def _frames(delta, sr):
    return int(round(float(delta) * int(sr)))


def planifica_extrems(durada, sr, trams, t_temps1=None, n_ini=0,
                      t_ultim_fort=None, n_fi=1, aplica_inici=True,
                      aplica_final=False, bpm_ini=None, num_ini=None,
                      den_ini=None, t_final=None, bpm_fi=None,
                      num_fi=None, den_fi=None, beat_unit_ini=None,
                      beat_unit_fi=None):
    """Calcula un pla d'extrems **sense tocar** àudio ni model.

    Retorna deltes exactes per al model i fotogrames per a la WAV. Les
    fronteres del model són exactes (`N` compassos); la WAV s'arredoneix a
    mostra, amb una diferència màxima de mig fotograma per extrem.
    """
    durada = float(durada)
    sr = int(sr)
    if durada <= 0 or sr <= 0:
        raise ValueError("La WAV ha de tindre durada i freqüència vàlides")
    trams = [mapa_tempo.des_de_tupla(t) for t in (trams or ())]
    if not trams:
        raise ValueError("Cal un mapa de tempo/compàs per a quadrar extrems")
    total = int(round(durada * sr))
    pla = {
        "aplica_inici": bool(aplica_inici),
        "aplica_final": bool(aplica_final),
        "n_ini": 0, "n_fi": 0,
        "delta_ini": 0.0, "delta_fi": 0.0,
        "target_ini": 0.0, "target_fi": durada,
        "retalla_ini": 0, "silenci_ini": 0,
        "retalla_fi": 0, "silenci_fi": 0,
        "durada": durada, "sr": sr, "durada_nova": durada,
        "durada_nova_frames": total,
    }
    delta_ini = delta_fi = 0.0

    if aplica_inici:
        if t_temps1 is None:
            raise ValueError("Falta el temps 1 real")
        t1 = float(t_temps1)
        if not math.isfinite(t1) or t1 < 0 or t1 > durada + _TOL_PLA:
            raise ValueError("El temps 1 ha de ser dins la WAV")
        ent = trams[0]
        if isinstance(n_ini, bool) or not isinstance(n_ini, int) or n_ini < 0:
            raise ValueError("N inicial ha de ser un enter ≥ 0")
        bpm_ent = ent.bpm if bpm_ini is None else bpm_ini
        num_ent = ent.num if num_ini is None else num_ini
        den_ent = ent.den if den_ini is None else den_ini
        bpm_ent, num_ent, den_ent = _valida_tram_tempo(
            bpm_ent, num_ent, den_ent)
        unit_ent = _unitat_pols(
            beat_unit_ini or ent.beat_unit, num_ent, den_ent,
            ent.agrupacio)
        compas = tempo_map.durada_compas(bpm_ent, num_ent, den_ent)
        target = n_ini * compas
        delta_ini = target - t1
        frames = _frames(delta_ini, sr)
        if frames > 0:
            pla["silenci_ini"] = frames
        elif frames < 0:
            retalla = -frames
            if retalla >= total:
                raise ValueError("El retall inicial deixaria la WAV buida")
            pla["retalla_ini"] = retalla
        pla["n_ini"] = n_ini
        pla["delta_ini"] = delta_ini
        pla["target_ini"] = target
        pla["bpm_ini"] = bpm_ent
        pla["num_ini"] = num_ent
        pla["den_ini"] = den_ent
        pla["beat_unit_ini"] = unit_ent
        pla["agrupacio_ini"] = ent.agrupacio

    if aplica_final:
        ult = trams[-1]
        if t_final is not None:
            # Mode cua: `t_final` és on s'acaba la música i `n_fi` són els
            # compassos de cua que es volen conservar.
            tf = float(t_final)
            if not (0.0 <= tf <= durada + _TOL_PLA):
                raise ValueError(
                    "El punt de tall final ha de ser dins la WAV")
            bpm_tail = ult.bpm if bpm_fi is None else bpm_fi
            num_tail = ult.num if num_fi is None else num_fi
            den_tail = ult.den if den_fi is None else den_fi
            bpm_tail, num_tail, den_tail = _valida_tram_tempo(
                bpm_tail, num_tail, den_tail)
            unit_tail = _unitat_pols(
                beat_unit_fi or ult.beat_unit, num_tail, den_tail,
                ult.agrupacio)
            compas = tempo_map.durada_compas(ult.bpm, ult.num, ult.den)
            n_abans = max(0, int(round((tf - float(ult.ini)) / compas)))
            # El punt és el que ha marcat l'usuari: no es mou. El tram normal
            # de l'esquerra es recalcula (N/BPM) perquè tinga compassos sencers.
            tf_alin = tf
            if not (1 <= int(n_fi) <= 9999):
                raise ValueError("N de cua ha de ser un enter ≥ 1")
            n_cua = int(n_fi)
            compas_cua = tempo_map.durada_compas(
                bpm_tail, num_tail, den_tail)
            target_fi = tf_alin + n_cua * compas_cua
            delta_fi = target_fi - (durada + delta_ini)
            frames = _frames(delta_fi, sr)
            if frames > 0:
                pla["silenci_fi"] = frames
            elif frames < 0:
                retalla = -frames
                if retalla >= total:
                    raise ValueError("El retall final deixaria la WAV buida")
                pla["retalla_fi"] = retalla
            pla["n_fi"] = n_abans + n_cua
            pla["n_cua"] = n_cua
            pla["n_fi_abans"] = n_abans
            pla["target_final_point"] = tf_alin + delta_ini
            pla["t_final"] = tf
            pla["delta_fi"] = delta_fi
            pla["target_fi"] = target_fi + delta_ini
            pla["bpm_fi"] = bpm_tail
            pla["num_fi"] = num_tail
            pla["den_fi"] = den_tail
            pla["beat_unit_fi"] = unit_tail
            pla["agrupacio_fi"] = ult.agrupacio
        else:
            start_fi = float(ult.ini) + delta_ini
            if aplica_inici and int(n_ini) > 0:
                start_fi = max(start_fi, float(pla["target_ini"]))
            bpm_tail = ult.bpm if bpm_fi is None else bpm_fi
            num_tail = ult.num if num_fi is None else num_fi
            den_tail = ult.den if den_fi is None else den_fi
            bpm_tail, num_tail, den_tail = _valida_tram_tempo(
                bpm_tail, num_tail, den_tail)
            unit_tail = _unitat_pols(
                beat_unit_fi or ult.beat_unit, num_tail, den_tail,
                ult.agrupacio)
            minim = n_min_fi(t_ultim_fort, start_fi, bpm_tail,
                             num_tail, den_tail)
            if isinstance(n_fi, bool) or not isinstance(n_fi, int) \
                    or n_fi < minim:
                raise ValueError(
                    f"N final ha de ser un enter ≥ {minim} "
                    "(protecció del fort)")
            compas = tempo_map.durada_compas(bpm_tail, num_tail, den_tail)
            target_orig = start_fi + int(n_fi) * compas
            if t_ultim_fort is not None and target_orig < float(t_ultim_fort):
                raise ValueError("El final retallaria el temps fort protegit")
            delta_fi = target_orig - (durada + delta_ini)
            frames = _frames(delta_fi, sr)
            if frames > 0:
                pla["silenci_fi"] = frames
            elif frames < 0:
                retalla = -frames
                if retalla >= total:
                    raise ValueError("El retall final deixaria la WAV buida")
                pla["retalla_fi"] = retalla
            pla["n_fi"] = int(n_fi)
            pla["delta_fi"] = delta_fi
            pla["target_fi"] = target_orig
            pla["bpm_fi"] = bpm_tail
            pla["num_fi"] = num_tail
            pla["den_fi"] = den_tail
            pla["beat_unit_fi"] = unit_tail
            pla["agrupacio_fi"] = ult.agrupacio

    nou_final = durada + delta_ini + delta_fi
    nou_frames = (total - pla["retalla_ini"] + pla["silenci_ini"]
                  - pla["retalla_fi"] + pla["silenci_fi"])
    if nou_frames <= 0:
        raise ValueError("L'edició deixaria la WAV buida")
    if nou_final < limits.TEMPS_MIN_CLIP - _TOL_PLA:
        raise ValueError(
            f"La durada final ({nou_final:.4f}s) és inferior al mínim "
            f"({limits.TEMPS_MIN_CLIP:.4f}s)")
    if abs(nou_final - nou_frames / float(sr)) > 1.0 / sr + _TOL_PLA:
        raise ValueError("El pla d'àudio i el model no quadren a mostra")
    pla["durada_nova"] = nou_final
    pla["durada_nova_frames"] = nou_frames
    return pla


def escriu_wav_extrems(origen, desti, retalla_ini=0, silenci_ini=0,
                       retalla_fi=0, silenci_fi=0):
    """Aplica inici i final en **una sola escriptura atòmica** de la WAV.

    Els valors són fotogrames no negatius. Per a cada extrem, o es retalla o
    s'afegeix silenci, no les dos coses alhora.
    """
    valors = (retalla_ini, silenci_ini, retalla_fi, silenci_fi)
    if any(isinstance(v, bool) or not isinstance(v, int) or v < 0
           for v in valors):
        raise ValueError("Els fotogrames han de ser enters ≥ 0")
    if retalla_ini and silenci_ini:
        raise ValueError("No es pot retallar i afegir silenci a l'inici alhora")
    if retalla_fi and silenci_fi:
        raise ValueError("No es pot retallar i afegir silenci al final alhora")
    if os.path.abspath(origen) == os.path.abspath(desti):
        raise ValueError("l'edició necessita una destinació temporal diferent")
    temporal = None
    try:
        with wave.open(origen, "rb") as wav:
            total = wav.getnframes()
            sr = wav.getframerate()
            canals = wav.getnchannels()
            if wav.getsampwidth() != 2 or wav.getcomptype() != "NONE":
                raise ValueError("només es pot editar WAV PCM de 16 bits")
            if sr <= 0 or canals <= 0 or total <= 0:
                raise ValueError("la WAV no conté àudio vàlid")
            inici = int(retalla_ini)
            final = total - int(retalla_fi)
            if inici >= final:
                raise ValueError("el retall deixaria la WAV sense àudio")
            nou_total = int(silenci_ini) + (final - inici) + int(silenci_fi)
            if nou_total <= 0:
                raise ValueError("el resultat deixaria la WAV sense àudio")
            carpeta = os.path.dirname(os.path.abspath(desti))
            fd, temporal = tempfile.mkstemp(
                prefix=".audio-edit-", suffix=".wav", dir=carpeta)
            os.close(fd)
            with wave.open(temporal, "wb") as sortida:
                sortida.setparams((canals, 2, sr, 0, "NONE", "not compressed"))
                if silenci_ini:
                    _escriu_silenci(sortida, int(silenci_ini), canals)
                _copia_tram(wav, sortida, inici, final, int(silenci_ini),
                            fade_in=bool(silenci_ini or retalla_ini),
                            fade_out=bool(silenci_fi or retalla_fi))
                if silenci_fi:
                    _escriu_silenci(sortida, int(silenci_fi), canals)
        with wave.open(temporal, "rb") as validada:
            if (validada.getsampwidth() != 2
                    or validada.getcomptype() != "NONE"
                    or validada.getnframes() != nou_total):
                raise wave.Error("la WAV editada no ha superat la validació")
        os.replace(temporal, desti)
        temporal = None
        return nou_total / float(sr)
    finally:
        if temporal and os.path.exists(temporal):
            os.unlink(temporal)


def _desplaca_inici(clips, delta):
    if delta > _TOL_PLA:
        return ([pipeline.Clip(0.0, delta, pipeline.FORAT_ACORD)]
                + [pipeline.Clip(c.ini + delta, c.fi + delta, c.payload)
                   for c in clips])
    if delta < -_TOL_PLA:
        x = -delta
        return [pipeline.Clip(max(0.0, c.ini - x), c.fi - x, c.payload)
                for c in clips if c.fi > x]
    return list(clips)


def _desplaca_seccions(seccions, delta):
    if delta > _TOL_PLA:
        if seccions:
            return ([(0.0, seccions[0][1] + delta) + tuple(seccions[0][2:])]
                    + [(s[0] + delta, s[1] + delta) + tuple(s[2:])
                       for s in seccions[1:]])
        return seccions
    if delta < -_TOL_PLA:
        x = -delta
        return [(max(0.0, s[0] - x), s[1] - x) + tuple(s[2:])
                for s in seccions if s[1] > x]
    return list(seccions)


def transforma_model_extrems(acords, seccions, trams, marcadors, durada, pla,
                             pos=0.0, loop_a=None, loop_b=None, loop_on=False):
    """Transforma el model per al pla d'extrems, en una sola operació."""
    durada = float(durada)
    nou_final = float(pla["durada_nova"])
    delta_ini = float(pla.get("delta_ini", 0.0)) if pla["aplica_inici"] else 0.0
    delta_fi = float(pla.get("delta_fi", 0.0)) if pla["aplica_final"] else 0.0
    clips_acord = pipeline.clips_d_acords(acords, durada)
    clips_seccio = pipeline.clips_de_seccions(seccions)
    trams = [mapa_tempo.des_de_tupla(t) for t in (trams or [])]
    if not trams:
        trams = [mapa_tempo.TramMapa(0.0, durada, 120.0, "normal", "4/4")]
    marcadors = [float(t) for t in (marcadors or ())]
    nova_pos = float(pos)
    nou_loop_a, nou_loop_b, nou_loop_on = loop_a, loop_b, bool(loop_on)

    if abs(delta_ini) > _TOL_PLA:
        clips_acord = _desplaca_inici(clips_acord, delta_ini)
        clips_seccio = _desplaca_seccions(clips_seccio, delta_ini)
        trams = [replace(t, ini=float(t.ini) + delta_ini,
                         fi=float(t.fi) + delta_ini)
                 if delta_ini > 0 else t for t in trams]
        if delta_ini < 0:
            x = -delta_ini
            trams = [replace(t, ini=max(0.0, float(t.ini) - x),
                             fi=float(t.fi) - x)
                     for t in trams if float(t.fi) > x]
            if trams:
                trams[0] = replace(trams[0], ini=0.0)
        marcadors = [t + delta_ini for t in marcadors if t >= -delta_ini]
        nova_pos = max(0.0, nova_pos + delta_ini)
        if nou_loop_a is not None and nou_loop_b is not None:
            nou_loop_a = max(0.0, float(nou_loop_a) + delta_ini)
            nou_loop_b = max(0.0, float(nou_loop_b) + delta_ini)

    # Els N compassos d'entrada són un bloc propi (o s'integren al primer si
    # comparteixen BPM/compàs): el que hi ha abans del temps 1 no pot deformar
    # el tempo musical posterior.
    if pla["aplica_inici"] and int(pla.get("n_ini", 0)) > 0:
        target = float(pla["target_ini"])
        trams = [t for t in trams if float(t.fi) > target + _TOL_PLA]
        if trams and float(trams[0].ini) < target - _TOL_PLA:
            trams[0] = replace(trams[0], ini=target, n=None)
        if trams and float(trams[0].ini) > target + _TOL_PLA:
            trams[0] = replace(trams[0], ini=target, n=None)
        intro = mapa_tempo.TramMapa(
            0.0, target, float(pla["bpm_ini"]), "normal",
            f"{int(pla['num_ini'])}/{int(pla['den_ini'])}",
            pla.get("agrupacio_ini", ""), int(pla["n_ini"]),
            pla.get("beat_unit_ini"))
        pot_fusionar = False
        if (trams and abs(float(trams[0].ini) - target) <= _TOL_PLA
                and abs(float(trams[0].bpm) - intro.bpm) <= _TOL_PLA
                and trams[0].num == intro.num and trams[0].den == intro.den
                and trams[0].tipus == "normal"
                and trams[0].agrupacio == intro.agrupacio
                and trams[0].beat_unit == intro.beat_unit):
            durada_dreta = float(trams[0].fi) - target
            compas = tempo_map.durada_compas(
                intro.bpm, intro.num, intro.den)
            n_dreta = durada_dreta / compas if compas > 0 else 0.0
            pot_fusionar = abs(n_dreta - round(n_dreta)) <= 1e-6
        if pot_fusionar:
            trams[0] = replace(trams[0], ini=0.0, n=None)
        else:
            trams = [intro] + trams

    mid = durada + delta_ini
    if pla["aplica_final"]:
        punt = pla.get("target_final_point")
        if punt is not None:
            # El tall del final és una frontera de model: tot el que hi ha
            # després es descarta i només queda el clip final (N) fins al nou
            # final de la WAV.
            punt = float(punt)
            clips_acord = [
                pipeline.Clip(c.ini, min(c.fi, punt), c.payload)
                for c in clips_acord if c.ini < punt - _TOL_PLA]
            clips_acord.append(pipeline.Clip(
                punt, nou_final, pipeline.FORAT_ACORD))
            clips_seccio = [
                (s[0], min(s[1], punt)) + tuple(s[2:])
                for s in clips_seccio if s[0] < punt - _TOL_PLA]
            clips_seccio.append(
                (punt, nou_final) + tuple(
                    (clips_seccio[-1][2:] if clips_seccio
                     else (pipeline.FORAT_SECCIO,
                           pipeline.FORAT_SECCIO))))
        elif abs(delta_fi) > _TOL_PLA:
            if delta_fi < 0:
                clips_acord = [
                    pipeline.Clip(c.ini, min(c.fi, nou_final), c.payload)
                    for c in clips_acord if c.ini < nou_final]
                clips_seccio = [
                    (s[0], min(s[1], nou_final)) + tuple(s[2:])
                    for s in clips_seccio if s[0] < nou_final]
            else:
                clips_acord.append(pipeline.Clip(
                    mid, nou_final, pipeline.FORAT_ACORD))
                if clips_seccio:
                    ult = clips_seccio[-1]
                    clips_seccio[-1] = (ult[0], nou_final) + tuple(ult[2:])
        marcadors = [t for t in marcadors if t <= nou_final]
        nova_pos = min(nova_pos, nou_final)
        if nou_loop_a is not None and nou_loop_b is not None:
            nou_loop_a = min(float(nou_loop_a), nou_final)
            nou_loop_b = min(float(nou_loop_b), nou_final)
        target_fi = float(pla["target_fi"])
        if trams and punt is not None:
            punt = float(punt)
            abans = []
            for t in trams:
                if float(t.ini) >= punt - _TOL_PLA:
                    continue
                if float(t.fi) > punt + _TOL_PLA:
                    abans.append(replace(t, fi=punt, n=None))
                else:
                    abans.append(t)
            dreta = mapa_tempo.TramMapa(
                punt, target_fi,
                float(pla.get("bpm_fi", 120.0)), "normal",
                f"{int(pla.get('num_fi', 4))}/{int(pla.get('den_fi', 4))}",
                "", int(pla.get("n_cua", 1)),
                pla.get("beat_unit_fi"))
            trams = abans + [dreta]
        elif trams and float(trams[-1].ini) < target_fi - _TOL_PLA:
            trams[-1] = replace(trams[-1], fi=target_fi,
                                n=int(pla["n_fi"]))
        elif trams:
            trams = [t for t in trams if float(t.ini) < nou_final - _TOL_PLA]
            trams[-1] = replace(trams[-1], fi=nou_final,
                                n=int(pla["n_fi"]))
    else:
        target_fi = nou_final
        if trams:
            trams[-1] = replace(trams[-1], fi=nou_final)

    acords_nous = pipeline.normalitza_clips(
        clips_acord, nou_final, pipeline.FORAT_ACORD,
        arrodoneix=True, deriva_fi=True)
    seccions_noves = pipeline.normalitza_clips(
        clips_seccio, nou_final, pipeline.FORAT_SECCIO)
    if not acords_nous:
        acords_nous = [pipeline.Clip(0.0, nou_final, pipeline.FORAT_ACORD)]
    if not seccions_noves:
        seccions_noves = [pipeline.Clip(
            0.0, nou_final, pipeline.FORAT_SECCIO)]
    if (nou_loop_a is None or nou_loop_b is None
            or nou_loop_b <= nou_loop_a):
        nou_loop_a = nou_loop_b = None
        nou_loop_on = False
    trams, _avisos = mapa_tempo.normalitza_trams_map(trams, nou_final)
    base5, ns, _avisos_aj = tempo_map.ajusta_compassos_sencers(
        [tuple(t) for t in trams], estricte=True)
    trams_meta = [
        mapa_tempo.TramMapa(
            float(t5[0]), float(t5[1]), float(t5[2]), t.tipus,
            f"{int(t5[3])}/{int(t5[4])}", t.agrupacio, float(n),
            t.beat_unit)
        for t, t5, n in zip(trams, base5, ns)]
    return {
        "acords": acords_nous,
        "seccions": pipeline.seccions_de_clips(seccions_noves),
        "trams": trams_meta,
        "marcadors": marcadors,
        "durada": nou_final,
        "pos": nova_pos,
        "loop_a": nou_loop_a,
        "loop_b": nou_loop_b,
        "loop_on": nou_loop_on,
    }


def transforma_model(acords, seccions, trams, marcadors, durada,
                     operacio, delta, pos=0.0, loop_a=None, loop_b=None,
                     loop_on=False):
    """Transforma el model: delta és el tall inicial, fi objectiu o silenci."""
    durada = float(durada)
    delta = float(delta)
    if delta <= 0 or durada <= 0:
        raise ValueError("la durada i el canvi d'àudio han de ser positius")
    if operacio == RETALLA_INICI:
        nou_final = durada - delta
    elif operacio == RETALLA_FINAL:
        nou_final = delta
    else:
        nou_final = durada + delta
    if nou_final <= 0:
        raise ValueError("l'edició deixaria una durada no vàlida")
    if operacio in (RETALLA_INICI, RETALLA_FINAL) and nou_final >= durada:
        raise ValueError("el retall ha d'escurçar la durada")

    clips_acord = pipeline.clips_d_acords(acords, durada)
    clips_seccio = pipeline.clips_de_seccions(seccions)
    trams = [mapa_tempo.des_de_tupla(t) for t in (trams or [])]
    if not trams:
        trams = [mapa_tempo.TramMapa(0.0, durada, 120.0, "normal", "4/4")]
    marcadors = [float(t) for t in (marcadors or ())]
    nova_pos = float(pos)
    nou_loop_a, nou_loop_b = loop_a, loop_b
    nou_loop_on = bool(loop_on)

    if operacio == RETALLA_INICI:
        clips_acord = [
            pipeline.Clip(max(0.0, c.ini - delta), c.fi - delta, c.payload)
            for c in clips_acord if c.fi > delta]
        clips_seccio = [
            pipeline.Clip(max(0.0, s.ini - delta), s.fi - delta, s.payload)
            for s in clips_seccio if s.fi > delta]
        idx = next((i for i, t in enumerate(trams)
                    if float(t.fi) > delta + 1e-12), None)
        if idx is None:
            raise ValueError("el retall deixaria la WAV sense tempo")
        actiu = trams[idx]
        trams = [replace(actiu, ini=0.0, fi=float(actiu.fi) - delta)] + [
            replace(t, ini=float(t.ini) - delta, fi=float(t.fi) - delta)
            for t in trams[idx + 1:]]
        marcadors = [t - delta for t in marcadors if t >= delta]
        nova_pos = max(0.0, nova_pos - delta)
        if nou_loop_a is not None and nou_loop_b is not None:
            nou_loop_a = max(0.0, float(nou_loop_a) - delta)
            nou_loop_b = max(0.0, float(nou_loop_b) - delta)
    elif operacio == RETALLA_FINAL:
        clips_acord = [
            pipeline.Clip(c.ini, min(c.fi, nou_final), c.payload)
            for c in clips_acord if c.ini < nou_final]
        clips_seccio = [
            pipeline.Clip(s.ini, min(s.fi, nou_final), s.payload)
            for s in clips_seccio if s.ini < nou_final]
        trams = [replace(t, fi=min(float(t.fi), nou_final))
                 for t in trams if float(t.ini) < nou_final]
        marcadors = [t for t in marcadors if t <= nou_final]
        nova_pos = min(nova_pos, nou_final)
        if nou_loop_a is not None and nou_loop_b is not None:
            nou_loop_a = min(float(nou_loop_a), nou_final)
            nou_loop_b = min(float(nou_loop_b), nou_final)
    elif operacio == SILENCI_INICI:
        clips_acord = [pipeline.Clip(0.0, delta, pipeline.FORAT_ACORD)] + [
            pipeline.Clip(c.ini + delta, c.fi + delta, c.payload)
            for c in clips_acord]
        if clips_seccio:
            clips_seccio = [
                pipeline.Clip(0.0, clips_seccio[0].fi + delta,
                              clips_seccio[0].payload)
            ] + [
                pipeline.Clip(s.ini + delta, s.fi + delta, s.payload)
                for s in clips_seccio[1:]]
        if trams:
            trams = [
                replace(trams[0], ini=0.0, fi=float(trams[0].fi) + delta)
            ] + [
                replace(t, ini=float(t.ini) + delta,
                        fi=float(t.fi) + delta)
                for t in trams[1:]]
        marcadors = [t + delta for t in marcadors]
        nova_pos += delta
        if nou_loop_a is not None and nou_loop_b is not None:
            nou_loop_a = float(nou_loop_a) + delta
            nou_loop_b = float(nou_loop_b) + delta
    elif operacio == SILENCI_FINAL:
        clips_acord.append(pipeline.Clip(
            durada, nou_final, pipeline.FORAT_ACORD))
        if clips_seccio:
            ult = clips_seccio[-1]
            clips_seccio[-1] = pipeline.Clip(ult.ini, nou_final, ult.payload)
        if trams:
            trams[-1] = replace(trams[-1], fi=nou_final)
    else:
        raise ValueError(f"operació d'àudio desconeguda: {operacio!r}")

    acords_nous = pipeline.normalitza_clips(
        clips_acord, nou_final, pipeline.FORAT_ACORD,
        arrodoneix=True, deriva_fi=True)
    seccions_noves = pipeline.normalitza_clips(
        clips_seccio, nou_final, pipeline.FORAT_SECCIO)
    if not acords_nous:
        acords_nous = [pipeline.Clip(0.0, nou_final, pipeline.FORAT_ACORD)]
    if not seccions_noves:
        seccions_noves = [pipeline.Clip(
            0.0, nou_final, pipeline.FORAT_SECCIO)]
    if (nou_loop_a is None or nou_loop_b is None
            or nou_loop_b <= nou_loop_a):
        nou_loop_a = nou_loop_b = None
        nou_loop_on = False

    # §13.4/§13.9: N enter a tots els clips, també després d'una edició
    # d'àudio. Les fronteres temporals són les que ha fixat l'edició; si N
    # quedaria fraccionari, es recalcula el BPM. `estricte=True` fa fallar
    # l'operació sencera abans de tocar l'àudio si no hi ha cap BPM vàlid.
    trams, _avisos = mapa_tempo.normalitza_trams_map(trams, nou_final)
    base5, ns, _avisos_aj = tempo_map.ajusta_compassos_sencers(
        [tuple(t) for t in trams], estricte=True)
    trams_meta = [
        mapa_tempo.TramMapa(
            float(t5[0]), float(t5[1]), float(t5[2]), t.tipus,
            f"{int(t5[3])}/{int(t5[4])}", t.agrupacio, float(n),
            t.beat_unit)
        for t, t5, n in zip(trams, base5, ns)]
    return {
        "acords": acords_nous,
        "seccions": pipeline.seccions_de_clips(seccions_noves),
        "trams": trams_meta,
        "marcadors": marcadors,
        "durada": nou_final,
        "pos": nova_pos,
        "loop_a": nou_loop_a,
        "loop_b": nou_loop_b,
        "loop_on": nou_loop_on,
    }
