#!/usr/bin/env bash
# Crea el Python portable (Fase 2 de portabilitat) dins portable/python/.
# Usa python-build-standalone, build GENÈRIC x86_64 (sense AVX: el _v2
# demanaria SSE4.2 i faria SIGILL al Q9400).
set -e
cd "$(dirname "$0")/.."
PYV="3.12.15"
TAG="20261003"
URL="https://github.com/astral-sh/python-build-standalone/releases/latest/download"
FILE="cpython-${PYV}%2B${TAG}-x86_64-unknown-linux-gnu-install_only.tar.gz"

mkdir -p portable
echo "Baixant el CPython portable..."
curl -sfL -o /tmp/pyport.tar.gz "$URL/$FILE" || {
    echo "ERROR: no he pogut baixar el CPython portable ($URL/$FILE)" >&2; exit 1; }
tar xzf /tmp/pyport.tar.gz -C portable/
PY=./portable/python/bin/python3
echo "Instal·lant PyQt5 + numpy<2..."
$PY -m pip install --no-cache-dir --quiet "numpy<2" "PyQt5==5.15.11" \
    "PyQt5-Qt5==5.15.19" "PyQt5_sip"
echo "Retocant (treure qml/translations/pip: no s'usen)..."
$PY -m pip uninstall -y pip setuptools 2>/dev/null || true
Q=portable/python/lib/python3.12/site-packages/PyQt5/Qt5
for d in qml translations qsci; do [ -d "$Q/$d" ] && gio trash "$Q/$d" || true; done
find portable -name "__pycache__" -type d -exec gio trash {} \; 2>/dev/null || true
echo "Baixant ffmpeg estàtic (johnvansickle: ~40 MB comprimit)..."
curl -sfL -o /tmp/ff.tar.xz \
  "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz" || {
    echo "ERROR: no he pogut baixar ffmpeg" >&2; exit 1; }
tar xJf /tmp/ff.tar.xz -C /tmp/
FFDIR=$(ls -d /tmp/ffmpeg-*-amd64-static | head -1)
mkdir -p portable/bin
cp "$FFDIR/ffmpeg" portable/bin/ffmpeg   # només ffmpeg (ffprobe no s'usa)
echo "Llibreries natives de l'host Vamp (autoportabilitat)..."
[ -x vamp_host_local ] || ./eines/compila_vamp_host.sh
./eines/libreries_natives.sh
echo "Fet. Mida: $(du -sh portable | cut -f1)"
