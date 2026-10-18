#!/usr/bin/env python3
"""Corre la suite en ordre ALEATORI (o només la llista).

Per què: `unittest discover` corre els tests en un ordre FIX (alfabètic). Si
algun test depenguera de l'estat que deixa un altre (una QApplication, un
`tempdir`, una opció desada…), la suite passaria sempre i el problema només
eixiria en canviar d'ordre. Aquest script ho comprova.

Ús:
    .venv/bin/python eines/ordre_aleatori.py [seed] [--llista]

Sense arguments fa servir la seed 1. `--llista` només mostra l'ordre que tocaria
(i és el que permet provar l'script mateix sense córrer tota la suite).
"""
import argparse
import os
import random
import sys
import unittest

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _aplana(suite, desti):
    for t in suite:
        if isinstance(t, unittest.TestSuite):
            _aplana(t, desti)
        else:
            desti.append(t)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("seed", type=int, nargs="?", default=1,
                    help="llavor de l'atzar (defecte 1)")
    ap.add_argument("--llista", action="store_true",
                    help="només llista l'ordre i plega (sense executar)")
    a = ap.parse_args()

    os.chdir(ARREL)
    sys.path.insert(0, ARREL)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    random.seed(a.seed)
    # Igual que la comanda de sempre (`discover -s tests`) des de l'arrel.
    prove = unittest.TestLoader().discover("tests")
    tests = []
    _aplana(prove, tests)
    random.shuffle(tests)
    print(f"seed={a.seed} · {len(tests)} tests en ordre aleatori")
    if a.llista:
        for t in tests[:10]:
            print("  ", t.id())
        print("   …")
        return 0
    res = unittest.TextTestRunner(verbosity=1).run(unittest.TestSuite(tests))
    if not res.wasSuccessful():
        print("FALLADA amb ordre aleatori (seed=%d):" % a.seed)
        for t, _ in res.failures + res.errors:
            print("  ❌", t.id())
    return 0 if res.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
