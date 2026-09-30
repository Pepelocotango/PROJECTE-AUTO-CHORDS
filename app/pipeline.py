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
]


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


def fer_abc(seg_csv, abc_csv, bpm, log, lliure=False):
    step = 60.0 / bpm / 2
    SB = 8  # ranures per compàs de 4 temps (graella de corxera)

    def pos(t):
        if lliure:
            return f"{t:07.2f}s"  # zero-padding: ordena bé a la carpeta
        p = max(0, round(t / step))
        return "%d.%d.%d" % (p // SB + 1, (p % SB) // 2 + 1, 1 + 2 * (p % 2))

    lletres = {}
    abc = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    k = 0
    rows = []
    with open(seg_csv, encoding="utf-8") as f:
        for ini, dur, _idx, lab in csv.reader(f):
            ini, dur = float(ini), float(dur)
            if lab not in lletres:
                lletres[lab] = abc[k]
                k += 1
            L = lletres[lab]
            rows.append((ini, ini + dur, dur, L, lab, pos(ini), pos(ini + dur)))
    with open(abc_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["inici_s", "fi_s", "durada_s", "lletra", "família",
                    "compas_ini", "compas_fi"])
        for ini, fi, dur, L, lab, pi, pf in rows:
            w.writerow([round(ini, 2), round(fi, 2), round(dur, 2), L,
                        lab, pi, pf])
    log(f"ABC: {len(rows)} trossos, seqüència {''.join(r[3] for r in rows)}")
    return rows


def style(c):
    # espill de acords_a_live.py: Cmaj7->CMaj7, Am->A-, Em7->E-7
    import re
    c = re.sub(r"^([A-G][#b]?)maj", r"\1Maj", c)
    return re.sub(r"^([A-G][#b]?)m(?!aj|Aj)", r"\1-", c)


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
              f"{chord.replace('/', '-')}.wav")
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
            fn = f"{pos_.replace('.', '-')}_{chord.replace('/', '-')}.wav"
            escriu(fn, float(dur))
            n += 1
    log(f"wavs_acords: {n}")
    return n


def fer_wavs_estructura(abc_csv, dest_dir, sr, log):
    os.makedirs(dest_dir, exist_ok=True)
    n = 0
    with open(abc_csv, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            nm = (f"{r['compas_ini'].replace('.', '-')}_"
                  f"{r['compas_fi'].replace('.', '-')}_{r['lletra']}")
            frames = int(round(float(r["durada_s"]) * sr))
            with wave.open(os.path.join(dest_dir, nm + ".wav"), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sr)
                w.writeframes(b"\x00" * (frames * 2))
            n += 1
    log(f"wavs_estructura: {n}")
    return n
