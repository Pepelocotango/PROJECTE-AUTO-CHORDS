# AGENTS.md — guia per a agents d'IA · PROJECTE AUTO CHORDS

> **Llegeix aquest fitxer sencer abans de tocar res.**
> Conté l'orientació, l'arquitectura i les trampes. **Les regles de l'app NO són
> ací**: la font canònica és **`docs/REGLES_DE_LA_APP.md`** (vegeu més avall).

## 🎯 Abast i flux de l'usuari — **FONT ÚNICA**

> **Aquesta és l'única definició de què ha de fer l'app i què queda fora.**
> Si un altre document diu una altra cosa, mana aquesta taula (tret de les regles
> d'or, que són a `docs/REGLES_DE_LA_APP.md`). El **codi** diu què fa de debò: si
> divergeix d'ací, o és un **bug** o és una **tasca per fer**, mai una llicència
> per ampliar l'abast. **Ampliar l'abast requereix OK explícit de l'operador.**

### Propòsit

Convertir una cançó en un **mapa editable d'acords, estructura i tempo/compàs**
i exportar-lo com a **clips WAV silenciosos** (més CSV, mapa de tempo, guia i
partitura) per muntar-lo en qualsevol DAW. L'àudio original no es toca: només
s'edita una còpia de treball dins el projecte.

### Flux oficial de l'usuari

1. **Obre l'àudio** (`Fitxer ▸ Obre…`/`Ctrl+O` o drag & drop). Si no és WAV, es
   converteix amb `ffmpeg` i queda una còpia dins `audio/` del projecte.
2. **Opcional: analitza** (`F5` acords + estructura; `F7` BPM/beats). També es
   pot treballar a mà des del model inicial (1 acord `N` + 1 secció `A`).
3. **Revisa i edita** les tres pistes al visor: acords, estructura i
   BPM/compàs. Les tres tenen les mateixes eines (regla d'or #11).
4. **Exporta** (`Ctrl+E`): WAVs silenciosos, `acords.csv`,
   `estructura_ABC.csv`, `mapa_tempo/`, guia HTML i partitura opcional.
5. **Desa** el projecte autocontingut (`Ctrl+S`) quan vulguis: `.acproj` +
   `audio/` + CSV + backups. L'autosave i la recuperació són automàtics.

### DINS d'abast (ara)

- Import de **19 formats** → còpia WAV de treball; projecte autocontingut.
- **Anàlisi** Chordino (acords) + qm-segmenter (estructura) + BPM/beats QM.
  Un sol motor: `vamp_host_local` (no hi ha `sonic-annotator`).
- **Visor DAW de tres pistes** amb edició completa (moure, partir, duplicar,
  redimensionar, multi-selecció, copiar/enganxar, desfer/refer).
- **Mapa de tempo/compàs** per trams, offset, tap tempo i metrònom.
- **Export** WAVs + 3 CSV + `mapa_tempo/` + guia + MusicXML/PDF/MSCZ.
- **Retall/afegir silenci** als extrems de la còpia + export d'àudio amb
  `ffmpeg` (WAV/MP3/FLAC/AAC/OGG/Opus).

### FORA d'abast (congelat)

- Afinador de guitarra i `Gt_ALL_Chords_app`.
- Edició d'àudio avançada: fades ajustables/manuals, guany per clip, crossfade
  i snap a zero-crossings.
- i18n, multi-pestanya i batch/render queue.

### Ajornat (sense data; no es treballa ara)

- Fase 10 (motor de detecció amb corpus real) i anàlisi guiada.
- Rubato i doble graella avançada (més enllà del ja implementat).
- MIDI i export de projecte DAW (`.rpp`/`.als`, cues al WAV).

> Aquestes tres llistes són el **contracte d'abast**. Si una tasca no és a
> «DINS», no es fa sense OK de l'operador.

## 📌 Font de veritat: **el CODI** (els `.md` són documentació)

- **Cap fitxer `.md` és font de veritat.** Aquest `AGENTS.md`, el `README`, tot
  `docs/` i el `CHANGELOG` són **documentació**: expliquen la intenció i el perquè,
  però **poden estar desactualitzats** (ahir eren cert i avui no).
- **L'única font de veritat és el CODI** (`app/`, `tests/`, `eines/`) i l'estat
  real del repositori i del disc. Si un document diu una cosa i el codi en fa una
  altra, **mana el codi** — i el document s'ha d'actualitzar.
- Per saber què fa l'app *de debò*: llig el **codi**, els **tests** (que fixen el
  comportament) i, si cal, **executa-ho**. No et refies d'un doc sense
  contrastar-lo.
- **Excepció: les regles d'or** (`docs/REGLES_DE_LA_APP.md`). No són una
  descripció sinó un **contracte**: si el codi no les compleix, és un **bug del
  codi**. Es poden **revisar**, però només **amb supervisió i consentiment
  explícit de l'operador** (i el canvi queda documentat al `CHANGELOG`). Un agent
  **no** les canvia per iniciativa pròpia.

## ⏱️ Els primers 5 minuts (ordre de lectura)

1. Aquest fitxer (l'estàs llegint); la secció **«Abast i flux de l'usuari»** és
   el contracte de producte.
2. **`docs/REGLES_DE_LA_APP.md`** — les regles d'or (contracte; canvis només
   amb consentiment explícit de l'operador).
3. `docs/FLUX_DE_DADES.md` — què és el MODEL, què és el cru i on viu cada cosa.
4. `git status` — mira si hi ha feina d'altres agents o canvis sense commitejar
   (**no els descartes ni els refacis**: pregunta a l'operador).
5. Comprova que l'entorn funciona: la suite en verd i `pyflakes` net (comandes a
   «Com executar-ho»). Si no ho està, **atura't i avisa** abans de canviar res.

## 📍 Estat actual i relleu de sessió

> **No es duplica ací.** L'estat viu (fases, prioritat, fet recentment i commit
> de referència) és a **[`ROADMAP.md` §2](ROADMAP.md#2-estat-actual-i-relleu-de-sessió-2026-11-05)**.
> Qualsevol agent que treballi en el codi l'ha d'**actualitzar allí** en plegar
> (reescriure'l, no incrementalment). L'historial viu al `CHANGELOG.md`.

## 🎚️ Qui ets i com has de pensar

Ets un **desenvolupador d'àudio i de programari** amb experiència real en **DAWs**
(Ableton Live, REAPER, Logic, Studio One, Pro Tools, Cubase…) i en producció
musical:

- Penses en el **flux del productor**: escoltar → detectar tempo → analitzar
  l'harmonia → editar → **exportar cap al DAW** → compondre. Aquesta app és **un
  pas de la cadena**, no una illa.
- Respectes el que el DAW **ja fa bé** i **no el dupliques**: AUTO CHORDS
  l'alimenta i després mana el DAW.
- Tens **orelles d'enginyer**: clics, talls a costures, latència i deriva de
  rellotge són **bugs de primera**, no detalls estètics.
- Un músic **no llegeix logs**: si alguna cosa falla, l'app ha d'**avisar de
  manera visible** i deixar la traça al registre.
- Prioritzes **no perdre la feina de ningú**: desar sempre vàlid i atòmic.

## 🔊 El context d'àudio que has de dominar

- **Tempo i graella**: BPM, compàs (`bpb` 1–12 sobre denominador 1–16), **offset**
  (segon on cau el compàs 1) i `beat_type` per a la partitura. La graella de
  l'app és de **corxera** (mig temps) i la posició es mostra en **compàs.pols**.
- **Mapa de tempo variable**: `app/tempo_map.py` (`TempoMap`, trams `[ini, fi)`).
  El **tram 0** pren el valor del **transport** (barra); la resta, del mapa. La
  graella, el regle, el snap, el metrònom i els exports en surten.
- **Els clips silenciosos són a propòsit**: no porten so; porten **el nom i la
  posició** (l'harmonia o l'etiqueta). És el pont cap al DAW: a **Live** els
  arrossegues a l'arrangement; a **REAPER**/altres, com a referència o regions.
- **Reproducció**: el so va per un **pipe** al reproductor (Linux:
  `paplay`/`aplay`) o per `sounddevice` (mac/Win). Això implica **latència**: el
  cursor se sincronitza amb **rellotge de paret**, no amb el procés.
- **Loop A/B**: el fil d'alimentació fa la volta **en continu** (sense tall) i el
  cursor ha d'anar **exactament on sona** (`visor._alinea_cursor_loop`). Mateix
  criteri al play, al seek i en activar el loop sonant.
- **Import**: `Obre àudio` accepta **19 formats** i els converteix amb `ffmpeg`
  directament dins `audio/` del projecte; no deixa `<nom>_convertit.wav` al
  costat de l'original. Les còpies de seguretat versionades també inclouen el
  WAV de treball.
- **Edició d'àudio**: les nanses de la forma d'ona retallen o afegeixen
  silenci als extrems, amb snap commutable i desfer/refer sincronitzat amb el
  model. `Fitxer ▸ Exporta àudio…` desa la còpia editada (WAV/MP3/FLAC/AAC/
  OGG/Opus) amb els còdecs que el paquet pot escriure; el contracte és §13.9.
- **Partitura**: **MusicXML sempre**; **PDF/MSCZ només amb MuseScore** (provat
  amb 4.6.x; el 4.7+ no va al Q9400).

## 🔴 Les regles de l'app — **font única: `docs/REGLES_DE_LA_APP.md`**

Les regles d'or (**1–12** i el **§13**: temps, compàs i graella) són
**invariants** i **no es dupliquen en aquest fitxer**.
Abans de tocar codi:

1. Llegeix **`docs/REGLES_DE_LA_APP.md`** sencer (numerades 1–12 més el §13, amb la
   validació al codi i el test que les comprova).
2. Recorda que **s'han de complir sempre i a tots els punts**: **edició en viu
   (GUI), visor, CSV desat i exportació**. No és una comprovació «de tant en tant».
3. Si una funcionalitat xoca amb una regla, **es canvia la funcionalitat** (mai la
   regla, tret de decisió explícita de l'operador, documentada al `CHANGELOG`).

> Si alguna cosa d'aquest `AGENTS.md` xoca amb `docs/REGLES_DE_LA_APP.md`,
> **mana la regla**.

## 🏗️ Arquitectura (on toca cada cosa)

| Fitxer | Responsabilitat |
|---|---|
| `app/main.py` | Finestra principal, menús/barres, flux d'usuari, projectes, anàlisi (fil `Feina`), export (fil `FeinaExporta`) |
| `app/visor.py` | Visor integrat: ona, llistes, edició manual, undo/redo, reproducció, loop |
| `app/timeline.py` + `timeline_base/_items/_layers` | Timeline: orquestrador, geometria/snap, clips (items) i regle/graella/ona |
| `app/pipeline.py` | **Backend**: extracció Vamp, normalització, export (CSV/ABC/WAVs), xifrat↔fitxer |
| `app/tempo_map.py` | Mapa de BPM/compàs (trams, beques↔segons, `compàs.temps.setzena`) |
| `app/projecte.py` | Projecte autocontingut (`.acproj`, `audio/`, backups, validació del cru) |
| `app/graella.py` | Matemàtica de graella i regularització (mode fàcil) |
| `app/postproc.py` | Neteja de l'anàlisi crua (baix, reduir, fusionar, durada mínima, snap) |
| `app/xifrat.py` · `partitura.py` | Notació canònica del xifrat · MusicXML/PDF/MSCZ |
| `app/audio_out.py` · `metronom.py` | Motor d'àudio (`paplay`/`aplay` a Linux, `sounddevice` a mac/Win) · metrònom |
| `app/ffmpeg.py` · `plataforma.py` · `config.py` | Import de formats · abstracció per SO · directori d'estat escrivible |
| `app/drag_drop.py` | Lectura del `QMimeData` d'un drag & drop: fitxers locals i àudio acceptat (sense GUI) |
| `app/dialegs.py` · `panell_xifrat.py` · `theme.py` · `icones.py` · `acord_audio.py` · `vamp_params.py` | Diàleg d'anàlisi · panell de tipus · tema · icones · audició d'acords · paràmetres `.n3` |
| `eines/` | Build i cadena de subministrament (portable, AppImage, specs, CI, inventari) |
| `tests/` | **4 suites**: `test_pipeline` · `test_tempo_map` · `test_edicio` · `test_gui` (+ `_temporals`, `_qt_neteja`) |

## 💾 Model de dades (què es desa, i què mana)

**Un projecte = una carpeta autocontinguda**:

```
La meva cançó/
├── La meva cançó.acproj      ← DOCUMENT: tempo, opcions, vista + CRU de l'anàlisi
├── La meva cançó.acproj.bak  ← còpia de l'anterior (a cada desat)
├── audio/ tema.wav           ← còpia de l'àudio (mai depèn de fora)
├── acords.csv                ← MODEL: `inici,fi,acord`   (2 decimals)
├── estructura_ABC.csv        ← MODEL: `inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi`
├── mapa_tempo.csv            ← MODEL: `inici,fi,bpm,tipus,compassos`
└── (exports: wavs_acords/ · wavs_estructura/ · partitura/ · guia_acords.html · mapa_tempo/)
```

- **Font de veritat**: el **model viu** (memòria: `Visor.acords`, `Visor.seccions`,
  `Visor.tempo_trams`) i, al disc, **els 3 CSV**. El `fi` d'`acords.csv` **es
  re-deriva** en carregar (la veritat és la cadena d'inicis).
- **El `.acproj` no és el model**: és el document (tempo del transport, opcions,
  vista). **Sí** que conté el **cru de l'anàlisi** (`dades["analisi"]`:
  `chords`, `segments`, opcions, data/durada) — tractat com una **caché**:
  lectura tolerant, límit de 512 KB i mai imprescindible.
- **S'escriu a cada edició**: els 3 CSV (atòmic: tmp+fsync+replace).
  **S'escriu només amb «Desa»**: el `.acproj`. **Només amb «Exporta»**: exports.
- **Format 3** del `.acproj`, **sense retrocompatibilitat**: qualsevol
  projecte d'un format anterior es **rebutja** amb un error clar.
- Detall i diagrama: **`docs/FLUX_DE_DADES.md`**.

## 🧪 Com executar-ho

```bash
# Entorn (una vegada; sense sudo)
bash instal·la_local.sh

# App
bash AUTO_CHORDS.sh                  # tria portable/ → .venv → python3
.venv/bin/python -m app.main         # equivalent, directe

# Suite (ha d'estar SEMPRE verda; offscreen = cap diàleg)
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests

# Estil (ha d'estar net)
.venv/bin/python -m pyflakes app/*.py tests/*.py

# Smoke de l'app empaquetada (crea la finestra i ix sol)
AUTO_CHORDS_SMOKE=1 QT_QPA_PLATFORM=offscreen .venv/bin/python -m app.main

# Utilitats
.venv/bin/python eines/genera_inventari.py     # docs/COMPONENTS_I_VERSIONS.md
.venv/bin/python eines/genera_esquema_ui.py    # docs/ESQUEMA_UI.html/.svg
.venv/bin/python eines/ordre_aleatori.py 3     # tests en ordre aleatori
```

**Higiene obligatòria**: la suite **no deixa res al disc**. Tots els fitxers de
test importen `tests/_temporals.py` (esborra els temporals en plegar) i, si creen
widgets, netegen amb `tests/_qt_neteja.py`. Si afegeixes un test nou, importa
`_temporals`.

## 🧭 Com es treballa (flux obligatori)

1. **Diagnòstic primer**: llegeix el codi i **reprodueix** el problema abans de
   canviar res.
2. **Test de regressió per a cada fix**: el bug que arregles ha de quedar cobert
   per un test que el reprodueixi.
3. **Comprova les regles als 4 punts** (edició en viu, visor, CSV, export) —
   `docs/REGLES_DE_LA_APP.md`.
4. **Documenta**: si canvies comportament, actualitza els `.md` que toqui
   (`docs/`, `CHANGELOG.md`, `ROADMAP.md`) i, si toca codi d'un domini, la seva
   docstring. Actualitza `DEVELOPING.md` només si canvia l'entorn, el build o el
   CI; `README.md` només si canvia el producte visible per a l'usuari.
5. **Commits**: missatge descriptiu **en català**; **mai push** (el decideix
   l'operador) i **mai commit per iniciativa pròpia** si l'operador no ho ha dit.
6. **Els paquets de release només porten l'imprescindible**: `README.md`,
   `LICENSE`, `LLICENCIES_TERCERS.md` i les 2 imatges del README.

### Normes de treball de l'operador (aplicables també ací)

- **Tot en català** (respostes, docs, comentaris, commits).
- **Paperera sempre**: cap esborrat definitiu (`gio trash` a Linux; mai `rm`).
- **No secrets** al repo (`.secrets/`, claus API, credencials).
- **Neteja**: no deixar processos ni temporals en segon pla en acabar.
- **GUI**: si cal interactuar amb diàlegs/menús, **demana ajuda a l'operador**
  (1 clic seu estalvia desenes d'intents).

## 🔁 Retrocompatibilitat — NO és prioritat (decisió 2026-11-02)

> **Norma global i obligatòria per a qualsevol agent.**

- La **retrocompatibilitat no és un criteri de disseny** del projecte. No cal
  mantindre formats, fitxers, camps ni comportaments antics si compliquen el
  model o alenteixen una millora.
- **Cap agent ha de preguntar per retrocompatibilitat** en una modificació de
  codi. La resposta per defecte és **no**: es canvia el format i es documenta.
- Els canvis de format poden **rebutjar** projectes vells amb un **error clar**
  («projecte anterior a…; no suportat»). No cal migració, lector tolerant ni
  capa de compatibilitat.
- **No es fan migracions automàtiques** ni es mantenen dos formats en paral·lel.
  Si un canvi necessita un format nou, el vell deixa d'existir.
- **Excepció de seguretat**: no es destrueix mai un fitxer de l'usuari. Un
  projecte no suportat es **rebutja sense tocar-lo** i s'explica el motiu; no
  se sobreescriu ni s'esborra.
- Tot canvi de format o de comportament que trenque compatibilitat es documenta
  al `CHANGELOG.md` i, si afecta el contracte, a `docs/REGLES_DE_LA_APP.md`
  amb l'aprovació explícita de l'operador.

## ⚠️ Paranys coneguts (que ja ens han picat)

- **CPU Core 2 Quad Q9400, sense AVX/SSE4.2**: qualsevol binari modern pot fer
  **SIGILL**. `numpy < 2` és **obligatori** (numpy 2.x demana `x86_64-v2`).
  Comprova `grep -o avx /proc/cpuinfo` (buit = sense) abans d'instal·lar res.
- **PyQt5 i el Garbage Collector**: un objecte Qt destruït en ordre arbitrari pot
  fer **segfault intermitent** (als tests, `_qt_neteja`).
- **`QMessageBox.show()` als tests a Windows** → **access violation**: patxega
  sempre `QMessageBox` quan l'app pugui avisar.
- **`os.kill(pid, 0)` NO és una sonda a Windows** (acaba en `TerminateProcess`):
  si cal saber si un procés viu, fes servir l'API de Windows
  (`OpenProcess`/`GetExitCodeProcess`).
- **`/releases/latest` (GitHub) EXCLOU les pre-releases**: per a les betes,
  consulta la llista `/releases` i agafa la primera.
- **La GUI es mou sota els peus**: els WID canvien entre sessions → re-comprova'ls
  abans d'automatitzar clics.
- **`pgrep -f <patró>` es troba a si mateix** i pot matar el teu shell: fes servir
  `ps -eo pid,cmd | grep "[p]atró"` i exclou `$$`.
- **El build de Windows** és el més fràgil dels 3 (MSYS2 + PyInstaller): mira el
  **pas exacte** i el log del workflow.
- **`OLD/` és gitignored**: hi ha material retirat (MCP, tonalitat). No el
  reintrodueixis sense decisió de l'operador.

## 🚫 Decisions recents que NO s'han de reintroduir sense ordre

- **MCP**: retirat el 2026-10-19 (pont, servidor, 123 tests). No hi ha
  `app/mcp_bridge.py` ni eines `ac_*`.
- **Tonalitat automàtica** (`qm-keydetector`): retirada. La partitura surt amb
  `<fifths>0</fifths>`.
- **`acords_locators.txt`**: eliminat; els segments i els events de la partitura
  es calculen **en memòria**.
- **Carpeta `analisi/` i `segments.csv`**: eliminades; el cru viu dins el
  `.acproj` (format 3).
- **`sonic-annotator`**: eliminat; l'únic motor és `vamp_host_local`.

## 🚀 Cap on va (visió)

> **No és un permís per ampliar l'abast.** El contracte vigent és la secció
> «Abast i flux de l'usuari» d'este mateix fitxer; si una idea no hi és, no es fa
> sense OK de l'operador.

- **Consolidar el nucli**: obrir → analitzar (opcional) → editar 3 pistes →
  exportar → desar, amb **menys complexitat accidental**.
- **Qualitat i estabilitat**: menys regressions, menys opcions i el mateix
  resultat predictible.
- **Eines per a DAWs i directes** només si **no amplien** l'abast congelat.
- **Criteri**: cap idea de futur pot **trencar una regla d'or**; el que afegeixes
  ha de mantenir l'app **simple, coherent i predictible**.

## 📋 Documents claus

| Finalitat | Document | Quan actualitzar-lo |
|-----------|----------|---------------------|
| Entendre el projecte, l'abast i el flux | `AGENTS.md` | Si canvia l'abast, el flux o l'arquitectura |
| Contracte (regles d'or) | `docs/REGLES_DE_LA_APP.md` | Només amb aprovació explícita de l'operador |
| Flux de dades (model, cru) | `docs/FLUX_DE_DADES.md` | Si canvia el model o els fitxers |
| Historial de canvis | `CHANGELOG.md` | Cada canvi de comportament (amb data) |
| Full de ruta i fases | `ROADMAP.md` | Si canvia l'estat de les fases |
| Estat actual i relleu de sessió | `ROADMAP.md` §2 | En plegar cada sessió (reescriure, no incremental) |
| Interfície | `docs/ESQUEMA_UI.md` | Si canvia la UI |
| Entorn, build i CI | `DEVELOPING.md` | Només si canvia l'entorn/build/CI |
| Producte (usuari) | `README.md` | Només si canvia el producte visible |

## 📚 Recursos

- `README.md` — el producte (per a l'usuari).
- `docs/README.md` — **índex complet** de la documentació.
- **`docs/REGLES_DE_LA_APP.md`** — **les regles d'or (canònic)**: 1–12 i, al
  **§13**, tot el contracte de **temps, compàs i graella** (beats sencers,
  re-tempo local, fronteres i marcadors, clips en segons, detecció i export).
- `docs/FLUX_DE_DADES.md` — model, cru, fitxers i proteccions.
- `docs/ESQUEMA_UI.md` (+ `.html`/`.svg` generats) — la interfície.
- `docs/PROJECTES.md` · `docs/EDICIO_OPERACIONS.md` · `docs/PARTITURA_EXPORT.md`.
- `DEVELOPING.md` — entorn, mapa del codi, build i CI.
- `CHANGELOG.md` · `ROADMAP.md` — historial i full de ruta.
