"""Tempo i rubato del visor (F4).

Extret de `app/visor.py`: objectiu de tempo, mapa de tempo per trams,
validació, edició, rubato i conversió a trams normals.
"""
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QDialog, QMessageBox

from . import bpm_unit as bpm_unit_mod
from . import dialegs, limits, mapa_tempo, pipeline, tempo_map
from . import tempo_recalc

class TempoMixin:
    """Mapa de tempo, rubato i edició del tempo objectiu."""

    def ref_tempo_base(self):
        """Referència manual (bpm, num, den) per a tots els recalcs."""
        return (float(self.ref_bpm), int(self.ref_bpb),
                int(self.ref_beat_type))

    def unitat_de_tram(self, tram):
        """Unitat de pols d'un tram (objecte o tuple antiga de 5 camps)."""
        bu = getattr(tram, "beat_unit", None)
        if bu:
            return bpm_unit_mod.normalitza(bu)
        try:
            num, den = int(tram[3]), int(tram[4])
            agr = getattr(tram, "agrupacio", "")
        except (TypeError, ValueError, IndexError):
            return bpm_unit_mod.DEFECTE
        return bpm_unit_mod.unitat_per_defecte(num, den, agr)

    def beat_factor(self, unit=None):
        """Negres que val el pols detectat (negra=1, punt=1.5, corxera=0.5)."""
        u = self.unitat_objectiu() if unit is None else unit
        return bpm_unit_mod.factor(u)

    def set_beat_unit(self, unit):
        """Compatibilitat: canvia la unitat del tram objectiu (mantén tempo)."""
        unit = bpm_unit_mod.normalitza(unit)
        self.beat_unit = unit
        kind, idx = self.seleccio_activa()
        trams = list(self.tempo_trams or [])
        if kind == "tempo" and 0 <= int(idx) < len(trams):
            self.canvia_unitat_tram(int(idx), unit, mode="mantenir_tempo")
        senyal = getattr(self, "beatUnitCanviat", None)
        if senyal is not None:
            senyal.emit(unit)

    def canvia_unitat_tram(self, idx, unit, mode="mantenir_tempo",
                           desa=True):
        """Canvia la unitat de pols d'un tram mantenint les fronteres.

        `mode="mantenir_tempo"` conserva el BPM intern (el so no canvia).
        `mode="mantenir_numero"` conserva el número visible i recalcula el
        BPM intern; el recalc fix manté N enter i fronteres.
        """
        trams = list(self.tempo_trams or [])
        idx = int(idx)
        if not (0 <= idx < len(trams)):
            return False
        tr = trams[idx]
        unit = bpm_unit_mod.normalitza(unit)
        unit_actual = self.unitat_de_tram(tr)
        if unit == unit_actual:
            return False
        if mode == "mantenir_numero":
            visible = bpm_unit_mod.de_quarter(tr.bpm, unit_actual)
            target = bpm_unit_mod.a_quarter(visible, unit)
            try:
                target, num, den = tempo_map.valida_tempo(
                    target, tr.num, tr.den)
            except ValueError as e:
                self.avis_editor(f"Unitat: {e}")
                return False
            tmp = list(trams)
            tmp[idx] = mapa_tempo.TramMapa(
                tr.ini, tr.fi, target, tr.tipus, tr.compassos,
                tr.agrupacio, tr.n, unit)
            try:
                nous5 = tempo_map.ajusta_bpm_a_compassos(
                    tmp, idx, self._durada_wav(),
                    offset=getattr(self, "offset", 0.0),
                    beats_qm=self._beats_per_validacio())
            except ValueError as e:
                self.avis_editor(f"Unitat: {e}")
                return False
            nous = mapa_tempo.reenganxa_metadades(tmp, nous5)
            nou = nous[idx]
            nous[idx] = mapa_tempo.TramMapa(
                nou.ini, nou.fi, nou.bpm, nou.tipus, nou.compassos,
                nou.agrupacio, nou.n, unit)
        else:
            nous = list(trams)
            nous[idx] = mapa_tempo.TramMapa(
                tr.ini, tr.fi, tr.bpm, tr.tipus, tr.compassos,
                tr.agrupacio, tr.n, unit)
        self._undo_marca()
        ok = bool(self.aplica_tempo_trams(nous))
        self._undo_commit()
        if ok:
            self.log(f"unitat tram {idx}: {unit_actual} → {unit} "
                     f"({mode})")
        return ok

    def set_ref_tempo(self, bpm, num, den, unit=None):
        """Fixa la referència manual del recalcul, validada i amb unitat."""
        bpm, num, den = tempo_map.valida_tempo(bpm, num, den)
        self.ref_bpm = float(bpm)
        self.ref_bpb = int(num)
        self.ref_beat_type = int(den)
        if unit is not None:
            self.ref_beat_unit = bpm_unit_mod.normalitza(unit)
        self.ref_beat_unit = bpm_unit_mod.normalitza(
            getattr(self, "ref_beat_unit", bpm_unit_mod.DEFECTE))
        senyal = getattr(self, "refCanviat", None)
        if senyal is not None:
            senyal.emit()
        return self.ref_tempo_base()

    def ref_tempo_unit(self):
        """Unitat de la Ref. recalc."""
        return bpm_unit_mod.normalitza(
            getattr(self, "ref_beat_unit", bpm_unit_mod.DEFECTE))

    def ref_tempo_complet(self):
        """`(bpm, num, den, unitat)` de la Ref. recalc."""
        bpm, num, den = self.ref_tempo_base()
        return bpm, num, den, self.ref_tempo_unit()

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

    def edita_tempo_objectiu(self, idx, bpm, num, den, desa=True, repara=True,
                             agrupacio=None):
        """Aplica BPM/compàs a un tram de tempo (0 = transport).

        Contracte §13.4/§13.5: **tots** els clips mantenen `N` enter. En un
        tram interior, `N` exacte deriva `fi`; el veí conserva el seu `N` enter
        i recalcula el BPM. En l'últim/únic, el final no es mou: `N`
        s'arrodoneix a l'enter més pròxim i el BPM es deriva.

        Amb `desa=False` (TAP en viu) s'usa el camí permissiu: arrodoneix `N`
        i ajusta el BPM, sense moure les fronteres.
        """
        trams = list(self.tempo_trams or [])
        if not trams:
            trams = [mapa_tempo.TramMapa(
                0.0, self._durada_wav(), float(bpm), "normal",
                f"{int(num)}/{int(den)}")]
        idx = min(max(0, int(idx)), len(trams) - 1)
        if desa:
            try:
                nous = mapa_tempo.recalcula_tram_c(
                    trams, idx, self._durada_wav(),
                    offset=getattr(self, "offset", 0.0),
                    bpm=float(bpm), num=int(num), den=int(den),
                    camp="bpm")
            except ValueError as e:
                self.avis_editor(f"Tempo: {e}")
                return False
        else:
            try:
                nous5 = tempo_map.canvia_bpm_local(
                    [tuple(t) for t in trams], idx, float(bpm),
                    self._durada_wav(), offset=getattr(self, "offset", 0.0),
                    num=num, den=den,
                    beats_qm=self._beats_per_validacio(), permissiu=True)
            except ValueError as e:
                self.avis_editor(f"Tempo: {e}")
                return False
            if not nous5:
                return False
            nous = mapa_tempo.reenganxa_metadades(trams, nous5)
        if agrupacio is not None:
            agr = tempo_map.valida_agrupacio(
                agrupacio, nous[idx].num, nous[idx].den)
            nou = nous[idx]
            nous[idx] = mapa_tempo.TramMapa(
                nou.ini, nou.fi, nou.bpm, nou.tipus, nou.compassos, agr,
                getattr(nou, "n", None), nou.beat_unit)
        # El transport només pren valors d'un tros normal.
        self.bpm = float(nous[0][2])
        self.bpb = int(nous[0][3])
        self.beat_type = int(nous[0][4])
        if desa:
            return bool(self.aplica_tempo_trams(nous))
        self.tempo_trams = nous
        self._actualitza_temps()
        return True

    def edita_n_compassos(self, idx, n, num, den, desa=True):
        """Edita **N compassos** i compàs; el BPM es recalcula automàticament.

        Regla C: N i compàs són exactes; en interiors es deriva `fi` i el veí
        recalcula el BPM. En l'últim/únic, N exacte i BPM recalculat amb el
        final fix.
        """
        trams = list(self.tempo_trams or [])
        if not trams:
            return False
        idx = min(max(0, int(idx)), len(trams) - 1)
        try:
            nous = mapa_tempo.recalcula_tram_c(
                trams, idx, self._durada_wav(),
                offset=getattr(self, "offset", 0.0),
                n=int(n), bpm=float(trams[idx].bpm), num=int(num),
                den=int(den), camp="n")
        except ValueError as e:
            self.avis_editor(f"Compassos: {e}")
            return False
        self.bpm = float(nous[0][2])
        self.bpb = int(nous[0][3])
        self.beat_type = int(nous[0][4])
        if desa:
            ok = bool(self.aplica_tempo_trams(nous))
        else:
            self.tempo_trams = nous
            self._actualitza_temps()
            ok = True
        if ok:
            self.log(f"compassos tram {idx}: {trams[idx][2]:g} → "
                     f"{self.tempo_trams[idx][2]:.2f} BPM "
                     f"({int(n)} compassos de {int(num)}/{int(den)})")
        return ok

    def _repara_compas_no_enter(self, idx, bpm, num, den, n_compas,
                                trams, desa=True):
        """Diàleg per reparar un canvi de compàs que deixa N no enter.

        Opcions: ajustar el BPM perquè N siga enter amb el compàs triat,
        canviar a la signatura canònica que proposa el recalcul (base + beats),
        o cancel·lar. Retorna el resultat de l'opció aplicada.
        """
        tram = trams[int(idx)]
        ini, fi = float(tram[0]), float(tram[1])
        base = tempo_map._base_tram(
            tram, int(idx), getattr(self, "offset", 0.0))
        dt = fi - base
        num, den = int(num), int(den)
        bq = tempo_map._bar_quarters(num, den)
        n_enter = max(1, tempo_map._enter_mes_proper(float(n_compas)))
        bpm_ajust = None
        if dt > 0 and bq > 0:
            candidat = n_enter * bq * 60.0 / dt
            try:
                bpm_ajust = tempo_map.valida_tempo(candidat, num, den)[0]
            except ValueError:
                bpm_ajust = None

        ref_bpm, ref_num, ref_den = self.ref_tempo_base()
        beats = [float(b) for b in (self._beats_per_validacio() or ())]
        factor = self.beat_factor()
        n_beats = tempo_recalc.n_negres_del_clip(
            beats, ini, fi, factor) if beats else None
        canon = None
        try:
            canon = tempo_recalc.recalculca_tram(
                dt, ref_bpm, ref_num, ref_den, n_beats=n_beats,
                pas_beat=factor)
        except (TypeError, ValueError):
            canon = None

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Compàs no sencer")
        box.setText(
            f"El clip {int(idx) + 1} tindria {float(n_compas):.3f} compassos "
            f"amb {num}/{den} a {float(bpm):.3f} BPM.")
        box.setInformativeText(
            "Tria com reparar-lo perquè la graella i el metrònom quedin "
            "vàlids:")
        b_ajusta = None
        b_canvia = None
        if bpm_ajust is not None:
            b_ajusta = box.addButton(
                f"Ajusta BPM a {bpm_ajust:.3f} ({n_enter} compassos)",
                QMessageBox.AcceptRole)
        if canon is not None:
            b_canvia = box.addButton(
                f"Canvia a {int(canon['num'])}/{int(canon['den'])} "
                f"N={int(canon['n'])} ({float(canon['bpm']):.3f} BPM)",
                QMessageBox.ActionRole)
        b_cancel = box.addButton("Cancel·la", QMessageBox.RejectRole)
        box.setDefaultButton(b_ajusta or b_cancel)
        box.exec_()
        triat = box.clickedButton()
        if triat is b_ajusta and b_ajusta is not None:
            return self.edita_tempo_objectiu(
                idx, bpm_ajust, num, den, desa=desa, repara=False)
        if triat is b_canvia and b_canvia is not None:
            return self.edita_tempo_objectiu(
                idx, float(canon["bpm"]), int(canon["num"]),
                int(canon["den"]), desa=desa, repara=False)
        return False

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

        if not trams:
            # Mapa buit: se'n crea un de sol amb el transport (regla §13.3).
            trams = [mapa_tempo.TramMapa(
                0.0, d, float(self.bpm), "normal",
                f"{int(self.bpb)}/{den}")]
        # El tram 0 és un clip més: NO se sobreescriu amb el transport. La
        # barra és una vista i se sincronitza des del clip 0.
        if trams:
            self.bpm = float(trams[0][2])
            self.bpb = int(trams[0][3])
            self.beat_type = int(trams[0][4])
        self.tempo_trams = list(trams)
        self.tempo_map = TempoMap(self.tempo_trams,
                                  offset=getattr(self, "offset", 0.0))
        self.comprova_mapa_sencers()
        return self.tempo_map

    def comprova_mapa_sencers(self, forca=False):
        """Emite `mapaInconsistent` si algun clip no dona compassos sencers.

        S'executa cada vegada que es reconstrueix el `TempoMap`; `forca=True`
        fa que el senyal s'emeta encara que el text coincidisca amb l'anterior
        (en carregar un projecte o en connectar la finestra).
        """
        issues = tempo_map.problemes_compassos_sencers(
            self.tempo_trams, self._durada_wav(),
            offset=getattr(self, "offset", 0.0))
        if not issues:
            self._mapa_avis_actual = ""
            return []
        parts = ["El mapa de tempo/compàs té clips que no donen compassos "
                 "sencers:"]
        for p in issues:
            parts.append(
                f"· Clip {int(p['idx']) + 1}: {p['ini']:.3f}–{p['fi']:.3f}s "
                f"· {p['num']}/{p['den']} a {p['bpm']:.3f} BPM "
                f"→ {p['n']:.3f} compassos")
        text = "\n".join(parts)
        if getattr(self, "_tap_en_curs", False):
            # No s'interromp la sessió de taps amb l'avís modal; es torna a
            # comprovar en tancar-la.
            self._mapa_avis_actual = text
            return issues
        if forca or text != getattr(self, "_mapa_avis_actual", None):
            self._mapa_avis_actual = text
            self.mapaInconsistent.emit(text)
        return issues

    def aplica_tempo_trams(self, trams, forcat=False):
        """Aplica un mapa de tempo/compàs nou (des del diàleg).

        Normalitza (contigu, cobreix la WAV), actualitza el **transport** amb el
        valor inicial, reconstrueix el mapa, refresca el timeline i desa. Retorna
        `True` si s'ha aplicat.
        """
        entrada = list(trams or [])
        nous, avisos = mapa_tempo.normalitza_trams_map(
            entrada, self._durada_wav(), log=self.log)
        for avís in avisos:
            self.log(f"tempo: {avís}")
        if not nous:
            return False
        # El transport només pren valors d'un tros normal: un rubato no ha de
        # canviar el BPM/compàs de la barra.
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
        """Aplica un mapa amb la validació permissiva del model (F2).

        Exigeix BPM/compàs vàlids, contigüitat, cobertura, el mínim d'un
        compàs 1/16 a 350 BPM i **N enter a tots els clips** (si cal,
        s'arrodoneix `N` i s'ajusta el BPM). Les fronteres interiors poden ser
        lliures. Els detectors i les accions explícites mantenen la validació
        estricta pel seu compte.
        """
        entrada = list(trams or [])
        try:
            nous = tempo_map.valida_i_normalitza_permissiu(
                entrada, self._durada_wav(),
                offset=getattr(self, "offset", 0.0))
        except ValueError as e:
            self.avis_editor(f"{msg}: {e}")
            return False
        nous = mapa_tempo.reenganxa_metadades(entrada, nous)
        return bool(self.aplica_tempo_trams(nous))

    def _normalitza_mapa_viu(self, trams, msg=None):
        """Mapa validat per a un gest en viu (permissiu, F2).

        Comprova BPM/compàs, contigüitat, cobertura, el mínim d'un compàs
        1/16 a 350 BPM i **N enter**; si cal, arrodoneix `N` i ajusta el BPM.
        Si el mapa no val, el gest es rebutja amb un avís.
        """
        durada = self._durada_wav()
        offset = getattr(self, "offset", 0.0)
        try:
            return tempo_map.valida_i_normalitza_permissiu(
                trams, durada, offset)
        except ValueError as e:
            if msg:
                self.log(f"{msg}: el mapa no complix el contracte de clips "
                         f"({e})")
            raise

    def _info_clip_tempo(self, idx):
        """Tota la informació derivada del clip de tempo `idx` (per al diàleg)."""
        trams = list(self.tempo_trams or [])
        idx = int(idx)
        if not (0 <= idx < len(trams)):
            return None
        tr = trams[idx]
        ini, fi, bpm = float(tr[0]), float(tr[1]), float(tr[2])
        num, den = int(tr[3]), int(tr[4])
        durada = fi - ini
        agr = getattr(tr, "agrupacio", "") or ""
        try:
            agr_ef = agr or tempo_map.agrupacio_a_text(
                tempo_map.agrupacio_compas(num, den))
        except (TypeError, ValueError):
            agr_ef = agr
        n_desat = getattr(tr, "n", None)
        try:
            n_real = tempo_map.compassos_del_clip(tr)
        except (TypeError, ValueError):
            n_real = None
        n_enter = None
        n_valid = False
        if n_real is not None:
            n_enter = max(1, tempo_map._enter_mes_proper(float(n_real)))
            n_valid = abs(float(n_real) - float(n_enter)) <= 1e-6
        try:
            bq = float(num) * 4.0 / float(den) if den else 0.0
            dur_compas = tempo_map.durada_compas(bpm, num, den)
        except (TypeError, ValueError, ZeroDivisionError):
            bq = 0.0
            dur_compas = 0.0
        offset = float(getattr(self, "offset", 0.0) or 0.0)
        ref_bpm, ref_num, ref_den = self.ref_tempo_base()
        desviacio = ((bpm / ref_bpm) - 1.0) * 100.0 if ref_bpm else None
        ratio = (bpm / ref_bpm) if ref_bpm else None
        marge = tempo_recalc.MARGE_SOSPITA_OCTAVA
        sospita_octava = bool(
            ratio is not None
            and (abs(ratio - 2.0) <= 2.0 * marge
                 or abs(ratio - 0.5) <= 0.5 * marge))

        snap_on = bool(getattr(self, "snap_on", True))
        mode = str(getattr(self, "snap_mode", "") or "")
        noms_snap = {
            "qm_beats": "Beats QM", "": "Auto (zoom)",
            "negra": "Negra (1/4)", "corxera": "Corxera (1/8)",
            "semicorxera": "Semicorxera (1/16)", "fusa": "Fusa (1/32)",
            "treset_negra": "Treset de negra (2/3)",
            "treset_corxera": "Treset de corxera (1/3)",
            "treset_semicorxera": "Treset de semicorxera (1/6)",
        }
        snap = (f"{'actiu' if snap_on else 'desactivat'} · "
                f"{noms_snap.get(mode, mode or 'auto')}")

        beats = [float(b) for b in (getattr(self, "qm_beats", None) or ())]
        tol = tempo_recalc.TOL_TALL
        dins = [b for b in beats if ini - tol <= b < fi - tol]
        if dins:
            n_qm = len(dins)
            negres = tempo_recalc.n_negres_del_clip(
                beats, ini, fi, self.beat_factor())
            primer, ultim = min(dins), max(dins)
        else:
            n_qm = 0 if beats else None
            negres = None
            primer = ultim = None
        frontera = tempo_recalc.beats_a_la_frontera(beats, ini, fi, tol=tol)

        def _resum(j):
            t = trams[j]
            try:
                n = tempo_map.compassos_del_clip(t)
            except (TypeError, ValueError):
                n = getattr(t, "n", None)
            return {"idx": j + 1, "bpm": float(t[2]),
                    "compassos": f"{int(t[3])}/{int(t[4])}", "n": n}

        return {
            "idx": idx + 1, "total": len(trams),
            "rol": tempo_map.rol_tram(trams, idx),
            "tipus": getattr(tr, "tipus", "normal"),
            "ini": ini, "fi": fi, "durada": durada,
            "ini_cb": self._secs_a_cb(ini), "fi_cb": self._secs_a_cb(fi),
            "compassos": f"{num}/{den}",
            "bar_quarters": bq, "durada_compas": dur_compas,
            "agrupacio": agr, "agrupacio_ef": agr_ef,
            "n": n_desat, "n_real": n_real, "n_enter": n_enter,
            "n_valid": n_valid,
            "bpm": bpm,
            "bpm_mostra": bpm_unit_mod.de_quarter(
                bpm, self.unitat_de_tram(tr)),
            "bpm_unit": bpm_unit_mod.etiqueta(self.bpm_unit),
            "offset": offset,
            "ref_bpm": ref_bpm, "ref_compas": f"{int(ref_num)}/{int(ref_den)}",
            "desviacio": desviacio,
            "sospita_octava": sospita_octava,
            "beat_unit": bpm_unit_mod.etiqueta(
                self.unitat_de_tram(tr)),
            "snap": snap, "n_qm": n_qm, "negres_qm": negres,
            "primer_beat": primer, "ultim_beat": ultim,
            "beats_frontera": frontera,
            "extrem_ini": ("fix (inici de la WAV)" if idx == 0
                           else "lliure"),
            "extrem_fi": ("fixa (durada WAV)" if idx == len(trams) - 1
                          else "lliure"),
            "preroll": tempo_map.es_preroll_tram(trams, idx, offset),
            "vei_esq": _resum(idx - 1) if idx > 0 else None,
            "vei_dret": _resum(idx + 1) if idx < len(trams) - 1 else None,
            "bpm_ok": (tempo_map.BPM_EDIT_MIN <= bpm
                       <= tempo_map.BPM_EDIT_MAX),
            "durada_ok": durada >= limits.TEMPS_MIN_CLIP,
            "min_durada": limits.TEMPS_MIN_CLIP,
        }

    def _recalcula_tram_dialeg(self, dlg, idx, mode):
        """«Recalcula» del diàleg: fix (fronteres fixes) o mòbil (una frontera)."""
        trams = list(self.tempo_trams or [])
        idx = int(idx)
        if not (0 <= idx < len(trams)):
            self.avis_editor("Recalcul: el clip no existeix.")
            return False
        opcions = dlg.opcions_recalc()
        if opcions.get("rubato"):
            self.avis_editor("Recalcul: el rubato no es recalcula ací.")
            return False
        try:
            bpm_camp, num_camp, den_camp, n_camp = dlg.valors_camps()
            bpm_camp, num_camp, den_camp = tempo_map.valida_tempo(
                bpm_camp, num_camp, den_camp)
        except ValueError as e:
            self.avis_editor(f"Recalcul: {e}")
            return False
        tr = trams[idx]
        ini, fi = float(tr[0]), float(tr[1])
        durada_real = fi - ini
        if opcions["segons"]:
            durada = durada_real
        else:
            bq = float(num_camp) * 4.0 / float(den_camp)
            durada = float(n_camp) * bq * 60.0 / float(bpm_camp)
        if durada <= tempo_map.TOL:
            self.avis_editor("Recalcul: la durada de referència no és vàlida.")
            return False
        if opcions["ref"]:
            bpm_ref, num_ref, den_ref = self.ref_tempo_base()
        else:
            bpm_ref, num_ref, den_ref = bpm_camp, num_camp, den_camp
        if not opcions["compas"]:
            num_ref, den_ref = num_camp, den_camp
        n_beats = None
        pas_beat = 1.0
        if opcions["beats"]:
            factor = self.beat_factor() if opcions["unitat"] else 1.0
            beats = list(getattr(self, "qm_beats", None) or ())
            n_beats = tempo_recalc.n_negres_del_clip(
                beats, ini, fi, factor)
            pas_beat = factor
        try:
            res = tempo_recalc.recalculca_tram(
                durada, bpm_ref, num_ref, den_ref,
                n_ref=int(n_camp) if opcions["n_fix"] else None,
                n_beats=n_beats,
                mode="mixt" if n_beats is not None else "graella",
                bloca_compas=not opcions["compas"],
                pas_beat=pas_beat,
                ajusta_beats=bool(opcions["beats"]))
        except ValueError as e:
            self.avis_editor(f"Recalcul: {e}")
            return False
        if res is None:
            self.avis_editor(
                "Recalcul: no hi ha cap combinació vàlida amb estes opcions.")
            return False
        try:
            if mode == "fix":
                nous = tempo_map.canvia_compassos_tram(
                    trams, idx, n_new=int(res["n"]), num=int(res["num"]),
                    den=int(res["den"]), durada=self._durada_wav(),
                    offset=getattr(self, "offset", 0.0))
            else:
                nous = mapa_tempo.recalcula_tram_c(
                    trams, idx, self._durada_wav(),
                    offset=getattr(self, "offset", 0.0),
                    n=int(res["n"]), bpm=float(bpm_camp),
                    num=int(res["num"]), den=int(res["den"]), camp="n")
        except ValueError as e:
            self.avis_editor(f"Recalcul {mode}: {e}")
            return False
        if [tuple(x) for x in nous] == [tuple(x) for x in trams]:
            self.log(f"recalcul {mode} tram {idx}: sense canvis")
            return True
        ok = bool(self.aplica_tempo_trams(nous))
        if ok:
            self.log(
                f"recalcul {mode} tram {idx}: {float(tr[2]):.3f} → "
                f"{float(self.tempo_trams[idx][2]):.3f} BPM · "
                f"{int(res['num'])}/{int(res['den'])} · N={int(res['n'])}")
        return ok

    def _on_tempo_edit(self, idx):
        """Clic a un bloc de BPM/compàs → diàleg per editar-ne el valor."""
        trams = list(self.tempo_trams or [])
        if not (0 <= idx < len(trams)):
            return False
        s = trams[idx]
        try:
            lbl = self.tempo_map.label(s[0]).split(".")[0]
        except Exception:  # noqa: BLE001
            lbl = None
        try:
            durada = float(s[1]) - float(s[0])
            n_actual = tempo_map.compassos_del_clip(s)
        except (TypeError, ValueError):
            durada = 0.0
            n_actual = None
        unit_tram = self.unitat_de_tram(s)
        dlg = dialegs.DialegTramTempo(
            self, inici=s[0], bpm=s[2], num=s[3], den=s[4],
            inicial=(idx == 0), text_inici=lbl, unit=unit_tram,
            n_actual=n_actual, durada=durada,
            info=self._info_clip_tempo(idx), ref=self.ref_tempo_base(),
            ref_unit=self.ref_tempo_unit(), beat_unit=unit_tram)
        darrers = {"valors": None}

        def _valors_dialeg():
            return dlg.valors_n() if dlg.n_auto() else dlg.valors()

        def _aplica_actuals():
            if dlg.n_auto():
                bpm, num, den, n = dlg.valors_n()
                return bool(self.edita_n_compassos(idx, n, num, den))
            bpm, num, den = dlg.valors()
            return bool(self.edita_tempo_objectiu(idx, bpm, num, den))

        def _executa(accio):
            """Fa una acció amb desfer i captura els avisos per al diàleg."""
            avisos = []
            avis_original = self.avis_editor
            self.avis_editor = lambda text: (
                avisos.append(str(text)), avis_original(text))
            self._undo_marca()
            try:
                try:
                    ok = accio()
                except ValueError as e:
                    avisos.append(str(e))
                    ok = False
            finally:
                self._undo_commit()
                self.avis_editor = avis_original
            return bool(ok), avisos

        def _refresca():
            dlg.actualitza_estat(self._info_clip_tempo(idx))
            darrers["valors"] = _valors_dialeg()

        def _on_aplica():
            """«Ajusta»: aplica, refresca la informació i manté el diàleg."""
            ok, avisos = _executa(_aplica_actuals)
            if ok:
                _refresca()
                return True
            QMessageBox.warning(
                dlg, "Ajusta",
                " ".join(avisos) or
                "No s'ha pogut aplicar el canvi amb els valors actuals.")
            return False

        def _on_recalcul(mode):
            """«Recalcula» fix/mòbil: aplica, refresca i manté el diàleg."""
            ok, avisos = _executa(
                lambda: self._recalcula_tram_dialeg(dlg, idx, mode))
            if ok:
                _refresca()
                return True
            QMessageBox.warning(
                dlg, "Recalcula",
                " ".join(avisos) or
                "No s'ha pogut recalcular el tram amb estes opcions.")
            return False

        def _on_ref(bpm, num, den, unit):
            """«Aplica ref.»: canvia la Ref. recalc del visor."""
            try:
                self.set_ref_tempo(bpm, num, den, unit)
            except ValueError as e:
                QMessageBox.warning(dlg, "Ref. recalc invàlida", str(e))
                return False
            self._undo_touch_base()
            dlg.actualitza_ref(bpm, num, den, unit)
            dlg.actualitza_info(self._info_clip_tempo(idx))
            self.log(f"Ref. recalc: {float(bpm):.3f} BPM · "
                     f"{int(num)}/{int(den)}")
            return True

        def _on_beat_unit(unit):
            """Canvia la unitat de Beat/TAP del visor des del diàleg."""
            self.set_beat_unit(unit)
            self._undo_touch_base()
            dlg.actualitza_beat_unit(unit)
            tr = self.tempo_trams[idx]
            for sp in (dlg.sp_bpm, dlg.sp_bpm_mob):
                sp.blockSignals(True)
                try:
                    sp.setValue(bpm_unit_mod.de_quarter(
                        float(tr.bpm), unit))
                finally:
                    sp.blockSignals(False)
            dlg.actualitza_info(self._info_clip_tempo(idx))
            senyal = getattr(self, "canvis", None)
            if senyal is not None:
                senyal.emit()
            self.log(f"Beat/TAP: {getattr(self, 'beat_unit', unit)}")
            return True

        dlg.aplicaRequested.connect(_on_aplica)
        dlg.recalculRequested.connect(_on_recalcul)
        dlg.refRequested.connect(_on_ref)
        dlg.beatUnitRequested.connect(_on_beat_unit)
        if dlg.exec_() != QDialog.Accepted:
            return False
        try:
            valors = _valors_dialeg()
        except ValueError as e:
            QMessageBox.warning(self, "Tempo invàlid", str(e))
            return False
        # Si l'últim «Ajusta» ja va aplicar exactament estos valors, no es
        # torna a aplicar: OK només tanca.
        if darrers["valors"] == valors:
            return True
        self._undo_marca()
        try:
            ok = _aplica_actuals()
        finally:
            self._undo_commit()
        return bool(ok)

    def _on_tempo_mogut(self, idx, vora, t):
        """Vora d'un bloc de BPM/compàs arrossegada → **re-tempo** (el ratolí mana).

        El punter fixa els **segons**. Cada costat conserva el seu BPM/compàs
        com a referència i el motor de recalcul busca compassos sencers: pot
        ajustar el BPM, el compàs o el nombre de compassos. Si no hi ha cap
        combinació vàlida, es queda el valor anterior i s'avisa. Els trams
        posteriors no es mouen (sense *ripple*).

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
            nous = mapa_tempo.reenganxa_metadades(trams, nous)
            self._undo_marca()
            self.offset = float(nou_off)
            self.aplica_tempo_trams(nous)
            self._undo_commit()
            return
        avisos = []
        try:
            nous = tempo_map.mou_frontera_retempo(
                trams, p_idx, float(t), self._durada_wav(), offset=offset,
                beats_qm=self._beats_per_validacio(), permissiu=True,
                ref_base=self.ref_tempo_base(), avisos=avisos,
                beat_factor=self.beat_factor())
        except ValueError as e:
            self.avis_editor(f"Frontera de tempo: {e}")
            return
        nous = mapa_tempo.reenganxa_metadades(trams, nous)
        self._undo_marca()
        self.aplica_tempo_trams(nous)
        self._undo_commit()
        for avis in avisos:
            self.avis_editor(f"Frontera: {avis}")

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
        nous = mapa_tempo.reenganxa_metadades(trams, nous)
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
            n = tempo_map.compassos_del_clip(trams[int(idx)])
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

    def crea_rubato_rang(self, ini, fi):
        """Partix el mapa als extrems del rang i marca els trams com a rubato."""
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
        if not trams:
            return False
        for tall in (ini, fi):
            if tall <= tempo_map.TOL or tall >= durada - tempo_map.TOL:
                continue
            try:
                trams = tempo_map.parteix_tram_marcador(
                    trams, tall, durada,
                    offset=getattr(self, "offset", 0.0), permissiu=True)
            except ValueError as e:
                self.avis_editor(f"Rubato: {e}")
                return False
        nous = []
        tocat = False
        for tr in trams:
            dins = (float(tr[0]) >= ini - tempo_map.TOL
                    and float(tr[1]) <= fi + tempo_map.TOL)
            if dins:
                tocat = True
                nous.append(mapa_tempo.TramMapa(
                    float(tr[0]), float(tr[1]), float(tr[2]), "rubato",
                    f"{int(tr[3])}/{int(tr[4])}", "",
                    getattr(tr, "n", None), tr.beat_unit))
            else:
                nous.append(mapa_tempo.TramMapa(
                    float(tr[0]), float(tr[1]), float(tr[2]),
                    getattr(tr, "tipus", "normal"),
                    f"{int(tr[3])}/{int(tr[4])}",
                    getattr(tr, "agrupacio", ""),
                    getattr(tr, "n", None), tr.beat_unit))
        if not tocat:
            self.avis_editor("El rang no conté cap tram de tempo.")
            return False
        self._undo_marca()
        ok = self.aplica_tempo_trams(nous, forcat=True)
        self._undo_commit()
        if ok:
            self.log(f"rubato: rang {ini:.3f}–{fi:.3f}s marcat")
        return bool(ok)

    def converteix_rubato(self, idx):
        """Marca el tram com a rubato conservant tots els camps."""
        trams = list(self.tempo_trams or [])
        if not (0 <= idx < len(trams)):
            return False
        tr = trams[idx]
        if getattr(tr, "tipus", None) == "rubato":
            return False
        nous = list(trams)
        nous[idx] = mapa_tempo.TramMapa(
            tr.ini, tr.fi, tr.bpm, "rubato", tr.compassos,
            tr.agrupacio, getattr(tr, "n", None), tr.beat_unit)
        self._undo_marca()
        ok = self.aplica_tempo_trams(nous, forcat=True)
        self._undo_commit()
        if ok:
            self.log(f"rubato: tram {idx} marcat (només flag de notació)")
        return bool(ok)

    def converteix_normal(self, idx):
        """Treu el flag de rubato conservant tots els camps."""
        trams = list(self.tempo_trams or [])
        if not (0 <= idx < len(trams)):
            return False
        tr = trams[idx]
        if getattr(tr, "tipus", None) != "rubato":
            return False
        nous = list(trams)
        nous[idx] = mapa_tempo.TramMapa(
            tr.ini, tr.fi, tr.bpm, "normal", tr.compassos,
            tr.agrupacio, getattr(tr, "n", None), tr.beat_unit)
        self._undo_marca()
        ok = self.aplica_tempo_trams(nous, forcat=True)
        self._undo_commit()
        if ok:
            self.log(f"rubato: tram {idx} desmarcat (tram normal)")
        return bool(ok)
