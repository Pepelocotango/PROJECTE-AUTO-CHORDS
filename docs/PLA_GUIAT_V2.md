# Pla — Anàlisi guiat v2 (estació d'audició) i autodetecció

> **Creat:** 2026-10-21 · **Origen:** `docs/analisis guiat v2.markdown`
> (especificació de l'operador) contrastada amb el codi el 21-10.
> **Abast:** `app/tempo_map.py`, `app/dialegs.py`, `app/main.py`,
> `app/visor.py`, tests i docs. **Cap canvi a les regles d'or.**

## 0. Punt de partida (què ja hi havia)

L'especificació encerta tots els noms del codi, i **dues terceres parts ja
estaven fetes** (guiat v1, 20-10 + motor de tempo per trams, 21-10):

| Ja hi és | On |
|---|---|
| `DialegGuiaDownbeat`, Pas 1 (offset + tall + mode BPM + snap negra) | `main._analisi_guitat`, `_guia_pas1_fet` |
| Fil desacoblat `FilGuiaBpm` (només senyals) | `main.FilGuiaBpm` |
| Un sol desfer per tram, avanç automàtic | `_guia_fenestra_aplica` |
| Final: `fusiona_trams_iguals` + `executa()` | `_guia_final` |
| `×2`/`÷2`/`×4/3`/`×3/4`, 3 pastilles de candidats amb % | `DialegGuiaBpm` |
| `_fixa_loop`, `_alinea_cursor_loop`, `FADE_LOOP_S=0.004`, `mescla_metronom`, `_atura_si_sona` | `visor.py`, `metronom.py` |

## 1. Decisions preses (21-10)

1. **Audició vs. mesura (separació d'intervals).** L'especificació diu
   «es neteja qualsevol loop previ» i, alhora, «es fixa el loop al tram».
   Això xocava amb la funció del 20-10 («el loop A–B acota **on** es mesura el
   BPM»). **Solució:** el guiat fa una **instantània** del loop de l'usuari en
   arrancar (`_guia["loop"]`) i **mesura sempre amb eixa instantània**; el
   loop del visor passa a ser **l'interval d'audició** del tram i es pot
   canviar sense afectar la mesura. En cancel·lar/acabar es **restaura** el
   loop de l'usuari.
2. **`n_compassos` explícit.** `trams_finestra_guia` rep `n_compassos` (per
   defecte 4) en compte de deduir-lo de `beats=16`. Arregla un error real:
   **en 3/4 eixien 5 compassos** (`round(16/3)`) en compte de 4, que és el que
   diu la doc. `beats` es manté per compatibilitat.
3. **Metrònom forçat.** Amb un mapa de tempo variable, `mescla_metronom`
   ignora el `bpm` i segueix el mapa: per escoltar un tram **encara no
   aplicat** cal un mode forçat (`metro_forcat = (bpm, bpb, offset=t_k)`) que
   sona **alineat al inici del tram** (accent al compàs 1). És el que permet
   el metrònom **en viu** en canviar el BPM sense reiniciar el so
   (`_alimenta` ja llig l'estat a cada tros).
4. **Tecles.** `T` = TAP (dins del diàleg, amb `QShortcut` local) i `Espai` =
   play/pausa sense tancar el diàleg. `Enter` segueix acceptant.
5. **Mètrica al diàleg:** desplegable amb els presets (4/4, 3/4, 2/4, 6/8,
   12/8) **més la mètrica vigent del tram** si no hi és. Es descarta
   l'entrada lliure `num/den` (s'afegeix quan calgui): el cas real és canviar
   de preset i el contracte de compassos ja es valida al backend.

## 2. Fases

### P1 · Backend pur (baix risc)
- [x] `tempo_map.trams_finestra_guia(..., n_compassos=None)`.
- [x] `_guia_fenestra`: finestra = `4 · num` temps (`8 s` al primer tram).
- [x] Tests: 3/4 → 4 compassos; 6/8 → 4 compassos; `n_compassos=1,2,8`;
      `beats=` segueix funcionant.

### P2 · Diàleg d'audició (`DialegGuiaBpm`)
- [x] Fila de mètrica (combo) i `−1 / N compassos / +1`.
- [x] TAP amb `T` (2–6 cops, reinici si > 2,5 s entre cops).
- [x] Botó `▶ / ⏸` i `Espai` → senyal `vol_reproduir`.
- [x] Senyal `bpm_canviat(float)` en editar/ràtio/pastilla/TAP.
- [x] `compassos()` i `metrica()` per a l'orquestrador.
- [x] Tests de GUI (sense fil): estat inicial, ±1, combo, TAP sintètic,
      ràtios, senyals.

### P3 · Orquestració i àudio
- [x] `_guia_fenestra_aplica`: passar `n_compassos` i `num/den` del diàleg.
- [x] `_guia_bpm_ditectat`: **audició automàtica** — loop `[t_k, t_seg]`,
      metrònom forçat i play si està parat.
- [x] `bpm_canviat` → actualitza `metro_forcat` (metrònom en viu).
- [x] `visor.metro_forcat` a `_alimenta` (`mapa=None`, `offset=t_k`).
- [x] Restaurar loop i metrònom a `_guia_final`/`_guia_cancel`.
- [x] Tests: motor fals de reproducció (com `_cursor_loop___FakeMotor`),
      loop fixat al tram, `metro_forcat` net en tancar.

### P4 · Tancament i documentació
- [x] Avís final «mapa consolidat (N trams) → obro l'anàlisi d'acords»
      (ja hi és; polir el text) i `executa()`.
- [x] `docs/ANALISI_GUIAT.md` §2.2/2.3 reescrits amb el flux real;
      `CHANGELOG`; `ESQUEMA_UI` si canvia el diàleg.
- [x] Suite sencera verda + pyflakes + 2 passades seguides.

> **Estat 2026-10-21: P1–P4 FETES.** 1161 tests OK (1 skip), pyflakes net.
> Detall a `docs/ANALISI_GUIAT.md` §2 (finestra de 4 compassos) i §4.3
> (estació d'audició) + `CHANGELOG.md` (21-10, 2a). Manca la **prova
> auditiva amb l'operador** (el metrònom forçat i el canvi de BPM en viu
> demanen sentir-ho) i, si agrada, el mode automàtic (§6.1 de
> `ANALISI_GUIAT.md`).

## 3. Riscos i com es cobreixen

| Risc | Cobertura |
|---|---|
| El loop d'audició contamina la mesura | instantània `_guia["loop"]` + test |
| Metrònom desalineat del tram | accent a `t_k` (`offset=t_k`) + prova auditiva amb l'operador |
| Canvi de BPM en viu → micro-tall | no es reinicia el motor: `_alimenta` llig el forçat a cada tros (~0,7 s) |
| Contracte de compassos amb mètrica nova | `trams_finestra_guia` → `valida_i_normalitza_compassos`; el diàleg no aplica res directament |
| Fil que toca la GUI | es manté la regla: el fil només emet senyals |
