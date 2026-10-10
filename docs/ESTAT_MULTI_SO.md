# Estat multi-SO — on som i què queda pendent

> **2026-10-09 · v0.5.2 (BETA).** Foto del desplegament a **Linux, Windows i
> macOS**: **els 3 builds del CI són VERDS**. Complementa `ROADMAP.md` §9
> (viabilitat), `docs/CI_WORKFLOWS.md` (els 5 workflows de CI),
> `docs/PORTABILITAT.md` (Linux), `docs/PORTABILITAT_WINDOWS.md`
> i `docs/PLANIFICACIO_MACOS.md`.

## Resum

| SO | Objectiu | Estat | Artefacte del CI |
|----|----------|-------|------------------|
| **🐧 Linux** | AppImage x86_64 | ✅ **VERD i verificat** (run #8, `08bbfc7`) | `AutoChords_v0.5.1-main-build8-Linux` (ZIP que conté l'AppImage `auto-chords-*-x86_64.AppImage`) |
| **🪟 Windows** | ZIP portable x64 | ✅ **VERD amb tests** (run #14, `08bbfc7`) | `AutoChords_v0.5.1-main-build14-Windows` (**~95 MB**) |
| **🍎 macOS** | `.app` per a **High Sierra 10.13+** (Intel) + **`.dmg`** | ✅ **VERD** (run #14, `3c7f441`; smoke test OK) | `AUTO_CHORDS-macos-build14` (`.app` dins ZIP **+ `.dmg`**) |

> ⚠️ Els noms dels artefactes porten la versió del **`pyproject.toml`** en el
> moment de construir-los (`v0.5.1`); amb el bump a **v0.5.2** (2026-10-09), una
> execució nova els anomenarà `v0.5.2`. Els 3 runs **#8 / #14 / #8** validen tot
> el codi de la Fase D.2 (`08bbfc7`).

## Detall per plataforma

### 🐧 Linux — complet ✅

- **AppImage autocontinguda** (runtime estàtic → **no cal `libfuse2`**).
- **Verificada de soca-rel**: arrenca muntada (GUI real, 0 errors), l'estat va a
  `~/.local/state/auto-chords/`, **231/231 tests dins el paquet**, host+plugins
  del paquet OK sobre un WAV real, i **export de partitura** (MusicXML+PDF+MSCZ).
- Workflows: `build-appimage.yml` (manual), **`build-all.yml`** (agregador: executa
  els 3 builds en **paral·lel**) i `release.yml` (tags `v*`).
- ✅ **Release #1 VERD** (tag **`v0.5.1_CHECKPOINT_3_so_ARTIFACTS`** = `e895fa6`);
  `release.yml` s'activa amb tags `v*`.
- **`release.yml` — drecera manual amb els 3 SO** (2026-10-09): **manual**
  (workflow_dispatch). **No compila res**: busca l'última execució **VERDA** de
  cada build, en baixa els artefactes de GitHub Actions i crea l'esborrany amb
  **els 3 paquets** adjunts (AppImage + ZIP Windows + ZIP macOS). És
  **idempotent** (si el Release ja existeix, només hi adjunta/actualitza).

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
- **Artefacte**: `AUTO_CHORDS-macos.zip` **+ `AUTO_CHORDS-macos.dmg`**.
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

> 🎯 **Únic pendent**: la **revisió funcional** dels 3 paquets en un sistema real
> (Linux ja es va verificar a fons; **Windows i macOS cal provar-los** des dels
> sistemes respectius — els agents no hi tenen accés directe).
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
# Linux (AppImage) — descarregar de GitHub > Actions o del Release
chmod +x *.AppImage && ./*.AppImage

# macOS — provar al Hackintosh (10.13)
unzip AUTO_CHORDS-macos-build8.zip
# clic-dret ▸ Obrir (o: xattr -dr com.apple.quarantine AUTO_CHORDS.app)

# Windows — descomprimir el ZIP i executar AUTO_CHORDS.exe
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
