"""Tests del loop SENSE TALL (Opció A): el fil d'alimentació fa la volta del
loop ell mateix, en un flux continu, sense reiniciar el reproductor.

Provem `Visor._alimenta` amb un reproductor fals i àudio constant: si hi hagués
un «tall», apareixeria silenci (zeros) al punt de la volta.
"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.visor import Visor  # noqa: E402


class _FakeStdin:
    def __init__(self, limit_bytes):
        self.buf = bytearray()
        self.limit = limit_bytes
        self.tancat = False

    def write(self, b):
        self.buf += b
        if len(self.buf) >= self.limit:
            raise BrokenPipeError("límit de prova")

    def close(self):
        self.tancat = True


class _FakeProc:
    def __init__(self, limit_bytes):
        self.stdin = _FakeStdin(limit_bytes)

    def poll(self):
        return None


class _Doble:
    """Doble del Visor amb només el que `_alimenta` necessita."""

    FADE_LOOP_S = 0.004

    def __init__(self, mono, sr, loop=None):
        self.audio = {"sr": sr, "durada": len(mono) / sr}
        self._mono = np.asarray(mono, dtype=np.int16).tobytes()
        self._sess = 0
        self.loop_on = loop is not None
        self.loop_a, self.loop_b = loop if loop else (None, None)
        self.mut = False
        self.vol = 1.0
        self.metro_on = False
        self.metro_vol = 0.6
        self.bpm, self.bpb, self.offset = 120.0, 4, 0.0

    def _mono_bytes(self):
        return self._mono


def _max_run_zeros(data):
    run = mx = 0
    for v in (data == 0):
        run = run + 1 if v else 0
        if run > mx:
            mx = run
    return mx


class TestLoopContinu(unittest.TestCase):
    def test_sense_loop_alimenta_fins_al_final(self):
        doble = _Doble(np.full(2000, 1000, dtype=np.int16), 1000)
        proc = _FakeProc(10_000_000)
        Visor._alimenta(doble, proc, 0.0, 0)
        data = np.frombuffer(bytes(proc.stdin.buf), dtype=np.int16)
        self.assertEqual(data.size, 2000)         # tot el tema, un sol cop
        self.assertTrue(proc.stdin.tancat)

    def test_loop_fa_voltes_sense_tall(self):
        sr = 1000
        doble = _Doble(np.full(2000, 1000, dtype=np.int16), sr,
                       loop=(0.1, 0.2))            # A=100, B=200 (100 mostres)
        proc = _FakeProc(5000)                     # ~25 voltes
        Visor._alimenta(doble, proc, 0.15, 0)      # comença a mig loop
        data = np.frombuffer(bytes(proc.stdin.buf), dtype=np.int16)

        # (1) Ha fet MOLTES voltes (més enllà de la primera passada)
        self.assertGreater(data.size, 2000)
        # (2) El cos del loop sona PLE (no hi ha buit): el valor màxim és ple
        self.assertEqual(int(data.max()), 1000)
        # (3) No hi ha CAP buit real: els zeros (micro-fade als extrems) estan
        #     aïllats, mai en ratxes → si hi hagués un tall, hi hauria un bloc
        #     llarg de zeros.
        self.assertLessEqual(_max_run_zeros(data), 2)

    def test_loop_canvi_en_calell(self):
        # Si A/B canvien a mig flux, el feeder ho agafa a la volta següent.
        doble = _Doble(np.full(2000, 1000, dtype=np.int16), 1000,
                       loop=(0.1, 0.2))
        proc = _FakeProc(1200)
        doble.loop_a, doble.loop_b = 0.3, 0.4     # canvi (300..400) abans de res
        Visor._alimenta(doble, proc, 0.35, 0)
        data = np.frombuffer(bytes(proc.stdin.buf), dtype=np.int16)
        self.assertEqual(int(data.max()), 1000)   # segueix ple, sense tall


if __name__ == "__main__":
    unittest.main()
