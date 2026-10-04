import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(APP_DIR)
# Preferència per variable d'entorn per fer el projecte portable
TEMP_DIR = os.getenv("AUTO_CHORDS_TEMP", os.path.join(PROJECT_ROOT, "temp"))

# Garantir que existeix quan s'importa
try:
    os.makedirs(TEMP_DIR, exist_ok=True)
except OSError:
    pass  # permisos o disc ple; no és crític per arrencar
