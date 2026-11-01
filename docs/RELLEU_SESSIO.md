# Relleu de sessió — PROJECTE AUTO CHORDS

> Document per a un agent diferent que agafi el relleu. Estat actual del projecte
> després de les sessions de novembre 2026.

## Estat de les fases del pla (`00PER FER/PLA_SIMPLIFICACIO_TEMPO.md`)

| Fase | Estat | Notes |
|------|-------|-------|
| 0 Base i corpus | Completada (avaluador + sintètics) | Corpus real pendent de rebre (no bloqueja) |
| 1 Constants i validació | Completada | `app/limits.py`, `tempo_map.valida_tempo` |
| 2 Fuzzer i proposta de regles | Completada i fusionada | `docs/PROPOSTA_REGLES_v2.md` eliminat (fusionat al contracte) |
| 3 TAP robust i destí visible | Completada | Mediana + descart; `lb_desti_accions` |
| 4 Compàs vs secció | Completada | Dos botons, tipus de marcador, colors, menú contextual |
| 5 Ajust d'un sol BPM | Completada | `app/tempo_ajust.py`, partició recursiva |
| 6 Edició bàsica d'àudio | Pendents | Retall/afegit extrems implementat; exportació d'àudio pendent |
| 7 Rubato exportat i anacrusi | Pendents | Requereix aprovació de canvis al contracte |
| 8 Evolució MIDI | Ajornada | |
| 9 Anàlisi guiada aparcada | Ajornada | |
| 10 Motor de detecció | Pendents | |
| 11 Flux del 90 % | Ajornada | |
| 12 Congelació i higiene | Pendents | |

## Bugs corregits recentment

- **Downbeat (offset) absolut**: les operacions d'ajust de BPM a partir de
  marcadors ja no desplacen l'offset. L'offset només canvia quan l'usuari
  l'edita explícitament. (commit `db32196`)
- **T (tap tempo)**: només actua quan hi ha un clip de BPM/compàs
  seleccionat; sense selecció o amb acords/seccions seleccionats, no fa res.
  (commit `8620f79`)

## Commits recents (novembre 2026)

- `8620f79` Corregeix: T (tap tempo) només amb clip de tempo seleccionat
- `db32196` Corregeix: downbeat (offset) absolut, no es mou en ajustar BPM
- `6fc462b` Fase 5: ajust d'un sol BPM per mínims quadrats i partició recursiva
- `b80912d` Fase 4: menú contextual per convertir marcadors
- `18c46f1` Fase 4: compàs vs secció, tipus de marcador i colors
- `6b73a8b` Fases 2-3: fuzzer i proposta fusionada, TAP robust i destí visible

## Feina pendent principal

1. **Fase 6**: exportació d'àudio amb FFmpeg (formats WAV, MP3, FLAC, AAC/M4A,
   OGG, Opus), validació d'encoders, errors visibles.
2. **Fase 7**: rubato aproximat a l'exportació i anacrusi (requereix aprovació
   de canvis al contracte §13.7 i regla 12).
3. **Fase 10**: millores del motor de detecció (amb mesures sobre corpus).
4. Rebre corpus real per a la Fase 0.

## Notes importants

- La font de veritat és el **CODI**, no els `.md`. `docs/REGLES_DE_LA_APP.md` és
  el contracte (canvis només amb aprovació explícita de l'operador).
- Suite completa: ~1.436 tests, `pyflakes` net.
- Entorn: Q9400 sense AVX, `numpy<2` obligatori.
- No fer push sense ordre de l'operador.

## Última actualització

2026-11-01 — sessió tancada després de Fase 5 i correccions de bugs.
