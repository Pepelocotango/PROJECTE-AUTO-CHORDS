"""Neteja ORDENADA dels objectes Qt entre tests.

Per què: un objecte Qt (QWidget / QMessageBox) amb cicles de referència Python
es destrueix quan vol el GARBAGE COLLECTOR — sovint dins d'un test POSTERIOR, en
un moment arbitrari → risc d'access violation (crash intermitent; es va veure en
aquesta suite). A més, `deleteLater()` SOL no n'hi ha prou: sense un event loop
en marxa, `QApplication.processEvents()` NO entrega els esdeveniments
`DeferredDelete` (comportament documentat de Qt 5) → la destrucció C++ continua
passant al GC. Cal `sendPostedEvents(None, QEvent.DeferredDelete)` + `gc.collect()`.

Ús recomanat (als mòduls de test que creen `Visor(...)`/`Finestra(...)`):

    def tearDownModule():
        import _qt_neteja
        _qt_neteja.processa_esborrats()

o, si es té una llista de finestres:

    _qt_neteja.tanca_i_destrueix(*finestres)
"""
import gc

from PyQt5.QtCore import QCoreApplication, QEvent
from PyQt5.QtWidgets import QApplication


def processa_esborrats():
    """Força el lliurament dels `DeferredDelete` pendents + un cicle de GC."""
    app = QApplication.instance()
    if app is not None:
        app.processEvents()
    # Qt 5: sense això, els deleteLater() queden a la cua i els destrueix el GC.
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    gc.collect()
    if app is not None:
        app.processEvents()


def tanca_i_destrueix(*finestres):
    """Tanca + destrueix (forçat i ordenat) un conjunt de finestres."""
    for w in finestres:
        try:
            w.close()
            w.deleteLater()
        except RuntimeError:
            pass
    processa_esborrats()
