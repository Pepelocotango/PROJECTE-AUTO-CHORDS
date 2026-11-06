"""Opcions persistents i valors per defecte dels diàlegs.

Extret de `app/dialegs.py`. Conté els defectes, els helpers de widgets i la
lectura/escriptura del fitxer d'opcions.
"""
import json

from PyQt5.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox

from app import config, tempo

# Traducció al català dels títols dels paràmetres del Chordino (els que dona
# el plugin son en anglès) + una ajuda curta de quan tocar-los.
NOMS_CA = {
    "useNNLS": "Transcripció aproximada (NNLS)",
    "useHMM": "Suavitzat HMM (Viterbi)",
    "rollon": "Tall de greus (roll-on espectral)",
    "tuningmode": "Mode d'afinació",
    "whitening": "Equalització espectral",
    "s": "Forma espectral",
}
AJUDA_CA = {
    "useNNLS": "Converteix l'espectre a croma amb NNLS (normalment millor que "
               "la FFT simple). Deixa'l activat.",
    "useHMM": "Suavitza els acords amb un model de Markov: menys canvis "
              "nerviosos. Desactiva'l si vols detectar canvis ràpids.",
    "rollon": "Emmudeix les freqüències greus abans d'analitzar (0 = no en "
              "treu cap). Apuja'l si el baix confon els acords.",
    "tuningmode": "Afinació global (recomanat) o local. Prova la local si el "
                  "tema està desafinat o és en directe.",
    "whitening": "Iguala l'espectre abans d'analitzar. Normalment activat.",
    "s": "Forma espectral (0,5–0,9). Valors alts = més suau.",
}

# Traducció dels noms de valor (value_names) dels paràmetres.
VALORS_CA = {
    "global tuning": "afinació global",
    "local tuning": "afinació local",
}

# Fitxer on es recorden les últimes opcions. Viu a `config.DADES_DIR` (un
# directori ESCRIPTIBLE: el projecte si ho és, si no l'estat d'usuari) perquè
# en una AppImage muntada la carpeta del projecte és de només lectura.
FITXER_OPCIONS = config.OPCIONS_PATH

# Valors per defecte de fàbrica del diàleg d'autodetecció. Revisats i fixats
# amb l'operador (2026-10-13). Són els que es mostren la primera vegada i els
# que restaura el botó «Restaura per defecte».
DEFECTES = {
    # ACORDS: coincideixen amb els defectes del descriptor del Chordino, però
    # els fixem explícitament perquè siguin estables (no depenen del plugin).
    "chords": {"useNNLS": 1, "useHMM": 1, "rollon": 0.0, "tuningmode": 0,
               "whitening": 1.0, "s": 0.7},
    "bpm": {
        "motor": "consens",
        "min": tempo.BPM_MIN, "max": tempo.BPM_MAX,
        "pref_min": tempo.BPM_PREFERIT[0], "pref_max": tempo.BPM_PREFERIT[1],
    },
    "structure": {"motor": "qm", "durada_min": 2.0,
                  "fusiona_iguals": True},
    # Neteja posterior dels acords (post-processat, app/postproc.py)
    "clean": {"durada_min": 0.15, "fusiona_iguals": True, "sense_baix": False,
              "reduir": False, "snap": True, "divisio": 4},
    # Anàlisi guiat: mida del tram i si es confirma la detecció amb el BPM
    # del tram anterior.
    "guiat": {"compassos": 4, "confirma": True},
    # QUÈ fa «Analitza»: cada etapa es pot activar/desactivar per separat
    # (BPM · acords · estructura). El que està desactivat NO es toca: es
    # conserva el que ja hi ha al model. Decisió de l'operador (21-10-2026):
    # per defecte les tres ACTIVADES — «Analitza» detecta també el BPM.
    "analisi": {"bpm": True, "acords": True, "estructura": True},
}

# Valors per defecte de l'acció separada «Analitza BPM». No formen part del
# diàleg d'anàlisi d'acords/estructura: són una acció independent.
BEATS_DEFECTES = {"motor": "qm", "sensibilitat": 50,
                  "mode": "beats", "aplica_bpm": True}



def _spin(minim, maxim, pas, valor, decimals=2):
    s = QDoubleSpinBox()
    s.setRange(float(minim), float(maxim))
    s.setSingleStep(float(pas) if pas else 0.05)
    s.setDecimals(decimals)
    s.setValue(float(valor))
    return s


def _combo(opcions, valor):
    c = QComboBox()
    for i, nom in enumerate(opcions):
        c.addItem(VALORS_CA.get(nom, nom), i)
    c.setCurrentIndex(int(valor))
    return c


def _checkbox(valor):
    c = QCheckBox("activat")
    c.setChecked(bool(valor))
    return c


def _fitxer_opcions():
    """Ruta efectiva de les opcions.

    Es llig de la façana `app.dialegs` perquè els tests patxen
    `dialegs.FITXER_OPCIONS` i el pedaç ha d'arribar ací.
    """
    try:
        from . import dialegs
        return getattr(dialegs, "FITXER_OPCIONS", FITXER_OPCIONS)
    except Exception:  # noqa: BLE001
        return FITXER_OPCIONS


def carrega_opcions():
    """Llegeix les opcions desades (o torna els defectes)."""
    base = json.loads(json.dumps(DEFECTES))     # copia profunda
    try:
        with open(_fitxer_opcions(), encoding="utf-8") as f:
            desat = json.load(f)
        for seccio in base:
            base[seccio].update(desat.get(seccio) or {})
    except (OSError, ValueError):
        pass
    return base


def desa_opcions(opcions):
    """Desa les opcions triades (silenciosament si no es pot)."""
    try:
        with open(_fitxer_opcions(), "w", encoding="utf-8") as f:
            json.dump(opcions, f, indent=2, ensure_ascii=False)
    except OSError:
        pass
