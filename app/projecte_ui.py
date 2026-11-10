"""Gestió de projectes de la finestra (F3).

Extret de `app/main.py`: projectes autocontinguts, desat/desa com/còpia,
recents, autosave, sessió i obertura d'àudio. Els overrides de drag & drop es
queden a `Finestra`.
"""
import json
import os
import time

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QApplication, QFileDialog, QInputDialog, QMessageBox,
)

from . import config, ffmpeg, pipeline, plataforma, projecte

class ProjecteMixin:
    """Projectes, desat, recents i sessió."""

    # ── Gestió de projectes (carpeta autocontinguda, com un DAW) ────────────
    RECENTS_MAX = 8

    def _recents_path(self):
        return os.path.join(config.DADES_DIR, "recents.json")

    def _carrega_recents(self):
        # En la suite (AUTO_CHORDS_TEST=1) no es llig la llista de l'usuari:
        # si no, un test podria obrir el projecte d'un altre.
        if os.environ.get("AUTO_CHORDS_TEST"):
            return []
        try:
            with open(self._recents_path(), encoding="utf-8") as f:
                d = json.load(f)
            return [str(x) for x in d if isinstance(x, str)][:self.RECENTS_MAX]
        except (OSError, ValueError):
            return []

    def _guarda_recents(self):
        try:
            pipeline.escriu_atomic(
                self._recents_path(),
                lambda f: json.dump(self.recents, f, ensure_ascii=False,
                                    indent=2))
        except OSError:
            pass

    def _afegeix_recent(self, ruta_acproj):
        ruta_acproj = os.path.abspath(ruta_acproj)
        self.recents = ([ruta_acproj]
                        + [r for r in self.recents if r != ruta_acproj])
        self.recents = self.recents[:self.RECENTS_MAX]
        self._guarda_recents()

    def _actualitza_titol(self):
        base = (f"{self.projecte.nom} — Auto Chords" if self.projecte is not None
                else "Auto Chords")
        self.setWindowTitle(base + (" *" if self.dirty else ""))

    def _marca_dirty(self, *_):
        # Els canvis programàtics de la barra (sincronitzar BPM/compàs amb el
        # clip de tempo seleccionat) no han de marcar el projecte com a brut.
        if getattr(self, "_actualitzant_temps", False):
            return
        if not self.dirty:
            self.dirty = True
            self._actualitza_titol()

    def _te_canvis(self):
        return bool(self.dirty)

    def _interactiu(self):
        """Hi ha un usuari que pugui respondre un diàleg modal?

        Amb la plataforma Qt **`offscreen`** (tests i CI sense pantalla) NO n'hi
        ha: un `QMessageBox` modal s'encallaria — i a Windows, directament, fa
        **«access violation»** (crash natiu; vegeu `tests/test_avis_no_modal.py`).
        En aquest cas les confirmacions responen amb el valor **segur** i ho
        deixen al log, en comptes d'obrir un diàleg.
        """
        app = QApplication.instance()
        return app is not None and app.platformName() != "offscreen"

    def _confirma_descartar(self):
        """Prompt Desa/Descarta/Cancel·la. True = podem continuar.

        Si es tria «Desa» i el desat FALLA, es retorna False (no es continua:
        mai tancar/sobreescriure perdent feina).
        """
        if not self._interactiu():
            self.registra("sense sessió interactiva (offscreen): es continua "
                          "(la cançó —acords i estructura— ja és al CSV)")
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Canvis sense desar")
        box.setText("El projecte té canvis sense desar. Vols desar-los abans "
                    "de continuar?")
        box.setInformativeText(
            "La cançó (acords i estructura) es desa automàticament; el que no "
            "es desa són els ajustos del projecte (tempo, compàs, mode, vista).")
        b_desa = box.addButton("Desa", QMessageBox.AcceptRole)
        box.addButton("Descarta", QMessageBox.DestructiveRole)
        b_canc = box.addButton("Cancel·la", QMessageBox.RejectRole)
        box.setDefaultButton(b_desa)
        box.exec_()
        clic = box.clickedButton()
        if clic is None or clic is b_canc:
            return False
        if clic is b_desa:
            return self._desa_projecte()      # False si el desat ha fallat
        return True

    def _pot_descartar(self):
        return (not self._te_canvis()) or self._confirma_descartar()

    def _dades_projecte(self):
        # El document desa el TEMPO DEL TRANSPORT (tram 0), no el del clip de
        # tempo que estiga seleccionat en eixe moment (2B).
        vr = getattr(self, "visor_ref", None)
        if vr is not None and vr.tempo_objectiu() > 0:
            bpm = float(getattr(vr, "bpm", 120.0))
            bpb = int(getattr(vr, "bpb", 4) or 4)
            den = int(getattr(vr, "beat_type", 4) or 4)
            offset = float(getattr(vr, "offset", 0.0) or 0.0)
        else:
            # Sense clip de tempo seleccionat, la barra ÉS el transport: es
            # desa el que hi ha escrit (encara que no s'haja premut Enter).
            bpm, bpb = self._bpm_val(), self._bpb_val()
            den, offset = self._beat_type_val(), self._offset_val()
        try:
            ref_bpm, ref_num, ref_den = self._ref_vals()
        except (AttributeError, TypeError, ValueError):
            ref_bpm, ref_num, ref_den = bpm, bpb, den
        return {
            "tempo": {"bpm": bpm, "bpb": bpb,
                      "offset": offset,
                      "fix": self.tempo_fix.isChecked(),
                      "compas": f"{bpb}/{den}",
                      "beat_unit": self._beat_unit_val(),
                      "ref": {"bpm": float(ref_bpm),
                              "compas": f"{int(ref_num)}/{int(ref_den)}"}},
            "opcions": self.opcions,
        }

    def _demana_ubicacio_projecte(self, base_dir, nom_suggerit, titol):
        """Pregunta ON crear/desar el projecte. Retorna la carpeta (o `None`).

        `base_dir` = carpeta on s'obre el diàleg; `nom_suggerit` = nom sense
        extensió. El resultat és la CARPETA del projecte (la que conté el
        `.acproj`), perquè un projecte és una carpeta autocontinguda.
        """
        suggerit = os.path.join(base_dir,
                                str(nom_suggerit).strip() + projecte.EXT)
        ruta, _ = QFileDialog.getSaveFileName(
            self, titol, suggerit, "Projecte AUTO CHORDS (*.acproj)")
        if not ruta:
            return None
        if not ruta.endswith(projecte.EXT):
            ruta += projecte.EXT
        nom = os.path.splitext(os.path.basename(ruta))[0]
        return os.path.join(os.path.dirname(ruta), nom)

    def _activa_projecte(self, p):
        """Carrega un projecte a la finestra (àudio, tempo, visor, títol)."""
        self._atura_si_sona("canvi de projecte")
        self.projecte = p
        self.sortida = p.carpeta
        wav = p.ruta_audio()
        self.wav_edit.setText(wav)
        tempo = p.dades.get("tempo") or {}
        self._posa_bpm_quarter(float(tempo.get("bpm", 120.0)))
        self._posa_beat_unit(tempo.get("beat_unit", "negra"))
        compas = tempo.get("compas")
        # Format COMPLET (4/4, no «4»): un «4» sol sembla el compàs denormalitzat
        # i confon; el parser accepta els dos, però el camp sempre el mostra bé.
        self.bpb.setText(str(compas) if compas
                         else f"{int(tempo.get('bpb', 4))}/4")
        ref = tempo.get("ref") or {}
        ref_bpm = float(ref.get("bpm", tempo.get("bpm", 120.0)))
        ref_compas = ref.get("compas") or self.bpb.text() or "4/4"
        self._actualitzant_temps = True
        try:
            try:
                self._posa_ref_recalc(ref_bpm, ref_compas)
            except ValueError:
                self._posa_ref_recalc(
                    float(tempo.get("bpm", 120.0)), self.bpb.text())
        finally:
            self._actualitzant_temps = False
        self._ref_manual = True
        self._posa_offset_camp(float(tempo.get("offset", 0.0)))
        self.tempo_fix.setChecked(bool(tempo.get("fix", False)))
        self._canvia_mode_temps(bool(tempo.get("fix", False)))
        if isinstance(p.dades.get("opcions"), dict) and p.dades["opcions"]:
            self.opcions = p.dades["opcions"]
        if not p.audio_present():
            self.avisa("Auto Chords", f"Falta l'àudio del projecte:\n{wav}")
        if wav and os.path.isfile(wav):
            try:
                self._actualitza_info_wav(wav)
            except Exception:  # noqa: BLE001
                pass
            self._carrega_visor(wav)
        self.dirty = False
        self._actualitza_titol()
        self._afegeix_recent(p.ruta_acproj)
        self.registra(f"Projecte obert: {p.carpeta}")
        self._engega_autosave()
        self._marca_sessio()

    def _obre_ruta_projecte(self, ruta):
        if not self._pot_descartar():
            return
        try:
            p = projecte.Projecte.obre(ruta)
        except projecte.ProjecteError as e:
            self.avisa("Auto Chords", f"No s'ha pogut obrir el projecte:\n{e}")
            return
        self._activa_projecte(p)

    def _obre_projecte(self):
        if not self._pot_descartar():
            return
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Obre un projecte", "", "Projecte AUTO CHORDS (*.acproj)")
        if ruta:
            self._obre_ruta_projecte(ruta)

    def _obre_recent(self):
        self.recents = [r for r in self.recents if os.path.isfile(r)]
        if not self.recents:
            self.avisa_info("Auto Chords", "No hi ha projectes recents.")
            return
        etiqueta, ok = QInputDialog.getItem(
            self, "Projectes recents", "Obre un projecte recent:",
            self.recents, 0, False)
        if ok and etiqueta:
            self._obre_ruta_projecte(etiqueta)

    def _desa_projecte(self):
        """Desa el projecte. Retorna True si s'ha desat (False si ha fallat)."""
        if self.projecte is None:
            self.avisa_info("Auto Chords", "No hi ha cap projecte obert.")
            return False
        self._refresca_dades_projecte()
        try:
            self.projecte.desa()
        except OSError as e:
            self.avisa("Auto Chords", f"No s'ha pogut desar:\n{e}")
            return False
        self.dirty = False
        self._actualitza_titol()
        self._afegeix_recent(self.projecte.ruta_acproj)
        self.registra(f"Projecte desat: {self.projecte.ruta_acproj}")
        return True

    def _desa_projecte_com(self):
        if self.projecte is None:
            self.avisa_info("Auto Chords", "No hi ha cap projecte obert.")
            return
        desti = self._demana_ubicacio_projecte(
            os.path.dirname(self.projecte.carpeta), self.projecte.nom,
            "Desa el projecte com")
        if not desti:
            return
        if os.path.abspath(desti) == self.projecte.carpeta:
            self._desa_projecte()          # mateix lloc → «Desa» normal
            return
        self._refresca_dades_projecte()
        self.projecte.desa()
        try:
            nou = self.projecte.duplica(desti)
        except (projecte.ProjecteError, OSError) as e:
            self.avisa("Auto Chords", f"No s'ha pogut desar com:\n{e}")
            return
        self.projecte = nou
        self.sortida = nou.carpeta
        self.dirty = False
        self._actualitza_titol()
        self._afegeix_recent(nou.ruta_acproj)
        self.registra(f"Projecte desat com: {nou.carpeta}")

    def _desa_copia(self):
        """Desa una CÒPIA sense canviar el projecte actiu."""
        if self.projecte is None:
            self.avisa_info("Auto Chords", "No hi ha cap projecte obert.")
            return
        desti = self._demana_ubicacio_projecte(
            os.path.dirname(self.projecte.carpeta),
            self.projecte.nom + "_còpia", "Desa una còpia a")
        if not desti:
            return
        self._refresca_dades_projecte()
        self.projecte.desa()
        try:
            self.projecte.duplica(desti)
        except (projecte.ProjecteError, OSError) as e:
            self.avisa("Auto Chords", f"No s'ha pogut desar la còpia:\n{e}")
            return
        self.registra(f"Còpia desada a: {desti}")

    def _reverteix(self):
        """Torna el projecte a l'últim estat desat.

        No es demana confirmació: l'acció s'ha demanat explícitament i el
        descart és el seu significat.
        """
        if self.projecte is None:
            self.avisa_info("Auto Chords", "No hi ha cap projecte obert.")
            return
        if self._te_canvis() and not self._confirma_descartar():
            return
        try:
            p = projecte.Projecte.obre(self.projecte.ruta_acproj)
        except projecte.ProjecteError as e:
            self.avisa("Auto Chords", f"No s'ha pogut revertir:\n{e}")
            return
        self._activa_projecte(p)
        self.registra("Projecte reverit a l'últim desat.")

    # -- Autosave + sessió (recuperació després d'un tancament brusc) --------
    AUTOSAVE_MS = 60000

    def _refresca_dades_projecte(self):
        """Passa el tempo/opcions dels widgets al document en memòria."""
        if self.projecte is None:
            return
        d = self._dades_projecte()
        self.projecte.dades["tempo"] = d["tempo"]
        self.projecte.dades["opcions"] = d["opcions"]

    def _desa_meta_silencios(self):
        """Desa el document del projecte (tempo/offset/opcions) sense avisos."""
        if getattr(self, "projecte", None) is None:
            return
        try:
            self._refresca_dades_projecte()
            self.projecte.desa()
        except OSError as e:
            self.registra(f"no s'ha pogut desar el projecte: {e}")

    def _engega_autosave(self):
        if getattr(self, "_autosave", None) is None:
            self._autosave = QTimer(self)
            self._autosave.setInterval(self.AUTOSAVE_MS)
            self._autosave.timeout.connect(self._fes_autosave)
        self._autosave.start()

    def _fes_autosave(self):
        """Còpia de seguretat periòdica a `backup/` (només si hi ha canvis NOUS)."""
        if self.projecte is None or not self.dirty:
            return
        try:
            self._refresca_dades_projecte()
            dest = self.projecte.fes_backup()
            if dest:
                self.registra(f"autosave: còpia creada "
                              f"({len(self.projecte.backups())} guardades)")
        except OSError as e:
            self.registra(f"autosave ERROR: {e}")

    def _sessio_path(self):
        return os.path.join(config.DADES_DIR, "sessio.json")

    def _marca_sessio(self):
        """Marca que hi ha una sessió oberta (per detectar un crash)."""
        if self.projecte is None:
            return
        try:
            pipeline.escriu_atomic(self._sessio_path(), lambda f: json.dump(
                {"acproj": self.projecte.ruta_acproj, "pid": os.getpid(),
                 "inic": time.strftime("%Y-%m-%dT%H:%M:%S")},
                f, ensure_ascii=False, indent=2))
        except OSError:
            pass

    def _neteja_sessio(self):
        try:
            os.remove(self._sessio_path())
        except OSError:
            pass

    def _sessio_pendent(self):
        """`acproj` de la sessió inacabada (i neteja el marcador), o `None`."""
        try:
            with open(self._sessio_path(), encoding="utf-8") as f:
                s = json.load(f)
        except (OSError, ValueError):
            return None
        acproj = s.get("acproj") if isinstance(s, dict) else None
        self._neteja_sessio()          # no ho tornis a oferir
        if not acproj or not os.path.isfile(acproj):
            return None
        return acproj

    def _comprova_recuperacio(self):
        """A l'arrencada: si la sessió anterior no es va tancar bé, ofereix-la.

        Es crida NOMÉS des de l'entrada real de l'app (`main()`), mai des de
        `Finestra.__init__` — així els tests no disparen cap diàleg.
        """
        acproj = self._sessio_pendent()
        if not acproj:
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle("Recupera la sessió")
        box.setText("Sembla que l'app es va tancar inesperadament.")
        box.setInformativeText(f"Vols reobrir el darrer projecte?\n{acproj}")
        b_ok = box.addButton("Reobre", QMessageBox.AcceptRole)
        box.addButton("Descarta", QMessageBox.RejectRole)
        box.setDefaultButton(b_ok)
        box.exec_()
        if box.clickedButton() is b_ok:
            self._obre_ruta_projecte(acproj)

    def tria_wav(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Tria un àudio", "", self._filtre_audio())
        if not ruta:
            return
        self._obri_des_de_wav(ruta)

    def _projecte_associat(self, wav):
        """Projecte ja associat a aquest àudio, o `None`.

        1. La carpeta germana `AUTOCHORDS_<nom>/` (convenció de l'app).
        2. Si no hi és, els **recents**: un projecte desat en un altre lloc el
           `audio/` del qual es diu igual que aquest fitxer.
        """
        carp = projecte.carpeta_autochords(wav)
        if carp:
            try:
                return projecte.Projecte.obre(carp)
            except projecte.ProjecteError:
                pass
        base = os.path.basename(wav).lower()
        for ruta in list(self.recents or ()):
            try:
                p = projecte.Projecte.obre(ruta)
            except projecte.ProjecteError:
                continue
            try:
                if os.path.basename(p.ruta_audio()).lower() == base:
                    return p
            except (OSError, ValueError):
                continue
        return None

    def _pregunta_projecte_existent(self, p):
        """Carrega / sobreescriu / cancel·la el projecte que ja té aquest àudio.

        Retorna `"carrega"`, `"sobreescriu"` o `None` (cancel·la). Sense sessió
        interactiva (tests, `offscreen`) s'escull el camí **no destructiu**.
        """
        if not self._interactiu():
            self.registra("projecte existent: sense sessió interactiva → es "
                          "carrega (no es destrueix res)")
            return "carrega"
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle("Aquest àudio ja té projecte")
        box.setText("Ja hi ha un projecte associat a aquest àudio.")
        box.setInformativeText(
            f"{p.carpeta}\n\n"
            "Si el carregues, mana el projecte (el seu àudio, els seus acords i "
            "el seu tempo).\n"
            "Si el sobreescrius, la carpeta actual va a la PAPERERA i es crea "
            "de zero amb aquest àudio.")
        b_car = box.addButton("Carrega el projecte", QMessageBox.AcceptRole)
        b_sov = box.addButton("Sobreescriu (esborra'l)",
                              QMessageBox.DestructiveRole)
        box.addButton("Cancel·la", QMessageBox.RejectRole)
        box.setDefaultButton(b_car)
        box.exec_()
        clic = box.clickedButton()
        if clic is b_car:
            return "carrega"
        if clic is b_sov:
            return "sobreescriu"
        return None

    def _obri_des_de_wav(self, ruta):
        """Obre un àudio: reutilitza el projecte si ja n'hi ha, o en crea un."""
        if not self._pot_descartar():
            return

        # Un àudio que JA té projecte: l'usuari decideix (mai un error).
        previ = self._projecte_associat(ruta)
        desti = None
        if previ is not None:
            tria = self._pregunta_projecte_existent(previ)
            if tria is None:
                return
            if tria == "carrega":
                self._activa_projecte(previ)
                self.registra(f"Projecte existent carregat: {previ.carpeta}")
                return
            # SOBREESCRIURE: la carpeta vella a la paperera (recuperable) i es
            # recrea allí mateix, sense restes de l'anterior.
            desti = previ.carpeta
            if not plataforma.a_la_paperera(desti):
                self.avisa(
                    "Auto Chords",
                    "No s'ha pogut enviar el projecte actual a la paperera, "
                    "així que NO se sobreescriu res.\n"
                    f"Projecte: {desti}")
                return
            self.registra(f"Projecte anterior a la paperera: {desti}")

        if not desti:
            # Pregunta ON crear el projecte (per defecte, al costat del WAV).
            base = os.path.splitext(os.path.basename(ruta))[0]
            desti = self._demana_ubicacio_projecte(
                os.path.dirname(ruta), pipeline.PREFIX_SORTIDA + base,
                "Crea el projecte")
            if not desti:
                return
        # Un WAV/projecte nou no hereta RES del tema anterior (OC-6/415):
        # ni BPM, ni compàs, ni offset. No hi ha excepcions per a compàs.
        self._posa_bpm_quarter(120.0)
        self.bpb.setText("4/4")
        self._posa_offset_camp(0.0)
        self.registra("WAV nou → tempo inicial 120 BPM · 4/4 · offset 0 "
                      "(detecta'l o posa'l a mà)")
        bpm, bpb, offset, compas = 120.0, 4, 0.0, "4/4"
        # Migració: si hi ha una AUTOCHORDS_<nom>/ vella al costat del WAV,
        # n'importem els CSVs (i, si el destí és la mateixa carpeta, in situ).
        antic = projecte.carpeta_autochords(ruta)
        ca = os.path.join(antic, projecte.NOM_CSV_ACORDS) if antic else None
        sa = os.path.join(antic, projecte.NOM_CSV_ESTRUCTURA) if antic else None
        in_situ = bool(antic) and os.path.abspath(desti) == os.path.abspath(antic)
        if not ffmpeg.es_wav_pcm16(ruta):
            self.registra(f"Convertint «{os.path.basename(ruta)}» a WAV "
                          "dins del projecte (ffmpeg)…")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        error = None
        try:
            p = projecte.Projecte.crea(
                desti, ruta, nom=os.path.basename(desti),
                bpm=bpm, bpb=bpb, offset=offset,
                fix=self.tempo_fix.isChecked(),
                opcions=self.opcions, compas=compas,
                csv_acords=ca if ca and os.path.isfile(ca) else None,
                csv_estructura=sa if sa and os.path.isfile(sa) else None,
                permet_existent=in_situ, log=self.registra)
        except (projecte.ProjecteError, OSError) as e:
            self.logger.exception("No s'ha pogut crear el projecte des de %s",
                                  ruta)
            error = e
        finally:
            QApplication.restoreOverrideCursor()
        if error is not None:
            self.avisa("Auto Chords", f"No s'ha pogut crear el projecte:\n{error}")
            return
        self._activa_projecte(p)
        self.registra(f"Projecte creat a: {desti}")
