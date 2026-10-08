#!/usr/bin/env python3
"""Development launcher for the PyQt app.

Default behavior: run the app once without auto-reload.
Optional behavior: use --watch to restart automatically when Python files change.
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / "app"


def _crea_handler(launcher):
    """Handler de `watchdog` (import LAZY: només cal quan s'usa --watch).

    Així `dev_reload.py` funciona sense tenir `watchdog` instal·lat si no
    es demana l'auto-reload.
    """
    from watchdog.events import FileSystemEventHandler

    class AppRestartHandler(FileSystemEventHandler):
        def __init__(self, launcher):
            self.launcher = launcher

        def on_any_event(self, event):
            if event.is_directory:
                return
            if not event.src_path.endswith(".py"):
                return
            path = Path(event.src_path)
            if path.is_relative_to(ROOT):
                self.launcher.restart()

    return AppRestartHandler(launcher)


class AppLauncher:
    def __init__(self):
        self.process = None
        self._pending_restart = False

    def start(self):
        if self.process and self.process.poll() is None:
            return
        print("\n[dev] starting Auto Chords...")
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        self.process = subprocess.Popen(
            [sys.executable, "-m", "app.main"],
            cwd=str(ROOT),
            env=env,
            stdout=None,
            stderr=None,
        )

    def stop(self):
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                self.process.kill()
                self.process.wait(timeout=5)
        self.process = None

    def restart(self):
        if self._pending_restart:
            return
        self._pending_restart = True
        time.sleep(0.2)
        try:
            self.stop()
            self.start()
            print("[dev] restarted")
        finally:
            self._pending_restart = False


def main():
    parser = argparse.ArgumentParser(description="Launch Auto Chords for development.")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="watch Python files under app/ and auto-restart when they change",
    )
    args = parser.parse_args()

    launcher = AppLauncher()

    if args.watch:
        try:
            from watchdog.observers import Observer
        except ImportError:
            sys.exit("[dev] falta el paquet 'watchdog' per a --watch: "
                     "pip install watchdog")
        handler = _crea_handler(launcher)
        observer = Observer()
        for path in (ROOT / "app",):
            observer.schedule(handler, str(path), recursive=True)
        observer.start()
        print(f"[dev] watching: {APP_DIR} (auto-reload enabled)")
    else:
        observer = None
        print("[dev] auto-reload disabled; run with --watch to enable it")

    launcher.start()

    try:
        while True:
            if launcher.process and launcher.process.poll() is not None:
                if args.watch:
                    print("[dev] app exited; waiting for file changes...")
                else:
                    print("[dev] app exited")
                    break
                launcher.process = None
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[dev] stopping...")
    finally:
        if observer is not None:
            observer.stop()
            observer.join(timeout=3)
        launcher.stop()


if __name__ == "__main__":
    main()
