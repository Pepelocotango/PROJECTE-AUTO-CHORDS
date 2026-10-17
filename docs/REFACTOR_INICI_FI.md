# Refactor de base: model únic de clips amb **inici + fi**

> **ESTAT ACTUAL (2026-10-17) — tag `refactor-s4-fet` → S5 FET**
> - ✅ **S1** · ✅ **S2** · ✅ **S3** · ✅ **S4** · ✅ **S5**
> - ⏳ **S6 PENDENT** (neteja: wrappers de marques + ponts S4, docs, CHANGELOG)
>
> **Punt de partida**: taguejat `refactor-inici-fi` (decisió de l'operador, 17-10-2026).
> **Abast**: es refactoritza TOT el model de dades i tot el codi d'edició que hi toca.
> Detall de commits i del següent pas: `docs/AUTOPROMPT_REFACTOR.md`.

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
2. ✅ **FET — S2 «una sola operació per acció»**: `mou_bloc`, `redimensiona`,
   `parteix`, `fusiona`, `elimina`, `duplica` tenen **una única implementació**
   que serveix acords i estructura. **Fets**: S2a — vores (`redimensiona_clips`,
   `redimensiona_acord`, `redimensiona_seccio`); S2b — moure (`mou_bloc_clips`,
   `mou_bloc_acords`, `mou_bloc_seccions`, amb la **correcció §6.3**: el tros
   tallat conserva el nom); S2c — partir/fusionar (`parteix_clips`, `fusiona_clips`
   i wrappers); **elimina/duplica** (`elimina_clips`/`duplica_clips` + wrappers i
   handlers del visor, §6.4); **graella** (`regularitza_clips` = nucli únic de
   `regularitza_acords`/`regularitza_seccions`); **vores del gest** del visor
   (`ZONE_LEFT`/`ZONE_RIGHT`) enganxades a `redimensiona_clips`; **`filtra_seccions`**
   reabsorbit al model de clips (equivalència exacta verificada sobre 20.000
   casos) i **MCP d'`elimina`/`duplica`** alineat als nuclis.
3. ✅ **FET — S3 — CSV `inici,fi` als dos**: `acords.csv` passa a `inici,fi,acord`
   (escriptors `desa_acords_csv`/`postproc.processa_acords_csv` i **tots els
   lectors del model**: `visor.llegeix_acords`, `pipeline.segments_lliures`/
   `exporta_total`, `acords_a_live.py`), **sense retrocompatibilitat**. El `fi`
   es re-deriva sempre. Els **crus** d'anàlisi (`chords_raw.csv` / Chordino)
   queden en 2 columnes (són immutables).
4. ✅ **FET — S4 — Visor**: el model en memòria del visor (i del timeline) passa
   a clips `Clip(ini, fi, payload)` (el mateix model que l'estructura i el CSV,
   #11); `llegeix_acords`/`model_inicial` donen clips; validació i normalització
   (`_valida_canvis_acords`, `_normalitza_cobertura`) sobre clips; les operacions
   del visor van pels nuclis de clips; i **fora el despatx `kind` duplicat**
   (`Visor._aplica_carril`). Ponts `pipeline.nom_d_acord` / `_acords_a_clips`.
5. ✅ **FET — S5 — Exports i derivats**: els WAVs (`fer_wavs_acords`,
   `fer_wavs_estructura`), l'ABC, la partitura/MusicXML i la guia DAW
   (`acords_a_live.py`) consumeixen l'artefacte exportat o el CSV `inici,fi,acord`
   i funciona amb el model de clips; `exporta_total` normalitza explícitament els
   clips (`clips_de_model` + `normalitza_clips`); l'MCP ja edita clips (S4).
   Suite sencera verda (incloent-hi els tests d'export i partitura).
6. ⏳ **S6 — Neteja**: fora codi mort i helpers que ja no calguin (wrappers de
   **marques** `parteix_acord`/`fusiona_acords`/`mou_bloc_acords`/`redimensiona_
   acord`/`elimina_acord`/`duplica_acord` + `clips_d_acords`/`acords_de_clips`,
   un cop migrats els tests als nuclis de clips; ponts S4 `nom_d_acord`/
   `clips_de_model` si es poden eliminar); docs i `CHANGELOG`.

## Nota

Aquest fitxer és el contracte del refactor: si una fase obliga a canviar-lo, es
documenta aquí el perquè abans de seguir.

## Conducta canònica de MOURE un bloc (decisió de l'operador, 2026-10-17)

Regla §6.3, sense matisos: el bloc editat **mana**; el material que queda **a
sota** es **talla** si només queda cobert **en part**, i **s'elimina** si queda
**sobrepassat** del tot. El bloc **conserva la seva durada**; l'**origen** el
tanca el **veí** i, si no n'hi ha cap, el forat el posa el **normalitzador**
(`N` / `-`) — un sol lloc, mai l'operació.

**Cas de referència** (cançó `C[0,2) Am[2,4) F[4,6) G[6,8) Em[8,10)`): l'usuari
arrossega el clip **G** 3 s enrere (comença a 3 s). El bloc nou `[3,5)` **talla**
el `F` (que arriba a 6 s: **no** queda sobrepassat):

- ✅ **canònic**: `C[0,2) Am[2,3) G[3,5) F[5,6) Em[6,10)`
- ❌ conducta vella dels **acords** (marques): `… G[3,5) Em[5,10)` — el tros de
  `F` es **renombra** `Em` → pèrdua d'informació (i l'export etiqueta malament
  aquell tros).

Conseqüències per a **S2**:

1. El nucli únic és el d'**intervals** (`mou_bloc_clips`): clips amb `ini`+`fi`.
2. Els tests del moviment d'acords que fixaven la conducta vella s'**arreglen**,
   documentant-ho com a **correcció** d'aquest cas de referència.
3. El forat de l'origen **no** el posa l'operació: el posa el normalitzador
   unificat (`normalitza_clips` / `normalitza_cobertura`).

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

## Següent (pendent del refactor, en ordre)

1. **S5 — exports i derivats**: revisar que WAVs, ABC, partitura, MusicXML, la
   guia DAW (`acords_a_live.py`) i les eines MCP treballin ja amb el model de
   clips (des de S3 el CSV és `inici,fi,acord` i l'MCP ja edita clips); netejar
   els ponts que quedin.
2. **S6 — neteja**: codi mort, helpers sense ús, docs i CHANGELOG.

**Nuclis ja fets** (no duplicar-los mai): `normalitza_clips`, `redimensiona_clips`,
`mou_bloc_clips`, `parteix_clips`, `fusiona_clips`, `elimina_clips`,
`duplica_clips` (+ els wrappers dels dos tipus) i `graella.regularitza_clips`.
