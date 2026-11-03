"""bpm_unit.py — unitat de visualització del BPM (negra, negra amb punt…).

El MODEL i tots els càlculs de tempo treballen sempre en **negres per minut**.
Este mòdul només convertix eixa veritat interna a la unitat que l'usuari vol
vore o escriure (per exemple, `55` negres amb punt = `82.5` negres/min).

Així la graella, el metrònom, `TempoMap` i els CSV no canvien: canvia només la
capa de presentació.
"""
from __future__ import annotations

#: Claus estables (les que es guarden al `.acproj`).
DEFECTE = "negra"

#: `clau: (etiqueta, negres per unitat)`.
UNITATS = {
    "negra": ("Negra", 1.0),
    "negra_punt": ("Negra amb punt", 1.5),
    "corxera": ("Corxera", 0.5),
    "blanca": ("Blanca", 2.0),
}


def normalitza(unitat):
    """Retorna una clau vàlida; qualsevol valor estrany cau a `negra`."""
    return unitat if unitat in UNITATS else DEFECTE


def etiqueta(unitat):
    """Etiqueta humana de la unitat (per a la UI)."""
    return UNITATS[normalitza(unitat)][0]


def factor(unitat):
    """Negres que val una unitat (negra=1, negra amb punt=1.5…)."""
    return UNITATS[normalitza(unitat)][1]


def a_quarter(bpm_mostra, unitat):
    """BPM en la unitat mostrada → BPM intern en negres/minut."""
    return float(bpm_mostra) * factor(unitat)


def de_quarter(bpm_quarter, unitat):
    """BPM intern en negres/minut → BPM en la unitat mostrada."""
    return float(bpm_quarter) / factor(unitat)


def formata(bpm_quarter, unitat, decimals=3):
    """Text del BPM per a la UI, ja convertit a la unitat."""
    return f"{de_quarter(bpm_quarter, unitat):.{int(decimals)}f}"


def opcions():
    """`[(clau, etiqueta), …]` en l'orde de la UI."""
    return [(clau, dades[0]) for clau, dades in UNITATS.items()]


def encaixa_en_compas(unitat, num, den, tolerancia=1e-9):
    """True si la unitat de clic dividix exactament un compàs `num/den`.

    `auto` sempre encaixa (és el denominador). Una unitat més gran que el
    compàs o que no el dividix (p. ex. negra amb punt en 4/4) no encaixa.
    """
    unitat = normalitza(unitat) if unitat not in (None, "", "auto") else "auto"
    if unitat == "auto":
        return True
    try:
        num, den = int(num), int(den)
    except (TypeError, ValueError):
        return False
    if num <= 0 or den <= 0:
        return False
    barra = float(num) * 4.0 / float(den)
    pas = factor(unitat)
    if pas <= 0 or pas > barra + tolerancia:
        return False
    quocient = barra / pas
    return abs(quocient - round(quocient)) <= tolerancia
