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


def _bar_quarters(num, den):
    """Negres que fa un compàs `num/den` (4/4→4, 3/4→3, 6/8→3, 12/8→6)."""
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
            if den <= 0:
                den = 4
            if num <= 0:
                num = 4
            trams.append(Tram(ini, fi, bpm if bpm > 0 else 120.0, num, den))
        trams.sort(key=lambda x: x.ini)
        if trams and trams[0].ini > TOL:
            s0 = trams[0]
            trams.insert(0, Tram(0.0, s0.ini, s0.bpm, s0.num, s0.den))
        if not trams:
            trams = [self._DEFECTE]
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
        """`(num, den)` del compàs a `t`."""
        s = self.tram(t)
        return (s.num, s.den)

    def es_constant(self):
        """True si tots els trossos comparteixen tempo i compàs.

        És el **punt de sortida ràpid**: quan el mapa és constant, tota l'app pot
        fer servir la seua via uniforme de sempre (idèntica) i el mapa només
        serveix per a la persistència.
        """
        if not self._trams:
            return True
        s0 = self._trams[0]
        return all(abs(s.bpm - s0.bpm) < 1e-9 and s.num == s0.num
                   and s.den == s0.den for s in self._trams)

    def durations(self, t):
        """`(compàs_s, temps_s, mitja_negra_s)` de durada a l'instant `t`."""
        s = self.tram(t)
        beat = _beat_quarters(s.den) * 60.0 / s.bpm
        return (_bar_quarters(s.num, s.den) * 60.0 / s.bpm, beat, beat / 2.0)

    def grid_lines(self, t0, t1, kind="bar", n=1, frac=None):
        """Temps de les línies de graella de `kind` dins `[t0, t1]` (mapa-aware).

        `kind`: `"bar"` (cada `n` compassos), `"beat"` (temps) o `"sub"`
        (fracció de temps). `frac` permet graelles de treset (1/3, 2/3, 1/6)
        o qualsevol altra subdivisió; si no es passa, 0,5 per a `"sub"` i 1,0
        per a `"beat"`. Les línies són **musicals** (bar/beat), per tant el seu
        espaiat en segons varia amb el mapa.
        """
        t0, t1 = float(t0), float(t1)
        talls = self._talls_de_compas()
        out = []
        if kind == "bar":
            pas = max(1, int(n))
            for k, tall in enumerate(talls):
                if k % pas == 0 and t0 - TOL <= tall[1] <= t1 + TOL:
                    out.append(tall[1])
            return out
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
                    return out
                if t >= t0 - TOL:
                    out.append(t)
                j += 1
        return out

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
            if (s.num, s.den) != sig:
                return float(s.ini), (s.num, s.den)
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
        sig = (s.num, s.den)
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
            sig_next = (s_next.num, s_next.den)
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
            bq = _bar_quarters(s.num, s.den)
            compas = int((q + TOL) // bq) + 1        # ≤ 0
            q_ini = (compas - 1) * bq
            num, den = s.num, s.den
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
        """Etiqueta `compàs.temps.subdivisió` (mateixa forma que `pos_compas`)."""
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
def normalitza_trams(trams, durada):
    """Ordena i fa **contigus** els trossos, cobrint `[0, durada]`.

    Cada tros és `(ini, fi, bpm, num, den)`; el `fi` es **re-deriva** de l'inici
    del següent (o de `durada` per a l'últim). Descarta inicis repetits o fora
    del tema. No muta l'entrada.
    """
    durada = float(durada or 0.0)
    net, vists = [], set()
    for t in sorted(trams or (), key=lambda x: float(x[0])):
        # Regla d'or #8 (temps vàlids): cap inici negatiu ni cap valor
        # impossible. Si n'arriba algun (CSV editat a mà, projecte vell, client
        # es PORTA AL VALOR VÀLID en comptes de propagar-lo.
        ini = max(0.0, float(t[0]))
        if durada > 0 and ini >= durada - TOL:
            continue
        clau = round(ini, 6)
        if clau in vists:
            continue
        vists.add(clau)
        bpm = float(t[2])
        num, den = int(t[3]), int(t[4])
        net.append((ini, bpm if bpm > 0 else BPM_DEFECTE,
                    num if num > 0 else 4, den if den > 0 else 4))
    if not net:
        return []
    out = []
    for i, t in enumerate(net):
        fi = net[i + 1][0] if i + 1 < len(net) else durada
        out.append((t[0], fi, t[1], t[2], t[3]))
    if out[0][0] > TOL:
        out.insert(0, (0.0, out[0][0], out[0][2], out[0][3], out[0][4]))
    return out


# --- contracte de COMPASSOS ENTERS (docs/REGLES_TEMPS_GRID.md) -------------
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
    for i in range(1, len(nous)):
        t = float(nous[i][0])
        if not _es_bar(t):
            raise ValueError(
                f"La frontera {t:.6f}s no cau en una línia de compàs")
    # El primer tram: el tros posterior a la primera línia de compàs (l'offset,
    # si cau dins del tram) ha de ser un nombre enter de compassos. El tros
    # anterior a l'offset és l'única part parcial permesa al començament.
    ini0, fi0, bpm0, num0, den0 = nous[0]
    b0 = durada_compas(bpm0, num0, den0)
    if b0 <= TOL:
        raise ValueError("El primer tram té un compàs de durada nul·la")
    base0 = float(offset) if float(offset) > float(ini0) + TOL else float(ini0)
    bars0 = (float(fi0) - base0) / b0
    if base0 <= float(ini0) + TOL and bars0 < 1.0 - 1e-5:
        raise ValueError(
            "El primer tram ha d'acabar com a mínim al primer compàs sencer")
    if bars0 < -1e-5 or abs(bars0 - round(bars0)) > 1e-5:
        raise ValueError(
            "El primer tram no acaba en una línia de compàs "
            f"({bars0:.3f} compassos des del compàs 1)")
    # Els trams interiors (ni el primer ni l'últim) han de ser enters.
    for i in range(1, len(nous) - 1):
        ini, fi, bpm, num, den = nous[i]
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


def canvia_bpm_compassos(trams, idx, bpm, durada, offset=0.0,
                         num=None, den=None):
    """Canvia BPM/compàs conservant els compassos del tram (opció A).

    - Tram interior: conserva el nombre enter de compassos i mou la seua fi.
    - Primer tram: conserva els compassos des de l'offset (o des de 0) fins a
      la fi; el tros de compte enrere inicial és l'excepció.
    - Últim tram: com que la fi de la WAV no es mou, pot canviar el nombre de
      compassos (excepció).
    - Els trams següents s'arrosseguen; l'últim absorbeix.
    """
    durada = float(durada or 0.0)
    nous = normalitza_trams(trams, durada)
    if not (0 <= int(idx) < len(nous)):
        raise ValueError("El tram de tempo no existeix")
    idx = int(idx)
    ini, fi, bpm0, num0, den0 = nous[idx]
    bpm = float(bpm)
    num = int(num if num is not None else num0)
    den = int(den if den is not None else den0)
    if bpm <= 0 or num <= 0 or den <= 0:
        raise ValueError("BPM o compàs no vàlid")
    b_old = durada_compas(bpm0, num0, den0)
    b_new = durada_compas(bpm, num, den)
    if b_old <= TOL or b_new <= TOL:
        raise ValueError("El compàs té una durada nul·la")

    if idx == len(nous) - 1:
        # Últim tram: la fi de la WAV mana; pot canviar el nombre de compassos.
        out = list(nous)
        out[idx] = (ini, fi, bpm, num, den)
        return valida_i_normalitza_compassos(out, durada, offset)

    if idx == 0:
        base = float(offset) if float(offset) > float(ini) + TOL else float(ini)
        n = int(round((float(fi) - base) / b_old))
        if base <= float(ini) + TOL and n < 1:
            raise ValueError("El primer tram ha de tindre almenys un compàs")
        if n < 0:
            raise ValueError("El tram no pot acabar abans del compàs 1")
        nou_fi = base + n * b_new
    else:
        n = int(round((float(fi) - float(ini)) / b_old))
        if n < 1:
            raise ValueError("El tram ha de tindre almenys un compàs")
        nou_fi = float(ini) + n * b_new

    if nou_fi <= float(ini) + TOL or nou_fi >= durada - TOL:
        raise ValueError("El canvi no cap dins de la WAV")

    out = _ripple_des_de(nous, idx, nou_fi, durada)
    for j in range(idx + 1, len(out)):
        s = float(out[j][0])
        if s < -TOL or s >= durada - TOL:
            raise ValueError("El canvi no cap dins de la WAV")
    out[idx] = (float(ini), float(nou_fi), bpm, num, den)
    return valida_i_normalitza_compassos(out, durada, offset)


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


# --- Re-tempo: el RATOLÍ mana sobre el temps (docs/FLUX DE TEMPO VARIABLE.md) --
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


def mou_frontera_retempo(trams, idx_frontera, nou_t, durada, offset=0.0):
    """Mou una frontera **interior** conservant els compassos dels dos costats.

    Inverteix la jerarquia (docs/FLUX DE TEMPO VARIABLE.md §2): el ratolí fixa
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
    # Límit físic: ni enganxar-se a l'inici del tram esquerre ni al fi del dret.
    minim = ini_a + FRONTERA_MIN_S
    if (i - 1) == 0 and float(offset or 0.0) > ini_a + TOL:
        # El primer tram pot tindre pre-música: el compàs 1 no es pot travessar.
        minim = max(minim, float(offset) + FRONTERA_MIN_S)
    maxim = fi_b - FRONTERA_MIN_S
    if maxim <= minim:
        raise ValueError("Els trams són massa curts per a moure la frontera")
    t = float(nou_t)
    if t < minim - TOL:
        raise ValueError(
            f"La frontera no pot quedar a menys de {FRONTERA_MIN_S:g} s de "
            "l'inici del tram")
    if t > maxim + TOL:
        raise ValueError(
            f"La frontera no pot quedar a menys de {FRONTERA_MIN_S:g} s del "
            "final del tram")
    t = min(maxim, max(minim, t))

    # N de cada costat: el que JA té (el mapa vàlid té compassos enters).
    n_a = max(1, _enter_mes_proper(_compassos_del_tram(a, i - 1, offset)))
    n_b = max(1, _enter_mes_proper(_compassos_del_tram(b, i, offset)))
    bq_a = _bar_quarters(int(a[3]), int(a[4]))
    bq_b = _bar_quarters(int(b[3]), int(b[4]))
    dt_a = t - _base_tram(a, i - 1, offset)
    # El tram de la dreta comença EXACTAMENT a la frontera (i > 0 → sense offset).
    dt_b = fi_b - t
    if dt_a <= TOL or dt_b <= TOL:
        raise ValueError("La frontera deixaria un tram sense durada")
    bpm_a = _valida_bpm_edicio(n_a * bq_a * 60.0 / dt_a, "esquerre")
    bpm_b = _valida_bpm_edicio(n_b * bq_b * 60.0 / dt_b, "dret")

    out = list(nous)
    out[i - 1] = (ini_a, t, bpm_a, int(a[3]), int(a[4]))
    out[i] = (t, fi_b, bpm_b, int(b[3]), int(b[4]))
    return valida_i_normalitza_compassos(out, durada, offset)


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
    out = normalitza_trams(trams, durada)
    if len(out) <= 1:
        return out
    error = None
    for _ in range(2 * len(out) + 2):
        try:
            return valida_i_normalitza_compassos(out, durada, offset)
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
    raise error if error is not None else ValueError("Mapa de tempo invàlid")


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
