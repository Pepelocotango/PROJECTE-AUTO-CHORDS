# Seguretat

Aquest document explica **com informar d'un problema de seguretat** i quina
política seguim amb les llibreries natives que l'app porta a dins.

## Com informar d'un problema

**Escriu a [pepelocotango@gmail.com](mailto:pepelocotango@gmail.com)** (el
mateix contacte que surt al `README`).

- Si pots, indica: **què passa**, **com reproduir-ho**, **quina versió de
  l'app** (surt a «Quant a Auto Chords») i **quin sistema** (Linux, Windows o
  macOS).
- **Si us plau, no ho publiquis en obert** fins que hàgim pogut mirar-ho i
  arreglar-ho: així ningú no queda exposat mentre no hi ha solució.
- És un **projecte personal**: no hi ha recompenses econòmiques ni un temps de
  resposta garantit. Es mira amb la millor voluntat i es respon quan es pot.

## Què considerem un problema de seguretat

- Que l'app pugui **executar o llegir coses que no hauria** a partir d'un fitxer
  d'àudio manipulat (per exemple, un fitxer que en realitat és una llista de
  reproducció i que fa que ffmpeg busqui a la xarxa).
- Que una altra persona o un altre usuari de la mateixa màquina pugui
  **controlar l'app** o **llegir-ne les dades** sense permís.
- Que un paquet publicat (AppImage, ZIP de Windows, app del Mac) **no sigui
  exactament** el que es va publicar.

## Com protegim el que publiquem

- Totes les descàrregues del procés de construcció es fan **per HTTPS** i amb el
  **SHA256 comprovat** (`eines/deps_fixades.env` +
  `eines/baixa_verificat.py`). Si un fitxer no coincideix, el build **peta**.
- Les accions de GitHub Actions es fixen **per commit** (no per etiqueta mòbil).
- Cada versió publicada porta un **`SHA256SUMS.txt`** amb la «petjada» de cada
  paquet: qui el baixa pot comprovar que és el que nosaltres vam publicar.

## Política d'actualització de les llibreries natives

- A **cada versió** es repassa la llista de components
  (`docs/COMPONENTS_I_VERSIONS.md`) i, si n'hi ha alguna amb un avís de
  seguretat publicat, **s'actualitza**.
- **No** s'actualitza res «per tenir-ho més nou»: es fixa el que funciona i es
  comprova. Hi ha components **clavats** per maquinari o per compatibilitat:
  - `numpy` s'ha de quedar a la sèrie **1.x** (el processador d'aquest equip no
    té AVX; la 2.x faria petar l'app).
  - A **macOS High Sierra (10.13)** hi ha versions concretes que no es poden
    pujar (p. ex. PyQt5 5.15.10, ffmpeg amb mínim 10.13).
- Detall tècnic de tot plegat: **`docs/SEGURETAT.md`**.
