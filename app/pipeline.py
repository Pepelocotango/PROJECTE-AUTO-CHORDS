#!/usr/bin/env python3
# pipeline.py — motor de l'Auto Chords (stdlib + binaris del projecte).
# Cadena: wav -> csv acords (annotator+Chordino) -> locators/guia ->
#         wavs_acords (+ segmentino -> ABC -> wavs_estructura, opcional).
# Tot en català.
import csv
import os
import subprocess
import wave

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJ_DIR = os.path.dirname(APP_DIR)
SONIC = os.path.join(PROJ_DIR, "sonic-annotator")
ACORDS_PY = os.path.join(PROJ_DIR, "acords_a_live.py")
VAMP_DIRS = [
    os.path.join(PROJ_DIR, "nnls-chroma-linux64-local"),
    os.path.join(PROJ_DIR, "segmentino-linux64-local"),
    # tempo/beats via aubio (compilat localment; vegeu docs/AUBIO_TEMPO.md)
    os.path.join(PROJ_DIR, "vamp-aubio-linux64-local"),
]


def safe_filename(name, fallback="X"):
    """Retorna un nom segur per usar com a part d un filename.

    - Substitueix separadors de path (/ i os.sep) per -
    - Treu caracters de control (\0, \n, \r, \t)
    - Retorna fallback si el resultat es buit
    - Trunca a 64 caracters per evitar toxicitat
    """
    s = str(name).strip()
    s = s.replace(os.sep, "-").replace("/", "-").replace("\\", "-")
    s = s.replace("\0", "").replace("\n", "").replace("\r", "").replace("\t", "")
    s = s.strip()
    if not s:
        s = fallback
    return s[:64]


def _vamp_env():
    env = dict(os.environ)
    env["VAMP_PATH"] = ":".join(VAMP_DIRS)
    return env


def run(cmd, log, cwd=None):
    log("$ " + " ".join(cmd))
    p = subprocess.run(cmd, capture_output=True, text=True, env=_vamp_env(),
                       cwd=cwd)
    for line in (p.stdout + p.stderr).splitlines():
        line = line.strip()
        if line and "Extracting features..." not in line:
            log("  " + line)
    if p.returncode != 0:
        raise RuntimeError(f"ha fallat: {cmd[0]} (codi {p.returncode})")
    return p


def wav_info(path):
    with wave.open(path, "rb") as w:
        return {
            "canals": w.getnchannels(),
            "mostreig": w.getframerate(),
            "durada": w.getnframes() / w.getframerate(),
        }


def extract_chords(wav_path, out_csv, log):
    run([SONIC, "-d", "vamp:nnls-chroma:chordino:simplechord",
         "-w", "csv", "--csv-one-file", out_csv, "--csv-force",
         "--csv-omit-filename", wav_path], log)


def detecta_bpm(wav_path, log):
    """Estima el BPM amb el plugin Vamp d'aubio, a partir de les pulsacions.

    Retorna float (BPM) o None si no es pot estimar. El BPM es deriva de la
    MEDIANA dels intervals entre pulsacions (mes estable que el `tempo`
    per fotograma). Vegeu docs/AUBIO_TEMPO.md.
    """
    import statistics
    import tempfile
    tmp = tempfile.mkdtemp(prefix="ac_bpm_")
    out = os.path.join(tmp, "beats.csv")
    try:
        run([SONIC, "-d", "vamp:vamp-aubio:aubiotempo:beats",
             "-w", "csv", "--csv-one-file", out, "--csv-force",
             "--csv-omit-filename", wav_path], log)
        beats = []
        with open(out, newline="", encoding="utf-8") as f:
            for fila in csv.reader(f):
                # agafem l'ultim camp numeric de cada fila (robust a formats)
                for camp in reversed(fila):
                    try:
                        beats.append(float(camp))
                        break
                    except (ValueError, TypeError):
                        continue
        iv = [b - a for a, b in zip(beats, beats[1:])]
        iv = [x for x in iv if 0.2 < x < 2.0]     # descarta outliers
        if len(iv) < 4:
            log("BPM: pocs beats detectats")
            return None
        med = statistics.median(iv)
        bpm = 60.0 / med if med > 0 else None
        log(f"BPM detectat: {bpm:.1f} ({len(beats)} pulsacions, "
            f"interval mediana {med:.3f}s)")
        return bpm
    except Exception as e:  # noqa: BLE001
        log(f"BPM: no s'ha pogut detectar ({e})")
        return None


def extract_segments(wav_path, out_csv, log):
    run([SONIC, "-d", "vamp:segmentino:segmentino:segmentation",
         "-w", "csv", "--csv-one-file", out_csv, "--csv-force",
         "--csv-omit-filename", wav_path], log)


def run_acords_py(csv_path, bpm, bpb, offset, workdir, log):
    run(["python3", ACORDS_PY, csv_path, str(bpm), str(bpb),
         str(offset)], log, cwd=workdir)
    # el py escriu al directori de treball
    return (os.path.join(workdir, "acords_locators.txt"),
            os.path.join(workdir, "guia_acords.html"))


def pos_compas(t, bpm, bpb=4, lliure=False):
    """Posició en format compàs.temps.subdivisió (qualsevol compàs).

    Graella = corxera (mig temps). `bpb` = temps per compàs, així funciona
    amb 3/4, 6/8, 5/4... (abans estava fixat a 8 corxeres = només 4/4).
    """
    if lliure:
        return f"{float(t):07.2f}s"
    step = 60.0 / bpm / 2              # corxera
    SB = max(1, int(bpb)) * 2          # corxeres per compàs
    p = max(0, round(float(t) / step))
    return "%d.%d.%d" % (p // SB + 1, (p % SB) // 2 + 1, 1 + 2 * (p % 2))


def seq_abc(seccions):
    return "".join(s[2] for s in seccions)


def lletra_lliure(seccions):
    usades = {s[2] for s in seccions}
    abc = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for L in abc:
        if L not in usades:
            return L
    k = 0
    while f"X{k}" in usades:
        k += 1
    return f"X{k}"


def parteix_seccio(seccions, i, talla, marge=0.05):
    # Un tros → dos. La primera meitat conserva lletra; la segona en pren una de nova.
    if i < 0 or i >= len(seccions):
        raise ValueError("índex de secció inexistent")
    ini, fi, L, fam = seccions[i]
    talla = float(talla)
    if not (ini + marge < talla < fi - marge):
        raise ValueError(
            f"el tall ({talla:.2f}s) ha de caure dins {ini:.2f}–{fi:.2f}s")
    nova = lletra_lliure(seccions)
    a = (ini, talla, L, fam)
    b = (talla, fi, nova, nova)
    return list(seccions[:i]) + [a, b] + list(seccions[i + 1:])


def fusiona_seccions(seccions, i, amb="seguent"):
    # Fusiona i amb el veí. Conserva lletra i família del que queda a l'esquerra.
    if not seccions or i < 0 or i >= len(seccions):
        raise ValueError("índex de secció inexistent")
    if amb == "anterior":
        if i == 0:
            raise ValueError("no hi ha secció anterior")
        i = i - 1
    elif amb != "seguent":
        raise ValueError("amb ha de ser 'seguent' o 'anterior'")
    if i >= len(seccions) - 1:
        raise ValueError("no hi ha secció següent")
    a, b = seccions[i], seccions[i + 1]
    nou = (a[0], b[1], a[2], a[3])
    return list(seccions[:i]) + [nou] + list(seccions[i + 2:])


def desa_abc_csv(ruta, seccions, bpm, log, lliure=False, bpb=4):
    os.makedirs(os.path.dirname(os.path.abspath(ruta)) or ".", exist_ok=True)
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["inici_s", "fi_s", "durada_s", "lletra", "família",
                    "compas_ini", "compas_fi"])
        for ini, fi, L, fam in seccions:
            dur = fi - ini
            w.writerow([f"{float(ini):.{TEMPS_DEC}f}",
                        f"{float(fi):.{TEMPS_DEC}f}",
                        f"{float(dur):.{TEMPS_DEC}f}", L, fam,
                        pos_compas(ini, bpm, bpb, lliure),
                        pos_compas(fi, bpm, bpb, lliure)])
    seq = seq_abc(seccions)
    log(f"ABC: {len(seccions)} trossos, seqüència {seq}")
    return seccions


def regenera_wavs_estructura(abc_csv, sortida, sr, log):
    dest = os.path.join(sortida, "wavs_estructura")
    neteja_wavs(dest)
    return fer_wavs_estructura(abc_csv, dest, sr, log)


def fer_abc(seg_csv, abc_csv, bpm, log, lliure=False, bpb=4):
    import re

    def familia(lab):
        # Segmentino etiqueta N1,N4,N6... (mateixa família N) i B,A,C...
        # Traiem dígits finals i normalitzem: N1->N, n1->N, B->B.
        fam = re.sub(r"\d+$", "", lab.strip()).upper() or lab.strip()
        return fam

    # 1. Llegeix + fusiona adjacents de la mateixa família (C-C -> un sol tros).
    trossos = []  # (ini, fi, família, etiqueta_original)
    with open(seg_csv, encoding="utf-8") as f:
        for ini, dur, _idx, lab in csv.reader(f):
            ini, dur = float(ini), float(dur)
            fam = familia(lab)
            if trossos and trossos[-1][2] == fam:
                trossos[-1][1] = ini + dur
                trossos[-1][3] += "+" + lab
            else:
                trossos.append([ini, ini + dur, fam, lab])
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
    desa_abc_csv(abc_csv, rows, bpm, log, lliure=lliure, bpb=bpb)
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
    # com acords_a_live.py però en segons, sense graella: N s'absorbeix,
    # repetits seguits es fusionen, capçalera N si cal.
    segs = []
    with open(csv_path, encoding="utf-8") as f:
        for t, c in csv.reader(f):
            t, c = float(t), c.strip()
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


def fer_wavs_acords_lliures(csv_path, total_s, dest_dir, sr, log):
    os.makedirs(dest_dir, exist_ok=True)
    n = 0
    for ini, fi, chord in segments_lliures(csv_path, total_s, log):
        frames = int(round((fi - ini) * sr))
        fn = (f"{ini:07.2f}s_{fi:07.2f}s_"
              f"{safe_filename(chord, fallback='N')}.wav")
        with wave.open(os.path.join(dest_dir, fn), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(b"\x00" * (frames * 2))
        n += 1
    log(f"wavs_acords: {n}")
    return n


def fer_wavs_acords(locators_txt, bpm, dest_dir, sr, log, bpb=4):
    os.makedirs(dest_dir, exist_ok=True)

    def inici_en_temps(pos_):
        b, t, s = (int(x) for x in pos_.split("."))
        return (b - 1) * bpb + (t - 1) + (s - 1) / 4.0

    def escriu(nom, temps):
        frames = int(round(temps * 60.0 / bpm * sr))
        with wave.open(os.path.join(dest_dir, nom), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(b"\x00" * (frames * 2))

    n = 0
    primer = True
    with open(locators_txt, encoding="utf-8") as f:
        for line in f.read().splitlines()[1:]:
            if not line.strip():
                continue
            pos_, chord, dur = line.split()
            if primer:
                # la tanda sempre engega a l'1-1-1: buit inicial -> N
                cap = inici_en_temps(pos_)
                if cap > 1e-9:
                    escriu("1-1-1_N.wav", cap)
                    n += 1
                    log(f"capçalera N: {cap:.2f} temps")
                primer = False
            fn = f"{pos_.replace('.', '-')}_{safe_filename(chord, fallback='N')}.wav"
            escriu(fn, float(dur))
            n += 1
    log(f"wavs_acords: {n}")
    return n


def exporta_total(csv_ac, csv_seg, sortida, bpm, bpb, offset, sr, log,
                 tempo_fix=True, amb_estructura=True, total_s=None):
    """Exporta el flux complet a partir dels CSVs ja generats.

    Retorna un diccionari amb les rutes finals (csv + carpetes).
    """
    sortida = os.path.abspath(sortida)
    os.makedirs(sortida, exist_ok=True)
    csv_ac = os.path.abspath(csv_ac)
    if not os.path.isfile(csv_ac):
        raise FileNotFoundError(f"No trobo acords.csv: {csv_ac}")

    result = {"acords_csv": csv_ac, "sortida": sortida}
    if tempo_fix:
        loc, guia = run_acords_py(csv_ac, bpm, bpb, offset, sortida, log)
        result["locators_txt"] = loc
        result["guia_html"] = guia
        dest = os.path.join(sortida, "wavs_acords")
        neteja_wavs(dest)
        result["n_acords_wavs"] = fer_wavs_acords(loc, bpm, dest, sr, log, bpb)
    else:
        if total_s is None:
            total_s = 0.0
            with open(csv_ac, encoding="utf-8") as f:
                for row in csv.reader(f):
                    if not row or row[0].startswith("posici"):
                        continue
                    try:
                        total_s = max(total_s, float(row[0]))
                    except ValueError:
                        pass
        dest = os.path.join(sortida, "wavs_acords")
        neteja_wavs(dest)
        result["n_acords_wavs"] = fer_wavs_acords_lliures(
            csv_ac, total_s, dest, sr, log)

    if amb_estructura and csv_seg:
        csv_seg = os.path.abspath(csv_seg)
        if not os.path.isfile(csv_seg):
            raise FileNotFoundError(f"No trobo segments.csv: {csv_seg}")
        abc = os.path.join(sortida, "estructura_ABC.csv")
        result["segments_csv"] = csv_seg
        result["abc_csv"] = abc
        fer_abc(csv_seg, abc, bpm, log, lliure=not tempo_fix, bpb=bpb)
        dest_abc = os.path.join(sortida, "wavs_estructura")
        neteja_wavs(dest_abc)
        result["n_estructura_wavs"] = fer_wavs_estructura(
            abc, dest_abc, sr, log)

    return result


# Resolució temporal unificada dels CSV: 10 ms (2 decimals) — opció (b).
# Abans: acords.csv guardava 9 decimals i estructura_ABC.csv 2 → incoherent.
TEMPS_DEC = 2


def desa_acords_csv(ruta, items):
    """Desa (temps, acord) amb el temps arrodonit a TEMPS_DEC decimals.

    S'ha unificat la resolució amb estructura_ABC.csv (10 ms) perquè els
    límits de secció i els temps d'acord siguin coherents.
    """
    os.makedirs(os.path.dirname(os.path.abspath(ruta)) or ".", exist_ok=True)
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for it in items:
            t, c = it[0], it[1]
            w.writerow([f"{float(t):.{TEMPS_DEC}f}", c])


def neteja_wavs(dest_dir):
    if not os.path.isdir(dest_dir):
        return
    for fn in os.listdir(dest_dir):
        if fn.endswith(".wav"):
            os.remove(os.path.join(dest_dir, fn))


def regenera_wavs_acords(csv_path, sortida, bpm, bpb, offset, total_s, sr, log,
                         tempo_fix=True):
    # Recalcula locators/guia + wavs_acords/ a partir del csv ja editat.
    dest = os.path.join(sortida, "wavs_acords")
    neteja_wavs(dest)
    if tempo_fix:
        loc, _guia = run_acords_py(csv_path, bpm, bpb, offset, sortida, log)
        return fer_wavs_acords(loc, bpm, dest, sr, log, bpb)
    return fer_wavs_acords_lliures(csv_path, total_s, dest, sr, log)


def fer_wavs_estructura(abc_csv, dest_dir, sr, log):
    os.makedirs(dest_dir, exist_ok=True)
    n = 0
    with open(abc_csv, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            nm = (f"{r['compas_ini'].replace('.', '-')}_"
                  f"{r['compas_fi'].replace('.', '-')}_"
                  f"{safe_filename(r['lletra'], fallback='X')}")
            frames = int(round(float(r["durada_s"]) * sr))
            with wave.open(os.path.join(dest_dir, nm + ".wav"), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sr)
                w.writeframes(b"\x00" * (frames * 2))
            n += 1
    log(f"wavs_estructura: {n}")
    return n
