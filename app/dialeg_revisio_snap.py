"""Diàleg de revisió dels dubtes del snap."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout,
)

class DialegRevisioSnap(QDialog):
    """Llista no modal de marcadors que el snap no ha pogut col·locar.

    No bloqueja ni pregunta res mentre sona: s'obri després del play i es pot
    deixar oberta. Doble clic en un tall porta el cursor a eixe punt per
    inspeccionar-lo.
    """

    def __init__(self, parent=None, ambigus=None, ves_a=None, snap=None):
        super().__init__(parent)
        self.setModal(False)
        self.setWindowTitle("Revisió del snap de compassos")
        self.setMinimumWidth(520)
        self._ves_a = ves_a
        self._snap = snap
        lay = QVBoxLayout(self)
        info = QLabel(
            "Estos marcadors no han trobat un beat/bar de QM dins de la "
            "tolerància. No s'han mogut. Doble clic per anar-hi.")
        info.setWordWrap(True)
        info.setStyleSheet("color:#9aa6b8; font-size:11px;")
        lay.addWidget(info)
        self.llista = QListWidget(self)
        for vell, proper, delta in (ambigus or ()):
            txt = (f"{float(vell):8.3f}s → {float(proper):8.3f}s "
                   f"({float(delta) * 1000:+.0f} ms)")
            item = QListWidgetItem(txt)
            item.setData(Qt.UserRole, float(vell))
            item.setData(Qt.UserRole + 1, float(proper))
            self.llista.addItem(item)
        self.llista.itemDoubleClicked.connect(self._anar)
        lay.addWidget(self.llista)
        box = QDialogButtonBox()
        self.b_snap = QPushButton("Snap al candidat")
        self.b_snap.setObjectName("secundari")
        self.b_snap.setEnabled(False)
        self.b_snap.clicked.connect(self._snap_seleccionat)
        box.addButton(self.b_snap, QDialogButtonBox.ActionRole)
        b_tanca = QPushButton("Tanca")
        b_tanca.clicked.connect(self.reject)
        box.addButton(b_tanca, QDialogButtonBox.RejectRole)
        lay.addWidget(box)
        self.llista.currentItemChanged.connect(
            lambda cur, _old: self.b_snap.setEnabled(cur is not None))

    def _anar(self, item):
        if self._ves_a is not None:
            try:
                self._ves_a(float(item.data(Qt.UserRole)))
            except Exception:  # noqa: BLE001
                pass

    def _snap_seleccionat(self):
        item = self.llista.currentItem()
        if item is None or self._snap is None:
            return
        vell = float(item.data(Qt.UserRole))
        proper = float(item.data(Qt.UserRole + 1))
        try:
            ok = bool(self._snap(vell, proper))
        except Exception:  # noqa: BLE001
            ok = False
        if ok:
            self.llista.takeItem(self.llista.row(item))
