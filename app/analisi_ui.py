"""Accions d'anàlisi de la finestra (F3).

Extret de `app/main.py`: anàlisi d'acords/estructura, BPM/beats, revisió del
snap, compàs del marcador i aplicació del BPM detectat.
"""
import copy
import os

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QDialog, QInputDialog, QMessageBox

from . import beats as beats_mod, dialegs, ffmpeg, pipeline, projecte
from .feines import Feina

class AnalisiMixin:
    """Anàlisi, beats i revisió del snap."""

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
        self.b_guia.setEnabled(False)        # res de guiat mentre s'analitza
        self.b_marker.setEnabled(False)
        self.b_marker_compas.setEnabled(False)
        self.a_exporta.setEnabled(False)
        self.a_exporta_part.setEnabled(False)
        _ana = self.opcions.get("analisi") or {}
        # Separació d'accions: «Analitza» només fa acords i estructura.
        # El BPM es detecta amb «Analitza BPM…» i es mostra com a capa.
        self.feina = Feina(wav, self.sortida, self._bpm_val(),
                           self._bpb_val(), self._offset_val(),
                           bool(_ana.get("estructura", True)),
                           self.tempo_fix.isChecked(),
                           opcions=self.opcions,
                           amb_bpm=False,
                           amb_acords=bool(_ana.get("acords", True)),
                           mapa=getattr(getattr(self, "visor_ref", None),
                                        "tempo_map", None))
        self.feina.missatge.connect(self.registra)
        self.feina.progres.connect(self.barra.setValue)
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
        self.b_guia.setEnabled(False)
        self.b_marker.setEnabled(False)
        self.b_marker_compas.setEnabled(False)
        self.a_exporta.setEnabled(False)
        self.a_exporta_part.setEnabled(False)
        self.feina = Feina(
            wav, self.sortida, self._bpm_val(), self._bpb_val(),
            self._offset_val(), False, self.tempo_fix.isChecked(),
            opcions=self.opcions, amb_bpm=False, amb_acords=True,
            amb_estructura=False,
            mapa=getattr(vr, "tempo_map", None),
            rang=rang, acords=list(getattr(vr, "acords", []) or []))
        self.feina.missatge.connect(self.registra)
        self.feina.progres.connect(self.barra.setValue)
        self.feina.feta.connect(self.acabada)
        self.feina.start()

    def acabada(self, be, dada):
        self.b_exec.setEnabled(True)
        self.b_guia.setEnabled(True)
        self.b_marker.setEnabled(True)
        self.b_marker_compas.setEnabled(True)
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
        if not visor or not isinstance(info, dict):
            self._beats_actuals = None
            return
        beats = info.get("beats")
        downbeats = info.get("downbeats")
        if not isinstance(beats, list):
            self._beats_actuals = None
            return
        self._beats_actuals = info
        try:
            visor.timeline.set_beats(beats, downbeats if isinstance(
                downbeats, list) else [])
            visor.set_snap_beats(beats)
        except Exception as e:  # noqa: BLE001
            self.registra(f"beats: no s'han pogut restaurar ({e})")

    def _analitza_bpm(self):
        """Acció separada «Analitza BPM»: motor, sensibilitat i línies."""
        wav = self.wav_edit.text().strip()
        if not wav or not os.path.isfile(wav):
            self.avisa("Analitza BPM", "Primer tria una WAV.")
            return
        dlg = dialegs.DialegAnalitzaBPM(self, opcions=self.opcions)
        if dlg.exec_() != QDialog.Accepted:
            return
        cfg = dlg.valors()
        nomes_beats = cfg.get("mode") == "beats"
        opcions_bpm = self.opcions.get("bpm") or {}
        self._atura_si_sona("anàlisi de beats")
        self.registra(
            f"Analitzant {'beats' if nomes_beats else 'BPM'}: "
            f"{cfg['motor']} · sensibilitat {cfg['sensibilitat']}/100…")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            res = beats_mod.detecta(
                wav,
                motor=cfg["motor"],
                sensibilitat=cfg["sensibilitat"],
                bpb=self._bpb_val(),
                den=self._beat_type_val(),
                bpm_hint=self._bpm_val(),
                bpm_min=opcions_bpm.get("min"),
                bpm_max=opcions_bpm.get("max"),
                preferit=(opcions_bpm.get("pref_min"),
                          opcions_bpm.get("pref_max")),
                log=self.registra,
                nomes_beats=nomes_beats,
            )
        except Exception as e:  # noqa: BLE001
            self.registra(f"Analitza BPM ERROR: {e}")
            self.avisa_crit("Analitza BPM", f"No s'ha pogut detectar: {e}")
            return
        finally:
            QApplication.restoreOverrideCursor()

        self._beats_actuals = res
        beats = list(res.get("beats") or ())
        downbeats = list(res.get("downbeats") or ())
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            vr.timeline.set_beats(beats, downbeats)
            vr.set_snap_beats(beats)
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
            self.avisa_info("Analitza BPM",
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

    def _ajusta_graella_beats(self):
        """Acció de menú: snap dels marcadors a QM i ajust del mapa."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.avisa("Ajusta graella", "Primer obri una WAV.")
            return
        info = getattr(self, "_beats_actuals", None)
        if not info:
            info = (getattr(getattr(self, "projecte", None), "dades", {})
                    .get("analisi_beats"))
        if not isinstance(info, dict) or not info.get("beats"):
            self.avisa_info(
                "Ajusta graella",
                "No hi ha beats detectats. Executa «Analitza BPM» primer.")
            return
        beats = list(info.get("beats") or ())
        downbeats = list(info.get("downbeats") or ())
        # Ajustar la graella és una operació posterior al play: parem primer
        # per no mostrar cap diàleg mentre l'usuari està marcant compassos.
        self._atura_si_sona("ajust de la graella als beats")
        tolerancia, ok = QInputDialog.getDouble(
            self, "Ajusta la graella als beats QM",
            "Tolerància del snap (ms):", 120.0, 10.0, 500.0, 0)
        if not ok:
            return
        try:
            res = vr.ajusta_graella_a_beats(
                beats, downbeats, tolerancia=float(tolerancia) / 1000.0)
        except Exception as e:  # noqa: BLE001
            self.registra(f"Ajusta graella ERROR: {e}")
            self.avisa_crit("Ajusta graella", f"No s'ha pogut ajustar: {e}")
            return
        if res is None:
            return
        self._marca_dirty()
        self._missatge_info(
            f"Graella ajustada: {len(res.get('moguts') or [])} marcadors "
            f"snapats · {len(res.get('ambigus') or [])} dubtosos")
        self.registra(
            f"Ajusta graella: {len(res.get('moguts') or [])} snapats, "
            f"{len(res.get('ambigus') or [])} dubtosos, "
            f"{res.get('trams')} trams")
        self._mostra_revisio_snap(res.get("ambigus") or [])

    def _mostra_revisio_snap(self, ambigus):
        if not ambigus:
            return
        vr = getattr(self, "visor_ref", None)
        dlg = dialegs.DialegRevisioSnap(
            self, ambigus=ambigus,
            ves_a=(vr.ves_a if vr is not None else None),
            snap=self._snap_individual)
        self._revisio_snap = dlg
        dlg.show()

    def _snap_individual(self, vell, nou):
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return False
        try:
            ok = bool(vr.snap_un_marcador(float(vell), float(nou)))
        except Exception as e:  # noqa: BLE001
            self.registra(f"Snap individual ERROR: {e}")
            return False
        if ok:
            self._marca_dirty()
        return ok

    def _compas_del_marcador(self):
        """Obfri editar el compàs del tram que comença en un marcador."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.avisa("Compàs del marcador", "Primer obri una WAV.")
            return
        self._atura_si_sona("edició del compàs")
        t = float(getattr(vr, "pos", 0.0))
        idx_m = None
        dist = 0.25
        for i, m in enumerate(getattr(vr, "marcadors", []) or []):
            d = abs(float(m) - t)
            if d <= dist:
                idx_m, dist = i, d
        if idx_m is None:
            self.avisa_info(
                "Compàs del marcador",
                "Posa el cursor prop d'un marcador de compàs.")
            return
        t_m = float(vr.marcadors[idx_m])
        idx_t = None
        for i, s in enumerate(getattr(vr, "tempo_trams", []) or []):
            if abs(float(s[0]) - t_m) <= 0.06:
                idx_t = i
                break
        if idx_t is None:
            self.avisa_info(
                "Compàs del marcador",
                "No hi ha cap tram de tempo que comence en eixe marcador.")
            return
        vr._on_tempo_edit(idx_t)

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
