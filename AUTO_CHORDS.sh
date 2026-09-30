#!/usr/bin/env bash
# Obre l'Auto Chords (GUI). Ús: bash AUTO_CHORDS.sh  (o doble clic -> "Executa")
cd "$(dirname "$0")/app" || exit 1
exec python3 main.py
