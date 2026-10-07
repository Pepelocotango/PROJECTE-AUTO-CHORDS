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

# Mode headless GLOBAL: sense això, les classes que creen QApplication abans
# de definir-lo (p.ex. ExportPipelineTests, que corre primer) poden penjar-se
# o avortar en un entorn sense pantalla.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app import main as app_main, pipeline, visor

# QMessageBox.information/warning/... son MODALS: bloquegen fins que algu
# clica OK. En un entorn sense pantalla (CI) aixo penja el test per sempre.
# Els neutralitzem per a TOTS els tests (test-only; no toca l'app).
for _m in ("information", "warning", "critical", "question", "about"):
    if hasattr(visor.QMessageBox, _m):
        setattr(visor.QMessageBox, _m, staticmethod(lambda *a, **k: None))


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

    def test_obre_wav_mostra_timeline_buit_abans_d_analitzar(self):
        """Reorg GUI (pas 2): obrir una WAV mostra l'ona i el timeline DE
        SEGUIDA, encara que no s'hagi analitzat (pistes buides).

        Abans (comportament d'assistent) es mostrava un placeholder fins que
        hi havia CSV. Ara el visor s'obre sempre amb la WAV."""
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
            self.assertIsNotNone(window.visor_ref)
            self.assertEqual(len(window.visor_ref.acords), 0)
            self.assertEqual(len(window.visor_ref.seccions), 0)
            self.assertIsNotNone(window.visor_widget)
            self.assertFalse(hasattr(window, "visor_dock"))
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
            v.exporta()   # els QMessageBox ja son no-ops (vegeu dalt)
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


    def test_main_window_te_les_accions_analitza_i_exporta(self):
        """Reorg GUI (pas 3): «Processa» passa a dir-se «Analitza» i
        «Finalitza i publica» → «Exporta» (ara són accions, no passos
        d'assistent)."""
        app = app_main.QApplication.instance() or app_main.QApplication([])
        window = app_main.Finestra()
        self.assertTrue(hasattr(window, "b_exec"))
        self.assertTrue(hasattr(window, "b_export"))
        self.assertEqual(window.b_exec.text(), "Analitza")
        self.assertEqual(window.b_export.text(), "Exporta")
        app.quit()

    def test_metro_desactivat_en_mode_lliure(self):
        """El metrònom només està disponible en mode BPM · compàs."""
        import tempfile, wave
        app = app_main.QApplication.instance() or app_main.QApplication([])
        window = app_main.Finestra()
        # sense visor NO hi ha metrònom disponible
        window._actualitza_metro_ui()
        self.assertFalse(window.b_metro.isEnabled())
        # amb una WAV carregada (mode BPM per defecte) → actiu
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "t.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100)
        window.wav_edit.setText(wav)
        window._carrega_visor(wav)
        self.assertTrue(window.b_metro.isEnabled())
        self.assertTrue(window.a_metro.isEnabled())
        # passar a Lliure → desactivat + desmarcat + tooltip
        window._toggle_metro(True)
        window._canvia_mode_temps(False)
        self.assertFalse(window.b_metro.isEnabled())
        self.assertFalse(window.vol_metro.isEnabled())
        self.assertFalse(window.a_metro.isEnabled())
        self.assertFalse(window.b_metro.isChecked())
        self.assertIn("BPM", window.b_metro.toolTip())
        app.quit()

    def test_volum_metro_per_defecte(self):
        from app import theme
        app = app_main.QApplication.instance() or app_main.QApplication([])
        window = app_main.Finestra()
        self.assertEqual(window.vol_metro.value(), 60)
        self.assertEqual(window.vol_metro.minimum(), 0)
        self.assertEqual(window.vol_metro.maximum(), 100)
        # i el color de l'estat activat viu al theme, no al visor
        self.assertTrue(hasattr(theme, "METRO_ACTIU"))
        app.quit()

    def test_analitza_desactivat_sense_wav(self):
        """Estat dinàmic: «Analitza» està desactivat fins que hi ha WAV."""
        app = app_main.QApplication.instance() or app_main.QApplication([])
        window = app_main.Finestra()
        self.assertFalse(window.b_exec.isEnabled())
        app.quit()

    def test_log_dock_amagat_per_defecte(self):
        """El log és un tauler inferior plegable, tancat per defecte."""
        app = app_main.QApplication.instance() or app_main.QApplication([])
        window = app_main.Finestra()
        self.assertTrue(hasattr(window, "log_dock"))
        self.assertFalse(window.log_dock.isVisible())
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

    def test_click_a_un_clip_mou_el_cursor(self):
        """Clic (sense drag) a un acord o una secció → cursor al seu inici.

        Regressió: el lambda del click capturava el valor antic d'ini/t i
        després d'un resize anava al lloc vell."""
        v, _ = self._make_visor_with_data()
        v.timeline.zoom_to(0, 20)
        casos = [("acord", v.timeline._chord_items, 1, 2.0),
                 ("secció", v.timeline._section_items, 1, 5.0)]
        for nom, items, idx, esperat in casos:
            v.timeline.set_position(0.0, emit=False)
            items[idx].clicked.emit()
            obtingut = v.timeline.get_position()
            self.assertAlmostEqual(obtingut, esperat, places=2,
                                   msg=f"{nom}: cursor {obtingut} != {esperat}")
        v.close()

    def test_delete_esborra_l_acord_seleccionat(self):
        """Delete esborra l'acord seleccionat i passa per l'undo."""
        from PyQt5.QtGui import QKeyEvent
        from PyQt5.QtCore import QEvent, Qt
        v, _ = self._make_visor_with_data()
        n = len(v.acords)
        v.timeline.select_clip("chord", 1)
        v.timeline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier))
        self.assertEqual(len(v.acords), n - 1)
        self.assertEqual(len(v._undo_stack), 1)
        v.undo()
        self.assertEqual(len(v.acords), n)      # undo el restaura
        v.close()

    def test_delete_seccio_el_vei_ocupa_l_espai(self):
        """En esborrar una secció, el previ s'estén (invariant de contigüitat)."""
        from PyQt5.QtGui import QKeyEvent
        from PyQt5.QtCore import QEvent, Qt
        v, _ = self._make_visor_with_data()
        n = len(v.seccions)
        fi_alliberada = v.seccions[1][1]
        v.timeline.select_clip("section", 1)
        v.timeline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier))
        self.assertEqual(len(v.seccions), n - 1)
        # el fi del previ ara arriba on arribava el de la seccio esborrada
        self.assertAlmostEqual(v.seccions[0][1], fi_alliberada, places=3)
        v.undo()
        self.assertEqual(len(v.seccions), n)
        v.close()

    def test_ctrl_d_duplica_acord_a_mig_cami(self):
        """Ctrl+D sobre un acord: s'insereix després, a mig camí (invariants)."""
        from PyQt5.QtGui import QKeyEvent
        from PyQt5.QtCore import QEvent, Qt
        v, _ = self._make_visor_with_data()
        n = len(v.acords)
        t0, t1 = v.acords[0][0], v.acords[1][0]
        v.timeline.select_clip("chord", 0)
        v.timeline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_D, Qt.ControlModifier))
        self.assertEqual(len(v.acords), n + 1)
        self.assertAlmostEqual(v.acords[1][0], (t0 + t1) / 2.0, places=3)
        self.assertEqual(v.acords[1][1], v.acords[0][1])   # mateix nom
        v.undo()
        self.assertEqual(len(v.acords), n)
        v.close()

    def test_ctrl_d_duplica_seccio_partint_la_durada(self):
        """Ctrl+D sobre una secció: es parteix en dues meitats."""
        from PyQt5.QtGui import QKeyEvent
        from PyQt5.QtCore import QEvent, Qt
        v, _ = self._make_visor_with_data()
        n = len(v.seccions)
        ini, fi = v.seccions[0][0], v.seccions[0][1]
        v.timeline.select_clip("section", 0)
        v.timeline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_D, Qt.ControlModifier))
        self.assertEqual(len(v.seccions), n + 1)
        mig = (ini + fi) / 2.0
        self.assertAlmostEqual(v.seccions[0][1], mig, places=3)
        self.assertAlmostEqual(v.seccions[1][0], mig, places=3)
        v.undo()
        self.assertEqual(len(v.seccions), n)
        v.close()

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


class MetronomTests(unittest.TestCase):
    """Generador de clics del metrònom (app/metronom.py) — numpy pur."""

    SR = 44100

    def _silenci(self, dur):
        return b"\x00\x00" * int(self.SR * dur)

    def _a_array(self, b):
        return np.frombuffer(b, dtype=np.int16).astype(np.int32)

    def _onsets(self, senyal, llindar=1000):
        """Inici de cada esclat de clic (separats per >50 ms de silenci)."""
        actiu = np.abs(senyal) > llindar
        idx = np.where(actiu)[0]
        if idx.size == 0:
            return np.array([])
        gaps = np.where(np.diff(idx) > 0.05 * self.SR)[0]
        inicis = np.concatenate(([idx[0]], idx[gaps + 1]))
        return inicis / self.SR

    def _freq(self, tros):
        sp = np.abs(np.fft.rfft(tros))
        return np.fft.rfftfreq(len(tros), 1.0 / self.SR)[np.argmax(sp)]

    def test_clics_a_120bpm_4_4(self):
        from app import metronom
        out = metronom.mescla_metronom(self._silenci(3.0), self.SR,
                                       0.0, 120.0, 4, volum=1.0)
        onsets = self._onsets(self._a_array(out))
        # 0, 0.5, 1.0, 1.5, 2.0, 2.5
        self.assertEqual(len(onsets), 6)
        for k, o in enumerate(onsets):
            self.assertAlmostEqual(o, k * 0.5, places=3)
        # accent (≈1500 Hz) als beats 0 i 4; la resta ≈1000 Hz
        n = int(self.SR * 0.02)
        f0 = self._freq(self._a_array(out)[int(0.0 * self.SR):int(0.0 * self.SR) + n])
        f2 = self._freq(self._a_array(out)[self.SR:self.SR + n])
        self.assertGreater(f0, 1300)
        self.assertLess(f2, 1100)

    def test_comencar_a_mig_compas_mante_el_patro(self):
        from app import metronom
        # comencem a t=2.5 s (beat 5). En 2 s de buffer hi cauen els beats
        # 5,6,7,8 -> a 0.0, 0.5, 1.0, 1.5 dins la rodanxa.
        out = metronom.mescla_metronom(self._silenci(2.0), self.SR,
                                       2.5, 120.0, 4, volum=1.0)
        onsets = self._onsets(self._a_array(out))
        self.assertEqual(len(onsets), 4)
        for k, o in enumerate(onsets):
            self.assertAlmostEqual(o, k * 0.5, places=3)
        # el beat 8 (t=4.0 → 1.5 dins la rodanxa) ha de ser accentuat
        arr = self._a_array(out)
        n = int(self.SR * 0.02)
        i = int(1.5 * self.SR)
        self.assertGreater(self._freq(arr[i:i + n]), 1300)

    def test_bpm_invalid_no_canvia_res(self):
        from app import metronom
        for bpm in (0, -5, float("nan"), float("inf")):
            base = self._silenci(1.0)
            out = metronom.mescla_metronom(base, self.SR, 0.0, bpm, 4, volum=1.0)
            self.assertEqual(out, base, f"bpm={bpm} hauria de no fer res")

    def test_volum_zero_no_canvia_l_audio(self):
        from app import metronom
        base = self._silenci(1.0)
        out = metronom.mescla_metronom(base, self.SR, 0.0, 120.0, 4, volum=0.0)
        self.assertEqual(out, base)

    def test_la_mescla_no_desborda(self):
        from app import metronom
        # audio a tope (32767) -> amb el clic NO ha de superar int16
        fort = (np.ones(self.SR, dtype=np.int16) * 32000).tobytes()
        out = metronom.mescla_metronom(fort, self.SR, 0.0, 120.0, 4, volum=1.0)
        arr = np.frombuffer(out, dtype=np.int16)
        self.assertTrue(np.all(arr <= 32767))
        self.assertTrue(np.all(arr >= -32768))

    def test_bpb_menor_que_1_es_tracta_com_1(self):
        from app import metronom
        out = metronom.mescla_metronom(self._silenci(1.1), self.SR,
                                       0.0, 120.0, 0, volum=1.0)
        # amb bpb=1 tots els beats son accents (cada 0.5 s)
        self.assertEqual(len(self._onsets(self._a_array(out))), 3)


class OffsetDosCampsTests(unittest.TestCase):
    """Offset amb DOS camps sincronitzats: compas.beat <-> segons."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def _finestra(self):
        import tempfile, wave
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "t.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * 30)
        ac = os.path.join(td, "t_ACORDS"); os.makedirs(ac)
        open(os.path.join(ac, "acords.csv"), "w").write("9.5,Am\n")
        window = app_main.Finestra()
        window.wav_edit.setText(wav)
        window._carrega_visor(wav)
        window.bpm.setText("101"); window.bpb.setText("4")
        window._aplica_parametres_temps()
        return window

    def test_compas_beat_a_segons(self):
        # a 101 BPM 4/4, compas 5 beat 1 = 16 temps x 0.594 = 9.50 s
        window = self._finestra()
        s = window._cb_a_secs("5.1")
        self.assertAlmostEqual(s, 16 * (60.0 / 101.0), places=4)
        window.close()

    def test_segons_a_compas_beat(self):
        window = self._finestra()
        self.assertEqual(window._secs_a_cb(16 * (60.0 / 101.0)), "5.1")
        self.assertEqual(window._secs_a_cb(0.0), "1.1")
        window.close()

    def test_els_dos_camps_queden_sincronitzats(self):
        window = self._finestra()
        # escrivim el compas.beat -> el camp de segons s'actualitza
        window.offset_cb.setText("5.1")
        window._offset_cb_canviat()
        # el camp de segons es desa amb 2 decimals (9.50495 -> 9.50)
        self.assertAlmostEqual(window._offset_val(), 16 * (60.0 / 101.0),
                               places=2)
        self.assertEqual(window.offset_cb.text(), "5.1")
        # i el regle posa el compas 1 alla
        self.assertEqual(
            __import__("app.timeline", fromlist=["fmt_pos"]).fmt_pos(
                window._offset_val(), True, 101, 4, window._offset_val()), "1.1")
        window.close()


class OffsetLlistesTests(unittest.TestCase):
    """Les llistes (etiquetes de compas) han de seguir l'offset."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def _finestra(self):
        import tempfile, wave
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "t.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * 30)
        ac = os.path.join(td, "t_ACORDS"); os.makedirs(ac)
        open(os.path.join(ac, "acords.csv"), "w").write("9.5,Am\n12.0,C\n")
        window = app_main.Finestra()
        window.wav_edit.setText(wav)
        window._carrega_visor(wav)
        return window

    def test_llistes_segueixen_l_offset(self):
        window = self._finestra()
        v = window.visor_ref
        window.bpm.setText("101")
        window._aplica_parametres_temps()
        # amb offset 0, l'acord de 9.5s surt com a compas 5
        self.assertTrue(v.llista_ac.item(0).text().startswith("5."))
        # amb offset 9.5, ha de sortir com a compas 1
        window.offset.setText("9.50")
        window._aplica_parametres_temps()
        self.assertTrue(v.llista_ac.item(0).text().startswith("1.1"),
                        v.llista_ac.item(0).text())
        self.assertTrue(v.llista_ac.item(1).text().startswith("2.1"),
                        v.llista_ac.item(1).text())
        window.close()


class TempoTests(unittest.TestCase):
    """Detecció de BPM (app/tempo.py) — autocorrelacio + comb, numpy pur."""

    SR = 22050

    def _wav_clics(self, td, bpm, dur=20.0, silenci_ini=3.0):
        """Genera una WAV amb clics periodics (i silenci inicial)."""
        import wave
        n = int(self.SR * dur)
        a = np.zeros(n, dtype=np.int16)
        periode = 60.0 / bpm
        t = silenci_ini
        while t < dur - 0.05:
            i = int(t * self.SR)
            llarg = int(self.SR * 0.02)
            env = np.exp(-8.0 * np.arange(llarg) / llarg).astype(np.float32)
            to = (np.sin(2 * np.pi * 1000 * np.arange(llarg) / self.SR) * env * 12000)
            a[i:i + llarg] = np.clip(a[i:i + llarg] + to.astype(np.int16),
                                     -32768, 32767)
            t += periode
        ruta = os.path.join(td, "clics.wav")
        with wave.open(ruta, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(self.SR)
            w.writeframes(a.tobytes())
        return ruta

    def test_detecta_bpm_sintetic(self):
        import tempfile
        from app import tempo
        for bpm in (101.0, 118.0, 120.0):
            with tempfile.TemporaryDirectory() as td:
                ruta = self._wav_clics(td, bpm)
                b = tempo.detecta_bpm(ruta, lambda m: None)
                self.assertIsNotNone(b, f"bpm {bpm}: None")
                self.assertLess(abs(b - bpm), 4.0,
                                f"bpm {bpm}: detectat {b}")

    def test_detecta_bpm_amb_silenci_inicial(self):
        """El silenci inicial NO ha de desviar la deteccio (cas real)."""
        import tempfile
        from app import tempo
        with tempfile.TemporaryDirectory() as td:
            ruta = self._wav_clics(td, 101.0, dur=25.0, silenci_ini=9.5)
            b = tempo.detecta_bpm(ruta, lambda m: None)
            self.assertLess(abs(b - 101.0), 4.0, f"detectat {b}")

    def test_detecta_bpm_silenci_retorna_none(self):
        import tempfile, wave
        from app import tempo
        with tempfile.TemporaryDirectory() as td:
            ruta = os.path.join(td, "silenci.wav")
            with wave.open(ruta, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(self.SR)
                w.writeframes(b"\x00\x00" * self.SR * 2)
            self.assertIsNone(tempo.detecta_bpm(ruta, lambda m: None))


class OffsetTests(unittest.TestCase):
    """L'offset (segon del compàs 1) ha d'aplicar-se a graella, clic i export."""

    SR = 44100

    def test_fmt_pos_amb_offset(self):
        from app.timeline import fmt_pos
        # a 120 BPM (beat=0.5s), offset=1.0 -> t=2.0 es el compas 1 beat 3
        self.assertEqual(fmt_pos(2.0, True, 120, 4, 1.0), "1.3")
        self.assertEqual(fmt_pos(2.0, True, 120, 4, 0.0), "2.1")

    def test_snap_time_amb_offset(self):
        from app.timeline import snap_time
        # offset=1.0 -> graella a 1.0, 1.125, 1.25... (setzena a 120 BPM)
        self.assertAlmostEqual(snap_time(1.13, True, 120, 4, 4.0, 1.0),
                               1.125, places=4)
        self.assertAlmostEqual(snap_time(1.13, True, 120, 4, 4.0, 0.0),
                               1.125, places=4)

    def test_pos_compas_amb_offset(self):
        from app.pipeline import pos_compas
        # 120 BPM: el compas 1 cau a t=offset; sense offset, a t=0
        self.assertEqual(pos_compas(0.0, 120, 4, False, 0.0), "1.1.1")
        self.assertEqual(pos_compas(1.0, 120, 4, False, 1.0), "1.1.1")
        self.assertEqual(pos_compas(2.0, 120, 4, False, 1.0), "1.3.1")

    def _onsets_metronom(self, out):
        arr = np.frombuffer(out, dtype=np.int16).astype(np.int32)
        idx = np.where(np.abs(arr) > 1000)[0]
        gaps = np.where(np.diff(idx) > 0.05 * self.SR)[0]
        return np.concatenate(([idx[0]], idx[gaps + 1])) / self.SR

    def test_metronom_amb_offset(self):
        from app import metronom
        base = b"\x00\x00" * int(self.SR * 2)
        out = metronom.mescla_metronom(base, self.SR, 0.0, 120.0, 4,
                                       volum=1.0, offset=1.0)
        onsets = self._onsets_metronom(out)
        # hi ha d'haver un clic JUST a l'offset (1.0)
        self.assertTrue(any(abs(o - 1.0) < 0.03 for o in onsets),
                        f"cap clic a l'offset: {onsets[:6]}")

    def test_count_in_abans_de_l_offset(self):
        """El silenci inicial s'omple amb el compte enrere (count-in)."""
        from app import metronom
        base = b"\x00\x00" * int(self.SR * 2)
        out = metronom.mescla_metronom(base, self.SR, 0.0, 120.0, 4,
                                       volum=1.0, offset=1.0)
        onsets = self._onsets_metronom(out)
        # hi ha clics ABANS de l'offset (count-in) i a l'offset
        self.assertTrue(any(o < 0.95 for o in onsets),
                        f"sense count-in: {onsets[:6]}")
        self.assertTrue(any(abs(o - 1.0) < 0.03 for o in onsets))

    def test_compas_negatiu_abans_de_l_offset(self):
        """Abans de l'offset (compas 1) la graella es negativa (count-in)."""
        from app.timeline import fmt_pos
        from app.pipeline import pos_compas
        # 120 BPM 4/4 -> compas = 2,0 s. Amb offset=3.0 (compas 1 a 3,0 s),
        # t=0 cau al compas -1 (beat 3).
        self.assertEqual(fmt_pos(0.0, True, 120, 4, 3.0), "-1.3")
        self.assertEqual(pos_compas(0.0, 120, 4, False, 3.0), "-1.3.1")
        # i el compas 1 si que es positiu a l'offset
        self.assertEqual(fmt_pos(3.0, True, 120, 4, 3.0), "1.1")
        # sense offset, tot positiu (comportament antic)
        self.assertEqual(fmt_pos(0.0, True, 120, 4, 0.0), "1.1")

    def test_metronom_limita_bpm(self):
        from app import metronom
        base = b"\x00\x00" * int(self.SR)
        # BPM enorme -> no fa res (evita bucles de milions de voltes)
        for bpm in (500.0, 10000.0):
            self.assertEqual(
                metronom.mescla_metronom(base, self.SR, 0.0, bpm, 4, volum=1.0),
                base)
        self.assertIsNone(metronom._es_valid(1000.0, 4))
        self.assertIsNotNone(metronom._es_valid(120.0, 4))


class TransportBarTests(unittest.TestCase):
    """Els botons de la BARRA de transport (fora del visor) han de fer efecte.

    Regressió: commuta_mut()/commuta_loop() llegien l'estat dels botons
    PROPIS del visor, no el de la barra -> el botó es marcava pero no passava res.
    """

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def _finestra_amb_visor(self):
        import tempfile, wave
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "t.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100)
        window = app_main.Finestra()
        window.wav_edit.setText(wav)
        window._carrega_visor(wav)
        return window, window.visor_ref

    def test_boto_mute_de_la_barra_afecta_el_visor(self):
        window, v = self._finestra_amb_visor()
        self.assertFalse(v.mut)
        window.tb_mut.setChecked(True)
        window.tb_mut.clicked.emit()
        self.assertTrue(v.mut)
        self.assertTrue(v.b_mut.isChecked())     # sincronitzat
        window.tb_mut.setChecked(False)
        window.tb_mut.clicked.emit()
        self.assertFalse(v.mut)
        window.close()

    def test_boto_loop_de_la_barra_afecta_el_visor(self):
        window, v = self._finestra_amb_visor()
        v.loop_a, v.loop_b = 1.0, 3.0           # cal tenir A i B marcats
        self.assertFalse(v.loop_on)
        window.tb_loop.setChecked(True)
        window.tb_loop.clicked.emit()
        self.assertTrue(v.loop_on)
        self.assertTrue(v.b_loop.isChecked())
        window.close()

    def test_boto_loop_no_activa_sense_a_i_b(self):
        window, v = self._finestra_amb_visor()
        v.loop_a = v.loop_b = None
        window.tb_loop.setChecked(True)
        window.tb_loop.clicked.emit()
        self.assertFalse(v.loop_on)             # sense A/B no s'activa
        window.close()


class MetroVisorTests(unittest.TestCase):
    """Integració del metrònom al visor (estat i reinici). Encara sense GUI."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def _visor(self):
        import tempfile, wave
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "t.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * 3)
        return visor.Visor(wav, None, None, 120.0, 4, True)

    def test_estat_inicial(self):
        v = self._visor()
        self.assertFalse(v.metro_on)
        self.assertAlmostEqual(v.metro_vol, 0.6)
        v.close()

    def test_commuta_metro_es_toggle(self):
        v = self._visor()
        v.commuta_metro()
        self.assertTrue(v.metro_on)
        v.commuta_metro()
        self.assertFalse(v.metro_on)
        v.close()

    def test_canvia_vol_metro_amb_clamp(self):
        v = self._visor()
        v._canvia_vol_metro(25)
        self.assertAlmostEqual(v.metro_vol, 0.25)
        v._canvia_vol_metro(150)
        self.assertAlmostEqual(v.metro_vol, 1.0)
        v._canvia_vol_metro(-5)
        self.assertAlmostEqual(v.metro_vol, 0.0)
        v.close()

    def test_commuta_metro_reinicia_des_de_la_posicio_si_sona(self):
        v = self._visor()
        v.sona = True
        v.pos = 1.5
        crides = {}
        v._atura_proc = lambda: crides.__setitem__("atura", True)
        v._engega_des_de = lambda t: crides.__setitem__("des_de", t)
        v.commuta_metro()
        self.assertTrue(crides.get("atura"))
        self.assertAlmostEqual(crides.get("des_de"), 1.5)
        v.close()

    def test_canvia_vol_metro_reinicia_si_sona(self):
        v = self._visor()
        v.sona = True
        v.pos = 0.7
        crides = {}
        v._atura_proc = lambda: crides.__setitem__("atura", True)
        v._engega_des_de = lambda t: crides.__setitem__("des_de", t)
        v._canvia_vol_metro(40)
        self.assertTrue(crides.get("atura"))
        self.assertAlmostEqual(crides.get("des_de"), 0.7)
        v.close()


class ContextMenuTests(unittest.TestCase):
    """Menu contextual (boto dret) sobre un clip del timeline."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def _visor(self):
        import tempfile, wave
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "t.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * 2)
        ac = os.path.join(td, "acords.csv")
        open(ac, "w").write("0.0,C\n2.0,Am\n")
        return visor.Visor(wav, ac, None, 120, 4, False)

    def _captura(self, v, kind, idx):
        from PyQt5.QtWidgets import QMenu
        from PyQt5.QtCore import QPoint
        capt = {}
        orig = QMenu.exec_

        def fake(self, pos, *a):
            capt["accions"] = [(x.text(), x.isEnabled())
                               for x in self.actions() if not x.isSeparator()]
            return None
        QMenu.exec_ = fake
        try:
            v._on_clip_context_menu(kind, idx, QPoint(0, 0))
        finally:
            QMenu.exec_ = orig
        return capt.get("accions", [])

    def test_menu_te_les_tres_accions(self):
        v = self._visor()
        accions = self._captura(v, "chord", 1)
        self.assertEqual([x[0] for x in accions],
                         ["Duplica", "Elimina", "Reanomena"])
        v.close()

    def test_menu_desactivat_sense_seleccio(self):
        v = self._visor()
        accions = self._captura(v, "chord", -1)
        self.assertTrue(all(not habilitat for _n, habilitat in accions))
        v.close()


class ThemeColorsTests(unittest.TestCase):
    """Els colors del visor viuen a app/theme.py, i seleccionat != actiu."""

    def test_seleccionat_i_actiu_son_distints(self):
        from app import theme
        self.assertNotEqual(theme.CLIP_SELECTED_BORDER,
                            theme.CLIP_ACTIVE_FILL)
        self.assertNotEqual(theme.CLIP_ACTIVE_FILL, theme.CLIP_FILL)

    def test_el_timeline_pren_els_colors_del_theme(self):
        from app import theme, timeline
        self.assertEqual(timeline.SELECTION_COLOR,
                         theme.CLIP_SELECTED_BORDER)
        self.assertEqual(timeline.CHORD_ACTIVE_FILL,
                         theme.CLIP_ACTIVE_FILL)
        self.assertEqual(timeline.CURSOR_COLOR, theme.TL_CURSOR)


class PipelineRunTests(unittest.TestCase):
    """run() ha de tenir timeout: un subprocés encallat no pot penjar-ho tot."""

    def test_run_aplica_timeout(self):
        from app import pipeline
        with self.assertRaises(subprocess.TimeoutExpired):
            pipeline.run(["sleep", "30"], lambda m: None, timeout=1)

    def test_run_ok(self):
        from app import pipeline
        p = pipeline.run(["true"], lambda m: None, timeout=5)
        self.assertEqual(p.returncode, 0)


class FormatCsvTests(unittest.TestCase):
    """Resolució temporal unificada (10 ms) i compassos de qualsevol bpb."""

    def test_acords_csv_te_2_decimals(self):
        import tempfile
        from app import pipeline
        td = tempfile.mkdtemp()
        ruta = os.path.join(td, "acords.csv")
        pipeline.desa_acords_csv(ruta, [
            (0.0, "C", "0.000000000"),
            (16.439727891, "E7", "16.439727891"),
        ])
        files = open(ruta).read().strip().splitlines()
        self.assertEqual(files[0], "0.00,C")
        self.assertEqual(files[1], "16.44,E7")
        for linia in files:
            t = linia.split(",")[0]
            self.assertLessEqual(len(t.split(".")[1]), 2,
                                 f"mes de 2 decimals: {linia}")

    def test_abc_csv_te_2_decimals(self):
        import tempfile
        from app import pipeline
        td = tempfile.mkdtemp()
        ruta = os.path.join(td, "estructura_ABC.csv")
        pipeline.desa_abc_csv(ruta, [(0.0, 21.362, "A", "N")], 101.0,
                              lambda m: None)
        files = open(ruta).read().strip().splitlines()
        self.assertEqual(files[0].split(",")[:3], ["inici_s", "fi_s", "durada_s"])
        self.assertEqual(files[1].split(",")[:3], ["0.00", "21.36", "21.36"])

    def test_pos_compas_respecta_bpb(self):
        from app import pipeline
        # 120 BPM -> beat 0.5s. Amb bpb=3, el 4t temps ja es compas 2.
        self.assertEqual(pipeline.pos_compas(0.0, 120, 3), "1.1.1")
        self.assertEqual(pipeline.pos_compas(0.5, 120, 3), "1.2.1")
        self.assertEqual(pipeline.pos_compas(1.0, 120, 3), "1.3.1")
        self.assertEqual(pipeline.pos_compas(1.5, 120, 3), "2.1.1")
        # bpb=4: el 4t temps encara es compas 1
        self.assertEqual(pipeline.pos_compas(1.5, 120, 4), "1.4.1")
        self.assertEqual(pipeline.pos_compas(2.0, 120, 4), "2.1.1")

    def test_pos_compas_lliure_mostra_segons(self):
        from app import pipeline
        self.assertTrue(pipeline.pos_compas(12.34, 120, 4, lliure=True)
                        .endswith("s"))


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
