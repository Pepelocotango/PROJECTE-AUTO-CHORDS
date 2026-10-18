"""Higiene dels tests: cap temporal no s'ha de quedar pel disc.

`unittest discover` crea **centenars** de carpetes i WAVs temporals per tongada
(`tempfile.mkdtemp` / `mkstemp` / `NamedTemporaryFile`) i fins ara **no els
esborrava ningú**: una tongada deixava ~1.000 carpetes i ~1,3 GB a `/tmp`, i en
un dia de feina (amb diversos agents corrent la suite) s'hi van acumular **57 GB**
amb el disc al 97% (auditoria 18-10-2026).

Aquest mòdul, importat per tots els fitxers de test, **registra** els temporals
que es creen durant la tongada i els **esborra en acabar el procés**. No canvia
cap comportament dels tests: només recull el que ells ja no volen.

Regla de seguretat: només s'esborra el que haja quedat **dins el directori
temporal del sistema**; mai res de fora.
"""
import atexit
import os
import shutil
import tempfile

_creats = set()
_mkdtemp = tempfile.mkdtemp
_mkstemp = tempfile.mkstemp
_named = tempfile.NamedTemporaryFile
_arrel = os.path.abspath(tempfile.gettempdir()) + os.sep


def _apunta(ruta):
    """Anota `ruta` si és dins el temporal del sistema."""
    try:
        if os.path.abspath(ruta).startswith(_arrel):
            _creats.add(os.path.abspath(ruta))
    except (TypeError, ValueError):
        pass
    return ruta


def mkdtemp(*args, **kwargs):
    return _apunta(_mkdtemp(*args, **kwargs))


def mkstemp(*args, **kwargs):
    fd, ruta = _mkstemp(*args, **kwargs)
    _apunta(ruta)
    return fd, ruta


def NamedTemporaryFile(*args, **kwargs):
    f = _named(*args, **kwargs)
    _apunta(f.name)
    return f


# Es substitueixen a nivell de mòdul: qualsevol `import tempfile` els veu.
tempfile.mkdtemp = mkdtemp
tempfile.mkstemp = mkstemp
tempfile.NamedTemporaryFile = NamedTemporaryFile


def esborra():
    """Esborra els temporals anotats (els més pregons primer)."""
    for ruta in sorted(_creats, key=len, reverse=True):
        try:
            if os.path.isdir(ruta):
                shutil.rmtree(ruta, ignore_errors=True)
            elif os.path.exists(ruta):
                os.remove(ruta)
        except OSError:
            pass
    _creats.clear()


atexit.register(esborra)
