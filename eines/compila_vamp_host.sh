#!/usr/bin/env bash
# Compila l'host Vamp propi (vamp_host_local).
# Depèn de: libvamp-hostsdk-dev + libsndfile1-dev (headers del sistema o .deps).
# Flags -msse -msse2: SENSE AVX (Q9400 i altres CPUs antigues).
set -e
cd "$(dirname "$0")/.."
INC=""
[ -d .deps/usr/include ] && INC="-I.deps/usr/include"
echo "Compilant vamp_host_local..."
g++ -O2 -msse -msse2 -mfpmath=sse -ftree-vectorize $INC \
    -o vamp_host_local eines/vamp_host.cpp \
    -lvamp-hostsdk -lsndfile -ldl -lpthread -lm
echo "Fet: $(du -h vamp_host_local | cut -f1)"
ldd vamp_host_local | grep '=>' | awk '{print "  "$1}'
