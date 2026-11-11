"""Marcadors en viu de la finestra (F3).

Extret de `app/main.py`: encaix al beat QM i alta de marcadors. Els marcadors
són anotacions visuals: no participen en cap recalcul de tempo.
"""

class MarcadorsMixin:
    """Marcadors en viu."""

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

    def _esborra_ultim_marcador(self):
        vr = getattr(self, "visor_ref", None)
        if vr is None or not vr.elimina_marcador():
            return False
        return True
