"""Tancament intel·ligent: detectar canvis (ajustos del projecte I edicions de la
cançó), avisar NOMÉS si n'hi ha, oferir Desa/Descarta/Cancel·la, i MAI tancar si
el desat falla.
"""
import os
import sys
import tempfile
import unittest
import wave
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtWidgets import QFileDialog, QMessageBox  # noqa: E402

from app import config  # noqa: E402
from app import main as app_main  # noqa: E402

_VIVES = []


def _wav(dur=4.0):
    d = tempfile.mkdtemp()
    ruta = os.path.join(d, "tema.wav")
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * int(44100 * dur))
    return ruta


def _finestra_amb_projecte():
    f = app_main.Finestra()
    _VIVES.append(f)
    # Silencia els avisos (alguns són modals i encallarien el test).
    f.avisa = lambda *a, **k: None
    f.avisa_info = lambda *a, **k: None
    f.avisa_crit = lambda *a, **k: None
    wav = _wav()
    acproj = os.path.join(os.path.dirname(wav), "P.acproj")
    with patch.object(QFileDialog, "getOpenFileName", return_value=(wav, "")), \
            patch.object(QFileDialog, "getSaveFileName", return_value=(acproj, "")):
        f.tria_wav()
    return f


def _tanca(f):
    """Tanca l'app netejant el «dirty» (evita el prompt real als tests)."""
    f.dirty = False
    f.close()


def _clic_prompt(f, etiqueta):
    """Simula clicar el botó `etiqueta` del prompt de tancament."""
    capt = {}
    o_add, o_exec, o_cb = (QMessageBox.addButton, QMessageBox.exec_,
                           QMessageBox.clickedButton)

    def fake_add(self, *a):
        b = o_add(self, *a)
        try:
            capt[b.text()] = b
        except Exception:  # noqa: BLE001
            pass
        return b
    QMessageBox.addButton = fake_add
    QMessageBox.exec_ = lambda self: 0
    QMessageBox.clickedButton = lambda self: capt.get(etiqueta)
    try:
        # Als tests la plataforma és `offscreen` i l'app HI SALTA els diàlegs a
        # posta (un modal fa «access violation» a Windows; vegeu `_interactiu`).
        # Aquí simulem un entorn interactiu per provar la lògica del prompt.
        with patch.object(f, "_interactiu", return_value=True):
            return f._confirma_descartar()
    finally:
        QMessageBox.addButton, QMessageBox.exec_, QMessageBox.clickedButton = (
            o_add, o_exec, o_cb)


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = app_main.QApplication.instance() or app_main.QApplication([])

    def setUp(self):
        self.td = tempfile.mkdtemp()
        self._p = patch.object(config, "DADES_DIR", self.td)
        self._p.start()

    def tearDown(self):
        self._p.stop()
        try:
            import _qt_neteja
        except ImportError:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import _qt_neteja
        ws, _VIVES[:] = _VIVES[:], []
        for w in ws:
            w.dirty = False
        _qt_neteja.tanca_i_destrueix(*ws)


class TestTancamentIntel·ligent(_Base):
    def test_acabat_d_obrir_esta_net(self):
        f = _finestra_amb_projecte()
        self.assertFalse(f._te_canvis(), "acabat d'obrir no hi ha canvis")
        _tanca(f)

    def test_editar_la_canco_marca_canvis(self):
        f = _finestra_amb_projecte()
        f.visor_ref._afegeix_acord(1.0, "G")
        f.visor_ref._desa_i_regenera()          # edició → senyal `canvis`
        self.assertTrue(f._te_canvis(),
                        "una edició de la cançó ha de marcar el projecte")
        self.assertTrue(f.windowTitle().endswith("*"))
        _tanca(f)

    def test_desa_retorna_ok_i_net(self):
        f = _finestra_amb_projecte()
        f.visor_ref._afegeix_acord(1.0, "G")
        f.visor_ref._desa_i_regenera()
        self.assertTrue(f._desa_projecte())
        self.assertFalse(f._te_canvis())
        _tanca(f)

    def test_desa_fallit_retorna_fals(self):
        f = _finestra_amb_projecte()
        f._marca_dirty()
        with patch.object(type(f.projecte), "desa",
                          side_effect=OSError("disc ple")):
            self.assertFalse(f._desa_projecte())
        _tanca(f)

    def test_prompt_desa_fallit_no_continua(self):
        f = _finestra_amb_projecte()
        f._marca_dirty()
        with patch.object(f, "_desa_projecte", return_value=False):
            self.assertFalse(_clic_prompt(f, "Desa"),
                             "si el desat falla, NO s'ha de continuar")
        _tanca(f)

    def test_prompt_descarta_i_cancela(self):
        f = _finestra_amb_projecte()
        f._marca_dirty()
        self.assertTrue(_clic_prompt(f, "Descarta"))
        f._marca_dirty()
        self.assertFalse(_clic_prompt(f, "Cancel·la"))
        _tanca(f)

    def test_close_net_tanca_sense_prompt(self):
        f = _finestra_amb_projecte()
        with patch.object(f, "_confirma_descartar") as p:
            _tanca(f)
        p.assert_not_called()                   # net → cap prompt
        self.assertFalse(f.isVisible())

    def test_offscreen_no_obre_cap_dialeg_modal(self):
        """A la plataforma `offscreen` (tests i CI) les confirmacions NO han
        d'obrir cap `QMessageBox` modal: a Windows fa «access violation» (el
        crash que va tombar el CI). Han de respondre amb el valor segur."""
        f = _finestra_amb_projecte()
        f._marca_dirty()
        with patch.object(QMessageBox, "exec_") as m:
            self.assertTrue(f._pot_descartar())     # continua sense preguntar
            m.assert_not_called()
        _tanca(f)


def tearDownModule():
    try:
        import _qt_neteja
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _qt_neteja
    _qt_neteja.processa_esborrats()


if __name__ == "__main__":
    unittest.main()
