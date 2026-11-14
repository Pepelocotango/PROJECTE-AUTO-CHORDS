"""Dreceres de teclat: valors per defecte, càrrega i desat.

La configuració d'usuari viu a `config.DADES_DIR/dreceres.json`. Els identificadors
són estables per a les accions que ho necessiten (menú i timeline comparteixen
`edita.copia`, `global.play`, etc.); les accions de menú sense ID explícit
generen un ID a partir del menú i el text.
"""
from __future__ import annotations

import json
import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence

from . import config
from .pipeline_io import escriu_atomic

NOM_FITXER = "dreceres.json"
FORMAT = 1

#: Dreceres que no són QAction de menú. `tipus` decidix on s'apliquen.
DEFECTES = {
    "global.play": {
        "etiqueta": "Reproduïr / pausa", "grup": "Global",
        "defecte": "Space", "tipus": "shortcut",
    },
    "global.tap": {
        "etiqueta": "Tap tempo", "grup": "Global",
        "defecte": "T", "tipus": "shortcut",
    },
    "global.eina": {
        "etiqueta": "Canviar l'eina del timeline", "grup": "Global",
        "defecte": "E", "tipus": "shortcut",
    },
    "talla.plus": {
        "etiqueta": "Parteix tempo i estructura al cursor", "grup": "Editor",
        "defecte": "+", "tipus": "raw",
    },
    "talla.tempo": {
        "etiqueta": "Parteix només el tempo al cursor", "grup": "Editor",
        "defecte": "Return", "tipus": "raw",
    },
    "talla.estructura": {
        "etiqueta": "Parteix només l'estructura al cursor", "grup": "Editor",
        "defecte": "0", "tipus": "raw",
    },
    "marcador": {
        "etiqueta": "Afig un marcador al cursor", "grup": "Editor",
        "defecte": "M", "tipus": "raw",
    },
    "edita.copia": {
        "etiqueta": "Copia", "grup": "Menú Edita",
        "defecte": "Ctrl+C", "tipus": "menu",
    },
    "edita.retalla": {
        "etiqueta": "Retalla", "grup": "Menú Edita",
        "defecte": "Ctrl+X", "tipus": "menu",
    },
    "edita.enganxa": {
        "etiqueta": "Enganxa", "grup": "Menú Edita",
        "defecte": "Ctrl+V", "tipus": "menu",
    },
    "edita.duplica": {
        "etiqueta": "Duplica element", "grup": "Menú Edita",
        "defecte": "Ctrl+D", "tipus": "menu",
    },
    "edita.elimina": {
        "etiqueta": "Elimina element", "grup": "Menú Edita",
        "defecte": "Del", "tipus": "menu",
    },
    "timeline.esc": {
        "etiqueta": "Cancel·la rang, loop o selecció", "grup": "Timeline",
        "defecte": "Esc", "tipus": "timeline",
    },
    "timeline.nudge_esq": {
        "etiqueta": "Nudge a l'esquerra", "grup": "Timeline",
        "defecte": "Left", "tipus": "timeline",
    },
    "timeline.nudge_dret": {
        "etiqueta": "Nudge a la dreta", "grup": "Timeline",
        "defecte": "Right", "tipus": "timeline",
    },
}


def ruta():
    """Ruta del fitxer d'usuari (dinàmica: els tests poden moure DADES_DIR)."""
    return os.path.join(config.DADES_DIR, NOM_FITXER)


def normalitza(seq):
    """Retorna la seqüència en format portable estable (pot ser buida)."""
    if seq is None:
        return ""
    return QKeySequence(str(seq)).toString(QKeySequence.PortableText)


def carrega():
    """Llig les dreceres de l'usuari; si no hi ha res o està malmès, `{}`."""
    try:
        with open(ruta(), encoding="utf-8") as f:
            dades = json.load(f)
    except (OSError, ValueError, TypeError):
        return {}
    if isinstance(dades, dict) and isinstance(dades.get("bindings"), dict):
        dades = dades["bindings"]
    if not isinstance(dades, dict):
        return {}
    out = {}
    for clau, valor in dades.items():
        if isinstance(clau, str) and isinstance(valor, str):
            out[clau] = normalitza(valor)
    return out


def desa(bindings):
    """Desa les dreceres de manera atòmica. Retorna la ruta escrita."""
    net = {}
    for clau, valor in (bindings or {}).items():
        if isinstance(clau, str) and isinstance(valor, str):
            net[clau] = normalitza(valor)
    dades = {"format": FORMAT, "bindings": net}
    escriu_atomic(ruta(), lambda f: json.dump(
        dades, f, ensure_ascii=False, indent=2, sort_keys=True))
    return ruta()


def coincideix(seq, event, ignora_mods=0):
    """Cert si `event` correspon a la seqüència d'una sola tecla `seq`.

    Admet les equivalències habituals: Return/Enter i Del/Retrocés. El `+`
    també accepta el teclat numèric (`Key_Plus` + `KeypadModifier`) i els
    layouts que l'envien com a `Shift`+`=` o `Key_Plus` + `Shift`.
    """
    seq = normalitza(seq)
    if not seq:
        return False
    ks = QKeySequence(seq)
    if ks.count() != 1:
        return False
    combo = int(ks[0])
    tecla = int(event.key())
    mods = int(event.modifiers()) & ~int(ignora_mods)
    if combo == (tecla | mods):
        return True
    ret = int(QKeySequence("Return")[0])
    ent = int(QKeySequence("Enter")[0])
    if combo in (ret, ent) and event.key() in (Qt.Key_Return, Qt.Key_Enter):
        return True
    del_ = int(QKeySequence("Del")[0])
    if combo == del_ and event.key() == Qt.Key_Backspace:
        return True
    # El «+» pot arribar de tres maneres segons el teclat: Key_Plus sense
    # modificadors (fila superior del layout es), Key_Plus + KeypadModifier
    # (teclat numèric) o Key_Plus/Key_Equal + Shift (layouts on + és Shift+=).
    # Shift i Keypad són part de la mateixa tecla; Ctrl/Alt/Meta no.
    if seq == "+":
        extra = int(event.modifiers()) & ~(
            int(Qt.ShiftModifier) | int(Qt.KeypadModifier) | int(ignora_mods))
        if extra == 0:
            if event.key() == Qt.Key_Plus:
                return True
            if event.key() == Qt.Key_Equal \
                    and (event.modifiers() & Qt.ShiftModifier):
                return True
    return False
