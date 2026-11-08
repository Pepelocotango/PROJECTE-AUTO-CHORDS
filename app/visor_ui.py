"""Càrrega del visor i estat d'exportació (F3).

Extret de `app/main.py`: placeholder, càrrega del `Visor`, senyals, export
disponible, WAV de treball, editor de nom, audició i conversió amb ffmpeg.
"""
import os
import traceback

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from . import ffmpeg, pipeline, theme, visor as visor_mod

class VisorUIMixin:
    """Càrrega del visor i export disponible."""

    def _mostra_placeholder_visor(self):
        cont = QWidget()
        cont.setObjectName("placeholder_visor")
        cont.setStyleSheet(f"QWidget {{ background: {theme.BG}; color: {theme.TEXT}; }}")
        lay = QVBoxLayout(cont)
        lay.setContentsMargins(20, 20, 20, 20)
        label = QLabel("Sense WAV carregada\n\nSelecciona una WAV per activar el visor.")
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        lay.addWidget(label)
        if self._stack.indexOf(cont) < 0:
            self._stack.insertWidget(0, cont)   # pagina 0 = placeholder
        self._stack.setCurrentWidget(cont)
        self.visor_widget = None

    def _detecta_sortida_wav(self, wav):
        if not wav or not os.path.isfile(wav):
            return ""
        sortida = pipeline.carpeta_sortida(wav)
        if os.path.isdir(sortida):
            return sortida
        return ""

    def _carrega_visor(self, wav):
        self._atura_si_sona("recarrega del visor")
        if not wav or not os.path.isfile(wav):
            self.logger.warning("No s'ha pogut carregar la WAV: %s", wav)
            self.visor_ref = None
            self.b_exec.setEnabled(False)
            self.b_guia.setEnabled(False)
            self.b_marker.setEnabled(False)
            self.b_marker_compas.setEnabled(False)
            self._mostra_placeholder_visor()
            return
        try:
            if not self.sortida:
                self.sortida = self._detecta_sortida_wav(wav)
            acords_csv = None
            abc_csv = None
            if self.sortida:
                acords_csv = os.path.join(self.sortida, "acords.csv")
                abc_csv = os.path.join(self.sortida, "estructura_ABC.csv")
                if not os.path.isfile(acords_csv):
                    acords_csv = None
                if not os.path.isfile(abc_csv):
                    abc_csv = None

            if acords_csv is None:
                self.logger.info("Sense resultat processat per %s; obro el visor amb pistes buides", wav)

            self.logger.info("Carregant visor per %s | sortida=%s", wav, self.sortida)
            if getattr(self, "_ref_manual", False):
                try:
                    _rb, _rn, _rd = self._ref_vals()
                except ValueError:
                    _rb, _rn, _rd = None, None, None
            else:
                _rb, _rn, _rd = None, None, None
            visor = visor_mod.Visor(
                os.path.abspath(wav),
                acords_csv,
                abc_csv,
                self._bpm_val(),
                self._bpb_val(),
                tempo_fix=self.tempo_fix.isChecked(),
                # La carpeta de sortida del PROJECTE va al constructor: així
                # el visor no desa mai cap CSV a `audio/…` (carpeta derivada
                # del WAV).
                sortida=self.sortida or pipeline.carpeta_sortida(wav),
                offset=self._offset_val(),
                beat_type=self._beat_type_val(),
                bpm_unit=self._bpm_unit_val(),
                ref_bpm=_rb,
                ref_bpb=_rn,
                ref_beat_type=_rd,
                latencia_cursor_ms=self._latencia_cursor_val(),
            )
            self.visor_ref = visor
            if _rb is None or not getattr(self, "_ref_manual", False):
                self._sincronitza_ref_des_del_visor()
            self._aplica_beats_guardats(visor)
            visor.metro_click_unit = self._metro_click_unit_val()
            # El visor ha de desar els CSV/export a la carpeta de sortida del
            # PROJECTE (no derivar-la del WAV, que viu a <projecte>/audio/).
            visor.sortida = self.sortida or pipeline.carpeta_sortida(wav)
            visor.canvis.connect(self._marca_dirty)   # edicions → projecte «brut»
            if hasattr(self, "tb_snap"):
                self._canvia_snap()   # reaplica snap/divisió escollits
            self._replica_eina()      # reaplica eina + abast del rang
            # connectem els senyals del visor (icona play/pause + missatges
            # de la caixa d'informacio: desfer/refer...)
            try:
                visor.playStateChanged.disconnect(self._on_play_state)
            except (TypeError, AttributeError):
                pass
            visor.playStateChanged.connect(self._on_play_state)
            try:
                visor.infoMissatge.disconnect(self._missatge_info)
            except (TypeError, AttributeError):
                pass
            visor.infoMissatge.connect(self._missatge_info)
            try:
                visor.loopStateChanged.disconnect(self._on_loop_state)
            except (TypeError, AttributeError):
                pass
            visor.loopStateChanged.connect(self._on_loop_state)
            try:
                visor.timeline.clipSelected.disconnect(self._on_visor_seleccio)
            except (TypeError, AttributeError, RuntimeError):
                pass
            visor.timeline.clipSelected.connect(self._on_visor_seleccio)
            try:
                visor.tempoCanviat.disconnect(self._sincronitza_temps_del_visor)
            except (TypeError, AttributeError, RuntimeError):
                pass
            visor.tempoCanviat.connect(self._sincronitza_temps_del_visor)
            avisos_tempo = getattr(visor, "_avisos_csv_tempo", ())
            if avisos_tempo:
                self._missatge_info(
                    "El mapa CSV de tempo s'ha reparat: "
                    + " ".join(avisos_tempo))
            try:
                visor.velocitatCanviada.disconnect(
                    self._sincronitza_velocitat)
            except (TypeError, AttributeError, RuntimeError):
                pass
            visor.velocitatCanviada.connect(self._sincronitza_velocitat)
            self._sincronitza_velocitat(
                getattr(visor, "velocitat", 1.0))
            self._on_loop_state(getattr(visor, "loop_on", False))
            self.visor_widget = visor.centralWidget()
            self.visor_widget.setParent(self._stack)
            if self._stack.indexOf(self.visor_widget) < 0:
                self._stack.addWidget(self.visor_widget)   # pagina 1 = visor
            self._stack.setCurrentWidget(self.visor_widget)
            self.visor_widget.show()
            self.b_exec.setEnabled(True)     # hi ha WAV -> es pot analitzar
            self.b_guia.setEnabled(True)
            self.b_marker.setEnabled(True)
            self.b_marker_compas.setEnabled(True)
            # Si el visor ja porta MODEL (projecte obert, o anàlisi feta), les
            # exportacions també han d'estar disponibles. Abans només
            # s'activaven al final d'una ANÀLISI → OBRIR UN PROJECTE deixava
            # «Exporta WAV's»/«Exporta partitura» apagats i no feien res.
            self._habilita_export()
            self._actualitza_metro_ui()
            if hasattr(visor, "cont_transport"):
                # el transport viu a la barra de la finestra
                visor.cont_transport.setVisible(False)
            if hasattr(visor, "registre"):
                # el log viu al tauler plegable de la finestra (pas 3)
                visor.registre.setVisible(False)
            visor._embedded = True
            visor.setVisible(False)
            visor.close()
            # Els camps BPM/compàs han de mostrar el transport fins que es
            # seleccione un tram de tempo concret (2B).
            self._sincronitza_temps_del_visor()
            # El visor acaba de crear camps de text: que tampoc capturen drops.
            self._desactiva_drops_fills()
        except Exception:  # noqa: BLE001
            self.logger.exception("Crash en carregar el visor per %s", wav)
            self.registra(f"Visor ERROR: {traceback.format_exc()}")
            self.visor_ref = None
            self._mostra_placeholder_visor()

    def _habilita_export(self):
        """Activa «Exporta WAV's»/«Exporta partitura» si el visor té MODEL.

        El model pot venir d'una anàlisi d'aquesta sessió **o** d'un projecte
        obert (els CSV ja hi són) → en tots dos casos s'ha de poder exportar.
        """
        vr = getattr(self, "visor_ref", None)
        te_model = vr is not None and bool(getattr(vr, "acords", None)
                                           or getattr(vr, "seccions", None))
        self.b_export.setEnabled(te_model)
        self.b_export_part.setEnabled(te_model)
        accio = getattr(self, "a_exporta_audio", None)
        if accio is not None:
            accio.setEnabled(bool(self._wav_treball()))

    def _wav_treball(self):
        """Ruta de la còpia WAV de treball del projecte (o del WAV obert)."""
        if self.projecte is not None:
            ruta = self.projecte.ruta_audio()
            if ruta and os.path.isfile(ruta):
                return ruta
        ruta = self.wav_edit.text().strip()
        return ruta if ruta and os.path.isfile(ruta) else ""

    def _posa_nom_editor(self, nom):
        """El panell «Tipus d'acord» vol escriure `nom` a la casella de l'editor.

        Només l'omple (el visor també hi posa el focus); **no aplica** res.
        """
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.avisa_info("Auto Chords", "Obre un tema i tria un acord abans "
                                           "de fer servir el panell dels tipus.")
            return
        vr.posa_nom_editor(nom)

    def _escolta_notes(self, notes, preset=""):
        """Audició d'un tipus d'acord (e-piano) demanada pel panell.

        Ho toca el visor amb un motor efímer (`Visor.toca_notes`): no toca la
        reproducció de la cançó i mai aixeca (si l'àudio falla, s'avisa).
        """
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.avisa_info("Tipus d'acord",
                            "Obre un tema abans d'escoltar l'acord.")
            return
        if not vr.toca_notes(notes, preset=preset or None):
            self.avisa("Tipus d'acord",
                       "No s'ha pogut reproduir l'àudio (mira el log).")

    def _atura_si_sona(self, motiu):
        """Atura el reproductor abans d'una operacio pesada (no te sentit
        continuar sonant mentre s'analitza o es redibuixa el visor)."""
        vr = getattr(self, "visor_ref", None)
        if vr is not None and getattr(vr, "sona", False):
            self.registra(f"⏸ aturo el reproductor ({motiu})")
            vr.play_stop()

    def _assegura_wav(self, ruta):
        """Si `ruta` no és un WAV PCM 16 bits, el converteix amb ffmpeg.

        Retorna la ruta del WAV de treball (o `ruta` si ja ho era).
        """
        if ffmpeg.es_wav_pcm16(ruta):
            return ruta
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.registra(f"Convertint «{os.path.basename(ruta)}» a WAV "
                          "(ffmpeg)…")
            wav = ffmpeg.converteix_a_wav(ruta, self.registra)
        finally:
            QApplication.restoreOverrideCursor()
        return wav
