"""Geometria persistent de la finestra principal i dels diàlegs.

Guarda `saveGeometry()` (i `saveState()` a la finestra principal) en un JSON
dins `config.DADES_DIR`, de manera atòmica. És el mateix mecanisme a Linux,
Windows i macOS; el gestor de finestres pot ignorar la posició en Wayland,
però la mida i la resta d'estat es continuen restaurant.
"""
import json
import os
import tempfile

from PyQt5.QtCore import QByteArray, QTimer
from PyQt5.QtWidgets import QApplication, QMainWindow

from . import config

FITXER = os.path.join(config.DADES_DIR, "finestres.json")

# No escrivim estat durant la suite (offscreen) ni si l'usuari ho desactiva:
# així els tests no embruten el repo i es poden executar en paral·lel.
def persistencia_activa():
    """Cert si esta execució ha de llegir/escriure geometria."""
    if os.environ.get("AUTO_CHORDS_SENSE_GEOMETRIA"):
        return False
    return (os.environ.get("QT_QPA_PLATFORM", "").lower()
            not in ("offscreen", "minimal"))


def _clau(widget, clau=None):
    if clau:
        return clau
    try:
        nom = widget.objectName()
    except (AttributeError, RuntimeError):
        nom = ""
    return nom or type(widget).__name__


def _carrega():
    try:
        with open(FITXER, encoding="utf-8") as f:
            dades = json.load(f)
        return dades if isinstance(dades, dict) else {}
    except (OSError, ValueError):
        return {}


def _desa(dades):
    carpeta = os.path.dirname(FITXER) or "."
    os.makedirs(carpeta, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".finestres_", suffix=".json",
                               dir=carpeta)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(dades, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, FITXER)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _a_base64(bytearray):
    return bytes(bytearray.toBase64()).decode("ascii")


def _de_base64(text):
    return QByteArray.fromBase64(str(text).encode("ascii"))


def _visible(widget):
    """La finestra té prou superfície dins alguna pantalla disponible."""
    try:
        geo = widget.frameGeometry()
    except RuntimeError:
        return False
    for pantalla in QApplication.screens():
        part = pantalla.availableGeometry().intersected(geo)
        if part.width() >= 80 and part.height() >= 40:
            return True
    return False


def _damunt(widget):
    try:
        if widget.isVisible():
            widget.raise_()
            widget.activateWindow()
    except RuntimeError:
        pass


def _centra(widget):
    """Centra en el següent cicle, quan el WM ja ha aplicat la mida final."""
    def _fer():
        try:
            if not widget.isVisible():
                return
            pantalla = (widget.screen() or QApplication.primaryScreen())
            if pantalla is None:
                return
            geo = pantalla.availableGeometry()
            fg = widget.frameGeometry()
            fg.moveCenter(geo.center())
            widget.move(fg.topLeft())
            _damunt(widget)
        except RuntimeError:
            pass

    QTimer.singleShot(0, _fer)


def restaura(widget, clau=None, centra_si_falta=True):
    """Restaura geometria/estat; si no és vàlida, centra (si cal).

    Retorna `True` si ha restaurat una geometria desada.
    """
    clau = _clau(widget, clau)
    entrada = _carrega().get(clau, {}) if persistencia_activa() else {}
    ok = False
    text = entrada.get("geometry")
    if text:
        try:
            ok = bool(widget.restoreGeometry(_de_base64(text)))
        except (TypeError, ValueError, RuntimeError):
            ok = False
    # Si la geometria desada no cap a la pantalla (p. ex. un dialeg que
    # es va obrir molt alt), la descartem i centrem amb la mida per defecte.
    try:
        from PyQt5.QtWidgets import QApplication
        scr = widget.screen() or QApplication.primaryScreen()
        if ok and scr is not None:
            avail = scr.availableGeometry()
            if (widget.frameGeometry().height() > avail.height() - 40
                    or widget.frameGeometry().width() > avail.width() - 40):
                ok = False
    except Exception:  # noqa: BLE001
        pass
    if not ok or not _visible(widget):
        if centra_si_falta or text:
            _centra(widget)
        return False
    estat = entrada.get("state")
    if estat and isinstance(widget, QMainWindow):
        try:
            widget.restoreState(_de_base64(estat))
        except (TypeError, ValueError, RuntimeError):
            pass
    QTimer.singleShot(0, lambda: _damunt(widget))
    return True


def desa(widget, clau=None):
    """Guarda geometria (i estat de la finestra principal) de forma atòmica."""
    if not persistencia_activa():
        return
    clau = _clau(widget, clau)
    dades = _carrega()
    entrada = dades.setdefault(clau, {})
    try:
        entrada["geometry"] = _a_base64(widget.saveGeometry())
        if isinstance(widget, QMainWindow):
            entrada["state"] = _a_base64(widget.saveState())
    except RuntimeError:
        return
    try:
        _desa(dades)
    except OSError:
        # Un error d'estat local no ha de fer caure l'app en tancar.
        pass


class GeometriaMixin:
    """Recorda posició i mida d'un diàleg entre sessions.

    Si no hi ha geometria desada (o queda fora de pantalla), el diàleg es
    centra a la pantalla. Els diàlegs modals continuen pel damunt del parent.
    """

    _geo_clau = None

    def showEvent(self, event):
        super().showEvent(event)
        restaura(self, self._geo_clau or type(self).__name__)

    def hideEvent(self, event):
        desa(self, self._geo_clau or type(self).__name__)
        super().hideEvent(event)
