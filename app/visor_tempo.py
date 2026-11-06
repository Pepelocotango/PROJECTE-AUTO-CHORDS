"""Tempo i rubato del visor (F4).

Extret de `app/visor.py`: objectiu de tempo, mapa de tempo per trams,
validació, edició, rubato i conversió a trams normals.
"""
import math

from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QDialog

from . import dialegs, mapa_tempo, pipeline, rubato as rubato_mod, tempo_map

class TempoMixin:
    """Mapa de tempo, rubato i edició del tempo objectiu."""

    def tempo_objectiu(self):
        """Índex del tram de tempo objectiu.

        Si hi ha un tram de tempo seleccionat, mana eixe (el clip actiu de la
        selecció); si no, el **transport** (tram 0). Decisió 2026-10-19.
        """
        kind, idx = self.seleccio_activa()
        if kind == "tempo" and self._index_valid("tempo", idx):
            return int(idx)
        return 0

    def tempo_objectiu_vals(self):
        """`(idx, bpm, num, den)` del tram objectiu (o del transport)."""
        trams = list(self.tempo_trams or [])
        idx = self.tempo_objectiu()
        if not trams:
            return (idx, float(self.bpm), int(self.bpb),
                    int(getattr(self, "beat_type", 4) or 4))
        idx = min(max(0, int(idx)), len(trams) - 1)
        s = trams[idx]
        return (idx, float(s[2]), int(s[3]), int(s[4]))

    def _preserva_rubato(self, abans, nous):
        """Reconstrueix `TramMapa` després d'una operació de tempo.

        Les operacions de `tempo_map` treballen amb 5 tuples i podrien perdre
        el `tipus`/`compassos` d'un rubato. Ací es reenganxen els rubatos per
        **interval temporal**, no per índex: un marcador pot afegir un tram
        abans o després d'un rubato i desplaçar tots els índexs.
        """
        abans = [mapa_tempo.des_de_tupla(x) for x in abans]
        rubatos = [t for t in abans if t.tipus == "rubato"]
        out = []
        for nou in nous:
            ini, fi, bpm = float(nou[0]), float(nou[1]), float(nou[2])
            triat, millor = None, 0.0
            for v in rubatos:
                vini, vfi = float(v.ini), float(v.fi)
                # Un tram nou dins un rubato (o que el conté) el conserva.
                dins = (ini >= vini - 1e-9 and fi <= vfi + 1e-9)
                conte = (vini >= ini - 1e-9 and vfi <= fi + 1e-9)
                solap = max(0.0, min(fi, vfi) - max(ini, vini))
                frac = solap / max(vfi - vini, 1e-9)
                if dins or conte or frac > 0.5:
                    if frac >= millor:
                        triat, millor = v, frac
            if triat is not None:
                segs = triat.segments
                q = sum(n * 4.0 / d * c for n, d, c in segs)
                if q > 0 and fi > ini:
                    bpm = q * 60.0 / (fi - ini)
                bpm = min(max(bpm, 30.0), 350.0)
                out.append(mapa_tempo.TramMapa(
                    ini, fi, bpm, "rubato", triat.compassos))
            else:
                out.append(mapa_tempo.TramMapa(
                    ini, fi, bpm, "normal",
                    f"{int(nou[3])}/{int(nou[4])}"))
        return out

    def edita_tempo_objectiu(self, idx, bpm, num, den, desa=True):
        """Aplica BPM/compàs a un tram de tempo (0 = transport).

        Re-tempo local (`docs/REGLES_DE_LA_APP.md` §13.5): el tram conserva el
        seu nombre de compassos, la seua durada passa a `N · bq · 60 / BPM` i
        el veí de la dreta conserva els compassos i el seu final recalculant el
        BPM. Els trams posteriors **no es mouen** (sense *ripple*). Si el canvi
        no és vàlid, es rebutja amb un avís.

        Amb `desa=False` (tap en viu) el canvi queda només en memòria; el desat
        es fa en tancar la sessió de taps.
        """
        trams = list(self.tempo_trams or [])
        if not trams:
            trams = [mapa_tempo.TramMapa(
                0.0, self._durada_wav(), float(bpm), "normal",
                f"{int(num)}/{int(den)}")]
        idx = min(max(0, int(idx)), len(trams) - 1)
        if getattr(trams[idx], "tipus", None) == "rubato":
            self.avis_editor(
                "El BPM i el compàs d'un rubato són derivats; no s'editen "
                "directament.")
            return False
        try:
            nous5 = tempo_map.canvia_bpm_local(
                [tuple(t) for t in trams], idx, float(bpm),
                self._durada_wav(), offset=getattr(self, "offset", 0.0),
                num=num, den=den,
                beats_qm=self._beats_per_validacio())
        except ValueError as e:
            self.avis_editor(f"Tempo: {e}")
            return False
        if not nous5:
            return False
        nous = self._preserva_rubato(trams, nous5)
        # El transport només pren valors d'un tros normal.
        if getattr(nous[0], "tipus", None) != "rubato":
            self.bpm = float(nous[0][2])
            self.bpb = int(nous[0][3])
            self.beat_type = int(nous[0][4])
        if desa:
            return bool(self.aplica_tempo_trams(nous))
        self.tempo_trams = nous
        self._actualitza_temps()
        return True

    def _refresca_tempo_map(self):
        """(Re)construeix `self.tempo_map` a partir de `self.tempo_trams`.

        El mapa és la font del tempo/compàs variables: la graella, el regle, el
        snap i els exports en surten. Sense trossos, se'n crea un de sol amb el
        BPM·compàs actual.
        """
        from app.tempo_map import TempoMap
        d = self._durada_wav()
        # Regles 1, 2, 4 i 8: aquest és el PUNT ÚNIC on es construeix el mapa.
        # El normalitzador preserva `tipus`/`compassos` (rubato inclòs).
        trams, avisos = mapa_tempo.normalitza_trams_map(
            list(self.tempo_trams or []), d, log=self.log)
        if avisos and tuple(avisos) != getattr(self, "_avisos_tempo", ()):
            for _a in avisos:
                self.log(f"tempo: {_a}")
            self.infoMissatge.emit("Tempo: " + " ".join(avisos))
        self._avisos_tempo = tuple(avisos)
        den = int(getattr(self, "beat_type", 4) or 4)

        def _lliure(t):
            return getattr(t, "tipus", None) == "rubato"

        if len(trams) <= 1:
            # Un sol tros = el cas constant, EXCEPTE si és rubato: llavors el
            # transport no hi té res a dir.
            if not (trams and _lliure(trams[0])):
                trams = [mapa_tempo.TramMapa(
                    0.0, d, float(self.bpm), "normal",
                    f"{int(self.bpb)}/{den}")]
        elif not _lliure(trams[0]):
            # El tram 0 és el VALOR INICIAL (el transport mana).
            t0 = trams[0]
            trams[0] = mapa_tempo.TramMapa(
                0.0, float(t0.fi), float(self.bpm), "normal",
                f"{int(self.bpb)}/{den}")
        self.tempo_trams = list(trams)
        offset_rub = self._offset_rubato_inicial(self.tempo_trams)
        if offset_rub is not None:
            self.offset = offset_rub
        self.tempo_map = TempoMap(self.tempo_trams,
                                  offset=getattr(self, "offset", 0.0))
        return self.tempo_map

    def aplica_tempo_trams(self, trams, forcat=False):
        """Aplica un mapa de tempo/compàs nou (des del diàleg).

        Normalitza (contigu, cobreix la WAV), actualitza el **transport** amb el
        valor inicial, reconstrueix el mapa, refresca el timeline i desa. Retorna
        `True` si s'ha aplicat.
        """
        abans = [mapa_tempo.des_de_tupla(t)
                 for t in (self.tempo_trams or [])]
        entrada = list(trams or [])
        if (not forcat and abans
                and any(t.tipus == "rubato" for t in abans)):
            if len(abans) != len(entrada):
                self.avis_editor(
                    "Aquesta operació canvia el nombre de trams d'un mapa "
                    "amb rubatos; les accions de rubato arribaran en la "
                    "fase 3.2.")
                return False
            entrada = self._preserva_rubato(
                abans, [tuple(t) for t in entrada])
        nous, avisos = mapa_tempo.normalitza_trams_map(
            entrada, self._durada_wav(), log=self.log)
        for avís in avisos:
            self.log(f"tempo: {avís}")
        if not nous:
            return False
        # El transport només pren valors d'un tros normal: un rubato no ha de
        # canviar el BPM/compàs de la barra.
        if getattr(nous[0], "tipus", None) != "rubato":
            self.bpm = float(nous[0][2])
            self.bpb = int(nous[0][3])
            self.beat_type = int(nous[0][4])
        self.tempo_trams = list(nous)
        # Refresca mapa + timeline + LLISTES (les etiquetes de compàs depenen
        # de l'offset i del BPM; `_actualitza_temps` és el punt únic).
        self._actualitza_temps()
        try:
            pipeline.desa_tempo_map(self._carpeta_acords(), self.tempo_trams)
        except Exception as e:  # noqa: BLE001
            self.log(f"desa mapa tempo/compàs ERROR: {e}")
        # Els compassos són una vista derivada del mapa: en canviar el tempo,
        # les columnes `compas_ini`/`compas_fi` de l'ABC han de quadrar amb la
        # graella nova. Els SEGONS no es mouen (model audio-first).
        self._regenera_posicions_musicals("canvi de tempo/compàs")
        # Si el canvi ve de FORA d'una operacio (carrega, analisi, el dialeg
        # del mapa...), la base del desfer s'ha de quedar al dia; si ve de
        # dins d'una operacio oberta, no fa res.
        self._undo_touch_base()
        self.canvis.emit()   # el mapa ha canviat → el projecte queda «brut»
        self.tempoCanviat.emit()   # la barra ha de refrescar BPM/compàs
        self.log(f"mapa de tempo/compàs: {len(nous)} tros(s)")
        return True

    def aplica_tempo_validat(self, trams, msg="Tempo"):
        """Aplica un mapa només si compleix el contracte de beats sencers.

        Punt d'entrada de la GUI per als canvis de mapa (diàleg, eliminar,
        fusionar, duplicar…). El backend `aplica_tempo_trams` continua
        permissiu per a càrregues de projectes vells i tests.
        """
        try:
            nous = tempo_map.valida_i_normalitza_compassos(
                trams, self._durada_wav(),
                offset=getattr(self, "offset", 0.0),
                beats_qm=self._beats_per_validacio())
        except ValueError as e:
            self.avis_editor(f"{msg}: {e}")
            return False
        return bool(self.aplica_tempo_trams(nous))

    def _normalitza_mapa_viu(self, trams, msg=None):
        """Mapa validat per a un gest en viu, sense reparacions silencioses.

        Els gestos de tempo (marcador `+`, re-tempo pel ratolí, «Detecta»)
        han de complir el contracte de beats sencers. Si el mapa no val, el
        gest es rebutja amb un avís: no es desa un mapa invàlid.
        """
        durada = self._durada_wav()
        offset = getattr(self, "offset", 0.0)
        try:
            return tempo_map.valida_i_normalitza_compassos(
                trams, durada, offset,
                beats_qm=self._beats_per_validacio())
        except ValueError as e:
            if msg:
                self.log(f"{msg}: el mapa no complix el contracte de clips "
                         f"({e})")
            raise

    def _on_tempo_edit(self, idx):
        """Clic a un bloc de BPM/compàs → diàleg per editar-ne el valor."""
        trams = list(self.tempo_trams or [])
        if not (0 <= idx < len(trams)):
            return
        s = trams[idx]
        try:
            lbl = self.tempo_map.label(s[0]).split(".")[0]
        except Exception:  # noqa: BLE001
            lbl = None
        dlg = dialegs.DialegTramTempo(
            self, inici=s[0], bpm=s[2], num=s[3], den=s[4],
            inicial=(idx == 0), text_inici=lbl, unit=self.bpm_unit)
        if dlg.exec_() != QDialog.Accepted:
            return
        bpm, num, den = dlg.valors()
        self._undo_marca()
        self.edita_tempo_objectiu(idx, bpm, num, den)
        self._undo_commit()

    def _on_tempo_mogut(self, idx, vora, t):
        """Vora d'un bloc de BPM/compàs arrossegada → **re-tempo** (el ratolí mana).

        Des del 21-10-2026 (`docs/REGLES_DE_LA_APP.md` §13.5) la jerarquia
        està invertida: el punter fixa **Δt**, els **compassos N** dels dos
        costats es conserven i el **BPM** es recalcula. Per això ja no s'imanta
        a la línia de compàs del tram anterior ni s'arrosseguen els trams
        següents (`_ripple_des_de`): **cap altre tram no es mou** i la frontera
        cau sempre en línia de compàs per construcció (el validador de
        beats sencers no ha de bloquejar el gest).

        Si el marcador humà d'eixa frontera coincidia, es mou amb ella (§4.C),
        tot dins del **mateix** desfer.
        """
        trams = list(self.tempo_trams or [])
        if not (0 <= idx < len(trams)):
            return
        # `idx` és el tram de la vora tocada; la frontera és el SEU inici
        # («ini»/«cos») o el del SEGÜENT («fi»). `mou_frontera_retempo` rep
        # l'índex del tram de la DRETA (la frontera és el seu inici).
        p_idx = int(idx) if str(vora).strip().lower() == "ini" else int(idx) + 1
        if not (0 < p_idx < len(trams)):
            # Els extrems del tema no es toquen: marquen l'inici i el final WAV.
            if p_idx <= 0:
                self.avis_editor(
                    "L'inici del primer clip marca l'inici de la WAV")
            else:
                self.avis_editor(
                    "La fi de l'últim clip marca el final de la WAV")
            return
        vell = float(trams[p_idx][0])
        offset = float(getattr(self, "offset", 0.0))
        if tempo_map.es_frontera_preroll(trams, p_idx, offset):
            # El tall és el COMPÀS 1 (el primer tram no té cap compàs): el gest
            # el mou a ell i el tram de música conserva els seus compassos.
            try:
                nous, nou_off = tempo_map.mou_frontera_preroll(
                    trams, p_idx, float(t), self._durada_wav(), offset)
            except ValueError as e:
                self.avis_editor(f"Compàs 1: {e}")
                return
            self._undo_marca()
            self.offset = float(nou_off)
            if self.aplica_tempo_trams(nous):
                self._mou_marcador(vell, float(self.tempo_trams[p_idx][0]))
            self._undo_commit()
            return
        try:
            nous = tempo_map.mou_frontera_retempo(
                trams, p_idx, float(t), self._durada_wav(), offset=offset,
                beats_qm=self._beats_per_validacio())
        except ValueError as e:
            self.avis_editor(f"Frontera de tempo: {e}")
            return
        self._undo_marca()
        if self.aplica_tempo_trams(nous):
            self._mou_marcador(vell, float(self.tempo_trams[p_idx][0]))
        self._undo_commit()

    def canvia_compassos_tram(self, idx, delta_compassos=0, factor=None):
        """Correcció **mètrica** discreta d'un tram de tempo (§4.C del flux).

        `+1`/`−1` compassos o `×2`/`÷2`: els **segons queden immòbils**, els
        veïns no es toquen i el BPM es recalcula (`tempo_map.canvia_compassos_tram`).
        Un sol desfer. Retorna `True` si el mapa ha canviat.
        """
        trams = list(self.tempo_trams or [])
        idx = -1 if idx is None else int(idx)
        if not (0 <= idx < len(trams)):
            return False
        try:
            nous = tempo_map.canvia_compassos_tram(
                trams, idx, delta_compassos=delta_compassos,
                durada=self._durada_wav(),
                offset=getattr(self, "offset", 0.0), factor=factor)
        except ValueError as e:
            self.avis_editor(f"Compassos: {e}")
            return False
        if [tuple(x) for x in nous] == [tuple(x) for x in trams]:
            return False
        self._undo_marca()
        ok = self.aplica_tempo_trams(nous)
        self._undo_commit()
        if ok:
            self.log(f"compassos tram {idx}: {trams[idx][2]:g} → "
                     f"{self.tempo_trams[idx][2]:.2f} BPM "
                     f"({self._compassos_de(idx):g} compassos)")
        return bool(ok)

    def _compassos_de(self, idx):
        """Compassos (arredonits) del tram `idx` del mapa viu (per a missatges)."""
        trams = list(self.tempo_trams or [])
        if not (0 <= int(idx) < len(trams)):
            return 0
        try:
            n = tempo_map._compassos_del_tram(
                trams[int(idx)], int(idx), getattr(self, "offset", 0.0))
        except ValueError:
            return 0
        return tempo_map._enter_mes_proper(max(1.0, n))

    def _on_tempo_menu(self, idx, t):
        """Botó dret a la pista ③ BPM/compàs.

        Regla d'or #11: **la mateixa definició de menú** que ④ estructura i
        ⑤ acords (vegeu `_menu_contextual`), pel mateix camí d'usuari.
        """
        idx = -1 if idx is None else int(idx)
        menu = self._menu_contextual("tempo", idx, float(t))
        accio = menu.exec_(QCursor.pos())
        self._executa_contextual("tempo", idx, float(t),
                                 accio.data() if accio else None, "timeline")

    # ---------------- RUBATO (fase 3.2) ----------------
    _EPS_RUBATO = 1e-6

    def _ref_rubato(self, ini, fi, exclude=None):
        """Referència per a un rubato: normal anterior, després següent."""
        ini, fi = float(ini), float(fi)
        anteriors = []
        posteriors = []
        for i, tr in enumerate(self.tempo_trams or []):
            if exclude is not None and i == exclude:
                continue
            if getattr(tr, "tipus", None) != "normal":
                continue
            d = (float(tr.bpm), int(tr.num), int(tr.den))
            if float(tr.ini) < ini - self._EPS_RUBATO:
                anteriors.append(d)
            elif float(tr.ini) >= fi - self._EPS_RUBATO:
                posteriors.append(d)
        transport = (float(self.bpm), int(self.bpb),
                     int(getattr(self, "beat_type", 4) or 4))
        return rubato_mod.tria_referencia(anteriors, posteriors, transport)

    def _crea_tram_rubato(self, ini, fi):
        ref = self._ref_rubato(ini, fi)
        d = rubato_mod.deriva(float(fi) - float(ini), *ref)
        return mapa_tempo.TramMapa(
            float(ini), float(fi), float(d.bpm), "rubato", d.compassos)

    def _offset_rubato_inicial(self, trams):
        """Si el primer tram és rubato, el compàs 1 és el primer normal."""
        if trams and getattr(trams[0], "tipus", None) == "rubato":
            for tr in trams:
                if getattr(tr, "tipus", None) == "normal":
                    return float(tr.ini)
        return None

    def _part_normal_retempo(self, tr, tall, esquerra):
        """Retalla un tram normal en una vora i re-tempa perquè tinga N bars."""
        ini, fi = (float(tr.ini), float(tall)) if esquerra else (
            float(tall), float(tr.fi))
        dur = fi - ini
        if dur <= self._EPS_RUBATO:
            return None
        bq = int(tr.num) * 4.0 / int(tr.den)
        if bq <= 0:
            raise ValueError("El compàs del veí no és vàlid")
        n_min = max(1, int(math.ceil(dur * 30.0 / (bq * 60.0) - 1e-9)))
        n_max = int(math.floor(dur * 350.0 / (bq * 60.0) + 1e-9))
        if n_max < n_min:
            raise ValueError(
                "El tall deixa un veí massa curt per a un compàs "
                "entre 30 i 350 BPM")
        vell_bar = bq * 60.0 / float(tr.bpm) if float(tr.bpm) > 0 else 0.0
        n = int(math.floor(dur / vell_bar + 0.5)) if vell_bar > 0 else n_min
        n = min(max(n, n_min), n_max)
        bpm = min(max(n * bq * 60.0 / dur, 30.0), 350.0)
        return mapa_tempo.TramMapa(ini, fi, bpm, "normal", tr.compassos)

    def crea_rubato_rang(self, ini, fi):
        """Marca com a rubato un interval [ini, fi], en un sol desfer."""
        durada = self._durada_wav()
        try:
            ini, fi = float(ini), float(fi)
        except (TypeError, ValueError):
            self.avis_editor("El rang del rubato no és vàlid.")
            return False
        if not (0.0 <= ini < fi <= durada + self._EPS_RUBATO):
            self.avis_editor("El rang del rubato ha de caure dins la WAV.")
            return False
        fi = min(fi, durada)
        trams = list(self.tempo_trams or [])
        for tr in trams:
            if (getattr(tr, "tipus", None) == "rubato"
                    and float(tr.fi) > ini + self._EPS_RUBATO
                    and float(tr.ini) < fi - self._EPS_RUBATO):
                self.avis_editor(
                    "El rang travessa un rubato existent; ajusta'l o "
                    "converteix-lo primer.")
                return False
        nous = []
        anteriors = []
        posteriors = []
        try:
            for tr in trams:
                if (float(tr.fi) <= ini + self._EPS_RUBATO
                        or float(tr.ini) >= fi - self._EPS_RUBATO):
                    nous.append(tr)
                    if getattr(tr, "tipus", None) == "normal":
                        if float(tr.fi) <= ini + self._EPS_RUBATO:
                            anteriors.append(
                                (float(tr.bpm), int(tr.num), int(tr.den)))
                        elif float(tr.ini) >= fi - self._EPS_RUBATO:
                            posteriors.append(
                                (float(tr.bpm), int(tr.num), int(tr.den)))
                    continue
                if getattr(tr, "tipus", None) == "rubato":
                    self.avis_editor(
                        "El rang travessa un rubato existent; ajusta'l o "
                        "converteix-lo primer.")
                    return False
                if float(tr.ini) < ini - self._EPS_RUBATO:
                    peça = self._part_normal_retempo(tr, ini, True)
                    if peça is not None:
                        nous.append(peça)
                        anteriors.append(
                            (float(peça.bpm), int(peça.num), int(peça.den)))
                if float(tr.fi) > fi + self._EPS_RUBATO:
                    peça = self._part_normal_retempo(tr, fi, False)
                    if peça is not None:
                        nous.append(peça)
                        posteriors.append(
                            (float(peça.bpm), int(peça.num), int(peça.den)))
            transport = (float(self.bpm), int(self.bpb),
                         int(getattr(self, "beat_type", 4) or 4))
            ref = rubato_mod.tria_referencia(anteriors, posteriors, transport)
            d = rubato_mod.deriva(fi - ini, *ref)
            rub = mapa_tempo.TramMapa(
                ini, fi, float(d.bpm), "rubato", d.compassos)
        except (ValueError, rubato_mod.RubatoError) as e:
            self.avis_editor(f"Rubato: {e}")
            return False
        nous.append(rub)
        nous.sort(key=lambda x: x.ini)
        try:
            nous, _avisos = mapa_tempo.normalitza_trams_map(
                nous, durada, fusiona=True)
        except (ValueError, rubato_mod.RubatoError) as e:
            self.avis_editor(f"Rubato: {e}")
            return False
        offset = self._offset_rubato_inicial(nous)
        self._undo_marca()
        if offset is not None:
            self.offset = offset
        ok = self.aplica_tempo_trams(nous, forcat=True)
        self._undo_commit()
        if ok:
            self.log(f"rubato: rang {ini:.3f}–{fi:.3f}s "
                     f"({rub.compassos} · {rub.bpm:.3f} BPM)")
        return bool(ok)

    def converteix_rubato(self, idx):
        """Converteix un tram normal en rubato (mateixa durada)."""
        trams = list(self.tempo_trams or [])
        if not (0 <= idx < len(trams)):
            return False
        if getattr(trams[idx], "tipus", None) == "rubato":
            return False
        tr = trams[idx]
        try:
            rub = self._crea_tram_rubato(tr.ini, tr.fi)
        except rubato_mod.RubatoError as e:
            self.avis_editor(f"Rubato: {e}")
            return False
        nous = list(trams)
        nous[idx] = rub
        try:
            nous, _avisos = mapa_tempo.normalitza_trams_map(
                nous, self._durada_wav(), fusiona=True)
        except (ValueError, rubato_mod.RubatoError) as e:
            self.avis_editor(f"Rubato: {e}")
            return False
        offset = self._offset_rubato_inicial(nous)
        self._undo_marca()
        if offset is not None:
            self.offset = offset
        ok = self.aplica_tempo_trams(nous, forcat=True)
        self._undo_commit()
        if ok:
            self.log(f"rubato: tram {idx} convertit "
                     f"({rub.compassos} · {rub.bpm:.3f} BPM)")
        return bool(ok)

    def converteix_normal(self, idx):
        """Converteix un rubato en clips normals, un per segment."""
        trams = list(self.tempo_trams or [])
        if not (0 <= idx < len(trams)):
            return False
        tr = trams[idx]
        if getattr(tr, "tipus", None) != "rubato":
            return False
        bpm = float(tr.bpm)
        t = float(tr.ini)
        fi = float(tr.fi)
        nous_t = []
        for k, (num, den, count) in enumerate(tr.segments):
            dur = (num * 4.0 / den) * count * 60.0 / bpm
            t2 = fi if k == len(tr.segments) - 1 else min(fi, t + dur)
            if t2 <= t + self._EPS_RUBATO:
                continue
            nous_t.append(mapa_tempo.TramMapa(
                t, t2, bpm, "normal", f"{num}/{den}"))
            t = t2
        nous = trams[:idx] + nous_t + trams[idx + 1:]
        try:
            nous, _avisos = mapa_tempo.normalitza_trams_map(
                nous, self._durada_wav(), fusiona=False)
        except (ValueError, rubato_mod.RubatoError) as e:
            self.avis_editor(f"Rubato: {e}")
            return False
        self._undo_marca()
        if idx == 0:
            self.offset = 0.0
        ok = self.aplica_tempo_trams(nous, forcat=True)
        self._undo_commit()
        if ok:
            self.log(f"rubato: tram {idx} convertit a {len(nous_t)} clip(s) "
                     "normals")
        return bool(ok)
