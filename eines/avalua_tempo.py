#!/usr/bin/env python3
"""Avalua tempo, compassos, beats i downbeats sobre un corpus local autoritzat."""

import argparse
import csv
import json
import math
import os
import statistics
import subprocess
import sys
import time
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import pipeline
from app.tempo_map import TempoMap

TOLERANCIA_COMPAS = 0.070
TOLERANCIA_ESDEVENIMENT = 0.070
COLUMNES = (
    "cançó", "bpm_referencia", "bpm_detectat", "error_bpm_pct",
    "compas_1_referencia_s", "compas_1_detectat_s", "error_downbeat_ms",
    "compassos_esperats", "compassos_detectats", "dins_70ms_pct",
    "sobrants", "absents", "error_maxim_ms", "deriva_ms",
    "beat_esperats", "beat_detectats", "beat_precisio", "beat_recall",
    "beat_f", "beat_error_mitja_ms", "beat_error_maxim_ms",
    "downbeat_esperats", "downbeat_detectats", "downbeat_precisio",
    "downbeat_recall", "downbeat_f", "downbeat_error_mitja_ms",
    "downbeat_error_maxim_ms", "temps_s", "error",
)


def _a_float(valor, camp):
    if isinstance(valor, bool) or not isinstance(valor, (int, float, str)):
        raise ValueError(f"{camp} ha de ser un número")
    try:
        return float(valor)
    except ValueError as e:
        raise ValueError(f"{camp} ha de ser un número") from e


def _a_int(valor, camp):
    if isinstance(valor, bool) or not isinstance(valor, (int, float, str)):
        raise ValueError(f"{camp} ha de ser un enter")
    try:
        resultat = int(valor)
    except (ValueError, OverflowError) as e:
        raise ValueError(f"{camp} ha de ser un enter") from e
    if isinstance(valor, float) and not valor.is_integer():
        raise ValueError(f"{camp} ha de ser un enter")
    return resultat


def _canvi_tempo(valor):
    if isinstance(valor, dict):
        camps = (valor.get("t", valor.get("inici_s")),
                 valor.get("bpm"), valor.get("num"), valor.get("den"))
    elif isinstance(valor, (list, tuple)) and len(valor) == 4:
        camps = valor
    else:
        raise ValueError("cada canvi de tempo ha de tindre t, bpm, num i den")
    t = _a_float(camps[0], "l'instant del canvi")
    bpm = _a_float(camps[1], "el BPM")
    num = _a_int(camps[2], "el numerador")
    den = _a_int(camps[3], "el denominador")
    if (not all(math.isfinite(x) for x in (t, bpm))
            or t < 0 or bpm <= 0 or num < 0 or den < 0
            or ((num == 0) != (den == 0))):
        raise ValueError(f"canvi de tempo invàlid: {valor!r}")
    return t, bpm, num, den


def _interval_rubato(valor):
    if isinstance(valor, dict):
        camps = (valor.get("inici_s", valor.get("inici")),
                 valor.get("fi_s", valor.get("fi")))
    elif isinstance(valor, (list, tuple)) and len(valor) == 2:
        camps = valor
    else:
        raise ValueError("cada rubato ha de tindre inici_s i fi_s")
    inici = _a_float(camps[0], "l'inici del rubato")
    fi = _a_float(camps[1], "la fi del rubato")
    if not math.isfinite(inici) or not math.isfinite(fi) or inici < 0 or fi <= inici:
        raise ValueError(f"interval de rubato invàlid: {valor!r}")
    return inici, fi


_CAMPS_TEMPS = (
    "time", "t", "inici_s", "beatTime", "downbeatTime",
    "odfPeakTime", "refinedAttackTime",
)


def _temps_referencia(dades, camp, durada, unics=True):
    """Llig una llista de temps (números o objectes) d'una anotació.

    Accepta els noms del model suggerit per la guia tècnica (`time`,
    `beatTime`, `downbeatTime`, `odfPeakTime`…) i els de les anotacions
    simples (`inici_s`). Retorna `None` si el camp no hi és.
    """
    valor = dades.get(camp)
    if valor is None and camp == "beats":
        beat_track = dades.get("beatTrack")
        if isinstance(beat_track, dict):
            valor = beat_track.get("beats")
    if valor is None:
        return None
    if not isinstance(valor, (list, tuple)):
        raise ValueError(f"«{camp}» ha de ser una llista de temps")

    temps = []
    for item in valor:
        if isinstance(item, dict):
            for clau in _CAMPS_TEMPS:
                if clau in item:
                    brut = item[clau]
                    break
            else:
                raise ValueError(
                    f"un element de «{camp}» no té cap camp de temps")
        else:
            brut = item
        t = _a_float(brut, f"un temps de «{camp}»")
        if not math.isfinite(t) or t < 0 or t > float(durada) + 1e-6:
            raise ValueError(f"temps fora de l'àudio a «{camp}»: {brut!r}")
        temps.append(t)
    temps.sort()
    if unics:
        for abans, despres in zip(temps, temps[1:]):
            if abs(despres - abans) < 1e-9:
                raise ValueError(f"«{camp}» té temps duplicats")
    return temps


def avalua_events(esperats, detectats, tolerancia=TOLERANCIA_ESDEVENIMENT):
    """Precisió, recall, F i error d'alineació amb emparellament un-a-un.

    Els temps de referència i els detectats s'ordenen i s'emparellen dins la
    tolerància. Els detectats sobrants i els esperats absents es compten com a
    errors, de manera que una graella massa densa no es premia.
    """
    esperats = sorted(float(t) for t in (esperats or ()))
    detectats = sorted(float(t) for t in (detectats or ()))
    tolerancia = float(tolerancia)
    if not math.isfinite(tolerancia) or tolerancia < 0:
        raise ValueError("la tolerància ha de ser finita i no negativa")
    if any(not math.isfinite(t) for t in esperats + detectats):
        raise ValueError("els temps dels esdeveniments han de ser finits")

    i = j = emparellats = 0
    errors = []
    while i < len(esperats) and j < len(detectats):
        error = detectats[j] - esperats[i]
        if abs(error) <= tolerancia:
            errors.append(error)
            emparellats += 1
            i += 1
            j += 1
        elif error < -tolerancia:
            j += 1
        else:
            i += 1

    n_esperats = len(esperats)
    n_detectats = len(detectats)
    if not n_esperats and not n_detectats:
        precisio = recall = f = None
    elif not n_esperats or not n_detectats:
        precisio = recall = f = 0.0
    else:
        precisio = emparellats / n_detectats
        recall = emparellats / n_esperats
        f = (2.0 * precisio * recall / (precisio + recall)
             if precisio + recall else 0.0)
    errors_abs = [abs(e) for e in errors]
    return {
        "esperats": n_esperats,
        "detectats": n_detectats,
        "emparellats": emparellats,
        "precisio": precisio,
        "recall": recall,
        "f": f,
        "error_mitja_s": (statistics.mean(errors_abs)
                          if errors_abs else None),
        "error_maxim_s": (max(errors_abs) if errors_abs else None),
    }


def compassos_referencia(dades, durada):
    """Deriva els downbeats de referència declarats per a una cançó."""
    durada = float(durada)
    if not math.isfinite(durada) or durada <= 0:
        raise ValueError("la durada de l'àudio ha de ser positiva")
    bpm_base = dades.get("bpm")
    num_base = dades.get("num", 4)
    den_base = dades.get("den", 4)
    if bpm_base is None:
        bpm_base = 120.0
    primer = _canvi_tempo((0, bpm_base, num_base, den_base))
    declarats = [_canvi_tempo(c) for c in dades.get("canvis", [])]
    canvis = declarats if declarats and declarats[0][0] == 0 else (
        [primer] + declarats)
    canvis.sort(key=lambda c: c[0])
    if len({c[0] for c in canvis}) != len(canvis):
        raise ValueError("hi ha canvis de tempo duplicats en el mateix instant")
    for canvi in canvis:
        t = canvi[0]
        if t >= durada:
            raise ValueError("un canvi de tempo queda fora de la durada de l'àudio")
    rubatos = [_interval_rubato(r) for r in dades.get("rubatos", [])]
    for inici, fi in rubatos:
        if inici >= durada:
            raise ValueError("un rubato comença fora de la durada de l'àudio")

    vores = {0.0, durada}
    vores.update(canvi[0] for canvi in canvis)
    for inici, fi in rubatos:
        vores.add(min(inici, durada))
        vores.add(min(fi, durada))
    vores = sorted(vores)

    trams = []
    j = 0
    for inici, fi in zip(vores, vores[1:]):
        if fi <= inici:
            continue
        mig = (inici + fi) / 2.0
        while j + 1 < len(canvis) and canvis[j + 1][0] <= mig:
            j += 1
        canvi = canvis[j]
        bpm, num, den = canvi[1], canvi[2], canvi[3]
        if any(a <= mig < b for a, b in rubatos):
            num, den = 0, 0
        trams.append((inici, fi, bpm, num, den))

    offset = float(dades.get("compas_1_s", 0.0))
    if not math.isfinite(offset):
        raise ValueError("compas_1_s ha de ser un temps finit")
    bars = [bar[1] for bar in TempoMap(trams, offset=offset).compassos()]
    return [t for t in bars
            if not any(inici <= t < fi for inici, fi in rubatos)]


def avalua_graella(esperats, detectats, tolerancia=TOLERANCIA_COMPAS):
    """Compara compassos amb emparellament temporal un-a-un."""
    esperats = sorted(float(t) for t in esperats)
    detectats = sorted(float(t) for t in detectats)
    tolerancia = float(tolerancia)
    if not math.isfinite(tolerancia) or tolerancia < 0:
        raise ValueError("la tolerància ha de ser finita i no negativa")
    if any(not math.isfinite(t) for t in esperats + detectats):
        raise ValueError("els temps dels compassos han de ser finits")

    i = j = 0
    errors = []
    sobrants = absents = 0
    while i < len(esperats) and j < len(detectats):
        error = detectats[j] - esperats[i]
        if abs(error) <= tolerancia:
            errors.append(error)
            i += 1
            j += 1
        elif error < -tolerancia:
            sobrants += 1
            j += 1
        else:
            absents += 1
            i += 1
    absents += len(esperats) - i
    sobrants += len(detectats) - j
    percentatge = (100.0 * len(errors) / len(esperats)
                   if esperats else None)
    residus = ([min(detectats, key=lambda t: abs(t - esperat)) - esperat
                for esperat in esperats] if detectats else [])
    error_maxim = max((abs(e) for e in residus), default=None)
    deriva = errors[-1] - errors[0] if errors else None
    return {
        "esperats": len(esperats),
        "detectats": len(detectats),
        "dins_tolerancia_pct": percentatge,
        "sobrants": sobrants,
        "absents": absents,
        "error_maxim_s": error_maxim,
        "deriva_s": deriva,
    }


def avalua_canço(ruta_anotacio, num=4, den=4, cada_compassos=4,
                  registre=None):
    """Executa els detectors actuals i retorna una fila de mètriques."""
    registre = registre or (
        lambda *missatges: print(*missatges, file=sys.stderr))
    with open(ruta_anotacio, encoding="utf-8") as f:
        dades = json.load(f)
    audio = dades.get("audio")
    if not isinstance(audio, str) or not audio.strip():
        raise ValueError("falta el camp «audio» en l'anotació")
    ruta_audio = os.path.abspath(os.path.join(
        os.path.dirname(os.path.abspath(ruta_anotacio)), audio))
    if not os.path.isfile(ruta_audio):
        raise FileNotFoundError(f"no existeix l'àudio anotat: {ruta_audio}")
    durada = float(pipeline.wav_info(ruta_audio)["durada"])
    esperats = compassos_referencia(dades, durada)
    beats_ref = _temps_referencia(dades, "beats", durada)
    downbeats_ref = _temps_referencia(dades, "downbeats", durada)
    # Els onsets encara no es puntuen, però es validen perquè el schema siga
    # estable i els errors d'anotació es detecten abans de comparar motors.
    _temps_referencia(dades, "onsets", durada, unics=False)
    canvis = [_canvi_tempo(c) for c in dades.get("canvis", [])]
    bpm_ref = float(dades.get(
        "bpm", canvis[0][1] if canvis else 120.0))
    downbeat_ref = float(dades.get("compas_1_s", 0.0))
    inici = time.perf_counter()
    bpm = pipeline.detecta_bpm(ruta_audio, registre)
    downbeat = pipeline.detecta_compas1(ruta_audio, registre)

    sig = next(((canvi[2], canvi[3]) for canvi in canvis
                if canvi[2] > 0 and canvi[3] > 0),
               (int(dades.get("num", num)), int(dades.get("den", den))))
    mapa_detectat = pipeline.detecta_tempo_per_trams(
        ruta_audio, registre, durada, num=sig[0], den=sig[1],
        cada_compassos=cada_compassos, offset=downbeat)
    trams, offset = mapa_detectat[0], mapa_detectat[1]
    detectats = ([bar[1] for bar in
                  TempoMap(trams, offset=offset).compassos()]
                 if trams else [])
    graella = avalua_graella(esperats, detectats)

    beat_met = None
    if beats_ref:
        beats_detectats = pipeline.detecta_beats(ruta_audio, registre)
        beat_met = avalua_events(beats_ref, beats_detectats)
    downbeat_met = (avalua_events(downbeats_ref, detectats)
                    if downbeats_ref else None)
    elapsed = time.perf_counter() - inici

    def _met(metrica, clau):
        return metrica[clau] if metrica else None

    def _ms(metrica, clau):
        valor = _met(metrica, clau)
        return 1000.0 * valor if valor is not None else None
    err_bpm = (100.0 * (float(bpm) - bpm_ref) / bpm_ref
               if bpm is not None and bpm_ref else None)
    err_downbeat = (1000.0 * (float(downbeat) - downbeat_ref)
                    if downbeat is not None else None)
    return {
        "cançó": os.path.basename(ruta_audio),
        "bpm_referencia": bpm_ref,
        "bpm_detectat": bpm,
        "error_bpm_pct": err_bpm,
        "compas_1_referencia_s": downbeat_ref,
        "compas_1_detectat_s": downbeat,
        "error_downbeat_ms": err_downbeat,
        "compassos_esperats": graella["esperats"],
        "compassos_detectats": graella["detectats"],
        "dins_70ms_pct": graella["dins_tolerancia_pct"],
        "sobrants": graella["sobrants"],
        "absents": graella["absents"],
        "error_maxim_ms": (1000.0 * graella["error_maxim_s"]
                           if graella["error_maxim_s"] is not None else None),
        "deriva_ms": (1000.0 * graella["deriva_s"]
                      if graella["deriva_s"] is not None else None),
        "beat_esperats": _met(beat_met, "esperats"),
        "beat_detectats": _met(beat_met, "detectats"),
        "beat_precisio": _met(beat_met, "precisio"),
        "beat_recall": _met(beat_met, "recall"),
        "beat_f": _met(beat_met, "f"),
        "beat_error_mitja_ms": _ms(beat_met, "error_mitja_s"),
        "beat_error_maxim_ms": _ms(beat_met, "error_maxim_s"),
        "downbeat_esperats": _met(downbeat_met, "esperats"),
        "downbeat_detectats": _met(downbeat_met, "detectats"),
        "downbeat_precisio": _met(downbeat_met, "precisio"),
        "downbeat_recall": _met(downbeat_met, "recall"),
        "downbeat_f": _met(downbeat_met, "f"),
        "downbeat_error_mitja_ms": _ms(downbeat_met, "error_mitja_s"),
        "downbeat_error_maxim_ms": _ms(downbeat_met, "error_maxim_s"),
        "temps_s": elapsed,
        "error": "",
    }


def escriu_csv(ruta, files):
    carpeta = os.path.dirname(os.path.abspath(ruta))
    os.makedirs(carpeta, exist_ok=True)
    temporal = ruta + ".tmp"
    try:
        with open(temporal, "w", encoding="utf-8", newline="") as f:
            escriptor = csv.DictWriter(f, fieldnames=COLUMNES)
            escriptor.writeheader()
            escriptor.writerows(files)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporal, ruta)
    finally:
        if os.path.exists(temporal):
            os.unlink(temporal)


def resum(files):
    valid = [f for f in files if not f["error"]]
    bpm = [abs(float(f["error_bpm_pct"])) for f in valid
           if f["error_bpm_pct"] is not None]
    downbeat = [abs(float(f["error_downbeat_ms"])) for f in valid
                if f["error_downbeat_ms"] is not None]
    percentatges = [float(f["dins_70ms_pct"]) for f in valid
                    if f["dins_70ms_pct"] is not None]
    beat_f = [float(f["beat_f"]) for f in valid
              if f["beat_f"] is not None]
    downbeat_f = [float(f["downbeat_f"]) for f in valid
                  if f["downbeat_f"] is not None]
    beat_error = [float(f["beat_error_mitja_ms"]) for f in valid
                  if f["beat_error_mitja_ms"] is not None]
    downbeat_error = [float(f["downbeat_error_mitja_ms"]) for f in valid
                      if f["downbeat_error_mitja_ms"] is not None]
    if not valid:
        return "Sense dades d'àudio avaluades."
    return (
        f"Cançons avaluades: {len(valid)}; fallides: {len(files) - len(valid)}; "
        f"error BPM absolut mitjà: "
        f"{statistics.mean(bpm):.2f}%"
        if bpm else f"Cançons: {len(valid)}; BPM: sense dades"
    ) + (
        f"; error compàs 1 mitjà: {statistics.mean(downbeat):.1f} ms"
        if downbeat else "; compàs 1: sense dades"
    ) + (
        f"; compassos dins ±70 ms: {statistics.mean(percentatges):.1f}%"
        if percentatges else "; graella: sense dades"
    ) + (
        f"; beat F mitjà: {statistics.mean(beat_f):.3f}"
        if beat_f else "; beat F: sense dades"
    ) + (
        f"; error beat mitjà: {statistics.mean(beat_error):.1f} ms"
        if beat_error else "; error beat: sense dades"
    ) + (
        f"; downbeat F mitjà: {statistics.mean(downbeat_f):.3f}"
        if downbeat_f else "; downbeat F: sense dades"
    ) + (
        f"; error downbeat mitjà: {statistics.mean(downbeat_error):.1f} ms"
        if downbeat_error else "; error downbeat: sense dades"
    )


def prova_sintetica():
    """Comprova la mètrica de graella sense àudio ni plugins."""
    dades = {
        "bpm": 120,
        "compas_1_s": 0.0,
        "num": 4,
        "den": 4,
        "canvis": [[8.0, 100, 4, 4]],
        "rubatos": [[16.0, 18.0]],
    }
    esperats = compassos_referencia(dades, 24.0)
    resultat = avalua_graella(esperats, esperats, 0.070)
    if (resultat["esperats"] < 5 or resultat["absents"]
            or resultat["sobrants"]
            or resultat["dins_tolerancia_pct"] != 100.0):
        raise AssertionError(f"avaluació sintètica incorrecta: {resultat}")
    shifted = avalua_graella(esperats, [t + 0.1 for t in esperats])
    if shifted["dins_tolerancia_pct"] != 0.0:
        raise AssertionError(f"tolerància sintètica incorrecta: {shifted}")
    empty = avalua_graella([], [])
    if empty["dins_tolerancia_pct"] is not None:
        raise AssertionError(f"cas buit incorrecte: {empty}")

    events = avalua_events([0.0, 1.0, 2.0],
                           [0.01, 1.02, 2.30], 0.070)
    if (events["emparellats"] != 2
            or abs(events["f"] - 2.0 / 3.0) > 1e-12):
        raise AssertionError(f"beat F sintètic incorrecte: {events}")
    shifted_events = avalua_events(
        [0.0, 1.0, 2.0], [0.1, 1.1, 2.1], 0.070)
    if shifted_events["f"] != 0.0:
        raise AssertionError(
            f"tolerància de beat sintètica incorrecta: {shifted_events}")
    empty_events = avalua_events([], [])
    if empty_events["f"] is not None:
        raise AssertionError(f"cas buit de beat incorrecte: {empty_events}")
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", help="directori local amb anotacions *.tempo.json")
    parser.add_argument("--csv", default="resultats_tempo.csv",
                        help="ruta del CSV de resultats")
    parser.add_argument("--num", type=int, default=4,
                        help="numerador per defecte del mapa detectat")
    parser.add_argument("--den", type=int, default=4,
                        help="denominador per defecte del mapa detectat")
    parser.add_argument("--cada-compassos", type=int, default=4,
                        help="grandària dels blocs del detector de mapa")
    parser.add_argument("--prova-sintetica", action="store_true",
                        help="prova les mètriques sense àudio ni plugins")
    args = parser.parse_args(argv)
    if args.prova_sintetica:
        prova_sintetica()
        print("Prova sintètica correcta; cap àudio real utilitzat.")
        return 0
    if not args.corpus:
        parser.error("cal indicar --corpus o --prova-sintetica")
    if args.num <= 0 or args.den <= 0 or args.cada_compassos <= 0:
        parser.error("--num, --den i --cada-compassos han de ser positius")

    corpus = os.path.abspath(args.corpus)
    anotacions = []
    if os.path.isdir(corpus):
        for entrada in os.walk(corpus):
            arrel, noms = entrada[0], entrada[2]
            anotacions.extend(os.path.join(arrel, nom) for nom in noms
                              if nom.endswith(".tempo.json"))
    anotacions.sort()
    if not anotacions:
        print("Sense dades: no s'han trobat fitxers *.tempo.json al corpus.")
        return 0

    files = []
    for ruta in anotacions:
        try:
            files.append(avalua_canço(
                ruta, num=args.num, den=args.den,
                cada_compassos=args.cada_compassos,
                registre=lambda missatge: print(missatge, file=sys.stderr)))
        except (OSError, ValueError, RuntimeError, wave.Error,
                subprocess.SubprocessError) as e:
            files.append(dict.fromkeys(COLUMNES))
            files[-1].update({
                "cançó": os.path.basename(ruta),
                "error": str(e),
            })
            print(f"ERROR {ruta}: {e}", file=sys.stderr)
    print(resum(files))
    escriu_csv(args.csv, files)
    print(f"Resultats CSV: {os.path.abspath(args.csv)}")
    return 1 if any(f["error"] for f in files) else 0


if __name__ == "__main__":
    raise SystemExit(main())
