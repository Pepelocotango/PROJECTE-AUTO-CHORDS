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
    if curl -sfL -o "icones/$n.svg" "$BASE/$n.svg"; then
        echo "  ✓ $n"
    else
        echo "  ⚠️  no trobat: $n"; rm -f "icones/$n.svg"
    fi
done
echo "fet: $(ls icones | wc -l) icones ($(du -sh icones | cut -f1))"
