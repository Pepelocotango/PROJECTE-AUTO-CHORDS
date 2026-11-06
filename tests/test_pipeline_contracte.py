"""Contracte de superfície de `app.pipeline` (refactor F0).

Congela els noms públics, la firma d'exportació i les constants que fan
servir la resta de mòduls i els tests. Serveix de xarxa de seguretat per a
la modularització de `pipeline.py` (F1).
"""
import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene: esborra els temporals en plegar

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest  # noqa: E402

from app import pipeline  # noqa: E402

NOMS_PUBLICS = (
    # Constants i configuració
    "PREFIX_SORTIDA", "PREFIXOS_TMP", "VAMP_DIRS", "HOST", "STEPS",
    "CHORDS_TRANSFORM", "MOTORS_BPM", "MOTORS_ESTRUCTURA", "QM",
    "TOL_TEMPS", "MIN_GAP_TEMPS", "SENSE_ACORD", "SENSE_SECCIO",
    "FORAT_ACORD", "FORAT_SECCIO", "TEMPS_DEC", "RESOLUCIO_CSV",
    "NOM_MAPA_TEMPO", "NOM_MARCADORS",
    # Tipus i model
    "Clip", "clips_d_acords", "acords_de_clips", "clips_de_seccions",
    "seccions_de_clips", "normalitza_clips", "model_inicial",
    "normalitza_cobertura",
    # Fitxers i ejecución externa
    "safe_filename", "saneja_nom_acord", "carpeta_sortida", "esborra_tmp",
    "run", "wav_info", "executa_transform",
    # Vamp i detectors
    "extract_chords", "detecta_bpm_qm", "detecta_bpm", "detecta_bpm_tram",
    "detecta_bpm_tram_detallat", "detecta_bpm_detallat",
    "detecta_tempo_per_trams", "detecta_beats", "detecta_compas1",
    "extract_segments", "filtra_seccions",
    # Derivats de guia/export
    "segments_locators", "events_partitura", "segments_exactes",
    "segments_export", "genera_guia_html", "pos_compas", "seq_abc",
    # Edició de clips
    "parteix_clips", "fusiona_clips", "parteix_acord", "fusiona_acords",
    "mou_bloc_acords", "redimensiona_acord", "redimensiona_clips",
    "redimensiona_seccio", "mou_bloc_clips", "mou_bloc_seccions",
    "parteix_seccio", "fusiona_seccions", "elimina_clips", "elimina_seccio",
    "duplica_clips", "duplica_bloc_clips", "duplica_bloc_seccions",
    "valida_canvis_acords", "valida_canvis_seccions", "contiguitat_seccions",
    "bloc_sobre_acords", "bloc_sobre_seccions", "renomena_acords_model",
    "renomena_seccions_model", "substitueix_en_model",
    # Estructura, export i CSV/mapa
    "desa_abc_csv", "regenera_wavs_estructura", "fer_abc", "style",
    "segments_lliures", "fer_wavs_acords_lliures", "fer_wavs_acords",
    "escriu_manifest", "exporta_total", "escriu_atomic", "desa_acords_csv",
    "desa_marcadors", "llegeix_marcadors", "llegeix_marcadors_tipus",
    "desa_tempo_map", "llegeix_tempo_map", "neteja_wavs",
    "regenera_wavs_acords", "fer_wavs_estructura",
)


class TestSuperficiePipeline(unittest.TestCase):
    def test_tots_els_noms_publics_existeixen(self):
        for nom in NOMS_PUBLICS:
            self.assertTrue(hasattr(pipeline, nom), f"falta pipeline.{nom}")

    def test_firma_exporta_total(self):
        params = inspect.signature(pipeline.exporta_total).parameters
        for nom in ("acords", "seccions", "mapa_tempo", "sortida", "log"):
            self.assertIn(nom, params, f"falta el paràmetre {nom}")

    def test_os_i_time_visibles_per_als_patches(self):
        self.assertTrue(hasattr(pipeline, "os"))
        self.assertTrue(hasattr(pipeline, "time"))

    def test_clip_es_el_tipus_compartit(self):
        c = pipeline.Clip(0.0, 1.0, ("C", "0"))
        self.assertEqual((c.ini, c.fi, c.nom), (0.0, 1.0, "C"))
        self.assertIsInstance(c, tuple)

    def test_constants_de_precisio(self):
        self.assertEqual(pipeline.TEMPS_DEC, 6)
        self.assertAlmostEqual(pipeline.RESOLUCIO_CSV, 1e-6)
