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

# Mode test: l'app no ha de llegir la llista de recents de l'usuari (si no, un
# test podria obrir el projecte d'un altre i contaminar-se).
import os as _os
_os.environ.setdefault("AUTO_CHORDS_TEST", "1")
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
# Prefix de les carpetes que l'app crea al costat de la WAV
# (`pipeline.PREFIX_SORTIDA`; es repeteix ací per no importar `app` en un mòdul
# que es carrega abans que res).
_PREFIX_APP = "AUTOCHORDS_"


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


def esborra(objectius=None):
    """Esborra els temporals anotats (els més pregons primer).

    `objectius` permet netejar només un subconjunt (ho fan els tests del propi
    mecanisme, per no interferir amb la resta de la tongada).
    """
    origens = set(_creats if objectius is None else objectius)
    a_esborrar = set(origens)
    for ruta in origens:
        a_esborrar.update(_germans_de_l_app(ruta))
    for ruta in sorted(a_esborrar, key=len, reverse=True):
        if not _es_dins_el_temporal(ruta):
            continue
        try:
            if os.path.isdir(ruta):
                shutil.rmtree(ruta, ignore_errors=True)
            elif os.path.exists(ruta):
                os.remove(ruta)
        except OSError:
            pass
    _creats.difference_update(origens)


def _es_dins_el_temporal(ruta):
    try:
        return os.path.abspath(ruta).startswith(_arrel)
    except (TypeError, ValueError):
        return False


def _germans_de_l_app(ruta):
    """Carpetes `AUTOCHORDS_<stem>` que l'app crea al costat d'una WAV temporal.

    `pipeline.carpeta_sortida()` retorna `<dir>/AUTOCHORDS_<nom-sense-ext>` i el
    qui exporta/edita fa `makedirs`. Quan la WAV és un `tempfile.mkstemp`
    (`/tmp/tmpXXXX.wav`), eixa carpeta queda directament a `/tmp` — **fora** de
    qualsevol directori registrat — i fins ara sobrevivia a la tongada (102
    carpetes buides per execució, detectat 2026-10-19).
    """
    ruta = os.path.abspath(ruta)
    base = os.path.splitext(os.path.basename(ruta))[0]
    return (os.path.join(os.path.dirname(ruta), _PREFIX_APP + base),)


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
