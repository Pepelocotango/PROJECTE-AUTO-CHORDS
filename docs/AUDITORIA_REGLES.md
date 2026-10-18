# 🔍 AUDITORIA DE LES REGLES D'OR — revisió contínua

> Revisió exhaustiva de `docs/REGLES_DE_LA_APP.md` contra **tot** el codi,
> demanada per l'operador de manera **recurrent** (cada ~30 min). Aquest fitxer
> és el **registre**: què ja s'ha auditat, què s'ha trobat i què queda, per
> reprendre la feina sense perdre el fil.

## Com s'audita (mètode)

Per a **cada regla** es comproven tres coses, en aquest ordre:

1. **La validació existeix i és completa** — la que la regla cita al peu
   (`→ …`). Si la regla diu «`pipeline.normalitza_cobertura()`», s'ha de veure
   que realment garantisca allò que la regla diu, **sense forats**.
2. **Tots els camins hi passen** — hi ha 4 camins que han de complir-les
   *sempre* (ho diu el §«S'ha de complir SEMPRE»): **edició en viu** (visor),
   **MCP**, **CSV desat** i **exportació**; més la **càrrega** (un CSV editat a
   mà o un projecte vell no hi poden entrar trencant res).
3. **El test mou el cas de veritat** — no un cas semblant: el test ha de poder
   fallar si es trenca la regla.

El que no es complisca → **fix + test** el mateix dia, i s'anota ací.

## Mapa regla → validació → test

| # | Regla | Validació al codi | Test | Estat |
|---|---|---|---|---|
| 1 | Ordre estricte | `visor._valida_canvis_acords` / `_valida_canvis_seccions` · `pipeline.normalitza_cobertura` (reordena) · `tempo_map.normalitza_trams` (ordena i deduplica) | `test_regles_or.TestRegla1OrdreEstricte` · `test_tempo_map` | ✅ auditada als 3 nuclis i a la càrrega (Ronda 2) |
| 2 | Contigüitat | `pipeline.filtra_seccions` · els normalitzadors dels 3 tipus (`prev.fi == curr.ini`) | `test_seccions_contigues` | 🟡 auditada al mapa (Ronda 2); **falta** el repàs complet dels 3 tipus |
| 3 | Durades derivades | el `fi` del `Clip` **no mana**: es re-deriva de la frontera (cadena d'inis) | `test_regles_or.TestRegla3DuradesDerivades` | ✅ auditat |
| 4 | Cobertura total | `pipeline.normalitza_cobertura()` (acords + seccions) · `tempo_map.normalitza_trams(trams, durada)` (mapa) | `test_cobertura_viu` | 🟡 auditada; **falta** comprovar-ho després de cada mutació del mapa (undo/porta-retalls/MCP) |
| 5 | Una sola font de veritat | `pipeline` + `tempo_map` (2 backends); la còpia del visor mai no mana | `test_regles_or.TestRegla5FontDeVeritat` | ⏳ pendent de repàs (buscar mutacions de la UI que no passin pel backend) |
| 6 | WAVs només via `exporta_total()` | `pipeline.exporta_total` / `regenera_wavs_*` | `test_regles_or.TestRegla6WavsNomesViaExporta` | 🟡 auditada; **falta** recórrer tots els cridadors de `regenera_wavs_*` |
| 7 | Instància única | `plataforma.bloqueja_instancia_unica` | `test_regles_or.TestRegla7InstanciaUnica` | ✅ auditat |
| 8 | Temps vàlids | `visor._valida_canvis_*` **+** les xarxes de seguretat (`normalitza_cobertura`, `normalitza_trams`) | `test_regles_or.TestRegla8TempsValids` | ✅ auditat (Ronda 1: 2 forats arreglats) |
| 9 | Portabilitat i maquinari (3 SO, sense AVX) | CI (`eines/verifica_minos_macos.py`) · build genèric · `tests/test_requirements.py` | `test_requirements` | ✅ auditat al que és verificable des d'ací |
| 10 | Estat en directori escriptible | `app/config.py` (prova d'escriptura real) | `test_regles_or.TestRegla10EstatEscriptible` | ✅ auditat |
| 11 | Paritat d'edició i tracte visual | el joc simètric a `app/visor.py` + `app/pipeline.py` + `app/tempo_map.py` | `test_regla11_paritat` | 🟡 auditada; **falta** repàs camí a camí (MCP inclòs) |
| 12 | Paritat d'exportació (paquet complet) | — | — | ⛔ **PENDENT D'IMPLEMENTACIÓ, ASSIGNAT A PART** (un altre agent; `docs/REGLES_DE_LA_APP.md` §12). **No tocar des d'ací.** |

## Trobades i fixes (el més nou a dalt)

### 2026-10-18 · Ronda 2 — Regles 1/2/4 al CAMÍ DE CÀRREGA del mapa

- 🐞 `pipeline.llegeix_tempo_map` retornava els trams **tal com són als CSVs**
  (`tempo.csv` + `compas.csv`). Com que aquests fitxers es poden editar a
  mà, hi podia entrar un mapa amb **forat** (un tram que no arrenca a 0),
  un inici **negatiu** o un `bpm`/compàs **impossibles**, i a més la còpia
  `self.tempo_trams` quedava diferent de l'objecte `TempoMap` (regla 5).
  → la càrrega ara passa el resultat per `tempo_map.normalitza_trams` amb
  la durada de la WAV: ordre (#1), contigüitat (#2), cobertura 0→durada
  (#4) i valors vàlids (#8).

Test nou: `test_tempo_map.TestPersistencia.test_csv_editat_a_ma_entra_normalitzat`.

### 2026-10-18 · Ronda 1 — Regla 8 als normalitzadors (2 forats reals)

Els validators del visor (`_valida_canvis_acords` / `_valida_canvis_seccions`)
**sí** que rebutgen temps negatius, però les **xarxes de seguretat** (les que
cobreixen el CSV editat a mà, els projectes vells i els clients de l'MCP)
deixaven passar valors impossibles:

- 🐞 `tempo_map.normalitza_trams`: un tram amb inici **−5 s** es quedava igual;
  un `bpm` **0** i un compàs **0/0** també. → ara l'inici s'acota a **0** i els
  valors no positius van al vàlid (`BPM_DEFECTE = 120.0`, compàs 4/4, el mateix
  que fa `TempoMap`).
- 🐞 `pipeline.normalitza_cobertura`: un acord a **−2 s** hi sobrevivia; les
  seccions negatives també. → els acords es porten a **0** (la cobertura ja hi
  posa la capçalera/el forat que calgui) i les seccions es retallen a 0 o
  s'eliminen si són **senceres** abans de la WAV.

Test nou: `tests/test_regles_or.py` › `test_les_xarxes_de_seguretat_tambe_ho_arreglen`.

## Cua (properes rondes)

1. **R2 a fons** — la contigüitat de les **3** famílies, incloent-hi el camí de
   càrrega (CSV amb forats/encavalcaments editats a mà).
2. **R4** — comprovar que el **mapa de tempo** es re-normalitza després de
   **cada** mutació (com fa la cobertura): visor, MCP, porta-retalls, undo.
3. **R5** — caçar mutacions de la UI que no passin pels backends
   (`pipeline`/`tempo_map`).
4. **R6** — recórrer **tots** els cridadors de `regenera_wavs_*`: cap camí
   d'edició no pot escriure WAVs.
5. **R1** — el mapa: inis repetits/empatats (la deduplicació per `round(ini, 6)`).
6. **R11** — repàs camí a camí (GUI ↔ MCP ↔ porta-retalls ↔ undo) de les 3
   famílies.
7. **Neteja** de codi i tests obsolets que es vagen trobant pel camí.
8. **R12** — quan l'agent a càrrec la implemente, auditar-la ací (no tocar-la).

> 📌 **En tancar una ronda**: actualitza aquest mapa (l'✅/⏳ de cada regla) i
> apunta-hi les trobades amb el seu fix i test.
