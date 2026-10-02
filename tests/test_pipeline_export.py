import csv
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

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
        v = visor.Visor.__new__(visor.Visor)
        v.acords = [(0.0, "C", "0.000000000")]
        v.seccions = [(0.0, 2.0, "A", "A")]
        v.bpm = 120.0
        v.bpb = 4
        v.offset = 0.0
        v.tempo_fix = True
        v.audio = {"durada": 2.0}
        v.log = lambda msg: None
        v._carpeta_acords = lambda: "/tmp/export_test_ACORDS"

        with patch.object(visor.os, "makedirs"):
            with patch.object(visor.pipeline, "desa_acords_csv") as desa:
                with patch.object(visor.pipeline, "desa_abc_csv") as abc:
                    with patch.object(visor.pipeline, "regenera_wavs_acords") as reg_ac:
                        with patch.object(visor.pipeline, "regenera_wavs_estructura") as reg_abc:
                            with patch.object(visor.QMessageBox, "information"):
                                v.exporta()

        reg_ac.assert_called_once()
        reg_abc.assert_called_once()
        desa.assert_called_once()
        abc.assert_called_once()

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


if __name__ == "__main__":
    unittest.main()
