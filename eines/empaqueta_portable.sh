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
        --exclude 'CODI_concatenat.txt' --exclude '.gitignore' \
        --exclude '.git*' --exclude 'LLEGEIX-ME.txt' --exclude 'OLD/' \
        "$SRC"/ "$DEST"/
else
    echo "(sense rsync: còpia manual)"
    for f in app eines docs icones icona *-local vamp_host_local \
             AUTO_CHORDS.sh AUTO_CHORDS.desktop pyproject.toml LICENSE \
             LLICENCIES_TERCERS.md README.md CHANGELOG.md ROADMAP.md \
             DEVELOPING.md requirements.txt concatena.py acords_a_live.py \
             wav_a_wavs.py portable; do
        if [ -e "$f" ]; then
            cp -r "$f" "$DEST"/ || { echo "ERROR copiant $f" >&2; exit 1; }
        fi
    done
fi
chmod +x "$DEST/AUTO_CHORDS.sh" "$DEST/vamp_host_local" 2>/dev/null || true

# rsync --exclude PROTEGEIX els fitxers exclosos que ja hi eren (no els
# esborra): si una build anterior hi va deixar un .gitignore, el traiem.
for brossa in .gitignore .git .gitattributes; do
    [ -e "$DEST/$brossa" ] && gio trash "$DEST/$brossa" 2>/dev/null || true
done

# Nota dins el paquet: NO editar-hi codi.
cat > "$DEST/LLEGEIX-ME.txt" <<'TXT'
AUTO CHORDS — PAQUET PORTABLE (generat automaticament)
======================================================

AQUESTA CARPETA ES UN ARTEFACTE DE BUILD. NO HI EDITIS CODI.
Qualsevol canvi aquí es perdra a la propera regeneracio.

El codi viu al projecte:
    ~/0PROJECTES_GitHub/PROJECTE AUTO CHORDS/

Per regenerar aquest paquet:
    cd "PROJECTE AUTO CHORDS" && ./eines/empaqueta_portable.sh

EXECUTAR L'APP:
    ./AUTO_CHORDS.sh          (terminal)
    o doble clic a AUTO_CHORDS.sh (tria "Executa")

REQUISITS MINIMS DEL SISTEMA (tota la resta va INCLOSA al paquet):
    - Linux x86_64 amb glibc >= 2.35 (Ubuntu 22.04+, Debian 12+, Fedora 36+...)
    - Un entorn d'escriptori (X11 o Wayland)
    - Per ESCOLTAR: PipeWire o PulseAudio + `paplay` o `aplay`.
      Sense ells, l'app funciona igual (analitzar, editar, exportar);
      nomes avisa que no pot sonar.

Dins el paquet ja hi van: Python + PyQt5 + numpy, ffmpeg, els plugins Vamp i
les seves llibreries natives (portable/lib/), o sigui que NO cal instal·lar-ne
cap al sistema.

IMPORTAR ALTRES FORMATS (mp3, aif, flac...): ja va inclos (ffmpeg del paquet).

Codi font i AppImage publicada:
    https://github.com/Pepelocotango/PROJECTE-AUTO-CHORDS
Mes informacio: docs/PORTABILITAT.md dins aquesta carpeta.
TXT

echo "Fet. Mida: $(du -sh "$DEST" | cut -f1)"
echo "Per provar:  cd '$DEST' && ./AUTO_CHORDS.sh"
