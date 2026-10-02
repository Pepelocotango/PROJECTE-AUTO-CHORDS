# Full de ruta — PROJECTE AUTO CHORDS

Visió: a partir de un arxiu de audio carregat a la app, n'extraiem acords + estructura , pensat principalment en obtenir carpetes separades amb clips de wavs llestos per al Live/Reaper, pero obert a altres exportacions futures.
amb un visor on **escoltar, navegar, corregir i re-exportar**.
Tot en català. Llicència: GPLv3.

## Estat actual (2026-10-02)

El projecte ja ha passat de prototip funcional a flux de producte útil:

- app principal única i estable
- visor integrat dins la mateixa finestra
- procés d’anàlisi amb una sola acció clara (`Processa`)
- revisió i edició d’acords i seccions des del visor
- export final separat i explícit (`Finalitza i publica`)
- llançament directe des de la carpeta del projecte
- bloqueig de doble instància per evitar sobreposició d’aplicacions

La base funcional està validada. El que queda són millores de polish i estabilització, no reescriure el flux bàsic.

## Fase A — Visor navegable ✅

- ona, cursor i navegació per temps
- play/stop, loop A-B, zoom i temps en compàs/segons segons el mode
- estructura i acords visibles a la mateixa interfície
- llista d’acords i llista d’estructura operatives
- validació del dock/visor integrat

## Fase B — Edició i correcció ✅

1. **Corregir acord** ✅
   - doble-clic a un acord per editar-ne la nota
   - regenera els `wavs_acords/` sense re-analitzar

2. **Partir / fusionar / eliminar secció** ✅
   - menú contextual sobre la llista ABC
   - regen de `estructura_ABC.csv` i `wavs_estructura/`

3. **Afegir / eliminar acords i seccions** ✅
   - possibilitat d’editar el dataset manualment des del visor
   - regeneració immediata del resultat exportable

4. **Noms `music21`** ✅
   - normalització d’arrel, qualitat i baix/inversió
   - criteri: `G/D`, `Cmaj7`, `Am` estables

## Fase C — Flux producte ✅

- app única des de la qual s’analitza i es revisa el resultat
- export final clar i separat del processament
- llançador directe (`AUTO_CHORDS.sh` / `AUTO_CHORDS.desktop`)
- sorteix sense dependre de terminal ni de múltiples finestres

## Prioritat de millores restants

### Alta
- confirmacions d’export més guiades i logs de resultat més rics
- ajust final del layout i etiquetatge per a usuaris no tècnics
- packaging més net i docs d’ús final

### Mitjana
- historial d’edicions / desfer
- opcions de preset de tempo i export
- validacions visuals addicionals de l’ABC

### Baixa
- suport d’altres formats de sortida
- configuració persistents d’usuari

## Àrees de futur: investigar, valorar i discutir

Aquestes són idees i oportunitats que queden pendents de revisió i que convé gestionar com a feina de producte i d’arquitectura, no com a correccions urgents del flux principal.

### 1) Compassos amb 3 xifres i formats de temps avançats

- investigar com es representarà correctament la estructura en compàs amb notació de 3 xifres, per exemple `1.1.3` o `1.1.50`
- definir si el format és estrictament de visualització o si també entra dins el CSV de referència
- valorar si la codificació del compàs ha de tenir un esquema explícit separant `compàs`, `beat` i `subdivisió`
- decidir si l’editor ha de mostrar sempre “segons” o “compàs” o si ha d’haver un mode dual amb canvi contextual
- garantir que aquesta representació no trenqui el model que ja usa temps en segons com a font de veritat

### 2) Control del processament automàtic i paràmetres d’algoritme

- revisar si `Chordino`, `Segmentino` i els scripts de suport exposen opcions reals de sensibilitat, llindars, auto-generació o ajust d’algoritme
- valorar la introducció d’una finestra de configuració avançada per a:
  - sensibilitat de detecció
  - llindar de confiança d’acords
  - detecció d’estructura i divisió de seccions
  - auto-generació de dades de referència
- decidir si el procés automàtic es manté “simple” per defecte i s’obre un mode expert quan calgui
- documentar clarament què és paramètric i què és resultat “fix”, per evitar la confusió entre dades analitzades i dades editades

### 3) Tema de colors i estètica visual

- millorar el tema global per a una paleta més coherent i menys agressiva
- comprovar si cal un tema “fosc” però amb menys intensitat i més contrast estable
- definir si la UI ha de tenir:
  - colors per categoria (acords, seccions, focus, cursor)
  - paleta mínima i legible
  - contrast calibrat per a treball llarg
- decidir si la gamma de colors forma part de l’arquitectura de tema centralitzat o si s’ha de mantenir en un sistema de variables CSS

### 4) Gràfica i visualització de temps

- millorar la representació visual perquè sigui clar veure la línea temporal en segons i en BPM/compàs
- valorar si la gràfica de l’ona ha de mostrar overlays amb indicadors de compàs, seccions i transicions
- decidir si la visualització ha de tenir un mode “temps real” i un mode “compàs” en paralelo
- revisar si hi ha necessitat d’afegir una etiqueta, una regla o un cursor de forma més clara a la UI

### 5) Auditoria de seguretat i robustesa

- revisar els punts d’entrada de fitxers, paths i execucions externes per fer un control més estricte
- auditar:
  - càrrega de WAVs i CSVs
  - execució de subprocessos
  - paths d’exportació
  - manejo de fitxers temporals
  - logs i processos no autoritzats
- valorar si cal una política de validació de ruta i noms, i si cal evitar l’execució de binaris fora de directoris controlats
- preparar una política d’errors i de registre per a producció, sense exposar informació sensible o innecessària

### 6) Nomenclatura de fitxers i convenis d’export

- revisar com es nomenen els WAVs finals i com s’ordenen a la carpeta de sortida
- buscar una regla clara per a:
  - acords
  - parts o seccions
  - clips derivats d’intervals
- que els noms siguin “ordenables” i “legibles” i que el prefixedel text estigui el més a prop possible de l’inici del nom
- definir si el nom és una etiqueta semàntica, temporal, de secció o de versió, i no barrejar totes les idees en un mateix string

### 7) Altres exportacions i formats de partitura

- valorar exportar no només WAVs i carpetes de clips, sinó també altres sortides útils
- possibilitats a estudiar:
  - MusicXML
  - ABC / partitures basades en text
  - LilyPond
  - CSV intel·ligible per DAW i editors externs
  - imatges de partitura o exportació resumida
- decidir quin és el valor real per a l’usuari i si això entra dins el producte core o és un mode de postprocessament
- prioritzar les exportacions amb més rendiment i menys fragmentació de flux

### 8) Desplegament de l’app real

- definir si la app es distribueix com a:
  - binari local per desktop
  - paquet Python
  - app empaquetada per a Linux
  - app per a Windows/macOS
- decidir si cal un procés de build reproducible amb versions i checksums
- preparar un canal de distribució per a usuaris finals, no només per a desenvolupament local

### 9) Desplegament a altres SO

- revisar compatibilitat de dependències per a Linux, Windows i macOS
- detectar quines parts del stack són dependents de platforma i quines són universals
- determinar els punts crítics:
  - PyQt5 / Qt5
  - execució de `sonic-annotator` i plugins
  - subprocessos i reproductors d’àudio
  - paths i permisos de fitxers
- decidir una estratègia modular per a build multi-platform i per a mantenir un nucli de producte estable

## Criteri de producte actualitzat

La projecta es considera funcionalment preparada per a l’ús del flux principal quan:

- un usuari pot obrir una WAV
- analitzar-la sense terminal
- veure i navegar acords i estructura
- corregir, eliminar o afegir acords i seccions
- exportar el paquet final per a DAW
- i fer-ho tot des d’una sola app, amb un flux clar i repetible.

Aquest criteri ja està cobert en la seva base funcional i validat per regressions del pipeline i la UI.
