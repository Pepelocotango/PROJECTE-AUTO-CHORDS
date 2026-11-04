# Flux de dades (model vs cru)

Font canònica: `docs/FLUX_DE_DADES.md`. Resum operatiu.

## Què és què

- **MODEL viu** (memòria): `Visor.acords`, `Visor.seccions`, `Visor.tempo_trams`. Font de veritat.
- **Al disc**: 3 CSV = model: `acords.csv`, `estructura_ABC.csv`, `mapa_tempo.csv` (mapa_tempo.csv).
- **`.acproj`**: document (tempo transport, opcions, vista) + **cru de l'anàlisi** com a caché (`dades["analisi"]`: chords, segments, opcions, data/durada). Lectura tolerant, límit 512 KB, mai imprescindible.

## Quan s'escriu què

- **A cada edició**: els 3 CSV (atòmic: tmp+fsync+replace).
- **Només amb "Desa"**: el `.acproj`.
- **Només amb "Exporta"**: exports (wavs, partitura, guia HTML, mapa_tempo/).

## Projecte = carpeta autocontinguda

```
La meva cançó/
├── La meva cançó.acproj
├── La meva cançó.acproj.bak   (còpia anterior a cada desat)
├── audio/ tema.wav            (còpia de l'àudio, mai depèn de fora)
├── acords.csv
├── estructura_ABC.csv
├── mapa_tempo.csv
└── (exports: wavs_acords/, wavs_estructura/, partitura/, guia_acords.html, mapa_tempo/)
```

## Proteccions

- `fi` d'`acords.csv` es re-deriva en carregar (veritat = cadena d'inicis).
- `.acproj` format 3 sense retrocompatibilitat; vells rebutjats amb error clar.
- No es destrueix mai un fitxer de l'usuari; projecte no suportat es rebutja sense tocar-lo.

## Implicacions per a l'agent

- Si toques model, recorda que els 3 CSV s'han d'actualitzar.
- Si toques `.acproj`, recorda que és només document+caché, no model.
- Mai assumeixis que el `.acproj` conté l'estat actual del model; el model viu és a memòria/CSV.
