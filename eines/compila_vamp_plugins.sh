#!/usr/bin/env bash
# compila_vamp_plugins.sh — Recompila els plugins Vamp (nnls-chroma + qm-vamp-plugins)
# al MATEIX entorn on es construeix el paquet. DETECTA EL SO TOT SOL (uname):
#
#   · Linux   -> nnls-chroma-linux64-local/ + qm-vamp-plugins-linux64-local/ (.so)
#   · Windows -> nnls-chroma-win64-local/  + qm-vamp-plugins-win64-local/  (.dll)
#                + vamp_host_local.exe   (MSYS2 / MINGW64)
#   · macOS   -> nnls-chroma-macos-local/  + qm-vamp-plugins-macos-local/  (.dylib)
#                (target 10.13, x86_64; el host el fa compila_vamp_host.sh)
#
# PER QUÈ (Linux): els .so precompilats (fets a Ubuntu 24.04 / GCC 13) demanaven
# GLIBCXX_3.4.32 i símbols de glibc 2.38 (__isoc23_*) -> no carregaven ni al
# runner (jammy, GCC 11) ni a un destí Ubuntu 22.04. Compilant-los AQUÍ, queden
# ancorats a la glibc/GCC del runner (2.35 / GCC 11), l'abast mínim de l'AppImage.
#
# REQUISITS Linux (apt): vamp-plugin-sdk libboost-dev libsndfile1-dev
#   (+ eines: g++ make git curl)
# REQUISITS Windows (MSYS2 MINGW64): mingw-w64-x86_64-gcc, -vamp-plugin-sdk,
#   -libsndfile, -boost (+ curl, unzip, binutils)
# REQUISITS macOS: Xcode CLT (clang), curl + els natius de suport a $PREFIX
#   (vamp-plugin-sdk: headers a $PREFIX/include/vamp-sdk i libvamp-sdk.a a
#   $PREFIX/lib; libsndfile només cal per al host). Boost: headers (brew).
#
# OPCIONAL (per proves): NNLS_OUT / QM_OUT canvien la carpeta de sortida.
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"

# ===========================================================================
#  BRANCA WINDOWS (MSYS2 / MINGW64)
# ===========================================================================
compila_windows() {
    echo "== compila_vamp_plugins.sh: branca WINDOWS (MINGW64) =="
    PREFIX="${MINGW_PREFIX:-/mingw64}"
    INC="$PREFIX/include"
    LIB="$PREFIX/lib"
    BIN="$PREFIX/bin"
    NNLS_OUT="${NNLS_OUT:-$ROOT/nnls-chroma-win64-local}"
    QM_OUT="${QM_OUT:-$ROOT/qm-vamp-plugins-win64-local}"
    # Clausura de DLLs de runtime (libsndfile + còdecs + runtimes MinGW). PyInstaller
    # les copia al costat de vamp_host_local.exe (_internal/), on Windows les troba.
    WIN_DLLS="${WIN_DLLS:-$ROOT/portable/win-dlls}"
    WORK="$(mktemp -d -t ac_vamp_win.XXXXXX)"
    trap 'rm -rf "$WORK"' EXIT

    # Cal make+git: el qm-vamp-plugins es compila des de font (+ qm-dsp i
    # vamp-plugin-sdk que es clonen).
    for t in g++ gcc make git curl objdump; do
        command -v "$t" >/dev/null || { echo "ERROR: falta l'eina '$t'"; exit 1; }
    done
    [ -d "$INC/vamp-sdk" ] || {
        echo "ERROR: falten headers de Vamp ($INC/vamp-sdk). Instal·la 'mingw-w64-x86_64-vamp-plugin-sdk'." >&2
        exit 1
    }
    [ -f "$LIB/libvamp-sdk.a" ] || {
        echo "ERROR: falta $LIB/libvamp-sdk.a (paquet mingw-w64-x86_64-vamp-plugin-sdk)." >&2
        exit 1
    }
    [ -f "$LIB/libvamp-hostsdk.a" ] || {
        echo "ERROR: falta $LIB/libvamp-hostsdk.a (paquet mingw-w64-x86_64-vamp-plugin-sdk)." >&2
        exit 1
    }
    [ -d "$INC/boost" ] || {
        echo "ERROR: falten headers de boost ($INC/boost). Instal·la 'mingw-w64-x86_64-boost'." >&2
        exit 1
    }

    mkdir -p "$NNLS_OUT" "$QM_OUT" "$WIN_DLLS"

    # --- 1) nnls-chroma / Chordino (.dll self-contained) -------------------
    # Receta provada (mingw-w64): compilar les fonts + .def d'export i enllaçar
    # libgcc/libstdc++ ESTÀTICS -> només KERNEL32/msvcrt com a dependències.
    echo "== [1/3] nnls-chroma (Chordino) win64 =="
    (
        cd codi_font_chordino
        rm -f ./*.o nnls-chroma.dll
        FLAGS="-O2 -DNDEBUG -ffast-math -msse -msse2 -I$INC"
        gcc  $FLAGS -c nnls.c -o nnls.o
        for f in NNLSBase NNLSChroma Chordino Tuning chromamethods viterbi plugins; do
            g++ $FLAGS -c "$f.cpp" -o "$f.o"
        done
        printf 'EXPORTS\nvampGetPluginDescriptor\n' > nnls-chroma.def
        g++ -shared -o nnls-chroma.dll ./*.o nnls-chroma.def \
            -static -static-libgcc -static-libstdc++ \
            -L"$LIB" -lvamp-sdk -Wl,--enable-stdcall-fixup
        cp -f nnls-chroma.dll nnls-chroma.cat nnls-chroma.n3 "$NNLS_OUT/"
    )
    if ! objdump -p "$NNLS_OUT/nnls-chroma.dll" | grep -q vampGetPluginDescriptor; then
        echo "ERROR: nnls-chroma.dll no exporta vampGetPluginDescriptor" >&2
        exit 1
    fi
    echo "   -> $NNLS_OUT/nnls-chroma.dll"

    # --- 2) qm-vamp-plugins (COMPILAT des de font) -------------------------
    # PER QUÈ NO el binari oficial win64: els que hi ha (oficial/mirrors) depenen
    # de `libblas.dll`/`liblapack.dll` i, en alguns casos, del runtime **DEBUG**
    # de MSVC (MSVCP140D/ucrtbased) -> LoadLibrary falla amb error 126
    # (MOD_NOT_FOUND) i no és empaquetable. Compilant-lo aquí amb els
    # clapack/cblas INCLOSOS (com al Linux) queda autocontingut: només runtime
    # MinGW, que ja recollim a portable/win-dlls.
    echo "== [2/3] qm-vamp-plugins win64 (des de font) =="
    (
        cd "$WORK"
        curl -sL --retry 3 -o qm.tar.gz \
            https://github.com/c4dm/qm-vamp-plugins/archive/refs/heads/master.tar.gz
        tar xzf qm.tar.gz
        cd qm-vamp-plugins-master
        mkdir -p lib
        git clone --depth 1 -q https://github.com/c4dm/qm-dsp lib/qm-dsp
        git clone --depth 1 -q https://github.com/c4dm/vamp-plugin-sdk lib/vamp-plugin-sdk
        # -D_USE_MATH_DEFINES: el Makefile compila amb -std=c++98 (ANSI
        # estricte) i a MinGW M_PI no es defineix -> error a
        # base/KaiserWindow.h:76. El passem via CXX/CC (sobreescriu el `?=` del
        # Makefile sense perdre cap altra bandera; al Linux no cal).
        MCXX="g++ -D_USE_MATH_DEFINES"; MCC="gcc -D_USE_MATH_DEFINES"
        make -C lib/qm-dsp -f build/linux/Makefile.linux64 CXX="$MCXX" CC="$MCC"
        # Enllaç propi per a Windows: res de --version-script (ELF) i .def per
        # exportar només el símbol que busca el host; runtime MinGW estàtic.
        printf 'EXPORTS\nvampGetPluginDescriptor\n' > qm-vamp-plugins.def
        make -f build/linux/Makefile.linux64 PLUGIN_EXT=.dll CXX="$MCXX" CC="$MCC" \
            LDFLAGS="-shared -static -static-libgcc -static-libstdc++ -lpthread qm-vamp-plugins.def"
        cp -f qm-vamp-plugins.dll "$QM_OUT/qm-vamp-plugins.dll"
        [ -f qm-vamp-plugins.cat ] && cp -f qm-vamp-plugins.cat "$QM_OUT/"
        [ -f qm-vamp-plugins.n3 ] && cp -f qm-vamp-plugins.n3 "$QM_OUT/"
    )
    if ! objdump -p "$QM_OUT/qm-vamp-plugins.dll" | grep -q vampGetPluginDescriptor; then
        echo "ERROR: qm-vamp-plugins.dll no exporta vampGetPluginDescriptor" >&2
        exit 1
    fi
    echo "   -> $QM_OUT/qm-vamp-plugins.dll"

    # --- 3) host Vamp propi (vamp_host_local.exe) --------------------------
    echo "== [3/3] host Vamp (vamp_host_local.exe) =="
    g++ -O2 -DNDEBUG -msse -msse2 -mfpmath=sse -ftree-vectorize \
        -I"$INC" -o vamp_host_local.exe eines/vamp_host.cpp \
        -L"$LIB" -Wl,-Bstatic -lvamp-hostsdk -Wl,-Bdynamic -lsndfile \
        -static-libgcc -static-libstdc++

    # Clausura de dependències no-sistema del host (recursiva). Només copiem
    # les DLLs que existeixen al prefix de MinGW; la resta són del sistema.
    recull_dlls() {
        local bin="$1" dll
        for dll in $(objdump -p "$bin" | awk '/DLL Name/ {print $3}'); do
            [ -f "$WIN_DLLS/$dll" ] && continue
            if [ -f "$BIN/$dll" ]; then
                cp -f "$BIN/$dll" "$WIN_DLLS/"
                recull_dlls "$BIN/$dll"
            fi
        done
    }
    recull_dlls vamp_host_local.exe
    # Runtimes MinGW que poden necessitar els plugins (.dll), encara que el host
    # els porti estàtics.
    for d in libgcc_s_seh-1.dll libstdc++-6.dll libwinpthread-1.dll; do
        [ -f "$BIN/$d" ] && cp -f "$BIN/$d" "$WIN_DLLS/"
    done

    echo "== Fet (Windows) =="
    ls -la "$NNLS_OUT" "$QM_OUT"
    echo "   host: $(du -h vamp_host_local.exe | cut -f1)"
    echo "   DLLs de runtime a $WIN_DLLS:"
    ls "$WIN_DLLS" | sed 's/^/     /'
}

# ===========================================================================
#  BRANCA macOS (Darwin, target 10.13, x86_64)
#  Els natius de suport (libvamp-hostsdk + libsndfile) els proporciona el
#  workflow a $PREFIX (CPATH/LIBRARY_PATH). Aquí només fem els PLUGINS: el
#  host el construeix `eines/compila_vamp_host.sh`.
# ===========================================================================
compila_macos() {
    echo "== compila_vamp_plugins.sh: branca macOS (plugins, target 10.13) =="
    local DEP="10.13" ARCH="x86_64"
    export MACOSX_DEPLOYMENT_TARGET="$DEP"

    PREFIX="${PREFIX:-${VAMP_PREFIX:-$ROOT/.mac-natius}}"
    local VSINC="$PREFIX/include" VSLIB="$PREFIX/lib"

    for t in clang clang++ make git curl tar; do
        command -v "$t" >/dev/null || { echo "ERROR: falta l'eina '$t'"; exit 1; }
    done
    [ -d "$VSINC/vamp-sdk" ] || {
        echo "ERROR: falten headers de Vamp ($VSINC/vamp-sdk). El workflow ha de construir vamp-plugin-sdk a \$PREFIX." >&2
        exit 1
    }
    # Preferim el .a (estàtic): enllaçar el .dylib de $PREFIX hi deixaria una
    # dependència de ruta que no existiria a l'ordinador de l'usuari.
    local VAMP_SDK_LIB
    VAMP_SDK_LIB="$(ls "$VSLIB"/libvamp-sdk.a 2>/dev/null | head -1)"
    [ -n "$VAMP_SDK_LIB" ] || {
        echo "ERROR: falta $VSLIB/libvamp-sdk.a (cal construir vamp-plugin-sdk amb static)." >&2
        exit 1
    }

    # Boost (headers) per al Chordino.
    local BOOST_INC=""
    for d in "$VSINC" "$(brew --prefix 2>/dev/null)/include" /usr/local/include /opt/homebrew/include; do
        [ -n "$d" ] && [ -d "$d/boost" ] && { BOOST_INC="$d"; break; }
    done
    if [ -z "$BOOST_INC" ] && command -v brew >/dev/null 2>&1; then
        echo "   boost no hi és; l'instal·lo (header-only)..."
        brew install boost >/dev/null 2>&1 || true
        [ -d "$(brew --prefix)/include/boost" ] && BOOST_INC="$(brew --prefix)/include"
    fi
    [ -n "$BOOST_INC" ] && [ -d "$BOOST_INC/boost" ] || {
        echo "ERROR: falten headers de boost. Fes 'brew install boost'." >&2; exit 1; }

    NNLS_OUT="${NNLS_OUT:-$ROOT/nnls-chroma-macos-local}"
    QM_OUT="${QM_OUT:-$ROOT/qm-vamp-plugins-macos-local}"
    WORK="$(mktemp -d -t ac_vamp_mac.XXXXXX)"
    trap 'rm -rf "$WORK"' EXIT
    mkdir -p "$NNLS_OUT" "$QM_OUT"

    # --- 1) nnls-chroma / Chordino (.dylib) --------------------------------
    echo "== [1/2] nnls-chroma (Chordino) macOS =="
    (
        cd codi_font_chordino
        rm -f ./*.o nnls-chroma.dylib
        FLAGS="-O2 -DNDEBUG -ffast-math -mmacosx-version-min=$DEP -arch $ARCH -I$VSINC -I$BOOST_INC"
        clang $FLAGS -c nnls.c -o nnls.o
        for f in NNLSBase NNLSChroma Chordino Tuning chromamethods viterbi plugins; do
            clang++ $FLAGS -c "$f.cpp" -o "$f.o"
        done
        clang++ -dynamiclib -o nnls-chroma.dylib ./*.o \
            -mmacosx-version-min=$DEP -arch $ARCH \
            -Wl,-exported_symbols_list,vamp-plugin.list \
            "$VAMP_SDK_LIB" -framework Accelerate
        cp -f nnls-chroma.dylib nnls-chroma.cat nnls-chroma.n3 "$NNLS_OUT/"
    )
    nm -gU "$NNLS_OUT/nnls-chroma.dylib" 2>/dev/null | grep -q _vampGetPluginDescriptor \
        || echo "AVÍS: no he pogut confirmar l'export de _vampGetPluginDescriptor" >&2
    echo "   -> $NNLS_OUT/nnls-chroma.dylib ($(otool -l "$NNLS_OUT/nnls-chroma.dylib" 2>/dev/null | grep -m1 -oE 'minos [0-9.]+' || echo '?'))"

    # --- 2) qm-vamp-plugins (COMPILAT des de font, target 10.13) -----------
    # PER QUÈ NO el binari oficial: code.soundsoftware.ac.uk és inaccessible
    # (com diu docs/QM_VAMP.md) -> no es pot baixar. Compilant-lo aquí amb els
    # clapack/cblas INCLOSOS (com a Linux/Windows) queda autocontingut.
    echo "== [2/2] qm-vamp-plugins macOS (des de font) =="
    OSXARCH="-mmacosx-version-min=$DEP -arch $ARCH -stdlib=libc++"
    (
        cd "$WORK"
        curl -sL --retry 3 -o qm.tar.gz \
            https://github.com/c4dm/qm-vamp-plugins/archive/refs/heads/master.tar.gz
        tar xzf qm.tar.gz
        cd qm-vamp-plugins-master
        mkdir -p lib
        git clone --depth 1 -q https://github.com/c4dm/qm-dsp lib/qm-dsp
        git clone --depth 1 -q https://github.com/c4dm/vamp-plugin-sdk lib/vamp-plugin-sdk
        MCXX="clang++ -D_USE_MATH_DEFINES"; MCC="clang -D_USE_MATH_DEFINES"
        make -C lib/qm-dsp -f build/osx/Makefile.osx ARCHFLAGS="$OSXARCH" \
            CXX="$MCXX" CC="$MCC"
        # Enllaç propi: res de ../vamp-plugin-sdk (les fonts SDK ja es compilen
        # dins el plugin) i exported_symbols_list del nostre .list.
        make -f build/osx/Makefile.osx ARCHFLAGS="$OSXARCH" CXX="$MCXX" CC="$MCC" \
            LDFLAGS="-dynamiclib $OSXARCH -lpthread -framework Accelerate -Wl,-exported_symbols_list,vamp-plugin.list"
        cp -f qm-vamp-plugins.dylib "$QM_OUT/qm-vamp-plugins.dylib"
        [ -f qm-vamp-plugins.cat ] && cp -f qm-vamp-plugins.cat "$QM_OUT/"
        [ -f qm-vamp-plugins.n3 ] && cp -f qm-vamp-plugins.n3 "$QM_OUT/"
    )
    nm -gU "$QM_OUT/qm-vamp-plugins.dylib" 2>/dev/null | grep -q _vampGetPluginDescriptor \
        || echo "AVÍS: no he pogut confirmar l'export de _vampGetPluginDescriptor" >&2
    echo "   -> $QM_OUT/qm-vamp-plugins.dylib ($(otool -l "$QM_OUT/qm-vamp-plugins.dylib" 2>/dev/null | grep -m1 -oE 'minos [0-9.]+' || echo '?'))"

    echo "== Fet (macOS) =="
    ls -la "$NNLS_OUT" "$QM_OUT"
}

# ===========================================================================
#  DISPATCH per SO
# ===========================================================================
case "$(uname -s 2>/dev/null)" in
    MINGW*|MSYS*|CYGWIN*|Windows_NT)
        compila_windows
        exit 0
        ;;
    Darwin)
        compila_macos
        exit 0
        ;;
esac

# ===========================================================================
#  BRANCA LINUX (comportament de sempre, sense canvis)
# ===========================================================================
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
# libvamp-sdk: pot ser 'libvamp-sdk.so' (paquet dev) o només 'libvamp-sdk.so.N'
# (runtime) -> agafem el que hi hagi i el symlinkem com a .so per al -l.
VAMP_LIB="$(ls "$LIB_SRC"/libvamp-sdk.so* 2>/dev/null | head -1)"
if [ -z "$VAMP_LIB" ]; then
    echo "ERROR: no trobo libvamp-sdk.so* a $LIB_SRC. Instal·la 'vamp-plugin-sdk'." >&2
    exit 1
fi
ln -sf "$VAMP_LIB" "$SDK/libvamp-sdk.so"

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
