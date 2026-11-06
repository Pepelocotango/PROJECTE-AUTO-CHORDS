"""Model pur de clips d'AUTO CHORDS (refactor F1 de `pipeline.py`).

Conté el tipus `Clip`, les conversions acords/seccions, els invariants de
cobertura i les operacions de clips que no depenen de fitxers ni de Qt.

La façana `app.pipeline` re-exporta tots estos símbols perquè la resta de
mòduls i els tests continuen funcionant igual.
"""
from collections import namedtuple

# Tolerància compartida per als temps (evita falsos positius per coma flotant).
# La fan servir la normalització de cobertura i els validadors del visor.
TOL_TEMPS = 1e-6
# Separació mínima PRÀCTICA per a l'edició manual: 1 ms. La resolució de
# guardat és 1 µs, però dos canvis d'acord a menys d'1 ms no tenen sentit
# musical i fan clips inútils. No s'ha de confondre amb `RESOLUCIO_CSV`.
MIN_GAP_TEMPS = 0.001

# Resolució temporal unificada dels CSV: 6 decimals (1 µs). És la MATEIXA
# unitat per als fitxers editables (`acords.csv`, `estructura_ABC.csv`,
# `mapa_tempo.csv` i `marcadors.csv`): el model no ha de tindre una resolució
# per a cada fitxer. La UI en mostra 3 (mil·lisegons); el model en guarda 6.
TEMPS_DEC = 6
# Distància MÍNIMA entre dos temps del CSV perquè els seus arrodoniments siguin
# DIFERENTS. Amb menys, dues files cauen al mateix instant del CSV → un clip de
# durada 0 a l'export (i la suma de durades ja no quadra).
RESOLUCIO_CSV = 10.0 ** -TEMPS_DEC


# --- Model unificat de CLIPS (refactor «inici+fi») -------------------------
# Un SOL tipus per a acords i estructura: `Clip(ini, fi, payload)`, on el
# `payload` és tot el que no és temps:
#   · acords:     `(nom, tsrc)` — p. ex. `("Am", "16.153846154")`;
#   · estructura: `(lletra, família)` — p. ex. `("A", "A")`.
# La font única de veritat és la CADENA DE FRONTERES: el `fi` se'n deriva i, per
# tant, no pot quedar mai incoherent.
_ClipBase = namedtuple("Clip", ("ini", "fi", "payload"))


class Clip(_ClipBase):
    """Estructura única de clip: interval `[ini, fi)` amb `payload`."""

    @property
    def nom(self):
        p = self.payload
        return p[0] if isinstance(p, tuple) else p


def clips_d_acords(acords, durada):
    """Converteix acords a `Clip` amb el `fi` derivat de la cadena de fronteres."""
    durada = float(durada or 0.0)
    acords = list(acords or ())
    out = []
    for i, a in enumerate(acords):
        if isinstance(a, Clip):
            out.append(a)
        else:
            fi = float(acords[i + 1][0]) if i + 1 < len(acords) else durada
            out.append(Clip(float(a[0]), fi, tuple(a[1:])))
    return out


def acords_de_clips(clips):
    """`Clip` → acords `(t, nom, tsrc)`: només la frontera d'inici."""
    return [(float(c.ini),) + tuple(c.payload) for c in clips]


def clips_de_seccions(seccions):
    """Seccions `(ini, fi, lletra, família)` → `Clip`."""
    return [s if isinstance(s, Clip) else Clip(float(s[0]), float(s[1]), tuple(s[2:]))
            for s in (seccions or ())]


def seccions_de_clips(clips):
    """`Clip` → seccions `(ini, fi, lletra, família)`."""
    return [(float(c.ini), float(c.fi)) + tuple(c.payload) for c in clips]


def normalitza_clips(clips, durada, forat, arrodoneix=False, deriva_fi=False,
                     log=None):
    """XARXA DE SEGURETAT única dels invariants #1, #2, #4 i #8 (model de clips).

    - **#1 ordre estricte**: clips ordenats per `ini` (`sort` estable).
    - **#2 contigüitat**: la frontera entre dos clips és una de sola → si dos
      clips es trepitgen, el primer s'acota a l'`ini` del segon (o s'elimina si
      queda sense espai); si hi ha un forat, es tapa amb un clip de payload `forat`.
    - **#4 cobertura**: si el primer no arrenca a 0 s'hi posa una capçalera
      `forat`, i el `fi` de l'últim s'acota a `durada`.
    - **#8 temps vàlids**: cap inici negatiu ni durada ≤ 0.

    Retorna una llista NOVA de `Clip`; no muta l'entrada.
    """
    durada = float(durada or 0.0)
    ordenats = sorted(
        (c if isinstance(c, Clip) else Clip(float(c[0]), float(c[1]), tuple(c[2]))
         for c in (clips or ())),
        key=lambda c: float(c.ini))
    net, fora, n_neg = [], 0, 0
    for c in ordenats:
        ini, fi = float(c.ini), float(c.fi)
        if deriva_fi:
            if ini < 0.0:
                ini = 0.0
                n_neg += 1
        else:
            if fi <= 0.0:
                n_neg += 1
                continue
            if ini < 0.0:
                ini = 0.0
                n_neg += 1
        if durada > 0:
            ref = round(ini, TEMPS_DEC) if arrodoneix else ini
            if ref >= durada - TOL_TEMPS:
                fora += 1
                continue
            fi = min(fi, durada)
        if arrodoneix and net and ini - net[-1].ini < MIN_GAP_TEMPS - TOL_TEMPS:
            if log:
                log(f"cobertura: clip a {ini:.6f} s eliminat (a menys de "
                    f"{MIN_GAP_TEMPS * 1000:.0f} ms del clip anterior, "
                    f"{net[-1].ini:.6f} s)")
            continue
        net.append(Clip(ini, fi, tuple(c.payload)))
    if n_neg and log:
        log(f"cobertura: {n_neg} clip(s) amb temps negatiu ajustats")
    if fora and log:
        log(f"cobertura: {fora} clip(s) fora de la WAV (>= {durada:.2f} s) eliminats")
    net.sort(key=lambda c: c.ini)
    if deriva_fi:
        net = [Clip(c.ini, net[i + 1].ini if i + 1 < len(net) else durada,
                    c.payload) for i, c in enumerate(net)]
    out = []
    for c in net:
        if not deriva_fi and c.fi <= c.ini + TOL_TEMPS:
            continue
        while out and c.ini < out[-1].fi - TOL_TEMPS:
            prev = out[-1]
            if c.ini <= prev.ini + TOL_TEMPS:
                out.pop()
                continue
            out[-1] = Clip(prev.ini, c.ini, prev.payload)
            break
        if out and c.ini > out[-1].fi + TOL_TEMPS:
            out.append(Clip(out[-1].fi, c.ini, tuple(forat)))
            if log:
                log(f"cobertura: forat {out[-2].fi:.2f}–{c.ini:.2f} s tapat "
                    f"amb «{forat[0]}»")
        out.append(c)
    if out and out[0].ini > 1e-9:
        out.insert(0, Clip(0.0, out[0].ini, tuple(forat)))
        if log:
            log(f"cobertura: capçalera «{forat[0]}» a 0 ({out[1].ini:.2f} s)")
    if out and durada > 0 and out[-1].fi < durada - 1e-9:
        ult = out[-1]
        out[-1] = Clip(ult.ini, durada, ult.payload)
    return out


def model_inicial(durada, log=None):
    """Model MÍNIM per treballar **sense anàlisi** (roadmap §14.1).

    Un sol clip d'acords (marca «N» = sense acord) i un de sol d'estructura
    que cobreixen **tota la cançó**: el punt de partida editable (a partir
    d'aquí, partir/afegir/moure/renombrar). Regla d'or **#4**: els clips han
    de cobrir `[0, durada]`.
    """
    dur = max(0.0, float(durada or 0.0))
    if log:
        log(f"model inicial (sense anàlisi): 1 acord «N» i 1 secció de 0 a "
            f"{dur:.2f}s")
    return ([Clip(0.0, dur, FORAT_ACORD)], [(0.0, dur, "A", "A")])


def normalitza_cobertura(acords, seccions, durada, log=None):
    """Garanteix l'**INVARIANT de COBERTURA** delegant al motor únic `normalitza_clips`."""
    durada = float(durada or 0.0)
    ac_out, sec_out = [], []
    if acords:
        son_clips = isinstance(acords[0], Clip)
        if son_clips:
            ac_out = normalitza_clips(acords, durada, FORAT_ACORD,
                                      arrodoneix=True, deriva_fi=True, log=log)
        else:
            extra = tuple("0.000000000" for _ in acords[0][2:])
            cl = normalitza_clips(
                clips_d_acords(acords, durada), durada,
                (SENSE_ACORD,) + extra, arrodoneix=True, deriva_fi=True,
                log=log)
            ac_out = acords_de_clips(cl)
    if seccions:
        son_clips_s = isinstance(seccions[0], Clip)
        cl_s = seccions if son_clips_s else clips_de_seccions(seccions)
        norm_s = normalitza_clips(cl_s, durada, FORAT_SECCIO, log=log)
        sec_out = norm_s if son_clips_s else seccions_de_clips(norm_s)
    return ac_out, sec_out
def parteix_clips(clips, i, talla, nou_payload=None, marge=MIN_GAP_TEMPS,
                  etiqueta="clip"):
    """Parteix el clip `i` pel temps `talla` (implementació única, #11)."""
    if i < 0 or i >= len(clips):
        raise ValueError(f"índex de {etiqueta} inexistent")
    c = clips[i]
    talla = float(talla)
    if not (c.ini + marge < talla < c.fi - marge):
        raise ValueError(f"el tall ({talla:.2f}s) ha de caure dins "
                         f"{c.ini:.2f}–{c.fi:.2f}s")
    esq = Clip(c.ini, talla, c.payload)
    dreta = Clip(talla, c.fi, c.payload if nou_payload is None else nou_payload)
    return list(clips[:i]) + [esq, dreta] + list(clips[i + 1:])


def fusiona_clips(clips, i, amb="seguent", etiqueta="clip"):
    """Fusiona el clip `i` amb el veí: el de l'esquerra s'estén (un sol nucli)."""
    n = len(clips)
    if n == 0 or i < 0 or i >= n:
        raise ValueError(f"índex de {etiqueta} inexistent")
    if amb == "anterior":
        if i == 0:
            raise ValueError(f"no hi ha {etiqueta} anterior")
        i -= 1
    elif amb != "seguent":
        raise ValueError("amb ha de ser 'seguent' o 'anterior'")
    if i >= n - 1:
        raise ValueError(f"no hi ha {etiqueta} següent")
    a, b = clips[i], clips[i + 1]
    return list(clips[:i]) + [Clip(a.ini, b.fi, a.payload)] + list(clips[i + 2:])

SENSE_SECCIO = "-"      # §6.1: forat explícit d'estructura («sense secció»)
SENSE_ACORD = "N"       # §6.1: forat explícit d'acords («sense acord»)
# --- Operacions úniques sobre CLIPS (S2): una sola implementació -------------
FORAT_ACORD = (SENSE_ACORD, "0.000000000")
FORAT_SECCIO = (SENSE_SECCIO, SENSE_SECCIO)
def redimensiona_clips(clips, idx, vora, t, durada, forat, log=None):
    """ESTIRAR/ENCONGIR una VORA d'un clip (regla §6.3, la mateixa que MOURE).

    El clip editat **mana** al seu tram nou: el que queda **a sota** es **talla**
    o **s'elimina**. **Encongir** deixa un buit que tanca el **veí** (a la dreta
    el següent; a l'esquerra l'anterior); si **no hi ha veí** (primer o últim
    clip) el buit queda perquè `normalitza_clips` hi posi el `forat`.

    `vora`: `"ini"` (esquerra) o `"fi"` (dreta). Retorna una llista NOVA.
    """
    out = [Clip(c.ini, c.fi, c.payload) for c in clips or ()]
    durada = float(durada or 0.0)
    if not (0 <= idx < len(out)) or abs(float(t)) < 1e-12:
        return out
    t = max(0.0, min(durada, float(t)))
    esq = str(vora).strip().lower() in ("ini", "inici", "esquerra", "left")
    c = out[idx]
    if not esq:
        if (abs(t - c.fi) < TOL_TEMPS
                or (t < c.fi and t - c.ini < MIN_GAP_TEMPS - TOL_TEMPS)):
            return out                      # no canvia res (o queda massa curt)
        if t > c.fi:                        # ESTIRAR cap a la dreta
            nous = [Clip(c.ini, t, c.payload)]
            for i, x in enumerate(out):
                if i == idx:
                    continue
                if x.ini >= c.fi - TOL_TEMPS and x.fi <= t + TOL_TEMPS:
                    continue                # cobert del tot → s'elimina
                if x.ini < t - TOL_TEMPS and x.fi > t + TOL_TEMPS:
                    x = Clip(t, x.fi, x.payload)    # contenia t → es talla
                nous.append(x)
            nous.sort(key=lambda z: z.ini)
            return normalitza_clips(nous, durada, forat)
        if idx + 1 >= len(out):             # últim clip: el buit → `forat`
            return normalitza_clips(out + [Clip(t, c.fi, tuple(forat))],
                                    durada, forat)
        out[idx] = Clip(c.ini, t, c.payload)
        s = out[idx + 1]
        out[idx + 1] = Clip(t, s.fi, s.payload)     # el següent s'estira
        return normalitza_clips(out, durada, forat)
    if t < c.ini:                           # ESTIRAR cap a l'esquerra
        nous = [Clip(t, c.fi, c.payload)]
        for i, x in enumerate(out):
            if i == idx:
                continue
            if x.ini >= t - TOL_TEMPS and x.fi <= c.ini + TOL_TEMPS:
                continue                    # cobert del tot → s'elimina
            if x.ini < t - TOL_TEMPS and x.fi > t + TOL_TEMPS:
                x = Clip(x.ini, t, x.payload)   # contenia t → es talla
            nous.append(x)
        nous.sort(key=lambda z: z.ini)
        return normalitza_clips(nous, durada, forat)
    if c.fi - t < MIN_GAP_TEMPS - TOL_TEMPS:
        return out                          # no canvia res (queda massa curt)
    if idx > 0:                             # l'anterior s'estira endavant
        p = out[idx - 1]
        out[idx - 1] = Clip(p.ini, t, p.payload)
    out[idx] = Clip(t, c.fi, c.payload)
    return normalitza_clips(out, durada, forat)
def mou_bloc_clips(clips, first, last, dt, durada, forat, log=None):
    """Moviment d'un BLOC de clips (§6.3; implementació única).

    El bloc **conserva la durada** i **tapa** `[a', b')`: el material de sota es
    **TALLA** (si només queda cobert en part → en sobreviu el tros de fora, amb
    el seu nom) o **S'ELIMINA** (si queda sobrepassat del tot). L'**origen** el
    tanca el veí; si no n'hi ha cap, hi va el `forat`. Retorna clips NOUS.
    """
    out = [Clip(c.ini, c.fi, c.payload) for c in clips or ()]
    n = len(out)
    durada = float(durada or 0.0)
    if not (0 <= first <= last < n) or abs(float(dt)) < 1e-9:
        return out
    a, b = out[first].ini, out[last].fi
    if b - a <= 1e-9:
        return out
    dt = max(-a, min(durada - b, float(dt)))     # el bloc no surt de la WAV
    if abs(dt) < 1e-9:
        return out
    a2, b2 = a + dt, b + dt
    bloc = [Clip(c.ini + dt, c.fi + dt, c.payload) for c in out[first:last + 1]]
    resta = []
    for c in out[:first] + out[last + 1:]:
        if c.fi <= a2 + TOL_TEMPS or c.ini >= b2 - TOL_TEMPS:
            resta.append(c)                      # fora del tram nou: intacte
            continue
        if c.ini < a2 - TOL_TEMPS:
            resta.append(Clip(c.ini, a2, c.payload))    # se'n talla la cua
        if c.fi > b2 + TOL_TEMPS:
            resta.append(Clip(b2, c.fi, c.payload))     # se'n talla el principi
    if dt > 0:                                   # l'anterior tanca l'origen
        fi_vei, tapades = min(a2, b), False
        for i, c in enumerate(resta):
            if c.ini < a - TOL_TEMPS and abs(c.fi - a) <= TOL_TEMPS:
                resta[i], tapades = Clip(c.ini, fi_vei, c.payload), True
        if not tapades:
            resta.append(Clip(0.0, fi_vei, tuple(forat)))
    else:                                        # el següent tanca l'origen
        ini_vei, tapades = max(b2, a), False
        for i, c in enumerate(resta):
            if abs(c.ini - b) <= TOL_TEMPS:
                resta[i], tapades = Clip(ini_vei, c.fi, c.payload), True
        if not tapades and b2 < durada - TOL_TEMPS:
            resta.append(Clip(ini_vei, durada, tuple(forat)))
    nou = bloc + resta
    nou.sort(key=lambda c: c.ini)                # sort estable: mana el bloc
    if log and len(nou) != n:
        log(f"moviment: bloc {first}-{last} → {a2:.2f}-{b2:.2f}s")
    return nou
def elimina_clips(clips, idx, durada, forat):
    """Nucli únic d'ESBORRAR un clip (§6.4: l'anterior s'estira; sense veí, forat).

    El clip `idx` s'esborra i l'**anterior s'estira** per tapar el forat (mateixa
    lògica que l'origen d'un moviment, §6.3). Si NO hi ha anterior (el clip 0),
    el forat el tapa el **normalitzador** amb `forat` (`N`/`-`) sense moure cap
    altre clip (important: esborrar la «N» de capçalera no ha de desplaçar l'acord
    següent). Si el carril queda **buit**, hi va el clip canònic `forat` de 0 a
    `durada` (regla d'or #4). Retorna clips NOUS; no muta l'entrada.
    """
    out = [Clip(c.ini, c.fi, c.payload) for c in (clips or ())]
    if not (0 <= idx < len(out)):
        return out
    c = out.pop(idx)
    if idx > 0 and out:
        p = out[idx - 1]
        out[idx - 1] = Clip(p.ini, c.fi, p.payload)
    out = normalitza_clips(out, durada, forat)
    if not out:
        out = [Clip(0.0, float(durada or c.fi), tuple(forat))]
    return out
def duplica_clips(clips, idx, marge=MIN_GAP_TEMPS):
    """Nucli únic de DUPLICAR un clip: es **parteix pel mig** en dos d'iguals.

    El duplicat conserva el `payload` i, entre els dos, la durada total (com el
    `Ctrl+D` de l'app: la meitat per a cadascun). Si no hi ha prou marge (< 2×
    `marge`), no es fa res. Retorna clips NOUS; no muta l'entrada.
    """
    out = [Clip(c.ini, c.fi, c.payload) for c in (clips or ())]
    if not (0 <= idx < len(out)):
        return out
    c = out[idx]
    mig = (c.ini + c.fi) / 2.0
    if mig - c.ini < marge or c.fi - mig < marge:
        return out
    return (list(out[:idx]) + [Clip(c.ini, mig, c.payload),
                               Clip(mig, c.fi, c.payload)] + list(out[idx + 1:]))


def duplica_bloc_clips(clips, first, last, desti, durada, forat):
    """Nucli de DUPLICAR un BLOC a un DESTÍ (sobreescrivint, §6.3/#11).

    La còpia del bloc `[first..last]` (que conserva la durada i l'espaiat intern,
    com el `Grid Relative` del Cubase) es col·loca a `desti`; el material que hi
    cau **a sota** es **talla** o **s'elimina** (§6.3) i **l'original es queda
    intacte** (a diferència de MOURE). El destí s'acota a `[0, durada)`.

    Amb `desti = fi del bloc` és el `Ctrl+D` («el duplicat va després del clip i
    sobreescriu el tram que ocupa», PLA_EDICIO_LLIURE §2). Retorna clips NOUS.
    """
    out = [Clip(c.ini, c.fi, c.payload) for c in (clips or ())]
    n = len(out)
    durada = float(durada or 0.0)
    if not (0 <= first <= last < n):
        return out
    a, b = float(out[first].ini), float(out[last].fi)
    llarg = b - a
    if llarg <= 1e-9:
        return out
    desti = max(0.0, min(float(desti or 0.0), max(0.0, durada - llarg)))
    ini2, fi2 = desti, desti + llarg
    copies = [Clip(c.ini - a + ini2, c.fi - a + ini2, c.payload)
              for c in out[first:last + 1]]
    resta = []
    for x in out:
        if x.fi <= ini2 + TOL_TEMPS or x.ini >= fi2 - TOL_TEMPS:
            resta.append(x)                       # fora del destí: intacte
            continue
        if x.ini < ini2 - TOL_TEMPS:
            resta.append(Clip(x.ini, ini2, x.payload))      # se'n talla la cua
        if x.fi > fi2 + TOL_TEMPS:
            resta.append(Clip(fi2, x.fi, x.payload))        # se'n talla el cap
    nou = resta + copies
    nou.sort(key=lambda c: c.ini)                 # sort estable: mana la còpia
    return normalitza_clips(nou, durada, forat)

