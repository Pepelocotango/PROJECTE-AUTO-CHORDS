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

El contracte vigent és a `docs/REGLES_DE_LA_APP.md` §13.
"""
from __future__ import annotations

import math
from collections import namedtuple

from app import limits, tempo_recalc

# Tolerància temporal (evita falsos positius de coma flotant).
TOL = 1e-9
# Tolerància per a les fronteres de compàs en segons (els CSV guarden 1 µs).
TOL_COMPAS = 1e-4
# Un canvi de compàs a menys d'esta tolerància (s) d'una línia de compàs
# s'imanta a la línia: una edició manual de mil·lisegons no ha de crear dos
# compassos quasi iguals ni desplaçar la graella/metrònom.
TOL_GRID_S = 0.02
# BPM de seguretat (regla d'or #8): un valor no positiu no és vàlid i es
# substitueix per aquest (el mateix que fa servir `TempoMap`).
BPM_DEFECTE = 120.0
BPM_EDIT_MIN = limits.BPM_MIN
BPM_EDIT_MAX = limits.BPM_MAX


def valida_tempo(bpm, num, den):
    """Valida BPM i compàs; retorna `(bpm, num, den)` normalitzats.

    `0/0` és l'única representació vàlida d'un tram en segons (rubato).
    """
    try:
        b = float(bpm)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("El BPM no és un número vàlid") from None
    if not math.isfinite(b):
        raise ValueError("El BPM ha de ser finit")
    if not limits.BPM_MIN <= b <= limits.BPM_MAX:
        raise ValueError(
            f"El BPM ha d'estar entre {limits.BPM_MIN:g} i "
            f"{limits.BPM_MAX:g}")

    def _enter(valor, nom):
        try:
            n = float(valor)
        except (TypeError, ValueError, OverflowError):
            raise ValueError(f"El {nom} del compàs no és vàlid") from None
        if not math.isfinite(n) or not n.is_integer():
            raise ValueError(f"El {nom} del compàs ha de ser un enter")
        return int(n)

    numerador = _enter(num, "numerador")
    denominador = _enter(den, "denominador")
    if numerador == 0 and denominador == 0:
        return b, 0, 0
    if numerador == 0 or denominador == 0:
        raise ValueError("El compàs ha de ser 0/0 per anar en segons")
    if not limits.NUM_MIN <= numerador <= limits.NUM_MAX:
        raise ValueError(
            f"El numerador ha d'estar entre {limits.NUM_MIN} i "
            f"{limits.NUM_MAX}")
    if denominador not in limits.DENOMINADORS_ADMESOS:
        valors = ", ".join(str(x) for x in limits.DENOMINADORS_ADMESOS)
        raise ValueError(f"El denominador ha de ser {valors}")
    return b, numerador, denominador

# Un tros del mapa: temps i compàs constants dins `[ini, fi)`.
#   bpm = negres per minut · num/den = compàs (p. ex. 4/4, 6/8, 12/8)
#   agrupacio = `3+3` per a `6/8`; buit = agrupació automàtica per signatura.
_TramBase = namedtuple(
    "Tram", ("ini", "fi", "bpm", "num", "den", "agrupacio"),
    defaults=("",))


class Tram(_TramBase):
    """Tram de tempo/compàs amb interfície compatible amb `Clip(ini, fi, payload)`."""

    @property
    def payload(self):
        return (self.bpm, self.num, self.den)

    @property
    def agrupacio_efectiva(self):
        """Grups de temps efectius (explícits o deduïts de la signatura)."""
        agr = text_a_agrupacio(self.agrupacio)
        return agr or agrupacio_compas(self.num, self.den)

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


def rol_tram(trams, idx):
    """Rol estructural derivat d'un tram: `unic`, `primer`, `ultim`, `interior`."""
    n = len(trams or ())
    try:
        idx = int(idx)
    except (TypeError, ValueError):
        return "interior"
    if n <= 0 or idx < 0 or idx >= n:
        return "interior"
    if n == 1:
        return "unic"
    if idx == 0:
        return "primer"
    if idx == n - 1:
        return "ultim"
    return "interior"


def es_preroll_tram(trams, idx, offset=0.0):
    """True si el tram és el pre-roll inicial (0 → compàs 1)."""
    trams = list(trams or ())
    if not trams or int(idx) != 0 or float(offset or 0.0) <= TOL:
        return False
    try:
        return float(trams[0].fi) <= float(offset) + TOL
    except (AttributeError, TypeError, ValueError, IndexError):
        try:
            return float(trams[0][1]) <= float(offset) + TOL
        except (TypeError, ValueError, IndexError):
            return False


def agrupacio_compas(num, den):
    """Grups de temps dins del compàs, en unitats del denominador.

    És el `beat grouping` dels DAW: la suma de la tupla és sempre `num`.
    Per defecte:
      - `6/8`, `9/8`, `12/8` → grups de 3;
      - `5/8` → `3+2`; `7/8` → `2+2+3`; `8/8` → `3+3+2`;
      - la resta → un sol grup (`num`), és a dir només accent de compàs.
    """
    try:
        num, den = int(num), int(den)
    except (TypeError, ValueError):
        return (4,)
    if num <= 0 or den <= 0:
        return (4,)
    if den == 8 and num >= 6 and num % 3 == 0:
        return tuple([3] * (num // 3))
    return {
        (5, 8): (3, 2),
        (7, 8): (2, 2, 3),
        (8, 8): (3, 3, 2),
    }.get((num, den), (num,))


def inicis_grups(num, den):
    """Inicis de grup (0-based, en unitats del denominador) dins del compàs."""
    out = []
    q = 0
    for mida in agrupacio_compas(num, den):
        out.append(q)
        q += int(mida)
    return tuple(out)


def es_inici_grup(beat, num, den):
    """True si `beat` (1-based) és l'inici d'un grup del compàs."""
    try:
        beat = int(beat)
    except (TypeError, ValueError):
        return False
    return beat > 0 and (beat - 1) in inicis_grups(num, den)


def text_a_agrupacio(text):
    """`"3+3"` → `(3, 3)`; buit/`auto` → `()` (agrupació per defecte)."""
    s = str(text or "").strip().lower().replace(" ", "")
    if not s or s == "auto":
        return ()
    parts = s.split("+")
    try:
        valors = tuple(int(p) for p in parts)
    except (TypeError, ValueError):
        raise ValueError(f"L'agrupació «{text}» no és vàlida") from None
    if not valors or any(v <= 0 for v in valors):
        raise ValueError(f"L'agrupació «{text}» ha de tindre grups positius")
    return valors


def agrupacio_a_text(agrupacio):
    """`(3, 3)` → `"3+3"`; `()` → `""` (automàtica)."""
    return "+".join(str(int(v)) for v in (agrupacio or ()))


def valida_agrupacio(text, num, den):
    """Normalitza una agrupació per a un compàs; retorna `""` si és auto."""
    agr = text_a_agrupacio(text)
    if not agr:
        return ""
    try:
        num = int(num)
    except (TypeError, ValueError):
        raise ValueError("El compàs no és vàlid per a l'agrupació") from None
    if sum(agr) != num:
        raise ValueError(
            f"L'agrupació «{text}» suma {sum(agr)} temps, però el compàs "
            f"{num}/{int(den)} en té {num}")
    return agrupacio_a_text(agr)


def _expandeix_segments(segments):
    """Normalitza els segments d'entrada a tuples de 6 elements.

    El model nou no té rubatos expandits: tots els trams són una graella
    mètrica única. Les tuples antigues de 5 elements es mantenen.
    """
    out = []
    for s in segments or ():
        agr = s[5] if len(s) > 5 else getattr(s, "agrupacio", "")
        out.append(tuple(s)[:5] + (agr,))
    return out


class TempoMap:
    """Mapa de tempo i compàs a trossos, amb integració temps↔negres.

    `segments`: `[(ini, fi, bpm, num, den), …]` — trossos contigus i ordenats.
    Si no cobreixen des de 0 s'estén el primer cap a l'esquerra; per a instants
    més enllà de l'últim s'extrapola amb el seu tempo.
    `offset`: instant del **compàs 1** (origen de la numeració).
    """

    # Valor per defecte si no hi ha cap tros (defensa).
    _DEFECTE = Tram(0.0, 0.0, 120.0, 4, 4, "")

    def __init__(self, segments, offset=0.0):
        segments = _expandeix_segments(segments)
        trams = []
        for s in segments or ():
            ini, fi, bpm, num, den = (float(s[0]), float(s[1]), float(s[2]),
                                      int(s[3]), int(s[4]))
            agr = getattr(s, "agrupacio", "") if len(s) <= 5 else s[5]
            if num <= 0 or den <= 0:
                # Tros EN SEGONS: no té compàs. El BPM només és la referència
                # de notació (100 per defecte).
                num = den = 0
                bpm = bpm if bpm > 0 else 100.0
                agr = ""
            elif den <= 0:
                den = 4
            if bpm <= 0:
                bpm = 120.0
            try:
                agr = valida_agrupacio(agr, num, den)
            except ValueError:
                agr = ""
            trams.append(Tram(ini, fi, bpm, num, den, agr))
        trams.sort(key=lambda x: x.ini)
        if trams and trams[0].ini > TOL:
            s0 = trams[0]
            trams.insert(0, Tram(0.0, s0.ini, s0.bpm, s0.num, s0.den,
                                 s0.agrupacio))
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
                             _t.den, _t.agrupacio)
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
        """Tros actiu a `t`, extrapolant el primer/últim fora del mapa."""
        t = float(t)
        if t < self._trams[0].ini - TOL:
            return self._trams[0]
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

    def agrupacio(self, t):
        """Grups de temps efectius a `t` (explícits o per signatura)."""
        return self.tram(t).agrupacio_efectiva

    def te_agrupacions_explicites(self):
        """True si algun tram té una agrupació explícita."""
        return any(bool(s.agrupacio) for s in self._trams)

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
                   and s.agrupacio == s0.agrupacio
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
        if float(t) < self._trams[0].ini - TOL:
            return 0
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
            if canvi is None:
                # Un canvi just DESPRÉS de la línia (per una edició manual de
                # pocs ms) també s'ha d'imantar a la línia; si no, el compàs
                # actual s'afegiria i després el canvi crearia un duplicat.
                canvi = self._canvi_compas_entre(
                    t_end, t_end + TOL_GRID_S, sig)
            if canvi is not None:
                # Canvi de compàs a mig compàs: es tanca el compàs ahí i se'n
                # comença un altre amb la signatura nova. Si cau a tocar de la
                # línia, s'imanta a la línia (q_end/t_end) per mantindre la
                # numeració i la graella alineades.
                t_nou, sig_nou = canvi
                q_nou = self.quarters(t_nou)
                if q_nou <= q_bar + TOL:
                    break
                if abs(float(t_nou) - float(t_end)) <= TOL_GRID_S:
                    q_nou, t_nou = q_end, t_end
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
        # La integració del tempo pot deixar offsets de fraccions de fusa a
        # les línies de compàs. Arrodonim la distància a la subdivisió de
        # 1/32 (1/8 de negra) perquè un clic o una etiqueta a la vora no es
        # quede un sample abans del beat.
        dins = round(dins * 8.0) / 8.0
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
def _com_a_tuples(trams):
    """Converteix `TramMapa` a tuples de 5 elements (sense metadades)."""
    return [tuple(t)[:5] for t in (trams or ())]


def neteja_trams(trams, durada, preserva_fi_idx=None):
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

    **`preserva_fi_idx`**: índex del tram que ha de conservar el seu `fi` original
    en edicions mètriques que no canvien els segons. Només s'usa en camins
    interns on es garanteix que la contigüitat es respecta.
    """
    durada = float(durada or 0.0)
    trams = _com_a_tuples(trams)
    net, avisos = [], []
    def _clau_inici(t):
        try:
            ini = float(t[0])
        except (TypeError, ValueError, IndexError):
            return 0.0
        return ini if math.isfinite(ini) else 0.0

    for t in sorted(trams or (), key=_clau_inici):
        try:
            ini = float(t[0])
        except (TypeError, ValueError, IndexError):
            avisos.append("Un tram tenia un inici invàlid: s'ha descartat.")
            continue
        if not math.isfinite(ini):
            avisos.append("Un tram tenia un inici no finit: s'ha posat a 0.")
            ini = 0.0
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
        except (TypeError, ValueError, IndexError):
            fi0 = ini
        if not math.isfinite(fi0):
            avisos.append("Un tram tenia un fi no finit: s'ha recalculat.")
            fi0 = ini
        if fi0 < ini - TOL:
            avisos.append("Un tram tenia el fi abans de l'inici: "
                          "s'ha recalculat.")
        try:
            bpm, num, den = valida_tempo(t[2], t[3], t[4])
        except (ValueError, IndexError, TypeError) as e:
            avisos.append(f"Un tram tenia tempo/compàs invàlid ({e}); "
                          "s'ha reparat.")
            try:
                num0, den0 = int(t[3]), int(t[4])
            except (ValueError, TypeError, IndexError):
                num0, den0 = 4, 4
            num, den = (0, 0) if num0 == den0 == 0 else (4, 4)
            try:
                bpm0 = float(t[2])
            except (ValueError, TypeError, IndexError):
                bpm0 = float("nan")
            bpm = (bpm0 if math.isfinite(bpm0)
                   and limits.BPM_MIN <= bpm0 <= limits.BPM_MAX
                   else (100.0 if num == den == 0 else BPM_DEFECTE))
        net.append((ini, fi0, bpm, num, den))
    if not net:
        return [], avisos
    out = []
    for i, t in enumerate(net):
        if preserva_fi_idx is not None and i == int(preserva_fi_idx):
            # Preserva el fi original d'aquest tram (edicció mètrica)
            fi = float(t[1]) if float(t[1]) > float(t[0]) + TOL else t[0]
        elif i + 1 < len(net):
            fi = net[i + 1][0]
        elif durada > TOL:
            fi = durada                 # regla #4: l'últim acaba a la WAV
        else:
            fi = float(t[1]) if float(t[1]) > float(t[0]) + TOL else t[0]
        out.append((t[0], fi, t[2], t[3], t[4]))
    if out[0][0] > TOL:
        out.insert(0, (0.0, out[0][0], out[0][2], out[0][3], out[0][4]))
    return out, avisos


def normalitza_trams(trams, durada, preserva_fi_idx=None):
    """`neteja_trams` sense els avisos (compatibilitat i camins interns).

    **`preserva_fi_idx`**: índex del tram que ha de conservar el seu `fi` original
    en edicions mètriques que no canvien els segons.
    """
    return neteja_trams(trams, durada, preserva_fi_idx=preserva_fi_idx)[0]


# --- contracte de BEATS SENCERS (docs/REGLES_DE_LA_APP.md §13.4) ------------
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


def _beat_segons_tram(tram):
    """Duració en segons d'un temps de la graella del tram."""
    bpm, num, den = float(tram[2]), int(tram[3]), int(tram[4])
    if bpm <= TOL or num <= 0 or den <= 0:
        return 0.0
    return _beat_quarters(den) * 60.0 / bpm


def _graella_beats(trams, durada, offset=0.0, beats_qm=None):
    """Línies de beat que validen el mapa.

    Si `beats_qm` té valors, mana la graella QM (mode Snap «Beats QM»). Si no,
    es deriva la graella BPM/compàs del mapa. Retorna una llista ordenada.
    """
    qm = sorted({float(b) for b in (beats_qm or ())})
    if qm:
        return qm
    mapa = TempoMap(trams, offset=offset)
    grid = [float(t) for t in mapa.grid_lines(0.0, float(durada),
                                               kind="beat")]
    # El primer clip pot tindre pre-roll abans de l'offset. La graella de
    # beats continua cap enrere amb el BPM/compàs del primer tram: eixos
    # beats també compten per a la regla del primer clip.
    if float(offset) > TOL and trams:
        base_tram = trams[0]
        beat = _beat_segons_tram(base_tram)
        if beat > TOL:
            lo = float(offset) + math.floor((0.0 - float(offset)) / beat) * beat
            t = lo
            while t <= float(offset) + TOL:
                if -TOL <= t <= float(durada) + TOL:
                    grid.append(float(t))
                t += beat
    return sorted(set(round(float(t), 9) for t in grid))


def clip_conte_beat_sencer(tram, graella, tol=TOL_COMPAS):
    """Cert si dins del clip hi ha un beat complet de la graella.

    Ha d’existir un interval `[b_i, b_i+1]` de dos beats consecutius
    completament dins de `[ini, fi]`. No basta que el clip dure més d’un beat:
    els dos extrems del beat han de caure dins del clip.
    """
    if not graella or len(graella) < 2:
        return False
    ini, fi = float(tram[0]), float(tram[1])
    return any(float(a) + tol >= ini and float(b) - tol <= fi
               for a, b in zip(graella, graella[1:]))


def _graella_tram(tram, idx, offset=0.0, durada=0.0):
    """Línies de beat d'un clip, ancorades al seu inici musical.

    El primer clip compta des de l'offset (pot incloure pre-roll negatiu); la
    resta des del seu propi inici. Així una frontera de tempo no es converteix
    artificialment en una línia de beat.
    """
    num, den = int(tram[3]), int(tram[4])
    beat = _beat_segons_tram(tram)
    if beat <= TOL or num <= 0 or den <= 0:
        return []
    base = float(offset) if int(idx) == 0 else float(tram[0])
    ini, fi = float(tram[0]), float(tram[1])
    k0 = int(math.floor((ini - base) / beat)) - 2
    k1 = int(math.ceil((fi - base) / beat)) + 2
    return [base + k * beat for k in range(k0, k1 + 1)
            if -TOL <= base + k * beat <= float(durada) + TOL]


def valida_i_normalitza_compassos(trams, durada, offset=0.0,
                                  preserva_fi_idx=None, beats_qm=None):
    """Valida el contracte de clips de tempo i retorna el mapa normalitzat.

    Contracte nou (`docs/REGLES_DE_LA_APP.md` §13.4):

    - Cada clip ha de contindre **almenys un beat sencer** de la graella
      seleccionada pel Snap.
    - Si Snap = **Beats QM**, la graella és la de beats QM.
    - En qualsevol altre mode (o si no hi ha QM), la graella és la de
      BPM/compàs del mapa.
    - Les fronteres interiors han de caure en una línia d’eixa graella.
    - **N enter sempre**: cap clip pot quedar amb un nombre fraccionari de
      compassos, inclòs el primer i l’últim.
    - El primer inici és 0 i l’últim final és la durada de la WAV.

    `beats_qm` és opcional: només s’ha de passar quan el mode Snap és
    «qm_beats». Si no es passa, es valida amb la graella BPM/compàs.

    Aixeca `ValueError` amb un missatge d’usuari si algun clip no complix el
    contracte.

    **`preserva_fi_idx`**: índex del tram que ha de conservar el seu `fi`
    original en edicions mètriques que no canvien els segons.
    """
    durada = float(durada or 0.0)
    for i, t in enumerate(trams or ()):
        if durada > 0 and float(t[0]) >= durada - TOL:
            raise ValueError("Hi ha un tram que comença fora de la WAV")
        try:
            valida_tempo(t[2], t[3], t[4])
        except (ValueError, IndexError, TypeError) as e:
            raise ValueError(f"Tram {i + 1}: {e}") from None
    nous = normalitza_trams(trams, durada, preserva_fi_idx=preserva_fi_idx)
    if not nous:
        raise ValueError("El mapa de tempo/compàs és buit")
    if not any(int(t[3]) > 0 and int(t[4]) > 0 for t in nous):
        return nous                       # tot el mapa va en segons/rubato

    def _lliure(t):
        return int(t[3]) <= 0 or int(t[4]) <= 0

    n = len(nous)
    for i, tram in enumerate(nous):
        if _lliure(tram):
            continue                       # rubato / en segons: lliure
        graella = (_graella_beats(nous, durada, offset, beats_qm)
                   if beats_qm else _graella_tram(tram, i, offset, durada))
        if len(graella) < 2:
            raise ValueError(
                f"El tram {i + 1} no té cap graella de beats per a validar")
        inici_lliure = (i == 0) or (i > 0 and _lliure(nous[i - 1]))
        fi_lliure = (i == n - 1) or (i + 1 < n and _lliure(nous[i + 1]))
        if not inici_lliure:
            graella_esq = (_graella_beats(nous, durada, offset, beats_qm)
                           if beats_qm
                           else _graella_tram(nous[i - 1], i - 1,
                                              offset, durada))
            if not any(abs(float(tram[0]) - float(b)) <= TOL_COMPAS
                       for b in graella_esq):
                raise ValueError(
                    f"El tram {i + 1} no comença en una línia de beat "
                    f"({float(tram[0]):.6f}s)")
        if not fi_lliure:
            if not any(abs(float(tram[1]) - float(b)) <= TOL_COMPAS
                       for b in graella):
                raise ValueError(
                    f"El tram {i + 1} no acaba en una línia de beat "
                    f"({float(tram[1]):.6f}s)")
        if not clip_conte_beat_sencer(tram, graella):
            raise ValueError(
                f"El tram {i + 1} no conté cap beat sencer de la graella")
        n_clip = compassos_del_clip(tram)
        if abs(n_clip - round(n_clip)) > 1e-3 or round(n_clip) < 1:
            raise ValueError(
                f"El tram {i + 1} no té un nombre enter de compassos "
                f"({n_clip:.3f}); ajusta N, el BPM o el compàs")
    return nous


# --- Anàlisi guiat -----------------------------------------------------------
def parteix_trams_a(trams, t, durada):
    """Talla el mapa a la posició `t` (mateix bpm/compàs als dos trossos).

    L'«Anàlisi guiat» l'usa per al tall LLIURE del carril de tempo al punt del
    cursor: encara no hi ha cap contracte de beats sencers en joc (la zona
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


def ajusta_primer_clip_a_compas(trams, durada, offset=0.0):
    """Fa que el primer clip siga **un compàs sencer** en fixar l'offset.

    El primer clip és el pre-roll (0 → offset). Quan l'operador marra el
    compàs 1, es tria el compàs admissible que deixa el BPM més pròxim al
    primer clip de música (el segon), evitant dobles/meitats. Així, per a un
    pre-roll de 0.742667 s i un segon clip a 147.056 BPM, ix `2/4` a 161.58
    BPM, no un `4/4` a 323 BPM.
    """
    durada = float(durada or 0.0)
    nous = normalitza_trams(trams, durada)
    if len(nous) < 2:
        return nous
    ini, fi, bpm_vell, num_vell, den_vell = nous[0]
    if _es_lliure_tram(nous[0]) or _es_lliure_tram(nous[1]):
        return nous
    if abs(float(fi) - float(offset)) > 1e-3:
        return nous
    dt = float(fi) - float(ini)
    ref = float(nous[1][2])
    if dt <= TOL or ref <= 0:
        return nous
    candidats = []
    for num in range(limits.NUM_MIN, limits.NUM_MAX + 1):
        for den in limits.DENOMINADORS_ADMESOS:
            bq = _bar_quarters(num, den)
            bpm = bq * 60.0 / dt
            if not (BPM_EDIT_MIN - TOL <= bpm <= BPM_EDIT_MAX + TOL):
                continue
            ratio = bpm / ref
            if not (0.5 + 1e-9 < ratio < 2.0 - 1e-9):
                continue
            # A igualtat de BPM, preferix conservar el denominador i després
            # el numerador més simple (2/4 abans que 4/8).
            score = (abs(math.log(ratio)),
                     abs(int(den) - int(den_vell)),
                     abs(int(num) - int(num_vell)),
                     int(num))
            candidats.append((score, bpm, int(num), int(den)))
    if not candidats:
        return nous
    _score, bpm, num, den = min(candidats)
    out = list(nous)
    out[0] = (float(ini), float(fi), float(bpm), int(num), int(den))
    return out


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
    beat = _beat_quarters(den) * 60.0 / bpm
    if t_seg >= durada - TOL:
        t_seg = durada
        nous = abans + [(t, durada, bpm, num, den)]
    elif durada - t_seg < beat - TOL:
        # La cua seria més curta que un beat: el contracte nou la rebutjaria.
        # Absorbim la cua dins del tram confirmat (l'últim final és lliure).
        t_seg = durada
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
    perquè els trams interiors continuen amb beats sencers. Rebutja si no
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


def _enter_mes_proper(x):
    """Enter més pròxim (half-up; `round` fa *banker's* i desconcerta)."""
    return int(math.floor(float(x) + 0.5))


def _base_tram(tram, idx, offset=0.0):
    """Instant on comença a comptar el compàs 1 **dins** del tram.

    Només el PRIMER tram es compta des de l'offset, que pot quedar abans del
    WAV quan s'ha retallat el so anterior al compàs 1. La resta compta des del
    propi inici.
    """
    ini = float(tram[0])
    off = float(offset or 0.0)
    return off if int(idx) == 0 else ini


def _es_lliure_tram(tram):
    """True si el tram va **en segons** (`num`/`den` = 0)."""
    return int(tram[3]) <= 0 or int(tram[4]) <= 0


def valida_i_normalitza_permissiu(trams, durada, offset=0.0):
    """Valida el mapa amb les regles permissives del model (F2).

    - BPM i compàs vàlids (30–350 i 1–12 / 2,4,8,16).
    - Contigüitat i cobertura de tota la WAV.
    - **N enter a tots els clips**, primer i últim inclosos. Si una duració
      deixa `N` fraccionari, s'arrodoneix i es recalcula el BPM.
    - Cap clip més curt que `limits.TEMPS_MIN_CLIP` (1/16 a 350 BPM).
    - Les fronteres poden caure on vulga l'usuari: no s'exigeix beat sencer
      ni línia de graella.
    """
    durada = float(durada or 0.0)
    for i, t in enumerate(trams or ()):
        if durada > 0 and float(t[0]) >= durada - TOL:
            raise ValueError("Hi ha un tram que comença fora de la WAV")
        try:
            valida_tempo(t[2], t[3], t[4])
        except (ValueError, IndexError, TypeError) as e:
            raise ValueError(f"Tram {i + 1}: {e}") from None
    nous = normalitza_trams(trams, durada)
    if not nous:
        raise ValueError("El mapa de tempo/compàs és buit")
    nous, _ns, _avisos = ajusta_compassos_sencers(nous)
    for i, t in enumerate(nous):
        ini, fi = float(t[0]), float(t[1])
        if fi - ini < limits.TEMPS_MIN_CLIP - TOL:
            raise ValueError(
                "El tram %d és més curt que el mínim (%d ms): un compàs "
                "1/16 a 350 BPM"
                % (i + 1, round(limits.TEMPS_MIN_CLIP * 1000)))
    return nous


def problemes_compassos_sencers(trams, durada=0.0, offset=0.0,
                                 tolerancia=1e-3):
    """Llista els clips que no donen un nombre enter de compassos.

    **No hi ha excepció de pre-roll**: el primer clip també ha de tindre `N`
    enter (contracte §13.4). Cada element és un diccionari amb índex, rang,
    BPM, compàs i `N` fraccionari.
    """
    durada = float(durada or 0.0)
    issues = []
    net = normalitza_trams(list(trams or ()), durada)
    for i, tr in enumerate(net):
        ini, fi, bpm, num, den = (float(tr[0]), float(tr[1]), float(tr[2]),
                                  int(tr[3]), int(tr[4]))
        if num <= 0 or den <= 0:
            continue                    # compàs invàlid / tram en segons
        try:
            n = compassos_del_clip(tr)
        except (TypeError, ValueError):
            continue
        if abs(n - round(n)) <= float(tolerancia):
            continue
        issues.append({
            "idx": i,
            "ini": ini,
            "fi": fi,
            "bpm": bpm,
            "num": num,
            "den": den,
            "n": float(n),
        })
    return issues


def _compassos_del_tram(tram, idx, offset=0.0):
    """Compasos (pot ser fraccionari) que conté el tram segons durada i BPM."""
    fi, bpm, num, den = (float(tram[1]), float(tram[2]),
                         int(tram[3]), int(tram[4]))
    b = durada_compas(bpm, num, den)
    if b <= TOL:
        raise ValueError("El compàs té una durada nul·la")
    return (float(fi) - _base_tram(tram, idx, offset)) / b


def compassos_del_clip(tram):
    """`N` d'un clip comptant la seua **duració completa** (`fi − ini`).

    És la magnitud del contracte nou: tots els clips de tempo/compàs han de
    tindre un `N` enter, inclòs el primer (encara que hi haja offset/pre-roll).
    No depén de l'offset: eixe només mou la graella.
    """
    ini, fi, bpm, num, den = (float(tram[0]), float(tram[1]), float(tram[2]),
                              int(tram[3]), int(tram[4]))
    b = durada_compas(bpm, num, den)
    if b <= TOL:
        raise ValueError("El compàs té una durada nul·la")
    return (fi - ini) / b


def ajusta_compassos_sencers(trams, tolerancia=1e-9, estricte=True):
    """Fa que **tots** els clips tinguen `N` enter; retorna `(trams, ns, avisos)`.

    - Si `N` ja és enter (dins `tolerancia`), es conserva el BPM exacte.
    - Si no, s'arrodoneix `N` (mínim 1) i es **recalcula el BPM** perquè la
      duració del clip (fronteres fixes) coincidisca amb eixa xifra.
    - Si cap `N` enter dona un BPM dins 30–350, amb `estricte=True` llança
      `ValueError`; amb `estricte=False` deixa el clip com estava i avisa
      (per a càrregues/refrescos de la GUI: mai un crash, però l'avís és
      visible i `problemes_compassos_sencers` el continuarà detectant).

    No depén de l'offset: el `N` es compta sobre `fi − ini` (contracte §13.4).
    """
    out, ns, avisos = [], [], []
    for i, t in enumerate(trams or ()):
        ini, fi, bpm, num, den = (float(t[0]), float(t[1]), float(t[2]),
                                  int(t[3]), int(t[4]))
        dt = fi - ini
        if dt <= TOL:
            raise ValueError(f"El clip {i + 1} no té durada")
        bq = _bar_quarters(num, den)
        if bq <= TOL:
            raise ValueError(f"El clip {i + 1} té un compàs sense durada")
        n = dt / (bq * 60.0 / bpm)
        n_int = max(1, _enter_mes_proper(n))
        if abs(n - n_int) > float(tolerancia):
            n_min = max(1, int(math.ceil(
                limits.BPM_MIN * dt / (bq * 60.0) - 1e-9)))
            n_max = int(math.floor(
                limits.BPM_MAX * dt / (bq * 60.0) + 1e-9))
            if n_max < n_min:
                if estricte:
                    raise ValueError(
                        f"El clip {i + 1} ({dt:.3f}s) no pot tindre cap N "
                        f"enter a {limits.BPM_MIN:g}–"
                        f"{limits.BPM_MAX:g} BPM")
                avisos.append(
                    f"Clip {i + 1}: {dt:.3f}s no cap en cap N enter a "
                    f"{limits.BPM_MIN:g}–{limits.BPM_MAX:g} BPM; revisa el "
                    "compàs o la frontera")
                out.append((ini, fi, float(bpm), num, den))
                ns.append(float(n))
                continue
            n_int = min(max(n_int, n_min), n_max)
            bpm_new = n_int * bq * 60.0 / dt
            avisos.append(
                f"Clip {i + 1}: N {n:.3f} → {n_int}; "
                f"BPM {bpm:.3f} → {bpm_new:.3f}")
            bpm = bpm_new
        out.append((ini, fi, float(bpm), num, den))
        ns.append(float(n_int))
    return out, ns, avisos


def _valida_bpm_edicio(bpm, costat):
    """Comprova la banda de BPM d'un re-tempo (regla §5 del document)."""
    b = float(bpm)
    if not (BPM_EDIT_MIN - TOL <= b <= BPM_EDIT_MAX + TOL):
        raise ValueError(
            f"El tram {costat} quedaria a {b:.1f} BPM, fora del rang "
            f"{BPM_EDIT_MIN:g}–{BPM_EDIT_MAX:g}")
    return b


def _mapa_valida_sense_moure(out, durada, offset, preserva_fi_idx=None,
                             beats_qm=None):
    """Valida el mapa **sense moure cap frontera**.

    Les operacions de l'usuari (`+`, re-tempo pel ratolí, «Detecta» d'un tram,
    «Ajusta BPMs pels marcadors») fixen elles mateixes les fronteres: el lloc on
    cau el marcador o la nansa és la veritat. El contracte exigix **N enter** i
    almenys un beat sencer; si el resultat no complix, el gest es rebutja amb
    un missatge (no es deixa cap clip fraccionari en silenci).
    """
    return valida_i_normalitza_compassos(
        out, durada, offset, preserva_fi_idx=preserva_fi_idx,
        beats_qm=beats_qm)


def canvia_bpm_local(trams, idx, bpm, durada, offset=0.0, num=None, den=None,
                     beats_qm=None, permissiu=False):
    """Canvia el BPM/compàs d'un tram sense moure fronteres ni veïns.

    Contracte nou (§13.4/§13.5): el clip ha de contindre un **N enter** de
    compassos. El BPM demanat és la referència per triar eixe `N`; el BPM
    final es deriva perquè `N` compassos hi caben exactament. Els veïns no es
    re-tempen ni es desplacen.

    Si `permissiu=True` (TAP, detectors, gestos en viu) s'aplica esta
    normalització; si no, es valida de manera estricta.
    """
    durada = float(durada or 0.0)
    nous = normalitza_trams(trams, durada)
    i = int(idx)
    if not (0 <= i < len(nous)):
        raise ValueError("El tram de tempo no existeix")
    ini, fi, _bpm0, num0, den0 = nous[i]
    bpm, num, den = valida_tempo(
        bpm, num if num is not None else num0,
        den if den is not None else den0)
    out = list(nous)
    out[i] = (float(ini), float(fi), float(bpm), int(num), int(den))
    if permissiu:
        return valida_i_normalitza_permissiu(out, durada, offset)
    out = _millora_signatures_clips(out, durada, offset, beats_qm, {i})
    return _mapa_valida_sense_moure(out, durada, offset,
                                    beats_qm=beats_qm)


def _candidats_fit_clip(tram, i, offset):
    """Candidats (score, bpm, den) per a un clip, sense moure fronteres."""
    ini, fi, bpm0, num, den0 = tram
    dt = float(fi) - (float(offset) if i == 0 else float(ini))
    if dt <= TOL or int(num) <= 0 or int(den0) <= 0:
        return [(0.0, float(bpm0), int(den0))]
    out = [(0.0, float(bpm0), int(den0))]
    for d in limits.DENOMINADORS_ADMESOS:
        bq = _beat_quarters(d)
        n0 = max(1, _enter_mes_proper(dt * float(bpm0) / (bq * 60.0)))
        for n in range(max(1, n0 - 2), n0 + 3):
            bpm = float(n) * bq * 60.0 / dt
            if not (BPM_EDIT_MIN - TOL <= bpm <= BPM_EDIT_MAX + TOL):
                continue
            if not (0.5 + 1e-9 < bpm / float(bpm0) < 2.0 - 1e-9):
                continue
            score = abs(math.log(bpm / float(bpm0))) + 0.02 * abs(
                float(d) - float(den0))
            out.append((score, float(bpm), int(d)))
    # Elimina duplicats exactes i ordena per preferència.
    vist = set()
    unics = []
    for c in sorted(out):
        clau = (round(c[1], 9), c[2])
        if clau in vist:
            continue
        vist.add(clau)
        unics.append(c)
    return unics


def ajusta_bpm_a_compassos(trams, idx, durada, offset=0.0, beats_qm=None):
    """Recalcula el BPM perquè el clip tinga un nombre enter de compassos.

    Acció **explícita** de la GUI (botó «Ajusta BPM al compàs»): conserva les
    fronteres en segons i el compàs, i calcula el BPM que fa que el clip tinga
    `N` compassos sencers, amb `N` el més pròxim possible al BPM actual.
    És l'única via que força compassos sencers; la resta del contracte només
    exigeix un beat sencer.

    El `N` es compta sempre sobre la **duració completa** del clip
    (`fi − ini`); l'offset només mou la graella i no eximeix de compassos
    enters (contracte §13.4).
    """
    durada = float(durada or 0.0)
    nous = normalitza_trams(trams, durada)
    i = int(idx)
    if not (0 <= i < len(nous)):
        raise ValueError("El tram de tempo no existeix")
    ini, fi, bpm, num, den = nous[i]
    dt = float(fi) - float(ini)
    bq = _bar_quarters(int(num), int(den))
    if dt <= TOL or bq <= TOL:
        raise ValueError("El clip no té prou durada per a un compàs")
    n = max(1, _enter_mes_proper(dt * float(bpm) / (bq * 60.0)))
    try:
        res = tempo_recalc.recalculca_tram(
            dt, bpm, int(num), int(den), n_ref=n, mode="graella",
            bloca_compas=True)
    except ValueError as e:
        raise ValueError(f"Amb {n} compàs(s): {e}") from e
    if res is None:
        raise ValueError(
            f"Amb {n} compàs(s), no hi ha cap BPM vàlid entre "
            f"{BPM_EDIT_MIN:g} i {BPM_EDIT_MAX:g}")
    bpm2 = float(res["bpm"])
    out = list(nous)
    out[i] = (float(ini), float(fi), float(bpm2), int(num), int(den))
    return _mapa_valida_sense_moure(out, durada, offset,
                                    beats_qm=beats_qm)


def _millora_signatures_clips(trams, durada, offset=0.0, beats_qm=None,
                               idxs=None):
    """Ajusta compàs i, si cal, BPM perquè els clips tinguen un beat sencer.

    Prioritat 1: conservar el BPM. S'hi proven primers els denominadors
    admissibles; si cap no encaixa, es prova un BPM proper que faça que el clip
    continga un nombre enter de beats. No s'accepten BPM a la meitat ni al
    doble del de referència, ni fora de 30–350.
    """
    out = [tuple(t) for t in (trams or ())]
    if beats_qm:
        return out
    idxs = list(range(len(out))) if idxs is None else sorted(set(idxs))
    idxs = [i for i in idxs
            if 0 <= i < len(out)
            and int(out[i][3]) > 0 and int(out[i][4]) > 0]
    if not idxs:
        return out
    try:
        valida_i_normalitza_compassos(out, durada, offset)
        return out
    except ValueError:
        pass
    # Per a pocs clips afectats (els gestos de frontera en toquen dos) provem
    # les combinacions de candidats; així la frontera compartida pot encaixar
    # en totes dues bandes alhora.
    if len(idxs) <= 3:
        llistes = [_candidats_fit_clip(out[i], i, offset) for i in idxs]
        def _prova(k, actual):
            if k == len(idxs):
                try:
                    valida_i_normalitza_compassos(actual, durada, offset)
                except ValueError:
                    return None
                return actual
            i = idxs[k]
            bpm0, den0 = float(actual[i][2]), int(actual[i][4])
            for _score, bpm, den in llistes[k]:
                # No repetir el valor actual en bucle.
                if abs(bpm - bpm0) <= TOL and int(den) == den0:
                    cand = actual
                else:
                    cand = list(actual)
                    ini, fi, _b, num, _d = actual[i]
                    cand[i] = (ini, fi, bpm, num, den)
                res = _prova(k + 1, cand)
                if res is not None:
                    return res
            return None
        res = _prova(0, out)
        if res is not None:
            return res
    return out


def parteix_tram_marcador(trams, t, durada, offset=0.0, bpm_ref=None,
                          beats_qm=None, permissiu=False, recalculca=False,
                          ref_base=None, avisos=None, beat_factor=1.0):
    """Parteix el mapa a `t` conservant BPM i compàs com a referència.

    Contracte nou (§13.4): **les dos parts han de tindre `N` enter**. El
    marcador obri dos clips; si amb el BPM/compàs heretats queden fraccionaris,
    el camí permissiu arrodoneix `N` i recalcula el BPM de cada part. El camí
    estricte rebutja el tall si no pot quadrar.

    `bpm_ref` es conserva per compatibilitat d'API, però no decidix el BPM.
    `t` ha de vindre ja encaixat al beat QM pel camí del `+`.
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
        bpm, num, den = float(s[2]), int(s[3]), int(s[4])
        out = list(net)
        out[i:i + 1] = [(ini, t, bpm, num, den),
                        (t, fi, bpm, num, den)]
        if permissiu:
            if recalculca:
                out = _recalcula_costats(out, [(i, s), (i + 1, s)],
                                         durada, offset, beats_qm=beats_qm,
                                         ref_base=ref_base, avisos=avisos,
                                         beat_factor=beat_factor)
            return valida_i_normalitza_permissiu(out, durada, offset)
        out = _millora_signatures_clips(out, durada, offset, beats_qm,
                                        {i, i + 1})
        return _mapa_valida_sense_moure(out, durada, offset,
                                        beats_qm=beats_qm)
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
    try:
        res = tempo_recalc.recalculca_tram(
            dt, bpm_det, int(num), int(den), n_ref=n, mode="graella",
            bloca_compas=True)
    except ValueError as e:
        raise ValueError(f"BPM detectat: {e}") from e
    if res is None:
        raise ValueError(
            f"El BPM detectat no dona cap valor vàlid per a {n} compàs(s)")
    bpm_final = _valida_bpm_edicio(float(res["bpm"]), "detectat")
    out = list(nous)
    out[i] = (float(ini), float(fi), bpm_final, int(num), int(den))
    return _mapa_valida_sense_moure(out, durada, offset)


def _bpm_per_beats(dt, ref, den):
    """BPM que fa que `dt` siga un nombre enter de beats, prop de `ref`."""
    dt = float(dt)
    bq = _beat_quarters(int(den))
    ref = float(ref)
    if dt <= TOL or bq <= TOL or ref <= 0:
        return ref
    n = max(1, _enter_mes_proper(dt * ref / (bq * 60.0)))
    bpm = n * bq * 60.0 / dt
    if not (BPM_EDIT_MIN - TOL <= bpm <= BPM_EDIT_MAX + TOL):
        return ref
    if not (0.5 + 1e-9 < bpm / ref < 2.0 - 1e-9):
        return ref
    return bpm


def ajusta_trams_a_marcadors(trams, marcadors, durada, offset=None,
                             referencies=None, beats_qm=None):
    """Mapa amb un clip per interval entre marcadors, amb `N` enter.

    Contracte nou: cada interval conserva el **BPM de referència** (prioritat
    1) i el compàs vigent, però tots els clips —també el «cap» `0 → t_0` i la
    «cua» `t_últim → durada`— han de quedar amb un nombre enter de compassos.
    Si cal, s'arrodoneix `N` i es recalcula el BPM. Si `offset` és `None`, es
    pren el primer marcador; si s'indica, es conserva eixe offset.
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
        ref = min(max(ref, BPM_EDIT_MIN), BPM_EDIT_MAX)
        num, den = mapa.signatura(float(a) + TOL)
        bpm = _bpm_per_beats(dt, ref, int(den))
        intervals.append((float(a), float(b), float(bpm), int(num), int(den)))
    if not intervals:
        raise ValueError("Els marcadors no defineixen cap interval")
    num0, den0 = mapa.signatura(0.0)
    bpm0 = _bpm_per_beats(float(ms[0]), intervals[0][2], int(den0))
    out = [(0.0, float(ms[0]), float(bpm0), int(num0), int(den0))]
    out.extend(intervals)
    num_f, den_f = mapa.signatura(float(ms[-1]) - TOL)
    dt_f = float(durada) - float(ms[-1])
    bpm_f = _bpm_per_beats(dt_f, intervals[-1][2], int(den_f))
    out.append((float(ms[-1]), durada, float(bpm_f),
                int(num_f), int(den_f)))
    out = _millora_signatures_clips(out, durada, off, beats_qm)
    out, _ns, _avisos = ajusta_compassos_sencers(out)
    return _mapa_valida_sense_moure(out, durada, off, beats_qm=beats_qm)


def mou_frontera_retempo(trams, idx_frontera, nou_t, durada, offset=0.0,
                         beats_qm=None, permissiu=False, ref_base=None,
                         avisos=None, beat_factor=1.0):
    """Mou una frontera interior.

    Dos camins:

    - **permissiu=True** (GUI): el punter fixa els segons; cada costat conserva
      el seu BPM/compàs com a referència i `recalculca_tram` busca un **`N`
      enter** de compassos. Pot canviar BPM, compàs o `N`. Si no hi ha solució,
      es queda el valor anterior.
    - **permissiu=False** (compatibilitat/detectors): conserva BPM i compàs
      com a referència, però al final ajusta `N`/BPM perquè tots dos costats
      tinguen compassos sencers.

    `idx_frontera` és l'índex del tram de la DRETA (la frontera és el seu
    inici); el tram de l'esquerra és `idx_frontera - 1`.
    """
    durada = float(durada or 0.0)
    nous = normalitza_trams(trams, durada)
    i = int(idx_frontera)
    if not (0 < i < len(nous)):
        raise ValueError("No hi ha cap frontera interior per a moure")
    a, b = nous[i - 1], nous[i]
    ini_a, fi_b = float(a[0]), float(b[1])
    minim = ini_a + TOL
    if (i - 1) == 0 and float(offset or 0.0) > ini_a + TOL:
        minim = max(minim, float(offset or 0.0))
    maxim = fi_b - TOL
    if maxim <= minim:
        raise ValueError("Els trams són massa curts per a moure la frontera")
    t = float(nou_t)
    if ((i - 1) == 0 and float(offset or 0.0) > ini_a + TOL
            and t < float(offset) - TOL):
        raise ValueError("La frontera no pot quedar abans del compàs 1")
    if t <= ini_a + TOL:
        raise ValueError("La frontera deixaria el tram esquerre sense durada")
    if t >= fi_b - TOL:
        raise ValueError("La frontera deixaria el tram dret sense durada")
    t = min(maxim, max(minim, t))

    out = list(nous)
    out[i - 1] = (float(ini_a), float(t), float(a[2]), int(a[3]), int(a[4]))
    out[i] = (float(t), float(fi_b), float(b[2]), int(b[3]), int(b[4]))
    if permissiu:
        beats = [float(x) for x in (beats_qm or ())]
        abans = None
        if beats:
            abans = (
                tempo_recalc.n_negres_del_clip(
                    beats, a[0], a[1], beat_factor,
                    tol=tempo_recalc.TOL_BEATS),
                tempo_recalc.n_negres_del_clip(
                    beats, b[0], b[1], beat_factor,
                    tol=tempo_recalc.TOL_BEATS))
        out = _recalcula_costats(out, [(i - 1, a), (i, b)],
                                 durada, offset, beats_qm=beats_qm,
                                 ref_base=ref_base, avisos=avisos,
                                 beat_factor=beat_factor)
        if abans is not None and avisos is not None:
            ara = (
                tempo_recalc.n_negres_del_clip(
                    beats, out[i - 1][0], out[i - 1][1], beat_factor,
                    tol=tempo_recalc.TOL_BEATS),
                tempo_recalc.n_negres_del_clip(
                    beats, out[i][0], out[i][1], beat_factor,
                    tol=tempo_recalc.TOL_BEATS))
            if ara != abans and any(
                    0.0 < abs(float(x) - t) <= tempo_recalc.TOL_TALL
                    for x in beats):
                text = (
                    f"Frontera {t:.3f}s: el recompte exacte de beats ha "
                    f"canviat ({abans[0]}→{ara[0]} / {abans[1]}→{ara[1]}); "
                    "s'ha estabilitzat amb la tolerància de 50 ms; revisa "
                    "el tall o activa snap")
                if text not in avisos:
                    avisos.append(text)
        return valida_i_normalitza_permissiu(out, durada, offset)
    out = _millora_signatures_clips(out, durada, offset, beats_qm,
                                    {i - 1, i})
    out, _ns, _avisos = ajusta_compassos_sencers(out)
    return _mapa_valida_sense_moure(out, durada, offset,
                                    beats_qm=beats_qm)


def _recalcula_costats(out, refs, durada, offset=0.0, beats_qm=None,
                       ref_base=None, avisos=None, beat_factor=1.0):
    """Recalcula BPM/compàs dels costats amb una referència.

    `refs`: `[(idx, tram_referencia), …]`. Si `ref_base=(bpm, num, den)` no és
    `None`, **tots** els costats usen eixa referència manual (BPM/compàs base
    del tema); si no, cada costat conserva la referència del seu clip. S'ometen
    els rubatos, el pre-roll del primer clip i els trams on no hi ha cap
    combinació vàlida. Si hi ha beats detectats dins del clip, el seu nombre
    restringix `N` i el compàs (i poden corregir la referència base).
    """
    beats = [float(b) for b in (beats_qm or ())]
    for idx, ref in refs:
        if not (0 <= idx < len(out)) or _es_lliure_tram(out[idx]):
            continue
        ini, fi = float(out[idx][0]), float(out[idx][1])
        if int(idx) == 0 and float(offset) > ini + TOL:
            continue                     # pre-roll: el clip no és musical
        n_beats = tempo_recalc.n_negres_del_clip(
            beats, ini, fi, beat_factor, tol=tempo_recalc.TOL_TALL) if beats else None
        if avisos is not None and beats:
            for b in tempo_recalc.beats_a_la_frontera(
                    beats, ini, fi, tol=tempo_recalc.TOL_TALL):
                x = ini if abs(b - ini) <= abs(b - fi) else fi
                text = (
                    f"Frontera {x:.3f}s: beat a {b:.3f}s dins la tolerància "
                    f"de {tempo_recalc.TOL_TALL * 1000:.0f} ms; recompte "
                    "ambigu (activa snap o ajusta el tall)")
                if text not in avisos:
                    avisos.append(text)
        if ref_base is None:
            bpm_ref, num_ref, den_ref = ref[2], ref[3], ref[4]
        else:
            bpm_ref, num_ref, den_ref = ref_base
        try:
            r = tempo_recalc.recalculca_tram(
                fi - ini, bpm_ref, num_ref, den_ref, n_beats=n_beats,
                pas_beat=beat_factor)
        except (TypeError, ValueError):
            if ref_base is None:
                raise
            # Referència base heretada/invàlida: no bloquegem el gest.
            r = tempo_recalc.recalculca_tram(
                fi - ini, ref[2], ref[3], ref[4], n_beats=n_beats,
                pas_beat=beat_factor)
        if r is None:
            continue
        if avisos is not None:
            text = tempo_recalc.avis_de_resultat(r)
            if text:
                avisos.append(
                    f"Clip {int(idx) + 1} ({float(ini):.3f}s): {text}")
        out[idx] = (ini, fi, float(r["bpm"]), int(r["num"]), int(r["den"]))
    return out


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

    El pre-roll és el clip `0 → offset` (el compàs 1 cau a la seua fi). No es
    decidix pel nombre de compassos: el primer clip també ha de tindre `N`
    enter (§13.4), però això no el convertix en música.
    """
    i = int(idx_frontera)
    # Només la frontera 0→1 és el pre-roll. Abans qualsevol frontera amb un
    # primer tram sense cap compàs es tractava com a «Compàs 1», i per això
    # les fronteres 2–3, 3–4… es rebutjaven com si foren l'offset.
    if i != 1 or not (0 < i < len(trams or ())):
        return False
    off = float(offset or 0.0)
    if off <= float(trams[0][0]) + TOL or _es_lliure_tram(trams[0]):
        return False
    return es_preroll_tram(trams, 0, off)


def mou_frontera_preroll(trams, idx_frontera, nou_offset, durada, offset=0.0):
    """Arrossegar la frontera del **pre-roll** = moure el **compàs 1**.

    Canvia l'`offset`; el primer clip (`0 → offset`) i el de música conserven
    `N` enter i recalculen el BPM si la nova duració ho exigix. És el que fa
    📍, però arrossegant el tall.

    Retorna `(trams, nou_offset)`.
    """
    durada = float(durada or 0.0)
    nous = normalitza_trams(trams, durada)
    i = int(idx_frontera)
    if i != 1 or not (0 < i < len(nous)):
        raise ValueError("No hi ha cap frontera de pre-roll per a moure")
    off = float(nou_offset)
    ini_a = float(nous[0][0])
    fi_b = float(nous[i][1])
    if off <= ini_a + TOL:
        raise ValueError("El compàs 1 no pot quedar a l'inici de la WAV")
    if off >= fi_b - TOL:
        raise ValueError("El compàs 1 quedaria més enllà del tram de música")
    b = nous[i]
    n_b = max(1, _enter_mes_proper(compassos_del_clip(b)))
    bq_b = _bar_quarters(int(b[3]), int(b[4]))
    bpm_b = _bpm_de_n(n_b, bq_b, fi_b - off)
    out = list(nous)
    out[0] = (ini_a, off, float(nous[0][2]), int(nous[0][3]), int(nous[0][4]))
    out[i] = (off, fi_b, bpm_b, int(b[3]), int(b[4]))
    # Contracte §13.4: el primer clip (0 → offset) també ha de tindre N enter;
    # s'ajusta el seu BPM si cal. El segon ja s'ha recalculat amb N enter.
    out, _ns, _avisos = ajusta_compassos_sencers(out)
    return _mapa_valida_sense_moure(out, durada, off), off


def canvia_compassos_tram(trams, idx, delta_compassos=0, durada=0.0,
                          offset=0.0, factor=None, n_new=None,
                          num=None, den=None, permissiu=False):
    """Reinterpreta el tram `idx` amb més/menys compassos, **sense moure'l**.

    Els segons (`ini`, `fi`) queden intactes, els veïns no es toquen i el BPM
    es recalcula perquè `N` compassos hi caben: és una reinterpretació mètrica
    interna del bloc (8 s amb 4 compassos a 60 BPM → ×2 = 8 compassos a 120).

    - `delta_compassos`: suma algebraica (+1, −1…).
    - `factor`: multiplica N (2 = ×2, 0.5 = ÷2), arredonit a l'enter més pròxim.
    - `n_new`: fixa directament el nombre de compassos (camp «N compassos»).
    - `num`/`den`: compàs nou opcional; si no, es conserva el del clip.

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
    ini, fi, _bpm, num0, den0 = nous[i]
    dt = float(fi) - float(ini)
    if dt <= TOL:
        raise ValueError("El tram no té durada")
    n_act = _enter_mes_proper(max(1.0, compassos_del_clip(nous[i])))
    if n_new is not None:
        n_final = int(n_new)
    elif factor is not None:
        f = float(factor)
        if f <= 0:
            raise ValueError("El factor de compassos ha de ser positiu")
        n_final = _enter_mes_proper(n_act * f)
    else:
        n_final = n_act + int(delta_compassos)
    if n_final < 1:
        raise ValueError("El tram ha de tindre com a mínim un compàs")
    num_final = int(num) if num is not None else int(num0)
    den_final = int(den) if den is not None else int(den0)
    if n_final == n_act and (num_final, den_final) == (int(num0), int(den0)):
        return nous
    try:
        res = tempo_recalc.recalculca_tram(
            dt, _bpm, int(num_final), int(den_final), n_ref=n_final,
            mode="graella", bloca_compas=True)
    except ValueError as e:
        raise ValueError(f"Compàs triat: {e}") from e
    if res is None:
        raise ValueError("El compàs triat no dona cap BPM vàlid")
    bpm_new = _valida_bpm_edicio(float(res["bpm"]), "triat")
    bpm_new, num_final, den_final = valida_tempo(
        bpm_new, num_final, den_final)
    out = list(nous)
    out[i] = (float(ini), float(fi), float(bpm_new),
              int(num_final), int(den_final))
    if permissiu:
        return valida_i_normalitza_permissiu(out, durada, offset)
    return valida_i_normalitza_compassos(out, durada, offset, preserva_fi_idx=i)


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

    Tres mesures del mateix tram:

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
