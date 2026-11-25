"""Marcadors humans del visor (F4).

Extret de `app/visor.py`: alta, moviment i esborrat. Els marcadors són
anotacions independents: no participen en cap recalcul de tempo.
"""
from . import limits, mapa_tempo, pipeline, tempo_map

class MarcadorsMixin:
    """Marcadors humans (anotacions)."""

    def rang_analisi(self):
        """Retorna el rang dels marcadors d'anàlisi, o `None`."""
        from app import marcadors as M
        return M.rang_analisi(
            self.marcadors or (), self.marcador_tipus or {},
            self._durada_wav())

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

    def _inicia_tall_qm(self):
        """Guarda l'estat de play abans de qualsevol diàleg del tall QM."""
        if getattr(self, "_tall_qm_actiu", False):
            return
        self._tall_qm_actiu = True
        self._tall_qm_sonava = bool(getattr(self, "sona", False))
        self._tall_qm_pos = float(getattr(self, "pos", 0.0))
        self._tall_qm_pausat = False

    def _pausa_tall_qm(self):
        """Pausa el play una sola vegada per operació de tall QM."""
        self._inicia_tall_qm()
        if getattr(self, "sona", False) and not getattr(
                self, "_tall_qm_pausat", False):
            self.play_stop()
            self._tall_qm_pausat = True

    def _cancel·la_tall_qm(self):
        """Cancel·la la intenció de reprendre; deixa el play en pausa."""
        self._tall_qm_actiu = False
        self._tall_qm_sonava = False
        self._tall_qm_pausat = False

    def _reprén_tall_qm(self):
        """Reprén des de la posició guardada, només si sonava abans."""
        if not getattr(self, "_tall_qm_actiu", False):
            return
        sonava = bool(getattr(self, "_tall_qm_sonava", False))
        pos = float(getattr(self, "_tall_qm_pos", 0.0))
        self._tall_qm_actiu = False
        self._tall_qm_pausat = False
        self._tall_qm_sonava = False
        if sonava and not getattr(self, "sona", False):
            self.ves_a(pos)
            self.play_stop()

    def _tall_simple_si_enter(self, t, trams):
        """Partició òbvia: el tall cau en línia de compàs del clip actual.

        Conserva BPM/compàs i deixa els dos costats amb `N` enter. Estalvia el
        diàleg QM quan no hi ha res a decidir (el cas normal de «+»).
        """
        t = float(t)
        for i, tr in enumerate(trams):
            ini, fi = float(tr[0]), float(tr[1])
            if not (ini + 1e-9 < t < fi - 1e-9):
                continue
            bpm, num, den = (float(getattr(tr, "bpm", tr[2])),
                             int(getattr(tr, "num", tr[3])),
                             int(getattr(tr, "den", tr[4])))
            bar = tempo_map.durada_compas(bpm, num, den)
            if bar <= tempo_map.TOL:
                return None
            nl = (t - ini) / bar
            nr = (fi - t) / bar
            if (abs(nl - round(nl)) > 1e-3
                    or abs(nr - round(nr)) > 1e-3
                    or round(nl) < 1 or round(nr) < 1):
                return None
            esq = mapa_tempo.TramMapa(
                ini, t, bpm, getattr(tr, "tipus", "normal"),
                f"{num}/{den}", getattr(tr, "agrupacio", ""),
                int(round(nl)), getattr(tr, "beat_unit", None))
            dreta = mapa_tempo.TramMapa(
                t, fi, bpm, getattr(tr, "tipus", "normal"),
                f"{num}/{den}", getattr(tr, "agrupacio", ""),
                int(round(nr)), getattr(tr, "beat_unit", None))
            self.log(
                f"tall simple: {t:.3f}s · {num}/{den} · "
                f"{int(round(nl))}+{int(round(nr))} compassos")
            return trams[:i] + [esq, dreta] + trams[i + 1:]
        return None

    def _tall_qm_si_es_facil(self, t, trams, beats):
        """Tall QM amb decisió òbvia: esquerra a compàs + dreta de cua.

        Si el cursor cau sobre un beat QM i l'esquerra queda a prop d'un `N`
        enter, no cal obrir el diàleg: es conserva BPM/compàs del clip i, si
        el costat dret és l'últim, el seu `N` pot ser fraccionari.
        """
        t = float(t)
        for i, tr in enumerate(trams):
            ini, fi = float(tr[0]), float(tr[1])
            if not (ini + 1e-9 < t < fi - 1e-9):
                continue
            bpm, num, den = (float(getattr(tr, "bpm", tr[2])),
                             int(getattr(tr, "num", tr[3])),
                             int(getattr(tr, "den", tr[4])))
            bar = tempo_map.durada_compas(bpm, num, den)
            if bar <= tempo_map.TOL:
                return None
            nl = (t - ini) / bar
            nr = (fi - t) / bar
            # L'esquerra és un clip NO final: admet poca tolerància i
            # s'arredoneix a N enter; el normalitzador ajusta el BPM.
            if abs(nl - round(nl)) > 0.12 or round(nl) < 1:
                return None
            ultim = (i == len(trams) - 1)
            if not ultim and (abs(nr - round(nr)) > 0.12
                              or round(nr) < 1):
                return None
            bq = float(num) * 4.0 / float(den)
            bpm_esq = bq * int(round(nl)) * 60.0 / (t - ini)
            if not (limits.BPM_MIN <= bpm_esq <= limits.BPM_MAX):
                return None
            bar_esq = (t - ini) / int(round(nl))
            nr_esq = (fi - t) / bar_esq
            esq = mapa_tempo.TramMapa(
                ini, t, bpm_esq, getattr(tr, "tipus", "normal"),
                f"{num}/{den}", getattr(tr, "agrupacio", ""),
                int(round(nl)), getattr(tr, "beat_unit", None))
            dreta = mapa_tempo.TramMapa(
                t, fi, bpm_esq, getattr(tr, "tipus", "normal"),
                f"{num}/{den}", getattr(tr, "agrupacio", ""),
                (float(nr_esq) if ultim else float(round(nr_esq))),
                getattr(tr, "beat_unit", None))
            self.log(
                f"tall QM simple: {t:.3f}s · {num}/{den} · "
                f"{int(round(nl))}+{'cua ' + format(nr, '.3f') if ultim else int(round(nr))}")
            return trams[:i] + [esq, dreta] + trams[i + 1:]
        return None

    def _parteix_tempo_nou(self, t, trams=None):
        """Retorna el mapa partit a `t` o `None` si no cal/possible.

        Amb Snap QM usa el motor de candidats de `tall_qm`: beats per costat,
        BPM/compàs/N i diàleg si hi ha més d'una opció. Sense QM conserva el
        camí anterior. `trams` permet encadenar talls sense aplicar-los.
        """
        base = self.tempo_trams if trams is None else trams
        trams = list(base or [])
        durada = self._durada_wav()
        beats = list(self._beats_per_validacio() or ())
        self._tall_qm_cancelat = False
        if beats:
            rapid = self._tall_simple_si_enter(t, trams)
            if rapid is None:
                rapid = self._tall_qm_si_es_facil(t, trams, beats)
            if rapid is not None:
                return rapid
            from . import tall_qm
            self._inicia_tall_qm()
            try:
                idx = next(i for i, tr in enumerate(trams)
                           if float(tr[0]) + 1e-9 < float(t)
                           < float(tr[1]) - 1e-9)
            except StopIteration:
                return None
            tr = trams[idx]
            factor = self.beat_factor(self.unitat_de_tram(tr))
            costats = tall_qm.opcions_tall(
                trams, float(t), durada, beats,
                self.referencia_tempo_a(t), factor)
            if costats is None:
                self._cancel·la_tall_qm()
                self.avis_editor(
                    "Tall QM: no hi ha cap combinació exacta per a este punt.")
                return None
            return self._tria_opcions_tall_qm(trams, idx, costats)
        if (getattr(self, "snap_on", False)
                and getattr(self, "snap_mode", "") == "qm_beats"):
            rapid = self._tall_simple_si_enter(t, trams)
            if rapid is not None:
                return rapid
            from . import tall_qm
            self._inicia_tall_qm()
            try:
                idx = next(i for i, tr in enumerate(trams)
                           if float(tr[0]) + 1e-9 < float(t)
                           < float(tr[1]) - 1e-9)
            except StopIteration:
                return None
            costats = tall_qm.opcions_tall_graella(
                trams, getattr(self, "tempo_map", None),
                float(t), durada, self.referencia_tempo_a(t))
            if costats is None:
                self._cancel·la_tall_qm()
                self.avis_editor(
                    "Tall QM: no hi ha cap combinació vàlida amb la graella.")
                return None
            return self._tria_opcions_tall_qm(trams, idx, costats)
        # Sense Snap QM: recalcula sempre els dos costats amb la referència
        # del clip (com feia el «+» de v0.9.1). Així no queda una solució
        # fraccionària ni s'accepta una partició pitjor només perquè ja era
        # quasi sencera.
        try:
            out = tempo_map.parteix_tram_marcador(
                trams, float(t), durada, recalculca=True,
                beats_qm=None, permissiu=True,
                ref_base=None,
                beat_factor=self.beat_factor(),
                permet_ultim_fraccionari=True)
        except ValueError:
            return None
        return out if len(out) != len(trams) else None

    def _tria_opcions_tall_qm(self, trams, idx, costats):
        """Filtra, pregunta si cal i retorna el mapa amb els clips triats."""
        from . import tall_qm
        costats = [tall_qm.selecciona_opcions(o) for o in costats]
        # Si l'esquerra és única i la dreta de l'últim clip té la cua
        # fraccionària, no cal preguntar: la cua preserva BPM/compàs i N obert.
        cua_unica = (len(costats[0]) == 1 and costats[1]
                     and costats[1][0].get("ultima_fraccionaria"))
        if any(len(o) > 1 for o in costats) and not cua_unica:
            self._pausa_tall_qm()
            from .dialeg_tall_qm import DialegTallQM
            dlg = DialegTallQM(self, costats[0], costats[1])
            if not dlg.exec_():
                self._tall_qm_cancelat = True
                self._cancel·la_tall_qm()
                return None
            sel_esq, sel_dreta = dlg.seleccions()
        else:
            sel_esq = sel_dreta = 0
        triades = (list(costats[0][sel_esq]["clips"])
                   + list(costats[1][sel_dreta]["clips"]))
        self.log(
            "Tall QM: " + " | ".join(
                costats[j][sel]["etiqueta"]
                for j, sel in ((0, sel_esq), (1, sel_dreta))))
        return trams[:idx] + triades + trams[idx + 1:]

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
        if tempo and nous_trams is None:
            # Atòmic: si el tempo no s'ha pogut tallar (o s'ha cancel·lat el
            # diàleg), no es parteix només l'estructura.
            return False
        noves_seccions = self._parteix_estructura_noves(t) if estructura else None
        if nous_trams is None and noves_seccions is None:
            return False
        self._undo_marca()
        try:
            if nous_trams is not None:
                if not self.aplica_tempo_trams(nous_trams):
                    self._cancel·la_tall_qm()
                    return False
            if noves_seccions is not None:
                self.seccions = noves_seccions
                self._sincronitza_vista()
                if hasattr(self, "llista_ab"):
                    self._actualitza_llista_abc()
            self._desa_i_regenera()
        except Exception:
            self._cancel·la_tall_qm()
            raise
        finally:
            self._undo_commit()
        self._reprén_tall_qm()
        return True

    def talla_tempo(self, t):
        """Fin: parteix només el clip de tempo (sense marcador/estructura)."""
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
        tipus = (tipus if tipus in M.TIPUS_VALIDS else "marcador")
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
        from app import marcadors as M
        tipus_nou = (tipus_nou if tipus_nou in M.TIPUS_VALIDS else "seccio")
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
            if not M.es_tipus_valid(nou_t):
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
