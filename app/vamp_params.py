"""Llegeix els paràmetres ajustables dels plugins Vamp (descriptors .n3).

Vamp és un estàndard sense GUI: cada plugin descriu els seus paràmetres en un
fitxer `.n3` (identificador, títol, rang, pas, valor per defecte i, de vega-
des, els noms de valor). Aquesta peça els converteix en estructures simples
perquè la UI pugui construir un diàleg i el pipeline els pugui passar al
motor amb un fitxer transform (`.ttl`) via `sonic-annotator -t`.

Vegeu `docs/AUTODETECCIO_OPCIONS.md` per al context.
"""

import os
import re

from . import pipeline

# Nom del plugin (dins el .n3) per a cada transform que fem servir.
PLUGINS = {
    "chords": ("nnls-chroma-linux64-local/nnls-chroma.n3", "chordino"),
    "structure": ("segmentino-linux64-local/segmentino.n3", "segmentino"),
}


def _blocs(text):
    """Parteix el .n3 en blocs «plugbase:xxx a vamp:Tipus ; ... .»"""
    return re.split(r"\n(?=plugbase:)", text)


def _valor(bloc, patro, defecte=None):
    m = re.search(patro, bloc)
    return m.group(1) if m else defecte


def llegeix_params(n3_path, nom_plugin):
    """Retorna la llista de paràmetres d'un plugin, en l'ordre del descriptor.

    Cada element és un dict:
        {id, titol, tipus, minim, maxim, pas, defecte, valors}
    `tipus` ∈ {"quantitzat", "numeric"}; `valors` és la llista de noms
    (p. ex. ["global tuning", "local tuning"]) o [].
    """
    with open(n3_path, encoding="utf-8") as f:
        text = f.read()
    blocs = _blocs(text)

    # 1) paràmetres definits: id del bloc -> especificació
    defs = {}
    for b in blocs:
        m = re.match(r"plugbase:(\w+)_param_(\w+)", b)
        if not m:
            continue
        prefix, ident = m.group(1), m.group(2)
        if prefix != nom_plugin:
            continue
        tipus = "quantitzat" if "QuantizedParameter" in b else "numeric"
        vn = _valor(b, r"value_names\s*\(([^)]*)\)", "") or ""
        valors = re.findall(r'"([^"]*)"', vn)
        defs[f"plugbase:{prefix}_param_{ident}"] = {
            "id": _valor(b, r'vamp:identifier\s+"([^"]*)"', ident),
            "titol": _valor(b, r'dc:title\s+"([^"]*)"', ident),
            "tipus": tipus,
            "minim": float(_valor(b, r"min_value\s+([\d.]+)", "0")),
            "maxim": float(_valor(b, r"max_value\s+([\d.]+)", "1")),
            "pas": float(_valor(b, r"quantize_step\s+([\d.]+)",
                                "1" if tipus == "quantitzat" else "0")),
            "defecte": float(_valor(b, r"default_value\s+([\d.]+)", "0")),
            "valors": valors,
        }

    # 2) l'ordre en què el plugin els declara
    ordre = []
    for b in blocs:
        if re.match(rf"plugbase:{nom_plugin}\s+a\s+vamp:Plugin", b):
            ordre = re.findall(r"vamp:parameter\s+(plugbase:\w+)", b)
            break
    return [defs[r] for r in ordre if r in defs]


def params_de(clau):
    """Paràmetres del transform `clau` ('chords' | 'structure')."""
    n3, plugin = PLUGINS[clau]
    ruta = os.path.join(pipeline.PROJ_DIR, n3)
    if not os.path.exists(ruta):
        return []
    return llegeix_params(ruta, plugin)


def valors_per_defecte(clau):
    """{id: valor} amb els valors per defecte."""
    return {p["id"]: p["defecte"] for p in params_de(clau)}
