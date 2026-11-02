# Notes de verificació del pla de tempo

## Fase 0 — línia base i corpus

- La línia base abans dels canvis d'aquesta fase: **1.411 tests correctes,
  1 omés**, i `pyflakes` net. Després dels canvis: **1.417 tests correctes,
  1 omés**, `pyflakes` net i sense diagnòstics Pylance al nou avaluador. No
  s'ha incorporat cap àudio comercial ni cap corpus real.
- `eines/avalua_tempo.py` accepta una carpeta local d'anotacions
  `*.tempo.json`. Cada anotació apunta a un àudio WAV i declara BPM de
  referència, compàs 1, canvis de tempo/compàs i passatges rubato. El CSV
  inclou error de BPM, error del compàs 1, alineació dels compassos dins
  ±70 ms, compassos sobrants/absents, error màxim i deriva, a més del temps.
- L'error màxim usa el downbeat detectat més proper per a cada downbeat de
  referència; la deriva compara el primer i l'últim emparellament correcte dins
  ±70 ms. Els sobrants/absents i el percentatge també usen emparellament
  un-a-un.
- `--prova-sintetica` verifica l'avaluació i els casos buits sense executar
  detectors ni necessitar plugins. Sense corpus no s'inventa cap línia base:
  l'eina ho indica com «Sense dades».
- Exemple d'anotació:

  ```json
  {
    "audio": "canço.wav",
    "bpm": 120,
    "num": 4,
    "den": 4,
    "compas_1_s": 0.0,
    "canvis": [[16.0, 96, 4, 4]],
    "rubatos": [[32.0, 35.0]]
  }
  ```

  Els canvis tenen la forma `[instant_s, bpm, numerador, denominador]`; també
  s'accepten objectes amb els camps `t`, `bpm`, `num` i `den`. El corpus i els
  seus resultats queden fora del repositori llevat d'autorització expressa.

## Comprovacions del codi existents

### a) Destí del TAP i re-tempo

`Visor.edita_tempo_objectiu` crida `tempo_map.canvia_bpm_local`, que aplica el
re-tempo local del contracte §13.5. Amb `desa=False`, el TAP manté els canvis en
memòria i el seu tancament els desa com una sessió.

### b) Accés a l'anàlisi guiada v3

El control visible «Anàlisi guiat» de `app/main.py` mostra una guia
informativa. El mètode v3 `_analisi_ancoratges` existeix en la mateixa finestra,
però no és l'acció connectada a aquell control. Els tests GUI actuals fixen
aquest comportament.

### c) Cobertura de les regles actuals

- Regles 1–8 i 10–12: els tests indicats pel contracte a
  `docs/REGLES_DE_LA_APP.md`, especialment `tests/test_edicio.py`,
  `tests/test_pipeline.py` i el fuzzer de vista de `tests/test_gui.py`.
- Regla 9 (AVX/portabilitat): `GuardAvxTests` a `tests/test_pipeline.py`;
  comprovacions de paquets multi-SO també viuen als scripts de `eines/` i CI.
- §13 (temps/compàs/graella): `tests/test_tempo_map.py`,
  `tests/test_tempo_trams.py`, `tests/test_despatx_edicio.py`,
  `tests/test_edicio.py` (`TestUndoTemps`, `TestLlistaTempo`) i
  `tests/test_pipeline.py`.
- §13.9 (edició d'àudio): `tests/test_audio_edit.py`, `tests/test_exporta_audio.py`
  i les classes `TestEdicioAudioVisor`, `TestNansesAudioTimeline` i
  `TestBackups` a `tests/test_gui.py`. L'exportació d'àudio s'ha implementat a
  la Fase 6; la restauració de backup des de la GUI continua sense implementar.

## Seguiment de Pylance

Els diagnòstics `reportArgumentType` venien de llegir camps opcionals del JSON
i passar valors `None | Unknown` a `float()`/`int()`. L'avaluador ara valida
els tipus i els valors numèrics a l'entrada, i Pylance retorna zero
diagnòstics per a `eines/avalua_tempo.py`. Les proves de l'avaluador (6),
`pyflakes` i `git diff --check` també passen després d'aquest ajust.

## Ús

```bash
.venv/bin/python eines/avalua_tempo.py --prova-sintetica
.venv/bin/python eines/avalua_tempo.py --corpus /ruta/local/corpus \
  --csv /ruta/local/resultats.csv
```
