#!/usr/bin/env bash
# Empaqueta AUTO CHORDS en una carpeta portable (Fase 5).
# Ús: eines/empaqueta_portable.sh [desti]   (per defecte ../AUTO_CHORDS_PORTABLE)
#
# Inclou: codi + plugins + host Vamp + Python portable (portable/) + ffmpeg.
# Exclou: .deps/ (només build), .venv/, .git/, temp/, __pycache__, tauri-ui/,
#         logs, opcions d'usuari.
set -e
cd "$(dirname "$0")/.."
SRC="$PWD"
DEST="${1:-$SRC/../AUTO_CHORDS_PORTABLE}"

# Salvaguarda: el destí NO pot ser dins del projecte (bucle de còpia + git).
DEST="$(realpath -m "$DEST" 2>/dev/null || echo "$DEST")"
case "$DEST" in
    "$SRC"|"$SRC"/*)
        echo "ERROR: el destí no pot ser DINS del projecte ('$SRC')."
        echo "       Fes-lo servir com a germà: ../AUTO_CHORDS_PORTABLE"
        exit 1
        ;;
esac

if [ ! -d portable/python ]; then
    echo "⚠️  Falta portable/ (Python). Executa abans: eines/crea_portable.sh"
    exit 1
fi
[ -x vamp_host_local ] || { echo "⚠️  Falta vamp_host_local. Executa: eines/compila_vamp_host.sh"; exit 1; }

echo "Empaquetant a: $DEST"
mkdir -p "$DEST"
# còpia selectiva (rsync si hi és, si no cp)
if command -v rsync >/dev/null; then
    rsync -a --delete \
        --exclude '.deps/' --exclude '.venv/' --exclude '.git/' \
        --exclude 'temp/' --exclude '__pycache__/' --exclude '*.pyc' \
        --exclude 'tauri-ui/' --exclude '.pytest_cache/' \
        --exclude 'auto_chords.log' --exclude 'opcions_detecta.json' \
        --exclude 'CODI_concatenat.txt' \
        "$SRC"/ "$DEST"/
else
    echo "(sense rsync: còpia manual)"
    for f in app eines docs *-local vamp_host_local sonic-annotator AUTO_CHORDS.sh \
             AUTO_CHORDS.desktop pyproject.toml LICENSE README.md CHANGELOG.md \
             ROADMAP.md DEVELOPING.md requirements.txt concatena.py \
             acords_a_live.py wav_a_wavs.py portable; do
        [ -e "$f" ] && cp -r "$f" "$DEST"/ 2>/dev/null || true
    done
fi
chmod +x "$DEST/AUTO_CHORDS.sh" "$DEST/vamp_host_local" 2>/dev/null || true
echo "Fet. Mida: $(du -sh "$DEST" | cut -f1)"
echo "Per provar:  cd '$DEST' && ./AUTO_CHORDS.sh"
