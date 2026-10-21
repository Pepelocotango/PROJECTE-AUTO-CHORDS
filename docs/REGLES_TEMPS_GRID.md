# Regles de TEMPS, COMPÀS i GRAELLA

> **Contracte viu.** Aquest document fixa les regles del que hem acordat sobre
> el temps, el compàs, la graella i els clips de tempo. Si el codi no les
> compleix, **és un bug del codi**. Els canvis de regla necessiten el vistiplau
> explícit de l'operador i queden al `CHANGELOG`.
>
> Complementa les regles d'or de `docs/REGLES_DE_LA_APP.md` (ordre,
> contigüitat, durades derivades, cobertura, paritat, exportació…), que
> continuen manant.

## 1. Els segons són la font de veritat de l'àudio

- Els acords i les seccions es guarden en **segons**.
- Canviar el BPM **no mou** els acords ni les seccions: continuen sonant al
  mateix instant de la WAV.
- El que sí que es recalcula és la **posició musical**: etiquetes de compàs de
  la interfície i columnes `compas_ini`/`compas_fi` de `estructura_ABC.csv`.
- Per alinear acords i seccions a la graella s'usa **Quantitza** de manera
  explícita. No es mouen sols.

## 2. Els clips de tempo/compàs manen sobre la graella

- El conjunt de trams de tempo/compàs és el que defineix el BPM i la mida de
  compàs a cada moment.
- La graella (regle, línies, snap i coordenades) es calcula a partir d'eixos
  trams.
- La graella dona a cada acord i a cada secció la seua coordenada
  `compàs.temps.subdivisió`.

## 3. Cobertura, ordre i contigüitat

- Els trams de tempo/compàs cobreixen **tota la WAV**, de 0 a la durada, de
  manera contigua i ordenada.
- La suma de tots els trams = durada de la WAV.
- No hi ha forats, solapaments ni durades nul·les o negatives.

## 4. Compassos enters als trams interiors

- Cada tram de tempo/compàs **interior** ha de contindre un **nombre enter de
  compassos** (1, 2, 3…), no només “un compàs com a mínim”.
- Les **fronteres entre trams interiors** cauen sempre en una **línia de
  compàs**.
- Un tram d'1,5 compassos no és vàlid encara que dure més d'un compàs.

## 5. Excepcions: el primer inici i l'últim final

- El **primer tram** pot començar a 0 (o a l'inici de la WAV) a mig compàs.
- L'**últim tram** pot acabar a la fi de la WAV a mig compàs.
- La resta de fronteres —inclosa la del primer amb el segon i la de
  l'últim amb l'anterior— són línies de compàs.
- Si la WAV sencera és més curta que un compàs, el tram únic és l'excepció.

## 6. Tempo i compàs no són el mateix

- Un canvi de **tempo** amb la mateixa signatura **no reinicia** el compàs: la
  numeració continua i només canvia la durada dels compassos.
- Un canvi de **compàs** (signatura) sí que obri un compàs nou.
- Amb la regla dels compassos enters, els canvis de compàs interiors també
  cauen en una línia de compàs.

## 7. Canviar el BPM o el compàs d'un tram (re-tempo local)

> **Jerarquia:** el punter/tall mana sobre **Δt**, el **nombre de compassos N**
> es conserva i el **BPM en deriva** (`BPM = N · bq · 60 / Δt`). Detall:
> `docs/FLUX DE TEMPO VARIABLE.md` §2.

**Contracte.** Quan es re-temporitza un tram —moure una frontera, arrossegar un
bloc, `+1`/`−1`/`×2`/`÷2`, o detectar el BPM dins d'un tram delimitat per
marcadors— l'ajust és **local**:

1. El tram **conserva el seu nombre enter de compassos**. Si l'operador en vol
   canviar el nombre, ho fa explícitament (`+1` / `−1` / `×2` / `÷2`), no com a
   efecte secundari d'un canvi de BPM.
2. En canviar el BPM, la **durada del tram** s'ajusta a
   `Δt = N · bq · 60 / BPM`; la **frontera amb el veí** es mou fins on cau la
   nova línia de compàs, que per construcció és exacta.
3. El **veí afectat conserva els seus compassos** i **recalcula el seu BPM**
   per encabir-s'hi. L'ajust és **local**: només els dos trams que toquen
   eixa frontera.
4. Les fronteres dels trams **següents NO es desplacen** en el temps: **no hi
   ha ripple**. Els marcadors humans tampoc no es mouen si no toquen la
   frontera afectada.
5. L'**últim tram** continua acotat per la fi de la WAV (§5): pot canviar el
   nombre de compassos o el BPM per a quadrar-hi. Si l'últim tram és el **veí**
   de qui canvia (no el tram editat), conserva el seu **BPM** i la seua **fi** i
   absorbeix el desplaçament en el nombre de compassos (pot ser fraccionari:
   excepció §5).
6. Si el resultat deixaria un tram **interior** per davall d'un compàs, si el
   veí es quedaria sense espai (`FRONTERA_MIN_S`) o si algun BPM derivat eixira
   de la banda editable (`BPM_EDIT_MIN/MAX`), **es rebutja el canvi** i
   s'avisa; mai no s'aplica un valor absurd.

**Implementació.** `tempo_map.canvia_bpm_local` (diàleg del tram, camps de la
barra i TAP), `mou_frontera_retempo` (drag de la frontera),
`canvia_compassos_tram` (`+1`/`−1`/`×2`/`÷2`) i `retempo_tram_detectat`
(«Detecta» per tram) complixen este apartat. **No hi ha cap camí d'usuari amb
*ripple*.** `snap_frontera_compas`/`_ripple_des_de` només queden per a
`repara_fronteres` (mapes heretats) i l'anàlisi guiat, que creen el mapa des de
zero.

## 8. Moure o crear fronteres a mà

- La frontera **la col·loca el músic** damunt del pic de l'ona, d'un marcador o
  on decidisca. El snap a la graella és **opcional** (es pot apagar) i, si
  s'usa, és el **snap normal del timeline**, no la graella del tempo vell.
- **La graella s'ajusta a la frontera**, no al revés: es conserven els
  compassos dels dos trams i es recalcula el BPM de cada un
  (`BPM = N · bq · 60 / Δt`) perquè el compàs acabe exactament en el tall.
- Per construcció, la frontera **sempre cau en una línia de compàs**: no cal
  imantar-la-hi ni pot quedar-hi un compàs fraccionari.
- Es **rebutja** i s'avisa si un tram interior quedaria per davall d'un compàs
  (`FRONTERA_MIN_S` a cada veí) o si algun BPM eixiria de la banda
  `BPM_EDIT_MIN/MAX`.
- El gest és **local**: cap altre tram no es mou i els marcadors humans lligats
  a la frontera **viatgen amb ella**. El **clip d'estructura** que el `+` va
  crear en eixe punt també la seguix (vincle per coincidència de temps, ±5 ms;
  si després s'edita la secció a mà i deixa de coincidir, deixa de seguir-la).

## 9. Detecció de BPM dins d'un tram

- Si hi ha un **tram de tempo/compàs seleccionat**, la detecció analitza
  **només l'àudio d'eixe tram** i n'estima el BPM de referència.
- El **downbeat del tram és el seu inici** (el primer atac); no cal detectar-lo
  a part.
- En un tram delimitat per marcadors, **Δt és fix**: el BPM detectat només
  serveix per a escollir quants compassos hi caben —
  `N = round(Δt · BPM_ref / (bq · 60))`, mínim 1 — i s'aplica el **BPM derivat
  exacte** (`N · bq · 60 / Δt`) que clava les barres entre els dos punts.
- **La fi del tram no es mou**, i els trams següents tampoc: si el BPM derivat
  cau fora de `BPM_EDIT_MIN/MAX` o el tram no admet cap compàs sencer, s'avisa
  en comptes d'aplicar-lo.
- S'aplica **directament**, com una sola operació de desfer, amb un missatge
  clar del BPM detectat.
- Si no hi ha cap tram de tempo seleccionat, la detecció global existent es
  manté com a via separada.
- Per a **tempo variable**, *Analitza ▸ Detecta el tempo per trams…* fa el
  mapa sencer: un BPM cada N compassos, amb cada frontera exactament en una
  línia de compàs (el BPM es deriva de la durada del bloc, §4) i el resultat
  validat amb les mateixes regles d'ací. Detall: `TEMPO_PER_TRAMS.md`.

## 10. Temps lliure

- De moment **no es fan trams de temps lliure al mig** de la cançó.
- Tots els trams són de BPM/compàs.
- Les úniques parts “lliures” permeses són el començament del primer tram i el
  final de l'últim, perquè la WAV pot no començar o acabar en un compàs sencer.

## 11. Exportació i paritat

- L'exportació continua tenint les tres parts: acords, estructura i mapa de
  tempo/compàs.
- Les columnes de compàs de l'ABC surten del mapa de tempo/compàs.
- Els trams de tempo/compàs continuen participant de la paritat d'edició i de
  selecció, amb les diferències legítimes ja documentades (alçada mitjana,
  contingut numèric amb diàleg, etc.).

## 12. Resum d'una frase

**Els segons manen per a l'àudio; els trams de tempo/compàs manen per a la
graella; els trams interiors tenen compassos enters; el punter fixa Δt, els
compassos es conserven i el BPM en deriva (ajust local, sense arrossegar els
trams següents); i el primer inici i l'últim final són les úniques excepcions.**

## 13. Com s'aplica

- En **carregar** un projecte vell, el mapa es mostra tal com és: no es
  rebutja. Així no es perd la feina ni es mouen coses sense avisar.
- En carregar també es **fusionen els trams adjacents amb el mateix BPM i
  compàs**: no representen cap canvi musical i solen ser duplicats de
  l'anàlisi o de projectes vells. Una partició manual de dos trams iguals es
  respecta mentre s'edita; no es desfà sola.
- Les **edicions de la GUI** que re-temporitzen (moure/crear/partir una
  frontera, `+1`/`−1`/`×2`/`÷2`, detectar el BPM d'un tram, canviar el BPM o el
  compàs pel diàleg del tram, pels camps de la barra o pel TAP) passen pel
  **re-tempo local** (`tempo_map.mou_frontera_retempo`,
  `canvia_bpm_local`, `retempo_tram_detectat`, `canvia_compassos_tram`):
  conserven els compassos, recalculen el BPM i **no mouen els trams següents**.
  Si el resultat no compleix el contracte, **no es toca res** i s'avisa.
- Ja **no hi ha cap camí d'usuari que arrossegue** fronteres:
  `canvia_bpm_compassos` (opció A amb *ripple*) s'ha retirat.
  `snap_frontera_compas`/`_ripple_des_de` només queden per a
  `repara_fronteres` (mapes heretats) i l'anàlisi guiat, que creen o
  reorganitzen el mapa des de zero.
- El backend permissiu serveix per a càrregues i eines internes; el camí
  d'usuari és el que fa complir la regla.
- Els tests del contracte viuen a `tests/test_tempo_map.py`
  (`TestCompassosEnters`), `tests/test_tempo_trams.py` (re-tempo, límits i
  detecció per trams) i `tests/test_pipeline.py` (detecció local).

## 14. Sincronització de la vista

- Quan el model es reconstrueix (quantitzar, desfer, etc.), la selecció del
  timeline es notifica buida i l'editor integrat s'ha de buidar o refrescar.
  No pot quedar mostrant el **temps vell** d'un clip que s'ha mogut.
- Després de quantitzar es recupera, si encara existeix, el clip que s'estava
  editant, perquè l'editor mostre el temps **nou**.
