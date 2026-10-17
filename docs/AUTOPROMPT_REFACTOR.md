# AUTOPROMPT — continuar el refactor «inici+fi» (AUTO CHORDS)

> **Com usar-lo**: en una conversa nova, enganxa això tal qual —o bé digues
> «llegeix `docs/AUTOPROMPT_REFACTOR.md` i continua el refactor»— i l'agent
> tindrà tot el context necessari.

## On som

Projecte: **`/home/peplx/0PROJECTES_GitHub/PROJECTE AUTO CHORDS`** (app PyQt5,
host Ubuntu; `AGENTS.md` del projecte està **gitignored**).

**Refactor EN MARXA, tot local (mai push).** Punt de partida taguejat:
`refactor-inici-fi`. Contracte, pla per fases i handoff: **`docs/REFACTOR_INICI_FI.md`**
(llegeix-lo primer). Taula d'operacions viva: **`docs/EDICIO_OPERACIONS.md`**.

## Objectiu

Unificar el model de dades: **tots dos tipus** (acords i estructura) passen a ser
**clips amb `ini`+`fi`** (`Clip(ini, fi, payload)`), amb el **`fi` re-derivat
sempre** de la cadena de fronteres. Tots dos CSV escriuran **`inici,fi`**.
**Sense retrocompatibilitat** (decisió explícita de l'operador).

## Fet (commits locals)

| Commit | Què |
|---|---|
| `6338bcd` | **S1** — `Clip` + adaptadors (`clips_d_acords`, `acords_de_clips`, `clips_de_seccions`, `seccions_de_clips`) + `normalitza_clips(...)` |
| `dcf2d74` | **S2a** — `redimensiona_clips` + `redimensiona_acord` / `redimensiona_seccio` |
| `a2f392d` | **S2b** — `mou_bloc_clips` + `mou_bloc_acords` / `mou_bloc_seccions` (+ **correcció §6.3**) |
| `7010c1d` | **S2c** — `parteix_clips` / `fusiona_clips` + wrappers dels dos tipus |
| `1785067` · `a1ae05e` · `0dbe3e7` | neteja (3 funcions mortes, 2 tests obsolets) i docs al dia |

Tot és a **`app/pipeline.py`**: tipus i normalitzador (~l. 590-730), nuclis
d'operació i wrappers (~l. 895-1120).

**Conseqüència**: les 4 famílies que estaven duplicades —**vores, moure, partir,
fusionar**— ja tenen **un sol nucli**; la paritat #11 hi és estructural.

## Regles del projecte (no negociables)

- **Regla d'or #11**: acords i estructura = **mateixes eines i mateix comportament**.
- **§6.3**: el clip editat **mana**; el material de sota es **TALLA** si només queda
  cobert en part (**i conserva el nom**) i **S'ELIMINA** si queda sobrepassat; el
  bloc **conserva la seva durada**; l'**origen** el tanca el veí i, sense veí, hi va
  el **`forat`** (`N` acords / `-` estructura).
  **Cas de referència** (test golden): cançó `C[0,2) Am[2,4) F[4,6) G[6,8) Em[8,10)`;
  arrossegar el clip **G** 3 s enrere →
  `C[0,2) Am[2,3) G[3,5) F[5,6) Em[6,10)`.
- Tot en **català**; commits **locals, petits i descriptius**; **MAI push**.
- **MAI deixar l'arbre amb la suite vermella**: si una escombrada no queda neta,
  `git checkout -- <fitxers>` i s'explica exactament què falta i per què.
- Un test només s'adapta si es documenta al commit com a **correcció** (amb el
  perquè), mai com a pedaç perquè passi.
- No duplicar mai els nuclis: `normalitza_clips`, `redimensiona_clips`,
  `mou_bloc_clips`, `parteix_clips`, `fusiona_clips`.

## Verificació (sempre abans de commitejar)

```bash
cd "/home/peplx/0PROJECTES_GitHub/PROJECTE AUTO CHORDS"
.venv/bin/python -m pyflakes app/*.py tests/*.py eines/*.py
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests
```

Estat en deixar aquest autoprompt: **942 tests OK** (1 skip), **pyflakes net**,
arbre net.

## Pendent (en ordre)

1. **Graella** — unificar `graella.regularitza_acords` (l. 134) i
   `regularitza_seccions` (l. 201): un sol nucli sobre clips + wrappers.
2. **Visor** — ~10 handlers duplicats per tipus (`_elimina_acord_index`,
   `_elimina_seccio_index`, `_duplica_acord_index`, `_duplica_seccio_index`,
   `_elimina_seleccio`, `_duplica_seleccio`, `_enganxa_seleccio`, `_elimina_acord`,
   `_elimina_seccio`) → nucli únic; i el gest de vores (`ZONE_LEFT`/`ZONE_RIGHT`)
   enganxat a `redimensiona_clips`.
3. **S3 — CSV `inici,fi` als dos**: escriptors **i tots els lectors alhora**
   (`pipeline.desa_acords_csv` ~l. 1489, el lector del visor, l'obertura de
   projecte, el MCP, `acords_a_live.py`); el `fi` es re-deriva. És una
   **escombrada**: fes-la sencera en una tongada i verifica la suite.
4. **S5** — exports i derivats: WAVs, ABC, partitura, MusicXML, guia DAW i les
   eines MCP al nou model.
5. **S6** — neteja final: codi mort, helpers sense ús, `CHANGELOG` i docs.

## Trampes conegudes

- Si hi ha una **app viva**, porta el **codi vell en memòria**: cal reiniciar-la
  per provar canvis.
- Eines MCP noves: es criden pel servidor, no pel llistat de la sessió →
  `.venv/bin/python eines/mcp_auto_chords_server.py --call <ac_tool> --args '{...}'`.
- Els missatges en català dins de comandes `bash` amb accents/backticks: **fes
  servir heredocs**, no `-c "..."` (els backticks es substitueixen i mutilen el text).
