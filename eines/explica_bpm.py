#!/usr/bin/env python3
"""Genera un gràfic explicatiu de com app/tempo.py detecta el BPM.

Ús: .venv/bin/python eines/explica_bpm.py <wav> <sortida.png>
"""
import os
import sys

import numpy as np
from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QImage, QPainter, QPen
from PyQt5.QtWidgets import QApplication

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import tempo  # noqa: E402

W, H = 1400, 1080
BG = QColor("#14171c")
FG = QColor("#e8edf5")
MUTED = QColor("#9aa6b8")
GRID = QColor("#2a2f37")
ACC = QColor("#38bdf8")
ACC2 = QColor("#4ade80")
WARN = QColor("#ffd166")


def panell(p, x, y, w, h, titol, sub=""):
    p.setPen(QPen(GRID, 1))
    p.setBrush(QColor("#0f1218"))
    p.drawRect(x, y, w, h)
    p.setPen(FG)
    f = QFont(); f.setPointSize(12); f.setBold(True); p.setFont(f)
    p.drawText(x + 8, y + 19, titol)
    if sub:
        p.setPen(MUTED)
        f.setPointSize(9); f.setBold(False); p.setFont(f)
        p.drawText(x + 8, y + 34, sub)


def linia(p, pts, color, ample=1.4):
    p.setPen(QPen(color, ample))
    for i in range(len(pts) - 1):
        p.drawLine(QPointF(*pts[i]), QPointF(*pts[i + 1]))


def main():
    wav = sys.argv[1]
    out = sys.argv[2]
    _ = QApplication(sys.argv)  # referència viva de QApplication per a Qt (_ l'ignora pyflakes)

    env, sr = tempo._envolupant_onsets(wav)
    bpm = tempo._comb_bpm(env)
    ac = np.correlate(env, env, "full")[env.size - 1:]
    ac = ac / ac[0] if ac[0] > 0 else ac

    img = QImage(W, H, QImage.Format_RGB32)
    img.fill(BG)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)

    f = QFont(); f.setPointSize(16); f.setBold(True); p.setFont(f)
    p.setPen(FG)
    p.drawText(20, 34, "Com es detecta el BPM  ·  app/tempo.py")
    f.setPointSize(10); f.setBold(False); p.setFont(f)
    p.setPen(MUTED)
    p.drawText(20, 54, f"{os.path.basename(wav)}  ·  {bpm:.1f} BPM detectat")

    # ---- 1) envolupant ----
    x, y, w, h = 20, 80, W - 40, 190
    panell(p, x, y, w, h, "1. Envolupant d'onsets (flux espectral, passos de 10 ms)",
           "cada cop que l'energia CRECX = un atac (pua, cop de bateria...). "
           "El silenci inicial es treu.")
    e = env / (env.max() or 1)
    pts = [(x + 4 + (w - 8) * i / max(1, len(e) - 1), y + h - 6 - (h - 40) * max(0, v))
           for i, v in enumerate(e)]
    linia(p, pts, ACC)
    p.setPen(MUTED); p.setFont(f)
    p.setPen(MUTED); p.setFont(f)
    p.drawText(x + 8, y + h - 24, f"{len(e)} fotogrames  ({len(e)*0.01:.1f} s)")

    # ---- 2) zoom + periode ----
    y2 = y + h + 20
    panell(p, x, y2, w, h, "2. Zoom (2 s) amb el PERÍODE detectat",
           "cada línia verda = un temps del BPM detectat")
    z = e[200:400]
    pts = [(x + 4 + (w - 8) * i / max(1, len(z) - 1), y2 + h - 6 - (h - 40) * max(0, v))
           for i, v in enumerate(z)]
    linia(p, pts, ACC, 1.6)
    per = int(round((60.0 / bpm) / 0.01))
    k = 0
    while 200 + k < 400:
        px = x + 4 + (w - 8) * k / max(1, len(z) - 1)
        p.setPen(QPen(ACC2, 1, Qt.DashLine))
        p.drawLine(QPointF(px, y2 + 30), QPointF(px, y2 + h - 6))
        k += per

    # ---- 3) autocorrelacio ----
    y3 = y2 + h + 20
    panell(p, x, y3, w, h, "3. Autocorrelació de l'envolupant",
           "pics = periodicitats fortes (temps, i els seus múltiples)")
    n = min(int(3.0 / 0.01), ac.size)          # fins a 3 s de retard
    a = ac[:n]
    lo, hi = float(a.min()), float(a.max())
    rng = (hi - lo) or 1.0
    pts = [(x + 4 + (w - 8) * i / max(1, n - 1), y3 + h - 6 - (h - 40) * (v - lo) / rng)
           for i, v in enumerate(a)]
    linia(p, pts, ACC)
    lag = (60.0 / bpm) / 0.01
    for m, col in ((1, ACC2), (2, WARN), (3, MUTED), (4, MUTED)):
        L = lag * m
        if L >= n:
            break
        px = x + 4 + (w - 8) * L / max(1, n - 1)
        p.setPen(QPen(col, 1, Qt.DashLine))
        p.drawLine(QPointF(px, y3 + 30), QPointF(px, y3 + h - 6))
        p.setPen(col); p.setFont(f)
        p.drawText(QPointF(px + 3, y3 + 46 + 14 * (m - 1)), f"x{m} ({m*60/bpm:.2f}s)")

    # ---- 4) puntuacio comb ----
    y4 = y3 + h + 20
    panell(p, x, y4, w, 210,
           f"4. Puntuació «comb» per a cada BPM (la guanyadora = {bpm:.1f})",
           "per a cada BPM es mira l'autocorrelació al seu període I als múltiples "
           "(1,2,3,4). La zona verda (80-160) no rep càstig (plateau del prior).")
    bmps = np.arange(60, 180, 0.25)
    scs = []
    for b in bmps:
        lg = (60.0 / b) / 0.01
        if lg < 1 or lg >= ac.size:
            scs.append(0.0); continue
        s = 0.0
        for m in (1, 2, 3, 4):
            L = lg * m
            if L >= ac.size:
                break
            i = int(L); fr = L - i
            v = ac[i] * (1 - fr) + ac[i + 1] * fr if i + 1 < ac.size else ac[i]
            s += v / m
        s *= tempo._prior(b, tempo.BPM_PREFERIT)
        scs.append(s)
    scs = np.array(scs)
    lo, hi = float(scs.min()), float(scs.max())
    rng = (hi - lo) or 1.0
    # zona preferida
    xa = x + 4 + (w - 8) * (80 - 60) / 120
    xb = x + 4 + (w - 8) * (160 - 60) / 120
    p.setPen(Qt.NoPen); p.setBrush(QColor("#16301f"))
    p.drawRect(QRectF(xa, y4 + 44, xb - xa, 210 - 56))
    pts = [(x + 4 + (w - 8) * (b - 60) / 120, y4 + 210 - 8 - (210 - 58) * (v - lo) / rng)
           for b, v in zip(bmps, scs)]
    linia(p, pts, ACC, 1.4)
    px = x + 4 + (w - 8) * (bpm - 60) / 120
    p.setPen(QPen(WARN, 2)); p.drawLine(QPointF(px, y4 + 44), QPointF(px, y4 + 210 - 8))
    p.setPen(WARN); f2 = QFont(); f2.setPointSize(11); f2.setBold(True); p.setFont(f2)
    p.drawText(QPointF(px + 4, y4 + 66), f"{bpm:.1f} BPM")
    p.setPen(MUTED); f2.setBold(False); p.setFont(f2)
    p.drawText(x + 8, y4 + 210 - 8, "60 BPM")
    p.drawText(x + w - 90, y4 + 210 - 8, "180 BPM")

    p.end()
    img.save(out)
    print(f"OK -> {out}  ({bpm:.1f} BPM)")


if __name__ == "__main__":
    main()
