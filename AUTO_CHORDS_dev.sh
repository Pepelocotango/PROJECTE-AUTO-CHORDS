#!/usr/bin/env bash
# Llençador de desenvolupament.
# Per defecte NO fa auto-reload; afegeix --watch si vols reobrir al guardar canvis.

cd "$(dirname "$0")" || exit 1

if [ -f ".venv/bin/activate" ]; then
  . .venv/bin/activate
fi

exec python3 dev_reload.py "$@"
