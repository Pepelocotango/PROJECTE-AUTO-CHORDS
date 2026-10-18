"""Metrònom: clics i accents, amb BPM fix i amb **mapa de tempo/compàs**.

Regla d'or #5: el mapa és la font del tempo. El metrònom ha de seguir-lo; abans
anava sempre amb el BPM fix de la barra i, a partir del primer canvi de tempo, es
desalineava (auditoria 18-10-2026).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

from app import metronom  # noqa: E402
from app import tempo_map as tm  # noqa: E402

SR = 44100


def _silenci(segons):
    return b"\x00\x00" * int(SR * segons)


def _clics(mono, llindar=1500):
    """Instants (s) on arrenca cada clic (les regions no nul·les)."""
    arr = np.abs(np.frombuffer(mono, dtype=np.int16))
    idx = np.flatnonzero(arr > llindar)
    if idx.size == 0:
        return []
    talls = np.flatnonzero(np.diff(idx) > SR // 50)   # 20 ms de separació
    inicis = np.concatenate(([idx[0]], idx[talls + 1]))
    return [round(i / SR, 2) for i in inicis]


class TestMetronom(unittest.TestCase):

    def test_sense_volum_no_toca_res(self):
        s = _silenci(2)
        self.assertEqual(metronom.mescla_metronom(s, SR, 0.0, 120.0, 4, 0.0), s)

    def test_bpm_fix_clics_cada_temps(self):
        """A 120 BPM el temps fa 0,5 s: clics a 0, 0,5, 1,0, 1,5…"""
        out = metronom.mescla_metronom(_silenci(2), SR, 0.0, 120.0, 4)
        self.assertEqual(_clics(out), [0.0, 0.5, 1.0, 1.5])

    def test_accent_al_primer_temps_del_compas(self):
        """El clic del temps 1 sona més fort que els altres (4/4 → cada 4)."""
        out = metronom.mescla_metronom(_silenci(2), SR, 0.0, 120.0, 4)
        arr = np.abs(np.frombuffer(out, dtype=np.int16))
        fort = arr[int(0.0 * SR):int(0.1 * SR)].max()
        fluix = arr[int(0.5 * SR):int(0.6 * SR)].max()
        self.assertGreater(fort, fluix)

    def test_amb_mapa_segueix_el_canvi_de_tempo(self):
        """Mapa 120 BPM (0–2 s) i 60 BPM (2–6 s): a partir de 2 s els clics van
        cada 1 s, no cada 0,5 (que és el que faria el BPM fix)."""
        mapa = tm.TempoMap([(0.0, 2.0, 120.0, 4, 4),
                            (2.0, 6.0, 60.0, 4, 4)])
        out = metronom.mescla_metronom(_silenci(6), SR, 0.0, 120.0, 4,
                                       mapa=mapa)
        clics = _clics(out)
        self.assertEqual(clics, [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0])

    def test_amb_mapa_constant_es_el_cami_de_sempre(self):
        mapa = tm.TempoMap([(0.0, 2.0, 120.0, 4, 4)])
        a = metronom.mescla_metronom(_silenci(2), SR, 0.0, 120.0, 4)
        b = metronom.mescla_metronom(_silenci(2), SR, 0.0, 120.0, 4,
                                     mapa=mapa)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
