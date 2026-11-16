"""Motor pur de recalcul del mapa de temps (F0).

Donada la durada d'un tram i una referència de BPM/compàs (la que ha posat
el músic amb el tap tempo i el compàs), busca la combinació de BPM, compàs i
nombre de compassos que més s'hi acosta i que fa que el tram tinga compassos
sencers.

És l'**únic motor** de decisió `N/BPM/compàs`. `mode` fa explícites les dos
fonts de veritat —`graella`/segons o `beats` detectats— i `mixt` les combina.
Les operacions del mapa (BPM explícit, N compassos, detectat, fronteres,
marcadors, rubato) han de reduir-se a una crida amb estes opcions.

No depén de Qt ni del model de clips: és una funció pura i testable.
"""
from __future__ import annotations

import math

from . import bpm_unit, limits

# Penalitzacions de signatures poc habituals.
_COMUNS = {(4, 4), (3, 4), (2, 4), (6, 8), (12, 8)}
_MENYS_COMUNS = {(5, 4), (7, 4), (11, 4), (7, 8), (9, 8), (5, 8),
                 (6, 4), (2, 2), (3, 8)}

# Avisos (no canvien la decisió): desviació de BPM i sospita d'octava.
LLINDAR_DESVIACIO_BPM = 0.12
MARGE_SOSPITA_OCTAVA = 0.08

# --- Classificació del recalc (S3) -----------------------------------------
# Llindars DETERMINISTES i testejables. El classificador no decidix res: diu
# quant de segur és aplicar un candidat. ALT = aplicable automàticament;
# MITJÀ = factible però cal revisió (canvi estructural, beats ajustats,
# candidats propers, cost alt o factor 1,5×/2/3); BAIX = conflicte dur.
NIVELL_ALT = "ALT"
NIVELL_MITJA = "MITJÀ"
NIVELL_BAIX = "BAIX"
#: Cost màxim d'un candidat ALT.
COST_ALT = 0.05
#: Dos candidats són «propers» si el segon no supera el millor per este marge.
COST_PROPER = 0.10
#: |log2(bpm/bpm_ref)| màxim d'un candidat ALT (≈2 %).
DESVIACIO_BPM_ALT = 0.02
#: Un únic candidat factible per damunt d'este cost és MITJÀ amb avís.
COST_MITJA_AVIS = 0.30
#: Factors sospitosos (possible error d'octava o de treset). NO s'apliquen
#: automàticament: són MITJÀ. Es proven també els inversos (0,5; 0,667; 0,333).
FACTORS_SOSPITOSOS = (1.5, 2.0, 3.0)
MARGE_FACTOR = 0.05
#: El compàs global de la Ref. només desempata: el pes és menut a posta perquè
#: la referència LOCAL continue manant en `n_previst` i la regla del múltiple.
PES_METER_PRIOR = 1e-3

# Tolerància exacta per a fronteres calculades (tests i snap).
TOL_BEATS = 1e-6
# Tolerància OPERATIVA dels talls manuals sense snap: un beat dins d'esta
# franja es considera de frontera. Evita que moure la vora 1 ms canvie K i,
# amb ell, la signatura o el BPM.
TOL_TALL = 0.05


def bpm_de_n(n, num, den, durada):
    """BPM que fa que `n` compassos `num/den` caben en `durada` segons."""
    durada = float(durada)
    if durada <= 0:
        raise ValueError("La durada ha de ser positiva")
    return float(n) * _bar_quarters(num, den) * 60.0 / durada


def durada_de_n(n, bpm, num, den):
    """Segons que ocupen `n` compassos `num/den` a `bpm`."""
    bpm = float(bpm)
    if bpm <= 0:
        raise ValueError("El BPM ha de ser positiu")
    return float(n) * _bar_quarters(num, den) * 60.0 / bpm


def n_de_durada(durada, bpm, num, den):
    """Nombre de compassos (pot ser fraccionari) en `durada` segons."""
    bpm = float(bpm)
    if bpm <= 0:
        raise ValueError("El BPM ha de ser positiu")
    bq = _bar_quarters(num, den)
    if bq <= 0:
        raise ValueError("El compàs no és vàlid")
    return float(durada) * bpm / (bq * 60.0)


def n_negres_del_clip(beats, ini, fi, beat_factor=1.0, tol=TOL_TALL):
    """Negres (float) dels beats detectats dins `[ini, fi)`, o `None`.

    `beats` són els temps del detector (tactus); `beat_factor` els convertix a
    negres (negra=1, negra amb punt=1.5, corxera=0.5). Si no hi ha cap beat
    dins el clip retorna `None` (no `0`), perquè el recalcul puga inferir el
    nombre de negres des de la durada i la referència.

    `tol` és la tolerància operativa (50 ms per defecte): un beat dins d'eixa
    franja al voltant d'una frontera es classifica de manera estable. Els tests
    de frontera exacta poden passar `tol=TOL_BEATS`.
    """
    ini = float(ini)
    fi = float(fi)
    if fi <= ini:
        return None
    factor = float(beat_factor or 1.0)
    if factor <= 0:
        return None
    tol = float(tol)
    n = sum(1 for b in (beats or ())
            if ini - tol <= float(b) < fi - tol)
    if not n:
        return None
    return float(n) * factor


def beats_a_la_frontera(beats, ini, fi, tol=TOL_TALL):
    """Beats que queden dins la franja ambigua d'algun extrem del clip.

    No inclou els que cauen exactament damunt la frontera: eixos tenen una
    classificació clara (clip de la dreta). Serveix per a avisar que un tall
    sense snap està massa prop d'un beat i que el recompte depén de la
    tolerància.
    """
    ini = float(ini)
    fi = float(fi)
    tol = float(tol)
    if tol <= 0 or fi <= ini:
        return []
    return sorted({float(b) for b in (beats or ())
                   if 0.0 < abs(float(b) - ini) <= tol
                   or 0.0 < abs(float(b) - fi) <= tol})


def _bar_quarters(num, den):
    return limits.bar_quarters(num, den)


def _distancia_compas(num, den, num_ref, den_ref):
    if (num, den) == (num_ref, den_ref):
        return 0.0
    if den == den_ref:
        diferencia = abs(int(num) - int(num_ref))
        if diferencia == 1:
            return 0.25
        if diferencia == 2:
            return 0.5
        return 1.5
    if num == num_ref:
        return 1.5
    return 2.0


def _penalitzacio_compas(num, den):
    if (num, den) in _COMUNS:
        return 0.0
    if (num, den) in _MENYS_COMUNS:
        return 0.2
    return 0.5


def _valida_referencia(bpm_ref, num_ref, den_ref):
    bpm_ref = float(bpm_ref)
    if not (limits.BPM_MIN <= bpm_ref <= limits.BPM_MAX):
        raise ValueError(
            f"BPM de referència fora de {limits.BPM_MIN:g}–"
            f"{limits.BPM_MAX:g}")
    if int(num_ref) < limits.NUM_MIN or int(num_ref) > limits.NUM_MAX:
        raise ValueError("Numerador de referència fora de rang")
    if int(den_ref) not in limits.DENOMINADORS_ADMESOS:
        raise ValueError("Denominador de referència no admissible")
    return bpm_ref, int(num_ref), int(den_ref)


def _amb_avisos_resultat(res, bpm_ref, num_ref, den_ref, prior, prior_actiu):
    """Afegix els avisos comuns i la traçabilitat del compàs local/global."""
    ratio = float(res["bpm"]) / float(bpm_ref)
    res["desviacio_bpm"] = ratio - 1.0
    res["sospita_octava"] = (
        abs(ratio - 2.0) <= 2.0 * MARGE_SOSPITA_OCTAVA
        or abs(ratio - 0.5) <= 0.5 * MARGE_SOSPITA_OCTAVA)
    res["compas_local"] = (int(num_ref), int(den_ref))
    res["meter_prior"] = (int(prior[0]), int(prior[1]))
    res["meter_prior_actiu"] = bool(prior_actiu)
    return res


def _valida_compas(num, den):
    """Valida un compàs ``num/den`` admissible i el retorna com a enters."""
    try:
        num, den = int(num), int(den)
    except (TypeError, ValueError):
        raise ValueError("El compàs no és vàlid") from None
    if num < limits.NUM_MIN or num > limits.NUM_MAX:
        raise ValueError("Numerador de referència fora de rang")
    if den not in limits.DENOMINADORS_ADMESOS:
        raise ValueError("Denominador de referència no admissible")
    return num, den


def _prior_meter(meter_prior, num_ref, den_ref):
    """Retorna ``((num, den), actiu)`` per al compàs global de la Ref.

    ``actiu`` és False si no hi ha prior o si coincidix amb el compàs local:
    així ``meter_prior=None`` reproduïx EXACTAMENT el cost històric.
    """
    if meter_prior is None:
        return (int(num_ref), int(den_ref)), False
    prior = _valida_compas(*meter_prior)
    return prior, prior != (int(num_ref), int(den_ref))


def _cost_beats(bpm, num, den, n, bpm_ref, num_ref, den_ref,
                prior_num, prior_den, prior_actiu, n_cost_ref,
                w_bpm, w_compas, w_n, w_natural, w_den):
    """Cost històric (compàs LOCAL) + desempat menut pel compàs GLOBAL."""
    cost = (w_bpm * abs(math.log2(bpm / bpm_ref))
            + w_compas * _distancia_compas(num, den, num_ref, den_ref)
            + w_n * abs(n - n_cost_ref) / max(1, n_cost_ref)
            + w_natural * _penalitzacio_compas(num, den)
            + w_den * (den != den_ref))
    if prior_actiu:
        cost += PES_METER_PRIOR * (
            w_compas * _distancia_compas(num, den, prior_num, prior_den)
            + w_den * (den != prior_den))
    return cost


def _cost_durada(bpm, num, den, n, bpm_ref, num_ref, den_ref,
                 prior_num, prior_den, prior_actiu, n_cost_ref,
                 w_bpm, w_compas, w_n, w_natural, w_den):
    """Cost del camí per durada (històricament sense `w_den`)."""
    cost = (w_bpm * abs(math.log2(bpm / bpm_ref))
            + w_compas * _distancia_compas(num, den, num_ref, den_ref)
            + w_n * abs(n - n_cost_ref) / max(1, n_cost_ref)
            + w_natural * _penalitzacio_compas(num, den))
    if prior_actiu:
        cost += PES_METER_PRIOR * (
            w_compas * _distancia_compas(num, den, prior_num, prior_den)
            + w_den * (den != prior_den))
    return cost


def _candidats_per_beats(durada, bpm_ref, num_ref, den_ref, prior_num,
                         prior_den, prior_actiu, n_beats, n_previst, n_fix,
                         n_ref, bloca_compas, bpm_min, bpm_max, n_max,
                         w_bpm, w_compas, w_n, w_natural, w_den):
    """Tuples de candidats quan els beats són una restricció forta.

    Mateixa lògica que el motor històric: `n` compassos del compàs han de
    cuadrar amb el nombre de negres (tolerància 0,25) i no s'admeten
    solucions degenerades (`bq ≤ 1` amb `n > 1`). Els costos inclouen el
    compàs local com a referència principal.
    """
    out = []
    dens = (den_ref,) if bloca_compas else limits.DENOMINADORS_ADMESOS
    nums = ((num_ref,) if bloca_compas
            else range(limits.NUM_MIN, limits.NUM_MAX + 1))
    for den in dens:
        for num in nums:
            bq = _bar_quarters(num, den)
            n_exact = float(n_beats) / bq
            n = int(round(n_exact))
            if n < 1 or n > int(n_max):
                continue
            if abs(n * bq - float(n_beats)) > 0.25:
                continue
            if bq <= 1.0 + 1e-9 and int(n) > 1:
                continue
            if n_fix and n != int(n_ref):
                continue
            bpm = 60.0 * n * bq / durada
            if not (bpm_min - 1e-9 <= bpm <= bpm_max + 1e-9):
                continue
            cost = _cost_beats(
                bpm, num, den, n, bpm_ref, num_ref, den_ref,
                prior_num, prior_den, prior_actiu, n_previst,
                w_bpm, w_compas, w_n, w_natural, w_den)
            out.append((cost, abs(math.log2(bpm / bpm_ref)),
                        _distancia_compas(num, den, num_ref, den_ref),
                        bpm, num, den, n))
    return out


def _candidats_per_durada(durada, bpm_ref, num_ref, den_ref, prior_num,
                          prior_den, prior_actiu, n_valors, n_cost_ref,
                          bloca_compas, bpm_min, bpm_max,
                          w_bpm, w_compas, w_n, w_natural, w_den):
    """Tuples de candidats del camí per durada (sense beats)."""
    out = []
    dens = (den_ref,) if bloca_compas else limits.DENOMINADORS_ADMESOS
    nums = ((num_ref,) if bloca_compas
            else range(limits.NUM_MIN, limits.NUM_MAX + 1))
    for n in n_valors:
        for den in dens:
            for num in nums:
                bpm = 60.0 * n * num * (4.0 / den) / durada
                if not (bpm_min - 1e-9 <= bpm <= bpm_max + 1e-9):
                    continue
                cost = _cost_durada(
                    bpm, num, den, n, bpm_ref, num_ref, den_ref,
                    prior_num, prior_den, prior_actiu, n_cost_ref,
                    w_bpm, w_compas, w_n, w_natural, w_den)
                out.append((cost, abs(n - n_cost_ref),
                            abs(math.log2(bpm / bpm_ref)),
                            _distancia_compas(num, den, num_ref, den_ref),
                            bpm, num, den, n))
    return out


def recalculca_tram(durada, bpm_ref, num_ref, den_ref, n_ref=None, *,
                    n_beats=None, mode="mixt", bloca_compas=False,
                    bpm_min=None, bpm_max=None, n_ventana=3,
                    w_bpm=1.0, w_compas=1.5, w_n=3.0, w_natural=0.1,
                    w_den=1.5, n_max=16, ajusta_beats=True,
                    pas_beat=1.0, meter_prior=None):
    """Busca la millor combinació (BPM, compàs, N) per a un tram.

    `n_ref` fixat = el nombre de compassos és una restricció (marcadors).
    Si no es passa, es calcula a partir de la referència i la durada.

    `mode` fa explícites les dos fonts de veritat:
      - ``graella``: només durada + BPM/compàs de referència (segons/graella);
      - ``beats``: obliga `n_beats` (beats detectats) i no infereix res;
      - ``mixt`` (defecte): usa els beats si n'hi ha; si no, infereix negres
        de la referència quan és a prop d'un enter i, si cal, cau a graella.

    `bloca_compas=True` impedix canviar la signatura de referència; és el que
    fan les accions explícites que només volen recalcular el BPM amb el
    compàs triat. Retorna un diccionari o `None` si no hi ha cap combinació.

    **Compàs local i compàs global (S3).** `num_ref`/`den_ref` són sempre el
    compàs **LOCAL** del costat: manen en `bar_ref`/`n_previst`, en la regla
    del múltiple i en `bloca_compas`. `meter_prior=(num, den)` és el compàs
    **GLOBAL** de la Ref. i només entra al cost com a desempat menut
    (`_distancia_compas`, `w_den`, naturalitat). Si és `None` (o coincidix
    amb el local) el resultat és EXACTAMENT el de sempre.
    """
    durada = float(durada)
    if durada <= 0:
        raise ValueError("La durada del tram ha de ser positiva")
    mode = str(mode or "mixt").strip().lower()
    if mode not in ("graella", "beats", "mixt"):
        mode = "mixt"
    if mode == "graella":
        n_beats = None
    elif mode == "beats" and n_beats is None:
        return None
    if n_beats is not None:
        n_beats = float(n_beats)
        if n_beats <= 0:
            n_beats = None
        if mode == "beats" and n_beats is None:
            return None
    pas_beat = float(pas_beat or 1.0)
    if pas_beat <= 0:
        pas_beat = 1.0
    bpm_ref, num_ref, den_ref = _valida_referencia(
        bpm_ref, num_ref, den_ref)
    (prior_num, prior_den), prior_actiu = _prior_meter(
        meter_prior, num_ref, den_ref)
    bpm_min = limits.BPM_MIN if bpm_min is None else float(bpm_min)
    bpm_max = limits.BPM_MAX if bpm_max is None else float(bpm_max)

    def _amb_avisos(res):
        return _amb_avisos_resultat(
            res, bpm_ref, num_ref, den_ref,
            (prior_num, prior_den), prior_actiu)

    bar_ref = _bar_quarters(num_ref, den_ref) * 60.0 / bpm_ref
    n_previst = max(1, int(round(durada / bar_ref)))
    n_fix = n_ref is not None
    beats_inferits = False

    # Sense beats detectats, si la referència BPM dona un nombre de negres
    # pràcticament enter, l'usem com a pista (7,02 → 7). No ho fem si el
    # nombre de compassos ve fixat pels marcadors.
    if n_beats is None and not n_fix and mode == "mixt":
        beats_ref = durada * bpm_ref / 60.0
        n_round = int(round(beats_ref))
        if n_round >= 1 and abs(beats_ref - n_round) <= 0.2:
            n_beats = float(n_round)
            beats_inferits = True

    # Si tenim els beats detectats, el nombre de negres del clip és una
    # restricció forta: 7 beats han de ser 7/4 (o una combinació equivalent),
    # no 2 compassos de 4/4. Quan hi ha beats, poden corregir el compàs i `N`
    # respecte de la referència base: es prefereix una signatura natural amb
    # el mínim de compassos (14 beats → 7/4 N=2, no 2/4 N=7; 8 beats → 4/4
    # N=2, no 8/4 N=1). La referència base decidix només els empats.
    if n_beats is not None:
        # Regla del múltiple: si la signatura de la referència encaixa exacta
        # amb el nombre de negres del clip, mana ella. Així 20/24/28 beats amb
        # base 4/4 són 4/4 N=5/6/7 (no 5/4/6/4/7/4); 12/36 amb base 3/4 són
        # 3/4 N=4/12; 6/12 amb base 6/8 són 6/8 N=2/4. La signatura de la
        # referència està exempta de `n_max` (clips llargs), però no de la
        # banda de BPM. Amb `n_fix`, només val si `N` coincidix amb el fixat.
        bq_ref = _bar_quarters(num_ref, den_ref)
        if bq_ref > 1.0 + 1e-9:
            n_ref_mult = int(round(float(n_beats) / bq_ref))
            if (n_ref_mult >= 1
                    and abs(n_ref_mult * bq_ref - float(n_beats)) <= 0.25
                    and (not n_fix or n_ref_mult == int(n_ref))):
                bpm_ref_mult = 60.0 * n_ref_mult * bq_ref / durada
                if bpm_min - 1e-9 <= bpm_ref_mult <= bpm_max + 1e-9:
                    return _amb_avisos({
                        "bpm": float(bpm_ref_mult),
                        "num": int(num_ref),
                        "den": int(den_ref),
                        "n": int(n_ref_mult),
                        "cost": 0.0,
                        "n_ref": int(n_previst),
                        "bpm_ref": float(bpm_ref),
                        "compas_ref": (int(num_ref), int(den_ref)),
                        "beats": float(n_beats),
                        "beats_detectats": float(n_beats),
                        "beats_ajustats": False,
                        "beats_usats": True,
                        "beats_inferits": beats_inferits,
                        "canvis": {
                            "bpm": abs(bpm_ref_mult - bpm_ref) > 1e-9,
                            "compas": False,
                            "n": (not n_fix) and n_ref_mult != n_previst,
                        },
                    })
        beats_candidats = _candidats_per_beats(
            durada, bpm_ref, num_ref, den_ref, prior_num, prior_den,
            prior_actiu, n_beats, n_previst, n_fix, n_ref, bloca_compas,
            bpm_min, bpm_max, n_max,
            w_bpm, w_compas, w_n, w_natural, w_den)
        if beats_candidats:
            # Prioritat 1: signatures COMUNES amb el MATEIX denominador que
            # la base i pocs compassos (8 beats → 4/4 N=2; 9 → 3/4 N=3; 6 →
            # 3/4 N=2, no 12/8 N=1). Prioritat 2: qualsevol signatura natural
            # amb el mateix denominador (14 → 7/4 N=2, no 2/4 N=7). Prioritat
            # 3: qualsevol natural. Si no, cost.
            def _natural(c):
                return (c[4], c[5]) in _COMUNS or (c[4], c[5]) in _MENYS_COMUNS
            comuns_den = [
                c for c in beats_candidats
                if c[6] <= 4 and c[5] == den_ref and (c[4], c[5]) in _COMUNS
            ]
            naturals_den = [
                c for c in beats_candidats if c[5] == den_ref and _natural(c)
            ]
            naturals = [c for c in beats_candidats if _natural(c)]
            if comuns_den:
                tria = comuns_den
            elif naturals_den:
                tria = naturals_den
            elif naturals:
                tria = naturals
            else:
                tria = beats_candidats
            # Menys compassos primer; el cost decidix empats (p. ex. 4/4 vs
            # 2/2 per a 8 beats, o 3/4 vs 6/8 per a 9).
            cost, _db, _dc, bpm, num, den, n = min(
                tria, key=lambda c: (c[6], c[0], c[1], c[2]))
            return _amb_avisos({
                "bpm": float(bpm),
                "num": int(num),
                "den": int(den),
                "n": int(n),
                "cost": float(cost),
                "n_ref": int(n_previst),
                "bpm_ref": float(bpm_ref),
                "compas_ref": (int(num_ref), int(den_ref)),
                "beats": float(n_beats),
                "beats_detectats": float(n_beats),
                "beats_ajustats": False,
                "beats_usats": True,
                "beats_inferits": beats_inferits,
                "canvis": {
                    "bpm": abs(bpm - bpm_ref) > 1e-9,
                    "compas": (num, den) != (num_ref, den_ref),
                    "n": (not n_fix) and n != n_previst,
                },
            })
        # Fallback d'un beat detectat: si K no es pot factoritzar en cap
        # compàs, provem un tacte amunt/avall. `pas_beat` val 1,5 negres amb
        # negra amb punt i 0,5 amb corxera; si els beats són inferits, el pas
        # és una negra (no hi ha cap tacte detectat). Prioritat al K' que
        # encaixa amb la signatura de la referència; si no, al BPM més pròxim.
        # No s'aplica amb n_fix.
        if (ajusta_beats and not n_fix
                and n_beats is not None and float(n_beats) > 0):
            pas = 1.0 if beats_inferits else pas_beat
            candidats = []
            for k2 in (n_beats - pas, n_beats + pas):
                if k2 < 1:
                    continue
                r2 = recalculca_tram(
                    durada, bpm_ref, num_ref, den_ref, n_ref=None,
                    n_beats=k2, mode="beats", bloca_compas=bloca_compas,
                    bpm_min=bpm_min, bpm_max=bpm_max,
                    ajusta_beats=False, pas_beat=pas,
                    meter_prior=(prior_num, prior_den) if prior_actiu
                    else None)
                if r2 is not None and r2.get("beats_usats"):
                    candidats.append((k2, r2))
            if candidats:
                def _mult_ref(k2):
                    if bq_ref <= 1.0 + 1e-9:
                        return False
                    n2 = int(round(float(k2) / bq_ref))
                    return (n2 >= 1
                            and abs(n2 * bq_ref - float(k2)) <= 0.25)
                refs = [c for c in candidats if _mult_ref(c[0])]
                pool = refs or candidats
                k2, r = min(
                    pool,
                    key=lambda c: abs(math.log(c[1]["bpm"] / bpm_ref)))
                r["beats"] = float(k2)
                r["beats_detectats"] = float(n_beats)
                r["beats_ajustats"] = True
                r["beats_inferits"] = beats_inferits
                return _amb_avisos(r)
    if n_fix:
        n_valors = [int(n_ref)]
        n_cost_ref = int(n_ref)
    else:
        n_valors = range(max(1, n_previst - int(n_ventana)),
                         n_previst + int(n_ventana) + 1)
        n_cost_ref = n_previst

    millor = None
    for candidat in _candidats_per_durada(
            durada, bpm_ref, num_ref, den_ref, prior_num, prior_den,
            prior_actiu, n_valors, n_cost_ref, bloca_compas, bpm_min, bpm_max,
            w_bpm, w_compas, w_n, w_natural, w_den):
        if millor is None or candidat < millor:
            millor = candidat
    if millor is None:
        return None
    cost, _dn, _db, _dc, bpm, num, den, n = millor
    return _amb_avisos({
        "bpm": float(bpm),
        "num": int(num),
        "den": int(den),
        "n": int(n),
        "cost": float(cost),
        "n_ref": int(n_previst),
        "bpm_ref": float(bpm_ref),
        "compas_ref": (int(num_ref), int(den_ref)),
        "beats": None if n_beats is None else float(n_beats),
        "beats_detectats": None if n_beats is None else float(n_beats),
        "beats_ajustats": False,
        "beats_usats": False,
        "beats_inferits": False,
        "canvis": {
            "bpm": abs(bpm - bpm_ref) > 1e-9,
            "compas": (num, den) != (num_ref, den_ref),
            "n": (not n_fix) and n != n_previst,
        },
    })


def recalculca_vei_ref(durada, bpm_ref, num_ref, den_ref, *,
                       bpm_min=None, bpm_max=None, meter_prior=None):
    """Recalcula el veí amb el mínim moviment respecte del veí esquerre.

    Prioritat:
    1. Conserva la signatura `num_ref/den_ref` i busca l'`N` enter que deixa
       el BPM més a prop possible de `bpm_ref` (ajust xicotet de BPM).
    2. Només si no hi ha cap `N` vàlid amb eixa signatura, permet canviar
       `x/x` i torna a buscar la combinació més pròxima a la referència.

    `meter_prior=(num, den)` és el compàs GLOBAL de la Ref. i només desempata
    el cost del recalcul (la signatura local continua manant).

    Retorna el diccionari de `recalculca_tram` o `None` si no hi ha cap
    combinació vàlida.
    """
    durada = float(durada)
    bpm_ref, num_ref, den_ref = _valida_referencia(bpm_ref, num_ref, den_ref)
    bmin = limits.BPM_MIN if bpm_min is None else float(bpm_min)
    bmax = limits.BPM_MAX if bpm_max is None else float(bpm_max)
    kw = dict(mode="graella", bpm_min=bmin, bpm_max=bmax, n_ventana=8,
              meter_prior=meter_prior)
    r = recalculca_tram(durada, bpm_ref, num_ref, den_ref,
                        bloca_compas=True, **kw)
    if r is not None:
        return r
    return recalculca_tram(durada, bpm_ref, num_ref, den_ref,
                           bloca_compas=False, **kw)


def _clau_candidat(c):
    """Clau d'un resultat per a deduplicar candidats idèntics."""
    return (round(float(c["bpm"]), 9), int(c["num"]), int(c["den"]),
            int(c["n"]))


def _resultat_candidat(cost, bpm, num, den, n, bpm_ref, num_ref, den_ref,
                       prior_num, prior_den, prior_actiu, n_previst,
                       beats, n_fix, beats_inferits=False,
                       beats_ajustats=False):
    """Construïx el diccionari d'un candidat amb la mateixa forma que el motor."""
    res = {
        "bpm": float(bpm),
        "num": int(num),
        "den": int(den),
        "n": int(n),
        "cost": float(cost),
        "n_ref": int(n_previst),
        "bpm_ref": float(bpm_ref),
        "compas_ref": (int(num_ref), int(den_ref)),
        "beats": None if beats is None else float(beats),
        "beats_detectats": None if beats is None else float(beats),
        "beats_ajustats": bool(beats_ajustats),
        "beats_usats": beats is not None,
        "beats_inferits": bool(beats_inferits),
        "canvis": {
            "bpm": abs(float(bpm) - float(bpm_ref)) > 1e-9,
            "compas": (int(num), int(den)) != (int(num_ref), int(den_ref)),
            "n": (not n_fix) and int(n) != int(n_previst),
        },
    }
    return _amb_avisos_resultat(
        res, bpm_ref, num_ref, den_ref,
        (prior_num, prior_den), prior_actiu)


def _enumera_candidats(durada, bpm_ref, num_ref, den_ref, n_ref=None, *,
                       n_beats=None, mode="mixt", bloca_compas=False,
                       bpm_min=None, bpm_max=None, n_ventana=3,
                       w_bpm=1.0, w_compas=1.5, w_n=3.0, w_natural=0.1,
                       w_den=1.5, n_max=16, ajusta_beats=True,
                       pas_beat=1.0, meter_prior=None):
    """Enumera els candidats factibles del recalcul (per al classificador).

    Fa exactament els mateixos filtres durs que `recalculca_tram` (rang de
    BPM, `N` enter, tolerància de beats, regla del múltiple, degenerats). No
    aplica la prioritat de selecció: el resultat autoritatiu continua sent
    `recalculca_tram`; esta funció només servix per a vore si hi ha
    alternatives i com de prop estan.
    """
    durada = float(durada)
    if durada <= 0:
        raise ValueError("La durada del tram ha de ser positiva")
    mode = str(mode or "mixt").strip().lower()
    if mode not in ("graella", "beats", "mixt"):
        mode = "mixt"
    if mode == "graella":
        n_beats = None
    elif mode == "beats" and n_beats is None:
        return []
    if n_beats is not None:
        n_beats = float(n_beats)
        if n_beats <= 0:
            n_beats = None
        if mode == "beats" and n_beats is None:
            return []
    pas_beat = float(pas_beat or 1.0)
    if pas_beat <= 0:
        pas_beat = 1.0
    bpm_ref, num_ref, den_ref = _valida_referencia(
        bpm_ref, num_ref, den_ref)
    (prior_num, prior_den), prior_actiu = _prior_meter(
        meter_prior, num_ref, den_ref)
    bpm_min = limits.BPM_MIN if bpm_min is None else float(bpm_min)
    bpm_max = limits.BPM_MAX if bpm_max is None else float(bpm_max)

    bar_ref = _bar_quarters(num_ref, den_ref) * 60.0 / bpm_ref
    n_previst = max(1, int(round(durada / bar_ref)))
    n_fix = n_ref is not None
    beats_inferits = False
    if n_beats is None and not n_fix and mode == "mixt":
        beats_ref = durada * bpm_ref / 60.0
        n_round = int(round(beats_ref))
        if n_round >= 1 and abs(beats_ref - n_round) <= 0.2:
            n_beats = float(n_round)
            beats_inferits = True

    out = []

    def _afegeix(cost, bpm, num, den, n):
        out.append(_resultat_candidat(
            cost, bpm, num, den, n, bpm_ref, num_ref, den_ref,
            prior_num, prior_den, prior_actiu, n_previst, n_beats,
            n_fix, beats_inferits))

    if n_beats is not None:
        # Regla del múltiple (compàs LOCAL): si encaixa exacta, és candidat.
        bq_ref = _bar_quarters(num_ref, den_ref)
        if bq_ref > 1.0 + 1e-9:
            n_ref_mult = int(round(float(n_beats) / bq_ref))
            if (n_ref_mult >= 1
                    and abs(n_ref_mult * bq_ref - float(n_beats)) <= 0.25
                    and (not n_fix or n_ref_mult == int(n_ref))):
                bpm_ref_mult = 60.0 * n_ref_mult * bq_ref / durada
                if bpm_min - 1e-9 <= bpm_ref_mult <= bpm_max + 1e-9:
                    _afegeix(0.0, bpm_ref_mult, num_ref, den_ref,
                             n_ref_mult)
        for cost, _db, _dc, bpm, num, den, n in _candidats_per_beats(
                durada, bpm_ref, num_ref, den_ref, prior_num, prior_den,
                prior_actiu, n_beats, n_previst, n_fix, n_ref, bloca_compas,
                bpm_min, bpm_max, n_max,
                w_bpm, w_compas, w_n, w_natural, w_den):
            _afegeix(cost, bpm, num, den, n)
    else:
        if n_fix:
            n_valors = [int(n_ref)]
            n_cost_ref = int(n_ref)
        else:
            n_valors = range(max(1, n_previst - int(n_ventana)),
                             n_previst + int(n_ventana) + 1)
            n_cost_ref = n_previst
        for (cost, _dn, _db, _dc, bpm, num, den,
             n) in _candidats_per_durada(
                durada, bpm_ref, num_ref, den_ref, prior_num, prior_den,
                prior_actiu, n_valors, n_cost_ref, bloca_compas,
                bpm_min, bpm_max,
                w_bpm, w_compas, w_n, w_natural, w_den):
            _afegeix(cost, bpm, num, den, n)

    vist = set()
    unics = []
    for c in sorted(out, key=lambda x: (x["cost"], x["n"],
                                        x["num"], x["den"])):
        clau = _clau_candidat(c)
        if clau in vist:
            continue
        vist.add(clau)
        unics.append(c)
    # Per al classificador, «alternatives» vol dir combinacions amb un cost
    # semblant; la resta no són candidats reals per a l'usuari.
    if unics:
        millor_cost = unics[0]["cost"]
        unics = [c for c in unics
                 if c["cost"] <= millor_cost + COST_PROPER + 1e-12]
    return unics


def _factor_sospitos(ratio):
    """Factor 1,5×/2×/3× (o invers) del BPM respecte de la Ref., si n'hi ha."""
    try:
        ratio = float(ratio)
    except (TypeError, ValueError):
        return None
    if ratio <= 0:
        return None
    for f in FACTORS_SOSPITOSOS:
        if abs(ratio - f) <= MARGE_FACTOR * f:
            return f
        inv = 1.0 / f
        if abs(ratio - inv) <= MARGE_FACTOR * inv:
            return f
    return None


def classifica_recalc(millor, candidats=None, *, bpm_ref=None,
                      num_ref=None, den_ref=None, meter_prior=None,
                      unitat_actual=None, unitat_suggerida=None,
                      frontera_ambigua=False, beats_requerits=False,
                      rang_valid=True):
    """Classifica un resultat de recalc: ALT, MITJÀ o BAIX (funció PURA).

    - **ALT**: un sol candidat factible, cost ≤ `COST_ALT`,
      |log2(bpm/bpm_ref)| ≤ `DESVIACIO_BPM_ALT`, sense beats ajustats, sense
      sospita d'octava/factor, sense canvi de compàs/N ni conflicte
      unitat/compàs.
    - **MITJÀ**: hi ha candidat factible però amb canvi estructural, beats
      ajustats, candidats propers, cost alt (> `COST_MITJA_AVIS` amb avís) o
      sospita de factor 1,5×/2×/3× (que NO s'aplica automàticament).
    - **BAIX**: condició DURA: cap candidat, rang invàlid, conflicte real
      unitat/compàs (`encaixa_en_compas` falla), frontera ambigua o beats no
      resolubles.

    La sospita d'octava/factor és MITJÀ, no BAIX: el motor no decidix per tu.
    Els llindars són constants públiques i deterministes.
    """
    candidats = list(candidats or ())
    motius = []
    if not rang_valid:
        return _classificacio(NIVELL_BAIX, ["rang invàlid"],
                              unitat_suggerida)
    if millor is None:
        if unitat_suggerida is not None and unitat_actual is not None:
            motiu = (f"conflicte real unitat/compàs ({unitat_actual} no "
                     f"encaixa; suggerida {unitat_suggerida})")
        else:
            motiu = ("beats no resolubles" if beats_requerits
                     else "cap candidat")
        return _classificacio(NIVELL_BAIX, [motiu], unitat_suggerida)

    num, den = int(millor["num"]), int(millor["den"])
    if unitat_actual is not None and not bpm_unit.encaixa_en_compas(
            unitat_actual, num, den):
        if unitat_suggerida is None:
            unitat_suggerida = bpm_unit.unitat_per_defecte(num, den)
        return _classificacio(
            NIVELL_BAIX,
            [f"conflicte real unitat/compàs ({unitat_actual} no dividix "
             f"{num}/{den})"], unitat_suggerida)
    if frontera_ambigua:
        return _classificacio(NIVELL_BAIX, ["frontera ambigua"],
                              unitat_suggerida)

    if bpm_ref is None:
        bpm_ref = millor.get("bpm_ref", millor.get("bpm"))
    if num_ref is None or den_ref is None:
        local = millor.get("compas_local") or millor.get("compas_ref")
        if local:
            num_ref, den_ref = int(local[0]), int(local[1])
    cost = float(millor.get("cost") or 0.0)
    ratio = float(millor["bpm"]) / float(bpm_ref) if bpm_ref else 1.0
    factor = _factor_sospitos(ratio)

    if millor.get("beats_ajustats"):
        motius.append("beats ajustats")
    if factor is not None:
        motius.append(f"sospita de factor {factor:g}× (no auto-aplicar)")
    if millor.get("sospita_octava") and factor is None:
        motius.append("sospita d'octava (no auto-aplicar)")
    canvis = millor.get("canvis") or {}
    if canvis.get("compas"):
        motius.append("canvi de compàs")
    if canvis.get("n"):
        motius.append("canvi de N")
    if cost > COST_MITJA_AVIS:
        motius.append(f"cost alt ({cost:.3f}); revisa el resultat")
    elif cost > COST_ALT:
        motius.append(f"cost per damunt del llindar ALT ({cost:.3f})")
    if abs(math.log2(ratio)) > DESVIACIO_BPM_ALT:
        motius.append("BPM allunyat de la Ref.")
    if len(candidats) > 1:
        propers = [
            c for c in candidats
            if _clau_candidat(c) != _clau_candidat(millor)
            and float(c.get("cost") or 0.0) <= cost + COST_PROPER]
        if propers:
            motius.append(
                f"{len(propers)} candidat(s) proper(s) amb cost semblant")
        else:
            motius.append(f"{len(candidats)} candidats factibles")
    if motius:
        return _classificacio(NIVELL_MITJA, motius, unitat_suggerida)
    return _classificacio(NIVELL_ALT, ["candidat únic i estable"],
                          unitat_suggerida)


def _classificacio(nivell, motius, unitat_suggerida=None):
    """Resultat uniforme del classificador (també per a la UI)."""
    return {
        "nivell": nivell,
        "classificacio": nivell,
        "motius": list(motius),
        "avis": "; ".join(motius),
        "unitat_suggerida": unitat_suggerida,
    }


def recalculca_tram_amb_candidats(
        durada, bpm_ref, num_ref, den_ref, n_ref=None, *,
        n_beats=None, mode="mixt", bloca_compas=False,
        bpm_min=None, bpm_max=None, n_ventana=3,
        w_bpm=1.0, w_compas=1.5, w_n=3.0, w_natural=0.1,
        w_den=1.5, n_max=16, ajusta_beats=True, pas_beat=1.0,
        meter_prior=None, unitat_actual=None, frontera_ambigua=False):
    """Recalc + candidats + classificació ALT/MITJÀ/BAIX (API per a la UI).

    Retorna un diccionari::

        {"millor": <resultat o None>,
         "candidats": [<resultats alternatius>],
         "classificacio": "ALT"|"MITJÀ"|"BAIX",
         "motius": [...], "unitat_suggerida": str|None}

    Si es passa `unitat_actual`, s'aplica el filtre L3: només es consideren
    candidats que `bpm_unit.encaixa_en_compas` accepta. Si cap encaixa,
    `millor` és `None` (la UI ha de conservar el valor anterior) i
    `unitat_suggerida` indica la unitat que caldria aprovar. La unitat mai no
    es canvia en silenci.
    """
    kw = dict(
        n_ref=n_ref, n_beats=n_beats, mode=mode, bloca_compas=bloca_compas,
        bpm_min=bpm_min, bpm_max=bpm_max, n_ventana=n_ventana,
        w_bpm=w_bpm, w_compas=w_compas, w_n=w_n, w_natural=w_natural,
        w_den=w_den, n_max=n_max, ajusta_beats=ajusta_beats,
        pas_beat=pas_beat, meter_prior=meter_prior)
    try:
        millor = recalculca_tram(durada, bpm_ref, num_ref, den_ref, **kw)
        candidats = _enumera_candidats(
            durada, bpm_ref, num_ref, den_ref, **kw)
    except ValueError:
        classif = classifica_recalc(
            None, [], bpm_ref=bpm_ref, num_ref=num_ref, den_ref=den_ref,
            meter_prior=meter_prior, unitat_actual=unitat_actual,
            frontera_ambigua=frontera_ambigua, rang_valid=False)
        classif["millor"] = None
        classif["candidats"] = []
        return classif
    if millor is not None:
        claus = {_clau_candidat(c) for c in candidats}
        if _clau_candidat(millor) not in claus:
            candidats.append(dict(millor))
        candidats.sort(key=lambda x: (x["cost"], x["n"], x["num"], x["den"]))

    unitat_suggerida = None
    if unitat_actual is not None and millor is not None:
        if not bpm_unit.encaixa_en_compas(
                unitat_actual, millor["num"], millor["den"]):
            valids = [
                c for c in candidats
                if bpm_unit.encaixa_en_compas(
                    unitat_actual, c["num"], c["den"])]
            if valids:
                millor = min(valids,
                             key=lambda c: (c["cost"], c["n"],
                                            c["num"], c["den"]))
            else:
                unitat_suggerida = bpm_unit.unitat_per_defecte(
                    millor["num"], millor["den"])
                millor = None
    classif = classifica_recalc(
        millor, candidats, bpm_ref=bpm_ref, num_ref=num_ref,
        den_ref=den_ref, meter_prior=meter_prior,
        unitat_actual=unitat_actual, unitat_suggerida=unitat_suggerida,
        frontera_ambigua=frontera_ambigua,
        beats_requerits=(mode == "beats" or n_beats is not None))
    classif["millor"] = millor
    classif["candidats"] = candidats
    return classif


def avis_de_resultat(resultat):
    """Text combinat d'avisos d'un resultat de `recalculca_tram`.

    No decidix res: només descriu beats ajustats, desviació de BPM i sospita
    d'octava. Retorna "" si no hi ha cap avís.
    """
    if not resultat:
        return ""
    parts = []

    def _fmt(v):
        return "—" if v is None else f"{float(v):g}"

    if resultat.get("beats_ajustats"):
        if resultat.get("beats_inferits"):
            parts.append(
                "sense beats detectats; durada incompatible amb compassos "
                f"sencers ({_fmt(resultat.get('beats_detectats'))}→"
                f"{_fmt(resultat.get('beats'))} negres)")
        else:
            parts.append(
                f"beats ajustats {_fmt(resultat.get('beats_detectats'))}→"
                f"{_fmt(resultat.get('beats'))}")
    desviacio = float(resultat.get("desviacio_bpm") or 0.0)
    if abs(desviacio) > LLINDAR_DESVIACIO_BPM:
        parts.append(f"BPM desviat {desviacio * 100.0:+.1f}%")
    if resultat.get("sospita_octava"):
        parts.append("sospita d'octava")
    return "; ".join(parts)
