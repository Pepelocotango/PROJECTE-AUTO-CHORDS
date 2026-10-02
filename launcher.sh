#!/usr/bin/env bash
# Portable launcher that prefers the project venv and falls back to system Python.
cd "$(dirname "$0")" || exit 1

# If a venv exists, use it
if [ -x ".venv/bin/python3" ]; then
  exec .venv/bin/python3 -m app.main "$@"
else
  exec python3 -m app.main "$@"
fi
