"""Diàleg del mapa de tempo per trams."""
import math

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from app import bpm_unit, tempo_map

class DialegTempoMapa(QDialog):
    """Editor del mapa de **tempo i compàs** (canvis al llarg del tema).

    Cada fila és un tros que val fins a la següent: «Des de (s)», «BPM» i
    «Compàs» (`num/den`). La primera fila («Des de 0 s») és el valor inicial.
    """

    def __init__(self, parent=None, trams=None, durada=0.0,
                 unit=bpm_unit.DEFECTE):
        super().__init__(parent)
        self._unit = bpm_unit.normalitza(unit)
        self.setWindowTitle("Mapa de tempo i compàs")
        self.setMinimumWidth(470)
        self._durada = float(durada or 0.0)
        self._trams = tempo_map.normalitza_trams(list(trams or []),
                                                 self._durada)
        lay = QVBoxLayout(self)
        avis = QLabel(
            "El tempo i el compàs poden **canviar** al llarg del tema (com un "
            "DAW). Cada fila val fins a la següent; la primera («Des de 0 s») "
            "és el valor inicial.\nA «Des de» pots escriure **segons** (p. ex. "
            "`90`) o un **compàs** fent-ho començar per `c` (p. ex. `c33` o "
            "`c33.1`).\nEls rubatos es creen des del visor amb «Marca com a "
            "rubato» o «Converteix a rubato».")
        avis.setWordWrap(True)
        lay.addWidget(avis)
        self.taula = QTableWidget(0, 3)
        self.taula.setHorizontalHeaderLabels(["Des de (s)", "BPM", "Compàs"])
        self.taula.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        lay.addWidget(self.taula)
        fila = QHBoxLayout()
        b_add = QPushButton("Afegeix un canvi")
        b_del = QPushButton("Elimina")
        b_add.clicked.connect(self._afegeix)
        b_del.clicked.connect(self._elimina)
        fila.addWidget(b_add)
        fila.addWidget(b_del)
        fila.addStretch(1)
        lay.addLayout(fila)
        botons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botons.accepted.connect(self.accept)
        botons.rejected.connect(self.reject)
        lay.addWidget(botons)
        self._omple()

    # -- taula <-> trossos ----------------------------------------------
    def _omple(self):
        self.taula.setRowCount(0)
        for i, s in enumerate(self._trams):
            r = self.taula.rowCount()
            self.taula.insertRow(r)
            it0 = QTableWidgetItem("0.000" if i == 0 else f"{float(s[0]):.3f}")
            if i == 0:
                it0.setFlags(Qt.ItemIsEnabled)      # el valor inicial: fix
            self.taula.setItem(r, 0, it0)
            bpm_mostra = bpm_unit.de_quarter(float(s[2]), self._unit)
            self.taula.setItem(r, 1, QTableWidgetItem(f"{bpm_mostra:g}"))
            self.taula.setItem(r, 2,
                               QTableWidgetItem(f"{int(s[3])}/{int(s[4])}"))

    def _sync(self):
        """Llegeix la taula cap a `self._trams` (encara per normalitzar)."""
        out = []
        for r in range(self.taula.rowCount()):
            def _t(c):
                it = self.taula.item(r, c)
                return it.text().strip() if it else ""
            # El PRIMER argument de `_t` és la COLUMNA (un int): abans hi
            # passaven strings ("0"/"1"/"2"), cosa que feia petar
            # `self.taula.item(r, "0")` amb TypeError — i no es capturava, així
            # que el diàleg del mapa PETAVA en afegir/eliminar un tram o en
            # prémer OK (auditoria 18-10-2026, destapat pel primer test que
            # exercita el diàleg).
            txt_ini = _t(0).replace(",", ".").strip().lower()
            try:
                bpm = bpm_unit.a_quarter(
                    float(_t(1).replace(",", ".")), self._unit)
                if r == 0:
                    ini = 0.0
                elif txt_ini.startswith("c"):
                    ini = self._temps_de_compas(txt_ini[1:])
                else:
                    ini = float(txt_ini)
            except (ValueError, IndexError) as e:
                raise ValueError(f"Fila {r + 1}: BPM o inici no vàlid") from e
            if not math.isfinite(ini):
                raise ValueError(f"Fila {r + 1}: l'inici ha de ser finit")
            if ini < 0:
                raise ValueError(f"Fila {r + 1}: l'inici no pot ser negatiu")
            if self._durada > 0 and ini >= self._durada:
                raise ValueError(f"Fila {r + 1}: l'inici queda fora de la WAV")
            if out and ini <= out[-1][0] + 1e-12:
                raise ValueError(
                    f"Fila {r + 1}: els inicis han d'anar en ordre creixent")
            comp = _t(2).replace(" ", "")
            if "/" in comp:
                try:
                    a, b = comp.split("/", 1)
                    num, den = int(a), int(b)
                except ValueError as e:
                    raise ValueError(
                        f"Fila {r + 1}: compàs «{comp}» no vàlid") from e
            else:
                raise ValueError(
                    f"Fila {r + 1}: escriu el compàs com num/den")
            try:
                bpm, num, den = tempo_map.valida_tempo(bpm, num, den)
            except ValueError as e:
                raise ValueError(f"Fila {r + 1}: {e}") from e
            if num == 0 and den == 0:
                raise ValueError(
                    f"Fila {r + 1}: el rubato es crea des del visor "
                    "(«Marca com a rubato» / «Converteix a rubato»).")
            out.append((ini, ini, bpm, num, den))
        if not out:
            raise ValueError("El mapa de tempo/compàs és buit")
        self._trams = out

    def accept(self):
        try:
            self.trams()
        except ValueError as e:
            QMessageBox.warning(self, "Mapa de tempo invàlid", str(e))
            return
        super().accept()

    def _temps_de_compas(self, text):
        """`33` / `33.1` (compàs[.temps]) → segons, segons el mapa actual."""
        from app.tempo_map import TempoMap
        mapa = TempoMap(tempo_map.normalitza_trams(self._trams,
                                                   self._durada))
        parts = str(text).split(".")
        bar = int(parts[0])
        beat = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
        return float(mapa.t_de_pos(bar, beat))

    def _afegeix(self):
        try:
            self._sync()
        except ValueError as e:
            QMessageBox.warning(self, "Mapa de tempo invàlid", str(e))
            return
        # `_sync` deixa els trams com `(ini, ini, …)` (el `fi` encara per
        # derivar): cal NORMALITZAR abans de calcular el punt mig del darrer
        # tram, o el mig ix igual que la frontera i el tall es descarta (el
        # botó «+» no feia res — auditoria 18-10-2026).
        trams = tempo_map.normalitza_trams(self._trams, self._durada)
        t = 0.0
        if trams:
            s = trams[-1]
            t = (float(s[0]) + float(s[1])) / 2.0
        self._trams = tempo_map.normalitza_trams(
            tempo_map.afegeix_tall(trams, t), self._durada)
        self._omple()

    def _elimina(self):
        r = self.taula.currentRow()
        if r <= 0:                               # no es toca el valor inicial
            return
        try:
            self._sync()
        except ValueError as e:
            QMessageBox.warning(self, "Mapa de tempo invàlid", str(e))
            return
        self._trams = tempo_map.normalitza_trams(
            tempo_map.elimina_tall(self._trams, r), self._durada)
        self._omple()

    def trams(self):
        """Els trossos editats (`(ini, fi, bpm, num, den)`, contigus)."""
        self._sync()
        return tempo_map.normalitza_trams(self._trams, self._durada)
