#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mapa de TEMPO i COMPÀS variables — el «motor» (stdlib pur).

En un DAW el BPM i el compàs no són constants: hi ha un **mapa** (tempo track /
signature track) amb esdeveniments que valen fins al següent. Aquest mòdul
implementa aquest mapa per a AUTO CHORDS.

- **Unitats musicals**: la referència interna és la **negra** (quarter note); el
  tempo s'expressa en negres per minut (com a tots els DAWs). Un compàs `num/den`
  fa `num·4/den` negres i el seu temps (beat) `4/den` negres.
- **Trossos**: dins de cada tros `[ini, fi)` el tempo i el compàs són constants.
  (Les rampes de tempo lineals són una extensió futura.)
- **Conversions**: `quarters(t)` (negres des de l'origen) i la seua inversa
  `t_de_quarters(q)`, obtingudes per **integració** (no amb un BPM fix).
- **Posició**: `pos(t)` → `(compàs, temps, subdivisió)`, amb el compàs 1 a
  l'`offset` (l'origen de la numeració; abans seu el compte enrere és ≤ 0).

Tot és stdlib pur (immune a AVX/SIGILL al Q9400) i sense dependències d'app.

Vegeu el contracte del refactor a `docs/REFACTOR_INICI_FI.md` i el pla del mapa
a `docs/archive/PLA_TEMPO_COMPAS.md`.
"""
from __future__ import annotations

import math
from collections import namedtuple

# Tolerància temporal (evita falsos positius de coma flotant).
TOL = 1e-9
# Tolerància per a les fronteres de compàs en segons (els CSV guarden 1 µs).
TOL_COMPAS = 1e-4
# BPM de seguretat (regla d'or #8): un valor no positiu no és vàlid i es
# substitueix per aquest (el mateix que fa servir `TempoMap`).
BPM_DEFECTE = 120.0

# Un tros del mapa: temps i compàs constants dins `[ini, fi)`.
#   bpm = negres per minut · num/den = compàs (p. ex. 4/4, 6/8, 12/8)
_TramBase = namedtuple("Tram", ("ini", "fi", "bpm", "num", "den"))


class Tram(_TramBase):
    """Tram de tempo/compàs amb interfície compatible amb `Clip(ini, fi, payload)`."""

    @property
    def payload(self):
        return (self.bpm, self.num, self.den)

    @property
    def lliure(self):
        """True si el tros va **en segons** (sense compàs: `num`/`den` = 0)."""
        return int(self.num) <= 0 or int(self.den) <= 0

    @property
    def num_ef(self):
        """Compàs efectiu per a l'aritmètica (4 si el tros és lliure)."""
        return 4 if self.lliure else int(self.num)

    @property
    def den_ef(self):
        """Denominador efectiu per a l'aritmètica (4 si el tros és lliure)."""
        return 4 if self.lliure else int(self.den)

    @property
    def bpm_ef(self):
        """BPM efectiu (100 si el tros és lliure: referència de notació)."""
        return 100.0 if self.lliure else float(self.bpm)


def _bar_quarters(num, den):
    """Negres que fa un compàs `num/den` (4/4→4, 3/4→3, 6/8→3, 12/8→6).

    Un tram EN SEGONS (`0/0`) no té compàs: 4 (el valor de notació) evita el
    `ZeroDivisionError` i no s'usa per a res (eixe costat no es re-tempa).
    """
    if int(num) <= 0 or int(den) <= 0:
        return 4.0
    return float(num) * 4.0 / float(den)


def _beat_quarters(den):
    """Negres que fa un temps d'un compàs de denominador `den` (4→1, 8→0.5)."""
    return 4.0 / float(den)


class TempoMap:
    """Mapa de tempo i compàs a trossos, amb integració temps↔negres.

    `segments`: `[(ini, fi, bpm, num, den), …]` — trossos contigus i ordenats.
    Si no cobreixen des de 0 s'estén el primer cap a l'esquerra; per a instants
    més enllà de l'últim s'extrapola amb el seu tempo.
    `offset`: instant del **compàs 1** (origen de la numeració).
    """

    # Valor per defecte si no hi ha cap tros (defensa).
    _DEFECTE = Tram(0.0, 0.0, 120.0, 4, 4)

    def __init__(self, segments, offset=0.0):
        trams = []
        for s in segments or ():
            ini, fi, bpm, num, den = (float(s[0]), float(s[1]), float(s[2]),
                                      int(s[3]), int(s[4]))
            if num <= 0 or den <= 0:
                # Tros EN SEGONS: no té compàs. El BPM només és la referència
                # de notació (100 per defecte).
                num = den = 0
                bpm = bpm if bpm > 0 else 100.0
            elif den <= 0:
                den = 4
            if bpm <= 0:
                bpm = 120.0
            trams.append(Tram(ini, fi, bpm, num, den))
        trams.sort(key=lambda x: x.ini)
        if trams and trams[0].ini > TOL:
            s0 = trams[0]
            trams.insert(0, Tram(0.0, s0.ini, s0.bpm, s0.num, s0.den))
        if not trams:
            trams = [self._DEFECTE]
        # Regla #2: en un mapa de tempo/compàs la contigüitat no és una
        # convenció, és **estructura** — el `fi` d'un tram ÉS l'`ini` del
        # següent (i l'últim conserva el seu, que és la fi de la WAV). Es
        # re-deriva ací perquè cap llista amb forats o encavalcaments (CSV
        # editat a mà, client antic) puga produir una graella trencada.
        for _i in range(len(trams) - 1):
            _t = trams[_i]
            trams[_i] = Tram(_t.ini, trams[_i + 1].ini, _t.bpm, _t.num,
                             _t.den)
        self._trams = trams
        self._offset = float(offset or 0.0)

    # ── constructors còmodes ────────────────────────────────────────────────
    @classmethod
    def constant(cls, bpm, num=4, den=4, durada=0.0, offset=0.0):
        """Mapa d'un sol tros (l'app actual: BPM·compàs constant)."""
        return cls([(0.0, float(durada or 0.0), bpm, num, den)], offset=offset)

    @classmethod
    def des_de_maps(cls, tempo, compas, offset=0.0):
        """Combina un mapa de **tempo** `[(ini, fi, bpm)]` i un de **compàs**
        `[(ini, fi, num, den)]` en un sol mapa de trossos alineats (fronteres
        de tots dos)."""
        talls = {0.0}
        for s in tempo or ():
            talls.add(float(s[0]))
            talls.add(float(s[1]))
        for s in compas or ():
            talls.add(float(s[0]))
            talls.add(float(s[1]))
        talls = sorted(talls)
        if len(talls) < 2:
            talls = [0.0, 0.0]
        segs = []
        for a, b in zip(talls, talls[1:]):
            if b - a <= TOL:
                continue
            bpm = cls._valor_a(tempo, (a + b) / 2.0, 120.0)
            num, den = cls._compas_a(compas, (a + b) / 2.0)
            segs.append((a, b, bpm, num, den))
        return cls(segs, offset=offset)

    @staticmethod
    def _valor_a(llista, t, defecte):
        val = defecte
        for s in llista or ():
            if float(s[0]) <= t + TOL:
                val = float(s[2])
        return val

    @staticmethod
    def _compas_a(llista, t):
        num, den = 4, 4
        for s in llista or ():
            if float(s[0]) <= t + TOL:
                num, den = int(s[2]), int(s[3])
        return num, den

    # ── consultes ───────────────────────────────────────────────────────────
    @property
    def offset(self):
        return self._offset

    @property
    def trams(self):
        return tuple(self._trams)

    def durada(self):
        return float(self._trams[-1].fi)

    def tram(self, t):
        """Tros actiu a l'instant `t` (el darrer si és més enllà del mapa)."""
        t = float(t)
        for s in self._trams:
            if s.ini - TOL <= t < s.fi - TOL:
                return s
        return self._trams[-1]

    def bpm(self, t):
        """Negres per minut a `t`."""
        return self.tram(t).bpm

    def signatura(self, t):
        """`(num, den)` del compàs a `t` (efectiu: 4/4 si el tros és lliure)."""
        s = self.tram(t)
        return (s.num_ef, s.den_ef)

    def es_lliure(self, t):
        """True si `t` cau en un tros **en segons** (sense compàs)."""
        return self.tram(t).lliure

    def es_constant(self):
        """True si tots els trossos comparteixen tempo i compàs.

        És el **punt de sortida ràpid**: quan el mapa és constant, tota l'app pot
        fer servir la seua via uniforme de sempre (idèntica) i el mapa només
        serveix per a la persistència.
        """
        if not self._trams:
            return True
        s0 = self._trams[0]
        return all(abs(s.bpm_ef - s0.bpm_ef) < 1e-9
                   and s.num_ef == s0.num_ef and s.den_ef == s0.den_ef
                   and s.lliure == s0.lliure for s in self._trams)

    def durations(self, t):
        """`(compàs_s, temps_s, mitja_negra_s)` de durada a l'instant `t`."""
        s = self.tram(t)
        beat = _beat_quarters(s.den_ef) * 60.0 / s.bpm_ef
        return (_bar_quarters(s.num_ef, s.den_ef) * 60.0 / s.bpm_ef, beat,
                beat / 2.0)

    def grid_lines(self, t0, t1, kind="bar", n=1, frac=None):
        """Temps de les línies de graella de `kind` dins `[t0, t1]` (mapa-aware).

        `kind`: `"bar"` (cada `n` compassos), `"beat"` (temps) o `"sub"`
        (fracció de temps). `frac` permet graelles de treset (1/3, 2/3, 1/6)
        o qualsevol altra subdivisió; si no es passa, 0,5 per a `"sub"` i 1,0
        per a `"beat"`. Les línies són **musicals** (bar/beat), per tant el seu
        espaiat en segons varia amb el mapa.
        """
        t0, t1 = float(t0), float(t1)
        if not any((not tr.lliure) and tr.fi > t0 + TOL and tr.ini < t1 - TOL
                   for tr in self._trams):
            return []                 # tot el rang va en segons: sense graella
        talls = self._talls_de_compas()
        out = []
        if kind == "bar":
            pas = max(1, int(n))
            for k, tall in enumerate(talls):
                if k % pas == 0 and t0 - TOL <= tall[1] <= t1 + TOL:
                    out.append(tall[1])
            # Els trossos en segons no dibuixen res (rubato); la línia que
            # obri el tros lliure sí que es conserva (límit del clip).
            return [t for t in out if not self.es_lliure(t - TOL_COMPAS)]
        if frac is None:
            frac = 0.5 if kind == "sub" else 1.0
        if frac <= 0:
            frac = 1.0
        for k, (q_bar, _t_bar, num, den) in enumerate(talls):
            q_fi = talls[k + 1][0] if k + 1 < len(talls) else None
            pas_q = _beat_quarters(den) * frac
            j = 0
            while j < 100000:
                q = q_bar + j * pas_q
                if q_fi is not None and q >= q_fi - TOL:
                    break        # la frontera és del compàs següent
                t = self.t_de_quarters(q)
                if t > t1 + TOL:
                    return [x for x in out if not self.es_lliure(x - TOL_COMPAS)]
                if t >= t0 - TOL:
                    out.append(t)
                j += 1
        return [x for x in out if not self.es_lliure(x - TOL_COMPAS)]

    # ── conversió temps ↔ negres (integració) ───────────────────────────────
    def _quarters_entre(self, a, b):
        """Negres entre dos instants (signe); fora del mapa s'extrapola."""
        a, b = float(a), float(b)
        if abs(b - a) <= TOL:
            return 0.0
        signe = 1.0 if b >= a else -1.0
        lo, hi = (a, b) if b >= a else (b, a)
        q = 0.0
        # per sota del mapa: el tempo del primer tros
        if lo < self._trams[0].ini - TOL:
            cap = min(hi, self._trams[0].ini)
            if cap > lo:
                q += (cap - lo) * self._trams[0].bpm / 60.0
        for s in self._trams:
            sl = max(s.ini, lo)
            sh = min(s.fi, hi)
            if sh > sl + TOL:
                q += (sh - sl) * s.bpm / 60.0
        # per sobre del mapa: el tempo de l'últim tros
        ult = self._trams[-1]
        if hi > ult.fi + TOL:
            ini = max(lo, ult.fi)
            q += (hi - ini) * ult.bpm / 60.0
        return signe * q

    def quarters(self, t):
        """Negres des de l'origen (compàs 1) fins a `t` (signe; pot ser < 0)."""
        return self._quarters_entre(self._offset, t)

    def t_de_quarters(self, q):
        """Instant en què s'assoleixen `q` negres des de l'origen (inversa)."""
        q = float(q)
        if abs(q) <= TOL:
            return self._offset
        if q > 0:
            i = self._index(self._offset)
            t = self._offset
            restant = q
            while i < len(self._trams):
                s = self._trams[i]
                tram_q = (s.fi - t) * s.bpm / 60.0
                if restant <= tram_q + TOL or i == len(self._trams) - 1:
                    return t + restant * 60.0 / s.bpm
                restant -= tram_q
                t = s.fi
                i += 1
            return t
        # q < 0: cap enrere
        i = self._index(self._offset)
        t = self._offset
        restant = -q
        while i >= 0:
            s = self._trams[i]
            tram_q = (t - s.ini) * s.bpm / 60.0
            if restant <= tram_q + TOL or i == 0:
                return t - restant * 60.0 / s.bpm
            restant -= tram_q
            t = s.ini
            i -= 1
        return t

    def _index(self, t):
        for i, s in enumerate(self._trams):
            if s.ini - TOL <= t < s.fi - TOL:
                return i
        return len(self._trams) - 1

    # ── posició compàs·temps·subdivisió ─────────────────────────────────────
    def _canvi_compas_entre(self, t0, t1, sig):
        """Primer canvi de **compàs** (signatura) estrictament dins (t0, t1).

        Els canvis de TEMPO amb la mateixa signatura NO compten: el compàs
        continua i només canvia la seua durada en segons. Retorna
        `(t, (num, den))` o `None`.
        """
        for s in self._trams:
            if s.ini <= t0 + TOL:
                continue
            if s.ini >= t1 - TOL:
                break
            if s.lliure or (s.num_ef, s.den_ef) != sig:
                return float(s.ini), ((4, 4) if s.lliure
                                      else (s.num_ef, s.den_ef))
        return None

    def _talls_de_compas(self):
        """`[(q_ini, t_ini, num, den), …]` — inici de cada compàs des de l'origen.

        Els **canvis de compàs** (signatura) arrenquen un compàs nou, encara
        que caiguen a mig compàs (com als DAWs). Els **canvis de tempo** amb la
        mateixa signatura **NO** tallen el compàs: es continua el compàs actual
        i la resta es mesura amb el BPM nou. Els inici de compàs es calculen en
        l'espai de negres i es converteixen a segons amb `t_de_quarters`, així
        la integració del tempo variable és la correcta.
        """
        offset = float(self._offset)
        durada = float(self._trams[-1].fi)
        s = self.tram(offset)
        sig = (s.num_ef, s.den_ef)
        talls = [(0.0, offset, sig[0], sig[1])]
        q_bar, t_bar = 0.0, offset
        limit = 100000                     # salvavides
        while t_bar < durada - TOL and limit > 0:
            limit -= 1
            bq = _bar_quarters(sig[0], sig[1])
            if bq <= TOL:
                break
            q_end = q_bar + bq
            t_end = self.t_de_quarters(q_end)
            if t_end <= t_bar + TOL:
                break
            canvi = self._canvi_compas_entre(t_bar, t_end, sig)
            if canvi is not None:
                # Canvi de compàs a mig compàs: es tanca el compàs ahí i se'n
                # comença un altre amb la signatura nova.
                t_nou, sig_nou = canvi
                q_nou = self.quarters(t_nou)
                if q_nou <= q_bar + TOL:
                    break
                talls.append((q_nou, t_nou, sig_nou[0], sig_nou[1]))
                q_bar, t_bar, sig = q_nou, t_nou, sig_nou
                continue
            if t_end > durada + TOL:
                break
            # El compàs acaba dins del mapa. La signatura del compàs que
            # COMENÇA ahí és la del tram on cau `t_end` (pot haver-hi un canvi
            # de compàs exactament a la frontera).
            s_next = self.tram(t_end)
            sig_next = (s_next.num_ef, s_next.den_ef)
            talls.append((q_end, t_end, sig_next[0], sig_next[1]))
            q_bar, t_bar = q_end, t_end
            sig = sig_next
            if t_end >= durada - TOL:
                break
        return talls

    def pos(self, t):
        """`(compàs, temps, subdivisió)` d'un instant.

        El **compàs 1** és a l'offset; abans seu la numeració és ≤ 0 (compte
        enrere). `subdivisió` és la **fusa** dins del temps (1..8).
        """
        t = float(t)
        # La posició es mostra a resolució de 1/32: arrodonim la negra a la
        # fusa més propera perquè `pos_compas` i el mapa donen la mateixa
        # etiqueta també a les vores (p. ex. 9,5 s a 101 BPM).
        q = round(self.quarters(t) * 8) / 8.0
        talls = self._talls_de_compas()
        if q >= -TOL:
            idx = 0
            for j in range(len(talls) - 1, -1, -1):
                if talls[j][0] <= q + TOL:
                    idx = j
                    break
            q_ini, _t_ini, num, den = talls[idx]
            compas = idx + 1
        else:
            # compte enrere: el primer tros cap enrere
            s = self.tram(self._offset)
            bq = _bar_quarters(s.num_ef, s.den_ef)
            compas = int((q + TOL) // bq) + 1        # ≤ 0
            q_ini = (compas - 1) * bq
            num, den = s.num_ef, s.den_ef
        beat_q = _beat_quarters(den)
        dins = q - q_ini
        if dins < -TOL:
            dins = 0.0
        b = int(dins // beat_q + TOL)
        if b >= num:
            b = num - 1
        frac = (dins - b * beat_q) / beat_q
        sub = 1 + int(frac * 8 + TOL)
        return (compas, max(1, min(num, b + 1)), min(8, sub))

    def label(self, t):
        """Etiqueta `compàs.temps.subdivisió` (o `—` si va en segons)."""
        if self.es_lliure(t):
            return "—"
        c, b, s = self.pos(t)
        return "%d.%d.%d" % (c, b, s)

    def t_de_pos(self, compas, temps=1):
        """Instant del compàs/temps indicat (inversa parcial de `pos`).

        Usa la llista REAL de compassos (`_talls_de_compas`), no una suposició
        de compàs constant: amb canvis de tempo/compàs, cada compàs pot tindre
        una durada distinta.
        """
        compas, temps = int(compas), int(temps)
        talls = self._talls_de_compas()
        if not talls:
            return self._offset
        if compas >= 1:
            idx = compas - 1
            if idx < len(talls):
                q_bar, _t, num, den = talls[idx]
            else:
                q_bar, _t, num, den = talls[-1]
                q_bar += (compas - len(talls)) * _bar_quarters(num, den)
        else:
            # Compte enrere (abans del compàs 1): signatura de l'origen.
            q_bar, _t, num, den = talls[0]
            q_bar += (compas - 1) * _bar_quarters(num, den)
        return self.t_de_quarters(q_bar + (temps - 1) * _beat_quarters(den))

    # ── snap a la graella ───────────────────────────────────────────────────
    def compassos(self):
        """`[(q_ini, t_ini, num, den), …]` — inici de cada compàs del mapa."""
        return self._talls_de_compas()

    def compassos_beats(self):
        """`[(compàs, inici_en_negres, num, den), …]` — per a la notació.

        El «beat» és la **negra** (la unitat del MusicXML); cada compàs fa
        `num·4/den` negres. El compàs 1 arrenca a la negra 0.
        """
        talls = self._talls_de_compas()
        if not talls:
            return []
        q0 = talls[0][0]
        return [(k + 1, q - q0, num, den)
                for k, (q, _t, num, den) in enumerate(talls)]

    def snap(self, t, divisio=("beat", 1.0)):
        """Encaixa `t` a la subdivisió més propera de la graella del mapa.

        `divisio`: `("bars", n)` = les línies de compàs cada `n` compassos, o
        `("beat", frac)` = dins del compàs, `frac` del temps (1.0 = el temps,
        0.5 = la corxera…). La graella s'ancora a les **línies de compàs
        reals** del mapa (no a múltiples uniformes), així funciona amb canvis de
        compàs i de tempo.
        """
        t = float(t)
        talls = self._talls_de_compas()
        # Compàs que conté `t`.
        j = 0
        for k in range(len(talls) - 1, -1, -1):
            if talls[k][1] <= t + TOL:
                j = k
                break
        q_bar, _t_bar, num, den = talls[j]
        if divisio and divisio[0] == "bars":
            n = max(1, int(divisio[1]))
            punts = [talls[k][1] for k in range(len(talls)) if k % n == 0]
            if not punts:
                return t
            return min(punts, key=lambda tt: (abs(tt - t), tt))
        frac = float(divisio[1]) if divisio else 1.0
        if frac <= 0:
            frac = 1.0
        pas_q = _beat_quarters(den) * frac
        q = self.quarters(t)
        k = round((q - q_bar) / pas_q)
        return self.t_de_quarters(max(0.0, q_bar + k * pas_q))


# --- edició del mapa (utilitats pures per a la GUI) ------------------------
def neteja_trams(trams, durada):
    """Ordena, fa contigus i **repara** els trossos; retorna `(trams, avisos)`.

    Cada tros és `(ini, fi, bpm, num, den)`; el `fi` es **re-deriva** de l'inici
    del següent (o de `durada` per a l'últim): la frontera és única. No muta
    l'entrada. Sense `durada` (> 0) no es pot imposar la cobertura (regla #4) i
    es **conserva** el `fi` de l'últim tram: inventar-hi 0 destruïa el mapa
    d'un projecte amb el WAV absent o encara no carregat.

    **Regla #1** (`docs/REGLES_DE_LA_APP.md`): l'estat invàlid no pot existir;
    si una entrada externa (CSV a mà, projecte vell, estat vell del desfer) n'hi
    porta un, es **repara cap al valor vàlid i s'avisa** — la llista `avisos`
    és el que la UI ha de mostrar (mai en silenci). Casos:

    - inici negatiu → 0;
    - inici repetit → es descarta el segon (un sol tram pot començar en cada
      instant, per construcció);
    - inici fora del tema (≥ durada) → es descarta;
    - fi abans de l'inici → es recalcula.

    La **capçalera** (forat a l'inici) no avisa: és com es construïx un mapa a
    partir d'un tros solt (`elimina_tall`, anàlisi guiat).
    """
    durada = float(durada or 0.0)
    net, avisos = [], []
    for t in sorted(trams or (), key=lambda x: float(x[0])):
        ini = float(t[0])
        # Regla d'or #8 (temps vàlids): cap inici negatiu ni cap valor
        # impossible: es porta al valor vàlid en comptes de propagar-lo.
        if ini < -TOL:
            avisos.append("Un tram començava abans de 0 s: s'ha posat a 0.")
        ini = max(0.0, ini)
        if durada > 0 and ini >= durada - TOL:
            avisos.append("Un tram començava fora del tema: s'ha descartat.")
            continue
        # «Mateix instant» vol dir **el mateix** (o el soroll de coma flotant,
        # ~1e-16), no «dins del mateix microsegon»: arredonir a 6 decimals
        # descartava un tram sencer quan dos inicis queien a 1e-9 s (el mapa es
        # quedava amb el primer i el segon desapareixia — pèrdua silenciosa).
        if net and ini - float(net[-1][0]) <= 1e-12:
            avisos.append("Dos trams començaven al mateix instant: "
                          "se n'ha fusionat un (només n'hi pot haver un).")
            continue
        try:
            fi0 = float(t[1])
        except (TypeError, ValueError):
            fi0 = ini
        if fi0 < ini - TOL:
            avisos.append("Un tram tenia el fi abans de l'inici: "
                          "s'ha recalculat.")
        bpm = float(t[2])
        num, den = int(t[3]), int(t[4])
        if num <= 0 or den <= 0:
            # Tros EN SEGONS: es conserva (0/0); el BPM és la referència de
            # notació (100 per defecte).
            net.append((ini, fi0, bpm if bpm > 0 else 100.0, 0, 0))
        else:
            net.append((ini, fi0, bpm if bpm > 0 else BPM_DEFECTE, num, den))
    if not net:
        return [], avisos
    out = []
    for i, t in enumerate(net):
        if i + 1 < len(net):
            fi = net[i + 1][0]
        elif durada > TOL:
            fi = durada                 # regla #4: l'últim acaba a la WAV
        else:
            fi = float(t[1]) if float(t[1]) > float(t[0]) + TOL else t[0]
        out.append((t[0], fi, t[2], t[3], t[4]))
    if out[0][0] > TOL:
        out.insert(0, (0.0, out[0][0], out[0][2], out[0][3], out[0][4]))
    return out, avisos


def normalitza_trams(trams, durada):
    """`neteja_trams` sense els avisos (compatibilitat i camins interns)."""
    return neteja_trams(trams, durada)[0]


# --- contracte de COMPASSOS ENTERS (docs/REGLES_DE_LA_APP.md §13.4) ---------
def fusiona_trams_iguals(trams, durada=0.0):
    """Fusiona trams adjacents amb el **mateix BPM i compàs**.

    No representen cap canvi musical; els projectes vells i les anàlisis en
    solen deixar de duplicats (p. ex. `65.75` repetit). Es fa sobretot en
    **carregar**, perquè una partició manual de dos trams iguals no es desfa
    automàticament mentre s'edita. Retorna trams normalitzats.
    """
    base = normalitza_trams(trams, durada)
    out = []
    for t in base:
        if out:
            p = out[-1]
            if (abs(float(p[2]) - float(t[2])) <= TOL
                    and int(p[3]) == int(t[3])
                    and int(p[4]) == int(t[4])):
                continue
        out.append(t)
    return normalitza_trams(out, durada)


def durada_compas(bpm, num, den):
    """Segons que dura un compàs `num/den` a `bpm`."""
    return _bar_quarters(num, den) * 60.0 / float(bpm)


def _bar_lines_tram(tram, offset=0.0):
    """Línies de compàs d'un tram, en segons (inclou les dels extrems)."""
    ini, fi, bpm, num, den = (float(tram[0]), float(tram[1]), float(tram[2]),
                              int(tram[3]), int(tram[4]))
    b = durada_compas(bpm, num, den)
    if b <= TOL:
        return []
    # El primer tram pot tindre un tros de compte enrere abans del compàs 1
    # (offset): les seues línies Parteixen de l'offset, no de 0.
    base = float(offset) if abs(ini) <= TOL and offset > TOL else ini
    k0 = int(math.floor((ini - base) / b)) - 2
    k1 = int(math.ceil((fi - base) / b)) + 2
    return [base + k * b for k in range(k0, k1 + 1)]


def valida_i_normalitza_compassos(trams, durada, offset=0.0):
    """Valida el contracte de compassos enters i retorna el mapa normalitzat.

    - Les fronteres interiors han de caure en una **línia de compàs**.
    - Els trams interiors han de tindre un **nombre enter de compassos** ≥1.
    - El primer inici i l'últim final poden ser parcials (excepcions).
    - El mapa ha de ser contigu i cobrir `[0, durada]`.

    Aixeca `ValueError` amb un missatge d'usuari si no es compleix.
    """
    durada = float(durada or 0.0)
    for t in trams or ():
        if durada > 0 and float(t[0]) >= durada - TOL:
            raise ValueError("Hi ha un tram que comença fora de la WAV")
    nous = normalitza_trams(trams, durada)
    if not nous:
        raise ValueError("El mapa de tempo/compàs és buit")
    if len(nous) == 1:
        return nous

    mapa = TempoMap(nous, offset=offset)
    bar_times = [float(t) for _q, t, _n, _d in mapa.compassos()]

    def _es_bar(t):
        return any(abs(float(t) - b) <= TOL_COMPAS for b in bar_times)

    # Totes les fronteres interiors (inclou l'inici de l'últim tram). El
    # primer inici (0) i l'últim final (durada) són les excepcions.
    def _lliure(tram):
        return int(tram[3]) <= 0 or int(tram[4]) <= 0

    for i in range(1, len(nous)):
        if _lliure(nous[i]) or _lliure(nous[i - 1]):
            continue                  # frontera d'un tros en segons: lliure
        t = float(nous[i][0])
        if not _es_bar(t):
            raise ValueError(
                f"La frontera {t:.6f}s no cau en una línia de compàs")
    # El primer tram: el tros posterior a la primera línia de compàs (l'offset,
    # si cau dins del tram) ha de ser un nombre enter de compassos. El tros
    # anterior a l'offset és l'única part parcial permesa al començament.
    ini0, fi0, bpm0, num0, den0 = nous[0]
    if _lliure(nous[0]):
        b0 = 0.0
    else:
        b0 = durada_compas(bpm0, num0, den0)
    if not _lliure(nous[0]) and b0 <= TOL:
        raise ValueError("El primer tram té un compàs de durada nul·la")
    base0 = float(offset) if float(offset) > float(ini0) + TOL else float(ini0)
    bars0 = 0.0 if b0 <= TOL else (float(fi0) - base0) / b0
    # Si el segon tram va EN SEGONS, el primer pot acabar a mig compàs (la
    # frontera és lliure, com al pre-roll).
    if _lliure(nous[0]) or _lliure(nous[1]):
        pass
    elif base0 <= float(ini0) + TOL and bars0 < 1.0 - 1e-5:
        raise ValueError(
            "El primer tram ha d'acabar com a mínim al primer compàs sencer")
    # Tolerància en TEMPS (no en compassos): l'offset es desa amb 3 decimals i
    # la frontera pot caure a dècimes de mil·lisegon (abans 1e-5 compassos = 20
    # µs a 120 BPM bloquejaven qualsevol reparació).
    if not _lliure(nous[0]) and not _lliure(nous[1]) and (
            bars0 < -1e-5 or abs(bars0 - round(bars0)) * b0 > TOL_COMPAS):
        raise ValueError(
            "El primer tram no acaba en una línia de compàs "
            f"({bars0:.3f} compassos des del compàs 1)")
    # Els trams interiors (ni el primer ni l'últim) han de ser enters.
    for i in range(1, len(nous) - 1):
        ini, fi, bpm, num, den = nous[i]
        if (_lliure(nous[i]) or _lliure(nous[i - 1])
                or _lliure(nous[i + 1])):
            continue                  # toca un tros en segons: sense contracte
        b = durada_compas(bpm, num, den)
        if b <= TOL:
            raise ValueError(f"El tram {i + 1} té un compàs de durada nul·la")
        bars = (float(fi) - float(ini)) / b
        if bars < 1.0 - 1e-5 or abs(bars - round(bars)) > 1e-5:
            raise ValueError(
                f"El tram {i + 1} no conté un nombre enter de compassos "
                f"({bars:.3f}); ha de ser 1, 2, 3…")
    return nous


# --- Anàlisi guiat (docs/ANALISI_GUIAT.md) ----------------------------------
def parteix_trams_a(trams, t, durada):
    """Talla el mapa a la posició `t` (mateix bpm/compàs als dos trossos).

    L'«Anàlisi guiat» l'usa per al tall LLIURE del carril de tempo al punt del
    cursor: encara no hi ha cap contracte de compassos enters en joc (la zona
    anterior al compàs 1 és el compte enrere). Retorna trams normalitzats; si
    `t` cau fora del tema o damunt d'una frontera existent, no canvia res.
    """
    durada = float(durada or 0.0)
    t = float(t)
    net = normalitza_trams(trams, durada)
    if durada <= 0 or t <= TOL or t >= durada - TOL:
        return net
    out = []
    for s in net:
        if s[0] + TOL < t < s[1] - TOL:
            # No crear micro-trams: si el tall cau a menys de NETEJA_TRAM_S
            # d'una frontera, s'hi apunta. Un tram de 4 ms (📍 a 0,202 s amb
            # una frontera a 0,2066 s) va fer explotar la reparació del mapa
            # fins a 5.978 BPM / 5.972 compassos (22-10-2026).
            if (t - s[0] < NETEJA_TRAM_S) or (s[1] - t < NETEJA_TRAM_S):
                out.append(s)
                continue
            out.append((s[0], t, s[2], s[3], s[4]))
            out.append((t, s[1], s[2], s[3], s[4]))
        else:
            out.append(s)
    return normalitza_trams(out, durada)


def trams_finestra_guia(trams, t_inici, bpm, num, den, durada, beats=16,
                       n_compassos=None):
    """Nou mapa després de CONFIRMAR una finestra de l'«Anàlisi guiat».

    `t_inici` = inici del tram de cua (pendent de detectar). El tram
    confirmat acaba a la primera quantitat **entera de compassos** que més
    s'acosta a `beats` temps del nou BPM (a 4/4, 16 temps = 4 compassos);
    amb `n_compassos` s'imposa el nombre de compassos directament (és el que
    fa servir el guiat: 4 compassos **de la mètrica vigent**, no 16 temps —
    en 3/4, `beats=16` donava 5 compassos);
    la cua que queda després va amb el BPM confirmat (es re-detectarà a la
    finestra següent, o es queda com a últim tram si ja som al final).

    Retorna `(nous, t_seguent, m)` amb `nous` la llista de trams nova
    (normalitzada), `t_seguent` la frontera confirmada i `m` el nombre de
    compassos del tram confirmat. No muta l'entrada. Retorna `None` si no
    hi ha res a detectar (`t_inici` al final de la WAV o BPM invàlid).
    """
    durada = float(durada or 0.0)
    t = float(t_inici)
    bpm = float(bpm)
    num, den = int(num), int(den)
    if bpm <= 0 or durada <= 0 or t >= durada - TOL:
        return None
    b_len = durada_compas(bpm, num, den)
    if b_len <= TOL:
        return None
    # el càlcul assumeix que `t` és una frontera; si no ho fos, la creem
    base = parteix_trams_a(trams, t, durada)
    if not base:
        base = [(0.0, durada, bpm, num, den)]
    abans = [s for s in base if float(s[0]) < t - TOL]
    if n_compassos is None:
        m = max(1, int(round((float(beats) * 60.0 / bpm) / b_len)))
    else:
        m = max(1, int(n_compassos))
    t_seg = t + m * b_len
    if t_seg >= durada - TOL:
        nous = abans + [(t, durada, bpm, num, den)]
    else:
        nous = (abans + [(t, t_seg, bpm, num, den),
                         (t_seg, durada, bpm, num, den)])
    return (normalitza_trams(nous, durada), t_seg, m)


def _ripple_des_de(trams, idx, nou_fi, durada):
    """Mou la fi del tram `idx` i arrossega les fronteres següents.

    Els trams posteriors conserven la seua durada (i, per tant, els seus
    compassos); l'últim acabarà a `durada` (excepció).
    """
    out = [list(t) for t in trams]
    delta = float(nou_fi) - float(out[idx][1])
    out[idx][1] = float(nou_fi)
    for j in range(idx + 1, len(out)):
        out[j][0] = float(out[j][0]) + delta
        out[j][1] = float(out[j][1]) + delta
    return [tuple(t) for t in out]


def snap_frontera_compas(trams, p_idx, t, durada, offset=0.0, direccio=None):
    """Imanta la FI del tram `p_idx` a la línia de compàs més pròxima.

    `direccio` ("dreta"/"esquerra") limita les candidates al sentit del gest:
    així arrossegar una vora mitja compàs cap a la dreta **avança** una línia de
    compàs en lloc de tornar a la mateixa (que es veia com «no es pot moure»).

    Retorna `(t_final, mapa_normalitzat)`. Arrossega les fronteres següents
    perquè els trams interiors continuen amb compassos enters. Rebutja si no
    hi ha cap línia vàlida.
    """
    durada = float(durada or 0.0)
    nous = normalitza_trams(trams, durada)
    p_idx = int(p_idx)
    if not (0 <= p_idx < len(nous) - 1):
        raise ValueError("No hi ha cap frontera posterior per a moure")
    tram = nous[p_idx]
    ini, fi, bpm, num, den = tram
    b = durada_compas(bpm, num, den)
    if b <= TOL:
        raise ValueError("El compàs té una durada nul·la")
    base = float(offset) if (p_idx == 0 and float(offset) > float(ini) + TOL) \
        else float(ini)
    minim = base + (b if (p_idx > 0 or base <= float(ini) + TOL) else 0.0)
    cands = [c for c in _bar_lines_tram(tram, offset)
             if minim - TOL_COMPAS <= c <= durada + TOL_COMPAS]
    d = str(direccio or "").lower()
    if d == "dreta":
        cap = [c for c in cands if c > float(fi) + TOL_COMPAS]
    elif d == "esquerra":
        cap = [c for c in cands if c < float(fi) - TOL_COMPAS]
    else:
        cap = []
    if cap:
        cands = cap
    for c in sorted(cands, key=lambda x: abs(x - float(t))):
        out = _ripple_des_de(nous, p_idx, c, durada)
        try:
            return float(c), valida_i_normalitza_compassos(out, durada, offset)
        except ValueError:
            continue
    raise ValueError("No hi ha cap línia de compàs vàlida a prop")


# --- Re-tempo: el RATOLÍ mana sobre el temps (REGLES_DE_LA_APP.md §13.5) -----
#: Distància mínima (s) entre una frontera i la seua veïna (límit de seguretat).
FRONTERA_MIN_S = 0.5
#: Banda de BPM «raonable» per a un arrossegament (fora d'ací s'avisa i no es fa).
BPM_EDIT_MIN = 30.0
BPM_EDIT_MAX = 350.0


def _enter_mes_proper(x):
    """Enter més pròxim (half-up; `round` fa *banker's* i desconcerta)."""
    return int(math.floor(float(x) + 0.5))


def _base_tram(tram, idx, offset=0.0):
    """Instant on comença a comptar el compàs 1 **dins** del tram.

    Només el PRIMER tram pot tindre una zona de pre-música (`0 → offset`): la
    seua graella compta des de l'offset. La resta, des del propi inici.
    """
    ini = float(tram[0])
    off = float(offset or 0.0)
    return off if (int(idx) == 0 and off > ini + TOL) else ini


def _es_lliure_tram(tram):
    """True si el tram va **en segons** (`num`/`den` = 0)."""
    return int(tram[3]) <= 0 or int(tram[4]) <= 0


def _compassos_del_tram(tram, idx, offset=0.0):
    """Compasos (pot ser fraccionari) que conté el tram segons durada i BPM."""
    fi, bpm, num, den = (float(tram[1]), float(tram[2]),
                         int(tram[3]), int(tram[4]))
    b = durada_compas(bpm, num, den)
    if b <= TOL:
        raise ValueError("El compàs té una durada nul·la")
    return (float(fi) - _base_tram(tram, idx, offset)) / b


def _valida_bpm_edicio(bpm, costat):
    """Comprova la banda de BPM d'un re-tempo (regla §5 del document)."""
    b = float(bpm)
    if not (BPM_EDIT_MIN - TOL <= b <= BPM_EDIT_MAX + TOL):
        raise ValueError(
            f"El tram {costat} quedaria a {b:.1f} BPM, fora del rang "
            f"{BPM_EDIT_MIN:g}–{BPM_EDIT_MAX:g}")
    return b


def _mapa_valida_sense_moure(out, durada, offset):
    """Valida el mapa **sense moure cap frontera**.

    Les operacions de l'usuari (`+`, re-tempo pel ratolí, «Detecta» d'un tram,
    «Ajusta BPMs pels marcadors») fixen elles mateixes les fronteres: el lloc on
    cau el marcador o la nansa és la veritat. Per tant, si el mapa no valida
    perquè un ALTRE tram arrossega una desviació vella, no es pot cridar
    `repara_fronteres` (mouria la frontera que l'operador acaba de posar). Es
    retorna el mapa normalitzat (permissiu): el gest no es bloqueja i la
    reparació es farà quan l'operador la veja.
    """
    try:
        return valida_i_normalitza_compassos(out, durada, offset)
    except ValueError:
        return normalitza_trams(out, durada)


def canvia_bpm_local(trams, idx, bpm, durada, offset=0.0, num=None, den=None):
    """Canvia el BPM/compàs d'un tram **conservant els compassos** (local).

    És el camí del diàleg del tram, dels camps de la barra i del TAP
    (`docs/REGLES_DE_LA_APP.md` §13.5): el tram conserva el seu nombre enter de
    compassos `N`, la seua durada passa a ``Δt = N · bq · 60 / BPM`` i el
    **veí de la dreta** conserva els seus compassos i el seu final, recalculant
    el BPM. La resta del mapa **no es mou** (sense *ripple*).

    - **Canvi només de compàs** (`4/4` → `3/4`…): es conserva la **durada** i
      es recompta `N` (el BPM s'ajusta el mínim perquè siga enter). Canviar la
      xifra no ha de fer el tram més llarg: les fronteres són la veritat.
    - **Últim tram** (o mapa d'un sol tram): la fi de la WAV mana → conserva
      `ini`/`fi` i pot canviar `N` (excepció §5).
    - **Primer tram**: la zona de pre-música (`0 → offset`) es respecta; si el
      tram acaba a **mig compàs** (pre-roll o marcador fora de graella) es
      conserva eixa fracció i el tram sí que canvia de mida. Si tot ell és
      pre-música, només canvia el BPM (la durada no depén del compàs).
    - Validació **permissiva** (`_mapa_valida_sense_moure`): una frontera vella
      fora de graella no bloqueja l'edició del tram (igual que al drag).
    - Si el **veí afectat és l'últim tram**, conserva el seu BPM i la seua fi
      (la WAV mana) i absorbeix el desplaçament en el nombre de compassos
      (excepció §5); si és interior, conserva els compassos i recalcula el BPM.

    Retorna el mapa normalitzat i validat. Aixeca `ValueError` amb un missatge
    d'usuari si el canvi no cap (massa a prop del veí, BPM fora de rang…).
    """
    durada = float(durada or 0.0)
    nous = normalitza_trams(trams, durada)
    i = int(idx)
    if not (0 <= i < len(nous)):
        raise ValueError("El tram de tempo no existeix")
    ini, fi, bpm0, num0, den0 = nous[i]
    bpm = float(bpm)
    num = int(num if num is not None else num0)
    den = int(den if den is not None else den0)
    lliure_vel = int(num0) <= 0 or int(den0) <= 0
    if num <= 0 or den <= 0:
        # Passa a **EN SEGONS**: conserva les fronteres i no hi ha contracte
        # de compàs. El BPM queda com a referència de notació (100 si no hi
        # ha cap valor).
        if bpm <= 0:
            bpm = 100.0
        out = list(nous)
        out[i] = (float(ini), float(fi), float(bpm), 0, 0)
        return _mapa_valida_sense_moure(out, durada, offset)
    if bpm <= 0:
        raise ValueError("BPM o compàs no vàlid")
    b_old = 0.0 if lliure_vel else durada_compas(bpm0, num0, den0)
    b_new = durada_compas(bpm, num, den)
    if (not lliure_vel and b_old <= TOL) or b_new <= TOL:
        raise ValueError("El compàs té una durada nul·la")

    if i == len(nous) - 1:
        # Últim tram: la fi de la WAV no es mou; pot canviar el nombre de
        # compassos (excepció §5). Validació **permissiva**, com el drag: una
        # frontera vella fora de graella no ha de bloquejar l'edició d'este
        # tram (`_mapa_valida_sense_moure`).
        out = list(nous)
        out[i] = (float(ini), float(fi), bpm, num, den)
        return _mapa_valida_sense_moure(out, durada, offset)

    if (num, den) != (int(num0), int(den0)):
        # Només canvia el COMPÀS (p. ex. 1/4 → 4/4): és el mateix tros de
        # música recontat. Mana la DURADA (les fronteres no es mouen) i el
        # nombre de compassos passa a ser el que hi cap; el BPM s'ajusta el
        # mínim perquè N siga enter. Abans es conservava N i el tram es feia
        # 4× més llarg → «el tram següent quedaria massa curt» (Jamiroquai).
        base = _base_tram(nous[i], i, offset)
        dt = float(fi) - base
        out = list(nous)
        if dt > TOL:
            bq = _bar_quarters(num, den)
            n = max(1, _enter_mes_proper(dt * float(bpm) / (bq * 60.0)))
            bpm = _valida_bpm_edicio(n * bq * 60.0 / dt, "tram")
        out[i] = (float(ini), float(fi), float(bpm), num, den)
        return _mapa_valida_sense_moure(out, durada, offset)

    base = _base_tram(nous[i], i, offset)
    n_frac = _compassos_del_tram(nous[i], i, offset)
    if n_frac <= TOL and i == 0:
        # Tot el primer tram és pre-música (el compàs 1 cau a la seua fi o
        # més enllà): la seua durada no depén del compàs. Canvia el BPM i prou.
        out = list(nous)
        out[i] = (float(ini), float(fi), bpm, num, den)
        return _mapa_valida_sense_moure(out, durada, offset)
    n = _enter_mes_proper(n_frac)
    if n < 1:
        if i == 0 and n_frac > TOL:
            # El primer tram pot acabar a MIG compàs (pre-roll o marcador
            # fora de graella, §5): conservem eixa fracció en compte
            # d'inflar-lo a un compàs sencer (que el faria saltar).
            n = float(n_frac)
        else:
            raise ValueError("El tram ha de tindre almenys un compàs")
    nou_fi = base + n * b_new
    vei = nous[i + 1]
    if nou_fi <= float(ini) + TOL:
        raise ValueError("El canvi deixaria el tram sense durada")
    limit = float(vei[1]) - FRONTERA_MIN_S
    if nou_fi >= limit:
        # El veí té el final fix: el tram editat no pot créixer més enllà.
        # Li donem el BPM extrem que encara hi cap (el més baix possible,
        # perquè baixar el BPM allarga el tram).
        bq = _bar_quarters(num, den)
        marge = limit - base
        extra = ""
        if marge > TOL and bq > 0:
            bpm_min = n * bq * 60.0 / marge
            extra = (f" El BPM més baix que hi cap és {bpm_min:.1f} "
                     f"(el tram següent quedaria a {FRONTERA_MIN_S:g} s).")
        raise ValueError(
            "El canvi no cap: el tram següent quedaria massa curt." + extra)

    out = list(nous)
    out[i] = (float(ini), float(nou_fi), bpm, num, den)
    interior = (i + 1) < (len(nous) - 1)
    if interior and _es_lliure_tram(vei):
        # El veí va en segons: no té compassos; només el desplacem.
        out[i + 1] = (float(nou_fi), float(vei[1]), float(vei[2]),
                      int(vei[3]), int(vei[4]))
        interior = False
    if interior:
        n_v = _enter_mes_proper(_compassos_del_tram(vei, i + 1, offset))
        if n_v < 1:
            raise ValueError("El tram següent ha de tindre almenys un compàs")
        bq_v = _bar_quarters(int(vei[3]), int(vei[4]))
        dt_v = float(vei[1]) - nou_fi
        bpm_v = _valida_bpm_edicio(n_v * bq_v * 60.0 / dt_v, "següent")
        out[i + 1] = (float(nou_fi), float(vei[1]), bpm_v, int(vei[3]),
                      int(vei[4]))
    else:
        # L'últim tram conserva el tempo i la fi (la WAV mana): absorbeix el
        # desplaçament en els compassos, que poden ser fraccionaris (§5).
        out[i + 1] = (float(nou_fi), float(vei[1]), float(vei[2]),
                      int(vei[3]), int(vei[4]))
    # El tram afectat ha de quedar amb compassos enters per construcció; ho
    # comprovem abans de validar la resta (un mapa vell pot arrossegar
    # fraccions i no ha de bloquejar este gest).
    bars = _compassos_del_tram(out[i], i, offset)
    if abs(n - round(n)) < 1e-6 and abs(bars - _enter_mes_proper(bars)) > 1e-6:
        raise ValueError(
            f"El tram no ha quedat amb compassos enters ({bars:.3f})")
    if interior:
        bars_v = _compassos_del_tram(out[i + 1], i + 1, offset)
        if abs(bars_v - _enter_mes_proper(bars_v)) > 1e-6:
            raise ValueError(
                f"El tram següent no ha quedat amb compassos enters "
                f"({bars_v:.3f})")
    return _mapa_valida_sense_moure(out, durada, offset)


def parteix_tram_marcador(trams, t, durada, offset=0.0, bpm_ref=None):
    """Parteix el mapa a `t` fent nàixer el tram esquerre **ja vàlid**.

    Un marcador és un **inici de compàs**: el tram que es tanca (`[ini, t]`)
    ha de tindre un nombre enter de compassos des del seu inici musical
    (`offset` si és el primer tram) i el BPM que els clava exactament:

    ``BPM = N · bar_quarters · 60 / (t − base)``

    amb ``N = max(1, round((t − base) · BPM_ref / (bar_quarters · 60)))``.
    El marcador obri el tram nou cap endavant: la resta fins al pròxim inici
    (que no es mou) conserva el compàs i ajusta el BPM al nombre enter de
    compassos més pròxim — si `t` ja cau en línia de compàs, el BPM no canvia.

    A diferència de `parteix_trams_a`, que conserva el BPM cec i deixa
    compassos fraccionaris (el bug que bloquejava el flux), ací la frontera
    naix damunt d'una línia de compàs per construcció.

    Retorna els trams normalitzats/validats (o la mateixa llista normalitzada
    si `t` cau damunt d'una frontera existent). Si el marcador cau massa a
    prop de l'inici perquè hi càpiga cap compàs enter dins del rang de BPM
    raonable, es conserva el BPM vigent i el tram queda pendent d'ajust: el
    gest no es bloqueja.
    """
    durada = float(durada or 0.0)
    t = float(t)
    net = normalitza_trams(trams, durada)
    if durada <= 0 or t <= TOL or t >= durada - TOL:
        return net
    for i, s in enumerate(net):
        if not (float(s[0]) + TOL < t < float(s[1]) - TOL):
            continue
        ini, fi = float(s[0]), float(s[1])
        bpm_s, num, den = float(s[2]), int(s[3]), int(s[4])
        ref = float(bpm_s if bpm_ref is None else bpm_ref)
        if ref <= 0:
            ref = BPM_DEFECTE
        bq = _bar_quarters(num, den)
        base = _base_tram(s, i, offset)
        dt = t - base
        if bq <= TOL or dt <= TOL:
            raise ValueError(
                "El marcador cau massa a prop de l'inici del tram")
        n = max(1, _enter_mes_proper(dt * ref / (bq * 60.0)))
        bpm_nou = n * bq * 60.0 / dt
        if not (BPM_EDIT_MIN - TOL <= bpm_nou <= BPM_EDIT_MAX + TOL):
            # Massa a prop de l'inici per a cap compàs enter dins del rang
            # raonable (p. ex. un `+` al primer mig segon). El marcador mana:
            # es conserva el BPM vigent i el tram queda pendent d'ajust, però
            # el gest no es bloqueja (abans s'aixecava ValueError i el `+`
            # es perdia).
            bpm_nou = bpm_s
        # La resta del tram (fins al pròxim inici, que NO es mou) també ha de
        # tindre compassos enters des del marcador: s'ajusta el BPM al nombre
        # enter més pròxim. Si `t` ja cau en línia de compàs, el BPM no canvia.
        bpm_dreta = bpm_s
        dt2 = fi - t
        if dt2 > TOL and bq > TOL:
            n2 = max(1, _enter_mes_proper(dt2 * bpm_s / (bq * 60.0)))
            bpm2 = n2 * bq * 60.0 / dt2
            if BPM_EDIT_MIN - TOL <= bpm2 <= BPM_EDIT_MAX + TOL:
                bpm_dreta = bpm2
        out = list(net)
        out[i:i + 1] = [(ini, t, bpm_nou, num, den),
                        (t, fi, bpm_dreta, num, den)]
        return _mapa_valida_sense_moure(out, durada, offset)
    return net


def retempo_tram_detectat(trams, idx, bpm_detectat, durada, offset=0.0):
    """Ajusta el BPM d'un tram **sense moure cap frontera** («Detecta»).

    El tram conserva `ini` i `fi` (els marcadors delimitadors manen) i els
    veïns no es desplacen: el BPM detectat només és l'**àrbitre** per triar el
    nombre enter de compassos més pròxim:

    ``N = max(1, round(Δt · BPM_detectat / (bar_quarters · 60)))``

    i s'aplica el BPM matemàtic exacte que clava eixos `N` compassos a `Δt`.
    Així el clip queda mètricament vàlid i la música no es desquadra amb el
    següent marcador (l'antic camí amb *ripple* ho desquadrava).

    Retorna el mapa validat. `ValueError` si l'índex no existeix, el BPM no és
    positiu o el BPM resultant ix del rang raonable.
    """
    durada = float(durada or 0.0)
    nous = normalitza_trams(trams, durada)
    i = int(idx)
    if not (0 <= i < len(nous)):
        raise ValueError("El tram de tempo no existeix")
    ini, fi, _bpm0, num, den = nous[i]
    bpm_det = float(bpm_detectat)
    if bpm_det <= 0:
        raise ValueError("El BPM detectat no és vàlid")
    bq = _bar_quarters(int(num), int(den))
    dt = float(fi) - _base_tram(nous[i], i, offset)
    if bq <= TOL or dt <= TOL:
        raise ValueError("El tram no té durada suficient")
    n = max(1, _enter_mes_proper(dt * bpm_det / (bq * 60.0)))
    bpm_final = _valida_bpm_edicio(n * bq * 60.0 / dt, "detectat")
    out = list(nous)
    out[i] = (float(ini), float(fi), bpm_final, int(num), int(den))
    return _mapa_valida_sense_moure(out, durada, offset)


def ajusta_trams_a_marcadors(trams, marcadors, durada, offset=None,
                             referencies=None):
    """Mapa complet amb un tram per interval entre marcadors.

    Acció per lot («Ajusta BPMs a partir dels marcadors per trams»): cada
    interval `[t_k, t_{k+1}]` entre marcadors passa a tindre un nombre enter
    `N_k` de compassos al BPM derivat, amb el BPM de referència (l'àudio
    detectat o el BPM vigent del mapa) com a àrbitre. El «cap» (`0 → t_0`) i la
    «cua» (`t_últim → durada`) són les excepcions permeses (primer inici i
    últim final). L'`offset` passa a ser el primer marcador (és un inici de
    compàs) tret que se n'indique un.

    Retorna el mapa validat. `ValueError` si hi ha menys de dos marcadors.
    """
    durada = float(durada or 0.0)
    ms = []
    for m in sorted(float(x) for x in (marcadors or ())):
        if TOL < m < durada - TOL and (not ms or m - ms[-1] > TOL):
            ms.append(m)
    if len(ms) < 2:
        raise ValueError("Calen almenys dos marcadors per a ajustar el tempo")
    base_trams = normalitza_trams(trams, durada)
    if not base_trams:
        base_trams = [(0.0, durada, BPM_DEFECTE, 4, 4)]
    mapa = TempoMap(base_trams, offset=offset or 0.0)
    off = float(ms[0] if offset is None else offset)
    refs = list(referencies or ())
    intervals = []
    for k, (a, b) in enumerate(zip(ms, ms[1:])):
        dt = float(b) - float(a)
        if dt <= TOL:
            continue
        ref = float(refs[k]) if k < len(refs) and refs[k] else 0.0
        if ref <= 0:
            ref = mapa.bpm((float(a) + float(b)) / 2.0)
        num, den = mapa.signatura(float(a) + TOL)
        bq = _bar_quarters(num, den)
        n = max(1, _enter_mes_proper(dt * ref / (bq * 60.0)))
        bpm = _valida_bpm_edicio(n * bq * 60.0 / dt, f"de l'interval {k + 1}")
        intervals.append((float(a), float(b), bpm, int(num), int(den)))
    if not intervals:
        raise ValueError("Els marcadors no defineixen cap interval")
    num0, den0 = mapa.signatura(0.0)
    out = [(0.0, float(ms[0]), intervals[0][2], int(num0), int(den0))]
    out.extend(intervals)
    num_f, den_f = mapa.signatura(float(ms[-1]) - TOL)
    out.append((float(ms[-1]), durada, intervals[-1][2],
                int(num_f), int(den_f)))
    return _mapa_valida_sense_moure(out, durada, off)


def mou_frontera_retempo(trams, idx_frontera, nou_t, durada, offset=0.0):
    """Mou una frontera **interior** conservant els compassos dels dos costats.

    Inverteix la jerarquia (docs/REGLES_DE_LA_APP.md §13.5): el ratolí fixa
    Δt, el nombre de compassos N de cada tram es conserva i el BPM es recalcula
    (``BPM = N · bq · 60 / Δt``). Cap altre tram del tema no es mou, i les
    fronteres resultants cauen **sempre** en línia de compàs per construcció —
    per això el validador de compassos enters no pot bloquejar l'arrossegament.

    `idx_frontera` és l'índex del tram de la DRETA (la frontera és el seu
    inici); el tram de l'esquerra és `idx_frontera - 1`.

    Excepcions (regles §5): el primer tram conserva la seua zona de pre-música
    (compta des de l'`offset`) i l'últim tram pot acabar on acaba la WAV.

    Retorna el mapa normalitzat i validat. Aixeca `ValueError` amb un missatge
    d'usuari si el moviment no és possible (massa a prop d'un veí, BPM fora de
    rang o mapa que no valida).
    """
    durada = float(durada or 0.0)
    nous = normalitza_trams(trams, durada)
    i = int(idx_frontera)
    if not (0 < i < len(nous)):
        raise ValueError("No hi ha cap frontera interior per a moure")
    a, b = nous[i - 1], nous[i]
    ini_a, fi_b = float(a[0]), float(b[1])
    # Límit físic: només no es pot deixar un tram de durada zero. El mínim de
    # 0,5 s es va traure el 22-10-2026: bloquejava fronteres que ja hi eren a
    # prop (p. ex. el compàs 1 a 0,036 s) i el BPM ja acotat a 30–350 basta.
    minim = ini_a + TOL
    pre = False
    if (i - 1) == 0 and float(offset or 0.0) > ini_a + TOL:
        # El primer tram pot tindre pre-música: la frontera no pot passar
        # ABANS del compàs 1, però sí caure-hi exactament (pre-roll pur) o
        # deixar-hi música.
        pre = True
        minim = max(minim, float(offset))
    maxim = fi_b - TOL
    if maxim <= minim:
        raise ValueError("Els trams són massa curts per a moure la frontera")
    t = float(nou_t)
    if t < minim - TOL:
        if pre:
            raise ValueError(
                "La frontera no pot quedar abans del compàs 1")
        raise ValueError("La frontera deixaria el tram esquerre sense durada")
    if t > maxim + TOL:
        raise ValueError("La frontera deixaria el tram dret sense durada")
    t = min(maxim, max(minim, t))

    lliure_a, lliure_b = _es_lliure_tram(a), _es_lliure_tram(b)
    if lliure_a and lliure_b:
        # Els DOS costats van EN SEGONS: no hi ha cap contracte de compàs i el
        # punter mana (el «BPM» d'un rubato només és referència de notació).
        out = list(nous)
        out[i - 1] = (float(ini_a), float(t), float(a[2]), int(a[3]),
                      int(a[4]))
        out[i] = (float(t), float(fi_b), float(b[2]), int(b[3]), int(b[4]))
        return _mapa_valida_sense_moure(out, durada, offset)

    # Un costat rubato no té compassos, però el SEU VEÍ amb compàs sí: el
    # costat mètric conserva N i recalcula el BPM (el nombre de compassos ha
    # de quedar enter, §13.4) i ha de respectar la banda (§13.5).
    n_a = n_b = None
    bq_a = _bar_quarters(int(a[3]), int(a[4]))
    bq_b = _bar_quarters(int(b[3]), int(b[4]))
    if not lliure_a:
        bars_a = _compassos_del_tram(a, i - 1, offset)
        if abs(bars_a) < 1e-6 and t > float(offset or 0.0) + TOL:
            # Tram de pre-roll sense cap compàs (regla §5): no se li pot
            # inventar un compàs. Estirar-lo és moure el compàs 1.
            raise ValueError(
                "La frontera és el compàs 1: mou-lo amb el botó 📍 (o el camp "
                "«Compàs 1»)")
        # N del costat: el que JA té (el mapa vàlid té compassos enters).
        n_a = max(1, _enter_mes_proper(bars_a))
    if not lliure_b:
        n_b = max(1, _enter_mes_proper(_compassos_del_tram(b, i, offset)))
    if pre and not lliure_a and t <= float(offset) + TOL:
        # Pre-roll PUR: la frontera cau al compàs 1, el tram esquerre no té
        # cap compàs (excepció §5). Conserva el seu BPM; la dreta conserva N.
        n_b = max(1, _enter_mes_proper(_compassos_del_tram(b, i, offset)))
        dt_b = fi_b - float(offset)
        bpm_b = _bpm_de_n(n_b, bq_b, dt_b)
        out = list(nous)
        out[0] = (ini_a, float(offset), float(a[2]), int(a[3]), int(a[4]))
        out[i] = (float(offset), fi_b, bpm_b, int(b[3]), int(b[4]))
        return _mapa_valida_sense_moure(out, durada, offset)
    dt_a = t - _base_tram(a, i - 1, offset)
    # El tram de la dreta comença EXACTAMENT a la frontera (i > 0 → sense offset).
    dt_b = fi_b - t
    if dt_a <= TOL or dt_b <= TOL:
        raise ValueError("La frontera deixaria un tram sense durada")
    # El ratolí fixa Δt; el costat amb compàs conserva N i en deriva el BPM.
    # Un costat rubato (0/0) no té compassos: conserva el seu «BPM» (referència
    # de notació) i només canvia de llargada.
    bpm_a = float(a[2]) if lliure_a else _bpm_de_n(n_a, bq_a, dt_a)
    bpm_b = float(b[2]) if lliure_b else _bpm_de_n(n_b, bq_b, dt_b)
    # Regla #3 (decisió de l'operador, 23-10-2026): un tram **amb compàs** no
    # es pot quedar fora de la banda de BPM. Com que N es conserva, «fora de
    # banda» vol dir un clip massa curt (1 ms → 1.200.000 BPM) o massa llarg.
    # Els trams EN SEGONS (0/0) no hi entren: ixen per la branca de dalt, on
    # el ratolí mana i cap BPM no es toca.
    base_a = _base_tram(a, i - 1, offset)
    lo, hi = float("-inf"), float("inf")
    if not lliure_a:
        lo = max(lo, base_a + n_a * bq_a * 60.0 / BPM_EDIT_MAX)
        hi = min(hi, base_a + n_a * bq_a * 60.0 / BPM_EDIT_MIN)
    if not lliure_b:
        lo = max(lo, fi_b - n_b * bq_b * 60.0 / BPM_EDIT_MIN)
        hi = min(hi, fi_b - n_b * bq_b * 60.0 / BPM_EDIT_MAX)
    if lo > hi + TOL:
        raise ValueError(
            f"No hi ha cap posició que deixe els dos trams dins de "
            f"{BPM_EDIT_MIN:g}–{BPM_EDIT_MAX:g} BPM: el tram quedaria massa "
            "curt per al seu nombre de compassos")
    if t < lo - TOL or t > hi + TOL:
        fora = []
        if not lliure_a and not (BPM_EDIT_MIN - TOL <= bpm_a
                                <= BPM_EDIT_MAX + TOL):
            fora.append(f"l'esquerre a {bpm_a:.0f}")
        if not lliure_b and not (BPM_EDIT_MIN - TOL <= bpm_b
                                <= BPM_EDIT_MAX + TOL):
            fora.append(f"el dret a {bpm_b:.0f}")
        qui = " i ".join(fora) or "un tram"
        raise ValueError(
            f"Quedaria {qui} BPM (fora de {BPM_EDIT_MIN:g}–"
            f"{BPM_EDIT_MAX:g}): mou la frontera entre "
            f"{max(0.0, lo):.3f} i {min(hi, durada):.3f} s")

    out = list(nous)
    out[i - 1] = (ini_a, t, bpm_a, int(a[3]), int(a[4]))
    out[i] = (t, fi_b, bpm_b, int(b[3]), int(b[4]))
    # Els DOS trams afectats queden amb compassos enters exactes per
    # construcció; ho comprovem abans de validar la resta (si un tram VELL
    # del projecte arrossega fraccions, no ha de bloquejar este gest).
    for j, costat in ((i - 1, "esquerre"), (i, "dret")):
        if _es_lliure_tram(out[j]):
            continue                      # rubato: no té compassos
        bars = _compassos_del_tram(out[j], j, offset)
        if abs(bars - _enter_mes_proper(bars)) > 1e-6:
            raise ValueError(
                f"El tram {costat} no ha quedat amb compassos enters "
                f"({bars:.3f})")
    return _mapa_valida_sense_moure(out, durada, offset)


def _bpm_de_n(n, bq, dt):
    """BPM per a `n` compassos (`bq` negres) en `dt` segons. Sense banda."""
    if dt <= 0:
        raise ValueError("La frontera deixaria un tram sense durada")
    bpm = float(n) * float(bq) * 60.0 / float(dt)
    if not (bpm > 0 and bpm == bpm and bpm != float("inf")):
        raise ValueError("El BPM calculat no és vàlid")
    return bpm


def es_frontera_preroll(trams, idx_frontera, offset=0.0):
    """Cert si la frontera `idx_frontera` tanca el **pre-roll**.

    El primer tram no té cap compàs (regla §5): la seua fi és el compàs 1.
    """
    i = int(idx_frontera)
    if not (0 < i < len(trams or ())):
        return False
    off = float(offset or 0.0)
    if off <= float(trams[0][0]) + TOL or _es_lliure_tram(trams[0]):
        return False
    return abs(_compassos_del_tram(trams[0], 0, off)) < 1e-6


def mou_frontera_preroll(trams, idx_frontera, nou_offset, durada, offset=0.0):
    """Arrossegar la frontera del **pre-roll** = moure el **compàs 1**.

    El primer tram no té compassos, així que el gest no li toca el BPM ni n'hi
    inventa cap: canvia l'`offset` i el tram de la música conserva els seus
    compassos (BPM recalculat). És el que fa 📍, però arrossegant el tall.

    Retorna `(trams, nou_offset)`.
    """
    durada = float(durada or 0.0)
    nous = normalitza_trams(trams, durada)
    i = int(idx_frontera)
    if not (0 < i < len(nous)):
        raise ValueError("No hi ha cap frontera de pre-roll per a moure")
    off = float(nou_offset)
    ini_a = float(nous[0][0])
    fi_b = float(nous[i][1])
    if off <= ini_a + TOL:
        raise ValueError("El compàs 1 no pot quedar a l'inici de la WAV")
    if off >= fi_b - TOL:
        raise ValueError("El compàs 1 quedaria més enllà del tram de música")
    b = nous[i]
    n_b = max(1, _enter_mes_proper(_compassos_del_tram(
        b, i, float(offset or 0.0))))
    bq_b = _bar_quarters(int(b[3]), int(b[4]))
    bpm_b = _bpm_de_n(n_b, bq_b, fi_b - off)
    out = list(nous)
    out[0] = (ini_a, off, float(nous[0][2]), int(nous[0][3]), int(nous[0][4]))
    out[i] = (off, fi_b, bpm_b, int(b[3]), int(b[4]))
    return _mapa_valida_sense_moure(out, durada, off), off


def canvia_compassos_tram(trams, idx, delta_compassos=0, durada=0.0,
                          offset=0.0, factor=None):
    """Reinterpreta el tram `idx` amb més/menys compassos, **sense moure'l**.

    Els segons (`ini`, `fi`) queden intactes, els veïns no es toquen i el BPM
    es recalcula perquè `N` compassos hi caben: és una reinterpretació mètrica
    interna del bloc (8 s amb 4 compassos a 60 BPM → ×2 = 8 compassos a 120).

    - `delta_compassos`: suma algebraica (+1, −1…).
    - `factor`: multiplica N (2 = ×2, 0.5 = ÷2), arredonit a l'enter més pròxim.

    Retorna el mapa normalitzat i validat; `ValueError` si N baixa d'1 o el BPM
    ix de la banda raonable.
    """
    durada = float(durada or 0.0)
    nous = normalitza_trams(trams, durada)
    i = int(idx)
    if not (0 <= i < len(nous)):
        raise ValueError("El tram de tempo no existeix")
    if _es_lliure_tram(nous[i]):
        raise ValueError(
            "Aquest clip va en segons: no té compassos per a canviar")
    ini, fi, _bpm, num, den = nous[i]
    bq = _bar_quarters(num, den)
    dt = float(fi) - _base_tram(nous[i], i, offset)
    if dt <= TOL:
        raise ValueError("El tram no té durada")
    n_act = _enter_mes_proper(max(1.0, _compassos_del_tram(nous[i], i, offset)))
    if factor is not None:
        f = float(factor)
        if f <= 0:
            raise ValueError("El factor de compassos ha de ser positiu")
        n_new = _enter_mes_proper(n_act * f)
    else:
        n_new = n_act + int(delta_compassos)
    if n_new < 1:
        raise ValueError("El tram ha de tindre com a mínim un compàs")
    if n_new == n_act:
        return nous
    bpm_new = _valida_bpm_edicio(n_new * bq * 60.0 / dt, "triat")
    out = list(nous)
    out[i] = (float(ini), float(fi), bpm_new, int(num), int(den))
    return valida_i_normalitza_compassos(out, durada, offset)


#: Un tram més curt que això (50 ms) no té cap sentit musical: naix d'un `+`
#: o d'un drag a mil·lèsimes d'una frontera i fa inviable qualsevol validació.
NETEJA_TRAM_S = 0.05


def neteja_trams_curts(trams, minim=NETEJA_TRAM_S):
    """Fon els trams més curts que `minim` amb el veí (no muta l'entrada)."""
    out = [tuple(t) for t in (trams or ())]
    if len(out) <= 1 or minim <= 0:
        return out
    i = 0
    while i < len(out) and len(out) > 1:
        ini, fi = float(out[i][0]), float(out[i][1])
        if fi - ini < minim:
            if i > 0:
                pre = out[i - 1]
                out[i - 1] = (pre[0], fi, pre[2], pre[3], pre[4])
                del out[i]
                i = max(0, i - 1)
            else:
                seg = out[1]
                out[0] = (ini, seg[1], seg[2], seg[3], seg[4])
                del out[1]
                i = 0
        else:
            i += 1
    return out


def refit_trams(trams, durada, offset=0.0):
    """Repara el mapa **recalculant** el BPM de cada tram amb N enter.

    Cada frontera és la fi del tram de l'esquerra: si es conserva el nombre de
    compassos i es recalcula el BPM, la frontera cau exactament a la seua
    graella sense moure-la (l'inici del tram de la dreta n'és la base). És
    l'últim recurs de `repara_fronteres` quan imantar la frontera faria curt
    un dels dos costats.

    L'últim tram i el pre-roll pur conserven el BPM (excepcions §5).
    """
    durada = float(durada or 0.0)
    out = normalitza_trams(trams, durada)
    res = []
    for i, (ini, fi, bpm, num, den) in enumerate(out):
        if i == len(out) - 1:
            res.append((ini, fi, bpm, num, den))
            continue
        base = _base_tram(out[i], i, offset)
        bq = _bar_quarters(num, den)
        dt = float(fi) - base
        if dt <= TOL or bq <= TOL:
            res.append((ini, fi, bpm, num, den))
            continue
        n = max(1, _enter_mes_proper(dt * float(bpm) / (bq * 60.0)))
        bpm2 = n * bq * 60.0 / dt
        if not (BPM_EDIT_MIN - TOL <= bpm2 <= BPM_EDIT_MAX + TOL):
            res.append((ini, fi, bpm, num, den))
            continue
        res.append((ini, fi, bpm2, num, den))
    return valida_i_normalitza_compassos(res, durada, offset)


def repara_fronteres(trams, durada, offset=0.0):
    """Fa vàlid un mapa **imantant** les fronteres que no cauen a la graella.

    Les operacions sobre el mapa (eliminar, fusionar o duplicar un tram)
    hereten fronteres d'altres trams amb un BPM lleugerament diferent: la
    frontera queda fora de la línia de compàs (a mil·lèsimes, o a un tros de
    compàs si els BPM difereixen) i el contracte de compassos enters la
    rebutja — l'operació quedava bloquejada (bug 21-10: després de l'Anàlisi
    guiat no es podien editar els trams de tempo).

    Esmena: la frontera **més desviada** s'imanta amb `snap_frontera_compas`
    (que prova les línies de compàs més pròximes fins que el mapa valida i
    arrossega les fronteres següents). Es repeteix fins que valida o no hi ha
    res a imantar. Si no és pot, propaga el `ValueError` original.
    """
    durada = float(durada or 0.0)
    out = neteja_trams_curts(normalitza_trams(trams, durada))
    if len(out) <= 1:
        return out
    error = None
    for _ in range(2 * len(out) + 2):
        try:
            return _comprova_banda(
                valida_i_normalitza_compassos(out, durada, offset))
        except ValueError as e:
            error = e
        pitjor = None
        for i in range(1, len(out)):
            t = float(out[i][0])
            linies = _bar_lines_tram(out[i - 1], offset)
            if not linies:
                continue
            millor = min(linies, key=lambda c: abs(float(c) - t))
            d = abs(float(millor) - t)
            if d > TOL_COMPAS and (pitjor is None or d > pitjor[0]):
                pitjor = (d, i - 1, t)
        if pitjor is None:
            break
        _d, p_idx, t = pitjor
        try:
            _tall, out = snap_frontera_compas(out, p_idx, t, durada, offset)
        except ValueError:
            break
    # Últim recurs: conservar les fronteres i recalcular els BPM (N enter).
    try:
        return _comprova_banda(refit_trams(out, durada, offset))
    except ValueError:
        pass
    raise error if error is not None else ValueError("Mapa de tempo invàlid")


def _comprova_banda(trams):
    """Rebutja un mapa amb BPM fora de `BPM_EDIT_MIN/MAX` (reparació interna).

    L'operador pot arrossegar un tall fins on vulga (regla 22-10-2026), però
    una REPARACIÓ no ha de convertir un mapa sa en un d'impossible: un tram de
    pocs mil·lisegons amb 1 compàs donava 5.978 BPM i 5.972 compassos.
    """
    for i, t in enumerate(trams or ()):
        bpm = float(t[2])
        if not (BPM_EDIT_MIN - TOL <= bpm <= BPM_EDIT_MAX + TOL):
            raise ValueError(
                f"El tram {i + 1} quedaria a {bpm:.1f} BPM, fora del rang "
                f"{BPM_EDIT_MIN:g}–{BPM_EDIT_MAX:g}")
    return trams


def parteix_a_compas(trams, idx, t, durada, offset=0.0):
    """Parteix el tram `idx` per la línia de compàs més pròxima a `t`.

    Retorna `(tall, mapa_normalitzat)` o aixeca `ValueError` si el tall deixaria
    un tram interior sense cap compàs sencer.
    """
    durada = float(durada or 0.0)
    nous = normalitza_trams(trams, durada)
    idx = int(idx)
    if not (0 <= idx < len(nous)):
        raise ValueError("El tram de tempo no existeix")
    tram = nous[idx]
    ini, fi, bpm, num, den = tram
    b = durada_compas(bpm, num, den)
    if b <= TOL:
        raise ValueError("El compàs té una durada nul·la")
    cands = [c for c in _bar_lines_tram(tram, offset)
             if float(ini) + TOL_COMPAS < c < float(fi) - TOL_COMPAS]
    for c in sorted(cands, key=lambda x: abs(x - float(t))):
        out = list(nous)
        out[idx:idx + 1] = [(float(ini), float(c), bpm, num, den),
                            (float(c), float(fi), bpm, num, den)]
        try:
            return float(c), valida_i_normalitza_compassos(out, durada, offset)
        except ValueError:
            continue
    raise ValueError("No hi ha cap línia de compàs vàlida per a este tall")


def afegeix_tall(trams, t):
    """Insereix una frontera nova a `t`, heretant el tempo/compàs del tros que hi ha.

    Retorna la llista de trossos amb el nou (encara per normalitzar).
    """
    t = float(t)
    trams = list(trams or [])
    # Regla #1: un sol tram pot començar en cada instant. Si el tall ja hi és,
    # no se'n crea un altre (ni tan sols per a ser descartat després).
    if any(abs(float(s[0]) - t) <= TOL for s in trams):
        return trams
    for s in trams:
        if float(s[0]) - TOL <= t <= float(s[1]) + TOL:
            return trams + [(t, t, float(s[2]), int(s[3]), int(s[4]))]
    return trams + [(t, t, 120.0, 4, 4)]


def fusiona_trams(trams, i, amb="seguent"):
    """Fusiona el tram `i` amb el veí (mirall de `pipeline.fusiona_acords`).

    Regla d'or #11: el carril de BPM/compàs ha de tindre les **mateixes
    operacions** que els d'acords i estructura. «Fusionar» ací vol dir
    **traure una frontera** (l'invers de «partir»): mana el BPM/compàs del
    tram que s'estira.

    - `"seguent"`: el tram `i` s'estira fins al fi del següent (mana el SEU BPM).
    - `"anterior"`: el tram anterior s'estira fins al fi de `i` (mana el d'aquell).

    Retorna la llista NOVA (encara per normalitzar); no muta l'entrada. Si no
    es pot (índex fora de rang o sense veí), torna la llista tal com estava.
    """
    out = list(trams or [])
    if not (0 <= i < len(out)):
        return out
    if amb == "anterior":
        if i == 0:
            return out
        out[i - 1] = (float(out[i - 1][0]), float(out[i][1])) + tuple(out[i - 1][2:])
        del out[i]
    else:
        if i + 1 >= len(out):
            return out
        out[i] = (float(out[i][0]), float(out[i + 1][1])) + tuple(out[i][2:])
        del out[i + 1]
    return out


def elimina_tall(trams, idx):
    """Treu el tros `idx` del mapa (els veïns n'ocupen l'espai).

    El mapa **sempre** comença a 0: si el tros eliminat era el PRIMER, el nou
    primer s'hi **ancora** (abans quedava a l'inici vell i `normalitza_trams`
    hi afegia un tros duplicat — mai es podia arribar a un sol tram).
    """
    trams = list(trams or [])
    if not (0 <= idx < len(trams)):
        return trams
    out = trams[:idx] + trams[idx + 1:]
    if idx == 0 and out:
        out[0] = (0.0,) + tuple(out[0][1:])
    return out


def infereix_trams_beat(temps, durada, num=4, den=4, tol=0.12, finestra=3):
    """Dedueix els trossos del mapa a partir dels temps dels **temps** (beats).

    Calcula els intervals entre temps, els suavitza amb una **mediana local**
    (`finestra`) i obre un tros nou quan el període local canvia més d'un
    `tol` relatiu. El tempo de cada tros és `60/període`. Retorna trossos
    `(ini, fi, bpm, num, den)` contigus (via `normalitza_trams`).
    """
    ts = sorted(float(t) for t in (temps or ()))
    durada = float(durada or 0.0)
    if len(ts) < 2 * finestra + 2:
        return [(0.0, durada, 120.0, int(num), int(den))]
    ibis = [ts[i + 1] - ts[i] for i in range(len(ts) - 1)]
    local = []
    for i in range(len(ibis)):
        a, b = max(0, i - finestra), min(len(ibis), i + finestra + 1)
        local.append(mediana(ibis[a:b]))
    trossos, ref, ini_i = [], local[0], 0
    for i in range(1, len(local)):
        if ref > 0 and abs(local[i] - ref) / ref > tol:
            trossos.append((ini_i, i, ref))
            ref, ini_i = local[i], i
    trossos.append((ini_i, len(local), ref))
    out = []
    for a, b, peri in trossos:
        ini = ts[a]
        fi = ts[b + 1] if b + 1 < len(ts) else (durada or ts[-1])
        out.append((ini, fi, (60.0 / peri) if peri > 0 else 120.0,
                    int(num), int(den)))
    return normalitza_trams(out, durada)


def mediana(vals):
    """Mediana d'una llista (stdlib `statistics`, però sense import extra)."""
    v = sorted(vals)
    n = len(v)
    if n == 0:
        return 0.0
    m = n // 2
    return float(v[m]) if n % 2 else (v[m - 1] + v[m]) / 2.0


def bloc_sobre_trams(trams, bloc, llargada, T, durada):
    """Mapa de BPM/compàs amb el bloc enganxat sobre `[T, T+llargada]`.

    El mapa està **SATURAT** (cobreix sempre `[0, durada]` amb trams
    contigus): enganxar-hi un bloc de trams no insereix res, **obre les
    fronteres** del bloc i hi **canvia el BPM/compàs**.
    """
    out = list(trams or [])
    if not bloc:
        return out
    T = float(T)
    llargada = float(llargada or 0.0)
    for (r, _rfi, _b, _n, _d) in bloc:
        t = T + float(r)
        if t < durada - 1e-6:
            out = afegeix_tall(out, t)
    te = T + llargada
    if 1e-6 < te < durada - 1e-6:
        out = afegeix_tall(out, te)

    def _valor(rel):
        for (r, rfi, b, n, d) in bloc:
            if float(r) - 1e-9 <= rel < float(rfi) - 1e-9:
                return float(b), int(n), int(d)
        return None

    nou = []
    for s in out:
        v = _valor(float(s[0]) - T)
        nou.append((float(s[0]), float(s[1]), v[0], v[1], v[2])
                   if v else (float(s[0]), float(s[1]), s[2], s[3], s[4]))
    return nou


# ---------------------------------------------------------------------------
# Guiat v2: confirmació de la detecció amb el tram anterior i un tros llarg
# ---------------------------------------------------------------------------
def avalua_confirmacio(bpm, prev=None, banda=None, llarga=None,
                       tol=0.5, tol_prev_pct=3.0):
    """Decideix si el BPM detectat és **fiable** o **dubtós** (guiat v2).

    Tres mesures del mateix tram, fetes per `main.FilGuiaBpm`:

    - `bpm`: la detecció normal (lliure) sobre la finestra del tram.
    - `banda`: la mateixa finestra buscant **només** dins del ±8 % del BPM
      del tram anterior (si el tempo continua prop del que portàvem).
    - `llarga`: la detecció normal sobre el **doble** de tros (una mesura
      llarga és molt més estable que una de curta).

    Es considera **fiable** si coincidix amb totes les que hi ha (tolerància
    `tol` BPM entre mesures, `tol_prev_pct` % respecte del tram anterior).
    Si alguna discrepa → **dubtós** (l'usuari decideix; millor això que
    donar-li un número fals amb cara de bo).

    Retorna ``{"estat": "fiable"|"dubtos"|"sense", "bpm": float|None,
    "detall": str, "coincideix": bool}``.
    """
    res = {"estat": "sense", "bpm": None, "detall": "", "coincideix": False}
    if bpm is None:
        bpm = banda if banda is not None else llarga
        if bpm is None:
            res["detall"] = "cap mesura utilitzable"
            return res
    bpm = float(bpm)
    res["bpm"] = bpm
    trossos = []
    coincideix = True
    if banda is not None:
        ok = abs(float(banda) - bpm) <= float(tol)
        coincideix = coincideix and ok
        trossos.append(f"tram anterior {float(banda):.2f}"
                       + ("" if ok else " ✗"))
    if llarga is not None:
        ok = abs(float(llarga) - bpm) <= float(tol)
        coincideix = coincideix and ok
        trossos.append(f"tros llarg {float(llarga):.2f}"
                       + ("" if ok else " ✗"))
    if prev:
        ok = abs(float(prev) - bpm) <= max(float(tol),
                                           float(prev) * tol_prev_pct / 100.0)
        coincideix = coincideix and ok
        trossos.append(f"anterior {float(prev):.2f}" + ("" if ok else " ✗"))
    res["coincideix"] = bool(coincideix and trossos)
    res["estat"] = "fiable" if res["coincideix"] else (
        "dubtos" if trossos else "sense")
    res["detall"] = (f"✓ fiable ({'; '.join(trossos)})" if res["coincideix"]
                     else (f"⚠ dubtós — {bpm:.2f} vs " + "; ".join(trossos)
                           if trossos else ""))
    return res
