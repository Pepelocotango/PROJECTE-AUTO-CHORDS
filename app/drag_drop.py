"""Fitxers d'àudio que es poden arrossegar des del gestor de fitxers.

Els 3 sistemes operatius publiquen els fitxers arrossegats com a **URLs**
(`text/uri-list`): Windows (Explorer), macOS (Finder) i Linux (Nautilus,
Dolphin, Thunar…) passen per `QUrl` i `QUrl.toLocalFile()` en dona la ruta
nativa, amb els accents i els espais ja desescapats. Alguns gestors o apps
només publiquen la ruta com a **text pla**, així que hi ha un fallback.

Aquest mòdul no toca la GUI: només interpreta el `QMimeData` d'un drag &
drop. Les rutes que retorna sempre són **fitxers locals existents** amb una
extensió d'àudio acceptada per `app.ffmpeg` (la mateixa que el diàleg
«Obre àudio»).
"""

import os

from PyQt5.QtCore import QUrl

from . import ffmpeg


def _extensio(ruta):
    return os.path.splitext(str(ruta))[1].lower().lstrip(".")


def es_audio(ruta):
    """Cert si `ruta` és un fitxer local amb una extensió d'àudio acceptada."""
    try:
        return (bool(ruta)
                and os.path.isfile(ruta)
                and _extensio(ruta) in set(ffmpeg.extensions()))
    except (OSError, TypeError, ValueError):
        return False


def _afegeix(out, vistos, ruta):
    """Afig `ruta` si és un fitxer existent i no l'havíem vist encara."""
    ruta = str(ruta or "").strip()
    if not ruta or not os.path.isfile(ruta):
        return
    clau = os.path.normcase(os.path.abspath(ruta))
    if clau in vistos:
        return
    vistos.add(clau)
    out.append(os.path.abspath(ruta))


def rutes(mime):
    """Rutes de fitxers locals del MIME, en ordre i sense duplicats.

    Prioritza `urls()`, que és el que fan servir els 3 SO. Si no n'hi ha,
    accepta un llistat de rutes en text pla (`text/uri-list` sense URLs,
    aplicacions que només copien el camí, etc.).
    """
    out = []
    vistos = set()
    if mime is None:
        return out
    try:
        if mime.hasUrls():
            for url in mime.urls():
                if isinstance(url, QUrl) and url.isLocalFile():
                    _afegeix(out, vistos, url.toLocalFile())
        if out:
            return out
        if mime.hasText():
            for linia in str(mime.text()).splitlines():
                linia = linia.strip()
                if not linia or linia.startswith("#"):
                    continue
                if linia.lower().startswith("file:"):
                    url = QUrl(linia)
                    if url.isLocalFile():
                        _afegeix(out, vistos, url.toLocalFile())
                else:
                    _afegeix(out, vistos, linia)
    except (OSError, TypeError, ValueError):
        pass
    return out


def rutes_audio(mime):
    """Subconjunt de `rutes(mime)` que són àudio obribles per l'app."""
    return [r for r in rutes(mime) if es_audio(r)]


def te_audio(mime):
    """Cert si el drag conté almenys un àudio que l'app puga obrir."""
    return bool(rutes_audio(mime))
