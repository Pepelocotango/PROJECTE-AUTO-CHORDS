#!/usr/bin/env bash
# Crea el Python portable (Fase 2 de portabilitat) dins portable/python/.
# Usa python-build-standalone, build GENÈRIC x86_64 (sense AVX: el _v2
# demanaria SSE4.2 i faria SIGILL al Q9400).
set -e
cd "$(dirname "$0")/.."
# Versions fixades del projecte (URL + versió + SHA256 de cada baixada).
. eines/deps_fixades.env

mkdir -p portable
echo "Baixant el CPython portable ${PYBS_PYV} (tag ${PYBS_TAG}, verificat)..."
# Baixada VERIFICADA amb SHA256 (eines/baixa_verificat.py): si el hash no
# quadra, peta i NO deixa cap fitxer a mitges.
python3 eines/baixa_verificat.py "$PYBS_URL" "$PYBS_SHA256" /tmp/pyport.tar.gz
tar xzf /tmp/pyport.tar.gz -C portable/
PY=./portable/python/bin/python3
echo "Instal·lant dependències (pins de requirements.txt)..."
# Font ÚNICA de pins: requirements.txt → builds reproduïbles i alineats amb
# l'inventari. (Abans anaven specs soltes i `PyQt5_sip` sense pin.)
# Vegeu docs/AUDITORIA_PRODUCCIO.md A.2/D.1.
$PY -m pip install --no-cache-dir --quiet -r requirements.txt
echo "Retocant (treure qml/translations/pip: no s'usen)..."
$PY -m pip uninstall -y pip setuptools 2>/dev/null || true
Q=portable/python/lib/python3.12/site-packages/PyQt5/Qt5
for d in qml translations qsci; do [ -d "$Q/$d" ] && gio trash "$Q/$d" || true; done
find portable -name "__pycache__" -type d -exec gio trash {} \; 2>/dev/null || true
echo "Baixant ffmpeg estàtic ${FFMPEG_LINUX_VER} (johnvansickle, verificat)..."
python3 eines/baixa_verificat.py "$FFMPEG_LINUX_URL" "$FFMPEG_LINUX_SHA256" /tmp/ff.tar.xz
tar xJf /tmp/ff.tar.xz -C /tmp/
FFDIR=$(ls -d /tmp/ffmpeg-*-amd64-static | head -1)
mkdir -p portable/bin
cp "$FFDIR/ffmpeg" portable/bin/ffmpeg   # només ffmpeg: ffprobe NO s'empaqueta
# (l'app no el fa servir; només ffmpeg.info(), que es degrada a {} sense ffprobe)
echo "Llibreries natives de l'host Vamp (autoportabilitat)..."
[ -x vamp_host_local ] || ./eines/compila_vamp_host.sh
./eines/libreries_natives.sh
echo "Fet. Mida: $(du -sh portable | cut -f1)"
