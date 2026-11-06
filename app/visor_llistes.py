"""Poblament i handlers de les llistes del visor (F4).

Extret de `app/visor.py`: llistes d'acords, estructura i tempo, amb la
preservació de la fila seleccionada.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QAbstractItemView, QTableWidget, QTableWidgetItem

from . import rubato as rubato_mod
from .visor_io import nom_acord

class LlistesMixin:
    """Llistes d'acords, estructura i tempo."""

    def _omple_llista_ac(self):
        # Preserva la fila seleccionada: _actualitza_temps() repobla la llista
        # i, sense aixo, el clear() en perdia la seleccio (bug: clicar una
        # fila no la deixava ressaltada perque ves_a()->_actualitza_temps()).
        cur = self.llista_ac.currentRow()
        self.llista_ac.clear()
        for _a in self.acords:
            t, c = float(_a[0]), nom_acord(_a)
            et = self._fmt_compas(t) if self.tempo_fix else f"{t:07.3f}s"
            self.llista_ac.addItem(f"{et}  {c}")
        if 0 <= cur < self.llista_ac.count():
            self.llista_ac.setCurrentRow(cur)

    @staticmethod
    def _centra_fila_llista(llista, row):
        """Deixa la fila seleccionada al centre del viewport de la llista.

        Si no hi ha prou files abans o després, Qt la deixa el més a prop
        possible del centre. Així sempre es veuen unes quantes files
        anteriors i posteriors, i la selecció blava no queda amagada a la
        vora inferior.
        """
        row = int(row)
        if llista is None or row < 0:
            return
        # Si la llista encara no s'ha mostrat (tests, canvi de layout), Qt no
        # pot calcular el viewport; no hi ha res a centrar.
        if not bool(getattr(llista, "isVisible", lambda: True)()):
            return
        if isinstance(llista, QTableWidget):
            # Amb ScrollPerItem, Qt no pot centrar una fila; en píxels sí.
            if llista.verticalScrollMode() != QAbstractItemView.ScrollPerPixel:
                llista.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
            item = llista.item(row, 0)
        else:
            item = llista.item(row)
        if item is not None:
            llista.scrollToItem(item, QAbstractItemView.PositionAtCenter)

    def _salt_acord(self, item):
        row = self.llista_ac.row(item)
        if row >= 0:
            self.timeline.select_clip("chord", row)
        self._centra_fila_llista(self.llista_ac, row)
        self.ves_a(self._parse_pos_label(item.text()))
        # Desplaça la vista cap al cursor NOMÉS si cal (manté el zoom).
        self.timeline.ensure_cursor_visible()

    def _actualitza_llista_abc(self):
        cur = self.llista_ab.currentRow()    # preserva la seleccio (vegeu _omple_llista_ac)
        self.llista_ab.clear()
        for ini, fi, L, fam in self.seccions:
            if self.tempo_fix:
                ini_txt = self._fmt_compas(ini)
                fi_txt = self._fmt_compas(fi)
            else:
                ini_txt = f"{ini:07.3f}s"
                fi_txt = f"{fi:07.3f}s"
            self.llista_ab.addItem(f"{L} ({fam})  {ini_txt}–{fi_txt}")
        if 0 <= cur < self.llista_ab.count():
            self.llista_ab.setCurrentRow(cur)

    def _salt_seccio(self, item):
        row = self.llista_ab.row(item)
        if row >= 0:
            self.timeline.select_clip("section", row)
        self._centra_fila_llista(self.llista_ab, row)
        self.ves_a(self._parse_pos_label(item.text()))
        # Desplaça la vista cap al cursor NOMÉS si cal (manté el zoom).
        self.timeline.ensure_cursor_visible()

    def _omple_llista_tempo(self):
        """Una fila per tram del mapa (inici, fi, BPM, compàs).

        Es repobla des de `_actualitza_temps()`, el punt únic que ja criden
        tots els camins que canvien el mapa (barra, diàlegs, drag, undo).
        Preserva la fila seleccionada, com les altres dues llistes.
        """
        t = getattr(self, "llista_tempo", None)
        if t is None:
            return
        cur = t.currentRow()
        trams = list(getattr(self, "tempo_trams", None) or [])
        t.blockSignals(True)
        try:
            t.setRowCount(len(trams))
            for i, tr in enumerate(trams):
                ini, fi, bpm = float(tr[0]), float(tr[1]), float(tr[2])
                rubato = getattr(tr, "tipus", None) == "rubato"
                if rubato:
                    compas = "R " + rubato_mod.presenta_compassos(tr.compassos)
                else:
                    compas = f"{int(tr[3])}/{int(tr[4])}"
                vals = (f"{ini:.3f}", f"{fi:.3f}",
                        self.bpm_mostra(bpm), compas)
                for c, v in enumerate(vals):
                    it = t.item(i, c)
                    if it is None:
                        it = QTableWidgetItem()
                        it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                        t.setItem(i, c, it)
                    if it.text() != v:
                        it.setText(v)
        finally:
            t.blockSignals(False)
        if 0 <= cur < t.rowCount():
            t.setCurrentCell(cur, 0)

    def _salt_tempo(self, item):
        """Clic a la llista de tempo → selecciona el clip i hi porta el cursor."""
        row = self.llista_tempo.row(item)
        if row < 0:
            return
        self._ed_kind, self._ed_idx = "tempo", row
        self.timeline.select_clip("tempo", row)
        self._centra_fila_llista(self.llista_tempo, row)
        self._actualitza_editor()
        trams = getattr(self, "tempo_trams", None) or []
        if 0 <= row < len(trams):
            self.ves_a(float(trams[row][0]))
        self.timeline.ensure_cursor_visible()
