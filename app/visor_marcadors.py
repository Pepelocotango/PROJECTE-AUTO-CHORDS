"""Marcadors humans del visor (F4).

Extret de `app/visor.py`: alta, moviment i esborrat. Els marcadors són
anotacions independents: no participen en cap recalcul de tempo.
"""
from . import pipeline, tempo_map

class MarcadorsMixin:
    """Marcadors humans (anotacions)."""

    def _marcador_a(self, t, tol=0.05):
        """Índex del marcador humà que coincideix amb `t` (o `None`).

        0,05 s és prou per a emparellar-los sense confondre dos marcadors
        distints (entre ells sempre hi ha ≥ `SEPARACIO_MIN`).
        """
        t = float(t)
        for i, m in enumerate(self.marcadors or ()):
            if abs(float(m) - t) <= float(tol):
                return i
        return None

    def _mou_marcador(self, t_vell, t_nou):
        """Mou un marcador de manera independent (snap o edició manual).

        No toca cap clip de tempo ni d'estructura. Retorna `True` si el
        marcador existia i ha canviat.
        """
        from app import marcadors as M
        i = self._marcador_a(t_vell)
        if i is None:
            return False
        marques = [float(x) for x in (self.marcadors or ())]
        marques[i] = float(t_nou)
        nou = M.normalitza_marcadors(marques, self._durada_wav())
        if nou == list(self.marcadors or ()):
            return False
        tipus = self.marcador_tipus.pop(round(float(t_vell), 6), None)
        if tipus:
            self.marcador_tipus[round(float(t_nou), 6)] = tipus
        self.marcadors = nou
        self._pinta_marcadors()
        try:
            pipeline.desa_marcadors(
                self._carpeta_acords(),
                [(m, self.marcador_tipus.get(round(float(m), 6), "seccio"))
                 for m in (self.marcadors or [])])
        except OSError as e:
            self.log(f"marcadors: no s'han pogut desar ({e})")
        self.log(f"marcador mogut: {t_vell:.3f} → {t_nou:.3f}s")
        return True

    def _parteix_tempo_nou(self, t):
        """Retorna el mapa partit a `t` o `None` si no cal/possible.

        Primer intenta conservar el BPM/compàs. Si el tall deixa un dels
        clips afectats amb un nombre no enter de compassos, torna a partir
        amb el recalcul guiat (referència del mateix clip, no la global).
        """
        trams = list(self.tempo_trams or [])
        durada = self._durada_wav()
        offset = getattr(self, "offset", 0.0)
        kw = dict(offset=offset,
                  beats_qm=self._beats_per_validacio(),
                  permissiu=True, ref_base=None,
                  beat_factor=self.beat_factor())
        try:
            out = tempo_map.parteix_tram_marcador(
                trams, float(t), durada, recalculca=False, **kw)
        except ValueError:
            out = None
        if out is not None and len(out) != len(trams):
            # Si els dos costats queden en compassos sencers, no cal tocar
            # el BPM. Si no, apliquem el recalcul guiat.
            idx = next((i for i, tr in enumerate(trams)
                        if float(tr[0]) + 1e-9 < float(t)
                        < float(tr[1]) - 1e-9), None)
            if idx is not None:
                afectats = (idx, idx + 1)
                fraccionari = False
                for i in afectats:
                    if i >= len(out) or int(out[i][3]) <= 0:
                        continue
                    try:
                        nb = tempo_map.compassos_del_clip(out[i])
                    except (TypeError, ValueError):
                        continue
                    if abs(nb - round(nb)) > 1e-6:
                        fraccionari = True
                        break
                if not fraccionari:
                    return out
        try:
            out = tempo_map.parteix_tram_marcador(
                trams, float(t), durada, recalculca=True, **kw)
        except ValueError:
            return None
        return out if len(out) != len(trams) else None

    def _parteix_estructura_noves(self, t):
        """Retorna les seccions partides a `t` o `None` si no cal/possible."""
        t = float(t)
        for i, (ini, fi, _l, _f) in enumerate(self.seccions or ()):
            if float(ini) + self.MIN_SECCIO_S <= t <= float(fi) - self.MIN_SECCIO_S:
                try:
                    return self._normalitza_seccions(
                        pipeline.parteix_seccio(self.seccions, i, t))
                except ValueError:
                    return None
        return None

    def _talla(self, t, tempo=False, estructura=False):
        """Talla tempo i/o estructura en una sola operació d'undo."""
        t = float(t)
        nous_trams = self._parteix_tempo_nou(t) if tempo else None
        noves_seccions = self._parteix_estructura_noves(t) if estructura else None
        if nous_trams is None and noves_seccions is None:
            return False
        self._undo_marca()
        try:
            if nous_trams is not None:
                if not self.aplica_tempo_trams(nous_trams):
                    self._undo_commit()
                    return False
            if noves_seccions is not None:
                self.seccions = noves_seccions
                self._sincronitza_vista()
                if hasattr(self, "llista_ab"):
                    self._actualitza_llista_abc()
            self._desa_i_regenera()
        finally:
            self._undo_commit()
        return True

    def talla_tempo(self, t):
        """Enter: parteix només el clip de tempo (sense marcador/estructura)."""
        return self._talla(t, tempo=True)

    def talla_estructura(self, t):
        """0: parteix només el clip d'estructura (sense tempo/marcador)."""
        return self._talla(t, estructura=True)

    def talla_tempo_i_estructura(self, t):
        """+: parteix tempo i estructura, sense crear cap marcador."""
        return self._talla(t, tempo=True, estructura=True)

    def afegeix_marcador_lliure(self, t=None, tipus="marcador"):
        """M: afig només un marcador; no toca tempo ni estructura."""
        from app import marcadors as M
        t = float(self.pos if t is None else t)
        if not (0.0 < t < self._durada_wav() - 1e-3):
            return False
        abans = list(self.marcadors or ())
        marques = M.afegeix(abans, t, self._durada_wav())
        if marques == abans:
            return False
        tipus = tipus if tipus in ("marcador", "compas", "seccio") else "marcador"
        self._undo_marca()
        self.marcadors = marques
        self.marcador_tipus[round(float(t), 6)] = tipus
        self._undo_commit()
        self._pinta_marcadors()
        try:
            pipeline.desa_marcadors(
                self._carpeta_acords(),
                [(m, self.marcador_tipus.get(round(float(m), 6), "marcador"))
                 for m in (self.marcadors or ())])
        except OSError:
            pass
        return True

    def elimina_marcador(self, idx=None):
        """Esborra un marcador (per defecte, l'últim). Els clips NO es toquen."""
        from app import marcadors as M
        if not self.marcadors:
            return False
        idx = (len(self.marcadors) - 1) if idx is None else int(idx)
        abans = list(self.marcadors)
        marques = M.elimina(abans, idx)
        if marques == abans:
            return False
        self._undo_marca()
        self.marcadors = marques
        self._undo_commit()
        self._pinta_marcadors()
        try:
            pipeline.desa_marcadors(
                self._carpeta_acords(),
                [(m, self.marcador_tipus.get(round(float(m), 6), "seccio"))
                 for m in (self.marcadors or [])])
        except OSError:
            pass
        self.log(f"marcador esborrat (en queden {len(self.marcadors)})")
        return True

    def converteix_marcador(self, t, tipus_nou):
        """Converteix el marcador més pròxim a `t` al tipus indicat."""
        tipus_nou = tipus_nou if tipus_nou in ("compas", "seccio") else "seccio"
        mi = self._marcador_a(t)
        if mi is None:
            return False
        marques = list(self.marcadors or [])
        if not (0 <= mi < len(marques)):
            return False
        m = marques[mi]
        self._undo_marca()
        self.marcador_tipus[round(float(m), 6)] = tipus_nou
        self._pinta_marcadors()
        self._undo_commit()
        try:
            pipeline.desa_marcadors(
                self._carpeta_acords(),
                [(x, self.marcador_tipus.get(round(float(x), 6), "seccio"))
                 for x in (self.marcadors or [])])
        except OSError:
            pass
        self.log(f"marcador convertit a {tipus_nou}")
        return True


    def _canvia_marcador_llista(self, item):
        """Edita el temps o el tipus d'un marcador des de la llista."""
        if getattr(self, "_omplint_marcadors", False):
            return
        from app import marcadors as M
        fila = int(item.row())
        marques = list(self.marcadors or ())
        if not (0 <= fila < len(marques)):
            return
        vell = float(marques[fila])
        tipus = dict(getattr(self, "marcador_tipus", {}) or {})
        if int(item.column()) == 0:
            try:
                nou = float(str(item.text()).replace(",", "."))
            except ValueError:
                self._pinta_marcadors()
                return
            if not (0.0 < nou < self._durada_wav() - 1e-3):
                self._pinta_marcadors()
                return
            marques[fila] = nou
            marques = M.normalitza_marcadors(marques, self._durada_wav())
            vell_t = tipus.pop(round(vell, 6), None)
            if vell_t:
                tipus[round(nou, 6)] = vell_t
        else:
            nou_t = str(item.text()).strip()
            if nou_t not in ("marcador", "compas", "seccio"):
                self._pinta_marcadors()
                return
            tipus[round(vell, 6)] = nou_t
        self._undo_marca()
        self.marcadors = marques
        self.marcador_tipus = tipus
        self._undo_commit()
        self._pinta_marcadors()
        try:
            pipeline.desa_marcadors(
                self._carpeta_acords(),
                [(m, self.marcador_tipus.get(round(float(m), 6), "marcador"))
                 for m in (self.marcadors or ())])
        except OSError:
            pass

    def _elimina_marcador_llista(self):
        """Elimina el marcador seleccionat a la llista (tecla Del)."""
        t = getattr(self, "llista_marcadors", None)
        if t is None:
            return False
        fila = t.currentRow()
        if fila < 0:
            return False
        return bool(self.elimina_marcador(fila))

    def _menu_marcador_llista(self, pos):
        """Menú contextual de la llista de marcadors."""
        from PyQt5.QtWidgets import QMenu
        from app import marcadors as M
        item = self.llista_marcadors.itemAt(pos)
        if item is None:
            return
        fila = int(item.row())
        menu = QMenu(self)
        act = menu.addAction("Elimina el marcador")
        triat = menu.exec_(self.llista_marcadors.viewport().mapToGlobal(pos))
        if triat is act:
            self._undo_marca()
            self.marcadors = M.elimina(list(self.marcadors or ()), fila)
            self._undo_commit()
            self._pinta_marcadors()
            try:
                pipeline.desa_marcadors(
                    self._carpeta_acords(),
                    [(m, self.marcador_tipus.get(round(float(m), 6),
                                                 "marcador"))
                     for m in (self.marcadors or ())])
            except OSError:
                pass

    def _pinta_marcadors(self):
        tl = getattr(self, "timeline", None)
        if tl is not None and hasattr(tl, "set_marcadors"):
            marques = [(m, self.marcador_tipus.get(round(float(m), 6), "seccio"))
                       for m in (self.marcadors or [])]
            tl.set_marcadors(marques)
        if hasattr(self, "_omple_llista_marcadors"):
            self._omple_llista_marcadors()
