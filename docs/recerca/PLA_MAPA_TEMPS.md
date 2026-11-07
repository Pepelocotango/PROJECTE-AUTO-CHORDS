# Pla — simplificació del mapa de temps

> **Data:** 2026-11-06 · **Estat:** completat (F0–F5) · **Abast:** trams de
> BPM/compàs i la seua relació amb la graella.
>
> **Nota (2026-11-07):** el contracte ja s'ha actualitzat a
> `docs/REGLES_DE_LA_APP.md` §13 (model permissiu, recalcul guiat, mínim de
> 86 ms i clips sempre manen). La referència del recalcul és la **base manual
> de la barra 2** (`BPM ref` + `compàs ref`), no la dels clips veïns; els beats
> detectats poden corregir compàs/X-X i `N`. Este pla queda com a registre de
> les decisions.

## Decisions

1. **La referència la posa el músic.** En obrir una cançó, escolta, marca un
   BPM aproximat amb el tap tempo i tria un compàs `x/x` a la **barra 2**
   (`Ref. recalc`). És una referència manual i global per al recalcul, no la
   dels clips veïns; els beats poden corregir-la.
2. **Els clips de temps són el model.** Es comporten com els clips d'acords i
   estructura: afegir, partir, fusionar, moure, redimensionar i eliminar.
   Cada edició actualitza la graella.
3. **Les fronteres són lliures.** L'usuari pot moure una frontera on vulga.
   El snap ajuda, però no obliga.
4. **El model és permissiu.** Un clip pot no coincidir amb compassos sencers;
   l'app no ha de bloquejar l'edició per això. El mínim és que el clip siga
   prou llarg: no pot ser més curt que un compàs de `1/8` a 350 BPM
   (≈ 86 ms).
5. **Els compassos sencers són l'objectiu del recalcul, no una barrera.**
   Si no es poden aconseguir, l'app avisa i aplica la solució menys agressiva.
6. **El recalcul decideix què tocar.** Amb la referència base de BPM i
   compàs, calcula quants compassos «espera» el tram i tria la combinació que
   menys s'allunya de la referència: conservar BPM i compàs, canviar el compàs,
   ajustar el BPM o canviar el nombre de compassos. Amb beats detectats, la
   selecció prefereix signatures naturals amb el mateix denominador i el mínim
   de compassos (14 beats → `7/4` N=2; 8 → `4/4` N=2).
7. **Si l'usuari marca els compassos, aquests manen.** Amb marcadors als
   inicis de compàs, el nombre de compassos es conserva i l'app ajusta BPM o
   compàs per encaixar-hi.
8. **El rubato continua existint com a tipus de clip.** Mateixes operacions,
   però BPM i compàs derivats i de només lectura. Els segons no ballen.
9. **El pre-roll automàtic es conserva**, limitat a l'inici de la cançó.
10. **El transport no és una segona veritat.** Els clips de temps manen; els
    camps de BPM/compàs de la barra són un editor. La **referència base** de
    recalcul és independent del transport i dels clips.
11. **Si no hi ha cap solució raonable**, l'app no fa canvis silenciosos:
    avisa i tria el mal menor (ajustar la frontera o deixar el tram com està).

## Algorisme de recalcul

Entrada: `D` (durada del tram), `BPM_ref`, `num_ref/den_ref`, `N_ref`
(opcional; si no arriba, es calcula com `round(D / durada_compàs_ref)`).

Per a cada candidat `(N, num, den)`:

```
BPM = 60 · N · num · (4/den) / D
```

Es descarten els BPM fora de 30–350. Es puntua:

```
cost = w_bpm     · |log2(BPM / BPM_ref)|
     + w_compas  · distancia_compas((num,den), (num_ref,den_ref))
     + w_n       · |N − N_ref| / max(1, N_ref)
     + w_natural · penalitzacio_compas(num,den)
```

Guanya el cost més baix. `distancia_compas` penalitza menys els canvis de
numerador que els de denominador. `penalitzacio_compas` afavoreix les
signatures habituals (`4/4`, `3/4`, `2/4`, `6/8`, `12/8`). Amb beats
detectats, abans del cost es filtra per `N × bq = beats` i es prefereix una
signatura natural amb el mateix denominador i el mínim `N`; així els beats
poden corregir el compàs/X-X i `N` de la base.

Si `N_ref` ve fixat pels marcadors, el cost de canviar-lo és infinit: només
es mouen BPM i compàs.

## Fases

- **F0 — Motor pur de recalcul.** `app/tempo_recalc.py` amb
  `recalcula_tram()`, sense tocar la GUI. Tests amb els casos de referència.
- **F1 — Tram 0 com un clip més.** `_refresca_tempo_map` deixa de sobreescriure
  el tram 0 amb el transport; el transport només mostra/edita el clip.
- **F2 — Model permissiu.** Validació de GUI sense «beat sencer» ni fronteres
  obligatòries a la graella; mínim de durada i BPM/compàs vàlids. Els
  detectors i les accions explícites mantenen els criteris musicals.
- **F3 — Integració del recalcul.** En moure una frontera o canviar BPM/compàs,
  el recalcul busca compassos sencers amb la referència del clip. Si no pot,
  avisa i aplica el mal menor.
- **F4 — Marcadors com a `N` fix.** Si hi ha marcadors d'inici de compàs,
  el nombre de compassos mana i el recalcul només ajusta BPM/compàs.
- **F5 — Contracte i documentació.** Actualitzar `REGLES_DE_LA_APP.md` §13,
  `CHANGELOG.md` i els docstrings. Ho fa l'agent de documentació.

## Progrés

- **F0 — FET (2026-11-06).** `app/tempo_recalc.py` amb `recalculca_tram()` i
  `tests/test_tempo_recalc.py` (10 casos). Motor pur, sense GUI.
- **F1 — FET (2026-11-06).** `_refresca_tempo_map` ja no sobreescriu el tram 0
  amb el transport; només crea un tram si el mapa és buit i sincronitza la
  barra des del clip 0. Tests de desat/revert adaptats.
- **F2 — FET (2026-11-06).** Model permissiu: mínim de 86 ms, fronteres
  lliures i validació de GUI sense «beat sencer». La validació estricta es
  conserva per als detectors i les accions explícites.
- **F3 — FET (2026-11-07).** En moure una frontera, el recalcul busca
  compassos sencers amb el BPM/compàs que tenia cada costat com a referència.
  Si hi ha beats detectats dins del clip, el seu nombre restringix `N` i el
  compàs (7 beats → `7/4`, no 2×`4/4`). Sense beats detectats, s'inferixen a
  partir de la referència (`D × BPM_ref / 60`) quan cauen a prop d'un enter
  (±0,2).
- **F4 — FET (2026-11-07).** L'acció `+` recalcula els dos costats del tall
  perquè queden en compassos sencers; «BPM dels marcadors» usa el nombre de
  compassos de cada interval com a `N` fix i només tria BPM i compàs. Si hi ha
  beats detectats, el seu nombre mana sobre el `N` estimat.
- **F5 — FET (2026-11-07).** Contracte i documentació: `REGLES_DE_LA_APP.md`
  §13 actualitzat al model nou, entrada al `CHANGELOG`, `ROADMAP` i taula de
  mòduls. Ho ha fet l'agent de documentació.

## Criteris d'acceptació

- Suite verda i `pyflakes` net després de cada fase.
- Cap canvi silenciós: si el recalcul ha de canviar BPM, compàs o `N`, es veu
  al log i, si és gran, s'avisa.
- El mínim de clip és `1/8` a 350 BPM (≈ 86 ms).
- Rubato i pre-roll continuen funcionant.
- Els exports i la graella continuen derivant del mapa.
