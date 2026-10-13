#!/usr/bin/env python3
"""Baixa un fitxer i en comprova el SHA256.

Ús:
    python3 eines/baixa_verificat.py URL SHA256 DESTI
    python3 eines/baixa_verificat.py URL - DESTI       # calcula i mostra el hash

`SHA256` pot ser el hash esperat (64 caràcters hex) o `-` per NOMÉS calcular-lo
i mostrar-lo: és el que es fa la primera vegada que es fixa una versió (vegeu
`eines/deps_fixades.env`).

Propietats:
- **HTTPS obligatori** (l'única excepció és HTTP a `127.0.0.1`/`localhost`, per
  poder provar-ho amb un servidor local). Res de `file:`, `ftp:` ni `data:`.
- **Reintents** amb espera creixent i **timeout** de connexió i de lectura.
- **Mai deixa un fitxer a mitges**: s'escriu a `<desti>.part` i només es mou a
  `<desti>` quan la baixada ha acabat. Si el hash no quadra, el fitxer
  descarregat s'esborra.
- Si alguna cosa falla → missatge clar a stderr i **codi de sortida != 0**.
- **Memòria cau**: cada fitxer verificat es desa a
  `<projecte>/.baixades/<sha256>` (carpeta gitignorada; es pot canviar amb
  `$AUTO_CHORDS_BAIXADES`). La propera vegada **no es baixa**: es copia. Al CI,
  `actions/cache` desa aquesta carpeta entre execucions. `--sense-cache` ho
  desactiva.
- **Només biblioteca estàndard** (Python >= 3.8 del sistema): el fan servir els
  scripts i els workflows ABANS de tenir el Python portable del projecte.
"""
import hashlib
import os
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT = 60.0          # segons per connexió i per lectura
REINTENTS = 3
ESPERA = 2.0            # segons; es multiplica pel número d'intent
BLOC = 1024 * 256       # mida dels trossos de lectura

# Únics hosts on acceptem HTTP (proves locals).
_HOSTS_LOCALS = ("127.0.0.1", "localhost", "::1", "0.0.0.0")

# ── Memòria cau de baixades ─────────────────────────────────────────────────
# Cada fitxer verificat es desa amb el seu SHA256 com a nom. Així, la propera
# vegada NO cal baixar-lo (ni aquí ni al CI, on `actions/cache` desa aquesta
# carpeta). Es pot canviar amb AUTO_CHORDS_BAIXADES o desactivar amb
# `--sense-cache`. La carpeta és gitignorada.
CACHE_ENV = "AUTO_CHORDS_BAIXADES"
_ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USA_CACHE = True


def cache_dir():
    """Carpeta de memòria cau de baixades (per defecte `<projecte>/.baixades`)."""
    return os.getenv(CACHE_ENV) or os.path.join(_ARREL, ".baixades")


def sha256_fitxer(path):
    """SHA256 d'un fitxer del disc."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for tros in iter(lambda: f.read(BLOC), b""):
            h.update(tros)
    return h.hexdigest()


def _de_cache(sha):
    """Ruta de la còpia a la memòria cau (si hi és i el hash QUADRA), o None."""
    if not sha or len(sha) != 64 or not USA_CACHE:
        return None
    p = os.path.join(cache_dir(), sha.lower())
    if not os.path.isfile(p):
        return None
    try:
        if sha256_fitxer(p) != sha.lower():
            return None         # còpia corrupta: la ignorem i es torna a baixar
    except OSError:
        return None
    return p


def _a_cache(path, sha):
    """Desa una còpia a la memòria cau (best-effort: mai llança)."""
    if not USA_CACHE or not sha:
        return
    try:
        d = cache_dir()
        os.makedirs(d, exist_ok=True)
        desti = os.path.join(d, sha.lower())
        try:
            if os.path.isfile(desti) and sha256_fitxer(desti) == sha.lower():
                return          # ja hi és i és bona
        except OSError:
            pass
        shutil.copy2(path, desti + ".part")
        os.replace(desti + ".part", desti)
    except OSError:
        pass


def valida_url(url):
    """Cert si la URL és acceptable: HTTPS, o HTTP si és local (proves)."""
    p = urllib.parse.urlsplit(str(url))
    if not p.netloc:
        return False
    if p.scheme == "https":
        return True
    if p.scheme == "http":
        return (p.hostname or "").lower() in _HOSTS_LOCALS
    return False


def _esborra(path):
    try:
        os.remove(path)
    except OSError:
        pass


def baixa(url, desti, log=print, reintents=REINTENTS, timeout=TIMEOUT,
          sha_esperat=None):
    """Baixa `url` a `desti` i retorna el SHA256 calculat.

    Si `sha_esperat` és un hash i ja el tenim a la **memòria cau**, no es baixa
    res: es copia. No deixa mai el fitxer a mitges (escriu `<desti>.part` i el
    mou al final).
    """
    if not valida_url(url):
        raise ValueError(f"URL no permesa (cal HTTPS): {url!r}")
    d = os.path.dirname(os.path.abspath(desti))
    os.makedirs(d, exist_ok=True)
    # 1) Memòria cau: si ja el tenim (i el hash quadra), no baixem res.
    c = _de_cache(sha_esperat)
    if c:
        shutil.copy2(c, desti)
        log(f"  memòria cau: {os.path.basename(desti)} (no cal baixar)")
        return sha_esperat.lower()
    part = desti + ".part"
    ultim = None
    for intent in range(1, reintents + 1):
        try:
            h = hashlib.sha256()
            with urllib.request.urlopen(url, timeout=timeout) as r, \
                    open(part, "wb") as f:
                while True:
                    tros = r.read(BLOC)
                    if not tros:
                        break
                    f.write(tros)
                    h.update(tros)
            os.replace(part, desti)
            hx = h.hexdigest()
            _a_cache(desti, hx)      # 2) hi desem una còpia per a la propera
            return hx
        except (urllib.error.URLError, OSError, ValueError) as e:
            ultim = e
            log(f"  baixada fallida (intent {intent}/{reintents}): {e}")
            _esborra(part)
            if intent < reintents:
                time.sleep(ESPERA * intent)
    raise RuntimeError(f"no s'ha pogut baixar {url}: {ultim}")


def main(argv):
    global USA_CACHE
    if "--sense-cache" in argv:
        USA_CACHE = False
    args = [a for a in argv[1:] if a not in ("-q", "--quiet", "--sense-cache")]
    quiet = ("-q" in argv) or ("--quiet" in argv)
    log = (lambda *_a: None) if quiet else print
    if len(args) != 3:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    url, esperat, desti = args
    if esperat != "-" and len(esperat) != 64:
        print(f"error: SHA256 ha de tenir 64 caràcters hex: {esperat!r}",
              file=sys.stderr)
        return 2
    try:
        h = baixa(url, desti, log=log, reintents=REINTENTS, timeout=TIMEOUT,
                  sha_esperat=esperat)
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    if esperat == "-":
        # Mode «fixar versió nova»: baixa, diu el hash i deixa el fitxer.
        print(f"sha256  {h}  {os.path.basename(desti)}")
        return 0
    if h.lower() != esperat.lower():
        _esborra(desti)
        print("ERROR: el SHA256 NO coincideix!\n"
              f"  esperat:  {esperat}\n  obtingut: {h}\n"
              "  (el fitxer descarregat s'ha esborrat: no es deixa res a mitges)",
              file=sys.stderr)
        return 1
    log(f"OK: {desti}  (sha256 {h[:16]}…)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
