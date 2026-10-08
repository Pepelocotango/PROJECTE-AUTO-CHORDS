#!/usr/bin/env bash
# instal·la_local.sh — deixa el projecte llest SENSE sudo ni apt.
# Crea .venv/ (aïllat) + pip install PyQt5 + verifica binaris i headers.
# Ús: bash instal·la_local.sh
set -euo pipefail
cd "$(dirname "$0")"

echo "== 1/4 venv =="
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "== 2/4 Python =="
.venv/bin/python -c "from PyQt5.QtCore import QT_VERSION_STR; print('PyQt5 Qt', QT_VERSION_STR)"
.venv/bin/python -m py_compile acords_a_live.py wav_a_wavs.py app/main.py app/pipeline.py
echo "py_compile OK"

echo "== 3/4 binaris (lectura, sense instal·lar) =="
for b in OLD/sonic-annotator nnls-chroma-linux64-local/nnls-chroma.so; do
  if [ -f "$b" ]; then
    falt=$(ldd "$b" 2>/dev/null | grep "not found" || true)
    if [ -n "$falt" ]; then
      echo "AVÍS: a $b li falten llibreries del sistema (Ubuntu 24.04 les porta):"
      echo "$falt"
    else
      echo "$b: llibreries OK"
    fi
  else
    echo "AVÍS: no trobo $b"
  fi
done

echo "== 4/4 headers C++ (via .deps/, sense apt install ni sudo) =="
mkdir -p .deps
cd .deps
for pkg in libboost1.83-dev vamp-plugin-sdk libsndfile1-dev; do
  if ! ls "${pkg}"_*.deb >/dev/null 2>&1; then
    apt-get download "$pkg"
  fi
  for deb in "${pkg}"_*.deb; do
    [ -f "$deb" ] && dpkg-deb -x "$deb" .
  done
done
cd ..
for h in .deps/usr/include/boost/tokenizer.hpp .deps/usr/include/vamp-hostsdk/PluginInputDomainAdapter.h .deps/usr/include/sndfile.h; do
  if [ -f "$h" ]; then echo "$h: OK"; else echo "FALTA: $h"; fi
done

echo "== 5/5 chordextract local (prova, sense substituir l'annotator) =="
if [ -f .deps/usr/include/boost/tokenizer.hpp ]; then
  (cd codi_font_chordino && g++ -D_VAMP_PLUGIN_IN_HOST_NAMESPACE -O2 -ffast-math \
    -I../.deps/usr/include chordextract.cpp Chordino.cpp NNLSBase.cpp \
    chromamethods.cpp viterbi.cpp nnls.c -o ${AUTO_CHORDS_TEMP:-temp}/chordextract \
    -L../.deps/usr/lib/x86_64-linux-gnu -lsndfile -lvamp-hostsdk -ldl \
    -Wl,-rpath,${AUTO_CHORDS_TEMP:-temp} 2>&1 | head -10 && echo "chordextract: compilat a ${AUTO_CHORDS_TEMP:-temp}/chordextract") || \
    echo "AVÍS: chordextract no ha compilat (via annotator intacta)"
else
  echo "chordextract: pendent headers (.deps incomplet, sense xarxa apt?)"
fi

echo ""
echo "FET ✅ — sense tocar el sistema. Obre amb:"
echo "  .venv/bin/python app/main.py"
echo "  .venv/bin/python wav_a_wavs.py --help"
