"""Configuració de dreceres de la finestra (menú, globals i timeline)."""
from __future__ import annotations

import re

from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QDialog

from . import dreceres
from .dialeg_dreceres import DialegDreceres


def _slug(text):
    return re.sub(r"\W+", "_", str(text or "").replace("&", "")).strip("_").lower()


class DreceresMixin:
    """Catàleg, aplicació i persistència de les dreceres."""

    def _inicialitza_dreceres(self):
        self._dreceres_cataleg = {}
        self._bindings = dreceres.carrega()
        for clau, meta in dreceres.DEFECTES.items():
            self._registra_drecera(
                clau, meta["etiqueta"], meta["grup"], meta["defecte"],
                meta["tipus"])

    def _registra_drecera(self, clau, etiqueta, grup, defecte="",
                          tipus="menu", objecte=None, conflicte=True):
        """Registra una acció al catàleg (i opcionalment el seu giny)."""
        if not hasattr(self, "_dreceres_cataleg"):
            self._dreceres_cataleg = {}
        self._dreceres_cataleg[clau] = {
            "id": clau,
            "etiqueta": str(etiqueta).replace("&", ""),
            "grup": str(grup or ""),
            "defecte": dreceres.normalitza(defecte),
            "tipus": tipus,
            "objecte": objecte,
            "conflicte": bool(conflicte),
        }

    def _vincula_drecera(self, clau, objecte):
        """Associa un QAction/QShortcut ja creat a una entrada del catàleg."""
        meta = getattr(self, "_dreceres_cataleg", {}).get(clau)
        if meta is not None:
            meta["objecte"] = objecte

    def _valor_drecera(self, clau):
        meta = getattr(self, "_dreceres_cataleg", {}).get(clau) or {}
        defecte = meta.get("defecte", "")
        return self._bindings.get(clau, defecte)

    def _mapa_timeline(self):
        return {clau: self._valor_drecera(clau)
                for clau in getattr(self, "_dreceres_cataleg", {})}

    def _aplica_dreceres(self):
        """Aplica els valors efectius als QAction/QShortcut i al timeline."""
        for clau, meta in getattr(self, "_dreceres_cataleg", {}).items():
            seq = QKeySequence(self._valor_drecera(clau) or "")
            obj = meta.get("objecte")
            if obj is None:
                continue
            if meta.get("tipus") == "shortcut":
                obj.setKey(seq)
            else:
                obj.setShortcut(seq)
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            if hasattr(vr, "_sc_play"):
                vr._sc_play.setKey(QKeySequence(
                    self._valor_drecera("global.play") or ""))
            if hasattr(vr, "timeline"):
                vr.timeline.set_dreceres(self._mapa_timeline())

    def _cataleg_llista(self):
        """Entrades per al diàleg, ordenades per grup i etiqueta."""
        out = []
        for clau, meta in getattr(self, "_dreceres_cataleg", {}).items():
            e = dict(meta)
            e["valor"] = self._valor_drecera(clau)
            out.append(e)

        def ordre(e):
            grup = e.get("grup") or ""
            prioritat = 0 if grup in ("Global", "Editor", "Timeline") else 1
            return (prioritat, grup, e.get("etiqueta") or "")
        out.sort(key=ordre)
        return out

    def _obre_config_dreceres(self):
        dlg = DialegDreceres(self, self._cataleg_llista())
        if dlg.exec_() != QDialog.Accepted:
            return
        self._bindings = dict(dlg.bindings)
        self._aplica_dreceres()
        try:
            ruta = dreceres.desa(self._bindings)
        except OSError as e:
            self.avisa("Dreceres",
                       f"S'han aplicat, però no s'han pogut desar:\n{e}")
            return
        self.registra(f"Dreceres desades: {ruta}")

    def _coincideix_drecera(self, clau, event):
        return dreceres.coincideix(self._valor_drecera(clau), event)
