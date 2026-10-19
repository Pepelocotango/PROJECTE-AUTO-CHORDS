"""Genera la icona de l'aplicació (finestra + .desktop + AppImage + Windows + macOS).

Renderitza el logo vectorial `icona/auto-chords-logo.svg` a PNG (diverses
mides) i, a més, en deriva el format propi de cada sistema:
  · Linux   -> els PNG (els fan servir el .desktop, l'AppImage i la finestra)
  · Windows -> `auto-chords.ico`  (16–128 en BMP/DIB + 256 en PNG)
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
# Windows 10/11: 16, 20, 24, 32, 40, 48, 64, 128 (BMP) i 256 (PNG).
MIDES_ICO = (16, 20, 24, 32, 40, 48, 64, 128, 256)

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


def _packbits(dades):
    """RLE PackBits de l'ICNS (el mateix que fan servir `ic04`/`ic05`).

    · Control < 0x80  -> literals: els `control + 1` bytes següents (1..128).
    · Control >= 0x80 -> repetició: el byte següent, `control - 125` cops
      (3..130). Una repetició de 2 no és representable: va com a literal.
    """
    out = bytearray()
    n = len(dades)
    i = 0
    while i < n:
        run = 1
        while i + run < n and dades[i + run] == dades[i] and run < 130:
            run += 1
        if run >= 3:
            # 3..130 -> control 128..255 (control - 125 = longitud).
            out.append(0x80 | (run - 3))
            out.append(dades[i])
            i += run
            continue
        literal = bytearray()
        while i < n and len(literal) < 128:
            # No comencem un literal si al davant hi ha una repetició de 3+.
            ahead = 1
            while (i + ahead < n and dades[i + ahead] == dades[i]
                   and ahead < 3):
                ahead += 1
            if ahead >= 3:
                break
            literal.append(dades[i])
            i += 1
        out.append(len(literal) - 1)
        out.extend(literal)
    return bytes(out)


def _dib(mida):
    """Bloc BMP/DIB 32-bit (BGRA + AND mask) per a l'ICO de Windows.

    Microsoft recomana **BMP** per a les mides < 256 i PNG només per a 256.
    El DIB de l'ICO no porta la capçalera de fitxer BMP: comença directament
    pel `BITMAPINFOHEADER` de 40 bytes, amb `biHeight = 2·mida` (píxels + màscara),
    píxels **BGRA de baix a dalt** i una màscara AND d'1 bit per píxel (1 =
    transparent), amb cada fila alineada a 32 bits.
    """
    img = _render(mida)
    xor = bytearray()
    for y in range(mida - 1, -1, -1):
        for x in range(mida):
            c = img.pixelColor(x, y)
            if c.alpha() == 0:
                xor += b"\x00\x00\x00\x00"
            else:
                xor += bytes((c.blue(), c.green(), c.red(), c.alpha()))
    files_mask = ((mida + 31) // 32) * 4
    mask = bytearray()
    for y in range(mida - 1, -1, -1):
        fila = bytearray(files_mask)
        for x in range(mida):
            if img.pixelColor(x, y).alpha() == 0:
                fila[x // 8] |= 0x80 >> (x % 8)
        mask.extend(fila)
    capcalera = struct.pack(
        "<IiiHHIIiiII",
        40,              # biSize
        mida,            # biWidth
        mida * 2,        # biHeight (XOR + AND mask)
        1,               # biPlanes
        32,              # biBitCount
        0,               # biCompression = BI_RGB
        mida * mida * 4,  # biSizeImage
        0, 0, 0, 0,      # ppm X/Y, colors usats/importants
    )
    return bytes(capcalera + xor + mask)


def _argb(mida):
    """Bloc ARGB+RLE per a les mides petites de l'ICNS (`ic04`/`ic05`).

    macOS **no dibuixa bé** els PNG de 16/32 px dins dels blocs `icp4`/`icp5`
    (Finder/DMG els ensenya com a soroll; el Dock i l'app instal·lada, que
    agafen mides grans, es veuen bé). Apple's `iconutil` escriu aquestes dues
    mides com a ARGB amb RLE PackBits per canal: magic `ARGB` + canals
    **A, R, G, B** (RGB sense premultiplicar).
    """
    img = _render(mida)
    canals = [bytearray() for _ in range(4)]   # A, R, G, B
    for y in range(mida):
        for x in range(mida):
            c = img.pixelColor(x, y)
            canals[0].append(c.alpha())
            canals[1].append(c.red())
            canals[2].append(c.green())
            canals[3].append(c.blue())
    return b"ARGB" + b"".join(_packbits(bytes(c)) for c in canals)


def _escriu_ico(desti, imatges):
    """ICO (Windows): capçalera + directori + imatges (PNG o BMP/DIB)."""
    n = len(imatges)
    cap = struct.pack("<HHH", 0, 1, n)          # reserved, type=icon, count
    offset = 6 + 16 * n
    entrades, dades = b"", b""
    for mida, d in sorted(imatges):
        w = h = 0 if mida >= 256 else mida      # 0 = 256 px (conveni ICO)
        entrades += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(d), offset)
        offset += len(d)
        dades += d
    with open(desti, "wb") as f:
        f.write(cap + entrades + dades)


def _escriu_icns(desti, mapa):
    """ICNS (macOS): magic 'icns' + mida total + blocs [tipus + mida + dades]."""
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
    #    BMP/DIB per a 16–128 (recomanació de Microsoft) i PNG per a 256.
    _escriu_ico(os.path.join(DESTI, "auto-chords.ico"),
                [(m, _png(m) if m >= 256 else _dib(m))
                 for m in MIDES_ICO])
    print(f"  ✓ auto-chords.ico ({len(MIDES_ICO)} mides: "
          "BMP 16–128 + PNG 256)")

    # 3) macOS: .icns.
    #    · ic04/ic05: 16/32 px en ARGB+RLE, com `iconutil` (PNG en `icp4`/
    #      `icp5`/`icp6` es veu CORRUPTE al Finder/DMG a 1×).
    #    · ic07..ic14: PNG (128, 256, 512, 1024 i les seues versions @2x).
    mapa = [
        (b"ic04", _argb(16)),
        (b"ic05", _argb(32)),
        (b"ic07", _png(128)),
        (b"ic08", _png(256)),
        (b"ic09", _png(512)),
        (b"ic10", _png(1024)),
        (b"ic11", _png(32)),
        (b"ic12", _png(64)),
        (b"ic13", _png(256)),
        (b"ic14", _png(512)),
    ]
    _escriu_icns(os.path.join(DESTI, "auto-chords.icns"), mapa)
    print(f"  ✓ auto-chords.icns ({len(mapa)} mides)")

    print(f"fet: {len(MIDES) + 4} fitxers a icona/")


if __name__ == "__main__":
    main()
