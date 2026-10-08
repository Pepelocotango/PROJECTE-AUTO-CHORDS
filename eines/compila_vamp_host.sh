#!/usr/bin/env bash
# Compila l'host Vamp propi (vamp_host_local).
# Depèn de: vamp-plugin-sdk + libsndfile (headers del sistema, .deps o $PREFIX).
# Flags -msse -msse2: SENSE AVX (Q9400 i altres CPUs antigues).
#
# Multi-SO (mateix script per a tots): Linux, macOS (10.13+) i Windows (MSYS2).
#   · Linux   -> vamp_host_local      (+ -ldl i comprovació amb ldd)
#   · macOS   -> vamp_host_local      (natius a $PREFIX via CPATH/LIBRARY_PATH;
#                                      comprovació amb otool)
#   · Windows -> vamp_host_local.exe  (MINGW64; comprovació amb objdump)
set -e
cd "$(dirname "$0")/.."

case "$(uname -s)" in
    Darwin)               SO="mac"   ;;
    MINGW*|MSYS*|CYGWIN*) SO="win"   ;;
    *)                    SO="linux" ;;
esac

INC=""
LIBS="-lvamp-hostsdk -lsndfile"
case "$SO" in
    linux)
        [ -d .deps/usr/include ] && INC="-I.deps/usr/include"
        LIBS="$LIBS -ldl"          # -ldl NO existeix ni a macOS ni a Windows
        ;;
    mac)
        # Els natius (libvamp-hostsdk, libsndfile) els construeix el workflow a
        # $PREFIX. Si hi és, l'hi apuntem explícitament (a més de CPATH/LIBRARY_PATH).
        [ -n "${PREFIX:-}" ] && INC="-I$PREFIX/include -L$PREFIX/lib"
        ;;
esac
LIBS="$LIBS -lpthread -lm"

CXX="${CXX:-g++}"
EXT=""
[ "$SO" = "win" ] && EXT=".exe"

echo "Compilant vamp_host_local$EXT ($SO)..."
$CXX -O2 -msse -msse2 -mfpmath=sse -ftree-vectorize $INC \
    -o "vamp_host_local$EXT" eines/vamp_host.cpp $LIBS

echo "Fet: $(du -h "vamp_host_local$EXT" | cut -f1)"
case "$SO" in
    mac)  otool -L "vamp_host_local$EXT" | tail -n +2 | awk '{print "  "$1}' ;;
    win)  objdump -p "vamp_host_local$EXT" | awk '/DLL Name/{print "  "$3}' ;;
    *)    ldd "vamp_host_local$EXT" | grep '=>' | awk '{print "  "$1}' ;;
esac
