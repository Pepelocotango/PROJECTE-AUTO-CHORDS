#!/usr/bin/env python3
# pipeline.py — motor de l'Auto Chords (stdlib + binaris del projecte).
# Cadena: wav -> csv acords (annotator+Chordino) -> locators/guia ->
#         wavs_acords (+ qm-segmenter -> ABC -> wavs_estructura, opcional).
# Tot en català.
import csv
import os
import re
import subprocess
import wave

from app import plataforma, tempo

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJ_DIR = os.path.dirname(APP_DIR)
SONIC = os.path.join(PROJ_DIR, "OLD", "sonic-annotator")   # arxivat (reserva)
ACORDS_PY = os.path.join(PROJ_DIR, "acords_a_live.py")
# Directoris dels plugins Vamp SEGONS EL SO (vegeu `app/plataforma.py`):
#   Linux   -> nnls-chroma-linux64-local + qm-vamp-plugins-linux64-local
#   Windows -> nnls-chroma-win64-local   + qm-vamp-plugins-win64-local
#   macOS   -> nnls-chroma-macos-local   + qm-vamp-plugins-macos-local
VAMP_DIRS = plataforma.dirs_plugins(PROJ_DIR)


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
    env["VAMP_PATH"] = plataforma.path_env_vamp(VAMP_DIRS)
    return env


def run(cmd, log, cwd=None, timeout=600, silenci=False):
    """Executa una comanda externa. `timeout` evita penjaments indefinits.

    Sense timeout, si un subprocés es queda encallat (esperant stdin, un
    dispositiu d'àudio inexistent...) l'app i els tests es penjarien.
    """
    if not silenci:
        log("$ " + " ".join(cmd))
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, env=_vamp_env(),
                           cwd=cwd, timeout=timeout)
    except subprocess.TimeoutExpired:
        log(f"  ⏱️ TIMEOUT ({timeout}s): {cmd[0]} no ha respost")
        raise
    if not silenci:
        for line in (p.stdout + p.stderr).splitlines():
            line = line.strip()
            if line and "Extracting features..." not in line:
                log("  " + line)
    if p.returncode != 0:
        # Inclou la cua de stderr: si el log és un no-op (p. ex. dins els tests)
        # la causa es perdia i només es veia "codi 1", sense cap pista.
        cua = [l.strip() for l in (p.stderr or "").splitlines() if l.strip()]
        raise RuntimeError(f"ha fallat: {cmd[0]} (codi {p.returncode})"
                           + (": " + " | ".join(cua[-3:]) if cua else ""))
    return p


def wav_info(path):
    with wave.open(path, "rb") as w:
        return {
            "canals": w.getnchannels(),
            "mostreig": w.getframerate(),
            "durada": w.getnframes() / w.getframerate(),
        }


# --- Host Vamp propi (vamp_host_local) ------------------------------------
# Substitueix `sonic-annotator` (que arrossegava Qt6/ICU/glib). El nostre host
# nomes depen de libc/libstdc++/sndfile. Vegeu eines/vamp_host.cpp.
HOST = os.path.join(PROJ_DIR, plataforma.NOM_HOST)   # .exe a Windows

# mida de finestra (step, block) per transform: son les que fa servir el
# sonic-annotator (extretes del seu `-s`). Calen per replicar-ne la resolucio.
STEPS = {
    "vamp:nnls-chroma:chordino:simplechord": (2048, 16384),
    "vamp:nnls-chroma:chordino:loglikelihood": (2048, 16384),
    "vamp:nnls-chroma:chordino:chordnotes": (2048, 16384),
    "vamp:qm-vamp-plugins:qm-segmenter:segmentation": (8820, 26460),
    "vamp:qm-vamp-plugins:qm-tempotracker:tempo": (512, 1024),
    "vamp:qm-vamp-plugins:qm-tempotracker:beats": (512, 1024),
    "vamp:qm-vamp-plugins:qm-onsetdetector:onsets": (512, 1024),
    "vamp:qm-vamp-plugins:qm-barbeattracker:bars": (512, 1024),
    "vamp:qm-vamp-plugins:qm-barbeattracker:beats": (512, 1024),
    "vamp:qm-vamp-plugins:qm-keydetector:key": (512, 1024),
}


def usa_host():
    """Cert si hi ha el nostre host Vamp (preferent al sonic-annotator)."""
    return os.path.isfile(HOST) and os.access(HOST, os.X_OK)


def _cmd_transform(transform, out_csv, wav, params=None):
    """Comanda per executar un transform: el nostre host, o sonic-annotator."""
    if usa_host():
        cmd = [HOST, "--plugin", transform.replace("vamp:", ""),
               "--csv", out_csv]
        st = STEPS.get(transform)
        if st:
            # Les mides de la taula son per 44100 Hz; els plugins les volen
            # escalades al mostreig real (p. ex. el barbeattracker vol 256 a
            # 22050 i 512 a 44100).
            try:
                sr = wav_info(wav)["mostreig"]
            except Exception:  # noqa: BLE001
                # fallback: si no puc llegir el mostreig, assumeixo 44100
                sr = 44100
            esc = (sr / 44100.0) if sr else 1.0
            stp = max(1, int(round(st[0] * esc)))
            blk = max(1, int(round(st[1] * esc)))
            cmd += ["--step", str(stp), "--block", str(blk)]
        for k, v in (params or {}).items():
            cmd += ["--param", f"{k}={v}"]
        cmd.append(wav)
        return cmd
    if params:
        import tempfile
        ttl = os.path.join(tempfile.mkdtemp(prefix="ac_ttl_"), "t.ttl")
        escriu_ttl("chords" if "chordino" in transform else "structure",
                   params, ttl, lambda *a: None)
        return [SONIC, "-t", ttl, "-w", "csv", "--csv-one-file", out_csv,
                "--csv-force", "--csv-omit-filename", wav]
    return [SONIC, "-d", transform, "-w", "csv", "--csv-one-file", out_csv,
            "--csv-force", "--csv-omit-filename", wav]


def executa_transform(transform, out_csv, wav, log, params=None):
    """Executa un transform Vamp i desa el CSV.

    Primer amb el step/block de la taula (fidelitat amb el sonic-annotator);
    si el plugin els refusa (depenen del mostreig), reintenta amb els seus
    valors preferits (sempre funcionen).
    """
    cmd = _cmd_transform(transform, out_csv, wav, params)
    try:
        return run(cmd, log)
    except RuntimeError:
        if "--step" not in cmd:
            raise
        cmd2 = _cmd_transform(transform, out_csv, wav, params)
        i = cmd2.index("--step")
        del cmd2[i:i + 4]                 # treu --step N --block M
        if log:
            log("  (step/block de la taula refusats; uso els del plugin)")
        return run(cmd2, log)


# Transform Vamp per defecte de cada deteccio (vegeu docs/AUTODETECCIO_OPCIONS.md)
TRANSFORMS = {
    "chords": "vamp:nnls-chroma:chordino:simplechord",
    "structure": "vamp:qm-vamp-plugins:qm-segmenter:segmentation",
}


def escriu_ttl(clau, params, dest, log):
    """Genera un transform `.ttl` del transform `clau` amb `params` aplicats.

    IMPORTANT: `sonic-annotator -s <id>` NOMES llista una part dels parametres
    (p. ex. no hi surt `useHMM`), aixi que no podem pedacar el TTL per defecte.
    El reconstruim: prenem plugin/step/block/output del TTL per defecte i hi
    afegim un `vamp:parameter_binding` per a CADA parametre del descriptor .n3
    (amb el valor demanat o el seu defecte).
    """
    from app import vamp_params          # import local: evita cicle d'imports
    base = run([SONIC, "-s", TRANSFORMS[clau]], log, silenci=True).stdout

    def _cap(patro):
        m = re.search(patro, base)
        return m.group(1) if m else None

    plugin = _cap(r"vamp:plugin\s+<([^>]*)>")
    step = _cap(r'vamp:step_size\s+"([^"]*)"')
    block = _cap(r'vamp:block_size\s+"([^"]*)"')
    versio = _cap(r'vamp:plugin_version\s+"""(\d+)"""')
    output = _cap(r"vamp:output\s+<([^>]*)>")
    if not (plugin and output):
        raise RuntimeError(f"no puc llegir el transform per defecte de {clau}")

    specs = vamp_params.params_de(clau)
    triats = {s["id"]: triats_val for s in specs
              for triats_val in [float((params or {}).get(s["id"], s["defecte"]))]}
    linies = ['@prefix xsd:      <http://www.w3.org/2001/XMLSchema#> .',
              '@prefix vamp:     <http://purl.org/ontology/vamp/> .',
              '@prefix :         <#> .',
              ':transform a vamp:Transform ;',
              f'    vamp:plugin <{plugin}> ;',
              f'    vamp:step_size "{step}"^^xsd:int ;',
              f'    vamp:block_size "{block}"^^xsd:int ;']
    if versio:
        linies.append(f'    vamp:plugin_version """{versio}""" ;')
    for s in specs:
        linies.append('    vamp:parameter_binding [')
        linies.append(f'        vamp:parameter [ vamp:identifier "{s["id"]}" ] ;')
        linies.append(f'        vamp:value "{triats[s["id"]]}"^^xsd:float ;')
        linies.append('    ] ;')
    linies.append(f'    vamp:output <{output}> .')
    with open(dest, "w", encoding="utf-8") as f:
        f.write("\n".join(linies) + "\n")
    log(f"  transform {clau}: {len(specs)} paràmetres "
        f"({sum(1 for s in specs if s['id'] in (params or {}))} ajustats)")
    return dest


def extract_chords(wav_path, out_csv, log, params=None):
    """Acords via Chordino (host propi; `params` son els parametres .n3)."""
    if usa_host():
        return executa_transform(TRANSFORMS["chords"], out_csv, wav_path, log,
                                 params)
    if params:
        import tempfile
        ttl = os.path.join(tempfile.mkdtemp(prefix="ac_ttl_"), "chords.ttl")
        escriu_ttl("chords", params, ttl, log)
        run([SONIC, "-t", ttl, "-w", "csv", "--csv-one-file", out_csv,
             "--csv-force", "--csv-omit-filename", wav_path], log)
    else:
        run([SONIC, "-d", TRANSFORMS["chords"],
             "-w", "csv", "--csv-one-file", out_csv, "--csv-force",
             "--csv-omit-filename", wav_path], log)


MOTORS_BPM = ("nostre", "qm", "consens")
MOTORS_ESTRUCTURA = ("qm",)


def _qm_valors(transform, wav_path, col=1, timeout=1800):
    """Valors numerics d'una columna d'un transform del qm."""
    import tempfile
    d = tempfile.mkdtemp(prefix="ac_qm_")
    out = os.path.join(d, "x.csv")
    executa_transform(transform, out, wav_path, lambda *a: None)
    vals = []
    if os.path.exists(out):
        with open(out, newline="", encoding="utf-8") as f:
            for r in csv.reader(f):
                try:
                    vals.append(float(r[col]))
                except (ValueError, IndexError):
                    continue
    return vals


def detecta_bpm_qm(wav_path, log=None):
    """BPM amb el qm-tempotracker (mediana dels valors per fotograma)."""
    import statistics
    vals = _qm_valors("vamp:qm-vamp-plugins:qm-tempotracker:tempo",
                      wav_path)
    if not vals:
        return None
    bpm = statistics.median(vals)
    if log:
        log(f"BPM (qm-tempotracker): {bpm:.1f}")
    return bpm


def detecta_bpm(wav_path, log, bpm_min=None, bpm_max=None, preferit=None,
                motor="nostre"):
    """Estima el BPM d'una WAV (numpy pur, vegeu app/tempo.py).

    Substitueix l'antic metode basat en el beat tracker d'aubio, que
    s'enganxava a un pols erroni en trossos del tema (p. ex. amb silenci
    inicial o directes). El nou mesura la periodicitat real de la musica.
    `bpm_min`/`bpm_max`/`preferit` son opcionals (dialeg d'opcions).
    """
    if motor == "qm":
        return detecta_bpm_qm(wav_path, log)
    if motor == "consens":
        return _bpm_consens(wav_path, log, bpm_min, bpm_max, preferit)
    kw = {}
    if bpm_min is not None:
        kw["bpm_min"] = bpm_min
    if bpm_max is not None:
        kw["bpm_max"] = bpm_max
    if preferit is not None:
        kw["preferit"] = preferit
    return tempo.detecta_bpm(wav_path, log, **kw)


def _bpm_consens(wav_path, log, bpm_min, bpm_max, preferit):
    """Consens: si el nostre motor i el qm coincideixen, confiança alta.

    Si difereixen mes d'un 4 %, guanya el nostre (afinat) i s'avisa.
    """
    kw = {}
    if bpm_min is not None:
        kw["bpm_min"] = bpm_min
    if bpm_max is not None:
        kw["bpm_max"] = bpm_max
    if preferit is not None:
        kw["preferit"] = preferit
    nostre = tempo.detecta_bpm(wav_path, log, **kw)
    qm = detecta_bpm_qm(wav_path, log)
    if not nostre:
        return qm
    if not qm:
        return nostre
    # coincideixen (mateix tempo o doble/meitat exactes)?
    ratio = max(nostre, qm) / min(nostre, qm)
    for r in (1.0, 2.0):
        if abs(ratio - r) < 0.045 * r:
            log(f"consens: els dos motors coincideixen ({nostre:.1f} / "
                f"{qm:.1f}) → {nostre:.1f}")
            return nostre
    log(f"⚠️ consens: els motors NO coincideixen (nostre {nostre:.1f} vs "
        f"qm {qm:.1f}) → em quedo el nostre")
    return nostre


# --- Queen Mary: onsets, bars, beats, key (vegeu docs/QM_VAMP.md) ----------
QM = {
    "onsets": "vamp:qm-vamp-plugins:qm-onsetdetector:onsets",
    "bars": "vamp:qm-vamp-plugins:qm-barbeattracker:bars",
    "beats": "vamp:qm-vamp-plugins:qm-barbeattracker:beats",
    "key": "vamp:qm-vamp-plugins:qm-keydetector:key",
    "segments": "vamp:qm-vamp-plugins:qm-segmenter:segmentation",
}


def _qm_temps(transform, wav_path, timeout=1800, log=None):
    """Primera columna (segons) d'un transform del qm (onsets/bars/beats).

    `log` (opcional) rep la sortida del host; si no es passa, es descarta.
    """
    import tempfile
    d = tempfile.mkdtemp(prefix="ac_qm_")
    out = os.path.join(d, "x.csv")
    executa_transform(transform, out, wav_path, log or (lambda *a: None))
    temps = []
    if os.path.exists(out):
        with open(out, newline="", encoding="utf-8") as f:
            for r in csv.reader(f):
                try:
                    temps.append(float(r[0]))
                except (ValueError, IndexError):
                    continue
    return temps


def detecta_compas1(wav_path, log=None):
    """Segon on cau el COMPÀS 1 (primer downbeat real de la cançó).

    Usa el qm: el **primer onset** marca l'inici de la música i el **primer
    bar** (downbeat) a partir d'aquí és el compàs 1. Al tema de 101 (9,5 s de
    silenci) dona 9,49 s — exacte. Retorna el segon (float) o None.
    """
    def _log(t):
        if log:
            log(t)
    ons = _qm_temps(QM["onsets"], wav_path, log=_log)
    bars = _qm_temps(QM["bars"], wav_path, log=_log)
    if not bars:
        _log("compàs 1: no he pogut detectar els compassos")
        return None
    inici = ons[0] if ons else 0.0
    marge = 0.35                       # tolerància (el bar pot caure just abans)
    cand = [b for b in bars if b >= inici - marge]
    compas = cand[0] if cand else bars[0]
    _log(f"compàs 1: {compas:.2f}s (inici de música {inici:.2f}s, "
         f"{len(bars)} compassos)")
    return compas


def extract_segments(wav_path, out_csv, log, params=None, motor="qm"):
    """Estructura via qm-segmenter (unic motor des de v0.5).

    El Segmentino s'ha retirat: el qm-segmenter el substitueix i, a mes, troba
    les repeticions (A...A). Format (inici, durada, index, etiqueta) -> fer_abc.
    """
    return executa_transform(QM["segments"], out_csv, wav_path, log)


def _extract_segments_segmentino(wav_path, out_csv, log, params=None):
    """[historic] Segmentino. Retirat de la UI; es conserva per referencia."""
    if params:
        import tempfile
        ttl = os.path.join(tempfile.mkdtemp(prefix="ac_ttl_"), "seg.ttl")
        escriu_ttl("structure", params, ttl, log)
        run([SONIC, "-t", ttl, "-w", "csv", "--csv-one-file", out_csv,
             "--csv-force", "--csv-omit-filename", wav_path], log)
    else:
        run([SONIC, "-d", TRANSFORMS["structure"],
             "-w", "csv", "--csv-one-file", out_csv, "--csv-force",
             "--csv-omit-filename", wav_path], log)


def filtra_seccions(seccions, durada_min=0.0, fusiona_iguals=False):
    """Post-processa les seccions (opcions del dialeg; motor qm-segmenter).

    - `fusiona_iguals`: uneix trossos consecutius amb la MATEIXA etiqueta
      (p. ex. «B» «B» -> una sola secció), conservant-ne els límits.
    - `durada_min`: fusiona els trossos més curts que aquesta durada amb el
      veí (el de l'esquerra; el primer, amb el de la dreta).

    Manté l'invariant: intervals ordenats i contigus (prev.fi == curr.ini).
    """
    if not seccions:
        return []
    s = [list(x) for x in seccions]
    if fusiona_iguals:
        out = []
        for it in s:
            if out and out[-1][2] == it[2]:
                out[-1][1] = it[1]            # esten el fi del mateix grup
            else:
                out.append(it)
        s = out
    if durada_min and durada_min > 0 and len(s) > 1:
        i = 0
        while i < len(s) and len(s) > 1:
            if (s[i][1] - s[i][0]) < durada_min:
                if i > 0:
                    s[i - 1][1] = s[i][1]
                    del s[i]
                    i = max(0, i - 1)
                else:
                    s[1][0] = s[0][0]
                    del s[0]
            else:
                i += 1
    return [tuple(x) for x in s]


def run_acords_py(csv_path, bpm, bpb, offset, workdir, log):
    # `sys.executable` (mai un `python3` fix): trencava a Windows i amb
    # PyInstaller. Vegeu `app/plataforma.py`.
    run([plataforma.python_actual(), ACORDS_PY, csv_path, str(bpm), str(bpb),
         str(offset)], log, cwd=workdir)
    # el py escriu al directori de treball
    return (os.path.join(workdir, "acords_locators.txt"),
            os.path.join(workdir, "guia_acords.html"))


def pos_compas(t, bpm, bpb=4, lliure=False, offset=0.0):
    """Posició en format compàs.temps.subdivisió (qualsevol compàs).

    Graella = corxera (mig temps). `bpb` = temps per compàs, així funciona
    amb 3/4, 6/8, 5/4... (abans estava fixat a 8 corxeres = només 4/4).
    """
    if lliure:
        return f"{float(t):07.2f}s"
    step = 60.0 / bpm / 2              # corxera
    SB = max(1, int(bpb)) * 2          # corxeres per compàs
    # Sense clampar: abans de l'offset (compàs 1) les posicions son negatives
    # -> el silenci inicial queda com un compte enrere (compàs -1, -2...).
    p = round((float(t) - float(offset)) / step)
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


def desa_abc_csv(ruta, seccions, bpm, log, lliure=False, bpb=4, offset=0.0):
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
                        pos_compas(ini, bpm, bpb, lliure, offset),
                        pos_compas(fi, bpm, bpb, lliure, offset)])
    seq = seq_abc(seccions)
    log(f"ABC: {len(seccions)} trossos, seqüència {seq}")
    return seccions


def regenera_wavs_estructura(abc_csv, sortida, sr, log):
    dest = os.path.join(sortida, "wavs_estructura")
    neteja_wavs(dest)
    return fer_wavs_estructura(abc_csv, dest, sr, log)


def fer_abc(seg_csv, abc_csv, bpm, log, lliure=False, bpb=4, offset=0.0,
            durada_min=0.0, fusiona_iguals=True):
    import re

    def familia(lab):
        # El motor d'estructura (qm-segmenter) etiqueta N1,N4,N6... (família N) i B,A,C...
        # Traiem dígits finals i normalitzem: N1->N, n1->N, B->B.
        fam = re.sub(r"\d+$", "", lab.strip()).upper() or lab.strip()
        return fam

    # 1. Llegeix + fusiona adjacents de la mateixa família (C-C -> un sol tros).
    trossos = []  # (ini, fi, família, etiqueta_original)
    with open(seg_csv, encoding="utf-8") as f:
        for ini, dur, _idx, lab in csv.reader(f):
            ini, dur = float(ini), float(dur)
            fam = familia(lab)
            if fusiona_iguals and trossos and trossos[-1][2] == fam:
                trossos[-1][1] = ini + dur
                trossos[-1][3] += "+" + lab
            else:
                trossos.append([ini, ini + dur, fam, lab])
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
        fer_abc(csv_seg, abc, bpm, log, lliure=not tempo_fix, bpb=bpb,
                offset=offset)
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
