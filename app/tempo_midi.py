"""Exportació del mapa de tempo/compàs a MIDI (Standard MIDI File tipus 1).

El fitxer és una **pista de conductor** portable: `Set Tempo`, `Time Signature`
i markers. Els temps del model són en segons; els events MIDI es col·loquen
integrant el BPM de cada tram, de manera que un DAW els llig en la mateixa
posició que el mapa.

El rubato és només un flag de notació en este projecte (no una corba de BPM):
s'exporta amb els mateixos events i el marker ho indica. L'offset/anacrusi
s'anota amb un marker a l'inici.
"""
from __future__ import annotations

import struct

from . import bpm_unit
from .pipeline_io import escriu_atomic_bytes

NOM_MAPA_MIDI = "mapa_tempo.mid"
PPQ = 480
#: Claus dels events meta que ens interessen.
META_TEMPO = 0x51
META_TIMESIG = 0x58
META_MARKER = 0x06
META_TRACK_NAME = 0x03
META_END = 0x2F


def _vlq(n):
    """Variable-length quantity de MIDI."""
    n = max(0, int(n))
    out = bytearray([n & 0x7F])
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


def _meta(tipus, dades=b""):
    return bytes((0xFF, tipus)) + _vlq(len(dades)) + dades


def _track(events, end_tick=None):
    """Construeix un `MTrk` a partir de `(tick_absolut, bytes_event)`."""
    cos = bytearray()
    ultim = 0
    for tick, ev in events:
        tick = max(ultim, int(tick))
        cos += _vlq(tick - ultim)
        cos += ev
        ultim = tick
    if end_tick is not None and int(end_tick) > ultim:
        cos += _vlq(int(end_tick) - ultim)
        ultim = int(end_tick)
        cos += _meta(META_END)
    else:
        cos += _vlq(0) + _meta(META_END)
    return b"MTrk" + struct.pack(">I", len(cos)) + bytes(cos)


def _tram_camps(tr):
    """`(bpm, num, den, beat_unit)` d'un `TramMapa` o d'una tupla."""
    bpm = float(tr.bpm if hasattr(tr, "bpm") else tr[2])
    num = int(getattr(tr, "num", tr[3]))
    den = int(getattr(tr, "den", tr[4]))
    unit = bpm_unit.normalitza(
        getattr(tr, "beat_unit", None)
        or bpm_unit.unitat_per_defecte(num, den))
    return bpm, num, den, unit


def _text_marcador(m):
    """Normalitza un marcador: `t` o `(t, tipus)` -> `(t, text)`."""
    if isinstance(m, (tuple, list)):
        t = float(m[0])
        tipus = str(m[1] if len(m) > 1 else "marcador").strip().lower()
    else:
        t, tipus = float(m), "marcador"
    text = {"compas": "Compàs", "seccio": "Secció",
            "marcador": "Marcador"}.get(tipus, "Marcador")
    return t, text


def _events_base(trams, offset=0.0, marques=()):
    """Events `(t, prioritat, tipus, valor)` abans de convertir a ticks."""
    trams = list(trams or ())
    if not trams:
        raise ValueError("El mapa de tempo és buit; no hi ha res a exportar.")
    first_bpm, first_num, first_den, first_unit = _tram_camps(trams[0])
    events = []
    if float(getattr(trams[0], "ini", trams[0][0])) > 1e-9:
        events.append((0.0, 0, "tempo", first_bpm))
        events.append((0.0, 1, "timesig", (first_num, first_den, first_unit)))
    if float(offset or 0.0) > 0:
        events.append((0.0, 4, "marker",
                       f"Anacrusi: {float(offset):.6f} s"))
    for i, tr in enumerate(trams):
        bpm, num, den, unit = _tram_camps(tr)
        t = max(0.0, float(getattr(tr, "ini", tr[0])))
        events.append((t, 0, "tempo", bpm))
        events.append((t, 1, "timesig", (num, den, unit)))
        text = f"Tram {i + 1} · {num}/{den}"
        if getattr(tr, "tipus", "normal") == "rubato":
            text += " · rubato"
        events.append((t, 2, "marker", text))
    for m in marques or ():
        t, text = _text_marcador(m)
        events.append((max(0.0, t), 5, "marker", text))
    # El MIDI ha de durar fins al final de l'últim tram (no només fins al
    # seu inici): si no, importat en un DAW queda més curt que la WAV.
    end_t = float(getattr(trams[-1], "fi", trams[-1][1]))
    for m in marques or ():
        end_t = max(end_t, _text_marcador(m)[0])
    # Alguns DAW (REAPER) dimensionen l'item MIDI pel darrer event, no per
    # l'EOT. Un `Set Tempo` redundant al final (mateix BPM) allarga l'item
    # sense crear cap marker que després es puga desplaçar.
    last_bpm = float(getattr(trams[-1], "bpm", trams[-1][2]))
    events.append((max(0.0, end_t), 0, "tempo", last_bpm))
    events.append((max(0.0, end_t), 9, "end", None))
    # Orde estable: a igual temps, tempo → compàs → markers → final.
    events.sort(key=lambda e: (e[0], e[1]))
    return events, first_bpm


def _a_ticks(events, bpm_inicial):
    """Converteix temps en segons a ticks MIDI integrant el BPM vigent."""
    t_prev = 0.0
    bpm = float(bpm_inicial)
    tick_prev = 0
    out = []
    for t, _pri, tipus, valor in events:
        t = max(t_prev, float(t))
        delta_q = (t - t_prev) * bpm / 60.0 if bpm > 0 else 0.0
        tick = tick_prev + int(round(delta_q * PPQ))
        out.append((tick, tipus, valor))
        t_prev, tick_prev = t, tick
        if tipus == "tempo":
            bpm = float(valor)
    return out


def _events_de_conductor(trams, offset=0.0, marques=()):
    """Retorna `(events_meta, n_tempo)` per a la pista de conductor."""
    base, bpm_inicial = _events_base(trams, offset=offset, marques=marques)
    ticks = _a_ticks(base, bpm_inicial)
    out = [(0, _meta(META_TRACK_NAME,
                     "AUTO CHORDS — Tempo Map".encode("utf-8")))]
    n_tempo = 0
    end_tick = None
    for tick, tipus, valor in ticks:
        if tipus == "end":
            end_tick = tick
            continue
        if tipus == "tempo":
            bpm = float(valor)
            if not (bpm > 0):
                raise ValueError("BPM no vàlid al mapa de tempo.")
            us = int(round(60_000_000.0 / bpm))
            us = max(1, min(0xFFFFFF, us))
            dades = us.to_bytes(3, "big")
            out.append((tick, _meta(META_TEMPO, dades)))
            n_tempo += 1
        elif tipus == "timesig":
            num, den = int(valor[0]), int(valor[1])
            unit = valor[2] if len(valor) > 2 else None
            if num <= 0 or den <= 0 or (den & (den - 1)):
                raise ValueError(f"Compàs no vàlid per a MIDI: {num}/{den}")
            dd = den.bit_length() - 1
            # `cc` = clocks MIDI per clic de metrònom (24 = negra; 36 =
            # negra amb punt). És un hint: alguns DAWs l'ignoren.
            factor = bpm_unit.factor(
                unit or bpm_unit.unitat_per_defecte(num, den))
            cc = max(1, min(255, int(round(24 * factor))))
            out.append((tick, _meta(META_TIMESIG,
                                    bytes((num & 0x7F, dd & 0x7F, cc, 8)))))
        elif tipus == "marker":
            text = str(valor).encode("utf-8")
            out.append((tick, _meta(META_MARKER, text)))
    out.sort(key=lambda e: e[0])
    return out, n_tempo, end_tick


def desa_mapa_midi(ruta, trams, offset=0.0, marques=(), log=None):
    """Escriu `mapa_tempo.mid` (tipus 1, una pista de conductor).

    Args:
        ruta: destí `.mid`.
        trams: `TramMapa`/tuples del mapa, en orde.
        offset: offset/anacrusi en segons (s'anota amb un marker).
        marques: markers addicionals: `t` o `(t, tipus)`.
    Retorna la ruta escrita.
    """
    events, n_tempo, end_tick = _events_de_conductor(trams, offset, marques)
    track = _track(events, end_tick)
    cap = b"MThd" + struct.pack(">IHHH", 6, 1, 1, PPQ)
    escriu_atomic_bytes(ruta, cap + track)
    if log:
        log(f"MIDI del mapa: {n_tempo} event(s) de tempo → {ruta}")
    return ruta


def _llegeix_vlq(dades, pos):
    val = 0
    while True:
        if pos >= len(dades):
            raise ValueError("MIDI truncat llegint un VLQ")
        b = dades[pos]
        pos += 1
        val = (val << 7) | (b & 0x7F)
        if not b & 0x80:
            return val, pos


def llegeix_mapa_midi(ruta):
    """Llig un MIDI generat per `desa_mapa_midi` i en retorna els events.

    Retorna un diccionari amb `format`, `ppq`, `n_tracks`, `tempo`, `timesig`,
    `markers` i `track_names`. Servix per a validar l'export i per a tests.
    """
    with open(ruta, "rb") as f:
        dades = f.read()
    if len(dades) < 14 or dades[:4] != b"MThd":
        raise ValueError("No és un Standard MIDI File (falta MThd).")
    cap_len = struct.unpack(">I", dades[4:8])[0]
    if cap_len < 6:
        raise ValueError("Capçalera MIDI invàlida.")
    fmt, n_tracks, divisio = struct.unpack(">HHH", dades[8:14])
    info = {"format": fmt, "ppq": divisio, "n_tracks": n_tracks,
            "tempo": [], "timesig": [], "markers": [], "track_names": [],
            "end_tick": 0}
    pos = 8 + cap_len
    while pos + 8 <= len(dades):
        tipus = dades[pos:pos + 4]
        llarg = struct.unpack(">I", dades[pos + 4:pos + 8])[0]
        pos += 8
        if pos + llarg > len(dades):
            raise ValueError("MIDI truncat en una pista.")
        if tipus != b"MTrk":
            pos += llarg
            continue
        _llegeix_pista(dades[pos:pos + llarg], info)
        pos += llarg
    return info


def _llegeix_pista(pista, info):
    pos = 0
    tick = 0
    estat = None
    while pos < len(pista):
        delta, pos = _llegeix_vlq(pista, pos)
        tick += delta
        if pos >= len(pista):
            break
        b = pista[pos]
        if b < 0x80:
            if estat is None:
                raise ValueError("MIDI: running status sense estat previ.")
            primer = b
            pos += 1
        else:
            estat = b
            pos += 1
            if estat in (0xF0, 0xF7):
                llarg, pos = _llegeix_vlq(pista, pos)
                pos += llarg
                estat = None
                continue
            if estat == 0xFF:
                if pos >= len(pista):
                    break
                meta = pista[pos]
                pos += 1
                llarg, pos = _llegeix_vlq(pista, pos)
                dades = pista[pos:pos + llarg]
                pos += llarg
                _meta_llegida(tick, meta, dades, info)
                estat = None
                continue
            primer = None
        alt = estat >> 4
        n = 1 if alt in (0xC, 0xD) else 2
        if primer is not None:
            dades = bytes((primer,)) + pista[pos:pos + n - 1]
            pos += n - 1
        else:
            dades = pista[pos:pos + n]
            pos += n
        _ = dades


def _meta_llegida(tick, meta, dades, info):
    if meta == META_END:
        info["end_tick"] = max(int(info.get("end_tick") or 0), int(tick))
    elif meta == META_TEMPO and len(dades) >= 3:
        us = int.from_bytes(dades[:3], "big")
        if us > 0:
            info["tempo"].append({"tick": tick, "bpm": 60_000_000.0 / us})
    elif meta == META_TIMESIG and len(dades) >= 2:
        info["timesig"].append({
            "tick": tick, "num": int(dades[0]),
            "den": 2 ** int(dades[1]),
            "cc": int(dades[2]) if len(dades) >= 3 else None,
            "bb": int(dades[3]) if len(dades) >= 4 else None})
    elif meta == META_MARKER:
        info["markers"].append({
            "tick": tick, "text": dades.decode("utf-8", "replace")})
    elif meta == META_TRACK_NAME:
        info["track_names"].append(
            {"tick": tick, "text": dades.decode("utf-8", "replace")})


def tick_a_segons(info, tick):
    """Converteix un tick absolut a segons segons els `Set Tempo` del MIDI."""
    events = sorted(info.get("tempo") or (), key=lambda e: e["tick"])
    bpm = 120.0
    if events:
        bpm = float(events[0]["bpm"])
    t = 0.0
    prev_tick = 0
    for ev in events:
        if ev["tick"] > tick:
            break
        t += (ev["tick"] - prev_tick) / float(info["ppq"]) * 60.0 / bpm
        prev_tick = ev["tick"]
        bpm = float(ev["bpm"])
    t += (tick - prev_tick) / float(info["ppq"]) * 60.0 / bpm
    return t
