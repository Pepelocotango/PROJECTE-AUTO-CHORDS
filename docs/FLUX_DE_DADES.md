# Flux de dades: la capa CRUA i el MODEL editable

> **En una frase:** cada tema té **dues capes**. La **CRUA** (`analisi/`) és
> l'evidència de l'anàlisi i **no es toca mai**; el **MODEL** (`acords.csv` +
> `estructura_ABC.csv`) és el que veus i edites, i sempre es pot **regenerar des
> de la crua**. Per això pots editar a mà o tornar a aplicar el **mode fàcil**
> tantes vegades com vulguis sense malmetre l'anàlisi original.

## 1. Les dues capes (i les seves germanes)

| Capa | Fitxers | Quan s'escriuen | Qui els toca |
|---|---|---|---|
| **CRUA** | `analisi/chords_raw.csv`<br>`analisi/segments_raw.csv`<br>`analisi/meta.json` | **una vegada**, a cada «Analitza» | **només `Feina.run`**. Mai l'edició ni el mode fàcil |
| **MODEL** | `acords.csv`<br>`estructura_ABC.csv`<br>`tempo.csv` · `compas.csv` | a **cada edició** | el visor, el mode fàcil, l'anàlisi inicial |
| **EXPORTS** | `wavs_acords/` · `wavs_estructura/` · `partitura/` · `guia_acords.html` | només a «Exporta» | `pipeline.exporta_total` |
| **CÒPIES** | `backup/<data-hora>/` (**hi inclou `analisi/`**) | autosave cada 60 s, si hi ha canvis | `Projecte.fes_backup` |

## 2. Estructura de la carpeta del projecte

```
La meva cançó/                     ← carpeta autocontinguda (portable)
├── La meva cançó.acproj          ← el document (JSON: tempo, opcions, vista)
├── audio/ tema.wav               ← CÒPIA de l'àudio (mai depèn de fora)
│
├── acords.csv                    ← MODEL: els acords
├── estructura_ABC.csv            ← MODEL: l'estructura A/B/C
├── segments.csv                  ← MODEL: els talls (base de l'ABC)
│
├── analisi/                      ← CAPA CRUA (evidència · IMMUTABLE)
│   ├── chords_raw.csv            ←   acords de Chordino ABANS de netejar
│   ├── segments_raw.csv          ←   talls del segmentador (qm-segmenter)
│   └── meta.json                 ←   paràmetres de l'anàlisi
│
├── wavs_acords/ · wavs_estructura/ · partitura/   ← EXPORTS («Exporta»)
└── backup/ <data-hora>/          ← còpies versionades (fins a 10)
```

## 3. El flux

```
              «Analitza»
                  │
                  ▼
   analisi/chords_raw.csv ──┐   (1) evidència crua: s'hi copia ABANS de netejar
   analisi/segments_raw.csv ┤
   analisi/meta.json ───────┘
                  │
      ┌───────────┼──────────────────────────────┐
      │           │                              │
      │  (2) neteja dels acords         (3) mode fàcil INICIAL
      │      (opcions del diàleg)          (llegeix el CRU)
      │           │                              │
      └───────────┴──────────────► acords.csv ◄───┘
                                    │
                                    │  (4) engega el visor
                                    ▼
                          ┌────────────────────┐
                          │   edició en viu    │  ← l'usuari edita al visor
                          │ (acords + seccions)│
                          └─────────┬──────────┘
                                    │  desa NOMÉS els CSV (mai la crua)
                                    ▼
                    acords.csv · estructura_ABC.csv
                                    ▲
                                    │  (5) mode fàcil (re-deriva del CRU)
                                    └── regularitza_des_de_cru
```

## 4. Regles i conseqüències

1. **La capa crua és immutable.** L'únic lloc del codi que escriu a `analisi/`
   és `Feina.run` (`app/main.py`). La resta **només la llegeixen**
   (`visor.regularitza_des_de_cru`). Ho protegeix un test:
   `tests/test_graella.py::test_la_capa_crua_no_es_toca`.

2. **El MODEL és la font de veritat de l'edició.** Editar (moure/renombrar/
   partir/… un acord o una secció) reescriu `acords.csv` /
   `estructura_ABC.csv` — **mai** `analisi/`.

3. **El mode fàcil re-deriva del CRU.** `regularitza_des_de_cru` llegeix
   `analisi/chords_raw.csv` i genera acords nous a la graella (un acord per
   compàs / mig / temps…). Com que sempre parteix de l'original, **no
   s'acumula error** i pots provar estils diversos en cadena.

4. ⚠️ **El mode fàcil descarta les edicions manuals d'acords.** Com que
   re-genera des de la crua, els canvis que hagis fet a mà **es tornen a
   escriure**. És **una sola operació de desfer** → `Ctrl+Z` les recupera. Regla
   pràctica: **primer** el mode fàcil, **després** els retocs a mà.

5. **Canviar BPM / compàs / offset / mode no toca la crua.** Afecten la
   interpretació de temps (i per tant el MODEL), no l'anàlisi original.

6. **L'estructura també té el seu cru.** `analisi/segments_raw.csv` són els
   talls del segmentador; les **lletres A/B/C** i els ajustos de mòdul de
   compassos es calculen sobre el MODEL (`estructura_ABC.csv`). El mode fàcil
   amb «mòdul de compassos» **encaixa els talls de secció** del MODEL, no la
   crua.

7. **Les còpies de seguretat inclouen la crua.** `Projecte.fes_backup` copia
   el `.acproj` + els CSV/`:txt` importants + la carpeta `analisi/` sencera →
   l'evidència de l'anàlisi queda protegida a cada `backup/`.

## 5. Referència al codi

| Què | On |
|---|---|
| Escriu `analisi/` (i la neteja + mode fàcil inicial) | `app/main.py` → `Feina.run` |
| Noms i carpeta de la crua | `app/pipeline.py` → `carpeta_analisi`, `NOM_CRU_ACORDS`, `NOM_CRU_SEGMENTS`, `NOM_ANALISI_META` |
| Desa el MODEL en editar | `app/visor.py` → `_desa_i_regenera`, `_desa_csvs_base` |
| Reescriu l'ABC des de les seccions | `app/visor.py` → `_regenera_abc_des_de_totes_les_seccions` |
| Mode fàcil (llegeix el CRU) | `app/visor.py` → `regularitza_des_de_cru` |
| Mode fàcil dins l'anàlisi | `app/main.py` → `pipeline.regularitza_acords_csv(raw, csv_ac, …)` |
| Còpies (inclouen `analisi/`) | `app/projecte.py` → `Projecte.fes_backup` |
| Test que fixa la immutabilitat del cru | `tests/test_graella.py::test_la_capa_crua_no_es_toca` |

## 6. Preguntes curtes

- **Puc tornar a l'anàlisi original?** Sí: la crua hi és sempre
  (`analisi/`). Esborra o re-regularitza el MODEL i torna a partir d'ella.
- **Per què no s'edita la crua directament?** Perquè és l'**evidència**: si
  l'edició la toqués, ja no podries dir «què va detectar l'anàlisi» ni
  re-provar un estil diferent des de zero.
- **El mode fàcil em toca l'estructura?** Només el MODEL
  (`estructura_ABC.csv`), i només si tries un **mòdul de compassos**. La crua
  (`segments_raw.csv`) no es mou.
- **Per què el `.acproj` no conté els acords?** Perquè el model viu en text
  (CSV) editable, i el `.acproj` només guarda tempo/opcions/vista — així els CSV
  són la font única i llegible.

---

> Vegeu també: [`PROJECTES.md`](PROJECTES.md) (carpeta del projecte) ·
> [`REGLES_DE_LA_APP.md`](REGLES_DE_LA_APP.md) (regla d'or #4: cobertura total) ·
> [`GRAELLA_PPQ_TEMPS.md`](GRAELLA_PPQ_TEMPS.md) (temps i graella) ·
> [`AUTODETECCIO_OPCIONS.md`](AUTODETECCIO_OPCIONS.md) (motors i opcions).
