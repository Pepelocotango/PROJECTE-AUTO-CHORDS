# Regles de l'app (resum operatiu)

Font canònica: `docs/REGLES_DE_LA_APP.md`. Llegeix-la sencera abans de tocar codi que afecti comportament.

## Regles d'or 1-12 (invariants)

1. Un sol motor d'anàlisi: `vamp_host_local`.
2. Model viu = font de veritat; CSV desats a cada edició.
3. `.acproj` és document (tempo transport, opcions, vista + cru caché); no és el model.
4. Format 3 sense retrocompatibilitat; projectes vells es rebutgen amb error clar.
5. Desar sempre vàlid i atòmic (tmp+fsync+replace).
6. Anàlisi opcional: projecte nou neix amb model complet (1 acord "N", 1 secció "A").
7. Tres pistes editables amb les mateixes eines (acords, estructura, BPM/compàs).
8. Clips silenciosos a propòsit (nom+posició), pont cap al DAW.
9. Loop A/B sense tall, cursor on sona.
10. Import universal via ffmpeg dins `audio/` del projecte.
11. Compàs ≠ secció.
12. Mapa de tempo a `mapa_tempo/mapa_tempo.csv`.

## §13 Temps, compàs i graella (essencial)

- Beats sencers: clips de BPM/compàs han de contenir almenys un beat sencer de la graella (QM o BPM/compàs), inclòs 1/4.
- `+` sempre usa el beat QM més pròxim; ajust prioritza conservar BPM i canviar compàs.
- "Ajusta BPM al compàs" força compassos sencers explícitament.
- Downbeat (offset) absolut: no es mou en ajustar BPM.
- T (tap tempo): només amb clip de tempo seleccionat.
- Graella de corxera (mig temps); posició en compàs.pols.
- Unitat de BPM global (negra/negra punt/corxera/blanca); metrònom amb unitat de clic independent.
- Metrònom per denominador: beat = 4/den negres.

## Validació als 4 punts

Tota regla s'ha de complir a: edició en viu (GUI), visor, CSV desat, exportació.

## Si una funcionalitat xoca amb una regla

Es canvia la funcionalitat, mai la regla (tret de decisió explícita de l'operador, documentada al CHANGELOG).
