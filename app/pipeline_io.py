"""Fitxers, noms segurs i escriptura atòmica d'AUTO CHORDS (F1).

Extret de `app/pipeline.py`: no depén de Qt ni del motor Vamp. La façana
`app.pipeline` re-exporta estos símbols.
"""
import csv
import os
import shutil
import threading
import time

from app import xifrat
from .pipeline_model import TEMPS_DEC, Clip


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
# NO la toquen l'edició, ni la quantització, ni els canvis de compàs/BPM/mode.
# És el «primer autoanàlisi» que es pot reintrepretar amb la graella.
# Prefixos dels directoris temporals que crea l'app (per netejar-los sempre).
PREFIXOS_TMP = ("ac_ttl_", "ac_qm_", "ac_key_", "ac_rang_")


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
def neteja_wavs(dest_dir):
    if not os.path.isdir(dest_dir):
        return
    for fn in os.listdir(dest_dir):
        if fn.endswith(".wav"):
            os.remove(os.path.join(dest_dir, fn))
