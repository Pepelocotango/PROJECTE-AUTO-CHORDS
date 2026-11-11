"""Façana dels diàlegs d'AUTO CHORDS.

Re-exporta els diàlegs i les opcions perquè `app.dialegs.X` continue
funcionant igual que abans.
"""
from .opcions import (  # noqa: F401
    AJUDA_CA, BEATS_DEFECTES, DEFECTES, FITXER_OPCIONS, NOMS_CA, VALORS_CA,
    carrega_opcions, desa_opcions,
)
from .dialeg_opcions import DialegOpcions  # noqa: F401
from .dialeg_troba import DialegTrobaReemplaca  # noqa: F401
from .dialeg_quantitza import DialegQuantitza  # noqa: F401
from .dialeg_tempo_mapa import DialegTempoMapa  # noqa: F401
from .dialeg_tram_tempo import DialegTramTempo  # noqa: F401
from .dialeg_tempo_per_trams import DialegTempoPerTrams  # noqa: F401
from .dialeg_analitza_bpm import DialegAnalitzaBPM  # noqa: F401

__all__ = [
    "DialegOpcions", "DialegTrobaReemplaca", "DialegQuantitza",
    "DialegTempoMapa", "DialegTramTempo", "DialegTempoPerTrams",
    "DialegAnalitzaBPM",
    "DEFECTES", "BEATS_DEFECTES", "FITXER_OPCIONS", "NOMS_CA", "AJUDA_CA",
    "VALORS_CA", "carrega_opcions", "desa_opcions",
]
