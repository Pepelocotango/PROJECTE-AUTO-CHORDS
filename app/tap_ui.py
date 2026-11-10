"""Tap tempo de la finestra (F3).

Extret de `app/main.py`: sessió de taps, mediana robusta i aplicació al clip
de tempo seleccionat.
"""
import statistics
import time

from . import bpm_unit as bpm_unit_mod, limits

class TapMixin:
    """Tap tempo robust."""

    def _tanca_sessio_tap(self):
        """Tanca la sessió de taps: desa el canvi i apila UN sol undo.

        La sessió s'obri al primer toc (o quan canvia el clip objectiu) i es
        tanca al cap de 2 s sense tocar, en canviar de clip o en aturar el
        transport. Així `Ctrl+Z` desfà tota la mesura de cop.
        """
        if not getattr(self, "_tap_sessio_oberta", False):
            return
        self._tap_sessio_oberta = False
        try:
            self._tap_timer.stop()
        except (AttributeError, RuntimeError):
            pass
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            try:
                if getattr(self, "_tap_canviat", False):
                    vr._desa_i_regenera()
                vr._undo_commit()
            except Exception as e:  # noqa: BLE001
                self.registra(f"tap tempo: no s'ha pogut tancar la sessió ({e})")
            finally:
                vr._tap_en_curs = False
            self._sincronitza_temps_del_visor()
        self._tap_canviat = False

    def _tap_tempo(self):
        """Tap tempo (com als DAWs): intervals dels últims taps → BPM.

        El destí és el **clip de tempo seleccionat**; sense un tram de
        BPM/compàs seleccionat, T no fa res. Una sessió de taps = una sola
        operació de desfer.
        """
        self._actualitza_desti_accions()
        ara = time.monotonic()
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return
        kind, idx = vr.seleccio_activa()
        if kind != "tempo" or not vr._index_valid("tempo", idx):
            # T només actua amb un clip de BPM/compàs seleccionat.
            return
        idx = int(idx)
        # Canvi de clip objectiu o pausa > 2 s → tanca la sessió anterior.
        if self._taps and (self._tap_target != idx):
            self._tanca_sessio_tap()
            self._taps = []
        if self._taps and (ara - self._taps[-1]) > 2.0:
            self._tanca_sessio_tap()
            self._taps = []
        if vr is not None and not self._tap_sessio_oberta:
            self._tap_sessio_oberta = True
            self._tap_canviat = False
            vr._tap_en_curs = True
            vr._undo_marca()
            # Decisió 3: si està SONANT, el tap tanca el loop al clip de tempo
            # seleccionat.
            if getattr(vr, "sona", False):
                trams = list(vr.tempo_trams or [])
                if 0 <= idx < len(trams):
                    a, b = float(trams[idx][0]), float(trams[idx][1])
                    if b > a:
                        vr._fixa_loop(a, b, activa=True, alinea=True)
                        self._tap_canviat = True
        self._tap_target = idx
        self._taps.append(ara)
        if len(self._taps) > 8:
            self._taps = self._taps[-8:]         # finestra dels últims 8
        if len(self._taps) < 2:
            self.b_tap.setText("TAP (1)")
            self._tap_timer.start()
            return
        ivs = [b - a for a, b in zip(self._taps, self._taps[1:])]
        ivs = [x for x in ivs if 60.0 / limits.BPM_MAX <= x <= 2.0]
        if not ivs:
            self.b_tap.setText(f"TAP ({len(self._taps)})")
            self._tap_timer.start()
            return
        # TAP robust (Fase 3): mediana + descart d'intervals clarament anòmals.
        mediana = statistics.median(ivs)
        ivs_robustos = [x for x in ivs
                        if mediana * 0.7 <= x <= mediana * 1.3]
        if not ivs_robustos:
            ivs_robustos = [mediana]
        taps_bpm = 60.0 / statistics.median(ivs_robustos)
        factor = float(vr.beat_factor()) if vr is not None else 1.0
        bpm = taps_bpm * factor
        if vr is not None:
            _, _bpm, num, den = vr.tempo_objectiu_vals()
            if vr.edita_tempo_objectiu(idx, bpm, num, den, desa=False):
                self._tap_canviat = True
            self._sincronitza_temps_del_visor()
        else:
            self._posa_bpm_quarter(bpm)
        unit = getattr(vr, "bpm_unit", "negra") if vr is not None else "negra"
        self.b_tap.setText(
            f"TAP ({len(self._taps)}) {bpm_unit_mod.de_quarter(bpm, unit):.0f}")
        self.registra(f"tap tempo: {taps_bpm:.3f} taps/min · "
                      f"{factor:g} negres/beat → {bpm:.3f} BPM · tram {idx} "
                      f"({len(self._taps)} taps)")
        self._tap_timer.start()
        self._actualitza_desti_accions()
