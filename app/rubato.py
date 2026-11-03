"""Derivació mètrica dels clips de rubato (subplà de rubato, fase 1).

Aquest mòdul és **pur**: no toca Qt, ni el projecte, ni el disc. Rep la durada
d'un rubato i el tempo/compàs de referència, i calcula:

- el **nombre de negres** enteres que més s'aproxima a la referència;
- el **BPM derivat** (negres per minut) que fa coincidir eixes negres amb la
  durada;
- una **seqüència de compassos** (fins a 4 segments) que suma exactament eixes
  negres.

El BPM és sempre **en negres per minut**, com `app/tempo_map.py` i el
metrònomo. Per això es poden barrejar denominadors dins d'un rubato
(`4/4*2+6/8`): cada compàs aporta `num·4/den` negres.

Els segons són la veritat: este mòdul només construeix la representació
mètrica derivada. Si no hi ha cap solució dins del contracte (BPM 30–350,
compassos estàndard, màxim 4 segments), aixeca `RubatoError`.

Decisions de disseny: `00PER FER/DECISIONS_RUBATO.md`.
"""

from dataclasses import dataclass
import math
import re

from app import limits

#: Compassos estàndard per a la seqüència: `(numerador, denominador)`.
ESTANDARDS = (
    (2, 4), (3, 4), (4, 4), (5, 4), (6, 4), (7, 4),
    (3, 8), (6, 8), (9, 8), (12, 8),
    (2, 2), (3, 2), (4, 2),
)

#: Màxim de segments de compàs dins d'un rubato.
MAX_SEGMENTS = 4

#: Límit intern de seguretat (bars) per a un rubato.
MAX_BARS = 999

#: Límit de nodes de la cerca exhaustiva de la resta (evita casos patològics).
MAX_NODES = 500_000

_RE_SEGMENT = re.compile(r"^(\d{1,2})/(\d{1,2})(?:\*(\d{1,3}))?$")


class RubatoError(ValueError):
    """No es pot construir una representació mètrica vàlida."""


@dataclass(frozen=True)
class Derivacio:
    """Resultat de la derivació d'un rubato."""

    bpm: float
    den: int
    compassos: str
    pulsos: int
    segments: tuple
    ref_bpm: float
    ref_num: int
    ref_den: int

    @property
    def quarters(self):
        """Negres totals de la seqüència."""
        return sum(num * 4.0 / den * count
                   for num, den, count in self.segments)


def _pes(num, den):
    """Negres × 2 (octaves) que fa un compàs `num/den`; enter per a 2/4/8."""
    return int(num) * 8 // int(den)


def _valida_referencia(bpm, num, den):
    try:
        bpm = float(bpm)
        num_f = float(num)
        den_f = float(den)
    except (TypeError, ValueError) as e:
        raise RubatoError("La referència del rubato no és numèrica") from e
    if not math.isfinite(bpm):
        raise RubatoError("El BPM de referència no és un nombre finit")
    if not limits.BPM_MIN <= bpm <= limits.BPM_MAX:
        raise RubatoError(
            f"El BPM de referència ha d'estar entre {limits.BPM_MIN:g} i "
            f"{limits.BPM_MAX:g}")
    if not num_f.is_integer() or not den_f.is_integer():
        raise RubatoError("El compàs de referència ha de ser enter")
    num, den = int(num_f), int(den_f)
    if den not in (2, 4, 8):
        raise RubatoError("El denominador de referència ha de ser 2, 4 o 8")
    if not limits.NUM_MIN <= num <= limits.NUM_MAX:
        raise RubatoError(
            f"El numerador de referència ha d'estar entre "
            f"{limits.NUM_MIN} i {limits.NUM_MAX}")
    return bpm, num, den


def _tria_pulsos(durada, bpm_ref):
    """Nombre enter de negres dins de 30–350, el més pròxim a la referència."""
    if not math.isfinite(durada) or durada <= 0:
        raise RubatoError("La durada del rubato ha de ser positiva")
    ideal = durada * bpm_ref / 60.0
    n_min = max(1, int(math.ceil(durada * limits.BPM_MIN / 60.0 - 1e-9)))
    n_max = int(math.floor(durada * limits.BPM_MAX / 60.0 + 1e-9))
    if n_max < n_min:
        raise RubatoError(
            "La durada del rubato no permet cap BPM entre "
            f"{limits.BPM_MIN:g} i {limits.BPM_MAX:g}")
    n = int(math.floor(ideal + 0.5))          # arrodoniment mig cap amunt
    n = min(max(n, n_min), n_max)
    bpm = n * 60.0 / durada
    if bpm < limits.BPM_MIN - 1e-9:
        n += 1
        bpm = n * 60.0 / durada
    elif bpm > limits.BPM_MAX + 1e-9:
        n -= 1
        bpm = n * 60.0 / durada
    if not (limits.BPM_MIN - 1e-9 <= bpm <= limits.BPM_MAX + 1e-9):
        raise RubatoError(
            "No hi ha cap nombre enter de negres dins de la banda de BPM")
    bpm = min(max(bpm, limits.BPM_MIN), limits.BPM_MAX)
    return n, bpm


def _fusiona(segments):
    """Fusiona segments adjacents del mateix compàs."""
    out = []
    for num, den, count in segments:
        if count <= 0:
            continue
        if out and out[-1][0] == num and out[-1][1] == den:
            out[-1] = (num, den, out[-1][2] + count)
        else:
            out.append((num, den, count))
    return out


def _millor_resta(rest, max_parts, ref_num, ref_den, max_bars=MAX_BARS,
                  nodes=None):
    """Millor combinació de fins a `max_parts` compassos que suma `rest`.

    `rest` i els pesos són en **octaves** (negra = 2). Retorna una llista de
    `(num, den, repeticions)` o `None`.
    """
    if rest == 0:
        return []
    if nodes is None:
        nodes = [0, False]
    metres = list(ESTANDARDS)
    if (ref_num, ref_den) not in metres:
        metres.append((ref_num, ref_den))
    # Pes en octaves i orde: la referència mana; després, els més grans.
    metres = sorted(
        metres, key=lambda m: (-(m == (ref_num, ref_den)), -_pes(*m), m))
    pesos = [(_pes(n, d), n, d) for n, d in metres]
    max_pes = max(p for p, _n, _d in pesos)
    if math.ceil(rest / max_pes) > max_bars:
        return None

    def _clau(parts):
        ref_bars = sum(count for n, d, count in parts
                       if (n, d) == (ref_num, ref_den))
        total = sum(count for _n, _d, count in parts)
        return (
            -ref_bars,
            total,
            len(parts),
            len({(n, d) for n, d, _c in parts}),
            tuple((n, d, -count) for n, d, count in parts),
        )

    millor = [None]

    def _rec(remaining, inici, parts, bars):
        if nodes[1]:
            return
        if nodes[0] >= MAX_NODES:
            if millor[0] is None:
                nodes[1] = True
            return
        nodes[0] += 1
        if remaining == 0:
            clau = _clau(parts)
            if millor[0] is None or clau < millor[0][0]:
                millor[0] = (clau, list(parts))
            return
        if len(parts) >= max_parts:
            return
        if bars + math.ceil(remaining / max_pes) > max_bars:
            return
        for i in range(inici, len(pesos)):
            pes, num, den = pesos[i]
            if pes > remaining:
                continue
            max_count = min(remaining // pes, max_bars - bars)
            for count in range(max_count, 0, -1):
                _rec(remaining - pes * count, i,
                     parts + [(num, den, count)], bars + count)

    _rec(rest, 0, [], 0)
    return None if millor[0] is None else millor[0][1]


def _cerca_segments(negres, ref_num, ref_den):
    """Cerca la seqüència de compassos que cobreix `negres` negres."""
    rest_total = 2 * int(negres)          # octaves (negra = 2)
    ref_pes = _pes(ref_num, ref_den)
    metres = list(ESTANDARDS)
    if (ref_num, ref_den) not in metres:
        metres.append((ref_num, ref_den))
    # La referència mana; després, els compassos més pròxims en pes.
    primaris = sorted(
        metres, key=lambda m: (m != (ref_num, ref_den),
                               abs(_pes(*m) - ref_pes), -_pes(*m), m))

    nodes = [0, False]
    for pnum, pden in primaris:
        ppes = _pes(pnum, pden)
        max_q = min(rest_total // ppes, MAX_BARS)
        for q in range(max_q, -1, -1):
            rest = rest_total - q * ppes
            max_parts = MAX_SEGMENTS - (1 if q > 0 else 0)
            parts = _millor_resta(rest, max_parts, ref_num, ref_den,
                                  MAX_BARS - q, nodes=nodes)
            if nodes[1]:
                raise RubatoError(
                    "La durada del rubato no es pot representar amb compassos "
                    "estàndard (la cerca ha esgotat el pressupost)")
            if parts is None:
                continue
            segs = ([(pnum, pden, q)] if q > 0 else []) + list(parts)
            segs = _fusiona(segs)
            if not segs or len(segs) > MAX_SEGMENTS:
                continue
            if sum(c for _n, _d, c in segs) > MAX_BARS:
                continue
            if sum(_pes(n, d) * c for n, d, c in segs) != rest_total:
                continue
            return segs
    raise RubatoError(
        "La durada del rubato no es pot representar amb compassos estàndard "
        f"i un màxim de {MAX_SEGMENTS} segments")


def compassos_a_text(segments):
    """Converteix segments `(num, den, count)` a la forma canònica ASCII."""
    try:
        segs = _fusiona([(int(n), int(d), int(c)) for n, d, c in segments])
    except (TypeError, ValueError) as e:
        raise RubatoError("La seqüència de compassos no és vàlida") from e
    if not segs:
        raise RubatoError("La seqüència de compassos és buida")
    if len(segs) > MAX_SEGMENTS:
        raise RubatoError(
            f"La seqüència de compassos no pot tindre més de "
            f"{MAX_SEGMENTS} segments")
    total = 0
    parts = []
    for num, den, count in segs:
        if den not in (2, 4, 8):
            raise RubatoError("El denominador ha de ser 2, 4 o 8")
        if not limits.NUM_MIN <= num <= limits.NUM_MAX:
            raise RubatoError(
                f"El numerador ha d'estar entre {limits.NUM_MIN} i "
                f"{limits.NUM_MAX}")
        if count < 1 or count > MAX_BARS:
            raise RubatoError("El nombre de repeticions no és vàlid")
        total += count
        parts.append(f"{num}/{den}" + (f"*{count}" if count > 1 else ""))
    if total > MAX_BARS:
        raise RubatoError(
            f"Un rubato no pot tindre més de {MAX_BARS} compassos")
    return "+".join(parts)


def text_a_compassos(text):
    """Llig la forma canònica ASCII (`4/4*3+6/8`) i retorna els segments.

    És estricta: no accepta espais, `×`, zeros davanters, `*1` ni segments
    adjacents iguals. Admet denominadors diferents (el BPM és en negres).
    """
    if not isinstance(text, str) or not text or text != text.strip():
        raise RubatoError("La seqüència de compassos no és vàlida")
    parts = text.split("+")
    if not 1 <= len(parts) <= MAX_SEGMENTS:
        raise RubatoError(
            f"La seqüència de compassos ha de tindre entre 1 i "
            f"{MAX_SEGMENTS} segments")
    out = []
    for part in parts:
        m = _RE_SEGMENT.match(part)
        if not m:
            raise RubatoError(f"Segment de compàs no vàlid: {part!r}")
        num_s, den_s, count_s = m.groups()
        if num_s != str(int(num_s)) or den_s != str(int(den_s)):
            raise RubatoError(f"Segment de compàs no canònic: {part!r}")
        if count_s is not None:
            if count_s != str(int(count_s)) or int(count_s) == 1:
                raise RubatoError(f"Segment de compàs no canònic: {part!r}")
        num, den = int(num_s), int(den_s)
        count = int(count_s) if count_s is not None else 1
        if den not in (2, 4, 8):
            raise RubatoError("El denominador ha de ser 2, 4 o 8")
        if not limits.NUM_MIN <= num <= limits.NUM_MAX:
            raise RubatoError(
                f"El numerador ha d'estar entre {limits.NUM_MIN} i "
                f"{limits.NUM_MAX}")
        if count < 1 or count > MAX_BARS:
            raise RubatoError("El nombre de repeticions no és vàlid")
        out.append((num, den, count))
    if _fusiona(out) != out:
        raise RubatoError(
            "La seqüència de compassos ha d'estar compactada (sense segments "
            "adjacents iguals)")
    if sum(c for _n, _d, c in out) > MAX_BARS:
        raise RubatoError(
            f"Un rubato no pot tindre més de {MAX_BARS} compassos")
    return tuple(out)


def presenta_compassos(text):
    """Forma per a la UI: `4/4 × 3 + 6/8`."""
    out = []
    for num, den, count in text_a_compassos(text):
        et = f"{num}/{den}"
        if count > 1:
            et += f" × {count}"
        out.append(et)
    return " + ".join(out)


def deriva(durada, bpm_ref, num_ref, den_ref):
    """Deriva el BPM (negres/min) i la seqüència de compassos d'un rubato.

    `durada` en segons; `bpm_ref`, `num_ref`, `den_ref` del clip mètric de
    referència. Retorna `Derivacio` o aixeca `RubatoError`.
    """
    bpm_ref, num_ref, den_ref = _valida_referencia(
        bpm_ref, num_ref, den_ref)
    n, bpm = _tria_pulsos(float(durada), bpm_ref)
    segments = _cerca_segments(n, num_ref, den_ref)
    text = compassos_a_text(segments)
    return Derivacio(
        bpm=float(bpm),
        den=int(segments[0][1]),
        compassos=text,
        pulsos=int(n),
        segments=tuple(segments),
        ref_bpm=float(bpm_ref),
        ref_num=int(num_ref),
        ref_den=int(den_ref),
    )


def _normalitza_refs(refs):
    """Accepta una llista de tuples o una sola tupla `(bpm, num, den)`."""
    if refs is None:
        return []
    refs = list(refs)
    if len(refs) == 3 and all(
            isinstance(x, (int, float)) and not isinstance(x, bool)
            for x in refs):
        return [tuple(refs)]
    return refs


def _prova_referencia(t):
    if t is None:
        return None
    try:
        return _valida_referencia(*t)
    except (RubatoError, TypeError):
        return None


def tria_referencia(anteriors, posteriors, transport):
    """Tria la referència d'un rubato: anterior, després següent, transport.

    Cada element és `(bpm, num, den)`; també s'accepta una sola tupla. Els
    elements `None` o no vàlids s'ignoren. Retorna la tupla validada o aixeca
    `RubatoError`.
    """
    for t in reversed(_normalitza_refs(anteriors)):
        ref = _prova_referencia(t)
        if ref is not None:
            return ref
    for t in _normalitza_refs(posteriors):
        ref = _prova_referencia(t)
        if ref is not None:
            return ref
    if transport is None:
        raise RubatoError("No hi ha cap referència per al rubato")
    ref = _prova_referencia(transport)
    if ref is None:
        raise RubatoError("La referència del rubato no és vàlida")
    return ref
