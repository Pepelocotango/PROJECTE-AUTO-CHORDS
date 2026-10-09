# Planificació: app de macOS (High Sierra 10.13+)

> **2026-10-07 · actualitzat 2026-10-08.** Pla per construir AUTO CHORDS per a
> **macOS x86_64** amb **mínim High Sierra 10.13**, tot a **GitHub Actions**
> (cap build local Mac). Complementa `ROADMAP.md` §9 (viabilitat) i
> `docs/PORTABILITAT.md` (Linux).
>
> ✅ **ESTAT (2026-10-09)**: build **VERD** al CI (run #8, `08bbfc7`); `.app`
> dins ZIP. **Falta una etapa de tests** al workflow (avui només valida el
> build). Detall: `docs/ESTAT_MULTI_SO.md`.

## 1. Objectiu i abast

| | |
|---|---|
| **Destí** | macOS **10.13 High Sierra o superior**, **Intel x86_64** |
| **Format** | `AUTO_CHORDS.app` (PyInstaller `--windowed`) dins un **ZIP** (`ditto`) |
| **Signatura** | **No** (sense developer ID) → Gatekeeper: l'usuari obre amb **clic-dret ▸ Obrir** o `xattr -dr com.apple.quarantine` |
| **Host de build** | GitHub Actions, runner **`macos-15-intel`** |

⚠️ **`macos-15-intel` és l'ÚLTIM runner Intel** de GitHub Actions (anunciat
19-09-2025; disponible fins a **agost 2027**). No hi haurà més imatges x86_64
després. Si mai calgués, alternatives: `macos-14-large` / `macos-15-large`
(runners grans, de pagament).

## 2. Dependències (pins crítics)

| Paquet | Pin | Motiu |
|---|---|---|
| **PyQt5** | **`==5.15.10`** | L'últim amb wheel **`macosx_10_13_x86_64`**. El **5.15.11** és `macosx_11_0` → **no instal·la ni corre a High Sierra**. |
| PyQt5-Qt5 | `==5.15.19` | Wheel `10_13` ✅ |
| PyQt5_sip | l'últim | Wheel `10_9_universal2` ✅ |
| numpy | `<2` (1.26.4) | Wheel `10_9` ✅ i **obligatori pel Q9400** (numpy 2.x demana x86_64-v2) |
| Python | 3.12 | Suporta 10.13 ✅ |

## 3. Les 3 peces natives (compilades a 10.13)

> **Regla d'or**: tot el que sigui natiu s'ha de compilar **amb
> `MACOSX_DEPLOYMENT_TARGET=10.13`**. **MAI** fer servir *bottles* de Homebrew
> (pujarien el mínim i l'app no arrencaria a High Sierra).

1. **`libvamp-hostsdk`** + **`libsndfile`** → compilats des de font
   (`c4dm/vamp-plugin-sdk`, `libsndfile/libsndfile`) amb el deployment target.
2. **`vamp_host_local`** (host propi, `eines/vamp_host.cpp`) → `clang++` amb
   `-mmacosx-version-min=10.13` (i `-msse -msse2`, com al Linux).
3. **Plugins Vamp** (`nnls-chroma` + `qm-vamp-plugins`) → `.dylib`:
   - `qm-vamp-plugins`: des de font (`c4dm/qm-vamp-plugins` + `c4dm/qm-dsp`).
   - `Chordino`/`nnls-chroma`: des de font; el repo ja porta **`Makefile.osx`**
     (`codi_font_chordino/`).
   - Sortides a `nnls-chroma-macos-local/` i `qm-vamp-plugins-macos-local/`
     (els noms que ja espera `app/plataforma.py`).

## 4. Altres peces

- **ffmpeg**: build **estàtic** d'[evermeet.cx](https://evermeet.cx/ffmpeg/)
  (requereix 10.13 ✅) → `portable/bin/ffmpeg`.
- **Empaquetat**: `pyinstaller --windowed --onedir` amb les dades
  (`app/`, `eines/`, `icones/`, `icona/`, els directoris dels plugins,
  `vamp_host_local`, `portable/bin/ffmpeg`, `docs/`…). El launcher `.sh`
  queda substituït pel binari de l'.app.

## 5. Verificació del mínim (obligatòria al CI)

```bash
# El binari ha de declarar 10.13 com a mínim:
otool -l <binari> | grep -A3 LC_BUILD_VERSION | grep minos      # -> minos 10.13
# (en binaris antics pot sortir LC_VERSION_MIN_MACOSX -> version 10.13)
```

S'ha de comprovar per a: `vamp_host_local`, els `.dylib` dels plugins,
`libvamp-hostsdk`, `libsndfile` i l'executable de l'.app.

## 6. Riscos i punts oberts

| Risc | Nota |
|---|---|
| **Xcode 16 / SDK de macOS 15** al runner | Apple encara accepta `-mmacosx-version-min=10.13` amb el SDK actual, però cal **verificar-ho** amb `otool` a cada build |
| `libsndfile` des de font | Cal `cmake` (o autotools) + `libFLAC`/`libogg`/`libvorbis`/`libopus` estàtics **també a 10.13** (o enllaçats estàticament per evitar dependències) |
| `Makefile.osx` del Chordino | No s'ha provat mai en aquest entorn; pot caldre adaptar flags |
| PyInstaller a 10.13 | El bootloader ja apunta a 10.13 per defecte ✅ (verificar-ho igualment) |
| **Quarantine** a macOS modern | L'usuari haurà d'obrir amb clic-dret ▸ Obrir (documentar-ho) |

## 7. Pla d'iteracions al CI

1. **Iteració 1** — validar el runner i les rodes: `macos-15-intel` + Python 3.12
   + `PyQt5==5.15.10` + `numpy<2` + `pyinstaller`, i comprovar que el wheel
   instal·la i importa.
2. **Iteració 2** — natius: `libvamp-hostsdk` + `libsndfile` + el host + els
   plugins, amb `otool` verificant `minos 10.13`.
3. **Iteració 3** — empaquetat PyInstaller + ZIP + artefacte.
4. **Iteració 4** — prova real: l'operador arrenca el **Hackintosh (sdb)** i
   obre l'.app; els agents no hi tenen accés directe.

## 8. Fitxers implicats

| Fitxer | Estat |
|---|---|
| `.github/workflows/build-macos.yml` | **NOU** (aquest treball) |
| `docs/PLANIFICACIO_MACOS.md` | **NOU** (aquest document) |
| `eines/compila_vamp_plugins.sh` | **modificat per OC-2** (dispatch per SO; s'hi afegeix la branca macOS) |
| `app/plataforma.py` | ja preveu els noms `*-macos-local` i `ffplay` ✅ |
