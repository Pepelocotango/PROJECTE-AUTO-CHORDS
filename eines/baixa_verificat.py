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
- **Només biblioteca estàndard** (Python >= 3.8 del sistema): el fan servir els
  scripts i els workflows ABANS de tenir el Python portable del projecte.
"""
import hashlib
import os
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


def baixa(url, desti, log=print, reintents=REINTENTS, timeout=TIMEOUT):
    """Baixa `url` a `desti` i retorna el SHA256 calculat.

    No deixa mai el fitxer a mitges (escriu `<desti>.part` i el mou al final).
    """
    if not valida_url(url):
        raise ValueError(f"URL no permesa (cal HTTPS): {url!r}")
    part = desti + ".part"
    d = os.path.dirname(os.path.abspath(desti))
    ultim = None
    for intent in range(1, reintents + 1):
        try:
            os.makedirs(d, exist_ok=True)
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
            return h.hexdigest()
        except (urllib.error.URLError, OSError, ValueError) as e:
            ultim = e
            log(f"  baixada fallida (intent {intent}/{reintents}): {e}")
            _esborra(part)
            if intent < reintents:
                time.sleep(ESPERA * intent)
    raise RuntimeError(f"no s'ha pogut baixar {url}: {ultim}")


def main(argv):
    args = [a for a in argv[1:] if a not in ("-q", "--quiet")]
    quiet = len(args) != len(argv) - 1
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
        h = baixa(url, desti, log=log, reintents=REINTENTS, timeout=TIMEOUT)
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
