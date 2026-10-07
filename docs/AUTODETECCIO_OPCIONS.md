# AUTODETECCIÓ: què tenim i què podem oferir

> Exploració dels motors d'autodetecció (BPM, acords, estructura) de
> **2026-10-07**. Mesures reals amb `/home/peplx/Escriptori/WAVS_PROVA/`.

---

## 0. Resum: què fem servir ara

| Detecció | Motor actual | On |
|----------|--------------|----|
| **BPM** | `app/tempo.py` (numpy: envolupant d'onsets + autocorrelació + puntuació «comb» + **prior de plateau 85–150**) · motors alternatius: `qm-tempotracker`, `aubio`, **consens** | `🎯 Detecta` |
| **Acords** | Vamp **`nnls-chroma:chordino:simplechord`** (paràmetres per defecte) | `Analitza` |
| **Estructura** | Vamp **`qm-segmenter`** (per defecte; troba repeticions) o `segmentino` | `Analitza` (+ `Inclou estructura`) |
| **Compàs 1** | `qm-onsetdetector` + `qm-barbeattracker` (downbeats) | `🧭` |

**Motors instal·lats disponibles** (Vamp, `.so` locals, sense AVX):

- **nnls-chroma** (Chordino) → `simplechord`, `chordnotes`, `harmonicchange`,
  `loglikelihood`, `nnls-chroma` (chroma/basschroma/bothchroma…), **`tuning`**
- **segmentino** → `segmentation`
- **vamp-aubio** (compilat per nosaltres) → `aubiotempo:tempo`/`beats`,
  `aubioonset:onsets`, `aubionotes:notes`, `aubiopitch:frequency`,
  `aubiosilence:*`, `aubiomfcc`…

---

## 1. BPM (`🎯 Detecta`)

### Mesures reals
| Fitxer | `tempo.py` (actual) | aubio `tempo` (plugin) | aubio `beats`+mediana (vell) |
|--------|--------------------|------------------------|------------------------------|
| 101 BPM | **101,0** ✅ | 124,6 ❌ | s'enganxa a la subdivisió ❌ |
| 118 BPM | **117,8** ✅ | 166,0 ❌ | ❌ |

👉 **Conclusió**: el nostre `tempo.py` és clarament millor que aubio (que dobla/
triplica el tempo en temes amb silenci inicial o directes). **Mantenir-lo.**

### Opcions que podríem exposar
1. **Confiança / alternatives**: `tempo.py` ja calcula una puntuació «comb»;
   mostrar **«BPM 101,0 (confiança alta)»** i oferir **×2 / ÷2** (101 ↔ 202)
   per si l'usuari vol el doble/meitat.
2. **Rang preferit**: exposar el rang (p. ex. 60–200) per evitar que un tema
   lent es detecti com a ràpid.
3. **Afinació** (nnls-chroma **`tuning`**): mesura real = **440,3 Hz (A440)**.
   Si el tema està desafinat, els acords fallen → es podria **avisar** i
   passar `tuningmode=1` al Chordino (que corregeix l'afinació abans d'analitzar).
4. **Aubio `onsets`**: detectar els atacs → ajuda a **posar l'offset** (compàs 1)
   o a afinar el tap tempo.

---

## 2. Acords (`Analitza` → Chordino)

### Paràmetres del Chordino (per defecte actuals)
| Paràmetre | Valor actual | Què fa |
|-----------|--------------|--------|
| `useNNLS` | 1 | espectre cromàtic NNLS (millor que FFT simple) |
| `useHMM` | (0/1) | suavitzat per HMM (acords més estables) |
| `rollon` | 0 | **tall de baixos**: 0 = el que hi ha; pujar-lo treu el baix (útil si el baix confon) |
| `s` (smoothing) | 0,7 | suavitzat temporal (0 = cap) |
| `whitening` | 1 | equalització espectral prèvia |
| `tuningmode` | 0 | 0 = afinació fixa; 1 = **detecta-la** (per temes desafinats) |
| `boostn` | 0,1 | emfasitza el to principal |
| `usehartesyntax` | 0 (`simplechord`) | notació Harte (Am7/…) vs simple (Am7) |

### Opcions que podríem exposar
1. **Confiança per acord** (`loglikelihood`): mesura real → min **−6,83** ·
   mediana **−3,84** · max **−2,29**. Es podria **marcar en vermell** els acords
   sota un llindar perquè l'usuari els revisi → gran millora de qualitat.
2. **Notació** (`usehartesyntax`): passar a **Harte** (maj7, sus4, inversions
   `C/E`) si es vol més precisió; ara fem servir `simplechord`.
3. **Vocabulari**: `rollon` (treure baix) + `useHMM` (estabilitzar) són els dos
   ajustos que més canvien el resultat — podrien ser **caselles a la UI**
   («Suavitza acords», «Ignora el baix»).
4. **Notes de l'acord** (`chordnotes`): mesura real → dona els **números MIDI**
   de cada corda (p. ex. 52=E3, 71=B4, 74=D5…). Es podria mostrar **quines
   notes** formen l'acord detectat.

---

## 3. Estructura (`Analitza` → Segmentino)

### Què dona ara
`segmentation` → trossos amb etiqueta (`N1`, `B`, `N3`…); mesura real al tema
101: **8 trossos** (durades 21,4 · 7,2 · 25,9 · 20,2 …). Les etiquetes surten
com «N1/N3» (novelty) i «B»; després l'app les **reanomena** a A/B/C… amb
`lletra_lliure()`.

### Opcions que podríem exposar
1. **Durada mínima de tros** (paràmetre del Segmentino): evita trossos curts
   d'un compàs que embruten l'estructura.
2. **Nombre de trossos objectiu**: forçar 4/6/8 seccions (més control).
3. **Estructura per REPETICIÓ d'acords** (alternativa musical): mirar la
   seqüència d'acords i detectar els trossos que **es repeteixen**
   (autosimilitud). Sovint dona A/B/C més musicals que la novetat acústica.
4. **Fusionar trossos idèntics** consecutius (p. ex. «B» «B» → una sola secció).

---

## 4. Idees de UI (per decidir)

| Prioritat | Idea | Esforç |
|-----------|------|--------|
| ⭐ alta | **Confiança dels acords** (loglikelihood) → ressaltar els dubtosos | mitjà |
| ⭐ alta | **Afinació** (`tuning`) → avisar si no està a A440 | baix |
| ⭐ mitjana | **BPM amb confiança + ×2/÷2** | baix |
| mitjana | Caselles «Suavitza acords» (`useHMM`) i «Ignora el baix» (`rollon`) | mitjà |
| mitjana | **Durada mínima / nombre de trossos** (Segmentino) | mitjà |
| baixa | **Notes de l'acord** (`chordnotes`) a l'Editor | mitjà |
| baixa | Estructura per **repetició d'acords** | alt |

---

## 4bis. Com es passen els paràmetres (implementat, fases 1+2)

- **Llegir-los**: `app/vamp_params.py` → llegeix el descriptor **`.n3`** del
  plugin (id, títol, rang, pas, defecte, value_names).
- **Passar-los**: `app/pipeline.escriu_ttl(clau, params, dest, log)` →
  **reconstrueix** un transform `.ttl` amb un `vamp:parameter_binding` per a
  cada paràmetre (valor demanat o defecte) i `extract_chords(..., params=)` el
  fa servir amb **`sonic-annotator -t <ttl>`**.
- ⚠️ **Trampa verificada**: `sonic-annotator -s <id>` **NO llista tots els
  paràmetres** (p. ex. no hi surt `useHMM`); per això **no** es pot pedaçar el
  TTL per defecte → cal **reconstruir-lo** amb el descriptor `.n3`.

## 4ter. Post-processat (implementat, fase 5)

Els motors donen el resultat «cru»; `app/postproc.py` el neteja (funcions
pures). Controls a la pestanya **Acords** del diàleg:

| Opció | Què fa | Exemple |
|-------|--------|---------|
| **Treure el baix** | elimina el baix tallat | `A/E` → `A` |
| **Reduir a l'acord bàsic** | treu extensions | `Cmaj7` → `C`, `Em6` → `Em`, `Edim7` → `Edim` |
| **Fusionar iguals seguits** | uneix acords idèntics consecutius | `C` `C` → `C` |
| **Durada mínima** | elimina acords massa curts (soroll) | Am de 0,2 s → fora |
| **Encaixar a la graella** | snap al beat/compàs (subdivisions triables) | 1,03 s → 1,00 s |

**Estructura** (pestanya pròpia): `pipeline.filtra_seccions` (durada mínima +
fusionar iguals) via `fer_abc(durada_min=, fusiona_iguals=)`.

## 5. Com es prova (reproduïble)

```bash
cd "/home/peplx/0PROJECTES_GitHub/PROJECTE AUTO CHORDS/"
export VAMP_PATH="$PWD/nnls-chroma-linux64-local:$PWD/segmentino-linux64-local:$PWD/vamp-aubio-linux64-local"
./sonic-annotator -d "vamp:nnls-chroma:chordino:loglikelihood" -w csv \
    --csv-one-file /tmp/ll.csv --csv-force --csv-omit-filename "<tema.wav>"
./sonic-annotator -d "vamp:nnls-chroma:tuning:tuning" -w csv \
    --csv-one-file /tmp/tun.csv --csv-force --csv-omit-filename "<tema.wav>"
./sonic-annotator -d "vamp:vamp-aubio:aubiotempo:tempo" -w csv \
    --csv-one-file /tmp/t.csv --csv-force --csv-omit-filename "<tema.wav>"
# paràmetres per defecte d'un transform:
./sonic-annotator -s "vamp:nnls-chroma:chordino:simplechord"
# llista de tots els transforms disponibles:
./sonic-annotator --list
```
