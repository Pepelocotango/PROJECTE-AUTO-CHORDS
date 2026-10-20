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

## 7. Canviar el BPM o el compàs d'un tram (opció A)

Quan es canvia el BPM o el compàs d'un tram seleccionat:

1. El tram **conserva el seu nombre enter de compassos**.
2. La seua fi es mou en segons fins a la nova línia de compàs.
3. Les fronteres dels trams **següents s'arrosseguen** la mateixa quantitat,
   perquè continuen tenint compassos enters.
4. L'**últim tram absorbeix** la diferència perquè ha d'acabar a la fi de la
   WAV (pot canviar el seu nombre de compassos: és l'excepció).
5. Si el resultat deixa un tram **interior** per davall d'un compàs, o el mapa
   no pot cobrir la WAV, **es rebutja el canvi** i s'avisa.
6. Si el tram afectat és l'últim, com que la fi de la WAV no es mou, és
   l'excepció: pot canviar el nombre de compassos.

## 8. Moure o crear fronteres a mà

- En crear o moure una frontera de tempo/compàs, s'imanta a la **línia de
  compàs més pròxima**.
- Si la frontera resultant deixaria un tram interior per davall d'un compàs,
  **es rebutja** i s'avisa.
- No es poden crear trams interiors amb compassos fraccionaris.

## 9. Detecció de BPM dins d'un tram

- Si hi ha un **tram de tempo/compàs seleccionat**, la detecció analitza
  **només l'àudio d'eixe tram** i n'estima el BPM.
- El **downbeat del tram és el seu inici** (el primer atac); no cal detectar-lo
  a part.
- El BPM detectat s'aplica amb l'opció A (compassos enters, arrossegament de
  fronteres, últim absorbeix).
- S'aplica **directament**, com una sola operació de desfer, amb un missatge
  clar del BPM detectat.
- Si no hi ha cap tram de tempo seleccionat, la detecció global existent es
  manté com a via separada.

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
graella; els trams interiors tenen compassos enters; canviar el BPM conserva
els compassos i arrossega les fronteres; i el primer inici i l'últim final són
les úniques excepcions.**

## 13. Com s'aplica

- En **carregar** un projecte vell, el mapa es mostra tal com és: no es
  rebutja. Així no es perd la feina ni es mouen coses sense avisar.
- En carregar també es **fusionen els trams adjacents amb el mateix BPM i
  compàs**: no representen cap canvi musical i solen ser duplicats de
  l'anàlisi o de projectes vells. Una partició manual de dos trams iguals es
  respecta mentre s'edita; no es desfà sola.
- Les **edicions de la GUI** (moure/crear/partir una frontera, canviar
  BPM/compàs, detectar el BPM d'un tram, el diàleg del mapa) validen o
  imanten a la línia de compàs. Si el resultat no compleix el contracte,
  **no es toca res** i s'avisa.
- El backend permissiu serveix per a càrregues i eines internes; el camí
  d'usuari és el que fa complir la regla.
- Els tests del contracte viuen a `tests/test_tempo_map.py`
  (`TestCompassosEnters`) i a `tests/test_pipeline.py` (detecció local).

## 14. Sincronització de la vista

- Quan el model es reconstrueix (quantitzar, desfer, etc.), la selecció del
  timeline es notifica buida i l'editor integrat s'ha de buidar o refrescar.
  No pot quedar mostrant el **temps vell** d'un clip que s'ha mogut.
- Després de quantitzar es recupera, si encara existeix, el clip que s'estava
  editant, perquè l'editor mostre el temps **nou**.
