# Domini audio/tempo (invariants)

Font: `docs/REGLES_DE_LA_APP.md` §13, `docs/TEMPO_PER_TRAMS.md`, `docs/GRAELLA_PPQ_TEMPS.md`, `docs/ANALISI_BPM.md`.

## Invariants clau

- **Downbeat (offset) absolut**: no es mou en ajustar BPM.
- **T (tap tempo)**: només amb clip de tempo seleccionat.
- **Beats sencers**: clips de BPM/compàs han de contenir almenys un beat sencer de la graella (QM o BPM/compàs), inclòs `1/4`.
- **`+`**: sempre usa el beat QM més pròxim; ajust prioritza conservar BPM i canviar compàs.
- **"Ajusta BPM al compàs"**: força compassos sencers explícitament.
- **Graella de corxera** (mig temps); posició en compàs.pols.
- **Unitat de BPM global** (negra/negra punt/corxera/blanca); model en negres/min; unitat de clic del metrònom independent.
- **Metrònom per denominador**: beat = 4/den negres (`6/8`, `9/8`, `12/8` cliquen corxeres; `2/2` blanques).
- **Mapa de tempo variable**: trams `[ini, fi)`; tram 0 pren valor del transport; resta del mapa.
- **Rubato**: model unificat `mapa_tempo.csv`, FORMAT=3; subplà complet (fases 1-5).

## Mòduls de domini

`app/tempo.py`, `app/tempo_map.py`, `app/mapa_tempo.py`, `app/rubato.py`, `app/graella.py`, `app/metronom.py`, `app/beats.py`, `app/tempo_ajust.py`, `app/marcadors.py`, `app/ancoratges.py`, `app/limits.py`.

## Comprovacions abans de canviar

1. Llegeix la regla §13 afectada.
2. Comprova la regla als 4 punts (edició en viu, visor, CSV, export).
3. Tests de regressió obligatoris (`test_tempo*`, `test_mapa_tempo`, `test_rubato`, `test_beats`).
4. No toquis UI (`visor.py`, `timeline.py`, `main.py`) des d'aquest domini; delega al primary.
5. Documenta canvis de comportament (avisa `docs`).
6. No reintrodueixis retrocompatibilitat (projectes vells es rebutgen amb error clar).

## Tests rellevants

`test_tempo_map`, `test_tempo_trams`, `test_tempo_ajust`, `test_mapa_tempo`, `test_rubato`, `test_beats`, `test_ancoratges`, `test_avalua_tempo`.
