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
| 12 | Paritat d'exportació (paquet complet) | `pipeline.exporta_total(..., mapa_tempo=)` → `mapa_tempo/` | `test_regla12_export` | ✅ **IMPLEMENTADA I PROVADA** (Ronda 21; ordre de l'operador) |

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

## Ronda 21 — REGLA 12 IMPLEMENTADA (era l'única sense compliment)

Ordre de l'operador: «la regla 12 també implementa-la tu» (fins ara estava
marcada com a pendent assignada a part; l'altre agent només n'havia escrit el
text).

- `pipeline.exporta_total(..., mapa_tempo=)`: rep els trossos del mapa del
  **model viu** (com `acords`/`seccions`) i els desa a la seva **carpeta
  pròpia** `mapa_tempo/` (`tempo.csv` + `compas.csv`). Cridadors: la finestra
  (`_prepara_export` → fil de l'export) i el visor autònom.
  Sense mapa, el paquet queda **exactament** com era.
- El paquet queda paritari: `acords.csv` + `wavs_acords/` ·
  `estructura_ABC.csv` + `wavs_estructura/` · `mapa_tempo/` (tempo + compàs).
- NOU `tests/test_regla12_export.py` (4 proves) i `REGLES_DE_LA_APP.md` §12
  passa de «pendent» a ✅ FET (la capçalera i la nota final també).
- **Prova de mutació (2)**: treure l'export del mapa → 3 proves peten; desar-hi
  valors fixos → 2 peten; posar el mapa a l'arrel en lloc de la seva carpeta →
  3 peten.
- ⚠️ **Lliçó apresa**: el primer intent de mutació va fer `git checkout --`
  sobre `pipeline.py` amb la feina **sense commitejar** i se la va endur. Ara
  la regla del mètode és: **commit abans de mutar**.

## Ronda 20 — `acords_a_live.py`: no s'executava MAI als tests

- **Verificat**: cap script d'arrel està orfe (tots referenciats ≥2 llocs) i els
  comentaris que parlen de funcions **retirades** (inspector lateral, selecció
  creuada) ho fan per documentar-ho: cap resta de codi.
- 🐞 **Forat de cobertura real**: la guia DAW (`acords_a_live.py`) la crida
  l'app de debò (`pipeline.run_acords_py`) però la suite **sempre la mockejava**
  (`patch.object(pipeline, 'run_acords_py')`) → ningú no provava que l'script
  s'executara, que generara `acords_locators.txt` + `guia_acords.html` ni que
  respectara el **mapa de tempo/compàs**.
  → NOU `tests/test_acords_a_live.py` (3 proves): executa l'script de veritat
  (sense mocks), amb un tema de 120 BPM i **amb un mapa variable** (4/4→3/4).
- 🐞 Sense arguments l'script peta amb `IndexError`: ara diu l'**ús** i plega
  amb codi 2 (com fa `explica_bpm.py`).

## Ronda 19 — camí `eines/`: un script que petava

- **Tots els scripts de `eines/` estan referenciats** (CI, docs o codi): res
  orfe. Revisat script a script què els crida.
- 🐞 **`eines/explica_bpm.py` petava** (`TypeError`) quan la detecció de BPM
  retorna `None` — que `tempo._comb_bpm` fa **a propòsit** quan el senyal és
  massa curt o no té periodicitat (i que l'app ja preveu: vegeu
  `test_detecta_bpm_silenci_retorna_none`). El script intentava formatar `None`
  (`f"{bpm:.1f}"`) i sortia un *traceback*.
  → ara, si no hi ha BPM, diu un **missatge clar** i plega amb codi 1. Provat
  amb un àudio degenerat (missatge net, sense traça) **i** amb un ritme real de
  120 BPM (detecta `120.0 BPM` i genera el PNG de 129 KB).

## Ronda 18 — tests que fan *skip*: cap d'obsolet

Revisats **tots** els punts on la suite pot saltar-se proves
(`skipTest`/`skipIf`/`skipUnless`, 15 llocs): **tots són condicionals d'entorn i
documentats**, cap test obsolet ni mort:

- **Plataforma**: motor d'àudio natiu (mac/win), `flock` i permisos POSIX,
  `/proc`, `O_NOFOLLOW`, `aplay`/`paplay`… (a cada SO corre el seu).
- **Eines de sistema**: `ffprobe` (no s'empaqueta) i `sonic-annotator`
  (`_SONIC_OK`, la reserva).
- En **aquest** entorn només se'n salta **1**: `test_natiu_a_windows_i_macos`
  («al Linux no es fa servir el motor natiu»), que és el que toca.
- `EscriuTtlTests` (només amb `sonic-annotator` executable) **sí que corre
  aquí**: `_SONIC_OK = True`.

## 🏁 Cobertura de la prova de mutació — LES 11 REGLES, verificades

Cada regla té almenys **una mutació feta i detectada** pels tests (una mutació =
trencar la validació a posta i comprovar que la suite peta):

| Regla | Mutació que es va provar | Detectada |
|---|---|---|
| 1 Ordre | treure el `sort` de `normalitza_cobertura` | ✅ (R11, R17) |
| 2 Contigüitat | desactivar l'arreglament d'encaixaments de seccions | ✅ (R12) |
| 3 Durades derivades | no acotar el fi de l'última secció | ✅ (R16) |
| 4 Cobertura | treure la capçalera «N» / no cobrir fins a la durada (mapa) | ✅ (R12, R17) |
| 5 Font de veritat | guardar el CSV convertit en no-op | ✅ (R16) |
| 6 WAVs només en exportar | `_desa_i_regenera` deixant anar una WAV | ✅ (R16) |
| 7 Instància única | el bloqueig dient sempre que sí | ✅ (R17) |
| 8 Temps vàlids | treure els clamps de negatius (mapa i acords) | ✅ (R12) |
| 9 Sense AVX | posar `-mavx` a l'script de build | ✅ (R17) |
| 10 Directori escriptible | `_es_escriptible` dient sempre que sí | ✅ (R16) |
| 11 Paritat | 4 mutacions (una NO detectada → test feible, arreglat) | ✅ (R14) |

**Conclusió**: cap test feible pendent en el nucli de les regles. Només la
**regla 12** queda fora (assignada a un altre agent).

## Ronda 17 — mutació a les regles 1, 2, 4, 7 i 9 (totes detectades)

| Mutació | Detectada |
|---|---|
| El bloqueig d'instància única diu sempre que sí (R7) | ✅ `test_regles_or` |
| `-mavx` a `compila_vamp_host.sh` (R9) | ✅ el guard nou `GuardAvxTests` |
| Treure el `sort` del backend (R1) | ✅ `test_regles_or` |
| El mapa deixa de cobrir fins a la durada (R2/R4) | ✅ `test_tempo_map` (5) |
| El mapa perd la capçalera a 0 (R4) | ✅ `test_tempo_map` + `test_regles_or` |

## Ronda 16 — prova de mutació a les regles 3, 5, 6 i 10

Totes quatre **detectades** (cap test feble nou):

| Mutació | Regla | Qui la va caçar |
|---|---|---|
| Guardar el CSV convertit en no-op | 5 | `test_regles_or` ✅ |
| `_desa_i_regenera` deixant anar una WAV | 6 | `test_regles_or` ✅ |
| Fi de l'última secció sense acotar a la durada | 3 | `test_pipeline_export` ✅ |
| `_es_escriptible` dient sempre que sí | 10 | `test_pipeline_export` ✅ |

Notes del mètode (après a la Ronda 14 i 16):

- **La mutació s'ha de comprovar que S'EXECUTA**: dues temptatives de la Ronda
  16 no van valdre perquè el punt d'injecció no s'arribava a cridar (una va
  petar de sintaxi i l'altra escrivia a un lloc que el test no mirava). Cal
  `import` net i pensar QUIN camí passa el test.
- Els tests de la regla 3 són **estructurals** (el model no té camp de durada):
  l'acotament del fi de l'última secció el cobreix `test_pipeline_export`. Està
  cobert, però és bo saber-ho.

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

## Ronda 32 — `eines/prova_mcp_completa.py`: dos bugs (smoke de les eines)

Smoke de les eines (el mateix patró que ja havia trobat `wav_a_wavs` i
`explica_bpm`):

- 🐞 `prova_mcp_completa.py` connecta bé amb el pont viu (74 eines) però donava un
  **fals KO** perquè el recompte esperat era `== 51` **hardcoded** d'una sessió
  antiga. Ara es compara amb el que **exposa** el servidor (`_TOOLS`) — que és la
  invariant que es vol comprovar; si no es pot importar, no s'exigeix.
- 🐞 I **petava** amb `AttributeError: 'str' object has no attribute 'get'` quan
  una crida tornava un **ERROR** (el resultat és un text, no un dict): ara
  `chords()` i `seccions()` passen per `_llista()` i tornen buit en eixe cas.
  Verificat en viu: `tools/list` (74 eines = servidor) OK.
- **`DialegTrobaReemplaca`** afegit al test dels diàlegs (camps i `strip`):
  `app/dialegs.py` queda amb **tots** els diàlegs coberts.

Commit `583379a` · suite 1065 OK (1 skip).

## Ronda 31 — dialegs (II): contracte de persistència i presets del mode fàcil

Completa la cobertura de `app/dialegs.py` (616 línies que no en tenien cap):

- **`DialegOpcions`**: el **round-trip dels defectes** — posar-los als controls i
  tornar-los a llegir amb `opcions()` ha de donar **exactament** el mateix, clau a
  clau i tipus a tipus. És el contracte que evita que un canvi de widget trenque
  l'anàlisi **en silenci**. També: `_restaura()` torna als defectes i la pestanya
  inicial triada.
- **`DialegModeFacil`**: cada preset d'estil fixa el seu ritme harmònic i el seu
  mòdul (es proven **tots** els presets de `graella.PRESETS`), i una tria manual
  posterior **mana** sobre el preset.

Commit `8f1afda` · suite 1063 OK (1 skip).

## Ronda 30 — `app/dialegs.py` (616 línies) no tenia CAP test: 2 bugs reals

Els diàlegs sempre es **bypassaven** (patch de `QMessageBox`/`QInputDialog` o
cridant la lògica del visor). El primer test que els exercita de debò ha destapat
**dos bugs de veritat**, tots dos al diàleg «Mapa de tempo i compàs…»:

1. 🐞 **`_sync()` petava**: cridava `self.taula.item(...)` amb el número de
   **columna com a string** (`_t("0","0")`, `_t("1","120")`, `_t("2","4/4")`) →
   `TypeError` que el `try` **no** capturava (només agafava
   `ValueError`/`IndexError`) → el diàleg **petava** en afegir/eliminar un tram o
   en prémer OK. Ara són `int`.
2. 🐞 **El botó «+» no feia res**: `_afegeix()` calculava el punt mig del darrer
   tram sobre el que deixa `_sync()` (`(ini, ini, …)`, amb el `fi` encara per
   derivar) → el mig queia damunt la mateixa frontera, `afegeix_tall` hi posava
   un tall que el normalitzador descartava → cap efecte. Ara normalitza abans de
   calcular el mig.

➕ **NOU `tests/test_dialegs.py`** (13 proves): `DialegTramTempo.valors()`
(compàs «num/den» i «num», invàlids, mai zero, el BPM del camp) i
`DialegTempoMapa` (compàs → segons amb el tempo del tram correcte,
afegir/eliminar i que el mapa que entrega siga **sempre vàlid**: regles
#1/#2/#4). Commit `d124e6f` · suite 1058 OK (1 skip).

## Ronda 29 — mutació: menús i `postproc`/`vamp_params` + un test feble (mutació 22)

- **Cobertura dels wrappers de menú**: verificada, **cap forat** (tota acció de
  menú té el seu camí).
- **Prova de mutació a `app/postproc.py` i `app/vamp_params.py`**: detectada. ✅
- 🐞 **Test feble (mutació 22)**: el test de les zones de `TempoLayer` (Ronda 26)
  **no distingia les dues vores**: en traure la comprovació d'`ini` de `_zona`,
  la frontera retornava el «fi» del tram anterior, i el test ho acceptava perquè
  les dues respostes són el mateix punt de canvi. Ara la comprovació d'`ini` es
  fa al **tram 2** (x=603), on el tram anterior no pot respondre «fi» → amb la
  mutació hi peta.

Commit `c86fd2b` (només el test endurit; la resta de la ronda va ser verificació
sense canvi de codi).

## Ronda 28 — proves directes de les funcions pures de la graella (`timeline_base`)

`snap_step` tenia **ZERO** referències als tests i la resta de funcions pures
d'`app/timeline_base.py` (el pla de graella, les posicions, els nivells) només
s'exercitaven **indirectament** des del `TimelineView`.

➕ **NOU `tests/test_timeline_base.py`** (12 proves) que fixen els **contractes**
(no els números d'un zoom concret):

- **`snap_step`**: la divisió triada complix la seua invariant
  (`step*pps >= MIN_LINE_PX`) i amb més zoom **mai** no engruixeix; amb mapa
  variable les durades són les del tram de l'offset.
- **`grid_plan`**: el seu `snap` coincidix amb `snap_step` (**font única**), les
  línies van de gruixut a fi i inclouen el snap, i l'etiqueta és la més fina que
  hi cap (amb el *fallback* documentat).
- **`grid_levels`**: deriva del pla (mateixos passos, en ordre invers).
- **`grid_positions`**: és un **generador**, dona `offset + k*step` per **índex**
  (mai acumulant — era el bug del regle amb «(N−1).4») i els extrems són
  inclusius.

Commit `c4eab57` · suite 1045 OK (1 skip).

## Ronda 27 — eina nova `eines/ordre_aleatori.py` (dependències d'ordre a la suite)

`unittest discover` corre els tests en un ordre **fix** (alfabètic): si algun test
depenguera de l'estat que en deixa un altre (una `QApplication`, un tempdir, una
opció desada…), la suite passaria sempre i el problema només eixiria en canviar
d'ordre. L'informe d'incoherències (punt **7.3**) citava una fallada no
reproduïda que podia ser això.

➕ **NOU `eines/ordre_aleatori.py [seed] [--llista]`**: descobrix tota la suite,
la barreja amb la llavor donada i l'executa; si falla, diu **quin** test i amb
quina llavor (reproduïble). Amb `--llista` només mostra l'ordre (per provar
l'eina mateixa).

- **Provat amb dues llavors (1 i 7)**: 1032 tests OK a totes dues → **cap
  dependència d'ordre**.
- Guard de smoke afegit a `tests/test_scripts_smoke.py`.

Commit `c0b3e4c` · suite 1033 OK (1 skip).

## Ronda 26 — pista de BPM/compàs: proves pròpies de les zones i del cursor

`TempoLayer._zona()` és el **cor** del gest de la pista (decidix si
l'arrossegament mou una vora o el punt de canvi, i amb ell què passa amb els
veïns) i **no tenia cap prova pròpia**: la suite l'exercitava només pel `paint` i
a través del `TimelineView`.

- **Extreta la lògica del cursor** a `TempoLayer._cursor_de_zona(z)` (funció
  pura, **idèntica a la d'acords i estructura**: regla #11). PyQt5 no deixa
  fabricar un event de *hover*, així que així la paritat del cursor també es pot
  provar.
- ➕ **NOU `tests/test_timeline_layers.py`** (6 proves): vores i cos de cada
  bloc, que els **extrems** no tenen vora arrossegable (el mapa sempre comença a
  0 i acaba a la durada), fora del mapa, capa inactiva, cursor per zona i la
  selecció/deselecció de la capa.

Commit `63ed60b` · suite 1032 OK (1 skip).

## Ronda 25 — guards amb dents + arxivar el que ja és històric

- **Prova de mutació dels guards nous** (3): tornar a trencar
  `wav_a_wavs.py` → `test_scripts_smoke` hi peta; treure el guard d'ús de
  `acords_a_live.py` → hi peta; treure el de `explica_bpm.py` → hi peta. ✅
- **Arxivat** `docs/INFORME_INCOHERENCIES_2026-10-16.md` → `docs/archive/`
  (`git mv`): tots els seus punts han quedat resolts (l'últim, el 7.4, a la
  Ronda 13) i era l'únic document de `docs/` que ja era purament històric.
  `docs/README.md` actualitzat amb la ruta nova i l'estat.
- Vist i **descartat**: afegir `docs/EDICIO_OPERACIONS.md` a la whitelist de
  `concatena.py` (l'eina empaqueta el context mínim: `REGLES` + `MCP` i el codi;
  la taula d'operacions és útil però «detallada», com diu el propi script).

## Ronda 24 — el NUCLI de l'app no s'executava mai als tests

Buscant el patró de la Ronda 20 (components vius que els tests sempre
**mockegen**) s'ha trobat el forat més gros de tots: **l'anàlisi real de la
WAV**. La suite patchava `pipeline.extract_chords` / `pipeline.executa_transform`
en 3 llocs, i els que restaven només provaven el runner amb un transform
**inexistent** (`vamp:x`) per veure que netejava el `.ttl`. És a dir: el nucli
de l'app (treure els acords d'una cançó) **no s'executava mai de veritat**.

➕ **NOU `tests/test_analisi_real.py`** (2 proves, ~1 s): corre el **host Vamp
de debò** sobre un WAV sintètic de tres triades i comprova que (a) el CSV ix
amb el format esperat, els temps en ordre i **almenys un acord de veritat** (no
tot «N»), i (b) la crida amb `params` no deixa cap directori temporal `ac_ttl_`
orphe. Si el host/els plugins no hi són, se salta netament.

## Ronda 23 — scripts d'arrel: DOS que petaven de bon començament

Smoke dels scripts d'arrel (el mateix patró que `explica_bpm`/`acords_a_live`):

| Script | Estat |
|---|---|
| `concatena.py` | ✅ funciona (149 fitxers · 42k línies · 1,7 MB). Totes les
  entrades de la whitelist **existeixen** (cap referència morta). |
| `dev_reload.py` | ✅ `--help` i arrancada correctes. |
| `wav_a_wavs.py` | 🐞 **PETA** amb `--help` i amb tot: feia `import pipeline`
  amb `app/` al `sys.path`, però el mòdul viu DINS el paquet `app` des del
  refactor → «attempted relative import with no known parent package». Ara fa
  `from app import pipeline` i corre de cap a cap (el flux arriba a generar la
  guia; amb àudio sintètic pobre el propi script avisa que Chordino ha donat
  tot «N», que és el seu guard). |
| `eines/explica_bpm.py` | 🐞 **encara petava sense arguments** (`IndexError`):
  el fix de la Ronda 19 era per al cas `BPM = None`. Ara té guard d'ús. |

➕ **NOU `tests/test_scripts_smoke.py`** (4 proves): executa de debò
`wav_a_wavs.py --help`, `acords_a_live.py` sense args, `eines/explica_bpm.py`
sense args i `dev_reload.py --help`, i comprova que **cap** trau `Traceback`.
Hauria atrapat tots dos bugs d'aquestes rondes.

## Ronda 22 — els DOS motors d'anàlisi, comparats en viu

L'app té dos camins per als transforms Vamp: el **host propi**
(`vamp_host_local`, el preferent) i la **reserva** `OLD/sonic-annotator` (si el
host no hi és, p. ex. arrencant des de codi font). Amb la reserva *executable*
en aquesta màquina (`_SONIC_OK = True`), s'han corregut **tots dos** sobre el
mateix WAV (tres acords C · F · G) i s'han comparat:

- **Etiquetes d'acord: IDÈNTIQUES** (el que importa per a l'app): `C`, `F`, `G`
  amb el mateix nombre de files (5).
- **Marques de temps**: iguals fins a **1e-6 s** excepte el **primer onset**
  (`0,232` amb el host vs `0,046` amb el sonic). És el comportament dels
  plugins Vamp amb el primer bloc: el host hi passa el `--step`/`--block` de la
  taula (escalat al mostreig) i el sonic fa servir les preferències del plugin.
  No és cap defecte del codi ni afecta les etiquetes.

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
