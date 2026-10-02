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

## Criteri de producte actualitzat

La projecta es considera funcionalment preparada per a l’ús del flux principal quan:

- un usuari pot obrir una WAV
- analitzar-la sense terminal
- veure i navegar acords i estructura
- corregir, eliminar o afegir acords i seccions
- exportar el paquet final per a DAW
- i fer-ho tot des d’una sola app, amb un flux clar i repetible.

Aquest criteri ja està cobert en la seva base funcional i validat per regressions del pipeline i la UI.
