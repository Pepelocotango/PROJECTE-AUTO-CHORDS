#!/usr/bin/env python3
# pipeline.py — motor de l'Auto Chords (stdlib + binaris del projecte).
# Cadena: wav -> csv acords (annotator+Chordino) -> guia ->
#         wavs_acords (+ qm-segmenter -> ABC -> wavs_estructura, opcional).
# Tot en català.
import csv
import os

from . import tempo_csv
from . import tempo_map
import threading
import time
import wave

from . import pipeline_vamp as _pv
_RESERVATS_WINDOWS = _pv._RESERVATS_WINDOWS

from . import pipeline_model as _pm
TEMPS_DEC = _pm.TEMPS_DEC
RESOLUCIO_CSV = _pm.RESOLUCIO_CSV
NOM_MAPA_TEMPO = _pm.NOM_MAPA_TEMPO
APP_DIR = _pv.APP_DIR
PROJ_DIR = _pv.PROJ_DIR
VAMP_DIRS = _pv.VAMP_DIRS
HOST = _pv.HOST
STEPS = _pv.STEPS
CHORDS_TRANSFORM = _pv.CHORDS_TRANSFORM
MOTORS_BPM = _pv.MOTORS_BPM
MOTORS_ESTRUCTURA = _pv.MOTORS_ESTRUCTURA
QM = _pv.QM
PREFIXOS_TMP = _pv.PREFIXOS_TMP

from . import pipeline_model as _pm
Clip = _pm.Clip
FORAT_ACORD = _pm.FORAT_ACORD
FORAT_SECCIO = _pm.FORAT_SECCIO
MIN_GAP_TEMPS = _pm.MIN_GAP_TEMPS
SENSE_ACORD = _pm.SENSE_ACORD
SENSE_SECCIO = _pm.SENSE_SECCIO
TOL_TEMPS = _pm.TOL_TEMPS
_ClipBase = _pm._ClipBase
_nom_item_acord = _pm._nom_item_acord
_segments_guia_daw = _pm._segments_guia_daw
_tempo_csv_carpeta = _pm._tempo_csv_carpeta
NOM_MAPA_TEMPO = _pm.NOM_MAPA_TEMPO
RESOLUCIO_CSV = _pm.RESOLUCIO_CSV
TEMPS_DEC = _pm.TEMPS_DEC
acords_de_clips = _pm.acords_de_clips
bloc_sobre_acords = _pm.bloc_sobre_acords
bloc_sobre_seccions = _pm.bloc_sobre_seccions
clips_d_acords = _pm.clips_d_acords
clips_de_seccions = _pm.clips_de_seccions
contiguitat_seccions = _pm.contiguitat_seccions
duplica_bloc_clips = _pm.duplica_bloc_clips
duplica_bloc_seccions = _pm.duplica_bloc_seccions
duplica_clips = _pm.duplica_clips
elimina_clips = _pm.elimina_clips
elimina_seccio = _pm.elimina_seccio
events_partitura = _pm.events_partitura
fusiona_acords = _pm.fusiona_acords
fusiona_clips = _pm.fusiona_clips
fusiona_seccions = _pm.fusiona_seccions
model_inicial = _pm.model_inicial
mou_bloc_acords = _pm.mou_bloc_acords
mou_bloc_clips = _pm.mou_bloc_clips
mou_bloc_seccions = _pm.mou_bloc_seccions
normalitza_clips = _pm.normalitza_clips
normalitza_cobertura = _pm.normalitza_cobertura
parteix_acord = _pm.parteix_acord
parteix_clips = _pm.parteix_clips
parteix_seccio = _pm.parteix_seccio
pos_compas = _pm.pos_compas
redimensiona_acord = _pm.redimensiona_acord
redimensiona_clips = _pm.redimensiona_clips
redimensiona_seccio = _pm.redimensiona_seccio
renomena_acords_model = _pm.renomena_acords_model
renomena_seccions_model = _pm.renomena_seccions_model
saneja_nom_acord = _pm.saneja_nom_acord
seccions_de_clips = _pm.seccions_de_clips
segments_exactes = _pm.segments_exactes
segments_export = _pm.segments_export
segments_lliures = _pm.segments_lliures
segments_locators = _pm.segments_locators
seq_abc = _pm.seq_abc
style = _pm.style
substitueix_en_model = _pm.substitueix_en_model
valida_canvis_acords = _pm.valida_canvis_acords
valida_canvis_seccions = _pm.valida_canvis_seccions

# Directoris dels plugins Vamp SEGONS EL SO (vegeu `app/plataforma.py`):
#   Linux   -> nnls-chroma-linux64-local + qm-vamp-plugins-linux64-local
#   Windows -> nnls-chroma-win64-local   + qm-vamp-plugins-win64-local
#   macOS   -> nnls-chroma-macos-local   + qm-vamp-plugins-macos-local


# Noms reservats de Windows: no poden ser el nom (ni l'arrel) d'un fitxer.


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
# NO la toquen l'edició, ni la quantització, ni els canvis de compàs/BPM/mode.
# És el «primer autoanàlisi» que es pot reintrepretar amb la graella.
# Prefixos dels directoris temporals que crea l'app (per netejar-los sempre).










# --- Host Vamp propi (vamp_host_local) ------------------------------------
# L'ÚNIC motor d'anàlisi: no arrossega Qt6/ICU/glib, només libc/libstdc++/
# sndfile. Vegeu eines/vamp_host.cpp.

# mida de finestra (step, block) per transform (els valors «de fàbrica» dels
# plugins a 44.1 kHz; s'escalen al mostreig real).




























# --- Queen Mary: onsets, bars, beats, key (vegeu docs/QM_VAMP.md) ----------










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
# Separació mínima PRÀCTICA per a l'edició manual: 1 ms. La resolució de
# guardat és 1 µs, però dos canvis d'acord a menys d'1 ms no tenen sentit
# musical i fan clips inútils. No s'ha de confondre amb `RESOLUCIO_CSV`.


# --- Model unificat de CLIPS (refactor «inici+fi») -------------------------
# Un SOL tipus per a acords i estructura: `Clip(ini, fi, payload)`, on el
# `payload` és tot el que no és temps:
#   · acords:     `(nom, tsrc)` — p. ex. `("Am", "16.153846154")`;
#   · estructura: `(lletra, família)` — p. ex. `("A", "A")`.
# La font única de veritat és la CADENA DE FRONTERES: el `fi` se'n deriva i, per
# tant, no pot quedar mai incoherent. Contracte i pla: docs/archive/REFACTOR_INICI_FI.md.






























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




















# --- Operacions úniques sobre CLIPS (S2): una sola implementació -------------




















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
                 acords=None, seccions=None, tempo_csv=None):
    """Exporta el flux complet.

    Si es passen `acords`/`seccions` (el **model VIU** del visor), s'usen ELLS
    per sobre dels CSV del disc: es re-escriuen els CSV (acords + estructura)
    ja **normalitzats** amb l'invariant de COBERTURA, de manera que l'export
    **no perd les edicions manuals** (finals de secció, capçalera «N», etc.).
    Si no es passen, es comporta exactament com abans (llegeix els CSV).

    `tempo_csv` = els trossos del mapa de BPM/compàs del **model viu**. Amb ell,
    el paquet exportat tracta els **tres tipus igual** (regla d'or #12): a més
    d'`acords.csv` + `wavs_acords/` i `estructura_ABC.csv` + `wavs_estructura/`,
    el mapa té la seva **carpeta pròpia** `mapa_tempo/` amb `mapa_tempo.csv`
    (el seu derivat, igual que els altres dos).

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
    if tempo_csv:
        # No convertir a tuples: es perdrien `tipus`/`compassos` dels rubatos.
        trams = list(tempo_csv)
        dest_mapa = os.path.join(sortida, "tempo_csv")
        desa_tempo_map(dest_mapa, trams)
        result["tempo_csv_dir"] = dest_mapa
        result["n_mapa_trams"] = len(trams)
        rubatos = [t for t in trams
                   if getattr(t, "tipus", None) == "rubato"]
        if rubatos:
            ruta_avis = os.path.join(dest_mapa, "AVIS_APROXIMACIO.txt")

            def _escriu_avis(f):
                f.write(
                    "RUBATO — GRAELLA APROXIMADA\n"
                    "================================\n\n"
                    "Estos trams no són una detecció de tempo: el BPM i els\n"
                    "compassos són una representació derivada per a DAW i\n"
                    "partitura. Els segons del model són la veritat.\n\n"
                    "inici_s\tfi_s\tbpm_derivat\tcompassos\n")
                for tr in rubatos:
                    f.write(f"{float(tr.ini):.6f}\t{float(tr.fi):.6f}\t"
                            f"{float(tr.bpm):.6f}\t{tr.compassos}\n")
            escriu_atomic(ruta_avis, _escriu_avis)
            result["tempo_csv_avis"] = ruta_avis
            if log:
                log(f"mapa de tempo/compàs: {len(rubatos)} rubato(s) marcats "
                    "com a graella aproximada")
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
# unitat per als tres fitxers editables (`acords.csv`, `estructura_ABC.csv` i
# `mapa_tempo.csv`): el model no ha de tindre una resolució per a cada fitxer.
# La UI en mostra 3 (mil·lisegons); el model en guarda 6.
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


# --- Mapa de TEMPO i COMPÀS (model unificat `mapa_tempo.csv`) --------
# Un sol fitxer, amb una fila per tram:
#   inici,fi,bpm,tipus,compassos
# `tipus` = normal | rubato; `compassos` = `4/4` o `4/4*3+3/4`.
NOM_MAPA_TEMPO = tempo_csv.NOM_MAPA_TEMPO


# --- Marcadors (inici de compàs marcats a mà, en viu) -----------------------
NOM_MARCADORS = "marcadors.csv"


def desa_marcadors(carpeta, marques):
    """Desa els marcadors (una columna `t_s`) al projecte. Silenciós si falla."""
    if not carpeta:
        return None
    ruta = os.path.join(str(carpeta), NOM_MARCADORS)
    try:
        escriu_atomic(ruta, lambda f: _escriu_marcadors(f, marques))
    except OSError:
        return None
    return ruta


def _escriu_marcadors(f, marques):
    # Format nou (Fase 4): `t_s,tipus` (tipus = compas | seccio).
    f.write("t_s,tipus\n")
    for item in marques or ():
        if isinstance(item, (tuple, list)):
            t, tipus = item[0], item[1] if len(item) > 1 else "seccio"
        else:
            t, tipus = item, "seccio"
        f.write(f"{float(t):.6f},{tipus}\n")


def llegeix_marcadors(carpeta, durada=0.0):
    """Llig els marcadors del projecte (llista de temps en segons).

    Manté la signatura antiga (llista de floats) per compatibilitat. Els tipus
    es lliguen amb `llegeix_marcadors_tipus`.
    """
    from app import marcadors as _m
    if not carpeta:
        return []
    ruta = os.path.join(str(carpeta), NOM_MARCADORS)
    out = []
    try:
        with open(ruta, encoding="utf-8") as f:
            for linia in f:
                parts = linia.strip().split(",")
                text = parts[0]
                if not text or text.lower().startswith("t_"):
                    continue
                try:
                    out.append(float(text))
                except ValueError:
                    continue
    except OSError:
        return []
    return _m.normalitza_marcadors(out, float(durada or 1e9))


def llegeix_marcadors_tipus(carpeta):
    """Llig el mapa temps→tipus dels marcadors (buit si no n'hi ha)."""
    if not carpeta:
        return {}
    ruta = os.path.join(str(carpeta), NOM_MARCADORS)
    out = {}
    try:
        with open(ruta, encoding="utf-8") as f:
            for linia in f:
                parts = linia.strip().split(",")
                if not parts or parts[0].lower().startswith("t_"):
                    continue
                try:
                    t = float(parts[0])
                except ValueError:
                    continue
                tipus = parts[1].strip() if len(parts) > 1 else "seccio"
                if tipus not in ("compas", "seccio"):
                    tipus = "seccio"
                out[round(t, 6)] = tipus
    except OSError:
        return {}
    return out


def desa_tempo_map(carpeta, trams):
    """Desa el mapa unificat (`mapa_tempo.csv`) d'una carpeta de projecte."""
    os.makedirs(carpeta, exist_ok=True)
    tempo_csv.desa_tempo_csv(os.path.join(carpeta, NOM_MAPA_TEMPO), trams)


def llegeix_tempo_map(carpeta, bpm, num, den, durada, log=None):
    """Llig `mapa_tempo.csv`; si no hi ha model, un sol tros constant.

    Els projectes amb el model antic (`tempo.csv` + `compas.csv`) es rebutgen:
    no hi ha migració. El resultat són `TramMapa`, de manera que el visor pot
    distingir els clips normals dels rubatos.
    """
    def _constant():
        net, avisos = tempo_map.neteja_trams(
            [(0.0, float(durada or 0.0), bpm, num, den)], durada)
        if log:
            for avís in avisos:
                log(f"Mapa de tempo: {avís}")
        return [tempo_csv.des_de_tupla(t) for t in net]

    if not carpeta:
        return _constant()
    ruta = os.path.join(carpeta, NOM_MAPA_TEMPO)
    if tempo_csv.te_format_antic(carpeta) and not os.path.isfile(ruta):
        raise ValueError(
            f"El projecte té el model antic ({tempo_csv.NOM_CSV_TEMPO_ANTIC}"
            f" + {tempo_csv.NOM_CSV_COMPAS_ANTIC}); no suportat. Cal recrear "
            "el mapa amb el model actual.")
    trams_map = tempo_csv.llegeix_tempo_csv(ruta, log=log)
    if not trams_map:
        return _constant()
    net, avisos = tempo_csv.normalitza_trams_map(
        trams_map, durada, log=log, fusiona=True)
    if log:
        for avís in avisos:
            log(f"Mapa de tempo: {avís}")
    return net


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
