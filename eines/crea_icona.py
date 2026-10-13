"""Genera la icona de l'aplicació (finestra + .desktop + AppImage + Windows + macOS).

Renderitza el logo vectorial `icona/auto-chords-logo.svg` a PNG (diverses
mides) i, a més, en deriva el format propi de cada sistema:
  · Linux   -> els PNG (els fan servir el .desktop, l'AppImage i la finestra)
  · Windows -> `auto-chords.ico`  (diverses mides dins d'un sol fitxer)
  · macOS   -> `auto-chords.icns` (format d'icones d'Apple)

Tot es fa per codi i SENSE dependències externes: els .ico i .icns es
construeixen a mà (pur Python), així el mateix script val a qualsevol SO.

Ús: .venv/bin/python eines/crea_icona.py
"""

import os
import struct

from PyQt5.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PyQt5.QtGui import QImage, QPainter
from PyQt5.QtSvg import QSvgRenderer

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESTI = os.path.join(ARREL, "icona")
SVG = os.path.join(DESTI, "auto-chords-logo.svg")
MIDES = (1024, 512, 256, 128, 64, 48, 32)      # PNG per a Linux
MIDES_ICO = (16, 24, 32, 48, 64, 128, 256)     # mides dins l'.ico de Windows

_SVG_DATA = None


def _svg():
    global _SVG_DATA
    if _SVG_DATA is None:
        with open(SVG, encoding="utf-8") as f:
            _SVG_DATA = f.read().encode("utf-8")
    return _SVG_DATA


def _render(mida):
    """QImage del logo a `mida` px (l'SVG ja porta el marc i el fons)."""
    rend = QSvgRenderer(QByteArray(_svg()))
    img = QImage(mida, mida, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    rend.render(p, QRectF(0, 0, mida, mida))
    p.end()
    return img


def _png(mida):
    """Bytes PNG del logo a `mida` px (en memòria, per als .ico/.icns)."""
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    _render(mida).save(buf, "PNG")
    buf.close()
    return bytes(buf.data())


def _escriu_ico(desti, pngs):
    """ICO (Windows): capçalera + directori + PNGs incrustats (Vista+)."""
    n = len(pngs)
    cap = struct.pack("<HHH", 0, 1, n)          # reserved, type=icon, count
    offset = 6 + 16 * n
    entrades, dades = b"", b""
    for mida, d in sorted(pngs):
        w = h = 0 if mida >= 256 else mida      # 0 = 256 px (conveni ICO)
        entrades += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(d), offset)
        offset += len(d)
        dades += d
    with open(desti, "wb") as f:
        f.write(cap + entrades + dades)


def _escriu_icns(desti, mapa):
    """ICNS (macOS): magic 'icns' + mida total + blocs [tipus + mida + PNG]."""
    blocs = b""
    for tipus, d in mapa:
        blocs += tipus + struct.pack(">I", 8 + len(d)) + d
    with open(desti, "wb") as f:
        f.write(b"icns" + struct.pack(">I", 8 + len(blocs)) + blocs)


def main():
    os.makedirs(DESTI, exist_ok=True)
    if not os.path.isfile(SVG):
        raise SystemExit(f"falta el logo: {SVG}")

    # 1) PNG — Linux: .desktop, AppImage (.DirIcon) i finestra de l'app.
    for m in MIDES:
        _render(m).save(os.path.join(DESTI, f"auto-chords-{m}.png"))
        print(f"  ✓ auto-chords-{m}.png")
    import shutil
    shutil.copy(os.path.join(DESTI, "auto-chords-512.png"),
                os.path.join(DESTI, "auto-chords.png"))
    print("  ✓ auto-chords.png (=512)")

    # 2) Windows: .ico multi-mida (per a l'EXE de PyInstaller).
    _escriu_ico(os.path.join(DESTI, "auto-chords.ico"),
                [(m, _png(m)) for m in MIDES_ICO])
    print(f"  ✓ auto-chords.ico ({len(MIDES_ICO)} mides)")

    # 3) macOS: .icns (tipus PNG, suportat per High Sierra 10.13+).
    mapa = [
        (b"icp4", _png(16)), (b"icp5", _png(32)), (b"icp6", _png(64)),
        (b"ic07", _png(128)), (b"ic08", _png(256)), (b"ic09", _png(512)),
        (b"ic10", _png(1024)),
        (b"ic11", _png(32)), (b"ic12", _png(64)), (b"ic13", _png(256)),
        (b"ic14", _png(512)),
    ]
    _escriu_icns(os.path.join(DESTI, "auto-chords.icns"), mapa)
    print(f"  ✓ auto-chords.icns ({len(mapa)} mides)")

    print(f"fet: {len(MIDES) + 4} fitxers a icona/")


if __name__ == "__main__":
    main()
