"""Contracte de superfície de `app.timeline` (refactor F0).

Congela els noms re-exportats, la classe `TimelineView` i els mètodes que
fan servir `visor.py` i els tests. Serveix de xarxa de seguretat per a la
modularització de `timeline.py` (F2).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene: esborra els temporals en plegar

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest  # noqa: E402

from app import timeline  # noqa: E402

NOMS_REEXPORTATS = (
    "TimelineView", "ChordItem", "SectionItem", "RenameEditor",
    "WaveformLayer", "GridLayer", "BeatLayer", "RulerLayer",
    "TimeRulerLayer", "LaneBackground", "CursorLine", "TempoLayer",
    "MarcadorsLayer", "fmt_pos", "snap_time", "grid_levels",
    "CURSOR_COLOR", "CHORD_ACTIVE_FILL", "SELECTION_COLOR",
    "RULER_H",
)

METODES_TIMELINEVIEW = (
    # Dades i modes
    "set_data", "set_audio", "set_marcadors", "set_beats",
    "set_tempo_mode", "set_bpm_unit", "set_follow",
    # Cursor i zoom
    "set_position", "get_position", "zoom_in", "zoom_out", "zoom_full",
    "zoom_to", "zoom_selection", "ensure_cursor_visible",
    "_zoom_al_punt", "_set_view_range",
    # Geometria i snap
    "_temps_a_x", "_x_to_time", "_loop_mode_at", "snap", "set_snap",
    "_snap", "_snap_step", "nudge", "_nudge",
    # Selecció i rangs
    "select_clip", "selecciona", "toggle_selection", "extend_selection",
    "clear_selection", "keys_dins_rang", "keys_dins_marc",
    "rang_seleccio", "_bloc_del_gest", "_temps_item", "_trams_tempo",
    # Edició
    "_on_chord_time_changed", "_on_chord_end_changed",
    "_on_section_changed", "_open_rename", "_commit_rename",
    # Porta-retalls
    "copy_selection", "cut_selection", "paste_at_cursor",
    # Eina
    "set_tool",
)


class TestSuperficieTimeline(unittest.TestCase):
    def test_reexports(self):
        for nom in NOMS_REEXPORTATS:
            self.assertTrue(hasattr(timeline, nom), f"falta timeline.{nom}")

    def test_all_public(self):
        for nom in timeline.__all__:
            self.assertTrue(hasattr(timeline, nom), f"falta __all__: {nom}")

    def test_metodes_de_timelineview(self):
        for nom in METODES_TIMELINEVIEW:
            self.assertTrue(hasattr(timeline.TimelineView, nom),
                            f"falta TimelineView.{nom}")

    def test_timelineview_viu_al_modul(self):
        self.assertEqual(timeline.TimelineView.__module__, "app.timeline")

    def test_funcions_pures_importables(self):
        self.assertIsInstance(timeline.fmt_pos(0.0, True, 120.0, 4), str)
        self.assertIsInstance(
            timeline.snap_time(1.0, True, 120.0, 4, 10.0), float)
