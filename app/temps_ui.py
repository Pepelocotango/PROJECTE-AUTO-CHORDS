"""UI de temps de la finestra (F3): BPM i compàs.

Extret de `app/main.py`. `TempsMixin` treballa amb els widgets de la barra i
delega la validació a `tempo_map`/`limits`.
"""
from . import limits, tempo_map


def _beat_seconds(bpm, den):
    """Durada en segons d'un temps del denominador `den`."""
    return (4.0 / max(1, int(den))) * 60.0 / max(float(bpm), 1e-9)


def cb_a_secs(text, bpm, num, den):
    """`C.B[.S]` → segons, amb el denominador del compàs."""
    import re
    m = re.match(r"\s*(-?\d+)\s*[.,]\s*(\d+)"
                 r"(?:\s*[.,]\s*(\d+))?\s*$", str(text))
    if not m:
        return None
    c, b = int(m.group(1)), int(m.group(2))
    sub = int(m.group(3)) if m.group(3) else 1
    sub = max(1, min(8, sub))
    n = ((c - 1) * max(1, int(num)) + (b - 1) + (sub - 1) / 8.0)
    return max(0.0, n * _beat_seconds(bpm, den))


def secs_a_cb(t, bpm, num, den):
    """Segons → `C.B[.S]`, amb el denominador del compàs."""
    beat_len = _beat_seconds(bpm, den)
    num = max(1, int(num))
    p = int(round(max(0.0, float(t)) / beat_len * 8))
    SB = num * 8
    c = p // SB + 1
    dins = p % SB
    b = dins // 8 + 1
    sub = dins % 8 + 1
    return f"{c}.{b}" if sub == 1 else f"{c}.{b}.{sub}"

class TempsMixin:
    """Camps de BPM/compàs i aplicació al visor."""

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

    def _posa_bpm_quarter(self, bpm_quarter, decimals=3):
        """Escriu al camp de BPM un valor intern en negres/minut."""
        self.bpm.setText(f"{float(bpm_quarter):.{int(decimals)}f}")

    def _bpm_val(self):
        raw = str(self.bpm.text()).replace(",", ".").strip()
        try:
            return tempo_map.valida_tempo(float(raw), 4, 4)[0]
        except (ValueError, TypeError) as e:
            raise ValueError(f"Tempo: {e}") from e

    def _bpb_val(self):
        num, den = self._parse_compas(self.bpb.text())
        return tempo_map.valida_tempo(self._bpm_val(), num, den)[1]

    def _beat_type_val(self):
        num, den = self._parse_compas(self.bpb.text())
        return tempo_map.valida_tempo(self._bpm_val(), num, den)[2]

    def _cb_a_secs(self, text):
        """'C.B' o 'C.B.S' (compàs.beat.fusa) -> segons."""
        return cb_a_secs(text, self._bpm_val(), self._bpb_val(),
                         self._beat_type_val())

    def _secs_a_cb(self, t):
        """Segons -> 'C.B' o 'C.B.S' (fusa) a la graella ORIGINAL."""
        return secs_a_cb(t, self._bpm_val(), self._bpb_val(),
                         self._beat_type_val())

    def _canvia_mode_temps(self, bpm_compas):
        """Canvia entre mode BPM·compàs i mode Lliure (hh:mm:ss)."""
        self._params_temps.setVisible(bool(bpm_compas))
        if hasattr(self, "barra_temps"):
            self.barra_temps.setVisible(bool(bpm_compas))
        self.tempo_fix.setChecked(bool(bpm_compas))
        self._actualitza_metro_ui()

    def _aplica_parametres_temps(self):
        """Aplica BPM/compàs al VISOR, al clip de tempo objectiu.

        Decisió 2B (2026-10-19): si hi ha un tram de tempo seleccionat, els
        camps de dalt editen **eixe tram**; si no, el transport (tram 0).
        No es reinicia l'àudio: el fil d'alimentació llig el BPM/mapa a cada
        tros.
        """
        if getattr(self, "_actualitzant_temps", False):
            return
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return
        idx = vr.tempo_objectiu()
        # Escriure 0 BPM no és vàlid. El rubato es crea amb les accions del
        # menú del clip, no des d'esta barra.
        raw = str(self.bpm.text()).replace(",", ".").strip()
        try:
            zero = abs(float(raw)) <= 1e-9
        except ValueError:
            zero = False
        if zero:
            self.avisa_info(
                "Auto Chords",
                "Un BPM de 0 no és vàlid. Per a un passatge rubato, usa el "
                "menú del clip de tempo.")
            self._sincronitza_temps_del_visor()
            return
        try:
            bpm = self._bpm_val()
            num, den = self._parse_compas(self.bpb.text())
            bpm, num, den = tempo_map.valida_tempo(bpm, num, den)
        except ValueError as e:
            self.avisa_info("Tempo o compàs invàlid", str(e))
            self._sincronitza_temps_del_visor()
            return
        try:
            _idx, _bpm, _num, _den = vr.tempo_objectiu_vals()
        except Exception:  # noqa: BLE001
            _bpm, _num, _den = vr.bpm, vr.bpb, getattr(vr, "beat_type", 4)
        if (abs(bpm - float(_bpm)) <= 1e-9 and num == int(_num)
                and den == int(_den)):
            return
        vr._undo_marca()
        ok = vr.edita_tempo_objectiu(idx, bpm, num, den)
        vr._undo_commit()
        if ok:
            self.registra(f"tempo: tram {idx} → {bpm:.3f} BPM · "
                          f"{num}/{den}")
        self._sincronitza_temps_del_visor()

    def _canvia_tempo(self, fix):
        """Commuta BPM·compàs ↔ Lliure i refresca el visor.

        ⚠️ Aci NO es torna a cridar `timeline.set_tempo_mode(...)`: eixa crida
        era anterior al **mapa de tempo variable** i, sense el paràmetre
        `mapa=`, deixava el timeline amb `_mapa = None`. Això apagava la pista
        de BPM/compàs (`TempoLayer._visible()`) i la graella/regle tornaven a
        la graella constant. `_actualitza_temps()` ja fa la crida correcta
        (amb `mapa=self.tempo_map`). (reportat per l'operador,
        19-10-2026: «canvio a hh:mm:ss i torne a BPM i ja no hi ha carril»).
        """
        for w in (self.bpm, self.bpb):
            w.setEnabled(fix)
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            # Els camps poden estar mostrant un tram interior (2B): el canvi
            # de MODE no ha de copiar-los al transport.
            vr.tempo_fix = bool(fix)
            vr._actualitza_temps()
            self._sincronitza_temps_del_visor()
