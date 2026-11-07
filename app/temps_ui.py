"""UI de temps de la finestra (F3): BPM, compàs i offset.

Extret de `app/main.py`. `TempsMixin` treballa amb els widgets de la barra i
delega la validació a `tempo_map`/`limits`/`bpm_unit`.
"""
from . import bpm_unit as bpm_unit_mod, limits, tempo_map

class TempsMixin:
    """Camps de BPM/compàs/offset i aplicació al visor."""

    @staticmethod
    def _parse_compas(text, defecte_num=4, defecte_den=4):
        """Accepta «4», «4/4», «3/4», «2/4», «1/4», «6/8»; `0/0` és rubato."""
        s = str(text).replace(" ", "").strip()
        if not s:
            raise ValueError("El compàs no pot estar buit")
        if "/" in s:
            parts = s.split("/", 1)
            if len(parts) != 2 or not all(p.isdigit() for p in parts):
                raise ValueError(f"El compàs «{text}» no és vàlid")
            numer, den = int(parts[0]), int(parts[1])
        elif s.isdigit():
            numer, den = int(s), int(defecte_den)
        else:
            raise ValueError(f"El compàs «{text}» no és vàlid")
        _, numer, den = tempo_map.valida_tempo(
            limits.BPM_MIN, numer, den)
        return numer, den

    @staticmethod
    def _llegeix_num(w, defecte, minim, maxim, enter=False):
        try:
            v = float(str(w.text()).replace(",", ".").strip())
        except (ValueError, AttributeError):
            return defecte
        v = max(minim, min(maxim, v))
        return int(round(v)) if enter else v

    def _bpm_unit_val(self):
        """Clau de la unitat de BPM triada a la barra (sempre vàlida)."""
        cb = getattr(self, "cb_bpm_unit", None)
        return bpm_unit_mod.normalitza(cb.currentData() if cb else None)

    def _posa_bpm_quarter(self, bpm_quarter, decimals=3):
        """Escriu al camp de BPM un valor INTERN (negres/min) en la unitat triada."""
        self.bpm.setText(bpm_unit_mod.formata(
            float(bpm_quarter), self._bpm_unit_val(), decimals))

    def _posa_ref_recalc(self, bpm_quarter, compas=None, den=None):
        """Escriu la referència manual de recalcul (BPM en la unitat activa).

        Accepta `(bpm, "4/4")` o `(bpm, num, den)`.
        """
        bpm = float(bpm_quarter)
        if den is not None:
            compas = f"{int(compas)}/{int(den)}"
        text = self.ref_bpb.text() if compas is None else str(compas)
        num, den = self._parse_compas(text)
        self.ref_bpm.setText(
            bpm_unit_mod.formata(bpm, self._bpm_unit_val()))
        self.ref_bpb.setText(f"{num}/{den}")

    def _ref_bpm_val(self):
        raw = str(self.ref_bpm.text()).replace(",", ".").strip()
        try:
            quarter = bpm_unit_mod.a_quarter(float(raw), self._bpm_unit_val())
            return tempo_map.valida_tempo(quarter, 4, 4)[0]
        except (ValueError, TypeError) as e:
            raise ValueError(f"Referència: {e}") from e

    def _ref_vals(self):
        """Referència manual validada: `(bpm_quarter, num, den)`."""
        bpm = self._ref_bpm_val()
        num, den = self._parse_compas(self.ref_bpb.text())
        bpm, num, den = tempo_map.valida_tempo(bpm, num, den)
        return float(bpm), int(num), int(den)

    def _sincronitza_ref_des_del_visor(self):
        """Copia la referència efectiva del visor als camps de la barra 2."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return
        self._actualitzant_temps = True
        try:
            self._posa_ref_recalc(*vr.ref_tempo_base())
        finally:
            self._actualitzant_temps = False
        self._ref_manual = True

    def _aplica_ref_recalc(self):
        """Aplica la referència manual de recalcul (només recalcul, no clips)."""
        if getattr(self, "_actualitzant_temps", False):
            return
        try:
            bpm, num, den = self._ref_vals()
        except ValueError as e:
            self.avis_info("Referència de recalcul invàlida", str(e))
            self._sincronitza_ref_des_del_visor()
            return
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            vr.set_ref_tempo(bpm, num, den)
        else:
            self._posa_ref_recalc(bpm, f"{num}/{den}")
        self._ref_manual = True
        self._marca_dirty()
        self.registra(f"Referència recalc: {bpm:g} BPM · {num}/{den}")

    def _canvia_unitat_bpm(self, _idx=None):
        """Canvia la unitat mostrada sense tocar el valor intern del tempo."""
        vr = getattr(self, "visor_ref", None)
        unit = self._bpm_unit_val()
        old_unit = getattr(self, "_bpm_unit_anterior", "negra")
        if vr is not None:
            vr.set_bpm_unit(unit)
            try:
                _idx, q, _num, _den = vr.tempo_objectiu_vals()
            except Exception:  # noqa: BLE001
                q = float(getattr(vr, "bpm", 120.0))
        else:
            try:
                q = bpm_unit_mod.a_quarter(
                    float(self.bpm.text().replace(",", ".").strip()),
                    getattr(self, "_bpm_unit_anterior", "negra"))
            except ValueError:
                q = 120.0
        self._bpm_unit_anterior = unit
        # El camp ha de mostrar el mateix valor intern amb la unitat nova.
        self._actualitzant_temps = True
        try:
            self._posa_bpm_quarter(q)
        finally:
            self._actualitzant_temps = False
        # La referència també es mostra en la unitat nova, però conserva el
        # valor intern en negres/min.
        if hasattr(self, "ref_bpm"):
            ref_q = None
            if vr is not None:
                ref_q = float(vr.ref_tempo_base()[0])
            else:
                try:
                    ref_q = bpm_unit_mod.a_quarter(
                        float(str(self.ref_bpm.text()).replace(",", ".")),
                        old_unit)
                except (TypeError, ValueError):
                    ref_q = None
            if ref_q is not None:
                self._actualitzant_temps = True
                try:
                    self.ref_bpm.setText(
                        bpm_unit_mod.formata(ref_q, unit))
                finally:
                    self._actualitzant_temps = False
        self._marca_dirty()

    def _bpm_val(self):
        raw = str(self.bpm.text()).replace(",", ".").strip()
        try:
            quarter = bpm_unit_mod.a_quarter(float(raw), self._bpm_unit_val())
            return tempo_map.valida_tempo(quarter, 4, 4)[0]
        except (ValueError, TypeError) as e:
            raise ValueError(f"Tempo: {e}") from e

    def _bpb_val(self):
        num, den = self._parse_compas(self.bpb.text())
        return tempo_map.valida_tempo(self._bpm_val(), num, den)[1]

    def _beat_type_val(self):
        num, den = self._parse_compas(self.bpb.text())
        return tempo_map.valida_tempo(self._bpm_val(), num, den)[2]

    def _posa_offset_camp(self, valor):
        """Escriu l'offset amb 3 decimals, però conserva el valor exacte.

        També s'usa en carregar un projecte: el text de la GUI no pot ser la
        font de veritat de l'offset (1.207438 es veu com 1.207).
        """
        exact = float(valor)
        text = f"{exact:.3f}"
        self.offset.setText(text)
        self._offset_ui_text = text
        self._offset_ui_exact = exact

    def _offset_val(self):
        """Offset en segons sense perdre la precisió que no cap a la GUI.

        El camp mostra 3 decimals (`1.207`), però el model pot tindre
        `1.207438`. Si l'usuari no ha tocat el text que va pintar
        `_sincronitza_temps_del_visor`, es recupera el valor intern exacte.
        """
        text = str(self.offset.text()).strip()
        exact = getattr(self, "_offset_ui_exact", None)
        if (exact is not None
                and getattr(self, "_offset_ui_text", None) == text):
            return float(exact)
        return self._llegeix_num(self.offset, 0.0, 0.0, 60.0)

    def _cb_a_secs(self, text):
        """'C.B' o 'C.B.S' (compàs.beat.fusa) -> segons (offset=0)."""
        import re
        m = re.match(r"\s*(-?\d+)\s*[.,]\s*(\d+)"
                     r"(?:\s*[.,]\s*(\d+))?\s*$", str(text))
        if not m:
            return None
        c, b = int(m.group(1)), int(m.group(2))
        sub = int(m.group(3)) if m.group(3) else 1
        sub = max(1, min(8, sub))
        beat_len = 60.0 / max(self._bpm_val(), 1e-9)
        n = ((c - 1) * max(1, self._bpb_val()) + (b - 1)
             + (sub - 1) / 8.0)
        return max(0.0, min(60.0, n * beat_len))

    def _secs_a_cb(self, t):
        """Segons -> 'C.B' o 'C.B.S' (fusa) a la graella ORIGINAL."""
        beat_len = 60.0 / max(self._bpm_val(), 1e-9)
        bpb = max(1, self._bpb_val())
        p = int(round(float(t) / beat_len * 8))
        SB = bpb * 8
        c = p // SB + 1
        dins = p % SB
        b = dins // 8 + 1
        sub = dins % 8 + 1
        return f"{c}.{b}" if sub == 1 else f"{c}.{b}.{sub}"

    def _offset_cb_canviat(self):
        """L'usuari ha escrit el camp compàs.beat -> passa-ho a segons."""
        s = self._cb_a_secs(self.offset_cb.text())
        if s is None:
            return
        self._posa_offset_camp(s)
        self._aplica_parametres_temps()

    def _canvia_mode_temps(self, bpm_compas):
        """Canvia entre mode BPM·compàs i mode Lliure (hh:mm:ss)."""
        self._params_temps.setVisible(bool(bpm_compas))
        if hasattr(self, "barra_temps"):
            self.barra_temps.setVisible(bool(bpm_compas))
        self.tempo_fix.setChecked(bool(bpm_compas))
        self._actualitza_metro_ui()

    def _aplica_parametres_temps(self):
        """Aplica BPM/compàs/offset al VISOR, al clip de tempo objectiu.

        Decisió 2B (2026-10-19): si hi ha un tram de tempo seleccionat, els
        camps de dalt editen **eixe tram**; si no, el transport (tram 0).
        L'offset continua sent global. No es reinicia l'àudio: el fil
        d'alimentació llig el BPM/mapa a cada tros.
        """
        if getattr(self, "_actualitzant_temps", False):
            return
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return
        idx = vr.tempo_objectiu()
        free = bool(getattr(self, "chk_segons", None)
                    and self.chk_segons.isChecked())
        if free:
            self._missatge_info(
                "El rubato es crea amb «Marca com a rubato» o «Converteix a "
                "rubato», no amb el commutador «En segons».")
            self.chk_segons.setChecked(False)
            self._sincronitza_temps_del_visor()
            return
        if not free:
            # Escriure 0 BPM NO s'ha de convertir en 30 en silenci: és el gest
            # natural per demanar un clip en segons.
            raw = str(self.bpm.text()).replace(",", ".").strip()
            try:
                zero = abs(float(raw)) <= 1e-9
            except ValueError:
                zero = False
            if zero:
                self.avis_info(
                    "Auto Chords",
                    "Un BPM de 0 no és vàlid. Per a un passatge rubato, marca "
                    "«En segons» al costat del compàs.")
                self._sincronitza_temps_del_visor()
                return
        try:
            bpm = self._bpm_val()
            if free:
                bpm, num, den = tempo_map.valida_tempo(bpm, 0, 0)
            else:
                num, den = self._parse_compas(self.bpb.text())
                bpm, num, den = tempo_map.valida_tempo(bpm, num, den)
        except ValueError as e:
            self.avisa_info("Tempo o compàs invàlid", str(e))
            self._sincronitza_temps_del_visor()
            return
        offset = self._offset_val()
        try:
            _idx, _bpm, _num, _den = vr.tempo_objectiu_vals()
        except Exception:  # noqa: BLE001
            _bpm, _num, _den = vr.bpm, vr.bpb, getattr(vr, "beat_type", 4)
        if (abs(bpm - float(_bpm)) <= 1e-9 and num == int(_num)
                and den == int(_den)
                and abs(offset - float(getattr(vr, "offset", 0.0))) <= 1e-9):
            return
        vr._undo_marca()
        vr.offset = offset
        ok = vr.edita_tempo_objectiu(idx, bpm, num, den)
        vr._undo_commit()
        self.offset_cb.setText(self._secs_a_cb(offset))
        if ok:
            self.registra(f"tempo: tram {idx} → {bpm:.3f} BPM · "
                          f"{num}/{den} (offset {offset:.3f}s)")
        self._sincronitza_temps_del_visor()

    def _segons_top_bar(self, actiu):
        """Casella «En segons»: a 3.1 es rebutja; el rubato és de 3.2."""
        if getattr(self, "_actualitzant_temps", False):
            return
        if not actiu and self.bpb.text().strip() in ("0/0", "0", ""):
            self.bpb.setText("4/4")     # tornar a compàs: un valor real
        self._aplica_parametres_temps()

    def _canvia_tempo(self, fix):
        """Commuta BPM·compàs ↔ Lliure i refresca el visor.

        ⚠️ Aci NO es torna a cridar `timeline.set_tempo_mode(...)`: eixa crida
        era anterior al **mapa de tempo variable** i, sense el paràmetre
        `mapa=`, deixava el timeline amb `_mapa = None`. Això apagava la pista
        de BPM/compàs (`TempoLayer._visible()`) i la graella/regle tornaven a
        la graella constant. `_actualitza_temps()` ja fa la crida correcta
        (amb `mapa=self.tempo_map`); ací només cal deixar-hi l'offset al dia,
        que és el que `_actualitza_temps()` hi llig. (reportat per l'operador,
        19-10-2026: «canvio a hh:mm:ss i torne a BPM i ja no hi ha carril»).
        """
        for w in (self.bpm, self.cb_bpm_unit, self.bpb, self.offset):
            w.setEnabled(fix)
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            # Els camps poden estar mostrant un tram interior (2B): el canvi de
            # MODE no ha de copiar-los al transport. L'offset, però, és global
            # i el camp n'és la font (el test de commutació ho exigeix).
            vr.offset = self._offset_val()
            vr.tempo_fix = bool(fix)
            vr._actualitza_temps()
            self._sincronitza_temps_del_visor()
