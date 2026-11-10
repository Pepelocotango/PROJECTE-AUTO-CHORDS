"""Transport, loop, zoom, velocitat i metrònom del visor (F4).

Extret de `app/visor.py`. `TransportMixin` treballa amb l'estat de `Visor` i
els widgets del transport.
"""
import time

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QComboBox, QMessageBox

from . import bpm_unit as bpm_unit_mod, limits, metronom

class TransportMixin:
    """Loop, zoom, velocitat i metrònom."""

    def _fixa_loop(self, a, b, activa=True, alinea=True):
        """Fixa el loop A/B **sense** tocar l'undo (el caller el gestiona).

        Pensat per al tap tempo automàtic i per a «Loop a la selecció»: el
        canvi de loop forma part de la mateixa operació que l'edició. Si està
        sonant i el cursor queda fora, l'alinea a l'inici (so i cursor quadren).
        """
        self.loop_a = None if a is None else float(a)
        self.loop_b = None if b is None else float(b)
        self.loop_on = bool(
            activa and self.loop_a is not None and self.loop_b is not None
            and self.loop_b > self.loop_a)
        if hasattr(self, "b_loop"):
            self.b_loop.setChecked(self.loop_on)
        self.loopStateChanged.emit(self.loop_on)
        self._pinta_loop()
        if self.loop_on and alinea and getattr(self, "sona", False):
            self._alinea_cursor_loop(self.pos)
        self.log(f"loop {'ON' if self.loop_on else 'OFF'}"
                 + (f" A={self.loop_a:.3f}s B={self.loop_b:.3f}s"
                    if self.loop_on else ""))
        return self.loop_on

    def loop_a_la_seleccio(self, kind=None, idx=None):
        """Posa el loop A/B a la **unió** de la selecció (3 carrils).

        Un sol clip → les seues fronteres. Diversos (o selecció mixta) → del
        mínim inici al màxim final. Sense selecció, si el menú contextual ha
        apuntat un clip vàlid, s'usa eixe. És una sola operació d'undo i, si
        està sonant, alinea el cursor a l'inici del loop.
        """
        keys = self.clips_seleccionats()
        if not keys and kind in self._KINDS_EDICIO and idx is not None:
            i = int(idx)
            if self._index_valid(kind, i):
                keys = {(kind, i)}
        if not keys:
            self.avis_editor(
                "Loop a la selecció: no hi ha cap clip seleccionat.")
            return False
        inis, fis = [], []
        for k, i in keys:
            if k == "chord":
                c = self.acords[i]
                inis.append(float(c.ini))
                fis.append(float(c.fi))
            elif k == "section":
                s = self.seccions[i]
                inis.append(float(s[0]))
                fis.append(float(s[1]))
            elif k == "tempo":
                tr = (self.tempo_trams or [])[i]
                inis.append(float(tr[0]))
                fis.append(float(tr[1]))
        if not inis:
            return False
        a, b = min(inis), max(fis)
        if b <= a:
            return False
        self._undo_marca()
        self._fixa_loop(a, b, activa=True, alinea=True)
        self._undo_commit()
        self.avis_editor(f"Loop a la selecció: {a:.3f}–{b:.3f}s "
                         f"({len(keys)} clip(s))")
        return True

    def set_loop(self, on):
        """Fixa l'estat del loop A-B (les barres de fora NO toquen b_loop)."""
        self._undo_marca()          # A1: el loop també és desfer/fer
        self.loop_on = bool(on)
        if self.loop_on and (self.loop_a is None or self.loop_b is None
                             or self.loop_b <= self.loop_a):
            self.log("loop: cal marcar A i B (B > A) primer")
            self.loop_on = False
        if hasattr(self, "b_loop") and self.b_loop.isChecked() != self.loop_on:
            self.b_loop.setChecked(self.loop_on)
        if self.loop_on and getattr(self, "sona", False):
            # Activar el loop MENTRES sona: el só hi salta tot sol (el feeder
            # llegeix `loop_on` en viu) → el cursor s'hi ha de posar també, o
            # queden desalineats («el que sona no és on el cursor és»).
            self._alinea_cursor_loop(self.pos)
        # Sincronitza el botó 🔁 de fora amb l'estat REAL (pot haver-se revertit
        # a OFF si faltaven A i B).
        self.loopStateChanged.emit(self.loop_on)
        self.log(f"loop {'ON' if self.loop_on else 'OFF'}")
        self._pinta_loop()
        self._undo_commit()

    def commuta_loop(self):
        self.set_loop(not self.loop_on)

    def _alinea_cursor_loop(self, t):
        """Alinea el CURSOR amb el só quan hi ha loop A/B actiu.

        `_alimenta` fa el salt pel seu compte («si el punt de generació queda
        fora del bucle, arrenca a `loop_a`»); aquest mètode fa el MATEIX amb la
        visualització: si `t` és FORA de `[loop_a, loop_b)`, el retorna muntat a
        `loop_a` i hi mou el cursor a l'instant (posició + timeline + lliscador +
        etiqueta de temps). Si el transport sona, re-ancora el rellotge perquè
        la visualització no derivi respecte al só. Retorna el `t` efectiu.
        """
        if (self.loop_on and self.loop_a is not None
                and self.loop_b is not None and self.loop_b > self.loop_a
                and not (self.loop_a <= t < self.loop_b)):
            t = float(self.loop_a)
            self.pos = t
            self.timeline.set_position(t, emit=False, snap=False)
            self.lliscador.setValue(int(t * 100))
            self.temps.setText(self._fmt_timeline(t))
            if getattr(self, "sona", False):
                self.t0_pos = t
                self.t0_mono = time.monotonic()
        return t

    def _pinta_loop(self):
        """El loop el dibuixa el mateix TimelineView."""
        if (self.loop_a is not None and self.loop_b is not None
                and self.loop_b > self.loop_a):
            self.timeline.set_loop(self.loop_a, self.loop_b)
        else:
            self.timeline.set_loop(0.0, 0.0)

    def zoom(self, factor):
        if factor < 1.0:
            self.timeline.zoom_in()
        else:
            self.timeline.zoom_out()

    def zoom_tot(self):
        self.timeline.zoom_full()

    def zoom_seleccio(self):
        """Ajusta la vista del timeline perquè es vegi tota la selecció."""
        if not self.timeline.selected_keys():
            self.log("Zoom selecció: no hi ha cap clip seleccionat "
                     "(fes Ctrl/Shift+clic al timeline).")
            return
        self.timeline.zoom_selection()
        self.log("Zoom a la selecció ✅")

    def _canvia_volum(self, v):
        # S'aplica en directe al fil d'alimentacio (vegeu _alimenta): NO
        # cal reiniciar el reproductor, aixi canviar el volum no fa cap tall.
        self.vol = v / 100.0

    def _crea_selector_velocitat(self):
        """Desplegable de velocitat (es fa servir al visor i a la finestra)."""
        c = QComboBox()
        for v in self.VELOCITATS:
            c.addItem(f"{v:g}×", float(v))
        c.setToolTip("Velocitat de reproducció (0,5–3×) amb el TO MANTINGUT "
                     "(ffmpeg atempo, com el VLC). El cursor, el loop i el "
                     "metrònom es mantenen alineats. El primer cop a cada "
                     "velocitat pot trigar uns segons a preparar l'àudio.")
        c.setMaximumWidth(80)
        c.setCurrentIndex(self.VELOCITATS.index(1.0))
        c.currentIndexChanged.connect(
            lambda _i, cc=c: self.set_velocitat(cc.currentData()))
        self.cmb_vel = c
        return c

    def _sincronitza_selector_velocitat(self):
        """Posa el desplegable al valor vigent (sense disparar el canvi)."""
        c = getattr(self, "cmb_vel", None)
        if c is None:
            return
        i = c.findData(round(float(getattr(self, "velocitat", 1.0)), 4))
        if i < 0:
            return
        c.blockSignals(True)
        c.setCurrentIndex(i)
        c.blockSignals(False)

    def set_velocitat(self, factor, avisar=True):
        """Canvia la velocitat de reproducció (0,5–3,0×, to mantingut).

        Si està sonant, es repren **exactament** a la mateixa posició de la
        cançó (el cursor no salta): el buffer estirat es llig des d'on toca.
        """
        try:
            f = float(factor)
        except (TypeError, ValueError):
            return
        f = round(max(0.5, min(3.0, f)), 2)
        if abs(f - float(getattr(self, "velocitat", 1.0))) < 1e-9:
            self._sincronitza_selector_velocitat()
            return
        # Preparar el buffer ABANS de tocar la reproducció: si falla, no canvia.
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                self._mono_a(f)
            finally:
                QApplication.restoreOverrideCursor()
        except (RuntimeError, OSError, ValueError) as e:
            self.log(f"velocitat {f:g}×: no s'ha pogut preparar ({e})")
            if avisar:
                QMessageBox.warning(self, "Velocitat",
                                    f"No s'ha pogut preparar l'àudio a "
                                    f"{f:g}×:\n{e}")
            self._sincronitza_selector_velocitat()
            return
        sonava = bool(self.sona)
        pos = float(self.pos)
        if sonava:
            self._atura_proc()     # invalida el fil vell (el rellotge segueix)
        self.velocitat = f
        self._sincronitza_selector_velocitat()
        self.log(f"velocitat: {f:g}×"
                 + (" (to mantingut)" if abs(f - 1.0) > 1e-9 else ""))
        if sonava:
            self._engega_des_de(pos)   # re-ancora t0 amb la velocitat nova
            if self.proc is None:
                self.play_stop()
        self.velocitatCanviada.emit(f)

    def metro_disponible(self):
        """El metrònom només té sentit amb graella (mode BPM · compàs)."""
        return bool(self.tempo_fix)

    def set_metro(self, on):
        """Fixa l'estat del metrònom — **sense tallar la reproducció**.

        El fil d'alimentació llig `metro_on`/`metro_vol` a **cada tros**, igual
        que fa amb el volum i el mute: el canvi s'aplica a l'instant. Abans es
        reiniciava el reproductor (`_atura_proc` + `_engega_des_de`) i se sentia
        un **micro-tall** a l'àudio cada cop que es posava o treia el metrònom
        (reportat per l'operador, 18-10-2026). El reinici era un vestigi de quan
        el clic es pre-mesclava a la memòria.
        """
        on = bool(on)
        if on == self.metro_on:
            return
        self.metro_on = on
        if self.metro_on:
            self.log(
                f"metrònom ON: {self.bpm_mostra()} "
                f"{bpm_unit_mod.etiqueta(self.bpm_unit).lower()} "
                f"({float(self.bpm):.3f} negres/min) · compàs "
                f"{int(self.bpb)}/{int(self.beat_type)} · patró "
                f"{self.metro_mode}")
        else:
            self.log("metrònom OFF")

    def commuta_metro(self):
        """Activa/desactiva el metrònom (sense tallar la reproducció)."""
        self.set_metro(not self.metro_on)

    def set_metro_forcat(self, bpm=None, bpb=4, offset=0.0, den=4, mode=None):
        """Metrònom sobre una graella pròpia: `bpm` + `bpb`/`den` des de `offset`.

        Amb `bpm=None` es torna al metrònom normal (mapa de tempo o BPM de la
        barra). El fil d'àudio ho llig **a cada tros**, així que el canvi de
        BPM o l'encesa/apagada s'apliquen a l'instant i **sense reiniciar** el
        reproductor (cap micro-tall).
        """
        if bpm is None:
            self.metro_forcat = None
            self.log("metrònom forçat: OFF (torna al mapa)")
            return
        bpm = float(bpm)
        if not (bpm > 0):
            self.metro_forcat = None
            return
        try:
            den = int(den)
        except (TypeError, ValueError):
            den = 4
        if den not in limits.DENOMINADORS_ADMESOS:
            den = 4
        if mode not in metronom.MODES:
            mode = getattr(self, "metro_mode", "auto")
        if mode not in metronom.MODES:
            mode = "auto"
        self.metro_forcat = (bpm, max(1, int(bpb)), float(offset),
                             den, mode)
        self.log(f"metrònom forçat: {bpm:.2f} BPM · compàs "
                 f"{int(bpb)}/{den} · patró {mode} · "
                 f"des de {float(offset):.3f}s")

    def set_metro_mode(self, mode):
        """Canvia el patró del metrònom sense tallar la reproducció."""
        if mode not in metronom.MODES:
            mode = "auto"
        self.metro_mode = mode
        if self.metro_forcat is not None:
            bpm, bpb, offset, den, _mode = self.metro_forcat
            self.metro_forcat = (bpm, bpb, offset, den, mode)
        self.log(f"metrònom: patró {mode}")

    def _canvia_vol_metro(self, v):
        """Volum del clic (0-100) — **sense tallar la reproducció**.

        Mateix motiu que `set_metro`: el fil ho llig a cada tros.
        """
        self.metro_vol = max(0.0, min(1.0, v / 100.0))

    def set_mut(self, on):
        """Fixa el mute (les barres de fora NO toquen b_mut)."""
        self.mut = bool(on)
        if hasattr(self, "b_mut") and self.b_mut.isChecked() != self.mut:
            self.b_mut.setChecked(self.mut)
        self.log(f"mute {'ON' if self.mut else 'OFF'}")
        # S'aplica en directe al fil d'alimentacio: sense reiniciar.

    def commuta_mut(self):
        self.set_mut(not self.mut)

    def _on_loop_changed(self, a, b):
        """Loop A/B seleccionat al regle del timeline (1 cop per arrossegada)."""
        self._undo_marca()          # A1: el loop també és desfer/fer
        self.loop_a, self.loop_b = float(a), float(b)
        self.loop_on = True
        if hasattr(self, "b_loop"):
            self.b_loop.setChecked(True)
        # El botó 🔁 de la barra de fora ha de reflectir-ho (abans quedava
        # desactivat mentre el play ja feia loop).
        self.loopStateChanged.emit(True)
        self.log(f"loop A={a:.3f}s B={b:.3f}s")
        self._undo_commit()
