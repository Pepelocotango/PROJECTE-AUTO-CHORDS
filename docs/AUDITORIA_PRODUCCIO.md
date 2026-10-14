# Auditoria de PRODUCCIÓ — AUTO CHORDS

> Auditoria de qualitat de **producció** (allò que veu i fa servir l'usuari final),
> feta en paral·lel per **OC-5** i **OC-6** amb permís de l'operador **només per a
> documentació** (zero codi).
>
> - **Commit base:** `75c8f31` (main) · **Versió:** 0.6.2 (BETA) + `CHANGELOG [Unreleased]`
> - **Data:** 2026-10-13
> - **Regla:** cap fitxer de codi tocat; verificat amb `git status` (només `.md`).
> - **Estat final (2026-10-13):** blocs 1–2 de codi (OC-4) i l'ítem **1.6** aplicats ·
>   **HEAD `aac8b26`** — vegeu **«ESTAT FINAL»** més avall.

## Com llegir-ho

| Marca | Significat |
|:---:|---|
| ✅ | **OK** — funciona i està documentat/cobert |
| ⚠️ | **Risc** — funciona però hi ha un problema o una fragilitat a mirar |
| 🕳️ | **Buit** — falta (documentació, test o política) |
| 📝 | **Corregit** en aquesta auditoria (només `.md`) |
| 🔧 | **Cal codi** → passa a **OC-4** (té permís de codi) |

## ✅ ESTAT FINAL (consolidació 2026-10-13 · HEAD `aac8b26`)

Auditoria **tancada**. Tots els ítems de **codi/CI** han estat implementats per **OC-4**
(commits `4f6c8bb` = blocs 1–2, `aac8b26` = 1.6/4.3) i verificats al codi per **OC-6**.
Els ítems de **documentació** (1.2, 2.3, 3.1–3.3) s'han aplicat als `.md`.

| Origen | Ítem | Estat final |
|---|---|:---:|
| OC-6 1.1 | `LICENSE` amb la GPLv3 completa | ✅ FET (674 línies) |
| OC-6 1.2 | Unificar llicència → `GPL-3.0-or-later` | ✅ FET (README/ROADMAP/DEVELOPING) |
| OC-6 1.4 | Pins a `pyproject.toml` | ✅ FET |
| OC-6 1.5 | `XX TEMP FILES USUARI/` fora del git | ✅ FET (gitignore + destrackejat) |
| OC-6 1.6 / 4.3 | Fora els `except` silenciosos + **avís d'àudio VISIBLE** | ✅ FET (`aac8b26` + test) |
| OC-6 2.1 / 2.2 | `instal·la_local.sh`: numeració `/6` + `.desktop` al menú | ✅ FET |
| OC-6 2.3 / 3.1–3.3 | Docs desactualitzats (README venv/eines, DEVELOPING §5, PyQtGraph) | ✅ FET |
| OC-6 2.4 | Tolerància a `apt-get download` | ✅ FET |
| OC-5 A.2 / D.1 | Builds des de `requirements-build.txt` (+ pin `pyinstaller`) | ✅ FET |
| OC-5 A.3 | Verificació de **contingut** dels paquets | ✅ FET |
| OC-5 A.4 | **Smoke test** de l'AppImage | ✅ FET |
| OC-5 A.5 | Windows: **tests abans** de l'upload | ✅ FET |
| OC-5 A.6 | Avís de **tag existent** al Release | ✅ FET |
| OC-5 A.7 / B.4 | `concurrency` + `timeout-minutes` (5 workflows) | ✅ FET |
| OC-5 B.1 / B.2 / D.4 | **Dependabot** (`github-actions` + `pip`) | ⛔ **RETIRAT** (14-10-2026, decisió de l'operador → dependències/accions s'actualitzen **a mà** amb validació al CI; vegeu `docs/CI_WORKFLOWS.md`) |

**Encara oberts (no bloquejants):** 1.3 `--require-hashes` · 1.7 renombrar `deps_fixades.env`
(opcional) · 3.4 índex de `docs/` · 4.1 `coverage` + llindar al CI · 4.2 tests de GUI ·
A.1 (retenció 30 dies, documentat) · A.8 SBOM · A.9 · B.5 · C.1/C.2 (dates límit de runners) ·
D.3 · D.5. Artefacte local detectat: `.coverage` (untracked) → valorar `.gitignore`.

> Els estats de sota de cada secció es conserven com a **fotografia del moment de l'auditoria**.

## Resum per àrea

| Àrea | Qui | Estat global |
|---|---|:---:|
| A. Empaquetat i Release (tar.gz/zip/dmg) | OC-5 | **⚠️** (coherent; riscos d'operació: 30 dies, no reproduïble) |
| B. CI/CD (5 workflows) | OC-5 | **⚠️** (enduriment fort; falta manteniment automatitzat) |
| C. Portabilitat 3 SO | OC-5 | **⚠️** (ben documentat; 2 dates límit + validació real pendent) |
| D. Versions i dependències (pins, inventari, CVE) | OC-5 | **⚠️** (pins+inventari OK; no s'apliquen al build ni revisió CVE) |
| **1. Seguretat i llicències** | **OC-6** | **⚠️** (enduriment fort; 1 forat legal + incoherències) |
| **2. UX + instal·lació local** | **OC-6** | **⚠️** (sòlid; 2 textos de guia i 1 descuit d'instal·lació) |
| **3. Documentació (README/DEVELOPING/docs)** | **OC-6** | **⚠️** (molt completa; 3 punts desactualitzats → corregits) |
| **4. Proves i gestió d'errors** | **OC-6** | **⚠️** (403 tests OK; sense cobertura mesurada ni tests de GUI) |

---

# PART OC-6

## 1. Seguretat i llicències

**Estat: ⚠️** — L'**enduriment és fort i està ben documentat**; el que falla és sobretot
**formal/legal** (fitxer de llicència) i alguna **incoherència** entre fitxers.

### ✅ Què està bé (amb evidència)

- **Enduriment de seguretat de l'app i de la cadena de subministrament**: documentat a
  `docs/SEGURETAT.md` (10 punts) i al `CHANGELOG.md` `[Unreleased] / Seguretat`.
- **Cadena de subministrament verificada**: `eines/baixa_verificat.py` (HTTPS + SHA256 +
  reintents; no deixa res a mitges) sobre `eines/deps_fixades.env` (URL + versió + SHA256
  de tot el que es baixa + *commit* dels repos compilats). Ho cobreix
  `tests/test_baixa_verificat.py` (16 tests).
- **Instància única per usuari**: `os.open(..., O_NOFOLLOW, 0o600)`, uid/nom al nom del
  fitxer (`app/plataforma.py`, `app/main.py`).
- **Pont MCP endurit** (`app/mcp_bridge.py`): fitxer `0600`, límit 1 MiB, màx. 8
  connexions, testimoni validat primer.
- **`safe_filename()`** (`app/pipeline.py`): reservats de Windows + noms reservats +
  desambiguació, amb **test «daurat»**.
- **Temporals** `ac_ttl_`/`ac_qm_`/`ac_key_` netejats sempre (`finally`) i `esborra_tmp()`
  només toca prefixos propis.
- **`SECURITY.md`** (canal de report + política) i **`LLICENCIES_TERCERS.md`** (24
  components, compatibilitats GPL argumentades) + **`icones/LICENSE`** (ISC/MIT) —
  presents i correctes.
- **Pins exactes** a `requirements.txt` + **guarda** `tests/test_requirements.py`
  (prohibeix `numpy>=2` i `PyQt6`).
- **Inventari de components** `docs/COMPONENTS_I_VERSIONS.md` (per vigilar CVE).
- **Sense secrets versionats**: `git ls-files` no conté cap clau/credencial.

### ⚠️ Problemes i recomanacions

| # | Problema | Evidència | Acció |
|---|---|---|---|
| 1.1 | **`LICENSE` és un *stub* de 10 línies** que només enllaça a la URL de la GPLv3 i **NO conté el text complet**. La GPLv3 demana rebre una còpia; a més, el paquet distribuït (tar.gz/zip/dmg) inclou aquest mateix fitxer → l'usuari rep un punter, no la llicència. | `LICENSE:10` («See https://www.gnu.org/licenses/gpl-3.0.txt for full text») | 🔧 **OC-4**: substituir per la GPLv3 completa (o afegir `COPYING`). En ser `.md`-free, no el toco. |
| 1.2 | **Incoherència de llicència** entre fitxers: `GPL-3.0-or-later` (pyproject, LLICENCIES) vs `GPLv3` (README, ROADMAP, DEVELOPING). | `pyproject.toml:10` · `LLICENCIES_TERCERS.md:3` vs `README.md:330` | 🔧 Unificar a **`GPL-3.0-or-later`** (o «GPLv3 o posterior») a tots. |
| 1.3 | **`requirements.txt` sense `--require-hashes`** (documentat com a pendent). | `requirements.txt:28-36` | ⚠️ Acceptat; la protecció actual és el pin `==` + el test guarda. Anotat. |
| 1.4 | **`pyproject.toml` amb rangs** (`PyQt5>=5.15.9`, `numpy>=1.22,<2`) ≠ els pins exactes de `requirements.txt`: instal·lant via `pip install .` es podria arrossegar una PyQt5 més nova. | `pyproject.toml:14-17` | 🔧 Alinear amb els pins de `requirements.txt`. |
| 1.5 | **`XX TEMP FILES USUARI/` parcialment versionat** (`NOTES_RELEASE_v0.5.2.md`) i amb una subcarpeta (`errors auto chords mac`) **no** gitignorada → risc de filtrar notes/errors locals a l'historial. | `git ls-files "XX TEMP FILES USUARI"` | 🔧 Afegir a `.gitignore` + `git rm --cached`. |
| 1.6 | **`except Exception: pass` silenciosos** (àudio i MCP): l'error no arribava a l'usuari. | `app/audio_out.py` · `app/mcp_bridge.py:454` | ✅ **FET** (`aac8b26`): avís **VISIBLE** quan mor el motor d'àudio + fora els `except` silenciosos; `docs/PLAY.md` ja ho marca FET. |
| 1.7 | `eines/deps_fixades.env` versionat amb extensió `.env`: **no és un secret** (URL+SHA), però el patró `.env` s'associa a secrets i pot confondre eines/scanners. | `eines/deps_fixades.env` | ⚠️ Menor; valorar renombrar (p. ex. `eines/deps_fixades.sh`). |

## 2. UX + instal·lació local

**Estat: ⚠️** — El flux d'instal·lació **sense sudo** està ben resolt; hi ha **una
incoherència visible** i **una promesa incomplerta**.

### ✅ Què està bé (amb evidència)

- **`instal·la_local.sh` sense `sudo` ni `apt install`**: crea `.venv/`, instal·la PyQt5
  de rodes i baixa headers a `.deps/` (`apt-get download`). Funciona i és coherent amb la
  filosofia del projecte (Q9400 sense AVX).
- **`AUTO_CHORDS.desktop` portable**: `Exec` sense rutes absolutes (`%k` → `dirname`),
  funciona si es mou/copia el projecte.
- **`AUTO_CHORDS.sh`** tria l'intèrpret amb prioritat: `portable/` → `.venv/` → `python3`.
- **README «Requisits»** molt complet: separa **usuari final (AppImage)** / **des del codi
  (dev)** / **per construir**, amb CPU, RAM, glibc, àudio i FUSE explicats.
- **`docs/PROVES_FUNCIONALS_3SO.md`**: guia de validació dels 3 paquets + checklist de 5 min.

### ⚠️ Problemes i recomanacions

| # | Problema | Evidència | Acció |
|---|---|---|---|
| 2.1 | **`instal·la_local.sh`: numeració de passos incoherent** — diu `1/4, 2/4, 3/4, 4/4` i després `5/5, 6/6`. Visible per a qui instal·la. | `instal·la_local.sh:8,15,20,35,51,63` | 🔧 **OC-4** (és `.sh`): unificar a `/6`. |
| 2.2 | **`instal·la_local.sh` instal·la la icona però NO el `.desktop`** a `~/.local/share/applications/` → l'app **no apareix al menú** tot i existir el llançador. | `instal·la_local.sh:63-73` | 🔧 **OC-4**: copiar el `.desktop` + `update-desktop-database`. |
| 2.3 | **El README no esmenta la via d'entorn aïllat** (`bash instal·la_local.sh`) a «Llançament»: només diu `python -m app.main` / `./AUTO_CHORDS.sh`. Qui no té PyQt5 al sistema no troba com crear-lo (ho diu només el DEVELOPING). | `README.md:104-122` vs `DEVELOPING.md:25-35` | 📝 **Corregit** (README). |
| 2.4 | `instal·la_local.sh` amb `set -euo pipefail` i `apt-get download` dins bucle **sense `\|\| true`**: si un paquet no existeix al repo, el script aborta. | `instal·la_local.sh:38-45` | 🔧 **OC-4**: tolerància + missatge clar. |
| 2.5 | El README presenta `./AUTO_CHORDS.desktop` com a llançador directe; el flux real és instal·lar-lo o doble-clic. | `README.md:118-122` | 📝 Menor (vegeu correcció 2.3). |

## 3. Documentació (README / DEVELOPING / docs)

**Estat: ⚠️ → 📝** — Cobertura **excel·lent** (README 342 l., DEVELOPING 255, CHANGELOG
1.275, ROADMAP 738, `SECURITY.md`, 20 docs a `docs/`); però hi havia **3 punts
desactualitzats** (2 ja corregits en aquesta auditoria) i **falta un índex** de `docs/`.

### ✅ Què està bé (amb evidència)

- README complet (flux, requisits, estructura, appimage, CI, autoria/agraïments).
- **`docs/ESQUEMA_UI.md` amb test d'auditoria GUI↔doc** (`tests/test_esquema_ui_doc.py`) —
  bona pràctica poc habitual.
- **`docs/REGLES_DE_LA_APP.md`** (10 invariants) enllaçat des del DEVELOPING.
- `docs/` temàtic i en català; autoria i llicència de tercers reconegudes.

### ⚠️ Problemes i recomanacions

| # | Problema | Evidència | Acció |
|---|---|---|---|
| 3.1 | **`DEVELOPING.md` §5 «Auditoria de seguretat» encara llista com a ÀREA DE FUTUR** quan ja s'ha executat (vegeu `docs/SEGURETAT.md`). | `DEVELOPING.md:159-164` | 📝 **Corregit** (marcat FET, com el §9). |
| 3.2 | **Agraïment a «PyQtGraph»** a `DEVELOPING.md`, però **PyQtGraph no s'usa** enlloc. | `DEVELOPING.md:210` (no apareix al codi ni a `requirements`) | 📝 **Corregit** (retirat). |
| 3.3 | **`README` «Estructura clau» desactualitzat** per a `eines/`: esmenta noms vells i no les eines noves (`baixa_verificat.py`, `deps_fixades.env`, `genera_inventari.py`, `notes_release.py`, `launcher_pyinstaller.py`, `AutoChords-win.spec`). | `README.md:144-147` vs `ls eines/` | 📝 **Corregit** (llista actualitzada). |
| 3.4 | **`docs/` no té índex/README** que ordeni els 20 documents → navegació difícil. | `ls docs/` | ⚠️/🕳️ Proposat; es pot resoldre enllaçant-los des del README (fet parcialment). |
| 3.5 | El README «Novetats» s'atura a v0.6.2 i no esmenta els canvis del 13-10 posteriors (enduriment de seguretat, empaquetat unificat). | `README.md:11-20` | ⚠️ Menor; `CHANGELOG [Unreleased]` ho recull. |

## 4. Proves i gestió d'errors

**Estat: ⚠️** — La suite és **gran i verda** (403 tests), però **no es mesura la cobertura**
i la **GUI no té tests d'unitat**.

### ✅ Què està bé (amb evidència)

- **Suite: `Ran 403 tests in 21.3s · OK (skipped=1)`** — reproduïda en local aquesta
  auditoria (`QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests`).
  Corre als **3 SO** al CI.
- 12 fitxers de test; el nucli (`test_pipeline_export.py`) = 273.

  | Fitxer | Tests | | Fitxer | Tests |
  |---|---:|---|---|---:|
  | `test_pipeline_export.py` | 273 | | `test_mcp_bridge.py` | 30 |
  | `test_partitura.py` | 21 | | `test_audio_out.py` | 20 |
  | `test_baixa_verificat.py` | 16 | | `test_timeline_loop.py` | 14 |
  | `test_avis_reanalisi.py` | 6 | | `test_timeline_regle.py` | 6 |
  | `test_dialegs_defaults.py` | 5 | | `test_esquema_ui_doc.py` | 5 |
  | `test_requirements.py` | 4 | | `test_loop_continu.py` | 3 |

- Cobreixen seguretat: `baixa_verificat`, `requirements`, `mcp_bridge` (socket real),
  `safe_filename`, instància única i temporals (dins `pipeline_export`).

### ⚠️ Problemes i recomanacions

| # | Problema | Evidència | Acció |
|---|---|---|---|
| 4.1 | **No hi ha mesura de cobertura** (`coverage.py` absent a `requirements`/CI) ni llindar mínim → no se sap el % real ni es detecten regressions silencioses. | `grep coverage` → res | 🔧 Afegir `coverage` + llindar al CI (o com a mínim informe). |
| 4.2 | **Distribució esbiaixada**: 273/403 (68 %) dels tests són d'un sol fitxer; la **GUI** (`app/main.py`, `app/visor.py`, timeline) **no té tests d'unitat** (només `test_esquema_ui_doc` comprova coherència doc i smoke headless a macOS). | recompte de `def test_` | 🕳️/🔧 Tests de GUI (Qt offscreen) o d'integració. |
| 4.3 | **Errors silenciosos** (4 `except Exception: pass`): l'usuari no s'assabenta de fallades d'àudio/MCP. | `app/audio_out.py`, `app/mcp_bridge.py` | 🔧 Vegeu 1.6. |
| 4.4 | La suite **depèn** dels plugins Vamp locals: sense ells, alguns tests se salten (el `skipped=1`). | execució local | ⚠️ Acceptat; documentat. |
| 4.5 | **Export de partitura** depèn de **MuseScore** instal·lat → no cobert a tot arreu. | `docs/PARTITURA_EXPORT.md` | ⚠️ Acceptat; hi ha skip. |

---

# PART OC-5 (empaquetat/release, CI/CD, portabilitat 3 SO, versions i dependències)

> **Abast:** infraestructura de publicació (paquets per SO), els **5 workflows** de
> CI/CD, la **portabilitat** als 3 SO i la política de **versions/dependències**.
> **Mètode:** lectura directa de `.github/workflows/*.yml`, `eines/*`,
> `docs/{CI_WORKFLOWS,ESTAT_MULTI_SO,COMPONENTS_I_VERSIONS,PROVES_FUNCIONALS_3SO}.md`,
> `pyproject.toml` i `requirements.txt`. **No** s'ha executat el CI (els runs es llancen
> des de GitHub ▸ Actions).

## A. Empaquetat i Release (`.tar.gz` / `.zip` / `.dmg`)

**Estat: ⚠️** — l'esquema és **coherent i ben pensat** (1 paquet canònic per SO amb
executable + docs a dins, noms `AutoChords-<versió>-build<NN>-<so>`, cadena de
subministrament fixada per SHA256); els riscos són sobretot **d'operació**.

### ✅ Què està bé (amb evidència)

- **1 paquet canònic per SO** amb l'executable i els docs a dins: `tar.gz` (Linux),
  `zip` (Windows), `dmg` (macOS) — `release.yml` pas 4 + empaquetat de cada `build-*.yml`.
- **`release.yml` NO compila res**: aprofita l'última execució **verda** de `build-all`
  (o, si no, de cada build solt) i en baixa els artefactes (`release.yml` pas 3).
- **Permisos mínims**: `contents: read` a tots i `write` només al job del Release
  (`release.yml` 27-35); `persist-credentials: false` al checkout.
- **Idempotent** i **robust**: si un SO no té build verd, l'omet i avisa (`release.yml` 88-107).
- **`SHA256SUMS.txt`** generat i adjuntat al Release (`release.yml` 150-158).
- **`build-all`** executa els 3 builds en paral·lel amb un sol clic.

### ⚠️ Problemes i recomanacions

| # | Problema | Evidència | Acció |
|---|---|---|---|
| A.1 | **Finestra de 30 dies**: els artefactes s'esborren al cap de 30 dies i `release.yml` només sap baixar artefactes del CI → passats 30 dies cal **recompilar** per poder publicar. | `build-*.yml`: `retention-days: 30`; `release.yml` pas 3 | 📝 Documentat; opcionalment pujar la retenció |
| A.2 | **Els builds del CI NO fan servir `requirements.txt`**: instal·len amb specs soltes → **no reproduïble** i deriva de versions (`pyinstaller` i `PyQt5-sip` **sense pin**). | `build-windows.yml:102`, `build-macos.yml:80` | 🔧 Fer que els 3 builds instal·lin des de `requirements.txt` |
| A.3 | **Sense verificació de contingut** dels paquets Linux/Windows (macOS sí: 7b munten i comproven el DMG). Un paquet incomplet no es detecta fins al Release. | `build-appimage.yml` 10/11; `build-windows.yml` 10/11 | 🔧 `tar -tzf` / `unzip -l` + comprovar fitxers esperats |
| A.4 | **Linux no té smoke test de l'AppImage** (macOS: 6c; Windows: pas 9). Es valida que els imports i els tests passen, però no que l'AppImage arrenqui. | `build-appimage.yml` 7-10 | 🔧 `--appimage-extract` + execució headless (`AUTO_CHORDS_SMOKE`) |
| A.5 | **Windows puja l'artefacte (pas 11) ABANS dels tests (pas 12)** amb `if: always()` → es pot descarregar un paquet que no ha passat la suite. | `build-windows.yml:159-165` vs `167-194` | 🔧 Moure els tests abans de l'upload (o `if: success()`) |
| A.6 | El **tag del Release surt de `pyproject.toml`**; si s'oblida pujar la versió, el Release existent es **sobreescriu** silenciosament (idempotent). | `release.yml` 44-54 + 160-182 | 🔧 Comprovar al CI que la versió no coincideix amb un tag existent |
| A.7 | **Sense `concurrency`** a cap workflow: dues execucions del mateix poden solapar-se. | `grep concurrency .github/` → res | 🔧 `concurrency:` per workflow |
| A.8 | **Sense atestació/proveniència ni SBOM** estàndard (SPDX/CycloneDX). | `grep attest/sbom` → res | 🕳️/🔧 Valorar `actions/attest-build-provenance` + SBOM |
| A.9 | `cp LICENSE … \|\| true` als 3 empaquetats: si falta un doc, s'ignora en **silenci** i el paquet surt sense. | `build-appimage.yml:134`, `build-windows.yml:144`, `build-macos.yml:342` | ⚠️ Menor; comprovar els docs obligatoris |

## B. CI/CD (5 workflows)

**Estat: ⚠️** — l'enduriment de seguretat és **excel·lent**; falta sobretot
**manteniment automatitzat** (actualitzar accions/dependències) i **límits**.

### ✅ Què està bé (amb evidència)

- **Tots manuals** (`workflow_dispatch`), sense cap trigger automàtic (ni push ni tags).
- **Accions fixades per SHA** (amb la versió al comentari): `checkout@…v5`,
  `setup-python@…v6`, `upload-artifact@…v6`, `cache@…v6`, `setup-msys2@…v2`.
- **`permissions: contents: read`** a tots i `persist-credentials: false` al checkout.
- **La suite sencera** (`python -m unittest discover -s tests`) corre als **3 runners**.
- **Diagnòstic en fallada** (`ZZ`/`ZZ2`) que puja logs i anotacions `::error::` llegibles per API.
- **`build-all`** com a *reusable workflow* agregador.

### ⚠️ Problemes i recomanacions

| # | Problema | Evidència | Acció |
|---|---|---|---|
| B.1 | **Accions fixades per SHA sense actualització automàtica** → envelliran; quan GitHub retiri el runtime (Node), caldrà moure-les a mà. | `uses: …@<sha>  # v5/v6/v2` | 🔧 Dependabot (`github-actions`) |
| B.2 | **Sense Dependabot ni revisió programada de dependències**, tot i tenir `COMPONENTS_I_VERSIONS.md`. | `.github/` sense `dependabot.yml` | 🔧 Crear `.github/dependabot.yml` |
| B.3 | **Sense cobertura** al CI (compartit amb OC-6 §4.1). | `grep coverage .github/` → res | 🔧/🕳️ `coverage` + llindar |
| B.4 | **Sense `timeout-minutes`** → una execució encallada pot arribar al límit per defecte. | `grep timeout .github/` → res | 🔧 `timeout-minutes` raonable |
| B.5 | `build-appimage.yml` instal·la `libqt6*` «best effort» (`\|\| true`) només per al TTL dels tests → depèn de paquets que poden desaparèixer. | `build-appimage.yml:79-80` | ⚠️ Menor; documentar |

## C. Portabilitat 3 SO

**Estat: ⚠️** — **documentació extensa i coherent**; els punts febles són **dates
límit** (runners) i la **validació en maquinari real**.

### ✅ Què està bé (amb evidència)

- Guies per SO: `docs/PORTABILITAT.md`, `docs/PORTABILITAT_WINDOWS.md`,
  `docs/PLANIFICACIO_MACOS.md`, `docs/MOTOR_AUDIO_SO.md`, `docs/ESTAT_MULTI_SO.md`,
  `docs/PROVES_FUNCIONALS_3SO.md` (checklist de 5 min).
- **`app/plataforma.py`**: abstracció de SO (noms `.exe`, dreceres de plugins,
  reproductor, kill, lock).
- **macOS a 10.13**: `minos` verificat a tot el bundle (6b) + **smoke test** real (6c) +
  guard del Python (2b) — arregla arrels profundes del «no arrenca».
- **Windows**: `portable/win-dlls` al `PATH` i al costat del host (evita `0xC0000135`).
- **`.desktop` portable** amb `%k` i `AUTO_CHORDS.sh` amb cascada `portable/ → .venv/ → python3`.

### ⚠️ Problemes i recomanacions

| # | Problema | Evidència | Acció |
|---|---|---|---|
| C.1 | **`macos-15-intel` caduca l'agost de 2027** (últim runner Intel de GitHub Actions) i el destí és x86_64 10.13 → **data límit** sense pla B documentat. | `build-macos.yml:14-15` | ⚠️ Nota de risc + pla (self-hosted o canvi de SO objectiu) |
| C.2 | **MINGW64 «deprecated»** a MSYS2 (migrar a UCRT64 = canvi de toolchain). | `build-windows.yml:57-59` | ⚠️ Documentat; planificar |
| C.3 | **Validació en maquinari real** de Windows/macOS **pendent** (els agents no hi tenen accés). | `docs/PROVES_FUNCIONALS_3SO.md` | ✅ Acceptat (operador) |
| C.4 | La guia de proves descrivia els **noms antics** dels paquets. | `PROVES_FUNCIONALS_3SO.md:19-23,38` | 📝 Corregit (noms canònics nous) |

## D. Versions i dependències (pins, inventari, CVE)

**Estat: ⚠️** — pins i inventari **presents i ben fets**; el problema és que els pins
**no s'apliquen al build** i no hi ha revisió CVE automatitzada.

### ✅ Què està bé (amb evidència)

- **`requirements.txt` amb pins exactes** `==` i **guard** `tests/test_requirements.py`
  (prohibeix `numpy>=2` i `PyQt6`).
- **`eines/deps_fixades.env`**: URL + versió + **SHA256** de cada baixada i **commit**
  dels repos compilats (verificat a cada descàrrega).
- **`docs/COMPONENTS_I_VERSIONS.md`** generat per `eines/genera_inventari.py`.
- **`numpy==1.26.4`** obligatori pel Q9400 (sense AVX/SSE4.2) — documentat i guardat.

### ⚠️ Problemes i recomanacions

| # | Problema | Evidència | Acció |
|---|---|---|---|
| D.1 | **Els pins de `requirements.txt` no s'apliquen al CI** (vegeu A.2): l'inventari i el pin divergeixen. Ex.: `PyQt5_sip` **12.20.0** al portable vs **12.19.0** a `requirements.txt`. | `COMPONENTS_I_VERSIONS.md:80` vs `requirements.txt:16` | 🔧 Vegeu A.2 |
| D.2 | `pyproject.toml` amb **rangs** ≠ pins (compartit amb OC-6 §1.4). | `pyproject.toml:14-17` | 🔧 Vegeu OC-6 |
| D.3 | **Sense `--require-hashes`** (compartit amb OC-6 §1.3). | `requirements.txt:28-36` | 🕳️ Pendent |
| D.4 | **Sense revisió de CVE automatitzada** (Dependabot/audit). | — | 🔧 Vegeu B.2 |
| D.5 | `COMPONENTS_I_VERSIONS.md` es regenera **a mà**; cap CI comprova que estigui al dia. | `eines/genera_inventari.py` | 🔧 Pas de CI: regenerar + `git diff --exit-code` |

### 📝 Esmenes (revisió creuada d'OC-6/306)

> **Append-only**: no he tocat les files originals d'aquesta part; aquí queda el
> registre de les esmenes, citant l'ID del registre que les motiva.

- **A.5 — prioritat rebaixada d'«alta» a «mitjana»** _(esmena citant OC-6/306)_:
  `release.yml` només accepta runs amb `--status success` (`release.yml` pas 3), així
  que un paquet d'una run **vermella** no arriba mai al **Release automàtic**; el risc
  queda limitat a una **descàrrega manual** de l'artefacte. La resta de l'item es manté.
- **A.2 / D.1 — evidència afegida**: `docs/COMPONENTS_I_VERSIONS.md` **s'autocontradiu**
  (`PyQt5_sip` **12.19.0** al resum, línia 20, vs **12.20.0** a «Paquets del Python
  portable», línia 80). Com que és un **document generat** (`eines/genera_inventari.py`),
  el que cal arreglar és el **generador** (no el `.md`) → encaixa amb D.5. 🔧 Per a OC-4.
- **Revisió independent d'OC-6/306**: les afirmacions de més pes d'aquesta part
  (retenció de 30 dies, cap build usa `requirements.txt`, ordre pujada/tests a Windows,
  sense smoke test de l'AppImage, sense `concurrency`/`timeout`, `cp LICENSE … || true`,
  `PyQt5_sip` 12.19 vs 12.20) han estat **confirmades al codi**. Cap contradicció amb la
  PART OC-6.

> Generat per **OC-5** (2026-10-13) sobre el commit `75c8f31`. Coordinació via
> `LOG_DIALEGS_AGENTS.txt` (`OC-5/302`+).

---

# Correccions fetes en aquesta auditoria (només `.md`)

> **Consolidat** en un sol lloc [OC-5, petició de l'operador, 13-10] (abans n'hi havia
> dues: OC-6 §«Correccions fetes» i OC-5 §«Correccions fetes per OC-5»).

| Fitxer | Canvi | Motiu | Autor |
|---|---|---|---|
| `docs/AUDITORIA_PRODUCCIO.md` | **Nou** (aquest document) | Lliurable | OC-6 + OC-5 |
| `README.md` | Afegit `bash instal·la_local.sh` a «Llançament»; llista de `eines/` actualitzada | ⚠️ 2.3, 3.3 | OC-6 |
| `DEVELOPING.md` | §5 seguretat → marcat **FET**; retirat l'agraïment a PyQtGraph | ⚠️ 3.1, 3.2 | OC-6 |
| `docs/CI_WORKFLOWS.md` | Retenció d'artefactes: «~90 dies» → **30 dies** (+ nota que passats 30 dies cal recompilar) | A.1 | OC-5 |
| `docs/ESTAT_MULTI_SO.md` | Corregit «`release.yml` s'activa amb tags `v*`» (ara és **manual**) + llista de paquets actualitzada a 3 (`.tar.gz`/`.zip`/`.dmg`) | estale | OC-5 |
| `docs/PROVES_FUNCIONALS_3SO.md` | Noms canònics nous dels paquets (Linux `.tar.gz`, macOS `.dmg`) | C.4 | OC-5 |

# Arreglos de CODI/CI → OC-4 (requereixen codi)

> **Consolidat** en un sol lloc [OC-5, petició de l'operador, 13-10]: fusiona les
> «Passes següents» d'OC-6 (punts 1-7) i els «Arreglos de CODI/CI» d'OC-5 (A-D).
> OC-4 és l'únic amb permís d'editar codi. Cap ítem perdut; `coverage` surt una sola vegada.

**Estat [verificat per OC-5 al codi, 13-10]:**

- ✅ **BLOC 1 fet i verificat** — A.2 `requirements-build.txt` (`-r requirements.txt` +
  `pyinstaller==6.22.3`, usat pels builds de Windows i macOS) · A.5 tests **abans** de
  l'upload a Windows · A.7/B.4 `concurrency` + `timeout-minutes` als **5** workflows ·
  B.2 `.github/dependabot.yml` (amb `numpy` i `PyQt6` ignorats) · 1.1 `LICENSE` = GPLv3
  complet (674 l.) · 1.4/D.2 `pyproject` amb pins · 1.5 `.gitignore` `XX TEMP FILES USUARI/` ·
  2.1/2.2 `instal·la_local.sh` numeració `/6` + `.desktop` a `~/.local/share/applications`.
- ✅ **BLOC 2 fet i verificat** (`4f6c8bb`) — A.3 verificació de **contingut** del `.tar.gz`
  i del `.zip` (fitxers obligatoris) · A.4 **smoke test de l'AppImage** (pas 9b, headless) ·
  A.6 **avis** de tag/Release existent (`::warning::`).
- ✅ **1.6/4.3 fet** (`aac8b26`) — fora els `except Exception: pass` silenciosos (àudio/MCP)
  + avís visible quan mor el motor d'àudio (+ `tests/test_avis_audio.py`).
- ✅ **2.4 fet** — `instal·la_local.sh`: `apt-get download … || avís` (no tomba l'script).
- ⏳ Encara pendents: els opcionals **A.8** (SBOM/atestació) i **D.5** (CI que regeneri
  l'inventari i comprovi `git diff`).

> **[OC-6, 13-10] ACTUALITZACIÓ (estat final, HEAD `aac8b26`)** — el **BLOC 2 JA està FET**
> (A.3 · A.4 · A.6) i també ho estan **1.6** (`aac8b26`: avís d'àudio VISIBLE + fora els
> `except` silenciosos) i **2.4** (tolerància a `apt-get download`). Verificat al codi per
> OC-6. Els ítems de la llista de sota ja són **fets**; només resten oberts els **opcionals**
> (1.3, 1.7, 3.4, A.8, B.5, C.1/C.2, D.5 i `coverage`/tests de GUI). Vegeu l'**«ESTAT FINAL»**
> de dalt. (Esmena append-only: no modifico el text original d'OC-5.)

**D'OC-6 (auditoria d'app/UX/docs/seguretat):**

1. `LICENSE` → text complet de la GPLv3 (o `COPYING`). · **1.1** · ✅ **FET** (`4f6c8bb`)
2. Unificar la llicència a `GPL-3.0-or-later` (pyproject/README/etc.). · **1.2** · ✅ **FET** (`4f6c8bb`)
3. `instal·la_local.sh`: numeració `/6` + instal·lar el `.desktop` al menú + tolerància a `apt-get download`. · **2.1/2.2/2.4** · ✅ **FET** (`4f6c8bb`)
4. `pyproject.toml`: `dependencies` alineades amb els pins de `requirements.txt`. · **1.4 / D.2** · ✅ **FET** (`4f6c8bb`)
5. `.gitignore`: excloure `XX TEMP FILES USUARI/` (+ `git rm --cached`). · **1.5** · ✅ **FET** (`4f6c8bb`)
6. Avís visible quan el motor d'àudio mor (fora els `except Exception: pass` silenciosos). · **1.6 / 4.3** · ✅ **FET** (`aac8b26`)
7. `coverage` + llindar al CI. · **4.1 / B.3** · ✅ **FET** (`77f7e45`, llindar 65 %)

**D'OC-5 (empaquetat/CI/portabilitat/versions):** _prioritat alta/mitjana/baixa_

- [x] `build-{appimage,windows,macos}.yml` — instal·lar des de `requirements.txt` + **pin** de `pyinstaller`. · **A.2/D.1** · ✅ `4f6c8bb`
- [x] `build-windows.yml` — executar els tests **abans** de pujar l'artefacte. · **A.5** · ✅ `4f6c8bb` _(rebaixat; vegeu l'esmena OC-6/306)_
- [x] `build-appimage.yml` — **smoke test** de l'AppImage (headless). · **A.4** · ✅ `4f6c8bb`
- [x] `build-{appimage,windows}.yml` — verificar el **contingut** del `.tar.gz`/`.zip`. · **A.3** · ✅ `4f6c8bb`
- [x] `.github/` — `concurrency` + `timeout-minutes`. · **A.7/B.4** · ✅ `4f6c8bb`
- [x] `.github/dependabot.yml` — `github-actions` + `pip`. · **B.2/D.4** · ✅ `4f6c8bb`
- [x] CI que regeneri `COMPONENTS_I_VERSIONS.md` i comprovi `git diff`. · **D.5** · ✅ `77f7e45`
- [ ] _(Opcional, **no fet**)_ SBOM + atestació de proveniència. · **A.8** · **baixa**

> ✅ **13-10:** tots els ítems **no opcionals** d'aquesta llista estan **FETS** (commits `4f6c8bb`/`77f7e45`/`aac8b26`); només queda obert l'opcional **A.8 (SBOM/atestació)**.

# ✅ Bugs de producció (13-10) — trobats i arreglats

Detectats durant la **validació funcional**; tots amb causa, fix, test i commit.

### B1. (GREU) No es podia reanomenar cap secció que no fos la primera — `c46c7d6`
- **Símptoma**: canviar el nom de qualsevol secció d'estructura que no fos la 1a fallava
  (log de l'app: «Les seccions no poden solapar-se ni invertir-se…»).
- **Causa**: l'**editor** mostra l'inici amb **2 decimals** i, en aplicar, el re-escrivia
  arrodonit (16,63 en lloc de 16,633663): la 2a secció quedava uns ms **abans** del final
  de la 1a → la validació la rebutjava. La 1a funcionava perquè no té res al davant.
- **Fix** (`app/visor.py`, `_aplica_editor`): si l'inici **no s'ha tocat** (dins ±0,005 s)
  es conserva el valor **intern de precisió completa**; mateix criteri als **acords**.
- **Test**: `tests/test_editor_renom.py` (3 casos).

### B2. (GREU) L'exportació perdia les edicions de seccions — `85704ed` (A)
- **Símptoma**: editar seccions (reanomenar/moure/esborrar) i **exportar** →
  `estructura_ABC.csv` i `wavs_estructura/` **tornaven a les originals**. (Els acords sí.)
- **Causa**: `main.exporta` passava a `pipeline.exporta_total` el `segments.csv` **cru** de
  l'anàlisi i en **regenerava** l'estructura, ignorant el model (`self.seccions`).
- **Fix** (retrocompatible): `exporta_total(..., acords=None, seccions=None)` — si s'hi
  passen, **mana el MODEL** (l'ABC es genera de les seccions del model); sense ells,
  comportament idèntic a abans. `main.exporta` hi passa el model del visor.
- **Test**: `tests/test_cobertura_viu.py` (l'export usa el model i **no** `segments.csv`;
  re-normalitza; sense model = com abans).

### B3. (regla d'or #4) La cobertura no s'aplicava a les edicions en viu — `85704ed` (B)
- **Símptoma**: eliminar el **1r acord** deixava un forat al principi (0,00→0,30), visible
  **al visor i al CSV**.
- **Causa**: `normalitza_cobertura()` només s'aplicava a l'anàlisi, en carregar el visor i
  en exportar l'ABC — **no** després d'editar (ni GUI ni MCP).
- **Fix**: nou `Visor._normalitza_cobertura()` (que crida `pipeline.normalitza_cobertura`),
  aplicat a `_desa_i_regenera` **abans** de desar → refresca el visor i desa `acords.csv`
  **i** `estructura_ABC.csv` ja **normalitzats**.
- **Test**: `tests/test_cobertura_viu.py` (4 casos).

### B4. (GREU) Xocs d'inici dins la resolució del CSV
- **Símptoma**: dos acords amb inicis **molt propers** que, arrodonits al **CSV** (2 decimals), **coincidien** de fila → CSV ambigu i WAVs de durada 0 a l'export.
- **Causa**: la resolució del CSV (2 decimals) no garantia files úniques.
- **Fix**: exigir una **distància mínima** entre inicis (en lloc de tocar `TEMPS_DEC`) + detecció de xocs amb missatge clar. Test: `tests/test_xocs_inici_csv.py` (10).

### B5. Reanomenament sense sanejar (noms d'acord)
- **Símptoma**: el nom d'un acord es podia escriure amb caràcters **no vàlids** per al fitxer (des de l'MCP o l'editor) i podia **divergir** del nom a l'export.
- **Causa**: el sanejat era **parcial** (només a l'alta d'acord).
- **Fix**: helper canònic **`pipeline.saneja_nom_acord()`** (embolcalla `safe_filename`) aplicat als **4 camins** (MCP `rename_chord`, editor, renom inline, alta). Noms habituals intactes (`C#m7`, `N`; `Am/G`→`Am-G`). Test: `tests/test_rename_sanejat.py` (6).

> ✅ **Tots** els bugs d'aquesta secció estan arreglats, amb **tests de regressió**; els d'ordre/cobertura estan documentats a `docs/REGLES_DE_LA_APP.md`. Suite **468 OK (1 skip)**.

> Generat per **OC-6** (2026-10-13) sobre el commit `75c8f31`. Coordinació via
> `LOG_DIALEGS_AGENTS.txt` (`OC-6/303`+). **Seccions duplicades consolidades per OC-5**
> el 13-10 (petició de l'operador): «Correccions fetes» i «Arreglos de CODI/CI → OC-4»
> unificats en un sol lloc (cap ítem perdut; `coverage` només una vegada).
