#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Llançador de l'app AUTO CHORDS **amb el pont MCP actiu**.

Fa exactament el mateix que `python -m app.main`, però enganxa el pont MCP
(`app/mcp_bridge.py`) a la finestra principal **sense tocar `app/main.py`**:
embolcalla la classe `Finestra` amb una subclasse que activa el pont.

Ús:
    eines/mcp_auto_chords_launcher.py
    AUTO_CHORDS_MCP.sh

⚠️ Només una instància de l'app alhora (bloqueig d'instància única de l'app).
Arrencar-la per aquí habilita les eines MCP `ac_*`; arrencar-la pel llançador
normal (`AUTO_CHORDS.sh`) la deixa exactament com sempre (pont inactiu).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import app.main as main_mod            # noqa: E402
from app import mcp_bridge             # noqa: E402


class _FinestraAmbPont(main_mod.Finestra):
    """Subclasse mínima: activa el pont MCP en crear-se la finestra."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            mcp_bridge.activa_pont(self)
        except Exception as e:  # noqa: BLE001 — el pont mai ha de tombar l'app
            self.logger.exception("No s'ha pogut activar el pont MCP: %s", e)


def main():
    # `main()` de l'app fa servir la classe global `Finestra`; la substituïm
    # abans de cridar-lo. No s'edita cap fitxer de l'app.
    main_mod.Finestra = _FinestraAmbPont
    return main_mod.main()


if __name__ == "__main__":
    raise SystemExit(main())
