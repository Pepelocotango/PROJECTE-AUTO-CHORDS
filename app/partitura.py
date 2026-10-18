#!/usr/bin/env python3
"""Exportació de partitura (xifrat) des dels resultats d'Auto Chords.

Genera un **lead sheet de xifrats** a partir dels resultats que ja produeix
l'exportació normal del projecte:

    <sortida>/acords_locators.txt   (posició compàs.temps.setzena · acord · durada en temps)
    <sortida>/estructura_ABC.csv    (seccions amb posició en compàs)

i el converteix a:

    <sortida>/partitura/<tema>.musicxml   estàndard, editable a qualsevol MuseScore
    <sortida>/partitura/<tema>.pdf        render amb MuseScore (si hi és)
    <sortida>/partitura/<tema>.mscz       projecte natiu MuseScore (si hi és)

Sense dependències de tercers (stdlib). El render amb MuseScore és **opcional**:
si no es troba el binari, s'escriu només el MusicXML i s'avisa (no trenca res).

⚠️ En aquesta màquina (Q9400, sense SSE4.2): **MuseScore 4.6.x funciona**; 4.7+
   NO (Qt6 exigeix SSE4.2+POPCNT). Es detecta amb la variable d'entorn
   `AUTO_CHORDS_MUSESCORE` o es busca sol a `~/Applications`.

Abast: la partitura reflecteix els **xifrats** detectats/editats (no hi ha
transcripció de melodia). Només té sentit en mode **BPM · compàs** (cal
`acords_locators.txt`; en mode lliure no hi ha graella).
"""
import csv
import glob
import os
import re
import shutil
import subprocess
from xml.sax.saxutils import escape

from app import xifrat           # notació del xifrat (sense deps del projecte)

__all__ = [
    "exporta_partitura", "construeix_musicxml", "harmony_xml",
    "llegeix_locators", "llegeix_seccions", "parse_pos",
    "musescore_bin", "detecta_fifths", "fifths_de_to",
]

DIV = 4                      # divisions per negra (quarter) al MusicXML
MOTS = "partitura"


# --- utilitats -------------------------------------------------------------
def _log_std(log):
    return log if callable(log) else (lambda *_a, **_k: None)


def safe_filename(nom, fallback="X"):
    s = str(nom).strip()
    # `/` (acord amb baix) i els separadors de path → `_`, MAI `-` (al xifrat
    # el `-` vol dir «menor»). Control chars: fora.
    for ch in (os.sep, "/", "\\"):
        s = s.replace(ch, "_")
    for ch in ("\0", "\n", "\r", "\t"):
        s = s.replace(ch, "")
    s = s.strip()
    return (s or fallback)[:64]


# Prefix de les carpetes que genera l'app. La font única és
# `pipeline.PREFIX_SORTIDA`; aquí el repetim perquè aquest mòdul no importa res
# del projecte (un test comprova que tots dos valors coincideixen).
_PREFIX_SORTIDA = "AUTOCHORDS_"


def _base_de_sortida(sortida):
    b = os.path.basename(os.path.abspath(sortida).rstrip("/"))
    if b.startswith(_PREFIX_SORTIDA):
        b = b[len(_PREFIX_SORTIDA):]
    return safe_filename(b or "partitura")


# --- lectura de dades ------------------------------------------------------
def parse_pos(s, bpb=4, bars=None):
    """`compàs.temps.setzena` -> posició absoluta en negres (beat).

    Amb `bars` (mapa compàs→negra d'inici; per a compàs variable) el
    desplaçament ve del mapa; si no, `(b-1)*bpb` (compàs uniforme).
    """
    b, t, sub = (int(x) for x in s.split("."))
    # 3r camp = subdivisió dins del temps (1..4, "setzena"; les dades d'Auto
    # Chords fan servir 1 = temps i 3 = "i" del temps -> +0,5 beats).
    base = bars.get(b, (b - 1) * bpb) if bars else (b - 1) * bpb
    return base + (t - 1) + (sub - 1) / 4.0


_RE_POS = re.compile(r"^\d+\.\d+\.\d+$")


def llegeix_locators(ruta, bpb=4, bars=None):
    """Llegeix `acords_locators.txt` -> [(start_beat, acord, duracio_beats)]."""
    ev = []
    with open(ruta, encoding="utf-8") as f:
        for line in f.read().splitlines():
            parts = line.split()
            if len(parts) < 3 or not _RE_POS.match(parts[0]):
                continue                     # capçalera o línia no vàlida
            try:
                dur = float(parts[2])
            except ValueError:
                continue
            ev.append((parse_pos(parts[0], bpb, bars), parts[1], dur))
    ev.sort(key=lambda e: e[0])
    return ev


def llegeix_seccions(ruta):
    """Llegeix `estructura_ABC.csv` -> [(compas, lletra)] (deduplicat)."""
    secs, vist = [], set()
    if not ruta or not os.path.isfile(ruta):
        return secs
    with open(ruta, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                bar = int(float(str(r.get("compas_ini", "")).split(".")[0]))
            except (ValueError, IndexError, AttributeError):
                continue
            if bar in vist:
                continue
            vist.add(bar)
            secs.append((bar, str(r.get("lletra", "")).strip()))
    return secs


def llegeix_bpm_bpb_de_guia(ruta):
    """Retorna (bpm, bpb) de la capçalera de `guia_acords.html`, o (None, None)."""
    if not ruta or not os.path.isfile(ruta):
        return None, None
    with open(ruta, encoding="utf-8") as f:
        cap = f.read(4000)
    m = re.search(r"<h3>(\d+(?:\.\d+)?)\s*BPM\s*·\s*(\d+)\s*temps", cap)
    if not m:
        return None, None
    return float(m.group(1)), int(m.group(2))


# --- xifrat -> <harmony> MusicXML -----------------------------------------
_ALT = {"#": 1, "b": -1, "##": 2, "bb": -2, "": 0}


def _degree_xml(valor, alter, tipus):
    """Un `<degree>` de MusicXML (9, −1, alter → la 9a bemollitzada)."""
    return (f"<degree><degree-value>{valor}</degree-value>"
            f"<degree-alter>{alter}</degree-alter>"
            f"<degree-type>{tipus}</degree-type></degree>")


def harmony_xml(chord):
    """Bloc `<harmony>` per a un xifrat (o '' si no és un acord).

    Escriu el `<kind>` base **i els `<degree>`** de les alteracions/extensions
    (segons la taula de tipus de `app/xifrat.py`) → MuseScore ho mostra **i ho
    reprodueix** bé. Si la qualitat no es reconeix, cau a `other` amb el sufix
    com a `text` (mai el nom sencer: el root ja s'escriu a part).
    """
    if not chord or xifrat.es_cap_acord(chord):
        return ""
    xif = xifrat.normalitza_xifrat(chord)          # forma canònica
    base, bass = xifrat.parteix_baix(xif)
    pa = xifrat.parteix_arrel(base)
    if pa is None:
        return ""
    root, qual = pa
    step, alt = root[0], root[1:]
    kind, gr = xifrat.kind_i_graus(qual)
    if kind is None:                          # qualitat no estàndard
        kind, txt, gr = "other", f' text="{escape(qual)}"', ()
    elif xifrat.resta_qualitat(qual):
        # El `kind` només és la BASE però hi ha un tros no estàndard (p. ex.
        # `7alt`): es conserva el símbol sencer al `text` per no perdre'l.
        txt = f' text="{escape(qual)}"'
    else:
        txt = ""
    alter = f"<root-alter>{_ALT.get(alt, 0)}</root-alter>" if alt else ""
    out = (f"      <harmony><root><root-step>{step}</root-step>{alter}</root>"
           f"<kind{txt}>{kind}</kind>")
    for (valor, galt, tipus) in gr:
        out += _degree_xml(valor, galt, tipus)
    if bass:
        pb = xifrat.parteix_arrel(bass)
        if pb is not None:
            bstep, balt = pb[0][0], pb[0][1:]
            balter = (f"<bass-alter>{_ALT.get(balt, 0)}</bass-alter>"
                      if balt else "")
            out += f"<bass><bass-step>{bstep}</bass-step>{balter}</bass>"
    return out + "</harmony>\n"


# --- durades i notes -------------------------------------------------------
_UNITS = {"whole": 16, "half": 8, "quarter": 4, "eighth": 2, "16th": 1}
_STD = [(16, "whole", 0), (12, "half", 1), (8, "half", 0), (6, "quarter", 1),
        (4, "quarter", 0), (3, "eighth", 1), (2, "eighth", 0), (1, "16th", 0)]


def _decomposa(units):
    """Descompon una durada (en unitats de DIV) en notes estàndard."""
    out = []
    for u, t, d in _STD:
        while units >= u:
            out.append((t, d))
            units -= u
    return out


def _note_xml(units, rest=False):
    parts = []
    for t, dot in _decomposa(int(units)):
        dur = _UNITS[t] * (3 if dot else 2) // 2     # puntet = x1,5
        cap = "<rest/>" if rest else ""
        pit = "" if rest else "<pitch><step>B</step><octave>4</octave></pitch>"
        head = "" if rest else "<notehead>slash</notehead>"
        parts.append(f"      <note>{cap}{pit}<duration>{dur}</duration>"
                     f"<voice>1</voice><type>{t}</type>"
                     f"{'<dot/>' if dot else ''}{head}</note>\n")
    return "".join(parts)


# --- construcció del MusicXML ----------------------------------------------
def construeix_musicxml(events, seccions, bpb=4, bpm=120.0, titol="Partitura",
                        key_fifths=0, new_system_each=None, beat_type=4,
                        mapa=None):
    """Retorna el text MusicXML (partwise) del lead sheet."""
    sec_bar = {bar: let for bar, let in seccions if let}
    fi = max([e[0] + e[2] for e in events] + [0.0])
    compasos = None
    if mapa is not None and not mapa.es_constant():
        compasos = mapa.compassos_beats()

    def _mesura(i):
        """(negra_ini, negra_fi, num, den) de la mesura `i` (1-based)."""
        if compasos and i <= len(compasos):
            _bar, b0, num, den = compasos[i - 1]
            return (float(b0), float(b0) + num * 4.0 / den, int(num), int(den))
        return (float(i - 1) * bpb, float(i) * bpb, int(bpb), int(beat_type))

    n_bars = int(fi // bpb) + (1 if fi % bpb else 0)
    if compasos:
        n_bars = max(n_bars, len(compasos))
    if seccions:
        n_bars = max(n_bars, max(b for b, _ in seccions))
    n_bars = max(n_bars, 1)

    x = ['<?xml version="1.0" encoding="UTF-8"?>\n',
         '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 '
         'Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">\n',
         '<score-partwise version="4.0">\n',
         f"  <work><work-title>{escape(titol)}</work-title></work>\n",
         "  <identification><encoding><software>AUTO CHORDS</software>"
         "</encoding></identification>\n",
         '  <part-list><score-part id="P1"><part-name>Chords</part-name>'
         "</score-part></part-list>\n",
         '  <part id="P1">\n']

    # Canvis de TEMPO del mapa (variable): <sound tempo> al compàs on cauen.
    canvis_tempo = {}
    if mapa is not None and not mapa.es_constant():
        for k in range(1, len(mapa.trams)):
            s, pre = mapa.trams[k], mapa.trams[k - 1]
            if abs(s.bpm - pre.bpm) > 1e-9:
                canvis_tempo[mapa.pos(s.ini)[0]] = s.bpm
        if canvis_tempo:               # calen compassos fins al darrer canvi
            n_bars = max(n_bars, max(canvis_tempo))

    darrera = None
    sig_ant = None
    for i in range(1, n_bars + 1):
        bs, be, num_m, den_m = _mesura(i)
        x.append(f'    <measure number="{i}">\n')
        # Salt de sistema: a l'inici de cada secció i, si es vol, cada N
        # compassos (per tenir línies regulars, estil lead sheet).
        if i != 1 and (i in sec_bar or
                       (new_system_each and (i - 1) % new_system_each == 0)):
            x.append('      <print new-system="yes"/>\n')
        if i == 1:
            x.append("      <attributes><divisions>4</divisions>"
                     f"<key><fifths>{int(key_fifths)}</fifths></key>"
                     f"<time><beats>{num_m}</beats>"
                     f"<beat-type>{den_m}</beat-type></time>"
                     "<clef><sign>G</sign><line>2</line></clef></attributes>\n")
            x.append('      <direction placement="above"><direction-type>'
                     f"<metronome><beat-unit>quarter</beat-unit>"
                     f"<per-minute>{bpm:g}</per-minute></metronome></direction-type>"
                     f'<sound tempo="{bpm:g}"/></direction>\n')
        elif (num_m, den_m) != sig_ant:
            # canvi de COMPÀS (mapa variable): nova signatura
            x.append("      <attributes><time>"
                     f"<beats>{num_m}</beats>"
                     f"<beat-type>{den_m}</beat-type>"
                     "</time></attributes>\n")
        sig_ant = (num_m, den_m)
        if i in canvis_tempo:
            tb = canvis_tempo[i]
            x.append('      <direction placement="above"><direction-type>'
                     f"<metronome><beat-unit>quarter</beat-unit>"
                     f"<per-minute>{tb:g}</per-minute></metronome>"
                     "</direction-type>"
                     f'<sound tempo="{tb:g}"/></direction>\n')
        if i in sec_bar:
            x.append('      <direction placement="above"><direction-type>'
                     f"<rehearsal>{escape(sec_bar[i])}</rehearsal>"
                     "</direction-type></direction>\n")

        segs = []
        for s, c, d in events:
            a, b = max(s, bs), min(s + d, be)
            if b - a > 1e-9:
                segs.append((a, b, c))
        segs.sort()
        cur = bs
        for a, b, c in segs:
            if a - cur > 1e-9:
                x.append(_note_xml(round((a - cur) * DIV), rest=True))
            if c != "N" and c != darrera:
                x.append(harmony_xml(c))
                darrera = c
            x.append(_note_xml(round((b - a) * DIV)))
            cur = b
        if be - cur > 1e-9:
            x.append(_note_xml(round((be - cur) * DIV), rest=True))
        x.append("    </measure>\n")

    x.append(f'    <measure number="{n_bars + 1}"><barline location="right">'
             "<bar-style>light-heavy</bar-style></barline></measure>\n")
    x.append("  </part>\n</score-partwise>\n")
    return "".join(x)


# --- tonalitat -------------------------------------------------------------
_MAJ = {"C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5, "F#": 6, "C#": 7,
        "F": -1, "Bb": -2, "Eb": -3, "Ab": -4, "Db": -5, "Gb": -6, "Cb": -7}
_MIN_REL = {"A": "C", "E": "G", "B": "D", "F#": "A", "C#": "E", "G#": "B",
            "D#": "F#", "D": "F", "G": "Bb", "C": "Eb", "F": "Ab",
            "Bb": "Db", "Eb": "Gb"}


def fifths_de_to(to):
    """`G` / `G major` / `E minor` / `Em` -> armadura en fifths (C=0)."""
    m = re.match(r"^\s*([A-G][#b]?)\s*(major|maj|minor|min|m)?\s*$",
                 str(to), re.I)
    if not m:
        return 0
    root, mode = m.group(1), (m.group(2) or "major").lower()
    if mode.startswith("mi") or mode == "m":          # menor -> relatiu major
        root = _MIN_REL.get(root, root)
    return _MAJ.get(root, 0)


def detecta_fifths(wav, log=None):
    """Tonalitat amb el `qm-keydetector` del projecte (opcional).

    Reutilitza l'API pública de `app.pipeline` (no en modifica res). Si falla,
    retorna 0 (= sense armadura) sense interrompre l'exportació.
    """
    log = _log_std(log)
    d = None
    try:
        from app import pipeline
        import tempfile
        d = tempfile.mkdtemp(prefix="ac_key_")
        out = os.path.join(d, "key.csv")
        pipeline.executa_transform(pipeline.QM["key"], out, wav,
                                   lambda *_a: None)
        with open(out, encoding="utf-8") as f:
            for row in csv.reader(f):
                for cell in row:
                    t = cell.strip()
                    if re.match(r"^[A-G][#b]?\s+(major|minor)$", t):
                        log(f"partitura: tonalitat detectada: {t}")
                        return fifths_de_to(t)
    except Exception as e:  # noqa: BLE001
        log(f"partitura: no he pogut detectar la tonalitat ({e})")
    finally:
        # El directori temporal és nostre: s'esborra sempre (també si peta).
        if d:
            shutil.rmtree(d, ignore_errors=True)
    return 0


# --- MuseScore -------------------------------------------------------------
def musescore_bin():
    """Retorna el binari/AppImage de MuseScore, o None.

    Ordre: `$AUTO_CHORDS_MUSESCORE` -> `PATH` -> ubicacions típiques **per SO**:
    Linux (`~/Applications/*.AppImage`), **macOS** (`/Applications/MuseScore*.app`)
    i **Windows** (`Program Files\\MuseScore *`). Es prefereix 4.6.x (l'última que
    corre al Q9400 sense SSE4.2).
    """
    env = os.environ.get("AUTO_CHORDS_MUSESCORE")
    if env:
        return env
    # `shutil.which` (no `os.popen("command -v …")`: a Windows no hi ha `command`).
    for c in ("mscore", "mscore3", "mscore4", "musescore", "musescore4",
              "MuseScore4", "MuseScore4.exe", "MuseScore3.exe"):
        p = shutil.which(c)
        if p:
            return p
    patrons = [
        # Linux (AppImages)
        "~/Applications/MuseScore*4.6*.AppImage",
        "~/Applications/MuseScore*.AppImage",
        "~/Applications/musescore*.AppImage",
        "~/MuseScore*.AppImage",
        # macOS (.app)
        "/Applications/MuseScore*.app/Contents/MacOS/mscore",
        "/Applications/MuseScore*.app/Contents/MacOS/MuseScore*",
        "~/Applications/MuseScore*.app/Contents/MacOS/mscore",
        "~/Applications/MuseScore*.app/Contents/MacOS/MuseScore*",
        # Windows
        "C:/Program Files/MuseScore */bin/MuseScore*.exe",
        "C:/Program Files (x86)/MuseScore */bin/MuseScore*.exe",
    ]
    loc = os.environ.get("LOCALAPPDATA")
    if loc:
        patrons.append(os.path.join(loc, "Programs", "MuseScore *", "bin",
                                    "MuseScore*.exe"))
    for pat in patrons:
        trobat = sorted(glob.glob(os.path.expanduser(pat)))
        if trobat:
            return trobat[0]
    return None


def _musescore_en_marxa():
    for p in glob.glob("/proc/[0-9]*/comm"):
        try:
            with open(p, encoding="utf-8", errors="ignore") as f:
                if f.read().strip().lower().startswith("musescore"):
                    return True
        except OSError:
            pass
    return False


def _renderitza(binari, entrada, sortida, log, timeout=300):
    """Exporta `entrada` -> `sortida` amb MuseScore. Retorna True/False."""
    if os.path.exists(sortida):
        try:
            os.remove(sortida)
        except OSError:
            pass
    extra_opts = []
    if binari.lower().endswith(".appimage"):
        extra_opts = [[], ["--appimage-extract-and-run"]]
    else:
        extra_opts = [[]]
    for extra in extra_opts:
        try:
            p = subprocess.run([binari] + extra + ["-o", sortida, entrada],
                               capture_output=True, text=True, timeout=timeout)
        except Exception as e:  # noqa: BLE001
            log(f"partitura: MuseScore ha fallat ({e})")
            continue
        if os.path.isfile(sortida) and os.path.getsize(sortida) > 0:
            return True
        if p.returncode != 0:
            log(f"partitura: MuseScore rc={p.returncode}")
    if _musescore_en_marxa():
        log("partitura: ⚠️ sembla que tens MuseScore obert; és d'instància "
            "única i el CLI pot no exportar. Tanca'l i reintenta.")
    return False


# --- export principal ------------------------------------------------------
def exporta_partitura(sortida, log=None, bpm=None, bpb=None, offset=0.0,
                      titol=None, key_fifths=0, wav=None,
                      genera_pdf=True, genera_mscz=True, musescore=None,
                      timeout=300, new_system_each=None, beat_type=4,
                      mapa=None):
    """Genera MusicXML (+ PDF/.mscz amb MuseScore) a `<sortida>/partitura/`.

    Retorna un diccionari amb les rutes generades (`musicxml`, `pdf`, `mscz`,
    `base`) i `error` si no s'ha pogut fer res.
    """
    log = _log_std(log)
    sortida = os.path.abspath(sortida)
    loc = os.path.join(sortida, "acords_locators.txt")
    if not os.path.isfile(loc):
        log("partitura: no trobo acords_locators.txt (cal el mode BPM · compàs)")
        return {"error": "sense_locators"}

    guia = os.path.join(sortida, "guia_acords.html")
    g_bpm, g_bpb = llegeix_bpm_bpb_de_guia(guia)
    bpm = float(bpm) if bpm else (g_bpm or 120.0)
    bpb = int(bpb) if bpb else (g_bpb or 4)

    _bars = None
    if mapa is not None and not mapa.es_constant():
        _bars = {bar: b0 for (bar, b0, _n, _d) in mapa.compassos_beats()}
    events = llegeix_locators(loc, bpb, _bars)
    if not events:
        log("partitura: acords_locators.txt buit")
        return {"error": "locators_buits"}
    seccions = llegeix_seccions(os.path.join(sortida, "estructura_ABC.csv"))

    base = safe_filename(titol) if titol else _base_de_sortida(sortida)
    dest_dir = os.path.join(sortida, MOTS)
    os.makedirs(dest_dir, exist_ok=True)

    xml = construeix_musicxml(events, seccions, bpb=bpb, bpm=bpm, mapa=mapa,
                              titol=base, key_fifths=key_fifths,
                              new_system_each=new_system_each,
                              beat_type=beat_type)
    ruta_xml = os.path.join(dest_dir, base + ".musicxml")
    with open(ruta_xml, "w", encoding="utf-8") as f:
        f.write(xml)
    log(f"partitura: MusicXML -> {ruta_xml} "
        f"({len(events)} acords, {bpm:g} BPM, {bpb}/{beat_type}, "
        f"{len(seccions)} seccions)")

    result = {"musicxml": ruta_xml, "pdf": None, "mscz": None, "base": base}
    if not (genera_pdf or genera_mscz):
        return result

    binari = musescore or musescore_bin()
    if not binari:
        log("partitura: no he trobat MuseScore; tens el MusicXML per obrir-lo "
            "a mà (o defineix AUTO_CHORDS_MUSESCORE)")
        return result
    log(f"partitura: renderitzo amb {binari}")
    if genera_pdf:
        out = os.path.join(dest_dir, base + ".pdf")
        if _renderitza(binari, ruta_xml, out, log, timeout):
            result["pdf"] = out
            log(f"partitura: PDF -> {out}")
        else:
            log("partitura: no s'ha pogut generar el PDF")
    if genera_mscz:
        out = os.path.join(dest_dir, base + ".mscz")
        if _renderitza(binari, ruta_xml, out, log, timeout):
            result["mscz"] = out
            log(f"partitura: MSCZ -> {out}")
        else:
            log("partitura: no s'ha pogut generar el MSCZ")
    return result
