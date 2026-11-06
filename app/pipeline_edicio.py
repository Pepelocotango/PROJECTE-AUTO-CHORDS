"""Operacions d'edició i validació del model de clips (F1).

Extret de `app/pipeline.py`: wrappers d'acords/seccions, validació de canvis,
blocs i renombrat. Depén del model pur i de `pipeline_io` (noms canònics).
"""
from .pipeline_io import saneja_nom_acord
from .pipeline_model import (
    TOL_TEMPS, MIN_GAP_TEMPS, RESOLUCIO_CSV,
    FORAT_ACORD, FORAT_SECCIO,
    Clip, clips_d_acords, acords_de_clips, clips_de_seccions,
    seccions_de_clips, parteix_clips, fusiona_clips,
    redimensiona_clips, mou_bloc_clips, elimina_clips, duplica_bloc_clips,
)

def parteix_acord(acords, i, talla, nom=None, marge=MIN_GAP_TEMPS, durada=0.0):
    """Parteix l'acord `i` (wrapper del nucli unificat `parteix_clips`; #11)."""
    if i < 0 or i >= len(acords):
        raise ValueError("índex d'acord inexistent")
    nom = (saneja_nom_acord(nom) if nom else "") or acords[i][1]
    payload = (nom, f"{float(talla):.9f}")
    cl = parteix_clips(clips_d_acords(acords, durada), i, talla,
                       nou_payload=payload, marge=marge, etiqueta="acord")
    return [(float(c.ini),) + tuple(c.payload) for c in cl]


def fusiona_acords(acords, i, amb="seguent"):
    """Fusiona l'acord `i` amb el veí (wrapper de `fusiona_clips`; #11)."""
    cl = fusiona_clips(clips_d_acords(acords, 0.0), i, amb, etiqueta="acord")
    return [(float(c.ini),) + tuple(c.payload) for c in cl]


def mou_bloc_acords(acords, first, last, dt, durada, log=None):
    """DESTÍ del moviment d'un BLOC d'acords (PLA_EDICIO_LLIURE §6.3).

    Mou el bloc **consecutiu** `[first..last]` un delta `dt` (segons) **sense
    canviar-ne la durada** i resol el destí amb la regla «**mana l'últim
    editat**»: el material que queda **a sota** del bloc es **talla** (se'n
    conserva la part que no cau dins del bloc) o **s'elimina** (si no en queda
    cap tros). Mai es refusa l'operació per la regla d'or #4.

    El model són **MARQUES**: el clip `i` va de `t_i` a `t_{i+1}` (i l'últim,
    fins a `durada`). El bloc només **tapa** el seu nou tram `[a', b')`: el que
    cau a sota es talla o s'elimina, però **els clips que queden entre l'origen
    i el destí NO es toquen** (es queden quiets i la cobertura la manté el
    mateix model de marques). L'**origen** el tanca el veí: endavant,
    l'anterior s'estira fins a l'inici nou; endarrere, el posterior s'estira
    fins al final nou. Si el bloc queda a la vora, el tros que cap operació tapi
    es converteix en `N` a la normalització (``normalitza_cobertura``).

    Retorna una llista NOVA d'acords (no muta l'entrada). Si el bloc no
    existeix, la durada és nul·la o el delta és ~0, torna la llista original.
    """
    clips = mou_bloc_clips(clips_d_acords(acords, durada), first, last, dt,
                           durada, FORAT_ACORD, log)
    # `tsrc` (temps font): el d'un acord que NO s'ha mogut es conserva; el d'un
    # de mogut o nou passa a ser el seu temps.
    orig = {(round(float(a[0]), 6), a[1]): tuple(a) for a in (acords or ())}
    res = []
    for c in clips:
        t = float(c.ini)
        vell = orig.get((round(t, 6), c.payload[0]))
        if vell is not None:
            res.append((t,) + vell[1:])
        else:
            res.append((t, c.payload[0], f"{t:.9f}") + tuple(c.payload[2:]))
    return res



def redimensiona_acord(acords, idx, vora, t, durada, log=None):
    """ESTIRAR/ENCONGIR una vora d'un acord (mateixa lògica que MOURE, §6.3).

    El clip editat **mana** al seu tram nou: el que queda **a sota** es **talla**
    o **s'elimina**. **Encongir** deixa un buit que tanca el **veí** (a la dreta,
    el següent; a l'esquerra, l'anterior); si **no hi ha veí** (primer o últim
    clip), el buit queda perquè `normalitza_cobertura` hi posi **`N`**.

    `vora`: `"ini"` (esquerra) o `"fi"` (dreta). Retorna una llista NOVA.
    """
    return acords_de_clips(redimensiona_clips(
        clips_d_acords(acords, durada), idx, vora, t, durada, FORAT_ACORD, log))






def redimensiona_seccio(seccions, idx, vora, t, durada, log=None):
    """Vora d'una SECCIÓ: mateixa regla i mateix nucli que els acords (#11)."""
    return seccions_de_clips(redimensiona_clips(
        clips_de_seccions(seccions), idx, vora, t, durada, FORAT_SECCIO, log))




def mou_bloc_seccions(seccions, first, last, dt, durada, log=None):
    """DESTÍ del moviment d'un BLOC de seccions (paritat d'edició #11, §6.3).

    Mateixa regla que :func:`mou_bloc_acords`: el bloc **conserva la seva
    durada**, **tapa** el seu tram nou (el que hi cau a sota es talla o
    s'elimina) i **no toca** les seccions que queden entre l'origen i el destí.
    L'**origen** el tanca el veí (endavant, l'anterior; endarrere, la següent) i,
    si no n'hi ha cap, el forat es converteix en una secció **«-»** (§6.1).

    Les seccions són explícites `(ini, fi, lletra, família)`; el resultat torna a
    ser **contigu** (sense forats) i ordenat. Retorna una llista NOVA.
    """
    return seccions_de_clips(mou_bloc_clips(
        clips_de_seccions(seccions), first, last, dt, durada, FORAT_SECCIO, log))


def parteix_seccio(seccions, i, talla, marge=MIN_GAP_TEMPS):
    """Parteix la secció `i` (mateix nucli que els acords, #11)."""
    return seccions_de_clips(parteix_clips(
        clips_de_seccions(seccions), i, talla, marge=marge, etiqueta="secció"))


def fusiona_seccions(seccions, i, amb="seguent"):
    """Fusiona la secció `i` amb el veí (mateix nucli que els acords, #11)."""
    return seccions_de_clips(fusiona_clips(
        clips_de_seccions(seccions), i, amb, etiqueta="secció"))




def elimina_seccio(seccions, idx, durada):
    """Esborra la secció `idx` (mateix nucli que els acords; #11)."""
    return seccions_de_clips(elimina_clips(
        clips_de_seccions(seccions), idx, durada, FORAT_SECCIO))




def duplica_bloc_seccions(seccions, first, last, desti, durada):
    """Duplica un bloc de seccions a `desti` (mateix nucli que els acords, #11)."""
    return seccions_de_clips(duplica_bloc_clips(
        clips_de_seccions(seccions), first, last, desti, durada, FORAT_SECCIO))


def _nom_item_acord(item):
    if isinstance(item, Clip):
        return item.nom
    if len(item) >= 3 and isinstance(item[1], (int, float)):
        p = item[2]
        return p[0] if isinstance(p, tuple) else p
    return item[1]


def valida_canvis_acords(items, durada=0.0):
    """Valida l'ordre estricte, límits i resolució CSV, i deriva el `fi` en `Clip`."""
    if not items:
        return []
    durada = float(durada or 0.0)
    ordenats = sorted(items, key=lambda x: float(x[0]))
    n = len(ordenats)
    out = []
    prev_t, prev_nom = None, None
    for i, item in enumerate(ordenats):
        t = float(item[0])
        nom = _nom_item_acord(item)
        if t < 0:
            raise ValueError(f"L'acord {nom} té un inici negatiu ({t:.2f}s)")
        if durada > 0 and t >= durada - TOL_TEMPS:
            raise ValueError(
                f"L'acord {nom} no cap dins de la WAV ({t:.2f}s; la WAV "
                f"fa {durada:.2f}s)")
        if prev_t is not None:
            if t <= prev_t + 1e-9:
                raise ValueError(
                    "Els acords no poden compartir ni invertir el seu inici. "
                    "L'ordre ha de ser estricte i sense solapaments."
                )
            if t - prev_t < MIN_GAP_TEMPS - 1e-9:
                raise ValueError(
                    f"Els acords {prev_nom} ({prev_t:.6f}s) i {nom} "
                    f"({t:.6f}s) estan a menys de "
                    f"{MIN_GAP_TEMPS * 1000:.0f} ms: dos canvis d'acord "
                    f"més junts no són útils i fan clips inútils."
                )
        prev_t, prev_nom = t, nom
        fi = float(ordenats[i + 1][0]) if i + 1 < n else durada
        if isinstance(item, Clip):
            payload = tuple(item.payload)
        elif len(item) >= 3 and isinstance(item[1], (int, float)):
            p = item[2]
            payload = tuple(p) if isinstance(p, tuple) else (p,)
        else:
            payload = tuple(item[1:])
        out.append(Clip(t, fi, payload))
    return out


def valida_canvis_seccions(items, durada=0.0):
    """Valida l'ordre estricte, durades positives i no solapament d'estructura."""
    if not items:
        return []
    durada = float(durada or 0.0)
    ordenats = sorted(items, key=lambda x: float(x[0]))
    prev_fi = -1e-9
    for item in ordenats:
        ini = float(item[0])
        fi = float(item[1])
        etq = item.payload[0] if isinstance(item, Clip) else item[2]
        if ini < 0 or fi < 0:
            raise ValueError(
                f"La secció {etq} té temps negatius ({ini:.2f}s–{fi:.2f}s)")
        if fi <= ini:
            raise ValueError(
                f"La secció {etq} té una durada no vàlida ({ini:.2f}s–{fi:.2f}s)")
        if durada > 0 and fi > durada + TOL_TEMPS:
            raise ValueError(
                f"La secció {etq} surt de la WAV ({fi:.2f}s; la WAV fa "
                f"{durada:.2f}s)")
        if ini < prev_fi - 1e-9:
            raise ValueError(
                "Les seccions no poden solapar-se ni invertir-se. "
                "L'ordre temporal ha de ser estricte."
            )
        prev_fi = fi
    return ordenats


def contiguitat_seccions(items, idx, min_s=MIN_GAP_TEMPS):
    """Manté l'INVARIANT de CONTIGÜITAT (#2) ajustant els veïns de la secció `idx`."""
    items = list(items)
    ini, fi, L, _F = items[idx]
    if fi - ini < min_s:
        raise ValueError(
            f"La secció {L} quedaria massa curta ({ini:.2f}s–{fi:.2f}s)")
    if idx - 1 >= 0:
        pi, _pf, pl, pfam = items[idx - 1]
        if ini - pi < min_s:
            raise ValueError(
                f"La secció {pl} quedaria massa curta: el nou inici "
                f"({ini:.2f}s) no deixa marge")
        items[idx - 1] = (pi, ini, pl, pfam)
    if idx + 1 < len(items):
        _ni, nf, nl, nfam = items[idx + 1]
        if nf - fi < min_s:
            raise ValueError(
                f"La secció {nl} quedaria massa curta: el nou fi "
                f"({fi:.2f}s) no deixa marge")
        items[idx + 1] = (fi, nf, nl, nfam)
    return items


def bloc_sobre_acords(acords, bloc, llargada, T, durada, rel=1e-6):
    """Sobreescriu un bloc copiat d'acords dins `[T, T+llargada]`."""
    Te = min(float(T) + float(llargada), float(durada))
    punts = []
    for (r, name) in bloc:
        t = float(T) + float(r)
        if t < durada - rel:
            punts.append(Clip(t, t, (str(name), f"{t:.9f}")))
    if not punts:
        return list(acords)
    marca = None
    for a in acords:
        if abs(float(a[0]) - Te) <= rel:
            marca = a
            break
    if marca is None and Te < durada - rel:
        after = None
        for a in acords:
            if float(a[0]) <= Te - rel:
                after = a
            else:
                break
        nom_m = (str(_nom_item_acord(after))
                 if after else str(_nom_item_acord(punts[-1])))
        marca = Clip(Te, Te, (nom_m, f"{Te:.9f}"))
    nou = [a for a in acords if float(a[0]) < float(T) - rel]
    nou += punts
    if marca is not None:
        if float(marca[0]) > float(punts[-1][0]) + RESOLUCIO_CSV - 1e-6:
            nou.append(marca)
    nou += [a for a in acords if float(a[0]) > Te + rel]
    return nou


def bloc_sobre_seccions(seccions, bloc, llargada, T, durada, rel=1e-6):
    """Sobreescriu un bloc copiat de seccions dins `[T, T+llargada]`."""
    T = float(T)
    durada = float(durada)
    Te = min(T + float(llargada), durada)
    nou = []
    for (ini, fi, ll, fam) in seccions:
        ini, fi = float(ini), float(fi)
        if fi <= T + rel or ini >= Te - rel:
            nou.append((ini, fi, ll, fam))
            continue
        if ini < T - rel:
            nou.append((ini, T, ll, fam))
        if fi > Te + rel:
            nou.append((Te, fi, ll, fam))
    for (ri, rf, ll, fam) in bloc:
        ini = T + float(ri)
        fi = min(T + float(rf), Te)
        if ini < durada - rel and fi - ini > rel:
            nou.append((ini, fi, str(ll), str(fam)))
    nou.sort(key=lambda s: float(s[0]))
    return [s for s in nou if float(s[1]) - float(s[0]) > rel]


def renomena_acords_model(acords, idxs, nom, durada=0.0):
    """Reanomena els acords `idxs` a `nom` i valida la cadena."""
    idxs = sorted({i for i in idxs if 0 <= i < len(acords)})
    nom = saneja_nom_acord(nom)
    if not idxs or not nom:
        return None, ""
    nova = list(acords)
    for i in idxs:
        _a = nova[i]
        nova[i] = Clip(float(_a[0]), float(_a[1]), (nom,) + tuple(_a[2][1:]))
    return valida_canvis_acords(nova, durada), nom


def renomena_seccions_model(seccions, idxs, lletra, durada=0.0):
    """Reanomena les seccions `idxs` a `lletra` i valida la cadena."""
    idxs = sorted({i for i in idxs if 0 <= i < len(seccions)})
    if not idxs:
        return None, ""
    lletra = (str(lletra) if lletra is not None else "").strip() \
        or seccions[idxs[0]][2]
    nova = list(seccions)
    for i in idxs:
        ini, fi, _l, _f = nova[i]
        nova[i] = (ini, fi, lletra, lletra)
    return valida_canvis_seccions(nova, durada), lletra


def substitueix_en_model(items, camp, troba, reemplaca, durada=0.0):
    """Substitueix aparicions exactes a `items` (`acords` o `estructura`).

    Retorna `(nova_llista, n_canvis, etiqueta_aplicada)`.
    """
    troba = str(troba or "").strip()
    reemplaca = str(reemplaca or "").strip()
    if not troba or not reemplaca:
        return list(items), 0, ""
    if camp == "estructura":
        lista, n = [], 0
        for (ini, fi, lletra, fam) in items:
            if str(lletra) == troba:
                n += 1
                fam = reemplaca if str(fam) == troba else fam
                lletra = reemplaca
            lista.append((ini, fi, lletra, fam))
        if not n:
            return list(items), 0, reemplaca
        return valida_canvis_seccions(lista, durada), n, reemplaca
    nou = saneja_nom_acord(reemplaca)
    if not nou:
        return list(items), 0, ""
    lista, n = [], 0
    for _a in items:
        t, fi, nom = float(_a[0]), float(_a[1]), _nom_item_acord(_a)
        if str(nom) == troba:
            n += 1
            nom = nou
        lista.append(Clip(t, fi, (nom, f"{t:.9f}")))
    if not n:
        return list(items), 0, nou
    return valida_canvis_acords(lista, durada), n, nou
