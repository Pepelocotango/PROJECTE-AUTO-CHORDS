# -*- mode: python ; coding: utf-8 -*-
# AutoChords-win.spec — empaquetat PyInstaller --onedir per a Windows x64.
#
# Construcció (a l'arrel del projecte, amb els binaris ja compilats):
#     pyinstaller --noconfirm --clean eines/AutoChords-win.spec
# -> dist/AutoChords/AutoChords.exe  (+ _internal/ amb tot)
#
# Requereix que abans s'hagin generat:
#   · vamp_host_local.exe                      (eines/compila_vamp_plugins.sh)
#   · nnls-chroma-win64-local/                 (idem)
#   · qm-vamp-plugins-win64-local/             (idem)
#   · portable/win-dlls/*.dll                  (idem; clausura de runtime)
#   · portable/bin/ffmpeg.exe                  (baixat al workflow)
#
# Nota: l'entry és eines/launcher_pyinstaller.py (no app/main.py), perquè resol
# el subprocés `acords_a_live.py` en mode congelat. Vegeu aquell fitxer.
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))

datas = [
    (os.path.join(ROOT, 'acords_a_live.py'), '.'),
    (os.path.join(ROOT, 'vamp_host_local.exe'), '.'),
    (os.path.join(ROOT, 'icones'), 'icones'),
    (os.path.join(ROOT, 'nnls-chroma-win64-local'), 'nnls-chroma-win64-local'),
    (os.path.join(ROOT, 'qm-vamp-plugins-win64-local'), 'qm-vamp-plugins-win64-local'),
    (os.path.join(ROOT, 'portable', 'bin', 'ffmpeg.exe'), os.path.join('portable', 'bin')),
]
# DLLs de runtime (libsndfile + còdecs + runtimes MinGW): al costat de l'exe,
# que és on Windows les busca quan s'executa vamp_host_local.exe.
_win_dlls = os.path.join(ROOT, 'portable', 'win-dlls')
if os.path.isdir(_win_dlls):
    for _dll in sorted(os.listdir(_win_dlls)):
        if _dll.lower().endswith('.dll'):
            datas.append((os.path.join(_win_dlls, _dll), '.'))

hiddenimports = [
    # Mòduls de primer nivell que viuen a app/ (main.py fa sys.path.insert).
    'ffmpeg', 'partitura', 'pipeline', 'postproc', 'theme', 'metronom', 'icones',
    # Paquet app (per si l'anàlisi estàtica no els veu tots).
    'app', 'app.main', 'app.visor', 'app.timeline', 'app.dialegs',
    'app.vamp_params', 'app.plataforma',
]

a = Analysis(
    [os.path.join(ROOT, 'eines', 'launcher_pyinstaller.py')],
    pathex=[ROOT, os.path.join(ROOT, 'app')],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt5.QtWebEngineWidgets', 'PyQt5.QtWebEngineCore', 'PyQt5.QtWebEngine',
        'PyQt5.QtQml', 'PyQt5.QtQuick', 'PyQt5.QtQuickWidgets', 'PyQt5.QtQuick3D',
        'PyQt5.Qt3DCore', 'PyQt5.QtCharts', 'PyQt5.QtDataVisualization',
        'PyQt5.QtBluetooth', 'PyQt5.QtNfc', 'PyQt5.QtSerialPort', 'PyQt5.QtSensors',
        'PyQt5.QtPositioning', 'PyQt5.QtLocation', 'PyQt5.QtWebSockets',
        'PyQt5.QtWebChannel', 'PyQt5.QtDesigner', 'PyQt5.QtHelp', 'PyQt5.QtTest',
        'tkinter',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AutoChords',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='AutoChords',
)
