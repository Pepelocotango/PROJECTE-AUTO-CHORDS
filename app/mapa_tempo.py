"""Model unificat del mapa de tempo/compàs (`mapa_tempo.csv`).

Subplà de rubato, fase 2. Este mòdul és la **capa de dades** del model:

    inici,fi,bpm,tipus,compassos

- `tipus`: `normal` o `rubato`.
- `compassos`: forma canònica ASCII (`4/4` o `4/4*2+6/8`).

Els clips normals tenen **un sol compàs**; els rubato poden tindre una
seqüència de fins a 4 compassos, amb un sol BPM derivat.

El mòdul és pur respecte de Qt. La integració amb el projecte, el visor i
l'exportació es fa a `pipeline`/`visor`; ací es defineix el model i el fitxer.
"""

from dataclasses import dataclass
import csv
import os
from decimal import Decimal, ROUND_HALF_UP

from app import rubato
from app import tempo_map


NOM_MAPA_TEMPO = "mapa_tempo.csv"
NOM_CSV_TEMPO_ANTIC = "tempo.csv"
NOM_CSV_COMPAS_ANTIC = "compas.csv"

#: Capçalera del fitxer (es llig i s'ignora en carregar).
CAPCALERA = ("inici", "fi", "bpm", "tipus", "compassos")

#: Decimals de temps i BPM (els mateixos que el model anterior).
TEMPS_DEC = 6
BPM_DEC = 6


@dataclass(frozen=True)
class TramMapa:
    """Un tram del mapa de tempo/compàs.

    És compatible amb el model antic de 5 tuples: `iter()` i `[]` retornen
    `(ini, fi, bpm, num, den)`, on `num`/`den` són el **primer** compàs de la
    seqüència. Això permet que el codi existent seguisca funcionant mentre la
    fase 3 incorpora la graella completa dels rubatos.
    """

    ini: float
    fi: float
    bpm: float
    tipus: str = "normal"
    compassos: str = "4/4"

    def __post_init__(self):
        tipus = str(self.tipus or "").strip().lower()
        if tipus not in ("normal", "rubato"):
            raise rubato.RubatoError(
                f"Tipus de tram no vàlid: {self.tipus!r}")
        object.__setattr__(self, "tipus", tipus)
        text = str(self.compassos or "").strip()
        segs = rubato.text_a_compassos(text)
        if tipus == "normal" and (len(segs) != 1 or segs[0][2] != 1):
            raise rubato.RubatoError(
                "Un clip normal ha de tindre un sol compàs sense repeticions")
        object.__setattr__(self, "compassos", text)

    @property
    def segments(self):
        return rubato.text_a_compassos(self.compassos)

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
            return (self.ini, self.fi, self.bpm, self.tipus, self.compassos) == (
                other.ini, other.fi, other.bpm, other.tipus, other.compassos)
        if isinstance(other, (tuple, list)) and len(other) == 5:
            return tuple(self) == tuple(other)
        return NotImplemented

    def __hash__(self):
        return hash((self.ini, self.fi, self.bpm, self.tipus, self.compassos))

    @property
    def payload(self):
        return (self.bpm, self.num, self.den)

    @property
    def lliure(self):
        return self.tipus == "rubato"

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
    ini, fi, bpm, num, den = tram
    return TramMapa(float(ini), float(fi), float(bpm), "normal",
                    f"{int(num)}/{int(den)}")


def a_tuples(trams):
    """Vista de 5 tuples (per al codi que encara no coneix `TramMapa`)."""
    return [tuple(t) for t in trams]


def normalitza_trams_map(trams, durada, log=None, fusiona=False):
    """Normalitza el mapa preservant `tipus`/`compassos`.

    Sense rubatos, delega en `tempo_map.neteja_trams` + `fusiona_trams_iguals`
    (comportament idèntic al model anterior). Amb rubatos, garantix ordre,
    cobertura i contigüitat; si la durada d'un rubato canvia, recalcula el seu
    BPM a partir de la seqüència i la durada. Fusiona rubatos adjacents quan
    la seqüència resultant cap en 4 segments.
    """
    trams = [des_de_tupla(t) for t in (trams or ())]
    if not any(t.tipus == "rubato" for t in trams):
        net, avisos = tempo_map.neteja_trams(
            [tuple(t) for t in trams], durada)
        if fusiona:
            net = tempo_map.fusiona_trams_iguals(net, durada)
        return [des_de_tupla(t) for t in net], avisos

    avisos = []
    durada = float(durada or 0.0)
    if not trams:
        return [], avisos
    trams.sort(key=lambda t: t.ini)
    # Cobertura dels extrems (el primer a 0, l'últim a la durada).
    p = trams[0]
    if p.ini > tempo_map.TOL or p.ini < 0:
        trams[0] = TramMapa(0.0, p.fi, p.bpm, p.tipus, p.compassos)
    u = trams[-1]
    if durada > tempo_map.TOL and (u.fi < durada - tempo_map.TOL
                                   or u.fi > durada + tempo_map.TOL):
        trams[-1] = TramMapa(u.ini, durada, u.bpm, u.tipus, u.compassos)

    out = []
    for t in trams:
        ini = 0.0 if not out else float(out[-1].fi)
        fi = float(t.fi)
        if durada > tempo_map.TOL:
            fi = min(fi, durada)
        if fi <= ini + tempo_map.TOL:
            avisos.append(f"tram buit o invertit a {ini:.3f}s; s'ha descartat")
            continue
        tipus = t.tipus
        bpm = float(t.bpm)
        compassos = t.compassos
        if tipus == "rubato":
            segs = t.segments
            quarters = sum(n * 4.0 / d * c for n, d, c in segs)
            if quarters > 0:
                bpm = quarters * 60.0 / (fi - ini)
                if not (30.0 - 1e-9 <= bpm <= 350.0 + 1e-9):
                    avisos.append(
                        f"rubato {ini:.3f}–{fi:.3f}s: BPM derivat fora de "
                        "30–350; es conserva el valor antic")
                    bpm = float(t.bpm)
                bpm = min(max(bpm, 30.0), 350.0)
        nou = TramMapa(ini, fi, bpm, tipus, compassos)
        if fusiona and out:
            prev = out[-1]
            if (prev.tipus == "normal" and nou.tipus == "normal"
                    and abs(prev.bpm - nou.bpm) <= tempo_map.TOL
                    and (prev.num, prev.den) == (nou.num, nou.den)):
                out[-1] = TramMapa(prev.ini, nou.fi, prev.bpm,
                                   "normal", prev.compassos)
                continue
            if prev.tipus == "rubato" and nou.tipus == "rubato":
                segs = rubato._fusiona(list(prev.segments) + list(nou.segments))
                if len(segs) <= rubato.MAX_SEGMENTS:
                    quarters = sum(n * 4.0 / d * c for n, d, c in segs)
                    bpm = quarters * 60.0 / (nou.fi - prev.ini)
                    if 30.0 - 1e-9 <= bpm <= 350.0 + 1e-9:
                        out[-1] = TramMapa(
                            prev.ini, nou.fi, min(max(bpm, 30.0), 350.0),
                            "rubato", rubato.compassos_a_text(segs))
                        continue
                    avisos.append(
                        "dos rubatos adjacents no s'han pogut fusionar per "
                        "BPM fora de 30–350")
        out.append(nou)
    return out, avisos


def _arrodoneix_bpm(bpm, decimals):
    """Arredonix un BPM positiu amb ROUND_HALF_UP (0,5 sempre cap amunt)."""
    decimals = max(0, int(decimals))
    quant = Decimal(1).scaleb(-decimals) if decimals else Decimal(1)
    return float(Decimal(str(float(bpm))).quantize(
        quant, rounding=ROUND_HALF_UP))


def quantitza_bpm(trams, durada, decimals=1, offset=0.0):
    """Quantitza el BPM dels trams **normals** a `decimals` decimals.

    Conserva el nombre enter de compassos de cada clip normal i recalcula el
    seu fi; els inicis dels clips següents es desplacen en conseqüència. Els
    rubatos **no es quantitzen**: conserven el BPM i la seqüència, però la seua
    finestra es pot desplaçar perquè el mapa continue contigu. L'últim tram
    acaba a `durada` (excepció permesa a l'últim final).

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
        if (not first.lliure and abs(float(first.ini)) <= 1e-9
                and abs(float(first.fi) - offset) <= 1e-6):
            # Pre-roll: es conserva sencer (BPM, compàs i fi). La música
            # comença exactament a l'offset.
            out.append(first)
            cursor = float(first.fi)
            inici_loop = 1
        elif (not first.lliure and abs(float(first.ini)) <= 1e-9
              and float(first.fi) < offset - 1e-6):
            raise ValueError(
                "El pre-roll acaba abans de l'offset; no es pot quantitzar "
                "sense moure el compàs 1. Restaura el mapa o ajusta l'offset.")
    for tr in net[inici_loop:]:
        dur = max(0.0, float(tr.fi) - float(tr.ini))
        if tr.tipus == "rubato":
            fi = cursor + dur
            out.append(TramMapa(cursor, fi, float(tr.bpm), "rubato",
                                tr.compassos))
            cursor = fi
            continue
        bq = float(tr.num) * 4.0 / float(tr.den)
        if bq <= 0:
            raise ValueError("Hi ha un compàs sense durada vàlida")
        n = max(1, int(round(dur * float(tr.bpm) / (bq * 60.0))))
        bpm = _arrodoneix_bpm(float(tr.bpm), decimals)
        if bpm <= 0:
            raise ValueError("Hi ha un BPM no vàlid")
        fi = cursor + n * bq * 60.0 / bpm
        out.append(TramMapa(cursor, fi, bpm, "normal",
                            f"{int(tr.num)}/{int(tr.den)}"))
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
                               last.compassos)
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
            if len(fila) != 5:
                if log:
                    log(f"{NOM_MAPA_TEMPO} fila {n}: columnes incorrectes; "
                        "s'ha descartat")
                continue
            try:
                tm = TramMapa(float(fila[0]), float(fila[1]), float(fila[2]),
                              fila[3], fila[4])
            except (ValueError, rubato.RubatoError) as e:
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
