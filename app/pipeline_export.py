"""Exportació de WAVs silenciosos i paquet complet (F1).

Extret de `app/pipeline.py`: WAVs d'acords, manifest i `exporta_total`.
"""
import csv
import os
import wave

from . import bpm_unit as _bpm_unit
from .pipeline_derivats import (
    _segments_guia_daw, segments_export, genera_guia_html,
)
from .pipeline_estructura import (
    desa_abc_csv, fer_abc, fer_wavs_estructura, segments_lliures,
)
from .pipeline_io import (
    safe_filename, escriu_atomic, desa_acords_csv, neteja_wavs,
)
from .pipeline_mapa import desa_tempo_map
from . import tempo_midi
from .pipeline_model import (
    FORAT_ACORD, clips_d_acords, normalitza_clips, normalitza_cobertura,
)

def fer_wavs_acords_lliures(csv_path, total_s, dest_dir, sr, log,
                            manifest=None):
    os.makedirs(dest_dir, exist_ok=True)
    n = 0
    usats = set()          # desambigua noms d'acord que quedin iguals
    for ini, fi, chord in segments_lliures(csv_path, total_s, log):
        frames = int(round((fi - ini) * sr))
        if frames <= 0:
            # Mai escriure un WAV de durada 0 (un xoc d'inicis a la resolució
            # del CSV, o un acord a tocar del final, el produiria).
            log(f"wavs_acords: segment {ini:.6f}–{fi:.6f}s ({chord}) de durada "
                f"0 → s'omet")
            continue
        fn = (f"{ini:08.3f}s_{fi:08.3f}s_"
              f"{safe_filename(chord, fallback='N', usats=usats)}.wav")
        with wave.open(os.path.join(dest_dir, fn), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(b"\x00" * (frames * 2))
        if manifest is not None:
            manifest.append(("acord", fn, ini, fi, fi - ini, chord,
                             f"{ini:.3f}s"))
        n += 1
    log(f"wavs_acords: {n}")
    return n


def fer_wavs_acords(segments, dest_dir, sr, log, manifest=None):
    """WAVs silenciosos d'acords amb durades EXACTES.

    `segments` = `[(posicio_1/32, acord, ini_s, fi_s)]` (vegeu
    `segments_export`). El nom conserva la posició musical `1-1-1`; la durada
    del WAV surt dels segons exactes, no de la graella. Si es passa `manifest`,
    s'hi afegeix una fila per cada WAV amb els temps exactes.
    """
    os.makedirs(dest_dir, exist_ok=True)
    n = 0
    usats = set()          # desambigua noms d'acord que quedin iguals
    usats_pos = set()      # desambigua posicions que caiguen a la mateixa 1/32
    for pos_, chord, ini, fi in segments or ():
        ini, fi = float(ini), float(fi)
        frames = int(round((fi - ini) * sr))
        if frames <= 0:
            log(f"wavs_acords: segment {ini:.6f}–{fi:.6f}s ({chord}) de "
                f"durada 0 → s'omet")
            continue
        fn = (f"{pos_.replace('.', '-')}_"
              f"{safe_filename(chord, fallback='N', usats=usats)}.wav")
        base = fn
        k = 2
        while fn in usats_pos:
            fn = base[:-4] + f"_{k}.wav"
            k += 1
        usats_pos.add(fn)
        with wave.open(os.path.join(dest_dir, fn), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(b"\x00" * (frames * 2))
        if manifest is not None:
            manifest.append(("acord", fn, ini, fi, fi - ini, chord, pos_))
        n += 1
    log(f"wavs_acords: {n}")
    return n


CAPÇALERA_MANIFEST = (
    "tipus", "fitxer", "inici_s", "fi_s", "durada_s", "contingut", "posicio",
    "bpm_quarter", "beat_unit", "bpm_mostra",
)


def _mapa_export(mapa_tempo):
    """Normalitza `mapa_tempo` a un `TempoMap` (o `None`).

    Accepta el `TempoMap` viu del visor o una llista de `TramMapa`/tuples.
    """
    if mapa_tempo is None:
        return None
    if (hasattr(mapa_tempo, "bpm") and hasattr(mapa_tempo, "unitat")
            and hasattr(mapa_tempo, "tram")):
        return mapa_tempo
    try:
        from .tempo_map import TempoMap
        trams = list(mapa_tempo)
        return TempoMap(trams) if trams else None
    except (TypeError, ValueError, IndexError):
        return None


def enriqueix_manifest(manifest, mapa_tempo=None, bpm=120.0,
                       beat_unit="negra"):
    """Completa files de `manifest.csv` amb el BPM/unitat del segment.

    Les files d'entrada són les 7 columnes històriques
    `(tipus, fitxer, ini_s, fi_s, durada_s, contingut, posicio)`. S'hi afigen
    `bpm_quarter`, `beat_unit` i `bpm_mostra` calculats a l'**inici** de cada
    segment (`ini_s`), amb el mapa de tempo/compàs com a font canònica. Si no
    hi ha mapa, s'usa el `bpm` i el `beat_unit` de fallback (transport).

    És una funció **pura**: no muta l'entrada i retorna una llista nova. Les
    files que ja porten 10 camps es retornen tal qual (idempotent).
    """
    mapa = _mapa_export(mapa_tempo)
    fallback_unit = _bpm_unit.normalitza(beat_unit)
    fallback_bpm = float(bpm)
    out = []
    for fila in manifest or ():
        vals = list(fila)
        if len(vals) >= 10:
            out.append(tuple(vals[:10]))
            continue
        # Completa fins a 7 (una fila curta no ha de fer petar l'export).
        if len(vals) < 7:
            vals += [""] * (7 - len(vals))
        try:
            ini = float(vals[2])
        except (TypeError, ValueError):
            ini = 0.0
        if mapa is not None:
            bq = float(mapa.bpm(ini))
            unit = mapa.unitat(ini)
        else:
            bq = fallback_bpm
            unit = fallback_unit
        mostra = _bpm_unit.de_quarter(bq, unit)
        out.append(tuple(vals[:7]) + (bq, unit, mostra))
    return out


def escriu_manifest(ruta, files):
    """Escriu `manifest.csv` amb els temps EXACTES de cada WAV exportat.

    `files`: files de 7 camps
    `(tipus, fitxer, ini_s, fi_s, durada_s, contingut, posicio)` o de 10, amb
    `bpm_quarter`, `beat_unit` i `bpm_mostra` al final. Les files de 7 camps
    s'escriuen amb els tres extres buits (compatibilitat). Els temps i els BPM
    es desen amb 6 decimals (1 µs), igual que el MODEL.
    """
    def _fmt(valor):
        if valor in (None, ""):
            return ""
        try:
            return f"{float(valor):.6f}"
        except (TypeError, ValueError):
            return str(valor)

    def _escriu(f):
        w = csv.writer(f)
        w.writerow(CAPÇALERA_MANIFEST)
        for fila in files:
            vals = list(fila)
            if len(vals) < 7:
                vals += [""] * (7 - len(vals))
            base = [vals[0], vals[1], _fmt(vals[2]), _fmt(vals[3]),
                    _fmt(vals[4]), vals[5], vals[6]]
            extres = list(vals[7:10]) + [""] * max(0, 10 - len(vals))
            base += [_fmt(extres[0]), extres[1], _fmt(extres[2])]
            w.writerow(base[:10])
    escriu_atomic(ruta, _escriu)
    return ruta


def exporta_total(csv_ac, csv_seg, sortida, bpm, bpb, sr, log,
                 tempo_fix=True, amb_estructura=True, total_s=None,
                 acords=None, seccions=None, mapa_tempo=None, den=4,
                 beat_unit=None, bpm_unit=None, marques=None):
    """Exporta el flux complet.

    Si es passen `acords`/`seccions` (el **model VIU** del visor), s'usen ELLS
    per sobre dels CSV del disc: es re-escriuen els CSV (acords + estructura)
    ja **normalitzats** amb l'invariant de COBERTURA, de manera que l'export
    **no perd les edicions manuals** (finals de secció, capçalera «N», etc.).
    Si no es passen, es comporta exactament com abans (llegeix els CSV).

    `mapa_tempo` = els trossos del mapa de BPM/compàs del **model viu**. Amb ell,
    el paquet exportat tracta els **tres tipus igual** (regla d'or #12): a més
    d'`acords.csv` + `wavs_acords/` i `estructura_ABC.csv` + `wavs_estructura/`,
    el mapa té la seva **carpeta pròpia** `mapa_tempo/` amb `mapa_tempo.csv`
    (el seu derivat, igual que els altres dos).

    Retorna un diccionari amb les rutes finals (csv + carpetes).
    """
    sortida = os.path.abspath(sortida)
    os.makedirs(sortida, exist_ok=True)
    csv_ac = os.path.abspath(csv_ac)
    unit_defecte = _bpm_unit.normalitza(
        beat_unit or bpm_unit) if (beat_unit or bpm_unit) else (
            _bpm_unit.unitat_per_defecte(bpb, den))
    mapa_viu = _mapa_export(mapa_tempo)
    # (A)+(B) Si ens donen el MODEL, mana ell: normalitzem la cobertura i
    # re-escrivim el CSV d'acords ABANS de comprovar-lo/fer-lo servir.
    if acords is not None or seccions is not None:
        durada = float(total_s or 0.0)
        if acords is not None:
            clips = normalitza_clips(
                clips_d_acords(acords, durada), durada, FORAT_ACORD,
                arrodoneix=True, deriva_fi=True, log=log)
            desa_acords_csv(csv_ac, clips, durada)
        if seccions is not None:
            _, seccions = normalitza_cobertura([], seccions, durada, log=log)
    if not os.path.isfile(csv_ac):
        raise FileNotFoundError(f"No trobo acords.csv: {csv_ac}")

    result = {"acords_csv": csv_ac, "sortida": sortida}
    manifest = []
    if tempo_fix:
        dades_guia = _segments_guia_daw(csv_ac, bpm, bpb,
                                        durada=total_s, mapa=mapa_viu, den=den)
        segs = segments_export(csv_ac, bpm, bpb,
                               durada=total_s, mapa=dades_guia[4], den=den)
        guia = genera_guia_html(csv_ac, bpm, bpb, workdir=sortida,
                                durada=total_s, log=log, _dades=dades_guia,
                                den=den, beat_unit=unit_defecte,
                                bpm_unit=unit_defecte)
        result["guia_html"] = guia
        dest = os.path.join(sortida, "wavs_acords")
        neteja_wavs(dest)
        result["n_acords_wavs"] = fer_wavs_acords(
            segs, dest, sr, log, manifest=manifest)
    else:
        if total_s is None:
            total_s = 0.0
            with open(csv_ac, encoding="utf-8") as f:
                for row in csv.reader(f):
                    if not row or row[0].startswith(("posici", "inici")):
                        continue
                    try:
                        total_s = max(total_s, float(row[0]))
                    except ValueError:
                        pass
        dest = os.path.join(sortida, "wavs_acords")
        neteja_wavs(dest)
        result["n_acords_wavs"] = fer_wavs_acords_lliures(
            csv_ac, total_s, dest, sr, log, manifest=manifest)

    if amb_estructura and (seccions is not None or csv_seg):
        abc = os.path.join(sortida, "estructura_ABC.csv")
        result["abc_csv"] = abc
        if seccions is not None:
            # (A) Seccions DEL MODEL (edició en viu): NO es reconstrueix l'ABC
            # des de `segments.csv` (que és el resultat CRU de l'anàlisi), sinó
            # del model editat → les edicions de seccions no es perden.
            desa_abc_csv(abc, seccions, bpm, log, lliure=not tempo_fix,
                         bpb=bpb)
            result["segments_csv"] = None
        else:
            csv_seg = os.path.abspath(csv_seg)
            if not os.path.isfile(csv_seg):
                raise FileNotFoundError(f"No trobo segments.csv: {csv_seg}")
            result["segments_csv"] = csv_seg
            fer_abc(csv_seg, abc, bpm, log, lliure=not tempo_fix, bpb=bpb,
                    durada=total_s)
        dest_abc = os.path.join(sortida, "wavs_estructura")
        neteja_wavs(dest_abc)
        result["n_estructura_wavs"] = fer_wavs_estructura(
            abc, dest_abc, sr, log, manifest=manifest)

    # Regla d'or #12 (paritat a l'exportació): el mapa de BPM/compàs també surt
    # al paquet, amb la seva carpeta pròpia, com els altres dos tipus.
    if mapa_tempo:
        # No convertir a tuples: es perdrien `tipus`/`compassos` dels rubatos.
        trams = list(mapa_tempo)
        dest_mapa = os.path.join(sortida, "mapa_tempo")
        desa_tempo_map(dest_mapa, trams)
        result["mapa_tempo_dir"] = dest_mapa
        result["n_mapa_trams"] = len(trams)
        result["mapa_tempo_midi"] = tempo_midi.desa_mapa_midi(
            os.path.join(dest_mapa, tempo_midi.NOM_MAPA_MIDI), trams,
            marques=marques or (), log=log)
        rubatos = [t for t in trams
                   if getattr(t, "tipus", None) == "rubato"]
        if rubatos:
            ruta_avis = os.path.join(dest_mapa, "AVIS_APROXIMACIO.txt")

            def _escriu_avis(f):
                f.write(
                    "RUBATO — TRAMS MARCADES PER A NOTACIÓ\n"
                    "=====================================\n\n"
                    "El rubato només canvia la notació/exportació; el tempo\n"
                    "i els compassos són els mateixos que els d'un tram normal.\n\n"
                    "inici_s\tfi_s\tbpm\tcompassos\n")
                for tr in rubatos:
                    f.write(f"{float(tr.ini):.6f}\t{float(tr.fi):.6f}\t"
                            f"{float(tr.bpm):.6f}\t{tr.compassos}\n")
            escriu_atomic(ruta_avis, _escriu_avis)
            result["mapa_tempo_avis"] = ruta_avis
            if log:
                log(f"mapa de tempo/compàs: {len(rubatos)} rubato(s) marcats")
        if log:
            log(f"mapa de tempo/compàs exportat: {len(trams)} tram(s) a "
                f"{dest_mapa}")

    if manifest:
        manifest = enriqueix_manifest(
            manifest, mapa_viu, bpm=bpm, beat_unit=unit_defecte)
        result["manifest_csv"] = escriu_manifest(
            os.path.join(sortida, "manifest.csv"), manifest)
        if log:
            log(f"manifest: {len(manifest)} fila(es) amb temps exactes")

    return result








# --- Mapa de TEMPO i COMPÀS (model unificat `mapa_tempo.csv`) --------
# Un sol fitxer, amb una fila per tram:
#   inici,fi,bpm,tipus,compassos,agrupacio,n
# `tipus` = normal | rubato; `compassos` = `4/4` o `4/4*3+3/4`.




def regenera_wavs_acords(csv_path, sortida, bpm, bpb, total_s, sr, log,
                         tempo_fix=True, manifest=None, den=4, mapa=None,
                         beat_unit=None, bpm_unit=None):
    # Recalcula guia + wavs_acords/ a partir del csv ja editat.
    dest = os.path.join(sortida, "wavs_acords")
    neteja_wavs(dest)
    if tempo_fix:
        dades_guia = _segments_guia_daw(csv_path, bpm, bpb,
                                        durada=total_s, mapa=mapa, den=den)
        segs = segments_export(csv_path, bpm, bpb,
                               durada=total_s, mapa=dades_guia[4], den=den)
        genera_guia_html(csv_path, bpm, bpb, workdir=sortida,
                         durada=total_s, log=log, _dades=dades_guia, den=den,
                         beat_unit=beat_unit, bpm_unit=bpm_unit)
        return fer_wavs_acords(segs, dest, sr, log, manifest=manifest)
    return fer_wavs_acords_lliures(csv_path, total_s, dest, sr, log,
                                   manifest=manifest)
