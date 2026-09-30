#!/usr/bin/env bash
# instal·la_vm_debian.sh — Deixa la VM Debian (Mac) llesta per l'Auto Chords.
# S'executa DINS la VM (Xfce): bash instal·la_vm_debian.sh
# Demana 1 pkexec (diàleg). Només llibreries d'execució: no compila res
# (els binaris ja venen fets al disc compartit).
set -euo pipefail

echo "== 1/2 llibreries (pkexec) =="
pkexec apt-get update
pkexec apt-get install -y python3-pyqt5 \
  libqt6core6t64 libqt6network6 libqt6xml6 libqt6test6 \
  libsndfile1 libsamplerate0 libfftw3-double3 \
  libsord-0-0 libserd-0-0 liboggz2 libfishsound1 libmad0 libid3tag0 \
  libopusfile0 libvamp-hostsdk3t64

echo "== 2/2 verificació =="
# > [2026-09-30] [SPARK] (trasllat a ~/0PROJECTES_GitHub: ja no és al disc
# > compartit exFAT; la VM/Mac no hi accedeix. Aquest script només té sentit
# > si el projecte torna a l'exFAT o es copia la carpeta a la VM.)
PROJ="/home/peplx/0PROJECTES_GitHub/PROJECTE AUTO CHORDS"
python3 -c "from PyQt5.QtCore import QT_VERSION_STR; print('PyQt5 Qt', QT_VERSION_STR)"
ldd "$PROJ/sonic-annotator" | grep -i "not found" \
  && echo "FALTEN llibreries (passa'm la línia)" \
  || echo "sonic-annotator: totes les llibreries OK"
python3 -c "import ctypes; ctypes.CDLL('$PROJ/nnls-chroma-linux64-local/nnls-chroma.so'); print('Chordino .so OK')"

echo ""
echo "FET ✅ — obre l'app amb:"
echo "  python3 \"$PROJ/app/main.py\""
