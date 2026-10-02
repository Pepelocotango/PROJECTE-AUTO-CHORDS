# Paleta simple centralitzada, amb 4 colors bàsics:
# 1) gris quasi negre
# 2) gris fosc
# 3) gris clar
# 4) blanc

BG = "#0f0f10"
BG_2 = "#17181a"
PANEL = "#1d1f22"
SURFACE = "#2a2c30"
SURFACE_2 = "#3a3d42"
BORDER = "#4d5056"
BORDER_SOFT = "#676b71"
TEXT = "#f3f4f6"
TEXT_SOFT = "#dfe3ea"
MUTED = "#a7acb5"
PRIMARY = "#dfe3ea"
PRIMARY_DARK = "#b8bec8"
PRIMARY_LIGHT = "#ffffff"
ACCENT = "#dfe3ea"
WARNING = "#dfe3ea"
DANGER = "#dfe3ea"
DISABLED = "#2f3238"


def app_stylesheet():
    return f"""
QWidget {{
    background: {BG};
    color: {TEXT};
    font-size: 13px;
}}
QMainWindow, QDockWidget {{
    background: {BG};
    color: {TEXT};
}}
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 10px;
    font-weight: 600;
    color: {TEXT};
    background: {BG_2};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    color: {TEXT_SOFT};
}}
QLabel {{
    color: {TEXT};
}}
QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QListWidget, QSlider {{
    background: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 8px;
}}
QTextEdit#log {{
    font-family: monospace;
    font-size: 12px;
}}
QPushButton {{
    background: {PRIMARY_LIGHT};
    color: {BG};
    border: 1px solid {PRIMARY_DARK};
    border-radius: 7px;
    padding: 7px 14px;
    font-weight: 700;
}}
QPushButton:hover {{
    background: {PRIMARY};
    color: {BG};
}}
QPushButton:pressed {{
    background: {PRIMARY_DARK};
    color: {TEXT};
}}
QPushButton:disabled {{
    background: {DISABLED};
    color: {MUTED};
    border: 1px solid {BORDER};
}}
QPushButton#secundari {{
    background: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    font-weight: 500;
}}
QPushButton#secundari:hover {{
    background: {SURFACE_2};
}}
QProgressBar {{
    border: 1px solid {BORDER};
    border-radius: 5px;
    background: {SURFACE};
    color: {TEXT};
    height: 14px;
}}
QProgressBar::chunk {{
    background: {PRIMARY_LIGHT};
}}
QSlider::groove:horizontal {{
    background: {SURFACE_2};
    height: 6px;
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {PRIMARY_LIGHT};
    border: 1px solid {PRIMARY_DARK};
    width: 14px;
    margin: -4px 0;
    border-radius: 7px;
}}
QToolTip {{
    background: {BG_2};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 6px 8px;
    border-radius: 5px;
}}
"""


def visor_stylesheet():
    return f"""
QWidget {{
    background: {BG};
    color: {TEXT};
}}
QMainWindow {{ background: {BG}; }}
QPushButton {{
    background: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    font-weight: 600;
}}
QPushButton:hover {{ background: {SURFACE_2}; }}
QPushButton:pressed {{ background: {BORDER_SOFT}; }}
QPushButton:checked {{ background: {PRIMARY_LIGHT}; color: {BG}; }}
QPushButton:disabled {{ background: {DISABLED}; color: {MUTED}; }}
QListWidget, QTextEdit, QSlider, QLabel {{
    background: {PANEL};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
}}
QSlider::handle:horizontal {{ background: {PRIMARY_LIGHT}; border: 1px solid {PRIMARY_DARK}; }}
QSlider::groove:horizontal {{ background: {SURFACE_2}; height: 6px; }}
QToolTip {{
    background: {BG_2};
    color: {TEXT};
    border: 1px solid {PRIMARY};
    padding: 6px;
}}
"""
