# CI — els workflows de GitHub Actions

> **2026-10-13 · v0.6.2.** Com funcionen els **5 workflows** de `.github/workflows/`.
>
> **Tots són d'execució MANUAL** (`workflow_dispatch`): cap s'activa sol (ni amb
> tags, ni amb push). Els llances des de GitHub ▸ **Actions** ▸ tries el workflow
> ▸ **Run workflow**. Cap workflow fa `git push` al repositori.
>
> _(Actualitzat 13-10 amb l'enduriment de l'auditoria de producció: builds
> reproduïbles, `concurrency`/`timeout`, verificació de contingut i
> smoke tests — vegeu §4.)_
>
> _(14-10-2026: **retirat Dependabot** per decisió de l'operador — els pins són
> **deliberats** per compatibilitat (Q9400 sense AVX, macOS 10.13, roda de Windows)
> i Dependabot obria PRs perjudicials (p. ex. `pyqt5-qt5` 5.15.19 trencaria
> Windows; `cffi` 2.1.1 trencaria macOS 10.13). Les dependències i les accions
> s'actualitzen **a mà**, amb validació al CI.)_

## Resum

| Workflow | Tipus | Què fa | Sortida |
|---|---|---|---|
| **`build-appimage.yml`** | build (Linux) | AppImage x86_64 autocontinguda | **artefacte** `.tar.gz` (AppImage + docs) |
| **`build-windows.yml`** | build (Windows) | paquet portable x64 (MSYS2 + PyInstaller `--onedir`) | **artefacte** `.zip` (`.exe` + `_internal/` + docs) |
| **`build-macos.yml`** | build (macOS) | `.app` per a High Sierra 10.13+ (Intel) | **artefacte** `.dmg` (`.app` + docs) |
| **`build-all.yml`** | agregador | executa els 3 builds **en paral·lel** | els 3 artefactes alhora |
| **`release.yml`** | release | agafa els **últims artefactes verds** (build-all o per build) | **Release PUBLICAT** amb **1 paquet per SO** (+ tag) |

## Noms i formats (canònics per SO)

El CI i el Release fan servir el **mateix patró**: **un sol paquet per SO** amb
**l'executable + els docs a dins**.

| SO | Fitxer | Format | Contingut |
|---|---|---|---|
| 🐧 **Linux** | `AutoChords-<versió>-build<NN>-linux-x86_64.tar.gz` | **`.tar.gz`** (tarball binari) | `AutoChords-<versió>-x86_64.AppImage` + docs |
| 🪟 **Windows** | `AutoChords-<versió>-build<NN>-win-x64.zip` | **`.zip`** (portable) | `AutoChords.exe` + `_internal/` + docs (a l'arrel) |
| 🍎 **macOS** | `AutoChords-<versió>-build<NN>-macos-x86_64.dmg` | **`.dmg`** (UDZO) | `AUTO_CHORDS.app` + enllaç a `/Applications` + docs |

- Al **CI** el nom porta la versió del `pyproject.toml`; al **Release** es
  re-escriu amb la **versió del tag**. El **número de build** (`<NN>` = número
  d'execució de GitHub) es manté sempre.
- Docs inclosos: `README.md`, `CHANGELOG.md`, `ROADMAP.md`, `LICENSE`,
  `LLICENCIES_TERCERS.md` i `docs/`.

> **Artefacte vs Release**: un *artefacte* és un fitxer temporal i privat que queda a
> la pàgina de l'execució (Actions ▸ execució ▸ *Artifacts*). **El projecte els guarda
> 30 dies** (`retention-days: 30` als 3 builds) → per tant, passats 30 dies cal tornar
> a compilar abans de poder fer un Release. Un *Release* és la pàgina **pública
> permanent** (GitHub ▸ Releases).

## 1. Els 3 builds (`build-{appimage,windows,macos}.yml`)

Cada un construeix el paquet del seu SO i el deixa com a **artefacte**. Tots tres
comparteixen l'esquelet: checkout → cau de baixades → entorn → compilar els natius
Vamp → Python (dependències **des de `requirements-build.txt`**, amb pins `==`) →
**tests (suite completa: `python -m unittest discover -s tests`)** → empaquetar →
**verificar el contingut del paquet** → **smoke test del paquet** → **pujar
l'artefacte** → (si falla) pujar els logs de debug. Els 5 workflows tenen
**`concurrency`** (no se solapen) i **`timeout-minutes`** (límits d'execució).

- **`build-appimage.yml`** — runner **`ubuntu-22.04`** (marca la glibc mínima de
  l'AppImage). Compila l'host Vamp + plugins, munta el CPython portable + ffmpeg,
  corre els tests, construeix l'**AppImage** i en fa un **smoke test** (pas **9b**:
  `--appimage-extract` + execució headless amb `AUTO_CHORDS_SMOKE=1`). S'empaqueta
  en un **`.tar.gz`** (`AutoChords-<versió>-build<NN>-linux-x86_64.tar.gz`) amb
  l'AppImage (`AutoChords-<versió>-x86_64.AppImage`) i els docs, i es **verifica el
  contingut** (pas 10: hi han de ser l'AppImage, `README.md` i `LICENSE`).
- **`build-windows.yml`** — runner **`windows-2022`**, amb **MSYS2/MINGW64**.
  Compila els natius, fa PyInstaller `--onedir` i prepara el **`.zip` portable**
  (`AutoChords-<versió>-build<NN>-win-x64.zip`) amb `AutoChords.exe` (+ `_internal/`)
  i els docs **a l'arrel** (sense carpetes del CI a dins). **Verifica el contingut**
  del `.zip` (pas 10: hi han de ser `AutoChords.exe`, `README.md` i `LICENSE`) i els
  **tests van ABANS de pujar l'artefacte** (11 → 12, **sense** `if: always()`): no es
  pot descarregar un paquet que no ha passat la suite.
- **`build-macos.yml`** — runner **`macos-15-intel`** (l'últim Intel de GitHub
  Actions; disponible fins a l'agost de 2027). Compila els natius **des de font** a
  10.13, fa el `.app` amb PyInstaller i aleshores: (6b) **verifica el `minos`
  de TOTS els Mach-O del bundle** (fatia x86_64 ≤ 10.13, amb
  `eines/verifica_minos_macos.py`), (6c) **smoke test** — executa l'`.app`
  empaquetada en mode headless (`offscreen`) i comprova que arrenca de debò —,
  (7) un `.zip` (`ditto`) de comprovació (no es publica) i (7b) el **`.dmg`**
  (`AutoChords-<versió>-build<NN>-macos-x86_64.dmg`, `hdiutil`, amb l'`.app`, un
  enllaç a `/Applications` i els docs; muntat i verificat). L'artefacte és
  **només el `.dmg`**.

> Els 3 tenen **`workflow_call`** a més de `workflow_dispatch`: això els fa
> *reusable* (es poden cridar des d'altres workflows). Ho aprofita **`build-all.yml`**.

## 2. L'agregador (`build-all.yml`)

**Manual.** Crida els 3 builds com a **jobs germans** → GitHub els llança **en
paral·lel**. Un sol clic i tens els **3 artefactes alhora**, a la mateixa execució.
(No fa res més: no crea cap Release.) Té **`concurrency`** (si se'n llança un mentre
corre un altre, espera — no se solapen) i **`timeout-minutes`** per job (60/60/90).

## 3. El release (`release.yml`)

**Manual i «intel·ligent»** — **no compila res**. Quan el llances:

1. Busca l'**última execució VERDA** de l'agregador **`build-all`** (els 3 SO
   alhora) i, si no n'hi ha cap, l'**última verda de cada build** solt.
2. En baixa l'**artefacte directament de GitHub Actions**.
3. Deixa un **resum** a la pàgina de l'execució.
4. Crea el **Release PUBLICAT** (i el **tag**) amb els paquets que ha trobat.
   Si el Release ja existia com a esborrany, el **publica** (`--draft=false`).

Detalls:
- **Tag/versió**: si el poses com a *input*, l'usa; si el deixes buit, el calcula
  com **`v<versió de pyproject.toml>`**.
- **Robust**: si un SO **no** té cap build verd, l'**omet i avisa** (no peta); només
  s'atura si **no n'hi ha cap** dels 3.
- **Idempotent**: si el Release ja existeix, només hi **adjunta/actualitza** els fitxers.
- Les **notes** surten de **`CHANGELOG.md`** (via `eines/notes_release.py`).
- El nom de l'execució és dinàmic (`run-name`): **«Publicar Release <tag>»**.
- Permisos del token: `contents: write` (crear el Release) + `actions: read` (baixar
  artefactes d'altres execucions).
- **`concurrency`** (un Release alhora) i **`timeout-minutes: 30`**.
- **Avis de tag existent** (A.6): si el tag/Release ja existeix, surt un
  `::warning::` (el flux segueix sent idempotent) → ajuda a detectar que s'ha
  oblidat pujar la versió de `pyproject.toml`.

## 4. Reproduïbilitat i manteniment

- **Builds reproduïbles**: les dependències Python dels builds (Windows i macOS)
  s'instal·len des de **`requirements-build.txt`** (`-r requirements.txt` +
  `pyinstaller==6.22.3`), tot amb pins `==`. Abans s'instal·laven amb specs soltes
  (`numpy<2`, `PyQt5-sip`, `sounddevice` i `pyinstaller` **sense pin**) → podien
  derivar entre execucions.
- **Manteniment — A MÀ** (14-10-2026): **Dependabot RETIRAT** per decisió de
  l'operador. Els pins (`requirements*.txt`, `pyproject.toml` i les accions) són
  **deliberats** per compatibilitat (Q9400 sense AVX, macOS 10.13, roda Windows) i
  Dependabot obria PRs **perjudicials** (p. ex. `pyqt5-qt5` 5.15.19 trencaria
  Windows; `cffi` 2.1.1 trencaria macOS 10.13). Les actualitzacions es fan **a mà,
  amb validació al CI**.
- **Verificació de contingut**: cada build comprova que el paquet contingui
  l'executable i els docs obligatoris **abans** de pujar-lo.
- **Smoke tests**: Linux (9b, AppImage headless) i macOS (6c, `.app` headless) fan
  **arrencar el paquet de debò**; Windows comprova el contingut del `.zip`.

## Flux típic

1. **`build-all.yml`** (o els 3 builds) → espera que surtin **verds**.
2. **`release.yml`** → **publica** el Release (amb els 3 paquets + el tag).
3. Fet: el Release ja és públic a GitHub ▸ **Releases**.

## Notes tècniques

- Runners: **`ubuntu-22.04`** (no 24.04: allà es compila `vamp_host_local` i la seva
  glibc marca l'abast mínim de l'AppImage), **`windows-2022`** i **`macos-15-intel`**.
- Els workflows viuen a `.github/workflows/`; els scripts de build a `eines/`.
- Detall per SO: `docs/ESTAT_MULTI_SO.md`, `docs/PORTABILITAT.md`,
  `docs/PORTABILITAT_WINDOWS.md`, `docs/PLANIFICACIO_MACOS.md`.
- Proves funcionals dels paquets: `docs/PROVES_FUNCIONALS_3SO.md`.
