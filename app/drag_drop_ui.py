"""Helpers de drag & drop de la finestra (F3).

Extret de `app/main.py`: desactivació de drops als fills i gestió del drag.
Els overrides de Qt (`dragEnterEvent`, `dropEvent`…) es queden a `Finestra`.
"""
import os

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QWidget

from . import drag_drop

class DragDropMixin:
    """Gestió dels drag & drop d'àudio."""

    def _desactiva_drops_fills(self):
        """Fa que els fills no capturen el drop (que arribe a la finestra).

        `QLineEdit`, `QTextEdit` i els seus viewports accepten drops de text
        per defecte; si l'usuari deixa anar un àudio damunt, hi enganxarien la
        ruta. Amb `acceptDrops` desactivat, Qt propaga el drag al
        `QMainWindow`, que és qui obri l'àudio.
        """
        for w in self.findChildren(QWidget):
            if w is not self and w.acceptDrops():
                try:
                    w.setAcceptDrops(False)
                except RuntimeError:
                    pass

    @staticmethod
    def _accepta_copia(ev):
        """Accepta el drag com a CÒPIA (mai movem ni esborrem l'original)."""
        if ev.possibleActions() & Qt.CopyAction:
            ev.setDropAction(Qt.CopyAction)
        ev.accept()

    def _drag_entra(self, ev):
        """DragEnter amb almenys un àudio: l'acceptem i mostrem l'avís."""
        if not drag_drop.te_audio(ev.mimeData()):
            return False
        self._accepta_copia(ev)
        self.statusBar().showMessage(
            "Deixa anar el fitxer d'àudio per obrir-lo")
        return True

    def _drag_mou(self, ev):
        if not drag_drop.te_audio(ev.mimeData()):
            return False
        self._accepta_copia(ev)
        return True

    def _drag_deixa(self, ev):
        """Drop: obre el primer àudio. La feina grossa es fa FORA del drop.

        Els gestors de fitxers dels 3 SO esperen que el dropEvent torne de
        seguida; obrir diàlegs o convertir l'àudio ací faria que el drag
        d'origen es quedara penjat. Per això s'ajorna al cicle
        d'esdeveniments (`QTimer.singleShot`).
        """
        rutes = drag_drop.rutes_audio(ev.mimeData())
        if not rutes:
            ev.ignore()
            return False
        self._accepta_copia(ev)
        self.statusBar().clearMessage()
        if len(rutes) > 1:
            self.registra(
                "Drag & drop: hi ha %d àudios; s'obre només «%s»"
                % (len(rutes), os.path.basename(rutes[0])))
        QTimer.singleShot(0, lambda r=rutes[0]: self._obri_des_de_wav(r))
        return True

