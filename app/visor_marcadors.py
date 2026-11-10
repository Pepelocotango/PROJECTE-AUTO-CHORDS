"""Marcadors humans del visor (F4).

Extret de `app/visor.py`: alta, moviment, esborrat, snap i BPM derivat dels
marcadors.
"""
from . import bpm_unit as bpm_unit_mod
from . import mapa_tempo, pipeline, tempo_map, tempo_recalc

class MarcadorsMixin:
    """Marcadors humans i BPM derivat."""

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

    def afegeix_marcador(self, t=None, tipus="seccio"):
        """Crea un marcador i parteix tempo+estructura (camí de compatibilitat).

        La UI nova no usa este mètode: `+` parteix tempo+estructura sense
        marcador, `M` crea només el marcador i `Enter`/`0` fan talls parcials.
        Els marcadors creats ací ja no queden lligats a cap frontera.
        """
        tipus = tipus if tipus in ("compas", "seccio") else "seccio"
        from app import marcadors as M
        durada = self._durada_wav()
        t = float(self.pos if t is None else t)
        if not (0.0 < t < durada - 1e-3):
            return False
        abans = list(self.marcadors or [])
        marques = M.afegeix(abans, t, durada)
        if marques == abans:
            return False
        trams = list(self.tempo_trams or [(0.0, durada, self.bpm, self.bpb,
                                           getattr(self, "beat_type", 4))])
        try:
            bpm_ref = float(self.tempo_map.bpm(t))
        except (AttributeError, TypeError, ValueError):
            bpm_ref = float(self.bpm)
        avisos = []
        try:
            trams = tempo_map.parteix_tram_marcador(
                trams, t, durada, offset=getattr(self, "offset", 0.0),
                bpm_ref=bpm_ref, beats_qm=self._beats_per_validacio(),
                permissiu=True, recalculca=True,
                ref_base=self.ref_tempo_base(), avisos=avisos,
                beat_factor=self.beat_factor())
        except ValueError as e:
            self.avis_editor(f"Marcador: {e}")
            return False
        try:
            trams = self._normalitza_mapa_viu(trams, "Marcador")
        except ValueError as e:
            self.avis_editor(f"Marcador: {e}")
            return False
        seccions = list(self.seccions or [])
        if tipus == "seccio":
            idx = next((i for i, s in enumerate(seccions)
                        if float(s[0]) + 1e-6 < t < float(s[1]) - 1e-6), None)
            if idx is not None:
                try:
                    seccions = pipeline.parteix_seccio(
                        seccions, idx, t, marge=self.MIN_SECCIO_S)
                except ValueError as e:
                    self.log(f"marcador: no s'ha pogut partir l'estructura ({e})")
                    seccions = list(self.seccions or [])
        self._undo_marca()
        self.marcadors = marques
        self.marcador_tipus[round(float(t), 6)] = tipus
        if [tuple(x) for x in trams] != [tuple(x) for x in
                                         (self.tempo_trams or [])]:
            # El marcador pot afegir un tram a un mapa que ja té rubatos:
            # el guard genèric no ha de bloquejar un tall explícit de l'usuari.
            # `parteix_tram_marcador` treballa amb 5 tuples i perd el tipus;
            # reenganxem els rubatos abans d'aplicar el mapa.
            trams = mapa_tempo.reenganxa_metadades(self.tempo_trams or [], trams)
            self.aplica_tempo_trams(trams, forcat=True)
            for avis in avisos:
                self.avis_editor(f"Marcador: {avis}")
        if seccions != list(self.seccions or []):
            self.seccions = self._normalitza_seccions(seccions)
        self._undo_commit()
        self._pinta_marcadors()
        self._sincronitza_vista()
        try:
            pipeline.desa_marcadors(
                self._carpeta_acords(),
                [(m, self.marcador_tipus.get(round(float(m), 6), "seccio"))
                 for m in (self.marcadors or [])])
        except Exception as e:  # noqa: BLE001
            self.log(f"marcadors: no s'han pogut desar ({e})")
        self.log(f"marcador a {t:.3f}s (n'hi ha {len(self.marcadors)})")
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
                        nb = tempo_map._compassos_del_tram(
                            out[i], i, offset)
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

    def candidats_bpm_marcadors(self, preferit=None, num=None, den=None,
                                bpm_min=60.0, bpm_max=180.0):
        """BPMs compatibles amb els marcadors (tots els talls enters).

        `preferit` = BPM de la barra: servix per a ordenar els candidats (no
        decidix res: l'ambigüitat doble/meitat la resol l'operador).
        """
        from app import marcadors as M
        num = self.bpb if num is None else num
        den = getattr(self, "beat_type", 4) if den is None else den
        preferit = self.bpm if preferit is None else preferit
        _, num, den = tempo_map.valida_tempo(preferit, num, den)
        return M.candidats_bpm(
            list(self.marcadors or ()), num, den, bpm_min, bpm_max,
            preferit=float(preferit))

    def aplica_bpm_marcadors(self, candidat, num=None, den=None):
        """Reescriu el mapa amb el BPM deduït dels marcadors (1 sol desfer).

        Cada interval entre marcadors passa a tindre **exactament `k`
        compassos** al BPM del propi interval: així totes les fronteres cauen
        en línia de compàs i els clips de tempo/compàs tornen a ser editables.
        El «cap» (abans del 1r marcador) va amb el primer BPM i l'offset passa a
        ser el primer marcador.
        """
        from app import marcadors as M
        ms = M.normalitza_marcadors(list(self.marcadors or ()),
                                    self._durada_wav())
        if len(ms) < 2:
            self.avis_editor("Calen almenys dos marcadors per a traure el BPM")
            return False
        num = self.bpb if num is None else num
        den = getattr(self, "beat_type", 4) if den is None else den
        try:
            bpm_ref, num, den = tempo_map.valida_tempo(
                candidat.get("bpm"), num, den)
        except (AttributeError, ValueError) as e:
            self.avis_editor(f"BPM marcadors: {e}")
            return False
        durada = self._durada_wav()
        inter = list(candidat.get("intervals") or ())
        if len(inter) != len(ms) - 1:
            self.log("BPM marcadors: els intervals no quadren amb els marcadors")
            return False
        # Els marcadors fixen el nombre de compassos de cada interval; el
        # recalcul només pot moure BPM i compàs. La referència és la MANUAL de
        # la barra 2, no la del clip ni el compàs del diàleg.
        beats = sorted(float(b) for b in
                       (getattr(self, "qm_beats", None) or ()))
        ref_bpm, ref_num, ref_den = self.ref_tempo_base()
        factor = bpm_unit_mod.factor(getattr(self, "beat_unit", "negra"))
        avisos = []

        def _tram(dt, k, bpm_i, nb=None):
            # Si hi ha beats detectats, manen sobre el nombre de compassos
            # estimat pels marcadors: 7 beats són 7/4, no 2×4/4. `nb` ja ve
            # en NEGRES (factor de la unitat aplicat pel helper).
            _ = float(bpm_i)      # el candidat dels marcadors ja no és la ref
            r = tempo_recalc.recalculca_tram(
                dt, ref_bpm, int(ref_num), int(ref_den),
                n_ref=int(k) if nb is None else None, n_beats=nb,
                pas_beat=factor)
            if r is None:
                return (float(bpm_i), int(num), int(den))
            texto = tempo_recalc.avis_de_resultat(r)
            if texto:
                avisos.append(f"Interval {int(k)} ({float(dt):.3f}s): {texto}")
            return (float(r["bpm"]), int(r["num"]), int(r["den"]))

        bpm0, num0, den0 = _tram(float(inter[0][0]), int(inter[0][1]),
                                 float(inter[0][2]))
        trams = [(0.0, float(ms[0]), bpm0, num0, den0)]
        ini = float(ms[0])
        for dt, k, bpm_i in inter:
            fi = ini + float(dt)
            if beats:
                for b in tempo_recalc.beats_a_la_frontera(beats, ini, fi):
                    x = ini if abs(b - ini) <= abs(b - fi) else fi
                    text = (
                        f"Frontera {x:.3f}s: beat a {b:.3f}s dins la "
                        f"tolerància de "
                        f"{tempo_recalc.TOL_TALL * 1000:.0f} ms; recompte "
                        "ambigu (activa snap o ajusta el tall)")
                    if text not in avisos:
                        avisos.append(text)
            nb = (tempo_recalc.n_negres_del_clip(
                beats, ini, fi, factor, tol=tempo_recalc.TOL_TALL)
                if beats else None)
            bpm_i, num_i, den_i = _tram(
                float(dt), int(k), float(bpm_i), nb=nb)
            trams.append((ini, fi, bpm_i, num_i, den_i))
            ini = fi
        bpm_last, num_last, den_last = _tram(
            float(inter[-1][0]), int(inter[-1][1]), float(inter[-1][2]))
        trams.append((ini, durada, bpm_last, num_last, den_last))
        try:
            trams = tempo_map.valida_i_normalitza_permissiu(
                trams, durada, offset=getattr(self, "offset", 0.0))
        except ValueError as e:
            self.avis_editor(f"BPM marcadors: {e}")
            return False
        self._undo_marca()
        try:
            if not self.aplica_tempo_trams(trams):
                self.log("BPM marcadors: el mapa no s'ha pogut aplicar")
                return False
        finally:
            self._undo_commit()
        for avis in avisos:
            self.avis_editor(f"BPM dels marcadors: {avis}")
        self.bpm = bpm_ref
        self.bpb = num
        self.beat_type = den
        self._actualitza_temps()
        self._sincronitza_vista()
        self._desa_i_regenera()
        self.log(f"BPM dels marcadors: {self.bpm:.2f} (residu "
                 f"{float(candidat.get('residu') or 0):.4f}) · "
                 f"{len(trams)} trams · {len(ms)} marcadors")
        return True

    def snap_un_marcador(self, vell, nou):
        """Snap individual d'un marcador i recalcul del mapa (un desfer)."""
        from app import marcadors as M
        if self._marcador_a(float(vell)) is None:
            return False
        self._undo_marca()
        try:
            mogut = self._mou_marcador(float(vell), float(nou))
            if not mogut:
                self._undo_commit()
                return False
            self.marcadors = M.normalitza_marcadors(
                list(self.marcadors or ()), self._durada_wav())
            self._pinta_marcadors()
            self.ajusta_bpms_marcadors()
        finally:
            self._undo_commit()
        self._sincronitza_vista()
        return True

    def ajusta_bpms_marcadors(self):
        """Ajusta **tot** el mapa a partir dels marcadors, en un sol desfer.

        Acció per lot: cada interval entre marcadors passa a tindre compassos
        enters amb el BPM derivat; el BPM vigent del mapa al centre de cada
        interval és la referència (l'àudio detectat, si l'operador l'ha aplicat
        abans, ja és al mapa). El «cap» i la «cua» queden com a excepcions.
        L'offset (downbeat) és absolut i **no es mou**: només canvia quan
        l'usuari l'edita explícitament (decisió 2026-11-01).
        Retorna `True` si el mapa ha canviat.
        """
        from app import marcadors as M
        durada = self._durada_wav()
        ms = M.normalitza_marcadors(list(self.marcadors or ()), durada)
        if len(ms) < 2:
            self.avis_editor(
                "Calen almenys dos marcadors per a ajustar els BPMs")
            return False
        referencies = []
        for a, b in zip(ms, ms[1:]):
            try:
                referencies.append(float(self.tempo_map.bpm((a + b) / 2.0)))
            except (AttributeError, TypeError, ValueError):
                referencies.append(float(self.bpm))
        try:
            nous = tempo_map.ajusta_trams_a_marcadors(
                list(self.tempo_trams or []), ms, durada,
                referencies=referencies,
                offset=getattr(self, "offset", 0.0),
                beats_qm=self._beats_per_validacio())
        except ValueError as e:
            self.avis_editor(f"Ajusta BPMs: {e}")
            return False
        abans = [tuple(x) for x in (self.tempo_trams or [])]
        if [tuple(x) for x in nous] == abans:
            return False
        self._undo_marca()
        ok = self.aplica_tempo_trams(nous)
        self._undo_commit()
        if ok:
            self._sincronitza_vista()
            self.log(f"BPMs ajustats pels {len(ms)} marcadors: "
                     f"{len(nous)} trams · compàs 1 a {ms[0]:.3f}s")
        return bool(ok)

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
