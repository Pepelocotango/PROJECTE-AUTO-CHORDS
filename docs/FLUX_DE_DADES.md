# Flux de dades: el MODEL editable (i el cru dins el document)

> **En una frase:** el projecte té **una sola capa de fitxers** — el **MODEL**
> (`acords.csv`, `estructura_ABC.csv`, `tempo.csv`, `compas.csv`). El **cru de
> l'anàlisi** (el que retorna el motor *abans* de netejar) viu **dins el
> `.acproj`**, no en fitxers solts. Així el pots reaprofitar (re-neteja,
> re-anàlisi) sense omplir la carpeta de fitxers intermedis.

> Canvi de disseny (2026-10-19): s'han retirat la carpeta `analisi/` (3 fitxers)
> i `segments.csv`. El cru ara és una clau del document. **Sense
> retrocompatibilitat** (l'app s'està construint; els projectes existents són de
> prova).

## 1. Les peces

| Peça | On | Quan s'escriu | Qui la toca |
|---|---|---|---|
| **MODEL** | `acords.csv`<br>`estructura_ABC.csv`<br>`tempo.csv` · `compas.csv` | a **cada edició** | el visor, la quantització, l'anàlisi |
| **CRU** | dins `<nom>.acproj` → `dades["analisi"]` | a cada «Analitza» | **només `Feina.run`** (i el desat del document) |
| **EXPORTS** | `wavs_acords/` · `wavs_estructura/` · `partitura/` · `guia_acords.html` · `mapa_tempo/` · `manifest.csv` | només a «Exporta» | `pipeline.exporta_total` |
| **CÒPIES** | `backup/<data-hora>/` | autosave cada 60 s, si hi ha canvis | `Projecte.fes_backup` |

## 2. Estructura de la carpeta del projecte

```
La meva cançó/                     ← carpeta autocontinguda (portable)
├── La meva cançó.acproj          ← EL DOCUMENT: tempo, opcions, vista i el CRU
├── audio/ tema.wav               ← CÒPIA de l'àudio (mai depèn de fora)
│
├── acords.csv                    ← MODEL: els acords
├── estructura_ABC.csv            ← MODEL: l'estructura A/B/C
├── tempo.csv · compas.csv        ← MODEL: el mapa de BPM/compàs
│
├── wavs_acords/ · wavs_estructura/ · partitura/   ← EXPORTS («Exporta»)
├── guia_acords.html · mapa_tempo/ · manifest.csv   ← EXPORTS
└── backup/ <data-hora>/          ← còpies versionades (fins a 10)
```

## 3. El flux

```
              «Analitza»
                  │
    Chordino ──────┤  (1) el motor retorna el CRU (t, acord) i els talls
    qm-segmenter ──┤      → es queden EN MEMÒRIA
                  │
      ┌───────────┼──────────────────────────────┐
      │  (2) neteja dels acords (opcions del diàleg)
      └──────────────────────────► acords.csv ◄───┘
                                    │
                                    │  (4) engega el visor
                                    ▼
                          ┌────────────────────┐
                          │   edició en viu    │  ← l'usuari edita al visor
                          │ (acords + seccions)│
                          └─────────┬──────────┘
                                    │  desa NOMÉS els 4 CSV del MODEL
                                    ▼
                    acords.csv · estructura_ABC.csv · tempo.csv · compas.csv
                                    ▲
                                    │  (5) quantització del MODEL
                                    └── quantitza
```

En acabar, el cru es desa **dins el `.acproj`** (un sol fitxer, escriptura
atòmica), junt amb la data, la durada, el BPM/compàs/offset i les opcions que
es van fer servir.

## 4. Regles i conseqüències

1. **El cru és immutable.** L'únic lloc que l'escriu és `Feina.run`
   (`app/main.py`), i el desa al document. La resta només el llegeixen.
   La quantització treballa sobre el MODEL i no toca el cru.

2. **El MODEL és la font de veritat de l'edició.** Editar (moure/renombrar/
   partir/…) reescriu els 4 CSV del MODEL — **mai** el cru.

3. **La quantització treballa sobre el MODEL**, no sobre el cru: només mou
   inicis de clips (acords o estructura) a la graella. No re-deriva l'anàlisi.

4. **La quantització no descarta les edicions manuals.** Parteix del model que
   veus, és una sola operació de desfer (`Ctrl+Z`) i el cru no es toca.

5. **Canviar BPM / compàs / offset / mode no toca el cru.** Afecten la
   interpretació de temps (i per tant el MODEL), no l'anàlisi original.
   Els clips guarden **segons** (font de veritat): canviar el BPM **no els mou**.
   Es recalcula la vista musical (etiquetes de compàs i columnes
   `compas_ini`/`compas_fi` de `estructura_ABC.csv`). Per alinear clips a la
   graella es fa servir **Quantitza**.

6. **L'estructura també té el seu cru.** Els `segments` (talls + etiquetes del
   qm-segmenter) viuen al document; les **lletres A/B/C** i els ajustos de mòdul
   de compassos es calculen sobre el MODEL (`estructura_ABC.csv`).

7. **Les còpies de seguretat inclouen el cru.** `Projecte.fes_backup` copia el
   `.acproj` (que ja porta el cru) + els 4 CSV del MODEL. **No** copia l'àudio
   ni els exports.

## 5. Referència al codi

| Què | On |
|---|---|
| Extreu i deixa el cru en memòria (neteja) | `app/main.py` → `Feina.run` |
| Desa el cru al document en acabar | `app/main.py` → `Feina.acabada` |
| Llegeix el cru del document i el passa al visor | `app/main.py` → `_carrega_visor` |
| Desa el MODEL en editar | `app/visor.py` → `_desa_i_regenera`, `_desa_csvs_base` |
| Reescriu l'ABC des de les seccions | `app/visor.py` → `_regenera_abc_des_de_totes_les_seccions` |
| Quantització del model (acords/estructura) | `app/visor.py` → `quantitza` · `app/graella.py` → `quantitza_boundaries` |
| Talls → ABC (en memòria) | `app/pipeline.py` → `fer_abc` |
| Format del document (`analisi`) | `app/projecte.py` → `FORMAT = 2` |

## 6. Proteccions del document (el cru és una *cache*)

El cru viu dins el `.acproj`, però es tracta com el que és: **una cache**. Tres
blindatges (2026-10-19):

1. **Lectura tolerant.** Si `dades["analisi"]` no és vàlida (tipus dolent,
   entrades trencades o massa gran), **es descarta i el projecte s'obre
   igualment** (`projecte.saneja_analisi`). El MODEL és als CSV.
2. **Límit de mida** (`MAX_ANALISI_BYTES` = 512 KB). Si el cru el supera (cançons
   molt llargues), no es desa al document; s'avisa al log i es pot
   tornar a analitzar. El `.acproj` no s'ha de convertir en una base de dades.
3. **`.acproj.bak`**. Abans de cada desat es guarda una còpia de l'anterior
   (`<nom>.acproj.bak`, com el `.rpp-bak` de REAPER).

## 7. Preguntes curtes

- **Puc tornar a l'anàlisi original?** Sí: el cru és dins el `.acproj`. El mode
  fàcil o una re-neteja hi tornen a partir sense re-analitzar.
- **Per què no s'edita el cru directament?** Perquè és l'**evidència**: si
  l'edició el toqués, ja no podries dir «què va detectar l'anàlisi» ni re-provar
  un estil diferent des de zero.
- **La quantització em toca l'estructura?** Només si tries un abast que la
  incloga (`tot`, `selecció` amb seccions, o `només estructura`). El cru de
  talls no es mou.
- **Per què el `.acproj` no conté els acords editats?** Perquè el model viu en
  text (CSV) editable i llegible; el document només hi afegeix el **cru**, el
  tempo del transport, les opcions i la vista.
- **Què passa si obro un projecte vell amb `analisi/`?** S'ignora: no hi ha
  migració. L'app encara s'està construint i els projectes són de prova.

---

> Vegeu també: [`PROJECTES.md`](PROJECTES.md) (carpeta del projecte) ·
> [`REGLES_DE_LA_APP.md`](REGLES_DE_LA_APP.md) (regla d'or #4: cobertura total) ·
> [`GRAELLA_PPQ_TEMPS.md`](GRAELLA_PPQ_TEMPS.md) (temps i graella) ·
> [`AUTODETECCIO_OPCIONS.md`](AUTODETECCIO_OPCIONS.md) (motors i opcions).
