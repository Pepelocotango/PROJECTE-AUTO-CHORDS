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

1. **S1 — Tipus i normalització únics**: `pipeline.Clip` + `normalitza_clips()` (un sol
   lloc per als invariants i els forats), amb adaptadors des del model actual. Cap
   canvi de comportament; la suite ha de quedar **verda sense tocar tests**.
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
