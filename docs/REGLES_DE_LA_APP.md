# ⚠️ REGLES DE LA APP — invariants inmutables

> ## 🔴 IMPORTANT — LLEGEIX-HO ABANS DE TOCAR CODI
> Aquestes són les **regles d'or (invariants)** d'AUTO CHORDS.
> **Cap canvi de codi pot trencar-les.** Si una funcionalitat nova xoca amb una
> regla, es canvia **la funcionalitat**, no la regla (tret de decisió explícita
> de l'operador, que s'ha de documentar aquí **i** al `CHANGELOG`).
>
> Cada regla té la seva **validació** al codi i un **test** que la comprova
> (les 11: vegeu la nota del final).
> Referenciades a `ROADMAP_HISTORIA.md` (§Notes d'implementació) i `DEVELOPING.md`.
>
> ## ‼️ S'HA DE COMPLIR **SEMPRE** — a TOTS els punts
> Les regles **no** són una comprovació «de tant en tant»: s'han de complir en
> **TOTS** aquests punts, sempre i alhora:
> 1. **Edició en viu** — GUI del visor **i** pont MCP: cada mutació (afegir,
>    eliminar, moure, redimensionar, reanomenar) ha de deixar el model **vàlid**.
> 2. **Visor** — el que es veu a la pantalla reflecteix el model vàlid.
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
(contracte: `docs/REFACTOR_INICI_FI.md`).

## 3. Durades derivades
La durada d'un clip **no s'emmagatzema**: es **deriva** (l'inici del següent, o
la durada de la WAV per a l'últim). El model `Clip(ini, fi, payload)` **sí** que
té un camp `fi`, però **no és la dada que mana**: sempre es torna a derivar de la
frontera (l'`ini` del següent) — la **cadena de fronteres** és la font de veritat.

## 4. Cobertura total
**La suma dels clips d'acords = la durada de la WAV**, **la suma dels clips
d'estructura = la durada** i **la dels trams de BPM/compàs = la durada**,
en qualsevol mode (**Lliure** o **BPM · compàs**) i
amb o sense **snap**: el 1r clip arrenca a **0** (capçalera «N» si cal) i
l'últim arriba a la **durada**. La regla **mana sobre el snap** (que només
quantitza els límits **interiors**). → `pipeline.normalitza_cobertura()`.
**S'aplica SEMPRE** (§«S'ha de complir SEMPRE»): en l'**edició en viu** (després de
cada mutació al visor i al MCP), al **visor**, al **CSV** que es desa i en
**exportar** (CSV/ABC + wavs) — **no només** «en carregar el visor i en exportar».

## 5. Una sola font de veritat
El model viu al **backend**, no a la UI. Hi ha **dos backends**: `app.pipeline`
(acords i estructura) i `app.tempo_map` (trams de BPM/compàs). La UI
(`app.visor` + `app.timeline`) **en reflecteix** l'estat: en guarda una còpia
(`self.acords`/`self.seccions` i `self.tempo_trams`/`self.tempo_map`), però
**aquesta còpia mai no mana** — tota mutació passa abans per les funcions de
`pipeline`/`tempo_map`, i el visor només n'aplica el resultat.

## 6. Les WAVs només via `pipeline.exporta_total()`
L'edició **mai** toca les WAVs generades; només s'escriuen en **exportar**, des
del backend `pipeline.exporta_total(...)`. La UI hi delega via els mètodes
`exporta()` (`app.visor` / `app.main`). «Mai toca els WAVs generats.»
→ Paritat d'exportació dels **3 carrils**: vegeu la **regla 11**.

## 7. Instància única
No poden córrer **dues instàncies** de l'app alhora (un lock a `tempfile`).
→ `main.py` + `plataforma.bloqueja_instancia_unica`.

## 8. Temps vàlids
Cap temps **negatiu** ni cap durada **≤ 0**.

## 9. Portabilitat
Tot el que sigui natiu es compila per a **macOS 10.13+** i **sense AVX**
(el Q9400): cap binari del paquet pot superar **`minos 10.13`** ni requerir AVX.
→ `archive/PLANIFICACIO_MACOS.md` · verificat al CI (`eines/verifica_minos_macos.py`).

## 10. Estat en un directori escriptible
El **log / opcions / temp** van sempre a un directori **escriptible** — mai dins
un paquet de només lectura (AppImage, `.app` en quarantena). → `app/config.py`.

## 11. Paritat d'edició i tracte visual (acords ↔ estructura ↔ BPM/compàs)

Els clips d'**acords**, d'**estructura** i els **trams de BPM/compàs** són
iguals davant l'edició i la visualització. Tota operació d'un tipus ho ha de
ser per als altres, i pel **mateix camí d'usuari**.

- **Joc d'operacions comú**: afegir · eliminar · partir (pel cursor · **per la
  meitat**) · moure ·
  redimensionar · desfer/refer. Reanomenar i duplicar/fusionar són comuns a
  **acords i estructura**; als **trams de BPM/compàs** el contingut és
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
- **Semàntica de les operacions**: *partir* un acord = dos trossos amb el
  mateix nom (el de la part nova és editable, per defecte heretat);
  *fusionar* acords = en queda l'harmonia de l'esquerre. Mateix patró que
  l'estructura. *Partir* un tram de BPM/compàs = dos trams amb el mateix
  BPM i compàs (el de la dreta és editable).
- **Paritat a l'exportació**: el paquet exportat tracta els **tres** tipus igual,
  cadascun amb la seva **carpeta pròpia**: acords (`acords.csv` + `wavs_acords/`) ·
  estructura (`estructura_ABC.csv` + `wavs_estructura/`) · **mapa de tempo/compàs**
  (els seus CSV, en carpeta pròpia). ⏳ **Pendent d'implementació** (2026-10-18):
  avui el mapa de tempo/compàs encara **no** surt al paquet exportat.

→ Validació: `app/visor.py` + `app/pipeline.py` (joc d'operacions simètric) ·
test `tests/test_regla11_paritat.py` — **✅ FET** (verd; en fila amb les regles 1–10).

---

## 📌 Evidència: 2 bugs de producció (`OC-6/332-334`, 2026-10-13)

Aquests dos casos reals són el motiu del §«S'ha de complir SEMPRE» de dalt:

1. **L'exportació ignorava les edicions de seccions** (`OC-6/332`) — **greu**.
   `app/main.py` passava a `pipeline.exporta_total` la sortida **crua** del
   qm-segmenter (`segments.csv`) i **regenerava** l'estructura des d'allà, ignorant
   el model editat (`self.seccions`). Resultat: `estructura_ABC.csv` i
   `wavs_estructura/` **tornaven a les seccions originals**. (Els **acords**, en
   canvi, sí que s'exportaven del model editat.) → L'exportació ha de sortir del
   **model**, no de dades intermèdies.

2. **La COBERTURA (#4) no s'aplicava a les edicions en viu** (`OC-6/333`).
   En eliminar el **1r** acord, el primer clip passava de **0,00** a **0,30** i el
   forat es veia **al visor i al CSV** (`acords.csv`: `0.30,N … 192.18,Em7`; hauria
   de ser `0.00 … 199.60`). `pipeline.normalitza_cobertura()` només s'aplicava a
   l'anàlisi, en carregar el visor i en exportar l'ABC — **no** després d'editar
   (ni pel camí de la GUI ni pel del MCP). → La cobertura s'ha de reaplicar
   **després de cada mutació**.

> 🧭 **Lliçó**: una regla d'or **no** pot dependre d'*on* s'aplica el codi; ha de
> valer a **tots** els punts (edició en viu, visor, CSV i exportació). Aquests 2
> bugs van aparèixer precisament perquè la validació vivia només en alguns passos.
> **Seguiment**: fix assignat a **OC-4** + tests de regressió (detall a `OC-6/334`).

---

> 📌 **En afegir una regla nova**: numera-la aquí, afegeix-ne la validació al
> codi i un test que la comprovi. **Les 11 regles ja tenen el seu test**:
> `tests/test_regles_or.py` (1, 3, 5, 6, 7, 8 i 10) · `test_seccions_contigues` (2)
> · `test_cobertura_viu` (4) · `test_requirements` (9) · `test_regla11_paritat` (11).
