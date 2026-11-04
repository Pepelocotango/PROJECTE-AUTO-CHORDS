# Pla — flux de marcadors, beats QM i graella

> **2026-11-04 · fase 10.** Flux acordat: `+` continua creant **inici de
> compàs + inici de secció** en una sola pulsació; la gràcia és que
> internament la graella i l’estructura queden separades. La resolució de
> dubtes es fa **després** del play, mai amb diàlegs mentre sona.

## Objectiu

Permetre construir una graella de BPM/compàs a partir de:

1. els beats/downbeats de QM;
2. un BPM i un compàs de referència;
3. els marcadors de compàs de l’usuari (`+`);
4. un snap reversible dels marcadors a les línies de QM.

La secció que crea `+` es pot editar després amb les eines d’estructura sense
que desaparega l’ancoratge de compàs.

## Decisions

- `+` = **compàs + secció**; no es pregunta res durant el play.
- La secció és independent de l’ancoratge de compàs després de crear-se.
- El snap es fa **en parar** o amb una acció explícita.
- El selector Snap incorpora **Beats QM** per al cursor i els clips.
- Amb Snap actiu, el `+` encaixa el marcador a la línia de QM més pròxima
  (120 ms); si no n'hi ha cap, conserva el temps del cursor.
- Només es snapen marcadors que tenen un beat/bar de QM dins de la tolerància.
- Els dubtes queden en una llista; no bloquegen.
- El BPM/compàs es recalcula amb els marcadors snapats; un sol desfer.
- Els canvis de metre són de l’usuari; QM no els inferix.
- Si el tall cau al beat 3, pot ser línia de compàs si el metre anterior és
  `2/4`; la validació usa el metre vigent, no una suposició 4/4.

## Fases

### Fase 1 — Snap i ajust (implementada en este bloc)
- Funció pura `marcadors.snap_a_objectius()`.
- `Visor.ajusta_graella_a_beats()`:
  - snapeja els marcadors;
  - mou les seccions només si encara coincidien;
  - recalcula el mapa amb `tempo_map.ajusta_trams_a_marcadors`;
  - un sol desfer.
- Acció de menú **Ajusta la graella als beats QM…**.
- Tolerància configurable (ms).
- Informe de moguts/dubtosos.

### Fase 2 — Revisió no modal ✅
- `DialegRevisioSnap`: llista no modal de talls dubtosos.
- Doble clic al tall → cursor al punt per inspeccionar-lo.
- **Snap al candidat** per a un tall individual.
- No bloqueja el play ni l’edició.

### Fase 3 — Metres variables (en curs)
- El model de `mapa_tempo` ja admet `num/den` per tram.
- Nova acció **Compàs del marcador…**: edita el metre del clip de tempo que
  comença en un marcador.
- QM per regions encara no automàtic; per a metres variables, usar beats +
  metre de l’usuari o editar el clip.
- Propostes automàtiques de `2/4`, `3/4`, `7/4` encara pendents.

## Criteris d’acceptació de la fase 1

- `+` continua creant compàs + secció.
- Editar una secció no mou l’ancoratge de compàs.
- El snap no mou res si no hi ha un beat dins de la tolerància.
- Els marcadors snapats queden en ordre i sense duplicats.
- El mapa resultant cobreix tota la WAV i té compassos enters.
- Un sol `Ctrl+Z` desfà snap + mapa.
- Cap diàleg durant el play.

## Límit actual

En esta fase el metre és el vigent del transport; els canvis de metre es
resolen en la fase 3. El snap no inventa un compàs: si el metre no quadra,
l’interval queda dubtós.
