#!/usr/bin/env bash
# Construeix un AppImage d'AUTO CHORDS a partir del paquet portable.
#
# Ús:  eines/crea_appimage.sh [desti.AppImage]
#   (per defecte: ../AUTO_CHORDS-x86_64.AppImage, germà del projecte)
#
# Requisits: portable/ (-> eines/crea_portable.sh), vamp_host_local
# (-> eines/compila_vamp_host.sh), icona/ (-> eines/crea_icona.py).
# Descarrega appimagetool si no el troba (a portable/bin, gitignorat).
set -e
cd "$(dirname "$0")/.."
PROJ="$PWD"
DESTI="${1:-$PROJ/../AUTO_CHORDS-x86_64.AppImage}"

# --- comprovacions ---
[ -d portable/python ] || { echo "⚠️  falta portable/ -> eines/crea_portable.sh"; exit 1; }
[ -x vamp_host_local ] || { echo "⚠️  falta vamp_host_local -> eines/compila_vamp_host.sh"; exit 1; }
[ -f icona/auto-chords.png ] || .venv/bin/python eines/crea_icona.py

# --- appimagetool (es baixa un cop) ---
TOOL="$PROJ/portable/bin/appimagetool"
if [ ! -x "$TOOL" ]; then
    echo "Baixant appimagetool..."
    mkdir -p "$PROJ/portable/bin"
    curl -sfL -o "$TOOL" \
      "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x "$TOOL"
fi

# --- AppDir en un directori temporal (mai dins del projecte) ---
WORK="$(mktemp -d /tmp/ac_appimage.XXXXXX)"
APP="$WORK/AutoChords.AppDir"
mkdir -p "$APP/usr/share/auto-chords"

echo "1/4 empaquetant el portable dins l'AppDir..."
"./eines/empaqueta_portable.sh" "$APP/usr/share/auto-chords" >/dev/null

echo "2/4 icona + .desktop + AppRun..."
cp icona/auto-chords.png "$APP/auto-chords.png"
cp icona/auto-chords.png "$APP/.DirIcon"
cp icona/auto-chords-256.png "$APP/auto-chords-256.png" 2>/dev/null || true

cat > "$APP/auto-chords.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Auto Chords
GenericName=Analitzador d'acords
Comment=Analitza acords i estructura d'un audio i exporta clips per al DAW
Exec=auto-chords
Icon=auto-chords
Categories=AudioVideo;Audio;AudioVideoEditing;
Keywords=audio;acords;chords;bpm;musica;
Terminal=false
StartupNotify=true
EOF

cat > "$APP/AppRun" <<'EOF'
#!/bin/sh
# Punt d'entrada de l'AppImage: executa l'app amb el Python de dins.
HERE="$(dirname "$(readlink -f "$0")")"
export AUTO_CHORDS_APPDIR="$HERE"
exec "$HERE/usr/share/auto-chords/AUTO_CHORDS.sh" "$@"
EOF
chmod +x "$APP/AppRun" "$APP/usr/share/auto-chords/AUTO_CHORDS.sh"

echo "3/4 construint l'AppImage..."
export ARCH=x86_64
"$TOOL" --no-appstream "$APP" "$DESTI" 2>&1 | tail -3

echo "4/4 fet."
ls -la "$DESTI" 2>/dev/null | awk '{print "  AppImage: "$NF" ("$5/1048576" MB)"}'
