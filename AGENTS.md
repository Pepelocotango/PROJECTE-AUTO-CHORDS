# AGENTS.md — guia per a agents d'IA · PROJECTE AUTO CHORDS

> **Primera lectura:** aquest fitxer + els 3 fitxers de «Primers 5 minuts».
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
tempo, guia i partitura) per muntar-lo en qualsevol DAW. L'àudio original no es
toca: només s'edita una còpia de treball dins el projecte.

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
- **Mapa de tempo/compàs** per trams, offset, tap tempo i metrònom.
- **Export** WAVs + CSV + `mapa_tempo/` + guia + MusicXML/PDF/MSCZ.
- **Retall/afegir silenci** als extrems + export d'àudio amb `ffmpeg`.

**FORA d'abast (ara; decisió vigent, no invariant):** afinador i
`Gt_ALL_Chords_app`; edició avançada (fades manuals, guany per clip, crossfade,
snap a zero-crossings); i18n, multi-pestanya i batch/render queue.

**Ajornat (sense data):** fase 10 (motor de detecció amb corpus real) i anàlisi
guiada; rubato i doble graella avançada; MIDI i export de projecte DAW.

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

## ⏱️ Primers 5 minuts

1. Aquest fitxer (secció «Abast i flux»).
2. **`docs/REGLES_DE_LA_APP.md`** sencer (1–12 + §13).
3. **`app/projecte.py`** i **`app/pipeline_model.py`** (model, cru i clips);
   `ARBRE_DIRECTORIS.md` si necessites orientar-te.
4. **`git status`**: no descartes ni refaces feina d'altres agents.
5. Suite verda i `pyflakes` net (comandes a `DEVELOPING.md`). Si no ho estan,
   **atura't i avisa**. Si la falla és d'un **refactor en curs d'un altre agent**,
   no l'arreglis sense OK: distingeix-la de la teva feina.

## 📍 Estat actual

No es duplica: viu a **`ROADMAP.md` §2**. Actualitza'l en plegar (reescriure, no
incrementalment). L'historial és al `CHANGELOG.md`.

## 🔴 Regles de l'app

Les regles d'or (1–12 i §13) són invariants. Llegeix `docs/REGLES_DE_LA_APP.md`
abans de tocar codi; s'han de complir als **4 punts** (**edició en viu, visor,
CSV desat i exportació**). Si una funcionalitat xoca amb una regla, es canvia la
funcionalitat (mai la regla); si hi ha conflicte, mana la regla.

## 🧭 Com es treballa

1. **Diagnòstic primer**: reprodueix el problema abans de canviar res.
2. **Test de regressió per a cada fix**.
3. Comprova les regles als 4 punts.
4. **Documenta** segons la taula de sota.
5. **Commits** descriptius en català; **mai push** i **mai commit** sense ordre.
6. Release: només `README.md`, `LICENSE`, `LLICENCIES_TERCERS.md` i les 2 imatges.

### Documentació: què cal tocar

- **Obligatori (ho enforça la suite/CI):** `CHANGELOG.md` per comportament;
  `docs/TIPUS_XIFRAT_ACORDS.md` si toques `xifrat.py`; `docs/ESQUEMA_UI.md`
  (+ regenerar `.html`/`.svg`) si toques GUI; `docs/EDICIO_OPERACIONS.md` si
  toques edició; **regenerar** amb `make docs` (vistes, inventari o taula de
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

**Abans de tancar:** `make lint`, `make test` i `make docs-check` han de passar.
Si `docs-check` falla, executa `make docs` i revisa el diff.

**Normes de l'operador:** tot en català · paperera sempre (`gio trash`, mai `rm`)
· cap secret al repo · no deixar processos ni temporals · per a diàlegs o menús
de GUI, demana ajuda a l'operador.

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

- **`ARBRE_DIRECTORIS.md`** — mapa de carpetes i fitxers.
- **`docs/README.md`** — índex de tota la documentació.
- **`DEVELOPING.md`** — entorn, arquitectura, build i CI.
- **`ROADMAP.md`** · **`CHANGELOG.md`** — futur i història.
- Tempo, compàs, graella i reproducció: `docs/REGLES_DE_LA_APP.md` §13 +
  `app/tempo_map.py`, `app/audio_out.py`.

Criteri: pensa com un enginyer de DAW; clics, talls a costures, latència i deriva
de rellotge són bugs de primera. Un músic no llegeix logs: l'app ha d'avisar de
manera visible i desar sempre de forma vàlida i atòmica.
