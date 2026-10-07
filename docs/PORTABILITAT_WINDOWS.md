# Portabilitat a Windows (x64)

> **2026-10-07 — Fase 1 del pla multi-SO.** Documenta com es construeix el
> paquet portable de **Windows x64** de l'AUTO CHORDS, amb **tots els natius a
> dins** (host Vamp, plugins, ffmpeg) i **sense instal·lar res** al sistema
> (només cal Windows 10/11 x64). Vegeu també `ROADMAP.md` §9.

## 1. Què es construeix

Un **ZIP portable** amb l'executable `AutoChords.exe` (PyInstaller `--onedir`)
i, a dins, tot el que l'app necessita:

| Peça | Origen | Carpeta |
|------|--------|---------|
| GUI + pipeline | PyInstaller (Python 3.12 + PyQt5 + `numpy<2`) | `AutoChords.exe` + `_internal/` |
| Host Vamp propi | compilat amb **MSYS2 / MINGW64** | `_internal/vamp_host_local.exe` |
| Chordino (nnls-chroma) | **compilat** des de `codi_font_chordino/` (mingw-w64) | `_internal/nnls-chroma-win64-local/` |
| Queen Mary | **binari oficial 1.8.0 win64** | `_internal/qm-vamp-plugins-win64-local/` |
| `libsndfile` + còdecs + runtimes MinGW | clausura de dependències del host | `_internal/*.dll` |
| ffmpeg estàtic | gyan.dev (release-essentials) | `_internal/portable/bin/ffmpeg.exe` |

`app/plataforma.py` ja espera aquests noms (`nnls-chroma-win64-local`,
`qm-vamp-plugins-win64-local`, `vamp_host_local.exe`).

## 2. Com es dispara

`.github/workflows/build-windows.yml` (**manual**, `workflow_dispatch`):

> GitHub > Actions > **Compilar paquet Windows (x64)** > *Run workflow*.

Fa, en ordre: MSYS2 → `eines/compila_vamp_plugins.sh` (branca Windows) →
Python + rodes → ffmpeg → **smoke test** dels natius → PyInstaller → **smoke
test del paquet** → ZIP-artefacte → tests unitaris. No fa cap push.

`windows-2022` és el runner; **cap build local de Windows** no cal.

## 3. La branca Windows de `compila_vamp_plugins.sh`

El script **detecta el SO** amb `uname -s` i té tres branques (`Linux`,
`Windows`, `macOS`). La de Windows:

1. **Chordino** — compila `codi_font_chordino/` amb `gcc`/`g++` de MINGW64 i
   enllaça `libgcc`/`libstdc++` **estàtics**, amb un `.def` que exporta
   `vampGetPluginDescriptor`. Resultat: un `.dll` **self-contained** (només
   `KERNEL32.dll`/`msvcrt.dll`). Receta provada (mingw-w64) que evita el
   `Makefile.mingw` original, que amb `--retain-symbols-file` i el guió baix
   del símbol (32-bit) deixaria el `.dll` sense exports en 64-bit.
2. **Queen Mary** — baixa el **binari oficial win64** (Redmine id 2622) i, si
   falla, cau al mirall `xlights.org/downloads/vamp64/`. Es verifica que sigui
   de 64 bits.
3. **Host** — compila `eines/vamp_host.cpp` enllaçant `libvamp-hostsdk` estàtic
   i `libsndfile` dinàmic, i recull **recursivament** les DLLs no-sistema
   (`objdump -p` → `DLL Name`) a `portable/win-dlls/` (gitignored).

## 4. Empaquetat (PyInstaller)

`eines/AutoChords-win.spec` (`--onedir`, `console=False`):

* **Entry**: `eines/launcher_pyinstaller.py` (**no** `app/main.py`).
* **Datas**: `acords_a_live.py`, `vamp_host_local.exe`, `icones/`, els dos
  directoris de plugins, `portable/bin/ffmpeg.exe` i les DLLs de runtime.
* `hiddenimports` per als mòduls de primer nivell que viuen a `app/`
  (`pipeline`, `theme`, `metronom`, `icones`…) i el paquet `app`.

### El llançador i el subprocés `acords_a_live.py`

PyInstaller fa que `sys.executable` sigui `AutoChords.exe`. L'app, però, torna
a invocar-se per executar `acords_a_live.py` (`app/pipeline.run_acords_py`). En
mode congelat això reobriria la GUI. `launcher_pyinstaller.py` detecta el cas
(1r argument = `acords_a_live.py`) i l'executa **en el mateix procés** amb
`runpy`, sense tocar `app/`. El mateix llançador serveix per a **macOS**.

## 5. Verificació

* **Smoke test** (`eines/prova_windows.py`): genera un WAV sintètic (un acord +
  pulsacions), executa el host amb **Chordino** i **qm-tempotracker** i
  comprova que els plugins carreguen i escriuen CSV. S'executa **dues** vegades:
  sobre l'arrel del repo (natius acabats de compilar) i sobre
  `dist/AutoChords/_internal` (natius dins el paquet).
* **Tests unitaris**: `python -m unittest tests.test_pipeline_export tests.test_partitura`.
* A mà (operador): descomprimir el ZIP i obrir `AutoChords.exe`. L'estat
  (log/opcions/temp) va a `%LOCALAPPDATA%` o al propi paquet, mai en una carpeta
  de només lectura (vegeu `app/config.py`).

## 6. Requisits i limitacions

* **Windows 10/11 x64**. L'app **no es signa** → SmartScreen pot avisar
  («More info» > «Run anyway»).
* La reproducció d'àudio fa servir **`ffplay`** (del paquet) perquè
  `paplay`/`aplay` són de Linux (`app/plataforma.py`).
* MuseScore (PDF/MSCZ de la partitura) és **opcional**: si l'usuari el té
  instal·lat, es genera el PDF; si no, sempre queda el MusicXML.

## 7. Regenerar en local (només si cal)

En un entorn MSYS2 MINGW64 amb `mingw-w64-x86_64-{gcc,vamp-plugin-sdk,libsndfile,boost}`:

```bash
bash eines/compila_vamp_plugins.sh          # host .exe + plugins .dll
# i, amb un Python x64 amb PyQt5/numpy/pyinstaller + portable/bin/ffmpeg.exe:
pyinstaller --noconfirm --clean eines/AutoChords-win.spec
```

En un **Linux** es pot seguir validant la branca de sempre sense regressió
(`uname -s` = `Linux` → comportament idèntic a abans).
