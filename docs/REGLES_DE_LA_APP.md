# ⚠️ REGLES DE LA APP — invariants inmutables

> ## 🔴 IMPORTANT — LLEGEIX-HO ABANS DE TOCAR CODI
> Aquestes són les **regles d'or (invariants)** d'AUTO CHORDS.
> **Cap canvi de codi pot trencar-les.** Si una funcionalitat nova xoca amb una
> regla, es canvia **la funcionalitat**, no la regla (tret de decisió explícita
> de l'operador, que s'ha de documentar aquí **i** al `CHANGELOG`).
>
> Cada regla té la seva **validació** al codi i un **test** que la comprova
> (les 1–12, totes amb el seu test). L'**auditoria continuada** (prova de mutació,
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
>    `tests/test_vista_segueix_model.py`, que comprova **després de cada operació**
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
→ `visor._valida_canvis_acords` / `_valida_canvis_seccions` /
`tempo_map.normalitza_trams`.

## 2. Contigüitat
Cada clip comença **exactament** on acaba l'anterior: `prev.fi == curr.ini`, per a
**les tres** famílies (acords, seccions i trams de BPM/compàs), amb el model
unificat `Clip(ini, fi, payload)` — sense forats ni encavalcaments. (Els **extrems**
0 ↔ durada són competència de la regla 4.)
→ `timeline.py` · `pipeline.filtra_seccions` · `tempo_map.normalitza_trams`
(contracte: `docs/archive/REFACTOR_INICI_FI.md`).

## 3. Durades derivades
La durada d'un clip **no s'emmagatzema**: es **deriva** (l'inici del següent, o
la durada de la WAV per a l'últim). El model `Clip(ini, fi, payload)` **sí** que
té un camp `fi`, però **no és la dada que mana**: sempre es torna a derivar de la
frontera (l'`ini` del següent) — la **cadena de fronteres** és la font de veritat.
→ És **estructural** (el model no té camp de durada); l'acotament del fi de
l'última secció el cobreix `tests/test_pipeline_export.py`.
test `tests/test_regles_or.py` › `TestRegla3DuradesDerivades`.

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
test `tests/test_regles_or.py` › `TestRegla5FontDeVeritat`.

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
test `tests/test_regles_or.py` › `TestRegla8TempsValids`.

## 9. Portabilitat i maquinari objectiu
L'app ha de córrer als **3 SO** — **Linux** (AppImage x86_64, compilat a Ubuntu
22.04) · **Windows** (portable x64, Win10) · **macOS** (`.app` per a **10.13 High
Sierra+**, Intel) — i amb el **maquinari mínim objectiu** (**sense AVX**): cap
binari ni dependència del paquet no pot requerir **AVX** ni superar
**`minos 10.13`**.
→ **`minos`**: verificat al CI (`eines/verifica_minos_macos.py`, pas 6b). →
**AVX**: garantit pel build (CPython portable **genèric**, host VAMP `-msse -msse2`,
`numpy` **1.x**) i `tests/test_requirements.py`, que inclou el guard **`GuardAvxTests`**
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
  tram és `Tram(ini, fi, bpm, num, den)`), el camp «Família» de l'Editor (només
  secció), l'edició **inline** i «Reanomena en bloc» (només acord/secció) i el
  **color/carri** del timeline (distinció de tipus).
- **Diferències legítimes del carril de BPM/compàs** (NO són manca de paritat):
  la seva **alçada** és **mitja** (`timeline_base.LANE_TEMPO_H`) i el contingut
  s'edita **només amb diàleg emergent** (`DialegTramTempo`), mentre que
  acords/seccions tenen la **franja EDITORA integrada**, l'edició **inline** al
  timeline i el «Reanomena en bloc».
- **Semàntica de les operacions**: *partir* un acord = dos trossos amb el
  mateix nom (el de la part nova és editable, per defecte heretat);
  *fusionar* acords = en queda l'harmonia de l'esquerre. Mateix patró que
  l'estructura. *Partir* un tram de BPM/compàs = dos trams amb el mateix
  BPM i compàs (el de la dreta és editable).

→ Validació: `app/visor.py` + `app/pipeline.py` + `app/tempo_map.py` (joc d'operacions
simètric).
test `tests/test_edicio.py` › paritat — **✅ FET (18-10-2026)** per a
l'edició, el tracte visual, la selecció i el **desfer/refer**, incloses les **operacions
MIxtes** de les 3 famílies (esborrar o copiar/enganxar una selecció acord+secció+tram =
una sola operació, un sol `Ctrl+Z`). La **paritat d'exportació** és la **regla 12**.

## 12. Paritat a l'exportació (paquet complet)
El paquet exportat tracta els **tres** tipus igual, cadascun amb la seva part:
acords (`acords.csv` + `wavs_acords/`) · estructura (`estructura_ABC.csv` +
`wavs_estructura/`) · **mapa de tempo/compàs** (**carpeta pròpia** `mapa_tempo/`
amb `tempo.csv` i `compas.csv`).
→ `pipeline.exporta_total(..., mapa_tempo=)` — rep el mapa del **model viu** (com
`acords`/`seccions`); si no se li passa, el paquet queda exactament com era.
test `tests/test_regla12_export.py` — **✅ FET (2026-10-18)**.

---



> 🧭 **Lliçó**: una regla d'or **no** pot dependre d'*on* s'aplica el codi; ha de
> valer a **tots** els punts (edició en viu, visor, CSV i exportació)..

---

> 📌 **En afegir una regla nova**: numera-la aquí, afegeix-ne la validació al
> codi i un test que la comprovi. **Les regles 1–12 ja tenen el seu test**:
> `tests/test_regles_or.py` (1, 3, 5, 6, 7, 8 i 10) · `test_seccions_contigues` (2)
> · `test_cobertura_viu` (4) · `test_requirements` (9) · `test_regla11_paritat` (11)
> · `test_regla12_export` (12).
> La **12** (paritat d'exportació) té el seu test: `tests/test_regla12_export.py`.
>
> Seguiment i verificacions (prova de mutació, regla a regla): **`docs/archive/AUDITORIA_REGLES.md`**.

---

## 🕒 Regles específiques de temps, compàs i graella

El contracte detallat viu a **`docs/REGLES_TEMPS_GRID.md`** i complementa les
regles 1–12:

- els **segons** són la font de veritat de l'àudio; canviar el BPM no mou
  acords ni seccions;
- els **trams de tempo/compàs** manen sobre la graella;
- els trams **interiors** contenen un **nombre enter de compassos** i les
  fronteres cauen en línies de compàs;
- el **primer inici** i l'**últim final** de la WAV són les úniques
  excepcions;
- canviar el BPM d'un tram conserva els seus compassos i **arrossega** les
  fronteres següents (l'últim tram absorbeix);
- la detecció de BPM amb un tram seleccionat analitza **només eixe tram** i
  aplica el canvi directament, amb desfer.
