# Estat multi-SO — on som i què queda pendent

> **2026-10-14 · v0.7.0 (BETA).** Foto del desplegament a **Linux, Windows i
> macOS**: **els 3 builds del CI són VERDS**. Complementa `ROADMAP_HISTORIA.md` §9
> (viabilitat), `docs/CI_WORKFLOWS.md` (els 5 workflows de CI),
> `docs/PORTABILITAT.md` (Linux), `docs/PORTABILITAT_WINDOWS.md`,
> `docs/PLANIFICACIO_MACOS.md` i `docs/MOTOR_AUDIO_SO.md` (àudio per SO).

## Resum

| SO | Objectiu | Estat | Artefacte del CI |
|----|----------|-------|------------------|
| **🐧 Linux** | `tar.gz` amb l'AppImage x86_64 | ✅ **VERD i verificat** | **`.tar.gz`** `AutoChords-<versió>-build<NN>-linux-x86_64` (AppImage + docs) |
| **🪟 Windows** | `.zip` portable x64 | ✅ **VERD amb tests** | **`.zip`** `AutoChords-<versió>-build<NN>-win-x64` (`.exe` + `_internal/` + docs; ~95 MB) |
| **🍎 macOS** | `.dmg` amb l'`.app` per a **High Sierra 10.13+** (Intel) | ✅ **VERD** (smoke test OK) | **`.dmg`** `AutoChords-<versió>-build<NN>-macos-x86_64` (`.app` + enllaç a /Applications + docs) |

> ⚠️ Els noms dels artefactes porten la **versió del `pyproject.toml`** del
> moment de construir-los i el **número de l'execució** (`<NN>`). Els darrers
> builds verds: **`build-all` #4** (`98aa58e`), amb la **suite completa** de
> tests a cada runner.

> 🔧 **Enduriment del CI (13-10, `4f6c8bb`)**: builds **reproduïbles**
> (`requirements-build.txt` amb pins + `pyinstaller==6.22.3`), **verificació de
> contingut** de cada paquet, **smoke test de l'AppImage** (Linux), tests **abans**
> de l'upload a Windows, `concurrency`+`timeout` als 5 workflows i Dependabot (**retirat el 14-10**; a mà).
> Detall: `docs/CI_WORKFLOWS.md` §4.
>
> ⚠️ **Pendent de validar**: aquests passos nous **encara no han corregut** en una
> execució verda — el darrer `build-all` verd és el **#4** (`98aa58e`). Cal llançar
> `build-all` per confirmar-los.

## Detall per plataforma

### 🐧 Linux — complet ✅

- **AppImage autocontinguda** (runtime estàtic → **no cal `libfuse2`**).
- **Verificada de soca-rel**: arrenca muntada (GUI real, 0 errors), l'estat va a
  `~/.local/state/auto-chords/`, **tota la suite de tests dins el paquet**, host+plugins
  del paquet OK sobre un WAV real, i **export de partitura** (MusicXML+PDF+MSCZ).
- Workflows: `build-appimage.yml` (manual), **`build-all.yml`** (agregador: executa
  els 3 builds en **paral·lel**) i `release.yml` (**manual**).
- ✅ **Release #1 VERD** (tag **`v0.5.1_CHECKPOINT_3_so_ARTIFACTS`** = `e895fa6`).
  _(Corregit 13-10 [OC-5]: `release.yml` JA NO s'activa amb tags `v*` — ara és
  exclusivament **manual** (`workflow_dispatch`); vegeu `docs/CI_WORKFLOWS.md`.)_
- **`release.yml` — drecera manual amb els 3 SO** (2026-10-10): **manual**
  (workflow_dispatch). **No compila res**: busca l'última execució **VERDA** de
  `build-all` (els 3 SO) o, si no, de cada build; en baixa els artefactes de
  GitHub Actions i crea el **Release PUBLICAT** (i el tag) amb **els 3 paquets**
  adjunts (**`.tar.gz`** Linux + **`.zip`** Windows + **`.dmg`** macOS — noms
  canònics `AutoChords-<versió>-build<NN>-<so>`). És
  **idempotent** (si existeix, hi adjunta/actualitza i el **publica**).

### 🍎 macOS — VERD amb etapa de tests ✅

- Runner **`macos-15-intel`** (l'últim Intel de GitHub Actions; disponible fins a
  l'agost de 2027).
- `MACOSX_DEPLOYMENT_TARGET=10.13` i **`PyQt5==5.15.10`** (l'únic amb wheel
  `macosx_10_13_x86_64`; el 5.15.11 és `11_0` i no va a High Sierra).
- **Natius compilats des de font** a 10.13: `libvamp-hostsdk`, `libsndfile`, el
  host propi (`vamp_host_local`) i **`qm-vamp-plugins`** — el binari oficial de
  macOS **no es pot baixar** (`code.soundsoftware.ac.uk` està inaccessible), o
  sigui que es compila (qm-dsp + vamp-plugin-sdk).
- `ffmpeg` estàtic (evermeet, requereix 10.13) + **PyInstaller `.app`** + ZIP
  (`ditto`) + **DMG** (`hdiutil`).
- Workflow: `build-macos.yml` (manual). Etapes noves (2026-10-10): **6b**
  verificació exhaustiva del `minos` de TOT el bundle (x86_64 ≤ 10.13, amb
  `eines/verifica_minos_macos.py`), **6c** **smoke test** de l'`.app`
  empaquetada (headless, `AUTO_CHORDS_SMOKE=1`; script `eines/smoke_macos.sh`) i
  **7b** **DMG** (`hdiutil`, muntat i verificat).
- ✅ **Fix 1 (10-10)**: el Python del runner (**3.14**) tenia `minos 15.0` →
  l'`.app` **no arrencava** a High Sierra (`PYI-ERROR: cannot load 'Python'`).
  Ara s'usa **Python 3.12** + un **guard** que falla el build si el `minos` del
  Python és > 10.13 (`c7ed61a`).
- ✅ **Fix 2 (10-10) — l'arrel del «no funciona»**: l'app congelada petava amb
  **`ModuleNotFoundError: No module named 'PyQt5'`**. PyInstaller **no resolia
  `app.main`** (el launcher l'importa **dins d'una funció** i l'entry és a
  `eines/`) → **no empaquetava PyQt5** (ni el directori `platforms` de Qt).
  **Fix**: `--paths . --paths app` + `--hidden-import` (igual que el `.spec` de
  Windows) (`3c7f441`). Detectat gràcies al **smoke test** del CI.
- ✅ **Run #14 (`3c7f441`) VERD** — amb tots els passos nous (minos, smoke, DMG).
- **Artefacte**: el **`.dmg`** (`AutoChords-<versió>-build<NN>-macos-x86_64.dmg`).
- **PENDENT**:
  1. ✅ **FET**: etapa de tests afegida al workflow (`e7f6695`); runs **#7 i #8
     VERDS amb els tests dins** (suite completa + anotació `::error::`).
  2. ✅ **FET (10-10)**: **verificació exhaustiva del `minos`** + **smoke test**
     al CI + **DMG** (aquest treball).
  3. **Provar l'`.app` i el `.dmg` al Hackintosh** (High Sierra 10.13 real) — els
     agents no hi tenen accés; ho ha de fer l'operador.
  4. Signatura/notarització: **descartades** (l'usuari obre amb clic-dret ▸ Obrir
     o `xattr -dr com.apple.quarantine`).

### 🪟 Windows — VERD ✅

- Runner `windows-2022`; host i plugins amb **MSYS2/MINGW64**.
- **`qm-vamp-plugins` compilat des de font**: el binari oficial win64 depèn de
  `libblas.dll`/`liblapack.dll` **i del runtime DEBUG de MSVC** → no empaquetable.
- `portable/win-dlls` (runtime MinGW) al `PATH` de l'etapa de tests **i** copiat
  al costat del host (evita `0xC0000135` = `STATUS_DLL_NOT_FOUND`).
- `ffmpeg` estàtic + **PyInstaller `--onedir`** + ZIP.
- Workflow: `build-windows.yml` (manual; **corre els tests**).
- ✅ **Runs #12 (`653ca98`) i #14 (`08bbfc7`) VERDS**: l'últim error del CI era
  un `print()` amb emojis en consola cp1252 (`UnicodeEncodeError`), resolt
  (`653ca98`). El **#14** valida tot el codi de la Fase D.2.

## Pendent real

> 🎯 **Dos pendents** (13-10):
> 1. **Revalidar el CI**: els passos nous (smoke de l'AppImage, verificació de
>    contingut, `concurrency`/`timeout`, builds reproducibles) i els
>    **fixos de Windows** encara **no han corregut** en una execució verda — cal
>    llançar `build-all` i confirmar el verd.
> 2. **Validació funcional real** dels 3 paquets: Linux ja es va verificar a fons;
>    **Windows i macOS cal provar-los** des dels sistemes respectius (els agents no
>    hi tenen accés directe).
> Guia pas a pas: **`docs/PROVES_FUNCIONALS_3SO.md`** (arrencada, checklist de
> 5 minuts i què mirar si falla).

## Els problemes trobats i resolts (per ordre)

| # | Símptoma | Causa | Solució |
|---|----------|-------|---------|
| 1 | `E: Unable to locate package libvamp-hostsdk-dev` | El paquet no existeix a Ubuntu | `vamp-plugin-sdk` |
| 2 | Avís de deprecació de Node 20 | Actions @v4 apunten a Node 20 | `checkout@v5`, `upload-artifact@v6` |
| 3 | El job no corria `test_partitura` | Només s'executava `test_pipeline_export` | afegit al `unittest` |
| 4 | `vamp_host_local` sortia amb codi 1 al runner | Els `.so` dels plugins demanaven **`GLIBCXX_3.4.32`** (GCC 13) | **compilar els plugins al runner** (jammy/GCC 11) |
| 5 | `FileNotFoundError: 'ffmpeg'` | Els tests cridaven l'ffmpeg del sistema | `ffmpeg.FFMPEG` + `portable/bin` al `PATH` |
| 6 | `KeyError: 'mostreig'` | `ffprobe` no s'empaqueta | el test fa `skipTest` si no hi és |
| 7 | Windows: `pacman` → `target not found` | BD de pacman vella + mirror a 1 byte/s | `pacman -Sy` abans d'instal·lar |
| 8 | Windows: `error: 'M_PI' was not declared` | `-std=c++98` (ANSI) i `M_PI` és POSIX | `-D_USE_MATH_DEFINES` |
| 9 | Windows: plugin `error code 126` | El binari oficial depèn de libblas/liblapack + runtime DEBUG | **qm compilat des de font** |
| 10 | Windows: `0xC0000135` (`DLL_NOT_FOUND`) | El host no trobava el runtime MinGW | `portable/win-dlls` al `PATH` |
| 11 | Windows: 40 errors als tests | `open()` **sense `encoding`** (cp1252) i fitxers sense tancar | `encoding="utf-8"` a tot + `_escriu_fitxer()` |
| 12 | Windows: 1 error `UnicodeEncodeError` al `print` | Consola cp1252 amb emojis | `print` tolerant + `sys.stdout.reconfigure(errors="replace")` |

## Com provar-ho (operador)

```bash
# Linux — descarregar de GitHub > Releases i extreure el paquet .tar.gz
tar -xzf AutoChords-*-linux-x86_64.tar.gz
chmod +x AutoChords-*-x86_64.AppImage && ./AutoChords-*-x86_64.AppImage

# macOS — obrir el .dmg al Hackintosh (10.13) i arrossegar l'app a Applications
# clic-dret ▸ Obrir (o: xattr -dr com.apple.quarantine AUTO_CHORDS.app)

# Windows — descomprimir el paquet .zip i executar AutoChords.exe
```

## Fitxers clau

| Fitxer | Què hi ha |
|--------|-----------|
| `app/plataforma.py` | **Abstracció de SO** (noms `.exe`, dirs de plugins, reproductor, kill, lock) |
| `eines/compila_vamp_host.sh` | Host propi, **multi-SO** |
| `eines/compila_vamp_plugins.sh` | Plugins, **dispatch per SO** (Linux/Windows/macOS) |
| `eines/launcher_pyinstaller.py` | Entry de PyInstaller (Win i macOS) |
| `.github/workflows/build-{appimage,windows,macos}.yml` | Els 3 builds |
| `.github/workflows/build-all.yml` | **Agregador**: els executa tots 3 en paral·lel |
| `docs/PORTABILITAT_WINDOWS.md`, `docs/PLANIFICACIO_MACOS.md` | Detall per SO |
