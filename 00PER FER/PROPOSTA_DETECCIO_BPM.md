# Proposta de detecció de BPM i col·laboració amb l'usuari

> **Data:** 2026-11-19
> **Estat:** idea de treball · **no és contracte** · viu a `00PER FER/`
> **Abast:** detectar el BPM d'una cançó de forma reproduïble, explicar les
> hipòtesis i permetre que l'usuari aporte el que l'app no pot saber del cert.
> **Fora d'abast:** canviar les regles de l'app, ampliar l'ús de QM fora dels
> talls QM o introduir dependències noves.

---

## 1. Idea central

L'app no ha de ser un oracle que afirma un BPM exacte. Ha de ser un **sistema
d'hipòtesis de tempo** que:

1. mesura el senyal;
2. genera diverses hipòtesis;
3. explica per què en recomana una;
4. ensenya les alternatives;
5. deixa que l'usuari confirmi, corregeja o digui «no ho sé»;
6. només aplica al model allò que l'usuari accepta.

El BPM no és una propietat física absoluta del so: és una **convenció
perceptiva**. Per això l'objectiu no és «la veritat», sinó una decisió
**útil, explicable i reversible**.

La divisió correcta és:

> **L'app mesura i proposa; l'usuari interpreta i decidix.**

---

## 2. Diagnòstic actual

### 2.1. Evidència sobre el corpus de Foo Fighters

Prova feta el 2026-11-19 sobre l'àudio de `CORPUS/foofighters 2`:

| Mètode | Resultat |
|---|---|
| `tempo.detecta_bpm()` | **144,75 BPM** |
| `tempo.detecta_bpm_candidats()` | **144,60 BPM** |
| `qm-tempotracker` | **120,25 BPM** |
| Consens actual | 144,75 BPM (descarta QM) |
| Detecció per trams | base **144,60**; final **143,27** |
| Prova exploratòria de fase | millor pic **144,725**; 144,70 molt a prop |

La cançó va estable al voltant de **144,7 BPM** i només té un final que
ralentitza. El resultat **144,75 no és una mesura exacta**: és una cel·la de la
graella de cerca.

### 2.2. Causes tècniques

- `detecta_bpm()` acaba usant `_comb_bpm()` amb `pas=0.25`.
  - Els candidats queden en `144,50`, `144,75`, `145,00`.
  - El valor real cau entre dues cel·les.
- `detecta_bpm_candidats()` baixa a `pas=0.1`, però encara dona `144,60`.
- `_punt_comb()` puntua autocorrelació; no alinea directament els onsets amb la
  fase del candidat.
- L'envolupant té un hop de 10 ms; la interpolació pot biaixar el pic.
- QM pot enganxar-se a una subdivisió o a un altre pols; en este cas, 120,2.
- El flux actual pot amagar la detecció:
  - `opcions.analisi.bpm` pot estar desactivat;
  - l'acció «Analitza» separa BPM d'acords/estructura;
  - `BEATS_DEFECTES` té `motor="qm"`;
  - F7 pot executar només beats o QM.

### 2.3. Conclusió del diagnòstic

El motor intern **sí que pot trobar el tempo**. El que falla és:

1. la resolució de la cerca;
2. la manca de refinament per fase;
3. l'ús del final lent com si formara part del cos;
4. el motor per defecte;
5. la presentació d'un sol número sense alternatives ni explicació.

---

## 3. Què vol dir «BPM exacte»

Cal separar tres conceptes:

- **BPM mesurat:** el valor continu que millor alinea els onsets del cos
  estable. Pot ser `144,72`.
- **BPM nominal:** el valor de referència que es mostra i s'aplica, per
  exemple `144,70`. És el que l'usuari espera si la cançó està clavada.
- **BPM de referència:** el valor que aporta l'usuari perquè té una font
  fiable (DAW, partitura, click, editor extern).

L'app ha de poder dir:

```text
BPM mesurat: 144,72
BPM nominal: 144,70
Interval: 144,68–144,76
Confiança: alta
```

I no ha de dir mai:

```text
144,75  ← falsa precisió de la graella
```

### 3.1. Precisió objectiu

- Per a un tema estable: **±0,05 BPM** sobre el cos principal.
- Per a un tema variable: **no inventar un únic BPM**; mostrar mapa o rang.
- Per a una intro/outro variable: excloure-les del càlcul global i explicar-ho.

---

## 4. Principis de disseny

1. **Cap valor únic sense evidència.** Si hi ha empat, es mostra.
2. **Cap aplicació automàtica silent.** L'anàlisi proposa; l'usuari decidix.
3. **Cap falsa precisió.** `144,70` no és el mateix que `144,75`.
4. **El cos mana.** Intro i outro no han de contaminar el BPM principal.
5. **L'usuari no ha de fer de detector.** Només respon coses que l'app no pot
   inferir: intenció, pols percebut, límits del cos, referència externa.
6. **«No ho sé» és una resposta vàlida.** L'app ha de continuar sense forçar.
7. **Tot és reversible.** Desfer, desbloquejar i tornar a mesurar.
8. **Explicar sempre el perquè.** Cada candidat ha de portar una raó curta.
9. **No tocar el contracte de tempo.** L'aplicació al mapa continua sent una
   acció explícita de l'usuari (regla #11).
10. **QM només com a contrast.** No s'amplia l'ús de QM fora dels talls QM.

---

## 5. Què aporta cada part

| L'app pot fer bé | L'usuari pot fer bé |
|---|---|
| Mesurar onsets, fase i periodicitat | Dir quin pols sent com a principal |
| Comparar centenars de beats i detectar deriva | Distingir negra/corxera, meitat/doble, 6/8 vs 3/4 |
| Excloure intro/outro de forma estadística | Decidir si el final és part del tema o un outro |
| Donar confiança, intervals i alternatives | Validar si el click «sona bé» musicalment |
| Detectar tempo variable per blocs | Marcar on comença el cos estable |
| Proposar 144,70 i explicar per què | Corregir a 144,70 si té una referència fiable |
| Ensenyar la deriva del click | Decidir si la deriva és acceptable |

Cap de les dues parts té certesa absoluta. L'app ha de fer visible la seua
incertesa; l'usuari ha de poder dir fins on vol acceptar-la.

---

## 6. Flux d'ús proposat

### 6.1. En obrir la cançó

L'app fa una detecció ràpida en segon pla i mostra una proposta, sense aplicar-la:

```text
Tempo proposat: 144,70 BPM
Confiança: alta · cos estable del 89% de la cançó
[Escoltar] [Veure alternatives] [Per què?]
```

No bloqueja la càrrega. No modifica el projecte. No desa res al CSV.

### 6.2. L'app ensenya les hipòtesis

No un sol número:

```text
144,70  ← recomanat
144,60  alternativa propera
72,35   meitat del pols
120,20  QM, descartat
```

Amb una explicació curta per a cada una:

- «144,70 alinea el 93% dels beats del cos.»
- «144,60 també encaixa, però perd fase al final.»
- «72,35 seria sentir el doble de lent.»
- «120,20 ve de QM i no coincidix amb el pols dominant.»

### 6.3. L'usuari només respon quan cal

No convertir-ho en un interrogatori. Preguntar només si la decisió és ambigua:

- `Aquest és el pols` → confirma.
- `No és aquest` → descarta'l i no el tornes a proposar.
- `Sento el doble / la meitat` → canvia la família rítmica.
- `No ho sé` → no forçar; ampliar la cerca o mostrar mapa variable.
- `Marca el cos` → l'usuari assenyala on el tempo és estable.
- `Aquest final no compta` → exclou-lo del càlcul global.
- `Tinc una referència` → introdueix 144,70 i l'app valida si encaixa.

### 6.4. Validació per escolta

El millor test no és veure números: és **escoltar**.

- Reproduir un loop de 8–16 compassos amb metrònom.
- Canviar entre candidats amb el mateix loop.
- Mostrar un indicador de deriva: «al compàs 32 el click va 8 ms avançat».
- Permetre `Ajusta +0,01` / `-0,01` i tornar a escoltar.

### 6.5. Decisió i aplicació

Quan l'usuari decidix:

- `Aplica 144,70 al cos`
- `Aplica 144,70 a tot el tema`
- `Bloqueja este BPM`
- `No tornar a proposar 144,75`
- `Marca el tram com a estable`

El valor acceptat passa al model. La informació d'anàlisi (confiança,
alternatives, motius) queda com a metadada del projecte, no com a veritat del
CSV.

### 6.6. Quan l'usuari no pot saber del cert

No obligar-lo a triar. Baixar el nivell de certesa:

- **Alta confiança:** proposta principal; alternatives amagades.
- **Confiança mitjana:** ensenyar 2–3 candidats i demanar una escolta.
- **Baixa confiança:** no aplicar res; oferir:
  - mapa per trams;
  - «tempo variable»;
  - introducció manual;
  - anàlisi d'un tram seleccionat.

Botó explícit:

```text
No ho puc assegurar
```

Resposta de l'app:

```text
No aplicaré cap BPM.
Puc ensenyar-te el mapa per trams o analitzar només el cos.
```

---

## 7. Algorisme proposat

### 7.1. Capes

1. **Senyal:** envolupant d'onsets i beats.
2. **Hipòtesis:** candidats de BPM, incloent família harmònica.
3. **Decisió:** cos estable, fase, regressió i confiança.
4. **Explicació:** motius dels candidats i dels descartats.

### 7.2. Trobar el cos estable

No usar tota la cançó de cop.

- Dividir en blocs de 4–8 compassos.
- Calcular BPM local per bloc.
- Calcular mediana i desviació robusta (MAD).
- Seleccionar el **tram contigu més llarg** dins de ±0,2–0,3 BPM de la mediana.
- Excloure intro/outro si no tenen prou onsets o si el BPM local difereix.
- Guardar `inici/fi` del cos i el percentatge de la cançó que representa.

Per al corpus actual, el cos hauria de quedar aproximadament entre el segon 5–10
i el 200–210; el final lent quedaria fora.

### 7.3. Generar candidats

- Candidat inicial amb el mètode actual, però amb pas fi (`0,01` o `0,005`).
- Afegir família harmònica:
  - `B`
  - `B/2`
  - `2B`
  - eventualment `3B/2` si el compàs ho justifica.
- No descartar candidats només per estar a prop; guardar-los per explicar-los.
- Descartar duplicats a menys del 2%, com ara.

### 7.4. Refinar per fase

Per a cada candidat `B`, buscar la fase `φ` que maximitza:

```text
S(B, φ) = Σ E(φ + k·60/B)
```

on `E(t)` és l'energia d'onsets positiva i `k` recorre els beats del cos estable.

- Buscar `B` en una finestra de `±0,5 BPM` al voltant del candidat.
- Pas de `0,005` o `0,01`.
- Fase en passos de `1–2 ms`.
- Ponderar menys les zones amb poca energia.
- Puntuar només el cos estable.

La prova exploratòria va donar un millor pic al voltant de **144,72**; `144,70`
quedava pràcticament igual i `144,75` pitjor.

### 7.5. Regressió dels beats

Alternativa o complement:

1. Detectar beats amb `segueix_beats`.
2. Agafar els beats del cos estable.
3. Ajustar `t_k = a + b·k` amb regressió robusta.
4. Calcular `BPM = 60 / b`.

Si els residus són petits, el BPM és estable i la precisió pot ser molt alta.
Si els residus creixen o hi ha canvis de pendent, el tema és variable.

### 7.6. Decisió

Un candidat és principal si:

- cobertura suficient del cos;
- fase consistent;
- diferència clara respecte del segon;
- residus baixos;
- no està en zona ambigua d'octava.

Si hi ha empat tècnic, no decidir automàticament: mostrar les opcions.

Si el cos és variable, retornar mapa per trams o `variable=True`.

### 7.7. Arrodoniment

- No usar mai una graella de 0,25.
- No arrodonir durant la cerca.
- Arrodonir només al final, a **0,1 BPM**, si la corba és plana.
- Conservar el valor continu i l'interval per a l'explicació.

### 7.8. Limitacions

- Si l'àudio té rubato real, no hi ha un únic BPM exacte.
- Si la cançó té canvis de tempo, cal mapa per trams.
- Si la intro és amb tempo lliure, no s'ha d'incloure al cos.
- Si l'usuari té una referència externa, l'app ha de validar-la, no acceptar-la
  cegament.

---

## 8. Contracte de dades de la proposta

El detector ha de retornar un objecte complet, no només un `float`:

```python
{
    "bpm": 144.7,
    "bpm_mesurat": 144.72,
    "bpm_interval": [144.68, 144.76],
    "confianca": 0.93,
    "metode": "fase+regressio",
    "origen": "app",
    "cos": {
        "inici": 5.2,
        "fi": 206.5,
        "cobertura": 0.89,
    },
    "candidats": [
        {"bpm": 144.7, "pes": 1.00, "motiu": "cos estable"},
        {"bpm": 144.6, "pes": 0.91, "motiu": "candidat proper"},
        {"bpm": 72.35, "pes": 0.62, "motiu": "meitat del pols"},
    ],
    "descartats": [
        {"bpm": 120.2, "origen": "QM", "motiu": "no coincidix amb el cos"},
        {"bpm": 144.75, "origen": "graella antiga", "motiu": "pitjor fase"},
    ],
    "variable": False,
    "trams": [],
    "bloquejat": False,
}
```

Camps:

- `bpm`: valor nominal que es mostra i s'aplica si l'usuari accepta.
- `bpm_mesurat`: valor continu del refinament.
- `bpm_interval`: incertesa.
- `confianca`: 0–1; no és una probabilitat calibrada, és una mesura interna.
- `origen`: `app`, `usuari`, `app+correcció`.
- `cos`: regió usada per a la decisió.
- `candidats`: alternatives ordenades.
- `descartats`: hipòtesis rellevants que no guanyen.
- `variable`: si cal mapa per trams.
- `bloquejat`: si l'usuari ha fixat el valor.

---

## 9. UI proposada

### 9.1. En obrir una cançó

No bloquejar la càrrega. Fer una detecció ràpida en segon pla i mostrar:

```text
Tempo estimat: 144,70 BPM
[Analitza a fons] [Veure alternatives]
```

No aplicar automàticament al projecte. L'anàlisi proposa; l'usuari decidix.

### 9.2. Diàleg «Analitza BPM»

Opcions:

- **Motor**
  - `Automàtic (recomanat)`
  - `Nostre — onsets/fase`
  - `QM — només com a contrast`
- **Abast**
  - `Cos principal (recomanat)`
  - `Tota la cançó`
  - `Tram seleccionat`
- **Resultat**
  - BPM principal gran: `144,70`
  - confiança i interval
  - llista d'alternatives amb motiu
  - botó `Per què?`
  - botons `Aplica`, `Aplica només al cos`, `Detecta per trams`, `Cancel·la`

### 9.3. Targetes de candidat

Cada targeta ha de mostrar:

```text
144,70 BPM   ← recomanat
Cos estable · 93% de fase
[Escoltar] [Aplicar]
```

I per a les alternatives:

```text
144,60 BPM
Proper, però perd fase al final
[Escoltar] [Aplicar]
```

### 9.4. Panell «Per què?»

Text curt, no logs:

- «He analitzat 5,2–206,5 s (89% de la cançó).»
- «He alineat 471 beats; desviació mitjana 4 ms.»
- «144,70 guanya 144,75 per un 8% de fase.»
- «Intro (0–5 s) i final (206–232 s) no compten.»
- «QM 120,20 descartat: no encaixa amb la pulsació.»

### 9.5. Si el mapa ja té diversos trams

No sobreescriure'l sense avisar. Oferir:

- `Aplica al tram seleccionat`
- `Substituïx el mapa per un de detectat`
- `No aplicar; només mostra el resultat`

### 9.6. Format del número

- En UI: **144,70 BPM**.
- Intern: `144.7`.
- No mostrar mai `144,75` si és producte de la graella.
- Si cal, mostrar `144,70 ± 0,05`.

---

## 10. Explicabilitat

Cada candidat ha de portar una explicació generada a partir de dades reals:

- **144,70 — recomanat**
  - «Cos estable del 89% de la cançó.»
  - «471 beats alineats; desviació mitjana 4 ms.»
  - «Intro i final no s'han usat.»
- **144,60 — alternativa propera**
  - «També encaixa, però perd un 8% de fase.»
- **72,35 — meitat**
  - «Correspondria a sentir el doble de lent; no és el pols dominant.»
- **120,20 — QM, descartat**
  - «No coincidix amb el pols del cos; probable enganxament a una subdivisió.»
- **Tempo variable**
  - «El cos canvia més de 0,3 BPM; cal mapa per trams.»

---

## 11. Implementació al codi

### 11.1. `app/tempo.py`

Afegir:

- `refina_bpm_per_fase(env, bpm, ...)`
- `detecta_cos_estable(env/beats, ...)`
- `detecta_bpm_estable(wav, ...) -> dict`
- `_regressio_beats(beats, ...)`

Mantenir `detecta_bpm()` retornant `float` per compatibilitat, però que
internament use el refinament fi. Canviar `candidats_bpm()` perquè no treballe
amb pas 0,25 en la fase final.

### 11.2. `app/pipeline_vamp.py`

- Ampliar `detecta_bpm_detallat()` per retornar el diccionari complet.
- `_bpm_consens()` ha de rebre i exposar els candidats, no només el guanyador.
- Fer que `motor="consens"` siga el camí recomanat.

### 11.3. `app/beats.py`

- `_detecta_nostre()` ha d'usar `detecta_bpm_estable()`.
- QM ha de quedar com a **contrast**, no com a motor principal per defecte.
- `BEATS_DEFECTES["motor"]` hauria de passar de `"qm"` a `"auto"` o `"nostre"`.

### 11.4. `app/opcions.py`

- Canviar el motor per defecte.
- Afegir `bpm.abast = "cos"` i `bpm.refina = True`.
- No cal migració de projectes antics; si un projecte vell no té estos camps,
  s'usen els defaults.

### 11.5. `app/feines.py`

- Fer la detecció ràpida en el fil de treball.
- Retornar l'objecte complet a la UI.
- Permetre cancel·lar si l'usuari tanca o canvia de cançó.

### 11.6. `app/analisi_ui.py`

- En obrir: llançar detecció ràpida opcional.
- En `Analitza BPM`: rebre el resultat complet i mostrar-lo.
- No aplicar automàticament si el mapa té més d'un tram.
- Mantindre QM només per als talls QM, com fins ara.

### 11.7. `app/dialeg_analitza_bpm.py`

- Afegir «Automàtic» i «Cos principal».
- Traure QM com a opció principal.
- Afegir el panell de resultats/alternatives o obrir un diàleg de resultat.

### 11.8. `app/visor_tempo.py`

- Permetre bloquejar el BPM d'un tram.
- Mostrar la deriva del click respecte dels beats.
- Oferir `Ajusta` i `Torna a mesurar el cos`.

### 11.9. Persistència

- El valor acceptat entra a `mapa_tempo.csv`.
- La informació de confiança, alternatives i motius queda a la metadada
  d'anàlisi del `.acproj` (per exemple, `analisi_tempo`), no al CSV canònic.
- No inventar camps al model sense actualitzar el contracte i el CHANGELOG.

---

## 12. Fases d'implementació

### Fase 1 — Resolució i fase

- Eliminar la graella de 0,25 de la decisió final.
- Refinar candidats per fase.
- Retornar `144,70` en compte de `144,75`.
- Tests amb clics sintètics i amb el corpus real.

### Fase 2 — Cos estable

- Detectar el tram estable i excloure intro/outro.
- Mostrar l'abast usat.
- Tests amb final lent.

### Fase 3 — Objecte de resultat i alternatives

- Retornar candidats, descartats, confiança i motius.
- No canviar encara la UI principal; només exposar les dades.

### Fase 4 — UI d'alternatives i «Per què?»

- Targetes de candidat.
- Escolta amb metrònom.
- Botons `Aplica`, `No aplicar`, `Bloqueja`, `No ho sé`.

### Fase 5 — Motor per defecte i detecció en obrir

- Canviar el default de QM a automàtic/consens.
- Detecció ràpida en segon pla en obrir.
- No aplicar automàticament.

### Fase 6 — Tempo variable

- Mapa per trams quan el cos no siga estable.
- No forçar un BPM únic.

---

## 13. Tests necessaris

- Clic sintètic a **144,70** amb intro i outro a un altre BPM → retorna
  `144,70 ±0,05`.
- Mateix àudio amb la graella antiga → no ha de tornar `144,75`.
- Tema amb final lent → el BPM principal no es mou.
- Tema amb meitat/doble → alternatives explicades.
- QM a 120,2 → no ha de guanyar si el cos és clar.
- Mapa amb diversos trams → no s'aplica el BPM global sense avís.
- Regressió del corpus real de Foo Fighters.
- Usuari que bloqueja 144,70 → una anàlisi posterior no el sobreescriu.
- Usuari que diu «no ho sé» → l'app no aplica res i no bloqueja la UI.
- Usuari que introdueix una referència externa → l'app mostra si encaixa o no.

---

## 14. Decisions obertes

1. **Arrodoniment:** sempre a 0,1 BPM o només quan la corba és plana?
2. **Detecció en obrir:** activa per defecte o opt-in?
3. **Aplicació automàtica:** mai, o només amb confiança molt alta i un sol tram?
4. **Persistència de la confiança:** al `.acproj` o només en memòria?
5. **Llindars:** quina diferència mínima entre primer i segon candidat per decidir?
6. **Bloqueig:** per projecte, per tram o tots dos?
7. **QM:** es mostra sempre com a contrast o només si difereix més del 4%?
8. **Tempo variable:** es detecta automàticament o només amb «Detecta per trams»?

---

## 15. Criteris d'acceptació

- Una cançó estable a 144,7 pot mostrar **144,70 BPM** de forma reproduïble.
- `144,75` no apareix com a resultat principal si el cos real és 144,7.
- El final lent no arrossega el BPM global.
- L'usuari veu almenys una explicació del resultat principal.
- Si hi ha ambigüitat, l'usuari pot triar o dir «no ho sé».
- L'aplicació al model és explícita i reversible.
- QM no s'usa fora dels talls QM.
- La suite i els tests de regressió del tempo passen.

---

## 16. Relació amb les regles de l'app

- No es canvia cap regla d'or.
- L'anàlisi continua sent una proposta; l'aplicació al mapa és una edició de
  l'usuari.
- El BPM intern continua sent negres/minut; la unitat percebuda es mostra a
  part.
- QM només s'usa als talls QM.
- El model canònic continua sent `mapa_tempo.csv`; la incertesa no s'hi barreja.
- Qualsevol canvi de comportament s'haurà de documentar al `CHANGELOG` i, si
  afecta el contracte, a `docs/REGLES_DE_LA_APP.md` amb OK de l'operador.

---

## 17. Resum

La idea no és fer que l'app endevine més, sinó fer que **ensenyi el que sap, el
que suposa i el que no pot saber**. L'usuari no ha de demostrar que 144,70 és
«la veritat absoluta»; ha de poder dir:

> «Per a mi, este és el pols útil per a este projecte.»

I l'app ha de respondre:

> «D'acord. Amb estes dades encaixa al 93% del cos; el final no hi encaixa i el
> deixaré com a tram a part.»

Això és més honest que una app que afirma un BPM exacte quan només en té una
sospita, i més útil que una app que obliga l'usuari a endevinar-ho tot.
