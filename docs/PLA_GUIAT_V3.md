# Anàlisi guiat v3 — **EN STAND BY** (21-10-2026, vesprada)

> L'operador ha decidit **simplificar**: el treball real es fa amb
> **marcadors en viu** (`docs/MARCADORS.md`). Les fases F1–F5 d'este pla
> estan implementades i provades (suite verda), però el flux v3 **no té
> entrada a la UI**: el diàleg era modal i impedia moure el cursor del
> visor, que és just el que cal per marcar el compàs 1. El codi es conserva
> per si es vol recuperar amb un disseny no modal.

---

# Anàlisi guiat v3 (ancoratges) — estat de la implementació

> **Data:** 2026-10-21 · **Estat:** F1–F5 acabades (suite 1256 OK, 1 skip)
> **Especificació:** [`ANALISI_GUIAT_v3.md`](ANALISI_GUIAT_v3.md) (R1–R21, D1–D12)
> **Substituïx:** el flux v2 per trams (`ANALISI_GUIAT.md`), que queda al menú
> *Analitza* com a eina de reparació.

## Què fa, en una frase

L'operador escolta la cançó (amb velocidad ½·⅔·1·1,5·2·4 i to mantingut) i prem
**`+`** cada vegada que comença un compàs; el motor **deriva** el BPM de cada
interval perquè la graella passe exactament pels punts marcats i, d'eixe mapa,
en ix **també l'estructura** (una secció per interval).

## Fases

| Fase | Estat | On viu |
|---|---|---|
| F1 · motor d'encaix | ✅ | `app/ancoratges.py` (`encaixa_ancoratges`, `seccions_de_ancoratges`) |
| F2 · velocitat amb to | ✅ | `app/ffmpeg.py` (`prepara_escolta`, `estira_a_wav`, `VELOCITATS`) |
| F3 · diàleg | ✅ | `app/dialeg_ancoratges.py` (`DialegAncoratges`, `Reproductor`) |
| F4 · generar i aplicar | ✅ | `app/main.py` (`_analisi_ancoratges`, `_aplica_ancoratges`, `_detector_interval`, `_mou_cursor_guia`) + `Visor.aplica_ancoratges` |
| F5 · docs i polit | ✅ | este fitxer, `CHANGELOG`, `ESQUEMA_UI` + vistes, `ANALISI_GUIAT_v3.md` |

## Decisions que canvien el disseny original

- **D13 · Dos marcs abans de començar.** El diàleg exigix **① compàs 1**
  (offset + primer ancoratge) i **② compàs 2** (o un de posterior, amb
  «compassos entre»). D'eixos dos punts ix el **BPM aproximat** i el **rang
  acceptat ±10 %**, que descarta les solucions al doble o a la meitat. Sense
  els dos marcs, «Genera» queda bloquejat.
- **Arrossegar una vora de tempo respecta el sentit del gest**: si arrossegues
  cap a la dreta, la frontera va a la **següent** línia de compàs (abans
  s'imantava a la mateixa i pareixia que no es podia moure).

- **D12 · Finestra modal.** El cursor del visor i la regla de temps avancen amb
  el só (R21) i l'audició arranca on és el cursor, però **no** es pot clicar la
  forma d'ona mentre sona. Fer-la no modal exigix decidir què passa quan
  l'usuari mou el cursor (el só hauria de saltar) — pendent de disseny.
- **El `+` és un atall de finestra** (`QShortcut`), no un `keyPressEvent`: així
  val el `+` de dalt (Maj+`=`) i **el del teclat numèric**, i funciona encara
  que el focus siga en un camp (un `QLineEdit` s'empassava la tecla).
- **El primer interval mana** (R6-bis): no es rebutja per allunyar-se del BPM de
  la barra (que sol ser el 120 per defecte). El bloqueig queda per a
  incoherències dins de la cadena.
- **«Intro»**: el tros anterior al primer ancoratge és una secció pròpia si dura
  més de 50 ms; si no, s'absorbeix a la primera.
- **Reparació de fronteres**: eliminar/fusionar/duplicar un tram imanta la
  frontera a la línia de compàs (`tempo_map.repara_fronteres`) en lloc de
  rebutjar (bug 21-10: després del guiat no es podien editar els trams).

## Temps i limitacions conegudes

- La detecció de BPM **per interval** només s'executa als intervals que la
  cadena no ha pogut encaixar (finestres de 2-5 s són poc fiables).
- No es creen **noms** de secció musicals (A/B/C… i «Intro»); l'operador els pot
  reanomenar amb el clic dret del carril d'estructura.
- El cap queda amb compassos negatius a l'ABC (`-11.2.2`): és la zona abans del
  compàs 1, igual que al flux v2.

## Com provar-ho d'oïda (operador)

1. *Analitza ▸ Anàlisi guiat: ancoratges (v3)* (o el botó **Anàlisi guiat**).
2. **Espai** i punxa **`+`** a cada compàs; mira com el cursor del visor avança.
3. **Genera i aplica** → el mapa i les seccions entren amb **un sol Ctrl+Z**.
4. Comprova que el metrònom cau a lloc i que a **½ el to no canvia**.
