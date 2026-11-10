"""Model unificat del mapa de tempo/compàs (`mapa_tempo.csv`).

Este mòdul és la **capa de dades** del model:

    inici,fi,bpm,tipus,compassos,agrupacio,n

- `tipus`: `normal` o `rubato`. El rubato és **només un flag de notació**: el
  tram té els mateixos camps i la mateixa graella que un normal.
- `compassos`: un sol compàs ASCII (`4/4`, `6/8`); mai una seqüència.
- `agrupacio`: `3+3` (opcional) o buit per a l’agrupació automàtica.
- `n`: nombre de compassos (opcional; buit = encara no fixat).

El mòdul és pur respecte de Qt. La integració amb el projecte, el visor i
l'exportació es fa a `pipeline`/`visor`; ací es defineix el model i el fitxer.
"""

from dataclasses import dataclass, replace
import csv
import math
import os
import re
from decimal import Decimal, ROUND_HALF_UP

from app import limits, tempo_recalc
from app import tempo_map


NOM_MAPA_TEMPO = "mapa_tempo.csv"
NOM_CSV_TEMPO_ANTIC = "tempo.csv"
NOM_CSV_COMPAS_ANTIC = "compas.csv"

#: Capçalera del fitxer (es llig i s'ignora en carregar).
CAPCALERA = ("inici", "fi", "bpm", "tipus", "compassos",
             "agrupacio", "n")

#: Decimals de temps i BPM (els mateixos que el model anterior).
TEMPS_DEC = 6
BPM_DEC = 6


_RE_COMPAS = re.compile(r"^(\d{1,2})/(\d{1,2})$")


def _segments_compas(text):
    """Valida un **sol** compàs ASCII i en retorna els segments.

    El model nou no admet seqüències (`+`), repeticions (`*`) ni `0/0`: un
    rubato és idèntic a un normal i només canvia el flag `tipus`.
    """
    s = str(text or "").strip()
    m = _RE_COMPAS.match(s)
    if not m:
        raise ValueError(
            f"El compàs «{text}» no és vàlid: cal un sol compàs num/den "
            "(sense «+», «*» ni 0/0)")
    num, den = int(m.group(1)), int(m.group(2))
    if not limits.NUM_MIN <= num <= limits.NUM_MAX:
        raise ValueError(
            f"El numerador ha d'estar entre {limits.NUM_MIN} i "
            f"{limits.NUM_MAX}")
    if den not in limits.DENOMINADORS_ADMESOS:
        valors = ", ".join(str(x) for x in limits.DENOMINADORS_ADMESOS)
        raise ValueError(f"El denominador ha de ser {valors}")
    return ((num, den, 1),)


@dataclass(frozen=True)
class TramMapa:
    """Un tram del mapa de tempo/compàs.

    És compatible amb el model antic de 5 tuples: `iter()` i `[]` retornen
    `(ini, fi, bpm, num, den)`. `segments` també retorna una tupla de segments
    (sempre un de sol) per compatibilitat amb el codi antic.
    """

    ini: float
    fi: float
    bpm: float
    tipus: str = "normal"
    compassos: str = "4/4"
    agrupacio: str = ""
    n: float | None = None

    def __post_init__(self):
        tipus = str(self.tipus or "").strip().lower()
        if tipus not in ("normal", "rubato"):
            raise ValueError(f"Tipus de tram no vàlid: {self.tipus!r}")
        object.__setattr__(self, "tipus", tipus)
        text = str(self.compassos or "").strip()
        segs = _segments_compas(text)
        object.__setattr__(self, "compassos", text)
        agr = tempo_map.valida_agrupacio(
            self.agrupacio, segs[0][0], segs[0][1])
        object.__setattr__(self, "agrupacio", agr)
        n = self.n
        if n is not None:
            try:
                n = float(n)
            except (TypeError, ValueError):
                n = None
            if n is not None and (not math.isfinite(n) or n <= 0):
                n = None
        object.__setattr__(self, "n", n)

    @property
    def segments(self):
        return _segments_compas(self.compassos)

    @property
    def den(self):
        return int(self.segments[0][1])

    @property
    def num(self):
        return int(self.segments[0][0])

    def __iter__(self):
        yield float(self.ini)
        yield float(self.fi)
        yield float(self.bpm)
        yield self.num
        yield self.den

    def __getitem__(self, idx):
        return tuple(self)[idx]

    def __len__(self):
        return 5

    def __eq__(self, other):
        """Compatible amb tuples antigues de 5 elements."""
        if isinstance(other, TramMapa):
            return (self.ini, self.fi, self.bpm, self.tipus, self.compassos,
                    self.agrupacio, self.n) == (
                other.ini, other.fi, other.bpm, other.tipus, other.compassos,
                other.agrupacio, other.n)
        if isinstance(other, (tuple, list)) and len(other) == 5:
            return tuple(self) == tuple(other)
        return NotImplemented

    def __hash__(self):
        return hash((self.ini, self.fi, self.bpm, self.tipus,
                      self.compassos, self.agrupacio, self.n))

    @property
    def payload(self):
        return (self.bpm, self.num, self.den)

    @property
    def lliure(self):
        """Un rubato ja no va en segons: sempre és una graella mètrica."""
        return False

    @property
    def num_ef(self):
        return self.num

    @property
    def den_ef(self):
        return self.den

    @property
    def bpm_ef(self):
        return float(self.bpm)


def des_de_tupla(tram):
    """Converteix una tupla antiga `(ini, fi, bpm, num, den)` en `TramMapa`."""
    if isinstance(tram, TramMapa):
        return tram
    agr = tram[5] if len(tram) > 5 else ""
    n = tram[6] if len(tram) > 6 else None
    ini, fi, bpm, num, den = tram[:5]
    return TramMapa(float(ini), float(fi), float(bpm), "normal",
                    f"{int(num)}/{int(den)}", agr, n)


def a_tuples(trams):
    """Vista de 5 tuples (per al codi que encara no coneix `TramMapa`)."""
    return [tuple(t) for t in trams]


def recalcula_tram_c(trams, idx, durada, offset=0.0, *, n=None, bpm=None,
                     num=None, den=None, camp="bpm"):
    """Regla C: edita camps exactes i deriva la frontera `fi`.

    - Trams interiors: `n`, BPM i `x/x` exactes → `fi` derivada. El veí de la
      dreta conserva `n` i `x/x` i **recalcula el BPM** (regla A).
    - Últim/únic: BPM i `x/x` exactes → `n` derivat (pot ser fraccionari). Si
      `camp="n"`, `n` és exacte i es recalcula el BPM amb el `fi` fix.
    """
    net = [des_de_tupla(t) for t in (trams or ())]
    if not net:
        raise ValueError("El mapa de tempo és buit")
    i = int(idx)
    if not (0 <= i < len(net)):
        raise ValueError("El tram de tempo no existeix")
    tr = net[i]
    if tr.tipus == "rubato":
        # El rubato és un flag, però no ha de impedir l'edició.
        pass
    if n is not None:
        n = float(n)
        if n <= 0:
            raise ValueError("N ha de ser positiu")
    bpm = float(tr.bpm if bpm is None else bpm)
    num = int(tr.num if num is None else num)
    den = int(tr.den if den is None else den)
    bpm, num, den = tempo_map.valida_tempo(bpm, num, den)
    base = float(offset) if i == 0 else float(tr.ini)
    ultim = (i == len(net) - 1)

    if ultim:
        # El final de la WAV no es mou.
        dur_fix = float(tr.fi) - base
        if dur_fix <= tempo_map.TOL:
            raise ValueError("El tram no té durada suficient")
        if camp == "n":
            n_final = float(n if n is not None else (
                tr.n if tr.n is not None else
                tempo_recalc.n_de_durada(dur_fix, bpm, num, den)))
            if n_final <= 0:
                raise ValueError("N ha de ser positiu")
            bpm_final = tempo_recalc.bpm_de_n(n_final, num, den, dur_fix)
        else:
            bpm_final = bpm
            n_final = tempo_recalc.n_de_durada(dur_fix, bpm_final, num, den)
        if not (limits.BPM_MIN <= bpm_final <= limits.BPM_MAX):
            raise ValueError("El BPM resultant ix de la banda permesa")
        fi_final = float(tr.fi)
    else:
        if n is not None:
            n_final = float(n)
        elif tr.n is not None:
            n_final = max(1.0, float(tr.n))
        else:
            # N actual es deriva de la referència ANTIGA, no del BPM nou.
            n_final = max(1.0, float(round(tempo_recalc.n_de_durada(
                float(tr.fi) - base, tr.bpm, tr.num, tr.den))))
        try:
            dur_nou = tempo_recalc.durada_de_n(n_final, bpm, num, den)
        except ValueError as e:
            raise ValueError(str(e)) from e
        if dur_nou <= limits.TEMPS_MIN_CLIP:
            raise ValueError("El tram quedaria massa curt")
        fi_final = base + dur_nou
        if fi_final >= float(net[i + 1].fi) - tempo_map.TOL:
            raise ValueError("El tram no cap abans del següent")
        bpm_final = bpm
        n_final = float(n_final)

    nou_tr = TramMapa(
        float(tr.ini), float(fi_final), float(bpm_final), tr.tipus,
        f"{int(num)}/{int(den)}", tr.agrupacio, n_final)
    out = list(net)
    out[i] = nou_tr

    if not ultim:
        seg = net[i + 1]
        n_seg = (float(seg.n) if seg.n is not None else
                 tempo_recalc.n_de_durada(
                     float(seg.fi) - float(seg.ini), seg.bpm,
                     seg.num, seg.den))
        if n_seg <= 0:
            raise ValueError("El tram següent no té cap compàs")
        dur_seg = float(seg.fi) - fi_final
        if dur_seg <= tempo_map.TOL:
            raise ValueError("El veí de la dreta quedaria sense durada")
        bq_seg = float(seg.num) * 4.0 / float(seg.den)
        bpm_seg = float(n_seg) * bq_seg * 60.0 / dur_seg
        if not (limits.BPM_MIN <= bpm_seg <= limits.BPM_MAX):
            raise ValueError(
                "El veí de la dreta quedaria fora de la banda de BPM")
        out[i + 1] = TramMapa(
            fi_final, float(seg.fi), bpm_seg, seg.tipus, seg.compassos,
            seg.agrupacio, n_seg)
    return out


def hereta_agrupacio(antics, nous):
    """Passa l'agrupació i el camp `n` dels trams antics als nous.

    Fa servir el solapament temporal. Tots els tipus es tracten igual: un
    rubato conserva la seua agrupació i `n` com qualsevol tram normal.
    """
    antics = [des_de_tupla(t) for t in (antics or ())]
    out = []
    for n in (nous or ()):
        if n.agrupacio:
            out.append(n)
            continue
        millor = None
        millor_solap = 0.0
        millor_n = None
        millor_n_solap = 0.0
        for a in antics:
            solap = max(0.0, min(n.fi, a.fi) - max(n.ini, a.ini))
            if a.agrupacio and solap > millor_solap + tempo_map.TOL:
                millor, millor_solap = a, solap
            if a.n is not None and solap > millor_n_solap + tempo_map.TOL:
                millor_n, millor_n_solap = a, solap
        if millor is not None:
            try:
                agr = tempo_map.valida_agrupacio(
                    millor.agrupacio, n.num, n.den)
            except ValueError:
                agr = ""
            if agr:
                n = replace(n, agrupacio=agr)
        if (n.n is None and millor_n is not None
                and abs(n.ini - millor_n.ini) <= tempo_map.TOL
                and abs(n.fi - millor_n.fi) <= tempo_map.TOL):
            n = replace(n, n=millor_n.n)
        out.append(n)
    return out


def reenganxa_metadades(antics, nous):
    """Reconstrueix `TramMapa` amb les metadades dels trams antics.

    Les funcions pures de `tempo_map` treballen amb 5 tuples i perden
    `tipus`/`agrupacio`/`n`. Este ajudant els torna a enganxar **sense derivar
    res**: només copia els camps de metadades del tram antic que corresponga
    (mateix inici, després contenidor o, finalment, el de més solapament).
    """
    antics = [des_de_tupla(t) for t in (antics or ())]
    out = []
    for nou in (nous or ()):
        ini, fi = float(nou[0]), float(nou[1])
        triat = next((a for a in antics
                      if abs(ini - float(a.ini)) <= tempo_map.TOL), None)
        if triat is None:
            contenidors = [a for a in antics
                           if float(a.ini) - tempo_map.TOL <= ini
                           and fi <= float(a.fi) + tempo_map.TOL]
            if contenidors:
                triat = min(contenidors,
                            key=lambda a: float(a.fi) - float(a.ini))
        if triat is None:
            millor = 0.0
            for a in antics:
                solap = max(0.0, min(fi, float(a.fi))
                            - max(ini, float(a.ini)))
                if solap > millor:
                    millor, triat = solap, a
        if triat is None and antics:
            triat = antics[0]
        tipus = getattr(triat, "tipus", "normal") if triat else "normal"
        agr = getattr(triat, "agrupacio", "") if triat else ""
        n = getattr(triat, "n", None) if triat else None
        try:
            agr = tempo_map.valida_agrupacio(agr, int(nou[3]), int(nou[4]))
        except (ValueError, TypeError):
            agr = ""
        out.append(TramMapa(float(nou[0]), float(nou[1]), float(nou[2]),
                            tipus, f"{int(nou[3])}/{int(nou[4])}", agr, n))
    return out


def _fusiona_amb_agrupacio(trams):
    """Fusiona veïns idèntics només si també coincidixen tipus i agrupació."""
    out = []
    for t in trams or ():
        if out:
            p = out[-1]
            if (p.tipus == t.tipus
                    and abs(p.bpm - t.bpm) <= tempo_map.TOL
                    and (p.num, p.den) == (t.num, t.den)
                    and p.agrupacio == t.agrupacio):
                n = (p.n + t.n) if (p.n is not None and t.n is not None) else None
                out[-1] = replace(p, fi=t.fi, n=n)
                continue
        out.append(t)
    return out


def normalitza_trams_map(trams, durada, log=None, fusiona=False):
    """Normalitza el mapa preservant `tipus`, `agrupacio` i `n`.

    Tots els trams (normals i rubatos) passen pel **mateix camí**: ordre,
    cobertura i contigüitat de `tempo_map.neteja_trams`. Les metadades es
    reenganxen després per interval; el rubato no deriva BPM ni compassos.
    """
    trams_in = [des_de_tupla(t) for t in (trams or ())]
    if not trams_in:
        return [], []
    base, avisos = tempo_map.neteja_trams(
        [tuple(t) for t in trams_in], durada)
    net = reenganxa_metadades(trams_in, base)
    if fusiona:
        net = _fusiona_amb_agrupacio(net)
    return net, avisos


def _arrodoneix_bpm(bpm, decimals):
    """Arredonix un BPM positiu amb ROUND_HALF_UP (0,5 sempre cap amunt)."""
    decimals = max(0, int(decimals))
    quant = Decimal(1).scaleb(-decimals) if decimals else Decimal(1)
    return float(Decimal(str(float(bpm))).quantize(
        quant, rounding=ROUND_HALF_UP))


def quantitza_bpm(trams, durada, decimals=1, offset=0.0):
    """Quantitza el BPM de **tots** els trams a `decimals` decimals.

    Conserva el nombre enter de compassos de cada clip i recalcula el seu fi;
    els inicis dels clips següents es desplacen en conseqüència. Els rubatos es
    quantitzen igual que els normals: només es conserva el flag `tipus` i la
    resta de metadades. L'últim tram acaba a `durada` (excepció permesa a
    l'últim final).

    Si hi ha un **pre-roll** (primer clip 0 → offset), es conserva intacte:
    no és música i no ha de moure el compàs 1. Els clips musicals es
    quantitzen a partir d'eixe offset.
    """
    durada = float(durada or 0.0)
    decimals = max(0, int(decimals))
    offset = max(0.0, float(offset or 0.0))
    net = [des_de_tupla(t) for t in (trams or ())]
    if not net:
        raise ValueError("El mapa de tempo/compàs és buit")
    out = []
    cursor = 0.0
    inici_loop = 0
    if offset > 1e-6 and net:
        first = net[0]
        if (abs(float(first.ini)) <= 1e-9
                and abs(float(first.fi) - offset) <= 1e-6):
            # Pre-roll: es conserva sencer (BPM, compàs i fi). La música
            # comença exactament a l'offset.
            out.append(first)
            cursor = float(first.fi)
            inici_loop = 1
        elif (abs(float(first.ini)) <= 1e-9
              and float(first.fi) < offset - 1e-6):
            raise ValueError(
                "El pre-roll acaba abans de l'offset; no es pot quantitzar "
                "sense moure el compàs 1. Restaura el mapa o ajusta l'offset.")
    for tr in net[inici_loop:]:
        dur = max(0.0, float(tr.fi) - float(tr.ini))
        bq = float(tr.num) * 4.0 / float(tr.den)
        if bq <= 0:
            raise ValueError("Hi ha un compàs sense durada vàlida")
        n = max(1, int(round(dur * float(tr.bpm) / (bq * 60.0))))
        bpm = _arrodoneix_bpm(float(tr.bpm), decimals)
        if bpm <= 0:
            raise ValueError("Hi ha un BPM no vàlid")
        fi = cursor + n * bq * 60.0 / bpm
        out.append(TramMapa(cursor, fi, bpm, tr.tipus,
                            f"{int(tr.num)}/{int(tr.den)}",
                            tr.agrupacio, tr.n))
        cursor = fi
    if durada > 0:
        last = out[-1]
        if last.ini >= durada - 1e-6:
            raise ValueError(
                "La quantització deixa l'últim clip fora de la WAV; "
                "reduïx el nombre de compassos o el BPM.")
        # L'últim final pot ser parcial (excepció de la regla §13.4): la
        # quantització no ha d'inventar un tram fora de la WAV.
        if abs(last.fi - durada) > 1e-9:
            out[-1] = TramMapa(last.ini, durada, last.bpm, last.tipus,
                               last.compassos, last.agrupacio, last.n)
    return out


def desa_mapa_tempo(ruta, trams):
    """Escriu `mapa_tempo.csv` de manera atòmica.

    Accepta `TramMapa` o tuples antigues `(ini, fi, bpm, num, den)`; en este
    segon cas s'escriuen com a `normal` amb el compàs `num/den`.
    """
    from app import pipeline       # import diferit: evita el cicle

    def _escriu(f):
        w = csv.writer(f)
        w.writerow(CAPCALERA)
        for t in trams or ():
            tm = des_de_tupla(t)
            w.writerow([
                f"{float(tm.ini):.{TEMPS_DEC}f}",
                f"{float(tm.fi):.{TEMPS_DEC}f}",
                f"{float(tm.bpm):.{BPM_DEC}f}",
                tm.tipus,
                tm.compassos,
                tm.agrupacio,
                "" if tm.n is None else f"{float(tm.n):.{BPM_DEC}f}",
            ])

    pipeline.escriu_atomic(ruta, _escriu)
    return ruta


def llegeix_mapa_tempo(ruta, log=None):
    """Llig `mapa_tempo.csv` i retorna una llista de `TramMapa`.

    Les files mal formades es descarten amb una traça al log. La reparació de
    cobertura/ordre la fa la capa de mapa (`tempo_map`), com abans.
    """
    out = []
    if not ruta or not os.path.isfile(ruta):
        return out
    with open(ruta, encoding="utf-8") as f:
        for n, fila in enumerate(csv.reader(f), 1):
            if not fila:
                continue
            if str(fila[0]).strip().lower() == "inici":
                continue
            if len(fila) not in (5, 6, 7):
                if log:
                    log(f"{NOM_MAPA_TEMPO} fila {n}: columnes incorrectes; "
                        "s'ha descartat")
                continue
            comp = str(fila[4]).strip()
            if ("+" in comp or "*" in comp
                    or comp.replace(" ", "") in ("0/0", "0")):
                raise ValueError(
                    f"{NOM_MAPA_TEMPO} fila {n}: rubato antic amb seqüència "
                    f"«{comp}»; este projecte no és compatible. Cal recrear "
                    "el mapa amb rubato com a flag.")
            try:
                tm = TramMapa(float(fila[0]), float(fila[1]), float(fila[2]),
                              fila[3], fila[4],
                              fila[5] if len(fila) > 5 else "",
                              fila[6] if len(fila) > 6 else None)
            except ValueError as e:
                if log:
                    log(f"{NOM_MAPA_TEMPO} fila {n}: {e}; s'ha descartat")
                continue
            out.append(tm)
    return out


def te_format_antic(carpeta):
    """Hi ha el model antic (`tempo.csv` + `compas.csv`) en una carpeta?"""
    if not carpeta:
        return False
    return (os.path.isfile(os.path.join(carpeta, NOM_CSV_TEMPO_ANTIC))
            or os.path.isfile(os.path.join(carpeta, NOM_CSV_COMPAS_ANTIC)))
