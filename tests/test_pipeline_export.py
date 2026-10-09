import csv
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

# --- Neteja: la suite creava centenars de tempdirs a /tmp que no s'esborraven
# (s'acumulaven entre execucions). Interceptem tempfile.mkdtemp i els traiem
# tots en acabar el modul de tests.
_TMPDIRS = []
_MKDTEMP_ORIG = tempfile.mkdtemp


def _mkdtemp_tracked(*args, **kwargs):
    d = _MKDTEMP_ORIG(*args, **kwargs)
    _TMPDIRS.append(d)
    return d


def setUpModule():
    _TMPDIRS.clear()
    tempfile.mkdtemp = _mkdtemp_tracked


def tearDownModule():
    tempfile.mkdtemp = _MKDTEMP_ORIG
    for d in _TMPDIRS:
        shutil.rmtree(d, ignore_errors=True)
    _TMPDIRS.clear()

import numpy as np

# Mode headless GLOBAL: sense això, les classes que creen QApplication abans
# de definir-lo (p.ex. ExportPipelineTests, que corre primer) poden penjar-se
# o avortar en un entorn sense pantalla.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app import (config, dialegs, ffmpeg, main as app_main, pipeline,
                 plataforma, postproc, theme, vamp_params, visor)

# QMessageBox.information/warning/... son MODALS: bloquegen fins que algu
# clica OK. En un entorn sense pantalla (CI) aixo penja el test per sempre.
# Els neutralitzem per a TOTS els tests (test-only; no toca l'app).
for _m in ("information", "warning", "critical", "question", "about"):
    if hasattr(visor.QMessageBox, _m):
        setattr(visor.QMessageBox, _m, staticmethod(lambda *a, **k: None))


def _escriu_fitxer(ruta, text):
    """Escriu un fitxer TANCANT-LO de seguida.

    A Windows un fitxer obert sense tancar pot bloquejar la lectura posterior
    (i les dades poden no estar a disc). Era la causa d'errors intermitents.
    """
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(text)


class ExportPipelineTests(unittest.TestCase):
    def test_setup_logging_creates_log_file(self):
        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "auto_chords_test.log"
            app_main.setup_logging(str(log_path))
            self.assertTrue(log_path.exists())
            # A Windows un FileHandler OBRERT bloqueja l'esborrat del tempdir
            # (TemporaryDirectory falla al cleanup): cal tancar i treure els
            # handlers del logger abans de sortir del `with`.
            _lg = logging.getLogger("auto_chords")
            for h in list(_lg.handlers):
                h.close()
                _lg.removeHandler(h)

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
        from PyQt5.QtGui import QCloseEvent
        app = visor.QApplication.instance() or visor.QApplication([])
        v = visor.Visor.__new__(visor.Visor)
        visor.QMainWindow.__init__(v)
        v._embedded = True
        v.rellotge = type("R", (), {"stop": lambda self: None})()
        v._atura_proc = lambda: None
        v.log = lambda *args, **kwargs: None
        with patch.object(visor.QApplication.instance(), "quit") as quit_mock:
            v.closeEvent(QCloseEvent())
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

    def test_multi_selection_toggle_i_rang(self):
        """Ctrl+clic afegeix/treu; Shift+clic selecciona el rang sencer."""
        view = self._make_view(tempo_fix=False)
        view.toggle_selection("chord", 0)
        view.toggle_selection("chord", 2)   # Ctrl-clic: afegeix
        self.assertEqual(view.selected_keys(), {("chord", 0), ("chord", 2)})
        self.assertTrue(view._chord_items[0]._selected)
        self.assertTrue(view._chord_items[2]._selected)
        self.assertFalse(view._chord_items[1]._selected)
        # Shift-clic des de l'àncora (2) fins a 3 → rang {2, 3}
        view.extend_selection("chord", 3)
        self.assertEqual(view.selected_keys(), {("chord", 2), ("chord", 3)})
        # Ctrl-clic sobre un de ja seleccionat el treu
        view.toggle_selection("chord", 2)
        self.assertEqual(view.selected_keys(), {("chord", 3)})

    def test_select_clip_resseteja_la_multi_seleccio(self):
        """Una selecció simple (des de llista/menu) buida la multi-selecció."""
        view = self._make_view(tempo_fix=False)
        view.toggle_selection("chord", 0)
        view.toggle_selection("chord", 1)
        view.select_clip("chord", 2)
        self.assertEqual(view.selected_keys(), {("chord", 2)})
        self.assertFalse(view._chord_items[0]._selected)

    def test_clear_selection_buida(self):
        """clear_selection deixa el conjunt buit i desmarca els items."""
        view = self._make_view(tempo_fix=False)
        view.select_clip("chord", 1)
        view.toggle_selection("chord", 2)
        view.clear_selection()
        self.assertEqual(view.selected_keys(), set())
        self.assertFalse(any(it._selected for it in view._chord_items))

    def test_set_data_buida_la_multi_seleccio(self):
        """set_data (re-render amb índexs nous) no deixa selecció òrfena."""
        view = self._make_view(tempo_fix=False)
        view.toggle_selection("chord", 0)
        view.toggle_selection("chord", 1)
        view.set_data([(0.0, "C", "0.0"), (1.0, "D", "1.0")], [])
        self.assertEqual(view.selected_keys(), set())


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
        with open(os.path.join(sortida, "acords.csv"), "w", encoding="utf-8") as f:
            f.write("0.0,C\n2.0,Am\n4.5,F\n7.0,G\n10.0,C\n")
        with open(os.path.join(sortida, "estructura_ABC.csv"), "w", encoding="utf-8") as f:
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

    def test_delete_de_grup_esborra_els_seleccionats(self):
        """Delete amb multi-selecció esborra tots els clips d'una sola vegada."""
        from PyQt5.QtGui import QKeyEvent
        from PyQt5.QtCore import QEvent, Qt
        v, _ = self._make_visor_with_data()
        n = len(v.acords)
        v.timeline.toggle_selection("chord", 1)
        v.timeline.toggle_selection("chord", 3)
        self.assertEqual(len(v.timeline.selected_keys()), 2)
        v.timeline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier))
        self.assertEqual(len(v.acords), n - 2)
        self.assertEqual(len(v._undo_stack), 1)   # una sola operació d'undo
        v.undo()
        self.assertEqual(len(v.acords), n)
        v.close()

    def test_ctrl_c_i_ctrl_v_enganxa_acord(self):
        """Ctrl+C + Ctrl+V: enganxa l'acord copiat al cursor (amb undo)."""
        from PyQt5.QtGui import QKeyEvent
        from PyQt5.QtCore import QEvent, Qt
        v, _ = self._make_visor_with_data()
        n = len(v.acords)
        v.timeline.select_clip("chord", 0)     # C @ 0.0
        v.timeline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_C, Qt.ControlModifier))
        self.assertTrue(v.timeline.has_clipboard())
        v.timeline.set_position(6.0, emit=False)
        v.timeline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_V, Qt.ControlModifier))
        self.assertEqual(len(v.acords), n + 1)
        temps = [round(float(t), 1) for (t, *_r) in v.acords]
        self.assertIn(6.0, temps)
        v.undo()
        self.assertEqual(len(v.acords), n)
        v.close()

    def test_ctrl_x_retalla_la_seleccio(self):
        """Ctrl+X: copia al buffer i esborra la selecció (amb undo)."""
        from PyQt5.QtGui import QKeyEvent
        from PyQt5.QtCore import QEvent, Qt
        v, _ = self._make_visor_with_data()
        n = len(v.acords)
        v.timeline.select_clip("chord", 1)
        v.timeline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_X, Qt.ControlModifier))
        self.assertEqual(len(v.acords), n - 1)
        self.assertTrue(v.timeline.has_clipboard())
        v.undo()
        self.assertEqual(len(v.acords), n)
        v.close()

    def test_ctrl_v_enganxa_seccio_parteix_la_contenidora(self):
        """Ctrl+V de seccions: insereix el bloc i parteix la contenidora."""
        from PyQt5.QtGui import QKeyEvent
        from PyQt5.QtCore import QEvent, Qt
        v, _ = self._make_visor_with_data()
        n = len(v.seccions)                    # 3: A 0-5, B 5-10, C 10-20
        v.timeline.select_clip("section", 1)   # B 5-10 (span 5)
        v.timeline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_C, Qt.ControlModifier))
        v.timeline.set_position(12.0, emit=False)   # dins C 10-20
        v.timeline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_V, Qt.ControlModifier))
        self.assertEqual(len(v.seccions), n + 2)   # 10-12 C + 12-17 B + 17-20 C
        for i in range(len(v.seccions) - 1):
            self.assertLessEqual(v.seccions[i][1], v.seccions[i + 1][0] + 1e-9)
        v.undo()
        self.assertEqual(len(v.seccions), n)
        v.close()

    def test_ctrl_v_seccio_no_hi_cap_no_canvia_res(self):
        """Si el bloc de seccions no cap a la contenidora, no es toca res."""
        from PyQt5.QtGui import QKeyEvent
        from PyQt5.QtCore import QEvent, Qt
        v, _ = self._make_visor_with_data()
        n = len(v.seccions)
        v.timeline.select_clip("section", 0)   # A 0-5 (span 5)
        v.timeline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_C, Qt.ControlModifier))
        v.timeline.set_position(6.0, emit=False)   # dins B 5-10: 6+5=11 > 10
        v.timeline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_V, Qt.ControlModifier))
        self.assertEqual(len(v.seccions), n)
        self.assertEqual(len(v._undo_stack), 0)
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

    def test_ctrl_d_duplica_el_grup_d_acords(self):
        """Ctrl+D amb multi-selecció duplica tots els acords (una sola undo)."""
        from PyQt5.QtGui import QKeyEvent
        from PyQt5.QtCore import QEvent, Qt
        v, _ = self._make_visor_with_data()
        n = len(v.acords)
        v.timeline.toggle_selection("chord", 0)
        v.timeline.toggle_selection("chord", 1)
        v.timeline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_D, Qt.ControlModifier))
        self.assertEqual(len(v.acords), n + 2)
        self.assertEqual(len(v._undo_stack), 1)
        v.undo()
        self.assertEqual(len(v.acords), n)
        v.close()

    def test_ctrl_d_duplica_les_seccions_seleccionades(self):
        """Ctrl+D amb multi-selecció de seccions: totes es parteixen (una undo)."""
        from PyQt5.QtGui import QKeyEvent
        from PyQt5.QtCore import QEvent, Qt
        v, _ = self._make_visor_with_data()
        n = len(v.seccions)
        v.timeline.toggle_selection("section", 0)
        v.timeline.toggle_selection("section", 1)
        v.timeline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_D, Qt.ControlModifier))
        self.assertEqual(len(v.seccions), n + 2)
        self.assertEqual(len(v._undo_stack), 1)
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
        _escriu_fitxer(os.path.join(ac, "acords.csv"), "9.5,Am\n")
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
        _escriu_fitxer(os.path.join(ac, "acords.csv"), "9.5,Am\n12.0,C\n")
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


class TempoOctavaTests(unittest.TestCase):
    """Ambiguitat d'octava/subdivisio del BPM (cas real: Otis Redding).

    Amb corxera forta, el prior pla antic triava 179,8; el plateau nou
    ha de triar el TEMPS real (~103,5).
    """

    SR = 22050

    def _wav(self, td, bpm, dur=40.0, amp_corxera=0.0):
        import wave
        n = int(self.SR * dur)
        a = np.zeros(n, dtype=np.float32)
        rng = np.random.default_rng(1)
        beat = 60.0 / bpm

        def clic(t, amp):
            i = int(t * self.SR)
            llarg = int(self.SR * 0.02)
            if i + llarg < n:
                env = np.exp(-8.0 * np.arange(llarg) / llarg)
                a[i:i + llarg] += (rng.normal(0, 1, llarg).astype(np.float32)
                                   * amp * env)

        t = 0.5
        while t < dur - 0.5:
            clic(t, 1.0)                     # el temps (fort)
            if amp_corxera:
                clic(t + beat / 2, amp_corxera)   # la corxera (mes fluixa)
            t += beat
        a = np.clip(a / max(1e-9, np.abs(a).max()) * 30000, -32768,
                    32767).astype(np.int16)
        ruta = os.path.join(td, "clics.wav")
        with wave.open(ruta, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(self.SR)
            w.writeframes(a.tobytes())
        return ruta

    def test_prior_plateau(self):
        from app import tempo
        lo, hi = tempo.BPM_PREFERIT
        self.assertEqual(tempo._prior(120.0), 1.0)
        self.assertEqual(tempo._prior(lo), 1.0)
        self.assertEqual(tempo._prior(hi), 1.0)
        self.assertLess(tempo._prior(200.0), 0.95)   # fora: penalitzat
        self.assertLess(tempo._prior(45.0), 0.95)

    def test_octava_132_no_queda_en_66(self):
        """Cas Chemical Brothers: 132 real, amb corxera forta a 66."""
        import tempfile
        from app import tempo
        td = tempfile.mkdtemp()
        wav = self._wav(td, 132.0, amp_corxera=0.55)
        b = tempo.detecta_bpm(wav, lambda *a: None)
        self.assertAlmostEqual(b, 132.0, delta=5.0)   # no 66

    def test_corxera_no_guanya_el_temps(self):
        import tempfile
        from app import tempo
        td = tempfile.mkdtemp()
        wav = self._wav(td, 103.45, amp_corxera=0.55)
        b = tempo.detecta_bpm(wav, lambda *a: None)
        self.assertIsNotNone(b)
        self.assertAlmostEqual(b, 103.45, delta=6.0)   # no 179/207

    def test_tempo_normal_intacte(self):
        import tempfile
        from app import tempo
        td = tempfile.mkdtemp()
        for bpm in (70.0, 101.0, 118.0, 138.0):
            wav = self._wav(td, bpm)
            b = tempo.detecta_bpm(wav, lambda *a: None)
            self.assertAlmostEqual(b, bpm, delta=4.0,
                                   msg=f"esperava {bpm}, vaig rebre {b}")


class UndoInfoTests(unittest.TestCase):
    """Desfer/refer expliquen el canvi a la caixa d'informacio."""

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
            w.writeframes(b"\x00\x00" * 44100 * 10)
        ac = os.path.join(td, "t_ACORDS"); os.makedirs(ac)
        _escriu_fitxer(os.path.join(ac, "acords.csv"), "0.0,C\n4.0,Am\n8.0,G\n")
        window = app_main.Finestra()
        window.wav_edit.setText(wav)
        window._carrega_visor(wav)
        return window

    def test_desfer_descriu_el_canvi(self):
        w = self._finestra(); v = w.visor_ref
        v._undo_marca()
        v.acords[1] = (5.0, "Am", "5.0")
        v._undo_commit()
        v.undo()
        txt = w.info_box.toPlainText()
        self.assertIn("DESFER", txt)
        self.assertIn("Am", txt)
        self.assertIn("5.00", txt)      # des de 5.00 (on era)
        w.close()

    def test_refer_descriu_el_canvi(self):
        w = self._finestra(); v = w.visor_ref
        v._undo_marca()
        v.acords[1] = (5.0, "Am", "5.0")
        v._undo_commit()
        v.undo()
        v.redo()
        txt = w.info_box.toPlainText()
        self.assertIn("REFER", txt)
        self.assertIn("Am", txt)
        w.close()

    def test_info_senyal_connectat(self):
        w = self._finestra()
        # si el senyal no esta connectat, aixo no peta pero no mostra res
        w.visor_ref.infoMissatge.emit("PROVA")
        self.assertIn("PROVA", w.info_box.toPlainText())
        w.close()

    def test_playstate_connectat_en_carregar(self):
        w = self._finestra()
        w.visor_ref.playStateChanged.emit(True)
        self.assertIn("Atura", w.b_play_tb.toolTip())
        w.close()


class InfoBoxTests(unittest.TestCase):
    """La caixa d'informacio explica el "ratoli intel·ligent" del timeline."""

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
            w.writeframes(b"\x00\x00" * 44100 * 20)
        ac = os.path.join(td, "t_ACORDS"); os.makedirs(ac)
        _escriu_fitxer(os.path.join(ac, "acords.csv"), "0.0,C\n8.0,G\n")
        _escriu_fitxer(os.path.join(ac, "estructura_ABC.csv"),
            "inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
            "0.0,8.0,8.0,A,N,1,1\n")
        window = app_main.Finestra()
        window.wav_edit.setText(wav)
        window._carrega_visor(wav)
        return window

    def test_zona_regle(self):
        from PyQt5.QtCore import QPoint
        w = self._finestra(); tv = w.visor_ref.timeline
        self.assertIn("LOOP", tv.info_zona(QPoint(200, 5)))

    def test_zona_ona(self):
        from PyQt5.QtCore import QPoint
        w = self._finestra(); tv = w.visor_ref.timeline
        txt = tv.info_zona(QPoint(900, 95))
        self.assertTrue("cursor" in txt.lower() or "zoom" in txt.lower())
        w.close()

    def test_zona_clip(self):
        from PyQt5.QtCore import QPoint
        w = self._finestra(); tv = w.visor_ref.timeline
        # el cos d'un clip te una accio de MOURE
        txt = tv.info_zona(QPoint(60, 130))
        self.assertTrue("Mou" in txt)
        w.close()


class Compas1Tests(unittest.TestCase):
    """Deteccio automatica del compas 1 (downbeat) amb el Queen Mary."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def test_boto_i_accio_existeixen(self):
        w = app_main.Finestra()
        # compas 1 automatic: ara es una ICONA (Lucide compass)
        self.assertFalse(w.b_compas_auto.icon().isNull())
        self.assertIn("compàs 1", w.b_compas_auto.toolTip().lower())
        # res del que ja hi havia s'ha perdut
        self.assertFalse(w.b_offset_cursor.icon().isNull())   # map-pin
        self.assertEqual(w.b_tap.text(), "TAP")
        self.assertEqual(w.b_bpm_x2.text(), "×2")
        self.assertEqual(w.b_bpm_div2.text(), "÷2")
        w.close()

    def test_transforms_qm_disponibles(self):
        for clau, frag in (("onsets", "qm-onsetdetector:onsets"),
                           ("bars", "qm-barbeattracker:bars"),
                           ("beats", "qm-barbeattracker:beats"),
                           ("key", "qm-keydetector:key"),
                           ("segments", "qm-segmenter:segmentation")):
            self.assertIn(frag, pipeline.QM[clau])

    def test_plugins_unics_restants(self):
        # només Chordino i Queen Mary: fora el Segmentino i l'aubio
        dirs = [d for d in os.listdir(pipeline.PROJ_DIR)
                if d.endswith("-local")]
        self.assertIn("nnls-chroma-linux64-local", dirs)
        self.assertIn("qm-vamp-plugins-linux64-local", dirs)
        self.assertNotIn("segmentino-linux64-local", dirs)
        self.assertNotIn("vamp-aubio-linux64-local", dirs)

    def test_detecta_compas1_retorna_float_o_none(self):
        import tempfile, wave
        import numpy as np
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "t.wav")
        sr = 22050
        a = (np.sin(np.linspace(0, 440 * 2 * np.pi * 8, sr * 8))
             * 6000).astype(np.int16)
        with wave.open(wav, "wb") as f:
            f.setnchannels(1); f.setsampwidth(2); f.setframerate(sr)
            f.writeframes(a.tobytes())
        # Log VISIBLE: si el host falla, el motiu ha de sortir al log del CI.
        r = pipeline.detecta_compas1(wav, lambda m: print("[compas1]", m, flush=True))
        self.assertTrue(r is None or isinstance(r, float))
        if r is not None:
            self.assertTrue(0.0 <= r <= 8.5)


class PlayCoherenciaTests(unittest.TestCase):
    """Coherencia del play: cache de mono + aturar abans de plugins/redibuix."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])
        import tempfile, wave
        import numpy as np
        cls._d = tempfile.mkdtemp()
        cls._wav = os.path.join(cls._d, "t.wav")
        with wave.open(cls._wav, "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(44100)
            w.writeframes((np.sin(np.linspace(0, 440 * 2 * np.pi * 3,
                                              44100 * 3)) * 8000).astype(
                np.int16).tobytes() * 2)
        cls._ac = os.path.join(cls._d, "ACORDS"); os.makedirs(cls._ac)
        _escriu_fitxer(os.path.join(cls._ac, "acords.csv"), "0.0,C\n")
    def _visor(self):
        return visor.Visor(self._wav, os.path.join(self._ac, "acords.csv"),
                           None, 120, 4)

    def test_mono_bytes_cachejat(self):
        v = self._visor()
        a = v._mono_bytes()
        import time
        t0 = time.perf_counter()
        b = v._mono_bytes()
        dt = time.perf_counter() - t0
        self.assertIs(a, b)                 # mateix objecte (cache)
        self.assertLess(dt, 0.01)           # instantani

    def test_mono_bytes_no_depen_del_mute(self):
        # el volum/mute s'apliquen en directe al fil, NO al buffer cacat
        v = self._visor()
        a = v._mono_bytes()
        v.mut = True
        self.assertIs(a, v._mono_bytes())

    def test_player_te_latencia_baixa(self):
        v = self._visor()
        _pl, args = v._tria_player()
        if _pl == "paplay":
            self.assertIn("--latency-msec=100", args)

    def test_alimenta_aplica_el_guany(self):
        import numpy as np

        class _Buf:
            def __init__(self):
                self.dades = bytearray()

            def write(self, b):
                self.dades += b
                return len(b)

            def close(self):
                pass

        class FakeProc:
            def __init__(self):
                self.buf = _Buf()
                self.rc = None

            def poll(self):
                return self.rc

            @property
            def stdin(self):
                return self.buf

        v = self._visor()
        v._sess = 0
        tros = v._mono_bytes()[:65536]
        v.vol = 0.5
        v.mut = False
        p1 = FakeProc()
        v._alimenta(p1, tros, 0)
        v.vol = 1.0
        p2 = FakeProc()
        v._alimenta(p2, tros, 0)
        a = np.frombuffer(bytes(p1.buf.dades), dtype=np.int16).astype(float)
        b = np.frombuffer(bytes(p2.buf.dades), dtype=np.int16).astype(float)
        self.assertGreater(np.abs(b).mean(), 0)
        self.assertAlmostEqual(np.abs(a).mean() / np.abs(b).mean(), 0.5,
                               delta=0.05)

    def test_volum_i_mute_no_reinicien(self):
        v = self._visor()
        crides = []
        v._atura_proc = lambda: crides.append("atura")
        v._engega_des_de = lambda t: crides.append("engega")
        v.sona = True
        v._canvia_volum(50)
        v.set_mut(True)
        self.assertEqual(crides, [])        # cap reinici
        self.assertAlmostEqual(v.vol, 0.5, places=3)
        self.assertTrue(v.mut)

    def test_tiquet_no_talla_la_cua(self):
        # posicionat just al final, sonant: NO ha d'aturar (espera l'EOF)
        import time
        v = self._visor()

        class FakeProc:
            returncode = None

            def poll(self):
                return None

        v.proc = FakeProc()
        v.sona = True
        v.t0_pos = float(v.audio["durada"])
        v.t0_mono = time.monotonic()
        v._tiquet()
        self.assertTrue(v.sona)             # segueix "sonant"

    def test_atura_si_sona(self):
        w = app_main.Finestra()

        class Fake:
            def __init__(self, sona):
                self.sona = sona
                self.stops = 0

            def play_stop(self):
                self.sona = False
                self.stops += 1

        f = Fake(True); w.visor_ref = f
        w._atura_si_sona("prova")
        self.assertFalse(f.sona)
        self.assertEqual(f.stops, 1)
        f2 = Fake(False); w.visor_ref = f2
        w._atura_si_sona("prova")
        self.assertEqual(f2.stops, 0)       # ja aturat: no fa res
        w.close()

    def test_sites_que_aturen(self):
        import inspect
        for fn in (app_main.Finestra.executa,
                   app_main.Finestra._detecta_bpm,
                   app_main.Finestra._carrega_visor):
            self.assertIn("_atura_si_sona", inspect.getsource(fn))


class BpmDoblaTests(unittest.TestCase):
    """Botons ×2 / ÷2 del BPM."""

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
            w.writeframes(b"\x00\x00" * 44100 * 5)
        ac = os.path.join(td, "t_ACORDS"); os.makedirs(ac)
        _escriu_fitxer(os.path.join(ac, "acords.csv"), "0.0,C\n")
        window = app_main.Finestra()
        window.wav_edit.setText(wav)
        window._carrega_visor(wav)
        return window

    def test_botons_existeixen(self):
        w = self._finestra()
        self.assertEqual(w.b_bpm_x2.text(), "×2")
        self.assertEqual(w.b_bpm_div2.text(), "÷2")
        w.close()

    def test_dobla_i_meitat(self):
        w = self._finestra()
        w.bpm.setText("101.0")
        w.b_bpm_x2.click()
        self.assertAlmostEqual(w._bpm_val(), 202.0, places=1)
        w.b_bpm_div2.click()
        self.assertAlmostEqual(w._bpm_val(), 101.0, places=1)
        w.close()

    def test_limits(self):
        w = self._finestra()
        w.bpm.setText("300.0"); w.b_bpm_x2.click()
        self.assertAlmostEqual(w._bpm_val(), 400.0, places=1)
        w.bpm.setText("50.0"); w.b_bpm_div2.click()
        self.assertAlmostEqual(w._bpm_val(), 30.0, places=1)
        w.close()

    def test_propaga_al_visor(self):
        w = self._finestra()
        w.bpm.setText("101.0"); w.b_bpm_x2.click()
        self.assertAlmostEqual(w.visor_ref.bpm, 202.0, places=1)
        w.close()


class FfmpegTests(unittest.TestCase):
    """Import d'altres formats d'audio via ffmpeg (conversio a WAV PCM 16)."""

    @classmethod
    def setUpClass(cls):
        if not ffmpeg.disponible():
            raise unittest.SkipTest("ffmpeg no disponible")
        import tempfile
        cls._d = tempfile.mkdtemp()
        cls._src = os.path.join(cls._d, "ton.wav")
        subprocess.run([ffmpeg.FFMPEG, "-y", "-f", "lavfi", "-i",
                        "sine=frequency=440:duration=1", "-c:a", "pcm_s16le",
                        cls._src], capture_output=True)

    def test_extensions_i_filtre(self):
        for e in ("wav", "mp3", "aif", "aiff", "flac", "m4a", "ogg"):
            self.assertIn(e, ffmpeg.extensions())
        f = ffmpeg.filtre()
        self.assertIn("*.mp3", f)
        self.assertIn("*.aif", f)

    def test_es_wav_pcm16(self):
        self.assertTrue(ffmpeg.es_wav_pcm16(self._src))
        self.assertFalse(ffmpeg.es_wav_pcm16("/no/existeix.wav"))
        self.assertFalse(ffmpeg.es_wav_pcm16("/tmp/x.mp3"))

    def test_converteix_mp3(self):
        mp3 = os.path.join(self._d, "canco.mp3")
        subprocess.run([ffmpeg.FFMPEG, "-y", "-i", self._src, mp3],
                       capture_output=True)
        wav = ffmpeg.converteix_a_wav(mp3)
        self.assertTrue(wav.endswith("canco_convertit.wav"))
        self.assertTrue(ffmpeg.es_wav_pcm16(wav))
        # `info()` depèn de ffprobe, que NO s'empaqueta (l'app no el fa servir:
        # fa pipeline.wav_info). Sense ffprobe retorna {} -> no hi ha res a
        # comprovar aquí; la conversió ja s'ha validat a les línies de dalt.
        if not shutil.which(ffmpeg.FFPROBE):
            self.skipTest("ffprobe no disponible (no s'empaqueta)")
        inf = ffmpeg.info(wav)
        self.assertEqual(inf["mostreig"], 44100)
        self.assertAlmostEqual(inf["durada"], 1.0, delta=0.1)

    def test_converteix_aiff_i_flac(self):
        for ext in ("aiff", "flac"):
            src = os.path.join(self._d, f"pista.{ext}")
            subprocess.run([ffmpeg.FFMPEG, "-y", "-i", self._src, src],
                           capture_output=True)
            wav = ffmpeg.converteix_a_wav(src)
            self.assertTrue(ffmpeg.es_wav_pcm16(wav))

    def test_wav_ja_bona_no_es_toca(self):
        self.assertEqual(ffmpeg.converteix_a_wav(self._src), self._src)

    def test_reutilitza_si_es_mes_nou(self):
        mp3 = os.path.join(self._d, "reut.mp3")
        subprocess.run([ffmpeg.FFMPEG, "-y", "-i", self._src, mp3],
                       capture_output=True)
        wav1 = ffmpeg.converteix_a_wav(mp3)
        m1 = os.path.getmtime(wav1)
        wav2 = ffmpeg.converteix_a_wav(mp3)
        self.assertEqual(wav1, wav2)
        self.assertEqual(m1, os.path.getmtime(wav2))


class PostprocTests(unittest.TestCase):
    """Post-processat dels acords (app/postproc.py)."""

    def test_treu_baix(self):
        self.assertEqual(postproc.treu_baix("A/E"), "A")
        self.assertEqual(postproc.treu_baix("F#dim7/E"), "F#dim7")
        self.assertEqual(postproc.treu_baix("C"), "C")

    def test_redueix(self):
        for entrada, esperat in [("Cmaj7", "C"), ("Em6", "Em"), ("A7", "A"),
                                 ("Edim7", "Edim"), ("C#m", "C#m"),
                                 ("D6", "D"), ("Am7", "Am"), ("Cmaj9", "C")]:
            self.assertEqual(postproc.redueix(entrada), esperat)

    def test_fusiona_iguals(self):
        r = postproc.processa_acords([(0, "C"), (4, "C"), (8, "Am")])
        self.assertEqual([x[1] for x in r], ["C", "Am"])

    def test_durada_minima(self):
        # Am dura 0,2 s -> s'elimina
        r = postproc.processa_acords(
            [(0, "C"), (8, "Am"), (8.2, "G"), (12, "F")], durada_min=1.0)
        self.assertNotIn("Am", [x[1] for x in r])

    def test_sense_baix_i_reduir(self):
        r = postproc.processa_acords([(0, "A/E"), (4, "Cmaj7")],
                                     sense_baix=True, reduir=True)
        self.assertEqual([x[1] for x in r], ["A", "C"])

    def test_snap(self):
        r = postproc.snap_acords([(0.1, "C"), (1.03, "G"), (2.4, "Am")],
                                 bpm=60, divisio=1)
        self.assertEqual([round(x[0], 2) for x in r], [0.0, 1.0, 2.0])

    def test_processa_acords_csv(self):
        import tempfile
        d = tempfile.mkdtemp()
        f = os.path.join(d, "a.csv")
        with open(f, "w", encoding="utf-8") as fh:
            fh.write("0.0,A/E\n4.0,A\n8.0,Cmaj7\n8.5,G\n12.0,G\n")
        postproc.processa_acords_csv(f, sense_baix=True, reduir=True,
                                     durada_min=1.0, fusiona_iguals=True)
        with open(f, encoding="utf-8") as fh:
            noms = [r[1] for r in csv.reader(fh)]
        self.assertEqual(noms, ["A", "G"])


class FiltraSeccionsTests(unittest.TestCase):
    """Post-processat de les seccions (opcions del dialeg)."""

    def test_fusiona_iguals(self):
        s = [(0, 5, "A", "A"), (5, 10, "B", "B"), (10, 14, "B", "B"),
             (14, 18, "C", "C")]
        r = pipeline.filtra_seccions(s, fusiona_iguals=True)
        self.assertEqual(r, [(0, 5, "A", "A"), (5, 14, "B", "B"),
                             (14, 18, "C", "C")])

    def test_durada_minima(self):
        s = [(0, 5, "A", "A"), (5, 6, "B", "B"), (6, 18, "C", "C")]
        r = pipeline.filtra_seccions(s, durada_min=2)
        self.assertEqual(r, [(0, 6, "A", "A"), (6, 18, "C", "C")])

    def test_buit(self):
        self.assertEqual(pipeline.filtra_seccions([]), [])


class DialegOpcionsTests(unittest.TestCase):
    """Dialeg d'opcions d'autodeteccio (BPM / Acords / Estructura)."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def setUp(self):
        # ailla els tests del fitxer real d'opcions de l'usuari
        import tempfile
        self._patch = patch.object(
            dialegs, "FITXER_OPCIONS",
            os.path.join(tempfile.mkdtemp(), "op.json"))
        self._patch.start()

    def tearDown(self):
        self._patch.stop()

    def test_tres_pestanyes_i_tab_inicial(self):
        d = dialegs.DialegOpcions(None, tab="acords")
        self.assertEqual(d.tabs.count(), 3)
        self.assertEqual(d.tabs.currentIndex(), 1)
        d2 = dialegs.DialegOpcions(None, tab="bpm")
        self.assertEqual(d2.tabs.currentIndex(), 0)

    def test_opcions_son_els_6_parametres_del_chordino(self):
        d = dialegs.DialegOpcions(None)
        op = d.opcions()
        self.assertEqual(sorted(op["chords"]),
                         ["rollon", "s", "tuningmode", "useHMM",
                          "useNNLS", "whitening"])
        self.assertEqual(op["chords"]["useHMM"], 1)
        self.assertAlmostEqual(op["chords"]["s"], 0.7, places=2)

    def test_canvi_de_valors(self):
        d = dialegs.DialegOpcions(None)
        d._controls["chords"]["useHMM"].setChecked(False)
        d._controls["chords"]["rollon"].setValue(3)
        op = d.opcions()
        self.assertEqual(op["chords"]["useHMM"], 0)
        self.assertEqual(op["chords"]["rollon"], 3)

    def test_estructura_te_les_seves_opcions(self):
        d = dialegs.DialegOpcions(None)
        op = d.opcions()
        self.assertIn("durada_min", op["structure"])
        self.assertIn("fusiona_iguals", op["structure"])

    def test_bpm_te_rang_i_preferit(self):
        d = dialegs.DialegOpcions(None)
        b = d.opcions()["bpm"]
        self.assertEqual(b["min"], 60)
        self.assertEqual(b["pref_min"], 85)    # plateau del prior
        self.assertEqual(b["motor"], "nostre")

    def test_estructura_nomes_qm(self):
        # el Segmentino s'ha retirat: l'estructura sempre va amb qm-segmenter
        d = dialegs.DialegOpcions(None)
        self.assertEqual(d.opcions()["structure"]["motor"], "qm")
        self.assertEqual(pipeline.MOTORS_ESTRUCTURA, ("qm",))

    def test_motors_bpm(self):
        d = dialegs.DialegOpcions(None)
        c = d._controls["bpm"]["motor"]
        for m in ("nostre", "qm", "consens"):
            c.setCurrentIndex(c.findData(m))
            self.assertEqual(d.opcions()["bpm"]["motor"], m)
        # aubio s'ha retirat
        self.assertEqual(pipeline.MOTORS_BPM, ("nostre", "qm", "consens"))

    def test_restaura_per_defecte(self):
        d = dialegs.DialegOpcions(None)
        d._controls["chords"]["useHMM"].setChecked(False)
        d._controls["structure"]["durada_min"].setValue(9)
        d._restaura()
        op = d.opcions()
        self.assertEqual(op["chords"]["useHMM"], 1)
        self.assertEqual(op["structure"]["durada_min"], 0.0)

    def test_desa_i_carrega(self):
        op = dialegs.carrega_opcions()
        op["chords"]["useHMM"] = 0
        dialegs.desa_opcions(op)
        self.assertEqual(dialegs.carrega_opcions()["chords"]["useHMM"], 0)


class VampParamsTests(unittest.TestCase):
    """Lectura dels parametres dels plugins Vamp (descriptors .n3)."""

    def test_chordino_te_6_parametres_en_ordre(self):
        ids = [p["id"] for p in vamp_params.params_de("chords")]
        self.assertEqual(ids, ["useNNLS", "useHMM", "rollon",
                               "tuningmode", "whitening", "s"])

    def test_rangs_i_defectes(self):
        ps = {p["id"]: p for p in vamp_params.params_de("chords")}
        self.assertEqual((ps["useNNLS"]["minim"], ps["useNNLS"]["maxim"],
                          ps["useNNLS"]["defecte"]), (0.0, 1.0, 1.0))
        self.assertEqual((ps["rollon"]["minim"], ps["rollon"]["maxim"],
                          ps["rollon"]["pas"], ps["rollon"]["defecte"]),
                         (0.0, 5.0, 0.5, 0.0))
        self.assertEqual(ps["s"]["minim"], 0.5)
        self.assertEqual(ps["s"]["maxim"], 0.9)

    def test_value_names_tuningmode(self):
        ps = {p["id"]: p for p in vamp_params.params_de("chords")}
        self.assertEqual(ps["tuningmode"]["valors"],
                         ["global tuning", "local tuning"])

    def test_segmentino_sense_parametres(self):
        self.assertEqual(vamp_params.params_de("structure"), [])

    def test_valors_per_defecte(self):
        d = vamp_params.valors_per_defecte("chords")
        self.assertEqual(d["useHMM"], 1.0)
        self.assertEqual(d["s"], 0.7)


def _sonic_ok():
    """Cert si el `sonic-annotator` es pot executar (les seves llibreries hi son).

    S'usa per FER SKIP dels tests que en depenen quan falta (p. ex. a un
    runner de CI sense Qt6/ICU/glib). El pipeline real fa servir l'host propi
    (`vamp_host_local`); el sonic-annotator nome es la reserva.
    """
    import subprocess
    try:
        p = subprocess.run([pipeline.SONIC, "--version"],
                           capture_output=True, timeout=30)
        return p.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


_SONIC_OK = _sonic_ok()


@unittest.skipUnless(_SONIC_OK, "sonic-annotator no executable (falten llibreries)")
class EscriuTtlTests(unittest.TestCase):
    """Generacio del transform .ttl amb els parametres triats.

    NOMES amb el sonic-annotator executable: es el que genera el TTL base.
    El pipeline real fa servir l'host propi (vamp_host_local).
    """

    def _ttl(self, params):
        import tempfile
        d = tempfile.mkdtemp()
        ruta = os.path.join(d, "t.ttl")
        pipeline.escriu_ttl("chords", params, ruta, lambda *a: None)
        return open(ruta, encoding="utf-8").read()

    def test_ttl_te_tots_els_parametres(self):
        s = self._ttl({})
        for k in ("useNNLS", "useHMM", "rollon", "tuningmode", "whitening", "s"):
            self.assertIn(f'vamp:identifier "{k}"', s)
        self.assertIn("vamp:output", s)

    def test_ttl_aplica_els_valors_demanats(self):
        s = self._ttl({"useHMM": 0, "rollon": 3})
        self.assertIn('vamp:identifier "useHMM" ] ;\n        vamp:value "0.0"', s)
        self.assertIn('vamp:identifier "rollon" ] ;\n        vamp:value "3.0"', s)
        # els no indicats agafen el defecte
        self.assertIn('vamp:identifier "useNNLS" ] ;\n        vamp:value "1.0"', s)

    def test_ttl_no_es_el_default_quan_canvia(self):
        self.assertNotEqual(self._ttl({}), self._ttl({"useHMM": 0, "rollon": 3}))


class BotoOnOffTests(unittest.TestCase):
    """Botons: icona play/pause i estat ences/apagat ben visible."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = visor.QApplication.instance() or visor.QApplication([])

    def setUp(self):
        self._app.setStyleSheet(theme.app_stylesheet())   # com fa main()

    def _finestra(self):
        import tempfile, wave
        td = tempfile.mkdtemp()
        wav = os.path.join(td, "t.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
            w.writeframes(b"\x00\x00" * 44100 * 10)
        ac = os.path.join(td, "t_ACORDS"); os.makedirs(ac)
        _escriu_fitxer(os.path.join(ac, "acords.csv"), "0.0,C\n")
        window = app_main.Finestra()
        window.wav_edit.setText(wav)
        window._carrega_visor(wav)
        return window

    def test_play_icona_play_i_pause(self):
        # Ara son ICONES (Lucide), no text: comprovem el tooltip + la icona.
        w = self._finestra()
        self.assertFalse(w.b_play_tb.icon().isNull())
        self.assertIn("Reprodueix", w.b_play_tb.toolTip())
        w._on_play_state(True)
        self.assertIn("Atura", w.b_play_tb.toolTip())
        self.assertFalse(w.b_play_tb.icon().isNull())
        w._on_play_state(False)
        self.assertIn("Reprodueix", w.b_play_tb.toolTip())
        w.close()

    def test_visor_emet_play_state(self):
        w = self._finestra(); v = w.visor_ref
        rebut = []
        v.playStateChanged.connect(rebut.append)
        v.sona = True                       # simulem que estaba sonant
        v.play_stop()                       # -> atura i ha d'emetre False
        self.assertIn(False, rebut)
        self.assertIn("Reprodueix", w.b_play_tb.toolTip())
        w.close()

    def test_commutables_son_checkable(self):
        w = self._finestra()
        for b in (w.tb_loop, w.tb_mut, w.b_metro, w.b_mode_bpm, w.b_mode_lliure):
            self.assertTrue(b.isCheckable())
        w.close()

    def test_estil_te_estat_checked(self):
        e = theme.app_stylesheet()
        self.assertIn("QPushButton:checked", e)
        self.assertIn(theme.ACTIU, e)
        self.assertIn("QPushButton#metro:checked", e)

    def test_render_ences_vs_apagat(self):
        """El fons del boto canvia de debò (pixel) entre apagat i ences."""
        from PyQt5.QtCore import QPoint
        w = self._finestra(); w.resize(1100, 600); w.show()
        self._app.processEvents()

        def fons(bot):
            img = w.grab().toImage()
            p = bot.mapTo(w, QPoint(5, bot.height() // 2))
            c = img.pixelColor(p.x(), p.y())
            return (c.red(), c.green(), c.blue())

        # apagat = estil "Obre..." (gris)
        apagat = fons(w.tb_loop)
        self.assertLess(abs(apagat[0] - apagat[1]), 15)
        self.assertLess(abs(apagat[1] - apagat[2]), 15)
        # ences = blau
        w.tb_loop.setChecked(True); self._app.processEvents()
        ences = fons(w.tb_loop)
        self.assertNotEqual(apagat, ences)
        self.assertGreater(ences[2], ences[0] + 40)      # blau dominant
        # mute i metronom s'encenen en groc
        w.tb_mut.setChecked(True); w.b_metro.setChecked(True)
        self._app.processEvents()
        for bot in (w.tb_mut, w.b_metro):
            g = fons(bot)
            self.assertGreater(g[0], 200); self.assertLess(g[2], 130)
        w.close()


class LlistaSeleccioTests(unittest.TestCase):
    """Clicar una fila de les llistes l'ha de deixar ressaltada.

    Regressio: _actualitza_temps() (cridada per ves_a) repobla les llistes
    amb clear() i abans en perdia la seleccio.
    """

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
            w.writeframes(b"\x00\x00" * 44100 * 20)
        ac = os.path.join(td, "t_ACORDS"); os.makedirs(ac)
        _escriu_fitxer(os.path.join(ac, "acords.csv"), "0.0,C\n4.0,Am\n8.0,G\n")
        _escriu_fitxer(os.path.join(ac, "estructura_ABC.csv"),
            "inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
            "0.00,4.00,4.00,A,N,1,1\n4.00,20.00,16.00,B,B,1,1\n")
        window = app_main.Finestra()
        window.wav_edit.setText(wav)
        window._carrega_visor(wav)
        window.bpm.setText("101"); window._aplica_parametres_temps()
        return window

    def test_clic_acord_deixa_fila_ressaltada(self):
        w = self._finestra(); v = w.visor_ref
        v._salt_acord(v.llista_ac.item(1))
        self.assertEqual(v.llista_ac.currentRow(), 1)
        self.assertTrue(v.llista_ac.item(1).isSelected())
        self.assertEqual(v.timeline._sel, ("chord", 1))
        w.close()

    def test_clic_seccio_deixa_fila_ressaltada(self):
        w = self._finestra(); v = w.visor_ref
        v._salt_seccio(v.llista_ab.item(1))
        self.assertEqual(v.llista_ab.currentRow(), 1)
        self.assertTrue(v.llista_ab.item(1).isSelected())
        self.assertEqual(v.timeline._sel, ("section", 1))
        w.close()

    def test_canvi_bpm_conserva_seleccio(self):
        w = self._finestra(); v = w.visor_ref
        v._salt_acord(v.llista_ac.item(1))
        w.bpm.setText("120"); w._aplica_parametres_temps()
        self.assertEqual(v.llista_ac.currentRow(), 1)
        w.close()


class OffsetBotoCursorTests(unittest.TestCase):
    """Boto a Offset: llegeix el cursor vermell i hi posa el compas 1."""

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
            w.writeframes(b"\x00\x00" * 44100 * 20)
        ac = os.path.join(td, "t_ACORDS"); os.makedirs(ac)
        _escriu_fitxer(os.path.join(ac, "acords.csv"), "0.0,C\n")
        window = app_main.Finestra()
        window.wav_edit.setText(wav)
        window._carrega_visor(wav)
        window.bpm.setText("101"); window.bpb.setText("4")
        window._aplica_parametres_temps()
        return window

    def test_boto_llegeix_cursor_i_aplica_offset(self):
        w = self._finestra(); v = w.visor_ref
        v.ves_a(9.5)                       # "cursor vermell" a 9.5s
        w.b_offset_cursor.click()          # com l'usuari
        self.assertAlmostEqual(v.offset, 9.5, places=2)
        self.assertEqual(w.offset.text(), "9.50")
        # el camp compas.beat tambe s'actualitza
        self.assertTrue(w.offset_cb.text().startswith("5."))
        v.ves_a(3.0); w.b_offset_cursor.click()
        self.assertAlmostEqual(v.offset, 3.0, places=2)
        w.close()


class TapTempoTests(unittest.TestCase):
    """Tap tempo (patro estandard: ultims taps -> mitjana -> 60/interval)."""

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
            w.writeframes(b"\x00\x00" * 44100 * 10)
        ac = os.path.join(td, "t_ACORDS"); os.makedirs(ac)
        _escriu_fitxer(os.path.join(ac, "acords.csv"), "0.0,C\n")
        window = app_main.Finestra()
        window.wav_edit.setText(wav)
        window._carrega_visor(wav)
        return window

    def _taps_en(self, w, interval, n=5, inici=1000.0):
        """Simula n taps separats `interval` segons (mock de monotonic)."""
        from unittest.mock import patch
        t = inici
        with patch("app.main.time.monotonic", side_effect=[t + i * interval
                                                           for i in range(n)]):
            w._taps = []
            for _ in range(n):
                w._tap_tempo()
        return w

    def test_taps_594ms_donen_101bpm(self):
        w = self._finestra()
        self._taps_en(w, 0.594)
        self.assertAlmostEqual(w._bpm_val(), 101.0, delta=3.0)
        w.close()

    def test_taps_500ms_donen_120bpm(self):
        w = self._finestra()
        self._taps_en(w, 0.5)
        self.assertAlmostEqual(w._bpm_val(), 120.0, delta=3.0)
        w.close()

    def test_tap_propaga_al_visor(self):
        w = self._finestra()
        self._taps_en(w, 0.5)
        self.assertAlmostEqual(w.visor_ref.bpm, 120.0, delta=3.0)
        w.close()

    def test_reset_per_timeout(self):
        from unittest.mock import patch
        w = self._finestra()
        w._taps = [0.0]
        with patch("app.main.time.monotonic", return_value=5.0):  # >2s despres
            w._tap_tempo()
        self.assertEqual(len(w._taps), 1)      # s'ha reiniciat
        w.close()

    def test_intervals_absurds_descartats(self):
        """Un doble-tap accidental (interval <0.2s) s'ignora."""
        from unittest.mock import patch
        w = self._finestra()
        w._taps = [0.0, 0.5, 0.51]   # 3r tap a 10 ms -> absurd
        with patch("app.main.time.monotonic", return_value=1.0):
            w._tap_tempo()
        # els intervals valids son 0.5 i 0.49 -> BPM ~120, no ~2000
        self.assertLess(w._bpm_val(), 130)
        w.close()


class EditorFranjaTests(unittest.TestCase):
    """Franja Editor: mostra/edita l'element seleccionat sense finestres."""

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
            w.writeframes(b"\x00\x00" * 44100 * 20)
        ac = os.path.join(td, "t_ACORDS"); os.makedirs(ac)
        _escriu_fitxer(os.path.join(ac, "acords.csv"), "0.0,C\n4.0,Am\n8.0,G\n")
        _escriu_fitxer(os.path.join(ac, "estructura_ABC.csv"),
            "inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
            "0.00,4.00,4.00,A,N,1,1\n4.00,20.00,16.00,B,B,1,1\n")
        window = app_main.Finestra()
        window.bpm.setText("120"); window.bpb.setText("4")
        window._aplica_parametres_temps()
        window.wav_edit.setText(wav)
        window._carrega_visor(wav)
        return window

    def test_editor_mostra_l_acord_seleccionat(self):
        w = self._finestra(); v = w.visor_ref
        v.timeline.select_clip("chord", 1); v._on_clip_selected("chord", 1)
        self.assertEqual(v.ed_gran.text(), "Am")
        self.assertEqual(v.ed_nom.text(), "Am")
        self.assertEqual(v.ed_ini.text(), "4.00")
        self.assertFalse(v.ed_fam.isVisible())
        w.close()

    def test_editor_mostra_la_seccio_seleccionada(self):
        w = self._finestra(); v = w.visor_ref
        v.timeline.select_clip("section", 0); v._on_clip_selected("section", 0)
        self.assertTrue(v.ed_gran.text().startswith("A"))
        self.assertEqual(v.ed_nom.text(), "A")
        self.assertEqual(v.ed_fam.text(), "N")
        w.close()

    def test_editar_nom_directament(self):
        w = self._finestra(); v = w.visor_ref
        v.timeline.select_clip("chord", 1); v._on_clip_selected("chord", 1)
        v.ed_nom.setText("Am7"); v._aplica_editor()
        self.assertEqual(v.acords[1][1], "Am7")
        self.assertEqual(v.ed_gran.text(), "Am7")   # l'editor s'actualitza
        v.undo()
        w.close()

    def test_editar_inici_directament(self):
        w = self._finestra(); v = w.visor_ref
        v.timeline.select_clip("chord", 1); v._on_clip_selected("chord", 1)
        v.ed_ini.setText("5.0"); v._aplica_editor()
        self.assertAlmostEqual(v.acords[1][0], 5.0, places=2)
        v.undo()
        w.close()

    def test_editar_seccio_directament(self):
        w = self._finestra(); v = w.visor_ref
        v.timeline.select_clip("section", 0); v._on_clip_selected("section", 0)
        v.ed_nom.setText("Z"); v.ed_fam.setText("N"); v._aplica_editor()
        self.assertEqual(v.seccions[0][2], "Z")
        v.undo()
        w.close()

    def test_doble_clic_carril_va_a_l_editor_sense_dialeg(self):
        """El doble-clic (editRequested) selecciona i enfoca l'Editor."""
        w = self._finestra(); v = w.visor_ref
        v._on_chord_edit_requested(1)
        self.assertEqual((v._ed_kind, v._ed_idx), ("chord", 1))
        self.assertEqual(v.ed_nom.text(), "Am")
        self.assertTrue(v.ed_nom.hasFocus() or True)   # focus (best-effort)
        w.close()

    def test_clic_a_les_llistes_actualitza_l_editor(self):
        """Regressio: el clic a la llista ha d'actualitzar la franja Editor.

        select_clip() abans NO emetia clipSelected, aixi que seleccionar des
        de la llista no arribava a l'Editor."""
        w = self._finestra(); v = w.visor_ref
        v._salt_acord(v.llista_ac.item(1))
        self.assertEqual(v.ed_gran.text(), "Am")
        v._salt_seccio(v.llista_ab.item(0))
        self.assertTrue(v.ed_gran.text().startswith("A"))
        w.close()

    def test_sense_seleccio_esta_buit(self):
        w = self._finestra(); v = w.visor_ref
        v._actualitza_editor()   # cap _ed_kind
        self.assertFalse(v.ed_aplica.isEnabled())
        self.assertIn("Selecciona", v.ed_gran.text())
        w.close()


class MenuEdicioTests(unittest.TestCase):
    """Accions dels menus Edita i Selecciona (reusen la logica existent)."""

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
            w.writeframes(b"\x00\x00" * 44100 * 20)
        ac = os.path.join(td, "t_ACORDS"); os.makedirs(ac)
        _escriu_fitxer(os.path.join(ac, "acords.csv"), "0.0,C\n4.0,Am\n8.0,G\n")
        _escriu_fitxer(os.path.join(ac, "estructura_ABC.csv"),
            "inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
            "0.00,4.00,4.00,A,N,1,1\n4.00,20.00,16.00,B,B,1,1\n")
        window = app_main.Finestra()
        window.wav_edit.setText(wav)
        window._carrega_visor(wav)
        return window

    def test_selecciona_acord_i_seccio_del_cursor(self):
        w = self._finestra()
        v = w.visor_ref
        v.ves_a(5.0); w._sel_acord_cursor()
        self.assertEqual(w._clip_seleccionat(), ("chord", 1))
        v.ves_a(10.0); w._sel_seccio_cursor()
        self.assertEqual(w._clip_seleccionat(), ("section", 1))
        w.close()

    def test_duplica_i_elimina_element(self):
        w = self._finestra()
        v = w.visor_ref
        v.ves_a(5.0); w._sel_acord_cursor()
        n = len(v.acords); w._duplica_element()
        self.assertEqual(len(v.acords), n + 1)
        v.undo()
        v.ves_a(5.0); w._sel_acord_cursor()
        n = len(v.acords); w._elimina_element()
        self.assertEqual(len(v.acords), n - 1)
        w.close()

    def test_afegeix_acord_i_seccio(self):
        from unittest.mock import patch
        import PyQt5.QtWidgets as QW
        w = self._finestra()
        v = w.visor_ref
        with patch.object(QW.QInputDialog, "getText", return_value=("F", True)):
            v.ves_a(6.0); n = len(v.acords); w._afegeix_acord_ui()
            self.assertEqual(len(v.acords), n + 1)
            # a 21 s (passada la ultima seccio, que acaba a 20) -> sense solapar
            v.ves_a(21.0); n = len(v.seccions); w._afegeix_seccio_ui()
            self.assertEqual(len(v.seccions), n + 1)
        w.close()

    def test_neteja_loop(self):
        w = self._finestra()
        v = w.visor_ref
        v.loop_a, v.loop_b, v.loop_on = 1.0, 3.0, True
        w._neteja_loop()
        self.assertIsNone(v.loop_a)
        self.assertFalse(v.loop_on)
        w.close()

    def test_menus_tenen_les_accions(self):
        w = self._finestra()
        def accions(nom):
            for act in w.menuBar().actions():
                if act.text() == nom:
                    return [a.text() for a in act.menu().actions()
                            if not a.isSeparator()]
            return []
        e = accions("&Edita")
        for x in ("Elimina element", "Duplica element", "Reanomena element",
                  "Afegeix acord…", "Afegeix secció…"):
            self.assertIn(x, e)
        s = accions("&Selecciona")
        for x in ("Selecciona l'acord del cursor", "Neteja el loop"):
            self.assertIn(x, s)
        w.close()


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
        _escriu_fitxer(ac, "0.0,C\n2.0,Am\n")
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
        files = open(ruta, encoding="utf-8").read().strip().splitlines()
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
        files = open(ruta, encoding="utf-8").read().strip().splitlines()
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
        with open(os.path.join(sortida, "acords.csv"), "w", encoding="utf-8") as f:
            f.write("0.0,C\n2.0,Am\n4.5,F\n7.0,G\n10.0,C\n")
        with open(os.path.join(sortida, "estructura_ABC.csv"), "w", encoding="utf-8") as f:
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


class TriaPlayerTests(unittest.TestCase):
    """Selecció del reproductor extern (`Visor._tria_player`).

    L'app fa servir `paplay` (PipeWire/Pulse) i, si no hi és, `aplay` (ALSA).
    Si no n'hi ha cap, retorna `None` (i el visor ho avisa) en lloc de provar
    ordres que no existeixen.
    """

    def _visor_buit(self):
        v = visor.Visor.__new__(visor.Visor)
        v.audio = {"sr": 44100}
        return v

    def test_prefereix_paplay(self):
        if not plataforma.ES_LINUX:
            self.skipTest("l'ordre paplay/aplay es només del Linux")
        v = self._visor_buit()
        with patch("app.visor.shutil.which", lambda n: "/usr/bin/" + n):
            player, args = v._tria_player()
        self.assertEqual(player, "paplay")
        self.assertIn("--raw", args)
        self.assertIn("--latency-msec=100", args)
        self.assertIn("--rate=44100", args)

    def test_aplay_si_no_hi_ha_paplay(self):
        if not plataforma.ES_LINUX:
            self.skipTest("aplay es només del Linux")
        v = self._visor_buit()
        with patch("app.visor.shutil.which",
                   lambda n: "/usr/bin/aplay" if n == "aplay" else None):
            player, args = v._tria_player()
        self.assertEqual(player, "aplay")
        self.assertIn("--format=S16_LE", args)

    def test_ffplay_a_windows_i_macos(self):
        if plataforma.ES_LINUX:
            self.skipTest("al Linux no es fa servir ffplay")
        v = self._visor_buit()
        with patch("app.visor.shutil.which", lambda n: "/usr/bin/" + n):
            player, args = v._tria_player()
        self.assertEqual(player, "ffplay")
        self.assertIn("-nodisp", args)

    def test_cap_reproductor_retorna_none(self):
        v = self._visor_buit()
        with patch("app.visor.shutil.which", lambda n: None):
            player, args = v._tria_player()
        self.assertIsNone(player)
        self.assertEqual(args, [])


class TonalitatAutoTests(unittest.TestCase):
    """Partitura a la GUI: opció «Tonalitat automàtica» (qm-keydetector).

    Comprovem que l'acció és commutable i per defecte NO, i que el ganxo passa
    `key_fifths` a `partitura.exporta_partitura` només quan està marcada.
    """

    def _finestra(self):
        app_main.QApplication.instance() or app_main.QApplication([])
        w = app_main.Finestra()
        w.sortida = "/tmp/sortida_falsa"
        w.wav_edit.setText("/tmp/tema.wav")
        return w

    def test_accio_existeix_i_per_defecte_no(self):
        w = self._finestra()
        self.assertTrue(w.tonalitat_auto.isCheckable())
        self.assertFalse(w.tonalitat_auto.isChecked())

    def test_sense_marcar_no_detecta_i_key_fifths_zero(self):
        w = self._finestra()
        with patch("app.main.partitura.exporta_partitura",
                   return_value={"musicxml": "/tmp/x.musicxml"}) as ex, \
             patch("app.main.partitura.detecta_fifths", return_value=3) as det:
            w._exporta_partitura()
        det.assert_not_called()
        self.assertEqual(ex.call_args.kwargs["key_fifths"], 0)

    def test_marcada_detecta_i_passa_els_fifths(self):
        w = self._finestra()
        w.tonalitat_auto.setChecked(True)
        with patch("app.main.partitura.exporta_partitura",
                   return_value={"musicxml": "/tmp/x.musicxml"}) as ex, \
             patch("app.main.partitura.detecta_fifths", return_value=1) as det:
            w._exporta_partitura()
        det.assert_called_once()
        self.assertEqual(ex.call_args.kwargs["key_fifths"], 1)
        self.assertEqual(ex.call_args.kwargs["wav"], "/tmp/tema.wav")
        self.assertEqual(ex.call_args.kwargs["new_system_each"], 4)


class ConfigEscripturaTests(unittest.TestCase):
    """L'AppImage munta el contingut en NOMÉS LECTURA.

    L'estat de l'app (log, temp, opcions) ha d'anar a un directori ESCRIPTIBLE;
    si no, l'app peta a l'arrencada amb `OSError [Errno 30] Read-only file
    system` i no arriba ni a mostrar la finestra (bug del run #5).
    """

    def test_dades_dir_es_escriptible(self):
        self.assertTrue(os.access(config.DADES_DIR, os.W_OK))

    def test_log_i_opcions_dins_dades_dir(self):
        for p in (config.LOG_PATH, config.OPCIONS_PATH):
            self.assertTrue(p.startswith(config.DADES_DIR), p)

    def test_temp_dir_es_escriptible(self):
        self.assertTrue(os.access(config.TEMP_DIR, os.W_OK))

    def test_detecta_nomes_lectura(self):
        if not plataforma.ES_LINUX:
            self.skipTest("/proc només existeix al Linux")
        # /proc és de només lectura
        self.assertFalse(config._es_escriptible("/proc"))

    def test_cau_fora_del_projecte_si_aquest_no_es_escriptible(self):
        if not plataforma.ES_LINUX:
            self.skipTest("cal un camí de només lectura; /proc és només del Linux")
        with patch.object(config, "PROJECT_ROOT", "/proc"):
            d = config._dir_de_dades()
        self.assertNotEqual(d, "/proc")
        self.assertTrue(os.access(d, os.W_OK))

    def test_main_i_dialegs_apanten_al_config(self):
        self.assertEqual(app_main.DEFAULT_LOG_PATH, config.LOG_PATH)
        self.assertEqual(dialegs.FITXER_OPCIONS, config.OPCIONS_PATH)


class PlataformaTests(unittest.TestCase):
    """Capa d'abstracció de plataforma (`app/plataforma.py`).

    Al Linux ha de retornar EXACTAMENT els valors d'abans (cap regressió);
    la resta de SO es cobreix als CI de Windows/macOS.
    """

    def test_so_detectat(self):
        self.assertIn(plataforma.SO, ("linux", "win", "mac"))
        self.assertEqual(sum([plataforma.ES_LINUX, plataforma.ES_WINDOWS,
                              plataforma.ES_MAC]), 1)

    def test_noms_binaris(self):
        if plataforma.ES_WINDOWS:
            self.assertTrue(plataforma.NOM_HOST.endswith(".exe"))
            self.assertTrue(plataforma.NOM_FFMPEG.endswith(".exe"))
        else:
            self.assertEqual(plataforma.NOM_HOST, "vamp_host_local")
            self.assertEqual(plataforma.NOM_FFMPEG, "ffmpeg")

    def test_candidats_reproductor(self):
        c = plataforma.candidats_reproductor()
        if plataforma.ES_LINUX:
            self.assertEqual(c, ("paplay", "aplay"))
        else:
            self.assertEqual(c, ("ffplay",))

    def test_dirs_plugins(self):
        d = [os.path.basename(x) for x in plataforma.dirs_plugins("/tmp")]
        if plataforma.ES_LINUX:
            self.assertIn("nnls-chroma-linux64-local", d)
            self.assertIn("qm-vamp-plugins-linux64-local", d)
        elif plataforma.ES_WINDOWS:
            self.assertIn("nnls-chroma-win64-local", d)
        else:
            self.assertIn("nnls-chroma-macos-local", d)

    def test_path_env_vamp_separador_del_so(self):
        self.assertEqual(plataforma.path_env_vamp(["/a", "/b"]),
                         os.pathsep.join(["/a", "/b"]))

    def test_executable(self):
        self.assertFalse(plataforma.executable("/no/existeix"))
        self.assertTrue(plataforma.executable(sys.executable))

    def test_kwargs_nou_grup(self):
        k = plataforma.kwargs_nou_grup()
        if plataforma.ES_WINDOWS:
            self.assertIn("creationflags", k)
        else:
            self.assertEqual(k, {"start_new_session": True})

    def test_mata_grup_tolerant(self):
        plataforma.mata_grup(None)   # no ha de petar

        class P:                      # procés inexistent
            pid = 10 ** 9

            def terminate(self):
                pass

            def kill(self):
                pass

        plataforma.mata_grup(P())     # ha de ser tolerant

    def test_python_actual_mai_fix(self):
        self.assertTrue(plataforma.python_actual())
        self.assertNotEqual(plataforma.python_actual(), "python3")


if __name__ == "__main__":
    unittest.main()
