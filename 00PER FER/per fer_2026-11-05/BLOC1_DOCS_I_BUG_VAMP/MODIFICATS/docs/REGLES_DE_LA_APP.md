# ⚠️ REGLES DE LA APP — invariants inmutables

> ## 🔴 IMPORTANT — LLEGEIX-HO ABANS DE TOCAR CODI
> Aquestes són les **regles d'or (invariants)** d'AUTO CHORDS.
> **Cap canvi de codi pot trencar-les.** Si una funcionalitat nova xoca amb una
> regla, es canvia **la funcionalitat**, no la regla (tret de decisió explícita
> de l'operador, que s'ha de documentar aquí **i** al `CHANGELOG`).
>
> Les regles numerades **1–12** tenen la seva **validació** al codi i un
> **test** que les comprova. El §13.9 és un requisit nou aprovat i està
> **implementat** pel que fa a importació, backups, retall/afegit als extrems,
> sincronització del model, undo/redo i **exportació d'àudio**; la restauració
> des de la GUI i les proves visuals continuen pendents. L'**auditoria
> continuada** (prova de mutació, regla a regla) viu a
> `docs/archive/AUDITORIA_REGLES.md`.
> Referenciades a `ROADMAP_HISTORIA.md` (§Notes d'implementació) i `DEVELOPING.md`.
>
> ## ‼️ S'HA DE COMPLIR **SEMPRE** — a TOTS els punts
> Les regles **no** són una comprovació «de tant en tant»: s'han de complir en
> **TOTS** aquests punts, sempre i alhora:
> 1. **Edició en viu** — GUI del visor: cada mutació (afegir,
>    eliminar, moure, redimensionar, reanomenar) ha de deixar el model **vàlid**.
> 2. **Visor** — el que es veu a la pantalla reflecteix el model vàlid.
>    **Té xarxa pròpia** (19-10-2026): punt **únic** `Visor._sincronitza_vista()`
>    (el criden les primitives de mutació) + el fuzzer
>    `tests/test_gui.py` › `_vista_segueix_model___Base` (`TestFuzzerReglesIVista`,
>    `TestElsDosBugsDeLaRonda12h`), que comprova **després de cada operació**
>    que els items pintats quadren amb el model (els seeds **9 i 15** detecten el
>    bug del gest). Vegeu `docs/archive/AUDITORIA_REGLES.md` → Ronda 52.
> 3. **CSV desat** — `acords.csv` / `estructura_ABC.csv` es desen **ja normalitzats**.
> 4. **Exportació** — el paquet exportat (CSV/ABC + wavs) surt del **model editat**,
>    normalitzat.
>
> ⚠️ **En especial la #4 (COBERTURA)**: no n'hi ha prou que s'aplique «en carregar el
> visor i en exportar» — s'ha d'aplicar **després de cada edició** també. Vegeu
> l'evidència de baix (**2 bugs de producció**, `OC-6/332-334`).

## Grups de regles (organització)

Les regles 1–12 i el §13 es mantenen amb la numeració vigent. A efectes de
lectura i prioritat, es poden agrupar així (sense canviar el contracte):

- **Requisits de plataforma**: 7 (instància única), 9 (portabilitat/AVX), 10
  (estat en directori escriptible).
- **Criteri de paritat**: 11 (edició i tracte visual), 12 (exportació).
- **Especificació del tempo**: §13 (temps, compàs i graella).

## 1. Ordre estricte dels clips
Els clips (**acords**, **seccions** i **trams de BPM/compàs**) estan
**ordenats pel temps d'inici**, **sense solapaments ni inversions**.

L'estat invàlid **no pot existir**: les operacions de l'app no el poden produir
(per lògica i per construcció —p. ex. un inici de tram **no es pot duplicar**:
`tempo_map.afegeix_tall` no crea el tall si ja hi ha una frontera en eixe
instant). Si entra **de fora** (CSV editat a mà, projecte vell, estat vell del
desfer), es **repara** cap al valor vàlid **i s'avisa** — mai en silenci: la
reparació passa per un sol punt (`tempo_map.neteja_trams`, que retorna els
avisos, i `visor._refresca_tempo_map`, que els mostra) i deixa traça al registre.
→ `visor._valida_canvis_acords` / `_valida_canvis_seccions` /
`tempo_map.neteja_trams` (repara i avisa) · `normalitza_trams` (intern) ·
`afegeix_tall`.

## 2. Contigüitat
Cada clip comença **exactament** on acaba l'anterior: `prev.fi == curr.ini`, per a
**les tres** famílies (acords, seccions i trams de BPM/compàs), amb el model
unificat `Clip(ini, fi, payload)` — sense forats ni encavalcaments. (Els **extrems**
0 ↔ durada són competència de la regla 4.)

Al **mapa de tempo/compàs** això no és una convenció sinó **estructura**: el `fi`
d'un tram **no s'emmagatzema**, és l'`ini` del següent (l'últim conserva el de la
WAV). Per això un forat o un encavalcament **no es poden representar**:
`tempo_map.TempoMap` els re-deriva en construir-se i `visor._refresca_tempo_map`
—el **punt únic** on es toca el model— els re-deriva *i els desa* al model, amb
avís si ha calgut reparar (regla #1). Cap operació hi mou una vora sola: `ini` i
`fi` d'un tram són la **mateixa frontera** compartida amb el veí (§13.6).
→ `timeline.py` · `pipeline.filtra_seccions` · `tempo_map.neteja_trams` /
`normalitza_trams` (model) i `tempo_map.TempoMap` (graella)
(contracte: `docs/archive/REFACTOR_INICI_FI.md`).

## 3. Durades derivades
La durada d'un clip **no s'emmagatzema**: es **deriva** (l'inici del següent, o
la durada de la WAV per a l'últim). El model `Clip(ini, fi, payload)` **sí** que
té un camp `fi`, però **no és la dada que mana**: sempre es torna a derivar de la
frontera (l'`ini` del següent) — la **cadena de fronteres** és la font de veritat.
→ És **estructural** (el model no té camp de durada); l'acotament del fi de
l'última secció el cobreix `tests/test_pipeline.py` › `CoberturaTests`
(`test_ultima_seccio_acotada_a_la_durada`).
test `tests/test_edicio.py` › `TestRegla3DuradesDerivades`.

## 4. Cobertura total
**La suma dels clips d'acords = la durada de la WAV**, **la suma dels clips
d'estructura = la durada** i **la dels trams de BPM/compàs = la durada**,
en qualsevol mode (**Lliure** o **BPM · compàs**) i
amb o sense **snap**: el 1r clip arrenca a **0** (capçalera «N» si cal) i
l'últim arriba a la **durada**. La regla **mana sobre el snap** (que només
quantitza els límits **interiors**). → `pipeline.normalitza_cobertura()`.
**S'aplica SEMPRE** (§«S'ha de complir SEMPRE»): en l'**edició en viu** (després de
cada mutació al visor), al **visor**, al **CSV** que es desa i en
**exportar** (CSV/ABC + wavs) — **no només** «en carregar el visor i en exportar».

## 5. Una sola font de veritat
El model viu al **backend**, no a la UI. Hi ha **dos backends**: `app.pipeline`
(acords i estructura) i `app.tempo_map` (trams de BPM/compàs). La UI
(`app.visor` + `app.timeline`) **en reflecteix** l'estat: en guarda una còpia
(`self.acords`/`self.seccions` i `self.tempo_trams`/`self.tempo_map`), però
**aquesta còpia mai no mana** — tota mutació passa abans per les funcions de
`pipeline`/`tempo_map`, i el visor només n'aplica el resultat.
Al **mapa de tempo/compàs** les còpies derivades (`self.tempo_map`, el
**transport** `bpm`/`bpb`/`beat_type`, la llista ⑭, la graella) es
reconstrueixen en **un sol punt**: `visor._refresca_tempo_map`. La UI **mai
munta ni muta trams a mà** —tampoc en desar—: si ho fera, el model avançaria
sense el mapa derivat (CSV i graella discrepant).
→ `pipeline` + `tempo_map` (backends); el visor sempre hi delega.
→ `visor._refresca_tempo_map` (punt únic model ↔ mapa ↔ transport).
test `tests/test_edicio.py` › `TestRegla5FontDeVeritat`.

## 6. Els WAVs musicals generats només via `pipeline.exporta_total()`
L'edició **mai** toca els WAVs silenciosos generats per als acords i les
seccions; només s'escriuen en **exportar**, des del backend
`pipeline.exporta_total(...)`. La UI hi delega via els mètodes `exporta()`
(`app.visor` / `app.main`). La còpia WAV de treball del projecte és l'àudio
font i es pot editar d'acord amb el **§13.9**; això no autoritza a modificar
els WAVs musicals generats.
→ Paritat d'exportació dels **3 carrils**: vegeu la **regla 12**.

## 7. Instància única
No poden córrer **dues instàncies** de l'app alhora. El bloqueig és un lock **del
sistema operatiu** — `fcntl.flock` (Linux/macOS) / `msvcrt.locking` (Windows) —
**no** un fitxer de PID: si l'app peta, el nucli l'allibera **sol** (no queden
locks ròmics). El nom del fitxer inclou l'usuari.
→ `main.py` + `plataforma.bloqueja_instancia_unica`.

## 8. Temps vàlids
Cap temps **negatiu** ni cap durada **≤ 0**. Els validadors de la UI ho rebutgen;
les **xarxes de seguretat** (les que cobreixen el CSV editat a mà, els projectes
vells) també ho arreglen.
→ `visor._valida_canvis_*` · `pipeline.normalitza_cobertura` · `tempo_map.normalitza_trams`.
test `tests/test_edicio.py` › `TestRegla8TempsValids`.

## 9. Portabilitat i maquinari objectiu
L'app ha de córrer als **3 SO** — **Linux** (AppImage x86_64, compilat a Ubuntu
22.04) · **Windows** (portable x64, Win10) · **macOS** (`.app` per a **10.13 High
Sierra+**, Intel) — i amb el **maquinari mínim objectiu** (**sense AVX**): cap
binari ni dependència del paquet no pot requerir **AVX** ni superar
**`minos 10.13`**.
→ **`minos`**: verificat al CI (`eines/verifica_minos_macos.py`, pas 6b). →
**AVX**: garantit pel build (CPython portable **genèric**, host VAMP `-msse -msse2`,
`numpy` **1.x**) i `tests/test_pipeline.py` › **`GuardAvxTests`**
(cap script de compilació pot introduir `-mavx*`/`-march=native`/`-mtune=native` —
compilarien pel maquinari de qui construeix, no pel de destí — i cal que hi hagen
`-msse2`). Vegeu `docs/ESTAT_MULTI_SO.md`.

## 10. Estat en un directori escriptible
El **log / opcions / temp** van sempre a un directori **escriptible** — mai dins
un paquet de només lectura. El cas es dona als **3 SO**: **Linux** (l'AppImage es
munta **només lectura**) · **Windows** (el `.zip` portable pot estar en una carpeta
sense permís d'escriptura, p. ex. `Program Files`) · **macOS** (l'`.app` pot estar
**en quarantena**).
→ `app/config.py` tria `DADES_DIR` amb una **prova d'escriptura real** (carpeta del
projecte → `$XDG_STATE_HOME`/`~/.local/state` → temp del sistema); d'allà en surten
`LOG_PATH`, `OPCIONS_PATH` i `TEMP_DIR` (`AUTO_CHORDS_TEMP` mana sobre el temporal).

## 11. Paritat d'edició i tracte visual (acords ↔ estructura ↔ BPM/compàs)

Els clips d'**acords**, d'**estructura** i els **trams de BPM/compàs** són
iguals davant l'edició i la visualització (**amb les diferències legítimes** que
es detallen avall). Tota operació d'un tipus ho ha de ser per als altres, i pel
**mateix camí d'usuari**.

- **Joc d'operacions comú**: afegir · eliminar · partir (pel cursor · **per la
  meitat**) · moure · redimensionar · desfer/refer. Reanomenar i duplicar/fusionar
  són comuns a **acords i estructura**; als **trams de BPM/compàs** el contingut és
  numèric (BPM + compàs) i s'edita amb el mateix diàleg per a tots ells, i
  «afegir» i «partir» hi són el **mateix gest** (obrir un **tall** nou:
  `tempo_map.afegeix_tall`), mentre que «eliminar» **fusióna els veïns**.
- **Gest i affordances idèntics**: nanses laterals, cursor de hover
  (`OpenHandCursor`, tancat en arrossegar, `↔` a les vores), senyal d'inici
  de gest (`dragStarted`), ressaltat de selecció, ordre relatiu (z),
  doble-clic/menú contextual → editar, **menú contextual amb la mateixa
  estructura i redacció**, i **mateixa transparència** del carri.
- **Propi de cada tipus (NO s'iguala)**: el **payload** (acord i estructura són
  `Clip(ini, fi, payload)` — acord `(nom, tsrc)`, secció `(lletra, família)` — i el
  tram és `Tram(ini, fi, bpm, num, den)`), els camps propis de cada tipus a
  l'Editor («Família» a la secció; «BPM»/«Compàs» al tram), l'edició **inline**
  i «Reanomena en bloc» (només acord/secció) i el **color/carri** del timeline
  (distinció de tipus).
- **Diferències legítimes del carril de BPM/compàs** (NO són manca de paritat):
  la seva **alçada** és **mitja** (`timeline_base.LANE_TEMPO_H`) i no té edició
  **inline** al timeline ni «Reanomena en bloc» (el contingut és numèric). Sí que
  té, des del 22-10-2026, **franja Editor** (mode BPM/Compàs, amb `tipus=rubato`) i **llista pròpia** (⑭: `Inici (s)` · `Fi (s)` · `BPM` · `Compàs`), amb
  el mateix clic / doble-clic / menú contextual que ⑩ i ⑪.
- **Semàntica de les operacions**: *partir* un acord = dos trossos amb el
  mateix nom (el de la part nova és editable, per defecte heretat);
  *fusionar* acords = en queda l'harmonia de l'esquerre. Mateix patró que
  l'estructura. *Partir* un tram de BPM/compàs = dos trams amb el mateix
  BPM i compàs (el de la dreta és editable).

→ Validació: `app/visor.py` + `app/pipeline.py` + `app/tempo_map.py` (joc d'operacions
simètric).
test `tests/test_edicio.py` › `_regla11_paritat___Base` — **✅ FET (18-10-2026)** per a
l'edició, el tracte visual, la selecció i el **desfer/refer**, incloses les **operacions
mixtes** de les 3 famílies (esborrar o copiar/enganxar una selecció acord+secció+tram =
una sola operació, un sol `Ctrl+Z`). La **paritat d'exportació** és la **regla 12**.

## 12. Paritat a l'exportació (paquet complet)
El paquet exportat tracta els **tres** tipus igual, cadascun amb la seva part:
acords (`acords.csv` + `wavs_acords/`) · estructura (`estructura_ABC.csv` +
`wavs_estructura/`) · **mapa de tempo/compàs** (**carpeta pròpia** `mapa_tempo/`
amb `mapa_tempo.csv`).
→ `pipeline.exporta_total(..., mapa_tempo=)` — rep el mapa del **model viu** (com
`acords`/`seccions`); si no se li passa, el paquet queda exactament com era.
test `tests/test_pipeline.py` › `TestRegla12ParitatExport` — **✅ FET (2026-10-18)**.
- **Representació aproximada (I7)**: el mapa exportat pot incloure una graella mètrica
  aproximada per als trams en segons, identificada visiblement com a tal; els CSV del
  model del projecte mantenen `0,0`.

## Cobertura i invariants (proposta v2)

Invariants candidats i la seua cobertura actual (detall fusionat en aquesta secció):

| Id | Enunciat (resum) | Test que el cobreix | Cobertura |
|----|------------------|---------------------|-----------|
| I1 | Partició contigua i completa de `[0, durada]` per carril. | `_viola_regles` (`tests/test_gui.py`, fuzzer) · `tests/test_edicio.py`. | Sí |
| I2 | Els segons manen; la graella en deriva. | `_viola_regles` · `tests/test_tempo_map.py` · `tests/test_edicio.py`. | Parcial |
| I3 | Cada clip conté un beat sencer; fronteres interiors a la graella del Snap (excepcions: primer inici, últim final i rubato). | `tests/test_tempo_map.py` · `tests/test_tempo_trams.py`. | Sí |
| I4 | Una sola font de veritat al backend, un únic punt de refresc. | `TestElsDosBugsDeLaRonda12h` · `TestFuzzerReglesIVista` (`_viola_vista`). | Sí |
| I5 | Atòmic, un desfer, sense reparacions silencioses. | `TestValidacioTempoVisor` · `tests/test_edicio.py`. | Parcial |
| I6 | L'exportació surt del model editat; l'edició no escriu àudio. | `tests/test_pipeline.py` (export). | Sí |
| I7 | Rubato conservat amb `tipus=rubato` i segons; aproximació mètrica a l'exportació (aprovat). | `tests/test_rubato.py` · `tests/test_mapa_tempo.py`. | Motor i model |

---

> 🧭 **Lliçó**: una regla d'or **no** pot dependre d'*on* s'aplica el codi; ha de
> valer a **tots** els punts (edició en viu, visor, CSV i exportació)..

---

> 📌 **En afegir una regla nova**: numera-la aquí, afegeix-ne la validació al
> codi i un test que la comprovi. **Les regles 1–12 ja tenen el seu test** — tots
> dins `tests/`, i els noms són **classes**, no fitxers:
> · **`test_edicio.py`**: `TestRegla1OrdreEstricte` (1) ·
>   `_seccions_contigues___Base` (2: `TestMoureSeccioManteContiguitat`,
>   `TestEditorDeSeccions`, `TestCarregaCSVAmbForat`) · `TestCoberturaViu` (4) ·
>   `TestRegla3DuradesDerivades` (3), `TestRegla5FontDeVeritat` (5),
>   `TestRegla6WavsNomesViaExporta` (6), `TestRegla7InstanciaUnica` (7),
>   `TestRegla8TempsValids` (8), `TestRegla10EstatEscriptible` (10) ·
>   `_regla11_paritat___Base` (11: `TestBackendParitat`, `TestVisorParitat`,
>   `TestMenusParitat`, `TestMenuPrincipalParitat`, `TestTracteVisual`).
> · **`test_pipeline.py`**: `GuardAvxTests` (9) · `TestRegla12ParitatExport` (12).
> · **`test_gui.py`**: `_vista_segueix_model___Base` (xarxa vista ↔ model).
> **La 13 (temps, compàs i graella)** es verifica a `test_tempo_map.py`
> (`TestCompassosEnters`, `TestTramsEnSegons`, `TestEdicioMapa`),
> `test_tempo_trams.py`, `test_despatx_edicio.py`, `test_edicio.py`
> (`TestUndoTemps`, `TestLlistaTempo`) i `test_pipeline.py`.
>
> Seguiment i verificacions (prova de mutació, regla a regla): **`docs/archive/AUDITORIA_REGLES.md`**.

---

## 13. Temps, compàs i graella

> **Contracte fusionat ací el 23-10-2026** (abans vivia a
> `docs/REGLES_TEMPS_GRID.md`, ara a `docs/archive/`). Si el codi no el complix,
> **és un bug del codi**. Un canvi d'estes regles necessita el vistiplau
> explícit de l'operador i queda al `CHANGELOG`.
>
> **Resum**: *els segons manen per a l'àudio; els clips de tempo/compàs han de
> contindre almenys un beat sencer de la graella del Snap; el BPM semblant es
> conserva i el compàs s'ajusta abans d'allunyar el tempo; el primer inici i
> l'últim final poden ser lliures.*

### 13.1 Els segons són la font de veritat de l'àudio

- Acords i seccions es guarden en **segons**: canviar BPM o compàs **no els mou**
  ni els fa sonar en un altre instant de la WAV.
- Només es recalcula la **posició musical** (etiquetes de compàs de la UI i
  columnes `compas_ini`/`compas_fi` de `estructura_ABC.csv`). Alinear a la
  graella és **Quantitza**, explícit; res no es mou sol.
- **Precisió de l’offset**: la GUI en mostra 3 decimals, però el model conserva
  el valor intern (p. ex. `1.207438`). Recarregar el visor, analitzar només
  acords o canviar el BPM no ha d’arredonir-lo a `1.207`.
- **Codi:** `visor._regenera_posicions_musicals` · `tempo_map`
- **Test:** `test_edicio` (regla 10) · `test_tempo_map`

### 13.2 Els trams de tempo/compàs manen sobre la graella

- El mapa (`tempo_trams`) definix el BPM i la mida de compàs a cada instant; la
  graella, el regle, les coordenades `compàs.temps.subdivisió`, el **snap**, el
  metrònom, la numeració i els exports **en deriven**.
- `app/tempo_map.py` és l'**únic motor** del temps; el visor només n'aplica el
  resultat (mai calcula graella pel seu compte).
- **Codi:** `tempo_map.TempoMap` · `visor._refresca_tempo_map` (punt únic de construcció)
- **Test:** `test_tempo_map`

### 13.3 Cobertura, ordre i contigüitat del mapa

- Els trams cobreixen **tota la WAV**, de 0 a la durada, **contigus i ordenats**:
  `Σ trams = durada`, sense forats, solapaments ni durades nul·les o negatives.
- El mapa buit no existix: sense trams, se'n crea un de sol amb el transport.
- Si **no se sap la durada** (`durada == 0`: WAV absent o encara no carregat) la
  cobertura **no s'imposa**: es conserva el `fi` de l'últim tram. Inventar-hi 0
  deixava el tram invertit (10 → 0) i eixe mapa es desava al disc.
- La contigüitat és **estructural** (regla #2): el `fi` de cada tram és l'`ini`
  del següent, i `TempoMap` ho re-deriva en construir-se (`test_tempo_map` ›
  `test_el_mapa_es_contigu_encara_que_li_donen_forats`).
- **Codi:** `tempo_map.neteja_trams` (repara i avisa) · `normalitza_trams` ·
  `TempoMap.__init__` · `visor._refresca_tempo_map`
- **Test:** `test_tempo_map` · `test_edicio` ›
  `TestLlistaTempo.test_el_mapa_viu_sempre_es_contigu_i_cobert`

### 13.4 Beats sencers i valors vàlids

> **Contracte nou (2026-11-04, decisió explícita de l'operador).** Ja **no**
> s'exigixen compassos sencers ni fronteres en línia de compàs.

- Cada clip de BPM/compàs ha de contindre **almenys un beat sencer** de la
  graella que decidix el **Snap** de l'app:
  - **Snap = Beats QM** → mana la graella de beats QM.
  - **Qualsevol altre mode** (o Snap desactivat) → mana la graella de beats
    BPM/compàs.
- Un beat sencer vol dir que hi ha un interval `[beat_i, beat_i+1]` complet
  dins del clip; no n'hi ha prou que el clip dure més d'un beat.
- **Fronteres interiors**: han de caure en una línia de beat de la graella
  seleccionada.
- **Excepcions d'extrems**:
  - **1 clip**: inici i fi lliures.
  - **2 clips**: el primer inici és lliure i l'últim final és lliure; la
    frontera compartida ha de caure a la graella.
  - **3 o més**: el primer inici és lliure, l'últim final és lliure i la resta
    de fronteres cauen a la graella.
- Si un clip va **en segons/rubato** (§13.7), la seua frontera és lliure i no
  entra en la regla dels beats.
- **Valors**: BPM 30–350, numerador **1–12** (inclòs `1/4`) i denominador
  2, 4 o 8. Els límits d'edició són compartits a `app/limits.py`.
- Una entrada d'usuari amb BPM o compàs invàlid es rebutja amb avís i sense
  mutació parcial; en carregar un CSV editat fora de l'app, el mapa es repara i
  s'informa de què s'ha corregit.
- **Codi:** `tempo_map.valida_tempo` · `neteja_trams` ·
  `valida_i_normalitza_compassos` · `_mapa_valida_sense_moure`
- **Test:** `test_tempo_map::TestValidaTempo` · `TestCompassosEnters` ·
  `TestContracteBeatsSencers` · `TestPersistencia` · proves GUI dels camps
  d'entrada

### 13.5 Ajust de BPM i compàs

> **Contracte nou (2026-11-04):** es prioritza conservar el BPM i canviar el
> compàs abans d'allunyar el tempo.

- **Prioritat 1: BPM semblant.** En ajustar un clip es conserva el BPM de
  referència sempre que siga possible.
- **Prioritat 2: compàs.** Si el clip no conté cap beat sencer o una frontera
  no cau a la graella, es prova de canviar el denominador (`4/4` → `4/8`…) per
  encaixar-lo.
- **Últim recurs: BPM proper.** Si cap compàs admissible ho resol, es pot
  ajustar el BPM al valor més pròxim que faça el clip múltiple de beats, dins de
  **30–350** i sense anar a la meitat ni al doble del BPM de referència.
- **Acció explícita «Ajusta BPM al compàs»** (franja Editor d’un clip de
  tempo): conserva les fronteres i el compàs, i recalcula el BPM perquè el clip
  tinga un **nombre enter de compassos**. És l’única via que força compassos
  sencers; no s’aplica automàticament a la resta d’edicions.
- **Fronteres i veïns**: canviar el BPM o el compàs d'un clip **no mou** les
  seues fronteres ni re-tempa els veïns. Els segons són la font de veritat.
- **Arrossegar**: el punter fixa Δt; s'ajusten les fronteres i, si cal, el
  compàs/BPM dels costats amb la prioritat anterior. No hi ha mínim de 0,5 s:
  només s'evita una durada zero o un BPM impossible.
- Un tram **rubato** (`tipus=rubato`) **no té cap regla** de duració ni de BPM:
  es mou lliurement. El veí amb compàs conserva el BPM i ajusta el compàs si
  cal; la frontera amb el rubato és lliure.
- **Codi:** `tempo_map.canvia_bpm_local` · `ajusta_bpm_a_compassos` ·
`_millora_signatures_clips` · `mou_frontera_retempo` ·
`ajusta_trams_a_marcadors`
- **Test:** `test_tempo_trams`

### 13.6 Fronteres a mà i marcadors

- La frontera **la col·loca el músic** (damunt del pic de l'ona, d'un marcador o
  on decidisca). El snap és **opcional** i, si s'usa, és el **snap normal del
  timeline**, no la graella del tempo vell.
- **La graella de validació és la del Snap**: amb **Beats QM**, mana QM; en
  qualsevol altre mode, mana BPM/compàs (§13.4).
- **Arrossegar és lliure**: amb el snap apagat, inici i fi es poden moure dins
  de la WAV; els clips afectats conserven el BPM i, si cal, se'ls ajusta el
  compàs perquè complisquen la regla del beat sencer. No hi ha mínim de 0,5 s:
  el que no pot passar és que un clip quede **sense durada** o no continga cap
  beat.
- **Inici i fi són editables** —arrossegant la vora al timeline o escrivint-los a
  la franja Editor (`Inici (s)` / `Fi (s)`, només en mode tempo). Com que la
  frontera és única, moure'n un mou **eixa** frontera; **l'extrem contrari del
  clip no es mou** i es recalcula el BPM del clip editat i, si cal, el del veí:

  | Gest | Resultat |
  |---|---|
  | `ini` del **1r** clip | **rebutjat + avís** (és l'inici de la WAV) |
  | `fi` de l'**últim** clip | **rebutjat + avís** (és la fi de la WAV) |
  | `ini` de qualsevol altre | mou la frontera `(i-1, i)`; el `fi` del clip **no** es mou; s'ajusten compàs/BPM si cal |
  | `fi` de qualsevol altre | mou la frontera `(i, i+1)`; l'`ini` del clip **no** es mou; s'ajusten compàs/BPM si cal |
  | qualsevol dels dos amb un costat rubato (`tipus=rubato`) | es mou la frontera; el costat **rubato** no canvia, el costat **amb compàs** conserva el BPM i ajusta el compàs si cal |

  Si l'instant demanat no és possible (passaria del veí, o deixaria un tram sense
  durada), s'aplica el més a prop i **s'avisa**.
- **`+` (marcador)**: seguix la **graella del Snap**:
  - Snap **Beats QM** → sempre s'encaixa al beat QM més pròxim;
  - qualsevol altra graella → s'encaixa a la graella BPM/compàs;
  - si Snap està desactivat, es respecta la posició del cursor.
  Si la graella QM no té beats, no es crea el marcador i s'avisa. Els clips
  afectats es recalculen amb la prioritat BPM → compàs.
- La fi del primer pot caure **exactament** en el compàs 1 (pre-roll pur); si el
  primer tram no té cap compàs, moure'n la fi **mou el compàs 1** (offset).
- El gest és **local**: els **marcadors humans** lligats a la frontera **viatgen
  amb ella** (i s'esborren amb ella), i el clip d'estructura creat en eixe punt la
  seguix per coincidència de temps (±5 ms) fins que s'edite a mà.
- **Codi:** `tempo_map.mou_frontera_retempo` · `visor._on_tempo_mogut` ·
  `visor._aplica_editor_tempo` · `marcadors`
- **Test:** `test_despatx_edicio`

### 13.7 Clips de rubato (`tipus=rubato`)

> **Implementació (2026-11-02):** subplà de rubato complet — motor, model,
> visor/graella, accions d'usuari i exportació (amb `AVIS_APROXIMACIO.txt` i
> text al MusicXML).

- **Qualsevol** clip del carril pot ser rubato (inici, mig o final). Els seus
  **segons són invariables**: cap canvi de BPM o compàs el mou.
- **Com s'escriu**: al `mapa_tempo.csv`, `tipus=rubato` i `compassos` amb la
  seqüència derivada (`4/4*3+3/4`). El BPM i la seqüència són **derivats** del
  clip mètric anterior (si no n'hi ha, el següent; si tampoc, el transport), no
  una detecció. Són de **només lectura** i es recalculen quan canvia la durada
  o el veí.
- **Graella**: la graella mètrica del rubato és una representació derivada; la
  **graella de temps** sempre és visible i no en depén. Un rubato inicial ocupa
  compassos negatius (pre-roll) i el primer clip mètric és `1.1`.
- **Exportació**: la representació mètrica exportada s'identifica visiblement
  com a aproximada; els CSV del model conserven `tipus=rubato` i els segons.
  No es converteix mai un rubato en un BPM «real» de manera silenciosa.
- **Numeració**: els compassos derivats del rubato continuen la sèrie; el clip
  mètric següent comença en una línia de la graella. Els rubatos adjacents es
  fusionen.
- **Vores**: es mouen com la resta del mapa; el veí amb compàs conserva el BPM
  i ajusta el compàs si cal. Un sol desfer.
- **Convertir a normal**: es parteix en clips normals, un per segment de compàs.
- **Paritat #11**: s'aplica igual (clip, llista ⑭ i franja Editor).
- **Codi:** `app/rubato.py` (derivació pura) · `app/mapa_tempo.py` (model) ·
  `tempo_map.canvia_bpm_local` / `mou_frontera_retempo` (fronteres).
- **Test:** `tests/test_rubato.py` · `tests/test_mapa_tempo.py` i, quan estiga
  integrat, `test_tempo_map` / `test_edicio`.

### 13.8 Detecció i export del mapa

- Amb un **tram seleccionat**, *Detecta* analitza **només** l'àudio d'eixe tram; el
  downbeat és el seu inici. En un tram delimitat per marcadors **Δt és fix**: el
  BPM detectat només servix per a comptar compassos
  (`N = round(Δt · BPM_ref / (bq · 60))`, mínim 1) i s'aplica el **BPM derivat
  exacte** (`N · bq · 60 / Δt`), que clava les barres entre els dos punts.
- La **fi del tram no es mou** ni els trams següents tampoc; si el BPM derivat cau
  fora de 30–350 o no hi cap cap compàs sencer, **s'avisa** en compte d'aplicar-lo.
- S'aplica **directament**, com una sola operació de desfer, amb el BPM detectat al
  missatge. Sense tram seleccionat, la detecció global és una via separada.
- Per a **tempo variable**, *Analitza ▸ Detecta el tempo per trams…* fa el mapa
  sencer (un BPM cada N compassos, fronteres en línia de beat) i el valida amb
  estes mateixes regles.
- L'export porta les **tres parts** (acords, estructura i **mapa**):
  `mapa_tempo.csv` + còpia a `mapa_tempo/`; les columnes de compàs de l'ABC en surten
  (lligat a #12).
- **Codi:** `tempo_map.retempo_tram_detectat` · `app/tempo.py` ·
`pipeline.desa_tempo_map`
- **Test:** `test_pipeline` · `test_tempo_trams`

### 13.9 Edició de l'àudio del projecte

> **Estat:** requisit de producte aprovat (2026-11-01), implementat pel que fa a
> importació, backups, retall/afegit als extrems, sincronització del model,
> desfer/refer i **exportació d'àudio amb FFmpeg**. La restauració d'una còpia
> des de la GUI i les proves visuals continuen pendents.

- L'edició afecta només la **còpia WAV de treball** dins del projecte; l'original
  importat es conserva. Els WAVs silenciosos generats per als acords/seccions no
  es modifiquen (regla #6).
- La retallada i l'afegit de silenci als extrems són una transformació conjunta
  del fitxer d'àudio i del model en segons:
  - En retallar l'inici `t`, s'elimina l'àudio anterior al tall; els elements
    musicals, marcadors i fronteres que queden es desplacen `−t`, i l'offset
    també es desplaça `−t`. El contingut anterior al nou zero desapareix.
  - En retallar el final a `D`, els elements posteriors a `D` s'eliminen i els
    intervals que travessen `D` s'escurcen; la durada nova del WAV és `D`.
  - En afegir silenci a l'inici `t`, el so existent i les seves referències
    musicals es desplacen `+t`; l'offset es desplaça `+t`. Es crea un interval
    d'acord `N` per al silenci i la secció existent el continua cobrint.
  - En afegir silenci al final, la cobertura s'estén fins a la nova durada amb
    acord `N`; la secció existent i l'últim tram del mapa cobreixen l'extensió.
- Després de cada operació, acords, seccions i mapa continuen ordenats,
  contigus i cobrint `[0, durada WAV]` (regles #1–4 i §13.3). El mapa conserva
  la relació entre compassos, offset i els mateixos instants musicals; el
  pre-roll i el final poden continuar sent parcials segons §13.4.
- L'edició d'àudio és una acció explícita diferent d'un canvi de BPM/compàs:
  **§13.1 continua vigent** —canviar el tempo no mou els clips—; en canvi,
  retallar o inserir àudio transforma els temps perquè les marques segueixin el
  mateix so. Les restriccions de gest de §13.6 per a les vores del mapa no
  autoritzen ni prohibeixen aquesta operació d'àudio.
- Cada operació mostra una previsualització durant l'arrossegament i s'aplica en
  deixar anar; àudio i model són **atòmics** i una sola acció de desfer/refer.
  L'ajust a línies de compàs és commutable; la proposta automàtica de silenci
  per completar compassos necessita confirmació. El tall es fa al punt exacte
  triat, arrodonit al fotograma més pròxim; no es mou a un pas per zero. Cada
  nova vora entre àudio i silenci rep un fade curt d'entrada o eixida de **4 ms**
  per reduir clics. El crossfade entre dos clips d'àudio queda fora de l'abast
  inicial, que només té un WAV; si s'afegeix edició entre clips, s'hi aplicarà
  el crossfade curt habitual.
- L'historial conjunt de desfer/refer conserva les **10 últimes accions totals**
  (musicals i d'àudio); quan se supera el límit, l'acció més antiga es descarta
  i l'app ho comunica.
- Els canvis s'escriuen primer en un temporal i es validen abans de substituir
  la còpia del projecte. Un error no pot deixar l'àudio i el model en estats
  diferents.
- Les còpies de seguretat versionades inclouen també el WAV de treball i els
  marcadors, perquè restaurar una còpia recupere l'àudio i el model del mateix
  estat.
- **Codi i tests:** la còpia del WAV i `marcadors.csv` als backups, el seu
  caràcter atòmic i la detecció de canvis tenen codi i proves. També hi ha
  proves del motor PCM, fades mono/estèreo, quatre gestos de les nanses,
  retall/afegit, offset i marques, cobertura dels tres carrils, `N`, undo/redo
  mixt i recuperació davant d'una fallada de publicació. L'**exportació
  d'àudio** té proves pròpies (`tests/test_exporta_audio.py`). Abans de donar
  la resta per implementada, afegir proves visuals de previsualització i la
  restauració conjunta d'àudio i model des d'un backup.

### Com s'aplica (notes d'implementació)

- En **carregar** un projecte vell, el mapa es mostra **tal com és** (no es
  rebutja) i es **fusionen** els trams adjacents amb el mateix BPM i compàs: no
  representen cap canvi musical. Una partició manual de dos trams iguals es
  respecta mentre s'edita.
- **Totes** les edicions de la GUI que re-temporitzen passen pel re-tempo local; si
  el resultat no complix el contracte, **no es toca res** i s'avisa. El backend
  permissiu és per a càrregues i eines internes; el camí d'usuari és el que fa
  complir la regla. **No queda cap camí d'usuari amb *ripple***.
- Quan el model es reconstrueix (quantitzar, desfer…), la selecció es notifica
  buida i l'editor s'ha de buidar o refrescar: **mai el temps vell** d'un clip que
  s'ha mogut; després de quantitzar es recupera, si encara existix, el clip que
  s'estava editant (punt 2 del preàmbul).
