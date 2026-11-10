"""Marcadors en viu de la finestra (F3).

Extret de `app/main.py`: encaix al beat QM, alta de marcadors, BPM derivat
dels marcadors i ajustos per lots.
"""
from . import dialeg_bpm_marcadors

class MarcadorsMixin:
    """Marcadors en viu i BPM derivat."""

    def _snap_marcador_qm(self, t):
        """Retorna el beat QM més pròxim a `t` (sempre, sense tolerància).

        El contracte nou fa que el `+` no es guarde mai a la posició crua del
        cursor si hi ha anàlisi de QM: el marcador ha de coincidir amb un beat
        de QM. Si no n'hi ha cap, retorna `None` i el cridador ha d'avisar.
        """
        info = getattr(self, "_beats_actuals", None)
        if not info:
            info = (getattr(getattr(self, "projecte", None), "dades", {})
                    .get("analisi_beats"))
        if not isinstance(info, dict):
            return None
        beats = [float(x) for x in (info.get("beats") or ())]
        downbeats = [float(x) for x in (info.get("downbeats") or ())]
        objectius = sorted(set(beats or downbeats))
        if not objectius:
            return None
        return min(objectius, key=lambda x: (abs(x - float(t)), x))

    def _afegeix_marcador(self, tipus="seccio"):
        """Camí de compatibilitat: marcador + tall de tempo/estructura.

        La UI nova fa servir `_marcador_cursor`, `_talla_tempo_cursor`,
        `_talla_estructura_cursor` i `_talla_tempo_i_estructura_cursor`.

        Contracte nou: sempre s'encaixa al **beat QM més pròxim**; si no hi ha
        QM, no es crea el marcador i s'avisa. El visor recalcula els clips
        afectats amb prioritat de BPM i ajust de compàs.
        """
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.avisa("Marcador", "Primer obri una WAV.")
            return False
        mode = (self.cb_graella.currentData()
                if hasattr(self, "cb_graella") else "") or ""
        if mode == "qm_beats":
            t = self._snap_marcador_qm(float(vr.pos))
            if t is None:
                msg = ("No s'ha afegit el marcador: el Snap està en "
                       "«Beats QM» però no hi ha beats QM. Executa "
                       "«Analitza beats, downbeats i BPM» o canvia la graella.")
                self.registra(msg)
                self._missatge_info(msg)
                return False
        else:
            # Fora del mode QM, mana la graella BPM/compàs del timeline.
            t = vr._snap_ui(float(vr.pos))
            if not (0.0 < t < vr._durada_wav() - 1e-3):
                msg = "No s'ha afegit el marcador: cau fora del tema."
                self.registra(msg)
                self._missatge_info(msg)
                return False
        ok = bool(vr.afegeix_marcador(t=t, tipus=tipus))
        if ok:
            self.registra(f"Marcador a {t:.3f}s "
                          f"({len(vr.marcadors)} en total)")
        else:
            prop = min((abs(float(m) - t) for m in (vr.marcadors or ())),
                       default=99.0)
            if prop < 0.05:
                msg = ("No s'ha afegit: ja hi ha un marcador a "
                       f"{t:.3f}s (o a menys de 50 ms).")
            else:
                msg = ("No s'ha pogut afegir el marcador: el clip resultant "
                       "no conté cap beat sencer de la graella del Snap.")
            self.registra(msg)
            self._missatge_info(msg)
        return ok


    def _t_from_cursor_ui(self):
        """Temps del cursor per a les accions M/Enter/0/+ de la Finestra."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return None
        mode = (self.cb_graella.currentData()
                if hasattr(self, "cb_graella") else "") or ""
        if mode == "qm_beats":
            t = self._snap_marcador_qm(float(vr.pos))
        else:
            t = float(vr._snap_ui(float(vr.pos)))
        if t is None or not (0.0 < t < vr._durada_wav() - 1e-3):
            msg = "El cursor no cau dins el tema; no s'ha fet cap acció."
            self.registra(msg)
            self._missatge_info(msg)
            return None
        return float(t)

    def _marcador_cursor(self):
        """M: crea un marcador lliure al cursor."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return False
        t = self._t_from_cursor_ui()
        if t is None:
            return False
        ok = bool(vr.afegeix_marcador_lliure(t))
        self.registra(
            f"Marcador lliure a {t:.3f}s" if ok
            else f"No s'ha afegit el marcador a {t:.3f}s")
        return ok

    def _talla_tempo_cursor(self):
        """Enter: talla només el tempo al cursor."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return False
        t = self._t_from_cursor_ui()
        if t is None:
            return False
        ok = bool(vr.talla_tempo(t))
        self.registra(
            f"Tempo tallat a {t:.3f}s" if ok
            else f"No s'ha pogut tallar el tempo a {t:.3f}s")
        return ok

    def _talla_estructura_cursor(self):
        """0: talla només l'estructura al cursor."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return False
        t = self._t_from_cursor_ui()
        if t is None:
            return False
        ok = bool(vr.talla_estructura(t))
        self.registra(
            f"Estructura tallada a {t:.3f}s" if ok
            else f"No s'ha pogut tallar l'estructura a {t:.3f}s")
        return ok

    def _talla_tempo_i_estructura_cursor(self):
        """+: talla tempo i estructura al cursor, sense marcador."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return False
        t = self._t_from_cursor_ui()
        if t is None:
            return False
        ok = bool(vr.talla_tempo_i_estructura(t))
        self.registra(
            f"Tempo i estructura tallats a {t:.3f}s" if ok
            else f"No s'ha pogut tallar a {t:.3f}s")
        return ok

    def _bpm_dels_marcadors(self):
        """Deduu el BPM dels marcadors i reescriu el mapa (clips editables)."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.avisa("BPM dels marcadors", "Primer obri una WAV.")
            return False
        if len(vr.marcadors or ()) < 2:
            self.avisa("BPM dels marcadors",
                       "Calen almenys dos marcadors (prem + al compàs 1 i a un "
                       "altre compàs).")
            return False
        try:
            cands = vr.candidats_bpm_marcadors(self._bpm_val(),
                                               self._bpb_val(),
                                               self._beat_type_val())
        except ValueError as e:
            self.avisa("BPM dels marcadors", str(e))
            return False
        if not cands:
            self.avisa("BPM dels marcadors",
                       "Els marcadors no quadren amb cap BPM entre 60 i 180.")
            return False
        dlg = dialeg_bpm_marcadors.DialegBpmMarcadors(
            cands, self, self._bpb_val(), self._beat_type_val())
        if dlg.exec_() != dlg.Accepted:
            return False
        triat = dlg.triat()
        if not triat:
            return False
        ok = bool(vr.aplica_bpm_marcadors(triat, self._bpb_val(),
                                          self._beat_type_val()))
        if ok:
            self._sincronitza_temps_del_visor()
            self._desa_meta_silencios()
            self.registra(
                f"BPM dels marcadors: {triat['bpm']:.2f} · "
                f"{len(triat.get('intervals') or ())} trams · "
                f"compassos {triat.get('compassos')}")
        return ok

    def _ajusta_bpms_marcadors(self):
        """Acció per lot: un beat sencer a cada interval de marcador.

        Recorre els intervals entre marcadors, conserva el BPM de referència
        i ajusta el compàs (o, si cal, un BPM proper) perquè cada clip continga
        almenys un beat sencer. S'aplica en **una sola operació de desfer**.
        """
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.avisa("Ajusta BPMs", "Primer obri una WAV.")
            return False
        if len(vr.marcadors or ()) < 2:
            self.avisa("Ajusta BPMs",
                       "Calen almenys dos marcadors (prem + a cada inici de "
                       "compàs que vulgues ajustar).")
            return False
        self._atura_si_sona("ajust dels BPMs pels marcadors")
        abans = len(vr.tempo_trams or ())
        ok = bool(vr.ajusta_bpms_marcadors())
        if ok:
            self._sincronitza_temps_del_visor()
            self.registra(
                f"Ajusta BPMs pels marcadors: {len(vr.tempo_trams)} trams "
                f"(abans {abans}), compàs 1 a {float(vr.offset):.3f}s")
            self._missatge_info(
                f"BPMs ajustats amb {len(vr.marcadors)} marcadors "
                f"({len(vr.tempo_trams)} trams). Ctrl+Z ho desfà tot.")
        return ok

    def _ajusta_bpm_minims_quadrats(self):
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.avisa("Ajusta BPM", "Primer obri una WAV.")
            return False
        if len(vr.marcadors or ()) < 2:
            self.avisa("Ajusta BPM",
                       "Calen almenys dos marcadors.")
            return False
        self._atura_si_sona("ajust del BPM per mínims quadrats")
        abans = len(vr.tempo_trams or ())
        ok = bool(vr.ajusta_bpm_minims_quadrats())
        if ok:
            self._sincronitza_temps_del_visor()
            self.registra(
                f"Ajusta BPM mínims quadrats: {len(vr.tempo_trams)} trams "
                f"(abans {abans})")
            self._missatge_info(
                f"BPM ajustat per mínims quadrats "
                f"({len(vr.tempo_trams)} trams). Ctrl+Z ho desfà tot.")
        return ok

    def _esborra_ultim_marcador(self):
        vr = getattr(self, "visor_ref", None)
        if vr is None or not vr.elimina_marcador():
            return False
        return True
