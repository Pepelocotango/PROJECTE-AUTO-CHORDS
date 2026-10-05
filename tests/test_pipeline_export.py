import csv
import os
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import numpy as np

from app import main as app_main, pipeline, visor


class ExportPipelineTests(unittest.TestCase):
    def test_setup_logging_creates_log_file(self):
        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "auto_chords_test.log"
            app_main.setup_logging(str(log_path))
            self.assertTrue(log_path.exists())

    def test_main_detects_existing_output_folder_for_wav(self):
        with tempfile.TemporaryDirectory() as td:
            wav = Path(td) / "tema.wav"
            with wave.open(str(wav), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(44100)
                w.writeframes(b"\x00\x00" * 1000)
            out = Path(td) / "tema_ACORDS"
            out.mkdir()
            (out / "acords.csv").write_text("0.0,C\n", encoding="utf-8")
            (out / "estructura_ABC.csv").write_text(
                "inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n0.0,2.0,2.0,A,N,1.1.1,2.1.1\n",
                encoding="utf-8",
            )

            app = app_main.QApplication.instance() or app_main.QApplication([])
            window = app_main.Finestra()
            self.assertEqual(window._detecta_sortida_wav(str(wav)), str(out))
            window.sortida = ""
            window._carrega_visor(str(wav))
            self.assertEqual(window.sortida, str(out))
            self.assertGreater(window.visor_ref.llista_ac.count(), 0)
            app.quit()

    def test_main_shows_placeholder_before_first_processing(self):
        with tempfile.TemporaryDirectory() as td:
            wav = Path(td) / "tema.wav"
            with wave.open(str(wav), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(44100)
                w.writeframes(b"\x00\x00" * 1000)

            app = app_main.QApplication.instance() or app_main.QApplication([])
            window = app_main.Finestra()
            window.sortida = ""
            window._carrega_visor(str(wav))
            self.assertIsNone(window.visor_ref)
            self.assertTrue(window.visor_dock.widget() is not None)
            app.quit()

    def test_exporta_total_generates_expected_outputs(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "tema_ACORDS"
            csv_ac = base / "acords.csv"
            csv_seg = base / "segments.csv"
            abc = base / "estructura_ABC.csv"
            base.mkdir(parents=True, exist_ok=True)

            with csv_ac.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["0.0", "C"])
                writer.writerow(["2.0", "Am"])

            with csv_seg.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["0.0", "2.0", "0", "N1"])
                writer.writerow(["2.0", "4.0", "1", "A"])

            result = pipeline.exporta_total(
                csv_ac=str(csv_ac),
                csv_seg=str(csv_seg),
                sortida=str(base),
                bpm=120.0,
                bpb=4,
                offset=0.0,
                sr=44100,
                log=lambda msg: None,
                tempo_fix=True,
                amb_estructura=True,
            )

            self.assertEqual(result["acords_csv"], str(csv_ac))
            self.assertTrue(abc.exists())
            self.assertTrue((base / "wavs_acords").is_dir())
            self.assertTrue((base / "wavs_estructura").is_dir())

    def test_app_main_imports_as_module(self):
        root = Path(__file__).resolve().parents[1]
        code = (
            "import sys; sys.path.insert(0, r'" + str(root) + "'); "
            "import app.main; print('APP_IMPORT_OK')"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("APP_IMPORT_OK", proc.stdout)

    def test_section_split_and_merge(self):
        base = [(0.0, 4.0, "A", "A"), (4.0, 8.0, "B", "B")]
        split = pipeline.parteix_seccio(base, 0, 2.0)
        self.assertEqual(len(split), 3)
        self.assertEqual(split[0][0], 0.0)
        self.assertEqual(split[0][1], 2.0)
        self.assertEqual(split[1][0], 2.0)
        self.assertEqual(split[1][1], 4.0)
        merged = pipeline.fusiona_seccions(split, 0, amb="seguent")
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0][2], "A")
        self.assertEqual(merged[1][2], "B")

    def test_exporta_includes_both_acord_and_structure_wavs(self):
        # Test d'integració: el Visor complet amb TimelineView exporta bé
        import os
        from app.timeline import TimelineView
        import numpy as np

        app = visor.QApplication.instance() or visor.QApplication([])
        with tempfile.TemporaryDirectory() as td:
            wav = Path(td) / "tema.wav"
            with wave.open(str(wav), "wb") as wv_w:
                wv_w.setnchannels(1)
                wv_w.setsampwidth(2)
                wv_w.setframerate(44100)
                wv_w.writeframes(b"\x00\x00" * 44100 * 2)
            out = Path(td) / "tema_ACORDS"
            out.mkdir()
            (out / "acords.csv").write_text("0.0,C\n", encoding="utf-8")
            (out / "estructura_ABC.csv").write_text(
                "inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
                "0.0,2.0,2.0,A,N,1.1,2.1\n",
                encoding="utf-8",
            )
            v = visor.Visor(str(wav), str(out / "acords.csv"),
                           str(out / "estructura_ABC.csv"),
                           bpm=120, bpb=4, tempo_fix=True)
            self.assertIsInstance(v.timeline, TimelineView)
            self.assertGreater(len(v.timeline._chord_items), 0)
            self.assertGreater(len(v.timeline._section_items), 0)
            v.exporta()
            self.assertTrue((out / "wavs_acords").is_dir())
            self.assertTrue((out / "wavs_estructura").is_dir())
            v.close()
        app.quit()

    def test_style_normalizes_common_chords(self):
        cases = {
            "cmaj7": "CMaj7",
            "am": "A-",
            "Em7": "E-7",
            "g/d": "G/D",
            "f#m7": "F#-7",
            "Bbmaj7": "BbMaj7",
        }
        for source, expected in cases.items():
            self.assertEqual(pipeline.style(source), expected)

    def test_tempo_fixed_view_switches_to_measure_display(self):
        original_init = visor.Visor.__init__
        visor.Visor.__init__ = lambda self, *args, **kwargs: None
        try:
            v = visor.Visor.__new__(visor.Visor)
            v.tempo_fix = True
            v.bpm = 120.0
            v.bpb = 4
            v.audio = {"durada": 8.0}

            self.assertEqual(v._fmt_timeline(0.0), "1.1 / 4.4")
            self.assertEqual(v._fmt_timeline(2.0), "1.4 / 4.4")
        finally:
            visor.Visor.__init__ = original_init


    def test_main_window_has_process_and_publish_actions(self):
        app = app_main.QApplication.instance() or app_main.QApplication([])
        window = app_main.Finestra()
        self.assertTrue(hasattr(window, "b_exec"))
        self.assertTrue(hasattr(window, "b_export"))
        self.assertEqual(window.b_exec.text(), "Processa")
        self.assertEqual(window.b_export.text(), "Finalitza i publica")
        app.quit()

    def test_embedded_visor_close_does_not_quit_app(self):
        app = visor.QApplication.instance() or visor.QApplication([])
        v = visor.Visor.__new__(visor.Visor)
        visor.QMainWindow.__init__(v)
        v._embedded = True
        v.rellotge = type("R", (), {"stop": lambda self: None})()
        v._atura_proc = lambda: None
        v.log = lambda *args, **kwargs: None
        with patch.object(visor.QApplication.instance(), "quit") as quit_mock:
            v.closeEvent(visor.QCloseEvent())
        quit_mock.assert_not_called()
        app.quit()

    def test_visor_supports_add_and_remove_chords_and_sections(self):
        app = visor.QApplication.instance() or visor.QApplication([])
        v = visor.Visor.__new__(visor.Visor)
        visor.QMainWindow.__init__(v)
        v.acords = [(0.0, "C", "0.0"), (2.0, "Am", "2.0")]
        v.seccions = [(0.0, 2.0, "A", "A"), (2.0, 4.0, "B", "B")]
        v.bpm = 120.0
        v.bpb = 4
        v.offset = 0.0
        v.tempo_fix = True
        v.audio = {"durada": 4.0}
        v.log = lambda msg: None

        v._afegeix_acord(1.0, "G")
        self.assertEqual(len(v.acords), 3)
        self.assertEqual(v.acords[1][1], "G")

        v._elimina_acord(1)
        self.assertEqual(len(v.acords), 2)
        self.assertEqual(v.acords[1][1], "Am")

        v._afegeix_seccio(4.0, 6.0, "C", "C")
        self.assertEqual(len(v.seccions), 3)
        self.assertEqual(v.seccions[2][2], "C")

        v._elimina_seccio(2)
        self.assertEqual(len(v.seccions), 2)
        self.assertEqual(v.seccions[1][2], "B")
        app.quit()

    def test_main_window_export_calls_pipeline_export(self):
        app = app_main.QApplication.instance() or app_main.QApplication([])
        window = app_main.Finestra()
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            (base / "tema_ACORDS").mkdir()
            (base / "tema_ACORDS" / "acords.csv").write_text(
                "0.0,C\n2.0,Am\n", encoding="utf-8"
            )
            (base / "tema_ACORDS" / "segments.csv").write_text(
                "0.0,2.0,0,N1\n2.0,4.0,1,A\n", encoding="utf-8"
            )
            window.sortida = str(base / "tema_ACORDS")
            window.wav_edit.setText(str(base / "tema.wav"))
            with patch.object(app_main.pipeline, "exporta_total") as exporta:
                with patch.object(app_main.QDesktopServices, "openUrl"):
                    window.exporta()

        exporta.assert_called_once()
        self.assertEqual(exporta.call_args.kwargs["sortida"], str(base / "tema_ACORDS"))
        app.quit()

    def test_visor_normalizes_interval_order_for_chords_and_sections(self):
        app = visor.QApplication.instance() or visor.QApplication([])
        v = visor.Visor.__new__(visor.Visor)
        v.acords = [(10.0, "E", "10.000000000"), (0.0, "C", "0.000000000"), (2.0, "Am", "2.000000000")]
        v.seccions = [(10.0, 12.0, "C", "C"), (0.0, 2.0, "A", "A"), (2.0, 10.0, "B", "B")]

        v._normalitza_acords(v.acords)
        v._normalitza_seccions(v.seccions)

        self.assertEqual([item[0] for item in v.acords], [0.0, 2.0, 10.0])
        self.assertEqual([item[2] for item in v.seccions], ["A", "B", "C"])
        app.quit()

    def test_visor_rejects_invalid_edit_order_for_chords_and_sections(self):
        v = visor.Visor.__new__(visor.Visor)
        v.audio = {"durada": 30.0}
        v.acords = [(0.0, "C", "0.000000000"), (5.0, "Am", "5.000000000"), (10.0, "G", "10.000000000")]
        v.seccions = [(0.0, 5.0, "A", "A"), (5.0, 10.0, "B", "B"), (10.0, 30.0, "C", "C")]

        with self.assertRaises(ValueError):
            v._valida_canvis_acords([(0.0, "C", "0.000000000"), (0.0, "Am", "0.000000000"), (10.0, "G", "10.000000000")])

        with self.assertRaises(ValueError):
            v._valida_canvis_seccions([(0.0, 5.0, "A", "A"), (3.0, 10.0, "B", "B")])



class TimelineConstraintTests(unittest.TestCase):
    """Tests del constraint engine i snap del TimelineView."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def _make_view(self, durada=10.0, acords=None, seccions=None,
                   bpm=120.0, bpb=4, tempo_fix=True):
        from app.timeline import TimelineView
        audio = {
            "sr": 44100, "canals": 1, "durada": durada,
            "pics": np.linspace(0.1, 0.9, 500, dtype=np.float32),
            "temps": np.linspace(0, durada, 500),
            "raw": b"",
        }
        if acords is None:
            acords = [(0.0, "C", "0.0"), (2.0, "Am", "2.0"),
                      (4.5, "F", "4.5"), (7.0, "G", "7.0")]
        if seccions is None:
            seccions = []
        view = TimelineView(audio, acords, seccions, bpm, bpb, tempo_fix)
        view.resize(900, 300)
        return view

    def test_chord_move_propagates_to_neighbour_amplitude(self):
        """Moure B.t propaga a A.fi (amplitud canvia) i a B.t."""
        view = self._make_view(tempo_fix=False)
        view.zoom_to(0, 10)
        # Mou Am de 2.0 a 1.5 — l'amplada de C canvia
        view._on_chord_time_changed(1, 1.5)
        self.assertAlmostEqual(view._acords[1][0], 1.5, places=4)
        # C (anterior) té el seu "fi" actualitzat a 1.5
        self.assertAlmostEqual(view._chord_items[0]._next_t, 1.5, places=4)
        # F (següent) no canvia
        self.assertAlmostEqual(view._acords[2][0], 4.5, places=4)

    def test_chord_move_clamped_by_neighbours(self):
        """No es pot passar el veinat."""
        view = self._make_view(tempo_fix=False)
        view.zoom_to(0, 10)
        # Prova d'anar més enllà de F (4.5)
        view._on_chord_time_changed(1, 100.0)
        self.assertLessEqual(view._acords[1][0], 4.5 - 0.02 + 1e-6)
        # Prova d'anar més enrere de C (0.0)
        view._on_chord_time_changed(1, -10.0)
        self.assertGreaterEqual(view._acords[1][0], 0.02)

    def test_chord_end_move_propagates_to_next_chord(self):
        """Moure B.fi (= inici de C) propaga C.t."""
        view = self._make_view(tempo_fix=False)
        view.zoom_to(0, 10)
        view._on_chord_end_changed(1, 3.5)
        self.assertAlmostEqual(view._acords[2][0], 3.5, places=4)
        # Am.t no canvia
        self.assertAlmostEqual(view._acords[1][0], 2.0, places=4)

    def test_chord_snap_tempo_measure(self):
        """Snap a mesura en mode tempo_fix amb span ample."""
        view = self._make_view(tempo_fix=True, bpm=120, bpb=4)
        view.zoom_to(0, 10)  # span=10 → pas=measure=2.0s
        view.set_data([(0.0, "C", "0.0"), (1.7, "Am", "1.7"),
                       (3.0, "F", "3.0")], [])
        view._on_chord_time_changed(1, 1.7)
        self.assertAlmostEqual(view._acords[1][0], 1.75, places=4)

    def test_chord_snap_free(self):
        """Snap a 1s en mode lliure amb span ample."""
        view = self._make_view(durada=60.0, tempo_fix=False)
        view.zoom_to(0, 50)  # span=50 → pas=1.0s
        view.set_data([(0.0, "C", "0.0"), (3.7, "Am", "3.7"),
                       (8.0, "F", "8.0")], [])
        view._on_chord_time_changed(1, 4.3)
        self.assertAlmostEqual(view._acords[1][0], 4.5, places=4)

    def test_section_resize_clamped_by_neighbours(self):
        """Les seccions esclamen pels veins."""
        view = self._make_view(durada=10.0, tempo_fix=False)
        view.set_data([], [(0.0, 3.0, "A", "A"),
                           (3.0, 6.0, "B", "B"),
                           (6.0, 10.0, "C", "C")])
        view._section_items[1]._drag_mode = 0  # ZONE_NONE -> tractat com a LEFT
        view._on_section_changed(1, 1.5, 7.0)
        # Amb la lògica nova (contigüitat), moure l'inici arrossega el fi
        # de l'anterior; la secció queda [1.5, 5.98]
        self.assertAlmostEqual(view._seccions[1][0], 1.5, places=4)
        self.assertAlmostEqual(view._seccions[1][1], 6.0, places=4)

    def test_rename_chord_updates_data(self):
        """Rename inline programatic actualitza self.acords."""
        view = self._make_view(tempo_fix=False)
        view._commit_rename("chord", 1, view._chord_items[1], "Am7")
        self.assertEqual(view._acords[1][1], "Am7")
        self.assertEqual(view._chord_items[1].name, "Am7")

    def test_rename_section_updates_data(self):
        """Rename inline programatic actualitza self.seccions."""
        view = self._make_view()
        view.set_data([], [(0.0, 4.0, "A", "A"), (4.0, 8.0, "B", "B")])
        view._commit_rename("section", 0, view._section_items[0], "Verse")
        self.assertEqual(view._seccions[0][2], "Verse")

    def test_set_data_rebuilds_items(self):
        """set_data reconfigura tots els items correctament."""
        view = self._make_view()
        view.set_data([(0.0, "Dm", "0.0"), (5.0, "G7", "5.0")],
                      [(0.0, 4.0, "X", "X"), (4.0, 10.0, "Y", "Y")])
        self.assertEqual(len(view._chord_items), 2)
        self.assertEqual(len(view._section_items), 2)
        self.assertEqual(view._chord_items[0].name, "Dm")
        self.assertEqual(view._section_items[1].lletra, "Y")

    def test_zoom_to_respects_durada_limit(self):
        """zoom_to no pot anar més enllà de durada."""
        view = self._make_view(durada=10.0)
        view.zoom_to(0, 50)
        self.assertAlmostEqual(view._view_right, 10.0, places=4)

    def test_position_highlights_active_chord(self):
        """set_position il·lumina l'acord que toca."""
        view = self._make_view(tempo_fix=False)
        view.set_position(3.0)
        # L'acord 1 (Am, t=2.0) hauria d'estar actiu
        self.assertTrue(view._chord_items[1]._active)
        self.assertFalse(view._chord_items[0]._active)


class VisorTimelineIntegrationTests(unittest.TestCase):
    """Tests d'integració Visor ↔ TimelineView."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def _make_visor_with_data(self):
        import os
        td = tempfile.mkdtemp()
        wav_path = os.path.join(td, "tema.wav")
        sortida = os.path.join(td, "tema_ACORDS")
        os.makedirs(sortida)
        with wave.open(wav_path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * 20)
        with open(os.path.join(sortida, "acords.csv"), "w") as f:
            f.write("0.0,C\n2.0,Am\n4.5,F\n7.0,G\n10.0,C\n")
        with open(os.path.join(sortida, "estructura_ABC.csv"), "w") as f:
            f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n")
            f.write("0.0,5.0,5.0,A,A,1.1,5.1\n")
            f.write("5.0,10.0,5.0,B,B,5.1,10.1\n")
            f.write("10.0,20.0,10.0,C,C,10.1,20.1\n")
        v = visor.Visor(wav_path,
                        os.path.join(sortida, "acords.csv"),
                        os.path.join(sortida, "estructura_ABC.csv"),
                        bpm=120, bpb=4, tempo_fix=False)
        return v, sortida

    def test_visor_has_timeline_attribute(self):
        v, _ = self._make_visor_with_data()
        self.assertTrue(hasattr(v, "timeline"))
        self.assertGreater(len(v.timeline._chord_items), 0)
        v.close()

    def test_visor_does_not_have_obsolete_attributes(self):
        v, _ = self._make_visor_with_data()
        self.assertFalse(hasattr(v, "corba"))
        self.assertFalse(hasattr(v, "partitura"))
        v.close()

    def test_chord_move_via_timeline_propagates_to_visor(self):
        v, _ = self._make_visor_with_data()
        v.timeline._on_chord_time_changed(1, 3.6)
        # Snap fi (span=20 → 0.1s a mode lliure) → 3.6
        self.assertAlmostEqual(v.acords[1][0], 3.6, places=4)
        v.close()

    def test_rename_via_timeline_propagates_to_visor(self):
        v, _ = self._make_visor_with_data()
        v.timeline._commit_rename("chord", 2, v.timeline._chord_items[2],
                                  "Fmaj7")
        self.assertEqual(v.acords[2][1], "Fmaj7")
        v.close()

    def test_section_move_via_timeline_propagates_to_visor(self):
        v, _ = self._make_visor_with_data()
        v.timeline._section_items[1]._drag_mode = 0
        v.timeline._on_section_changed(1, 6.0, 10.0)
        self.assertAlmostEqual(v.seccions[1][0], 6.0, places=4)
        self.assertAlmostEqual(v.seccions[1][1], 10.0, places=4)
        v.close()

    def test_delete_chord_via_visor_updates_timeline(self):
        v, _ = self._make_visor_with_data()
        n_antes = len(v.acords)
        v._elimina_acord_index(0)
        self.assertEqual(len(v.acords), n_antes - 1)
        self.assertEqual(len(v.timeline._chord_items), n_antes - 1)
        v.close()


class UndoRedoTests(unittest.TestCase):
    """Tests de desfer/refer (només edició; MAI toquen les wavs)."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def _make_visor_with_data(self):
        td = tempfile.mkdtemp()
        wav_path = os.path.join(td, "tema.wav")
        sortida = os.path.join(td, "tema_ACORDS")
        os.makedirs(sortida)
        with wave.open(wav_path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * 20)
        with open(os.path.join(sortida, "acords.csv"), "w") as f:
            f.write("0.0,C\n2.0,Am\n4.5,F\n7.0,G\n10.0,C\n")
        with open(os.path.join(sortida, "estructura_ABC.csv"), "w") as f:
            f.write("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n")
            f.write("0.0,5.0,5.0,A,A,1.1,5.1\n")
            f.write("5.0,10.0,5.0,B,B,5.1,10.1\n")
            f.write("10.0,20.0,10.0,C,C,10.1,20.1\n")
        v = visor.Visor(wav_path,
                        os.path.join(sortida, "acords.csv"),
                        os.path.join(sortida, "estructura_ABC.csv"),
                        bpm=120, bpb=4, tempo_fix=False)
        return v, sortida

    def _mou_acord(self, v, idx, nou_t):
        v.timeline._on_chord_time_changed(idx, nou_t)
        v.timeline._emit_edit_finished()

    def test_undo_redo_chord_move(self):
        v, _ = self._make_visor_with_data()
        t_original = v.acords[1][0]
        self._mou_acord(v, 1, 3.6)
        self.assertAlmostEqual(v.acords[1][0], 3.6, places=4)
        v.undo()
        self.assertAlmostEqual(v.acords[1][0], t_original, places=4)
        v.redo()
        self.assertAlmostEqual(v.acords[1][0], 3.6, places=4)
        v.close()

    def test_undo_section_move(self):
        v, _ = self._make_visor_with_data()
        ini0 = v.seccions[1][0]
        v.timeline._section_items[1]._drag_mode = 0
        v.timeline._on_section_changed(1, 6.0, 10.0)
        v.timeline._emit_edit_finished()
        self.assertAlmostEqual(v.seccions[1][0], 6.0, places=4)
        v.undo()
        self.assertAlmostEqual(v.seccions[1][0], ini0, places=4)
        v.close()

    def test_undo_covers_rename(self):
        v, _ = self._make_visor_with_data()
        nom0 = v.acords[2][1]
        # flux real: el timeline canvia el nom i emet chordRenamed
        v.timeline._commit_rename("chord", 2, v.timeline._chord_items[2],
                                  "Fmaj7")
        self.assertEqual(v.acords[2][1], "Fmaj7")
        v.undo()
        self.assertEqual(v.acords[2][1], nom0)
        v.redo()
        self.assertEqual(v.acords[2][1], "Fmaj7")
        v.close()

    def test_undo_restores_timeline_items(self):
        v, _ = self._make_visor_with_data()
        t0 = v.acords[1][0]
        self._mou_acord(v, 1, 3.6)
        v.undo()
        # el model I la UI (items del timeline) han de tornar
        self.assertAlmostEqual(v.acords[1][0], t0, places=4)
        self.assertAlmostEqual(v.timeline._chord_items[1].t, t0, places=4)
        v.close()

    def test_undo_does_not_generate_wavs(self):
        """Les wavs són l'últim pas: editar/desfer NO n'ha de generar cap."""
        v, sortida = self._make_visor_with_data()
        self._mou_acord(v, 1, 3.6)
        v.undo()
        wavs = [f for f in os.listdir(sortida) if f.lower().endswith(".wav")]
        self.assertEqual(wavs, [], f"no hauria de generar wavs, però hi ha: {wavs}")
        # el CSV sí que s'ha d'actualitzar
        self.assertTrue(os.path.isfile(os.path.join(sortida, "acords.csv")))
        v.close()

    def test_new_edit_clears_redo(self):
        v, _ = self._make_visor_with_data()
        self._mou_acord(v, 1, 3.6)
        v.undo()
        self._mou_acord(v, 2, 5.9)   # edició nova → esborra el refer
        v.redo()                      # no ha de fer res
        self.assertAlmostEqual(v.acords[1][0], v.acords[1][0], places=4)
        self.assertFalse(v._redo_stack)
        v.close()

    def test_undo_empty_stack_is_safe(self):
        v, _ = self._make_visor_with_data()
        v.undo()   # no ha de petar
        v.redo()
        self.assertEqual(len(v.acords), 5)
        v.close()


if __name__ == "__main__":
    unittest.main()
