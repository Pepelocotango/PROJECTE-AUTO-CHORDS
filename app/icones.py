"""Icones de la UI: SVG de Lucide (llicència ISC, https://lucide.dev).

Els fitxers viuen a `icones/` (a l'arrel del projecte) i porten
`stroke="currentColor"`, que aquí substituïm pel color que volem. Així una
mateixa icona serveix per a fons clars i foscos sense duplicar fitxers.

Ús:
    from app import icones
    boto.setIcon(icones.ico("play"))
    accio.setIcon(icones.ico("target", color=icones.ACTIU))
"""

import os

from PyQt5.QtCore import QByteArray, QSize, Qt
from PyQt5.QtGui import QIcon, QPainter, QPixmap
from PyQt5.QtSvg import QSvgRenderer

_ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DIR = os.path.join(_ARREL, "icones")

# Color per defecte: el text de la UI (clar sobre fons fosc).
TEXT = "#f3f4f6"
MUTED = "#a7acb5"
# Colors d'estat (coincideixen amb app/theme.py).
ACTIU = "#ffffff"       # damunt del blau/taronja quan el botó està encès
BLAU = "#38bdf8"
GROC = "#ffb26b"        # (nom històric: ara és un TARONJA SUAU, com theme.py)
VERMELL = "#ff6b6b"

_CACHE = {}


def disponible(nom):
    return os.path.isfile(os.path.join(_DIR, nom + ".svg"))


def _svg_recolorejat(nom, color):
    ruta = os.path.join(_DIR, nom + ".svg")
    with open(ruta, encoding="utf-8") as f:
        s = f.read()
    return s.replace("currentColor", color)


def ico(nom, mida=18, color=TEXT):
    """Retorna un QIcon de la icona `nom`, de `mida` px i `color` donat.

    Si l'SVG no hi és, retorna un QIcon buit (l'app no ha de petar mai per
    una icona que falti).
    """
    clau = (nom, int(mida), color)
    if clau in _CACHE:
        return _CACHE[clau]
    if not disponible(nom):
        return QIcon()
    dades = QByteArray(_svg_recolorejat(nom, color).encode("utf-8"))
    rend = QSvgRenderer(dades)
    pm = QPixmap(int(mida), int(mida))
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    rend.render(p)
    p.end()
    ic = QIcon(pm)
    _CACHE[clau] = ic
    return ic


def icona_boto(boto, nom, mida=18, color=TEXT):
    """Posa la icona a un botó (i treu el text si era només un símbol)."""
    boto.setIcon(ico(nom, mida, color))
    boto.setIconSize(pm_mida(mida))
    return boto


def pm_mida(mida):
    return QSize(int(mida), int(mida))


def icona_app():
    """QIcon del logo de l'aplicació (barra de títol / llançador).

    El logo es genera a `icona/` (vegeu eines/crea_icona.py). Si no hi és,
    retorna un QIcon buit: l'app no ha de petar mai per una icona que falti.
    """
    for nom in ("auto-chords.png", "auto-chords-256.png", "auto-chords-128.png"):
        ruta = os.path.join(_ARREL, "icona", nom)
        if os.path.isfile(ruta):
            return QIcon(ruta)
    return QIcon()
