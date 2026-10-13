# CI — els workflows de GitHub Actions

> **2026-10-13 · v0.6.2.** Com funcionen els **5 workflows** de `.github/workflows/`.
>
> **Tots són d'execució MANUAL** (`workflow_dispatch`): cap s'activa sol (ni amb
> tags, ni amb push). Els llances des de GitHub ▸ **Actions** ▸ tries el workflow
> ▸ **Run workflow**. Cap workflow fa `git push` al repositori.

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

> **Artefacte vs Release**: un *artefacte* és un fitxer temporal (~90 dies) i privat
> que queda a la pàgina de l'execució (Actions ▸ execució ▸ *Artifacts*). Un *Release*
> és la pàgina **pública permanent** (GitHub ▸ Releases).

## 1. Els 3 builds (`build-{appimage,windows,macos}.yml`)

Cada un construeix el paquet del seu SO i el deixa com a **artefacte**. Tots tres
comparteixen l'esquelet: checkout → entorn → compilar els natius Vamp → Python
portable/roda → **tests (suite completa: `python -m unittest discover -s tests`)** → empaquetar → **pujar l'artefacte** → (si falla) pujar
els logs de debug.

- **`build-appimage.yml`** — runner **`ubuntu-22.04`** (marca la glibc mínima de
  l'AppImage). Compila l'host Vamp + plugins, munta el CPython portable + ffmpeg,
  corre els tests i construeix l'**AppImage**, que s'empaqueta en un **`.tar.gz`**
  (`AutoChords-<versió>-build<NN>-linux-x86_64.tar.gz`) amb l'AppImage
  (`AutoChords-<versió>-x86_64.AppImage`) i els docs a dins.
- **`build-windows.yml`** — runner **`windows-2022`**, amb **MSYS2/MINGW64**.
  Compila els natius, fa PyInstaller `--onedir` i prepara el **`.zip` portable**
  (`AutoChords-<versió>-build<NN>-win-x64.zip`) amb `AutoChords.exe` (+ `_internal/`)
  i els docs **a l'arrel** (sense carpetes del CI a dins).
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
(No fa res més: no crea cap Release.)

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
