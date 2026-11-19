"""Franja Editor del visor (F4).

Extret de `app/visor.py`: actualització i aplicació dels camps de l'editor
d'acords, estructura i tempo/rubato.
"""
import re

from . import bpm_unit as bpm_unit_mod
from . import limits, mapa_tempo, pipeline, tempo_map, tempo_recalc
from .visor_io import nom_acord

class EditorMixin:
    """Franja Editor del visor."""

    def _actualitza_editor(self):
        """Mostra a la franja Editor l'element seleccionat (o el buit)."""
        k, i = getattr(self, "_ed_kind", None), getattr(self, "_ed_idx", -1)
        # La franja és compartida: cada mode hi posa les seues etiquetes.
        self.ed_nom_lbl.setText("Nom:")
        self.ed_fam_lbl.setText("Família:")
        self.ed_agr_lbl.setVisible(False)
        self.ed_agr.setVisible(False)
        self.ed_n_lbl.setVisible(False)
        self.ed_n.setVisible(False)
        self.ed_rol_lbl.setVisible(False)
        self.ed_ini_lbl.setVisible(False)
        self.ed_ini.setVisible(False)
        self.ed_ini.setEnabled(True)
        self.ed_cb_lbl.setText("≈")
        self.ed_cb_fi_lbl.setVisible(False)
        self.ed_cb_fi.setVisible(False)
        self.ed_cb.setEnabled(True)
        self.ed_bpm_compas.setVisible(False)
        self.ed_bpm_compas.setEnabled(False)
        for w in (self.ed_bpm_fix, self.ed_bpm_aplica,
                  self.ed_bpm_x2, self.ed_bpm_div2,
                  self.ed_compas_fix, self.ed_compas_aplica,
                  self.ed_n_fix, self.ed_n_aplica, self.ed_agr_aplica):
            w.setVisible(False)
        if k == "tempo" and 0 <= i < len(getattr(self, "tempo_trams", None) or []):
            tr = self.tempo_trams[i]
            ini, fi, bpm = float(tr[0]), float(tr[1]), float(tr[2])
            self.ed_gran.setText(f"TOTAL: {fi - ini:.2f} s")
            self.ed_nom_lbl.setText("BPM:")
            self.ed_nom.setToolTip(
                "BPM del clip (30–350, en "
                f"{bpm_unit_mod.etiqueta(self.bpm_unit).lower()})")
            self.ed_nom.setText(self.bpm_mostra(bpm))
            self.ed_fam_lbl.setText("Compàs:")
            self.ed_fam.setToolTip("Compàs num/den")
            self.ed_fam.setText(f"{int(tr[3])}/{int(tr[4])}")
            self.ed_fam.setVisible(True)
            self.ed_fam_lbl.setVisible(True)
            self.ed_agr_lbl.setVisible(True)
            self.ed_agr.setVisible(True)
            self.ed_agr.setText(getattr(tr, "agrupacio", ""))
            self.ed_agr.setPlaceholderText(
                self._suggeriment_agrupacio(int(tr.num), int(tr.den)))
            self.ed_agr.setToolTip(
                "Grups de temps del compàs (p. ex. 3+3, 2+2+3). "
                "Buit = automàtic; per als irregulars, tria l'agrupació.")
            self.ed_n_lbl.setVisible(True)
            self.ed_n.setVisible(True)
            n_val = getattr(tr, "n", None)
            if n_val is None:
                try:
                    n_val = tempo_map.compassos_del_clip(tr)
                except (TypeError, ValueError):
                    n_val = 0.0
            self.ed_n.setText(f"{float(n_val):.3f}")
            self.ed_n.setToolTip(
                "Nombre de compassos: sempre un enter (tots els clips, "
                "primer i últim inclosos).")
            rol = tempo_map.rol_tram(self.tempo_trams, i)
            self.ed_rol_lbl.setText(f"Rol: {rol}")
            self.ed_rol_lbl.setVisible(True)
            self.ed_cb_lbl.setText("Ini (c):")
            self.ed_cb.setText(self._secs_a_cb(ini))
            self.ed_cb.setEnabled(True)
            self.ed_cb_fi_lbl.setVisible(True)
            self.ed_cb_fi.setVisible(True)
            self.ed_cb_fi.setEnabled(True)
            self.ed_cb_fi.setText(self._secs_a_cb(fi))
            self._ed_cb_ini_text = self.ed_cb.text()
            self._ed_cb_fi_text = self.ed_cb_fi.text()
            self.ed_bpm_compas.setVisible(True)
            self.ed_bpm_compas.setEnabled(True)
            ultim = (i == len(self.tempo_trams) - 1)
            for w in (self.ed_nom, self.ed_fam, self.ed_agr, self.ed_n,
                      self.ed_aplica, self.ed_bpm_fix,
                      self.ed_bpm_aplica, self.ed_bpm_x2,
                      self.ed_bpm_div2, self.ed_compas_fix,
                      self.ed_compas_aplica, self.ed_n_fix,
                      self.ed_n_aplica, self.ed_agr_aplica):
                w.setEnabled(True)
            self.ed_bpm_fix.setVisible(True)
            self.ed_bpm_aplica.setVisible(True)
            self.ed_bpm_x2.setVisible(True)
            self.ed_bpm_div2.setVisible(True)
            self.ed_compas_fix.setVisible(True)
            self.ed_compas_aplica.setVisible(True)
            self.ed_n_fix.setVisible(True)
            self.ed_n_aplica.setVisible(True)
            self.ed_agr_aplica.setVisible(True)
            # El recalc mòbil no pot moure la fi de l'últim clip.
            self.ed_bpm_aplica.setEnabled(not ultim)
            self.ed_compas_aplica.setEnabled(not ultim)
            self.ed_n_aplica.setEnabled(not ultim)
            self.ed_aplica.setEnabled(not ultim)
            self.ed_aplica.setToolTip(
                ("Aplica no està disponible a l'últim clip: la fi de la WAV "
                 "és fixa. Usa «Ajusta» per obrir el diàleg del tram.")
                if ultim else "Recalc mòbil: aplica els canvis (Enter)")
        elif k == "chord" and 0 <= i < len(self.acords):
            t, nom = float(self.acords[i][0]), nom_acord(self.acords[i])
            self.ed_gran.setText(nom)
            self.ed_nom.setText(nom)
            self.ed_nom.setToolTip("Nom de l'acord o lletra de la secció")
            self.ed_fam.setToolTip("Família de la secció (p. ex. N, A, B)")
            self.ed_ini_lbl.setVisible(True)
            self.ed_ini.setVisible(True)
            self.ed_ini.setText(f"{float(t):.3f}")
            self.ed_cb_lbl.setText("≈")
            self.ed_cb.setText(self._secs_a_cb(float(t)))
            self.ed_fam.setVisible(False); self.ed_fam_lbl.setVisible(False)
            self.ed_agr_lbl.setVisible(False); self.ed_agr.setVisible(False)
            self.ed_n_lbl.setVisible(False); self.ed_n.setVisible(False)
            self.ed_rol_lbl.setVisible(False)
            for w in (self.ed_nom, self.ed_ini, self.ed_cb, self.ed_aplica):
                w.setEnabled(True)
            self.ed_agr_aplica.setVisible(False)
            self.ed_aplica.setToolTip("Aplica els canvis (Enter)")
        elif k == "section" and 0 <= i < len(self.seccions):
            ini, fi, lletra, fam = self.seccions[i]
            self.ed_gran.setText(f"{lletra} ({fam})")
            self.ed_nom.setText(lletra)
            self.ed_fam.setText(fam)
            self.ed_ini_lbl.setVisible(True)
            self.ed_ini.setVisible(True)
            self.ed_ini.setText(f"{float(ini):.3f}")
            self.ed_cb_lbl.setText("≈")
            self.ed_cb.setText(self._secs_a_cb(float(ini)))
            self.ed_fam.setVisible(True); self.ed_fam_lbl.setVisible(True)
            self.ed_agr_lbl.setVisible(False); self.ed_agr.setVisible(False)
            self.ed_n_lbl.setVisible(False); self.ed_n.setVisible(False)
            self.ed_rol_lbl.setVisible(False)
            for w in (self.ed_nom, self.ed_fam, self.ed_ini, self.ed_cb,
                      self.ed_aplica):
                w.setEnabled(True)
            self.ed_agr_aplica.setVisible(False)
            self.ed_aplica.setToolTip("Aplica els canvis (Enter)")
        else:
            self.ed_gran.setText("Selecciona un acord o una secció")
            for w in (self.ed_nom, self.ed_fam, self.ed_agr, self.ed_n,
                      self.ed_ini, self.ed_cb, self.ed_aplica,
                      self.ed_agr_aplica):
                w.setEnabled(False)
            self.ed_aplica.setToolTip("Recalc mòbil: aplica els canvis (Enter)")
            self.ed_bpm_compas.setVisible(False)
            self.ed_bpm_compas.setEnabled(False)
            self.ed_nom.clear(); self.ed_fam.clear(); self.ed_agr.clear()
            self.ed_n.clear()
            self.ed_ini.clear(); self.ed_cb.clear(); self.ed_cb_fi.clear()

    def avis_editor(self, text):
        """Avís de la franja Editor: al log I a la caixa d'informació.

        MAI en silenci: abans, sis camins de `_aplica_editor` tornaven sense dir
        res i el botó «Aplica» semblava no fer res (OC-6/394).
        """
        self.log(f"editor: {text}")
        self.infoMissatge.emit(text)

    @staticmethod
    def _suggeriment_agrupacio(num, den):
        """Text d'ajuda per a l'agrupació; no és una agrupació imposada."""
        return {
            (5, 8): "5 (o una altra agrupació)",
            (7, 8): "7 (o una altra agrupació)",
            (8, 8): "8 (o una altra agrupació)",
            (5, 4): "p. ex. 3+2 o 2+3",
            (7, 4): "p. ex. 4+3 o 3+4",
            (10, 8): "p. ex. 3+3+2+2",
            (11, 8): "p. ex. 3+3+3+2",
            (9, 8): "3+3+3",
            (12, 8): "3+3+3+3",
        }.get((num, den), "3+3" if num in (6, 9, 12) else "Auto")

    @staticmethod
    def _agr_en_canvi_compas(tr, num, den):
        """Agrupació per defecte si el compàs canvia i la vella era automàtica."""
        agr = getattr(tr, "agrupacio", "") or ""
        if agr or (int(tr.num), int(tr.den)) == (int(num), int(den)):
            return agr
        return tempo_map.agrupacio_a_text(
            tempo_map.agrupacio_compas(int(num), int(den)))

    def _aplica_editor_var_fix(self, camp):
        """Aplica només una variable amb **recalc fix** (fronteres fixes).

        El camp triat mana: es conserva el seu valor exacte, no es mouen
        `ini`/`fi` i es recalcula el que calga (N, BPM o compàs).
        """
        k, i = getattr(self, "_ed_kind", None), getattr(self, "_ed_idx", -1)
        if k != "tempo" or not (0 <= i < len(self.tempo_trams or [])):
            self.avis_editor("Selecciona un clip de tempo abans d'aplicar.")
            return False
        trams = list(self.tempo_trams or [])
        tr = trams[i]
        ultim = (i == len(trams) - 1)
        try:
            ini, fi = float(tr[0]), float(tr[1])
            dt = fi - ini
            if dt <= tempo_map.TOL:
                raise ValueError("El clip no té durada.")
            num, den = int(tr.num), int(tr.den)
            bpm = float(tr.bpm)
            if camp == "compas":
                m = re.match(r"^\s*(\d+)\s*[/:]\s*(\d+)\s*$",
                             self.ed_fam.text().strip())
                if not m:
                    raise ValueError("El compàs ha de ser num/den (p. ex. 7/4).")
                num, den = int(m.group(1)), int(m.group(2))
                bpm, num, den = tempo_map.valida_tempo(bpm, num, den)
            elif camp == "bpm":
                bpm = self.bpm_entrada(self.ed_nom.text())
                bpm, num, den = tempo_map.valida_tempo(bpm, num, den)
            elif camp != "n":
                return False
            bq = float(num) * 4.0 / float(den)
            n_actual = getattr(tr, "n", None)
            if n_actual is None:
                n_actual = tempo_map.compassos_del_clip(tr)
            n_actual = float(n_actual)
            if camp == "n":
                n_obj = float(self.ed_n.text().strip().replace(",", "."))
                inferit = self._inferir_compas_qm(i, n_obj)
                if inferit is not None:
                    num, den, _n_qm = inferit
                    bq = float(num) * 4.0 / float(den)
                bpm_obj = n_obj * bq * 60.0 / dt
            else:
                # BPM i compàs són exactes: N deriva de la durada fixa.
                n_obj = dt * bpm / (bq * 60.0)
                bpm_obj = float(bpm)
            if n_obj <= 0:
                raise ValueError("N ha de ser positiu.")
            n_qm = self._qm_n_enter(i, num, den)
            if ultim:
                n_final = float(n_obj)
                if n_qm is not None and int(round(n_final)) != n_qm:
                    raise ValueError(
                        f"Snap Beats QM: amb {num}/{den} el N ha de ser "
                        f"{n_qm}, no {int(round(n_final))}.")
            else:
                n_final = int(round(n_obj))
                if abs(n_obj - n_final) > 1e-3:
                    if camp == "compas":
                        raise ValueError(
                            f"Amb el compàs {num}/{den} i el BPM actual, "
                            f"el N seria {n_obj:.3f}, no enter; cal canviar "
                            "el BPM o triar un altre compàs.")
                    raise ValueError(
                        f"Amb el BPM {bpm:.3f} i les fronteres fixes, el N "
                        f"seria {n_obj:.3f}, no enter; cal canviar el BPM "
                        "o triar un altre compàs.")
                if n_qm is not None and n_final != n_qm:
                    raise ValueError(
                        f"Snap Beats QM: amb {num}/{den} el N ha de ser "
                        f"{n_qm}, no {n_final}.")
            if not (limits.BPM_MIN <= bpm_obj <= limits.BPM_MAX):
                raise ValueError("El BPM resultant ix de la banda permesa")
            agr = (self._agr_en_canvi_compas(tr, num, den)
                   if camp == "compas" else getattr(tr, "agrupacio", ""))
            unit = self.unitat_de_tram(tr)
            if camp == "compas":
                provisional = mapa_tempo.TramMapa(
                    ini, fi, bpm_obj, tr.tipus, f"{num}/{den}", agr,
                    n_final, unit)
                unit = self._unitat_en_canvi_compas(tr, provisional, None)
            nou = mapa_tempo.TramMapa(
                ini, fi, float(bpm_obj), tr.tipus, f"{num}/{den}", agr,
                float(n_final), unit)
            nous = list(trams)
            nous[i] = nou
        except (TypeError, ValueError, AttributeError) as e:
            self.avis_editor(str(e))
            return False
        if not self._valida_unitat_tram(nous[i], "Editor"):
            return False
        self._undo_marca()
        try:
            ok = bool(self.aplica_tempo_trams(nous))
        finally:
            self._undo_commit()
        self._actualitza_editor()
        return ok

    def _inferir_compas_qm(self, idx, n):
        """Amb Snap QM, troba el compàs que fa encaixar N amb els beats."""
        beats = list(self._beats_per_validacio() or ())
        if not beats:
            return None
        trams = list(self.tempo_trams or [])
        if not (0 <= int(idx) < len(trams)):
            return None
        tr = trams[int(idx)]
        factor = self.beat_factor(self.unitat_de_tram(tr))
        negres = tempo_recalc.n_negres_del_clip(
            beats, float(tr.ini), float(tr.fi), factor)
        if negres is None:
            raise ValueError(
                "Snap Beats QM: no hi ha cap beat detectat dins del clip.")
        try:
            res = tempo_recalc.recalculca_tram(
                float(tr.fi) - float(tr.ini), float(tr.bpm),
                int(tr.num), int(tr.den), n_ref=int(round(float(n))),
                n_beats=float(negres), mode="beats", bloca_compas=False)
        except ValueError as e:
            raise ValueError(f"Snap Beats QM: {e}") from e
        if res is None:
            raise ValueError(
                "Snap Beats QM: no hi ha cap compàs que encaixe amb "
                f"N={int(round(float(n)))} i els beats detectats.")
        return int(res["num"]), int(res["den"]), int(res["n"])

    def _aplica_bpm_factor(self, factor):
        """Dobla o dividix el BPM amb recalc fix (fronteres fixes)."""
        k, i = getattr(self, "_ed_kind", None), getattr(self, "_ed_idx", -1)
        if k != "tempo" or not (0 <= i < len(self.tempo_trams or [])):
            self.avis_editor("Selecciona un clip de tempo abans d'aplicar.")
            return False
        trams = list(self.tempo_trams or [])
        tr = trams[i]
        try:
            ini, fi = float(tr.ini), float(tr.fi)
            dt = fi - ini
            if dt <= tempo_map.TOL:
                raise ValueError("El clip no té durada.")
            bpm = float(tr.bpm) * float(factor)
            bpm, num, den = tempo_map.valida_tempo(bpm, int(tr.num),
                                                   int(tr.den))
            bq = float(num) * 4.0 / float(den)
            n_obj = dt * bpm / (bq * 60.0)
            ultim = (i == len(trams) - 1)
            n_final = float(n_obj) if ultim else int(round(n_obj))
            if not ultim and abs(n_obj - n_final) > 1e-3:
                raise ValueError(
                    f"Amb este BPM i les fronteres fixes, el N seria "
                    f"{n_obj:.3f}; no és enter.")
            n_qm = self._qm_n_enter(i, num, den)
            if n_qm is not None and int(round(n_final)) != n_qm:
                raise ValueError(
                    f"Snap Beats QM: amb {num}/{den} el N ha de ser "
                    f"{n_qm}, no {int(round(n_final))}.")
            nou = mapa_tempo.TramMapa(
                ini, fi, float(bpm), tr.tipus, f"{int(num)}/{int(den)}",
                getattr(tr, "agrupacio", ""), float(n_final),
                getattr(tr, "beat_unit", None))
            nous = list(trams)
            nous[i] = nou
        except (TypeError, ValueError, AttributeError) as e:
            self.avis_editor(str(e))
            return False
        self._undo_marca()
        try:
            ok = bool(self.aplica_tempo_trams(nous))
        finally:
            self._undo_commit()
        self._actualitza_editor()
        return ok

    def _edita_bpm_mobil(self, idx, bpm):
        """Aplica BPM movent la frontera però conservant N i compàs."""
        trams = list(self.tempo_trams or ())
        idx = int(idx)
        if not (0 <= idx < len(trams)):
            self.avis_editor("Aquest clip de tempo ja no existeix.")
            return False
        if idx == len(trams) - 1:
            self.avis_editor(
                "El recalc mòbil no pot moure la fi de l'últim clip.")
            return False
        tr = trams[idx]
        n_actual = getattr(tr, "n", None)
        if n_actual is None:
            n_actual = tempo_map.compassos_del_clip(tr)
        n_actual = int(round(float(n_actual)))
        if n_actual < 1:
            self.avis_editor("N ha de ser com a mínim 1.")
            return False
        n_qm = self._qm_n_enter(idx, int(tr.num), int(tr.den))
        if n_qm is not None and n_actual != n_qm:
            self.avis_editor(
                f"Snap Beats QM: amb {int(tr.num)}/{int(tr.den)} el N ha "
                f"de ser {n_qm}, no {n_actual}.")
            return False
        try:
            nous = mapa_tempo.recalcula_tram_c(
                trams, idx, self._durada_wav(), n=n_actual,
                bpm=float(bpm), num=int(tr.num), den=int(tr.den),
                camp="n", permet_ultim_fraccionari=False)
        except ValueError as e:
            self.avis_editor(f"Tempo: {e}")
            return False
        if not self._valida_unitat_tram(nous[idx], "Tempo"):
            return False
        return bool(self.aplica_tempo_trams(nous))

    def _edita_compas_mobil(self, idx, num, den):
        """Aplica compàs movent la frontera: conserva N i el BPM visible."""
        trams = list(self.tempo_trams or ())
        idx = int(idx)
        if not (0 <= idx < len(trams)):
            self.avis_editor("Aquest clip de tempo ja no existeix.")
            return False
        if idx == len(trams) - 1:
            self.avis_editor(
                "El recalc mòbil no pot moure la fi de l'últim clip.")
            return False
        tr = trams[idx]
        num, den = int(num), int(den)
        try:
            tempo_map.valida_tempo(float(tr.bpm), num, den)
        except ValueError as e:
            self.avis_editor(f"Tempo: {e}")
            return False
        n_actual = getattr(tr, "n", None)
        if n_actual is None:
            n_actual = tempo_map.compassos_del_clip(tr)
        n_actual = int(round(float(n_actual)))
        if n_actual < 1:
            self.avis_editor("N ha de ser com a mínim 1.")
            return False
        n_qm = self._qm_n_enter(idx, num, den)
        if n_qm is not None and n_actual != n_qm:
            self.avis_editor(
                f"Snap Beats QM: amb {num}/{den} el N ha de ser "
                f"{n_qm}, no {n_actual}.")
            return False
        unit_vella = self.unitat_de_tram(tr)
        agr_nova = self._agr_en_canvi_compas(tr, num, den)
        bpm_visible = bpm_unit_mod.de_quarter(float(tr.bpm), unit_vella)
        provisional = mapa_tempo.TramMapa(
            float(tr.ini), float(tr.fi), float(tr.bpm), tr.tipus,
            f"{num}/{den}", agr_nova,
            getattr(tr, "n", None), unit_vella)
        try:
            unit_nova = self._unitat_en_canvi_compas(tr, provisional, None)
            bpm_intern = bpm_unit_mod.a_quarter(bpm_visible, unit_nova)
            try:
                nous = mapa_tempo.recalcula_tram_c(
                    trams, idx, self._durada_wav(), n=n_actual,
                    bpm=bpm_intern, num=num, den=den,
                    camp="n", permet_ultim_fraccionari=False)
            except ValueError:
                # En signaturas irregulars, mantindre el número visible pot
                # fer inviable el veí; es conserva el tempo intern.
                nous = mapa_tempo.recalcula_tram_c(
                    trams, idx, self._durada_wav(), n=n_actual,
                    bpm=float(tr.bpm), num=num, den=den,
                    camp="n", permet_ultim_fraccionari=False)
        except ValueError as e:
            self.avis_editor(f"Tempo: {e}")
            return False
        nous = self._amb_unitat(nous, idx, unit_nova)
        nous[idx] = mapa_tempo.TramMapa(
            nous[idx].ini, nous[idx].fi, nous[idx].bpm, nous[idx].tipus,
            nous[idx].compassos, agr_nova, nous[idx].n, nous[idx].beat_unit)
        if not self._valida_unitat_tram(nous[idx], "Tempo"):
            return False
        return bool(self.aplica_tempo_trams(nous))

    def _edita_n_mobil(self, idx, n):
        """Aplica N movent la frontera compartida, amb BPM i compàs actuals."""
        trams = list(self.tempo_trams or [])
        idx = int(idx)
        if not (0 <= idx < len(trams)):
            self.avis_editor("Aquest clip de tempo ja no existeix.")
            return False
        if idx == len(trams) - 1:
            self.avis_editor(
                "El recalc mòbil no pot moure la fi de l'últim clip.")
            return False
        tr = trams[idx]
        n = float(n)
        n_int = int(round(n))
        if n <= 0 or abs(n - n_int) > 1e-3:
            self.avis_editor("N ha de ser un enter positiu.")
            return False
        num, den = int(tr.num), int(tr.den)
        try:
            inferit = self._inferir_compas_qm(idx, n_int)
            if inferit is not None:
                num, den, _n_qm = inferit
            else:
                n_qm = self._qm_n_enter(idx, num, den)
                if n_qm is not None and n_int != n_qm:
                    raise ValueError(
                        f"Snap Beats QM: amb {num}/{den} el N ha de ser "
                        f"{n_qm}, no {n_int}.")
            nous = mapa_tempo.recalcula_tram_c(
                trams, idx, self._durada_wav(), n=n_int,
                bpm=float(tr.bpm), num=num, den=den,
                camp="n", permet_ultim_fraccionari=False)
        except ValueError as e:
            self.avis_editor(f"Tempo: {e}")
            return False
        if not self._valida_unitat_tram(nous[idx], "Tempo"):
            return False
        return bool(self.aplica_tempo_trams(nous))

    def _aplica_editor_var(self, camp):
        """Aplica només una variable del clip de tempo seleccionat.

        `camp`: `"bpm"`, `"compas"`, `"agr"` o `"n"`. Els altres camps de
        l'Editor s'ignoren totalment; el model aplica les seues regles de N
        enter. Cada clic és una operació d'undo independent.
        """
        k, i = getattr(self, "_ed_kind", None), getattr(self, "_ed_idx", -1)
        if k != "tempo" or not (0 <= i < len(self.tempo_trams or [])):
            self.avis_editor("Selecciona un clip de tempo abans d'aplicar.")
            return False
        tr = self.tempo_trams[i]
        self._undo_marca()
        try:
            if camp == "bpm":
                bpm = self.bpm_entrada(self.ed_nom.text())
                bpm, _num, _den = tempo_map.valida_tempo(
                    bpm, int(tr.num), int(tr.den))
                ok = self._edita_bpm_mobil(i, bpm)
            elif camp == "compas":
                m = re.match(r"^\s*(\d+)\s*[/:]\s*(\d+)\s*$",
                             self.ed_fam.text().strip())
                if not m:
                    raise ValueError("El compàs ha de ser num/den (p. ex. 6/8).")
                num, den = int(m.group(1)), int(m.group(2))
                tempo_map.valida_tempo(float(tr.bpm), num, den)
                ok = self._edita_compas_mobil(i, num, den)
            elif camp == "agr":
                agr = tempo_map.valida_agrupacio(
                    self.ed_agr.text(), int(tr.num), int(tr.den))
                unit_vella = self.unitat_de_tram(tr)
                derivada_vella = bpm_unit_mod.unitat_per_defecte(
                    int(tr.num), int(tr.den),
                    getattr(tr, "agrupacio", ""))
                unit_nova = (bpm_unit_mod.unitat_per_defecte(
                    int(tr.num), int(tr.den), agr)
                    if unit_vella == derivada_vella else unit_vella)
                nous = list(self.tempo_trams)
                nous[i] = mapa_tempo.TramMapa(
                    tr.ini, tr.fi, tr.bpm, tr.tipus, tr.compassos, agr,
                    getattr(tr, "n", None), unit_nova)
                ok = bool(self.aplica_tempo_trams(nous))
            elif camp == "n":
                n = float(self.ed_n.text().strip().replace(",", "."))
                if n <= 0:
                    raise ValueError("N ha de ser positiu.")
                if i != len(self.tempo_trams) - 1 and abs(n - round(n)) > 1e-3:
                    raise ValueError("N ha de ser un enter positiu.")
                ok = self._edita_n_mobil(i, n)
            else:
                return False
        except (TypeError, ValueError, AttributeError) as e:
            self.avis_editor(str(e))
            return False
        finally:
            self._undo_commit()
        self._actualitza_editor()
        return bool(ok)

    def _aplica_editor_tempo(self, i):
        """Aplica BPM/compàs/N exactes i recalcula el veí (recalc mòbil).

        El clip seleccionat rep exactament el que ha escrit l'usuari. El veí
        dret conserva la signatura del veí esquerre si pot i ajusta BPM/N; només
        si no hi ha cap combinació vàlida canvia de signatura. En l'últim/únic
        clip Aplica no està disponible: la fi de la WAV és fixa.
        """
        trams = list(getattr(self, "tempo_trams", None) or [])
        if not (0 <= i < len(trams)):
            self.avis_editor("Aquest clip de tempo ja no existeix.")
            return
        if i == len(trams) - 1:
            self.avis_editor(
                "Aplica no està disponible a l'últim clip: la fi de la WAV "
                "és fixa. Usa «Ajusta» per obrir el diàleg del tram.")
            return
        tr = trams[i]
        try:
            bpm = self.bpm_entrada(self.ed_nom.text())
        except (ValueError, TypeError):
            self.avis_editor(f"El BPM «{self.ed_nom.text()}» no és un número.")
            return
        m = re.match(r"^\s*(\d+)\s*[/:]\s*(\d+)\s*$",
                     self.ed_fam.text().strip())
        if not m:
            self.avis_editor(
                f"El compàs «{self.ed_fam.text()}» no és vàlid (num/den).")
            return
        num, den = int(m.group(1)), int(m.group(2))
        if num <= 0 or den <= 0:
            self.avis_editor(
                "El compàs ha de ser num/den positiu; el rubato és només "
                "un flag i no s'escriu 0/0.")
            return
        try:
            bpm, num, den = tempo_map.valida_tempo(bpm, num, den)
            agr = tempo_map.valida_agrupacio(self.ed_agr.text(), num, den)
        except ValueError as e:
            self.avis_editor(str(e))
            return
        try:
            n_val = float(self.ed_n.text().strip().replace(",", "."))
        except (ValueError, TypeError):
            self.avis_editor(f"El N «{self.ed_n.text()}» no és un número.")
            return
        if n_val <= 0:
            self.avis_editor("N ha de ser positiu.")
            return
        n_actual = getattr(tr, "n", None)
        if n_actual is None:
            try:
                n_actual = tempo_map.compassos_del_clip(tr)
            except (TypeError, ValueError):
                n_actual = 0.0
        canvi_n = abs(n_val - float(n_actual)) > 1e-3
        if (i != len(trams) - 1
                and abs(n_val - round(n_val)) > 1e-3):
            self.avis_editor(
                "N ha de ser un nombre enter de compassos; només l'últim "
                "clip pot quedar amb N fraccionari.")
            return
        canvi_compas = (num, den) != (int(tr.num), int(tr.den))
        canvi_bpm_num = abs(bpm - float(tr.bpm)) > 5e-4
        canvi_bpm = (canvi_bpm_num or canvi_compas)
        # En canviar el compàs, l'agrupació automàtica ha de passar a la del
        # compàs nou, encara que el camp no s'haja tocat.
        if canvi_compas and agr == getattr(tr, "agrupacio", ""):
            agr = tempo_map.agrupacio_a_text(
                tempo_map.agrupacio_compas(num, den))
        canvi_agr = agr != getattr(tr, "agrupacio", "")
        # Cas B: el BPM del camp és el visible en la unitat VELLA. Si el
        # compàs canvia, es deriva la unitat nova i es conserva el número
        # visible; l'intern es recalcula. Així Enter/Aplica i el botó xicot
        # de Compàs fan exactament el mateix.
        unit_vella = self.unitat_de_tram(tr)
        unit_nova = unit_vella
        if canvi_compas:
            bpm_visible = bpm_unit_mod.de_quarter(float(bpm), unit_vella)
            provisional = mapa_tempo.TramMapa(
                float(tr.ini), float(tr.fi), float(tr.bpm), tr.tipus,
                f"{int(num)}/{int(den)}", agr, getattr(tr, "n", None),
                unit_vella)
            unit_nova = self._unitat_en_canvi_compas(tr, provisional, None)
            bpm = bpm_unit_mod.a_quarter(bpm_visible, unit_nova)

        ini_nou = self._cb_a_secs(self.ed_cb.text())
        fi_nou = self._cb_a_secs(self.ed_cb_fi.text())
        if ini_nou is None or fi_nou is None:
            self.avis_editor(
                "El compàs d'inici o de fi no és vàlid (cal compàs.temps).")
            return
        mou_ini = (self.ed_cb.text().strip()
                   != getattr(self, "_ed_cb_ini_text", None))
        mou_fi = (self.ed_cb_fi.text().strip()
                  != getattr(self, "_ed_cb_fi_text", None))
        if (mou_ini or mou_fi) and (canvi_bpm or canvi_n):
            self.avis_editor(
                "No barreges Ini (c)/Fi (c) amb BPM/N en un mateix Aplica: "
                "canvia els camps o mou els compassos, no les dues coses.")
            return
        if mou_ini and i == 0:
            self.avis_editor("L'inici del primer clip és l'inici de la WAV: "
                             "no es pot moure.")
            return
        if mou_fi and i == len(trams) - 1:
            self.avis_editor("La fi de l'últim clip és la fi de la WAV: "
                             "no es pot moure.")
            return
        if not (canvi_bpm or canvi_n or canvi_agr or mou_ini or mou_fi):
            return

        # Un sol camp canviat → recalcula els altres amb el motor guiat
        # (compàs > BPM > N), sense obligar l'usuari a encertar N.
        if (not canvi_agr and not mou_ini and not mou_fi
                and sum((canvi_compas, canvi_bpm_num, canvi_n)) == 1):
            self._undo_marca()
            try:
                if canvi_compas:
                    ok = self._edita_compas_mobil(i, num, den)
                elif canvi_bpm_num:
                    ok = self._edita_bpm_mobil(i, bpm)
                else:
                    ok = self._edita_n_mobil(i, int(round(n_val)))
            finally:
                self._undo_commit()
            self._actualitza_editor()
            return bool(ok)

        # Amb Snap Beats QM, qualsevol edició múltiple ha de quadrar amb els
        # beats detectats; no es pot acceptar un N/BPM incompatible.
        if self._beats_per_validacio():
            try:
                n_qm = self._qm_n_enter(i, num, den)
            except ValueError as e:
                self.avis_editor(str(e))
                return
            if n_qm is not None:
                if int(round(n_val)) != n_qm:
                    self.avis_editor(
                        f"Snap Beats QM: amb {num}/{den} el N ha de ser "
                        f"{n_qm}, no {int(round(n_val))}.")
                    return
                bq = float(num) * 4.0 / float(den)
                bpm_qm = n_qm * bq * 60.0 / (
                    float(tr[1]) - float(tr[0]))
                if canvi_bpm_num and abs(bpm - bpm_qm) > 0.05:
                    self.avis_editor(
                        f"Snap Beats QM: amb {num}/{den} i N={n_qm}, el BPM "
                        f"ha de ser {bpm_qm:.3f}, no {bpm:.3f}.")
                    return

        d = self._durada_wav()
        self._undo_marca()
        try:
            mapa = trams
            if mou_ini:
                mapa = self._mou_frontera_ui(mapa, i, ini_nou, d)
            if mapa is None:
                return
            if mou_fi:
                mapa = self._mou_frontera_ui(mapa, i + 1, fi_nou, d)
            if mapa is None:
                return
            if mapa is not trams:
                mapa = mapa_tempo.reenganxa_metadades(trams, mapa)
            if canvi_bpm or canvi_n:
                bq = tempo_map._bar_quarters(num, den)
                if bq <= 0 or bpm <= 0:
                    self.avis_editor("Tempo: BPM o compàs no vàlids.")
                    return
                dur_sel = float(n_val) * bq * 60.0 / float(bpm)
                fi_sel = float(tr.ini) + dur_sel
                vei = trams[i + 1]
                if fi_sel <= float(tr.ini) + tempo_map.TOL:
                    self.avis_editor("Tempo: el clip seleccionat no té durada.")
                    return
                if fi_sel >= float(vei.fi) - tempo_map.TOL:
                    self.avis_editor(
                        "Tempo: el clip seleccionat no cap abans del veí "
                        "de la dreta.")
                    return
                dur_vei = float(vei.fi) - fi_sel
                if dur_vei <= tempo_map.TOL:
                    self.avis_editor(
                        "Tempo: el veí de la dreta quedaria sense durada.")
                    return
                bpm_vei, num_vei, den_vei = self.referencia_tempo_base(i)
                recalc = tempo_recalc.recalculca_vei_ref(
                    dur_vei, bpm_vei, num_vei, den_vei)
                if recalc is None:
                    self.avis_editor(
                        "Tempo: el veí de la dreta no cap amb cap combinació "
                        "vàlida a partir del veí esquerre.")
                    return
                nous = list(mapa)
                nous[i] = mapa_tempo.TramMapa(
                    float(tr.ini), fi_sel, float(bpm), tr.tipus,
                    f"{int(num)}/{int(den)}", agr, float(n_val),
                    unit_nova)
                agr_vei = (
                    vei.agrupacio
                    if (int(recalc["num"]), int(recalc["den"]))
                    == (int(vei.num), int(vei.den)) else "")
                nous[i + 1] = mapa_tempo.TramMapa(
                    fi_sel, float(vei.fi), float(recalc["bpm"]), vei.tipus,
                    f"{int(recalc['num'])}/{int(recalc['den'])}",
                    agr_vei, float(recalc["n"]), vei.beat_unit)
                mapa = nous
            if canvi_agr:
                mapa = list(mapa)
                tr2 = mapa[i]
                mapa[i] = mapa_tempo.TramMapa(
                    tr2.ini, tr2.fi, tr2.bpm, tr2.tipus, tr2.compassos,
                    agr, getattr(tr2, "n", None), tr2.beat_unit)
            if not self._valida_unitat_tram(mapa[i], "Editor"):
                return
            self.aplica_tempo_trams(mapa)
        finally:
            self._undo_commit()
        self._actualitza_editor()

    def _aplica_editor(self):
        """Aplica els canvis de la franja Editor al model (amb undo).

        Tots els camins que NO apliquen donen feedback visible (`avis_editor`):
        un botó que no fa res i no diu per què és un defecte.
        """
        k, i = getattr(self, "_ed_kind", None), getattr(self, "_ed_idx", -1)
        if k is None or i < 0:
            self.avis_editor("Selecciona un acord, una secció o un clip de "
                             "tempo (clic al clip) abans d'aplicar.")
            return
        if k == "tempo":
            self._aplica_editor_tempo(i)
            return
        # Multi-selecció del MATEIX tipus → renom EN BLOC (estil fulla de càlcul):
        # el camp Nom s'aplica a TOTS els seleccionats del tipus actiu. L'INICI
        # NO s'aplica en bloc (no s'han d'apilar tots els clips al mateix instant).
        _n = len(self.acords) if k == "chord" else len(self.seccions)
        idxs = sorted({j for (kk, j) in self.timeline.selected_keys()
                       if kk == k and 0 <= j < _n})
        if len(idxs) >= 2:
            nom = self.ed_nom.text().strip()
            if k == "chord":
                if not self._renomena_acords(idxs, nom):
                    self.avis_editor("Renom en bloc: nom o canvi no vàlid.")
            else:
                if not self._renomena_seccions(idxs, nom or self.seccions[i][2]):
                    self.avis_editor("Renom en bloc: lletra o canvi no vàlid.")
            return
        # inici: prioritza el camp de segons; si esta buit, el de compas.beat
        txt = self.ed_ini.text().strip()
        if txt:
            try:
                ini = float(txt.replace(",", "."))
            except ValueError:
                self.avis_editor(f"L'inici «{txt}» no és un número vàlid.")
                return
        else:
            ini = self._cb_a_secs(self.ed_cb.text())
            if ini is None:
                self.avis_editor(f"El compàs «{self.ed_cb.text()}» no és vàlid.")
                return
        nom = self.ed_nom.text().strip()
        if k == "chord":
            if not nom or not (0 <= i < len(self.acords)):
                self.avis_editor("Cal un nom, i l'acord ha d'existir (potser "
                                 "l'has esborrat).")
                return
            # Mateix sanejat que l'alta i l'export (coherència nom CSV ↔ WAV).
            nom = pipeline.saneja_nom_acord(nom)
            if not nom:
                self.avis_editor("El nom de l'acord no és vàlid.")
                return
            # Si l'inici NO s'ha tocat, conserva el valor INTERN de precisió
            # completa: l'editor només en mostra 2 decimals i re-escriure'l
            # arrodonit podria fer que l'acord "xoqui" amb el veí.
            if abs(ini - float(self.acords[i][0])) <= 0.005:
                ini = float(self.acords[i][0])
            self._undo_marca()
            nova = list(self.acords)
            _a = nova[i]
            nova[i] = pipeline.Clip(ini, float(_a[1]),
                                    (nom,) + tuple(_a[2][1:]))
            try:
                self.acords = self._normalitza_acords(nova)
            except ValueError as e:
                self.avis_editor(f"canvi invalid ({e})")
                return
            finally:
                self._undo_commit()
            self.timeline.set_data(self.acords, self.seccions)
            self._desa_i_regenera()
            self.log(f"editor: acord {i} -> {nom} @ {ini:.3f}s")
            # Si s'ha mogut l'inici, l'acord pot haver canviat de fila → re-localitza.
            i = next((j for j, a in enumerate(self.acords)
                      if abs(float(a[0]) - ini) <= 1e-6
                      and nom_acord(a) == nom), i)
        else:
            if not (0 <= i < len(self.seccions)):
                self.avis_editor("Aquesta secció ja no existeix (potser l'has "
                                 "esborrada).")
                return
            _ini, fi, _ll, _f = self.seccions[i]
            # (mateix motiu que als acords) si l'inici no s'ha tocat, conserva
            # la precisió completa -> evita falsos solapaments amb la secció
            # anterior, que acaba EXACTAMENT aquí.
            if abs(ini - _ini) <= 0.005:
                ini = _ini
            lletra = nom or self.seccions[i][2]
            fam = self.ed_fam.text().strip() or self.seccions[i][3]
            self._undo_marca()
            nova = list(self.seccions)
            nova[i] = (ini, max(ini + self.MIN_SECCIO_S, fi), lletra, fam)
            try:
                # Manté la contigüitat (#2) com el drag del timeline.
                nova = self._contiguitat_seccions(nova, i)
                self.seccions = self._normalitza_seccions(nova)
            except ValueError as e:
                self.avis_editor(f"canvi invalid ({e})")
                return
            finally:
                self._undo_commit()
            self.timeline.set_data(self.acords, self.seccions)
            self._regenera_abc_des_de_totes_les_seccions("editat des de l'editor")
            self.log(f"editor: seccio {i} -> {lletra} @ {ini:.3f}s")
            i = next((j for j, s in enumerate(self.seccions)
                      if abs(float(s[0]) - ini) <= 1e-6 and s[2] == lletra), i)
        self._refresca_post_edicio(k, i)

    def posa_nom_editor(self, nom):
        """Posa `nom` a la casella «Nom» de la franja Editor (**sense aplicar**).

        El fa servir el panell «Tipus d'acord»: clicar un tipus només **omple**
        la casella; l'usuari decideix quan prem «Aplica» (o Enter).
        """
        self.ed_nom.setText(str(nom or ""))
        self.ed_nom.setFocus()
        self.ed_nom.selectAll()
        self.avis_editor(f"tipus d'acord: «{nom}» llest per aplicar")

    def _focus_editor(self, kind, idx):
        """Selecciona l'element i enganxa el focus a la franja Editor
        (en comptes d'obrir cap finestra emergent)."""
        self._ed_kind, self._ed_idx = kind, idx
        self.timeline.select_clip(kind, idx)
        if kind == "chord":
            self._centra_fila_llista(self.llista_ac, idx)
        elif kind == "section":
            self._centra_fila_llista(self.llista_ab, idx)
        elif kind == "tempo":
            self._centra_fila_llista(self.llista_tempo, idx)
        self._actualitza_editor()
        self.ed_nom.setFocus()
        self.ed_nom.selectAll()
