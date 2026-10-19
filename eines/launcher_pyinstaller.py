"""Punt d'entrada de l'executable congelat (PyInstaller, Windows i macOS).

En mode congelat, `app/` viu a `sys._MEIPASS`; assegurem que tant el paquet
`app` com els mòduls de primer nivell que hi conviuen siguin importables abans
d'arrencar la finestra principal.
"""
import os
import sys


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    for p in (base, os.path.join(base, "app")):
        if p not in sys.path:
            sys.path.insert(0, p)

    from app.main import main as app_main
    return app_main()


if __name__ == "__main__":
    raise SystemExit(main())
