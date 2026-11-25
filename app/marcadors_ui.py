"""Marcadors en viu de la finestra (F3).

Extret de `app/main.py`: encaix al beat QM de les accions de cursor i alta de
marcadors. Els marcadors són anotacions visuals: no participen en cap recalcul
de tempo.
"""

import os

class MarcadorsMixin:
    """Marcadors en viu."""

    def _snap_marcador_qm(self, t):
        """Retorna el beat QM més pròxim a `t` (sempre, sense tolerància).

        Amb la graella en mode QM, les accions de cursor (`M`, Enter, `0`, `+`)
        no treballen mai a la posició crua: han de coincidir amb un beat de QM.
        Si no n'hi ha cap, retorna `None` i el cridador ha d'avisar.
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

    def _t_from_cursor_ui(self):
        """Temps del cursor per a les accions M/Enter/0/+ de la Finestra."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return None
        mode = (self.cb_graella.currentData()
                if hasattr(self, "cb_graella") else "") or ""
        snap_on = (bool(self.tb_snap.isChecked())
                   if hasattr(self, "tb_snap") else True)
        if snap_on and mode == "qm_beats":
            t = self._snap_marcador_qm(float(vr.pos))
            if t is None:
                # Sense QM, el motor de talls fa servir els polsos del mapa
                # actual; el cursor s'encaixa a la graella normal.
                self.registra(
                    "Snap QM sense beats detectats: uso la graella actual.")
                t = float(vr._snap_ui(float(vr.pos)))
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

    def _marca_analisi_temps(self, tipus, t):
        """Marca inici/final d'anàlisi en un temps concret (únic)."""
        from app import marcadors as M
        from app import pipeline
        vr = getattr(self, "visor_ref", None)
        if vr is None or tipus not in M.TIPUS_ANALISI:
            return False
        t = float(t)
        if not (0.0 < t < vr._durada_wav() - 1e-3):
            return False
        abans = list(vr.marcadors or ())
        tipos = dict(vr.marcador_tipus or {})
        marques = [float(x) for x in abans
                   if tipos.get(round(float(x), 6)) != tipus]
        propi = [float(x) for x in marques
                 if abs(float(x) - t) < M.SEPARACIO_MIN]
        if propi:
            final_t = min(propi, key=lambda x: abs(x - t))
        else:
            marques = M.afegeix(marques, t, vr._durada_wav())
            if not marques:
                return False
            final_t = min(marques, key=lambda x: abs(float(x) - t))
        tipos = {round(float(x), 6): tp for x, tp in tipos.items()
                 if tp != tipus}
        tipos[round(float(final_t), 6)] = tipus
        if hasattr(vr, "_undo_marca"):
            vr._undo_marca()
        vr.marcadors = M.normalitza_marcadors(marques, vr._durada_wav())
        vr.marcador_tipus = tipos
        if hasattr(vr, "_undo_commit"):
            vr._undo_commit()
        if hasattr(vr, "_pinta_marcadors"):
            vr._pinta_marcadors()
        try:
            pipeline.desa_marcadors(
                vr._carpeta_acords(),
                [(m, vr.marcador_tipus.get(round(float(m), 6), "marcador"))
                 for m in (vr.marcadors or ())])
        except OSError:
            pass
        self.registra(f"{tipus} a {final_t:.3f}s")
        return True

    def _marca_analisi_cursor(self, tipus):
        """Marca l'inici o el final d'anàlisi al cursor (marcador únic)."""
        t = self._t_from_cursor_ui()
        if t is None:
            return False
        return self._marca_analisi_temps(tipus, t)

    def _proposa_onsets_guia(self, tipus):
        """Proposa un onset per a inici/final i deixa triar l'usuari."""
        from PyQt5.QtWidgets import QInputDialog
        from app import marcadors as M
        from app import tempo
        vr = getattr(self, "visor_ref", None)
        wav = self.wav_edit.text().strip()
        if vr is None or not wav or not os.path.isfile(wav):
            self.avisa_info("Guia ràpida", "Primer obri una WAV.")
            return False
        if tipus not in M.TIPUS_ANALISI:
            return False
        marcat = [float(t) for t, tp in (vr.marcador_tipus or {}).items()
                  if tp == tipus]
        base = min(marcat, key=lambda x: abs(x - float(vr.pos)))             if marcat else float(vr.pos)
        cfg = self.opcions.get("beats") or {}
        prom = float(cfg.get("prominencia_db", 0.0) or 0.0)
        trans = float(cfg.get("transiente_db", 0.0) or 0.0)
        candidats = tempo.proposa_onsets(
            wav, base, finestra=0.35, n=3, refina=True,
            log=self.registra,
            prominencia_db=prom if prom > 0 else None,
            transiente_db=trans if trans > 0 else None)
        if not candidats:
            self.avisa_info(
                "Guia ràpida",
                "No s'ha trobat cap onset a prop. Mou el cursor i torna-ho "
                "a provar.")
            return False
        etiquetes = [f"{t:.3f} s" for t in candidats]
        triat, ok = QInputDialog.getItem(
            self, "Proposa onset", f"Onset per a {tipus}:",
            etiquetes, 0, False)
        if not ok:
            return False
        idx = etiquetes.index(triat) if triat in etiquetes else 0
        return self._marca_analisi_temps(tipus, candidats[idx])

    def _proposa_bpm_guia(self):
        """Proposa BPM per al rang d'anàlisi i deixa triar; no aplica res."""
        from PyQt5.QtWidgets import QInputDialog
        from app import tempo
        vr = getattr(self, "visor_ref", None)
        wav = self.wav_edit.text().strip()
        if vr is None or not wav or not os.path.isfile(wav):
            self.avisa_info("Guia ràpida", "Primer obri una WAV.")
            return None
        rang = vr.rang_analisi() if hasattr(vr, "rang_analisi") else None
        if rang is None:
            self.avisa_info(
                "Guia ràpida",
                "Marca l'inici i el final de l'anàlisi abans de proposar BPM.")
            return None
        cfg = self.opcions.get("bpm") or {}
        res = tempo.proposa_bpm(
            wav, rang[0], rang[1], log=self.registra,
            bpm_min=cfg.get("min"), bpm_max=cfg.get("max"),
            preferit=(cfg.get("pref_min"), cfg.get("pref_max")), n=3)
        cands = list(res.get("candidats") or ())
        if not cands:
            self.avisa_info("Guia ràpida", "No s'han trobat candidats de BPM.")
            return None
        etiquetes = [f"{float(b):.3f} BPM · confiança {float(c):.2f}"
                     for b, c in cands]
        triat, ok = QInputDialog.getItem(
            self, "Proposa BPM", "Candidats de BPM per al rang:",
            etiquetes, 0, False)
        if not ok:
            return None
        idx = etiquetes.index(triat) if triat in etiquetes else 0
        bpm = float(cands[idx][0])
        self._guia_bpm_triat = bpm
        self.registra(f"BPM proposat per a la Guia: {bpm:.3f}")
        return f"BPM triat: {bpm:.3f}"

    def _diagnostica_estabilitat_guia(self):
        """Comprova estabilitat del rang; només mostra el diagnòstic."""
        from app import tempo
        vr = getattr(self, "visor_ref", None)
        wav = self.wav_edit.text().strip()
        if vr is None or not wav or not os.path.isfile(wav):
            self.avisa_info("Guia ràpida", "Primer obri una WAV.")
            return None
        rang = vr.rang_analisi() if hasattr(vr, "rang_analisi") else None
        if rang is None:
            self.avisa_info(
                "Guia ràpida",
                "Marca l'inici i el final de l'anàlisi abans de comprovar.")
            return None
        bpm = getattr(self, "_guia_bpm_triat", None)
        res = tempo.diagnostica_estabilitat(
            wav, rang[0], rang[1], bpm=bpm, log=self.registra,
            t_ancla=rang[0])
        self._guia_diagnostic = res
        if res.get("bpm") is None:
            text = f"{res.get('estat')} · {res.get('motiu') or 'sense dades'}"
        else:
            emax = res.get("e_max")
            efin = res.get("e_final")
            fmt = lambda x: "—" if x is None else f"{x * 1000:.1f} ms"
            gap = res.get("gap")
            avis = " · ⚠️ gap >20 ms" if gap is not None and abs(gap) > 0.020 else ""
            text = (f"{res['estat']} · BPM {res['bpm']:.3f} · "
                    f"e_max {fmt(emax)} · e_final {fmt(efin)} · "
                    f"gap {fmt(gap)}{avis} · "
                    f"{res.get('n_inliers', 0)}/{res.get('n', 0)} inliers")
        self.registra("Estabilitat: " + text)
        return text

    def _proposa_mapa_guia(self):
        """Proposa el mapa del rang; no aplica res."""
        from app import mapa_tempo, tempo
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.avisa_info("Guia ràpida", "Primer obri una WAV.")
            return None
        rang = vr.rang_analisi() if hasattr(vr, "rang_analisi") else None
        if rang is None:
            self.avisa_info(
                "Guia ràpida",
                "Marca l'inici i el final de l'anàlisi abans de proposar.")
            return None
        bpm = getattr(self, "_guia_bpm_triat", None)
        if bpm is None:
            diag = getattr(self, "_guia_diagnostic", None) or {}
            bpm = diag.get("bpm")
        if bpm is None:
            self.avisa_info(
                "Guia ràpida",
                "Proposa o tria un BPM abans de proposar el mapa.")
            return None
        try:
            proposta, avisos = mapa_tempo.proposa_mapa_rang(
                vr.tempo_trams or (), rang[0], rang[1], float(bpm),
                self._transport_bpb(), self._transport_beat_type(),
                vr._durada_wav(), beat_unit=vr.unitat_objectiu())
        except ValueError as e:
            self.avisa_info("Guia ràpida", f"No es pot proposar el mapa: {e}")
            return None
        if not proposta:
            self.avisa_info("Guia ràpida", "No s'ha pogut calcular la proposta.")
            return None
        cos = min(proposta, key=lambda t: abs(float(t.ini) - rang[0])
                  + abs(float(t.fi) - rang[1]))
        res = tempo.proposa_mapa_bpm(
            float(cos.fi) - float(cos.ini), float(cos.bpm),
            self._transport_bpb(), self._transport_beat_type())
        if not res:
            self.avisa_info("Guia ràpida", "No s'ha pogut calcular la proposta.")
            return None
        self._guia_mapa = res
        self._guia_mapa_trams = list(proposta)
        self._guia_mapa_rang = (float(rang[0]), float(rang[1]))
        avis = " · N enter" if res["n_enter_valid"] else " · N no enter"
        text = (f"{len(proposta)} clip(s) · cos {cos.ini:.3f}–{cos.fi:.3f} s "
                f"a {cos.bpm:.3f} BPM · N {res['n']:.3f}{avis}")
        if avisos:
            text += f" · {len(avisos)} avís(os)"
        self.registra("Proposta de mapa: " + text)
        return text

    def _aplica_mapa_guia(self):
        """Aplica la proposta de mapa, amb confirmació i un sol desfer."""
        from PyQt5.QtWidgets import QMessageBox
        vr = getattr(self, "visor_ref", None)
        proposta = getattr(self, "_guia_mapa_trams", None)
        rang = getattr(self, "_guia_mapa_rang", None)
        if vr is None or not proposta:
            self.avisa_info(
                "Guia ràpida", "Proposa un mapa abans d'aplicar-lo.")
            return False
        act = vr.rang_analisi() if hasattr(vr, "rang_analisi") else None
        if (rang is None or act is None
                or abs(float(act[0]) - rang[0]) > 1e-3
                or abs(float(act[1]) - rang[1]) > 1e-3):
            self.avisa_info(
                "Guia ràpida",
                "Els marcadors han canviat: torna a proposar el mapa.")
            return False
        cos = min(proposta, key=lambda t: abs(float(t.ini) - rang[0])
                  + abs(float(t.fi) - rang[1]))
        text = (f"Aplicar el mapa proposat?\n\n"
                f"{len(proposta)} clip(s); cos {cos.ini:.3f}–{cos.fi:.3f} s "
                f"a {cos.bpm:.3f} BPM.\n"
                "Els clips de fora del rang es conserven.")
        if QMessageBox.question(
                self, "Aplica mapa", text,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No) != QMessageBox.Yes:
            return False
        if hasattr(vr, "_undo_marca"):
            vr._undo_marca()
        try:
            ok = bool(vr.aplica_tempo_trams(proposta))
        except (ValueError, RuntimeError) as e:
            self.avisa_info("Guia ràpida", f"No s'ha pogut aplicar: {e}")
            ok = False
        if hasattr(vr, "_undo_commit"):
            vr._undo_commit()
        if ok:
            self.registra(f"Mapa aplicat: {len(proposta)} clip(s)")
        return ok

    def _aplica_bpm_guia(self):
        """Aplica el BPM proposat; preserva el clip seleccionat si en hi ha."""
        from PyQt5.QtWidgets import QMessageBox
        from app import mapa_tempo
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.avisa_info("Guia ràpida", "Primer obri una WAV.")
            return False
        trams = list(getattr(vr, "tempo_trams", None) or ())
        bpm = getattr(self, "_guia_bpm_triat", None)
        if bpm is None:
            diag = getattr(self, "_guia_diagnostic", None) or {}
            bpm = diag.get("bpm")
        if bpm is None:
            self.avisa_info("Guia ràpida",
                            "Proposa o tria un BPM abans d'aplicar-lo.")
            return False
        kind, idx = vr.seleccio_activa()
        te_tempo = (kind == "tempo" and 0 <= int(idx) < len(trams))
        if len(trams) > 1 and te_tempo:
            if QMessageBox.question(
                    self, "Aplica BPM",
                    f"Aplicar {float(bpm):.3f} BPM al clip {int(idx) + 1} "
                    "sense moure les fronteres?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No) != QMessageBox.Yes:
                return False
            try:
                ok = bool(vr.retempo_tram_detectat(int(idx), float(bpm)))
            except (ValueError, RuntimeError) as e:
                self.avisa_info("Guia ràpida", f"No s'ha pogut aplicar: {e}")
                return False
            if ok:
                self.registra(
                    f"BPM aplicat al clip {int(idx) + 1}: {float(bpm):.3f}")
            return ok
        num = int(self._transport_bpb())
        den = int(self._transport_beat_type())
        if trams:
            missatge = (
                f"Substituir el mapa actual ({len(trams)} clip(s)) per un sol "
                f"clip a {float(bpm):.3f} BPM?")
        else:
            missatge = f"Crear un clip de tempo a {float(bpm):.3f} BPM?"
        if QMessageBox.question(
                self, "Aplica BPM", missatge,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No) != QMessageBox.Yes:
            return False
        tr = mapa_tempo.TramMapa(
            0.0, vr._durada_wav(), float(bpm), "normal", f"{num}/{den}",
            "", None, vr.unitat_objectiu())
        try:
            ok = bool(vr.aplica_tempo_trams([tr]))
        except (ValueError, RuntimeError) as e:
            self.avisa_info("Guia ràpida", f"No s'ha pogut aplicar: {e}")
            return False
        if ok:
            self.registra(f"BPM aplicat al mapa: {float(bpm):.3f}")
        return ok

    def _talla_tempo_cursor(self):
        """Fin: talla només el tempo al cursor."""
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
