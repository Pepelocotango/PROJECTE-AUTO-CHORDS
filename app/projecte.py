#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Projectes d'AUTO CHORDS — carpeta **autocontinguda**, com un DAW.

Un **projecte** és una carpeta que ho conté tot::

    La meva cançó/                 ← la carpeta del projecte (portable)
    ├── La meva cançó.acproj       ← el document (JSON, amb «versió de format»)
    ├── audio/ tema.wav            ← CÒPIA de l'àudio (mai depèn de fora)
    ├── acords.csv                 ← el model (font de veritat)
    ├── estructura_ABC.csv         ← el model (font de veritat)
    ├── wavs_acords/ …             ← exports (els crea `pipeline.exporta_total`)
    └── backup/ …                  ← còpies versionades

En crear un projecte **copiem l'àudio a `audio/`** (sempre): així la carpeta es
pot renombrar o moure sencera —o es pot esborrar el fitxer original— i el
projecte continua obrint-se **exactament igual**. No hi ha cap ruta absoluta cap
a fora del projecte.

Tot en català. Només biblioteca estàndard (sense AVX).
"""
from __future__ import annotations

import copy
import json
import os
import shutil
from datetime import datetime

from app import pipeline

EXT = ".acproj"
FORMAT = 1
NOM_AUDIO_DIR = "audio"
NOM_BACKUP_DIR = "backup"
NOM_CSV_ACORDS = "acords.csv"
NOM_CSV_ESTRUCTURA = "estructura_ABC.csv"
MAX_BACKUPS = 10


class ProjecteError(Exception):
    """Error en crear, obrir o desar un projecte."""


def _ara():
    return datetime.now().replace(microsecond=0).isoformat()


def _timestamp():
    # Amb MICROSEGONS: noms únics i que ORDENEN cronològicament encara que es
    # facin moltes còpies dins el mateix segon (abans, el sufix «-2/-3…» feia
    # que l'ordre lexicogràfic fos incorrecte a partir de «-10»).
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f")


def _acproj_de_carpeta(carpeta):
    """Retorna el `.acproj` de `carpeta`, o `None` (si n'hi ha 0 o més d'1)."""
    try:
        fits = [f for f in os.listdir(carpeta) if f.endswith(EXT)]
    except OSError:
        return None
    if len(fits) != 1:
        return None
    return os.path.join(carpeta, fits[0])


def troba_acproj(ruta):
    """Troba el `.acproj` a partir d'un fitxer o d'una carpeta (o `None`).

    Accepta: un `.acproj`, la carpeta del projecte, o un WAV (mira la carpeta
    de projecte que tindria al costat — `AUTOCHORDS_<nom>/`).
    """
    if not ruta:
        return None
    if os.path.isfile(ruta):
        if ruta.endswith(EXT):
            return os.path.abspath(ruta)
        carp = pipeline.carpeta_sortida(ruta)      # WAV -> carpeta al costat
        return _acproj_de_carpeta(carp) if os.path.isdir(carp) else None
    if os.path.isdir(ruta):
        return _acproj_de_carpeta(ruta)
    return None


def es_projecte(ruta):
    """Cert si `ruta` és un `.acproj` o una carpeta de projecte."""
    return troba_acproj(ruta) is not None


class Projecte:
    """Un projecte d'AUTO CHORDS (carpeta autocontinguda + document `.acproj`)."""

    def __init__(self, carpeta, dades, ruta_acproj=None):
        self.carpeta = os.path.abspath(carpeta)
        self.dades = dades
        self._ruta = ruta_acproj

    # -- propietats -----------------------------------------------------
    @property
    def nom(self):
        return self.dades.get("nom") or os.path.basename(self.carpeta)

    @property
    def ruta_acproj(self):
        return self._ruta or os.path.join(self.carpeta, self.nom + EXT)

    def ruta(self, *parts):
        return os.path.join(self.carpeta, *parts)

    def ruta_audio(self):
        rel = self.dades.get("audio") or ""
        return os.path.join(self.carpeta, rel) if rel else ""

    def audio_present(self):
        r = self.ruta_audio()
        return bool(r) and os.path.isfile(r)

    def ruta_csv_acords(self):
        return self.ruta(NOM_CSV_ACORDS)

    def ruta_csv_estructura(self):
        return self.ruta(NOM_CSV_ESTRUCTURA)

    # -- creació --------------------------------------------------------
    @classmethod
    def crea(cls, carpeta, wav_origen, nom=None, bpm=120.0, bpb=4, offset=0.0,
             fix=False, opcions=None, vista=None, csv_acords=None,
             csv_estructura=None, permet_existent=False, compas=None):
        """Crea una carpeta de projecte AUTOCONTINGUDA a partir d'un WAV.

        - **Copia l'àudio a `audio/`** (sempre): el projecte no depèn de fora.
        - Opcionalment importa CSVs ja existents (migració).
        - Escriu el `.acproj` **atomicament** (últim pas).

        `permet_existent=True` és per a la **migració** (carpeta ja amb
        contingut, p. ex. una `AUTOCHORDS_<nom>/` antiga).
        """
        if not wav_origen or not os.path.isfile(wav_origen):
            raise ProjecteError(f"l'àudio no existeix: {wav_origen!r}")
        carpeta = os.path.abspath(carpeta)
        # MAI sobreescriure un projecte existent (té `.acproj`): perdria el
        # document (tempo/vista). Especialment en migració in situ.
        if _acproj_de_carpeta(carpeta) is not None:
            raise ProjecteError(f"ja hi ha un projecte a {carpeta!r}")
        if not permet_existent and os.path.isdir(carpeta) and os.listdir(carpeta):
            raise ProjecteError(
                f"la carpeta {carpeta!r} ja té contingut i no és buida")
        nom = (nom or os.path.basename(carpeta)).strip() or "Projecte"
        os.makedirs(carpeta, exist_ok=True)
        audio_dir = os.path.join(carpeta, NOM_AUDIO_DIR)
        os.makedirs(audio_dir, exist_ok=True)
        dest_wav = os.path.join(audio_dir, os.path.basename(wav_origen))
        if os.path.abspath(dest_wav) != os.path.abspath(wav_origen):
            shutil.copy2(wav_origen, dest_wav)
        # Importa CSVs existents (migració), sense copiar-se a si mateixos.
        csv_a = cls._csv(carpeta, NOM_CSV_ACORDS)
        csv_s = cls._csv(carpeta, NOM_CSV_ESTRUCTURA)
        for origen, desti in ((csv_acords, csv_a), (csv_estructura, csv_s)):
            if origen and os.path.isfile(origen) and \
                    os.path.abspath(origen) != os.path.abspath(desti):
                shutil.copy2(origen, desti)
        # MODEL INICIAL COMPLET: un projecte acabat de crear ja serveix per
        # treballar i exportar **sense cap anàlisi** (decisió de l'operador,
        # 2026-10-19). Els CSVs cobreixen tota la cançó (regla d'or #4) i el
        # mapa de tempo/compàs també hi és des del primer moment.
        try:
            durada = float(pipeline.wav_info(dest_wav)["durada"])
        except Exception:  # noqa: BLE001  (wav il·legible: model de durada 0)
            durada = 0.0
        if not os.path.isfile(csv_a):
            pipeline.desa_acords_csv(
                csv_a, [pipeline.Clip(0.0, durada, pipeline.FORAT_ACORD)],
                durada)
        if not os.path.isfile(csv_s):
            pipeline.desa_abc_csv(
                csv_s, [(0.0, durada, "A", "A")], float(bpm),
                lambda *_a: None, lliure=not fix, bpb=int(bpb),
                offset=float(offset))
        den = 4
        if compas and "/" in str(compas):
            try:
                den = int(str(compas).split("/", 1)[1])
            except (TypeError, ValueError):
                den = 4
        pipeline.desa_tempo_map(
            carpeta, [(0.0, durada, float(bpm), int(bpb), int(den or 4))])
        dades = {
            "format": FORMAT,
            "app": "AUTO_CHORDS",
            "nom": nom,
            "creat": _ara(),
            "audio": os.path.join(NOM_AUDIO_DIR, os.path.basename(dest_wav)),
            "tempo": {"bpm": float(bpm), "bpb": int(bpb),
                      "offset": float(offset), "fix": bool(fix),
                      "compas": str(compas).strip() if compas else ""},
            "opcions": copy.deepcopy(opcions) if opcions else {},
            "vista": copy.deepcopy(vista) if vista else {},
        }
        p = cls(carpeta, dades)
        p.desa()
        return p

    @staticmethod
    def _csv(carpeta, nom):
        return os.path.join(carpeta, nom)

    # -- lectura --------------------------------------------------------
    @classmethod
    def obre(cls, ruta):
        """Obre un projecte a partir d'una carpeta o d'un `.acproj`."""
        ap = troba_acproj(ruta)
        if not ap:
            raise ProjecteError(f"no hi ha cap projecte a {ruta!r}")
        try:
            with open(ap, encoding="utf-8") as f:
                dades = json.load(f)
        except (OSError, ValueError) as e:
            raise ProjecteError(f"no puc llegir el projecte {ap!r}: {e}") from e
        if not isinstance(dades, dict):
            raise ProjecteError(f"el projecte {ap!r} no és vàlid")
        dades = _migra(dades, ap)
        return cls(os.path.dirname(ap), dades, ruta_acproj=ap)

    # -- escriptura -----------------------------------------------------
    def desa(self):
        """Desa el `.acproj` **atomicament**. Retorna la ruta escrita."""
        ruta = self.ruta_acproj
        os.makedirs(self.carpeta, exist_ok=True)
        self.dades["desat"] = _ara()
        pipeline.escriu_atomic(
            ruta, lambda f: json.dump(self.dades, f, ensure_ascii=False,
                                      indent=2, sort_keys=True))
        self._ruta = ruta
        return ruta

    def duplica(self, carpeta_desti):
        """Còpia el projecte SENCER a `carpeta_desti` (Desa com / Desa una còpia).

        Si el nom de la carpeta nova canvia, renombra el `.acproj` i el camp
        `nom` perquè coincideixin (com «Desa com»). Retorna el nou `Projecte`.
        """
        desti = os.path.abspath(carpeta_desti)
        if desti == self.carpeta or \
                desti.startswith(self.carpeta + os.sep):
            raise ProjecteError(
                "no es pot copiar el projecte DINS d'ell mateix")
        if os.path.exists(desti):
            raise ProjecteError(f"la destinació ja existeix: {desti!r}")
        shutil.copytree(self.carpeta, desti)
        nou_nom = os.path.basename(desti)
        vell = _acproj_de_carpeta(desti)
        if vell:
            with open(vell, encoding="utf-8") as f:
                dades = json.load(f)
            dades["nom"] = nou_nom
            nou_ap = os.path.join(desti, nou_nom + EXT)
            if os.path.abspath(vell) != os.path.abspath(nou_ap):
                os.replace(vell, nou_ap)
            pipeline.escriu_atomic(
                nou_ap, lambda f: json.dump(dades, f, ensure_ascii=False,
                                            indent=2, sort_keys=True))
        return Projecte.obre(desti)

    # -- còpies de seguretat (autosave / backups versionats) ----------------
    def dir_backup(self):
        return os.path.join(self.carpeta, NOM_BACKUP_DIR)

    def backups(self):
        """Carpetes de backup existents (ordenades de més antiga a més nova)."""
        d = self.dir_backup()
        try:
            noms = sorted(x for x in os.listdir(d)
                          if os.path.isdir(os.path.join(d, x)))
        except OSError:
            return []
        return [os.path.join(d, x) for x in noms]

    def fes_backup(self, max_backups=MAX_BACKUPS):
        """Còpia versionada dins `backup/<data-hora>/`.

        Guarda el **document** (`.acproj` amb l'estat viu) + els **fitxers
        importants** (CSV d'acords/estructura/segments) + la carpeta
        **`analisi/`** (l'anàlisi crua). **NO** copia l'àudio (`audio/`) ni els
        exports (`wavs_*`, `partitura/`), que es deriven i són grossos.

        **No duplica** si el contingut no ha canviat des de l'última còpia.
        Rota perquè només quedin `max_backups` (les més noves).
        Retorna la carpeta creada, o `None` si no calia (sense canvis).
        """
        fits, dirs = self._materials_backup()
        sign = self._signatura(fits, dirs)
        ultims = self.backups()
        if ultims:
            try:
                with open(os.path.join(ultims[-1], ".signatura"),
                          encoding="utf-8") as f:
                    if f.read().strip() == sign:
                        return None          # cap canvi → cap còpia nova
            except OSError:
                pass
        dest = os.path.join(self.dir_backup(), _timestamp())
        k = 2
        while os.path.exists(dest):
            dest = os.path.join(self.dir_backup(), f"{_timestamp()}-{k}")
            k += 1
        os.makedirs(dest, exist_ok=True)
        # document (estat viu, encara que no s'hagi «desat»)
        ap = os.path.join(dest, os.path.basename(self.ruta_acproj))
        pipeline.escriu_atomic(
            ap, lambda f: json.dump(self.dades, f, ensure_ascii=False,
                                    indent=2, sort_keys=True))
        for n in fits:
            if n == os.path.basename(self.ruta_acproj):
                continue
            origen = os.path.join(self.carpeta, n)
            if os.path.isfile(origen):
                shutil.copy2(origen, os.path.join(dest, n))
        for d in dirs:
            origen = os.path.join(self.carpeta, d)
            if os.path.isdir(origen):
                shutil.copytree(origen, os.path.join(dest, d))
        with open(os.path.join(dest, ".signatura"), "w", encoding="utf-8") as f:
            f.write(sign)
        self._rota_backups(max_backups)
        return dest

    # Fitxers del projecte que es guarden a cada còpia (model + anàlisi crua).
    _FITXERS_BACKUP = (NOM_CSV_ACORDS, NOM_CSV_ESTRUCTURA, "segments.csv",
                       pipeline.NOM_CSV_TEMPO, pipeline.NOM_CSV_COMPAS)

    def _materials_backup(self):
        """(noms de fitxers, carpetes) del projecte que es guarden a una còpia."""
        fits = [os.path.basename(self.ruta_acproj)]
        for n in self._FITXERS_BACKUP:
            if os.path.isfile(os.path.join(self.carpeta, n)):
                fits.append(n)
        dirs = []
        an = getattr(pipeline, "NOM_ANALISI", "analisi")
        if os.path.isdir(os.path.join(self.carpeta, an)):
            dirs.append(an)
        return fits, dirs

    def _signatura(self, fits, dirs):
        """Empremta del contingut que es copia (per no duplicar còpies iguals)."""
        import hashlib
        h = hashlib.sha256()
        base = {k: v for k, v in self.dades.items() if k != "desat"}
        h.update(json.dumps(base, ensure_ascii=False, sort_keys=True).encode())
        for n in sorted(fits):
            if n == os.path.basename(self.ruta_acproj):
                continue                     # ja inclòs a `dades`
            try:
                with open(os.path.join(self.carpeta, n), "rb") as f:
                    h.update(f.read())
            except OSError:
                pass
        for d in sorted(dirs):
            for arrel, _dd, ff in os.walk(os.path.join(self.carpeta, d)):
                for fit in sorted(ff):
                    p = os.path.join(arrel, fit)
                    try:
                        with open(p, "rb") as f:
                            h.update(os.path.relpath(p, self.carpeta).encode())
                            h.update(f.read())
                    except OSError:
                        pass
        return h.hexdigest()

    def _rota_backups(self, max_backups):
        if not max_backups or max_backups <= 0:
            return
        llista = self.backups()
        for vella in llista[:-max_backups]:
            shutil.rmtree(vella, ignore_errors=True)


def _migra(dades, ap):
    """Adapta el diccionari del projecte a la versió de format actual."""
    fmt = int(dades.get("format") or 0)
    if fmt > FORMAT:
        raise ProjecteError(
            f"el projecte {ap!r} és d'una versió més nova (format {fmt} > "
            f"{FORMAT}); actualitza l'app")
    # fmt 0 = projectes desats abans que existira el camp `format`: els seus
    # camps son els mateixos de la versio 1, aixi que no cal canviar-ne cap.
    # Quan hi hagi un FORMAT 2, aquí hi van les migracions camp a camp (i el
    # test que les cobreix).
    dades["format"] = FORMAT
    return dades


# ── Migració des de l'esquema antic (AUTOCHORDS_<nom>/ al costat del WAV) ────
def carpeta_autochords(wav):
    """Carpeta `AUTOCHORDS_<nom>/` al costat del WAV, si existeix (o `None`)."""
    carp = pipeline.carpeta_sortida(wav)
    return carp if os.path.isdir(carp) else None


def importa_autochords(wav, carpeta_desti=None, nom=None):
    """Migra una `AUTOCHORDS_<nom>/` existent a un projecte **autocontingut**.

    Per defecte ho fa **a la mateixa carpeta** (hi afegeix `audio/` i el
    `.acproj`, conservant els CSVs i els exports). Retorna el `Projecte`.
    """
    origen = carpeta_autochords(wav)
    if not origen:
        raise ProjecteError(
            "no hi ha cap carpeta AUTOCHORDS_ al costat del WAV")
    desti = carpeta_desti or origen
    ca = os.path.join(origen, NOM_CSV_ACORDS)
    sa = os.path.join(origen, NOM_CSV_ESTRUCTURA)
    return Projecte.crea(
        desti, wav, nom=nom,
        csv_acords=ca if os.path.isfile(ca) else None,
        csv_estructura=sa if os.path.isfile(sa) else None,
        permet_existent=True)
