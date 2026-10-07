#!/usr/bin/env bash
# Copia dins portable/lib/ les llibreries natives que necessita `vamp_host_local`
# (host Vamp propi) i els seus plugins, EXCEPTE les que tot Linux modern porta
# de sèrie (glibc + libstdc++/libgcc).
#
# Per què cal: sense això l'AppImage depenia de tenir instal·lats al SO host
# `libvamp-hostsdk.so.3`, `libsndfile.so.1` i els còdecs (libFLAC, libvorbis,
# libvorbisenc, libopus, libogg, libmpg123, libmp3lame). Amb les llibreries
# empaquetades, l'AppImage és autoportable.
#
# D'on surten: del MATEIX sistema que compila (no es baixa res). Al CI és
# `ubuntu-22.04`, o sigui que les llibreries queden ancorades a glibc 2.35 —
# coherent amb el binary `vamp_host_local` que s'hi compila.
#
# El llançador (`AUTO_CHORDS.sh`) exporta LD_LIBRARY_PATH cap aquí.
set -e
cd "$(dirname "$0")/.."

DEST="portable/lib"
# Llibreries que deixem AL SISTEMA: són a qualsevol Linux amb glibc modern.
# (Si les empaquetéssim, podríem ombrejar el libstdc++ que fan servir
#  Qt/Python i trencar coses; a més no guanyem portabilitat real.)
EXCLOU='^(linux-vdso|ld-linux|libc\.so|libm\.so|libdl\.so|libpthread\.so|librt\.so|libstdc\+\+\.so|libgcc_s\.so)'

mkdir -p "$DEST"
echo "Resolent les llibreries natives (ldd)..."
n=0
for bin in vamp_host_local nnls-chroma-linux64-local/*.so \
           qm-vamp-plugins-linux64-local/*.so; do
    [ -e "$bin" ] || continue
    while read -r name arrow path; do
        [ -n "$path" ] || continue
        case "$path" in /*) ;; *) continue ;; esac      # només rutes absolutes
        base=$(basename "$path")
        echo "$base" | grep -qE "$EXCLOU" && continue
        if [ ! -e "$DEST/$base" ]; then
            # cp desreferencia el symlink: guardem el fitxer sota el seu soname,
            # que és exactament el nom que busca el carregador dinàmic.
            cp "$path" "$DEST/$base"
            echo "  + $base"
            n=$((n + 1))
        fi
    done < <(ldd "$bin" 2>/dev/null | awk '/=>/ {print $1, $2, $3}')
done

if [ "$n" -eq 0 ]; then
    echo "AVIS: no s'ha copiat cap llibreria (ja hi eren o falta vamp_host_local)." >&2
fi
echo "Fet: $n noves, $(ls "$DEST" 2>/dev/null | wc -l) en total a $DEST/ ($(du -sh "$DEST" | cut -f1))"
