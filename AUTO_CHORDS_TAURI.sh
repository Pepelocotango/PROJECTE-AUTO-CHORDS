#!/usr/bin/env bash
# AUTO_CHORDS_TAURI.sh — Llançador de l'AppImage Tauri d'Auto Chords.
#
# Ús:
#   ./AUTO_CHORDS_TAURI.sh
#   (o doble-clic si el fitxer és executable)
#
# Configura AUTO_CHORDS_ROOT automàticament perquè l'AppImage trobi
# el backend Python (wav_a_wavs.py, analyze.py, save.py).
set -euo pipefail

cd "$(dirname "$0")" || exit 1
export AUTO_CHORDS_ROOT="$(pwd)"

APPDIR="tauri-ui/src-tauri/target/release/bundle/appimage"
APPIMG="$(find "$APPDIR" -maxdepth 1 -name '*.AppImage' 2>/dev/null | head -1)"

if [ -z "${APPIMG:-}" ]; then
  echo "❌ No trobo cap AppImage a: $APPDIR"
  echo "   Construeix-la primer amb:"
  echo "     cd tauri-ui && pnpm tauri build --bundles appimage"
  exit 1
fi

echo "🖥️  AUTO_CHORDS_ROOT=$AUTO_CHORDS_ROOT"
echo "📦 AppImage: $APPIMG"
echo

exec "$APPIMG" "$@"
