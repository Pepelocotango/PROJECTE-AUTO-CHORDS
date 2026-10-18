# 🔍 AUDITORIA DE LES REGLES D'OR — revisió contínua

> Revisió exhaustiva de `docs/REGLES_DE_LA_APP.md` contra **tot** el codi,
> demanada per l'operador de manera **recurrent** (cada ~30 min). Aquest fitxer
> és el **registre**: què ja s'ha auditat, què s'ha trobat i què queda, per
> reprendre la feina sense perdre el fil.

## Com s'audita (mètode)

**Prova de mutació** (per comprovar que els tests d'una regla *tenen dents*):
es trenca la validació **a posta** i es comprova que el test peta; després es
restaura (`git checkout --`). Si el test NO peta, el test no val — i això és
un test feble que s'ha de reescriure. Resultats de la Ronda 12: 5/5 mutacions
detectades.

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
| 2 | Contigüitat | `pipeline.filtra_seccions` · els normalitzadors dels 3 tipus (`prev.fi == curr.ini`) · `normalitza_cobertura` (encaixaments) · lectors | `test_seccions_contigues` · `test_regles_or` | ✅ auditada (Rondes 4 i 7: mapa, càrrega i encavalcaments) |
| 3 | Durades derivades | el `fi` del `Clip` **no mana**: es re-deriva de la frontera (cadena d'inis) | `test_regles_or.TestRegla3DuradesDerivades` | ✅ auditat |
| 4 | Cobertura total | `pipeline.normalitza_cobertura()` (acords + seccions) · `tempo_map.normalitza_trams(trams, durada)` (mapa) · **punt únic**: `visor._refresca_tempo_map` | `test_cobertura_viu` · `test_regles_or` | ✅ auditada (Ronda 3: el mapa es re-normalitza SEMPRE que es construeix) |
| 5 | Una sola font de veritat | `pipeline` + `tempo_map` (2 backends); la còpia del visor mai no mana | `test_regles_or.TestRegla5FontDeVeritat` | ✅ auditada (Ronda 5: les 36 mutacions del visor passen pels validators/normalitzadors o preserven els invariants) |
| 6 | WAVs només via `exporta_total()` | `pipeline.exporta_total` / `regenera_wavs_*` | `test_regles_or.TestRegla6WavsNomesViaExporta` | ✅ auditada (Ronda 3: els 6 cridadors són tots camins d'exportació; la UI delega) |
| 7 | Instància única | `plataforma.bloqueja_instancia_unica` (flock / `msvcrt.locking`) | `test_regles_or` · `test_lock_windows` | ✅ auditat a fons (Ronda 15) |
| 8 | Temps vàlids | `visor._valida_canvis_*` **+** les xarxes de seguretat (`normalitza_cobertura`, `normalitza_trams`) | `test_regles_or.TestRegla8TempsValids` | ✅ auditat (Ronda 1: 2 forats arreglats) |
| 9 | Portabilitat i maquinari (3 SO, sense AVX) | CI (`eines/verifica_minos_macos.py`) · build genèric (`-msse -msse2`, sense AVX) · `tests/test_requirements.py` (pins) · **NOU `GuardAvxTests`** (flags dels scripts de build) | `test_requirements` | ✅ auditat (Ronda 8: + guard d'AVX als scripts) |
| 10 | Estat en directori escriptible | `app/config.py` (prova d'escriptura real: projecte → XDG → temporal) | `test_regles_or` · `test_pipeline_export` (cas no escrivible) | ✅ auditat a fons (Ronda 15) |
| 11 | Paritat d'edició i tracte visual | el joc simètric a `app/visor.py` + `app/pipeline.py` + `app/tempo_map.py` · pont MCP (`app/mcp_bridge.py`) | `test_regla11_paritat` · `test_mcp_paritat` · `test_eina_marc` | ✅ auditada (Ronda 10: incloses les operacions MIxtes de les 3 famílies i el desfer/refer) |
| 12 | Paritat d'exportació (paquet complet) | — | — | ⛔ **PENDENT D'IMPLEMENTACIÓ, ASSIGNAT A PART** (un altre agent; `docs/REGLES_DE_LA_APP.md` §12). **No tocar des d'ací.** |

## Trobades i fixes (el més nou a dalt)

### 2026-10-18 · Ronda 12 — prova de MUTACIÓ: els tests de regla tenen dents

Trencades a posta 5 validacions i comprovat que els tests corresponents peten
(i després restaurades amb `git checkout --`):

| Mutació | Regla | Test que va peta |
|---|---|---|
| Tret el clamp de temps negatius del mapa | 8 | `test_tempo_map` + `test_regles_or` ✅ |
| Tret el clamp de l'acord amb inici negatiu | 8 | `test_regles_or` ✅ |
| Desactivat l'arreglament d'encaixaments de seccions | 2 | `test_seccions_contigues` ✅ |
| Desactivada la capçalera «N» dels acords | 4 | `test_pipeline_export` ✅ |
| Treta la normalització del mapa a `_refresca_tempo_map` | 1/2/4 | `test_regles_or` ✅ |

Cap test feble trobat en aquests camins. La prova de mutació queda com a mètode
del registre (damunt) per a les properes rondes.

### 2026-10-18 · Ronda 10 — R11 camí a camí: operacions MIxtes de les 3 famílies

- **Verificat sense canvis** (i blindat amb un test nou a `test_regla11_paritat`):
  * **Esborrar una selecció mixta** (un acord + una secció + un tram) és **una
    sola** operació: els tres desapareixen alhora i **un sol `Ctrl+Z`** els
    torna (i `Ctrl+Y` els torna a treure).
  * **Copiar i enganxar una selecció mixta** (acord + tram): s'enganxen tots
    dos de cop, amb la semàntica de cada carril (el clip substitueix el tram;
    el mapa obre fronteres i hi canvia el BPM/compàs) i **un sol desfer** ho
    reverteix.
  * El **Ctrl+Shift**+arrossegar ja és coherent amb 1 clip o amb multi-selecció
    (Ronda 6).

### 2026-10-18 · Ronda 9 — R11: l'MCP no podia editar els valors d'un tram

- 🐞 **Forat de paritat**: la GUI pot editar el **BPM i el compàs** de qualsevol
  tram del mapa (menú ▸ *Reanomena (BPM/compàs)…*), però pel pont **no hi havia
  cap eina**: `ac_set_tempo` només toca el valor global de la barra (que és el
  del tram 0) i `ac_mou_tall` mou fronteres, no valors.
  → NOVA eina **`ac_set_tram_tempo`** (73 → 74): fixa el BPM i/o el compàs del
  tram `index` (el que no s'indique, es conserva), amb validació de bpm>0 i
  compàs positiu. Si és el tram 0, el valor nou passa també al transport, com
  fa la GUI. Test nou a `test_mcp_paritat` i taula d'operacions al dia.
- 🧹 **Restes històriques al codi**: tretes les etiquetes «(fase N)» del pla de
  tempo (ja tancat) dels comentaris de `pipeline`, `tempo_map`, `timeline`,
  `visor`, `projecte` i `acords_a_live`, i **corregit un docstring obsolet** de
  `_refresca_tempo_map` que deia que «la graella encara fa servir
  `self.bpm`/`self.bpb`» — la graella, el regle, el snap i els exports ja són
  mapa-conscients des de fa fases.

### 2026-10-18 · Ronda 8 — R9: guard automàtic dels flags de build

- **R9 verificada**: els natius es compilen amb `-msse -msse2` (i el comentari
  de l'script diu per què) i cap script del paquet demana AVX. La suite
  mateixa, corrent en un **Q9400 sense AVX**, és la prova de facto que res del
  camí de l'app en demana (buit a `grep -o avx /proc/cpuinfo`).
- ➕ **Guard nou** (`tests/test_requirements.py` › `GuardAvxTests`): vigila que
  els scripts de compilació dels natius no hi introdueixin `-mavx*`,
  `-march=native` ni `-mtune=native` — que compilarien pel maquinari de qui
  construeix i no pel de destí (el Q9400) — i que hi hagen `-msse2`. Sense
  això, la regla depenia només de llegir-se l'script.
- **`eines/` net**: cap funció ni constant morta (revisades totes amb el
  detector d'usos).

### 2026-10-18 · Ronda 7 — R2/R8: encavalcaments i durades nul·les de SECCIONS

- 🐞 `pipeline.normalitza_cobertura` (la xarxa de seguretat dels 4 camins + la
  càrrega) **no** tocava les seccions que **s'encavalcaven** ni les de
  **durada nul·la**: un CSV editat a mà o un projecte vell hi podien entrar i
  el model quedava amb solapaments (#2) i amb una secció de durada 0 (#8). El
  visor ja ho rebutja, però per ací també s'hi passa.
  → ara mana la secció que **arrenca més tard** (el seu inici retalla el fi de
  l'anterior, com fa una marca d'acord), les de `fi <= ini` s'eliminen i el
  forat que en quede el tapa el farciment de sempre. Test nou a
  `test_seccions_contigues`.

### 2026-10-18 · Ronda 6 — R1/R2/R4 a la càrrega (verificades) + camí llegat de duplicar

- **R1/R2/R4 (mapa i acords, camí de càrrega)**: provats els casos extrems —
  empats d'inici, `fi < ini`, `fi != inici del següent`, desordre i trams
  repetits — i tots ixen normalitzats i deterministes. ✅ (El mapa: l'empat
  el guanya el primer; `afegeix_tall` sobre una frontera existent és un
  no-op, que és el que toca.)
- 🧹 **Camí llegat de duplicar arrossegant** (`_move_chord_group`, amb el
  comentari «es reubicarà a la fase 4»): amb **multi-selecció** el gest
  movia el grup pel camí vell i deixava **una sola marca solta** a l'origen;
  i amb un sol clip duplicava fent un **redimensionat** (la durada podia
  canviar) en comptes d'un moviment de bloc. Ara el cos arrossega sempre el
  **BLOC** (§6.3) i la còpia a l'origen només s'arma amb **un** clip
  seleccionat → mateix tracte que les seccions (#11). Mètode llegat eliminat
  (−1.871 caràcters) i test nou a `test_eina_marc`.
- **Tests obsolets**: cap. Comprovat amb tres detectors —noms repetits dins
  la mateixa classe (0 ombrejats), tests sense cap assert (7, tots *smoke*
  legítims del tipus «no peta») i ajudants/constants de test morts (cap;
  l'únic candidat, `setUpModule`, és un ganxo del framework).

### 2026-10-18 · Ronda 5 — R5 (una sola font de veritat): cap mutació fora del backend

Repàs de les **36** assignacions a `self.acords` / `self.seccions` del visor, una
a una: totes passen per `_valida_canvis_*`, `_normalitza_*` o les funcions de
`pipeline` (les poques que assignen directament —`_aplica_estat` de l'undo, el
renom inline— treballen sobre estats ja validats o preserven els invariants:
el renom inline sanea el nom amb `pipeline.saneja_nom_acord`, conserva el
`Clip` i **marca l'undo**). Cap camí de la UI escriu WAVs ni es salta el
backend. ✅

### 2026-10-18 · Ronda 4 — R2 a la càrrega + neteja de codi mort

- 🐞 `visor.llegeix_abc` (lector de l'estructura, camí de càrrega) **petava** amb
  una línia malmesa (`ValueError`) mentre `llegeix_acords` ja la descartava amb
  avís → el tema no s'obria. I una família absent quedava `None`, que després
  s'escrivia al CSV com «None». Ara els dos lectors es comporten igual (#11):
  línia dolenta fora amb avís, i lletra/família al valor per defecte del model.
  Test nou a `test_regles_or`.
- 🧹 **Neteja de codi mort** (5.443 caràcters): `theme.CLIP_ACTIVE_BORDER`,
  `main._executa_i_exporta_final`, `visor._undo_reset` i els **diàlegs vells**
  d'edició d'acord/secció (`_edita_acord_index` + `_edita_acord`,
  `_edita_seccio_index` + `_edita_seccio`), substituïts per l'editor inline i
  la franja Editor (`_focus_editor`). Comprovat que **no** eren els handlers
  del doble clic de les llistes (això va a `_focus_editor`) ni que la cascada
  deixara cap altre mètode orfe.
- Els `skipTest` de la suite són tots legítims (Windows/POSIX/ffprobe/sonic),
  cap test obsolet.

### 2026-10-18 · Ronda 3 — R4 (punt únic del mapa) i R6 (escriptors de WAV)

- **R4**: `visor._refresca_tempo_map` és l'**únic** lloc on es construeix
  l'objecte `TempoMap` a partir de la còpia. Ara normalitza sempre
  (`normalitza_trams`), així que la còpia vinga d'on vinga (CSV a mà, undo
  vell, client MCP) ix amb ordre (#1), contigüitat (#2), cobertura (#4) i
  valors vàlids (#8). Test nou a `test_regles_or`.
- **R6**: revisats **tots** els cridadors d'escriptors de WAV
  (`exporta_total`, `regenera_wavs_acords`, `regenera_wavs_estructura`,
  `neteja_wavs`): els 6 són camins d'exportació (menú principal, visor i el
  fil de l'exportació asíncrona). Cap camí d'edició n'escriu. ✅
  *(Nota de redacció: la regla diu «des del backend `exporta_total()`» i el
  visor autònom hi arriba pels seus regeneradors; el fons de la regla —només
  l'exportació escriu WAVs— es compleix. Ho deixo anotat, no reescric la
  regla perquè ara la té en mans un altre agent.)*

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

## Ronda 14 — prova de mutació a la R11: UN TEST FEIBLE trobat i arreglat

Quatre mutacions de paritat (R11), i una **no** va fer petar res:

| Mutació | Detectada? |
|---|---|
| `parteix_per_la_meitat` només per als acords | ✅ `test_regla11_paritat` |
| Treure una acció del menú de llista d'acords | ✅ `test_regla11_paritat` |
| `_elimina_seleccio` ignora els trams | ✅ `test_regla11_paritat` |
| **`_sync_selection_visual` ignora els trams** | ❌ **NO** — cap test ho mirava! |

- 🐞 **Test feble arreglat**: la pista de BPM/compàs es comprovava pel **model**
  (`selected_keys`) però no pel **ressaltat visual** de la capa
  (`TempoLayer._sel`). Si `_sync_selection_visual` deixava d'actualitzar-la, la
  suite quedava verda i la pista no es ressaltava a la pantalla. Ara el test
  ho comprova (`select_clip` → `_sel` i `clear_selection` → `-1`) i la mutació
  **sí** que hi peta.

## Ronda 13 — l'informe d'incoherències: propostes obertes, RESOLTES

- L'`INFORME_INCOHERENCIES_2026-10-16.md` tenia un punt obert (7.4): deia que els
  docs afirmaven que l'estat va sempre a `~/.local/state/auto-chords`, mentre que
  `app/config.py` prefereix la **carpeta del projecte**. Comprovat contra el codi
  (`DADES_DIR` = primer escrivible de projecte → XDG → temporal, i
  `recents.json`/`sessio.json` en pengen) i arreglat: `docs/PROJECTES.md` ja ho
  diu bé, i el que diu `PROVES_FUNCIONALS_3SO.md` es queda perquè parla del cas
  **AppImage** i de la **quarantena** del `.app` (on la carpeta del paquet no és
  escrivible). El punt queda marcat com a ✅ RESOLT dins l'informe.

## Ronda 11 — restes de funcionalitats RETIRADES

- 🧹 **`_alt_copia`** era el nom del gest **`Alt`+arrossegar**, retirat el
  16-10-2026 (a Linux el gestor de finestres se l'emporta; ara és
  **`Ctrl+Shift`**+arrossegar). El nom havia quedat al codi i als tests, i
  confonia. Renombrat a **`_copia_ac`** (mirall de `_copia_sec` de les
  seccions) i actualitzats els comentaris, el nom de la classe de test
  (`TestCtrlShiftArrossegaCopia`) i els noms dels tests. Cap canvi de
  comportament; el text explicatiu del `docs/ESQUEMA_UI.md` (que diu *per què*
  no s'usa `Alt`) es manté, que és correcte.

## Verificacions sense canvi (queda constància)

- **R7 a fons (Ronda 15)**: el bloqueig d'instància única és un **`flock`/
  `msvcrt.locking` del sistema operatiu**, no un fitxer de PID: si l'app peta,
  el lock l'allibera el nucli **sol** → no hi ha *locks ròmics* que impedisquen
  tornar a obrir-la (que era el risc del mètode). El nom del fitxer inclou
  l'usuari (no és global al sistema) i la 2a instància es rebutja de manera neta
  (el `write` de Windows va DINS el `try`: escriure en una regió bloquejada hi
  llança `OSError`, no torna `False`).
- **R10 als 3 SO (Ronda 15)**: la cadena **carpeta del projecte →
  `$XDG_STATE_HOME/auto-chords` → temporal** cobreix els tres casos que la regla
  enumera (AppImage de només lectura · `.zip` a `Program Files` · `.app` en
  quarantena) amb una **prova d'escriptura real**, no amb una llista de
  plataformes. Proveït pel cas «el projecte no és escrivible» de
  `test_pipeline_export`.

- **`pipeline.SONIC`** (`OLD/sonic-annotator`, «reserva llegat»): **no és codi
  mort**. `_cmd_transform` fa servir el **host Vamp propi** si hi és
  (`usa_host()`) i cau a `sonic-annotator` si no (arrencada des de codi font
  sense el host compilat). Per això `main` l'exclou de l'autocomprovació
  d'arrencada. Es deixa tal com està.
- **R1/R2/R4 al camí de càrrega** (empats d'inici, `fi < ini`, ordre barrejat,
  duplicats): ja es complien (Ronda 6).

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
