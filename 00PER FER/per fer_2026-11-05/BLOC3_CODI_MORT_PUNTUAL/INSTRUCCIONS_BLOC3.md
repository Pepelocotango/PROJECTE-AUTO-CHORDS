# INSTRUCCIONS BLOC 3
Aplicar despres del BLOC 2.
Elimina codi mort puntual.
Veure DIFFS/bloc3.patch i MODIFICATS/.

Fitxers modificats:
- app/pipeline.py (duplica_acord, duplica_seccio)
- app/plataforma.py (proces_viu)
- app/tempo_map.py (clip_te_temps_sencer)
- app/metronom.py (_ha_de_sonar, _es_accent, beats_a_temps)
- app/main.py (_idx_acord_del_cursor, _idx_seccio_del_cursor, _idx_tram_del_cursor) - inclou BLOC2
- app/ffmpeg.py (VELOCITATS, estira_a_wav) - conserva ruta_velocitat, _es_mono_pcm16, _render, prepara_escolta

Validacio:
.venv/bin/python -m pyflakes app/*.py tests/*.py
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests
