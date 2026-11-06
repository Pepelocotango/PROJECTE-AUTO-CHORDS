"""Estructura ABC i WAVs de seccions (F1).

Extret de `app/pipeline.py`: filtre de seccions, `estructura_ABC.csv`,
`fer_abc`, mode lliure i WAVs silenciosos d'estructura.
"""
import csv
import os
import wave

from .pipeline_derivats import pos_compas, seq_abc
from .pipeline_io import safe_filename, escriu_atomic, neteja_wavs
from .pipeline_model import (
    TEMPS_DEC, Clip, clips_de_seccions, fusiona_clips, normalitza_cobertura,
    seccions_de_clips,
)

def filtra_seccions(seccions, durada_min=0.0, fusiona_iguals=False):
    """Post-processa les seccions (opcions del dialeg; motor qm-segmenter).

    Reabsorbit al MODEL DE CLIPS (#11): no manté cap llista paral·lela.

    - `fusiona_iguals`: uneix trossos consecutius amb la MATEIXA etiqueta
      (p. ex. «B» «B» -> una sola secció), conservant-ne els límits.
    - `durada_min`: fusiona els trossos més curts que aquesta durada amb el
      veí (el de l'esquerra, que conserva la seva etiqueta; el primer, amb el
      de la dreta) — el nucli `fusiona_clips`.

    Manté l'invariant: intervals ordenats i contigus (prev.fi == curr.ini).
    """
    if not seccions:
        return []
    clips = clips_de_seccions(seccions)
    if fusiona_iguals:
        out = []
        for c in clips:
            if out and out[-1].payload[0] == c.payload[0]:
                out[-1] = Clip(out[-1].ini, c.fi, out[-1].payload)
            else:
                out.append(c)
        clips = out
    if durada_min and durada_min > 0 and len(clips) > 1:
        i = 0
        while i < len(clips) and len(clips) > 1:
            c = clips[i]
            if (c.fi - c.ini) < durada_min:
                if i > 0:
                    clips = fusiona_clips(clips, i, "anterior")
                    i = max(0, i - 1)
                else:
                    # El primer s'ajunta amb el següent (mana el següent).
                    clips = ([Clip(clips[0].ini, clips[1].fi, clips[1].payload)]
                             + clips[2:])
                    i = 0
            else:
                i += 1
    return seccions_de_clips(clips)
def desa_abc_csv(ruta, seccions, bpm, log, lliure=False, bpb=4, offset=0.0,
                 mapa=None):
    def _escriu(f):
        w = csv.writer(f)
        w.writerow(["inici_s", "fi_s", "durada_s", "lletra", "família",
                    "compas_ini", "compas_fi"])
        for ini, fi, L, fam in seccions:
            dur = fi - ini
            w.writerow([f"{float(ini):.{TEMPS_DEC}f}",
                        f"{float(fi):.{TEMPS_DEC}f}",
                        f"{float(dur):.{TEMPS_DEC}f}", L, fam,
                        pos_compas(ini, bpm, bpb, lliure, offset, mapa),
                        pos_compas(fi, bpm, bpb, lliure, offset, mapa)])
    escriu_atomic(ruta, _escriu)
    seq = seq_abc(seccions)
    log(f"ABC: {len(seccions)} trossos, seqüència {seq}")
    return seccions


def regenera_wavs_estructura(abc_csv, sortida, sr, log, manifest=None):
    dest = os.path.join(sortida, "wavs_estructura")
    neteja_wavs(dest)
    return fer_wavs_estructura(abc_csv, dest, sr, log, manifest=manifest)


def fer_abc(trossos, abc_csv, bpm, log, lliure=False, bpb=4, offset=0.0,
            durada_min=0.0, fusiona_iguals=True, durada=None):
    """Talls (en memòria o camí a un CSV) -> `estructura_ABC.csv`.

    `trossos`: llista `[(ini, durada, index, etiqueta), …]` (el que retorna el
    qm-segmenter) o el camí d'un CSV amb eixes columnes.
    """
    import re

    def familia(lab):
        # El motor d'estructura (qm-segmenter) etiqueta N1,N4,N6... (família N) i B,A,C...
        # Traiem dígits finals i normalitzem: N1->N, n1->N, B->B.
        fam = re.sub(r"\d+$", "", lab.strip()).upper() or lab.strip()
        return fam

    # 1. Llegeix (si cal) + fusiona adjacents de la mateixa família.
    if isinstance(trossos, (str, os.PathLike)):
        with open(trossos, encoding="utf-8") as f:
            files = [[float(r[0]), float(r[1]), r[2], r[3]]
                     for r in csv.reader(f) if len(r) >= 4]
    else:
        files = [[float(r[0]), float(r[1]), r[2], r[3]] for r in (trossos or ())]
    trams = []  # (ini, fi, família, etiqueta_original)
    for ini, dur, _idx, lab in files:
        fam = familia(lab)
        if fusiona_iguals and trams and trams[-1][2] == fam:
            trams[-1][1] = ini + dur
            trams[-1][3] += "+" + lab
        else:
            trams.append([ini, ini + dur, fam, str(lab)])
    trossos = trams
    # 1b. Filtratge per durada minima (opcio del dialeg).
    if durada_min and durada_min > 0:
        trossos = [list(t) for t in filtra_seccions(
            [tuple(t) for t in trossos], durada_min=durada_min)]
    # 2. Família -> lletra per ordre d'aparició (les repeticions casen: A...A).
    lletres = {}
    abc = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    k = 0
    rows = []
    for ini, fi, fam, lab in trossos:
        if fam not in lletres:
            lletres[fam] = abc[k] if k < len(abc) else f"X{k}"
            k += 1
        L = lletres[fam]
        rows.append((ini, fi, L, fam))
    # INVARIANT de COBERTURA: les seccions cobreixen tota la WAV (0 → durada).
    _, rows = normalitza_cobertura([], rows, durada, log=log)
    desa_abc_csv(abc_csv, rows, bpm, log, lliure=lliure, bpb=bpb, offset=offset)
    seq = seq_abc(rows)
    rep = ", ".join(f"{L}×{seq.count(L)}" for L in sorted(set(seq)))
    log(f"ABC famílies {len(lletres)} ({rep})")
    return rows


def style(c):
    """Normalitza noms d’acords a un format estable i llegible.

    Exemples:
    - cmaj7 -> CMaj7
    - am -> A-
    - Em7 -> E-7
    - g/d -> G/D
    - Bbmaj7 -> B♭Maj7
    """
    import re

    if c is None:
        return ""

    s = str(c).strip()
    if not s:
        return ""
    if s.upper() == "N":
        return "N"

    def norm_alt(token):
        if token in {"#", "♯"}:
            return "#"
        if token in {"b", "♭"}:
            return "b"
        return token

    def norm_root(base):
        if not base:
            return ""
        m = re.match(r"^([A-Ga-g])([#b♯♭]?)", base)
        if not m:
            return base
        root, alt = m.groups()
        return f"{root.upper()}{norm_alt(alt)}"

    if "/" in s:
        base, bass = s.split("/", 1)
        return f"{style(base)}/{norm_root(bass)}"

    s = s.replace("♭", "b").replace("♯", "#")
    m = re.match(r"^([A-Ga-g])([#b]?)(.*)$", s)
    if not m:
        return s.strip()

    root, alt, quality = m.groups()
    root = root.upper()
    alt = norm_alt(alt)
    quality = quality.strip()

    if quality.lower().startswith("maj"):
        quality = "Maj" + quality[3:]
    elif quality.lower().startswith("m") and not quality.lower().startswith("maj"):
        quality = "-" + quality[1:]
    elif quality.lower().startswith("dim"):
        quality = "dim" + quality[3:]
    elif quality.lower().startswith("aug"):
        quality = "aug" + quality[3:]

    return f"{root}{alt}{quality}"


def segments_lliures(csv_path, total_s, log):
    # Mode Lliure: com la guia DAW però en segons, sense graella: N s'absorbeix,
    # repetits seguits es fusionen, capçalera N si cal.
    # El CSV del model és `inici,fi,acord` (S3): el fi es re-deriva.
    segs = []
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) < 3 or row[0].startswith("inici"):
                continue
            t, c = float(row[0]), row[2].strip()
            if c == "N" or (segs and segs[-1][1] == style(c)):
                continue
            segs.append([t, style(c)])
    if segs and segs[0][0] > 1e-9:
        segs.insert(0, [0.0, "N"])
        log(f"capçalera N: {segs[1][0]:.2f} s")
    out = []
    for i, (t, c) in enumerate(segs):
        fi = segs[i + 1][0] if i + 1 < len(segs) else total_s
        out.append((t, fi, c))
    return out
def fer_wavs_estructura(abc_csv, dest_dir, sr, log, manifest=None):
    os.makedirs(dest_dir, exist_ok=True)
    n = 0
    usats = set()          # desambigua etiquetes de secció que quedin iguals
    with open(abc_csv, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            def _neta_pos(txt):
                # Un clip «en segons» dona «—» (sense compàs): el nom del WAV
                # ha de ser un fitxer vàlid a tots els sistemes.
                txt = str(txt or "").replace(".", "-").replace("—", "s")
                return "".join(c if (c.isalnum() or c in "-_") else "_"
                               for c in txt) or "X"

            nm = (f"{_neta_pos(r['compas_ini'])}_"
                  f"{_neta_pos(r['compas_fi'])}_"
                  f"{safe_filename(r['lletra'], fallback='X', usats=usats)}")
            try:
                ini = float(r["inici_s"])
                fi = float(r["fi_s"])
            except (KeyError, TypeError, ValueError):
                # CSV antic/manual sense les columnes de segons: el WAV encara
                # es pot generar per `durada_s`; el manifest no hi pot posar
                # temps exactes i s'omet eixa fila.
                ini = fi = None
            dur = float(r["durada_s"])
            frames = int(round(dur * sr))
            if frames <= 0:
                # Mateix motiu que als acords: mai un WAV de durada 0.
                log(f"wavs_estructura: secció {r.get('lletra', '?')} de durada "
                    f"0 → s'omet")
                continue
            with wave.open(os.path.join(dest_dir, nm + ".wav"), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sr)
                w.writeframes(b"\x00" * (frames * 2))
            if manifest is not None and ini is not None:
                manifest.append(("estructura", nm + ".wav", ini, fi, dur,
                                 r["lletra"],
                                 f"{r['compas_ini']}–{r['compas_fi']}"))
            n += 1
    log(f"wavs_estructura: {n}")
    return n
