"""Camins de l'app i tria d'un directori d'estat ESCRIPTIBLE.

⚠️ Clau per a l'AppImage: el seu contingut es munta en **NOMÉS LECTURA**. Si
l'app hi escriu el log (o el temp, o les opcions) peta a l'arrencada amb
`OSError: [Errno 30] Read-only file system` i no arriba ni a mostrar la
finestra. Per això tot l'estat va a `DADES_DIR`, que es tria amb una prova
d'escriptura real:

    1. la carpeta del projecte  -> paquet portable/repo: autocontingut (com abans)
    2. $XDG_STATE_HOME/auto-chords
    3. ~/.local/state/auto-chords
    4. <temp del sistema>/auto-chords

`AUTO_CHORDS_TEMP` (si es defineix) segueix manant sobre el directori temporal,
com sempre.
"""
import os
import tempfile

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(APP_DIR)


def _es_escriptible(d):
    """Cert si `d` existeix (o es pot crear) I s'hi pot escriure.

    No n'hi ha prou que existeixi: en una AppImage muntada la carpeta hi és,
    però és de només lectura.
    """
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        return False
    return os.access(d, os.W_OK)


def _dir_de_dades():
    """Primer directori ESCRIPTIBLE de la llista de preferència (vegeu el mòdul)."""
    base_xdg = (os.getenv("XDG_STATE_HOME")
                or os.path.join(os.path.expanduser("~"), ".local", "state"))
    for d in (PROJECT_ROOT,
              os.path.join(base_xdg, "auto-chords"),
              os.path.join(tempfile.gettempdir(), "auto-chords")):
        if d and _es_escriptible(d):
            return d
    return tempfile.gettempdir()


DADES_DIR = _dir_de_dades()
TEMP_DIR = os.getenv("AUTO_CHORDS_TEMP") or os.path.join(DADES_DIR, "temp")
LOG_PATH = os.path.join(DADES_DIR, "auto_chords.log")
OPCIONS_PATH = os.path.join(DADES_DIR, "opcions_detecta.json")

# Garantir que existeix quan s'importa
try:
    os.makedirs(TEMP_DIR, exist_ok=True)
except OSError:
    pass  # permisos o disc ple; no és crític per arrencar
