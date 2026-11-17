"""Exportació de la finestra (F3).

Extret de `app/main.py`: preparació, export d'àudio amb ffmpeg, WAVs,
partitura i obertura de la carpeta de sortida.
"""
import os
import time

from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QFileDialog

from . import (
    exporta_audio as exporta_audio_mod, partitura, pipeline, tempo_midi,
)
from .feines import FeinaExporta, FeinaExportaAudio

class ExportMixin:
    """Exportació de WAVs, àudio i partitura."""

    def _prepara_export(self):
        """Valida i calcula els arguments de l'export (NOMÉS al fil de UI).

        Retorna el diccionari de kwargs per a `pipeline.exporta_total`, o
        `None` si no es pot exportar (i ja ha avisat). Els widgets es llegeixen
        AQUÍ perquè el fil de l'export (A5) no els pot tocar.
        """
        wav = self.wav_edit.text().strip()
        if not self.sortida:
            if not wav or not os.path.isfile(wav):
                self.avisa("Auto Chords",
                           "Tria una wav vàlida abans d'exportar.")
                return None
            self.sortida = pipeline.carpeta_sortida(wav)

        csv_ac = os.path.join(self.sortida, "acords.csv")
        if not os.path.isfile(csv_ac):
            if not wav or not os.path.isfile(wav):
                self.avisa("Auto Chords",
                           "No hi ha CSVs d'exportació. Fes 'Executa' primer.")
                return None
            self.avisa_info(
                "Auto Chords",
                "Encara no hi ha CSVs generats. Fes 'Executa' primer.")
            return None

        # (A) Si hi ha visor, l'export usa el MODEL VIU (no els CSV del disc):
        # així no es perden les edicions manuals de seccions (ni la cobertura).
        vr = getattr(self, "visor_ref", None)
        vre = vr
        acords_model = list(vr.acords) if vr is not None else None
        seccions_model = list(vr.seccions) if vr is not None else None
        total_s = (float(vr.audio.get("durada", 0.0))
                   if vr is not None else None)
        # Regla d'or #12: el mapa de BPM/compàs del model viu també s'exporta.
        mapa_model = list(vr.tempo_trams) if vr is not None else None
        # L'export és INDEPENDENT de «Inclou estructura» (opció d'ANÀLISI):
        # si el model té estructura, s'exporta sempre amb els altres tipus.
        amb_estructura = seccions_model is not None
        marques = []
        if vr is not None:
            tipus = pipeline.llegeix_marcadors_tipus(self.sortida)
            marques = [(float(t), tipus.get(round(float(t), 6), "marcador"))
                       for t in (vr.marcadors or ())]
        return dict(
            csv_ac=csv_ac,
            csv_seg=None,
            sortida=self.sortida,
            bpm=self._bpm_val(),
            bpb=self._bpb_val(),
            den=self._beat_type_val(),
            beat_unit=((vre.unitat_objectiu() if vre is not None
                        else "negra")),
            bpm_unit=((vre.unitat_objectiu() if vre is not None
                       else "negra")),
            sr=44100,
            tempo_fix=self.tempo_fix.isChecked(),
            amb_estructura=amb_estructura,
            acords=acords_model,
            seccions=seccions_model,
            total_s=total_s,
            mapa_tempo=mapa_model,
            marques=marques,
        )

    def _exporta_audio_ui(self):
        """Tria format i destí i exporta la còpia WAV de treball (Fase 6).

        Obre el diàleg natiu de desar. Els filtres són els perfils que aquest
        `ffmpeg` sap escriure de debò; el nom suggerit viu a la carpeta del
        projecte. Mai es pot triar la còpia de treball; per a qualsevol altre
        fitxer existent, el diàleg natiu demana confirmació.
        """
        origen = self._wav_treball()
        if not origen:
            self.avisa_info("Exporta àudio",
                            "Obre un àudio abans d'exportar-ne una còpia.")
            return
        perfils = exporta_audio_mod.perfils_disponibles()
        if not perfils:
            self.avisa(
                "Exporta àudio",
                "Aquest ffmpeg no té cap codificador d'àudio compatible.\n"
                "No s'ofereix cap format per no prometre'n un que fallaria.")
            return
        carpeta = (self.projecte.carpeta if self.projecte is not None
                   else os.path.dirname(origen))
        nom = ((self.projecte.nom if self.projecte is not None
                else os.path.splitext(os.path.basename(origen))[0])
               + "_editat")
        filtres = [exporta_audio_mod.filtre(p) for p in perfils]
        dlg = QFileDialog(self, "Exporta àudio", carpeta, ";;".join(filtres))
        dlg.setAcceptMode(QFileDialog.AcceptSave)
        dlg.setFileMode(QFileDialog.AnyFile)
        dlg.setConfirmOverwrite(True)
        dlg.setDefaultSuffix(perfils[0]["ext"])
        dlg.selectNameFilter(filtres[0])
        dlg.selectFile(os.path.join(carpeta,
                                    nom + "." + perfils[0]["ext"]))

        def _canvia_filtre(text):
            p = exporta_audio_mod.perfil_de_filtre(text, perfils)
            if p is not None:
                dlg.setDefaultSuffix(p["ext"])

        dlg.filterSelected.connect(_canvia_filtre)
        if dlg.exec_() != QFileDialog.Accepted:
            return
        ruta = dlg.selectedFiles()[0]
        perfil = exporta_audio_mod.perfil_de_filtre(
            dlg.selectedNameFilter(), perfils)
        if perfil is None:
            self.avisa("Exporta àudio",
                       "No s'ha pogut determinar el format triat.")
            return
        ext_esperada = "." + perfil["ext"]
        arrel, ext = os.path.splitext(ruta)
        if not ext:
            ruta = arrel + ext_esperada
        elif ext.lower() != ext_esperada:
            # No substituïm l'extensió en silenci: seria un fitxer amb un
            # contingut que no diu el nom.
            self.avisa(
                "Exporta àudio",
                f"El nom acaba en «{ext}», però el format triat és "
                f"«{perfil['etiqueta']}» ({ext_esperada}).\n"
                "Tria el format que corresponga a l'extensió o canvia el nom.")
            return
        protegits = {os.path.realpath(origen)}
        if os.path.realpath(ruta) in protegits:
            self.avisa(
                "Exporta àudio",
                "No es pot exportar sobre la còpia de treball del projecte.\n"
                "Tria un altre nom o una altra carpeta.")
            return
        if not os.path.isdir(os.path.dirname(os.path.abspath(ruta))):
            self.avisa("Exporta àudio",
                       "La carpeta de destinació no existeix.")
            return
        self.a_exporta_audio.setEnabled(False)
        self.registra(f"Exportant àudio ({perfil['etiqueta']}): {ruta}")
        fil = FeinaExportaAudio(origen, ruta, perfil)
        fil.missatge.connect(self.registra)
        fil.feta.connect(self._exporta_audio_acabada)
        self._fil_exporta_audio = fil
        fil.start()

    def _exporta_audio_acabada(self, ok, error, desti):
        """Tanca l'exportació d'àudio: log visible i estat de l'acció."""
        self._fil_exporta_audio = None
        if hasattr(self, "a_exporta_audio"):
            self.a_exporta_audio.setEnabled(bool(self._wav_treball()))
        if ok:
            self.registra(f"Exportació d'àudio feta: {desti}")
            self._missatge_info(f"Àudio exportat: {os.path.basename(desti)}")
        else:
            self.registra(f"ERROR a l'exportar àudio: {error}")
            self.avisa("Exporta àudio",
                       f"No s'ha pogut exportar l'àudio:\n{error}")

    def _exporta_acabada(self, res_part=None):
        """Missatges de final d'exportació (compartit pel camí síncron i el fil)."""
        self.registra("Exportació feta ✅")
        msg = f"Exportació feta a:\n{self.sortida}"
        if res_part is not None and not res_part.get("pdf"):
            msg += ("\n\n⚠️ La partitura s'ha generat NOMÉS en MusicXML: el "
                    "PDF necessita MuseScore instal·lat.")
        self.avisa_info("Auto Chords", msg)
        self.obre_carpeta()

    def desa_i_exporta(self):
        """Desa el projecte i exporta el paquet complet + partitura.

        Acció de «Fitxer ▸ Desa i exporta-ho tot…». Primer desa (si falla, no
        s'exporta res) i després llança l'export en fil amb la partitura
        FORÇADA: MusicXML sempre i PDF/MSCZ si hi ha MuseScore. No exporta la
        WAV sencera (per a això hi ha «Exporta àudio…»). Els derivats existents
        se sobreescriuen i, en acabar, s'obri la carpeta del projecte.
        """
        fe = getattr(self, "feina_export", None)
        if fe is not None and fe.isRunning():
            self.avisa_info("Auto Chords", "Ja hi ha una exportació en curs.")
            return False
        if getattr(self, "projecte", None) is None:
            self.avisa_info("Auto Chords",
                            "No hi ha cap projecte obert. Obre un àudio primer.")
            return False
        if not self._desa_projecte():
            return False
        return self.exporta_async(forca_partitura=True)

    def exporta(self):
        """Exporta de forma SÍNCRONA (la UI espera). Vegeu `exporta_async`."""
        kwargs = self._prepara_export()
        if kwargs is None:
            return
        self.exporta_error = ""
        try:
            self.registra(f"Exportant a: {self.sortida}")
            pipeline.exporta_total(log=self.registra, **kwargs)
            res_part = self._exporta_partitura() if self.amb_part.isChecked() else None
            self._exporta_acabada(res_part)
        except Exception as e:  # noqa: BLE001
            self.exporta_error = str(e)
            self.registra(f"exporta ERROR: {e}")
            self.avisa_crit("Auto Chords",
                            f"No s'ha pogut exportar:\n{e}")

    def exporta_async(self, forca_partitura=None):
        """Exporta en un FIL (A5). Retorna True si ha arrencat.

        La partitura es fa DESPRÉS, al fil de la UI, quan el fil acaba. Amb
        `forca_partitura=True` es genera SEMPRE (MusicXML, i PDF/MSCZ si es pot)
        encara que «Inclou la partitura» estiga desmarcada; amb `None` mana la
        marca. El progrés es veu a la barra i a `self.exportant`.
        """
        fe = getattr(self, "feina_export", None)
        if fe is not None and fe.isRunning():
            return False
        kwargs = self._prepara_export()
        if kwargs is None:
            return False
        self._exporta_amb_partitura = (
            self.amb_part.isChecked() if forca_partitura is None
            else bool(forca_partitura))
        self.registra(f"Exportant a: {self.sortida}")
        self.exporta_error = ""
        self.exportant = True
        self.exporta_iniciat = time.time()
        self.barra.setValue(0)
        self.feina_export = FeinaExporta(kwargs)
        self.feina_export.missatge.connect(self.registra)
        self.feina_export.progres.connect(self.barra.setValue)
        self.feina_export.feta.connect(self._exporta_async_feta)
        self.feina_export.start()
        return True

    def _exporta_async_feta(self, ok, error):
        self.exportant = False
        if not ok:
            self.exporta_error = error
            self.registra(f"exporta ERROR: {error}")
            self.avisa_crit("Auto Chords", f"No s'ha pogut exportar:\n{error}")
            return
        amb_part = getattr(self, "_exporta_amb_partitura",
                           self.amb_part.isChecked())
        res_part = self._exporta_partitura() if amb_part else None
        self._exporta_acabada(res_part)

    def exporta_mapa_midi_ara(self):
        """Exporta només el mapa de tempo/compàs a un `.mid` triat per l'usuari."""
        vr = getattr(self, "visor_ref", None)
        if vr is None or not getattr(vr, "tempo_trams", None):
            self.avisa_info("Exporta MIDI",
                            "Obre un projecte amb mapa de tempo primer.")
            return
        base = self.sortida or os.getcwd()
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Exporta el mapa de tempo (MIDI)",
            os.path.join(base, tempo_midi.NOM_MAPA_MIDI),
            "MIDI (*.mid)")
        if not ruta:
            return
        if not ruta.lower().endswith((".mid", ".midi")):
            ruta += ".mid"
        try:
            tipus = pipeline.llegeix_marcadors_tipus(self.sortida)
            marques = [(float(t), tipus.get(round(float(t), 6), "marcador"))
                       for t in (vr.marcadors or ())]
            tempo_midi.desa_mapa_midi(
                ruta, list(vr.tempo_trams),
                marques=marques, log=self.registra)
        except (OSError, ValueError) as e:
            self.avisa("Exporta MIDI", f"No s'ha pogut exportar el MIDI:\n{e}")
            return
        self.registra(f"MIDI del mapa exportat: {ruta}")
        self._missatge_info(f"MIDI exportat: {os.path.basename(ruta)}")

    def _exporta_partitura(self):
        """Genera el lead sheet de xifrats de la carpeta de sortida.

        Es **tolerant**: `app/partitura.py` escriu sempre el MusicXML i, només
        si troba el MuseScore, el PDF/MSCZ. Cap error d'aquí no ha de fer caure
        l'exportació normal. Retorna el diccionari de resultats (o None).

        """
        wav = self.wav_edit.text().strip() or None
        vr = getattr(self, "visor_ref", None)
        mapa = getattr(vr, "tempo_map", None)
        durada = float((getattr(vr, "audio", {}) or {}).get("durada", 0.0) or 0.0)
        # Els acords surten del MODEL viu (zero fitxers intermedis). Si encara
        # no n'hi ha, la partitura ja retorna el seu error net («sense acords»).
        ev = []
        try:
            ev = pipeline.events_partitura(
                os.path.join(self.sortida, "acords.csv"),
                self._bpm_val(), self._bpb_val(),
                durada=durada, mapa=mapa,
                den=self._beat_type_val())
        except (RuntimeError, OSError) as e:
            self.registra(f"partitura: el model encara no té acords ({e})")
        rubatos = [
            (float(t.ini), float(t.fi), t.compassos)
            for t in (getattr(vr, "tempo_trams", None) or [])
            if getattr(t, "tipus", None) == "rubato"
        ]
        try:
            res = partitura.exporta_partitura(
                self.sortida,
                log=self.registra,
                bpm=self._bpm_val(),
                bpb=self._bpb_val(),
                beat_type=self._beat_type_val(),
                bpm_unit=(getattr(getattr(self, "visor_ref", None),
                                  "unitat_objectiu",
                                  lambda: "negra")()),
                wav=wav,
                new_system_each=4,     # 4 compassos per línia (lead sheet)
                mapa=mapa,
                events=ev,
                durada=durada,
                rubatos=rubatos,
            )
            if res.get("error"):
                self.registra(f"partitura: sense resultat ({res['error']})")
            return res
        except Exception as e:  # noqa: BLE001
            self.registra(f"partitura ERROR: {e}")
            return None

    def _missatge_partitura(self, res):
        """Text clar de què s'ha generat a la partitura, deixant palès que el
        PDF i el MSCZ depenen de **MuseScore** instal·lat (l'app no l'inclou)."""
        fets = ["MusicXML"]
        if res.get("pdf"):
            fets.append("PDF")
        if res.get("mscz"):
            fets.append("MSCZ")
        linies = ["S'ha generat: " + " + ".join(fets) + " ✓"]
        for clau, etiqueta in (("musicxml", "MusicXML"), ("pdf", "PDF"),
                               ("mscz", "MSCZ")):
            if res.get(clau):
                linies.append(f"{etiqueta}: {res[clau]}")
        if not res.get("pdf"):
            linies += ["",
                       "⚠️ El PDF (i el MSCZ) NO s'han generat: la partitura en "
                       "PDF necessita MuseScore instal·lat.",
                       "Pots obrir el MusicXML amb el MuseScore que tinguis, o "
                       "instal·lar-lo (o definir la variable AUTO_CHORDS_MUSESCORE)."]
        return "\n".join(linies)

    def exporta_partitura_ara(self):
        """Accio de menu: genera NOMES la partitura de la sortida actual."""
        if not self.sortida:
            self.avisa("Auto Chords",
                                "Exporta primer (cal la carpeta de resultats).")
            return
        res = self._exporta_partitura()
        if not res or res.get("error"):
            self.avisa(
                "Auto Chords",
                "No s'ha pogut generar la partitura.\n"
                "Cal haver exportat abans, en mode BPM · compàs "
                "(cal que el model tinga almenys un acord). Detall al log.")
            return
        self.avisa_info("Auto Chords",
                                self._missatge_partitura(res))
        self.obre_carpeta()

    def obre_carpeta(self):
        if self.sortida and os.path.isdir(self.sortida):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.sortida))
        else:
            self.avisa_info("Auto Chords",
                                    "Encara no hi ha cap resultat.")
