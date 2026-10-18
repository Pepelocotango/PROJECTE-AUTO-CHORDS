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
import time

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


def escombra_residus(hores=12):
    """Treu els temporals VELLS que han deixat tongades mortes (kill/crash).

    Una tongada que mor a mitges (SIGKILL, tancament de sessio, crash) no pot
    executar l'`atexit`, aixi que deixa el seu directori. Aixo ho recull.

    Seguretat: nomes mira el patro `tmp*` **del temporal del sistema**,
    **propietat de l'usuari** i **mes vell que `hores`** — una tongada en curs
    (meua o d'un company) te els temporals JOVES i no se li toca res.
    """
    try:
        arrel = tempfile.gettempdir()
        ara = time.time()
        for nom in os.listdir(arrel):
            if not nom.startswith("tmp"):
                continue
            ruta = os.path.join(arrel, nom)
            try:
                st = os.stat(ruta)
                if st.st_uid != os.getuid():
                    continue
                if st.st_mtime >= ara - hores * 3600:
                    continue
                if os.path.isdir(ruta):
                    shutil.rmtree(ruta, ignore_errors=True)
                else:
                    os.remove(ruta)
            except OSError:
                pass
    except OSError:
        pass


# A l'INICI de la tongada, escombra el que hagen deixat les tongades mortes.
escombra_residus()
atexit.register(esborra)
