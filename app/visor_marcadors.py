"""Marcadors humans del visor (F4).

Extret de `app/visor.py`: alta, moviment, esborrat, snap i BPM derivat dels
marcadors.
"""
from . import pipeline, tempo_map, tempo_recalc

class MarcadorsMixin:
    """Marcadors humans i BPM derivat."""

    def _marcador_a(self, t, tol=0.05):
        """Índex del marcador humà que coincideix amb `t` (o `None`).

        Els marcadors es creen amb `+` i els seus ancestres són les fronteres
        de tempo; 0,05 s és prou per a emparellar-los sense confondre dos
        marcadors distints (entre ells sempre hi ha ≥ `SEPARACIO_MIN`).
        """
        t = float(t)
        for i, m in enumerate(self.marcadors or ()):
            if abs(float(m) - t) <= float(tol):
                return i
        return None

    def _mou_marcador(self, t_vell, t_nou):
        """Mou el marcador ancorat a una frontera que s'ha mogut (§4.C).

        Va DINS de l'operació de desfer del gest: el marcador, la frontera
        d'**estructura** que va crear i el mapa es desfan junts. Retorna `True`
        si n'hi havia cap.
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
        self._mou_seccio_amb_marcador(t_vell, t_nou)
        try:
            pipeline.desa_marcadors(
                self._carpeta_acords(),
                [(m, self.marcador_tipus.get(round(float(m), 6), "seccio"))
                 for m in (self.marcadors or [])])
        except OSError as e:
            self.log(f"marcadors: no s'han pogut desar ({e})")
        self.log(f"marcador mogut amb la frontera: {t_vell:.3f} → {t_nou:.3f}s")
        return True

    def _mou_seccio_amb_marcador(self, t_vell, t_nou):
        """Mou la frontera d'**estructura** que coincidia amb el marcador.

        El `+` crea alhora un inici de clip de BPM/compàs **i** d'estructura:
        si després es mou la frontera de tempo (i el marcador viatja amb ella,
        §4.C), el clip de secció també ha de seguir el marcador que el va
        crear. El vincle es resol per **coincidència de temps** (5 ms), sense
        desar cap identificador nou al projecte.

        Mou només les **dues** seccions que toquen la frontera (la de
        l'esquerra estira la fi i la de la dreta mou l'inici) i respecta
        `MIN_SECCIO_S`; si no hi cap, no toca res i ho deixa al registre.
        """
        seccions = list(self.seccions or [])
        if len(seccions) < 2:
            return False
        idx = next((j for j in range(1, len(seccions))
                    if abs(float(seccions[j][0]) - float(t_vell)) <= 0.005),
                   None)
        if idx is None:
            return False
        nou = float(t_nou)
        ini_a = float(seccions[idx - 1][0])
        fi_b = float(seccions[idx][1])
        if not (ini_a + self.MIN_SECCIO_S <= nou <= fi_b - self.MIN_SECCIO_S):
            self.log(f"marcador: la secció no pot seguir-lo ({nou:.3f}s)")
            return False
        nova = list(seccions)
        nova[idx - 1] = (ini_a, nou) + tuple(seccions[idx - 1][2:])
        nova[idx] = (nou, fi_b) + tuple(seccions[idx][2:])
        self.seccions = self._normalitza_seccions(nova)
        # El gest acaba al `release` del carril de tempo: NO podem re-sincronitzar
        # model←timeline (tornaria les seccions velles). Passem les dades noves
        # al timeline (sense reconstruir items ací mateix, que seria insegur
        # dins de l'esdeveniment) i deixem el re-render al cicle següent.
        tl = getattr(self, "timeline", None)
        if tl is not None:
            tl._seccions = [tuple(s) for s in self.seccions]
        self._actualitza_llista_abc()
        self._sincronitza_vista(preserva=True, difereix=True)
        self.log(f"estructura moguda amb el marcador: {t_vell:.3f} → "
                 f"{nou:.3f}s")
        return True

    def _esborra_marcador_a(self, t, tol=0.05):
        """Esborra el marcador d'una frontera que ha desaparegut (§4.C)."""
        from app import marcadors as M
        i = self._marcador_a(t, tol)
        if i is None:
            return False
        self.marcadors = M.elimina(list(self.marcadors or ()), i)
        self._pinta_marcadors()
        try:
            pipeline.desa_marcadors(
                self._carpeta_acords(),
                [(m, self.marcador_tipus.get(round(float(m), 6), "seccio"))
                 for m in (self.marcadors or [])])
        except OSError as e:
            self.log(f"marcadors: no s'han pogut desar ({e})")
        self.log(f"marcador esborrat amb la frontera de {float(t):.3f}s")
        return True

    def afegeix_marcador(self, t=None, tipus="seccio"):
        """Marca l'instant actual (o `t`) com a **inici de compàs**.

        Crea, en eixe punt, un **inici de clip al carril de BPM/compàs i al
        d'estructura**. El marcador queda **lligat a la frontera de tempo**
        (la segueix si s'arrossega i s'esborra amb ella, §4.C del flux de tempo
        variable) i el **clip d'estructura** que naix ací el seguix també
        (`_mou_seccio_amb_marcador`, vincle per coincidència de temps: si
        després s'edita la secció a mà i deixa de coincidir, deixa de seguir-lo).
        Es pot cridar mentre sona (tecla `+`). Un sol desfer ho desfà tot.

        El tram que es tanca conserva el BPM; si cal, s'ajusta el compàs per
       què continga un beat sencer (`tempo_map.parteix_tram_marcador`).
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
        try:
            trams = tempo_map.parteix_tram_marcador(
                trams, t, durada, offset=getattr(self, "offset", 0.0),
                bpm_ref=bpm_ref, beats_qm=getattr(self, "qm_beats", None),
                permissiu=True, recalculca=True,
                ref_base=self.ref_tempo_base())
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
            trams = self._preserva_rubato(self.tempo_trams or [], trams)
            self.aplica_tempo_trams(trams, forcat=True)
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

        def _tram(dt, k, bpm_i, nb=None):
            # Si hi ha beats detectats, manen sobre el nombre de compassos
            # estimat pels marcadors: 7 beats són 7/4, no 2×4/4.
            _ = float(bpm_i)      # el candidat dels marcadors ja no és la ref
            r = tempo_recalc.recalculca_tram(
                dt, ref_bpm, int(ref_num), int(ref_den),
                n_ref=None if nb else int(k), n_beats=nb)
            if r is None:
                return (float(bpm_i), int(num), int(den))
            return (float(r["bpm"]), int(r["num"]), int(r["den"]))

        bpm0, num0, den0 = _tram(float(inter[0][0]), int(inter[0][1]),
                                 float(inter[0][2]))
        trams = [(0.0, float(ms[0]), bpm0, num0, den0)]
        ini = float(ms[0])
        for dt, k, bpm_i in inter:
            fi = ini + float(dt)
            nb = (sum(1 for b in beats if ini - 1e-6 <= b < fi - 1e-6)
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

    def _pinta_marcadors(self):
        tl = getattr(self, "timeline", None)
        if tl is not None and hasattr(tl, "set_marcadors"):
            marques = [(m, self.marcador_tipus.get(round(float(m), 6), "seccio"))
                       for m in (self.marcadors or [])]
            tl.set_marcadors(marques)
