# CI — els workflows de GitHub Actions

> **2026-10-09 · v0.5.2.** Com funcionen els **5 workflows** de `.github/workflows/`.
>
> **Tots són d'execució MANUAL** (`workflow_dispatch`): cap s'activa sol (ni amb
> tags, ni amb push). Els llances des de GitHub ▸ **Actions** ▸ tries el workflow
> ▸ **Run workflow**. Cap workflow fa `git push` al repositori.

## Resum

| Workflow | Tipus | Què fa | Sortida |
|---|---|---|---|
| **`build-appimage.yml`** | build (Linux) | AppImage x86_64 autocontinguda | **artefacte** (carpeta amb l'AppImage + docs) |
| **`build-windows.yml`** | build (Windows) | paquet portable x64 (MSYS2 + PyInstaller `--onedir`) | **artefacte** (carpeta amb el paquet + docs) |
| **`build-macos.yml`** | build (macOS) | `.app` per a High Sierra 10.13+ (Intel) | **artefacte** (`AUTO_CHORDS-macos.zip`) |
| **`build-all.yml`** | agregador | executa els 3 builds **en paral·lel** | els 3 artefactes alhora |
| **`release.yml`** | release | agafa els **últims artefactes verds** dels 3 SO | **Release esborrany** amb els 3 paquets |

> **Artefacte vs Release**: un *artefacte* és un fitxer temporal (~90 dies) i privat
> que queda a la pàgina de l'execució (Actions ▸ execució ▸ *Artifacts*). Un *Release*
> és la pàgina **pública permanent** (GitHub ▸ Releases).

## 1. Els 3 builds (`build-{appimage,windows,macos}.yml`)

Cada un construeix el paquet del seu SO i el deixa com a **artefacte**. Tots tres
comparteixen l'esquelet: checkout → entorn → compilar els natius Vamp → Python
portable/roda → **tests** → empaquetar → **pujar l'artefacte** → (si falla) pujar
els logs de debug.

- **`build-appimage.yml`** — runner **`ubuntu-22.04`** (marca la glibc mínima de
  l'AppImage). Compila l'host Vamp + plugins, munta el CPython portable + ffmpeg,
  corre els tests i construeix l'**AppImage** (`auto-chords-<sane>-x86_64.AppImage`).
- **`build-windows.yml`** — runner **`windows-2022`**, amb **MSYS2/MINGW64**.
  Compila els natius, fa PyInstaller `--onedir` i prepara el ZIP portable.
- **`build-macos.yml`** — runner **`macos-15-intel`** (l'últim Intel de GitHub
  Actions; disponible fins a l'agost de 2027). Compila els natius **des de font** a
  10.13 i fa el `.app` + `ditto` → ZIP.

> Els 3 tenen **`workflow_call`** a més de `workflow_dispatch`: això els fa
> *reusable* (es poden cridar des d'altres workflows). Ho aprofita **`build-all.yml`**.

## 2. L'agregador (`build-all.yml`)

**Manual.** Crida els 3 builds com a **jobs germans** → GitHub els llança **en
paral·lel**. Un sol clic i tens els **3 artefactes alhora**, a la mateixa execució.
(No fa res més: no crea cap Release.)

## 3. El release (`release.yml`)

**Manual i «intel·ligent»** — **no compila res**. Quan el llances:

1. Per a **cada SO**, busca l'**última execució VERDA** del seu build.
2. En baixa l'**artefacte directament de GitHub Actions**.
3. Deixa un **resum** a la pàgina de l'execució (taula: SO · run# · data · commit).
4. Crea un **Release ESBORRANY** amb els paquets que ha trobat.

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
2. **`release.yml`** → crea l'**esborrany** amb els 3 paquets.
3. Revisa'l a GitHub ▸ **Releases** i clica **Publish release**.

## Notes tècniques

- Runners: **`ubuntu-22.04`** (no 24.04: allà es compila `vamp_host_local` i la seva
  glibc marca l'abast mínim de l'AppImage), **`windows-2022`** i **`macos-15-intel`**.
- Els workflows viuen a `.github/workflows/`; els scripts de build a `eines/`.
- Detall per SO: `docs/ESTAT_MULTI_SO.md`, `docs/PORTABILITAT.md`,
  `docs/PORTABILITAT_WINDOWS.md`, `docs/PLANIFICACIO_MACOS.md`.
- Proves funcionals dels paquets: `docs/PROVES_FUNCIONALS_3SO.md`.
