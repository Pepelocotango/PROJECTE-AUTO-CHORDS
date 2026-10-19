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
a `docs/PLA_TEMPO_COMPAS.md`.
"""
from __future__ import annotations

from collections import namedtuple

# Tolerància temporal (evita falsos positius de coma flotant).
TOL = 1e-9
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

    def grid_lines(self, t0, t1, kind="bar", n=1):
        """Temps de les línies de graella de `kind` dins `[t0, t1]` (mapa-aware).

        `kind`: `"bar"` (cada `n` compassos), `"beat"` (temps) o `"sub"`
        (mitja negra). Les línies són **musicals** (bar/beat), per tant el seu
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
        frac = 0.5 if kind == "sub" else 1.0
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
    def _talls_de_compas(self):
        """`[(q_ini, t_ini, num, den), …]` — inici de cada compàs des de l'origen.

        Els **canvis de compàs** arrenquen un compàs nou encara que caiguen a
        mig (com als DAWs: el canvi de compàs implica frontera de compàs).
        """
        talls = [(0.0, float(self._offset), self.tram(self._offset).num,
                  self.tram(self._offset).den)]
        i = self._index(self._offset)
        q = 0.0
        t = self._offset
        limit = 100000                     # salvavides
        while i < len(self._trams) and limit > 0:
            limit -= 1
            s = self._trams[i]
            bq = _bar_quarters(s.num, s.den)
            q_fi_tram = q + (s.fi - t) * s.bpm / 60.0
            q_bar = q + bq
            if q_bar <= q_fi_tram + TOL:
                t_bar = self.t_de_quarters(q_bar)
                talls.append((q_bar, t_bar, s.num, s.den))
                q, t = q_bar, t_bar
            else:
                # canvia de compàs/tempo abans d'acabar el compàs → nou compàs
                if i + 1 < len(self._trams):
                    q, t = q_fi_tram, s.fi
                    nxt = self._trams[i + 1]
                    talls.append((q, t, nxt.num, nxt.den))
                    i += 1
                    continue
                break
            if abs(t - s.fi) <= TOL and i + 1 < len(self._trams):
                i += 1
        return talls

    def pos(self, t):
        """`(compàs, temps, subdivisió)` d'un instant.

        El **compàs 1** és a l'offset; abans seu la numeració és ≤ 0 (compte
        enrere). `subdivisió` és 1 o 3 (les dues meitats del temps), com a l'app.
        """
        t = float(t)
        q = self.quarters(t)
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
        sub = 1 + 2 * int(frac * 2 + TOL)
        return (compas, max(1, min(num, b + 1)), min(3, sub))

    def label(self, t):
        """Etiqueta `compàs.temps.subdivisió` (mateixa forma que `pos_compas`)."""
        c, b, s = self.pos(t)
        return "%d.%d.%d" % (c, b, s)

    def t_de_pos(self, compas, temps=1):
        """Instant del compàs/temps indicat (inversa parcial de `pos`)."""
        s = self.tram(self._offset)
        bq = _bar_quarters(s.num, s.den)
        beat_q = _beat_quarters(s.den)
        q = (int(compas) - 1) * bq + (int(temps) - 1) * beat_q
        return self.t_de_quarters(q)

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
