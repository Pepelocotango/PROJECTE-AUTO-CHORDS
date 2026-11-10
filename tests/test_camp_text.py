"""Tests — Camps de text que mostren l'inici del contingut."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication  # noqa: E402

from app.camp_text import CampText  # noqa: E402

_app = QApplication.instance() or QApplication([])


class TestCampText(unittest.TestCase):
    def test_mostra_l_inici_en_construir(self):
        camp = CampText("123456789.000")
        self.assertEqual(camp.cursorPosition(), 0)

    def test_mostra_l_inici_despres_de_set_text(self):
        camp = CampText()
        camp.setText("123456789.000")
        self.assertEqual(camp.cursorPosition(), 0)
        self.assertEqual(camp.text(), "123456789.000")


if __name__ == "__main__":
    unittest.main()
