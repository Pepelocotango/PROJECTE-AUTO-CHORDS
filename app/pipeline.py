#!/usr/bin/env python3
# pipeline.py — motor de l'Auto Chords (stdlib + binaris del projecte).
# Cadena: wav -> csv acords (annotator+Chordino) -> guia ->
#         wavs_acords (+ qm-segmenter -> ABC -> wavs_estructura, opcional).
# Tot en català.
import os
import time  # patch.object(pipeline.time/os, ...) als tests

from .pipeline_model import (  # noqa: F401  (re-exportats per compatibilitat)
    TOL_TEMPS, MIN_GAP_TEMPS, TEMPS_DEC, RESOLUCIO_CSV,
    SENSE_SECCIO, SENSE_ACORD, FORAT_ACORD, FORAT_SECCIO,
    Clip, clips_d_acords, acords_de_clips, clips_de_seccions,
    seccions_de_clips, normalitza_clips, model_inicial,
    normalitza_cobertura, parteix_clips, fusiona_clips,
    redimensiona_clips, mou_bloc_clips, elimina_clips,
    duplica_clips, duplica_bloc_clips,
)
from .pipeline_io import (
    safe_filename, saneja_nom_acord, PREFIX_SORTIDA, carpeta_sortida,
    PREFIXOS_TMP, esborra_tmp, escriu_atomic, desa_acords_csv,
    neteja_wavs,
)
from .pipeline_edicio import (
    parteix_acord, fusiona_acords, mou_bloc_acords, redimensiona_acord,
    redimensiona_seccio, mou_bloc_seccions, parteix_seccio, fusiona_seccions,
    elimina_seccio, duplica_bloc_seccions, valida_canvis_acords,
    valida_canvis_seccions, contiguitat_seccions, bloc_sobre_acords,
    bloc_sobre_seccions, renomena_acords_model, renomena_seccions_model,
    substitueix_en_model,
)
from .pipeline_mapa import (
    NOM_MAPA_TEMPO, NOM_MARCADORS, desa_marcadors, llegeix_marcadors,
    llegeix_marcadors_tipus, desa_tempo_map, llegeix_tempo_map,
)
from .pipeline_derivats import (
    segments_locators, events_partitura, segments_exactes, segments_export,
    genera_guia_html, pos_compas, seq_abc,
)
from .pipeline_estructura import (
    filtra_seccions, desa_abc_csv, regenera_wavs_estructura, fer_abc,
    style, segments_lliures, fer_wavs_estructura,
)
from .pipeline_export import (
    fer_wavs_acords_lliures, fer_wavs_acords, escriu_manifest,
    exporta_total, regenera_wavs_acords,
)
from .pipeline_vamp import (
    APP_DIR, PROJ_DIR, VAMP_DIRS, HOST, STEPS, CHORDS_TRANSFORM, MOTORS_BPM, MOTORS_ESTRUCTURA,
    QM, run, wav_info, retalla_wav, executa_transform, extract_chords,
    detecta_bpm_qm,
    detecta_bpm, detecta_bpm_tram, detecta_bpm_tram_detallat,
    detecta_bpm_detallat, detecta_tempo_per_trams, detecta_beats,
    detecta_compas1, extract_segments,
)

# Superfície pública del mòdul. Inclou els re-exports del model i la resta de
# funcions que fan servir `main.py`, `visor.py`, les eines i els tests.
__all__ = [
    "os", "time", "APP_DIR", "PROJ_DIR", "PREFIX_SORTIDA", "PREFIXOS_TMP",
    "VAMP_DIRS", "HOST", "STEPS",
    "CHORDS_TRANSFORM", "MOTORS_BPM", "MOTORS_ESTRUCTURA", "QM",
    "TOL_TEMPS", "MIN_GAP_TEMPS", "SENSE_ACORD", "SENSE_SECCIO",
    "FORAT_ACORD", "FORAT_SECCIO", "TEMPS_DEC", "RESOLUCIO_CSV",
    "NOM_MAPA_TEMPO", "NOM_MARCADORS",
    "Clip", "clips_d_acords", "acords_de_clips", "clips_de_seccions",
    "seccions_de_clips", "normalitza_clips", "model_inicial",
    "normalitza_cobertura",
    "safe_filename", "saneja_nom_acord", "carpeta_sortida", "esborra_tmp",
    "run", "wav_info", "retalla_wav", "executa_transform",
    "extract_chords", "detecta_bpm_qm", "detecta_bpm", "detecta_bpm_tram",
    "detecta_bpm_tram_detallat", "detecta_bpm_detallat",
    "detecta_tempo_per_trams", "detecta_beats", "detecta_compas1",
    "extract_segments", "filtra_seccions",
    "segments_locators", "events_partitura", "segments_exactes",
    "segments_export", "genera_guia_html", "pos_compas", "seq_abc",
    "parteix_clips", "fusiona_clips", "parteix_acord", "fusiona_acords",
    "mou_bloc_acords", "redimensiona_acord", "redimensiona_clips",
    "redimensiona_seccio", "mou_bloc_clips", "mou_bloc_seccions",
    "parteix_seccio", "fusiona_seccions", "elimina_clips", "elimina_seccio",
    "duplica_clips", "duplica_bloc_clips", "duplica_bloc_seccions",
    "valida_canvis_acords", "valida_canvis_seccions", "contiguitat_seccions",
    "bloc_sobre_acords", "bloc_sobre_seccions", "renomena_acords_model",
    "renomena_seccions_model", "substitueix_en_model",
    "desa_abc_csv", "regenera_wavs_estructura", "fer_abc", "style",
    "segments_lliures", "fer_wavs_acords_lliures", "fer_wavs_acords",
    "escriu_manifest", "exporta_total", "escriu_atomic", "desa_acords_csv",
    "desa_marcadors", "llegeix_marcadors", "llegeix_marcadors_tipus",
    "desa_tempo_map", "llegeix_tempo_map", "neteja_wavs",
    "regenera_wavs_acords", "fer_wavs_estructura",
]
