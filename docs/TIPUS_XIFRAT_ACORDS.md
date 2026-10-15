# Tipus de xifrat d'acords — variants, graus i `<kind>`

> **Font de veritat del xifrat**: `app/xifrat.py` (`normalitza_qualitat`,
> `TIPUS`, `graus`, `kind_i_graus`). La taula «Nivells 1–3» ve de la
> referència de l'operador *«acords i tensions»*; la secció **Extres** són
> tipus/formes que l'app també entén i que la referència no llistava.
>
> Aquesta llista la **fixa un test** (`tests/test_xifrat.py`,
> `tests/test_doc_xifrat.py`): si s'hi afegeix un tipus al codi i no aquí, la
> suite peta.

## Com funciona (en 20 segons)

1. **Al model** el xifrat es desa sempre en **forma canònica** (menor `-`,
   major sense marca, `Maj7`, `-7`, `-7b5`…). Si escrius una variant
   (`Am7`, `Ami`, `Amin7`, `A-7`), l'app l'**entén i la deixa bé**.
2. **A l'export de WAVs** el nom del fitxer surt del model, amb `/` → `_`
   (`A7/G` → `A7_G.wav`). La `-` **no** es toca (és «menor»).
3. **A la partitura (MusicXML)** cada acord s'escriu amb `<root>` + `<kind>`
   + els **`<degree>`** (afegir/alterar/treure graus) + `<bass>` → **MuseScore
   ho mostra i ho reprodueix**.

Columnes: **Tipus** (forma canònica) · **Variants acceptades** · **Graus**
(tal com els descriu la referència; *entre parèntesis* = opcionals) ·
**`<kind>` MusicXML**.

---

## Nivell 1 — Bàsic

| Tipus | Variants acceptades | Graus | `<kind>` |
|---|---|---|---|
| `C` | `C` `CM` `CMa` `CMaj` `Cma` `Cmaj` `CΔ` | (1) 3 (5) | `major` |
| `C-` | `Cm` `Cmi` `Cmin` `C-` | (1) b3 (5) | `minor` |
| `Cdim` | `Cdim` `C°` `Co` | (1) b3 b5 | `diminished` |
| `C7` | `C7` | (1) 3 (5) b7 | `dominant` |
| `C-7` | `Cm7` `Cmi7` `Cmin7` `C-7` | (1) b3 (5) b7 | `minor-seventh` |
| `C-7b5` | `Cm7b5` `Cmi7b5` `Cø` `Cø7` `C-7b5` | (1) b3 b5 b7 | `half-diminished` |
| `CMaj7` | `Cmaj7` `CM7` `CMa7` `CΔ7` `Cma7` | (1) 3 (5) 7 | `major-seventh` |

## Nivell 2 — Intermedi

| Tipus | Variants acceptades | Graus | `<kind>` |
|---|---|---|---|
| `CMajb5` | `Cmajb5` | (1) 3 b5 | `major` + `(5,-1,alter)` |
| `C5` | `C5` | 1 5 | `power` |
| `Csus2` | `Csus2` | (1) 2 (5) | `suspended-second` |
| `Csus4` | `Csus4` `Csus` | (1) 4 (5) | `suspended-fourth` |
| `Caug` | `Caug` `C+` | (1) 3 #5 | `augmented` |
| `C6` | `C6` | (1) 3 (5) 6 | `major-sixth` |
| `Cadd9` | `Cadd9` | (1) 3 (5) 9 | `major` + `(9,0,add)` |
| `C-6` | `Cm6` `Cmi6` `Cmin6` `C-6` | (1) b3 (5) 6 | `minor-sixth` |
| `C-add9` | `Cmadd9` `Cm(add9)` `C-add9` | (1) b3 (5) 9 | `minor` + `(9,0,add)` |
| `Cdim7` | `Cdim7` `C°7` `Co7` | (1) b3 b5 bb7 | `diminished-seventh` |
| `C7sus4` | `C7sus4` `C7sus` | (1) 4 (5) b7 | `suspended-fourth` + `(7,-1,add)` |
| `C7b5` | `C7b5` | (1) 3 b5 b7 | `dominant` + `(5,-1,alter)` |
| `C7#5` | `C7#5` `Caug7` `C+7` | (1) 3 #5 b7 | `augmented-seventh` |
| `C-Maj7` | `Cm(maj7)` `CmMaj7` `CmM7` `CmΔ7` `C-Maj7` | (1) b3 (5) 7 | `major-minor` |
| `C6add9` | `C6add9` `C69` `C6/9` | (1) 3 (5) 6 9 | `major-sixth` + `(9,0,add)` |
| `C-6add9` | `Cm6add9` `Cm69` | (1) b3 (5) 6 9 | `minor-sixth` + `(9,0,add)` |
| `C7b9` | `C7b9` | (1) 3 (5) b7 b9 | `dominant` + `(9,-1,alter)` |
| `C7#9` | `C7#9` | (1) 3 (5) b7 #9 | `dominant` + `(9,+1,alter)` |
| `C-7b9` | `Cm7b9` | (1) b3 (5) b7 b9 | `minor-seventh` + `(9,-1,alter)` |
| `C9` | `C9` | (1) 3 (5) b7 9 | `dominant-ninth` |
| `C9b5` | `C9b5` | (1) 3 b5 (b7) 9 | `dominant-ninth` + `(5,-1,alter)` |
| `C9#5` | `C9#5` | (1) 3 #5 (b7) 9 | `dominant-ninth` + `(5,+1,alter)` |
| `C-9` | `Cm9` `Cmi9` `Cmin9` `C-9` | (1) b3 (5) b7 9 | `minor-ninth` |
| `CMaj9` | `Cmaj9` `CM9` `CMa9` `CΔ9` | (1) 3 (5) 7 9 | `major-ninth` |
| `C11` | `C11` | (1) (3) (5) b7 9 11 | `dominant-11th` |
| `C-11` | `Cm11` `Cmin11` `C-11` | (1) b3 (5) b7 9 11 | `minor-11th` |
| `CMaj11` | `Cmaj11` `CM11` | (1) (3) (5) 7 9 11 | `major-11th` |
| `C13` | `C13` | (1) 3 (5) b7 (9) 13 | `dominant-13th` |
| `C-13` | `Cm13` `Cmin13` `C-13` | (1) b3 (5) b7 (9) 13 | `minor-13th` |
| `CMaj13` | `Cmaj13` `CM13` | (1) (3) (5) 7 (9) 13 | `major-13th` |

## Nivell 3 — Avançat

| Tipus | Variants acceptades | Graus | `<kind>` |
|---|---|---|---|
| `CMaj7b5` | `Cmaj7b5` | (1) 3 b5 7 | `major-seventh` + `(5,-1,alter)` |
| `CMaj7#5` | `Cmaj7#5` | (1) 3 #5 7 | `major-seventh` + `(5,+1,alter)` |
| `C7b5b9` | `C7b5b9` | (1) 3 b5 b7 b9 | `dominant` + `(5,-1)` `(9,-1)` |
| `C7#5b9` | `C7#5b9` | (1) 3 #5 b7 b9 | `augmented-seventh` + `(9,-1,alter)` |
| `C7#5#9` | `C7#5#9` | (1) 3 #5 b7 #9 | `augmented-seventh` + `(9,+1,alter)` |
| `C7add11` | `C7add11` | (1) (3) (5) b7 11 | `dominant` + `(11,0,add)` |
| `C7#11` | `C7#11` | (1) (3) (5) b7 #11 | `dominant` + `(11,+1,alter)` |
| `C-7b5b9` | `Cm7b5b9` | (1) b3 b5 b7 b9 | `half-diminished` + `(9,-1,alter)` |
| `C-7add11` | `Cm7add11` | (1) b3 (5) b7 11 | `minor-seventh` + `(11,0,add)` |
| `CMaj7#11` | `Cmaj7#11` | (1) (3) (5) 7 #11 | `major-seventh` + `(11,+1,alter)` |
| `C-9b5` | `Cm9b5` | (1) b3 b5 b7 9 | `minor-ninth` + `(5,-1,alter)` |
| `C-Maj9` | `Cm(maj9)` `CmMaj9` `C-Maj9` | (1) b3 (5) 7 9 | `major-minor` + `(9,0,add)` |
| `CMaj9#5` | `Cmaj9#5` | (1) (3) #5 7 9 | `major-ninth` + `(5,+1,alter)` |
| `C9#11` | `C9#11` | (1) 3 (5) (b7) 9 #11 | `dominant-ninth` + `(11,+1,alter)` |
| `CMaj9#11` | `Cmaj9#11` | (1) (3) (5) 7 9 #11 | `major-ninth` + `(11,+1,alter)` |
| `C11b9` | `C11b9` | (1) (3) (5) (b7) b9 11 | `dominant-11th` + `(9,-1,alter)` |
| `C13b5b9` | `C13b5b9` | (1) 3 b5 (b7) b9 13 | `dominant-13th` + `(5,-1)` `(9,-1)` |
| `C13b9` | `C13b9` | (1) 3 (5) (b7) b9 13 | `dominant-13th` + `(9,-1,alter)` |
| `C13#9` | `C13#9` | (1) 3 (5) (b7) #9 13 | `dominant-13th` + `(9,+1,alter)` |
| `C13#11` | `C13#11` | (1) (3) (5) (b7) 9 #11 13 | `dominant-13th` + `(11,+1,alter)` |

> Les columnes `<kind> + (…)` volen dir: `kind` base **més** un `<degree>`
> amb *(valor, alteració, tipus)*. Exemple: `CMajb5` →
> `<kind>major</kind>` + `<degree>5 / -1 / alter</degree>`.

---

## Extres (no són a la referència «acords i tensions»)

| Tipus | Variants acceptades | Què és | `<kind>` / tractament |
|---|---|---|---|
| `C` sense 3a | `C5` | **power chord** (arrel + 5a) | `power` |
| `C6/9` | `C69` `C6/9` | 6a + 9a | `major-sixth` + `(9,0,add)` |
| `Cadd11` | `Cadd11` | 11a afegida | `major` + `(11,0,add)` |
| `Cadd6` | `Cadd6` | 6a afegida | `major` + `(6,0,add)` |
| `Cno3` | `Cmajno3` `Cno3` | **treure** la 3a | `major` + `(3,0,subtract)` |
| `Cno5` | `C7no5` `Cmaj7no5` `C-7no5` | **treure** la 5a | `kind` base + `(5,0,subtract)` |
| `Cno7` | `Cno7` | treure la 7a | `major` + `(7,0,subtract)` |
| … | qualsevol `noN` | N ∈ 1–13 | `(N,0,subtract)` |
| … | qualsevol `addN` | N ∈ 1–13 | `(N,0,add)` |
| … | qualsevol `#N` / `bN` | N ∈ 1–13 | `(N,±1,alter)` |
| `C7alt` | `C7alt` | dominant alterat | `dominant` + `text="7alt"` (símbol sencer) |
| `C##`/`Cbb` | `C##` `Cx` (♯♯) · `Cbb` (♭♭) | **dobles alteracions** de l'arrel | `<root-alter>±2</root-alter>` |
| `C/E` | `C/E` `A7/G` `A-7/G` `C6/9/G` | **acord amb baix** | `<bass>` (i la `/` → `_` al nom de fitxer) |
| `N` | `N` `NC` `N.C.` | **sense acord** | *(no s'escriu cap `<harmony>`)* |

### Notes útils
- **Parèntesis i comes**: `C7(#11)` ≡ `C7#11`; `Cm(add9)` ≡ `Cmadd9`;
  `C69(#11,#13)` ≡ `C6add9#11#13`. Al model s'escriuen sense parèntesis.
- **`6/9` no és un acord amb baix**: la barra només compta si el que segueix
  és una **nota** (`C6/9/G` → 6/9 amb baix G).
- **Alteracions de l'arrel** també al baix: `C/Db`, `C##/Dbb`.
- **`Δ` sol** = tríada major; per a la major 7a cal `Δ7` (`CΔ7` → `CMaj7`).
- **`Ma`/`mi`**: `CMa7` → `CMaj7`; `Cmi7` → `C-7`. Compte: `madd9` és
  **menor + add9** (`C-add9`), no `Maj`+`dd9`.
- **Sense prefix reconegut** però amb alteracions (`no5`, `#11`, `add6`), la
  base és la **tríada major**.
- **Qualitat impossible de reconèixer** (p. ex. `Cxyz`): es conserva el text
  al `<kind text="…">` i la base és `other` — **mai es duplica** el nom (era el
  bug de l'«AA-maj7»).

## No suportat (i per què)
| Cas | Estat |
|---|---|
| **Policords** (`F\|C`) | ❌ Encara no. MusicXML ho admet (harmony-chords apilats dins d'un `<harmony>`); MuseScore els mostra però només toca el primer. |
| **`drop2`** | ❌ MuseScore tampoc no el suporta. |
| **`natural`** (becaire) | ⚠️ Rar i MuseScore tampoc l'exporta bé a MusicXML. |
| **`t` per a `Δ`** | ❌ No (és una drecera de teclat de MuseScore, no un símbol de xifrat). |

## Referències
- Codi: `app/xifrat.py` (notació) · `app/partitura.py` (`harmony_xml`) ·
  `app/pipeline.py` (`saneja_nom_acord`, `safe_filename`).
- Tests: `tests/test_xifrat.py` · `tests/test_partitura.py` ·
  `tests/test_doc_xifrat.py` (aquest fitxer).
- Vegeu també: [`FLUX_DE_DADES.md`](FLUX_DE_DADES.md) ·
  [`PARTITURA_EXPORT.md`](PARTITURA_EXPORT.md).
