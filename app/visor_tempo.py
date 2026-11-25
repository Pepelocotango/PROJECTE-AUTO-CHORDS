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

    def referencia_tempo_base(self, idx=None):
        """Referència del recalcul: el **veí esquerre** del clip.

        Si el clip és el primer (idx 0) no té veí: s'usa el propi clip. La
        referència és sempre local; no hi ha cap BPM/compàs global.
        """
        trams = self._trams_map()
        if not trams:
            return (float(self.bpm), int(self.bpb),
                    int(getattr(self, "beat_type", 4) or 4))
        if idx is None:
            idx = self.tempo_objectiu()
        idx = min(max(0, int(idx)), len(trams) - 1)
        ref_idx = idx - 1 if idx > 0 else idx
        tr = trams[ref_idx]
        return (float(getattr(tr, "bpm", tr[2])),
                int(getattr(tr, "num", tr[3])),
                int(getattr(tr, "den", tr[4])))

    def referencia_tempo_unit(self, idx=None):
        """Unitat de pols del clip de referència (veí esquerre)."""
        trams = self._trams_map()
        if not trams:
            return bpm_unit_mod.DEFECTE
        if idx is None:
            idx = self.tempo_objectiu()
        idx = min(max(0, int(idx)), len(trams) - 1)
        ref_idx = idx - 1 if idx > 0 else idx
        return self.unitat_de_tram(trams[ref_idx])

    def referencia_tempo_a(self, t):
        """Referència per a un tall al temps `t` (clip que el conté)."""
        trams = self._trams_map()
        if not trams:
            return self.referencia_tempo_base(0)
        idx = 0
        for i, tr in enumerate(trams):
            if float(getattr(tr, "ini", tr[0])) <= float(t) + 1e-9:
                idx = i
            else:
                break
        return self.referencia_tempo_base(idx)

    def escolta_tram(self, ini, fi, bpm, num, den,
                     beat_unit=bpm_unit_mod.DEFECTE):
        """Escolta una proposta (loop + metrònom propi) sense aplicar res.

        Guarda l'estat de reproducció, loop i metrònom i el restaura amb
        `atura_escolta_tram()`. Retorna `False` si no hi ha reproductor.
        """
        self.atura_escolta_tram()
        ini = float(ini)
        fi = float(fi)
        if fi <= ini or getattr(self, "player", None) is None:
            return False
        self._escolta_estat = {
            "sona": bool(getattr(self, "sona", False)),
            "pos": float(getattr(self, "pos", 0.0)),
            "loop": (getattr(self, "loop_a", None),
                     getattr(self, "loop_b", None),
                     bool(getattr(self, "loop_on", False))),
            "metro": (bool(getattr(self, "metro_on", False)),
                      getattr(self, "metro_forcat", None)),
        }
        self._fixa_loop(ini, fi, activa=True, alinea=False)
        self.set_metro_forcat(float(bpm), int(num), ini, int(den), "auto",
                              "auto")
        self.set_metro(True)
        if getattr(self, "sona", False):
            self.ves_a(ini)
        else:
            self.pos = ini
            self.timeline.set_position(ini)
            self.play_stop()
        if getattr(self, "proc", None) is None:
            self.atura_escolta_tram()
            return False
        return True

    def atura_escolta_tram(self):
        """Atura l'audició i restaura loop, metrònom i reproducció previs."""
        estat = getattr(self, "_escolta_estat", None)
        if not estat:
            return False
        self._escolta_estat = None
        sona = bool(getattr(self, "sona", False))
        if sona and not estat["sona"]:
            self.play_stop()
        la, lb, lon = estat["loop"]
        self._fixa_loop(la, lb, activa=lon, alinea=False)
        m_on, m_forc = estat["metro"]
        if m_forc is None:
            self.set_metro_forcat(None)
        else:
            vals = list(m_forc)
            if len(vals) == 5:
                vals.append("auto")
            self.set_metro_forcat(*vals)
        self.set_metro(m_on)
        if estat["sona"]:
            self.ves_a(float(estat["pos"]))
        return True

    def _trams_map(self):
        """`self.tempo_trams` com a `TramMapa` (accepta tuples antigues de 5).

        El model pot arribar amb tuples de 5 camps (motor, desfer antic o codi
        de proves); estes edicions lliguen `num`/`den`/`tipus` i han de vore
        sempre `TramMapa`.
        """
        return [mapa_tempo.des_de_tupla(t) for t in (self.tempo_trams or ())]

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

    def _valida_unitat_tram(self, tram, context="Tempo"):
        """L3: la unitat del tram ha d'encaixar amb el compàs resultant."""
        unit = self.unitat_de_tram(tram)
        try:
            num, den = int(tram[3]), int(tram[4])
        except (TypeError, ValueError, IndexError):
            return True
        if bpm_unit_mod.encaixa_en_compas(unit, num, den):
            return True
        sugg = bpm_unit_mod.unitat_per_defecte(
            num, den, getattr(tram, "agrupacio", "") or "")
        self.avis_editor(
            f"{context}: el compàs {num}/{den} no encaixa amb la unitat "
            f"{unit}; canvia la unitat a {sugg} abans d'aplicar "
            "(no s'ha tocat res).")
        return False

    def beat_factor(self, unit=None):
        """Negres que val el pols detectat (negra=1, punt=1.5, corxera=0.5)."""
        u = self.unitat_objectiu() if unit is None else unit
        return bpm_unit_mod.factor(u)

    def canvia_unitat_tram(self, idx, unit, mode="mantenir_tempo",
                           desa=True):
        """Canvia la unitat de pols d'un tram mantenint les fronteres.

        `mode="mantenir_tempo"` conserva el BPM intern (el so no canvia).
        `mode="mantenir_numero"` conserva el número visible i recalcula el
        BPM intern; el recalc fix manté N enter i fronteres.
        """
        trams = self._trams_map()
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
                    tmp, idx, self._durada_wav(), beats_qm=None)
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
            agr = getattr(tr, "agrupacio", "") or ""
            preferida = bpm_unit_mod.unitat_per_defecte(
                int(tr.num), int(tr.den), agr)
            if preferida != unit:
                self.avis_editor(
                    f"Unitat tram {idx + 1}: {unit} no alinea amb "
                    f"l'agrupació (preferida {preferida}); es respecta la "
                    "tria.")
            else:
                self.log(f"unitat tram {idx}: {unit_actual} → {unit} "
                         f"({mode})")
        return ok

    def tempo_objectiu(self):
        """Índex del tram de tempo objectiu.

        Si hi ha un tram de tempo seleccionat, mana eixe; si no, el transport
        (tram 0). Decisió 2026-10-19.
        """
        kind, idx = self.seleccio_activa()
        if kind == "tempo" and self._index_valid("tempo", idx):
            return int(idx)
        return 0

    def tempo_objectiu_vals(self):
        """`(idx, bpm, num, den)` del tram objectiu (o del transport)."""
        trams = self._trams_map()
        idx = self.tempo_objectiu()
        if not trams:
            return (idx, float(self.bpm), int(self.bpb),
                    int(getattr(self, "beat_type", 4) or 4))
        idx = min(max(0, int(idx)), len(trams) - 1)
        s = trams[idx]
        return (idx, float(s[2]), int(s[3]), int(s[4]))

    def _amb_unitat(self, nous, idx, beat_unit):
        """Retorna el mapa amb la unitat de pols del tram `idx` canviada."""
        if beat_unit is None:
            return nous
        trams = list(nous or [])
        i = int(idx)
        if not (0 <= i < len(trams)):
            return trams
        unit = bpm_unit_mod.normalitza(beat_unit)
        tr = trams[i]
        if getattr(tr, "beat_unit", None) == unit:
            return trams
        trams[i] = mapa_tempo.TramMapa(
            float(tr[0]), float(tr[1]), float(tr[2]),
            getattr(tr, "tipus", "normal"),
            f"{int(tr[3])}/{int(tr[4])}",
            getattr(tr, "agrupacio", ""), getattr(tr, "n", None), unit)
        return trams

    def _unitat_en_canvi_compas(self, vell, nou, beat_unit=None):
        """Unitat resultant en canviar el compàs (§13.4).

        - Si el compàs no canvia, es conserva la unitat.
        - Un `beat_unit` explícit té prioritat, però ha d'encaixar.
        - Si la unitat vella era la derivada, passa a la derivada del compàs
          nou.
        - Si era explícita i encaixa, es conserva.
        - Si era explícita i no encaixa, no s'aplica res: `ValueError` amb la
          unitat derivada suggerida.
        """
        def _n(t, i):
            return int(getattr(t, "num" if i == 3 else "den", t[i]))

        num_vell, den_vell = _n(vell, 3), _n(vell, 4)
        num_nou, den_nou = _n(nou, 3), _n(nou, 4)
        agr_nou = getattr(nou, "agrupacio", "") or ""
        if (num_vell, den_vell) == (num_nou, den_nou):
            if beat_unit is not None:
                return bpm_unit_mod.normalitza(beat_unit)
            return self.unitat_de_tram(vell)

        derivada_vella = bpm_unit_mod.unitat_per_defecte(
            num_vell, den_vell, getattr(vell, "agrupacio", "") or "")
        unit_vella = self.unitat_de_tram(vell)
        if beat_unit is not None:
            unit = bpm_unit_mod.normalitza(beat_unit)
        elif unit_vella == derivada_vella:
            unit = bpm_unit_mod.unitat_per_defecte(num_nou, den_nou, agr_nou)
        else:
            unit = unit_vella
        if not bpm_unit_mod.encaixa_en_compas(
                unit, num_nou, den_nou):
            sugg = bpm_unit_mod.unitat_per_defecte(
                num_nou, den_nou, agr_nou)
            raise ValueError(
                f"el compàs {num_nou}/{den_nou} no encaixa amb la unitat "
                f"{unit}; cal canviar-la a {sugg} abans d'aplicar "
                "(no s'ha tocat res)")
        return unit

    def edita_tempo_objectiu(self, idx, bpm, num, den, desa=True, repara=True,
                             agrupacio=None, beat_unit=None,
                             permet_ultim_fraccionari=True):
        """Aplica BPM/compàs a un tram de tempo (0 = transport).

        Contracte §13.4/§13.5: **tots** els clips mantenen `N` enter. En un
        tram interior, `N` exacte deriva `fi`; el veí conserva el seu `N` enter
        i recalcula el BPM. En l'últim/únic, el final no es mou: `N`
        s'arrodoneix a l'enter més pròxim i el BPM es deriva.

        Amb `desa=False` (TAP en viu) s'usa el camí permissiu: arrodoneix `N`
        i ajusta el BPM, sense moure les fronteres.
        """
        trams = self._trams_map()
        if not trams:
            trams = [mapa_tempo.TramMapa(
                0.0, self._durada_wav(), float(bpm), "normal",
                f"{int(num)}/{int(den)}")]
        idx = min(max(0, int(idx)), len(trams) - 1)
        # Còpia del tram ABANS de tocar-lo: `_unitat_en_canvi_compas` ha de
        # comparar el compàs vell amb el nou (si mirem `trams[idx]` després
        # del reset d'agrupació, la comparació sempre surt igual i la unitat
        # de pols no es recalcula).
        tram_vell = trams[idx]
        compas_canviat = ((int(num), int(den)) !=
                          (int(tram_vell.num), int(tram_vell.den)))
        if compas_canviat and agrupacio is None:
            # El motor no ha de vore l'agrupació vella sobre un compàs nou.
            trams = list(trams)
            tr0 = trams[idx]
            agr0 = tempo_map.agrupacio_a_text(
                tempo_map.agrupacio_compas(int(num), int(den)))
            trams[idx] = mapa_tempo.TramMapa(
                float(tr0.ini), float(tr0.fi), float(tr0.bpm), tr0.tipus,
                f"{int(num)}/{int(den)}", agr0, getattr(tr0, "n", None),
                getattr(tr0, "beat_unit", None))
        if desa:
            try:
                nous = mapa_tempo.recalcula_tram_c(
                    trams, idx, self._durada_wav(),
                    bpm=float(bpm), num=int(num), den=int(den),
                    camp="bpm", permet_ultim_fraccionari=True)
            except ValueError as e:
                self.avis_editor(f"Tempo: {e}")
                return False
        else:
            try:
                nous5 = tempo_map.canvia_bpm_local(
                    [tuple(t) for t in trams], idx, float(bpm),
                    self._durada_wav(), num=num, den=den,
                    beats_qm=None, permissiu=True,
                    permet_ultim_fraccionari=permet_ultim_fraccionari)
            except ValueError as e:
                self.avis_editor(f"Tempo: {e}")
                return False
            if not nous5:
                return False
            nous = mapa_tempo.reenganxa_metadades(trams, nous5)
            # En el TAP, `n` és el resultat nou (pot ser fraccionari a
            # l'últim clip); no el reenganxem del tram vell.
            t5 = nous5[idx]
            bq = float(t5[3]) * 4.0 / float(t5[4])
            dt = float(t5[1]) - float(t5[0])
            if bq > 0 and dt > 0:
                nous[idx] = mapa_tempo.TramMapa(
                    float(t5[0]), float(t5[1]), float(t5[2]),
                    getattr(nous[idx], "tipus", "normal"),
                    f"{int(t5[3])}/{int(t5[4])}",
                    getattr(nous[idx], "agrupacio", ""),
                    float(dt) * float(t5[2]) / (bq * 60.0),
                    getattr(nous[idx], "beat_unit", None))
        try:
            unit = self._unitat_en_canvi_compas(
                tram_vell, nous[idx], beat_unit)
        except ValueError as e:
            self.avis_editor(f"Tempo: {e}")
            return False
        nous = self._amb_unitat(nous, idx, unit)
        if not self._valida_unitat_tram(nous[idx], "Tempo"):
            return False
        if (int(num), int(den)) != (int(trams[idx].num), int(trams[idx].den)):
            agrupacio = tempo_map.agrupacio_a_text(
                tempo_map.agrupacio_compas(int(num), int(den)))
        if agrupacio is not None:
            agr = tempo_map.valida_agrupacio(
                agrupacio, nous[idx].num, nous[idx].den)
            nou = nous[idx]
            nous[idx] = mapa_tempo.TramMapa(
                nou.ini, nou.fi, nou.bpm, nou.tipus, nou.compassos, agr,
                getattr(nou, "n", None), nou.beat_unit)
        if not desa:
            errors = self._bloquejos_tempo_errors(nous)
            if errors:
                self.avis_editor(
                    "Bloquejat: canvi de " + ", ".join(errors) + ".")
                return False
        # El transport només pren valors d'un tros normal.
        self.bpm = float(nous[0][2])
        self.bpb = int(nous[0][3])
        self.beat_type = int(nous[0][4])
        if desa:
            return bool(self.aplica_tempo_trams(nous))
        self.tempo_trams = nous
        self._actualitza_temps()
        return True

    def edita_tempo_tap_mobil(self, idx, bpm):
        """TAP amb frontera mòbil: BPM exacte, N actual i fi desplaçable.

        En un clip interior, mou `fi` a la línia de compàs més pròxima amb el
        BPM nou i recalcula N (enter) i el veí; en l'últim clip, la fi de la
        WAV no es mou i el N queda fraccionari.
        No desa: la sessió de TAP ho fa en tancar-se.
        """
        trams = self._trams_map()
        idx = int(idx)
        if not (0 <= idx < len(trams)):
            return False
        tr = trams[idx]
        try:
            bpm, num, den = tempo_map.valida_tempo(
                float(bpm), int(tr.num), int(tr.den))
        except ValueError as e:
            self.avis_editor(f"TAP mòbil: {e}")
            return False
        bq = float(num) * 4.0 / float(den)
        dt = float(tr.fi) - float(tr.ini)
        if bq <= 0 or dt <= 0:
            return False
        ultim = (idx == len(trams) - 1)
        try:
            if ultim:
                n = dt * bpm / (bq * 60.0)
                nous = list(trams)
                nous[idx] = mapa_tempo.TramMapa(
                    float(tr.ini), float(tr.fi), float(bpm),
                    getattr(tr, "tipus", "normal"), f"{num}/{den}",
                    getattr(tr, "agrupacio", ""), float(n),
                    getattr(tr, "beat_unit", None))
            else:
                # Fi a la línia de compàs més pròxima amb el BPM nou;
                # N es recalcula a partir d'eixa durada.
                compas = bq * 60.0 / float(bpm)
                n = max(1, int(round(dt / compas)))
                nous = mapa_tempo.recalcula_tram_c(
                    trams, idx, self._durada_wav(), n=n,
                    bpm=float(bpm), num=num, den=den, camp="n",
                    permet_ultim_fraccionari=False)
        except ValueError as e:
            self.avis_editor(f"TAP mòbil: {e}")
            return False
        if not self._valida_unitat_tram(nous[idx], "TAP"):
            return False
        errors = self._bloquejos_tempo_errors(nous)
        if errors:
            self.avis_editor(
                "Bloquejat: canvi de " + ", ".join(errors) + ".")
            return False
        self.bpm = float(nous[0][2])
        self.bpb = int(nous[0][3])
        self.beat_type = int(nous[0][4])
        self.tempo_trams = nous
        self._actualitza_temps()
        return True

    def edita_compas_objectiu(self, idx, num, den, desa=True,
                              beat_unit=None, bpm_visible=None,
                              agrupacio=None):
        """Canvia el compàs conservant sempre el **BPM intern** (§13.4).

        El BPM visible es recalcula amb la unitat resultant; mai no es canvia
        el BPM intern per conservar el número visible. Si la unitat vella era
        la derivada, passa a la derivada del compàs nou; si era explícita i
        encaixa, es conserva; si no encaixa, no s'aplica res.

        En canviar el compàs, l'agrupació passa al **valor per defecte** del
        compàs nou (`7/8` → `7`, `3/4` → `3`…); es pot passar una
        `agrupacio` explícita si el cridador ja ha triat una altra.

        `bpm_visible` es conserva per compatibilitat d'API, però no altera el
        BPM intern.
        """
        trams = self._trams_map()
        idx = int(idx)
        if not (0 <= idx < len(trams)):
            return False
        tr = trams[idx]
        try:
            num, den = int(num), int(den)
            tempo_map.valida_tempo(float(tr.bpm), num, den)
        except (TypeError, ValueError) as e:
            self.avis_editor(f"Compàs: {e}")
            return False
        unit_vella = self.unitat_de_tram(tr)
        if agrupacio is None and (num, den) != (int(tr.num), int(tr.den)):
            agrupacio = tempo_map.agrupacio_a_text(
                tempo_map.agrupacio_compas(num, den))
        try:
            provisional = mapa_tempo.TramMapa(
                float(tr.ini), float(tr.fi), float(tr.bpm),
                getattr(tr, "tipus", "normal"), f"{num}/{den}",
                agrupacio or getattr(tr, "agrupacio", ""),
                getattr(tr, "n", None), unit_vella)
            unit_nova = self._unitat_en_canvi_compas(
                tr, provisional, beat_unit)
        except (TypeError, ValueError) as e:
            self.avis_editor(f"Compàs: {e}")
            return False
        return bool(self.edita_tempo_objectiu(
            idx, float(tr.bpm), num, den, desa=desa, beat_unit=unit_nova,
            agrupacio=agrupacio))

    def edita_n_compassos(self, idx, n, num, den, desa=True, beat_unit=None):
        """Edita **N compassos** i compàs; el BPM es recalcula automàticament.

        Regla C: N i compàs són exactes; en interiors es deriva `fi` i el veí
        recalcula el BPM. En l'últim/únic, N exacte i BPM recalculat amb el
        final fix.
        """
        trams = self._trams_map()
        if not trams:
            return False
        idx = min(max(0, int(idx)), len(trams) - 1)
        tram_vell = trams[idx]
        compas_canviat = ((int(num), int(den)) !=
                          (int(tram_vell.num), int(tram_vell.den)))
        if compas_canviat:
            trams = list(trams)
            tr0 = trams[idx]
            agr0 = tempo_map.agrupacio_a_text(
                tempo_map.agrupacio_compas(int(num), int(den)))
            trams[idx] = mapa_tempo.TramMapa(
                float(tr0.ini), float(tr0.fi), float(tr0.bpm), tr0.tipus,
                f"{int(num)}/{int(den)}", agr0, getattr(tr0, "n", None),
                getattr(tr0, "beat_unit", None))
        try:
            nous = mapa_tempo.recalcula_tram_c(
                trams, idx, self._durada_wav(),
                n=int(n), bpm=float(trams[idx].bpm), num=int(num),
                den=int(den), camp="n", permet_ultim_fraccionari=True)
        except ValueError as e:
            self.avis_editor(f"Compassos: {e}")
            return False
        try:
            unit = self._unitat_en_canvi_compas(
                tram_vell, nous[idx], beat_unit)
        except ValueError as e:
            self.avis_editor(f"Compassos: {e}")
            return False
        nous = self._amb_unitat(nous, idx, unit)
        if (int(num), int(den)) != (int(trams[idx].num), int(trams[idx].den)):
            agr = tempo_map.agrupacio_a_text(
                tempo_map.agrupacio_compas(int(num), int(den)))
            nou = nous[idx]
            nous[idx] = mapa_tempo.TramMapa(
                nou.ini, nou.fi, nou.bpm, nou.tipus, nou.compassos, agr,
                getattr(nou, "n", None), nou.beat_unit)
        if not self._valida_unitat_tram(nous[idx], "Compassos"):
            return False
        self.bpm = float(nous[0][2])
        self.bpb = int(nous[0][3])
        self.beat_type = int(nous[0][4])
        if desa:
            ok = bool(self.aplica_tempo_trams(nous))
        else:
            errors = self._bloquejos_tempo_errors(nous)
            if errors:
                self.avis_editor(
                    "Bloquejat: canvi de " + ", ".join(errors) + ".")
                return False
            self.tempo_trams = nous
            self._actualitza_temps()
            ok = True
        if ok:
            self.log(f"compassos tram {idx}: {trams[idx][2]:g} → "
                     f"{self.tempo_trams[idx][2]:.2f} BPM "
                     f"({int(n)} compassos de {int(num)}/{int(den)})")
        return ok

    def edita_tempo_guiat(self, idx, *, bpm=None, num=None, den=None, n=None):
        """Edita un clip recalcular els camps que no s'han fixat.

        Prioritat: compàs > BPM > N > referència. No consulta QM: els beats
        QM només s'usen als Talls QM.
        """
        trams = self._trams_map()
        idx = int(idx)
        if not (0 <= idx < len(trams)):
            self.avis_editor("Aquest clip de tempo ja no existeix.")
            return False
        tr = trams[idx]
        num_t = int(tr.num if num is None else num)
        den_t = int(tr.den if den is None else den)
        bpm_t = float(tr.bpm if bpm is None else bpm)
        try:
            bpm_t, num_t, den_t = tempo_map.valida_tempo(
                bpm_t, num_t, den_t)
        except ValueError as e:
            self.avis_editor(f"Tempo: {e}")
            return False
        dt = float(tr[1]) - float(tr[0])
        if dt <= tempo_map.TOL:
            self.avis_editor("Tempo: el clip no té durada.")
            return False
        bq = float(num_t) * 4.0 / float(den_t)
        compas_canviat = ((int(num_t), int(den_t)) !=
                          (int(tr.num), int(tr.den)))
        base = trams
        if compas_canviat:
            base = list(trams)
            agr0 = tempo_map.agrupacio_a_text(
                tempo_map.agrupacio_compas(int(num_t), int(den_t)))
            base[idx] = mapa_tempo.TramMapa(
                float(tr.ini), float(tr.fi), float(tr.bpm), tr.tipus,
                f"{int(num_t)}/{int(den_t)}", agr0,
                getattr(tr, "n", None), getattr(tr, "beat_unit", None))
        try:
            if n is not None:
                n_t = float(n)
                if idx != len(trams) - 1:
                    n_t = max(1, int(round(n_t)))
                if n_t <= 0:
                    raise ValueError("N ha de ser positiu.")
                if bpm is None:
                    bpm_t = n_t * bq * 60.0 / dt
            else:
                n_t = max(1, int(round(dt * bpm_t / (bq * 60.0))))
            nous = mapa_tempo.recalcula_tram_c(
                base, idx, self._durada_wav(), n=n_t, bpm=bpm_t,
                num=num_t, den=den_t, camp="n",
                permet_ultim_fraccionari=True)
        except ValueError as e:
            self.avis_editor(f"Tempo: {e}")
            return False
        try:
            unit = self._unitat_en_canvi_compas(tr, nous[idx], None)
        except ValueError as e:
            self.avis_editor(f"Tempo: {e}")
            return False
        nous = self._amb_unitat(nous, idx, unit)
        if (int(num_t), int(den_t)) != (int(tr.num), int(tr.den)):
            agr = tempo_map.agrupacio_a_text(
                tempo_map.agrupacio_compas(int(num_t), int(den_t)))
            nou = nous[idx]
            nous[idx] = mapa_tempo.TramMapa(
                nou.ini, nou.fi, nou.bpm, nou.tipus, nou.compassos, agr,
                getattr(nou, "n", None), nou.beat_unit)
        if not self._valida_unitat_tram(nous[idx], "Tempo"):
            return False
        self.bpm = float(nous[0][2])
        self.bpb = int(nous[0][3])
        self.beat_type = int(nous[0][4])
        ok = bool(self.aplica_tempo_trams(nous))
        if ok:
            self.log(
                f"editor guiat tram {idx}: {float(tr[2]):.3f} → "
                f"{float(self.tempo_trams[idx][2]):.3f} BPM · "
                f"{int(self.tempo_trams[idx].num)}/"
                f"{int(self.tempo_trams[idx].den)} · "
                f"N={float(self.tempo_trams[idx].n):g}")
        return ok

    def _repara_compas_no_enter(self, idx, bpm, num, den, n_compas,
                                trams, desa=True):
        """Diàleg per reparar un canvi de compàs que deixa N no enter.

        Opcions: ajustar el BPM perquè N siga enter amb el compàs triat,
        canviar a la signatura canònica que proposa el recalcul (base + beats),
        o cancel·lar. Retorna el resultat de l'opció aplicada.
        """
        tram = trams[int(idx)]
        fi = float(tram[1])
        base = tempo_map._base_tram(tram, int(idx))
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

        bpm_vei, num_vei, den_vei = self.referencia_tempo_base(idx)
        factor = self.beat_factor()
        canon = None
        try:
            canon = tempo_recalc.recalculca_tram(
                dt, bpm_vei, num_vei, den_vei, n_beats=None,
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
        # El normalitzador preserva `tipus`/`compassos` (rubato inclòs). Un
        # BPM 0/fora de banda en una còpia trencada es repara amb el transport
        # abans de validar; els mapes desats invàlids es rebutgen en carregar.
        entrada = []
        for t in (self.tempo_trams or []):
            if isinstance(t, mapa_tempo.TramMapa):
                entrada.append(t)
                continue
            try:
                bpm = float(t[2])
            except (TypeError, ValueError, IndexError):
                bpm = None
            if bpm is None or not (limits.BPM_MIN <= bpm <= limits.BPM_MAX):
                t = (t[0], t[1], float(self.bpm), *t[3:])
            entrada.append(t)
        try:
            trams, avisos = mapa_tempo.normalitza_trams_map(
                entrada, d, log=self.log, permet_ultim_fraccionari=True)
        except ValueError as e:
            self.log(f"tempo: mapa no vàlid: {e}")
            trams, avisos = [], [str(e)]
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
        self.tempo_map = TempoMap(self.tempo_trams)
        self.comprova_mapa_sencers()
        return self.tempo_map

    def comprova_mapa_sencers(self, forca=False):
        """Emite `mapaInconsistent` si algun clip no dona compassos sencers.

        S'executa cada vegada que es reconstrueix el `TempoMap`; `forca=True`
        fa que el senyal s'emeta encara que el text coincidisca amb l'anterior
        (en carregar un projecte o en connectar la finestra).
        """
        issues = tempo_map.problemes_compassos_sencers(
            self.tempo_trams, self._durada_wav())
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

    def aplica_tempo_trams(self, trams, forcat=False,
                           ignora_bloquejos=False, antics=None):
        """Aplica un mapa de tempo/compàs nou (des del diàleg).

        Normalitza (contigu, cobreix la WAV), actualitza el **transport** amb el
        valor inicial, reconstrueix el mapa, refresca el timeline i desa. Retorna
        `True` si s'ha aplicat.
        """
        entrada = list(trams or [])
        try:
            nous, avisos = mapa_tempo.normalitza_trams_map(
                entrada, self._durada_wav(), log=self.log,
                permet_ultim_fraccionari=True)
        except ValueError as e:
            self.log(f"tempo: mapa no vàlid: {e}")
            return False
        for avís in avisos:
            self.log(f"tempo: {avís}")
        if not nous:
            return False
        if not ignora_bloquejos:
            # Els candaus globals sempre manen; els locals del diàleg
            # s'hi sumen i només vigilen el clip seleccionat.
            errors = self._bloquejos_tempo_errors(nous, antics=antics)
            local = getattr(self, "_bloquejos_tempo_dialog", None)
            if local is not None:
                bloquejos, idx_local = local
                for err in self._bloquejos_tempo_errors(
                        nous, antics=antics, bloquejos=bloquejos,
                        idx=idx_local):
                    if err not in errors:
                        errors.append(err)
            if errors:
                text = ("Bloquejat: canvi de " + ", ".join(errors)
                        + ". Desactiva el candau o ajusta l'operació.")
                self.log(text)
                self.avis_editor(text)
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

    def aplica_tempo_validat(self, trams, msg="Tempo",
                             ignora_bloquejos=False):
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
                permet_ultim_fraccionari=True)
        except ValueError as e:
            self.avis_editor(f"{msg}: {e}")
            return False
        nous = mapa_tempo.reenganxa_metadades(entrada, nous)
        return bool(self.aplica_tempo_trams(
            nous, ignora_bloquejos=ignora_bloquejos))

    def _normalitza_mapa_viu(self, trams, msg=None):
        """Mapa validat per a un gest en viu (permissiu, F2).

        Comprova BPM/compàs, contigüitat, cobertura, el mínim d'un compàs
        1/16 a 350 BPM i **N enter**; si cal, arrodoneix `N` i ajusta el BPM.
        Si el mapa no val, el gest es rebutja amb un avís.
        """
        durada = self._durada_wav()
        try:
            return tempo_map.valida_i_normalitza_permissiu(
                trams, durada, permet_ultim_fraccionari=True)
        except ValueError as e:
            if msg:
                self.log(f"{msg}: el mapa no complix el contracte de clips "
                         f"({e})")
            raise

    def _info_clip_tempo(self, idx):
        """Tota la informació derivada del clip de tempo `idx` (per al diàleg)."""
        trams = self._trams_map()
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
        n_fracc = False
        if n_real is not None:
            n_enter = max(1, tempo_map._enter_mes_proper(float(n_real)))
            n_valid = abs(float(n_real) - float(n_enter)) <= 1e-6
            n_fracc = bool(not n_valid and idx == len(trams) - 1)
            n_valid = bool(n_valid or n_fracc)
        try:
            bq = float(num) * 4.0 / float(den) if den else 0.0
            dur_compas = tempo_map.durada_compas(bpm, num, den)
        except (TypeError, ValueError, ZeroDivisionError):
            bq = 0.0
            dur_compas = 0.0
        bpm_vei, num_vei, den_vei = self.referencia_tempo_base(idx)
        desviacio = ((bpm / bpm_vei) - 1.0) * 100.0 if bpm_vei else None
        ratio = (bpm / bpm_vei) if bpm_vei else None
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
            "n_valid": n_valid, "n_fracc": n_fracc,
            "bpm": bpm,
            "bpm_mostra": bpm_unit_mod.de_quarter(
                bpm, self.unitat_de_tram(tr)),
            "bpm_unit": bpm_unit_mod.etiqueta(self.bpm_unit),
            "vei_bpm": bpm_vei,
            "vei_compas": f"{int(num_vei)}/{int(den_vei)}",
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
            "vei_esq": _resum(idx - 1) if idx > 0 else None,
            "vei_dret": _resum(idx + 1) if idx < len(trams) - 1 else None,
            "bpm_ok": (tempo_map.BPM_EDIT_MIN <= bpm
                       <= tempo_map.BPM_EDIT_MAX),
            "durada_ok": durada >= limits.TEMPS_MIN_CLIP,
            "min_durada": limits.TEMPS_MIN_CLIP,
        }

    def canvia_unitat_ui(self, idx):
        """Obre el diàleg de canvi d'unitat de pols d'un clip de tempo."""
        trams = self._trams_map()
        idx = int(idx)
        if not (0 <= idx < len(trams)):
            self.avis_editor("Unitat: el clip de tempo no existeix.")
            return False
        tr = trams[idx]
        unit = self.unitat_de_tram(tr)
        dlg = dialegs.DialegCanviUnitat(
            self, etiqueta=f"Tram {idx + 1}", bpm=float(tr.bpm),
            unit_vella=unit, unit_nova=unit)
        if dlg.exec_() != QDialog.Accepted:
            return False
        _bpm, unit_nova, mode = dlg.resultat()
        return bool(self.canvia_unitat_tram(idx, unit_nova, mode))

    def _on_tempo_edit(self, idx):
        """Inspector del clip de tempo: delega tota edició als motors vius."""
        trams = self._trams_map()
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
        es_ultim = (idx == len(trams) - 1)
        es_rubato = getattr(s, "tipus", "normal") == "rubato"
        dlg = dialegs.DialegTramTempo(
            self, inici=s[0], bpm=s[2], num=s[3], den=s[4],
            inicial=(idx == 0), text_inici=lbl, unit=unit_tram,
            n_actual=n_actual, durada=durada,
            info=self._info_clip_tempo(idx), beat_unit=unit_tram,
            es_ultim=es_ultim, es_rubato=es_rubato)
        aplicat = {"ok": False}

        def _executa(accio, locks=None, amb_undo=True):
            avisos = []
            avis_original = self.avis_editor
            self.avis_editor = lambda text: (
                avisos.append(str(text)), avis_original(text))
            abans = (self.bpm, self.bpb, self.beat_type)
            abans_trams = [tuple(t) for t in (self.tempo_trams or [])]
            actius = dict(locks or {})
            self._bloquejos_tempo_dialog = (
                (actius, idx) if any(actius.values()) else None)
            if amb_undo:
                self._undo_marca()
            try:
                try:
                    ok = accio()
                except ValueError as e:
                    avisos.append(str(e))
                    ok = False
            finally:
                self._bloquejos_tempo_dialog = None
                if amb_undo:
                    self._undo_commit()
                self.avis_editor = avis_original
            if not ok:
                self.bpm, self.bpb, self.beat_type = abans
            canviat = [tuple(t) for t in (self.tempo_trams or [])] != abans_trams
            return bool(ok), avisos, bool(canviat)

        def _refresca():
            dlg.actualitza_estat(self._info_clip_tempo(idx))

        def _on_camp(camp):
            try:
                bpm, num, den, n = dlg.valors_camps()
                tempo_map.valida_tempo(bpm, num, den)
            except ValueError as e:
                QMessageBox.warning(dlg, "Tempo invàlid", str(e))
                return False
            locks = dlg.locks()
            if locks.get(camp):
                QMessageBox.warning(
                    dlg, "Camp bloquejat",
                    "El camp està bloquejat; desactiva el candau abans "
                    "d'aplicar-lo.")
                return False
            mode = dlg.mode()
            if (camp == "n" and not es_ultim
                    and abs(n - round(n)) > 1e-3):
                QMessageBox.warning(
                    dlg, "N invàlid",
                    "N ha de ser un enter positiu als clips interiors.")
                return False
            if mode == "mobil" and es_ultim:
                QMessageBox.warning(
                    dlg, "Recalcul mòbil",
                    "L'últim clip no pot moure la fi de la WAV.")
                return False
            if mode == "fix":
                def accio():
                    trams = list(self.tempo_trams or [])
                    tr = trams[idx]
                    if camp == "bpm":
                        nou = self._resol_fix_bpm(tr, bpm, idx=idx)
                    elif camp == "compas":
                        nou = self._resol_fix_compas(
                            tr, num, den, idx=idx)
                    else:
                        return bool(self.canvia_compassos_tram(
                            idx, n_new=n, num=num, den=den))
                    trams[idx] = nou
                    return bool(self.aplica_tempo_trams(trams))
            elif camp == "bpm":
                accio = lambda: self._edita_bpm_mobil(idx, bpm)
            elif camp == "compas":
                accio = lambda: self._edita_compas_mobil(idx, num, den)
            else:
                accio = lambda: self._edita_n_mobil(idx, n)
            # `canvia_compassos_tram` ja obri/tanca el seu propi desfer.
            amb_undo = not (mode == "fix" and camp == "n")
            ok, avisos, canviat = _executa(
                accio, locks, amb_undo=amb_undo)
            if ok:
                aplicat["ok"] = True
                _refresca()
                if not canviat:
                    self.log("Aplica: sense canvis")
                return True
            if not canviat and not avisos:
                self.log("Aplica: sense canvis")
                return True
            QMessageBox.warning(
                dlg, "Aplica",
                " ".join(avisos) or
                "No s'ha pogut aplicar el camp amb estes opcions.")
            return False

        def _on_operacio(op):
            mapa = {
                "mes1": {"delta_compassos": 1},
                "menys1": {"delta_compassos": -1},
                "x2": {"factor": 2.0},
                "div2": {"factor": 0.5},
            }
            kw = mapa.get(op)
            if kw is None:
                return False
            ok, avisos, canviat = _executa(
                lambda: self.canvia_compassos_tram(idx, **kw),
                dlg.locks(), amb_undo=False)
            if ok:
                aplicat["ok"] = True
                _refresca()
                if not canviat:
                    self.log("Operació mètrica: sense canvis")
                return True
            if not canviat and not avisos:
                self.log("Operació mètrica: sense canvis")
                return True
            QMessageBox.warning(
                dlg, "Operació mètrica",
                " ".join(avisos) or "No s'ha pogut aplicar l'operació.")
            return False

        def _on_rubato(desitjat):
            if bool(desitjat) == bool(dlg._es_rubato):
                return
            ok, avisos, canviat = _executa(
                (lambda: self.converteix_rubato(idx)) if desitjat else
                (lambda: self.converteix_normal(idx)),
                amb_undo=False)
            if ok:
                aplicat["ok"] = True
                _refresca()
                if not canviat:
                    self.log("Tipus: sense canvis")
            else:
                dlg.chk_rubato.blockSignals(True)
                dlg.chk_rubato.setChecked(bool(dlg._es_rubato))
                dlg.chk_rubato.blockSignals(False)
                QMessageBox.warning(
                    dlg, "Tipus",
                    " ".join(avisos) or "No s'ha pogut canviar el tipus.")

        def _on_unitat(unit, mode):
            ok = bool(self.canvia_unitat_tram(idx, unit, mode))
            if ok:
                aplicat["ok"] = True
                tr = self._trams_map()[idx]
                dlg.refresca_unitat(
                    float(tr.bpm), self.unitat_de_tram(tr))
                _refresca()
            else:
                QMessageBox.warning(
                    dlg, "Unitat de pols",
                    "No s'ha pogut canviar la unitat; no s'ha tocat res.")
            return ok

        dlg.campRequested.connect(_on_camp)
        dlg.operacioRequested.connect(_on_operacio)
        dlg.rubatoRequested.connect(_on_rubato)
        dlg.unitatRequested.connect(_on_unitat)
        dlg.exec_()
        return bool(aplicat["ok"])

    def _reseteja_compas_canviat(self, antics, nous):
        """Ajusta agrupació i unitat si un clip canvia de compàs.

        La unitat derivada passa a la derivada nova; una unitat explícita
        compatible es conserva; una d'incompatible fa fallar l'operació.
        """
        antics = [mapa_tempo.des_de_tupla(a) for a in (antics or ())]
        out = []
        for j, n in enumerate(nous or ()):
            n = mapa_tempo.des_de_tupla(n)
            if j < len(antics):
                a = antics[j]
                if (int(a.num), int(a.den)) != (int(n.num), int(n.den)):
                    agr = tempo_map.agrupacio_a_text(
                        tempo_map.agrupacio_compas(int(n.num), int(n.den)))
                    n = mapa_tempo.TramMapa(
                        n.ini, n.fi, n.bpm, n.tipus, n.compassos, agr,
                        getattr(n, "n", None), n.beat_unit)
                    unit = self._unitat_en_canvi_compas(a, n, None)
                    n = mapa_tempo.TramMapa(
                        n.ini, n.fi, n.bpm, n.tipus, n.compassos, agr,
                        getattr(n, "n", None), unit)
            out.append(n)
        return out

    def _on_tempo_mogut(self, idx, vora, t):
        """Mou el bloc sencer o una sola frontera del mapa de tempo.

        Amb `vora="cos"` es mou el bloc interior: conserva durada, BPM, compàs
        i N, i recalcula **els dos veïns**; si un no pot quedar vàlid, no
        s'aplica res. Amb `"ini"`/`"fi"` es mou exactament una frontera i es
        recalcula el costat afectat. La referència és sempre el clip anterior
        al seleccionat (`idx - 1`, o el propi clip si és el primer).
        """
        trams = self._trams_map()
        if not (0 <= idx < len(trams)):
            return
        unitats = {j: self.unitat_de_tram(tr)
                   for j, tr in enumerate(trams)}
        if str(vora).strip().lower() == "cos":
            avisos = []
            try:
                nous = tempo_map.mou_tram_sencer(
                    trams, idx, float(t), self._durada_wav(),
                    beats_qm=None, avisos=avisos,
                    beat_factor=self.beat_factor(), unitats=unitats,
                    permet_ultim_fraccionari=True)
            except ValueError as e:
                self.avis_editor(f"Bloc de tempo: {e}")
                return
            nous = mapa_tempo.reenganxa_metadades(trams, nous)
            try:
                nous = self._reseteja_compas_canviat(trams, nous)
            except ValueError as e:
                self.avis_editor(f"Bloc de tempo: {e}")
                return
            self._undo_marca()
            self.aplica_tempo_trams(nous)
            self._undo_commit()
            for avis in avisos:
                self.avis_editor(f"Bloc: {avis}")
            return
        # Les vores no s'arrosseguen des de la GUI (bloc sencer), però el
        # mètode conserva el camí antic per a crides internes/tests.
        # `idx` és el tram de la vora tocada; la frontera és el SEU inici
        # («ini») o el del SEGÜENT («fi»). `mou_frontera_retempo` rep
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
        avisos = []
        try:
            nous = tempo_map.mou_frontera_retempo(
                trams, p_idx, float(t), self._durada_wav(),
                beats_qm=None, permissiu=True,
                ref_base=self.referencia_tempo_base(idx), avisos=avisos,
                permet_ultim_fraccionari=True,
                beat_factor=self.beat_factor(), unitats=unitats)
        except ValueError as e:
            self.avis_editor(f"Frontera de tempo: {e}")
            return
        nous = mapa_tempo.reenganxa_metadades(trams, nous)
        try:
            nous = self._reseteja_compas_canviat(trams, nous)
        except ValueError as e:
            self.avis_editor(f"Frontera de tempo: {e}")
            return
        self._undo_marca()
        self.aplica_tempo_trams(nous)
        self._undo_commit()
        for avis in avisos:
            self.avis_editor(f"Frontera: {avis}")

    def canvia_compassos_tram(self, idx, delta_compassos=0, factor=None,
                              n_new=None, num=None, den=None):
        """Correcció **mètrica** discreta d'un tram de tempo (§4.C del flux).

        `+1`/`−1` compassos o `×2`/`÷2`: els **segons queden immòbils**, els
        veïns no es toquen, el compàs es conserva i el BPM es recalcula
        (`tempo_map.canvia_compassos_tram`). A l'últim clip es respecta el `N`
        fraccionari. Un sol desfer. Retorna `True` si el mapa ha canviat.
        """
        trams = self._trams_map()
        idx = -1 if idx is None else int(idx)
        if not (0 <= idx < len(trams)):
            return False
        try:
            nous = tempo_map.canvia_compassos_tram(
                trams, idx, delta_compassos=delta_compassos,
                durada=self._durada_wav(), factor=factor, n_new=n_new,
                num=num, den=den, permet_ultim_fraccionari=True)
        except ValueError as e:
            self.avis_editor(f"Compassos: {e}")
            return False
        nous = mapa_tempo.reenganxa_metadades(trams, nous)
        if [tuple(x) for x in nous] == [tuple(x) for x in trams]:
            return False
        # L3: un canvi de compàs no pot deixar la unitat del tram sense
        # encaixar. No s'aplica res (atòmic); es proposa la unitat derivada.
        nou = nous[idx]
        unit_actual = self.unitat_de_tram(nou)
        if not bpm_unit_mod.encaixa_en_compas(
                unit_actual, int(nou.num), int(nou.den)):
            sugg = bpm_unit_mod.unitat_per_defecte(
                int(nou.num), int(nou.den),
                getattr(nou, "agrupacio", "") or "")
            self.avis_editor(
                f"Compassos: el compàs {int(nou.num)}/{int(nou.den)} no "
                f"encaixa amb la unitat {unit_actual}; canvia la unitat a "
                f"{sugg} abans d'aplicar (no s'ha tocat res).")
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
        trams = self._trams_map()
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
        trams = self._trams_map()
        if not trams:
            return False
        for tall in (ini, fi):
            if tall <= tempo_map.TOL or tall >= durada - tempo_map.TOL:
                continue
            try:
                trams = tempo_map.parteix_tram_marcador(
                    trams, tall, durada, permissiu=True,
                    permet_ultim_fraccionari=True)
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
        trams = self._trams_map()
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
        trams = self._trams_map()
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
