#!/usr/bin/env bash
# compila_vamp_plugins.sh — Recompila els plugins Vamp (nnls-chroma + qm-vamp-plugins)
# DES DEL CODI FONT, al MATEIX entorn on es construeix l'AppImage.
#
# PER QUÈ: els .so precompilats (fets a Ubuntu 24.04 / GCC 13) demanaven
# GLIBCXX_3.4.32 i símbols de glibc 2.38 (__isoc23_*) -> no carregaven ni al
# runner (jammy, GCC 11) ni a un destí Ubuntu 22.04. Compilant-los AQUÍ, queden
# ancorats a la glibc/GCC del runner (2.35 / GCC 11), l'abast mínim de l'AppImage.
#
# REQUISITS (apt): vamp-plugin-sdk libboost-dev libsndfile1-dev
#   (+ eines: g++ make git curl)
# OPCIONAL (per proves): NNLS_OUT / QM_OUT canvien la carpeta de sortida.
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"
NNLS_OUT="${NNLS_OUT:-$ROOT/nnls-chroma-linux64-local}"
QM_OUT="${QM_OUT:-$ROOT/qm-vamp-plugins-linux64-local}"
WORK="$(mktemp -d -t ac_vamp_plugins.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT

# --- comprovacions ---
for t in g++ make git curl; do
    command -v "$t" >/dev/null || { echo "ERROR: falta l'eina '$t'"; exit 1; }
done
INC_SRC="/usr/include"
LIB_SRC="/usr/lib/x86_64-linux-gnu"
[ -d .deps/usr/include/vamp-sdk ] && INC_SRC="$ROOT/.deps/usr/include"
[ -f .deps/usr/lib/libvamp-sdk.so ] && LIB_SRC="$ROOT/.deps/usr/lib"
# boost: pot venir del sistema (/usr/include) o de .deps (apt download)
BOOST_INC="/usr/include"
[ -d "$INC_SRC/boost" ] && BOOST_INC="$INC_SRC"
if [ ! -d "$INC_SRC/vamp-sdk" ]; then
    echo "ERROR: falten headers de Vamp ($INC_SRC/vamp-sdk). Instal·la 'vamp-plugin-sdk'." >&2
    exit 1
fi
if [ ! -d "$BOOST_INC/boost" ]; then
    echo "ERROR: falten headers de boost. Instal·la 'libboost-dev'." >&2
    exit 1
fi

# ===== 1) nnls-chroma (Chordino) =====
echo "== [1/2] nnls-chroma (Chordino) =="
# El Makefile espera un sol directori amb els headers (vamp-sdk/) I el .so.
SDK="$WORK/vamp-sdk"
mkdir -p "$SDK"
ln -sf "$INC_SRC/vamp-sdk" "$SDK/vamp-sdk"
ln -sf "$INC_SRC/vamp-hostsdk" "$SDK/vamp-hostsdk"
ln -sf "$LIB_SRC/libvamp-sdk.so" "$SDK/libvamp-sdk.so"

make -C codi_font_chordino -f Makefile.linux clean >/dev/null 2>&1 || true
# boost: symlink SENSE espais dins $WORK (el path del projecte en pot tenir,
# i el Makefile passa -I$(BOOST_ROOT) sense cometes -> es trencaria).
ln -sfn "$BOOST_INC/boost" "$WORK/boost"
# --eval='.SECONDARY:': sense això GNU make esborra els .o com a intermedis
# abans del link i aquest falla ("cannot find XXX.o").
make -C codi_font_chordino -f Makefile.linux --eval='.SECONDARY:' \
    VAMP_SDK_DIR="$SDK" BOOST_ROOT="$WORK"
mkdir -p "$NNLS_OUT"
mv -f codi_font_chordino/nnls-chroma.so "$NNLS_OUT/nnls-chroma.so"
make -C codi_font_chordino -f Makefile.linux clean >/dev/null 2>&1 || true
echo "   -> $NNLS_OUT/nnls-chroma.so"

# ===== 2) qm-vamp-plugins (Queen Mary) =====
echo "== [2/2] qm-vamp-plugins (Queen Mary) =="
cd "$WORK"
curl -sL -o qm.tar.gz \
    https://github.com/c4dm/qm-vamp-plugins/archive/refs/heads/master.tar.gz
tar xzf qm.tar.gz
cd qm-vamp-plugins-master
mkdir -p lib
git clone --depth 1 -q https://github.com/c4dm/qm-dsp lib/qm-dsp
git clone --depth 1 -q https://github.com/c4dm/vamp-plugin-sdk lib/vamp-plugin-sdk
make -C lib/qm-dsp -f build/linux/Makefile.linux64
make -f build/linux/Makefile.linux64
mkdir -p "$QM_OUT"
cp -f qm-vamp-plugins.so "$QM_OUT/qm-vamp-plugins.so"
[ -f qm-vamp-plugins.cat ] && cp -f qm-vamp-plugins.cat "$QM_OUT/qm-vamp-plugins.cat"
[ -f qm-vamp-plugins.n3 ] && cp -f qm-vamp-plugins.n3 "$QM_OUT/qm-vamp-plugins.n3"
echo "   -> $QM_OUT/qm-vamp-plugins.so"

# ===== resum: GLIBCXX máxim que demana cada .so =====
echo "== Fet =="
for so in "$NNLS_OUT/nnls-chroma.so" "$QM_OUT/qm-vamp-plugins.so"; do
    v=$(readelf -V "$so" 2>/dev/null | grep -oE 'GLIBCXX_[0-9.]+' | sort -uV | tail -1)
    echo "   $(basename "$so"): GLIBCXX max = ${v:-cap}"
done
