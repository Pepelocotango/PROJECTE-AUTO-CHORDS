#!/usr/bin/env bash
# Llançador directe de l'app Auto Chords.
# Prefereix el Python PORTABLE (carpeta portable/, fase 2 de portabilitat);
# si no hi és, fa servir el .venv; i si no, el python3 del sistema.
cd "$(dirname "$0")" || exit 1

if [ -x "portable/python/bin/python3" ]; then
    PY="portable/python/bin/python3"
elif [ -x ".venv/bin/python" ]; then
    PY=".venv/bin/python"
else
    PY="python3"
fi

exec "$PY" -m app.main "$@"
