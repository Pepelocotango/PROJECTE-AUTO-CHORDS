# AUTO PROMPT — continuació del projecte AUTO CHORDS

> Enganxa aquest text sencer al començament d'una conversa nova.

## Context
Treballo al repo `/home/peplx/0PROJECTES_GitHub/PROJECTE AUTO CHORDS` (app PyQt5
«Auto Chords», tot en **català**). **L'operador i jo, sols**: jo faig codi,
tests, documentació i **commits locals** (MAI push).

## Regles de treball
- Suite: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests`
  (**871 tests**, ha d'estar sempre verda) + `.venv/bin/python -m pyflakes app/*.py tests/*.py`.
- Commits locals petits; el que es canvia es documenta a `docs/`.
- La **regla d'or #4** (els clips cobreixen tota la WAV) s'està **reubicant**: deixa
  de ser un guard a cada edició i passa a complir-se **al final de cada operació**.

## La tasca (especificada i TANCADA)
`docs/PLA_EDICIO_LLIURE.md`, **§6**. Resum:
- Símbols: **`-`** = «sense secció» · **`N`** = «sense acord».
- **Mana l'últim editat**; cap operació es refusa per la #4.
- **Moviment d'un bloc (1+ clips, mateixa durada)**:
  - **Endavant**: l'anterior s'estira fins a l'inici de la selecció; al destí
    **es talla l'inici** del solapat, o **s'elimina** si el seu final cau dins o
    més enllà del bloc.
  - **Endarrere**: el posterior s'estira fins al final de la selecció; al destí
    **es talla el final**, o **s'elimina** si el seu inici cau dins o més enllà.
- **Esborrar** (1+ clips): **l'anterior s'estira** (opció a). `N` només si el
  model queda sense cap clip.
- **L'origen ja fa el que volem** (el model de marques estira el veí sol).
  **El gruix és el DESTÍ**: preservar la durada + tallar/eliminar.

## Següent pas (començar aquí)
Punt **1 de §6.6: el DESTÍ del moviment**. Primer un test que reprodueixi els
dos exemples de l'operador (endavant i endarrere amb el mateix dibuix de clips),
després implementar-ho. Ordre: 2) treure el guard de l'últim a l'esborrar ·
3) duplicar/enganxar · 4) seccions amb `-` · 5) guia Live/partitura + export
normalitzat + MCP (esborrar/duplicar la selecció).

## Imprescindible (no repetir errors)
- **⚠️ BUG OBERT (greu)**: les **lletres d'estructura es re-etiqueten totes
  soles** (log de l'app ~línies 3395-3439: l'`E` → `B` amb el mateix recompte;
  la `F` de 25 s també va passar a `B`). **No fer més proves sobre estructura**
  fins entendre-ho. Sospitosos: regeneració de l'ABC, normalització de cobertura
  i snapshot del desfer.
- Fixes previs: `fa25969` (Del + multi-selecció) · `07d383a` (Ctrl+D + multi +
  auditoria) · `e131837` (esborrar-ho tot → `_normalitza_cobertura()` a l'instant).
  Pla: `6e947d2` + `5e83c3c`.
- **Model**: acords = **marques** (final = marca següent) · seccions = inici/fi
  explícits · `N` ja existeix · **no cal migrar cap CSV**.
- **Ganxo existent**: `Visor._normalitza_cobertura()` (1r a 0 + última secció a
  la durada) — cridar-lo al final de cada operació.
- L'app oberta de l'operador **cal reiniciar-la** per veure canvis de codi.
- MCP (`AUTO_CHORDS_MCP.sh`): ~50 eines `ac_*`; **no hi ha** esborrar/duplicar la
  selecció. Per confirmar estats: `ac_status`, `ac_selection`, `ac_list_chords`,
  `ac_list_sections`.
- **Cursors** (pendent): l'operador va rebutjar el disseny proposat; definir-ne
  un altre amb ell abans de tocar res.
