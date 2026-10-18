"""Simula WINDOWS per provar `plataforma.bloqueja_instancia_unica`.

El bloqueig d'instància única a Windows fa servir `msvcrt.locking`, que **no
existeix a Linux**. Aquí l'injectem amb un **doble** de `msvcrt` i simulem el
seu comportament, perquè aquesta classe d'error es caçi **a Linux** (sense
dependre que el CI de Windows hi sigui):

- `locking(fd, LK_NBLCK, 1)` bloqueja la regió **[posició actual, +1)** del
  **fitxer** (no del fd): dues obertures del mateix fitxer comparteixen el lock.
- **Escriure** en una regió bloquejada **llança `OSError`** (com fa Windows).

Amb això, dos bugs reals queden coberts:
1. si el `write`/`locking` no van dins el `try` → el test peta en lloc de
   retornar `False` (ERROR);
2. si el `locking` bloqueja un offset diferent del que allibera `desbloqueja`
   → el lock penja i el test falla (la 2a instància no el pot tornar a agafar).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene dels tests: l'import té efecte (esborra els temporals en plegar)

from app import plataforma  # noqa: E402


class _FakeMsvcrt:
    """Doble de `msvcrt`: bloqueig per regió `(fitxer, offset)`."""

    LK_NBLCK = 2
    LK_UNLCK = 0

    def __init__(self):
        self._fitxers = {}          # fd -> _FitxerFals
        self._bloquejats = set()    # {(fitxer_id, offset)}

    def registrar(self, fitxer):
        self._fitxers[fitxer.fileno()] = fitxer

    def esta_bloquejat(self, fitxer_id, offset):
        return (fitxer_id, offset) in self._bloquejats

    def locking(self, fd, mode, nbytes):
        fx = self._fitxers[fd]
        clau = (fx.fitxer_id, fx.posicio())
        if mode == self.LK_NBLCK:
            if clau in self._bloquejats:
                raise OSError(13, "regió ja bloquejada")
            self._bloquejats.add(clau)
        elif mode == self.LK_UNLCK:
            self._bloquejats.discard(clau)


class _FitxerFals:
    """Fitxer fals: `write()` peta si la regió actual està bloquejada."""

    def __init__(self, fake, fitxer_id, fd):
        self.fake = fake
        self.fitxer_id = fitxer_id
        self._fd = fd
        self._pos = 0
        fake.registrar(self)

    def seek(self, n):
        self._pos = int(n)

    def write(self, s):
        if self.fake.esta_bloquejat(self.fitxer_id, self._pos):
            raise OSError(13, "escriure en una regió bloquejada")
        self._pos += len(s)

    def flush(self):
        pass

    def fileno(self):
        return self._fd

    def posicio(self):
        return self._pos


class TestLockWindowsSimulat(unittest.TestCase):
    def setUp(self):
        self.msv = _FakeMsvcrt()
        sys.modules["msvcrt"] = self.msv          # `import msvcrt` dins la funció
        self._orig = plataforma.ES_WINDOWS
        plataforma.ES_WINDOWS = True

    def tearDown(self):
        plataforma.ES_WINDOWS = self._orig
        sys.modules.pop("msvcrt", None)

    def test_segona_instancia_rebutjada(self):
        f1 = _FitxerFals(self.msv, "tema", fd=1)
        self.assertTrue(plataforma.bloqueja_instancia_unica(f1))
        # 2a obertura del MATEIX fitxer: escriure/bloquejar la regió ja
        # bloquejada ha de donar False (no petar).
        f2 = _FitxerFals(self.msv, "tema", fd=2)
        self.assertFalse(plataforma.bloqueja_instancia_unica(f2))
        # En alliberar el primer, el segon JA el pot agafar (el lock no penja).
        plataforma.desbloqueja(f1)
        self.assertTrue(plataforma.bloqueja_instancia_unica(f2))
        plataforma.desbloqueja(f2)

    def test_desbloqueja_allibera_la_mateixa_regio(self):
        f = _FitxerFals(self.msv, "tema", fd=3)
        self.assertTrue(plataforma.bloqueja_instancia_unica(f))
        self.assertTrue(self.msv.esta_bloquejat("tema", 0))   # offset 0
        plataforma.desbloqueja(f)
        self.assertFalse(self.msv.esta_bloquejat("tema", 0))  # alliberat

    def test_desbloqueja_es_best_effort(self):
        # Mai ha de llançar, ni amb un fitxer sense `locking` disponible.
        plataforma.desbloqueja(None)
        f = _FitxerFals(self.msv, "tema", fd=4)   # sense bloquejar prèviament
        plataforma.desbloqueja(f)                 # no ha de petar


if __name__ == "__main__":
    unittest.main()
