"""Genera la icona de l'aplicació (finestra + .desktop + AppImage).

La dibuixa amb Qt (QPainter) a partir dels colors de `app/theme.py` i d'una
icona de Lucide (`icones/`), així queda coherent amb la UI. Genera els PNG a
`icona/` en diverses mides (les que vol l'AppImage: 256, 512).

Ús: .venv/bin/python eines/crea_icona.py
"""

import os
import sys

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import (QBrush, QColor, QFont, QImage, QLinearGradient,
                         QPainter, QPen, QPixmap)
from PyQt5.QtSvg import QSvgRenderer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import theme  # noqa: E402

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESTI = os.path.join(ARREL, "icona")
MIDES = (1024, 512, 256, 128, 64, 48, 32)


def _svg_icona(nom, color):
    with open(os.path.join(ARREL, "icones", nom + ".svg"), encoding="utf-8") as f:
        return f.read().replace("currentColor", color)


def dibuixa(mida):
    """Icona: quadrat arrodonit fosc + forma d'ona (Lucide) en blau."""
    img = QImage(mida, mida, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)

    m = mida
    r = m * 0.22
    # fons: degradat fosc
    g = QLinearGradient(0, 0, 0, m)
    g.setColorAt(0.0, QColor("#1b1e24"))
    g.setColorAt(1.0, QColor("#0f0f10"))
    p.setBrush(QBrush(g))
    p.setPen(QPen(QColor("#3a4150"), max(1.0, m * 0.006)))
    p.drawRoundedRect(QRectF(m * 0.035, m * 0.035, m * 0.93, m * 0.93), r, r)

    # forma d'ona (Lucide "audio-lines"), en blau, al centre
    svg = _svg_icona("audio-lines", theme.BLAU_INFO)
    rend = QSvgRenderer(svg.encode("utf-8"))
    costat = m * 0.55
    rend.render(p, QRectF((m - costat) / 2, (m - costat) / 2, costat, costat))

    # inicial "A" discreta a baix a la dreta?  -> millor net, sense text
    p.end()
    return img


def main():
    os.makedirs(DESTI, exist_ok=True)
    for m in MIDES:
        img = dibuixa(m)
        ruta = os.path.join(DESTI, f"auto-chords-{m}.png")
        img.save(ruta)
        print(f"  ✓ {os.path.basename(ruta)}")
    # la principal (la que busquen els .desktop / AppImage)
    import shutil
    shutil.copy(os.path.join(DESTI, "auto-chords-512.png"),
                os.path.join(DESTI, "auto-chords.png"))
    print(f"  ✓ auto-chords.png (=512)")
    print(f"fet: {len(MIDES) + 1} fitxers a icona/")


if __name__ == "__main__":
    main()
