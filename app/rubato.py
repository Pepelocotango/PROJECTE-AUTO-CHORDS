"""Derivació mètrica dels clips de rubato (subplà de rubato, fase 1).

Aquest mòdul és **pur**: no toca Qt, ni el projecte, ni el disc. Rep la durada
d'un rubato i el tempo/compàs de referència, i calcula:

- el **nombre de pulsos** enters que més s'aproxima a la referència;
- el **BPM derivat** que fa coincidir eixos pulsos amb la durada;
- una **seqüència de compassos estàndard** (en la mateixa família de
  denominador) que suma exactament eixos pulsos.

Els segons són la veritat: este mòdul només construeix la representació
mètrica derivada. Si no hi ha cap solució dins del contracte (BPM 30–350,
compassos estàndard, màxim 4 segments), aixeca `RubatoError`.

Decisions de disseny: `00PER FER/DECISIONS_RUBATO.md`.
"""

from dataclasses import dataclass
import math
import re

from app import limits

#: Famílies de compassos estàndard per al rubato, pel denominador.
#: La referència sempre és permesa encara que el seu numerador no siga ací.
FAMILIES = {
    2: (2, 3, 4),
    4: (2, 3, 4, 5, 6, 7),
    8: (3, 6, 9, 12),
}

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
    if den not in FAMILIES:
        raise RubatoError(
            "El denominador de referència ha de ser 2, 4 o 8")
    if not limits.NUM_MIN <= num <= limits.NUM_MAX:
        raise RubatoError(
            f"El numerador de referència ha d'estar entre "
            f"{limits.NUM_MIN} i {limits.NUM_MAX}")
    return bpm, num, den


def _tria_pulsos(durada, bpm_ref):
    """Nombre enter de pulsos dins de 30–350, el més pròxim a la referència."""
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
    # Ajust de seguretat només si eixim de la banda de debò (no per
    # arrodoniment de coma flotant, p. ex. 350.00000000000006).
    if bpm < limits.BPM_MIN - 1e-9:
        n += 1
        bpm = n * 60.0 / durada
    elif bpm > limits.BPM_MAX + 1e-9:
        n -= 1
        bpm = n * 60.0 / durada
    if not (limits.BPM_MIN - 1e-9 <= bpm <= limits.BPM_MAX + 1e-9):
        raise RubatoError(
            "No hi ha cap nombre enter de pulsos dins de la banda de BPM")
    # El valor del model ha de quedar estrictament dins la banda.
    bpm = min(max(bpm, limits.BPM_MIN), limits.BPM_MAX)
    return n, bpm


def _fusiona(segments):
    """Fusiona segments adjacents del mateix compàs."""
    out = []
    for num, count in segments:
        if count <= 0:
            continue
        if out and out[-1][0] == num:
            out[-1] = (num, out[-1][1] + count)
        else:
            out.append((num, count))
    return out


def _millor_resta(rest, den, max_parts, ref_num, max_bars=MAX_BARS,
                  nodes=None):
    """Millor combinació de fins a `max_parts` compassos que suma `rest`.

    Retorna una llista de `(numerador, repeticions)` o `None`. Els compassos
    són de la família `den`; la referència també és permesa. `max_bars` limita
    el nombre total de compassos de la combinació.

    `nodes` és un comptador compartit `[usats, esgotat]`: la cerca pot trobar
    una solució i continuar buscant-ne una de millor, però si s'esgota el
    pressupost sense cap solució, marca `esgotat` perquè el cridador puga
    rebutjar el rubato sense quedar-se penjat.
    """
    if rest == 0:
        return []
    if nodes is None:
        nodes = [0, False]
    nums = sorted(set(FAMILIES[den]) | {ref_num}, reverse=True)
    max_num = max(nums)
    if math.ceil(rest / max_num) > max_bars:
        return None

    def _clau(parts):
        ref_bars = sum(count for num, count in parts if num == ref_num)
        total = sum(count for _, count in parts)
        return (
            -ref_bars,
            total,
            len(parts),
            len({num for num, _ in parts}),
            tuple((num, -count) for num, count in parts),
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
        if bars + math.ceil(remaining / max_num) > max_bars:
            return
        for i in range(inici, len(nums)):
            num = nums[i]
            if num > remaining:
                continue
            max_count = min(remaining // num, max_bars - bars)
            for count in range(max_count, 0, -1):
                _rec(remaining - num * count, i,
                     parts + [(num, count)], bars + count)

    _rec(rest, 0, [], 0)
    return None if millor[0] is None else millor[0][1]


def _cerca_segments(n, den, ref_num):
    """Cerca la seqüència de compassos que cobreix `n` pulsos."""
    estandards = sorted(set(FAMILIES[den]) | {ref_num})
    # Si tots els numeradors són múltiples de g, només hi ha solucions per a
    # n múltiple de g (p. ex. família 8 amb referència 6/8: g = 3).
    g = 0
    for num in estandards:
        g = math.gcd(g, num)
    if g > 1 and n % g:
        raise RubatoError(
            "La durada del rubato no es pot representar amb compassos "
            f"estàndard (els pulsos han de ser múltiples de {g})")
    # La referència mana; després, els compassos més pròxims al seu numerador.
    primaris = [ref_num] + [
        num for num in sorted(estandards, key=lambda x: (abs(x - ref_num), x))
        if num != ref_num
    ]

    nodes = [0, False]
    for primari in primaris:
        max_q = min(n // primari, MAX_BARS)
        for q in range(max_q, -1, -1):
            rest = n - q * primari
            max_parts = MAX_SEGMENTS - (1 if q > 0 else 0)
            parts = _millor_resta(rest, den, max_parts, ref_num,
                                  MAX_BARS - q, nodes=nodes)
            if nodes[1]:
                raise RubatoError(
                    "La durada del rubato no es pot representar amb compassos "
                    "estàndard (la cerca ha esgotat el pressupost)")
            if parts is None:
                continue
            segs = ([(primari, q)] if q > 0 else []) + list(parts)
            segs = _fusiona(segs)
            if not segs or len(segs) > MAX_SEGMENTS:
                continue
            if sum(count for _, count in segs) > MAX_BARS:
                continue
            if sum(num * count for num, count in segs) != n:
                continue
            return segs
    raise RubatoError(
        "La durada del rubato no es pot representar amb compassos estàndard "
        f"i un màxim de {MAX_SEGMENTS} segments")


def compassos_a_text(segments, den):
    """Converteix segments `(num, count)` a la forma canònica ASCII."""
    try:
        den = int(den)
        segs = _fusiona([(int(num), int(count)) for num, count in segments])
    except (TypeError, ValueError) as e:
        raise RubatoError("La seqüència de compassos no és vàlida") from e
    if den not in FAMILIES:
        raise RubatoError("El denominador ha de ser 2, 4 o 8")
    if not segs:
        raise RubatoError("La seqüència de compassos és buida")
    if len(segs) > MAX_SEGMENTS:
        raise RubatoError(
            f"La seqüència de compassos no pot tindre més de "
            f"{MAX_SEGMENTS} segments")
    total = 0
    parts = []
    for num, count in segs:
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
    """Llig la forma canònica ASCII (`4/4*3+3/4`) i retorna els segments.

    És estricta: no accepta espais, `×`, zeros davanters, `*1`, segments
    adjacents iguals ni més de 999 compassos en total. Els segments han de
    tindre el mateix denominador i un màxim de 4.
    """
    if not isinstance(text, str) or not text or text != text.strip():
        raise RubatoError("La seqüència de compassos no és vàlida")
    parts = text.split("+")
    if not 1 <= len(parts) <= MAX_SEGMENTS:
        raise RubatoError(
            f"La seqüència de compassos ha de tindre entre 1 i "
            f"{MAX_SEGMENTS} segments")
    out = []
    den = None
    for part in parts:
        m = _RE_SEGMENT.match(part)
        if not m:
            raise RubatoError(f"Segment de compàs no vàlid: {part!r}")
        num_s, den_s, count_s = m.groups()
        # Forma canònica: sense zeros davanters i sense `*1`.
        if num_s != str(int(num_s)) or den_s != str(int(den_s)):
            raise RubatoError(f"Segment de compàs no canònic: {part!r}")
        if count_s is not None:
            if count_s != str(int(count_s)) or int(count_s) == 1:
                raise RubatoError(f"Segment de compàs no canònic: {part!r}")
        num, d = int(num_s), int(den_s)
        count = int(count_s) if count_s is not None else 1
        if d not in FAMILIES:
            raise RubatoError("El denominador ha de ser 2, 4 o 8")
        if not limits.NUM_MIN <= num <= limits.NUM_MAX:
            raise RubatoError(
                f"El numerador ha d'estar entre {limits.NUM_MIN} i "
                f"{limits.NUM_MAX}")
        if count < 1 or count > MAX_BARS:
            raise RubatoError("El nombre de repeticions no és vàlid")
        if den is None:
            den = d
        elif d != den:
            raise RubatoError(
                "Tots els compassos d'un rubato han de tindre el mateix "
                "denominador")
        out.append((num, count))
    if _fusiona(out) != out:
        raise RubatoError(
            "La seqüència de compassos ha d'estar compactada (sense segments "
            "adjacents iguals)")
    if sum(count for _, count in out) > MAX_BARS:
        raise RubatoError(
            f"Un rubato no pot tindre més de {MAX_BARS} compassos")
    return tuple(out)


def presenta_compassos(text):
    """Forma per a la UI: `4/4 × 3 + 3/4`."""
    segs = text_a_compassos(text)
    den = int(text.split("+", 1)[0].split("/", 1)[1].split("*", 1)[0])
    out = []
    for num, count in segs:
        et = f"{num}/{den}"
        if count > 1:
            et += f" × {count}"
        out.append(et)
    return " + ".join(out)


def deriva(durada, bpm_ref, num_ref, den_ref):
    """Deriva el BPM i la seqüència de compassos d'un rubato.

    `durada` en segons; `bpm_ref`, `num_ref`, `den_ref` del clip mètric de
    referència. Retorna `Derivacio` o aixeca `RubatoError`.
    """
    bpm_ref, num_ref, den_ref = _valida_referencia(
        bpm_ref, num_ref, den_ref)
    n, bpm = _tria_pulsos(float(durada), bpm_ref)
    segments = _cerca_segments(n, den_ref, num_ref)
    text = compassos_a_text(segments, den_ref)
    return Derivacio(
        bpm=float(bpm),
        den=int(den_ref),
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
