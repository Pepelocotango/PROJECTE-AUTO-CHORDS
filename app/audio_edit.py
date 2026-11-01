"""Edició destructiva i segura dels extrems d'una WAV PCM 16 bits."""

import os
import tempfile
import wave

import numpy as np

from app import pipeline
from app.tempo_map import TempoMap

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


def transforma_model(acords, seccions, trams, marcadors, offset, durada,
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
    trams = [tuple(t) for t in (trams or ())]
    if not trams:
        trams = [(0.0, durada, 120.0, 4, 4)]
    marcadors = [float(t) for t in (marcadors or ())]
    nou_offset = float(offset)
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
        mapa = TempoMap(trams, nou_offset)
        actiu = mapa.tram(delta)
        nou_trams = [(0.0, actiu.fi - delta, actiu.bpm,
                      actiu.num, actiu.den)]
        for t in trams:
            if t[0] >= actiu.fi - 1e-9 and t[1] > delta:
                nou_trams.append((t[0] - delta, t[1] - delta,
                                  t[2], t[3], t[4]))
        trams = nou_trams
        marcadors = [t - delta for t in marcadors if t >= delta]
        nou_offset -= delta
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
        trams = [(t[0], min(t[1], nou_final), *t[2:])
                 for t in trams if t[0] < nou_final]
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
                (0.0, trams[0][1] + delta, *trams[0][2:])
            ] + [
                (t[0] + delta, t[1] + delta, *t[2:])
                for t in trams[1:]]
        marcadors = [t + delta for t in marcadors]
        nou_offset += delta
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
            trams[-1] = (trams[-1][0], nou_final, *trams[-1][2:])
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

    return {
        "acords": acords_nous,
        "seccions": pipeline.seccions_de_clips(seccions_noves),
        "trams": trams,
        "marcadors": marcadors,
        "offset": nou_offset,
        "durada": nou_final,
        "pos": nova_pos,
        "loop_a": nou_loop_a,
        "loop_b": nou_loop_b,
        "loop_on": nou_loop_on,
    }
