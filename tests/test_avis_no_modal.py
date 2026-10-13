"""Els avisos de l'app NO poden encallar el pont MCP.

Bug (OC-6/367, nota a): l'export i l'analitza mostren un `QMessageBox` **modal**
que bloqueja el fil de Qt fins que algú el tanca. Si l'acció la dispara una
crida MCP (p. ex. `ac_export_wav`), el pont queda **encallat** i l'agent no rep
mai la resposta.

Fix: `main.Finestra._avis()` — amb el pont actiu (`w.mcp_actiu`, que posa
`mcp_bridge.activa_pont`) l'avís s'ensenya **no modal**, s'auto-tanca al cap de
10 s i el text queda a `ultim_avis` perquè el pont el retorni. Sense pont, el
comportament és el de sempre (modal).
"""
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from unittest.mock import patch  # noqa: E402

import PyQt5.QtWidgets as QW  # noqa: E402
from PyQt5.QtCore import Qt  # noqa: E402

from app import mcp_bridge  # noqa: E402
from app import main as app_main  # noqa: E402


def _finestra():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "t.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * 5)
    f = app_main.Finestra()
    f.wav_edit.setText(wav)
    f._carrega_visor(wav)
    return f


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QW.QApplication.instance() or QW.QApplication([])


class TestAvisSensePont(_Base):
    def test_sense_pont_es_modal_com_sempre(self):
        w = _finestra()
        with patch.object(QW.QMessageBox, "warning") as m:
            w.avisa("Títol", "missatge")
        self.assertTrue(m.called, "sense pont ha de ser modal (de sempre)")
        self.assertEqual(w.ultim_avis, "missatge")


class TestAvisAmbPont(_Base):
    def test_amb_pont_no_es_modal_i_queda_registrat(self):
        w = _finestra()
        w.mcp_actiu = True
        vist = {}
        with patch.object(QW.QMessageBox, "warning") as modal, \
                patch.object(QW.QMessageBox, "show",
                             lambda self: vist.update(box=self)):
            w.avisa("Títol", "missatge")
        self.assertFalse(modal.called, "amb el pont NO hi pot haver modal")
        self.assertEqual(w.ultim_avis, "missatge")
        self.assertIn("box", vist, "s'hauria d'haver ensenyat (no modal)")
        self.assertEqual(vist["box"].windowModality(), Qt.NonModal)

    def test_activa_pont_marca_mcp_actiu(self):
        w = _finestra()
        self.assertFalse(w.mcp_actiu)
        pont = mcp_bridge.activa_pont(w)
        self.assertTrue(w.mcp_actiu,
                        "activar el pont ha de desactivar els modals")
        if pont is not None:
            pont.tanca()


class TestExportMCPNoBloqueja(_Base):
    def test_l_export_amb_pont_torna_i_reporta_l_avis(self):
        """Si l'export vol avisar, la crida MCP TORNA (no s'encalla) i l'avís
        arriba a l'agent."""
        w = _finestra()
        w.mcp_actiu = True
        ctx = mcp_bridge._Context(w)
        with patch.object(QW.QMessageBox, "warning") as modal, \
                patch.object(QW.QMessageBox, "show", lambda self: None):
            r = mcp_bridge._op_export_wav(ctx, {})
        self.assertFalse(modal.called, "no pot haver-hi modal amb el pont")
        self.assertTrue(r.get("ok"))
        self.assertIn("avis", r, "l'avís hauria d'arribar a l'agent")

    def test_el_status_mostra_el_darrer_avis(self):
        w = _finestra()
        w.mcp_actiu = True
        w.avisa("Títol", "avís de prova")
        r = mcp_bridge._op_status(mcp_bridge._Context(w), {})
        self.assertEqual(r.get("avis"), "avís de prova")


if __name__ == "__main__":
    unittest.main()
