# AGENTS.md — guia per a agents d'IA · PROJECTE AUTO CHORDS

> **Primera lectura:** comença per **`README.md`** (vista de producte: què és i
> què fa l'app) i continua amb aquest fitxer + els passos de «Primers 5 minuts».
> Les regles de l'app NO són ací: la font canònica és **`docs/REGLES_DE_LA_APP.md`**.
>
> ⚠️ **El codi mana sobre la documentació** (detall a «Font de veritat», avall).
> Única excepció: les regles d'or, **invariants** i només amb **OK de l'operador**.

## 🎯 Abast i flux de l'usuari — FONT ÚNICA

> Aquesta és l'única definició de què fa l'app i què queda fora. Si un altre
> document diu una altra cosa, mana aquesta (tret de les regles d'or). El codi
> diu què fa de debò: si divergeix, és un **bug** o una **tasca**, mai una
> llicència per ampliar l'abast. **Ampliar l'abast requereix OK de l'operador.**

**Propòsit:** convertir una cançó en un **mapa editable d'acords, estructura i
tempo/compàs** i exportar-lo com a **clips WAV silenciosos** (més CSV, mapa de
tempo —CSV i MIDI—, guia i partitura) per muntar-lo en qualsevol DAW. L'àudio
original no es toca: només s'edita una còpia de treball dins el projecte.

**Flux:** 1) **Obre l'àudio** (`Ctrl+O` o drag & drop; si no és WAV, `ffmpeg` el
converteix dins `audio/`). En obrir-lo es crea/obre el **projecte**. 2)
**Opcional: analitza** (`F7` tempo/beats, `F5` acords/estructura; l'ordre és
lliure) i/o treballa a mà (1 acord `N` + 1 secció `A`). **L'anàlisi i l'edició
manual són complementaris i iteratius**: l'anàlisi proposa i l'usuari corregeix,
o al revés; no és un flux lineal ni una via substituta de l'altra. 3) **Revisa i
edita** les tres pistes: acords, estructura i BPM/compàs (regla #11). 4)
**Exporta** (`Ctrl+E`): WAVs, `acords.csv`, `estructura_ABC.csv`, `mapa_tempo/`,
guia i partitura; exportar és **independent de desar**. 5) **Desa** el projecte
autocontingut (`Ctrl+S`): `.acproj` + `audio/` + CSV + backups; els **CSV del
model es desen a cada edició** i l'autosave/recuperació són automàtics.

**DINS (ara):**
- Import de **19 formats** → WAV de treball; projecte autocontingut.
- **Anàlisi** Chordino + qm-segmenter + BPM/beats QM; únic motor `vamp_host_local`.
- **Visor DAW de 3 pistes** amb edició completa i desfer/refer.
- **Mapa de tempo/compàs** per trams, tap tempo, metrònom i **export MIDI**
  (`mapa_tempo.mid`).
- **Export** WAVs + CSV + `mapa_tempo/` (CSV + **MIDI**) + guia + MusicXML/PDF/MSCZ.
- **Retall/afegir silenci** als extrems + export d'àudio amb `ffmpeg`.

**FORA d'abast (ara; decisió vigent, no invariant):** afinador i
`Gt_ALL_Chords_app`; edició avançada (fades manuals, guany per clip, crossfade,
snap a zero-crossings); i18n, multi-pestanya i batch/render queue.

**Ajornat (sense data):** fase 10 (motor de detecció amb corpus real) i anàlisi
guiada; rubato i doble graella avançada; **export MIDI d'acords/seccions** (el
mapa de tempo ja és dins) i **export de projecte DAW**.

> Si una tasca no és a «DINS», no es fa sense OK de l'operador.

## 📌 Font de veritat: el CODI (la documentació pot quedar desfasada)

> **Mentre hi hagi un refactor en curs, els `.md` poden quedar desactualitzats en
> qualsevol moment.** No és un error: és l'estat normal. Sempre que dubtis, mana
> el codi i els tests.

- Cap `.md` és font de veritat; mana el **codi** (`app/`, `tests/`, `eines/`) i
  l'estat real del repositori i del disc. Si un doc diu una cosa i el codi en fa
  una altra, **el doc és el que s'ha d'actualitzar**.
- Els noms de mòduls, taules, arbres i comandes dels `.md` són **orientatius**;
  comprova'ls al codi abans de confiar-hi.
- **Carpetes locals:** `00PER FER/`, `.opencode/`, `CORPUS/`, `portable/` i
  `temp/` no són font de veritat ni contracte; no les llegeixis per defecte.
- **Excepció:** `docs/REGLES_DE_LA_APP.md` és **contracte**; si el codi no el
  compleix, és un bug. Només es canvia amb OK de l'operador i queda al `CHANGELOG`.

## ⏱️ Primers 5 minuts (Protocol d'arrencada)

1. **`README.md`** — vista de producte: què és i què fa l'app. No és contracte; si
   divergeix, manen aquest fitxer i el codi. Continua amb **aquest fitxer**
   (secció «Abast i flux»).
2. **`docs/REGLES_DE_LA_APP.md`** sencer (l'únic contracte invariant intocable).
3. **Mapeig viu del codi (sense assumir res):**
   * Consulta `DEVELOPING.md` › «Mòduls de l'app» (taula sincronitzada amb el codi per CI).
   * Fes `git status` i `git diff` per veure si hi ha feina a mitges d'un altre agent.
4. **Verificació d'estat:**
   * Executa `make check` (o `python3 -m unittest discover -s tests`).
   * Si la suite no és verda, **atura't i avisa abans de tocar res**.
5. **Per a la tasca concreta:**
   * Localitza el fitxer a editar a `app/` i el seu test a `tests/`.
   * Llegeix el test per entendre el contracte real vigent, no assumeixis el que fa pel nom.


## 📍 Estat actual

No es duplica: viu a **`ROADMAP.md` §2**. Actualitza'l en plegar (reescriure, no
incrementalment). L'historial és al `CHANGELOG.md`.

## 🔴 Regles de l'app

Les regles d'or (1–12 i §13) són invariants. Llegeix `docs/REGLES_DE_LA_APP.md`
abans de tocar codi; s'han de complir als **4 punts** (**edició en viu, visor,
CSV desat i exportació**). Si una funcionalitat xoca amb una regla, es canvia
la funcionalitat (mai la regla); si hi ha conflicte, mana la regla.

**Terminologia de tempo:** **«recalc fix»** = recalcul amb fronteres fixes (no
mou cap frontera; deriva BPM o `N`). **«recalc mòbil»** = recalcul amb **una
sola** frontera compartida mòbil (mou el `fi` del clip seleccionat i l'`ini` del
veí dret, o la simetria esquerra). Mai dues fronteres alhora. Definició
canònica: `docs/REGLES_DE_LA_APP.md` §13.6.

## 🧭 Com es treballa

1. **Diagnòstic primer**: reprodueix el problema abans de canviar res.
2. **Test de regressió per a cada fix**.
3. Comprova les regles als 4 punts.
4. **Documenta** segons la taula de sota.
5. **Commits** descriptius en català; **mai push** i **mai commit** sense ordre.
   Usa `make commit MSG="..."`: afegeix-ho tot, regenera la documentació, passa
   `make commit-check` (compile + lint + docs-check) i només aleshores commiteja
   (si alguna cosa falla, no commiteja). No fa push.
6. Release: només `README.md`, `LICENSE`, `LLICENCIES_TERCERS.md` i les 2 imatges.

### Documentació: què cal tocar

- **Obligatori (ho enforça la suite/CI):** `CHANGELOG.md` per comportament;
  `docs/TIPUS_XIFRAT_ACORDS.md` si toques `xifrat.py`; `docs/ESQUEMA_UI.md`
  (+ regenerar `.html`/`.svg`) si toques GUI; **regenerar** amb `make docs` (vistes, inventari o taula de
  mòduls) si canvien GUI, pins o `app/`; `ROADMAP.md` §2 en plegar.
- **Ideal si queden mentint:** `README.md` (producte), `DEVELOPING.md`
  (entorn/build/CI), `ARBRE_DIRECTORIS.md` (fitxers), docstrings i `docs/recerca/`.
- **Mai sense OK:** `docs/REGLES_DE_LA_APP.md`, `AGENTS.md` i el `CHANGELOG`
  històric.

### Crear documentació nova

- **No crees cap `.md` nou** sense **OK explícit de l'operador**.
- Abans de crear-ne un: ho pot explicar el **codi/docstring**, el `CHANGELOG` o
  un **doc existent**? Si sí, no crees res nou.
- **Una sola font per tema**: si ja hi ha un doc que en parla, amplia'l o
  enllaça-hi; no en crees un de paral·lel ni hi dupliquis el contingut.
- Si un doc queda redundant o desfasat, **s'esborra** (`gio trash`); no es
  conserva «per si de cas».
- Si creus que cal un doc nou, **proposa-ho** (objectiu, abast i lloc) i espera
  l'OK; no el crees per iniciativa pròpia.

**Abans de tancar / abans de pujar:** `make check` sencer (compile + lint +
**suite completa** + docs-check; ~6 min) ha de passar. **Cap agent el llança
sense avisar l'operador i esperar OK.** Si `docs-check` falla, executa
`make docs` i revisa el diff.

**Si commitejas a mà** (sense `make commit`): `git add` primer —l'arbre es
genera amb `git ls-files` i, si no, els fitxers nous surten 🟡—, després
`make docs` i finalment `git commit`.

**Normes de l'operador:** tot en català · paperera sempre (`gio trash`, mai `rm`)
· cap secret al repo · no deixar processos ni temporals · per a diàlegs o menús
de GUI, demana ajuda a l'operador · **control de ratolí/teclat només dins del
guard** (`Agents_IA_i_IDEs/mouse_control_wrapper.sh`), mai `xdotool` directe.

## 🚪 «Tanca sessió» (protocol)

Quan l'operador diu **«tanca sessió»** (o «tanca sessio»), executa això en ordre:

1. **Estat**: `git status --short` i `git diff`. Si hi ha una altra sessió o agent
   actiu (mtimes recents, tests en marxa o canvis que no són teus), **atura't i
   avisa**; no commitegis feina barrejada.
2. **Neteja**: fora processos i temporals/logs locals; paperera sempre
   (`gio trash`, mai `rm`).
3. **Documenta**: `ROADMAP.md` §2 (reescriure, no incrementalment) i
   `CHANGELOG.md` si hi ha canvis de comportament.
4. **Commit**: si hi ha canvis i cap blocatge, `make commit MSG="..."` (fa
   `git add`, `make docs`, `make commit-check` i commit). És l'única ordre que
   autoritza el commit; **mai push**.
5. **Verificació**: `make check` sencer (~6 min) només amb avís previ i OK de
   l'operador. Si no s'ha pogut fer, digues-ho al resum.
6. **Resum final**: què s'ha fet, què queda pendent i estat del repo (commit i
   `git status`).

## 🤖 Subagents i skills (`.opencode/`)

Els subagents d'OpenCode estan configurats a `.opencode/agents/` per repartir la
feina per domini amb un abast tancat. Són **config local (no versionada) i no són
font de veritat**; si la carpeta no hi és, ignora-ho.

| Subagent | Abast |
|---|---|
| `audio-dsp` | Tempo/compàs/graella: `tempo*`, `mapa_tempo`, `tempo_recalc`, `graella`, `metronom`, `beats`, `marcadors`, `limits`. |
| `pipeline` | Anàlisi i export: pipeline Vamp, `postproc`, `xifrat`, paràmetres `.n3`, import `ffmpeg`. |
| `tester` | Només `tests/`: suite, `pyflakes`, ordre aleatori, smoke i regressions. |
| `docs` | Només `.md` i `docs/`: `CHANGELOG`, `ROADMAP`, `AGENTS.md` i regenerar amb `make docs`. |
| `explorer` | Només lectura: cerca símbols i traça fluxos; respon amb `fitxer:línia`. |
| `reviewer` | Només lectura: revisa el diff contra les regles d'or, `pyflakes` i higiene; no edita. |

També hi ha **skills** a `.opencode/skills/` (`audio-tempo`, `flux-dades`,
`regles-app`, `release-higiene`, `suite-tests`) i **comandes** a
`.opencode/command/` (`/estat`, `/qualitat`, `/regles`). Delega al subagent que
correspongui i no ampliïs el seu abast.

### Skills compartides (`opencode.json` › `skills.paths`)

`opencode.json` carrega, a més, les skills de la carpeta compartida
`/mnt/F5EB-8EFE/CARPETA_IA_AGENTS/skills/` (**font canònica; no es copien ací**).
Si una skill xoca amb les regles d'aquest projecte, **manen les regles d'aquest
projecte** (`docs/REGLES_DE_LA_APP.md`).

La rellevant per coordinar-se és **`oc-oc-dialeg`** (avisos GUI entre **pestanyes**
d'OpenCode, un agent per pestanya):

- **Només host Ubuntu** amb X11 (`DISPLAY=:0`); a la VM Debian o al Mac no funciona.
- Ratolí/teclat **només dins del guard** (`Agents_IA_i_IDEs/mouse_control_wrapper.sh`).
- **Canal formal = `LOG_DIALEGS_AGENTS.txt`** (`CODI-N/NNNN` + `.pcc.lock`, append-only).
  La GUI només **avisa**; cap decisió es pren pel xat teclejat.
- El **mapatge pestanya ↔ agent és viu** (1 = primera per l'esquerra): no l'endevinis,
  pregunta a l'operador o mira els títols. Passa `--self M` per no enviar-te a tu mateix.
- Missatge **ASCII, curt (1-3 línies)**; tipat lent + `Enter`; **fire-and-forget**
  (enviar és l'última acció, no esperis resposta en bucle) i **mai clicar enviar/stop**.
- Una sola finestra `OpenCode`: si n'hi ha dues, l'helper agafa la primera (risc
  d'enviar a l'altra instància).

Les **P0** que porta la skill (control d'entrada dins del guard, paperera sempre,
mai `push`, cap secret al repo, català) **manen sobre qualsevol costum local**.
Detall canònic: `CARPETA_IA_AGENTS/AGENTS.md` §0.

## 🔁 Retrocompatibilitat — decisió vigent (2026-11-02, no invariant)

> No és un invariant: es pot revisar amb OK de l'operador.

- **No es prioritza** mantindre formats, camps ni comportaments antics si
  compliquen el model.
- No preguntes per retrocompatibilitat: la resposta per defecte és **no**.
- Un format nou pot **rebutjar** projectes vells amb un error clar; sense migració
  ni lector tolerant.
- **No es destrueix mai un fitxer de l'usuari**: es rebutja sense tocar-lo.
- Tot canvi de format o comportament es documenta al `CHANGELOG` i, si afecta el
  contracte, a `docs/REGLES_DE_LA_APP.md` amb OK de l'operador.

## ⚠️ Paranys coneguts

Vegeu **`DEVELOPING.md` › «Paranys i trampes conegudes»**.

## 🧪 Comandes essencials

Vegeu **`DEVELOPING.md` › «Comandes essencials»** (entorn, app, suite, pyflakes,
smoke, generadors i ordre aleatori).

## 🗺️ On anar per a la resta

- **`README.md`** — vista de producte / punt d'entrada humà: què és i què fa l'app.
- **`ARBRE_DIRECTORIS.md`** — mapa de carpetes i fitxers.
- **`docs/README.md`** — índex de tota la documentació.
- **`DEVELOPING.md`** — entorn, arquitectura, build i CI.
- **`ROADMAP.md`** · **`CHANGELOG.md`** — futur i història.
- Tempo, compàs, graella i reproducció: `docs/REGLES_DE_LA_APP.md` §13 +
  `app/tempo_map.py`, `app/audio_out.py`.

Criteri: pensa com un enginyer de DAW; clics, talls a costures, latència i deriva
de rellotge són bugs de primera. Un músic no llegeix logs: l'app ha d'avisar de
manera visible i desar sempre de forma vàlida i atòmica.
