# Notació del xifrat — forma canònica

> **En una frase:** l'app desa **sempre** els acords en una **forma canònica**
> (`Am` → `A-`, `Cmaj7` → `CMaj7`, `Bø` → `B-7b5`). Si escrius una variant,
> l'app l'**entén** i la deixa bé, i així el **model** (CSV), els **noms de
> fitxer** de l'export i la **partitura** (MusicXML → MuseScore) parlen tots la
> mateixa llengua.

Decisió de l'operador («opció 3», 2026-10-15). **Font única al codi**:
`app/xifrat.py` (sense dependències del projecte → el fan servir `pipeline` i
`partitura` sense cicles).

## 1. Per què una forma canònica

Abans, cada camí tenia la seva pròpia manera d'escriure l'acord:
- el **model** guardava el que l'usuari havia escrit (`Am`, `Amin`, `ami`…);
- l'**export de WAVs** en reescrivia els noms amb un `style()` (`Am` → `A-`);
- la **partitura** tornava a parsejar el nom.

Resultat: **divergència de noms** entre el CSV i els fitxers exportats
(`Am` al CSV ↔ `A-.wav` al disc). Amb **una sola** font de notació, tot
coincideix i MuseScore ho entén igual.

## 2. La forma canònica

| Concepte | Forma canònica | Variants que l'app entén |
|---|---|---|
| **Menor** | `-` | `m`, `mi`, `min`, `-` |
| **Major** | *(sense marca)* | `M`, `Ma`, `maj`, `Δ`, `^` |
| **Major 7** | `Maj7` | `M7`, `maj7`, `Δ7` |
| **Menor 7** | `-7` | `m7`, `min7` |
| **Menor-maj7** | `-Maj7` | `mMaj7`, `minmaj7` |
| **Disminuït** | `dim` | `°`, `o` |
| **Disminuït 7** | `dim7` | `o7`, `°7` |
| **Semidisminuït** | `-7b5` | `ø`, `ø7`, `m7b5` |
| **Augmentat** | `aug` | `+` |
| **Suspès** | `sus4` / `sus2` | `sus` (= sus4) |
| **Sexta** | `6` / `-6` | `m6` |
| **Extensions** | `9` / `11` / `13` (i `Maj…`/`-…`) | `maj9`, `m9`, `add9`… |
| **Graus afegits/trets** | `add9`, `no5` | `9` / `#11` (com a `<degree>` a MusicXML) |
| **Dobles alteracions** | `##` / `bb` | `x` (= doble sostingut) |
| **6/9** | `6add9` | `6/9` |
| **Baix (inversió)** | `/` | `A7/G` (però **`C6/9` NO és baix**) |
| **Sense acord** | `N` | `NC`, `N.C.`, buit |

La qualitat **no reconeguda** es deixa tal qual (l'app **no inventa** res: les
anotacions rares no es trenquen).

## 3. Exemples

```
Am · Amin · ami   →  A-          Am7 · Amin7  →  A-7
Amaj7 · AM7 · CΔ7 →  AMaj7/CMaj7 Bø · Bm7b5   →  B-7b5
Cmaj · CM · CΔ    →  C           F#o7         →  F#dim7
Am/G              →  A-/G        C6/9 · C69    →  C6add9  (no és baix)
C##7 · Cx7        →  C##7        C7alt         →  C7alt  (l'«alt» es conserva)
N · NC · N.C.     →  N           «solo» / «H7» →  intactes
```

## 4. On s'aplica

| Camí | Com hi arriba |
|---|---|
| **Model / CSV** | `pipeline.saneja_nom_acord()` → `xifrat.normalitza_xifrat()` (ho fan servir editor, renombrar, renom **en bloc**, alta i troba-i-reemplaça) |
| **Noms de fitxer** de l'export | `pipeline.safe_filename()` / `partitura.safe_filename()`: `/` i separadors de path → **`_`** (mai `-`, que vol dir «menor») → `A7/G` → `A7_G.wav` |
| **Export de WAVs** | `pipeline.genera_locators()`: **sense** `style()` → els noms viatgen **verbatim** |
| **Partitura (MusicXML)** | `partitura.harmony_xml()`: usa la forma canònica (taula `xifrat.TIPUS`) i escriu el `<kind>` base **+ els `<degree>`** de les alteracions/extensions (`#5`, `b9`, `add9`, `no5`…) → **MuseScore ho mostra i ho reprodueix**. Si una qualitat no es reconeix, cau a `<kind text="…">other</kind>` amb **només el sufix** (el root ja s'escriu a part). |

## 5. Conseqüències pràctiques

1. **El que deses és el que veus**: si escrius `Am`, es desa com `A-`.
2. **Els projectes vells es conserven**: l'app **no reescriu** dades antigues pel
   seu compte (`Am`… es queden com són fins que els **editis**).
3. **Reinicia l'app** després d'actualitzar: la notació canònica s'activa en
   arrencar.

---

> Vegeu també: [`FLUX_DE_DADES.md`](FLUX_DE_DADES.md) (model vs capa crua) ·
> [`PARTITURA_EXPORT.md`](PARTITURA_EXPORT.md) (xifrat → MusicXML) ·
> [`REGLES_DE_LA_APP.md`](REGLES_DE_LA_APP.md).
