"""Tests de l'eina de baixada verificada (`eines/baixa_verificat.py`).

Es fa servir un **servidor HTTP local** (loopback) perquè els tests no depenguin
de la xarxa.
"""
import hashlib
import http.server
import importlib.util
import os
import shutil
import socketserver
import tempfile
import threading
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _carrega():
    ruta = os.path.join(ROOT, "eines", "baixa_verificat.py")
    spec = importlib.util.spec_from_file_location("baixa_verificat", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BV = _carrega()


class _Servidor:
    """Servidor HTTP local que serveix un diccionari {cami: bytes}."""

    def __init__(self, fitxers):
        self._fitxers = fitxers
        pare = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                cos = pare._fitxers.get(self.path)
                if cos is None:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Length", str(len(cos)))
                self.end_headers()
                self.wfile.write(cos)

            def log_message(self, *a):      # silenciós
                pass

        self._srv = socketserver.TCPServer(("127.0.0.1", 0), Handler)
        self.port = self._srv.server_address[1]
        self._fil = threading.Thread(target=self._srv.serve_forever,
                                     daemon=True)
        self._fil.start()

    def url(self, cami):
        return f"http://127.0.0.1:{self.port}{cami}"

    def tanca(self):
        self._srv.shutdown()
        self._srv.server_close()


class BaixaVerificatTests(unittest.TestCase):
    def setUp(self):
        # Sense reintents ni esperes: els tests de fallada han de ser ràpids.
        self._reintents = BV.REINTENTS
        self._espera = BV.ESPERA
        BV.REINTENTS = 1
        BV.ESPERA = 0
        self._d = tempfile.mkdtemp()
        self._cos = b"contingut de prova\n" * 20
        self._sha = hashlib.sha256(self._cos).hexdigest()
        self.srv = _Servidor({"/fitxer.bin": self._cos})

    def tearDown(self):
        BV.REINTENTS = self._reintents
        BV.ESPERA = self._espera
        self.srv.tanca()
        shutil.rmtree(self._d, ignore_errors=True)

    def _desti(self):
        return os.path.join(self._d, "f.bin")

    def test_hash_correcte(self):
        rc = BV.main(["baixa_verificat.py", self.srv.url("/fitxer.bin"),
                      self._sha, self._desti()])
        self.assertEqual(rc, 0)
        with open(self._desti(), "rb") as f:
            self.assertEqual(f.read(), self._cos)

    def test_hash_incorrecte(self):
        rc = BV.main(["baixa_verificat.py", self.srv.url("/fitxer.bin"),
                      "0" * 64, self._desti()])
        self.assertEqual(rc, 1)
        self.assertFalse(os.path.exists(self._desti()))
        self.assertFalse(os.path.exists(self._desti() + ".part"))

    def test_calcula_el_hash(self):
        rc = BV.main(["baixa_verificat.py", self.srv.url("/fitxer.bin"),
                      "-", self._desti()])
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(self._desti()))
        self.assertEqual(BV.baixa(self.srv.url("/fitxer.bin"),
                                  os.path.join(self._d, "altre.bin")),
                         self._sha)

    def test_url_no_permesa(self):
        for url in ("file:///etc/passwd", "ftp://exemple/x",
                    "http://exemple.com/x", "data:text/plain,hola", ""):
            with self.assertRaises(ValueError):
                BV.baixa(url, self._desti())

    def test_404_no_deixa_fitxer(self):
        rc = BV.main(["baixa_verificat.py", self.srv.url("/no-existeix"),
                      self._sha, self._desti()])
        self.assertEqual(rc, 1)
        self.assertFalse(os.path.exists(self._desti()))
        self.assertFalse(os.path.exists(self._desti() + ".part"))

    def test_sha256_mal_format(self):
        rc = BV.main(["baixa_verificat.py", self.srv.url("/fitxer.bin"),
                      "abc", self._desti()])
        self.assertEqual(rc, 2)

    def test_us_dolent(self):
        self.assertEqual(BV.main(["baixa_verificat.py"]), 2)

    def test_crea_el_directori_desti(self):
        desti = os.path.join(self._d, "sub", "dir", "f.bin")
        rc = BV.main(["baixa_verificat.py", self.srv.url("/fitxer.bin"),
                      self._sha, desti])
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.isfile(desti))


class DepsFixadesTests(unittest.TestCase):
    """El fitxer de versions fixades ha de ser complet i llegible."""

    RUTA = os.path.join(ROOT, "eines", "deps_fixades.env")
    CLAUS_SHA = ("PYBS_SHA256", "FFMPEG_LINUX_SHA256", "APPIMAGETOOL_SHA256",
                 "FFMPEG_MAC_SHA256", "FFMPEG_WIN_SHA256")
    CLAUS_URL = ("PYBS_URL", "FFMPEG_LINUX_URL", "APPIMAGETOOL_URL",
                 "FFMPEG_MAC_URL", "FFMPEG_WIN_URL")
    CLAUS_COMMIT = ("QM_VAMP_PLUGINS_COMMIT", "QM_DSP_COMMIT",
                    "VAMP_PLUGIN_SDK_COMMIT", "LIBSNDFILE_COMMIT")

    def _vars(self):
        """Llegeix el fitxer com ho faria bash (KEY=valor)."""
        valors = {}
        with open(self.RUTA, encoding="utf-8") as f:
            for linia in f:
                linia = linia.strip()
                if not linia or linia.startswith("#") or "=" not in linia:
                    continue
                clau, valor = linia.split("=", 1)
                valors[clau.strip()] = valor.strip().strip('"')
        return valors

    def test_te_les_claus(self):
        v = self._vars()
        for c in self.CLAUS_SHA + self.CLAUS_URL + self.CLAUS_COMMIT:
            self.assertIn(c, v, f"falta {c} a deps_fixades.env")

    def test_sha256_son_valids(self):
        v = self._vars()
        for c in self.CLAUS_SHA:
            self.assertRegex(v[c], r"^[0-9a-f]{64}$", f"{c} no és un SHA256")

    def test_commits_son_valids(self):
        v = self._vars()
        for c in self.CLAUS_COMMIT:
            self.assertRegex(v[c], r"^[0-9a-f]{40}$", f"{c} no és un commit")

    def test_urls_https_i_no_mobils(self):
        v = self._vars()
        for c in self.CLAUS_URL:
            self.assertTrue(v[c].startswith("https://"), f"{c} no és HTTPS")
            for mobil in ("continuous", "getrelease", "/latest/", "-release-"):
                self.assertNotIn(mobil, v[c], f"{c} encara és mòbil ({mobil})")

    def test_tag_lucide_fixat(self):
        self.assertRegex(self._vars()["LUCIDE_TAG"], r"^\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
