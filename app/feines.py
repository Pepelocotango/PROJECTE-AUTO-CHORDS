"""Workers de fils de la finestra (F3).

Extret de `app/main.py`: exportació, exportació d'àudio, detecció de tempo per
trams, anàlisi i els lectors del cru. No depén de la GUI.
"""
import csv
import os
import tempfile
import time

from PyQt5.QtCore import QThread, pyqtSignal

from . import exporta_audio as exporta_audio_mod, pipeline, postproc

class FeinaExporta(QThread):
    """Exporta el paquet de WAV's en un FIL (A5).

    L'export pot trigar (una WAV per acord/secció): fet al fil de la UI,
    congelava la finestra. Aquí el progrés arriba per senyal (segur entre
    fils) i la UI no es queda encallada.
    """
    missatge = pyqtSignal(str)
    progres = pyqtSignal(int)
    feta = pyqtSignal(bool, str)

    def __init__(self, kwargs):
        super().__init__()
        self._kwargs = kwargs

    def log(self, t):
        self.missatge.emit(t)

    def run(self):
        try:
            self.progres.emit(10)
            pipeline.exporta_total(log=self.log, **self._kwargs)
            self.progres.emit(100)
            self.feta.emit(True, "")
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR a l'exportar: {e}")
            self.feta.emit(False, str(e))


class FeinaExportaAudio(QThread):
    """Exporta la còpia WAV de treball a un altre format (Fase 6).

    Igual que `FeinaExporta`, el log s'emet per senyal: cridar la GUI des del
    fil seria UB. El resultat arriba amb `feta(ok, error, desti)`.
    """
    missatge = pyqtSignal(str)
    feta = pyqtSignal(bool, str, str)

    def __init__(self, origen, desti, perfil):
        super().__init__()
        self._origen = origen
        self._desti = desti
        self._perfil = perfil

    def log(self, t):
        self.missatge.emit(t)

    def run(self):
        try:
            exporta_audio_mod.exporta(self._origen, self._desti,
                                      self._perfil, log=self.log)
            self.feta.emit(True, "", self._desti)
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR a l'exportar àudio: {e}")
            self.feta.emit(False, str(e), "")


class FilTempoTrams(QThread):
    """«Detecta el tempo per trams» en un fil (no bloqueja la GUI).

    Segueix els temps de tota la cançó (DP d'Ellis) i en fa un mapa de BPM
    cada N compassos. Emet `{"trams", "offset", "bpm_base"}`.
    """
    feta = pyqtSignal(object)
    missatge = pyqtSignal(str)

    def __init__(self, wav, durada, num, den, cada, tol, bpm_min=None,
                 bpm_max=None, preferit=None, offset=None, parent=None):
        super().__init__(parent)
        self._wav = wav
        self._durada = float(durada)
        self._num = int(num)
        self._den = int(den)
        self._cada = int(cada)
        self._tol = float(tol)
        self._min = bpm_min
        self._max = bpm_max
        self._pref = preferit
        self._offset = offset

    def log(self, t):
        self.missatge.emit(str(t))

    def run(self):
        res = {"trams": [], "offset": 0.0, "bpm_base": None}
        try:
            trams, offset, base = pipeline.detecta_tempo_per_trams(
                self._wav, self.log, self._durada, num=self._num,
                den=self._den, cada_compassos=self._cada,
                tolerancia=self._tol, bpm_min=self._min, bpm_max=self._max,
                preferit=self._pref, offset=self._offset)
            res = {"trams": trams, "offset": float(offset or 0.0),
                   "bpm_base": base}
        except Exception as e:  # noqa: BLE001
            self.log(f"tempo per trams: ERROR ({e})")
        self.feta.emit(res)


class Feina(QThread):
    missatge = pyqtSignal(str)
    progres = pyqtSignal(int)
    feta = pyqtSignal(bool, str)

    def __init__(self, wav, sortida, bpm, bpb, offset, amb_estructura,
                 tempo_fix=True, opcions=None, amb_bpm=True, amb_acords=True,
                 mapa=None):
        super().__init__()
        # CRU de l'anàlisi EN MEMÒRIA: es desa dins el `.acproj` en acabar
        # (decisió 2026-10-19: ni `analisi/` ni `segments.csv` al disc).
        self.raw_chords = []       # [(t, acord), …] tal com l'ha donat Chordino
        self.raw_segments = []     # [(ini, durada, idx, etiqueta), …]
        self.analisi = None
        self.wav = wav
        self.sortida = sortida
        self.bpm = bpm
        self.bpb = bpb
        self.offset = offset
        self.amb_estructura = amb_estructura
        self.tempo_fix = tempo_fix
        self.opcions = opcions or {}
        self.mapa = mapa
        # QUÈ S'ANALITZA (3 etapes independents, decisió 21-10-2026): el que
        # està desactivat NO es toca — es conserva el model que ja hi ha.
        self.amb_bpm = bool(amb_bpm)
        self.amb_acords = bool(amb_acords)
        #: BPM detectat en esta passada (None = no s'ha detectat o no tocava)
        self.bpm_detectat = None

    def log(self, t):
        self.missatge.emit(t)

    def _detecta_bpm(self, durada_wav=None):
        """BPM del tema **sencer** amb les opcions del diàleg (motor + rang).

        Retorna el número o `None`. No toca res: qui l'aplica és la Finestra
        (camp del transport) en acabar el fil.
        """
        b = self.opcions.get("bpm") or {}
        try:
            return pipeline.detecta_bpm(
                self.wav, self.log,
                bpm_min=b.get("min"), bpm_max=b.get("max"),
                preferit=(b.get("pref_min"), b.get("pref_max")),
                motor=b.get("motor", "nostre"))
        except Exception as e:  # noqa: BLE001
            self.log(f"BPM: ERROR a la detecció ({e})")
            return None

    def run(self):
        """ANALITZA: les **3 etapes** (BPM · acords · estructura), cadascuna
        activable/desactivable a les Opcions. Les wavs es generen a l'EXPORTAR.

        Disseny (decisio de l'operador): les `wavs_acords/`/`wavs_estructura/`
        no tenen cap paper en la visualitzacio ni l'edicio; son l'ULTIM pas.
        Ací només s'escriuen els CSV del MODEL (`acords.csv`,
        `estructura_ABC.csv`); el CRU es queda en memòria i es desa dins el
        `.acproj`. La guia i les wavs les fa `pipeline.exporta_total`.

        El que està **desactivat no es toca**: es conserva el model actual (el
        BPM del transport, els acords o les seccions que ja hi ha).
        """
        passos = []
        if self.amb_bpm:
            passos.append("bpm")
        if self.amb_acords:
            passos.append("acords")
        if self.amb_estructura:
            passos.append("estructura")
        n = len(passos) or 1
        comptador = {"i": 0}

        def _pas(text):
            comptador["i"] += 1
            return f"{comptador['i']}/{n} {text}"

        try:
            os.makedirs(self.sortida, exist_ok=True)
            csv_ac = os.path.join(self.sortida, "acords.csv")
            # Durada de la WAV → invariant de cobertura dels clips (0 → durada).
            try:
                durada_wav = float(pipeline.wav_info(self.wav)["durada"])
            except Exception:  # noqa: BLE001
                durada_wav = None

            # ── 1) BPM (nou: «Analitza» també el detecta) ─────────────────
            if self.amb_bpm:
                self.log(_pas("detecta el BPM..."))
                self.bpm_detectat = self._detecta_bpm(durada_wav)
                if self.bpm_detectat:
                    self.bpm = float(self.bpm_detectat)
                    self.log(f"BPM detectat: {self.bpm:.3f} "
                             "(s'aplicarà al transport)")
                else:
                    self.log("BPM: la detecció no ha donat cap número; es "
                             "conserva el del transport")
            else:
                self.log("BPM: OMÈS (es conserva el del transport)")
            self.progres.emit(20)

            # ── 2) acords ─────────────────────────────────────────────────
            beat = (60.0 / float(self.bpm)) if self.bpm else 0.0
            if self.amb_acords:
                self.log(_pas("extreu acords (Chordino)..."))
                pipeline.extract_chords(
                    self.wav, csv_ac, self.log,
                    params=(self.opcions.get("chords") or None))
                # CRU en memòria: el resultat de Chordino ABANS de netejar-lo
                # (es desa al `.acproj` com a caché; l'edició no el toca).
                self.raw_chords = _llegeix_cru_acords(csv_ac)
                # Neteja posterior dels acords (opcions del dialeg).
                cl = self.opcions.get("clean") or {}
                if cl:
                    self.log("neteja dels acords...")
                    postproc.processa_acords_csv(
                        csv_ac,
                        # `durada_min` s'expressa en TEMPS → a segons amb el BPM
                        durada_min=float(cl.get("durada_min", 0.0)) * beat,
                        fusiona_iguals=bool(cl.get("fusiona_iguals", True)),
                        sense_baix=bool(cl.get("sense_baix", False)),
                        reduir=bool(cl.get("reduir", False)),
                        snap=bool(cl.get("snap", False)),
                        bpm=self.bpm, bpb=self.bpb, offset=self.offset,
                        divisio=int(cl.get("divisio", 1)),
                        grid=cl.get("grid"), mapa=self.mapa,
                        log=self.log, durada=durada_wav)
            else:
                self.log("acords: OMESOS (es conserva el model actual)")
            self.progres.emit(55)

            # ── 3) estructura ─────────────────────────────────────────────
            if self.amb_estructura:
                self.log(_pas("extreu estructura (qm-segmenter)..."))
                tmpd = tempfile.mkdtemp(prefix="ac_qm_")
                try:
                    seg = os.path.join(tmpd, "seg.csv")
                    pipeline.extract_segments(
                        self.wav, seg, self.log,
                        motor=(self.opcions.get("structure") or {}).get(
                            "motor", "qm"))
                    self.raw_segments = _llegeix_cru_segments(seg)
                finally:
                    pipeline.esborra_tmp([tmpd])
                self.progres.emit(80)
                self.log(_pas("ABC (estructura)..."))
                abc = os.path.join(self.sortida, "estructura_ABC.csv")
                _est = self.opcions.get("structure") or {}
                compas = beat * max(1, int(self.bpb or 4))
                pipeline.fer_abc(self.raw_segments, abc, self.bpm, self.log,
                                 lliure=not self.tempo_fix, bpb=self.bpb,
                                 offset=self.offset,
                                 # `durada_min` s'expressa en COMPASSOS → a segons
                                 durada_min=float(_est.get("durada_min", 0.0)) * compas,
                                 fusiona_iguals=bool(_est.get("fusiona_iguals", True)),
                                 durada=durada_wav)
            else:
                self.log("estructura: OMESA (es conserva la que hi ha)")
            self.analisi = {
                "data": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "durada": durada_wav,
                "bpm": self.bpm, "bpb": self.bpb, "offset": self.offset,
                "tempo_fix": self.tempo_fix,
                "opcions": self.opcions,
                "chords": self.raw_chords,
                "segments": self.raw_segments,
            }
            self.log("Analisi feta. Les wavs es generaran en 'Exporta'.")
            self.progres.emit(100)
            self.feta.emit(True, self.sortida)
        except Exception as e:  # noqa: BLE001
            # Mateixa traça que `FeinaExporta`: un error d'analisi tambe ha de
            # quedar AL REGISTRE (abans s'avisava per `feta` i prou, i al log no
            # n'hi havia constancia — auditoria 18-10-2026).
            self.log(f"ERROR a l'analisi: {e}")
            self.feta.emit(False, str(e))


def _llegeix_cru_acords(ruta):
    """CSV del host -> `[(t, acord), …]` (el CRU que es guarda al projecte)."""
    out = []
    try:
        with open(ruta, encoding="utf-8") as f:
            for fila in csv.reader(f):
                if len(fila) < 2 or not fila[0] or fila[0].startswith("posici"):
                    continue
                try:
                    out.append([float(fila[0]), fila[1].strip()])
                except ValueError:
                    continue
    except OSError:
        return []
    return out


def _llegeix_cru_segments(ruta):
    """CSV del qm-segmenter -> `[(ini, durada, idx, etiqueta), …]`."""
    out = []
    try:
        with open(ruta, encoding="utf-8") as f:
            for fila in csv.reader(f):
                if len(fila) < 4:
                    continue
                try:
                    out.append([float(fila[0]), float(fila[1]),
                                int(float(fila[2])), fila[3].strip()])
                except (ValueError, IndexError):
                    continue
    except OSError:
        return []
    return out
