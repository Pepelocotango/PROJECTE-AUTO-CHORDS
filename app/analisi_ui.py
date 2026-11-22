"""Accions d'anàlisi de la finestra (F3).

Extret de `app/main.py`: anàlisi d'acords/estructura, BPM/beats i aplicació
del BPM detectat.
"""
import copy
import os
import tempfile

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QDialog, QMessageBox, QProgressDialog,
)

from . import bpm_unit, beats as beats_mod, dialegs, ffmpeg, pipeline, projecte
from . import tempo as tempo_mod
from .feines import Feina

class AnalisiMixin:
    """Anàlisi, beats i revisió del snap."""

    def _obre_progres(self, titol, maxim=100):
        """Finestra de progrés visible mentre l'anàlisi treballa."""
        self._tanca_progres()
        dlg = QProgressDialog(titol, "", 0, int(maxim), self)
        dlg.setWindowTitle("Auto Chords — treballant")
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.setCancelButton(None)
        dlg.show()
        QApplication.processEvents()
        self._progres_analisi = dlg
        return dlg

    def _tanca_progres(self):
        dlg = getattr(self, "_progres_analisi", None)
        self._progres_analisi = None
        if dlg is not None:
            try:
                dlg.close()
                dlg.deleteLater()
            except RuntimeError:
                pass

    def _progres_valor(self, valor):
        self.barra.setValue(int(valor))
        dlg = getattr(self, "_progres_analisi", None)
        if dlg is not None:
            dlg.setValue(int(valor))

    def _actualitza_info_wav(self, ruta, info=None):
        """Info (durada/Hz) a la barra d'estat. El títol el duu `_actualitza_titol`."""
        if info is None:
            try:
                info = pipeline.wav_info(ruta)
            except Exception as e:  # noqa: BLE001
                # error real i poc freqüent (WAV il·legible): warning al log de fitxer
                self.logger.warning("no es pot llegir la info del WAV %s: %s", ruta, e)
                info = None
        if info:
            self.wav_info.setText(
                f"{info['durada']:.1f} s · {info['canals']} canals · "
                f"{info['mostreig']} Hz")

    def _hi_ha_resultats(self):
        """Cert si ja hi ha un resultat d'anàlisi carregat al visor.

        Serveix per decidir si cal avisar que tornar a analitzar el
        sobreescriurà (i, amb ell, les edicions manuals de l'usuari).
        """
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return False
        return bool(getattr(vr, "acords", None)
                    or getattr(vr, "seccions", None))

    def _confirma_reanalisi(self):
        """Avís de sobreescriptura abans de re-analitzar.

        Retorna True per continuar i False per cancel·lar. Només pregunta si
        HI HA resultats a perdre: en la primera anàlisi d'un WAV nou no molesta.
        """
        if not self._hi_ha_resultats():
            return True
        if not self._interactiu():
            self.registra("sense sessió interactiva (offscreen): es continua "
                          "amb la reanàlisi")
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Tornar a analitzar")
        box.setText(
            "Tornar a analitzar <b>sobreescriurà els acords i l'estructura "
            "actuals</b>, incloent-hi les <b>edicions manuals</b> que hagis "
            "fet (moure, renombrar o eliminar acords, retallar seccions…).")
        box.setInformativeText(
            "Aquesta acció <b>no es pot desfer</b>: els fitxers de la carpeta "
            "de sortida es tornaran a generar.")
        b_go = box.addButton("Continua i descarta", QMessageBox.DestructiveRole)
        b_no = box.addButton("Cancel·la", QMessageBox.RejectRole)
        box.setDefaultButton(b_no)
        box.exec_()
        return box.clickedButton() is b_go

    def executa(self, pregunta=True, nomes_acords=False):
        """Analitza l'àudio (BPM · acords · estructura, segons les Opcions).

        Amb `nomes_acords` (F6) només es passen els acords: ni BPM ni
        estructura. Sense, mana el que hi haja a les 3 pestanyes del diàleg.
        """
        if nomes_acords:
            self.amb_est.setChecked(False)
            self.opcions["analisi"] = {"bpm": False, "acords": True,
                                       "estructura": False}
        wav = self.wav_edit.text().strip()
        if not wav or not os.path.isfile(wav):
            self.avisa("Auto Chords",
                                "Tria un àudio vàlid primer.")
            return
        if not ffmpeg.es_wav_pcm16(wav):
            try:
                wav = self._assegura_wav(wav)
                self.wav_edit.setText(wav)
            except Exception as e:  # noqa: BLE001
                self.avisa_crit("Auto Chords",
                                     f"No s'ha pogut convertir: {e}")
                return
        if pregunta:
            dlg = dialegs.DialegOpcions(self, tab="acords",
                                        opcions=self.opcions)
            # «Analitza» és només acords + estructura. El BPM té la seua
            # acció separada («Analitza BPM…»); no el tornem a oferir ací.
            if dlg.tabs.count() and dlg.tabs.tabText(0) == "BPM":
                dlg.tabs.removeTab(0)
            if dlg.exec_() != QDialog.Accepted:
                return
            self.opcions = dlg.opcions()
            self.opcions.setdefault("analisi", {})["bpm"] = False
            dialegs.desa_opcions(self.opcions)
            self._marca_dirty()
            # La casella «Només els acords» i l'acció «Inclou estructura» són
            # el MATEIX estat: es sincronitzen (una sola font de veritat).
            self.amb_est.setChecked(
                bool((self.opcions.get("analisi") or {})
                     .get("estructura", True)))
            # AVÍS OBLIGATORI: re-analitzar re-escriu els acords/estructura (i
            # les edicions manuals) i reinicia el desfer → no es recupera.
            if not self._confirma_reanalisi():
                return
        self._atura_si_sona("analisi amb els plugins")
        if self.projecte is not None:
            self.sortida = self.projecte.carpeta
        else:
            self.sortida = pipeline.carpeta_sortida(wav)
        self.log.clear()
        self.barra.setValue(0)
        self.registra(f"Sortida: {self.sortida}")
        self.b_exec.setEnabled(False)
        self.b_analitza_beats_clip.setEnabled(False)
        self.b_analitza_beats_loop.setEnabled(False)
        self.b_analitza_onsets_loop.setEnabled(False)
        self.b_guia.setEnabled(False)        # res de guiat mentre s'analitza
        self.b_audio_ini.setEnabled(False)
        self.b_audio_fi.setEnabled(False)
        self.a_exporta.setEnabled(False)
        self.a_exporta_part.setEnabled(False)
        _ana = self.opcions.get("analisi") or {}
        # Separació d'accions: «Analitza» només fa acords i estructura.
        # El BPM es detecta amb «Analitza BPM…» i es mostra com a capa.
        self.feina = Feina(wav, self.sortida, self._transport_bpm(),
                           self._transport_bpb(),
                           bool(_ana.get("estructura", True)),
                           self.tempo_fix.isChecked(),
                           opcions=self.opcions,
                           amb_bpm=False,
                           amb_acords=bool(_ana.get("acords", True)),
                           mapa=getattr(getattr(self, "visor_ref", None),
                                        "tempo_map", None))
        self._obre_progres("Analitzant acords i estructura…")
        self.feina.missatge.connect(self.registra)
        self.feina.progres.connect(self._progres_valor)
        self.feina.feta.connect(self.acabada)
        self.feina.start()

    def _analitza_acords_rang(self):
        """Re-analitza NOMÉS els acords del loop A–B, conservant la resta.

        No toca BPM, estructura ni els acords de fora del rang. El resultat
        passa per les mateixes opcions de neteja i graella que «Analitza».
        """
        wav = self.wav_edit.text().strip()
        if not wav or not os.path.isfile(wav):
            self.avisa("Analitza acords A–B", "Tria un àudio vàlid primer.")
            return
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.avisa("Analitza acords A–B", "Primer obri una WAV.")
            return
        rang = vr._loop_vals()
        if rang is None or (rang[1] - rang[0]) < 0.5:
            self.avisa_info(
                "Analitza acords A–B",
                "Marca un rang A–B vàlid (mínim 0,5 s) al regle o amb "
                "A/B abans d'analitzar.")
            return
        if not ffmpeg.es_wav_pcm16(wav):
            try:
                wav = self._assegura_wav(wav)
                self.wav_edit.setText(wav)
            except Exception as e:  # noqa: BLE001
                self.avisa_crit("Analitza acords A–B",
                                f"No s'ha pogut convertir: {e}")
                return
        dlg = dialegs.DialegOpcions(self, tab="acords",
                                    opcions=self.opcions)
        for i in reversed(range(dlg.tabs.count())):
            if dlg.tabs.tabText(i) != "Acords":
                dlg.tabs.removeTab(i)
        if dlg.exec_() != QDialog.Accepted:
            return
        # No es toquen els flags globals de «Analitza»: esta acció només
        # re-analitza acords al rang, independentment de F5/F6.
        self.opcions = dlg.opcions()
        dialegs.desa_opcions(self.opcions)
        self._marca_dirty()
        self._atura_si_sona("anàlisi d'acords al rang A–B")
        if self.projecte is not None:
            self.sortida = self.projecte.carpeta
        else:
            self.sortida = pipeline.carpeta_sortida(wav)
        self.log.clear()
        self.barra.setValue(0)
        a, b = rang
        self.registra(f"Analitzant acords al rang A–B "
                      f"({a:.3f}–{b:.3f}s)…")
        self.b_exec.setEnabled(False)
        self.b_analitza_beats_clip.setEnabled(False)
        self.b_analitza_beats_loop.setEnabled(False)
        self.b_analitza_onsets_loop.setEnabled(False)
        self.b_guia.setEnabled(False)
        self.b_audio_ini.setEnabled(False)
        self.b_audio_fi.setEnabled(False)
        self.a_exporta.setEnabled(False)
        self.a_exporta_part.setEnabled(False)
        self.feina = Feina(
            wav, self.sortida, self._transport_bpm(), self._transport_bpb(),
            False, self.tempo_fix.isChecked(),
            opcions=self.opcions, amb_bpm=False, amb_acords=True,
            amb_estructura=False,
            mapa=getattr(vr, "tempo_map", None),
            rang=rang, acords=list(getattr(vr, "acords", []) or []))
        self._obre_progres("Analitzant acords al rang A–B…")
        self.feina.missatge.connect(self.registra)
        self.feina.progres.connect(self._progres_valor)
        self.feina.feta.connect(self.acabada)
        self.feina.start()

    def acabada(self, be, dada):
        self._tanca_progres()
        self.b_exec.setEnabled(True)
        self.b_analitza_beats_clip.setEnabled(True)
        self.b_analitza_beats_loop.setEnabled(True)
        self.b_analitza_onsets_loop.setEnabled(True)
        self.b_guia.setEnabled(True)
        self.b_audio_ini.setEnabled(True)
        self.b_audio_fi.setEnabled(True)
        self.a_exporta.setEnabled(True)
        self.a_exporta_part.setEnabled(True)
        self.registra("FET ✅ — ara pots revisar el visor i fer «Exporta WAV's».")
        self.barra.setValue(100)
        # El CRU de l'anàlisi es desa DINS el document (un sol fitxer).
        ana = getattr(self.feina, "analisi", None)
        if ana is not None and self.projecte is not None:
                net = projecte.saneja_analisi(ana)
                if net is None:
                    self.registra("AVÍS: l'anàlisi és massa gran (o no vàlida) "
                                  "per desar-la al projecte; el MODEL sí que "
                                  "hi és. Es pot tornar a analitzar.")
                    self.projecte.dades.pop("analisi", None)
                else:
                    self.projecte.dades["analisi"] = net
                try:
                    self.projecte.desa()
                    self.dirty = False
                    self._actualitza_titol()
                except OSError as e:
                    self.registra(f"AVÍS: no s'ha pogut desar l'anàlisi al "
                                  f"projecte: {e}")
        rang = getattr(self.feina, "rang", None)
        nou = getattr(self.feina, "acords_result", None)
        if rang is not None and be and nou is not None:
            # Actualització EN VIU (una sola operació d'undo): no cal
            # recarregar tot el visor ni perdre l'historial.
            vr = getattr(self, "visor_ref", None)
            if vr is not None:
                vr._undo_marca()
                vr.acords = copy.deepcopy(nou)
                vr._undo_commit()
                vr._sincronitza_vista(preserva=True)
                try:
                    vr._desa_i_regenera()
                except Exception as e:  # noqa: BLE001
                    self.registra(f"rang A–B: error en desar el model: {e}")
            self._marca_dirty()
            self.registra("Acords del rang A–B desats al model; la resta "
                          "no s'ha tocat.")
            self.barra.setValue(100)
            return
        wav = self.wav_edit.text().strip()
        if wav and os.path.isfile(wav):
            self._carrega_visor(wav)
            # BPM detectat per l'anàlisi: al transport (tram 0) DESPRÉS de
            # carregar el visor, que si no el sobreescriu amb el del projecte.
            b_det = getattr(self.feina, "bpm_detectat", None)
            if b_det:
                self._aplica_bpm_detectat(float(b_det))
        else:
            self.a_exporta.setEnabled(False)
            self.a_exporta_part.setEnabled(False)
            self.registra(f"ERROR: {dada}")
            self.log_dock.setVisible(True)    # en cas d'error, obrim el log
            self.avisa_crit("Auto Chords", dada)

    def _aplica_beats_guardats(self, visor=None):
        """Restaura els beats QM del projecte i sincronitza l'estat de Finestra.

        `_beats_actuals` és la font que usa el `+` i el Snap QM; si no es
        neteja en obrir un altre projecte, el projecte nou hereta els beats
        del projecte anterior.
        """
        visor = visor or getattr(self, "visor_ref", None)
        dades = getattr(getattr(self, "projecte", None), "dades", None) or {}
        info = dades.get("analisi_beats")
        if not visor:
            self._beats_actuals = None
            return
        if not isinstance(info, dict):
            info = {}
        beats = info.get("beats")
        downbeats = info.get("downbeats")
        if not isinstance(beats, list):
            beats = []
            self._beats_actuals = None
        else:
            self._beats_actuals = info
        try:
            downbeats = downbeats if isinstance(downbeats, list) else []
            onsets_info = dades.get("analisi_onsets") or {}
            onsets = onsets_info.get("onsets")
            if onsets is None:
                # Compatibilitat amb projectes desats abans de separar capes.
                onsets = info.get("onsets") or []
            visor.set_snap_beats(beats, downbeats)
            visor.set_onsets(onsets)
        except Exception as e:  # noqa: BLE001
            self.registra(f"beats/onsets: no s'han pogut restaurar ({e})")

    def _posa_beats_analisi(self, vr, beats, downbeats):
        """Posa els beats detectats al visor i consolida la base d'undo.

        `qm_beats` forma part de l'estat d'undo (`visor.py:984`). Sense cridar
        `_undo_touch_base()` ací, la propera edició capturaria l'estat PRE-F7
        i el `Ctrl+Z` restauraria els beats vells, emission `beatsChanged` i
        sobreescriuria `projecte.dades["analisi_beats"]` amb la llista buida.
        """
        if vr is None:
            return
        vr.timeline.set_beats(beats, downbeats)
        vr.set_snap_beats(beats, downbeats)
        if hasattr(vr, "_undo_touch_base"):
            vr._undo_touch_base()

    def _on_beats_desplacats(self, beats, downbeats):
        """Actualitza la còpia del projecte quan l'àudio mou els beats QM."""
        beats = [float(t) for t in (beats or ())]
        downbeats = [float(t) for t in (downbeats or ())]
        if not beats and not downbeats and not self._beats_actuals:
            return
        info = dict(self._beats_actuals or {})
        info["beats"] = beats
        info["downbeats"] = downbeats
        vr = getattr(self, "visor_ref", None)
        self._beats_actuals = info
        if self.projecte is not None:
            dades = dict(self.projecte.dades.get("analisi_beats") or {})
            dades.update(beats=beats, downbeats=downbeats)
            self.projecte.dades["analisi_beats"] = dades
            if vr is not None and hasattr(vr, "qm_onsets"):
                od = dict(self.projecte.dades.get("analisi_onsets") or {})
                od["onsets"] = list(vr.qm_onsets or ())
                self.projecte.dades["analisi_onsets"] = od
        self._marca_dirty()

    @staticmethod
    def _fusiona_beats_rang(vells, nous, ini, fi):
        """Substituïx els beats de `[ini, fi)` pels nous, conservant la resta."""
        ini, fi = float(ini), float(fi)
        fora = [float(b) for b in (vells or ())
                if not (ini - 1e-9 <= float(b) < fi - 1e-9)]
        return sorted(set(fora + [float(b) for b in (nous or ())]))

    def _analitza_bpm_clip(self):
        """Analitza amb QM només el tram de tempo seleccionat."""
        vr = getattr(self, "visor_ref", None)
        wav = self.wav_edit.text().strip()
        if vr is None or not wav or not os.path.isfile(wav):
            self.avisa("Beats del clip", "Primer obri una WAV.")
            return
        kind, idx = vr.seleccio_activa()
        if kind != "tempo" or not vr._index_valid("tempo", idx):
            self.avisa("Beats del clip",
                       "Selecciona un clip de la pista de tempo/compàs.")
            return
        tr = vr.tempo_trams[int(idx)]
        ini = float(getattr(tr, "ini", tr[0]))
        fi = float(getattr(tr, "fi", tr[1]))
        if fi <= ini + 1e-6:
            self.avisa("Beats del clip", "El tram seleccionat és buit.")
            return
        cfg = dict(self.opcions.get("beats") or {})
        sens = float(cfg.get("sensibilitat", 50))
        opcions_bpm = self.opcions.get("bpm") or {}
        self._atura_si_sona("anàlisi de beats del clip")
        tmpd = tempfile.mkdtemp(prefix="ac_qm_clip_")
        wav_clip = os.path.join(tmpd, "clip.wav")
        try:
            pipeline.retalla_wav(wav, wav_clip, ini, fi)
            self.registra(
                f"Analitzant beats QM del clip {idx + 1} "
                f"({ini:.3f}–{fi:.3f}s)…")
            self._obre_progres("Analitzant beats QM del clip…", 0)
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                res = beats_mod.detecta(
                    wav_clip,
                    motor="qm",
                    sensibilitat=sens,
                    bpb=int(getattr(tr, "num", tr[3])),
                    den=int(getattr(tr, "den", tr[4])),
                    bpm_hint=float(getattr(tr, "bpm", tr[2])),
                    bpm_min=opcions_bpm.get("min"),
                    bpm_max=opcions_bpm.get("max"),
                    preferit=(opcions_bpm.get("pref_min"),
                              opcions_bpm.get("pref_max")),
                    beat_unit=vr.unitat_de_tram(tr),
                    log=self.registra,
                    nomes_beats=False,
                )
            finally:
                QApplication.restoreOverrideCursor()
                self._tanca_progres()
        except Exception as e:  # noqa: BLE001
            self.registra(f"Beats del clip ERROR: {e}")
            self.avisa_crit("Beats del clip",
                            f"No s'ha pogut analitzar el tram: {e}")
            return
        finally:
            pipeline.esborra_tmp([tmpd])
        locals_b = [ini + float(t) for t in (res.get("beats") or ())
                    if 0.0 <= float(t) < (fi - ini) - 1e-9]
        locals_d = [ini + float(t) for t in (res.get("downbeats") or ())
                    if 0.0 <= float(t) < (fi - ini) - 1e-9]
        if not locals_b:
            self.avisa_info("Beats del clip",
                            "QM no ha detectat cap beat dins d'este tram.")
            return
        vells_b = list(getattr(vr, "qm_beats", None) or ())
        vells_d = list(getattr(vr, "qm_downbeats", None) or ())
        beats = self._fusiona_beats_rang(vells_b, locals_b, ini, fi)
        downbeats = self._fusiona_beats_rang(vells_d, locals_d, ini, fi)
        self._posa_beats_analisi(vr, beats, downbeats)
        info = dict(self._beats_actuals or {})
        info.update({
            "motor": "qm",
            "mode": "clip",
            "sensibilitat": sens,
            "bpm": res.get("bpm"),
            "beat_unit": vr.unitat_de_tram(tr),
            "beats": beats,
            "downbeats": downbeats,
            "rang": [ini, fi],
        })
        self._beats_actuals = info
        self._marca_dirty()
        if self.projecte is not None:
            dades = dict(self.projecte.dades.get("analisi_beats") or {})
            dades.update(info)
            self.projecte.dades["analisi_beats"] = dades
            try:
                self.projecte.desa()
                self.dirty = False
                self._actualitza_titol()
            except OSError as e:
                self.registra(f"beats del clip: no s'han pogut desar ({e})")
        bpm_txt = (f" · BPM QM {res['bpm']:.2f}"
                   if res.get("bpm") is not None else "")
        self.registra(
            f"{len(locals_b)} beats QM dins el clip {idx + 1}"
            f" ({ini:.3f}–{fi:.3f}s){bpm_txt}")
        self._missatge_info(
            f"{len(locals_b)} beats QM al clip · BPM {bpm_txt or '—'}")

    def _analitza_bpm_loop(self):
        """Analitza beats només al loop A–B, amb motor i sensibilitat com F7.

        No aplica el BPM al transport: el resultat és una capa de beats dins
        del rang. Els beats de fora del loop es conserven.
        """
        titol = "Beats A–B"
        wav = self.wav_edit.text().strip()
        vr = getattr(self, "visor_ref", None)
        if vr is None or not wav or not os.path.isfile(wav):
            self.avisa(titol, "Primer obri una WAV.")
            return
        rang = vr._loop_vals()
        if rang is None or (rang[1] - rang[0]) < 1.0:
            self.avisa_info(
                titol,
                "Marca un loop A–B de com a mínim 1 s (regle o botons A/B) "
                "abans d'analitzar.")
            return
        ini, fi = float(rang[0]), float(rang[1])
        bpb = int(self._transport_bpb())
        den = int(self._transport_beat_type())
        bpm_hint = float(self._transport_bpm())
        beat_unit = bpm_unit.unitat_per_defecte(bpb, den)
        try:
            tr = vr.tempo_map.tram(ini)
            if tr is not None:
                bpb = int(tr.num)
                den = int(tr.den)
                bpm_hint = float(tr.bpm)
                beat_unit = vr.unitat_de_tram(tr)
        except (AttributeError, TypeError, ValueError):
            pass
        dlg = dialegs.DialegAnalitzaBPM(
            self, opcions=self.opcions, num=bpb, den=den,
            beat_unit=beat_unit, bpm=bpm_hint, permet_aplica_bpm=False)
        dlg.setWindowTitle("Analitza beats del loop A–B")
        if dlg.exec_() != QDialog.Accepted:
            return
        cfg = dlg.valors()
        beat_unit = cfg.get("beat_unit") or beat_unit
        nomes_beats = cfg.get("mode") == "beats"
        opcions_bpm = self.opcions.get("bpm") or {}
        self.opcions["beats"] = {
            **dict(self.opcions.get("beats") or {}),
            "motor": cfg["motor"],
            "sensibilitat": cfg["sensibilitat"],
            "mode": cfg["mode"],
            "beat_unit": beat_unit,
        }
        dialegs.desa_opcions(self.opcions)
        self._marca_dirty()
        self._atura_si_sona("anàlisi de beats del loop A–B")
        self.registra(
            f"Analitzant beats del loop A–B ({ini:.3f}–{fi:.3f}s): "
            f"{cfg['motor']} · sensibilitat {cfg['sensibilitat']}/100…")
        tmpd = tempfile.mkdtemp(prefix="ac_beats_loop_")
        wav_loop = os.path.join(tmpd, "loop.wav")
        try:
            pipeline.retalla_wav(wav, wav_loop, ini, fi)
            self._obre_progres("Analitzant beats del loop A–B…", 0)
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                res = beats_mod.detecta(
                    wav_loop,
                    motor=cfg["motor"],
                    sensibilitat=float(cfg["sensibilitat"]),
                    bpb=bpb,
                    den=den,
                    bpm_hint=bpm_hint,
                    bpm_min=opcions_bpm.get("min"),
                    bpm_max=opcions_bpm.get("max"),
                    preferit=(opcions_bpm.get("pref_min"),
                              opcions_bpm.get("pref_max")),
                    beat_unit=beat_unit,
                    log=self.registra,
                    nomes_beats=nomes_beats,
                )
            finally:
                QApplication.restoreOverrideCursor()
                self._tanca_progres()
        except Exception as e:  # noqa: BLE001
            self.registra(f"Beats A–B ERROR: {e}")
            self.avisa_crit(titol, f"No s'ha pogut analitzar el loop: {e}")
            return
        finally:
            pipeline.esborra_tmp([tmpd])
        locals_b = [ini + float(t) for t in (res.get("beats") or ())
                    if 0.0 <= float(t) < (fi - ini) - 1e-9]
        locals_d = [ini + float(t) for t in (res.get("downbeats") or ())
                    if 0.0 <= float(t) < (fi - ini) - 1e-9]
        if not locals_b:
            self.avisa_info(titol,
                            "No s'ha detectat cap beat dins del loop A–B.")
            return
        vells_b = list(getattr(vr, "qm_beats", None) or ())
        vells_d = list(getattr(vr, "qm_downbeats", None) or ())
        beats = self._fusiona_beats_rang(vells_b, locals_b, ini, fi)
        downbeats = self._fusiona_beats_rang(vells_d, locals_d, ini, fi)
        self._posa_beats_analisi(vr, beats, downbeats)
        info = dict(self._beats_actuals or {})
        info.update({
            "motor": res.get("motor"),
            "mode": "loop",
            "sensibilitat": res.get("sensibilitat"),
            "bpm": res.get("bpm"),
            "beat_unit": beat_unit,
            "beats": beats,
            "downbeats": downbeats,
            "rang": [ini, fi],
        })
        self._beats_actuals = info
        self._marca_dirty()
        if self.projecte is not None:
            dades = dict(self.projecte.dades.get("analisi_beats") or {})
            dades.update(info)
            self.projecte.dades["analisi_beats"] = dades
            try:
                self.projecte.desa()
                self.dirty = False
                self._actualitza_titol()
            except OSError as e:
                self.registra(f"beats A–B: no s'han pogut desar ({e})")
        bpm = res.get("bpm")
        bpm_txt = f" · BPM {bpm:.2f}" if bpm is not None else ""
        self.registra(
            f"{len(locals_b)} beats dins el loop A–B "
            f"({ini:.3f}–{fi:.3f}s){bpm_txt}")
        self._missatge_info(
            f"{len(locals_b)} beats al loop A–B{bpm_txt}")

    def _analitza_onsets_loop(self):
        """Detecta onsets (sense BPM) només al loop A–B i els marca com beats."""
        titol = "Onsets A–B"
        wav = self.wav_edit.text().strip()
        vr = getattr(self, "visor_ref", None)
        if vr is None or not wav or not os.path.isfile(wav):
            self.avisa(titol, "Primer obri una WAV.")
            return
        rang = vr._loop_vals()
        if rang is None or (rang[1] - rang[0]) < 0.1:
            self.avisa_info(
                titol,
                "Marca un loop A–B d'almenys 0,1 s abans de detectar onsets.")
            return
        if (rang[1] - rang[0]) > 2.0:
            self.avisa_info(
                titol,
                "El loop és massa llarg per a Onsets A–B: el màxim és 2 s. "
                "Marca un rang més curt o usa «Beats del clip».")
            return
        ini, fi = float(rang[0]), float(rang[1])
        cfg = dict(self.opcions.get("beats") or {})
        sens = float(cfg.get("sensibilitat", 50))
        self._atura_si_sona("detecció d'onsets del loop A–B")
        self.registra(
            f"Detectant onsets del loop A–B ({ini:.3f}–{fi:.3f}s) · "
            f"sensibilitat {sens:.0f}/100…")
        self._obre_progres("Detectant onsets del loop A–B…", 0)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            onsets = tempo_mod.detecta_onsets(
                wav, log=self.registra, sensibilitat=sens,
                inici=ini, fi=fi, min_sep=0.05, refina=True)
        except Exception as e:  # noqa: BLE001
            self.registra(f"Onsets A–B ERROR: {e}")
            self.avisa_crit(titol, f"No s'han pogut detectar onsets: {e}")
            return
        finally:
            QApplication.restoreOverrideCursor()
            self._tanca_progres()
        locals_b = [float(t) for t in onsets
                    if ini - 1e-9 <= float(t) < fi - 1e-9]
        if not locals_b:
            self.avisa_info(titol,
                            "No s'ha detectat cap onset dins del loop A–B.")
            return
        # Capa independent: no toca els beats ni els downbeats.
        vr.set_onsets(locals_b)
        if hasattr(vr, "_undo_touch_base"):
            vr._undo_touch_base()
        info = {
            "motor": "onsets",
            "mode": "onsets",
            "sensibilitat": sens,
            "bpm": None,
            "beat_unit": vr.unitat_objectiu(),
            "onsets": locals_b,
            "rang": [ini, fi],
            "parametre": {"min_sep": 0.05},
        }
        self._marca_dirty()
        if self.projecte is not None:
            dades = dict(self.projecte.dades.get("analisi_onsets") or {})
            dades.update(info)
            self.projecte.dades["analisi_onsets"] = dades
            try:
                self.projecte.desa()
                self.dirty = False
                self._actualitza_titol()
            except OSError as e:
                self.registra(f"onsets A–B: no s'han pogut desar ({e})")
        self.registra(
            f"{len(locals_b)} onsets dins el loop A–B "
            f"({ini:.3f}–{fi:.3f}s), sense BPM")
        self._missatge_info(f"{len(locals_b)} onsets al loop A–B")

    def _analitza_bpm(self):
        """Acció separada «Analitza beats, downbeats i BPM»: motor, sensibilitat i línies."""
        wav = self.wav_edit.text().strip()
        if not wav or not os.path.isfile(wav):
            self.avisa("Analitza beats, downbeats i BPM", "Primer tria una WAV.")
            return
        vr = getattr(self, "visor_ref", None)
        bpb = self._transport_bpb()
        den = self._transport_beat_type()
        beat_unit = bpm_unit.unitat_per_defecte(bpb, den)
        try:
            if vr is not None and getattr(vr, "tempo_trams", None):
                beat_unit = vr.unitat_de_tram(vr.tempo_trams[0])
        except (TypeError, ValueError, AttributeError):
            pass
        dlg = dialegs.DialegAnalitzaBPM(
            self, opcions=self.opcions, num=bpb, den=den,
            beat_unit=beat_unit, bpm=self._transport_bpm())
        if dlg.exec_() != QDialog.Accepted:
            return
        cfg = dlg.valors()
        beat_unit = cfg.get("beat_unit") or beat_unit
        nomes_beats = cfg.get("mode") == "beats"
        opcions_bpm = self.opcions.get("bpm") or {}
        self._atura_si_sona("anàlisi de beats")
        self.registra(
            f"Analitzant {'beats' if nomes_beats else 'BPM'}: "
            f"{cfg['motor']} · sensibilitat {cfg['sensibilitat']}/100…")
        self._obre_progres("Analitzant beats i BPM…", 0)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        def _log_beats(text):
            self.registra(text)
        try:
            res = beats_mod.detecta(
                wav,
                motor=cfg["motor"],
                sensibilitat=cfg["sensibilitat"],
                bpb=bpb,
                den=den,
                bpm_hint=self._transport_bpm(),
                bpm_min=opcions_bpm.get("min"),
                bpm_max=opcions_bpm.get("max"),
                preferit=(opcions_bpm.get("pref_min"),
                          opcions_bpm.get("pref_max")),
                beat_unit=beat_unit,
                log=_log_beats,
                nomes_beats=nomes_beats,
            )
        except Exception as e:  # noqa: BLE001
            self.registra(f"Analitza beats/BPM ERROR: {e}")
            self.avisa_crit("Analitza beats, downbeats i BPM", f"No s'ha pogut detectar: {e}")
            return
        finally:
            QApplication.restoreOverrideCursor()
            self._tanca_progres()

        self._beats_actuals = res
        beats = list(res.get("beats") or ())
        downbeats = list(res.get("downbeats") or ())
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            self._posa_beats_analisi(vr, beats, downbeats)
        self.opcions["beats"] = dict(cfg)
        dialegs.desa_opcions(self.opcions)
        self._marca_dirty()
        bpm = res.get("bpm")
        if not nomes_beats and cfg.get("aplica_bpm") and bpm:
            self._aplica_bpm_detectat(float(bpm))
        if self.projecte is not None:
            self.projecte.dades["analisi_beats"] = {
                "motor": res.get("motor"),
                "sensibilitat": res.get("sensibilitat"),
                "mode": cfg.get("mode"),
                "bpm": bpm,
                "beat_unit": beat_unit,
                "beats": beats,
                "downbeats": downbeats,
            }
            try:
                self.projecte.desa()
                self.dirty = False
                self._actualitza_titol()
            except OSError as e:
                self.registra(f"beats: no s'han pogut desar al projecte ({e})")
        if not beats:
            self.avisa_info("Analitza beats, downbeats i BPM",
                            "No s'ha detectat cap beat amb estes opcions.")
            return
        bpm_txt = f"{bpm:.2f}" if bpm is not None else "—"
        if nomes_beats:
            self._missatge_info(f"{len(beats)} beats (sense BPM ni compassos)")
            self.registra(
                f"{len(beats)} beats · només polsos · motor "
                f"{res.get('motor')} (sensibilitat "
                f"{res.get('sensibilitat'):.0f}/100)")
        else:
            self._missatge_info(
                f"BPM: {bpm_txt} · {len(beats)} beats · "
                f"{len(downbeats)} downbeats")
            self.registra(
                f"BPM: {bpm_txt} · {len(beats)} beats · "
                f"{len(downbeats)} downbeats · motor {res.get('motor')} "
                f"(sensibilitat {res.get('sensibilitat'):.0f}/100)")

    def _aplica_bpm_detectat(self, b):
        """Posa al transport el BPM que ha detectat «Analitza» (etapa BPM).

        Si el mapa de tempo té **més d'un tram**, no s'hi toca res: canviar-ne
        només el primer trencaria el contracte de beats sencers dels trams
        (regla de temps) — per a eixe cas hi ha «Detecta el tempo per trams».
        """
        b = float(b)
        self._posa_bpm_quarter(b)
        self._marca_dirty()
        self.registra(f"BPM detectat: {b:.3f}")
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return
        trams = list(getattr(vr, "tempo_trams", []) or [])
        if len(trams) > 1:
            self.registra(f"BPM detectat: no s'aplica al mapa ({len(trams)} "
                          "trams); fes servir «Detecta el tempo per trams»")
            return
        self._aplica_parametres_temps()
