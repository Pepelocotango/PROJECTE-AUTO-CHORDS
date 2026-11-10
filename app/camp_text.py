"""Camps de text de l'app amb l'inici sempre visible."""

from PyQt5.QtWidgets import QLineEdit


class CampText(QLineEdit):
    """`QLineEdit` que, si el text no hi cap, en mostra l'inici i no la fi."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCursorPosition(0)

    def setText(self, text):
        super().setText(text)
        self.setCursorPosition(0)
