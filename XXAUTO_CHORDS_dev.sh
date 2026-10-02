#!/usr/bin/env bash
# Llençador de desenvolupament.
# Per defecte no fa auto-reload; afegeix --watch si vols que es rebotin els canvis.

cd "$(dirname "$0")" || exit 1

if [ -f ".venv/bin/activate" ]; then
  . .venv/bin/activate
fi

exec python3 dev_reload.py "$@"
