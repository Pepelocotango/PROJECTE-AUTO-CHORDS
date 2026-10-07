#!/usr/bin/env bash
# Baixa les icones de la UI des de Lucide (ISC, https://lucide.dev).
# Nomes les que fem servir. Els SVG porten stroke="currentColor" -> es
# recoloreixen a app/icones.py.
set -e
cd "$(dirname "$0")/.."
BASE="https://raw.githubusercontent.com/lucide-icons/lucide/main/icons"
mkdir -p icones
NOMES="play pause square repeat-2 volume-x metronome target map-pin compass \
audio-lines zoom-in zoom-out rewind fast-forward maximize arrow-left-to-line \
arrow-right-to-line music piano circle-gauge mic settings"
for n in $NOMES; do
    tmp="$(mktemp)"
    # Baixem a un temporal i NOMES el substituim si ha anat bé: així, si la xarxa
    # falla, es conserva la icona que ja hi havia al repo (abans esborrava el
    # fitxer i deixava el projecte sense icones).
    if curl -sfL -o "$tmp" "$BASE/$n.svg"; then
        mv -f "$tmp" "icones/$n.svg"
        echo "  ✓ $n"
    else
        echo "  ⚠️  no trobat: $n (deixo la que hi havia)"
        gio trash "$tmp" 2>/dev/null || true
    fi
done
echo "fet: $(ls icones | wc -l) icones ($(du -sh icones | cut -f1))"
