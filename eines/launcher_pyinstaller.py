"""Punt d'entrada de l'executable de Windows (PyInstaller).

PyInstaller fa que `sys.executable` sigui aquest mateix `.exe`. L'app, però,
torna a invocar-se a si mateixa per executar `acords_a_live.py` (vegeu
`app/pipeline.run_acords_py`, que fa servir `plataforma.python_actual()`).

En mode congelat això reobriria la GUI una segona vegada. Aquest llançador
detecta aquest cas (el primer argument és la ruta a `acords_a_live.py`) i
l'executa **en el mateix procés** amb `runpy`, sense tocar `app/`.

A Linux/macOS aquest fitxer no s'usa: allà `sys.executable` és un intèrpret
real i el shim no cal.
"""
import os
import runpy
import sys


def _es_acords():
    """Cert si ens han cridat per fer l'equivalent a `python acords_a_live.py`."""
    if len(sys.argv) < 2:
        return False
    return os.path.basename(sys.argv[1]).lower() == "acords_a_live.py"


def _executa_acords():
    script = sys.argv[1]
    # acords_a_live.py fa servir sys.argv[1]=csv, [2]=bpm, [3]=bpb, [4]=offset
    sys.argv = [script] + sys.argv[2:]
    runpy.run_path(script, run_name="__main__")
    return 0


def main():
    if _es_acords():
        return _executa_acords()

    # En mode congelat, `app/` viu a `sys._MEIPASS`; assegurem que tant el
    # paquet `app` com els mòduls de primer nivell que hi conviuen
    # (`pipeline`, `theme`, `metronom`, `icones`...) siguin importables.
    base = os.path.dirname(os.path.abspath(__file__))
    for p in (base, os.path.join(base, "app")):
        if p not in sys.path:
            sys.path.insert(0, p)

    from app.main import main as app_main
    return app_main()


if __name__ == "__main__":
    raise SystemExit(main())
