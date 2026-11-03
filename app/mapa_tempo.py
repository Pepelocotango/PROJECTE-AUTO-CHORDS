"""Model unificat del mapa de tempo/compàs (`mapa_tempo.csv`).

Subplà de rubato, fase 2. Este mòdul és la **capa de dades** del model:

    inici,fi,bpm,tipus,compassos

- `tipus`: `normal` o `rubato`.
- `compassos`: forma canònica ASCII (`4/4` o `4/4*3+3/4`).

Els clips normals tenen **un sol compàs**; els rubato poden tindre una
seqüència de fins a 4 compassos, amb un sol BPM derivat.

El mòdul és pur respecte de Qt. La integració amb el visor, el projecte i
l'exportació es fa en la fase 2b/3; ací només es llig i s'escriu el fitxer.
"""

from dataclasses import dataclass
import csv
import os

from app import rubato


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
        if tipus == "normal" and (len(segs) != 1 or segs[0][1] != 1):
            raise rubato.RubatoError(
                "Un clip normal ha de tindre un sol compàs sense repeticions")
        object.__setattr__(self, "compassos", text)

    @property
    def segments(self):
        return rubato.text_a_compassos(self.compassos)

    @property
    def den(self):
        primer = self.compassos.split("+", 1)[0]
        return int(primer.split("/", 1)[1].split("*", 1)[0])

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
