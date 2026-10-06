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

# --- Timeline i clips -------------------------------------------------------
# ACTIU  = el clip que SONA (segueix el cursor)  -> fons tenyit suau.
# SELECCIONAT = el clip que has CLICAT            -> vora gruixuda i brillant.
# Son estats independents: un clip pot estar actiu i seleccionat alhora.
TL_BG = "#0f1218"
TL_LANE_BG_A = "#1a1d23"
TL_LANE_BG_B = "#15181d"
TL_LANE_DIVIDER = "#2a2f37"
TL_RULER_TEXT = "#c4d0e2"
TL_WAVEFORM = "#8ab4f8"
TL_CURSOR = "#ff6b6b"
TL_RULER_BG = "#10131a"
TL_SCENE_BG = "#0f0f10"
TL_GUIDE = "#ffd166"           # guia de snap / loop A-B
TL_GRID_MEASURE = "#55677f"    # linia de compas
TL_GRID_BEAT = "#3d4c60"       # linia de temps
TL_GRID_SUB = "#303a48"        # subdivisio
TL_WAVE_MID = "#2f3640"        # linia central de l'ona
CLIP_SECTION_BORDER = "#dfe7f5"
# Metrònom: color de l'estat activat (botó/acció)
METRO_ACTIU = "#ffd166"
CLIP_FILL = "#2e3844"          # clip normal
CLIP_BORDER = "#b8c7dc"
CLIP_TEXT = "#edf3ff"
CLIP_ACTIVE_FILL = "#1f5c3d"   # ACTIU: verd suau (sona)
CLIP_ACTIVE_BORDER = "#4ade80"
CLIP_ACTIVE_TEXT = "#eafff3"
CLIP_SELECTED_BORDER = "#38bdf8"   # SELECCIONAT: cian brillant
CLIP_SELECTED_WIDTH = 3
CLIP_HANDLE = "#5b8dd6"
CLIP_HANDLE_SELECTED = "#38bdf8"
SECTION_FILLS = ("#3a4655", "#475a70", "#5d6f82", "#70849a", "#8996aa")
SECTION_TEXT = "#edf3ff"


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
QPushButton#metro:checked {{ background: {METRO_ACTIU}; color: {BG}; }}
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
