# ⚠️ REGLES DE LA APP — invariants inmutables

> ## 🔴 IMPORTANT — LLEGEIX-HO ABANS DE TOCAR CODI
> Aquestes són les **regles d'or (invariants)** d'AUTO CHORDS.
> **Cap canvi de codi pot trencar-les.** Si una funcionalitat nova xoca amb una
> regla, es canvia **la funcionalitat**, no la regla (tret de decisió explícita
> de l'operador, que s'ha de documentar aquí **i** al `CHANGELOG`).
>
> Cada regla té la seva **validació** al codi i un **test** que la comprova
> (les 1–19, totes amb el seu test). L'**auditoria continuada** (prova de mutació,
> regla a regla) viu a `docs/archive/AUDITORIA_REGLES.md`.
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
→ `pipeline` + `tempo_map` (backends); el visor sempre hi delega.
test `tests/test_edicio.py` › `TestRegla5FontDeVeritat`.

## 6. Les WAVs només via `pipeline.exporta_total()`
L'edició **mai** toca les WAVs generades; només s'escriuen en **exportar**, des
del backend `pipeline.exporta_total(...)`. La UI hi delega via els mètodes
`exporta()` (`app.visor` / `app.main`). «Mai toca els WAVs generats.»
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
  té, des del 22-10-2026, **franja Editor** (mode BPM/Compàs, amb `0/0` =
  segons) i **llista pròpia** (⑭: `Inici (s)` · `Fi (s)` · `BPM` · `Compàs`), amb
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
amb `tempo.csv` i `compas.csv`).
→ `pipeline.exporta_total(..., mapa_tempo=)` — rep el mapa del **model viu** (com
`acords`/`seccions`); si no se li passa, el paquet queda exactament com era.
test `tests/test_pipeline.py` › `TestRegla12ParitatExport` — **✅ FET (2026-10-18)**.

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
> **Resum**: *els segons manen per a l'àudio; els trams de tempo/compàs manen per
> a la graella; els trams interiors tenen compassos enters; el punter fixa Δt, els
> compassos es conserven i el BPM en deriva (ajust local, sense arrossegar els
> trams següents); i el primer inici i l'últim final són les úniques excepcions.*

### 13.1 Els segons són la font de veritat de l'àudio

- Acords i seccions es guarden en **segons**: canviar BPM o compàs **no els mou**
  ni els fa sonar en un altre instant de la WAV.
- Només es recalcula la **posició musical** (etiquetes de compàs de la UI i
  columnes `compas_ini`/`compas_fi` de `estructura_ABC.csv`). Alinear a la
  graella és **Quantitza**, explícit; res no es mou sol.
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

### 13.4 Compassos enters i valors vàlids

- Cada tram **interior** té un **nombre enter de compassos** i les seues
  fronteres cauen en **línia de compàs** (1,5 compassos és invàlid encara que
  dure més d'un compàs).
- **Excepcions**: el **primer inici** (offset/pre-roll) i l'**últim final** (fi de
  la WAV) poden ser a mig compàs; si un clip va **en segons** (§13.7), la seua
  frontera és lliure i el clip mètric del costat pot acabar o començar amb un
  **compàs parcial** (com el `*` dels marcadors de compàs de REAPER).
- **Valors**: BPM 30–350 (`BPM_EDIT_MIN/MAX`) i compàs 1–12 sobre 1–16 (lligat a
  la regla #8).
- **Codi:** `tempo_map.valida_i_normalitza_compassos` · `_mapa_valida_sense_moure`
- **Test:** `test_tempo_map::TestCompassosEnters`

### 13.5 Re-tempo local (BPM i compàs)

- **Jerarquia**: el punter/tall mana sobre **Δt**; el **nombre de compassos N** es
  conserva i el **BPM en deriva** (`BPM = N · bq · 60 / Δt`).
- En canviar el **BPM**, la durada del tram s'ajusta i la frontera amb el veí es
  mou; el veí **conserva els seus compassos** i **recalcula el seu BPM**.
  L'ajust és **local**: només els dos trams que toquen eixa frontera.
- En canviar **només el compàs** (`4/4` → `3/4`…), **mana la durada** i es
  recompta `N` (el BPM s'ajusta el mínim perquè siga enter): conservar `N` faria
  el tram més llarg (el cas `1/4` amb 551 compassos).
- **Sense *ripple***: les fronteres dels trams **següents no es desplacen** ni els
  marcadors es mouen, si no toquen la frontera afectada. L'**últim tram** queda
  acotat per la fi de la WAV; si és el veí, conserva BPM i fi i absorbix el
  desplaçament en compassos.
- **Banda al re-tempo (decisió 23-10-2026)**: en arrossegar, el ratolí fixa Δt
  i **no** hi ha mínim de 0,5 s, però un tram **amb compàs** conserva N i no pot
  quedar-se fora de **30–350 BPM** — eixa banda és el que impedix l'estat absurd
  d'un clip d'1 ms a 1.200.000 BPM. Si el gest el deixaria fora, **es rebutja** i
  l'avís diu **entre quins segons** sí que hi cap.
- Un tram **en segons** (`0/0`, rubato) **no té cap regla** de duració ni de BPM:
  es mou lliurement. Però **el seu veí amb compàs sí**: eixe costat conserva N i
  en deriva el BPM (si no, quedaria amb compassos fraccionaris, §13.4) i respecta
  la banda.
- **Codi:** `tempo_map.canvia_bpm_local` · `canvia_compassos_tram` ·
`retempo_tram_detectat` · `snap_frontera_compas`/`_ripple_des_de` (només per a
`repara_fronteres` i l'anàlisi guiat, que creen el mapa des de zero)
- **Test:** `test_tempo_trams`

### 13.6 Fronteres a mà i marcadors

- La frontera **la col·loca el músic** (damunt del pic de l'ona, d'un marcador o
  on decidisca). El snap és **opcional** i, si s'usa, és el **snap normal del
  timeline**, no la graella del tempo vell.
- **La graella s'ajusta a la frontera**: es conserven els compassos dels dos
  costats i es recalcula el BPM de cada un; per construcció la frontera **sempre
  cau en línia de compàs**.
- **Arrossegar és lliure** (22-10-2026, amb la banda del §13.5 des del
  23-10-2026): amb el snap apagat, inici i fi es poden moure sempre que el tram
  **amb compàs** es quede dins de 30–350 BPM; l'extrem contrari **no es mou** i
  només es recalcula el BPM de dins. No hi ha mínim de 0,5 s: el que no pot
  passar és que un tram quede **sense durada** o a un BPM impossible.
- **Inici i fi són editables** —arrossegant la vora al timeline o escrivint-los a
  la franja Editor (`Inici (s)` / `Fi (s)`, només en mode tempo). Com que la
  frontera és única, moure'n un mou **eixa** frontera; **l'extrem contrari del
  clip no es mou** i es recalcula el BPM del clip editat i, si cal, el del veí:

  | Gest | Resultat |
  |---|---|
  | `ini` del **1r** clip | **rebutjat + avís** (és l'inici de la WAV) |
  | `fi` de l'**últim** clip | **rebutjat + avís** (és la fi de la WAV) |
  | `ini` de qualsevol altre | mou la frontera `(i-1, i)`; el `fi` del clip **no** es mou; re-tempo del clip i del **veí anterior** |
  | `fi` de qualsevol altre | mou la frontera `(i, i+1)`; l'`ini` del clip **no** es mou; re-tempo del clip i del **veí posterior** |
  | qualsevol dels dos amb un costat en segons (`0/0`) | es mou la frontera; el costat **rubato** no canvia (ni BPM ni compàs), el costat **amb compàs** conserva N i re-tempa (banda 30–350) |

  Si l'instant demanat no és possible (passaria del veí, o deixaria un tram sense
  durada), s'aplica el més a prop i **s'avisa**.
- La fi del primer pot caure **exactament** en el compàs 1 (pre-roll pur); si el
  primer tram no té cap compàs, moure'n la fi **mou el compàs 1** (offset).
- El gest és **local**: els **marcadors humans** lligats a la frontera **viatgen
  amb ella** (i s'esborren amb ella), i el clip d'estructura creat en eixe punt la
  seguix per coincidència de temps (±5 ms) fins que s'edite a mà.
- **Codi:** `tempo_map.mou_frontera_retempo` · `visor._on_tempo_mogut` ·
  `visor._aplica_editor_tempo` · `marcadors`
- **Test:** `test_despatx_edicio`

### 13.7 Clips en segons (`0/0`, rubato)

- **Qualsevol** clip del carril pot existir en segons (no només el primer o
  l'últim): un passatge rubato al mig del tema.
- **Com s'escriu**: `num = 0` i `den = 0` a `compas.csv`/`tempo.csv`; al diàleg
  del clip, la casella **«En segons (sense compàs: rubato)»**; a la franja
  Editor, el camp **Compàs** amb `0/0` o «segons».
- **Dura el que diu l'àudio**: no té graella, ni compassos enters, ni obligació de
  caure en cap línia. Dins del clip, regle i etiquetes mostren **temps**
  (`m:ss.mmm`) i el `snap` no hi encaixa res.
- `bpm` es conserva com a **referència de notació** (100 per defecte): no afecta
  cap graella. La **partitura** l'exporta com a compassos a 100 BPM 4/4 (1 compàs
  = 2,4 s) i pot acabar amb un compàs **parcial**.
- Els seus compassos **no compten** per a la numeració: el primer clip amb
  compàs després del rubato continua la sèrie.
- Les **vores** es mouen sense recalcular **el seu** BPM (el «BPM» d'un rubato
  és de notació); el **veí amb compàs** sí que re-tempa (§13.5). Canviar-li
  «compassos» es rebutja amb avís. `tempo.csv`, `compas.csv` i la còpia a `mapa_tempo/` porten
  `0,0` i res més canvia.
- La **paritat #11 s'hi aplica igual**: clip, llista ⑭ i franja Editor.
- **Codi:** `tempo_map.Tram.lliure`/`es_lliure`/`num_ef` · `canvia_bpm_local` ·
`mou_frontera_retempo` · `visor._secs_a_cb`
- **Test:** `test_tempo_map::TestTramsEnSegons` · `test_edicio::TestLlistaTempo`

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
  sencer (un BPM cada N compassos, fronteres en línia de compàs) i el valida amb
  estes mateixes regles.
- L'export porta les **tres parts** (acords, estructura i **mapa**): `tempo.csv` +
  `compas.csv` + còpia a `mapa_tempo/`; les columnes de compàs de l'ABC en surten
  (lligat a #12).
- **Codi:** `tempo_map.retempo_tram_detectat` · `app/tempo.py` ·
`pipeline.desa_tempo_map`
- **Test:** `test_pipeline` · `test_tempo_trams`

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
