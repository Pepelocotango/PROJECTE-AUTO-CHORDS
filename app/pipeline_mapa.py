"""Mapa de tempo i marcadors del projecte (F1).

Extret de `app/pipeline.py`: lectura/escriptura de `mapa_tempo.csv` i
`marcadors.csv`. Depén de `pipeline_io` per a l'escriptura atòmica.
"""
import os

from . import mapa_tempo, tempo_map
from .pipeline_io import escriu_atomic

def _mapa_tempo_carpeta(carpeta, offset=0.0):
    """Llig `mapa_tempo.csv` de `carpeta` (o `mapa_tempo/`) i retorna un
    `TempoMap` si té més d'un tram i no és constant, o `None`.
    """
    try:
        from app.tempo_map import TempoMap

        for d in (carpeta, os.path.join(carpeta, "mapa_tempo")):
            trams_map = mapa_tempo.llegeix_mapa_tempo(
                os.path.join(d, NOM_MAPA_TEMPO))
            if len(trams_map) > 1:
                tm = TempoMap([tuple(t) for t in trams_map], offset=offset)
                if not tm.es_constant():
                    return tm
    except Exception:
        pass
    return None
NOM_MAPA_TEMPO = mapa_tempo.NOM_MAPA_TEMPO


# --- Marcadors (inici de compàs marcats a mà, en viu) -----------------------
NOM_MARCADORS = "marcadors.csv"


def desa_marcadors(carpeta, marques):
    """Desa els marcadors (una columna `t_s`) al projecte. Silenciós si falla."""
    if not carpeta:
        return None
    ruta = os.path.join(str(carpeta), NOM_MARCADORS)
    try:
        escriu_atomic(ruta, lambda f: _escriu_marcadors(f, marques))
    except OSError:
        return None
    return ruta


def _escriu_marcadors(f, marques):
    # Format nou (Fase 4): `t_s,tipus` (tipus = compas | seccio).
    f.write("t_s,tipus\n")
    for item in marques or ():
        if isinstance(item, (tuple, list)):
            t, tipus = item[0], item[1] if len(item) > 1 else "seccio"
        else:
            t, tipus = item, "seccio"
        f.write(f"{float(t):.6f},{tipus}\n")


def llegeix_marcadors(carpeta, durada=0.0):
    """Llig els marcadors del projecte (llista de temps en segons).

    Manté la signatura antiga (llista de floats) per compatibilitat. Els tipus
    es lliguen amb `llegeix_marcadors_tipus`.
    """
    from app import marcadors as _m
    if not carpeta:
        return []
    ruta = os.path.join(str(carpeta), NOM_MARCADORS)
    out = []
    try:
        with open(ruta, encoding="utf-8") as f:
            for linia in f:
                parts = linia.strip().split(",")
                text = parts[0]
                if not text or text.lower().startswith("t_"):
                    continue
                try:
                    out.append(float(text))
                except ValueError:
                    continue
    except OSError:
        return []
    return _m.normalitza_marcadors(out, float(durada or 1e9))


def llegeix_marcadors_tipus(carpeta):
    """Llig el mapa temps→tipus dels marcadors (buit si no n'hi ha)."""
    if not carpeta:
        return {}
    ruta = os.path.join(str(carpeta), NOM_MARCADORS)
    out = {}
    try:
        with open(ruta, encoding="utf-8") as f:
            for linia in f:
                parts = linia.strip().split(",")
                if not parts or parts[0].lower().startswith("t_"):
                    continue
                try:
                    t = float(parts[0])
                except ValueError:
                    continue
                tipus = parts[1].strip() if len(parts) > 1 else "seccio"
                if tipus not in ("compas", "seccio", "marcador"):
                    tipus = "marcador"
                out[round(t, 6)] = tipus
    except OSError:
        return {}
    return out


def desa_tempo_map(carpeta, trams):
    """Desa el mapa unificat (`mapa_tempo.csv`) d'una carpeta de projecte."""
    os.makedirs(carpeta, exist_ok=True)
    mapa_tempo.desa_mapa_tempo(os.path.join(carpeta, NOM_MAPA_TEMPO), trams)


def llegeix_tempo_map(carpeta, bpm, num, den, durada, log=None):
    """Llig `mapa_tempo.csv`; si no hi ha model, un sol tros constant.

    Els projectes amb el model antic (`tempo.csv` + `compas.csv`) es rebutgen:
    no hi ha migració. El resultat són `TramMapa`, de manera que el visor pot
    distingir els clips normals dels rubatos.
    """
    def _constant():
        net, avisos = tempo_map.neteja_trams(
            [(0.0, float(durada or 0.0), bpm, num, den)], durada)
        if log:
            for avís in avisos:
                log(f"Mapa de tempo: {avís}")
        return [mapa_tempo.des_de_tupla(t) for t in net]

    if not carpeta:
        return _constant()
    ruta = os.path.join(carpeta, NOM_MAPA_TEMPO)
    if mapa_tempo.te_format_antic(carpeta) and not os.path.isfile(ruta):
        raise ValueError(
            f"El projecte té el model antic ({mapa_tempo.NOM_CSV_TEMPO_ANTIC}"
            f" + {mapa_tempo.NOM_CSV_COMPAS_ANTIC}); no suportat. Cal recrear "
            "el mapa amb el model actual.")
    trams_map = mapa_tempo.llegeix_mapa_tempo(ruta, log=log)
    if not trams_map:
        return _constant()
    net, avisos = mapa_tempo.normalitza_trams_map(
        trams_map, durada, log=log, fusiona=True)
    if log:
        for avís in avisos:
            log(f"Mapa de tempo: {avís}")
    return net
