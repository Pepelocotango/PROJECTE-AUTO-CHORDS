#!/usr/bin/env bash
# Llançador directe de l'app Auto Chords.
# Es pot executar des de la terminal o amb doble clic si el fitxer és executable.

cd "$(dirname "$0")" || exit 1

if [ -f ".venv/bin/activate" ]; then
  . .venv/bin/activate
fi

exec python3 -m app.main "$@"
