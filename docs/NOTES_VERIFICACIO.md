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

## Fase 10 — motor de detecció (2026-11-03)

- **Estat**: en curs, **bloquejada per corpus real**. `eines/avalua_tempo.py
  --prova-sintetica` passa; no hi ha cap corpus local autoritzat al
  repositori ni cap `BASE.csv` inventat.
- **Projecte de prova**: `AUTOCHORDS_01 POLICE_convertit` serveix per comprovar
  la coherència del model (format 3, cobertura exacta, rubato inicial), però
  **no** és una veritat de terreny independent: el model ve de la mateixa
  anàlisi. No s'usa com a línia base.
- **Puntuació de downbeat amb acords**: proposta pendent; cal passar els
  canvis de Chordino al detector i mesurar sobre corpus. No s'ha canviat el
  detector per defecte.
- **Alternatives (revisió d'escriptori, sense instal·lar ni integrar)**:

  | Motor | Llicència | Requisits / cost | Q9400 | Decisió |
  |---|---|---|---|---|
  | qm actual (`qm-barbeattracker`) | la del projecte/Vamp | ja instal·lat; sense dependència nova | funciona | **default** |
  | `madmom` | codi BSD; **models CC BY-NC-SA** | PyPI 0.16.1 (2018); el README de Beat This! indica Py<3.10/numpy<1.20 per a eixe paquet; `main` pot requerir compilació | **no provat** | **no adoptar per defecte** (models no comercials + risc) |
  | Beat This! | **MIT** (codi i pesos) | PyTorch 2.0+; model 78 MB (small 8,1 MB); CPU | **no provat**; risc AVX de PyTorch | **candidat opcional**; cal prova de maquinari i empaquetat |

- **Conclusió**: no s'integra cap motor nou. El següent pas real és rebre un
  corpus autoritzat i mesurar l'alineació de la graella; després es pot
  comparar el qm amb Beat This! (opcional) i provar la puntuació de downbeat
  amb acords.

### Corpus manual de tempo (abast acordat 2026-11-03)

- **Abast**: només **tempo i compàs**; no calen acords, estructura ni
  partitura. L’avaluador actual mesura BPM, compàs 1 i alineació de la
  graella.
- **Ubicació**: carpeta local `CORPUS/` a l’arrel del projecte, **ignorada per
  Git**; no es versiona cap WAV ni cap anotació. Es pot tindre fora del
  repositori i passar la ruta amb `--corpus`.
- **Estructura**:

  ```text
  CORPUS/
  ├── 01_artista_titol/
  │   ├── audio.wav
  │   └── 01_artista_titol.tempo.json
  └── README.md
  ```

- **Anotació independent**: s’ha de fer des de l’àudio, amb DAW/orella/tap,
  **sense usar la sortida del detector**. Si s’anota dins AUTO CHORDS, no
  prémer «Analitza» ni acceptar la proposta automàtica; evitar el snap si
  arrossega a la graella del detector.
- **Camps mínims** per cançó: `audio`, `bpm` (negres/minut), `num`, `den`,
  `compas_1_s` (primer downbeat), `canvis` (`[t, bpm, num, den]`) i
  `rubatos` (`[inici_s, fi_s]`) si n’hi ha. No cal anotar cada beat.
- **Volum**: **3–5 cançons** per a la primera línia base; **15–20** per a
  l’acceptació final, amb tempo fix, canvi de tempo, canvi de compàs, rubato,
  silenci/anacrusi i estils diferents.
- **Comanda**:

  ```bash
  .venv/bin/python eines/avalua_tempo.py --corpus CORPUS \
    --csv /tmp/resultats_tempo.csv
  ```

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
