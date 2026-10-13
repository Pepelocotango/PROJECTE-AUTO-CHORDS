#!/usr/bin/env bash
# Llançador d'Auto Chords AMB el pont MCP actiu (per controlar l'app des
# d'opencode). Igual que AUTO_CHORDS.sh pel que fa a l'intèrpret, però crida
# el llançador que enganxa `app/mcp_bridge.py` sense tocar app/main.py.
#
# Ús:  ./AUTO_CHORDS_MCP.sh
# Per a l'ús normal (sense pont), segueix fent servir AUTO_CHORDS.sh.
cd "$(dirname "$0")" || exit 1

# Llibreries natives empaquetades (Vamp + libsndfile + còdecs): prioritzen
# sobre les del sistema (vegeu eines/libreries_natives.sh).
if [ -d "portable/lib" ]; then
    LD_LIBRARY_PATH="$PWD/portable/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    export LD_LIBRARY_PATH
fi

if [ -x "portable/python/bin/python3" ]; then
    PY="portable/python/bin/python3"
elif [ -x ".venv/bin/python" ]; then
    PY=".venv/bin/python"
else
    PY="python3"
fi

exec "$PY" eines/mcp_auto_chords_launcher.py "$@"
