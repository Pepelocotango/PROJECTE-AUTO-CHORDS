# Detecció i alineació de beats i downbeats sobre la forma d'ona

**Document tècnic per avaluació i implementació**
**Estat:** especificació de treball; les propostes s'han de validar amb el corpus de proves del projecte.
**Àmbit:** detecció d'onsets, beats, downbeats, BPM, alineació temporal i correcció assistida per l'usuari.

---

## 1. Objectiu

Definir una metodologia robusta per:

1. detectar esdeveniments d'atac (*onsets*) en un senyal d'àudio;
2. estimar els beats i el període del pols (BPM);
3. determinar quin beat correspon al primer temps del compàs (*downbeat*);
4. alinear una graella de BPM amb el temps musical real;
5. permetre que l'usuari corregeixi el resultat sense perdre les dades originals de l'anàlisi.

Aquest document no prescriu substituir necessàriament el motor actual del projecte. Proposa una arquitectura d'avaluació i millora que es pot aplicar als resultats dels motors existents (incloent-hi QVamp/Sonic Visualiser) i a motors alternatius.

## 2. Terminologia: conceptes que no s'han de confondre

| Concepte | Definició operativa | Què no significa |
|---|---|---|
| **Onset** | Inici perceptible d'un esdeveniment sonor, com una nota, cop o canvi d'energia/espectre. | No és necessàriament un beat. |
| **Beat** | Posició temporal del pols musical percebut. | No és necessàriament el pic d'amplitud ni un atac acústic visible. |
| **Downbeat** | Primer beat d'un compàs, és a dir, el beat amb posició mètrica 1. | No és necessàriament el primer so del fitxer ni el so més fort. |
| **BPM** | Nombre de beats per minut; defineix el període mitjà del pols. | No defineix per si sol la fase ni quin beat és el primer del compàs. |
| **Fase/alineació** | Desplaçament temporal de la graella respecte del senyal. | No és el mateix que estimar el BPM. |
| **Anacrusi** | Material musical que precedeix el primer temps d'un compàs complet. | No s'ha de convertir automàticament en downbeat. |

**Distinció fonamental:** trobar el BPM correcte no garanteix trobar la fase correcta; trobar els beats no garanteix identificar el downbeat. El sistema ha de tractar aquestes tasques per separat.

## 3. Resposta a la pregunta principal: on col·locar el marcador?

### 3.1 Regla general

No s'ha de col·locar sistemàticament el marcador al màxim de l'ona ni al màxim RMS.

Quan el beat coincideix amb l'atac d'un instrument, una referència inicial raonable és l'inici temporal de l'atac musical, no el pic posterior d'amplitud o d'energia. Però això és una **heurística**, no una llei universal.

El beat és una posició musical. Pot coincidir amb:
- l'inici d'un atac clar (bombo, caixa, pua, piano);
- un so d'atac lent (corda fregada, pad, baix suau);
- una nota sostinguda o una veu sense atac clar;
- un beat sense atac nou, per exemple quan el pols continua mentre el so anterior es manté;
- un punt de silenci o una pausa expressiva.

Per tant, el marcador de beat/downbeat ha de representar la posició musical estimada. La forma d'ona i els detectors d'onset són evidències per estimar-la, no la definició del beat.

### 3.2 Esquema conceptual d'un atac percussor

```text
amplitud
   ^
   |             pic
   |              /\
   |             /  \
   |            /    \__
   |___________/___________> temps
               ^
               inici aproximat de l'atac
```

- **Inici de l'atac:** punt on comença el canvi acústic significatiu que forma part de l'esdeveniment.
- **Pic d'amplitud:** màxim instantani posterior; habitualment és massa tard per usar-lo com a referència d'inici.
- **Pic RMS:** màxim d'energia dins d'una finestra; depèn de la mida i el desplaçament de la finestra i tampoc no defineix l'inici.

En una forma d'ona real pot ser difícil veure l'inici perquè hi ha soroll de fons, reverberació, compressió, altres instruments o una transició gradual. No s'ha d'inferir un atac només perquè hi hagi una oscil·lació petita.

### 3.3 Exemples conceptuals

**Atac sec (kick, caixa, palmada):** el primer transitori clar pot ser un bon indici d'onset.
**Atac progressiu (piano, baix, guitarra o corda):** el pic pot arribar força després de l'inici; cal combinar informació temporal, espectral i auditiva.
**So amb reverberació o soroll previ:** cal distingir el nou atac de la cua del so anterior o del soroll de fons.
**Beat sense atac:** no hi ha cap pic que es pugui marcar; el beat s'ha d'inferir de la continuïtat de la graella i del context musical.

---

## 4. Amplitud, RMS i funcions d'onset

### 4.1 Forma d'ona

La forma d'ona mostra les mostres d'àudio al llarg del temps. És útil per a la inspecció i l'ajust fi, però els màxims positius o negatius són oscil·lacions de la forma d'ona, no esdeveniments musicals per si mateixos.

No s'ha d'usar:
- el primer creuament per zero com a onset universal;
- el primer màxim local de la forma d'ona;
- el màxim absolut d'amplitud del fragment.

### 4.2 RMS

L'RMS d'una finestra de N mostres es pot expressar com:

\[
RMS[n] = \sqrt{\frac{1}{N}\sum_{k=0}^{N-1}x[n-k]^2}
\]

És una mesura de nivell/energia local. És útil per detectar canvis d'energia, però:
- depèn de la mida de finestra i del salt (*hop*);
- suavitza els transitoris;
- pot assolir el màxim després de l'inici real;
- pot respondre a un augment de volum que no és un onset musical;
- no identifica el downbeat.

És acceptable utilitzar RMS com una característica més o com a funció d'energia per a un refinament, però no com a marcador final universal.

### 4.3 Spectral Flux

El *spectral flux* mesura, de manera simplificada, l'augment de magnitud espectral entre frames consecutius (sovint amb diferències positives rectificades). És una funció d'intensitat d'onset: tendeix a destacar canvis espectrals, en lloc de mirar només l'amplitud global.

És una bona opció general per generar candidats d'onset, però pot fallar o donar falsos positius en:
- canvis de timbre;
- vibrato o modulacions;
- soroll i percussió contínua;
- mescles denses;
- atacs molt suaus;
- sons amb molta energia sostinguda.

### 4.4 Altres funcions d'onset

Essentia documenta diversos mètodes:
- **HFC (High Frequency Content):** útil especialment per a esdeveniments percussius;
- **Complex / Complex Phase:** combina informació de magnitud i fase espectral;
- **Flux:** canvis de magnitud espectral;
- **MelFlux:** diferències d'energia en bandes Mel;
- **RMS:** canvis d'energia RMS.

Cap mètode és òptim per a tots els instruments i estils. Cal comparar-los amb dades reals i no assumir que un únic detector és universalment superior.

---

## 5. Pipeline recomanat

Separar el procés en etapes permet diagnosticar errors i substituir components sense perdre informació.

### Etapa A — Preparació de l'àudio
1. Llegir el senyal i conservar la freqüència de mostreig original.
2. Gestionar mono/estèreo de manera explícita. No descartar canals sense justificar-ho.
3. Si cal, generar una còpia mono per a l'anàlisi, documentant el mètode de mescla.
4. Conservar el temps en segons i la correspondència exacta entre frames i mostres.
5. Evitar canvis de sample rate innecessaris; si un motor exigeix 44,1 kHz, fer el resampling correctament i conservar el mapping temporal.

### Etapa B — Característiques d'onset
1. Calcular una o més ODF: com a mínim Spectral Flux; opcionalment HFC, Complex, MelFlux i RMS-difference.
2. Guardar paràmetres: mida de frame, hop, finestra, sample rate, canal/mescla i normalització.
3. Aplicar suavitzat i normalització només si s'avalua el seu efecte; conservar també la funció original.
4. Detectar pics locals amb llindar adaptatiu i període refractari per evitar duplicats.

### Etapa C — Candidats d'onset i refinament
1. Obtenir pics candidats a partir de l'ODF.
2. Per a cada pic, estimar un inici anterior mitjançant *backtracking* sobre una funció d'energia adequada.
3. Refinar opcionalment amb l'àudio original i/o una envolupant temporal.
4. Conservar **tant el pic ODF com el punt refinat**. No sobreescriure el pic original.
5. Assignar una confiança i informació del mètode, no només un timestamp.

La funció `librosa.onset.onset_backtrack()` retrocedeix des dels esdeveniments detectats fins al mínim local precedent de la funció d'energia que se li proporciona. És una tècnica útil per aproximar l'inici d'un atac, però no converteix automàticament el resultat en el beat musical ni en el downbeat. Cal validar quina funció d'energia s'hi passa i com afecta cada tipus de material.

### Etapa D — Beat tracking
1. Estimar el període/tempo a partir de la periodicitat de les funcions rítmiques.
2. Generar una seqüència de beats coherent amb el tempo i els candidats d'onset.
3. Permetre tempo variable quan el material ho requereixi.
4. No forçar tots els beats a coincidir amb un onset: alguns beats poden no tenir un atac clar.
5. Guardar els beats estimats i la confiança per separat dels onsets.

Com a referència, `librosa.beat.beat_track()` descriu tres fases: mesurar la força d'onset, estimar el tempo a partir de la correlació dels onsets i seleccionar pics compatibles amb el tempo. Essentia `RhythmExtractor2013` retorna BPM, posicions dels beats i confiança (amb el mètode `multifeature`).

### Etapa E — Downbeat / fase mètrica
1. Rebre una seqüència de beats i un o més compassos candidats (si el compàs no és conegut, mantenir alternatives).
2. Avaluar quina fase de la seqüència correspon al temps 1 del compàs.
3. Utilitzar evidències musicals: accents, patrons de bombo/caixa, baix, harmonia, repeticions i estructura.
4. No assumir que el primer beat detectat del fitxer és el downbeat.
5. No assumir que el beat més fort és sempre el primer temps.
6. Retornar una hipòtesi de downbeat amb confiança i alternatives quan hi hagi ambigüitat.
7. Permetre a l'usuari marcar el downbeat i recalcular la numeració dels compassos sense alterar el BPM ni els onsets originals.

La detecció de downbeat és una tasca d'estructura mètrica, diferent de la detecció d'onsets i del beat tracking. Si el motor actual no proporciona downbeats, no s'ha de presentar el primer beat com a downbeat sense una justificació o confirmació.

### Etapa F — Validació i correcció de l'usuari
1. Mostrar la graella de beats sobre la forma d'ona.
2. Mostrar, opcionalment, ODF i RMS en pistes separades.
3. Permetre zoom fins a mil·lisegons i desplaçament fi del marcador.
4. Permetre escoltar un fragment abans/després del marcador, amb clic/metrònom de referència.
5. Separar les accions «corregir BPM», «desplaçar fase», «definir downbeat» i «canviar compàs».
6. Registrar les correccions de l'usuari com a dades pròpies, sense destruir el resultat automàtic ni les dades originals.

---

## 6. Model de dades suggerit

Els noms són orientatius; adaptar-los a l'esquema actual del projecte.

```json
{
  "analysis": {
    "sampleRate": 44100,
    "channels": 2,
    "frameSize": 2048,
    "hopSize": 256,
    "timeReference": "seconds"
  },
  "onsets": [
    {
      "odfPeakTime": 1.234,
      "refinedAttackTime": 1.210,
      "method": "spectral_flux",
      "confidence": 0.82
    }
  ],
  "beatTrack": {
    "bpm": 120.0,
    "meter": [4, 4],
    "beats": [
      {
        "time": 1.210,
        "beatIndex": 1,
        "barIndex": 1,
        "beatInBar": 1,
        "confidence": 0.78
      }
    ],
    "tempoModel": "constant"
  },
  "downbeat": {
    "time": 1.210,
    "source": "automatic",
    "confidence": 0.71,
    "alternatives": []
  },
  "userCorrections": [
    {
      "type": "set_downbeat",
      "time": 1.210,
      "previousTime": 1.185
    }
  ]
}
```

Requisits del model:
- timestamps en segons (o mostres) amb una única convenció documentada;
- no barrejar temps de frame, temps de mostra i segons sense conversions explícites;
- distingir `odfPeakTime`, `refinedAttackTime`, `beatTime` i `downbeatTime`;
- preservar la procedència (`source`: motor, versió, automàtic, usuari);
- conservar confiança i paràmetres;
- representar canvis de tempo i compassos variables si el projecte els suporta;
- no assumir que `downbeat.time` sempre coincideix amb un onset.

## 7. Interfície d'usuari recomanada

### Pistes visuals
1. **Forma d'ona:** senyal original, amb zoom.
2. **ODF:** corba de Spectral Flux o funció seleccionada, normalitzada i etiquetada.
3. **RMS/envolupant:** opcional, en una escala separada.
4. **Graella de beats:** línies verticals regulars o adaptatives.
5. **Downbeat:** marcador visual diferenciat i numeració de compassos.

### Interaccions
- arrossegar el downbeat sense canviar BPM;
- moure un beat individual només si s'activa un mode de correcció local;
- definir el temps 1 i el compàs;
- escoltar abans/després i escoltar amb metrònom;
- desfer/refer;
- mostrar el resultat automàtic original i el resultat corregit;
- indicar incertesa quan hi hagi dues fases plausibles.

No cal que l'usuari vegi totes les funcions tècniques per defecte. Es pot oferir una vista avançada amb ODF/RMS per a diagnòstic.

## 8. Errors i casos límit que s'han de contemplar

- **Anacrusi:** la primera nota no és necessàriament el temps 1.
- **Silenci inicial:** el primer beat pot arribar després d'un espai buit.
- **Introducció lliure o rubato:** no hi ha una graella estable des del primer instant.
- **Atac lent:** el màxim d'energia arriba tard respecte del començament musical.
- **Beat sense onset:** el pols continua sense un nou transitori.
- **Pickup, síncope o anticipació:** un atac fort pot caure fora del downbeat.
- **Half-time/double-time:** el BPM pot ser ambigu a meitat o doble tempo.
- **Canvis de tempo:** una sola graella constant pot desalinear-se progressivament.
- **Canvi de compàs:** no assumir sempre 4/4.
- **Polirítmia o subdivisions:** els onsets poden correspondre a subdivisions, no a beats.
- **Reverberació i cues:** no confondre el final d'un so amb un atac nou.
- **Mescla densa:** el flux espectral pot respondre a canvis tímbrics que no són beats.
- **Clipping/limitació:** els pics d'amplitud poden perdre valor com a indicadors.
- **Canals estèreo diferents:** una suma mono pot cancel·lar parcialment components; cal provar-la.

## 9. Proposta de proves i criteris d'acceptació

Preparar un corpus etiquetat manualment, amb referència temporal de beats i downbeats. Incloure diversos gèneres, instruments, compassos i dificultats.

### Casos mínims
1. bateria clara amb kick al temps 1;
2. bateria amb caixa accentuada als temps 2 i 4;
3. piano amb atac progressiu;
4. baix amb atac lent;
5. música sense bateria;
6. anacrusi;
7. silenci inicial;
8. introducció sense pols;
9. cançó amb canvi de BPM;
10. síncopes i anticipacions;
11. 3/4 o 6/8;
12. beat sense onset clar;
13. estèreo amb informació diferent per canal.

### Mètriques
- **Onset detection:** precision, recall i F-measure amb una tolerància temporal definida.
- **Beat tracking:** Beat F-measure amb tolerància documentada, i mètriques de continuïtat/consistència quan sigui pertinent.
- **Downbeat:** F-measure de downbeat i exactitud de fase/compàs.
- **Alineació:** error absolut en mil·lisegons entre beat/downbeat estimat i anotació de referència.
- **Tempo:** error absolut de BPM, i anàlisi separada dels errors ×2 i ÷2.
- **Experiència d'usuari:** nombre de correccions, temps fins a una alineació acceptable i percentatge de casos resolts manualment.

No fixar llindars arbitraris abans de mesurar el corpus. Definir toleràncies segons el cas d'ús i la resolució temporal del sistema.

### Criteris funcionals
- canviar el downbeat no modifica el BPM;
- canviar el BPM no destrueix la correcció manual del downbeat sense demanar-ho;
- el marcador pot situar-se en un beat sense onset;
- la interfície diferencia onset, beat i downbeat;
- el sistema conserva el resultat automàtic i l'historial de correccions;
- els resultats es poden reproduir amb els mateixos paràmetres;
- es pot comparar el motor actual amb motors alternatius sobre el mateix corpus.

---

## 10. Recomanació d'implementació per fases

**Fase 1 — Instrumentació i visualització**
- exposar timestamps i paràmetres dels resultats actuals;
- superposar beats i downbeat a la forma d'ona;
- afegir zoom i correcció manual independent del BPM.

**Fase 2 — Diagnòstic d'onsets**
- afegir o calcular Spectral Flux i RMS com a pistes de diagnòstic;
- conservar pics ODF i punts refinats;
- provar backtracking sense canviar encara el motor principal.

**Fase 3 — Comparació de detectors**
- executar els mètodes candidats sobre el mateix corpus;
- comparar precisió, cost, latència, dependències i compatibilitat amb les màquines objectiu;
- no adoptar una llibreria només perquè tingui més funcions.

**Fase 4 — Downbeat i estructura mètrica**
- avaluar un detector específic de downbeat o una capa de classificació mètrica;
- oferir alternatives/confiança;
- incorporar la correcció manual com a dada de primera classe.

**Fase 5 — Integració i regressió**
- fixar proves de regressió per a cada cas difícil;
- verificar que una millora d'onset no empitjora el beat tracking o el downbeat;
- documentar versions, paràmetres i limitacions.

---

## 11. Advertiments per als agents de codi

1. **No implementar `downbeat = màxim RMS`.** No és una definició correcta.
2. **No implementar `downbeat = primer onset del fitxer`.** Pot haver-hi silenci, introducció o anacrusi.
3. **No confondre pic ODF amb inici acústic.** El pic és un indicador; el backtracking és un refinament possible.
4. **No confondre inici acústic amb beat musical.** Poden no coincidir.
5. **No moure la graella sencera quan l'usuari només corregeix el downbeat**, tret que l'acció triada sigui explícitament corregir la fase de tots els beats.
6. **No substituir el motor actual sense benchmark.** Comparar resultats i compatibilitat sobre el mateix corpus.
7. **No eliminar dades originals.** Conservar resultats automàtics, alternatives i correccions.
8. **No assumir un compàs fix ni un tempo constant** si l'anàlisi detecta canvis o si el material ho requereix.

### Decisió tècnica resumida

- Per detectar **onsets**: començar a avaluar Spectral Flux; comparar HFC, Complex/MelFlux i RMS-difference segons el material.
- Per aproximar l'**inici de l'atac**: provar backtracking fins al mínim local anterior en una funció d'energia adequada, i validar-ho auditivament.
- Per detectar **beats**: utilitzar un beat tracker que combini periodicitat/tempo i força d'onset; no limitar-se a seleccionar tots els pics.
- Per detectar **downbeats**: afegir una etapa mètrica específica que identifiqui el temps 1 del compàs.
- Per garantir un resultat utilitzable: mantenir correcció manual independent, reversible i traçable.

---

## 12. Referències i documentació

1. **Librosa — Onset detection**
   https://librosa.org/doc/main/onset.html
   Documenta `onset_strength` (Spectral Flux), `onset_detect` i `onset_backtrack` (mínim local precedent de la funció d'energia).

2. **Librosa — `onset_backtrack`**
   https://librosa.org/doc/0.11.0/generated/librosa.onset.onset_backtrack.html
   Referència de l'operació de backtracking d'esdeveniments detectats cap al mínim local anterior.

3. **Librosa — `beat_track`**
   https://librosa.org/doc/main/generated/librosa.beat.beat_track.html
   Descriu el beat tracking en tres fases: força d'onset, estimació de tempo per correlació i selecció de pics compatibles amb el tempo.

4. **Essentia (MTG, Universitat Pompeu Fabra) — OnsetDetection**
   https://essentia.upf.edu/reference/streaming_OnsetDetection.html
   Descriu HFC, Complex, Complex Phase, Flux, MelFlux i RMS, i adverteix que la funció resultant s'ha de postprocessar per decidir si un frame conté un onset.

5. **Essentia — RhythmExtractor2013**
   https://essentia.upf.edu/reference/std_RhythmExtractor2013.html
   Retorna BPM, posicions dels beats, confiança (segons el mètode) i intervals entre beats.

6. **Essentia — Tutorial de beat detection i BPM**
   https://essentia.upf.edu/tutorial_rhythm_beatdetection.html
   Explica l'ús de `RhythmExtractor2013`, les diferències entre `multifeature` i `degara`, i les sortides de tempo i beats.

7. **Ableton Live Manual 12 — Audio Clips, Tempo and Warping**
   https://www.ableton.com/en/live-manual/12/audio-clips-tempo-and-warping/
   Explica transitoris, Warp Markers i la correcció del downbeat quan Auto-Warp ha estimat bé el tempo però ha situat malament el primer temps del compàs.

8. **Bello, J. P., Duxbury, C., Davies, M. & Sandler, M. (2004).**
   *On the use of phase and energy for musical onset detection in the complex domain.* IEEE Signal Processing Letters, 11(6), 553–556.
   https://doi.org/10.1109/LSP.2004.827951
   Referència acadèmica sobre detecció d'onsets en el domini complex, combinant magnitud i fase.

9. **Ellis, D. P. W. (2007).**
   *Beat tracking by dynamic programming.* Journal of New Music Research, 36(1), 51–60.
   https://doi.org/10.1080/09298210701653344
   Referència del mètode de beat tracking per programació dinàmica utilitzat com a base de `librosa.beat.beat_track`.

---

## 13. Nota final

Aquest document és una especificació d'avaluació i una guia d'implementació, no una afirmació que un únic algorisme resolgui tots els casos. La decisió final s'ha de basar en proves amb àudio real del projecte, anotacions de referència i escolta crítica.

**Principi rector:** la forma d'ona ajuda a inspeccionar l'àudio; les funcions d'onset ajuden a trobar atacs; el beat tracker estima el pols; i el downbeat identifica la fase mètrica del compàs. Són capes relacionades, però no intercanviables.
