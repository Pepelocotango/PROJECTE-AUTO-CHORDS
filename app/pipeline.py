#!/usr/bin/env python3
# pipeline.py — motor de l'Auto Chords (stdlib + binaris del projecte).
# Cadena: wav -> csv acords (annotator+Chordino) -> guia ->
#         wavs_acords (+ qm-segmenter -> ABC -> wavs_estructura, opcional).
# Tot en català.
import csv
import os
import shutil

from . import tempo_map
import subprocess
import tempfile
import threading
import time
import wave
from collections import namedtuple

from app import plataforma, tempo, xifrat

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJ_DIR = os.path.dirname(APP_DIR)
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
# L'ÚNIC motor d'anàlisi: no arrossega Qt6/ICU/glib, només libc/libstdc++/
# sndfile. Vegeu eines/vamp_host.cpp.
HOST = os.path.join(PROJ_DIR, plataforma.NOM_HOST)   # .exe a Windows

# mida de finestra (step, block) per transform (els valors «de fàbrica» dels
# plugins a 44.1 kHz; s'escalen al mostreig real).
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
}


def _cmd_host(transform, out_csv, wav, params=None):
    """Comanda per executar un transform amb el nostre host Vamp."""
    cmd = [HOST, "--plugin", transform.replace("vamp:", ""), "--csv", out_csv]
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


def executa_transform(transform, out_csv, wav, log, params=None):
    """Executa un transform Vamp (host propi) i desa el CSV.

    Primer amb el step/block de la taula; si el plugin els refusa (depenen del
    mostreig), reintenta amb els seus valors preferits (sempre funcionen).
    """
    cmd = _cmd_host(transform, out_csv, wav, params)
    try:
        return run(cmd, log)
    except RuntimeError:
        if "--step" not in cmd:
            raise
        cmd2 = _cmd_host(transform, out_csv, wav, params)
        i = cmd2.index("--step")
        del cmd2[i:i + 4]                     # treu --step N --block M
        if log:
            log("  (step/block de la taula refusats; uso els del plugin)")
        return run(cmd2, log)


CHORDS_TRANSFORM = "vamp:nnls-chroma:chordino:simplechord"


def extract_chords(wav_path, out_csv, log, params=None):
    """Acords via Chordino (host propi; `params` son els parametres .n3)."""
    return executa_transform(CHORDS_TRANSFORM, out_csv, wav_path, log, params)


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
    "segments": "vamp:qm-vamp-plugins:qm-segmenter:segmentation",
}


def detecta_beats(wav_path, log=None):
    """Temps dels TEMPS (beats) detectats pel qm-barbeattracker (segons).

    El fa servir la inferència del mapa de tempo.
    """
    return _qm_temps(QM["beats"], wav_path, log=log)


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
# Separació mínima PRÀCTICA per a l'edició manual: 1 ms. La resolució de
# guardat és 1 µs, però dos canvis d'acord a menys d'1 ms no tenen sentit
# musical i fan clips inútils. No s'ha de confondre amb `RESOLUCIO_CSV`.
MIN_GAP_TEMPS = 0.001


# --- Model unificat de CLIPS (refactor «inici+fi») -------------------------
# Un SOL tipus per a acords i estructura: `Clip(ini, fi, payload)`, on el
# `payload` és tot el que no és temps:
#   · acords:     `(nom, tsrc)` — p. ex. `("Am", "16.153846154")`;
#   · estructura: `(lletra, família)` — p. ex. `("A", "A")`.
# La font única de veritat és la CADENA DE FRONTERES: el `fi` se'n deriva i, per
# tant, no pot quedar mai incoherent. Contracte i pla: docs/archive/REFACTOR_INICI_FI.md.
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


def _mapa_tempo_carpeta(carpeta, offset=0.0):
    """Llegeix `tempo.csv` i `compas.csv` de `carpeta` (o `mapa_tempo/`) i
    retorna un `TempoMap` si té més d'un tram i no és constant, o `None`.
    """
    try:
        from app.tempo_map import TempoMap

        def _llegeix(base_dir, nom, ncol):
            r = os.path.join(base_dir, nom)
            out = []
            if os.path.isfile(r):
                with open(r, encoding="utf-8") as f:
                    for fila in csv.reader(f):
                        if len(fila) >= ncol and not fila[0].startswith(("inici", "ini")):
                            try:
                                out.append([float(x) for x in fila[:ncol]])
                            except ValueError:
                                pass
            return out

        for d in (carpeta, os.path.join(carpeta, "mapa_tempo")):
            _tempo = _llegeix(d, "tempo.csv", 3)
            _compas = _llegeix(d, "compas.csv", 4)
            if len(_tempo) > 1 and len(_tempo) == len(_compas):
                _trams = [(t[0], t[1], t[2], int(c[2]), int(c[3]))
                          for t, c in zip(_tempo, _compas)]
                tm = TempoMap(_trams, offset=offset)
                if not tm.es_constant():
                    return tm
    except Exception:
        pass
    return None


def _segments_guia_daw(csv_path, bpm, bpb, offset=0.0, durada=0.0, mapa=None):
    """Calcula els segments quantitzats a **1/32** per als locators i la guia HTML.

    Retorna `(segs, end, step, slots_bar, mapa, pos_de_p)`, on cada segment és
    `(t_exacte, p, acord)` i `p` és l'índex de **fusa** des de l'origen.
    """
    bpm = float(bpm)
    bpb = int(bpb)
    offset = float(offset or 0.0)
    durada = float(durada or 0.0)
    step = 60.0 / bpm / 8.0                  # fusa (1/32)
    slots_bar = bpb * 8                      # fuses per compàs

    if mapa is None:
        mapa = _mapa_tempo_carpeta(os.path.dirname(os.path.abspath(csv_path)),
                                   offset=offset)
    elif hasattr(mapa, "es_constant") and mapa.es_constant():
        mapa = None

    with open(csv_path, encoding="utf-8") as f:
        rows = [(float(r[0]), r[2].strip())
                for r in csv.reader(f)
                if len(r) >= 3 and not r[0].startswith("inici")]

    def _q(t):
        if mapa is not None:
            return mapa.quarters(t)
        return (float(t) - offset) / (60.0 / bpm)

    def _t_de_p(p):
        if mapa is not None:
            return mapa.t_de_quarters(p / 8.0)
        return offset + p * step

    def _pos_de_p(p):
        if mapa is not None:
            return mapa.label(_t_de_p(p))
        return "%d.%d.%d" % (p // slots_bar + 1, (p % slots_bar) // 8 + 1,
                             1 + (p % 8))

    segs, last, end = [], -1, 0
    for t, c in rows:
        p = max(0, round(_q(t) * 8))
        if c == "N":
            end = p
            continue
        if p <= last:
            p = last + 1
        if segs and segs[-1][2] == c:
            continue
        # El TEMPS és l'exacte del model; `p` només serveix per a l'etiqueta.
        segs.append((t, p, c))
        last = p
    if not segs:
        raise RuntimeError(
            "No hi ha cap acord per exportar: el model només té «N». "
            "Posa'n almenys un (editant-lo al timeline) o prem «Analitza».")
    end = max(end, segs[-1][1] + slots_bar)
    if durada > 0:
        end = max(end, round(_q(durada) * 8))
    return segs, end, step, slots_bar, mapa, _pos_de_p


def segments_locators(csv_path, bpm, bpb, offset=0.0, durada=None,
                      mapa=None, _dades=None):
    """Guia DAW **en memòria**: `[(posició_1/32, acord, durada_en_beats), …]`.

    És un DERIVAT del model: **no es desa en cap fitxer** (decisió de
    l'operador, 2026-10-19: el sistema de fitxers intern, el més simple
    possible). El fan servir la guia HTML i la partitura; els WAVs d'acords
    usen `segments_export` (temps exactes) i el `manifest.csv`.
    """
    if _dades is None:
        _dades = _segments_guia_daw(csv_path, bpm, bpb, offset=offset,
                                    durada=durada, mapa=mapa)
    segs, end, _step, _slots_bar, _mapa, _pos_de_p = _dades
    out = []
    for i, (_t, p, c) in enumerate(segs):
        q = segs[i + 1][1] if i + 1 < len(segs) else end
        out.append((_pos_de_p(p), c, (q - p) / 8.0))
    return out


def events_partitura(csv_path, bpm, bpb, offset=0.0, durada=None, mapa=None,
                     _dades=None):
    """Acords per a la PARTITURA en memòria: `[(beat_inici, acord, beats), …]`.

    Mateixa font que la guia (`_segments_guia_daw`): el model quantitzat a
    **1/32**. Així la partitura no depèn de cap fitxer intermedi.
    """
    if _dades is None:
        _dades = _segments_guia_daw(csv_path, bpm, bpb, offset=offset,
                                    durada=durada, mapa=mapa)
    segs, end, _step, _slots_bar, _mapa, _pos_de_p = _dades
    out = []
    for i, (_t, p, c) in enumerate(segs):
        q = segs[i + 1][1] if i + 1 < len(segs) else end
        out.append((p / 8.0, c, (q - p) / 8.0))
    return out


def segments_exactes(csv_path, durada=0.0):
    """Segments EXACTES del model: `[(ini_s, fi_s, acord), …]`.

    A diferència de `segments_locators` (que quantitza a 1/32 per a la guia i
    els noms), ací els temps són els del model, sense arrodonir. És la font
    per a les durades dels WAV i per al `manifest.csv` de l'export.
    """
    durada = float(durada or 0.0)
    rows = []
    with open(csv_path, encoding="utf-8") as f:
        for r in csv.reader(f):
            if len(r) < 3 or r[0].startswith(("inici", "posici")):
                continue
            try:
                t = float(r[0])
            except ValueError:
                continue
            c = r[2].strip()
            if c == "N":
                continue
            if rows and rows[-1][1] == c:
                continue
            rows.append((t, c))
    if not rows:
        raise RuntimeError(
            "No hi ha cap acord per exportar: el model només té «N». "
            "Posa'n almenys un (editant-lo al timeline) o prem «Analitza».")
    out = []
    if rows[0][0] > 1e-9:
        out.append((0.0, rows[0][0], "N"))
    for i, (t, c) in enumerate(rows):
        if durada > 0 and t >= durada - 1e-9:
            continue
        fi = rows[i + 1][0] if i + 1 < len(rows) else (
            durada if durada > 0 else t + 1.0)
        if durada > 0:
            fi = min(fi, durada)
        if fi > t + 1e-9:
            out.append((t, fi, c))
    return out


def segments_export(csv_path, bpm, bpb, offset=0.0, durada=None, mapa=None):
    """`[(posicio_1/32, acord, ini_s, fi_s)]` per als WAVs i el manifest.

    El nom és la posició musical quantitzada a 1/32; els temps són els EXACTES
    del model. Si dos acords cauen a la mateixa fusa, el segon agafa la
    següent etiqueta per no xocar el nom (el manifest porta el temps exacte).
    """
    bpm = float(bpm)
    bpb = int(bpb)
    offset = float(offset or 0.0)
    durada = float(durada or 0.0)
    if mapa is None:
        mapa = _mapa_tempo_carpeta(os.path.dirname(os.path.abspath(csv_path)),
                                   offset=offset)
    elif hasattr(mapa, "es_constant") and mapa.es_constant():
        mapa = None
    step = 60.0 / bpm / 8.0                  # fusa (1/32)
    slots_bar = bpb * 8

    def _q(t):
        if mapa is not None:
            return mapa.quarters(t)
        return (float(t) - offset) / (60.0 / bpm)

    def _t_de_p(p):
        if mapa is not None:
            return mapa.t_de_quarters(p / 8.0)
        return offset + p * step

    def _pos(p):
        if mapa is not None:
            return mapa.label(_t_de_p(p))
        return "%d.%d.%d" % (p // slots_bar + 1, (p % slots_bar) // 8 + 1,
                             1 + (p % 8))

    exactes = segments_exactes(csv_path, durada)
    out, last = [], -1
    for ini, fi, c in exactes:
        p = max(0, round(_q(ini) * 8))
        if p <= last:
            p = last + 1
        out.append((_pos(p), c, ini, fi))
        last = p
    return out


def genera_guia_html(csv_path, bpm, bpb, offset=0.0, workdir=None, durada=None,
                     mapa=None, log=None, _dades=None):
    """Genera `guia_acords.html` en memòria i en retorna la ruta."""
    import html as _html
    workdir = workdir or os.path.dirname(os.path.abspath(csv_path))
    bpm = float(bpm)
    bpb = int(bpb)
    offset = float(offset or 0.0)
    durada_val = float(durada or 0.0)
    if _dades is None:
        _dades = _segments_guia_daw(csv_path, bpm, bpb, offset=offset,
                                    durada=durada_val, mapa=mapa)
    segs, end, step, slots_bar, mapa_resolt, _pos = _dades

    if mapa_resolt is not None:
        talls = [x[1] for x in mapa_resolt.compassos()]
        nbars = len(talls)
    else:
        nbars = (end + slots_bar - 1) // slots_bar
        talls = [offset + b * slots_bar * step for b in range(nbars)]

    def _bar_de(t):
        k = 0
        for i, tb in enumerate(talls):
            if t >= tb - 1e-9:
                k = i
            else:
                break
        return k

    cells = []
    for b in range(nbars):
        items = []
        for i, (t, _p, c) in enumerate(segs):
            t1 = segs[i + 1][0] if i + 1 < len(segs) else (
                durada_val if durada_val > 0 else t + 1e-9)
            if _bar_de(t) <= b <= _bar_de(max(t1 - 1e-9, t)):
                items.append(
                    '<span class="%s">%s</span>'
                    % ("" if _bar_de(t) >= b else "k", _html.escape(c)))
        cells.append('<div class="b"><i>%d</i>%s</div>' % (b + 1, " ".join(items)))

    guia_path = os.path.join(workdir, "guia_acords.html")
    with open(guia_path, "w", encoding="utf-8") as f:
        f.write(
            """<!doctype html><meta charset="utf-8"><title>Guia d'acords</title>
<style>body{font:20px system-ui;margin:20px;background:#fff;color:#111}
.g{display:grid;grid-template-columns:repeat(4,1fr);gap:0;border-top:1px solid #999;border-left:1px solid #999}
.b{position:relative;min-height:56px;padding:22px 8px 6px;border-right:1px solid #999;border-bottom:1px solid #999;font-weight:600}
.b i{position:absolute;top:3px;left:6px;font:12px system-ui;color:#888}.b span{margin-right:10px}.k{color:#aaa;font-weight:400}
@media(prefers-color-scheme:dark){body{background:#111;color:#eee}}</style>
<h3>%d BPM · %d temps/compàs · gris = acord que ve del compàs anterior</h3><div class="g">%s</div>"""
            % (bpm, bpb, "".join(cells))
        )
    if log:
        log(f"  {len(segs)} acords, {nbars} compassos")
    return guia_path


def pos_compas(t, bpm, bpb=4, lliure=False, offset=0.0, mapa=None):
    """Posició en format compàs.temps.fusa (qualsevol compàs).

    Graella = **1/32** (fusa). El tercer camp és la fusa dins del temps
    (1..8). `bpb` = temps per compàs, així funciona amb 3/4, 6/8, 5/4…
    """
    if lliure:
        return f"{float(t):07.3f}s"
    if mapa is not None and not mapa.es_constant():
        return mapa.label(t)           # mateixa forma (compàs.temps.fusa)
    step = 60.0 / bpm / 8              # fusa (1/32)
    SB = max(1, int(bpb)) * 8          # fuses per compàs
    # Sense clampar: abans de l'offset (compàs 1) les posicions son negatives
    # -> el silenci inicial queda com un compte enrere (compàs -1, -2...).
    p = round((float(t) - float(offset)) / step)
    return "%d.%d.%d" % (p // SB + 1, (p % SB) // 8 + 1, 1 + (p % 8))


def seq_abc(seccions):
    return "".join(s[2] for s in seccions)


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


def parteix_seccio(seccions, i, talla, marge=MIN_GAP_TEMPS):
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


def duplica_acord(acords, idx, durada, marge=MIN_GAP_TEMPS):
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


def duplica_seccio(seccions, idx, marge=MIN_GAP_TEMPS):
    """Duplica la secció `idx` (mateix nucli que els acords; #11)."""
    return seccions_de_clips(duplica_clips(
        clips_de_seccions(seccions), idx, marge))


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


def fer_wavs_acords_lliures(csv_path, total_s, dest_dir, sr, log,
                            manifest=None):
    os.makedirs(dest_dir, exist_ok=True)
    n = 0
    usats = set()          # desambigua noms d'acord que quedin iguals
    for ini, fi, chord in segments_lliures(csv_path, total_s, log):
        frames = int(round((fi - ini) * sr))
        if frames <= 0:
            # Mai escriure un WAV de durada 0 (un xoc d'inicis a la resolució
            # del CSV, o un acord a tocar del final, el produiria).
            log(f"wavs_acords: segment {ini:.6f}–{fi:.6f}s ({chord}) de durada "
                f"0 → s'omet")
            continue
        fn = (f"{ini:08.3f}s_{fi:08.3f}s_"
              f"{safe_filename(chord, fallback='N', usats=usats)}.wav")
        with wave.open(os.path.join(dest_dir, fn), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(b"\x00" * (frames * 2))
        if manifest is not None:
            manifest.append(("acord", fn, ini, fi, fi - ini, chord,
                             f"{ini:.3f}s"))
        n += 1
    log(f"wavs_acords: {n}")
    return n


def fer_wavs_acords(segments, dest_dir, sr, log, manifest=None):
    """WAVs silenciosos d'acords amb durades EXACTES.

    `segments` = `[(posicio_1/32, acord, ini_s, fi_s)]` (vegeu
    `segments_export`). El nom conserva la posició musical `1-1-1`; la durada
    del WAV surt dels segons exactes, no de la graella. Si es passa `manifest`,
    s'hi afegeix una fila per cada WAV amb els temps exactes.
    """
    os.makedirs(dest_dir, exist_ok=True)
    n = 0
    usats = set()          # desambigua noms d'acord que quedin iguals
    usats_pos = set()      # desambigua posicions que caiguen a la mateixa 1/32
    for pos_, chord, ini, fi in segments or ():
        ini, fi = float(ini), float(fi)
        frames = int(round((fi - ini) * sr))
        if frames <= 0:
            log(f"wavs_acords: segment {ini:.6f}–{fi:.6f}s ({chord}) de "
                f"durada 0 → s'omet")
            continue
        fn = (f"{pos_.replace('.', '-')}_"
              f"{safe_filename(chord, fallback='N', usats=usats)}.wav")
        base = fn
        k = 2
        while fn in usats_pos:
            fn = base[:-4] + f"_{k}.wav"
            k += 1
        usats_pos.add(fn)
        with wave.open(os.path.join(dest_dir, fn), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(b"\x00" * (frames * 2))
        if manifest is not None:
            manifest.append(("acord", fn, ini, fi, fi - ini, chord, pos_))
        n += 1
    log(f"wavs_acords: {n}")
    return n


def escriu_manifest(ruta, files):
    """Escriu `manifest.csv` amb els temps EXACTES de cada WAV exportat.

    `files`: `[(tipus, fitxer, ini_s, fi_s, durada_s, contingut, posicio), …]`.
    Els temps es desen amb 6 decimals (1 µs), igual que el MODEL.
    """
    def _escriu(f):
        w = csv.writer(f)
        w.writerow(["tipus", "fitxer", "inici_s", "fi_s", "durada_s",
                    "contingut", "posicio"])
        for tipus, fn, ini, fi, dur, contingut, pos in files:
            w.writerow([tipus, fn, f"{float(ini):.6f}", f"{float(fi):.6f}",
                        f"{float(dur):.6f}", contingut, pos])
    escriu_atomic(ruta, _escriu)
    return ruta


def exporta_total(csv_ac, csv_seg, sortida, bpm, bpb, offset, sr, log,
                 tempo_fix=True, amb_estructura=True, total_s=None,
                 acords=None, seccions=None, mapa_tempo=None):
    """Exporta el flux complet.

    Si es passen `acords`/`seccions` (el **model VIU** del visor), s'usen ELLS
    per sobre dels CSV del disc: es re-escriuen els CSV (acords + estructura)
    ja **normalitzats** amb l'invariant de COBERTURA, de manera que l'export
    **no perd les edicions manuals** (finals de secció, capçalera «N», etc.).
    Si no es passen, es comporta exactament com abans (llegeix els CSV).

    `mapa_tempo` = els trossos del mapa de BPM/compàs del **model viu**. Amb ell,
    el paquet exportat tracta els **tres tipus igual** (regla d'or #12): a més
    d'`acords.csv` + `wavs_acords/` i `estructura_ABC.csv` + `wavs_estructura/`,
    el mapa té la seva **carpeta pròpia** `mapa_tempo/` amb `tempo.csv` i
    `compas.csv` (els seus derivats, igual que els altres dos).

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
                clips_d_acords(acords, durada), durada, FORAT_ACORD,
                arrodoneix=True, deriva_fi=True, log=log)
            desa_acords_csv(csv_ac, clips, durada)
        if seccions is not None:
            _, seccions = normalitza_cobertura([], seccions, durada, log=log)
    if not os.path.isfile(csv_ac):
        raise FileNotFoundError(f"No trobo acords.csv: {csv_ac}")

    result = {"acords_csv": csv_ac, "sortida": sortida}
    manifest = []
    if tempo_fix:
        dades_guia = _segments_guia_daw(csv_ac, bpm, bpb, offset=offset,
                                        durada=total_s)
        segs = segments_export(csv_ac, bpm, bpb, offset=offset,
                               durada=total_s, mapa=dades_guia[4])
        guia = genera_guia_html(csv_ac, bpm, bpb, offset=offset, workdir=sortida,
                                durada=total_s, log=log, _dades=dades_guia)
        result["guia_html"] = guia
        dest = os.path.join(sortida, "wavs_acords")
        neteja_wavs(dest)
        result["n_acords_wavs"] = fer_wavs_acords(
            segs, dest, sr, log, manifest=manifest)
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
            csv_ac, total_s, dest, sr, log, manifest=manifest)

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
            abc, dest_abc, sr, log, manifest=manifest)

    # Regla d'or #12 (paritat a l'exportació): el mapa de BPM/compàs també surt
    # al paquet, amb la seva carpeta pròpia, com els altres dos tipus.
    if mapa_tempo:
        trams = [tuple(t) for t in mapa_tempo]
        dest_mapa = os.path.join(sortida, "mapa_tempo")
        desa_tempo_map(dest_mapa, trams)
        result["mapa_tempo_dir"] = dest_mapa
        result["n_mapa_trams"] = len(trams)
        if log:
            log(f"mapa de tempo/compàs exportat: {len(trams)} tram(s) a "
                f"{dest_mapa}")

    if manifest:
        result["manifest_csv"] = escriu_manifest(
            os.path.join(sortida, "manifest.csv"), manifest)
        if log:
            log(f"manifest: {len(manifest)} fila(es) amb temps exactes")

    return result


# Resolució temporal unificada dels CSV: 6 decimals (1 µs). És la MATEIXA
# unitat per als quatre fitxers editables (`acords.csv`, `estructura_ABC.csv`,
# `tempo.csv` i `compas.csv`): el model no ha de tindre una resolució per a
# cada fitxer. La UI en mostra 3 (mil·lisegons); el model en guarda 6.
TEMPS_DEC = 6
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


def regularitza_acords_items(items, csv_desti, bpm, bpb, offset, ritme, durada,
                             log=None):
    """Mode fàcil: regularitza a la graella uns acords ja en memòria.

    `items`: `[(t, nom), …]` (normalment el **cru** de l'anàlisi desat al
    projecte). Escriu `csv_desti` amb el MODEL resultant (cobertura #4).
    """
    from app import graella                    # import local: evita cicles
    items = [(float(t), str(n)) for t, n in (items or ())]
    if not items:
        return None
    if ritme in (None, "auto"):
        ritme = graella.infereix_nivell(items, bpm, bpb, offset, durada, log=log)
    res = graella.regularitza_acords(items, bpm, bpb, offset,
                                     ritme or "compas", durada, log=log)
    clips = normalitza_clips(
        clips_d_acords(res, durada), durada, FORAT_ACORD,
        arrodoneix=True, deriva_fi=True, log=log)
    desa_acords_csv(csv_desti, clips, durada)
    return acords_de_clips(clips)


def regularitza_acords_csv(csv_cru, csv_desti, bpm, bpb, offset, ritme, durada,
                           log=None):
    """Igual que `regularitza_acords_items`, però llegint el cru d'un CSV."""
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
    return regularitza_acords_items(items, csv_desti, bpm, bpb, offset, ritme,
                                    durada, log=log)


def desa_acords_csv(ruta, clips, durada=0.0):
    """Desa el model d'acords (`Clip(ini, fi, payload)`) com a `inici,fi,acord`."""
    clips = list(clips or ())
    durada = float(durada or 0.0)

    def _escriu(f):
        w = csv.writer(f)
        for c in clips:
            if not isinstance(c, Clip):
                c = Clip(float(c[0]), float(c[1]), c[2])
            ini, fi = float(c.ini), float(c.fi)
            nom = c.nom
            w.writerow([f"{ini:.{TEMPS_DEC}f}", f"{fi:.{TEMPS_DEC}f}", nom])
    escriu_atomic(ruta, _escriu)


# --- Mapa de TEMPO i COMPÀS (persistència) -------------------------
# Dos fitxers, com les dues pistes d'un DAW (tempo track / signature track):
#   tempo.csv   →  inici,fi,bpm
#   compas.csv  →  inici,fi,num,den
# Els trossos són alineats (les mateixes fronteres), així no es desincronitzen.
NOM_CSV_TEMPO = "tempo.csv"
NOM_CSV_COMPAS = "compas.csv"


def desa_tempo_csv(ruta, trams):
    """Desa el mapa de tempo com a `inici,fi,bpm` (resolució `TEMPS_DEC`)."""
    def _escriu(f):
        w = csv.writer(f)
        for s in trams:
            w.writerow([f"{float(s[0]):.{TEMPS_DEC}f}",
                        f"{float(s[1]):.{TEMPS_DEC}f}",
                        f"{float(s[2]):.6f}"])
    escriu_atomic(ruta, _escriu)


def desa_compas_csv(ruta, trams):
    """Desa el mapa de compàs com a `inici,fi,num,den`.

    `trams` són els del mapa: `(ini, fi, bpm, num, den)` (només s'escriuen
    `ini, fi, num, den`), o també `(ini, fi, num, den)`.
    """
    def _escriu(f):
        w = csv.writer(f)
        for s in trams:
            w.writerow([f"{float(s[0]):.{TEMPS_DEC}f}",
                        f"{float(s[1]):.{TEMPS_DEC}f}",
                        f"{int(s[-2])}", f"{int(s[-1])}"])
    escriu_atomic(ruta, _escriu)


def llegeix_tempo_csv(ruta):
    """`inici,fi,bpm` → `[(ini, fi, bpm), …]` (buit si no hi és o és dolent)."""
    out = []
    if not ruta or not os.path.isfile(ruta):
        return out
    with open(ruta, encoding="utf-8") as f:
        for fila in csv.reader(f):
            if len(fila) < 3 or fila[0].startswith("inici"):
                continue
            try:
                out.append((float(fila[0]), float(fila[1]), float(fila[2])))
            except ValueError:
                continue
    return out


def llegeix_compas_csv(ruta):
    """`inici,fi,num,den` → `[(ini, fi, num, den), …]` (buit si no hi és)."""
    out = []
    if not ruta or not os.path.isfile(ruta):
        return out
    with open(ruta, encoding="utf-8") as f:
        for fila in csv.reader(f):
            if len(fila) < 4 or fila[0].startswith("inici"):
                continue
            try:
                out.append((float(fila[0]), float(fila[1]),
                            int(round(float(fila[2]))),
                            int(round(float(fila[3])))))
            except ValueError:
                continue
    return out


def desa_tempo_map(carpeta, trams):
    """Desa els dos mapes (tempo + compàs) d'una carpeta de projecte."""
    os.makedirs(carpeta, exist_ok=True)
    desa_tempo_csv(os.path.join(carpeta, NOM_CSV_TEMPO), trams)
    desa_compas_csv(os.path.join(carpeta, NOM_CSV_COMPAS), trams)


def llegeix_tempo_map(carpeta, bpm, num, den, durada):
    """Trossos del mapa d'una carpeta; si no hi ha fitxers, un sol tros
    (`bpm`, `num/den`) que cobreix `[0, durada)` — el cas constant d'avui."""
    tempo = llegeix_tempo_csv(os.path.join(carpeta or "", NOM_CSV_TEMPO))
    compas = llegeix_compas_csv(os.path.join(carpeta or "", NOM_CSV_COMPAS))
    if not tempo or not compas:
        return [(0.0, float(durada or 0.0), float(bpm), int(num), int(den))]
    trams = []
    for t, c in zip(tempo, compas):
        trams.append((float(t[0]), float(t[1]), float(t[2]),
                      int(c[2]), int(c[3])))
    if not trams:
        return [(0.0, float(durada or 0.0), float(bpm), int(num), int(den))]
    # Els CSVs poden haver estat editats a mà: el que ix d'ací és el MODEL, i
    # ha de complir les regles 1, 2, 4 i 8 (ordre, contigüitat, cobertura de
    # 0 a la durada i valors vàlids). Es normalitza AQUÍ, que és la porta
    # d'entrada, igual que fa `normalitza_cobertura` amb els acords.
    return tempo_map.normalitza_trams(trams, durada)


def neteja_wavs(dest_dir):
    if not os.path.isdir(dest_dir):
        return
    for fn in os.listdir(dest_dir):
        if fn.endswith(".wav"):
            os.remove(os.path.join(dest_dir, fn))


def regenera_wavs_acords(csv_path, sortida, bpm, bpb, offset, total_s, sr, log,
                         tempo_fix=True, manifest=None):
    # Recalcula guia + wavs_acords/ a partir del csv ja editat.
    dest = os.path.join(sortida, "wavs_acords")
    neteja_wavs(dest)
    if tempo_fix:
        dades_guia = _segments_guia_daw(csv_path, bpm, bpb, offset=offset,
                                        durada=total_s)
        segs = segments_export(csv_path, bpm, bpb, offset=offset,
                               durada=total_s, mapa=dades_guia[4])
        genera_guia_html(csv_path, bpm, bpb, offset=offset, workdir=sortida,
                         durada=total_s, log=log, _dades=dades_guia)
        return fer_wavs_acords(segs, dest, sr, log, manifest=manifest)
    return fer_wavs_acords_lliures(csv_path, total_s, dest, sr, log,
                                   manifest=manifest)


def fer_wavs_estructura(abc_csv, dest_dir, sr, log, manifest=None):
    os.makedirs(dest_dir, exist_ok=True)
    n = 0
    usats = set()          # desambigua etiquetes de secció que quedin iguals
    with open(abc_csv, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            nm = (f"{r['compas_ini'].replace('.', '-')}_"
                  f"{r['compas_fi'].replace('.', '-')}_"
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
