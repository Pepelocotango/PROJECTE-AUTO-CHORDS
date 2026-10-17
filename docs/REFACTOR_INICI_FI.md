# Refactor de base: model únic de clips amb **inici + fi**

> **Estat**: PUNT DE PARTIDA (taguejat `refactor-inici-fi`). Decisió de l'operador, 17-10-2026.
> **Abast**: es refactoritza TOT el model de dades i tot el codi d'edició que hi toca.

## Per què

Avui hi ha **dos models** per a la mateixa idea:

| | model actual | conseqüència |
|---|---|---|
| **Acords** | marques: només `temps` (el `fi` es deriva) | una implementació d'edició |
| **Estructura** | intervals: `ini` **i** `fi` explícits | una altra implementació |

Això obliga a **duplicar cada operació** (moure, estirar/encongir, partir, fusionar, eliminar…) i converteix la paritat **#11** en una cosa que cal vigilar amb tests, en comptes de ser estructuralment impossible de trencar.

L'origen de la divergència són els analitzadors (Chordino / qm-segmenter), que emeten
segments amb inici i fi, però el model editable de l'app es va quedar a mitges.

## Decisió

**Un sol model per a tots dos**: una llista de clips amb `inici` i `fi`.

- **CSV**: tots dos escriuen `inici,fi` (+ les columnes pròpies de les seccions).
- **Sense retrocompatibilitat** (decisió explícita de l'operador): si un projecte vell
  no s'obre, no passa res. No hi ha res important guardat.

## Model objectiu

- `Clip(ini, fi, payload)`.
  - `payload` (acord) = **nom de l'acord** (`Am`, `CMaj7`…).
  - `payload` (secció) = **lletra + família** (i les columnes extra que calguen).
- **Invariants** (els actuals #2 i #4, ara a tots dos): la cadena és **contigua** i
  **cobreix** `[0, durada)`; els forats es materialitzen amb `N` (acords) i `-`
  (estructura).
- **Font única de veritat**: la cadena de fronteres. El `fi` és **derivat** i es
  **re-deriva sempre** a la normalització (carregar, desar i després de cada operació)
  → una inconsistència `fi[i] ≠ ini[i+1]` és impossible d'arrossegar.

## Pla per fases (suite verda a cada fase)

1. **S1 — Tipus i normalització únics** ✅ **FET (2026-10-17)**: `pipeline.Clip`
   (`ini`, `fi`, `payload`) + `clips_d_acords` / `acords_de_clips` /
   `clips_de_seccions` / `seccions_de_clips` + `normalitza_clips(...)`. Cap canvi
   de comportament: la suite passa **sense tocar cap test** i un test nou
   (`tests/test_clips_unificats.py`) demostra l'**equivalència exacta** amb
   `normalitza_cobertura` sobre el corpus dels dos tipus.
2. **S2 — Una sola operació per acció**: `mou_bloc`, `redimensiona`, `parteix`,
   `fusiona`, `elimina`, `duplica` passen a **una única implementació** que serveix
   acords i estructura.
3. **S3 — CSV `inici,fi` als dos**: escriptors i lectors (seccions ja ho fan; acords
   passa a `inici,fi,acord`), sense cap camí de compatibilitat.
4. **S4 — Visor**: el model en memòria passa a clips amb `ini`+`fi` (vores ZONE_LEFT/
   ZONE_RIGHT incloses) i s'elimina el despatx `kind` duplicat.
5. **S5 — Exports i derivats**: WAVs, ABC, partitura, MusicXML, guia DAW
   (`acords_a_live.py`) i MCP al nou model.
6. **S6 — Neteja**: fora codi mort i helpers que ja no calguin; docs i CHANGELOG.

## Nota

Aquest fitxer és el contracte del refactor: si una fase obliga a canviar-lo, es
documenta aquí el perquè abans de seguir.

---

## Impacte en l'autoanàlisi (analitzat 2026-10-17)

**Conclusió: impacte BAIX i en positiu — l'autoanàlisi JA treballa amb intervals.**

1. **La capa CRUA no es toca** (`analisi/chords_raw.csv`, `analisi/segments_raw.csv`,
   `meta.json`): és la sortida dels plugins (Vamp host → CSV `inici, durada, …`) i és
   immutable per disseny. **Zero impacte** a: els plugins, `STEPS`, `executa_transform`,
   el host propi, temps/BPM (`tempo.py`), compàs 1, onsets/bars/beats — són temps
   escalars o intervals crus.
2. **Acords** (el cas que millora): avui `chords_raw.csv` (inici+durada) s'ha de
   **col·lapsar a marques** (`pipeline.regularitza_acords_csv` → `graella.regularitza_acords`
   → `postproc.processa_acords`), **es perd el `fi` del motor** i es re-deriva. Amb el
   model unificat la conversió passa a ser **1:1** (interval cru → `Clip`) i el fi real
   es conserva.
3. **Estructura**: `pipeline.fer_abc` + `graella.regularitza_seccions` +
   `pipeline.filtra_seccions` **ja** treballen amb intervals `[ini, fi, etiqueta]` i ja
   mantenen la contigüitat (`prev.fi == curr.ini`) → s'hi acoblen directament.
4. **Duplicació que desapareixerà**: `filtra_seccions(durada_min, fusiona_iguals)` i les
   `graella.regularitza_*` són el mateix tipus d'operació que les edicions del model →
   passaran a les operacions úniques de **S2** (no caldrà mantenir-ne dues versions).
5. **Semàntica a preservar** (criteri d'èxit de S1-S3): **el resultat visible de
   l'anàlisi no pot canviar**. L'adaptador ha de mantenir el comportament actual: els
   forats de la sortida crua s'absorbeixen al veí i els `N` del motor queden `N`.
6. **Punt únic de conversió**: `inici+durada → fi` en un sol helper.
7. **On impacta de veritat**: els tests que fixen el **format del MODEL** (marques) i els
   CSV del MODEL / `.acproj` (S3), i el MCP (S5). Els tests del parser i del postproc
   (funcions pures sobre llistes) **no s'han de tocar**.

