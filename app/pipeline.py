#!/usr/bin/env python3
# pipeline.py — motor de l'Auto Chords (stdlib + binaris del projecte).
# Cadena: wav -> csv acords (annotator+Chordino) -> locators/guia ->
#         wavs_acords (+ qm-segmenter -> ABC -> wavs_estructura, opcional).
# Tot en català.
import csv
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import wave
from collections import namedtuple

from app import plataforma, tempo, xifrat

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJ_DIR = os.path.dirname(APP_DIR)
SONIC = os.path.join(PROJ_DIR, "OLD", "sonic-annotator")   # arxivat (reserva)
ACORDS_PY = os.path.join(PROJ_DIR, "acords_a_live.py")
# Directoris dels plugins Vamp SEGONS EL SO (vegeu `app/plataforma.py`):
#   Linux   -> nnls-chroma-linux64-local + qm-vamp-plugins-linux64-local
#   Windows -> nnls-chroma-win64-local   + qm-vamp-plugins-win64-local
#   macOS   -> nnls-chroma-macos-local   + qm-vamp-plugins-macos-local
VAMP_DIRS = plataforma.dirs_plugins(PROJ_DIR)


# Noms reservats de Windows: no poden ser el nom (ni l'arrel) d'un fitxer.
_RESERVATS_WINDOWS = frozenset(
    ["CON", "PRN", "AUX", "NUL"]
    + [f"COM{i}" for i in range(0, 10)]
    + [f"LPT{i}" for i in range(0, 10)])


def _desambigua(nom, usats):
    """Torna `nom` únic dins `usats` (hi afegeix `_2`, `_3`… NOMÉS si cal).

    Els noms que no xoquen es queden exactament igual.
    """
    if nom not in usats:
        usats.add(nom)
        return nom
    i = 2
    while True:
        sufix = f"_{i}"
        unic = nom[:64 - len(sufix)] + sufix
        if unic not in usats:
            break
        i += 1
    usats.add(unic)
    return unic


def safe_filename(name, fallback="X", usats=None):
    """Retorna un nom segur per usar com a part d un filename.

    - Substitueix separadors de path (/ i os.sep) per _ (MAI per -, que al
      xifrat vol dir «menor»: `A7/G` → `A7_G`)
    - Treu caracters de control (\0, \n, \r, \t)
    - Substitueix els caracters reservats a Windows (: * ? " < > |) per -
    - Treu punt o espai FINAL (Windows no els accepta)
    - Evita els noms reservats de Windows (CON, PRN, AUX, NUL, COM0-9, LPT0-9)
    - Retorna fallback si el resultat es buit
    - Trunca a 64 caracters per evitar toxicitat
    - Si es passa `usats` (un set), desambigua amb un sufix (_2, _3...) quan el
      nom ja hi es; els noms unics NO canvien mai

    Els noms habituals d'acord (C, C#m7, N, Am/G→Am_G...) NO canvien.
    """
    s = str(name).strip()
    # El separador de l'acord amb baix (`/`) i el de path passen a `_`: NO a
    # `-`, perquè al xifrat el `-` vol dir «menor» (`A-7` ≠ `A7/G`).
    s = s.replace(os.sep, "_").replace("/", "_").replace("\\", "_")
    s = s.replace("\0", "").replace("\n", "").replace("\r", "").replace("\t", "")
    # Caracters reservats a Windows. Els evitem SEMPRE (tambe a Linux/macOS)
    # perque el mateix projecte doni els MATEIXOS noms a tots els sistemes.
    for c in ': * ? " < > |':
        s = s.replace(c, "-")
    s = s.strip()
    s = s.rstrip(". ")          # Windows: ni punt ni espai al final
    if not s:
        s = fallback
    s = s[:64].rstrip(". ")     # truncar pot deixar un punt/espai final
    if not s:
        s = fallback
    if s.upper() in _RESERVATS_WINDOWS:
        s = s + "_"
    if usats is not None:
        s = _desambigua(s, usats)
    return s


def saneja_nom_acord(nom):
    """Nom d'acord net per al MODEL i el CSV, en la **notació canònica** de l'app.

    Delega a `app.xifrat`: entén les variants que escrigui l'usuari (menor
    `m`/`mi`/`min`/`-`, major `M`/`Ma`/`maj`/`Δ`, `°`/`o`/`dim`, `+`, `ø`…) i
    deixa el xifrat en la forma canònica (`Am` → `A-`, `Cmaj7` → `CMaj7`,
    `Bø` → `B-7b5`). El baix amb `/` es conserva (`A7/G` → `A7/G`).

    La seguretat per als noms de FITXER la garanteix `safe_filename`, que
    l'export aplica pel seu compte. Retorna "" si el nom queda buit — qui cridi
    decideix què fer.
    """
    return xifrat.normalitza_xifrat(nom)


# Prefix de les carpetes que genera l'app al costat del WAV. És PREFIX (no
# sufix) perquè totes les carpetes de l'app quedin juntes i al davant quan
# s'ordena el directori on hi ha la cançó.
PREFIX_SORTIDA = "AUTOCHORDS_"


def carpeta_sortida(wav):
    """Carpeta de resultats que l'app crea al costat de `wav`.

    Nom: `AUTOCHORDS_<nom-de-la-wav>` (p. ex. `Tema.wav` → `AUTOCHORDS_Tema`).
    Font única del nom: la fan servir main.py, visor.py i wav_a_wavs.py.
    """
    base = os.path.splitext(os.path.basename(wav))[0]
    return os.path.join(os.path.dirname(wav), PREFIX_SORTIDA + base)


# Subcarpeta de la SORTIDA on es desa l'ANÀLISI CRUA (evidència, només lectura):
# NO la toquen l'edició, ni el mode fàcil, ni els canvis de compàs/BPM/mode.
# És el «primer autoanàlisi» que es pot reintrepretar amb la graella.
NOM_ANALISI = "analisi"
NOM_CRU_ACORDS = "chords_raw.csv"
NOM_CRU_SEGMENTS = "segments_raw.csv"
NOM_ANALISI_META = "meta.json"


def carpeta_analisi(sortida):
    """Carpeta de l'anàlisi crua (`analisi/`) dins la sortida del tema."""
    return os.path.join(sortida, NOM_ANALISI)


# Prefixos dels directoris temporals que crea l'app (per netejar-los sempre).
PREFIXOS_TMP = ("ac_ttl_", "ac_qm_", "ac_key_")


def esborra_tmp(dirs):
    """Esborra directoris temporals creats per l'app (mai llança).

    Només esborra els que comencen per un dels prefixos propis: així, passi el
    que passi, no es pot esborrar una ruta arbitrària. Aplica reintents breus
    per resistir bloquejos temporals de fitxers a Windows.
    """
    for d in dirs or ():
        try:
            p = str(d).rstrip("/\\")
            if os.path.basename(p).startswith(PREFIXOS_TMP):
                for intent in range(5):
                    try:
                        shutil.rmtree(p, ignore_errors=False)
                        break
                    except OSError:
                        if intent == 4:
                            shutil.rmtree(p, ignore_errors=True)
                        else:
                            time.sleep(0.05 * (intent + 1))
        except OSError:
            pass


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


def _cmd_transform(transform, out_csv, wav, params=None, tmp=None):
    """Comanda per executar un transform: el nostre host, o sonic-annotator.

    Si cal un `.ttl` temporal, el seu directori s'apunta a `tmp` (una llista)
    perquè qui crida el pugui esborrar quan la comanda ja s'hagi executat.
    """
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
        d = tempfile.mkdtemp(prefix="ac_ttl_")
        if tmp is not None:
            tmp.append(d)      # el ttl ha de viure fins que corri la comanda
        ttl = os.path.join(d, "t.ttl")
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

    Els `.ttl` temporals s'esborren SEMPRE en sortir (també si peta).
    """
    tmp = []
    try:
        cmd = _cmd_transform(transform, out_csv, wav, params, tmp)
        try:
            return run(cmd, log)
        except RuntimeError:
            if "--step" not in cmd:
                raise
            cmd2 = _cmd_transform(transform, out_csv, wav, params, tmp)
            i = cmd2.index("--step")
            del cmd2[i:i + 4]                 # treu --step N --block M
            if log:
                log("  (step/block de la taula refusats; uso els del plugin)")
            return run(cmd2, log)
    finally:
        esborra_tmp(tmp)


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
        d = tempfile.mkdtemp(prefix="ac_ttl_")
        try:
            ttl = os.path.join(d, "chords.ttl")
            escriu_ttl("chords", params, ttl, log)
            run([SONIC, "-t", ttl, "-w", "csv", "--csv-one-file", out_csv,
                 "--csv-force", "--csv-omit-filename", wav_path], log)
        finally:
            esborra_tmp([d])
    else:
        run([SONIC, "-d", TRANSFORMS["chords"],
             "-w", "csv", "--csv-one-file", out_csv, "--csv-force",
             "--csv-omit-filename", wav_path], log)


MOTORS_BPM = ("nostre", "qm", "consens")
MOTORS_ESTRUCTURA = ("qm",)


def _qm_valors(transform, wav_path, col=1, timeout=1800):
    """Valors numerics d'una columna d'un transform del qm."""
    d = tempfile.mkdtemp(prefix="ac_qm_")
    try:
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
    finally:
        esborra_tmp([d])


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
    d = tempfile.mkdtemp(prefix="ac_qm_")
    try:
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
    finally:
        esborra_tmp([d])


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
        d = tempfile.mkdtemp(prefix="ac_ttl_")
        try:
            ttl = os.path.join(d, "seg.ttl")
            escriu_ttl("structure", params, ttl, log)
            run([SONIC, "-t", ttl, "-w", "csv", "--csv-one-file", out_csv,
                 "--csv-force", "--csv-omit-filename", wav_path], log)
        finally:
            esborra_tmp([d])
    else:
        run([SONIC, "-d", TRANSFORMS["structure"],
             "-w", "csv", "--csv-one-file", out_csv, "--csv-force",
             "--csv-omit-filename", wav_path], log)


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


# Tolerància compartida per als temps (evita falsos positius per coma flotant).
# La fan servir la normalització de cobertura i els validadors del visor.
TOL_TEMPS = 1e-6


# --- Model unificat de CLIPS (refactor «inici+fi») -------------------------
# Un SOL tipus per a acords i estructura: `Clip(ini, fi, payload)`, on el
# `payload` és tot el que no és temps:
#   · acords:     `(nom, tsrc)` — p. ex. `("Am", "16.153846154")`;
#   · estructura: `(lletra, família)` — p. ex. `("A", "A")`.
# La font única de veritat és la CADENA DE FRONTERES: el `fi` se'n deriva i, per
# tant, no pot quedar mai incoherent. Contracte i pla: docs/REFACTOR_INICI_FI.md.
Clip = namedtuple("Clip", ("ini", "fi", "payload"))


def clips_d_acords(acords, durada):
    """Acords (marques `(t, nom, tsrc)`) → `Clip` amb el `fi` derivat.

    El `fi` d'un acord és l'`ini` del següent; el de l'últim, la `durada`.
    """
    durada = float(durada or 0.0)
    out = []
    for i, a in enumerate(acords or ()):
        fi = float(acords[i + 1][0]) if i + 1 < len(acords) else durada
        out.append(Clip(float(a[0]), fi, tuple(a[1:])))
    return out


def acords_de_clips(clips):
    """`Clip` → acords (marques `(t, nom, tsrc)`): només la frontera d'inici."""
    return [(float(c.ini),) + tuple(c.payload) for c in clips]


def nom_d_acord(it):
    """Nom d'un clip d'acord (`Clip(ini, fi, payload)`) o d'una marca `(t, nom[, tsrc])`.

    Pont mentre el model viu passa de **marques** a **clips** (S4): permet
    accedir al nom sense dependre de la forma de l'element.
    """
    if isinstance(it, Clip):
        p = it.payload
        return p[0] if isinstance(p, tuple) else p
    return it[1]


def clips_de_model(items, durada=0.0):
    """Normalitza una llista d'acords (clips `Clip` o marques `(t, nom[, tsrc])`) a clips.

    Pont (S4): el model viu ja són clips; les **marques** encara hi arriben des
    del camí de l'anàlisi o de crides directes. El `fi` d'una marca es deriva
    (inici del següent; l'últim, `durada`). No muta l'entrada.
    """
    items = list(items or [])
    durada = float(durada or 0.0)
    out = []
    for i, a in enumerate(items):
        if isinstance(a, Clip):
            out.append(a)
        else:
            fi = (float(items[i + 1][0]) if i + 1 < len(items) else durada)
            out.append(Clip(float(a[0]), fi, tuple(a[1:])))
    return out


def clips_de_seccions(seccions):
    """Seccions `(ini, fi, lletra, família)` → `Clip` (el `fi` ja hi és)."""
    return [Clip(float(s[0]), float(s[1]), tuple(s[2:])) for s in (seccions or ())]


def seccions_de_clips(clips):
    """`Clip` → seccions `(ini, fi, lletra, família)`."""
    return [(float(c.ini), float(c.fi)) + tuple(c.payload) for c in clips]


def normalitza_clips(clips, durada, forat, arrodoneix=False, deriva_fi=False,
                     log=None):
    """XARXA DE SEGURETAT única dels invariants #1, #2 i #4 (model de clips).

    - **#1 ordre estricte**: clips ordenats per `ini` (`sort` estable).
    - **#2 contigüitat**: la frontera entre dos clips és una de sola → si dos
      clips es trepitgen, el primer s'acota a l'`ini` del segon; si hi ha un
      forat, es tapa amb un clip de payload `forat`.
    - **#4 cobertura**: si el primer no arrenca a 0 s'hi posa una capçalera
      `forat`, i el `fi` de l'últim s'acota a `durada`.

    Paràmetres de variant (les dues cares del model actual):
    - `forat`: payload del clip de farciment — `(SENSE_ACORD, "0.000000000")`
      per als acords i `(SENSE_SECCIO, SENSE_SECCIO)` per a l'estructura.
    - `arrodoneix`: aplica la resolució del CSV (`TEMPS_DEC`, 10 ms) als descarts
      i als xocs d'inici (es conserva el primer).
    - `deriva_fi`: el `fi` es **deriva** de la cadena (semàntica de marques). Si
      és fals es respecta el `fi` d'entrada (semàntica d'intervals: els forats
      són reals i es tapen amb `forat`).

    Retorna una llista NOVA de `Clip`; no muta l'entrada.
    """
    durada = float(durada or 0.0)
    net, vists = [], set()
    for c in clips or ():
        ini, fi = float(c.ini), float(c.fi)
        if durada > 0:
            ref = round(ini, TEMPS_DEC) if arrodoneix else ini
            if ref >= durada - TOL_TEMPS:
                continue                  # arrenca (o arrodonit) fora: no hi és
            fi = min(fi, durada)          # cap clip no surt de la WAV
        if arrodoneix:
            clau = round(ini, TEMPS_DEC)
            if clau in vists:
                if log:
                    log(f"cobertura: clip a {ini:.3f} s eliminat (xoca al CSV "
                        f"amb un altre a {clau:.2f} s)")
                continue
            vists.add(clau)
        net.append(Clip(ini, fi, tuple(c.payload)))
    net.sort(key=lambda c: c.ini)
    if deriva_fi:
        net = [Clip(c.ini, net[i + 1].ini if i + 1 < len(net) else durada,
                    c.payload) for i, c in enumerate(net)]
    out = []
    for c in net:
        if out:
            prev = out[-1]
            if c.ini < prev.fi - TOL_TEMPS:
                out[-1] = Clip(prev.ini, c.ini, prev.payload)    # es trepitgen
            elif c.ini > prev.fi + TOL_TEMPS:
                out.append(Clip(prev.fi, c.ini, tuple(forat)))   # forat
                if log:
                    log(f"cobertura: forat {prev.fi:.2f}–{c.ini:.2f} s tapat "
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
    """Garanteix l'**INVARIANT de COBERTURA** (regla d'or de l'app):

        suma(clips d'acords)     == durada de la WAV
        suma(clips d'estructura) == durada de la WAV

    És a dir, els clips cobreixen **tota** la WAV (0 → durada), en qualsevol
    mode (Lliure o BPM·compàs) i amb o sense snap.

    - **Acords** `[(t, nom, tsrc), …]`: si el primer comença > 0 s'hi insereix
      una **«N» a 0** (capçalera). (La durada de l'últim acord és implícita: el
      timeline/export la fixen a `durada`.)
    - **Seccions** `[(ini, fi, lletra, família), …]`: si la primera comença > 0
      s'hi insereix una **«N» a 0**; i el `fi` de l'última **s'acota a `durada`**.
    - **Forats interns de les seccions**: si una secció no arrenca on acaba
      l'anterior (`prev.fi != curr.ini`, regla d'or #2) el forat es **tapa amb
      una secció «N»** (una regió sense etiqueta, com la capçalera) → la suma
      de durades torna a ser exactament la de la WAV.

    Retorna `(acords, seccions)` normalitzats (llistes noves; no muta les d'entrada).
    """
    durada = float(durada or 0.0)
    acords = [tuple(a) for a in (acords or [])]
    seccions = [tuple(s) for s in (seccions or [])]
    # Regla d'or #1 (ordre estricte): aquesta funció és la XARXA DE SEGURETAT
    # dels 4 camins (edició en viu, visor, CSV i export), així que reordenem
    # aquí. El visor ja ho valida, però un CSV editat a mà no hi passa. El
    # `sort` és ESTABLE: davant d'instants repetits, es conserva el primer.
    acords.sort(key=lambda a: float(a[0]))
    seccions.sort(key=lambda s: float(s[0]))
    # Acords: la veritat és el que quedarà AL CSV (arrodonit a `TEMPS_DEC`).
    #   (a) els que cauen FORA de la WAV (arrodonits) no tenen àudio → fora;
    #   (b) dos acords que arrodoneixin al MATEIX instant deixarien un clip de
    #       durada 0 a l'export (xocs d'inici dins la resolució del CSV) → es
    #       conserva el primer.
    if durada > 0:
        net, vists, fora, xocs = [], set(), 0, 0
        for a in acords:
            t_arrod = round(float(a[0]), TEMPS_DEC)
            if t_arrod >= durada - TOL_TEMPS:
                fora += 1
                continue
            if t_arrod in vists:
                xocs += 1
                if log:
                    log(f"cobertura: acord {a[1]} a {float(a[0]):.3f} s eliminat "
                        f"(xoca amb un altre a {t_arrod:.2f} s al CSV)")
                continue
            vists.add(t_arrod)
            net.append(a)
        if fora and log:
            log(f"cobertura: {fora} acord(s) fora de la WAV "
                f"(arrodonits >= {durada:.2f} s) eliminats")
        if fora or xocs:
            acords = net
    # Acords: capçalera N si el 1r no arrenca a 0.
    if acords and float(acords[0][0]) > 1e-9:
        # conserva els camps extra (p. ex. `tsrc`), posant-los a 0.
        extra = tuple("0.000000000" for _ in acords[0][2:])
        acords.insert(0, (0.0, "N") + extra)
        if log:
            log(f"cobertura: capçalera N als acords (1r acord a "
                f"{float(acords[1][0]):.2f} s)")
    # Seccions: capçalera N + forats interns + dins de la durada.
    if seccions and durada > 0:
        # (a) Una secció no pot SORTIR de la WAV: si arrenca més enllà, no hi
        #     és (fora); si el seu fi passa de la durada, s'hi acota.
        dins = [(s[0], min(float(s[1]), durada), s[2], s[3]) for s in seccions
                if float(s[0]) < durada - TOL_TEMPS]
        if len(dins) != len(seccions):
            if log:
                log(f"cobertura: {len(seccions) - len(dins)} secció(ns) que "
                    f"arrencaven fora de la WAV (>= {durada:.2f} s) eliminades")
        seccions = dins
    if seccions:
        if float(seccions[0][0]) > 1e-9:
            seccions.insert(0, (0.0, float(seccions[0][0]),
                                SENSE_SECCIO, SENSE_SECCIO))
            if log:
                log(f"cobertura: capçalera «{SENSE_SECCIO}» a l'estructura "
                    f"(1a secció a {float(seccions[1][0]):.2f} s)")
        # Forats INTERNS (regla d'or #2: el fi d'una secció == inici de la
        # següent): es tapen amb una secció «-» (§6.1: sense secció). Sense
        # això, moure una secció cap endavant deixava un forat que l'app
        # acceptava i la suma de durades ja no quadrava amb la WAV (#4).
        farcit = []
        for s in seccions:
            if farcit and float(s[0]) > float(farcit[-1][1]) + 1e-9:
                forat = (float(farcit[-1][1]), float(s[0]),
                         SENSE_SECCIO, SENSE_SECCIO)
                farcit.append(forat)
                if log:
                    log(f"cobertura: forat intern {forat[0]:.2f}–{forat[1]:.2f} s "
                        f"tapat amb «{SENSE_SECCIO}»")
            farcit.append(s)
        seccions = farcit
        if durada > 0 and float(seccions[-1][1]) < durada - 1e-9:
            ini, _fi, L, fam = seccions[-1]
            seccions[-1] = (ini, durada, L, fam)
            if log:
                log(f"cobertura: última secció acotada a la durada "
                    f"({durada:.2f} s)")
    return acords, seccions


def run_acords_py(csv_path, bpm, bpb, offset, workdir, log, durada=None):
    # `sys.executable` (mai un `python3` fix): trencava a Windows i amb
    # PyInstaller. Vegeu `app/plataforma.py`.
    args = [plataforma.python_actual(), ACORDS_PY, csv_path, str(bpm),
            str(bpb), str(offset)]
    if durada:
        # INVARIANT de COBERTURA: l'últim acord ha d'arribar a la durada.
        args.append(str(float(durada)))
    run(args, log, cwd=workdir)
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


def parteix_clips(clips, i, talla, nou_payload=None, marge=0.05,
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


def parteix_acord(acords, i, talla, nom=None, marge=0.05):
    """Parteix l'acord `i` (wrapper del nucli unificat `parteix_clips`; #11)."""
    if i < 0 or i >= len(acords):
        raise ValueError("índex d'acord inexistent")
    if i + 1 >= len(acords):
        raise ValueError("no es pot partir l'últim acord (durada fins al final)")
    nom = (saneja_nom_acord(nom) if nom else "") or acords[i][1]
    payload = (nom, f"{float(talla):.9f}")
    cl = parteix_clips(clips_d_acords(acords, 0.0), i, talla,
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


SENSE_SECCIO = "-"      # §6.1: forat explícit d'estructura («sense secció»)
SENSE_ACORD = "N"       # §6.1: forat explícit d'acords («sense acord»)


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
                or (t < c.fi and t - c.ini < 0.02 - TOL_TEMPS)):
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
    if c.fi - t < 0.02 - TOL_TEMPS:
        return out                          # no canvia res (queda massa curt)
    if idx > 0:                             # l'anterior s'estira endavant
        p = out[idx - 1]
        out[idx - 1] = Clip(p.ini, t, p.payload)
    out[idx] = Clip(t, c.fi, c.payload)
    return normalitza_clips(out, durada, forat)


def redimensiona_seccio(seccions, idx, vora, t, durada, log=None):
    """Vora d'una SECCIÓ: mateixa regla i mateix nucli que els acords (#11)."""
    return seccions_de_clips(redimensiona_clips(
        clips_de_seccions(seccions), idx, vora, t, durada, FORAT_SECCIO, log))


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


def parteix_seccio(seccions, i, talla, marge=0.05):
    """Parteix la secció `i` (mateix nucli que els acords, #11)."""
    return seccions_de_clips(parteix_clips(
        clips_de_seccions(seccions), i, talla, marge=marge, etiqueta="secció"))


def fusiona_seccions(seccions, i, amb="seguent"):
    """Fusiona la secció `i` amb el veí (mateix nucli que els acords, #11)."""
    return seccions_de_clips(fusiona_clips(
        clips_de_seccions(seccions), i, amb, etiqueta="secció"))


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


def elimina_seccio(seccions, idx, durada):
    """Esborra la secció `idx` (mateix nucli que els acords; #11)."""
    return seccions_de_clips(elimina_clips(
        clips_de_seccions(seccions), idx, durada, FORAT_SECCIO))


def duplica_clips(clips, idx, marge=0.05):
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


def duplica_acord(acords, idx, durada, marge=0.02):
    """Duplica l'acord `idx` (wrapper de `duplica_clips`; #11).

    El 2n tros (el nou) pren el seu inici com a `tsrc` (temps font), com fan la
    resta de marques noves; l'original conserva el seu.
    """
    clips = clips_d_acords(acords, durada)
    nou = duplica_clips(clips, idx, marge)
    if len(nou) == len(clips) + 1:
        s = nou[idx + 1]
        p = tuple(s.payload)
        nou = list(nou)
        nou[idx + 1] = Clip(s.ini, s.fi, (p[0], f"{s.ini:.9f}") + p[2:])
    return acords_de_clips(nou)


def duplica_seccio(seccions, idx, marge=0.05):
    """Duplica la secció `idx` (mateix nucli que els acords; #11)."""
    return seccions_de_clips(duplica_clips(
        clips_de_seccions(seccions), idx, marge))


def desa_abc_csv(ruta, seccions, bpm, log, lliure=False, bpb=4, offset=0.0):
    def _escriu(f):
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
    escriu_atomic(ruta, _escriu)
    seq = seq_abc(seccions)
    log(f"ABC: {len(seccions)} trossos, seqüència {seq}")
    return seccions


def regenera_wavs_estructura(abc_csv, sortida, sr, log):
    dest = os.path.join(sortida, "wavs_estructura")
    neteja_wavs(dest)
    return fer_wavs_estructura(abc_csv, dest, sr, log)


def fer_abc(seg_csv, abc_csv, bpm, log, lliure=False, bpb=4, offset=0.0,
            durada_min=0.0, fusiona_iguals=True, durada=None):
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
    # com acords_a_live.py però en segons, sense graella: N s'absorbeix,
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


def fer_wavs_acords_lliures(csv_path, total_s, dest_dir, sr, log):
    os.makedirs(dest_dir, exist_ok=True)
    n = 0
    usats = set()          # desambigua noms d'acord que quedin iguals
    for ini, fi, chord in segments_lliures(csv_path, total_s, log):
        frames = int(round((fi - ini) * sr))
        if frames <= 0:
            # Mai escriure un WAV de durada 0 (un xoc d'inicis a la resolució
            # del CSV, o un acord a tocar del final, el produiria).
            log(f"wavs_acords: segment {ini:.2f}–{fi:.2f}s ({chord}) de durada "
                f"0 → s'omet")
            continue
        fn = (f"{ini:07.2f}s_{fi:07.2f}s_"
              f"{safe_filename(chord, fallback='N', usats=usats)}.wav")
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
    usats = set()          # desambigua noms d'acord que quedin iguals
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
            fn = f"{pos_.replace('.', '-')}_{safe_filename(chord, fallback='N', usats=usats)}.wav"
            escriu(fn, float(dur))
            n += 1
    log(f"wavs_acords: {n}")
    return n


def exporta_total(csv_ac, csv_seg, sortida, bpm, bpb, offset, sr, log,
                 tempo_fix=True, amb_estructura=True, total_s=None,
                 acords=None, seccions=None):
    """Exporta el flux complet.

    Si es passen `acords`/`seccions` (el **model VIU** del visor), s'usen ELLS
    per sobre dels CSV del disc: es re-escriuen els CSV (acords + estructura)
    ja **normalitzats** amb l'invariant de COBERTURA, de manera que l'export
    **no perd les edicions manuals** (finals de secció, capçalera «N», etc.).
    Si no es passen, es comporta exactament com abans (llegeix els CSV).

    Retorna un diccionari amb les rutes finals (csv + carpetes).
    """
    sortida = os.path.abspath(sortida)
    os.makedirs(sortida, exist_ok=True)
    csv_ac = os.path.abspath(csv_ac)
    # (A)+(B) Si ens donen el MODEL, mana ell: normalitzem la cobertura i
    # re-escrivim el CSV d'acords ABANS de comprovar-lo/fer-lo servir.
    if acords is not None or seccions is not None:
        durada = float(total_s or 0.0)
        if acords is not None:
            clips = normalitza_clips(
                clips_de_model(acords, durada), durada, FORAT_ACORD,
                arrodoneix=True, deriva_fi=True, log=log)
            desa_acords_csv(csv_ac, clips, durada)
        if seccions is not None:
            _, seccions = normalitza_cobertura([], seccions, durada, log=log)
    if not os.path.isfile(csv_ac):
        raise FileNotFoundError(f"No trobo acords.csv: {csv_ac}")

    result = {"acords_csv": csv_ac, "sortida": sortida}
    if tempo_fix:
        loc, guia = run_acords_py(csv_ac, bpm, bpb, offset, sortida, log,
                                  durada=total_s)
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
                    if not row or row[0].startswith(("posici", "inici")):
                        continue
                    try:
                        total_s = max(total_s, float(row[0]))
                    except ValueError:
                        pass
        dest = os.path.join(sortida, "wavs_acords")
        neteja_wavs(dest)
        result["n_acords_wavs"] = fer_wavs_acords_lliures(
            csv_ac, total_s, dest, sr, log)

    if amb_estructura and (seccions is not None or csv_seg):
        abc = os.path.join(sortida, "estructura_ABC.csv")
        result["abc_csv"] = abc
        if seccions is not None:
            # (A) Seccions DEL MODEL (edició en viu): NO es reconstrueix l'ABC
            # des de `segments.csv` (que és el resultat CRU de l'anàlisi), sinó
            # del model editat → les edicions de seccions no es perden.
            desa_abc_csv(abc, seccions, bpm, log, lliure=not tempo_fix,
                         bpb=bpb, offset=offset)
            result["segments_csv"] = None
        else:
            csv_seg = os.path.abspath(csv_seg)
            if not os.path.isfile(csv_seg):
                raise FileNotFoundError(f"No trobo segments.csv: {csv_seg}")
            result["segments_csv"] = csv_seg
            fer_abc(csv_seg, abc, bpm, log, lliure=not tempo_fix, bpb=bpb,
                    offset=offset, durada=total_s)
        dest_abc = os.path.join(sortida, "wavs_estructura")
        neteja_wavs(dest_abc)
        result["n_estructura_wavs"] = fer_wavs_estructura(
            abc, dest_abc, sr, log)

    return result


# Resolució temporal unificada dels CSV: 10 ms (2 decimals) — opció (b).
# Abans: acords.csv guardava 9 decimals i estructura_ABC.csv 2 → incoherent.
TEMPS_DEC = 2
# Distància MÍNIMA entre dos temps del CSV perquè els seus arrodoniments siguin
# DIFERENTS. Amb menys, dues files cauen al mateix instant del CSV → un clip de
# durada 0 a l'export (i la suma de durades ja no quadra). Vegeu `visor` (els
# validadors el fan complir) i `normalitza_cobertura` (el repara en carregar).
RESOLUCIO_CSV = 10.0 ** -TEMPS_DEC


def escriu_atomic(ruta, escriu):
    """Escriu `ruta` de forma ATÒMICA: fitxer temporal + fsync + `os.replace`.

    Els CSV d'acords i d'estructura són la FEINA de l'usuari i es reescriuen a
    cada edició. Amb `open(ruta, "w")` el fitxer es trunca ABANS d'escriure: un
    crash, un kill o un tall de corrent enmig deixava un CSV buit o a mitges i
    es perdia tot. Aquí o queda la versió anterior sencera o la nova sencera.

    `escriu(f)` rep el fitxer de text obert (utf-8, `newline=""`). A Windows,
    `os.replace` pot fallar un instant si un antivirus o l'Explorer tenen el
    destí obert: es reintenta unes quantes vegades abans de donar l'error.
    """
    ruta = os.path.abspath(ruta)
    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
    tmp = f"{ruta}.{os.getpid()}.{threading.get_ident()}.tmp"
    try:
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            escriu(f)
            f.flush()
            os.fsync(f.fileno())
        for intent in range(6):
            try:
                os.replace(tmp, ruta)
                return
            except PermissionError:
                if intent == 5:
                    raise
                time.sleep(0.05 * (intent + 1))
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def regularitza_acords_csv(csv_cru, csv_desti, bpm, bpb, offset, ritme, durada,
                           log=None):
    """Mode fàcil: del cru al MODEL regularitzat a la graella.

    `ritme`: "auto" | "compas" | "mig" | "temps". Converteix la decisió musical
    (cada quants **temps** canvia l'acord) en segons amb el BPM. Aplica la
    cobertura (#4). **No toca `csv_cru`.** Retorna la llista d'acords o `None`.
    """
    from app import graella                    # import local: evita cicles
    items = []
    try:
        with open(csv_cru, encoding="utf-8") as f:
            for fila in csv.reader(f):
                if not fila or fila[0].startswith("posici"):
                    continue
                try:
                    items.append((float(fila[0]), fila[1].strip()))
                except (ValueError, IndexError):
                    continue
    except OSError:
        return None
    if not items:
        return None
    if ritme in (None, "auto"):
        ritme = graella.infereix_nivell(items, bpm, bpb, offset, durada, log=log)
    res = graella.regularitza_acords(items, bpm, bpb, offset,
                                     ritme or "compas", durada, log=log)
    acords, _ = normalitza_cobertura(res, [], durada, log=log)
    desa_acords_csv(csv_desti, [(float(t), str(n)) for (t, n) in acords], durada)
    return acords


def desa_acords_csv(ruta, items, durada=0.0):
    """Desa el model d'acords com a CLIPS: `inici,fi,acord` (S3+S4).

    Accepta **clips** `(ini, fi, payload)` (el model del visor) o **marques**
    `(t, nom[, tsrc])` (el camí de l'anàlisi); en tots dos casos n'escriu el nom.
    El `fi` d'una marca es deriva (inici del següent; l'últim, la `durada`). Els
    temps van arrodonits a `TEMPS_DEC` (10 ms), com `estructura_ABC.csv`.
    """
    items = [tuple(it) for it in items]
    durada = float(durada or 0.0)

    def _nom(payload):
        return payload[0] if isinstance(payload, tuple) else payload

    def _escriu(f):
        w = csv.writer(f)
        for i, it in enumerate(items):
            t = float(it[0])
            if isinstance(it[1], (int, float)):     # CLIP (ini, fi, payload)
                fi, c = float(it[1]), _nom(it[2])
            else:                                    # MARCA (t, nom[, tsrc])
                c = _nom(it[1])
                fi = float(items[i + 1][0]) if i + 1 < len(items) else durada
            w.writerow([f"{t:.{TEMPS_DEC}f}", f"{fi:.{TEMPS_DEC}f}", c])
    escriu_atomic(ruta, _escriu)


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
    usats = set()          # desambigua etiquetes de secció que quedin iguals
    with open(abc_csv, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            nm = (f"{r['compas_ini'].replace('.', '-')}_"
                  f"{r['compas_fi'].replace('.', '-')}_"
                  f"{safe_filename(r['lletra'], fallback='X', usats=usats)}")
            frames = int(round(float(r["durada_s"]) * sr))
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
            n += 1
    log(f"wavs_estructura: {n}")
    return n
